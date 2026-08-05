from __future__ import annotations

import base64
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import tempfile
from typing import Any, Iterator

from .contracts import canonical_json_bytes, sha256_bytes, sha256_json


EVIDENCE_BINDING_REVISION = "chalxius-evidence-library-binding-1"
PAPER_SYNC_REVISION = "chalxius-paper-evidence-sync-1"
PAPER_ATTESTATION_REVISION = "chalxius-paper-evidence-attestation-2"
PAPER_EVIDENCE_MATERIAL_USES = [
    "background",
    "citation_source",
    "inspiration",
    "research_material",
]
FACT_CAPSULE_REVISION = "chalxius-external-fact-evidence-capsule-1"
BRIDGE_CAPSULE_REVISION = "chalxius-evidence-bridge-capsule-1"
EVIDENCE_ASSOCIATION_REVISION = "chalxius-evidence-triad-association-1"
EVIDENCE_ASSOCIATION_REQUEST_REVISION = (
    "chalxius-evidence-triad-association-request-1"
)
EVIDENCE_ASSOCIATION_EFFECT_REVISION = (
    "chalxius-evidence-triad-association-effect-1"
)
EVIDENCE_ASSOCIATION_PLANNING_REVISION = (
    "chalxius-evidence-triad-association-planning-attempt-1"
)


class EvidencePlane:
    """Project-local adapter to the cross-project, nontruth Evidence library."""

    def __init__(self, store: Any) -> None:
        self.store = store
        self.project_root = Path(store.root).resolve()
        self.root = self.project_root / "evidence"
        self.outbox_dir = self.root / "outbox" / "by-id"
        self.receipts_dir = self.root / "receipts" / "by-snapshot"
        self.fact_capsules_dir = self.root / "fact-capsules" / "by-id"
        self.association_outbox_dir = (
            self.root / "association-outbox" / "by-id"
        )
        self.association_effects_dir = (
            self.root / "association-effects" / "by-request"
        )
        self.association_planning_dir = (
            self.root / "association-planning" / "by-id"
        )
        self.binding_path = self.root / "library-binding.json"
        self.lock_path = self.root / ".evidence-sync.lock"
        self.skill_root = Path(__file__).resolve().parents[2]

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Evidence JSON is missing or unsafe: {path}")
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"Evidence JSON must be an object: {path}")
        return value

    @staticmethod
    def _write_json_once(path: Path, value: dict[str, Any]) -> None:
        payload = json.dumps(
            value, ensure_ascii=False, sort_keys=True, indent=2
        ).encode("utf-8") + b"\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            raise ValueError(f"refusing to write through Evidence symlink: {path}")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(path, flags, 0o600)
        except FileExistsError:
            if not path.is_file() or path.is_symlink() or path.read_bytes() != payload:
                raise ValueError(f"immutable Evidence collision at {path}")
            return
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            raise

    @contextlib.contextmanager
    def _lock(self) -> Iterator[None]:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+b") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _runtime(self) -> dict[str, str]:
        version_path = self.skill_root / "VERSION"
        manifest_path = self.skill_root / "MANIFEST.sha256"
        return {
            "skill_root": str(self.skill_root),
            "version": version_path.read_text(encoding="utf-8").strip(),
            "version_sha256": sha256_bytes(version_path.read_bytes()),
            "manifest_file_sha256": sha256_bytes(manifest_path.read_bytes()),
        }

    def _binding(self) -> dict[str, Any] | None:
        environment_root = os.environ.get("CHALXIUS_EVIDENCE_LIBRARY_ROOT", "").strip()
        environment_cli = os.environ.get("CHALXIUS_EVIDENCE_LIBRARY_CLI", "").strip()
        if environment_root:
            candidate = {
                "schema_version": 1,
                "contract_revision": EVIDENCE_BINDING_REVISION,
                "library_root": environment_root,
                "paperlib_cli": environment_cli,
                "source": "environment",
            }
        else:
            paths = [
                self.binding_path,
                Path.home() / ".codex" / "chalxius" / "evidence-library.json",
            ]
            selected = next((path for path in paths if path.is_file() and not path.is_symlink()), None)
            if selected is None:
                return None
            candidate = self._read_json(selected)
            candidate = {**candidate, "source": str(selected)}
        required = {
            "schema_version",
            "contract_revision",
            "library_root",
            "paperlib_cli",
            "source",
        }
        if set(candidate) != required:
            raise ValueError("Evidence library binding fields are not exact")
        if (
            candidate["schema_version"] != 1
            or candidate["contract_revision"] != EVIDENCE_BINDING_REVISION
        ):
            raise ValueError("Evidence library binding contract mismatch")
        library_root = Path(str(candidate["library_root"])).expanduser().resolve()
        if not (library_root / "library.json").is_file():
            raise ValueError("Evidence library root is not initialized")
        cli_value = str(candidate["paperlib_cli"]).strip()
        if cli_value:
            cli = Path(cli_value).expanduser().resolve()
        else:
            library_cli = library_root / "bin" / "paperlib"
            bundled_cli = self.skill_root / "scripts" / "paperlib"
            cli = (
                library_cli
                if library_cli.is_file() and not library_cli.is_symlink()
                else bundled_cli
            )
        if cli.is_symlink() or not cli.is_file():
            raise ValueError("Evidence library CLI is missing or unsafe")
        return {
            **candidate,
            "library_root": str(library_root),
            "paperlib_cli": str(cli),
        }

    def _run_library(self, binding: dict[str, Any], *arguments: str) -> dict[str, Any]:
        command = [binding["paperlib_cli"], *arguments]
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        stream = completed.stdout if completed.returncode == 0 else completed.stderr
        try:
            result = json.loads(stream)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Evidence library returned non-JSON output: " + stream.strip()[:500]
            ) from exc
        if completed.returncode != 0 or not isinstance(result, dict) or result.get("ok") is not True:
            raise ValueError(
                "Evidence library command failed: "
                + str(result.get("error", stream.strip()))
            )
        return result

    def _snapshot_request(self, snapshot_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        paper = self.store.paper_logic()
        manifest = paper.snapshot_manifest(snapshot_id)
        revision_id = manifest["revision_ids"][-1]
        revision = paper.revision(revision_id)
        manifest_path = paper.snapshots_dir / snapshot_id / "manifest.json"
        body = {
            "schema_version": 1,
            "contract_revision": PAPER_SYNC_REVISION,
            "project_id": self.store.project_id(),
            "paper_id": manifest["paper_id"],
            "snapshot_id": snapshot_id,
            "snapshot_manifest_sha256": sha256_bytes(manifest_path.read_bytes()),
            "graph_kind": manifest["graph_kind"],
            "source_role": manifest.get("source_role", "legacy_unspecified"),
            "revision_id": revision_id,
            "source_artifact_sha256": revision["source"]["artifact_sha256"],
            "source_artifact_relpath": revision["artifact_relpath"],
            "source_title": revision["source"]["title"],
            "source_version": revision["source"]["version"],
            "source_locator": revision["source"]["artifact_locator"],
            "source_mime_type": revision["source"]["mime_type"],
            "source_retrieved_at": revision["source"]["retrieved_at"],
            "supersedes_snapshot_id": manifest["supersedes_snapshot_id"],
            "runtime": self._runtime(),
            "truth_effect": "none",
            "premise_eligible": False,
        }
        request_id = "pes-" + sha256_json(body)
        return {**body, "request_id": request_id}, manifest

    def _receipt_path(self, snapshot_id: str) -> Path:
        return self.receipts_dir / f"{snapshot_id}.json"

    def paper_snapshot_frozen(self, snapshot_id: str, *, actor: str) -> dict[str, Any]:
        try:
            with self._lock():
                receipt_path = self._receipt_path(snapshot_id)
                if receipt_path.exists():
                    receipt = self._read_json(receipt_path)
                    return {
                        "status": "synced",
                        "request_id": receipt["request_id"],
                        "evidence_id": receipt["evidence_id"],
                        "receipt_path": str(receipt_path),
                        "truth_effect": "none",
                    }
                request, manifest = self._snapshot_request(snapshot_id)
                request_path = self.outbox_dir / f"{request['request_id']}.json"
                self._write_json_once(request_path, request)
                binding = self._binding()
                if binding is None:
                    return {
                        "status": "pending_unconfigured",
                        "request_id": request["request_id"],
                        "outbox_path": str(request_path),
                        "truth_effect": "none",
                    }
                artifact = self.project_root / request["source_artifact_relpath"]
                if artifact.is_symlink() or not artifact.is_file():
                    raise ValueError("Paper Evidence source artifact is missing or unsafe")
                raw = artifact.read_bytes()
                if sha256_bytes(raw) != request["source_artifact_sha256"]:
                    raise ValueError("Paper Evidence source artifact hash drifted")
                if not raw.startswith(b"%PDF-"):
                    return {
                        "status": "pending_missing_exact_pdf",
                        "request_id": request["request_id"],
                        "outbox_path": str(request_path),
                        "truth_effect": "none",
                    }
                library_root = binding["library_root"]
                local_key = f"chalxius:{request['project_id']}:{request['paper_id']}"
                paper_result = self._run_library(
                    binding,
                    "paper-add",
                    "--root",
                    library_root,
                    "--local-key",
                    local_key,
                    "--title",
                    request["source_title"],
                )
                version_arguments = [
                    "version-add",
                    "--root",
                    library_root,
                    "--paper-id",
                    paper_result["paper_id"],
                    "--label",
                    request["source_version"],
                    "--kind",
                    "other",
                    "--pdf",
                    str(artifact),
                    "--source-locator",
                    request["source_locator"],
                    "--retrieved-at",
                    request["source_retrieved_at"][:10],
                ]
                version_result = self._run_library(binding, *version_arguments)
                predecessor_receipt: dict[str, Any] | None = None
                if request["supersedes_snapshot_id"]:
                    prior_path = self._receipt_path(request["supersedes_snapshot_id"])
                    if not prior_path.is_file():
                        raise ValueError(
                            "superseding Paper snapshot cannot sync before its predecessor"
                        )
                    predecessor_receipt = self._read_json(prior_path)
                graph_arguments = [
                    "graph-add",
                    "--root",
                    library_root,
                    "--paper-id",
                    paper_result["paper_id"],
                    "--version-id",
                    version_result["version_id"],
                    "--graph-root",
                    str(self.store.paper_logic().root),
                    "--graph-kind",
                    "paper_logic" if request["graph_kind"] == "logic" else "paper_audit",
                    "--chalxius-root",
                    str(self.skill_root),
                    "--source-project-id",
                    request["project_id"],
                    "--snapshot-id",
                    snapshot_id,
                ]
                if predecessor_receipt is not None:
                    graph_arguments.extend(
                        ["--supersedes-graph-id", predecessor_receipt["graph_id"]]
                    )
                graph_result = self._run_library(binding, *graph_arguments)
                audit = self.store.paper_logic().audit(blackboard=self.store.blackboard())
                snapshot_nodes, _ = self.store.paper_logic().snapshot_objects(snapshot_id)
                reviews = [
                    self.store.paper_logic().review(review_id)
                    for review_id in manifest["review_ids"]
                ]
                attestation = {
                    "schema_version": 1,
                    "contract_revision": PAPER_ATTESTATION_REVISION,
                    "graph_id": graph_result["graph_id"],
                    "graph_tree_sha256": graph_result["tree_sha256"],
                    "paper_snapshot_id": snapshot_id,
                    "snapshot_manifest_sha256": request["snapshot_manifest_sha256"],
                    "snapshot_graph_kind": request["graph_kind"],
                    "source_role": request["source_role"],
                    "material_uses": PAPER_EVIDENCE_MATERIAL_USES,
                    "source_project_id": request["project_id"],
                    "pdf_sha256": version_result["pdf_sha256"],
                    "node_ids": sorted(snapshot_nodes),
                    "review_ids": sorted(manifest["review_ids"]),
                    "review_profiles": sorted(review["profile"] for review in reviews),
                    "paper_logic_audit": audit,
                    "paper_logic_audit_sha256": sha256_json(audit),
                    "truth_effect": "none",
                }
                descriptor, temporary = tempfile.mkstemp(
                    prefix=".paper-evidence-attestation.", suffix=".json", dir=self.root
                )
                temporary_path = Path(temporary)
                try:
                    with os.fdopen(descriptor, "wb") as handle:
                        handle.write(canonical_json_bytes(attestation) + b"\n")
                        handle.flush()
                        os.fsync(handle.fileno())
                    evidence_arguments = [
                        "evidence-paper-add",
                        "--root",
                        library_root,
                        "--graph-id",
                        graph_result["graph_id"],
                        "--attestation",
                        str(temporary_path),
                        "--sync-mode",
                        "automatic_after_reviewed_freeze",
                    ]
                    if predecessor_receipt is not None:
                        evidence_arguments.extend(
                            [
                                "--supersedes-evidence-id",
                                predecessor_receipt["evidence_id"],
                            ]
                        )
                    evidence_result = self._run_library(binding, *evidence_arguments)
                finally:
                    try:
                        temporary_path.unlink()
                    except FileNotFoundError:
                        pass
                receipt_body = {
                    "schema_version": 1,
                    "contract_revision": PAPER_SYNC_REVISION,
                    "request_id": request["request_id"],
                    "snapshot_id": snapshot_id,
                    "library_root": library_root,
                    "library_id": self._read_json(Path(library_root) / "library.json")[
                        "library_id"
                    ],
                    "paper_id": paper_result["paper_id"],
                    "version_id": version_result["version_id"],
                    "graph_id": graph_result["graph_id"],
                    "evidence_id": evidence_result["evidence_id"],
                    "actor": actor,
                    "truth_effect": "none",
                    "premise_eligible": False,
                }
                receipt = {
                    **receipt_body,
                    "receipt_id": "per-" + sha256_json(receipt_body),
                }
                self._write_json_once(receipt_path, receipt)
                self._run_library(binding, "index", "--root", library_root)
                return {
                    "status": "synced",
                    "request_id": request["request_id"],
                    "evidence_id": evidence_result["evidence_id"],
                    "receipt_path": str(receipt_path),
                    "truth_effect": "none",
                }
        except Exception as exc:
            return {
                "status": "pending_error",
                "snapshot_id": snapshot_id,
                "error": str(exc),
                "truth_effect": "none",
            }

    @staticmethod
    def _encoded_object(role: str, object_id: str, raw: bytes) -> dict[str, str]:
        return {
            "role": role,
            "object_id": object_id,
            "sha256": sha256_bytes(raw),
            "bytes_base64": base64.b64encode(raw).decode("ascii"),
        }

    def _association_request_path(self, request_id: str) -> Path:
        return self.association_outbox_dir / f"{request_id}.json"

    def _association_effect_path(self, request_id: str) -> Path:
        return self.association_effects_dir / f"{request_id}.json"

    def _association_planning_path(self, attempt_id: str) -> Path:
        return self.association_planning_dir / f"{attempt_id}.json"

    @staticmethod
    def _valid_sha256(value: Any) -> bool:
        return (
            isinstance(value, str)
            and len(value) == 64
            and all(character in "0123456789abcdef" for character in value)
        )

    def _validate_association_planning_attempt(
        self,
        attempt: dict[str, Any],
    ) -> None:
        required = {
            "schema_version",
            "contract_revision",
            "destination_project_id",
            "source_project_id",
            "source_root_locator",
            "source_audit_sha256",
            "active_facts_sha256",
            "fact_capsule_id",
            "fact_capsule_file_sha256",
            "fact_evidence_id",
            "fact_evidence_record_sha256",
            "authorization",
            "association_policy",
            "fact_evidence_import_preserved",
            "cross_project_fact_authority",
            "premise_eligible",
            "truth_effect",
            "attempt_id",
        }
        if set(attempt) != required:
            raise ValueError(
                "Evidence association planning attempt fields are not exact"
            )
        core = {key: value for key, value in attempt.items() if key != "attempt_id"}
        if (
            type(attempt["schema_version"]) is not int
            or attempt["schema_version"] != 1
            or attempt["contract_revision"]
            != EVIDENCE_ASSOCIATION_PLANNING_REVISION
            or attempt["attempt_id"] != "eap-" + sha256_json(core)
            or attempt["destination_project_id"] != self.store.project_id()
            or attempt["fact_evidence_import_preserved"] is not True
            or attempt["cross_project_fact_authority"] is not False
            or attempt["premise_eligible"] is not False
            or attempt["truth_effect"] != "none"
        ):
            raise ValueError(
                "Evidence association planning attempt identity or authority mismatch"
            )
        for field in (
            "source_project_id",
            "source_root_locator",
            "fact_capsule_id",
            "fact_evidence_id",
        ):
            if not isinstance(attempt[field], str) or not attempt[field].strip():
                raise ValueError(
                    "Evidence association planning attempt identifier is invalid"
                )
        if (
            not attempt["fact_capsule_id"].startswith("efc-")
            or not attempt["fact_evidence_id"].startswith("evd-")
        ):
            raise ValueError(
                "Evidence association planning attempt object type is invalid"
            )
        for field in (
            "source_audit_sha256",
            "active_facts_sha256",
            "fact_capsule_file_sha256",
            "fact_evidence_record_sha256",
        ):
            if not self._valid_sha256(attempt[field]):
                raise ValueError(
                    "Evidence association planning attempt hash is invalid"
                )
        authorization = attempt["authorization"]
        if (
            not isinstance(authorization, dict)
            or set(authorization) != {"actor", "reason"}
            or any(
                not isinstance(authorization[field], str)
                or not authorization[field].strip()
                for field in ("actor", "reason")
            )
        ):
            raise ValueError(
                "Evidence association planning authorization is invalid"
            )
        if attempt["association_policy"] != {
            "derivation": "exact_release_paper_evidence_ref_and_local_receipt",
            "inferred_from_title_doi_or_credibility": False,
        }:
            raise ValueError(
                "Evidence association planning inference policy mismatch"
            )

    def _persist_association_planning_attempt(
        self,
        *,
        source_path: Path,
        inventory: dict[str, Any],
        capsule: dict[str, Any],
        capsule_path: Path,
        fact_result: dict[str, Any],
        actor: str,
        reason: str,
    ) -> dict[str, Any]:
        body = {
            "schema_version": 1,
            "contract_revision": EVIDENCE_ASSOCIATION_PLANNING_REVISION,
            "destination_project_id": self.store.project_id(),
            "source_project_id": inventory["source_project_id"],
            "source_root_locator": str(source_path),
            "source_audit_sha256": sha256_json(inventory["source_audit"]),
            "active_facts_sha256": sha256_json(inventory["active_facts"]),
            "fact_capsule_id": capsule["capsule_id"],
            "fact_capsule_file_sha256": sha256_bytes(capsule_path.read_bytes()),
            "fact_evidence_id": fact_result["evidence_id"],
            "fact_evidence_record_sha256": fact_result["record"][
                "record_sha256"
            ],
            "authorization": {"actor": actor, "reason": reason},
            "association_policy": {
                "derivation": (
                    "exact_release_paper_evidence_ref_and_local_receipt"
                ),
                "inferred_from_title_doi_or_credibility": False,
            },
            "fact_evidence_import_preserved": True,
            "cross_project_fact_authority": False,
            "premise_eligible": False,
            "truth_effect": "none",
        }
        attempt = {**body, "attempt_id": "eap-" + sha256_json(body)}
        self._validate_association_planning_attempt(attempt)
        self._write_json_once(
            self._association_planning_path(attempt["attempt_id"]), attempt
        )
        return attempt

    def _validated_fact_evidence_record(
        self,
        *,
        attempt: dict[str, Any],
        binding: dict[str, Any],
        capsule: dict[str, Any],
        capsule_bytes: bytes,
    ) -> dict[str, Any]:
        library_root = Path(binding["library_root"])
        record_path = (
            library_root
            / "records"
            / "evidence_items"
            / "by-id"
            / f"{attempt['fact_evidence_id']}.json"
        )
        record = self._read_json(record_path)
        record_core = {
            key: value for key, value in record.items() if key != "record_sha256"
        }
        source = record.get("source")
        expected_fact_ids = sorted(
            item["fact_id"] for item in capsule["active_facts"]
        )
        if (
            record.get("object_id") != attempt["fact_evidence_id"]
            or record.get("record_sha256") != sha256_json(record_core)
            or record.get("record_sha256")
            != attempt["fact_evidence_record_sha256"]
            or record.get("evidence_kind") != "external_fact_graph"
            or record.get("source_project_id") != attempt["source_project_id"]
            or not isinstance(source, dict)
            or source.get("capsule_id") != attempt["fact_capsule_id"]
            or source.get("capsule_sha256")
            != attempt["fact_capsule_file_sha256"]
            or source.get("active_fact_ids") != expected_fact_ids
            or record.get("premise_eligible") is not False
        ):
            raise ValueError(
                "Evidence association planning Fact Evidence record drifted"
            )
        relative_value = source.get("capsule_path")
        if not isinstance(relative_value, str):
            raise ValueError(
                "Evidence association planning Fact Evidence capsule path is invalid"
            )
        relative = PurePosixPath(relative_value)
        if relative.is_absolute() or not relative.parts or ".." in relative.parts:
            raise ValueError(
                "Evidence association planning Fact Evidence capsule path is unsafe"
            )
        library_capsule = library_root.joinpath(*relative.parts)
        current = library_root
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise ValueError(
                    "Evidence association planning Fact Evidence capsule is unsafe"
                )
        try:
            library_capsule.resolve().relative_to(library_root)
        except ValueError as exc:
            raise ValueError(
                "Evidence association planning Fact Evidence capsule escapes library"
            ) from exc
        if not library_capsule.is_file():
            raise ValueError(
                "Evidence association planning Fact Evidence capsule is missing"
            )
        library_capsule_bytes = library_capsule.read_bytes()
        if (
            sha256_bytes(library_capsule_bytes)
            != attempt["fact_capsule_file_sha256"]
            or library_capsule_bytes != capsule_bytes
        ):
            raise ValueError(
                "Evidence association planning Fact Evidence capsule copy drifted"
            )
        return record

    def _validated_association_planning_inputs(
        self,
        attempt: dict[str, Any],
        *,
        binding: dict[str, Any],
    ) -> dict[str, Any]:
        self._validate_association_planning_attempt(attempt)
        capsule_path = self.fact_capsules_dir / f"{attempt['fact_capsule_id']}.json"
        if capsule_path.is_symlink() or not capsule_path.is_file():
            raise ValueError(
                "Evidence association planning Fact capsule is missing or unsafe"
            )
        capsule_bytes = capsule_path.read_bytes()
        if sha256_bytes(capsule_bytes) != attempt["fact_capsule_file_sha256"]:
            raise ValueError("Evidence association planning Fact capsule drifted")
        capsule = self._read_json(capsule_path)
        capsule_body = {
            key: value for key, value in capsule.items() if key != "capsule_id"
        }
        active_facts = capsule.get("active_facts")
        source_audit = capsule.get("source_audit")
        if (
            capsule.get("schema_version") != 1
            or capsule.get("contract_revision") != FACT_CAPSULE_REVISION
            or capsule.get("capsule_id") != "efc-" + sha256_json(capsule_body)
            or capsule.get("capsule_id") != attempt["fact_capsule_id"]
            or capsule.get("source_project_id") != attempt["source_project_id"]
            or capsule.get("source_root_locator")
            != attempt["source_root_locator"]
            or not isinstance(active_facts, list)
            or not active_facts
            or any(not isinstance(item, dict) for item in active_facts)
            or not isinstance(source_audit, dict)
            or sha256_json(active_facts) != attempt["active_facts_sha256"]
            or sha256_json(source_audit) != attempt["source_audit_sha256"]
            or capsule.get("truth_effect") != "none"
            or capsule.get("premise_eligible") is not False
        ):
            raise ValueError(
                "Evidence association planning Fact capsule identity drifted"
            )
        fact_record = self._validated_fact_evidence_record(
            attempt=attempt,
            binding=binding,
            capsule=capsule,
            capsule_bytes=capsule_bytes,
        )
        source_path = Path(attempt["source_root_locator"]).expanduser()
        if (
            source_path.is_symlink()
            or not source_path.is_dir()
            or source_path.resolve() != source_path
        ):
            raise ValueError(
                "Evidence association planning source root is missing or drifted"
            )
        source_store = self.store.__class__(source_path)
        if source_store.project_id() != attempt["source_project_id"]:
            raise ValueError(
                "Evidence association planning source project identity drifted"
            )
        release_bytes: dict[str, bytes] = {}
        for encoded in capsule.get("objects", []):
            if not isinstance(encoded, dict) or encoded.get("role") != "release":
                continue
            if set(encoded) != {"role", "object_id", "sha256", "bytes_base64"}:
                raise ValueError(
                    "Evidence association planning encoded release is invalid"
                )
            object_id = encoded["object_id"]
            if not isinstance(object_id, str) or object_id in release_bytes:
                raise ValueError(
                    "Evidence association planning encoded release identity is invalid"
                )
            try:
                raw = base64.b64decode(encoded["bytes_base64"], validate=True)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "Evidence association planning encoded release bytes are invalid"
                ) from exc
            if sha256_bytes(raw) != encoded["sha256"]:
                raise ValueError(
                    "Evidence association planning encoded release hash drifted"
                )
            release_bytes[object_id] = raw
        release_records: dict[str, dict[str, Any]] = {}
        lifecycle = source_store.v5_lifecycle()
        for item in active_facts:
            release_id = item.get("release_id")
            if not isinstance(release_id, str) or release_id not in release_bytes:
                raise ValueError(
                    "Evidence association planning source release is absent from capsule"
                )
            release_path = lifecycle.candidate_releases_dir / f"{release_id}.json"
            if release_path.is_symlink() or not release_path.is_file():
                raise ValueError(
                    "Evidence association planning source release is missing or unsafe"
                )
            live_bytes = release_path.read_bytes()
            if live_bytes != release_bytes[release_id]:
                raise ValueError(
                    "Evidence association planning source release bytes drifted"
                )
            try:
                release = json.loads(live_bytes)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError(
                    "Evidence association planning source release is not JSON"
                ) from exc
            if (
                not isinstance(release, dict)
                or release.get("release_id") != release_id
                or release.get("release_sha256") != item.get("release_sha256")
            ):
                raise ValueError(
                    "Evidence association planning source release identity drifted"
                )
            previous = release_records.setdefault(release_id, release)
            if previous != release:
                raise ValueError(
                    "Evidence association planning source release bytes conflict"
                )
        inventory = {
            "source_project_id": capsule["source_project_id"],
            "source_audit": source_audit,
            "active_facts": active_facts,
            "revoked_fact_ids": capsule.get("revoked_fact_ids", []),
        }
        return {
            "source_path": source_path,
            "source_store": source_store,
            "inventory": inventory,
            "capsule": capsule,
            "capsule_path": capsule_path,
            "fact_result": {
                "evidence_id": attempt["fact_evidence_id"],
                "record": fact_record,
            },
            "release_records": release_records,
        }

    def _validate_association_request(
        self,
        request: dict[str, Any],
        *,
        binding: dict[str, Any] | None = None,
    ) -> None:
        required = {
            "schema_version",
            "contract_revision",
            "destination_project_id",
            "source_project_id",
            "source_root_locator",
            "source_release_id",
            "source_release_sha256",
            "paper_evidence_ref",
            "paper_evidence_ref_sha256",
            "paper_sync_request",
            "paper_sync_request_file_sha256",
            "paper_evidence_receipt",
            "paper_evidence_receipt_file_sha256",
            "fact_evidence_id",
            "fact_evidence_record_sha256",
            "fact_capsule_id",
            "fact_capsule_sha256",
            "associated_fact_ids",
            "authorization",
            "association_policy",
            "cross_project_fact_authority",
            "premise_eligible",
            "truth_effect",
            "request_id",
        }
        if set(request) != required:
            raise ValueError("Evidence association request fields are not exact")
        core = {key: value for key, value in request.items() if key != "request_id"}
        if (
            request["schema_version"] != 1
            or request["contract_revision"]
            != EVIDENCE_ASSOCIATION_REQUEST_REVISION
            or request["request_id"] != "eas-" + sha256_json(core)
            or request["destination_project_id"] != self.store.project_id()
            or request["cross_project_fact_authority"] is not False
            or request["premise_eligible"] is not False
            or request["truth_effect"] != "none"
        ):
            raise ValueError("Evidence association request identity or authority mismatch")
        text_fields = (
            "source_project_id",
            "source_root_locator",
            "source_release_id",
            "fact_evidence_id",
            "fact_capsule_id",
        )
        if any(
            not isinstance(request[field], str) or not request[field].strip()
            for field in text_fields
        ):
            raise ValueError("Evidence association request identifiers are invalid")
        for field in (
            "source_release_sha256",
            "paper_evidence_ref_sha256",
            "paper_sync_request_file_sha256",
            "paper_evidence_receipt_file_sha256",
            "fact_evidence_record_sha256",
            "fact_capsule_sha256",
        ):
            if not self._valid_sha256(request[field]):
                raise ValueError("Evidence association request hash is invalid")
        fact_ids = request["associated_fact_ids"]
        if (
            not isinstance(fact_ids, list)
            or not fact_ids
            or fact_ids != sorted(set(fact_ids))
            or any(not isinstance(item, str) or not item.strip() for item in fact_ids)
        ):
            raise ValueError("Evidence association request Fact ids are invalid")
        policy = request["association_policy"]
        if policy != {
            "derivation": "exact_release_paper_evidence_ref_and_local_receipt",
            "inferred_from_title_doi_or_credibility": False,
        }:
            raise ValueError("Evidence association request inference policy mismatch")
        authorization = request["authorization"]
        if (
            not isinstance(authorization, dict)
            or set(authorization) != {"actor", "reason"}
            or any(
                not isinstance(authorization[field], str)
                or not authorization[field].strip()
                for field in ("actor", "reason")
            )
        ):
            raise ValueError("Evidence association authorization is invalid")
        ref = request["paper_evidence_ref"]
        ref_fields = {
            "paper_id",
            "snapshot_id",
            "snapshot_sha256",
            "graph_kind",
            "target_artifact_sha256",
            "target_node_ids",
        }
        if (
            not isinstance(ref, dict)
            or set(ref) != ref_fields
            or request["paper_evidence_ref_sha256"] != sha256_json(ref)
            or not self._valid_sha256(ref.get("snapshot_sha256"))
            or not self._valid_sha256(ref.get("target_artifact_sha256"))
            or ref.get("graph_kind") not in {"logic", "audit"}
        ):
            raise ValueError("Evidence association Paper EvidenceRef is invalid")
        target_node_ids = ref["target_node_ids"]
        if (
            not isinstance(target_node_ids, list)
            or not target_node_ids
            or target_node_ids != sorted(set(target_node_ids))
            or any(
                not isinstance(item, str) or not item.strip()
                for item in target_node_ids
            )
        ):
            raise ValueError("Evidence association Paper node ids are invalid")
        sync_request = request["paper_sync_request"]
        if not isinstance(sync_request, dict) or "request_id" not in sync_request:
            raise ValueError("Evidence association Paper sync request is invalid")
        sync_core = {
            key: value for key, value in sync_request.items() if key != "request_id"
        }
        if (
            sync_request["request_id"] != "pes-" + sha256_json(sync_core)
            or sync_request.get("contract_revision") != PAPER_SYNC_REVISION
            or sync_request.get("project_id") != request["source_project_id"]
            or sync_request.get("paper_id") != ref["paper_id"]
            or sync_request.get("snapshot_id") != ref["snapshot_id"]
            or sync_request.get("snapshot_manifest_sha256")
            != ref["snapshot_sha256"]
            or sync_request.get("source_artifact_sha256")
            != ref["target_artifact_sha256"]
            or sync_request.get("truth_effect") != "none"
            or sync_request.get("premise_eligible") is not False
        ):
            raise ValueError("Evidence association Paper sync binding mismatch")
        receipt = request["paper_evidence_receipt"]
        if not isinstance(receipt, dict) or "receipt_id" not in receipt:
            raise ValueError("Evidence association Paper receipt is invalid")
        receipt_core = {
            key: value for key, value in receipt.items() if key != "receipt_id"
        }
        if (
            receipt["receipt_id"] != "per-" + sha256_json(receipt_core)
            or receipt.get("contract_revision") != PAPER_SYNC_REVISION
            or receipt.get("request_id") != sync_request["request_id"]
            or receipt.get("snapshot_id") != ref["snapshot_id"]
            or receipt.get("truth_effect") != "none"
            or receipt.get("premise_eligible") is not False
        ):
            raise ValueError("Evidence association Paper receipt binding mismatch")
        if binding is not None:
            library = self._read_json(Path(binding["library_root"]) / "library.json")
            if (
                Path(str(receipt.get("library_root", ""))).expanduser().resolve()
                != Path(binding["library_root"])
                or receipt.get("library_id") != library.get("library_id")
            ):
                raise ValueError("Evidence association receipt belongs to another library")

    def _validate_association_effect(
        self,
        effect: dict[str, Any],
        *,
        request: dict[str, Any],
    ) -> None:
        required = {
            "schema_version",
            "contract_revision",
            "request_id",
            "request_record_sha256",
            "library_id",
            "association_id",
            "association_record_sha256",
            "paper_evidence_id",
            "fact_evidence_id",
            "associated_fact_ids",
            "executed_by",
            "fact_evidence_import_preserved",
            "cross_project_fact_authority",
            "premise_eligible",
            "truth_effect",
            "effect_id",
        }
        if set(effect) != required:
            raise ValueError("Evidence association effect fields are not exact")
        core = {key: value for key, value in effect.items() if key != "effect_id"}
        receipt = request["paper_evidence_receipt"]
        if (
            effect["schema_version"] != 1
            or effect["contract_revision"]
            != EVIDENCE_ASSOCIATION_EFFECT_REVISION
            or effect["effect_id"] != "eae-" + sha256_json(core)
            or effect["request_id"] != request["request_id"]
            or effect["request_record_sha256"] != sha256_json(request)
            or effect["library_id"] != receipt["library_id"]
            or effect["paper_evidence_id"] != receipt["evidence_id"]
            or effect["fact_evidence_id"] != request["fact_evidence_id"]
            or effect["associated_fact_ids"] != request["associated_fact_ids"]
            or effect["fact_evidence_import_preserved"] is not True
            or effect["cross_project_fact_authority"] is not False
            or effect["premise_eligible"] is not False
            or effect["truth_effect"] != "none"
            or not isinstance(effect["association_id"], str)
            or not effect["association_id"].startswith("eva-")
            or not isinstance(effect["executed_by"], str)
            or not effect["executed_by"].strip()
            or not self._valid_sha256(effect["association_record_sha256"])
        ):
            raise ValueError("Evidence association effect identity or authority mismatch")

    def _validated_local_paper_receipt(
        self,
        *,
        source_store: Any,
        ref: dict[str, Any],
        binding: dict[str, Any],
    ) -> tuple[dict[str, Any], Path, dict[str, Any], Path]:
        manifest_path = (
            source_store.paper_logic().snapshots_dir
            / ref["snapshot_id"]
            / "manifest.json"
        )
        if (
            manifest_path.is_symlink()
            or not manifest_path.is_file()
            or sha256_bytes(manifest_path.read_bytes()) != ref["snapshot_sha256"]
        ):
            raise ValueError("exact Paper EvidenceRef snapshot is missing or drifted")
        receipt_path = (
            Path(source_store.root)
            / "evidence"
            / "receipts"
            / "by-snapshot"
            / f"{ref['snapshot_id']}.json"
        )
        receipt = self._read_json(receipt_path)
        request_id = receipt.get("request_id")
        if not isinstance(request_id, str) or not request_id.startswith("pes-"):
            raise ValueError("local Paper Evidence receipt has no exact request id")
        sync_path = (
            Path(source_store.root)
            / "evidence"
            / "outbox"
            / "by-id"
            / f"{request_id}.json"
        )
        sync_request = self._read_json(sync_path)
        probe = {
            "schema_version": 1,
            "contract_revision": EVIDENCE_ASSOCIATION_REQUEST_REVISION,
            "destination_project_id": self.store.project_id(),
            "source_project_id": source_store.project_id(),
            "source_root_locator": str(Path(source_store.root).resolve()),
            "source_release_id": "probe",
            "source_release_sha256": "0" * 64,
            "paper_evidence_ref": ref,
            "paper_evidence_ref_sha256": sha256_json(ref),
            "paper_sync_request": sync_request,
            "paper_sync_request_file_sha256": sha256_bytes(sync_path.read_bytes()),
            "paper_evidence_receipt": receipt,
            "paper_evidence_receipt_file_sha256": sha256_bytes(
                receipt_path.read_bytes()
            ),
            "fact_evidence_id": "probe",
            "fact_evidence_record_sha256": "0" * 64,
            "fact_capsule_id": "probe",
            "fact_capsule_sha256": "0" * 64,
            "associated_fact_ids": ["probe"],
            "authorization": {"actor": "probe", "reason": "probe"},
            "association_policy": {
                "derivation": (
                    "exact_release_paper_evidence_ref_and_local_receipt"
                ),
                "inferred_from_title_doi_or_credibility": False,
            },
            "cross_project_fact_authority": False,
            "premise_eligible": False,
            "truth_effect": "none",
        }
        probe["request_id"] = "eas-" + sha256_json(probe)
        self._validate_association_request(probe, binding=binding)
        return sync_request, sync_path, receipt, receipt_path

    @staticmethod
    def _mapped_fact_ids_for_paper_ref(
        release: dict[str, Any],
        ref: dict[str, Any],
        active_release_fact_ids: set[str],
    ) -> list[str]:
        assurance = release.get("requested_assurance")
        coverage = assurance.get("coverage") if isinstance(assurance, dict) else None
        if not isinstance(coverage, list):
            return []
        target_nodes = set(ref.get("target_node_ids", []))
        return sorted(
            {
                item.get("fact_id")
                for item in coverage
                if isinstance(item, dict)
                and item.get("paper_node_id") in target_nodes
                and item.get("disposition") == "fact_bundle_member"
                and item.get("fact_id") in active_release_fact_ids
            }
        )

    def _execute_association_request(
        self,
        request: dict[str, Any],
        *,
        actor: str,
    ) -> dict[str, Any]:
        binding = self._binding()
        if binding is None:
            raise ValueError("Evidence library is not configured")
        self._validate_association_request(request, binding=binding)
        effect_path = self._association_effect_path(request["request_id"])
        if effect_path.exists():
            effect = self._read_json(effect_path)
            self._validate_association_effect(effect, request=request)
            return {
                "status": "associated_as_nontruth_evidence_triad",
                "request_id": request["request_id"],
                "association_id": effect["association_id"],
                "effect_id": effect["effect_id"],
                "effect_path": str(effect_path),
                "idempotent": True,
                "truth_effect": "none",
            }
        receipt = request["paper_evidence_receipt"]
        arguments = [
            "evidence-association-add",
            "--root",
            binding["library_root"],
            "--destination-project-id",
            request["destination_project_id"],
            "--paper-evidence-id",
            receipt["evidence_id"],
            "--fact-evidence-id",
            request["fact_evidence_id"],
            "--actor",
            request["authorization"]["actor"],
            "--reason",
            request["authorization"]["reason"],
            "--request",
            str(self._association_request_path(request["request_id"])),
        ]
        for fact_id in request["associated_fact_ids"]:
            arguments.extend(["--fact-id", fact_id])
        result = self._run_library(binding, *arguments)
        self._run_library(binding, "index", "--root", binding["library_root"])
        library = self._read_json(Path(binding["library_root"]) / "library.json")
        effect_body = {
            "schema_version": 1,
            "contract_revision": EVIDENCE_ASSOCIATION_EFFECT_REVISION,
            "request_id": request["request_id"],
            "request_record_sha256": sha256_json(request),
            "library_id": library["library_id"],
            "association_id": result["association_id"],
            "association_record_sha256": result["record"]["record_sha256"],
            "paper_evidence_id": receipt["evidence_id"],
            "fact_evidence_id": request["fact_evidence_id"],
            "associated_fact_ids": request["associated_fact_ids"],
            "executed_by": actor,
            "fact_evidence_import_preserved": True,
            "cross_project_fact_authority": False,
            "premise_eligible": False,
            "truth_effect": "none",
        }
        effect = {**effect_body, "effect_id": "eae-" + sha256_json(effect_body)}
        self._write_json_once(effect_path, effect)
        return {
            "status": "associated_as_nontruth_evidence_triad",
            "request_id": request["request_id"],
            "association_id": result["association_id"],
            "effect_id": effect["effect_id"],
            "effect_path": str(effect_path),
            "idempotent": False,
            "truth_effect": "none",
        }

    def _plan_fact_import_association_requests(
        self,
        *,
        source_path: Path,
        source_store: Any,
        inventory: dict[str, Any],
        capsule: dict[str, Any],
        capsule_path: Path,
        fact_result: dict[str, Any],
        binding: dict[str, Any],
        actor: str,
        reason: str,
        release_records: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        active_by_release: dict[str, set[str]] = {}
        release_hashes: dict[str, str] = {}
        for item in inventory["active_facts"]:
            active_by_release.setdefault(item["release_id"], set()).add(
                item["fact_id"]
            )
            previous = release_hashes.setdefault(
                item["release_id"], item["release_sha256"]
            )
            if previous != item["release_sha256"]:
                raise ValueError("Fact import release hashes are inconsistent")
        prepared: dict[str, dict[str, Any]] = {}
        pending: list[dict[str, Any]] = []
        exact_ref_count = 0
        unmapped_ref_count = 0
        for release_id in sorted(active_by_release):
            release = release_records.get(release_id)
            if not isinstance(release, dict):
                pending.append(
                    {
                        "status": "pending_missing_exact_source_release",
                        "release_id": release_id,
                        "error": "validated source release is unavailable",
                    }
                )
                continue
            refs = release.get("paper_evidence_refs", [])
            if not isinstance(refs, list) or any(
                not isinstance(ref, dict) for ref in refs
            ):
                pending.append(
                    {
                        "status": "pending_invalid_release_paper_refs",
                        "release_id": release_id,
                        "error": "paper_evidence_refs is not a list of objects",
                    }
                )
                continue
            exact_ref_count += len(refs)
            for ref in refs:
                fact_ids = self._mapped_fact_ids_for_paper_ref(
                    release, ref, active_by_release[release_id]
                )
                if not fact_ids:
                    unmapped_ref_count += 1
                    continue
                try:
                    (
                        sync_request,
                        sync_path,
                        receipt,
                        receipt_path,
                    ) = self._validated_local_paper_receipt(
                        source_store=source_store,
                        ref=ref,
                        binding=binding,
                    )
                    request_body = {
                        "schema_version": 1,
                        "contract_revision": (
                            EVIDENCE_ASSOCIATION_REQUEST_REVISION
                        ),
                        "destination_project_id": self.store.project_id(),
                        "source_project_id": inventory["source_project_id"],
                        "source_root_locator": str(source_path),
                        "source_release_id": release_id,
                        "source_release_sha256": release_hashes[release_id],
                        "paper_evidence_ref": ref,
                        "paper_evidence_ref_sha256": sha256_json(ref),
                        "paper_sync_request": sync_request,
                        "paper_sync_request_file_sha256": sha256_bytes(
                            sync_path.read_bytes()
                        ),
                        "paper_evidence_receipt": receipt,
                        "paper_evidence_receipt_file_sha256": sha256_bytes(
                            receipt_path.read_bytes()
                        ),
                        "fact_evidence_id": fact_result["evidence_id"],
                        "fact_evidence_record_sha256": fact_result["record"][
                            "record_sha256"
                        ],
                        "fact_capsule_id": capsule["capsule_id"],
                        "fact_capsule_sha256": sha256_bytes(
                            capsule_path.read_bytes()
                        ),
                        "associated_fact_ids": fact_ids,
                        "authorization": {"actor": actor, "reason": reason},
                        "association_policy": {
                            "derivation": (
                                "exact_release_paper_evidence_ref_and_local_receipt"
                            ),
                            "inferred_from_title_doi_or_credibility": False,
                        },
                        "cross_project_fact_authority": False,
                        "premise_eligible": False,
                        "truth_effect": "none",
                    }
                    request = {
                        **request_body,
                        "request_id": "eas-" + sha256_json(request_body),
                    }
                    self._validate_association_request(request, binding=binding)
                    prepared[request["request_id"]] = request
                except Exception as exc:
                    pending.append(
                        {
                            "status": "pending_exact_paper_binding_error",
                            "release_id": release_id,
                            "snapshot_id": ref.get("snapshot_id", ""),
                            "error": str(exc),
                        }
                    )
        return {
            "prepared": prepared,
            "pending": pending,
            "exact_paper_evidence_ref_count": exact_ref_count,
            "unmapped_paper_evidence_ref_count": unmapped_ref_count,
        }

    def _sync_fact_import_associations(
        self,
        *,
        source_path: Path,
        source_store: Any,
        inventory: dict[str, Any],
        capsule: dict[str, Any],
        capsule_path: Path,
        fact_result: dict[str, Any],
        binding: dict[str, Any],
        actor: str,
        reason: str,
        release_records: dict[str, dict[str, Any]],
        execution_actor: str | None = None,
    ) -> dict[str, Any]:
        plan = self._plan_fact_import_association_requests(
            source_path=source_path,
            source_store=source_store,
            inventory=inventory,
            capsule=capsule,
            capsule_path=capsule_path,
            fact_result=fact_result,
            binding=binding,
            actor=actor,
            reason=reason,
            release_records=release_records,
        )
        pending = list(plan["pending"])
        durable: dict[str, dict[str, Any]] = {}
        for request_id, request in sorted(plan["prepared"].items()):
            try:
                request_path = self._association_request_path(request_id)
                self._write_json_once(request_path, request)
                durable[request_id] = request
            except Exception as exc:
                pending.append(
                    {
                        "status": "pending_association_request_write_error",
                        "request_id": request_id,
                        "outbox_path": str(
                            self._association_request_path(request_id)
                        ),
                        "error": str(exc),
                    }
                )
        completed: list[dict[str, Any]] = []
        for request_id in sorted(durable):
            try:
                completed.append(
                    self._execute_association_request(
                        durable[request_id], actor=execution_actor or actor
                    )
                )
            except Exception as exc:
                pending.append(
                    {
                        "status": "pending_library_association_error",
                        "request_id": request_id,
                        "outbox_path": str(
                            self._association_request_path(request_id)
                        ),
                        "error": str(exc),
                    }
                )
        exact_ref_count = plan["exact_paper_evidence_ref_count"]
        unmapped_ref_count = plan["unmapped_paper_evidence_ref_count"]
        if exact_ref_count == 0:
            status = "not_applicable_no_exact_paper_evidence_refs"
        elif pending and completed:
            status = "partially_associated_pending_retry"
        elif pending:
            status = "pending_retry"
        elif completed:
            status = "associated"
        else:
            status = "not_applicable_no_exact_fact_mapping"
        return {
            "schema_version": 1,
            "contract_revision": EVIDENCE_ASSOCIATION_REQUEST_REVISION,
            "status": status,
            "exact_paper_evidence_ref_count": exact_ref_count,
            "unmapped_paper_evidence_ref_count": unmapped_ref_count,
            "request_ids": sorted(durable),
            "completed": completed,
            "pending": pending,
            "planning_complete": (
                not plan["pending"]
                and len(durable) == len(plan["prepared"])
            ),
            "fact_evidence_import_preserved": True,
            "cross_project_fact_authority": False,
            "premise_eligible": False,
            "truth_effect": "none",
        }

    def _execute_association_planning_attempt(
        self,
        attempt: dict[str, Any],
        *,
        execution_actor: str,
    ) -> dict[str, Any]:
        binding = self._binding()
        if binding is None:
            raise ValueError("Evidence library is not configured")
        inputs = self._validated_association_planning_inputs(
            attempt, binding=binding
        )
        sync = self._sync_fact_import_associations(
            **inputs,
            binding=binding,
            actor=attempt["authorization"]["actor"],
            reason=attempt["authorization"]["reason"],
            execution_actor=execution_actor,
        )
        return {
            **sync,
            "planning_attempt_id": attempt["attempt_id"],
            "planning_attempt_path": str(
                self._association_planning_path(attempt["attempt_id"])
            ),
        }

    def association_planning_status(
        self,
        *,
        attempt_id: str = "",
    ) -> dict[str, Any]:
        if attempt_id:
            if not attempt_id.startswith("eap-") or "/" in attempt_id:
                raise ValueError(
                    "Evidence association planning attempt id is invalid"
                )
            paths = [self._association_planning_path(attempt_id)]
        else:
            paths = sorted(self.association_planning_dir.glob("eap-*.json"))
        try:
            binding = self._binding()
            binding_error = ""
        except Exception as exc:
            binding = None
            binding_error = str(exc)
        rows: list[dict[str, Any]] = []
        for path in paths:
            if not path.exists():
                rows.append(
                    {
                        "planning_attempt_id": path.stem,
                        "status": "missing",
                        "fact_evidence_import_preserved": True,
                        "cross_project_fact_authority": False,
                        "premise_eligible": False,
                        "truth_effect": "none",
                    }
                )
                continue
            try:
                attempt = self._read_json(path)
                self._validate_association_planning_attempt(attempt)
                if path.stem != attempt["attempt_id"]:
                    raise ValueError(
                        "association planning attempt filename mismatch"
                    )
            except Exception as exc:
                rows.append(
                    {
                        "planning_attempt_id": path.stem,
                        "status": "invalid_tampered",
                        "error": str(exc),
                        "fact_evidence_import_preserved": True,
                        "cross_project_fact_authority": False,
                        "premise_eligible": False,
                        "truth_effect": "none",
                    }
                )
                continue
            row_base = {
                "planning_attempt_id": attempt["attempt_id"],
                "fact_capsule_id": attempt["fact_capsule_id"],
                "fact_evidence_id": attempt["fact_evidence_id"],
                "fact_evidence_import_preserved": True,
                "cross_project_fact_authority": False,
                "premise_eligible": False,
                "truth_effect": "none",
            }
            if binding is None:
                rows.append(
                    {
                        **row_base,
                        "status": "pending_replan",
                        "expected_request_ids": [],
                        "error": binding_error or "Evidence library is not configured",
                    }
                )
                continue
            try:
                inputs = self._validated_association_planning_inputs(
                    attempt, binding=binding
                )
            except Exception as exc:
                rows.append(
                    {
                        **row_base,
                        "status": "invalid_tampered",
                        "expected_request_ids": [],
                        "error": str(exc),
                    }
                )
                continue
            plan = self._plan_fact_import_association_requests(
                **inputs,
                binding=binding,
                actor=attempt["authorization"]["actor"],
                reason=attempt["authorization"]["reason"],
            )
            expected = plan["prepared"]
            expected_request_ids = sorted(expected)
            plan_base = {
                **row_base,
                "expected_request_ids": expected_request_ids,
                "exact_paper_evidence_ref_count": plan[
                    "exact_paper_evidence_ref_count"
                ],
                "unmapped_paper_evidence_ref_count": plan[
                    "unmapped_paper_evidence_ref_count"
                ],
            }
            if plan["pending"]:
                rows.append(
                    {
                        **plan_base,
                        "status": "pending_replan",
                        "pending": plan["pending"],
                    }
                )
                continue
            if plan["exact_paper_evidence_ref_count"] == 0:
                rows.append(
                    {
                        **plan_base,
                        "status": "not_applicable_no_exact_paper_evidence_refs",
                    }
                )
                continue
            if not expected:
                rows.append(
                    {
                        **plan_base,
                        "status": "not_applicable_no_exact_fact_mapping",
                    }
                )
                continue
            request_states: list[dict[str, Any]] = []
            for request_id, expected_request in sorted(expected.items()):
                request_path = self._association_request_path(request_id)
                if not request_path.exists():
                    request_states.append(
                        {"request_id": request_id, "status": "missing"}
                    )
                    continue
                try:
                    request = self._read_json(request_path)
                    self._validate_association_request(request, binding=binding)
                    if request != expected_request or request_path.stem != request_id:
                        raise ValueError(
                            "association request does not match exact planning attempt"
                        )
                    effect_path = self._association_effect_path(request_id)
                    if effect_path.exists():
                        effect = self._read_json(effect_path)
                        self._validate_association_effect(effect, request=request)
                        request_states.append(
                            {"request_id": request_id, "status": "associated"}
                        )
                    else:
                        request_states.append(
                            {"request_id": request_id, "status": "pending"}
                        )
                except Exception as exc:
                    request_states.append(
                        {
                            "request_id": request_id,
                            "status": "invalid_tampered",
                            "error": str(exc),
                        }
                    )
            if any(
                item["status"] == "invalid_tampered"
                for item in request_states
            ):
                status = "invalid_tampered"
            elif any(item["status"] == "missing" for item in request_states):
                status = "pending_replan"
            elif any(item["status"] == "pending" for item in request_states):
                status = "planned_pending_execution"
            else:
                status = "associated"
            rows.append(
                {
                    **plan_base,
                    "status": status,
                    "requests": request_states,
                }
            )
        states = (
            "associated",
            "pending_replan",
            "planned_pending_execution",
            "not_applicable_no_exact_paper_evidence_refs",
            "not_applicable_no_exact_fact_mapping",
            "invalid_tampered",
            "missing",
        )
        return {
            "schema_version": 1,
            "contract_revision": EVIDENCE_ASSOCIATION_PLANNING_REVISION,
            "attempt_id": attempt_id,
            "counts": {
                state: sum(row["status"] == state for row in rows)
                for state in states
            },
            "attempts": rows,
            "fact_evidence_import_preserved": True,
            "cross_project_fact_authority": False,
            "premise_eligible": False,
            "truth_effect": "none",
        }

    def import_fact_graph(
        self,
        *,
        source_root: str,
        inventory: dict[str, Any],
        actor: str,
        reason: str,
    ) -> dict[str, Any]:
        source_audit = inventory.get("source_audit")
        if (
            not isinstance(source_audit, dict)
            or source_audit.get("contract_revision")
            != "chalxius-v5-fact-evidence-audit-1"
            or source_audit.get("scope") != "active_v5_fact_authority_only"
            or source_audit.get("current_ok") is not True
            or source_audit.get("history_clean") is not True
            or source_audit.get("errors") != []
        ):
            raise ValueError(
                "Fact Evidence import requires a clean scoped V5 authority audit"
            )
        expected_fact_ids = sorted(
            item["fact_id"] for item in inventory.get("active_facts", [])
        )
        if source_audit.get("active_fact_ids") != expected_fact_ids:
            raise ValueError("Fact Evidence authority audit Fact set drifted")
        binding = self._binding()
        if binding is None:
            raise ValueError("Evidence library is not configured")
        source_path = Path(source_root).expanduser().resolve()
        source_store = self.store.__class__(source_path)
        lifecycle = source_store.v5_lifecycle()
        objects: dict[tuple[str, str], dict[str, str]] = {}
        for item in inventory["active_facts"]:
            fact_id = item["fact_id"]
            fact_path = source_store.active_fact_path(fact_id)
            release_path = lifecycle.candidate_releases_dir / f"{item['release_id']}.json"
            decision_path = lifecycle.certification_decisions_dir / f"{item['decision_id']}.json"
            marker_path = lifecycle.admissions_dir / item["release_id"] / "ACCEPTED.json"
            interface = source_store.statement_interface(fact_id, materialize=False)
            raw_objects = [
                ("fact", fact_id, fact_path.read_bytes()),
                ("release", item["release_id"], release_path.read_bytes()),
                ("decision", item["decision_id"], decision_path.read_bytes()),
                ("admission", item["acceptance_id"], marker_path.read_bytes()),
                ("interface", fact_id, canonical_json_bytes(interface) + b"\n"),
            ]
            for role, object_id, raw in raw_objects:
                encoded = self._encoded_object(role, object_id, raw)
                key = (role, object_id)
                if key in objects and objects[key] != encoded:
                    raise ValueError("Fact Evidence object identity has conflicting bytes")
                objects[key] = encoded
        capsule_body = {
            "schema_version": 1,
            "contract_revision": FACT_CAPSULE_REVISION,
            "source_project_id": inventory["source_project_id"],
            "source_root_locator": str(source_path),
            "source_audit": inventory["source_audit"],
            "active_facts": inventory["active_facts"],
            "revoked_fact_ids": inventory["revoked_fact_ids"],
            "objects": [objects[key] for key in sorted(objects)],
            "runtime": self._runtime(),
            "truth_effect": "none",
            "premise_eligible": False,
        }
        capsule = {
            **capsule_body,
            "capsule_id": "efc-" + sha256_json(capsule_body),
        }
        capsule_path = self.fact_capsules_dir / f"{capsule['capsule_id']}.json"
        self._write_json_once(capsule_path, capsule)
        result = self._run_library(
            binding,
            "evidence-fact-add",
            "--root",
            binding["library_root"],
            "--capsule",
            str(capsule_path),
            "--actor",
            actor,
            "--reason",
            reason,
        )
        self._run_library(binding, "index", "--root", binding["library_root"])
        planning_attempt = self._persist_association_planning_attempt(
            source_path=source_path,
            inventory=inventory,
            capsule=capsule,
            capsule_path=capsule_path,
            fact_result=result,
            actor=actor,
            reason=reason,
        )
        planning_path = self._association_planning_path(
            planning_attempt["attempt_id"]
        )
        try:
            association_sync = self._execute_association_planning_attempt(
                planning_attempt,
                execution_actor=actor,
            )
        except Exception as exc:
            association_sync = {
                "schema_version": 1,
                "contract_revision": EVIDENCE_ASSOCIATION_REQUEST_REVISION,
                "status": "pending_retry",
                "exact_paper_evidence_ref_count": 0,
                "unmapped_paper_evidence_ref_count": 0,
                "request_ids": [],
                "completed": [],
                "pending": [
                    {
                        "status": "pending_association_planning_error",
                        "error": str(exc),
                    }
                ],
                "planning_complete": False,
                "planning_attempt_id": planning_attempt["attempt_id"],
                "planning_attempt_path": str(planning_path),
                "fact_evidence_import_preserved": True,
                "cross_project_fact_authority": False,
                "premise_eligible": False,
                "truth_effect": "none",
            }
        return {
            "status": "imported_as_evidence",
            "evidence_id": result["evidence_id"],
            "capsule_id": capsule["capsule_id"],
            "capsule_path": str(capsule_path),
            "planning_attempt_id": planning_attempt["attempt_id"],
            "planning_attempt_path": str(planning_path),
            "source_project_id": inventory["source_project_id"],
            "source_audit_scope": source_audit["scope"],
            "association_sync": association_sync,
            "cross_project_fact_authority": False,
            "truth_effect": "none",
            "premise_eligible": False,
        }

    def association_status(self, *, request_id: str = "") -> dict[str, Any]:
        if request_id:
            if not request_id.startswith("eas-") or "/" in request_id:
                raise ValueError("Evidence association request id is invalid")
            paths = [self._association_request_path(request_id)]
        else:
            paths = sorted(self.association_outbox_dir.glob("eas-*.json"))
        rows: list[dict[str, Any]] = []
        for path in paths:
            if not path.exists():
                rows.append(
                    {
                        "request_id": path.stem,
                        "status": "missing",
                        "truth_effect": "none",
                    }
                )
                continue
            try:
                request = self._read_json(path)
                self._validate_association_request(request)
                if path.stem != request["request_id"]:
                    raise ValueError("association request filename mismatch")
                effect_path = self._association_effect_path(request["request_id"])
                if effect_path.exists():
                    effect = self._read_json(effect_path)
                    self._validate_association_effect(effect, request=request)
                    row = {
                        "request_id": request["request_id"],
                        "status": "associated",
                        "association_id": effect["association_id"],
                        "effect_id": effect["effect_id"],
                        "paper_evidence_id": effect["paper_evidence_id"],
                        "fact_evidence_id": effect["fact_evidence_id"],
                        "associated_fact_ids": effect["associated_fact_ids"],
                        "truth_effect": "none",
                    }
                else:
                    row = {
                        "request_id": request["request_id"],
                        "status": "pending",
                        "paper_evidence_id": request["paper_evidence_receipt"][
                            "evidence_id"
                        ],
                        "fact_evidence_id": request["fact_evidence_id"],
                        "associated_fact_ids": request["associated_fact_ids"],
                        "truth_effect": "none",
                    }
            except Exception as exc:
                row = {
                    "request_id": path.stem,
                    "status": "invalid_tampered",
                    "error": str(exc),
                    "truth_effect": "none",
                }
            rows.append(row)
        counts = {
            state: sum(row["status"] == state for row in rows)
            for state in ("associated", "pending", "invalid_tampered", "missing")
        }
        return {
            "schema_version": 1,
            "contract_revision": EVIDENCE_ASSOCIATION_REQUEST_REVISION,
            "request_id": request_id,
            "counts": counts,
            "requests": rows,
            "fact_evidence_import_preserved": True,
            "cross_project_fact_authority": False,
            "premise_eligible": False,
            "truth_effect": "none",
        }

    def retry_associations(
        self,
        *,
        request_id: str = "",
        actor: str,
    ) -> dict[str, Any]:
        planning_results: list[dict[str, Any]] = []
        if not request_id:
            planning_before = self.association_planning_status()
            for row in planning_before["attempts"]:
                if row["status"] == "pending_replan":
                    try:
                        attempt = self._read_json(
                            self._association_planning_path(
                                row["planning_attempt_id"]
                            )
                        )
                        planning_results.append(
                            self._execute_association_planning_attempt(
                                attempt,
                                execution_actor=actor,
                            )
                        )
                    except Exception as exc:
                        planning_results.append(
                            {
                                "planning_attempt_id": row[
                                    "planning_attempt_id"
                                ],
                                "status": "pending_error",
                                "error": str(exc),
                                "fact_evidence_import_preserved": True,
                                "cross_project_fact_authority": False,
                                "premise_eligible": False,
                                "truth_effect": "none",
                            }
                        )
                elif row["status"] in {
                    "associated",
                    "planned_pending_execution",
                    "not_applicable_no_exact_paper_evidence_refs",
                    "not_applicable_no_exact_fact_mapping",
                }:
                    planning_results.append({**row, "idempotent": True})
                else:
                    planning_results.append(row)
        before = self.association_status(request_id=request_id)
        results: list[dict[str, Any]] = []
        for row in before["requests"]:
            if row["status"] == "associated":
                results.append({**row, "idempotent": True})
                continue
            if row["status"] != "pending":
                results.append(row)
                continue
            path = self._association_request_path(row["request_id"])
            try:
                request = self._read_json(path)
                results.append(
                    self._execute_association_request(request, actor=actor)
                )
            except Exception as exc:
                results.append(
                    {
                        "request_id": row["request_id"],
                        "status": "pending_error",
                        "error": str(exc),
                        "fact_evidence_import_preserved": True,
                        "truth_effect": "none",
                    }
                )
        after = self.association_status(request_id=request_id)
        planning_after = self.association_planning_status()
        association_clean = not any(
            after["counts"][state]
            for state in ("pending", "invalid_tampered", "missing")
        )
        planning_clean = not any(
            planning_after["counts"][state]
            for state in (
                "pending_replan",
                "planned_pending_execution",
                "invalid_tampered",
                "missing",
            )
        )
        complete = (
            association_clean
            and bool(after["counts"]["associated"])
            and (bool(request_id) or planning_clean)
        )
        return {
            "schema_version": 1,
            "contract_revision": EVIDENCE_ASSOCIATION_REQUEST_REVISION,
            "request_id": request_id,
            "planning_results": planning_results,
            "results": results,
            "status": "associated" if complete else "pending",
            "association_planning_status": planning_after,
            "association_status": after,
            "fact_evidence_import_preserved": True,
            "cross_project_fact_authority": False,
            "premise_eligible": False,
            "truth_effect": "none",
        }

    def prepare_bridge(
        self,
        *,
        selection_path: str,
        actor: str,
        reason: str,
        output_path: str,
    ) -> dict[str, Any]:
        binding = self._binding()
        if binding is None:
            raise ValueError("Evidence library is not configured")
        arguments = [
            "bridge-prepare",
            "--root",
            binding["library_root"],
            "--destination-project-id",
            self.store.project_id(),
            "--selection",
            str(Path(selection_path).expanduser().resolve()),
            "--actor",
            actor,
            "--reason",
            reason,
        ]
        if output_path:
            arguments.extend(["--output", str(Path(output_path).expanduser().resolve())])
        return self._run_library(binding, *arguments)

    def bridge_check(self, bridge_id: str) -> dict[str, Any]:
        binding = self._binding()
        if binding is None:
            raise ValueError("Evidence library is not configured")
        return self._run_library(
            binding,
            "bridge-check",
            "--root",
            binding["library_root"],
            "--bridge-id",
            bridge_id,
        )

    def query(
        self,
        *,
        query: str,
        limit: int,
        include_inactive: bool,
        associations_only: bool = False,
    ) -> dict[str, Any]:
        binding = self._binding()
        if binding is None:
            raise ValueError("Evidence library is not configured")
        arguments = [
            "evidence-query",
            "--root",
            binding["library_root"],
            "--query",
            query,
            "--limit",
            str(limit),
        ]
        if include_inactive:
            arguments.append("--include-inactive")
        if associations_only:
            arguments.append("--associations-only")
        return self._run_library(binding, *arguments)

    def validate_bridge_artifact(
        self,
        *,
        path: Path,
        expected_sha256: str,
        expected_bridge_id: str,
        expected_record_sha256: str,
        require_current: bool,
    ) -> dict[str, Any]:
        if path.is_symlink() or not path.is_file():
            raise ValueError("Evidence bridge capsule is missing or unsafe")
        raw = path.read_bytes()
        if sha256_bytes(raw) != expected_sha256:
            raise ValueError("Evidence bridge capsule artifact hash drifted")
        bridge = self._read_json(path)
        if bridge.get("contract_revision") != BRIDGE_CAPSULE_REVISION:
            raise ValueError("Evidence bridge capsule contract mismatch")
        payload = {
            key: value
            for key, value in bridge.items()
            if key not in {"object_id", "record_sha256"}
        }
        object_id = "evb-" + sha256_json(payload)
        record_core = {**payload, "object_id": object_id}
        record_sha256 = sha256_json(record_core)
        if (
            bridge.get("object_id") != object_id
            or bridge.get("record_sha256") != record_sha256
            or object_id != expected_bridge_id
            or record_sha256 != expected_record_sha256
            or bridge.get("object_type") != "evidence_bridge_capsule"
            or bridge.get("destination_project_id") != self.store.project_id()
            or bridge.get("bridge_status") != "prepared_nontruth"
            or bridge.get("requires_destination_candidate_release") is not True
            or bridge.get("requires_fresh_verifier") is not True
            or bridge.get("requires_fact_gateway") is not True
            or bridge.get("premise_eligible") is not False
            or bridge.get("truth_effect") != "none"
        ):
            raise ValueError("Evidence bridge capsule identity or authority boundary mismatch")
        selection = bridge.get("selection")
        items = selection.get("items") if isinstance(selection, dict) else None
        if not isinstance(items, list) or not items:
            raise ValueError("Evidence bridge capsule selection is empty")
        evidence_ids = sorted(
            item.get("evidence_id", "") for item in items if isinstance(item, dict)
        )
        if (
            len(evidence_ids) != len(items)
            or any(not item for item in evidence_ids)
            or len(evidence_ids) != len(set(evidence_ids))
        ):
            raise ValueError("Evidence bridge capsule Evidence ids are invalid")
        if require_current:
            checked = self.bridge_check(object_id)
            if (
                checked.get("current") is not True
                or checked.get("bridge_record_sha256") != record_sha256
                or checked.get("destination_project_id") != self.store.project_id()
            ):
                raise ValueError("Evidence bridge is stale or targets another project")
        return {
            "bridge_id": object_id,
            "bridge_record_sha256": record_sha256,
            "bridge_artifact_sha256": expected_sha256,
            "library_id": bridge.get("library_id"),
            "evidence_ids": evidence_ids,
        }

    def mark(
        self,
        *,
        evidence_id: str,
        status: str,
        actor: str,
        reason: str,
        replacement_evidence_ids: list[str],
        supersedes_disposition_ids: list[str],
        artifact: str,
    ) -> dict[str, Any]:
        binding = self._binding()
        if binding is None:
            raise ValueError("Evidence library is not configured")
        arguments = [
            "evidence-disposition-add",
            "--root",
            binding["library_root"],
            "--evidence-id",
            evidence_id,
            "--status",
            status,
            "--actor",
            actor,
            "--reason",
            reason,
        ]
        for replacement in replacement_evidence_ids:
            arguments.extend(["--replacement-evidence-id", replacement])
        for predecessor in supersedes_disposition_ids:
            arguments.extend(["--supersedes-disposition-id", predecessor])
        if artifact:
            arguments.extend(["--artifact", str(Path(artifact).expanduser().resolve())])
        result = self._run_library(binding, *arguments)
        self._run_library(binding, "index", "--root", binding["library_root"])
        return {**result, "local_impact": self.impact_report(evidence_id=evidence_id)}

    def impact_report(self, *, evidence_id: str = "") -> dict[str, Any]:
        releases: list[dict[str, Any]] = []
        lifecycle = self.store.v5_lifecycle()
        if lifecycle.candidate_releases_dir.exists():
            for path in sorted(lifecycle.candidate_releases_dir.glob("release-*.json")):
                if path.is_symlink() or not path.is_file():
                    continue
                release = self._read_json(path)
                refs = release.get("evidence_bridge_refs", [])
                if not isinstance(refs, list):
                    continue
                matching = [
                    ref
                    for ref in refs
                    if isinstance(ref, dict)
                    and (not evidence_id or evidence_id in ref.get("evidence_ids", []))
                ]
                if not matching:
                    continue
                admission = lifecycle.admissions_dir / path.stem / "ACCEPTED.json"
                bridge_states: list[dict[str, Any]] = []
                for ref in matching:
                    try:
                        checked = self.bridge_check(ref["bridge_id"])
                        bridge_states.append(
                            {"bridge_id": ref["bridge_id"], "current": checked["current"]}
                        )
                    except Exception as exc:
                        bridge_states.append(
                            {
                                "bridge_id": ref.get("bridge_id", ""),
                                "current": False,
                                "error": str(exc),
                            }
                        )
                releases.append(
                    {
                        "release_id": path.stem,
                        "fact_ids": release.get("fact_ids", []),
                        "admitted": admission.is_file() and not admission.is_symlink(),
                        "bridge_states": bridge_states,
                    }
                )
        return {
            "schema_version": 1,
            "contract_revision": "chalxius-evidence-impact-report-1",
            "project_id": self.store.project_id(),
            "evidence_id": evidence_id,
            "affected_releases": releases,
            "admitted_fact_ids_requiring_operator_review": sorted(
                {
                    fact_id
                    for release in releases
                    if release["admitted"]
                    for fact_id in release["fact_ids"]
                }
            ),
            "automatic_fact_revocation": False,
            "truth_effect": "none",
        }

    def status(self) -> dict[str, Any]:
        binding_error = ""
        try:
            binding = self._binding()
        except Exception as exc:
            binding = None
            binding_error = str(exc)
        outbox = sorted(path.stem for path in self.outbox_dir.glob("pes-*.json"))
        receipts = sorted(path.stem for path in self.receipts_dir.glob("*.json"))
        synced_requests = {
            self._read_json(path)["request_id"]
            for path in self.receipts_dir.glob("*.json")
        }
        planning = self.association_planning_status()
        associations = self.association_status()
        return {
            "schema_version": 1,
            "contract_revision": EVIDENCE_BINDING_REVISION,
            "configured": binding is not None,
            "binding": binding or {},
            "binding_error": binding_error,
            "outbox_count": len(outbox),
            "synced_snapshot_count": len(receipts),
            "pending_request_ids": sorted(set(outbox).difference(synced_requests)),
            "association_planning_attempt_count": sum(
                planning["counts"].values()
            ),
            "pending_association_planning_attempt_ids": sorted(
                row["planning_attempt_id"]
                for row in planning["attempts"]
                if row["status"]
                in {"pending_replan", "planned_pending_execution"}
            ),
            "invalid_association_planning_attempt_ids": sorted(
                row["planning_attempt_id"]
                for row in planning["attempts"]
                if row["status"] in {"invalid_tampered", "missing"}
            ),
            "association_outbox_count": sum(associations["counts"].values()),
            "association_effect_count": associations["counts"]["associated"],
            "pending_association_request_ids": sorted(
                row["request_id"]
                for row in associations["requests"]
                if row["status"] == "pending"
            ),
            "invalid_association_request_ids": sorted(
                row["request_id"]
                for row in associations["requests"]
                if row["status"] in {"invalid_tampered", "missing"}
            ),
            "association_planning": planning,
            "associations": associations,
            "paper_auto_sync": "reviewed_freeze_default",
            "fact_graph_import": "explicit_user_only",
            "fact_graph_paper_association": (
                "automatic_from_exact_release_refs_and_local_receipts_only"
            ),
            "truth_effect": "none",
        }

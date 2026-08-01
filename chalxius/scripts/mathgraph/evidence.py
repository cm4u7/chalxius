from __future__ import annotations

import base64
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
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


class EvidencePlane:
    """Project-local adapter to the cross-project, nontruth Evidence library."""

    def __init__(self, store: Any) -> None:
        self.store = store
        self.project_root = Path(store.root).resolve()
        self.root = self.project_root / "evidence"
        self.outbox_dir = self.root / "outbox" / "by-id"
        self.receipts_dir = self.root / "receipts" / "by-snapshot"
        self.fact_capsules_dir = self.root / "fact-capsules" / "by-id"
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
        return {
            "status": "imported_as_evidence",
            "evidence_id": result["evidence_id"],
            "capsule_id": capsule["capsule_id"],
            "capsule_path": str(capsule_path),
            "source_project_id": inventory["source_project_id"],
            "source_audit_scope": source_audit["scope"],
            "cross_project_fact_authority": False,
            "truth_effect": "none",
            "premise_eligible": False,
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
        return {
            "schema_version": 1,
            "contract_revision": EVIDENCE_BINDING_REVISION,
            "configured": binding is not None,
            "binding": binding or {},
            "binding_error": binding_error,
            "outbox_count": len(outbox),
            "synced_snapshot_count": len(receipts),
            "pending_request_ids": sorted(set(outbox).difference(synced_requests)),
            "paper_auto_sync": "reviewed_freeze_default",
            "fact_graph_import": "explicit_user_only",
            "truth_effect": "none",
        }

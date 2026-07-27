from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable

from .contracts import (
    BUNDLE_ID_RE,
    FACT_ID_RE,
    POLICY_REVISION_V4,
    SHA256_RE,
    canonical_json_bytes,
    contained_path,
    require_exact_keys,
    require_string,
    sha256_bytes,
    sha256_json,
    validate_bundle_id,
    validate_fact_id,
)
from .interfaces import statement_only_packet_section, validate_statement_interface


FINDING_CLASSES = {
    "mathematical",
    "typing",
    "scope",
    "source_mismatch",
    "source_access",
    "reproducibility",
    "evidence_access",
    "protocol",
}
HARD_FINDING_CLASSES = {
    "mathematical",
    "typing",
    "scope",
    "source_mismatch",
}
FINDING_SEVERITIES = {"critical_error", "gap"}
DISPOSITIONS = {
    "resolved_by_bundle_expansion",
    "resolved_by_new_submission",
    "still_open",
}
_INHERITED_CHALK_FIXTURE_AUTHORITY = object()


def validate_review_v4(payload: dict[str, Any]) -> dict[str, Any]:
    require_exact_keys(
        payload,
        required={
            "schema_version",
            "policy_revision",
            "fact_id",
            "submission_sha256",
            "bundle_sha256",
            "verdict",
            "findings",
            "prior_review_dispositions",
            "reviewer",
            "host_attestation",
        },
        optional={"review_id", "record_sha256", "reviewed_at"},
        label="v4 review",
    )
    if payload.get("schema_version") != 4:
        raise ValueError("v4 review schema_version must be 4")
    if payload.get("policy_revision") != POLICY_REVISION_V4:
        raise ValueError("v4 review policy_revision mismatch")
    validate_fact_id(require_string(payload, "fact_id"))
    for key in ("submission_sha256", "bundle_sha256"):
        if SHA256_RE.fullmatch(require_string(payload, key)) is None:
            raise ValueError(f"v4 review {key} is invalid")
    verdict = require_string(payload, "verdict")
    if verdict not in {"correct", "reject"}:
        raise ValueError("v4 review verdict must be correct or reject")
    findings = payload.get("findings")
    if not isinstance(findings, list) or any(not isinstance(item, dict) for item in findings):
        raise ValueError("v4 review findings must be a list of objects")
    finding_ids: set[str] = set()
    for index, finding in enumerate(findings, 1):
        require_exact_keys(
            finding,
            required={"id", "severity", "class", "description", "repair_hint"},
            label=f"v4 review findings[{index}]",
        )
        finding_id = require_string(finding, "id")
        if finding_id in finding_ids:
            raise ValueError("v4 review finding ids must be unique")
        finding_ids.add(finding_id)
        if require_string(finding, "severity") not in FINDING_SEVERITIES:
            raise ValueError("v4 review finding severity is invalid")
        if require_string(finding, "class") not in FINDING_CLASSES:
            raise ValueError("v4 review finding class is invalid")
        require_string(finding, "description")
        require_string(finding, "repair_hint", allow_empty=True)
    if verdict == "correct" and findings:
        raise ValueError("correct v4 review requires findings=[]")
    if verdict == "reject" and not findings:
        raise ValueError("rejecting v4 review requires at least one finding")
    dispositions = payload.get("prior_review_dispositions")
    if not isinstance(dispositions, list) or any(
        not isinstance(item, dict) for item in dispositions
    ):
        raise ValueError("prior_review_dispositions must be a list of objects")
    disposition_ids: set[str] = set()
    for index, disposition in enumerate(dispositions, 1):
        require_exact_keys(
            disposition,
            required={"prior_review_id", "finding_id", "disposition", "explanation"},
            label=f"prior_review_dispositions[{index}]",
        )
        prior_review_id = require_string(disposition, "prior_review_id")
        if SHA256_RE.fullmatch(prior_review_id) is None:
            raise ValueError("prior review id is invalid")
        finding_id = require_string(disposition, "finding_id")
        key = f"{prior_review_id}:{finding_id}"
        if key in disposition_ids:
            raise ValueError("duplicate prior review finding disposition")
        disposition_ids.add(key)
        if require_string(disposition, "disposition") not in DISPOSITIONS:
            raise ValueError("prior review disposition is invalid")
        require_string(disposition, "explanation")
    require_string(payload, "reviewer")
    attestation = payload.get("host_attestation")
    if not isinstance(attestation, dict):
        raise ValueError("v4 review host_attestation must be an object")
    require_exact_keys(
        attestation,
        required={
            "host",
            "agent_id",
            "isolation",
            "fork_turns",
            "allowed_bundle_sha256",
        },
        label="v4 review host_attestation",
    )
    for key in ("host", "agent_id", "isolation", "fork_turns"):
        require_string(attestation, key)
    if attestation["isolation"] != "fresh_context" or attestation["fork_turns"] != "none":
        raise ValueError("v4 review must attest a fresh fork_turns=none context")
    if attestation["allowed_bundle_sha256"] != payload["bundle_sha256"]:
        raise ValueError("v4 review attestation bundle hash mismatch")
    semantic = {
        key: payload[key]
        for key in (
            "schema_version",
            "policy_revision",
            "fact_id",
            "submission_sha256",
            "bundle_sha256",
            "verdict",
            "findings",
            "prior_review_dispositions",
            "reviewer",
            "host_attestation",
        )
    }
    if "review_id" in payload and payload["review_id"] != sha256_json(semantic):
        raise ValueError("v4 review id/hash mismatch")
    if "record_sha256" in payload:
        if "reviewed_at" not in payload:
            raise ValueError("stored v4 review record lacks reviewed_at")
        expected = sha256_json({**semantic, "reviewed_at": payload["reviewed_at"]})
        if payload["record_sha256"] != expected:
            raise ValueError("v4 review record hash mismatch")
    return payload


class VerificationBundleStore:
    def __init__(
        self,
        project_root: Path | str,
        *,
        creation_authority: object | None = None,
        _fixture_authority: object | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.root = self.project_root / "verification_queue" / "bundles"
        self.by_hash_dir = self.root / "by-hash"
        self.by_fact_dir = self.root / "by-fact"
        self._creation_authority = creation_authority
        self._inherited_chalk_fixture = (
            _fixture_authority is _INHERITED_CHALK_FIXTURE_AUTHORITY
        )

    @classmethod
    def _for_inherited_chalk_fixture(
        cls,
        project_root: Path | str,
    ) -> "VerificationBundleStore":
        return cls(
            project_root,
            _fixture_authority=_INHERITED_CHALK_FIXTURE_AUTHORITY,
        )

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"expected one JSON object in {path}")
        return payload

    @staticmethod
    def _write_once(path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            fd = os.open(path, flags, 0o600)
        except FileExistsError:
            if not path.is_file() or path.is_symlink() or path.read_bytes() != payload:
                raise ValueError(f"immutable verification bundle collision at {path}")
            return
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

    @staticmethod
    def _append(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def initialize(self) -> None:
        self.by_hash_dir.mkdir(parents=True, exist_ok=True)
        self.by_fact_dir.mkdir(parents=True, exist_ok=True)

    def _ensure_fact_index_entry(
        self,
        *,
        fact_id: str,
        entry: dict[str, Any],
    ) -> None:
        path = self.by_fact_dir / f"{fact_id}.jsonl"
        existing: list[dict[str, Any]] = []
        if path.exists():
            for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1
            ):
                if not line.strip():
                    continue
                payload = json.loads(line)
                if not isinstance(payload, dict):
                    raise ValueError(
                        f"verification bundle index has non-object line {number}"
                    )
                existing.append(payload)
        matches = [
            item
            for item in existing
            if item.get("bundle_id") == entry["bundle_id"]
        ]
        if matches:
            if len(matches) != 1 or matches[0] != entry:
                raise ValueError("verification bundle index collision")
            return
        self._append(path, entry)

    @staticmethod
    def _artifact_manifest(
        submission: dict[str, Any],
    ) -> dict[tuple[str, str], dict[str, str]]:
        result: dict[tuple[str, str], dict[str, str]] = {}
        for evidence in submission.get("computational_evidence", []):
            key = str(evidence.get("key", ""))
            for ref in evidence.get("artifact_refs", []):
                role = str(ref.get("role", ""))
                result[(key, role)] = {
                    "key": key,
                    "role": role,
                    "path": str(ref.get("path", "")),
                    "sha256": str(ref.get("sha256", "")),
                }
        return result

    @staticmethod
    def _packet(
        *,
        submission: dict[str, Any],
        predecessor_statements: dict[str, str],
        interfaces: dict[str, dict[str, Any]],
    ) -> str:
        lines = [
            "# MathGraph v4 verification bundle",
            "",
            f"Fact ID: `{submission['fact_id']}`",
            f"Submission SHA-256: `{submission['submission_sha256']}`",
            "",
            "The verifier may use only this packet, the included statement interfaces,",
            "the explicitly authorized artifacts, and exact primary-source locators named",
            "in the submission. No project CLI or exploration state is authorized.",
            "",
            "## Submitted statement",
            "",
            submission["statement"],
            "",
            "## Submitted proof",
            "",
            submission["proof"],
            "",
        ]
        for fact_id in submission.get("predecessors", []):
            lines.append(
                statement_only_packet_section(
                    fact_id=fact_id,
                    statement=predecessor_statements[fact_id],
                    interface=interfaces[fact_id],
                )
            )
        if submission.get("external_refs"):
            lines.extend(
                [
                    "## External-source evidence",
                    "",
                    "```json",
                    json.dumps(
                        submission["external_refs"],
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    ),
                    "```",
                    "",
                ]
            )
        return "\n".join(lines).rstrip() + "\n"

    def create(
        self,
        *,
        submission: dict[str, Any],
        predecessor_statements: dict[str, str],
        interfaces: dict[str, dict[str, Any]],
        verification_plan: dict[str, Any],
        authorized_artifacts: list[dict[str, str]] | None = None,
        supersedes_bundle_id: str | None = None,
        bundle_reason: str = "initial",
        _creation_authority: object | None = None,
    ) -> dict[str, Any]:
        if not self._inherited_chalk_fixture and (
            self._creation_authority is None
            or _creation_authority is not self._creation_authority
        ):
            raise ValueError(
                "verification bundle construction requires MathGraphStore authority"
            )
        fact_id = validate_fact_id(require_string(submission, "fact_id"))
        submission_sha = require_string(submission, "submission_sha256")
        if SHA256_RE.fullmatch(submission_sha) is None:
            raise ValueError("submission_sha256 is invalid")
        predecessors = submission.get("predecessors", [])
        if set(predecessor_statements) != set(predecessors) or set(interfaces) != set(
            predecessors
        ):
            raise ValueError("verification bundle predecessor interface set mismatch")
        for fact_id_key in predecessors:
            validate_statement_interface(interfaces[fact_id_key])
            if interfaces[fact_id_key]["fact_id"] != fact_id_key:
                raise ValueError("verification interface fact id mismatch")
        mode = verification_plan.get("mode")
        if mode not in {"closed_packet", "artifact_replay"}:
            raise ValueError("verification bundle mode is invalid")
        artifact_index = self._artifact_manifest(submission)
        authorized_artifacts = authorized_artifacts or []
        selected: list[dict[str, str]] = []
        if mode == "closed_packet" and authorized_artifacts:
            raise ValueError("closed_packet bundle cannot contain computation bytes")
        authorized_roles = set(
            verification_plan.get("authorized_artifact_roles", [])
        )
        for item in authorized_artifacts:
            require_exact_keys(
                item,
                required={"key", "role"},
                label="authorized bundle artifact",
            )
            key = (require_string(item, "key"), require_string(item, "role"))
            if key not in artifact_index:
                raise ValueError("bundle artifact was not hash-bound by the submission")
            if key[1] not in authorized_roles:
                raise ValueError("bundle artifact role is outside verifier capability")
            path_parts = Path(artifact_index[key]["path"]).parts
            if "work" in path_parts or "checkpoints" in path_parts:
                raise ValueError(
                    "mutable work/checkpoint bytes cannot enter a verification bundle"
                )
            selected.append(artifact_index[key])
        packet = self._packet(
            submission=submission,
            predecessor_statements=predecessor_statements,
            interfaces=interfaces,
        )
        packet_sha = sha256_bytes(packet.encode("utf-8"))
        interface_entries = [
            {
                "fact_id": predecessor,
                "interface_sha256": interfaces[predecessor]["interface_sha256"],
            }
            for predecessor in sorted(predecessors)
        ]
        selected_sorted = sorted(
            selected, key=lambda value: (value["key"], value["role"])
        )
        artifact_entries = [
            {
                "key": item["key"],
                "role": item["role"],
                "sha256": item["sha256"],
                "bundle_relpath": (
                    f"artifacts/{item['key']}/{Path(item['path']).name}"
                ),
            }
            for item in selected_sorted
        ]
        if supersedes_bundle_id is not None:
            validate_bundle_id(supersedes_bundle_id)
            if bundle_reason != "evidence_expansion":
                raise ValueError("follow-up bundle reason must be evidence_expansion")
            prior_manifest = self.verify(
                supersedes_bundle_id.removeprefix("bundle-")
            )
            if (
                prior_manifest["fact_id"] != fact_id
                or prior_manifest["submission_sha256"] != submission_sha
            ):
                raise ValueError(
                    "follow-up bundle must keep the same fact and submission"
                )
            prior_artifacts = {
                (
                    item["key"],
                    item["role"],
                    item["sha256"],
                    item["bundle_relpath"],
                )
                for item in prior_manifest["artifacts"]
            }
            current_artifacts = {
                (
                    item["key"],
                    item["role"],
                    item["sha256"],
                    item["bundle_relpath"],
                )
                for item in artifact_entries
            }
            if not prior_artifacts < current_artifacts:
                raise ValueError(
                    "follow-up bundle must strictly expand authorized evidence bytes"
                )
        manifest_body = {
            "schema_version": 4,
            "policy_revision": POLICY_REVISION_V4,
            "fact_id": fact_id,
            "submission_sha256": submission_sha,
            "packet_sha256": packet_sha,
            "verification_mode": mode,
            "supersedes_bundle_id": supersedes_bundle_id,
            "bundle_reason": bundle_reason,
            "interfaces": interface_entries,
            "artifacts": artifact_entries,
            "verification_plan": verification_plan,
        }
        digest = sha256_json(manifest_body)
        bundle_id = "bundle-" + digest
        manifest = {
            **manifest_body,
            "bundle_id": bundle_id,
            "bundle_sha256": digest,
        }
        destination = self.by_hash_dir / digest
        if destination.exists():
            existing = self._read_json(destination / "manifest.json")
            if existing != manifest:
                raise ValueError("verification bundle hash collision")
            self._ensure_fact_index_entry(
                fact_id=fact_id,
                entry={
                    "bundle_id": bundle_id,
                    "bundle_sha256": digest,
                    "submission_sha256": submission_sha,
                    "supersedes_bundle_id": supersedes_bundle_id,
                    "bundle_reason": bundle_reason,
                },
            )
            return {
                **manifest,
                "bundle_path": str(destination),
            }
        self.by_hash_dir.mkdir(parents=True, exist_ok=True)
        temporary = Path(
            tempfile.mkdtemp(prefix=f".{digest}.", dir=self.by_hash_dir)
        )
        try:
            self._write_once(temporary / "packet.md", packet.encode("utf-8"))
            for predecessor in sorted(predecessors):
                self._write_once(
                    temporary / "interfaces" / f"{predecessor}.json",
                    json.dumps(
                        interfaces[predecessor],
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    ).encode("utf-8")
                    + b"\n",
                )
            for source, entry in zip(selected_sorted, artifact_entries):
                path = contained_path(
                    self.project_root, source["path"], "computation artifact"
                )
                if not path.is_file() or path.is_symlink():
                    raise ValueError("authorized computation artifact is missing")
                data = path.read_bytes()
                if sha256_bytes(data) != source["sha256"]:
                    raise ValueError("authorized computation artifact hash mismatch")
                self._write_once(temporary / entry["bundle_relpath"], data)
            self._write_once(
                temporary / "manifest.json",
                json.dumps(
                    manifest, ensure_ascii=False, indent=2, sort_keys=True
                ).encode("utf-8")
                + b"\n",
            )
            os.replace(temporary, destination)
        except BaseException:
            shutil.rmtree(temporary, ignore_errors=True)
            raise
        self._ensure_fact_index_entry(
            fact_id=fact_id,
            entry={
                "bundle_id": bundle_id,
                "bundle_sha256": digest,
                "submission_sha256": submission_sha,
                "supersedes_bundle_id": supersedes_bundle_id,
                "bundle_reason": bundle_reason,
            },
        )
        return {
            **manifest,
            "bundle_path": str(destination),
        }

    def verify(self, bundle_sha256: str) -> dict[str, Any]:
        if SHA256_RE.fullmatch(bundle_sha256) is None:
            raise ValueError("bundle_sha256 must be a full lowercase SHA-256")
        directory = self.by_hash_dir / bundle_sha256
        manifest = self._read_json(directory / "manifest.json")
        body = {
            key: manifest[key]
            for key in (
                "schema_version",
                "policy_revision",
                "fact_id",
                "submission_sha256",
                "packet_sha256",
                "verification_mode",
                "supersedes_bundle_id",
                "bundle_reason",
                "interfaces",
                "artifacts",
                "verification_plan",
            )
        }
        if (
            sha256_json(body) != bundle_sha256
            or manifest.get("bundle_id") != "bundle-" + bundle_sha256
            or manifest.get("bundle_sha256") != bundle_sha256
        ):
            raise ValueError("verification bundle manifest hash mismatch")
        packet = directory / "packet.md"
        if sha256_bytes(packet.read_bytes()) != manifest["packet_sha256"]:
            raise ValueError("verification bundle packet was tampered")
        for interface in manifest["interfaces"]:
            path = directory / "interfaces" / f"{interface['fact_id']}.json"
            payload = validate_statement_interface(self._read_json(path))
            if payload["interface_sha256"] != interface["interface_sha256"]:
                raise ValueError("verification bundle interface hash mismatch")
        for artifact in manifest["artifacts"]:
            path = directory / artifact["bundle_relpath"]
            if not path.is_file() or path.is_symlink():
                raise ValueError("verification bundle artifact is missing")
            if sha256_bytes(path.read_bytes()) != artifact["sha256"]:
                raise ValueError("verification bundle artifact was tampered")
        authorized = {
            "manifest.json",
            "packet.md",
            *[
                f"interfaces/{item['fact_id']}.json"
                for item in manifest["interfaces"]
            ],
            *[item["bundle_relpath"] for item in manifest["artifacts"]],
        }
        actual = {
            path.relative_to(directory).as_posix()
            for path in directory.rglob("*")
            if path.is_file() or path.is_symlink()
        }
        if actual != authorized:
            raise ValueError("verification bundle contains unauthorized bytes")
        return manifest

    def capability(
        self,
        *,
        bundle_sha256: str,
        review_return_path: Path | str,
    ) -> dict[str, Any]:
        self.verify(bundle_sha256)
        return {
            "bundle_path": str(self.by_hash_dir / bundle_sha256),
            "bundle_sha256": bundle_sha256,
            "review_return_path": str(Path(review_return_path).resolve()),
            "fork_turns": "none",
        }

    def audit(self) -> dict[str, Any]:
        errors: list[str] = []
        indexed: dict[str, str] = {}
        for path in sorted(self.by_fact_dir.glob("*.jsonl")):
            try:
                fact_id = validate_fact_id(path.stem)
                for number, line in enumerate(
                    path.read_text(encoding="utf-8").splitlines(), 1
                ):
                    if not line.strip():
                        continue
                    entry = json.loads(line)
                    require_exact_keys(
                        entry,
                        required={
                            "bundle_id",
                            "bundle_sha256",
                            "submission_sha256",
                            "supersedes_bundle_id",
                            "bundle_reason",
                        },
                        label=f"verification bundle index {path.name}:{number}",
                    )
                    validate_bundle_id(
                        require_string(entry, "bundle_id")
                    )
                    bundle_sha = require_string(entry, "bundle_sha256")
                    if (
                        SHA256_RE.fullmatch(bundle_sha) is None
                        or entry["bundle_id"] != "bundle-" + bundle_sha
                    ):
                        raise ValueError("bundle id/hash mismatch")
                    if SHA256_RE.fullmatch(
                        require_string(entry, "submission_sha256")
                    ) is None:
                        raise ValueError("submission hash is invalid")
                    manifest = self.verify(bundle_sha)
                    if (
                        manifest["fact_id"] != fact_id
                        or manifest["submission_sha256"]
                        != entry["submission_sha256"]
                        or manifest["supersedes_bundle_id"]
                        != entry["supersedes_bundle_id"]
                        or manifest["bundle_reason"]
                        != entry["bundle_reason"]
                    ):
                        raise ValueError("bundle index/manifest mismatch")
                    if bundle_sha in indexed:
                        raise ValueError("bundle is indexed more than once")
                    indexed[bundle_sha] = fact_id
            except Exception as exc:
                errors.append(f"{path.name}: {exc}")
        for directory in sorted(self.by_hash_dir.iterdir()):
            if not directory.is_dir():
                errors.append(
                    f"bundle root has non-directory entry: {directory.name}"
                )
                continue
            try:
                manifest = self.verify(directory.name)
                if directory.name not in indexed:
                    raise ValueError("bundle has no append-only fact index entry")
                if indexed[directory.name] != manifest["fact_id"]:
                    raise ValueError("bundle is indexed under another fact")
            except Exception as exc:
                errors.append(f"{directory.name}: {exc}")
        return {
            "ok": not errors,
            "errors": errors,
            "bundles": len(indexed),
        }

    @staticmethod
    def validate_followup_eligibility(
        prior_review: dict[str, Any],
    ) -> None:
        validate_review_v4(prior_review)
        if prior_review["verdict"] != "reject":
            raise ValueError("follow-up bundle requires a rejecting prior review")
        classes = {finding["class"] for finding in prior_review["findings"]}
        hard = classes.intersection(HARD_FINDING_CLASSES)
        if hard:
            raise ValueError(
                "mathematical/typing/scope/source-mismatch rejection requires "
                "a new submission, not bundle expansion"
            )
        if not classes.issubset(
            {"evidence_access", "reproducibility", "source_access"}
        ):
            raise ValueError("finding class cannot be resolved by a follow-up bundle")


def admission_gate_v4(
    *,
    review: dict[str, Any],
    bundle_store: VerificationBundleStore,
    prior_reviews: list[dict[str, Any]],
) -> None:
    validate_review_v4(review)
    current_manifest = bundle_store.verify(review["bundle_sha256"])
    if review["verdict"] != "correct" or review["findings"]:
        raise ValueError("v4 admission requires a correct finding-free review")
    prior_findings = {
        (prior.get("review_id"), finding["id"]): finding
        for prior in prior_reviews
        for finding in prior.get("findings", [])
    }
    dispositions = {
        (item["prior_review_id"], item["finding_id"]): item
        for item in review["prior_review_dispositions"]
    }
    if set(dispositions) != set(prior_findings):
        raise ValueError("correct review must disposition every prior finding exactly once")
    ancestor_bundle_hashes: set[str] = set()
    cursor = current_manifest.get("supersedes_bundle_id")
    while cursor is not None:
        validate_bundle_id(cursor)
        cursor_hash = cursor.removeprefix("bundle-")
        if cursor_hash in ancestor_bundle_hashes:
            raise ValueError("verification bundle supersession cycle")
        ancestor_bundle_hashes.add(cursor_hash)
        cursor = bundle_store.verify(cursor_hash).get("supersedes_bundle_id")
    for key, item in dispositions.items():
        finding = prior_findings[key]
        if item["disposition"] == "still_open":
            raise ValueError("admission cannot leave a prior finding open")
        if (
            finding["class"] in HARD_FINDING_CLASSES
            and item["disposition"] == "resolved_by_bundle_expansion"
        ):
            raise ValueError("hard rejection cannot be resolved by bundle expansion")
        if item["disposition"] == "resolved_by_bundle_expansion":
            prior_review = next(
                prior
                for prior in prior_reviews
                if prior.get("review_id") == key[0]
            )
            if prior_review["bundle_sha256"] not in ancestor_bundle_hashes:
                raise ValueError(
                    "bundle-expansion disposition lacks a supersession lineage"
                )
        if (
            item["disposition"] == "resolved_by_new_submission"
            and review["submission_sha256"]
            == next(
                prior
                for prior in prior_reviews
                if prior.get("review_id") == key[0]
            )["submission_sha256"]
        ):
            raise ValueError(
                "new-submission disposition requires a changed submission hash"
            )

from __future__ import annotations

import json
import os
import stat
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .contracts import contained_path, sha256_bytes, sha256_json
from .decision_preflight import V5_FINDING_CLASSES
from .neutral_review_submission import NEUTRAL_REVIEW_SUBMISSION_REVISION
from .verification_bundles import VerificationBundleStore


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _write_once(path: Path, data: bytes, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, mode)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _encoded(payload: dict[str, Any]) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")


def _prepare_v4_verifier_capsule(
    *,
    project_root: Path | str,
    bundle_sha256: str,
    capsule_root: Path | str,
) -> dict[str, Any]:
    """Verify and copy exactly one frozen bundle into a neutral host capsule."""

    project = Path(project_root).resolve()
    capsule = Path(capsule_root).resolve()
    skill_root = Path(__file__).resolve().parents[2]
    if capsule == project or _is_within(capsule, project):
        raise ValueError("verifier capsule must be outside the project root")
    if capsule == skill_root or _is_within(capsule, skill_root):
        raise ValueError("verifier capsule must be outside the skill root")
    if capsule.exists():
        raise ValueError("verifier capsule destination already exists")
    capsule.parent.mkdir(parents=True, exist_ok=True)

    bundles = VerificationBundleStore(project)
    manifest = bundles.verify(bundle_sha256)
    source = bundles.by_hash_dir / bundle_sha256
    authorized_relpaths = [
        "manifest.json",
        "packet.md",
        *[
            f"interfaces/{item['fact_id']}.json"
            for item in manifest["interfaces"]
        ],
        *[item["bundle_relpath"] for item in manifest["artifacts"]],
    ]
    temporary = Path(
        tempfile.mkdtemp(
            prefix=f".{capsule.name}.",
            dir=capsule.parent,
        )
    )
    try:
        input_root = temporary / "input"
        output_root = temporary / "output"
        host_root = temporary / "host"
        output_root.mkdir(parents=True)
        copied: dict[str, str] = {}
        for relpath in authorized_relpaths:
            source_path = contained_path(
                source,
                relpath,
                "verifier capsule bundle input",
            )
            if not source_path.is_file() or source_path.is_symlink():
                raise ValueError("verified bundle source is no longer a regular file")
            data = source_path.read_bytes()
            destination = contained_path(
                input_root,
                relpath,
                "verifier capsule destination",
            )
            _write_once(destination, data, mode=0o400)
            copied[relpath] = sha256_bytes(data)
        review_relpath = "output/review.json"
        capability = {
            "schema_version": 1,
            "policy_revision": manifest["policy_revision"],
            "fact_id": manifest["fact_id"],
            "submission_sha256": manifest["submission_sha256"],
            "bundle_sha256": bundle_sha256,
            "input_file_sha256s": copied,
            "allowed_read_relpaths": [
                f"input/{item}" for item in authorized_relpaths
            ],
            "allowed_write_relpaths": [review_relpath],
            "forbidden_context": [
                "skill instructions",
                "project root",
                "worker conversation",
                "other tests",
            ],
            "isolation": "fresh_context",
            "fork_turns": "none",
            "enforcement_boundary": (
                "cooperative host audit; not an OS filesystem sandbox"
            ),
        }
        _write_once(
            host_root / "capability.json",
            _encoded(capability),
            mode=0o400,
        )
        os.replace(temporary, capsule)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise

    return {
        **capability,
        "capsule_root": str(capsule),
        "allowed_read_paths": [
            str(capsule / item)
            for item in capability["allowed_read_relpaths"]
        ],
        "review_return_path": str(capsule / review_relpath),
        "host_capability_path": str(capsule / "host" / "capability.json"),
        "spawn_task": (
            "Review only the listed frozen input files. Do not load any "
            "external skill or project instruction. Write one strict review "
            "JSON to review_return_path and report every accessed path."
        ),
    }


def _replace_capsule_placeholders(value: Any, capsule_sha256: str) -> Any:
    if isinstance(value, str):
        return value.replace(
            "COPY_EXACT_CAPSULE_SHA256_FROM_CAPSULE_JSON",
            capsule_sha256,
        )
    if isinstance(value, list):
        return [
            _replace_capsule_placeholders(item, capsule_sha256) for item in value
        ]
    if isinstance(value, dict):
        return {
            key: _replace_capsule_placeholders(item, capsule_sha256)
            for key, item in value.items()
        }
    return value


def _validate_v5_capsule_identity(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("V5 capsule JSON must be one object")
    if payload.get("schema_version") != 5:
        raise ValueError("explicit capsule is not a V5 capsule")
    capsule_id = payload.get("capsule_id")
    capsule_sha = payload.get("capsule_sha256")
    if not isinstance(capsule_id, str) or not isinstance(capsule_sha, str):
        raise ValueError("V5 capsule identity fields are missing")
    semantic = {
        key: value
        for key, value in payload.items()
        if key not in {"capsule_id", "capsule_sha256"}
    }
    computed = sha256_json(semantic)
    if capsule_sha != computed or capsule_id != "capsule-" + computed:
        raise ValueError("V5 capsule semantic identity/hash mismatch")
    return payload


def _resolve_v5_capsule(
    *,
    project: Path,
    release_id: str | None,
    capsule_id: str | None,
    capsule_json: Path | str | None,
) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    # Lazy import avoids a package cycle for the compatibility V4 materializer.
    from .store import MathGraphStore

    store = MathGraphStore(project)
    lifecycle = store.v5_lifecycle()
    explicit: dict[str, Any] | None = None
    if capsule_json is not None:
        capsule_path = Path(capsule_json).resolve()
        if capsule_path.is_symlink() or not capsule_path.is_file():
            raise ValueError("explicit V5 capsule JSON is missing or unsafe")
        explicit = _validate_v5_capsule_identity(
            json.loads(capsule_path.read_text(encoding="utf-8"))
        )
        release_id = explicit.get("release_id")
    if capsule_id is not None:
        matches = [
            lifecycle.verifier_capsule(release["release_id"])
            for release in lifecycle.releases()
            if lifecycle.verifier_capsule(release["release_id"])["capsule_id"]
            == capsule_id
        ]
        if len(matches) != 1:
            raise ValueError("V5 capsule id does not resolve to one Candidate Release")
        computed = matches[0]
        release_id = computed["release_id"]
    else:
        if not isinstance(release_id, str):
            raise ValueError("V5 materialization requires a release id")
        computed = lifecycle.verifier_capsule(release_id)
    _validate_v5_capsule_identity(computed)
    if explicit is not None and explicit != computed:
        raise ValueError(
            "explicit V5 capsule does not exactly equal the project-recomputed capsule"
        )
    release = lifecycle.release(str(release_id))
    return lifecycle, release, computed


def _prepare_v5_verifier_capsule(
    *,
    project_root: Path | str,
    capsule_root: Path | str,
    release_id: str | None,
    capsule_id: str | None,
    capsule_json: Path | str | None,
) -> dict[str, Any]:
    project = Path(project_root).resolve()
    capsule = Path(capsule_root).resolve()
    skill_root = Path(__file__).resolve().parents[2]
    if capsule == project or _is_within(capsule, project):
        raise ValueError("verifier capsule must be outside the project root")
    if capsule == skill_root or _is_within(capsule, skill_root):
        raise ValueError("verifier capsule must be outside the skill root")
    existing_empty = False
    if capsule.exists():
        if capsule.is_symlink() or not capsule.is_dir():
            raise ValueError("V5 verifier capsule destination is unsafe")
        if stat.S_IMODE(capsule.stat().st_mode) != 0o700:
            raise ValueError("existing V5 capsule destination must have mode 0700")
        if any(capsule.iterdir()):
            raise ValueError("existing V5 capsule destination must be empty")
        existing_empty = True
    capsule.parent.mkdir(parents=True, exist_ok=True)

    lifecycle, release, v5_capsule = _resolve_v5_capsule(
        project=project,
        release_id=release_id,
        capsule_id=capsule_id,
        capsule_json=capsule_json,
    )
    capsule_sha = v5_capsule["capsule_sha256"]
    host_controlled_review = (
        v5_capsule.get("neutral_review_submission_revision")
        == NEUTRAL_REVIEW_SUBMISSION_REVISION
    )
    authorized = v5_capsule.get("authorized_artifacts")
    if not isinstance(authorized, list) or any(
        not isinstance(item, dict) for item in authorized
    ):
        raise ValueError("V5 capsule authorized_artifacts is invalid")
    release_artifacts = {
        (
            item["artifact_sha256"],
            item["role"],
            item["sealed_relpath"],
        ): item
        for item in release["artifacts"]
    }
    authorized_keys = {
        (
            item.get("artifact_sha256"),
            item.get("role"),
            item.get("sealed_relpath"),
        )
        for item in authorized
    }
    if len(authorized_keys) != len(authorized) or not authorized_keys.issubset(
        release_artifacts
    ):
        raise ValueError("V5 capsule names an unauthorized or duplicate artifact")

    temporary = Path(
        tempfile.mkdtemp(prefix=f".{capsule.name}.", dir=capsule.parent)
    )
    os.chmod(temporary, 0o700)
    try:
        input_root = temporary / "input"
        output_root = temporary / "output"
        host_root = temporary / "host"
        output_root.mkdir(parents=True, mode=0o700)
        host_root.mkdir(parents=True, mode=0o700)
        capsule_relpath = "input/capsule.json"
        capsule_bytes = _encoded(v5_capsule)
        _write_once(temporary / capsule_relpath, capsule_bytes, mode=0o400)

        transported: list[dict[str, Any]] = []
        allowed_read_relpaths = [capsule_relpath]
        copied_hashes = {capsule_relpath: sha256_bytes(capsule_bytes)}
        for item in sorted(
            authorized,
            key=lambda value: (
                value["artifact_sha256"],
                value["role"],
                value["sealed_relpath"],
            ),
        ):
            source_relpath = item["sealed_relpath"]
            source_path = contained_path(
                project,
                source_relpath,
                "V5 verifier capsule artifact source",
            )
            if source_path.is_symlink() or not source_path.is_file():
                raise ValueError("V5 authorized artifact is missing or unsafe")
            raw = source_path.read_bytes()
            digest = sha256_bytes(raw)
            if digest != item["artifact_sha256"]:
                raise ValueError("V5 authorized artifact bytes/hash drifted")
            destination_relpath = (
                f"input/artifacts/{digest}/{item['name']}"
            )
            destination = contained_path(
                temporary,
                destination_relpath,
                "V5 verifier capsule artifact destination",
            )
            _write_once(destination, raw, mode=0o400)
            allowed_read_relpaths.append(destination_relpath)
            copied_hashes[destination_relpath] = digest
            transported.append(
                {
                    "source_relpath": source_relpath,
                    "destination_relpath": destination_relpath,
                    "sha256": digest,
                    "bytes": len(raw),
                    "role": item["role"],
                }
            )

        template = lifecycle._certification_decision_template(release)
        template = _replace_capsule_placeholders(template, capsule_sha)
        template_relpath = "input/decision-template.json"
        template_bytes = _encoded(template)
        _write_once(temporary / template_relpath, template_bytes, mode=0o400)
        allowed_read_relpaths.append(template_relpath)
        copied_hashes[template_relpath] = sha256_bytes(template_bytes)

        validator_source = Path(__file__).with_name("decision_preflight.py")
        validator_bytes = validator_source.read_bytes()
        validator_relpath = "host/validate_decision.py"
        _write_once(temporary / validator_relpath, validator_bytes, mode=0o500)
        copied_hashes[validator_relpath] = sha256_bytes(validator_bytes)

        submitter_relpath = "host/submit_review.py"
        if host_controlled_review:
            submitter_source = Path(__file__).with_name(
                "neutral_review_submission.py"
            )
            submitter_bytes = submitter_source.read_bytes()
            _write_once(
                temporary / submitter_relpath,
                submitter_bytes,
                mode=0o500,
            )
            copied_hashes[submitter_relpath] = sha256_bytes(submitter_bytes)

        transport_core = {
            "schema_version": 1,
            "kind": "chalxius-v5-neutral-capsule-transport",
            "project_id": v5_capsule["project_id"],
            "release_id": v5_capsule["release_id"],
            "release_sha256": v5_capsule["release_sha256"],
            "capsule_semantic_sha256": capsule_sha,
            "omitted_capsule_identity_fields": [
                "capsule_id",
                "capsule_sha256",
            ],
            "files": transported,
        }
        transport_manifest = {
            **transport_core,
            "transport_sha256": sha256_json(transport_core),
        }
        transport_relpath = "host/transport-manifest.json"
        transport_bytes = _encoded(transport_manifest)
        _write_once(temporary / transport_relpath, transport_bytes, mode=0o400)
        copied_hashes[transport_relpath] = sha256_bytes(transport_bytes)

        review_draft_relpath = "output/review-draft.json"
        review_relpath = "output/review.json"
        capability = {
            "schema_version": 3 if host_controlled_review else 2,
            "kind": "chalxius-v5-neutral-verifier-capability",
            "policy_revision": v5_capsule["policy_revision"],
            "project_id": v5_capsule["project_id"],
            "release_id": v5_capsule["release_id"],
            "release_sha256": v5_capsule["release_sha256"],
            "capsule_id": v5_capsule["capsule_id"],
            "capsule_sha256": capsule_sha,
            "input_file_sha256s": dict(sorted(copied_hashes.items())),
            "allowed_read_relpaths": allowed_read_relpaths,
            "allowed_execute_relpaths": [
                validator_relpath,
                *([submitter_relpath] if host_controlled_review else []),
            ],
            "allowed_write_relpaths": [
                review_draft_relpath if host_controlled_review else review_relpath
            ],
            "allowed_live_queries": v5_capsule.get(
                "source_query_capabilities", []
            ),
            "forbidden_context": [
                "skill instructions",
                "project root",
                "worker conversation",
                "other tests",
            ],
            "isolation": "fresh_context",
            "fork_turns": "none",
            "enforcement_boundary": (
                "cooperative host audit; not an OS filesystem sandbox"
            ),
            "decision_preflight_command": [
                "python3",
                validator_relpath,
                "--capsule",
                capsule_relpath,
                "--decision",
                (
                    review_draft_relpath
                    if host_controlled_review
                    else review_relpath
                ),
            ],
            **(
                {
                    "review_submission_command": [
                        "python3",
                        submitter_relpath,
                        "--capsule-root",
                        ".",
                    ]
                }
                if host_controlled_review
                else {}
            ),
            "allowed_finding_classes": list(V5_FINDING_CLASSES),
            "role_boundary": (
                {
                    "verifier": "writes only output/review-draft.json",
                    "host": (
                        "strictly preflights the draft, quarantines failures, and "
                        "atomically publishes immutable output/review.json plus its "
                        "content-addressed formal-return receipt"
                    ),
                    "gateway": (
                        "consumes only the formally returned bytes and receipt; it "
                        "records or admits nothing after a failed preflight"
                    ),
                }
                if host_controlled_review
                else {
                    "verifier": "writes and preflights only output/review.json",
                    "gateway": (
                        "records exact returned bytes and admits only after validation"
                    ),
                }
            ),
        }
        _write_once(
            host_root / "capability.json",
            _encoded(capability),
            mode=0o400,
        )
        if existing_empty:
            capsule.rmdir()
        os.replace(temporary, capsule)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise

    return {
        **capability,
        "capsule_root": str(capsule),
        "allowed_read_paths": [
            str(capsule / item) for item in capability["allowed_read_relpaths"]
        ],
        **(
            {"review_draft_path": str(capsule / review_draft_relpath)}
            if host_controlled_review
            else {}
        ),
        "review_return_path": str(capsule / review_relpath),
        "host_capability_path": str(capsule / "host" / "capability.json"),
        "transport_manifest_path": str(capsule / transport_relpath),
        "decision_template_path": str(capsule / template_relpath),
        "decision_validator_path": str(capsule / validator_relpath),
        **(
            {
                "review_submission_path": str(capsule / submitter_relpath),
                "review_handoff_dir": str(capsule / "output" / "handoff"),
            }
            if host_controlled_review
            else {}
        ),
        "spawn_task": (
            (
                "Review only the listed frozen inputs and write "
                "output/review-draft.json. The host runs host/submit_review.py; "
                "only that preflight gate may publish output/review.json and its "
                "formal-return receipt. The gateway, not the verifier, records or "
                "admits the returned review."
            )
            if host_controlled_review
            else (
                "Review only the listed frozen inputs, write output/review.json, "
                "run the local decision preflight, and return the unchanged bytes. "
                "The gateway, not the verifier, records or admits them."
            )
        ),
    }


def prepare_verifier_capsule(
    *,
    project_root: Path | str,
    capsule_root: Path | str,
    bundle_sha256: str | None = None,
    release_id: str | None = None,
    capsule_id: str | None = None,
    capsule_json: Path | str | None = None,
) -> dict[str, Any]:
    """Materialize exactly one compatibility V4 bundle or V5 capsule."""

    selectors = [
        bundle_sha256 is not None,
        release_id is not None,
        capsule_id is not None,
        capsule_json is not None,
    ]
    if sum(selectors) != 1:
        raise ValueError(
            "select exactly one of bundle_sha256, release_id, capsule_id, or capsule_json"
        )
    if bundle_sha256 is not None:
        return _prepare_v4_verifier_capsule(
            project_root=project_root,
            bundle_sha256=bundle_sha256,
            capsule_root=capsule_root,
        )
    return _prepare_v5_verifier_capsule(
        project_root=project_root,
        capsule_root=capsule_root,
        release_id=release_id,
        capsule_id=capsule_id,
        capsule_json=capsule_json,
    )

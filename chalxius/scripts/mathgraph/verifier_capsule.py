from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .contracts import contained_path, sha256_bytes
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


def prepare_verifier_capsule(
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

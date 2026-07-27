from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

from .contracts import sha256_bytes, sha256_json
from .store import MathGraphStore


def project_tree_snapshot(root: Path | str) -> dict[str, Any]:
    """Hash one project tree without following links or changing its state."""

    project_root = Path(root).expanduser().resolve()
    if not project_root.is_dir():
        raise ValueError(f"project source is not a directory: {project_root}")
    inventory: dict[str, dict[str, Any]] = {}
    for path in sorted(
        project_root.rglob("*"),
        key=lambda item: item.relative_to(project_root).as_posix(),
    ):
        relative = path.relative_to(project_root).as_posix()
        if path.is_symlink():
            raise ValueError(
                "project inheritance rejects symlinks: "
                f"{relative}"
            )
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError(
                "project inheritance rejects non-regular files: "
                f"{relative}"
            )
        raw = path.read_bytes()
        inventory[relative] = {
            "byte_length": len(raw),
            "sha256": sha256_bytes(raw),
        }
    project_path = project_root / "project.json"
    if "project.json" not in inventory:
        raise ValueError(f"not an initialized math graph: {project_root}")
    project = json.loads(project_path.read_text(encoding="utf-8"))
    if not isinstance(project, dict):
        raise ValueError("project.json must contain one object")
    return {
        "schema_version": 1,
        "tree_sha256": sha256_json(inventory),
        "file_count": len(inventory),
        "total_bytes": sum(
            item["byte_length"] for item in inventory.values()
        ),
        "project_semantic_sha256": sha256_json(project),
    }


def _validate_copy_boundary(source: Path, destination: Path) -> None:
    if source == destination:
        raise ValueError("stable source and Chalk destination must differ")
    if source in destination.parents or destination in source.parents:
        raise ValueError(
            "stable source and Chalk destination must not be nested"
        )
    if os.path.lexists(destination):
        raise ValueError(
            f"Chalk destination already exists: {destination}"
        )
    if not destination.parent.is_dir():
        raise ValueError(
            "Chalk destination parent must already exist: "
            f"{destination.parent}"
        )


def upgrade_stable_project_copy(
    *,
    source: Path | str,
    destination: Path | str,
    actor: str = "",
    dry_run: bool,
) -> dict[str, Any]:
    """Copy a stable V3 project, migrate only the copy, and bind its lineage."""

    source_root = Path(source).expanduser().resolve()
    destination_root = Path(destination).expanduser().resolve()
    _validate_copy_boundary(source_root, destination_root)

    source_store = MathGraphStore(source_root)
    source_store.require_initialized()
    source_workflow = source_store.workflow_evidence_version()
    if source_workflow != 3:
        raise ValueError(
            "stable-to-Chalk project inheritance requires workflow "
            f"evidence v3, found {source_workflow}"
        )
    source_snapshot = project_tree_snapshot(source_root)
    source_audit = source_store.audit().as_dict()
    plan = {
        "schema_version": 1,
        "operation": "stable-project-copy-to-chalk-v4",
        "source_project_id": source_store.project_id(),
        "source_workflow_evidence_version": source_workflow,
        "destination_workflow_evidence_version": 4,
        "source_tree_sha256": source_snapshot["tree_sha256"],
        "source_file_count": source_snapshot["file_count"],
        "source_total_bytes": source_snapshot["total_bytes"],
        "source_current_ok_before_projection": source_audit["current_ok"],
        "source_history_clean": source_audit["history_clean"],
        "source_root": str(source_root),
        "destination_root": str(destination_root),
        "source_mutation": "forbidden",
        "destination_state": "chalk-v4-only-after-upgrade",
        "dry_run": dry_run,
    }
    if dry_run:
        return {**plan, "status": "planned"}
    if not isinstance(actor, str) or not actor.strip():
        raise ValueError(
            "stable-to-Chalk project inheritance requires a nonempty actor"
        )

    staging_root = destination_root.parent / (
        f".{destination_root.name}.chalk-staging-{uuid.uuid4().hex}"
    )
    try:
        shutil.copytree(source_root, staging_root, copy_function=shutil.copy2)
        copied_snapshot = project_tree_snapshot(staging_root)
        if copied_snapshot != source_snapshot:
            raise RuntimeError(
                "copied project bytes do not match the stable source snapshot"
            )

        inheritance = {
            "schema_version": 1,
            "inheritance_kind": "stable-project-copy-to-chalk-v4",
            "source_project_id": source_store.project_id(),
            "source_workflow_evidence_version": 3,
            "source_tree_sha256": source_snapshot["tree_sha256"],
            "source_file_count": source_snapshot["file_count"],
            "source_total_bytes": source_snapshot["total_bytes"],
            "source_project_semantic_sha256": source_snapshot[
                "project_semantic_sha256"
            ],
            "assurance_policy": (
                "preserve-recorded-legacy-assurance;never-relabel-as-v4"
            ),
            "state_boundary": (
                "stable-source-read-only;chalk-copy-v4-only"
            ),
        }
        staged_store = MathGraphStore._for_legacy_workflow_fixture(
            staging_root
        )
        upgraded = staged_store.upgrade_workflow(
            to_version=4,
            dry_run=False,
            actor=actor.strip(),
            stable_copy_inheritance=inheritance,
        )

        source_after = project_tree_snapshot(source_root)
        if source_after != source_snapshot:
            raise RuntimeError(
                "stable source changed during copy migration; do not cut over"
            )
        staged_audit = staged_store.audit().as_dict()
        if not staged_audit["current_ok"]:
            raise RuntimeError(
                "migrated Chalk copy has current audit errors: "
                + "; ".join(staged_audit["errors"])
            )
        if os.path.lexists(destination_root):
            raise RuntimeError(
                "Chalk destination appeared during migration; refusing "
                "to overwrite it"
            )
        staging_root.rename(destination_root)
    except Exception as exc:
        preservation = (
            f"staging copy preserved at {staging_root}"
            if os.path.lexists(staging_root)
            else "no staging copy was created"
        )
        raise RuntimeError(
            f"stable-to-Chalk copy upgrade failed; {preservation}: {exc}"
        ) from exc

    return {
        **plan,
        "dry_run": False,
        "status": "upgraded_copy",
        "migration_receipt_id": upgraded["migration_receipt_id"],
        "legacy_default_campaign_id": upgraded[
            "legacy_default_campaign_id"
        ],
        "source_unchanged": True,
        "destination_current_ok": staged_audit["current_ok"],
        "destination_history_clean": staged_audit["history_clean"],
        "destination_historical_workflow_warnings": staged_audit[
            "historical_workflow_warnings"
        ],
        "destination_trust_debt": staged_audit["trust_debt"],
        "cutover_status": "not_performed",
    }

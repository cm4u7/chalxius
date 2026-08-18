"""Single source of truth for cross-file release-assurance revisions.

These values are runtime-neutral metadata.  They bind the architecture
scanner, CHX receipt admission, the capability registry, and the release lock
without granting any research or Fact authority.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ARCHITECTURE_RECONNAISSANCE_REVISION = (
    "chalxius-architecture-reconnaissance-4"
)
CAPABILITY_TOPOLOGY_REGISTRY_REVISION = (
    "chalxius-capability-topology-registry-3"
)
RELEASE_VALIDATION_MATRIX_REVISION = "chalxius-release-validation-matrix-6"


def validate_release_audit_revision_bindings(
    skill_root: Path,
) -> dict[str, str]:
    """Fail closed unless all release metadata names the current contracts."""

    root = skill_root.expanduser().resolve(strict=True)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("release audit root must be one canonical directory")
    lock = _load_object(root / "INHERITANCE.lock.json", "inheritance lock")
    release_audit = lock.get("release_audit")
    if not isinstance(release_audit, dict):
        raise ValueError("inheritance lock release_audit must be an object")
    registry = _load_object(
        root / "references" / "capability_topology_registry.json",
        "capability topology registry",
    )
    actual = {
        "architecture_reconnaissance_revision": release_audit.get(
            "architecture_reconnaissance_revision"
        ),
        "capability_registry_revision": release_audit.get(
            "capability_registry_revision"
        ),
        "registry_contract_revision": registry.get("contract_revision"),
        "release_validation_matrix_revision": release_audit.get(
            "coordinator_contract_revision"
        ),
    }
    expected = {
        "architecture_reconnaissance_revision": (
            ARCHITECTURE_RECONNAISSANCE_REVISION
        ),
        "capability_registry_revision": (
            CAPABILITY_TOPOLOGY_REGISTRY_REVISION
        ),
        "registry_contract_revision": (
            CAPABILITY_TOPOLOGY_REGISTRY_REVISION
        ),
        "release_validation_matrix_revision": (
            RELEASE_VALIDATION_MATRIX_REVISION
        ),
    }
    if actual != expected:
        raise ValueError(
            "release audit revision binding mismatch: "
            f"expected={expected!r} actual={actual!r}"
        )
    return expected


def _load_object(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{label} must be one regular file")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is unreadable") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must contain one JSON object")
    return payload

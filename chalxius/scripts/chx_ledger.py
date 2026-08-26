#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import secrets
import sys
import unicodedata
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterator, Sequence

sys.dont_write_bytecode = True

from mathgraph.runtime_archive import (
    runtime_binding_from_root,
    validate_bound_runtime_at,
    validate_runtime_binding,
)
from mathgraph.release_contracts import (
    ARCHITECTURE_RECONNAISSANCE_REVISION as ARCHITECTURE_RECONNAISSANCE_CONTRACT_REVISION,
)
from operational_ledger_core import (
    canonical_bytes as _core_canonical_bytes,
    canonical_nfc_bytes as _core_canonical_nfc_bytes,
    event_sha256 as _core_event_sha256,
    new_run_id as _core_new_run_id,
    normalize_unicode as _core_normalize_unicode,
    require_text as _core_require_text,
    sha256 as _core_sha256,
    utc_now as _core_utc_now,
    with_hash as _core_with_hash,
    write_new_ledger_events as _core_write_new_ledger_events,
)


SCHEMA_VERSION = 1
LEGACY_CONTRACT_REVISION = "chalxius-chx-run-ledger-1"
PLACEMENT_CONTRACT_REVISION = "chalxius-chx-run-ledger-2"
FINDING_CONTRACT_REVISION = "chalxius-chx-run-ledger-3"
LINEAGE_CONTRACT_REVISION = "chalxius-chx-run-ledger-4"
REPAIR_CONTRACT_REVISION = "chalxius-chx-run-ledger-5"
CONTRACT_REVISION = REPAIR_CONTRACT_REVISION
INVENTORY_CONTRACT_REVISION = "chalxius-chx-ledger-inventory-1"
LEDGER_DISPOSITION_CONTRACT_REVISION = (
    "chalxius-chx-ledger-administrative-disposition-1"
)
GLOBAL_REPAIR_CONTRACT_REVISION = "chalxius-chx-global-integrated-repair-3"
GLOBAL_REPAIR_INPUT_REVISION = "chalxius-chx-global-integrated-repair-input-3"
FINDING_CONTRACT_REVISIONS = frozenset(
    {
        FINDING_CONTRACT_REVISION,
        LINEAGE_CONTRACT_REVISION,
        REPAIR_CONTRACT_REVISION,
    }
)
LINEAGE_CONTRACT_REVISIONS = frozenset(
    {LINEAGE_CONTRACT_REVISION, REPAIR_CONTRACT_REVISION}
)
REPAIR_CONTRACT_REVISIONS = frozenset({REPAIR_CONTRACT_REVISION})
SUPPORTED_CONTRACT_REVISIONS = frozenset(
    {
        LEGACY_CONTRACT_REVISION,
        PLACEMENT_CONTRACT_REVISION,
        FINDING_CONTRACT_REVISION,
        LINEAGE_CONTRACT_REVISION,
        REPAIR_CONTRACT_REVISION,
    }
)
DEFAULT_PROJECT_LEDGER_DIR = "chx-ledgers"
LEDGER_DISPOSITION_DIR = "administrative-dispositions"
LEDGER_ADMINISTRATIVE_STATUSES = frozenset(
    {"abandoned", "superseded", "administratively_complete"}
)
CAUSATIONS = frozenset({"caused", "materially_amplified"})
MECHANISM_TYPES = frozenset(
    {
        "state_model",
        "coupling",
        "automatic_trigger",
        "validation_boundary",
        "recovery_rule",
        "authority_boundary",
        "interface_contract",
    }
)
DISPOSITION_STATUSES = frozenset({"resolved", "excluded_nonarchitectural"})
FINDING_RECONCILIATIONS = frozenset(
    {"promoted_to_issue", "merged_with_reason", "excluded_with_reason"}
)
ISSUE_RELATION_TYPES = frozenset(
    {"related_to", "extends", "discovered_from", "supersedes"}
)
RUN_ID_RE = re.compile(r"run-[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
ISSUE_ID_RE = re.compile(r"CHX-[0-9]{3,}")
FINDING_ID_RE = re.compile(r"finding-[0-9a-f]{64}")
RECONNAISSANCE_ID_RE = re.compile(r"reconnaissance-[0-9a-f]{64}")
TACTICAL_REPAIR_ID_RE = re.compile(r"tactical-repair-[0-9a-f]{64}")
INTEGRATED_REPAIR_ID_RE = re.compile(r"integrated-repair-[0-9a-f]{64}")
GLOBAL_REPAIR_ID_RE = re.compile(r"global-repair-[0-9a-f]{64}")
LEDGER_DISPOSITION_ID_RE = re.compile(
    r"ledger-disposition-[0-9a-f]{64}"
)
QUALIFIED_ISSUE_ID_RE = re.compile(
    r"run-[A-Za-z0-9][A-Za-z0-9._-]{0,127}/CHX-[0-9]{3,}"
)
GLOBAL_REPAIR_BASES = frozenset(
    {
        "fixed_by_unified_repair",
        "historical_nonarchitectural",
        "revalidated_current",
        "superseded_current",
    }
)
DIGEST_BOUND_REFERENCE_RE = re.compile(
    r"(candidate|project):([^#]+)#sha256=([0-9a-f]{64})"
)
MECHANISM_ID_RE = re.compile(r"mechanism\.[a-z][a-z0-9._-]{0,127}")
DECISION_ID_RE = re.compile(r"decision\.[a-z][a-z0-9._-]{0,127}")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
PUBLIC_DISCLOSURE_CONTRACT_REVISION = "chalxius-chx-public-disclosure-2"
REUSABLE_MECHANISM_REGISTRY_REVISION = (
    "chalxius-chx-reusable-mechanism-registry-1"
)


def _canonical_bytes(payload: Any) -> bytes:
    return _core_canonical_bytes(payload)


def _canonical_nfc_bytes(payload: Any) -> bytes:
    return _core_canonical_nfc_bytes(payload)


def _normalize_unicode(value: Any) -> Any:
    """Return the NFC-normalized JSON value used by prospective v3 ids.

    Historical v1/v2 event bytes are never rewritten.  This normalization is
    applied only while computing new canonical bytes, which prevents two
    visually identical findings from acquiring different ids.
    """

    return _core_normalize_unicode(value)


def _sha256(payload: bytes) -> str:
    return _core_sha256(payload)


def _parse_utc_timestamp(value: Any, *, label: str) -> datetime:
    text = _require_text(value, label, maximum=64)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} is not an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label} must include an explicit timezone")
    return parsed.astimezone(timezone.utc)


def _qualified_issue_sort_key(value: str) -> tuple[str, int]:
    if not isinstance(value, str) or QUALIFIED_ISSUE_ID_RE.fullmatch(value) is None:
        raise ValueError("qualified CHX issue id is invalid")
    run_id, issue_id = value.split("/", 1)
    return run_id, int(issue_id.removeprefix("CHX-"))


def _canonical_qualified_issue_ids(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str)
        or QUALIFIED_ISSUE_ID_RE.fullmatch(item) is None
        for item in value
    ):
        raise ValueError(f"{label} must be a list of qualified CHX issue ids")
    normalized = sorted(set(value), key=_qualified_issue_sort_key)
    if value != normalized:
        raise ValueError(f"{label} must be sorted and duplicate-free")
    return normalized


def _canonical_digest_bound_references(value: Any, label: str) -> list[str]:
    references = _require_canonical_string_list(value, label, nonempty=True)
    for reference in references:
        match = DIGEST_BOUND_REFERENCE_RE.fullmatch(reference)
        if match is None:
            raise ValueError(
                f"{label} entries must use ROOT:relative/path#sha256=DIGEST"
            )
        relpath = match.group(2)
        pure = PurePosixPath(relpath)
        if (
            pure.is_absolute()
            or "\\" in relpath
            or any(part in {"", ".", ".."} for part in pure.parts)
            or str(pure) != relpath
        ):
            raise ValueError(f"{label} contains an unsafe relative path")
    return references


def _verify_digest_bound_reference(
    reference: str,
    *,
    candidate_root: Path,
    project_root: Path,
) -> None:
    match = DIGEST_BOUND_REFERENCE_RE.fullmatch(reference)
    if match is None:  # pragma: no cover - syntax validation precedes verification
        raise ValueError("CHX global repair digest-bound reference is invalid")
    root = candidate_root if match.group(1) == "candidate" else project_root
    pure = PurePosixPath(match.group(2))
    path = root
    for part in pure.parts:
        path = path / part
        if path.is_symlink():
            raise ValueError("CHX global repair reference traverses a symlink")
    if not path.is_file():
        raise ValueError("CHX global repair reference file is missing")
    resolved = path.resolve(strict=True)
    if resolved != root and root not in resolved.parents:
        raise ValueError("CHX global repair reference escaped its declared root")
    if _sha256(path.read_bytes()) != match.group(3):
        raise ValueError("CHX global repair reference hash drifted")


def _verify_global_repair_references(
    integration: dict[str, Any],
    *,
    project_root: Path,
) -> None:
    candidate_root = _resolved_path(integration["candidate_root"])
    if any(
        not reference.startswith("project:")
        for reference in integration["regression_evidence"]
    ):
        raise ValueError(
            "CHX global repair regression evidence must bind project receipts"
        )
    references = {
        *integration["risk_evidence"],
        *integration["regression_evidence"],
    }
    group_for_issue: dict[str, dict[str, Any]] = {}
    for group in integration["mechanism_groups"]:
        if any(
            not reference.startswith("candidate:")
            for reference in group["implementation_anchors"]
        ):
            raise ValueError(
                "CHX global repair implementation anchors must bind candidate files"
            )
        references.update(group["implementation_anchors"])
        references.update(group["evidence"])
        for issue_id in group["issue_ids"]:
            group_for_issue[issue_id] = group
    regression = set(integration["regression_evidence"])
    for group in integration["mechanism_groups"]:
        if not set(group["evidence"]).issubset(regression):
            raise ValueError(
                "CHX global repair mechanism evidence must be included in "
                "global regression evidence"
            )
    for disposition in integration["issue_dispositions"]:
        group = group_for_issue[disposition["qualified_issue_id"]]
        if not set(disposition["evidence"]).issubset(set(group["evidence"])):
            raise ValueError(
                "CHX global repair disposition evidence must be included in "
                "its mechanism group evidence"
            )
        references.update(disposition["evidence"])
    for reference in sorted(references):
        _verify_digest_bound_reference(
            reference,
            candidate_root=candidate_root,
            project_root=project_root,
        )


def _global_repair_semantic(event: dict[str, Any]) -> dict[str, Any]:
    return {
        key: event[key]
        for key in (
            "schema_version",
            "contract_revision",
            "event",
            "project_root",
            "candidate_root",
            "candidate_version",
            "candidate_manifest_sha256",
            "inventory_sha256",
            "covered_issue_snapshot_sha256",
            "included_issue_ids",
            "issue_dispositions",
            "mechanism_groups",
            "risk_evidence",
            "regression_evidence",
            "supersedes_global_repair_id",
            "truth_effect",
            "project_effect",
        )
    }


def _global_repair_id(event: dict[str, Any]) -> str:
    return "global-repair-" + _sha256(
        _canonical_nfc_bytes(_global_repair_semantic(event))
    )


def _event_sha256(event: dict[str, Any]) -> str:
    return _core_event_sha256(event)


def _utc_now() -> str:
    return _core_utc_now()


def _require_text(value: Any, label: str, *, maximum: int = 8_192) -> str:
    return _core_require_text(value, label, maximum=maximum)


def _require_string_list(
    value: Any,
    label: str,
    *,
    nonempty: bool,
) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(f"{label} must be a list of nonempty strings")
    if nonempty and not value:
        raise ValueError(f"{label} must contain at least one entry")
    if len(value) > 128:
        raise ValueError(f"{label} exceeds 128 entries")
    return list(value)


def _require_canonical_string_list(
    value: Any,
    label: str,
    *,
    nonempty: bool,
) -> list[str]:
    result = _require_string_list(value, label, nonempty=nonempty)
    if result != sorted(set(result)):
        raise ValueError(f"{label} must be sorted and duplicate-free")
    return result


def _validate_architecture_reconnaissance_report(
    report: Any,
) -> dict[str, Any]:
    """Validate one full-tree reconnaissance artifact without rerunning it.

    The architecture scanner owns the full inventory.  CHX records its
    content-addressed result once so later tactical and integrated events do
    not repeat an administrative scan or silently replace the inspected tree.
    A pre-repair report may legitimately contain errors and warnings.
    """

    if not isinstance(report, dict):
        raise ValueError("CHX architecture reconnaissance input must be an object")
    expected_fields = {
        "schema_version",
        "contract_revision",
        "root",
        "version",
        "counts",
        "manifest",
        "modules",
        "generated_artifacts",
        "unreferenced_modules",
        "production_unreferenced_modules",
        "orphan_modules",
        "exact_duplicate_files",
        "duplicate_function_bodies",
        "duplicate_body_adjudication",
        "commands",
        "capability_registry",
        "behavioral_features",
        "baseline_comparison",
        "installed_comparison",
        "errors",
        "warnings",
        "truth_effect",
        "inventory_sha256",
    }
    if set(report) != expected_fields:
        raise ValueError(
            "CHX architecture reconnaissance fields are not exact"
        )
    if report.get("schema_version") != 1:
        raise ValueError("CHX architecture reconnaissance schema is invalid")
    if (
        report.get("contract_revision")
        != ARCHITECTURE_RECONNAISSANCE_CONTRACT_REVISION
    ):
        raise ValueError("CHX architecture reconnaissance revision is invalid")
    if report.get("truth_effect") != "none":
        raise ValueError("CHX architecture reconnaissance authority is invalid")
    root_text = _require_text(
        report.get("root"), "CHX architecture reconnaissance root", maximum=4_096
    )
    root = Path(root_text).expanduser()
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise ValueError("CHX architecture reconnaissance root is unsafe")
    if str(root.resolve(strict=True)) != root_text:
        raise ValueError("CHX architecture reconnaissance root is not canonical")
    _require_text(
        report.get("version"),
        "CHX architecture reconnaissance version",
        maximum=64,
    )
    counts = report.get("counts")
    if (
        not isinstance(counts, dict)
        or not isinstance(counts.get("files"), int)
        or isinstance(counts.get("files"), bool)
        or counts["files"] < 1
    ):
        raise ValueError("CHX architecture reconnaissance file count is invalid")
    if (
        not isinstance(report.get("manifest"), dict)
        or not isinstance(report.get("modules"), dict)
        or not isinstance(report.get("commands"), dict)
    ):
        raise ValueError("CHX architecture reconnaissance inventory is incomplete")
    for field in (
        "generated_artifacts",
        "unreferenced_modules",
        "production_unreferenced_modules",
        "orphan_modules",
        "exact_duplicate_files",
        "duplicate_function_bodies",
    ):
        if not isinstance(report.get(field), list):
            raise ValueError(
                f"CHX architecture reconnaissance {field} is invalid"
            )
    for field in ("baseline_comparison", "installed_comparison"):
        if report.get(field) is not None and not isinstance(report.get(field), dict):
            raise ValueError(
                f"CHX architecture reconnaissance {field} is invalid"
            )
    capability = report.get("capability_registry")
    behavioral = report.get("behavioral_features")
    if not isinstance(capability, dict) or not isinstance(behavioral, dict):
        raise ValueError("CHX architecture reconnaissance registries are missing")
    capability_sha256 = capability.get("registry_sha256")
    behavioral_sha256 = behavioral.get("registry_sha256")
    if (
        not isinstance(capability_sha256, str)
        or SHA256_RE.fullmatch(capability_sha256) is None
        or not isinstance(behavioral_sha256, str)
        or SHA256_RE.fullmatch(behavioral_sha256) is None
    ):
        raise ValueError("CHX architecture reconnaissance registry hash is invalid")
    errors = _require_canonical_string_list(
        report.get("errors"),
        "CHX architecture reconnaissance errors",
        nonempty=False,
    )
    warnings = _require_canonical_string_list(
        report.get("warnings"),
        "CHX architecture reconnaissance warnings",
        nonempty=False,
    )
    inventory_sha256 = report.get("inventory_sha256")
    if not isinstance(inventory_sha256, str) or SHA256_RE.fullmatch(
        inventory_sha256
    ) is None:
        raise ValueError("CHX architecture reconnaissance digest is invalid")
    semantic = {
        key: value for key, value in report.items() if key != "inventory_sha256"
    }
    expected = _sha256(
        json.dumps(
            semantic,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    if inventory_sha256 != expected:
        raise ValueError("CHX architecture reconnaissance digest mismatch")
    return {
        "candidate_root": root_text,
        "candidate_version": report["version"],
        "candidate_file_count": counts["files"],
        "inventory_sha256": inventory_sha256,
        "report_sha256": _sha256(_canonical_nfc_bytes(report)),
        "capability_registry_sha256": capability_sha256,
        "behavioral_registry_sha256": behavioral_sha256,
        "scan_errors": errors,
        "scan_warnings": warnings,
    }


def _reconnaissance_semantic(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        key: receipt[key]
        for key in (
            "candidate_root",
            "candidate_version",
            "candidate_file_count",
            "inventory_sha256",
            "report_sha256",
            "capability_registry_sha256",
            "behavioral_registry_sha256",
            "scan_errors",
            "scan_warnings",
            "scope",
            "truth_effect",
        )
    }


def _reconnaissance_id(receipt: dict[str, Any]) -> str:
    return "reconnaissance-" + _sha256(
        _canonical_nfc_bytes(_reconnaissance_semantic(receipt))
    )


def _validate_tactical_repair_input(value: Any) -> dict[str, Any]:
    expected = {
        "mechanism_id",
        "summary",
        "applicability",
        "implementation",
        "fail_closed_boundary",
        "reusable_domains",
        "implementation_anchors",
        "bounded_validation_evidence",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("CHX tactical repair input fields are not exact")
    mechanism_id = value.get("mechanism_id")
    if not isinstance(mechanism_id, str) or MECHANISM_ID_RE.fullmatch(
        mechanism_id
    ) is None:
        raise ValueError("CHX tactical repair mechanism_id is invalid")
    normalized = {
        "mechanism_id": mechanism_id,
        "summary": _require_text(value.get("summary"), "CHX tactical summary"),
        "applicability": _require_text(
            value.get("applicability"), "CHX tactical applicability"
        ),
        "implementation": _require_text(
            value.get("implementation"), "CHX tactical implementation"
        ),
        "fail_closed_boundary": _require_text(
            value.get("fail_closed_boundary"),
            "CHX tactical fail-closed boundary",
        ),
        "reusable_domains": _require_canonical_string_list(
            value.get("reusable_domains"),
            "CHX tactical reusable_domains",
            nonempty=True,
        ),
        "implementation_anchors": _require_canonical_string_list(
            value.get("implementation_anchors"),
            "CHX tactical implementation_anchors",
            nonempty=True,
        ),
        "bounded_validation_evidence": _require_canonical_string_list(
            value.get("bounded_validation_evidence"),
            "CHX tactical bounded_validation_evidence",
            nonempty=True,
        ),
    }
    return _normalize_unicode(normalized)


def _tactical_repair_semantic(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "issue_id": event["issue_id"],
        "reconnaissance_id": event["reconnaissance_id"],
        **{
            key: event[key]
            for key in (
                "mechanism_id",
                "summary",
                "applicability",
                "implementation",
                "fail_closed_boundary",
                "reusable_domains",
                "implementation_anchors",
                "bounded_validation_evidence",
            )
        },
        "truth_effect": event["truth_effect"],
    }


def _tactical_repair_id(event: dict[str, Any]) -> str:
    return "tactical-repair-" + _sha256(
        _canonical_nfc_bytes(_tactical_repair_semantic(event))
    )


def _validate_coordination_decisions(
    value: Any,
    *,
    included_issue_ids: list[str],
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ValueError("CHX coordination_decisions must be a nonempty list")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    covered: set[str] = set()
    included = set(included_issue_ids)
    for index, item in enumerate(value, 1):
        if not isinstance(item, dict) or set(item) != {
            "decision_id",
            "affected_issue_ids",
            "decision",
            "rationale",
        }:
            raise ValueError(
                f"CHX coordination decision {index} fields are not exact"
            )
        decision_id = item.get("decision_id")
        if not isinstance(decision_id, str) or DECISION_ID_RE.fullmatch(
            decision_id
        ) is None:
            raise ValueError("CHX coordination decision id is invalid")
        if decision_id in seen:
            raise ValueError("CHX coordination decision id is duplicated")
        affected = _require_canonical_string_list(
            item.get("affected_issue_ids"),
            "CHX coordination affected_issue_ids",
            nonempty=True,
        )
        if any(ISSUE_ID_RE.fullmatch(issue_id) is None for issue_id in affected):
            raise ValueError("CHX coordination issue id is invalid")
        if not set(affected).issubset(included):
            raise ValueError("CHX coordination decision escaped included issues")
        normalized.append(
            {
                "decision_id": decision_id,
                "affected_issue_ids": affected,
                "decision": _require_text(
                    item.get("decision"), "CHX coordination decision"
                ),
                "rationale": _require_text(
                    item.get("rationale"), "CHX coordination rationale"
                ),
            }
        )
        seen.add(decision_id)
        covered.update(affected)
    if covered != included:
        raise ValueError("CHX coordination decisions do not cover every issue")
    normalized = sorted(normalized, key=lambda item: item["decision_id"])
    if value != normalized:
        raise ValueError(
            "CHX coordination decisions must be canonical and decision-id sorted"
        )
    return _normalize_unicode(normalized)


def _validate_integrated_repair_input(value: Any) -> dict[str, Any]:
    expected = {
        "included_issue_ids",
        "coordination_decisions",
        "risk_evidence",
        "regression_evidence",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("CHX integrated repair input fields are not exact")
    included = _require_canonical_string_list(
        value.get("included_issue_ids"),
        "CHX integrated included_issue_ids",
        nonempty=True,
    )
    if any(ISSUE_ID_RE.fullmatch(issue_id) is None for issue_id in included):
        raise ValueError("CHX integrated repair issue id is invalid")
    return _normalize_unicode(
        {
            "included_issue_ids": included,
            "coordination_decisions": _validate_coordination_decisions(
                value.get("coordination_decisions"),
                included_issue_ids=included,
            ),
            "risk_evidence": _require_canonical_string_list(
                value.get("risk_evidence"),
                "CHX integrated risk_evidence",
                nonempty=True,
            ),
            "regression_evidence": _require_canonical_string_list(
                value.get("regression_evidence"),
                "CHX integrated regression_evidence",
                nonempty=True,
            ),
        }
    )


def _validate_global_repair_input(value: Any) -> dict[str, Any]:
    """Validate one cross-ledger repair plan without requiring tactical entries.

    Historical task ledgers remain immutable.  This input is the project-wide
    copy-on-write closure record used when several independent task ledgers
    must be revalidated and repaired as one mechanism-level operation.
    """

    expected = {
        "candidate_root",
        "candidate_version",
        "candidate_manifest_sha256",
        "inventory_sha256",
        "covered_issue_snapshot_sha256",
        "included_issue_ids",
        "issue_dispositions",
        "mechanism_groups",
        "risk_evidence",
        "regression_evidence",
        "supersedes_global_repair_id",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("CHX global repair input fields are not exact")
    candidate_root = _require_text(
        value.get("candidate_root"),
        "CHX global repair candidate_root",
        maximum=4_096,
    )
    candidate_path = Path(candidate_root).expanduser()
    if (
        not candidate_path.is_absolute()
        or candidate_path.is_symlink()
        or not candidate_path.is_dir()
        or str(candidate_path.resolve(strict=True)) != candidate_root
    ):
        raise ValueError("CHX global repair candidate_root is unsafe")
    candidate_version = _require_text(
        value.get("candidate_version"),
        "CHX global repair candidate_version",
        maximum=64,
    )
    candidate_manifest_sha256 = value.get("candidate_manifest_sha256")
    if not isinstance(candidate_manifest_sha256, str) or SHA256_RE.fullmatch(
        candidate_manifest_sha256
    ) is None:
        raise ValueError("CHX global repair candidate_manifest_sha256 is invalid")
    inventory_sha256 = value.get("inventory_sha256")
    if not isinstance(inventory_sha256, str) or SHA256_RE.fullmatch(
        inventory_sha256
    ) is None:
        raise ValueError("CHX global repair inventory_sha256 is invalid")
    covered_issue_snapshot_sha256 = value.get(
        "covered_issue_snapshot_sha256"
    )
    if not isinstance(
        covered_issue_snapshot_sha256, str
    ) or SHA256_RE.fullmatch(covered_issue_snapshot_sha256) is None:
        raise ValueError(
            "CHX global repair covered_issue_snapshot_sha256 is invalid"
        )
    included = _canonical_qualified_issue_ids(
        value.get("included_issue_ids"),
        "CHX global repair included_issue_ids",
    )
    if not included:
        raise ValueError("CHX global repair must cover at least one issue")

    dispositions = value.get("issue_dispositions")
    if not isinstance(dispositions, list) or not dispositions:
        raise ValueError("CHX global repair issue_dispositions must be nonempty")
    normalized_dispositions: list[dict[str, Any]] = []
    seen_dispositions: set[str] = set()
    for index, item in enumerate(dispositions, 1):
        if not isinstance(item, dict) or set(item) != {
            "qualified_issue_id",
            "status",
            "basis",
            "reason",
            "evidence",
        }:
            raise ValueError(
                f"CHX global repair issue disposition {index} fields are not exact"
            )
        qualified = item.get("qualified_issue_id")
        if (
            not isinstance(qualified, str)
            or QUALIFIED_ISSUE_ID_RE.fullmatch(qualified) is None
            or qualified in seen_dispositions
        ):
            raise ValueError("CHX global repair issue disposition id is invalid")
        status = item.get("status")
        if status not in DISPOSITION_STATUSES:
            raise ValueError("CHX global repair issue disposition status is invalid")
        basis = item.get("basis")
        if basis not in GLOBAL_REPAIR_BASES:
            raise ValueError("CHX global repair issue disposition basis is invalid")
        if (
            status == "excluded_nonarchitectural"
            and basis != "historical_nonarchitectural"
        ) or (
            status == "resolved" and basis == "historical_nonarchitectural"
        ):
            raise ValueError(
                "CHX global repair disposition basis/status pairing is invalid"
            )
        evidence = _canonical_digest_bound_references(
            item.get("evidence"),
            "CHX global repair issue disposition evidence",
        )
        normalized_dispositions.append(
            {
                "qualified_issue_id": qualified,
                "status": status,
                "basis": basis,
                "reason": _require_text(
                    item.get("reason"),
                    "CHX global repair issue disposition reason",
                ),
                "evidence": evidence,
            }
        )
        seen_dispositions.add(qualified)
    normalized_dispositions.sort(
        key=lambda item: _qualified_issue_sort_key(item["qualified_issue_id"])
    )
    if [item["qualified_issue_id"] for item in normalized_dispositions] != included:
        raise ValueError(
            "CHX global repair dispositions must cover every included issue exactly once"
        )

    groups = value.get("mechanism_groups")
    if not isinstance(groups, list) or not groups:
        raise ValueError("CHX global repair mechanism_groups must be nonempty")
    normalized_groups: list[dict[str, Any]] = []
    group_ids: set[str] = set()
    covered: set[str] = set()
    for index, item in enumerate(groups, 1):
        expected_group = {
            "group_id",
            "issue_ids",
            "summary",
            "implementation_anchors",
            "fail_closed_boundary",
            "evidence",
        }
        if not isinstance(item, dict) or set(item) != expected_group:
            raise ValueError(
                f"CHX global repair mechanism group {index} fields are not exact"
            )
        group_id = item.get("group_id")
        if (
            not isinstance(group_id, str)
            or MECHANISM_ID_RE.fullmatch(group_id) is None
            or group_id in group_ids
        ):
            raise ValueError("CHX global repair mechanism group id is invalid")
        issue_ids = _canonical_qualified_issue_ids(
            item.get("issue_ids"),
            "CHX global repair mechanism group issue_ids",
        )
        if not issue_ids or not set(issue_ids).issubset(set(included)):
            raise ValueError(
                "CHX global repair mechanism group escaped included issue ids"
            )
        if covered.intersection(issue_ids):
            raise ValueError(
                "CHX global repair mechanism groups overlap issue ownership"
            )
        evidence = _canonical_digest_bound_references(
            item.get("evidence"),
            "CHX global repair mechanism group evidence",
        )
        normalized_groups.append(
            {
                "group_id": group_id,
                "issue_ids": issue_ids,
                "summary": _require_text(
                    item.get("summary"),
                    "CHX global repair mechanism group summary",
                ),
                "implementation_anchors": _canonical_digest_bound_references(
                    item.get("implementation_anchors"),
                    "CHX global repair mechanism group implementation_anchors",
                ),
                "fail_closed_boundary": _require_text(
                    item.get("fail_closed_boundary"),
                    "CHX global repair mechanism group fail_closed_boundary",
                ),
                "evidence": evidence,
            }
        )
        group_ids.add(group_id)
        covered.update(issue_ids)
    if covered != set(included):
        raise ValueError(
            "CHX global repair mechanism groups must cover every included issue"
        )
    normalized_groups.sort(key=lambda item: item["group_id"])

    supersedes = value.get("supersedes_global_repair_id")
    if not isinstance(supersedes, str):
        raise ValueError("CHX global repair predecessor must be text")
    if supersedes and GLOBAL_REPAIR_ID_RE.fullmatch(supersedes) is None:
        raise ValueError("CHX global repair predecessor id is invalid")
    return _normalize_unicode(
        {
            "candidate_root": candidate_root,
            "candidate_version": candidate_version,
            "candidate_manifest_sha256": candidate_manifest_sha256,
            "inventory_sha256": inventory_sha256,
            "covered_issue_snapshot_sha256": covered_issue_snapshot_sha256,
            "included_issue_ids": included,
            "issue_dispositions": normalized_dispositions,
            "mechanism_groups": normalized_groups,
            "risk_evidence": _canonical_digest_bound_references(
                value.get("risk_evidence"),
                "CHX global repair risk_evidence",
            ),
            "regression_evidence": _canonical_digest_bound_references(
                value.get("regression_evidence"),
                "CHX global repair regression_evidence",
            ),
            "supersedes_global_repair_id": supersedes,
        }
    )


def _reusable_mechanism_registry(
    tactical_events: Sequence[dict[str, Any]],
    *,
    included_issue_ids: Sequence[str],
) -> dict[str, Any]:
    selected = {
        event["issue_id"]: event
        for event in tactical_events
        if event["issue_id"] in set(included_issue_ids)
    }
    if set(selected) != set(included_issue_ids):
        raise ValueError("CHX integrated repair lacks a tactical issue binding")
    groups: dict[str, dict[str, Any]] = {}
    definition_fields = (
        "summary",
        "applicability",
        "implementation",
        "fail_closed_boundary",
        "reusable_domains",
    )
    for issue_id in sorted(selected):
        event = selected[issue_id]
        mechanism_id = event["mechanism_id"]
        definition = {
            key: event[key]
            for key in definition_fields
        }
        existing = groups.get(mechanism_id)
        if existing is None:
            existing = {
                "mechanism_id": mechanism_id,
                **definition,
                "issue_bindings": [],
            }
            groups[mechanism_id] = existing
        elif any(existing[key] != value for key, value in definition.items()):
            raise ValueError(
                "CHX reusable mechanism id has inconsistent definitions"
            )
        existing["issue_bindings"].append(
            {
                "issue_id": issue_id,
                "tactical_repair_id": event["tactical_repair_id"],
                "reconnaissance_id": event["reconnaissance_id"],
                "implementation_anchors": event["implementation_anchors"],
                "bounded_validation_evidence": event[
                    "bounded_validation_evidence"
                ],
            }
        )
    return {
        "schema_version": 1,
        "contract_revision": REUSABLE_MECHANISM_REGISTRY_REVISION,
        "mechanisms": [groups[key] for key in sorted(groups)],
        "truth_effect": "none",
    }


def _integrated_repair_semantic(event: dict[str, Any]) -> dict[str, Any]:
    return {
        key: event[key]
        for key in (
            "included_issue_ids",
            "tactical_repair_ids",
            "supersedes_integrated_repair_id",
            "reusable_mechanism_registry",
            "reusable_mechanism_registry_sha256",
            "coordination_decisions",
            "risk_evidence",
            "regression_evidence",
            "truth_effect",
        )
    }


def _integrated_repair_id(event: dict[str, Any]) -> str:
    return "integrated-repair-" + _sha256(
        _canonical_nfc_bytes(_integrated_repair_semantic(event))
    )


def _repair_gate(
    *,
    issue_id: str,
    resolved_issue_ids: set[str],
    reconnaissance_events: dict[str, dict[str, Any]],
    tactical_by_issue: dict[str, dict[str, Any]],
    integrated_events: Sequence[dict[str, Any]],
    disposition_evidence: Sequence[str],
) -> None:
    tactical = tactical_by_issue.get(issue_id)
    if tactical is None:
        raise ValueError(
            "resolved CHX issue requires one reusable tactical repair"
        )
    if tactical["reconnaissance_id"] not in reconnaissance_events:
        raise ValueError(
            "resolved CHX issue lacks a prior architecture reconnaissance"
        )
    if not integrated_events:
        raise ValueError("resolved CHX issue requires an integrated repair")
    latest = integrated_events[-1]
    required = resolved_issue_ids | {issue_id}
    if not required.issubset(set(latest["included_issue_ids"])):
        raise ValueError(
            "latest CHX integrated repair does not cover all resolved issues"
        )
    if tactical["tactical_repair_id"] not in latest["tactical_repair_ids"]:
        raise ValueError("CHX integrated repair omitted the issue tactical repair")
    if not set(disposition_evidence).issubset(
        set(latest["regression_evidence"])
    ):
        raise ValueError(
            "CHX disposition evidence is not bound by the integrated repair"
        )


def _skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _skill_version() -> str:
    version = (_skill_root() / "VERSION").read_text(encoding="utf-8").strip()
    return _require_text(version, "skill version", maximum=64)


def _runtime_binding() -> dict[str, Any]:
    return runtime_binding_from_root(_skill_root())


def _validate_task_card_runtime(task_card: Path | str) -> dict[str, Any]:
    path = _resolved_path(task_card)
    if path.is_symlink() or not path.is_file():
        raise ValueError("CHX worker task card is missing, unsafe, or not a file")
    card = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(card, dict):
        raise ValueError("CHX worker task card must contain one object")
    # Runtime identity is optional diagnostic provenance in 0.8.0.  CHX
    # protects workflow findings and task-card content identity, not the
    # location of an installed runtime or a historical archive.  A worker
    # may therefore pick up a valid card after a runtime move or on a host
    # without the predecessor archive.
    semantic = {
        key: value
        for key, value in card.items()
        if key != "task_card_semantic_sha256"
    }
    if card.get("task_card_semantic_sha256") != _sha256(
        _canonical_bytes(semantic)
    ):
        raise ValueError("CHX worker task-card semantic hash mismatch")
    return card


def _resolved_path(path: Path | str) -> Path:
    requested = Path(path).expanduser()
    if requested.is_symlink():
        raise ValueError("CHX paths must not be symlinks")
    return requested.resolve(strict=False)


def _assert_outside_skill(path: Path) -> None:
    root = _skill_root()
    if path == root or root in path.parents:
        raise ValueError("the CHX ledger root must be outside the skill")


def _assert_outside_projects(path: Path, project_roots: Sequence[Path | str]) -> None:
    for project_root_value in project_roots:
        project_root = _resolved_path(project_root_value)
        if path == project_root or project_root in path.parents:
            raise ValueError(
                "the CHX ledger root must be outside every Chalxius project"
            )


def _new_run_id() -> str:
    return _core_new_run_id()


def _validate_run_id(run_id: Any) -> str:
    if not isinstance(run_id, str) or RUN_ID_RE.fullmatch(run_id) is None:
        raise ValueError("run_id is invalid")
    return run_id


def _with_hash(payload: dict[str, Any], previous: str) -> dict[str, Any]:
    return _core_with_hash(payload, previous)


def _write_new_ledger(path: Path, event: dict[str, Any]) -> None:
    _write_new_ledger_events(path, [event])


def _write_new_ledger_events(path: Path, events: list[dict[str, Any]]) -> None:
    _core_write_new_ledger_events(path, events)


def _parse_events(raw: str, *, ledger_path: Path) -> list[dict[str, Any]]:
    if not raw or not raw.endswith("\n"):
        raise ValueError("CHX ledger is empty or lacks a complete final line")
    events: list[dict[str, Any]] = []
    for number, line in enumerate(raw.splitlines(), 1):
        if not line:
            raise ValueError(f"CHX ledger line {number} is blank")
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"CHX ledger line {number} is invalid JSON") from exc
        if not isinstance(event, dict):
            raise ValueError(f"CHX ledger line {number} must be an object")
        events.append(event)
    _validate_events(events, ledger_path=ledger_path)
    return events


def _validate_common_event(
    event: dict[str, Any],
    *,
    expected_previous: str,
    run_id: str,
    schema_version: int,
    contract_revision: str,
) -> None:
    if event.get("schema_version") != schema_version:
        raise ValueError("CHX ledger schema version mismatch")
    if event.get("contract_revision") != contract_revision:
        raise ValueError("CHX ledger contract revision mismatch")
    if event.get("run_id") != run_id:
        raise ValueError("CHX ledger run binding mismatch")
    _require_text(event.get("occurred_at"), "event occurred_at", maximum=64)
    if event.get("previous_event_sha256") != expected_previous:
        raise ValueError("CHX ledger hash-chain predecessor mismatch")
    event_hash = event.get("event_sha256")
    if not isinstance(event_hash, str) or SHA256_RE.fullmatch(event_hash) is None:
        raise ValueError("CHX ledger event hash is invalid")
    if event_hash != _event_sha256(event):
        raise ValueError("CHX ledger event hash mismatch")


def _validate_issue_fields(event: dict[str, Any]) -> None:
    if event.get("causation") not in CAUSATIONS:
        raise ValueError("CHX issue causation is invalid")
    if event.get("mechanism_type") not in MECHANISM_TYPES:
        raise ValueError("CHX issue mechanism_type is invalid")
    for field_name in (
        "classification",
        "mechanism",
        "trigger",
        "observed_effect",
        "mathematical_effect",
        "current_workaround",
        "upgrade_requirement",
    ):
        _require_text(event.get(field_name), f"CHX issue {field_name}")
    _require_string_list(
        event.get("audit_anchors"),
        "CHX issue audit_anchors",
        nonempty=True,
    )


def _validate_issue_relations(
    value: Any,
    *,
    known_issue_ids: set[str],
    current_issue_id: str,
) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise ValueError("CHX issue relations must be a list")
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(value, 1):
        if not isinstance(item, dict) or set(item) != {
            "relation_type",
            "issue_id",
        }:
            raise ValueError(f"CHX issue relation {index} fields are not exact")
        relation_type = item.get("relation_type")
        issue_id = item.get("issue_id")
        if relation_type not in ISSUE_RELATION_TYPES:
            raise ValueError("CHX issue relation type is invalid")
        if not isinstance(issue_id, str) or ISSUE_ID_RE.fullmatch(issue_id) is None:
            raise ValueError("CHX issue relation target is invalid")
        if issue_id == current_issue_id:
            raise ValueError("CHX issue relation must not target itself")
        if issue_id not in known_issue_ids:
            raise ValueError("CHX issue relation targets an unknown issue")
        key = (relation_type, issue_id)
        if key in seen:
            raise ValueError("CHX issue relation is duplicated")
        seen.add(key)
        normalized.append(
            {"relation_type": relation_type, "issue_id": issue_id}
        )
    return sorted(
        normalized, key=lambda item: (item["relation_type"], item["issue_id"])
    )


def _finding_semantic(finding: dict[str, Any]) -> dict[str, Any]:
    return {
        key: finding[key]
        for key in (
            "classification",
            "mechanism_type",
            "mechanism",
            "trigger",
            "observed_effect",
            "mathematical_effect",
            "current_workaround",
            "upgrade_requirement",
            "audit_anchors",
        )
    }


def _finding_id(finding: dict[str, Any]) -> str:
    return "finding-" + _sha256(_canonical_nfc_bytes(_finding_semantic(finding)))


def _validate_finding_fields(event: dict[str, Any]) -> None:
    if event.get("mechanism_type") not in MECHANISM_TYPES:
        raise ValueError("CHX finding mechanism_type is invalid")
    for field_name in (
        "classification",
        "mechanism",
        "trigger",
        "observed_effect",
        "mathematical_effect",
        "current_workaround",
        "upgrade_requirement",
    ):
        _require_text(event.get(field_name), f"CHX finding {field_name}")
    _require_string_list(
        event.get("audit_anchors"),
        "CHX finding audit_anchors",
        nonempty=True,
    )
    finding_id = event.get("finding_id")
    if not isinstance(finding_id, str) or FINDING_ID_RE.fullmatch(finding_id) is None:
        raise ValueError("CHX finding id is invalid")
    if finding_id != _finding_id(event):
        raise ValueError("CHX finding content id mismatch")


def _validate_predecessor_lineage(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("CHX predecessor lineage must be a list")
    normalized: list[dict[str, Any]] = []
    seen_runs: set[str] = set()
    seen_issues: set[str] = set()
    previous_run_id = ""
    for index, entry in enumerate(value, 1):
        expected = {
            "ledger_run_id",
            "ledger_sha256",
            "ledger_contract_revision",
            "predecessor_run_id",
            "observed_issue_ids",
        }
        if not isinstance(entry, dict) or set(entry) != expected:
            raise ValueError(
                f"CHX predecessor lineage entry {index} fields are not exact"
            )
        run_id = _validate_run_id(entry["ledger_run_id"])
        digest = entry["ledger_sha256"]
        revision = entry["ledger_contract_revision"]
        predecessor_run_id = entry["predecessor_run_id"]
        if not isinstance(digest, str) or SHA256_RE.fullmatch(digest) is None:
            raise ValueError("CHX predecessor lineage digest is invalid")
        if revision not in SUPPORTED_CONTRACT_REVISIONS:
            raise ValueError("CHX predecessor lineage contract revision is invalid")
        if predecessor_run_id != previous_run_id:
            raise ValueError("CHX predecessor lineage order is invalid")
        if run_id in seen_runs:
            raise ValueError("CHX predecessor lineage contains a cycle")
        issue_ids = _require_string_list(
            entry["observed_issue_ids"],
            "CHX predecessor lineage observed issue ids",
            nonempty=False,
        )
        if (
            any(ISSUE_ID_RE.fullmatch(item) is None for item in issue_ids)
            or issue_ids
            != sorted(
                set(issue_ids),
                key=lambda item: int(item.removeprefix("CHX-")),
            )
        ):
            raise ValueError("CHX predecessor lineage issue ids are invalid")
        overlap = seen_issues.intersection(issue_ids)
        if overlap:
            raise ValueError("CHX predecessor lineage issue ownership overlaps")
        seen_runs.add(run_id)
        seen_issues.update(issue_ids)
        normalized.append(
            {
                "ledger_run_id": run_id,
                "ledger_sha256": digest,
                "ledger_contract_revision": revision,
                "predecessor_run_id": predecessor_run_id,
                "observed_issue_ids": issue_ids,
            }
        )
        previous_run_id = run_id
    numbers = sorted(int(item.removeprefix("CHX-")) for item in seen_issues)
    if numbers and numbers != list(range(1, numbers[-1] + 1)):
        raise ValueError("CHX predecessor lineage issue ids are not contiguous")
    return normalized


def _validate_events(events: list[dict[str, Any]], *, ledger_path: Path) -> None:
    if not events or events[0].get("event") != "run_started":
        raise ValueError("CHX ledger must begin with run_started")
    start = events[0]
    run_id = _validate_run_id(start.get("run_id"))
    schema_version = start.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        raise ValueError("CHX ledger schema version mismatch")
    contract_revision = start.get("contract_revision")
    if contract_revision not in SUPPORTED_CONTRACT_REVISIONS:
        raise ValueError("CHX ledger contract revision mismatch")
    if ledger_path.stem != run_id:
        raise ValueError("CHX ledger path/run id mismatch")
    legacy_start_keys = {
        "schema_version",
        "contract_revision",
        "event",
        "run_id",
        "task",
        "skill_version",
        "host_task_scope_id",
        "prospective_only",
        "truth_effect",
        "project_effect",
        "occurred_at",
        "previous_event_sha256",
        "event_sha256",
    }
    v3_start_keys = legacy_start_keys | {
        "predecessor_ledger_path",
        "predecessor_ledger_sha256",
        "predecessor_issue_ids",
        "inherited_finding_ids",
    }
    v4_start_keys = v3_start_keys | {"predecessor_lineage"}
    if contract_revision in LINEAGE_CONTRACT_REVISIONS:
        expected_start_keys = v4_start_keys
    elif contract_revision == FINDING_CONTRACT_REVISION:
        expected_start_keys = v3_start_keys
    else:
        expected_start_keys = legacy_start_keys
    if (
        contract_revision == REPAIR_CONTRACT_REVISION
        and "task_card_binding" in start
    ):
        expected_start_keys = expected_start_keys | {"task_card_binding"}
    if set(start) != expected_start_keys:
        raise ValueError("CHX run_started fields are not exact")
    _require_text(start.get("task"), "CHX run task", maximum=2_000)
    _require_text(start.get("skill_version"), "CHX run skill_version", maximum=64)
    if not isinstance(start.get("host_task_scope_id"), str):
        raise ValueError("CHX run host_task_scope_id must be text")
    if (
        start.get("prospective_only") is not True
        or start.get("truth_effect") != "none"
        or start.get("project_effect") != "none"
    ):
        raise ValueError("CHX run authority boundary is invalid")
    task_card_binding = start.get("task_card_binding")
    if task_card_binding is not None:
        if (
            not isinstance(task_card_binding, dict)
            or set(task_card_binding)
            != {
                "round_id",
                "assignment_id",
                "task_card_sha256",
                "task_card_semantic_sha256",
            }
        ):
            raise ValueError("CHX worker task-card binding fields are not exact")
        _require_text(
            task_card_binding.get("round_id"),
            "CHX worker round id",
            maximum=160,
        )
        _require_text(
            task_card_binding.get("assignment_id"),
            "CHX worker assignment id",
            maximum=160,
        )
        digest = _require_text(
            task_card_binding.get("task_card_sha256"),
            "CHX worker task-card hash",
            maximum=64,
        )
        if SHA256_RE.fullmatch(digest) is None:
            raise ValueError("CHX worker task-card hash is invalid")
        semantic_digest = _require_text(
            task_card_binding.get("task_card_semantic_sha256"),
            "CHX worker task-card semantic hash",
            maximum=64,
        )
        if SHA256_RE.fullmatch(semantic_digest) is None:
            raise ValueError("CHX worker task-card semantic hash is invalid")
    predecessor_issue_ids: set[str] = set()
    inherited_finding_ids: set[str] = set()
    if contract_revision in FINDING_CONTRACT_REVISIONS:
        predecessor_path = start["predecessor_ledger_path"]
        predecessor_sha256 = start["predecessor_ledger_sha256"]
        if not isinstance(predecessor_path, str):
            raise ValueError("CHX predecessor ledger path must be text")
        if not isinstance(predecessor_sha256, str):
            raise ValueError("CHX predecessor ledger SHA-256 must be text")
        if bool(predecessor_path) != bool(predecessor_sha256):
            raise ValueError("CHX predecessor path/hash binding is incomplete")
        if predecessor_sha256 and SHA256_RE.fullmatch(predecessor_sha256) is None:
            raise ValueError("CHX predecessor ledger SHA-256 is invalid")
        predecessor_issue_ids = set(
            _require_string_list(
                start["predecessor_issue_ids"],
                "CHX predecessor issue ids",
                nonempty=False,
            )
        )
        if any(ISSUE_ID_RE.fullmatch(item) is None for item in predecessor_issue_ids):
            raise ValueError("CHX predecessor issue id is invalid")
        inherited_finding_ids = set(
            _require_string_list(
                start["inherited_finding_ids"],
                "CHX inherited finding ids",
                nonempty=False,
            )
        )
        if any(FINDING_ID_RE.fullmatch(item) is None for item in inherited_finding_ids):
            raise ValueError("CHX inherited finding id is invalid")
        if contract_revision in LINEAGE_CONTRACT_REVISIONS:
            predecessor_lineage = _validate_predecessor_lineage(
                start["predecessor_lineage"]
            )
            if bool(predecessor_lineage) != bool(predecessor_path):
                raise ValueError("CHX predecessor lineage/path binding is incomplete")
            if predecessor_lineage:
                direct = predecessor_lineage[-1]
                if (
                    direct["ledger_sha256"] != predecessor_sha256
                    or direct["ledger_run_id"] != Path(predecessor_path).stem
                ):
                    raise ValueError("CHX direct predecessor lineage binding drifted")
            lineage_issue_ids = {
                issue_id
                for entry in predecessor_lineage
                for issue_id in entry["observed_issue_ids"]
            }
            if lineage_issue_ids != predecessor_issue_ids:
                raise ValueError("CHX transitive predecessor issue closure drifted")

    expected_previous = ""
    observed: dict[str, dict[str, Any]] = {}
    dispositions: dict[str, dict[str, Any]] = {}
    findings: dict[str, dict[str, Any]] = {}
    reconciliations: dict[str, dict[str, Any]] = {}
    reconnaissance_events: dict[str, dict[str, Any]] = {}
    tactical_by_issue: dict[str, dict[str, Any]] = {}
    integrated_events: list[dict[str, Any]] = []
    closed = False
    for index, event in enumerate(events):
        _validate_common_event(
            event,
            expected_previous=expected_previous,
            run_id=run_id,
            schema_version=schema_version,
            contract_revision=contract_revision,
        )
        expected_previous = event["event_sha256"]
        event_type = event.get("event")
        if index == 0:
            continue
        if closed:
            raise ValueError("CHX ledger contains an event after run_closed")
        if (
            event_type == "finding_observed"
            and contract_revision in FINDING_CONTRACT_REVISIONS
        ):
            finding_keys = {
                "schema_version",
                "contract_revision",
                "event",
                "run_id",
                "finding_id",
                "classification",
                "mechanism_type",
                "mechanism",
                "trigger",
                "observed_effect",
                "mathematical_effect",
                "current_workaround",
                "upgrade_requirement",
                "audit_anchors",
                "inherited_from_predecessor",
                "occurred_at",
                "previous_event_sha256",
                "event_sha256",
            }
            if set(event) != finding_keys:
                raise ValueError("CHX finding_observed fields are not exact")
            _validate_finding_fields(event)
            finding_id = event["finding_id"]
            if finding_id in findings:
                raise ValueError("CHX finding is duplicated")
            inherited = event["inherited_from_predecessor"]
            if not isinstance(inherited, bool):
                raise ValueError("CHX finding inherited marker must be boolean")
            if inherited != (finding_id in inherited_finding_ids):
                raise ValueError("CHX inherited finding binding mismatch")
            findings[finding_id] = event
        elif event_type == "issue_observed":
            legacy_issue_keys = {
                "schema_version",
                "contract_revision",
                "event",
                "run_id",
                "issue_id",
                "classification",
                "causation",
                "mechanism_type",
                "mechanism",
                "trigger",
                "observed_effect",
                "mathematical_effect",
                "current_workaround",
                "upgrade_requirement",
                "audit_anchors",
                "occurred_at",
                "previous_event_sha256",
                "event_sha256",
            }
            v3_issue_keys = legacy_issue_keys | {"finding_id", "relations"}
            issue_keys = (
                v3_issue_keys
                if contract_revision in FINDING_CONTRACT_REVISIONS
                else legacy_issue_keys
            )
            if set(event) != issue_keys:
                raise ValueError("CHX issue_observed fields are not exact")
            issue_id = event.get("issue_id")
            if not isinstance(issue_id, str) or ISSUE_ID_RE.fullmatch(issue_id) is None:
                raise ValueError("CHX issue id is invalid")
            prior_numbers = [
                int(item.split("-")[1]) for item in predecessor_issue_ids
            ]
            first_number = max(prior_numbers, default=0) + 1
            expected_issue_id = f"CHX-{first_number + len(observed):03d}"
            if issue_id != expected_issue_id or issue_id in observed:
                raise ValueError("CHX issue sequence is invalid")
            _validate_issue_fields(event)
            if contract_revision in FINDING_CONTRACT_REVISIONS:
                finding_id = event["finding_id"]
                if finding_id not in findings:
                    raise ValueError("CHX issue lacks an observed finding")
                if any(
                    item.get("finding_id") == finding_id for item in observed.values()
                ):
                    raise ValueError("one CHX finding cannot create multiple issues")
                relations = _validate_issue_relations(
                    event["relations"],
                    known_issue_ids=predecessor_issue_ids | set(observed),
                    current_issue_id=issue_id,
                )
                if event["relations"] != relations:
                    raise ValueError("CHX issue relations are not canonical")
            observed[issue_id] = event
        elif (
            event_type == "finding_reconciled"
            and contract_revision in FINDING_CONTRACT_REVISIONS
        ):
            reconciliation_keys = {
                "schema_version",
                "contract_revision",
                "event",
                "run_id",
                "finding_id",
                "status",
                "reason",
                "issue_id",
                "occurred_at",
                "previous_event_sha256",
                "event_sha256",
            }
            if set(event) != reconciliation_keys:
                raise ValueError("CHX finding_reconciled fields are not exact")
            finding_id = event.get("finding_id")
            if finding_id not in findings:
                raise ValueError("CHX reconciliation targets an unknown finding")
            if finding_id in reconciliations:
                raise ValueError("CHX finding is already reconciled")
            status = event.get("status")
            if status not in FINDING_RECONCILIATIONS:
                raise ValueError("CHX finding reconciliation status is invalid")
            _require_text(event.get("reason"), "CHX finding reconciliation reason")
            issue_id = event.get("issue_id")
            if not isinstance(issue_id, str):
                raise ValueError("CHX finding reconciliation issue_id must be text")
            if status == "excluded_with_reason":
                if issue_id:
                    raise ValueError("excluded CHX finding must not name an issue")
            else:
                if issue_id not in (set(observed) | predecessor_issue_ids):
                    raise ValueError("CHX finding reconciliation issue is unknown")
                if (
                    status == "promoted_to_issue"
                    and observed.get(issue_id, {}).get("finding_id") != finding_id
                ):
                    raise ValueError("CHX finding promotion binding mismatch")
            reconciliations[finding_id] = event
        elif (
            event_type == "architecture_reconnaissance_recorded"
            and contract_revision in REPAIR_CONTRACT_REVISIONS
        ):
            keys = {
                "schema_version",
                "contract_revision",
                "event",
                "run_id",
                "reconnaissance_id",
                "candidate_root",
                "candidate_version",
                "candidate_file_count",
                "inventory_sha256",
                "report_sha256",
                "capability_registry_sha256",
                "behavioral_registry_sha256",
                "scan_errors",
                "scan_warnings",
                "scope",
                "truth_effect",
                "occurred_at",
                "previous_event_sha256",
                "event_sha256",
            }
            if set(event) != keys:
                raise ValueError(
                    "CHX architecture_reconnaissance_recorded fields are not exact"
                )
            reconnaissance_id = event.get("reconnaissance_id")
            if not isinstance(
                reconnaissance_id, str
            ) or RECONNAISSANCE_ID_RE.fullmatch(reconnaissance_id) is None:
                raise ValueError("CHX reconnaissance id is invalid")
            for field in (
                "candidate_root",
                "candidate_version",
            ):
                _require_text(event.get(field), f"CHX reconnaissance {field}")
            if (
                not isinstance(event.get("candidate_file_count"), int)
                or isinstance(event.get("candidate_file_count"), bool)
                or event["candidate_file_count"] < 1
            ):
                raise ValueError("CHX reconnaissance file count is invalid")
            for field in (
                "inventory_sha256",
                "report_sha256",
                "capability_registry_sha256",
                "behavioral_registry_sha256",
            ):
                value = event.get(field)
                if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
                    raise ValueError(f"CHX reconnaissance {field} is invalid")
            _require_canonical_string_list(
                event.get("scan_errors"),
                "CHX reconnaissance scan_errors",
                nonempty=False,
            )
            _require_canonical_string_list(
                event.get("scan_warnings"),
                "CHX reconnaissance scan_warnings",
                nonempty=False,
            )
            if (
                event.get("scope") != "full_candidate_tree"
                or event.get("truth_effect") != "none"
            ):
                raise ValueError("CHX reconnaissance scope or authority is invalid")
            if reconnaissance_id != _reconnaissance_id(event):
                raise ValueError("CHX reconnaissance content id mismatch")
            if reconnaissance_id in reconnaissance_events:
                raise ValueError("CHX reconnaissance receipt is duplicated")
            reconnaissance_events[reconnaissance_id] = event
        elif (
            event_type == "tactical_repair_recorded"
            and contract_revision in REPAIR_CONTRACT_REVISIONS
        ):
            keys = {
                "schema_version",
                "contract_revision",
                "event",
                "run_id",
                "tactical_repair_id",
                "issue_id",
                "reconnaissance_id",
                "mechanism_id",
                "summary",
                "applicability",
                "implementation",
                "fail_closed_boundary",
                "reusable_domains",
                "implementation_anchors",
                "bounded_validation_evidence",
                "truth_effect",
                "occurred_at",
                "previous_event_sha256",
                "event_sha256",
            }
            if set(event) != keys:
                raise ValueError("CHX tactical_repair_recorded fields are not exact")
            issue_id = event.get("issue_id")
            if issue_id not in observed:
                raise ValueError("CHX tactical repair targets an unknown issue")
            if issue_id in dispositions:
                raise ValueError("CHX tactical repair follows an issue disposition")
            if issue_id in tactical_by_issue:
                raise ValueError("CHX issue already has a tactical repair")
            reconnaissance_id = event.get("reconnaissance_id")
            if reconnaissance_id not in reconnaissance_events:
                raise ValueError(
                    "CHX tactical repair lacks a prior architecture reconnaissance"
                )
            repair_input = {
                key: event[key]
                for key in (
                    "mechanism_id",
                    "summary",
                    "applicability",
                    "implementation",
                    "fail_closed_boundary",
                    "reusable_domains",
                    "implementation_anchors",
                    "bounded_validation_evidence",
                )
            }
            if repair_input != _validate_tactical_repair_input(repair_input):
                raise ValueError("CHX tactical repair is not canonical")
            tactical_repair_id = event.get("tactical_repair_id")
            if not isinstance(
                tactical_repair_id, str
            ) or TACTICAL_REPAIR_ID_RE.fullmatch(tactical_repair_id) is None:
                raise ValueError("CHX tactical repair id is invalid")
            if event.get("truth_effect") != "none":
                raise ValueError("CHX tactical repair authority is invalid")
            if tactical_repair_id != _tactical_repair_id(event):
                raise ValueError("CHX tactical repair content id mismatch")
            tactical_by_issue[issue_id] = event
        elif (
            event_type == "integrated_repair_recorded"
            and contract_revision in REPAIR_CONTRACT_REVISIONS
        ):
            keys = {
                "schema_version",
                "contract_revision",
                "event",
                "run_id",
                "integrated_repair_id",
                "included_issue_ids",
                "tactical_repair_ids",
                "supersedes_integrated_repair_id",
                "reusable_mechanism_registry",
                "reusable_mechanism_registry_sha256",
                "coordination_decisions",
                "risk_evidence",
                "regression_evidence",
                "truth_effect",
                "occurred_at",
                "previous_event_sha256",
                "event_sha256",
            }
            if set(event) != keys:
                raise ValueError("CHX integrated_repair_recorded fields are not exact")
            included = _require_canonical_string_list(
                event.get("included_issue_ids"),
                "CHX integrated included_issue_ids",
                nonempty=True,
            )
            if any(issue_id not in observed for issue_id in included):
                raise ValueError("CHX integrated repair targets an unknown issue")
            if any(
                dispositions.get(issue_id, {}).get("status")
                == "excluded_nonarchitectural"
                for issue_id in included
            ):
                raise ValueError("CHX integrated repair includes an excluded issue")
            prior_resolved = {
                issue_id
                for issue_id, disposition in dispositions.items()
                if disposition["status"] == "resolved"
            }
            if not prior_resolved.issubset(set(included)):
                raise ValueError(
                    "CHX integrated repair omitted a previously resolved issue"
                )
            selected_tactical = [
                tactical_by_issue[issue_id]
                for issue_id in included
                if issue_id in tactical_by_issue
            ]
            expected_tactical_ids = sorted(
                event["tactical_repair_id"] for event in selected_tactical
            )
            tactical_ids = _require_canonical_string_list(
                event.get("tactical_repair_ids"),
                "CHX integrated tactical_repair_ids",
                nonempty=True,
            )
            if tactical_ids != expected_tactical_ids:
                raise ValueError("CHX integrated tactical repair closure drifted")
            expected_registry = _reusable_mechanism_registry(
                selected_tactical,
                included_issue_ids=included,
            )
            if event.get("reusable_mechanism_registry") != expected_registry:
                raise ValueError("CHX reusable mechanism registry drifted")
            registry_sha256 = event.get("reusable_mechanism_registry_sha256")
            expected_registry_sha256 = _sha256(
                _canonical_nfc_bytes(expected_registry)
            )
            if registry_sha256 != expected_registry_sha256:
                raise ValueError("CHX reusable mechanism registry hash drifted")
            _validate_coordination_decisions(
                event.get("coordination_decisions"),
                included_issue_ids=included,
            )
            _require_canonical_string_list(
                event.get("risk_evidence"),
                "CHX integrated risk_evidence",
                nonempty=True,
            )
            _require_canonical_string_list(
                event.get("regression_evidence"),
                "CHX integrated regression_evidence",
                nonempty=True,
            )
            supersedes = event.get("supersedes_integrated_repair_id")
            expected_supersedes = (
                integrated_events[-1]["integrated_repair_id"]
                if integrated_events
                else ""
            )
            if supersedes != expected_supersedes:
                raise ValueError("CHX integrated repair predecessor drifted")
            integrated_repair_id = event.get("integrated_repair_id")
            if not isinstance(
                integrated_repair_id, str
            ) or INTEGRATED_REPAIR_ID_RE.fullmatch(integrated_repair_id) is None:
                raise ValueError("CHX integrated repair id is invalid")
            if event.get("truth_effect") != "none":
                raise ValueError("CHX integrated repair authority is invalid")
            if integrated_repair_id != _integrated_repair_id(event):
                raise ValueError("CHX integrated repair content id mismatch")
            if any(
                item["integrated_repair_id"] == integrated_repair_id
                for item in integrated_events
            ):
                raise ValueError("CHX integrated repair is duplicated")
            integrated_events.append(event)
        elif event_type == "issue_disposition":
            disposition_keys = {
                "schema_version",
                "contract_revision",
                "event",
                "run_id",
                "issue_id",
                "status",
                "reason",
                "regression_evidence",
                "occurred_at",
                "previous_event_sha256",
                "event_sha256",
            }
            if set(event) != disposition_keys:
                raise ValueError("CHX issue_disposition fields are not exact")
            issue_id = event.get("issue_id")
            if issue_id not in observed:
                raise ValueError("CHX disposition targets an unknown issue")
            if issue_id in dispositions:
                raise ValueError("CHX issue already has a disposition")
            if event.get("status") not in DISPOSITION_STATUSES:
                raise ValueError("CHX disposition status is invalid")
            _require_text(event.get("reason"), "CHX disposition reason")
            evidence = _require_string_list(
                event.get("regression_evidence"),
                "CHX disposition regression_evidence",
                nonempty=False,
            )
            if event.get("status") == "resolved" and not evidence:
                raise ValueError(
                    "resolved CHX issue requires regression evidence"
                )
            if (
                event.get("status") == "resolved"
                and contract_revision in REPAIR_CONTRACT_REVISIONS
            ):
                _repair_gate(
                    issue_id=issue_id,
                    resolved_issue_ids={
                        candidate
                        for candidate, disposition in dispositions.items()
                        if disposition["status"] == "resolved"
                    },
                    reconnaissance_events=reconnaissance_events,
                    tactical_by_issue=tactical_by_issue,
                    integrated_events=integrated_events,
                    disposition_evidence=evidence,
                )
            dispositions[issue_id] = event
        elif event_type == "run_closed":
            legacy_close_keys = {
                "schema_version",
                "contract_revision",
                "event",
                "run_id",
                "included_issue_ids",
                "excluded_issue_ids",
                "report_required",
                "occurred_at",
                "previous_event_sha256",
                "event_sha256",
            }
            v3_close_keys = legacy_close_keys | {
                "finding_ids",
                "reconciled_finding_ids",
                "architecture_report_semantic_sha256",
            }
            close_keys = (
                v3_close_keys
                if contract_revision in FINDING_CONTRACT_REVISIONS
                else legacy_close_keys
            )
            if set(event) != close_keys:
                raise ValueError("CHX run_closed fields are not exact")
            included = sorted(
                issue_id
                for issue_id in observed
                if dispositions.get(issue_id, {}).get("status")
                != "excluded_nonarchitectural"
            )
            excluded = sorted(set(observed).difference(included))
            if (
                event.get("included_issue_ids") != included
                or event.get("excluded_issue_ids") != excluded
                or event.get("report_required") is not bool(included)
            ):
                raise ValueError("CHX run_closed summary mismatch")
            if contract_revision in FINDING_CONTRACT_REVISIONS:
                unresolved_findings = sorted(set(findings).difference(reconciliations))
                if unresolved_findings:
                    raise ValueError(
                        "CHX run cannot close with unreconciled findings: "
                        + ", ".join(unresolved_findings)
                    )
                if (
                    event.get("finding_ids") != sorted(findings)
                    or event.get("reconciled_finding_ids")
                    != sorted(reconciliations)
                ):
                    raise ValueError("CHX run_closed finding summary mismatch")
                report_semantic = {
                    "run_id": run_id,
                    "predecessor_ledger_sha256": start[
                        "predecessor_ledger_sha256"
                    ],
                    "finding_ids": sorted(findings),
                    "included_issue_ids": included,
                    "excluded_issue_ids": excluded,
                    "reconciliation": {
                        finding_id: {
                            "status": item["status"],
                            "issue_id": item["issue_id"],
                        }
                        for finding_id, item in sorted(reconciliations.items())
                    },
                    "issue_relations": {
                        issue_id: item["relations"]
                        for issue_id, item in sorted(observed.items())
                    },
                }
                if contract_revision in LINEAGE_CONTRACT_REVISIONS:
                    report_semantic["predecessor_lineage"] = start[
                        "predecessor_lineage"
                    ]
                if contract_revision in REPAIR_CONTRACT_REVISIONS:
                    resolved_issue_ids = sorted(
                        issue_id
                        for issue_id, disposition in dispositions.items()
                        if disposition["status"] == "resolved"
                    )
                    if resolved_issue_ids:
                        if not integrated_events or not set(
                            resolved_issue_ids
                        ).issubset(
                            set(integrated_events[-1]["included_issue_ids"])
                        ):
                            raise ValueError(
                                "CHX close requires latest integrated coverage "
                                "of every resolved issue"
                            )
                    report_semantic.update(
                        {
                            "reconnaissance_ids": sorted(
                                reconnaissance_events
                            ),
                            "tactical_repair_ids": sorted(
                                event["tactical_repair_id"]
                                for event in tactical_by_issue.values()
                            ),
                            "integrated_repair_ids": [
                                event["integrated_repair_id"]
                                for event in integrated_events
                            ],
                            "latest_integrated_repair_id": (
                                integrated_events[-1]["integrated_repair_id"]
                                if integrated_events
                                else ""
                            ),
                        }
                    )
                if event.get("architecture_report_semantic_sha256") != _sha256(
                    _canonical_nfc_bytes(report_semantic)
                ):
                    raise ValueError("CHX architecture report semantic hash mismatch")
            closed = True
        else:
            raise ValueError(f"unsupported CHX ledger event: {event_type!r}")
    if (
        contract_revision in FINDING_CONTRACT_REVISIONS
        and not inherited_finding_ids.issubset(findings)
    ):
        raise ValueError("CHX successor ledger omitted inherited findings")


def _status_from_events(
    events: list[dict[str, Any]], *, ledger_path: Path
) -> dict[str, Any]:
    start = events[0]
    issue_events = {
        event["issue_id"]: event
        for event in events
        if event["event"] == "issue_observed"
    }
    dispositions = {
        event["issue_id"]: event
        for event in events
        if event["event"] == "issue_disposition"
    }
    finding_events = {
        event["finding_id"]: event
        for event in events
        if event["event"] == "finding_observed"
    }
    reconciliations = {
        event["finding_id"]: event
        for event in events
        if event["event"] == "finding_reconciled"
    }
    issues: list[dict[str, Any]] = []
    excluded = 0
    for issue_id, event in issue_events.items():
        disposition = dispositions.get(issue_id)
        status = disposition["status"] if disposition else "open"
        if status == "excluded_nonarchitectural":
            excluded += 1
            continue
        issue = {
            key: event[key]
            for key in (
                "issue_id",
                "classification",
                "causation",
                "mechanism_type",
                "mechanism",
                "trigger",
                "observed_effect",
                "mathematical_effect",
                "current_workaround",
                "upgrade_requirement",
                "audit_anchors",
                "occurred_at",
            )
        }
        if "finding_id" in event:
            issue["finding_id"] = event["finding_id"]
            issue["relations"] = event["relations"]
        issue["status"] = status
        if disposition:
            issue["disposition_reason"] = disposition["reason"]
            issue["regression_evidence"] = disposition["regression_evidence"]
        issues.append(issue)
    findings = []
    for finding_id, event in finding_events.items():
        reconciliation = reconciliations.get(finding_id)
        findings.append(
            {
                "finding_id": finding_id,
                "classification": event["classification"],
                "mechanism_type": event["mechanism_type"],
                "mechanism": event["mechanism"],
                "trigger": event["trigger"],
                "observed_effect": event["observed_effect"],
                "mathematical_effect": event["mathematical_effect"],
                "current_workaround": event["current_workaround"],
                "upgrade_requirement": event["upgrade_requirement"],
                "audit_anchors": event["audit_anchors"],
                "inherited_from_predecessor": event[
                    "inherited_from_predecessor"
                ],
                "reconciliation": (
                    {
                        "status": reconciliation["status"],
                        "reason": reconciliation["reason"],
                        "issue_id": reconciliation["issue_id"],
                    }
                    if reconciliation is not None
                    else None
                ),
            }
        )
    status = {
        "schema_version": start["schema_version"],
        "contract_revision": start["contract_revision"],
        "run_id": start["run_id"],
        "skill_version": start["skill_version"],
        "task": start["task"],
        "host_task_scope_id": start["host_task_scope_id"],
        "ledger_path": str(ledger_path),
        "state": "closed" if events[-1]["event"] == "run_closed" else "open",
        "issue_count": len(issues),
        "excluded_issue_count": excluded,
        "report_required": bool(issues),
        "issues": issues,
        "finding_count": len(findings),
        "unreconciled_finding_ids": sorted(
            set(finding_events).difference(reconciliations)
        ),
        "findings": findings,
        "predecessor_ledger_path": start.get("predecessor_ledger_path", ""),
        "predecessor_ledger_sha256": start.get(
            "predecessor_ledger_sha256", ""
        ),
        "predecessor_issue_ids": start.get("predecessor_issue_ids", []),
        "predecessor_lineage": start.get("predecessor_lineage", []),
        "truth_effect": "none",
        "project_effect": "none",
    }
    if start["contract_revision"] in REPAIR_CONTRACT_REVISIONS:
        reconnaissance = [
            {
                key: event[key]
                for key in (
                    "reconnaissance_id",
                    "candidate_root",
                    "candidate_version",
                    "candidate_file_count",
                    "inventory_sha256",
                    "report_sha256",
                    "capability_registry_sha256",
                    "behavioral_registry_sha256",
                    "scan_errors",
                    "scan_warnings",
                    "scope",
                    "truth_effect",
                    "occurred_at",
                )
            }
            for event in events
            if event["event"] == "architecture_reconnaissance_recorded"
        ]
        tactical = [
            {
                key: event[key]
                for key in (
                    "tactical_repair_id",
                    "issue_id",
                    "reconnaissance_id",
                    "mechanism_id",
                    "summary",
                    "applicability",
                    "implementation",
                    "fail_closed_boundary",
                    "reusable_domains",
                    "implementation_anchors",
                    "bounded_validation_evidence",
                    "truth_effect",
                    "occurred_at",
                )
            }
            for event in events
            if event["event"] == "tactical_repair_recorded"
        ]
        integrated = [
            {
                key: event[key]
                for key in (
                    "integrated_repair_id",
                    "included_issue_ids",
                    "tactical_repair_ids",
                    "supersedes_integrated_repair_id",
                    "reusable_mechanism_registry",
                    "reusable_mechanism_registry_sha256",
                    "coordination_decisions",
                    "risk_evidence",
                    "regression_evidence",
                    "truth_effect",
                    "occurred_at",
                )
            }
            for event in events
            if event["event"] == "integrated_repair_recorded"
        ]
        resolved_issue_ids = sorted(
            issue_id
            for issue_id, disposition in dispositions.items()
            if disposition["status"] == "resolved"
        )
        latest_covered = (
            integrated[-1]["included_issue_ids"] if integrated else []
        )
        status.update(
            {
                "architecture_reconnaissance_receipts": reconnaissance,
                "tactical_repairs": tactical,
                "integrated_repairs": integrated,
                "latest_integrated_repair_id": (
                    integrated[-1]["integrated_repair_id"] if integrated else ""
                ),
                "repair_gate": {
                    "resolved_issue_ids": resolved_issue_ids,
                    "latest_covered_issue_ids": latest_covered,
                    "all_resolved_covered": set(resolved_issue_ids).issubset(
                        set(latest_covered)
                    ),
                },
            }
        )
    return status


def _read_locked(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("CHX ledger path is missing, unsafe, or not a file")
    with path.open("r", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
        try:
            events = _parse_events(handle.read(), ledger_path=path)
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return events, _status_from_events(events, ledger_path=path)


def _mutate_locked(
    path: Path,
    builder: Callable[[list[dict[str, Any]]], dict[str, Any] | None],
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("CHX ledger path is missing, unsafe, or not a file")
    with path.open("r+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            events = _parse_events(handle.read(), ledger_path=path)
            payload = builder(events)
            if payload is None:
                return None, _status_from_events(events, ledger_path=path)
            event = _with_hash(payload, events[-1]["event_sha256"])
            candidate = [*events, event]
            _validate_events(candidate, ledger_path=path)
            handle.seek(0, os.SEEK_END)
            handle.write(_canonical_bytes(event).decode("utf-8") + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return event, _status_from_events(candidate, ledger_path=path)


def _mutate_many_locked(
    path: Path,
    builder: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Append an all-or-none group of events under one ledger lock."""

    if path.is_symlink() or not path.is_file():
        raise ValueError("CHX ledger path is missing, unsafe, or not a file")
    with path.open("r+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            events = _parse_events(handle.read(), ledger_path=path)
            payloads = builder(events)
            if not isinstance(payloads, list):
                raise ValueError("CHX grouped mutation must produce an event list")
            if not payloads:
                return [], _status_from_events(events, ledger_path=path)
            appended: list[dict[str, Any]] = []
            previous = events[-1]["event_sha256"]
            for payload in payloads:
                event = _with_hash(payload, previous)
                appended.append(event)
                previous = event["event_sha256"]
            candidate = [*events, *appended]
            _validate_events(candidate, ledger_path=path)
            handle.seek(0, os.SEEK_END)
            for event in appended:
                handle.write(_canonical_bytes(event).decode("utf-8") + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return appended, _status_from_events(candidate, ledger_path=path)


def _collect_closed_ledger_records(
    ledger_path: Path | str,
) -> list[dict[str, Any]]:
    """Read a digest-bound predecessor chain once at successor/publication time."""

    current = _resolved_path(ledger_path)
    newest_first: list[dict[str, Any]] = []
    seen_paths: set[Path] = set()
    seen_runs: set[str] = set()
    expected_digest = ""
    while True:
        if current in seen_paths:
            raise ValueError("CHX predecessor lineage contains a path cycle")
        before = current.read_bytes()
        events, status = _read_locked(current)
        after = current.read_bytes()
        if before != after:
            raise ValueError("CHX predecessor ledger changed during lineage read")
        digest = _sha256(before)
        if expected_digest and digest != expected_digest:
            raise ValueError("CHX predecessor ledger digest binding drifted")
        if status["state"] != "closed":
            raise ValueError("CHX successor lineage requires closed ledgers")
        run_id = status["run_id"]
        if run_id in seen_runs:
            raise ValueError("CHX predecessor lineage contains a run cycle")
        newest_first.append(
            {
                "path": current,
                "ledger_sha256": digest,
                "events": events,
                "status": status,
            }
        )
        seen_paths.add(current)
        seen_runs.add(run_id)
        predecessor_path = status["predecessor_ledger_path"]
        predecessor_digest = status["predecessor_ledger_sha256"]
        if not predecessor_path:
            if predecessor_digest:
                raise ValueError("CHX predecessor path/hash binding is incomplete")
            break
        expected_digest = predecessor_digest
        current = _resolved_path(predecessor_path)

    return list(reversed(newest_first))


def _collect_closed_ledger_lineage(
    ledger_path: Path | str,
) -> list[dict[str, Any]]:
    records = _collect_closed_ledger_records(ledger_path)
    chronological: list[dict[str, Any]] = []
    previous_run_id = ""
    for record in records:
        status = record["status"]
        issue_ids = sorted(
            {
                event["issue_id"]
                for event in record["events"]
                if event["event"] == "issue_observed"
            },
            key=lambda item: int(item.removeprefix("CHX-")),
        )
        chronological.append(
            {
                "ledger_run_id": status["run_id"],
                "ledger_sha256": record["ledger_sha256"],
                "ledger_contract_revision": status["contract_revision"],
                "predecessor_run_id": previous_run_id,
                "observed_issue_ids": issue_ids,
            }
        )
        previous_run_id = status["run_id"]
    return _validate_predecessor_lineage(chronological)


def start_ledger(
    *,
    task: str,
    project_root: Path | str | None = None,
    root: Path | str | None = None,
    run_id: str | None = None,
    host_task_scope_id: str = "",
    project_roots: Sequence[Path | str] = (),
    task_card: Path | str | None = None,
    predecessor_ledger: Path | str | None = None,
    inherited_findings: Sequence[dict[str, Any]] = (),
) -> dict[str, Any]:
    task_card_binding: dict[str, str] | None = None
    project_path: Path | None = None
    if task_card is not None:
        card = _validate_task_card_runtime(task_card)
        task_card_binding = {
            "round_id": _require_text(
                card.get("round_id"), "CHX worker round id", maximum=160
            ),
            "assignment_id": _require_text(
                card.get("assignment_id"),
                "CHX worker assignment id",
                maximum=160,
            ),
            "task_card_sha256": _require_text(
                _sha256(_resolved_path(task_card).read_bytes()),
                "CHX worker task-card hash",
                maximum=64,
            ),
            "task_card_semantic_sha256": _require_text(
                card.get("task_card_semantic_sha256"),
                "CHX worker task-card semantic hash",
                maximum=64,
            ),
        }
        if SHA256_RE.fullmatch(task_card_binding["task_card_sha256"]) is None:
            raise ValueError("CHX worker task-card hash is invalid")
        if (
            SHA256_RE.fullmatch(
                task_card_binding["task_card_semantic_sha256"]
            )
            is None
        ):
            raise ValueError("CHX worker task-card semantic hash is invalid")
    if (project_root is None) == (root is None):
        raise ValueError("exactly one of project_root or root is required")
    if project_root is not None:
        project_path = _resolved_path(project_root)
        _assert_outside_skill(project_path)
        if project_path.exists() and (
            project_path.is_symlink() or not project_path.is_dir()
        ):
            raise ValueError("Chalxius project root is unsafe or not a directory")
        project_path.mkdir(parents=True, exist_ok=True)
        ledger_candidate = project_path / DEFAULT_PROJECT_LEDGER_DIR
        if ledger_candidate.is_symlink():
            raise ValueError("CHX paths must not be symlinks")
        ledger_root = ledger_candidate.resolve(strict=False)
    else:
        assert root is not None
        ledger_root = _resolved_path(root)
        _assert_outside_skill(ledger_root)
        _assert_outside_projects(ledger_root, project_roots)
    if ledger_root.exists() and (ledger_root.is_symlink() or not ledger_root.is_dir()):
        raise ValueError("CHX ledger root is unsafe or not a directory")
    ledger_root.mkdir(parents=True, exist_ok=True)
    run_id = _validate_run_id(run_id or _new_run_id())
    task = _require_text(task, "CHX run task", maximum=2_000)
    if not isinstance(host_task_scope_id, str) or len(host_task_scope_id) > 512:
        raise ValueError("host_task_scope_id must be text with at most 512 code points")
    predecessor_path_text = ""
    predecessor_sha256 = ""
    predecessor_issue_ids: list[str] = []
    predecessor_lineage: list[dict[str, Any]] = []
    if predecessor_ledger is not None:
        if CONTRACT_REVISION not in FINDING_CONTRACT_REVISIONS:
            raise ValueError("only finding-aware CHX ledgers support a predecessor")
        predecessor_path = _resolved_path(predecessor_ledger)
        predecessor_lineage = _collect_closed_ledger_lineage(predecessor_path)
        predecessor_path_text = str(predecessor_path)
        predecessor_sha256 = predecessor_lineage[-1]["ledger_sha256"]
        predecessor_issue_ids = sorted(
            {
                issue_id
                for entry in predecessor_lineage
                for issue_id in entry["observed_issue_ids"]
            },
            key=lambda item: int(item.removeprefix("CHX-")),
        )
    normalized_inherited = [
        _validate_finding_input(item) for item in inherited_findings
    ]
    inherited_ids = sorted({_finding_id(item) for item in normalized_inherited})
    if len(inherited_ids) != len(normalized_inherited):
        raise ValueError("CHX inherited findings must be content-distinct")
    if inherited_ids and not predecessor_sha256:
        raise ValueError("inherited CHX findings require a predecessor ledger")
    path = ledger_root / f"{run_id}.jsonl"
    start_payload = {
            "schema_version": SCHEMA_VERSION,
            "contract_revision": CONTRACT_REVISION,
            "event": "run_started",
            "run_id": run_id,
            "task": task,
            "skill_version": _skill_version(),
            "host_task_scope_id": host_task_scope_id,
            "prospective_only": True,
            "truth_effect": "none",
            "project_effect": "none",
            "occurred_at": _utc_now(),
    }
    if CONTRACT_REVISION in FINDING_CONTRACT_REVISIONS:
        start_payload.update(
            {
                "predecessor_ledger_path": predecessor_path_text,
                "predecessor_ledger_sha256": predecessor_sha256,
                "predecessor_issue_ids": predecessor_issue_ids,
                "inherited_finding_ids": inherited_ids,
            }
        )
        if CONTRACT_REVISION in LINEAGE_CONTRACT_REVISIONS:
            start_payload["predecessor_lineage"] = predecessor_lineage
    elif predecessor_ledger is not None or inherited_findings:
        raise ValueError("legacy CHX ledger revisions do not support successors")
    if task_card_binding is not None:
        start_payload["task_card_binding"] = task_card_binding
    events = [_with_hash(start_payload, "")]
    previous = events[0]["event_sha256"]
    for finding in sorted(normalized_inherited, key=_finding_id):
        payload = _finding_event_payload(
            events[0], finding, inherited_from_predecessor=True
        )
        event = _with_hash(payload, previous)
        events.append(event)
        previous = event["event_sha256"]
    _validate_events(events, ledger_path=path)
    if project_path is None:
        _write_new_ledger_events(path, events)
    else:
        with _global_repair_lock(project_path, exclusive=True):
            _write_new_ledger_events(path, events)
    return ledger_status(path)


def _validate_finding_input(finding: Any) -> dict[str, Any]:
    expected = {
        "classification",
        "mechanism_type",
        "mechanism",
        "trigger",
        "observed_effect",
        "mathematical_effect",
        "current_workaround",
        "upgrade_requirement",
        "audit_anchors",
    }
    if not isinstance(finding, dict) or set(finding) != expected:
        raise ValueError("CHX finding input fields are not exact")
    candidate = {
        **finding,
        "finding_id": "",
    }
    candidate["finding_id"] = _finding_id(candidate)
    _validate_finding_fields(candidate)
    return _normalize_unicode(dict(finding))


def _finding_event_payload(
    start: dict[str, Any],
    finding: dict[str, Any],
    *,
    inherited_from_predecessor: bool,
) -> dict[str, Any]:
    return {
        "schema_version": start["schema_version"],
        "contract_revision": start["contract_revision"],
        "event": "finding_observed",
        "run_id": start["run_id"],
        "finding_id": _finding_id(finding),
        **finding,
        "inherited_from_predecessor": inherited_from_predecessor,
        "occurred_at": _utc_now(),
    }


def _finding_from_issue(issue: dict[str, Any]) -> dict[str, Any]:
    return _validate_finding_input(
        {
            key: value
            for key, value in issue.items()
            if key != "causation"
        }
    )


def _validate_issue_input(issue: Any) -> dict[str, Any]:
    expected = {
        "classification",
        "causation",
        "mechanism_type",
        "mechanism",
        "trigger",
        "observed_effect",
        "mathematical_effect",
        "current_workaround",
        "upgrade_requirement",
        "audit_anchors",
    }
    if not isinstance(issue, dict) or set(issue) != expected:
        raise ValueError("CHX issue input fields are not exact")
    _validate_issue_fields(issue)
    return dict(issue)


def record_finding(
    ledger_path: Path | str,
    finding: dict[str, Any],
) -> dict[str, Any]:
    path = _resolved_path(ledger_path)
    normalized = _validate_finding_input(finding)

    def build(events: list[dict[str, Any]]) -> dict[str, Any]:
        if events[0]["contract_revision"] not in FINDING_CONTRACT_REVISIONS:
            raise ValueError("CHX findings require a finding-aware ledger revision")
        if events[-1]["event"] == "run_closed":
            raise ValueError("CHX ledger is closed")
        finding_id = _finding_id(normalized)
        if any(
            event.get("finding_id") == finding_id
            and event["event"] == "finding_observed"
            for event in events
        ):
            raise ValueError("CHX finding is already recorded")
        return _finding_event_payload(
            events[0], normalized, inherited_from_predecessor=False
        )

    event, _ = _mutate_locked(path, build)
    if event is None:  # pragma: no cover - builder always returns an event
        raise RuntimeError("CHX finding mutation produced no event")
    return event


def reconcile_finding(
    ledger_path: Path | str,
    *,
    finding_id: str,
    status: str,
    reason: str,
    issue_id: str = "",
) -> dict[str, Any]:
    path = _resolved_path(ledger_path)
    if not isinstance(finding_id, str) or FINDING_ID_RE.fullmatch(finding_id) is None:
        raise ValueError("CHX reconciliation finding_id is invalid")
    if status not in FINDING_RECONCILIATIONS:
        raise ValueError("CHX finding reconciliation status is invalid")
    reason = _require_text(reason, "CHX finding reconciliation reason")
    if not isinstance(issue_id, str):
        raise ValueError("CHX finding reconciliation issue_id must be text")

    def build(events: list[dict[str, Any]]) -> dict[str, Any]:
        if events[0]["contract_revision"] not in FINDING_CONTRACT_REVISIONS:
            raise ValueError("CHX findings require a finding-aware ledger revision")
        if events[-1]["event"] == "run_closed":
            raise ValueError("CHX ledger is closed")
        return {
            "schema_version": events[0]["schema_version"],
            "contract_revision": events[0]["contract_revision"],
            "event": "finding_reconciled",
            "run_id": events[0]["run_id"],
            "finding_id": finding_id,
            "status": status,
            "reason": reason,
            "issue_id": issue_id,
            "occurred_at": _utc_now(),
        }

    event, _ = _mutate_locked(path, build)
    if event is None:  # pragma: no cover - builder always returns an event
        raise RuntimeError("CHX reconciliation mutation produced no event")
    return event


def record_issue(
    ledger_path: Path | str,
    issue: dict[str, Any],
    *,
    relations: Sequence[dict[str, str]] = (),
    finding_id: str | None = None,
) -> dict[str, Any]:
    path = _resolved_path(ledger_path)
    normalized = _validate_issue_input(issue)

    _, initial_status = _read_locked(path)
    if initial_status["contract_revision"] in FINDING_CONTRACT_REVISIONS:
        finding = _finding_from_issue(normalized)
        supplied_finding_id = finding_id
        if supplied_finding_id is not None and (
            not isinstance(supplied_finding_id, str)
            or FINDING_ID_RE.fullmatch(supplied_finding_id) is None
        ):
            raise ValueError("CHX issue finding_id is invalid")
        relation_list = list(relations)

        def build_v3(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
            if events[-1]["event"] == "run_closed":
                raise ValueError("CHX ledger is closed")
            starts = events[0]
            known_findings = {
                event["finding_id"]
                for event in events
                if event["event"] == "finding_observed"
            }
            reconciled = {
                event["finding_id"]
                for event in events
                if event["event"] == "finding_reconciled"
            }
            effective_finding_id = supplied_finding_id or _finding_id(finding)
            payloads: list[dict[str, Any]] = []
            if effective_finding_id not in known_findings:
                if supplied_finding_id is not None:
                    raise ValueError("CHX issue targets an unknown finding")
                payloads.append(
                    _finding_event_payload(
                        starts, finding, inherited_from_predecessor=False
                    )
                )
            else:
                existing_finding = next(
                    event
                    for event in events
                    if event["event"] == "finding_observed"
                    and event["finding_id"] == effective_finding_id
                )
                if _finding_semantic(existing_finding) != _finding_semantic(finding):
                    raise ValueError("CHX issue/finding semantic binding mismatch")
            if effective_finding_id in reconciled:
                reconciliation = next(
                    event
                    for event in events
                    if event["event"] == "finding_reconciled"
                    and event["finding_id"] == effective_finding_id
                )
                if reconciliation["status"] == "promoted_to_issue":
                    return []
                raise ValueError("CHX issue finding is already reconciled")
            observed_ids = {
                event["issue_id"]
                for event in events
                if event["event"] == "issue_observed"
            }
            predecessor_ids = set(starts["predecessor_issue_ids"])
            prior_numbers = [
                int(item.split("-")[1])
                for item in predecessor_ids | observed_ids
            ]
            issue_id_value = f"CHX-{max(prior_numbers, default=0) + 1:03d}"
            canonical_relations = _validate_issue_relations(
                relation_list,
                known_issue_ids=predecessor_ids | observed_ids,
                current_issue_id=issue_id_value,
            )
            payloads.append(
                {
                    "schema_version": starts["schema_version"],
                    "contract_revision": starts["contract_revision"],
                    "event": "issue_observed",
                    "run_id": starts["run_id"],
                    "issue_id": issue_id_value,
                    "finding_id": effective_finding_id,
                    **normalized,
                    "relations": canonical_relations,
                    "occurred_at": _utc_now(),
                }
            )
            payloads.append(
                {
                    "schema_version": starts["schema_version"],
                    "contract_revision": starts["contract_revision"],
                    "event": "finding_reconciled",
                    "run_id": starts["run_id"],
                    "finding_id": effective_finding_id,
                    "status": "promoted_to_issue",
                    "reason": "Promoted transactionally into the append-only CHX issue ledger.",
                    "issue_id": issue_id_value,
                    "occurred_at": _utc_now(),
                }
            )
            return payloads

        appended, _ = _mutate_many_locked(path, build_v3)
        if appended:
            return next(
                event for event in appended if event["event"] == "issue_observed"
            )
        events, _ = _read_locked(path)
        effective_finding_id = supplied_finding_id or _finding_id(finding)
        return next(
            event
            for event in events
            if event["event"] == "issue_observed"
            and event["finding_id"] == effective_finding_id
        )

    def build(events: list[dict[str, Any]]) -> dict[str, Any]:
        if events[-1]["event"] == "run_closed":
            raise ValueError("CHX ledger is closed")
        observed_count = sum(
            event["event"] == "issue_observed" for event in events
        )
        return {
            "schema_version": events[0]["schema_version"],
            "contract_revision": events[0]["contract_revision"],
            "event": "issue_observed",
            "run_id": events[0]["run_id"],
            "issue_id": f"CHX-{observed_count + 1:03d}",
            **normalized,
            "occurred_at": _utc_now(),
        }

    event, _ = _mutate_locked(path, build)
    if event is None:  # pragma: no cover - builder always returns an event
        raise RuntimeError("CHX record mutation produced no event")
    return event


def record_architecture_reconnaissance(
    ledger_path: Path | str,
    report: dict[str, Any],
) -> dict[str, Any]:
    path = _resolved_path(ledger_path)
    normalized = _validate_architecture_reconnaissance_report(report)

    def build(events: list[dict[str, Any]]) -> dict[str, Any]:
        if events[0]["contract_revision"] not in REPAIR_CONTRACT_REVISIONS:
            raise ValueError(
                "CHX architecture reconnaissance receipts require revision 5"
            )
        if events[-1]["event"] == "run_closed":
            raise ValueError("CHX ledger is closed")
        if normalized["candidate_root"] != str(_skill_root()) or normalized[
            "candidate_version"
        ] != events[0]["skill_version"]:
            raise ValueError(
                "CHX reconnaissance does not bind this ledger runtime"
            )
        payload = {
            "schema_version": events[0]["schema_version"],
            "contract_revision": events[0]["contract_revision"],
            "event": "architecture_reconnaissance_recorded",
            "run_id": events[0]["run_id"],
            **normalized,
            "scope": "full_candidate_tree",
            "truth_effect": "none",
            "occurred_at": _utc_now(),
        }
        payload["reconnaissance_id"] = _reconnaissance_id(payload)
        if any(
            event.get("reconnaissance_id") == payload["reconnaissance_id"]
            for event in events
        ):
            raise ValueError("CHX reconnaissance receipt is already recorded")
        return payload

    event, _ = _mutate_locked(path, build)
    if event is None:  # pragma: no cover - builder always returns an event
        raise RuntimeError("CHX reconnaissance mutation produced no event")
    return event


def record_tactical_repair(
    ledger_path: Path | str,
    *,
    issue_id: str,
    reconnaissance_id: str,
    repair: dict[str, Any],
) -> dict[str, Any]:
    """Record one repair whose implementation remains inside this project run.

    A repair intended for global Chalxius installation belongs to
    ``record_global_repair`` and must not manufacture this local precursor.
    """
    path = _resolved_path(ledger_path)
    if not isinstance(issue_id, str) or ISSUE_ID_RE.fullmatch(issue_id) is None:
        raise ValueError("CHX tactical repair issue_id is invalid")
    if not isinstance(
        reconnaissance_id, str
    ) or RECONNAISSANCE_ID_RE.fullmatch(reconnaissance_id) is None:
        raise ValueError("CHX tactical repair reconnaissance_id is invalid")
    normalized = _validate_tactical_repair_input(repair)

    def build(events: list[dict[str, Any]]) -> dict[str, Any]:
        if events[0]["contract_revision"] not in REPAIR_CONTRACT_REVISIONS:
            raise ValueError("CHX tactical repairs require revision 5")
        if events[-1]["event"] == "run_closed":
            raise ValueError("CHX ledger is closed")
        payload = {
            "schema_version": events[0]["schema_version"],
            "contract_revision": events[0]["contract_revision"],
            "event": "tactical_repair_recorded",
            "run_id": events[0]["run_id"],
            "issue_id": issue_id,
            "reconnaissance_id": reconnaissance_id,
            **normalized,
            "truth_effect": "none",
            "occurred_at": _utc_now(),
        }
        payload["tactical_repair_id"] = _tactical_repair_id(payload)
        return payload

    event, _ = _mutate_locked(path, build)
    if event is None:  # pragma: no cover - builder always returns an event
        raise RuntimeError("CHX tactical repair mutation produced no event")
    return event


def record_integrated_repair(
    ledger_path: Path | str,
    integration: dict[str, Any],
) -> dict[str, Any]:
    path = _resolved_path(ledger_path)
    normalized = _validate_integrated_repair_input(integration)

    def build(events: list[dict[str, Any]]) -> dict[str, Any]:
        if events[0]["contract_revision"] not in REPAIR_CONTRACT_REVISIONS:
            raise ValueError("CHX integrated repairs require revision 5")
        if events[-1]["event"] == "run_closed":
            raise ValueError("CHX ledger is closed")
        included = normalized["included_issue_ids"]
        tactical_events = [
            event
            for event in events
            if event["event"] == "tactical_repair_recorded"
            and event["issue_id"] in set(included)
        ]
        registry = _reusable_mechanism_registry(
            tactical_events,
            included_issue_ids=included,
        )
        prior_integrated = [
            event
            for event in events
            if event["event"] == "integrated_repair_recorded"
        ]
        payload = {
            "schema_version": events[0]["schema_version"],
            "contract_revision": events[0]["contract_revision"],
            "event": "integrated_repair_recorded",
            "run_id": events[0]["run_id"],
            "included_issue_ids": included,
            "tactical_repair_ids": sorted(
                event["tactical_repair_id"] for event in tactical_events
            ),
            "supersedes_integrated_repair_id": (
                prior_integrated[-1]["integrated_repair_id"]
                if prior_integrated
                else ""
            ),
            "reusable_mechanism_registry": registry,
            "reusable_mechanism_registry_sha256": _sha256(
                _canonical_nfc_bytes(registry)
            ),
            "coordination_decisions": normalized[
                "coordination_decisions"
            ],
            "risk_evidence": normalized["risk_evidence"],
            "regression_evidence": normalized["regression_evidence"],
            "truth_effect": "none",
            "occurred_at": _utc_now(),
        }
        payload["integrated_repair_id"] = _integrated_repair_id(payload)
        return payload

    event, _ = _mutate_locked(path, build)
    if event is None:  # pragma: no cover - builder always returns an event
        raise RuntimeError("CHX integrated repair mutation produced no event")
    return event


def dispose_issue(
    ledger_path: Path | str,
    *,
    issue_id: str,
    disposition: dict[str, Any],
) -> dict[str, Any]:
    path = _resolved_path(ledger_path)
    if not isinstance(issue_id, str) or ISSUE_ID_RE.fullmatch(issue_id) is None:
        raise ValueError("CHX disposition issue_id is invalid")
    expected = {"status", "reason", "regression_evidence"}
    if not isinstance(disposition, dict) or set(disposition) != expected:
        raise ValueError("CHX disposition input fields are not exact")
    disposition_status = disposition.get("status")
    if disposition_status not in DISPOSITION_STATUSES:
        raise ValueError("CHX disposition status is invalid")
    reason = _require_text(disposition.get("reason"), "CHX disposition reason")
    evidence = _require_string_list(
        disposition.get("regression_evidence"),
        "CHX disposition regression_evidence",
        nonempty=False,
    )
    if disposition_status == "resolved" and not evidence:
        raise ValueError("resolved CHX issue requires regression evidence")
    def build(events: list[dict[str, Any]]) -> dict[str, Any]:
        if events[-1]["event"] == "run_closed":
            raise ValueError("CHX ledger is closed")
        known = {
            event["issue_id"]
            for event in events
            if event["event"] == "issue_observed"
        }
        disposed = {
            event["issue_id"]
            for event in events
            if event["event"] == "issue_disposition"
        }
        if issue_id not in known:
            raise ValueError("CHX disposition targets an unknown issue")
        if issue_id in disposed:
            raise ValueError("CHX issue already has a disposition")
        return {
            "schema_version": events[0]["schema_version"],
            "contract_revision": events[0]["contract_revision"],
            "event": "issue_disposition",
            "run_id": events[0]["run_id"],
            "issue_id": issue_id,
            "status": disposition_status,
            "reason": reason,
            "regression_evidence": evidence,
            "occurred_at": _utc_now(),
        }

    event, _ = _mutate_locked(path, build)
    if event is None:  # pragma: no cover - builder always returns an event
        raise RuntimeError("CHX disposition mutation produced no event")
    return event


def _architecture_report_path(ledger_path: Path) -> Path:
    return ledger_path.with_name(ledger_path.stem + ".architecture-report.md")


def render_architecture_report(ledger_path: Path | str) -> str:
    path = _resolved_path(ledger_path)
    events, status = _read_locked(path)
    if status["contract_revision"] not in FINDING_CONTRACT_REVISIONS:
        raise ValueError("derived architecture reports require a finding-aware ledger")
    if status["state"] != "closed":
        raise ValueError("derived architecture reports require a closed CHX ledger")
    close = events[-1]
    projection = {
        "schema_version": 1,
        "contract_revision": "chalxius-chx-derived-architecture-report-1",
        "run_id": status["run_id"],
        "ledger_sha256": _sha256(path.read_bytes()),
        "predecessor_ledger_path": status["predecessor_ledger_path"],
        "predecessor_ledger_sha256": status["predecessor_ledger_sha256"],
        "architecture_report_semantic_sha256": close[
            "architecture_report_semantic_sha256"
        ],
        "finding_count": status["finding_count"],
        "issue_count": status["issue_count"],
        "excluded_issue_count": status["excluded_issue_count"],
        "findings": status["findings"],
        "issues": status["issues"],
        "truth_effect": "none",
        "project_effect": "none",
    }
    # Revision 3 reports predate the transitive-lineage projection.  Their
    # frozen deterministic bytes intentionally contain only the direct
    # predecessor path/hash even though the ledger start event already carried
    # predecessor_issue_ids.  Adding later empty fields would falsely classify
    # valid immutable historical reports as drifted.
    if status["contract_revision"] in LINEAGE_CONTRACT_REVISIONS:
        projection.update(
            {
                "predecessor_issue_ids": status["predecessor_issue_ids"],
                "predecessor_lineage": status["predecessor_lineage"],
            }
        )
    if status["contract_revision"] in REPAIR_CONTRACT_REVISIONS:
        projection.update(
            {
                "architecture_reconnaissance_receipts": status[
                    "architecture_reconnaissance_receipts"
                ],
                "tactical_repairs": status["tactical_repairs"],
                "integrated_repairs": status["integrated_repairs"],
                "latest_integrated_repair_id": status[
                    "latest_integrated_repair_id"
                ],
                "repair_gate": status["repair_gate"],
            }
        )
    lines = [
        f"# CHX architecture report — {status['run_id']}",
        "",
        "This report is a deterministic projection of the append-only CHX ledger.",
        "It has no truth, project, Certification, Gateway, or Fact-admission effect.",
        "",
        f"- Findings: {status['finding_count']}",
        f"- Included issues: {status['issue_count']}",
        f"- Excluded issues: {status['excluded_issue_count']}",
        f"- Ledger SHA-256: `{projection['ledger_sha256']}`",
        "",
        "## Machine projection",
        "",
        "```json",
        json.dumps(projection, ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
    ]
    return "\n".join(lines)


def write_architecture_report(
    ledger_path: Path | str,
    output_path: Path | str | None = None,
) -> dict[str, Any]:
    path = _resolved_path(ledger_path)
    target = (
        _resolved_path(output_path)
        if output_path is not None
        else _architecture_report_path(path)
    )
    if target == path:
        raise ValueError("CHX report path must differ from the ledger path")
    if target.exists() and (target.is_symlink() or not target.is_file()):
        raise ValueError("CHX architecture report path is unsafe")
    raw = render_architecture_report(path).encode("utf-8")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(
        f".{target.name}.tmp-{os.getpid()}-{secrets.token_hex(4)}"
    )
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return {
        "report_path": str(target),
        "report_sha256": _sha256(raw),
        "ledger_path": str(path),
        "ledger_sha256": _sha256(path.read_bytes()),
        "truth_effect": "none",
    }


def verify_architecture_report(
    ledger_path: Path | str,
    report_path: Path | str | None = None,
) -> dict[str, Any]:
    path = _resolved_path(ledger_path)
    target = (
        _resolved_path(report_path)
        if report_path is not None
        else _architecture_report_path(path)
    )
    if target.is_symlink() or not target.is_file():
        raise ValueError("CHX architecture report is missing or unsafe")
    expected = render_architecture_report(path).encode("utf-8")
    observed = target.read_bytes()
    if observed != expected:
        raise ValueError("CHX architecture report drifted from its ledger")
    return {
        "report_path": str(target),
        "report_sha256": _sha256(observed),
        "ledger_path": str(path),
        "ledger_sha256": _sha256(path.read_bytes()),
        "status": "exact",
        "truth_effect": "none",
    }


def close_ledger(ledger_path: Path | str) -> dict[str, Any]:
    path = _resolved_path(ledger_path)

    def build(events: list[dict[str, Any]]) -> dict[str, Any] | None:
        if events[-1]["event"] == "run_closed":
            return None
        observed_ids = {
            event["issue_id"]
            for event in events
            if event["event"] == "issue_observed"
        }
        excluded_ids = {
            event["issue_id"]
            for event in events
            if event["event"] == "issue_disposition"
            and event["status"] == "excluded_nonarchitectural"
        }
        included_ids = observed_ids.difference(excluded_ids)
        payload = {
            "schema_version": events[0]["schema_version"],
            "contract_revision": events[0]["contract_revision"],
            "event": "run_closed",
            "run_id": events[0]["run_id"],
            "included_issue_ids": sorted(included_ids),
            "excluded_issue_ids": sorted(excluded_ids),
            "report_required": bool(included_ids),
            "occurred_at": _utc_now(),
        }
        if events[0]["contract_revision"] in FINDING_CONTRACT_REVISIONS:
            finding_ids = sorted(
                event["finding_id"]
                for event in events
                if event["event"] == "finding_observed"
            )
            reconciliations = {
                event["finding_id"]: event
                for event in events
                if event["event"] == "finding_reconciled"
            }
            unresolved = sorted(set(finding_ids).difference(reconciliations))
            if unresolved:
                raise ValueError(
                    "CHX run cannot close with unreconciled findings: "
                    + ", ".join(unresolved)
                )
            observed = {
                event["issue_id"]: event
                for event in events
                if event["event"] == "issue_observed"
            }
            report_semantic = {
                "run_id": events[0]["run_id"],
                "predecessor_ledger_sha256": events[0][
                    "predecessor_ledger_sha256"
                ],
                "finding_ids": finding_ids,
                "included_issue_ids": sorted(included_ids),
                "excluded_issue_ids": sorted(excluded_ids),
                "reconciliation": {
                    finding_id: {
                        "status": item["status"],
                        "issue_id": item["issue_id"],
                    }
                    for finding_id, item in sorted(reconciliations.items())
                },
                "issue_relations": {
                    issue_id: item["relations"]
                    for issue_id, item in sorted(observed.items())
                },
            }
            if events[0]["contract_revision"] in LINEAGE_CONTRACT_REVISIONS:
                report_semantic["predecessor_lineage"] = events[0][
                    "predecessor_lineage"
                ]
            if events[0]["contract_revision"] in REPAIR_CONTRACT_REVISIONS:
                dispositions = {
                    event["issue_id"]: event
                    for event in events
                    if event["event"] == "issue_disposition"
                }
                resolved_issue_ids = sorted(
                    issue_id
                    for issue_id, disposition in dispositions.items()
                    if disposition["status"] == "resolved"
                )
                reconnaissance_ids = sorted(
                    event["reconnaissance_id"]
                    for event in events
                    if event["event"]
                    == "architecture_reconnaissance_recorded"
                )
                tactical_repair_ids = sorted(
                    event["tactical_repair_id"]
                    for event in events
                    if event["event"] == "tactical_repair_recorded"
                )
                integrated_repair_ids = [
                    event["integrated_repair_id"]
                    for event in events
                    if event["event"] == "integrated_repair_recorded"
                ]
                integrated_events = [
                    event
                    for event in events
                    if event["event"] == "integrated_repair_recorded"
                ]
                if resolved_issue_ids and (
                    not integrated_events
                    or not set(resolved_issue_ids).issubset(
                        set(integrated_events[-1]["included_issue_ids"])
                    )
                ):
                    raise ValueError(
                        "CHX close requires latest integrated coverage of "
                        "every resolved issue"
                    )
                report_semantic.update(
                    {
                        "reconnaissance_ids": reconnaissance_ids,
                        "tactical_repair_ids": tactical_repair_ids,
                        "integrated_repair_ids": integrated_repair_ids,
                        "latest_integrated_repair_id": (
                            integrated_repair_ids[-1]
                            if integrated_repair_ids
                            else ""
                        ),
                    }
                )
            payload.update(
                {
                    "finding_ids": finding_ids,
                    "reconciled_finding_ids": sorted(reconciliations),
                    "architecture_report_semantic_sha256": _sha256(
                        _canonical_nfc_bytes(report_semantic)
                    ),
                }
            )
        return payload

    _, status = _mutate_locked(path, build)
    if status["contract_revision"] in FINDING_CONTRACT_REVISIONS:
        write_architecture_report(path)
        # Return the same verified projection as every later status/read call.
        # Without this refresh, the first close omitted architecture_report
        # while idempotent close/status included it, breaking API equality.
        return ledger_status(path)
    return status


def ledger_status(ledger_path: Path | str) -> dict[str, Any]:
    path = _resolved_path(ledger_path)
    _, status = _read_locked(path)
    if (
        status["contract_revision"] in FINDING_CONTRACT_REVISIONS
        and status["state"] == "closed"
    ):
        status = {
            **status,
            "architecture_report": verify_architecture_report(path),
        }
    return status


def _inventory_semantic_projection(result: dict[str, Any]) -> dict[str, Any]:
    """Return the complete, pre-global-repair inventory projection."""

    return {
        key: result[key]
        for key in (
            "contract_revision",
            "project_root",
            "ledger_root",
            "ledger_count",
            "chain_count",
            "unresolved",
            "report_compatibility_drift",
            "lineage_errors",
            "parallel_issue_free_successors",
            "parallel_closed_successors",
            "ignored_supersedes",
            "active_run_ids",
            "counts",
            "truth_effect",
            "project_effect",
            "ledgers",
            "chains",
        )
    }


def _covered_issue_snapshot_sha256(
    inventory: dict[str, Any],
    included_issue_ids: Sequence[str],
) -> str:
    """Bind each covered issue to the exact immutable ledger that owns it.

    The full inventory hash remains the exact record-time snapshot.  This
    narrower hash lets a valid repair remain applicable when later ledgers are
    appended, while still detecting removal, replacement, or byte drift of any
    ledger that owned an issue covered by the repair.
    """

    included = _canonical_qualified_issue_ids(
        list(included_issue_ids),
        "CHX global repair covered issue snapshot ids",
    )
    ledgers = inventory.get("ledgers")
    if not isinstance(ledgers, list):
        raise ValueError("CHX covered issue snapshot requires a full inventory")
    owners: dict[str, dict[str, str]] = {}
    for ledger in ledgers:
        if not isinstance(ledger, dict):
            raise ValueError("CHX covered issue snapshot ledger is malformed")
        run_id = ledger.get("run_id")
        digest = ledger.get("sha256")
        revision = ledger.get("contract_revision")
        issue_ids = ledger.get("issue_ids")
        if (
            not isinstance(run_id, str)
            or RUN_ID_RE.fullmatch(run_id) is None
            or not isinstance(digest, str)
            or SHA256_RE.fullmatch(digest) is None
            or revision not in SUPPORTED_CONTRACT_REVISIONS
            or not isinstance(issue_ids, list)
        ):
            raise ValueError("CHX covered issue snapshot ledger is malformed")
        for qualified in issue_ids:
            if qualified in owners:
                raise ValueError("CHX covered issue snapshot ownership overlaps")
            owners[qualified] = {
                "qualified_issue_id": qualified,
                "ledger_run_id": run_id,
                "ledger_sha256": digest,
                "ledger_contract_revision": revision,
            }
    if set(owners).intersection(included) != set(included):
        raise ValueError("CHX covered issue snapshot issue is missing")
    projection = {
        "contract_revision": "chalxius-chx-covered-issue-snapshot-1",
        "issues": [owners[qualified] for qualified in included],
    }
    return _sha256(_canonical_nfc_bytes(projection))


def _global_repair_dir(project_root: Path | str) -> Path:
    project = _resolved_path(project_root)
    ledger_root = project / DEFAULT_PROJECT_LEDGER_DIR
    if ledger_root.is_symlink():
        raise ValueError("CHX global repair ledger root must not be a symlink")
    return ledger_root / "global-repairs"


@contextmanager
def _global_repair_lock(
    project_root: Path | str,
    *,
    exclusive: bool,
) -> Iterator[None]:
    """Lock the existing CHX ledger directory without creating project state."""

    project = _resolved_path(project_root)
    ledger_root = project / DEFAULT_PROJECT_LEDGER_DIR
    if ledger_root.is_symlink() or not ledger_root.is_dir():
        raise ValueError("CHX global repair ledger root is missing or unsafe")
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = -1
    try:
        descriptor = os.open(ledger_root, flags)
        if not os.path.samestat(os.fstat(descriptor), ledger_root.stat()):
            raise ValueError("CHX global repair ledger root changed before lock")
        fcntl.flock(
            descriptor,
            fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH,
        )
        yield
    finally:
        if descriptor >= 0:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)


def _candidate_manifest_sha256(candidate_root: Path | str) -> str:
    root = _resolved_path(candidate_root)
    manifest = root / "MANIFEST.sha256"
    if manifest.is_symlink() or not manifest.is_file():
        raise ValueError("CHX global repair candidate manifest is missing or unsafe")
    return _sha256(manifest.read_bytes())


def _validate_global_repair_candidate(
    candidate_root: Path | str,
    *,
    candidate_version: str,
    candidate_manifest_sha256: str,
) -> dict[str, Any]:
    """Validate the exact candidate tree, not only its manifest identity file."""

    root = _resolved_path(candidate_root)
    binding = runtime_binding_from_root(root)
    if binding["skill_root"] != str(root):
        raise ValueError("CHX global repair candidate root binding drifted")
    if binding["skill_version"] != candidate_version:
        raise ValueError("CHX global repair candidate version is stale")
    if binding["manifest_file_sha256"] != candidate_manifest_sha256:
        raise ValueError("CHX global repair candidate manifest is stale")
    return validate_bound_runtime_at(
        root,
        binding,
        verify_manifest_tree=True,
        require_exact_file_set=True,
    )


def _require_global_repair_inventory_integrity(result: dict[str, Any]) -> None:
    if result["lineage_errors"]:
        raise ValueError("CHX global repair inventory has lineage errors")
    if result["report_compatibility_drift"]:
        raise ValueError("CHX global repair inventory has report drift")


def _validate_global_repair_record(
    record: Any,
    *,
    path: Path,
    project_root: Path,
) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError("CHX global repair record must be one object")
    expected = {
        "schema_version",
        "contract_revision",
        "event",
        "global_repair_id",
        "project_root",
        "candidate_root",
        "candidate_version",
        "candidate_manifest_sha256",
        "inventory_sha256",
        "covered_issue_snapshot_sha256",
        "included_issue_ids",
        "issue_dispositions",
        "mechanism_groups",
        "risk_evidence",
        "regression_evidence",
        "supersedes_global_repair_id",
        "truth_effect",
        "project_effect",
        "created_at",
        "record_sha256",
    }
    if set(record) != expected:
        raise ValueError("CHX global repair record fields are not exact")
    if (
        record["schema_version"] != 1
        or record["contract_revision"] != GLOBAL_REPAIR_CONTRACT_REVISION
        or record["event"] != "global_integrated_repair"
        or record["truth_effect"] != "none"
        or record["project_effect"] != "none"
    ):
        raise ValueError("CHX global repair record contract or authority is invalid")
    canonical_project = str(project_root.resolve(strict=True))
    if record["project_root"] != canonical_project:
        raise ValueError("CHX global repair project binding drifted")
    normalized = _validate_global_repair_input(
        {
            key: record[key]
            for key in (
                "candidate_root",
                "candidate_version",
                "candidate_manifest_sha256",
                "inventory_sha256",
                "covered_issue_snapshot_sha256",
                "included_issue_ids",
                "issue_dispositions",
                "mechanism_groups",
                "risk_evidence",
                "regression_evidence",
                "supersedes_global_repair_id",
            )
        }
    )
    if record["global_repair_id"] != _global_repair_id(record):
        raise ValueError("CHX global repair id mismatch")
    if path.stem != record["global_repair_id"]:
        raise ValueError("CHX global repair path/id mismatch")
    created_at = _require_text(
        record["created_at"],
        "CHX global repair created_at",
        maximum=64,
    )
    _parse_utc_timestamp(created_at, label="CHX global repair created_at")
    if record["record_sha256"] != _sha256(
        _canonical_nfc_bytes(
            {key: value for key, value in record.items() if key != "record_sha256"}
        )
    ):
        raise ValueError("CHX global repair record hash mismatch")
    return {**record, **normalized}


def _collect_global_repair_records(
    project_root: Path | str,
) -> tuple[list[dict[str, Any]], list[str]]:
    project = _resolved_path(project_root)
    directory = _global_repair_dir(project)
    if directory.is_symlink():
        raise ValueError("CHX global repair directory is unsafe")
    if not directory.exists():
        return [], []
    if not directory.is_dir():
        raise ValueError("CHX global repair directory is unsafe")
    records: list[dict[str, Any]] = []
    ids: set[str] = set()
    for path in sorted(directory.iterdir(), key=lambda item: item.name):
        if path.suffix != ".json":
            raise ValueError("CHX global repair directory contains an unexpected entry")
        if path.is_symlink() or not path.is_file():
            raise ValueError("CHX global repair entry is unsafe")
        record = _validate_global_repair_record(
            json.loads(path.read_text(encoding="utf-8")),
            path=path,
            project_root=project,
        )
        if record["global_repair_id"] in ids:
            raise ValueError("CHX global repair id is duplicated")
        ids.add(record["global_repair_id"])
        records.append(record)
    by_id = {record["global_repair_id"]: record for record in records}
    for record in records:
        predecessor = record["supersedes_global_repair_id"]
        if predecessor and predecessor not in by_id:
            raise ValueError("CHX global repair predecessor is missing")
    terminals = [
        record
        for record in records
        if not any(
            other["supersedes_global_repair_id"] == record["global_repair_id"]
            for other in records
        )
    ]
    if len(terminals) > 1:
        raise ValueError("CHX global repair lineage has multiple terminals")
    if not terminals:
        return records, []
    terminal = terminals[0]
    chain: list[str] = []
    seen: set[str] = set()
    current: dict[str, Any] | None = terminal
    while current is not None:
        identifier = current["global_repair_id"]
        if identifier in seen:
            raise ValueError("CHX global repair lineage contains a cycle")
        seen.add(identifier)
        chain.append(identifier)
        predecessor = current["supersedes_global_repair_id"]
        current = by_id.get(predecessor) if predecessor else None
    if len(seen) != len(records):
        raise ValueError("CHX global repair lineage contains an orphan branch")
    return records, list(reversed(chain))


def _apply_global_repair_projection(
    result: dict[str, Any],
    *,
    project_root: Path,
) -> dict[str, Any]:
    records, chain = _collect_global_repair_records(project_root)
    projection: dict[str, Any] = {
        "status": "absent",
        "global_repair_id": "",
        "covered_issue_count": 0,
        "uncovered_issue_count": 0,
        "inventory_sha256": "",
        "covered_issue_snapshot_sha256": "",
        "candidate_version": "",
        "candidate_manifest_sha256": "",
        "truth_effect": "none",
        "project_effect": "none",
    }
    observed_ids = {
        issue_id
        for ledger in result.get("ledgers", [])
        for issue_id in ledger.get("issue_ids", [])
    }
    if not records:
        projection["uncovered_issue_count"] = len(observed_ids)
        result["global_repair"] = projection
        return result
    latest = next(
        record
        for record in records
        if record["global_repair_id"] == chain[-1]
    )
    projection.update(
        {
            "global_repair_id": latest["global_repair_id"],
            "covered_issue_count": len(latest["included_issue_ids"]),
            "inventory_sha256": latest["inventory_sha256"],
            "covered_issue_snapshot_sha256": latest[
                "covered_issue_snapshot_sha256"
            ],
            "candidate_version": latest["candidate_version"],
            "candidate_manifest_sha256": latest["candidate_manifest_sha256"],
        }
    )
    covered_ids = set(latest["included_issue_ids"])
    projection["uncovered_issue_count"] = (
        len(observed_ids.difference(covered_ids))
        if covered_ids.issubset(observed_ids)
        else len(observed_ids)
    )
    candidate_current = False
    if latest["candidate_root"] == str(_skill_root()):
        try:
            _validate_global_repair_candidate(
                latest["candidate_root"],
                candidate_version=latest["candidate_version"],
                candidate_manifest_sha256=latest[
                    "candidate_manifest_sha256"
                ],
            )
            _verify_global_repair_references(latest, project_root=project_root)
        except (OSError, ValueError):
            pass
        else:
            candidate_current = True
    if not candidate_current:
        projection["status"] = "stale"
        result["global_repair"] = projection
        return result
    if result["lineage_errors"] or result["report_compatibility_drift"]:
        projection["status"] = "stale"
        result["global_repair"] = projection
        return result
    all_rows = [
        *result["unresolved"],
    ]
    dispositions = {
        item["qualified_issue_id"]: item
        for item in latest["issue_dispositions"]
    }
    if not covered_ids.issubset(observed_ids):
        projection["status"] = "stale"
        result["global_repair"] = projection
        return result
    if set(dispositions) != covered_ids:
        projection["status"] = "stale"
        result["global_repair"] = projection
        return result
    try:
        current_covered_snapshot = _covered_issue_snapshot_sha256(
            result,
            latest["included_issue_ids"],
        )
    except ValueError:
        projection["status"] = "stale"
        result["global_repair"] = projection
        return result
    if current_covered_snapshot != latest["covered_issue_snapshot_sha256"]:
        projection["status"] = "stale"
        result["global_repair"] = projection
        return result
    for row in all_rows:
        disposition = dispositions.get(row["qualified_issue_id"])
        if disposition is None:
            continue
        if disposition["status"] == "resolved":
            row["resolution"] = "resolved_by_global_repair"
        elif disposition["status"] == "excluded_nonarchitectural":
            row["resolution"] = "excluded_nonarchitectural"
    result["unresolved"] = [
        row for row in all_rows if row["resolution"].startswith("open_")
    ]
    for chain_row in result.get("chains", []):
        chain_row["unresolved_issue_ids"] = [
            row["qualified_issue_id"]
            for row in all_rows
            if row["qualified_issue_id"] in set(chain_row["unresolved_issue_ids"])
            and row["resolution"].startswith("open_")
        ]
    result["counts"]["unresolved_issues"] = len(result["unresolved"])
    result["counts"]["orphan_open_issues"] = sum(
        row["resolution"] == "open_orphan" for row in result["unresolved"]
    )
    result["counts"]["active_open_issues"] = sum(
        row["resolution"] == "open_active" for row in result["unresolved"]
    )
    result["counts"]["successor_pending_issues"] = sum(
        row["resolution"] == "open_successor_pending"
        for row in result["unresolved"]
    )
    resolved_count = sum(
        disposition["status"] == "resolved"
        for disposition in dispositions.values()
    )
    excluded_count = sum(
        disposition["status"] == "excluded_nonarchitectural"
        for disposition in dispositions.values()
    )
    result["counts"]["global_repaired_issues"] = resolved_count
    result["counts"]["global_resolved_issues"] = resolved_count
    result["counts"]["global_excluded_nonarchitectural_issues"] = (
        excluded_count
    )
    result["counts"]["global_disposed_issues"] = (
        resolved_count + excluded_count
    )
    projection["status"] = "current"
    result["global_repair"] = projection
    return result


def _ledger_disposition_dir(project_root: Path | str) -> Path:
    project = _resolved_path(project_root)
    return project / DEFAULT_PROJECT_LEDGER_DIR / LEDGER_DISPOSITION_DIR


def _safe_project_relpath(value: Any, label: str) -> str:
    text = _require_text(value, label)
    pure = PurePosixPath(text)
    if (
        pure.is_absolute()
        or "\\" in text
        or any(part in {"", ".", ".."} for part in pure.parts)
        or str(pure) != text
    ):
        raise ValueError(f"{label} is unsafe")
    return text


def _validate_ledger_disposition_record(
    value: Any,
    *,
    path: Path,
    project_root: Path,
) -> dict[str, Any]:
    expected = {
        "contract_revision",
        "target_run_id",
        "target_ledger_relpath",
        "target_ledger_sha256",
        "status",
        "reason",
        "successor",
        "truth_effect",
        "project_effect",
        "ledger_disposition_id",
        "created_at",
        "record_sha256",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("CHX ledger disposition fields are not exact")
    if value["contract_revision"] != LEDGER_DISPOSITION_CONTRACT_REVISION:
        raise ValueError("CHX ledger disposition revision is invalid")
    target_run_id = value["target_run_id"]
    if not isinstance(target_run_id, str) or RUN_ID_RE.fullmatch(target_run_id) is None:
        raise ValueError("CHX ledger disposition target run id is invalid")
    target_relpath = _safe_project_relpath(
        value["target_ledger_relpath"],
        "CHX ledger disposition target path",
    )
    if not target_relpath.startswith(f"{DEFAULT_PROJECT_LEDGER_DIR}/"):
        raise ValueError("CHX ledger disposition target is outside the ledger root")
    if (
        not isinstance(value["target_ledger_sha256"], str)
        or SHA256_RE.fullmatch(value["target_ledger_sha256"]) is None
    ):
        raise ValueError("CHX ledger disposition target hash is invalid")
    status = value["status"]
    if status not in LEDGER_ADMINISTRATIVE_STATUSES:
        raise ValueError("CHX ledger administrative status is invalid")
    _require_text(value["reason"], "CHX ledger disposition reason")
    successor = value["successor"]
    if status == "superseded":
        if not isinstance(successor, dict) or set(successor) != {
            "run_id",
            "ledger_relpath",
            "ledger_sha256",
        }:
            raise ValueError("superseded CHX ledger requires an exact successor")
        if (
            not isinstance(successor["run_id"], str)
            or RUN_ID_RE.fullmatch(successor["run_id"]) is None
            or successor["run_id"] == target_run_id
        ):
            raise ValueError("CHX ledger successor run id is invalid")
        successor_path = _safe_project_relpath(
            successor["ledger_relpath"],
            "CHX ledger successor path",
        )
        if not successor_path.startswith(f"{DEFAULT_PROJECT_LEDGER_DIR}/"):
            raise ValueError("CHX ledger successor is outside the ledger root")
        if (
            not isinstance(successor["ledger_sha256"], str)
            or SHA256_RE.fullmatch(successor["ledger_sha256"]) is None
        ):
            raise ValueError("CHX ledger successor hash is invalid")
    elif successor is not None:
        raise ValueError("non-superseded CHX ledger disposition has a successor")
    if value["truth_effect"] != "none" or value["project_effect"] != "none":
        raise ValueError("CHX ledger disposition must remain administrative")
    disposition_id = value["ledger_disposition_id"]
    if (
        not isinstance(disposition_id, str)
        or LEDGER_DISPOSITION_ID_RE.fullmatch(disposition_id) is None
        or path.stem != disposition_id
    ):
        raise ValueError("CHX ledger disposition id/path is invalid")
    _parse_utc_timestamp(
        value["created_at"],
        label="CHX ledger disposition created_at",
    )
    semantic = {
        key: value[key]
        for key in expected.difference(
            {"ledger_disposition_id", "created_at", "record_sha256"}
        )
    }
    if disposition_id != f"ledger-disposition-{_sha256(_canonical_nfc_bytes(semantic))}":
        raise ValueError("CHX ledger disposition content id drifted")
    record_without_hash = {
        key: value[key] for key in expected.difference({"record_sha256"})
    }
    if value["record_sha256"] != _sha256(
        _canonical_nfc_bytes(record_without_hash)
    ):
        raise ValueError("CHX ledger disposition record hash drifted")
    return value


def _project_ledger_bindings(project_root: Path) -> dict[str, dict[str, Any]]:
    ledger_root = project_root / DEFAULT_PROJECT_LEDGER_DIR
    bindings: dict[str, dict[str, Any]] = {}
    for path in sorted(ledger_root.iterdir(), key=lambda item: item.name):
        if path.suffix != ".jsonl":
            continue
        if path.is_symlink() or not path.is_file():
            raise ValueError("CHX ledger root contains an unsafe ledger")
        raw = path.read_bytes()
        _events, status = _read_locked(path)
        run_id = status["run_id"]
        if run_id in bindings:
            raise ValueError("CHX project contains a duplicate ledger run id")
        bindings[run_id] = {
            "run_id": run_id,
            "path": path,
            "relpath": path.relative_to(project_root).as_posix(),
            "sha256": _sha256(raw),
            "state": status["state"],
        }
    return bindings


def _collect_ledger_dispositions(
    project_root: Path,
    bindings: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    directory = _ledger_disposition_dir(project_root)
    if directory.is_symlink():
        raise ValueError("CHX ledger disposition directory is unsafe")
    if not directory.exists():
        return {}, []
    if not directory.is_dir():
        raise ValueError("CHX ledger disposition directory is unsafe")
    valid: dict[str, dict[str, Any]] = {}
    drift: list[dict[str, str]] = []
    for path in sorted(directory.iterdir(), key=lambda item: item.name):
        if path.suffix != ".json" or path.is_symlink() or not path.is_file():
            raise ValueError("CHX ledger disposition directory contains an unsafe entry")
        record = _validate_ledger_disposition_record(
            json.loads(path.read_text(encoding="utf-8")),
            path=path,
            project_root=project_root,
        )
        target = bindings.get(record["target_run_id"])
        error = ""
        if target is None:
            error = "target_run_missing"
        elif target["relpath"] != record["target_ledger_relpath"]:
            error = "target_path_drifted"
        elif target["sha256"] != record["target_ledger_sha256"]:
            error = "target_hash_drifted"
        successor = record["successor"]
        if not error and successor is not None:
            successor_binding = bindings.get(successor["run_id"])
            if successor_binding is None:
                error = "successor_run_missing"
            elif successor_binding["relpath"] != successor["ledger_relpath"]:
                error = "successor_path_drifted"
            elif successor_binding["sha256"] != successor["ledger_sha256"]:
                error = "successor_hash_drifted"
        if error:
            drift.append(
                {
                    "ledger_disposition_id": record["ledger_disposition_id"],
                    "target_run_id": record["target_run_id"],
                    "error": error,
                }
            )
            continue
        previous = valid.get(record["target_run_id"])
        if previous is not None and previous != record:
            raise ValueError("CHX ledger has conflicting administrative dispositions")
        valid[record["target_run_id"]] = record
    return valid, drift


def record_ledger_disposition(
    project_root: Path | str,
    *,
    run_id: str,
    status: str,
    reason: str,
    successor_run_id: str | None = None,
) -> dict[str, Any]:
    """Append one administrative COW terminal marker for a historical run."""

    project = _resolved_path(project_root)
    if project.is_symlink() or not project.is_dir():
        raise ValueError("CHX ledger disposition project root is unsafe")
    if not isinstance(run_id, str) or RUN_ID_RE.fullmatch(run_id) is None:
        raise ValueError("CHX ledger disposition run id is invalid")
    if status not in LEDGER_ADMINISTRATIVE_STATUSES:
        raise ValueError("CHX ledger administrative status is invalid")
    reason = _require_text(reason, "CHX ledger disposition reason")
    if status == "superseded":
        if (
            not isinstance(successor_run_id, str)
            or RUN_ID_RE.fullmatch(successor_run_id) is None
            or successor_run_id == run_id
        ):
            raise ValueError("superseded CHX ledger requires a distinct successor run")
    elif successor_run_id is not None:
        raise ValueError("successor run is valid only for superseded disposition")
    with _global_repair_lock(project, exclusive=True):
        bindings = _project_ledger_bindings(project)
        target = bindings.get(run_id)
        if target is None:
            raise ValueError("unknown CHX ledger run id")
        if target["state"] != "open":
            raise ValueError("closed CHX ledger does not need administrative disposition")
        successor = None
        if successor_run_id is not None:
            successor_binding = bindings.get(successor_run_id)
            if successor_binding is None:
                raise ValueError("unknown CHX successor run id")
            successor = {
                "run_id": successor_run_id,
                "ledger_relpath": successor_binding["relpath"],
                "ledger_sha256": successor_binding["sha256"],
            }
        semantic = {
            "contract_revision": LEDGER_DISPOSITION_CONTRACT_REVISION,
            "target_run_id": run_id,
            "target_ledger_relpath": target["relpath"],
            "target_ledger_sha256": target["sha256"],
            "status": status,
            "reason": reason,
            "successor": successor,
            "truth_effect": "none",
            "project_effect": "none",
        }
        disposition_id = "ledger-disposition-" + _sha256(
            _canonical_nfc_bytes(semantic)
        )
        record_without_hash = {
            **semantic,
            "ledger_disposition_id": disposition_id,
            "created_at": _utc_now(),
        }
        record = {
            **record_without_hash,
            "record_sha256": _sha256(
                _canonical_nfc_bytes(record_without_hash)
            ),
        }
        directory = _ledger_disposition_dir(project)
        path = directory / f"{disposition_id}.json"
        existing, _drift = _collect_ledger_dispositions(project, bindings)
        previous = existing.get(run_id)
        if previous is not None:
            if previous["ledger_disposition_id"] == disposition_id:
                return {
                    "ledger_disposition_id": disposition_id,
                    "record_path": str(path),
                    "record_sha256": previous["record_sha256"],
                    "status": "already_recorded",
                    "truth_effect": "none",
                    "project_effect": "none",
                }
            raise ValueError("CHX ledger already has a different administrative disposition")
        if directory.is_symlink():
            raise ValueError("CHX ledger disposition directory is unsafe")
        directory.mkdir(parents=True, exist_ok=True)
        temporary = directory / (
            f".{path.name}.tmp-{os.getpid()}-{secrets.token_hex(4)}"
        )
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        try:
            with os.fdopen(descriptor, "wb", closefd=True) as handle:
                handle.write(_canonical_bytes(record))
                handle.write(b"\n")
                handle.flush()
                os.fsync(handle.fileno())
            _validate_ledger_disposition_record(
                record,
                path=path,
                project_root=project,
            )
            os.replace(temporary, path)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    return {
        "ledger_disposition_id": disposition_id,
        "record_path": str(path),
        "record_sha256": record["record_sha256"],
        "status": "recorded",
        "truth_effect": "none",
        "project_effect": "none",
    }


def _bounded_rows(rows: list[Any], *, limit: int = 8) -> dict[str, Any]:
    return {
        "count": len(rows),
        "sha256": _sha256(_canonical_nfc_bytes(rows)),
        "truncated": len(rows) > limit,
        "items": rows[:limit],
    }


def _ledger_activity_projection(
    *,
    project_root: Path,
    records: dict[str, dict[str, Any]],
    current_run_ids: Sequence[str],
    full: bool,
) -> dict[str, Any]:
    current = []
    seen_current: set[str] = set()
    for value in current_run_ids:
        if not isinstance(value, str) or RUN_ID_RE.fullmatch(value) is None:
            raise ValueError("CHX inventory current run id is invalid")
        if value in seen_current:
            raise ValueError("CHX inventory current run ids must be unique")
        seen_current.add(value)
        record = records.get(value)
        if record is None:
            raise ValueError("CHX inventory current run id is unknown")
        if record["state"] != "open":
            raise ValueError("CHX inventory current run id is already closed")
        current.append(value)
    bindings = {
        run_id: {
            "run_id": run_id,
            "path": Path(record["path"]),
            "relpath": Path(record["path"])
            .relative_to(project_root)
            .as_posix(),
            "sha256": record["sha256"],
            "state": record["state"],
        }
        for run_id, record in records.items()
    }
    dispositions, drift = _collect_ledger_dispositions(
        project_root,
        bindings,
    )
    categories: dict[str, list[dict[str, Any]]] = {
        "open_current": [],
        "open_stale": [],
        "open_orphaned": [],
    }
    for run_id in sorted(
        run_id
        for run_id, record in records.items()
        if record["state"] == "open"
    ):
        record = records[run_id]
        disposition = dispositions.get(run_id)
        category = (
            "open_stale"
            if disposition is not None
            else "open_current"
            if run_id in seen_current
            else "open_orphaned"
        )
        row: dict[str, Any] = {
            "run_id": run_id,
            "ledger_path": record["path"],
            "ledger_sha256": record["sha256"],
            "skill_version": record["skill_version"],
            "local_open_issue_count": sum(
                issue["status"] == "open"
                for issue in record["issues"].values()
            ),
        }
        if disposition is not None:
            row.update(
                {
                    "administrative_status": disposition["status"],
                    "administrative_reason": disposition["reason"],
                    "ledger_disposition_id": disposition[
                        "ledger_disposition_id"
                    ],
                    "successor_run_id": (
                        disposition["successor"]["run_id"]
                        if disposition["successor"] is not None
                        else None
                    ),
                }
            )
        categories[category].append(row)
    projection: dict[str, Any] = {
        "liveness_source": "explicit_current_run_ids_only",
        "raw_open_ledger_count": sum(
            record["state"] == "open" for record in records.values()
        ),
        "administrative_disposition_drift": (
            drift if full else drift[:8]
        ),
        "administrative_disposition_drift_count": len(drift),
        "administrative_disposition_drift_sha256": _sha256(
            _canonical_nfc_bytes(drift)
        ),
    }
    for category, rows in categories.items():
        projection[category] = rows if full else rows[:8]
        projection[f"{category}_count"] = len(rows)
        projection[f"{category}_sha256"] = _sha256(
            _canonical_nfc_bytes(rows)
        )
        projection[f"{category}_truncated"] = (
            not full and len(rows) > 8
        )
    return projection


def _bound_inventory_projection(result: dict[str, Any]) -> dict[str, Any]:
    summaries: dict[str, dict[str, Any]] = {}
    for field in (
        "unresolved",
        "report_compatibility_drift",
        "lineage_errors",
        "parallel_issue_free_successors",
        "parallel_closed_successors",
        "ignored_supersedes",
        "active_run_ids",
    ):
        rows = result.get(field)
        if not isinstance(rows, list):
            continue
        bounded = _bounded_rows(rows)
        summaries[field] = {
            key: bounded[key]
            for key in ("count", "sha256", "truncated")
        }
        result[field] = bounded["items"]
    result["bounded_lists"] = summaries
    return result


def _inventory_project_ledgers_unlocked(
    project_root: Path | str,
    *,
    full: bool = False,
    include_global: bool = True,
    current_run_ids: Sequence[str] = (),
) -> dict[str, Any]:
    """Build a read-only closure view over every project-local CHX ledger.

    ``run_closed`` only freezes a ledger; it does not resolve its issues.  This
    projection follows each predecessor chain and evaluates direct dispositions
    and unique ``supersedes`` successors without changing any ledger or report.
    Historical report-renderer drift is surfaced separately from ledger validity.
    """

    project = _resolved_path(project_root)
    if project.is_symlink() or not project.is_dir():
        raise ValueError("CHX inventory project root is missing or unsafe")
    ledger_root = project / DEFAULT_PROJECT_LEDGER_DIR
    if ledger_root.is_symlink():
        raise ValueError("CHX inventory ledger root must not be a symlink")
    if not ledger_root.exists():
        result = {
            "contract_revision": INVENTORY_CONTRACT_REVISION,
            "project_root": str(project),
            "ledger_root": str(ledger_root),
            "ledger_count": 0,
            "chain_count": 0,
            "unresolved": [],
            "report_compatibility_drift": [],
            "lineage_errors": [],
            "parallel_issue_free_successors": [],
            "parallel_closed_successors": [],
            "ignored_supersedes": [],
            "active_run_ids": [],
            "counts": {
                "active_ledgers": 0,
                "closed_ledgers": 0,
                "observed_issues": 0,
                "unresolved_issues": 0,
                "orphan_open_issues": 0,
                "active_open_issues": 0,
                "successor_pending_issues": 0,
                "report_compatibility_drift": 0,
                "ignored_supersedes": 0,
            },
            "truth_effect": "none",
            "project_effect": "none",
            "ledgers": [],
            "chains": [],
        }
        result["inventory_sha256"] = _sha256(
            _canonical_nfc_bytes(_inventory_semantic_projection(result))
        )
        if include_global:
            result = _apply_global_repair_projection(
                result,
                project_root=project,
            )
        result["ledger_activity"] = _ledger_activity_projection(
            project_root=project,
            records={},
            current_run_ids=current_run_ids,
            full=full,
        )
        result["active_run_ids"] = sorted(set(current_run_ids))
        result["counts"]["raw_open_ledgers"] = result["counts"][
            "active_ledgers"
        ]
        result["counts"]["active_ledgers"] = result[
            "ledger_activity"
        ]["open_current_count"]
        result["counts"]["stale_open_ledgers"] = result[
            "ledger_activity"
        ]["open_stale_count"]
        result["counts"]["orphaned_open_ledgers"] = result[
            "ledger_activity"
        ]["open_orphaned_count"]
        if full:
            pass
        else:
            result.pop("ledgers", None)
            result.pop("chains", None)
            result = _bound_inventory_projection(result)
        return result
    if not ledger_root.is_dir():
        raise ValueError("CHX inventory ledger root is not a directory")

    records: dict[str, dict[str, Any]] = {}
    path_to_run: dict[Path, str] = {}
    for path in sorted(ledger_root.iterdir(), key=lambda item: item.name):
        if path.suffix != ".jsonl":
            continue
        if path.is_symlink() or not path.is_file():
            raise ValueError("CHX inventory contains an unsafe ledger entry")
        before = path.read_bytes()
        events, status = _read_locked(path)
        if path.read_bytes() != before:
            raise ValueError("CHX ledger changed during inventory read")
        run_id = status["run_id"]
        if run_id in records:
            raise ValueError("CHX inventory contains a duplicate run id")
        dispositions = {
            event["issue_id"]: event
            for event in events
            if event["event"] == "issue_disposition"
        }
        issues: dict[str, dict[str, Any]] = {}
        for event in events:
            if event["event"] != "issue_observed":
                continue
            issue_id = event["issue_id"]
            disposition = dispositions.get(issue_id)
            issues[issue_id] = {
                "issue_id": issue_id,
                "status": (
                    disposition["status"] if disposition is not None else "open"
                ),
                "classification": event["classification"],
                "relations": list(event.get("relations", [])),
            }
        report_status = "not_applicable"
        report_error = ""
        if status["contract_revision"] in FINDING_CONTRACT_REVISIONS:
            if status["state"] != "closed":
                report_status = "pending"
            else:
                try:
                    verify_architecture_report(path)
                except (OSError, ValueError) as exc:
                    report_status = "drifted_or_missing"
                    report_error = str(exc)
                else:
                    report_status = "exact"
        predecessor_path = status.get("predecessor_ledger_path", "")
        predecessor = ""
        if predecessor_path:
            candidate = Path(predecessor_path).expanduser()
            if not candidate.is_absolute():
                candidate = path.parent / candidate
            predecessor = str(candidate.resolve(strict=False))
        record = {
            "run_id": run_id,
            "path": str(path),
            "sha256": _sha256(before),
            "skill_version": status["skill_version"],
            "contract_revision": status["contract_revision"],
            "state": status["state"],
            "predecessor_path": predecessor,
            "predecessor_sha256": status.get(
                "predecessor_ledger_sha256", ""
            ),
            "predecessor_lineage": status.get("predecessor_lineage", []),
            "issues": issues,
            "report_status": report_status,
            "report_error": report_error,
        }
        records[run_id] = record
        path_to_run[path.resolve(strict=False)] = run_id

    parent: dict[str, str | None] = {}
    lineage_errors: list[str] = []
    for run_id, record in records.items():
        predecessor = record["predecessor_path"]
        if not predecessor:
            parent[run_id] = None
            continue
        predecessor_run = path_to_run.get(Path(predecessor))
        if predecessor_run is None:
            lineage_errors.append(
                f"{run_id}: predecessor ledger is outside or missing from inventory: "
                f"{predecessor}"
            )
        else:
            expected_digest = record["predecessor_sha256"]
            observed_digest = records[predecessor_run]["sha256"]
            if expected_digest != observed_digest:
                lineage_errors.append(
                    f"{run_id}: predecessor ledger digest binding drifted for "
                    f"{predecessor_run}: expected {expected_digest}, observed "
                    f"{observed_digest}"
                )
        parent[run_id] = predecessor_run

    children: dict[str, list[str]] = {}
    for run_id, predecessor in parent.items():
        if predecessor is not None:
            children.setdefault(predecessor, []).append(run_id)
    parallel_issue_free_successors: list[dict[str, Any]] = []
    parallel_closed_successors: list[dict[str, Any]] = []
    parallel_supersede_sources: dict[str, set[str]] = {}

    def successor_subtree(
        run_id: str,
        visiting: tuple[str, ...] = (),
    ) -> tuple[int, tuple[str, ...]]:
        """Return the exact closed subtree beneath one direct successor."""

        if run_id in visiting:
            raise ValueError("CHX inventory predecessor chain contains a cycle")
        descendant_runs = [run_id]
        issue_count = len(records[run_id]["issues"])
        for child_run_id in sorted(children.get(run_id, [])):
            child_issue_count, child_runs = successor_subtree(
                child_run_id,
                visiting + (run_id,),
            )
            issue_count += child_issue_count
            descendant_runs.extend(child_runs)
        return issue_count, tuple(descendant_runs)

    for predecessor, successor_run_ids in sorted(children.items()):
        if len(successor_run_ids) > 1:
            branch_data = [
                (
                    successor_run_id,
                    *successor_subtree(successor_run_id),
                )
                for successor_run_id in sorted(successor_run_ids)
            ]
            ancestor_owners: dict[str, str] = {}
            ancestor_run: str | None = predecessor
            while ancestor_run is not None:
                for issue_id in records[ancestor_run]["issues"]:
                    ancestor_owners.setdefault(issue_id, ancestor_run)
                ancestor_run = parent.get(ancestor_run)
            for successor_run_id, issue_count, descendant_runs in branch_data:
                projection = {
                    "predecessor_run_id": predecessor,
                    "successor_run_id": successor_run_id,
                    "successor_subtree_run_ids": list(descendant_runs),
                    "successor_subtree_issue_count": issue_count,
                }
                subtree_active = any(
                    records[descendant_run_id]["state"] == "open"
                    for descendant_run_id in descendant_runs
                )
                if not subtree_active:
                    parallel_closed_successors.append(projection)
                    if issue_count == 0:
                        parallel_issue_free_successors.append(projection)
                for descendant_run_id in descendant_runs:
                    for issue in records[descendant_run_id]["issues"].values():
                        for relation in issue["relations"]:
                            if relation.get("relation_type") != "supersedes":
                                continue
                            target_id = relation.get("issue_id")
                            owner_run = ancestor_owners.get(target_id)
                            if owner_run is None:
                                continue
                            qualified_target = f"{owner_run}/{target_id}"
                            parallel_supersede_sources.setdefault(
                                qualified_target, set()
                            ).add(successor_run_id)
    for qualified_target, sources in sorted(parallel_supersede_sources.items()):
        if len(sources) > 1:
            lineage_errors.append(
                f"{qualified_target}: competing supersedes successors across "
                "parallel branches: "
                + ", ".join(sorted(sources))
            )
    terminals = sorted(
        (run_id for run_id in records if run_id not in children),
        key=lambda item: (records[item]["state"] != "open", item),
    )

    def chain_for(terminal: str) -> list[str]:
        chain: list[str] = []
        seen: set[str] = set()
        current: str | None = terminal
        while current is not None:
            if current in seen:
                raise ValueError("CHX inventory predecessor chain contains a cycle")
            seen.add(current)
            chain.append(current)
            current = parent.get(current)
        return list(reversed(chain))

    chains: list[dict[str, Any]] = []
    all_issue_rows: list[dict[str, Any]] = []
    ignored_supersedes: list[dict[str, str]] = []
    seen_chain_runs: set[str] = set()
    for terminal in terminals:
        chain = chain_for(terminal)
        seen_chain_runs.update(chain)
        owners: dict[str, str] = {}
        issue_map: dict[str, dict[str, Any]] = {}
        successors: dict[str, list[str]] = {}
        for run_id in chain:
            for issue_id, issue in records[run_id]["issues"].items():
                if issue_id in owners:
                    raise ValueError(
                        "CHX inventory issue numbering collides inside a predecessor chain"
                    )
                owners[issue_id] = run_id
                issue_map[issue_id] = {**issue, "run_id": run_id}
        for issue_id, issue in issue_map.items():
            for relation in issue["relations"]:
                if relation.get("relation_type") != "supersedes":
                    continue
                target_id = relation.get("issue_id")
                if target_id not in issue_map:
                    lineage_errors.append(
                        f"{owners[issue_id]}/{issue_id}: supersedes absent issue {target_id}"
                    )
                    continue
                if owners[issue_id] == owners[target_id]:
                    ignored_supersedes.append(
                        {
                            "source_qualified_issue_id": (
                                f"{owners[issue_id]}/{issue_id}"
                            ),
                            "target_qualified_issue_id": (
                                f"{owners[target_id]}/{target_id}"
                            ),
                            "reason": "same_ledger_not_strictly_later",
                        }
                    )
                    continue
                if issue["status"] == "excluded_nonarchitectural":
                    ignored_supersedes.append(
                        {
                            "source_qualified_issue_id": (
                                f"{owners[issue_id]}/{issue_id}"
                            ),
                            "target_qualified_issue_id": (
                                f"{owners[target_id]}/{target_id}"
                            ),
                            "reason": "excluded_successor_has_no_repair_effect",
                        }
                    )
                    continue
                successors.setdefault(target_id, []).append(issue_id)
        resolved_cache: dict[str, bool] = {}

        def is_resolved(issue_id: str, visiting: tuple[str, ...] = ()) -> bool:
            cached = resolved_cache.get(issue_id)
            if cached is not None:
                return cached
            if issue_id in visiting:
                raise ValueError("CHX inventory supersedes relation contains a cycle")
            if issue_map[issue_id]["status"] == "resolved":
                resolved_cache[issue_id] = True
                return True
            if issue_map[issue_id]["status"] == "excluded_nonarchitectural":
                resolved_cache[issue_id] = False
                return False
            candidates = sorted(
                successors.get(issue_id, []),
                key=lambda item: int(item.removeprefix("CHX-")),
            )
            result = len(candidates) == 1 and is_resolved(
                candidates[0], visiting + (issue_id,)
            )
            resolved_cache[issue_id] = result
            return result

        issue_rows: list[dict[str, Any]] = []
        terminal_active = records[terminal]["state"] == "open"
        for issue_id in sorted(
            issue_map, key=lambda item: int(item.removeprefix("CHX-"))
        ):
            issue = issue_map[issue_id]
            qualified = f"{issue['run_id']}/{issue_id}"
            direct_status = issue["status"]
            if direct_status in {"resolved", "excluded_nonarchitectural"}:
                resolution = (
                    "excluded_nonarchitectural"
                    if direct_status == "excluded_nonarchitectural"
                    else "resolved_direct"
                )
            elif is_resolved(issue_id):
                resolution = "resolved_by_successor"
            elif terminal_active:
                resolution = "open_active"
            elif successors.get(issue_id):
                resolution = "open_successor_pending"
            else:
                resolution = "open_orphan"
            issue_row = {
                "qualified_issue_id": qualified,
                "run_id": issue["run_id"],
                "issue_id": issue_id,
                "status": direct_status,
                "resolution": resolution,
                "classification": issue["classification"],
                "successor_issue_ids": [
                    f"{owners[item]}/{item}" for item in successors.get(issue_id, [])
                ],
            }
            issue_rows.append(issue_row)
        all_issue_rows.extend(issue_rows)
        chains.append(
            {
                "terminal_run_id": terminal,
                "run_ids": chain,
                "active": terminal_active,
                "issue_count": len(issue_rows),
                "_issue_ids": [
                    item["qualified_issue_id"] for item in issue_rows
                ],
            }
        )

    if seen_chain_runs != set(records):
        missing = sorted(set(records).difference(seen_chain_runs))
        raise ValueError("CHX inventory could not construct chains: " + ", ".join(missing))

    # A common ancestor appears once in every terminal chain below a closed
    # parallel split. Consolidate by immutable qualified ownership so counts
    # are not multiplied by branch count and one unique resolving successor
    # applies consistently to that ancestor in every chain projection.
    rows_by_issue: dict[str, list[dict[str, Any]]] = {}
    for row in all_issue_rows:
        rows_by_issue.setdefault(row["qualified_issue_id"], []).append(row)
    resolution_rank = {
        "open_orphan": 0,
        "open_successor_pending": 1,
        "open_active": 2,
        "resolved_by_successor": 3,
        "excluded_nonarchitectural": 4,
        "resolved_direct": 5,
    }
    consolidated_rows: dict[str, dict[str, Any]] = {}
    for qualified, rows in sorted(rows_by_issue.items()):
        first = rows[0]
        identity = (
            first["run_id"],
            first["issue_id"],
            first["status"],
            first["classification"],
        )
        if any(
            (
                row["run_id"],
                row["issue_id"],
                row["status"],
                row["classification"],
            )
            != identity
            for row in rows[1:]
        ):
            raise ValueError(
                "CHX inventory parallel projections disagree on issue identity"
            )
        resolution = max(
            (row["resolution"] for row in rows),
            key=lambda value: resolution_rank[value],
        )
        consolidated_rows[qualified] = {
            **first,
            "resolution": resolution,
            "successor_issue_ids": sorted(
                {
                    successor
                    for row in rows
                    for successor in row["successor_issue_ids"]
                },
                key=_qualified_issue_sort_key,
            ),
        }
    unresolved = [
        row
        for row in consolidated_rows.values()
        if row["resolution"].startswith("open_")
    ]
    for chain in chains:
        chain["unresolved_issue_ids"] = [
            qualified
            for qualified in chain.pop("_issue_ids")
            if consolidated_rows[qualified]["resolution"].startswith("open_")
        ]

    ignored_supersedes = [
        {
            "source_qualified_issue_id": source,
            "target_qualified_issue_id": target,
            "reason": reason,
        }
        for source, target, reason in sorted(
            {
                (
                    item["source_qualified_issue_id"],
                    item["target_qualified_issue_id"],
                    item["reason"],
                )
                for item in ignored_supersedes
            }
        )
    ]
    ledgers: list[dict[str, Any]] = []
    for run_id in sorted(records):
        record = records[run_id]
        local_open = [
            f"{run_id}/{issue_id}"
            for issue_id, issue in sorted(
                record["issues"].items(),
                key=lambda item: int(item[0].removeprefix("CHX-")),
            )
            if issue["status"] == "open"
        ]
        ledgers.append(
            {
                key: record[key]
                for key in (
                    "run_id",
                    "path",
                    "sha256",
                    "skill_version",
                    "contract_revision",
                    "state",
                    "predecessor_path",
                    "report_status",
                )
            }
            | {
                "issue_ids": [
                    f"{run_id}/{issue_id}" for issue_id in record["issues"]
                ],
                "local_open_issue_ids": local_open,
            }
        )
    report_drift = [
        {
            "run_id": record["run_id"],
            "path": record["path"],
            "error": record["report_error"],
        }
        for record in records.values()
        if record["report_status"] == "drifted_or_missing"
    ]
    counts = {
        "active_ledgers": sum(record["state"] == "open" for record in records.values()),
        "closed_ledgers": sum(record["state"] == "closed" for record in records.values()),
        "observed_issues": sum(len(record["issues"]) for record in records.values()),
        "unresolved_issues": len(unresolved),
        "orphan_open_issues": sum(item["resolution"] == "open_orphan" for item in unresolved),
        "active_open_issues": sum(item["resolution"] == "open_active" for item in unresolved),
        "successor_pending_issues": sum(
            item["resolution"] == "open_successor_pending" for item in unresolved
        ),
        "report_compatibility_drift": len(report_drift),
        "ignored_supersedes": len(ignored_supersedes),
    }
    result = {
        "contract_revision": INVENTORY_CONTRACT_REVISION,
        "project_root": str(project),
        "ledger_root": str(ledger_root),
        "ledger_count": len(records),
        "chain_count": len(chains),
        "unresolved": unresolved,
        "report_compatibility_drift": report_drift,
        "lineage_errors": sorted(set(lineage_errors)),
        "parallel_issue_free_successors": parallel_issue_free_successors,
        "parallel_closed_successors": parallel_closed_successors,
        "ignored_supersedes": sorted(
            ignored_supersedes,
            key=lambda item: (
                item["source_qualified_issue_id"],
                item["target_qualified_issue_id"],
                item["reason"],
            ),
        ),
        "active_run_ids": sorted(
            run_id for run_id, record in records.items() if record["state"] == "open"
        ),
        "counts": counts,
        "truth_effect": "none",
        "project_effect": "none",
        "ledgers": ledgers,
        "chains": chains,
    }
    result["inventory_sha256"] = _sha256(
        _canonical_nfc_bytes(_inventory_semantic_projection(result))
    )
    if include_global:
        result = _apply_global_repair_projection(
            result,
            project_root=project,
        )
    result["ledger_activity"] = _ledger_activity_projection(
        project_root=project,
        records=records,
        current_run_ids=current_run_ids,
        full=full,
    )
    result["active_run_ids"] = sorted(set(current_run_ids))
    result["counts"]["raw_open_ledgers"] = result["counts"][
        "active_ledgers"
    ]
    result["counts"]["active_ledgers"] = result[
        "ledger_activity"
    ]["open_current_count"]
    result["counts"]["stale_open_ledgers"] = result[
        "ledger_activity"
    ]["open_stale_count"]
    result["counts"]["orphaned_open_ledgers"] = result[
        "ledger_activity"
    ]["open_orphaned_count"]
    if full:
        pass
    else:
        result.pop("ledgers", None)
        result.pop("chains", None)
        result = _bound_inventory_projection(result)
    return result


def inventory_project_ledgers(
    project_root: Path | str,
    *,
    full: bool = False,
    include_global: bool = True,
    current_run_ids: Sequence[str] = (),
    _lock_held: bool = False,
) -> dict[str, Any]:
    """Read a project inventory under the shared CHX writer lock.

    A caller already holding the exclusive global-repair lock uses the private
    ``_lock_held`` escape hatch to avoid trying to acquire a second flock.
    The public CLI path always takes a shared lock, so a reader cannot observe
    a half-written ledger or global-repair record.
    """

    if _lock_held:
        return _inventory_project_ledgers_unlocked(
            project_root,
            full=full,
            include_global=include_global,
            current_run_ids=current_run_ids,
        )
    project = _resolved_path(project_root)
    ledger_root = project / DEFAULT_PROJECT_LEDGER_DIR
    if not ledger_root.exists():
        return _inventory_project_ledgers_unlocked(
            project,
            full=full,
            include_global=include_global,
            current_run_ids=current_run_ids,
        )
    with _global_repair_lock(project, exclusive=False):
        return _inventory_project_ledgers_unlocked(
            project,
            full=full,
            include_global=include_global,
            current_run_ids=current_run_ids,
        )


def record_global_repair(
    project_root: Path | str,
    integration: dict[str, Any],
) -> dict[str, Any]:
    """Record one immutable, cross-ledger CHX integrated repair.

    This is the direct route for a repair intended for global Chalxius
    installation as well as an explicit historical settlement. It has no
    tactical-repair precondition: tactical records describe only changes that
    remain inside a project run. The operation binds the complete current
    inventory, assigns every qualified issue to one mechanism group, and writes
    one content-addressed successor without mutating historical JSONL ledgers.
    """

    project = _resolved_path(project_root)
    if project.is_symlink() or not project.is_dir():
        raise ValueError("CHX global repair project root is missing or unsafe")
    normalized = _validate_global_repair_input(integration)
    if normalized["candidate_root"] != str(_skill_root()):
        raise ValueError("CHX global repair candidate root does not match this runtime")
    if normalized["candidate_version"] != _skill_version():
        raise ValueError("CHX global repair candidate version does not match this runtime")
    _validate_global_repair_candidate(
        normalized["candidate_root"],
        candidate_version=normalized["candidate_version"],
        candidate_manifest_sha256=normalized["candidate_manifest_sha256"],
    )
    _verify_global_repair_references(normalized, project_root=project)
    with _global_repair_lock(project, exclusive=True):
        try:
            base = inventory_project_ledgers(
                project,
                full=True,
                include_global=False,
                _lock_held=True,
            )
            _require_global_repair_inventory_integrity(base)
            if normalized["inventory_sha256"] != base["inventory_sha256"]:
                raise ValueError("CHX global repair inventory snapshot is stale")
            observed_ids = sorted(
                {
                    issue_id
                    for ledger in base["ledgers"]
                    for issue_id in ledger["issue_ids"]
                },
                key=_qualified_issue_sort_key,
            )
            expected_covered_snapshot = _covered_issue_snapshot_sha256(
                base,
                observed_ids,
            )
            if (
                normalized["covered_issue_snapshot_sha256"]
                != expected_covered_snapshot
            ):
                raise ValueError(
                    "CHX global repair covered issue snapshot is stale"
                )
            if normalized["included_issue_ids"] != observed_ids:
                raise ValueError(
                    "CHX global repair must cover every observed qualified issue"
                )
            records, chain = _collect_global_repair_records(project)
            if chain:
                latest = next(
                    record
                    for record in records
                    if record["global_repair_id"] == chain[-1]
                )
                if all(latest[key] == value for key, value in normalized.items()):
                    return {
                        "global_repair_id": latest["global_repair_id"],
                        "record_path": str(
                            _global_repair_dir(project)
                            / f"{latest['global_repair_id']}.json"
                        ),
                        "record_sha256": latest["record_sha256"],
                        "inventory_sha256": latest["inventory_sha256"],
                        "covered_issue_snapshot_sha256": latest[
                            "covered_issue_snapshot_sha256"
                        ],
                        "covered_issue_count": len(latest["included_issue_ids"]),
                        "status": "existing",
                        "truth_effect": "none",
                        "project_effect": "none",
                    }
            expected_predecessor = chain[-1] if chain else ""
            if normalized["supersedes_global_repair_id"] != expected_predecessor:
                raise ValueError(
                    "CHX global repair predecessor does not name the latest record"
                )
            final_base = inventory_project_ledgers(
                project,
                full=True,
                include_global=False,
                _lock_held=True,
            )
            _require_global_repair_inventory_integrity(final_base)
            if final_base["inventory_sha256"] != base["inventory_sha256"]:
                raise ValueError(
                    "CHX global repair inventory changed before final write"
                )
            final_covered_snapshot = _covered_issue_snapshot_sha256(
                final_base,
                normalized["included_issue_ids"],
            )
            if (
                final_covered_snapshot
                != normalized["covered_issue_snapshot_sha256"]
            ):
                raise ValueError(
                    "CHX global repair covered issue snapshot changed before final write"
                )
            final_records, final_chain = _collect_global_repair_records(project)
            if final_chain != chain or {
                item["global_repair_id"] for item in final_records
            } != {item["global_repair_id"] for item in records}:
                raise ValueError(
                    "CHX global repair lineage changed before final write"
                )
            _validate_global_repair_candidate(
                normalized["candidate_root"],
                candidate_version=normalized["candidate_version"],
                candidate_manifest_sha256=normalized[
                    "candidate_manifest_sha256"
                ],
            )
            _verify_global_repair_references(normalized, project_root=project)
            semantic = {
                "schema_version": 1,
                "contract_revision": GLOBAL_REPAIR_CONTRACT_REVISION,
                "event": "global_integrated_repair",
                "project_root": str(project),
                **normalized,
                "truth_effect": "none",
                "project_effect": "none",
            }
            global_repair_id = _global_repair_id(semantic)
            path = _global_repair_dir(project) / f"{global_repair_id}.json"
            if path.exists():
                raise ValueError("CHX global repair record already exists")
            record = {
                **semantic,
                "global_repair_id": global_repair_id,
                "created_at": _utc_now(),
            }
            record["record_sha256"] = _sha256(_canonical_nfc_bytes(record))
            _validate_global_repair_record(record, path=path, project_root=project)
            directory = path.parent
            if directory.is_symlink():
                raise ValueError("CHX global repair directory is unsafe")
            directory.mkdir(parents=True, exist_ok=True)
            temporary = directory / f".{path.name}.tmp-{os.getpid()}-{secrets.token_hex(4)}"
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with os.fdopen(descriptor, "wb", closefd=True) as handle:
                    handle.write(_canonical_bytes(record))
                    handle.write(b"\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                _validate_global_repair_candidate(
                    normalized["candidate_root"],
                    candidate_version=normalized["candidate_version"],
                    candidate_manifest_sha256=normalized[
                        "candidate_manifest_sha256"
                    ],
                )
                _verify_global_repair_references(normalized, project_root=project)
                os.replace(temporary, path)
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise
        finally:
            pass
    return {
        "global_repair_id": global_repair_id,
        "record_path": str(path),
        "record_sha256": record["record_sha256"],
        "inventory_sha256": normalized["inventory_sha256"],
        "covered_issue_snapshot_sha256": normalized[
            "covered_issue_snapshot_sha256"
        ],
        "covered_issue_count": len(observed_ids),
        "status": "recorded",
        "truth_effect": "none",
        "project_effect": "none",
    }


def verify_global_repair(project_root: Path | str) -> dict[str, Any]:
    """Verify the latest global repair against a fresh project inventory."""

    project = _resolved_path(project_root)
    base = inventory_project_ledgers(project, full=True, include_global=False)
    records, chain = _collect_global_repair_records(project)
    if not records:
        raise ValueError("CHX global repair record is missing")
    latest = next(
        record for record in records if record["global_repair_id"] == chain[-1]
    )
    if base["lineage_errors"]:
        raise ValueError("CHX global repair inventory has lineage errors")
    if base["report_compatibility_drift"]:
        raise ValueError("CHX global repair inventory has report drift")
    if latest["candidate_root"] != str(_skill_root()):
        raise ValueError("CHX global repair candidate root is not current")
    if latest["candidate_version"] != _skill_version():
        raise ValueError("CHX global repair candidate version is not current")
    try:
        _validate_global_repair_candidate(
            latest["candidate_root"],
            candidate_version=latest["candidate_version"],
            candidate_manifest_sha256=latest["candidate_manifest_sha256"],
        )
    except ValueError as exc:
        raise ValueError(
            "CHX global repair candidate manifest is not current"
        ) from exc
    _verify_global_repair_references(latest, project_root=project)
    observed_ids = {
        issue_id
        for ledger in base["ledgers"]
        for issue_id in ledger["issue_ids"]
    }
    covered_ids = set(latest["included_issue_ids"])
    if not covered_ids.issubset(observed_ids):
        raise ValueError("CHX global repair covered issue set drifted")
    if (
        _covered_issue_snapshot_sha256(base, latest["included_issue_ids"])
        != latest["covered_issue_snapshot_sha256"]
    ):
        raise ValueError("CHX global repair covered issue snapshot drifted")
    disposition_ids = {
        item["qualified_issue_id"] for item in latest["issue_dispositions"]
    }
    if disposition_ids != covered_ids:
        raise ValueError("CHX global repair disposition coverage drifted")
    if any(
        item["status"] not in DISPOSITION_STATUSES
        for item in latest["issue_dispositions"]
    ):
        raise ValueError("CHX global repair contains an unresolved disposition")
    return {
        "global_repair_id": latest["global_repair_id"],
        "record_path": str(
            _global_repair_dir(project)
            / f"{latest['global_repair_id']}.json"
        ),
        "inventory_sha256": latest["inventory_sha256"],
        "covered_issue_snapshot_sha256": latest[
            "covered_issue_snapshot_sha256"
        ],
        "covered_issue_count": len(latest["included_issue_ids"]),
        "uncovered_issue_count": len(observed_ids.difference(covered_ids)),
        "status": "current",
        "truth_effect": "none",
        "project_effect": "none",
    }


def validate_public_disclosure_contract(
    skill_root: Path | str | None = None,
) -> dict[str, Any]:
    """Validate a lineage-aware public registry against its documents."""

    requested_root = (
        Path(skill_root).expanduser()
        if skill_root is not None
        else _skill_root()
    )
    if requested_root.is_symlink():
        raise ValueError("CHX public-disclosure skill root must not be a symlink")
    root = requested_root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("CHX public-disclosure skill root is not a directory")
    lock_path = root / "INHERITANCE.lock.json"
    if lock_path.is_symlink() or not lock_path.is_file():
        raise ValueError("CHX public-disclosure inheritance lock is unsafe")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    disclosure = lock.get("chx_public_disclosure")
    expected_fields = {
        "contract_revision",
        "included_issue_ids",
        "ledger_lineage",
        "latest_issue_id",
        "document_contracts",
        "private_ledger_included",
        "truth_effect",
    }
    if not isinstance(disclosure, dict) or set(disclosure) != expected_fields:
        raise ValueError("CHX public-disclosure contract fields are not exact")
    if disclosure["contract_revision"] != PUBLIC_DISCLOSURE_CONTRACT_REVISION:
        raise ValueError("CHX public-disclosure contract revision is invalid")
    if (
        disclosure["private_ledger_included"] is not False
        or disclosure["truth_effect"] != "none"
    ):
        raise ValueError("CHX public-disclosure authority boundary is invalid")

    included = disclosure["included_issue_ids"]
    if (
        not isinstance(included, list)
        or not included
        or any(
            not isinstance(item, str) or ISSUE_ID_RE.fullmatch(item) is None
            for item in included
        )
        or included
        != sorted(
            set(included),
            key=lambda item: int(item.removeprefix("CHX-")),
        )
    ):
        raise ValueError("CHX public-disclosure included issue ids are invalid")
    included_numbers = [int(item.removeprefix("CHX-")) for item in included]
    if included_numbers != list(range(1, included_numbers[-1] + 1)):
        raise ValueError("CHX public-disclosure included issue ids are not contiguous")
    if disclosure["latest_issue_id"] != included[-1]:
        raise ValueError("CHX public-disclosure latest issue id drifted")

    lineage = disclosure["ledger_lineage"]
    if not isinstance(lineage, list) or not lineage:
        raise ValueError("CHX public-disclosure ledger lineage is invalid")
    normalized_lineage: list[dict[str, Any]] = []
    issue_owners: dict[str, str] = {}
    seen_runs: set[str] = set()
    previous_run_id = ""
    for index, entry in enumerate(lineage, 1):
        expected_entry_fields = {
            "ledger_run_id",
            "ledger_sha256",
            "ledger_contract_revision",
            "predecessor_run_id",
            "included_issue_ids",
        }
        if not isinstance(entry, dict) or set(entry) != expected_entry_fields:
            raise ValueError(
                f"CHX public-disclosure lineage entry {index} fields are not exact"
            )
        run_id = _validate_run_id(entry["ledger_run_id"])
        digest = entry["ledger_sha256"]
        revision = entry["ledger_contract_revision"]
        if run_id in seen_runs:
            raise ValueError("CHX public-disclosure ledger lineage contains a cycle")
        if not isinstance(digest, str) or SHA256_RE.fullmatch(digest) is None:
            raise ValueError("CHX public-disclosure ledger digest is invalid")
        if revision not in SUPPORTED_CONTRACT_REVISIONS:
            raise ValueError("CHX public-disclosure ledger revision is invalid")
        if entry["predecessor_run_id"] != previous_run_id:
            raise ValueError("CHX public-disclosure ledger lineage order drifted")
        issue_ids = entry["included_issue_ids"]
        if (
            not isinstance(issue_ids, list)
            or any(
                not isinstance(item, str) or ISSUE_ID_RE.fullmatch(item) is None
                for item in issue_ids
            )
            or issue_ids
            != sorted(
                set(issue_ids),
                key=lambda item: int(item.removeprefix("CHX-")),
            )
        ):
            raise ValueError("CHX public-disclosure lineage issue ids are invalid")
        for issue_id in issue_ids:
            if issue_id in issue_owners:
                raise ValueError("CHX public-disclosure issue ownership overlaps")
            issue_owners[issue_id] = run_id
        normalized_lineage.append(
            {
                "ledger_run_id": run_id,
                "ledger_sha256": digest,
                "ledger_contract_revision": revision,
                "predecessor_run_id": previous_run_id,
                "included_issue_ids": issue_ids,
            }
        )
        seen_runs.add(run_id)
        previous_run_id = run_id
    owned_ids = sorted(
        issue_owners,
        key=lambda item: int(item.removeprefix("CHX-")),
    )
    if owned_ids != included:
        raise ValueError("CHX public-disclosure lineage issue ownership drifted")

    document_contracts = disclosure["document_contracts"]
    if not isinstance(document_contracts, dict) or not document_contracts:
        raise ValueError("CHX public-disclosure document contracts are invalid")
    document_hashes: dict[str, str] = {}
    for relative, contract in sorted(document_contracts.items()):
        relative_path = Path(relative)
        if (
            not isinstance(relative, str)
            or not relative
            or relative_path.is_absolute()
            or any(part in {"", ".", ".."} for part in relative_path.parts)
        ):
            raise ValueError("CHX public-disclosure document path is invalid")
        if not isinstance(contract, dict) or set(contract) != {
            "explicit_issue_enumeration",
            "required_markers",
        }:
            raise ValueError("CHX public-disclosure document contract is malformed")
        explicit = contract["explicit_issue_enumeration"]
        markers = contract["required_markers"]
        if not isinstance(explicit, bool) or (
            not isinstance(markers, list)
            or not markers
            or any(not isinstance(item, str) or not item for item in markers)
            or markers != sorted(set(markers))
        ):
            raise ValueError("CHX public-disclosure document requirements are invalid")
        document = root / relative_path
        if document.is_symlink() or not document.is_file():
            raise ValueError("CHX public-disclosure document is missing or unsafe")
        if root not in document.resolve(strict=True).parents:
            raise ValueError("CHX public-disclosure document escaped the skill root")
        raw = document.read_bytes()
        text = raw.decode("utf-8")
        missing = [marker for marker in markers if marker not in text]
        if missing:
            raise ValueError(
                f"CHX public-disclosure document lacks required markers: {relative}"
            )
        if explicit:
            enumerated = re.findall(
                r"^[0-9]+\. \*\*(CHX-[0-9]{3,}) [—-]",
                text,
                flags=re.MULTILINE,
            )
            if enumerated != included:
                raise ValueError(
                    "CHX public-disclosure explicit issue enumeration drifted"
                )
        document_hashes[relative] = _sha256(raw)
    return {
        "contract_revision": PUBLIC_DISCLOSURE_CONTRACT_REVISION,
        "included_issue_ids": included,
        "ledger_lineage": normalized_lineage,
        "current_ledger_run_id": normalized_lineage[-1]["ledger_run_id"],
        "current_ledger_issue_ids": normalized_lineage[-1][
            "included_issue_ids"
        ],
        "latest_issue_id": included[-1],
        "qualified_included_issue_ids": [
            f"{issue_owners[issue_id]}/{issue_id}" for issue_id in included
        ],
        "document_sha256": document_hashes,
        "registry_sha256": _sha256(_canonical_nfc_bytes(disclosure)),
        "status": "current",
        "truth_effect": "none",
    }


def verify_public_disclosure(
    ledger_path: Path | str,
    skill_root: Path | str | None = None,
) -> dict[str, Any]:
    """Verify the exact closed private ledger chain without publishing it."""

    contract = validate_public_disclosure_contract(skill_root)
    path = _resolved_path(ledger_path)
    records = _collect_closed_ledger_records(path)
    actual_lineage: list[dict[str, Any]] = []
    publication_issues: dict[str, tuple[int, dict[str, Any]]] = {}
    previous_run_id = ""
    for record_index, record in enumerate(records):
        status = record["status"]
        if status.get("unreconciled_finding_ids"):
            raise ValueError("CHX publication has unreconciled findings")
        # The ordinary status projection deliberately hides issues disposed as
        # nonarchitectural.  Public lineage cannot do that: issue ownership must
        # remain contiguous and an explicit exclusion is itself the terminal
        # publication disposition.  Reconstruct only those omitted issue ids
        # from the already validated immutable events; do not reinterpret them
        # as repaired.
        excluded_ids = {
            event["issue_id"]
            for event in record["events"]
            if event["event"] == "issue_disposition"
            and event["status"] == "excluded_nonarchitectural"
        }
        observed = {
            event["issue_id"]: event
            for event in record["events"]
            if event["event"] == "issue_observed"
        }
        issues = [
            *status["issues"],
            *[
                {
                    "issue_id": issue_id,
                    "relations": observed[issue_id].get("relations", []),
                    "status": "excluded_nonarchitectural",
                }
                for issue_id in sorted(
                    excluded_ids,
                    key=lambda item: int(item.removeprefix("CHX-")),
                )
            ],
        ]
        for issue in issues:
            issue_id = issue["issue_id"]
            if issue_id in publication_issues:
                raise ValueError("CHX publication issue ownership overlaps")
            publication_issues[issue_id] = (record_index, issue)
        issue_ids = sorted(
            (item["issue_id"] for item in issues),
            key=lambda item: int(item.removeprefix("CHX-")),
        )
        actual_lineage.append(
            {
                "ledger_run_id": status["run_id"],
                "ledger_sha256": record["ledger_sha256"],
                "ledger_contract_revision": status["contract_revision"],
                "predecessor_run_id": previous_run_id,
                "included_issue_ids": issue_ids,
            }
        )
        previous_run_id = status["run_id"]

    superseding_issue_ids: dict[str, list[str]] = {}
    for source_id, (source_index, source_issue) in publication_issues.items():
        for relation in source_issue["relations"]:
            if relation["relation_type"] != "supersedes":
                continue
            target_id = relation["issue_id"]
            target = publication_issues.get(target_id)
            if target is None:
                raise ValueError(
                    "CHX publication supersedes relation names an absent issue"
                )
            target_index, _ = target
            if target_index >= source_index:
                raise ValueError(
                    "CHX publication supersedes relation is not strictly later"
                )
            if source_issue["status"] == "excluded_nonarchitectural":
                # Exclusion disposes only the source observation.  It is not
                # evidence that an earlier architectural mechanism was
                # repaired, so it cannot discharge a predecessor through a
                # supersedes edge.
                continue
            superseding_issue_ids.setdefault(target_id, []).append(source_id)

    resolution_cache: dict[str, bool] = {}

    def publication_resolved(issue_id: str, visiting: set[str]) -> bool:
        cached = resolution_cache.get(issue_id)
        if cached is not None:
            return cached
        if issue_id in visiting:
            raise ValueError("CHX publication supersedes relation contains a cycle")
        _, issue = publication_issues[issue_id]
        if issue["status"] in {"resolved", "excluded_nonarchitectural"}:
            resolution_cache[issue_id] = True
            return True
        successors = sorted(
            superseding_issue_ids.get(issue_id, []),
            key=lambda item: int(item.removeprefix("CHX-")),
        )
        if len(successors) != 1:
            resolution_cache[issue_id] = False
            return False
        resolved = publication_resolved(successors[0], visiting | {issue_id})
        resolution_cache[issue_id] = resolved
        return resolved

    unresolved_issue_ids = sorted(
        (
            issue_id
            for issue_id in publication_issues
            if not publication_resolved(issue_id, set())
        ),
        key=lambda item: int(item.removeprefix("CHX-")),
    )
    if unresolved_issue_ids:
        raise ValueError(
            "CHX publication contains an unresolved included issue: "
            + ", ".join(unresolved_issue_ids)
        )
    if actual_lineage != contract["ledger_lineage"]:
        raise ValueError("CHX private ledger lineage differs from public disclosure")
    current = records[-1]
    events = current["events"]
    status = current["status"]
    return {
        **contract,
        "ledger_path": str(path),
        "ledger_state": status["state"],
        "ledger_event_head_sha256": events[-1]["event_sha256"],
        "ledger_file_sha256": current["ledger_sha256"],
        "status": "pass",
        "private_ledger_included": False,
    }


def _json_file(path_value: str) -> dict[str, Any]:
    path = _resolved_path(path_value)
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"input JSON is missing, unsafe, or not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("input JSON must contain one object")
    return payload


def _json_list_file(path_value: str) -> list[Any]:
    path = _resolved_path(path_value)
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"input JSON is missing, unsafe, or not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("input JSON must contain one list")
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Operate a task-scoped CHX ledger.")
    commands = parser.add_subparsers(dest="command", required=True)

    start = commands.add_parser("start")
    placement = start.add_mutually_exclusive_group(required=True)
    placement.add_argument("--project-root")
    placement.add_argument("--root")
    start.add_argument("--task", required=True)
    start.add_argument("--run-id")
    start.add_argument("--host-task-scope-id", default="")
    start.add_argument("--predecessor-ledger")
    start.add_argument(
        "--inherited-finding",
        action="append",
        default=[],
        help="JSON object for one late finding inherited by a successor ledger",
    )
    start.add_argument(
        "--task-card",
        help=(
            "for a worker run, fail closed unless this exact task card binds "
            "the current candidate skill root and version"
        ),
    )

    record = commands.add_parser("record")
    record.add_argument("--ledger", required=True)
    record.add_argument("--input", required=True)
    record.add_argument("--finding-id")
    record.add_argument("--relations-input")

    finding = commands.add_parser("finding")
    finding.add_argument("--ledger", required=True)
    finding.add_argument("--input", required=True)

    reconcile = commands.add_parser("reconcile-finding")
    reconcile.add_argument("--ledger", required=True)
    reconcile.add_argument("--finding-id", required=True)
    reconcile.add_argument("--status", choices=sorted(FINDING_RECONCILIATIONS), required=True)
    reconcile.add_argument("--reason", required=True)
    reconcile.add_argument("--issue-id", default="")

    reconnaissance = commands.add_parser("record-reconnaissance")
    reconnaissance.add_argument("--ledger", required=True)
    reconnaissance.add_argument("--input", required=True)

    tactical = commands.add_parser(
        "record-tactical-repair",
        help="record a repair that remains local to one project run",
    )
    tactical.add_argument("--ledger", required=True)
    tactical.add_argument("--issue-id", required=True)
    tactical.add_argument("--reconnaissance-id", required=True)
    tactical.add_argument("--input", required=True)

    integrated = commands.add_parser("record-integrated-repair")
    integrated.add_argument("--ledger", required=True)
    integrated.add_argument("--input", required=True)

    dispose = commands.add_parser("dispose")
    dispose.add_argument("--ledger", required=True)
    dispose.add_argument("--issue-id", required=True)
    dispose.add_argument("--input", required=True)

    status = commands.add_parser("status")
    status.add_argument("--ledger", required=True)

    inventory = commands.add_parser(
        "inventory",
        help="read-only closure inventory for every project-local CHX ledger",
    )
    inventory.add_argument("--project-root", required=True)
    inventory.add_argument(
        "--full",
        action="store_true",
        help="include every validated ledger and predecessor-chain projection",
    )
    inventory.add_argument(
        "--current-run-id",
        action="append",
        default=[],
        help=(
            "exact live run known to Main; repeat as needed. The inventory "
            "never guesses liveness from age or an open bit"
        ),
    )

    ledger_disposition = commands.add_parser(
        "record-ledger-disposition",
        help="append a COW administrative terminal marker for an old open run",
    )
    ledger_disposition.add_argument("--project-root", required=True)
    ledger_disposition.add_argument("--run-id", required=True)
    ledger_disposition.add_argument(
        "--status",
        choices=sorted(LEDGER_ADMINISTRATIVE_STATUSES),
        required=True,
    )
    ledger_disposition.add_argument("--reason", required=True)
    ledger_disposition.add_argument("--successor-run-id")

    global_repair = commands.add_parser(
        "record-global-repair",
        help=(
            "record the direct integrated CHX repair for global installation "
            "or historical settlement; no tactical precursor"
        ),
    )
    global_repair.add_argument("--project-root", required=True)
    global_repair.add_argument("--input", required=True)

    verify_global = commands.add_parser(
        "verify-global-repair",
        help="verify the latest cross-ledger integrated CHX repair",
    )
    verify_global.add_argument("--project-root", required=True)

    close = commands.add_parser("close")
    close.add_argument("--ledger", required=True)

    report = commands.add_parser("report")
    report.add_argument("--ledger", required=True)
    report.add_argument("--output")

    verify_report = commands.add_parser("verify-report")
    verify_report.add_argument("--ledger", required=True)
    verify_report.add_argument("--report")

    verify_disclosure = commands.add_parser("verify-public-disclosure")
    verify_disclosure.add_argument("--ledger", required=True)
    verify_disclosure.add_argument("--skill-root")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "start":
        result = start_ledger(
            root=args.root,
            project_root=args.project_root,
            task=args.task,
            run_id=args.run_id,
            host_task_scope_id=args.host_task_scope_id,
            task_card=args.task_card,
            predecessor_ledger=args.predecessor_ledger,
            inherited_findings=[
                _json_file(path) for path in args.inherited_finding
            ],
        )
    elif args.command == "record":
        result = record_issue(
            args.ledger,
            _json_file(args.input),
            finding_id=args.finding_id,
            relations=(
                _json_list_file(args.relations_input)
                if args.relations_input
                else []
            ),
        )
    elif args.command == "finding":
        result = record_finding(args.ledger, _json_file(args.input))
    elif args.command == "reconcile-finding":
        result = reconcile_finding(
            args.ledger,
            finding_id=args.finding_id,
            status=args.status,
            reason=args.reason,
            issue_id=args.issue_id,
        )
    elif args.command == "record-reconnaissance":
        result = record_architecture_reconnaissance(
            args.ledger,
            _json_file(args.input),
        )
    elif args.command == "record-tactical-repair":
        result = record_tactical_repair(
            args.ledger,
            issue_id=args.issue_id,
            reconnaissance_id=args.reconnaissance_id,
            repair=_json_file(args.input),
        )
    elif args.command == "record-integrated-repair":
        result = record_integrated_repair(
            args.ledger,
            _json_file(args.input),
        )
    elif args.command == "dispose":
        result = dispose_issue(
            args.ledger,
            issue_id=args.issue_id,
            disposition=_json_file(args.input),
        )
    elif args.command == "status":
        result = ledger_status(args.ledger)
    elif args.command == "inventory":
        result = inventory_project_ledgers(
            args.project_root,
            full=args.full,
            current_run_ids=args.current_run_id,
        )
    elif args.command == "record-ledger-disposition":
        result = record_ledger_disposition(
            args.project_root,
            run_id=args.run_id,
            status=args.status,
            reason=args.reason,
            successor_run_id=args.successor_run_id,
        )
    elif args.command == "record-global-repair":
        result = record_global_repair(
            args.project_root,
            _json_file(args.input),
        )
    elif args.command == "verify-global-repair":
        result = verify_global_repair(args.project_root)
    elif args.command == "close":
        result = close_ledger(args.ledger)
    elif args.command == "report":
        result = write_architecture_report(args.ledger, args.output)
    elif args.command == "verify-report":
        result = verify_architecture_report(args.ledger, args.report)
    elif args.command == "verify-public-disclosure":
        result = verify_public_disclosure(args.ledger, args.skill_root)
    else:  # parser and dispatch must remain exactly closed
        raise ValueError(f"unsupported CHX command: {args.command}")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"CHX_LEDGER_ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)

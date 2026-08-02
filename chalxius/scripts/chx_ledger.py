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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

sys.dont_write_bytecode = True

from mathgraph.runtime_archive import (
    runtime_binding_from_root,
    validate_bound_runtime_at,
    validate_runtime_binding,
)


SCHEMA_VERSION = 1
LEGACY_CONTRACT_REVISION = "chalxius-chx-run-ledger-1"
PLACEMENT_CONTRACT_REVISION = "chalxius-chx-run-ledger-2"
FINDING_CONTRACT_REVISION = "chalxius-chx-run-ledger-3"
LINEAGE_CONTRACT_REVISION = "chalxius-chx-run-ledger-4"
CONTRACT_REVISION = LINEAGE_CONTRACT_REVISION
FINDING_CONTRACT_REVISIONS = frozenset(
    {FINDING_CONTRACT_REVISION, LINEAGE_CONTRACT_REVISION}
)
SUPPORTED_CONTRACT_REVISIONS = frozenset(
    {
        LEGACY_CONTRACT_REVISION,
        PLACEMENT_CONTRACT_REVISION,
        FINDING_CONTRACT_REVISION,
        LINEAGE_CONTRACT_REVISION,
    }
)
DEFAULT_PROJECT_LEDGER_DIR = "chx-ledgers"
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
SHA256_RE = re.compile(r"[0-9a-f]{64}")
PUBLIC_DISCLOSURE_CONTRACT_REVISION = "chalxius-chx-public-disclosure-2"


def _canonical_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _canonical_nfc_bytes(payload: Any) -> bytes:
    return _canonical_bytes(_normalize_unicode(payload))


def _normalize_unicode(value: Any) -> Any:
    """Return the NFC-normalized JSON value used by prospective v3 ids.

    Historical v1/v2 event bytes are never rewritten.  This normalization is
    applied only while computing new canonical bytes, which prevents two
    visually identical findings from acquiring different ids.
    """

    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [_normalize_unicode(item) for item in value]
    if isinstance(value, dict):
        return {
            _normalize_unicode(key): _normalize_unicode(item)
            for key, item in value.items()
        }
    return value


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _event_sha256(event: dict[str, Any]) -> str:
    return _sha256(
        _canonical_bytes(
            {key: value for key, value in event.items() if key != "event_sha256"}
        )
    )


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _require_text(value: Any, label: str, *, maximum: int = 8_192) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be nonempty text")
    if len(value) > maximum:
        raise ValueError(f"{label} exceeds {maximum} code points")
    return value


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
    runtime = validate_runtime_binding(card.get("runtime_binding"))
    if runtime != _runtime_binding():
        raise ValueError(
            "CHX worker runtime does not match the task-card candidate skill root/version"
        )
    validate_bound_runtime_at(
        Path(runtime["skill_root"]),
        runtime,
        verify_manifest_tree=True,
    )
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
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"run-{stamp}-{secrets.token_hex(6)}"


def _validate_run_id(run_id: Any) -> str:
    if not isinstance(run_id, str) or RUN_ID_RE.fullmatch(run_id) is None:
        raise ValueError("run_id is invalid")
    return run_id


def _with_hash(payload: dict[str, Any], previous: str) -> dict[str, Any]:
    record = {**payload, "previous_event_sha256": previous}
    return {**record, "event_sha256": _event_sha256(record)}


def _write_new_ledger(path: Path, event: dict[str, Any]) -> None:
    _write_new_ledger_events(path, [event])


def _write_new_ledger_events(path: Path, events: list[dict[str, Any]]) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            for event in events:
                handle.write(_canonical_bytes(event) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            path.unlink(missing_ok=True)
        finally:
            raise


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
    if contract_revision == LINEAGE_CONTRACT_REVISION:
        expected_start_keys = v4_start_keys
    elif contract_revision == FINDING_CONTRACT_REVISION:
        expected_start_keys = v3_start_keys
    else:
        expected_start_keys = legacy_start_keys
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
        if contract_revision == LINEAGE_CONTRACT_REVISION:
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
                if contract_revision == LINEAGE_CONTRACT_REVISION:
                    report_semantic["predecessor_lineage"] = start[
                        "predecessor_lineage"
                    ]
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
    return {
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
    if task_card is not None:
        _validate_task_card_runtime(task_card)
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
        if CONTRACT_REVISION == LINEAGE_CONTRACT_REVISION:
            start_payload["predecessor_lineage"] = predecessor_lineage
    elif predecessor_ledger is not None or inherited_findings:
        raise ValueError("legacy CHX ledger revisions do not support successors")
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
        "predecessor_issue_ids": status["predecessor_issue_ids"],
        "predecessor_lineage": status["predecessor_lineage"],
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
            if events[0]["contract_revision"] == LINEAGE_CONTRACT_REVISION:
                report_semantic["predecessor_lineage"] = events[0][
                    "predecessor_lineage"
                ]
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
    previous_run_id = ""
    for record in records:
        status = record["status"]
        if status.get("unreconciled_finding_ids"):
            raise ValueError("CHX publication has unreconciled findings")
        issues = status["issues"]
        if any(item["status"] != "resolved" for item in issues):
            raise ValueError("CHX publication contains an unresolved included issue")
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

    dispose = commands.add_parser("dispose")
    dispose.add_argument("--ledger", required=True)
    dispose.add_argument("--issue-id", required=True)
    dispose.add_argument("--input", required=True)

    status = commands.add_parser("status")
    status.add_argument("--ledger", required=True)

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
    elif args.command == "dispose":
        result = dispose_issue(
            args.ledger,
            issue_id=args.issue_id,
            disposition=_json_file(args.input),
        )
    elif args.command == "status":
        result = ledger_status(args.ledger)
    elif args.command == "close":
        result = close_ledger(args.ledger)
    elif args.command == "report":
        result = write_architecture_report(args.ledger, args.output)
    elif args.command == "verify-report":
        result = verify_architecture_report(args.ledger, args.report)
    else:
        result = verify_public_disclosure(args.ledger, args.skill_root)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"CHX_LEDGER_ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)

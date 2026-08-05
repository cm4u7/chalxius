#!/usr/bin/env python3
"""Operate the global Chalxius architecture-route reference ledger (PHX)."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import stat
import sys
from pathlib import Path
from typing import Any, Sequence

sys.dont_write_bytecode = True

from chx_ledger import _read_locked as _read_chx_locked
from operational_ledger_core import (
    canonical_bytes,
    canonical_nfc_bytes,
    event_sha256,
    mutate_locked,
    new_run_id,
    read_locked,
    require_text as _require_text,
    sha256,
    utc_now,
    with_hash,
    write_new_ledger_events,
)


SCHEMA_VERSION = 1
CONTRACT_REVISION = "chalxius-phx-architecture-route-ledger-1"
DEFAULT_GLOBAL_ROOT = Path.home() / ".codex" / "chalxius" / "phx-ledgers"
RUN_ID_RE = re.compile(r"run-[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
ROUTE_ID_RE = re.compile(r"PHX-[0-9]{3,}")
ROUTE_KEY_RE = re.compile(r"route\.[a-z][a-z0-9._-]{0,127}")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
MEASUREMENT_ID_RE = re.compile(r"measurement-[0-9a-f]{64}")
ADOPTION_ID_RE = re.compile(r"adoption-[0-9a-f]{64}")
CONSULTATION_ID_RE = re.compile(r"consultation-[0-9a-f]{64}")
ROUTE_DOMAINS = frozenset(
    {
        "coordination",
        "evidence_governance",
        "extensibility",
        "performance_cost",
        "release_deployment",
        "reliability",
        "research_workflow",
        "usability",
        "verification",
    }
)
ROUTE_ORIGINS = frozenset(
    {"architecture_review", "chx_synthesis", "measurement", "user_direction"}
)
ROUTE_KINDS = frozenset(
    {
        "measurement",
        "work_elimination",
        "scope_separation",
        "command_local_reuse",
        "persistent_index",
        "parallelism",
        "coordination",
        "architecture_reorganization",
        "automation",
        "deprecation",
        "governance_change",
        "interface_change",
        "lifecycle_change",
    }
)
RELATION_TYPES = frozenset(
    {"extends", "refines", "derived_from", "supersedes", "related_to"}
)
MEASUREMENT_OUTCOMES = frozenset({"supported", "not_supported", "inconclusive"})
EVALUATION_KINDS = frozenset(
    {
        "architecture_review",
        "benchmark",
        "compatibility_matrix",
        "operational_trace",
        "prototype",
        "reliability_matrix",
        "user_study",
    }
)
EVALUATION_MUTATION_SCOPES = frozenset(
    {"read_only", "isolated_sandbox", "active_architecture"}
)
CONSULTATION_DECISIONS = frozenset(
    {"approved", "approved_with_constraints", "declined", "deferred"}
)
IMPLEMENTATION_STATES = frozenset(
    {"not_started", "already_in_progress", "already_completed"}
)


def _text_list(
    value: Any,
    label: str,
    *,
    nonempty: bool,
    canonical: bool,
) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(f"{label} must be a list of nonempty strings")
    if nonempty and not value:
        raise ValueError(f"{label} must not be empty")
    if len(value) > 128:
        raise ValueError(f"{label} exceeds 128 entries")
    result = list(value)
    if canonical and result != sorted(set(result)):
        raise ValueError(f"{label} must be sorted and duplicate-free")
    return result


def _exact_object(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{label} fields are not exact")
    return dict(value)


def _load_json(path: Path | str, label: str) -> Any:
    candidate = Path(path).expanduser()
    if candidate.is_symlink() or not candidate.is_file():
        raise ValueError(f"{label} is missing or unsafe")
    return json.loads(candidate.read_text(encoding="utf-8"))


def _canonical_path(path: Path | str, label: str) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_symlink():
        raise ValueError(f"{label} must not be a symlink")
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    return candidate.resolve(strict=False)


def _skill_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _require_private_path(path: Path, *, mode: int, label: str) -> None:
    metadata = path.stat()
    if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != mode:
        raise ValueError(f"{label} must be user-owned with mode {mode:04o}")


def _safe_global_root(
    value: Path | str,
    *,
    project_roots: Sequence[Path | str] = (),
) -> Path:
    root = _canonical_path(value, "PHX root")
    skill = _skill_root()
    if root == skill or skill in root.parents:
        raise ValueError("PHX root must be outside the Chalxius skill")
    for project_value in project_roots:
        project = _canonical_path(project_value, "Chalxius project root")
        if root == project or project in root.parents:
            raise ValueError("global PHX root must be outside every project")
    if root.exists() and (root.is_symlink() or not root.is_dir()):
        raise ValueError("PHX root exists but is unsafe")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("PHX root is unsafe after creation")
    root_stat = root.stat()
    if root_stat.st_uid != os.getuid() or stat.S_IMODE(root_stat.st_mode) != 0o700:
        raise ValueError("PHX root must be user-owned with mode 0700")
    return root


def _common(
    *,
    event: str,
    run_id: str,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_revision": CONTRACT_REVISION,
        "event": event,
        "run_id": run_id,
        "occurred_at": utc_now(),
        "truth_effect": "none",
        "project_effect": "none",
        "premise_eligible": False,
    }


def _prefix_sha256(events: list[dict[str, Any]], index: int) -> str:
    return sha256(
        b"".join(canonical_bytes(event) + b"\n" for event in events[: index + 1])
    )


def _ledger_sha256(path: Path) -> str:
    return sha256(path.read_bytes())


def _split_qualified(
    value: Any,
    *,
    item_pattern: re.Pattern[str],
    label: str,
) -> tuple[str, str]:
    text = _require_text(value, label, maximum=256)
    if text.count("/") != 1:
        raise ValueError(f"{label} must be run-id/item-id")
    run_id, item_id = text.split("/", 1)
    if RUN_ID_RE.fullmatch(run_id) is None or item_pattern.fullmatch(item_id) is None:
        raise ValueError(f"{label} is invalid")
    return run_id, item_id


def _resolve_chx_ref(value: Any) -> dict[str, Any]:
    item = _exact_object(
        value,
        {"ledger_path", "qualified_issue_id"},
        "PHX source CHX reference",
    )
    path = _canonical_path(item["ledger_path"], "PHX source CHX ledger")
    events, status = _read_chx_locked(path)
    run_id, issue_id = _split_qualified(
        item["qualified_issue_id"],
        item_pattern=re.compile(r"CHX-[0-9]{3,}"),
        label="PHX source qualified CHX issue",
    )
    if status["run_id"] != run_id:
        raise ValueError("PHX source CHX run id mismatches its ledger")
    matches = [
        (index, event)
        for index, event in enumerate(events)
        if event.get("event") == "issue_observed"
        and event.get("issue_id") == issue_id
    ]
    if len(matches) != 1:
        raise ValueError("PHX source CHX issue is absent or duplicated")
    index, event = matches[0]
    closed = bool(status.get("closed", status.get("state") == "closed"))
    return {
        "qualified_issue_id": f"{run_id}/{issue_id}",
        "issue_event_sha256": event["event_sha256"],
        "target_event_prefix_sha256": _prefix_sha256(events, index),
        "target_contract_revision": events[0]["contract_revision"],
        "target_ledger_path": str(path),
        "target_ledger_closed": closed,
        "target_closed_ledger_sha256": _ledger_sha256(path) if closed else None,
    }


def _validate_stored_chx_ref(value: Any) -> dict[str, Any]:
    item = _exact_object(
        value,
        {
            "qualified_issue_id",
            "issue_event_sha256",
            "target_event_prefix_sha256",
            "target_contract_revision",
            "target_ledger_path",
            "target_ledger_closed",
            "target_closed_ledger_sha256",
        },
        "stored PHX CHX reference",
    )
    _split_qualified(
        item["qualified_issue_id"],
        item_pattern=re.compile(r"CHX-[0-9]{3,}"),
        label="stored qualified CHX issue",
    )
    for field in ("issue_event_sha256", "target_event_prefix_sha256"):
        if not isinstance(item[field], str) or SHA256_RE.fullmatch(item[field]) is None:
            raise ValueError(f"stored PHX CHX {field} is invalid")
    _require_text(item["target_contract_revision"], "CHX contract revision", maximum=128)
    path = Path(_require_text(item["target_ledger_path"], "CHX ledger path", maximum=4096))
    if not path.is_absolute():
        raise ValueError("stored CHX ledger path must be absolute")
    if not isinstance(item["target_ledger_closed"], bool):
        raise ValueError("stored CHX closed state must be boolean")
    closed_hash = item["target_closed_ledger_sha256"]
    if item["target_ledger_closed"]:
        if not isinstance(closed_hash, str) or SHA256_RE.fullmatch(closed_hash) is None:
            raise ValueError("closed CHX reference lacks its ledger hash")
    elif closed_hash is not None:
        raise ValueError("active CHX reference cannot claim a closed ledger hash")
    return item


def _route_input(value: Any) -> dict[str, Any]:
    item = _exact_object(
        value,
        {
            "route_key",
            "title",
            "summary",
            "route_domain",
            "route_kind",
            "origin",
            "applicability_signals",
            "measurement_plan",
            "implementation_options",
            "fail_closed_boundaries",
            "source_chx_refs",
            "relations",
        },
        "PHX route input",
    )
    if not isinstance(item["route_key"], str) or ROUTE_KEY_RE.fullmatch(item["route_key"]) is None:
        raise ValueError("PHX route key is invalid")
    item["title"] = _require_text(item["title"], "PHX route title", maximum=256)
    item["summary"] = _require_text(item["summary"], "PHX route summary")
    if item["route_domain"] not in ROUTE_DOMAINS:
        raise ValueError("PHX route domain is invalid")
    if item["route_kind"] not in ROUTE_KINDS:
        raise ValueError("PHX route kind is invalid")
    if item["origin"] not in ROUTE_ORIGINS:
        raise ValueError("PHX route origin is invalid")
    item["applicability_signals"] = _text_list(
        item["applicability_signals"], "PHX applicability signals", nonempty=True, canonical=True
    )
    item["measurement_plan"] = _text_list(
        item["measurement_plan"], "PHX measurement plan", nonempty=True, canonical=False
    )
    item["implementation_options"] = _text_list(
        item["implementation_options"], "PHX implementation options", nonempty=True, canonical=False
    )
    item["fail_closed_boundaries"] = _text_list(
        item["fail_closed_boundaries"], "PHX fail-closed boundaries", nonempty=True, canonical=True
    )
    if not isinstance(item["source_chx_refs"], list):
        raise ValueError("PHX source CHX refs must be a list")
    if item["origin"] == "chx_synthesis" and not item["source_chx_refs"]:
        raise ValueError("CHX-synthesized PHX route requires source CHX references")
    if not isinstance(item["relations"], list):
        raise ValueError("PHX relations must be a list")
    return item


def _measurement_input(value: Any) -> dict[str, Any]:
    item = _exact_object(
        value,
        {
            "route_id",
            "scope",
            "operation",
            "requested_projection",
            "evaluation_kind",
            "mutation_scope",
            "authorization_consultation_id_or_null",
            "authorization_scope_acknowledged_or_null",
            "consultation_constraints_acknowledged",
            "measurement_method",
            "runtime_identity_sha256_or_null",
            "project_snapshot_sha256_or_null",
            "outcome",
            "metrics",
            "observations",
            "evidence_sha256s",
        },
        "PHX measurement input",
    )
    if not isinstance(item["route_id"], str) or ROUTE_ID_RE.fullmatch(item["route_id"]) is None:
        raise ValueError("PHX measurement route id is invalid")
    for field in ("scope", "operation", "requested_projection", "measurement_method"):
        item[field] = _require_text(item[field], f"PHX measurement {field}")
    if item["evaluation_kind"] not in EVALUATION_KINDS:
        raise ValueError("PHX evaluation kind is invalid")
    if item["mutation_scope"] not in EVALUATION_MUTATION_SCOPES:
        raise ValueError("PHX evaluation mutation scope is invalid")
    authorization = item["authorization_consultation_id_or_null"]
    if authorization is not None and (
        not isinstance(authorization, str)
        or CONSULTATION_ID_RE.fullmatch(authorization) is None
    ):
        raise ValueError("PHX evaluation authorization consultation id is invalid")
    if item["mutation_scope"] == "active_architecture" and authorization is None:
        raise ValueError("active-architecture PHX evaluation requires prior user authorization")
    if item["mutation_scope"] != "active_architecture" and authorization is not None:
        raise ValueError("nonmutating PHX evaluation must not claim architecture authorization")
    acknowledged_scope = item["authorization_scope_acknowledged_or_null"]
    if acknowledged_scope is not None:
        acknowledged_scope = _require_text(
            acknowledged_scope, "PHX evaluation acknowledged authorization scope"
        )
    item["authorization_scope_acknowledged_or_null"] = acknowledged_scope
    item["consultation_constraints_acknowledged"] = _text_list(
        item["consultation_constraints_acknowledged"],
        "PHX evaluation acknowledged consultation constraints",
        nonempty=False,
        canonical=True,
    )
    if item["mutation_scope"] == "active_architecture" and acknowledged_scope is None:
        raise ValueError("active-architecture PHX evaluation must acknowledge authorization scope")
    if item["mutation_scope"] != "active_architecture" and (
        acknowledged_scope is not None or item["consultation_constraints_acknowledged"]
    ):
        raise ValueError("nonmutating PHX evaluation cannot claim architecture scope")
    for field in ("runtime_identity_sha256_or_null", "project_snapshot_sha256_or_null"):
        value_or_null = item[field]
        if value_or_null is not None and (
            not isinstance(value_or_null, str) or SHA256_RE.fullmatch(value_or_null) is None
        ):
            raise ValueError(f"PHX measurement {field} is invalid")
    if item["outcome"] not in MEASUREMENT_OUTCOMES:
        raise ValueError("PHX measurement outcome is invalid")
    if not isinstance(item["metrics"], list):
        raise ValueError("PHX measurement metrics must be a list")
    metrics: list[dict[str, Any]] = []
    for metric in item["metrics"]:
        normalized = _exact_object(metric, {"name", "value", "unit"}, "PHX metric")
        normalized["name"] = _require_text(normalized["name"], "PHX metric name", maximum=128)
        normalized["unit"] = _require_text(normalized["unit"], "PHX metric unit", maximum=64)
        if isinstance(normalized["value"], bool) or not isinstance(normalized["value"], (int, float)):
            raise ValueError("PHX metric value must be numeric")
        if not math.isfinite(float(normalized["value"])):
            raise ValueError("PHX metric value must be finite")
        metrics.append(normalized)
    if [item["name"] for item in metrics] != sorted({item["name"] for item in metrics}):
        raise ValueError("PHX metrics must be name-sorted and unique")
    item["metrics"] = metrics
    item["observations"] = _text_list(
        item["observations"], "PHX observations", nonempty=True, canonical=True
    )
    hashes = item["evidence_sha256s"]
    if not isinstance(hashes, list) or any(
        not isinstance(value, str) or SHA256_RE.fullmatch(value) is None for value in hashes
    ) or hashes != sorted(set(hashes)):
        raise ValueError("PHX evidence hashes must be sorted unique SHA-256 values")
    if item["outcome"] == "supported" and not hashes:
        raise ValueError("supported PHX evaluation requires digest-bound evidence")
    return item


def _adoption_input(value: Any) -> dict[str, Any]:
    item = _exact_object(
        value,
        {
            "route_id",
            "measurement_id",
            "consultation_id",
            "consultation_constraints_acknowledged",
            "authorization_scope_acknowledged",
            "implementation_summary",
            "applicability",
            "implementation_anchors",
            "implementation_evidence_sha256s",
            "regression_evidence",
            "regression_evidence_sha256s",
            "residual_boundaries",
        },
        "PHX adoption input",
    )
    if not isinstance(item["route_id"], str) or ROUTE_ID_RE.fullmatch(item["route_id"]) is None:
        raise ValueError("PHX adoption route id is invalid")
    if not isinstance(item["measurement_id"], str) or MEASUREMENT_ID_RE.fullmatch(item["measurement_id"]) is None:
        raise ValueError("PHX adoption measurement id is invalid")
    if not isinstance(item["consultation_id"], str) or CONSULTATION_ID_RE.fullmatch(item["consultation_id"]) is None:
        raise ValueError("PHX adoption consultation id is invalid")
    item["consultation_constraints_acknowledged"] = _text_list(
        item["consultation_constraints_acknowledged"],
        "PHX acknowledged consultation constraints",
        nonempty=False,
        canonical=True,
    )
    item["authorization_scope_acknowledged"] = _require_text(
        item["authorization_scope_acknowledged"],
        "PHX acknowledged authorization scope",
    )
    item["implementation_summary"] = _require_text(
        item["implementation_summary"], "PHX implementation summary"
    )
    item["applicability"] = _require_text(item["applicability"], "PHX adoption applicability")
    for field in ("implementation_anchors", "regression_evidence", "residual_boundaries"):
        item[field] = _text_list(
            item[field], f"PHX adoption {field}", nonempty=True, canonical=True
        )
    for field in ("implementation_evidence_sha256s", "regression_evidence_sha256s"):
        hashes = item[field]
        if (
            not isinstance(hashes, list)
            or not hashes
            or any(
                not isinstance(value, str) or SHA256_RE.fullmatch(value) is None
                for value in hashes
            )
            or hashes != sorted(set(hashes))
        ):
            raise ValueError(f"PHX adoption {field} must be nonempty sorted SHA-256 values")
    return item


def _consultation_input(value: Any) -> dict[str, Any]:
    item = _exact_object(
        value,
        {
            "route_id",
            "proposal_summary",
            "user_question",
            "user_response",
            "user_response_sha256",
            "decision",
            "constraints",
            "consultation_context",
            "host_task_scope_id",
            "user_turn_locator",
            "authorization_scope",
            "implementation_state_at_consultation",
            "presented_alternatives",
            "expected_benefits",
            "costs_and_risks",
            "migration_or_rollback",
        },
        "PHX consultation input",
    )
    if not isinstance(item["route_id"], str) or ROUTE_ID_RE.fullmatch(item["route_id"]) is None:
        raise ValueError("PHX consultation route id is invalid")
    for field in (
        "proposal_summary",
        "user_question",
        "user_response",
        "consultation_context",
        "host_task_scope_id",
        "user_turn_locator",
        "authorization_scope",
    ):
        item[field] = _require_text(item[field], f"PHX consultation {field}")
    response_sha256 = item["user_response_sha256"]
    if not isinstance(response_sha256, str) or SHA256_RE.fullmatch(response_sha256) is None:
        raise ValueError("PHX consultation user response SHA-256 is invalid")
    if response_sha256 != sha256(item["user_response"].encode("utf-8")):
        raise ValueError("PHX consultation user response SHA-256 mismatches the response")
    if item["decision"] not in CONSULTATION_DECISIONS:
        raise ValueError("PHX consultation decision is invalid")
    if item["implementation_state_at_consultation"] not in IMPLEMENTATION_STATES:
        raise ValueError("PHX consultation implementation state is invalid")
    if (
        item["decision"] in {"approved", "approved_with_constraints"}
        and item["implementation_state_at_consultation"] != "not_started"
    ):
        raise ValueError("PHX approval must precede implementation")
    for field in (
        "presented_alternatives",
        "expected_benefits",
        "costs_and_risks",
        "migration_or_rollback",
    ):
        item[field] = _text_list(
            item[field],
            f"PHX consultation {field}",
            nonempty=True,
            canonical=True,
        )
    if len(item["presented_alternatives"]) < 2:
        raise ValueError("PHX consultation must present at least two alternatives")
    item["constraints"] = _text_list(
        item["constraints"],
        "PHX consultation constraints",
        nonempty=item["decision"] == "approved_with_constraints",
        canonical=True,
    )
    return item


def _measurement_id(payload: dict[str, Any]) -> str:
    return "measurement-" + sha256(canonical_nfc_bytes(payload))


def _adoption_id(payload: dict[str, Any]) -> str:
    return "adoption-" + sha256(canonical_nfc_bytes(payload))


def _consultation_id(payload: dict[str, Any]) -> str:
    return "consultation-" + sha256(canonical_nfc_bytes(payload))


def _validate_common_event(
    event: dict[str, Any],
    *,
    previous: str,
    run_id: str,
) -> None:
    if event.get("schema_version") != SCHEMA_VERSION or event.get("contract_revision") != CONTRACT_REVISION:
        raise ValueError("PHX event contract mismatch")
    if event.get("run_id") != run_id:
        raise ValueError("PHX event run binding mismatch")
    _require_text(event.get("occurred_at"), "PHX occurred_at", maximum=64)
    if event.get("truth_effect") != "none" or event.get("project_effect") != "none" or event.get("premise_eligible") is not False:
        raise ValueError("PHX event authority fields are invalid")
    if event.get("previous_event_sha256") != previous:
        raise ValueError("PHX event predecessor hash mismatch")
    if event.get("event_sha256") != event_sha256(event):
        raise ValueError("PHX event hash mismatch")


def _route_semantic(event: dict[str, Any]) -> dict[str, Any]:
    return {
        key: event[key]
        for key in (
            "route_key",
            "title",
            "summary",
            "route_domain",
            "route_kind",
            "origin",
            "applicability_signals",
            "measurement_plan",
            "implementation_options",
            "fail_closed_boundaries",
            "source_chx_refs",
            "relations",
        )
    }


def _route_request_identity(value: dict[str, Any]) -> dict[str, Any]:
    """Return the stable request identity without replaying mutable target ledgers."""

    source_rows: list[dict[str, str]] = []
    for raw in value["source_chx_refs"]:
        item = _exact_object(
            raw,
            {"ledger_path", "qualified_issue_id"},
            "PHX source CHX reference",
        )
        source_rows.append(
            {
                "qualified_issue_id": _require_text(
                    item["qualified_issue_id"],
                    "PHX source qualified CHX issue",
                    maximum=256,
                ),
                "target_ledger_path": str(
                    _canonical_path(item["ledger_path"], "PHX source CHX ledger")
                ),
            }
        )
    source_refs = sorted(
        source_rows,
        key=lambda item: (item["qualified_issue_id"], item["target_ledger_path"]),
    )
    relation_rows: list[dict[str, str]] = []
    for raw in value["relations"]:
        item = _exact_object(
            raw,
            {"relation_type", "target_qualified_id", "target_ledger_path"},
            "PHX route relation",
        )
        relation_rows.append(
            {
                "relation_type": _require_text(
                    item["relation_type"], "PHX relation type", maximum=64
                ),
                "target_qualified_id": _require_text(
                    item["target_qualified_id"],
                    "PHX relation target",
                    maximum=256,
                ),
                "target_ledger_path": str(
                    _canonical_path(item["target_ledger_path"], "PHX relation ledger")
                ),
            }
        )
    relations = sorted(
        relation_rows,
        key=lambda item: (
            item["relation_type"],
            item["target_qualified_id"],
            item["target_ledger_path"],
        ),
    )
    return {
        **{
            key: value[key]
            for key in (
                "route_key",
                "title",
                "summary",
                "route_domain",
                "route_kind",
                "origin",
                "applicability_signals",
                "measurement_plan",
                "implementation_options",
                "fail_closed_boundaries",
            )
        },
        "source_chx_refs": source_refs,
        "relations": relations,
    }


def _stored_route_request_identity(event: dict[str, Any]) -> dict[str, Any]:
    return {
        **{
            key: event[key]
            for key in (
                "route_key",
                "title",
                "summary",
                "route_domain",
                "route_kind",
                "origin",
                "applicability_signals",
                "measurement_plan",
                "implementation_options",
                "fail_closed_boundaries",
            )
        },
        "source_chx_refs": sorted(
            (
                {
                    "qualified_issue_id": item["qualified_issue_id"],
                    "target_ledger_path": item["target_ledger_path"],
                }
                for item in event["source_chx_refs"]
            ),
            key=lambda item: (item["qualified_issue_id"], item["target_ledger_path"]),
        ),
        "relations": sorted(
            (
                {
                    "relation_type": item["relation_type"],
                    "target_qualified_id": item["target_qualified_id"],
                    "target_ledger_path": item["target_ledger_path"],
                }
                for item in event["relations"]
            ),
            key=lambda item: (
                item["relation_type"],
                item["target_qualified_id"],
                item["target_ledger_path"],
            ),
        ),
    }


def _validate_events(events: list[dict[str, Any]], *, ledger_path: Path) -> None:
    if not events:
        raise ValueError("PHX ledger is empty")
    first = events[0]
    if first.get("event") != "run_started":
        raise ValueError("PHX ledger must begin with run_started")
    run_id = first.get("run_id")
    if not isinstance(run_id, str) or RUN_ID_RE.fullmatch(run_id) is None:
        raise ValueError("PHX run id is invalid")
    canonical_ledger = _canonical_path(ledger_path, "PHX ledger")
    if canonical_ledger.name != f"{run_id}.jsonl":
        raise ValueError("PHX ledger filename does not match its run id")
    routes: dict[str, dict[str, Any]] = {}
    route_keys: set[str] = set()
    measurements: dict[str, dict[str, Any]] = {}
    consultations: dict[str, dict[str, Any]] = {}
    adoptions: dict[str, dict[str, Any]] = {}
    previous = "0" * 64
    closed = False
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise ValueError("PHX event must be an object")
        _validate_common_event(event, previous=previous, run_id=run_id)
        previous = event["event_sha256"]
        kind = event.get("event")
        if closed:
            raise ValueError("PHX ledger has events after close")
        common = {
            "schema_version", "contract_revision", "event", "run_id",
            "occurred_at", "truth_effect", "project_effect", "premise_eligible",
            "previous_event_sha256", "event_sha256",
        }
        if kind == "run_started":
            if index != 0 or set(event) != common | {"scope_id", "global_root"}:
                raise ValueError("PHX run_started fields are not exact")
            _require_text(event["scope_id"], "PHX scope id", maximum=512)
            root = Path(_require_text(event["global_root"], "PHX global root", maximum=4096))
            if not root.is_absolute():
                raise ValueError("PHX global root must be absolute")
            if _canonical_path(root, "PHX global root") != root:
                raise ValueError("PHX global root is not canonical")
            if canonical_ledger.parent != root:
                raise ValueError("PHX ledger is outside its bound global root")
        elif kind == "route_recorded":
            expected = common | {
                "route_id", "route_key", "title", "summary", "route_kind",
                "route_domain", "origin",
                "applicability_signals", "measurement_plan", "implementation_options",
                "fail_closed_boundaries", "source_chx_refs", "relations",
            }
            if set(event) != expected:
                raise ValueError("PHX route event fields are not exact")
            expected_id = f"PHX-{len(routes) + 1:03d}"
            if event["route_id"] != expected_id:
                raise ValueError("PHX route ids must be run-local and continuous")
            normalized = _route_input({
                key: event[key] for key in expected - common - {"route_id"}
            })
            if normalized["route_key"] in route_keys:
                raise ValueError("PHX route key is duplicated")
            route_keys.add(normalized["route_key"])
            for ref in event["source_chx_refs"]:
                _validate_stored_chx_ref(ref)
            if event["relations"] != sorted(
                event["relations"], key=lambda item: (item["relation_type"], item["target_qualified_id"])
            ):
                raise ValueError("PHX route relations are not canonical")
            for relation in event["relations"]:
                _validate_stored_relation(relation)
            routes[event["route_id"]] = event
        elif kind == "measurement_recorded":
            expected = common | {
                "measurement_id", "route_id", "scope", "operation",
                "requested_projection", "evaluation_kind", "measurement_method",
                "mutation_scope", "authorization_consultation_id_or_null",
                "authorization_scope_acknowledged_or_null",
                "consultation_constraints_acknowledged",
                "runtime_identity_sha256_or_null", "project_snapshot_sha256_or_null",
                "outcome", "metrics", "observations", "evidence_sha256s",
            }
            if set(event) != expected:
                raise ValueError("PHX measurement event fields are not exact")
            semantic = {key: event[key] for key in expected - common - {"measurement_id"}}
            normalized = _measurement_input(semantic)
            if normalized["route_id"] not in routes:
                raise ValueError("PHX measurement names an unknown route")
            authorization = normalized["authorization_consultation_id_or_null"]
            if normalized["mutation_scope"] == "active_architecture":
                consultation = consultations.get(authorization)
                route_consultations = [
                    item for item in consultations.values()
                    if item["route_id"] == normalized["route_id"]
                ]
                if (
                    consultation is None
                    or consultation["route_id"] != normalized["route_id"]
                    or consultation["decision"]
                    not in {"approved", "approved_with_constraints"}
                    or not route_consultations
                    or route_consultations[-1]["consultation_id"] != authorization
                ):
                    raise ValueError(
                        "active-architecture PHX evaluation lacks latest user authorization"
                    )
                if (
                    normalized["authorization_scope_acknowledged_or_null"]
                    != consultation["authorization_scope"]
                    or normalized["consultation_constraints_acknowledged"]
                    != consultation["constraints"]
                ):
                    raise ValueError(
                        "active-architecture PHX evaluation drifts from user authorization"
                    )
            if event["measurement_id"] != _measurement_id(normalized):
                raise ValueError("PHX measurement id mismatch")
            if event["measurement_id"] in measurements:
                raise ValueError("PHX measurement is duplicated")
            measurements[event["measurement_id"]] = event
        elif kind == "consultation_recorded":
            expected = common | {
                "consultation_id", "route_id", "proposal_summary",
                "user_question", "user_response", "user_response_sha256",
                "decision", "constraints", "consultation_context",
                "host_task_scope_id", "user_turn_locator", "authorization_scope",
                "implementation_state_at_consultation",
                "presented_alternatives", "expected_benefits",
                "costs_and_risks", "migration_or_rollback",
            }
            if set(event) != expected:
                raise ValueError("PHX consultation event fields are not exact")
            semantic = {
                key: event[key] for key in expected - common - {"consultation_id"}
            }
            normalized = _consultation_input(semantic)
            if normalized["route_id"] not in routes:
                raise ValueError("PHX consultation names an unknown route")
            if normalized["route_id"] in adoptions:
                raise ValueError("PHX cannot reconsider a route after its adoption record")
            if event["consultation_id"] != _consultation_id(normalized):
                raise ValueError("PHX consultation id mismatch")
            if event["consultation_id"] in consultations:
                raise ValueError("PHX consultation is duplicated")
            consultations[event["consultation_id"]] = event
        elif kind == "adoption_recorded":
            expected = common | {
                "adoption_id", "route_id", "measurement_id", "consultation_id",
                "consultation_constraints_acknowledged",
                "authorization_scope_acknowledged",
                "implementation_summary", "applicability", "implementation_anchors",
                "implementation_evidence_sha256s", "regression_evidence",
                "regression_evidence_sha256s", "residual_boundaries",
            }
            if set(event) != expected:
                raise ValueError("PHX adoption event fields are not exact")
            semantic = {key: event[key] for key in expected - common - {"adoption_id"}}
            normalized = _adoption_input(semantic)
            measurement = measurements.get(normalized["measurement_id"])
            if measurement is None or measurement["route_id"] != normalized["route_id"]:
                raise ValueError("PHX adoption lacks its route measurement")
            if measurement["outcome"] != "supported":
                raise ValueError("PHX adoption requires a supporting measurement")
            consultation = consultations.get(normalized["consultation_id"])
            if consultation is None or consultation["route_id"] != normalized["route_id"]:
                raise ValueError("PHX adoption lacks its route user consultation")
            if consultation["decision"] not in {"approved", "approved_with_constraints"}:
                raise ValueError("PHX architecture adoption requires user approval")
            route_consultations = [
                item for item in consultations.values()
                if item["route_id"] == normalized["route_id"]
            ]
            if not route_consultations or route_consultations[-1]["consultation_id"] != normalized["consultation_id"]:
                raise ValueError("PHX adoption must bind the latest route consultation")
            if normalized["consultation_constraints_acknowledged"] != consultation["constraints"]:
                raise ValueError("PHX adoption does not acknowledge the approved constraints")
            if normalized["authorization_scope_acknowledged"] != consultation["authorization_scope"]:
                raise ValueError("PHX adoption exceeds or drifts from the authorized scope")
            if normalized["route_id"] in adoptions:
                raise ValueError("PHX route already has an adoption")
            if event["adoption_id"] != _adoption_id(normalized):
                raise ValueError("PHX adoption id mismatch")
            adoptions[normalized["route_id"]] = event
        elif kind == "run_closed":
            expected = common | {
                "route_ids", "measurement_ids", "consultation_ids",
                "adoption_ids", "report_required",
            }
            if set(event) != expected:
                raise ValueError("PHX close event fields are not exact")
            if event["route_ids"] != list(routes):
                raise ValueError("PHX close route set mismatch")
            if event["measurement_ids"] != list(measurements):
                raise ValueError("PHX close measurement set mismatch")
            if event["consultation_ids"] != list(consultations):
                raise ValueError("PHX close consultation set mismatch")
            expected_adoptions = [adoptions[key]["adoption_id"] for key in routes if key in adoptions]
            if event["adoption_ids"] != expected_adoptions:
                raise ValueError("PHX close adoption set mismatch")
            if event["report_required"] is not bool(routes):
                raise ValueError("PHX close report requirement mismatch")
            closed = True
        else:
            raise ValueError(f"unknown PHX event: {kind}")


def _parse_events(raw: str, ledger_path: Path) -> list[dict[str, Any]]:
    if not raw or not raw.endswith("\n"):
        raise ValueError("PHX ledger is empty or lacks a complete final line")
    events: list[dict[str, Any]] = []
    for number, line in enumerate(raw.splitlines(), 1):
        if not line:
            raise ValueError(f"PHX ledger line {number} is blank")
        event = json.loads(line)
        if not isinstance(event, dict):
            raise ValueError(f"PHX ledger line {number} must be an object")
        events.append(event)
    _validate_events(events, ledger_path=ledger_path)
    return events


def _status(events: list[dict[str, Any]], ledger_path: Path) -> dict[str, Any]:
    routes = [event for event in events if event["event"] == "route_recorded"]
    measurements = [event for event in events if event["event"] == "measurement_recorded"]
    consultations = [event for event in events if event["event"] == "consultation_recorded"]
    adoptions = [event for event in events if event["event"] == "adoption_recorded"]
    measurement_by_route: dict[str, list[dict[str, Any]]] = {}
    for event in measurements:
        measurement_by_route.setdefault(event["route_id"], []).append(event)
    adoption_by_route = {event["route_id"]: event for event in adoptions}
    consultation_by_route: dict[str, list[dict[str, Any]]] = {}
    for event in consultations:
        consultation_by_route.setdefault(event["route_id"], []).append(event)
    prefix_hasher = hashlib.sha256()
    event_prefixes: dict[str, str] = {}
    for event in events:
        prefix_hasher.update(canonical_bytes(event) + b"\n")
        event_prefixes[event["event_sha256"]] = prefix_hasher.hexdigest()
    rows = []
    for route in routes:
        route_measurements = measurement_by_route.get(route["route_id"], [])
        rows.append(
            {
                "route_id": route["route_id"],
                "qualified_route_id": f"{events[0]['run_id']}/{route['route_id']}",
                "route_key": route["route_key"],
                "route_event_sha256": route["event_sha256"],
                "route_event_prefix_sha256": event_prefixes[route["event_sha256"]],
                "title": route["title"],
                "route_domain": route["route_domain"],
                "route_kind": route["route_kind"],
                "origin": route["origin"],
                "measurement_count": len(route_measurements),
                "latest_measurement_outcome": (
                    route_measurements[-1]["outcome"] if route_measurements else "unmeasured"
                ),
                "adopted": route["route_id"] in adoption_by_route,
                "latest_consultation_decision": (
                    consultation_by_route[route["route_id"]][-1]["decision"]
                    if route["route_id"] in consultation_by_route
                    else "not_consulted"
                ),
                "relations": route["relations"],
                "source_chx_refs": route["source_chx_refs"],
                "implementation_requires_user_consultation": True,
            }
        )
    closed = events[-1]["event"] == "run_closed"
    global_root = Path(events[0]["global_root"])
    root_scope = (
        "canonical_global"
        if global_root == _canonical_path(DEFAULT_GLOBAL_ROOT, "canonical PHX root")
        else "custom_expert"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_revision": CONTRACT_REVISION,
        "run_id": events[0]["run_id"],
        "scope_id": events[0]["scope_id"],
        "global_root": str(global_root),
        "root_scope": root_scope,
        "ledger_path": str(ledger_path),
        "ledger_sha256": _ledger_sha256(ledger_path),
        "closed": closed,
        "report_required": bool(routes) if closed else None,
        "route_count": len(routes),
        "measurement_count": len(measurements),
        "consultation_count": len(consultations),
        "adoption_count": len(adoptions),
        "routes": rows,
        "truth_effect": "none",
        "project_effect": "none",
        "premise_eligible": False,
        "architecture_change_requires_user_consultation": True,
    }


def _read_ledger(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    path = _canonical_path(path, "PHX ledger")
    if path.is_symlink() or not path.is_file():
        raise ValueError("PHX ledger path is missing or unsafe")
    _require_private_path(path, mode=0o600, label="PHX ledger")
    return read_locked(
        path,
        label="PHX",
        parser=_parse_events,
        status_builder=_status,
    )


def _mutate(
    path: Path,
    builder: Any,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    path = _canonical_path(path, "PHX ledger")
    if path.is_symlink() or not path.is_file():
        raise ValueError("PHX ledger path is missing or unsafe")
    _require_private_path(path, mode=0o600, label="PHX ledger")
    return mutate_locked(
        path,
        label="PHX",
        parser=_parse_events,
        status_builder=_status,
        builder=builder,
    )


def _validate_stored_relation(value: Any) -> dict[str, Any]:
    item = _exact_object(
        value,
        {
            "relation_type", "target_qualified_id", "target_route_event_sha256",
            "target_event_prefix_sha256", "target_ledger_path",
            "target_ledger_closed", "target_closed_ledger_sha256",
        },
        "stored PHX relation",
    )
    if item["relation_type"] not in RELATION_TYPES:
        raise ValueError("PHX relation type is invalid")
    _split_qualified(
        item["target_qualified_id"], item_pattern=ROUTE_ID_RE, label="PHX relation target"
    )
    for field in ("target_route_event_sha256", "target_event_prefix_sha256"):
        if not isinstance(item[field], str) or SHA256_RE.fullmatch(item[field]) is None:
            raise ValueError(f"PHX relation {field} is invalid")
    path = Path(_require_text(item["target_ledger_path"], "PHX relation ledger path", maximum=4096))
    if not path.is_absolute():
        raise ValueError("PHX relation ledger path must be absolute")
    if not isinstance(item["target_ledger_closed"], bool):
        raise ValueError("PHX relation closed state is invalid")
    closed_hash = item["target_closed_ledger_sha256"]
    if item["target_ledger_closed"]:
        if not isinstance(closed_hash, str) or SHA256_RE.fullmatch(closed_hash) is None:
            raise ValueError("PHX closed relation lacks a ledger hash")
    elif closed_hash is not None:
        raise ValueError("PHX active relation cannot claim a closed ledger hash")
    return item


def _resolve_relation(
    value: Any,
    *,
    current_path: Path,
    current_events: list[dict[str, Any]],
) -> dict[str, Any]:
    item = _exact_object(
        value,
        {"relation_type", "target_qualified_id", "target_ledger_path"},
        "PHX route relation",
    )
    if item["relation_type"] not in RELATION_TYPES:
        raise ValueError("PHX relation type is invalid")
    target_path = _canonical_path(item["target_ledger_path"], "PHX relation ledger")
    target_run, target_id = _split_qualified(
        item["target_qualified_id"], item_pattern=ROUTE_ID_RE, label="PHX relation target"
    )
    if target_path == current_path:
        events = current_events
        status = _status(events, current_path)
    else:
        events, status = _read_ledger(target_path)
        if not status["closed"]:
            raise ValueError("cross-run PHX relation target must be closed")
    if status["run_id"] != target_run:
        raise ValueError("PHX relation target run mismatches its ledger")
    matches = [
        (index, event)
        for index, event in enumerate(events)
        if event.get("event") == "route_recorded" and event.get("route_id") == target_id
    ]
    if len(matches) != 1:
        raise ValueError("PHX relation target route is absent or duplicated")
    index, target = matches[0]
    closed = bool(status["closed"])
    return {
        "relation_type": item["relation_type"],
        "target_qualified_id": f"{target_run}/{target_id}",
        "target_route_event_sha256": target["event_sha256"],
        "target_event_prefix_sha256": _prefix_sha256(events, index),
        "target_ledger_path": str(target_path),
        "target_ledger_closed": closed,
        "target_closed_ledger_sha256": _ledger_sha256(target_path) if closed else None,
    }


def start(
    *,
    root: Path,
    scope_id: str,
    project_roots: Sequence[Path | str] = (),
    allow_custom_root: bool = False,
) -> dict[str, Any]:
    requested_root = _canonical_path(root, "PHX root")
    canonical_default = _canonical_path(DEFAULT_GLOBAL_ROOT, "canonical PHX root")
    if requested_root != canonical_default:
        if not allow_custom_root:
            raise ValueError("custom PHX root requires explicit expert authorization")
        if not project_roots:
            raise ValueError("custom PHX root requires declared project roots")
    global_root = _safe_global_root(root, project_roots=project_roots)
    run_id = new_run_id()
    path = global_root / f"{run_id}.jsonl"
    payload = {
        **_common(event="run_started", run_id=run_id),
        "scope_id": _require_text(scope_id, "PHX scope id", maximum=512),
        "global_root": str(global_root),
    }
    event = with_hash(payload, "0" * 64)
    write_new_ledger_events(path, [event])
    _, status = _read_ledger(path)
    return status


def record_route(path: Path, value: Any) -> dict[str, Any]:
    path = _canonical_path(path, "PHX ledger")
    normalized = _route_input(value)
    requested_identity = _route_request_identity(normalized)

    def builder(events: list[dict[str, Any]]) -> dict[str, Any] | None:
        if events[-1]["event"] == "run_closed":
            raise ValueError("PHX ledger is closed")
        existing = [
            event for event in events
            if event.get("event") == "route_recorded"
            and event.get("route_key") == normalized["route_key"]
        ]
        if existing:
            if _stored_route_request_identity(existing[0]) != requested_identity:
                raise ValueError("PHX route key already exists with different semantics")
            return None
        source_refs = sorted(
            (_resolve_chx_ref(item) for item in normalized["source_chx_refs"]),
            key=lambda item: item["qualified_issue_id"],
        )
        if len(source_refs) != len({item["qualified_issue_id"] for item in source_refs}):
            raise ValueError("PHX source CHX reference is duplicated")
        relations = sorted(
            (
                _resolve_relation(item, current_path=path, current_events=events)
                for item in normalized["relations"]
            ),
            key=lambda item: (item["relation_type"], item["target_qualified_id"]),
        )
        if len(relations) != len(
            {(item["relation_type"], item["target_qualified_id"]) for item in relations}
        ):
            raise ValueError("PHX route relation is duplicated")
        semantic = {
            **{key: normalized[key] for key in normalized if key not in {"source_chx_refs", "relations"}},
            "source_chx_refs": source_refs,
            "relations": relations,
        }
        route_count = sum(event.get("event") == "route_recorded" for event in events)
        return {
            **_common(event="route_recorded", run_id=events[0]["run_id"]),
            "route_id": f"PHX-{route_count + 1:03d}",
            **semantic,
        }

    event, status = _mutate(path, builder)
    if event is not None:
        return event
    route = next(
        item for item in status["routes"] if item["route_key"] == normalized["route_key"]
    )
    return {"idempotent": True, **route}


def record_measurement(path: Path, value: Any) -> dict[str, Any]:
    path = _canonical_path(path, "PHX ledger")
    normalized = _measurement_input(value)
    measurement_id = _measurement_id(normalized)

    def builder(events: list[dict[str, Any]]) -> dict[str, Any] | None:
        if events[-1]["event"] == "run_closed":
            raise ValueError("PHX ledger is closed")
        if not any(
            event.get("event") == "route_recorded"
            and event.get("route_id") == normalized["route_id"]
            for event in events
        ):
            raise ValueError("PHX measurement names an unknown route")
        existing = [
            event for event in events
            if event.get("event") == "measurement_recorded"
            and event.get("measurement_id") == measurement_id
        ]
        if existing:
            return None
        return {
            **_common(event="measurement_recorded", run_id=events[0]["run_id"]),
            "measurement_id": measurement_id,
            **normalized,
        }

    event, status = _mutate(path, builder)
    if event is not None:
        return event
    return {
        "idempotent": True,
        "measurement_id": measurement_id,
        "run_id": status["run_id"],
    }


def record_consultation(path: Path, value: Any) -> dict[str, Any]:
    path = _canonical_path(path, "PHX ledger")
    normalized = _consultation_input(value)
    consultation_id = _consultation_id(normalized)

    def builder(events: list[dict[str, Any]]) -> dict[str, Any] | None:
        if events[-1]["event"] == "run_closed":
            raise ValueError("PHX ledger is closed")
        if not any(
            event.get("event") == "route_recorded"
            and event.get("route_id") == normalized["route_id"]
            for event in events
        ):
            raise ValueError("PHX consultation names an unknown route")
        if any(
            event.get("event") == "adoption_recorded"
            and event.get("route_id") == normalized["route_id"]
            for event in events
        ):
            raise ValueError("PHX cannot reconsider a route after its adoption record")
        if any(
            event.get("event") == "consultation_recorded"
            and event.get("consultation_id") == consultation_id
            for event in events
        ):
            return None
        return {
            **_common(event="consultation_recorded", run_id=events[0]["run_id"]),
            "consultation_id": consultation_id,
            **normalized,
        }

    event, status = _mutate(path, builder)
    if event is not None:
        return event
    return {
        "idempotent": True,
        "consultation_id": consultation_id,
        "run_id": status["run_id"],
    }


def record_adoption(path: Path, value: Any) -> dict[str, Any]:
    path = _canonical_path(path, "PHX ledger")
    normalized = _adoption_input(value)
    adoption_id = _adoption_id(normalized)

    def builder(events: list[dict[str, Any]]) -> dict[str, Any] | None:
        if events[-1]["event"] == "run_closed":
            raise ValueError("PHX ledger is closed")
        existing = [
            event for event in events
            if event.get("event") == "adoption_recorded"
            and event.get("route_id") == normalized["route_id"]
        ]
        if existing:
            if existing[0]["adoption_id"] != adoption_id:
                raise ValueError("PHX route already has a different adoption")
            return None
        return {
            **_common(event="adoption_recorded", run_id=events[0]["run_id"]),
            "adoption_id": adoption_id,
            **normalized,
        }

    event, status = _mutate(path, builder)
    if event is not None:
        return event
    return {"idempotent": True, "adoption_id": adoption_id, "run_id": status["run_id"]}


def close(path: Path) -> dict[str, Any]:
    path = _canonical_path(path, "PHX ledger")

    def builder(events: list[dict[str, Any]]) -> dict[str, Any] | None:
        if events[-1]["event"] == "run_closed":
            return None
        routes = [event["route_id"] for event in events if event["event"] == "route_recorded"]
        measurements = [
            event["measurement_id"] for event in events if event["event"] == "measurement_recorded"
        ]
        consultations = [
            event["consultation_id"]
            for event in events
            if event["event"] == "consultation_recorded"
        ]
        adoptions = [event["adoption_id"] for event in events if event["event"] == "adoption_recorded"]
        return {
            **_common(event="run_closed", run_id=events[0]["run_id"]),
            "route_ids": routes,
            "measurement_ids": measurements,
            "consultation_ids": consultations,
            "adoption_ids": adoptions,
            "report_required": bool(routes),
        }

    event, status = _mutate(path, builder)
    return event if event is not None else status


def search_routes(
    *,
    root: Path,
    query: str,
    domains: Sequence[str] = (),
    source_chx: Sequence[str] = (),
    relation_types: Sequence[str] = (),
    limit: int = 20,
    allow_custom_root: bool = False,
    write_receipt: bool = False,
) -> dict[str, Any]:
    root = _canonical_path(root, "PHX search root")
    canonical_default = _canonical_path(DEFAULT_GLOBAL_ROOT, "canonical PHX root")
    if root != canonical_default and not allow_custom_root:
        raise ValueError("custom PHX search root requires explicit expert authorization")
    query = query.strip().casefold()
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1 or limit > 200:
        raise ValueError("PHX search limit must be between 1 and 200")
    selected_domains = sorted(set(domains))
    if any(domain not in ROUTE_DOMAINS for domain in selected_domains):
        raise ValueError("PHX search domain is invalid")
    selected_chx = sorted(set(source_chx))
    for qualified in selected_chx:
        _split_qualified(
            qualified,
            item_pattern=re.compile(r"CHX-[0-9]{3,}"),
            label="PHX search source CHX issue",
        )
    selected_relations = sorted(set(relation_types))
    if any(item not in RELATION_TYPES for item in selected_relations):
        raise ValueError("PHX search relation type is invalid")
    if not root.exists() and write_receipt:
        if root != canonical_default:
            raise ValueError(
                "a missing custom PHX root cannot receive a search receipt"
            )
        _safe_global_root(root)
    if not root.exists():
        receipt = {
            "contract_revision": CONTRACT_REVISION,
            "root": str(root),
            "root_scope": (
                "canonical_global" if root == canonical_default else "custom_expert"
            ),
            "query": query,
            "domains": selected_domains,
            "source_chx": selected_chx,
            "relation_types": selected_relations,
            "limit": limit,
            "scanned_ledger_heads": [],
            "result_route_heads": [],
            "truth_effect": "none",
            "project_effect": "none",
        }
        result = {
            "query": query,
            "domains": selected_domains,
            "source_chx": selected_chx,
            "relation_types": selected_relations,
            "route_count": 0,
            "total_match_count": 0,
            "root_scope": (
                "canonical_global" if root == canonical_default else "custom_expert"
            ),
            "routes": [],
            "warnings": [],
            "search_receipt": receipt,
            "search_receipt_sha256": sha256(canonical_nfc_bytes(receipt)),
            "architecture_change_requires_user_consultation": True,
            "truth_effect": "none",
            "project_effect": "none",
            "premise_eligible": False,
        }
        return _maybe_persist_search_receipt(result, write_receipt=write_receipt)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("PHX search root is unsafe")
    _require_private_path(root, mode=0o700, label="PHX search root")
    tokens = [token for token in re.findall(r"[a-z0-9_.-]+|[\u3400-\u9fff]+", query) if token]
    rows: list[dict[str, Any]] = []
    seen_qualified_routes: set[str] = set()
    scanned_ledger_heads: list[dict[str, Any]] = []
    for ledger in sorted(root.glob("run-*.jsonl")):
        if ledger.is_symlink() or not ledger.is_file():
            raise ValueError("PHX search encountered an unsafe ledger entry")
        events, status = _read_ledger(ledger)
        scanned_ledger_heads.append(
            {
                "run_id": status["run_id"],
                "ledger_sha256": status["ledger_sha256"],
                "event_head_sha256": events[-1]["event_sha256"],
                "closed": status["closed"],
            }
        )
        route_events = {
            event["route_id"]: event
            for event in events
            if event["event"] == "route_recorded"
        }
        for route in status["routes"]:
            if route["qualified_route_id"] in seen_qualified_routes:
                raise ValueError("PHX search encountered duplicate qualified route ownership")
            seen_qualified_routes.add(route["qualified_route_id"])
            detail = route_events[route["route_id"]]
            route_chx = sorted(
                item["qualified_issue_id"] for item in route["source_chx_refs"]
            )
            route_relation_types = sorted(
                {item["relation_type"] for item in route["relations"]}
            )
            matches_filters = (
                (not selected_domains or route["route_domain"] in selected_domains)
                and (not selected_chx or set(selected_chx).issubset(route_chx))
                and (
                    not selected_relations
                    or set(selected_relations).issubset(route_relation_types)
                )
            )
            source = " ".join(
                [
                    route["route_key"],
                    route["title"],
                    detail["summary"],
                    route["route_domain"],
                    route["route_kind"],
                    route["origin"],
                    *detail["applicability_signals"],
                    *detail["implementation_options"],
                    *route_chx,
                    *(
                        f"{item['relation_type']} {item['target_qualified_id']}"
                        for item in route["relations"]
                    ),
                ]
            ).casefold()
            score = 1 if not query else 0
            if query and query in source:
                score += 8
            score += sum(2 for token in tokens if token in source)
            rows.append(
                {
                    **route,
                    "run_id": status["run_id"],
                    "ledger_path": status["ledger_path"],
                    "ledger_closed": status["closed"],
                    "ledger_sha256": status["ledger_sha256"],
                    "match_score": score,
                    "_matches_filters": matches_filters,
                }
            )
    superseded_by: dict[str, list[str]] = {}
    for row in rows:
        for relation in row["relations"]:
            if relation["relation_type"] == "supersedes":
                superseded_by.setdefault(
                    relation["target_qualified_id"], []
                ).append(row["qualified_route_id"])
    for row in rows:
        successors = sorted(set(superseded_by.get(row["qualified_route_id"], [])))
        row["superseded_by"] = successors
        row["effective_status"] = "superseded" if successors else "current"
        row["is_current_head"] = not successors
    current_by_key: dict[str, list[str]] = {}
    for row in rows:
        if row["is_current_head"]:
            current_by_key.setdefault(row["route_key"], []).append(
                row["qualified_route_id"]
            )
    warnings = [
        "ambiguous_current_route_key:"
        + key
        + ":"
        + ",".join(sorted(ids))
        for key, ids in sorted(current_by_key.items())
        if len(ids) > 1
    ]
    rows = [
        row
        for row in rows
        if row.pop("_matches_filters") and (not query or row["match_score"] > 0)
    ]
    rows.sort(
        key=lambda item: (
            not item["is_current_head"],
            -item["match_score"],
            item["route_key"],
            item["qualified_route_id"],
        )
    )
    visible_rows = rows[:limit]
    receipt = {
        "contract_revision": CONTRACT_REVISION,
        "root": str(root),
        "root_scope": (
            "canonical_global" if root == canonical_default else "custom_expert"
        ),
        "query": query,
        "domains": selected_domains,
        "source_chx": selected_chx,
        "relation_types": selected_relations,
        "limit": limit,
        "scanned_ledger_heads": scanned_ledger_heads,
        "result_route_heads": [
            {
                "qualified_route_id": row["qualified_route_id"],
                "route_event_sha256": row["route_event_sha256"],
                "route_event_prefix_sha256": row["route_event_prefix_sha256"],
                "ledger_sha256": row["ledger_sha256"],
                "effective_status": row["effective_status"],
            }
            for row in visible_rows
        ],
        "truth_effect": "none",
        "project_effect": "none",
    }
    result = {
        "query": query,
        "domains": selected_domains,
        "source_chx": selected_chx,
        "relation_types": selected_relations,
        "route_count": min(len(rows), limit),
        "total_match_count": len(rows),
        "root_scope": (
            "canonical_global" if root == canonical_default else "custom_expert"
        ),
        "routes": visible_rows,
        "warnings": warnings,
        "search_receipt": receipt,
        "search_receipt_sha256": sha256(canonical_nfc_bytes(receipt)),
        "architecture_change_requires_user_consultation": True,
        "truth_effect": "none",
        "project_effect": "none",
        "premise_eligible": False,
    }
    return _maybe_persist_search_receipt(result, write_receipt=write_receipt)


def _maybe_persist_search_receipt(
    result: dict[str, Any], *, write_receipt: bool
) -> dict[str, Any]:
    if not write_receipt:
        return result
    root = Path(result["search_receipt"]["root"])
    if not root.is_dir():
        raise ValueError("PHX search receipt requires an existing global root")
    _require_private_path(root, mode=0o700, label="PHX search root")
    receipt_root = root / "search-receipts"
    receipt_root.mkdir(mode=0o700, exist_ok=True)
    _require_private_path(receipt_root, mode=0o700, label="PHX receipt root")
    digest = result["search_receipt_sha256"]
    path = receipt_root / f"search-{digest}.json"
    payload = canonical_bytes(result["search_receipt"]) + b"\n"
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file():
            raise ValueError("PHX search receipt path is unsafe")
        _require_private_path(path, mode=0o600, label="PHX search receipt")
        if path.read_bytes() != payload:
            raise ValueError("PHX search receipt content drifted")
        return {**result, "search_receipt_path": str(path), "receipt_idempotent": True}
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    return {**result, "search_receipt_path": str(path), "receipt_idempotent": False}


def _render_report(events: list[dict[str, Any]], path: Path) -> str:
    status = _status(events, path)
    if not status["closed"]:
        raise ValueError("PHX report requires a closed ledger")
    lines = [
        "# Chalxius PHX architecture-route report",
        "",
        f"- Run: `{status['run_id']}`",
        f"- Ledger SHA-256: `{status['ledger_sha256']}`",
        f"- Routes: {status['route_count']}",
        f"- Measurements: {status['measurement_count']}",
        f"- User consultations: {status['consultation_count']}",
        f"- Adoptions: {status['adoption_count']}",
        "- Authority: nontruth, no project effect, premise-ineligible",
        "- Governance: recording or retrieving a route does not authorize an architecture change; user consultation is required before adoption",
        "",
    ]
    for route in [event for event in events if event["event"] == "route_recorded"]:
        lines.extend(
            [
                f"## {route['route_id']} — {route['title']}",
                "",
                f"- Qualified id: `{status['run_id']}/{route['route_id']}`",
                f"- Stable key: `{route['route_key']}`",
                f"- Domain: `{route['route_domain']}`",
                f"- Kind: `{route['route_kind']}`",
                f"- Origin: `{route['origin']}`",
                f"- Summary: {route['summary']}",
                "- Applicability signals: " + "; ".join(route["applicability_signals"]),
                "- Measurement plan: " + " → ".join(route["measurement_plan"]),
                "- Implementation options: " + "; ".join(route["implementation_options"]),
                "- Preserved boundaries: " + "; ".join(route["fail_closed_boundaries"]),
            ]
        )
        if route["relations"]:
            lines.append(
                "- Route relations: "
                + "; ".join(
                    f"{item['relation_type']} {item['target_qualified_id']}"
                    for item in route["relations"]
                )
            )
        if route["source_chx_refs"]:
            lines.append(
                "- Source CHX: "
                + "; ".join(item["qualified_issue_id"] for item in route["source_chx_refs"])
            )
        for measurement in [
            item for item in events
            if item["event"] == "measurement_recorded" and item["route_id"] == route["route_id"]
        ]:
            metric_text = ", ".join(
                f"{item['name']}={item['value']} {item['unit']}" for item in measurement["metrics"]
            ) or "none"
            lines.append(
                f"- Evaluation `{measurement['measurement_id']}`: "
                f"{measurement['evaluation_kind']}; {measurement['outcome']}; {metric_text}"
            )
        for consultation in [
            item for item in events
            if item["event"] == "consultation_recorded"
            and item["route_id"] == route["route_id"]
        ]:
            lines.append(
                f"- User consultation `{consultation['consultation_id']}`: "
                f"{consultation['decision']}; response SHA-256 "
                f"`{consultation['user_response_sha256']}`; scope "
                f"{consultation['authorization_scope']}"
            )
        adoption = next(
            (
                item for item in events
                if item["event"] == "adoption_recorded" and item["route_id"] == route["route_id"]
            ),
            None,
        )
        if adoption is not None:
            lines.append(
                f"- Adopted as `{adoption['adoption_id']}`: {adoption['implementation_summary']}"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_report(ledger: Path, output: Path) -> dict[str, Any]:
    events, status = _read_ledger(ledger)
    rendered = _render_report(events, ledger)
    output = _canonical_path(output, "PHX report output")
    global_root = Path(events[0]["global_root"])
    reports_root = global_root / "reports"
    if output == reports_root or reports_root not in output.parents:
        raise ValueError("PHX report output must remain inside its bound global reports root")
    rendered_bytes = rendered.encode("utf-8")
    if output.exists() or output.is_symlink():
        if output.is_symlink() or not output.is_file():
            raise ValueError("PHX report output already exists with different or unsafe content")
        _require_private_path(output, mode=0o600, label="PHX report")
        if output.read_bytes() != rendered_bytes:
            raise ValueError("PHX report output already exists with different or unsafe content")
        return {
            "ok": True,
            "idempotent": True,
            "run_id": status["run_id"],
            "report_path": str(output),
            "report_sha256": sha256(rendered_bytes),
            "truth_effect": "none",
            "project_effect": "none",
        }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    if temporary.exists() or temporary.is_symlink():
        raise ValueError("PHX report temporary path is unsafe")
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(rendered_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "ok": True,
        "run_id": status["run_id"],
        "report_path": str(output),
        "report_sha256": sha256(rendered_bytes),
        "truth_effect": "none",
        "project_effect": "none",
    }


def verify_report(ledger: Path, report: Path) -> dict[str, Any]:
    events, status = _read_ledger(ledger)
    report = _canonical_path(report, "PHX report")
    global_root = Path(events[0]["global_root"])
    reports_root = global_root / "reports"
    if report == reports_root or reports_root not in report.parents:
        raise ValueError("PHX report must remain inside its bound global reports root")
    if report.is_symlink() or not report.is_file():
        raise ValueError("PHX report is missing or unsafe")
    _require_private_path(report, mode=0o600, label="PHX report")
    expected = _render_report(events, ledger).encode("utf-8")
    if report.is_symlink() or not report.is_file() or report.read_bytes() != expected:
        raise ValueError("PHX report differs from the deterministic closed ledger projection")
    return {
        "ok": True,
        "run_id": status["run_id"],
        "report_sha256": sha256(expected),
        "truth_effect": "none",
        "project_effect": "none",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    start_parser = sub.add_parser("start")
    start_parser.add_argument("--root", type=Path, default=DEFAULT_GLOBAL_ROOT)
    start_parser.add_argument("--scope-id", required=True)
    start_parser.add_argument("--project-root", action="append", default=[])
    start_parser.add_argument("--allow-custom-root", action="store_true")
    for name in (
        "record-route",
        "record-measurement",
        "record-consultation",
        "record-adoption",
    ):
        item = sub.add_parser(name)
        item.add_argument("--ledger", type=Path, required=True)
        item.add_argument("--input", type=Path, required=True)
    for name in ("status", "close"):
        item = sub.add_parser(name)
        item.add_argument("--ledger", type=Path, required=True)
    report_parser = sub.add_parser("report")
    report_parser.add_argument("--ledger", type=Path, required=True)
    report_parser.add_argument("--output", type=Path, required=True)
    verify_parser = sub.add_parser("verify-report")
    verify_parser.add_argument("--ledger", type=Path, required=True)
    verify_parser.add_argument("--report", type=Path, required=True)
    search_parser = sub.add_parser("search")
    search_parser.add_argument("--root", type=Path, default=DEFAULT_GLOBAL_ROOT)
    search_parser.add_argument("--query", default="")
    search_parser.add_argument("--domain", action="append", default=[])
    search_parser.add_argument("--source-chx", action="append", default=[])
    search_parser.add_argument("--relation-type", action="append", default=[])
    search_parser.add_argument("--limit", type=int, default=20)
    search_parser.add_argument("--allow-custom-root", action="store_true")
    search_parser.add_argument("--write-receipt", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.command == "start":
        result = start(
            root=args.root,
            scope_id=args.scope_id,
            project_roots=args.project_root,
            allow_custom_root=args.allow_custom_root,
        )
    elif args.command == "record-route":
        result = record_route(args.ledger, _load_json(args.input, "PHX route input"))
    elif args.command == "record-measurement":
        result = record_measurement(
            args.ledger, _load_json(args.input, "PHX measurement input")
        )
    elif args.command == "record-consultation":
        result = record_consultation(
            args.ledger, _load_json(args.input, "PHX consultation input")
        )
    elif args.command == "record-adoption":
        result = record_adoption(
            args.ledger, _load_json(args.input, "PHX adoption input")
        )
    elif args.command == "status":
        _, result = _read_ledger(args.ledger)
    elif args.command == "close":
        result = close(args.ledger)
    elif args.command == "report":
        result = write_report(args.ledger, args.output)
    elif args.command == "search":
        result = search_routes(
            root=args.root,
            query=args.query,
            domains=args.domain,
            source_chx=args.source_chx,
            relation_types=args.relation_type,
            limit=args.limit,
            allow_custom_root=args.allow_custom_root,
            write_receipt=args.write_receipt,
        )
    elif args.command == "verify-report":
        result = verify_report(args.ledger, args.report)
    else:  # pragma: no cover - argparse owns the command domain
        raise ValueError("unknown PHX command")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"PHX_LEDGER_ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)

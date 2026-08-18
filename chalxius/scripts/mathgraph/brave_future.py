from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .contracts import (
    ACTIVE_MEMORY_STATUSES,
    FACT_ID_RE,
    MEMORY_ID_RE,
    SHA256_RE,
    canonical_json_bytes,
    sha256_bytes,
    sha256_json,
    validate_assignment_id,
    validate_campaign_id,
    validate_memory_id,
    validate_round_id,
)
from .campaigns import canonical_research_objective
from .graph import DependencyGraph
from .goal_intake import (
    GOAL_INTAKE_EFFECT_KINDS,
    GoalIntakeTransactionStore,
    seal_goal_intake_effect,
    seal_goal_intake_intent,
    validate_goal_intake_effect,
)
from .modes import FACT_ADMISSION_CONTRACT_SHA256
from .markdown import parse_fact_markdown
from .v5_assurance import V5_ASSURANCE_CONTRACT_REVISION


BF_POLICY_REVISION = "chalxius-brave-future-policy-1"
BF_REPAIR_CONTRACT_REVISION = "chalxius-bf-repair-contract-1"
BF_PLANNING_SNAPSHOT_REVISION = "chalxius-bf-planning-snapshot-3"
BF_PLANNING_SNAPSHOT_FULL_AUDIT_REVISION = "chalxius-bf-planning-snapshot-2"
BF_PLANNING_SNAPSHOT_LEGACY_REVISION = "chalxius-bf-planning-snapshot-1"
BF_FRONTIER_PROJECTION_REVISION = "chalxius-bf-frontier-projection-2"
BF_FRONTIER_PROJECTION_LEGACY_REVISION = "chalxius-bf-frontier-projection-1"
BF_BLOCKAGE_REVISION = "chalxius-bf-blockage-1"
BF_CANDIDATE_MANIFEST_REVISION = "chalxius-bf-candidate-manifest-1"
BF_REASSESSMENT_REVISION = "chalxius-bf-reassessment-1"
BF_DECISION_REVISION = "chalxius-bf-decision-1"
BF_ACTIVATION_REVISION = "chalxius-bf-activation-event-1"
BF_GOAL_INTAKE_REVISION = "chalxius-bf-goal-intake-2"

BF_TRUTH_EFFECT = "none"
BF_FACT_ADMISSION_EFFECT = "none"
BF_MAX_OBJECT_BYTES = 256 * 1024
BF_PROJECTION_MEMBER_LIMIT = 256
BF_PROJECTION_RELATION_LIMIT = 512
BF_PROJECTION_PER_MEMBER_RELATION_LIMIT = 32

BF_REPAIR_STRATEGIES = frozenset(
    {
        "replacement",
        "restriction",
        "proof_repair",
        "source_repair",
        "computation_repair",
        "split",
        "counterexample_reframe",
    }
)
BF_REPAIR_RELATIONS = frozenset(
    {"repairs", "supersedes", "splits", "reframes"}
)
BF_COVERAGE_OUTCOMES = frozenset({"preserved", "resolved", "rehome"})
BF_BLOCKER_CLASSES = frozenset(
    {
        "missing_prerequisite",
        "surviving_counterexample",
        "scope_or_quantifier_mismatch",
        "source_or_applicability_gap",
        "representation_mismatch",
        "program_math_failure",
        "method_exhaustion",
        "dependency_conflict",
        "resource_bound_requiring_reformulation",
    }
)
BF_ATTEMPT_RESULTS = frozenset(
    {
        "blocker_survived",
        "prerequisite_missing",
        "scope_mismatch",
        "source_gap",
        "representation_failure",
        "program_math_failure",
        "method_exhausted",
        "dependency_conflict",
        "reformulation_required",
    }
)
BF_ACTIONS = frozenset(
    {
        "retry_with_changed_method",
        "inspect_prerequisite",
        "test_counterexample",
        "split_target",
        "switch_sibling_route",
        "recheck_source_or_applicability",
        "run_program_math_review",
        "park_and_escalate",
    }
)
BF_VIEWS = frozenset({"actionable", "all-active", "history"})
BF_PROJECTION_STATUSES = frozenset(
    {
        "actionable_current",
        "actionable_residual",
        "current_repair_leaf",
        "failed_repair",
        "blocked",
        "stale_by_route_invalidation",
        "collapsed_repaired",
        "collapsed_split_parent",
        "historical_disposed",
        "resolved_by_release_nontruth",
        "resolved_by_active_fact",
    }
)

_BF_ID_PATTERNS = {
    "planning_snapshot_id": re.compile(r"bfps-[0-9a-f]{64}"),
    "projection_id": re.compile(r"bfp-[0-9a-f]{64}"),
    "blockage_id": re.compile(r"bfb-[0-9a-f]{64}"),
    "candidate_manifest_id": re.compile(r"bfcm-[0-9a-f]{64}"),
    "reassessment_id": re.compile(r"bfr-[0-9a-f]{64}"),
    "decision_id": re.compile(r"bfd-[0-9a-f]{64}"),
}

_FIXED_POLICY = {
    "revision": BF_POLICY_REVISION,
    "autonomy_level": "advisory",
    "max_reassessments_per_signature": 1,
    "max_reassessments_per_epoch": 3,
    "shortlist_limit": 5,
    "local_graph_depth": 2,
    "local_graph_node_limit": 64,
    "max_new_research_nodes": 0,
    "max_auto_workers": 0,
    "max_consecutive_auto_rounds": 0,
    "allow_active_campaign_pointer": False,
    "allow_chx_as_route_input": False,
    "truth_effect": BF_TRUTH_EFFECT,
    "fact_admission_effect": BF_FACT_ADMISSION_EFFECT,
}


def validate_goal_intake(payload: Any) -> dict[str, str]:
    payload = _exact(
        payload,
        {"revision", "objective"},
        "Brave Future research-goal intake",
    )
    if payload.get("revision") != BF_GOAL_INTAKE_REVISION:
        raise ValueError("Brave Future research-goal intake revision mismatch")
    return {
        "revision": BF_GOAL_INTAKE_REVISION,
        "objective": canonical_research_objective(payload.get("objective")),
    }

_SNAPSHOT_SEMANTIC_FIELDS = {
    "revision",
    "project_id",
    "campaign_id",
    "campaign_scope_revision",
    "campaign_status_sha256",
    "campaign_event_count",
    "policy_head_sha256",
    "policy_epoch",
    "research_manifest",
    "research_manifest_sha256",
    "disposition_heads",
    "disposition_heads_sha256",
    "repair_lineage_manifest",
    "repair_lineage_manifest_sha256",
    "authority_snapshot",
    "blackboard_preview_manifest",
    "blackboard_preview_sha256",
    "workflow_heads",
    "background_index_sha256",
    "program_math_projection",
    "program_math_queue_head_sha256",
    "scheduler",
    "score_writeback",
    "active_campaign_pointer_used",
    "truth_effect",
    "fact_admission_effect",
}
_PROJECTION_SEMANTIC_FIELDS_V1 = {
    "revision",
    "project_id",
    "campaign_id",
    "planning_snapshot_id",
    "planning_snapshot_semantic_sha256",
    "view",
    "collapse_repairs",
    "lineage_edges",
    "collapse_map",
    "residual_surface",
    "failed_repairs",
    "invalidator_inventory",
    "obligation_inventory",
    "full_eligible_manifest",
    "full_eligible_manifest_sha256",
    "entries",
    "omitted_count",
    "scheduler",
    "score_writeback",
    "truth_effect",
    "fact_admission_effect",
}
_PROJECTION_SEMANTIC_FIELDS = {
    *(_PROJECTION_SEMANTIC_FIELDS_V1 - {
        "full_eligible_manifest",
        "full_eligible_manifest_sha256",
    }),
    "eligible_manifest_window",
    "eligible_manifest_window_limit",
    "eligible_manifest_total_count",
    "eligible_manifest_sha256",
}
_CANDIDATE_MANIFEST_SEMANTIC_FIELDS = {
    "revision",
    "project_id",
    "campaign_id",
    "planning_snapshot_id",
    "frontier_projection_id",
    "blockage_signature",
    "candidates",
    "candidate_count",
    "truth_effect",
    "fact_admission_effect",
}
_REASSESSMENT_SEMANTIC_FIELDS = {
    "revision",
    "project_id",
    "campaign_id",
    "blockage_id",
    "blockage_signature",
    "planning_snapshot_id",
    "frontier_projection_id",
    "candidate_manifest_id",
    "candidate_manifest_sha256",
    "shortlist",
    "omitted_count",
    "omission_policy",
    "recommended_action",
    "autonomy_level",
    "cooldown_state",
    "created_by",
    "plan_effect",
    "dispatch_effect",
    "campaign_close_effect",
    "truth_effect",
    "fact_admission_effect",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    return value.strip()


def _strings(value: Any, label: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{label} must be a list of strings")
    normalized = [_text(item, label) for item in value]
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{label} must be unique")
    if nonempty and not normalized:
        raise ValueError(f"{label} must be nonempty")
    return normalized


def _exact(payload: Any, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != fields:
        missing = sorted(fields.difference(payload if isinstance(payload, dict) else {}))
        extra = sorted((set(payload) if isinstance(payload, dict) else set()).difference(fields))
        raise ValueError(f"{label} fields are not exact; missing={missing}; extra={extra}")
    return payload


def _validate_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{label} must be a SHA-256")
    return value


def _validate_bf_id(value: Any, kind: str) -> str:
    pattern = _BF_ID_PATTERNS[kind]
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ValueError(f"invalid Brave Future {kind}: {value!r}")
    return value


def _sealed_record(
    semantic: dict[str, Any],
    *,
    id_key: str,
    prefix: str,
    created_at: str,
) -> dict[str, Any]:
    semantic_sha = sha256_json(semantic)
    body = {
        **semantic,
        id_key: prefix + semantic_sha,
        "created_at": created_at,
        "semantic_sha256": semantic_sha,
    }
    return {**body, "record_sha256": sha256_json(body)}


def _validate_sealed_record(
    record: Any,
    *,
    semantic_fields: set[str],
    id_key: str,
    prefix: str,
    revision: str,
    label: str,
) -> dict[str, Any]:
    required = {
        *semantic_fields,
        id_key,
        "created_at",
        "semantic_sha256",
        "record_sha256",
    }
    value = _exact(record, required, label)
    if value.get("revision") != revision:
        raise ValueError(f"{label} revision is invalid")
    _text(value.get("created_at"), f"{label} created_at")
    semantic = {key: value[key] for key in semantic_fields}
    semantic_sha = sha256_json(semantic)
    if value.get("semantic_sha256") != semantic_sha:
        raise ValueError(f"{label} semantic hash mismatch")
    if value.get(id_key) != prefix + semantic_sha:
        raise ValueError(f"{label} content id mismatch")
    without_hash = {key: item for key, item in value.items() if key != "record_sha256"}
    if value.get("record_sha256") != sha256_json(without_hash):
        raise ValueError(f"{label} record hash mismatch")
    if value.get("truth_effect") != BF_TRUTH_EFFECT or value.get(
        "fact_admission_effect"
    ) != BF_FACT_ADMISSION_EFFECT:
        raise ValueError(f"{label} truth boundary is invalid")
    return value


def _validate_planning_snapshot(record: Any) -> dict[str, Any]:
    """Validate current compact snapshots or exact immutable legacy v1 bytes."""

    revision = record.get("revision") if isinstance(record, dict) else None
    if revision not in {
        BF_PLANNING_SNAPSHOT_REVISION,
        BF_PLANNING_SNAPSHOT_FULL_AUDIT_REVISION,
        BF_PLANNING_SNAPSHOT_LEGACY_REVISION,
    }:
        raise ValueError("Brave Future planning snapshot revision is invalid")
    snapshot = _validate_sealed_record(
        record,
        semantic_fields=_SNAPSHOT_SEMANTIC_FIELDS,
        id_key="planning_snapshot_id",
        prefix="bfps-",
        revision=revision,
        label=(
            "Brave Future planning snapshot"
            if revision == BF_PLANNING_SNAPSHOT_REVISION
            else "legacy Brave Future planning snapshot"
        ),
    )
    for value_key, digest_key in (
        ("research_manifest", "research_manifest_sha256"),
        ("disposition_heads", "disposition_heads_sha256"),
        ("repair_lineage_manifest", "repair_lineage_manifest_sha256"),
        ("program_math_projection", "program_math_queue_head_sha256"),
    ):
        digest = snapshot.get(digest_key)
        _validate_sha(digest, f"Brave Future {digest_key}")
        value = snapshot.get(value_key)
        if revision == BF_PLANNING_SNAPSHOT_LEGACY_REVISION:
            if not isinstance(value, list) or any(
                not isinstance(item, dict) for item in value
            ):
                raise ValueError(
                    f"legacy Brave Future {value_key} must remain an exact list"
                )
            if sha256_json(value) != digest:
                raise ValueError(f"legacy Brave Future {value_key} digest mismatch")
        else:
            value = _exact(
                value,
                {"entry_count", "manifest_sha256"},
                f"Brave Future compact {value_key}",
            )
            count = value.get("entry_count")
            if (
                isinstance(count, bool)
                or not isinstance(count, int)
                or count < 0
                or value.get("manifest_sha256") != digest
            ):
                raise ValueError(f"Brave Future compact {value_key} is invalid")

    blackboard = snapshot.get("blackboard_preview_manifest")
    if revision == BF_PLANNING_SNAPSHOT_LEGACY_REVISION:
        blackboard = _exact(
            blackboard,
            {
                "node_entries",
                "edge_entries",
                "projection_sha256",
                "publication_effect",
            },
            "legacy Brave Future Blackboard preview",
        )
        if (
            not isinstance(blackboard["node_entries"], list)
            or not isinstance(blackboard["edge_entries"], list)
            or any(
                not isinstance(item, dict)
                for item in [
                    *blackboard["node_entries"],
                    *blackboard["edge_entries"],
                ]
            )
        ):
            raise ValueError("legacy Brave Future Blackboard entries are invalid")
    else:
        blackboard = _exact(
            blackboard,
            {
                "node_count",
                "node_entries_sha256",
                "edge_count",
                "edge_entries_sha256",
                "projection_sha256",
                "publication_effect",
            },
            "Brave Future compact Blackboard preview",
        )
        for count_key, digest_key in (
            ("node_count", "node_entries_sha256"),
            ("edge_count", "edge_entries_sha256"),
        ):
            count = blackboard.get(count_key)
            if (
                isinstance(count, bool)
                or not isinstance(count, int)
                or count < 0
            ):
                raise ValueError("Brave Future compact Blackboard count is invalid")
            _validate_sha(
                blackboard.get(digest_key),
                f"Brave Future compact Blackboard {digest_key}",
            )
    _validate_sha(
        blackboard.get("projection_sha256"),
        "Brave Future Blackboard projection digest",
    )
    if (
        blackboard.get("publication_effect") != "none"
        or snapshot.get("blackboard_preview_sha256") != sha256_json(blackboard)
    ):
        raise ValueError("Brave Future Blackboard preview binding is invalid")
    return snapshot


def _validate_frontier_projection(record: Any) -> dict[str, Any]:
    """Validate the current bounded-window projection or an exact legacy v1."""

    revision = record.get("revision") if isinstance(record, dict) else None
    if revision == BF_FRONTIER_PROJECTION_LEGACY_REVISION:
        return _validate_sealed_record(
            record,
            semantic_fields=_PROJECTION_SEMANTIC_FIELDS_V1,
            id_key="projection_id",
            prefix="bfp-",
            revision=BF_FRONTIER_PROJECTION_LEGACY_REVISION,
            label="legacy Brave Future frontier projection",
        )
    projection = _validate_sealed_record(
        record,
        semantic_fields=_PROJECTION_SEMANTIC_FIELDS,
        id_key="projection_id",
        prefix="bfp-",
        revision=BF_FRONTIER_PROJECTION_REVISION,
        label="Brave Future frontier projection",
    )
    window = projection["eligible_manifest_window"]
    window_limit = projection["eligible_manifest_window_limit"]
    total_count = projection["eligible_manifest_total_count"]
    if (
        not isinstance(window, list)
        or any(not isinstance(item, dict) for item in window)
        or not isinstance(window_limit, int)
        or isinstance(window_limit, bool)
        or window_limit <= 0
        or not isinstance(total_count, int)
        or isinstance(total_count, bool)
        or total_count < 0
        or len(window) != min(total_count, window_limit)
    ):
        raise ValueError("Brave Future eligible-manifest window is invalid")
    research_ids = [item.get("research_id") for item in window]
    if (
        any(not isinstance(item, str) or not item for item in research_ids)
        or len(research_ids) != len(set(research_ids))
    ):
        raise ValueError("Brave Future eligible-manifest window ids are invalid")
    _validate_sha(
        projection.get("eligible_manifest_sha256"),
        "Brave Future eligible-manifest digest",
    )
    entry_ids = {
        item.get("research_id")
        for item in projection["entries"]
        if isinstance(item, dict)
    }
    if not entry_ids.issubset(set(research_ids)):
        raise ValueError("Brave Future entries escape the eligible-manifest window")
    return projection


def _canonical_file_bytes(payload: Any) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _bounded(payload: Any, label: str) -> None:
    if len(_canonical_file_bytes(payload)) > BF_MAX_OBJECT_BYTES:
        raise ValueError(f"{label} exceeds the 256 KiB bounded-object limit")


def _legacy_tree_manifest(root: Path, *, project_root: Path) -> dict[str, Any]:
    """Exact planning-snapshot-1 tree projection; never used by the v2 writer."""

    entries: list[dict[str, str]] = []
    if root.exists():
        if root.is_symlink() or not root.is_dir():
            raise ValueError(f"unsafe planning-head directory: {root}")
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                raise ValueError(f"planning head contains a symlink: {path}")
            if not path.is_file():
                continue
            entries.append(
                {
                    "path": path.relative_to(project_root).as_posix(),
                    "sha256": sha256_bytes(path.read_bytes()),
                }
            )
    return {
        "entries": entries,
        "entry_count": len(entries),
        "manifest_sha256": sha256_json(entries),
    }


def _owner_generation_summary(root: Path, *, project_root: Path) -> dict[str, Any]:
    """Return one bounded owner head/generation witness without a tree walk."""

    relative = root.relative_to(project_root).as_posix()
    if not root.exists():
        return {"path": relative, "exists": False, "generation": 0, "head_sha256": None}
    if root.is_symlink():
        raise ValueError(f"unsafe planning owner path: {root}")
    if root.is_file():
        payload_bytes = root.read_bytes()
        generation = 1
        declared = None
        if root.suffix == ".json":
            payload = json.loads(payload_bytes)
            if not isinstance(payload, dict):
                raise ValueError(f"owner head is not an object: {root}")
            supplied_generation = payload.get("generation", 1)
            if (
                not isinstance(supplied_generation, bool)
                and isinstance(supplied_generation, int)
                and supplied_generation >= 0
            ):
                generation = supplied_generation
            supplied_head = payload.get("head_sha256")
            if isinstance(supplied_head, str) and SHA256_RE.fullmatch(supplied_head):
                declared = supplied_head
        return {
            "path": relative,
            "exists": True,
            "owner_head": "file",
            "generation": generation,
            "head_sha256": declared or sha256_bytes(payload_bytes),
        }
    if not root.is_dir():
        raise ValueError(f"unsafe planning owner path: {root}")
    for head_name in ("HEAD.json", "head.json", "manifest.json"):
        head_path = root / head_name
        if not head_path.exists():
            continue
        if head_path.is_symlink() or not head_path.is_file():
            raise ValueError(f"unsafe owner head: {head_path}")
        payload = json.loads(head_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"owner head is not an object: {head_path}")
        generation = payload.get("generation", 1)
        if isinstance(generation, bool) or not isinstance(generation, int) or generation < 0:
            generation = 1
        declared = payload.get("head_sha256")
        digest = (
            declared
            if isinstance(declared, str) and SHA256_RE.fullmatch(declared)
            else sha256_json(payload)
        )
        return {
            "path": relative,
            "exists": True,
            "owner_head": head_name,
            "generation": generation,
            "head_sha256": digest,
        }
    stat = root.stat()
    # Owners without a declared HEAD still expose a bounded generation witness
    # through the directory generation metadata.  No member path is copied.
    semantic = {
        "path": relative,
        "device": int(stat.st_dev),
        "inode": int(stat.st_ino),
        "mtime_ns": int(stat.st_mtime_ns),
        "ctime_ns": int(stat.st_ctime_ns),
    }
    return {
        "path": relative,
        "exists": True,
        "owner_head": "directory_generation",
        "generation": int(stat.st_mtime_ns),
        "head_sha256": sha256_json(semantic),
    }


def _owner_collection_summary(
    paths: dict[str, Path], *, project_root: Path
) -> dict[str, Any]:
    members = {
        name: _owner_generation_summary(path, project_root=project_root)
        for name, path in sorted(paths.items())
    }
    return {
        "owner_member_count": len(members),
        "owner_heads": members,
        "owner_heads_sha256": sha256_json(members),
    }


def validate_brave_future_policy(
    payload: Any, *, campaign_id: str
) -> dict[str, Any]:
    campaign_id = validate_campaign_id(campaign_id)
    required = {"campaign_id", *_FIXED_POLICY}
    value = _exact(payload, required, "Brave Future policy")
    normalized = dict(value)
    if normalized.get("campaign_id") != campaign_id:
        raise ValueError("Brave Future policy Campaign mismatch")
    for key, expected in _FIXED_POLICY.items():
        if normalized.get(key) != expected:
            raise ValueError(
                f"Brave Future 0.6.0 accepts only advisory policy; {key} must be {expected!r}"
            )
    return normalized


_REPAIR_FIELDS = {
    "repair_contract_revision",
    "strategy",
    "predecessor_research_ids",
    "method_family",
    "method_descriptor_sha256",
    "coverage",
    "residual_obligations",
    "inherited_invalidator_ids",
    "disposed_invalidator_ids",
    "source_capability_hashes",
    "created_under_snapshot_id",
}
_COVERAGE_FIELDS = {
    "predecessor_research_id",
    "obligation_key",
    "outcome",
    "supporting_research_ids",
}


def validate_repair_contract_structure(record: dict[str, Any]) -> dict[str, Any] | None:
    metadata = record.get("metadata")
    if not isinstance(metadata, dict):
        return None
    supplied = metadata.get("brave_future_repair_contract")
    if supplied is None:
        return None
    contract = _exact(supplied, _REPAIR_FIELDS, "Brave Future repair contract")
    if contract.get("repair_contract_revision") != BF_REPAIR_CONTRACT_REVISION:
        raise ValueError("Brave Future repair contract revision is invalid")
    if record.get("kind") != "repair":
        raise ValueError("Brave Future repair contract is allowed only on repair Research")
    if metadata.get("assurance_contract_revision") != V5_ASSURANCE_CONTRACT_REVISION:
        raise ValueError("Brave Future repair contract requires current-assurance Research")
    if record.get("relation") not in BF_REPAIR_RELATIONS:
        raise ValueError("Brave Future repair Research relation is not typed")
    strategy = contract.get("strategy")
    if strategy not in BF_REPAIR_STRATEGIES:
        raise ValueError("Brave Future repair strategy is invalid")
    predecessors = _strings(
        contract.get("predecessor_research_ids"),
        "repair predecessor ids",
        nonempty=True,
    )
    for research_id in predecessors:
        validate_memory_id(research_id)
    related = record.get("related_research_ids", [])
    if not isinstance(related, list) or not set(predecessors).issubset(related):
        raise ValueError("repair predecessors must all be explicit related Research ids")
    _text(contract.get("method_family"), "repair method family")
    _validate_sha(contract.get("method_descriptor_sha256"), "repair method descriptor")
    coverage = contract.get("coverage")
    if not isinstance(coverage, list):
        raise ValueError("repair coverage must be a list")
    coverage_keys: set[tuple[str, str]] = set()
    for item in coverage:
        item = _exact(item, _COVERAGE_FIELDS, "repair coverage entry")
        predecessor_id = validate_memory_id(
            _text(item.get("predecessor_research_id"), "coverage predecessor id")
        )
        if predecessor_id not in predecessors:
            raise ValueError("repair coverage names a non-predecessor")
        obligation_key = _text(item.get("obligation_key"), "coverage obligation key")
        pair = (predecessor_id, obligation_key)
        if pair in coverage_keys:
            raise ValueError("repair coverage keys must be unique per predecessor")
        coverage_keys.add(pair)
        if item.get("outcome") not in BF_COVERAGE_OUTCOMES:
            raise ValueError("repair coverage outcome is invalid")
        supports = _strings(
            item.get("supporting_research_ids"), "coverage supporting Research ids"
        )
        for research_id in supports:
            validate_memory_id(research_id)
        if item["outcome"] in {"resolved", "rehome"} and not supports:
            raise ValueError(
                f"repair coverage outcome {item['outcome']} requires supporting Research"
            )
    _strings(contract.get("residual_obligations"), "repair residual obligations")
    inherited = _strings(
        contract.get("inherited_invalidator_ids"), "inherited invalidator ids"
    )
    disposed = _strings(
        contract.get("disposed_invalidator_ids"), "disposed invalidator ids"
    )
    if set(inherited).intersection(disposed):
        raise ValueError("an invalidator cannot be both inherited and disposed")
    for research_id in [*inherited, *disposed]:
        validate_memory_id(research_id)
    capabilities = _strings(
        contract.get("source_capability_hashes"), "repair source capability hashes"
    )
    for digest in capabilities:
        _validate_sha(digest, "repair source capability hash")
    snapshot_id = contract.get("created_under_snapshot_id")
    if snapshot_id is not None:
        _validate_bf_id(snapshot_id, "planning_snapshot_id")
    return contract


def _obligation_keys(record: dict[str, Any]) -> list[str]:
    metadata = record.get("metadata", {})
    obligations = metadata.get("obligations", []) if isinstance(metadata, dict) else []
    if not isinstance(obligations, list):
        raise ValueError("Research obligations must be a list")
    keys: list[str] = []
    for item in obligations:
        if isinstance(item, str):
            key = _text(item, "Research obligation")
        elif isinstance(item, dict):
            key = _text(
                item.get("obligation_id", item.get("obligation_key")),
                "Research obligation id",
            )
        else:
            raise ValueError("Research obligations must be strings or typed objects")
        keys.append(key)
    if len(keys) != len(set(keys)):
        raise ValueError("Research obligation ids must be unique")
    return sorted(keys)


def validate_repair_contract_semantics(
    record: dict[str, Any], records: dict[str, dict[str, Any]]
) -> dict[str, Any] | None:
    contract = validate_repair_contract_structure(record)
    if contract is None:
        return None
    own_id = record.get("research_id")
    campaign_id = record.get("metadata", {}).get("campaign_id")
    campaign_id = validate_campaign_id(_text(campaign_id, "repair Campaign id"))
    if own_id is not None and own_id in contract["predecessor_research_ids"]:
        raise ValueError("repair contract contains a self edge")
    for predecessor_id in contract["predecessor_research_ids"]:
        predecessor = records.get(predecessor_id)
        if predecessor is None:
            raise ValueError(f"repair contract has unknown predecessor: {predecessor_id}")
        if predecessor.get("metadata", {}).get("campaign_id") != campaign_id:
            raise ValueError("repair contract crosses Campaigns")
    referenced_ids = {
        research_id
        for item in contract["coverage"]
        for research_id in item["supporting_research_ids"]
    }
    referenced_ids.update(contract["inherited_invalidator_ids"])
    referenced_ids.update(contract["disposed_invalidator_ids"])
    for research_id in referenced_ids:
        referenced = records.get(research_id)
        if referenced is None:
            raise ValueError(f"repair contract references unknown Research: {research_id}")
        if referenced.get("metadata", {}).get("campaign_id") != campaign_id:
            raise ValueError("repair contract semantic references cross Campaigns")
    artifact_hashes = sorted(
        item["sha256"]
        for item in record.get("metadata", {}).get("artifacts", [])
        if isinstance(item, dict) and isinstance(item.get("sha256"), str)
    )
    if sorted(contract["source_capability_hashes"]) != artifact_hashes:
        raise ValueError(
            "repair contract source capability hashes must exactly match Research artifacts"
        )
    return contract


class BraveFuturePolicyStore:
    def __init__(self, store: Any) -> None:
        self.store = store
        self.root = store.root / "governance" / "brave-future"
        self.events_path = self.root / "activation-events.jsonl"

    def _events(self) -> list[dict[str, Any]]:
        if not self.events_path.exists():
            return []
        if self.events_path.is_symlink() or not self.events_path.is_file():
            raise ValueError("Brave Future activation ledger is unsafe")
        events: list[dict[str, Any]] = []
        previous = None
        for number, raw in enumerate(
            self.events_path.read_text(encoding="utf-8").splitlines(), 1
        ):
            if not raw.strip():
                continue
            event = json.loads(raw)
            expected = {
                "revision",
                "event",
                "campaign_id",
                "policy",
                "actor",
                "reason",
                "recorded_at",
                "previous_event_sha256",
                "event_sha256",
                "truth_effect",
                "fact_admission_effect",
            }
            _exact(event, expected, f"Brave Future activation event line {number}")
            if event.get("revision") != BF_ACTIVATION_REVISION:
                raise ValueError("Brave Future activation revision mismatch")
            validate_campaign_id(event.get("campaign_id"))
            if event.get("event") not in {"enabled", "disabled"}:
                raise ValueError("Brave Future activation event type is invalid")
            if event.get("previous_event_sha256") != previous:
                raise ValueError("Brave Future activation chain is broken")
            semantic = {key: value for key, value in event.items() if key != "event_sha256"}
            if event.get("event_sha256") != sha256_json(semantic):
                raise ValueError("Brave Future activation event hash mismatch")
            if event.get("truth_effect") != BF_TRUTH_EFFECT or event.get(
                "fact_admission_effect"
            ) != BF_FACT_ADMISSION_EFFECT:
                raise ValueError("Brave Future activation truth boundary is invalid")
            if event["event"] == "enabled":
                validate_brave_future_policy(
                    event.get("policy"), campaign_id=event["campaign_id"]
                )
                if event.get("reason") != "":
                    raise ValueError("Brave Future enable reason must be empty")
            elif event.get("policy") is not None:
                raise ValueError("Brave Future disable event cannot carry a policy")
            previous = event["event_sha256"]
            events.append(event)
        return events

    def _append(self, event: dict[str, Any]) -> None:
        events = self._events()
        payload = b"".join(canonical_json_bytes(item) + b"\n" for item in [*events, event])
        self.root.mkdir(parents=True, exist_ok=True)
        self.store._write_bytes_atomic(self.events_path, payload)

    def status(self, campaign_id: str) -> dict[str, Any]:
        campaign_id = validate_campaign_id(campaign_id)
        self.store.campaigns().status(campaign_id)
        events = [item for item in self._events() if item["campaign_id"] == campaign_id]
        intake_activation = GoalIntakeTransactionStore(
            self.store
        ).committed_activation(campaign_id)
        if intake_activation is not None:
            if (
                intake_activation.get("base_event_count") != 0
                or intake_activation.get("base_head_event_sha256") is not None
            ):
                raise ValueError(
                    "goal-intake activation is not based on an empty Campaign policy history"
                )
            validate_brave_future_policy(
                intake_activation.get("policy"), campaign_id=campaign_id
            )
        if events:
            head = events[-1]
            enabled = head["event"] == "enabled"
            policy = head["policy"] if enabled else None
            head_sha256 = head["event_sha256"]
        elif intake_activation is not None:
            head = None
            enabled = True
            policy = intake_activation["policy"]
            head_sha256 = intake_activation["event_sha256"]
        else:
            head = None
            enabled = False
            policy = None
            head_sha256 = None
        epoch = sum(1 for item in events if item["event"] == "enabled") + int(
            intake_activation is not None
        )
        return {
            "revision": BF_POLICY_REVISION,
            "campaign_id": campaign_id,
            "enabled": enabled,
            "policy": policy,
            "head_event_sha256": head_sha256,
            "epoch": epoch,
            "event_count": len(events) + int(intake_activation is not None),
            "active_campaign_pointer_used": False,
            "autonomy_effect": "advisory_only" if enabled else "none",
            "truth_effect": BF_TRUTH_EFFECT,
            "fact_admission_effect": BF_FACT_ADMISSION_EFFECT,
        }

    def enable(
        self, *, campaign_id: str, policy: dict[str, Any], actor: str
    ) -> dict[str, Any]:
        campaign_id = validate_campaign_id(campaign_id)
        self.store.campaigns().status(campaign_id)
        normalized = validate_brave_future_policy(policy, campaign_id=campaign_id)
        actor = _text(actor, "Brave Future actor")
        with self.store.v5_mutation_lock(command="brave-future-enable"):
            current = self.status(campaign_id)
            if current["enabled"]:
                if current["policy"] != normalized:
                    raise ValueError("Brave Future is already enabled with another policy")
                return {**current, "write_effect": "none", "idempotent": True}
            events = self._events()
            previous = events[-1]["event_sha256"] if events else None
            semantic = {
                "revision": BF_ACTIVATION_REVISION,
                "event": "enabled",
                "campaign_id": campaign_id,
                "policy": normalized,
                "actor": actor,
                "reason": "",
                "recorded_at": _now(),
                "previous_event_sha256": previous,
                "truth_effect": BF_TRUTH_EFFECT,
                "fact_admission_effect": BF_FACT_ADMISSION_EFFECT,
            }
            self._append({**semantic, "event_sha256": sha256_json(semantic)})
        return {**self.status(campaign_id), "write_effect": "activation_event"}

    def disable(self, *, campaign_id: str, actor: str, reason: str) -> dict[str, Any]:
        campaign_id = validate_campaign_id(campaign_id)
        actor = _text(actor, "Brave Future actor")
        reason = _text(reason, "Brave Future disable reason")
        with self.store.v5_mutation_lock(command="brave-future-disable"):
            current = self.status(campaign_id)
            if not current["enabled"]:
                return {**current, "write_effect": "none", "idempotent": True}
            events = self._events()
            previous = events[-1]["event_sha256"] if events else None
            semantic = {
                "revision": BF_ACTIVATION_REVISION,
                "event": "disabled",
                "campaign_id": campaign_id,
                "policy": None,
                "actor": actor,
                "reason": reason,
                "recorded_at": _now(),
                "previous_event_sha256": previous,
                "truth_effect": BF_TRUTH_EFFECT,
                "fact_admission_effect": BF_FACT_ADMISSION_EFFECT,
            }
            self._append({**semantic, "event_sha256": sha256_json(semantic)})
        return {**self.status(campaign_id), "write_effect": "disablement_event"}


class PlanningSnapshotBuilder:
    def __init__(self, store: Any) -> None:
        self.store = store
        self.lifecycle = store.v5_lifecycle()

    @staticmethod
    def _effective_research(
        records: list[dict[str, Any]], campaign_id: str
    ) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
        bases: dict[str, dict[str, Any]] = {}
        dispositions: dict[str, dict[str, Any]] = {}
        for record in records:
            metadata = record.get("metadata", {})
            if record["kind"] == "disposition":
                target_id = metadata.get("target_research_id")
                if not isinstance(target_id, str):
                    continue
                target = bases.get(target_id)
                if target is None:
                    # The target may sort after its disposition; retain it and
                    # filter by the target Campaign below.
                    pass
                prior = dispositions.get(target_id)
                if prior is None or record["created_at"] > prior["created_at"]:
                    dispositions[target_id] = record
                continue
            if metadata.get("campaign_id") == campaign_id:
                bases[record["research_id"]] = record
        dispositions = {
            target_id: record
            for target_id, record in dispositions.items()
            if target_id in bases
        }
        return bases, dispositions

    def _authority(self) -> dict[str, Any]:
        """Project the direct active authority bytes without replaying releases.

        Brave Future is advisory-only.  Its default planning snapshot therefore
        needs the current Fact graph and visibility markers, not a recursive
        replay of every Candidate, verifier capsule, and frozen artifact that
        originally established those Facts.  The explicit ``fact-evidence-audit``
        command retains that full forensic path.
        """

        project = self.store.project()
        project_id = self.store.project_id()
        if (
            project.get("workflow_evidence_version") != 5
            or project.get("truth_policy") != "verifier-gated"
            or not isinstance(project.get("policy_revision"), str)
        ):
            raise ValueError("Brave Future requires a V5 verifier-gated project")
        policy_revision = project["policy_revision"]
        for label, directory in (
            ("Fact admissions", self.lifecycle.admissions_dir),
            ("Fact revocations", self.lifecycle.revocations_dir),
            ("Fact interfaces", self.store.fact_graph_dir / "interfaces"),
        ):
            if directory.is_symlink() or not directory.is_dir():
                raise ValueError(f"Brave Future {label} directory is missing or unsafe")
        if (
            self.lifecycle.contract_path.is_symlink()
            or not self.lifecycle.contract_path.is_file()
        ):
            raise ValueError("Brave Future lifecycle contract is missing or unsafe")

        revoked_ids = self.lifecycle.revoked_fact_ids()
        revocation_manifest = []
        for path in sorted(self.lifecycle.revocations_dir.glob("*.json")):
            if path.is_symlink() or not path.is_file():
                raise ValueError(
                    "Brave Future revocation projection contains an unsafe entry"
                )
            revocation_manifest.append(
                {
                    "fact_id": path.stem,
                    "record_sha256": sha256_bytes(path.read_bytes()),
                }
            )

        admitted_facts: dict[str, Any] = {}
        admitted_markers: dict[str, dict[str, Any]] = {}
        fact_manifest: list[dict[str, Any]] = []
        marker_manifest: list[dict[str, Any]] = []
        for directory in sorted(self.lifecycle.admissions_dir.glob("release-*")):
            if directory.is_symlink() or not directory.is_dir():
                raise ValueError(
                    "Brave Future admission projection contains an unsafe entry"
                )
            marker_path = directory / "ACCEPTED.json"
            if not marker_path.exists():
                continue
            if marker_path.is_symlink() or not marker_path.is_file():
                raise ValueError("Brave Future admission marker is unsafe")
            marker = self.store._read_json(marker_path)
            required = {
                "schema_version",
                "policy_revision",
                "project_id",
                "release_id",
                "release_sha256",
                "decision_id",
                "decision_sha256",
                "capsule_sha256",
                "fact_ids",
                "fact_sha256",
                "gateway",
                "reviewer",
                "accepted_at",
                "acceptance_id",
            }
            if not isinstance(marker, dict) or not required.issubset(marker):
                raise ValueError("Brave Future admission marker fields are incomplete")
            release_id = directory.name
            fact_ids = marker.get("fact_ids")
            fact_sha256 = marker.get("fact_sha256")
            semantic = {
                key: value for key, value in marker.items() if key != "acceptance_id"
            }
            if (
                marker.get("schema_version") != 5
                or marker.get("policy_revision") != policy_revision
                or marker.get("project_id") != project_id
                or marker.get("release_id") != release_id
                or not release_id.startswith("release-")
                or marker.get("release_sha256")
                != release_id.removeprefix("release-")
                or SHA256_RE.fullmatch(str(marker.get("release_sha256", ""))) is None
                or marker.get("decision_id")
                != "decision-" + str(marker.get("decision_sha256", ""))
                or SHA256_RE.fullmatch(
                    str(marker.get("decision_sha256", ""))
                )
                is None
                or SHA256_RE.fullmatch(str(marker.get("capsule_sha256", ""))) is None
                or marker.get("acceptance_id") != "acceptance-" + sha256_json(semantic)
                or not isinstance(fact_ids, list)
                or not fact_ids
                or len(fact_ids) != len(set(fact_ids))
                or any(
                    not isinstance(fact_id, str)
                    or FACT_ID_RE.fullmatch(fact_id) is None
                    for fact_id in fact_ids
                )
                or not isinstance(fact_sha256, dict)
                or set(fact_sha256) != set(fact_ids)
                or any(
                    not isinstance(digest, str)
                    or SHA256_RE.fullmatch(digest) is None
                    for digest in fact_sha256.values()
                )
            ):
                raise ValueError("Brave Future admission marker identity is invalid")
            marker_manifest.append(
                {
                    "release_id": release_id,
                    "acceptance_id": marker["acceptance_id"],
                    "marker_sha256": sha256_bytes(marker_path.read_bytes()),
                }
            )
            for fact_id in fact_ids:
                if fact_id in admitted_facts:
                    raise ValueError("Brave Future authority has duplicate admitted Fact ids")
                path = directory / "facts" / f"{fact_id}.md"
                if path.is_symlink() or not path.is_file():
                    raise ValueError("Brave Future admitted Fact is missing or unsafe")
                payload = path.read_bytes()
                digest = sha256_bytes(payload)
                if digest != fact_sha256[fact_id]:
                    raise ValueError("Brave Future admitted Fact hash mismatch")
                fact = parse_fact_markdown(payload.decode("utf-8"))
                errors = fact.validate()
                if errors or fact.fact_id != fact_id or fact.problem_id != project_id:
                    raise ValueError(
                        "Brave Future admitted Fact schema/project mismatch"
                        + (": " + "; ".join(errors) if errors else "")
                    )
                admitted_facts[fact_id] = fact
                admitted_markers[fact_id] = marker
                fact_manifest.append(
                    {
                        "fact_id": fact_id,
                        "fact_sha256": digest,
                        "predecessors_sha256": sha256_json(fact.predecessors),
                    }
                )

        unknown_revocations = revoked_ids.difference(admitted_facts)
        if unknown_revocations:
            raise ValueError(
                "Brave Future revocations have no admitted Fact: "
                + ", ".join(sorted(unknown_revocations))
            )
        active_facts = {
            fact_id: fact
            for fact_id, fact in admitted_facts.items()
            if fact_id not in revoked_ids
        }
        graph = DependencyGraph(active_facts)
        missing = graph.missing_predecessors()
        if missing:
            raise ValueError(
                "Brave Future active Fact graph has missing predecessors: "
                + ", ".join(f"{fact_id}->{prior}" for fact_id, prior in missing)
            )
        graph.topological_order()

        interface_manifest = []
        interfaces_dir = self.store.fact_graph_dir / "interfaces"
        for fact_id in sorted(active_facts):
            path = interfaces_dir / f"{fact_id}.json"
            if path.is_symlink() or not path.is_file():
                raise ValueError(
                    "Brave Future active Fact interface is missing or unsafe"
                )
            interface_manifest.append(
                {
                    "fact_id": fact_id,
                    "interface_sha256": sha256_bytes(path.read_bytes()),
                }
            )

        verification_events = self.store._read_jsonl(self.store.verification_log)
        events_by_fact: dict[str, list[dict[str, Any]]] = {}
        for event in verification_events:
            fact_id = str(event.get("fact_id", ""))
            events_by_fact.setdefault(fact_id, []).append(event)
        for fact_id, marker in admitted_markers.items():
            events = events_by_fact.get(fact_id, [])
            expected_id = sha256_json(
                [
                    "accepted-v5",
                    fact_id,
                    marker["release_id"],
                    marker["decision_id"],
                    marker["acceptance_id"],
                ]
            )
            if len(events) != 1 or any(
                events[0].get(key) != expected
                for key, expected in (
                    ("event", "accepted"),
                    ("event_id", expected_id),
                    ("release_id", marker["release_id"]),
                    ("decision_id", marker["decision_id"]),
                    ("capsule_sha256", marker["capsule_sha256"]),
                    ("acceptance_id", marker["acceptance_id"]),
                    ("fact_sha256", marker["fact_sha256"][fact_id]),
                )
            ):
                raise ValueError("Brave Future Fact acceptance event mismatch")
        unknown_event_facts = set(events_by_fact).difference(admitted_markers)
        if unknown_event_facts:
            raise ValueError(
                "Brave Future acceptance events have no admission marker: "
                + ", ".join(sorted(unknown_event_facts))
            )

        active_fact_ids = sorted(active_facts)
        roots = {
            "facts": self.store.fact_graph_dir / "facts",
            "interfaces": interfaces_dir,
            "admissions": self.lifecycle.admissions_dir,
            "revocations": self.lifecycle.revocations_dir,
            "verification_log": self.store.verification_log,
            "lifecycle_contract": self.lifecycle.contract_path,
        }
        semantic = {
            "projection_revision": "chalxius-bf-direct-authority-projection-1",
            "projection_scope": "direct_active_fact_graph_and_visibility_markers",
            "full_provenance_audit": "explicit_fact-evidence-audit",
            "active_fact_count": len(active_fact_ids),
            "active_fact_ids_sha256": sha256_json(active_fact_ids),
            "fact_manifest_sha256": sha256_json(
                sorted(fact_manifest, key=lambda item: item["fact_id"])
            ),
            "interface_manifest_sha256": sha256_json(interface_manifest),
            "admission_marker_manifest_sha256": sha256_json(marker_manifest),
            "revocation_manifest_sha256": sha256_json(revocation_manifest),
            "authority_state": (
                "valid_empty" if not active_fact_ids else "valid_nonempty"
            ),
            "authority_owner_heads": {
                name: _owner_generation_summary(path, project_root=self.store.root)
                for name, path in roots.items()
            },
            "fact_admission_contract_sha256": FACT_ADMISSION_CONTRACT_SHA256,
        }
        return {**semantic, "authority_snapshot_sha256": sha256_json(semantic)}

    def _full_authority(self) -> dict[str, Any]:
        audit = self.lifecycle.fact_evidence_audit()
        empty_authority = (
            audit.get("facts") == 0
            and audit.get("graph_errors") == []
            and audit.get("authority_errors")
            == ["external Fact Evidence requires at least one active Fact"]
        )
        if not audit.get("current_ok") and not empty_authority:
            raise ValueError("Brave Future requires a current valid Fact authority snapshot")
        roots = {
            "facts": self.store.fact_graph_dir / "facts",
            "interfaces": self.store.fact_graph_dir / "interfaces",
            "admissions": self.lifecycle.admissions_dir,
            "revocations": self.lifecycle.revocations_dir,
        }
        manifests = {
            name: _owner_generation_summary(path, project_root=self.store.root)
            for name, path in roots.items()
        }
        active_fact_ids = sorted(audit.get("active_fact_ids", []))
        semantic = {
            "audit_sha256": sha256_json(audit),
            "active_fact_count": len(active_fact_ids),
            "active_fact_ids_sha256": sha256_json(active_fact_ids),
            "authority_state": "valid_empty" if empty_authority else "valid_nonempty",
            "authority_owner_heads": manifests,
            "fact_admission_contract_sha256": FACT_ADMISSION_CONTRACT_SHA256,
        }
        return {**semantic, "authority_snapshot_sha256": sha256_json(semantic)}

    def _legacy_authority(self) -> dict[str, Any]:
        """Reconstruct the exact planning-snapshot-1 authority projection."""

        audit = self.lifecycle.fact_evidence_audit()
        empty_authority = (
            audit.get("facts") == 0
            and audit.get("graph_errors") == []
            and audit.get("authority_errors")
            == ["external Fact Evidence requires at least one active Fact"]
        )
        if not audit.get("current_ok") and not empty_authority:
            raise ValueError("Brave Future requires a current valid Fact authority snapshot")
        roots = [
            self.store.fact_graph_dir / "facts",
            self.store.fact_graph_dir / "interfaces",
            self.lifecycle.admissions_dir,
            self.lifecycle.revocations_dir,
        ]
        manifests = [
            _legacy_tree_manifest(path, project_root=self.store.root)
            for path in roots
        ]
        semantic = {
            "audit_sha256": sha256_json(audit),
            "active_fact_ids": list(audit.get("active_fact_ids", [])),
            "authority_state": "valid_empty" if empty_authority else "valid_nonempty",
            "authority_manifests": manifests,
            "fact_admission_contract_sha256": FACT_ADMISSION_CONTRACT_SHA256,
        }
        return {**semantic, "authority_snapshot_sha256": sha256_json(semantic)}

    def _head_manifest(self) -> dict[str, Any]:
        paper = self.store.paper_logic()
        continuation = self.lifecycle.paper_continuation()
        status_index = continuation._status_index
        research_draft = self.lifecycle.research_draft()
        evidence = self.store.evidence()
        reasoning_mode = self.store.reasoning_modes()
        adverse = self.store.adverse_routes()
        owners = {
            "paper_logic": {
                "feature": paper.feature_path,
                "artifacts": paper.artifacts_dir,
                "nodes": paper.nodes_dir,
                "edges": paper.edges_dir,
                "revisions": paper.revisions_dir,
                "reviews": paper.reviews_dir,
                "transactions": paper.transactions_dir,
                "snapshots": paper.snapshots_dir,
                "bridges": paper.bridges_dir,
                "projections": paper.projections_dir,
            },
            "paper_continuation": {
                "status_head": status_index.head_path,
                "plans": continuation.plans_dir,
                "materializations": continuation.materializations_dir,
                "dispositions": continuation.dispositions_dir,
                "writing_artifacts": continuation.writing_artifacts_dir,
                "status_states": status_index.states_dir,
                "status_receipts": status_index.receipts_dir,
                "research_lineage": status_index.lineage_dir,
            },
            "research_draft_admission": {
                "plans": research_draft.plans_dir,
                "authorizations": research_draft.authorizations_dir,
                "batches": research_draft.batches_dir,
                "heads": research_draft.heads_dir,
            },
            "evidence": {
                "binding": evidence.binding_path,
                "outbox": evidence.outbox_dir,
                "receipts": evidence.receipts_dir,
                "fact_capsules": evidence.fact_capsules_dir,
                "association_outbox": evidence.association_outbox_dir,
                "association_effects": evidence.association_effects_dir,
            },
            "reasoning_mode": {
                "contract": reasoning_mode.contract_path,
                "policy": reasoning_mode.policy_path,
                "ledger": reasoning_mode.ledger_path,
                "events": reasoning_mode.events_dir,
                "current": reasoning_mode.current_path,
                "activation_receipt": reasoning_mode.activation_receipt_path,
                "aborts": reasoning_mode.abort_dir,
            },
            "adverse_routing": {
                "contract": adverse.contract_path,
                "cases": adverse.cases_dir,
                "proposals": adverse.proposals_dir,
                "decisions": adverse.decisions_dir,
                "rules": adverse.rules_dir,
                "disablements": adverse.disablements_dir,
            },
        }
        return {
            name: _owner_collection_summary(paths, project_root=self.store.root)
            for name, paths in owners.items()
        }

    def _legacy_head_manifest(self) -> dict[str, Any]:
        """Reconstruct the exact planning-snapshot-1 workflow-head projection."""

        roots = {
            "paper_logic": self.store.root / "paper_logic",
            "paper_continuation": self.lifecycle.root / "paper-continuations",
            "research_draft_admission": self.lifecycle.root / "research-draft-admission",
            "evidence": self.store.root / "evidence",
            "reasoning_mode": self.store.root / "governance" / "unified-mode",
            "adverse_routing": self.store.root / "governance" / "adverse-routing",
        }
        return {
            name: _legacy_tree_manifest(path, project_root=self.store.root)
            for name, path in roots.items()
        }

    def preview(
        self,
        *,
        campaign_id: str,
        policy_status: dict[str, Any],
        campaign_status_override: dict[str, Any] | None = None,
        revision: str = BF_PLANNING_SNAPSHOT_REVISION,
    ) -> dict[str, Any]:
        campaign_id = validate_campaign_id(campaign_id)
        if revision not in {
            BF_PLANNING_SNAPSHOT_REVISION,
            BF_PLANNING_SNAPSHOT_FULL_AUDIT_REVISION,
            BF_PLANNING_SNAPSHOT_LEGACY_REVISION,
        }:
            raise ValueError("Brave Future planning snapshot revision is unsupported")
        if not policy_status.get("enabled") or policy_status.get("campaign_id") != campaign_id:
            raise ValueError("Brave Future is not enabled for the explicit Campaign")
        campaign_status = dict(
            campaign_status_override
            if campaign_status_override is not None
            else self.store.campaigns().status(campaign_id)
        )
        if campaign_status.get("campaign_id") != campaign_id:
            raise ValueError("Brave Future Campaign status override mismatch")
        # ACTIVE is an informational legacy pointer, never a BF selector or head.
        campaign_status.pop("active", None)
        records = self.lifecycle.research_envelopes()
        bases, dispositions = self._effective_research(records, campaign_id)
        manifest = [
            {
                "research_id": research_id,
                "record_sha256": record["record_sha256"],
                "kind": record["kind"],
                "status": record["status"],
            }
            for research_id, record in sorted(bases.items())
        ]
        disposition_manifest = [
            {
                "target_research_id": target_id,
                "research_id": record["research_id"],
                "record_sha256": record["record_sha256"],
            }
            for target_id, record in sorted(dispositions.items())
        ]
        repair_manifest = [
            {
                "research_id": research_id,
                "record_sha256": record["record_sha256"],
                "contract_sha256": sha256_json(
                    record.get("metadata", {}).get("brave_future_repair_contract")
                ),
            }
            for research_id, record in sorted(bases.items())
            if record.get("metadata", {}).get("brave_future_repair_contract") is not None
        ]
        blackboard = self.store.blackboard()
        nodes, edges, current_projection = blackboard._current_objects()
        blackboard_node_entries = [
            {"node_id": key, "sha256": sha256_json(value)}
            for key, value in sorted(nodes.items())
        ]
        blackboard_edge_entries = [
            {"edge_id": key, "sha256": sha256_json(value)}
            for key, value in sorted(edges.items())
        ]
        blackboard_manifest = {
            "node_count": len(blackboard_node_entries),
            "node_entries_sha256": sha256_json(blackboard_node_entries),
            "edge_count": len(blackboard_edge_entries),
            "edge_entries_sha256": sha256_json(blackboard_edge_entries),
            "projection_sha256": sha256_json(current_projection),
            "publication_effect": "none",
        }
        legacy_blackboard_manifest = {
            "node_entries": blackboard_node_entries,
            "edge_entries": blackboard_edge_entries,
            "projection_sha256": sha256_json(current_projection),
            "publication_effect": "none",
        }
        program_math = [
            {
                "research_id": research_id,
                "record_sha256": record["record_sha256"],
                "program_math_review_sha256": sha256_json(
                    record.get("metadata", {}).get("program_math_review")
                ),
            }
            for research_id, record in sorted(bases.items())
            if record.get("metadata", {}).get("program_math_review") is not None
        ]
        background_path = self.store.root / "PROJECT_BACKGROUND.md"
        background_sha = (
            sha256_bytes(background_path.read_bytes())
            if background_path.is_file() and not background_path.is_symlink()
            else None
        )
        legacy = revision == BF_PLANNING_SNAPSHOT_LEGACY_REVISION
        semantic = {
            "revision": revision,
            "project_id": self.store.project_id(),
            "campaign_id": campaign_id,
            "campaign_scope_revision": "chalxius-v5-campaign-scope-1",
            "campaign_status_sha256": sha256_json(campaign_status),
            "campaign_event_count": campaign_status["event_count"],
            "policy_head_sha256": policy_status["head_event_sha256"],
            "policy_epoch": policy_status["epoch"],
            "research_manifest": (
                manifest
                if legacy
                else {
                    "entry_count": len(manifest),
                    "manifest_sha256": sha256_json(manifest),
                }
            ),
            "research_manifest_sha256": sha256_json(manifest),
            "disposition_heads": (
                disposition_manifest
                if legacy
                else {
                    "entry_count": len(disposition_manifest),
                    "manifest_sha256": sha256_json(disposition_manifest),
                }
            ),
            "disposition_heads_sha256": sha256_json(disposition_manifest),
            "repair_lineage_manifest": (
                repair_manifest
                if legacy
                else {
                    "entry_count": len(repair_manifest),
                    "manifest_sha256": sha256_json(repair_manifest),
                }
            ),
            "repair_lineage_manifest_sha256": sha256_json(repair_manifest),
            "authority_snapshot": (
                self._legacy_authority()
                if legacy
                else (
                    self._full_authority()
                    if revision == BF_PLANNING_SNAPSHOT_FULL_AUDIT_REVISION
                    else self._authority()
                )
            ),
            "blackboard_preview_manifest": (
                legacy_blackboard_manifest if legacy else blackboard_manifest
            ),
            "blackboard_preview_sha256": sha256_json(
                legacy_blackboard_manifest if legacy else blackboard_manifest
            ),
            "workflow_heads": (
                self._legacy_head_manifest() if legacy else self._head_manifest()
            ),
            "background_index_sha256": background_sha,
            "program_math_projection": (
                program_math
                if legacy
                else {
                    "entry_count": len(program_math),
                    "manifest_sha256": sha256_json(program_math),
                }
            ),
            "program_math_queue_head_sha256": sha256_json(program_math),
            "scheduler": "v5_main_four_factor_frontier",
            "score_writeback": False,
            "active_campaign_pointer_used": False,
            "truth_effect": BF_TRUTH_EFFECT,
            "fact_admission_effect": BF_FACT_ADMISSION_EFFECT,
        }
        record = _sealed_record(
            semantic,
            id_key="planning_snapshot_id",
            prefix="bfps-",
            created_at=_now(),
        )
        _bounded(record, "Brave Future planning snapshot")
        return _validate_planning_snapshot(record)

    def revalidate(self, snapshot: dict[str, Any], policy_status: dict[str, Any]) -> bool:
        snapshot = _validate_planning_snapshot(snapshot)
        current = self.preview(
            campaign_id=snapshot["campaign_id"],
            policy_status=policy_status,
            revision=snapshot["revision"],
        )
        return current["semantic_sha256"] == snapshot["semantic_sha256"]


class RepairLineageProjector:
    def __init__(self, store: Any) -> None:
        self.store = store
        self.lifecycle = store.v5_lifecycle()

    @staticmethod
    def _effective_statuses(
        bases: dict[str, dict[str, Any]], dispositions: dict[str, dict[str, Any]]
    ) -> dict[str, str]:
        return {
            research_id: (
                dispositions[research_id]["metadata"]["disposition_status"]
                if research_id in dispositions
                else record["status"]
            )
            for research_id, record in bases.items()
        }

    @staticmethod
    def _cycles(edges: list[tuple[str, str]]) -> set[str]:
        outgoing: dict[str, list[str]] = {}
        for predecessor, successor in edges:
            outgoing.setdefault(predecessor, []).append(successor)
        visiting: set[str] = set()
        visited: set[str] = set()
        cyclic: set[str] = set()

        def visit(node: str, path: list[str]) -> None:
            if node in visiting:
                start = path.index(node) if node in path else 0
                cyclic.update(path[start:])
                return
            if node in visited:
                return
            visiting.add(node)
            path.append(node)
            for child in outgoing.get(node, []):
                visit(child, path)
            path.pop()
            visiting.remove(node)
            visited.add(node)

        for node in sorted(outgoing):
            visit(node, [])
        return cyclic

    @staticmethod
    def _paper_and_program_drift(
        predecessor: dict[str, Any], successor: dict[str, Any]
    ) -> list[str]:
        errors: list[str] = []
        predecessor_meta = predecessor.get("metadata", {})
        successor_meta = successor.get("metadata", {})
        paper_keys = {
            key
            for key in predecessor_meta
            if key.startswith("paper_") or key == "research_draft_ref"
        }
        for key in sorted(paper_keys):
            if successor_meta.get(key) != predecessor_meta.get(key):
                errors.append(f"paper_mapping_drift:{key}")
        if (
            predecessor_meta.get("program_math_review") is not None
            and successor_meta.get("program_math_review")
            != predecessor_meta.get("program_math_review")
        ):
            errors.append("program_math_obligation_drift")
        return errors

    def project(
        self,
        *,
        snapshot: dict[str, Any],
        view: str,
        collapse_repairs: bool,
        limit: int,
    ) -> dict[str, Any]:
        if view not in BF_VIEWS:
            raise ValueError("Brave Future frontier view is invalid")
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("Brave Future frontier limit must be positive")
        if limit > BF_PROJECTION_MEMBER_LIMIT:
            raise ValueError(
                "Brave Future frontier limit must not exceed "
                f"{BF_PROJECTION_MEMBER_LIMIT}"
            )
        campaign_id = validate_campaign_id(snapshot["campaign_id"])
        records = self.lifecycle.research_envelopes()
        bases, dispositions = PlanningSnapshotBuilder._effective_research(
            records, campaign_id
        )
        if sha256_json(
            [
                {
                    "research_id": research_id,
                    "record_sha256": record["record_sha256"],
                    "kind": record["kind"],
                    "status": record["status"],
                }
                for research_id, record in sorted(bases.items())
            ]
        ) != snapshot["research_manifest_sha256"]:
            raise ValueError("Brave Future Research manifest drifted from planning snapshot")
        statuses = self._effective_statuses(bases, dispositions)
        invalidators: dict[str, set[str]] = {research_id: set() for research_id in bases}
        for invalidator_id, record in bases.items():
            if statuses[invalidator_id] not in ACTIVE_MEMORY_STATUSES:
                continue
            for target_id in record.get("metadata", {}).get("route_invalidations", []):
                if target_id in invalidators:
                    invalidators[target_id].add(invalidator_id)

        contracts: dict[str, dict[str, Any]] = {}
        lineage_edges: list[tuple[str, str]] = []
        failed_repairs: dict[str, list[str]] = {}
        for research_id, record in sorted(bases.items()):
            try:
                contract = validate_repair_contract_semantics(record, bases)
            except Exception as exc:
                if record.get("metadata", {}).get("brave_future_repair_contract") is not None:
                    failed_repairs[research_id] = [str(exc)]
                continue
            if contract is None:
                if record["kind"] == "repair" and record.get("metadata", {}).get(
                    "repair_of_research_id"
                ):
                    failed_repairs[research_id] = ["legacy_repair_contract_is_not_collapsible"]
                continue
            contracts[research_id] = contract
            lineage_edges.extend(
                (predecessor_id, research_id)
                for predecessor_id in contract["predecessor_research_ids"]
            )
        cyclic = self._cycles(lineage_edges)
        for research_id in sorted(cyclic):
            failed_repairs.setdefault(research_id, []).append("repair_lineage_cycle")

        successors: dict[str, list[str]] = {}
        for predecessor_id, successor_id in lineage_edges:
            successors.setdefault(predecessor_id, []).append(successor_id)

        collapse_map: dict[str, list[str]] = {}
        residual_surface: dict[str, list[str]] = {}
        for predecessor_id, successor_ids in sorted(successors.items()):
            reasons: list[str] = []
            eligible_successors = [
                successor_id
                for successor_id in sorted(set(successor_ids))
                if successor_id not in failed_repairs
                and successor_id not in cyclic
                and statuses.get(successor_id) in ACTIVE_MEMORY_STATUSES
                and not invalidators.get(successor_id)
            ]
            if not eligible_successors:
                reasons.append("no_current_hash_valid_successor")
            strategies = [contracts[item]["strategy"] for item in eligible_successors]
            if len(eligible_successors) > 1 and any(
                strategy != "split" for strategy in strategies
            ):
                reasons.append("conflicting_complete_successors")
            obligations = set(_obligation_keys(bases[predecessor_id]))
            covered: set[str] = set()
            inherited: set[str] = set()
            disposed: set[str] = set()
            residuals: set[str] = set()
            for successor_id in eligible_successors:
                contract = contracts[successor_id]
                for item in contract["coverage"]:
                    if item["predecessor_research_id"] == predecessor_id:
                        supports = item["supporting_research_ids"]
                        if item["outcome"] == "resolved" and any(
                            statuses.get(research_id) not in ACTIVE_MEMORY_STATUSES
                            for research_id in supports
                        ):
                            reasons.append(
                                "coverage_support_not_current:"
                                + item["obligation_key"]
                            )
                            continue
                        if item["outcome"] == "rehome" and not any(
                            research_id in eligible_successors
                            and statuses.get(research_id) in ACTIVE_MEMORY_STATUSES
                            for research_id in supports
                        ):
                            reasons.append(
                                "coverage_rehome_not_visible:"
                                + item["obligation_key"]
                            )
                            continue
                        covered.add(item["obligation_key"])
                inherited.update(contract["inherited_invalidator_ids"])
                disposed.update(contract["disposed_invalidator_ids"])
                residuals.update(contract["residual_obligations"])
                reasons.extend(
                    self._paper_and_program_drift(
                        bases[predecessor_id], bases[successor_id]
                    )
                )
            missing_obligations = sorted(obligations.difference(covered))
            if missing_obligations:
                reasons.append("uncovered_obligations:" + ",".join(missing_obligations))
            if residuals:
                reasons.append("residual_obligations:" + ",".join(sorted(residuals)))
            falsely_disposed = sorted(
                invalidators[predecessor_id].intersection(disposed)
            )
            if falsely_disposed:
                reasons.append(
                    "invalidators_claimed_disposed_but_still_live:"
                    + ",".join(falsely_disposed)
                )
            missing_invalidators = sorted(
                invalidators[predecessor_id].difference(inherited)
            )
            if missing_invalidators:
                reasons.append("unhandled_invalidators:" + ",".join(missing_invalidators))
            if reasons:
                residual_surface[predecessor_id] = sorted(set(reasons))
            else:
                collapse_map[predecessor_id] = eligible_successors

        # A newly prepared goal Campaign is intentionally not normally visible
        # until the terminal intake receipt.  It cannot yet own Research, so
        # the pure preflight projection is exactly empty and must not force a
        # premature CampaignStore lookup.
        full_frontier = (
            self.lifecycle.frontier(
                limit=max(1, len(bases)),
                include_history=True,
                campaign_id=campaign_id,
                _research_records_override=records,
            )
            if bases
            else []
        )
        frontier_by_id = {item["research_id"]: item for item in full_frontier}
        ordered_ids = [item["research_id"] for item in full_frontier]
        ordered_ids.extend(sorted(set(bases).difference(ordered_ids)))
        entries: list[dict[str, Any]] = []
        collapsed_ids = set(collapse_map) if collapse_repairs else set()
        for research_id in ordered_ids:
            record = bases[research_id]
            status = statuses[research_id]
            is_active = status in ACTIVE_MEMORY_STATUSES
            if research_id in failed_repairs:
                projection_status = "failed_repair"
            elif status == "blocked":
                projection_status = "blocked"
            elif not is_active:
                projection_status = "historical_disposed"
            elif research_id in collapsed_ids:
                projection_status = (
                    "collapsed_split_parent"
                    if all(
                        contracts[child]["strategy"] == "split"
                        for child in collapse_map[research_id]
                    )
                    else "collapsed_repaired"
                )
            elif research_id in residual_surface:
                projection_status = "actionable_residual"
            elif invalidators.get(research_id):
                projection_status = "stale_by_route_invalidation"
            elif research_id in contracts:
                projection_status = "current_repair_leaf"
            else:
                projection_status = "actionable_current"
            if projection_status not in BF_PROJECTION_STATUSES:
                raise AssertionError(projection_status)
            if view == "actionable" and (
                (
                    not is_active
                    and projection_status
                    not in {"failed_repair", "blocked", "actionable_residual"}
                )
                or projection_status in {"collapsed_repaired", "collapsed_split_parent"}
            ):
                continue
            if view == "all-active" and not is_active:
                continue
            scoring = frontier_by_id.get(research_id, {})
            entries.append(
                {
                    "research_id": research_id,
                    "record_sha256": record["record_sha256"],
                    "kind": record["kind"],
                    "status": status,
                    "projection_status": projection_status,
                    "route_invalidator_ids": sorted(invalidators.get(research_id, set())),
                    "residual_reasons": residual_surface.get(research_id, []),
                    "score": scoring.get("score"),
                    "decision_factors": scoring.get("decision_factors"),
                    "score_model": scoring.get("score_model"),
                    "score_role": scoring.get("score_role"),
                    "readiness": scoring.get("readiness"),
                }
            )
        full_manifest = [
            {
                "research_id": item["research_id"],
                "record_sha256": item["record_sha256"],
                "projection_status": item["projection_status"],
                "score_bytes_sha256": sha256_json(
                    {
                        "score": item["score"],
                        "decision_factors": item["decision_factors"],
                        "score_model": item["score_model"],
                        "score_role": item["score_role"],
                        "readiness": item["readiness"],
                    }
                ),
            }
            for item in entries
        ]
        member_window_limit = BF_PROJECTION_MEMBER_LIMIT
        # Preserve the exact pre-bounding semantics whenever the complete
        # Campaign fits in one member window.  In particular, a successfully
        # collapsed predecessor is intentionally absent from ``entries`` but
        # remains a load-bearing key in ``collapse_map``.  Deriving window
        # membership from visible entries alone would therefore erase valid
        # L4 relations even on a three-node Campaign.
        retained_ids = (
            set(bases)
            if len(bases) <= member_window_limit
            else {
                item["research_id"]
                for item in entries[:member_window_limit]
            }
        )
        bounded_lineage_edges = [
            {
                "predecessor_research_id": predecessor,
                "successor_research_id": successor,
                "relation": bases[successor]["relation"],
                "strategy": contracts.get(successor, {}).get("strategy"),
            }
            for predecessor, successor in sorted(lineage_edges)
            if predecessor in retained_ids and successor in retained_ids
        ][:BF_PROJECTION_RELATION_LIMIT]
        bounded_collapse_map = {
            key: [child for child in value if child in retained_ids][
                :BF_PROJECTION_PER_MEMBER_RELATION_LIMIT
            ]
            for key, value in sorted(collapse_map.items())
            if key in retained_ids and any(child in retained_ids for child in value)
        }
        bounded_residual_surface = {
            key: value[:BF_PROJECTION_PER_MEMBER_RELATION_LIMIT]
            for key, value in sorted(residual_surface.items())
            if key in retained_ids
        }
        bounded_failed_repairs = {
            key: value[:BF_PROJECTION_PER_MEMBER_RELATION_LIMIT]
            for key, value in sorted(failed_repairs.items())
            if key in retained_ids
        }
        bounded_invalidators = {
            key: sorted(value)[:BF_PROJECTION_PER_MEMBER_RELATION_LIMIT]
            for key, value in sorted(invalidators.items())
            if key in retained_ids and value
        }
        bounded_obligations = {
            key: _obligation_keys(record)[:BF_PROJECTION_PER_MEMBER_RELATION_LIMIT]
            for key, record in sorted(bases.items())
            if key in retained_ids and _obligation_keys(record)
        }
        bounded_entries = [
            {
                **item,
                "route_invalidator_ids": item["route_invalidator_ids"][
                    :BF_PROJECTION_PER_MEMBER_RELATION_LIMIT
                ],
                "residual_reasons": item["residual_reasons"][
                    :BF_PROJECTION_PER_MEMBER_RELATION_LIMIT
                ],
            }
            for item in entries[:limit]
        ]
        # The complete Campaign generation remains bound by the snapshot's
        # Research manifest and this full digest.  BF-1 transports only a fixed
        # local member/relation window; otherwise a large project would defeat
        # the advisory local_graph_node_limit by serializing the entire tree.
        bounded_full_manifest = full_manifest[:member_window_limit]
        semantic = {
            "revision": BF_FRONTIER_PROJECTION_REVISION,
            "project_id": self.store.project_id(),
            "campaign_id": campaign_id,
            "planning_snapshot_id": snapshot["planning_snapshot_id"],
            "planning_snapshot_semantic_sha256": snapshot["semantic_sha256"],
            "view": view,
            "collapse_repairs": bool(collapse_repairs),
            "lineage_edges": bounded_lineage_edges,
            "collapse_map": bounded_collapse_map,
            "residual_surface": bounded_residual_surface,
            "failed_repairs": bounded_failed_repairs,
            "invalidator_inventory": bounded_invalidators,
            "obligation_inventory": bounded_obligations,
            "eligible_manifest_window": bounded_full_manifest,
            "eligible_manifest_window_limit": member_window_limit,
            "eligible_manifest_total_count": len(full_manifest),
            "eligible_manifest_sha256": sha256_json(full_manifest),
            "entries": bounded_entries,
            "omitted_count": max(0, len(entries) - limit),
            "scheduler": "v5_main_four_factor_frontier",
            "score_writeback": False,
            "truth_effect": BF_TRUTH_EFFECT,
            "fact_admission_effect": BF_FACT_ADMISSION_EFFECT,
        }
        record = _sealed_record(
            semantic,
            id_key="projection_id",
            prefix="bfp-",
            created_at=snapshot["created_at"],
        )
        _bounded(record, "Brave Future frontier projection")
        return record


class BlockageValidator:
    _FIELDS = {
        "revision",
        "campaign_id",
        "target_research_id",
        "blocked_route_research_ids",
        "blocker_class",
        "method_family",
        "method_descriptor_sha256",
        "attempts",
        "information_gained_research_ids",
        "remaining_obligation_keys",
        "mechanical_extension_failure",
        "operator_constraints",
        "planning_snapshot_id",
        "created_by",
        "truth_effect",
        "fact_admission_effect",
    }
    _ATTEMPT_FIELDS = {
        "round_id",
        "assignment_id",
        "task_card_sha256",
        "result_research_ids",
        "result",
    }

    def __init__(self, store: Any) -> None:
        self.store = store
        self.lifecycle = store.v5_lifecycle()

    def validate(
        self, payload: Any, *, snapshot: dict[str, Any]
    ) -> dict[str, Any]:
        value = _exact(payload, self._FIELDS, "Brave Future blockage input")
        if value.get("revision") != BF_BLOCKAGE_REVISION:
            raise ValueError("Brave Future blockage revision is invalid")
        campaign_id = validate_campaign_id(value.get("campaign_id"))
        if campaign_id != snapshot["campaign_id"]:
            raise ValueError("Brave Future blockage Campaign/snapshot mismatch")
        if value.get("planning_snapshot_id") != snapshot["planning_snapshot_id"]:
            raise ValueError("Brave Future blockage planning snapshot mismatch")
        if value.get("truth_effect") != BF_TRUTH_EFFECT or value.get(
            "fact_admission_effect"
        ) != BF_FACT_ADMISSION_EFFECT:
            raise ValueError("Brave Future blockage truth boundary is invalid")
        target_id = validate_memory_id(value.get("target_research_id"))
        blocked_ids = _strings(
            value.get("blocked_route_research_ids"),
            "blocked route Research ids",
            nonempty=True,
        )
        if target_id not in blocked_ids:
            raise ValueError("blocked routes must include the target Research")
        information_ids = _strings(
            value.get("information_gained_research_ids"),
            "information-gained Research ids",
            nonempty=True,
        )
        records = {
            record["research_id"]: record for record in self.lifecycle.research_records()
        }
        for research_id in {*blocked_ids, *information_ids}:
            validate_memory_id(research_id)
            record = records.get(research_id)
            if record is None:
                raise ValueError(f"blockage references unknown Research: {research_id}")
            if record.get("metadata", {}).get("campaign_id") != campaign_id:
                raise ValueError("blockage references cross-Campaign Research")
        if value.get("blocker_class") not in BF_BLOCKER_CLASSES:
            raise ValueError("Brave Future blockage class is ineligible")
        _text(value.get("method_family"), "blockage method family")
        _validate_sha(value.get("method_descriptor_sha256"), "blockage method descriptor")
        remaining = _strings(
            value.get("remaining_obligation_keys"),
            "remaining blockage obligations",
            nonempty=True,
        )
        failure = _text(
            value.get("mechanical_extension_failure"),
            "mechanical-extension failure explanation",
        )
        if "chx-" in failure.lower() or "architecture issue" in failure.lower():
            raise ValueError("CHX architecture issues are not Brave Future blockages")
        _strings(value.get("operator_constraints"), "blockage Operator constraints")
        _text(value.get("created_by"), "blockage creator")
        attempts = value.get("attempts")
        if not isinstance(attempts, list) or not attempts:
            raise ValueError("a Brave Future blockage requires at least one exact ingested attempt")
        for attempt in attempts:
            attempt = _exact(attempt, self._ATTEMPT_FIELDS, "blockage attempt")
            round_id = validate_round_id(attempt.get("round_id"))
            assignment_id = validate_assignment_id(attempt.get("assignment_id"))
            task_sha = _validate_sha(
                attempt.get("task_card_sha256"), "blockage task-card hash"
            )
            result_ids = _strings(
                attempt.get("result_research_ids"),
                "blockage result Research ids",
                nonempty=True,
            )
            if attempt.get("result") not in BF_ATTEMPT_RESULTS:
                raise ValueError("Brave Future blockage attempt result is invalid")
            round_dir, manifest = self.lifecycle._round_manifest(round_id)
            assignment = next(
                (
                    item
                    for item in manifest["assignments"]
                    if item["assignment_id"] == assignment_id
                ),
                None,
            )
            if assignment is None or assignment["task_card_sha256"] != task_sha:
                raise ValueError("blockage attempt is not bound to the frozen task card")
            product, _receipt = self.lifecycle._research_product_for_assignment(
                round_dir=round_dir,
                manifest=manifest,
                assignment=assignment,
            )
            if product["research_id"] not in result_ids:
                raise ValueError("blockage result ids omit the worker Research product")
            for research_id in result_ids:
                record = records.get(research_id)
                if record is None or record.get("metadata", {}).get("campaign_id") != campaign_id:
                    raise ValueError("blockage attempt result is unknown or cross-Campaign")
        return {
            **value,
            "blocked_route_research_ids": sorted(blocked_ids),
            "information_gained_research_ids": sorted(information_ids),
            "remaining_obligation_keys": sorted(remaining),
        }

    @staticmethod
    def signature(blockage: dict[str, Any], *, snapshot: dict[str, Any]) -> str:
        semantic = {
            "campaign_id": blockage["campaign_id"],
            "target_research_id": blockage["target_research_id"],
            "blocked_route_research_ids": sorted(
                blockage["blocked_route_research_ids"]
            ),
            "blocker_class": blockage["blocker_class"],
            "method_family": blockage["method_family"],
            "method_descriptor_sha256": blockage["method_descriptor_sha256"],
            "remaining_obligation_keys": sorted(
                blockage["remaining_obligation_keys"]
            ),
            "research_manifest_sha256": snapshot["research_manifest_sha256"],
            "disposition_heads_sha256": snapshot["disposition_heads_sha256"],
            "authority_snapshot_sha256": snapshot["authority_snapshot"][
                "authority_snapshot_sha256"
            ],
            "workflow_heads_sha256": sha256_json(snapshot["workflow_heads"]),
            "program_math_queue_head_sha256": snapshot[
                "program_math_queue_head_sha256"
            ],
        }
        return sha256_json(semantic)


class StepBackPlanner:
    _BLOCKER_ACTIONS = {
        "missing_prerequisite": "inspect_prerequisite",
        "surviving_counterexample": "test_counterexample",
        "scope_or_quantifier_mismatch": "split_target",
        "source_or_applicability_gap": "recheck_source_or_applicability",
        "representation_mismatch": "retry_with_changed_method",
        "program_math_failure": "run_program_math_review",
        "method_exhaustion": "switch_sibling_route",
        "dependency_conflict": "inspect_prerequisite",
        "resource_bound_requiring_reformulation": "split_target",
    }

    def __init__(self, store: Any) -> None:
        self.store = store
        self.lifecycle = store.v5_lifecycle()

    def reassess(
        self,
        *,
        snapshot: dict[str, Any],
        projection: dict[str, Any],
        blockage: dict[str, Any],
        policy: dict[str, Any],
        blockage_signature: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        blocked = set(blockage["blocked_route_research_ids"])
        records = {
            record["research_id"]: record
            for record in self.lifecycle.research_records()
            if record["kind"] != "disposition"
        }
        manifest_window = projection.get(
            "eligible_manifest_window",
            projection.get("full_eligible_manifest", []),
        )
        projection_status = {
            item["research_id"]: item for item in manifest_window
        }
        score_order = {
            item["research_id"]: index
            for index, item in enumerate(projection["entries"])
        }
        candidates: list[dict[str, Any]] = []
        target = records[blockage["target_research_id"]]
        target_related = set(target.get("related_research_ids", []))
        for research_id, item in projection_status.items():
            if research_id in blocked:
                continue
            if item["projection_status"] not in {
                "actionable_current",
                "actionable_residual",
                "current_repair_leaf",
            }:
                continue
            record = records[research_id]
            related = set(record.get("related_research_ids", []))
            if blockage["target_research_id"] in related or research_id in target_related:
                relevance = "direct"
                rank = 0
            elif record["kind"] in {"challenge", "counterexample", "obstacle"}:
                relevance = "diagnostic"
                rank = 1
            else:
                relevance = "indirect"
                rank = 2
            contract = record.get("metadata", {}).get("brave_future_repair_contract")
            method_family = (
                contract.get("method_family")
                if isinstance(contract, dict)
                else record.get("metadata", {}).get("method_family", record["kind"])
            )
            method_distance = (
                "same"
                if method_family == blockage["method_family"]
                else (
                    "orthogonal"
                    if record["kind"] in {"counterexample", "computation", "literature"}
                    else "adjacent"
                )
            )
            candidates.append(
                {
                    "research_id": research_id,
                    "record_sha256": record["record_sha256"],
                    "action": self._BLOCKER_ACTIONS[blockage["blocker_class"]],
                    "blocker_relevance": relevance,
                    "method_family": str(method_family),
                    "method_distance": method_distance,
                    "reuse_value": len(related.union(target_related)),
                    "suggested_l2_mode": (
                        "refute"
                        if record["kind"] in {"challenge", "counterexample", "obstacle"}
                        else (
                            "compute"
                            if record["kind"] == "computation"
                            else (
                                "literature"
                                if record["kind"] == "literature"
                                else "prove"
                            )
                        )
                    ),
                    "why_not_mechanical_extension": (
                        "Selects an existing route with a different frozen Research identity "
                        "or method family; it does not extend the blocked route in place."
                    ),
                    "expected_information_gain": (
                        "Tests the recorded blocker against reusable Campaign evidence."
                    ),
                    "stop_conditions": [
                        "stop after one bounded Research work unit",
                        "return to Operator review before any plan or dispatch",
                    ],
                    "_rank": rank,
                    "_score_order": score_order.get(research_id, 10**9),
                }
            )
        candidates.sort(
            key=lambda item: (
                item["_rank"],
                item["_score_order"],
                item["research_id"],
            )
        )
        full_candidates = [
            {key: value for key, value in item.items() if not key.startswith("_")}
            for item in candidates
        ]
        manifest_semantic = {
            "revision": BF_CANDIDATE_MANIFEST_REVISION,
            "project_id": self.store.project_id(),
            "campaign_id": blockage["campaign_id"],
            "planning_snapshot_id": snapshot["planning_snapshot_id"],
            "frontier_projection_id": projection["projection_id"],
            "blockage_signature": blockage_signature,
            "candidates": full_candidates,
            "candidate_count": len(full_candidates),
            "truth_effect": BF_TRUTH_EFFECT,
            "fact_admission_effect": BF_FACT_ADMISSION_EFFECT,
        }
        manifest = _sealed_record(
            manifest_semantic,
            id_key="candidate_manifest_id",
            prefix="bfcm-",
            created_at=snapshot["created_at"],
        )
        _bounded(manifest, "Brave Future candidate manifest")
        selected: list[dict[str, Any]] = []
        family_counts: dict[str, int] = {}
        for item in full_candidates:
            family = item["method_family"]
            if family_counts.get(family, 0) >= 2:
                continue
            selected.append(item)
            family_counts[family] = family_counts.get(family, 0) + 1
            if len(selected) >= policy["shortlist_limit"]:
                break
        recommended = selected[0]["action"] if selected else "park_and_escalate"
        if recommended not in BF_ACTIONS:
            raise AssertionError(recommended)
        return manifest, {
            "shortlist": selected,
            "omitted_count": len(full_candidates) - len(selected),
            "recommended_action": recommended,
        }


class BraveFutureManager:
    def __init__(self, store: Any) -> None:
        self.store = store
        self.root = store.root / "governance" / "brave-future"
        self.policy_store = BraveFuturePolicyStore(store)
        self.snapshot_builder = PlanningSnapshotBuilder(store)
        self.projector = RepairLineageProjector(store)
        self.blockage_validator = BlockageValidator(store)
        self.planner = StepBackPlanner(store)

    def _campaign_root(self, campaign_id: str) -> Path:
        return self.root / "campaigns" / validate_campaign_id(campaign_id)

    def _transactions_dir(self, campaign_id: str) -> Path:
        return self._campaign_root(campaign_id) / "transactions"

    def _transaction_path(self, campaign_id: str, reassessment_id: str) -> Path:
        return self._transactions_dir(campaign_id) / _validate_bf_id(
            reassessment_id, "reassessment_id"
        )

    def _read_transaction(
        self, campaign_id: str, reassessment_id: str
    ) -> dict[str, dict[str, Any]]:
        directory = self._transaction_path(campaign_id, reassessment_id)
        if directory.is_symlink() or not directory.is_dir():
            raise KeyError(f"unknown Brave Future reassessment: {reassessment_id}")
        expected = {
            "blockage.json",
            "planning-snapshot.json",
            "frontier-projection.json",
            "candidate-manifest.json",
            "reassessment.json",
            "transaction-manifest.json",
        }
        actual = {item.name for item in directory.iterdir()}
        if actual != expected or any(item.is_symlink() for item in directory.iterdir()):
            raise ValueError("Brave Future transaction object set is not exact")
        objects = {
            name.removesuffix(".json"): json.loads(
                (directory / name).read_text(encoding="utf-8")
            )
            for name in expected.difference({"transaction-manifest.json"})
        }
        manifest = json.loads(
            (directory / "transaction-manifest.json").read_text(encoding="utf-8")
        )
        expected_manifest = {
            "revision": "chalxius-bf-atomic-transaction-1",
            "campaign_id": campaign_id,
            "reassessment_id": reassessment_id,
            "objects": [
                {
                    "filename": name,
                    "sha256": sha256_bytes((directory / name).read_bytes()),
                }
                for name in sorted(expected.difference({"transaction-manifest.json"}))
            ],
            "truth_effect": BF_TRUTH_EFFECT,
            "fact_admission_effect": BF_FACT_ADMISSION_EFFECT,
        }
        if manifest != expected_manifest:
            raise ValueError("Brave Future atomic transaction manifest mismatch")
        snapshot = _validate_planning_snapshot(objects["planning-snapshot"])
        projection = _validate_frontier_projection(objects["frontier-projection"])
        blockage = _validate_sealed_record(
            objects["blockage"],
            semantic_fields=set(BlockageValidator._FIELDS),
            id_key="blockage_id",
            prefix="bfb-",
            revision=BF_BLOCKAGE_REVISION,
            label="Brave Future blockage",
        )
        candidate = _validate_sealed_record(
            objects["candidate-manifest"],
            semantic_fields=_CANDIDATE_MANIFEST_SEMANTIC_FIELDS,
            id_key="candidate_manifest_id",
            prefix="bfcm-",
            revision=BF_CANDIDATE_MANIFEST_REVISION,
            label="Brave Future candidate manifest",
        )
        reassessment = _validate_sealed_record(
            objects["reassessment"],
            semantic_fields=_REASSESSMENT_SEMANTIC_FIELDS,
            id_key="reassessment_id",
            prefix="bfr-",
            revision=BF_REASSESSMENT_REVISION,
            label="Brave Future reassessment",
        )
        if any(
            item["campaign_id"] != campaign_id
            for item in (snapshot, projection, blockage, candidate, reassessment)
        ):
            raise ValueError("Brave Future transaction crosses Campaigns")
        if (
            reassessment["reassessment_id"] != reassessment_id
            or projection["planning_snapshot_id"]
            != snapshot["planning_snapshot_id"]
            or blockage["planning_snapshot_id"]
            != snapshot["planning_snapshot_id"]
            or candidate["planning_snapshot_id"]
            != snapshot["planning_snapshot_id"]
            or reassessment["planning_snapshot_id"]
            != snapshot["planning_snapshot_id"]
            or candidate["frontier_projection_id"] != projection["projection_id"]
            or reassessment["frontier_projection_id"] != projection["projection_id"]
            or reassessment["blockage_id"] != blockage["blockage_id"]
            or reassessment["candidate_manifest_id"]
            != candidate["candidate_manifest_id"]
            or reassessment["candidate_manifest_sha256"]
            != candidate["record_sha256"]
            or reassessment["blockage_signature"]
            != candidate["blockage_signature"]
        ):
            raise ValueError("Brave Future transaction references are inconsistent")
        if (
            reassessment["autonomy_level"] != "advisory"
            or reassessment["plan_effect"] != "none"
            or reassessment["dispatch_effect"] != "none"
            or reassessment["campaign_close_effect"] != "none"
        ):
            raise ValueError("Brave Future reassessment exceeded advisory authority")
        return objects

    def _transactions(self, campaign_id: str) -> list[dict[str, dict[str, Any]]]:
        directory = self._transactions_dir(campaign_id)
        if not directory.exists():
            return []
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError("Brave Future transactions directory is unsafe")
        result = []
        for path in sorted(directory.iterdir()):
            if path.name.startswith("."):
                continue
            result.append(self._read_transaction(campaign_id, path.name))
        return result

    def _decisions_path(self, campaign_id: str) -> Path:
        return self._campaign_root(campaign_id) / "decisions.jsonl"

    def _decisions(self, campaign_id: str) -> list[dict[str, Any]]:
        path = self._decisions_path(campaign_id)
        if not path.exists():
            return []
        if path.is_symlink() or not path.is_file():
            raise ValueError("Brave Future decision ledger is unsafe")
        decisions: list[dict[str, Any]] = []
        for raw in path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            decision = json.loads(raw)
            semantic_fields = {
                "revision",
                "project_id",
                "campaign_id",
                "reassessment_id",
                "action",
                "selected_research_ids",
                "modified_proposal",
                "reason",
                "actor",
                "plan_effect",
                "dispatch_effect",
                "campaign_close_effect",
                "truth_effect",
                "fact_admission_effect",
            }
            _validate_sealed_record(
                decision,
                semantic_fields=semantic_fields,
                id_key="decision_id",
                prefix="bfd-",
                revision=BF_DECISION_REVISION,
                label="Brave Future decision",
            )
            if decision["campaign_id"] != campaign_id:
                raise ValueError("Brave Future decision ledger Campaign mismatch")
            decisions.append(decision)
        return decisions

    def status(self, campaign_id: str) -> dict[str, Any]:
        policy = self.policy_store.status(campaign_id)
        transactions = self._transactions(campaign_id)
        decisions = self._decisions(campaign_id)
        return {
            **policy,
            "reassessment_count": len(transactions),
            "decision_count": len(decisions),
            "latest_reassessment_id": (
                transactions[-1]["reassessment"]["reassessment_id"]
                if transactions
                else None
            ),
            "sidecar_only": True,
            "automatic_plan": False,
            "automatic_dispatch": False,
        }

    def enable(
        self, *, campaign_id: str, policy: dict[str, Any], actor: str
    ) -> dict[str, Any]:
        return self.policy_store.enable(
            campaign_id=campaign_id, policy=policy, actor=actor
        )

    def intake_research_goal(
        self,
        *,
        goal_input: dict[str, Any],
        actor: str,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Compile an ordinary-language research goal into advisory BF scope.

        The user supplies an exact objective, not a Campaign id.  Under
        ``reasoning_mode=auto`` or ``reasoning_mode=deep`` the compiler reuses
        one lexical exact match or prepares a new Campaign, enables only the
        fixed advisory policy, and computes BF-1 before either Campaign/BF
        selection becomes visible.  Intent, effects, and effect receipts are
        replayable nontruth outbox state; one terminal receipt is the shared
        visibility gate.  Ordinary reads never repair a pending intake.
        """

        validated = validate_goal_intake(goal_input)
        actor = _text(actor, "Brave Future goal-intake actor")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("Brave Future goal-intake limit must lie in [1,100]")
        mode_status = self.store.reasoning_modes().status()
        reasoning_mode = mode_status.get("reasoning_mode")
        if reasoning_mode not in {"auto", "deep"}:
            raise ValueError(
                "automatic research-goal intake requires reasoning_mode=auto or "
                "reasoning_mode=deep; use the explicit Campaign and Brave Future "
                "commands in fast"
            )
        objective = validated["objective"]
        objective_sha256 = sha256_bytes(objective.encode("utf-8"))
        with self.store.v5_mutation_lock(command="research-goal-intake"):
            # Validate the global activation chain before a new Campaign can
            # become visible. A corrupt pre-existing BF sidecar must fail with
            # a byte-identical Campaign store.
            self.policy_store._events()
            campaigns = self.store.campaigns()
            matches = campaigns.exact_objective_matches(objective)
            if len(matches) > 1:
                raise ValueError(
                    "research objective matches multiple exact Campaigns; "
                    f"operator resolution is required: {matches}"
                )
            if matches:
                campaign_id = matches[0]
                campaign_resolution = "exact_objective_reused"
                campaign_created = False
                campaign_status = campaigns.status(campaign_id)
                campaign_effect_payload = {
                    "revision": "chalxius-goal-intake-campaign-effect-1",
                    "operation": "reuse",
                    "campaign_id": campaign_id,
                    "campaign_status_sha256": sha256_json(
                        {
                            key: item
                            for key, item in campaign_status.items()
                            if key != "active"
                        }
                    ),
                }
            else:
                campaign_effect_payload = campaigns.prepare_goal_intake_create(
                    {
                        "name": f"Research goal {objective_sha256[:12]}",
                        "objective": objective,
                        "source_claim_ids": [],
                        "targets": [],
                        "constraints": [
                            "Preserve the exact research objective unless the "
                            "Operator authorizes a revision."
                        ],
                        "stop_conditions": [
                            "The user withdraws, replaces, or completes this exact "
                            "research objective."
                        ],
                        "value_definition": (
                            "Prefer high-information, feasible, low-burden work that "
                            "advances the exact objective."
                        ),
                    },
                    actor=actor,
                )
                campaign_id = campaign_effect_payload["campaign_id"]
                campaign_status = campaign_effect_payload["status"]
                campaign_resolution = "created_from_exact_user_goal"
                campaign_created = True
                pending_path = campaigns.root / campaign_id
                if pending_path.exists():
                    marker = campaigns._goal_intake_marker(campaign_id)
                    existing_events = campaigns._read_jsonl(
                        pending_path / "events.jsonl"
                    )
                    if (
                        marker is None
                        or existing_events != campaign_effect_payload["events"]
                    ):
                        raise ValueError(f"campaign id collision: {campaign_id}")
            if campaign_created:
                current = {
                    "revision": BF_POLICY_REVISION,
                    "campaign_id": campaign_id,
                    "enabled": False,
                    "policy": None,
                    "head_event_sha256": None,
                    "epoch": 0,
                    "event_count": 0,
                    "active_campaign_pointer_used": False,
                    "autonomy_effect": "none",
                    "truth_effect": BF_TRUTH_EFFECT,
                    "fact_admission_effect": BF_FACT_ADMISSION_EFFECT,
                }
            else:
                current = self.policy_store.status(campaign_id)
            if not current["enabled"] and current["event_count"]:
                raise ValueError(
                    "automatic research-goal intake cannot override an explicit "
                    "Brave Future disablement; obtain a new user re-enable decision"
                )
            policy = {**_FIXED_POLICY, "campaign_id": campaign_id}
            if current["enabled"]:
                if current["policy"] != policy:
                    raise ValueError(
                        "Brave Future is already enabled with another policy"
                    )
                policy_status = current
                activation_effect_payload = {
                    "revision": "chalxius-goal-intake-activation-effect-1",
                    "operation": "reuse",
                    "campaign_id": campaign_id,
                    "policy_head_sha256": current["head_event_sha256"],
                    "policy_epoch": current["epoch"],
                }
                activation_was_new = False
            else:
                activation_semantic = {
                    "revision": "chalxius-goal-intake-activation-effect-1",
                    "event": "enabled",
                    "campaign_id": campaign_id,
                    "policy": policy,
                    "actor": actor,
                    "base_event_count": 0,
                    "base_head_event_sha256": None,
                    "truth_effect": BF_TRUTH_EFFECT,
                    "fact_admission_effect": BF_FACT_ADMISSION_EFFECT,
                }
                activation_event_sha256 = sha256_json(activation_semantic)
                activation_effect_payload = {
                    **activation_semantic,
                    "operation": "activate",
                    "event_sha256": activation_event_sha256,
                }
                policy_status = {
                    "revision": BF_POLICY_REVISION,
                    "campaign_id": campaign_id,
                    "enabled": True,
                    "policy": policy,
                    "head_event_sha256": activation_event_sha256,
                    "epoch": 1,
                    "event_count": 1,
                    "active_campaign_pointer_used": False,
                    "autonomy_effect": "advisory_only",
                    "truth_effect": BF_TRUTH_EFFECT,
                    "fact_admission_effect": BF_FACT_ADMISSION_EFFECT,
                }
                activation_was_new = True

            # The entire BF-1 read/projection and its object budgets are
            # completed before any normal Campaign or BF activation reader can
            # observe this intake.
            snapshot = self.snapshot_builder.preview(
                campaign_id=campaign_id,
                policy_status=policy_status,
                campaign_status_override=campaign_status,
            )
            projection = self.projector.project(
                snapshot=snapshot,
                view="actionable",
                collapse_repairs=True,
                limit=limit,
            )
            bf1 = {
                "planning_snapshot": snapshot,
                "frontier_projection": projection,
                "write_effect": "none",
                "scheduler": "v5_main_four_factor_frontier",
                "truth_effect": BF_TRUTH_EFFECT,
                "fact_admission_effect": BF_FACT_ADMISSION_EFFECT,
            }
            _bounded(snapshot, "goal-intake BF-1 planning snapshot")
            _bounded(projection, "goal-intake BF-1 frontier projection")

            desired_effects = {
                "campaign": seal_goal_intake_effect(
                    kind="campaign", payload=campaign_effect_payload
                ),
                "activation": seal_goal_intake_effect(
                    kind="activation", payload=activation_effect_payload
                ),
                "planning_snapshot": seal_goal_intake_effect(
                    kind="planning_snapshot", payload=snapshot
                ),
                "frontier_projection": seal_goal_intake_effect(
                    kind="frontier_projection", payload=projection
                ),
            }
            for kind, effect in desired_effects.items():
                _bounded(effect, f"goal-intake {kind} effect")
            request = {
                "revision": BF_GOAL_INTAKE_REVISION,
                "objective": objective,
                "objective_sha256": objective_sha256,
                "reasoning_mode": reasoning_mode,
                "limit": limit,
            }
            transaction_store = GoalIntakeTransactionStore(self.store)
            matching_token = transaction_store.find_matching_committed(
                request=request,
                campaign_id=campaign_id,
                planning_snapshot_semantic_sha256=snapshot["semantic_sha256"],
                frontier_projection_semantic_sha256=projection["semantic_sha256"],
            )
            if matching_token is not None:
                terminal, _prior_intent, prior_effects = (
                    transaction_store.load_committed_transaction(matching_token)
                )
                bf1 = {
                    "planning_snapshot": prior_effects["planning_snapshot"]["payload"],
                    "frontier_projection": prior_effects["frontier_projection"]["payload"],
                    "write_effect": "none",
                    "scheduler": "v5_main_four_factor_frontier",
                    "truth_effect": BF_TRUTH_EFFECT,
                    "fact_admission_effect": BF_FACT_ADMISSION_EFFECT,
                }
                intake_token = matching_token
                intake_receipt = terminal
                activation_was_new = False
            else:
                intent = seal_goal_intake_intent(
                    project_id=self.store.project_id(),
                    request=request,
                    campaign_id=campaign_id,
                    campaign_resolution=campaign_resolution,
                    campaign_created=campaign_created,
                    effect_ids={
                        kind: effect["effect_id"]
                        for kind, effect in desired_effects.items()
                    },
                )
                _bounded(intent, "goal-intake intent")
                transaction_store.write_intent(intent)
                transaction_store._checkpoint("intent")
                effects: dict[str, dict[str, Any]] = {}
                for kind in sorted(GOAL_INTAKE_EFFECT_KINDS):
                    effects[kind] = transaction_store.write_effect(
                        desired_effects[kind]
                    )
                    transaction_store._checkpoint(f"effect:{kind}")
                if effects["campaign"]["payload"].get("operation") == "create":
                    campaigns.publish_goal_intake_create(
                        effects["campaign"]["payload"],
                        intake_token=intent["intake_token"],
                        campaign_effect_id=effects["campaign"]["effect_id"],
                    )
                transaction_store._checkpoint("side_effect:campaign")
                transaction_store.write_activation_link(
                    token=intent["intake_token"],
                    campaign_effect_id=effects["campaign"]["effect_id"],
                    activation_effect=effects["activation"],
                )
                # Preserve the legacy activation-ledger location as an empty,
                # non-selecting compatibility object.  The intake activation
                # itself remains receipt-gated in its sidecar link.
                if not self.policy_store.events_path.exists():
                    if self.policy_store.events_path.is_symlink():
                        raise ValueError("Brave Future activation ledger is unsafe")
                    self.policy_store.root.mkdir(parents=True, exist_ok=True)
                    self.store._write_bytes_atomic(
                        self.policy_store.events_path, b""
                    )
                transaction_store._checkpoint("side_effect:activation")
                effect_receipts: dict[str, dict[str, Any]] = {}
                side_effect_states = {
                    "campaign": (
                        "terminal_gated_campaign_published"
                        if effects["campaign"]["payload"].get("operation") == "create"
                        else "existing_campaign_reused"
                    ),
                    "activation": (
                        "terminal_gated_activation_link_published"
                        if effects["activation"]["payload"].get("operation") == "activate"
                        else "existing_activation_reused"
                    ),
                    "planning_snapshot": "content_addressed_snapshot_published",
                    "frontier_projection": "content_addressed_projection_published",
                }
                for kind in sorted(GOAL_INTAKE_EFFECT_KINDS):
                    effect_receipts[kind] = transaction_store.write_effect_receipt(
                        token=intent["intake_token"],
                        effect=effects[kind],
                        side_effect_state=side_effect_states[kind],
                    )
                    _bounded(
                        effect_receipts[kind],
                        f"goal-intake {kind} effect receipt",
                    )
                    transaction_store._checkpoint(f"effect_receipt:{kind}")
                terminal = transaction_store.write_terminal_receipt(
                    intent=intent,
                    effects=effects,
                    effect_receipts=effect_receipts,
                )
                _bounded(terminal, "goal-intake terminal receipt")
                transaction_store._checkpoint("terminal")
                intake_receipt = transaction_store.validate_intake_receipt(
                    intent["intake_token"]
                )
                intake_token = intent["intake_token"]
                bf1 = {
                    "planning_snapshot": effects["planning_snapshot"]["payload"],
                    "frontier_projection": effects["frontier_projection"]["payload"],
                    "write_effect": "none",
                    "scheduler": "v5_main_four_factor_frontier",
                    "truth_effect": BF_TRUTH_EFFECT,
                    "fact_admission_effect": BF_FACT_ADMISSION_EFFECT,
                }
            activation = {
                **self.policy_store.status(campaign_id),
                "write_effect": (
                    "terminal_gated_activation_effect"
                    if activation_was_new
                    else "none"
                ),
                "idempotent": not activation_was_new,
            }
        return {
            "revision": BF_GOAL_INTAKE_REVISION,
            "trigger": f"explicit_user_research_goal_under_{reasoning_mode}",
            "reasoning_mode": reasoning_mode,
            "objective": objective,
            "objective_sha256": objective_sha256,
            "campaign_id": campaign_id,
            "campaign_resolution": campaign_resolution,
            "campaign_created": campaign_created,
            "intake_token": intake_token,
            "intake_receipt": intake_receipt,
            "research_scope": {
                "campaign_id": campaign_id,
                "bind_future_research": True,
                "rebind_existing_untagged_research": False,
            },
            "brave_future_activation": activation,
            "bf1": bf1,
            "bf2_bf3_state": "awaiting_existing_exact_blockage_evidence_gate",
            "active_campaign_pointer_used": False,
            "fuzzy_objective_matching": False,
            "automatic_plan": False,
            "automatic_dispatch": False,
            "research_write_effect": "none",
            "truth_effect": BF_TRUTH_EFFECT,
            "fact_admission_effect": BF_FACT_ADMISSION_EFFECT,
        }

    def validate_intake_receipt(self, intake_token: str) -> dict[str, Any]:
        """Pure-read validation for later memory/round binding."""

        return GoalIntakeTransactionStore(self.store).validate_intake_receipt(
            intake_token
        )

    def disable(self, *, campaign_id: str, actor: str, reason: str) -> dict[str, Any]:
        return self.policy_store.disable(
            campaign_id=campaign_id, actor=actor, reason=reason
        )

    def frontier(
        self,
        *,
        campaign_id: str,
        view: str = "actionable",
        collapse_repairs: bool = True,
        limit: int = 10,
    ) -> dict[str, Any]:
        status = self.policy_store.status(campaign_id)
        if not status["enabled"]:
            raise ValueError("Brave Future is disabled for the explicit Campaign")
        snapshot = self.snapshot_builder.preview(
            campaign_id=campaign_id, policy_status=status
        )
        projection = self.projector.project(
            snapshot=snapshot,
            view=view,
            collapse_repairs=collapse_repairs,
            limit=limit,
        )
        return {
            "planning_snapshot": snapshot,
            "frontier_projection": projection,
            "write_effect": "none",
            "scheduler": "v5_main_four_factor_frontier",
            "truth_effect": BF_TRUTH_EFFECT,
            "fact_admission_effect": BF_FACT_ADMISSION_EFFECT,
        }

    def _epoch_count(self, campaign_id: str, policy_status: dict[str, Any]) -> int:
        resets = [
            decision
            for decision in self._decisions(campaign_id)
            if decision["action"] == "reset_epoch_with_reason"
        ]
        reset_at = resets[-1]["created_at"] if resets else ""
        return sum(
            transaction["reassessment"]["created_at"] > reset_at
            for transaction in self._transactions(campaign_id)
        )

    def _repeated_signature(
        self, campaign_id: str, signature: str
    ) -> dict[str, Any] | None:
        for transaction in self._transactions(campaign_id):
            if transaction["reassessment"]["blockage_signature"] == signature:
                return transaction["reassessment"]
        return None

    def blockage_input(self, *, campaign_id: str, blockage_id: str) -> dict[str, Any]:
        """Recover the exact immutable prewrite semantics of a stored blockage."""

        campaign_id = validate_campaign_id(campaign_id)
        blockage_id = _validate_bf_id(blockage_id, "blockage_id")
        for transaction in self._transactions(campaign_id):
            blockage = transaction["blockage"]
            if blockage["blockage_id"] != blockage_id:
                continue
            return {
                key: value
                for key, value in blockage.items()
                if key
                not in {
                    "blockage_id",
                    "created_at",
                    "semantic_sha256",
                    "record_sha256",
                }
            }
        raise KeyError(f"unknown Brave Future blockage: {blockage_id}")

    def _prepare_reassessment(
        self,
        *,
        campaign_id: str,
        blockage_input: dict[str, Any],
    ) -> dict[str, Any]:
        status = self.policy_store.status(campaign_id)
        if not status["enabled"]:
            raise ValueError("Brave Future is disabled for the explicit Campaign")
        snapshot = self.snapshot_builder.preview(
            campaign_id=campaign_id, policy_status=status
        )
        blockage_semantic = self.blockage_validator.validate(
            blockage_input, snapshot=snapshot
        )
        signature = self.blockage_validator.signature(
            blockage_semantic, snapshot=snapshot
        )
        repeated = self._repeated_signature(campaign_id, signature)
        if repeated is not None:
            return {
                "parked": True,
                "reason": "identical_blockage_signature_already_consumed",
                "prior_reassessment_id": repeated["reassessment_id"],
                "blockage_signature": signature,
                "recommended_action": "park_and_escalate",
                "write_effect": "none",
                "truth_effect": BF_TRUTH_EFFECT,
                "fact_admission_effect": BF_FACT_ADMISSION_EFFECT,
            }
        if self._epoch_count(campaign_id, status) >= status["policy"][
            "max_reassessments_per_epoch"
        ]:
            return {
                "parked": True,
                "reason": "campaign_epoch_reassessment_budget_exhausted",
                "blockage_signature": signature,
                "recommended_action": "park_and_escalate",
                "write_effect": "none",
                "truth_effect": BF_TRUTH_EFFECT,
                "fact_admission_effect": BF_FACT_ADMISSION_EFFECT,
            }
        projection = self.projector.project(
            snapshot=snapshot,
            view="actionable",
            collapse_repairs=True,
            limit=max(1, snapshot["research_manifest"]["entry_count"]),
        )
        created_at = _now()
        blockage = _sealed_record(
            blockage_semantic,
            id_key="blockage_id",
            prefix="bfb-",
            created_at=created_at,
        )
        manifest, plan = self.planner.reassess(
            snapshot=snapshot,
            projection=projection,
            blockage=blockage_semantic,
            policy=status["policy"],
            blockage_signature=signature,
        )
        semantic = {
            "revision": BF_REASSESSMENT_REVISION,
            "project_id": self.store.project_id(),
            "campaign_id": campaign_id,
            "blockage_id": blockage["blockage_id"],
            "blockage_signature": signature,
            "planning_snapshot_id": snapshot["planning_snapshot_id"],
            "frontier_projection_id": projection["projection_id"],
            "candidate_manifest_id": manifest["candidate_manifest_id"],
            "candidate_manifest_sha256": manifest["record_sha256"],
            "shortlist": plan["shortlist"],
            "omitted_count": plan["omitted_count"],
            "omission_policy": "full_content_addressed_manifest_retained",
            "recommended_action": plan["recommended_action"],
            "autonomy_level": "advisory",
            "cooldown_state": "signature_consumed",
            "created_by": blockage_semantic["created_by"],
            "plan_effect": "none",
            "dispatch_effect": "none",
            "campaign_close_effect": "none",
            "truth_effect": BF_TRUTH_EFFECT,
            "fact_admission_effect": BF_FACT_ADMISSION_EFFECT,
        }
        reassessment = _sealed_record(
            semantic,
            id_key="reassessment_id",
            prefix="bfr-",
            created_at=created_at,
        )
        for label, obj in (
            ("blockage", blockage),
            ("planning snapshot", snapshot),
            ("frontier projection", projection),
            ("candidate manifest", manifest),
            ("reassessment", reassessment),
        ):
            _bounded(obj, f"Brave Future {label}")
        return {
            "parked": False,
            "blockage": blockage,
            "planning_snapshot": snapshot,
            "frontier_projection": projection,
            "candidate_manifest": manifest,
            "reassessment": reassessment,
            "write_effect": "not_yet_persisted",
            "truth_effect": BF_TRUTH_EFFECT,
            "fact_admission_effect": BF_FACT_ADMISSION_EFFECT,
        }

    def _publish_transaction(self, prepared: dict[str, Any]) -> Path:
        reassessment = prepared["reassessment"]
        campaign_id = reassessment["campaign_id"]
        reassessment_id = reassessment["reassessment_id"]
        destination = self._transaction_path(campaign_id, reassessment_id)
        if os.path.lexists(destination):
            existing = self._read_transaction(campaign_id, reassessment_id)
            if existing["reassessment"] != reassessment:
                raise ValueError("Brave Future reassessment id collision")
            return destination
        transactions = self._transactions_dir(campaign_id)
        transactions.mkdir(parents=True, exist_ok=True)
        staging_root = self._campaign_root(campaign_id) / ".staging"
        staging_root.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix="transaction-", dir=staging_root))
        objects = {
            "blockage.json": prepared["blockage"],
            "planning-snapshot.json": prepared["planning_snapshot"],
            "frontier-projection.json": prepared["frontier_projection"],
            "candidate-manifest.json": prepared["candidate_manifest"],
            "reassessment.json": reassessment,
        }
        try:
            for filename, payload in objects.items():
                (stage / filename).write_bytes(_canonical_file_bytes(payload))
            manifest = {
                "revision": "chalxius-bf-atomic-transaction-1",
                "campaign_id": campaign_id,
                "reassessment_id": reassessment_id,
                "objects": [
                    {
                        "filename": filename,
                        "sha256": sha256_bytes((stage / filename).read_bytes()),
                    }
                    for filename in sorted(objects)
                ],
                "truth_effect": BF_TRUTH_EFFECT,
                "fact_admission_effect": BF_FACT_ADMISSION_EFFECT,
            }
            (stage / "transaction-manifest.json").write_bytes(
                _canonical_file_bytes(manifest)
            )
            for path in stage.iterdir():
                with path.open("rb") as handle:
                    os.fsync(handle.fileno())
            os.replace(stage, destination)
            directory_fd = os.open(transactions, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
            try:
                staging_root.rmdir()
            except OSError:
                # Another in-flight staging directory is not part of this
                # transaction and must never be removed here.
                pass
        except BaseException:
            if stage.exists():
                shutil.rmtree(stage)
            raise
        return destination

    def reassess(
        self,
        *,
        campaign_id: str,
        blockage_input: dict[str, Any],
        dry_run: bool,
    ) -> dict[str, Any]:
        campaign_id = validate_campaign_id(campaign_id)
        if dry_run:
            result = self._prepare_reassessment(
                campaign_id=campaign_id, blockage_input=blockage_input
            )
            return {**result, "dry_run": True, "write_effect": "none"}
        with self.store.v5_mutation_lock(command="campaign-reassess"):
            prepared = self._prepare_reassessment(
                campaign_id=campaign_id, blockage_input=blockage_input
            )
            if prepared["parked"]:
                return {**prepared, "dry_run": False}
            # Recheck all heads while holding the V5 project mutation lock.
            status = self.policy_store.status(campaign_id)
            if not self.snapshot_builder.revalidate(
                prepared["planning_snapshot"], status
            ):
                raise ValueError("Brave Future planning heads drifted before publish")
            destination = self._publish_transaction(prepared)
        return {
            **prepared["reassessment"],
            "transaction_relpath": destination.relative_to(self.store.root).as_posix(),
            "dry_run": False,
            "write_effect": "one_atomic_sidecar_transaction",
        }

    def _find_reassessment(
        self, reassessment_id: str
    ) -> tuple[str, dict[str, dict[str, Any]]]:
        reassessment_id = _validate_bf_id(reassessment_id, "reassessment_id")
        campaigns_root = self.root / "campaigns"
        if not campaigns_root.exists():
            raise KeyError(f"unknown Brave Future reassessment: {reassessment_id}")
        matches: list[tuple[str, dict[str, dict[str, Any]]]] = []
        for campaign_dir in sorted(campaigns_root.iterdir()):
            if not campaign_dir.is_dir() or campaign_dir.is_symlink():
                continue
            try:
                campaign_id = validate_campaign_id(campaign_dir.name)
            except ValueError:
                continue
            path = self._transaction_path(campaign_id, reassessment_id)
            if path.is_dir() and not path.is_symlink():
                matches.append((campaign_id, self._read_transaction(campaign_id, reassessment_id)))
        if len(matches) != 1:
            raise KeyError(f"unknown or ambiguous Brave Future reassessment: {reassessment_id}")
        return matches[0]

    def decide(
        self,
        reassessment_id: str,
        *,
        decision: dict[str, Any],
        actor: str,
    ) -> dict[str, Any]:
        campaign_id, transaction = self._find_reassessment(reassessment_id)
        actor = _text(actor, "Brave Future decision actor")
        fields = {
            "revision",
            "action",
            "selected_research_ids",
            "modified_proposal",
            "reason",
        }
        value = _exact(decision, fields, "Brave Future decision input")
        if value.get("revision") != BF_DECISION_REVISION:
            raise ValueError("Brave Future decision revision is invalid")
        action = value.get("action")
        if action not in {
            "select",
            "select_modified",
            "park",
            "reject_reassessment",
            "reset_epoch_with_reason",
        }:
            raise ValueError("Brave Future decision action is invalid")
        selected = _strings(
            value.get("selected_research_ids"), "Brave Future selected Research ids"
        )
        shortlist_ids = {
            item["research_id"] for item in transaction["reassessment"]["shortlist"]
        }
        if action == "select":
            if len(selected) != 1 or selected[0] not in shortlist_ids:
                raise ValueError("select must name exactly one frozen shortlist Research id")
            if value.get("modified_proposal") is not None:
                raise ValueError("select cannot carry a modified proposal")
        elif action == "select_modified":
            if len(selected) != 1 or not isinstance(value.get("modified_proposal"), dict):
                raise ValueError("select_modified requires one id and one proposal object")
            record = self.store.v5_lifecycle()._research_record(selected[0])
            if record.get("metadata", {}).get("campaign_id") != campaign_id:
                raise ValueError("modified selection crosses Campaigns")
        else:
            if selected or value.get("modified_proposal") is not None:
                raise ValueError(f"{action} cannot select Research")
        reason = _text(value.get("reason"), "Brave Future decision reason")
        if action in {"select", "select_modified"}:
            policy = self.policy_store.status(campaign_id)
            if not policy["enabled"]:
                raise ValueError("cannot select from a disabled Brave Future Campaign")
            if not self.snapshot_builder.revalidate(
                transaction["planning-snapshot"], policy
            ):
                raise ValueError("Brave Future reassessment is stale for selection")
        semantic = {
            "revision": BF_DECISION_REVISION,
            "project_id": self.store.project_id(),
            "campaign_id": campaign_id,
            "reassessment_id": reassessment_id,
            "action": action,
            "selected_research_ids": selected,
            "modified_proposal": value["modified_proposal"],
            "reason": reason,
            "actor": actor,
            "plan_effect": "none",
            "dispatch_effect": "none",
            "campaign_close_effect": "none",
            "truth_effect": BF_TRUTH_EFFECT,
            "fact_admission_effect": BF_FACT_ADMISSION_EFFECT,
        }
        record = _sealed_record(
            semantic,
            id_key="decision_id",
            prefix="bfd-",
            created_at=_now(),
        )
        with self.store.v5_mutation_lock(command="campaign-reassess-decide"):
            existing = self._decisions(campaign_id)
            prior = [
                item for item in existing if item["reassessment_id"] == reassessment_id
            ]
            if prior:
                if prior[-1]["semantic_sha256"] != record["semantic_sha256"]:
                    raise ValueError("Brave Future reassessment already has another decision")
                return {**prior[-1], "write_effect": "none", "idempotent": True}
            path = self._decisions_path(campaign_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = b"".join(
                canonical_json_bytes(item) + b"\n" for item in [*existing, record]
            )
            self.store._write_bytes_atomic(path, payload)
        return {**record, "write_effect": "one_advisory_decision_event"}

    def audit(self) -> dict[str, Any]:
        errors: list[str] = []
        warnings: list[str] = []
        campaigns = 0
        transactions = 0
        decisions = 0
        try:
            self.policy_store._events()
        except Exception as exc:
            errors.append(f"activation ledger: {exc}")
        campaigns_root = self.root / "campaigns"
        if campaigns_root.exists():
            if campaigns_root.is_symlink() or not campaigns_root.is_dir():
                errors.append("campaign sidecar root is unsafe")
            else:
                for campaign_dir in sorted(campaigns_root.iterdir()):
                    if campaign_dir.name.startswith("."):
                        warnings.append(f"ignored incomplete staging root: {campaign_dir.name}")
                        continue
                    try:
                        campaign_id = validate_campaign_id(campaign_dir.name)
                        campaigns += 1
                        transactions += len(self._transactions(campaign_id))
                        decisions += len(self._decisions(campaign_id))
                    except Exception as exc:
                        errors.append(f"campaign sidecar {campaign_dir.name}: {exc}")
        forbidden = {
            "ACTIVE",
            "queue",
            "dispatch",
            "facts",
            "fact_graph",
            "certification",
            "candidate_releases",
        }
        if self.root.exists():
            for path in self.root.rglob("*"):
                if path.name in forbidden:
                    errors.append(
                        "forbidden authority or automation path in Brave Future sidecar: "
                        + path.relative_to(self.root).as_posix()
                    )
        return {
            "revision": "chalxius-bf-audit-1",
            "ok": not errors,
            "errors": errors,
            "warnings": warnings,
            "campaigns": campaigns,
            "transactions": transactions,
            "decisions": decisions,
            "truth_effect": BF_TRUTH_EFFECT,
            "fact_admission_effect": BF_FACT_ADMISSION_EFFECT,
            "stable_v5_audit_effect": "none",
        }

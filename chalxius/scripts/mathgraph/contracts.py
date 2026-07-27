from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any


FACT_ID_RE = re.compile(r"[0-9a-f]{16}")
MEMORY_ID_RE = re.compile(r"[0-9a-f]{12}")
REVIEW_ID_RE = re.compile(r"[0-9a-f]{64}")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
ROUND_ID_RE = re.compile(r"round-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}")
ASSIGNMENT_ID_RE = re.compile(
    r"a[0-9]{2}-[0-9a-f]{12}-(prove|refute|compute|literature|interpret)"
)
CLAIM_ID_RE = re.compile(r"claim-[0-9a-f]{16}")
CONVENTION_ID_RE = re.compile(r"conv-[0-9a-f]{16}")
CAMPAIGN_ID_RE = re.compile(r"campaign-[0-9a-f]{12}")
HOST_TASK_SCOPE_ID_RE = re.compile(r"hosttask-[0-9a-f]{32}")
CAMPAIGN_TARGET_ID_RE = re.compile(r"camtarget-[0-9a-f]{16}")
OBJECT_ID_RE = re.compile(r"object-[0-9a-f]{16}")
EXPERIMENT_ID_RE = re.compile(r"experiment-[0-9a-f]{16}")
BUNDLE_ID_RE = re.compile(r"bundle-[0-9a-f]{64}")
FACT_BUNDLE_ID_RE = re.compile(r"factbundle-[0-9a-f]{64}")
BB_NODE_ID_RE = re.compile(r"bbn-[0-9a-f]{64}")
BB_EDGE_ID_RE = re.compile(r"bbe-[0-9a-f]{64}")
BB_SNAPSHOT_ID_RE = re.compile(r"bbs-[0-9a-f]{64}")

POLICY_REVISION_V4 = "mathgraph-0.3.0"
WORK_MODES = ("prove", "refute", "compute", "literature", "interpret")

MEMORY_KINDS = {
    "conjecture",
    "example",
    "counterexample",
    "proof_attempt",
    "plan",
    "dead_end",
    "direction",
    "obstacle",
    "literature",
    "computation",
    "guidance",
}

ACTIVE_MEMORY_STATUSES = {"open", "supported", "challenged", "verifying"}
TERMINAL_MEMORY_STATUSES = {
    "resolved_by_fact",
    "replaced_by_fact",
    "resolved_by_evidence",
    "resolved_no_obstruction",
    "refuted_by_fact",
    "dead_end",
    "blocked",
}
MEMORY_STATUSES = ACTIVE_MEMORY_STATUSES | TERMINAL_MEMORY_STATUSES

SUBMISSION_STATUSES = {"pending_review", "rejected", "accepted", "revoked"}

CLAIM_RELATIONS = {
    "proves",
    "refutes",
    "strengthens",
    "weakens",
    "replaces",
    "unrelated",
}

NOVELTY_STATUSES = {
    "known",
    "likely_known",
    "no_exact_match_found",
    "unsearched",
}


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def sha256_json(payload: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def validate_identifier(value: str, pattern: re.Pattern[str], label: str) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ValueError(f"invalid {label}: {value!r}")
    return value


def validate_fact_id(value: str) -> str:
    return validate_identifier(value, FACT_ID_RE, "fact id")


def validate_memory_id(value: str) -> str:
    return validate_identifier(value, MEMORY_ID_RE, "memory id")


def validate_review_id(value: str) -> str:
    return validate_identifier(value, REVIEW_ID_RE, "review id")


def validate_round_id(value: str) -> str:
    return validate_identifier(value, ROUND_ID_RE, "round id")


def validate_assignment_id(value: str) -> str:
    return validate_identifier(value, ASSIGNMENT_ID_RE, "assignment id")


def validate_claim_id(value: str) -> str:
    return validate_identifier(value, CLAIM_ID_RE, "claim id")


def validate_convention_id(value: str) -> str:
    return validate_identifier(value, CONVENTION_ID_RE, "convention id")


def validate_campaign_id(value: str) -> str:
    return validate_identifier(value, CAMPAIGN_ID_RE, "campaign id")


def validate_campaign_target_id(value: str) -> str:
    return validate_identifier(value, CAMPAIGN_TARGET_ID_RE, "campaign target id")


def validate_object_id(value: str) -> str:
    return validate_identifier(value, OBJECT_ID_RE, "object id")


def validate_experiment_id(value: str) -> str:
    return validate_identifier(value, EXPERIMENT_ID_RE, "experiment id")


def validate_bundle_id(value: str) -> str:
    return validate_identifier(value, BUNDLE_ID_RE, "verification bundle id")


def validate_fact_bundle_id(value: str) -> str:
    return validate_identifier(value, FACT_BUNDLE_ID_RE, "fact bundle id")


def validate_bb_node_id(value: str) -> str:
    return validate_identifier(value, BB_NODE_ID_RE, "blackboard node id")


def validate_bb_edge_id(value: str) -> str:
    return validate_identifier(value, BB_EDGE_ID_RE, "blackboard edge id")


def validate_bb_snapshot_id(value: str) -> str:
    return validate_identifier(value, BB_SNAPSHOT_ID_RE, "blackboard snapshot id")


def require_string(
    payload: dict[str, Any],
    key: str,
    *,
    allow_empty: bool = False,
) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    if not allow_empty and not value.strip():
        raise ValueError(f"{key} must be nonempty")
    return value


def require_string_list(payload: dict[str, Any], key: str) -> list[str]:
    value = payload.get(key)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{key} must be a list of strings")
    return list(value)


def require_relative_path(value: str, label: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a nonempty relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise ValueError(f"unsafe {label}: {value!r}")
    return path


def contained_path(root: Path, relative: str, label: str) -> Path:
    rel = require_relative_path(relative, label)
    resolved_root = root.resolve()
    resolved = (resolved_root / Path(*rel.parts)).resolve()
    if not resolved.is_relative_to(resolved_root):
        raise ValueError(f"{label} escapes its root: {relative!r}")
    return resolved


def require_exact_keys(
    payload: dict[str, Any],
    *,
    required: set[str],
    optional: set[str] | None = None,
    label: str,
) -> None:
    optional = optional or set()
    missing = required.difference(payload)
    unknown = set(payload).difference(required | optional)
    if missing:
        raise ValueError(f"{label} is missing fields: {', '.join(sorted(missing))}")
    if unknown:
        raise ValueError(f"{label} has unknown fields: {', '.join(sorted(unknown))}")

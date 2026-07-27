from __future__ import annotations

from typing import Any

from .adoption import feature_required, validate_adoption_binding
from .modes import validate_mode_binding_fields
from .contracts import (
    ASSIGNMENT_ID_RE,
    BB_NODE_ID_RE,
    BB_SNAPSHOT_ID_RE,
    CAMPAIGN_ID_RE,
    CLAIM_ID_RE,
    CLAIM_RELATIONS,
    CONVENTION_ID_RE,
    FACT_ID_RE,
    HOST_TASK_SCOPE_ID_RE,
    MEMORY_ID_RE,
    POLICY_REVISION_V4,
    ROUND_ID_RE,
    SHA256_RE,
    WORK_MODES,
    canonical_json_bytes,
    require_exact_keys,
    require_relative_path,
    require_string,
    sha256_json,
    validate_assignment_id,
    validate_fact_bundle_id,
    validate_round_id,
)


PROTOCOL_V4 = "mathgraph-agent-v4"
CONTROL_FOLLOWUP_ACTIONS = {
    "clarify",
    "stop",
    "finalize",
    "report-blocker",
}
CONTROL_FOLLOWUP_PAYLOAD_MAX_BYTES = 8 * 1024
OUTCOMES_V4 = {
    "fact_submission",
    "fact_bundle_submission",
    "counterexample",
    "evidence",
    "dead_end",
}
OBLIGATION_STATUSES = {
    "satisfied",
    "refuted",
    "open",
    "blocked",
    "not_applicable",
}
VERIFICATION_MODES = {"closed_packet", "artifact_replay"}
DEFAULT_BUDGETS = {
    "max_artifact_files": 256,
    "max_artifact_bytes_each": 16 * 1024 * 1024,
    "max_artifact_bytes_total": 64 * 1024 * 1024,
    "max_blackboard_nodes_added": 256,
    "max_blackboard_edges_added": 512,
    "max_blackboard_object_bytes_each": 1024 * 1024,
    "max_blackboard_delta_bytes_total": 8 * 1024 * 1024,
    "max_wall_seconds": 0,
}
DEFAULT_HARD_CAPS = {
    "max_experiment_worker_event_count": 131040,
    "max_experiment_event_count_total": 131072,
    "max_experiment_event_bytes_each": 64 * 1024,
    "max_experiment_event_bytes_total": 64 * 1024 * 1024,
    "max_checkpoint_files": 64,
    "max_checkpoint_bytes_each": 64 * 1024 * 1024,
    "max_checkpoint_bytes_total": 256 * 1024 * 1024,
    "max_governance_event_count": 4096,
    "max_governance_event_bytes_each": 64 * 1024,
    "max_governance_event_bytes_total": 16 * 1024 * 1024,
    "max_pulse_control_records": 4096,
    "max_pulse_control_bytes_each": 256 * 1024,
    "max_pulse_control_bytes_total": 16 * 1024 * 1024,
}

_INGESTION_RECEIPT_SEMANTIC_FIELDS = (
    "schema_version",
    "policy_revision",
    "project_id",
    "round_id",
    "assignment_id",
    "assignment_sha256",
    "return_relpath",
    "return_sha256",
    "worker_final_sha256",
    "outcome",
    "artifacts",
    "effect",
    "blackboard_transaction_id",
    "blackboard_node_ids",
    "blackboard_edge_ids",
)

_BUNDLE_FACT_FIELDS = {
    "fact_id",
    "problem_id",
    "author",
    "predecessors",
    "glossary_introduces",
    "external_refs",
    "elementary_uses",
    "predecessor_uses",
    "quantifier_ledger",
    "convention_profile_ids",
    "computational_evidence",
    "terminology",
    "statement",
    "proof",
    "intuition",
}


def _ingestion_receipt_semantic_fields(
    payload: dict[str, Any],
) -> tuple[str, ...]:
    fields = _INGESTION_RECEIPT_SEMANTIC_FIELDS
    if payload.get("outcome") == "fact_bundle_submission":
        fields += ("task_card_sha256",)
    return fields


def seal_ingestion_receipt_v4(payload: dict[str, Any]) -> dict[str, Any]:
    semantic = {
        key: payload[key]
        for key in _ingestion_receipt_semantic_fields(payload)
    }
    return {
        **payload,
        "ingestion_sha256": sha256_json(semantic),
    }


def validate_ingestion_receipt_v4(payload: dict[str, Any]) -> dict[str, Any]:
    for key in _ingestion_receipt_semantic_fields(payload):
        if key not in payload:
            raise ValueError(f"v4 ingestion receipt missing field: {key}")
    if payload.get("schema_version") != 4:
        raise ValueError("v4 ingestion receipt schema_version must be 4")
    if payload.get("policy_revision") != POLICY_REVISION_V4:
        raise ValueError("v4 ingestion receipt policy_revision mismatch")
    if payload.get("status") != "ingested":
        raise ValueError("v4 ingestion receipt is not final")
    if payload.get("return_locked") is not True:
        raise ValueError("v4 ingestion receipt must lock the return")
    require_string(payload, "project_id")
    for key in (
        "assignment_sha256",
        "return_sha256",
        "worker_final_sha256",
        "blackboard_transaction_id",
    ):
        _require_sha256(payload, key)
    validate_round_id(require_string(payload, "round_id"))
    validate_assignment_id(require_string(payload, "assignment_id"))
    require_relative_path(
        require_string(payload, "return_relpath"),
        "return_relpath",
    )
    if not isinstance(payload.get("artifacts"), list):
        raise ValueError("v4 ingestion receipt artifacts must be a list")
    if not isinstance(payload.get("effect"), dict):
        raise ValueError("v4 ingestion receipt effect must be an object")
    if payload.get("outcome") == "fact_bundle_submission":
        _require_sha256(payload, "task_card_sha256")
        effect = payload["effect"]
        require_exact_keys(
            effect,
            required={"fact_bundle_id", "status"},
            label="fact-bundle ingestion effect",
        )
        validate_fact_bundle_id(
            require_string(effect, "fact_bundle_id")
        )
        if effect.get("status") != "pending_bundle_review":
            raise ValueError(
                "fact-bundle ingestion effect status must be "
                "'pending_bundle_review'"
            )
    for key in ("blackboard_node_ids", "blackboard_edge_ids"):
        value = payload.get(key)
        if not isinstance(value, list) or any(
            not isinstance(item, str) for item in value
        ):
            raise ValueError(f"v4 ingestion receipt {key} must be a string list")
    semantic = {
        key: payload[key]
        for key in _ingestion_receipt_semantic_fields(payload)
    }
    if payload.get("ingestion_sha256") != sha256_json(semantic):
        raise ValueError("v4 ingestion receipt hash mismatch")
    return payload

_TASK_CARD_FIELDS = {
    "schema_version",
    "policy_revision",
    "protocol",
    "project_id",
    "round_id",
    "assignment_id",
    "assignment_sha256",
    "memory_id",
    "worker_id",
    "mode",
    "campaign_id",
    "source_claim_id",
    "goal_relation",
    "goal_statement",
    "rationale_summary",
    "convention_profile_ids",
    "inputs",
    "obligations",
    "verification_plan",
    "adoption_plan",
    "budgets",
    "hard_caps",
    "stop_conditions",
    "blackboard_view",
    "blackboard_snapshot_sha256",
    "return_relpath",
    "artifact_dir_relpath",
    "work_dir_relpath",
}
_TASK_CARD_CAMPAIGN_SNAPSHOT_FIELDS = {
    "campaign_snapshot_relpath",
    "campaign_snapshot_sha256",
}
_TASK_CARD_UNIFIED_MODE_FIELDS = {
    "reasoning_mode",
    "reasoning_mode_event_id",
    "reasoning_mode_policy_sha256",
    "fact_admission_contract_sha256",
    "execution_profile",
}

_RETURN_COMMON_FIELDS = {
    "schema_version",
    "policy_revision",
    "protocol",
    "project_id",
    "round_id",
    "assignment_id",
    "assignment_sha256",
    "task_card_sha256",
    "blackboard_snapshot_sha256",
    "worker",
    "memory_id",
    "mode",
    "outcome",
    "obligation_ledger",
    "blackboard_graph_delta",
    "narrative_summary",
}

_FACT_RETURN_FIELDS = {
    "claim_relation",
    "statement",
    "proof",
    "predecessors",
    "predecessor_uses",
    "quantifier_ledger",
    "convention_profile_ids",
    "computational_evidence",
    "terminology",
    "glossary_introduces",
    "external_refs",
    "elementary_uses",
    "intuition",
    "artifacts",
}

_FACT_BUNDLE_RETURN_FIELDS = {
    "bundle_claim",
    "facts",
    "artifacts",
}


def _require_sha256(payload: dict[str, Any], key: str) -> str:
    value = require_string(payload, key)
    if SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{key} must be 64 lowercase hex characters")
    return value


def _require_id_or_none(
    payload: dict[str, Any],
    key: str,
    pattern: Any,
) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ValueError(f"{key} has an invalid identifier")
    return value


def _require_string_list(payload: dict[str, Any], key: str) -> list[str]:
    value = payload.get(key)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{key} must be a list of strings")
    return list(value)


def _require_object_list(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = payload.get(key)
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{key} must be a list of objects")
    return [dict(item) for item in value]


def _validate_v4_header(payload: dict[str, Any], label: str) -> None:
    if payload.get("schema_version") != 4:
        raise ValueError(f"{label}.schema_version must be 4")
    if payload.get("policy_revision") != POLICY_REVISION_V4:
        raise ValueError(
            f"{label}.policy_revision must be {POLICY_REVISION_V4!r}"
        )
    if payload.get("protocol") != PROTOCOL_V4:
        raise ValueError(f"{label}.protocol must be {PROTOCOL_V4!r}")


def validate_obligations(
    obligations: Any,
    *,
    ledger: bool,
) -> list[dict[str, Any]]:
    if not isinstance(obligations, list):
        raise ValueError("obligations must be a list")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(obligations, 1):
        label = f"{'obligation_ledger' if ledger else 'obligations'}[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{label} must be an object")
        if ledger:
            require_exact_keys(
                item,
                required={"id", "status", "witness_refs", "gap"},
                label=label,
            )
            obligation_id = require_string(item, "id")
            status = require_string(item, "status")
            if status not in OBLIGATION_STATUSES:
                raise ValueError(f"{label}.status is invalid")
            witness_refs = _require_string_list(item, "witness_refs")
            gap = require_string(item, "gap", allow_empty=True)
            if status in {"satisfied", "refuted"} and not witness_refs:
                raise ValueError(f"{label} requires at least one witness")
            if status in {"open", "blocked"} and not gap.strip():
                raise ValueError(f"{label} requires a nonempty gap")
            if status == "not_applicable" and witness_refs:
                raise ValueError(f"{label} cannot have witnesses when not_applicable")
            normalized.append(
                {
                    "id": obligation_id,
                    "status": status,
                    "witness_refs": witness_refs,
                    "gap": gap,
                }
            )
        else:
            require_exact_keys(
                item,
                required={"id", "kind", "statement", "required_evidence"},
                label=label,
            )
            obligation_id = require_string(item, "id")
            normalized.append(
                {
                    "id": obligation_id,
                    "kind": require_string(item, "kind"),
                    "statement": require_string(item, "statement"),
                    "required_evidence": _require_string_list(
                        item, "required_evidence"
                    ),
                }
            )
        if obligation_id in seen:
            raise ValueError(f"duplicate obligation id: {obligation_id}")
        seen.add(obligation_id)
    return normalized


def validate_task_card(
    payload: dict[str, Any],
    *,
    allow_legacy_adoption: bool = False,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("task card must be one JSON object")
    required_fields = set(_TASK_CARD_FIELDS)
    optional_fields = set(_TASK_CARD_CAMPAIGN_SNAPSHOT_FIELDS) | set(
        _TASK_CARD_UNIFIED_MODE_FIELDS
    )
    if allow_legacy_adoption:
        optional_fields.add("host_task_scope_id")
        required_fields.discard("hard_caps")
        optional_fields.add("hard_caps")
    else:
        required_fields.add("host_task_scope_id")
    require_exact_keys(
        payload,
        required=required_fields,
        optional=optional_fields,
        label="v4 task card",
    )
    _validate_v4_header(payload, "task card")
    require_string(payload, "project_id")
    round_id = require_string(payload, "round_id")
    assignment_id = require_string(payload, "assignment_id")
    memory_id = require_string(payload, "memory_id")
    worker_id = require_string(payload, "worker_id")
    if ROUND_ID_RE.fullmatch(round_id) is None:
        raise ValueError("task card round_id is invalid")
    if ASSIGNMENT_ID_RE.fullmatch(assignment_id) is None:
        raise ValueError("task card assignment_id is invalid")
    if worker_id != assignment_id:
        raise ValueError("task card worker_id must equal assignment_id")
    if MEMORY_ID_RE.fullmatch(memory_id) is None:
        raise ValueError("task card memory_id is invalid")
    _require_sha256(payload, "assignment_sha256")
    mode = require_string(payload, "mode")
    if mode not in WORK_MODES:
        raise ValueError("task card mode is invalid")
    campaign_id = require_string(payload, "campaign_id")
    if CAMPAIGN_ID_RE.fullmatch(campaign_id) is None:
        raise ValueError("task card campaign_id is invalid")
    host_task_scope_id = payload.get("host_task_scope_id")
    if host_task_scope_id is not None and (
        not isinstance(host_task_scope_id, str)
        or HOST_TASK_SCOPE_ID_RE.fullmatch(host_task_scope_id) is None
    ):
        raise ValueError("task card host_task_scope_id is invalid")
    campaign_snapshot_fields = _TASK_CARD_CAMPAIGN_SNAPSHOT_FIELDS.intersection(
        payload
    )
    if campaign_snapshot_fields and (
        campaign_snapshot_fields != _TASK_CARD_CAMPAIGN_SNAPSHOT_FIELDS
    ):
        raise ValueError(
            "task card campaign snapshot path and hash must appear together"
        )
    if campaign_snapshot_fields:
        require_relative_path(
            require_string(payload, "campaign_snapshot_relpath"),
            "task card campaign_snapshot_relpath",
        )
        _require_sha256(payload, "campaign_snapshot_sha256")
    source_claim_id = _require_id_or_none(
        payload, "source_claim_id", CLAIM_ID_RE
    )
    relation = require_string(payload, "goal_relation")
    if relation not in CLAIM_RELATIONS:
        raise ValueError("task card goal_relation is invalid")
    require_string(payload, "goal_statement")
    rationale = require_string(payload, "rationale_summary", allow_empty=True)
    if len(rationale) > 2000:
        raise ValueError("task card rationale_summary exceeds 2,000 code points")

    convention_ids = _require_string_list(payload, "convention_profile_ids")
    if len(convention_ids) != len(set(convention_ids)):
        raise ValueError("task card convention_profile_ids must be unique")
    for convention_id in convention_ids:
        if CONVENTION_ID_RE.fullmatch(convention_id) is None:
            raise ValueError("task card has an invalid convention profile id")

    inputs = _require_object_list(payload, "inputs")
    for index, item in enumerate(inputs, 1):
        require_exact_keys(
            item,
            required={"fact_id", "clauses", "required_hypotheses"},
            label=f"task card inputs[{index}]",
        )
        if FACT_ID_RE.fullmatch(require_string(item, "fact_id")) is None:
            raise ValueError(f"task card inputs[{index}].fact_id is invalid")
        clauses = _require_string_list(item, "clauses")
        if not clauses:
            raise ValueError(f"task card inputs[{index}].clauses must be nonempty")
        _require_string_list(item, "required_hypotheses")
    validate_obligations(payload["obligations"], ledger=False)

    plan = payload.get("verification_plan")
    if not isinstance(plan, dict):
        raise ValueError("task card verification_plan must be an object")
    require_exact_keys(
        plan,
        required={"mode", "authorized_artifact_roles", "required_checks"},
        label="task card verification_plan",
    )
    if require_string(plan, "mode") not in VERIFICATION_MODES:
        raise ValueError("task card verification_plan.mode is invalid")
    _require_string_list(plan, "authorized_artifact_roles")
    _require_string_list(plan, "required_checks")
    adoption_plan = validate_adoption_binding(
        payload.get("adoption_plan"),
        allow_legacy_estimate_policy=allow_legacy_adoption,
    )
    if (
        feature_required(
            adoption_plan,
            "artifact_replay",
            allow_legacy_estimate_policy=allow_legacy_adoption,
        )
        and plan["mode"] != "artifact_replay"
    ):
        raise ValueError(
            "task card workload requires artifact_replay verification"
        )
    if (
        feature_required(
            adoption_plan,
            "source_claim_gate",
            allow_legacy_estimate_policy=allow_legacy_adoption,
        )
        and source_claim_id is None
    ):
        raise ValueError(
            "task card source_claim_gate requires source_claim_id"
        )
    if (
        feature_required(
            adoption_plan,
            "convention_gate",
            allow_legacy_estimate_policy=allow_legacy_adoption,
        )
        and not convention_ids
    ):
        raise ValueError(
            "task card convention_gate requires convention_profile_ids"
        )
    validate_mode_binding_fields(
        payload,
        adoption_binding=adoption_plan,
        allow_legacy_adoption=allow_legacy_adoption,
    )

    budgets = payload.get("budgets")
    if not isinstance(budgets, dict):
        raise ValueError("task card budgets must be an object")
    require_exact_keys(
        budgets,
        required=set(DEFAULT_BUDGETS),
        label="task card budgets",
    )
    for key in DEFAULT_BUDGETS:
        value = budgets.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"task card budgets.{key} must be a nonnegative integer")
    if budgets["max_wall_seconds"] != 0:
        raise ValueError(
            "task card budgets.max_wall_seconds must be exactly 0"
        )
    if any(
        budgets[key] == 0
        for key in DEFAULT_BUDGETS
        if key != "max_wall_seconds"
    ):
        raise ValueError("task card object and artifact budgets must be positive")

    hard_caps = payload.get("hard_caps")
    if hard_caps is not None:
        if not isinstance(hard_caps, dict):
            raise ValueError("task card hard_caps must be an object")
        require_exact_keys(
            hard_caps,
            required=set(DEFAULT_HARD_CAPS),
            label="task card hard_caps",
        )
        for key in DEFAULT_HARD_CAPS:
            value = hard_caps.get(key)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(
                    f"task card hard_caps.{key} must be a positive integer"
                )
        if (
            hard_caps["max_experiment_worker_event_count"]
            >= hard_caps["max_experiment_event_count_total"]
        ):
            raise ValueError(
                "task card hard_caps must reserve experiment control-event capacity"
            )

    _require_string_list(payload, "stop_conditions")
    view = payload.get("blackboard_view")
    if not isinstance(view, dict):
        raise ValueError("task card blackboard_view must be an object")
    require_exact_keys(
        view,
        required={
            "snapshot_id",
            "seed_node_ids",
            "read_space_ids",
            "write_space_ids",
            "cross_space_endpoint_node_ids",
            "allow_create_space",
            "query_sha256",
        },
        label="task card blackboard_view",
    )
    snapshot_id = require_string(view, "snapshot_id")
    if BB_SNAPSHOT_ID_RE.fullmatch(snapshot_id) is None:
        raise ValueError("task card snapshot_id is invalid")
    for key in (
        "seed_node_ids",
        "read_space_ids",
        "write_space_ids",
        "cross_space_endpoint_node_ids",
    ):
        for node_id in _require_string_list(view, key):
            if BB_NODE_ID_RE.fullmatch(node_id) is None:
                raise ValueError(f"task card blackboard_view.{key} has an invalid node id")
    if not isinstance(view.get("allow_create_space"), bool):
        raise ValueError("task card allow_create_space must be boolean")
    _require_sha256(view, "query_sha256")
    _require_sha256(payload, "blackboard_snapshot_sha256")
    for key in ("return_relpath", "artifact_dir_relpath", "work_dir_relpath"):
        require_relative_path(require_string(payload, key), f"task card {key}")
    return payload


def _validate_return_convention_binding(
    convention_ids: list[str],
    *,
    task_card: dict[str, Any],
    label: str,
    allow_legacy_adoption: bool,
) -> None:
    if len(convention_ids) != len(set(convention_ids)):
        raise ValueError(f"{label} convention_profile_ids must be unique")
    for convention_id in convention_ids:
        if CONVENTION_ID_RE.fullmatch(convention_id) is None:
            raise ValueError(
                f"{label} has an invalid convention profile id"
            )
    allowed = set(task_card["convention_profile_ids"])
    actual = set(convention_ids)
    if not actual.issubset(allowed):
        raise ValueError(
            f"{label} convention profile is not bound by the task card"
        )
    if (
        feature_required(
            task_card["adoption_plan"],
            "convention_gate",
            allow_legacy_estimate_policy=allow_legacy_adoption,
        )
        and actual != allowed
    ):
        raise ValueError(
            f"{label} convention profile does not exactly match the "
            "convention-sensitive task card"
        )


def validate_worker_return_v4(
    payload: dict[str, Any],
    *,
    task_card: dict[str, Any],
    allow_legacy_adoption: bool = False,
) -> str:
    validate_task_card(
        task_card,
        allow_legacy_adoption=allow_legacy_adoption,
    )
    if not isinstance(payload, dict):
        raise ValueError("worker return must be one JSON object")
    outcome = payload.get("outcome")
    if outcome not in OUTCOMES_V4:
        raise ValueError(f"unsupported v4 worker outcome: {outcome!r}")
    required = set(_RETURN_COMMON_FIELDS)
    optional: set[str] = set()
    if outcome == "fact_submission":
        required |= _FACT_RETURN_FIELDS
    elif outcome == "fact_bundle_submission":
        required |= _FACT_BUNDLE_RETURN_FIELDS
    elif outcome == "counterexample":
        required |= {"claim", "construction", "verification", "artifacts"}
    elif outcome == "evidence":
        required |= {
            "claim",
            "method",
            "result",
            "artifacts",
            "limitations",
        }
    else:
        required |= {
            "claim",
            "method",
            "failure_mode",
            "what_remains_open",
            "artifacts",
        }
    require_exact_keys(
        payload,
        required=required,
        optional=optional,
        label=f"v4 {outcome} return",
    )
    _validate_v4_header(payload, "worker return")
    for key, expected in (
        ("project_id", task_card["project_id"]),
        ("round_id", task_card["round_id"]),
        ("assignment_id", task_card["assignment_id"]),
        ("assignment_sha256", task_card["assignment_sha256"]),
        ("worker", task_card["worker_id"]),
        ("memory_id", task_card["memory_id"]),
        ("mode", task_card["mode"]),
        (
            "blackboard_snapshot_sha256",
            task_card["blackboard_snapshot_sha256"],
        ),
    ):
        if require_string(payload, key) != expected:
            raise ValueError(f"worker return {key} mismatch")
    _require_sha256(payload, "task_card_sha256")
    validate_obligations(payload["obligation_ledger"], ledger=True)
    narrative = require_string(payload, "narrative_summary", allow_empty=True)
    if len(narrative) > 4000:
        raise ValueError("worker return narrative_summary exceeds 4,000 code points")
    delta = payload.get("blackboard_graph_delta")
    if not isinstance(delta, dict):
        raise ValueError("worker return blackboard_graph_delta must be an object")
    require_exact_keys(
        delta,
        required={"base_snapshot_id", "add_nodes", "add_edges"},
        label="blackboard_graph_delta",
    )
    if delta.get("base_snapshot_id") != task_card["blackboard_view"]["snapshot_id"]:
        raise ValueError("worker return base snapshot mismatch")
    _require_object_list(delta, "add_nodes")
    _require_object_list(delta, "add_edges")

    if outcome == "fact_submission":
        if feature_required(
            task_card["adoption_plan"],
            "atomic_fact_bundle",
            allow_legacy_estimate_policy=allow_legacy_adoption,
        ):
            raise ValueError(
                "task card requires atomic fact-bundle handling; "
                "a single fact_submission is forbidden"
            )
        relation = require_string(payload, "claim_relation")
        if relation not in CLAIM_RELATIONS:
            raise ValueError("worker return claim_relation is invalid")
        for key in ("statement", "proof"):
            require_string(payload, key)
        for key in ("predecessors", "convention_profile_ids"):
            _require_string_list(payload, key)
        _validate_return_convention_binding(
            payload["convention_profile_ids"],
            task_card=task_card,
            label="fact_submission",
            allow_legacy_adoption=allow_legacy_adoption,
        )
        for key in (
            "predecessor_uses",
            "quantifier_ledger",
            "computational_evidence",
            "terminology",
            "external_refs",
            "elementary_uses",
            "artifacts",
        ):
            _require_object_list(payload, key)
        glossary = payload.get("glossary_introduces")
        if not isinstance(glossary, dict) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in glossary.items()
        ):
            raise ValueError("glossary_introduces must map strings to strings")
        require_string(payload, "intuition", allow_empty=True)
    elif outcome == "fact_bundle_submission":
        if not feature_required(
            task_card["adoption_plan"],
            "atomic_fact_bundle",
            allow_legacy_estimate_policy=allow_legacy_adoption,
        ):
            raise ValueError(
                "fact_bundle_submission is allowed only when "
                "atomic_fact_bundle is required"
            )
        require_string(payload, "bundle_claim")
        facts = _require_object_list(payload, "facts")
        if len(facts) < 2:
            raise ValueError(
                "fact_bundle_submission requires at least two facts"
            )
        for index, fact in enumerate(facts, 1):
            require_exact_keys(
                fact,
                required=_BUNDLE_FACT_FIELDS,
                label=f"fact_bundle_submission facts[{index}]",
            )
            if require_string(fact, "problem_id") != task_card["project_id"]:
                raise ValueError(
                    "fact_bundle_submission fact project mismatch"
                )
            if require_string(fact, "author") != task_card["worker_id"]:
                raise ValueError(
                    "fact_bundle_submission fact author must equal "
                    "the assignment worker"
                )
            convention_ids = _require_string_list(
                fact,
                "convention_profile_ids",
            )
            _validate_return_convention_binding(
                convention_ids,
                task_card=task_card,
                label=f"fact_bundle_submission facts[{index}]",
                allow_legacy_adoption=allow_legacy_adoption,
            )
        _require_object_list(payload, "artifacts")
    else:
        for key in {
            "counterexample": ("claim", "construction", "verification"),
            "evidence": ("claim", "method"),
            "dead_end": ("claim", "method", "failure_mode", "what_remains_open"),
        }[outcome]:
            require_string(payload, key)
        _require_object_list(payload, "artifacts")
    return str(outcome)


def validate_final_handoff(payload: dict[str, Any]) -> dict[str, str]:
    if not isinstance(payload, dict):
        raise ValueError("final handoff must be one JSON object")
    require_exact_keys(
        payload,
        required={"assignment_id", "return_sha256", "status"},
        label="worker final handoff",
    )
    assignment_id = require_string(payload, "assignment_id")
    if ASSIGNMENT_ID_RE.fullmatch(assignment_id) is None:
        raise ValueError("final handoff assignment_id is invalid")
    digest = _require_sha256(payload, "return_sha256")
    if payload.get("status") != "final":
        raise ValueError("final handoff status must be 'final'")
    return {
        "assignment_id": assignment_id,
        "return_sha256": digest,
        "status": "final",
    }


def validate_control_followup(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate one bounded host-to-worker control-plane follow-up."""

    if not isinstance(payload, dict):
        raise ValueError("control follow-up must be one JSON object")
    require_exact_keys(
        payload,
        required={"type", "assignment_id", "action", "payload"},
        label="control follow-up",
    )
    if payload.get("type") != "control":
        raise ValueError("control follow-up type must be 'control'")
    assignment_id = require_string(payload, "assignment_id")
    if ASSIGNMENT_ID_RE.fullmatch(assignment_id) is None:
        raise ValueError("control follow-up assignment_id is invalid")
    action = require_string(payload, "action")
    if action not in CONTROL_FOLLOWUP_ACTIONS:
        raise ValueError("control follow-up action is invalid")
    body = payload.get("payload")
    if not isinstance(body, dict):
        raise ValueError("control follow-up payload must be an object")
    if len(canonical_json_bytes(body)) > CONTROL_FOLLOWUP_PAYLOAD_MAX_BYTES:
        raise ValueError(
            "control follow-up payload exceeds the 8 KiB canonical JSON limit"
        )
    return payload


def compact_worker_prompt(
    *,
    task_card_path: str,
    protocol_reference_path: str,
    mgraph_path: str,
) -> str:
    rendered = (
        "# MathGraph v4 assignment\n\n"
        f"Task card: `{task_card_path}`\n\n"
        f"Protocol reference: `{protocol_reference_path}`\n\n"
        f"MathGraph wrapper: `{mgraph_path}`\n\n"
        "Only admitted fact interfaces in the frozen task card are proof premises. "
        "Blackboard objects, memory, drafts, computations, and votes are not truth.\n\n"
        "Draft below the designated work directory and run `preflight-return --input` "
        "before copying those exact bytes to the designated return. Then run "
        "`validate-return` and hand off exactly `assignment_id`, `return_sha256`, "
        "and `status=\"final\"`.\n"
    )
    if len(rendered.encode("utf-8")) >= 4096:
        raise ValueError("static v4 worker prompt must be smaller than 4 KiB")
    return rendered

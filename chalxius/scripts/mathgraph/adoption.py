from __future__ import annotations

import math
from typing import Any

from .contracts import (
    POLICY_REVISION_V4,
    require_exact_keys,
    require_string,
    sha256_json,
)


ADOPTION_SCHEMA_VERSION = 1
ACTIVITIES = {
    "proof",
    "refutation",
    "computation",
    "literature",
    "interpretation",
    "export",
}
AUDIENCES = {"internal", "expert", "advisor", "publication"}
COMPUTATION_ROLES = {"none", "corroborative", "load_bearing"}
FEATURE_STATUSES = {"required", "available", "not_applicable"}
CORE_COMMUNICATION_PROTOCOL = {
    "control_plane": "required_compact_nontruth",
    "mathematical_state_plane": "required_typed_truth_boundary",
    "narrative_plane": "required_nontruth",
    "same_round_visibility": "frozen_snapshot_only",
}
TRIGGERED_FEATURES = {
    "experiment_checkpoint",
    "artifact_replay",
    "atomic_fact_bundle",
    "terminology_export_lint",
    "source_claim_gate",
    "convention_gate",
    "quantifier_gate",
}


def _require_bool(payload: dict[str, Any], key: str, label: str) -> bool:
    value = payload.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{label}.{key} must be boolean")
    return value


def _require_nonnegative_int(
    payload: dict[str, Any],
    key: str,
    label: str,
) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label}.{key} must be a nonnegative integer")
    return value


def validate_workload_profile(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("workload profile must be one object")
    require_exact_keys(
        payload,
        required={
            "schema_version",
            "policy_revision",
            "activity",
            "audience",
            "computation",
            "fact_output",
            "semantics",
        },
        label="workload profile",
    )
    if payload.get("schema_version") != ADOPTION_SCHEMA_VERSION:
        raise ValueError("workload profile schema_version must be 1")
    if payload.get("policy_revision") != POLICY_REVISION_V4:
        raise ValueError("workload profile policy_revision mismatch")
    activity = require_string(payload, "activity")
    if activity not in ACTIVITIES:
        raise ValueError("workload profile activity is invalid")
    audience = require_string(payload, "audience")
    if audience not in AUDIENCES:
        raise ValueError("workload profile audience is invalid")

    computation = payload.get("computation")
    if not isinstance(computation, dict):
        raise ValueError("workload profile computation must be an object")
    require_exact_keys(
        computation,
        required={
            "role",
            "estimated_wall_seconds",
            "stage_count",
            "resume_required",
        },
        label="workload profile computation",
    )
    role = require_string(computation, "role")
    if role not in COMPUTATION_ROLES:
        raise ValueError("workload profile computation.role is invalid")
    wall_seconds = computation.get("estimated_wall_seconds")
    if wall_seconds is not None and (
        isinstance(wall_seconds, bool)
        or not isinstance(wall_seconds, (int, float))
        or not math.isfinite(float(wall_seconds))
        or float(wall_seconds) < 0
    ):
        raise ValueError(
            "workload profile computation.estimated_wall_seconds must be "
            "null or a nonnegative finite number"
        )
    stage_count = _require_nonnegative_int(
        computation, "stage_count", "workload profile computation"
    )
    resume_required = _require_bool(
        computation, "resume_required", "workload profile computation"
    )
    if role == "none":
        if wall_seconds not in {0, 0.0} or stage_count != 0 or resume_required:
            raise ValueError(
                "non-computational workload must use wall_seconds=0, "
                "stage_count=0, and resume_required=false"
            )
    elif stage_count < 1:
        raise ValueError("computational workload requires at least one stage")

    fact_output = payload.get("fact_output")
    if not isinstance(fact_output, dict):
        raise ValueError("workload profile fact_output must be an object")
    require_exact_keys(
        fact_output,
        required={
            "candidate_count",
            "internal_dependency_count",
            "atomic_visibility_required",
        },
        label="workload profile fact_output",
    )
    candidate_count = _require_nonnegative_int(
        fact_output, "candidate_count", "workload profile fact_output"
    )
    internal_dependency_count = _require_nonnegative_int(
        fact_output,
        "internal_dependency_count",
        "workload profile fact_output",
    )
    atomic_visibility_required = _require_bool(
        fact_output,
        "atomic_visibility_required",
        "workload profile fact_output",
    )
    if candidate_count == 0 and (
        internal_dependency_count or atomic_visibility_required
    ):
        raise ValueError(
            "zero-candidate workload cannot request internal dependencies "
            "or atomic visibility"
        )
    if candidate_count < 2 and internal_dependency_count:
        raise ValueError(
            "internal fact dependencies require at least two candidate facts"
        )

    semantics = payload.get("semantics")
    if not isinstance(semantics, dict):
        raise ValueError("workload profile semantics must be an object")
    require_exact_keys(
        semantics,
        required={
            "source_claim",
            "convention_sensitive",
            "quantifier_sensitive",
            "terminology_sensitive",
        },
        optional={"source_ambiguity"},
        label="workload profile semantics",
    )
    for key in (
        "source_claim",
        "convention_sensitive",
        "quantifier_sensitive",
        "terminology_sensitive",
    ):
        _require_bool(semantics, key, "workload profile semantics")
    if "source_ambiguity" in semantics:
        source_ambiguity = _require_bool(
            semantics,
            "source_ambiguity",
            "workload profile semantics",
        )
        if source_ambiguity and not semantics["source_claim"]:
            raise ValueError(
                "workload profile semantics.source_ambiguity=true requires "
                "source_claim=true"
            )
    # Preserve the optional field exactly.  In particular, do not materialize
    # ``source_ambiguity: false`` while reading a frozen pre-unified V4
    # profile: its canonical bytes and every dependent plan/binding hash must
    # remain unchanged.  Consumers use .get(..., False) for the legacy case.
    normalized_semantics = {
        key: semantics[key]
        for key in (
            "source_claim",
            "convention_sensitive",
            "quantifier_sensitive",
            "terminology_sensitive",
        )
    }
    if "source_ambiguity" in semantics:
        normalized_semantics["source_ambiguity"] = semantics[
            "source_ambiguity"
        ]
    return {
        "schema_version": ADOPTION_SCHEMA_VERSION,
        "policy_revision": POLICY_REVISION_V4,
        "activity": activity,
        "audience": audience,
        "computation": {
            "role": role,
            "estimated_wall_seconds": wall_seconds,
            "stage_count": stage_count,
            "resume_required": resume_required,
        },
        "fact_output": {
            "candidate_count": candidate_count,
            "internal_dependency_count": internal_dependency_count,
            "atomic_visibility_required": atomic_visibility_required,
        },
        "semantics": normalized_semantics,
    }


def default_workload_profile(entry: dict[str, Any]) -> dict[str, Any]:
    plan = entry.get("verification_plan")
    plan = plan if isinstance(plan, dict) else {}
    mode = plan.get("mode", "closed_packet")
    if mode == "artifact_replay":
        role = "load_bearing"
    elif entry.get("kind") == "computation" or "compute" in entry.get(
        "suggested_actions", []
    ):
        role = "corroborative"
    else:
        role = "none"
    budgets = entry.get("budgets")
    budgets = budgets if isinstance(budgets, dict) else {}
    wall_seconds = budgets.get("max_wall_seconds", 0)
    if isinstance(wall_seconds, bool) or not isinstance(wall_seconds, int):
        wall_seconds = 0
    activity = "computation" if role != "none" else "proof"
    return validate_workload_profile(
        {
            "schema_version": ADOPTION_SCHEMA_VERSION,
            "policy_revision": POLICY_REVISION_V4,
            "activity": activity,
            "audience": "internal",
            "computation": {
                "role": role,
                "estimated_wall_seconds": wall_seconds if role != "none" else 0,
                "stage_count": 1 if role != "none" else 0,
                "resume_required": False,
            },
            "fact_output": {
                "candidate_count": 1,
                "internal_dependency_count": 0,
                "atomic_visibility_required": False,
            },
            "semantics": {
                "source_claim": isinstance(entry.get("source_claim_id"), str),
                "convention_sensitive": bool(
                    entry.get("convention_profile_ids", [])
                ),
                "quantifier_sensitive": any(
                    isinstance(item, dict)
                    and item.get("kind") in {"quantifier", "witness"}
                    for item in entry.get("obligations", [])
                ),
                "terminology_sensitive": False,
            },
        }
    )


def workload_profile_for_entry(entry: dict[str, Any]) -> dict[str, Any]:
    supplied = entry.get("workload_profile")
    if supplied is None:
        return default_workload_profile(entry)
    return validate_workload_profile(supplied)


def _decision(required: bool, reason: str, *, applicable: bool = True) -> dict[str, Any]:
    status = "required" if required else (
        "available" if applicable else "not_applicable"
    )
    return {"status": status, "reason": reason}


def build_adoption_plan(profile: dict[str, Any]) -> dict[str, Any]:
    profile = validate_workload_profile(profile)
    computation = profile["computation"]
    fact_output = profile["fact_output"]
    semantics = profile["semantics"]
    is_computation = computation["role"] != "none"
    # Duration estimates are advisory scheduling metadata only.  They must
    # never activate a feature, gate dispatch, or trigger notification.
    experiment_required = is_computation and (
        computation["stage_count"] > 1
        or computation["resume_required"]
    )
    artifact_replay_required = computation["role"] == "load_bearing"
    atomic_bundle_required = fact_output["atomic_visibility_required"] or (
        fact_output["candidate_count"] > 1
        and fact_output["internal_dependency_count"] > 0
    )
    export_lint_required = (
        profile["audience"] != "internal"
        or semantics["terminology_sensitive"]
        or profile["activity"] == "export"
    )
    semantic = {
        "schema_version": ADOPTION_SCHEMA_VERSION,
        "policy_revision": POLICY_REVISION_V4,
        "workload_profile": profile,
        "workload_profile_sha256": sha256_json(profile),
        "communication_protocol": dict(CORE_COMMUNICATION_PROTOCOL),
        "features": {
            "experiment_checkpoint": _decision(
                experiment_required,
                (
                    "multi-stage or resumable computation"
                    if experiment_required
                    else (
                        "single-stage non-resumable computation may use "
                        "frozen artifacts directly; estimates are advisory only"
                        if is_computation
                        else "no computation declared"
                    )
                ),
                applicable=is_computation,
            ),
            "artifact_replay": _decision(
                artifact_replay_required,
                (
                    "load-bearing computation"
                    if artifact_replay_required
                    else "no load-bearing computation declared"
                ),
                applicable=is_computation,
            ),
            "atomic_fact_bundle": _decision(
                atomic_bundle_required,
                (
                    "candidate mini-DAG or explicit all-or-none visibility"
                    if atomic_bundle_required
                    else "independent single-fact admission is sufficient"
                ),
                applicable=fact_output["candidate_count"] > 0,
            ),
            "terminology_export_lint": _decision(
                export_lint_required,
                (
                    "external/expert audience or terminology-sensitive output"
                    if export_lint_required
                    else "internal research output"
                ),
            ),
            "source_claim_gate": _decision(
                semantics["source_claim"],
                (
                    "published or versioned source claim is in scope"
                    if semantics["source_claim"]
                    else "no source claim is bound"
                ),
            ),
            "convention_gate": _decision(
                semantics["convention_sensitive"],
                (
                    "convention-sensitive statement"
                    if semantics["convention_sensitive"]
                    else "no convention-sensitive statement declared"
                ),
            ),
            "quantifier_gate": _decision(
                semantics["quantifier_sensitive"],
                (
                    "quantifier or witness dependency is load-bearing"
                    if semantics["quantifier_sensitive"]
                    else "no nontrivial quantifier dependency declared"
                ),
            ),
        },
        "replan_triggers": [
            "a computation becomes multi-stage or resumable",
            "a computation becomes load-bearing",
            "multiple candidate facts acquire internal dependencies or all-or-none visibility",
            "the output audience changes from internal to expert, advisor, or publication",
            "source-claim, convention, quantifier, or terminology sensitivity is discovered",
        ],
    }
    return {**semantic, "plan_sha256": sha256_json(semantic)}


def _legacy_estimate_gated_adoption_plan(
    profile: dict[str, Any],
) -> dict[str, Any]:
    """Reconstruct the exact pre-advisory-estimate plan for frozen-card replay.

    New planning never calls this path.  It exists only so an already frozen
    dev.5 task card remains verifiable after the policy correction.
    """

    current = build_adoption_plan(profile)
    computation = current["workload_profile"]["computation"]
    is_computation = computation["role"] != "none"
    experiment_required = is_computation and (
        computation["stage_count"] > 1
        or computation["resume_required"]
        or computation["estimated_wall_seconds"] is None
        or computation["estimated_wall_seconds"] > 300
    )
    semantic = {
        key: value
        for key, value in current.items()
        if key != "plan_sha256"
    }
    semantic["features"] = {
        name: dict(decision)
        for name, decision in current["features"].items()
    }
    semantic["features"]["experiment_checkpoint"] = _decision(
        experiment_required,
        (
            "multi-stage, resumable, unknown-duration, or over-300s computation"
            if experiment_required
            else "small single-stage computation may use frozen artifacts directly"
        ),
        applicable=is_computation,
    )
    semantic["replan_triggers"] = [
        "a computation becomes multi-stage, resumable, unknown-duration, or over 300 seconds",
        "a computation becomes load-bearing",
        "multiple candidate facts acquire internal dependencies or all-or-none visibility",
        "the output audience changes from internal to expert, advisor, or publication",
        "source-claim, convention, quantifier, or terminology sensitivity is discovered",
    ]
    return {**semantic, "plan_sha256": sha256_json(semantic)}


def validate_adoption_plan(
    payload: Any,
    *,
    allow_legacy_estimate_policy: bool = False,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("adoption plan must be one object")
    require_exact_keys(
        payload,
        required={
            "schema_version",
            "policy_revision",
            "workload_profile",
            "workload_profile_sha256",
            "communication_protocol",
            "features",
            "replan_triggers",
            "plan_sha256",
        },
        label="adoption plan",
    )
    expected = build_adoption_plan(payload["workload_profile"])
    matches_legacy = False
    if allow_legacy_estimate_policy:
        legacy = _legacy_estimate_gated_adoption_plan(
            payload["workload_profile"]
        )
        matches_legacy = payload == legacy
    if payload != expected and not matches_legacy:
        raise ValueError("adoption plan does not match the deterministic V4 policy")
    features = payload.get("features")
    if not isinstance(features, dict) or set(features) != TRIGGERED_FEATURES:
        raise ValueError("adoption plan feature set is invalid")
    for name, decision in features.items():
        if not isinstance(decision, dict):
            raise ValueError(f"adoption feature {name} must be an object")
        require_exact_keys(
            decision,
            required={"status", "reason"},
            label=f"adoption feature {name}",
        )
        if decision.get("status") not in FEATURE_STATUSES:
            raise ValueError(f"adoption feature {name} status is invalid")
        require_string(decision, "reason")
    return payload


def compact_adoption_binding(
    plan: dict[str, Any],
    *,
    allow_legacy_estimate_policy: bool = False,
) -> dict[str, Any]:
    plan = validate_adoption_plan(
        plan,
        allow_legacy_estimate_policy=allow_legacy_estimate_policy,
    )
    semantic = {
        "schema_version": ADOPTION_SCHEMA_VERSION,
        "policy_revision": POLICY_REVISION_V4,
        "workload_profile": plan["workload_profile"],
        "workload_profile_sha256": plan["workload_profile_sha256"],
        "communication_protocol": plan["communication_protocol"],
        "feature_statuses": {
            name: plan["features"][name]["status"]
            for name in sorted(TRIGGERED_FEATURES)
        },
        "replan_triggers": [
            "computation_scope_change",
            "fact_output_shape_change",
            "audience_or_semantics_change",
        ],
        "plan_sha256": plan["plan_sha256"],
    }
    return {**semantic, "binding_sha256": sha256_json(semantic)}


def validate_adoption_binding(
    payload: Any,
    *,
    allow_legacy_estimate_policy: bool = False,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("adoption binding must be one object")
    require_exact_keys(
        payload,
        required={
            "schema_version",
            "policy_revision",
            "workload_profile",
            "workload_profile_sha256",
            "communication_protocol",
            "feature_statuses",
            "replan_triggers",
            "plan_sha256",
            "binding_sha256",
        },
        label="adoption binding",
    )
    expected = compact_adoption_binding(
        build_adoption_plan(payload["workload_profile"])
    )
    matches_legacy = False
    if allow_legacy_estimate_policy:
        legacy = compact_adoption_binding(
            _legacy_estimate_gated_adoption_plan(
                payload["workload_profile"]
            ),
            allow_legacy_estimate_policy=True,
        )
        matches_legacy = payload == legacy
    if payload != expected and not matches_legacy:
        raise ValueError(
            "adoption binding does not match the deterministic V4 policy"
        )
    return payload


def uses_legacy_estimate_policy(
    plan_or_binding: dict[str, Any],
) -> bool:
    """Identify an exact historical estimate-gated policy object.

    The legacy object may remain readable for provenance and audit, but this
    predicate does not authorize it for any active workflow operation.
    """

    if "feature_statuses" in plan_or_binding:
        validate_adoption_binding(
            plan_or_binding,
            allow_legacy_estimate_policy=True,
        )
        current = compact_adoption_binding(
            build_adoption_plan(plan_or_binding["workload_profile"])
        )
    else:
        validate_adoption_plan(
            plan_or_binding,
            allow_legacy_estimate_policy=True,
        )
        current = build_adoption_plan(
            plan_or_binding["workload_profile"]
        )
    return plan_or_binding != current


def feature_status(
    plan_or_binding: dict[str, Any],
    feature: str,
    *,
    allow_legacy_estimate_policy: bool = False,
) -> str:
    if feature not in TRIGGERED_FEATURES:
        raise ValueError(f"unknown adoption feature: {feature}")
    if "feature_statuses" in plan_or_binding:
        validate_adoption_binding(
            plan_or_binding,
            allow_legacy_estimate_policy=allow_legacy_estimate_policy,
        )
        return str(plan_or_binding["feature_statuses"][feature])
    validate_adoption_plan(
        plan_or_binding,
        allow_legacy_estimate_policy=allow_legacy_estimate_policy,
    )
    return str(plan_or_binding["features"][feature]["status"])


def feature_required(
    plan_or_binding: dict[str, Any],
    feature: str,
    *,
    allow_legacy_estimate_policy: bool = False,
) -> bool:
    return (
        feature_status(
            plan_or_binding,
            feature,
            allow_legacy_estimate_policy=allow_legacy_estimate_policy,
        )
        == "required"
    )

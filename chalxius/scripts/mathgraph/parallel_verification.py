from __future__ import annotations

"""Composable, nontruth verification planning and mechanical aggregation.

The module deliberately has no worker-dispatch primitive and no Fact-writing
primitive.  A plan must exist before a host can mint a packet; reviewer output
is accepted only as a machine receipt bound to that exact plan and slot; the
aggregator performs no semantic inference and can emit only eligibility for a
later Certification Decision.
"""

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Iterable


CONTRACT_REVISION = "chalxius-composable-parallel-verification-1"
OBLIGATION_REGISTER_REVISION = "chalxius-verification-obligation-register-1"
WORK_PLAN_REVISION = "chalxius-verification-work-plan-1"
PACKET_REVISION = "chalxius-verification-packet-1"
RECEIPT_REVISION = "chalxius-verification-machine-receipt-1"
AGGREGATE_REVISION = "chalxius-verification-mechanical-aggregate-1"
CUTOFF_REGISTRY_REVISION = "chalxius-verification-cutoff-registry-1"
TRUST_KEY_REVISION = "chalxius-verification-trusted-key-1"
SIGNED_PLAN_REVISION = "chalxius-verification-signed-work-plan-1"
SAFE_INTEGER = 9_007_199_254_740_991
SHA256_RE = re.compile(r"[0-9a-f]{64}")
ID_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.:-]{0,255}")

SLOT_ROLES = frozenset({"primary", "overlap", "seam", "global", "artifact_access"})
REVIEWER_ROLES = frozenset(
    {
        "semantic_reviewer",
        "source_fidelity_reviewer",
        "paper_binding_reviewer",
        "atomicity_reviewer",
        "interface_transport_reviewer",
        "defeater_reviewer",
        "seam_reviewer",
        "global_invariant_reviewer",
        "artifact_access_reviewer",
    }
)
RECEIPT_STATUSES = frozenset(
    {"supported", "reject", "not_applicable", "needs_adjudication"}
)
TRUST_KEY_ROLES = frozenset({"planner", "host", "reviewer"})
RELATION_KINDS = frozenset(
    {
        "supports_or_depends_on",
        "predecessor_use",
        "defeats_or_challenges",
        "paper_maps_or_binds",
        "evidence_refers_to",
        "artifact_contains_or_authorizes",
        "supersedes_or_revokes",
        "transports_scope_or_object",
    }
)

SUBJECT_CHECK_MATRIX: dict[str, tuple[str, ...]] = {
    "candidate_fact": (
        "semantic_correctness",
        "source_fidelity",
        "paper_binding",
        "atomicity",
        "failure_surface_sufficiency",
        "statement_interface_typing",
    ),
    "candidate_interface": (
        "statement_interface_typing",
        "hypothesis_transport",
        "quantifier_transport",
        "typed_object_transport",
        "temporal_transport",
        "applicability_transport",
        "comparator_transport",
    ),
    "internal_predecessor_use": (
        "edge_entailment",
        "hypothesis_transport",
        "quantifier_transport",
        "typed_object_transport",
        "temporal_transport",
        "applicability_transport",
        "comparator_transport",
    ),
    "external_predecessor_use": (
        "edge_entailment",
        "source_fidelity",
        "revoked_authority_exclusion",
        "applicability_transport",
    ),
    "paper_target": ("paper_binding", "target_and_headline_closure"),
    "challenge_or_defeater": ("defeater_disposition",),
    "assurance_item": ("dag_and_id_invariants",),
    "paper_evidence_ref": (
        "evidence_ref_transport_closure",
        "artifact_reachability",
    ),
    "paper_continuation_item": (
        "paper_binding",
        "target_and_headline_closure",
        "revoked_authority_exclusion",
    ),
    "source_or_query_capability": ("source_fidelity", "artifact_reachability"),
    "artifact": ("artifact_reachability",),
    "atomic_component": ("atomicity", "source_fidelity", "paper_binding"),
    "failure_surface": ("failure_surface_sufficiency",),
    "global_invariant": (
        "dag_and_id_invariants",
        "target_and_headline_closure",
        "revoked_authority_exclusion",
    ),
}

CHECK_REVIEWER_ROLE = {
    "semantic_correctness": "semantic_reviewer",
    "source_fidelity": "source_fidelity_reviewer",
    "paper_binding": "paper_binding_reviewer",
    "atomicity": "atomicity_reviewer",
    "failure_surface_sufficiency": "atomicity_reviewer",
    "statement_interface_typing": "interface_transport_reviewer",
    "hypothesis_transport": "interface_transport_reviewer",
    "quantifier_transport": "interface_transport_reviewer",
    "typed_object_transport": "interface_transport_reviewer",
    "temporal_transport": "interface_transport_reviewer",
    "applicability_transport": "interface_transport_reviewer",
    "comparator_transport": "interface_transport_reviewer",
    "edge_entailment": "seam_reviewer",
    "defeater_disposition": "defeater_reviewer",
    "artifact_reachability": "artifact_access_reviewer",
    "evidence_ref_transport_closure": "artifact_access_reviewer",
    "target_and_headline_closure": "global_invariant_reviewer",
    "revoked_authority_exclusion": "global_invariant_reviewer",
    "dag_and_id_invariants": "global_invariant_reviewer",
}

CHECK_CUTOFF_PROFILE = {
    "semantic_correctness": "semantic_full",
    "source_fidelity": "semantic_full",
    "paper_binding": "semantic_full",
    "atomicity": "semantic_full",
    "failure_surface_sufficiency": "semantic_full",
    "statement_interface_typing": "semantic_full",
    "hypothesis_transport": "seam_full",
    "quantifier_transport": "seam_full",
    "typed_object_transport": "seam_full",
    "temporal_transport": "seam_full",
    "applicability_transport": "seam_full",
    "comparator_transport": "seam_full",
    "edge_entailment": "seam_full",
    "defeater_disposition": "semantic_full",
    "artifact_reachability": "artifact_transport_full",
    "evidence_ref_transport_closure": "artifact_transport_full",
    "target_and_headline_closure": "global_membership",
    "revoked_authority_exclusion": "global_membership",
    "dag_and_id_invariants": "global_membership",
}

CUTOFF_PROFILES = {
    "semantic_full": {
        "allowed_terminal_kinds": [
            "exact_source_span_with_bytes",
            "external_evidence_leaf_with_authorized_bytes",
            "gateway_admitted_fact_with_complete_marker_and_nonrevocation_witness",
        ],
        "forbidden_cutoffs": [
            "cross_shard_boundary",
            "context_budget",
            "producer_summary",
            "untransported_evidence_ref",
        ],
    },
    "seam_full": {
        "allowed_terminal_kinds": [
            "exact_source_span_with_bytes",
            "external_evidence_leaf_with_authorized_bytes",
            "gateway_admitted_fact_with_complete_marker_and_nonrevocation_witness",
        ],
        "forbidden_cutoffs": [
            "either_endpoint",
            "cross_shard_boundary",
            "context_budget",
        ],
    },
    "artifact_transport_full": {
        "allowed_terminal_kinds": [
            "authorized_artifact_bytes",
            "contract_approved_membership_proof_with_off_project_verifier",
        ],
        "forbidden_cutoffs": [
            "project_local_availability",
            "manifest_without_members",
            "context_budget",
        ],
    },
    "global_membership": {
        "allowed_terminal_kinds": [
            "complete_typed_membership_manifest",
            "schema_validated_local_receipt",
        ],
        "forbidden_cutoffs": [
            "bare_counts",
            "producer_asserted_complete",
            "context_budget",
        ],
    },
}

RELATION_DIRECTION = {
    ("supports_or_depends_on", "forward_use"): "source_to_target",
    ("supports_or_depends_on", "premise_closure"): "target_to_source",
    ("predecessor_use", "premise_closure"): "target_to_source",
    ("defeats_or_challenges", "premise_closure"): "both_endpoints_and_disposition",
    ("paper_maps_or_binds", "premise_closure"): "candidate_to_paper_then_source",
    ("evidence_refers_to", "artifact_closure"): "reference_to_manifest_to_members",
    ("artifact_contains_or_authorizes", "artifact_closure"): "manifest_to_member",
    ("supersedes_or_revokes", "premise_closure"): "object_to_current_head",
    ("transports_scope_or_object", "premise_closure"): "target_to_source",
}

SET_FIELDS = frozenset(
    {
        "required_artifact_refs",
        "dependency_ref_ids",
        "allowed_slot_roles",
        "obligation_ids",
        "subject_ids",
        "relation_ids",
        "boundary_stub_ids",
        "conflict_ids",
        "new_obligation_ids",
        "host_context_ids",
        "trust_domain_ids",
    }
)


def _nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def _normalized_json(value: Any, *, field_name: str = "") -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        if not -SAFE_INTEGER <= value <= SAFE_INTEGER:
            raise ValueError("JSON integer is outside the safe-integer profile")
        return value
    if isinstance(value, float):
        raise ValueError("floating-point JSON numbers are forbidden")
    if isinstance(value, str):
        return _nfc(value)
    if isinstance(value, (list, tuple)):
        items = [_normalized_json(item) for item in value]
        if field_name in SET_FIELDS:
            keyed = [(jcs_bytes(item), item) for item in items]
            if len({raw for raw, _ in keyed}) != len(keyed):
                raise ValueError(f"{field_name} contains duplicate set members")
            return [item for _, item in sorted(keyed, key=lambda pair: pair[0])]
        return items
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("JSON member names must be strings")
            normalized_key = _nfc(key)
            if normalized_key in result:
                raise ValueError("duplicate JSON member after NFC normalization")
            result[normalized_key] = _normalized_json(
                item, field_name=normalized_key
            )
        return result
    raise ValueError(f"unsupported JSON value: {type(value).__name__}")


def _jcs(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, list):
        return "[" + ",".join(_jcs(item) for item in value) + "]"
    if isinstance(value, dict):
        keys = sorted(value, key=lambda item: item.encode("utf-16be"))
        return "{" + ",".join(
            _jcs(key) + ":" + _jcs(value[key]) for key in keys
        ) + "}"
    raise ValueError("noncanonical JSON value")


def jcs_bytes(value: Any) -> bytes:
    return _jcs(_normalized_json(value)).encode("utf-8")


def file_bytes(value: Any) -> bytes:
    return jcs_bytes(value) + b"\n"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _exact(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{label} fields are not exact")
    return value


def _text(value: Any, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text")
    value = _nfc(value).strip()
    if not allow_empty and not value:
        raise ValueError(f"{label} must be nonempty")
    return value


def _strings(value: Any, label: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{label} must be a list of strings")
    result = [_text(item, label) for item in value]
    if nonempty and not result:
        raise ValueError(f"{label} must be nonempty")
    if len(result) != len(set(result)):
        raise ValueError(f"{label} contains duplicates")
    return sorted(result, key=lambda item: jcs_bytes(item))


def _hash(value: Any) -> str:
    return sha256_bytes(jcs_bytes(value))


def _content_record(
    semantic: dict[str, Any], *, prefix: str, id_field: str
) -> dict[str, Any]:
    body_sha256 = _hash(semantic)
    return {**semantic, id_field: f"{prefix}-{body_sha256}", "body_sha256": body_sha256}


def _validate_sha(value: Any, label: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{label} is not a SHA-256 digest")
    return value


def _subject(value: Any) -> dict[str, Any]:
    fields = {
        "namespace",
        "object_id",
        "object_semantic_sha256_or_null",
        "object_file_sha256_or_null",
        "use_anchors",
        "required_artifact_refs",
        "dependency_ref_ids",
        "risk_class",
    }
    value = _exact(value, fields, "verification subject")
    namespace = value["namespace"]
    if namespace not in SUBJECT_CHECK_MATRIX:
        raise ValueError("verification subject namespace is invalid")
    object_id = _text(value["object_id"], "verification subject id")
    if ID_RE.fullmatch(object_id) is None:
        raise ValueError("verification subject id is invalid")
    semantic_hash = _validate_sha(
        value["object_semantic_sha256_or_null"],
        "verification subject semantic hash",
        nullable=True,
    )
    file_hash = _validate_sha(
        value["object_file_sha256_or_null"],
        "verification subject file hash",
        nullable=True,
    )
    if semantic_hash is None and file_hash is None:
        raise ValueError("verification subject requires a semantic or file hash")
    risk = value["risk_class"]
    if risk not in {"ordinary", "high"}:
        raise ValueError("verification subject risk class is invalid")
    return {
        "namespace": namespace,
        "object_id": object_id,
        "object_semantic_sha256_or_null": semantic_hash,
        "object_file_sha256_or_null": file_hash,
        "use_anchors": _strings(value["use_anchors"], "subject use anchors"),
        "required_artifact_refs": _strings(
            value["required_artifact_refs"], "subject artifact refs"
        ),
        "dependency_ref_ids": _strings(
            value["dependency_ref_ids"], "subject dependency refs"
        ),
        "risk_class": risk,
    }


def derive_obligation_register(subjects: list[dict[str, Any]]) -> dict[str, Any]:
    normalized_subjects = [_subject(item) for item in subjects]
    identity = [(item["namespace"], item["object_id"]) for item in normalized_subjects]
    if len(identity) != len(set(identity)):
        raise ValueError("verification subject identity is duplicated")
    obligations: list[dict[str, Any]] = []
    for subject in sorted(normalized_subjects, key=lambda item: jcs_bytes(item)):
        for check_kind in SUBJECT_CHECK_MATRIX[subject["namespace"]]:
            anchors = subject["use_anchors"] or ["global"]
            for anchor in anchors:
                high_risk = subject["risk_class"] == "high"
                required_role = CHECK_REVIEWER_ROLE[check_kind]
                semantic = {
                    "subject_ref": {
                        key: subject[key]
                        for key in (
                            "namespace",
                            "object_id",
                            "object_semantic_sha256_or_null",
                            "object_file_sha256_or_null",
                        )
                    },
                    "check_kind": check_kind,
                    "scope_ref": f"{subject['namespace']}:{subject['object_id']}",
                    "applicability_rule": "matrix_required",
                    "applicability_witness_requirement": "exact_subject_instance",
                    "use_anchor_or_global_key": anchor,
                    "required_artifact_refs": subject["required_artifact_refs"],
                    "dependency_ref_ids": subject["dependency_ref_ids"],
                    "derivation_witness": (
                        f"{OBLIGATION_REGISTER_REVISION}:"
                        f"{subject['namespace']}:{check_kind}:{anchor}"
                    ),
                    "risk_class": subject["risk_class"],
                    "primary_slot_lower_bound": 1,
                    "primary_slot_upper_bound": 1,
                    "required_overlap_slot_count": 1 if high_risk else 0,
                    "allowed_slot_roles": ["primary", "overlap"],
                    "allowed_reviewer_roles": [required_role],
                    "minimum_distinct_host_context_count": 2 if high_risk else 1,
                    "minimum_trust_domain_count": 2 if high_risk else 1,
                    "cardinality_policy_derivation_witness": (
                        "risk-policy-1:high" if high_risk else "risk-policy-1:ordinary"
                    ),
                    "cutoff_profile_id": CHECK_CUTOFF_PROFILE[check_kind],
                }
                obligations.append(
                    _content_record(
                        semantic, prefix="obl", id_field="obligation_id"
                    )
                )
    register_semantic = {
        "schema_version": 1,
        "contract_revision": OBLIGATION_REGISTER_REVISION,
        "subjects": normalized_subjects,
        "obligations": sorted(
            obligations, key=lambda item: item["obligation_id"]
        ),
        "subject_check_matrix_sha256": _hash(SUBJECT_CHECK_MATRIX),
        "cutoff_registry_revision": CUTOFF_REGISTRY_REVISION,
        "cutoff_profiles_sha256": _hash(CUTOFF_PROFILES),
        "truth_effect": "none",
    }
    return _content_record(
        register_semantic, prefix="vor", id_field="register_id"
    )


def _relation(value: Any) -> dict[str, Any]:
    fields = {
        "relation_id",
        "relation_kind",
        "source_ref",
        "target_ref",
        "traversal_purpose",
        "exact_use_anchor_or_null",
        "relation_semantic_sha256_or_null",
    }
    value = _exact(value, fields, "verification relation")
    relation_id = _text(value["relation_id"], "verification relation id")
    kind = value["relation_kind"]
    purpose = value["traversal_purpose"]
    if kind not in RELATION_KINDS:
        raise ValueError("verification relation kind is invalid")
    direction = RELATION_DIRECTION.get((kind, purpose))
    if direction is None:
        raise ValueError("verification relation traversal selector is undefined")
    for ref_name in ("source_ref", "target_ref"):
        if not isinstance(value[ref_name], str) or not value[ref_name]:
            raise ValueError("verification relation endpoint is invalid")
    anchor = value["exact_use_anchor_or_null"]
    if anchor is not None:
        anchor = _text(anchor, "verification relation use anchor")
    relation_hash = _validate_sha(
        value["relation_semantic_sha256_or_null"],
        "verification relation semantic hash",
        nullable=True,
    )
    if kind == "predecessor_use" and anchor is None:
        raise ValueError("predecessor_use requires an exact use anchor")
    return {
        "relation_id": relation_id,
        "relation_kind": kind,
        "source_ref": _text(value["source_ref"], "relation source"),
        "target_ref": _text(value["target_ref"], "relation target"),
        "traversal_purpose": purpose,
        "direction": direction,
        "exact_use_anchor_or_null": anchor,
        "relation_semantic_sha256_or_null": relation_hash,
    }


def _assignment(value: Any, obligations: dict[str, dict[str, Any]]) -> dict[str, Any]:
    fields = {
        "slot_id",
        "slot_role",
        "reviewer_role",
        "principal_id",
        "host_context_id",
        "trust_domain_id",
        "host_key_id",
        "reviewer_key_id",
        "obligation_ids",
        "subject_ids",
        "relation_ids",
        "boundary_stub_ids",
        "context_budget",
        "closure_complete",
        "cutoff_profile_id",
    }
    value = _exact(value, fields, "verification assignment")
    slot_id = _text(value["slot_id"], "verification slot id")
    slot_role = value["slot_role"]
    reviewer_role = value["reviewer_role"]
    if slot_role not in SLOT_ROLES:
        raise ValueError("verification slot role is invalid")
    if reviewer_role not in REVIEWER_ROLES:
        raise ValueError("verification reviewer role is invalid or compound")
    obligation_ids = _strings(
        value["obligation_ids"], "assignment obligation ids", nonempty=True
    )
    if not set(obligation_ids).issubset(obligations):
        raise ValueError("assignment names an unknown obligation")
    if slot_role in {"primary", "overlap"}:
        if any(
            reviewer_role not in item["allowed_reviewer_roles"]
            for item in (obligations[obligation_id] for obligation_id in obligation_ids)
        ):
            raise ValueError("assignment reviewer role is not allowed by its obligation")
    expected_profiles = {
        (
            "seam_full"
            if slot_role == "seam"
            else "artifact_transport_full"
            if slot_role == "artifact_access"
            else "global_membership"
            if slot_role == "global"
            else obligations[obligation_id]["cutoff_profile_id"]
        )
        for obligation_id in obligation_ids
    }
    if len(expected_profiles) != 1 or value["cutoff_profile_id"] not in expected_profiles:
        raise ValueError("assignment cutoff profile does not follow the public registry")
    budget = value["context_budget"]
    if not isinstance(budget, int) or isinstance(budget, bool) or budget <= 0:
        raise ValueError("assignment context budget must be a positive safe integer")
    if budget > SAFE_INTEGER:
        raise ValueError("assignment context budget exceeds the safe-integer profile")
    if value["closure_complete"] is not True:
        raise ValueError("assignment closure must be mechanically complete; replan on overflow")
    return {
        "slot_id": slot_id,
        "slot_role": slot_role,
        "reviewer_role": reviewer_role,
        "principal_id": _text(value["principal_id"], "assignment principal"),
        "host_context_id": _text(value["host_context_id"], "assignment host context"),
        "trust_domain_id": _text(value["trust_domain_id"], "assignment trust domain"),
        "host_key_id": _text(value["host_key_id"], "assignment host key id"),
        "reviewer_key_id": _text(
            value["reviewer_key_id"], "assignment reviewer key id"
        ),
        "obligation_ids": obligation_ids,
        "subject_ids": _strings(value["subject_ids"], "assignment subject ids", nonempty=True),
        "relation_ids": _strings(value["relation_ids"], "assignment relation ids"),
        "boundary_stub_ids": _strings(value["boundary_stub_ids"], "assignment boundary stubs"),
        "context_budget": budget,
        "closure_complete": True,
        "cutoff_profile_id": value["cutoff_profile_id"],
    }


def build_work_plan(
    *,
    release_semantic_sha256: str,
    release_file_sha256: str,
    capsule_semantic_sha256: str,
    capsule_file_sha256: str,
    subjects: list[dict[str, Any]],
    relations: list[dict[str, Any]],
    assignments: list[dict[str, Any]],
    parent_plan_id: str = "",
    discovery_receipt_ids: list[str] | None = None,
) -> dict[str, Any]:
    for value, label in (
        (release_semantic_sha256, "release semantic hash"),
        (release_file_sha256, "release file hash"),
        (capsule_semantic_sha256, "capsule semantic hash"),
        (capsule_file_sha256, "capsule file hash"),
    ):
        _validate_sha(value, label)
    register = derive_obligation_register(subjects)
    obligation_by_id = {
        item["obligation_id"]: item for item in register["obligations"]
    }
    normalized_relations = [_relation(item) for item in relations]
    relation_ids = [item["relation_id"] for item in normalized_relations]
    if len(relation_ids) != len(set(relation_ids)):
        raise ValueError("verification relation id is duplicated")
    normalized_assignments = [
        _assignment(item, obligation_by_id) for item in assignments
    ]
    slot_ids = [item["slot_id"] for item in normalized_assignments]
    if len(slot_ids) != len(set(slot_ids)):
        raise ValueError("verification slot id is duplicated")
    known_subject_ids = {item["object_id"] for item in register["subjects"]}
    known_relation_ids = set(relation_ids)
    for assignment in normalized_assignments:
        if not set(assignment["subject_ids"]).issubset(known_subject_ids):
            raise ValueError("assignment names an unknown subject")
        if not set(assignment["relation_ids"]).issubset(known_relation_ids):
            raise ValueError("assignment names an unknown relation")
    for obligation_id, obligation in obligation_by_id.items():
        assigned = [
            item
            for item in normalized_assignments
            if obligation_id in item["obligation_ids"]
        ]
        primary = [item for item in assigned if item["slot_role"] == "primary"]
        overlap = [item for item in assigned if item["slot_role"] == "overlap"]
        if not (
            obligation["primary_slot_lower_bound"]
            <= len(primary)
            <= obligation["primary_slot_upper_bound"]
        ):
            raise ValueError("verification primary-slot cardinality is invalid")
        if len(overlap) < obligation["required_overlap_slot_count"]:
            raise ValueError("verification overlap-slot cardinality is insufficient")
        relevant = primary + overlap
        if len({item["host_context_id"] for item in relevant}) < obligation[
            "minimum_distinct_host_context_count"
        ]:
            raise ValueError("verification host-context diversity is insufficient")
        if len({item["trust_domain_id"] for item in relevant}) < obligation[
            "minimum_trust_domain_count"
        ]:
            raise ValueError("verification trust-domain diversity is insufficient")
        if len({item["principal_id"] for item in relevant}) != len(relevant):
            raise ValueError("verification primary/overlap principals must be distinct")
    semantic = {
        "schema_version": 1,
        "contract_revision": WORK_PLAN_REVISION,
        "protocol_revision": CONTRACT_REVISION,
        "release_semantic_sha256": release_semantic_sha256,
        "release_file_sha256": release_file_sha256,
        "capsule_semantic_sha256": capsule_semantic_sha256,
        "capsule_file_sha256": capsule_file_sha256,
        "obligation_register": register,
        "relations": sorted(normalized_relations, key=lambda item: item["relation_id"]),
        "assignments": sorted(normalized_assignments, key=lambda item: item["slot_id"]),
        "parent_plan_id": _text(parent_plan_id, "parent plan id", allow_empty=True),
        "discovery_receipt_ids": _strings(
            discovery_receipt_ids or [], "discovery receipt ids"
        ),
        "inventory_before_partition": True,
        "auto_topology_effect": "none",
        "truth_effect": "none",
    }
    return _content_record(semantic, prefix="vwp", id_field="plan_id")


def validate_work_plan(plan: Any) -> dict[str, Any]:
    fields = {
        "schema_version",
        "contract_revision",
        "protocol_revision",
        "release_semantic_sha256",
        "release_file_sha256",
        "capsule_semantic_sha256",
        "capsule_file_sha256",
        "obligation_register",
        "relations",
        "assignments",
        "parent_plan_id",
        "discovery_receipt_ids",
        "inventory_before_partition",
        "auto_topology_effect",
        "truth_effect",
        "plan_id",
        "body_sha256",
    }
    plan = _exact(plan, fields, "verification work plan")
    rebuilt = build_work_plan(
        release_semantic_sha256=plan["release_semantic_sha256"],
        release_file_sha256=plan["release_file_sha256"],
        capsule_semantic_sha256=plan["capsule_semantic_sha256"],
        capsule_file_sha256=plan["capsule_file_sha256"],
        subjects=plan["obligation_register"]["subjects"],
        relations=[
            {
                key: item[key]
                for key in (
                    "relation_id",
                    "relation_kind",
                    "source_ref",
                    "target_ref",
                    "traversal_purpose",
                    "exact_use_anchor_or_null",
                    "relation_semantic_sha256_or_null",
                )
            }
            for item in plan["relations"]
        ],
        assignments=plan["assignments"],
        parent_plan_id=plan["parent_plan_id"],
        discovery_receipt_ids=plan["discovery_receipt_ids"],
    )
    if rebuilt != plan:
        raise ValueError("verification work plan content or normalization drifted")
    return plan


def _assignment_semantic_sha256(assignment: dict[str, Any]) -> str:
    return _hash(assignment)


# Pure-Python Ed25519 verification, used only for host-issued freshness tokens.
_Q = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493
_D = (-121665 * pow(121666, _Q - 2, _Q)) % _Q
_I = pow(2, (_Q - 1) // 4, _Q)


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * pow(_D * y * y + 1, _Q - 2, _Q)
    x = pow(xx, (_Q + 3) // 8, _Q)
    if (x * x - xx) % _Q != 0:
        x = (x * _I) % _Q
    if x & 1:
        x = _Q - x
    return x


def _decodepoint(raw: bytes) -> tuple[int, int]:
    if len(raw) != 32:
        raise ValueError("Ed25519 point must be 32 bytes")
    y = int.from_bytes(raw, "little") & ((1 << 255) - 1)
    if y >= _Q:
        raise ValueError("Ed25519 point is noncanonical")
    x = _xrecover(y)
    if x & 1 != (raw[31] >> 7):
        x = _Q - x
    if (-x * x + y * y - 1 - _D * x * x * y * y) % _Q != 0:
        raise ValueError("Ed25519 point is not on the curve")
    return x, y


def _edwards_add(p: tuple[int, int], q: tuple[int, int]) -> tuple[int, int]:
    x1, y1 = p
    x2, y2 = q
    denominator_x = pow(1 + _D * x1 * x2 * y1 * y2, _Q - 2, _Q)
    denominator_y = pow(1 - _D * x1 * x2 * y1 * y2, _Q - 2, _Q)
    return (
        (x1 * y2 + x2 * y1) * denominator_x % _Q,
        (y1 * y2 + x1 * x2) * denominator_y % _Q,
    )


def _scalarmult(point: tuple[int, int], scalar: int) -> tuple[int, int]:
    # Extended Edwards coordinates avoid one modular inversion per addition.
    # This matters because strict subgroup validation performs a full [L]P
    # multiplication for every previously unseen immutable key/signature point.
    def extended(value: tuple[int, int]) -> tuple[int, int, int, int]:
        x, y = value
        return x, y, 1, x * y % _Q

    def add(
        p: tuple[int, int, int, int], q: tuple[int, int, int, int]
    ) -> tuple[int, int, int, int]:
        x1, y1, z1, t1 = p
        x2, y2, z2, t2 = q
        a = (y1 - x1) * (y2 - x2) % _Q
        b = (y1 + x1) * (y2 + x2) % _Q
        c = 2 * _D * t1 * t2 % _Q
        d = 2 * z1 * z2 % _Q
        e = (b - a) % _Q
        f = (d - c) % _Q
        g = (d + c) % _Q
        h = (b + a) % _Q
        return e * f % _Q, g * h % _Q, f * g % _Q, e * h % _Q

    def double(
        p: tuple[int, int, int, int]
    ) -> tuple[int, int, int, int]:
        x, y, z, _ = p
        a = x * x % _Q
        b = y * y % _Q
        c = 2 * z * z % _Q
        d = -a % _Q
        e = ((x + y) * (x + y) - a - b) % _Q
        g = (d + b) % _Q
        f = (g - c) % _Q
        h = (d - b) % _Q
        return e * f % _Q, g * h % _Q, f * g % _Q, e * h % _Q

    result = (0, 1, 1, 0)
    addend = extended(point)
    while scalar:
        if scalar & 1:
            result = add(result, addend)
        addend = double(addend)
        scalar >>= 1
    x, y, z, _ = result
    inverse = pow(z, _Q - 2, _Q)
    return x * inverse % _Q, y * inverse % _Q


_B = (_xrecover(4 * pow(5, _Q - 2, _Q) % _Q), 4 * pow(5, _Q - 2, _Q) % _Q)


@lru_cache(maxsize=4096)
def _prime_order_point(raw: bytes) -> tuple[int, int]:
    point = _decodepoint(raw)
    if point == (0, 1) or _scalarmult(point, _L) != (0, 1):
        raise ValueError("Ed25519 point is identity or outside the prime-order subgroup")
    return point


@lru_cache(maxsize=8192)
def verify_ed25519(public_key: bytes, message: bytes, signature: bytes) -> bool:
    try:
        if len(public_key) != 32 or len(signature) != 64:
            return False
        r_raw, s_raw = signature[:32], signature[32:]
        scalar = int.from_bytes(s_raw, "little")
        if scalar >= _L:
            return False
        public_point = _prime_order_point(public_key)
        r_point = _prime_order_point(r_raw)
        # RFC 8032 verification must not accept the identity or a point outside
        # the prime-order subgroup.  Without these checks, identity A/R with
        # S=0 verifies arbitrary messages in the naive group equation.
        challenge = int.from_bytes(
            hashlib.sha512(r_raw + public_key + message).digest(), "little"
        ) % _L
        return _scalarmult(_B, scalar) == _edwards_add(
            r_point, _scalarmult(public_point, challenge)
        )
    except (ValueError, ZeroDivisionError):
        return False


def build_trusted_key_record(
    *,
    project_id: str,
    key_role: str,
    public_key_hex: str,
    principal_id: str,
    reviewer_role_or_null: str | None,
    host_context_id_or_null: str | None,
    trust_domain_id: str,
    registered_by: str,
) -> dict[str, Any]:
    project_id = _text(project_id, "verification key project id")
    if key_role not in TRUST_KEY_ROLES:
        raise ValueError("verification trusted key role is invalid")
    principal_id = _text(principal_id, "verification key principal")
    trust_domain_id = _text(trust_domain_id, "verification key trust domain")
    registered_by = _text(registered_by, "verification key registrar")
    try:
        public_key = bytes.fromhex(public_key_hex)
    except (TypeError, ValueError) as exc:
        raise ValueError("verification trusted public key encoding is invalid") from exc
    if len(public_key) != 32:
        raise ValueError("verification trusted public key must be 32 bytes")
    try:
        _prime_order_point(public_key)
    except ValueError as exc:
        raise ValueError(f"verification trusted public key is invalid: {exc}") from exc
    if key_role == "reviewer":
        if reviewer_role_or_null not in REVIEWER_ROLES:
            raise ValueError("verification reviewer key has an invalid reviewer role")
        if host_context_id_or_null is not None:
            raise ValueError("verification reviewer key cannot claim a host context")
    elif reviewer_role_or_null is not None:
        raise ValueError("verification non-reviewer key cannot claim a reviewer role")
    if key_role == "host":
        host_context_id = _text(
            host_context_id_or_null, "verification host key context"
        )
    elif host_context_id_or_null is not None:
        raise ValueError("verification non-host key cannot claim a host context")
    else:
        host_context_id = None
    semantic = {
        "schema_version": 1,
        "contract_revision": TRUST_KEY_REVISION,
        "project_id": project_id,
        "key_role": key_role,
        "reviewer_role_or_null": reviewer_role_or_null,
        "principal_id": principal_id,
        "host_context_id_or_null": host_context_id,
        "trust_domain_id": trust_domain_id,
        "public_key_hex": public_key.hex(),
        "registered_by": registered_by,
        "truth_effect": "none",
    }
    return _content_record(semantic, prefix="vtk", id_field="key_id")


def validate_trusted_key_record(
    value: Any, *, project_id: str | None = None
) -> dict[str, Any]:
    fields = {
        "schema_version",
        "contract_revision",
        "project_id",
        "key_role",
        "reviewer_role_or_null",
        "principal_id",
        "host_context_id_or_null",
        "trust_domain_id",
        "public_key_hex",
        "registered_by",
        "truth_effect",
        "key_id",
        "body_sha256",
    }
    value = _exact(value, fields, "verification trusted key record")
    rebuilt = build_trusted_key_record(
        project_id=value["project_id"],
        key_role=value["key_role"],
        public_key_hex=value["public_key_hex"],
        principal_id=value["principal_id"],
        reviewer_role_or_null=value["reviewer_role_or_null"],
        host_context_id_or_null=value["host_context_id_or_null"],
        trust_domain_id=value["trust_domain_id"],
        registered_by=value["registered_by"],
    )
    if rebuilt != value:
        raise ValueError("verification trusted key record drifted")
    if project_id is not None and value["project_id"] != project_id:
        raise ValueError("verification trusted key belongs to another project")
    return value


def validate_trusted_key_registry(
    value: Any, *, project_id: str | None = None
) -> dict[str, dict[str, Any]]:
    """Validate one project registry and reject cryptographic identity aliases.

    Distinct metadata and content-derived key ids do not establish independent
    reviewers when they resolve to the same Ed25519 public key.  Registry-wide
    uniqueness is therefore an authority invariant, not merely a registration
    convenience.
    """

    if not isinstance(value, dict):
        raise ValueError("verification trusted key registry is missing")
    if any(not isinstance(key_id, str) for key_id in value):
        raise ValueError("verification trusted key registry id is invalid")
    normalized: dict[str, dict[str, Any]] = {}
    public_key_owners: dict[str, str] = {}
    for key_id in sorted(value):
        record = validate_trusted_key_record(
            value[key_id], project_id=project_id
        )
        if record["key_id"] != key_id:
            raise ValueError("verification trusted key registry id drifted")
        public_key_hex = record["public_key_hex"]
        prior_key_id = public_key_owners.get(public_key_hex)
        if prior_key_id is not None and prior_key_id != key_id:
            raise ValueError(
                "verification trusted key registry aliases one Ed25519 public "
                "key across multiple identities"
            )
        public_key_owners[public_key_hex] = key_id
        normalized[key_id] = record
    return normalized


def _trusted_key(
    trusted_keys: dict[str, dict[str, Any]],
    key_id: str,
    *,
    expected_role: str,
) -> dict[str, Any]:
    if not isinstance(trusted_keys, dict):
        raise ValueError("verification trusted key registry is missing")
    record = trusted_keys.get(key_id)
    if record is None:
        raise ValueError("verification attestation key is not Operator-trusted")
    record = validate_trusted_key_record(record)
    if record["key_id"] != key_id or record["key_role"] != expected_role:
        raise ValueError("verification attestation key role is invalid")
    return record


def prepare_work_plan_attestation(plan: dict[str, Any]) -> dict[str, Any]:
    plan = validate_work_plan(plan)
    return {
        "contract_revision": SIGNED_PLAN_REVISION,
        "plan_id": plan["plan_id"],
        "plan_body_sha256": plan["body_sha256"],
        "release_semantic_sha256": plan["release_semantic_sha256"],
        "release_file_sha256": plan["release_file_sha256"],
        "capsule_semantic_sha256": plan["capsule_semantic_sha256"],
        "capsule_file_sha256": plan["capsule_file_sha256"],
    }


def _validate_durable_attestation(
    value: Any,
    *,
    signed_body: dict[str, Any],
    trusted_keys: dict[str, dict[str, Any]],
    expected_role: str,
    expected_scope: str,
) -> dict[str, Any]:
    value = _exact(
        value,
        {"algorithm", "key_id", "signature_hex", "scope"},
        "verification durable attestation",
    )
    if value["algorithm"] != "Ed25519":
        raise ValueError("verification signature algorithm is invalid")
    key_id = _text(value["key_id"], "verification attestation key id")
    key = _trusted_key(trusted_keys, key_id, expected_role=expected_role)
    scope = _text(value["scope"], "verification attestation scope")
    if scope != expected_scope:
        raise ValueError("verification durable attestation scope is invalid")
    try:
        signature = bytes.fromhex(value["signature_hex"])
        public_key = bytes.fromhex(key["public_key_hex"])
    except (TypeError, ValueError) as exc:
        raise ValueError("verification signature encoding is invalid") from exc
    projection = {
        **signed_body,
        "key_id": key_id,
        "scope": scope,
        "key_role": key["key_role"],
        "principal_id": key["principal_id"],
        "trust_domain_id": key["trust_domain_id"],
    }
    if not verify_ed25519(public_key, jcs_bytes(projection), signature):
        raise ValueError("verification durable attestation signature is invalid")
    return value


def build_signed_work_plan(
    *,
    plan: dict[str, Any],
    planner_attestation: dict[str, Any],
    trusted_keys: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    trusted_keys = validate_trusted_key_registry(trusted_keys)
    plan = validate_work_plan(plan)
    body = prepare_work_plan_attestation(plan)
    _validate_durable_attestation(
        planner_attestation,
        signed_body=body,
        trusted_keys=trusted_keys,
        expected_role="planner",
        expected_scope=f"plan:{plan['plan_id']}",
    )
    planner_key_id = planner_attestation["key_id"]
    for assignment in plan["assignments"]:
        host_key = _trusted_key(
            trusted_keys, assignment["host_key_id"], expected_role="host"
        )
        reviewer_key = _trusted_key(
            trusted_keys, assignment["reviewer_key_id"], expected_role="reviewer"
        )
        if (
            host_key["host_context_id_or_null"] != assignment["host_context_id"]
            or host_key["trust_domain_id"] != assignment["trust_domain_id"]
            or reviewer_key["principal_id"] != assignment["principal_id"]
            or reviewer_key["reviewer_role_or_null"] != assignment["reviewer_role"]
            or planner_key_id
            in {assignment["host_key_id"], assignment["reviewer_key_id"]}
            or assignment["host_key_id"] == assignment["reviewer_key_id"]
        ):
            raise ValueError(
                "verification assignment is not bound to the exact trusted host/reviewer keys"
            )
    semantic = {
        "schema_version": 1,
        "contract_revision": SIGNED_PLAN_REVISION,
        "work_plan": plan,
        "planner_attestation": planner_attestation,
        "truth_effect": "none",
    }
    return _content_record(semantic, prefix="vsp", id_field="signed_plan_id")


def validate_signed_work_plan(
    value: Any, *, trusted_keys: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    fields = {
        "schema_version",
        "contract_revision",
        "work_plan",
        "planner_attestation",
        "truth_effect",
        "signed_plan_id",
        "body_sha256",
    }
    value = _exact(value, fields, "verification signed work plan")
    rebuilt = build_signed_work_plan(
        plan=value["work_plan"],
        planner_attestation=value["planner_attestation"],
        trusted_keys=trusted_keys,
    )
    if value != rebuilt:
        raise ValueError("verification signed work plan drifted")
    return value


@dataclass
class FreshnessReplayCache:
    used_nonces: set[str] = field(default_factory=set)

    def consume(self, nonce: str) -> None:
        if nonce in self.used_nonces:
            raise ValueError("verification freshness nonce was replayed")
        self.used_nonces.add(nonce)


def _parse_time(value: str, label: str) -> datetime:
    value = _text(value, label)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} is not an ISO-8601 time") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _validate_fresh_attestation(
    value: Any,
    *,
    signed_body: dict[str, Any],
    trusted_keys: dict[str, dict[str, Any]],
    expected_key_id: str,
    expected_role: str,
    expected_scope: str,
    now: datetime,
    replay_cache: FreshnessReplayCache | None,
) -> dict[str, Any]:
    fields = {
        "algorithm",
        "key_id",
        "signature_hex",
        "nonce",
        "scope",
        "issued_at",
        "expires_at",
        "result_visibility",
    }
    value = _exact(value, fields, "verification fresh attestation")
    if value["algorithm"] != "Ed25519":
        raise ValueError("verification signature algorithm is invalid")
    key_id = _text(value["key_id"], "verification attestation key id")
    if key_id != expected_key_id:
        raise ValueError("verification attestation uses the wrong trusted key")
    key = _trusted_key(trusted_keys, key_id, expected_role=expected_role)
    try:
        public_key = bytes.fromhex(key["public_key_hex"])
        signature = bytes.fromhex(value["signature_hex"])
    except (TypeError, ValueError) as exc:
        raise ValueError("verification trusted key/signature encoding is invalid") from exc
    issued = _parse_time(value["issued_at"], "verification attestation issued_at")
    expires = _parse_time(value["expires_at"], "verification attestation expires_at")
    now = now.astimezone(timezone.utc)
    if not issued <= now <= expires or expires <= issued:
        raise ValueError("verification fresh attestation is stale")
    scope = _text(value["scope"], "verification attestation scope")
    if scope != expected_scope:
        raise ValueError("verification fresh attestation scope is invalid")
    projection = {
        **signed_body,
        "nonce": _text(value["nonce"], "verification attestation nonce"),
        "scope": scope,
        "issued_at": value["issued_at"],
        "expires_at": value["expires_at"],
        "result_visibility": value["result_visibility"],
        "key_id": key_id,
        "key_role": key["key_role"],
        "principal_id": key["principal_id"],
        "reviewer_role_or_null": key["reviewer_role_or_null"],
        "host_context_id_or_null": key["host_context_id_or_null"],
        "trust_domain_id": key["trust_domain_id"],
    }
    if value["result_visibility"] not in {"blind_to_peers", "peer_results_visible"}:
        raise ValueError("verification result visibility is invalid")
    if not verify_ed25519(public_key, jcs_bytes(projection), signature):
        raise ValueError("verification fresh attestation signature is invalid")
    if replay_cache is not None:
        replay_cache.consume(projection["nonce"])
    return value


def prepare_dispatch_packet(
    *,
    signed_plan: dict[str, Any],
    slot_id: str,
    trusted_keys: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    signed_plan = validate_signed_work_plan(signed_plan, trusted_keys=trusted_keys)
    plan = signed_plan["work_plan"]
    assignment = next(
        (item for item in plan["assignments"] if item["slot_id"] == slot_id),
        None,
    )
    if assignment is None:
        raise ValueError("verification dispatch requires an exact planned slot")
    semantic = {
        "schema_version": 1,
        "contract_revision": PACKET_REVISION,
        "protocol_revision": CONTRACT_REVISION,
        "plan_id": plan["plan_id"],
        "plan_body_sha256": plan["body_sha256"],
        "signed_plan_id": signed_plan["signed_plan_id"],
        "signed_plan_body_sha256": signed_plan["body_sha256"],
        "slot_id": assignment["slot_id"],
        "slot_role": assignment["slot_role"],
        "reviewer_role": assignment["reviewer_role"],
        "principal_id": assignment["principal_id"],
        "assignment_semantic_sha256": _assignment_semantic_sha256(assignment),
        "obligation_ids": assignment["obligation_ids"],
        "subject_ids": assignment["subject_ids"],
        "relation_ids": assignment["relation_ids"],
        "boundary_stub_ids": assignment["boundary_stub_ids"],
        "context_budget": assignment["context_budget"],
        "cutoff_profile_id": assignment["cutoff_profile_id"],
        "mutation_boundary": "read_only_no_project_mutation",
        "truth_effect": "none",
    }
    record = _content_record(semantic, prefix="vpk", id_field="packet_id")
    signed_body = {
        "contract_revision": PACKET_REVISION,
        "plan_id": plan["plan_id"],
        "plan_body_sha256": plan["body_sha256"],
        "signed_plan_id": signed_plan["signed_plan_id"],
        "signed_plan_body_sha256": signed_plan["body_sha256"],
        "slot_id": assignment["slot_id"],
        "assignment_semantic_sha256": record["assignment_semantic_sha256"],
        "packet_id": record["packet_id"],
        "packet_body_sha256": record["body_sha256"],
    }
    return {"record": record, "attestation_body": signed_body}


def build_dispatch_packet(
    *,
    signed_plan: dict[str, Any],
    slot_id: str,
    host_attestation: dict[str, Any],
    trusted_keys: dict[str, dict[str, Any]],
    now: datetime | None = None,
    replay_cache: FreshnessReplayCache | None = None,
) -> dict[str, Any]:
    prepared = prepare_dispatch_packet(
        signed_plan=signed_plan, slot_id=slot_id, trusted_keys=trusted_keys
    )
    plan = signed_plan["work_plan"]
    record = prepared["record"]
    assignment = next(
        item for item in plan["assignments"] if item["slot_id"] == slot_id
    )
    _validate_fresh_attestation(
        host_attestation,
        signed_body=prepared["attestation_body"],
        trusted_keys=trusted_keys,
        expected_key_id=assignment["host_key_id"],
        expected_role="host",
        expected_scope=f"dispatch:{plan['plan_id']}:{slot_id}",
        now=now or datetime.now(timezone.utc),
        replay_cache=replay_cache,
    )
    if host_attestation["result_visibility"] != "blind_to_peers":
        raise ValueError("verification dispatch must be blind to peer results")
    return {**record, "host_attestation": host_attestation}


def validate_dispatch_packet(
    packet: Any,
    *,
    signed_plan: dict[str, Any],
    trusted_keys: dict[str, dict[str, Any]],
    now: datetime | None = None,
    replay_cache: FreshnessReplayCache | None = None,
) -> dict[str, Any]:
    fields = {
        "schema_version",
        "contract_revision",
        "protocol_revision",
        "plan_id",
        "plan_body_sha256",
        "signed_plan_id",
        "signed_plan_body_sha256",
        "slot_id",
        "slot_role",
        "reviewer_role",
        "principal_id",
        "assignment_semantic_sha256",
        "obligation_ids",
        "subject_ids",
        "relation_ids",
        "boundary_stub_ids",
        "context_budget",
        "cutoff_profile_id",
        "mutation_boundary",
        "truth_effect",
        "packet_id",
        "body_sha256",
        "host_attestation",
    }
    packet = _exact(packet, fields, "verification dispatch packet")
    host_attestation = packet["host_attestation"]
    semantic = {
        key: value for key, value in packet.items() if key != "host_attestation"
    }
    expected = build_dispatch_packet(
        signed_plan=signed_plan,
        slot_id=packet["slot_id"],
        host_attestation=host_attestation,
        trusted_keys=trusted_keys,
        now=now,
        replay_cache=replay_cache,
    )
    if packet != expected or semantic["packet_id"] != expected["packet_id"]:
        raise ValueError("verification dispatch packet drifted from its frozen plan")
    return packet


def validate_receipt(
    receipt: Any,
    *,
    signed_plan: dict[str, Any],
    packet: dict[str, Any],
    trusted_keys: dict[str, dict[str, Any]],
    now: datetime | None = None,
    replay_cache: FreshnessReplayCache | None = None,
) -> dict[str, Any]:
    signed_plan = validate_signed_work_plan(signed_plan, trusted_keys=trusted_keys)
    plan = signed_plan["work_plan"]
    validate_dispatch_packet(
        packet, signed_plan=signed_plan, trusted_keys=trusted_keys, now=now
    )
    fields = {
        "schema_version",
        "contract_revision",
        "plan_id",
        "plan_body_sha256",
        "signed_plan_id",
        "signed_plan_body_sha256",
        "packet_id",
        "packet_body_sha256",
        "slot_id",
        "slot_role",
        "reviewer_role",
        "principal_id",
        "obligation_results",
        "subject_hashes",
        "conflicts",
        "new_obligations",
        "scope",
        "mutation_boundary",
        "reviewer_attestation",
        "truth_effect",
        "receipt_id",
        "body_sha256",
    }
    receipt = _exact(receipt, fields, "verification machine receipt")
    if (
        receipt["schema_version"] != 1
        or receipt["contract_revision"] != RECEIPT_REVISION
        or receipt["plan_id"] != plan["plan_id"]
        or receipt["plan_body_sha256"] != plan["body_sha256"]
        or receipt["signed_plan_id"] != signed_plan["signed_plan_id"]
        or receipt["signed_plan_body_sha256"] != signed_plan["body_sha256"]
        or receipt["packet_id"] != packet["packet_id"]
        or receipt["packet_body_sha256"] != packet["body_sha256"]
        or receipt["truth_effect"] != "none"
    ):
        raise ValueError("verification receipt contract or plan binding is invalid")
    assignment = next(
        (item for item in plan["assignments"] if item["slot_id"] == receipt["slot_id"]),
        None,
    )
    if assignment is None:
        raise ValueError("verification receipt targets an unknown slot")
    for field_name in ("slot_role", "reviewer_role", "principal_id"):
        if receipt[field_name] != assignment[field_name]:
            raise ValueError("verification receipt assignment binding drifted")
    results = receipt["obligation_results"]
    if not isinstance(results, list):
        raise ValueError("verification obligation results must be a list")
    seen: set[str] = set()
    for result in results:
        _exact(
            result,
            {
                "obligation_id",
                "status",
                "finding_ids",
                "proof_anchor_ids",
                "not_applicable_witness_or_null",
            },
            "verification obligation result",
        )
        obligation_id = result["obligation_id"]
        if obligation_id not in assignment["obligation_ids"] or obligation_id in seen:
            raise ValueError("verification receipt obligation coverage is invalid")
        seen.add(obligation_id)
        if result["status"] not in RECEIPT_STATUSES:
            raise ValueError("verification receipt status is invalid")
        _strings(result["finding_ids"], "verification result finding ids")
        anchors = _strings(result["proof_anchor_ids"], "verification proof anchors")
        if result["status"] == "supported" and not anchors:
            raise ValueError("supported verification result requires proof anchors")
        witness = result["not_applicable_witness_or_null"]
        if result["status"] == "not_applicable":
            if not isinstance(witness, dict):
                raise ValueError("not_applicable requires a machine witness")
        elif witness is not None:
            raise ValueError("only not_applicable may carry its witness")
    if seen != set(assignment["obligation_ids"]):
        raise ValueError("verification receipt does not cover its exact slot")
    subject_hashes = receipt["subject_hashes"]
    if not isinstance(subject_hashes, list):
        raise ValueError("verification receipt subject hashes must be a list")
    if {item.get("object_id") for item in subject_hashes} != set(
        assignment["subject_ids"]
    ):
        raise ValueError("verification receipt subject coverage is incomplete")
    for item in subject_hashes:
        _exact(
            item,
            {"object_id", "semantic_sha256_or_null", "file_sha256_or_null"},
            "verification receipt subject hash",
        )
        _validate_sha(item["semantic_sha256_or_null"], "receipt semantic hash", nullable=True)
        _validate_sha(item["file_sha256_or_null"], "receipt file hash", nullable=True)
    for key in ("conflicts", "new_obligations"):
        if not isinstance(receipt[key], list) or any(
            not isinstance(item, dict) for item in receipt[key]
        ):
            raise ValueError(f"verification receipt {key} must be machine objects")
    scope = _exact(
        receipt["scope"],
        {"subject_ids", "relation_ids", "boundary_stub_ids"},
        "verification receipt scope",
    )
    if (
        _strings(scope["subject_ids"], "receipt scope subject ids")
        != assignment["subject_ids"]
        or _strings(scope["relation_ids"], "receipt scope relation ids")
        != assignment["relation_ids"]
        or _strings(scope["boundary_stub_ids"], "receipt boundary stubs")
        != assignment["boundary_stub_ids"]
    ):
        raise ValueError("verification receipt scope drifted")
    if receipt["mutation_boundary"] != "read_only_no_project_mutation":
        raise ValueError("verification receipt mutation boundary is invalid")
    semantic = {
        key: value
        for key, value in receipt.items()
        if key not in {"receipt_id", "body_sha256", "reviewer_attestation"}
    }
    expected = _content_record(semantic, prefix="vmr", id_field="receipt_id")
    if receipt["receipt_id"] != expected["receipt_id"] or receipt["body_sha256"] != expected["body_sha256"]:
        raise ValueError("verification receipt content id mismatch")
    attestation_body = {
        "contract_revision": RECEIPT_REVISION,
        "plan_id": plan["plan_id"],
        "plan_body_sha256": plan["body_sha256"],
        "signed_plan_id": signed_plan["signed_plan_id"],
        "signed_plan_body_sha256": signed_plan["body_sha256"],
        "packet_id": packet["packet_id"],
        "packet_body_sha256": packet["body_sha256"],
        "slot_id": assignment["slot_id"],
        "slot_role": assignment["slot_role"],
        "reviewer_role": assignment["reviewer_role"],
        "principal_id": assignment["principal_id"],
        "receipt_id": receipt["receipt_id"],
        "receipt_body_sha256": receipt["body_sha256"],
    }
    _validate_fresh_attestation(
        receipt["reviewer_attestation"],
        signed_body=attestation_body,
        trusted_keys=trusted_keys,
        expected_key_id=assignment["reviewer_key_id"],
        expected_role="reviewer",
        expected_scope=f"result:{plan['plan_id']}:{assignment['slot_id']}",
        now=now or datetime.now(timezone.utc),
        replay_cache=replay_cache,
    )
    if receipt["reviewer_attestation"]["result_visibility"] != "blind_to_peers":
        raise ValueError("verification reviewer receipt must be blind to peer results")
    return receipt


def build_machine_receipt(
    *,
    signed_plan: dict[str, Any],
    packet: dict[str, Any],
    obligation_results: list[dict[str, Any]],
    subject_hashes: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
    new_obligations: list[dict[str, Any]],
    reviewer_attestation: dict[str, Any],
    trusted_keys: dict[str, dict[str, Any]],
    now: datetime | None = None,
    replay_cache: FreshnessReplayCache | None = None,
) -> dict[str, Any]:
    prepared = prepare_machine_receipt(
        signed_plan=signed_plan,
        packet=packet,
        obligation_results=obligation_results,
        subject_hashes=subject_hashes,
        conflicts=conflicts,
        new_obligations=new_obligations,
        trusted_keys=trusted_keys,
        now=now,
    )
    candidate = {
        **prepared["record"],
        "reviewer_attestation": reviewer_attestation,
    }
    return validate_receipt(
        candidate,
        signed_plan=signed_plan,
        packet=packet,
        trusted_keys=trusted_keys,
        now=now,
        replay_cache=replay_cache,
    )


def prepare_machine_receipt(
    *,
    signed_plan: dict[str, Any],
    packet: dict[str, Any],
    obligation_results: list[dict[str, Any]],
    subject_hashes: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
    new_obligations: list[dict[str, Any]],
    trusted_keys: dict[str, dict[str, Any]],
    now: datetime | None = None,
) -> dict[str, Any]:
    signed_plan = validate_signed_work_plan(signed_plan, trusted_keys=trusted_keys)
    plan = signed_plan["work_plan"]
    packet = validate_dispatch_packet(
        packet, signed_plan=signed_plan, trusted_keys=trusted_keys, now=now
    )
    assignment = next(
        item for item in plan["assignments"] if item["slot_id"] == packet["slot_id"]
    )
    semantic = {
        "schema_version": 1,
        "contract_revision": RECEIPT_REVISION,
        "plan_id": plan["plan_id"],
        "plan_body_sha256": plan["body_sha256"],
        "signed_plan_id": signed_plan["signed_plan_id"],
        "signed_plan_body_sha256": signed_plan["body_sha256"],
        "packet_id": packet["packet_id"],
        "packet_body_sha256": packet["body_sha256"],
        "slot_id": assignment["slot_id"],
        "slot_role": assignment["slot_role"],
        "reviewer_role": assignment["reviewer_role"],
        "principal_id": assignment["principal_id"],
        "obligation_results": obligation_results,
        "subject_hashes": subject_hashes,
        "conflicts": conflicts,
        "new_obligations": new_obligations,
        "scope": {
            "subject_ids": assignment["subject_ids"],
            "relation_ids": assignment["relation_ids"],
            "boundary_stub_ids": assignment["boundary_stub_ids"],
        },
        "mutation_boundary": "read_only_no_project_mutation",
        "truth_effect": "none",
    }
    record = _content_record(semantic, prefix="vmr", id_field="receipt_id")
    attestation_body = {
        "contract_revision": RECEIPT_REVISION,
        "plan_id": plan["plan_id"],
        "plan_body_sha256": plan["body_sha256"],
        "signed_plan_id": signed_plan["signed_plan_id"],
        "signed_plan_body_sha256": signed_plan["body_sha256"],
        "packet_id": packet["packet_id"],
        "packet_body_sha256": packet["body_sha256"],
        "slot_id": assignment["slot_id"],
        "slot_role": assignment["slot_role"],
        "reviewer_role": assignment["reviewer_role"],
        "principal_id": assignment["principal_id"],
        "receipt_id": record["receipt_id"],
        "receipt_body_sha256": record["body_sha256"],
    }
    return {"record": record, "attestation_body": attestation_body}


def aggregate_receipts(
    *,
    signed_plan: dict[str, Any],
    packets: list[dict[str, Any]],
    receipts: list[dict[str, Any]],
    trusted_keys: dict[str, dict[str, Any]],
    now: datetime | None = None,
) -> dict[str, Any]:
    signed_plan = validate_signed_work_plan(signed_plan, trusted_keys=trusted_keys)
    plan = signed_plan["work_plan"]
    replay_cache = FreshnessReplayCache()
    packet_by_slot: dict[str, dict[str, Any]] = {}
    for packet in packets:
        validated_packet = validate_dispatch_packet(
            packet,
            signed_plan=signed_plan,
            trusted_keys=trusted_keys,
            now=now,
            replay_cache=replay_cache,
        )
        if validated_packet["slot_id"] in packet_by_slot:
            raise ValueError("verification aggregate contains duplicate dispatch packets")
        packet_by_slot[validated_packet["slot_id"]] = validated_packet
    validated = [
        validate_receipt(
            item,
            signed_plan=signed_plan,
            packet=packet_by_slot.get(item.get("slot_id"), {}),
            trusted_keys=trusted_keys,
            now=now,
            replay_cache=replay_cache,
        )
        for item in receipts
    ]
    if len({item["slot_id"] for item in validated}) != len(validated):
        raise ValueError("verification aggregate contains duplicate slot receipts")
    by_slot = {item["slot_id"]: item for item in validated}
    missing_slots = sorted(
        set(item["slot_id"] for item in plan["assignments"]).difference(by_slot)
    )
    obligation_results: dict[str, list[dict[str, Any]]] = {}
    for receipt in validated:
        for result in receipt["obligation_results"]:
            obligation_results.setdefault(result["obligation_id"], []).append(
                {"slot_id": receipt["slot_id"], **result}
            )
    unresolved: list[dict[str, Any]] = []
    rejects: list[dict[str, Any]] = []
    for obligation in plan["obligation_register"]["obligations"]:
        obligation_id = obligation["obligation_id"]
        rows = obligation_results.get(obligation_id, [])
        assigned = [
            item
            for item in plan["assignments"]
            if obligation_id in item["obligation_ids"]
        ]
        expected_slots = {item["slot_id"] for item in assigned}
        observed_slots = {item["slot_id"] for item in rows}
        if expected_slots != observed_slots:
            unresolved.append(
                {
                    "obligation_id": obligation_id,
                    "reason": "machine_receipt_coverage_incomplete",
                }
            )
            continue
        for row in rows:
            if row["status"] == "reject":
                rejects.append(
                    {
                        "obligation_id": obligation_id,
                        "slot_id": row["slot_id"],
                        "finding_ids": row["finding_ids"],
                    }
                )
            elif row["status"] in {"needs_adjudication", "not_applicable"}:
                unresolved.append(
                    {
                        "obligation_id": obligation_id,
                        "slot_id": row["slot_id"],
                        "reason": row["status"],
                    }
                )
    conflicts = [
        {"receipt_id": item["receipt_id"], "conflict": conflict}
        for item in validated
        for conflict in item["conflicts"]
    ]
    new_obligations = [
        {"receipt_id": item["receipt_id"], "new_obligation": obligation}
        for item in validated
        for obligation in item["new_obligations"]
    ]
    eligible = not (
        missing_slots or unresolved or rejects or conflicts or new_obligations
    )
    semantic = {
        "schema_version": 1,
        "contract_revision": AGGREGATE_REVISION,
        "protocol_revision": CONTRACT_REVISION,
        "plan_id": plan["plan_id"],
        "plan_body_sha256": plan["body_sha256"],
        "signed_plan_id": signed_plan["signed_plan_id"],
        "signed_plan_body_sha256": signed_plan["body_sha256"],
        "packet_ids": sorted(item["packet_id"] for item in packet_by_slot.values()),
        "receipt_ids": sorted(item["receipt_id"] for item in validated),
        "missing_slot_ids": missing_slots,
        "rejects": sorted(rejects, key=jcs_bytes),
        "unresolved": sorted(unresolved, key=jcs_bytes),
        "conflicts": sorted(conflicts, key=jcs_bytes),
        "new_obligations": sorted(new_obligations, key=jcs_bytes),
        "aggregate_eligible_for_decision": eligible,
        "semantic_inference_performed": False,
        "majority_vote_performed": False,
        "truth_effect": "none",
        "fact_admission_effect": "none",
    }
    return _content_record(semantic, prefix="vag", id_field="aggregate_id")


def validate_aggregate(
    aggregate: Any,
    *,
    signed_plan: dict[str, Any],
    trusted_keys: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    fields = {
        "schema_version",
        "contract_revision",
        "protocol_revision",
        "plan_id",
        "plan_body_sha256",
        "signed_plan_id",
        "signed_plan_body_sha256",
        "packet_ids",
        "receipt_ids",
        "missing_slot_ids",
        "rejects",
        "unresolved",
        "conflicts",
        "new_obligations",
        "aggregate_eligible_for_decision",
        "semantic_inference_performed",
        "majority_vote_performed",
        "truth_effect",
        "fact_admission_effect",
        "aggregate_id",
        "body_sha256",
    }
    aggregate = _exact(aggregate, fields, "verification aggregate")
    signed_plan = validate_signed_work_plan(signed_plan, trusted_keys=trusted_keys)
    plan = signed_plan["work_plan"]
    if (
        aggregate["contract_revision"] != AGGREGATE_REVISION
        or aggregate["plan_id"] != plan["plan_id"]
        or aggregate["plan_body_sha256"] != plan["body_sha256"]
        or aggregate["signed_plan_id"] != signed_plan["signed_plan_id"]
        or aggregate["signed_plan_body_sha256"] != signed_plan["body_sha256"]
        or aggregate["semantic_inference_performed"] is not False
        or aggregate["majority_vote_performed"] is not False
        or aggregate["truth_effect"] != "none"
        or aggregate["fact_admission_effect"] != "none"
    ):
        raise ValueError("verification aggregate boundary is invalid")
    semantic = {
        key: value
        for key, value in aggregate.items()
        if key not in {"aggregate_id", "body_sha256"}
    }
    expected = _content_record(semantic, prefix="vag", id_field="aggregate_id")
    if aggregate != expected:
        raise ValueError("verification aggregate content id mismatch")
    expected_eligible = not any(
        aggregate[key]
        for key in (
            "missing_slot_ids",
            "rejects",
            "unresolved",
            "conflicts",
            "new_obligations",
        )
    )
    if aggregate["aggregate_eligible_for_decision"] is not expected_eligible:
        raise ValueError("verification aggregate eligibility is inconsistent")
    if "globally_admissible" in aggregate:
        raise ValueError("nontruth verification aggregate cannot claim admissibility")
    return aggregate

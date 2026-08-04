from __future__ import annotations

"""Prospective research-draft Paper lifecycle and admission preflight support.

Historical Paper continuation v1 objects remain readable by their original
manager.  This module is the strict path for a new or explicitly upgraded
``research_draft``: it binds the whole Paper target set, applies one explicit
domain continuity adapter, publishes dispositions as an all-or-none batch,
qualifies failure surfaces globally, and keeps node disposition distinct from
many-to-many Candidate mapping.  Only philosophy has a stance adapter.
Mathematics keeps an immutable exact target while admitting a typed refinement
DAG as non-closing intermediate progress.
"""

import json
import os
import re
import secrets
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import SHA256_RE, contained_path, sha256_bytes, sha256_json
from .paper_continuation import PaperContinuationManager
from .paper_logic_contracts import PAPER_SNAPSHOT_ID_RE


LEGACY_RESEARCH_DRAFT_PLAN_REVISION = "chalxius-research-draft-plan-1"
RESEARCH_DRAFT_PLAN_REVISION = "chalxius-research-draft-plan-2"
LEGACY_RESEARCH_DRAFT_BATCH_REVISION = (
    "chalxius-research-draft-disposition-batch-1"
)
RESEARCH_DRAFT_BATCH_REVISION = "chalxius-research-draft-disposition-batch-2"
LEGACY_RESEARCH_DRAFT_ADEQUACY_REVISION = "chalxius-research-draft-adequacy-1"
RESEARCH_DRAFT_ADEQUACY_REVISION = "chalxius-research-draft-adequacy-2"
RESEARCH_DRAFT_STANCE_AUTHORIZATION_REVISION = (
    "chalxius-research-draft-major-revision-authorization-1"
)
PROFILE_CLOSURE_REVISION = "chalxius-research-draft-profile-closure-1"
MATHEMATICAL_TARGET_POLICY_REVISION = "chalxius-mathematical-target-policy-1"
MATHEMATICAL_REFINEMENT_DAG_REVISION = "chalxius-mathematical-refinement-dag-1"
PLAN_ID_RE = re.compile(r"rdp-[0-9a-f]{64}")
BATCH_ID_RE = re.compile(r"rdb-[0-9a-f]{64}")
AUTHORIZATION_ID_RE = re.compile(r"rda-[0-9a-f]{64}")
LOCAL_ID_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.:-]{0,191}")
SENSE_ID_RE = re.compile(r"sense-[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
STANCE_POLICIES = frozenset(
    {"steelman_headline", "preserve_declared_stance", "allow_major_revision"}
)
NODE_DISPOSITIONS = frozenset(
    {"retained", "repaired", "replaced", "rejected", "out_of_scope"}
)
MAPPING_RELATIONS = frozenset(
    {
        "directly_reconstructs",
        "repairs",
        "splits_into",
        "supported_through_predecessor",
        "source_grounded",
        "weakened_from",
        "special_case_of",
        "strengthens_toward",
        "counterexample_candidate_for",
        "obstruction_to",
    }
)
STANCE_IMPACTS = frozenset(
    {
        "preserves_headline",
        "strengthens_headline",
        "narrows_headline",
        "reverses_headline",
        "withdraws_headline",
        "not_headline",
    }
)
MAJOR_STANCE_EFFECTS = {
    "narrows_headline": "narrow_headline",
    "reverses_headline": "reverse_headline",
    "withdraws_headline": "withdraw_headline",
}

MATHEMATICAL_EXACT_OUTCOMES = frozenset(
    {"proved", "disproved", "unresolved_with_obstruction"}
)
MATHEMATICAL_REFINEMENT_TYPES = frozenset(
    {
        "weaker_theorem",
        "stronger_theorem",
        "special_case",
        "added_hypothesis_theorem",
        "weakened_conclusion_theorem",
        "counterexample",
        "obstruction",
    }
)
MATHEMATICAL_REFINEMENT_RELATIONS = {
    "weaker_theorem": ("logically_weaker_than_original", "weakened_from"),
    "stronger_theorem": ("logically_stronger_than_original", "strengthens_toward"),
    "special_case": ("special_case_of_original", "special_case_of"),
    "added_hypothesis_theorem": (
        "stronger_hypotheses_than_original",
        "weakened_from",
    ),
    "weakened_conclusion_theorem": (
        "weaker_conclusion_than_original",
        "weakened_from",
    ),
    "counterexample": (
        "counterexample_candidate_for_original",
        "counterexample_candidate_for",
    ),
    "obstruction": ("obstructs_resolution_of_original", "obstruction_to"),
}
MATHEMATICAL_DELTA_TYPES = {
    "hypothesis": frozenset({"added", "removed", "weakened", "strengthened", "changed"}),
    "domain": frozenset({"restricted", "expanded", "changed"}),
    "quantifier": frozenset({"weakened", "strengthened", "reordered", "changed"}),
    "conclusion_strength": frozenset({"weakened", "strengthened", "changed"}),
}
DOMAIN_TARGET_ADAPTERS = {
    "empirical": "empirical_target",
    "mixed": "mixed_target",
}

PROFILE_OBLIGATIONS = {
    "philosophy": (
        "claim",
        "normative_bridge",
        "objection",
        "defeater",
        "authority_route",
        "scope",
        "failure_surface",
    ),
    "mathematics": (
        "definition",
        "hypothesis",
        "lemma",
        "proof_obligation",
        "case_split",
        "transport",
        "counterexample",
        "conclusion",
    ),
    "empirical": (
        "hypothesis",
        "design",
        "method",
        "measurement",
        "data_lineage",
        "uncertainty",
        "causal_identification",
        "transport",
        "limitations",
    ),
}


def _nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def _text(value: Any, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text")
    result = _nfc(value).strip()
    if not allow_empty and not result:
        raise ValueError(f"{label} must be nonempty")
    return result


def _strings(value: Any, label: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{label} must be a list of strings")
    result = [_text(item, label) for item in value]
    if nonempty and not result:
        raise ValueError(f"{label} must be nonempty")
    if len(result) != len(set(result)):
        raise ValueError(f"{label} must not contain duplicates")
    return sorted(result)


def _exact(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{label} fields are not exact")
    return value


def _term_key(term: str) -> str:
    return " ".join(_nfc(term).casefold().split())


def validate_term_registry(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise ValueError("research-draft term registry must be a list")
    result: list[dict[str, str]] = []
    seen_pairs: set[tuple[str, str]] = set()
    sense_definitions: dict[str, str] = {}
    for index, item in enumerate(value, 1):
        _exact(
            item,
            {"term", "sense_id", "exact_definition", "necessity"},
            f"research-draft term registry item {index}",
        )
        term = _text(item["term"], "research-draft term")
        sense_id = _text(item["sense_id"], "research-draft sense id")
        if SENSE_ID_RE.fullmatch(sense_id) is None:
            raise ValueError("research-draft sense id is invalid")
        definition = _text(item["exact_definition"], "research-draft exact definition")
        necessity = _text(item["necessity"], "research-draft term necessity")
        pair = (_term_key(term), sense_id)
        if pair in seen_pairs:
            raise ValueError("research-draft term/sense pair is duplicated")
        seen_pairs.add(pair)
        previous = sense_definitions.get(sense_id)
        if previous is not None and previous != definition:
            raise ValueError("one research-draft sense has conflicting exact definitions")
        sense_definitions[sense_id] = definition
        result.append(
            {
                "term": term,
                "sense_id": sense_id,
                "exact_definition": definition,
                "necessity": necessity,
            }
        )
    return sorted(result, key=lambda item: (_term_key(item["term"]), item["sense_id"]))


def failure_surface_uid(surface: dict[str, Any]) -> str:
    semantic = {
        key: surface[key]
        for key in (
            "target_node_id",
            "surface_id",
            "component_id",
            "statement",
            "statement_sha256",
            "trigger",
            "modality",
            "quantifier",
            "applicability_scope",
            "negates_exact_conclusion",
        )
    }
    return "rdfs-" + sha256_json(semantic)


def _profile_obligations(domain_profile: str) -> list[str]:
    if domain_profile == "mixed":
        return sorted(
            {
                item
                for profile in ("philosophy", "mathematics", "empirical")
                for item in PROFILE_OBLIGATIONS[profile]
            }
        )
    if domain_profile not in PROFILE_OBLIGATIONS:
        raise ValueError("research-draft domain profile is unsupported")
    return list(PROFILE_OBLIGATIONS[domain_profile])


def _hash_bound_text(value: Any, digest: Any, label: str, *, allow_empty: bool = False) -> str:
    normalized = _text(value, label, allow_empty=allow_empty)
    if not isinstance(digest, str) or SHA256_RE.fullmatch(digest) is None:
        raise ValueError(f"{label} SHA-256 is invalid")
    if digest != sha256_bytes(normalized.encode("utf-8")):
        raise ValueError(f"{label} SHA-256 drifted")
    return normalized


def _domain_binding(value: Any, *, available_claim_ids: set[str]) -> dict[str, Any]:
    value = _exact(
        value,
        {
            "binding_id",
            "exact_domain",
            "exact_domain_sha256",
            "source_claim_ids",
        },
        "mathematical domain binding",
    )
    binding_id = _text(value["binding_id"], "mathematical domain binding id")
    source_claim_ids = _strings(
        value["source_claim_ids"],
        "mathematical domain source claim ids",
        nonempty=True,
    )
    if not set(source_claim_ids).issubset(available_claim_ids):
        raise ValueError("mathematical domain binding escapes the Paper closure")
    exact_domain = _hash_bound_text(
        value["exact_domain"],
        value["exact_domain_sha256"],
        "mathematical exact domain",
    )
    return {
        "binding_id": binding_id,
        "exact_domain": exact_domain,
        "exact_domain_sha256": value["exact_domain_sha256"],
        "source_claim_ids": source_claim_ids,
    }


def _quantifier_binding(value: Any, *, available_claim_ids: set[str]) -> dict[str, Any]:
    value = _exact(
        value,
        {
            "binding_id",
            "exact_quantifier",
            "exact_scope",
            "binding_sha256",
            "source_claim_ids",
        },
        "mathematical quantifier binding",
    )
    binding_id = _text(value["binding_id"], "mathematical quantifier binding id")
    exact_quantifier = _text(
        value["exact_quantifier"], "mathematical exact quantifier"
    )
    exact_scope = _text(value["exact_scope"], "mathematical quantifier scope")
    source_claim_ids = _strings(
        value["source_claim_ids"],
        "mathematical quantifier source claim ids",
        nonempty=True,
    )
    if not set(source_claim_ids).issubset(available_claim_ids):
        raise ValueError("mathematical quantifier binding escapes the Paper closure")
    semantic = {
        "binding_id": binding_id,
        "exact_quantifier": exact_quantifier,
        "exact_scope": exact_scope,
        "source_claim_ids": source_claim_ids,
    }
    if value["binding_sha256"] != sha256_json(semantic):
        raise ValueError("mathematical quantifier binding hash drifted")
    return {**semantic, "binding_sha256": value["binding_sha256"]}


def validate_mathematical_target_policy(
    value: Any,
    *,
    available_claim_ids: set[str],
    exact_target_claim_ids: set[str],
) -> dict[str, Any]:
    """Validate an immutable mathematical root target without presuming truth."""

    value = _exact(
        value,
        {
            "contract_revision",
            "exact_target_statement",
            "exact_target_statement_sha256",
            "target_claim_ids",
            "hypothesis_claim_ids",
            "domain_bindings",
            "quantifier_bindings",
            "permitted_exact_target_outcomes",
            "target_revision_requires_operator_authorization",
            "partial_progress_policy",
        },
        "mathematical target policy",
    )
    if value["contract_revision"] != MATHEMATICAL_TARGET_POLICY_REVISION:
        raise ValueError("mathematical target policy revision is invalid")
    target_claim_ids = _strings(
        value["target_claim_ids"], "mathematical exact target claim ids", nonempty=True
    )
    if set(target_claim_ids) != exact_target_claim_ids:
        raise ValueError("mathematical target policy does not bind the exact Paper targets")
    hypothesis_claim_ids = _strings(
        value["hypothesis_claim_ids"], "mathematical hypothesis claim ids"
    )
    if not set(hypothesis_claim_ids).issubset(available_claim_ids):
        raise ValueError("mathematical hypothesis binding escapes the Paper closure")
    exact_target = _hash_bound_text(
        value["exact_target_statement"],
        value["exact_target_statement_sha256"],
        "mathematical exact target statement",
    )
    raw_domains = value["domain_bindings"]
    if not isinstance(raw_domains, list) or not raw_domains:
        raise ValueError("mathematical target requires at least one exact domain binding")
    domains = [
        _domain_binding(item, available_claim_ids=available_claim_ids)
        for item in raw_domains
    ]
    raw_quantifiers = value["quantifier_bindings"]
    if not isinstance(raw_quantifiers, list):
        raise ValueError("mathematical quantifier bindings must be a list")
    quantifiers = [
        _quantifier_binding(item, available_claim_ids=available_claim_ids)
        for item in raw_quantifiers
    ]
    for label, rows in (("domain", domains), ("quantifier", quantifiers)):
        ids = [item["binding_id"] for item in rows]
        if len(ids) != len(set(ids)):
            raise ValueError(f"mathematical {label} binding id is duplicated")
    outcomes = _strings(
        value["permitted_exact_target_outcomes"],
        "mathematical exact target outcomes",
        nonempty=True,
    )
    if set(outcomes) != MATHEMATICAL_EXACT_OUTCOMES:
        raise ValueError("mathematical exact target outcome policy drifted")
    if value["target_revision_requires_operator_authorization"] is not True:
        raise ValueError("mathematical exact target substitution must require Operator authorization")
    if value["partial_progress_policy"] != "typed_refinement_dag_keeps_exact_target_open":
        raise ValueError("mathematical partial-progress policy is invalid")
    return {
        "contract_revision": MATHEMATICAL_TARGET_POLICY_REVISION,
        "exact_target_statement": exact_target,
        "exact_target_statement_sha256": value["exact_target_statement_sha256"],
        "target_claim_ids": target_claim_ids,
        "hypothesis_claim_ids": hypothesis_claim_ids,
        "domain_bindings": sorted(domains, key=lambda item: item["binding_id"]),
        "quantifier_bindings": sorted(
            quantifiers, key=lambda item: item["binding_id"]
        ),
        "permitted_exact_target_outcomes": sorted(outcomes),
        "target_revision_requires_operator_authorization": True,
        "partial_progress_policy": "typed_refinement_dag_keeps_exact_target_open",
    }


def _mathematical_delta(value: Any, *, dimension: str) -> dict[str, Any]:
    value = _exact(
        value,
        {
            "dimension",
            "binding_id",
            "before",
            "before_sha256",
            "after",
            "after_sha256",
            "change_type",
            "rationale",
        },
        f"mathematical {dimension} delta",
    )
    if value["dimension"] != dimension:
        raise ValueError("mathematical refinement delta dimension drifted")
    before = _hash_bound_text(
        value["before"], value["before_sha256"], f"mathematical {dimension} before", allow_empty=True
    )
    after = _hash_bound_text(
        value["after"], value["after_sha256"], f"mathematical {dimension} after", allow_empty=True
    )
    if before == after:
        raise ValueError("mathematical refinement delta must change an exact value")
    change_type = value["change_type"]
    if change_type not in MATHEMATICAL_DELTA_TYPES[dimension]:
        raise ValueError("mathematical refinement delta type is invalid")
    return {
        "dimension": dimension,
        "binding_id": _text(value["binding_id"], f"mathematical {dimension} binding id"),
        "before": before,
        "before_sha256": value["before_sha256"],
        "after": after,
        "after_sha256": value["after_sha256"],
        "change_type": change_type,
        "rationale": _text(value["rationale"], f"mathematical {dimension} delta rationale"),
    }


def validate_mathematical_refinement_dag(
    value: Any,
    *,
    target_policy: dict[str, Any],
) -> dict[str, Any]:
    """Validate typed partial progress while keeping the exact root explicit."""

    base_fields = {
        "schema_version",
        "contract_revision",
        "root_target",
        "nodes",
        "edges",
        "topological_order",
        "truth_effect",
    }
    normalized_fields = base_fields | {
        "progress_class",
        "refinement_dag_sha256",
    }
    if not isinstance(value, dict):
        raise ValueError("mathematical refinement DAG must be an object")
    if frozenset(value) not in {frozenset(base_fields), frozenset(normalized_fields)}:
        raise ValueError(
            "mathematical refinement DAG fields are not exact for either "
            "producer input or normalized stored state"
        )
    supplied_progress_class = value.get("progress_class")
    supplied_refinement_dag_sha256 = value.get("refinement_dag_sha256")
    value = _exact(
        {field: value[field] for field in base_fields},
        base_fields,
        "mathematical refinement DAG",
    )
    if (
        value["schema_version"] != 1
        or value["contract_revision"] != MATHEMATICAL_REFINEMENT_DAG_REVISION
        or value["truth_effect"] != "none"
    ):
        raise ValueError("mathematical refinement DAG contract binding is invalid")
    root = _exact(
        value["root_target"],
        {
            "root_id",
            "exact_target_statement_sha256",
            "target_claim_ids",
            "hypothesis_claim_ids",
            "domain_bindings_sha256",
            "quantifier_bindings_sha256",
            "resolution_status",
            "resolution_evidence_ids",
            "obstruction",
            "original_target_open",
        },
        "mathematical exact target root",
    )
    if root["root_id"] != "exact-target-root":
        raise ValueError("mathematical refinement DAG root id is invalid")
    if (
        root["exact_target_statement_sha256"]
        != target_policy["exact_target_statement_sha256"]
        or _strings(root["target_claim_ids"], "mathematical root target ids", nonempty=True)
        != target_policy["target_claim_ids"]
        or _strings(root["hypothesis_claim_ids"], "mathematical root hypothesis ids")
        != target_policy["hypothesis_claim_ids"]
        or root["domain_bindings_sha256"] != sha256_json(target_policy["domain_bindings"])
        or root["quantifier_bindings_sha256"]
        != sha256_json(target_policy["quantifier_bindings"])
    ):
        raise ValueError("mathematical refinement root drifts from the immutable exact target")
    root_status = root["resolution_status"]
    if root_status not in MATHEMATICAL_EXACT_OUTCOMES:
        raise ValueError("mathematical exact target resolution status is invalid")
    root_evidence = _strings(
        root["resolution_evidence_ids"], "mathematical exact target evidence ids"
    )
    obstruction = _text(
        root["obstruction"], "mathematical exact target obstruction", allow_empty=True
    )
    root_open = root["original_target_open"]
    if root_status in {"proved", "disproved"}:
        if not root_evidence or obstruction or root_open is not False:
            raise ValueError("only an evidenced exact proof or disproof may close the mathematical target")
    elif not obstruction or root_open is not True:
        raise ValueError("an unresolved mathematical target must stay open with an exact obstruction")

    raw_nodes = value["nodes"]
    if not isinstance(raw_nodes, list):
        raise ValueError("mathematical refinement nodes must be a list")
    nodes: list[dict[str, Any]] = []
    node_ids: set[str] = set()
    candidate_fact_ids: set[str] = set()
    for raw in raw_nodes:
        raw = _exact(
            raw,
            {
                "node_id",
                "node_type",
                "statement",
                "statement_sha256",
                "resolution_status",
                "evidence_ids",
                "obstruction",
                "logical_relation_to_original",
                "refinement_mapping_relation",
                "candidate_fact_id_or_null",
                "hypothesis_deltas",
                "domain_deltas",
                "quantifier_deltas",
                "conclusion_strength_deltas",
                "remaining_gap_to_exact_target",
                "truth_effect",
            },
            "mathematical refinement node",
        )
        node_id = _text(raw["node_id"], "mathematical refinement node id")
        if LOCAL_ID_RE.fullmatch(node_id) is None or node_id == "exact-target-root" or node_id in node_ids:
            raise ValueError("mathematical refinement node id is invalid or duplicated")
        node_ids.add(node_id)
        node_type = raw["node_type"]
        if node_type not in MATHEMATICAL_REFINEMENT_TYPES:
            raise ValueError("mathematical refinement node type is invalid")
        expected_logical, expected_mapping = MATHEMATICAL_REFINEMENT_RELATIONS[node_type]
        if (
            raw["logical_relation_to_original"] != expected_logical
            or raw["refinement_mapping_relation"] != expected_mapping
        ):
            raise ValueError("mathematical refinement relation/type pairing drifted")
        statement = _hash_bound_text(
            raw["statement"], raw["statement_sha256"], "mathematical refinement statement"
        )
        resolution_status = raw["resolution_status"]
        if resolution_status not in MATHEMATICAL_EXACT_OUTCOMES:
            raise ValueError("mathematical refinement resolution status is invalid")
        evidence_ids = _strings(raw["evidence_ids"], "mathematical refinement evidence ids")
        node_obstruction = _text(
            raw["obstruction"], "mathematical refinement obstruction", allow_empty=True
        )
        candidate_fact_id = raw["candidate_fact_id_or_null"]
        if candidate_fact_id is not None:
            if not isinstance(candidate_fact_id, str) or re.fullmatch(r"[0-9a-f]{16}", candidate_fact_id) is None:
                raise ValueError("mathematical refinement Candidate Fact id is invalid")
            if candidate_fact_id in candidate_fact_ids:
                raise ValueError("mathematical refinement Candidate Fact id is duplicated")
            candidate_fact_ids.add(candidate_fact_id)
        if resolution_status in {"proved", "disproved"}:
            if not evidence_ids or node_obstruction or candidate_fact_id is None:
                raise ValueError("verified mathematical refinement requires evidence and an exact Candidate Fact id")
        elif not node_obstruction:
            raise ValueError("unresolved mathematical refinement requires an obstruction")
        if node_type == "obstruction" and (
            resolution_status != "unresolved_with_obstruction" or candidate_fact_id is not None
        ):
            raise ValueError("an obstruction node cannot masquerade as a proved Candidate Fact")
        deltas: dict[str, list[dict[str, Any]]] = {}
        for dimension, field in (
            ("hypothesis", "hypothesis_deltas"),
            ("domain", "domain_deltas"),
            ("quantifier", "quantifier_deltas"),
            ("conclusion_strength", "conclusion_strength_deltas"),
        ):
            if not isinstance(raw[field], list):
                raise ValueError(f"mathematical {dimension} deltas must be a list")
            deltas[field] = [
                _mathematical_delta(item, dimension=dimension) for item in raw[field]
            ]
        delta_count = sum(len(items) for items in deltas.values())
        if node_type in {
            "weaker_theorem",
            "stronger_theorem",
            "special_case",
            "added_hypothesis_theorem",
            "weakened_conclusion_theorem",
        } and delta_count == 0:
            raise ValueError("theorem refinement must expose its exact target delta")
        if node_type == "added_hypothesis_theorem" and not any(
            item["change_type"] == "added" for item in deltas["hypothesis_deltas"]
        ):
            raise ValueError("added-hypothesis theorem lacks an added hypothesis delta")
        if node_type == "weakened_conclusion_theorem" and not any(
            item["change_type"] == "weakened"
            for item in deltas["conclusion_strength_deltas"]
        ):
            raise ValueError("weakened-conclusion theorem lacks a weakened conclusion delta")
        nodes.append(
            {
                "node_id": node_id,
                "node_type": node_type,
                "statement": statement,
                "statement_sha256": raw["statement_sha256"],
                "resolution_status": resolution_status,
                "evidence_ids": evidence_ids,
                "obstruction": node_obstruction,
                "logical_relation_to_original": expected_logical,
                "refinement_mapping_relation": expected_mapping,
                "candidate_fact_id_or_null": candidate_fact_id,
                **{
                    field: sorted(items, key=lambda item: (item["binding_id"], item["before_sha256"], item["after_sha256"]))
                    for field, items in deltas.items()
                },
                "remaining_gap_to_exact_target": _text(
                    raw["remaining_gap_to_exact_target"],
                    "mathematical refinement remaining exact-target gap",
                ),
                "truth_effect": "none",
            }
        )

    raw_edges = value["edges"]
    if not isinstance(raw_edges, list):
        raise ValueError("mathematical refinement edges must be a list")
    all_ids = {"exact-target-root", *node_ids}
    edges: list[dict[str, str]] = []
    seen_edges: set[tuple[str, str, str]] = set()
    children: dict[str, set[str]] = {item: set() for item in all_ids}
    indegree: dict[str, int] = {item: 0 for item in all_ids}
    for raw in raw_edges:
        raw = _exact(
            raw,
            {"parent_id", "child_id", "relation"},
            "mathematical refinement edge",
        )
        parent = _text(raw["parent_id"], "mathematical refinement parent")
        child = _text(raw["child_id"], "mathematical refinement child")
        relation = raw["relation"]
        if (
            parent not in all_ids
            or child not in node_ids
            or parent == child
            or relation not in {"refines_toward_exact_target", "depends_on_refinement"}
            or (parent == "exact-target-root" and relation != "refines_toward_exact_target")
            or (parent != "exact-target-root" and relation != "depends_on_refinement")
        ):
            raise ValueError("mathematical refinement edge is invalid")
        key = (parent, child, relation)
        if key in seen_edges:
            raise ValueError("mathematical refinement edge is duplicated")
        seen_edges.add(key)
        children[parent].add(child)
        indegree[child] += 1
        edges.append({"parent_id": parent, "child_id": child, "relation": relation})
    if any(indegree[node_id] == 0 for node_id in node_ids):
        raise ValueError("every mathematical refinement must descend from the exact target root")
    ready = sorted(node_id for node_id, degree in indegree.items() if degree == 0)
    canonical_order: list[str] = []
    while ready:
        current = ready.pop(0)
        canonical_order.append(current)
        for child in sorted(children[current]):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
        ready.sort()
    if len(canonical_order) != len(all_ids):
        raise ValueError("mathematical refinement DAG contains a cycle")
    declared_order = _strings(
        value["topological_order"], "mathematical refinement topological order", nonempty=True
    )
    if set(declared_order) != all_ids:
        raise ValueError("mathematical refinement topological order inventory drifted")
    positions = {node_id: index for index, node_id in enumerate(declared_order)}
    if any(positions[edge["parent_id"]] >= positions[edge["child_id"]] for edge in edges):
        raise ValueError("mathematical refinement topological order violates an edge")
    reachable = {"exact-target-root"}
    queue = ["exact-target-root"]
    while queue:
        current = queue.pop(0)
        for child in children[current]:
            if child not in reachable:
                reachable.add(child)
                queue.append(child)
    if reachable != all_ids:
        raise ValueError("mathematical refinement DAG contains an orphan node")
    normalized_root = {
        "root_id": "exact-target-root",
        "exact_target_statement_sha256": root["exact_target_statement_sha256"],
        "target_claim_ids": target_policy["target_claim_ids"],
        "hypothesis_claim_ids": target_policy["hypothesis_claim_ids"],
        "domain_bindings_sha256": root["domain_bindings_sha256"],
        "quantifier_bindings_sha256": root["quantifier_bindings_sha256"],
        "resolution_status": root_status,
        "resolution_evidence_ids": root_evidence,
        "obstruction": obstruction,
        "original_target_open": root_open,
    }
    normalized = {
        "schema_version": 1,
        "contract_revision": MATHEMATICAL_REFINEMENT_DAG_REVISION,
        "root_target": normalized_root,
        "nodes": sorted(nodes, key=lambda item: item["node_id"]),
        "edges": sorted(edges, key=lambda item: (item["parent_id"], item["child_id"], item["relation"])),
        "topological_order": declared_order,
        "truth_effect": "none",
    }
    verified_partial = any(
        item["resolution_status"] in {"proved", "disproved"} for item in nodes
    )
    result = {
        **normalized,
        "progress_class": (
            "exact_target_resolved"
            if not root_open
            else "partial_verified_progress"
            if verified_partial
            else "unresolved_with_obstruction"
        ),
        "refinement_dag_sha256": sha256_json(normalized),
    }
    if supplied_progress_class is not None and (
        supplied_progress_class != result["progress_class"]
        or supplied_refinement_dag_sha256 != result["refinement_dag_sha256"]
    ):
        raise ValueError("normalized mathematical refinement DAG summary drifted")
    return result


class ResearchDraftManager:
    def __init__(self, lifecycle: Any) -> None:
        self.lifecycle = lifecycle
        self.store = lifecycle.store
        self.root = lifecycle.root / "research-draft-admission"
        self.plans_dir = self.root / "plans" / "by-id"
        self.authorizations_dir = self.root / "stance-authorizations" / "by-id"
        self.batches_dir = self.root / "disposition-batches" / "by-id"
        self.heads_dir = self.root / "disposition-heads"

    def initialize(self) -> None:
        for path in (
            self.plans_dir,
            self.authorizations_dir,
            self.batches_dir,
            self.heads_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def _plan_path(self, plan_id: str) -> Path:
        if PLAN_ID_RE.fullmatch(plan_id) is None:
            raise ValueError("research-draft plan id is invalid")
        return self.plans_dir / f"{plan_id}.json"

    def _batch_dir(self, batch_id: str) -> Path:
        if BATCH_ID_RE.fullmatch(batch_id) is None:
            raise ValueError("research-draft batch id is invalid")
        return self.batches_dir / batch_id

    def _authorization_path(self, decision_id: str) -> Path:
        if AUTHORIZATION_ID_RE.fullmatch(decision_id) is None:
            raise ValueError("research-draft authorization id is invalid")
        return self.authorizations_dir / f"{decision_id}.json"

    def _head_path(self, plan_id: str) -> Path:
        if PLAN_ID_RE.fullmatch(plan_id) is None:
            raise ValueError("research-draft plan id is invalid")
        return self.heads_dir / f"{plan_id}.json"

    @staticmethod
    def _source_role(manifest: dict[str, Any]) -> str:
        role = manifest.get("source_role")
        if role != "research_draft":
            if role in {"external_reference", "external_finished_publication"}:
                raise ValueError(
                    "an external finished publication belongs to Evidence, not the research-draft lifecycle"
                )
            raise ValueError("research-draft intake requires explicit source_role=research_draft")
        return role

    @staticmethod
    def _stance_policy(plan: dict[str, Any]) -> dict[str, Any]:
        if plan.get("contract_revision") == RESEARCH_DRAFT_PLAN_REVISION and plan.get(
            "domain_profile"
        ) != "philosophy":
            raise ValueError("stance preservation is available only for philosophy")
        stance = plan.get("stance_policy")
        if not isinstance(stance, dict):
            raise ValueError("research-draft plan has no philosophical stance policy")
        return stance

    @staticmethod
    def _canonical_mathematical_target_claim_ids(
        *,
        nodes: dict[str, dict[str, Any]],
        edges: dict[str, dict[str, Any]],
        target_ids: list[str],
    ) -> tuple[set[str], set[str]]:
        """Resolve Paper targets through canonical frozen graph edges."""

        available_claim_ids = {
            object_id
            for object_id, node in nodes.items()
            if node["object_type"] == "claim"
        }
        target_claim_edges = {
            target_id: sorted(
                edge["target_id"]
                for edge in edges.values()
                if edge["relation_type"] == "targets"
                and edge["source_id"] == target_id
                and edge["target_id"] in available_claim_ids
            )
            for target_id in target_ids
        }
        if any(len(claim_ids) != 1 for claim_ids in target_claim_edges.values()):
            raise ValueError(
                "mathematical Paper target must resolve through exactly one "
                "canonical targets edge"
            )
        return available_claim_ids, {
            claim_ids[0] for claim_ids in target_claim_edges.values()
        }

    def create_plan(
        self,
        snapshot_id: str,
        payload: dict[str, Any],
        *,
        actor: str,
    ) -> dict[str, Any]:
        actor = _text(actor, "research-draft plan actor")
        if PAPER_SNAPSHOT_ID_RE.fullmatch(snapshot_id) is None:
            raise ValueError("research-draft snapshot id is invalid")
        paper = self.store.paper_logic()
        if snapshot_id not in set(paper.status()["current_snapshot_ids"]):
            raise ValueError("research-draft plan requires a current Paper Logic snapshot")
        manifest = paper.snapshot_manifest(snapshot_id)
        if manifest["graph_kind"] != "logic":
            raise ValueError("research-draft plan requires a Logic snapshot")
        source_role = self._source_role(manifest)
        domain_profile = manifest["domain_profile"]
        if domain_profile == "philosophy":
            policy_field = "stance_policy"
        elif domain_profile == "mathematics":
            policy_field = "mathematical_target_policy"
        elif domain_profile in DOMAIN_TARGET_ADAPTERS:
            policy_field = "domain_target_policy"
        else:
            raise ValueError("research-draft domain profile is unsupported")
        _exact(
            payload,
            {
                "objective",
                "source_artifact_sha256",
                policy_field,
                "term_registry",
            },
            "research-draft plan input",
        )
        nodes, edges = paper.snapshot_objects(snapshot_id)
        targets = sorted(
            object_id
            for object_id, node in nodes.items()
            if node["object_type"] == "paper_target"
        )
        if not targets:
            raise ValueError("research-draft Paper Graph has zero targets")
        work_units = [
            PaperContinuationManager._target_closure(
                target_id=target_id, nodes=nodes, edges=edges
            )
            for target_id in targets
        ]
        normalized_policy: dict[str, Any]
        if domain_profile == "philosophy":
            stance = _exact(
                payload["stance_policy"],
                {
                    "policy",
                    "headline_target_ids",
                    "declared_stance",
                    "major_revision_requires_operator_authorization",
                },
                "research-draft stance policy",
            )
            policy = stance["policy"]
            if policy not in STANCE_POLICIES:
                raise ValueError("research-draft stance policy is invalid")
            headline_ids = _strings(
                stance["headline_target_ids"],
                "research-draft headline targets",
                nonempty=True,
            )
            if not set(headline_ids).issubset(targets):
                raise ValueError("research-draft headline target is outside the Paper Graph")
            if stance["major_revision_requires_operator_authorization"] is not True:
                raise ValueError("research-draft major stance revision must require Operator authorization")
            normalized_policy = {
                "policy": policy,
                "headline_target_ids": headline_ids,
                "declared_stance": _text(
                    stance["declared_stance"], "research-draft declared stance"
                ),
                "major_revision_requires_operator_authorization": True,
            }
        elif domain_profile == "mathematics":
            available_claim_ids, exact_target_claim_ids = (
                self._canonical_mathematical_target_claim_ids(
                    nodes=nodes,
                    edges=edges,
                    target_ids=targets,
                )
            )
            normalized_policy = validate_mathematical_target_policy(
                payload["mathematical_target_policy"],
                available_claim_ids=available_claim_ids,
                exact_target_claim_ids=exact_target_claim_ids,
            )
        else:
            policy = _exact(
                payload["domain_target_policy"],
                {
                    "adapter",
                    "declared_target",
                    "target_node_ids",
                    "domain_invariants",
                    "target_revision_requires_operator_authorization",
                },
                "research-draft domain target policy",
            )
            if policy["adapter"] != DOMAIN_TARGET_ADAPTERS[domain_profile]:
                raise ValueError("research-draft domain target adapter/profile drifted")
            policy_targets = _strings(
                policy["target_node_ids"], "research-draft domain target ids", nonempty=True
            )
            if set(policy_targets) != set(targets):
                raise ValueError("research-draft domain policy does not bind every Paper target")
            if not isinstance(policy["domain_invariants"], dict) or not policy["domain_invariants"]:
                raise ValueError("research-draft domain invariants must be a nonempty object")
            if policy["target_revision_requires_operator_authorization"] is not True:
                raise ValueError("research-draft target revision must require Operator authorization")
            normalized_policy = {
                "adapter": policy["adapter"],
                "declared_target": _text(
                    policy["declared_target"], "research-draft declared domain target"
                ),
                "target_node_ids": policy_targets,
                "domain_invariants": policy["domain_invariants"],
                "target_revision_requires_operator_authorization": True,
            }
        term_registry = validate_term_registry(payload["term_registry"])
        source_artifacts = {
            item["artifact_sha256"]: item["artifact_relpath"]
            for item in manifest["source_artifacts"]
        }
        requested_source = _text(
            payload["source_artifact_sha256"],
            "research-draft source artifact SHA-256",
            allow_empty=True,
        )
        if requested_source:
            if requested_source not in source_artifacts:
                raise ValueError("research-draft source artifact is absent from the snapshot")
            source_sha256 = requested_source
        elif len(source_artifacts) == 1:
            source_sha256 = next(iter(source_artifacts))
        else:
            raise ValueError("research-draft source artifact must be selected explicitly")
        snapshot_dir = paper.snapshots_dir / snapshot_id
        snapshot_files = {
            name: sha256_bytes((snapshot_dir / name).read_bytes())
            for name in ("manifest.json", "nodes.jsonl", "edges.jsonl")
        }
        semantic = {
            "schema_version": 1,
            "contract_revision": RESEARCH_DRAFT_PLAN_REVISION,
            "project_id": self.store.project_id(),
            "paper_id": manifest["paper_id"],
            "snapshot_id": snapshot_id,
            "snapshot_file_sha256": snapshot_files,
            "source_role": source_role,
            "source_artifact_sha256": source_sha256,
            "source_artifact_relpath": source_artifacts[source_sha256],
            "domain_profile": domain_profile,
            "profile_closure_revision": PROFILE_CLOSURE_REVISION,
            "required_profile_obligations": _profile_obligations(
                manifest["domain_profile"]
            ),
            "target_node_ids": targets,
            "work_units": work_units,
            "selected_reconstruction_node_ids": sorted(
                {
                    object_id
                    for unit in work_units
                    for object_id in unit["reconstruction_node_ids"]
                }
            ),
            "selected_source_node_ids": sorted(
                {
                    object_id
                    for unit in work_units
                    for object_id in unit["source_node_ids"]
                }
            ),
            "selected_edge_ids": sorted(
                {edge_id for unit in work_units for edge_id in unit["edge_ids"]}
            ),
            "objective": _text(payload["objective"], "research-draft objective"),
            policy_field: normalized_policy,
            "term_registry": term_registry,
            "auto_topology_effect": "none",
            "created_by": actor,
            "truth_effect": "none",
        }
        plan_id = "rdp-" + sha256_json(semantic)
        record = {
            **semantic,
            "plan_id": plan_id,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        }
        record["record_sha256"] = sha256_json(record)
        with self.store.v5_mutation_lock(command="research-draft-plan"):
            self.initialize()
            path = self._plan_path(plan_id)
            if path.exists():
                return self.plan(plan_id, deep=True)
            self.store._write_json_once(path, record)
        return record

    def plan(self, plan_id: str, *, deep: bool = False) -> dict[str, Any]:
        path = self._plan_path(plan_id)
        if path.is_symlink() or not path.is_file():
            raise KeyError(f"unknown research-draft plan: {plan_id}")
        record = self.store._read_json(path)
        common_fields = {
            "schema_version",
            "contract_revision",
            "project_id",
            "paper_id",
            "snapshot_id",
            "snapshot_file_sha256",
            "source_role",
            "source_artifact_sha256",
            "source_artifact_relpath",
            "domain_profile",
            "profile_closure_revision",
            "required_profile_obligations",
            "target_node_ids",
            "work_units",
            "selected_reconstruction_node_ids",
            "selected_source_node_ids",
            "selected_edge_ids",
            "objective",
            "term_registry",
            "auto_topology_effect",
            "created_by",
            "truth_effect",
            "plan_id",
            "created_at",
            "record_sha256",
        }
        revision = record.get("contract_revision")
        if revision == LEGACY_RESEARCH_DRAFT_PLAN_REVISION:
            fields = {*common_fields, "stance_policy"}
        elif revision == RESEARCH_DRAFT_PLAN_REVISION:
            profile = record.get("domain_profile")
            if profile == "philosophy":
                fields = {*common_fields, "stance_policy"}
            elif profile == "mathematics":
                fields = {*common_fields, "mathematical_target_policy"}
            elif profile in DOMAIN_TARGET_ADAPTERS:
                fields = {*common_fields, "domain_target_policy"}
            else:
                raise ValueError("research-draft plan domain profile is unsupported")
        else:
            raise ValueError("research-draft plan revision is unsupported")
        _exact(record, fields, "research-draft plan")
        if (
            record["schema_version"] != 1
            or record["project_id"] != self.store.project_id()
            or record["source_role"] != "research_draft"
            or record["truth_effect"] != "none"
            or record["auto_topology_effect"] != "none"
            or path.stem != plan_id
        ):
            raise ValueError("research-draft plan contract binding is invalid")
        semantic = {
            key: value
            for key, value in record.items()
            if key not in {"plan_id", "created_at", "record_sha256"}
        }
        if record["plan_id"] != "rdp-" + sha256_json(semantic):
            raise ValueError("research-draft plan content id mismatch")
        without_hash = {key: value for key, value in record.items() if key != "record_sha256"}
        if record["record_sha256"] != sha256_json(without_hash):
            raise ValueError("research-draft plan record hash mismatch")
        if validate_term_registry(record["term_registry"]) != record["term_registry"]:
            raise ValueError("research-draft term registry normalization drifted")
        if revision == RESEARCH_DRAFT_PLAN_REVISION and record["domain_profile"] == "philosophy":
            stance = _exact(
                record["stance_policy"],
                {
                    "policy",
                    "headline_target_ids",
                    "declared_stance",
                    "major_revision_requires_operator_authorization",
                },
                "research-draft stance policy",
            )
            if (
                stance["policy"] not in STANCE_POLICIES
                or stance["major_revision_requires_operator_authorization"] is not True
                or _strings(
                    stance["headline_target_ids"],
                    "research-draft headline targets",
                    nonempty=True,
                )
                != stance["headline_target_ids"]
            ):
                raise ValueError("research-draft stance policy normalization drifted")
            _text(stance["declared_stance"], "research-draft declared stance")
        elif revision == RESEARCH_DRAFT_PLAN_REVISION and record["domain_profile"] in DOMAIN_TARGET_ADAPTERS:
            policy = record["domain_target_policy"]
            if (
                not isinstance(policy, dict)
                or policy.get("adapter")
                != DOMAIN_TARGET_ADAPTERS[record["domain_profile"]]
            ):
                raise ValueError("research-draft domain target policy drifted")
        if deep:
            paper = self.store.paper_logic()
            if record["snapshot_id"] not in set(paper.status()["current_snapshot_ids"]):
                raise ValueError("research-draft plan Paper snapshot is stale")
            snapshot_dir = paper.snapshots_dir / record["snapshot_id"]
            observed = {
                name: sha256_bytes((snapshot_dir / name).read_bytes())
                for name in ("manifest.json", "nodes.jsonl", "edges.jsonl")
            }
            if observed != record["snapshot_file_sha256"]:
                raise ValueError("research-draft plan snapshot bytes drifted")
            if revision == RESEARCH_DRAFT_PLAN_REVISION and record["domain_profile"] == "mathematics":
                nodes, edges = paper.snapshot_objects(record["snapshot_id"])
                available_claim_ids, exact_target_claim_ids = (
                    self._canonical_mathematical_target_claim_ids(
                        nodes=nodes,
                        edges=edges,
                        target_ids=record["target_node_ids"],
                    )
                )
                if validate_mathematical_target_policy(
                    record["mathematical_target_policy"],
                    available_claim_ids=available_claim_ids,
                    exact_target_claim_ids=exact_target_claim_ids,
                ) != record["mathematical_target_policy"]:
                    raise ValueError("mathematical target policy normalization drifted")
            source_path = contained_path(
                self.store.root,
                record["source_artifact_relpath"],
                "research-draft source artifact",
            )
            if (
                source_path.is_symlink()
                or not source_path.is_file()
                or sha256_bytes(source_path.read_bytes())
                != record["source_artifact_sha256"]
            ):
                raise ValueError("research-draft source artifact drifted")
        return record

    def authorize_major_revision(
        self,
        plan_id: str,
        payload: dict[str, Any],
        *,
        actor: str,
        authority_role: str,
    ) -> dict[str, Any]:
        """Record an immutable Operator decision before a major stance change."""

        _exact(
            payload,
            {"target_node_id", "authorized_stance_impact", "reason"},
            "research-draft major-revision authorization input",
        )
        actor = _text(actor, "research-draft authorization actor")
        if authority_role != "operator":
            raise PermissionError(
                "research-draft major revision authorization requires the Operator role"
            )
        plan = self.plan(plan_id, deep=True)
        stance_policy = self._stance_policy(plan)
        target_id = _text(
            payload["target_node_id"], "research-draft authorization target"
        )
        if target_id not in stance_policy["headline_target_ids"]:
            raise ValueError(
                "research-draft major revision authorization must name a headline target"
            )
        stance_impact = payload["authorized_stance_impact"]
        if stance_impact not in MAJOR_STANCE_EFFECTS:
            raise ValueError(
                "research-draft authorization must name one exact major stance impact"
            )
        semantic = {
            "schema_version": 1,
            "contract_revision": RESEARCH_DRAFT_STANCE_AUTHORIZATION_REVISION,
            "project_id": self.store.project_id(),
            "plan_id": plan_id,
            "plan_record_sha256": plan["record_sha256"],
            "target_node_id": target_id,
            "declared_stance_sha256": sha256_bytes(
                stance_policy["declared_stance"].encode("utf-8")
            ),
            "authorized_stance_impact": stance_impact,
            "authorized_effect": MAJOR_STANCE_EFFECTS[stance_impact],
            "operator_actor": actor,
            "authority_role": "operator",
            "reason": _text(
                payload["reason"], "research-draft authorization reason"
            ),
            "truth_effect": "none",
        }
        decision_id = "rda-" + sha256_json(semantic)
        without_hash = {
            **semantic,
            "decision_id": decision_id,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        }
        record = {**without_hash, "record_sha256": sha256_json(without_hash)}
        with self.store.v5_mutation_lock(
            command="research-draft-authorize-major-revision"
        ):
            self.initialize()
            path = self._authorization_path(decision_id)
            if path.exists():
                return self.authorization(decision_id, deep=True)
            self._write_json_new(path, record)
        return record

    def authorization(
        self, decision_id: str, *, deep: bool = False
    ) -> dict[str, Any]:
        path = self._authorization_path(decision_id)
        if path.is_symlink() or not path.is_file():
            raise KeyError(f"unknown research-draft authorization: {decision_id}")
        record = self.store._read_json(path)
        fields = {
            "schema_version",
            "contract_revision",
            "project_id",
            "plan_id",
            "plan_record_sha256",
            "target_node_id",
            "declared_stance_sha256",
            "authorized_stance_impact",
            "authorized_effect",
            "operator_actor",
            "authority_role",
            "reason",
            "truth_effect",
            "decision_id",
            "created_at",
            "record_sha256",
        }
        _exact(record, fields, "research-draft major-revision authorization")
        semantic = {
            key: value
            for key, value in record.items()
            if key not in {"decision_id", "created_at", "record_sha256"}
        }
        without_hash = {
            key: value for key, value in record.items() if key != "record_sha256"
        }
        impact = record["authorized_stance_impact"]
        if (
            record["schema_version"] != 1
            or record["contract_revision"]
            != RESEARCH_DRAFT_STANCE_AUTHORIZATION_REVISION
            or record["project_id"] != self.store.project_id()
            or record["authority_role"] != "operator"
            or record["truth_effect"] != "none"
            or impact not in MAJOR_STANCE_EFFECTS
            or record["authorized_effect"] != MAJOR_STANCE_EFFECTS.get(impact)
            or record["decision_id"] != "rda-" + sha256_json(semantic)
            or record["record_sha256"] != sha256_json(without_hash)
            or path.stem != decision_id
        ):
            raise ValueError("research-draft authorization binding is invalid")
        _text(record["operator_actor"], "research-draft authorization actor")
        _text(record["reason"], "research-draft authorization reason")
        if deep:
            plan = self.plan(record["plan_id"], deep=True)
            stance_policy = self._stance_policy(plan)
            if (
                record["plan_record_sha256"] != plan["record_sha256"]
                or record["target_node_id"]
                not in stance_policy["headline_target_ids"]
                or record["declared_stance_sha256"]
                != sha256_bytes(
                    stance_policy["declared_stance"].encode("utf-8")
                )
            ):
                raise ValueError("research-draft authorization plan binding drifted")
        return record

    def _authorization(
        self,
        value: Any,
        *,
        plan: dict[str, Any],
        target_id: str,
        stance_impact: str,
    ) -> dict[str, Any] | None:
        if value is None:
            return None
        _exact(
            value,
            {"decision_id", "decision_record_sha256"},
            "research-draft major-revision authorization reference",
        )
        decision_id = _text(
            value["decision_id"], "research-draft authorization decision"
        )
        record = self.authorization(decision_id, deep=True)
        if value["decision_record_sha256"] != record["record_sha256"]:
            raise ValueError("research-draft authorization record hash mismatch")
        stance_policy = self._stance_policy(plan)
        expected_declared = sha256_bytes(stance_policy["declared_stance"].encode("utf-8"))
        if (
            record["plan_id"] != plan["plan_id"]
            or record["plan_record_sha256"] != plan["record_sha256"]
            or record["target_node_id"] != target_id
            or record["declared_stance_sha256"] != expected_declared
            or record["authorized_stance_impact"] != stance_impact
            or record["authorized_effect"] != MAJOR_STANCE_EFFECTS.get(stance_impact)
        ):
            raise ValueError(
                "research-draft authorization does not match the exact plan, target, and stance impact"
            )
        return record

    def _failure_surface(
        self, value: Any, *, target_id: str
    ) -> dict[str, Any]:
        fields = {
            "surface_id",
            "surface_uid",
            "target_node_id",
            "component_id",
            "statement",
            "statement_sha256",
            "trigger",
            "modality",
            "quantifier",
            "applicability_scope",
            "negates_exact_conclusion",
            "why_sufficient",
            "resolution",
        }
        value = _exact(value, fields, "research-draft failure surface")
        if value["target_node_id"] != target_id:
            raise ValueError("research-draft failure surface crosses Paper targets")
        normalized = {
            "surface_id": _text(value["surface_id"], "failure surface local id"),
            "surface_uid": value["surface_uid"],
            "target_node_id": target_id,
            "component_id": _text(value["component_id"], "failure surface component id"),
            "statement": _text(value["statement"], "failure surface statement"),
            "statement_sha256": value["statement_sha256"],
            "trigger": _text(value["trigger"], "failure surface trigger"),
            "modality": _text(value["modality"], "failure surface modality"),
            "quantifier": _text(value["quantifier"], "failure surface quantifier"),
            "applicability_scope": _text(
                value["applicability_scope"], "failure surface applicability scope"
            ),
            "negates_exact_conclusion": value["negates_exact_conclusion"],
            "why_sufficient": _text(value["why_sufficient"], "failure surface sufficiency"),
            "resolution": _text(value["resolution"], "failure surface resolution"),
        }
        if LOCAL_ID_RE.fullmatch(normalized["surface_id"]) is None:
            raise ValueError("research-draft failure surface local id is invalid")
        if (
            not isinstance(normalized["statement_sha256"], str)
            or SHA256_RE.fullmatch(normalized["statement_sha256"]) is None
            or normalized["statement_sha256"]
            != sha256_bytes(normalized["statement"].encode("utf-8"))
        ):
            raise ValueError("research-draft failure surface statement hash mismatch")
        if normalized["negates_exact_conclusion"] is not True:
            raise ValueError("failure surface must defeat the exact scoped component")
        if normalized["surface_uid"] != failure_surface_uid(normalized):
            raise ValueError("research-draft failure surface content id mismatch")
        return normalized

    def _entry(
        self,
        value: Any,
        *,
        plan: dict[str, Any],
        research_index: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        common_fields = {
            "target_node_id",
            "node_disposition",
            "disposition_reason",
            "research_record_ids",
            "successor_mappings",
            "term_sense_refs",
            "profile_obligations",
            "failure_surfaces",
            "writing_coverage",
        }
        current_domain_adapter = (
            plan.get("contract_revision") == RESEARCH_DRAFT_PLAN_REVISION
        )
        profile = plan["domain_profile"]
        if current_domain_adapter and profile == "mathematics":
            fields = {*common_fields, "mathematical_progress"}
        elif current_domain_adapter and profile in DOMAIN_TARGET_ADAPTERS:
            fields = {*common_fields, "domain_outcome"}
        else:
            fields = {
                *common_fields,
                "stance_impact",
                "major_revision_authorization",
            }
        value = _exact(value, fields, "research-draft disposition entry")
        target_id = _text(value["target_node_id"], "research-draft target id")
        if target_id not in plan["target_node_ids"]:
            raise ValueError("research-draft disposition target is outside the plan")
        disposition = value["node_disposition"]
        if disposition not in NODE_DISPOSITIONS:
            raise ValueError("research-draft node disposition is invalid")
        research_ids = _strings(
            value["research_record_ids"], "research-draft Research record ids", nonempty=True
        )
        if not set(research_ids).issubset(research_index):
            raise ValueError("research-draft disposition names unknown Research")
        normalized_domain_outcome: dict[str, Any]
        stance_impact: str | None = None
        authorization: dict[str, Any] | None = None
        if current_domain_adapter and profile == "mathematics":
            progress = validate_mathematical_refinement_dag(
                value["mathematical_progress"],
                target_policy=plan["mathematical_target_policy"],
            )
            normalized_domain_outcome = {
                "adapter": "mathematical_target",
                "mathematical_progress": progress,
            }
        elif current_domain_adapter and profile in DOMAIN_TARGET_ADAPTERS:
            outcome = _exact(
                value["domain_outcome"],
                {"adapter", "outcome", "evidence_ids", "remaining_gap"},
                "research-draft domain outcome",
            )
            adapter = DOMAIN_TARGET_ADAPTERS[profile]
            permitted = (
                {"supported", "disconfirmed", "inconclusive"}
                if profile == "empirical"
                else {"componentwise_resolved", "partially_resolved", "unresolved"}
            )
            if outcome["adapter"] != adapter or outcome["outcome"] not in permitted:
                raise ValueError("research-draft domain outcome/adapter drifted")
            normalized_domain_outcome = {
                "adapter": adapter,
                "outcome": outcome["outcome"],
                "evidence_ids": _strings(
                    outcome["evidence_ids"], "research-draft domain outcome evidence ids"
                ),
                "remaining_gap": _text(
                    outcome["remaining_gap"],
                    "research-draft domain outcome remaining gap",
                    allow_empty=outcome["outcome"] in {"supported", "disconfirmed", "componentwise_resolved"},
                ),
            }
        else:
            stance_impact = value["stance_impact"]
            if stance_impact not in STANCE_IMPACTS:
                raise ValueError("research-draft stance impact is invalid")
            stance_policy = self._stance_policy(plan)
            headline = target_id in stance_policy["headline_target_ids"]
            authorization = self._authorization(
                value["major_revision_authorization"],
                plan=plan,
                target_id=target_id,
                stance_impact=stance_impact,
            )
            major_impact = stance_impact in MAJOR_STANCE_EFFECTS
            if headline:
                if stance_impact == "not_headline":
                    raise ValueError("research-draft headline target cannot be marked non-headline")
                if major_impact and authorization is None:
                    raise ValueError(
                        "research-draft headline narrowing/reversal requires explicit Operator authorization"
                    )
                if not major_impact and authorization is not None:
                    raise ValueError(
                        "research-draft non-major stance impact cannot consume a major-revision authorization"
                    )
            elif stance_impact != "not_headline":
                raise ValueError("non-headline target must use stance_impact=not_headline")
            elif authorization is not None:
                raise ValueError(
                    "research-draft non-headline target cannot consume a major-revision authorization"
                )
            normalized_domain_outcome = {
                "adapter": "philosophy_stance",
                "stance_impact": stance_impact,
                "major_revision_authorization": authorization,
            }
        mappings = value["successor_mappings"]
        if not isinstance(mappings, list):
            raise ValueError("research-draft successor mappings must be a list")
        normalized_mappings: list[dict[str, str]] = []
        seen_mappings: set[tuple[str, str]] = set()
        for mapping in mappings:
            _exact(
                mapping,
                {"successor_id", "relation_kind", "reason"},
                "research-draft successor mapping",
            )
            successor_id = _text(mapping["successor_id"], "research-draft successor id")
            relation = mapping["relation_kind"]
            if relation not in MAPPING_RELATIONS:
                raise ValueError("research-draft successor relation is invalid")
            key = (successor_id, relation)
            if key in seen_mappings:
                raise ValueError("research-draft successor mapping is duplicated")
            seen_mappings.add(key)
            normalized_mappings.append(
                {
                    "successor_id": successor_id,
                    "relation_kind": relation,
                    "reason": _text(mapping["reason"], "successor mapping reason"),
                }
            )
        if disposition in {"retained", "repaired", "replaced"} and not normalized_mappings:
            raise ValueError("a live research-draft target requires successor mappings")
        if current_domain_adapter and profile == "mathematics":
            progress = normalized_domain_outcome["mathematical_progress"]
            expected_progress_mappings = {
                (
                    node["candidate_fact_id_or_null"],
                    node["refinement_mapping_relation"],
                )
                for node in progress["nodes"]
                if node["candidate_fact_id_or_null"] is not None
            }
            actual_mappings = {
                (item["successor_id"], item["relation_kind"])
                for item in normalized_mappings
            }
            if not expected_progress_mappings.issubset(actual_mappings):
                raise ValueError("mathematical refinement Candidate mappings are incomplete")
            if progress["root_target"]["original_target_open"] and any(
                item["relation_kind"] in {"directly_reconstructs", "repairs"}
                for item in normalized_mappings
            ):
                raise ValueError("a weaker mathematical result cannot masquerade as the exact target")
        term_refs = _strings(value["term_sense_refs"], "research-draft term-sense refs")
        registry_senses = {item["sense_id"] for item in plan["term_registry"]}
        if not set(term_refs).issubset(registry_senses):
            raise ValueError("research-draft disposition uses an unregistered term sense")
        obligations = value["profile_obligations"]
        if not isinstance(obligations, list):
            raise ValueError("research-draft profile obligations must be a list")
        normalized_obligations: list[dict[str, Any]] = []
        seen_obligations: set[str] = set()
        for item in obligations:
            _exact(
                item,
                {"obligation_kind", "status", "evidence_ids", "reason"},
                "research-draft profile obligation",
            )
            kind = item["obligation_kind"]
            if kind not in plan["required_profile_obligations"] or kind in seen_obligations:
                raise ValueError("research-draft profile obligation is invalid or duplicated")
            seen_obligations.add(kind)
            if item["status"] not in {"satisfied", "not_applicable_with_reason"}:
                raise ValueError("research-draft profile obligation status is invalid")
            evidence_ids = _strings(
                item["evidence_ids"], "research-draft profile evidence ids"
            )
            if item["status"] == "satisfied" and not evidence_ids:
                raise ValueError("satisfied research-draft obligation requires evidence")
            normalized_obligations.append(
                {
                    "obligation_kind": kind,
                    "status": item["status"],
                    "evidence_ids": evidence_ids,
                    "reason": _text(item["reason"], "profile obligation reason"),
                }
            )
        if seen_obligations != set(plan["required_profile_obligations"]):
            raise ValueError("research-draft profile obligation coverage is incomplete")
        surfaces = [
            self._failure_surface(item, target_id=target_id)
            for item in value["failure_surfaces"]
        ] if isinstance(value["failure_surfaces"], list) else None
        if surfaces is None:
            raise ValueError("research-draft failure surfaces must be a list")
        if plan["domain_profile"] in {"philosophy", "mixed"} and not surfaces:
            raise ValueError("philosophy research-draft target requires a failure surface")
        surface_uids = [item["surface_uid"] for item in surfaces]
        if len(surface_uids) != len(set(surface_uids)):
            raise ValueError("research-draft failure surface is duplicated")
        writing = _exact(
            value["writing_coverage"],
            {"artifact_relpath", "artifact_sha256", "section_ids", "reason"},
            "research-draft writing coverage",
        )
        artifact_path = contained_path(
            self.store.root,
            _text(writing["artifact_relpath"], "research-draft writing artifact"),
            "research-draft writing artifact",
        )
        artifact_sha256 = _text(
            writing["artifact_sha256"], "research-draft writing artifact SHA-256"
        )
        if (
            artifact_path.is_symlink()
            or not artifact_path.is_file()
            or SHA256_RE.fullmatch(artifact_sha256) is None
            or sha256_bytes(artifact_path.read_bytes()) != artifact_sha256
        ):
            raise ValueError("research-draft writing artifact drifted")
        normalized_entry = {
            "target_node_id": target_id,
            "node_disposition": disposition,
            "disposition_reason": _text(
                value["disposition_reason"], "research-draft disposition reason"
            ),
            "research_record_ids": research_ids,
            "successor_mappings": sorted(
                normalized_mappings,
                key=lambda item: (item["successor_id"], item["relation_kind"]),
            ),
            "term_sense_refs": term_refs,
            "profile_obligations": sorted(
                normalized_obligations, key=lambda item: item["obligation_kind"]
            ),
            "failure_surfaces": sorted(surfaces, key=lambda item: item["surface_uid"]),
            "writing_coverage": {
                "artifact_relpath": artifact_path.relative_to(self.store.root).as_posix(),
                "artifact_sha256": artifact_sha256,
                "section_ids": _strings(
                    writing["section_ids"],
                    "research-draft writing section ids",
                    nonempty=True,
                ),
                "reason": _text(writing["reason"], "research-draft writing reason"),
            },
        }
        if current_domain_adapter and profile == "mathematics":
            normalized_entry["mathematical_progress"] = normalized_domain_outcome[
                "mathematical_progress"
            ]
        elif current_domain_adapter and profile in DOMAIN_TARGET_ADAPTERS:
            normalized_entry["domain_outcome"] = normalized_domain_outcome
        else:
            normalized_entry["stance_impact"] = stance_impact
            normalized_entry["major_revision_authorization"] = authorization
        return normalized_entry

    def record_batch(
        self,
        plan_id: str,
        payload: dict[str, Any],
        *,
        actor: str,
    ) -> dict[str, Any]:
        _exact(
            payload,
            {"supersedes_batch_id", "entries"},
            "research-draft disposition batch input",
        )
        actor = _text(actor, "research-draft batch actor")
        with self.store.v5_mutation_lock(command="research-draft-disposition-batch"):
            self.initialize()
            plan = self.plan(plan_id, deep=True)
            current = self.current_batch(plan_id)
            expected_previous = current["batch_id"] if current is not None else ""
            if payload["supersedes_batch_id"] != expected_previous:
                raise ValueError(
                    "research-draft batch must supersede the exact current batch"
                )
            # CHX-010: the immutable Research index is validated exactly once for
            # the whole batch, never once per target.
            records = self.lifecycle.research_records()
            research_index = {item["research_id"]: item for item in records}
            entries_value = payload["entries"]
            if not isinstance(entries_value, list):
                raise ValueError("research-draft batch entries must be a list")
            entries = [
                self._entry(item, plan=plan, research_index=research_index)
                for item in entries_value
            ]
            target_ids = [item["target_node_id"] for item in entries]
            if len(target_ids) != len(set(target_ids)):
                raise ValueError("research-draft batch duplicates a target")
            if set(target_ids) != set(plan["target_node_ids"]):
                raise ValueError(
                    "research-draft disposition batch must cover the complete Paper target set"
                )
            all_surface_uids = [
                surface["surface_uid"]
                for entry in entries
                for surface in entry["failure_surfaces"]
            ]
            if len(all_surface_uids) != len(set(all_surface_uids)):
                raise ValueError("research-draft batch has a cross-target surface collision")
            current_revision = plan["contract_revision"] == RESEARCH_DRAFT_PLAN_REVISION
            batch_revision = (
                RESEARCH_DRAFT_BATCH_REVISION
                if current_revision
                else LEGACY_RESEARCH_DRAFT_BATCH_REVISION
            )
            adequacy_revision = (
                RESEARCH_DRAFT_ADEQUACY_REVISION
                if current_revision
                else LEGACY_RESEARCH_DRAFT_ADEQUACY_REVISION
            )
            semantic = {
                "schema_version": 1,
                "contract_revision": batch_revision,
                "project_id": self.store.project_id(),
                "plan_id": plan_id,
                "plan_record_sha256": plan["record_sha256"],
                "supersedes_batch_id": expected_previous,
                "entries": sorted(entries, key=lambda item: item["target_node_id"]),
                "research_index_count": len(research_index),
                "research_index_semantic_sha256": sha256_json(
                    [
                        {
                            "research_id": item["research_id"],
                            "record_sha256": item["record_sha256"],
                        }
                        for item in sorted(records, key=lambda item: item["research_id"])
                    ]
                ),
                "term_registry_sha256": sha256_json(plan["term_registry"]),
                "actor": actor,
                "truth_effect": "none",
            }
            batch_id = "rdb-" + sha256_json(semantic)
            record = {
                **semantic,
                "batch_id": batch_id,
                "created_at": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
            }
            record["record_sha256"] = sha256_json(record)
            adequacy_semantic = {
                "schema_version": 1,
                "contract_revision": adequacy_revision,
                "plan_id": plan_id,
                "batch_id": batch_id,
                "target_node_ids": plan["target_node_ids"],
                "term_registry_sha256": semantic["term_registry_sha256"],
                "failure_surface_uids": sorted(all_surface_uids),
                "adequacy_complete": True,
                "truth_effect": "none",
            }
            if not current_revision or plan["domain_profile"] == "philosophy":
                stance_policy = self._stance_policy(plan)
                adequacy_semantic["headline_stance_impacts"] = {
                    item["target_node_id"]: item["stance_impact"]
                    for item in entries
                    if item["target_node_id"] in stance_policy["headline_target_ids"]
                }
            elif plan["domain_profile"] == "mathematics":
                root_bindings = {
                    sha256_json(item["mathematical_progress"]["root_target"])
                    for item in entries
                }
                if len(root_bindings) != 1:
                    raise ValueError("mathematical disposition batch has inconsistent exact target roots")
                adequacy_semantic["mathematical_target_progress"] = {
                    "target_policy_sha256": sha256_json(
                        plan["mathematical_target_policy"]
                    ),
                    "root_target_sha256": next(iter(root_bindings)),
                    "target_progress": [
                        {
                            "target_node_id": item["target_node_id"],
                            "root_resolution_status": item["mathematical_progress"][
                                "root_target"
                            ]["resolution_status"],
                            "original_target_open": item["mathematical_progress"][
                                "root_target"
                            ]["original_target_open"],
                            "progress_class": item["mathematical_progress"][
                                "progress_class"
                            ],
                            "refinement_dag_sha256": item["mathematical_progress"][
                                "refinement_dag_sha256"
                            ],
                        }
                        for item in entries
                    ],
                    "weakening_closes_exact_target": False,
                }
            else:
                adequacy_semantic["domain_target_outcomes"] = {
                    item["target_node_id"]: item["domain_outcome"] for item in entries
                }
            adequacy = {
                **adequacy_semantic,
                "adequacy_receipt_sha256": sha256_json(adequacy_semantic),
            }
            summary = {
                "schema_version": 1,
                "contract_revision": adequacy_revision,
                "plan_id": plan_id,
                "batch_id": batch_id,
                "batch_record_sha256": record["record_sha256"],
                "target_count": len(entries),
                "research_index_count": len(research_index),
                "adequacy_receipt": adequacy,
                "truth_effect": "none",
            }
            batch_dir = self._batch_dir(batch_id)
            if batch_dir.exists():
                existing = self.batch(batch_id, deep=False)
                if existing != record:
                    raise ValueError("research-draft batch id collision")
            else:
                staging = self.batches_dir / (
                    f".staging-{batch_id}-{os.getpid()}-{secrets.token_hex(4)}"
                )
                staging.mkdir(mode=0o700)
                try:
                    self._write_json_new(staging / "manifest.json", record)
                    self._write_json_new(staging / "summary.json", summary)
                    os.rename(staging, batch_dir)
                except BaseException:
                    if staging.exists():
                        for child in staging.iterdir():
                            child.unlink(missing_ok=True)
                        staging.rmdir()
                    raise
            head = {
                "schema_version": 1,
                "contract_revision": batch_revision,
                "plan_id": plan_id,
                "batch_id": batch_id,
                "batch_record_sha256": record["record_sha256"],
                "adequacy_receipt_sha256": adequacy["adequacy_receipt_sha256"],
                "truth_effect": "none",
            }
            self._atomic_replace_json(self._head_path(plan_id), head)
        return {
            "batch": record,
            "adequacy_receipt": adequacy,
            "status": "committed_all_or_none",
            "stdout_contract": "single_machine_json",
            "truth_effect": "none",
        }

    @staticmethod
    def _write_json_new(path: Path, payload: dict[str, Any]) -> None:
        raw = (
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)
            + "\n"
        ).encode("utf-8")
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())

    @staticmethod
    def _atomic_replace_json(path: Path, payload: dict[str, Any]) -> None:
        raw = (
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)
            + "\n"
        ).encode("utf-8")
        temporary = path.with_name(
            f".{path.name}.tmp-{os.getpid()}-{secrets.token_hex(4)}"
        )
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "wb", closefd=True) as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise

    def batch(self, batch_id: str, *, deep: bool = False) -> dict[str, Any]:
        directory = self._batch_dir(batch_id)
        path = directory / "manifest.json"
        if directory.is_symlink() or path.is_symlink() or not path.is_file():
            raise KeyError(f"unknown research-draft batch: {batch_id}")
        record = self.store._read_json(path)
        if (
            record.get("batch_id") != batch_id
            or record.get("contract_revision")
            not in {
                LEGACY_RESEARCH_DRAFT_BATCH_REVISION,
                RESEARCH_DRAFT_BATCH_REVISION,
            }
            or record.get("truth_effect") != "none"
        ):
            raise ValueError("research-draft batch binding is invalid")
        without_hash = {key: value for key, value in record.items() if key != "record_sha256"}
        if record.get("record_sha256") != sha256_json(without_hash):
            raise ValueError("research-draft batch record hash mismatch")
        semantic = {
            key: value
            for key, value in record.items()
            if key not in {"batch_id", "created_at", "record_sha256"}
        }
        if batch_id != "rdb-" + sha256_json(semantic):
            raise ValueError("research-draft batch content id mismatch")
        if deep:
            plan = self.plan(record["plan_id"], deep=True)
            records = self.lifecycle.research_records()
            if record["research_index_semantic_sha256"] != sha256_json(
                [
                    {
                        "research_id": item["research_id"],
                        "record_sha256": item["record_sha256"],
                    }
                    for item in sorted(records, key=lambda item: item["research_id"])
                ]
            ):
                raise ValueError("research-draft batch Research dependency drifted")
            if record["plan_record_sha256"] != plan["record_sha256"]:
                raise ValueError("research-draft batch plan drifted")
            for entry in record["entries"]:
                if "stance_impact" not in entry:
                    if plan["domain_profile"] == "mathematics":
                        validate_mathematical_refinement_dag(
                            entry["mathematical_progress"],
                            target_policy=plan["mathematical_target_policy"],
                        )
                    continue
                authorization = entry["major_revision_authorization"]
                if authorization is None:
                    if entry["stance_impact"] in MAJOR_STANCE_EFFECTS:
                        raise ValueError(
                            "research-draft batch lost a required major-revision authorization"
                        )
                    continue
                stored = self.authorization(authorization["decision_id"], deep=True)
                if authorization != stored:
                    raise ValueError(
                        "research-draft batch authorization record drifted"
                    )
                if (
                    stored["plan_id"] != plan["plan_id"]
                    or stored["target_node_id"] != entry["target_node_id"]
                    or stored["authorized_stance_impact"] != entry["stance_impact"]
                ):
                    raise ValueError(
                        "research-draft batch authorization binding drifted"
                    )
        return record

    def current_batch(self, plan_id: str) -> dict[str, Any] | None:
        path = self._head_path(plan_id)
        if not path.exists():
            return None
        if path.is_symlink() or not path.is_file():
            raise ValueError("research-draft batch head is unsafe")
        head = self.store._read_json(path)
        _exact(
            head,
            {
                "schema_version",
                "contract_revision",
                "plan_id",
                "batch_id",
                "batch_record_sha256",
                "adequacy_receipt_sha256",
                "truth_effect",
            },
            "research-draft batch head",
        )
        if (
            head["plan_id"] != plan_id
            or head["contract_revision"]
            not in {
                LEGACY_RESEARCH_DRAFT_BATCH_REVISION,
                RESEARCH_DRAFT_BATCH_REVISION,
            }
            or head["truth_effect"] != "none"
        ):
            raise ValueError("research-draft batch head binding is invalid")
        batch = self.batch(head["batch_id"], deep=False)
        if batch["contract_revision"] != head["contract_revision"]:
            raise ValueError("research-draft batch head revision drifted")
        if batch["record_sha256"] != head["batch_record_sha256"]:
            raise ValueError("research-draft batch head hash drifted")
        summary_path = self._batch_dir(head["batch_id"]) / "summary.json"
        if summary_path.is_symlink() or not summary_path.is_file():
            raise ValueError("research-draft cached summary is missing or unsafe")
        summary = self.store._read_json(summary_path)
        if (
            summary.get("plan_id") != plan_id
            or summary.get("batch_id") != batch["batch_id"]
            or summary.get("batch_record_sha256") != batch["record_sha256"]
            or summary.get("adequacy_receipt", {}).get("adequacy_receipt_sha256")
            != head["adequacy_receipt_sha256"]
        ):
            raise ValueError("research-draft cached summary drifted")
        return {**batch, "cached_summary": summary}

    def status(self, plan_id: str, *, deep: bool = False) -> dict[str, Any]:
        # Fast status validates only the immutable plan record, current head,
        # batch bytes and cached dependency summary.  Explicit deep=True is the
        # only route that reopens the full Paper/Research dependency scan.
        plan = self.plan(plan_id, deep=deep)
        current = self.current_batch(plan_id)
        if current is None:
            return {
                "plan_id": plan_id,
                "state": "awaiting_atomic_batch",
                "target_count": len(plan["target_node_ids"]),
                "adequacy_complete": False,
                "status_source": "local_cached_summary",
                "truth_effect": "none",
            }
        if deep:
            self.batch(current["batch_id"], deep=True)
        summary = current["cached_summary"]
        return {
            "plan_id": plan_id,
            "state": "adequacy_complete",
            "batch_id": current["batch_id"],
            "target_count": summary["target_count"],
            "research_index_count": summary["research_index_count"],
            "adequacy_complete": summary["adequacy_receipt"]["adequacy_complete"],
            "adequacy_receipt_sha256": summary["adequacy_receipt"][
                "adequacy_receipt_sha256"
            ],
            "status_source": (
                "explicit_deep_validation" if deep else "local_cached_summary"
            ),
            "truth_effect": "none",
        }

    def audit(self) -> dict[str, Any]:
        errors: list[str] = []
        plans = 0
        authorizations = 0
        batches = 0
        if self.authorizations_dir.exists():
            for path in sorted(self.authorizations_dir.glob("rda-*.json")):
                authorizations += 1
                try:
                    self.authorization(path.stem, deep=True)
                except Exception as exc:
                    errors.append(f"{path.stem}: {exc}")
        if self.plans_dir.exists():
            for path in sorted(self.plans_dir.glob("rdp-*.json")):
                plans += 1
                try:
                    status = self.status(path.stem, deep=True)
                    if status["adequacy_complete"]:
                        batches += 1
                except Exception as exc:
                    errors.append(f"{path.stem}: {exc}")
        orphan_batches = []
        visible = {
            self.store._read_json(path).get("batch_id")
            for path in self.heads_dir.glob("rdp-*.json")
            if path.is_file() and not path.is_symlink()
        } if self.heads_dir.exists() else set()
        if self.batches_dir.exists():
            orphan_batches = sorted(
                path.name
                for path in self.batches_dir.glob("rdb-*")
                if path.is_dir() and path.name not in visible
            )
        return {
            "contract_revision": RESEARCH_DRAFT_PLAN_REVISION,
            "plans": plans,
            "major_revision_authorizations": authorizations,
            "adequacy_complete_plans": batches,
            "orphan_batches": orphan_batches,
            "errors": errors,
            "current_ok": not errors,
            "truth_effect": "none",
        }

from __future__ import annotations

import copy
import hashlib
import html
import json
import os
import re
import tempfile
import unicodedata
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable


PAPER_RESEARCH_PIPELINE_REVISION = "chalxius-paper-research-pipeline-2"
ORDERED_FRONTIER_REVISION = "chalxius-ordered-paper-frontier-1"
SUCCESSOR_MATERIALIZATION_REVISION = "chalxius-research-draft-successor-1"
EVIDENCE_GATE_REVISION = "chalxius-paper-evidence-gate-1"
ATOMIC_PREFLIGHT_REVISION = "chalxius-paper-atomic-preflight-2"
RESEARCH_CONTINUITY_REVISION = "chalxius-research-continuity-1"
PDF_NORMALIZATION_PROFILE = "corroborated-layout-dehyphen-v2"

CONTINUITY_MODES = {
    "philosophy": "argumentative_stance",
    "mathematics": "mathematical_target",
    "empirical": "empirical_target",
    "mixed": "mixed_target",
}
CONTINUITY_RESOLUTION_STATUSES = {
    "philosophy": frozenset({"preserved", "strengthened"}),
    "mathematics": frozenset(
        {"proved", "disproved", "unresolved_with_obstruction"}
    ),
    "empirical": frozenset({"supported", "disconfirmed", "inconclusive"}),
    "mixed": frozenset(
        {"componentwise_resolved", "partially_resolved", "unresolved_with_obstruction"}
    ),
}
CONTINUITY_CONTRACT_FIELDS = frozenset(
    {
        "schema_version",
        "contract_revision",
        "domain_profile",
        "continuity_mode",
        "declared_target",
        "required_claim_ids",
        "forbidden_claim_ids",
        "permitted_resolution_statuses",
        "target_revision_authorized",
        "domain_invariants",
    }
)

EVIDENCE_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "contract_revision",
        "paper_frontier_id",
        "counts",
        "sources",
        "claims",
        "normalization_profile",
        "authority_boundary",
        "evidence_receipt_id",
    }
)
SUCCESSOR_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "contract_revision",
        "project_id",
        "paper_id",
        "source_graph_canonical_sha256",
        "native_bundle_canonical_sha256",
        "activation_record",
        "stable_local_node_id_count",
        "preserved_edge_count",
        "source_component_and_inference_materialization",
        "predecessor_coverage_canonical_sha256",
        "successor_coverage_canonical_sha256",
        "dropped_non_native_top_level_metadata",
        "historical_rewrite",
        "inherited_fact_authority",
        "required_next_stage",
        "fact_effect",
        "truth_effect",
        "receipt_id",
    }
)

SUBSTANTIVE_SUPPORT_KINDS = {
    "direct_text",
    "direct_text_narrower_scope",
    "abstract_direct",
    "source_interpretation",
}
NON_SUBSTANTIVE_SUPPORT_KINDS = {"bibliographic_context"}
ALL_SUPPORT_KINDS = SUBSTANTIVE_SUPPORT_KINDS | NON_SUBSTANTIVE_SUPPORT_KINDS
SUBSTANTIVE_ACCESS = {
    "full_text",
    "official_full_text",
    "institutional_full_text",
    "author_manuscript_full_text",
    "publisher_full_text",
    "abstract_only",
    "institutional_summary",
}


class PaperPipelineError(ValueError):
    """A Paper research-pipeline contract failed closed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PaperPipelineError(message)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def validate_content_addressed_receipt(
    receipt: dict[str, Any],
    *,
    id_field: str,
    id_prefix: str,
    allowed_fields: frozenset[str],
    label: str,
) -> dict[str, str]:
    """Validate one exact-schema receipt without granting domain authority."""

    _require(isinstance(receipt, dict), f"{label} receipt must be an object")
    _require(set(receipt) == allowed_fields, f"{label} receipt field set drifted")
    declared_id = receipt.get(id_field)
    _require(
        isinstance(declared_id, str) and declared_id.startswith(id_prefix),
        f"{label} receipt id malformed",
    )
    semantic = {key: copy.deepcopy(value) for key, value in receipt.items() if key != id_field}
    expected_id = id_prefix + sha256_json(semantic)
    _require(declared_id == expected_id, f"{label} receipt id drifted")
    return {
        "receipt_id": expected_id,
        "canonical_sha256": sha256_json(receipt),
    }


def validate_evidence_receipt(
    receipt: dict[str, Any], *, paper_frontier_id: str
) -> dict[str, str]:
    status = validate_content_addressed_receipt(
        receipt,
        id_field="evidence_receipt_id",
        id_prefix="pev-",
        allowed_fields=EVIDENCE_RECEIPT_FIELDS,
        label="evidence",
    )
    _require(
        receipt.get("contract_revision") == EVIDENCE_GATE_REVISION,
        "evidence receipt contract mismatch",
    )
    _require(
        receipt.get("paper_frontier_id") == paper_frontier_id,
        "evidence receipt/frontier binding drifted",
    )
    sources = receipt.get("sources")
    claims = receipt.get("claims")
    counts = receipt.get("counts")
    _require(isinstance(sources, list), "evidence receipt sources malformed")
    _require(isinstance(claims, list), "evidence receipt claims malformed")
    _require(isinstance(counts, dict), "evidence receipt counts malformed")
    _require(
        counts
        == {
            "sources": len(sources),
            "claims": len(claims),
            "substantive_claims": sum(
                isinstance(row, dict)
                and row.get("support_kind") in SUBSTANTIVE_SUPPORT_KINDS
                for row in claims
            ),
        },
        "evidence receipt counts drifted",
    )
    _require(
        receipt.get("authority_boundary")
        == {
            "truth_effect": "none",
            "paper_authority_effect": "none",
            "fact_effect": "none",
        },
        "evidence receipt authority boundary drifted",
    )
    return status


def validate_successor_receipt(
    receipt: dict[str, Any], *, source_graph_canonical_sha256: str
) -> dict[str, str]:
    status = validate_content_addressed_receipt(
        receipt,
        id_field="receipt_id",
        id_prefix="rds-",
        allowed_fields=SUCCESSOR_RECEIPT_FIELDS,
        label="native successor",
    )
    _require(
        receipt.get("contract_revision") == SUCCESSOR_MATERIALIZATION_REVISION,
        "native successor receipt contract mismatch",
    )
    _require(
        receipt.get("source_graph_canonical_sha256")
        == source_graph_canonical_sha256,
        "native successor receipt/source graph binding drifted",
    )
    _require(
        receipt.get("historical_rewrite") is False
        and receipt.get("inherited_fact_authority") is False,
        "native successor receipt crosses the authority boundary",
    )
    _require(
        receipt.get("fact_effect") == "none" and receipt.get("truth_effect") == "none",
        "native successor receipt claims authority",
    )
    return status


def _strings(value: Any, label: str, *, nonempty: bool = False) -> list[str]:
    _require(isinstance(value, list), f"{label} must be a list")
    _require(
        all(isinstance(item, str) and item.strip() for item in value),
        f"{label} must contain nonempty strings",
    )
    result = [item.strip() for item in value]
    _require(not nonempty or bool(result), f"{label} must be nonempty")
    _require(len(result) == len(set(result)), f"{label} contains duplicates")
    return result


def _normalized_domain_profile(value: Any) -> str:
    _require(isinstance(value, str) and value.strip(), "domain profile missing")
    normalized = value.strip()
    return "mixed" if normalized == "mixed_union" else normalized


def validate_research_continuity_contract(
    *,
    graph: dict[str, Any],
    node_ids: set[str],
    continuity_contract: dict[str, Any],
) -> dict[str, Any]:
    """Validate the domain adapter that preserves a draft's research target.

    Philosophy preserves an argumentative direction. Mathematics preserves the
    exact problem, hypotheses, and quantifier-bearing claims while allowing a
    proof or a disproof. Empirical and mixed drafts use their own target
    semantics instead of inheriting a philosophical stance model.
    """

    _require(isinstance(continuity_contract, dict), "research continuity malformed")
    _require(
        set(continuity_contract) == CONTINUITY_CONTRACT_FIELDS,
        "research continuity field set drifted",
    )
    _require(
        continuity_contract.get("schema_version") == 1
        and continuity_contract.get("contract_revision")
        == RESEARCH_CONTINUITY_REVISION,
        "research continuity contract revision mismatch",
    )
    graph_profile = _normalized_domain_profile(graph.get("domain_profile"))
    contract_profile = _normalized_domain_profile(
        continuity_contract.get("domain_profile")
    )
    _require(graph_profile in CONTINUITY_MODES, "unsupported research domain profile")
    _require(
        contract_profile == graph_profile,
        "research continuity domain/profile substitution",
    )
    mode = continuity_contract.get("continuity_mode")
    _require(
        mode == CONTINUITY_MODES[graph_profile],
        "research continuity mode does not match the domain",
    )
    declared_target = continuity_contract.get("declared_target")
    _require(
        isinstance(declared_target, str) and declared_target.strip(),
        "declared research target missing",
    )
    required = set(
        _strings(
            continuity_contract.get("required_claim_ids"),
            "continuity required claim ids",
            nonempty=True,
        )
    )
    _require(
        required.issubset(node_ids),
        "research-target claim closure incomplete",
    )
    forbidden = set(
        _strings(
            continuity_contract.get("forbidden_claim_ids"),
            "continuity forbidden claim ids",
        )
    )
    _require(
        not forbidden.intersection(node_ids),
        "retired/forbidden Fact authority survived",
    )
    statuses = set(
        _strings(
            continuity_contract.get("permitted_resolution_statuses"),
            "permitted resolution statuses",
            nonempty=True,
        )
    )
    _require(
        statuses == CONTINUITY_RESOLUTION_STATUSES[graph_profile],
        "research continuity resolution policy drifted",
    )
    _require(
        continuity_contract.get("target_revision_authorized") is False,
        "ordinary strengthening cannot claim target-revision authorization",
    )
    invariants = continuity_contract.get("domain_invariants")
    _require(isinstance(invariants, dict), "domain continuity invariants malformed")

    if mode == "argumentative_stance":
        _require(
            set(invariants) == {"headline_claim_ids", "argumentative_direction"},
            "philosophy continuity invariant field set drifted",
        )
        headline_ids = set(
            _strings(
                invariants.get("headline_claim_ids"),
                "philosophy headline claim ids",
                nonempty=True,
            )
        )
        _require(
            headline_ids.issubset(required),
            "philosophy headline is outside required claim closure",
        )
        _require(
            isinstance(invariants.get("argumentative_direction"), str)
            and invariants["argumentative_direction"].strip(),
            "philosophy argumentative direction missing",
        )
    elif mode == "mathematical_target":
        _require(
            set(invariants)
            == {
                "target_claim_ids",
                "hypothesis_claim_ids",
                "quantifier_scope_claim_ids",
            },
            "mathematics continuity invariant field set drifted",
        )
        target_ids = set(
            _strings(
                invariants.get("target_claim_ids"),
                "mathematical target claim ids",
                nonempty=True,
            )
        )
        hypothesis_ids = set(
            _strings(
                invariants.get("hypothesis_claim_ids"),
                "mathematical hypothesis claim ids",
            )
        )
        quantifier_ids = set(
            _strings(
                invariants.get("quantifier_scope_claim_ids"),
                "mathematical quantifier-scope claim ids",
            )
        )
        _require(
            target_ids.issubset(required),
            "mathematical target is outside required claim closure",
        )
        _require(
            (target_ids | hypothesis_ids | quantifier_ids).issubset(node_ids),
            "mathematical target/hypothesis/quantifier binding is outside the DAG",
        )
    elif mode == "empirical_target":
        _require(
            set(invariants)
            == {
                "target_claim_ids",
                "research_question",
                "estimand",
                "population",
                "exposure_or_intervention",
                "outcome",
                "scope",
            },
            "empirical continuity invariant field set drifted",
        )
        target_ids = set(
            _strings(
                invariants.get("target_claim_ids"),
                "empirical target claim ids",
                nonempty=True,
            )
        )
        _require(
            target_ids.issubset(required),
            "empirical target is outside required claim closure",
        )
        for field in (
            "research_question",
            "estimand",
            "population",
            "exposure_or_intervention",
            "outcome",
            "scope",
        ):
            _require(
                isinstance(invariants.get(field), str) and invariants[field].strip(),
                f"empirical {field} missing",
            )
    else:
        _require(
            set(invariants) == {"target_claim_ids", "component_modes"},
            "mixed continuity invariant field set drifted",
        )
        target_ids = set(
            _strings(
                invariants.get("target_claim_ids"),
                "mixed target claim ids",
                nonempty=True,
            )
        )
        component_modes = set(
            _strings(
                invariants.get("component_modes"),
                "mixed component modes",
                nonempty=True,
            )
        )
        _require(
            target_ids.issubset(required),
            "mixed target is outside required claim closure",
        )
        _require(
            len(component_modes) >= 2
            and component_modes.issubset(
                {"argumentative_stance", "mathematical_target", "empirical_target"}
            ),
            "mixed continuity must compose at least two domain adapters",
        )

    normalized = {
        "contract_revision": RESEARCH_CONTINUITY_REVISION,
        "domain_profile": graph_profile,
        "continuity_mode": mode,
        "declared_target_sha256": sha256_bytes(
            declared_target.strip().encode("utf-8")
        ),
        "required_claim_ids": sorted(required),
        "forbidden_claim_ids": sorted(forbidden),
        "permitted_resolution_statuses": sorted(statuses),
        "domain_invariants_canonical_sha256": sha256_json(invariants),
        "contract_canonical_sha256": sha256_json(continuity_contract),
    }
    return normalized


def _node_id(node: dict[str, Any]) -> str:
    value = node.get("local_id", node.get("node_id"))
    _require(isinstance(value, str) and value.strip(), "Paper node id is missing")
    return value


def _edge_source(edge: dict[str, Any]) -> str:
    value = edge.get("source", edge.get("source_id"))
    _require(isinstance(value, str) and value.strip(), "Paper edge source is missing")
    return value


def _edge_target(edge: dict[str, Any]) -> str:
    value = edge.get("target", edge.get("target_id"))
    _require(isinstance(value, str) and value.strip(), "Paper edge target is missing")
    return value


def _edge_identity(edge: dict[str, Any]) -> str:
    semantic = {
        "source": _edge_source(edge),
        "target": _edge_target(edge),
        "relation_type": edge.get("relation_type"),
        "payload": edge.get("payload", {}),
    }
    return "pe-" + sha256_json(semantic)


def _graph_index(
    graph: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    _require(isinstance(nodes, list), "Paper graph nodes must be a list")
    _require(isinstance(edges, list), "Paper graph edges must be a list")
    _require(all(isinstance(item, dict) for item in nodes), "Paper nodes malformed")
    _require(all(isinstance(item, dict) for item in edges), "Paper edges malformed")
    indexed: dict[str, dict[str, Any]] = {}
    for node in nodes:
        object_id = _node_id(node)
        _require(object_id not in indexed, f"duplicate Paper node id: {object_id}")
        indexed[object_id] = node
    edge_ids = [_edge_identity(edge) for edge in edges]
    _require(len(edge_ids) == len(set(edge_ids)), "duplicate semantic Paper edge")
    return indexed, edges


def validate_paper_graph_semantics(graph: dict[str, Any]) -> dict[str, Any]:
    """Validate topology and source-component semantics without granting truth.

    This accepts both native ``source``/``target`` bundle edges and snapshot-like
    ``source_id``/``target_id`` edges.  Inference premise order is authoritative
    in the inference payload and must be witnessed by contiguous edge positions.
    """

    _require(isinstance(graph, dict), "Paper graph must be an object")
    _require(graph.get("graph_kind") == "logic", "Paper graph must be logic")
    nodes, edges = _graph_index(graph)
    relations: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        relation = edge.get("relation_type")
        _require(isinstance(relation, str) and relation, "Paper edge relation missing")
        source = _edge_source(edge)
        target = _edge_target(edge)
        _require(
            source == "__source__" or source in nodes,
            f"Paper edge has unknown source: {source}",
        )
        _require(target in nodes, f"Paper edge has unknown target: {target}")
        relations[relation].append(edge)

    premises_into: dict[str, list[tuple[int, str]]] = defaultdict(list)
    conclusions_from: dict[str, list[str]] = defaultdict(list)
    defeaters_into: dict[str, list[str]] = defaultdict(list)
    targets_from: dict[str, list[str]] = defaultdict(list)
    for edge in relations.get("premise_of", []):
        position = edge.get("payload", {}).get("position")
        _require(
            isinstance(position, int) and not isinstance(position, bool) and position >= 0,
            "premise_of edge needs a nonnegative integer position",
        )
        premises_into[_edge_target(edge)].append((position, _edge_source(edge)))
    for edge in relations.get("concludes", []):
        conclusions_from[_edge_source(edge)].append(_edge_target(edge))
    for edge in relations.get("defeats", []):
        defeaters_into[_edge_target(edge)].append(_edge_source(edge))
    for edge in relations.get("targets", []):
        targets_from[_edge_source(edge)].append(_edge_target(edge))

    inference_count = 0
    target_count = 0
    represented_components = 0
    excluded_components = 0
    component_ids: set[str] = set()
    hierarchy_links: list[tuple[str, str]] = []
    for object_id, node in nodes.items():
        object_type = node.get("object_type")
        payload = node.get("payload")
        _require(isinstance(payload, dict), f"{object_id} payload must be an object")
        if object_type == "inference":
            inference_count += 1
            premise_ids = _strings(
                payload.get("premise_ids", []), f"{object_id}.premise_ids"
            )
            positioned = premises_into.get(object_id, [])
            _require(
                len({position for position, _ in positioned}) == len(positioned),
                f"{object_id} has duplicate premise positions",
            )
            _require(
                sorted(position for position, _ in positioned)
                == list(range(len(premise_ids))),
                f"{object_id} premise positions are incomplete or gapped",
            )
            edge_order = [source for _, source in sorted(positioned)]
            _require(
                edge_order == premise_ids,
                f"{object_id} premise edge order differs from payload order",
            )
            conclusion_id = payload.get("conclusion_id")
            _require(
                isinstance(conclusion_id, str) and conclusion_id in nodes,
                f"{object_id} conclusion is missing",
            )
            _require(
                conclusions_from.get(object_id, []) == [conclusion_id],
                f"{object_id} conclusion edge differs from payload",
            )
            defeater_ids = _strings(
                payload.get("defeater_claim_ids", []),
                f"{object_id}.defeater_claim_ids",
            )
            _require(
                set(defeaters_into.get(object_id, [])) == set(defeater_ids),
                f"{object_id} defeater edges differ from payload",
            )
            bridge_ids = _strings(
                payload.get("bridge_claim_ids", []), f"{object_id}.bridge_claim_ids"
            )
            for dependency in [*premise_ids, *defeater_ids, *bridge_ids]:
                _require(
                    nodes.get(dependency, {}).get("object_type") == "claim",
                    f"{object_id} dependency is not a claim: {dependency}",
                )
        elif object_type == "paper_target":
            target_count += 1
            claim_id = payload.get("claim_id")
            _require(
                isinstance(claim_id, str)
                and nodes.get(claim_id, {}).get("object_type") == "claim",
                f"{object_id} target claim is missing",
            )
            _require(
                targets_from.get(object_id, []) == [claim_id],
                f"{object_id} target edge differs from payload",
            )
        elif object_type == "source_unit":
            source_text = payload.get("text")
            inventory = payload.get("proposition_inventory")
            _require(isinstance(source_text, str), f"{object_id} source text missing")
            _require(isinstance(inventory, list), f"{object_id} inventory missing")
            for component in inventory:
                _require(isinstance(component, dict), f"{object_id} component malformed")
                component_id = component.get("component_id")
                _require(
                    isinstance(component_id, str) and component_id,
                    f"{object_id} component id missing",
                )
                _require(
                    component_id not in component_ids,
                    f"duplicate source component id: {component_id}",
                )
                component_ids.add(component_id)
                span = component.get("exact_span")
                _require(isinstance(span, dict), f"{component_id} exact span missing")
                start, end = span.get("start"), span.get("end")
                _require(
                    isinstance(start, int)
                    and not isinstance(start, bool)
                    and isinstance(end, int)
                    and not isinstance(end, bool)
                    and 0 <= start <= end <= len(source_text),
                    f"{component_id} exact span bounds invalid",
                )
                exact_text = source_text[start:end]
                _require(span.get("text") == exact_text, f"{component_id} text drift")
                _require(
                    span.get("text_sha256")
                    == sha256_bytes(exact_text.encode("utf-8")),
                    f"{component_id} text hash drift",
                )
                mapped = _strings(
                    component.get("mapped_node_ids", []),
                    f"{component_id}.mapped_node_ids",
                )
                disposition = component.get("disposition")
                if disposition == "represented":
                    represented_components += 1
                    _require(mapped, f"{component_id} represented without graph mapping")
                    _require(
                        isinstance(component.get("composition_witness"), str)
                        and component["composition_witness"].strip(),
                        f"{component_id} represented without composition witness",
                    )
                    for mapped_id in mapped:
                        _require(
                            mapped_id in nodes,
                            f"{component_id} maps to unknown node: {mapped_id}",
                        )
                elif disposition == "excluded_with_reason":
                    excluded_components += 1
                    _require(not mapped, f"{component_id} excluded but mapped")
                    _require(
                        isinstance(component.get("reason"), str)
                        and component["reason"].strip(),
                        f"{component_id} excluded without reason",
                    )
                parent_id = component.get("parent_component_id")
                if parent_id is not None:
                    _require(
                        isinstance(parent_id, str) and parent_id,
                        f"{component_id} parent id malformed",
                    )
                    hierarchy_links.append((parent_id, component_id))

    for parent_id, child_id in hierarchy_links:
        _require(parent_id in component_ids, f"unknown parent component: {parent_id}")
        _require(parent_id != child_id, f"component cannot parent itself: {child_id}")
    hierarchy: dict[str, set[str]] = defaultdict(set)
    for parent_id, child_id in hierarchy_links:
        hierarchy[parent_id].add(child_id)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(component_id: str) -> None:
        _require(component_id not in visiting, "source component hierarchy cycle")
        if component_id in visited:
            return
        visiting.add(component_id)
        for child_id in hierarchy.get(component_id, set()):
            visit(child_id)
        visiting.remove(component_id)
        visited.add(component_id)

    for component_id in sorted(component_ids):
        visit(component_id)

    return {
        "contract_revision": PAPER_RESEARCH_PIPELINE_REVISION,
        "paper_id": graph.get("paper_id"),
        "project_id": graph.get("project_id"),
        "source_role": graph.get("source_role", "legacy_unspecified"),
        "nodes": len(nodes),
        "edges": len(edges),
        "inferences": inference_count,
        "paper_targets": target_count,
        "represented_source_components": represented_components,
        "excluded_source_components": excluded_components,
        "hierarchy_links": len(hierarchy_links),
        "graph_canonical_sha256": sha256_json(graph),
        "truth_effect": "none",
    }


def build_ordered_paper_frontier(
    graph: dict[str, Any], *, headline_claim_ids: list[str]
) -> dict[str, Any]:
    """Project the complete upstream Paper closure without topology compression."""

    graph_status = validate_paper_graph_semantics(graph)
    nodes, edges = _graph_index(graph)
    roots = _strings(headline_claim_ids, "headline_claim_ids", nonempty=True)
    for claim_id in roots:
        _require(
            nodes.get(claim_id, {}).get("object_type") == "claim",
            f"frontier root is not a Paper claim: {claim_id}",
        )
    inference_by_conclusion: dict[str, list[dict[str, Any]]] = defaultdict(list)
    targets_by_claim: dict[str, list[str]] = defaultdict(list)
    source_by_object: dict[str, list[str]] = defaultdict(list)
    for object_id, node in nodes.items():
        if node.get("object_type") == "inference":
            inference_by_conclusion[node["payload"]["conclusion_id"]].append(node)
        elif node.get("object_type") == "paper_target":
            targets_by_claim[node["payload"]["claim_id"]].append(object_id)
    for edge in edges:
        if edge.get("relation_type") == "anchors":
            source_by_object[_edge_source(edge)].append(_edge_target(edge))

    selected_claims: set[str] = set()
    selected_inferences: set[str] = set()
    queue: deque[str] = deque(roots)
    while queue:
        claim_id = queue.popleft()
        if claim_id in selected_claims:
            continue
        selected_claims.add(claim_id)
        for inference in inference_by_conclusion.get(claim_id, []):
            inference_id = _node_id(inference)
            selected_inferences.add(inference_id)
            payload = inference["payload"]
            for dependency in [
                *payload.get("premise_ids", []),
                *payload.get("bridge_claim_ids", []),
                *payload.get("defeater_claim_ids", []),
            ]:
                if dependency not in selected_claims:
                    queue.append(dependency)

    claim_rows: list[dict[str, Any]] = []
    for claim_id in sorted(selected_claims):
        payload = nodes[claim_id]["payload"]
        claim_rows.append(
            {
                "claim_id": claim_id,
                "statement": payload.get("statement"),
                "statement_sha256": payload.get("statement_sha256"),
                "discourse_role": payload.get("discourse_role"),
                "modality": payload.get("modality"),
                "content_type": payload.get("content_type"),
                "paper_target_ids": sorted(targets_by_claim.get(claim_id, [])),
                "source_unit_ids": sorted(set(source_by_object.get(claim_id, []))),
                "work_unit_kind": "paper_claim",
                "research_state": "requires_nodewise_research_or_disposition",
            }
        )
    inference_rows: list[dict[str, Any]] = []
    dependency_edges: list[dict[str, Any]] = []
    for inference_id in sorted(selected_inferences):
        payload = nodes[inference_id]["payload"]
        premise_ids = list(payload.get("premise_ids", []))
        bridge_ids = list(payload.get("bridge_claim_ids", []))
        defeater_ids = list(payload.get("defeater_claim_ids", []))
        conclusion_id = payload["conclusion_id"]
        inference_rows.append(
            {
                "inference_id": inference_id,
                "inference_kind": payload.get("inference_kind"),
                "strength": payload.get("strength"),
                "premise_ids": premise_ids,
                "premise_order_sha256": sha256_json(premise_ids),
                "bridge_claim_ids": bridge_ids,
                "defeater_claim_ids": defeater_ids,
                "conclusion_ids": [conclusion_id],
                "source_unit_ids": sorted(set(source_by_object.get(inference_id, []))),
                "work_unit_kind": "paper_inference",
                "research_state": "requires_bridge_validity_review",
            }
        )
        for position, source_id in enumerate(premise_ids):
            dependency_edges.append(
                {
                    "source_claim_id": source_id,
                    "target_claim_id": conclusion_id,
                    "inference_id": inference_id,
                    "dependency_role": "premise",
                    "position": position,
                }
            )
        for source_id in bridge_ids:
            dependency_edges.append(
                {
                    "source_claim_id": source_id,
                    "target_claim_id": conclusion_id,
                    "inference_id": inference_id,
                    "dependency_role": "bridge",
                    "position": None,
                }
            )
        for source_id in defeater_ids:
            dependency_edges.append(
                {
                    "source_claim_id": source_id,
                    "target_claim_id": conclusion_id,
                    "inference_id": inference_id,
                    "dependency_role": "defeater",
                    "position": None,
                }
            )
    selected_targets = sorted(
        {target for claim_id in selected_claims for target in targets_by_claim.get(claim_id, [])}
    )
    semantic = {
        "schema_version": 1,
        "contract_revision": ORDERED_FRONTIER_REVISION,
        "projection_kind": "paper_graph_research_frontier",
        "project_id": graph.get("project_id"),
        "paper_id": graph.get("paper_id"),
        "source_role": graph.get("source_role", "legacy_unspecified"),
        "paper_graph_canonical_sha256": graph_status["graph_canonical_sha256"],
        "headline_claim_ids": roots,
        "counts": {
            "claims": len(claim_rows),
            "inferences": len(inference_rows),
            "paper_targets": len(selected_targets),
            "dependency_edges": len(dependency_edges),
            "work_units": len(claim_rows) + len(inference_rows),
        },
        "claim_frontier": claim_rows,
        "inference_frontier": inference_rows,
        "paper_target_ids": selected_targets,
        "topology_edges": dependency_edges,
        "authority_boundary": {
            "auto_topology_effect": "none",
            "fact_effect": "none",
            "paper_authority_effect": "none",
            "truth_effect": "none",
        },
    }
    return {
        **semantic,
        "frontier_id": "prf-" + sha256_json(semantic),
    }


def validate_ordered_paper_frontier(
    graph: dict[str, Any], frontier: dict[str, Any]
) -> dict[str, Any]:
    _require(isinstance(frontier, dict), "Paper frontier must be an object")
    roots = _strings(
        frontier.get("headline_claim_ids"), "frontier.headline_claim_ids", nonempty=True
    )
    expected = build_ordered_paper_frontier(graph, headline_claim_ids=roots)
    _require(frontier == expected, "Paper frontier differs from ordered graph projection")
    return {
        "contract_revision": ORDERED_FRONTIER_REVISION,
        "frontier_id": expected["frontier_id"],
        "claims": expected["counts"]["claims"],
        "inferences": expected["counts"]["inferences"],
        "premise_order_preserved": True,
        "topology_compression": "forbidden",
        "truth_effect": "none",
    }


def stable_identity_merge(
    base: Iterable[dict[str, Any]],
    additions: Iterable[dict[str, Any]],
    *,
    identity_field: str,
) -> list[dict[str, Any]]:
    """Merge by stable identity, rejecting same-id semantic drift."""

    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for item in [*base, *additions]:
        _require(isinstance(item, dict), "stable-identity merge item malformed")
        identity = item.get(identity_field)
        _require(
            isinstance(identity, str) and identity,
            f"stable-identity item lacks {identity_field}",
        )
        if identity in merged:
            _require(
                merged[identity] == item,
                f"stable identity collision with semantic drift: {identity}",
            )
            continue
        merged[identity] = copy.deepcopy(item)
        order.append(identity)
    return [merged[identity] for identity in order]


def normalize_delta_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    """Normalize heterogeneous copy-on-write deltas to one nontruth IR."""

    _require(isinstance(receipt, dict), "delta receipt must be an object")
    delta_id = receipt.get("delta_id", receipt.get("receipt_id"))
    _require(isinstance(delta_id, str) and delta_id, "delta receipt id missing")
    added_nodes = receipt.get("added_node_ids", receipt.get("fresh_node_spec_ids", []))
    retired_nodes = receipt.get(
        "retired_node_ids", receipt.get("removed_active_node_lineage", [])
    )
    added_edges = receipt.get("added_edge_ids", receipt.get("declared_new_edge_ids", []))
    redirects = receipt.get(
        "identity_redirects",
        receipt.get("lineage_redirects", receipt.get("node_id_map", {})),
    )
    if isinstance(redirects, list):
        redirect_rows = redirects
    elif isinstance(redirects, dict):
        redirect_rows = [
            {"predecessor_id": key, "successor_id": value}
            for key, value in sorted(redirects.items())
        ]
    else:
        raise PaperPipelineError("delta identity redirects malformed")
    normalized = {
        "schema_version": 1,
        "contract_revision": "chalxius-paper-delta-ir-1",
        "delta_id": delta_id,
        "base_binding": receipt.get("base_binding", receipt.get("base_snapshot_id")),
        "added_node_ids": sorted(_strings(added_nodes, "delta added nodes")),
        "retired_node_ids": sorted(_strings(retired_nodes, "delta retired nodes")),
        "added_edge_ids": sorted(_strings(added_edges, "delta added edges")),
        "identity_redirects": stable_identity_merge(
            [], redirect_rows, identity_field="predecessor_id"
        ),
        "source_receipt_canonical_sha256": sha256_json(receipt),
        "authority_effect": "none",
        "fact_effect": "none",
        "truth_effect": "none",
    }
    _require(
        not set(normalized["added_node_ids"]).intersection(
            normalized["retired_node_ids"]
        ),
        "delta adds and retires the same node identity",
    )
    return normalized


_CHX38_OCCURRENCE_LINE = re.compile(
    r"CHX-038 source-total occurrence dispositions:\s*(\[[^\n]*\])"
)


def _inference_semantic_operation(local_id: str, payload: dict[str, Any]) -> str:
    kind = payload.get("inference_kind")
    rationale = str(payload.get("rationale", ""))
    if rationale.startswith(
        "Materializes a declared nontruth repair-manifest topology relation."
    ):
        return "relation_materialization"
    if re.search(r"classification|content[-_ ]?type|分类|归类", local_id + " " + rationale, re.IGNORECASE):
        return "classification_repair"
    if kind == "definition_expansion":
        return "definition_repair"
    if kind == "normative_bridge":
        return "normative_bridge"
    if kind == "conceptual_bridge":
        return "conceptual_bridge"
    return "argumentative_inference"


def _materialize_native_node_extensions(
    raw_nodes: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    # Imported lazily to keep the module usable for evidence-only workflows.
    from .paper_logic_contracts import scan_high_risk_operators

    nodes = copy.deepcopy(raw_nodes)
    transformed_nodes: set[str] = set()
    hierarchy_atoms = 0
    source_occurrence_records = 0
    inference_operations: dict[str, int] = defaultdict(int)
    for node in nodes:
        local_id = _node_id(node)
        payload = node.get("payload", {})
        if node.get("object_type") == "source_unit":
            inventory = payload.get("proposition_inventory", [])
            if not isinstance(inventory, list):
                continue
            changed = False
            unit_occurrences: dict[tuple[int, int, str, str], dict[str, Any]] = {}
            unit_text = str(payload.get("text", ""))
            scanned_positions = {
                (entry["start"], entry["end"], entry["token"]): entry
                for entry in scan_high_risk_operators(unit_text)
            }
            for component in inventory:
                component_id = component.get("component_id")
                if not isinstance(component_id, str) or not component_id:
                    continue
                component["component_level"] = "atom"
                component["partition_path"] = [local_id, component_id]
                component["child_component_ids"] = []
                hierarchy_atoms += 1
                changed = True
                witness = str(component.get("composition_witness", ""))
                match = _CHX38_OCCURRENCE_LINE.search(witness)
                if match is None:
                    continue
                try:
                    occurrences = json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue
                if not isinstance(occurrences, list):
                    continue
                for record in occurrences:
                    if not isinstance(record, dict):
                        continue
                    start, end, token = (
                        record.get("start"),
                        record.get("end"),
                        record.get("token"),
                    )
                    if (
                        not isinstance(start, int)
                        or not isinstance(end, int)
                        or not isinstance(token, str)
                        or not (0 <= start < end <= len(unit_text))
                    ):
                        continue
                    surface = unit_text[start:end]
                    if surface != token:
                        continue
                    semantic = {
                        "source_unit_id": local_id,
                        "token": surface,
                        "start": start,
                        "end": end,
                        "kind": str(record.get("kind", "unclassified")),
                    }
                    scanned_entry = scanned_positions.get((start, end, surface))
                    semantic["disposition"] = (
                        "mapped_as_operator"
                        if scanned_entry is not None
                        else "mapped_as_qualifier"
                    )
                    key = (start, end, surface.casefold(), semantic["kind"])
                    unit_occurrences[key] = {
                        "occurrence_id": "occ-src-" + sha256_json(semantic)[:20],
                        "token": surface,
                        "start": start,
                        "end": end,
                        "kind": semantic["kind"],
                        "disposition": semantic["disposition"],
                        "scope": (
                            f"Source-total occurrence at source-unit[{start}:{end}]; "
                            "semantic transport is reviewed through reciprocal Paper mappings."
                        ),
                    }
            payload["source_occurrence_ledger"] = [
                unit_occurrences[key]
                for key in sorted(unit_occurrences)
            ]
            source_occurrence_records += len(unit_occurrences)
            if changed:
                transformed_nodes.add(local_id)
        elif node.get("object_type") == "inference":
            operation = _inference_semantic_operation(local_id, payload)
            if payload.get("semantic_operation") != operation:
                payload["semantic_operation"] = operation
                transformed_nodes.add(local_id)
            inference_operations[operation] += 1
    return nodes, {
        "transformed_node_ids": sorted(transformed_nodes),
        "transformed_node_count": len(transformed_nodes),
        "hierarchy_atom_count": hierarchy_atoms,
        "source_occurrence_record_count": source_occurrence_records,
        "inference_semantic_operation_counts": dict(sorted(inference_operations.items())),
    }


def materialize_native_research_draft_successor(
    graph: dict[str, Any],
    *,
    actor: str,
    builder_context_id: str,
    activation_record: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Create a prospective native bundle while retaining dropped metadata hashes.

    The source graph is never rewritten.  The returned bundle has exactly the
    native Paper Logic bundle fields; every non-native top-level field remains
    visible in the separate content-addressed projection receipt.
    """

    status = validate_paper_graph_semantics(graph)
    _require(isinstance(actor, str) and actor.strip(), "successor actor missing")
    _require(
        isinstance(builder_context_id, str) and builder_context_id.strip(),
        "successor builder context missing",
    )
    _require(isinstance(activation_record, dict), "activation record malformed")
    _require(
        activation_record.get("activation_policy") == "prospective_only",
        "successor activation must be prospective_only",
    )
    _require(
        activation_record.get("source_role") == "research_draft",
        "successor activation must select research_draft",
    )
    _require(
        activation_record.get("authority_effect") == "none"
        and activation_record.get("truth_effect") == "none",
        "successor activation cannot transfer authority",
    )
    native_fields = {
        "schema_version",
        "feature_revision",
        "project_id",
        "paper_id",
        "graph_kind",
        "domain_profile",
        "builder",
        "builder_context_id",
        "source",
        "source_role",
        "base_snapshot_id",
        "supersedes_snapshot_id",
        "coverage",
        "nodes",
        "edges",
    }
    native_nodes, extension_status = _materialize_native_node_extensions(
        graph.get("nodes", [])
    )
    original_coverage = copy.deepcopy(graph.get("coverage"))
    successor_coverage = copy.deepcopy(original_coverage)
    if isinstance(successor_coverage, dict):
        successor_coverage["completeness_claim"] = (
            "Prospective native research-draft successor of a hash-bound predecessor "
            "coverage claim. Source-unit/atom hierarchy and open operator occurrences "
            "are materialized in the successor nodes; completeness remains nontruth "
            "pending native review and freeze. predecessor_coverage_sha256="
            + sha256_json(original_coverage)
        )
    bundle = {
        "schema_version": graph.get("schema_version"),
        "feature_revision": graph.get("feature_revision"),
        "project_id": graph.get("project_id"),
        "paper_id": graph.get("paper_id"),
        "graph_kind": graph.get("graph_kind"),
        "domain_profile": graph.get("domain_profile"),
        "builder": actor.strip(),
        "builder_context_id": builder_context_id.strip(),
        "source": copy.deepcopy(graph.get("source")),
        "source_role": "research_draft",
        "base_snapshot_id": "",
        "supersedes_snapshot_id": "",
        "coverage": successor_coverage,
        "nodes": native_nodes,
        "edges": copy.deepcopy(graph.get("edges")),
    }
    _require(set(bundle) == native_fields, "native successor field set drifted")
    dropped = {
        key: {
            "canonical_sha256": sha256_json(value),
            "value": copy.deepcopy(value),
        }
        for key, value in sorted(graph.items())
        if key not in native_fields
    }
    semantic_receipt = {
        "schema_version": 1,
        "contract_revision": SUCCESSOR_MATERIALIZATION_REVISION,
        "project_id": graph.get("project_id"),
        "paper_id": graph.get("paper_id"),
        "source_graph_canonical_sha256": status["graph_canonical_sha256"],
        "native_bundle_canonical_sha256": sha256_json(bundle),
        "activation_record": copy.deepcopy(activation_record),
        "stable_local_node_id_count": len(bundle["nodes"]),
        "preserved_edge_count": len(bundle["edges"]),
        "source_component_and_inference_materialization": extension_status,
        "predecessor_coverage_canonical_sha256": sha256_json(original_coverage),
        "successor_coverage_canonical_sha256": sha256_json(successor_coverage),
        "dropped_non_native_top_level_metadata": dropped,
        "historical_rewrite": False,
        "inherited_fact_authority": False,
        "required_next_stage": "native Paper stage/review/freeze and strict research-draft plan",
        "fact_effect": "none",
        "truth_effect": "none",
    }
    receipt = {
        **semantic_receipt,
        "receipt_id": "rds-" + sha256_json(semantic_receipt),
    }
    return bundle, receipt


PDF_LAYOUT_HYPHENATION_RE = re.compile(
    r"(?P<left>[^\W\d_])-[ \t]*\n[ \t]*(?P<right>[^\W\d_])",
    flags=re.UNICODE,
)
PDF_GAPPED_LAYOUT_HYPHENATION_RE = re.compile(
    r"(?P<left>[^\W\d_]+)[ \t]+-[ \t]*\n[ \t]*(?P<right>[^\W\d_]+)",
    flags=re.UNICODE,
)


def normalize_pdf_layout(value: str, corroborating_layout: str = "") -> str:
    """Remove only extraction-visible discretionary word breaks."""

    _require(isinstance(value, str), "PDF text must be a string")
    _require(isinstance(corroborating_layout, str), "PDF layout text must be a string")
    text = value.replace("\r\n", "\n").replace("\r", "\n").replace("\u00ad", "")
    layout = (
        corroborating_layout.replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\u00ad", "")
    )

    def join_corroborated(match: re.Match[str]) -> str:
        left = match.group("left")
        right = match.group("right")
        if not right[0].islower() or not layout:
            return match.group(0)
        pattern = re.compile(
            rf"(?<![^\W\d_]){re.escape(left)}-[ \t]*\n[ \t]*"
            rf"{re.escape(right)}(?![^\W\d_])",
            flags=re.UNICODE,
        )
        return left + right if pattern.search(layout) else match.group(0)

    text = PDF_GAPPED_LAYOUT_HYPHENATION_RE.sub(join_corroborated, text)

    def join_direct(match: re.Match[str]) -> str:
        right = match.group("right")
        return match.group("left") + right if right.islower() else match.group(0)

    return PDF_LAYOUT_HYPHENATION_RE.sub(join_direct, text)


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def normalize_identity(value: Any) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(value)))
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+", text.casefold()))


def normalize_doi(value: Any) -> str:
    doi = str(value).strip().lower()
    return re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi)


class _VisibleHTML(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "canvas", "template"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag.lower() in self.SKIP:
            self.skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.SKIP and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.skip_depth and data.strip():
            self.parts.append(data)


def _contained_file(project_root: Path, raw: Any, label: str) -> Path:
    _require(isinstance(raw, str) and raw.strip(), f"{label} path missing")
    root = project_root.resolve()
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PaperPipelineError(f"{label} path escapes project") from exc
    _require(resolved.is_file() and not resolved.is_symlink(), f"{label} file missing")
    return resolved


def _bound_file(project_root: Path, spec: Any, label: str) -> Path:
    _require(isinstance(spec, dict), f"{label} binding malformed")
    path = _contained_file(project_root, spec.get("path"), label)
    expected = spec.get("sha256", spec.get("raw_sha256"))
    _require(
        isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected),
        f"{label} SHA-256 invalid",
    )
    _require(sha256_path(path) == expected, f"{label} bytes drifted")
    return path


def _json_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _json_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _json_strings(item)
    elif value is not None:
        yield str(value)


def _extract_text(path: Path) -> tuple[str, list[str], str]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        _require(path.read_bytes().startswith(b"%PDF"), "evidence PDF magic invalid")
        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise PaperPipelineError("pypdf is required for PDF evidence") from exc
        pages: list[str] = []
        for page in PdfReader(str(path)).pages:
            raw = page.extract_text() or ""
            layout = ""
            if PDF_GAPPED_LAYOUT_HYPHENATION_RE.search(
                raw.replace("\r\n", "\n").replace("\r", "\n")
            ):
                layout = page.extract_text(extraction_mode="layout") or ""
            pages.append(normalize_space(normalize_pdf_layout(raw, layout)))
        return normalize_space("\n".join(pages)), pages, PDF_NORMALIZATION_PROFILE
    if suffix in {".html", ".htm"}:
        parser = _VisibleHTML()
        parser.feed(path.read_text(encoding="utf-8", errors="replace"))
        return normalize_space("\n".join(parser.parts)), [], "visible_html_text"
    if suffix in {".xml", ".xhtml", ".nxml"}:
        root = ET.fromstring(path.read_bytes())
        text = normalize_space(" ".join(root.itertext()))
        return text, [], "structured_xml_text"
    if suffix == ".json":
        value = json.loads(path.read_text(encoding="utf-8"))
        return normalize_space("\n".join(_json_strings(value))), [], "json_record_text"
    return (
        normalize_space(path.read_text(encoding="utf-8", errors="replace")),
        [],
        "plain_text",
    )


def _crossref_identity(record: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    if "status" in record:
        _require(record.get("status") == "ok", "Crossref status is not ok")
    message = record.get("message", record)
    _require(isinstance(message, dict), "Crossref identity message malformed")
    titles = message.get("title", [])
    actual_title = titles[0] if isinstance(titles, list) and titles else titles
    _require(
        normalize_identity(actual_title) == normalize_identity(expected.get("title")),
        "Crossref title mismatch",
    )
    _require(
        normalize_doi(message.get("DOI")) == normalize_doi(expected.get("doi")),
        "Crossref DOI mismatch",
    )
    author_rows = message.get("author", [])
    actual_authors = [
        normalize_space(f"{item.get('given', '')} {item.get('family', '')}")
        for item in author_rows
        if isinstance(item, dict)
    ]
    expected_authors = expected.get("authors", [])
    _require(
        [normalize_identity(item) for item in actual_authors]
        == [normalize_identity(item) for item in expected_authors],
        "Crossref author mismatch",
    )
    year = None
    for field in ("published-print", "published-online", "issued", "created"):
        parts = message.get(field, {}).get("date-parts", []) if isinstance(message.get(field), dict) else []
        if parts and parts[0]:
            year = parts[0][0]
            break
    _require(year == expected.get("year"), "Crossref year mismatch")
    return {
        "title": normalize_space(str(actual_title)),
        "doi": normalize_doi(message.get("DOI")) or None,
        "authors": actual_authors,
        "year": year,
    }


def _locator_text(
    claim: dict[str, Any], full_text: str, pages: list[str], source_key: str
) -> str:
    locator = claim.get("locator")
    _require(isinstance(locator, dict), f"{source_key}: claim locator required")
    kind = locator.get("kind")
    value = locator.get("value")
    _require(isinstance(kind, str) and kind, f"{source_key}: locator kind invalid")
    _require(value not in (None, ""), f"{source_key}: locator value missing")
    if kind in {"page", "pdf_page_1_based"}:
        try:
            page_number = int(value)
        except (TypeError, ValueError) as exc:
            raise PaperPipelineError(f"{source_key}: page locator invalid") from exc
        _require(
            not isinstance(value, bool) and 1 <= page_number <= len(pages),
            f"{source_key}: page locator invalid",
        )
        return pages[page_number - 1]
    # Section/abstract/record labels are human review locators.  The retained
    # exact witness is still checked against the bound whole payload, allowing
    # domain-specific locator vocabularies without weakening byte identity.
    return full_text


def verify_evidence_registry(
    *,
    project_root: Path,
    registry: dict[str, Any],
    frontier: dict[str, Any],
) -> dict[str, Any]:
    """Verify publication identity and claim-level retained witnesses."""

    _require(registry.get("schema_version") == 1, "evidence registry schema invalid")
    _require(
        registry.get("registry_kind") == "literature_identity_and_claim_support",
        "evidence registry kind invalid",
    )
    paper_objects = {
        row["claim_id"] for row in frontier.get("claim_frontier", [])
    } | {row["inference_id"] for row in frontier.get("inference_frontier", [])}
    target_ids = set(frontier.get("paper_target_ids", []))
    sources = registry.get("sources")
    _require(isinstance(sources, list) and sources, "evidence sources missing")
    source_keys: set[str] = set()
    claim_ids: set[str] = set()
    verified_sources: list[dict[str, Any]] = []
    verified_claims: list[dict[str, Any]] = []
    for source in sources:
        _require(isinstance(source, dict), "evidence source malformed")
        source_key = source.get("source_key")
        _require(isinstance(source_key, str) and source_key, "source_key missing")
        _require(source_key not in source_keys, f"duplicate source_key: {source_key}")
        source_keys.add(source_key)
        expected = source.get("expected_identity")
        _require(isinstance(expected, dict), f"{source_key}: expected identity missing")
        identity_spec = source.get("identity_record")
        identity_path = _bound_file(project_root, identity_spec, f"{source_key}.identity")
        adapter = identity_spec.get("adapter")
        if adapter == "crossref_message":
            identity = _crossref_identity(
                json.loads(identity_path.read_text(encoding="utf-8")), expected
            )
        else:
            identity_text, _, _ = _extract_text(identity_path)
            _require(
                normalize_identity(expected.get("title")) in normalize_identity(identity_text),
                f"{source_key}: identity title absent",
            )
            _require(
                normalize_identity(expected.get("year")) in normalize_identity(identity_text),
                f"{source_key}: identity year absent",
            )
            authors = expected.get("authors", [])
            _require(isinstance(authors, list) and authors, f"{source_key}: expected authors missing")
            minimum = expected.get("minimum_author_matches", len(authors))
            _require(
                isinstance(minimum, int)
                and not isinstance(minimum, bool)
                and 0 < minimum <= len(authors),
                f"{source_key}: minimum author match count invalid",
            )
            _require(
                sum(
                    normalize_identity(author) in normalize_identity(identity_text)
                    for author in authors
                )
                >= minimum,
                f"{source_key}: identity author absent",
            )
            expected_doi = normalize_doi(expected.get("doi"))
            if expected_doi and bool(expected.get("require_doi_in_payload", False)):
                _require(
                    normalize_identity(expected_doi)
                    in normalize_identity(identity_text),
                    f"{source_key}: identity DOI absent",
                )
            identity = copy.deepcopy(expected)
        payload_spec = source.get("substantive_payload")
        payload_path = _bound_file(project_root, payload_spec, f"{source_key}.payload")
        full_text, pages, extraction_profile = _extract_text(payload_path)
        access = payload_spec.get("access_sufficiency")
        source_claim_ids: list[str] = []
        for claim in source.get("claims", []):
            _require(isinstance(claim, dict), f"{source_key}: claim malformed")
            claim_id = claim.get("claim_id")
            _require(isinstance(claim_id, str) and claim_id, "evidence claim id missing")
            _require(claim_id not in claim_ids, f"duplicate evidence claim: {claim_id}")
            claim_ids.add(claim_id)
            source_claim_ids.append(claim_id)
            support_kind = claim.get("support_kind")
            _require(support_kind in ALL_SUPPORT_KINDS, f"{claim_id}: support kind invalid")
            substantive = support_kind in SUBSTANTIVE_SUPPORT_KINDS
            paper_ids = _strings(
                claim.get("paper_object_ids", []), f"{claim_id}.paper_object_ids"
            )
            if substantive:
                _require(access in SUBSTANTIVE_ACCESS, f"{claim_id}: access insufficient")
                _require(paper_ids, f"{claim_id}: substantive claim lacks Paper binding")
                _require(
                    not set(paper_ids).difference(paper_objects),
                    f"{claim_id}: unknown Paper binding",
                )
                witness = claim.get("witness")
                _require(
                    isinstance(witness, str) and witness.strip(),
                    f"{claim_id}: witness missing",
                )
                local_text = _locator_text(claim, full_text, pages, source_key)
                _require(
                    normalize_identity(witness) in normalize_identity(local_text),
                    f"{claim_id}: witness absent at locator",
                )
                if support_kind == "abstract_direct":
                    _require(access == "abstract_only", f"{claim_id}: abstract scope mismatch")
                if support_kind == "source_interpretation":
                    _require(
                        isinstance(claim.get("bridge_statement"), str)
                        and claim["bridge_statement"].strip(),
                        f"{claim_id}: interpretation bridge missing",
                    )
            else:
                _require(not paper_ids, f"{claim_id}: context claim binds Paper authority")
                witness = ""
            review = claim.get("support_review")
            _require(isinstance(review, dict), f"{claim_id}: support review missing")
            _require(review.get("status") == "passed", f"{claim_id}: review not passed")
            _require(
                isinstance(review.get("reviewer"), str) and review["reviewer"].strip(),
                f"{claim_id}: reviewer missing",
            )
            _require(
                isinstance(review.get("scope_note"), str) and review["scope_note"].strip(),
                f"{claim_id}: review scope missing",
            )
            claim_targets = sorted(
                {
                    target
                    for paper_id in paper_ids
                    for target in next(
                        (
                            row.get("paper_target_ids", [])
                            for row in frontier.get("claim_frontier", [])
                            if row.get("claim_id") == paper_id
                        ),
                        [],
                    )
                }
            )
            _require(
                not set(claim_targets).difference(target_ids),
                f"{claim_id}: unresolved Paper target binding",
            )
            verified_claims.append(
                {
                    **copy.deepcopy(claim),
                    "source_key": source_key,
                    "paper_object_ids": sorted(paper_ids),
                    "paper_target_ids": claim_targets,
                    "witness_sha256": sha256_bytes(witness.encode("utf-8")),
                    "truth_effect": "none",
                    "paper_authority_effect": "none",
                    "fact_effect": "none",
                }
            )
        verified_sources.append(
            {
                "source_key": source_key,
                "identity": identity,
                "identity_record_sha256": sha256_path(identity_path),
                "payload_sha256": sha256_path(payload_path),
                "extraction_profile": extraction_profile,
                "claim_ids": source_claim_ids,
            }
        )
    semantic = {
        "schema_version": 1,
        "contract_revision": EVIDENCE_GATE_REVISION,
        "paper_frontier_id": frontier.get("frontier_id"),
        "counts": {
            "sources": len(verified_sources),
            "claims": len(verified_claims),
            "substantive_claims": sum(
                row["support_kind"] in SUBSTANTIVE_SUPPORT_KINDS
                for row in verified_claims
            ),
        },
        "sources": verified_sources,
        "claims": verified_claims,
        "normalization_profile": PDF_NORMALIZATION_PROFILE,
        "authority_boundary": {
            "truth_effect": "none",
            "paper_authority_effect": "none",
            "fact_effect": "none",
        },
    }
    return {**semantic, "evidence_receipt_id": "pev-" + sha256_json(semantic)}


def _topological_order(node_ids: set[str], edges: list[tuple[str, str]]) -> list[str]:
    dependencies: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
    children: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
    for source, target in edges:
        _require(source in node_ids and target in node_ids, "atomic DAG edge endpoint missing")
        _require(source != target, "atomic DAG self-loop")
        dependencies[target].add(source)
        children[source].add(target)
    ready = sorted(node_id for node_id, deps in dependencies.items() if not deps)
    order: list[str] = []
    while ready:
        node_id = ready.pop(0)
        order.append(node_id)
        for child in sorted(children[node_id]):
            dependencies[child].discard(node_id)
            if not dependencies[child] and child not in order and child not in ready:
                ready.append(child)
        ready.sort()
    _require(len(order) == len(node_ids), "atomic Paper DAG has a cycle")
    return order


def validate_atomic_paper_dag(
    *,
    graph: dict[str, Any],
    frontier: dict[str, Any],
    dag: dict[str, Any],
    continuity_contract: dict[str, Any],
) -> dict[str, Any]:
    """Check Paper-subject atomic coverage before the native V5 truth path."""

    validate_ordered_paper_frontier(graph, frontier)
    _require(isinstance(dag, dict), "atomic Paper DAG malformed")
    subject = dag.get("validation_subject")
    _require(isinstance(subject, dict), "atomic Paper DAG validation subject missing")
    _require(subject.get("kind") == "paper", "atomic DAG escaped through theorem mode")
    _require(
        dag.get("source_role") == "research_draft"
        and subject.get("source_role", "research_draft") == "research_draft",
        "atomic DAG is not research_draft",
    )
    _require(
        dag.get("project_id") == graph.get("project_id")
        and dag.get("paper_id") == graph.get("paper_id"),
        "atomic DAG project/Paper binding drifted",
    )
    rows = dag.get("nodes")
    _require(isinstance(rows, list) and rows, "atomic DAG nodes missing")
    _require(all(isinstance(row, dict) for row in rows), "atomic DAG node malformed")
    node_ids = [row.get("claim_id") for row in rows]
    _require(
        all(isinstance(node_id, str) and node_id for node_id in node_ids),
        "atomic DAG claim id missing",
    )
    _require(len(node_ids) == len(set(node_ids)), "atomic DAG duplicate claim")
    node_set = set(node_ids)
    frontier_claims = {row["claim_id"] for row in frontier["claim_frontier"]}
    represented_paper_claims = {
        paper_id
        for row in rows
        for paper_id in row.get(
            "inherited_paper_object_ids",
            [row.get("paper_claim_id")] if row.get("paper_claim_id") else [],
        )
        if paper_id in frontier_claims
    } | {row.get("paper_claim_id") for row in rows if row.get("paper_claim_id") in frontier_claims}
    missing = sorted(frontier_claims.difference(represented_paper_claims))
    _require(not missing, "atomic DAG omits Paper claims: " + ", ".join(missing[:8]))
    for row in rows:
        claim_id = row["claim_id"]
        _require(
            isinstance(row.get("statement"), str) and row["statement"].strip(),
            f"{claim_id}: atomic statement missing",
        )
        _require(
            row.get("statement_sha256")
            == sha256_bytes(row["statement"].encode("utf-8")),
            f"{claim_id}: statement hash drift",
        )
        _require(
            isinstance(row.get("independent_failure_surface"), str)
            and row["independent_failure_surface"].strip(),
            f"{claim_id}: failure surface missing",
        )
        _require(
            row.get("truth_effect") in {"none", "none_until_gateway_admission"},
            f"{claim_id}: pre-admission node claims truth",
        )
    edge_rows = dag.get("dependency_edges")
    _require(isinstance(edge_rows, list), "atomic DAG dependency edges missing")
    edges = []
    for edge in edge_rows:
        _require(isinstance(edge, dict), "atomic DAG edge malformed")
        edges.append((edge.get("source_claim_id"), edge.get("target_claim_id")))
    canonical_order = _topological_order(node_set, edges)
    declared_order = dag.get("topological_order")
    _require(
        isinstance(declared_order, list)
        and len(declared_order) == len(node_set)
        and set(declared_order) == node_set,
        "atomic topological order inventory drift",
    )
    positions = {node_id: index for index, node_id in enumerate(declared_order)}
    _require(
        all(positions[source] < positions[target] for source, target in edges),
        "atomic topological order violates a dependency",
    )
    continuity_status = validate_research_continuity_contract(
        graph=graph,
        node_ids=node_set,
        continuity_contract=continuity_contract,
    )
    return {
        "contract_revision": ATOMIC_PREFLIGHT_REVISION,
        "validation_subject": {
            "kind": "paper",
            "paper_id": graph.get("paper_id"),
            "source_role": "research_draft",
        },
        "counts": {
            "atomic_claims": len(node_set),
            "dependency_edges": len(edges),
            "represented_frontier_claims": len(represented_paper_claims),
        },
        "declared_topological_order_sha256": sha256_json(declared_order),
        "canonical_topological_order_sha256": sha256_json(canonical_order),
        "research_continuity": continuity_status,
        "required_native_path": (
            "Paper stage/review/freeze -> research-draft plan/disposition -> "
            "Candidate -> independent Certification -> Gateway"
        ),
        "compatibility_factbundle_may_substitute": False,
        "fact_effect": "none",
        "truth_effect": "none",
    }


def l3_l4_limited_restoration_contract() -> dict[str, Any]:
    """Return the exact BF-1--BF-3 authority ceiling used by this release."""

    return {
        "contract_revision": "chalxius-brave-future-limited-restoration-1",
        "restored_stages": [
            "BF-1/read-only-L4-repair-lineage-projection",
            "BF-2/L3-dry-run-reassessment",
            "BF-3/one-bounded-persisted-advisory-receipt",
        ],
        "same_frozen_snapshot_required": True,
        "explicit_campaign_activation_and_opt_in_required": True,
        "repeat_blockage_action": "park",
        "forbidden": [
            "ACTIVE-read",
            "second-scheduler",
            "background-loop",
            "automatic-Research-creation",
            "automatic-round-planning",
            "dispatch",
            "Campaign-state-mutation",
            "Candidate-or-Fact-effect",
            "plan_one",
            "execute_one",
        ],
        "truth_effect": "none",
        "fact_effect": "none",
    }


def build_pipeline_receipt(
    *,
    graph: dict[str, Any],
    frontier: dict[str, Any],
    dag: dict[str, Any],
    continuity_contract: dict[str, Any],
    evidence_receipt: dict[str, Any] | None = None,
    successor_receipt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    graph_status = validate_paper_graph_semantics(graph)
    frontier_status = validate_ordered_paper_frontier(graph, frontier)
    atomic_status = validate_atomic_paper_dag(
        graph=graph,
        frontier=frontier,
        dag=dag,
        continuity_contract=continuity_contract,
    )
    evidence_receipt_status = (
        validate_evidence_receipt(
            evidence_receipt, paper_frontier_id=frontier.get("frontier_id")
        )
        if evidence_receipt is not None
        else None
    )
    successor_receipt_status = (
        validate_successor_receipt(
            successor_receipt,
            source_graph_canonical_sha256=graph_status["graph_canonical_sha256"],
        )
        if successor_receipt is not None
        else None
    )
    semantic = {
        "schema_version": 1,
        "contract_revision": PAPER_RESEARCH_PIPELINE_REVISION,
        "project_id": graph.get("project_id"),
        "paper_id": graph.get("paper_id"),
        "source_role": "research_draft",
        "graph_status": graph_status,
        "frontier_status": frontier_status,
        "atomic_status": atomic_status,
        "evidence_receipt_id": (
            evidence_receipt.get("evidence_receipt_id")
            if evidence_receipt is not None
            else None
        ),
        "evidence_receipt_canonical_sha256": (
            evidence_receipt_status["canonical_sha256"]
            if evidence_receipt_status is not None
            else None
        ),
        "native_successor_receipt_id": (
            successor_receipt.get("receipt_id")
            if successor_receipt is not None
            else None
        ),
        "native_successor_receipt_canonical_sha256": (
            successor_receipt_status["canonical_sha256"]
            if successor_receipt_status is not None
            else None
        ),
        "l3_l4_limited_restoration": l3_l4_limited_restoration_contract(),
        "authority_boundary": {
            "preflight_is_truth": False,
            "native_gateway_still_required": True,
            "fact_effect": "none",
            "truth_effect": "none",
        },
    }
    return {**semantic, "pipeline_receipt_id": "ppr-" + sha256_json(semantic)}


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

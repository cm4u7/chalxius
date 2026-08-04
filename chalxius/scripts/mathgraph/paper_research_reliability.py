from __future__ import annotations

import copy
import random
from collections import Counter
from typing import Any, Callable

from .paper_research_pipeline import (
    PaperPipelineError,
    build_pipeline_receipt,
    sha256_json,
    validate_atomic_paper_dag,
    validate_evidence_receipt,
    validate_ordered_paper_frontier,
    validate_paper_graph_semantics,
    validate_successor_receipt,
)


RELIABILITY_MATRIX_REVISION = "chalxius-paper-research-reliability-matrix-2"
MUTATION_CATEGORIES = (
    "paper_graph",
    "ordered_frontier",
    "atomic_dag",
    "research_continuity",
    "evidence_receipt",
    "successor_receipt",
)


def _mutate_graph(graph: dict[str, Any], rng: random.Random, variant: int) -> dict[str, Any]:
    mutated = copy.deepcopy(graph)
    premise_edges = [
        edge for edge in mutated.get("edges", []) if edge.get("relation_type") == "premise_of"
    ]
    source_nodes = [
        node for node in mutated.get("nodes", []) if node.get("object_type") == "source_unit"
    ]
    if variant == 0:
        mutated["graph_kind"] = "reliability-mutation"
    elif variant == 1 and premise_edges:
        edge = premise_edges[rng.randrange(len(premise_edges))]
        edge.setdefault("payload", {})["position"] = 10**9
    elif variant == 2 and source_nodes:
        source = source_nodes[rng.randrange(len(source_nodes))]
        inventory = source.get("payload", {}).get("proposition_inventory", [])
        if inventory:
            component = inventory[rng.randrange(len(inventory))]
            component.setdefault("exact_span", {})["text"] = "reliability-drift"
        else:
            mutated["graph_kind"] = "reliability-mutation"
    elif mutated.get("edges"):
        mutated["edges"].append(copy.deepcopy(mutated["edges"][0]))
    else:
        mutated["graph_kind"] = "reliability-mutation"
    return mutated


def _mutate_frontier(
    frontier: dict[str, Any], rng: random.Random, variant: int
) -> dict[str, Any]:
    mutated = copy.deepcopy(frontier)
    if variant == 0:
        mutated["frontier_id"] = str(mutated.get("frontier_id", "")) + "-drift"
    elif variant == 1:
        mutated.setdefault("counts", {})["claims"] = (
            mutated.get("counts", {}).get("claims", 0) + 1
        )
    elif variant == 2 and mutated.get("claim_frontier"):
        row = mutated["claim_frontier"][rng.randrange(len(mutated["claim_frontier"]))]
        row["statement"] = str(row.get("statement", "")) + " reliability-drift"
    elif variant == 3 and mutated.get("inference_frontier"):
        row = mutated["inference_frontier"][
            rng.randrange(len(mutated["inference_frontier"]))
        ]
        row["premise_order_sha256"] = "0" * 64
    elif mutated.get("topology_edges"):
        row = mutated["topology_edges"][rng.randrange(len(mutated["topology_edges"]))]
        row["dependency_role"] = "reliability-drift"
    else:
        mutated["projection_kind"] = "reliability-drift"
    return mutated


def _mutate_dag(dag: dict[str, Any], rng: random.Random, variant: int) -> dict[str, Any]:
    mutated = copy.deepcopy(dag)
    rows = mutated.get("nodes", [])
    if variant == 0:
        mutated.setdefault("validation_subject", {})["kind"] = "theorem"
    elif variant == 1 and rows:
        rows[rng.randrange(len(rows))]["statement_sha256"] = "0" * 64
    elif variant == 2 and rows:
        claim_id = rows[rng.randrange(len(rows))].get("claim_id")
        mutated.setdefault("dependency_edges", []).append(
            {"source_claim_id": claim_id, "target_claim_id": claim_id}
        )
    elif variant == 3:
        mutated["project_id"] = "reliability-drift"
    elif variant == 4 and rows:
        mutated["nodes"].append(copy.deepcopy(rows[rng.randrange(len(rows))]))
    elif mutated.get("topological_order"):
        mutated["topological_order"][0] = "reliability-missing-claim"
    else:
        mutated["source_role"] = "external_finished_publication"
    return mutated


def _mutate_continuity(
    continuity: dict[str, Any], dag: dict[str, Any], variant: int
) -> dict[str, Any]:
    mutated = copy.deepcopy(continuity)
    dag_ids = [row.get("claim_id") for row in dag.get("nodes", []) if row.get("claim_id")]
    required = mutated.get("required_claim_ids", [])
    if variant == 0:
        mutated["required_claim_ids"] = ["reliability-missing-claim"]
    elif variant == 1:
        mutated["target_revision_authorized"] = True
    elif variant == 2:
        mutated["declared_target"] = ""
    elif variant == 3 and dag_ids:
        mutated["forbidden_claim_ids"] = [dag_ids[0]]
    elif variant == 4 and required:
        mutated["required_claim_ids"] = [required[0], required[0]]
    else:
        mutated["domain_profile"] = (
            "mathematics"
            if mutated.get("domain_profile") != "mathematics"
            else "philosophy"
        )
    return mutated


def _mutate_evidence(
    receipt: dict[str, Any], rng: random.Random, variant: int
) -> dict[str, Any]:
    mutated = copy.deepcopy(receipt)
    if variant == 0:
        mutated.setdefault("counts", {})["sources"] = (
            mutated.get("counts", {}).get("sources", 0) + 1
        )
    elif variant == 1:
        mutated["unreviewed_extension"] = True
    elif variant == 2:
        mutated.setdefault("authority_boundary", {})["truth_effect"] = "fact"
    elif variant == 3 and mutated.get("claims"):
        row = mutated["claims"][rng.randrange(len(mutated["claims"]))]
        row["witness_sha256"] = "0" * 64
    elif variant == 4 and mutated.get("sources"):
        row = mutated["sources"][rng.randrange(len(mutated["sources"]))]
        row["payload_sha256"] = "0" * 64
    else:
        mutated["evidence_receipt_id"] = "pev-reliability-drift"
    return mutated


def _mutate_successor(
    receipt: dict[str, Any], variant: int
) -> dict[str, Any]:
    mutated = copy.deepcopy(receipt)
    if variant == 0:
        extension = mutated.setdefault("source_component_and_inference_materialization", {})
        extension["hierarchy_atom_count"] = extension.get("hierarchy_atom_count", 0) + 1
    elif variant == 1:
        mutated["unreviewed_extension"] = True
    elif variant == 2:
        mutated["truth_effect"] = "fact"
    elif variant == 3:
        mutated["source_graph_canonical_sha256"] = "0" * 64
    elif variant == 4:
        mutated["historical_rewrite"] = True
    else:
        mutated["receipt_id"] = "rds-reliability-drift"
    return mutated


def run_paper_research_reliability_matrix(
    *,
    graph: dict[str, Any],
    frontier: dict[str, Any],
    dag: dict[str, Any],
    continuity_contract: dict[str, Any],
    evidence_receipt: dict[str, Any],
    successor_receipt: dict[str, Any],
    mutations: int = 1200,
    seed: int = 6202,
) -> dict[str, Any]:
    """Run deterministic, domain-neutral negative tests over one real pipeline."""

    if not isinstance(mutations, int) or isinstance(mutations, bool) or mutations <= 0:
        raise PaperPipelineError("reliability mutation count must be positive")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise PaperPipelineError("reliability seed must be an integer")
    baseline = build_pipeline_receipt(
        graph=graph,
        frontier=frontier,
        dag=dag,
        continuity_contract=continuity_contract,
        evidence_receipt=evidence_receipt,
        successor_receipt=successor_receipt,
    )
    graph_status = validate_paper_graph_semantics(graph)
    rng = random.Random(seed)
    category_counts = {
        name: {"attempted": 0, "killed": 0, "survived": 0, "harness_errors": 0}
        for name in MUTATION_CATEGORIES
    }
    error_signatures: dict[str, Counter[str]] = {
        name: Counter() for name in MUTATION_CATEGORIES
    }
    survivors: list[dict[str, Any]] = []
    harness_errors: list[dict[str, Any]] = []

    for index in range(mutations):
        category = MUTATION_CATEGORIES[index % len(MUTATION_CATEGORIES)]
        variant = rng.randrange(6)
        category_counts[category]["attempted"] += 1
        validator: Callable[[], Any]
        if category == "paper_graph":
            mutated = _mutate_graph(graph, rng, variant % 4)
            validator = lambda mutated=mutated: validate_paper_graph_semantics(mutated)
        elif category == "ordered_frontier":
            mutated = _mutate_frontier(frontier, rng, variant % 5)
            validator = lambda mutated=mutated: validate_ordered_paper_frontier(
                graph, mutated
            )
        elif category == "atomic_dag":
            mutated = _mutate_dag(dag, rng, variant)
            validator = lambda mutated=mutated: validate_atomic_paper_dag(
                graph=graph,
                frontier=frontier,
                dag=mutated,
                continuity_contract=continuity_contract,
            )
        elif category == "research_continuity":
            mutated = _mutate_continuity(continuity_contract, dag, variant)
            validator = lambda mutated=mutated: validate_atomic_paper_dag(
                graph=graph,
                frontier=frontier,
                dag=dag,
                continuity_contract=mutated,
            )
        elif category == "evidence_receipt":
            mutated = _mutate_evidence(evidence_receipt, rng, variant)
            validator = lambda mutated=mutated: validate_evidence_receipt(
                mutated, paper_frontier_id=frontier["frontier_id"]
            )
        else:
            mutated = _mutate_successor(successor_receipt, variant)
            validator = lambda mutated=mutated: validate_successor_receipt(
                mutated,
                source_graph_canonical_sha256=graph_status[
                    "graph_canonical_sha256"
                ],
                source_graph=graph,
            )
        try:
            validator()
        except PaperPipelineError as exc:
            category_counts[category]["killed"] += 1
            error_signatures[category][str(exc)] += 1
        except Exception as exc:  # pragma: no cover - reported, never credited as kill
            category_counts[category]["harness_errors"] += 1
            if len(harness_errors) < 20:
                harness_errors.append(
                    {
                        "index": index,
                        "category": category,
                        "variant": variant,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
        else:
            category_counts[category]["survived"] += 1
            if len(survivors) < 20:
                survivors.append(
                    {"index": index, "category": category, "variant": variant}
                )

    killed = sum(row["killed"] for row in category_counts.values())
    survived = sum(row["survived"] for row in category_counts.values())
    harness_error_count = sum(
        row["harness_errors"] for row in category_counts.values()
    )
    semantic = {
        "schema_version": 1,
        "contract_revision": RELIABILITY_MATRIX_REVISION,
        "seed": seed,
        "mutations_requested": mutations,
        "mutations_killed": killed,
        "mutations_survived": survived,
        "harness_error_count": harness_error_count,
        "ok": killed == mutations and survived == 0 and harness_error_count == 0,
        "domain_profile": graph.get("domain_profile"),
        "baseline_pipeline_receipt_id": baseline["pipeline_receipt_id"],
        "input_canonical_sha256": {
            "paper_graph": sha256_json(graph),
            "ordered_frontier": sha256_json(frontier),
            "atomic_dag": sha256_json(dag),
            "research_continuity": sha256_json(continuity_contract),
            "evidence_receipt": sha256_json(evidence_receipt),
            "successor_receipt": sha256_json(successor_receipt),
        },
        "category_results": category_counts,
        "error_signatures": {
            category: [
                {"message": message, "count": count}
                for message, count in counter.most_common()
            ]
            for category, counter in error_signatures.items()
        },
        "survivor_samples": survivors,
        "harness_error_samples": harness_errors,
        "authority_boundary": {
            "result_is_truth": False,
            "result_is_certification": False,
            "native_gateway_still_required": True,
            "fact_effect": "none",
            "truth_effect": "none",
        },
    }
    return {
        **semantic,
        "matrix_receipt_id": "prm-" + sha256_json(semantic),
    }

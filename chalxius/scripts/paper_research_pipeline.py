#!/usr/bin/env python3
"""Run reusable nontruth gates for inherited Paper-led Research."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

sys.dont_write_bytecode = True

from mathgraph.paper_research_pipeline import (
    atomic_write_json,
    build_ordered_paper_frontier,
    build_pipeline_receipt,
    materialize_native_research_draft_successor,
    normalize_delta_receipt,
    validate_ordered_paper_frontier,
    verify_evidence_registry,
)
from mathgraph.paper_research_reliability import (
    run_paper_research_reliability_matrix,
)
from mathgraph.contracts import sha256_json
from mathgraph.research_draft import (
    validate_mathematical_refinement_dag,
    validate_mathematical_target_policy,
)


CLI_PIPELINE_RECEIPT_REVISION = "chalxius-paper-research-pipeline-3"


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON input must be an object: {path}")
    return value


def validate_mathematical_progress_input(
    *,
    graph: dict[str, Any],
    dag: dict[str, Any],
    continuity_contract: dict[str, Any],
    progress_input: dict[str, Any] | None,
) -> dict[str, Any]:
    """Bind typed mathematical progress to the existing exact-target adapter."""

    profile = graph.get("domain_profile")
    if profile != "mathematics":
        if progress_input is not None:
            raise ValueError(
                "mathematical progress is not applicable outside the mathematics adapter"
            )
        return {
            "applicability": "not_applicable",
            "domain_profile": profile,
            "stance_preservation_required": profile == "philosophy",
            "truth_effect": "none",
        }
    if progress_input is None:
        raise ValueError(
            "mathematics preflight requires an exact target and typed refinement DAG"
        )
    if not isinstance(progress_input, dict) or set(progress_input) != {
        "target_policy",
        "refinement_dag",
    }:
        raise ValueError("mathematical progress input fields are not exact")
    if (
        continuity_contract.get("domain_profile") != "mathematics"
        or continuity_contract.get("continuity_mode") != "mathematical_target"
    ):
        raise ValueError("mathematical progress cannot replace another continuity adapter")
    invariants = continuity_contract.get("domain_invariants")
    if not isinstance(invariants, dict):
        raise ValueError("mathematical continuity invariants are missing")
    dag_nodes = dag.get("nodes")
    if not isinstance(dag_nodes, list):
        raise ValueError("atomic Paper DAG nodes are missing")
    available_claim_ids = {
        item.get("claim_id")
        for item in dag_nodes
        if isinstance(item, dict) and isinstance(item.get("claim_id"), str)
    }
    target_claim_ids = set(invariants.get("target_claim_ids", []))
    policy = validate_mathematical_target_policy(
        progress_input["target_policy"],
        available_claim_ids=available_claim_ids,
        exact_target_claim_ids=target_claim_ids,
    )
    if policy["exact_target_statement"] != continuity_contract.get("declared_target"):
        raise ValueError("mathematical target statement drifts from research continuity")
    if set(policy["hypothesis_claim_ids"]) != set(
        invariants.get("hypothesis_claim_ids", [])
    ):
        raise ValueError("mathematical hypothesis set drifts from research continuity")
    quantifier_claim_ids = {
        claim_id
        for binding in policy["quantifier_bindings"]
        for claim_id in binding["source_claim_ids"]
    }
    if quantifier_claim_ids != set(invariants.get("quantifier_scope_claim_ids", [])):
        raise ValueError("mathematical quantifier scope drifts from research continuity")
    refinement = validate_mathematical_refinement_dag(
        progress_input["refinement_dag"], target_policy=policy
    )
    return {
        "applicability": "required_and_validated",
        "domain_profile": "mathematics",
        "target_policy_sha256": sha256_json(policy),
        "exact_target_root_sha256": sha256_json(refinement["root_target"]),
        "root_resolution_status": refinement["root_target"]["resolution_status"],
        "original_target_open": refinement["root_target"]["original_target_open"],
        "progress_class": refinement["progress_class"],
        "refinement_dag_sha256": refinement["refinement_dag_sha256"],
        "weakening_closes_exact_target": False,
        "stance_preservation_required": False,
        "truth_effect": "none",
    }


def build_cli_pipeline_receipt(
    *,
    graph: dict[str, Any],
    frontier: dict[str, Any],
    dag: dict[str, Any],
    continuity_contract: dict[str, Any],
    mathematical_progress: dict[str, Any] | None,
    evidence_receipt: dict[str, Any] | None,
    successor_receipt: dict[str, Any] | None,
) -> dict[str, Any]:
    """Run the native preflight and bind the domain-specific progress result."""

    progress_status = validate_mathematical_progress_input(
        graph=graph,
        dag=dag,
        continuity_contract=continuity_contract,
        progress_input=mathematical_progress,
    )
    native = build_pipeline_receipt(
        graph=graph,
        frontier=frontier,
        dag=dag,
        continuity_contract=continuity_contract,
        evidence_receipt=evidence_receipt,
        successor_receipt=successor_receipt,
    )
    semantic = {
        **{
            key: value
            for key, value in native.items()
            if key not in {"pipeline_receipt_id", "contract_revision"}
        },
        "contract_revision": CLI_PIPELINE_RECEIPT_REVISION,
        "domain_progress_binding": progress_status,
        "native_pipeline_receipt_id": native["pipeline_receipt_id"],
        "native_pipeline_receipt_sha256": sha256_json(native),
    }
    return {**semantic, "pipeline_receipt_id": "ppr-" + sha256_json(semantic)}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    frontier = sub.add_parser(
        "frontier", help="project an order-preserving Paper research frontier"
    )
    frontier.add_argument("--graph", type=Path, required=True)
    frontier.add_argument("--headline", action="append", required=True)
    frontier.add_argument("--output", type=Path, required=True)

    verify = sub.add_parser(
        "frontier-verify", help="recompute and verify an ordered frontier"
    )
    verify.add_argument("--graph", type=Path, required=True)
    verify.add_argument("--frontier", type=Path, required=True)

    successor = sub.add_parser(
        "successor", help="materialize a native research_draft successor bundle"
    )
    successor.add_argument("--project-root", type=Path, required=True)
    successor.add_argument("--graph", type=Path, required=True)
    successor.add_argument("--activation", type=Path, required=True)
    successor.add_argument("--actor", required=True)
    successor.add_argument("--builder-context-id", required=True)
    successor.add_argument("--bundle-output", type=Path, required=True)
    successor.add_argument("--receipt-output", type=Path, required=True)

    evidence = sub.add_parser(
        "evidence", help="verify identity and claim-level retained evidence"
    )
    evidence.add_argument("--project-root", type=Path, required=True)
    evidence.add_argument("--registry", type=Path, required=True)
    evidence.add_argument("--frontier", type=Path, required=True)
    evidence.add_argument("--output", type=Path, required=True)

    preflight = sub.add_parser(
        "preflight",
        help="bind Paper graph, frontier, evidence, research continuity, and atomic DAG",
    )
    preflight.add_argument("--graph", type=Path, required=True)
    preflight.add_argument("--frontier", type=Path, required=True)
    preflight.add_argument("--dag", type=Path, required=True)
    preflight_continuity = preflight.add_mutually_exclusive_group(required=True)
    preflight_continuity.add_argument("--continuity", type=Path)
    preflight_continuity.add_argument(
        "--stance", dest="continuity", type=Path, help=argparse.SUPPRESS
    )
    preflight.add_argument("--evidence-receipt", type=Path)
    preflight.add_argument("--successor-receipt", type=Path)
    preflight.add_argument(
        "--mathematical-progress",
        type=Path,
        help=(
            "required only for mathematics: exact target policy plus typed "
            "refinement DAG; weaker results remain non-closing progress"
        ),
    )
    preflight.add_argument("--output", type=Path, required=True)

    delta = sub.add_parser(
        "delta-normalize", help="normalize a heterogeneous successor delta receipt"
    )
    delta.add_argument("--input", type=Path, required=True)
    delta.add_argument("--output", type=Path, required=True)

    matrix = sub.add_parser(
        "reliability-matrix",
        help="run deterministic domain-neutral negative tests over one Paper pipeline",
    )
    matrix.add_argument("--graph", type=Path, required=True)
    matrix.add_argument("--frontier", type=Path, required=True)
    matrix.add_argument("--dag", type=Path, required=True)
    matrix_continuity = matrix.add_mutually_exclusive_group(required=True)
    matrix_continuity.add_argument("--continuity", type=Path)
    matrix_continuity.add_argument(
        "--stance", dest="continuity", type=Path, help=argparse.SUPPRESS
    )
    matrix.add_argument("--evidence-receipt", type=Path, required=True)
    matrix.add_argument("--successor-receipt", type=Path, required=True)
    matrix.add_argument(
        "--mathematical-progress",
        type=Path,
        help="required for a mathematics reliability baseline",
    )
    matrix.add_argument("--mutations", type=int, default=1200)
    matrix.add_argument("--seed", type=int, default=6202)
    matrix.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.command == "frontier":
        result = build_ordered_paper_frontier(
            _object(args.graph), headline_claim_ids=args.headline
        )
        atomic_write_json(args.output, result)
    elif args.command == "frontier-verify":
        result = validate_ordered_paper_frontier(
            _object(args.graph), _object(args.frontier)
        )
    elif args.command == "successor":
        bundle, receipt = materialize_native_research_draft_successor(
            _object(args.graph),
            actor=args.actor,
            builder_context_id=args.builder_context_id,
            activation_record=_object(args.activation),
            project_root=args.project_root,
        )
        atomic_write_json(args.bundle_output, bundle)
        atomic_write_json(args.receipt_output, receipt)
        result = receipt
    elif args.command == "evidence":
        result = verify_evidence_registry(
            project_root=args.project_root,
            registry=_object(args.registry),
            frontier=_object(args.frontier),
        )
        atomic_write_json(args.output, result)
    elif args.command == "preflight":
        graph = _object(args.graph)
        dag = _object(args.dag)
        result = build_cli_pipeline_receipt(
            graph=graph,
            frontier=_object(args.frontier),
            dag=dag,
            continuity_contract=_object(args.continuity),
            mathematical_progress=(
                _object(args.mathematical_progress)
                if args.mathematical_progress
                else None
            ),
            evidence_receipt=(
                _object(args.evidence_receipt) if args.evidence_receipt else None
            ),
            successor_receipt=(
                _object(args.successor_receipt) if args.successor_receipt else None
            ),
        )
        atomic_write_json(args.output, result)
    elif args.command == "delta-normalize":
        result = normalize_delta_receipt(_object(args.input))
        atomic_write_json(args.output, result)
    elif args.command == "reliability-matrix":
        graph = _object(args.graph)
        dag = _object(args.dag)
        continuity = _object(args.continuity)
        progress_status = validate_mathematical_progress_input(
            graph=graph,
            dag=dag,
            continuity_contract=continuity,
            progress_input=(
                _object(args.mathematical_progress)
                if args.mathematical_progress
                else None
            ),
        )
        result = run_paper_research_reliability_matrix(
            graph=graph,
            frontier=_object(args.frontier),
            dag=dag,
            continuity_contract=continuity,
            evidence_receipt=_object(args.evidence_receipt),
            successor_receipt=_object(args.successor_receipt),
            mutations=args.mutations,
            seed=args.seed,
        )
        result = {**result, "domain_progress_binding": progress_status}
        atomic_write_json(args.output, result)
    else:  # parser and dispatch must remain exactly closed
        raise ValueError(f"unsupported Paper Research command: {args.command}")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())

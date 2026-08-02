#!/usr/bin/env python3
"""Run reusable nontruth gates for inherited Paper-led Research."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

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


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON input must be an object: {path}")
    return value


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
        result = build_pipeline_receipt(
            graph=_object(args.graph),
            frontier=_object(args.frontier),
            dag=_object(args.dag),
            continuity_contract=_object(args.continuity),
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
    else:
        result = run_paper_research_reliability_matrix(
            graph=_object(args.graph),
            frontier=_object(args.frontier),
            dag=_object(args.dag),
            continuity_contract=_object(args.continuity),
            evidence_receipt=_object(args.evidence_receipt),
            successor_receipt=_object(args.successor_receipt),
            mutations=args.mutations,
            seed=args.seed,
        )
        atomic_write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())

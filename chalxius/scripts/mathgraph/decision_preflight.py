#!/usr/bin/env python3
"""Off-project, read-only V5 Certification Decision preflight.

This module intentionally uses only the Python standard library so the exact
file can be copied into a neutral verifier capsule.  It validates bytes and
returns a receipt; it never opens or writes a Chalxius project.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


V5_FINDING_CLASSES: tuple[str, ...] = (
    "mathematical",
    "typing",
    "scope",
    "source_mismatch",
    "source_access",
    "reproducibility",
    "evidence_access",
    "protocol",
    "assurance_scope",
    "coverage",
)


def _exact(value: Any, fields: set[str], pointer: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{pointer or '/'} must be an object")
    missing = sorted(fields.difference(value))
    unexpected = sorted(set(value).difference(fields))
    if missing or unexpected:
        details = [
            *[f"missing={pointer}/{field}" for field in missing],
            *[f"unexpected={pointer}/{field}" for field in unexpected],
        ]
        raise ValueError("fields are not exact: " + "; ".join(details))
    return value


def _strings(value: Any, pointer: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{pointer} must be a list of strings")
    return value


def _finding_ids(decision: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    findings = decision["findings"]
    if not isinstance(findings, list):
        raise ValueError("/findings must be a list")
    for index, raw in enumerate(findings):
        item = _exact(
            raw,
            {"id", "severity", "class", "description", "repair_hint"},
            f"/findings/{index}",
        )
        finding_id = item["id"]
        if not isinstance(finding_id, str) or not finding_id or finding_id in result:
            raise ValueError(f"/findings/{index}/id is empty or duplicated")
        if item["severity"] not in {"critical_error", "gap"}:
            raise ValueError(f"/findings/{index}/severity is invalid")
        if item["class"] not in V5_FINDING_CLASSES:
            raise ValueError(
                f"/findings/{index}/class is invalid; allowed="
                + ",".join(V5_FINDING_CLASSES)
            )
        if not isinstance(item["description"], str) or not item["description"].strip():
            raise ValueError(f"/findings/{index}/description must be nonempty")
        if not isinstance(item["repair_hint"], str):
            raise ValueError(f"/findings/{index}/repair_hint must be a string")
        result.add(finding_id)
    return result


def _check_finding_refs(value: Any, ids: set[str], pointer: str) -> list[str]:
    refs = _strings(value, pointer)
    if len(refs) != len(set(refs)) or not set(refs).issubset(ids):
        raise ValueError(f"{pointer} contains duplicate or unknown finding ids")
    return refs


def validate_decision_against_capsule(
    decision: Any,
    capsule: Any,
) -> dict[str, Any]:
    if not isinstance(capsule, dict):
        raise ValueError("capsule must be an object")
    if capsule.get("schema_version") != 5:
        raise ValueError("capsule schema_version must be 5")
    source_nonpass = capsule.get("source_nonpass_checks", [])
    if not isinstance(source_nonpass, list) or any(
        not isinstance(item, dict) for item in source_nonpass
    ):
        raise ValueError("capsule source_nonpass_checks is invalid")
    top_fields = {
        "schema_version",
        "release_id",
        "release_sha256",
        "capsule_sha256",
        "verdict",
        "findings",
        "check_results",
        "candidate_checks",
        "edge_checks",
        "assurance_matrix",
        "reviewer",
        "host_attestation",
    }
    if source_nonpass:
        top_fields.add("source_check_reconciliation")
    strict_research_draft = "research_draft_ref" in capsule
    if strict_research_draft:
        top_fields.add("parallel_verification_aggregate_id")
    decision = _exact(decision, top_fields, "")
    if decision["schema_version"] != 5:
        raise ValueError("/schema_version must be 5")
    for key in ("release_id", "release_sha256", "capsule_sha256"):
        if decision[key] != capsule[key]:
            raise ValueError(f"/{key} does not match capsule")
    if strict_research_draft and (
        not isinstance(decision["parallel_verification_aggregate_id"], str)
        or not decision["parallel_verification_aggregate_id"].startswith("vag-")
    ):
        raise ValueError("/parallel_verification_aggregate_id is invalid")
    if decision["verdict"] not in {"correct", "reject"}:
        raise ValueError("/verdict must be correct or reject")
    finding_ids = _finding_ids(decision)

    check_results = decision["check_results"]
    if not isinstance(check_results, list):
        raise ValueError("/check_results must be a list")
    seen_checks: set[str] = set()
    checks_clean = True
    for index, raw in enumerate(check_results):
        item = _exact(raw, {"check_id", "status", "findings"}, f"/check_results/{index}")
        check_id = item["check_id"]
        if not isinstance(check_id, str) or not check_id or check_id in seen_checks:
            raise ValueError(f"/check_results/{index}/check_id is empty or duplicated")
        seen_checks.add(check_id)
        if item["status"] not in {"pass", "fail"}:
            raise ValueError(f"/check_results/{index}/status is invalid")
        _check_finding_refs(item["findings"], finding_ids, f"/check_results/{index}/findings")
        checks_clean = checks_clean and item["status"] == "pass"
    if seen_checks != set(capsule["required_checks"]):
        raise ValueError("/check_results does not exactly cover capsule required_checks")

    candidates = decision["candidate_checks"]
    if not isinstance(candidates, list):
        raise ValueError("/candidate_checks must be a list")
    seen_facts: set[str] = set()
    candidates_clean = True
    for index, raw in enumerate(candidates):
        item = _exact(raw, {"fact_id", "verdict", "findings"}, f"/candidate_checks/{index}")
        fact_id = item["fact_id"]
        if not isinstance(fact_id, str) or fact_id in seen_facts:
            raise ValueError(f"/candidate_checks/{index}/fact_id is invalid or duplicated")
        seen_facts.add(fact_id)
        if item["verdict"] not in {"correct", "reject"}:
            raise ValueError(f"/candidate_checks/{index}/verdict is invalid")
        _check_finding_refs(item["findings"], finding_ids, f"/candidate_checks/{index}/findings")
        candidates_clean = candidates_clean and item["verdict"] == "correct"
    if seen_facts != set(capsule["fact_ids"]):
        raise ValueError("/candidate_checks does not exactly cover capsule fact_ids")

    edges = decision["edge_checks"]
    if not isinstance(edges, list):
        raise ValueError("/edge_checks must be a list")
    seen_edges: set[tuple[str, str]] = set()
    edges_clean = True
    for index, raw in enumerate(edges):
        item = _exact(
            raw,
            {"predecessor_fact_id", "fact_id", "verdict", "findings"},
            f"/edge_checks/{index}",
        )
        edge = (item["predecessor_fact_id"], item["fact_id"])
        if not all(isinstance(value, str) for value in edge) or edge in seen_edges:
            raise ValueError(f"/edge_checks/{index} edge is invalid or duplicated")
        seen_edges.add(edge)
        if item["verdict"] not in {"correct", "reject"}:
            raise ValueError(f"/edge_checks/{index}/verdict is invalid")
        _check_finding_refs(item["findings"], finding_ids, f"/edge_checks/{index}/findings")
        edges_clean = edges_clean and item["verdict"] == "correct"
    if seen_edges != {tuple(item) for item in capsule["internal_edges"]}:
        raise ValueError("/edge_checks does not exactly cover capsule internal_edges")

    requested = capsule.get("requested_assurance")
    if not isinstance(requested, dict):
        raise ValueError("capsule requested_assurance is invalid")
    subject = requested.get("validation_subject")
    if not isinstance(subject, dict) or subject.get("kind") not in {
        "theorem",
        "paper",
    }:
        raise ValueError("capsule validation subject is invalid")
    paper_requested = subject["kind"] == "paper"
    intermediate_ids = capsule.get("intermediate_fact_ids")
    if not isinstance(intermediate_ids, list) or any(
        not isinstance(item, str) for item in intermediate_ids
    ):
        raise ValueError("capsule intermediate_fact_ids is invalid")
    expected_assurance_matrix = {
        "paper_source_fidelity": (
            "complete" if paper_requested else "not_requested"
        ),
        "paper_graph_structure": (
            "complete" if paper_requested else "not_requested"
        ),
        "paper_audit": "complete" if paper_requested else "not_requested",
        "root_fact_admission": "candidate",
        "intermediate_fact_coverage": {
            "admitted_count": 0,
            "required_count": len(intermediate_ids),
        },
        "validation_granularity": requested.get("validation_granularity"),
    }
    if decision["assurance_matrix"] != expected_assurance_matrix:
        raise ValueError("/assurance_matrix does not match the capsule")

    reviewer = decision["reviewer"]
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("/reviewer must be nonempty")
    if reviewer.casefold() in {
        str(item).casefold() for item in capsule["excluded_verifier_ids"]
    }:
        raise ValueError("/reviewer is excluded by the capsule")
    attestation = _exact(
        decision["host_attestation"],
        {"host", "agent_id", "isolation", "fork_turns", "allowed_capsule_sha256"},
        "/host_attestation",
    )
    for key in ("host", "agent_id", "isolation", "fork_turns"):
        if not isinstance(attestation[key], str) or not attestation[key].strip():
            raise ValueError(f"/host_attestation/{key} must be nonempty")
    if (
        attestation["agent_id"] != reviewer
        or attestation["isolation"] != "fresh_context"
        or attestation["fork_turns"] != "none"
        or attestation["allowed_capsule_sha256"] != capsule["capsule_sha256"]
    ):
        raise ValueError("/host_attestation is not the exact fresh-context attestation")

    reconciliation_clean = True
    if source_nonpass:
        rows = decision["source_check_reconciliation"]
        if not isinstance(rows, list):
            raise ValueError("/source_check_reconciliation must be a list")
        expected = {
            (item["fact_id"], item["source_key"], item["check_kind"], item["status"])
            for item in source_nonpass
        }
        seen: set[tuple[str, str, str, str]] = set()
        for index, raw in enumerate(rows):
            item = _exact(
                raw,
                {
                    "fact_id",
                    "source_key",
                    "check_kind",
                    "status",
                    "disposition",
                    "rationale",
                },
                f"/source_check_reconciliation/{index}",
            )
            identity = tuple(
                item[key] for key in ("fact_id", "source_key", "check_kind", "status")
            )
            if identity not in expected or identity in seen:
                raise ValueError(
                    f"/source_check_reconciliation/{index} is unknown or duplicated"
                )
            seen.add(identity)
            if item["disposition"] not in {
                "bound_correction",
                "scope_restriction",
                "reject",
            }:
                raise ValueError(
                    f"/source_check_reconciliation/{index}/disposition is invalid"
                )
            if not isinstance(item["rationale"], str) or not item["rationale"].strip():
                raise ValueError(
                    f"/source_check_reconciliation/{index}/rationale must be nonempty"
                )
            reconciliation_clean = reconciliation_clean and item["disposition"] != "reject"
        if seen != expected:
            raise ValueError("source reconciliation does not exactly cover all non-pass checks")

    clean = (
        not finding_ids
        and checks_clean
        and candidates_clean
        and edges_clean
        and reconciliation_clean
    )
    if decision["verdict"] == "correct" and not clean:
        raise ValueError("a correct decision must be completely clean")
    if decision["verdict"] == "reject" and clean:
        raise ValueError("a rejecting decision requires a failed check")
    return {
        "valid": True,
        "release_id": capsule["release_id"],
        "capsule_sha256": capsule["capsule_sha256"],
        "verdict": decision["verdict"],
        "project_effect": "none",
        "truth_effect": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capsule", type=Path, required=True)
    parser.add_argument("--decision", type=Path, required=True)
    args = parser.parse_args()
    capsule = json.loads(args.capsule.read_text(encoding="utf-8"))
    decision = json.loads(args.decision.read_text(encoding="utf-8"))
    print(
        json.dumps(
            validate_decision_against_capsule(decision, capsule),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

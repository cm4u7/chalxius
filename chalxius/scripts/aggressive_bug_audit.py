#!/usr/bin/env python3
"""Run focused V5 boundary tests and prove that they kill critical mutants.

The harness copies the engine to a temporary directory, applies one deliberate
off-by-one or exact-set defect at a time, and runs the smallest regression that
must detect it.  It never edits the candidate or an installed skill tree.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Mutant:
    name: str
    old: str
    new: str
    test: str
    target: str = "mathgraph/v5_lifecycle.py"


TEST_MODULE = "chalxius.tests.test_v5_lifecycle.V5LifecycleTests"
MUTANTS = (
    Mutant(
        name="frontier_limit_minus_one",
        old="        return visible[:limit]\n",
        new="        return visible[: max(0, limit - 1)]\n",
        test=(
            f"{TEST_MODULE}."
            "test_frontier_limits_and_explicit_last_entry_have_no_truncation_error"
        ),
    ),
    Mutant(
        name="coverage_allows_n_plus_one",
        old="        if set(load_bearing) != covered:\n",
        new="        if set(load_bearing).difference(covered):\n",
        test=(
            f"{TEST_MODULE}."
            "test_paper_nodewise_release_binds_current_logic_audit_and_coverage"
        ),
    ),
    Mutant(
        name="candidate_mapping_allows_missing_fact",
        old="            if mapped_fact_ids != set(facts):\n",
        new="            if mapped_fact_ids.difference(set(facts)):\n",
        test=(
            f"{TEST_MODULE}."
            "test_paper_nodewise_release_binds_current_logic_audit_and_coverage"
        ),
    ),
    Mutant(
        name="required_check_duplicate_not_rejected",
        old=(
            "        if len(required_checks) != len(set(required_checks)):\n"
            "            raise ValueError(\"verification required checks are duplicated\")\n"
        ),
        new=(
            "        if False and len(required_checks) != len(set(required_checks)):\n"
            "            raise ValueError(\"verification required checks are duplicated\")\n"
        ),
        test=(
            f"{TEST_MODULE}."
            "test_certification_panels_require_exact_counts_without_duplicates"
        ),
    ),
    Mutant(
        name="certification_check_panel_allows_missing",
        old=(
            "        if {item[\"check_id\"] for item in normalized_check_results} != set(\n"
            "            capsule[\"required_checks\"]\n"
            "        ):\n"
        ),
        new=(
            "        if {item[\"check_id\"] for item in normalized_check_results}.difference(\n"
            "            set(capsule[\"required_checks\"])\n"
            "        ):\n"
        ),
        test=(
            f"{TEST_MODULE}."
            "test_certification_panels_require_exact_counts_without_duplicates"
        ),
    ),
    Mutant(
        name="certification_edge_panel_allows_missing",
        old="        if actual_edges != expected_edges:\n",
        new="        if actual_edges.difference(expected_edges):\n",
        test=(
            f"{TEST_MODULE}."
            "test_certification_panels_require_exact_counts_without_duplicates"
        ),
    ),
    Mutant(
        name="paper_ref_allows_unbound_load_bearing_node",
        old=(
            "        unbound = sorted(load_bearing.difference(bound_target_ids))\n"
        ),
        new="        unbound = []\n",
        test=(
            f"{TEST_MODULE}."
            "test_paper_nodewise_release_binds_current_logic_audit_and_coverage"
        ),
    ),
    Mutant(
        name="series_order_budget_accepts_declared_retention",
        old=(
            "        required = target_power - (valuation_sum - lowest)\n"
        ),
        new=(
            "        required = min(\n"
            "            target_power - (valuation_sum - lowest), retained\n"
            "        )\n"
        ),
        test=(
            f"{TEST_MODULE}."
            "test_v5_series_order_budget_rejects_xy_swap_undertruncation"
        ),
        target="mathgraph/computations.py",
    ),
)


def _run_test(*, repo: Path, scripts: Path, test: str) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(scripts), environment.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    return subprocess.run(
        [sys.executable, "-m", "unittest", test],
        cwd=repo,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def main() -> int:
    candidate_root = Path(__file__).resolve().parents[1]
    repo = candidate_root.parent
    source_scripts = candidate_root / "scripts"
    results: list[dict[str, object]] = []

    baseline_tests = sorted({mutant.test for mutant in MUTANTS})
    for test in baseline_tests:
        baseline = _run_test(repo=repo, scripts=source_scripts, test=test)
        if baseline.returncode != 0:
            print(baseline.stdout, file=sys.stderr)
            raise SystemExit(f"baseline regression failed before mutation: {test}")

    for mutant in MUTANTS:
        with tempfile.TemporaryDirectory(prefix="chalxius-v5-mutant-") as temporary:
            copied_scripts = Path(temporary) / "scripts"
            shutil.copytree(source_scripts, copied_scripts)
            target = copied_scripts / mutant.target
            text = target.read_text(encoding="utf-8")
            occurrences = text.count(mutant.old)
            if occurrences != 1:
                raise SystemExit(
                    f"mutant {mutant.name} expected one target, found {occurrences}"
                )
            target.write_text(text.replace(mutant.old, mutant.new), encoding="utf-8")
            outcome = _run_test(
                repo=repo,
                scripts=copied_scripts,
                test=mutant.test,
            )
            killed = outcome.returncode != 0
            results.append(
                {
                    "mutant": mutant.name,
                    "test": mutant.test,
                    "killed": killed,
                    "returncode": outcome.returncode,
                }
            )
            if not killed:
                print(outcome.stdout, file=sys.stderr)

    report = {
        "schema_version": 1,
        "scope": "V5 truncation, exact-set, and off-by-one critical guards",
        "mutants": results,
        "killed": sum(bool(item["killed"]) for item in results),
        "total": len(results),
        "ok": all(bool(item["killed"]) for item in results),
        "candidate_unchanged": True,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

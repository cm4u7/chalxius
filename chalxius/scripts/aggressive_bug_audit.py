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


TEST_MODULE = "tests.test_v5_lifecycle.V5LifecycleTests"
CONTEXT_TEST_MODULE = (
    "tests.test_chalxius_044_context.Chalxius044ContextTests"
)
FIELD_TEST_MODULE = "tests.test_bttf_field_repairs.BTTFFieldRepairTests"
READER_TEST_MODULE = "tests.test_reader_html.ReaderHtmlRenderTests"
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
    Mutant(
        name="background_snapshot_hash_bypass",
        old='    if sha256_bytes(raw) != binding["snapshot_sha256"]:\n',
        new='    if False and sha256_bytes(raw) != binding["snapshot_sha256"]:\n',
        test=(
            f"{CONTEXT_TEST_MODULE}."
            "test_background_is_indexed_snapshotted_and_rehydratable"
        ),
        target="mathgraph/project_background.py",
    ),
    Mutant(
        name="mode_free_text_becomes_route",
        old="            if suggestion in WORK_MODES:\n",
        new=(
            "            if suggestion in WORK_MODES or "
            "suggestion.startswith('prove'):\n"
        ),
        test=(
            f"{CONTEXT_TEST_MODULE}."
            "test_l2_rejects_free_text_as_a_route_and_falls_back_visibly"
        ),
    ),
    Mutant(
        name="mode_assurance_equivalence_bypass",
        old='                reason = "would_change_assurance_contract"\n',
        new="                reason = None\n",
        test=(
            f"{CONTEXT_TEST_MODULE}."
            "test_l2_rejects_free_text_as_a_route_and_falls_back_visibly"
        ),
    ),
    Mutant(
        name="mode_program_math_review_equivalence_bypass",
        old=(
            '                reason = "would_change_program_math_adverse_review"\n'
        ),
        new="                reason = None\n",
        test=(
            f"{CONTEXT_TEST_MODULE}."
            "test_l2_rejects_free_text_as_a_route_and_falls_back_visibly"
        ),
    ),
    Mutant(
        name="promoted_origin_activity_bypass",
        old="            if node_id not in current_nodes:\n",
        new="            if False and node_id not in current_nodes:\n",
        test=(
            f"{CONTEXT_TEST_MODULE}."
            "test_l1_promoted_query_and_l2_mode_hint_are_exact_and_bounded"
        ),
    ),
    Mutant(
        name="promoted_query_mixed_round_allowed",
        old="        if promoted and len(selected) != 1:\n",
        new="        if False and promoted and len(selected) != 1:\n",
        test=(
            f"{CONTEXT_TEST_MODULE}."
            "test_l1_promoted_query_and_l2_mode_hint_are_exact_and_bounded"
        ),
    ),
    Mutant(
        name="host_background_capability_leak",
        old=(
            '    "host": {\n'
            '        "pulse-dispatch",\n'
        ),
        new=(
            '    "host": {\n'
            '        "project-background-read",\n'
            '        "pulse-dispatch",\n'
        ),
        test=(
            f"{CONTEXT_TEST_MODULE}."
            "test_host_role_is_unchanged_and_v4_workers_do_not_expand"
        ),
        target="mathgraph/roles.py",
    ),
    Mutant(
        name="worker_reads_live_background_without_frozen_card",
        old=(
            "            if args.task_card is None:\n"
            '                if args.role not in {"main", "operator"}:\n'
        ),
        new=(
            "            if args.task_card is None:\n"
            '                if args.role not in {"main", "operator", "worker"}:\n'
        ),
        test=(
            f"{CONTEXT_TEST_MODULE}."
            "test_background_cli_exposes_index_and_exact_frozen_chunk"
        ),
        target="mathgraph/cli.py",
    ),
    Mutant(
        name="current_source_capability_requirement_bypassed",
        old=(
            "            if self._research_is_source_dependent(prospective_record) and not artifacts:\n"
        ),
        new=(
            "            if False and self._research_is_source_dependent(prospective_record) and not artifacts:\n"
        ),
        test=(
            f"{FIELD_TEST_MODULE}."
            "test_chx001_current_source_capability_and_legacy_planning_boundary"
        ),
    ),
    Mutant(
        name="worker_runtime_mismatch_bypassed",
        old="    if runtime != _runtime_binding():\n",
        new="    if False and runtime != _runtime_binding():\n",
        test=(
            f"{FIELD_TEST_MODULE}."
            "test_chx002_task_card_binds_candidate_runtime_and_ledger_fails_closed"
        ),
        target="chx_ledger.py",
    ),
    Mutant(
        name="adverse_evidence_provenance_dropped",
        old=(
            "                if (\n"
            "                    record[\"kind\"] not in adverse_kinds\n"
            "                    and not self._research_is_adverse_assignment(record)\n"
            "                ) or research_id in selected:\n"
        ),
        new=(
            "                if record[\"kind\"] not in adverse_kinds or research_id in selected:\n"
        ),
        test=(
            f"{FIELD_TEST_MODULE}."
            "test_chx003_evidence_return_from_refute_assignment_remains_adverse"
        ),
    ),
    Mutant(
        name="append_target_project_id_check_bypassed",
        old='    if inventory["source_project_id"] != expected_project_id:\n',
        new='    if False and inventory["source_project_id"] != expected_project_id:\n',
        test=(
            f"{FIELD_TEST_MODULE}."
            "test_chx004_inventory_and_append_target_are_explicit_read_only_routes"
        ),
        target="mathgraph/cli.py",
    ),
    Mutant(
        name="fact_inventory_leaked_to_main_role",
        old='    "main": {\n',
        new=(
            '    "main": {\n'
            '        "fact-graph-inventory",\n'
            '        "fact-graph-append-target",\n'
        ),
        test=(
            f"{FIELD_TEST_MODULE}."
            "test_chx004_inventory_and_append_target_are_explicit_read_only_routes"
        ),
        target="mathgraph/roles.py",
    ),
    Mutant(
        name="legacy_named_premise_condition_not_detected",
        old=(
            '    r"under\\s+(?:the\\s+)?(?:[A-Za-z][A-Za-z0-9_-]*\\s+){0,4}"\n'
        ),
        new='    r"under\\s+(?:the\\s+)?"\n',
        test=(
            f"{FIELD_TEST_MODULE}."
            "test_chx005_named_legacy_setup_requires_exact_hashed_witness"
        ),
        target="mathgraph/interfaces.py",
    ),
    Mutant(
        name="legacy_named_premise_witness_not_required",
        old=(
            "        required_hypotheses.update(\n"
            "            premise[\"witness_id\"] for premise in legacy_premises\n"
            "        )\n"
        ),
        new="        required_hypotheses.update([])\n",
        test=(
            f"{FIELD_TEST_MODULE}."
            "test_chx005_named_legacy_setup_requires_exact_hashed_witness"
        ),
        target="mathgraph/interfaces.py",
    ),
    Mutant(
        name="release_lineage_snapshot_recurses_through_store",
        old="                    active_facts=_lineage_facts,\n",
        new="                    active_facts=self.store.facts(),\n",
        test=(
            f"{FIELD_TEST_MODULE}."
            "test_chx006_nonempty_successor_contract_uses_nonrecursive_snapshot"
        ),
    ),
    Mutant(
        name="admission_projection_preflight_moved_after_visibility",
        old=(
            "        projection_plan = self._admission_projection_plan(\n"
            "            marker,\n"
            "            release=release,\n"
            "        )\n"
            "        self._preflight_admission_projections(projection_plan)\n"
            "        with self.store.v5_mutation_lock(command=\"fact-admit\"):\n"
        ),
        new=(
            "        projection_plan = self._admission_projection_plan(\n"
            "            marker,\n"
            "            release=release,\n"
            "        )\n"
            "        with self.store.v5_mutation_lock(command=\"fact-admit\"):\n"
        ),
        test=(
            f"{FIELD_TEST_MODULE}."
            "test_chx006_pre_marker_failure_has_no_visibility_and_retry_is_exact"
        ),
    ),
    Mutant(
        name="admission_projection_retry_appends_duplicates",
        old=(
            "            self.store._append_jsonl_once(\n"
            "                self.store.verification_log,\n"
            "                event,\n"
            "                event_id=event[\"event_id\"],\n"
            "            )\n"
        ),
        new=(
            "            self.store._append_jsonl(\n"
            "                self.store.verification_log,\n"
            "                event,\n"
            "            )\n"
        ),
        test=(
            f"{FIELD_TEST_MODULE}."
            "test_chx006_post_marker_partial_retry_is_idempotent_without_duplicates"
        ),
    ),
    Mutant(
        name="aborted_round_still_projects_awaiting_return",
        old=(
            "            elif abort is not None:\n"
            "                state = \"frozen_aborted\"\n"
        ),
        new=(
            "            elif False and abort is not None:\n"
            "                state = \"frozen_aborted\"\n"
        ),
        test=(
            f"{FIELD_TEST_MODULE}."
            "test_aborted_v5_round_status_is_frozen_and_audit_checks_projection"
        ),
    ),
    Mutant(
        name="abort_status_projection_audit_bypassed",
        old=(
            "                if (\n"
            "                    status.get(\"work_unit_state\") != \"aborted\"\n"
        ),
        new=(
            "                if False and (\n"
            "                    status.get(\"work_unit_state\") != \"aborted\"\n"
        ),
        test=(
            f"{FIELD_TEST_MODULE}."
            "test_aborted_v5_round_status_is_frozen_and_audit_checks_projection"
        ),
    ),
    Mutant(
        name="reader_summary_interface_and_math_projection_bypassed",
        old=(
            "    readable = _READER_INTERFACE_ANCHOR_RE.sub(\n"
            "        lambda match: f\"{labels[match.group(1)]} {match.group(2)}.\",\n"
            "        statement,\n"
            "    )\n"
        ),
        new="    readable = statement\n",
        test=(
            f"{FIELD_TEST_MODULE}."
            "test_reader_fact_summary_is_mathjax_ready_and_exact_fact_is_unchanged"
        ),
        target="mathgraph/v5_reader.py",
    ),
    Mutant(
        name="reader_dynamic_radial_memory_bypassed",
        old=(
            "        const memory = dynamicRadialMemoryDisplacement(nodeId, positions.get(nodeId));\n"
        ),
        new="        const memory = null;\n",
        test=(
            f"{READER_TEST_MODULE}."
            "test_revision_thirteen_box_selection_and_group_movement_contract_is_embedded"
        ),
        target="../assets/reader_html_app.js",
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
    repo = candidate_root
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
            copied_root = Path(temporary)
            copied_scripts = copied_root / "scripts"
            shutil.copytree(source_scripts, copied_scripts)
            if mutant.target.startswith("../assets/"):
                shutil.copytree(candidate_root / "assets", copied_root / "assets")
            for identity_name in ("VERSION", "MANIFEST.sha256"):
                shutil.copy2(candidate_root / identity_name, copied_root / identity_name)
            target = (copied_scripts / mutant.target).resolve()
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
        "scope": (
            "V5 truncation, exact-set, context authority, frozen background, "
            "mode equivalence, source capability, adverse provenance, prior-Fact "
            "routing, legacy premises, runtime identity, admission recovery, abort "
            "status projection, Reader math projection, radial-memory layout, and "
            "off-by-one critical guards"
        ),
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

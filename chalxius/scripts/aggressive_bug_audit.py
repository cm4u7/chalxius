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
PAPER_TEST_MODULE = "tests.test_paper_logic_graph.PaperLogicGraphTests"
CAMPAIGN_TEST_MODULE = (
    "tests.test_v5_campaign_envelope.V5CampaignEnvelopeTests"
)
ADVERSE_TEST_MODULE = (
    "tests.test_adverse_routing.AdverseRoutingEvolutionTests"
)
RESEARCH_DRAFT_CONTRACT_TEST_MODULE = (
    "tests.test_research_draft_contracts.ResearchDraftContractTests"
)
RESEARCH_DRAFT_ADMISSION_TEST_MODULE = (
    "tests.test_research_draft_admission.ResearchDraftAdmissionTests"
)
PARALLEL_VERIFICATION_TEST_MODULE = (
    "tests.test_parallel_verification.ParallelVerificationTests"
)
BRAVE_FUTURE_TEST_MODULE = "tests.test_brave_future.BraveFutureTests"
CHX_TEST_MODULE = "tests.test_chx_ledger.CHXRunLedgerTests"
RUNTIME_ARCHIVE_TEST_MODULE = "tests.test_runtime_archive.RuntimeArchiveTests"
V5_EXPERIMENT_TEST_MODULE = "tests.test_v5_experiments.V5ExperimentTests"
RUNTIME_CUTOVER_TEST_MODULE = "tests.test_runtime_cutover.RuntimeCutoverTests"
PAPER_RESEARCH_PIPELINE_TEST_MODULE = (
    "tests.test_paper_research_pipeline.PaperResearchPipelineTests"
)
RUNTIME_COMPATIBILITY_TEST_MODULE = (
    "tests.test_runtime_compatibility.RuntimeCompatibilityClosureTests"
)
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
        name="campaign_frontier_exact_match_bypassed",
        old=(
            "            if (\n"
            "                campaign_id is not None\n"
            "                and record[\"metadata\"].get(\"campaign_id\") != campaign_id\n"
            "            ):\n"
            "                continue\n"
        ),
        new=(
            "            if False and (\n"
            "                campaign_id is not None\n"
            "                and record[\"metadata\"].get(\"campaign_id\") != campaign_id\n"
            "            ):\n"
            "                continue\n"
        ),
        test=(
            f"{CAMPAIGN_TEST_MODULE}."
            "test_explicit_frontier_scope_is_exact_and_active_pointer_is_not_implicit"
        ),
    ),
    Mutant(
        name="campaign_active_pointer_becomes_implicit_v5_scope",
        old=(
            "        if campaign_id is not None:\n"
            "            campaign_id = validate_campaign_id(campaign_id)\n"
            "            self.store.campaigns().status(campaign_id)\n"
            "        bases: dict[str, dict[str, Any]] = {}\n"
        ),
        new=(
            "        campaign_id = campaign_id or self.store.campaigns().active()\n"
            "        if campaign_id is not None:\n"
            "            campaign_id = validate_campaign_id(campaign_id)\n"
            "            self.store.campaigns().status(campaign_id)\n"
            "        bases: dict[str, dict[str, Any]] = {}\n"
        ),
        test=(
            f"{CAMPAIGN_TEST_MODULE}."
            "test_explicit_frontier_scope_is_exact_and_active_pointer_is_not_implicit"
        ),
    ),
    Mutant(
        name="campaign_snapshot_hash_bypass",
        old=(
            "            len(raw) > V5_MAX_CAMPAIGN_SNAPSHOT_BYTES\n"
            "            or sha256_bytes(raw) != digest\n"
        ),
        new=(
            "            len(raw) > V5_MAX_CAMPAIGN_SNAPSHOT_BYTES\n"
            "            or False and sha256_bytes(raw) != digest\n"
        ),
        test=(
            f"{CAMPAIGN_TEST_MODULE}."
            "test_campaign_snapshot_tamper_fails_closed"
        ),
    ),
    Mutant(
        name="campaign_scope_omitted_from_round_manifest",
        old=(
            "            if campaign_scope is not None:\n"
            "                manifest_semantic[\"campaign_scope\"] = campaign_scope\n"
        ),
        new=(
            "            if False and campaign_scope is not None:\n"
            "                manifest_semantic[\"campaign_scope\"] = campaign_scope\n"
        ),
        test=(
            f"{CAMPAIGN_TEST_MODULE}."
            "test_scoped_round_freezes_lightweight_nontruth_campaign_envelope"
        ),
    ),
    Mutant(
        name="campaign_bound_worker_reads_live_status",
        old="                args.bound_campaign_status = frozen_status\n",
        new=(
            "                args.bound_campaign_status = "
            "store.campaigns().status(requested_id)\n"
        ),
        test=(
            f"{CAMPAIGN_TEST_MODULE}."
            "test_scoped_round_freezes_lightweight_nontruth_campaign_envelope"
        ),
        target="mathgraph/cli.py",
    ),
    Mutant(
        name="general_hidden_conjunct_baseline_omitted",
        old="        baseline = list(BASELINE_ATTACK_RULES)\n",
        new="        baseline = list(LEGACY_BASELINE_ATTACK_RULES)\n",
        test=(
            f"{ADVERSE_TEST_MODULE}."
            "test_philosophy_baselines_require_an_explicit_validated_domain"
        ),
        target="mathgraph/adverse_routing.py",
    ),
    Mutant(
        name="philosophy_baselines_activated_by_claim_keyword",
        old=(
            '            "philosophy_active": domain_profile in {"philosophy", "mixed"},\n'
        ),
        new=(
            '            "philosophy_active": domain_profile in {"philosophy", "mixed"} '
            'or "philosophy" in entry["claim"].casefold(),\n'
        ),
        test=(
            f"{ADVERSE_TEST_MODULE}."
            "test_philosophy_baselines_require_an_explicit_validated_domain"
        ),
        target="mathgraph/adverse_routing.py",
    ),
    Mutant(
        name="philosophy_baselines_not_appended_for_exact_domain",
        old='        if philosophy_scope["philosophy_active"]:\n',
        new='        if False and philosophy_scope["philosophy_active"]:\n',
        test=(
            f"{ADVERSE_TEST_MODULE}."
            "test_philosophy_baselines_require_an_explicit_validated_domain"
        ),
        target="mathgraph/adverse_routing.py",
    ),
    Mutant(
        name="philosophy_scope_task_card_drift_bypassed",
        old=(
            "                if any(\n"
            "                    scope[key] != expected_philosophy_scope[key]\n"
            "                    for key in philosophy_scope_fields\n"
            "                ):\n"
        ),
        new=(
            "                if False and any(\n"
            "                    scope[key] != expected_philosophy_scope[key]\n"
            "                    for key in philosophy_scope_fields\n"
            "                ):\n"
        ),
        test=(
            f"{ADVERSE_TEST_MODULE}."
            "test_philosophy_baselines_require_an_explicit_validated_domain"
        ),
        target="mathgraph/adverse_routing.py",
    ),
    Mutant(
        name="paper_edge_delta_diagnostic_removed",
        old='                f"missing_count={len(missing)} extra_count={len(extra)} "\n',
        new='                "missing_count=unknown extra_count=unknown "\n',
        test=(
            f"{PAPER_TEST_MODULE}."
            "test_public_minimal_logic_fixture_and_edge_diff_are_executable"
        ),
        target="mathgraph/paper_logic.py",
    ),
    Mutant(
        name="candidate_release_public_schema_pointer_removed",
        old='                "schema=references/paper_input_contracts.md"\n',
        new='                "schema=unavailable"\n',
        test=(
            f"{TEST_MODULE}."
            "test_candidate_release_exact_field_error_is_publicly_actionable"
        ),
    ),
    Mutant(
        name="worker_return_cli_public_schema_pointer_removed",
        old=(
            '            "references/v5_worker_return_contract.md and "\n'
            '            "assets/worker_return.v5.assurance-no-adverse.template.json"\n'
        ),
        new=(
            '            "schema unavailable and "\n'
            '            "template unavailable"\n'
        ),
        test=(
            f"{TEST_MODULE}."
            "test_public_v5_worker_return_template_and_diagnostics_are_executable"
        ),
        target="mathgraph/cli.py",
    ),
    Mutant(
        name="worker_return_top_level_delta_diagnostic_removed",
        old=(
            '                f"missing={missing}; unknown={unknown}; exact schema: "\n'
            '                "references/v5_worker_return_contract.md"\n'
        ),
        new=(
            '                f"missing={missing}; unknown={unknown}; exact schema: "\n'
            '                "unavailable"\n'
        ),
        test=(
            f"{TEST_MODULE}."
            "test_public_v5_worker_return_template_and_diagnostics_are_executable"
        ),
    ),
    Mutant(
        name="worker_return_disposition_delta_diagnostic_removed",
        old=(
            '                f"unknown={sorted(actual_fields.difference(disposition_fields))}; "\n'
            '                "exact schema: references/v5_worker_return_contract.md"\n'
        ),
        new=(
            '                f"unknown={sorted(actual_fields.difference(disposition_fields))}; "\n'
            '                "exact schema: unavailable"\n'
        ),
        test=(
            f"{TEST_MODULE}."
            "test_public_v5_worker_return_template_and_diagnostics_are_executable"
        ),
        target="mathgraph/v5_assurance.py",
    ),
    Mutant(
        name="paper_continuation_transitive_ancestry_bypassed",
        old=(
            "            binding = record.get(\"metadata\", {}).get(\"paper_continuation\")\n"
            "            if binding is not None:\n"
            "                validated = self._validate_research_binding(binding, record=record)\n"
            "                result.add(validated[\"plan_id\"])\n"
            "            pending.extend(record.get(\"related_research_ids\", []))\n"
        ),
        new=(
            "            binding = record.get(\"metadata\", {}).get(\"paper_continuation\")\n"
            "            if binding is not None:\n"
            "                validated = self._validate_research_binding(binding, record=record)\n"
            "                result.add(validated[\"plan_id\"])\n"
            "            # mutant: ignore transitive Research ancestry\n"
        ),
        test=(
            f"{TEST_MODULE}."
            "test_philosophy_paper_continuation_is_complete_atomic_and_current"
        ),
        target="mathgraph/paper_continuation.py",
    ),
    Mutant(
        name="paper_revised_writing_authority_bypassed",
        old="            if missing_writing:\n",
        new="            if False and missing_writing:\n",
        test=(
            f"{TEST_MODULE}."
            "test_philosophy_paper_continuation_is_complete_atomic_and_current"
        ),
    ),
    Mutant(
        name="philosophy_unreviewed_term_gate_bypassed",
        old=(
            "        if {item[\"term\"].casefold(): item for item in term_ledger} != (\n"
            "            disposition_terms\n"
            "        ):\n"
        ),
        new=(
            "        if False and {item[\"term\"].casefold(): item for item in term_ledger} != (\n"
            "            disposition_terms\n"
            "        ):\n"
        ),
        test=(
            f"{TEST_MODULE}."
            "test_philosophy_paper_continuation_is_complete_atomic_and_current"
        ),
        target="mathgraph/paper_continuation.py",
    ),
    Mutant(
        name="paper_verifier_evidence_omitted",
        old="                    \"paper_continuation_evidence\": continuation_evidence,\n",
        new="                    # mutant: omit verifier-visible continuation evidence\n",
        test=(
            f"{TEST_MODULE}."
            "test_philosophy_paper_continuation_is_complete_atomic_and_current"
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
        old="        return commands.intersection(V5_HOST_COMMANDS)\n",
        new=(
            "        return commands.intersection(V5_HOST_COMMANDS) "
            "| {\"project-background-read\"}\n"
        ),
        test=(
            f"{CONTEXT_TEST_MODULE}."
            "test_host_v5_verification_extension_is_additive_and_v4_does_not_expand"
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
        name="completed_round_historical_runtime_boundary_bypassed",
        old=(
            "        completed = self._round_is_completed(round_dir, manifest)\n"
            "        runtime_validation_cache: set[tuple[bool, str]] = set()\n"
            "        for card_path, card in frozen_cards:\n"
        ),
        new=(
            "        completed = False\n"
            "        runtime_validation_cache: set[tuple[bool, str]] = set()\n"
            "        for card_path, card in frozen_cards:\n"
        ),
        test=(
            f"{FIELD_TEST_MODULE}."
            "test_completed_round_uses_valid_receipts_as_historical_runtime_boundary"
        ),
    ),
    Mutant(
        name="completed_round_receipt_integrity_bypassed",
        old=(
            "            self._validated_ingest_receipt(\n"
            "                round_dir=round_dir,\n"
            "                assignment=assignment,\n"
            "            )\n"
        ),
        new="            pass\n",
        test=(
            f"{FIELD_TEST_MODULE}."
            "test_completed_round_uses_valid_receipts_as_historical_runtime_boundary"
        ),
    ),
    Mutant(
        name="runtime_archive_ancestor_symlink_check_bypassed",
        old=(
            "        if stat.S_ISLNK(info.st_mode):\n"
            "            raise ValueError(f\"{label} traverses a symlink\")\n"
        ),
        new=(
            "        if False and stat.S_ISLNK(info.st_mode):\n"
            "            raise ValueError(f\"{label} traverses a symlink\")\n"
        ),
        test=(
            f"{RUNTIME_ARCHIVE_TEST_MODULE}."
            "test_bound_root_rejects_a_symlink_in_any_ancestor"
        ),
        target="mathgraph/runtime_archive.py",
    ),
    Mutant(
        name="runtime_archive_host_trust_root_mismatch_bypassed",
        old=(
            "    if (\n"
            "        normalized[\"schema_version\"] == 2\n"
            "        and Path(normalized[\"historical_archive_root\"]) != expected\n"
            "    ):\n"
        ),
        new=(
            "    if False and (\n"
            "        normalized[\"schema_version\"] == 2\n"
            "        and Path(normalized[\"historical_archive_root\"]) != expected\n"
            "    ):\n"
        ),
        test=(
            f"{RUNTIME_ARCHIVE_TEST_MODULE}."
            "test_schema2_locator_must_match_current_host_trust_root"
        ),
        target="mathgraph/runtime_archive.py",
    ),
    Mutant(
        name="runtime_archive_original_manifest_tree_not_rehashed",
        old=(
            "            result = validate_bound_runtime_at(\n"
            "                bound_root,\n"
            "                normalized,\n"
            "                verify_manifest_tree=True,\n"
            "            )\n"
        ),
        new=(
            "            result = validate_bound_runtime_at(\n"
            "                bound_root,\n"
            "                normalized,\n"
            "                verify_manifest_tree=False,\n"
            "            )\n"
        ),
        test=(
            f"{RUNTIME_ARCHIVE_TEST_MODULE}."
            "test_original_bound_root_rehashes_every_manifest_entry"
        ),
        target="mathgraph/runtime_archive.py",
    ),
    Mutant(
        name="runtime_archive_exact_file_set_bypassed",
        old="        if require_exact_file_set:\n",
        new="        if False and require_exact_file_set:\n",
        test=(
            f"{FIELD_TEST_MODULE}."
            "test_schema2_runtime_archive_is_content_addressed_and_idempotent"
        ),
        target="mathgraph/runtime_archive.py",
    ),
    Mutant(
        name="runtime_archive_read_only_seal_check_bypassed",
        old="                require_read_only=require_read_only,\n",
        new="                require_read_only=False,\n",
        test=(
            f"{RUNTIME_ARCHIVE_TEST_MODULE}."
            "test_writable_archive_object_is_rejected_even_when_bytes_match"
        ),
        target="mathgraph/runtime_archive.py",
    ),
    Mutant(
        name="runtime_archive_registry_binding_bypassed",
        old=(
            "    if value != expected or raw != canonical_json_bytes(expected) + b\"\\n\":\n"
        ),
        new=(
            "    if False and (value != expected or raw != "
            "canonical_json_bytes(expected) + b\"\\n\"):\n"
        ),
        test=(
            f"{RUNTIME_ARCHIVE_TEST_MODULE}."
            "test_registry_and_archive_are_both_required_and_revalidated"
        ),
        target="mathgraph/runtime_archive.py",
    ),
    Mutant(
        name="active_runtime_manifest_tree_rehash_bypassed",
        old=(
            "        else:\n"
            "            validate_bound_runtime_at(\n"
            "                Path(normalized[\"skill_root\"]),\n"
            "                normalized,\n"
            "                verify_manifest_tree=True,\n"
            "            )\n"
        ),
        new=(
            "        else:\n"
            "            validate_bound_runtime_at(\n"
            "                Path(normalized[\"skill_root\"]),\n"
            "                normalized,\n"
            "                verify_manifest_tree=False,\n"
            "            )\n"
        ),
        test=(
            f"{FIELD_TEST_MODULE}."
            "test_active_round_never_uses_historical_runtime_archive"
        ),
    ),
    Mutant(
        name="active_round_illegally_uses_historical_archive",
        old="        if historical_runtime:\n",
        new="        if True:\n",
        test=(
            f"{FIELD_TEST_MODULE}."
            "test_active_round_never_uses_historical_runtime_archive"
        ),
    ),
    Mutant(
        name="runtime_validation_bounded_phase_dedup_removed",
        old=(
            "                if _runtime_validation_cache is not None:\n"
            "                    _runtime_validation_cache.add(runtime_cache_key)\n"
        ),
        new=(
            "                if _runtime_validation_cache is not None:\n"
            "                    pass  # mutant: rescan each identical card\n"
        ),
        test=(
            f"{FIELD_TEST_MODULE}."
            "test_runtime_binding_is_scanned_once_per_bounded_round_phase"
        ),
    ),
    Mutant(
        name="chx_worker_runtime_manifest_tree_rehash_bypassed",
        old=(
            "    validate_bound_runtime_at(\n"
            "        Path(runtime[\"skill_root\"]),\n"
            "        runtime,\n"
            "        verify_manifest_tree=True,\n"
            "    )\n"
        ),
        new=(
            "    validate_bound_runtime_at(\n"
            "        Path(runtime[\"skill_root\"]),\n"
            "        runtime,\n"
            "        verify_manifest_tree=False,\n"
            "    )\n"
        ),
        test=(
            f"{FIELD_TEST_MODULE}."
            "test_chx_worker_ledger_rehashes_the_task_card_runtime_before_writing"
        ),
        target="chx_ledger.py",
    ),
    Mutant(
        name="round_runtime_preflight_before_write_bypassed",
        old=(
            "            self._validate_bound_runtime_binding(\n"
            "                planned_runtime_binding,\n"
            "                historical_runtime=False,\n"
            "            )\n"
        ),
        new=(
            "            pass  # mutant: skip the pre-write runtime preflight\n"
        ),
        test=(
            f"{FIELD_TEST_MODULE}."
            "test_round_runtime_preflight_fails_before_any_project_write"
        ),
    ),
    Mutant(
        name="terminal_v5_experiment_finalize_write_allowed",
        old=(
            "        with self._mutation_lock():\n"
            "            self._validate_bound_task_card(\n"
            "                task_card,\n"
            "                require_active_work_unit=True,\n"
            "            )\n"
            "            if not selected_paths:\n"
        ),
        new=(
            "        with self._mutation_lock():\n"
            "            self._validate_bound_task_card(\n"
            "                task_card,\n"
            "                require_active_work_unit=False,\n"
            "            )\n"
            "            if not selected_paths:\n"
        ),
        test=(
            f"{V5_EXPERIMENT_TEST_MODULE}."
            "test_v5_task_local_experiment_replays_resumes_and_finalizes"
        ),
        target="mathgraph/v5_experiments.py",
    ),
    Mutant(
        name="runtime_cutover_exact_candidate_file_set_bypassed",
        old="        require_exact_file_set=exact_file_set,\n",
        new="        require_exact_file_set=False,\n",
        test=(
            f"{RUNTIME_CUTOVER_TEST_MODULE}."
            "test_candidate_with_an_unexpected_file_is_rejected_before_cutover"
        ),
        target="mathgraph/runtime_cutover.py",
    ),
    Mutant(
        name="runtime_cutover_project_inventory_confirmation_bypassed",
        old=(
            "    if not normalized_projects and not confirm_no_protected_projects:\n"
        ),
        new=(
            "    if False and not normalized_projects and not confirm_no_protected_projects:\n"
        ),
        test=(
            f"{RUNTIME_CUTOVER_TEST_MODULE}."
            "test_cutover_requires_an_explicit_protected_project_inventory"
        ),
        target="mathgraph/runtime_cutover.py",
    ),
    Mutant(
        name="runtime_cutover_candidate_approval_hash_optional",
        old=(
            "    if expected_candidate_manifest_sha256 is None:\n"
            "        raise ValueError(\n"
            "            \"cutover requires an approved candidate MANIFEST.sha256 hash\"\n"
            "        )\n"
        ),
        new=(
            "    if False and expected_candidate_manifest_sha256 is None:\n"
            "        raise ValueError(\n"
            "            \"cutover requires an approved candidate MANIFEST.sha256 hash\"\n"
            "        )\n"
        ),
        test=(
            f"{RUNTIME_CUTOVER_TEST_MODULE}."
            "test_cutover_rejects_a_missing_candidate_approval_hash"
        ),
        target="mathgraph/runtime_cutover.py",
    ),
    Mutant(
        name="runtime_cutover_prior_runtime_archive_bypassed",
        old=(
            "    if installed_binding is not None:\n"
            "        bindings_to_archive[\n"
            "            installed_binding[\"runtime_identity_sha256\"]\n"
            "        ] = installed_binding\n"
        ),
        new=(
            "    if False and installed_binding is not None:\n"
            "        bindings_to_archive[\n"
            "            installed_binding[\"runtime_identity_sha256\"]\n"
            "        ] = installed_binding\n"
        ),
        test=(
            f"{RUNTIME_CUTOVER_TEST_MODULE}."
            "test_install_and_explicit_rollback_both_archive_and_swap_exact_trees"
        ),
        target="mathgraph/runtime_cutover.py",
    ),
    Mutant(
        name="runtime_cutover_multiversion_archive_resolution_bypassed",
        old=(
            "        if live_matches:\n"
            "            bindings_to_archive[identity] = normalized\n"
            "            continue\n"
        ),
        new=(
            "        if True:  # mutant: require every historical identity at one live alias\n"
            "            bindings_to_archive[identity] = normalized\n"
            "            continue\n"
        ),
        test=(
            f"{RUNTIME_CUTOVER_TEST_MODULE}."
            "test_multiversion_project_uses_sealed_history_instead_of_one_live_alias"
        ),
        target="mathgraph/runtime_cutover.py",
    ),
    Mutant(
        name="runtime_cutover_postflight_project_gate_bypassed",
        old=(
            "        postflight = project_validator(\n"
            "            installed,\n"
            "            normalized_projects,\n"
            "            archive_root=archive,\n"
            "        )\n"
        ),
        new=(
            "        postflight = {\"projects\": [], \"runtime_bindings\": []}\n"
        ),
        test=(
            f"{RUNTIME_CUTOVER_TEST_MODULE}."
            "test_post_cutover_project_gate_failure_also_restores_the_prior_installation"
        ),
        target="mathgraph/runtime_cutover.py",
    ),
    Mutant(
        name="runtime_cutover_automatic_restore_bypassed",
        old=(
            "            if prior_moved and rollback is not None and rollback.exists():\n"
            "                os.rename(rollback, installed)\n"
        ),
        new=(
            "            if False and prior_moved and rollback is not None and rollback.exists():\n"
            "                os.rename(rollback, installed)\n"
        ),
        test=(
            f"{RUNTIME_CUTOVER_TEST_MODULE}."
            "test_post_cutover_failure_restores_the_prior_installation"
        ),
        target="mathgraph/runtime_cutover.py",
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
        name="research_draft_partial_target_batch_accepted",
        old="            if set(target_ids) != set(plan[\"target_node_ids\"]):\n",
        new=(
            "            if False and set(target_ids) != "
            "set(plan[\"target_node_ids\"]):\n"
        ),
        test=(
            f"{RESEARCH_DRAFT_CONTRACT_TEST_MODULE}."
            "test_batch_rejects_partial_target_set_before_publish"
        ),
        target="mathgraph/research_draft.py",
    ),
    Mutant(
        name="research_draft_headline_reversal_authorization_bypassed",
        old=(
            "            if major_impact and authorization is None:\n"
            "                raise ValueError(\n"
            "                    \"research-draft headline narrowing/reversal "
            "requires explicit Operator authorization\"\n"
            "                )\n"
        ),
        new=(
            "            if False and major_impact and authorization is None:\n"
            "                raise ValueError(\n"
            "                    \"research-draft headline narrowing/reversal "
            "requires explicit Operator authorization\"\n"
            "                )\n"
        ),
        test=(
            f"{RESEARCH_DRAFT_CONTRACT_TEST_MODULE}."
            "test_headline_reversal_without_authorization_fails_before_publish"
        ),
        target="mathgraph/research_draft.py",
    ),
    Mutant(
        name="research_draft_source_self_coverage_accepted",
        old=(
            "                        if mapped_node[\"object_type\"] == \"source_unit\":\n"
            "                            raise ValueError(\n"
            "                                f\"source component {component_id} cannot use its source unit as semantic coverage\"\n"
            "                            )\n"
        ),
        new=(
            "                        if False and mapped_node[\"object_type\"] == \"source_unit\":\n"
            "                            raise ValueError(\n"
            "                                f\"source component {component_id} cannot use its source unit as semantic coverage\"\n"
            "                            )\n"
        ),
        test=(
            f"{RESEARCH_DRAFT_ADMISSION_TEST_MODULE}."
            "test_source_unit_cannot_count_as_its_own_proposition_coverage"
        ),
        target="mathgraph/paper_logic.py",
    ),
    Mutant(
        name="research_draft_independent_components_compressed",
        old="                    if len(independently_challengeable) > 1:\n",
        new="                    if False and len(independently_challengeable) > 1:\n",
        test=(
            f"{RESEARCH_DRAFT_ADMISSION_TEST_MODULE}."
            "test_independent_source_components_require_an_explicit_mini_dag"
        ),
        target="mathgraph/paper_logic.py",
    ),
    Mutant(
        name="research_draft_semantic_component_binding_bypassed",
        old="        if semantic[\"component_id\"] != component[\"component_id\"]:\n",
        new=(
            "        if False and semantic[\"component_id\"] "
            "!= component[\"component_id\"]:\n"
        ),
        test=(
            f"{RESEARCH_DRAFT_ADMISSION_TEST_MODULE}."
            "test_strict_release_rejects_mapping_component_and_stance_seam_drift"
        ),
        target="mathgraph/research_draft_preflight.py",
    ),
    Mutant(
        name="research_draft_source_operator_drop_accepted",
        old="        if not required_operators.issubset(interface_operators):\n",
        new=(
            "        if False and not "
            "required_operators.issubset(interface_operators):\n"
        ),
        test=(
            f"{RESEARCH_DRAFT_ADMISSION_TEST_MODULE}."
            "test_strict_release_rejects_mapping_component_and_stance_seam_drift"
        ),
        target="mathgraph/research_draft_preflight.py",
    ),
    Mutant(
        name="research_draft_source_qualifier_drop_accepted",
        old="        if not required_qualifiers.issubset(interface_qualifiers):\n",
        new=(
            "        if False and not "
            "required_qualifiers.issubset(interface_qualifiers):\n"
        ),
        test=(
            f"{RESEARCH_DRAFT_ADMISSION_TEST_MODULE}."
            "test_strict_release_rejects_mapping_component_and_stance_seam_drift"
        ),
        target="mathgraph/research_draft_preflight.py",
    ),
    Mutant(
        name="parallel_verification_identity_subgroup_guard_bypassed",
        old=(
            "    if point == (0, 1) or _scalarmult(point, _L) != (0, 1):\n"
        ),
        new=(
            "    if False and (point == (0, 1) or "
            "_scalarmult(point, _L) != (0, 1)):\n"
        ),
        test=(
            f"{PARALLEL_VERIFICATION_TEST_MODULE}."
            "test_identity_public_key_and_zero_signature_are_rejected"
        ),
        target="mathgraph/parallel_verification.py",
    ),
    Mutant(
        name="parallel_verification_public_key_alias_accepted",
        old=(
            "        if prior_key_id is not None and prior_key_id != key_id:\n"
        ),
        new=(
            "        if False and prior_key_id is not None and "
            "prior_key_id != key_id:\n"
        ),
        test=(
            f"{PARALLEL_VERIFICATION_TEST_MODULE}."
            "test_registry_rejects_one_public_key_under_multiple_identities"
        ),
        target="mathgraph/parallel_verification.py",
    ),
    Mutant(
        name="parallel_verification_status_skips_registry_integrity",
        old=(
            "    def status(self, release_id: str) -> dict[str, Any]:\n"
            "        # Status is a public integrity projection, not a per-file inventory.\n"
            "        # Fail before returning a reassuring state when the project trust\n"
            "        # registry contains cross-record identity aliases.\n"
            "        self.trusted_keys()\n"
        ),
        new=(
            "    def status(self, release_id: str) -> dict[str, Any]:\n"
            "        # Status is a public integrity projection, not a per-file inventory.\n"
            "        # Fail before returning a reassuring state when the project trust\n"
            "        # registry contains cross-record identity aliases.\n"
        ),
        test=(
            f"{RESEARCH_DRAFT_ADMISSION_TEST_MODULE}."
            "test_disk_registry_alias_fails_status_subsystem_and_top_level_audit"
        ),
        target="mathgraph/parallel_verification_lifecycle.py",
    ),
    Mutant(
        name="parallel_verification_audit_skips_registry_integrity",
        old=(
            "        try:\n"
            "            self.trusted_keys()\n"
            "        except Exception as exc:\n"
            "            errors.append(f\"trusted_key_registry: {exc}\")\n"
            "        try:\n"
            "            self._fresh_nonce_owners()\n"
        ),
        new=(
            "        try:\n"
            "            self._fresh_nonce_owners()\n"
        ),
        test=(
            f"{RESEARCH_DRAFT_ADMISSION_TEST_MODULE}."
            "test_disk_registry_alias_fails_status_subsystem_and_top_level_audit"
        ),
        target="mathgraph/parallel_verification_lifecycle.py",
    ),
    Mutant(
        name="parallel_verification_idempotent_registration_skips_registry_integrity",
        old="            current = self._load_trusted_keys()\n",
        new="            current = {record[\"key_id\"]: record}\n",
        test=(
            f"{RESEARCH_DRAFT_ADMISSION_TEST_MODULE}."
            "test_disk_registry_alias_fails_status_subsystem_and_top_level_audit"
        ),
        target="mathgraph/parallel_verification_lifecycle.py",
    ),
    Mutant(
        name="parallel_verification_single_key_read_skips_registry_integrity",
        old="        registry = self._load_trusted_keys()\n",
        new="        registry = {key_id: self._key_record(key_id)}\n",
        test=(
            f"{RESEARCH_DRAFT_ADMISSION_TEST_MODULE}."
            "test_disk_registry_alias_invalidates_cached_public_record_reads"
        ),
        target="mathgraph/parallel_verification_lifecycle.py",
    ),
    Mutant(
        name="parallel_verification_signed_plan_cache_skips_registry_integrity",
        old=(
            "        if not deep and cached is not None and cached[0] == fingerprint:\n"
            "            # A cache is a byte-I/O optimization only, never cached authority.\n"
            "            self.trusted_keys()\n"
            "            return cached[1]\n"
            "        trusted = self.trusted_keys()\n"
            "        signed = self.store._read_json(path)\n"
        ),
        new=(
            "        if not deep and cached is not None and cached[0] == fingerprint:\n"
            "            # Mutant: cached signed plan bypasses current authority.\n"
            "            return cached[1]\n"
            "        trusted = self.trusted_keys()\n"
            "        signed = self.store._read_json(path)\n"
        ),
        test=(
            f"{RESEARCH_DRAFT_ADMISSION_TEST_MODULE}."
            "test_disk_registry_alias_invalidates_cached_public_record_reads"
        ),
        target="mathgraph/parallel_verification_lifecycle.py",
    ),
    Mutant(
        name="parallel_verification_packet_cache_skips_registry_integrity",
        old=(
            "        if not deep and cached is not None and cached[0] == fingerprint:\n"
            "            # A cache is a byte-I/O optimization only, never cached authority.\n"
            "            self.trusted_keys()\n"
            "            return cached[1]\n"
            "        trusted = self.trusted_keys()\n"
            "        wrapper = self.store._read_json(path)\n"
            "        fields = {\n"
            "            \"schema_version\",\n"
            "            \"contract_revision\",\n"
            "            \"project_id\",\n"
            "            \"signed_plan_id\",\n"
            "            \"slot_id\",\n"
            "            \"packet\",\n"
        ),
        new=(
            "        if not deep and cached is not None and cached[0] == fingerprint:\n"
            "            # Mutant: cached packet bypasses current authority.\n"
            "            return cached[1]\n"
            "        trusted = self.trusted_keys()\n"
            "        wrapper = self.store._read_json(path)\n"
            "        fields = {\n"
            "            \"schema_version\",\n"
            "            \"contract_revision\",\n"
            "            \"project_id\",\n"
            "            \"signed_plan_id\",\n"
            "            \"slot_id\",\n"
            "            \"packet\",\n"
        ),
        test=(
            f"{RESEARCH_DRAFT_ADMISSION_TEST_MODULE}."
            "test_disk_registry_alias_invalidates_cached_public_record_reads"
        ),
        target="mathgraph/parallel_verification_lifecycle.py",
    ),
    Mutant(
        name="parallel_verification_receipt_cache_skips_registry_integrity",
        old=(
            "        if not deep and cached is not None and cached[0] == fingerprint:\n"
            "            # A cache is a byte-I/O optimization only, never cached authority.\n"
            "            self.trusted_keys()\n"
            "            return cached[1]\n"
            "        trusted = self.trusted_keys()\n"
            "        wrapper = self.store._read_json(path)\n"
            "        fields = {\n"
            "            \"schema_version\",\n"
            "            \"contract_revision\",\n"
            "            \"project_id\",\n"
            "            \"signed_plan_id\",\n"
            "            \"slot_id\",\n"
            "            \"packet_id\",\n"
        ),
        new=(
            "        if not deep and cached is not None and cached[0] == fingerprint:\n"
            "            # Mutant: cached receipt bypasses current authority.\n"
            "            return cached[1]\n"
            "        trusted = self.trusted_keys()\n"
            "        wrapper = self.store._read_json(path)\n"
            "        fields = {\n"
            "            \"schema_version\",\n"
            "            \"contract_revision\",\n"
            "            \"project_id\",\n"
            "            \"signed_plan_id\",\n"
            "            \"slot_id\",\n"
            "            \"packet_id\",\n"
        ),
        test=(
            f"{RESEARCH_DRAFT_ADMISSION_TEST_MODULE}."
            "test_disk_registry_alias_invalidates_cached_public_record_reads"
        ),
        target="mathgraph/parallel_verification_lifecycle.py",
    ),
    Mutant(
        name="parallel_verification_signature_bypassed",
        old=(
            "    if not verify_ed25519(public_key, jcs_bytes(projection), signature):\n"
            "        raise ValueError(\"verification fresh attestation signature is invalid\")\n"
        ),
        new=(
            "    if False and not verify_ed25519(public_key, jcs_bytes(projection), signature):\n"
            "        raise ValueError(\"verification fresh attestation signature is invalid\")\n"
        ),
        test=(
            f"{PARALLEL_VERIFICATION_TEST_MODULE}."
            "test_tampered_host_signature_fails_closed"
        ),
        target="mathgraph/parallel_verification.py",
    ),
    Mutant(
        name="parallel_verification_project_nonce_replay_accepted",
        old=(
            "        if existing is not None and existing != owner_id:\n"
            "            raise ValueError(\"verification freshness nonce was replayed\")\n"
        ),
        new=(
            "        if False and existing is not None and existing != owner_id:\n"
            "            raise ValueError(\"verification freshness nonce was replayed\")\n"
        ),
        test=(
            f"{RESEARCH_DRAFT_ADMISSION_TEST_MODULE}."
            "test_strict_release_closes_every_plane_and_invalidates_only_changed_dependency"
        ),
        target="mathgraph/parallel_verification_lifecycle.py",
    ),
    Mutant(
        name="research_draft_certification_parallel_aggregate_requirement_dropped",
        old=(
            "        if strict_research_draft:\n"
            "            required.add(\"parallel_verification_aggregate_id\")\n"
            "        source_nonpass = self._source_nonpass_checks(release)\n"
        ),
        new=(
            "        if False and strict_research_draft:\n"
            "            required.add(\"parallel_verification_aggregate_id\")\n"
            "        source_nonpass = self._source_nonpass_checks(release)\n"
        ),
        test=(
            f"{RESEARCH_DRAFT_ADMISSION_TEST_MODULE}."
            "test_strict_release_closes_every_plane_and_invalidates_only_changed_dependency"
        ),
        target="mathgraph/v5_lifecycle.py",
    ),
    Mutant(
        name="campaign_worker_result_lineage_dropped",
        old=(
            "                    **(\n"
            "                        {\"campaign_id\": card[\"campaign_id\"]}\n"
            "                        if card.get(\"campaign_id\") is not None\n"
            "                        else {}\n"
            "                    ),\n"
        ),
        new="",
        test=(
            f"{BRAVE_FUTURE_TEST_MODULE}."
            "test_real_attempt_dry_run_atomic_advisory_and_cooldown"
        ),
    ),
    Mutant(
        name="brave_future_reassessment_gains_plan_effect",
        old=(
            "            \"autonomy_level\": \"advisory\",\n"
            "            \"cooldown_state\": \"signature_consumed\",\n"
            "            \"created_by\": blockage_semantic[\"created_by\"],\n"
            "            \"plan_effect\": \"none\",\n"
            "            \"dispatch_effect\": \"none\",\n"
            "            \"campaign_close_effect\": \"none\",\n"
        ),
        new=(
            "            \"autonomy_level\": \"advisory\",\n"
            "            \"cooldown_state\": \"signature_consumed\",\n"
            "            \"created_by\": blockage_semantic[\"created_by\"],\n"
            "            \"plan_effect\": \"plan_one\",\n"
            "            \"dispatch_effect\": \"none\",\n"
            "            \"campaign_close_effect\": \"none\",\n"
        ),
        test=(
            f"{BRAVE_FUTURE_TEST_MODULE}."
            "test_real_attempt_dry_run_atomic_advisory_and_cooldown"
        ),
        target="mathgraph/brave_future.py",
    ),
    Mutant(
        name="chx_first_close_status_projection_drift",
        old="        return ledger_status(path)\n    return status\n",
        new="        return status\n    return status\n",
        test=(
            f"{CHX_TEST_MODULE}."
            "test_empty_run_is_persisted_but_requires_no_feedback"
        ),
        target="chx_ledger.py",
    ),
    Mutant(
        name="paper_research_premise_order_reduced_to_set_equality",
        old=(
            "            _require(\n"
            "                edge_order == premise_ids,\n"
            "                f\"{object_id} premise edge order differs from payload order\",\n"
            "            )\n"
        ),
        new=(
            "            _require(\n"
            "                set(edge_order) == set(premise_ids),\n"
            "                f\"{object_id} premise edge order differs from payload order\",\n"
            "            )\n"
        ),
        test=(
            f"{PAPER_RESEARCH_PIPELINE_TEST_MODULE}."
            "test_frontier_preserves_premise_order_and_rejects_position_drift"
        ),
        target="mathgraph/paper_research_pipeline.py",
    ),
    Mutant(
        name="paper_research_represented_component_zero_mapping_accepted",
        old=(
            "                    _require(mapped, f\"{component_id} represented without graph mapping\")\n"
        ),
        new=(
            "                    _require(True, f\"{component_id} represented without graph mapping\")\n"
        ),
        test=(
            f"{PAPER_RESEARCH_PIPELINE_TEST_MODULE}."
            "test_represented_component_requires_mapping_and_composition_witness"
        ),
        target="mathgraph/paper_research_pipeline.py",
    ),
    Mutant(
        name="paper_research_claim_support_review_bypassed",
        old=(
            "            _require(review.get(\"status\") == \"passed\", f\"{claim_id}: review not passed\")\n"
        ),
        new=(
            "            _require(True, f\"{claim_id}: review not passed\")\n"
        ),
        test=(
            f"{PAPER_RESEARCH_PIPELINE_TEST_MODULE}."
            "test_evidence_identity_witness_and_support_review_gate"
        ),
        target="mathgraph/paper_research_pipeline.py",
    ),
    Mutant(
        name="paper_research_atomic_subject_escapes_through_theorem",
        old=(
            "    _require(subject.get(\"kind\") == \"paper\", \"atomic DAG escaped through theorem mode\")\n"
        ),
        new=(
            "    _require(True, \"atomic DAG escaped through theorem mode\")\n"
        ),
        test=(
            f"{PAPER_RESEARCH_PIPELINE_TEST_MODULE}."
            "test_atomic_preflight_rejects_theorem_escape_and_target_loss"
        ),
        target="mathgraph/paper_research_pipeline.py",
    ),
    Mutant(
        name="paper_research_cross_domain_continuity_substitution_accepted",
        old=(
            "    graph_profile = _normalized_domain_profile(graph.get(\"domain_profile\"))\n"
            "    contract_profile = _normalized_domain_profile(\n"
            "        continuity_contract.get(\"domain_profile\")\n"
            "    )\n"
        ),
        new=(
            "    contract_profile = _normalized_domain_profile(\n"
            "        continuity_contract.get(\"domain_profile\")\n"
            "    )\n"
            "    graph_profile = contract_profile\n"
        ),
        test=(
            f"{PAPER_RESEARCH_PIPELINE_TEST_MODULE}."
            "test_mathematics_preserves_target_and_allows_proof_or_disproof"
        ),
        target="mathgraph/paper_research_pipeline.py",
    ),
    Mutant(
        name="paper_research_mathematical_disproof_removed",
        old=(
            "        {\"proved\", \"disproved\", \"unresolved_with_obstruction\"}\n"
        ),
        new=(
            "        {\"proved\", \"unresolved_with_obstruction\"}\n"
        ),
        test=(
            f"{PAPER_RESEARCH_PIPELINE_TEST_MODULE}."
            "test_mathematics_preserves_target_and_allows_proof_or_disproof"
        ),
        target="mathgraph/paper_research_pipeline.py",
    ),
    Mutant(
        name="paper_research_stable_identity_semantic_collision_accepted",
        old=(
            "            _require(\n"
            "                merged[identity] == item,\n"
            "                f\"stable identity collision with semantic drift: {identity}\",\n"
            "            )\n"
        ),
        new=(
            "            _require(\n"
            "                True,\n"
            "                f\"stable identity collision with semantic drift: {identity}\",\n"
            "            )\n"
        ),
        test=(
            f"{PAPER_RESEARCH_PIPELINE_TEST_MODULE}."
            "test_stable_identity_merge_rejects_semantic_collision"
        ),
        target="mathgraph/paper_research_pipeline.py",
    ),
    Mutant(
        name="paper_research_source_occurrence_span_tamper_accepted",
        old="                or text[start:end] != token\n",
        new="                or False and text[start:end] != token\n",
        test=(
            f"{PAPER_RESEARCH_PIPELINE_TEST_MODULE}."
            "test_source_occurrence_ledger_is_exact_and_tamper_evident"
        ),
        target="mathgraph/paper_logic_contracts.py",
    ),
    Mutant(
        name="paper_research_normative_operation_relabel_accepted",
        old=(
            "        if kind == \"normative_bridge\" and operation != \"normative_bridge\":\n"
        ),
        new=(
            "        if False and kind == \"normative_bridge\" and operation != \"normative_bridge\":\n"
        ),
        test=(
            f"{PAPER_RESEARCH_PIPELINE_TEST_MODULE}."
            "test_semantic_operation_cannot_masquerade_as_normative_bridge"
        ),
        target="mathgraph/paper_logic_contracts.py",
    ),
    Mutant(
        name="paper_research_receipt_content_address_recomputation_bypassed",
        old="    expected_id = id_prefix + sha256_json(semantic)\n",
        new="    expected_id = declared_id\n",
        test=(
            f"{PAPER_RESEARCH_PIPELINE_TEST_MODULE}."
            "test_evidence_identity_witness_and_support_review_gate"
        ),
        target="mathgraph/paper_research_pipeline.py",
    ),
    Mutant(
        name="paper_research_receipt_exact_field_set_bypassed",
        old="    _require(set(receipt) == allowed_fields, f\"{label} receipt field set drifted\")\n",
        new="    _require(True, f\"{label} receipt field set drifted\")\n",
        test=(
            f"{PAPER_RESEARCH_PIPELINE_TEST_MODULE}."
            "test_evidence_identity_witness_and_support_review_gate"
        ),
        target="mathgraph/paper_research_pipeline.py",
    ),
    Mutant(
        name="runtime_compatibility_protected_count_drift_bypassed",
        old=(
            "    _require(\n"
            "        compatibility.get(\"protected_file_count\") == status[\"protected_file_count\"],\n"
            "        \"runtime compatibility protected_file_count drifted\",\n"
            "    )\n"
        ),
        new=(
            "    _require(\n"
            "        True,\n"
            "        \"runtime compatibility protected_file_count drifted\",\n"
            "    )\n"
        ),
        test=(
            f"{RUNTIME_COMPATIBILITY_TEST_MODULE}."
            "test_new_runtime_file_fails_stale_count_and_digest"
        ),
        target="mathgraph/runtime_compatibility.py",
    ),
    Mutant(
        name="runtime_compatibility_protected_digest_drift_bypassed",
        old=(
            "    _require(\n"
            "        compatibility.get(\"protected_tree_sha256\")\n"
            "        == status[\"protected_tree_sha256\"],\n"
            "        \"runtime compatibility protected_tree_sha256 drifted\",\n"
            "    )\n"
        ),
        new=(
            "    _require(\n"
            "        True,\n"
            "        \"runtime compatibility protected_tree_sha256 drifted\",\n"
            "    )\n"
        ),
        test=(
            f"{RUNTIME_COMPATIBILITY_TEST_MODULE}."
            "test_content_drift_fails_stale_digest_with_same_file_count"
        ),
        target="mathgraph/runtime_compatibility.py",
    ),
    Mutant(
        name="runtime_compatibility_changed_path_escape_bypassed",
        old=(
            "    _require(\n"
            "        set(changed).issubset(protected),\n"
            "        \"runtime compatibility changed path is outside the protected closure\",\n"
            "    )\n"
        ),
        new=(
            "    _require(\n"
            "        True,\n"
            "        \"runtime compatibility changed path is outside the protected closure\",\n"
            "    )\n"
        ),
        test=(
            f"{RUNTIME_COMPATIBILITY_TEST_MODULE}."
            "test_changed_path_cannot_escape_protected_closure"
        ),
        target="mathgraph/runtime_compatibility.py",
    ),
    Mutant(
        name="runtime_compatibility_changed_path_inventory_digest_bypassed",
        old=(
            "    _require(\n"
            "        compatibility.get(\"changed_path_inventory_sha256\") == changed_digest,\n"
            "        \"runtime compatibility changed path inventory digest drifted\",\n"
            "    )\n"
        ),
        new=(
            "    _require(\n"
            "        True,\n"
            "        \"runtime compatibility changed path inventory digest drifted\",\n"
            "    )\n"
        ),
        test=(
            f"{RUNTIME_COMPATIBILITY_TEST_MODULE}."
            "test_changed_path_inventory_fails_stale_digest"
        ),
        target="mathgraph/runtime_compatibility.py",
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
    Mutant(
        name="chx_public_disclosure_unresolved_issue_accepted",
        old=(
            "    if any(item[\"status\"] != \"resolved\" for item in issues):\n"
            "        raise ValueError(\"CHX publication contains an unresolved included issue\")\n"
        ),
        new=(
            "    if False and any(item[\"status\"] != \"resolved\" for item in issues):\n"
            "        raise ValueError(\"CHX publication contains an unresolved included issue\")\n"
        ),
        test=(
            f"{CHX_TEST_MODULE}."
            "test_public_disclosure_binds_ledger_registry_and_documents"
        ),
        target="chx_ledger.py",
    ),
    Mutant(
        name="chx_public_disclosure_explicit_enumeration_bypassed",
        old="            if enumerated != included:\n",
        new="            if False and enumerated != included:\n",
        test=(
            f"{CHX_TEST_MODULE}."
            "test_public_disclosure_binds_ledger_registry_and_documents"
        ),
        target="chx_ledger.py",
    ),
    Mutant(
        name="chx_public_disclosure_run_namespace_bypassed",
        old="    if status[\"run_id\"] != contract[\"ledger_run_id\"]:\n",
        new="    if False and status[\"run_id\"] != contract[\"ledger_run_id\"]:\n",
        test=(
            f"{CHX_TEST_MODULE}."
            "test_public_disclosure_binds_ledger_registry_and_documents"
        ),
        target="chx_ledger.py",
    ),
    Mutant(
        name="reader_orbit_off_pinned_collision_yield_bypassed",
        old=(
            "    const pinnedCollisionYieldEnabled = !state.orbitGravity\n"
            "      && ['drag', 'drag-release'].includes(reason);\n"
        ),
        new="    const pinnedCollisionYieldEnabled = false;\n",
        test=(
            f"{READER_TEST_MODULE}."
            "test_revision_twenty_orbit_off_drag_repels_an_existing_session_pin"
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
            "mode equivalence, source capability, adverse provenance, general hidden-"
            "conjunct and philosophy-domain baseline gating, prior-Fact routing, "
            "legacy premises, runtime identity, admission recovery, abort, "
            "terminal historical-runtime content objects, identity registry, "
            "component no-follow containment, active/write isolation, bounded-phase "
            "runtime-scan deduplication, CHX worker runtime rehash, pre-write round "
            "runtime preflight, fail-closed runtime cutover and automatic rollback, "
            "explicit Campaign exact-match scope and frozen snapshot integrity, "
            "public Paper and V5 worker-return interface reachability and diagnostics, "
            "Paper continuation "
            "ancestry, revised-writing authority, philosophy "
            "term review, verifier-visible evidence, "
            "strict research-draft proposition and target-total batch coverage, "
            "stance authorization, semantic-component and source-operator/qualifier "
            "continuity, explicit mini-DAG atomicity, exact receipt schemas and "
            "content-address recomputation, trusted prime-order signature "
            "verification, registry-wide cryptographic-identity, idempotent-registration, and cached-read authority integrity, "
            "project-wide freshness, Certification aggregate enforcement, Campaign "
            "worker-result lineage, Brave Future advisory-only effects, CHX "
            "close/status parity, public-disclosure completeness and run namespace, "
            "status projection, Reader math projection, multi-center theme-field layout, "
            "orbit-off pinned-card collision repulsion, and "
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

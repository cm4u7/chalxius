#!/usr/bin/env python3
"""Run focused V5 boundary tests and prove that they kill critical mutants.

The harness copies the engine to a temporary directory, applies one deliberate
off-by-one or exact-set defect at a time, and runs the smallest regression that
must detect it.  It never edits the candidate or an installed skill tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

sys.dont_write_bytecode = True


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
HOST_ENTRYPOINT_TEST_MODULE = (
    "tests.test_host_entrypoint_nonmutation.HostEntrypointNonMutationTests"
)
RELEASE_VALIDATION_TEST_MODULE = (
    "tests.test_release_validation.ReleaseValidationTests"
)
PAPER_RESEARCH_PIPELINE_TEST_MODULE = (
    "tests.test_paper_research_pipeline.PaperResearchPipelineTests"
)
CHX004_TEST_MODULE = (
    "tests.test_chx_004_fact_closure_authority."
    "CHX004FactClosureAuthorityTests"
)
RESEARCH_TWO_SUBROUND_TEST_MODULE = (
    "tests.test_research_two_subround.ResearchTwoSubroundTests"
)
CHX_0812_TEST_MODULE = (
    "tests.test_chx_0812_semantic_recovery.SemanticRecovery0812Tests"
)
MUTANTS = (
    Mutant(
        name="frontier_cow_branch_ambiguity_bypassed",
        old=(
            "                if len(children) != 1:\n"
            "                    terminals[seed] = None\n"
            "                    break\n"
        ),
        new=(
            "                if False and len(children) != 1:  # mutant\n"
            "                    terminals[seed] = None\n"
            "                    break\n"
        ),
        test=(
            f"{CHX_0812_TEST_MODULE}."
            "test_malformed_or_ambiguous_repair_lineage_never_closes_predecessor"
        ),
    ),
    Mutant(
        name="frontier_cow_invalidator_exhaustion_weakened",
        old=(
            "                or route_staleness.get(product_id) != [trigger_id]\n"
        ),
        new=(
            "                or trigger_id not in route_staleness.get(product_id, [])"
            "  # mutant\n"
        ),
        test=(
            f"{CHX_0812_TEST_MODULE}."
            "test_repair_requires_exact_active_invalidator_coverage"
        ),
    ),
    Mutant(
        name="frontier_cow_repair_continuity_bypassed",
        old=(
            "                or not cls._frontier_repair_continuity_is_exact(repair=repair)\n"
        ),
        new="                or False  # mutant: ignore repair continuity\n",
        test=(
            f"{CHX_0812_TEST_MODULE}."
            "test_repair_requires_hash_bound_objective_projection"
        ),
    ),
    Mutant(
        name="frontier_cow_original_projection_bypassed",
        old=(
            "            completed_members = [\n"
            "                member\n"
            "                for member, terminal in terminals.items()\n"
        ),
        new=(
            "            completed_members = [\n"
            "                terminal  # mutant: expose successor as work identity\n"
            "                for member, terminal in terminals.items()\n"
        ),
        test=(
            f"{CHX_0812_TEST_MODULE}."
            "test_exact_multihop_cow_completion_projects_to_original_workgroup"
        ),
    ),
    Mutant(
        name="frontier_cow_terminal_staleness_bypassed",
        old='            or product["research_id"] in route_staleness\n',
        new="            or False  # mutant: accept invalidated terminal product\n",
        test=(
            f"{CHX_0812_TEST_MODULE}."
            "test_terminal_product_invalidation_and_incomplete_obligations_reopen"
        ),
    ),
    Mutant(
        name="cow_supervision_defect_allowlist_restored",
        old=(
            '                    "obligations as mandatory but non-exhaustive attack seeds, not a "\n'
            '                    "defect allowlist; report new, inherited, repair-induced, or cross-"\n'
        ),
        new=(
            '                    "obligations as a checklist of already reported defects; "\n'
            '                    "report repair-related or cross-"\n'
        ),
        test=(
            f"{RESEARCH_TWO_SUBROUND_TEST_MODULE}."
            "test_failure_informed_assurance_removes_same_scope_integration_and_defaults_to_minimal_blackboard"
        ),
    ),
    Mutant(
        name="frontier_limit_minus_one",
        old="        selected = visible[:limit]\n",
        new="        selected = visible[: max(0, limit - 1)]\n",
        test=(
            f"{TEST_MODULE}."
            "test_frontier_limits_and_explicit_last_entry_have_no_truncation_error"
        ),
    ),
    Mutant(
        name="campaign_frontier_exact_match_bypassed",
        old=(
            "        for research_id, record in bases.items():\n"
            "            if (\n"
            "                campaign_id is not None\n"
            "                and record[\"metadata\"].get(\"campaign_id\") != campaign_id\n"
            "            ):\n"
            "                continue\n"
        ),
        new=(
            "        for research_id, record in bases.items():\n"
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
        name="explicit_selection_campaign_exact_match_bypassed",
        old=(
            "        for research_id in research_ids:\n"
            "            record = lineage[research_id]\n"
            "            if (\n"
            "                campaign_id is not None\n"
            "                and record[\"metadata\"].get(\"campaign_id\") != campaign_id\n"
            "            ):\n"
            "                continue\n"
        ),
        new=(
            "        for research_id in research_ids:\n"
            "            record = lineage[research_id]\n"
            "            if False and (\n"
            "                campaign_id is not None\n"
            "                and record[\"metadata\"].get(\"campaign_id\") != campaign_id\n"
            "            ):\n"
            "                continue\n"
        ),
        test=(
            f"{CAMPAIGN_TEST_MODULE}."
            "test_cross_campaign_explicit_selection_fails_before_round_write"
        ),
    ),
    Mutant(
        name="campaign_active_pointer_becomes_implicit_v5_scope",
        old=(
            "        if campaign_id is not None:\n"
            "            campaign_id = validate_campaign_id(campaign_id)\n"
            "            if campaign_id not in _inspection_context.campaign_statuses:\n"
            "                _inspection_context.campaign_statuses[campaign_id] = (\n"
            "                    self.store.campaigns().status(campaign_id)\n"
            "                )\n"
        ),
        new=(
            "        campaign_id = campaign_id or self.store.campaigns().active()\n"
            "        if campaign_id is not None:\n"
            "            campaign_id = validate_campaign_id(campaign_id)\n"
            "            if campaign_id not in _inspection_context.campaign_statuses:\n"
            "                _inspection_context.campaign_statuses[campaign_id] = (\n"
            "                    self.store.campaigns().status(campaign_id)\n"
            "                )\n"
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
        name="paper_continuation_bounded_lookup_replaced_by_project_scan",
        old=(
            "            try:\n"
            "                record = self.lifecycle._inspection_research_record(\n"
            "                    research_id,\n"
            "                    self._inspection_context,\n"
            "                )\n"
            "            except KeyError as exc:\n"
        ),
        new=(
            "            try:\n"
            "                record = {\n"
            "                    item[\"research_id\"]: item\n"
            "                    for item in self.lifecycle.research_records(\n"
            "                        _inspection_context=self._inspection_context\n"
            "                    )\n"
            "                }[research_id]\n"
            "            except KeyError as exc:\n"
        ),
        test=(
            f"{TEST_MODULE}."
            "test_paper_continuation_plan_lookup_is_ancestry_bounded"
        ),
        target="mathgraph/paper_continuation.py",
    ),
    Mutant(
        name="typed_fact_closure_authority_expansion_bypassed",
        old=(
            "        if fact_closure_reconstruction_required and "
            "referenced_fact_ids:\n"
        ),
        new=(
            "        if False and fact_closure_reconstruction_required and "
            "referenced_fact_ids:\n"
        ),
        test=(
            f"{CHX004_TEST_MODULE}."
            "test_typed_closure_evidence_expands_only_active_dependency_ancestry"
        ),
    ),
    Mutant(
        name="typed_fact_closure_non_active_root_accepted",
        old="            if non_active_root_ids:\n",
        new="            if False and non_active_root_ids:\n",
        test=(
            f"{CHX004_TEST_MODULE}."
            "test_typed_closure_rejects_non_active_root_before_dispatch"
        ),
    ),
    Mutant(
        name="proof_risk_logic_signals_ignored_by_supervision",
        old=(
            "                or bool(V5_PROOF_LOGIC_SELECTION_SIGNALS & "
            "logic_signals)\n"
        ),
        new="                or False\n",
        test=(
            f"{RESEARCH_TWO_SUBROUND_TEST_MODULE}."
            "test_interpretive_proof_boundary_signal_receives_proof_supervisor"
        ),
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
        name="paper_verifier_continuation_capsule_omitted",
        old=(
            "                semantic[\"paper_continuation_release_capsule\"] = release[\n"
            "                    \"paper_continuation_release_capsule\"\n"
            "                ]\n"
        ),
        new=(
            "                # mutant: omit verifier-visible continuation release capsule\n"
            "                pass\n"
        ),
        test=(
            f"{TEST_MODULE}."
            "test_philosophy_paper_continuation_is_complete_atomic_and_current"
        ),
        target="mathgraph/v5_lifecycle.py",
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
        name="adverse_evidence_provenance_dropped",
        old=(
            "                if (\n"
            "                    record[\"kind\"] not in adverse_kinds\n"
            "                    and not self._research_is_adverse_assignment(record)\n"
            "                ):\n"
        ),
        new=(
            "                if record[\"kind\"] not in adverse_kinds:\n"
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
        name="mathgraph_package_bytecode_suppression_removed",
        old=(
            "sys.dont_write_bytecode = True\n"
            "_self_cache = importlib.util.cache_from_source(__file__)\n"
        ),
        new=(
            "sys.dont_write_bytecode = False\n"
            "_self_cache = importlib.util.cache_from_source(__file__)\n"
        ),
        test=(
            f"{HOST_ENTRYPOINT_TEST_MODULE}."
            "test_default_python_entrypoints_do_not_create_bytecode"
        ),
        target="mathgraph/__init__.py",
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
        name="runtime_cutover_prevalidated_receipt_bypassed",
        old=(
            "    if project_validation_receipt is not None:\n"
            "        if installed_binding is None:\n"
        ),
        new=(
            "    if False and project_validation_receipt is not None:\n"
            "        if installed_binding is None:\n"
        ),
        test=(
            f"{RUNTIME_CUTOVER_TEST_MODULE}."
            "test_bounded_project_receipt_replaces_duplicate_cutover_audits"
        ),
        target="mathgraph/runtime_cutover.py",
    ),
    Mutant(
        name="runtime_cutover_implicit_duplicate_full_audits_reenabled",
        old=(
            "    if (\n"
            "        normalized_projects\n"
            "        and project_validation_receipt is None\n"
            "        and not force_full_project_audit\n"
            "    ):\n"
        ),
        new=(
            "    if False and (\n"
            "        normalized_projects\n"
            "        and project_validation_receipt is None\n"
            "        and not force_full_project_audit\n"
            "    ):\n"
        ),
        test=(
            f"{RUNTIME_CUTOVER_TEST_MODULE}."
            "test_protected_cutover_refuses_implicit_duplicate_full_audits"
        ),
        target="mathgraph/runtime_cutover.py",
    ),
    Mutant(
        name="runtime_cutover_forced_full_audit_repeated_post_swap",
        old="        elif in_memory_full_receipt is not None:\n",
        new="        elif False and in_memory_full_receipt is not None:\n",
        test=(
            f"{RUNTIME_CUTOVER_TEST_MODULE}."
            "test_multiversion_project_uses_sealed_history_instead_of_one_live_alias"
        ),
        target="mathgraph/runtime_cutover.py",
    ),
    Mutant(
        name="runtime_cutover_project_snapshot_drift_bypassed",
        old=(
            "        if raw.get(\"project_state\") != comparable_snapshot:\n"
            "            raise ValueError(\"protected project changed after validation receipt\")\n"
        ),
        new=(
            "        if False and raw.get(\"project_state\") != comparable_snapshot:\n"
            "            raise ValueError(\"protected project changed after validation receipt\")\n"
        ),
        test=(
            f"{RUNTIME_CUTOVER_TEST_MODULE}."
            "test_bounded_project_receipt_rejects_project_drift_before_swap"
        ),
        target="mathgraph/runtime_cutover.py",
    ),
    Mutant(
        name="runtime_cutover_required_deep_audit_downgraded",
        old=(
            "    if not deep_audit_required:\n"
        ),
        new=(
            "    if True:  # mutant: downgrade an explicitly required deep audit\n"
        ),
        test=(
            f"{RUNTIME_CUTOVER_TEST_MODULE}."
            "test_deep_project_validation_runs_once_while_building_receipt"
        ),
        target="mathgraph/runtime_cutover.py",
    ),
    Mutant(
        name="runtime_cutover_project_receipt_hash_bypassed",
        old=(
            "    if actual != expected_sha256:\n"
            "        raise ValueError(f\"{label} differs from the approved SHA-256\")\n"
        ),
        new=(
            "    if False and actual != expected_sha256:\n"
            "        raise ValueError(f\"{label} differs from the approved SHA-256\")\n"
        ),
        test=(
            f"{RUNTIME_CUTOVER_TEST_MODULE}."
            "test_bounded_project_receipt_hash_is_mandatory_and_exact"
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
        name="runtime_cutover_receipt_postflight_gate_bypassed",
        old=(
            "            postflight = _validate_cutover_project_receipt_postflight(\n"
            "                receipt=bounded_receipt,\n"
            "                receipt_path=project_validation_receipt,\n"
            "                receipt_sha256=bounded_receipt_sha256,\n"
            "                installed=installed,\n"
            "                archive_root=archive,\n"
            "                project_roots=normalized_projects,\n"
            "                installed_binding=new_binding,\n"
            "            )\n"
        ),
        new=(
            "            postflight = {\"projects\": [], \"runtime_bindings\": []}\n"
        ),
        test=(
            f"{RUNTIME_CUTOVER_TEST_MODULE}."
            "test_bounded_project_receipt_post_swap_drift_restores_prior_runtime"
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
            "                if major_impact and authorization is None:\n"
            "                    raise ValueError(\n"
            "                        \"research-draft headline narrowing/reversal "
            "requires explicit Operator authorization\"\n"
            "                    )\n"
        ),
        new=(
            "                if False and major_impact and authorization is None:\n"
            "                    raise ValueError(\n"
            "                        \"research-draft headline narrowing/reversal "
            "requires explicit Operator authorization\"\n"
            "                    )\n"
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
        name="goal_intake_nonauto_mode_gate_bypassed",
        old='        if reasoning_mode not in {"auto", "deep"}:\n',
        new='        if False and reasoning_mode not in {"auto", "deep"}:\n',
        test=(
            f"{BRAVE_FUTURE_TEST_MODULE}."
            "test_goal_intake_ambiguity_nonauto_and_disablement_fail_zero_write"
        ),
        target="mathgraph/brave_future.py",
    ),
    Mutant(
        name="goal_intake_deep_mode_excluded",
        old='        if reasoning_mode not in {"auto", "deep"}:\n',
        new='        if reasoning_mode not in {"auto"}:\n',
        test=(
            f"{BRAVE_FUTURE_TEST_MODULE}."
            "test_deep_goal_intake_creates_exact_campaign_enables_bf1_only"
        ),
        target="mathgraph/brave_future.py",
    ),
    Mutant(
        name="goal_intake_active_pointer_becomes_selector",
        old="            matches = campaigns.exact_objective_matches(objective)\n",
        new=(
            "            matches = ([campaigns.active()] if campaigns.active() "
            "else campaigns.exact_objective_matches(objective))\n"
        ),
        test=(
            f"{BRAVE_FUTURE_TEST_MODULE}."
            "test_goal_intake_ignores_active_pointer_and_exposes_future_scope"
        ),
        target="mathgraph/brave_future.py",
    ),
    Mutant(
        name="goal_intake_exact_objective_degraded_to_substring",
        old=(
            '            if canonical_research_objective(status["objective"]) == objective_key:\n'
        ),
        new=(
            '            if objective_key in canonical_research_objective(status["objective"]):\n'
        ),
        test=(
            f"{BRAVE_FUTURE_TEST_MODULE}."
            "test_auto_goal_intake_is_lexically_exact_and_idempotent"
        ),
        target="mathgraph/campaigns.py",
    ),
    Mutant(
        name="goal_intake_explicit_disablement_overridden",
        old='            if not current["enabled"] and current["event_count"]:\n',
        new=(
            '            if False and not current["enabled"] and '
            'current["event_count"]:\n'
        ),
        test=(
            f"{BRAVE_FUTURE_TEST_MODULE}."
            "test_goal_intake_ambiguity_nonauto_and_disablement_fail_zero_write"
        ),
        target="mathgraph/brave_future.py",
    ),
    Mutant(
        name="goal_intake_claims_automatic_plan_effect",
        old=(
            '            "fuzzy_objective_matching": False,\n'
            '            "automatic_plan": False,\n'
            '            "automatic_dispatch": False,\n'
            '            "research_write_effect": "none",\n'
        ),
        new=(
            '            "fuzzy_objective_matching": False,\n'
            '            "automatic_plan": True,\n'
            '            "automatic_dispatch": False,\n'
            '            "research_write_effect": "none",\n'
        ),
        test=(
            f"{BRAVE_FUTURE_TEST_MODULE}."
            "test_auto_goal_intake_creates_exact_campaign_enables_bf1_only"
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
        name="chx_revision5_missing_tactical_repair_accepted",
        old=(
            "    if tactical is None:\n"
            "        raise ValueError(\n"
            "            \"resolved CHX issue requires one reusable tactical repair\"\n"
            "        )\n"
        ),
        new=(
            "    if False and tactical is None:\n"
            "        raise ValueError(\n"
            "            \"resolved CHX issue requires one reusable tactical repair\"\n"
            "        )\n"
        ),
        test=(
            f"{CHX_TEST_MODULE}."
            "test_revision_five_resolution_requires_all_three_repair_gates"
        ),
        target="chx_ledger.py",
    ),
    Mutant(
        name="chx_revision5_reusable_registry_tamper_accepted",
        old=(
            "            if event.get(\"reusable_mechanism_registry\") != expected_registry:\n"
        ),
        new=(
            "            if False and event.get(\"reusable_mechanism_registry\") != expected_registry:\n"
        ),
        test=(
            f"{CHX_TEST_MODULE}."
            "test_integrated_registry_tamper_fails_beyond_the_event_hash"
        ),
        target="chx_ledger.py",
    ),
    Mutant(
        name="chx_revision5_late_issue_drops_prior_resolved_coverage",
        old="            if not prior_resolved.issubset(set(included)):\n",
        new="            if False and not prior_resolved.issubset(set(included)):\n",
        test=(
            f"{CHX_TEST_MODULE}."
            "test_late_issue_requires_a_superseding_integrated_full_coverage"
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
            "    if unresolved_issue_ids:\n"
            "        raise ValueError(\n"
            "            \"CHX publication contains an unresolved included issue: \"\n"
            "            + \", \".join(unresolved_issue_ids)\n"
            "        )\n"
        ),
        new=(
            "    if False and unresolved_issue_ids:\n"
            "        raise ValueError(\n"
            "            \"CHX publication contains an unresolved included issue: \"\n"
            "            + \", \".join(unresolved_issue_ids)\n"
            "        )\n"
        ),
        test=(
            f"{CHX_TEST_MODULE}."
            "test_public_disclosure_binds_ledger_registry_and_documents"
        ),
        target="chx_ledger.py",
    ),
    Mutant(
        name="chx_public_disclosure_superseding_successor_ignored",
        old="            if relation[\"relation_type\"] != \"supersedes\":\n",
        new="            if True:\n",
        test=(
            f"{CHX_TEST_MODULE}."
            "test_public_disclosure_accepts_exact_resolved_superseding_successor"
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
        name="chx_public_disclosure_lineage_equality_bypassed",
        old="    if actual_lineage != contract[\"ledger_lineage\"]:\n",
        new="    if False and actual_lineage != contract[\"ledger_lineage\"]:\n",
        test=(
            f"{CHX_TEST_MODULE}."
            "test_public_disclosure_binds_ledger_registry_and_documents"
        ),
        target="chx_ledger.py",
    ),
    Mutant(
        name="chx_successor_transitive_issue_closure_truncated",
        old=(
            "        predecessor_issue_ids = sorted(\n"
            "            {\n"
            "                issue_id\n"
            "                for entry in predecessor_lineage\n"
            "                for issue_id in entry[\"observed_issue_ids\"]\n"
        ),
        new=(
            "        predecessor_issue_ids = sorted(\n"
            "            {\n"
            "                issue_id\n"
            "                for entry in predecessor_lineage[-1:]\n"
            "                for issue_id in entry[\"observed_issue_ids\"]\n"
        ),
        test=(
            f"{CHX_TEST_MODULE}."
            "test_successor_carries_transitive_issue_lineage_across_empty_hop"
        ),
        target="chx_ledger.py",
    ),
    Mutant(
        name="paper_continuation_default_status_exports_full_topology",
        old=(
            "                    if args.full\n"
            "                    else continuation.status_summary(args.plan_id)\n"
        ),
        new=(
            "                    if True\n"
            "                    else continuation.status_summary(args.plan_id)\n"
        ),
        test=(
            "tests.test_paper_continuation_status_projection."
            "PaperContinuationStatusProjectionTests."
            "test_cli_defaults_to_summary_and_full_is_explicit"
        ),
        target="mathgraph/cli.py",
    ),
    Mutant(
        name="paper_continuation_summary_reconstructs_full_status",
        old="        return self._status_index.summary(plan_id)\n",
        new="        return self.status(plan_id)\n",
        test=(
            "tests.test_paper_continuation_status_projection."
            "PaperContinuationStatusProjectionTests."
            "test_summary_is_bounded_and_receipt_identical_to_full_view"
        ),
        target="mathgraph/paper_continuation.py",
    ),
    Mutant(
        name="paper_continuation_all_summary_reconstructs_full_status",
        old="        return self._status_index.all_summary()\n",
        new="        return self.status_all()\n",
        test=(
            "tests.test_paper_continuation_status_projection."
            "PaperContinuationStatusProjectionTests."
            "test_indexed_summary_is_two_json_reads_stale_safe_and_rebuildable"
        ),
        target="mathgraph/paper_continuation.py",
    ),
    Mutant(
        name="paper_continuation_status_stale_head_accepted",
        old=(
            "        if require_current and fingerprints != "
            "self._dependency_fingerprints():\n"
        ),
        new=(
            "        if False and require_current and fingerprints != "
            "self._dependency_fingerprints():\n"
        ),
        test=(
            "tests.test_paper_continuation_status_projection."
            "PaperContinuationStatusProjectionTests."
            "test_indexed_summary_is_two_json_reads_stale_safe_and_rebuildable"
        ),
        target="mathgraph/paper_continuation_status.py",
    ),
    Mutant(
        name="v5_top_level_status_reconstructs_full_paper_continuation",
        old=(
            "        paper_continuation = self.paper_continuation(\n"
            "            _inspection_context=_inspection_context\n"
            "        ).status_all_summary()\n"
        ),
        new=(
            "        paper_continuation = self.paper_continuation(\n"
            "            _inspection_context=_inspection_context\n"
            "        ).status_all()\n"
        ),
        test=(
            "tests.test_paper_continuation_status_projection."
            "PaperContinuationStatusProjectionTests."
            "test_indexed_summary_is_two_json_reads_stale_safe_and_rebuildable"
        ),
        target="mathgraph/v5_lifecycle.py",
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
    Mutant(
        name="aggressive_audit_child_bytecode_suppression_removed",
        old='    environment["PYTHONDONTWRITEBYTECODE"] = "1"\n',
        new='    environment.pop("PYTHONDONTWRITEBYTECODE", None)\n',
        test=(
            f"{HOST_ENTRYPOINT_TEST_MODULE}."
            "test_aggressive_audit_child_boundary_and_snapshot_are_exact"
        ),
        target="aggressive_bug_audit.py",
    ),
    Mutant(
        name="aggressive_audit_candidate_snapshot_comparison_bypassed",
        old="    return before == _candidate_snapshot(candidate_root)\n",
        new="    return True\n",
        test=(
            f"{HOST_ENTRYPOINT_TEST_MODULE}."
            "test_aggressive_audit_child_boundary_and_snapshot_are_exact"
        ),
        target="aggressive_bug_audit.py",
    ),
    Mutant(
        name="release_validation_lane_isolation_bypassed",
        old=(
            "    roots = {\n"
            '        name: canonical_workspace / name / "chalxius" for name in lane_names\n'
            "    }\n"
        ),
        new=(
            "    roots = {\n"
            '        name: canonical_workspace / "shared" / "chalxius"\n'
            "        for name in lane_names\n"
            "    }\n"
        ),
        test=(
            f"{RELEASE_VALIDATION_TEST_MODULE}."
            "test_manifest_bound_lanes_are_distinct_exact_copies"
        ),
        target="release_validation.py",
    ),
    Mutant(
        name="release_validation_lane_snapshot_bypassed",
        old="    lane_unchanged = before == _snapshot(lane_root)\n",
        new="    lane_unchanged = True\n",
        test=(
            f"{RELEASE_VALIDATION_TEST_MODULE}."
            "test_lane_runner_suppresses_bytecode_and_rejects_any_lane_write"
        ),
        target="release_validation.py",
    ),
    Mutant(
        name="release_validation_snapshot_sensitive_phase_barrier_removed",
        old=(
            '                "aggressive_bug_audit",\n'
            "                (\n"
            "                    python,\n"
            '                    "scripts/aggressive_bug_audit.py",\n'
            '                    "--profile",\n'
            '                    "semantic",\n'
            "                ),\n"
            "                phase=2,\n"
            '                mutation_profile="semantic",\n'
        ),
        new=(
            '                "aggressive_bug_audit",\n'
            "                (\n"
            "                    python,\n"
            '                    "scripts/aggressive_bug_audit.py",\n'
            '                    "--profile",\n'
            '                    "semantic",\n'
            "                ),\n"
            "                phase=1,\n"
            '                mutation_profile="semantic",\n'
        ),
        test=(
            f"{RELEASE_VALIDATION_TEST_MODULE}."
            "test_manifest_bound_lanes_are_distinct_exact_copies"
        ),
        target="release_validation.py",
    ),
    Mutant(
        name="release_validation_mutant_registry_preflight_delayed",
        old=(
            '            "mutant_registry_preflight",\n'
            "            (\n"
            "                python,\n"
            '                "scripts/aggressive_bug_audit.py",\n'
            '                "--preflight-only",\n'
            '                "--profile",\n'
            '                "full",\n'
            "            ),\n"
            "            phase=1,\n"
            '            mutation_profile="full",\n'
        ),
        new=(
            '            "mutant_registry_preflight",\n'
            "            (\n"
            "                python,\n"
            '                "scripts/aggressive_bug_audit.py",\n'
            '                "--preflight-only",\n'
            '                "--profile",\n'
            '                "full",\n'
            "            ),\n"
            "            phase=3,\n"
            '            mutation_profile="full",\n'
        ),
        test=(
            f"{RELEASE_VALIDATION_TEST_MODULE}."
            "test_manifest_bound_lanes_are_distinct_exact_copies"
        ),
        target="release_validation.py",
    ),
    Mutant(
        name="aggressive_audit_mutant_registry_preflight_bypassed",
        old=(
            "    _validate_mutant_targets(\n"
            "        candidate_root=candidate_root,\n"
            "        source_scripts=source_scripts,\n"
            "        mutants=mutants,\n"
            "    )\n"
        ),
        new="    pass  # mutant: skip the cheap complete registry preflight\n",
        test=(
            f"{HOST_ENTRYPOINT_TEST_MODULE}."
            "test_mutant_registry_preflight_runs_before_any_test_subprocess"
        ),
        target="aggressive_bug_audit.py",
    ),
)


# The release-time audit is deliberately small and semantic.  These probes
# guard the boundaries that can change a mathematical conclusion, Fact
# authority, graph ancestry, computation interpretation, or verifier result.
# The historical registry remains available through ``--profile full`` for an
# explicit forensic investigation; it is not a routine agent-facing gate.
SEMANTIC_MUTANT_NAMES = frozenset(
    {
        "frontier_limit_minus_one",
        "campaign_snapshot_hash_bypass",
        "typed_fact_closure_authority_expansion_bypassed",
        "typed_fact_closure_non_active_root_accepted",
        "candidate_mapping_allows_missing_fact",
        "series_order_budget_accepts_declared_retention",
        "background_snapshot_hash_bypass",
        "current_source_capability_requirement_bypassed",
        "adverse_evidence_provenance_dropped",
        "parallel_verification_signature_bypassed",
        "parallel_verification_project_nonce_replay_accepted",
        "research_draft_semantic_component_binding_bypassed",
        "paper_research_mathematical_disproof_removed",
        "paper_research_receipt_content_address_recomputation_bypassed",
        "paper_research_stable_identity_semantic_collision_accepted",
        "cow_supervision_defect_allowlist_restored",
        "frontier_cow_branch_ambiguity_bypassed",
        "frontier_cow_invalidator_exhaustion_weakened",
        "frontier_cow_original_projection_bypassed",
        "frontier_cow_repair_continuity_bypassed",
        "frontier_cow_terminal_staleness_bypassed",
    }
)


def _mutants_for_profile(profile: str) -> tuple[Mutant, ...]:
    if profile == "full":
        return MUTANTS
    if profile != "semantic":
        raise ValueError(f"unknown mutation profile: {profile}")
    # Keep the public preflight seam observable when a caller deliberately
    # replaces the registry in a host-entrypoint test.  The real path still
    # fails closed below if the selected profile is empty; returning an empty
    # tuple here lets the preflight itself remain the first callable boundary.
    if not MUTANTS:
        return ()
    selected = tuple(
        mutant for mutant in MUTANTS if mutant.name in SEMANTIC_MUTANT_NAMES
    )
    missing = SEMANTIC_MUTANT_NAMES - {mutant.name for mutant in selected}
    if missing:
        raise RuntimeError(
            "semantic mutation profile names missing from registry: "
            + ", ".join(sorted(missing))
        )
    return selected


def _mutant_target(
    *, candidate_root: Path, source_scripts: Path, mutant: Mutant
) -> Path:
    candidate = candidate_root.resolve()
    raw_target = source_scripts / mutant.target
    target = raw_target.resolve()
    if target == candidate or candidate not in target.parents:
        raise SystemExit(f"mutant {mutant.name} target escapes the candidate")
    if raw_target.is_symlink() or not target.is_file():
        raise SystemExit(f"mutant {mutant.name} target is not one regular file")
    return target


def _validate_mutant_targets(
    *,
    candidate_root: Path,
    source_scripts: Path,
    mutants: tuple[Mutant, ...],
) -> None:
    """Reject a stale mutation plan before spawning any expensive test."""

    for mutant in mutants:
        target = _mutant_target(
            candidate_root=candidate_root,
            source_scripts=source_scripts,
            mutant=mutant,
        )
        occurrences = target.read_text(encoding="utf-8").count(mutant.old)
        if occurrences != 1:
            raise SystemExit(
                f"mutant registry preflight: {mutant.name} expected one target, "
                f"found {occurrences}"
            )


def _candidate_snapshot(candidate_root: Path) -> tuple[tuple[str, str, str, str], ...]:
    """Freeze the complete local path, kind, mode, and content/link identity."""

    entries: list[tuple[str, str, str, str]] = []
    for path in sorted(candidate_root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(candidate_root).as_posix()
        mode = f"{path.lstat().st_mode & 0o7777:o}"
        if path.is_symlink():
            entries.append((relative, "symlink", mode, os.readlink(path)))
        elif path.is_file():
            entries.append(
                (relative, "file", mode, hashlib.sha256(path.read_bytes()).hexdigest())
            )
        elif path.is_dir():
            entries.append((relative, "directory", mode, ""))
        else:
            entries.append((relative, "other", mode, ""))
    return tuple(entries)


def _candidate_is_unchanged(
    before: tuple[tuple[str, str, str, str], ...], candidate_root: Path
) -> bool:
    return before == _candidate_snapshot(candidate_root)


def _copy_complete_runtime(*, candidate_root: Path, parent: Path) -> Path:
    """Create one complete isolated runtime with the canonical root name."""

    # macOS exposes the temporary directory through ``/var`` even though that
    # path traverses the system ``/var -> private/var`` symlink.  Chalxius
    # correctly rejects symlinked runtime ancestors, so canonicalize the
    # already-existing temporary parent before constructing the isolated root.
    parent = parent.resolve(strict=True)
    runtime_root = parent / "chalxius"
    if runtime_root.exists():
        raise ValueError("isolated mutant runtime already exists")
    shutil.copytree(
        candidate_root,
        runtime_root,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    if runtime_root.name != "chalxius":
        raise RuntimeError("isolated mutant runtime has a noncanonical name")
    return runtime_root


def _rebind_mutant_manifest(*, runtime_root: Path, target: Path) -> str:
    """Bind one deliberate source mutation as part of a valid built runtime."""

    root = runtime_root.resolve()
    resolved_target = target.resolve()
    if resolved_target == root or root not in resolved_target.parents:
        raise ValueError("mutant manifest target escapes the isolated runtime")
    if target.is_symlink() or not resolved_target.is_file():
        raise ValueError("mutant manifest target is not one regular file")
    relative = resolved_target.relative_to(root).as_posix()
    if relative == "MANIFEST.sha256":
        raise ValueError("the release manifest cannot be a mutation target")
    manifest = root / "MANIFEST.sha256"
    if manifest.is_symlink() or not manifest.is_file():
        raise ValueError("isolated mutant runtime lacks a regular manifest")
    lines = manifest.read_text(encoding="utf-8").splitlines()
    suffix = f"  {relative}"
    matching = [index for index, line in enumerate(lines) if line.endswith(suffix)]
    if len(matching) != 1:
        raise ValueError("mutant manifest target is absent or duplicated")
    lines[matching[0]] = (
        f"{hashlib.sha256(resolved_target.read_bytes()).hexdigest()}{suffix}"
    )
    payload = ("\n".join(lines) + "\n").encode("utf-8")
    manifest.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def _run_test(*, repo: Path, scripts: Path, test: str) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment.pop("PYTHONPYCACHEPREFIX", None)
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


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        choices=("semantic", "full"),
        default="semantic",
        help=(
            "semantic runs the small correctness-boundary set; full preserves "
            "the historical forensic registry"
        ),
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="validate the selected mutation registry without running baselines",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    mutants = _mutants_for_profile(args.profile)
    candidate_root = Path(__file__).resolve().parents[1]
    repo = candidate_root
    source_scripts = candidate_root / "scripts"
    candidate_before = _candidate_snapshot(candidate_root)
    results: list[dict[str, object]] = []

    _validate_mutant_targets(
        candidate_root=candidate_root,
        source_scripts=source_scripts,
        mutants=mutants,
    )
    if args.preflight_only:
        candidate_unchanged = _candidate_is_unchanged(
            candidate_before, candidate_root
        )
        report = {
            "schema_version": 1,
            "contract_revision": "chalxius-mutant-registry-preflight-2",
            "profile": args.profile,
            "mutant_count": len(mutants),
            "exact_single_target_count": len(mutants),
            "candidate_unchanged": candidate_unchanged,
            "truth_effect": "none",
            "ok": candidate_unchanged and bool(mutants),
        }
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if report["ok"] else 1

    if not mutants:
        raise RuntimeError(
            f"{args.profile} mutation profile is empty; refusing to run an "
            "unprotected audit"
        )

    baseline_tests = sorted({mutant.test for mutant in mutants})
    with tempfile.TemporaryDirectory(
        prefix="chalxius-v5-mutant-baseline-"
    ) as temporary:
        baseline_root = _copy_complete_runtime(
            candidate_root=candidate_root,
            parent=Path(temporary),
        )
        baseline_scripts = baseline_root / "scripts"
        for test in baseline_tests:
            baseline = _run_test(
                repo=baseline_root,
                scripts=baseline_scripts,
                test=test,
            )
            if baseline.returncode != 0:
                print(baseline.stdout, file=sys.stderr)
                raise SystemExit(
                    f"isolated baseline regression failed before mutation: {test}"
                )

    for mutant in mutants:
        with tempfile.TemporaryDirectory(prefix="chalxius-v5-mutant-") as temporary:
            copied_root = _copy_complete_runtime(
                candidate_root=candidate_root,
                parent=Path(temporary),
            )
            copied_scripts = copied_root / "scripts"
            target = _mutant_target(
                candidate_root=copied_root,
                source_scripts=copied_scripts,
                mutant=mutant,
            )
            text = target.read_text(encoding="utf-8")
            occurrences = text.count(mutant.old)
            if occurrences != 1:
                raise SystemExit(
                    f"mutant {mutant.name} expected one target, found {occurrences}"
                )
            target.write_text(text.replace(mutant.old, mutant.new), encoding="utf-8")
            mutant_manifest_sha256 = _rebind_mutant_manifest(
                runtime_root=copied_root,
                target=target,
            )
            outcome = _run_test(
                repo=copied_root,
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
                    "isolated_runtime_name": copied_root.name,
                    "mutant_manifest_sha256": mutant_manifest_sha256,
                    "output_sha256": hashlib.sha256(
                        outcome.stdout.encode("utf-8")
                    ).hexdigest(),
                    "output_tail": outcome.stdout[-1200:],
                }
            )
            if not killed:
                print(outcome.stdout, file=sys.stderr)

    mutants_ok = all(bool(item["killed"]) for item in results)
    candidate_unchanged = _candidate_is_unchanged(candidate_before, candidate_root)
    if args.profile == "semantic":
        scope = (
            "graph frontier, campaign snapshot integrity, Fact-closure authority, "
            "Candidate/Fact exact coverage, computation truncation, frozen source "
            "snapshots, adverse provenance, worker return integrity, verifier "
            "signatures and nonce replay, semantic Research continuity, evidence "
            "content addressing, and stable graph identity"
        )
    else:
        scope = (
            "V5 truncation, exact-set, context authority, frozen background, "
            "mode equivalence, source capability, adverse provenance, general hidden-"
            "conjunct and philosophy-domain baseline gating, prior-Fact routing, "
            "legacy premises, runtime identity, admission recovery, abort, "
            "terminal historical-runtime content objects, identity registry, "
            "component no-follow containment, active/write isolation, bounded-phase "
            "host exact-runtime entrypoint nonmutation, "
            "runtime-scan deduplication, CHX worker runtime rehash, pre-write round "
            "runtime preflight, fail-closed runtime cutover and automatic rollback, "
            "explicit Campaign exact-match scope and frozen snapshot integrity, "
            "public Paper and V5 worker-return interface reachability and diagnostics, "
            "Paper continuation ancestry, revised-writing authority, philosophy "
            "term review, verifier-visible evidence, "
            "strict research-draft proposition and target-total batch coverage, "
            "stance authorization, semantic-component and source-operator/qualifier "
            "continuity, explicit mini-DAG atomicity, exact receipt schemas and "
            "content-address recomputation, trusted prime-order signature "
            "verification, registry-wide cryptographic-identity, idempotent-"
            "registration, and cached-read authority integrity, project-wide "
            "freshness, Certification aggregate enforcement, Campaign worker-result "
            "lineage, exact goal-to-Campaign auto/deep intake, explicit disablement "
            "and active-pointer isolation, Brave Future advisory-only effects, CHX "
            "revision-5 reconnaissance/tactical/integrated repair coverage and "
            "reusable-registry integrity, close/status parity, public-disclosure "
            "completeness and run namespace, content-addressed Paper-continuation "
            "status-head freshness without summary-to-full fallback, status "
            "projection, Reader math projection, multi-center theme-field layout, "
            "orbit-off pinned-card collision repulsion, and off-by-one critical "
            "guards"
        )
    report = {
        "schema_version": 1,
        "profile": args.profile,
        "scope": scope,
        "mutants": results,
        "killed": sum(bool(item["killed"]) for item in results),
        "total": len(results),
        "ok": mutants_ok and candidate_unchanged,
        "candidate_unchanged": candidate_unchanged,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

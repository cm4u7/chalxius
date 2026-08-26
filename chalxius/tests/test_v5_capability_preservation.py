from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]


class V5CapabilityPreservationTests(unittest.TestCase):
    def test_080_mathgraph_first_compatibility_is_semantic_and_runtime_free(self) -> None:
        lock = json.loads(
            (SKILL_ROOT / "INHERITANCE.lock.json").read_text(encoding="utf-8")
        )
        self.assertNotIn("runtime_compatibility", lock)
        compatibility = lock["mathgraph_first_compatibility"]
        self.assertEqual(
            compatibility["basis"],
            "content_hashes_dependencies_provenance_workflow_and_owner_boundaries",
        )
        self.assertEqual(
            compatibility["forward_upgrade_policy"],
            "future_releases_need_not_preserve_runtime_or_procedural_compatibility;_graph_semantics_are_the_compatibility_surface",
        )
        self.assertFalse(compatibility["procedural_compatibility_requirement"])
        self.assertEqual(
            compatibility["runtime_role"],
            "diagnostic_provenance_only",
        )
        self.assertEqual(
            compatibility["legacy_operation"],
            "direct_graph_semantics_without_adapter_or_migration",
        )
        self.assertEqual(
            compatibility["project_schema_change"],
            "prospective_v5_context_background_source_campaign_adverse_nontruth_evidence_bridge_paper_continuation_research_draft_admission_and_paper_research_pipeline_only",
        )
        self.assertEqual(
            compatibility["activation_absent_behavior"],
            "legacy_frozen_task_cards_returns_releases_and_decisions_preserved",
        )
        self.assertFalse(compatibility["fact_admission_change"])
        self.assertEqual(
            compatibility["fact_admission_change_scope"],
            "base_contract_unchanged_with_recovery_legacy_premises_seal_time_lineage_shared_decision_validation_optional_evidence_bridge_freshness_paper_continuation_freshness_prospective_paper_research_pipeline_preflight_and_strict_research_draft_composable_verification",
        )
        task_context = lock["v5_task_context_surface"]
        self.assertEqual(
            task_context["contract_revision"],
            "chalxius-v5-task-context-0.4.4-1",
        )
        self.assertEqual(
            task_context["activation"],
            "prospective_new_task_cards_only",
        )
        self.assertEqual(task_context["truth_effect"], "none")
        self.assertFalse(task_context["fact_admission_change"])
        campaign_scope = lock["v5_campaign_scope_surface"]
        self.assertEqual(
            campaign_scope["contract_revision"],
            "chalxius-v5-campaign-scope-1",
        )
        self.assertEqual(
            campaign_scope["selection"],
            "main_selected_research_with_optional_explicit_campaign_scope",
        )
        self.assertEqual(
            campaign_scope["research_creation"],
            "atomic_memory_add_campaign_binding",
        )
        self.assertEqual(
            campaign_scope["scheduler"],
            "v5_main_four_factor_frontier",
        )
        self.assertFalse(campaign_scope["active_campaign_pointer_default"])
        self.assertFalse(campaign_scope["fact_admission_change"])
        self.assertEqual(campaign_scope["truth_effect"], "none")
        self.assertNotIn("brave_future_surface", lock)
        paper = lock["paper_continuation_surface"]
        self.assertEqual(
            paper["contract_revision"], "chalxius-v5-paper-continuation-1"
        )
        self.assertEqual(
            paper["selection"],
            "all_targets_without_score_cutoff_or_explicit_bounded_targets",
        )
        self.assertEqual(
            paper["adequacy_state"], "separate_from_fact_truth_and_clean_audit"
        )
        self.assertIn("ordinary_language", paper["plain_language_gate"])
        self.assertEqual(paper["historical_fact_effect"], "none")
        draft = lock["research_draft_admission_surface"]
        self.assertEqual(
            draft["preflight_revision"],
            "chalxius-research-draft-admission-preflight-1",
        )
        self.assertEqual(
            draft["disposition"],
            "one_target_total_all_or_none_batch_with_separate_node_and_many_to_many_successor_mapping",
        )
        self.assertEqual(draft["further_research_base"], "admitted_complete_fact_graph_only")
        parallel = lock["parallel_verification_surface"]
        self.assertIn("deterministic_monotone", parallel["aggregation"])
        self.assertEqual(
            parallel["project_lifecycle_revision"],
            "chalxius-parallel-verification-lifecycle-1",
        )
        self.assertIn("operator_registered", parallel["trust_anchor"])
        self.assertIn("nonce_uniqueness", parallel["freshness"])
        self.assertIn("same_eligible_aggregate", parallel["gateway"])

    def test_every_036_cli_command_is_accounted_for(self) -> None:
        cli_path = SKILL_ROOT / "scripts" / "mathgraph" / "cli.py"
        tree = ast.parse(cli_path.read_text(encoding="utf-8"))
        commands = {
            node.args[0].value
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_parser"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        }
        matrix = (
            SKILL_ROOT / "references" / "v5_capability_matrix.md"
        ).read_text(encoding="utf-8")
        missing = sorted(command for command in commands if f"`{command}`" not in matrix)
        self.assertEqual(missing, [], f"unmapped 0.3.6 public commands: {missing}")

    def test_three_planes_and_task_cards_are_preservation_invariants(self) -> None:
        matrix = (
            SKILL_ROOT / "references" / "v5_capability_matrix.md"
        ).read_text(encoding="utf-8")
        for required in (
            "control: compact prompt",
            "mathematical state: one frozen bounded snapshot",
            "narrative: bounded rationale",
            "task card remains immutable capability data",
        ):
            self.assertIn(required, matrix)

    def test_original_danus_is_reference_only(self) -> None:
        matrix = (
            SKILL_ROOT / "references" / "v5_capability_matrix.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Original Danus versions", matrix)
        self.assertIn(
            "no source module, runtime, writer, fact, review, receipt, or mutable store",
            matrix,
        )


if __name__ == "__main__":
    unittest.main()

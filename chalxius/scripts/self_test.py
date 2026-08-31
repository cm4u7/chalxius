#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from chx_ledger import (  # noqa: E402
    close_ledger,
    ledger_status,
    start_ledger,
    validate_public_disclosure_contract,
)
from mathgraph import parallel_verification as pv  # noqa: E402
from mathgraph.cli import main as cli_main  # noqa: E402
from mathgraph.applicability import validate_external_refs_for_submission  # noqa: E402
from mathgraph.blackboard import make_edge, make_node  # noqa: E402
from mathgraph.contracts import sha256_bytes, sha256_json  # noqa: E402
from mathgraph.release_contracts import (  # noqa: E402
    validate_release_audit_revision_bindings,
)
from mathgraph.elementary import validate_elementary_uses_for_submission  # noqa: E402
from mathgraph.event_ledger import (  # noqa: E402
    ExperimentEventIndexSession,
    ExperimentEventLedger,
)
from mathgraph.model import Fact  # noqa: E402
from mathgraph.orchestrator import (  # noqa: E402
    create_round,
    ingest_return,
    preflight_return,
    validate_return,
)
from mathgraph.paper_logic import PaperLogicStore  # noqa: E402
from mathgraph.paper_logic_contracts import (  # noqa: E402
    PAPER_LOGIC_FEATURE_REVISION,
    REVIEW_GLOBAL_CHECKS,
    scan_high_risk_operators,
)
from mathgraph.protocol import DEFAULT_HARD_CAPS  # noqa: E402
from mathgraph.reader_html import (  # noqa: E402
    export_reader_html,
    load_reader_packet,
    render_reader_html,
)
from mathgraph.roles import (  # noqa: E402
    V5_FACT_VERIFIER_COMMANDS,
    allowed_commands,
    allowed_commands_for_workflow,
)
from mathgraph.store import MathGraphStore  # noqa: E402


def review(
    store: MathGraphStore,
    fact_id: str,
    *,
    reviewer: str,
    verdict: str = "correct",
    errors: list[str] | None = None,
) -> str:
    frozen = store.freeze_verification_packet(fact_id)
    return store.record_review(
        {
            "fact_id": fact_id,
            "submission_sha256": frozen["submission_sha256"],
            "packet_sha256": frozen["packet_sha256"],
            "verdict": verdict,
            "critical_errors": errors or [],
            "gaps": [],
            "repair_hints": [],
            "reviewer": reviewer,
        }
    ).stem


def main() -> int:
    current_skill_version = (
        Path(__file__).resolve().parents[1] / "VERSION"
    ).read_text(encoding="utf-8").strip()
    if (
        allowed_commands("verifier") != V5_FACT_VERIFIER_COMMANDS
        or allowed_commands_for_workflow("verifier", 5)
        != V5_FACT_VERIFIER_COMMANDS
        or allowed_commands_for_workflow("verifier", 4)
        or allowed_commands("unknown-role")
    ):
        raise RuntimeError("verifier or unknown role projection is invalid")
    basepoint_public_key = (bytes([0x58]) + bytes([0x66]) * 31).hex()
    alias_planner = pv.build_trusted_key_record(
        project_id="self-test-key-registry",
        key_role="planner",
        public_key_hex=basepoint_public_key,
        principal_id="self-test-planner",
        reviewer_role_or_null=None,
        host_context_id_or_null=None,
        trust_domain_id="self-test-control",
        registered_by="self-test-operator",
    )
    alias_host = pv.build_trusted_key_record(
        project_id="self-test-key-registry",
        key_role="host",
        public_key_hex=basepoint_public_key,
        principal_id="self-test-host",
        reviewer_role_or_null=None,
        host_context_id_or_null="self-test-host-context",
        trust_domain_id="self-test-host-domain",
        registered_by="self-test-operator",
    )
    try:
        pv.validate_trusted_key_registry(
            {
                alias_planner["key_id"]: alias_planner,
                alias_host["key_id"]: alias_host,
            },
            project_id="self-test-key-registry",
        )
    except ValueError as exc:
        if "aliases one Ed25519 public key" not in str(exc):
            raise
    else:
        raise RuntimeError("verification registry accepted one key as two identities")
    if "preflight-return" not in allowed_commands("worker") or any(
        "preflight-return" in allowed_commands(role)
        for role in ("main", "operator", "host", "gateway", "verifier")
    ):
        raise RuntimeError(
            "preflight-return must remain an exclusive worker capability"
        )
    for command in (
        "export-interpret-card",
        "lint-interpret-document",
        "export-reader-html",
    ):
        if any(
            command not in allowed_commands(role)
            for role in ("main", "operator")
        ) or any(
            command in allowed_commands(role)
            for role in ("worker", "verifier", "gateway", "host")
        ):
            raise RuntimeError(
                f"{command} must remain a main/operator-only capability"
            )
    if any(
        command not in allowed_commands(role)
        for role in ("main", "operator")
        for command in ("project-background-index", "project-background-read")
    ) or any(
        command in allowed_commands("host")
        for command in ("project-background-index", "project-background-read")
    ):
        raise RuntimeError(
            "background inspection must remain Main/Operator and outside Host"
        )
    for command in ("fact-graph-inventory", "fact-graph-append-target"):
        if command not in allowed_commands("operator") or any(
            command in allowed_commands(role)
            for role in ("main", "worker", "gateway", "verifier", "host")
        ):
            raise RuntimeError(
                "cross-project Fact inventory/append-target selection must remain "
                "explicit Operator-only read-only routing"
            )
    paper_auditor = allowed_commands("paper-auditor")
    if (
        "paper-logic-record-review" not in paper_auditor
        or "paper-logic-query" not in paper_auditor
        or {
            "paper-logic-stage",
            "paper-logic-freeze",
            "paper-logic-project-blackboard",
        }.intersection(paper_auditor)
        or any(
            command.startswith("paper-logic-")
            for command in allowed_commands("worker")
        )
    ):
        raise RuntimeError("Paper Logic role capabilities crossed boundaries")
    for command in (
        "paper-continuation-plan",
        "paper-continuation-status",
        "paper-continuation-status-index-rebuild",
        "paper-continuation-dispose",
    ):
        if any(
            command not in allowed_commands(role)
            for role in ("main", "operator")
        ) or any(
            command in allowed_commands(role)
            for role in ("worker", "verifier", "gateway", "host", "paper-auditor")
        ):
            raise RuntimeError(
                f"{command} must remain a Main/Operator Paper-governance capability"
            )
    for command in (
        "research-draft-plan",
        "research-draft-disposition-batch",
        "research-draft-status",
    ):
        if any(command not in allowed_commands(role) for role in ("main", "operator")) or any(
            command in allowed_commands(role)
            for role in ("worker", "verifier", "gateway", "host", "paper-auditor")
        ):
            raise RuntimeError(f"{command} crossed the research-draft governance boundary")
    if "research-draft-authorize-major-revision" not in allowed_commands(
        "operator"
    ) or any(
        "research-draft-authorize-major-revision" in allowed_commands(role)
        for role in ("main", "worker", "verifier", "gateway", "host", "paper-auditor")
    ):
        raise RuntimeError(
            "research-draft major revision authorization must remain Operator-only"
        )
    verification_commands = {
        "verification-key-register",
        "verification-plan-prepare",
        "verification-plan-record",
        "verification-packet-prepare",
        "verification-packet-record",
        "verification-receipt-prepare",
        "verification-receipt-record",
        "verification-aggregate",
        "verification-status",
    }
    if not verification_commands.issubset(allowed_commands("operator")):
        raise RuntimeError("Operator lacks a required verification lifecycle command")
    if {
        "verification-key-register",
        "verification-packet-record",
    }.intersection(allowed_commands("main")):
        raise RuntimeError("Main crossed the verification trust/Host boundary")
    if not {
        "verification-plan-prepare",
        "verification-plan-record",
        "verification-packet-prepare",
        "verification-receipt-prepare",
        "verification-receipt-record",
        "verification-aggregate",
        "verification-status",
    }.issubset(allowed_commands("main")):
        raise RuntimeError("Main lacks a required verification coordination command")
    if not {
        "verification-packet-prepare",
        "verification-packet-record",
        "verification-status",
    }.issubset(allowed_commands("host")) or verification_commands.difference(
        {
            "verification-packet-prepare",
            "verification-packet-record",
            "verification-status",
        }
    ).intersection(allowed_commands("host")):
        raise RuntimeError("Host crossed the verification dispatch boundary")
    if allowed_commands_for_workflow("host", 4) != {
        "pulse-dispatch",
        "pulse-status",
        "pulse-audit",
    }:
        raise RuntimeError("prospective verification commands leaked into V4 Host")
    if any(
        verification_commands.intersection(allowed_commands(role))
        for role in ("worker", "verifier", "paper-auditor")
    ):
        raise RuntimeError("worker/verifier/Paper Auditor gained project verification CLI authority")
    if verification_commands.intersection(allowed_commands("gateway")) != {
        "verification-status"
    }:
        raise RuntimeError("Gateway verification access must remain read-only status")

    skill_root = Path(__file__).resolve().parents[1]
    inheritance_lock = json.loads(
        (skill_root / "INHERITANCE.lock.json").read_text(encoding="utf-8")
    )
    release_version = inheritance_lock.get("version")
    release_codename = inheritance_lock.get("release_codename")
    release_display_name = inheritance_lock.get("release_display_name")
    if (
        not isinstance(release_version, str)
        or release_version != current_skill_version
        or not isinstance(release_codename, str)
        or not release_codename.strip()
        or release_display_name
        != f"Chalxius {current_skill_version} — {release_codename}"
    ):
        raise RuntimeError(
            "VERSION, INHERITANCE.lock.json version/codename, and release display "
            "name must describe one current Chalxius release"
        )
    current_release_heading = f"# {release_display_name}"
    current_traceability_marker = (
        f"Candidate version: `{current_skill_version}`; release name "
        f"**{release_codename}**."
    )
    current_portable_deployment_markers = (
        f"`{current_skill_version}`",
        f"**{release_codename}**",
    )
    validate_release_audit_revision_bindings(skill_root)
    validate_public_disclosure_contract(skill_root)
    fact_alpha_surface = inheritance_lock.get("fact_alpha_surface")
    campaign_surface = inheritance_lock.get("v5_campaign_scope_surface")
    research_cycle_surface = inheritance_lock.get("v5_research_cycle_surface")
    adverse_surface = inheritance_lock.get("adverse_routing_surface")
    if (
        not isinstance(fact_alpha_surface, dict)
        or fact_alpha_surface.get("research_split_planning")
        != "new_schema_v3_split_production_disabled_by_default_exact_research_ids_and_current_explicit_user_request_plus_one_shot_user_authorized_split_choice_required_not_persisted_in_research_card_receipt_frontier_or_replay"
        or fact_alpha_surface.get("research_split_supervision")
        != "routine_supervision_and_fact_packaging_are_split_indifferent_historical_needs_split_is_readable_but_inert_actual_source_or_proof_defects_use_one_to_one_cow_explicit_user_authorized_low_level_split_batches_receive_ordinary_whole_product_review_without_fact_side_split_supervisor"
        or fact_alpha_surface.get("minor_repair")
        != "historical_1_0_0_bounded_fast_lane_only_one_to_one_complete_node_research_cow_then_same_verifier_full_component_recheck_without_ordinary_supervisor_or_verifier_authorship"
        or fact_alpha_surface.get("minor_repair_exclusions")
        != "historical_1_0_0_bounded_fast_lane_excludes_major_mathematical_error_relation_reallocation_or_other_structural_cow_ambiguity_which_returns_to_research_repair_worker_and_ordinary_proof_source_supervision"
        or fact_alpha_surface.get("direct_research_route_anchor_binding")
        != "plan_freezes_selection_mode_and_exact_main_route_anchor_research_ids_every_packager_sealed_component_contains_one_frozen_anchor_and_every_added_unmarked_node_is_connected_to_it_by_actual_package_dependency_edges"
        or fact_alpha_surface.get("existing_mark_plan_anchor_policy")
        != "selection_mode_existing_marks_with_empty_route_anchor_research_ids_does_not_apply_the_direct_research_route_anchor_rule"
        or not isinstance(research_cycle_surface, dict)
        or research_cycle_surface.get("blackboard_default_context")
        != "absent_with_exact_null_id_hash_and_empty_spaces_unless_promoted_query_or_write_space_capability_is_explicitly_requested"
        or research_cycle_surface.get("blackboard_historical_snapshot_policy")
        != "existing_frozen_rounds_keep_exact_id_hash_and_bytes_without_backfill_or_default_snapshot_recreation"
        or research_cycle_surface.get("blackboard_return_binding")
        != "copy_exact_card_value_json_null_or_explicit_historical_sha256_string"
        or not isinstance(campaign_surface, dict)
        or campaign_surface.get("recent_attainment_exact_queue_high_water_limit") != 64
        or campaign_surface.get("recent_attainment_routine_preview") != 4
        or campaign_surface.get("recent_attainment_complete_projection")
        != "exact_ids_count_and_digest_retained_beyond_preview"
        or campaign_surface.get("historical_landmark_count_quota") is not None
        or campaign_surface.get("historical_landmark_routine_preview") != 4
        or campaign_surface.get("historical_landmark_complete_projection")
        != "exact_working_state_and_diagnostic_ids_plus_routine_total_count_and_identity_digest"
        or campaign_surface.get("post_compaction_nonquota_boundary")
        != "four_is_the_routine_context_recent_and_landmark_preview_64_protects_only_recent_attainment_sparse_landmarks_have_no_count_quota_and_available_agent_slots_are_opportunities_not_semantic_quotas"
        or campaign_surface.get("next_research_cut_exact_search_invariant")
        != "main_runs_one_bounded_exact_research_search_before_every_next_research_cut_freeze_with_or_without_context_compaction"
        or campaign_surface.get("exact_search_result_policy")
        != "main_explicitly_disposes_every_material_exact_research_match_as_reference_only_attach_context_promote_landmark_add_head_or_retire_active_head_without_programmatic_importance_relevance_or_truth_inference"
        or campaign_surface.get("active_head_full_list_update")
        != "ordinary_full_list_is_additive_and_preserves_omitted_heads_exact_replacement_is_reserved_for_invalid_state_rebuild"
        or campaign_surface.get("active_head_incremental_operations")
        != "add_head_or_exact_retire_active_head_with_nontruth_disposition_detaching_not_deleting_context"
        or campaign_surface.get("round_attention_recovery")
        != "zero_argument_status_discovers_all_round_identities_and_deep_validates_only_unresolved_candidates_exact_id_and_all_remain_authoritative"
        or campaign_surface.get("frontier_maintenance_heartbeat")
        != "main_ensures_one_exact_project_thread_heartbeat_at_approximately_50_minutes_for_all_targets_heads_contexts_complete_landmark_identities_recent_history_active_rounds_and_material_exact_search_without_research_or_fact_dispatch"
        or campaign_surface.get("frontier_maintenance_pause")
        != "pause_changes_future_heartbeat_triggers_only_and_never_interrupts_agents_or_aborts_rounds"
        or campaign_surface.get("frontier_maintenance_repair_phase")
        != "heartbeat_trigger_exits_dont_notify_before_any_project_read_or_mutation_during_visible_integrated_repair_candidate_validation_installation_publication_or_pre_research_resume_reconciliation_without_lock_sentinel_state_machine_or_agent_interruption"
        or campaign_surface.get("routine_projection_drilldown")
        != "every_bounded_context_history_membership_workflow_supervision_research_or_round_summary_retains_exact_ids_or_complete_count_digest_plus_direct_diagnostic_or_exact_read_absence_from_preview_has_no_selection_or_truth_meaning"
        or campaign_surface.get("context_compaction_additional_duties")
        != "rehydrate_exact_operation_global_reread_and_landmark_curation_with_the_same_exact_match_placement_semantics_as_ordinary_turns_but_broader_search_and_reread_scope_not_the_exact_search_clock"
        or not isinstance(adverse_surface, dict)
        or adverse_surface.get("status")
        != "prospective_retired_frozen_completion_and_historical_readability"
        or adverse_surface.get("provenance_gate")
        != "none_main_policy_selects_historical_compatibility_without_new_identity_or_installation_gate"
    ):
        raise RuntimeError(
            "current Fact Alpha, Campaign, or historical-adverse release metadata drifted"
        )
    topology_registry = json.loads(
        (skill_root / "references" / "capability_topology_registry.json").read_text(
            encoding="utf-8"
        )
    )
    topology_modules = topology_registry.get("modules", {})
    topology_commands = topology_registry.get("commands", {})
    if (
        topology_modules.get("mathgraph.research_split", {}).get("path")
        != "scripts/mathgraph/research_split.py"
        or topology_commands.get("mgraph:candidate-release", {}).get("status")
        != "canonical"
    ):
        raise RuntimeError("capability topology release metadata drifted")
    behavior_registry = json.loads(
        (skill_root / "references" / "behavioral_feature_registry.json").read_text(
            encoding="utf-8"
        )
    )
    behavior_features = behavior_registry.get("features", {})
    for feature_id in (
        "feature.host_scope_attack_coverage",
        "feature.concise_attack_route_recommendations",
        "feature.historical_adverse_initialization",
        "feature.historical_adverse_counterexample_capture",
        "feature.historical_adverse_attack_capture",
        "feature.historical_adverse_decision",
        "feature.historical_adverse_disablement",
        "feature.historical_adverse_task_card_binding",
    ):
        if behavior_features.get(feature_id, {}).get("classification") != "compatibility":
            raise RuntimeError("historical adverse behavior registry boundary drifted")
    for feature_id in (
        "feature.paper_continuation_release_capsule",
        "feature.candidate_fresh_adverse_readiness",
        "feature.candidate_preflight_work_elimination",
        "feature.selective_fact_admission_checkpoint",
        "feature.candidate_fact_prepackaging_atomicity",
        "feature.prospective_candidate_adverse_planner",
        "feature.bounded_candidate_adverse_handoff",
        "feature.research_supervision_candidate_gate",
    ):
        if behavior_features.get(feature_id, {}).get("classification") != "compatibility":
            raise RuntimeError("historical Candidate behavior registry boundary drifted")
    skill_text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
    skill_line_count = len(skill_text.splitlines())
    policy_paths = (
        skill_root / "SKILL.md",
        skill_root / "references" / "adoption_policy_v4.md",
        skill_root / "references" / "agent_protocol_v4.md",
        skill_root / "references" / "computational_verification_v4.md",
        skill_root / "references" / "campaigns_and_migration_v4.md",
        skill_root / "references" / "portable_deployment.md",
        skill_root / "references" / "multi_agent_adapter.md",
        skill_root / "references" / "architecture.md",
        skill_root / "references" / "blackboard_graph_v4.md",
        skill_root / "references" / "data_contracts.md",
        skill_root / "references" / "paper_logic_graph_v1.md",
        skill_root / "references" / "paper_input_contracts.md",
        skill_root / "references" / "v5_production_worker_bootstrap.md",
        skill_root / "references" / "v5_supervisor_worker_bootstrap.md",
        skill_root / "references" / "v5_candidate_adverse_worker_bootstrap.md",
        skill_root / "references" / "learner_document_edit_bootstrap.md",
        skill_root / "references" / "v5_worker_return_contract.md",
        skill_root / "references" / "paper_continuation_contract.md",
        skill_root / "references" / "paper_research_pipeline.md",
        skill_root / "references" / "v5_capability_matrix.md",
        skill_root / "references" / "evidence_plane.md",
        skill_root / "references" / "paper-reading-modes.md",
        skill_root / "references" / "math-grilling.md",
        skill_root / "references" / "fact-graph-grilling.md",
        skill_root / "references" / "portable_deployment.md",
        skill_root / "references" / "v0_4_release_traceability.md",
        skill_root / "references" / "unified_architecture.md",
        skill_root / "references" / "reasoning_modes.md",
        skill_root / "references" / "admission_contract.md",
        skill_root / "references" / "chx_runtime_ledger.md",
        skill_root / "references" / "external_source_reliability.md",
        skill_root / "references" / "adverse_routing_evolution.md",
        skill_root / "references" / "capability_difference_audit.md",
        skill_root / "references" / "unified_learning_plane.md",
        skill_root / "references" / "reader_html_export.md",
        skill_root / "references" / "architecture-grilling.md",
        skill_root / "references" / "unified_release_traceability.md",
        skill_root / "references" / "v5_release_traceability.md",
        skill_root / "assets" / "DEPLOY_PROMPT.txt",
        skill_root / "assets" / "AGENTS.routing.md",
        skill_root / "agents" / "openai.yaml",
        skill_root / "INHERITANCE.lock.json",
        skill_root / "scripts" / "paperlib",
        skill_root / "scripts" / "paper_library.py",
        skill_root / "scripts" / "archive_runtime.py",
        skill_root / "scripts" / "local_install.py",
        skill_root / "scripts" / "release_validation.py",
        skill_root / "scripts" / "runtime_cutover.py",
        skill_root / "scripts" / "runtime_cutover_project_validation.py",
        skill_root / "scripts" / "paper_research_pipeline.py",
        skill_root / "scripts" / "mathgraph" / "paper_research_pipeline.py",
        skill_root / "scripts" / "mathgraph" / "paper_research_reliability.py",
        skill_root / "scripts" / "mathgraph" / "runtime_archive.py",
        skill_root / "scripts" / "mathgraph" / "_local_install.py",
        skill_root / "scripts" / "mathgraph" / "runtime_cutover.py",
    )
    policy_texts = {
        path.relative_to(skill_root).as_posix(): path.read_text(
            encoding="utf-8"
        )
        for path in policy_paths
    }
    identity_requirements = {
        "SKILL.md": (
            "name: chalxius",
            current_release_heading,
            "Future releases do not owe runtime or procedural forward compatibility.",
            "Mathematical-safety and Fact-authority",
            "Fact Alpha treats the immutable Research graph",
            "For immutable 0.x Candidate records only",
            "Start through the smallest applicable contract",
            "references/v5_production_worker_bootstrap.md",
            "references/v5_supervisor_worker_bootstrap.md",
            "references/v5_candidate_adverse_worker_bootstrap.md",
            "references/learner_document_edit_bootstrap.md",
            "The prospective truth path is:",
            "Research -> frozen package -> independent verifier decision -> Gateway Research certification",
            "Every worker task card retains three communication planes",
            "current card-bound worker ledger projects any genuine finding",
            "mathematical challenge creates no architecture observation.",
            "New V5 Pulse planning is retired",
            "only prospective Research collaboration path.",
            "records retain status, audit, dispatch, close, void, and abort compatibility.",
            "An ordinary new V5 round has no Blackboard snapshot",
            "exact `null` snapshot bindings",
            "Fact work is asynchronous.",
            "Chalxius Learner only when the user explicitly asks",
            "Grill Me Code",
            "scripts/local_install.py",
            "Main selects one validation",
            "sole public host-global path",
            "eligible CHX observation surfaces",
            "explicit publication request includes merging the corresponding reviewed change into `main` by default",
            "a heartbeat that finds the current task visibly inside an",
            "it creates no project lock, sentinel file, repair state machine",
        ),
        "agents/openai.yaml": (
            'display_name: "Chalxius"',
            "$chalxius",
            "allow_implicit_invocation: true",
        ),
        "INHERITANCE.lock.json": (
            '"skill_name": "chalxius"',
            f'"version": "{current_skill_version}"',
            f'"release_codename": "{release_codename}"',
            '"authority": "cross_project_nontruth_sidecar"',
            '"library_runtime": "bundled_native_local_cli"',
            '"library_cli": "scripts/paperlib"',
            '"zotero_dependency": false',
            '"nonpaper_fact_import": "explicit_user_request_and_operator_only"',
            '"default_evidence_version": 5',
            '"v4_authority_inheritance": false',
            '"version": "0.3.2-code"',
            '"product_availability": "globally_injected"',
            '"semantic_activation": "explicit_programming_grill_or_socratic_intent_only"',
            '"graph_mount_capability": false',
            '"research_authority": false',
            '"renderer_revision": "chalxius-reader-html-20"',
            '"contract_revision": "chalxius-v5-two-subround-research-2"',
            '"legacy_contract_revision": "chalxius-v5-two-subround-research-1"',
            '"supervision_revision": "chalxius-v5-research-supervision-2"',
            '"production_bootstrap_revision": "chalxius-v5-production-worker-bootstrap-1"',
            '"production_bootstrap_activation": "exact_current_machine_bound_production_card_only_with_full_protocol_fallback"',
            '"supervisor_bootstrap_revision": "chalxius-v5-supervisor-worker-bootstrap-1"',
            '"supervisor_bootstrap_activation": "exact_current_machine_bound_supervision_card_only_with_full_protocol_fallback"',
            '"logical_component_revision": "chalxius-v5-logical-supervision-component-1"',
            '"approved_computation_execution_revision": "chalxius-v5-approved-computation-execution-1"',
            '"production_allocation_revision": "chalxius-v5-logical-component-production-allocation-2"',
            '"legacy_production_allocation_revision": "chalxius-v5-supervision-only-refute-allocation-1"',
            '"component_validation": "authoritatively_rederived_from_exact_research_ancestry_with_stored_partition_as_witness_only"',
            '"supervision_validation": "one_ephemeral_command_local_component_bound_cycle_safe_inspection_context_shared_across_planning_subaudits_with_complete_outer_authority_and_hash_validation"',
            '"planning_validation_reuse": "one_command_local_context_only_without_persistent_cache_and_with_fresh_lock_held_overlap_and_liveness_recheck"',
            '"candidate_fields_scope": "procedurally_reserved_0x_compatibility_for_explicit_completion_or_audit_without_machine_authenticated_pre_1_0_provenance_or_new_identity_gate"',
            '"assurance_selection_revision": "chalxius-v5-failure-informed-selective-assurance-1"',
            '"failure_family_registry": "fixed_scope_owned_non_exhaustive_current_registry_with_exact_legacy_hash_readability_and_without_agent_scores_dynamic_learning_or_truth_authority"',
            '"blackboard_default_context": "absent_with_exact_null_id_hash_and_empty_spaces_unless_promoted_query_or_write_space_capability_is_explicitly_requested"',
            '"blackboard_default_write": "none_unless_exact_space_capability_is_explicitly_requested"',
            '"blackboard_historical_snapshot_policy": "existing_frozen_rounds_keep_exact_id_hash_and_bytes_without_backfill_or_default_snapshot_recreation"',
            '"blackboard_return_binding": "copy_exact_card_value_json_null_or_explicit_historical_sha256_string"',
            '"route_key": "route.failure_informed_selective_assurance"',
            '"execution_gate": "safe_live_nonaborted_assignment_local_latest_program_math_disposition_then_exact_supervised_source_and_dependencies_with_lock_held_authority_recheck_before_round_write"',
            '"aborted_supervision_downstream_authority": "never_authorizes_current_fact_package_computation_or_historical_candidate_and_reserves_no_coverage"',
            '"partial_write_recovery": "content_addressed_supervisor_research_reused_by_identical_retry_before_single_round_seal"',
            '"candidate_verifier_gateway_fact_change": false',
            '"layout": "deterministic_theme_multicenter_orbit_fields"',
            '"fixed_output": "visualizations/knowledge-map.html"',
            '"network_runtime": "disabled"',
            '"project_background_read_policy": "default_if_present_never_generate"',
            '"aggressive_bug_audit": "release_time_only"',
            '"contract_revision": "chalxius-chx-run-ledger-5"',
            '"chalxius-chx-run-ledger-1"',
            '"chalxius-chx-run-ledger-2"',
            '"chalxius-chx-run-ledger-3"',
            '"chalxius-chx-run-ledger-4"',
            '"architecture_reconnaissance": "one_prior_full_candidate_tree_content_addressed_receipt_per_repair_lineage"',
            '"resolved_disposition_gate": "reconnaissance_then_tactical_then_latest_integrated_evidence_binding"',
            '"historical_ledger_liveness": "explicit_current_run_ids_plus_content_addressed_cow_administrative_dispositions_without_mtime_or_timeout_guessing"',
            '"chalxius-chx-public-disclosure-2"',
            '"storage": "project_chx_ledgers_or_external_projectless_host_state"',
            '"older_run_policy": "no_backfill_reclassification_invalidation_or_redo"',
            '"contract_revision": "chalxius-adverse-routing-evolution-4"',
            '"user_rule_contract_revision": "chalxius-adverse-routing-evolution-3"',
            '"recommendation_report_revision": "historical_0x_chalxius-main-route-synthesis-queue-3"',
            '"productive_contract_revision": "chalxius-adverse-routing-evolution-2"',
            '"legacy_contract_revision": "chalxius-adverse-routing-evolution-1"',
            '"status": "prospective_retired_frozen_completion_and_historical_readability"',
            '"activation": "procedurally_reserved_explicit_historical_completion_and_audit_only_without_machine_authenticated_pre_1_0_provenance"',
            '"prospective_supervision_guidance": "fixed_scope_owned_non_exhaustive_failure_families_in_every_current_supervision_card"',
            '"prospective_learning_writes": "forbidden"',
            '"proposal_activation": "retired_no_new_proposal_synthesis"',
            '"persistent_rule_authority": "none_for_prospective_work_historical_rules_are_inert_nontruth"',
            '"attack_report": "no_prospective_attack_report_or_zero_report_ceremony"',
            '"worker_runtime_binding": "optional_diagnostic_provenance_content_hash_and_workflow_owner_checks_remain_exact"',
            '"automatic_inheritance": false',
            '"admission_lineage_validation": "two_phase_command_local_projection_with_bounded_reentry_and_exact_provisional_full_agreement"',
            '"candidate_local_shape_and_statement_interface_precheck": "nonauthoritative_rejection_only_before_global_research_replay"',
            '"active_fact_validation_reentry": "command_local_provisional_release_marker_fact_projection_followed_by_complete_outer_validation_and_exact_agreement"',
            '"fact_admission_inspection_reuse": "one_ephemeral_complete_context_before_publication_lock_and_one_distinct_fresh_context_under_lock"',
            '"fact_admission_lock_boundary": "no_authority_cache_crosses_lock_with_fresh_lock_held_history_and_lineage_replay"',
            '"contract_revision": "chalxius-v5-candidate-admission-efficiency-7"',
            '"contract_revision": "chalxius-v5-selective-fact-checkpoint-2"',
            '"batch_seed_revision": "chalxius-v5-candidate-batch-seed-3"',
            '"candidate_fact_atomicity_contract": "exactly_one_semantic_conclusion_atom_per_fact"',
            '"exact_repair_specification": "optional_main_json_is_normalized_hash_bound_into_repair_research_and_task_card"',
            '"contract_revision": "chalxius-v5-campaign-scope-3"',
            '"chalxius-v5-campaign-scope-1"',
            '"chalxius-v5-campaign-scope-2"',
            '"frontier_working_state_revision": "chalxius-v5-campaign-frontier-working-state-2"',
            '"selection": "main_selected_research_with_optional_explicit_campaign_scope"',
            '"research_creation": "atomic_memory_add_campaign_provenance_only"',
            '"membership_model": "campaign_side_many_to_many_nontruth_overlay_derived_from_existing_campaign_events_targets_and_frontier_roles_without_second_graph"',
            '"ordinary_member_semantics": "exact_same_project_research_link_independent_of_attention_roles_with_no_automatic_selection_research_truth_or_fact_effect"',
            '"cross_campaign_selection": "accept_any_exact_same_project_research_and_freeze_campaign_membership_link_before_round_publication"',
            '"campaign_automatic_selection": "only_from_explicit_active_research_goal_target_and_current_head_successor_corridors_never_from_all_members_context_landmarks_history_or_project_wide_scan"',
            '"plan_selection_receipt": "selection_source_exact_research_ids_campaign_membership_link_and_copy_safe_replay_argv_frozen_in_new_round_manifest"',
            '"manual_checkpoint_semantics": "optional_advisory_campaign_note_with_local_sequence_not_the_dynamic_frontier_working_state_generation_and_never_a_staleness_gate"',
            '"checkpoint_refresh_semantics": "advisory_dynamic_frontier_reconciliation_from_exact_semantic_successor_mismatch_only_never_manual_generation_delta_or_checkpoint_presence"',
            '"scheduler": "v5_main_four_factor_frontier"',
            '"exact_search_result_policy": "main_explicitly_disposes_every_material_exact_research_match_as_reference_only_attach_context_promote_landmark_add_head_or_retire_active_head_without_programmatic_importance_relevance_or_truth_inference"',
            '"active_head_full_list_update": "ordinary_full_list_is_additive_and_preserves_omitted_heads_exact_replacement_is_reserved_for_invalid_state_rebuild"',
            '"round_attention_recovery": "zero_argument_status_discovers_all_round_identities_and_deep_validates_only_unresolved_candidates_exact_id_and_all_remain_authoritative"',
            '"frontier_maintenance_heartbeat": "main_ensures_one_exact_project_thread_heartbeat_at_approximately_50_minutes_for_all_targets_heads_contexts_complete_landmark_identities_recent_history_active_rounds_and_material_exact_search_without_research_or_fact_dispatch"',
            '"frontier_maintenance_repair_phase": "heartbeat_trigger_exits_dont_notify_before_any_project_read_or_mutation_during_visible_integrated_repair_candidate_validation_installation_publication_or_pre_research_resume_reconciliation_without_lock_sentinel_state_machine_or_agent_interruption"',
            '"recent_attainment_exact_queue_high_water_limit": 64',
            '"recent_attainment_routine_preview": 4',
            '"recent_attainment_complete_projection": "exact_ids_count_and_digest_retained_beyond_preview"',
            '"historical_landmark_count_quota": null',
            '"historical_landmark_routine_preview": 4',
            '"historical_landmark_complete_projection": "exact_working_state_and_diagnostic_ids_plus_routine_total_count_and_identity_digest"',
            '"preflight_revision": "chalxius-research-draft-admission-preflight-1"',
            '"stance_authorization_revision": "chalxius-research-draft-major-revision-authorization-1"',
            '"project_lifecycle_revision": "chalxius-parallel-verification-lifecycle-1"',
            '"freshness": "durable_project_wide_nonce_uniqueness_across_packet_and_receipt_records"',
            '"neutral_review_submission_revision": "chalxius-neutral-review-submission-1"',
            '"release_capsule_revision": "chalxius-v5-paper-continuation-release-capsule-1"',
            '"mathematical_target_policy_revision": "chalxius-mathematical-target-policy-1"',
            '"independent_pair_contract_revision": "chalxius-independent-adverse-pair-1"',
            '"behavioral_gate_revision": "chalxius-behavioral-feature-gate-2"',
            '"duplicate_body_adjudication_revision": "chalxius-duplicate-body-adjudication-1"',
            '"replace_with_authoritative_mechanism"',
            '"contract_revision": "chalxius-runtime-archive-2"',
            '"forward_upgrade_policy": "future_releases_need_not_preserve_runtime_or_procedural_compatibility;_graph_semantics_are_the_compatibility_surface"',
            '"procedural_compatibility_requirement": false',
            '"ordinary_graph_operation": "runtime_identity_and_archive_location_are_diagnostic_only"',
            '"active_and_write_policy": "graph_semantics_and_owner_boundaries_not_runtime_history"',
            '"contract_revision": "chalxius-bounded-projection-surface-1"',
            '"selected_authority_validation": "complete_exact_content_and_direct_authority_inputs"',
            '"persistent_index": false',
            '"background_cache": false',
            '"watcher_or_scheduler": false',
        ),
        "references/reader_html_export.md": (
            "truth_effect=\"none\"",
            "PROJECT/visualizations/knowledge-map.html",
            "same semantic packet",
            "Fact-plane nodes",
            "There is no watcher, local storage, or graph writeback.",
            "PDF production is outside this feature",
        ),
        "references/paper_continuation_contract.md": (
            "paper-continuation-plan",
            "research-draft-plan",
            "research-draft-disposition-batch",
            "research-draft-authorize-major-revision",
            "research_draft_admission_preflight",
            "project-wide nonrepeating nonces",
            "paper_target_closure",
            "philosophy_semantic_atomicity",
            "philosophy_plain_language_clarity",
            "Clear wording is the default",
            "does not backfill old tasks",
        ),
        "references/paper_research_pipeline.md": (
            "research_draft",
            "external_finished_publication",
            "Do not replace a research draft with a small convenience FactBundle",
            "source_occurrence_ledger",
            "operator_ledger",
            "validation_subject.kind=\"paper\"",
            "compatibility_fact_bundle_substitute=false",
            "content-addressed objects",
            "reliability-matrix",
            "plan_one",
            '"truth_effect": "none"',
        ),
        "references/paper_input_contracts.md": (
            "paper_logic_minimal_logic_bundle.v1.example.json",
            "missing=",
            "paper_revised_writing",
            "philosophy_atomicity",
            "must not be placed in the input",
            "external_finished_publication",
            "proposition_inventory",
            "semantic_direction",
            "explicit inference mini-DAG",
        ),
        "references/v5_capability_matrix.md": (
            "parallel_verification_lifecycle.py",
            "project-wide nonrepeating nonces",
            "Certification and Gateway admission revalidate the same eligible aggregate",
        ),
        "references/v5_worker_return_contract.md": (
            "For an ordinary current",
            "Blackboard value is JSON `null`",
            "obligation_dispositions",
            "complete`, `blocked`, or `not_applicable",
            "program_math_alignments",
            "ordinary language",
            "does not create a Fact",
        ),
        "references/v5_production_worker_bootstrap.md": (
            'research_cycle.subround="production"',
            "Do not preload",
            "Role-specific expansion",
            "external_theorem_applicability.md",
            "external_source_reliability.md",
            "computational_verification_v4.md",
            "A frozen historical card may still contain `adverse_routing`",
            "chx_runtime_ledger.md",
            "computation_source",
            "computation_design",
            "computation_dependencies",
            "preflight-return",
            "Gateway alone certifies Research",
        ),
        "references/v5_supervisor_worker_bootstrap.md": (
            "research_cycle.subround=\"supervision\"",
            "Do not preload",
            "Conditional expansion is local",
            "computational_verification_v4.md",
            "external_theorem_applicability.md",
            "external_source_reliability.md",
            "A frozen historical card may still contain `adverse_routing`",
            "chx_runtime_ledger.md",
            "--task-card /absolute/path/to/exact-task-card.json",
            "research_supervision_report",
            "preflight-return",
            "there is no duplicate Candidate-adverse stage",
            "supervised_production_authority",
        ),
        "references/v5_candidate_adverse_worker_bootstrap.md": (
            'work_mode="refute"',
            "no `research_cycle` field",
            "must not load `v5_production_worker_bootstrap.md`",
            "No new proposal or rule is synthesized",
            "attack_learning=null",
            "preflight-return",
            "validate-return",
            "Certification Decision",
        ),
        "references/learner_document_edit_bootstrap.md": (
            "existing academic teaching Markdown file",
            "no new research result",
            "no-chat-context",
            "Stop the compact path",
            "global architecture change",
        ),
        "references/unified_learning_plane.md": (
            "Chalxius Learner",
            "Chalxius Learner is off by default",
            "`deep` does not activate",
            "Standalone Grill Me 0.3.2-code",
            "globally available to routing",
            "cannot mount Fact, Paper, Audit, Blackboard, or",
            "`$chalxius`, not through standalone `$grill-me`",
        ),
        "references/v5_release_traceability.md": (
            current_traceability_marker,
            "0.8.2 explicit-route-boundaries release overlay",
            "scripts/local_install.py",
            "0.8.0 mathgraph-first release overlay",
            "0.7.15 research-obligation-closure release overlay",
            "0.7.14 bounded-handoff local-install overlay",
            "0.7.13 admission-frontload local-install overlay",
            "0.7.8 early-candidate-gates local-install overlay",
            "0.7.6 selective-admission-checkpoints local-install overlay",
            "0.7.5 bounded-projections local-install overlay",
            "0.7.4 bounded-main-routing overlay",
            "0.7.3 selective-startup overlay",
            "bounded existing-Learner-document cards",
            "Explicit `plan-round` selection",
            "chx-observations/by-id/",
            "0.7.2 integrated-research-efficiency overlay",
            "references/v5_production_worker_bootstrap.md",
            "one ephemeral inspection context",
            "canonical three-role contract",
            "run-20260811T013254358017Z-46283133a345/CHX-001",
            "Current candidate version: `0.4.4`",
            "Release codename: `Back to the Future`",
            "Research -> Candidate Release -> Certification Decision -> Fact",
            "four durable states and three happy-path truth transitions",
            "complete exact-byte index with an immutable round snapshot",
            "26/26",
            "validated candidate, not an installed release",
            "later load some 0.4.1-or-later bytes",
            "Back to the Future field-repair successor",
            "4c2eb4c14605aacf18d4515e4f5515427321fa968f77b9ce2e5b8032dc1f4522",
            "CHX-020",
            "CHX-021",
            "CHX-022",
            "CHX-023",
            "CHX-024",
            "CHX-025",
            "CHX-026",
            "CHX-027",
            "CHX-028",
            "CHX-029",
            "CHX-030",
            "CHX-031",
        ),
        "references/unified_architecture.md": (
            "v5_production_worker_bootstrap.md",
            "Prospective ordinary V5 cards omit Blackboard entirely",
            "same explicit Blackboard snapshot or the same exact absence of one",
            "one command-local inspection",
            "canonical three-role contract",
            "later load some 0.4.1-or-later bytes",
            "Back to the Future field-repair boundaries",
            "two phases",
            "fact-graph-append-target",
        ),
        "references/blackboard_graph_v4.md": (
            "Prospective ordinary V5 Research has no implicit Blackboard query or snapshot",
            "Historical cards retain their frozen root or wider snapshots",
            "ordinary snapshot-free round is not retrofitted after freeze",
        ),
        "references/chx_runtime_ledger.md": (
            "runs started after the 0.4.1 activation boundary",
            "must not be backfilled",
            "never an audit warning, certification blocker, or reason to redo work",
            "truth_effect=none",
            "project_effect=none",
            "Project-bound runs store their ledger at `PROJECT/chx-ledgers/`",
            "Projectless runs use private host task state outside the skill",
            "If `report_required=false`, say nothing about the CHX ledger",
            "Loading some 0.4.1-or-later bytes",
            "--task-card /exact/card.json",
            "`runtime_binding` field is retained only as diagnostic provenance",
            "missing archive or changed runtime may",
            "must not be read as a runtime-compatibility mandate",
            "eligible CHX observation surfaces",
            "the direct order is: finish validation and",
            "close and render the task",
            "later publication belongs",
        ),
        "references/external_source_reliability.md": (
            "current-status assessment may be `not_assessed`",
            "must not trigger copy-on-write repair or",
            "negative status conclusion requires replayable response receipts",
        ),
        "references/admission_contract.md": (
            "full statement hash",
            "two-phase command-local",
            "exact provisional/full agreement",
            "outcome kind alone",
        ),
        "references/evidence_plane.md": (
            "Evidence is a persistent cross-project nontruth plane",
            "There is no automatic scanner or project discovery trigger",
            "evidence_bridge_current",
            "does not silently",
            "No running 0.4.0 project is backfilled",
        ),
        "references/adverse_routing_evolution.md": (
            "`counterexample` return",
            "Main compares the concrete reports",
            "attack report is separate from the CHX",
            "fresh-adverse readiness gate",
            "at most three pending failure families",
            "one reviewed ordinary-language family description",
            "never\nfrom worker-authored route instructions",
            "Only Main may decide",
            "worker_reported_counterexample_nontruth",
            "COPY_EXACT_PROJECT_ID_FROM_TASK_CARD",
            "Do not start from a schema-v4 example",
            "approve_modified",
            "future task cards",
            "Do not backfill attack cases",
        ),
        "references/portable_deployment.md": (
            *current_portable_deployment_markers,
            "0.8.2 Explicit Route Boundaries",
            "scripts/local_install.py",
            "0.8.0",
            "MathGraph First",
            "0.7.15",
            "Research Obligation Closure",
            "64 MiB aggregate",
            "C0 control bytes",
            "no generated bytecode",
            "retired dynamic",
            "no separate attack-report ceremony",
            "Never backfill attack cases",
            "loads some 0.4.1-or-later",
            "The Fact-admission contract is invariant in all modes",
            "V5 `profile-closure-status` computes local process",
            "V5 never activates a V1-V4 root",
            "Fact-package/verifier/Gateway boundary",
            "Preserve runtime continuity before every global cutover",
            "archive_runtime.py",
            "runtime_cutover_project_validation.py",
            "rejects every nonterminal protected project",
            "never authorizes two duplicate audits",
            "runtime_cutover.py",
            "automatically restores",
        ),
        "scripts/archive_runtime.py": (
            "Archive one exact Chalxius runtime for historical task-card reads.",
            "--archive-root",
            "--expected-runtime-identity",
            "read_json_file_nofollow",
        ),
        "scripts/local_install.py": (
            "Install this Chalxius candidate globally through the default fast path.",
            "perform_local_install",
            "--dry-run",
        ),
        "scripts/release_validation.py": (
            '"same_manifest_subsumes_profiles"',
            '"performance_summary"',
            "_repository_release_metadata",
            '"--metadata-only"',
            '"--repository-root"',
        ),
        "scripts/mathgraph/_local_install.py": (
            "Private implementation of the one public host-global installer.",
            'LOCAL_INSTALL_CONTRACT_REVISION = "chalxius-global-local-install-1"',
            "It never reads or mutates a project.",
            "direct rollback root must remain outside skill discovery",
            "local install failed and the prior installation was restored",
        ),
        "scripts/mathgraph/runtime_archive.py": (
            'RUNTIME_ARCHIVE_REVISION = "chalxius-runtime-archive-2"',
            'RUNTIME_ARCHIVE_ENV = "CHALXIUS_RUNTIME_ARCHIVE_ROOT"',
            "content_addressed_historical_archive",
            "historical_read_and_audit_only",
            "archived runtime root is not sealed read-only",
        ),
        "scripts/runtime_cutover.py": (
            "Perform one fail-closed Chalxius install or rollback cutover.",
            "--project-root",
            "--rollback-root",
            "--expected-candidate-manifest-sha256",
            "--project-validation-receipt",
            "--force-full-project-audit",
        ),
        "scripts/runtime_cutover_project_validation.py": (
            "Build one approved, reusable protected-project cutover validation receipt.",
            "--expected-request-sha256",
            "--output",
        ),
        "scripts/mathgraph/runtime_cutover.py": (
            'CUTOVER_CONTRACT_REVISION = "chalxius-runtime-cutover-2"',
            'CUTOVER_PROJECT_RECEIPT_REVISION =',
            "cutover requires protected project roots",
            "automatic rollback also failed",
            "prior installation was restored",
        ),
        "scripts/paperlib": (
            "exec python3 -B",
            "paper_library.py",
        ),
        "scripts/paper_library.py": (
            'CONTRACT_REVISION = "chalxius-paper-library-1"',
            'ARXIV_API_ENDPOINT = "https://export.arxiv.org/api/query"',
            'EVIDENCE_KINDS = {"reviewed_paper_graph", "external_fact_graph"}',
        ),
        "references/adoption_policy_v4.md": (
            "have no Fact-admission authority",
            "Each valid return enters cumulative Research independently",
            "closure never blocks a V5 verifier capsule",
        ),
        "references/agent_protocol_v4.md": (
            "semantically invalid peer receives an immutable local quarantine receipt",
            "Historical V4 round profile repair advice",
            "truth_effect=\"none\"",
        ),
        "references/campaigns_and_migration_v4.md": (
            "V5 never upgrades or inherits authority from a V1-V4",
            "not a V5 path",
            "grant no V5 authority",
        ),
        "references/data_contracts.md": (
            "V5 authority boundary",
            "review, acceptance marker, profile closure, import, or migration receipt is",
        ),
        "references/architecture.md": (
            "Historical V4 storage reference",
            "It is not the V5",
        ),
        "references/architecture-grilling.md": (
            "compatibility-only routing note",
            "stays on the Chalxius",
            "does not activate a learner",
            "Ordinary Chalxius research does not activate Chalxius Learner",
            "does not activate Grill Me Code",
        ),
        "references/math-grilling.md": (
            "only after explicit academic-learning intent",
            "does not activate it by itself",
            "Learner off",
        ),
        "references/paper-reading-modes.md": (
            "only after explicit academic teaching",
            "ordinary Chalxius research",
            "never activates",
            "learner by itself",
        ),
        "references/fact-graph-grilling.md": (
            "only after the user explicitly requests academic teaching",
            "Do not activate Chalxius Learner for ordinary research",
            "mount a graph unless it materially improves",
        ),
        "assets/AGENTS.routing.md": (
            "Chalxius Learner（内部 Grill 学习器）",
            "Grill Me Code（外部编程辅助）",
            "普通研究、论文审计、系统能力测试或 Fact 准入不得自动启动它",
            "普通编码、实现、调试或代码审查任务不得自动启动它",
            "不同时启动二者",
        ),
    }
    missing_identity_markers = [
        f"{relative}: {marker}"
        for relative, markers in identity_requirements.items()
        for marker in markers
        if marker not in policy_texts[relative]
        and " ".join(marker.split())
        not in " ".join(policy_texts[relative].split())
    ]
    if missing_identity_markers:
        raise RuntimeError(
            "missing Chalxius identity or companion-boundary markers: "
            + ", ".join(missing_identity_markers)
        )
    with tempfile.TemporaryDirectory(prefix="chalxius-self-test-chx-") as directory:
        project_root = Path(directory) / "project"
        started = start_ledger(
            project_root=project_root,
            task="Self-test the prospective silent-zero CHX contract.",
            run_id="run-self-test-chx-001",
            host_task_scope_id="self-test",
        )
        ledger_path = Path(started["ledger_path"])
        if (
            started["state"] != "open"
            or started["skill_version"] != current_skill_version
            or started["report_required"]
            or ledger_path.parent != (project_root / "chx-ledgers").resolve()
        ):
            raise RuntimeError("CHX start/silent-zero contract failed")
        closed = close_ledger(ledger_path)
        if (
            closed["state"] != "closed"
            or closed["report_required"]
            or close_ledger(ledger_path) != closed
            or ledger_status(ledger_path) != closed
        ):
            raise RuntimeError("CHX close/idempotence contract failed")
    with tempfile.TemporaryDirectory(prefix="chalxius-self-test-fixed-review-") as directory:
        review_store = MathGraphStore(Path(directory) / "project")
        review_store.initialize(
            project_id="self-test-fixed-review",
            title="Self-test fixed Research review guidance",
            workflow_evidence_version=5,
        )
        review_lifecycle = review_store.v5_lifecycle()
        target = review_lifecycle.add_research(
            {
                "kind": "challenge",
                "claim": "Check one quantifier-sensitive claim.",
                "logic_signals": ["quantifier_sensitive"],
            },
            actor="self-test-main",
        )
        planned = review_lifecycle.create_round(
            workers=1,
            research_ids=[target["research_id"]],
            host_task_scope_id="self-test-fixed-review-task",
        )
        card = json.loads(
            Path(planned["assignments"][0]["task_card_path"]).read_text(
                encoding="utf-8"
            )
        )
        if (
            "adverse_routing" in card
            or "adverse_routing_enabled_at_freeze"
            in card["context_selection"]["mode"]
            or review_store.adverse_routes().status()["state_materialized"]
        ):
            raise RuntimeError(
                "prospective fixed review unexpectedly activated adverse learning"
            )
    if "Start every paper-reading response" in policy_texts[
        "references/paper-reading-modes.md"
    ]:
        raise RuntimeError(
            "paper-reading modes still auto-activate the learner"
        )
    forbidden_v5_architecture_claims = {
        "references/portable_deployment.md": (
            "record exact typed evidence with `profile-closure-record` before constructing a verifier task",
            "is read-only until an operator records `mode-init`",
            "Imported facts retain inherited assurance",
        ),
        "references/adoption_policy_v4.md": (
            "Missing or drifted closure blocks both single-Fact and atomic-bundle verifier tasks",
        ),
        "references/agent_protocol_v4.md": (
            "writes a `pulse-abort` receipt bound to that evidence",
            "Verifier-task creation and admission require closure",
        ),
        "references/capability_difference_audit.md": (
            "before verification/admission",
        ),
    }
    stale_v5_architecture_claims = [
        f"{relative}: {marker}"
        for relative, markers in forbidden_v5_architecture_claims.items()
        for marker in markers
        if marker in policy_texts[relative]
    ]
    if stale_v5_architecture_claims:
        raise RuntimeError(
            "stale V4 authority claim in active V5 guidance: "
            + ", ".join(stale_v5_architecture_claims)
        )
    stale_public_names = [
        f"{relative}: {marker}"
        for relative, text in policy_texts.items()
        for marker in ("Chalk Nexus", "chalk-nexus")
        if marker in text
    ]
    if stale_public_names:
        raise RuntimeError(
            "stale pre-Chalxius public names: " + ", ".join(stale_public_names)
        )
    collaboration_policy = "\n".join(policy_texts.values())
    required_collaboration_markers = (
        "three communication planes",
        'score_role="priority_ordering_only"',
        "priority/load ordering",
        "optional two-wave coordination layer",
        "durable two-wave pulse",
        "independently repeated check",
        "active-interval union",
        "Exactly 1200 seconds does not trigger",
        "strictly greater than 1200 seconds",
        "experimental nature",
        "actual elapsed time and observed resources",
        "progress and latest checkpoint",
        "importance and continuation value",
        "impact of stopping",
        "Worker telemetry",
        "safety and integrity caps",
        "user-authorized V4 revision",
        "frozen legacy adoption binding",
        "cooperative evidence layer",
        "execution_profile",
        "default-if-present",
        "explicit blocker",
        "mode-init",
        "legacy standalone",
        "nontruth learning plane",
        "host_task_scope_id",
        "archival-only",
        "expert-lint-receipts",
        "interpret-lint-receipts",
        "fails before",
        "pulse-abort",
        "pulse-dispatch",
        "--host-config",
        "preflight-return",
        "procedural_ready",
        "machine_verified_ready",
        "federation is disabled",
        "never sends SIGKILL",
        "managed work remains runnable",
        "current/history",
        "prepare_verifier_capsule.py",
        "Paper Logic",
        "exploration_challenges_audit",
        "repair from refutation",
        "profile_obligations",
        "profile-closure-status",
        "profile-closure-record",
        "workflow_readiness_only",
        "mixed_procedural_and_machine_verified",
        "source_ambiguity",
        "V1-V3",
    )
    missing_collaboration_markers = [
        marker
        for marker in required_collaboration_markers
        if marker not in collaboration_policy
    ]
    if missing_collaboration_markers:
        raise RuntimeError(
            "missing default parallel-blackboard policy markers: "
            + ", ".join(missing_collaboration_markers)
        )
    forbidden_collaboration_markers = (
        "about 20 minutes",
        "20 minutes or longer",
        "estimated above 300 seconds",
        "unknown-duration, or over-300s",
        "default two-or-three-worker",
        "begin with the smallest complementary panel",
        "Substantive Chalk work defaults to two clean-context workers",
        "Launch two complementary workers",
        "make a two-worker constructive",
        "active campaign as the durable task scope",
        "project plus active campaign",
        "derived from project and campaign",
        "branches expected to run about",
        "one pending main/operator decision",
        "one notice and one main/operator decision",
        "obtain one main/operator decision",
        "one notice and one decision",
        "decision_required",
    )
    stale_collaboration_markers = [
        f"{relative}: {marker}"
        for relative, text in policy_texts.items()
        for marker in forbidden_collaboration_markers
        if marker in text
    ]
    if stale_collaboration_markers:
        raise RuntimeError(
            "stale estimate-gated collaboration policy markers: "
            + ", ".join(stale_collaboration_markers)
        )
    current_routing_surfaces = (
        "SKILL.md",
        "references/adoption_policy_v4.md",
        "references/agent_protocol_v4.md",
        "references/campaigns_and_migration_v4.md",
        "references/portable_deployment.md",
        "references/architecture.md",
        "references/blackboard_graph_v4.md",
        "references/paper_logic_graph_v1.md",
        "references/paper-reading-modes.md",
        "assets/DEPLOY_PROMPT.txt",
    )
    forbidden_unified_routing_markers = (
        "substantive Chalk research " + "fills " + "every callable",
        "Substantive Chalk work " + "uses every callable",
        "Use this protocol only when `$mathgraph-chalk-version` is the sole",
        "Use `$mathgraph-chalk-version` as the only MathGraph skill",
        "Permit explicit or implicit invocation of $mathgraph-chalk-version",
        "External Grill Me overlay",
        "mount the Fact Graph only",
        "Substantive Chalk work fills every callable",
        "Substantive Chalk work uses every callable",
    )
    stale_unified_routing = [
        f"{relative}: {marker}"
        for relative in current_routing_surfaces
        for marker in forbidden_unified_routing_markers
        if marker in policy_texts[relative]
    ]
    if stale_unified_routing:
        raise RuntimeError(
            "current unified surfaces retain standalone routing rules: "
            + ", ".join(stale_unified_routing)
        )

    reader_packet = load_reader_packet(
        skill_root / "assets" / "reader_packet.v1.example.json",
        project_id="reader-demo",
    )
    reader_html_first, reader_meta_first = render_reader_html(reader_packet)
    reader_html_second, reader_meta_second = render_reader_html(reader_packet)
    reader_packet_sha256 = sha256_json(reader_packet)
    expected_reader_finalize = {
        "schema_version": 1,
        "status": "ready",
        "scope": "presentation_readiness_only",
        "source_snapshot_id": reader_packet["source_snapshot"]["id"],
        "source_snapshot_sha256": reader_packet["source_snapshot"]["sha256"],
        "sidebar_complete_count": len(reader_packet["nodes"]),
        "node_count": len(reader_packet["nodes"]),
        "packet_sha256": reader_packet_sha256,
        "truth_effect": "none",
    }
    if (
        reader_html_first != reader_html_second
        or reader_meta_first != reader_meta_second
        or "connect-src 'none'" not in reader_html_first
        or "@@CHALXIUS_" in reader_html_first
        or reader_meta_first.get("renderer_revision")
        != "chalxius-reader-html-20"
        or reader_meta_first.get("layout")
        != "deterministic_theme_multicenter_orbit_fields"
        or reader_meta_first.get("packet_sha256") != reader_packet_sha256
        or reader_meta_first.get("reader_finalize") != expected_reader_finalize
        or reader_meta_first.get("truth_effect") != "none"
        or reader_meta_first.get("network_runtime") != "disabled"
        or any(
            token not in reader_html_first
            for token in (
                "maximizeTargets",
                "maximizeAllCards",
                "maximizeNodePath",
                "toggleNodeMinimized",
                "directedClosureNodeIds",
                "minimizedNodeIds",
                "sizingUndoStack",
                "sizingRedoStack",
                "undoSizing",
                "redoSizing",
                "node-size-toggle",
                "selected-node-halo",
                "bindNodeSizeToggle",
                "hoveredCanvasNodeId",
                "hoveredControlNodeId",
                "scheduleNodeHoverSync",
                "nextHoveredId",
                "nodeSizeControlAnchor",
                "NODE_SIZE_CONTROL_X_RATIO = 0.29",
                "NODE_SIZE_CONTROL_Y_RATIO = 0.5",
                "NODE_SIZE_CONTROL_CARD_HEIGHT_RATIO = 0.45",
                "applyNodeSizingClasses",
                "bounds.x1 + (bounds.x2 - bounds.x1) * NODE_SIZE_CONTROL_X_RATIO",
                "bounds.y1 + (bounds.y2 - bounds.y1) * NODE_SIZE_CONTROL_Y_RATIO",
                "compact.height * cy.zoom() * NODE_SIZE_CONTROL_CARD_HEIGHT_RATIO",
                "transition.oldAnchor.x - newAnchor.x",
                "transition.oldAnchor.y - newAnchor.y",
                "transition.node.position(compensated)",
                "'text-max-width': 106, 'text-margin-x': 18",
                "'text-max-width': 102, 'text-margin-x': 18",
                "'text-max-width': 98, 'text-margin-x': 17",
                "'text-max-width': 92, 'text-margin-x': 17",
                "'text-justification': 'left'",
                "'arrow-scale': 1.65",
                "'mid-target-arrow-shape': 'triangle'",
                "syncSelectedNodeHalo",
                "drop-shadow",
                'id="undo-sizing-button"',
                'id="redo-sizing-button"',
                'id="reload-graph-button"',
                "window.location.reload()",
                '"reader_finalize":{',
                'data-appearance-scheme="faceted"',
                'data-appearance-scheme="plaques"',
                "selectedId",
                "selectedNodeIds",
                "showBatchSelectionDetail",
                "boxSelectionEnabled: false",
                "box-selection-marquee",
                "selectedNodesInRectangle",
                "groupDrag",
                "lastMovedSelectionCount",
                "userPanningEnabled: false",
                "selectionType: 'additive'",
                "coreDistanceRanks",
                "radialRingRadii",
                "radialLayoutCoordinates",
                "layoutNodeBoundaryGap",
                "RADIAL_VISIBLE_EDGE_GAP",
                "applyDynamicForces",
                "scheduleDynamicForces",
                "scheduleSizingConvergence",
                "dynamicForceExecutedPasses",
                "lastSizingConvergencePasses",
                "DYNAMIC_ATTRACTION_TARGET_GAP",
                "dynamicAttractionEdges",
                "pinnedCollisionYieldEnabled",
                "repelledPinned",
                "dynamicRepelledPinnedCount",
                "RADIAL_RING_PHASE",
                "CROSSING_REFINEMENT_CANDIDATE_LIMIT",
                "layoutRefinementCandidates",
                "themeOrbitGroups",
                "themeOrbitRadii",
                "themeOrbitCenters",
                "themeOrbitRingAssignments",
                "sharedOrbitIntersectionPosition",
                "themeOrbitCoordinates",
                "themeOrbitRadiiByThemeId",
                "nodeOrbitAssignmentsByNodeId",
                "localized-multicenter-theme-field-equilibrium",
                "deterministic-theme-multicenter-orbit-fields",
                'id="orbit-gravity-button"',
                "kind: 'theme-orbit'",
            )
        )
        or reader_html_first.count('data-context-command="') != 2
        or reader_html_first.count('data-appearance-scheme="') != 2
        or any(
            token in reader_html_first
            for token in (
                "applyAllTargetsDisclosure",
                "applyAllCardsDisclosure",
                "applyNodeFocusDisclosure",
                "directedClosureEdgeIds",
                "toggleNodeSide",
                "setEdgeExpanded",
                "collapseNodeSide",
                "canvasEdgeIds",
                "canvasRootIds",
                "disclosurePreset",
                "edge-handle",
                "edge-stub-line",
                "node-side-control",
                "surfaceMode",
                "focusDomainEdgeIds",
                "focusEdgeIds",
                "enterFocusView",
                "exitFocusView",
                "bindNodeSizeToggleGesture",
                "NODE_SIZE_CONTROL_INSET",
                "NODE_SIZE_CONTROL_DRAG_THRESHOLD",
                "if (minimized) return center;",
                'data-dragging="yes"',
                "button.setPointerCapture",
                'id="back-to-overview-button"',
            )
        )
    ):
        raise RuntimeError(
            "deterministic offline reader HTML self-test failed"
        )
    size_toggle_start = reader_html_first.find("  function bindNodeSizeToggle(")
    size_toggle_end = reader_html_first.find(
        "\n  function ",
        size_toggle_start + len("  function bindNodeSizeToggle("),
    )
    size_toggle_source = (
        reader_html_first[size_toggle_start:size_toggle_end]
        if size_toggle_start >= 0 and size_toggle_end >= 0
        else ""
    )
    if not size_toggle_source or any(
        token in size_toggle_source
        for token in (
            "pointermove",
            "mousemove",
            "setPointerCapture",
            "state.pinned",
            ".position(",
            "suppressClick",
            "NODE_SIZE_CONTROL_DRAG_THRESHOLD",
        )
    ):
        raise RuntimeError(
            "reader size control must remain a click-only action, not a drag surface"
        )
    if (
        reader_html_first.count(
            "dom.reloadGraph.addEventListener('click', () => window.location.reload())"
        )
        != 1
    ):
        raise RuntimeError(
            "reader reload must remain one click-only browser refresh action"
        )
    for field in ("summary", "intuition", "importance", "reasoning"):
        for invalid in ("", " \t\r\n "):
            invalid_packet = json.loads(json.dumps(reader_packet))
            invalid_packet["nodes"][0][field] = invalid
            try:
                render_reader_html(invalid_packet)
            except ValueError as exc:
                if f"nodes[0].{field} must be nonempty" not in str(exc):
                    raise RuntimeError(
                        f"reader finalize rejected {field} for the wrong reason: {exc}"
                    ) from exc
            else:
                raise RuntimeError(
                    f"reader finalize accepted an empty or whitespace-only {field}"
                )

    minimum_zoom = 0.36
    control_x_ratio = 0.29
    control_y_ratio = 0.5
    control_height_ratio = 0.45
    reader_role_geometry = {
        "target": (78.0, 46.0, 254.0, 106.0, 18.0),
        "definition": (80.0, 44.0, 246.0, 102.0, 18.0),
        "result": (76.0, 44.0, 238.0, 98.0, 17.0),
        "explanation": (74.0, 44.0, 226.0, 92.0, 17.0),
    }
    for role, geometry in reader_role_geometry.items():
        compact_width, compact_height, full_width, text_max, text_margin = geometry
        control_size = max(
            11.0,
            min(20.0, compact_height * minimum_zoom * control_height_ratio),
        )
        rendered_width = compact_width * minimum_zoom
        rendered_height = compact_height * minimum_zoom
        compact_clearances = (
            rendered_width * control_x_ratio - control_size / 2,
            rendered_width * (1 - control_x_ratio) - control_size / 2,
            rendered_height * control_y_ratio - control_size / 2,
            rendered_height * (1 - control_y_ratio) - control_size / 2,
        )
        normal_control_size = max(
            11.0,
            min(20.0, compact_height * control_height_ratio),
        )
        label_gap = (
            full_width / 2
            + text_margin
            - text_max / 2
            - full_width * control_x_ratio
            - normal_control_size / 2
        )
        if min(compact_clearances) < 2.0 or label_gap < 8.0:
            raise RuntimeError(
                f"reader control or label geometry is unsafe for role {role}"
            )
        for zoom in (minimum_zoom, 1.0, 3.2):
            rendered_full_width = full_width * zoom
            rendered_control_size = max(
                11.0,
                min(20.0, compact_height * zoom * control_height_ratio),
            )
            control_left = (
                rendered_full_width * control_x_ratio
                - rendered_control_size / 2
            )
            label_right = (
                full_width / 2 + text_margin + text_max / 2
            ) * zoom
            content_center = (control_left + label_right) / 2
            content_bias_ratio = abs(
                content_center - rendered_full_width / 2
            ) / rendered_full_width
            if content_bias_ratio > 0.03:
                raise RuntimeError(
                    f"reader content balance is unsafe for role {role} "
                    f"at zoom {zoom}"
                )

    reader_surface_source = "\n".join(
        (skill_root / relative).read_text(encoding="utf-8")
        for relative in (
            "assets/reader_html_app.js",
            "assets/reader_html_template.html",
            "scripts/mathgraph/reader_html.py",
        )
    )
    if any(
        token in reader_surface_source
        for token in (
            "localStorage",
            "sessionStorage",
            "indexedDB",
            "showSaveFilePicker",
            "showDirectoryPicker",
            "FileSystemWritableFileStream",
            "sendBeacon",
            "XMLHttpRequest",
            "WebSocket",
            "EventSource",
            "fetch(",
            "createObjectURL",
            "showOpenFilePicker",
            'download="',
        )
    ):
        raise RuntimeError(
            "reader HTML must not add persistence, sidecar, or writeback surfaces"
        )
    with tempfile.TemporaryDirectory(prefix="mathgraph-reader-self-test-") as temporary:
        reader_root = Path(temporary) / "project"
        reader_store = MathGraphStore(reader_root)
        reader_store.initialize(
            project_id="reader-demo",
            title="Reader finalize smoke test",
            workflow_evidence_version=4,
            reasoning_mode="auto",
        )
        reader_packet_path = reader_root / "reader-packet.json"
        reader_packet_path.write_text(
            json.dumps(reader_packet, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        reader_receipt = export_reader_html(reader_store, reader_packet_path)
        reader_output = Path(reader_receipt["output"])
        reader_output_before = reader_output.read_bytes()
        invalid_replacement = json.loads(json.dumps(reader_packet))
        invalid_replacement["nodes"][0]["summary"] = " \t\r\n "
        reader_packet_path.write_text(
            json.dumps(invalid_replacement, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        try:
            export_reader_html(reader_store, reader_packet_path)
        except ValueError as exc:
            if "nodes[0].summary must be nonempty" not in str(exc):
                raise RuntimeError(
                    f"invalid reader replacement failed for the wrong reason: {exc}"
                ) from exc
        else:
            raise RuntimeError("invalid reader replacement unexpectedly exported")
        if (
            reader_output.read_bytes() != reader_output_before
            or reader_receipt.get("renderer_revision")
            != "chalxius-reader-html-20"
            or reader_receipt.get("reader_finalize") != expected_reader_finalize
        ):
            raise RuntimeError(
                "invalid reader replacement changed the fixed output or readiness receipt"
            )

    with tempfile.TemporaryDirectory(prefix="chalxius-v5-self-test-") as temporary:
        v5_root = Path(temporary) / "project"
        v5_store = MathGraphStore(v5_root)
        v5_store.initialize(
            project_id="v5-self-test",
            title="V5 authority and background smoke test",
            workflow_evidence_version=5,
        )
        if (
            v5_store.workflow_evidence_version() != 5
            or v5_store.fact_ids()
        ):
            raise RuntimeError("V5 project did not start with empty authority")
        v5_lifecycle = v5_store.v5_lifecycle()
        v5_research = v5_lifecycle.add_research(
            {
                "kind": "conjecture",
                "claim": "Exercise the V5 background binding boundary.",
            },
            actor="self-test-main",
        )
        first_round = v5_lifecycle.create_round(
            workers=1,
            research_ids=[v5_research["research_id"]],
        )
        first_card = v5_store._read_json(
            Path(first_round["assignments"][0]["task_card_path"])
        )
        background_path = v5_root / "PROJECT_BACKGROUND.md"
        if (
            background_path.exists()
            or first_card["mathematical_state"]["project_background"] is not None
        ):
            raise RuntimeError("V5 generated or bound a missing project background")
        background_body = "# Background\n\nUser-directed summary fixture.\n"
        background_path.write_text(background_body, encoding="utf-8")
        second_round = v5_lifecycle.create_round(
            workers=1,
            research_ids=[v5_research["research_id"]],
        )
        second_card = v5_store._read_json(
            Path(second_round["assignments"][0]["task_card_path"])
        )
        background = second_card["mathematical_state"]["project_background"]
        background_bytes = background_body.encode("utf-8")
        chunks = background.get("index", {}).get("chunks", [])
        if (
            background.get("binding_revision")
            != "chalxius-v5-project-background-binding-2"
            or background.get("read_policy")
            != "index_by_default_exact_chunks_on_demand"
            or "body" in background
            or background.get("source_sha256") != sha256_bytes(background_bytes)
            or background.get("snapshot_sha256") != sha256_bytes(background_bytes)
            or background.get("index", {}).get("coverage_receipt", {}).get(
                "omitted_byte_count"
            )
            != 0
            or not chunks
            or (v5_root / background["snapshot_relpath"]).read_bytes()
            != background_bytes
        ):
            raise RuntimeError("V5 did not index and freeze project background exactly")
        reconstructed_background = "".join(
            v5_lifecycle.project_background_chunk(
                card=second_card,
                chunk_id=chunk["chunk_id"],
            )["content"]
            for chunk in chunks
        )
        if reconstructed_background != background_body:
            raise RuntimeError("V5 background chunks did not rehydrate exact source bytes")
    for legacy_trace in ("references/v0_4_release_traceability.md",):
        if "Legacy package history, not current routing" not in policy_texts[
            legacy_trace
        ]:
            raise RuntimeError(
                f"{legacy_trace} lacks the legacy-routing supersession banner"
            )
    surface_requirements = {
        "SKILL.md": (
            "Every worker task card retains three communication planes",
            "references/v5_production_worker_bootstrap.md",
            "references/v5_supervisor_worker_bootstrap.md",
            "references/v5_candidate_adverse_worker_bootstrap.md",
            "references/learner_document_edit_bootstrap.md",
            "work-unit-abort",
            "New V5 Pulse planning is retired",
            "fresh verifier",
            "Project background is optional nontruth context",
            "Generate Reader HTML only on explicit request",
            "does not create Blackboard, Pulse, scoring, or truth",
        ),
        "references/adoption_policy_v4.md": (
            "V5 adaptation",
            "execution_profile",
            "status is `available`",
            "priority/load",
            "strictly greater than 1200 seconds",
            "host_task_scope_id",
            "archival-only",
            "expert-lint-receipts",
            "profile_obligations",
            "profile-closure-status",
            "workflow_readiness_only",
        ),
        "references/agent_protocol_v4.md": (
            "V5 adaptation",
            "execution_profile",
            "every callable clean-context slot",
            "opt-in",
            "may order starts and load within the selected panel",
            "strictly greater than 1200",
            "host_task_scope_id",
            "archival-only",
            "report-blocker",
            "worker-final handoff",
            "managed work remains runnable",
            "pulse-abort",
            "pulse-dispatch",
            "--host-config",
            "preflight-return",
            "prepare_verifier_capsule.py",
            "profile_obligations",
            "profile-closure-record",
            "mixed_procedural_and_machine_verified",
        ),
        "references/multi_agent_adapter.md": (
            "all currently callable clean-context",
            "priority/load ordering",
            "strictly greater than 1200 seconds",
            "MATHGRAPH_HOST_TASK_SCOPE_ID",
            "procedural_ready",
            "machine_verified_ready",
            "Federation is disabled",
            "pulse-dispatch",
            "--host-config",
            "preflight-return",
        ),
        "references/data_contracts.md": (
            "preflight-return",
            "Paper Logic and Audit Graph evidence",
            "Unified round profile closure",
            "profile_obligations",
            "workflow_readiness_only",
        ),
        "references/paper_logic_graph_v1.md": (
            "paper_source",
            "paper_reconstruction",
            "paper_audit",
            "agent_exploration",
            "exploration_challenges_audit",
            "local repair",
            "refutes_exact_claim",
            "paper_logic_mirror",
        ),
        "assets/DEPLOY_PROMPT.txt": (
            f"Chalxius {current_skill_version} — {release_codename}",
            "Normal global local installation",
            "zero project reads and zero project writes",
            "scripts/runtime_cutover.py",
            "Publication, remote push, tagging, and merge",
            "`route_invalidations` names exact stale Research targets",
            "Prospective Fact admission now certifies exact whole Research records",
            "Fact is therefore an append-only certification property of Research.",
            "Production is constructive.",
            "independent verifier",
            "Administrative receipts are optional",
            "formula-to-code",
            "advisory global route memory",
            "end that heartbeat immediately with `DONT_NOTIFY`",
            "do not add a lock file, sentinel, repair state machine",
            "ordinary new V5 round does not freeze a default Blackboard root snapshot",
            "Historical frozen rounds keep exact byte/hash validation",
        ),
        "references/reasoning_modes.md": (
            "future-only switch",
            "fast",
            "auto",
            "deep",
            "explicit blocker",
            "process-readiness compatibility commands",
            "work-unit-abort",
            "never cancels work",
            "certification change",
        ),
        "references/admission_contract.md": (
            "identical in `fast`, `auto`, and `deep`",
            "a fresh independent verifier",
            "automatic inclusion and explicit disposition",
            "machine-derived valuation",
            "atomic internal",
            "not Fact premises",
            "submitted and certified as a new V5 Candidate Release",
        ),
        "references/unified_learning_plane.md": (
            "nontruth",
            "does not invoke a Grill",
        ),
    }
    # Markdown line wrapping is presentation, not a release-contract change.
    # Accept exact markers or the same text after ordinary whitespace
    # normalization so a harmless reflow cannot break installation.
    missing_by_surface = [
        f"{relative}: {marker}"
        for relative, markers in surface_requirements.items()
        for marker in markers
        if marker not in policy_texts[relative]
        and " ".join(marker.split())
        not in " ".join(policy_texts[relative].split())
    ]
    if missing_by_surface:
        raise RuntimeError(
            "policy surface is missing a binding marker: "
            + ", ".join(missing_by_surface)
        )

    with tempfile.TemporaryDirectory(prefix="mathgraph-self-test-") as temporary:
        temporary_root = Path(temporary)
        ledger_path = temporary_root / "event-ledger" / "events.jsonl"
        ledger = ExperimentEventLedger(ledger_path)
        ledger_semantic = {
            "schema_version": 1,
            "policy_revision": "mathgraph-0.3.0",
            "event": "heartbeat",
            "stage": "smoke",
            "latest_check": "event-index smoke",
        }
        ledger_event_id = sha256_json(ledger_semantic)
        ledger_event = {
            **ledger_semantic,
            "event_id": ledger_event_id,
        }

        def append_ledger_event_once(
            session: ExperimentEventIndexSession,
        ) -> None:
            if session.find(ledger_event_id) is None:
                session.append(ledger_event)

        ledger.mutate(append_ledger_event_once)
        ledger_before_replay = ledger_path.read_bytes()
        ledger.mutate(append_ledger_event_once)
        if (
            ledger_path.read_bytes() != ledger_before_replay
            or not ledger.index_path.is_file()
        ):
            raise RuntimeError("rebuildable event index is not idempotent")
        # Exercise read compatibility with one deliberately isolated legacy
        # fixture through the private identity-authorized fixture seam.
        store = MathGraphStore._for_legacy_workflow_fixture(
            temporary_root / "project"
        )
        store.initialize(
            project_id="smoke",
            title="Portable schema-v3 smoke test",
            workflow_evidence_version=3,
            reasoning_mode=None,
        )
        if store.project().get("workflow_evidence_version") != 3:
            raise RuntimeError("new project does not label workflow evidence schema v3")
        source_statement = "Theorem 1. For every smoke object, H implies P."
        applicability_proof = (
            "Check the source hypothesis [APP:SMOKE:H1]. "
            "Match the source convention [APP:SMOKE:C1]. "
            "Apply its exact conclusion [APP:SMOKE:USE]. "
            "Audit its statement and source reliability [CRIT:SMOKE:USE]."
        )
        source_artifact_sha256 = sha256_bytes(b"smoke primary artifact")
        source_artifact_locator = (
            "https://example.org/primary-source/version-1.pdf"
        )
        source_audit_core = {
            "artifact_sha256": source_artifact_sha256,
            "artifact_locator": source_artifact_locator,
            "checked_at": "2026-07-24",
            "issue_searches": [
                {
                    "kind": "version_history",
                    "query": "Applicability smoke source version history",
                    "locator": "https://example.org/primary-source/versions",
                    "finding": "No statement drift was found.",
                },
                {
                    "kind": "errata",
                    "query": "Applicability smoke source erratum correction",
                    "locator": "https://example.org/primary-source/errata",
                    "finding": "No applicable erratum was found.",
                },
                {
                    "kind": "retraction_or_counterexample",
                    "query": (
                        "Applicability smoke source retraction counterexample false"
                    ),
                    "locator": "https://example.org/primary-source/status",
                    "finding": "No retraction or counterexample was found.",
                },
            ],
            "unresolved_signals": [],
            "finding": "The source-level checks found no unresolved signal.",
        }
        validate_external_refs_for_submission(
            [
                {
                    "key": "SMOKE",
                    "title": "Applicability smoke source",
                    "url": "https://example.org/primary-source",
                    "use_kind": "result",
                    "cited_for": "The exact smoke implication.",
                    "source_evidence_version": 3,
                    "source_trace": {
                        "artifact_sha256": source_artifact_sha256,
                        "artifact_locator": source_artifact_locator,
                        "retrieved_at": "2026-07-24",
                        "statement_locator": "Theorem 1, version 1, p. 1",
                        "statement_text": source_statement,
                        "statement_sha256": sha256_bytes(
                            source_statement.encode("utf-8")
                        ),
                        "inspection_methods": ["rendered_primary"],
                    },
                    "critical_audit": {
                        "profile": "baseline",
                        "risk_triggers": [],
                        "sanity_checks": [
                            {
                                "kind": "notation_and_binding",
                                "status": "pass",
                                "finding": "All symbols are bound.",
                            },
                            {
                                "kind": "type_and_domain",
                                "status": "pass",
                                "finding": "The smoke object has the required type.",
                            },
                            {
                                "kind": "quantifiers_and_scope",
                                "status": "pass",
                                "finding": "The universal scope agrees with the proof.",
                            },
                        ],
                        "source_audit": {
                            **source_audit_core,
                            "audit_sha256": sha256_json(source_audit_core),
                        },
                        "source_audit_reuse": {
                            "mode": "fresh",
                            "reused_at": "2026-07-24",
                            "origin": "current_submission",
                        },
                        "assessment": "as_stated",
                        "issues": [],
                        "justification": "The baseline checks found no source defect.",
                        "proof_anchor": "[CRIT:SMOKE:USE]",
                    },
                    "applicability": {
                        "source_version": "version 1",
                        "source_locator": "Theorem 1, version 1, p. 1",
                        "source_scope": "Objects satisfying H.",
                        "target_scope": "The smoke object.",
                        "source_conclusion": "H implies P.",
                        "used_conclusion": "The smoke object has P.",
                        "hypothesis_map": [
                            {
                                "source_hypothesis": "H.",
                                "target_witness": "Direct check in the proof.",
                                "proof_anchor": "[APP:SMOKE:H1]",
                            }
                        ],
                        "convention_map": [
                            {
                                "source_convention": "Ordinary equality convention.",
                                "target_convention": "The same convention is used.",
                                "proof_anchor": "[APP:SMOKE:C1]",
                            }
                        ],
                        "transport_obligations": [],
                        "exclusions_checked": ["Adjacent definitions and remarks checked."],
                        "strength_comparison": "exact",
                        "verdict": "direct",
                        "proof_anchor": "[APP:SMOKE:USE]",
                    },
                }
            ],
            applicability_proof,
            require_critical_audit=True,
        )
        elementary_proof = (
            "The displayed Jacobian determinant equals 1, so the local holomorphic "
            "inverse-function theorem applies [ELM:SMOKE-IFT]."
        )
        validate_elementary_uses_for_submission(
            [
                {
                    "key": "SMOKE-IFT",
                    "result": "Holomorphic inverse-function theorem at one point",
                    "category": "local_inverse_implicit",
                    "hypothesis_witnesses": [
                        "The proof displays the holomorphic map and computes determinant 1."
                    ],
                    "used_conclusion": "A unique local holomorphic inverse germ exists.",
                    "scope_limitations": [
                        "Local germ only.",
                        "No family-uniform or monodromy conclusion.",
                    ],
                    "reconstruction": (
                        "Apply the finite-dimensional holomorphic inverse-function theorem at "
                        "the displayed point and restrict to sufficiently small neighborhoods."
                    ),
                    "proof_anchor": "[ELM:SMOKE-IFT]",
                }
            ],
            elementary_proof,
        )
        bare_citation = Fact(
            problem_id="smoke",
            author="worker",
            predecessors=[],
            statement="A bare citation should fail.",
            proof="Citation only.",
            external_refs=[
                {
                    "key": "BARE",
                    "title": "Uncertified source",
                    "url": "https://example.org/source",
                    "use_kind": "result",
                    "cited_for": "An unsupported step.",
                }
            ],
        )
        try:
            store.submit(bare_citation, worker="worker")
        except ValueError:
            pass
        else:
            raise RuntimeError("bare external citation passed the applicability gate")
        fact = Fact(
            problem_id="smoke",
            author="worker",
            predecessors=[],
            statement="For every integer n, n=n.",
            proof="This is reflexivity of equality.",
        )
        store.submit(fact, worker="worker")
        frozen = store.freeze_verification_packet(fact.fact_id)
        try:
            store.record_review(
                {
                    "fact_id": fact.fact_id,
                    "submission_sha256": frozen["submission_sha256"],
                    "packet_sha256": frozen["packet_sha256"],
                    "verdict": "correct",
                    "critical_errors": [],
                    "gaps": [],
                    "repair_hints": [],
                    "reviewer": "WORKER",
                }
            )
        except ValueError:
            pass
        else:
            raise RuntimeError("case-folded worker identity was allowed to self-review")
        review_id = review(store, fact.fact_id, reviewer="fresh-verifier")
        store.admit(fact.fact_id, review_id=review_id, gateway="smoke-gateway")
        store.admit(fact.fact_id, review_id=review_id, gateway="smoke-gateway")
        store.set_targets([fact.fact_id])

        stale = Fact(
            problem_id="smoke",
            author="second-worker",
            predecessors=[fact.fact_id],
            statement="Reflexivity has a second name.",
            proof=f"This is only a renaming of verified fact {fact.fact_id}.",
        )
        store.submit(stale, worker="second-worker")
        older_correct = review(store, stale.fact_id, reviewer="first-verifier")
        review(
            store,
            stale.fact_id,
            reviewer="adversarial-verifier",
            verdict="reject",
            errors=["The statement is not an atomic mathematical consequence."],
        )
        try:
            store.admit(stale.fact_id, review_id=older_correct)
        except ValueError:
            pass
        else:
            raise RuntimeError("an older clean review bypassed a later rejection")

        memory_id = store.memory_add(
            {
                "kind": "conjecture",
                "claim": "Use the smoke fact in one generated assignment.",
                "dependencies": [fact.fact_id],
                "suggested_actions": ["prove directly"],
            },
            actor="smoke-main",
        )
        manifest = create_round(store, workers=1, memory_ids=[memory_id])
        assignment = manifest["assignments"][0]
        if not Path(assignment["artifact_dir_path"]).is_dir():
            raise RuntimeError("schema-v3 assignment artifact directory is missing")
        return_path = Path(assignment["return_path"])
        return_path.write_text(
            json.dumps(
                {
                    "project_id": manifest["project_id"],
                    "round_id": manifest["round_id"],
                    "assignment_id": assignment["assignment_id"],
                    "assignment_sha256": assignment["assignment_sha256"],
                    "worker": assignment["worker_id"],
                    "memory_id": assignment["memory_id"],
                    "mode": assignment["mode"],
                    "outcome": "evidence",
                    "notes": "portable bound-return check",
                    "claim": "Reflexivity is reusable.",
                    "method": "Direct inspection.",
                    "result": {"value": True},
                    "artifacts": [],
                    "limitations": ["Evidence smoke test only."],
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        validated = validate_return(
            store,
            manifest["round_id"],
            assignment["assignment_id"],
        )
        if validated["return_sha256"] != sha256_bytes(return_path.read_bytes()):
            raise RuntimeError("worker validate-return did not bind exact bytes")
        receipt = ingest_return(
            store,
            manifest["round_id"],
            assignment["assignment_id"],
            worker_final_sha256=sha256_bytes(return_path.read_bytes()),
        )
        replay = ingest_return(
            store,
            manifest["round_id"],
            assignment["assignment_id"],
            worker_final_sha256=sha256_bytes(return_path.read_bytes()),
        )
        if (
            receipt != replay
            or receipt.get("status") != "ingested"
            or receipt.get("schema_version") != 3
            or receipt.get("artifacts") != []
        ):
            raise RuntimeError("assignment-bound exactly-once ingestion failed")

        report = store.audit()
        if not report.ok or report.facts != 1 or report.target_closure != 1:
            raise RuntimeError(json.dumps(report.as_dict(), sort_keys=True))
        store.revoke(fact.fact_id, reason="smoke revocation", actor="smoke-gateway")
        try:
            store.admit(fact.fact_id, review_id=review_id, gateway="smoke-gateway")
        except ValueError:
            pass
        else:
            raise RuntimeError("revoked fact was re-admitted from stale state")

        old_skill_root = os.environ.get("MGRAPH_SKILL_ROOT")
        os.environ["MGRAPH_SKILL_ROOT"] = str(skill_root)
        try:
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                code = cli_main(
                    [
                        "--root",
                        str(skill_root / "forbidden-project"),
                        "--role",
                        "operator",
                        "init",
                        "--project-id",
                        "forbidden",
                        "--title",
                        "Forbidden",
                    ]
                )
            if code == 0:
                raise RuntimeError("CLI allowed project state inside the skill")
        finally:
            if old_skill_root is None:
                os.environ.pop("MGRAPH_SKILL_ROOT", None)
            else:
                os.environ["MGRAPH_SKILL_ROOT"] = old_skill_root
        try:
            store.report_output_path("../escape.md")
        except ValueError:
            pass
        else:
            raise RuntimeError("report output escaped the project reports directory")

    with tempfile.TemporaryDirectory(prefix="mathgraph-v4-self-test-") as temporary:
        v4_root = Path(temporary) / "project"
        v4_store = MathGraphStore(v4_root)
        v4_store.initialize(
            project_id="v4-smoke",
            title="Portable schema-v4 round smoke test",
            workflow_evidence_version=4,
        )
        if v4_store.project().get("workflow_evidence_version") != 4:
            raise RuntimeError("explicit v4 project did not retain workflow version 4")
        paper_store = v4_store.paper_logic()
        paper_store.initialize(actor="self-test-main")
        paper_artifact = Path(temporary) / "paper-source.txt"
        paper_artifact_bytes = b"It does not follow."
        paper_artifact.write_bytes(paper_artifact_bytes)
        paper_text = paper_artifact_bytes.decode("utf-8")

        def paper_ledger(text: str) -> list[dict[str, object]]:
            return [
                {
                    "operator_id": f"op-{index}",
                    "token": item["token"],
                    "occurrence": item["occurrence"],
                    "kind": item["kind"],
                    "scope": "rendered sentence",
                    "disposition": "logical",
                    "depends_on": [],
                }
                for index, item in enumerate(
                    scan_high_risk_operators(text)
                )
            ]

        paper_nodes = [
            {
                "local_id": "s1",
                "object_type": "source_unit",
                "payload": {
                    "unit_kind": "sentence",
                    "order": 1,
                    "locator": {
                        "kind": "pdf",
                        "pdf_page_index": 0,
                        "printed_page_label": "1",
                        "region": "self-test sentence",
                    },
                    "text": paper_text,
                    "text_sha256": sha256_bytes(
                        paper_text.encode("utf-8")
                    ),
                    "speaker": "author",
                    "inspection_methods": ["rendered_primary"],
                    "render_sha256": sha256_bytes(b"self-test-render"),
                    "context_before": "",
                    "context_after": "",
                    "operator_ledger": paper_ledger(paper_text),
                },
            },
            {
                "local_id": "c1",
                "object_type": "claim",
                "payload": {
                    "representation_kind": "source_literal",
                    "attribution": "author",
                    "discourse_role": "premise",
                    "content_type": "conceptual",
                    "statement": paper_text,
                    "statement_sha256": sha256_bytes(
                        paper_text.encode("utf-8")
                    ),
                    "source_unit_ids": ["s1"],
                    "semantic_diff": "",
                    "modality": "asserted",
                    "scope_notes": "Self-test scope.",
                    "operator_ledger": paper_ledger(paper_text),
                    "definition_ids": [],
                    "parent_claim_id": "",
                },
            },
            {
                "local_id": "c2",
                "object_type": "claim",
                "payload": {
                    "representation_kind": "researcher_reconstruction",
                    "attribution": "researcher",
                    "discourse_role": "headline_conclusion",
                    "content_type": "conceptual",
                    "statement": "The bounded conclusion follows.",
                    "statement_sha256": sha256_bytes(
                        b"The bounded conclusion follows."
                    ),
                    "source_unit_ids": [],
                    "semantic_diff": (
                        "Explicit self-test reconstruction, not a quotation."
                    ),
                    "modality": "asserted",
                    "scope_notes": "Self-test scope.",
                    "operator_ledger": [],
                    "definition_ids": [],
                    "parent_claim_id": "",
                },
            },
            {
                "local_id": "i1",
                "object_type": "inference",
                "payload": {
                    "premise_ids": ["c1"],
                    "conclusion_id": "c2",
                    "inference_kind": "deductive",
                    "strength": "strict",
                    "authorial_status": "researcher_reconstructed",
                    "source_unit_ids": ["s1"],
                    "bridge_claim_ids": [],
                    "defeater_claim_ids": [],
                    "rationale": "Exercise exact ports and polarity.",
                },
            },
            {
                "local_id": "t1",
                "object_type": "paper_target",
                "payload": {
                    "target_role": "headline",
                    "claim_id": "c2",
                    "rationale": "Self-test headline.",
                },
            },
        ]
        paper_local_nodes = {
            item["local_id"]: item for item in paper_nodes
        }
        paper_bundle = {
            "schema_version": 1,
            "feature_revision": PAPER_LOGIC_FEATURE_REVISION,
            "project_id": "v4-smoke",
            "paper_id": "self-test-paper",
            "graph_kind": "logic",
            "domain_profile": "philosophy",
            "source_role": "external_reference",
            "builder": "paper-builder",
            "builder_context_id": "paper-builder-context",
            "source": {
                "artifact_sha256": sha256_bytes(paper_artifact_bytes),
                "artifact_locator": str(paper_artifact),
                "title": "Self-test paper",
                "version": "fixture-v1",
                "mime_type": "text/plain",
                "retrieved_at": "2026-07-26T00:00:00Z",
                "inspection_methods": ["rendered_primary"],
            },
            "base_snapshot_id": "",
            "supersedes_snapshot_id": "",
            "coverage": {
                "scope_kind": "bounded",
                "included_locators": ["pdf:0"],
                "excluded_locators": [],
                "units": [
                    {
                        "unit_id": "s1",
                        "classification": "argumentative",
                        "mapped_node_ids": [
                            "s1",
                            "c1",
                            "c2",
                            "i1",
                            "t1",
                        ],
                        "reason": "",
                    }
                ],
                "unresolved_load_bearing_units": [],
                "completeness_claim": "Complete for one bounded sentence.",
            },
            "nodes": paper_nodes,
            "edges": PaperLogicStore._expected_logic_edges(
                paper_local_nodes
            ),
        }
        paper_staged = paper_store.stage(
            paper_bundle,
            artifact_path=paper_artifact,
            actor="paper-builder",
        )
        paper_revision = paper_store.revision(
            paper_staged["revision_id"]
        )
        for index, profile in enumerate(
            paper_revision["required_review_profiles"],
            1,
        ):
            paper_store.record_review(
                {
                    "schema_version": 1,
                    "feature_revision": PAPER_LOGIC_FEATURE_REVISION,
                    "project_id": "v4-smoke",
                    "revision_id": paper_revision["revision_id"],
                    "bundle_sha256": paper_revision["bundle_sha256"],
                    "profile": profile,
                    "verdict": "correct",
                    "reviewer": f"paper-reviewer-{index}",
                    "reviewer_context_id": (
                        f"paper-review-context-{index}"
                    ),
                    "fresh_context_contract": "fresh-context-v1",
                    "object_checks": [
                        {
                            "object_id": object_id,
                            "status": "pass",
                            "finding": "Self-test object check passed.",
                        }
                        for object_id in sorted(
                            paper_store._expected_review_object_ids(
                                paper_revision,
                                profile,
                            )
                        )
                    ],
                    "global_checks": [
                        {
                            "kind": kind,
                            "status": "pass",
                            "finding": "Self-test global check passed.",
                        }
                        for kind in sorted(REVIEW_GLOBAL_CHECKS[profile])
                    ],
                    "critical_errors": [],
                    "gaps": [],
                    "truth_effect": "none",
                }
            )
        paper_frozen = paper_store.freeze(
            paper_revision["revision_id"],
            actor="self-test-main",
        )
        paper_query = paper_store.query(
            paper_frozen["snapshot_id"],
            view="combined",
            query={
                "seed_ids": [],
                "direction": "both",
                "max_hops": 4,
                "node_budget": 32,
                "edge_budget": 64,
            },
        )
        if (
            paper_query["truth_effect"] != "none"
            or paper_query["omission"]["node_budget_hit"]
            or not paper_store.audit(blackboard=v4_store.blackboard())["ok"]
        ):
            raise RuntimeError("Paper Logic smoke failed")
        campaigns = v4_store.campaigns()

        def campaign_inventory() -> dict[str, str]:
            return {
                path.relative_to(campaigns.root).as_posix(): (
                    "directory"
                    if path.is_dir()
                    else sha256_bytes(path.read_bytes())
                )
                for path in sorted(campaigns.root.rglob("*"))
            }

        before_campaign_gate = campaign_inventory()
        try:
            campaigns.create(
                {
                    "name": "rejected-proof-target",
                    "objective": "Exercise the admitted-fact campaign gate.",
                    "source_claim_ids": [],
                    "targets": [
                        {
                            "role": "headline_proof",
                            "subject_kind": "fact",
                            "subject_id": "f" * 16,
                            "label": "Not admitted",
                        }
                    ],
                    "constraints": [],
                    "stop_conditions": [],
                    "value_definition": "Reject nontruth proof targets.",
                },
                actor="self-test",
                fact_exists=lambda _fact_id: False,
            )
        except ValueError as exc:
            if "not an active admitted fact" not in str(exc):
                raise
        else:
            raise RuntimeError("campaign creation bypassed the admitted-fact gate")
        if campaign_inventory() != before_campaign_gate:
            raise RuntimeError(
                "failed campaign creation left partial campaign state"
            )
        v4_memory_id = v4_store.memory_add(
            {
                "kind": "direction",
                "claim": "Check one exact toy case without promoting it to truth.",
                "rationale": "Exercise the v4 task-card and blackboard boundary.",
                "suggested_actions": ["compute one exact value"],
                "stop_conditions": ["Stop after one exact value is recorded."],
            },
            actor="v4-smoke-main",
        )
        v4_manifest = create_round(
            v4_store,
            workers=1,
            memory_ids=[v4_memory_id],
            mode="compute",
        )
        v4_assignment = v4_manifest["assignments"][0]
        v4_card_path = Path(v4_assignment["task_card_path"])
        v4_card = json.loads(v4_card_path.read_text(encoding="utf-8"))
        if v4_card.get("hard_caps") != DEFAULT_HARD_CAPS:
            raise RuntimeError(
                "v4 task card did not bind the fixed hard-cap profile"
            )
        pulse_store = v4_store.collaboration()
        pulse_plan = pulse_store.create_plan(
            wave1_commitments=[
                pulse_store.make_wave1_commitment(
                    round_id=v4_manifest["round_id"],
                    assignment_id=v4_assignment["assignment_id"],
                    criticality="core",
                )
            ],
            minimum_wave1_contributors=1,
            actor="v4-smoke-main",
        )
        v4_prompt_path = Path(v4_assignment["prompt_path"])
        if v4_prompt_path.stat().st_size >= 4096:
            raise RuntimeError("v4 compact worker prompt exceeded 4 KiB")
        root_space = v4_card["blackboard_view"]["write_space_ids"][0]
        evidence_node = make_node(
            node_type="computation_result",
            logical_key="v4-smoke-value",
            payload={"value": "1", "scope": "toy case only"},
            created_by_assignment_id=v4_card["assignment_id"],
        )
        placement = make_edge(
            edge_type="placed_in",
            source_node_id=evidence_node["node_id"],
            target_node_id=root_space,
            payload={},
            created_by_assignment_id=v4_card["assignment_id"],
        )
        v4_return_path = Path(v4_assignment["return_path"])
        v4_return_bytes = json.dumps(
            {
                "schema_version": 4,
                "policy_revision": "mathgraph-0.3.0",
                "protocol": "mathgraph-agent-v4",
                "project_id": v4_card["project_id"],
                "round_id": v4_card["round_id"],
                "assignment_id": v4_card["assignment_id"],
                "assignment_sha256": v4_card["assignment_sha256"],
                "task_card_sha256": sha256_bytes(
                    v4_card_path.read_bytes()
                ),
                "blackboard_snapshot_sha256": v4_card[
                    "blackboard_snapshot_sha256"
                ],
                "worker": v4_card["worker_id"],
                "memory_id": v4_card["memory_id"],
                "mode": v4_card["mode"],
                "outcome": "evidence",
                "obligation_ledger": [],
                "blackboard_graph_delta": {
                    "base_snapshot_id": v4_card["blackboard_view"][
                        "snapshot_id"
                    ],
                    "add_nodes": [evidence_node],
                    "add_edges": [placement],
                },
                "narrative_summary": (
                    "The exact value is exploration evidence, not an admitted fact."
                ),
                "claim": "The toy expression has value 1.",
                "method": "Exact evaluation.",
                "result": "The value is 1.",
                "artifacts": [],
                "limitations": ["One toy value proves no general statement."],
            },
            sort_keys=True,
        ).encode("utf-8")
        v4_draft_path = (
            Path(v4_assignment["work_dir_path"])
            / "self-test-return-draft.json"
        )
        v4_draft_path.write_bytes(v4_return_bytes)
        before_preflight = {
            path.relative_to(v4_root).as_posix(): path.read_bytes()
            for path in sorted(v4_root.rglob("*"))
            if path.is_file() and not path.is_symlink()
        }
        v4_preflight = preflight_return(
            v4_store,
            v4_manifest["round_id"],
            v4_assignment["assignment_id"],
            input_path=v4_draft_path,
        )
        after_preflight = {
            path.relative_to(v4_root).as_posix(): path.read_bytes()
            for path in sorted(v4_root.rglob("*"))
            if path.is_file() and not path.is_symlink()
        }
        if (
            before_preflight != after_preflight
            or v4_return_path.exists()
            or v4_preflight["return_sha256"]
            != sha256_bytes(v4_return_bytes)
        ):
            raise RuntimeError(
                "v4 return preflight was not an exact read-only dry run"
            )
        v4_return_path.write_bytes(v4_draft_path.read_bytes())
        v4_validated = validate_return(
            v4_store,
            v4_manifest["round_id"],
            v4_assignment["assignment_id"],
        )
        if (
            v4_validated["return_sha256"]
            != v4_preflight["return_sha256"]
        ):
            raise RuntimeError(
                "v4 preflight and canonical validation hashes differ"
            )
        v4_receipt = ingest_return(
            v4_store,
            v4_manifest["round_id"],
            v4_assignment["assignment_id"],
        )
        if (
            v4_receipt.get("schema_version") != 4
            or v4_receipt.get("return_sha256")
            != v4_preflight["return_sha256"]
            or v4_receipt.get("worker_final_sha256")
            != v4_preflight["return_sha256"]
            or evidence_node["node_id"] not in v4_store.blackboard().nodes()
            or v4_store.fact_ids()
        ):
            raise RuntimeError("v4 evidence crossed the exploration/truth boundary")
        pulse_store.abort(
            pulse_plan["pulse_id"],
            failure_phase="self_test_terminal",
            reason=(
                "The portable smoke intentionally ends after Wave 1; "
                "preserve its core evidence without fabricating a review."
            ),
            actor="v4-smoke-main",
        )
        if pulse_store.status(pulse_plan["pulse_id"])["state"] != "aborted":
            raise RuntimeError("v4 pulse abort smoke did not reach terminal state")
        v4_report = v4_store.audit()
        if not v4_report.current_ok or not v4_report.history_clean:
            raise RuntimeError(json.dumps(v4_report.as_dict(), sort_keys=True))

    print(
        "SELF_TEST=PASS schema_v3=PASS schema_v4_round=PASS schema_v5=PASS "
        "v5_empty_authority=PASS v5_background_default_read=PASS "
        "v4_blackboard=PASS admission_gate=PASS review_binding=PASS "
        "round_binding=PASS validate_return=PASS artifact_manifest=PASS "
        "applicability_gate=PASS critical_source_gate=PASS tiered_source_gate=PASS "
        "source_audit_hash=PASS elementary_gate=PASS "
        "audit=PASS revocation=PASS containment=PASS event_index=PASS "
        "parallel_blackboard_policy=PASS priority_ordering_policy=PASS "
        "actual_time_policy=PASS hard_caps=PASS pulse_abort=PASS "
        "preflight_return=PASS campaign_atomic_create=PASS "
        "paper_logic=PASS paper_review_gate=PASS "
        "reader_html=PASS chx_runtime_ledger=PASS fixed_review=PASS "
        "research_draft_roles=PASS verification_lifecycle_roles=PASS "
        "verification_registry_identity=PASS "
        "campaign_frontier=PASS chx_public_disclosure=PASS "
        f"skill_lines={skill_line_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

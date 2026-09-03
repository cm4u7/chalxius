from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from mathgraph.cli import build_parser, main as cli_main
from mathgraph.contracts import sha256_bytes, sha256_json
from mathgraph.store import MathGraphStore
from mathgraph.v5_lifecycle import (
    V5_CAMPAIGN_SCOPE_REVISION,
    V5_LEGACY_CAMPAIGN_SCOPE_REVISION,
    RoundInspectionContext,
)


class V5CampaignEnvelopeTests(unittest.TestCase):
    @staticmethod
    def _store(root: Path, project_id: str = "v5-campaign-envelope") -> MathGraphStore:
        store = MathGraphStore(root)
        store.initialize(
            project_id=project_id,
            title="V5 Campaign envelope",
            workflow_evidence_version=5,
        )
        return store

    @staticmethod
    def _campaign(
        store: MathGraphStore,
        label: str,
        *,
        activate: bool = False,
    ) -> str:
        with store.v5_mutation_lock(command="campaign-envelope-fixture"):
            campaign_id = store.campaigns().create(
                {
                    "name": f"Campaign {label}",
                    "objective": f"Resolve bounded objective {label}.",
                    "source_claim_ids": [],
                    "targets": [
                        {
                            "role": "communication",
                            "subject_kind": "report",
                            "subject_id": f"report-{label}",
                            "label": f"Report target {label}",
                        }
                    ],
                    "constraints": [f"Respect constraint {label}."],
                    "stop_conditions": [f"Stop when {label} is resolved."],
                    "value_definition": f"Prefer decisive low-burden work for {label}.",
                },
                actor="main",
                fact_exists=lambda _fact_id: False,
            )
            if activate:
                store.campaigns().activate(campaign_id, actor="main")
        return campaign_id

    @staticmethod
    def _research(
        store: MathGraphStore,
        label: str,
        *,
        campaign_id: str | None,
        score: float,
    ) -> str:
        payload: dict[str, object] = {
            "kind": "direction",
            "claim": f"Investigate branch {label}.",
            "decision_profile": {
                "impact": score,
                "information_value": score,
                "tractability": score,
                "burden": 1.0 - score,
            },
        }
        if campaign_id is not None:
            payload["campaign_id"] = campaign_id
        return store.v5_lifecycle().add_research(payload, actor="main")[
            "research_id"
        ]

    @staticmethod
    def _research_goal(
        store: MathGraphStore,
        campaign_id: str,
        research_id: str,
        label: str,
    ) -> str:
        with store.v5_mutation_lock(command="campaign-goal-fixture"):
            return store.campaigns().target_add(
                campaign_id,
                {
                    "role": "research_goal",
                    "subject_kind": "research",
                    "subject_id": research_id,
                    "label": label,
                },
                actor="main",
                fact_exists=lambda _fact_id: False,
                research_exists=lambda item: item == research_id,
            )

    @staticmethod
    def _goal_coverage_with_actions(
        store: MathGraphStore,
        campaign_id: str,
        actions: dict[str, str],
    ) -> list[dict[str, object]]:
        lifecycle = store.v5_lifecycle()
        bases = {
            item["research_id"]: item
            for item in lifecycle.research_envelopes()
        }
        work_keys = {
            research_id: f"{index:064x}"
            for index, research_id in enumerate(sorted(bases), start=1)
        }
        inspection = RoundInspectionContext(
            frontier_group_completions={
                work_keys[research_id]: (
                    "completed_production"
                    if next_action == "none"
                    else "pending",
                    research_id,
                    1,
                    "0" * 64,
                )
                for research_id, next_action in actions.items()
            },
            frontier_group_actions={
                work_keys[research_id]: {
                    "next_action": next_action,
                    "pending_reason": (
                        "workgroup_completed"
                        if next_action == "none"
                        else "no_ingested_production_product"
                    ),
                    "actionable_research_id": research_id,
                    "actionable_round_id": None,
                    "actionable_research_ids": [research_id],
                }
                for research_id, next_action in actions.items()
            },
        )
        with patch.object(
            lifecycle,
            "_frontier_structural_state_for_inspection",
            return_value=(bases, {}, {}, {}, work_keys),
        ):
            return lifecycle.campaign_goal_coverage(
                campaign_id,
                _inspection_context=inspection,
            )

    def test_worker_result_preserves_campaign_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            campaign_id = self._campaign(store, "worker-lineage")
            with store.v5_mutation_lock(command="large-campaign-history-fixture"):
                for index in range(40):
                    store.campaigns().update(
                        campaign_id,
                        {
                            "type": "note",
                            "payload": {
                                "text": f"historical-note-{index}:" + "x" * 8192
                            },
                        },
                        actor="main",
                    )
            lifecycle = store.v5_lifecycle()
            root_id = self._research(
                store,
                "worker-lineage",
                campaign_id=campaign_id,
                score=0.8,
            )
            planned = lifecycle.create_production_round(
                workers=1,
                research_ids=[root_id],
                campaign_id=campaign_id,
            )
            snapshot_path = (
                store.root
                / planned["campaign_scope"]["snapshot_relpath"]
            )
            frozen_campaign = json.loads(
                snapshot_path.read_text(encoding="utf-8")
            )["campaign_status"]
            self.assertNotIn("updates", frozen_campaign)
            self.assertIn("history", frozen_campaign)
            self.assertLess(len(snapshot_path.read_bytes()), 32 * 1024)
            assignment = planned["assignments"][0]
            card = json.loads(
                Path(str(assignment["task_card_path"])).read_text(
                    encoding="utf-8"
                )
            )
            artifact_dir = store.root / assignment["artifact_dir_relpath"]
            artifact_dir.mkdir(parents=True, exist_ok=True)
            report_path = artifact_dir / "worker-report.md"
            report_path.write_text(
                "One Campaign-scoped result is ready for review.\n",
                encoding="utf-8",
            )
            report = {
                "path": report_path.relative_to(store.root).as_posix(),
                "sha256": sha256_bytes(report_path.read_bytes()),
                "role": "research_report",
            }
            payload = {
                "schema_version": 5,
                "project_id": store.project_id(),
                "round_id": planned["round_id"],
                "assignment_id": assignment["assignment_id"],
                "worker_id": assignment["worker_id"],
                "task_card_sha256": assignment["task_card_sha256"],
                "blackboard_snapshot_sha256": assignment[
                    "blackboard_snapshot_sha256"
                ],
                "outcome": "proof",
                "claim": "The Campaign-scoped worker result is preserved.",
                "content": "This remains nontruth Research.",
                "narrative": {
                    "rationale": "Preserve the exact Campaign lineage.",
                    "summary": "One assignment completed.",
                    "intuition": "The product stays in its selected objective.",
                    "limitations": "No Fact authority is created.",
                },
                "artifacts": [report],
                "obligation_dispositions": [
                    {
                        "obligation_id": obligation["obligation_id"],
                        "status": "complete",
                        "witness_artifact_sha256s": [report["sha256"]],
                        "rationale": "The exact report is hash-bound.",
                    }
                    for obligation in card["assurance_contract"]["obligations"]
                ],
                "computation_manifest": None,
                "research_assurance": {
                    "source_uses": [],
                    "route_invalidations": [],
                    "extremal_cases": [],
                    "claim_strength": [],
                    "contour_substitutions": [],
                    "claimed_structures": [],
                    "program_math_alignments": [],
                },
            }
            return_path = Path(str(assignment["return_path"]))
            return_path.write_text(
                json.dumps(payload, sort_keys=True), encoding="utf-8"
            )
            receipt = lifecycle.ingest_return(
                round_id=planned["round_id"],
                assignment_id=assignment["assignment_id"],
                worker_final_sha256=sha256_bytes(return_path.read_bytes()),
            )
            self.assertEqual(receipt["status"], "ingested", receipt)
            product = next(
                item
                for item in lifecycle.research_records()
                if item["research_id"] == receipt["research_id"]
            )
            self.assertEqual(product["metadata"]["campaign_id"], campaign_id)
            with store.v5_mutation_lock(command="campaign-tail-after-freeze"):
                store.campaigns().update(
                    campaign_id,
                    {"type": "note", "payload": {"text": "new tail event"}},
                    actor="main",
                )
            supervision = lifecycle.create_supervision_round(
                planned["round_id"],
                supervisor_scopes=["proof_logic"],
            )
            self.assertEqual(
                supervision["campaign_scope"]["revision"],
                V5_CAMPAIGN_SCOPE_REVISION,
            )
            self.assertGreater(
                supervision["campaign_scope"]["event_count"],
                planned["campaign_scope"]["event_count"],
            )
            supervision_snapshot = (
                store.root
                / supervision["campaign_scope"]["snapshot_relpath"]
            )
            self.assertLess(len(supervision_snapshot.read_bytes()), 32 * 1024)

    def test_campaign_scope_commits_exact_history_prefix(self) -> None:
        for mutation in ("rewrite", "reorder", "truncate"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                store = self._store(Path(temporary) / "project")
                campaign_id = self._campaign(store, mutation)
                with store.v5_mutation_lock(command="campaign-prefix-fixture"):
                    for index in range(2):
                        store.campaigns().update(
                            campaign_id,
                            {
                                "type": "note",
                                "payload": {"text": f"prefix-note-{index}"},
                            },
                            actor="main",
                        )
                research_id = self._research(
                    store,
                    mutation,
                    campaign_id=campaign_id,
                    score=0.8,
                )
                lifecycle = store.v5_lifecycle()
                planned = lifecycle.create_round(
                    workers=1,
                    research_ids=[research_id],
                    campaign_id=campaign_id,
                )
                ledger_path = (
                    store.root / "campaigns" / campaign_id / "events.jsonl"
                )
                events = [
                    json.loads(line)
                    for line in ledger_path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
                if mutation == "rewrite":
                    rewritten = dict(events[-1])
                    rewritten["payload"] = {"text": "rewritten-prefix-note"}
                    semantic = {
                        key: value
                        for key, value in rewritten.items()
                        if key != "event_id"
                    }
                    rewritten["event_id"] = sha256_json(semantic)
                    events[-1] = rewritten
                elif mutation == "reorder":
                    events[-2], events[-1] = events[-1], events[-2]
                else:
                    events.pop()
                ledger_path.write_text(
                    "".join(
                        json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n"
                        for event in events
                    ),
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(
                    ValueError,
                    "history (?:was truncated|prefix changed)",
                ):
                    lifecycle.round_status(planned["round_id"])

    def test_explicit_frontier_scope_is_exact_and_active_pointer_is_not_implicit(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            campaign_a = self._campaign(store, "a")
            campaign_b = self._campaign(store, "b", activate=True)
            a_high = self._research(
                store, "a-high", campaign_id=campaign_a, score=0.9
            )
            a_low = self._research(
                store, "a-low", campaign_id=campaign_a, score=0.6
            )
            b_high = self._research(
                store, "b-high", campaign_id=campaign_b, score=1.0
            )
            untagged = self._research(
                store, "untagged", campaign_id=None, score=0.95
            )
            self._research_goal(store, campaign_a, a_high, "A high")
            self._research_goal(store, campaign_a, a_low, "A low")
            self._research_goal(store, campaign_b, b_high, "B high")

            lifecycle = store.v5_lifecycle()
            unscoped = lifecycle.frontier(limit=10)
            self.assertEqual(
                {item["research_id"] for item in unscoped},
                {a_high, a_low, b_high, untagged},
            )
            scoped = lifecycle.frontier(limit=10, campaign_id=campaign_a)
            self.assertEqual(
                [item["research_id"] for item in scoped],
                [a_high, a_low],
            )
            scoped_history = lifecycle.frontier(
                limit=10,
                include_history=True,
                campaign_id=campaign_a,
            )
            self.assertEqual(
                [item["research_id"] for item in scoped_history],
                [a_high, a_low],
            )
            self.assertFalse(store.campaigns().status(campaign_a)["active"])
            self.assertTrue(store.campaigns().status(campaign_b)["active"])

    def test_research_goal_tracks_progress_without_becoming_a_scheduler(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            store = self._store(root)
            campaign_id = self._campaign(store, "goal-anchor")
            research_id = self._research(
                store,
                "goal-anchor",
                campaign_id=campaign_id,
                score=0.8,
            )
            with store.v5_mutation_lock(command="campaign-goal-target-fixture"):
                target_id = store.campaigns().target_add(
                    campaign_id,
                    {
                        "role": "research_goal",
                        "subject_kind": "research",
                        "subject_id": research_id,
                        "label": "Resolve the exact goal-anchor branch",
                    },
                    actor="main",
                    fact_exists=lambda _fact_id: False,
                    research_exists=lambda item: item == research_id,
                )
                store.campaigns().activate(campaign_id, actor="main")

            self.assertEqual(
                store.campaigns().derived_targets(campaign_id), []
            )
            surface = store.v5_lifecycle().frontier_decision_surface(
                campaign_id=campaign_id,
                limit=3,
            )
            self.assertEqual(surface["goal_target_count"], 1)
            self.assertEqual(surface["goal_progress"]["research_open"], 1)
            goal = surface["goal_coverage"][0]
            self.assertEqual(goal["target_id"], target_id)
            self.assertEqual(goal["root_research_id"], research_id)
            self.assertEqual(goal["root_claim"], "Investigate branch goal-anchor.")
            self.assertEqual(goal["coverage_status"], "research_open")
            self.assertEqual(goal["action_class"], "research_development")
            self.assertEqual(goal["next_action"], "production")
            self.assertEqual(
                goal["why_now"], "no_ingested_production_product"
            )
            self.assertEqual(goal["actionable_research_id"], research_id)
            self.assertEqual(
                goal["plan_round_argv"],
                [
                    "plan-round",
                    "--workers",
                    "1",
                    "--mode",
                    "auto",
                    "--campaign",
                    campaign_id,
                    "--frontier-target",
                    target_id,
                    "--memory-id",
                    research_id,
                ],
            )
            self.assertNotIn("next_attention", goal)
            self.assertNotIn("attention_basis_research_ids", goal)
            self.assertEqual(
                surface["workflow_queue"][0]["goal_relevance"], "direct"
            )
            self.assertEqual(
                surface["workflow_queue"][0]["goal_target_ids"], [target_id]
            )

            unscoped = store.v5_lifecycle().frontier_decision_surface(limit=3)
            self.assertIsNone(unscoped["campaign_id"])
            self.assertEqual(unscoped["goal_campaign_id"], campaign_id)
            self.assertEqual(unscoped["goal_context_source"], "active_hint")
            self.assertEqual(unscoped["campaign_selection_effect"], "none")
            self.assertEqual(
                unscoped["goal_coverage"][0]["target_id"], target_id
            )

            store.v5_lifecycle()._research_path(research_id).unlink()
            orphaned = store.v5_lifecycle().frontier_decision_surface(limit=3)
            self.assertEqual(orphaned["goal_progress"]["orphaned"], 1)
            self.assertEqual(
                orphaned["goal_coverage"][0]["next_action"],
                "exact_research_search",
            )
            self.assertEqual(orphaned["workflow_queue"], [])

    def test_routine_frontier_limit_bounds_nested_goal_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            campaign_id = self._campaign(store, "bounded-goals")
            roots = [
                self._research(
                    store,
                    f"bounded-goal-{index}",
                    campaign_id=campaign_id,
                    score=0.9 - index / 100,
                )
                for index in range(6)
            ]
            with store.v5_mutation_lock(command="bounded-goal-fixture"):
                target_ids = [
                    store.campaigns().target_add(
                        campaign_id,
                        {
                            "role": "research_goal",
                            "subject_kind": "research",
                            "subject_id": research_id,
                            "label": f"Resolve bounded goal {index}",
                        },
                        actor="main",
                        fact_exists=lambda _fact_id: False,
                        research_exists=lambda item, expected=research_id: (
                            item == expected
                        ),
                    )
                    for index, research_id in enumerate(roots)
                ]
                store.campaigns().activate(campaign_id, actor="main")

            lifecycle = store.v5_lifecycle()
            lifecycle._replace_campaign_frontier_working_state(
                campaign_id,
                targets={
                    target_id: {
                        "recovery_root_research_id": research_id,
                        "active_head_research_ids": [research_id],
                        "historical_landmark_research_ids": [],
                        "recent_attained_research_ids": [],
                    }
                    for target_id, research_id in zip(target_ids, roots)
                },
            )
            with patch.object(
                lifecycle,
                "_campaign_attained_semantic_successor_summary",
                wraps=lifecycle._campaign_attained_semantic_successor_summary,
            ) as routine_successors:
                routine = lifecycle.frontier_decision_surface(
                    campaign_id=campaign_id,
                    limit=2,
                )
            with patch.object(
                lifecycle,
                "_campaign_attained_semantic_successor_summary",
                wraps=lifecycle._campaign_attained_semantic_successor_summary,
            ) as forensic_successors:
                forensic = lifecycle.frontier_decision_surface(
                    campaign_id=campaign_id,
                    limit=2,
                    diagnostic=True,
                )

            self.assertEqual(routine["goal_target_count"], 6)
            self.assertEqual(routine["goal_coverage_count"], 2)
            self.assertEqual(len(routine["goal_coverage"]), 2)
            self.assertTrue(routine["goal_coverage_truncated"])
            self.assertFalse(routine["goal_progress"]["projection_complete"])
            self.assertEqual(
                routine["goal_progress"]["unprojected_target_count"], 4
            )
            self.assertEqual(len(routine["workflow_queue"]), 2)
            self.assertEqual(routine_successors.call_count, 2)
            self.assertNotIn("unmapped_campaign_attention", routine)
            self.assertEqual(
                {item["target_id"] for item in routine["goal_coverage"]},
                set(routine["goal_coverage_target_ids"]),
            )
            self.assertTrue(
                {item["root_research_id"] for item in routine["goal_coverage"]}
                .issubset(set(roots))
            )

            self.assertEqual(forensic["goal_target_count"], 6)
            self.assertEqual(forensic["goal_coverage_count"], 6)
            self.assertEqual(len(forensic["goal_coverage"]), 6)
            self.assertEqual(forensic_successors.call_count, 6)
            self.assertFalse(forensic["goal_coverage_truncated"])
            self.assertTrue(forensic["goal_progress"]["projection_complete"])
            self.assertEqual(
                set(forensic["goal_coverage_target_ids"]), set(target_ids)
            )
            self.assertLess(
                len(json.dumps(routine, sort_keys=True)),
                len(json.dumps(forensic, sort_keys=True)),
            )

    def test_active_goal_hint_does_not_filter_the_global_workflow_queue(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            store = self._store(root)
            active_campaign = self._campaign(store, "active-goal")
            other_campaign = self._campaign(store, "other-work")
            goal_id = self._research(
                store,
                "active-goal",
                campaign_id=active_campaign,
                score=0.7,
            )
            other_id = self._research(
                store,
                "other-work",
                campaign_id=other_campaign,
                score=1.0,
            )
            with store.v5_mutation_lock(command="campaign-goal-hint-fixture"):
                store.campaigns().target_add(
                    active_campaign,
                    {
                        "role": "research_goal",
                        "subject_kind": "research",
                        "subject_id": goal_id,
                        "label": "Keep the active goal visible",
                    },
                    actor="main",
                    fact_exists=lambda _fact_id: False,
                    research_exists=lambda item: item == goal_id,
                )
                store.campaigns().activate(active_campaign, actor="main")

            surface = store.v5_lifecycle().frontier_decision_surface(limit=10)

            self.assertEqual(surface["goal_context_source"], "active_hint")
            self.assertEqual(surface["campaign_selection_effect"], "none")
            self.assertEqual(
                {item["research_id"] for item in surface["workflow_queue"]},
                {goal_id, other_id},
            )

    def test_main_checkpoint_is_the_routine_goal_entry_not_the_old_anchor(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            store = self._store(root)
            campaign_id = self._campaign(store, "checkpoint-heads")
            anchor_id = self._research(
                store,
                "old-anchor",
                campaign_id=campaign_id,
                score=0.9,
            )
            first_head = self._research(
                store,
                "current-head-one",
                campaign_id=campaign_id,
                score=0.8,
            )
            second_head = self._research(
                store,
                "current-head-two",
                campaign_id=campaign_id,
                score=0.7,
            )
            with store.v5_mutation_lock(command="campaign-head-fixture"):
                target_id = store.campaigns().target_add(
                    campaign_id,
                    {
                        "role": "research_goal",
                        "subject_kind": "research",
                        "subject_id": anchor_id,
                        "label": "Keep the semantic anchor but advance its heads",
                    },
                    actor="main",
                    fact_exists=lambda _fact_id: False,
                    research_exists=lambda item: item == anchor_id,
                )
                event_id = store.campaigns().update(
                    campaign_id,
                    {
                        "type": "note",
                        "payload": {
                            "kind": "campaign_frontier_head_checkpoint",
                            "generation": 3,
                            "target_frontiers": [
                                {
                                    "target_id": target_id,
                                    "recovery_root_research_id": anchor_id,
                                    "attained_checkpoints": [
                                        {"research_id": anchor_id}
                                    ],
                                    "active_heads": [
                                        {"research_id": first_head},
                                        {"research_id": second_head},
                                    ],
                                }
                            ],
                        },
                    },
                    actor="Main",
                )

            surface = store.v5_lifecycle().frontier_decision_surface(
                campaign_id=campaign_id,
                limit=10,
            )
            goal = surface["goal_coverage"][0]
            self.assertEqual(goal["root_research_id"], anchor_id)
            self.assertEqual(goal["frontier_source"], "main_checkpoint")
            self.assertEqual(goal["frontier_generation"], 3)
            self.assertEqual(goal["frontier_checkpoint_event_id"], event_id)
            self.assertEqual(goal["recovery_root_research_id"], anchor_id)
            self.assertEqual(
                goal["recovery_root_source"], "explicit_checkpoint_root"
            )
            self.assertEqual(
                goal["active_head_research_ids"],
                [first_head, second_head],
            )
            self.assertEqual(goal["next_action"], "advance_active_heads")
            self.assertEqual(goal["coverage_status"], "research_open")
            self.assertEqual(
                set(goal["actionable_research_ids"]),
                {first_head, second_head},
            )
            relevance = {
                item["research_id"]: item["goal_relevance"]
                for item in surface["workflow_queue"]
            }
            self.assertEqual(relevance[first_head], "direct")
            self.assertEqual(relevance[second_head], "direct")
            self.assertNotIn(anchor_id, relevance)
            self.assertNotIn(
                anchor_id,
                surface["unmapped_campaign_attention"][
                    "visible_research_ids"
                ],
            )
            self.assertEqual(
                surface["unmapped_campaign_attention"][
                    "selection_effect"
                ],
                "none",
            )

            lifecycle = store.v5_lifecycle()
            exact_id_entry = {
                "research_id": anchor_id,
                "claim": "Historical workgroup representative",
                "research_creation_campaign_id": campaign_id,
                "score": 0.9,
                "readiness": 1.0,
                "next_action": "supervision",
                "pending_reason": "current_product_requires_supervision",
                "actionable_research_id": first_head,
                "actionable_round_id": None,
                "actionable_research_ids": [first_head],
                "actionable_research_count": 1,
                "actionable_claim": "Current exact head product",
                "actionable_kind": "insight",
                "workgroup_member_count": 1,
                "work_key_sha256": "f" * 64,
            }
            with patch.object(
                lifecycle,
                "frontier",
                return_value=[exact_id_entry],
            ):
                exact_id_surface = lifecycle.frontier_decision_surface(
                    campaign_id=campaign_id,
                    limit=1,
                )
            self.assertEqual(
                exact_id_surface["workflow_queue"][0]["goal_relevance"],
                "direct",
            )
            self.assertEqual(
                exact_id_surface["workflow_queue"][0]["goal_target_ids"],
                [target_id],
            )

    def test_active_goal_requires_main_disposition_after_heads_complete(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            campaign_id = self._campaign(store, "active-completed-heads")
            labels = (
                "single-anchor",
                "single-head",
                "multi-anchor",
                "multi-head-one",
                "multi-head-two",
                "partial-anchor",
                "partial-complete-head",
                "partial-open-head",
            )
            research_ids = {
                label: self._research(
                    store,
                    label,
                    campaign_id=campaign_id,
                    score=0.8,
                )
                for label in labels
            }
            with store.v5_mutation_lock(command="campaign-head-fixture"):
                single_target = store.campaigns().target_add(
                    campaign_id,
                    {
                        "role": "research_goal",
                        "subject_kind": "research",
                        "subject_id": research_ids["single-anchor"],
                        "label": "Dispose one completed head semantically",
                    },
                    actor="main",
                    fact_exists=lambda _fact_id: False,
                    research_exists=lambda item: item in research_ids.values(),
                )
                multi_target = store.campaigns().target_add(
                    campaign_id,
                    {
                        "role": "research_goal",
                        "subject_kind": "research",
                        "subject_id": research_ids["multi-anchor"],
                        "label": "Dispose several completed heads semantically",
                    },
                    actor="main",
                    fact_exists=lambda _fact_id: False,
                    research_exists=lambda item: item in research_ids.values(),
                )
                partial_target = store.campaigns().target_add(
                    campaign_id,
                    {
                        "role": "research_goal",
                        "subject_kind": "research",
                        "subject_id": research_ids["partial-anchor"],
                        "label": "Keep unfinished heads in progress",
                    },
                    actor="main",
                    fact_exists=lambda _fact_id: False,
                    research_exists=lambda item: item in research_ids.values(),
                )
                store.campaigns().update(
                    campaign_id,
                    {
                        "type": "note",
                        "payload": {
                            "kind": "campaign_frontier_head_checkpoint",
                            "generation": 1,
                            "target_frontiers": [
                                {
                                    "target_id": single_target,
                                    "recovery_root_research_id": research_ids[
                                        "single-anchor"
                                    ],
                                    "attained_checkpoints": [],
                                    "active_heads": [
                                        {
                                            "research_id": research_ids[
                                                "single-head"
                                            ]
                                        }
                                    ],
                                },
                                {
                                    "target_id": multi_target,
                                    "recovery_root_research_id": research_ids[
                                        "multi-anchor"
                                    ],
                                    "attained_checkpoints": [],
                                    "active_heads": [
                                        {
                                            "research_id": research_ids[
                                                "multi-head-one"
                                            ]
                                        },
                                        {
                                            "research_id": research_ids[
                                                "multi-head-two"
                                            ]
                                        },
                                    ],
                                },
                                {
                                    "target_id": partial_target,
                                    "recovery_root_research_id": research_ids[
                                        "partial-anchor"
                                    ],
                                    "attained_checkpoints": [],
                                    "active_heads": [
                                        {
                                            "research_id": research_ids[
                                                "partial-complete-head"
                                            ]
                                        },
                                        {
                                            "research_id": research_ids[
                                                "partial-open-head"
                                            ]
                                        },
                                    ],
                                },
                            ],
                        },
                    },
                    actor="Main",
                )

            actions = {
                research_ids["single-head"]: "none",
                research_ids["multi-head-one"]: "none",
                research_ids["multi-head-two"]: "none",
                research_ids["partial-complete-head"]: "none",
                research_ids["partial-open-head"]: "production",
            }
            coverage = {
                item["target_id"]: item
                for item in self._goal_coverage_with_actions(
                    store,
                    campaign_id,
                    actions,
                )
            }
            for target_id in (single_target, multi_target):
                goal = coverage[target_id]
                self.assertEqual(goal["coverage_status"], "needs_main_choice")
                self.assertEqual(goal["action_class"], "semantic_choice")
                self.assertEqual(goal["next_action"], "main_disposition")
                self.assertEqual(
                    goal["why_now"],
                    "campaign_target_active_after_heads_completed",
                )
                self.assertIsNone(goal["actionable_research_id"])
                self.assertEqual(goal["actionable_research_ids"], [])

            partial = coverage[partial_target]
            self.assertEqual(partial["coverage_status"], "research_open")
            self.assertEqual(partial["next_action"], "advance_active_heads")
            self.assertEqual(
                partial["actionable_research_ids"],
                [research_ids["partial-open-head"]],
            )

            with store.v5_mutation_lock(command="campaign-target-archive"):
                store.campaigns().target_archive(
                    campaign_id,
                    single_target,
                    reason="Main explicitly closes this semantic target.",
                    actor="main",
                )
            after_archive = self._goal_coverage_with_actions(
                store,
                campaign_id,
                actions,
            )
            self.assertNotIn(
                single_target,
                {item["target_id"] for item in after_archive},
            )

    def test_active_goal_without_checkpoint_is_not_closed_by_work_completion(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            campaign_id = self._campaign(store, "active-anchor-completed")
            anchor_id = self._research(
                store,
                "active-anchor-completed",
                campaign_id=campaign_id,
                score=0.8,
            )
            with store.v5_mutation_lock(command="campaign-goal-target-fixture"):
                target_id = store.campaigns().target_add(
                    campaign_id,
                    {
                        "role": "research_goal",
                        "subject_kind": "research",
                        "subject_id": anchor_id,
                        "label": "Require explicit semantic closure",
                    },
                    actor="main",
                    fact_exists=lambda _fact_id: False,
                    research_exists=lambda item: item == anchor_id,
                )

            goal = self._goal_coverage_with_actions(
                store,
                campaign_id,
                {anchor_id: "none"},
            )[0]
            self.assertEqual(goal["target_id"], target_id)
            self.assertEqual(goal["coverage_status"], "needs_main_choice")
            self.assertEqual(goal["action_class"], "semantic_choice")
            self.assertEqual(goal["next_action"], "main_disposition")
            self.assertEqual(
                goal["why_now"],
                "campaign_target_active_after_work_completed",
            )
            self.assertIsNone(goal["actionable_research_id"])

    def test_checkpoint_without_a_live_head_requests_main_selection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            store = self._store(root)
            campaign_id = self._campaign(store, "checkpoint-boundary")
            anchor_id = self._research(
                store,
                "historical-anchor",
                campaign_id=campaign_id,
                score=0.9,
            )
            attained_id = self._research(
                store,
                "attained-boundary",
                campaign_id=campaign_id,
                score=0.8,
            )
            with store.v5_mutation_lock(command="campaign-head-fixture"):
                target_id = store.campaigns().target_add(
                    campaign_id,
                    {
                        "role": "research_goal",
                        "subject_kind": "research",
                        "subject_id": anchor_id,
                        "label": "Choose the next semantic head",
                    },
                    actor="main",
                    fact_exists=lambda _fact_id: False,
                    research_exists=lambda item: item == anchor_id,
                )
                store.campaigns().update(
                    campaign_id,
                    {
                        "type": "note",
                        "payload": {
                            "kind": "campaign_frontier_head_checkpoint",
                            "generation": 1,
                            "target_frontiers": [
                                {
                                    "target_id": target_id,
                                    "recovery_root_research_id": attained_id,
                                    "attained_checkpoints": [
                                        {"research_id": attained_id}
                                    ],
                                    "active_heads": [],
                                }
                            ],
                        },
                    },
                    actor="Main",
                )

            goal = store.v5_lifecycle().frontier_decision_surface(
                campaign_id=campaign_id,
                limit=10,
            )["goal_coverage"][0]
            self.assertEqual(goal["next_action"], "select_frontier_head")
            self.assertEqual(goal["coverage_status"], "needs_main_choice")
            self.assertEqual(goal["recovery_root_research_id"], attained_id)
            self.assertEqual(
                goal["recovery_root_source"], "explicit_checkpoint_root"
            )
            self.assertIsNone(goal["actionable_research_id"])

    def test_stale_checkpoint_head_degrades_to_bounded_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            store = self._store(root)
            campaign_id = self._campaign(store, "checkpoint-recovery")
            anchor_id = self._research(
                store,
                "recovery-anchor",
                campaign_id=campaign_id,
                score=0.9,
            )
            stale_id = "f" * 12
            with store.v5_mutation_lock(command="campaign-head-fixture"):
                target_id = store.campaigns().target_add(
                    campaign_id,
                    {
                        "role": "research_goal",
                        "subject_kind": "research",
                        "subject_id": anchor_id,
                        "label": "Recover an invalid head",
                    },
                    actor="main",
                    fact_exists=lambda _fact_id: False,
                    research_exists=lambda item: item == anchor_id,
                )
                store.campaigns().update(
                    campaign_id,
                    {
                        "type": "note",
                        "payload": {
                            "kind": "campaign_frontier_head_checkpoint",
                            "generation": 1,
                            "target_frontiers": [
                                {
                                    "target_id": target_id,
                                    "attained_checkpoints": [
                                        {"research_id": anchor_id}
                                    ],
                                    "active_heads": [
                                        {"research_id": stale_id}
                                    ],
                                }
                            ],
                        },
                    },
                    actor="Main",
                )

            goal = store.v5_lifecycle().frontier_decision_surface(
                campaign_id=campaign_id,
                limit=10,
            )["goal_coverage"][0]
            self.assertEqual(goal["next_action"], "exact_research_search")
            self.assertEqual(goal["coverage_status"], "needs_main_choice")
            self.assertEqual(goal["invalid_head_research_ids"], [stale_id])
            self.assertEqual(goal["recovery_root_research_id"], anchor_id)
            self.assertEqual(
                goal["recovery_root_source"],
                "immutable_campaign_anchor_fallback",
            )
            self.assertIn(
                "checkpoint_recovery_root_missing",
                goal["checkpoint_diagnostic_codes"],
            )

    def test_creation_campaign_provenance_does_not_define_membership(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            created_under = self._campaign(store, "created-under")
            linked_to = self._campaign(store, "linked-to")
            research_id = self._research(
                store,
                "provenance-only",
                campaign_id=created_under,
                score=0.8,
            )
            lifecycle = store.v5_lifecycle()
            self.assertEqual(
                lifecycle.campaign_membership_projection(created_under)[
                    "member_research_ids"
                ],
                [],
            )
            self._research_goal(
                store,
                linked_to,
                research_id,
                "Reuse the exact old Research",
            )
            self.assertEqual(
                lifecycle.campaign_membership_projection(linked_to)[
                    "members"
                ][0]["roles"],
                ["member", "target"],
            )

    def test_checkpoint_diagnostics_expose_ambiguity_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            store = self._store(root)
            campaign_id = self._campaign(store, "checkpoint-diagnostics")
            other_campaign_id = self._campaign(
                store, "checkpoint-diagnostics-other"
            )
            first_anchor = self._research(
                store,
                "diagnostic-first-anchor",
                campaign_id=campaign_id,
                score=0.9,
            )
            second_anchor = self._research(
                store,
                "diagnostic-second-anchor",
                campaign_id=campaign_id,
                score=0.8,
            )
            cross_campaign_id = self._research(
                store,
                "diagnostic-cross-campaign",
                campaign_id=other_campaign_id,
                score=0.7,
            )
            missing_id = "e" * 12
            with store.v5_mutation_lock(command="campaign-head-fixture"):
                first_target = store.campaigns().target_add(
                    campaign_id,
                    {
                        "role": "research_goal",
                        "subject_kind": "research",
                        "subject_id": first_anchor,
                        "label": "Diagnose the first target",
                    },
                    actor="main",
                    fact_exists=lambda _fact_id: False,
                    research_exists=lambda item: item == first_anchor,
                )
                second_target = store.campaigns().target_add(
                    campaign_id,
                    {
                        "role": "research_goal",
                        "subject_kind": "research",
                        "subject_id": second_anchor,
                        "label": "Diagnose the omitted target",
                    },
                    actor="main",
                    fact_exists=lambda _fact_id: False,
                    research_exists=lambda item: item == second_anchor,
                )
                first_event = store.campaigns().update(
                    campaign_id,
                    {
                        "type": "note",
                        "payload": {
                            "kind": "campaign_frontier_head_checkpoint",
                            "generation": 1,
                            "target_frontiers": [
                                {
                                    "target_id": first_target,
                                    "recovery_root_research_id": first_anchor,
                                    "attained_checkpoints": [],
                                    "active_heads": [],
                                    "main_disposition": "First baseline.",
                                },
                                {
                                    "target_id": second_target,
                                    "recovery_root_research_id": second_anchor,
                                    "attained_checkpoints": [],
                                    "active_heads": [],
                                    "main_disposition": "Second baseline.",
                                },
                            ],
                        },
                    },
                    actor="Main",
                )
                store.campaigns().update(
                    campaign_id,
                    {
                        "type": "note",
                        "payload": {
                            "kind": "campaign_frontier_head_checkpoint",
                            "generation": 3,
                            "supersedes_event_id": "0" * 64,
                            "target_frontiers": [
                                {
                                    "target_id": first_target,
                                    "recovery_root_research_id": (
                                        cross_campaign_id
                                    ),
                                    "attained_checkpoints": [
                                        {"research_id": missing_id},
                                        {"research_id": cross_campaign_id},
                                    ],
                                    "active_heads": [],
                                    "main_disposition": 7,
                                },
                                {
                                    "target_id": first_target,
                                    "recovery_root_research_id": first_anchor,
                                    "attained_checkpoints": [],
                                    "active_heads": [
                                        {"research_id": first_anchor}
                                    ],
                                    "main_disposition": "Duplicate entry.",
                                },
                            ],
                        },
                    },
                    actor="Main",
                )

            before = {
                str(path.relative_to(root)): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }
            surface = store.v5_lifecycle().frontier_decision_surface(
                campaign_id=campaign_id,
                limit=10,
            )
            after = {
                str(path.relative_to(root)): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }
            self.assertEqual(before, after)

            diagnostics = surface["checkpoint_diagnostics"]
            codes = {item["code"] for item in diagnostics}
            self.assertLessEqual(len(diagnostics), 32)
            self.assertTrue(
                {
                    "manual_checkpoint_sequence_mismatch",
                    "checkpoint_supersedes_mismatch",
                    "checkpoint_target_duplicate",
                    "checkpoint_target_missing",
                    "checkpoint_attained_missing",
                    "checkpoint_main_disposition_nontext",
                }.issubset(codes)
            )
            supersedes = next(
                item
                for item in diagnostics
                if item["code"] == "checkpoint_supersedes_mismatch"
            )
            self.assertEqual(supersedes["expected"], first_event)

            goals = {
                item["target_id"]: item for item in surface["goal_coverage"]
            }
            first = goals[first_target]
            self.assertEqual(
                first["recovery_root_research_id"], cross_campaign_id
            )
            self.assertEqual(
                first["recovery_root_source"],
                "explicit_checkpoint_root",
            )
            self.assertEqual(
                first["invalid_attained_checkpoint_research_ids"],
                [missing_id],
            )
            self.assertEqual(first["checkpoint_main_disposition"], "")

            second = goals[second_target]
            self.assertEqual(
                second["frontier_source"], "immutable_anchor_fallback"
            )
            self.assertEqual(
                second["recovery_root_research_id"], second_anchor
            )
            self.assertIn(
                "checkpoint_target_missing",
                second["checkpoint_diagnostic_codes"],
            )

    def test_scoped_round_freezes_lightweight_nontruth_campaign_envelope(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            store = self._store(root)
            campaign_id = self._campaign(store, "frozen")
            research_id = self._research(
                store,
                "frozen",
                campaign_id=campaign_id,
                score=0.8,
            )
            lifecycle = store.v5_lifecycle()
            planned = lifecycle.create_round(
                workers=1,
                research_ids=[research_id],
                campaign_id=campaign_id,
            )

            scope = planned["campaign_scope"]
            self.assertEqual(scope["revision"], V5_CAMPAIGN_SCOPE_REVISION)
            self.assertEqual(scope["campaign_id"], campaign_id)
            self.assertEqual(scope["scheduler"], "v5_main_four_factor_frontier")
            self.assertEqual(scope["truth_effect"], "none")
            self.assertEqual(scope["fact_admission_effect"], "none")
            self.assertFalse(scope["active_at_freeze"])
            self.assertEqual(scope["objective"], "Resolve bounded objective frozen.")
            self.assertEqual(scope["constraints"], ["Respect constraint frozen."])
            self.assertEqual(
                scope["stop_conditions"], ["Stop when frozen is resolved."]
            )
            self.assertEqual(len(scope["active_targets"]), 1)

            snapshot_path = root / scope["snapshot_relpath"]
            self.assertTrue(snapshot_path.is_file())
            self.assertEqual(
                sha256_bytes(snapshot_path.read_bytes()), scope["snapshot_sha256"]
            )
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            self.assertEqual(snapshot["campaign_id"], campaign_id)
            self.assertEqual(
                snapshot["campaign_status"]["event_count"], scope["event_count"]
            )

            card_path = Path(planned["assignments"][0]["task_card_path"])
            card_bytes = card_path.read_bytes()
            card = json.loads(card_bytes)
            self.assertEqual(card["campaign_scope"], scope)
            prompt = Path(planned["assignments"][0]["prompt_path"]).read_text(
                encoding="utf-8"
            )
            self.assertIn("explicitly scoped to the frozen Campaign", prompt)

            with store.v5_mutation_lock(command="campaign-envelope-update"):
                store.campaigns().update(
                    campaign_id,
                    {"type": "note", "payload": {"text": "Future-only note."}},
                    actor="main",
                )
            self.assertGreater(
                store.campaigns().status(campaign_id)["event_count"],
                scope["event_count"],
            )
            lifecycle.validate_task_card(card, expected_path=card_path)
            self.assertEqual(card_path.read_bytes(), card_bytes)
            self.assertEqual(lifecycle.round_status(planned["round_id"])["campaign_scope"], scope)
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = cli_main(
                    [
                        "--root",
                        str(root),
                        "--role",
                        "worker",
                        "campaign-status",
                        campaign_id,
                        "--task-card",
                        str(card_path),
                    ]
                )
            self.assertEqual(code, 0, stderr.getvalue())
            frozen_status = json.loads(stdout.getvalue())
            self.assertEqual(frozen_status["event_count"], scope["event_count"])
            self.assertLess(
                frozen_status["event_count"],
                store.campaigns().status(campaign_id)["event_count"],
            )
            self.assertEqual(store.fact_ids(), [])

    def test_immutable_scope_one_snapshot_remains_readable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            campaign_id = self._campaign(store, "legacy-scope")
            legacy_status = dict(store.campaigns().status(campaign_id))
            legacy_status.pop("history")
            snapshot = {
                "schema_version": 1,
                "revision": V5_LEGACY_CAMPAIGN_SCOPE_REVISION,
                "campaign_id": campaign_id,
                "campaign_status": legacy_status,
                "selection_policy": "explicit_exact_research_campaign_id_match",
                "scheduler": "v5_main_four_factor_frontier",
                "truth_effect": "none",
                "fact_admission_effect": "none",
            }
            scope = store.v5_lifecycle()._campaign_scope_from_snapshot(
                snapshot,
                snapshot_relpath="rounds/round-legacy/context/campaign.snapshot.json",
                snapshot_sha256="0" * 64,
            )
            self.assertEqual(
                scope["revision"],
                V5_LEGACY_CAMPAIGN_SCOPE_REVISION,
            )
            self.assertEqual(scope["campaign_id"], campaign_id)

    def test_cross_campaign_explicit_selection_creates_member_links(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            store = self._store(root)
            campaign_a = self._campaign(store, "a")
            campaign_b = self._campaign(store, "b")
            research_a = self._research(
                store, "a", campaign_id=campaign_a, score=0.8
            )
            research_b = self._research(
                store, "b", campaign_id=campaign_b, score=0.8
            )
            lifecycle = store.v5_lifecycle()
            research_bytes = {
                research_id: lifecycle._research_path(research_id).read_bytes()
                for research_id in (research_a, research_b)
            }
            planned = lifecycle.create_production_round(
                workers=2,
                research_ids=[research_a, research_b],
                campaign_id=campaign_a,
            )
            self.assertEqual(
                planned["campaign_scope"]["selection_policy"],
                "explicit_campaign_overlay_membership",
            )
            receipt = planned["selection_receipt"]
            self.assertEqual(
                receipt["campaign_membership"]["member_research_ids"],
                [research_a, research_b],
            )
            self.assertEqual(
                lifecycle.campaign_membership_projection(campaign_a)[
                    "member_research_ids"
                ],
                sorted([research_a, research_b]),
            )
            self.assertEqual(
                lifecycle.campaign_membership_projection(campaign_b)[
                    "member_research_ids"
                ],
                [],
            )
            self.assertEqual(
                research_bytes,
                {
                    research_id: lifecycle._research_path(
                        research_id
                    ).read_bytes()
                    for research_id in (research_a, research_b)
                },
            )

    def test_repair_inherits_exact_source_campaign_into_round_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            campaign_id = self._campaign(store, "repair-inheritance")
            lifecycle = store.v5_lifecycle()
            bound = self._research(
                store,
                "bound-repair-source",
                campaign_id=campaign_id,
                score=0.8,
            )
            repair = lifecycle.create_repair_round(bound)
            repair_record = lifecycle._research_record(repair["research_id"])
            self.assertEqual(
                repair_record["metadata"]["campaign_id"],
                campaign_id,
            )
            self.assertEqual(repair["campaign_scope"]["campaign_id"], campaign_id)
            repair_card = json.loads(
                Path(repair["assignments"][0]["task_card_path"]).read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                repair_card["campaign_scope"],
                repair["campaign_scope"],
            )

    def test_unbound_repair_does_not_infer_active_campaign(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            self._campaign(store, "active-but-unrelated", activate=True)
            lifecycle = store.v5_lifecycle()
            unbound = self._research(
                store,
                "unbound-repair-source",
                campaign_id=None,
                score=0.7,
            )
            unbound_repair = lifecycle.create_repair_round(unbound)
            unbound_record = lifecycle._research_record(
                unbound_repair["research_id"]
            )
            self.assertNotIn("campaign_id", unbound_record["metadata"])
            self.assertNotIn("campaign_scope", unbound_repair)

    def test_repair_rejects_tampered_source_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            campaign_id = self._campaign(store, "tampered-repair")
            lifecycle = store.v5_lifecycle()
            source_id = self._research(
                store,
                "tampered-repair-source",
                campaign_id=campaign_id,
                score=0.8,
            )
            source_path = (
                store.root / "research" / "entries" / "by-id" / f"{source_id}.json"
            )
            source_path.write_text(
                source_path.read_text(encoding="utf-8").replace(
                    campaign_id,
                    "campaign-000000000000",
                ),
                encoding="utf-8",
            )
            research_before = sorted(
                path.name
                for path in (store.root / "research" / "entries" / "by-id").glob(
                    "*.json"
                )
            )
            rounds_before = sorted(path.name for path in store.rounds_dir.iterdir())
            with self.assertRaises(ValueError):
                lifecycle.create_repair_round(source_id)
            self.assertEqual(
                sorted(
                    path.name
                    for path in (
                        store.root / "research" / "entries" / "by-id"
                    ).glob("*.json")
                ),
                research_before,
            )
            self.assertEqual(
                sorted(path.name for path in store.rounds_dir.iterdir()),
                rounds_before,
            )

    def test_unscoped_round_does_not_infer_membership_from_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            campaign_id = self._campaign(store, "passive")
            research_id = self._research(
                store,
                "passive",
                campaign_id=campaign_id,
                score=0.8,
            )
            planned = store.v5_lifecycle().create_round(
                workers=1,
                research_ids=[research_id],
            )
            card = json.loads(
                Path(planned["assignments"][0]["task_card_path"]).read_text(
                    encoding="utf-8"
                )
            )
            self.assertIsNone(card["campaign_id"])
            self.assertNotIn("campaign_scope", card)
            self.assertNotIn("campaign_scope", planned)
            self.assertEqual(
                store.v5_lifecycle().campaign_membership_projection(
                    campaign_id
                )["member_research_ids"],
                [],
            )
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = cli_main(
                    [
                        "--root",
                        str(store.root),
                        "--role",
                        "worker",
                        "campaign-status",
                        campaign_id,
                        "--task-card",
                        planned["assignments"][0]["task_card_path"],
                    ]
                )
            self.assertNotEqual(code, 0)
            self.assertIn(
                "not authorized by the frozen task card",
                stderr.getvalue(),
            )

    def test_campaign_snapshot_tamper_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            store = self._store(root)
            campaign_id = self._campaign(store, "tamper")
            research_id = self._research(
                store,
                "tamper",
                campaign_id=campaign_id,
                score=0.8,
            )
            lifecycle = store.v5_lifecycle()
            planned = lifecycle.create_round(
                workers=1,
                research_ids=[research_id],
                campaign_id=campaign_id,
            )
            snapshot_path = root / planned["campaign_scope"]["snapshot_relpath"]
            snapshot_path.write_bytes(snapshot_path.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "snapshot bytes/hash mismatch"):
                lifecycle.round_status(planned["round_id"])

    def test_cli_connects_campaign_scope_for_v5(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            store = self._store(root)
            campaign_id = self._campaign(store, "cli")
            research_id = self._research(
                store,
                "cli",
                campaign_id=campaign_id,
                score=0.8,
            )
            self._research_goal(
                store,
                campaign_id,
                research_id,
                "CLI target corridor",
            )

            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = cli_main(
                    [
                        "--root",
                        str(root),
                        "--role",
                        "main",
                        "frontier",
                        "--campaign",
                        campaign_id,
                    ]
                )
            self.assertEqual(code, 0, stderr.getvalue())
            decision_surface = json.loads(stdout.getvalue())
            self.assertEqual(decision_surface["campaign_id"], campaign_id)
            self.assertEqual(
                [
                    item["research_id"]
                    for item in decision_surface["workflow_queue"]
                ],
                [research_id],
            )

            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = cli_main(
                    [
                        "--root",
                        str(root),
                        "--role",
                        "main",
                        "plan-round",
                        "--workers",
                        "1",
                        "--memory-id",
                        research_id,
                        "--campaign",
                        campaign_id,
                    ]
                )
            self.assertEqual(code, 0, stderr.getvalue())
            self.assertEqual(json.loads(stdout.getvalue())["campaign_scope"]["campaign_id"], campaign_id)

    def test_cli_research_goal_is_many_to_many_same_project_link(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            store = self._store(root)
            campaign_id = self._campaign(store, "goal-cli")
            other_campaign_id = self._campaign(store, "other-goal-cli")
            research_id = self._research(
                store,
                "goal-cli",
                campaign_id=campaign_id,
                score=0.8,
            )
            target_path = Path(temporary) / "research-goal-target.json"
            target_path.write_text(
                json.dumps(
                    {
                        "role": "research_goal",
                        "subject_kind": "research",
                        "subject_id": research_id,
                        "label": "Exact CLI research goal",
                    }
                ),
                encoding="utf-8",
            )

            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = cli_main(
                    [
                        "--root",
                        str(root),
                        "--role",
                        "main",
                        "campaign-target-add",
                        campaign_id,
                        "--input",
                        str(target_path),
                        "--actor",
                        "main",
                    ]
                )
            self.assertEqual(code, 0, stderr.getvalue())
            target_id = json.loads(stdout.getvalue())["target_id"]
            self.assertEqual(
                store.campaigns().status(campaign_id)["targets"][target_id][
                    "subject_id"
                ],
                research_id,
            )

            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = cli_main(
                    [
                        "--root",
                        str(root),
                        "--role",
                        "main",
                        "campaign-target-add",
                        other_campaign_id,
                        "--input",
                        str(target_path),
                        "--actor",
                        "main",
                    ]
                )
            self.assertEqual(code, 0, stderr.getvalue())
            other_target_id = json.loads(stdout.getvalue())["target_id"]
            self.assertEqual(
                store.campaigns().status(other_campaign_id)["targets"][
                    other_target_id
                ]["subject_id"],
                research_id,
            )
            self.assertEqual(
                store.v5_lifecycle().campaign_membership_projection(
                    other_campaign_id
                )["members"][0]["roles"],
                ["member", "target"],
            )

    def test_campaign_cli_help_and_update_error_expose_exact_input_contract(self) -> None:
        for command, required_fragments in (
            (
                "campaign-create",
                ("name", "objective", "source_claim_ids", "value_definition"),
            ),
            (
                "campaign-update",
                ("constraint_added", "value_definition_updated", "payload"),
            ),
        ):
            stdout = StringIO()
            with redirect_stdout(stdout), self.assertRaises(SystemExit) as raised:
                build_parser().parse_args([command, "--help"])
            self.assertEqual(raised.exception.code, 0)
            for fragment in required_fragments:
                self.assertIn(fragment, stdout.getvalue())

        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            campaign_id = self._campaign(store, "bad-update")
            with store.v5_mutation_lock(command="campaign-help-error-fixture"):
                with self.assertRaisesRegex(
                    ValueError,
                    "constraint_added.*stop_condition_disposition.*note",
                ):
                    store.campaigns().update(
                        campaign_id,
                        {"type": "unknown", "payload": {}},
                        actor="main",
                    )


if __name__ == "__main__":
    unittest.main()

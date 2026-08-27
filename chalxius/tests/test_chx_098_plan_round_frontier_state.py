from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mathgraph.store import MathGraphStore


class PlanRoundFrontierStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "project"
        self.store = MathGraphStore(self.root)
        self.store.initialize(
            project_id="plan-round-frontier-state",
            title="Plan round frontier state",
            workflow_evidence_version=5,
        )
        with self.store.v5_mutation_lock(command="frontier-state-fixture"):
            self.campaign_id = self.store.campaigns().create(
                {
                    "name": "Frontier memory",
                    "objective": "Keep the mathematical boundary current.",
                    "source_claim_ids": [],
                    "targets": [],
                    "constraints": [],
                    "stop_conditions": [],
                    "value_definition": "Prefer decisive nonduplicate work.",
                },
                actor="main",
                fact_exists=lambda _fact_id: False,
            )
        self.root_id = self._research("root", "Original mathematical question")
        self.landmark_id = self._research(
            "landmark", "Ancient change of mechanism"
        )
        self.successor_id = self._research(
            "successor", "Current sharper boundary"
        )
        with self.store.v5_mutation_lock(command="frontier-state-fixture"):
            self.target_id = self.store.campaigns().target_add(
                self.campaign_id,
                {
                    "role": "research_goal",
                    "subject_kind": "research",
                    "subject_id": self.root_id,
                    "label": "Resolve the exact mathematical bridge",
                },
                actor="main",
                fact_exists=lambda _fact_id: False,
                research_exists=lambda item: item == self.root_id,
            )
            self.store.campaigns().activate(self.campaign_id, actor="main")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _research(
        self,
        label: str,
        content: str,
        *,
        relation: str | None = None,
        related_research_ids: list[str] | None = None,
    ) -> str:
        payload = {
            "kind": "direction",
            "campaign_id": self.campaign_id,
            "claim": f"Claim {label}",
            "content": content,
            "rationale": f"Rationale {label}",
            "decision_profile": {
                "impact": 0.8,
                "information_value": 0.8,
                "tractability": 0.7,
                "burden": 0.2,
            },
        }
        if relation is not None:
            payload["relation"] = relation
            payload["related_research_ids"] = related_research_ids or []
        return self.store.v5_lifecycle().add_research(
            payload,
            actor="main",
        )["research_id"]

    def _state(self) -> dict:
        path = (
            self.root
            / "campaigns"
            / self.campaign_id
            / "frontier-state.json"
        )
        return json.loads(path.read_text(encoding="utf-8"))

    def test_plan_round_atomically_selects_target_without_checkpoint_copy(self) -> None:
        lifecycle = self.store.v5_lifecycle()
        with self.store.v5_mutation_lock(command="legacy-frontier-fixture"):
            self.store.campaigns().update(
                self.campaign_id,
                {
                    "type": "note",
                    "payload": {
                        "kind": "campaign_frontier_head_checkpoint",
                        "generation": 1,
                        "supersedes_event_id": None,
                        "target_frontiers": [
                            {
                                "target_id": self.target_id,
                                "recovery_root_research_id": self.root_id,
                                "active_heads": [
                                    {"research_id": self.root_id}
                                ],
                                "attained_checkpoints": [
                                    {"research_id": self.landmark_id}
                                ],
                            }
                        ],
                    },
                },
                actor="main",
            )
        event_count = self.store.campaigns().status(self.campaign_id)[
            "history"
        ]["event_count"]
        planned = lifecycle.create_production_round(
            workers=1,
            research_ids=[self.root_id],
            campaign_id=self.campaign_id,
            frontier_target_id=self.target_id,
        )
        state = self._state()
        self.assertEqual(set(state["targets"]), {self.target_id})
        row = state["targets"][self.target_id]
        self.assertNotIn("target_id", row)
        self.assertEqual(row["active_head_research_ids"], [self.root_id])
        self.assertEqual(
            row["historical_landmark_research_ids"], [self.landmark_id]
        )
        self.assertEqual(
            self.store.campaigns().status(self.campaign_id)["history"][
                "event_count"
            ],
            event_count,
        )
        receipt = planned["selection_receipt"]
        self.assertEqual(receipt["frontier_target_id"], self.target_id)
        self.assertIn("--frontier-target", receipt["exact_replay_argv"])
        goal = lifecycle.frontier_decision_surface(
            campaign_id=self.campaign_id,
            limit=2,
        )["goal_coverage"][0]
        self.assertEqual(goal["frontier_source"], "working_state")
        self.assertEqual(goal["coverage_status"], "in_flight")
        self.assertEqual(goal["next_action"], "await_return")
        self.assertEqual(goal["actionable_round_id"], planned["round_id"])
        self.assertEqual(
            goal["historical_mathematical_summary"][0]["claim"],
            "Claim landmark",
        )
        self.assertTrue(self.store.audit().current_ok)

    def test_auxiliary_round_does_not_claim_a_frontier_target(self) -> None:
        planned = self.store.v5_lifecycle().create_production_round(
            workers=1,
            research_ids=[self.root_id],
            campaign_id=self.campaign_id,
        )
        self.assertIsNone(planned["selection_receipt"]["frontier_target_id"])
        self.assertFalse(
            (
                self.root
                / "campaigns"
                / self.campaign_id
                / "frontier-state.json"
            ).exists()
        )

    def test_invalid_repair_target_fails_before_creating_research(self) -> None:
        lifecycle = self.store.v5_lifecycle()
        before = sorted(lifecycle.research_entries_dir.glob("*.json"))
        with self.assertRaisesRegex(
            ValueError,
            "active Campaign research goal",
        ):
            lifecycle.create_repair_round(
                self.root_id,
                frontier_target_id="camtarget-0000000000000000",
            )
        self.assertEqual(
            sorted(lifecycle.research_entries_dir.glob("*.json")),
            before,
        )
        self.assertFalse(
            (
                self.root
                / "campaigns"
                / self.campaign_id
                / "frontier-state.json"
            ).exists()
        )

    def test_recent_progress_prompts_main_and_curation_preserves_ancient_history(self) -> None:
        lifecycle = self.store.v5_lifecycle()
        lifecycle._replace_campaign_frontier_working_state(
            self.campaign_id,
            targets={
                self.target_id: {
                    "recovery_root_research_id": self.root_id,
                    "active_head_research_ids": [self.root_id],
                    "historical_landmark_research_ids": [],
                    "recent_attained_research_ids": [self.landmark_id],
                }
            },
        )
        goal = lifecycle.campaign_goal_coverage(self.campaign_id)[0]
        self.assertTrue(goal["history_review_recommended"])
        self.assertIn(
            "historical_landmarks_empty", goal["history_review_reasons"]
        )
        events_before = self.store.campaigns().status(self.campaign_id)[
            "history"
        ]["event_count"]
        result = lifecycle.reconcile_campaign_frontier(
            self.campaign_id,
            {
                "kind": "campaign_frontier_update",
                "target_id": self.target_id,
                "historical_landmark_research_ids": [self.landmark_id],
                "recent_attained_research_ids": [],
            },
        )
        self.assertEqual(result["truth_effect"], "none")
        self.assertEqual(
            self.store.campaigns().status(self.campaign_id)["history"][
                "event_count"
            ],
            events_before,
        )
        goal = lifecycle.campaign_goal_coverage(self.campaign_id)[0]
        self.assertFalse(goal["history_review_recommended"])
        self.assertEqual(
            goal["historical_landmark_research_ids"], [self.landmark_id]
        )

    def test_exact_successor_retires_only_its_old_head(self) -> None:
        lifecycle = self.store.v5_lifecycle()
        lifecycle._replace_campaign_frontier_working_state(
            self.campaign_id,
            targets={
                self.target_id: {
                    "recovery_root_research_id": self.root_id,
                    "active_head_research_ids": [self.root_id],
                    "historical_landmark_research_ids": [self.landmark_id],
                    "recent_attained_research_ids": [],
                }
            },
        )
        projected = {
            "target_id": self.target_id,
            "active_head_actions": [
                {
                    "research_id": self.root_id,
                    "current_route_research_ids": [self.successor_id],
                    "actionable_research_id": self.successor_id,
                    "next_action": "production",
                }
            ],
        }
        with patch.object(
            lifecycle,
            "campaign_goal_coverage",
            return_value=[projected],
        ):
            lifecycle._advance_campaign_frontier_for_plan(
                campaign_id=self.campaign_id,
                frontier_target_id=self.target_id,
                selected_research_ids=[self.successor_id],
            )
        row = self._state()["targets"][self.target_id]
        self.assertEqual(
            row["active_head_research_ids"], [self.successor_id]
        )
        self.assertEqual(row["recent_attained_research_ids"], [self.root_id])
        self.assertEqual(
            row["historical_landmark_research_ids"], [self.landmark_id]
        )

    def test_repair_of_current_terminal_retires_stored_route_head(self) -> None:
        lifecycle = self.store.v5_lifecycle()
        lifecycle._replace_campaign_frontier_working_state(
            self.campaign_id,
            targets={
                self.target_id: {
                    "recovery_root_research_id": self.root_id,
                    "active_head_research_ids": [self.root_id],
                    "historical_landmark_research_ids": [],
                    "recent_attained_research_ids": [],
                }
            },
        )
        projected = {
            "target_id": self.target_id,
            "active_head_actions": [
                {
                    "research_id": self.root_id,
                    "current_route_research_ids": [self.successor_id],
                    "actionable_research_id": self.successor_id,
                    "next_action": "repair",
                }
            ],
        }
        selected_repair = self.landmark_id
        repair_record = {
            "research_id": selected_repair,
            "relation": "repairs",
            "metadata": {"repair_of_research_id": self.successor_id},
        }
        with (
            patch.object(
                lifecycle,
                "campaign_goal_coverage",
                return_value=[projected],
            ),
            patch.object(
                lifecycle,
                "_research_record",
                return_value=repair_record,
            ),
        ):
            lifecycle._advance_campaign_frontier_for_plan(
                campaign_id=self.campaign_id,
                frontier_target_id=self.target_id,
                selected_research_ids=[selected_repair],
            )
        row = self._state()["targets"][self.target_id]
        self.assertEqual(
            row["active_head_research_ids"], [selected_repair]
        )
        self.assertEqual(row["recent_attained_research_ids"], [self.root_id])

    def test_positive_successor_retires_reviewing_predecessor_route(self) -> None:
        lifecycle = self.store.v5_lifecycle()
        product_id = self._research(
            "product",
            "Completed product still under independent supervision",
            relation="extends",
            related_research_ids=[self.root_id],
        )
        next_id = self._research(
            "next",
            "Main-selected theorem-sized continuation",
            relation="extends",
            related_research_ids=[product_id],
        )
        lifecycle._replace_campaign_frontier_working_state(
            self.campaign_id,
            targets={
                self.target_id: {
                    "recovery_root_research_id": self.root_id,
                    "active_head_research_ids": [self.root_id],
                    "historical_landmark_research_ids": [],
                    "recent_attained_research_ids": [],
                }
            },
        )
        projected = {
            "target_id": self.target_id,
            "active_head_actions": [
                {
                    "research_id": self.root_id,
                    "current_route_research_ids": [
                        self.root_id,
                        product_id,
                    ],
                    "actionable_research_id": product_id,
                    "next_action": "await_return",
                }
            ],
        }
        with patch.object(
            lifecycle,
            "campaign_goal_coverage",
            return_value=[projected],
        ):
            lifecycle._advance_campaign_frontier_for_plan(
                campaign_id=self.campaign_id,
                frontier_target_id=self.target_id,
                selected_research_ids=[next_id],
            )
        row = self._state()["targets"][self.target_id]
        self.assertEqual(row["active_head_research_ids"], [next_id])
        self.assertEqual(row["recent_attained_research_ids"], [self.root_id])

    def test_too_many_ancient_landmarks_raise_only_an_advisory(self) -> None:
        lifecycle = self.store.v5_lifecycle()
        landmarks = [self.landmark_id]
        landmarks.extend(
            self._research(f"ancient-{index}", f"Ancient turn {index}")
            for index in range(4)
        )
        lifecycle._replace_campaign_frontier_working_state(
            self.campaign_id,
            targets={
                self.target_id: {
                    "recovery_root_research_id": self.root_id,
                    "active_head_research_ids": [self.root_id],
                    "historical_landmark_research_ids": landmarks,
                    "recent_attained_research_ids": [],
                }
            },
        )
        goal = lifecycle.campaign_goal_coverage(self.campaign_id)[0]
        self.assertTrue(goal["history_review_recommended"])
        self.assertEqual(
            goal["history_review_reasons"],
            ["historical_landmarks_need_main_curation"],
        )
        self.assertEqual(goal["next_action"], "production")

    def test_working_state_never_requests_a_legacy_checkpoint_copy(self) -> None:
        lifecycle = self.store.v5_lifecycle()
        lifecycle._replace_campaign_frontier_working_state(
            self.campaign_id,
            targets={
                self.target_id: {
                    "recovery_root_research_id": self.root_id,
                    "active_head_research_ids": [self.root_id],
                    "historical_landmark_research_ids": [self.landmark_id],
                    "recent_attained_research_ids": [],
                }
            },
        )
        surface = lifecycle.frontier_decision_surface(
            campaign_id=self.campaign_id,
            limit=2,
        )
        goal = surface["goal_coverage"][0]
        self.assertFalse(goal["checkpoint_refresh_recommended"])
        self.assertEqual(goal["checkpoint_refresh_reasons"], [])
        self.assertFalse(surface["checkpoint_refresh"]["recommended"])
        self.assertNotIn(
            "write one new advisory checkpoint",
            surface["checkpoint_refresh"]["instruction"],
        )
        self.assertNotIn("checkpoint", surface["main_selection_policy"])

    def test_malformed_work_memory_falls_back_and_main_can_rebuild_it(self) -> None:
        state_path = (
            self.root
            / "campaigns"
            / self.campaign_id
            / "frontier-state.json"
        )
        state_path.write_text('{"revision":"broken"}\n', encoding="utf-8")
        lifecycle = self.store.v5_lifecycle()
        surface = lifecycle.frontier_decision_surface(
            campaign_id=self.campaign_id,
            limit=2,
        )
        self.assertEqual(
            surface["checkpoint_diagnostics"][0]["code"],
            "frontier_working_state_invalid",
        )
        lifecycle.reconcile_campaign_frontier(
            self.campaign_id,
            {
                "kind": "campaign_frontier_update",
                "target_id": self.target_id,
                "active_head_research_ids": [self.root_id],
            },
        )
        self.assertEqual(self._state()["generation"], 1)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from mathgraph.cli import main as cli_main
from mathgraph.contracts import sha256_json
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

    def test_context_storage_has_no_count_limit_and_routine_view_stays_bounded(
        self,
    ) -> None:
        lifecycle = self.store.v5_lifecycle()
        context_ids = [
            self._research(
                f"context-{index:02d}",
                f"Material historical input {index:02d}",
            )
            for index in range(40)
        ]
        lifecycle._replace_campaign_frontier_working_state(
            self.campaign_id,
            targets={
                self.target_id: {
                    "recovery_root_research_id": self.root_id,
                    "active_head_research_ids": [self.root_id],
                    "historical_landmark_research_ids": [],
                    "recent_attained_research_ids": [],
                    "head_contexts": [],
                }
            },
        )
        lifecycle.reconcile_campaign_frontier(
            self.campaign_id,
            {
                "kind": "campaign_frontier_update",
                "target_id": self.target_id,
                "attention_updates": [
                    {
                        "operation": "attach_context",
                        "research_id": research_id,
                        "attached_head_research_id": self.root_id,
                        "reason": f"Exact material context {index:02d}.",
                    }
                    for index, research_id in enumerate(context_ids)
                ],
            },
        )
        self.assertEqual(
            len(
                self._state()["targets"][self.target_id][
                    "head_contexts"
                ]
            ),
            40,
        )
        routine = lifecycle.frontier_decision_surface(
            campaign_id=self.campaign_id,
            limit=2,
        )["goal_coverage"][0]
        self.assertEqual(routine["head_context_count"], 40)
        self.assertEqual(len(routine["head_contexts"]), 4)
        self.assertTrue(routine["head_contexts_truncated"])
        diagnostic = lifecycle.frontier_decision_surface(
            campaign_id=self.campaign_id,
            limit=2,
            diagnostic=True,
        )["goal_coverage"][0]
        self.assertEqual(len(diagnostic["head_contexts"]), 40)
        self.assertFalse(diagnostic["head_contexts_truncated"])
        lifecycle.reconcile_campaign_frontier(
            self.campaign_id,
            {
                "kind": "campaign_frontier_update",
                "target_id": self.target_id,
                "attention_updates": [
                    {
                        "operation": "remove_context",
                        "research_id": research_id,
                    }
                    for research_id in context_ids[:35]
                ],
            },
        )
        self.assertEqual(
            len(
                self._state()["targets"][self.target_id][
                    "head_contexts"
                ]
            ),
            5,
        )

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
            event_count + 1,
        )
        self.assertEqual(
            self.store.campaigns().status(self.campaign_id)["updates"][-1][
                "payload"
            ]["kind"],
            "campaign_research_membership_link",
        )
        receipt = planned["selection_receipt"]
        self.assertEqual(receipt["frontier_target_id"], self.target_id)
        self.assertIn("--frontier-target", receipt["exact_replay_argv"])
        goal = lifecycle.frontier_decision_surface(
            campaign_id=self.campaign_id,
            limit=2,
        )["goal_coverage"][0]
        self.assertNotIn("frontier_source", goal)
        self.assertEqual(goal["coverage_status"], "in_flight")
        self.assertEqual(goal["next_action"], "await_return")
        self.assertEqual(goal["actionable_round_id"], planned["round_id"])
        self.assertEqual(
            goal["historical_landmarks"][0]["mathematical_summary"]["claim"],
            "Claim landmark",
        )
        self.assertTrue(self.store.audit().current_ok)

    def test_full_head_list_preserves_omitted_cohead_until_explicit_retirement(
        self,
    ) -> None:
        lifecycle = self.store.v5_lifecycle()
        lifecycle._replace_campaign_frontier_working_state(
            self.campaign_id,
            targets={
                self.target_id: {
                    "recovery_root_research_id": self.root_id,
                    "active_head_research_ids": [
                        self.root_id,
                        self.successor_id,
                    ],
                    "historical_landmark_research_ids": [],
                    "recent_attained_research_ids": [],
                    "head_contexts": [
                        {
                            "research_id": self.landmark_id,
                            "attached_head_research_id": self.successor_id,
                            "reason": "Keep the independent inequality visible.",
                        }
                    ],
                }
            },
        )
        additive = lifecycle.reconcile_campaign_frontier(
            self.campaign_id,
            {
                "kind": "campaign_frontier_update",
                "target_id": self.target_id,
                "active_head_research_ids": [self.root_id],
            },
        )
        row = self._state()["targets"][self.target_id]
        self.assertEqual(
            row["active_head_research_ids"],
            [self.root_id, self.successor_id],
        )
        self.assertEqual(
            additive["attention_diff"]["warnings"][0]["code"],
            "omitted_active_heads_preserved",
        )

        retired = lifecycle.reconcile_campaign_frontier(
            self.campaign_id,
            {
                "kind": "campaign_frontier_update",
                "target_id": self.target_id,
                "attention_updates": [
                    {
                        "operation": "retire_active_head",
                        "research_id": self.successor_id,
                        "disposition": "dormant",
                    }
                ],
            },
        )
        row = self._state()["targets"][self.target_id]
        self.assertEqual(row["active_head_research_ids"], [self.root_id])
        self.assertIn(self.successor_id, row["recent_attained_research_ids"])
        self.assertIsNone(row["head_contexts"][0]["attached_head_research_id"])
        self.assertEqual(
            retired["attention_diff"]["retirements"],
            [
                {
                    "research_id": self.successor_id,
                    "disposition": "dormant",
                }
            ],
        )
        self.assertEqual(retired["truth_effect"], "none")

    def test_sixteen_heads_survive_checkpoint_reconcile_and_plan_projection(
        self,
    ) -> None:
        lifecycle = self.store.v5_lifecycle()
        heads = [
            self._research(
                f"head-{index}",
                f"Independent mathematical branch {index}",
            )
            for index in range(16)
        ]
        with self.store.v5_mutation_lock(command="sixteen-head-checkpoint"):
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
                                    {"research_id": research_id}
                                    for research_id in heads
                                ],
                                "attained_checkpoints": [],
                            }
                        ],
                    },
                },
                actor="main",
            )

        legacy_goal = lifecycle.frontier_decision_surface(
            campaign_id=self.campaign_id,
            limit=1,
        )["goal_coverage"][0]
        self.assertEqual(legacy_goal["active_head_research_ids"], heads)
        self.assertEqual(len(legacy_goal["active_head_actions"]), 16)

        lifecycle.reconcile_campaign_frontier(
            self.campaign_id,
            {
                "kind": "campaign_frontier_update",
                "target_id": self.target_id,
                "active_head_research_ids": heads,
            },
        )
        self.assertEqual(
            self._state()["targets"][self.target_id][
                "active_head_research_ids"
            ],
            heads,
        )

        advanced = lifecycle._advance_campaign_frontier_for_plan(
            campaign_id=self.campaign_id,
            frontier_target_id=self.target_id,
            selected_research_ids=heads,
        )
        self.assertEqual(
            advanced["targets"][self.target_id]["active_head_research_ids"],
            heads,
        )
        current_goal = lifecycle.frontier_decision_surface(
            campaign_id=self.campaign_id,
            limit=1,
        )["goal_coverage"][0]
        self.assertEqual(current_goal["active_head_research_ids"], heads)
        self.assertEqual(len(current_goal["active_head_actions"]), 16)

        seventeenth = self._research(
            "head-16", "Seventeenth independent mathematical branch"
        )
        with self.assertRaisesRegex(ValueError, "at most 16 ids"):
            lifecycle.reconcile_campaign_frontier(
                self.campaign_id,
                {
                    "kind": "campaign_frontier_update",
                    "target_id": self.target_id,
                    "active_head_research_ids": [*heads, seventeenth],
                },
            )

    def test_seventeen_checkpoint_heads_require_main_choice_without_truncation(
        self,
    ) -> None:
        lifecycle = self.store.v5_lifecycle()
        heads = [
            self._research(
                f"over-capacity-head-{index}",
                f"Independent branch {index}",
            )
            for index in range(17)
        ]
        with self.store.v5_mutation_lock(command="seventeen-head-checkpoint"):
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
                                    {"research_id": research_id}
                                    for research_id in heads
                                ],
                                "attained_checkpoints": [],
                            }
                        ],
                    },
                },
                actor="main",
            )
        surface = lifecycle.frontier_decision_surface(
            campaign_id=self.campaign_id,
            limit=1,
        )
        self.assertIn(
            "checkpoint_research_list_over_capacity",
            surface["goal_coverage"][0]["checkpoint_diagnostic_codes"],
        )
        with self.assertRaisesRegex(ValueError, "exceeds frontier capacity"):
            lifecycle.create_production_round(
                workers=1,
                research_ids=[heads[0]],
                campaign_id=self.campaign_id,
                frontier_target_id=self.target_id,
            )
        self.assertFalse(
            (
                self.root
                / "campaigns"
                / self.campaign_id
                / "frontier-state.json"
            ).exists()
        )

    def test_historical_checkpoint_imports_all_attained_landmarks(
        self,
    ) -> None:
        lifecycle = self.store.v5_lifecycle()
        attained = [
            self._research(
                f"attained-{index}",
                f"Completed mathematical milestone {index}",
            )
            for index in range(9)
        ]
        with self.store.v5_mutation_lock(command="nine-attained-checkpoint"):
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
                                    {"research_id": research_id}
                                    for research_id in attained
                                ],
                            }
                        ],
                    },
                },
                actor="main",
            )
        goal = lifecycle.campaign_goal_coverage(self.campaign_id)[0]
        self.assertEqual(goal["historical_landmark_research_ids"], attained)
        self.assertEqual(goal["historical_landmark_count"], len(attained))
        self.assertEqual(
            goal["historical_landmark_ids_sha256"], sha256_json(attained)
        )
        self.assertEqual(goal["unpartitioned_attained_research_ids"], [])
        self.assertNotIn(
            "checkpoint_attained_requires_frontier_partition",
            goal["checkpoint_diagnostic_codes"],
        )
        lifecycle.reconcile_campaign_frontier(
            self.campaign_id,
            {
                "kind": "campaign_frontier_update",
                "target_id": self.target_id,
                "recovery_root_research_id": self.root_id,
                "active_head_research_ids": [self.root_id],
                "historical_landmark_research_ids": attained,
                "historical_landmark_reasons": {
                    research_id: "Explicitly retained mathematical landmark."
                    for research_id in attained
                },
                "recent_attained_research_ids": [],
                "head_contexts": [],
            },
        )
        row = self._state()["targets"][self.target_id]
        self.assertEqual(
            row["historical_landmark_research_ids"], attained
        )
        self.assertEqual(row["recent_attained_research_ids"], [])

    def test_duplicate_checkpoint_target_requires_complete_main_reconcile(
        self,
    ) -> None:
        lifecycle = self.store.v5_lifecycle()
        with self.store.v5_mutation_lock(command="duplicate-target-checkpoint"):
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
                                "attained_checkpoints": [],
                            },
                            {
                                "target_id": self.target_id,
                                "recovery_root_research_id": self.root_id,
                                "active_heads": [
                                    {"research_id": self.successor_id}
                                ],
                                "attained_checkpoints": [],
                            },
                        ],
                    },
                },
                actor="main",
            )
        goal = lifecycle.frontier_decision_surface(
            campaign_id=self.campaign_id,
            limit=1,
        )["goal_coverage"][0]
        self.assertIn(
            "checkpoint_target_duplicate",
            goal["checkpoint_diagnostic_codes"],
        )
        with self.assertRaisesRegex(ValueError, "exceeds frontier capacity"):
            lifecycle.create_production_round(
                workers=1,
                research_ids=[self.root_id],
                campaign_id=self.campaign_id,
                frontier_target_id=self.target_id,
            )
        lifecycle.reconcile_campaign_frontier(
            self.campaign_id,
            {
                "kind": "campaign_frontier_update",
                "target_id": self.target_id,
                "recovery_root_research_id": self.root_id,
                "active_head_research_ids": [self.successor_id],
                "historical_landmark_research_ids": [],
                "historical_landmark_reasons": {},
                "recent_attained_research_ids": [],
                "head_contexts": [],
            },
        )
        self.assertEqual(
            self._state()["targets"][self.target_id][
                "active_head_research_ids"
            ],
            [self.successor_id],
        )

    def test_truncated_checkpoint_target_list_cannot_hide_omitted_goal(
        self,
    ) -> None:
        lifecycle = self.store.v5_lifecycle()
        target_rows = [
            {
                "target_id": self.target_id,
                "recovery_root_research_id": self.root_id,
                "active_heads": [{"research_id": self.root_id}],
                "attained_checkpoints": [],
            }
        ]
        omitted_target_id = ""
        omitted_root_id = ""
        for index in range(64):
            research_id = self._research(
                f"many-target-{index}",
                f"Independent target branch {index}",
            )
            with self.store.v5_mutation_lock(command="many-target-fixture"):
                target_id = self.store.campaigns().target_add(
                    self.campaign_id,
                    {
                        "role": "research_goal",
                        "subject_kind": "research",
                        "subject_id": research_id,
                        "label": f"Resolve branch {index}",
                    },
                    actor="main",
                    fact_exists=lambda _fact_id: False,
                    research_exists=lambda item, expected=research_id: (
                        item == expected
                    ),
                )
            target_rows.append(
                {
                    "target_id": target_id,
                    "recovery_root_research_id": research_id,
                    "active_heads": [{"research_id": research_id}],
                    "attained_checkpoints": (
                        [{"research_id": self.landmark_id}]
                        if index == 63
                        else []
                    ),
                }
            )
            if index == 63:
                omitted_target_id = target_id
                omitted_root_id = research_id
        with self.store.v5_mutation_lock(command="many-target-checkpoint"):
            self.store.campaigns().update(
                self.campaign_id,
                {
                    "type": "note",
                    "payload": {
                        "kind": "campaign_frontier_head_checkpoint",
                        "generation": 1,
                        "supersedes_event_id": None,
                        "target_frontiers": target_rows,
                    },
                },
                actor="main",
            )
        goals = lifecycle.campaign_goal_coverage(self.campaign_id)
        omitted_goal = next(
            item for item in goals if item["target_id"] == omitted_target_id
        )
        self.assertIn(
            "checkpoint_target_list_truncated",
            omitted_goal["checkpoint_diagnostic_codes"],
        )
        self.assertIn(
            "checkpoint_target_missing",
            omitted_goal["checkpoint_diagnostic_codes"],
        )
        with self.assertRaisesRegex(ValueError, "exceeds frontier capacity"):
            lifecycle.create_production_round(
                workers=1,
                research_ids=[omitted_root_id],
                campaign_id=self.campaign_id,
                frontier_target_id=omitted_target_id,
            )
        lifecycle.reconcile_campaign_frontier(
            self.campaign_id,
            {
                "kind": "campaign_frontier_update",
                "target_id": omitted_target_id,
                "recovery_root_research_id": omitted_root_id,
                "active_head_research_ids": [omitted_root_id],
                "historical_landmark_research_ids": [self.landmark_id],
                "historical_landmark_reasons": {
                    self.landmark_id: "Explicitly restored omitted history."
                },
                "recent_attained_research_ids": [],
                "head_contexts": [],
            },
        )
        state = self._state()
        self.assertEqual(len(state["targets"]), 65)
        self.assertEqual(
            state["targets"][omitted_target_id][
                "historical_landmark_research_ids"
            ],
            [self.landmark_id],
        )

    def test_missing_checkpoint_head_cannot_fail_open_to_root(self) -> None:
        lifecycle = self.store.v5_lifecycle()
        missing_id = "e" * 12
        with self.store.v5_mutation_lock(command="missing-head-checkpoint"):
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
                                    {"research_id": missing_id}
                                ],
                                "attained_checkpoints": [],
                            }
                        ],
                    },
                },
                actor="main",
            )
        goal = lifecycle.campaign_goal_coverage(self.campaign_id)[0]
        self.assertIn(
            "checkpoint_active_head_missing",
            goal["checkpoint_diagnostic_codes"],
        )
        rounds_before = set(self.store.rounds_dir.glob("round-*"))
        with self.assertRaisesRegex(ValueError, "explicit Main reconciliation"):
            lifecycle.create_production_round(
                workers=1,
                research_ids=[self.root_id],
                campaign_id=self.campaign_id,
                frontier_target_id=self.target_id,
            )
        self.assertEqual(
            set(self.store.rounds_dir.glob("round-*")), rounds_before
        )
        lifecycle.reconcile_campaign_frontier(
            self.campaign_id,
            {
                "kind": "campaign_frontier_update",
                "target_id": self.target_id,
                "recovery_root_research_id": self.root_id,
                "active_head_research_ids": [self.root_id],
                "historical_landmark_research_ids": [],
                "historical_landmark_reasons": {},
                "recent_attained_research_ids": [],
                "head_contexts": [],
            },
        )
        self.assertEqual(
            self._state()["targets"][self.target_id][
                "active_head_research_ids"
            ],
            [self.root_id],
        )

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
                "historical_landmark_reasons": {
                    self.landmark_id: (
                        "Ancient mechanism retained at the natural curation "
                        "window."
                    )
                },
                "recent_attained_research_ids": [],
            },
        )
        self.assertEqual(result["truth_effect"], "none")
        self.assertEqual(
            self.store.campaigns().status(self.campaign_id)["history"][
                "event_count"
            ],
            events_before + 1,
        )
        goal = lifecycle.campaign_goal_coverage(self.campaign_id)[0]
        self.assertFalse(goal["history_review_recommended"])
        self.assertEqual(
            goal["historical_landmark_research_ids"], [self.landmark_id]
        )

    def test_campaign_update_replacement_rolls_oldest_recent_at_capacity(
        self,
    ) -> None:
        lifecycle = self.store.v5_lifecycle()
        recent_ids = [
            self._research(
                f"recent-update-{index:02d}",
                f"Persisted recent attainment {index:02d}.",
            )
            for index in range(64)
        ]
        context = {
            "research_id": self.landmark_id,
            "attached_head_research_id": self.root_id,
            "reason": "Exact context must follow the replacement head.",
        }
        lifecycle._replace_campaign_frontier_working_state(
            self.campaign_id,
            targets={
                self.target_id: {
                    "recovery_root_research_id": self.root_id,
                    "active_head_research_ids": [self.root_id],
                    "historical_landmark_research_ids": [],
                    "head_contexts": [context],
                    "recent_attained_research_ids": recent_ids,
                }
            },
        )
        old_state = (
            MathGraphStore(self.root)
            .v5_lifecycle()
            ._read_campaign_frontier_working_state(self.campaign_id)
        )
        self.assertIsNotNone(old_state)
        assert old_state is not None
        self.assertEqual(
            old_state["revision"],
            "chalxius-v5-campaign-frontier-working-state-2",
        )
        self.assertEqual(
            old_state["targets"][self.target_id][
                "recent_attained_research_ids"
            ],
            recent_ids,
        )
        oldest_path = lifecycle._research_path(recent_ids[-1])
        oldest_bytes = oldest_path.read_bytes()
        fact_ids_before = self.store.fact_ids()
        campaign_event_count_before = self.store.campaigns().status(
            self.campaign_id
        )["history"]["event_count"]

        result = lifecycle.reconcile_campaign_frontier(
            self.campaign_id,
            {
                "kind": "campaign_frontier_update",
                "target_id": self.target_id,
                "attention_updates": [
                    {
                        "operation": "promote_active_head",
                        "research_id": self.successor_id,
                        "replace_head_research_id": self.root_id,
                    }
                ],
            },
        )

        state = self._state()
        row = state["targets"][self.target_id]
        self.assertEqual(result["truth_effect"], "none")
        self.assertEqual(
            state["revision"],
            "chalxius-v5-campaign-frontier-working-state-2",
        )
        self.assertEqual(row["active_head_research_ids"], [self.successor_id])
        self.assertEqual(
            row["recent_attained_research_ids"],
            [self.root_id, *recent_ids[:-1]],
        )
        self.assertEqual(
            result["attention_diff"][
                "recent_attainment_rolloff_research_ids"
            ],
            [recent_ids[-1]],
        )
        self.assertIn(
            "landmark",
            result["attention_diff"][
                "recent_attainment_rolloff_instruction"
            ],
        )
        self.assertEqual(
            row["head_contexts"],
            [
                {
                    **context,
                    "attached_head_research_id": self.successor_id,
                }
            ],
        )
        self.assertEqual(oldest_path.read_bytes(), oldest_bytes)
        self.assertEqual(
            lifecycle._research_record(recent_ids[-1])["research_id"],
            recent_ids[-1],
        )
        durable_members = lifecycle.campaign_membership_projection(
            self.campaign_id,
            full_members=True,
        )["member_research_ids"]
        self.assertIn(recent_ids[-1], durable_members)
        self.assertEqual(self.store.fact_ids(), fact_ids_before)
        self.assertEqual(
            self.store.campaigns().status(self.campaign_id)["history"][
                "event_count"
            ],
            campaign_event_count_before + 1,
        )
        self.assertTrue(self.store.audit().current_ok)

    def test_plan_round_advances_and_rolls_oldest_recent_at_capacity(
        self,
    ) -> None:
        lifecycle = self.store.v5_lifecycle()
        next_id = self._research(
            "capacity-plan-successor",
            "Main selected the next exact cut from the mature target.",
            relation="supports",
            related_research_ids=[self.root_id],
        )
        recent_ids = [
            self._research(
                f"recent-plan-{index:02d}",
                f"Persisted plan-round attainment {index:02d}.",
            )
            for index in range(64)
        ]
        context = {
            "research_id": self.landmark_id,
            "attached_head_research_id": self.root_id,
            "reason": "Exact context must survive the atomic round handoff.",
        }
        lifecycle._replace_campaign_frontier_working_state(
            self.campaign_id,
            targets={
                self.target_id: {
                    "recovery_root_research_id": self.root_id,
                    "active_head_research_ids": [self.root_id],
                    "historical_landmark_research_ids": [],
                    "head_contexts": [context],
                    "recent_attained_research_ids": recent_ids,
                }
            },
        )
        oldest_path = lifecycle._research_path(recent_ids[-1])
        oldest_bytes = oldest_path.read_bytes()
        fact_ids_before = self.store.fact_ids()
        campaign_event_count_before = self.store.campaigns().status(
            self.campaign_id
        )["history"]["event_count"]

        planned = lifecycle.create_production_round(
            workers=1,
            research_ids=[next_id],
            campaign_id=self.campaign_id,
            frontier_target_id=self.target_id,
            frontier_attention={
                "disposition": "replace_head",
                "replace_head_research_id": self.root_id,
                "context_handoff": {"mode": "all"},
            },
        )

        self.assertTrue(planned["round_id"].startswith("round-"))
        self.assertEqual(
            planned["frontier_attention_effect"][
                "recent_attainment_rolloff_research_ids"
            ],
            [recent_ids[-1]],
        )
        self.assertIn(
            "landmark",
            planned["frontier_attention_effect"][
                "recent_attainment_rolloff_instruction"
            ],
        )
        row = self._state()["targets"][self.target_id]
        self.assertEqual(row["active_head_research_ids"], [next_id])
        self.assertEqual(
            row["recent_attained_research_ids"],
            [self.root_id, *recent_ids[:-1]],
        )
        self.assertEqual(
            row["head_contexts"],
            [
                {
                    **context,
                    "attached_head_research_id": next_id,
                }
            ],
        )
        self.assertEqual(oldest_path.read_bytes(), oldest_bytes)
        self.assertEqual(
            lifecycle._research_record(recent_ids[-1])["research_id"],
            recent_ids[-1],
        )
        durable_members = lifecycle.campaign_membership_projection(
            self.campaign_id,
            full_members=True,
        )["member_research_ids"]
        self.assertIn(recent_ids[-1], durable_members)
        self.assertEqual(self.store.fact_ids(), fact_ids_before)
        self.assertEqual(
            self.store.campaigns().status(self.campaign_id)["history"][
                "event_count"
            ],
            campaign_event_count_before + 2,
        )
        self.assertTrue(self.store.audit().current_ok)

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
                frontier_attention={
                    "disposition": "replace_head",
                    "replace_head_research_id": self.root_id,
                },
            )
        row = self._state()["targets"][self.target_id]
        self.assertEqual(
            row["active_head_research_ids"], [self.successor_id]
        )
        self.assertEqual(row["recent_attained_research_ids"], [self.root_id])
        self.assertEqual(
            row["historical_landmark_research_ids"], [self.landmark_id]
        )

    def test_completed_coheads_require_explicit_natural_curation_window(
        self,
    ) -> None:
        lifecycle = self.store.v5_lifecycle()
        completed_heads = [
            self._research(
                f"completed-head-{index}",
                f"Completed independent branch {index}",
            )
            for index in range(5)
        ]
        selected = self._research(
            "selected-after-completions",
            "Next Main-selected research direction",
        )
        lifecycle._replace_campaign_frontier_working_state(
            self.campaign_id,
            targets={
                self.target_id: {
                    "recovery_root_research_id": self.root_id,
                    "active_head_research_ids": completed_heads,
                    "historical_landmark_research_ids": [],
                    "recent_attained_research_ids": [],
                }
            },
        )
        projected = {
            "target_id": self.target_id,
            "active_head_actions": [
                {
                    "research_id": research_id,
                    "next_action": "none",
                }
                for research_id in completed_heads
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
                selected_research_ids=[selected],
            )
        row = self._state()["targets"][self.target_id]
        self.assertEqual(
            row["active_head_research_ids"],
            [*completed_heads, selected],
        )
        self.assertEqual(row["historical_landmark_research_ids"], [])
        self.assertEqual(row["recent_attained_research_ids"], [])

        lifecycle.reconcile_campaign_frontier(
            self.campaign_id,
            {
                "kind": "campaign_frontier_update",
                "target_id": self.target_id,
                "attention_updates": [
                    {
                        "operation": "retire_active_head",
                        "research_id": research_id,
                        "disposition": "attained",
                    }
                    for research_id in reversed(completed_heads)
                ],
            },
        )
        goal = lifecycle.campaign_goal_coverage(self.campaign_id)[0]
        self.assertEqual(goal["recent_attained_count"], 5)
        self.assertEqual(
            goal["recent_attained_ids_sha256"],
            sha256_json(completed_heads),
        )
        self.assertTrue(goal["history_review_recommended"])

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
            "kind": "repair",
            "relation": "synthesized_repair",
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
                frontier_attention={
                    "disposition": "replace_head",
                    "replace_head_research_id": self.root_id,
                },
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
                frontier_attention={
                    "disposition": "replace_head",
                    "replace_head_research_id": self.root_id,
                },
            )
        row = self._state()["targets"][self.target_id]
        self.assertEqual(row["active_head_research_ids"], [next_id])
        self.assertEqual(row["recent_attained_research_ids"], [self.root_id])

    def test_terminal_successor_handoff_preserves_unrelated_heads_at_limit(
        self,
    ) -> None:
        lifecycle = self.store.v5_lifecycle()
        product_id = self._research(
            "completed-product",
            "Completed product of the stored root",
            relation="extends",
            related_research_ids=[self.root_id],
        )
        clean_review_id = self._research(
            "clean-review",
            "Clean independent review of the completed product",
            relation="supports",
            related_research_ids=[product_id],
        )
        next_id = self._research(
            "terminal-successor-next",
            "Main-selected continuation from exact terminal evidence",
            relation="extends",
            related_research_ids=[product_id, clean_review_id],
        )
        other_heads = [
            self._research(f"head-{index}", f"Stored head {index}")
            for index in range(7)
        ]
        in_flight_id = other_heads[0]
        stored_heads = [self.root_id, *other_heads]
        lifecycle._replace_campaign_frontier_working_state(
            self.campaign_id,
            targets={
                self.target_id: {
                    "recovery_root_research_id": self.root_id,
                    "active_head_research_ids": stored_heads,
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
                    "current_route_research_ids": [],
                    "current_terminal_research_ids": [
                        product_id,
                        clean_review_id,
                    ],
                    "terminal_evidence_research_ids": [clean_review_id],
                    "actionable_research_id": None,
                    "next_action": "plan_supervision",
                },
                {
                    "research_id": in_flight_id,
                    "current_route_research_ids": [in_flight_id],
                    "current_terminal_research_ids": [in_flight_id],
                    "terminal_evidence_research_ids": [],
                    "actionable_research_id": in_flight_id,
                    "next_action": "await_return",
                },
                *[
                    {
                        "research_id": head_id,
                        "current_route_research_ids": [],
                        "current_terminal_research_ids": [head_id],
                        "terminal_evidence_research_ids": [],
                        "actionable_research_id": None,
                        "next_action": "none",
                    }
                    for head_id in other_heads[1:]
                ],
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
                frontier_attention={
                    "disposition": "replace_head",
                    "replace_head_research_id": self.root_id,
                },
            )
        row = self._state()["targets"][self.target_id]
        self.assertEqual(
            row["active_head_research_ids"], [next_id, *other_heads]
        )
        self.assertEqual(row["recent_attained_research_ids"], [self.root_id])
        self.assertTrue(self.store.audit().current_ok)

    def test_in_flight_head_remains_goal_state_beside_reconciliation(self) -> None:
        lifecycle = self.store.v5_lifecycle()
        lifecycle._replace_campaign_frontier_working_state(
            self.campaign_id,
            targets={
                self.target_id: {
                    "recovery_root_research_id": self.root_id,
                    "active_head_research_ids": [
                        self.root_id,
                        self.successor_id,
                    ],
                    "historical_landmark_research_ids": [],
                    "recent_attained_research_ids": [],
                }
            },
        )
        records = {
            item["research_id"]: item
            for item in lifecycle.research_envelopes()
        }
        root_key = lifecycle._frontier_work_key(records[self.root_id])
        successor_key = lifecycle._frontier_work_key(
            records[self.successor_id]
        )
        completions = {
            root_key: ("pending", None, 0, "0" * 64),
            successor_key: ("pending", None, 0, "1" * 64),
        }
        actions = {
            root_key: {
                "next_action": "main_reconciliation",
                "pending_reason": "older_branch_needs_reconciliation",
                "actionable_research_id": self.root_id,
                "actionable_round_id": None,
            },
            successor_key: {
                "next_action": "await_return",
                "pending_reason": "production_round_in_flight",
                "actionable_research_id": self.successor_id,
                "actionable_round_id": "round-20260827T000000Z-00000000",
            },
        }
        with (
            patch.object(
                lifecycle,
                "_frontier_group_completion",
                return_value=completions,
            ),
            patch(
                "mathgraph.v5_lifecycle.project_frontier_group_actions",
                return_value=actions,
            ),
        ):
            goal = lifecycle.campaign_goal_coverage(self.campaign_id)[0]
        self.assertEqual(goal["coverage_status"], "in_flight")
        self.assertEqual(goal["next_action"], "advance_active_heads")
        self.assertEqual(goal["action_class"], "multi_branch_progress")
        self.assertEqual(len(goal["active_head_actions"]), 2)
        self.assertIn(
            "main_reconciliation",
            {
                item["next_action"]
                for item in goal["active_head_actions"]
            },
        )

    def test_routine_goal_projection_spends_context_on_math_not_duplicate_lineage(self) -> None:
        lifecycle = self.store.v5_lifecycle()
        actions = []
        for index in range(16):
            research_id = f"{index + 10:012x}"
            actions.append(
                {
                    "research_id": research_id,
                    "workflow_root_research_id": research_id,
                    "checkpoint_head_state": "current",
                    "action_class": "workflow_completion",
                    "next_action": "await_return",
                    "why_now": "one exact in-flight round remains",
                    "actionable_research_id": research_id,
                    "actionable_round_id": (
                        "round-20260827T000000Z-" + f"{index:08x}"
                    ),
                    "current_route_research_ids": [research_id],
                    "current_terminal_research_ids": [research_id],
                    "current_route_mathematical_summaries": [
                        {
                            "research_id": research_id,
                            "claim": "R" * 600,
                        }
                    ],
                    "terminal_evidence_research_ids": [],
                    "mathematical_summary": {
                        "research_id": research_id,
                        "kind": "conjecture",
                        "relation": "extends",
                        "claim": "C" * 900,
                        "content": "M" * 900,
                        "rationale": "D" * 900,
                    },
                    "work_completion_status": "pending",
                    "plan_round_argv": None,
                    "supervision_coverage": [
                        {
                            "production_round_id": (
                                "round-20260827T000000Z-" + f"{index:08x}"
                            ),
                            "source_component_id": f"component-{index:024x}",
                            "scope": "proof_logic",
                            "state": "completed",
                            "result_research_ids": [research_id],
                            "pending_round_ids": [],
                            "diagnostic_explanation": "X" * 800,
                        }
                    ],
                    "supervision_coverage_count": 1,
                    "supervision_coverage_sha256": "f" * 64,
                }
            )
        entry = {
            "target_id": "camtarget-0000000000000000",
            "label": "One exact mathematical goal",
            "root_research_id": self.root_id,
            "root_claim": "G" * 900,
            "coverage_status": "in_flight",
            "work_completion_status": "pending",
            "action_class": "workflow_completion",
            "next_action": "await_return",
            "why_now": "bounded active work",
            "actionable_research_id": actions[0]["research_id"],
            "actionable_round_id": actions[0]["actionable_round_id"],
            "actionable_research_ids": [actions[0]["research_id"]],
            "active_head_research_ids": [
                action["research_id"] for action in actions
            ],
            "historical_mathematical_summary": [
                {"research_id": f"{index + 30:012x}", "claim": "H" * 700}
                for index in range(8)
            ],
            "recent_attained_mathematical_history": [
                {"research_id": f"{index + 50:012x}", "claim": "N" * 700}
                for index in range(4)
            ],
            "active_head_actions": actions,
            "active_head_semantic_successors": [
                {
                    "production_product_research_ids": [
                        f"{index + 70:012x}" for index in range(16)
                    ],
                    "supervision_result_research_ids": [
                        f"{index + 90:012x}" for index in range(16)
                    ],
                }
            ],
        }
        compact = lifecycle._compact_goal_coverage_entry(entry)
        encoded = json.dumps(compact, sort_keys=True).encode()
        self.assertLess(len(encoded), 15_000)
        self.assertEqual(len(compact["active_head_actions"]), 16)
        self.assertEqual(len(compact["historical_mathematical_summary"]), 2)
        self.assertEqual(
            len(compact["recent_attained_mathematical_history"]), 2
        )
        self.assertIn(
            "claim", compact["active_head_actions"][0]["mathematical_summary"]
        )
        self.assertNotIn(
            "content",
            compact["active_head_actions"][0]["mathematical_summary"],
        )
        self.assertNotIn(
            "current_route_mathematical_summaries",
            compact["active_head_actions"][0],
        )
        self.assertNotIn(
            "current_terminal_research_ids",
            compact["active_head_actions"][0],
        )
        self.assertNotIn(
            "terminal_evidence_research_ids",
            compact["active_head_actions"][0],
        )
        self.assertNotIn(
            "supervision_coverage_sha256",
            compact["active_head_actions"][0],
        )
        self.assertEqual(
            compact["active_head_actions"][0]["supervision_coverage"],
            [
                {
                    "scope": "proof_logic",
                    "state": "completed",
                    "result_research_ids": ["00000000000a"],
                }
            ],
        )
        self.assertNotIn("active_head_semantic_successors", compact)
        self.assertNotIn("production_product_research_ids", compact)

    def test_ancient_landmark_count_is_not_a_maintenance_clock(self) -> None:
        lifecycle = self.store.v5_lifecycle()
        landmarks = [self.landmark_id]
        landmarks.extend(
            self._research(f"ancient-{index}", f"Ancient turn {index}")
            for index in range(20)
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
        self.assertEqual(
            goal["historical_landmark_research_ids"], landmarks
        )
        self.assertEqual(goal["historical_landmark_count"], len(landmarks))
        self.assertEqual(
            goal["historical_landmark_ids_sha256"], sha256_json(landmarks)
        )
        self.assertFalse(goal["history_review_recommended"])
        self.assertEqual(goal["history_review_reasons"], [])
        self.assertEqual(goal["next_action"], "production")
        routine = lifecycle.frontier_decision_surface(
            campaign_id=self.campaign_id,
            limit=1,
        )["goal_coverage"][0]
        expected_preview = [*landmarks[:2], *landmarks[-2:]]
        self.assertEqual(
            routine["historical_landmark_research_ids"], expected_preview
        )
        self.assertEqual(len(routine["historical_landmarks"]), 4)
        self.assertEqual(routine["historical_landmark_shown_count"], 4)
        self.assertTrue(routine["historical_landmarks_truncated"])
        self.assertEqual(
            routine["historical_landmark_count"], len(landmarks)
        )
        self.assertEqual(
            routine["historical_landmark_ids_sha256"],
            sha256_json(landmarks),
        )

    def test_maintenance_requires_explicit_campaign_scope(self) -> None:
        lifecycle = self.store.v5_lifecycle()
        with self.assertRaisesRegex(ValueError, "invalid campaign id"):
            lifecycle.frontier_maintenance_surface(
                campaign_id=None  # type: ignore[arg-type]
            )

        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = cli_main(
                [
                    "--root",
                    str(self.root),
                    "--role",
                    "main",
                    "frontier",
                    "--maintenance",
                ]
            )
        self.assertEqual(result, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn(
            "requires one explicit --campaign",
            stderr.getvalue(),
        )

    def test_routine_history_previews_keep_complete_diagnostic_drilldown(
        self,
    ) -> None:
        lifecycle = self.store.v5_lifecycle()
        contexts = [
            self._research(f"context-{index}", f"Context mechanism {index}")
            for index in range(7)
        ]
        landmarks = [
            self._research(f"landmark-{index}", f"Landmark mechanism {index}")
            for index in range(7)
        ]
        recent = [
            self._research(f"recent-{index}", f"Recent result {index}")
            for index in range(7)
        ]
        lifecycle._replace_campaign_frontier_working_state(
            self.campaign_id,
            targets={
                self.target_id: {
                    "recovery_root_research_id": self.root_id,
                    "active_head_research_ids": [self.root_id],
                    "historical_landmark_research_ids": landmarks,
                    "historical_landmark_reasons": {
                        research_id: f"Retain landmark {index}."
                        for index, research_id in enumerate(landmarks)
                    },
                    "recent_attained_research_ids": recent,
                    "head_contexts": [
                        {
                            "research_id": research_id,
                            "attached_head_research_id": self.root_id,
                            "reason": f"Use context {index} for this head.",
                        }
                        for index, research_id in enumerate(contexts)
                    ],
                }
            },
        )
        routine = lifecycle.frontier_decision_surface(
            campaign_id=self.campaign_id,
            limit=1,
        )["goal_coverage"][0]
        diagnostic = lifecycle.frontier_decision_surface(
            campaign_id=self.campaign_id,
            limit=1,
            diagnostic=True,
        )["goal_coverage"][0]
        maintenance_surface = lifecycle.frontier_maintenance_surface(
            campaign_id=self.campaign_id,
        )
        maintenance = maintenance_surface["targets"][0]
        expanded_surface = lifecycle.frontier_maintenance_surface(
            campaign_id=self.campaign_id,
            target_ids=(self.target_id,),
            expand_sections=("context-reasons", "recent", "queue"),
        )
        expanded = expanded_surface["targets"][0]
        all_landmarks = lifecycle.frontier_maintenance_surface(
            campaign_id=self.campaign_id,
            expand_sections=("landmarks",),
        )["targets"][0]

        self.assertEqual(len(routine["head_contexts"]), 4)
        self.assertEqual(len(routine["historical_landmarks"]), 4)
        self.assertEqual(len(routine["recent_attained_research_ids"]), 4)
        self.assertTrue(routine["head_contexts_truncated"])
        self.assertTrue(routine["historical_landmarks_truncated"])
        self.assertTrue(routine["recent_attained_truncated"])
        self.assertEqual(len(diagnostic["head_contexts"]), 7)
        self.assertEqual(len(diagnostic["historical_landmarks"]), 7)
        self.assertEqual(len(diagnostic["recent_attained_research_ids"]), 7)
        self.assertEqual(routine["head_context_count"], 7)
        self.assertEqual(routine["historical_landmark_count"], 7)
        self.assertEqual(routine["recent_attained_count"], 7)
        self.assertEqual(
            routine["head_contexts_sha256"],
            diagnostic["head_contexts_sha256"],
        )
        self.assertEqual(
            routine["historical_landmark_ids_sha256"],
            diagnostic["historical_landmark_ids_sha256"],
        )
        self.assertEqual(
            routine["recent_attained_ids_sha256"],
            diagnostic["recent_attained_ids_sha256"],
        )
        self.assertTrue(maintenance_surface["target_projection_complete"])
        self.assertTrue(maintenance_surface["all_target_projection"])
        self.assertEqual(maintenance_surface["goal_target_count"], 1)
        self.assertEqual(
            [item["research_id"] for item in maintenance["active_heads"]],
            [self.root_id],
        )
        self.assertNotIn("groups", maintenance["head_context_topology"])
        self.assertNotIn("items", maintenance["head_context_topology"])
        self.assertEqual(
            maintenance["head_context_topology"]["identity_expansion"],
            "target_drill_down",
        )
        self.assertEqual(
            maintenance["head_context_topology"]["reason_expansion"],
            "on_demand",
        )
        self.assertNotIn("items", maintenance["historical_landmarks"])
        self.assertEqual(
            [
                item["research_id"]
                for item in expanded["historical_landmarks"]["items"]
            ],
            landmarks,
        )
        self.assertEqual(
            [
                item["research_id"]
                for item in all_landmarks["historical_landmarks"]["items"]
            ],
            landmarks,
        )
        self.assertTrue(
            all(
                item["reason"] == f"Retain landmark {index}."
                and "mathematical_summary" not in item
                for index, item in enumerate(
                    expanded["historical_landmarks"]["items"]
                )
            )
        )
        self.assertEqual(
            expanded["head_context_topology"]["groups"][0][
                "research_ids"
            ],
            contexts,
        )
        self.assertEqual(
            expanded["head_context_topology"]["groups"][0][
                "attached_head_research_id"
            ],
            self.root_id,
        )
        self.assertNotIn("research_ids", maintenance["recent_attained"])
        self.assertEqual(
            [
                item["research_id"]
                for item in maintenance["recent_attained"]["summaries"]
            ],
            [*recent[:2], *recent[-2:]],
        )
        self.assertEqual(
            expanded["recent_attained"]["research_ids"], recent
        )
        self.assertTrue(
            all(
                item["reason"] == f"Use context {index} for this head."
                and "mathematical_summary" not in item
                for index, item in enumerate(
                    expanded["head_context_topology"]["items"]
                )
            )
        )
        self.assertFalse(expanded_surface["all_target_projection"])
        self.assertEqual(
            expanded_surface["selection"]["target_ids"],
            [self.target_id],
        )
        self.assertNotIn("attained_semantic_successors", maintenance)
        self.assertNotIn("historical_mathematical_summary", maintenance)
        self.assertTrue(
            maintenance_surface["maintenance_contract"][
                "reasoned_no_op_valid"
            ]
        )
        self.assertEqual(
            maintenance_surface["forensic_commands"]["full_diagnostic"],
            f"frontier --campaign {self.campaign_id} --diagnostic",
        )

        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = cli_main(
                [
                    "--root",
                    str(self.root),
                    "--role",
                    "main",
                    "frontier",
                    "--campaign",
                    self.campaign_id,
                    "--maintenance",
                ]
            )
        self.assertEqual(status, 0, stderr.getvalue())
        cli_surface = json.loads(stdout.getvalue())
        self.assertEqual(
            cli_surface["view"], "landmark_centered_situation_awareness"
        )
        self.assertEqual(len(cli_surface["targets"]), 1)

        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = cli_main(
                [
                    "--root",
                    str(self.root),
                    "--role",
                    "main",
                    "frontier",
                    "--campaign",
                    self.campaign_id,
                    "--maintenance",
                    "--maintenance-target",
                    self.target_id,
                    "--maintenance-expand",
                    "context-reasons",
                    "--maintenance-expand",
                    "recent",
                ]
            )
        self.assertEqual(status, 0, stderr.getvalue())
        cli_expanded = json.loads(stdout.getvalue())
        self.assertEqual(
            cli_expanded["targets"][0]["recent_attained"][
                "research_ids"
            ],
            recent,
        )
        self.assertEqual(
            len(
                cli_expanded["targets"][0]["head_context_topology"][
                    "items"
                ]
            ),
            len(contexts),
        )

        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = cli_main(
                [
                    "--root",
                    str(self.root),
                    "--role",
                    "main",
                    "frontier",
                    "--campaign",
                    self.campaign_id,
                    "--maintenance",
                    "--diagnostic",
                ]
            )
        self.assertNotEqual(status, 0)
        self.assertIn(
            "--maintenance is a separate compact frontier view",
            stderr.getvalue(),
        )

    def test_maintenance_index_size_ignores_local_reason_length(
        self,
    ) -> None:
        lifecycle = self.store.v5_lifecycle()
        contexts = [
            self._research(f"bounded-context-{index}", f"Context {index}")
            for index in range(12)
        ]
        landmarks = [
            self._research(
                f"bounded-landmark-{index}", f"Landmark {index}"
            )
            for index in range(3)
        ]

        def write_state(context_reason: str, landmark_reason: str) -> None:
            lifecycle._replace_campaign_frontier_working_state(
                self.campaign_id,
                targets={
                    self.target_id: {
                        "recovery_root_research_id": self.root_id,
                        "active_head_research_ids": [self.root_id],
                        "historical_landmark_research_ids": landmarks,
                        "historical_landmark_reasons": {
                            research_id: landmark_reason
                            for research_id in landmarks
                        },
                        "recent_attained_research_ids": [],
                        "head_contexts": [
                            {
                                "research_id": research_id,
                                "attached_head_research_id": self.root_id,
                                "reason": context_reason,
                            }
                            for research_id in contexts
                        ],
                    }
                },
            )

        write_state("short local reason", "short durable reason")
        short_surface = lifecycle.frontier_maintenance_surface(
            campaign_id=self.campaign_id,
        )
        write_state("x" * 2000, "y" * 2000)
        long_surface = lifecycle.frontier_maintenance_surface(
            campaign_id=self.campaign_id,
        )
        expanded = lifecycle.frontier_maintenance_surface(
            campaign_id=self.campaign_id,
            target_ids=(self.target_id,),
            expand_sections=("context-reasons",),
        )

        self.assertEqual(
            short_surface["targets"][0]["head_context_topology"]["count"],
            long_surface["targets"][0]["head_context_topology"]["count"],
        )
        self.assertLess(
            abs(
                len(json.dumps(short_surface))
                - len(json.dumps(long_surface))
            ),
            256,
        )
        self.assertGreater(
            len(json.dumps(expanded)) - len(json.dumps(long_surface)),
            20000,
        )
        self.assertEqual(
            [
                item["reason"]
                for item in expanded["targets"][0][
                    "historical_landmarks"
                ]["items"]
            ],
            ["y" * 2000 for _ in range(3)],
        )

    def test_maintenance_surface_always_covers_every_active_target(self) -> None:
        lifecycle = self.store.v5_lifecycle()
        second_root = self._research(
            "maintenance-second-root",
            "A second independent active mathematical route.",
        )
        with self.store.v5_mutation_lock(command="maintenance-target-fixture"):
            second_target_id = self.store.campaigns().target_add(
                self.campaign_id,
                {
                    "role": "research_goal",
                    "subject_kind": "research",
                    "subject_id": second_root,
                    "label": "Second maintenance target",
                },
                actor="main",
                fact_exists=lambda _fact_id: False,
                research_exists=lambda item: item == second_root,
            )
        lifecycle._replace_campaign_frontier_working_state(
            self.campaign_id,
            targets={
                self.target_id: {
                    "recovery_root_research_id": self.root_id,
                    "active_head_research_ids": [self.root_id],
                    "historical_landmark_research_ids": [],
                    "historical_landmark_reasons": {},
                    "recent_attained_research_ids": [],
                    "head_contexts": [],
                },
                second_target_id: {
                    "recovery_root_research_id": second_root,
                    "active_head_research_ids": [second_root],
                    "historical_landmark_research_ids": [],
                    "historical_landmark_reasons": {},
                    "recent_attained_research_ids": [],
                    "head_contexts": [],
                },
            },
        )

        surface = lifecycle.frontier_maintenance_surface(
            campaign_id=self.campaign_id,
        )

        self.assertEqual(surface["goal_target_count"], 2)
        self.assertTrue(surface["target_projection_complete"])
        self.assertEqual(
            {item["target_id"] for item in surface["targets"]},
            {self.target_id, second_target_id},
        )
        self.assertTrue(
            all(item["active_heads"] for item in surface["targets"])
        )

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
        with self.store.v5_mutation_lock(command="old-manual-checkpoint"):
            self.store.campaigns().update(
                self.campaign_id,
                {
                    "type": "note",
                    "payload": {
                        "kind": "campaign_frontier_head_checkpoint",
                        "generation": 37,
                        "target_frontiers": [
                            {
                                "target_id": self.target_id,
                                "recovery_root_research_id": self.root_id,
                                "active_heads": [],
                                "attained_checkpoints": [],
                                "main_disposition": "Old optional note.",
                            }
                        ],
                    },
                },
                actor="main",
            )
        surface = lifecycle.frontier_decision_surface(
            campaign_id=self.campaign_id,
            limit=2,
        )
        diagnostic_surface = lifecycle.frontier_decision_surface(
            campaign_id=self.campaign_id,
            limit=2,
            diagnostic=True,
        )
        goal = surface["goal_coverage"][0]
        diagnostic_goal = diagnostic_surface["goal_coverage"][0]
        self.assertNotIn("frontier_source", goal)
        self.assertNotIn("latest_manual_checkpoint_generation", goal)
        self.assertNotIn("frontier_version_axes", surface)
        self.assertNotIn("checkpoint_refresh", surface)
        self.assertNotIn("main_selection_policy", surface)
        self.assertEqual(diagnostic_goal["frontier_source"], "working_state")
        self.assertEqual(
            diagnostic_goal["frontier_generation_kind"],
            "dynamic_working_state",
        )
        self.assertEqual(
            diagnostic_goal["latest_manual_checkpoint_generation"], 37
        )
        self.assertEqual(
            diagnostic_surface["frontier_version_axes"],
            {
                "live_frontier_generation": diagnostic_goal[
                    "frontier_generation"
                ],
                "latest_manual_checkpoint_generation": 37,
                "manual_checkpoint": "optional_advisory_local_sequence",
                "generation_comparison_effect": "none",
                "staleness_basis": (
                    "live_frontier_state_and_exact_semantic_successor_mismatch"
                ),
                "selection_effect": "none",
            },
        )
        self.assertFalse(diagnostic_goal["checkpoint_refresh_recommended"])
        self.assertEqual(diagnostic_goal["checkpoint_refresh_reasons"], [])
        self.assertFalse(
            diagnostic_surface["checkpoint_refresh"]["recommended"]
        )
        self.assertNotIn(
            "write one new advisory checkpoint",
            diagnostic_surface["checkpoint_refresh"]["instruction"],
        )
        self.assertNotIn(
            "checkpoint", diagnostic_surface["main_selection_policy"]
        )

    def test_exact_search_context_can_attach_then_promote_atomically(self) -> None:
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
        lifecycle.reconcile_campaign_frontier(
            self.campaign_id,
            {
                "kind": "campaign_frontier_update",
                "target_id": self.target_id,
                "attention_updates": [
                    {
                        "operation": "attach_context",
                        "research_id": self.successor_id,
                        "attached_head_research_id": self.root_id,
                        "reason": "Exact search found a likely bridge for this head.",
                    }
                ],
            },
        )
        row = self._state()["targets"][self.target_id]
        self.assertEqual(
            row["head_contexts"],
            [
                {
                    "research_id": self.successor_id,
                    "attached_head_research_id": self.root_id,
                    "reason": "Exact search found a likely bridge for this head.",
                }
            ],
        )
        goal = lifecycle.frontier_decision_surface(
            campaign_id=self.campaign_id,
            limit=2,
        )["goal_coverage"][0]
        self.assertEqual(
            goal["head_contexts"][0]["mathematical_summary"]["claim"],
            "Claim successor",
        )

        lifecycle.reconcile_campaign_frontier(
            self.campaign_id,
            {
                "kind": "campaign_frontier_update",
                "target_id": self.target_id,
                "attention_updates": [
                    {
                        "operation": "promote_active_head",
                        "research_id": self.successor_id,
                        "replace_head_research_id": self.root_id,
                    }
                ],
            },
        )
        row = self._state()["targets"][self.target_id]
        self.assertEqual(row["active_head_research_ids"], [self.successor_id])
        self.assertEqual(row["head_contexts"], [])
        self.assertEqual(row["recent_attained_research_ids"], [self.root_id])

    def test_many_to_many_membership_roles_and_cross_provenance_plan(self) -> None:
        lifecycle = self.store.v5_lifecycle()
        with self.store.v5_mutation_lock(command="other-campaign-fixture"):
            other_campaign_id = self.store.campaigns().create(
                {
                    "name": "Other overlay",
                    "objective": "Reuse exact Research without ownership.",
                    "source_claim_ids": [],
                    "targets": [],
                    "constraints": [],
                    "stop_conditions": [],
                    "value_definition": "Prefer explicit links.",
                },
                actor="main",
                fact_exists=lambda _fact_id: False,
            )

        def add(label: str, campaign_id: str | None) -> str:
            payload: dict[str, object] = {
                "kind": "direction",
                "claim": f"Overlay {label}",
                "content": f"Exact old Research {label}",
                "rationale": "Exercise Campaign-side many-to-many roles.",
            }
            if campaign_id is not None:
                payload["campaign_id"] = campaign_id
            return lifecycle.add_research(payload, actor="main")["research_id"]

        plain_member = add("plain member", None)
        landmark = add("landmark", None)
        other_head = add("other head", other_campaign_id)
        other_root = add("other root", other_campaign_id)
        original_bytes = {
            research_id: lifecycle._research_path(research_id).read_bytes()
            for research_id in (plain_member, landmark, other_head)
        }
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
        lifecycle.reconcile_campaign_frontier(
            self.campaign_id,
            {
                "kind": "campaign_frontier_update",
                "target_id": self.target_id,
                "attention_updates": [
                    {
                        "operation": "reference_only",
                        "research_id": plain_member,
                    },
                    {
                        "operation": "promote_landmark",
                        "research_id": landmark,
                        "reason": "Exact old mechanism to retain.",
                    },
                    {
                        "operation": "attach_context",
                        "research_id": other_head,
                        "attached_head_research_id": self.root_id,
                        "reason": "Cross-provenance exact bridge.",
                    },
                ],
            },
        )
        projection = lifecycle.campaign_membership_projection(self.campaign_id)
        roles = {
            item["research_id"]: item["roles"]
            for item in projection["members"]
        }
        self.assertEqual(roles[plain_member], ["member"])
        self.assertEqual(roles[landmark], ["landmark", "member"])
        self.assertEqual(roles[other_head], ["context", "member"])
        self.assertNotIn(
            plain_member,
            {
                item["research_id"]
                for item in lifecycle.frontier(
                    campaign_id=self.campaign_id,
                    limit=10,
                )
            },
        )

        event_count_after_first_attention = self.store.campaigns().status(
            self.campaign_id
        )["history"]["event_count"]
        lifecycle.reconcile_campaign_frontier(
            self.campaign_id,
            {
                "kind": "campaign_frontier_update",
                "target_id": self.target_id,
                "attention_updates": [
                    {
                        "operation": "remove_context",
                        "research_id": other_head,
                    }
                ],
            },
        )
        after_remove_roles = {
            item["research_id"]: item["roles"]
            for item in lifecycle.campaign_membership_projection(
                self.campaign_id,
                full_members=True,
            )["members"]
        }
        self.assertEqual(after_remove_roles[other_head], ["member"])
        self.assertEqual(
            self.store.campaigns().status(self.campaign_id)["history"]
            ["event_count"],
            event_count_after_first_attention,
        )

        lifecycle.reconcile_campaign_frontier(
            self.campaign_id,
            {
                "kind": "campaign_frontier_update",
                "target_id": self.target_id,
                "attention_updates": [
                    {
                        "operation": "promote_active_head",
                        "research_id": other_head,
                        "replace_head_research_id": self.root_id,
                    }
                ],
            },
        )
        planned = lifecycle.create_production_round(
            workers=1,
            research_ids=[other_head],
            campaign_id=self.campaign_id,
            frontier_target_id=self.target_id,
        )
        self.assertEqual(
            planned["selection_receipt"]["campaign_membership"][
                "member_research_ids"
            ],
            [other_head],
        )

        with self.store.v5_mutation_lock(command="other-campaign-fixture"):
            other_target_id = self.store.campaigns().target_add(
                other_campaign_id,
                {
                    "role": "research_goal",
                    "subject_kind": "research",
                    "subject_id": other_root,
                    "label": "Other exact root",
                },
                actor="main",
                fact_exists=lambda _fact_id: False,
                research_exists=lambda item: item == other_root,
            )
        lifecycle.reconcile_campaign_frontier(
            other_campaign_id,
            {
                "kind": "campaign_frontier_update",
                "target_id": other_target_id,
                "attention_updates": [
                    {
                        "operation": "reference_only",
                        "research_id": plain_member,
                    }
                ],
            },
        )
        other_roles = {
            item["research_id"]: item["roles"]
            for item in lifecycle.campaign_membership_projection(
                other_campaign_id
            )["members"]
        }
        self.assertEqual(other_roles[plain_member], ["member"])
        self.assertEqual(
            original_bytes,
            {
                research_id: lifecycle._research_path(research_id).read_bytes()
                for research_id in (plain_member, landmark, other_head)
            },
        )

    def test_absent_role_removal_does_not_create_campaign_membership(
        self,
    ) -> None:
        lifecycle = self.store.v5_lifecycle()
        unrelated_id = lifecycle.add_research(
            {
                "kind": "direction",
                "claim": "Unrelated Research",
                "content": "Never associated with this Campaign.",
                "rationale": "Negative attention-membership control.",
            },
            actor="main",
        )["research_id"]
        lifecycle._replace_campaign_frontier_working_state(
            self.campaign_id,
            targets={
                self.target_id: {
                    "recovery_root_research_id": self.root_id,
                    "active_head_research_ids": [self.root_id],
                    "historical_landmark_research_ids": [],
                    "historical_landmark_reasons": {},
                    "recent_attained_research_ids": [],
                    "head_contexts": [],
                }
            },
        )
        events_before = self.store.campaigns().status(self.campaign_id)[
            "history"
        ]["event_count"]
        lifecycle.reconcile_campaign_frontier(
            self.campaign_id,
            {
                "kind": "campaign_frontier_update",
                "target_id": self.target_id,
                "attention_updates": [
                    {
                        "operation": "remove_context",
                        "research_id": unrelated_id,
                    }
                ],
            },
        )
        members = lifecycle.campaign_membership_projection(
            self.campaign_id,
            full_members=True,
        )["member_research_ids"]
        self.assertNotIn(unrelated_id, members)
        self.assertEqual(
            self.store.campaigns().status(self.campaign_id)["history"]
            ["event_count"],
            events_before,
        )

    def test_membership_is_bounded_until_explicit_forensic_drilldown(
        self,
    ) -> None:
        lifecycle = self.store.v5_lifecycle()
        members = [
            self._research(
                f"membership-preview-{index}",
                f"Independent Campaign member {index}",
            )
            for index in range(12)
        ]
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
        lifecycle.reconcile_campaign_frontier(
            self.campaign_id,
            {
                "kind": "campaign_frontier_update",
                "target_id": self.target_id,
                "attention_updates": [
                    {
                        "operation": "reference_only",
                        "research_id": research_id,
                    }
                    for research_id in members
                ],
            },
        )

        routine = lifecycle.frontier_decision_surface(
            campaign_id=self.campaign_id,
            limit=1,
        )["campaign_membership"]
        diagnostic = lifecycle.frontier_decision_surface(
            campaign_id=self.campaign_id,
            limit=1,
            diagnostic=True,
        )["campaign_membership"]
        forensic = lifecycle.frontier_decision_surface(
            campaign_id=self.campaign_id,
            limit=1,
            diagnostic=True,
            full_members=True,
        )["campaign_membership"]

        self.assertGreater(routine["member_count"], 4)
        self.assertNotIn("member_research_ids", routine)
        self.assertNotIn("members", routine)
        self.assertNotIn("members_truncated", routine)
        self.assertEqual(routine["diagnostic_command"], "frontier --diagnostic")
        self.assertEqual(
            routine["full_members_command"],
            f"frontier --campaign {self.campaign_id} --diagnostic "
            "--full-members",
        )
        self.assertEqual(
            routine["member_ids_sha256"], diagnostic["member_ids_sha256"]
        )
        self.assertEqual(len(diagnostic["member_research_ids"]), 4)
        self.assertEqual(len(diagnostic["members"]), 4)
        self.assertTrue(diagnostic["members_truncated"])
        self.assertEqual(
            diagnostic["full_members_command"],
            f"frontier --campaign {self.campaign_id} --diagnostic "
            "--full-members",
        )
        self.assertEqual(
            routine["member_ids_sha256"], forensic["member_ids_sha256"]
        )
        self.assertEqual(
            len(forensic["member_research_ids"]),
            forensic["member_count"],
        )
        self.assertEqual(len(forensic["members"]), forensic["member_count"])
        self.assertFalse(forensic["members_truncated"])
        self.assertTrue(set(members).issubset(forensic["member_research_ids"]))
        with self.assertRaisesRegex(
            ValueError,
            "full Campaign members require the diagnostic frontier",
        ):
            lifecycle.frontier_decision_surface(
                campaign_id=self.campaign_id,
                limit=1,
                full_members=True,
            )

        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = cli_main(
                [
                    "--root",
                    str(self.root),
                    "--role",
                    "main",
                    "frontier",
                    "--campaign",
                    self.campaign_id,
                    "--limit",
                    "1",
                    "--diagnostic",
                    "--full-members",
                ]
            )
        self.assertEqual(status, 0, stderr.getvalue())
        cli_membership = json.loads(stdout.getvalue())["campaign_membership"]
        self.assertEqual(
            len(cli_membership["members"]),
            cli_membership["member_count"],
        )

        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = cli_main(
                [
                    "--root",
                    str(self.root),
                    "--role",
                    "main",
                    "frontier",
                    "--campaign",
                    self.campaign_id,
                    "--full-members",
                ]
            )
        self.assertNotEqual(status, 0)
        self.assertIn("--full-members requires --diagnostic", stderr.getvalue())

    def test_same_research_has_independent_target_local_attention_roles(
        self,
    ) -> None:
        lifecycle = self.store.v5_lifecycle()
        second_root = self._research(
            "second-target-root",
            "An independent target in the same Campaign.",
        )
        with self.store.v5_mutation_lock(command="second-target-fixture"):
            second_target_id = self.store.campaigns().target_add(
                self.campaign_id,
                {
                    "role": "research_goal",
                    "subject_kind": "research",
                    "subject_id": second_root,
                    "label": "Second target-local route",
                },
                actor="main",
                fact_exists=lambda _fact_id: False,
                research_exists=lambda item: item == second_root,
            )
        lifecycle._replace_campaign_frontier_working_state(
            self.campaign_id,
            targets={
                self.target_id: {
                    "recovery_root_research_id": self.root_id,
                    "active_head_research_ids": [self.root_id],
                    "historical_landmark_research_ids": [],
                    "recent_attained_research_ids": [],
                },
                second_target_id: {
                    "recovery_root_research_id": second_root,
                    "active_head_research_ids": [second_root],
                    "historical_landmark_research_ids": [],
                    "recent_attained_research_ids": [],
                },
            },
        )
        lifecycle.reconcile_campaign_frontier(
            self.campaign_id,
            {
                "kind": "campaign_frontier_update",
                "target_id": self.target_id,
                "attention_updates": [
                    {
                        "operation": "promote_landmark",
                        "research_id": self.successor_id,
                        "reason": "Target one retains this as old mechanism.",
                    }
                ],
            },
        )
        lifecycle.reconcile_campaign_frontier(
            self.campaign_id,
            {
                "kind": "campaign_frontier_update",
                "target_id": second_target_id,
                "attention_updates": [
                    {
                        "operation": "promote_active_head",
                        "research_id": self.successor_id,
                        "replace_head_research_id": second_root,
                    }
                ],
            },
        )
        rows = self._state()["targets"]
        self.assertEqual(
            rows[self.target_id]["historical_landmark_reasons"],
            {
                self.successor_id: (
                    "Target one retains this as old mechanism."
                )
            },
        )
        self.assertEqual(
            rows[second_target_id]["active_head_research_ids"],
            [self.successor_id],
        )
        roles = {
            item["research_id"]: item["roles"]
            for item in lifecycle.campaign_membership_projection(
                self.campaign_id
            )["members"]
        }
        self.assertEqual(
            roles[self.successor_id],
            ["head", "landmark", "member"],
        )

        lifecycle.reconcile_campaign_frontier(
            self.campaign_id,
            {
                "kind": "campaign_frontier_update",
                "target_id": self.target_id,
                "attention_updates": [
                    {
                        "operation": "remove_landmark",
                        "research_id": self.successor_id,
                    }
                ],
            },
        )
        rows = self._state()["targets"]
        self.assertNotIn(
            self.successor_id,
            rows[self.target_id]["historical_landmark_research_ids"],
        )
        self.assertEqual(
            rows[second_target_id]["active_head_research_ids"],
            [self.successor_id],
        )

    def test_sparse_updates_compose_over_latest_persisted_working_state(
        self,
    ) -> None:
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
        # Simulate a stale advisory projection that still sees only the old
        # head.  It may inform Main's read surface, but it must never replace
        # the persisted write baseline between sparse transactions.
        projected_goal = {
            "target_id": self.target_id,
            "current_active_head_research_ids": [self.root_id],
            "active_head_actions": [],
            "invalid_head_research_ids": [],
            "invalid_attained_checkpoint_research_ids": [],
        }
        with patch.object(
            lifecycle,
            "campaign_goal_coverage",
            return_value=[projected_goal],
        ):
            added = lifecycle.reconcile_campaign_frontier(
                self.campaign_id,
                {
                    "kind": "campaign_frontier_update",
                    "target_id": self.target_id,
                    "attention_updates": [
                        {
                            "operation": "add_head",
                            "research_id": self.successor_id,
                        }
                    ],
                },
            )
            attached = lifecycle.reconcile_campaign_frontier(
                self.campaign_id,
                {
                    "kind": "campaign_frontier_update",
                    "target_id": self.target_id,
                    "attention_updates": [
                        {
                            "operation": "attach_context",
                            "research_id": self.landmark_id,
                            "attached_head_research_id": self.successor_id,
                            "reason": (
                                "Exact search recovered a prior theorem that "
                                "changes this current cut."
                            ),
                        }
                    ],
                },
            )
            retired = lifecycle.reconcile_campaign_frontier(
                self.campaign_id,
                {
                    "kind": "campaign_frontier_update",
                    "target_id": self.target_id,
                    "attention_updates": [
                        {
                            "operation": "retire_active_head",
                            "research_id": self.root_id,
                            "disposition": "superseded",
                        }
                    ],
                },
            )
        row = self._state()["targets"][self.target_id]
        self.assertEqual(row["active_head_research_ids"], [self.successor_id])
        self.assertEqual(
            row["head_contexts"],
            [
                {
                    "research_id": self.landmark_id,
                    "attached_head_research_id": self.successor_id,
                    "reason": (
                        "Exact search recovered a prior theorem that changes "
                        "this current cut."
                    ),
                }
            ],
        )
        self.assertEqual(
            added["attention_diff"]["before_active_head_research_ids"],
            [self.root_id],
        )
        self.assertEqual(
            attached["attention_diff"]["before_active_head_research_ids"],
            [self.root_id, self.successor_id],
        )
        self.assertEqual(
            retired["attention_diff"]["before_active_head_research_ids"],
            [self.root_id, self.successor_id],
        )

    def test_plan_round_retargets_context_on_unique_head_handoff(self) -> None:
        lifecycle = self.store.v5_lifecycle()
        next_id = self._research(
            "next-cut",
            "Main selected the exact next cut after searching the old route.",
            relation="supports",
            related_research_ids=[self.root_id],
        )
        lifecycle._replace_campaign_frontier_working_state(
            self.campaign_id,
            targets={
                self.target_id: {
                    "recovery_root_research_id": self.root_id,
                    "active_head_research_ids": [self.root_id],
                    "historical_landmark_research_ids": [],
                    "head_contexts": [
                        {
                            "research_id": self.landmark_id,
                            "attached_head_research_id": self.root_id,
                            "reason": "Old theorem that still constrains the route.",
                        }
                    ],
                    "recent_attained_research_ids": [],
                }
            },
        )
        projected_goal = {
            "target_id": self.target_id,
            "active_head_actions": [
                {
                    "research_id": self.root_id,
                    "actionable_research_id": self.root_id,
                    "current_route_research_ids": [self.root_id],
                    "current_terminal_research_ids": [],
                    "terminal_evidence_research_ids": [],
                    "next_action": "plan_production",
                }
            ],
        }
        with patch.object(
            lifecycle,
            "campaign_goal_coverage",
            return_value=[projected_goal],
        ):
            lifecycle._advance_campaign_frontier_for_plan(
                campaign_id=self.campaign_id,
                frontier_target_id=self.target_id,
                selected_research_ids=[next_id],
                frontier_attention={
                    "disposition": "replace_head",
                    "replace_head_research_id": self.root_id,
                    "context_handoff": {"mode": "all"},
                },
            )
        row = self._state()["targets"][self.target_id]
        self.assertEqual(row["active_head_research_ids"], [next_id])
        self.assertEqual(
            row["head_contexts"],
            [
                {
                    "research_id": self.landmark_id,
                    "attached_head_research_id": next_id,
                    "reason": "Old theorem that still constrains the route.",
                }
            ],
        )

    def test_plan_round_retargets_context_after_completed_head(self) -> None:
        lifecycle = self.store.v5_lifecycle()
        next_id = self._research(
            "post-completion-cut",
            "Main selected one new cut after the old workflow completed.",
        )
        lifecycle._replace_campaign_frontier_working_state(
            self.campaign_id,
            targets={
                self.target_id: {
                    "recovery_root_research_id": self.root_id,
                    "active_head_research_ids": [self.root_id],
                    "historical_landmark_research_ids": [],
                    "head_contexts": [
                        {
                            "research_id": self.landmark_id,
                            "attached_head_research_id": self.root_id,
                            "reason": (
                                "This theorem remains relevant after the "
                                "completed workflow hands off."
                            ),
                        }
                    ],
                    "recent_attained_research_ids": [],
                }
            },
        )
        projected_goal = {
            "target_id": self.target_id,
            "active_head_actions": [
                {
                    "research_id": self.root_id,
                    "actionable_research_id": self.root_id,
                    "current_route_research_ids": [],
                    "current_terminal_research_ids": [],
                    "terminal_evidence_research_ids": [self.successor_id],
                    "next_action": "none",
                }
            ],
        }
        with patch.object(
            lifecycle,
            "campaign_goal_coverage",
            return_value=[projected_goal],
        ):
            lifecycle._advance_campaign_frontier_for_plan(
                campaign_id=self.campaign_id,
                frontier_target_id=self.target_id,
                selected_research_ids=[next_id],
                frontier_attention={
                    "disposition": "replace_head",
                    "replace_head_research_id": self.root_id,
                    "context_handoff": {"mode": "all"},
                },
            )
        row = self._state()["targets"][self.target_id]
        self.assertEqual(row["active_head_research_ids"], [next_id])
        self.assertEqual(
            row["head_contexts"],
            [
                {
                    "research_id": self.landmark_id,
                    "attached_head_research_id": next_id,
                    "reason": (
                        "This theorem remains relevant after the completed "
                        "workflow hands off."
                    ),
                }
            ],
        )

    def test_plan_round_preserves_unrelated_completed_cohead_and_contexts(
        self,
    ) -> None:
        lifecycle = self.store.v5_lifecycle()
        type_e_head = self._research(
            "type-e-completed-head",
            "A separately supervised Type-E attention centre.",
        )
        s1_successor = self._research(
            "s1-repair-successor",
            "The unique repair selected only for the S1 head.",
            relation="supports",
            related_research_ids=[self.root_id],
        )
        type_e_context_ids = [
            self._research(
                f"type-e-context-{index}",
                f"Exact Type-E reference {index}.",
            )
            for index in range(10)
        ]
        type_e_contexts = [
            {
                "research_id": research_id,
                "attached_head_research_id": type_e_head,
                "reason": f"Type-E exact context {index} remains bound.",
            }
            for index, research_id in enumerate(type_e_context_ids)
        ]
        lifecycle._replace_campaign_frontier_working_state(
            self.campaign_id,
            targets={
                self.target_id: {
                    "recovery_root_research_id": self.root_id,
                    "active_head_research_ids": [
                        self.root_id,
                        type_e_head,
                    ],
                    "historical_landmark_research_ids": [],
                    "head_contexts": type_e_contexts,
                    "recent_attained_research_ids": [],
                }
            },
        )
        projected_goal = {
            "target_id": self.target_id,
            "active_head_actions": [
                {
                    "research_id": self.root_id,
                    "actionable_research_id": self.root_id,
                    "current_route_research_ids": [self.root_id],
                    "current_terminal_research_ids": [],
                    "terminal_evidence_research_ids": [],
                    "next_action": "repair",
                },
                {
                    "research_id": type_e_head,
                    "actionable_research_id": type_e_head,
                    "current_route_research_ids": [],
                    "current_terminal_research_ids": [],
                    "terminal_evidence_research_ids": [self.successor_id],
                    "next_action": "none",
                },
            ],
        }
        with patch.object(
            lifecycle,
            "campaign_goal_coverage",
            return_value=[projected_goal],
        ):
            lifecycle._advance_campaign_frontier_for_plan(
                campaign_id=self.campaign_id,
                frontier_target_id=self.target_id,
                selected_research_ids=[s1_successor],
                frontier_attention={
                    "disposition": "replace_head",
                    "replace_head_research_id": self.root_id,
                },
            )
        row = self._state()["targets"][self.target_id]
        self.assertEqual(
            row["active_head_research_ids"],
            [s1_successor, type_e_head],
        )
        self.assertEqual(row["head_contexts"], type_e_contexts)
        self.assertNotIn(
            type_e_head,
            row["recent_attained_research_ids"],
        )

    def test_public_plan_round_atomically_hands_context_to_sole_successor(
        self,
    ) -> None:
        lifecycle = self.store.v5_lifecycle()
        next_id = self._research(
            "public-next-cut",
            "One explicit target-local production cut selected by Main.",
        )
        lifecycle._replace_campaign_frontier_working_state(
            self.campaign_id,
            targets={
                self.target_id: {
                    "recovery_root_research_id": self.root_id,
                    "active_head_research_ids": [self.root_id],
                    "historical_landmark_research_ids": [],
                    "head_contexts": [
                        {
                            "research_id": self.landmark_id,
                            "attached_head_research_id": self.root_id,
                            "reason": "Exact comparator for the selected route.",
                        }
                    ],
                    "recent_attained_research_ids": [],
                }
            },
        )
        planned = lifecycle.create_production_round(
            workers=1,
            research_ids=[next_id],
            campaign_id=self.campaign_id,
            frontier_target_id=self.target_id,
            frontier_attention={
                "disposition": "replace_head",
                "replace_head_research_id": self.root_id,
                "context_handoff": {"mode": "all"},
            },
        )
        row = self._state()["targets"][self.target_id]
        self.assertEqual(row["active_head_research_ids"], [next_id])
        self.assertEqual(
            row["head_contexts"],
            [
                {
                    "research_id": self.landmark_id,
                    "attached_head_research_id": next_id,
                    "reason": "Exact comparator for the selected route.",
                }
            ],
        )
        self.assertEqual(
            planned["frontier_attention_effect"][
                "before_active_head_research_ids"
            ],
            [self.root_id],
        )
        self.assertEqual(
            planned["selection_receipt"]["revision"],
            "chalxius-v5-plan-round-selection-4",
        )
        self.assertIn(
            "--frontier-disposition",
            planned["selection_receipt"]["exact_replay_argv"],
        )

    def test_multi_selection_adds_heads_without_guessing_context_handoff(self) -> None:
        lifecycle = self.store.v5_lifecycle()
        successors = [
            self._research(
                f"split-cut-{index}",
                f"Independent successor surface {index}.",
                relation="supports",
                related_research_ids=[self.root_id],
            )
            for index in range(2)
        ]
        lifecycle._replace_campaign_frontier_working_state(
            self.campaign_id,
            targets={
                self.target_id: {
                    "recovery_root_research_id": self.root_id,
                    "active_head_research_ids": [self.root_id],
                    "historical_landmark_research_ids": [],
                    "head_contexts": [
                        {
                            "research_id": self.landmark_id,
                            "attached_head_research_id": self.root_id,
                            "reason": "A reference whose split destination is ambiguous.",
                        }
                    ],
                    "recent_attained_research_ids": [],
                }
            },
        )
        projected_goal = {
            "target_id": self.target_id,
            "active_head_actions": [
                {
                    "research_id": self.root_id,
                    "actionable_research_id": self.root_id,
                    "current_route_research_ids": [self.root_id],
                    "current_terminal_research_ids": [],
                    "terminal_evidence_research_ids": [],
                    "next_action": "plan_production",
                }
            ],
        }
        with patch.object(
            lifecycle,
            "campaign_goal_coverage",
            return_value=[projected_goal],
        ):
            lifecycle._advance_campaign_frontier_for_plan(
                campaign_id=self.campaign_id,
                frontier_target_id=self.target_id,
                selected_research_ids=successors,
            )
        row = self._state()["targets"][self.target_id]
        self.assertEqual(
            row["active_head_research_ids"], [self.root_id, *successors]
        )
        self.assertEqual(
            row["head_contexts"][0]["attached_head_research_id"], self.root_id
        )

    def test_context_attach_to_head_absorbs_unattached_duplicate(self) -> None:
        lifecycle = self.store.v5_lifecycle()
        lifecycle._replace_campaign_frontier_working_state(
            self.campaign_id,
            targets={
                self.target_id: {
                    "recovery_root_research_id": self.root_id,
                    "active_head_research_ids": [self.root_id],
                    "historical_landmark_research_ids": [],
                    "head_contexts": [
                        {
                            "research_id": self.landmark_id,
                            "attached_head_research_id": None,
                            "reason": "The same exact context for this route.",
                        }
                    ],
                    "recent_attained_research_ids": [],
                }
            },
        )
        lifecycle.reconcile_campaign_frontier(
            self.campaign_id,
            {
                "kind": "campaign_frontier_update",
                "target_id": self.target_id,
                "attention_updates": [
                    {
                        "operation": "attach_context",
                        "research_id": self.landmark_id,
                        "attached_head_research_id": self.root_id,
                        "reason": "The same exact context for this route.",
                    }
                ],
            },
        )
        row = self._state()["targets"][self.target_id]
        self.assertEqual(
            row["head_contexts"],
            [
                {
                    "research_id": self.landmark_id,
                    "attached_head_research_id": self.root_id,
                    "reason": "The same exact context for this route.",
                }
            ],
        )

    def test_context_attach_supersedes_distinct_unattached_reason(self) -> None:
        lifecycle = self.store.v5_lifecycle()
        lifecycle._replace_campaign_frontier_working_state(
            self.campaign_id,
            targets={
                self.target_id: {
                    "recovery_root_research_id": self.root_id,
                    "active_head_research_ids": [self.root_id],
                    "historical_landmark_research_ids": [],
                    "head_contexts": [
                        {
                            "research_id": self.landmark_id,
                            "attached_head_research_id": None,
                            "reason": (
                                "A different ambiguous branch still needs "
                                "placement."
                            ),
                        }
                    ],
                    "recent_attained_research_ids": [],
                }
            },
        )
        lifecycle.reconcile_campaign_frontier(
            self.campaign_id,
            {
                "kind": "campaign_frontier_update",
                "target_id": self.target_id,
                "attention_updates": [
                    {
                        "operation": "attach_context",
                        "research_id": self.landmark_id,
                        "attached_head_research_id": self.root_id,
                        "reason": "Exact context for the selected head.",
                    }
                ],
            },
        )
        row = self._state()["targets"][self.target_id]
        self.assertEqual(
            row["head_contexts"],
            [
                {
                    "research_id": self.landmark_id,
                    "attached_head_research_id": self.root_id,
                    "reason": "Exact context for the selected head.",
                }
            ],
        )

    def test_write_preserves_unattached_context_from_an_ambiguous_branch(
        self,
    ) -> None:
        lifecycle = self.store.v5_lifecycle()
        lifecycle._replace_campaign_frontier_working_state(
            self.campaign_id,
            targets={
                self.target_id: {
                    "recovery_root_research_id": self.root_id,
                    "active_head_research_ids": [self.root_id],
                    "historical_landmark_research_ids": [],
                    "head_contexts": [
                        {
                            "research_id": self.landmark_id,
                            "attached_head_research_id": self.root_id,
                            "reason": "The comparator remains exact for head A.",
                        },
                        {
                            "research_id": self.landmark_id,
                            "attached_head_research_id": None,
                            "reason": (
                                "A split of old head B has no unique context "
                                "destination."
                            ),
                        },
                    ],
                    "recent_attained_research_ids": [],
                }
            },
        )
        row = self._state()["targets"][self.target_id]
        self.assertEqual(len(row["head_contexts"]), 2)
        self.assertEqual(
            {
                context["attached_head_research_id"]
                for context in row["head_contexts"]
            },
            {self.root_id, None},
        )
        lifecycle._read_campaign_frontier_working_state(self.campaign_id)

    def test_two_context_heads_converge_without_poisoning_next_read(self) -> None:
        lifecycle = self.store.v5_lifecycle()
        second_head = self._research(
            "second-head", "A second active mathematical branch."
        )
        merged_head = self._research(
            "merged-head",
            "One Main-selected cut jointly succeeds both prior branches.",
            relation="supports",
            related_research_ids=[self.root_id, second_head],
        )
        lifecycle._replace_campaign_frontier_working_state(
            self.campaign_id,
            targets={
                self.target_id: {
                    "recovery_root_research_id": self.root_id,
                    "active_head_research_ids": [self.root_id, second_head],
                    "historical_landmark_research_ids": [],
                    "head_contexts": [
                        {
                            "research_id": self.landmark_id,
                            "attached_head_research_id": self.root_id,
                            "reason": "The comparator as used by the first branch.",
                        },
                        {
                            "research_id": self.landmark_id,
                            "attached_head_research_id": second_head,
                            "reason": "The current comparator rationale after convergence.",
                        },
                    ],
                    "recent_attained_research_ids": [],
                }
            },
        )
        projected_goal = {
            "target_id": self.target_id,
            "active_head_actions": [
                {
                    "research_id": head_id,
                    "actionable_research_id": head_id,
                    "current_route_research_ids": [head_id],
                    "current_terminal_research_ids": [],
                    "terminal_evidence_research_ids": [],
                    "next_action": "plan_production",
                }
                for head_id in (self.root_id, second_head)
            ],
        }
        with patch.object(
            lifecycle,
            "campaign_goal_coverage",
            return_value=[projected_goal],
        ):
            for replaced_head in (self.root_id, second_head):
                lifecycle._advance_campaign_frontier_for_plan(
                    campaign_id=self.campaign_id,
                    frontier_target_id=self.target_id,
                    selected_research_ids=[merged_head],
                    frontier_attention={
                        "disposition": "replace_head",
                        "replace_head_research_id": replaced_head,
                        "context_handoff": {"mode": "all"},
                    },
                )
        row = self._state()["targets"][self.target_id]
        self.assertEqual(row["active_head_research_ids"], [merged_head])
        self.assertEqual(
            row["head_contexts"],
            [
                {
                    "research_id": self.landmark_id,
                    "attached_head_research_id": merged_head,
                    "reason": (
                        "The current comparator rationale after convergence."
                    ),
                }
            ],
        )
        reread = lifecycle._read_campaign_frontier_working_state(
            self.campaign_id
        )
        self.assertIsNotNone(reread)

    def test_existing_new_head_context_wins_when_old_head_converges(self) -> None:
        lifecycle = self.store.v5_lifecycle()
        lifecycle._replace_campaign_frontier_working_state(
            self.campaign_id,
            targets={
                self.target_id: {
                    "recovery_root_research_id": self.root_id,
                    "active_head_research_ids": [
                        self.root_id,
                        self.successor_id,
                    ],
                    "historical_landmark_research_ids": [],
                    "head_contexts": [
                        {
                            "research_id": self.landmark_id,
                            "attached_head_research_id": self.root_id,
                            "reason": "Older route-specific rationale.",
                        },
                        {
                            "research_id": self.landmark_id,
                            "attached_head_research_id": self.successor_id,
                            "reason": "Rationale already current on the new head.",
                        },
                    ],
                    "recent_attained_research_ids": [],
                }
            },
        )
        projected_goal = {
            "target_id": self.target_id,
            "active_head_actions": [
                {
                    "research_id": self.root_id,
                    "actionable_research_id": self.successor_id,
                    "current_route_research_ids": [self.root_id],
                    "current_terminal_research_ids": [],
                    "terminal_evidence_research_ids": [],
                    "next_action": "production",
                },
                {
                    "research_id": self.successor_id,
                    "actionable_research_id": self.successor_id,
                    "current_route_research_ids": [self.successor_id],
                    "current_terminal_research_ids": [],
                    "terminal_evidence_research_ids": [],
                    "next_action": "production",
                },
            ],
        }
        with patch.object(
            lifecycle,
            "campaign_goal_coverage",
            return_value=[projected_goal],
        ):
            lifecycle._advance_campaign_frontier_for_plan(
                campaign_id=self.campaign_id,
                frontier_target_id=self.target_id,
                selected_research_ids=[self.successor_id],
                frontier_attention={
                    "disposition": "replace_head",
                    "replace_head_research_id": self.root_id,
                    "context_handoff": {"mode": "all"},
                },
            )
        row = self._state()["targets"][self.target_id]
        self.assertEqual(row["active_head_research_ids"], [self.successor_id])
        self.assertEqual(len(row["head_contexts"]), 1)
        self.assertEqual(
            row["head_contexts"][0]["reason"],
            "Rationale already current on the new head.",
        )
        lifecycle._read_campaign_frontier_working_state(self.campaign_id)

    def test_multi_head_plan_does_not_guess_pairwise_replacements(self) -> None:
        lifecycle = self.store.v5_lifecycle()
        second_head = self._research(
            "parallel-old-head", "A logically independent old branch."
        )
        first_new = self._research(
            "parallel-new-one",
            "Successor of only the first old branch.",
            relation="supports",
            related_research_ids=[self.root_id],
        )
        second_new = self._research(
            "parallel-new-two",
            "Successor of only the second old branch.",
            relation="supports",
            related_research_ids=[second_head],
        )
        lifecycle._replace_campaign_frontier_working_state(
            self.campaign_id,
            targets={
                self.target_id: {
                    "recovery_root_research_id": self.root_id,
                    "active_head_research_ids": [self.root_id, second_head],
                    "historical_landmark_research_ids": [],
                    "head_contexts": [
                        {
                            "research_id": self.landmark_id,
                            "attached_head_research_id": self.root_id,
                            "reason": "Comparator for branch one.",
                        },
                        {
                            "research_id": self.landmark_id,
                            "attached_head_research_id": second_head,
                            "reason": "Comparator for branch two.",
                        },
                    ],
                    "recent_attained_research_ids": [],
                }
            },
        )
        projected_goal = {
            "target_id": self.target_id,
            "active_head_actions": [
                {
                    "research_id": head_id,
                    "actionable_research_id": head_id,
                    "current_route_research_ids": [head_id],
                    "current_terminal_research_ids": [],
                    "terminal_evidence_research_ids": [],
                    "next_action": "production",
                }
                for head_id in (self.root_id, second_head)
            ],
        }
        with patch.object(
            lifecycle,
            "campaign_goal_coverage",
            return_value=[projected_goal],
        ):
            lifecycle._advance_campaign_frontier_for_plan(
                campaign_id=self.campaign_id,
                frontier_target_id=self.target_id,
                selected_research_ids=[first_new, second_new],
            )
        row = self._state()["targets"][self.target_id]
        self.assertEqual(
            row["active_head_research_ids"],
            [self.root_id, second_head, first_new, second_new],
        )
        self.assertEqual(
            {
                context["attached_head_research_id"]
                for context in row["head_contexts"]
            },
            {self.root_id, second_head},
        )
        lifecycle._read_campaign_frontier_working_state(self.campaign_id)

    def test_repair_of_handoff_carries_context_to_repair_head(self) -> None:
        lifecycle = self.store.v5_lifecycle()
        repair_id = self._research(
            "repair-head", "A structured repair of the exact route product."
        )
        lifecycle._replace_campaign_frontier_working_state(
            self.campaign_id,
            targets={
                self.target_id: {
                    "recovery_root_research_id": self.root_id,
                    "active_head_research_ids": [self.root_id],
                    "historical_landmark_research_ids": [],
                    "head_contexts": [
                        {
                            "research_id": self.landmark_id,
                            "attached_head_research_id": self.root_id,
                            "reason": "A theorem the repair must continue to use.",
                        }
                    ],
                    "recent_attained_research_ids": [],
                }
            },
        )
        projected_goal = {
            "target_id": self.target_id,
            "active_head_actions": [
                {
                    "research_id": self.root_id,
                    "actionable_research_id": self.successor_id,
                    "current_route_research_ids": [self.successor_id],
                    "current_terminal_research_ids": [],
                    "terminal_evidence_research_ids": [],
                    "next_action": "repair",
                }
            ],
        }
        repair_record = {
            "research_id": repair_id,
            "kind": "repair",
            "relation": "synthesized_repair",
            "metadata": {"repair_of_research_id": self.successor_id},
        }
        with (
            patch.object(
                lifecycle,
                "campaign_goal_coverage",
                return_value=[projected_goal],
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
                selected_research_ids=[repair_id],
                frontier_attention={
                    "disposition": "replace_head",
                    "replace_head_research_id": self.root_id,
                    "context_handoff": {"mode": "all"},
                },
            )
        row = self._state()["targets"][self.target_id]
        self.assertEqual(row["active_head_research_ids"], [repair_id])
        self.assertEqual(
            row["head_contexts"][0]["attached_head_research_id"], repair_id
        )
        lifecycle._read_campaign_frontier_working_state(self.campaign_id)

    def test_sparse_landmark_records_reason_without_becoming_a_head(self) -> None:
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
        lifecycle.reconcile_campaign_frontier(
            self.campaign_id,
            {
                "kind": "campaign_frontier_update",
                "target_id": self.target_id,
                "attention_updates": [
                    {
                        "operation": "promote_landmark",
                        "research_id": self.landmark_id,
                        "reason": "Mechanism change that future route selection must remember.",
                    }
                ],
            },
        )
        row = self._state()["targets"][self.target_id]
        self.assertEqual(row["active_head_research_ids"], [self.root_id])
        self.assertEqual(
            row["historical_landmark_research_ids"], [self.landmark_id]
        )
        self.assertEqual(
            row["historical_landmark_reasons"][self.landmark_id],
            "Mechanism change that future route selection must remember.",
        )

    def test_same_target_active_head_can_remain_a_durable_landmark(self) -> None:
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
        lifecycle.reconcile_campaign_frontier(
            self.campaign_id,
            {
                "kind": "campaign_frontier_update",
                "target_id": self.target_id,
                "attention_updates": [
                    {
                        "operation": "promote_landmark",
                        "research_id": self.root_id,
                        "reason": "Current and durable load-bearing mechanism.",
                    }
                ],
            },
        )
        lifecycle.reconcile_campaign_frontier(
            self.campaign_id,
            {
                "kind": "campaign_frontier_update",
                "target_id": self.target_id,
                "attention_updates": [
                    {
                        "operation": "promote_active_head",
                        "research_id": self.successor_id,
                        "replace_head_research_id": self.root_id,
                    },
                    {
                        "operation": "promote_landmark",
                        "research_id": self.successor_id,
                        "reason": "New current result is also a durable landmark.",
                    },
                ],
            },
        )
        row = self._state()["targets"][self.target_id]
        self.assertEqual(row["active_head_research_ids"], [self.successor_id])
        self.assertEqual(
            row["historical_landmark_research_ids"],
            [self.root_id, self.successor_id],
        )
        self.assertEqual(row["recent_attained_research_ids"], [])
        lifecycle._read_campaign_frontier_working_state(self.campaign_id)

    def test_named_head_replacement_transfers_exact_context(self) -> None:
        lifecycle = self.store.v5_lifecycle()
        lifecycle._replace_campaign_frontier_working_state(
            self.campaign_id,
            targets={
                self.target_id: {
                    "recovery_root_research_id": self.root_id,
                    "active_head_research_ids": [self.root_id],
                    "historical_landmark_research_ids": [],
                    "head_contexts": [
                        {
                            "research_id": self.landmark_id,
                            "attached_head_research_id": self.root_id,
                            "reason": "Exact theorem needed by this route.",
                        }
                    ],
                    "recent_attained_research_ids": [],
                }
            },
        )
        result = lifecycle.reconcile_campaign_frontier(
            self.campaign_id,
            {
                "kind": "campaign_frontier_update",
                "target_id": self.target_id,
                "attention_updates": [
                    {
                        "operation": "promote_active_head",
                        "research_id": self.successor_id,
                        "replace_head_research_id": self.root_id,
                    }
                ],
            },
        )
        row = self._state()["targets"][self.target_id]
        self.assertEqual(
            row["head_contexts"],
            [
                {
                    "research_id": self.landmark_id,
                    "attached_head_research_id": self.successor_id,
                    "reason": "Exact theorem needed by this route.",
                }
            ],
        )
        self.assertEqual(
            result["attention_diff"]["transferred_context_count"], 1
        )
        self.assertEqual(result["attention_diff"]["detached_context_count"], 0)

    def test_add_then_retire_stays_legal_but_warns_it_is_not_replacement(
        self,
    ) -> None:
        lifecycle = self.store.v5_lifecycle()
        lifecycle._replace_campaign_frontier_working_state(
            self.campaign_id,
            targets={
                self.target_id: {
                    "recovery_root_research_id": self.root_id,
                    "active_head_research_ids": [self.root_id],
                    "historical_landmark_research_ids": [],
                    "head_contexts": [
                        {
                            "research_id": self.landmark_id,
                            "attached_head_research_id": self.root_id,
                            "reason": "Exact theorem needed by the old route.",
                        }
                    ],
                    "recent_attained_research_ids": [],
                }
            },
        )
        result = lifecycle.reconcile_campaign_frontier(
            self.campaign_id,
            {
                "kind": "campaign_frontier_update",
                "target_id": self.target_id,
                "attention_updates": [
                    {
                        "operation": "add_head",
                        "research_id": self.successor_id,
                    },
                    {
                        "operation": "retire_active_head",
                        "research_id": self.root_id,
                        "disposition": "superseded",
                    },
                ],
            },
        )
        row = self._state()["targets"][self.target_id]
        self.assertEqual(row["active_head_research_ids"], [self.successor_id])
        self.assertEqual(
            row["head_contexts"][0]["attached_head_research_id"],
            None,
        )
        self.assertEqual(result["attention_diff"]["detached_context_count"], 1)
        warning_codes = {
            item["code"] for item in result["attention_diff"]["warnings"]
        }
        self.assertIn(
            "add_and_retire_are_not_head_replacement",
            warning_codes,
        )
        self.assertIn(
            "retired_head_contexts_left_unattached",
            warning_codes,
        )

    def test_concrete_context_attachment_absorbs_old_null_copy(self) -> None:
        lifecycle = self.store.v5_lifecycle()
        lifecycle._replace_campaign_frontier_working_state(
            self.campaign_id,
            targets={
                self.target_id: {
                    "recovery_root_research_id": self.root_id,
                    "active_head_research_ids": [self.root_id],
                    "historical_landmark_research_ids": [],
                    "head_contexts": [
                        {
                            "research_id": self.landmark_id,
                            "attached_head_research_id": None,
                            "reason": "Old ambiguous route rationale.",
                        }
                    ],
                    "recent_attained_research_ids": [],
                }
            },
        )
        lifecycle.reconcile_campaign_frontier(
            self.campaign_id,
            {
                "kind": "campaign_frontier_update",
                "target_id": self.target_id,
                "attention_updates": [
                    {
                        "operation": "attach_context",
                        "research_id": self.landmark_id,
                        "attached_head_research_id": self.root_id,
                        "reason": "Main resolved the exact attachment.",
                    }
                ],
            },
        )
        self.assertEqual(
            self._state()["targets"][self.target_id]["head_contexts"],
            [
                {
                    "research_id": self.landmark_id,
                    "attached_head_research_id": self.root_id,
                    "reason": "Main resolved the exact attachment.",
                }
            ],
        )

    def test_internal_maintenance_clock_is_nonblocking_and_pausable(self) -> None:
        lifecycle = self.store.v5_lifecycle()
        clock = lifecycle.reset_frontier_maintenance_clock(
            self.campaign_id,
            completed_at="2026-09-01T10:00:00Z",
            interval_minutes=50,
        )
        self.assertEqual(clock["next_due_at"], "2026-09-01T10:50:00.000000+00:00")
        self.assertIsNone(
            lifecycle.frontier_maintenance_advisory(
                self.campaign_id,
                now=datetime(2026, 9, 1, 10, 49, tzinfo=timezone.utc),
            )
        )
        advisory = lifecycle.frontier_maintenance_advisory(
            self.campaign_id,
            now=datetime(2026, 9, 1, 10, 50, tzinfo=timezone.utc),
        )
        self.assertIsNotNone(advisory)
        assert advisory is not None
        self.assertFalse(advisory["blocking"])
        self.assertEqual(advisory["truth_effect"], "none")
        self.assertEqual(
            advisory["maintenance_command"],
            f"frontier --campaign {self.campaign_id} --maintenance",
        )
        self.assertTrue(advisory["reasoned_no_op_valid"])
        lifecycle.pause_frontier_maintenance_clock(self.campaign_id)
        self.assertIsNone(
            lifecycle.frontier_maintenance_advisory(
                self.campaign_id,
                now=datetime(2026, 9, 1, 11, 0, tzinfo=timezone.utc),
            )
        )
        lifecycle.reset_frontier_maintenance_clock(
            self.campaign_id,
            completed_at="2000-01-01T00:00:00Z",
        )
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = cli_main(
                [
                    "--root",
                    str(self.root),
                    "--role",
                    "main",
                    "campaign-status",
                    self.campaign_id,
                ]
            )
        self.assertEqual(status, 0, stderr.getvalue())
        self.assertIn(
            "[Chalxius full frontier maintenance due]",
            stderr.getvalue(),
        )

    def test_overdue_maintenance_is_structured_on_frontier_and_plan(self) -> None:
        lifecycle = self.store.v5_lifecycle()
        lifecycle.reset_frontier_maintenance_clock(
            self.campaign_id,
            completed_at="2000-01-01T00:00:00Z",
        )
        frontier_stdout = StringIO()
        frontier_stderr = StringIO()
        with redirect_stdout(frontier_stdout), redirect_stderr(frontier_stderr):
            status = cli_main(
                [
                    "--root",
                    str(self.root),
                    "--role",
                    "main",
                    "frontier",
                    "--campaign",
                    self.campaign_id,
                    "--limit",
                    "2",
                ]
            )
        self.assertEqual(status, 0, frontier_stderr.getvalue())
        frontier = json.loads(frontier_stdout.getvalue())
        self.assertEqual(
            frontier["main_attention"]["state"],
            "frontier_maintenance_overdue",
        )
        self.assertFalse(
            frontier["main_attention"]["frontier_maintenance"]["blocking"]
        )

        plan_stdout = StringIO()
        plan_stderr = StringIO()
        with redirect_stdout(plan_stdout), redirect_stderr(plan_stderr):
            status = cli_main(
                [
                    "--root",
                    str(self.root),
                    "--role",
                    "main",
                    "plan-round",
                    "--workers",
                    "1",
                    "--memory-id",
                    self.root_id,
                    "--campaign",
                    self.campaign_id,
                    "--frontier-target",
                    self.target_id,
                    "--host-task-scope-id",
                    "hosttask-maintenance-attention",
                ]
            )
        self.assertEqual(status, 0, plan_stderr.getvalue())
        planned = json.loads(plan_stdout.getvalue())
        self.assertIn("round_id", planned)
        self.assertEqual(
            planned["main_attention"]["state"],
            "frontier_maintenance_overdue",
        )
        self.assertEqual(
            planned["main_attention"]["command_blocking_effect"], "none"
        )

    def test_aborted_selected_head_round_requires_main_disposition(self) -> None:
        lifecycle = self.store.v5_lifecycle()
        lifecycle._replace_campaign_frontier_working_state(
            self.campaign_id,
            targets={
                self.target_id: {
                    "recovery_root_research_id": self.root_id,
                    "active_head_research_ids": [self.root_id],
                    "historical_landmark_research_ids": [],
                    "recent_attained_research_ids": [],
                    "head_contexts": [],
                }
            },
        )
        planned = lifecycle.create_production_round(
            workers=1,
            research_ids=[self.root_id],
            campaign_id=self.campaign_id,
            frontier_target_id=self.target_id,
            host_task_scope_id="hosttask-aborted-head-disposition",
        )
        with self.store.v5_mutation_lock(command="work-unit-abort"):
            self.store.reasoning_modes().abort_work_unit(
                round_id=planned["round_id"],
                actor="main",
                reason="Exercise explicit stopped-route disposition.",
            )
        goal = lifecycle.frontier_decision_surface(
            campaign_id=self.campaign_id,
            limit=2,
        )["goal_coverage"][0]
        self.assertEqual(goal["coverage_status"], "needs_main_choice")
        self.assertEqual(goal["next_action"], "main_reconciliation")
        self.assertEqual(
            goal["why_now"], "aborted_head_needs_main_disposition"
        )
        self.assertEqual(goal["actionable_round_id"], planned["round_id"])
        self.assertEqual(
            goal["active_head_actions"][0]["why_now"],
            "aborted_head_needs_main_disposition",
        )

    def test_landmark_ids_cannot_silently_receive_a_generic_reason(self) -> None:
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
        state_before = self._state()
        with self.assertRaisesRegex(
            ValueError, "one exact Main reason"
        ):
            lifecycle.reconcile_campaign_frontier(
                self.campaign_id,
                {
                    "kind": "campaign_frontier_update",
                    "target_id": self.target_id,
                    "historical_landmark_research_ids": [self.landmark_id],
                },
            )
        self.assertEqual(self._state(), state_before)

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

    def test_invalid_target_row_blocks_plan_and_reconcile_preserves_peer(self) -> None:
        lifecycle = self.store.v5_lifecycle()
        peer_root = self._research("peer-root", "Independent peer target")
        peer_landmark = self._research(
            "peer-landmark", "Durable peer mechanism"
        )
        peer_context = self._research(
            "peer-context", "Reference needed by the peer target"
        )
        with self.store.v5_mutation_lock(command="frontier-state-fixture"):
            peer_target_id = self.store.campaigns().target_add(
                self.campaign_id,
                {
                    "role": "research_goal",
                    "subject_kind": "research",
                    "subject_id": peer_root,
                    "label": "Preserve the independent peer target",
                },
                actor="main",
                fact_exists=lambda _fact_id: False,
                research_exists=lambda item: item == peer_root,
            )
        peer_row = {
            "recovery_root_research_id": peer_root,
            "active_head_research_ids": [peer_root],
            "historical_landmark_research_ids": [peer_landmark],
            "historical_landmark_reasons": {
                peer_landmark: "Peer mechanism that must survive recovery."
            },
            "head_contexts": [
                {
                    "research_id": peer_context,
                    "attached_head_research_id": peer_root,
                    "reason": "Exact peer reference.",
                }
            ],
            "recent_attained_research_ids": [],
        }
        lifecycle._replace_campaign_frontier_working_state(
            self.campaign_id,
            targets={
                self.target_id: {
                    "recovery_root_research_id": self.root_id,
                    "active_head_research_ids": [self.root_id],
                    "historical_landmark_research_ids": [self.landmark_id],
                    "historical_landmark_reasons": {
                        self.landmark_id: "Primary durable mechanism."
                    },
                    "head_contexts": [],
                    "recent_attained_research_ids": [],
                },
                peer_target_id: peer_row,
            },
        )
        corrupted = self._state()
        del corrupted["targets"][self.target_id][
            "historical_landmark_reasons"
        ]
        state_path = (
            self.root
            / "campaigns"
            / self.campaign_id
            / "frontier-state.json"
        )
        state_path.write_text(
            json.dumps(corrupted, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        rounds_before = set(self.store.rounds_dir.glob("round-*"))
        with self.assertRaisesRegex(
            ValueError, "explicit Main reconciliation"
        ):
            lifecycle.create_production_round(
                workers=1,
                research_ids=[self.root_id],
                campaign_id=self.campaign_id,
                frontier_target_id=self.target_id,
            )
        self.assertEqual(
            set(self.store.rounds_dir.glob("round-*")), rounds_before
        )
        lifecycle.reconcile_campaign_frontier(
            self.campaign_id,
            {
                "kind": "campaign_frontier_update",
                "target_id": self.target_id,
                "active_head_research_ids": [self.root_id],
                "historical_landmark_research_ids": [self.landmark_id],
                "historical_landmark_reasons": {
                    self.landmark_id: "Primary durable mechanism."
                },
            },
        )
        self.assertEqual(
            self._state()["targets"][peer_target_id], peer_row
        )


if __name__ == "__main__":
    unittest.main()

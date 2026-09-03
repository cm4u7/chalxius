from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mathgraph.store import MathGraphStore


class PlanAttentionDispositionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "project"
        self.store = MathGraphStore(self.root)
        self.store.initialize(
            project_id="chx-002-plan-attention",
            title="CHX-002 plan attention",
            workflow_evidence_version=5,
        )
        self.lifecycle = self.store.v5_lifecycle()
        self.campaign_a = self._campaign("a")
        self.root_id = self._research("root", campaign_id=self.campaign_a)
        self.next_id = self._research(
            "next",
            campaign_id=self.campaign_a,
            relation="supports",
            related_research_ids=[self.root_id],
        )
        self.context_one = self._research("context-one")
        self.context_two = self._research("context-two")
        self.target_a = self._target(self.campaign_a, self.root_id, "A")
        with self.store.v5_mutation_lock(command="chx-002-fixture-activate"):
            self.store.campaigns().activate(self.campaign_a, actor="main")
        self._set_state(
            self.campaign_a,
            self.target_a,
            heads=[self.root_id],
            contexts=[
                self._context(self.context_one, self.root_id, "First exact input."),
                self._context(self.context_two, self.root_id, "Second exact input."),
            ],
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _campaign(self, label: str) -> str:
        with self.store.v5_mutation_lock(command="chx-002-fixture-campaign"):
            return self.store.campaigns().create(
                {
                    "name": f"Campaign {label}",
                    "objective": f"Resolve target {label}.",
                    "source_claim_ids": [],
                    "targets": [],
                    "constraints": [],
                    "stop_conditions": [],
                    "value_definition": "Prefer exact Main-selected work.",
                },
                actor="main",
                fact_exists=lambda _fact_id: False,
            )

    def _research(
        self,
        label: str,
        *,
        campaign_id: str | None = None,
        relation: str | None = None,
        related_research_ids: list[str] | None = None,
    ) -> str:
        payload: dict[str, object] = {
            "kind": "direction",
            "claim": f"Claim {label}",
            "content": f"Content {label}",
            "rationale": f"Rationale {label}",
            "decision_profile": {
                "impact": 0.8,
                "information_value": 0.8,
                "tractability": 0.7,
                "burden": 0.2,
            },
        }
        if campaign_id is not None:
            payload["campaign_id"] = campaign_id
        if relation is not None:
            payload["relation"] = relation
            payload["related_research_ids"] = related_research_ids or []
        return self.lifecycle.add_research(payload, actor="main")["research_id"]

    def _target(self, campaign_id: str, research_id: str, label: str) -> str:
        with self.store.v5_mutation_lock(command="chx-002-fixture-target"):
            return self.store.campaigns().target_add(
                campaign_id,
                {
                    "role": "research_goal",
                    "subject_kind": "research",
                    "subject_id": research_id,
                    "label": f"Target {label}",
                },
                actor="main",
                fact_exists=lambda _fact_id: False,
                research_exists=lambda item: item == research_id,
            )

    @staticmethod
    def _context(research_id: str, head_id: str | None, reason: str) -> dict:
        return {
            "research_id": research_id,
            "attached_head_research_id": head_id,
            "reason": reason,
        }

    def _set_state(
        self,
        campaign_id: str,
        target_id: str,
        *,
        heads: list[str],
        contexts: list[dict] | None = None,
        recent: list[str] | None = None,
    ) -> None:
        self.lifecycle._replace_campaign_frontier_working_state(
            campaign_id,
            targets={
                target_id: {
                    "recovery_root_research_id": heads[0],
                    "active_head_research_ids": heads,
                    "historical_landmark_research_ids": [],
                    "historical_landmark_reasons": {},
                    "head_contexts": contexts or [],
                    "recent_attained_research_ids": recent or [],
                }
            },
        )

    def _row(self, campaign_id: str, target_id: str) -> dict:
        state = self.lifecycle._read_campaign_frontier_working_state(campaign_id)
        assert state is not None
        return state["targets"][target_id]

    def test_default_add_head_ignores_relation_and_preserves_context(self) -> None:
        result = self.lifecycle._advance_campaign_frontier_for_plan(
            campaign_id=self.campaign_a,
            frontier_target_id=self.target_a,
            selected_research_ids=[self.next_id],
        )
        row = self._row(self.campaign_a, self.target_a)
        self.assertEqual(
            row["active_head_research_ids"], [self.root_id, self.next_id]
        )
        self.assertEqual(
            {item["attached_head_research_id"] for item in row["head_contexts"]},
            {self.root_id},
        )
        effect = result["frontier_attention_effect"]
        self.assertEqual(effect["retired_head_research_ids"], [])
        self.assertEqual(effect["moved_contexts"], [])
        self.assertEqual(effect["truth_effect"], "none")

    def test_replace_none_detaches_while_selected_moves_only_named_context(self) -> None:
        detached = self.lifecycle._advance_campaign_frontier_for_plan(
            campaign_id=self.campaign_a,
            frontier_target_id=self.target_a,
            selected_research_ids=[self.next_id],
            frontier_attention={
                "disposition": "replace_head",
                "replace_head_research_id": self.root_id,
            },
        )["frontier_attention_effect"]
        self.assertEqual(
            detached["unattached_context_research_ids"],
            [self.context_one, self.context_two],
        )
        self.assertEqual(
            {item["attached_head_research_id"] for item in self._row(
                self.campaign_a, self.target_a
            )["head_contexts"]},
            {None},
        )

        self._set_state(
            self.campaign_a,
            self.target_a,
            heads=[self.root_id],
            contexts=[
                self._context(self.context_one, self.root_id, "First exact input."),
                self._context(self.context_two, self.root_id, "Second exact input."),
            ],
        )
        selected = self.lifecycle._advance_campaign_frontier_for_plan(
            campaign_id=self.campaign_a,
            frontier_target_id=self.target_a,
            selected_research_ids=[self.next_id],
            frontier_attention={
                "disposition": "replace_head",
                "replace_head_research_id": self.root_id,
                "context_handoff": {
                    "mode": "selected",
                    "research_ids": [self.context_one],
                },
            },
        )["frontier_attention_effect"]
        attachments = {
            item["research_id"]: item["attached_head_research_id"]
            for item in self._row(self.campaign_a, self.target_a)["head_contexts"]
        }
        self.assertEqual(attachments[self.context_one], self.next_id)
        self.assertIsNone(attachments[self.context_two])
        self.assertEqual(
            [item["research_id"] for item in selected["moved_contexts"]],
            [self.context_one],
        )
        self.assertEqual(
            selected["unattached_context_research_ids"], [self.context_two]
        )

    def test_add_head_can_move_selected_context_from_exact_old_head(self) -> None:
        effect = self.lifecycle._advance_campaign_frontier_for_plan(
            campaign_id=self.campaign_a,
            frontier_target_id=self.target_a,
            selected_research_ids=[self.next_id],
            frontier_attention={
                "disposition": "add_head",
                "context_handoff": {
                    "mode": "selected",
                    "from_head_research_id": self.root_id,
                    "research_ids": [self.context_two],
                },
            },
        )["frontier_attention_effect"]
        attachments = {
            item["research_id"]: item["attached_head_research_id"]
            for item in self._row(self.campaign_a, self.target_a)["head_contexts"]
        }
        self.assertEqual(attachments[self.context_one], self.root_id)
        self.assertEqual(attachments[self.context_two], self.next_id)
        self.assertEqual(effect["unattached_context_research_ids"], [])

    def test_capacity_failure_is_visible_and_preserves_state(self) -> None:
        heads = [self.root_id]
        for index in range(15):
            heads.append(self._research(f"capacity-{index}"))
        overflow = self._research("overflow")
        self._set_state(self.campaign_a, self.target_a, heads=heads)
        before = self.lifecycle._read_campaign_frontier_working_state(
            self.campaign_a
        )
        with self.assertRaisesRegex(
            ValueError,
            "capacity exceeded without changing state",
        ):
            self.lifecycle._advance_campaign_frontier_for_plan(
                campaign_id=self.campaign_a,
                frontier_target_id=self.target_a,
                selected_research_ids=[overflow],
            )
        after = self.lifecycle._read_campaign_frontier_working_state(
            self.campaign_a
        )
        self.assertEqual(after, before)

    def test_receipt_v4_freezes_attention_and_v1_v3_still_validate(self) -> None:
        planned = self.lifecycle.create_production_round(
            workers=1,
            research_ids=[self.next_id],
            campaign_id=self.campaign_a,
            frontier_target_id=self.target_a,
        )
        receipt = planned["selection_receipt"]
        self.assertEqual(receipt["revision"], "chalxius-v5-plan-round-selection-4")
        self.assertEqual(
            receipt["frontier_attention"]["disposition"], "add_head"
        )
        self.assertIn("--frontier-disposition", receipt["exact_replay_argv"])
        self.lifecycle._validate_plan_round_selection_receipt(
            receipt,
            assignments=planned["assignments"],
            campaign_scope=planned["campaign_scope"],
        )

        for revision in (1, 2, 3):
            legacy = {
                key: json.loads(json.dumps(value))
                for key, value in receipt.items()
                if key != "frontier_attention"
            }
            legacy["revision"] = f"chalxius-v5-plan-round-selection-{revision}"
            if revision == 1:
                legacy.pop("frontier_target_id")
                legacy.pop("campaign_membership")
                replay_target = None
            elif revision == 2:
                legacy.pop("campaign_membership")
                replay_target = self.target_a
            else:
                replay_target = self.target_a
            legacy["exact_replay_argv"] = self.lifecycle._exact_plan_round_argv(
                [self.next_id],
                campaign_id=self.campaign_a,
                frontier_target_id=replay_target,
            )
            self.lifecycle._validate_plan_round_selection_receipt(
                legacy,
                assignments=planned["assignments"],
                campaign_scope=planned["campaign_scope"],
            )

    def test_repair_retry_reuses_math_round_and_applies_new_attention(self) -> None:
        campaign_b = self._campaign("b")
        target_b = self._target(campaign_b, self.root_id, "B")
        with self.store.v5_mutation_lock(command="chx-002-fixture-activate-b"):
            self.store.campaigns().activate(campaign_b, actor="main")
        self._set_state(campaign_b, target_b, heads=[self.root_id])

        first = self.lifecycle.create_repair_round(
            self.root_id,
            campaign_id=campaign_b,
            frontier_target_id=target_b,
            host_task_scope_id="chx-002-repair-retry",
        )
        repair_record = self.lifecycle._research_record(first["research_id"])
        self.assertEqual(
            repair_record["metadata"]["campaign_id"], self.campaign_a
        )
        self.assertEqual(first["campaign_scope"]["campaign_id"], campaign_b)
        self.assertEqual(
            self._row(campaign_b, target_b)["active_head_research_ids"],
            [self.root_id, first["research_id"]],
        )

        second = self.lifecycle.create_repair_round(
            self.root_id,
            campaign_id=campaign_b,
            frontier_target_id=target_b,
            frontier_attention={
                "disposition": "replace_head",
                "replace_head_research_id": self.root_id,
            },
            host_task_scope_id="chx-002-repair-retry",
        )
        self.assertEqual(second["research_id"], first["research_id"])
        self.assertEqual(second["round_id"], first["round_id"])
        self.assertTrue(second["planning_reused"])
        self.assertEqual(len(list(self.store.rounds_dir.glob("round-*"))), 1)
        self.assertEqual(
            self._row(campaign_b, target_b)["active_head_research_ids"],
            [first["research_id"]],
        )
        self.assertEqual(
            second["frontier_attention_effect"]["retired_head_research_ids"],
            [self.root_id],
        )
        self.assertEqual(self.store.fact_ids(), [])
        self.assertTrue(self.store.audit().current_ok)

    def test_exact_replace_retry_is_an_attention_noop_not_new_work(self) -> None:
        first = self.lifecycle.create_repair_round(
            self.root_id,
            campaign_id=self.campaign_a,
            frontier_target_id=self.target_a,
            frontier_attention={
                "disposition": "replace_head",
                "replace_head_research_id": self.root_id,
                "context_handoff": {"mode": "all"},
            },
            host_task_scope_id="chx-002-exact-replace-retry",
        )
        second = self.lifecycle.create_repair_round(
            self.root_id,
            campaign_id=self.campaign_a,
            frontier_target_id=self.target_a,
            frontier_attention={
                "disposition": "replace_head",
                "replace_head_research_id": self.root_id,
                "context_handoff": {"mode": "all"},
            },
            host_task_scope_id="chx-002-exact-replace-retry",
        )
        self.assertEqual(second["round_id"], first["round_id"])
        self.assertTrue(second["planning_reused"])
        self.assertEqual(len(list(self.store.rounds_dir.glob("round-*"))), 1)
        effect = second["frontier_attention_effect"]
        self.assertEqual(
            effect["before_active_head_research_ids"],
            [first["research_id"]],
        )
        self.assertEqual(
            effect["after_active_head_research_ids"],
            [first["research_id"]],
        )
        self.assertEqual(effect["moved_contexts"], [])
        self.assertEqual(effect["unattached_context_research_ids"], [])
        self.assertTrue(self.store.audit().current_ok)


if __name__ == "__main__":
    unittest.main()

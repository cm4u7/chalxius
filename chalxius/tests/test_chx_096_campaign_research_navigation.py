from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from mathgraph.cli import main as cli_main
from mathgraph.contracts import sha256_json
from mathgraph.store import MathGraphStore
from mathgraph.v5_lifecycle import RoundInspectionContext


class CampaignResearchNavigationTests(unittest.TestCase):
    @staticmethod
    def _store(root: Path) -> MathGraphStore:
        store = MathGraphStore(root)
        store.initialize(
            project_id="campaign-research-navigation",
            title="Campaign Research navigation",
            workflow_evidence_version=5,
        )
        return store

    @staticmethod
    def _campaign(store: MathGraphStore) -> str:
        with store.v5_mutation_lock(command="campaign-navigation-create"):
            return store.campaigns().create(
                {
                    "name": "Campaign navigation",
                    "objective": "Keep the exact current Research boundary visible.",
                    "source_claim_ids": [],
                    "targets": [],
                    "constraints": [],
                    "stop_conditions": [],
                    "value_definition": "Prefer exact nonduplicative work.",
                },
                actor="main",
                fact_exists=lambda _fact_id: False,
            )

    @staticmethod
    def _run_cli(*arguments: str) -> tuple[int, str, str]:
        output = io.StringIO()
        error = io.StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            status = cli_main(list(arguments))
        return status, output.getvalue(), error.getvalue()

    def test_default_search_and_show_include_immutable_research(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            store = self._store(root)
            record = store.v5_lifecycle().add_research(
                {
                    "kind": "direction",
                    "claim": "The ResearchOnlyNeedle boundary is current.",
                    "content": "Use this exact Research node before dispatch.",
                },
                actor="main",
            )
            research_id = str(record["research_id"])

            # The truth-stage Fact API remains Fact-only, while Main's ordinary
            # graph navigation searches Research without a filesystem scan.
            self.assertEqual(store.search("ResearchOnlyNeedle"), [])
            result = store.search_graph("ResearchOnlyNeedle", limit=4)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["object_type"], "research")
            self.assertEqual(result[0]["research_id"], research_id)
            self.assertEqual(
                store.search_graph(
                    "ResearchOnlyNeedle", limit=4, scope="facts"
                ),
                [],
            )

            status, output, error = self._run_cli(
                "--root",
                str(root),
                "--role",
                "main",
                "search",
                "ResearchOnlyNeedle",
            )
            self.assertEqual(status, 0, error)
            self.assertEqual(json.loads(output)[0]["research_id"], research_id)

            status, output, error = self._run_cli(
                "--root",
                str(root),
                "--role",
                "main",
                "show",
                research_id,
            )
            self.assertEqual(status, 0, error)
            shown = json.loads(output)
            self.assertEqual(shown["research_id"], research_id)
            self.assertEqual(
                shown["claim"], "The ResearchOnlyNeedle boundary is current."
            )

    def test_stale_checkpoint_head_projects_current_terminal_and_refresh_hint(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            campaign_id = self._campaign(store)
            anchor = lifecycle.add_research(
                {
                    "kind": "direction",
                    "claim": "Keep one durable Campaign anchor.",
                    "campaign_id": campaign_id,
                },
                actor="main",
            )
            head = lifecycle.add_research(
                {
                    "kind": "proof_attempt",
                    "claim": "Produce the first bounded result.",
                    "campaign_id": campaign_id,
                },
                actor="main",
            )
            anchor_id = str(anchor["research_id"])
            head_id = str(head["research_id"])
            with store.v5_mutation_lock(command="campaign-navigation-checkpoint"):
                target_id = store.campaigns().target_add(
                    campaign_id,
                    {
                        "role": "research_goal",
                        "subject_kind": "research",
                        "subject_id": anchor_id,
                        "label": "Keep current terminal heads visible",
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
                            "supersedes_event_id": None,
                            "target_frontiers": [
                                {
                                    "target_id": target_id,
                                    "recovery_root_research_id": anchor_id,
                                    "active_heads": [
                                        {"research_id": head_id}
                                    ],
                                    "attained_checkpoints": [],
                                    "main_disposition": "Continue exactly.",
                                }
                            ],
                        },
                    },
                    actor="main",
                )

            product_id = "a" * 12
            plan_id = "b" * 12
            review_id = "c" * 12
            bases = {
                item["research_id"]: item
                for item in lifecycle.research_envelopes()
            }
            bases[product_id] = {
                "research_id": product_id,
                "kind": "insight",
                "relation": "responds_to",
                "related_research_ids": [head_id],
                "created_at": "2026-01-01T00:01:00+00:00",
                "status": "open",
                "metadata": {
                    "campaign_id": campaign_id,
                    "assignment_provenance": {
                        "adverse_assignment": False,
                        "work_mode": "prove",
                    },
                    # An incomplete or blocked product is still an exact
                    # workflow successor for checkpoint freshness.  Its
                    # completion remains a separate Main-visible question.
                    "obligation_dispositions": [],
                },
            }
            bases[plan_id] = {
                "research_id": plan_id,
                "kind": "challenge",
                "relation": "challenges",
                "related_research_ids": [product_id],
                "created_at": "2026-01-01T00:02:00+00:00",
                "status": "open",
                "metadata": {
                    "campaign_id": campaign_id,
                    "research_supervision": {
                        "source_receipts": [
                            {"result_research_id": product_id}
                        ]
                    },
                },
            }
            bases[review_id] = {
                "research_id": review_id,
                "kind": "insight",
                "relation": "responds_to",
                "related_research_ids": [plan_id],
                "created_at": "2026-01-01T00:03:00+00:00",
                "status": "open",
                "metadata": {
                    "campaign_id": campaign_id,
                    "assignment_provenance": {
                        "adverse_assignment": True,
                        "work_mode": "refute",
                    },
                },
            }
            work_keys = {
                research_id: sha256_json(["work", research_id])
                for research_id in bases
            }
            workgroups = {
                work_key: [research_id]
                for research_id, work_key in work_keys.items()
            }
            head_work_key = work_keys[head_id]
            inspection = RoundInspectionContext(
                frontier_group_completions={
                    head_work_key: ("pending", None, 0, sha256_json([]))
                },
                frontier_group_actions={
                    head_work_key: {
                        "next_action": "main_reconciliation",
                        "pending_reason": "supervision_result_lineage_unreadable",
                        "actionable_research_id": review_id,
                        "actionable_round_id": None,
                        "actionable_research_ids": [review_id],
                    }
                },
            )
            with patch.object(
                lifecycle,
                "_frontier_structural_state_for_inspection",
                return_value=(bases, {}, {}, workgroups, work_keys),
            ), patch.object(lifecycle, "frontier", return_value=[]):
                surface = lifecycle.frontier_decision_surface(
                    campaign_id=campaign_id,
                    _inspection_context=inspection,
                )
                diagnostic_surface = lifecycle.frontier_decision_surface(
                    campaign_id=campaign_id,
                    diagnostic=True,
                    _inspection_context=inspection,
                )

            goal = surface["goal_coverage"][0]
            diagnostic_goal = diagnostic_surface["goal_coverage"][0]
            self.assertEqual(goal["active_head_research_ids"], [head_id])
            self.assertEqual(
                goal["stale_active_head_research_ids"], [head_id]
            )
            self.assertEqual(
                goal["current_active_head_research_ids"], []
            )
            self.assertEqual(
                goal["active_head_actions"][0]["checkpoint_head_state"],
                "stale_exact_successor_available",
            )
            self.assertNotIn(
                "current_terminal_research_ids",
                goal["active_head_actions"][0],
            )
            self.assertNotIn(
                "current_route_research_ids",
                goal["active_head_actions"][0],
            )
            self.assertNotIn(
                "terminal_evidence_research_ids",
                goal["active_head_actions"][0],
            )
            self.assertEqual(
                diagnostic_goal["active_head_actions"][0][
                    "current_terminal_research_ids"
                ],
                [review_id],
            )
            self.assertEqual(
                diagnostic_goal["active_head_actions"][0][
                    "terminal_evidence_research_ids"
                ],
                [review_id],
            )
            self.assertNotIn("active_head_semantic_successors", goal)
            self.assertNotIn("attained_semantic_successors", goal)
            self.assertIn(
                "active_head_semantic_successors", diagnostic_goal
            )
            self.assertIn("attained_semantic_successors", diagnostic_goal)
            self.assertTrue(goal["checkpoint_refresh_recommended"])
            self.assertIn(
                "active_head_has_newer_terminal_successor",
                goal["checkpoint_refresh_reasons"],
            )
            self.assertEqual(
                surface["checkpoint_refresh"],
                {
                    "recommended": True,
                    "reason_codes": [
                        "active_head_has_newer_terminal_successor"
                    ],
                    "target_ids": [target_id],
                    "selection_effect": "none",
                    "instruction": (
                        "Main should exact-search the listed Research ids and "
                        "write one new advisory checkpoint when the semantic "
                        "choice is clear; this hint neither mutates Campaign "
                        "state nor blocks planning."
                    ),
                },
            )

    def test_productive_review_and_legacy_cow_repair_are_current_routes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            campaign_id = "campaign-" + "1" * 12
            head_id = "a" * 12
            product_id = "b" * 12
            proof_plan_id = "c" * 12
            challenge_id = "d" * 12
            clean_review_id = "e" * 12
            repair_id = "f" * 12
            synthesis_id = "9" * 12
            bases = {
                head_id: {
                    "research_id": head_id,
                    "kind": "direction",
                    "relation": "supports",
                    "related_research_ids": [],
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "status": "open",
                    "metadata": {"campaign_id": campaign_id},
                },
                product_id: {
                    "research_id": product_id,
                    "kind": "proof_attempt",
                    "relation": "responds_to",
                    "related_research_ids": [head_id],
                    "created_at": "2026-01-01T00:01:00+00:00",
                    "status": "open",
                    "metadata": {
                        "campaign_id": campaign_id,
                        "assignment_provenance": {
                            "adverse_assignment": False,
                            "work_mode": "prove",
                        },
                        "obligation_dispositions": [],
                    },
                },
                proof_plan_id: {
                    "research_id": proof_plan_id,
                    "kind": "challenge",
                    "relation": "reviews_whole_product",
                    "related_research_ids": sorted([head_id, product_id]),
                    "created_at": "2026-01-01T00:02:00+00:00",
                    "status": "open",
                    "metadata": {
                        "research_supervision": {
                            "source_receipts": [
                                {"result_research_id": product_id}
                            ]
                        },
                    },
                },
                challenge_id: {
                    "research_id": challenge_id,
                    "kind": "challenge",
                    "relation": "finds_factor_rank_gap",
                    "related_research_ids": [proof_plan_id],
                    "created_at": "2026-01-01T00:03:00+00:00",
                    "status": "open",
                    "metadata": {
                        "assignment_provenance": {
                            "adverse_assignment": True,
                            "work_mode": "refute",
                        },
                        "worker_outcome": "challenge",
                    },
                },
            }
            source_plan_id = "1" * 12
            bases[source_plan_id] = {
                "research_id": source_plan_id,
                "kind": "challenge",
                "relation": "challenges",
                "related_research_ids": [product_id],
                "created_at": "2026-01-01T00:02:30+00:00",
                "status": "open",
                "metadata": {
                    "campaign_id": campaign_id,
                    "research_supervision": {
                        "source_receipts": [
                            {"result_research_id": product_id}
                        ]
                    },
                },
            }
            bases[clean_review_id] = {
                "research_id": clean_review_id,
                "kind": "insight",
                "relation": "responds_to",
                "related_research_ids": [source_plan_id],
                "created_at": "2026-01-01T00:03:30+00:00",
                "status": "open",
                "metadata": {
                    "campaign_id": campaign_id,
                    "assignment_provenance": {
                        "adverse_assignment": True,
                        "work_mode": "refute",
                    },
                    "worker_outcome": "evidence",
                },
            }

            # Receipt targets are the rigid supervision coverage.  Additional
            # related Research is legitimate review context, and relation labels
            # remain descriptive.  Campaign provenance is still derived exactly
            # for both the plan and its returned review.
            self.assertEqual(
                lifecycle._checkpoint_research_campaign_ids(
                    proof_plan_id, bases
                ),
                frozenset({campaign_id}),
            )
            self.assertEqual(
                lifecycle._checkpoint_research_campaign_ids(challenge_id, bases),
                frozenset({campaign_id}),
            )

            index = lifecycle._campaign_semantic_successor_index(bases)
            summary, terminals = (
                lifecycle._campaign_attained_semantic_successor_summary(
                    attained_research_id=head_id,
                    campaign_id=campaign_id,
                    bases=bases,
                    index=index,
                )
            )
            self.assertEqual(terminals, [challenge_id, clean_review_id])
            self.assertEqual(
                summary["current_route_research_ids"], [challenge_id]
            )
            self.assertEqual(
                summary["terminal_evidence_research_ids"],
                [clean_review_id],
            )

            # Structured repair identity is carried by kind plus exact lineage,
            # not by one reserved relation label or one required trigger author.
            # It still supersedes the productive challenge in Main's read-only
            # freshness view without asserting mathematical completion.
            bases[synthesis_id] = {
                "research_id": synthesis_id,
                "kind": "challenge",
                "relation": "combines_review_findings",
                "source": (
                    f"research:{product_id}; research:{challenge_id}"
                ),
                "related_research_ids": sorted(
                    {product_id, challenge_id}
                ),
                "created_at": "2026-01-01T00:03:45+00:00",
                "status": "open",
                "metadata": {"campaign_id": campaign_id},
            }
            bases[repair_id] = {
                "research_id": repair_id,
                "kind": "repair",
                "relation": "synthesized_repair",
                "source": f"research:{product_id}",
                "related_research_ids": sorted(
                    {product_id, synthesis_id}
                ),
                "created_at": "2026-01-01T00:04:00+00:00",
                "status": "open",
                "metadata": {
                    "campaign_id": campaign_id,
                    "repair_of_research_id": product_id,
                    "trigger_research_id": synthesis_id,
                },
            }
            index = lifecycle._campaign_semantic_successor_index(bases)
            self.assertIn(synthesis_id, index["children"][challenge_id])
            self.assertIn(repair_id, index["children"][synthesis_id])
            summary, terminals = (
                lifecycle._campaign_attained_semantic_successor_summary(
                    attained_research_id=head_id,
                    campaign_id=campaign_id,
                    bases=bases,
                    index=index,
                )
            )
            self.assertEqual(terminals, [clean_review_id, repair_id])
            self.assertEqual(
                summary["current_route_research_ids"], [repair_id]
            )
            self.assertEqual(
                summary["terminal_evidence_research_ids"],
                [clean_review_id],
            )

    def test_in_flight_supervision_does_not_dirty_stable_task_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            campaign_id = self._campaign(store)
            root = lifecycle.add_research(
                {
                    "kind": "direction",
                    "claim": "Keep the durable production task visible.",
                    "campaign_id": campaign_id,
                },
                actor="main",
            )
            root_id = str(root["research_id"])
            product_id = "a" * 12
            plan_id = "b" * 12
            with store.v5_mutation_lock(command="campaign-navigation-checkpoint"):
                target_id = store.campaigns().target_add(
                    campaign_id,
                    {
                        "role": "research_goal",
                        "subject_kind": "research",
                        "subject_id": root_id,
                        "label": "Keep one supervised product route current",
                    },
                    actor="main",
                    fact_exists=lambda _fact_id: False,
                    research_exists=lambda item: item == root_id,
                )
                store.campaigns().update(
                    campaign_id,
                    {
                        "type": "note",
                        "payload": {
                            "kind": "campaign_frontier_head_checkpoint",
                            "generation": 1,
                            "supersedes_event_id": None,
                            "target_frontiers": [
                                {
                                    "target_id": target_id,
                                    "recovery_root_research_id": root_id,
                                    "active_heads": [{"research_id": root_id}],
                                    "attained_checkpoints": [
                                        {"research_id": product_id}
                                    ],
                                    "main_disposition": (
                                        "Product attained; supervision is in flight."
                                    ),
                                }
                            ],
                        },
                    },
                    actor="main",
                )

            bases = {
                item["research_id"]: item
                for item in lifecycle.research_envelopes()
            }
            bases[product_id] = {
                "research_id": product_id,
                "kind": "proof_attempt",
                "relation": "responds_to",
                "related_research_ids": [root_id],
                "created_at": "2026-01-01T00:01:00+00:00",
                "status": "open",
                "metadata": {
                    "campaign_id": campaign_id,
                    "assignment_provenance": {
                        "adverse_assignment": False,
                        "work_mode": "prove",
                    },
                },
            }
            bases[plan_id] = {
                "research_id": plan_id,
                "kind": "challenge",
                "relation": "challenges",
                "related_research_ids": [product_id],
                "created_at": "2026-01-01T00:02:00+00:00",
                "status": "open",
                "metadata": {
                    "campaign_id": campaign_id,
                    "research_supervision": {
                        "source_receipts": [
                            {"result_research_id": product_id}
                        ]
                    },
                },
            }
            work_keys = {
                research_id: sha256_json(["work", research_id])
                for research_id in bases
            }
            workgroups = {
                work_key: [research_id]
                for research_id, work_key in work_keys.items()
            }
            root_work_key = work_keys[root_id]
            inspection = RoundInspectionContext(
                frontier_group_completions={
                    root_work_key: (
                        "pending",
                        None,
                        0,
                        sha256_json([]),
                    )
                },
                frontier_group_actions={
                    root_work_key: {
                        "next_action": "await_return",
                        "pending_reason": "supervision_round_in_flight",
                        "actionable_research_id": product_id,
                        "actionable_round_id": "round-" + "1" * 17,
                        "actionable_research_ids": [product_id],
                    }
                },
            )
            with patch.object(
                lifecycle,
                "_frontier_structural_state_for_inspection",
                return_value=(bases, {}, {}, workgroups, work_keys),
            ), patch.object(lifecycle, "frontier", return_value=[]):
                surface = lifecycle.frontier_decision_surface(
                    campaign_id=campaign_id,
                    _inspection_context=inspection,
                )

            goal = surface["goal_coverage"][0]
            self.assertEqual(goal["stale_active_head_research_ids"], [])
            self.assertEqual(
                goal["current_active_head_research_ids"], [root_id]
            )
            self.assertEqual(
                goal["uncheckpointed_terminal_successor_count"], 0
            )
            self.assertFalse(goal["checkpoint_refresh_recommended"])
            self.assertEqual(
                goal["active_head_actions"][0]["checkpoint_head_state"],
                "current_with_in_flight_supervision",
            )
            self.assertNotIn(
                "current_terminal_research_ids",
                goal["active_head_actions"][0],
            )
            self.assertFalse(surface["checkpoint_refresh"]["recommended"])

    def test_product_checkpoint_head_uses_bound_production_root_action(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            campaign_id = self._campaign(store)
            root = lifecycle.add_research(
                {
                    "kind": "direction",
                    "claim": "Produce one exact product.",
                    "campaign_id": campaign_id,
                },
                actor="main",
            )
            root_id = str(root["research_id"])
            product_id = "c" * 12
            plan_id = "d" * 12
            with store.v5_mutation_lock(command="campaign-navigation-checkpoint"):
                target_id = store.campaigns().target_add(
                    campaign_id,
                    {
                        "role": "research_goal",
                        "subject_kind": "research",
                        "subject_id": root_id,
                        "label": "Track the selected product",
                    },
                    actor="main",
                    fact_exists=lambda _fact_id: False,
                    research_exists=lambda item: item == root_id,
                )
                store.campaigns().update(
                    campaign_id,
                    {
                        "type": "note",
                        "payload": {
                            "kind": "campaign_frontier_head_checkpoint",
                            "generation": 1,
                            "supersedes_event_id": None,
                            "target_frontiers": [
                                {
                                    "target_id": target_id,
                                    "recovery_root_research_id": root_id,
                                    "active_heads": [
                                        {"research_id": product_id}
                                    ],
                                    "attained_checkpoints": [],
                                    "main_disposition": (
                                        "The product awaits supervision."
                                    ),
                                }
                            ],
                        },
                    },
                    actor="main",
                )

            bases = {
                item["research_id"]: item
                for item in lifecycle.research_envelopes()
            }
            provenance = {
                "adverse_assignment": False,
                "assignment_id": "a01-bound-product-prove",
                "round_id": "round-20260101T000000Z-12345678",
                "schema_version": 2,
                "task_card_sha256": "1" * 64,
                "work_mode": "prove",
            }
            bases[product_id] = {
                "research_id": product_id,
                "kind": "proof_attempt",
                "relation": "responds_to",
                "related_research_ids": [root_id],
                "created_at": "2026-01-01T00:01:00+00:00",
                "status": "open",
                "metadata": {
                    "campaign_id": campaign_id,
                    "assignment_provenance": provenance,
                    "task_binding": {
                        "assignment_id": provenance["assignment_id"],
                        "round_id": provenance["round_id"],
                        "task_card_sha256": provenance[
                            "task_card_sha256"
                        ],
                    },
                },
            }
            bases[plan_id] = {
                "research_id": plan_id,
                "kind": "challenge",
                "relation": "challenges",
                "related_research_ids": [product_id],
                "created_at": "2026-01-01T00:02:00+00:00",
                "status": "open",
                "metadata": {
                    "campaign_id": campaign_id,
                    "research_supervision": {
                        "source_receipts": [
                            {"result_research_id": product_id}
                        ]
                    },
                },
            }
            work_keys = {
                research_id: sha256_json(["work", research_id])
                for research_id in bases
            }
            workgroups = {
                work_key: [research_id]
                for research_id, work_key in work_keys.items()
            }
            root_work_key = work_keys[root_id]
            inspection = RoundInspectionContext(
                frontier_group_completions={
                    root_work_key: (
                        "pending",
                        None,
                        0,
                        sha256_json([]),
                    )
                },
                frontier_group_actions={
                    root_work_key: {
                        "next_action": "await_return",
                        "pending_reason": "supervision_round_in_flight",
                        "actionable_research_id": product_id,
                        "actionable_round_id": provenance["round_id"],
                        "actionable_research_ids": [product_id],
                    }
                },
            )
            with patch.object(
                lifecycle,
                "_frontier_structural_state_for_inspection",
                return_value=(bases, {}, {}, workgroups, work_keys),
            ), patch.object(lifecycle, "frontier", return_value=[]):
                surface = lifecycle.frontier_decision_surface(
                    campaign_id=campaign_id,
                    _inspection_context=inspection,
                )

            goal = surface["goal_coverage"][0]
            self.assertEqual(goal["next_action"], "await_return")
            self.assertEqual(goal["why_now"], "supervision_round_in_flight")
            self.assertEqual(
                goal["active_head_workflow_roots"],
                [
                    {
                        "active_head_research_id": product_id,
                        "workflow_root_research_id": root_id,
                        "selection_effect": "none",
                    }
                ],
            )
            self.assertEqual(
                goal["active_head_actions"][0][
                    "workflow_root_research_id"
                ],
                root_id,
            )
            self.assertFalse(goal["checkpoint_refresh_recommended"])

    def test_exact_legacy_repair_task_connects_later_cow_cycles(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            lifecycle = self._store(
                Path(temporary) / "project"
            ).v5_lifecycle()
            campaign_id = "campaign-" + "1" * 12
            root_id = "1" * 12
            product_one_id = "2" * 12
            plan_one_id = "3" * 12
            challenge_id = "4" * 12
            repair_task_id = "5" * 12
            product_two_id = "6" * 12
            plan_two_id = "7" * 12
            clean_review_id = "8" * 12
            bases = {
                root_id: {
                    "research_id": root_id,
                    "kind": "direction",
                    "relation": "supports",
                    "related_research_ids": [],
                    "source": "",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "metadata": {"campaign_id": campaign_id},
                },
                product_one_id: {
                    "research_id": product_one_id,
                    "kind": "proof_attempt",
                    "relation": "responds_to",
                    "related_research_ids": [root_id],
                    "source": "",
                    "created_at": "2026-01-01T00:01:00+00:00",
                    "metadata": {
                        "campaign_id": campaign_id,
                        "assignment_provenance": {
                            "adverse_assignment": False,
                            "work_mode": "prove",
                        },
                    },
                },
                plan_one_id: {
                    "research_id": plan_one_id,
                    "kind": "challenge",
                    "relation": "challenges",
                    "related_research_ids": [product_one_id],
                    "source": "",
                    "created_at": "2026-01-01T00:02:00+00:00",
                    "metadata": {
                        "campaign_id": campaign_id,
                        "research_supervision": {
                            "source_receipts": [
                                {"result_research_id": product_one_id}
                            ]
                        },
                    },
                },
                challenge_id: {
                    "research_id": challenge_id,
                    "kind": "challenge",
                    "relation": "responds_to",
                    "related_research_ids": [plan_one_id],
                    "source": "",
                    "created_at": "2026-01-01T00:03:00+00:00",
                    "metadata": {
                        "campaign_id": campaign_id,
                        "assignment_provenance": {
                            "adverse_assignment": True,
                            "work_mode": "refute",
                        },
                        "worker_outcome": "challenge",
                    },
                },
                repair_task_id: {
                    "research_id": repair_task_id,
                    "kind": "repair",
                    "relation": "repairs",
                    "related_research_ids": sorted(
                        {product_one_id, challenge_id}
                    ),
                    "source": (
                        f"research:{product_one_id}; "
                        f"research:{challenge_id}"
                    ),
                    "created_at": "2026-01-01T00:04:00+00:00",
                    "metadata": {"campaign_id": campaign_id},
                },
                product_two_id: {
                    "research_id": product_two_id,
                    "kind": "proof_attempt",
                    "relation": "responds_to",
                    "related_research_ids": [repair_task_id],
                    "source": "",
                    "created_at": "2026-01-01T00:05:00+00:00",
                    "metadata": {
                        "campaign_id": campaign_id,
                        "assignment_provenance": {
                            "adverse_assignment": False,
                            "work_mode": "prove",
                        },
                    },
                },
                plan_two_id: {
                    "research_id": plan_two_id,
                    "kind": "challenge",
                    "relation": "challenges",
                    "related_research_ids": [product_two_id],
                    "source": "",
                    "created_at": "2026-01-01T00:06:00+00:00",
                    "metadata": {
                        "campaign_id": campaign_id,
                        "research_supervision": {
                            "source_receipts": [
                                {"result_research_id": product_two_id}
                            ]
                        },
                    },
                },
                clean_review_id: {
                    "research_id": clean_review_id,
                    "kind": "insight",
                    "relation": "responds_to",
                    "related_research_ids": [plan_two_id],
                    "source": "",
                    "created_at": "2026-01-01T00:07:00+00:00",
                    "metadata": {
                        "campaign_id": campaign_id,
                        "assignment_provenance": {
                            "adverse_assignment": True,
                            "work_mode": "refute",
                        },
                        "worker_outcome": "evidence",
                    },
                },
            }

            index = lifecycle._campaign_semantic_successor_index(bases)
            summary, terminals = (
                lifecycle._campaign_attained_semantic_successor_summary(
                    attained_research_id=root_id,
                    campaign_id=campaign_id,
                    bases=bases,
                    index=index,
                )
            )
            self.assertEqual(terminals, [clean_review_id])
            self.assertIn(
                repair_task_id,
                summary["legacy_repair_task_research_ids"],
            )
            self.assertIn(
                product_two_id,
                summary["production_product_research_ids"],
            )
            self.assertEqual(summary["current_route_research_ids"], [])
            self.assertEqual(
                summary["terminal_evidence_research_ids"],
                [clean_review_id],
            )


if __name__ == "__main__":
    unittest.main()

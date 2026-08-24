from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from mathgraph.cli import build_parser, main as cli_main
from mathgraph.contracts import sha256_bytes
from mathgraph.store import MathGraphStore
from mathgraph.v5_lifecycle import V5_CAMPAIGN_SCOPE_REVISION


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
            self.assertEqual(
                surface["goal_coverage"][0],
                {
                    "target_id": target_id,
                    "label": "Resolve the exact goal-anchor branch",
                    "root_research_id": research_id,
                    "root_claim": "Investigate branch goal-anchor.",
                    "coverage_status": "research_open",
                    "work_completion_status": "pending",
                    "action_class": "research_development",
                    "next_action": "production",
                    "why_now": "no_ingested_production_product",
                    "actionable_research_id": research_id,
                    "actionable_round_id": None,
                    "actionable_research_ids": [research_id],
                },
            )
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

    def test_cross_campaign_explicit_selection_fails_before_round_write(self) -> None:
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
            rounds_before = sorted(path.name for path in store.rounds_dir.iterdir())

            with self.assertRaisesRegex(ValueError, f"Campaign {campaign_a}"):
                store.v5_lifecycle().create_round(
                    workers=2,
                    research_ids=[research_a, research_b],
                    campaign_id=campaign_a,
                )

            self.assertEqual(
                sorted(path.name for path in store.rounds_dir.iterdir()),
                rounds_before,
            )
            self.assertEqual(list(store.rounds_dir.rglob("campaign.snapshot.json")), [])

    def test_unscoped_round_preserves_passive_campaign_association(self) -> None:
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
            self.assertEqual(card["campaign_id"], campaign_id)
            self.assertNotIn("campaign_scope", card)
            self.assertNotIn("campaign_scope", planned)
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
            self.assertIn("explicitly scoped frozen Campaign", stderr.getvalue())

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

    def test_cli_research_goal_requires_the_exact_campaign_bound_root(
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
            self.assertNotEqual(code, 0)
            self.assertIn(
                "not an exact Campaign-bound Research root",
                stderr.getvalue(),
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

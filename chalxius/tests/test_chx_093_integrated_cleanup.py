from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import chx_ledger
from mathgraph.cli import build_parser
from mathgraph.roles import ALL_COMMANDS
from mathgraph.store import MathGraphStore


class IntegratedCleanup093Tests(unittest.TestCase):
    @staticmethod
    def _store(root: Path, project_id: str = "chx-093") -> MathGraphStore:
        store = MathGraphStore(root)
        store.initialize(
            project_id=project_id,
            title="CHX 0.9.3 integrated cleanup",
            workflow_evidence_version=5,
        )
        return store

    @staticmethod
    def _campaign(store: MathGraphStore, label: str = "campaign") -> str:
        with store.v5_mutation_lock(command="chx-093-campaign"):
            return store.campaigns().create(
                {
                    "name": label,
                    "objective": f"Resolve {label}.",
                    "source_claim_ids": [],
                    "targets": [],
                    "constraints": [],
                    "stop_conditions": [],
                    "value_definition": "Prefer exact progress.",
                },
                actor="main",
                fact_exists=lambda _fact_id: False,
            )

    def test_campaign_bound_research_publishes_exact_campaign(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            campaign_a = self._campaign(store, "a")
            record = lifecycle.add_research(
                {"claim": "One Campaign-bound Research root."},
                actor="main",
                campaign_id=campaign_a,
                reuse_unbound_main_semantics=True,
            )
            self.assertEqual(record["metadata"]["campaign_id"], campaign_a)

    def test_campaign_bound_research_predicate_false_stays_unbound(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            record = store.v5_lifecycle().add_research(
                {"claim": "One intentionally unbound Research root."},
                actor="main",
            )
            self.assertNotIn("campaign_id", record["metadata"])

    def test_campaign_bound_research_conflict_and_lock_drift_write_nothing(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            campaign_a = self._campaign(store, "a")
            campaign_b = self._campaign(store, "b")
            before = sorted(lifecycle.research_entries_dir.glob("*.json"))
            with self.assertRaisesRegex(ValueError, "different Campaigns"):
                lifecycle.add_research(
                    {
                        "claim": "Conflicting Campaign root.",
                        "campaign_id": campaign_b,
                    },
                    actor="main",
                    campaign_id=campaign_a,
                )
            self.assertEqual(
                before,
                sorted(lifecycle.research_entries_dir.glob("*.json")),
            )

            campaign_store = store.campaigns()
            real_status = campaign_store.status
            calls = 0

            def status_then_disappear(campaign_id: str):
                nonlocal calls
                calls += 1
                if calls == 1:
                    return real_status(campaign_id)
                raise ValueError("Campaign changed under write boundary")

            with patch.object(store, "campaigns", return_value=campaign_store), patch.object(
                campaign_store, "status", side_effect=status_then_disappear
            ):
                with self.assertRaisesRegex(ValueError, "write boundary"):
                    lifecycle.add_research(
                        {"claim": "Must fail before immutable publication."},
                        actor="main",
                        campaign_id=campaign_a,
                    )
            self.assertEqual(
                before,
                sorted(lifecycle.research_entries_dir.glob("*.json")),
            )

    def test_frontier_exact_argv_and_round_selection_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            campaign_id = self._campaign(store)
            lifecycle = store.v5_lifecycle()
            research = lifecycle.add_research(
                {"claim": "Plan this exact Campaign head."},
                actor="main",
                campaign_id=campaign_id,
            )
            row = lifecycle.frontier(limit=1, campaign_id=campaign_id)[0]
            expected = [
                "plan-round",
                "--workers",
                "1",
                "--mode",
                "auto",
                "--campaign",
                campaign_id,
                "--memory-id",
                research["research_id"],
            ]
            self.assertEqual(row["plan_round_argv"], expected)
            status = lifecycle.create_production_round(
                workers=1,
                research_ids=[research["research_id"]],
                campaign_id=campaign_id,
            )
            receipt = status["selection_receipt"]
            self.assertEqual(receipt["selection_source"], "explicit_research_ids")
            self.assertEqual(
                receipt["selected_research_ids"], [research["research_id"]]
            )
            self.assertEqual(receipt["exact_replay_argv"], expected)

        for campaign_scoped, expected_source in (
            (True, "campaign_frontier"),
            (False, "global_frontier"),
        ):
            with self.subTest(selection_source=expected_source), tempfile.TemporaryDirectory() as temporary:
                store = self._store(
                    Path(temporary) / "project",
                    project_id=f"chx-093-{expected_source}",
                )
                campaign_id = self._campaign(store) if campaign_scoped else None
                store.v5_lifecycle().add_research(
                    {
                        "claim": f"Generic {expected_source} head.",
                        **(
                            {"campaign_id": campaign_id}
                            if campaign_id is not None
                            else {}
                        ),
                    },
                    actor="main",
                )
                status = store.v5_lifecycle().create_production_round(
                    workers=1,
                    campaign_id=campaign_id,
                )
                self.assertEqual(
                    status["selection_receipt"]["selection_source"],
                    expected_source,
                )

    def test_semantic_attention_disposition_is_cow_and_stops_repeat_work(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            lifecycle = self._store(
                Path(temporary) / "project"
            ).v5_lifecycle()
            target = lifecycle.add_research(
                {"claim": "A reviewable Research product."}, actor="main"
            )
            review = lifecycle.add_research(
                {"claim": "An accepted equivalent independent review."},
                actor="reviewer",
            )
            with self.assertRaisesRegex(ValueError, "exact basis"):
                lifecycle.update_research(
                    target["research_id"],
                    status="equivalent_review_accepted",
                    actor="main",
                    note="Accepted.",
                )
            disposition = lifecycle.update_research(
                target["research_id"],
                status="equivalent_review_accepted",
                actor="main",
                note="The independent review covers this exact product.",
                attention_basis_research_ids=[review["research_id"]],
            )
            self.assertEqual(
                disposition["metadata"]["attention_disposition"],
                "equivalent_review_accepted",
            )
            history = lifecycle.frontier(limit=10, include_history=True)
            by_id = {item["research_id"]: item for item in history}
            self.assertEqual(
                by_id[target["research_id"]]["next_attention"], "none"
            )
            self.assertEqual(
                by_id[target["research_id"]]["disposition"],
                "equivalent_review_accepted",
            )

    def test_retired_brave_future_has_no_public_command_or_alias(self) -> None:
        parser = build_parser()
        subparsers = next(
            action.choices
            for action in parser._actions
            if isinstance(getattr(action, "choices", None), dict)
            and "frontier" in action.choices
        )
        retired = {
            "brave-future-enable",
            "research-goal-intake",
            "brave-future-status",
            "brave-future-audit",
            "campaign-reassess",
            "campaign-reassess-decide",
            "brave-future-disable",
        }
        self.assertTrue(retired.isdisjoint(subparsers))
        self.assertTrue(retired.isdisjoint(ALL_COMMANDS))
        frontier = subparsers["frontier"]
        options = {
            option
            for action in frontier._actions
            for option in action.option_strings
        }
        self.assertNotIn("--brave-future", options)
        self.assertNotIn("--view", options)

    def test_chx_ledger_liveness_is_explicit_bounded_and_cow(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            runs = []
            for index in range(10):
                started = chx_ledger.start_ledger(
                    project_root=project,
                    task=f"Historical task {index}",
                    run_id=f"run-chx093-{index:03d}",
                )
                runs.append(started["run_id"])
            orphaned = chx_ledger.inventory_project_ledgers(project)
            activity = orphaned["ledger_activity"]
            self.assertEqual(activity["open_current_count"], 0)
            self.assertEqual(activity["open_orphaned_count"], 10)
            self.assertEqual(len(activity["open_orphaned"]), 8)
            self.assertTrue(activity["open_orphaned_truncated"])

            current = chx_ledger.inventory_project_ledgers(
                project,
                current_run_ids=[runs[-1]],
            )
            self.assertEqual(current["active_run_ids"], [runs[-1]])
            self.assertEqual(
                current["ledger_activity"]["open_current_count"], 1
            )
            first = chx_ledger.record_ledger_disposition(
                project,
                run_id=runs[0],
                status="administratively_complete",
                reason="The historical task finished outside the old close ceremony.",
            )
            retry = chx_ledger.record_ledger_disposition(
                project,
                run_id=runs[0],
                status="administratively_complete",
                reason="The historical task finished outside the old close ceremony.",
            )
            self.assertEqual(first["ledger_disposition_id"], retry["ledger_disposition_id"])
            self.assertEqual(retry["status"], "already_recorded")
            with self.assertRaisesRegex(ValueError, "different administrative"):
                chx_ledger.record_ledger_disposition(
                    project,
                    run_id=runs[0],
                    status="abandoned",
                    reason="Conflicting terminal meaning.",
                )
            projected = chx_ledger.inventory_project_ledgers(
                project,
                current_run_ids=[runs[-1]],
            )
            self.assertEqual(
                projected["ledger_activity"]["open_stale_count"], 1
            )
            self.assertEqual(
                projected["ledger_activity"]["open_orphaned_count"], 8
            )
            self.assertEqual(projected["counts"]["active_ledgers"], 1)
            self.assertEqual(projected["counts"]["raw_open_ledgers"], 10)


if __name__ == "__main__":
    unittest.main()

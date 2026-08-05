from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mathgraph.brave_future import (
    BF_FRONTIER_PROJECTION_LEGACY_REVISION,
    BF_FRONTIER_PROJECTION_REVISION,
    BF_GOAL_INTAKE_REVISION,
    BF_MAX_OBJECT_BYTES,
    BF_PROJECTION_MEMBER_LIMIT,
    _PROJECTION_SEMANTIC_FIELDS_V1,
    _sealed_record,
    _validate_frontier_projection,
)
from mathgraph.goal_intake import GoalIntakeTransactionStore
from mathgraph.store import MathGraphStore


class GoalIntakeTransactionTests(unittest.TestCase):
    @staticmethod
    def _store(root: Path) -> MathGraphStore:
        store = MathGraphStore(root)
        store.initialize(
            project_id="goal-intake-transaction-fixture",
            title="Goal intake transaction fixture",
            workflow_evidence_version=5,
            reasoning_mode="auto",
        )
        return store

    @staticmethod
    def _goal(label: str = "Recover one exact research objective.") -> dict[str, str]:
        return {"revision": BF_GOAL_INTAKE_REVISION, "objective": label}

    @staticmethod
    def _inventory(root: Path) -> dict[str, str]:
        return {
            path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*")
            if path.is_file()
        }

    def test_every_published_checkpoint_is_retryable_and_preterminal_is_hidden(self) -> None:
        checkpoints = [
            "intent",
            "effect:activation",
            "effect:campaign",
            "effect:frontier_projection",
            "effect:planning_snapshot",
            "side_effect:campaign",
            "side_effect:activation",
            "effect_receipt:activation",
            "effect_receipt:campaign",
            "effect_receipt:frontier_projection",
            "effect_receipt:planning_snapshot",
            "terminal",
        ]
        for checkpoint in checkpoints:
            with self.subTest(checkpoint=checkpoint), tempfile.TemporaryDirectory() as temporary:
                store = self._store(Path(temporary) / "project")

                def interrupt(name: str) -> None:
                    if name == checkpoint:
                        raise RuntimeError(f"injected intake interruption at {name}")

                with mock.patch.object(
                    GoalIntakeTransactionStore,
                    "_checkpoint",
                    side_effect=interrupt,
                ):
                    with self.assertRaisesRegex(RuntimeError, "injected intake interruption"):
                        store.brave_future().intake_research_goal(
                            goal_input=self._goal(), actor="user"
                        )

                visible = store.campaigns().campaign_ids()
                if checkpoint == "terminal":
                    self.assertEqual(len(visible), 1)
                    self.assertTrue(store.brave_future().status(visible[0])["enabled"])
                else:
                    self.assertEqual(visible, [])
                    hidden = sorted(store.campaigns().root.glob("campaign-*"))
                    if hidden:
                        with self.assertRaises(KeyError):
                            store.campaigns().status(hidden[0].name)
                    before_reads = self._inventory(store.root)
                    self.assertEqual(store.campaigns().campaign_ids(), [])
                    store.brave_future().audit()
                    store.audit()
                    self.assertEqual(before_reads, self._inventory(store.root))

                recovered = store.brave_future().intake_research_goal(
                    goal_input=self._goal(), actor="user"
                )
                self.assertTrue(
                    store.brave_future().validate_intake_receipt(
                        recovered["intake_token"]
                    )["validated"]
                )
                self.assertEqual(
                    store.campaigns().campaign_ids(), [recovered["campaign_id"]]
                )
                self.assertTrue(
                    store.brave_future().status(recovered["campaign_id"])["enabled"]
                )
                after_recovery = self._inventory(store.root)
                repeated = store.brave_future().intake_research_goal(
                    goal_input=self._goal(), actor="another-reader"
                )
                self.assertEqual(repeated["intake_token"], recovered["intake_token"])
                self.assertEqual(after_recovery, self._inventory(store.root))
                self.assertEqual(store.fact_ids(), [])
                self.assertEqual(store.v5_lifecycle().research_records(), [])
                self.assertEqual(list(store.rounds_dir.iterdir()), [])

    def test_large_paper_and_workflow_use_bounded_owner_heads(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            for bulk in (
                store.paper_logic().artifacts_dir,
                store.adverse_routes().cases_dir,
            ):
                bulk.mkdir(parents=True, exist_ok=True)
                for index in range(1200):
                    (bulk / f"member-{index:04d}.json").write_text(
                        json.dumps({"index": index, "payload": "x" * 80}),
                        encoding="utf-8",
                    )
            result = store.brave_future().intake_research_goal(
                goal_input=self._goal("Bound a large Paper/workflow projection."),
                actor="user",
            )
            snapshot = result["bf1"]["planning_snapshot"]
            projection = result["bf1"]["frontier_projection"]
            self.assertLessEqual(
                len(json.dumps(snapshot, ensure_ascii=False, sort_keys=True).encode()),
                BF_MAX_OBJECT_BYTES,
            )
            self.assertLessEqual(
                len(json.dumps(projection, ensure_ascii=False, sort_keys=True).encode()),
                BF_MAX_OBJECT_BYTES,
            )
            encoded_heads = json.dumps(snapshot["workflow_heads"], sort_keys=True)
            self.assertNotIn("member-0000.json", encoded_heads)
            self.assertIn("head_sha256", encoded_heads)

    def test_full_effect_budget_fails_before_any_intake_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            before = self._inventory(store.root)
            with mock.patch("mathgraph.brave_future.BF_MAX_OBJECT_BYTES", 128):
                with self.assertRaisesRegex(ValueError, "bounded-object limit"):
                    store.brave_future().intake_research_goal(
                        goal_input=self._goal("Reject an over-budget BF-1 object."),
                        actor="user",
                    )
            self.assertEqual(before, self._inventory(store.root))
            self.assertEqual(store.campaigns().campaign_ids(), [])

    def test_frontier_limit_fails_closed_without_projection_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            manager = store.brave_future()
            intake = manager.intake_research_goal(
                goal_input=self._goal("Bound every BF-1 window."),
                actor="user",
            )
            before = self._inventory(store.root)
            with self.assertRaisesRegex(ValueError, "must not exceed 256"):
                manager.frontier(
                    campaign_id=intake["campaign_id"],
                    limit=BF_PROJECTION_MEMBER_LIMIT + 1,
                )
            self.assertEqual(before, self._inventory(store.root))

    def test_large_campaign_projection_is_a_bounded_local_window(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            manager = store.brave_future()
            goal = self._goal("Project a large Campaign through one bounded BF-1 window.")
            first = manager.intake_research_goal(goal_input=goal, actor="user")
            for index in range(1400):
                store.v5_lifecycle().add_research(
                    {
                        "kind": "direction",
                        "status": "open",
                        "claim": f"Bounded Campaign node {index:04d}.",
                        "content": "One independent advisory route.",
                        "rationale": "Large-project BF-1 fixture.",
                        "campaign_id": first["campaign_id"],
                    },
                    actor="main",
                )
            refreshed = manager.intake_research_goal(
                goal_input=goal,
                actor="user",
                limit=10,
            )
            snapshot = refreshed["bf1"]["planning_snapshot"]
            projection = refreshed["bf1"]["frontier_projection"]
            self.assertEqual(snapshot["research_manifest"]["entry_count"], 1400)
            self.assertEqual(len(projection["entries"]), 10)
            self.assertEqual(projection["omitted_count"], 1390)
            self.assertEqual(
                projection["revision"], BF_FRONTIER_PROJECTION_REVISION
            )
            self.assertEqual(len(projection["eligible_manifest_window"]), 256)
            self.assertEqual(projection["eligible_manifest_window_limit"], 256)
            self.assertEqual(projection["eligible_manifest_total_count"], 1400)
            self.assertLessEqual(
                len(json.dumps(projection, ensure_ascii=False, sort_keys=True).encode()),
                BF_MAX_OBJECT_BYTES,
            )

            legacy_semantic = {
                key: projection[key]
                for key in _PROJECTION_SEMANTIC_FIELDS_V1
                if key
                not in {
                    "revision",
                    "full_eligible_manifest",
                    "full_eligible_manifest_sha256",
                }
            }
            legacy_semantic.update(
                {
                    "revision": BF_FRONTIER_PROJECTION_LEGACY_REVISION,
                    "full_eligible_manifest": projection[
                        "eligible_manifest_window"
                    ],
                    "full_eligible_manifest_sha256": projection[
                        "eligible_manifest_sha256"
                    ],
                }
            )
            legacy = _sealed_record(
                legacy_semantic,
                id_key="projection_id",
                prefix="bfp-",
                created_at=projection["created_at"],
            )
            self.assertEqual(
                _validate_frontier_projection(legacy)["revision"],
                BF_FRONTIER_PROJECTION_LEGACY_REVISION,
            )

    def test_receipt_validation_and_status_are_pure_reads(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            result = store.brave_future().intake_research_goal(
                goal_input=self._goal("Bind a durable future-round intake token."),
                actor="user",
            )
            before = self._inventory(store.root)
            receipt = store.brave_future().validate_intake_receipt(
                result["intake_token"]
            )
            self.assertTrue(receipt["validated"])
            self.assertEqual(receipt["truth_effect"], "none")
            self.assertEqual(receipt["fact_admission_effect"], "none")
            self.assertTrue(store.brave_future().status(result["campaign_id"])["enabled"])
            self.assertTrue(store.brave_future().audit()["ok"])
            self.assertTrue(store.audit().current_ok)
            self.assertEqual(before, self._inventory(store.root))


if __name__ == "__main__":
    unittest.main()

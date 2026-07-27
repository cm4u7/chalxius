from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from mathgraph.orchestrator import create_round
from mathgraph.store import MathGraphStore


HOST_TASK_SCOPE_ID = "hosttask-" + "a" * 32


class V4ReleaseGovernanceClosureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = MathGraphStore(self.root)
        self.store.initialize(
            project_id="v4-release-governance-closure",
            title="V4 release governance closure",
            workflow_evidence_version=4,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _campaign_payload(
        name: str,
        *,
        source_claim_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "name": name,
            "objective": f"Resolve the {name} objective.",
            "source_claim_ids": list(source_claim_ids or []),
            "targets": [],
            "constraints": [],
            "stop_conditions": ["Stop at a decisive result."],
            "value_definition": "Prefer status-changing work.",
        }

    def _memory(self, label: str, *, campaign_id: str) -> str:
        return self.store.memory_add(
            {
                "kind": "computation",
                "claim": f"Run the {label} scoped computation.",
                "rationale": "Governance-closure fixture.",
                "suggested_actions": ["compute"],
                "campaign_id": campaign_id,
            },
            actor="main",
        )

    @staticmethod
    def _task_card(planned: dict[str, Any]) -> dict[str, Any]:
        return json.loads(
            Path(
                planned["assignments"][0]["task_card_path"]
            ).read_text(encoding="utf-8")
        )

    @staticmethod
    def _observation(
        observation_id: str,
        *,
        end_ns: int,
    ) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "observation_id": observation_id,
            "measurement_method": (
                "host_monotonic_active_intervals_union"
            ),
            "active_intervals": [
                {
                    "clock_epoch": "host-epoch-1",
                    "lease_id": "host-task-root",
                    "start_ns": 0,
                    "end_ns": end_ns,
                }
            ],
            "actual_resources": {
                "cpu_seconds": "host-observed",
                "peak_rss_bytes": "host-observed",
            },
            "experimental_nature": (
                "Exploratory mathematical computation."
            ),
            "progress": "The scoped task remains active.",
            "latest_checkpoint": "",
            "importance_and_continuation_value": (
                "The result tests a release-governance boundary."
            ),
            "stopping_impact": (
                "Stopping preserves only completed checkpoints."
            ),
        }

    @staticmethod
    def _tree_inventory(root: Path) -> dict[str, str]:
        inventory: dict[str, str] = {}
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                inventory[relative] = "symlink"
            elif path.is_dir():
                inventory[relative] = "directory"
            elif path.is_file():
                inventory[relative] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
        return inventory

    def _registered_claim(self) -> str:
        registry = self.store.claims()
        convention_id = registry.add_convention(
            {
                "theory": "release governance",
                "source_version": "arXiv:2607.00001v1",
                "source_artifact_sha256": "a" * 64,
                "authority": "literal_source",
                "dimensions": {
                    "normalization": "governance-normalized",
                },
            },
            actor="operator",
        )
        return registry.add_claim(
            {
                "kind": "published_literal",
                "title": "Release-governance literal claim",
                "statement": (
                    "For every admissible object, the closure property "
                    "holds."
                ),
                "source": {
                    "title": "Release-governance source",
                    "version": "arXiv:2607.00001v1",
                    "artifact_sha256": "b" * 64,
                    "locator": "Theorem 1",
                    "retrieved_at": "2026-07-25",
                },
                "convention_profile_id": convention_id,
                "authority": "literal_source",
            },
            actor="operator",
        )

    def test_same_host_task_scope_shares_clock_across_campaigns_once(
        self,
    ) -> None:
        campaigns = self.store.campaigns()
        first_campaign_id = campaigns.active()
        assert first_campaign_id is not None
        first_round = create_round(
            self.store,
            workers=1,
            mode="compute",
            memory_ids=[
                self._memory(
                    "first-campaign",
                    campaign_id=first_campaign_id,
                )
            ],
            host_task_scope_id=HOST_TASK_SCOPE_ID,
        )
        first_card = self._task_card(first_round)

        second_campaign_id = campaigns.create(
            self._campaign_payload("second-campaign"),
            actor="operator",
        )
        campaigns.activate(second_campaign_id, actor="operator")
        second_round = create_round(
            self.store,
            workers=1,
            mode="compute",
            memory_ids=[
                self._memory(
                    "second-campaign",
                    campaign_id=second_campaign_id,
                )
            ],
            host_task_scope_id=HOST_TASK_SCOPE_ID,
        )
        second_card = self._task_card(second_round)

        manager = self.store.experiments()
        self.assertNotEqual(
            first_card["campaign_id"],
            second_card["campaign_id"],
        )
        self.assertEqual(
            first_card["host_task_scope_id"],
            second_card["host_task_scope_id"],
        )
        self.assertEqual(
            manager.governance_task_id(first_card),
            manager.governance_task_id(second_card),
        )

        exactly = manager.observe(
            task_card=first_card,
            actor_role="main",
            payload=self._observation(
                "obs-cross-campaign-exact",
                end_ns=1_200_000_000_000,
            ),
        )
        self.assertEqual(exactly["event"], "observation")
        self.assertEqual(exactly["state"], "pre_threshold")
        self.assertEqual(
            exactly["actual_cumulative_task_seconds"],
            1200,
        )

        crossed_payload = self._observation(
            "obs-cross-campaign-plus-one",
            end_ns=1_200_000_000_001,
        )
        crossed = manager.observe(
            task_card=second_card,
            actor_role="operator",
            payload=crossed_payload,
        )
        self.assertEqual(crossed["event"], "continuation_notice")
        self.assertEqual(crossed["state"], "notice_issued")
        self.assertAlmostEqual(
            crossed["actual_cumulative_task_seconds"],
            1200.000000001,
        )

        replayed = manager.observe(
            task_card=second_card,
            actor_role="main",
            payload=crossed_payload,
        )
        self.assertEqual(replayed["event_id"], crossed["event_id"])
        self.assertEqual(replayed["notice_id"], crossed["notice_id"])
        events = manager._read_jsonl(
            manager._governance_events_path(second_card)
        )
        self.assertEqual(
            sum(
                event["event"] == "continuation_notice"
                for event in events
            ),
            1,
        )

    def test_plan_round_without_host_task_scope_fails_before_write(
        self,
    ) -> None:
        campaign_id = self.store.campaigns().active()
        assert campaign_id is not None
        memory_id = self._memory(
            "missing-host-scope",
            campaign_id=campaign_id,
        )
        before = self._tree_inventory(self.store.rounds_dir)
        with patch.dict(
            os.environ,
            {
                "MATHGRAPH_HOST_TASK_SCOPE_ID": "",
                "CODEX_THREAD_ID": "",
            },
        ):
            with self.assertRaisesRegex(
                ValueError,
                (
                    "new V4 planning requires a stable host task scope "
                    "via --host-task-scope-id, "
                    "MATHGRAPH_HOST_TASK_SCOPE_ID, or CODEX_THREAD_ID"
                ),
            ):
                create_round(
                    self.store,
                    workers=1,
                    mode="compute",
                    memory_ids=[memory_id],
                )
        self.assertEqual(
            before,
            self._tree_inventory(self.store.rounds_dir),
        )

    def test_campaign_create_rejects_dangling_claim_before_write(
        self,
    ) -> None:
        campaigns = self.store.campaigns()
        dangling_claim_id = "claim-" + "0" * 16
        before = self._tree_inventory(campaigns.root)
        with self.assertRaisesRegex(
            ValueError,
            (
                "campaign source claim is not registered: "
                f"{dangling_claim_id}"
            ),
        ):
            campaigns.create(
                self._campaign_payload(
                    "dangling-claim",
                    source_claim_ids=[dangling_claim_id],
                ),
                actor="operator",
            )
        self.assertEqual(before, self._tree_inventory(campaigns.root))

    def test_audit_rejects_campaign_whose_registered_claim_was_removed(
        self,
    ) -> None:
        claim_id = self._registered_claim()
        campaign_id = self.store.campaigns().create(
            self._campaign_payload(
                "removed-claim",
                source_claim_ids=[claim_id],
            ),
            actor="operator",
        )
        claim_path = (
            self.store.claims().claims_dir / f"{claim_id}.json"
        )
        self.assertTrue(claim_path.is_file())
        claim_path.unlink()

        report = self.store.audit()
        self.assertFalse(report.current_ok)
        self.assertTrue(
            any(
                campaign_id in error
                and claim_id in error
                and "source claim" in error
                for error in report.errors
            ),
            report.errors,
        )


if __name__ == "__main__":
    unittest.main()

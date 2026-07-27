from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mathgraph.computations import (
    CONTINUATION_THRESHOLD_NS,
    ExperimentManager,
    validate_experiment_final_receipt,
)
from mathgraph.orchestrator import create_round
from mathgraph.roles import allowed_commands, allowed_commands_for_workflow
from mathgraph.store import MathGraphStore


class V4ExperimentGovernanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.store = MathGraphStore(self.root)
        self.store.initialize(
            project_id="v4-governance",
            title="V4 governance",
            workflow_evidence_version=4,
        )
        memory_id = self.store.memory_add(
            {
                "kind": "computation",
                "claim": "Run a staged toy experiment.",
                "rationale": "Governance fixture",
                "suggested_actions": ["compute"],
            },
            actor="main",
        )
        planned = create_round(
            self.store,
            workers=1,
            memory_ids=[memory_id],
        )
        assignment = planned["assignments"][0]
        self.card = json.loads(Path(assignment["task_card_path"]).read_text())
        self.manager = self.store.experiments()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _manifest(objective: str = "one") -> dict:
        return {
            "objective": f"Compute exact toy result {objective}.",
            "command": ["python3", "run.py", objective],
            "environment": {
                "implementation": "CPython",
                "version": "3",
            },
            "cost_model": {
                "dominant_operation": "integer addition",
                "estimated_cost": 10**9,
                "expected_memory": "unknown",
                "parallelism": "host-selected",
                "complexity_model": {
                    "parameters": {"objective": objective},
                    "asymptotic_time": "unknown",
                    "asymptotic_space": "unknown",
                    "estimated_operation_count": None,
                    "estimate_basis": "advisory only",
                    "intermediate_object_estimates": [],
                },
            },
            "stages": ["exact"],
            "escalation_ladder": [
                {
                    "stage_id": "exact",
                    "arithmetic": "integer",
                    "advance_condition": "exact output exists",
                }
            ],
            "checkpoint_policy": "stage boundary",
            "resume_contract": {
                "checkpoint_format": "json",
                "resume_command": ["python3", "run.py", "--resume"],
                "compatibility_fields": ["python"],
                "deterministic_replay_required": True,
            },
            "truth_status": "exploration",
        }

    @staticmethod
    def _observation(
        observation_id: str,
        intervals: list[dict],
    ) -> dict:
        return {
            "schema_version": 1,
            "observation_id": observation_id,
            "measurement_method": "host_monotonic_active_intervals_union",
            "active_intervals": intervals,
            "actual_resources": {
                "cpu_seconds": "host-observed",
                "peak_rss_bytes": "host-observed",
            },
            "experimental_nature": "Exploratory mathematical computation.",
            "progress": "Exact stage is active.",
            "latest_checkpoint": "",
            "importance_and_continuation_value": (
                "The result tests a load-bearing obstruction."
            ),
            "stopping_impact": "Stopping preserves only completed checkpoints.",
        }

    @staticmethod
    def _interval(
        lease_id: str,
        start_ns: int,
        end_ns: int,
        *,
        epoch: str = "host-epoch-1",
    ) -> dict:
        return {
            "clock_epoch": epoch,
            "lease_id": lease_id,
            "start_ns": start_ns,
            "end_ns": end_ns,
        }

    def _complete_stage(self, experiment_id: str) -> None:
        self.manager.event(
            task_card=self.card,
            experiment_id=experiment_id,
            payload={
                "event": "stage_completed",
                "stage": "exact",
                "advance_condition_disposition": "exact output exists",
                "actual_intermediate_object_counts": [
                    {"object_kind": "integer", "count": 1}
                ],
            },
        )

    def test_strict_crossing_notifies_and_allows_finalize_without_decision(
        self,
    ) -> None:
        started = self.manager.start(
            task_card=self.card,
            manifest=self._manifest(),
        )
        self._complete_stage(started["experiment_id"])
        exactly = self.manager.observe(
            task_card=self.card,
            actor_role="main",
            payload=self._observation(
                "obs-exact",
                [self._interval("root", 0, CONTINUATION_THRESHOLD_NS)],
            ),
        )
        self.assertEqual(exactly["state"], "pre_threshold")
        self.assertEqual(exactly["event"], "observation")

        crossed_payload = self._observation(
            "obs-crossed",
            [
                self._interval(
                    "root",
                    0,
                    CONTINUATION_THRESHOLD_NS + 1,
                )
            ],
        )
        crossed = self.manager.observe(
            task_card=self.card,
            actor_role="operator",
            payload=crossed_payload,
        )
        self.assertEqual(crossed["state"], "notice_issued")
        self.assertEqual(crossed["event"], "continuation_notice")
        repeated = self.manager.observe(
            task_card=self.card,
            actor_role="main",
            payload=crossed_payload,
        )
        self.assertEqual(repeated["event_id"], crossed["event_id"])
        self.assertEqual(repeated["notice_id"], crossed["notice_id"])
        self.assertEqual(repeated["state"], "notice_issued")
        continued_observation = self.manager.observe(
            task_card=self.card,
            actor_role="main",
            payload=self._observation(
                "obs-after-notice",
                [
                    self._interval(
                        "root",
                        0,
                        CONTINUATION_THRESHOLD_NS + 2,
                    )
                ],
            ),
        )
        self.assertEqual(continued_observation["event"], "observation")
        self.assertEqual(continued_observation["state"], "notice_issued")
        second = self.manager.start(
            task_card=self.card,
            manifest=self._manifest("second"),
        )
        self.assertEqual(second["status"], "started")
        with self.assertRaisesRegex(ValueError, "main or operator"):
            self.manager.decision(
                task_card=self.card,
                actor_role="worker",
                payload={
                    "schema_version": 1,
                    "decision_id": "decision-1",
                    "notice_id": crossed["notice_id"],
                    "decision": "continue",
                    "authority_kind": "user",
                    "authority_reference": "host-ui-receipt-1",
                    "reason": "Continue because the obstruction is decisive.",
                },
            )

        directory = Path(started["directory"])
        (directory / "result.txt").write_text("2\n", encoding="utf-8")
        receipt = self.manager.finalize(
            task_card=self.card,
            experiment_id=started["experiment_id"],
            selected_paths=["result.txt"],
        )
        self.assertEqual(receipt["schema_version"], 3)
        self.assertEqual(receipt["governance_state"], "notice_issued")
        self.assertGreaterEqual(receipt["governance_event_count"], 3)
        validate_experiment_final_receipt(
            project_root=self.root,
            task_card=self.card,
            receipt_path=directory / "final_receipt.json",
        )
        acknowledgement = self.manager.decision(
            task_card=self.card,
            actor_role="main",
            payload={
                "schema_version": 1,
                "decision_id": "decision-1",
                "notice_id": crossed["notice_id"],
                "decision": "continue",
                "authority_kind": "user",
                "authority_reference": "host-ui-receipt-1",
                "reason": "The notice was received; work may continue.",
            },
        )
        self.assertEqual(acknowledgement["state"], "acknowledged")

    def test_parallel_intervals_are_unioned_not_summed(self) -> None:
        observed = self.manager.observe(
            task_card=self.card,
            actor_role="main",
            payload=self._observation(
                "obs-overlap",
                [
                    self._interval("worker-a", 0, 900_000_000_000),
                    self._interval(
                        "worker-b",
                        300_000_000_000,
                        1_000_000_000_000,
                    ),
                ],
            ),
        )
        self.assertEqual(observed["actual_cumulative_task_seconds"], 1000)
        self.assertEqual(observed["state"], "pre_threshold")

    def test_host_task_clock_unions_distinct_worker_memories_and_rounds(
        self,
    ) -> None:
        first = self.manager.observe(
            task_card=self.card,
            actor_role="main",
            payload=self._observation(
                "obs-first-worker",
                [self._interval("worker-a", 0, 700_000_000_000)],
            ),
        )
        self.assertEqual(first["state"], "pre_threshold")

        second_memory_id = self.store.memory_add(
            {
                "kind": "computation",
                "claim": "Run the complementary staged experiment.",
                "rationale": "Exercise one campaign-scoped task clock.",
                "suggested_actions": ["compute"],
            },
            actor="main",
        )
        second_round = create_round(
            self.store,
            workers=1,
            memory_ids=[second_memory_id],
        )
        second_card = json.loads(
            Path(
                second_round["assignments"][0]["task_card_path"]
            ).read_text()
        )
        self.assertNotEqual(
            self.card["memory_id"],
            second_card["memory_id"],
        )
        self.assertNotEqual(
            self.card["round_id"],
            second_card["round_id"],
        )
        self.assertEqual(
            self.manager.governance_task_id(self.card),
            self.manager.governance_task_id(second_card),
        )

        crossed = self.manager.observe(
            task_card=second_card,
            actor_role="operator",
            payload=self._observation(
                "obs-second-worker",
                [
                    self._interval(
                        "worker-a",
                        0,
                        700_000_000_000,
                    ),
                    self._interval(
                        "worker-b",
                        600_000_000_000,
                        CONTINUATION_THRESHOLD_NS + 1,
                    ),
                ],
            ),
        )
        self.assertEqual(crossed["event"], "continuation_notice")
        self.assertEqual(crossed["state"], "notice_issued")
        self.assertAlmostEqual(
            crossed["actual_cumulative_task_seconds"],
            1200.000000001,
        )

    def test_same_campaign_distinct_host_tasks_have_independent_clocks(
        self,
    ) -> None:
        first = self.manager.observe(
            task_card=self.card,
            actor_role="main",
            payload=self._observation(
                "obs-host-task-one",
                [self._interval("worker-a", 0, 700_000_000_000)],
            ),
        )
        self.assertEqual(first["state"], "pre_threshold")
        second_memory_id = self.store.memory_add(
            {
                "kind": "computation",
                "claim": "Run work in another host task.",
                "suggested_actions": ["compute"],
            },
            actor="main",
        )
        second_round = create_round(
            self.store,
            workers=1,
            memory_ids=[second_memory_id],
            host_task_scope_id="independent-host-task",
        )
        second_card = json.loads(
            Path(
                second_round["assignments"][0]["task_card_path"]
            ).read_text()
        )
        self.assertNotEqual(
            self.manager.governance_task_id(self.card),
            self.manager.governance_task_id(second_card),
        )
        second = self.manager.observe(
            task_card=second_card,
            actor_role="operator",
            payload=self._observation(
                "obs-host-task-two",
                [self._interval("worker-b", 0, 700_000_000_000)],
            ),
        )
        self.assertEqual(second["state"], "pre_threshold")
        self.assertEqual(second["actual_cumulative_task_seconds"], 700)

    def test_new_experiment_id_cannot_reset_pending_task_governance(self) -> None:
        self.manager.start(task_card=self.card, manifest=self._manifest("first"))
        notice = self.manager.observe(
            task_card=self.card,
            actor_role="main",
            payload=self._observation(
                "obs-over",
                [
                    self._interval(
                        "root",
                        0,
                        CONTINUATION_THRESHOLD_NS + 10,
                    )
                ],
            ),
        )
        self.assertEqual(notice["status"], "notice_issued")
        renamed = self.manager.start(
            task_card=self.card,
            manifest=self._manifest("renamed"),
        )
        self.assertEqual(renamed["status"], "started")

    def test_worker_heartbeat_is_telemetry_not_the_notice_clock(self) -> None:
        started = self.manager.start(
            task_card=self.card,
            manifest=self._manifest(),
        )
        heartbeat = {
            "event": "heartbeat",
            "timestamp": "2026-07-25T00:00:00Z",
            "stage": "exact",
            "completed_units": 1,
            "total_units_or_null": 2,
            "cpu_seconds": 10,
            "wall_seconds": 1201,
            "rss_bytes": 1024,
            "latest_check": "worker-local telemetry",
        }
        self.manager.event(
            task_card=self.card,
            experiment_id=started["experiment_id"],
            payload=heartbeat,
        )
        status = self.manager.status(
            task_card=self.card,
            experiment_id=started["experiment_id"],
        )
        self.assertEqual(status["task_governance"]["state"], "pre_threshold")
        invalid = dict(heartbeat)
        invalid["timestamp"] = "2026-07-25T00:00:01Z"
        invalid["wall_seconds"] = -1
        with self.assertRaisesRegex(ValueError, "nonnegative"):
            self.manager.event(
                task_card=self.card,
                experiment_id=started["experiment_id"],
                payload=invalid,
            )

    def test_interval_regression_and_finalize_without_stage_fail_closed(
        self,
    ) -> None:
        started = self.manager.start(
            task_card=self.card,
            manifest=self._manifest(),
        )
        self.manager.observe(
            task_card=self.card,
            actor_role="main",
            payload=self._observation(
                "obs-large",
                [self._interval("root", 0, 500)],
            ),
        )
        with self.assertRaisesRegex(ValueError, "remove or shrink"):
            self.manager.observe(
                task_card=self.card,
                actor_role="main",
                payload=self._observation(
                    "obs-small",
                    [self._interval("root", 0, 499)],
                ),
            )
        directory = Path(started["directory"])
        (directory / "result.txt").write_text("2\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "completed stage"):
            self.manager.finalize(
                task_card=self.card,
                experiment_id=started["experiment_id"],
                selected_paths=["result.txt"],
            )

    def test_only_main_and_operator_can_record_host_time_or_decisions(
        self,
    ) -> None:
        for command in ("experiment-observe", "experiment-decision"):
            self.assertIn(command, allowed_commands("main"))
            self.assertIn(command, allowed_commands("operator"))
            self.assertNotIn(command, allowed_commands("worker"))
            self.assertNotIn(
                command,
                allowed_commands_for_workflow("worker", 4),
            )


if __name__ == "__main__":
    unittest.main()

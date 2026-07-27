from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mathgraph.computations import (
    CONTINUATION_THRESHOLD_NS,
    ExperimentManager,
    validate_experiment_final_receipt,
)
from mathgraph.contracts import POLICY_REVISION_V4, sha256_json
from mathgraph.orchestrator import create_round
from mathgraph.roles import allowed_commands, allowed_commands_for_workflow
from mathgraph.store import MathGraphStore


class V4GovernanceRedTeamTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.store = MathGraphStore(self.root)
        self.store.initialize(
            project_id="v4-governance-redteam",
            title="V4 governance red-team",
            workflow_evidence_version=4,
        )
        self.memory_id = self.store.memory_add(
            {
                "kind": "computation",
                "claim": "Run an adversarially governed toy computation.",
                "rationale": "Task-time governor red-team fixture",
                "suggested_actions": ["compute"],
            },
            actor="main",
        )
        planned = create_round(
            self.store,
            workers=1,
            memory_ids=[self.memory_id],
        )
        assignment = planned["assignments"][0]
        self.card = json.loads(
            Path(assignment["task_card_path"]).read_text(encoding="utf-8")
        )
        self.manager = self.store.experiments()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _manifest(objective: str = "primary") -> dict:
        return {
            "objective": f"Compute adversarial toy result {objective}.",
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
                    "estimate_basis": "adversarial fixture",
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
            "progress": "The exact stage is active.",
            "latest_checkpoint": "",
            "importance_and_continuation_value": (
                "The result tests a load-bearing obstruction."
            ),
            "stopping_impact": "Only complete checkpoints survive stopping.",
        }

    @staticmethod
    def _decision(
        decision_id: str,
        notice_id: str,
        *,
        choice: str = "continue",
        reason: str = "The exact obstruction remains decisive.",
    ) -> dict:
        return {
            "schema_version": 1,
            "decision_id": decision_id,
            "notice_id": notice_id,
            "decision": choice,
            "authority_kind": "user",
            "authority_reference": "host-ui-redteam-receipt",
            "reason": reason,
        }

    @staticmethod
    def _heartbeat(*, marker: str = "heartbeat") -> dict:
        return {
            "event": "heartbeat",
            "stage": "exact",
            "completed_units": 1,
            "total_units_or_null": 2,
            "cpu_seconds": 1,
            "wall_seconds": 1201,
            "rss_bytes": 1024,
            "latest_check": marker,
        }

    @staticmethod
    def _write_json(path: Path, payload: dict) -> None:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _reencode_first_event(raw: bytes) -> bytes:
        lines = raw.splitlines(keepends=True)
        if not lines:
            raise AssertionError("expected a nonempty event ledger")
        first = json.loads(lines[0])
        lines[0] = (
            json.dumps(
                first,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
        return b"".join(lines)

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

    def _cross_threshold(
        self,
        *,
        observation_id: str = "obs-cross",
    ) -> dict:
        return self.manager.observe(
            task_card=self.card,
            actor_role="main",
            payload=self._observation(
                observation_id,
                [
                    self._interval(
                        "root",
                        0,
                        CONTINUATION_THRESHOLD_NS + 1,
                    )
                ],
            ),
        )

    def _prepare_resumable_experiment(
        self,
    ) -> tuple[dict, str, dict[str, str]]:
        started = self.manager.start(
            task_card=self.card,
            manifest=self._manifest(),
        )
        experiment_id = started["experiment_id"]
        self._complete_stage(experiment_id)
        directory = Path(started["directory"])
        checkpoint = directory / "checkpoints" / "exact.json"
        checkpoint.write_text('{"value":2}\n', encoding="utf-8")
        compatibility = {"python": "3"}
        checkpoint_event_id = self.manager.event(
            task_card=self.card,
            experiment_id=experiment_id,
            payload={
                "event": "checkpoint",
                "checkpoint_path": "checkpoints/exact.json",
                "checkpoint_sha256": hashlib.sha256(
                    checkpoint.read_bytes()
                ).hexdigest(),
                "completed_stage": "exact",
                "resume_compatibility_hash": sha256_json(compatibility),
            },
        )
        (directory / "result.txt").write_text("2\n", encoding="utf-8")
        return started, checkpoint_event_id, compatibility

    def _finalized_experiment(
        self,
        *,
        with_governance_observation: bool = False,
    ) -> tuple[dict, Path, dict]:
        started = self.manager.start(
            task_card=self.card,
            manifest=self._manifest(),
        )
        experiment_id = started["experiment_id"]
        self._complete_stage(experiment_id)
        if with_governance_observation:
            self.manager.observe(
                task_card=self.card,
                actor_role="main",
                payload=self._observation(
                    "obs-pre-threshold",
                    [self._interval("root", 0, 100)],
                ),
            )
        directory = Path(started["directory"])
        (directory / "result.txt").write_text("2\n", encoding="utf-8")
        receipt = self.manager.finalize(
            task_card=self.card,
            experiment_id=experiment_id,
            selected_paths=["result.txt"],
        )
        return started, directory, receipt

    def test_exact_threshold_and_plus_one_ns_with_parallel_union(self) -> None:
        overlap = self.manager.observe(
            task_card=self.card,
            actor_role="main",
            payload=self._observation(
                "obs-overlap",
                [
                    self._interval("parallel-a", 0, 900_000_000_000),
                    self._interval(
                        "parallel-b",
                        300_000_000_000,
                        1_000_000_000_000,
                    ),
                ],
            ),
        )
        self.assertEqual(overlap["actual_cumulative_task_seconds"], 1000)
        self.assertEqual(overlap["state"], "pre_threshold")

        exactly = self.manager.observe(
            task_card=self.card,
            actor_role="operator",
            payload=self._observation(
                "obs-exactly-1200",
                [
                    self._interval("parallel-a", 0, 900_000_000_000),
                    self._interval(
                        "parallel-b",
                        300_000_000_000,
                        CONTINUATION_THRESHOLD_NS,
                    ),
                ],
            ),
        )
        self.assertEqual(exactly["actual_cumulative_task_seconds"], 1200)
        self.assertEqual(exactly["event"], "observation")
        self.assertEqual(exactly["state"], "pre_threshold")

        plus_one = self.manager.observe(
            task_card=self.card,
            actor_role="main",
            payload=self._observation(
                "obs-plus-one-ns",
                [
                    self._interval("parallel-a", 0, 900_000_000_000),
                    self._interval(
                        "parallel-b",
                        300_000_000_000,
                        CONTINUATION_THRESHOLD_NS + 1,
                    ),
                ],
            ),
        )
        self.assertEqual(plus_one["event"], "continuation_notice")
        self.assertEqual(plus_one["state"], "notice_issued")
        state = self.manager._governance_state(self.card)
        self.assertEqual(
            state["latest_observation"]["actual_cumulative_task_ns"],
            CONTINUATION_THRESHOLD_NS + 1,
        )
        events = self.manager._read_jsonl(Path(state["events_path"]))
        self.assertEqual(
            sum(event["event"] == "continuation_notice" for event in events),
            1,
        )

    def test_observation_id_collision_and_canonical_replay(self) -> None:
        first = self.manager.observe(
            task_card=self.card,
            actor_role="main",
            payload=self._observation(
                "obs-stable-id",
                [self._interval("single", 0, 100)],
            ),
        )
        equivalent = self.manager.observe(
            task_card=self.card,
            actor_role="operator",
            payload=self._observation(
                "obs-stable-id",
                [
                    self._interval("split-a", 0, 40),
                    self._interval("split-b", 40, 100),
                ],
            ),
        )
        self.assertEqual(equivalent["event_id"], first["event_id"])
        self.assertEqual(equivalent["status"], "already_recorded")

        collision = self._observation(
            "obs-stable-id",
            [self._interval("single", 0, 100)],
        )
        collision["progress"] = "Different evidence under the same id."
        with self.assertRaisesRegex(
            ValueError,
            "observation id was reused with different evidence",
        ):
            self.manager.observe(
                task_card=self.card,
                actor_role="main",
                payload=collision,
            )

    def test_new_experiment_and_manager_instance_cannot_reset_governance(
        self,
    ) -> None:
        started = self.manager.start(
            task_card=self.card,
            manifest=self._manifest("first"),
        )
        notice = self._cross_threshold()
        self.assertEqual(notice["state"], "notice_issued")

        fresh_manager = ExperimentManager(self.root)
        fresh = fresh_manager.start(
            task_card=self.card,
            manifest=self._manifest("fresh-process-second"),
        )
        self.assertEqual(fresh["status"], "started")
        self.assertNotEqual(fresh["experiment_id"], started["experiment_id"])

    def test_interval_shrink_and_epoch_replacement_fail_closed(self) -> None:
        self.manager.observe(
            task_card=self.card,
            actor_role="main",
            payload=self._observation(
                "obs-two-epochs",
                [
                    self._interval("a", 0, 100, epoch="epoch-a"),
                    self._interval("b", 0, 50, epoch="epoch-b"),
                ],
            ),
        )
        with self.assertRaisesRegex(ValueError, "remove or shrink"):
            self.manager.observe(
                task_card=self.card,
                actor_role="main",
                payload=self._observation(
                    "obs-shrunk-a",
                    [
                        self._interval("a", 1, 100, epoch="epoch-a"),
                        self._interval("b", 0, 50, epoch="epoch-b"),
                    ],
                ),
            )
        with self.assertRaisesRegex(ValueError, "remove or shrink"):
            self.manager.observe(
                task_card=self.card,
                actor_role="main",
                payload=self._observation(
                    "obs-replaced-epoch",
                    [
                        self._interval("b", 0, 50, epoch="epoch-b"),
                        self._interval("c", 0, 200, epoch="epoch-c"),
                    ],
                ),
            )

        extended = self.manager.observe(
            task_card=self.card,
            actor_role="operator",
            payload=self._observation(
                "obs-added-epoch",
                [
                    self._interval("a", 0, 100, epoch="epoch-a"),
                    self._interval("b", 0, 50, epoch="epoch-b"),
                    self._interval("c", 0, 75, epoch="epoch-c"),
                ],
            ),
        )
        self.assertEqual(
            extended["actual_cumulative_task_seconds"],
            100 / 1_000_000_000,
        )
        state = self.manager._governance_state(self.card)
        self.assertEqual(
            state["latest_observation"]["actual_cumulative_task_ns"],
            100,
        )
        self.assertEqual(
            len(state["latest_observation"]["canonical_active_intervals"]),
            3,
        )

    def test_decision_notice_mismatch_and_decision_id_collision(self) -> None:
        notice = self._cross_threshold()
        with self.assertRaisesRegex(
            ValueError,
            "does not bind the issued notice",
        ):
            self.manager.decision(
                task_card=self.card,
                actor_role="main",
                payload=self._decision(
                    "decision-wrong-notice",
                    "notice-not-the-pending-notice",
                ),
            )

        accepted_payload = self._decision(
            "decision-stable-id",
            notice["notice_id"],
        )
        accepted = self.manager.decision(
            task_card=self.card,
            actor_role="operator",
            payload=accepted_payload,
        )
        self.assertEqual(accepted["state"], "acknowledged")
        collision = dict(accepted_payload)
        collision["reason"] = "Conflicting evidence under the same decision id."
        with self.assertRaisesRegex(
            ValueError,
            "decision id was reused with different evidence",
        ):
            self.manager.decision(
                task_card=self.card,
                actor_role="main",
                payload=collision,
            )
        stopped = self.manager.decision(
            task_card=self.card,
            actor_role="main",
            payload=self._decision(
                "decision-stop-after-acknowledgement",
                notice["notice_id"],
                choice="stop",
                reason="The host explicitly stops after acknowledging the notice.",
            ),
        )
        self.assertEqual(stopped["state"], "stopped")
        with self.assertRaisesRegex(
            ValueError,
            "no further response is available",
        ):
            self.manager.decision(
                task_card=self.card,
                actor_role="main",
                payload=self._decision(
                    "decision-after-resolution",
                    notice["notice_id"],
                ),
            )

    def test_worker_cannot_observe_or_authorize_continuation(self) -> None:
        for command in ("experiment-observe", "experiment-decision"):
            self.assertNotIn(command, allowed_commands("worker"))
            self.assertNotIn(
                command,
                allowed_commands_for_workflow("worker", 4),
            )
        with self.assertRaisesRegex(ValueError, "main or operator"):
            self.manager.observe(
                task_card=self.card,
                actor_role="worker",
                payload=self._observation(
                    "obs-worker-forbidden",
                    [self._interval("worker", 0, 1)],
                ),
            )
        notice = self._cross_threshold()
        with self.assertRaisesRegex(ValueError, "main or operator"):
            self.manager.decision(
                task_card=self.card,
                actor_role="worker",
                payload=self._decision(
                    "decision-worker-forbidden",
                    notice["notice_id"],
                ),
            )
        self.assertEqual(
            self.manager._governance_state(self.card)["state"],
            "notice_issued",
        )

    def test_pending_and_stopped_states_block_protected_actions(self) -> None:
        started, checkpoint_event_id, compatibility = (
            self._prepare_resumable_experiment()
        )
        experiment_id = started["experiment_id"]
        notice = self._cross_threshold()
        self.assertEqual(notice["state"], "notice_issued")

        with patch("os.kill") as os_kill:
            second = self.manager.start(
                task_card=self.card,
                manifest=self._manifest("after-notice"),
            )
            self.manager.event(
                task_card=self.card,
                experiment_id=experiment_id,
                payload=self._heartbeat(marker="after-notice-heartbeat"),
            )
            resumed = self.manager.resume(
                task_card=self.card,
                experiment_id=experiment_id,
                checkpoint_event_id=checkpoint_event_id,
                current_compatibility=compatibility,
            )
            self.assertEqual(resumed["status"], "resumed")
            extended = self.manager.observe(
                task_card=self.card,
                actor_role="operator",
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
            self.assertEqual(extended["state"], "notice_issued")
            receipt = self.manager.finalize(
                task_card=self.card,
                experiment_id=experiment_id,
                selected_paths=["result.txt"],
            )
            self.assertEqual(receipt["governance_state"], "notice_issued")

            second_id = second["experiment_id"]
            self._complete_stage(second_id)
            second_directory = Path(second["directory"])
            checkpoint = (
                second_directory / "checkpoints" / "before-stop.json"
            )
            checkpoint.write_text('{"value":3}\n', encoding="utf-8")
            second_checkpoint_event_id = self.manager.event(
                task_card=self.card,
                experiment_id=second_id,
                payload={
                    "event": "checkpoint",
                    "checkpoint_path": "checkpoints/before-stop.json",
                    "checkpoint_sha256": hashlib.sha256(
                        checkpoint.read_bytes()
                    ).hexdigest(),
                    "completed_stage": "exact",
                    "resume_compatibility_hash": sha256_json(compatibility),
                },
            )
            (second_directory / "result.txt").write_text(
                "3\n",
                encoding="utf-8",
            )
            status = self.manager.status(
                task_card=self.card,
                experiment_id=second_id,
            )
            self.assertEqual(
                status["task_governance"]["state"],
                "notice_issued",
            )
            self.assertIn(
                "issued_notice",
                status["task_governance"],
            )
            self.assertNotIn(
                "pending_notice",
                status["task_governance"],
            )
            os_kill.assert_not_called()

            stopped = self.manager.decision(
                task_card=self.card,
                actor_role="main",
                payload=self._decision(
                    "decision-stop",
                    notice["notice_id"],
                    choice="stop",
                    reason="The host explicitly elects to stop.",
                ),
            )
            self.assertEqual(stopped["state"], "stopped")

            post_stop_checkpoint = (
                second_directory / "checkpoints" / "after-stop.json"
            )
            post_stop_checkpoint.write_text(
                '{"value":4}\n',
                encoding="utf-8",
            )
            second_events_path = second_directory / "events.jsonl"
            second_events_before = second_events_path.read_bytes()
            experiment_names_before = sorted(
                path.name
                for path in second_directory.parent.iterdir()
                if path.is_dir()
            )
            stopped_actions = (
                lambda: self.manager.start(
                    task_card=self.card,
                    manifest=self._manifest("stopped-new"),
                ),
                lambda: self.manager.event(
                    task_card=self.card,
                    experiment_id=second_id,
                    payload=self._heartbeat(marker="stopped-heartbeat"),
                ),
                lambda: self.manager.event(
                    task_card=self.card,
                    experiment_id=second_id,
                    payload={
                        "event": "failed",
                        "stage": "exact",
                        "reason": "Must remain unwritten after explicit stop.",
                    },
                ),
                lambda: self.manager.event(
                    task_card=self.card,
                    experiment_id=second_id,
                    payload={
                        "event": "checkpoint",
                        "checkpoint_path": (
                            "checkpoints/after-stop.json"
                        ),
                        "checkpoint_sha256": hashlib.sha256(
                            post_stop_checkpoint.read_bytes()
                        ).hexdigest(),
                        "completed_stage": "exact",
                        "resume_compatibility_hash": sha256_json(
                            compatibility
                        ),
                    },
                ),
                lambda: self.manager.resume(
                    task_card=self.card,
                    experiment_id=second_id,
                    checkpoint_event_id=second_checkpoint_event_id,
                    current_compatibility=compatibility,
                ),
                lambda: self.manager.finalize(
                    task_card=self.card,
                    experiment_id=second_id,
                    selected_paths=["result.txt"],
                ),
                lambda: self.manager.observe(
                    task_card=self.card,
                    actor_role="operator",
                    payload=self._observation(
                        "obs-after-stop",
                        [
                            self._interval(
                                "root",
                                0,
                                CONTINUATION_THRESHOLD_NS + 3,
                            )
                        ],
                    ),
                ),
            )
            for action in stopped_actions:
                with self.subTest(state="stopped", action=repr(action)):
                    with self.assertRaisesRegex(
                        ValueError,
                        "stopped|forbidden",
                    ):
                        action()
            self.assertEqual(
                second_events_path.read_bytes(),
                second_events_before,
            )
            self.assertEqual(
                sorted(
                    path.name
                    for path in second_directory.parent.iterdir()
                    if path.is_dir()
                ),
                experiment_names_before,
            )
            os_kill.assert_not_called()

    def test_worker_heartbeat_1201_does_not_drive_governance_clock(self) -> None:
        started = self.manager.start(
            task_card=self.card,
            manifest=self._manifest(),
        )
        self.manager.event(
            task_card=self.card,
            experiment_id=started["experiment_id"],
            payload=self._heartbeat(marker="worker reports 1201 seconds"),
        )
        status = self.manager.status(
            task_card=self.card,
            experiment_id=started["experiment_id"],
        )
        self.assertEqual(status["task_governance"]["state"], "pre_threshold")
        self.assertEqual(status["task_governance"]["event_count"], 0)
        self.assertIsNone(
            self.manager._governance_state(self.card)["notice"],
        )

    def test_schema3_receipt_binds_exact_experiment_and_governance_prefixes(
        self,
    ) -> None:
        _, directory, receipt = self._finalized_experiment(
            with_governance_observation=True,
        )
        self.assertEqual(receipt["schema_version"], 3)
        receipt_path = directory / "final_receipt.json"
        experiment_events_path = directory / "events.jsonl"
        governance_events_path = Path(
            self.manager._governance_state(self.card)["events_path"]
        )

        original_experiment = experiment_events_path.read_bytes()
        tampered_experiment = self._reencode_first_event(
            original_experiment
        )
        self.assertNotEqual(tampered_experiment, original_experiment)
        try:
            experiment_events_path.write_bytes(tampered_experiment)
            with self.assertRaisesRegex(
                ValueError,
                "event-ledger prefix mismatch",
            ):
                validate_experiment_final_receipt(
                    project_root=self.root,
                    task_card=self.card,
                    receipt_path=receipt_path,
                )
        finally:
            experiment_events_path.write_bytes(original_experiment)

        original_governance = governance_events_path.read_bytes()
        tampered_governance = self._reencode_first_event(
            original_governance
        )
        self.assertNotEqual(tampered_governance, original_governance)
        try:
            governance_events_path.write_bytes(tampered_governance)
            with self.assertRaisesRegex(
                ValueError,
                "governance-ledger prefix mismatch",
            ):
                validate_experiment_final_receipt(
                    project_root=self.root,
                    task_card=self.card,
                    receipt_path=receipt_path,
                )
        finally:
            governance_events_path.write_bytes(original_governance)

    def test_final_event_crash_recovery_and_illegal_suffix_rejection(
        self,
    ) -> None:
        started, directory, receipt = self._finalized_experiment()
        receipt_path = directory / "final_receipt.json"
        events_path = directory / "events.jsonl"
        lines = events_path.read_bytes().splitlines(keepends=True)
        self.assertEqual(json.loads(lines[-1])["event"], "finalized")
        events_path.write_bytes(b"".join(lines[:-1]))

        with self.assertRaisesRegex(
            ValueError,
            "lacks its unique terminal event",
        ):
            validate_experiment_final_receipt(
                project_root=self.root,
                task_card=self.card,
                receipt_path=receipt_path,
            )
        recovered = self.manager.finalize(
            task_card=self.card,
            experiment_id=started["experiment_id"],
            selected_paths=["result.txt"],
        )
        self.assertEqual(recovered["receipt_sha256"], receipt["receipt_sha256"])
        repeated = self.manager.finalize(
            task_card=self.card,
            experiment_id=started["experiment_id"],
            selected_paths=["result.txt"],
        )
        self.assertEqual(repeated, recovered)
        recovered_events = self.manager._read_jsonl(events_path)
        self.assertEqual(
            sum(event.get("event") == "finalized" for event in recovered_events),
            1,
        )

        illegal_semantic = {
            "schema_version": 1,
            "policy_revision": POLICY_REVISION_V4,
            **self._heartbeat(marker="illegal post-final suffix"),
        }
        illegal_event = {
            **illegal_semantic,
            "event_id": sha256_json(illegal_semantic),
        }
        with events_path.open("ab") as handle:
            handle.write(
                (
                    json.dumps(
                        illegal_event,
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    + "\n"
                ).encode("utf-8")
            )
        with self.assertRaisesRegex(
            ValueError,
            "lacks its unique terminal event",
        ):
            validate_experiment_final_receipt(
                project_root=self.root,
                task_card=self.card,
                receipt_path=receipt_path,
            )
        with self.assertRaisesRegex(
            ValueError,
            "lacks its unique terminal event",
        ):
            self.manager.finalize(
                task_card=self.card,
                experiment_id=started["experiment_id"],
                selected_paths=["result.txt"],
            )

    def test_legacy_schema1_receipt_is_readable_but_not_schema2_like(
        self,
    ) -> None:
        _, directory, schema2 = self._finalized_experiment()
        receipt_path = directory / "final_receipt.json"
        legacy_semantic = {
            "schema_version": 1,
            "policy_revision": schema2["policy_revision"],
            "experiment_id": schema2["experiment_id"],
            "assignment_id": schema2["assignment_id"],
            "selected_outputs": schema2["selected_outputs"],
            "manifest_sha256": schema2["manifest_sha256"],
        }
        legacy = {
            **legacy_semantic,
            "receipt_sha256": sha256_json(legacy_semantic),
        }
        self._write_json(receipt_path, legacy)
        validated = validate_experiment_final_receipt(
            project_root=self.root,
            task_card=self.card,
            receipt_path=receipt_path,
        )
        self.assertEqual(validated["schema_version"], 1)
        self.assertNotIn("experiment_event_count", validated)
        self.assertNotIn("governance_task_id", validated)

        masquerading_semantic = {
            **legacy_semantic,
            "experiment_event_count": schema2["experiment_event_count"],
            "experiment_events_sha256": schema2[
                "experiment_events_sha256"
            ],
            "governance_task_id": schema2["governance_task_id"],
            "governance_state": schema2["governance_state"],
            "governance_event_count": schema2["governance_event_count"],
            "governance_events_sha256": schema2[
                "governance_events_sha256"
            ],
        }
        masquerading = {
            **masquerading_semantic,
            "receipt_sha256": sha256_json(masquerading_semantic),
        }
        self._write_json(receipt_path, masquerading)
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            validate_experiment_final_receipt(
                project_root=self.root,
                task_card=self.card,
                receipt_path=receipt_path,
            )


if __name__ == "__main__":
    unittest.main()

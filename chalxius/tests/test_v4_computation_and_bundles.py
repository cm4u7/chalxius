from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from mathgraph.computations import (
    INDEPENDENCE_AXES,
    ExperimentManager,
    validate_computational_evidence,
    validate_independence_matrix,
)
from mathgraph.contracts import POLICY_REVISION_V4, sha256_json
from mathgraph.event_ledger import INDEX_FILENAME, ExperimentEventLedger
from mathgraph.interfaces import build_statement_interface
from mathgraph.migration import project_tree_snapshot
from mathgraph.model import Fact
from mathgraph.orchestrator import create_round, create_verifier_assignment
from mathgraph.roles import allowed_commands_for_workflow
from mathgraph.store import MathGraphStore
from mathgraph.verification_bundles import (
    VerificationBundleStore,
    admission_gate_v4,
    validate_review_v4,
)


class V4ComputationAndBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.store = MathGraphStore(self.root)
        self.store.initialize(
            project_id="v4-computation",
            title="V4 computation",
            workflow_evidence_version=4,
        )
        memory_id = self.store.memory_add(
            {
                "kind": "computation",
                "claim": "Compute one exact toy value.",
                "rationale": "Fixture",
                "suggested_actions": ["compute"],
            },
            actor="main",
        )
        self.round = create_round(
            self.store,
            workers=1,
            memory_ids=[memory_id],
        )
        assignment = self.round["assignments"][0]
        self.card_path = Path(assignment["task_card_path"])
        self.card = json.loads(self.card_path.read_text())
        self.artifact_dir = Path(assignment["artifact_dir_path"])
        self.legacy_temporary: tempfile.TemporaryDirectory | None = None

    def tearDown(self) -> None:
        if self.legacy_temporary is not None:
            self.legacy_temporary.cleanup()
        self.temporary.cleanup()

    def _use_inherited_chalk_compatibility_store(self) -> None:
        self.legacy_temporary = tempfile.TemporaryDirectory()
        legacy_root = Path(self.legacy_temporary.name).resolve()
        self.root = legacy_root
        self.store = MathGraphStore._for_inherited_chalk_fixture(
            legacy_root
        )
        self.store.initialize(
            project_id="v4-computation",
            title="Inherited Chalk compatibility fixture",
            workflow_evidence_version=4,
            reasoning_mode=None,
        )
        self.artifact_dir = legacy_root / "imports" / "direct-fixture"
        self.artifact_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _matrix(value: str = "cross_checked") -> dict[str, str]:
        return {axis: value for axis in INDEPENDENCE_AXES}

    def _artifact(self, name: str, data: bytes) -> dict[str, str]:
        path = self.artifact_dir / name
        path.write_bytes(data)
        return {
            "path": path.relative_to(self.root).as_posix(),
            "sha256": hashlib.sha256(data).hexdigest(),
        }

    def _evidence(
        self,
        artifact: dict[str, str],
        *,
        role: str = "load_bearing",
        certificate_kind: str = "exact_bound",
    ) -> dict:
        return {
            "key": "toy",
            "role": role,
            "proof_anchor": "[COMP:toy]",
            "artifact_refs": [
                {
                    "role": "result",
                    "path": artifact["path"],
                    "sha256": artifact["sha256"],
                }
            ],
            "entrypoint_role": "result",
            "command": ["python3", "result.txt"],
            "interpreter": {
                "implementation": "CPython",
                "version": "3",
            },
            "arithmetic": "exact integers",
            "algorithm_spec": "Evaluate 1+1.",
            "truncation_certificate": {
                "kind": certificate_kind,
                "statement": "The finite calculation is exhaustive.",
                "checked_orders": [0],
                "limitations": [],
            },
            "expected_outputs": [
                {"role": "result", "sha256": artifact["sha256"]}
            ],
            "replay_checks": ["inspect_algorithm", "execute"],
            "independence_matrix": self._matrix(),
        }

    def _experiment_manifest(self) -> dict:
        return {
            "objective": "Compute one exact value.",
            "command": ["python3", "run.py"],
            "environment": {
                "implementation": "CPython",
                "version": "3",
            },
            "cost_model": {
                "dominant_operation": "integer addition",
                "estimated_cost": 1,
                "expected_memory": "constant",
                "parallelism": "none",
                "complexity_model": {
                    "parameters": {"n": 1},
                    "asymptotic_time": "O(n)",
                    "asymptotic_space": "O(1)",
                    "estimated_operation_count": 1,
                    "estimate_basis": "one addition",
                    "intermediate_object_estimates": [],
                },
            },
            "stages": ["exact"],
            "escalation_ladder": [
                {
                    "stage_id": "exact",
                    "arithmetic": "integer",
                    "advance_condition": "stop after exact result",
                }
            ],
            "checkpoint_policy": "after every complete stage",
            "resume_contract": {
                "checkpoint_format": "json",
                "resume_command": ["python3", "run.py", "--resume"],
                "compatibility_fields": ["python"],
                "deterministic_replay_required": True,
            },
            "truth_status": "exploration",
        }

    def _start_with_checkpoint(
        self,
    ) -> tuple[ExperimentManager, dict, str, dict[str, str]]:
        manager = self.store.experiments()
        started = manager.start(
            task_card=self.card,
            manifest=self._experiment_manifest(),
        )
        experiment_id = started["experiment_id"]
        directory = Path(started["directory"])
        manager.event(
            task_card=self.card,
            experiment_id=experiment_id,
            payload={
                "event": "stage_completed",
                "stage": "exact",
                "advance_condition_disposition": "exact result obtained",
            },
        )
        checkpoint = directory / "checkpoints" / "stage.json"
        checkpoint.write_text('{"value": 2}\n', encoding="utf-8")
        from mathgraph.contracts import sha256_json

        compatibility = {"python": "3"}
        event_id = manager.event(
            task_card=self.card,
            experiment_id=experiment_id,
            payload={
                "event": "checkpoint",
                "checkpoint_path": "checkpoints/stage.json",
                "checkpoint_sha256": hashlib.sha256(
                    checkpoint.read_bytes()
                ).hexdigest(),
                "completed_stage": "exact",
                "resume_compatibility_hash": sha256_json(compatibility),
            },
        )
        return manager, started, event_id, compatibility

    def _complete_exact_stage(
        self,
        manager: ExperimentManager,
        experiment_id: str,
    ) -> None:
        manager.event(
            task_card=self.card,
            experiment_id=experiment_id,
            payload={
                "event": "stage_completed",
                "stage": "exact",
                "advance_condition_disposition": "exact result obtained",
                "actual_intermediate_object_counts": [
                    {"object_kind": "integer", "count": 1}
                ],
            },
        )

    def test_load_bearing_computation_requires_comp_anchor(self) -> None:
        artifact = self._artifact("result.txt", b"2\n")
        evidence = self._evidence(artifact)
        validated = validate_computational_evidence(
            [evidence],
            proof="Exact replay gives 2. [COMP:toy]",
            artifacts=[artifact],
            verification_plan={
                "mode": "artifact_replay",
                "authorized_artifact_roles": ["result"],
                "required_checks": ["execute"],
            },
        )
        self.assertEqual(validated[0]["key"], "toy")
        with self.assertRaisesRegex(ValueError, "exactly once"):
            validate_computational_evidence(
                [evidence],
                proof="No anchor.",
                artifacts=[artifact],
                verification_plan={
                    "mode": "artifact_replay",
                    "authorized_artifact_roles": ["result"],
                    "required_checks": [],
                },
            )

    def test_computation_hashes_must_bind_declared_artifacts(self) -> None:
        artifact = self._artifact("result.txt", b"2\n")
        evidence = self._evidence(artifact)
        evidence["artifact_refs"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "artifact"):
            validate_computational_evidence(
                [evidence],
                proof="[COMP:toy]",
                artifacts=[artifact],
                verification_plan={
                    "mode": "artifact_replay",
                    "authorized_artifact_roles": ["result"],
                    "required_checks": [],
                },
            )

    def test_work_checkpoint_cannot_enter_computational_evidence(self) -> None:
        digest = hashlib.sha256(b"x").hexdigest()
        artifact = {
            "path": "rounds/r/work/a/checkpoints/x",
            "sha256": digest,
        }
        with self.assertRaisesRegex(ValueError, "checkpoint"):
            validate_computational_evidence(
                [self._evidence(artifact)],
                proof="[COMP:toy]",
                artifacts=[artifact],
                verification_plan={
                    "mode": "artifact_replay",
                    "authorized_artifact_roles": ["result"],
                    "required_checks": [],
                },
            )

    def test_two_depth_agreement_alone_is_not_truncation_proof(self) -> None:
        artifact = self._artifact("result.txt", b"2\n")
        with self.assertRaisesRegex(ValueError, "two-depth"):
            validate_computational_evidence(
                [self._evidence(artifact, certificate_kind="two_depth_agreement")],
                proof="[COMP:toy]",
                artifacts=[artifact],
                verification_plan={
                    "mode": "artifact_replay",
                    "authorized_artifact_roles": ["result"],
                    "required_checks": [],
                },
            )

    def test_independence_matrix_requires_all_fixed_axes(self) -> None:
        matrix = self._matrix()
        self.assertEqual(validate_independence_matrix(matrix), matrix)
        incomplete = dict(matrix)
        incomplete.pop(next(iter(INDEPENDENCE_AXES)))
        with self.assertRaises(ValueError):
            validate_independence_matrix(incomplete)

    def test_independence_matrix_rejects_scalar_confidence(self) -> None:
        matrix = self._matrix()
        with self.assertRaisesRegex(ValueError, "scalar"):
            validate_independence_matrix(
                {**matrix, "confidence_score": 0.9}
            )

    def test_experiment_requires_complexity_model_even_when_unknown(self) -> None:
        manifest = self._experiment_manifest()
        manifest["cost_model"]["complexity_model"] = {
            "parameters": {},
            "asymptotic_time": "unknown",
            "asymptotic_space": "unknown",
            "estimated_operation_count": None,
            "estimate_basis": "unknown before pilot",
            "intermediate_object_estimates": [],
        }
        result = self.store.experiments().start(
            task_card=self.card,
            manifest=manifest,
        )
        self.assertEqual(result["status"], "started")
        invalid = self._experiment_manifest()
        invalid["cost_model"].pop("complexity_model")
        with self.assertRaisesRegex(ValueError, "missing"):
            self.store.experiments().start(
                task_card=self.card,
                manifest=invalid,
            )

    def test_experiment_rejects_schema_valid_but_unbound_task_card(
        self,
    ) -> None:
        tampered = json.loads(json.dumps(self.card))
        tampered["work_dir_relpath"] = (
            tampered["work_dir_relpath"] + "-redirected"
        )
        with self.assertRaisesRegex(ValueError, "frozen round card"):
            self.store.experiments().start(
                task_card=tampered,
                manifest=self._experiment_manifest(),
            )

    def test_experiment_events_resume_finalize_and_immutable_receipt(self) -> None:
        manager = self.store.experiments()
        started = manager.start(
            task_card=self.card,
            manifest=self._experiment_manifest(),
        )
        experiment_id = started["experiment_id"]
        directory = Path(started["directory"])
        manager.event(
            task_card=self.card,
            experiment_id=experiment_id,
            payload={
                "event": "stage_completed",
                "stage": "exact",
                "advance_condition_disposition": "exact result obtained",
            },
        )
        checkpoint = directory / "checkpoints" / "stage.json"
        checkpoint.write_text('{"value": 2}\n')
        from mathgraph.contracts import sha256_json

        compatibility = {"python": "3"}
        checkpoint_event_id = manager.event(
            task_card=self.card,
            experiment_id=experiment_id,
            payload={
                "event": "checkpoint",
                "checkpoint_path": "checkpoints/stage.json",
                "checkpoint_sha256": hashlib.sha256(
                    checkpoint.read_bytes()
                ).hexdigest(),
                "completed_stage": "exact",
                "resume_compatibility_hash": sha256_json(compatibility),
            },
        )
        resumed = manager.validate_resume(
            task_card=self.card,
            experiment_id=experiment_id,
            checkpoint_event_id=checkpoint_event_id,
            current_compatibility=compatibility,
        )
        self.assertTrue(resumed["compatible"])
        with self.assertRaisesRegex(ValueError, "incompatible"):
            manager.validate_resume(
                task_card=self.card,
                experiment_id=experiment_id,
                checkpoint_event_id=checkpoint_event_id,
                current_compatibility={"python": "4"},
            )
        result_file = directory / "result.txt"
        result_file.write_text("2\n")
        unselected = directory / "scratch.txt"
        unselected.write_text("scratch\n")
        receipt = manager.finalize(
            task_card=self.card,
            experiment_id=experiment_id,
            selected_paths=["result.txt"],
        )
        self.assertEqual(len(receipt["selected_outputs"]), 1)
        self.assertFalse((self.artifact_dir / "scratch.txt").exists())
        repeated = manager.finalize(
            task_card=self.card,
            experiment_id=experiment_id,
            selected_paths=["scratch.txt"],
        )
        self.assertEqual(receipt, repeated)
        self.assertEqual(
            manager.status(
                task_card=self.card,
                experiment_id=experiment_id,
            )["status"],
            "finalized",
        )

    def test_finalized_experiment_receipt_is_immutable(self) -> None:
        manager = self.store.experiments()
        started = manager.start(
            task_card=self.card,
            manifest=self._experiment_manifest(),
        )
        directory = Path(started["directory"])
        self._complete_exact_stage(manager, started["experiment_id"])
        (directory / "result.txt").write_text("2\n")
        manager.finalize(
            task_card=self.card,
            experiment_id=started["experiment_id"],
            selected_paths=["result.txt"],
        )
        receipt_path = directory / "final_receipt.json"
        tampered = json.loads(receipt_path.read_text())
        tampered["receipt_sha256"] = "0" * 64
        receipt_path.write_text(
            json.dumps(tampered, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "receipt hash mismatch"):
            manager.finalize(
                task_card=self.card,
                experiment_id=started["experiment_id"],
                selected_paths=["result.txt"],
            )

    def test_experiment_checkpoint_remains_nontruth(self) -> None:
        manager, started, _, _ = self._start_with_checkpoint()
        status = manager.status(
            task_card=self.card,
            experiment_id=started["experiment_id"],
        )
        self.assertEqual(status["status"], "running")
        self.assertEqual(self.store.fact_ids(), [])
        self.assertFalse(
            (Path(started["directory"]) / "final_receipt.json").exists()
        )

    def test_experiment_events_are_append_only(self) -> None:
        manager = self.store.experiments()
        started = manager.start(
            task_card=self.card,
            manifest=self._experiment_manifest(),
        )
        events_path = Path(started["directory"]) / "events.jsonl"
        before = events_path.read_bytes()
        payload = {
            "event": "heartbeat",
            "stage": "exact",
            "completed_units": 1,
            "total_units_or_null": 2,
            "cpu_seconds": 0.1,
            "wall_seconds": 0.2,
            "rss_bytes": 1024,
            "latest_check": "one unit",
        }
        first = manager.event(
            task_card=self.card,
            experiment_id=started["experiment_id"],
            payload=payload,
        )
        once = events_path.read_bytes()
        second = manager.event(
            task_card=self.card,
            experiment_id=started["experiment_id"],
            payload=payload,
        )
        self.assertEqual(first, second)
        self.assertEqual(once, events_path.read_bytes())
        self.assertTrue(once.startswith(before))

    def test_event_index_recovers_log_append_before_index_commit(
        self,
    ) -> None:
        manager = self.store.experiments()
        started = manager.start(
            task_card=self.card,
            manifest=self._experiment_manifest(),
        )
        directory = Path(started["directory"])
        events_path = directory / "events.jsonl"
        index_path = directory / INDEX_FILENAME
        self.assertTrue(index_path.is_file())
        payload = {
            "event": "heartbeat",
            "stage": "exact",
            "completed_units": 7,
            "total_units_or_null": 10,
            "cpu_seconds": 1.0,
            "wall_seconds": 2.0,
            "rss_bytes": 2048,
            "latest_check": "crash-window tail",
        }
        semantic = {
            "schema_version": 1,
            "policy_revision": POLICY_REVISION_V4,
            **payload,
        }
        event_id = sha256_json(semantic)
        with events_path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {**semantic, "event_id": event_id},
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
            )
            handle.flush()
            os.fsync(handle.fileno())
        before = events_path.read_bytes()
        recovered = manager.event(
            task_card=self.card,
            experiment_id=started["experiment_id"],
            payload=payload,
        )
        self.assertEqual(recovered, event_id)
        self.assertEqual(events_path.read_bytes(), before)
        connection = sqlite3.connect(index_path)
        try:
            count = connection.execute(
                "SELECT COUNT(*) FROM events WHERE event_key = ?",
                (bytes.fromhex(event_id),),
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(count, 1)

    def test_event_index_recovers_same_call_after_cache_commit_failure(
        self,
    ) -> None:
        manager = self.store.experiments()
        started = manager.start(
            task_card=self.card,
            manifest=self._experiment_manifest(),
        )
        directory = Path(started["directory"])
        events_path = directory / "events.jsonl"
        payload = {
            "event": "heartbeat",
            "stage": "exact",
            "completed_units": 1,
            "total_units_or_null": 2,
            "cpu_seconds": 0.1,
            "wall_seconds": 0.2,
            "rss_bytes": 1024,
            "latest_check": "same-call cache recovery",
        }
        original = ExperimentEventLedger._write_metadata
        injected = False

        def fail_once(*args: object, **kwargs: object) -> None:
            nonlocal injected
            if not injected:
                injected = True
                raise sqlite3.OperationalError(
                    "injected cache commit failure"
                )
            original(*args, **kwargs)

        with patch.object(
            ExperimentEventLedger,
            "_write_metadata",
            side_effect=fail_once,
        ):
            event_id = manager.event(
                task_card=self.card,
                experiment_id=started["experiment_id"],
                payload=payload,
            )
        events = ExperimentManager._read_jsonl(events_path)
        self.assertEqual(
            sum(event.get("event_id") == event_id for event in events),
            1,
        )

    def test_event_index_rejects_forged_canonical_event_id(self) -> None:
        manager = self.store.experiments()
        started = manager.start(
            task_card=self.card,
            manifest=self._experiment_manifest(),
        )
        events_path = Path(started["directory"]) / "events.jsonl"
        forged = {
            "schema_version": 1,
            "policy_revision": POLICY_REVISION_V4,
            "event": "heartbeat",
            "stage": "exact",
            "completed_units": 1,
            "total_units_or_null": 2,
            "cpu_seconds": 0.1,
            "wall_seconds": 0.2,
            "rss_bytes": 1024,
            "latest_check": "forged id",
            "event_id": "0" * 64,
        }
        with events_path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(forged, ensure_ascii=False, sort_keys=True)
                + "\n"
            )
            handle.flush()
            os.fsync(handle.fileno())
        before = events_path.read_bytes()
        with self.assertRaisesRegex(ValueError, "event id/hash mismatch"):
            manager.event(
                task_card=self.card,
                experiment_id=started["experiment_id"],
                payload={
                    "event": "heartbeat",
                    "stage": "exact",
                    "completed_units": 2,
                    "total_units_or_null": 2,
                    "cpu_seconds": 0.2,
                    "wall_seconds": 0.3,
                    "rss_bytes": 1024,
                    "latest_check": "must not append",
                },
            )
        self.assertEqual(events_path.read_bytes(), before)

    def test_event_index_detects_same_size_canonical_log_tamper(
        self,
    ) -> None:
        manager = self.store.experiments()
        started = manager.start(
            task_card=self.card,
            manifest=self._experiment_manifest(),
        )
        events_path = Path(started["directory"]) / "events.jsonl"
        manager.event(
            task_card=self.card,
            experiment_id=started["experiment_id"],
            payload={
                "event": "heartbeat",
                "stage": "exact",
                "completed_units": 1,
                "total_units_or_null": 2,
                "cpu_seconds": 0.1,
                "wall_seconds": 0.2,
                "rss_bytes": 1024,
                "latest_check": "same-size-A",
            },
        )
        original = events_path.read_bytes()
        tampered = original.replace(
            b'"latest_check": "same-size-A"',
            b'"latest_check": "same-size-B"',
        )
        self.assertNotEqual(tampered, original)
        self.assertEqual(len(tampered), len(original))
        events_path.write_bytes(tampered)
        with self.assertRaisesRegex(ValueError, "event id/hash mismatch"):
            manager.event(
                task_card=self.card,
                experiment_id=started["experiment_id"],
                payload={
                    "event": "heartbeat",
                    "stage": "exact",
                    "completed_units": 2,
                    "total_units_or_null": 2,
                    "cpu_seconds": 0.2,
                    "wall_seconds": 0.3,
                    "rss_bytes": 1024,
                    "latest_check": "must not append",
                },
            )
        self.assertEqual(events_path.read_bytes(), tampered)

    def test_event_index_rebuilds_corrupt_cache_without_duplicate(
        self,
    ) -> None:
        manager = self.store.experiments()
        started = manager.start(
            task_card=self.card,
            manifest=self._experiment_manifest(),
        )
        directory = Path(started["directory"])
        events_path = directory / "events.jsonl"
        index_path = directory / INDEX_FILENAME
        payload = {
            "event": "heartbeat",
            "stage": "exact",
            "completed_units": 1,
            "total_units_or_null": 2,
            "cpu_seconds": 0.1,
            "wall_seconds": 0.2,
            "rss_bytes": 1024,
            "latest_check": "corrupt-index recovery",
        }
        event_id = manager.event(
            task_card=self.card,
            experiment_id=started["experiment_id"],
            payload=payload,
        )
        before = events_path.read_bytes()
        index_path.write_bytes(b"not a sqlite database")
        repeated = manager.event(
            task_card=self.card,
            experiment_id=started["experiment_id"],
            payload=payload,
        )
        self.assertEqual(repeated, event_id)
        self.assertEqual(events_path.read_bytes(), before)
        self.assertEqual(index_path.read_bytes()[:16], b"SQLite format 3\x00")

    def test_event_index_mapping_tamper_rebuilds_from_canonical_log(
        self,
    ) -> None:
        manager = self.store.experiments()
        started = manager.start(
            task_card=self.card,
            manifest=self._experiment_manifest(),
        )
        directory = Path(started["directory"])
        events_path = directory / "events.jsonl"
        index_path = directory / INDEX_FILENAME
        payload = {
            "event": "heartbeat",
            "stage": "exact",
            "completed_units": 1,
            "total_units_or_null": 2,
            "cpu_seconds": 0.1,
            "wall_seconds": 0.2,
            "rss_bytes": 1024,
            "latest_check": "mapping-tamper recovery",
        }
        event_id = manager.event(
            task_card=self.card,
            experiment_id=started["experiment_id"],
            payload=payload,
        )
        before = events_path.read_bytes()
        connection = sqlite3.connect(index_path)
        try:
            connection.execute("DROP TRIGGER events_no_update")
            connection.execute(
                "UPDATE events SET byte_offset = byte_offset + 1 "
                "WHERE event_key = ?",
                (bytes.fromhex(event_id),),
            )
            connection.commit()
        finally:
            connection.close()
        repeated = manager.event(
            task_card=self.card,
            experiment_id=started["experiment_id"],
            payload=payload,
        )
        self.assertEqual(repeated, event_id)
        self.assertEqual(events_path.read_bytes(), before)

    def test_event_index_rows_reject_in_place_sql_mutation(self) -> None:
        manager = self.store.experiments()
        started = manager.start(
            task_card=self.card,
            manifest=self._experiment_manifest(),
        )
        index_path = Path(started["directory"]) / INDEX_FILENAME
        connection = sqlite3.connect(index_path)
        try:
            with self.assertRaisesRegex(
                sqlite3.IntegrityError,
                "immutable",
            ):
                connection.execute(
                    "UPDATE events SET byte_offset = byte_offset + 1"
                )
            connection.rollback()
        finally:
            connection.close()

    def test_read_only_status_does_not_rebuild_missing_event_index(
        self,
    ) -> None:
        manager = self.store.experiments()
        started = manager.start(
            task_card=self.card,
            manifest=self._experiment_manifest(),
        )
        index_path = Path(started["directory"]) / INDEX_FILENAME
        index_path.unlink()
        self.store.lock_path.unlink()
        before = project_tree_snapshot(self.root)
        status = manager.status(
            task_card=self.card,
            experiment_id=started["experiment_id"],
        )
        self.assertEqual(status["event_count"], 1)
        self.assertFalse(index_path.exists())
        self.assertFalse(self.store.lock_path.exists())
        self.assertEqual(before, project_tree_snapshot(self.root))
        manager.event(
            task_card=self.card,
            experiment_id=started["experiment_id"],
            payload={
                "event": "heartbeat",
                "stage": "exact",
                "completed_units": 1,
                "total_units_or_null": 2,
                "cpu_seconds": 0.1,
                "wall_seconds": 0.2,
                "rss_bytes": 1024,
                "latest_check": "lazy rebuild",
            },
        )
        self.assertTrue(index_path.is_file())

    def test_event_index_symlink_is_rejected_without_external_write(
        self,
    ) -> None:
        manager = self.store.experiments()
        started = manager.start(
            task_card=self.card,
            manifest=self._experiment_manifest(),
        )
        index_path = Path(started["directory"]) / INDEX_FILENAME
        index_path.unlink()
        external = self.root / "external-index-target"
        external.write_bytes(b"unchanged")
        index_path.symlink_to(external)
        with self.assertRaisesRegex(ValueError, "cannot be a symlink"):
            manager.event(
                task_card=self.card,
                experiment_id=started["experiment_id"],
                payload={
                    "event": "heartbeat",
                    "stage": "exact",
                    "completed_units": 1,
                    "total_units_or_null": 2,
                    "cpu_seconds": 0.1,
                    "wall_seconds": 0.2,
                    "rss_bytes": 1024,
                    "latest_check": "symlink rejection",
                },
            )
        self.assertEqual(external.read_bytes(), b"unchanged")

    def test_concurrent_identical_experiment_events_are_idempotent(
        self,
    ) -> None:
        manager = self.store.experiments()
        started = manager.start(
            task_card=self.card,
            manifest=self._experiment_manifest(),
        )
        payload = {
            "event": "heartbeat",
            "stage": "exact",
            "completed_units": 1,
            "total_units_or_null": 2,
            "cpu_seconds": 0.1,
            "wall_seconds": 0.2,
            "rss_bytes": 1024,
            "latest_check": "concurrent idempotence",
        }
        original = ExperimentManager._read_jsonl

        def slow_read(path: Path) -> list[dict]:
            result = original(path)
            if path.name == "events.jsonl":
                time.sleep(0.01)
            return result

        with patch.object(
            ExperimentManager,
            "_read_jsonl",
            side_effect=slow_read,
        ):
            with ThreadPoolExecutor(max_workers=12) as executor:
                event_ids = list(
                    executor.map(
                        lambda _index: manager.event(
                            task_card=self.card,
                            experiment_id=started["experiment_id"],
                            payload=payload,
                        ),
                        range(24),
                    )
                )
        self.assertEqual(len(set(event_ids)), 1)
        events = ExperimentManager._read_jsonl(
            Path(started["directory"]) / "events.jsonl"
        )
        matching = [
            event
            for event in events
            if event.get("event_id") == event_ids[0]
        ]
        self.assertEqual(len(matching), 1)

    def test_failed_experiment_requires_bound_resume(self) -> None:
        manager, started, checkpoint_event_id, compatibility = (
            self._start_with_checkpoint()
        )
        manager.event(
            task_card=self.card,
            experiment_id=started["experiment_id"],
            payload={
                "event": "failed",
                "stage": "exact",
                "latest_check": "simulated interruption",
            },
        )
        heartbeat = {
            "event": "heartbeat",
            "stage": "exact",
            "completed_units": 1,
            "total_units_or_null": 2,
            "cpu_seconds": 0.1,
            "wall_seconds": 0.2,
            "rss_bytes": 1024,
            "latest_check": "must resume first",
        }
        with self.assertRaisesRegex(ValueError, "requires.*resume"):
            manager.event(
                task_card=self.card,
                experiment_id=started["experiment_id"],
                payload=heartbeat,
            )
        with self.assertRaisesRegex(ValueError, "requires.*resume"):
            manager.finalize(
                task_card=self.card,
                experiment_id=started["experiment_id"],
                selected_paths=["not-yet-selected.txt"],
            )
        resumed = manager.resume(
            task_card=self.card,
            experiment_id=started["experiment_id"],
            checkpoint_event_id=checkpoint_event_id,
            current_compatibility=compatibility,
        )
        self.assertEqual(resumed["status"], "resumed")
        self.assertEqual(
            resumed,
            manager.resume(
                task_card=self.card,
                experiment_id=started["experiment_id"],
                checkpoint_event_id=checkpoint_event_id,
                current_compatibility=compatibility,
            ),
        )
        manager.event(
            task_card=self.card,
            experiment_id=started["experiment_id"],
            payload=heartbeat,
        )
        self.assertEqual(
            manager.status(
                task_card=self.card,
                experiment_id=started["experiment_id"],
            )["status"],
            "running",
        )

    def test_experiment_escalation_requires_recorded_advance_disposition(self) -> None:
        manager = self.store.experiments()
        started = manager.start(
            task_card=self.card,
            manifest=self._experiment_manifest(),
        )
        with self.assertRaisesRegex(
            ValueError, "advance_condition_disposition"
        ):
            manager.event(
                task_card=self.card,
                experiment_id=started["experiment_id"],
                payload={"event": "stage_completed", "stage": "exact"},
            )

    def test_experiment_resume_rejects_incompatible_checkpoint(self) -> None:
        manager, started, event_id, _ = self._start_with_checkpoint()
        with self.assertRaisesRegex(ValueError, "incompatible"):
            manager.validate_resume(
                task_card=self.card,
                experiment_id=started["experiment_id"],
                checkpoint_event_id=event_id,
                current_compatibility={"python": "4"},
            )

    def test_experiment_resume_starts_from_last_complete_stage(self) -> None:
        manager, started, event_id, compatibility = (
            self._start_with_checkpoint()
        )
        resumed = manager.validate_resume(
            task_card=self.card,
            experiment_id=started["experiment_id"],
            checkpoint_event_id=event_id,
            current_compatibility=compatibility,
        )
        self.assertEqual(resumed["resume_from_stage"], "exact")

    def test_resume_is_bound_to_the_selected_checkpoint_stage_and_bytes(
        self,
    ) -> None:
        manifest = self._experiment_manifest()
        manifest["stages"] = ["coarse", "exact"]
        manifest["escalation_ladder"] = [
            {
                "stage_id": "coarse",
                "arithmetic": "integer",
                "advance_condition": "advance to exact",
            },
            {
                "stage_id": "exact",
                "arithmetic": "integer",
                "advance_condition": "stop",
            },
        ]
        manager = self.store.experiments()
        started = manager.start(
            task_card=self.card,
            manifest=manifest,
        )
        directory = Path(started["directory"])
        manager.event(
            task_card=self.card,
            experiment_id=started["experiment_id"],
            payload={
                "event": "stage_completed",
                "stage": "coarse",
                "advance_condition_disposition": "advance",
            },
        )
        checkpoint = directory / "checkpoints" / "coarse.json"
        checkpoint.write_text('{"stage": "coarse"}\n', encoding="utf-8")
        from mathgraph.contracts import sha256_json

        compatibility = {"python": "3"}
        checkpoint_event_id = manager.event(
            task_card=self.card,
            experiment_id=started["experiment_id"],
            payload={
                "event": "checkpoint",
                "checkpoint_path": "checkpoints/coarse.json",
                "checkpoint_sha256": hashlib.sha256(
                    checkpoint.read_bytes()
                ).hexdigest(),
                "completed_stage": "coarse",
                "resume_compatibility_hash": sha256_json(
                    compatibility
                ),
            },
        )
        manager.event(
            task_card=self.card,
            experiment_id=started["experiment_id"],
            payload={
                "event": "stage_completed",
                "stage": "exact",
                "advance_condition_disposition": "stop",
            },
        )
        resumed = manager.validate_resume(
            task_card=self.card,
            experiment_id=started["experiment_id"],
            checkpoint_event_id=checkpoint_event_id,
            current_compatibility=compatibility,
        )
        self.assertEqual(resumed["resume_from_stage"], "coarse")
        checkpoint.write_text('{"stage": "tampered"}\n', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "bytes changed"):
            manager.validate_resume(
                task_card=self.card,
                experiment_id=started["experiment_id"],
                checkpoint_event_id=checkpoint_event_id,
                current_compatibility=compatibility,
            )

    def test_checkpoint_must_be_in_checkpoint_directory(self) -> None:
        manager = self.store.experiments()
        started = manager.start(
            task_card=self.card,
            manifest=self._experiment_manifest(),
        )
        directory = Path(started["directory"])
        manager.event(
            task_card=self.card,
            experiment_id=started["experiment_id"],
            payload={
                "event": "stage_completed",
                "stage": "exact",
                "advance_condition_disposition": "stop",
            },
        )
        outside = directory / "mutable-work.json"
        outside.write_text('{"value": 2}\n', encoding="utf-8")
        from mathgraph.contracts import sha256_json

        with self.assertRaisesRegex(ValueError, "checkpoint is missing"):
            manager.event(
                task_card=self.card,
                experiment_id=started["experiment_id"],
                payload={
                    "event": "checkpoint",
                    "checkpoint_path": "mutable-work.json",
                    "checkpoint_sha256": hashlib.sha256(
                        outside.read_bytes()
                    ).hexdigest(),
                    "completed_stage": "exact",
                    "resume_compatibility_hash": sha256_json(
                        {"python": "3"}
                    ),
                },
            )

    def test_experiment_finalize_copies_selected_outputs_and_hashes_them(self) -> None:
        manager = self.store.experiments()
        started = manager.start(
            task_card=self.card,
            manifest=self._experiment_manifest(),
        )
        self._complete_exact_stage(manager, started["experiment_id"])
        result = Path(started["directory"]) / "result.txt"
        result.write_text("2\n", encoding="utf-8")
        receipt = manager.finalize(
            task_card=self.card,
            experiment_id=started["experiment_id"],
            selected_paths=["result.txt"],
        )
        output = self.root / receipt["selected_outputs"][0]["path"]
        self.assertEqual(output.read_bytes(), b"2\n")
        self.assertEqual(
            receipt["selected_outputs"][0]["sha256"],
            hashlib.sha256(b"2\n").hexdigest(),
        )

    def test_finalize_preflights_destination_collisions_before_copy(
        self,
    ) -> None:
        manager = self.store.experiments()
        started = manager.start(
            task_card=self.card,
            manifest=self._experiment_manifest(),
        )
        directory = Path(started["directory"])
        self._complete_exact_stage(manager, started["experiment_id"])
        for folder, value in (("a", "first\n"), ("b", "second\n")):
            nested = directory / folder
            nested.mkdir()
            (nested / "same.txt").write_text(value, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "destination name collision"):
            manager.finalize(
                task_card=self.card,
                experiment_id=started["experiment_id"],
                selected_paths=["a/same.txt", "b/same.txt"],
            )
        self.assertFalse(
            (self.artifact_dir / "same.txt").exists()
        )
        self.assertFalse(
            (directory / "final_receipt.json").exists()
        )

    def test_finalized_experiment_rejects_new_events(self) -> None:
        manager = self.store.experiments()
        started = manager.start(
            task_card=self.card,
            manifest=self._experiment_manifest(),
        )
        directory = Path(started["directory"])
        self._complete_exact_stage(manager, started["experiment_id"])
        (directory / "result.txt").write_text("2\n", encoding="utf-8")
        manager.finalize(
            task_card=self.card,
            experiment_id=started["experiment_id"],
            selected_paths=["result.txt"],
        )
        before = (directory / "events.jsonl").read_bytes()
        with self.assertRaisesRegex(ValueError, "finalized experiment"):
            manager.event(
                task_card=self.card,
                experiment_id=started["experiment_id"],
                payload={
                    "event": "heartbeat",
                    "stage": "exact",
                    "latest_check": "late mutation",
                },
            )
        self.assertEqual(
            before,
            (directory / "events.jsonl").read_bytes(),
        )

    def test_unselected_work_file_is_not_an_artifact(self) -> None:
        manager = self.store.experiments()
        started = manager.start(
            task_card=self.card,
            manifest=self._experiment_manifest(),
        )
        directory = Path(started["directory"])
        self._complete_exact_stage(manager, started["experiment_id"])
        (directory / "selected.txt").write_text("yes\n", encoding="utf-8")
        (directory / "scratch.txt").write_text("no\n", encoding="utf-8")
        receipt = manager.finalize(
            task_card=self.card,
            experiment_id=started["experiment_id"],
            selected_paths=["selected.txt"],
        )
        artifact_paths = {
            item["path"] for item in receipt["selected_outputs"]
        }
        self.assertFalse(any(path.endswith("scratch.txt") for path in artifact_paths))
        self.assertFalse((self.artifact_dir / "scratch.txt").exists())

    def _submission_and_interface(self) -> tuple[dict, dict, Fact]:
        predecessor = Fact(
            problem_id="v4-computation",
            author="author",
            predecessors=[],
            statement="A predecessor statement.",
            proof="SECRET PREDECESSOR PROOF",
        )
        interface = build_statement_interface(
            fact=predecessor,
            stored_fact_sha256="1" * 64,
            acceptance_event_sha256="2" * 64,
            admission_review_id="3" * 64,
            workflow_evidence_version=3,
        )
        submission = {
            "fact_id": "f" * 16,
            "submission_sha256": "a" * 64,
            "statement": "[CLAIM:MAIN] Result.",
            "proof": "Proof using the predecessor interface.",
            "predecessors": [predecessor.fact_id],
            "external_refs": [],
            "computational_evidence": [],
        }
        return submission, interface, predecessor

    def _legacy_verification_bundles(self) -> VerificationBundleStore:
        """Explicit unit-test seam for pre-unified low-level bundle bytes."""

        return VerificationBundleStore._for_inherited_chalk_fixture(
            self.root
        )

    def test_closed_packet_bundle_contains_no_computation_bytes(self) -> None:
        submission, interface, predecessor = self._submission_and_interface()
        bundle = self._legacy_verification_bundles().create(
            submission=submission,
            predecessor_statements={
                predecessor.fact_id: predecessor.statement
            },
            interfaces={predecessor.fact_id: interface},
            verification_plan={
                "mode": "closed_packet",
                "authorized_artifact_roles": [],
                "required_checks": ["mathematical"],
            },
        )
        packet = (
            Path(bundle["bundle_path"]) / "packet.md"
        ).read_text()
        self.assertIn(predecessor.statement, packet)
        self.assertNotIn(predecessor.proof, packet)
        self.assertFalse((Path(bundle["bundle_path"]) / "artifacts").exists())

    def test_verifier_bundle_contains_statement_interfaces_not_predecessor_proofs(self) -> None:
        submission, interface, predecessor = self._submission_and_interface()
        bundle = self._legacy_verification_bundles().create(
            submission=submission,
            predecessor_statements={
                predecessor.fact_id: predecessor.statement
            },
            interfaces={predecessor.fact_id: interface},
            verification_plan={
                "mode": "closed_packet",
                "authorized_artifact_roles": [],
                "required_checks": ["mathematical"],
            },
        )
        packet = (Path(bundle["bundle_path"]) / "packet.md").read_text()
        self.assertIn(predecessor.statement, packet)
        self.assertNotIn(predecessor.proof, packet)
        self.assertTrue(
            (
                Path(bundle["bundle_path"])
                / "interfaces"
                / f"{predecessor.fact_id}.json"
            ).is_file()
        )

    def test_work_checkpoint_cannot_enter_verification_bundle(self) -> None:
        checkpoint = (
            self.root
            / "rounds"
            / "fixture"
            / "work"
            / "assignment"
            / "checkpoints"
            / "state.json"
        )
        checkpoint.parent.mkdir(parents=True)
        checkpoint.write_text('{"partial":true}\n', encoding="utf-8")
        digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        submission = {
            "fact_id": "9" * 16,
            "submission_sha256": "8" * 64,
            "statement": "[CLAIM:C1] Candidate.",
            "proof": "[COMP:toy]",
            "predecessors": [],
            "external_refs": [],
            "computational_evidence": [
                {
                    "key": "toy",
                    "artifact_refs": [
                        {
                            "role": "checkpoint",
                            "path": checkpoint.relative_to(self.root).as_posix(),
                            "sha256": digest,
                        }
                    ],
                }
            ],
        }
        with self.assertRaisesRegex(ValueError, "checkpoint"):
            self._legacy_verification_bundles().create(
                submission=submission,
                predecessor_statements={},
                interfaces={},
                verification_plan={
                    "mode": "artifact_replay",
                    "authorized_artifact_roles": ["checkpoint"],
                    "required_checks": ["execute"],
                },
                authorized_artifacts=[
                    {"key": "toy", "role": "checkpoint"}
                ],
            )

    def test_artifact_replay_bundle_contains_exact_authorized_bytes_only(self) -> None:
        data = b"print(2)\\n"
        artifact_path = self.root / "authorized.py"
        artifact_path.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        submission = {
            "fact_id": "e" * 16,
            "submission_sha256": "b" * 64,
            "statement": "[CLAIM:MAIN] Computed result.",
            "proof": "[COMP:toy]",
            "predecessors": [],
            "external_refs": [],
            "computational_evidence": [
                {
                    "key": "toy",
                    "artifact_refs": [
                        {
                            "role": "entrypoint",
                            "path": "authorized.py",
                            "sha256": digest,
                        }
                    ],
                }
            ],
        }
        bundle = self._legacy_verification_bundles().create(
            submission=submission,
            predecessor_statements={},
            interfaces={},
            verification_plan={
                "mode": "artifact_replay",
                "authorized_artifact_roles": ["entrypoint"],
                "required_checks": ["execute"],
            },
            authorized_artifacts=[
                {"key": "toy", "role": "entrypoint"}
            ],
        )
        manifest = self.store.verification_bundles().verify(
            bundle["bundle_sha256"]
        )
        copied = (
            Path(bundle["bundle_path"])
            / manifest["artifacts"][0]["bundle_relpath"]
        )
        self.assertEqual(copied.read_bytes(), data)
        (Path(bundle["bundle_path"]) / "unauthorized.txt").write_text("x")
        with self.assertRaisesRegex(ValueError, "unauthorized"):
            self.store.verification_bundles().verify(
                bundle["bundle_sha256"]
            )

    def test_followup_bundle_cannot_resolve_mathematical_rejection(self) -> None:
        review = {
            "schema_version": 4,
            "policy_revision": "mathgraph-0.3.0",
            "fact_id": "d" * 16,
            "submission_sha256": "1" * 64,
            "bundle_sha256": "2" * 64,
            "verdict": "reject",
            "findings": [
                {
                    "id": "F1",
                    "severity": "critical_error",
                    "class": "mathematical",
                    "description": "False step.",
                    "repair_hint": "New proof.",
                }
            ],
            "prior_review_dispositions": [],
            "reviewer": "fresh-verifier",
            "host_attestation": {
                "host": "test",
                "agent_id": "fresh",
                "isolation": "fresh_context",
                "fork_turns": "none",
                "allowed_bundle_sha256": "2" * 64,
            },
        }
        validate_review_v4(review)
        with self.assertRaisesRegex(ValueError, "new submission"):
            VerificationBundleStore.validate_followup_eligibility(review)

    def test_followup_bundle_can_resolve_evidence_access(self) -> None:
        review = {
            "schema_version": 4,
            "policy_revision": "mathgraph-0.3.0",
            "fact_id": "c" * 16,
            "submission_sha256": "1" * 64,
            "bundle_sha256": "2" * 64,
            "verdict": "reject",
            "findings": [
                {
                    "id": "F1",
                    "severity": "gap",
                    "class": "evidence_access",
                    "description": "Artifact not supplied.",
                    "repair_hint": "Expand bundle.",
                }
            ],
            "prior_review_dispositions": [],
            "reviewer": "fresh-verifier",
            "host_attestation": {
                "host": "test",
                "agent_id": "fresh",
                "isolation": "fresh_context",
                "fork_turns": "none",
                "allowed_bundle_sha256": "2" * 64,
            },
        }
        VerificationBundleStore.validate_followup_eligibility(review)

    def _record_v4_review(
        self,
        *,
        fact_id: str,
        submission_sha256: str,
        bundle_sha256: str,
        verdict: str,
        findings: list[dict],
        dispositions: list[dict],
    ) -> str:
        path = self.store.record_review(
            {
                "schema_version": 4,
                "policy_revision": "mathgraph-0.3.0",
                "fact_id": fact_id,
                "submission_sha256": submission_sha256,
                "bundle_sha256": bundle_sha256,
                "verdict": verdict,
                "findings": findings,
                "prior_review_dispositions": dispositions,
                "reviewer": "fresh-verifier",
                "host_attestation": {
                    "host": "test-host",
                    "agent_id": "fresh-verifier",
                    "isolation": "fresh_context",
                    "fork_turns": "none",
                    "allowed_bundle_sha256": bundle_sha256,
                },
            }
        )
        return path.stem

    def test_v4_verification_review_and_admission_end_to_end(self) -> None:
        self._use_inherited_chalk_compatibility_store()
        fact = Fact(
            problem_id="v4-computation",
            author="worker",
            predecessors=[],
            statement="[CLAIM:C1] The direct toy identity holds.",
            proof="Both sides are identical.",
        )
        fact_id = self.store.submit(fact, worker="worker")
        assignment = create_verifier_assignment(self.store, fact_id)
        self.assertEqual(
            set(assignment["spawn_contract"]["capability"]),
            {
                "bundle_path",
                "bundle_sha256",
                "review_return_path",
                "fork_turns",
            },
        )
        review_id = self._record_v4_review(
            fact_id=fact_id,
            submission_sha256=assignment["submission_sha256"],
            bundle_sha256=assignment["bundle_sha256"],
            verdict="correct",
            findings=[],
            dispositions=[],
        )
        self.store.admit(fact_id, review_id=review_id)
        self.assertEqual(self.store.get_fact(fact_id).statement, fact.statement)
        interface = self.store.statement_interface(fact_id)
        self.assertEqual(interface["admission_review_id"], review_id)
        self.assertTrue(self.store.audit().current_ok)

    def test_correct_review_disposes_every_prior_finding(self) -> None:
        self._use_inherited_chalk_compatibility_store()
        result = self._artifact("result-followup.txt", b"2\n")
        ledger = self._artifact("ledger-followup.json", b'{"value":2}\n')
        evidence = self._evidence(result)
        evidence["artifact_refs"].append(
            {
                "role": "ledger",
                "path": ledger["path"],
                "sha256": ledger["sha256"],
            }
        )
        evidence["expected_outputs"].append(
            {"role": "ledger", "sha256": ledger["sha256"]}
        )
        fact = Fact(
            problem_id="v4-computation",
            author="worker",
            predecessors=[],
            statement="[CLAIM:C1] The replayed value is two.",
            proof="Exact replay gives two. [COMP:toy]",
            computational_evidence=[evidence],
        )
        plan = {
            "mode": "artifact_replay",
            "authorized_artifact_roles": ["result", "ledger"],
            "required_checks": ["execute", "byte_compare"],
        }
        fact_id = self.store.submit(
            fact,
            worker="worker",
            artifacts=[result, ledger],
            verification_plan=plan,
        )
        initial = create_verifier_assignment(
            self.store,
            fact_id,
            authorized_artifacts=[{"key": "toy", "role": "result"}],
        )
        rejected_id = self._record_v4_review(
            fact_id=fact_id,
            submission_sha256=initial["submission_sha256"],
            bundle_sha256=initial["bundle_sha256"],
            verdict="reject",
            findings=[
                {
                    "id": "F-EVIDENCE",
                    "severity": "gap",
                    "class": "evidence_access",
                    "description": "The result ledger was not available.",
                    "repair_hint": "Add the already hash-bound ledger bytes.",
                }
            ],
            dispositions=[],
        )
        followup = create_verifier_assignment(
            self.store,
            fact_id,
            authorized_artifacts=[
                {"key": "toy", "role": "result"},
                {"key": "toy", "role": "ledger"},
            ],
            supersedes_bundle_id=initial["bundle_id"],
            prior_review_id=rejected_id,
        )
        with self.assertRaisesRegex(ValueError, "disposition"):
            self._record_v4_review(
                fact_id=fact_id,
                submission_sha256=followup["submission_sha256"],
                bundle_sha256=followup["bundle_sha256"],
                verdict="correct",
                findings=[],
                dispositions=[],
            )
        accepted_id = self._record_v4_review(
            fact_id=fact_id,
            submission_sha256=followup["submission_sha256"],
            bundle_sha256=followup["bundle_sha256"],
            verdict="correct",
            findings=[],
            dispositions=[
                {
                    "prior_review_id": rejected_id,
                    "finding_id": "F-EVIDENCE",
                    "disposition": "resolved_by_bundle_expansion",
                    "explanation": "The follow-up includes the bound ledger bytes.",
                }
            ],
        )
        self.store.admit(fact_id, review_id=accepted_id)
        self.assertIn(fact_id, self.store.fact_ids())
        report = self.store.audit()
        self.assertTrue(report.current_ok, report.errors)

    def test_bundle_tamper_blocks_review_and_admission(self) -> None:
        self._use_inherited_chalk_compatibility_store()
        fact = Fact(
            problem_id="v4-computation",
            author="worker",
            predecessors=[],
            statement="[CLAIM:C1] A tamper-sensitive theorem.",
            proof="Direct.",
        )
        fact_id = self.store.submit(fact, worker="worker")
        assignment = create_verifier_assignment(self.store, fact_id)
        review_id = self._record_v4_review(
            fact_id=fact_id,
            submission_sha256=assignment["submission_sha256"],
            bundle_sha256=assignment["bundle_sha256"],
            verdict="correct",
            findings=[],
            dispositions=[],
        )
        packet = Path(assignment["bundle_path"]) / "packet.md"
        packet.write_text("tampered\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "tampered"):
            self.store.admit(fact_id, review_id=review_id)
        self.assertNotIn(fact_id, self.store.fact_ids())

    def test_verifier_has_no_project_cli(self) -> None:
        self._use_inherited_chalk_compatibility_store()
        fact = Fact(
            problem_id="v4-computation",
            author="worker",
            predecessors=[],
            statement="[CLAIM:C1] Capability isolation holds.",
            proof="By inspection.",
        )
        fact_id = self.store.submit(fact, worker="worker")
        assignment = create_verifier_assignment(self.store, fact_id)
        self.assertEqual(allowed_commands_for_workflow("verifier", 4), set())
        task = assignment["spawn_contract"]["task"]
        self.assertIn("Do not invoke a project CLI", task)
        self.assertNotIn("mgraph", assignment["spawn_contract"]["capability"])


if __name__ == "__main__":
    unittest.main()

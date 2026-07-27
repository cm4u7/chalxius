from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from mathgraph.blackboard import make_edge, make_node
from mathgraph.cli import main as cli_main
from mathgraph.collaboration import (
    ABORT_ID_RE,
    CORE_FAILURE_ID_RE,
    PulseStore,
)
from mathgraph.orchestrator import (
    create_round,
    ingest_return,
    preflight_return,
    validate_return,
)
from mathgraph.store import MathGraphStore


class CollaborationPulseAbortTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = MathGraphStore(self.root)
        self.store.initialize(
            project_id="v4-pulse-abort",
            title="V4 pulse abort",
            workflow_evidence_version=4,
        )
        memory_ids = [
            self.store.memory_add(
                {
                    "kind": "direction",
                    "claim": f"Abort fixture direction {index}.",
                    "rationale": "Independent pulse lifecycle fixture.",
                    "suggested_actions": ["prove"],
                },
                actor="main",
            )
            for index in range(3)
        ]
        self.round = create_round(
            self.store,
            workers=3,
            memory_ids=memory_ids,
            host_task_scope_id="hosttask-" + "a" * 32,
        )
        self.pulses = PulseStore(
            self.root,
            mutation_lock=self.store.mutation_lock,
        )
        self.commitments = [
            self.pulses.make_wave1_commitment(
                round_id=self.round["round_id"],
                assignment_id=assignment["assignment_id"],
                criticality="optional" if index == 2 else "core",
            )
            for index, assignment in enumerate(
                self.round["assignments"]
            )
        ]
        self.plan = self.pulses.create_plan(
            wave1_commitments=self.commitments,
            minimum_wave1_contributors=2,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _pulse_bytes(self) -> dict[str, bytes]:
        pulse_root = (
            self.root
            / "blackboard"
            / "pulses"
            / "by-hash"
            / self.plan["pulse_id"]
        )
        return {
            path.relative_to(pulse_root).as_posix(): path.read_bytes()
            for path in sorted(pulse_root.rglob("*"))
            if path.is_file() and not path.is_symlink()
        }

    def _write_graph_preflight_failure(
        self,
        index: int = 0,
    ) -> tuple[Path, str]:
        assignment = self.round["assignments"][index]
        card_path = Path(assignment["task_card_path"])
        card = json.loads(card_path.read_text(encoding="utf-8"))
        root_space = next(
            node_id
            for node_id, node in self.store.blackboard().nodes().items()
            if node["node_type"] == "space"
        )
        node = make_node(
            node_type="mechanism",
            logical_key="failed-final-return",
            payload={"mechanism": "failed graph preflight"},
            created_by_assignment_id=card["assignment_id"],
        )
        placed = make_edge(
            edge_type="placed_in",
            source_node_id=node["node_id"],
            target_node_id=root_space,
            payload={},
            created_by_assignment_id=card["assignment_id"],
        )
        unregistered = make_edge(
            edge_type="supports",
            source_node_id=node["node_id"],
            target_node_id=root_space,
            payload={},
            created_by_assignment_id=card["assignment_id"],
        )
        payload = {
            "schema_version": 4,
            "policy_revision": "mathgraph-0.3.0",
            "protocol": "mathgraph-agent-v4",
            "project_id": card["project_id"],
            "round_id": card["round_id"],
            "assignment_id": card["assignment_id"],
            "assignment_sha256": card["assignment_sha256"],
            "task_card_sha256": hashlib.sha256(
                card_path.read_bytes()
            ).hexdigest(),
            "blackboard_snapshot_sha256": card[
                "blackboard_snapshot_sha256"
            ],
            "worker": card["worker_id"],
            "memory_id": card["memory_id"],
            "mode": card["mode"],
            "outcome": "dead_end",
            "obligation_ledger": [],
            "blackboard_graph_delta": {
                "base_snapshot_id": card["blackboard_view"][
                    "snapshot_id"
                ],
                "add_nodes": [node],
                "add_edges": [placed, unregistered],
            },
            "narrative_summary": (
                "This final handoff deliberately fails graph preflight."
            ),
            "claim": "Pulse abort fixture",
            "method": "Typed graph preflight",
            "failure_mode": "Unregistered core-like edge type",
            "what_remains_open": "A new pulse with a new assignment",
            "artifacts": [],
        }
        return_path = Path(assignment["return_path"])
        return_path.write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
        return (
            return_path,
            hashlib.sha256(return_path.read_bytes()).hexdigest(),
        )

    def test_failed_core_final_return_ends_in_explicit_abort(
        self,
    ) -> None:
        return_path, final_sha256 = (
            self._write_graph_preflight_failure()
        )
        with self.assertRaisesRegex(
            ValueError,
            "unregistered core-like blackboard edge type",
        ):
            validate_return(
                self.store,
                self.round["round_id"],
                self.round["assignments"][0]["assignment_id"],
            )
        self.assertEqual(
            self.pulses.core_failure_receipts(
                self.plan["pulse_id"]
            ),
            [],
        )
        self.assertEqual(
            self.pulses.status(self.plan["pulse_id"])["state"],
            "wave1_open",
        )
        with self.assertRaisesRegex(
            ValueError,
            "unregistered core-like blackboard edge type",
        ):
            ingest_return(
                self.store,
                self.round["round_id"],
                self.round["assignments"][0]["assignment_id"],
                worker_final_sha256=final_sha256,
            )
        self.assertFalse(
            return_path.with_suffix(".receipt.json").exists()
        )
        with self.assertRaisesRegex(
            ValueError,
            "aborted pulse cannot",
        ):
            self.pulses.void_optional(
                self.plan["pulse_id"],
                self.commitments[0]["commitment_id"],
                reason="a core failure is not optional",
            )

        abort = self.pulses.abort_receipt(
            self.plan["pulse_id"]
        )
        failures = self.pulses.core_failure_receipts(
            self.plan["pulse_id"]
        )
        self.assertEqual(len(failures), 1)
        failure = failures[0]

        self.assertIsNotNone(
            ABORT_ID_RE.fullmatch(abort["abort_id"])
        )
        self.assertIsNotNone(
            CORE_FAILURE_ID_RE.fullmatch(failure["failure_id"])
        )
        self.assertEqual(
            abort["plan_sha256"],
            self.plan["plan_sha256"],
        )
        self.assertEqual(
            abort["core_failure_id"],
            failure["failure_id"],
        )
        self.assertEqual(
            failure["return_sha256"],
            final_sha256,
        )
        self.assertEqual(
            failure["worker_final_sha256"],
            final_sha256,
        )
        self.assertEqual(
            failure["error_class"],
            "ValueError",
        )
        self.assertIn(
            "unregistered core-like blackboard edge type",
            failure["error_message"],
        )
        self.assertEqual(
            hashlib.sha256(return_path.read_bytes()).hexdigest(),
            final_sha256,
        )
        self.assertFalse(
            return_path.with_suffix(".receipt.json").exists()
        )
        status = self.pulses.status(self.plan["pulse_id"])
        self.assertEqual(status["state"], "aborted")
        self.assertFalse(status["procedural_ready"])
        self.assertFalse(status["machine_verified_ready"])
        audit = self.pulses.audit(self.plan["pulse_id"])
        self.assertTrue(audit["ok"], audit["errors"])
        self.assertEqual(audit["warnings"], [])
        project_audit = self.store.audit()
        self.assertTrue(project_audit.ok, project_audit.errors)

    def test_draft_preflight_failure_is_zero_write_and_pulse_stays_open(
        self,
    ) -> None:
        return_path, _ = self._write_graph_preflight_failure()
        assignment = self.round["assignments"][0]
        draft_path = (
            Path(assignment["work_dir_path"])
            / "invalid-core-draft.json"
        )
        draft_path.write_bytes(return_path.read_bytes())
        return_path.unlink()
        before = {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in sorted(self.root.rglob("*"))
            if path.is_file() and not path.is_symlink()
        }
        with self.assertRaisesRegex(
            ValueError,
            "unregistered core-like blackboard edge type",
        ):
            preflight_return(
                self.store,
                self.round["round_id"],
                assignment["assignment_id"],
                input_path=draft_path,
            )
        after = {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in sorted(self.root.rglob("*"))
            if path.is_file() and not path.is_symlink()
        }
        self.assertEqual(after, before)
        self.assertFalse(return_path.exists())
        self.assertEqual(
            self.pulses.core_failure_receipts(
                self.plan["pulse_id"]
            ),
            [],
        )
        self.assertEqual(
            self.pulses.status(self.plan["pulse_id"])["state"],
            "wave1_open",
        )

    def test_barrier_rejects_canonical_core_without_ingestion_receipt(
        self,
    ) -> None:
        self._write_graph_preflight_failure()
        with self.assertRaisesRegex(
            ValueError,
            "canonical return exists without an ingestion receipt",
        ):
            self.pulses.derive_barrier(
                self.plan["pulse_id"],
                after_snapshot_id=self.plan["wave1_snapshot_id"],
                review_commitments=[],
            )
        status = self.pulses.status(self.plan["pulse_id"])
        self.assertTrue(
            any(
                "run ingest-return or pulse-abort" in blocker
                for blocker in status["blockers"]
            ),
            status,
        )

    def test_optional_ingest_failure_does_not_abort_whole_pulse(
        self,
    ) -> None:
        return_path, final_sha256 = (
            self._write_graph_preflight_failure(2)
        )
        assignment = self.round["assignments"][2]
        with self.assertRaisesRegex(
            ValueError,
            "unregistered core-like blackboard edge type",
        ):
            ingest_return(
                self.store,
                self.round["round_id"],
                assignment["assignment_id"],
                worker_final_sha256=final_sha256,
            )
        self.assertTrue(return_path.exists())
        self.assertEqual(
            self.pulses.core_failure_receipts(
                self.plan["pulse_id"]
            ),
            [],
        )
        with self.assertRaisesRegex(
            ValueError,
            "pulse abort receipt is missing",
        ):
            self.pulses.abort_receipt(self.plan["pulse_id"])
        void = self.pulses.void_optional(
            self.plan["pulse_id"],
            self.commitments[2]["commitment_id"],
            reason="optional invalid final return",
        )
        self.assertTrue(void["void_id"].startswith("bbvoid-"))
        with self.assertRaisesRegex(
            ValueError,
            "voided optional commitment cannot ingest",
        ):
            ingest_return(
                self.store,
                self.round["round_id"],
                assignment["assignment_id"],
                worker_final_sha256=final_sha256,
            )
        self.assertEqual(
            self.pulses.status(self.plan["pulse_id"])["state"],
            "wave1_open",
        )

    def test_auto_abort_retry_is_idempotent(self) -> None:
        _, final_sha256 = self._write_graph_preflight_failure()
        assignment = self.round["assignments"][0]
        with self.assertRaises(ValueError):
            ingest_return(
                self.store,
                self.round["round_id"],
                assignment["assignment_id"],
                worker_final_sha256=final_sha256,
            )
        before = self._pulse_bytes()
        with self.assertRaisesRegex(
            ValueError,
            "aborted pulse cannot ingest",
        ):
            ingest_return(
                self.store,
                self.round["round_id"],
                assignment["assignment_id"],
                worker_final_sha256=final_sha256,
            )
        self.assertEqual(self._pulse_bytes(), before)

    def test_repair_or_delete_after_failure_cannot_revive_pulse(
        self,
    ) -> None:
        return_path, final_sha256 = (
            self._write_graph_preflight_failure()
        )
        assignment = self.round["assignments"][0]
        with self.assertRaises(ValueError):
            ingest_return(
                self.store,
                self.round["round_id"],
                assignment["assignment_id"],
                worker_final_sha256=final_sha256,
            )
        pulse_before = self._pulse_bytes()
        return_path.chmod(0o600)
        return_path.write_text('{"repaired":true}', encoding="utf-8")
        repaired_sha256 = hashlib.sha256(
            return_path.read_bytes()
        ).hexdigest()
        with self.assertRaisesRegex(
            ValueError,
            "aborted pulse cannot ingest",
        ):
            ingest_return(
                self.store,
                self.round["round_id"],
                assignment["assignment_id"],
                worker_final_sha256=repaired_sha256,
            )
        return_path.unlink()
        with self.assertRaisesRegex(
            ValueError,
            "aborted pulse cannot ingest",
        ):
            ingest_return(
                self.store,
                self.round["round_id"],
                assignment["assignment_id"],
                worker_final_sha256=final_sha256,
            )
        self.assertEqual(self._pulse_bytes(), pulse_before)
        self.assertEqual(
            self.pulses.status(self.plan["pulse_id"])["state"],
            "aborted",
        )
        audit = self.pulses.audit(self.plan["pulse_id"])
        self.assertFalse(audit["ok"])
        self.assertTrue(
            any(
                "canonical return is missing" in error
                for error in audit["errors"]
            ),
            audit["errors"],
        )

    def test_cli_ingest_failure_records_abort_without_deadlock(
        self,
    ) -> None:
        _, final_sha256 = self._write_graph_preflight_failure()
        assignment = self.round["assignments"][0]
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = cli_main(
                [
                    "--root",
                    str(self.root),
                    "--role",
                    "main",
                    "ingest-return",
                    self.round["round_id"],
                    assignment["assignment_id"],
                    "--worker-final-sha256",
                    final_sha256,
                ]
            )
        self.assertEqual(code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn(
            "unregistered core-like blackboard edge type",
            stderr.getvalue(),
        )
        self.assertEqual(
            self.pulses.status(self.plan["pulse_id"])["state"],
            "aborted",
        )
        self.assertEqual(
            len(
                self.pulses.core_failure_receipts(
                    self.plan["pulse_id"]
                )
            ),
            1,
        )

    def test_audit_rejects_failure_evidence_without_abort(self) -> None:
        _, final_sha256 = self._write_graph_preflight_failure()
        assignment = self.round["assignments"][0]
        with self.assertRaises(ValueError):
            ingest_return(
                self.store,
                self.round["round_id"],
                assignment["assignment_id"],
                worker_final_sha256=final_sha256,
            )
        abort_path = (
            self.root
            / "blackboard"
            / "pulses"
            / "by-hash"
            / self.plan["pulse_id"]
            / "abort.json"
        )
        abort_path.unlink()
        audit = self.pulses.audit(self.plan["pulse_id"])
        self.assertFalse(audit["ok"])
        self.assertTrue(
            any(
                "failure evidence exists without a pulse abort"
                in error
                for error in audit["errors"]
            ),
            audit["errors"],
        )

    def test_abort_is_write_once_and_blocks_later_pulse_actions(
        self,
    ) -> None:
        first = self.pulses.abort(
            self.plan["pulse_id"],
            failure_phase="wave1_graph_preflight",
            actor="main",
            reason="The core final return failed graph preflight.",
        )
        replay = self.pulses.abort(
            self.plan["pulse_id"],
            failure_phase="wave1_graph_preflight",
            actor="main",
            reason="The core final return failed graph preflight.",
        )
        self.assertEqual(first, replay)
        self.assertEqual(
            self.pulses.abort_receipt(self.plan["pulse_id"])[
                "abort_id"
            ],
            first["abort_id"],
        )
        with self.assertRaisesRegex(
            ValueError,
            "immutable pulse evidence collision",
        ):
            self.pulses.abort(
                self.plan["pulse_id"],
                failure_phase="wave1_graph_preflight",
                actor="main",
                reason="A different retrospective explanation.",
            )

        blocked_calls = (
            lambda: self.pulses.derive_barrier(
                self.plan["pulse_id"],
                after_snapshot_id=self.plan["wave1_snapshot_id"],
                review_commitments=[],
            ),
            lambda: self.pulses.derive_closure(
                self.plan["pulse_id"]
            ),
            lambda: self.pulses.record_host_dispatch(
                self.plan["pulse_id"],
                self.commitments[0]["commitment_id"],
                issuer="test-host",
                host_context_id="fresh-test-context",
            ),
            lambda: self.pulses.void_optional(
                self.plan["pulse_id"],
                self.commitments[2]["commitment_id"],
                reason="too late",
            ),
        )
        for call in blocked_calls:
            with self.subTest(call=call):
                with self.assertRaisesRegex(
                    ValueError,
                    "aborted pulse cannot",
                ):
                    call()

    def test_existing_closure_marker_blocks_abort(self) -> None:
        closure_path = (
            self.root
            / "blackboard"
            / "pulses"
            / "by-hash"
            / self.plan["pulse_id"]
            / "closure.json"
        )
        closure_path.write_text("{}\n", encoding="utf-8")
        with self.assertRaisesRegex(
            ValueError,
            "closed pulse cannot be aborted",
        ):
            self.pulses.abort(
                self.plan["pulse_id"],
                failure_phase="closure",
                reason="too late",
            )
        self.assertFalse(
            closure_path.with_name("abort.json").exists()
        )

    def test_abort_obeys_pulse_control_hard_caps(self) -> None:
        with patch.dict(
            "mathgraph.collaboration.DEFAULT_HARD_CAPS",
            {"max_pulse_control_records": 1},
            clear=False,
        ):
            with self.assertRaisesRegex(
                ValueError,
                "record count hard cap exceeded",
            ):
                self.pulses.abort(
                    self.plan["pulse_id"],
                    failure_phase="wave1_graph_preflight",
                    reason="the cap must fail before visibility",
                )
        self.assertFalse(
            (
                self.root
                / "blackboard"
                / "pulses"
                / "by-hash"
                / self.plan["pulse_id"]
                / "abort.json"
            ).exists()
        )

    def test_audit_revalidates_abort_content_id(self) -> None:
        self.pulses.abort(
            self.plan["pulse_id"],
            failure_phase="wave1_graph_preflight",
            reason="The immutable reason.",
        )
        abort_path = (
            self.root
            / "blackboard"
            / "pulses"
            / "by-hash"
            / self.plan["pulse_id"]
            / "abort.json"
        )
        payload = json.loads(abort_path.read_text(encoding="utf-8"))
        payload["reason"] = "A forged replacement reason."
        abort_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        audit = self.pulses.audit(self.plan["pulse_id"])
        self.assertFalse(audit["ok"])
        self.assertTrue(
            any(
                "pulse abort id/hash mismatch" in error
                for error in audit["errors"]
            ),
            audit["errors"],
        )


if __name__ == "__main__":
    unittest.main()

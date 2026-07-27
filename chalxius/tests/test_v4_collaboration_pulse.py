from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mathgraph.blackboard import make_edge, make_node
from mathgraph.collaboration import PulseStore
from mathgraph.contracts import canonical_json_bytes
from mathgraph.orchestrator import (
    create_round,
    ingest_return,
    preflight_return,
    validate_return,
)
from mathgraph.store import MathGraphStore


class CollaborationPulseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = MathGraphStore(self.root)
        self.store.initialize(
            project_id="v4-collaboration-pulse",
            title="V4 collaboration pulse",
            workflow_evidence_version=4,
        )
        self.root_space = next(
            node_id
            for node_id, node in self.store.blackboard().nodes().items()
            if node["node_type"] == "space"
        )
        self.host_scope = "hosttask-" + "1" * 32
        self.memory_counter = 0
        self.pulses = PulseStore(
            self.root,
            mutation_lock=self.store.mutation_lock,
            trusted_host_issuers={"codex-test-host"},
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _planned_round(self, workers: int) -> dict:
        memory_ids: list[str] = []
        for _ in range(workers):
            self.memory_counter += 1
            memory_ids.append(
                self.store.memory_add(
                    {
                        "kind": "direction",
                        "claim": (
                            "Collaboration pulse direction "
                            f"{self.memory_counter}."
                        ),
                        "rationale": "Independent pulse fixture.",
                        "suggested_actions": ["prove"],
                    },
                    actor="main",
                )
            )
        return create_round(
            self.store,
            workers=workers,
            memory_ids=memory_ids,
            host_task_scope_id=self.host_scope,
        )

    def _file_inventory(self) -> dict[str, bytes]:
        return {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in sorted(self.root.rglob("*"))
            if path.is_file() and not path.is_symlink()
        }

    def _ingest_dead_end(
        self,
        planned: dict,
        index: int,
        *,
        node_key: str,
        cross_edge: dict | None = None,
    ) -> tuple[dict, dict]:
        assignment = planned["assignments"][index]
        card_path = Path(assignment["task_card_path"])
        card = json.loads(card_path.read_text(encoding="utf-8"))
        node = make_node(
            node_type="mechanism",
            logical_key=node_key,
            payload={"mechanism": node_key},
            created_by_assignment_id=card["assignment_id"],
        )
        edges = [
            make_edge(
                edge_type="placed_in",
                source_node_id=node["node_id"],
                target_node_id=self.root_space,
                payload={},
                created_by_assignment_id=card["assignment_id"],
            )
        ]
        if cross_edge is not None:
            edges.append(
                make_edge(
                    edge_type=cross_edge["edge_type"],
                    source_node_id=node["node_id"],
                    target_node_id=cross_edge["target_node_id"],
                    payload=cross_edge["payload"],
                    created_by_assignment_id=card["assignment_id"],
                )
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
                "add_edges": edges,
            },
            "narrative_summary": "Typed exploration boundary.",
            "claim": "Pulse fixture",
            "method": "Independent structural inspection",
            "failure_mode": "No truth claim is made",
            "what_remains_open": "Mathematical verification",
            "artifacts": [],
        }
        return_path = Path(assignment["return_path"])
        return_path.write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
        validated = validate_return(
            self.store,
            planned["round_id"],
            card["assignment_id"],
        )
        receipt = ingest_return(
            self.store,
            planned["round_id"],
            card["assignment_id"],
            worker_final_sha256=validated["return_sha256"],
        )
        return node, receipt

    def _barrier_fixture(self) -> dict:
        wave1 = self._planned_round(2)
        commitments = [
            self.pulses.make_wave1_commitment(
                round_id=wave1["round_id"],
                assignment_id=item["assignment_id"],
            )
            for item in wave1["assignments"]
        ]
        plan = self.pulses.create_plan(
            wave1_commitments=commitments,
        )
        left, _ = self._ingest_dead_end(
            wave1,
            0,
            node_key="wave1-left",
        )
        right, _ = self._ingest_dead_end(
            wave1,
            1,
            node_key="wave1-right",
        )
        wave2 = self._planned_round(1)
        assignment = wave2["assignments"][0]
        review = self.pulses.make_review_commitment(
            pulse_id=plan["pulse_id"],
            round_id=wave2["round_id"],
            assignment_id=assignment["assignment_id"],
            peer_node_id=left["node_id"],
            allowed_edge_types=["refines"],
        )
        barrier = self.pulses.derive_barrier(
            plan["pulse_id"],
            after_snapshot_id=wave2["blackboard_snapshot_id"],
            review_commitments=[review],
        )
        return {
            "wave1": wave1,
            "wave2": wave2,
            "left": left,
            "right": right,
            "plan": plan,
            "review": review,
            "barrier": barrier,
        }

    def _meaningful_payload(self, fixture: dict, source_id: str) -> dict:
        return {
            "exchange_schema_version": 1,
            "pulse_id": fixture["plan"]["pulse_id"],
            "barrier_id": fixture["barrier"]["barrier_id"],
            "commitment_id": fixture["review"]["commitment_id"],
            "peer_node_id": fixture["left"]["node_id"],
            "peer_node_sha256": hashlib.sha256(
                canonical_json_bytes(fixture["left"])
            ).hexdigest(),
            "check": {
                "kind": "scope_audit",
                "method": (
                    "Repeated the peer node's endpoint and scope check "
                    "against the fresh frozen snapshot."
                ),
                "witness_refs": [source_id],
            },
            "disposition": {
                "kind": "no_correction",
                "boundary": (
                    "No correction inside the endpoint/snapshot boundary; "
                    "mathematical truth remains outside this pulse."
                ),
            },
        }

    def test_meaningful_edge_and_trusted_host_receipt_close_ready(
        self,
    ) -> None:
        fixture = self._barrier_fixture()
        assignment_id = fixture["wave2"]["assignments"][0][
            "assignment_id"
        ]
        dispatch = self.pulses.record_host_dispatch(
            fixture["plan"]["pulse_id"],
            fixture["review"]["commitment_id"],
            issuer="codex-test-host",
            host_context_id="fresh-context-wave2-1",
        )
        source = make_node(
            node_type="mechanism",
            logical_key="preview-source",
            payload={"mechanism": "preview-source"},
            created_by_assignment_id=assignment_id,
        )
        node, _ = self._ingest_dead_end(
            fixture["wave2"],
            0,
            node_key="preview-source",
            cross_edge={
                "edge_type": "refines",
                "target_node_id": fixture["left"]["node_id"],
                "payload": self._meaningful_payload(
                    fixture,
                    source["node_id"],
                ),
            },
        )
        self.assertEqual(node["node_id"], source["node_id"])
        status = self.pulses.status(fixture["plan"]["pulse_id"])
        self.assertTrue(status["procedural_ready"])
        self.assertTrue(status["machine_verified_ready"])
        self.assertEqual(
            status["review_evidence"][0]["host_dispatch_id"],
            dispatch["dispatch_id"],
        )
        closure = self.pulses.derive_closure(
            fixture["plan"]["pulse_id"]
        )
        self.assertTrue(closure["procedural_ready"])
        self.assertTrue(closure["machine_verified_ready"])
        self.assertIn(
            "no mathematical truth",
            closure["truth_boundary"],
        )
        self.assertTrue(
            self.pulses.audit(fixture["plan"]["pulse_id"])["ok"]
        )

    def test_without_trusted_host_receipt_is_only_procedural(
        self,
    ) -> None:
        fixture = self._barrier_fixture()
        assignment_id = fixture["wave2"]["assignments"][0][
            "assignment_id"
        ]
        source = make_node(
            node_type="mechanism",
            logical_key="unattested-source",
            payload={"mechanism": "unattested-source"},
            created_by_assignment_id=assignment_id,
        )
        self._ingest_dead_end(
            fixture["wave2"],
            0,
            node_key="unattested-source",
            cross_edge={
                "edge_type": "refines",
                "target_node_id": fixture["left"]["node_id"],
                "payload": self._meaningful_payload(
                    fixture,
                    source["node_id"],
                ),
            },
        )
        status = self.pulses.status(fixture["plan"]["pulse_id"])
        self.assertTrue(status["procedural_ready"])
        self.assertFalse(status["machine_verified_ready"])
        self.assertTrue(
            any(
                "trusted host clean-context receipt is missing" in item
                for item in status["blockers"]
            )
        )
        closure = self.pulses.derive_closure(
            fixture["plan"]["pulse_id"]
        )
        self.assertTrue(closure["procedural_ready"])
        self.assertFalse(closure["machine_verified_ready"])

    def test_closure_rejects_canonical_core_without_ingestion_receipt(
        self,
    ) -> None:
        fixture = self._barrier_fixture()
        assignment_id = fixture["wave2"]["assignments"][0][
            "assignment_id"
        ]
        self.pulses.record_host_dispatch(
            fixture["plan"]["pulse_id"],
            fixture["review"]["commitment_id"],
            issuer="codex-test-host",
            host_context_id="fresh-context-pending-canonical",
        )
        source = make_node(
            node_type="mechanism",
            logical_key="pending-canonical-source",
            payload={"mechanism": "pending-canonical-source"},
            created_by_assignment_id=assignment_id,
        )
        with patch(
            __name__ + ".ingest_return",
            side_effect=RuntimeError("leave canonical return pending"),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "leave canonical return pending",
            ):
                self._ingest_dead_end(
                    fixture["wave2"],
                    0,
                    node_key="pending-canonical-source",
                    cross_edge={
                        "edge_type": "refines",
                        "target_node_id": fixture["left"]["node_id"],
                        "payload": self._meaningful_payload(
                            fixture,
                            source["node_id"],
                        ),
                    },
                )
        return_path = Path(
            fixture["wave2"]["assignments"][0]["return_path"]
        )
        self.assertTrue(return_path.exists())
        self.assertFalse(
            return_path.with_suffix(".receipt.json").exists()
        )
        status = self.pulses.status(fixture["plan"]["pulse_id"])
        self.assertFalse(status["procedural_ready"])
        self.assertTrue(
            any(
                "run ingest-return or pulse-abort" in blocker
                for blocker in status["blockers"]
            ),
            status,
        )
        with self.assertRaisesRegex(
            ValueError,
            "canonical return exists without an ingestion receipt",
        ):
            self.pulses.derive_closure(
                fixture["plan"]["pulse_id"]
            )

    def test_ceremonial_edge_is_a_fail_closed_breach(self) -> None:
        fixture = self._barrier_fixture()
        self.pulses.record_host_dispatch(
            fixture["plan"]["pulse_id"],
            fixture["review"]["commitment_id"],
            issuer="codex-test-host",
            host_context_id="fresh-context-wave2-ceremonial",
        )
        graph_before = self.store.blackboard().visible_ids()
        with self.assertRaisesRegex(
            ValueError,
            "pulse cross-review preflight",
        ):
            self._ingest_dead_end(
                fixture["wave2"],
                0,
                node_key="ceremonial-source",
                cross_edge={
                    "edge_type": "refines",
                    "target_node_id": fixture["left"]["node_id"],
                    "payload": {
                        "commitment_id": fixture["review"][
                            "commitment_id"
                        ]
                    },
                },
            )
        self.assertEqual(
            graph_before,
            self.store.blackboard().visible_ids(),
        )
        return_path = Path(
            fixture["wave2"]["assignments"][0]["return_path"]
        )
        self.assertFalse(
            return_path.with_suffix(".receipt.json").exists()
        )
        status = self.pulses.status(fixture["plan"]["pulse_id"])
        self.assertFalse(status["procedural_ready"])
        self.assertFalse(status["machine_verified_ready"])
        self.assertEqual(
            status["review_evidence"][0]["status"],
            "open",
        )

    def test_main_ingest_of_core_pulse_semantic_failure_auto_aborts(
        self,
    ) -> None:
        fixture = self._barrier_fixture()
        self.pulses.record_host_dispatch(
            fixture["plan"]["pulse_id"],
            fixture["review"]["commitment_id"],
            issuer="codex-test-host",
            host_context_id="fresh-context-semantic-failure",
        )
        with self.assertRaisesRegex(
            ValueError,
            "pulse cross-review preflight",
        ):
            self._ingest_dead_end(
                fixture["wave2"],
                0,
                node_key="semantic-failure-source",
                cross_edge={
                    "edge_type": "refines",
                    "target_node_id": fixture["left"]["node_id"],
                    "payload": {
                        "commitment_id": fixture["review"][
                            "commitment_id"
                        ]
                    },
                },
            )
        self.assertEqual(
            self.pulses.status(fixture["plan"]["pulse_id"])[
                "state"
            ],
            "wave2_open",
        )
        assignment = fixture["wave2"]["assignments"][0]
        return_path = Path(assignment["return_path"])
        return_sha256 = hashlib.sha256(
            return_path.read_bytes()
        ).hexdigest()
        with self.assertRaisesRegex(
            ValueError,
            "pulse cross-review preflight",
        ):
            ingest_return(
                self.store,
                fixture["wave2"]["round_id"],
                assignment["assignment_id"],
                worker_final_sha256=return_sha256,
            )
        status = self.pulses.status(fixture["plan"]["pulse_id"])
        self.assertEqual(status["state"], "aborted")
        failures = self.pulses.core_failure_receipts(
            fixture["plan"]["pulse_id"]
        )
        self.assertEqual(len(failures), 1)
        self.assertIn(
            "pulse cross-review preflight",
            failures[0]["error_message"],
        )

    def test_invalid_review_vocabulary_fails_draft_preflight(self) -> None:
        fixture = self._barrier_fixture()
        assignment = fixture["wave2"]["assignments"][0]
        assignment_id = assignment["assignment_id"]
        card_path = Path(assignment["task_card_path"])
        card = json.loads(card_path.read_text(encoding="utf-8"))
        source = make_node(
            node_type="mechanism",
            logical_key="invalid-vocabulary-source",
            payload={"mechanism": "invalid-vocabulary-source"},
            created_by_assignment_id=assignment_id,
        )
        payload = self._meaningful_payload(
            fixture,
            source["node_id"],
        )
        payload["check"]["kind"] = "algebraic_recheck"
        payload["disposition"]["kind"] = "confirmed"
        placement = make_edge(
            edge_type="placed_in",
            source_node_id=source["node_id"],
            target_node_id=self.root_space,
            payload={},
            created_by_assignment_id=assignment_id,
        )
        cross_edge = make_edge(
            edge_type="refines",
            source_node_id=source["node_id"],
            target_node_id=fixture["left"]["node_id"],
            payload=payload,
            created_by_assignment_id=assignment_id,
        )
        draft = {
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
                "add_nodes": [source],
                "add_edges": [placement, cross_edge],
            },
            "narrative_summary": "Invalid pulse vocabulary draft.",
            "claim": "Pulse vocabulary fixture",
            "method": "Use an unregistered check-kind synonym.",
            "failure_mode": "Vocabulary drift",
            "what_remains_open": "Use the exact registered check kind.",
            "artifacts": [],
        }
        draft_path = (
            Path(assignment["work_dir_path"])
            / "invalid-review-vocabulary.json"
        )
        draft_path.write_text(
            json.dumps(draft, ensure_ascii=False),
            encoding="utf-8",
        )
        return_path = Path(assignment["return_path"])
        before = {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in sorted(self.root.rglob("*"))
            if path.is_file() and not path.is_symlink()
        }
        with self.assertRaisesRegex(
            ValueError,
            "check kind is invalid",
        ):
            preflight_return(
                self.store,
                fixture["wave2"]["round_id"],
                assignment_id,
                input_path=draft_path,
            )
        after = {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in sorted(self.root.rglob("*"))
            if path.is_file() and not path.is_symlink()
        }
        self.assertEqual(after, before)
        self.assertFalse(return_path.exists())
        self.assertFalse(
            return_path.with_suffix(".receipt.json").exists()
        )

    def test_core_cannot_void_optional_void_is_write_once(self) -> None:
        wave1 = self._planned_round(3)
        commitments = [
            self.pulses.make_wave1_commitment(
                round_id=wave1["round_id"],
                assignment_id=item["assignment_id"],
                criticality="optional" if index == 2 else "core",
            )
            for index, item in enumerate(wave1["assignments"])
        ]
        plan = self.pulses.create_plan(
            wave1_commitments=commitments,
            minimum_wave1_contributors=2,
        )
        self._ingest_dead_end(wave1, 0, node_key="core-left")
        self._ingest_dead_end(wave1, 1, node_key="core-right")
        with self.assertRaisesRegex(
            ValueError,
            "core commitments can never be voided",
        ):
            self.pulses.void_optional(
                plan["pulse_id"],
                commitments[0]["commitment_id"],
                reason="forbidden",
            )
        first = self.pulses.void_optional(
            plan["pulse_id"],
            commitments[2]["commitment_id"],
            reason="optional channel was unavailable",
        )
        replay = self.pulses.void_optional(
            plan["pulse_id"],
            commitments[2]["commitment_id"],
            reason="optional channel was unavailable",
        )
        self.assertEqual(first, replay)
        with self.assertRaisesRegex(
            ValueError,
            "immutable pulse evidence collision",
        ):
            self.pulses.void_optional(
                plan["pulse_id"],
                commitments[2]["commitment_id"],
                reason="different retrospective excuse",
            )

    def test_federation_and_raw_remote_peer_are_rejected(self) -> None:
        wave1 = self._planned_round(2)
        commitments = [
            self.pulses.make_wave1_commitment(
                round_id=wave1["round_id"],
                assignment_id=item["assignment_id"],
            )
            for item in wave1["assignments"]
        ]
        with self.assertRaisesRegex(ValueError, "federation is disabled"):
            self.pulses.create_plan(
                wave1_commitments=commitments,
                federation_mode="read_only_mirror",
            )
        plan = self.pulses.create_plan(
            wave1_commitments=commitments
        )
        left, _ = self._ingest_dead_end(
            wave1,
            0,
            node_key="federation-left",
        )
        self._ingest_dead_end(
            wave1,
            1,
            node_key="federation-right",
        )
        wave2 = self._planned_round(1)
        with self.assertRaisesRegex(
            ValueError,
            "raw cross-project peer endpoints",
        ):
            self.pulses.make_review_commitment(
                pulse_id=plan["pulse_id"],
                round_id=wave2["round_id"],
                assignment_id=wave2["assignments"][0][
                    "assignment_id"
                ],
                peer_node_id=left["node_id"],
                peer_project_id="remote-project",
            )

    def test_plan_rejects_existing_wave1_canonical_draft_with_zero_write(
        self,
    ) -> None:
        wave1 = self._planned_round(1)
        assignment = wave1["assignments"][0]
        Path(assignment["return_path"]).write_text(
            '{"draft":true}',
            encoding="utf-8",
        )
        commitment = self.pulses.make_wave1_commitment(
            round_id=wave1["round_id"],
            assignment_id=assignment["assignment_id"],
        )
        before = self._file_inventory()
        with self.assertRaisesRegex(
            ValueError,
            "Wave-1 pulse-plan assignment is not pristine",
        ):
            self.pulses.create_plan(
                wave1_commitments=[commitment],
                minimum_wave1_contributors=1,
            )
        self.assertEqual(self._file_inventory(), before)
        self.assertFalse(
            (
                self.root / "blackboard" / "pulses" / "by-hash"
            ).exists()
        )

    def test_plan_rejects_ingested_wave1_from_transaction_after_files_removed(
        self,
    ) -> None:
        wave1 = self._planned_round(1)
        _, receipt = self._ingest_dead_end(
            wave1,
            0,
            node_key="late-plan-ingested-wave1",
        )
        assignment = wave1["assignments"][0]
        return_path = Path(assignment["return_path"])
        return_path.unlink()
        return_path.with_suffix(".receipt.json").unlink()
        commitment = self.pulses.make_wave1_commitment(
            round_id=wave1["round_id"],
            assignment_id=assignment["assignment_id"],
        )
        before = self._file_inventory()
        with self.assertRaisesRegex(
            ValueError,
            "blackboard_transaction:"
            + receipt["blackboard_transaction_id"],
        ):
            self.pulses.create_plan(
                wave1_commitments=[commitment],
                minimum_wave1_contributors=1,
            )
        self.assertEqual(self._file_inventory(), before)
        self.assertFalse(
            (
                self.root / "blackboard" / "pulses" / "by-hash"
            ).exists()
        )

    def test_host_dispatch_rejects_existing_wave2_draft_with_zero_write(
        self,
    ) -> None:
        fixture = self._barrier_fixture()
        assignment = fixture["wave2"]["assignments"][0]
        Path(assignment["return_path"]).write_text(
            '{"draft":true}',
            encoding="utf-8",
        )
        dispatch_path = self.pulses._dispatch_path(
            fixture["plan"]["pulse_id"],
            fixture["review"]["commitment_id"],
        )
        before = self._file_inventory()
        with self.assertRaisesRegex(
            ValueError,
            "Wave-2 host-dispatch assignment is not pristine",
        ):
            self.pulses.record_host_dispatch(
                fixture["plan"]["pulse_id"],
                fixture["review"]["commitment_id"],
                issuer="codex-test-host",
                host_context_id="late-draft-context",
            )
        self.assertEqual(self._file_inventory(), before)
        self.assertFalse(dispatch_path.exists())

    def test_host_dispatch_rejects_ingested_wave2_after_files_removed(
        self,
    ) -> None:
        fixture = self._barrier_fixture()
        assignment = fixture["wave2"]["assignments"][0]
        source = make_node(
            node_type="mechanism",
            logical_key="late-host-dispatch-review",
            payload={"mechanism": "late-host-dispatch-review"},
            created_by_assignment_id=assignment["assignment_id"],
        )
        _, receipt = self._ingest_dead_end(
            fixture["wave2"],
            0,
            node_key="late-host-dispatch-review",
            cross_edge={
                "edge_type": "refines",
                "target_node_id": fixture["left"]["node_id"],
                "payload": self._meaningful_payload(
                    fixture,
                    source["node_id"],
                ),
            },
        )
        return_path = Path(assignment["return_path"])
        return_path.unlink()
        return_path.with_suffix(".receipt.json").unlink()
        dispatch_path = self.pulses._dispatch_path(
            fixture["plan"]["pulse_id"],
            fixture["review"]["commitment_id"],
        )
        before = self._file_inventory()
        with self.assertRaisesRegex(
            ValueError,
            "blackboard_transaction:"
            + receipt["blackboard_transaction_id"],
        ):
            self.pulses.record_host_dispatch(
                fixture["plan"]["pulse_id"],
                fixture["review"]["commitment_id"],
                issuer="codex-test-host",
                host_context_id="late-ingested-context",
            )
        self.assertEqual(self._file_inventory(), before)
        self.assertFalse(dispatch_path.exists())

    def test_control_caps_preflight_has_zero_write_at_limit_plus_one(
        self,
    ) -> None:
        wave1 = self._planned_round(2)
        commitments = [
            self.pulses.make_wave1_commitment(
                round_id=wave1["round_id"],
                assignment_id=item["assignment_id"],
            )
            for item in wave1["assignments"]
        ]
        pulse_root = (
            self.root / "blackboard" / "pulses" / "by-hash"
        )
        pulse_root.mkdir(parents=True, exist_ok=True)
        marker = pulse_root / "existing.json"
        marker.write_text("{}\n", encoding="utf-8")
        before = marker.stat().st_mtime_ns
        with patch.dict(
            "mathgraph.collaboration.DEFAULT_HARD_CAPS",
            {
                "max_pulse_control_records": 1,
                "max_pulse_control_bytes_each": 256 * 1024,
                "max_pulse_control_bytes_total": 16 * 1024 * 1024,
            },
            clear=False,
        ):
            with self.assertRaisesRegex(
                ValueError,
                "record count hard cap exceeded",
            ):
                self.pulses.create_plan(
                    wave1_commitments=commitments,
                )
        self.assertEqual(marker.stat().st_mtime_ns, before)
        self.assertEqual(
            sorted(path.name for path in pulse_root.rglob("*.json")),
            ["existing.json"],
        )


if __name__ == "__main__":
    unittest.main()

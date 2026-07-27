from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from mathgraph.cli import main as cli_main
from mathgraph.orchestrator import create_round
from mathgraph.roles import (
    V4_BOUND_WORKER_QUERY_COMMANDS,
    allowed_bound_worker_queries_for_workflow,
    allowed_commands,
    allowed_commands_for_workflow,
)
from mathgraph.store import MathGraphStore


class V4BoundWorkerQueryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = MathGraphStore(self.root)
        self.store.initialize(
            project_id="v4-bound-worker-queries",
            title="V4 bound worker queries",
            workflow_evidence_version=4,
        )
        self.campaign_id = self.store.campaigns().active()
        assert self.campaign_id is not None

        claims = self.store.claims()
        self.convention_id = claims.add_convention(
            self._convention_payload("a", "positive"),
            actor="operator",
        )
        self.other_convention_id = claims.add_convention(
            self._convention_payload("b", "negative"),
            actor="operator",
        )
        self.claim_id = claims.add_claim(
            self._claim_payload(
                self.convention_id,
                "c",
                "The bound literal claim.",
            ),
            actor="operator",
        )
        self.other_claim_id = claims.add_claim(
            self._claim_payload(
                self.other_convention_id,
                "d",
                "A different literal claim.",
            ),
            actor="operator",
        )
        self.other_campaign_id = self.store.campaigns().create(
            {
                "name": "other",
                "objective": "A different campaign.",
                "source_claim_ids": [self.other_claim_id],
                "targets": [],
                "constraints": [],
                "stop_conditions": ["Stop elsewhere."],
                "value_definition": "Keep this campaign separate.",
            },
            actor="operator",
        )

        memory_id = self.store.memory_add(
            {
                "kind": "direction",
                "claim": "Analyze only the bound research inputs.",
                "rationale": "Exercise the independent input closure.",
                "suggested_actions": ["prove"],
                "campaign_id": self.campaign_id,
                "source_claim_id": self.claim_id,
                "convention_profile_ids": [self.convention_id],
            },
            actor="main",
        )
        planned = create_round(
            self.store,
            workers=1,
            memory_ids=[memory_id],
        )
        self.task_card_path = Path(
            planned["assignments"][0]["task_card_path"]
        )
        self.task_card = json.loads(
            self.task_card_path.read_text(encoding="utf-8")
        )
        self.snapshot_id = self.task_card["blackboard_view"]["snapshot_id"]
        snapshot_nodes, snapshot_edges = (
            self.store.blackboard().snapshot_objects(self.snapshot_id)
        )
        self.bound_blackboard_id = sorted(snapshot_nodes)[0]
        self.snapshot_query_path = self.root / "snapshot-query.json"
        self.snapshot_query_path.write_text(
            json.dumps(
                self.store.blackboard()
                .snapshot_manifest(self.snapshot_id)["query"],
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        self.other_blackboard_id = self.store.blackboard().create_space(
            name="post-snapshot-space",
            scope="Must remain outside the frozen worker snapshot.",
            actor="operator",
            parent_space_id=sorted(snapshot_nodes)[0],
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _convention_payload(seed: str, orientation: str) -> dict:
        return {
            "theory": "topological recursion",
            "source_version": f"arXiv:2401.0000{seed}v1",
            "source_artifact_sha256": seed * 64,
            "authority": "literal_source",
            "dimensions": {
                "residue_orientation": orientation,
            },
        }

    @staticmethod
    def _claim_payload(
        convention_id: str,
        seed: str,
        statement: str,
    ) -> dict:
        return {
            "kind": "published_literal",
            "title": statement,
            "statement": statement,
            "source": {
                "title": "Bound source",
                "version": f"arXiv:2401.0000{seed}v1",
                "artifact_sha256": seed * 64,
                "locator": "Theorem 1",
                "retrieved_at": "2026-07-25",
            },
            "convention_profile_id": convention_id,
            "authority": "literal_source",
        }

    def _run(
        self,
        role: str,
        *command: str,
    ) -> tuple[int, str, str]:
        output = io.StringIO()
        error = io.StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            status = cli_main(
                [
                    "--root",
                    str(self.root),
                    "--role",
                    role,
                    *command,
                ]
            )
        return status, output.getvalue(), error.getvalue()

    def _worker_query(
        self,
        command: str,
        object_id: str,
        *,
        task_card_path: Path | None = None,
    ) -> tuple[int, str, str]:
        card = task_card_path or self.task_card_path
        return self._run(
            "worker",
            command,
            object_id,
            "--task-card",
            str(card),
        )

    def test_worker_reads_exact_bound_registry_objects(self) -> None:
        cases = (
            ("claim-show", self.claim_id, "claim_id"),
            ("convention-show", self.convention_id, "convention_id"),
            ("campaign-status", self.campaign_id, "campaign_id"),
        )
        for command, object_id, result_key in cases:
            with self.subTest(command=command):
                status, output, error = self._worker_query(
                    command,
                    object_id,
                )
                self.assertEqual(status, 0, error)
                self.assertEqual(json.loads(output)[result_key], object_id)

    def test_worker_reads_only_blackboard_objects_in_bound_snapshot(self) -> None:
        status, output, error = self._worker_query(
            "blackboard-show",
            self.bound_blackboard_id,
        )
        self.assertEqual(status, 0, error)
        self.assertEqual(
            json.loads(output).get("node_id")
            or json.loads(output).get("edge_id"),
            self.bound_blackboard_id,
        )

        status, output, error = self._worker_query(
            "blackboard-show",
            self.other_blackboard_id,
        )
        self.assertEqual(status, 2)
        self.assertEqual(output, "")
        self.assertIn("not authorized by the frozen task card", error)

    def test_worker_queries_only_the_exact_bound_blackboard_snapshot(self) -> None:
        status, output, error = self._run(
            "worker",
            "blackboard-snapshot-query",
            self.snapshot_id,
            "--input",
            str(self.snapshot_query_path),
            "--task-card",
            str(self.task_card_path),
        )
        self.assertEqual(status, 0, error)
        result = json.loads(output)
        self.assertEqual(result["snapshot_id"], self.snapshot_id)
        self.assertIn(self.bound_blackboard_id, result["node_ids"])

        status, output, error = self._run(
            "worker",
            "blackboard-snapshot-query",
            "bbs-" + "0" * 64,
            "--input",
            str(self.snapshot_query_path),
            "--task-card",
            str(self.task_card_path),
        )
        self.assertEqual(status, 2)
        self.assertEqual(output, "")
        self.assertIn("not authorized by the frozen task card", error)

    def test_worker_rejects_unbound_exact_ids_and_campaign_listing(self) -> None:
        for command, object_id in (
            ("claim-show", self.other_claim_id),
            ("convention-show", self.other_convention_id),
            ("campaign-status", self.other_campaign_id),
        ):
            with self.subTest(command=command):
                status, output, error = self._worker_query(
                    command,
                    object_id,
                )
                self.assertEqual(status, 2)
                self.assertEqual(output, "")
                self.assertIn(
                    "not authorized by the frozen task card",
                    error,
                )

        status, output, error = self._run(
            "worker",
            "campaign-status",
            "--task-card",
            str(self.task_card_path),
        )
        self.assertEqual(status, 2)
        self.assertEqual(output, "")
        self.assertIn("requires an explicit campaign_id", error)

    def test_worker_campaign_status_is_frozen_not_live(self) -> None:
        status, output, error = self._worker_query(
            "campaign-status",
            self.campaign_id,
        )
        self.assertEqual(status, 0, error)
        frozen = json.loads(output)

        self.store.campaigns().update(
            self.campaign_id,
            {
                "type": "note",
                "payload": {"text": "LIVE-LEAK-SENTINEL"},
            },
            actor="operator",
        )
        status, output, error = self._worker_query(
            "campaign-status",
            self.campaign_id,
        )
        self.assertEqual(status, 0, error)
        self.assertEqual(json.loads(output), frozen)
        self.assertNotIn("LIVE-LEAK-SENTINEL", output)

        status, output, error = self._run(
            "main",
            "campaign-status",
            self.campaign_id,
        )
        self.assertEqual(status, 0, error)
        self.assertIn("LIVE-LEAK-SENTINEL", output)

    def test_worker_requires_task_card_for_every_bound_query(self) -> None:
        for command, object_id in (
            ("claim-show", self.claim_id),
            ("convention-show", self.convention_id),
            ("campaign-status", self.campaign_id),
            ("blackboard-show", self.bound_blackboard_id),
        ):
            with self.subTest(command=command):
                status, output, error = self._run(
                    "worker",
                    command,
                    object_id,
                )
                self.assertEqual(status, 2)
                self.assertEqual(output, "")
                self.assertIn("requires --task-card", error)

        status, output, error = self._run(
            "worker",
            "blackboard-snapshot-query",
            self.snapshot_id,
            "--input",
            str(self.snapshot_query_path),
        )
        self.assertEqual(status, 2)
        self.assertEqual(output, "")
        self.assertIn("requires --task-card", error)

    def test_worker_rejects_semantic_and_byte_only_card_tampering(self) -> None:
        task_card = json.loads(
            self.task_card_path.read_text(encoding="utf-8")
        )
        semantic_tamper = self.root / "semantic-tamper.json"
        changed = {**task_card, "source_claim_id": self.other_claim_id}
        semantic_tamper.write_text(
            json.dumps(changed, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        status, output, error = self._worker_query(
            "claim-show",
            self.other_claim_id,
            task_card_path=semantic_tamper,
        )
        self.assertEqual(status, 2)
        self.assertEqual(output, "")
        self.assertIn("differs from the frozen round card", error)

        byte_tamper = self.root / "byte-tamper.json"
        byte_tamper.write_text(
            json.dumps(task_card, separators=(",", ":")),
            encoding="utf-8",
        )
        status, output, error = self._worker_query(
            "claim-show",
            self.claim_id,
            task_card_path=byte_tamper,
        )
        self.assertEqual(status, 2)
        self.assertEqual(output, "")
        self.assertIn("bytes differ from the frozen round card", error)

    def test_worker_rejects_tampered_frozen_card_hash(self) -> None:
        task_card = json.loads(
            self.task_card_path.read_text(encoding="utf-8")
        )
        task_card["goal_statement"] = "Tampered in place."
        self.task_card_path.write_text(
            json.dumps(task_card, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        status, output, error = self._worker_query(
            "claim-show",
            self.claim_id,
        )
        self.assertEqual(status, 2)
        self.assertEqual(output, "")
        self.assertIn("differs from the frozen round card", error)

    def test_main_and_operator_queries_keep_unbound_behavior(self) -> None:
        status, output, error = self._run(
            "main",
            "claim-show",
            self.other_claim_id,
        )
        self.assertEqual(status, 0, error)
        self.assertEqual(
            json.loads(output)["claim_id"],
            self.other_claim_id,
        )

        status, output, error = self._run(
            "operator",
            "convention-show",
            self.other_convention_id,
        )
        self.assertEqual(status, 0, error)
        self.assertEqual(
            json.loads(output)["convention_id"],
            self.other_convention_id,
        )

        status, output, error = self._run("main", "campaign-status")
        self.assertEqual(status, 0, error)
        self.assertEqual(
            json.loads(output)["campaign_id"],
            self.campaign_id,
        )

    def test_roles_expose_bound_queries_only_for_v4_workers(self) -> None:
        self.assertIn("experiment-resume", allowed_commands("main"))
        self.assertEqual(
            allowed_bound_worker_queries_for_workflow("worker", 4),
            V4_BOUND_WORKER_QUERY_COMMANDS,
        )
        self.assertEqual(
            allowed_bound_worker_queries_for_workflow("worker", 3),
            set(),
        )
        self.assertEqual(
            allowed_bound_worker_queries_for_workflow("main", 4),
            set(),
        )
        for command in V4_BOUND_WORKER_QUERY_COMMANDS:
            self.assertNotIn(
                command,
                allowed_commands_for_workflow("worker", 4),
            )
            self.assertNotIn(
                command,
                allowed_commands_for_workflow("worker", 3),
            )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from mathgraph.blackboard import make_edge, make_node
from mathgraph.cli import main as cli_main
from mathgraph.contracts import (
    POLICY_REVISION_V4,
    canonical_json_bytes,
)
from mathgraph.orchestrator import (
    create_round,
    ingest_return,
    validate_return,
)
from mathgraph.store import MathGraphStore


class HostDispatchCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = MathGraphStore(self.root)
        self.store.initialize(
            project_id="v4-host-dispatch-cli",
            title="V4 host dispatch CLI",
            workflow_evidence_version=4,
        )
        self.root_space = next(
            node_id
            for node_id, node in self.store.blackboard().nodes().items()
            if node["node_type"] == "space"
        )
        self.host_scope = "hosttask-" + "7" * 32
        self.memory_counter = 0

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _cli(
        self,
        role: str,
        *args: str,
        host_config: Path | None = None,
    ) -> tuple[int, dict | None, str]:
        stdout = StringIO()
        stderr = StringIO()
        argv = ["--root", str(self.root)]
        if host_config is not None:
            argv.extend(["--host-config", str(host_config)])
        argv.extend(["--role", role, *args])
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = cli_main(argv)
        payload = (
            json.loads(stdout.getvalue())
            if stdout.getvalue().strip()
            else None
        )
        return code, payload, stderr.getvalue()

    def _cli_ok(
        self,
        role: str,
        *args: str,
        host_config: Path | None = None,
    ) -> dict:
        code, payload, error = self._cli(
            role,
            *args,
            host_config=host_config,
        )
        self.assertEqual(code, 0, error)
        self.assertIsInstance(payload, dict)
        return payload

    def _write_json(self, name: str, payload: dict) -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def _write_host_config(
        self,
        path: Path,
        *,
        issuers: list[str],
    ) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "policy_revision": POLICY_REVISION_V4,
                    "project_id": self.store.project_id(),
                    "adapter_mode": "cooperative",
                    "trusted_host_issuers": issuers,
                }
            ),
            encoding="utf-8",
        )
        return path

    def _planned_round(self, workers: int) -> dict:
        memory_ids: list[str] = []
        for _ in range(workers):
            self.memory_counter += 1
            memory_ids.append(
                self.store.memory_add(
                    {
                        "kind": "direction",
                        "claim": (
                            "Host dispatch CLI direction "
                            f"{self.memory_counter}."
                        ),
                        "rationale": "Independent host-adapter fixture.",
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

    def _ingest_dead_end(
        self,
        planned: dict,
        index: int,
        *,
        node_key: str,
        cross_edge: dict | None = None,
    ) -> dict:
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
            "policy_revision": POLICY_REVISION_V4,
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
            "narrative_summary": "Typed host-adapter test boundary.",
            "claim": "Host dispatch fixture",
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
        ingest_return(
            self.store,
            planned["round_id"],
            card["assignment_id"],
            worker_final_sha256=validated["return_sha256"],
        )
        return node

    def _prepare_pulse(
        self,
        *,
        host_config: Path | None,
        review_workers: int,
    ) -> dict:
        wave1 = self._planned_round(2)
        plan_input = self._write_json(
            f"plan-{self.memory_counter}.json",
            {
                "wave1_assignments": [
                    {
                        "round_id": wave1["round_id"],
                        "assignment_id": item["assignment_id"],
                    }
                    for item in wave1["assignments"]
                ],
                "minimum_wave1_contributors": 2,
            },
        )
        plan = self._cli_ok(
            "main",
            "pulse-plan",
            "--input",
            str(plan_input),
            host_config=host_config,
        )
        peers = [
            self._ingest_dead_end(
                wave1,
                index,
                node_key=f"wave1-peer-{self.memory_counter}-{index}",
            )
            for index in range(2)
        ]

        wave2 = self._planned_round(review_workers)
        barrier_input = self._write_json(
            f"barrier-{self.memory_counter}.json",
            {
                "review_assignments": [
                    {
                        "round_id": wave2["round_id"],
                        "assignment_id": item["assignment_id"],
                        "peer_node_id": peers[index % len(peers)][
                            "node_id"
                        ],
                        "allowed_edge_types": ["refines"],
                    }
                    for index, item in enumerate(
                        wave2["assignments"]
                    )
                ]
            },
        )
        barrier = self._cli_ok(
            "main",
            "pulse-barrier",
            plan["pulse_id"],
            "--after-snapshot-id",
            wave2["blackboard_snapshot_id"],
            "--input",
            str(barrier_input),
            host_config=host_config,
        )
        commitments = {
            item["assignment_id"]: item
            for item in barrier["review_commitments"]
        }
        return {
            "plan": plan,
            "barrier": barrier,
            "peers": peers,
            "wave2": wave2,
            "commitments": commitments,
        }

    def _ingest_reviews(self, fixture: dict) -> None:
        for index, assignment in enumerate(
            fixture["wave2"]["assignments"]
        ):
            commitment = fixture["commitments"][
                assignment["assignment_id"]
            ]
            peer = fixture["peers"][index % len(fixture["peers"])]
            source = make_node(
                node_type="mechanism",
                logical_key=f"wave2-review-{self.memory_counter}-{index}",
                payload={
                    "mechanism": (
                        f"wave2-review-{self.memory_counter}-{index}"
                    )
                },
                created_by_assignment_id=assignment["assignment_id"],
            )
            exchange = {
                "exchange_schema_version": 1,
                "pulse_id": fixture["plan"]["pulse_id"],
                "barrier_id": fixture["barrier"]["barrier_id"],
                "commitment_id": commitment["commitment_id"],
                "peer_node_id": peer["node_id"],
                "peer_node_sha256": hashlib.sha256(
                    canonical_json_bytes(peer)
                ).hexdigest(),
                "check": {
                    "kind": "scope_audit",
                    "method": (
                        "Repeated the peer endpoint and scope check "
                        "from this fresh frozen review context."
                    ),
                    "witness_refs": [source["node_id"]],
                },
                "disposition": {
                    "kind": "no_correction",
                    "boundary": (
                        "No correction inside this exploration boundary; "
                        "the pulse creates no mathematical truth."
                    ),
                },
            }
            node = self._ingest_dead_end(
                fixture["wave2"],
                index,
                node_key=f"wave2-review-{self.memory_counter}-{index}",
                cross_edge={
                    "edge_type": "refines",
                    "target_node_id": peer["node_id"],
                    "payload": exchange,
                },
            )
            self.assertEqual(node["node_id"], source["node_id"])

    def test_no_host_configuration_remains_procedural_only(
        self,
    ) -> None:
        fixture = self._prepare_pulse(
            host_config=None,
            review_workers=1,
        )
        self.assertEqual(
            fixture["plan"]["trusted_host_issuers"],
            [],
        )
        self._ingest_reviews(fixture)
        closure = self._cli_ok(
            "main",
            "pulse-close",
            fixture["plan"]["pulse_id"],
        )
        self.assertTrue(closure["procedural_ready"])
        self.assertFalse(closure["machine_verified_ready"])
        self.assertTrue(
            any(
                "trusted host clean-context receipt is missing"
                in blocker
                for blocker in closure["blockers"]
            )
        )

    def test_configured_real_format_dispatches_make_machine_ready(
        self,
    ) -> None:
        config = self._write_host_config(
            self.root / "host_adapter.json",
            issuers=["codex-local-host"],
        )
        fixture = self._prepare_pulse(
            host_config=None,
            review_workers=2,
        )
        self.assertEqual(
            fixture["plan"]["trusted_host_issuers"],
            ["codex-local-host"],
        )
        commitments = [
            fixture["commitments"][item["assignment_id"]]
            for item in fixture["wave2"]["assignments"]
        ]

        code, _, error = self._cli(
            "host",
            "pulse-dispatch",
            fixture["plan"]["pulse_id"],
            commitments[0]["commitment_id"],
            "--issuer",
            "forged-host",
            "--host-context-id",
            "context-forged",
            "--agent-identity",
            "agent-forged",
            "--fresh-context-contract",
            "fresh-context-v1",
        )
        self.assertEqual(code, 2)
        self.assertIn("not trusted", error)

        code, _, error = self._cli(
            "host",
            "pulse-dispatch",
            fixture["plan"]["pulse_id"],
            "bbpc-" + "0" * 64,
            "--issuer",
            "codex-local-host",
            "--host-context-id",
            "context-wrong-commitment",
            "--agent-identity",
            "agent-wrong-commitment",
            "--fresh-context-contract",
            "fresh-context-v1",
        )
        self.assertEqual(code, 2)
        self.assertIn("bound review commitment", error)

        first = self._cli_ok(
            "host",
            "pulse-dispatch",
            fixture["plan"]["pulse_id"],
            commitments[0]["commitment_id"],
            "--issuer",
            "codex-local-host",
            "--host-context-id",
            "codex-context-wave2-1",
            "--agent-identity",
            "/root/fresh-reviewer-1",
            "--fresh-context-contract",
            "fresh-context-v1",
        )
        self.assertEqual(
            first["host_task_scope_id"],
            self.host_scope,
        )
        self.assertEqual(
            first["agent_identity"],
            "/root/fresh-reviewer-1",
        )
        self.assertFalse(
            first["fresh_context_contract"][
                "prior_worker_context_inherited"
            ]
        )

        code, _, error = self._cli(
            "host",
            "pulse-dispatch",
            fixture["plan"]["pulse_id"],
            commitments[0]["commitment_id"],
            "--issuer",
            "codex-local-host",
            "--host-context-id",
            "codex-context-wave2-1",
            "--agent-identity",
            "/root/fresh-reviewer-1",
            "--fresh-context-contract",
            "fresh-context-v1",
        )
        self.assertEqual(code, 2)
        self.assertIn("replay is not accepted", error)

        code, _, error = self._cli(
            "host",
            "pulse-dispatch",
            fixture["plan"]["pulse_id"],
            commitments[1]["commitment_id"],
            "--issuer",
            "codex-local-host",
            "--host-context-id",
            "codex-context-wave2-1",
            "--agent-identity",
            "/root/fresh-reviewer-2",
            "--fresh-context-contract",
            "fresh-context-v1",
        )
        self.assertEqual(code, 2)
        self.assertIn("context id replay", error)

        second = self._cli_ok(
            "host",
            "pulse-dispatch",
            fixture["plan"]["pulse_id"],
            commitments[1]["commitment_id"],
            "--issuer",
            "codex-local-host",
            "--host-context-id",
            "codex-context-wave2-2",
            "--agent-identity",
            "/root/fresh-reviewer-2",
            "--fresh-context-contract",
            "fresh-context-v1",
        )
        self.assertNotEqual(
            first["dispatch_id"],
            second["dispatch_id"],
        )
        for assignment in fixture["wave2"]["assignments"]:
            commitment = fixture["commitments"][
                assignment["assignment_id"]
            ]
            self.assertTrue(
                (
                    self.root
                    / "blackboard"
                    / "pulses"
                    / "by-hash"
                    / fixture["plan"]["pulse_id"]
                    / "host-dispatches"
                    / f"{commitment['commitment_id']}.json"
                ).is_file()
            )
            self.assertFalse(Path(assignment["return_path"]).exists())
        self._ingest_reviews(fixture)
        closure = self._cli_ok(
            "main",
            "pulse-close",
            fixture["plan"]["pulse_id"],
        )
        self.assertTrue(closure["procedural_ready"])
        self.assertTrue(closure["machine_verified_ready"])
        self.assertEqual(closure["blockers"], [])
        self.assertTrue(self.store.audit().ok)
        self.assertTrue(config.is_file())

    def test_explicit_config_path_is_loaded_but_nonhost_roles_are_denied(
        self,
    ) -> None:
        explicit = self._write_host_config(
            self.root / "host-configs" / "codex.json",
            issuers=["codex-explicit-host"],
        )
        configured = MathGraphStore(
            self.root,
            host_config_path=explicit,
        )
        self.assertEqual(
            configured.trusted_host_issuers(),
            ("codex-explicit-host",),
        )
        for role in ("main", "operator", "worker", "gateway"):
            with self.subTest(role=role):
                code, _, error = self._cli(
                    role,
                    "pulse-dispatch",
                    "bbp-" + "0" * 64,
                    "bbpc-" + "0" * 64,
                    "--issuer",
                    "codex-explicit-host",
                    "--host-context-id",
                    f"{role}-context",
                    "--agent-identity",
                    role,
                    "--fresh-context-contract",
                    "fresh-context-v1",
                    host_config=explicit,
                )
                self.assertEqual(code, 3)
                self.assertIn("not allowed", error)


if __name__ == "__main__":
    unittest.main()

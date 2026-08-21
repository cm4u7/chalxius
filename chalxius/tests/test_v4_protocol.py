from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from mathgraph.blackboard import BlackboardStore, make_edge, make_node
from mathgraph.orchestrator import create_round, ingest_return, validate_return
from mathgraph.protocol import (
    compact_worker_prompt,
    validate_control_followup,
    validate_final_handoff,
    validate_task_card,
    validate_worker_return_v4,
)
from mathgraph.store import MathGraphStore
from mathgraph.worker_returns import validate_worker_return


class V4ProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = MathGraphStore(self.root)
        self.store.initialize(
            project_id="v4-protocol-tests",
            title="V4 protocol tests",
            workflow_evidence_version=4,
        )
        self.blackboard = self.store.blackboard()
        self.root_space = next(
            node_id
            for node_id, node in self.blackboard.nodes().items()
            if node["node_type"] == "space"
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _node(self, key: str, *, assignment: str = "operator") -> dict:
        return make_node(
            node_type="note",
            logical_key=key,
            payload={"text": key},
            created_by_assignment_id=assignment,
        )

    def _query(self, *seeds: str, node_budget: int = 64) -> dict:
        return {
            "seed_node_ids": list(seeds),
            "direction": "both",
            "max_hops": 4,
            "edge_type_allowlist": ["*"],
            "node_type_allowlist": ["*"],
            "node_budget": node_budget,
            "edge_budget": 128,
        }

    def _planned_round(self, workers: int = 1) -> dict:
        ids = []
        for index in range(workers):
            ids.append(
                self.store.memory_add(
                    {
                        "kind": "direction",
                        "claim": f"Investigate atomic claim {index}.",
                        "rationale": "Protocol fixture.",
                        "suggested_actions": ["prove"],
                    },
                    actor="main",
                )
            )
        return create_round(
            self.store,
            workers=workers,
            memory_ids=ids,
        )

    def _fact_submission_return(
        self,
        planned: dict,
        *,
        add_graph_node: bool,
    ) -> tuple[dict, dict, Path]:
        assignment = planned["assignments"][0]
        card_path = Path(assignment["task_card_path"])
        card = json.loads(card_path.read_text())
        add_nodes: list[dict] = []
        add_edges: list[dict] = []
        if add_graph_node:
            node = self._node(
                "ingestion-atomicity",
                assignment=card["assignment_id"],
            )
            add_nodes.append(node)
            add_edges.append(
                make_edge(
                    edge_type="placed_in",
                    source_node_id=node["node_id"],
                    target_node_id=self.root_space,
                    payload={},
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
            "outcome": "fact_submission",
            "obligation_ledger": [],
            "blackboard_graph_delta": {
                "base_snapshot_id": card["blackboard_view"]["snapshot_id"],
                "add_nodes": add_nodes,
                "add_edges": add_edges,
            },
            "narrative_summary": "A direct atomic proof.",
            "claim_relation": "proves",
            "statement": "[CLAIM:MAIN] The toy identity holds.",
            "proof": "Both sides are identical.",
            "predecessors": [],
            "predecessor_uses": [],
            "quantifier_ledger": [],
            "convention_profile_ids": [],
            "computational_evidence": [],
            "terminology": [],
            "glossary_introduces": {},
            "external_refs": [],
            "elementary_uses": [],
            "intuition": "",
            "artifacts": [],
        }
        return payload, card, Path(assignment["return_path"])

    def test_v4_task_card_rejects_unknown_fields_and_binds_snapshot(self) -> None:
        planned = self._planned_round()
        card = json.loads(
            Path(planned["assignments"][0]["task_card_path"]).read_text()
        )
        self.assertEqual(
            card["blackboard_view"]["snapshot_id"],
            planned["blackboard_snapshot_id"],
        )
        invalid = {**card, "unexpected": True}
        with self.assertRaisesRegex(ValueError, "unknown"):
            validate_task_card(invalid)

    def test_fact_cannot_introduce_unbound_convention_profile(self) -> None:
        planned = self._planned_round()
        payload, card, _ = self._fact_submission_return(
            planned,
            add_graph_node=False,
        )
        payload["convention_profile_ids"] = [
            "conv-0123456789abcdef"
        ]
        with self.assertRaisesRegex(ValueError, "not bound by the task card"):
            validate_worker_return_v4(payload, task_card=card)

    def test_bundled_v4_examples_are_schema_and_hash_consistent(self) -> None:
        assets = Path(__file__).resolve().parents[1] / "assets"
        card_path = assets / "task_card.v4.example.json"
        return_path = assets / "worker_return.v4.example.json"
        delta_path = assets / "blackboard_graph_delta.v4.example.json"
        card = json.loads(card_path.read_text(encoding="utf-8"))
        worker_return = json.loads(return_path.read_text(encoding="utf-8"))
        delta = json.loads(delta_path.read_text(encoding="utf-8"))
        validate_task_card(card)
        validate_worker_return_v4(worker_return, task_card=card)
        self.assertEqual(worker_return["blackboard_graph_delta"], delta)
        self.assertEqual(
            worker_return["task_card_sha256"],
            hashlib.sha256(card_path.read_bytes()).hexdigest(),
        )
        for node in delta["add_nodes"]:
            self.blackboard.validate_node(node)
        for edge in delta["add_edges"]:
            self.blackboard.validate_edge(edge)

    def test_host_task_scope_is_required_for_new_cards_only(self) -> None:
        assets = Path(__file__).resolve().parents[1] / "assets"
        card = json.loads(
            (assets / "task_card.v4.example.json").read_text(
                encoding="utf-8"
            )
        )
        historical = deepcopy(card)
        historical.pop("host_task_scope_id")
        with self.assertRaisesRegex(ValueError, "missing"):
            validate_task_card(historical)
        validate_task_card(
            historical,
            allow_legacy_adoption=True,
        )

    def test_worker_prompt_is_small_and_does_not_duplicate_policy(self) -> None:
        prompt = compact_worker_prompt(
            task_card_path="rounds/r/task.json",
            protocol_reference_path="references/protocol.md",
            mgraph_path="scripts/mgraph",
        )
        self.assertLess(len(prompt.encode()), 4096)
        self.assertNotIn("External Theorem Applicability Certificate", prompt)
        self.assertEqual(prompt.count("Blackboard"), 1)
        self.assertIn("preflight-return --input", prompt)

    def test_same_round_workers_receive_identical_frozen_snapshot(self) -> None:
        planned = self._planned_round(workers=2)
        cards = [
            json.loads(Path(item["task_card_path"]).read_text())
            for item in planned["assignments"]
        ]
        prompts = [
            Path(item["prompt_path"]).read_text(encoding="utf-8")
            for item in planned["assignments"]
        ]
        self.assertEqual(
            cards[0]["blackboard_snapshot_sha256"],
            cards[1]["blackboard_snapshot_sha256"],
        )
        self.assertEqual(
            cards[0]["blackboard_view"]["snapshot_id"],
            cards[1]["blackboard_view"]["snapshot_id"],
        )
        self.assertTrue(
            all(
                "references/agent_protocol_v4.md" in prompt
                for prompt in prompts
            )
        )
        self.assertTrue(
            all("#workflow-evidence-v4" not in prompt for prompt in prompts)
        )

    def test_same_snapshot_can_bind_distinct_worker_write_spaces(self) -> None:
        source_space = self.blackboard.create_space(
            name="source-lane",
            scope="Source-only writes.",
            actor="main",
            parent_space_id=self.root_space,
        )
        computation_space = self.blackboard.create_space(
            name="computation-lane",
            scope="Computation-only writes.",
            actor="main",
            parent_space_id=self.root_space,
        )
        frozen_peer = self._node("frozen-cross-space-peer")
        self.blackboard.add_node_with_placements(
            node=frozen_peer,
            space_ids=[self.root_space],
            actor="main",
        )
        memory_ids = [
            self.store.memory_add(
                {
                    "kind": "direction",
                    "claim": "Audit the source lane.",
                    "blackboard_write_space_ids": [source_space],
                    "blackboard_cross_space_endpoint_node_ids": [
                        frozen_peer["node_id"]
                    ],
                },
                actor="main",
            ),
            self.store.memory_add(
                {
                    "kind": "computation",
                    "claim": "Audit the computation lane.",
                    "blackboard_write_space_ids": [computation_space],
                },
                actor="main",
            ),
        ]
        planned = create_round(
            self.store,
            workers=2,
            memory_ids=memory_ids,
        )
        cards = [
            json.loads(Path(item["task_card_path"]).read_text())
            for item in planned["assignments"]
        ]
        self.assertEqual(
            cards[0]["blackboard_view"]["snapshot_id"],
            cards[1]["blackboard_view"]["snapshot_id"],
        )
        self.assertEqual(
            cards[0]["blackboard_view"]["write_space_ids"],
            [source_space],
        )
        self.assertEqual(
            cards[1]["blackboard_view"]["write_space_ids"],
            [computation_space],
        )
        self.assertEqual(
            cards[0]["blackboard_view"][
                "cross_space_endpoint_node_ids"
            ],
            [frozen_peer["node_id"]],
        )
        unauthorized = self._node(
            "lane-capability-breach",
            assignment=cards[0]["assignment_id"],
        )
        with self.assertRaisesRegex(ValueError, "write|space|capability"):
            self.blackboard.validate_delta(
                delta={
                    "base_snapshot_id": cards[0]["blackboard_view"][
                        "snapshot_id"
                    ],
                    "add_nodes": [unauthorized],
                    "add_edges": [
                        make_edge(
                            edge_type="placed_in",
                            source_node_id=unauthorized["node_id"],
                            target_node_id=computation_space,
                            payload={},
                            created_by_assignment_id=cards[0][
                                "assignment_id"
                            ],
                        )
                    ],
                },
                task_card=cards[0],
                return_sha256="9" * 64,
                defer_visibility=True,
            )

    def test_memory_rejects_unknown_worker_write_space(self) -> None:
        with self.assertRaisesRegex(ValueError, "existing spaces"):
            self.store.memory_add(
                {
                    "kind": "direction",
                    "claim": "Attempt a capability escalation.",
                    "blackboard_write_space_ids": [
                        "bbn-" + "0" * 64
                    ],
                },
                actor="main",
            )

    def test_worker_return_snapshot_mismatch_fails(self) -> None:
        planned = self._planned_round()
        assignment = planned["assignments"][0]
        manifest = self.store._read_json(
            self.store.rounds_dir / planned["round_id"] / "round.json"
        )
        card_path = Path(assignment["task_card_path"])
        card = json.loads(card_path.read_text())
        payload = {
            "schema_version": 4,
            "policy_revision": "mathgraph-0.3.0",
            "protocol": "mathgraph-agent-v4",
            "project_id": card["project_id"],
            "round_id": card["round_id"],
            "assignment_id": card["assignment_id"],
            "assignment_sha256": card["assignment_sha256"],
            "task_card_sha256": hashlib.sha256(card_path.read_bytes()).hexdigest(),
            "blackboard_snapshot_sha256": "0" * 64,
            "worker": card["worker_id"],
            "memory_id": card["memory_id"],
            "mode": card["mode"],
            "outcome": "dead_end",
            "obligation_ledger": [],
            "blackboard_graph_delta": {
                "base_snapshot_id": card["blackboard_view"]["snapshot_id"],
                "add_nodes": [],
                "add_edges": [],
            },
            "narrative_summary": "No result.",
            "claim": "fixture",
            "method": "fixture",
            "failure_mode": "fixture",
            "what_remains_open": "fixture",
            "artifacts": [],
        }
        with self.assertRaisesRegex(ValueError, "snapshot"):
            validate_worker_return(
                payload,
                assignment,
                manifest,
                project_root=self.root,
            )

    def test_validate_return_preflights_graph_registry_before_ingestion(self) -> None:
        planned = self._planned_round()
        payload, card, return_path = self._fact_submission_return(
            planned,
            add_graph_node=True,
        )
        node_id = payload["blackboard_graph_delta"]["add_nodes"][0]["node_id"]
        payload["blackboard_graph_delta"]["add_edges"].append(
            make_edge(
                edge_type="supports",
                source_node_id=node_id,
                target_node_id=self.root_space,
                payload={"scope": "unregistered shorthand"},
                created_by_assignment_id=card["assignment_id"],
            )
        )
        return_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "unregistered"):
            validate_return(
                self.store,
                planned["round_id"],
                card["assignment_id"],
            )
        self.assertFalse(return_path.with_suffix(".receipt.json").exists())

    def test_blackboard_merge_is_idempotent(self) -> None:
        planned = self._planned_round()
        assignment = planned["assignments"][0]
        card = json.loads(Path(assignment["task_card_path"]).read_text())
        node = self._node("idempotent", assignment=card["assignment_id"])
        placement = make_edge(
            edge_type="placed_in",
            source_node_id=node["node_id"],
            target_node_id=self.root_space,
            payload={},
            created_by_assignment_id=card["assignment_id"],
        )
        delta = {
            "base_snapshot_id": card["blackboard_view"]["snapshot_id"],
            "add_nodes": [node],
            "add_edges": [placement],
        }
        first = self.blackboard.merge_delta(
            delta=delta,
            task_card=card,
            return_sha256="1" * 64,
        )
        second = self.blackboard.merge_delta(
            delta=delta,
            task_card=card,
            return_sha256="1" * 64,
        )
        self.assertEqual(first, second)
        self.assertEqual(len(self.blackboard.nodes()), 2)

    def test_blackboard_conflict_is_not_last_write_wins(self) -> None:
        first = make_node(
            node_type="formula",
            logical_key="F2",
            payload={"formula": "x"},
            created_by_assignment_id="main",
        )
        second = make_node(
            node_type="formula",
            logical_key="F2",
            payload={"formula": "y"},
            created_by_assignment_id="main",
        )
        self.blackboard.add_node_with_placements(
            node=first, space_ids=[self.root_space], actor="main"
        )
        # Direct mutations do not synthesize conflict nodes; deterministic
        # worker merge does, which is the concurrent-write boundary.
        planned = self._planned_round()
        card = json.loads(
            Path(planned["assignments"][0]["task_card_path"]).read_text()
        )
        second["created_by_assignment_id"] = card["assignment_id"]
        second["node_id"] = make_node(
            node_type="formula",
            logical_key="F2",
            payload={"formula": "y"},
            created_by_assignment_id=card["assignment_id"],
        )["node_id"]
        placement = make_edge(
            edge_type="placed_in",
            source_node_id=second["node_id"],
            target_node_id=self.root_space,
            payload={},
            created_by_assignment_id=card["assignment_id"],
        )
        self.blackboard.merge_delta(
            delta={
                "base_snapshot_id": card["blackboard_view"]["snapshot_id"],
                "add_nodes": [second],
                "add_edges": [placement],
            },
            task_card=card,
            return_sha256="2" * 64,
        )
        formulas = [
            node
            for node in self.blackboard.nodes().values()
            if node["node_type"] == "formula"
        ]
        conflicts = [
            node
            for node in self.blackboard.nodes().values()
            if node["node_type"] == "conflict"
        ]
        self.assertEqual(len(formulas), 2)
        self.assertEqual(len(conflicts), 1)

    def test_blackboard_node_can_be_placed_in_multiple_spaces_without_copying_bytes(self) -> None:
        second_space = self.blackboard.create_space(
            name="second",
            scope="Second view",
            actor="main",
            overlaps_with=self.root_space,
        )
        node = self._node("multi-placement")
        receipt = self.blackboard.add_node_with_placements(
            node=node,
            space_ids=[self.root_space, second_space],
            actor="main",
        )
        self.assertEqual(receipt["node_ids"], [node["node_id"]])
        placements = [
            edge
            for edge in self.blackboard.edges().values()
            if edge["edge_type"] == "placed_in"
            and edge["source_node_id"] == node["node_id"]
        ]
        self.assertEqual(len(placements), 2)

    def test_blackboard_cross_space_edge_is_preserved_in_snapshot(self) -> None:
        second_space = self.blackboard.create_space(
            name="second",
            scope="Second view",
            actor="main",
            overlaps_with=self.root_space,
        )
        left, right = self._node("left"), self._node("right")
        self.blackboard.add_node_with_placements(
            node=left, space_ids=[self.root_space], actor="main"
        )
        self.blackboard.add_node_with_placements(
            node=right, space_ids=[second_space], actor="main"
        )
        relation = make_edge(
            edge_type="analogous_to",
            source_node_id=left["node_id"],
            target_node_id=right["node_id"],
            payload={"reason": "fixture"},
            created_by_assignment_id="main",
        )
        self.blackboard.add_objects(nodes=[], edges=[relation], actor="main")
        snap = self.blackboard.snapshot(
            query=self._query(left["node_id"]),
            actor="main",
        )
        _, edges = self.blackboard.snapshot_objects(snap["snapshot_id"])
        self.assertIn(relation["edge_id"], edges)

    def test_blackboard_custom_type_is_opaque_until_registered(self) -> None:
        node = make_node(
            node_type="x-tests:idea",
            logical_key="opaque",
            payload={},
            created_by_assignment_id="main",
        )
        self.blackboard.add_node_with_placements(
            node=node,
            space_ids=[self.root_space],
            actor="main",
        )
        self.assertIn(node["node_id"], self.blackboard.nodes())
        self.assertEqual(
            self.blackboard.effective_type_definition(
                "node", "x-tests:idea", 1
            )["automation_semantics"],
            "opaque",
        )
        self.blackboard.register_type(
            kind="node",
            definition={
                "name": "x-tests:idea",
                "type_version": 1,
                "logical_key_policy": "ignored",
                "automation_semantics": "opaque",
            },
            actor="operator",
        )
        self.assertIn(node["node_id"], self.blackboard.nodes())

    def test_blackboard_general_relation_allows_cycle(self) -> None:
        left, right = self._node("cycle-left"), self._node("cycle-right")
        self.blackboard.add_node_with_placements(
            node=left, space_ids=[self.root_space], actor="main"
        )
        self.blackboard.add_node_with_placements(
            node=right, space_ids=[self.root_space], actor="main"
        )
        edges = [
            make_edge(
                edge_type="analogous_to",
                source_node_id=source,
                target_node_id=target,
                payload={},
                created_by_assignment_id="main",
            )
            for source, target in (
                (left["node_id"], right["node_id"]),
                (right["node_id"], left["node_id"]),
            )
        ]
        self.blackboard.add_objects(nodes=[], edges=edges, actor="main")
        self.assertTrue(set(edge["edge_id"] for edge in edges).issubset(self.blackboard.edges()))

    def test_blackboard_dag_relation_rejects_cycle(self) -> None:
        child = self.blackboard.create_space(
            name="child",
            scope="Child",
            actor="main",
            parent_space_id=self.root_space,
        )
        cycle = make_edge(
            edge_type="subspace_of",
            source_node_id=self.root_space,
            target_node_id=child,
            payload={},
            created_by_assignment_id="main",
        )
        with self.assertRaisesRegex(ValueError, "cycle"):
            self.blackboard.add_objects(nodes=[], edges=[cycle], actor="main")

    def test_blackboard_snapshot_is_deterministic_under_completion_reordering(self) -> None:
        def build(order: list[str]) -> str:
            root = Path(tempfile.mkdtemp())
            store = MathGraphStore(root)
            store.initialize(
                project_id="determinism",
                title="determinism",
                workflow_evidence_version=4,
            )
            board = store.blackboard()
            space = next(
                key
                for key, value in board.nodes().items()
                if value["node_type"] == "space"
            )
            for key in order:
                node = make_node(
                    node_type="note",
                    logical_key=key,
                    payload={"text": key},
                    created_by_assignment_id="main",
                )
                board.add_node_with_placements(
                    node=node,
                    space_ids=[space],
                    actor="main",
                )
            return board.snapshot(
                query=self._query(space),
                actor="main",
            )["snapshot_id"]

        self.assertEqual(build(["a", "b"]), build(["b", "a"]))

    def test_blackboard_snapshot_budget_emits_omission_receipt(self) -> None:
        for key in ("a", "b"):
            self.blackboard.add_node_with_placements(
                node=self._node(key),
                space_ids=[self.root_space],
                actor="main",
            )
        result = self.blackboard.query(
            self._query(self.root_space, node_budget=1)
        )
        self.assertTrue(result["omission_receipt"]["node_budget_hit"])
        self.assertGreater(result["omission_receipt"]["omitted_node_count"], 0)

    def test_blackboard_delta_over_budget_rejects_entire_return(self) -> None:
        planned = self._planned_round()
        card = json.loads(
            Path(planned["assignments"][0]["task_card_path"]).read_text()
        )
        before = self.blackboard.visible_ids()
        delta = {
            "base_snapshot_id": card["blackboard_view"]["snapshot_id"],
            "add_nodes": [{}]
            * (card["budgets"]["max_blackboard_nodes_added"] + 1),
            "add_edges": [],
        }
        with self.assertRaisesRegex(ValueError, "budget"):
            self.blackboard.merge_delta(
                delta=delta,
                task_card=card,
                return_sha256="3" * 64,
            )
        self.assertEqual(before, self.blackboard.visible_ids())

    def test_worker_cannot_write_unbound_existing_space(self) -> None:
        planned = self._planned_round()
        card = json.loads(
            Path(planned["assignments"][0]["task_card_path"]).read_text()
        )
        # Create the space after the task card is sealed.  It is a real,
        # currently visible space, but it is outside this assignment's
        # capability and snapshot binding.
        unbound_space = self.blackboard.create_space(
            name="unbound",
            scope="not writable by this assignment",
            actor="main",
            parent_space_id=self.root_space,
        )
        self.assertNotIn(
            unbound_space,
            card["blackboard_view"]["write_space_ids"],
        )
        node = self._node(
            "unbound-write",
            assignment=card["assignment_id"],
        )
        placement = make_edge(
            edge_type="placed_in",
            source_node_id=node["node_id"],
            target_node_id=unbound_space,
            payload={},
            created_by_assignment_id=card["assignment_id"],
        )
        with self.assertRaisesRegex(ValueError, "write|space|capability"):
            self.blackboard.merge_delta(
                delta={
                    "base_snapshot_id": card["blackboard_view"]["snapshot_id"],
                    "add_nodes": [node],
                    "add_edges": [placement],
                },
                task_card=card,
                return_sha256="7" * 64,
            )
        self.assertNotIn(node["node_id"], self.blackboard.nodes())

    def test_blackboard_node_add_and_placements_are_atomic(self) -> None:
        node = self._node("atomic-placement")
        before = self.blackboard.visible_ids()
        with self.assertRaisesRegex(ValueError, "endpoint|space"):
            self.blackboard.add_node_with_placements(
                node=node,
                space_ids=[self.root_space, "bbn-" + "0" * 64],
                actor="main",
            )
        self.assertEqual(before, self.blackboard.visible_ids())
        self.assertFalse(
            (self.blackboard.nodes_dir / f"{node['node_id']}.json").exists()
        )

    def test_placement_retraction_preserves_historical_layout(self) -> None:
        node = self._node("retract")
        receipt = self.blackboard.add_node_with_placements(
            node=node,
            space_ids=[self.root_space],
            actor="main",
        )
        placement_id = receipt["edge_ids"][0]
        retraction = make_edge(
            edge_type="retracts_placement",
            source_node_id=node["node_id"],
            target_node_id=self.root_space,
            payload={"placement_edge_id": placement_id},
            created_by_assignment_id="main",
        )
        self.blackboard.add_objects(nodes=[], edges=[retraction], actor="main")
        self.assertIn(placement_id, self.blackboard.edges())
        self.assertNotIn(placement_id, self.blackboard.current_edges())

    def test_blackboard_type_registration_is_append_only(self) -> None:
        definition = {
            "name": "x-tests:relation",
            "type_version": 1,
            "allowed_source_types": ["*"],
            "allowed_target_types": ["*"],
            "allow_self_edge": False,
            "cycle_policy": "allow",
            "automation_semantics": "opaque",
        }
        self.blackboard.register_type(
            kind="edge", definition=definition, actor="operator"
        )
        modified = {**definition, "cycle_policy": "forbid"}
        with self.assertRaisesRegex(ValueError, "redefinition"):
            self.blackboard.register_type(
                kind="edge", definition=modified, actor="operator"
            )

    def test_blackboard_node_and_edge_cannot_be_predecessors(self) -> None:
        with self.assertRaises(ValueError):
            self.store._validate_predecessors(["bbn-" + "0" * 64])
        with self.assertRaises(ValueError):
            self.store._validate_predecessors(["bbe-" + "0" * 64])

    def test_blackboard_node_cannot_be_predecessor(self) -> None:
        with self.assertRaises(ValueError):
            self.store._validate_predecessors(["bbn-" + "0" * 64])

    def test_blackboard_edge_cannot_be_predecessor(self) -> None:
        with self.assertRaises(ValueError):
            self.store._validate_predecessors(["bbe-" + "0" * 64])

    def test_blackboard_rejects_truth_bearing_proves_and_refutes_edges(self) -> None:
        left, right = self._node("truth-left"), self._node("truth-right")
        for node in (left, right):
            self.blackboard.add_node_with_placements(
                node=node, space_ids=[self.root_space], actor="main"
            )
        for relation in ("proves", "refutes"):
            edge = make_edge(
                edge_type=relation,
                source_node_id=left["node_id"],
                target_node_id=right["node_id"],
                payload={},
                created_by_assignment_id="main",
            )
            with self.assertRaisesRegex(ValueError, "proves/refutes"):
                self.blackboard.add_objects(
                    nodes=[], edges=[edge], actor="main"
                )

    def test_blackboard_reindex_dry_run_is_read_only_and_apply_is_reproducible(self) -> None:
        self.blackboard.index_path.write_text("{}\n")
        before = self.blackboard.index_path.read_bytes()
        dry = self.blackboard.reindex(apply=False)
        self.assertFalse(dry["clean"])
        self.assertEqual(before, self.blackboard.index_path.read_bytes())
        applied = self.blackboard.reindex(apply=True, actor="operator")
        self.assertTrue(applied["clean"])
        self.assertTrue(self.blackboard.reindex(apply=False)["clean"])

    def test_direct_handoff_requires_assignment_and_final_status_only(self) -> None:
        payload = {
            "assignment_id": "a01-0123456789ab-prove",
            "status": "final",
        }
        self.assertEqual(validate_final_handoff(payload), payload)
        legacy = {**payload, "return_sha256": "4" * 64}
        self.assertEqual(validate_final_handoff(legacy), legacy)
        with self.assertRaisesRegex(ValueError, "unknown"):
            validate_final_handoff({**payload, "summary": "too much"})

    def test_control_followup_has_fixed_actions_and_bounded_payload(self) -> None:
        payload = {
            "type": "control",
            "assignment_id": "a01-0123456789ab-prove",
            "action": "clarify",
            "payload": {"question": "Which frozen clause is intended?"},
        }
        self.assertEqual(validate_control_followup(payload), payload)
        with self.assertRaisesRegex(ValueError, "action is invalid"):
            validate_control_followup({**payload, "action": "send-proof"})
        with self.assertRaisesRegex(ValueError, "8 KiB"):
            validate_control_followup(
                {**payload, "payload": {"text": "x" * (8 * 1024)}}
            )

    def test_v4_counterexample_ingestion_binds_blackboard_transaction(self) -> None:
        planned = self._planned_round()
        assignment = planned["assignments"][0]
        card_path = Path(assignment["task_card_path"])
        card = json.loads(card_path.read_text())
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
            "outcome": "counterexample",
            "obligation_ledger": [],
            "blackboard_graph_delta": {
                "base_snapshot_id": card["blackboard_view"]["snapshot_id"],
                "add_nodes": [],
                "add_edges": [],
            },
            "narrative_summary": "Found a toy counterexample.",
            "claim": "The unrestricted claim fails.",
            "construction": "Take the zero object.",
            "verification": "Direct substitution.",
            "artifacts": [],
        }
        return_path = Path(assignment["return_path"])
        return_path.write_text(json.dumps(payload))
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
        self.assertEqual(receipt["schema_version"], 4)
        self.assertIn("blackboard_transaction_id", receipt)
        self.assertEqual(receipt["status"], "ingested")
        child = self.store.memory_latest()[
            receipt["memory_entry_id"]
        ]
        self.assertEqual(
            child["source"],
            assignment["return_relpath"],
        )
        self.assertTrue(
            (self.root / child["source"]).is_file()
        )
        self.assertFalse(return_path.stat().st_mode & 0o222)

    def test_v4_invalid_delta_has_zero_ingestion_effect(self) -> None:
        planned = self._planned_round()
        assignment = planned["assignments"][0]
        card_path = Path(assignment["task_card_path"])
        card = json.loads(card_path.read_text())
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
                "base_snapshot_id": "bbs-" + "0" * 64,
                "add_nodes": [],
                "add_edges": [],
            },
            "narrative_summary": "No result.",
            "claim": "Fixture",
            "method": "Fixture",
            "failure_mode": "Fixture",
            "what_remains_open": "Everything",
            "artifacts": [],
        }
        return_path = Path(assignment["return_path"])
        return_path.write_text(json.dumps(payload))
        memory_before = self.store.memory_latest()
        graph_before = self.blackboard.visible_ids()
        with self.assertRaisesRegex(ValueError, "base snapshot"):
            validate_return(
                self.store,
                planned["round_id"],
                card["assignment_id"],
            )
        self.assertEqual(memory_before, self.store.memory_latest())
        self.assertEqual(graph_before, self.blackboard.visible_ids())
        self.assertFalse(
            return_path.with_suffix(".receipt.json").exists()
        )

    def test_v4_fact_submission_ingests_as_candidate_not_truth(self) -> None:
        planned = self._planned_round()
        assignment = planned["assignments"][0]
        card_path = Path(assignment["task_card_path"])
        card = json.loads(card_path.read_text())
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
            "outcome": "fact_submission",
            "obligation_ledger": [],
            "blackboard_graph_delta": {
                "base_snapshot_id": card["blackboard_view"]["snapshot_id"],
                "add_nodes": [],
                "add_edges": [],
            },
            "narrative_summary": "A direct atomic proof.",
            "claim_relation": "proves",
            "statement": "[CLAIM:MAIN] The toy identity holds.",
            "proof": "Both sides are identical.",
            "predecessors": [],
            "predecessor_uses": [],
            "quantifier_ledger": [],
            "convention_profile_ids": [],
            "computational_evidence": [],
            "terminology": [],
            "glossary_introduces": {},
            "external_refs": [],
            "elementary_uses": [],
            "intuition": "",
            "artifacts": [],
        }
        return_path = Path(assignment["return_path"])
        return_path.write_text(json.dumps(payload))
        validated = validate_return(
            self.store,
            planned["round_id"],
            card["assignment_id"],
        )
        receipt = ingest_return(
            self.store,
            planned["round_id"],
            card["assignment_id"],
        )
        self.assertEqual(receipt["return_sha256"], validated["return_sha256"])
        self.assertEqual(
            receipt["worker_final_sha256"], validated["return_sha256"]
        )
        fact_id = receipt["submission_id"]
        self.assertEqual(
            self.store.submission(fact_id)["evidence_version"],
            4,
        )
        self.assertFalse(self.store.fact_path(fact_id).exists())
        report = self.store.audit()
        self.assertTrue(report.current_ok, report.errors)
        self.assertEqual(report.candidates, 1)

    def test_blackboard_ingest_is_all_or_nothing_with_submission(self) -> None:
        planned = self._planned_round()
        payload, card, return_path = self._fact_submission_return(
            planned,
            add_graph_node=True,
        )
        node_id = payload["blackboard_graph_delta"]["add_nodes"][0]["node_id"]
        return_path.write_text(json.dumps(payload), encoding="utf-8")
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
        self.assertEqual(
            self.store.submission(receipt["submission_id"])["fact_id"],
            receipt["submission_id"],
        )
        self.assertIn(node_id, self.blackboard.nodes())
        self.assertEqual(
            receipt["effect"]["submission_id"],
            receipt["submission_id"],
        )
        self.assertEqual(
            receipt["ingestion_sha256"],
            self.store._read_json(
                return_path.with_suffix(".receipt.json")
            )["ingestion_sha256"],
        )

    def test_blackboard_ingest_crash_before_receipt_has_zero_visible_delta(self) -> None:
        planned = self._planned_round()
        payload, card, return_path = self._fact_submission_return(
            planned,
            add_graph_node=True,
        )
        node_id = payload["blackboard_graph_delta"]["add_nodes"][0]["node_id"]
        return_path.write_text(json.dumps(payload), encoding="utf-8")
        validated = validate_return(
            self.store,
            planned["round_id"],
            card["assignment_id"],
        )
        receipt_path = return_path.with_suffix(".receipt.json")
        original_write = self.store._write_json_once

        def crash_before_marker(path: Path, value: dict) -> None:
            if Path(path) == receipt_path:
                raise RuntimeError("simulated crash before ingestion marker")
            original_write(path, value)

        with patch.object(
            self.store,
            "_write_json_once",
            side_effect=crash_before_marker,
        ):
            with self.assertRaisesRegex(RuntimeError, "simulated crash"):
                ingest_return(
                    self.store,
                    planned["round_id"],
                    card["assignment_id"],
                    worker_final_sha256=validated["return_sha256"],
                )
        staged = list(self.store.submissions_dir.glob("*.json"))
        self.assertEqual(len(staged), 1)
        with self.assertRaisesRegex(KeyError, "uncommitted"):
            self.store.submission(staged[0].stem)
        self.assertNotIn(node_id, self.blackboard.nodes())
        self.assertFalse(receipt_path.exists())
        self.assertTrue(
            any(
                "pre-receipt" in warning
                for warning in self.blackboard.audit()["warnings"]
            )
        )

    def test_blackboard_ingest_recovery_rebuilds_indices_from_receipt(self) -> None:
        planned = self._planned_round()
        payload, card, return_path = self._fact_submission_return(
            planned,
            add_graph_node=True,
        )
        node_id = payload["blackboard_graph_delta"]["add_nodes"][0]["node_id"]
        return_path.write_text(json.dumps(payload), encoding="utf-8")
        validated = validate_return(
            self.store,
            planned["round_id"],
            card["assignment_id"],
        )
        receipt_path = return_path.with_suffix(".receipt.json")
        original_write = self.store._write_json_once

        def crash_before_marker(path: Path, value: dict) -> None:
            if Path(path) == receipt_path:
                raise RuntimeError("simulated crash before ingestion marker")
            original_write(path, value)

        with patch.object(
            self.store,
            "_write_json_once",
            side_effect=crash_before_marker,
        ):
            with self.assertRaises(RuntimeError):
                ingest_return(
                    self.store,
                    planned["round_id"],
                    card["assignment_id"],
                    worker_final_sha256=validated["return_sha256"],
                )
        receipt = ingest_return(
            self.store,
            planned["round_id"],
            card["assignment_id"],
            worker_final_sha256=validated["return_sha256"],
        )
        self.assertIn(node_id, self.blackboard.nodes())
        self.assertEqual(
            self.store.submission(receipt["submission_id"])["fact_id"],
            receipt["submission_id"],
        )
        self.assertTrue(self.blackboard.reindex(apply=False)["clean"])
        self.assertEqual(
            ingest_return(
                self.store,
                planned["round_id"],
                card["assignment_id"],
                worker_final_sha256=validated["return_sha256"],
            ),
            receipt,
        )


class SkillCollaborationPolicyTests(unittest.TestCase):
    def test_v5_retires_new_pulse_planning_while_v4_policy_stays_bounded(self) -> None:
        skill_root = Path(__file__).resolve().parents[1]
        skill = (skill_root / "SKILL.md").read_text(encoding="utf-8")
        adoption = (
            skill_root / "references" / "adoption_policy_v4.md"
        ).read_text(encoding="utf-8")
        adapter = (
            skill_root / "references" / "multi_agent_adapter.md"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "Every worker task card retains three communication planes",
            skill,
        )
        self.assertIn("New V5 Pulse planning is retired", skill)
        self.assertIn(
            "production/supervision cycle is the only prospective Research collaboration path",
            skill,
        )
        self.assertIn(
            "Existing historical Pulse records retain status, audit, dispatch, close, void, and abort compatibility",
            skill,
        )
        self.assertNotIn("optional two-wave Pulse", skill)
        self.assertIn(
            "When its status is `required`",
            adoption,
        )
        self.assertIn("When pulse status is `available`", adoption)
        self.assertNotIn("substantive Chalk research fills every callable", adoption)
        self.assertIn(
            "The second-wave task must require inspection of at least one peer node",
            adapter,
        )
        self.assertIn("parallel_clean_context_panel.status", adapter)
        self.assertIn("barriered_blackboard_pulse.status", adapter)
        self.assertIn("an empty edge does not count", adapter)
        self.assertIn("Exactly 1200 seconds does not trigger", adapter)
        self.assertIn(
            "Estimated budget, duration, cost, and burden may affect only",
            adapter,
        )


if __name__ == "__main__":
    unittest.main()

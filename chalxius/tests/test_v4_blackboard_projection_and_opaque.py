from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mathgraph.blackboard import BlackboardStore, make_edge, make_node
from mathgraph.store import MathGraphStore


class BlackboardProjectionAndOpaqueTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = MathGraphStore(self.root)
        self.store.initialize(
            project_id="blackboard-projection-tests",
            title="Blackboard projection tests",
            workflow_evidence_version=4,
        )
        self.board = self.store.blackboard()
        self.root_space = next(
            node_id
            for node_id, node in self.board.nodes().items()
            if node["node_type"] == "space"
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _query(*seeds: str, max_hops: int = 1) -> dict:
        return {
            "seed_node_ids": list(seeds),
            "direction": "both",
            "max_hops": max_hops,
            "edge_type_allowlist": ["*"],
            "node_type_allowlist": ["*"],
            "node_budget": 64,
            "edge_budget": 128,
        }

    @staticmethod
    def _note(key: str) -> dict:
        return make_node(
            node_type="note",
            logical_key=key,
            payload={"text": key},
            created_by_assignment_id="main",
        )

    def _place(self, node: dict) -> str:
        receipt = self.board.add_node_with_placements(
            node=node,
            space_ids=[self.root_space],
            actor="main",
        )
        return receipt["edge_ids"][0]

    def test_unregistered_namespaced_types_are_opaque_not_rejected(self) -> None:
        left = make_node(
            node_type="x-tests:idea",
            logical_key="left",
            payload={"text": "left"},
            created_by_assignment_id="main",
        )
        right = make_node(
            node_type="x-tests:idea",
            logical_key="right",
            payload={"text": "right"},
            created_by_assignment_id="main",
        )
        self._place(left)
        self._place(right)
        opaque = make_edge(
            edge_type="x-tests:cross-check",
            source_node_id=left["node_id"],
            target_node_id=right["node_id"],
            payload={"note": "display only until registered"},
            created_by_assignment_id="main",
        )
        self.board.add_objects(nodes=[], edges=[opaque], actor="main")

        self.assertIsNone(
            self.board.type_definition("node", "x-tests:idea", 1)
        )
        self.assertEqual(
            self.board.effective_type_definition(
                "node", "x-tests:idea", 1
            )["automation_semantics"],
            "opaque",
        )
        self.assertEqual(
            self.board.effective_type_definition(
                "edge", "x-tests:cross-check", 1
            )["automation_semantics"],
            "opaque",
        )

        one_seed = self.board.query(self._query(left["node_id"]))
        self.assertNotIn(right["node_id"], one_seed["node_ids"])
        self.assertNotIn(opaque["edge_id"], one_seed["edge_ids"])

        both_seeds = self.board.query(
            self._query(left["node_id"], right["node_id"], max_hops=0)
        )
        self.assertIn(opaque["edge_id"], both_seeds["edge_ids"])

        self.board.register_type(
            kind="edge",
            definition={
                "name": "x-tests:cross-check",
                "type_version": 1,
                "allowed_source_types": ["*"],
                "allowed_target_types": ["*"],
                "allow_self_edge": False,
                "cycle_policy": "allow",
                "automation_semantics": "exploration_only",
            },
            actor="operator",
        )
        registered = self.board.query(self._query(left["node_id"]))
        self.assertIn(right["node_id"], registered["node_ids"])
        self.assertIn(opaque["edge_id"], registered["edge_ids"])

    def test_projection_folds_nodes_edges_and_index_without_erasing_history(
        self,
    ) -> None:
        original = self._note("original")
        replacement = self._note("replacement")
        closer = self._note("closer")
        peer = self._note("peer")
        placements = {
            node["logical_key"]: self._place(node)
            for node in (original, replacement, closer, peer)
        }
        semantic_edge = make_edge(
            edge_type="motivates",
            source_node_id=original["node_id"],
            target_node_id=peer["node_id"],
            payload={},
            created_by_assignment_id="main",
        )
        self.board.add_objects(
            nodes=[],
            edges=[semantic_edge],
            actor="main",
        )
        supersedes = make_edge(
            edge_type="supersedes",
            source_node_id=replacement["node_id"],
            target_node_id=original["node_id"],
            payload={},
            created_by_assignment_id="main",
        )
        closes = make_edge(
            edge_type="closes",
            source_node_id=closer["node_id"],
            target_node_id=replacement["node_id"],
            payload={},
            created_by_assignment_id="main",
        )
        retraction = make_edge(
            edge_type="retracts_placement",
            source_node_id=replacement["node_id"],
            target_node_id=self.root_space,
            payload={
                "placement_edge_id": placements["replacement"],
            },
            created_by_assignment_id="main",
        )
        self.board.add_objects(
            nodes=[],
            edges=[supersedes, closes, retraction],
            actor="main",
        )

        history_nodes = self.board.nodes()
        history_edges = self.board.edges()
        self.assertIn(original["node_id"], history_nodes)
        self.assertIn(replacement["node_id"], history_nodes)
        self.assertIn(supersedes["edge_id"], history_edges)
        self.assertIn(closes["edge_id"], history_edges)
        self.assertIn(retraction["edge_id"], history_edges)

        projection = self.board.current_projection()
        self.assertEqual(
            projection["inactive_node_ids"],
            sorted([original["node_id"], replacement["node_id"]]),
        )
        self.assertEqual(
            projection["inactive_node_causes"],
            {
                original["node_id"]: [supersedes["edge_id"]],
                replacement["node_id"]: [closes["edge_id"]],
            },
        )
        self.assertEqual(
            projection["projection_edge_ids"],
            sorted(
                [
                    supersedes["edge_id"],
                    closes["edge_id"],
                    retraction["edge_id"],
                ]
            ),
        )
        self.assertEqual(
            projection["retracted_placement_edge_ids"],
            [placements["replacement"]],
        )

        current_nodes = self.board.current_nodes()
        current_edges = self.board.current_edges()
        self.assertNotIn(original["node_id"], current_nodes)
        self.assertNotIn(replacement["node_id"], current_nodes)
        self.assertIn(closer["node_id"], current_nodes)
        self.assertIn(peer["node_id"], current_nodes)
        self.assertEqual(
            self.board.show(original["node_id"]),
            original,
        )
        with self.assertRaisesRegex(ValueError, "unknown seeds"):
            self.board.query(self._query(original["node_id"]))
        for inactive_edge_id in (
            placements["original"],
            placements["replacement"],
            semantic_edge["edge_id"],
            supersedes["edge_id"],
            closes["edge_id"],
            retraction["edge_id"],
        ):
            self.assertNotIn(inactive_edge_id, current_edges)
        self.assertIn(placements["closer"], current_edges)
        self.assertIn(placements["peer"], current_edges)

        self.board.reindex(apply=True, actor="operator")
        index = self.board._read_json(self.board.index_path)
        self.assertEqual(index["current_projection"], projection)
        self.assertEqual(
            index["by_type"]["note"],
            sorted([closer["node_id"], peer["node_id"]]),
        )
        self.assertTrue(self.board.audit()["ok"])

    def test_projection_payload_and_context_are_fail_closed_in_audit(
        self,
    ) -> None:
        left = self._note("left")
        right = self._note("right")
        left_placement = self._place(left)
        self._place(right)

        malformed_supersedes = make_edge(
            edge_type="supersedes",
            source_node_id=right["node_id"],
            target_node_id=left["node_id"],
            payload={"reason": "payload is not part of the projection"},
            created_by_assignment_id="main",
        )
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            self.board.add_objects(
                nodes=[],
                edges=[malformed_supersedes],
                actor="main",
            )

        malformed_retraction = make_edge(
            edge_type="retracts_placement",
            source_node_id=left["node_id"],
            target_node_id=self.root_space,
            payload={},
            created_by_assignment_id="main",
        )
        with self.assertRaisesRegex(ValueError, "missing fields"):
            self.board.add_objects(
                nodes=[],
                edges=[malformed_retraction],
                actor="main",
            )

        mismatched_retraction = make_edge(
            edge_type="retracts_placement",
            source_node_id=right["node_id"],
            target_node_id=self.root_space,
            payload={"placement_edge_id": left_placement},
            created_by_assignment_id="main",
        )
        with self.assertRaisesRegex(ValueError, "matching visible placement"):
            self.board.add_objects(
                nodes=[],
                edges=[mismatched_retraction],
                actor="main",
            )

        self.board.reindex(apply=True, actor="operator")
        self.board._stage_and_commit(
            nodes=[],
            edges=[mismatched_retraction],
            kind="audit-fixture",
            actor="main",
        )
        audit = self.board.audit()
        self.assertFalse(audit["ok"])
        self.assertTrue(
            any(
                "current projection replay failed" in error
                and "matching visible placement" in error
                for error in audit["errors"]
            )
        )


if __name__ == "__main__":
    unittest.main()

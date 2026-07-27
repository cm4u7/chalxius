from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "learning_graph.py"
SPEC = importlib.util.spec_from_file_location("grill_learning_graph", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
lg = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lg)


class LearningGraphInteropTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_jsonl(self, path: Path, values: list[dict]) -> list[dict]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "".join(
                json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n"
                for value in values
            ),
            encoding="utf-8",
        )
        return [
            {
                "object_id": value.get("object_id"),
                "sha256": lg.canonical_sha256(value),
            }
            for value in values
        ]

    def make_paper_snapshot(self) -> tuple[str, Path, list[dict]]:
        snapshot_id = "pls-" + "a" * 64
        snapshot = (
            self.root / "paper_logic" / "snapshots" / "by-id" / snapshot_id
        )
        source_id = "psn-" + "1" * 64
        target_id = "prn-" + "2" * 64
        audit_id = "pan-" + "3" * 64
        nodes = [
            {
                "object_id": source_id,
                "object_type": "source_unit",
                "logical_key": "source",
                "payload": {"text": "Exact source sentence."},
                "plane": "paper_source",
                "truth_effect": "none",
            },
            {
                "object_id": target_id,
                "object_type": "paper_target",
                "logical_key": "target",
                "payload": {"claim": "Reconstructed thesis.", "target_role": "headline"},
                "plane": "paper_reconstruction",
                "truth_effect": "none",
            },
            {
                "object_id": audit_id,
                "object_type": "audit_finding",
                "logical_key": "audit",
                "payload": {"claim": "The inference needs a scope premise."},
                "plane": "paper_audit",
                "truth_effect": "none",
            },
        ]
        edges = [
            {
                "object_id": "pae-" + "4" * 64,
                "source_id": source_id,
                "target_id": target_id,
                "relation_type": "supports",
                "payload": {},
                "plane": "paper_reconstruction",
                "truth_effect": "none",
            },
            {
                "object_id": "pae-" + "5" * 64,
                "source_id": audit_id,
                "target_id": target_id,
                "relation_type": "audits",
                "payload": {},
                "plane": "paper_audit",
                "truth_effect": "none",
            },
        ]
        node_entries = self.write_jsonl(snapshot / "nodes.jsonl", nodes)
        edge_entries = self.write_jsonl(snapshot / "edges.jsonl", edges)
        manifest = {
            "snapshot_id": snapshot_id,
            "project_id": "paper-project",
            "paper_id": "paper-id",
            "truth_effect": "none",
            "current_audit_node_ids": [audit_id],
            "inactive_audit_node_ids": [],
            "node_entries": node_entries,
            "edge_entries": edge_entries,
        }
        (snapshot / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        return snapshot_id, snapshot, nodes

    def make_blackboard_snapshot(self) -> tuple[str, Path, str, str]:
        snapshot_id = "bbs-" + "b" * 64
        snapshot = (
            self.root / "blackboard" / "snapshots" / "by-hash" / snapshot_id
        )
        actual_id = "bbn-" + "6" * 64
        omitted_id = "bbn-" + "7" * 64
        nodes = [
            {
                "node_id": actual_id,
                "node_type": "observation",
                "logical_key": "visible",
                "payload": {"claim": "Exploratory possibility."},
                "truth_status": "exploration",
            }
        ]
        edges = [
            {
                "edge_id": "bbe-" + "8" * 64,
                "source_node_id": omitted_id,
                "target_node_id": actual_id,
                "edge_type": "challenges",
                "payload": {"note": "Boundary challenge."},
            }
        ]
        snapshot.mkdir(parents=True)
        (snapshot / "nodes.jsonl").write_text(
            json.dumps(nodes[0], sort_keys=True) + "\n", encoding="utf-8"
        )
        (snapshot / "edges.jsonl").write_text(
            json.dumps(edges[0], sort_keys=True) + "\n", encoding="utf-8"
        )
        manifest = {
            "snapshot_id": snapshot_id,
            "node_entries": [
                {"node_id": actual_id, "sha256": lg.canonical_sha256(nodes[0])}
            ],
            "edge_entries": [
                {"edge_id": edges[0]["edge_id"], "sha256": lg.canonical_sha256(edges[0])}
            ],
            "seed_node_ids": [actual_id],
            "query_sha256": "9" * 64,
            "omission_receipt": {
                "boundary_node_ids": [actual_id, omitted_id],
                "node_budget_hit": True,
                "edge_budget_hit": False,
                "omitted_node_count": 1,
                "omitted_edge_count": 0,
            },
        }
        (snapshot / "manifest.json").write_text(
            json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        return snapshot_id, snapshot, actual_id, omitted_id

    def make_fact_graph(self) -> Path:
        project = self.root / "danus"
        facts = project / "fact_graph" / "facts"
        facts.mkdir(parents=True)
        fact_id = "1" * 16
        (facts / f"{fact_id}.md").write_text(
            "---\n"
            f"fact_id: {fact_id}\n"
            "predecessors: []\n"
            "---\n\n"
            "## statement\n\nA native admitted fact.\n",
            encoding="utf-8",
        )
        (project / "TARGETS.txt").write_text(fact_id + "\n", encoding="utf-8")
        return project

    def test_fact_graph_remains_native_and_legacy_cli_identity_is_preserved(self) -> None:
        graph = lg.empty_learning_graph()
        snapshot = lg.snapshot_fact_source(str(self.make_fact_graph()))
        lg.merge_snapshot(graph, snapshot)
        self.assertEqual([], lg.verify_graph(lg.seal_graph(graph)))
        node_hash = next(iter(graph["nodes"]))
        node = graph["nodes"][node_hash]
        self.assertEqual("source_fact_artifact_sha256", node["identity_kind"])
        self.assertEqual("admitted", node["truth_status"])

    def test_paper_mount_preserves_planes_without_truth_inheritance(self) -> None:
        snapshot_id, _, nodes = self.make_paper_snapshot()
        mounted = lg.snapshot_paper_source(str(self.root), snapshot_id)
        graph = lg.empty_learning_graph()
        lg.merge_snapshot(graph, mounted)
        self.assertEqual([], lg.verify_graph(lg.seal_graph(graph)))
        statuses = {node["truth_status"] for node in graph["nodes"].values()}
        self.assertEqual(
            {
                "source-bound-nontruth",
                "reviewed-reconstruction-nontruth",
                "reviewed-audit-nontruth",
            },
            statuses,
        )
        target_alias = nodes[1]["object_id"]
        _, target = lg.resolve_node(graph, target_alias)
        self.assertEqual(0, target["learning"]["mastery"])
        self.assertEqual("headline", graph["targets"][0]["target_role"])

    def test_paper_snapshot_tamper_fails_drift_verification(self) -> None:
        snapshot_id, snapshot, _ = self.make_paper_snapshot()
        graph = lg.empty_learning_graph()
        lg.merge_snapshot(graph, lg.snapshot_paper_source(str(self.root), snapshot_id))
        text = (snapshot / "nodes.jsonl").read_text(encoding="utf-8")
        (snapshot / "nodes.jsonl").write_text(
            text.replace("Exact source sentence", "Changed source sentence"),
            encoding="utf-8",
        )
        errors = lg.verify_graph(lg.seal_graph(graph))
        self.assertTrue(any("source drift check failed" in error for error in errors))

    def test_blackboard_boundary_edges_become_nonlearnable_stubs(self) -> None:
        snapshot_id, _, actual_id, omitted_id = self.make_blackboard_snapshot()
        graph = lg.empty_learning_graph()
        lg.merge_snapshot(
            graph, lg.snapshot_blackboard_source(str(self.root), snapshot_id)
        )
        self.assertEqual([], lg.verify_graph(lg.seal_graph(graph)))
        self.assertEqual(2, len(graph["nodes"]))
        self.assertEqual(1, len(graph["edges"]))
        _, actual = lg.resolve_node(graph, actual_id)
        omitted_hash, omitted = lg.resolve_node(graph, omitted_id)
        self.assertEqual("exploration-nontruth", actual["truth_status"])
        self.assertEqual(
            "blackboard_boundary_stub_binding_sha256", omitted["identity_kind"]
        )
        with self.assertRaisesRegex(ValueError, "omitted boundary stub"):
            lg.require_learnable_node(graph, omitted_hash)

    def test_lightweight_concern_blocks_teaching_but_not_mastery_truth(self) -> None:
        snapshot_id, _, nodes = self.make_paper_snapshot()
        graph_path = self.root / "learning.json"
        graph = lg.empty_learning_graph()
        lg.merge_snapshot(graph, lg.snapshot_paper_source(str(self.root), snapshot_id))
        lg.atomic_write_json(graph_path, lg.seal_graph(graph), refuse_exists=True)
        target_alias = nodes[1]["object_id"]
        lg.cmd_record_source_concern(
            SimpleNamespace(
                graph=str(graph_path),
                node=target_alias,
                kind="misconstructed-edge",
                severity="blocking",
                description="The mounted relation may reverse support direction.",
            )
        )
        with self.assertRaisesRegex(ValueError, "blocking concerns"):
            lg.cmd_teach(
                SimpleNamespace(
                    graph=str(graph_path),
                    node=target_alias,
                    fact_hash=None,
                    coverage="taught-unchecked",
                    note="Do not teach this yet.",
                    source_locator=None,
                )
            )
        lg.cmd_record(
            SimpleNamespace(
                graph=str(graph_path),
                node=target_alias,
                fact_hash=None,
                mastery=2,
                status="developing",
                hint_level=0,
                error_class=None,
                evidence="Learner identified why the relation is questionable.",
                due_review=None,
            )
        )
        reloaded = lg.load_learning_graph(graph_path)
        _, target = lg.resolve_node(reloaded, target_alias)
        self.assertEqual(2, target["learning"]["mastery"])
        self.assertEqual("reviewed-reconstruction-nontruth", target["truth_status"])
        self.assertEqual(1, len(lg.active_source_concerns(reloaded)))

    def test_bounded_context_reports_truncation(self) -> None:
        snapshot_id, _, nodes = self.make_paper_snapshot()
        graph = lg.empty_learning_graph()
        lg.merge_snapshot(graph, lg.snapshot_paper_source(str(self.root), snapshot_id))
        node_hash, _ = lg.resolve_node(graph, nodes[1]["object_id"])
        context = lg.context_subgraph(graph, node_hash, radius=2, max_nodes=1)
        self.assertTrue(context["omission_receipt"]["truncated"])
        self.assertEqual(1, context["omission_receipt"]["returned_node_count"])


if __name__ == "__main__":
    unittest.main()

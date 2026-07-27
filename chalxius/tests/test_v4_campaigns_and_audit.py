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
from mathgraph.campaigns import actionable_score
from mathgraph.cli import main as cli_main
from mathgraph.contracts import sha256_json
from mathgraph.markdown import serialize_fact
from mathgraph.migration import (
    project_tree_snapshot,
    upgrade_stable_project_copy,
)
from mathgraph.model import Fact
from mathgraph.orchestrator import create_repair_round, create_round
from mathgraph.store import MathGraphStore


class V4CampaignAndAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = MathGraphStore(self.root)
        self.store.initialize(
            project_id="v4-campaign",
            title="V4 campaign",
            workflow_evidence_version=4,
        )
        self.campaigns = self.store.campaigns()
        self.campaign_id = self.campaigns.active()
        assert self.campaign_id is not None

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _campaign_payload(self, name: str = "test") -> dict:
        return {
            "name": name,
            "objective": "Resolve the literal claim.",
            "source_claim_ids": [],
            "targets": [],
            "constraints": ["exact arithmetic"],
            "stop_conditions": ["An admitted counterexample settles it."],
            "value_definition": "Prefer status-changing tasks.",
        }

    def _manual_fact(self, statement: str = "A fact.") -> Fact:
        fact = Fact(
            problem_id=self.store.project_id(),
            author="import",
            predecessors=[],
            statement=statement,
            proof="Direct proof.",
        )
        (self.store.facts_dir / f"{fact.fact_id}.md").write_text(
            serialize_fact(fact),
            encoding="utf-8",
        )
        return fact

    @staticmethod
    def _tree_inventory(root: Path) -> dict[str, str]:
        inventory: dict[str, str] = {}
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                inventory[relative] = "symlink"
            elif path.is_dir():
                inventory[relative] = "directory"
            elif path.is_file():
                inventory[relative] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
        return inventory

    def _promote_fixture(
        self,
        *,
        node_type: str = "conjecture",
    ) -> tuple[dict, dict, dict, str]:
        board = self.store.blackboard()
        space = next(
            node_id
            for node_id, node in board.nodes().items()
            if node["node_type"] == "space"
        )
        node = make_node(
            node_type=node_type,
            logical_key=f"promote-{node_type}",
            payload={"statement": "Promoted candidate."},
            created_by_assignment_id="main",
        )
        board.add_node_with_placements(
            node=node,
            space_ids=[space],
            actor="main",
        )
        query = {
            "seed_node_ids": [node["node_id"]],
            "direction": "both",
            "max_hops": 1,
            "edge_type_allowlist": ["*"],
            "node_type_allowlist": ["*"],
            "node_budget": 20,
            "edge_budget": 20,
        }
        snapshot = board.snapshot(query=query, actor="main")
        memory_id = self.campaigns.promote_blackboard_node(
            node["node_id"],
            {
                "snapshot_id": snapshot["snapshot_id"],
                "campaign_id": self.campaign_id,
                "memory_kind": "conjecture",
                "claim": "Promoted candidate task.",
                "rationale": "It is manually selected.",
                "mode_suggestions": ["refute"],
                "decision_profile": {
                    "burden": 0.2,
                    "impact": 0.8,
                    "information_value": 0.7,
                    "tractability": 0.8,
                },
                "blackboard_query": query,
            },
            actor="main",
            memory_add=lambda payload, actor: self.store.memory_add(
                payload,
                actor=actor,
            ),
        )
        return node, snapshot, query, memory_id

    def test_active_campaign_derives_targets_txt(self) -> None:
        fact = self._manual_fact()
        target_id = self.campaigns.target_add(
            self.campaign_id,
            {
                "role": "headline_proof",
                "subject_kind": "fact",
                "subject_id": fact.fact_id,
                "label": "Headline",
            },
            actor="main",
            fact_exists=lambda fact_id: fact_id in self.store.fact_ids(),
        )
        targets = self.store.sync_active_campaign_targets(
            campaign_id=self.campaign_id
        )
        self.assertEqual(targets, [fact.fact_id])
        self.assertEqual(self.store.targets(), [fact.fact_id])
        self.campaigns.target_archive(
            self.campaign_id,
            target_id,
            reason="superseded",
            actor="main",
        )
        self.store.sync_active_campaign_targets(
            campaign_id=self.campaign_id
        )
        self.assertEqual(self.store.targets(), [])

    def test_set_targets_is_denied_in_v4_outside_campaign_sync(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "active-campaign derived projection",
        ):
            self.store.set_targets([])

    def test_active_campaign_projection_mismatch_fails_audit(self) -> None:
        fact = self._manual_fact("Campaign projection fact.")
        self.store._write_json_once(
            self.store.imports_dir / "projection-fixture.json",
            {
                "project_id": self.store.project_id(),
                "facts": [fact.fact_id],
            },
        )
        self.campaigns.target_add(
            self.campaign_id,
            {
                "role": "headline_proof",
                "subject_kind": "fact",
                "subject_id": fact.fact_id,
                "label": "Projection target",
            },
            actor="main",
            fact_exists=lambda fact_id: fact_id in self.store.fact_ids(),
        )
        self.store.sync_active_campaign_targets(
            campaign_id=self.campaign_id
        )
        self.store._write_targets_projection([])
        report = self.store.audit()
        self.assertFalse(report.current_ok)
        self.assertTrue(
            any(
                "does not equal the active campaign" in item
                for item in report.workflow_errors
            ),
            report.errors,
        )

    def test_campaign_rejects_nonadmitted_fact_target(self) -> None:
        with self.assertRaisesRegex(ValueError, "not an active admitted fact"):
            self.campaigns.target_add(
                self.campaign_id,
                {
                    "role": "headline_proof",
                    "subject_kind": "fact",
                    "subject_id": "1" * 16,
                    "label": "Not admitted",
                },
                actor="main",
                fact_exists=lambda _fact_id: False,
            )

    def test_campaign_create_rejects_nonadmitted_target_without_writing(
        self,
    ) -> None:
        payload = self._campaign_payload("nonadmitted-create")
        payload["targets"] = [
            {
                "role": "headline_proof",
                "subject_kind": "fact",
                "subject_id": "1" * 16,
                "label": "Not admitted",
            }
        ]
        before = self._tree_inventory(self.campaigns.root)
        with self.assertRaisesRegex(
            ValueError,
            "not an active admitted fact",
        ):
            self.campaigns.create(
                payload,
                actor="operator",
                fact_exists=lambda _fact_id: False,
            )
        self.assertEqual(
            before,
            self._tree_inventory(self.campaigns.root),
        )

    def test_campaign_create_requires_predicate_for_proof_target(
        self,
    ) -> None:
        payload = self._campaign_payload("missing-predicate")
        payload["targets"] = [
            {
                "role": "supporting_proof",
                "subject_kind": "fact",
                "subject_id": "2" * 16,
                "label": "No predicate",
            }
        ]
        before = self._tree_inventory(self.campaigns.root)
        with self.assertRaisesRegex(
            ValueError,
            "require.*active admitted-fact predicate",
        ):
            self.campaigns.create(payload, actor="operator")
        self.assertEqual(
            before,
            self._tree_inventory(self.campaigns.root),
        )

    def test_campaign_create_validates_all_targets_before_writing(
        self,
    ) -> None:
        admitted = self._manual_fact("Admitted initial target.")
        payload = self._campaign_payload("second-invalid")
        payload["targets"] = [
            {
                "role": "headline_proof",
                "subject_kind": "fact",
                "subject_id": admitted.fact_id,
                "label": "Valid first target",
            },
            {
                "role": "supporting_proof",
                "subject_kind": "fact",
                "subject_id": "3" * 16,
                "label": "Invalid second target",
            },
        ]
        admitted_ids = set(self.store.fact_ids())
        before = self._tree_inventory(self.campaigns.root)
        with self.assertRaisesRegex(
            ValueError,
            "not an active admitted fact",
        ):
            self.campaigns.create(
                payload,
                actor="operator",
                fact_exists=admitted_ids.__contains__,
            )
        self.assertEqual(
            before,
            self._tree_inventory(self.campaigns.root),
        )

    def test_campaign_create_publishes_all_initial_targets_together(
        self,
    ) -> None:
        headline = self._manual_fact("Initial headline fact.")
        supporting = self._manual_fact("Initial supporting fact.")
        payload = self._campaign_payload("multiple-targets")
        payload["targets"] = [
            {
                "role": "headline_proof",
                "subject_kind": "fact",
                "subject_id": headline.fact_id,
                "label": "Initial headline",
            },
            {
                "role": "supporting_proof",
                "subject_kind": "fact",
                "subject_id": supporting.fact_id,
                "label": "Initial supporting",
            },
        ]
        admitted_ids = set(self.store.fact_ids())
        campaign_id = self.campaigns.create(
            payload,
            actor=" operator ",
            fact_exists=admitted_ids.__contains__,
        )
        status = self.campaigns.status(campaign_id)
        self.assertEqual(status["event_count"], 3)
        self.assertEqual(
            {
                target["subject_id"]
                for target in status["targets"].values()
            },
            {headline.fact_id, supporting.fact_id},
        )
        events = self.campaigns._read_jsonl(
            self.campaigns._events_path(campaign_id)
        )
        self.assertEqual(
            [event["event"] for event in events],
            ["created", "target_added", "target_added"],
        )
        self.assertTrue(
            all(event["actor"] == "operator" for event in events)
        )

    def test_campaign_create_rejects_duplicate_initial_targets_before_write(
        self,
    ) -> None:
        fact = self._manual_fact("Duplicate initial target.")
        target = {
            "role": "headline_proof",
            "subject_kind": "fact",
            "subject_id": fact.fact_id,
            "label": "Duplicate",
        }
        payload = self._campaign_payload("duplicate-target")
        payload["targets"] = [target, dict(target)]
        admitted_ids = set(self.store.fact_ids())
        before = self._tree_inventory(self.campaigns.root)
        with self.assertRaisesRegex(ValueError, "must be unique"):
            self.campaigns.create(
                payload,
                actor="operator",
                fact_exists=admitted_ids.__contains__,
            )
        self.assertEqual(
            before,
            self._tree_inventory(self.campaigns.root),
        )

    def test_campaign_create_collision_is_fail_closed(self) -> None:
        payload = self._campaign_payload("collision")
        timestamp = 123456789
        count_after_collision = (
            len(list(self.campaigns.root.glob("campaign-*"))) + 1
        )
        campaign_id = "campaign-" + sha256_json(
            [payload, timestamp, count_after_collision]
        )[:12]
        collision = self.campaigns.root / campaign_id
        collision.mkdir()
        (collision / "sentinel").write_text(
            "existing campaign namespace\n",
            encoding="utf-8",
        )
        before = self._tree_inventory(self.campaigns.root)
        with patch(
            "mathgraph.campaigns.time.time_ns",
            return_value=timestamp,
        ):
            with self.assertRaisesRegex(ValueError, "campaign id collision"):
                self.campaigns.create(payload, actor="operator")
        self.assertEqual(
            before,
            self._tree_inventory(self.campaigns.root),
        )

    def test_campaign_create_publication_failure_cleans_staging(self) -> None:
        payload = self._campaign_payload("publish-failure")
        before = self._tree_inventory(self.campaigns.root)
        with patch(
            "mathgraph.campaigns.os.rename",
            side_effect=OSError("publication failed"),
        ):
            with self.assertRaisesRegex(OSError, "publication failed"):
                self.campaigns.create(payload, actor="operator")
        self.assertEqual(
            before,
            self._tree_inventory(self.campaigns.root),
        )

    def test_cli_campaign_create_enforces_admitted_fact_gate(self) -> None:
        payload = self._campaign_payload("cli-nonadmitted")
        payload["targets"] = [
            {
                "role": "headline_proof",
                "subject_kind": "fact",
                "subject_id": "4" * 16,
                "label": "CLI must reject",
            }
        ]
        input_path = self.root / "cli-campaign-create.json"
        input_path.write_text(
            json.dumps(payload),
            encoding="utf-8",
        )
        before = self._tree_inventory(self.campaigns.root)
        stderr = StringIO()
        with redirect_stderr(stderr):
            status = cli_main(
                [
                    "--root",
                    str(self.root),
                    "--role",
                    "operator",
                    "campaign-create",
                    "--input",
                    str(input_path),
                    "--actor",
                    "operator",
                ]
            )
        self.assertEqual(status, 2)
        self.assertIn(
            "not an active admitted fact",
            stderr.getvalue(),
        )
        self.assertEqual(
            before,
            self._tree_inventory(self.campaigns.root),
        )

    def test_campaign_separates_communication_targets(self) -> None:
        self.campaigns.target_add(
            self.campaign_id,
            {
                "role": "communication",
                "subject_kind": "report",
                "subject_id": "reports/result.md",
                "label": "Advisor report",
            },
            actor="main",
            fact_exists=lambda _fact_id: False,
        )
        self.assertEqual(self.campaigns.derived_targets(), [])

    def test_campaign_separates_headline_supporting_communication_and_archived_targets(self) -> None:
        headline = self._manual_fact("Headline fact.")
        supporting = self._manual_fact("Supporting fact.")
        self.campaigns.target_add(
            self.campaign_id,
            {
                "role": "headline_proof",
                "subject_kind": "fact",
                "subject_id": headline.fact_id,
                "label": "Headline",
            },
            actor="main",
            fact_exists=lambda fact_id: fact_id in self.store.fact_ids(),
        )
        supporting_target = self.campaigns.target_add(
            self.campaign_id,
            {
                "role": "supporting_proof",
                "subject_kind": "fact",
                "subject_id": supporting.fact_id,
                "label": "Supporting",
            },
            actor="main",
            fact_exists=lambda fact_id: fact_id in self.store.fact_ids(),
        )
        self.campaigns.target_add(
            self.campaign_id,
            {
                "role": "communication",
                "subject_kind": "report",
                "subject_id": "reports/advisor.md",
                "label": "Communication",
            },
            actor="main",
            fact_exists=lambda _fact_id: False,
        )
        self.campaigns.target_archive(
            self.campaign_id,
            supporting_target,
            reason="superseded",
            actor="main",
        )
        self.assertEqual(
            self.campaigns.derived_targets(),
            [headline.fact_id],
        )

    def test_communication_target_never_enters_targets_txt(self) -> None:
        self.campaigns.target_add(
            self.campaign_id,
            {
                "role": "communication",
                "subject_kind": "report",
                "subject_id": "reports/communication.md",
                "label": "Communication only",
            },
            actor="main",
            fact_exists=lambda _fact_id: False,
        )
        self.store.sync_active_campaign_targets(
            campaign_id=self.campaign_id
        )
        self.assertEqual(self.store.targets(), [])
        self.assertNotIn(
            "reports/communication.md",
            self.store.targets_path.read_text(encoding="utf-8"),
        )

    def test_memory_stop_condition_is_copied_to_task_card(self) -> None:
        stop = "Stop after an admitted counterexample."
        memory_id = self.store.memory_add(
            {
                "kind": "direction",
                "claim": "A bounded task.",
                "stop_conditions": [stop],
                "suggested_actions": ["prove"],
            },
            actor="main",
        )
        planned = create_round(
            self.store,
            workers=1,
            memory_ids=[memory_id],
        )
        card = json.loads(
            Path(planned["assignments"][0]["task_card_path"]).read_text()
        )
        self.assertEqual(card["stop_conditions"], [stop])

    def test_actionable_frontier_uses_v4_score_formula(self) -> None:
        payload = {
            "priority": 0.8,
            "novelty": 0.2,
            "testability": 0.9,
            "risk": 0.4,
            "target_relevance": 1.0,
            "decisiveness": 0.7,
            "information_gain": 0.6,
            "estimated_cost": 0.3,
        }
        expected = actionable_score(payload, readiness=1.0)
        memory_id = self.store.memory_add(
            {
                "kind": "direction",
                "claim": "Score fixture.",
                **payload,
            },
            actor="main",
        )
        entry = next(
            item
            for item in self.store.frontier(limit=20)
            if item["id"] == memory_id
        )
        self.assertEqual(entry["score"], expected)

    def test_actionable_frontier_collapses_repair_lineage(self) -> None:
        root_id = self.store.memory_add(
            {"kind": "conjecture", "claim": "Overstrong root."},
            actor="main",
        )
        child_id = self.store.memory_add(
            {
                "kind": "direction",
                "claim": "Minimal repair leaf.",
                "repair_of_memory_id": root_id,
            },
            actor="main",
        )
        visible = {item["id"] for item in self.store.frontier(limit=50)}
        self.assertIn(child_id, visible)
        self.assertNotIn(root_id, visible)
        history = {
            item["id"]
            for item in self.store.frontier(
                limit=50,
                include_history=True,
            )
        }
        self.assertIn(root_id, history)
        self.assertIn(child_id, history)

    def test_worker_cannot_set_killed_by_fact(self) -> None:
        fact = self._manual_fact("A killing fact.")
        with self.assertRaisesRegex(ValueError, "main or operator"):
            self.store.memory_add(
                {
                    "kind": "direction",
                    "claim": "Worker tries to close this direction.",
                    "killed_by_fact": fact.fact_id,
                },
                actor="worker",
            )

    def test_killed_direction_is_hidden_but_visible_in_history(self) -> None:
        fact = self._manual_fact("A decisive fact.")
        memory_id = self.store.memory_add(
            {
                "kind": "direction",
                "claim": "A direction closed by admitted evidence.",
                "killed_by_fact": fact.fact_id,
            },
            actor="main",
        )
        visible = {item["id"] for item in self.store.frontier(limit=50)}
        history = {
            item["id"]
            for item in self.store.frontier(
                limit=50,
                include_history=True,
            )
        }
        self.assertNotIn(memory_id, visible)
        self.assertIn(memory_id, history)

    def test_repair_task_uses_ids_not_full_claim_duplication(self) -> None:
        original_text = "UNIQUE ORIGINAL CLAIM BYTES 314159"
        challenge_text = "UNIQUE CHALLENGE BYTES 271828"
        original_id = self.store.memory_add(
            {
                "kind": "conjecture",
                "status": "challenged",
                "claim": original_text,
                "obligations": [
                    {
                        "id": "O1",
                        "kind": "domain",
                        "statement": "Check the domain.",
                        "required_evidence": ["proof_anchor"],
                    }
                ],
            },
            actor="main",
        )
        trigger_id = self.store.memory_add(
            {
                "kind": "counterexample",
                "status": "challenged",
                "claim": challenge_text,
                "parent_memory_id": original_id,
                "failed_obligation_ids": ["O1"],
            },
            actor="main",
        )
        repaired = create_repair_round(
            self.store,
            original_id,
            trigger_memory_id=trigger_id,
        )
        latest = self.store.memory_latest()
        for repair_id in repaired["repair_memory_ids"]:
            entry = latest[repair_id]
            self.assertEqual(entry["repair_of_memory_id"], original_id)
            self.assertEqual(entry["trigger_memory_id"], trigger_id)
            self.assertNotIn(original_text, entry["claim"])
            self.assertNotIn(challenge_text, entry["claim"])
            self.assertIn(
                entry["repair_mode"],
                {"minimal", "strongest_defensible"},
            )
        context_node = self.store.blackboard().show(
            repaired["repair_context_node_id"]
        )
        self.assertEqual(
            context_node["payload"]["original_claim"],
            original_text,
        )
        self.assertEqual(
            context_node["payload"]["challenge"],
            challenge_text,
        )
        snapshot_nodes, _ = self.store.blackboard().snapshot_objects(
            repaired["round"]["blackboard_snapshot_id"]
        )
        self.assertIn(repaired["repair_context_node_id"], snapshot_nodes)

    def test_blackboard_node_is_not_actionable_until_promoted(self) -> None:
        board = self.store.blackboard()
        space = next(
            node_id
            for node_id, node in board.nodes().items()
            if node["node_type"] == "space"
        )
        node = make_node(
            node_type="conjecture",
            logical_key="candidate",
            payload={"statement": "Candidate"},
            created_by_assignment_id="main",
        )
        board.add_node_with_placements(
            node=node,
            space_ids=[space],
            actor="main",
        )
        self.assertFalse(
            any(
                entry.get("origin_blackboard_node_id") == node["node_id"]
                for entry in self.store.frontier(limit=50)
            )
        )
        query = {
            "seed_node_ids": [node["node_id"]],
            "direction": "both",
            "max_hops": 1,
            "edge_type_allowlist": ["*"],
            "node_type_allowlist": ["*"],
            "node_budget": 20,
            "edge_budget": 20,
        }
        snapshot = board.snapshot(query=query, actor="main")
        metrics = {
            "priority": 0.7,
            "novelty": 0.5,
            "testability": 0.8,
            "risk": 0.4,
            "target_relevance": 0.9,
            "decisiveness": 0.8,
            "information_gain": 0.7,
            "estimated_cost": 0.2,
        }
        memory_id = self.campaigns.promote_blackboard_node(
            node["node_id"],
            {
                "snapshot_id": snapshot["snapshot_id"],
                "campaign_id": self.campaign_id,
                "memory_kind": "conjecture",
                "claim": "Promoted candidate.",
                "rationale": "It may settle the target.",
                "mode_suggestions": ["refute"],
                "metrics": metrics,
                "blackboard_query": query,
            },
            actor="main",
            memory_add=lambda payload, actor: self.store.memory_add(
                payload,
                actor=actor,
            ),
        )
        promoted = self.store.memory_latest()[memory_id]
        self.assertEqual(
            promoted["origin_blackboard_node_id"], node["node_id"]
        )
        self.assertEqual(
            promoted["origin_blackboard_snapshot_id"],
            snapshot["snapshot_id"],
        )

    def test_blackboard_promotion_binds_node_snapshot_and_query_hashes(self) -> None:
        node, snapshot, query, memory_id = self._promote_fixture()
        promoted = self.store.memory_latest()[memory_id]
        expected_node_hash = hashlib.sha256(
            json.dumps(
                node,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        self.assertEqual(
            promoted["origin_blackboard_node_sha256"],
            expected_node_hash,
        )
        self.assertEqual(
            promoted["origin_blackboard_snapshot_id"],
            snapshot["snapshot_id"],
        )
        self.assertEqual(
            promoted["blackboard_query_sha256"],
            sha256_json(query),
        )

    def test_plan_round_snapshot_is_seeded_from_promoted_graph_node(self) -> None:
        node, _, query, memory_id = self._promote_fixture()
        planned = create_round(
            self.store,
            workers=1,
            memory_ids=[memory_id],
        )
        manifest = self.store.blackboard().snapshot_manifest(
            planned["blackboard_snapshot_id"]
        )
        self.assertIn(node["node_id"], manifest["seed_node_ids"])
        self.assertEqual(manifest["query"], query)

    def test_opaque_graph_type_never_receives_automatic_metrics(self) -> None:
        board = self.store.blackboard()
        board.register_type(
            kind="node",
            definition={
                "name": "x-tests:opaque-candidate",
                "type_version": 1,
                "logical_key_policy": "ignored",
                "automation_semantics": "opaque",
            },
            actor="operator",
        )
        space = next(
            node_id
            for node_id, value in board.nodes().items()
            if value["node_type"] == "space"
        )
        node = make_node(
            node_type="x-tests:opaque-candidate",
            logical_key="opaque",
            payload={"statement": "Opaque candidate."},
            created_by_assignment_id="main",
        )
        board.add_node_with_placements(
            node=node,
            space_ids=[space],
            actor="main",
        )
        self.assertFalse(
            any(
                item.get("origin_blackboard_node_id") == node["node_id"]
                for item in self.store.frontier(limit=50)
            )
        )
        query = {
            "seed_node_ids": [node["node_id"]],
            "direction": "both",
            "max_hops": 1,
            "edge_type_allowlist": ["*"],
            "node_type_allowlist": ["*"],
            "node_budget": 20,
            "edge_budget": 20,
        }
        snapshot = board.snapshot(query=query, actor="main")
        with self.assertRaisesRegex(ValueError, "exactly one"):
            self.campaigns.promote_blackboard_node(
                node["node_id"],
                {
                    "snapshot_id": snapshot["snapshot_id"],
                    "campaign_id": self.campaign_id,
                    "memory_kind": "direction",
                    "claim": "Opaque manual candidate.",
                    "rationale": "No automatic score is allowed.",
                    "mode_suggestions": ["prove"],
                    "blackboard_query": query,
                },
                actor="main",
                memory_add=lambda payload, actor: self.store.memory_add(
                    payload,
                    actor=actor,
                ),
            )

    def test_blackboard_audit_detects_hash_and_index_errors(self) -> None:
        board = self.store.blackboard()
        space = next(
            node_id
            for node_id, node in board.nodes().items()
            if node["node_type"] == "space"
        )
        node = make_node(
            node_type="note",
            logical_key="tamper",
            payload={"text": "original"},
            created_by_assignment_id="main",
        )
        board.add_node_with_placements(
            node=node,
            space_ids=[space],
            actor="main",
        )
        board.reindex(apply=True, actor="main")
        path = board.nodes_dir / f"{node['node_id']}.json"
        payload = json.loads(path.read_text())
        payload["payload"]["text"] = "tampered"
        path.write_text(json.dumps(payload))
        audit = self.store.audit()
        self.assertFalse(audit.current_ok)
        self.assertTrue(audit.blackboard_graph_errors)

    def test_blackboard_audit_detects_hash_endpoint_cycle_and_capability_errors(self) -> None:
        board = self.store.blackboard()
        space = next(
            node_id
            for node_id, node in board.nodes().items()
            if node["node_type"] == "space"
        )
        left = make_node(
            node_type="note",
            logical_key="audit-left",
            payload={"text": "left"},
            created_by_assignment_id="main",
        )
        right = make_node(
            node_type="note",
            logical_key="audit-right",
            payload={"text": "right"},
            created_by_assignment_id="main",
        )
        for node in (left, right):
            board.add_node_with_placements(
                node=node,
                space_ids=[space],
                actor="main",
            )
        memory_id = self.store.memory_add(
            {"kind": "direction", "claim": "Capability fixture."},
            actor="main",
        )
        planned = create_round(
            self.store,
            workers=1,
            memory_ids=[memory_id],
        )
        card = json.loads(
            Path(planned["assignments"][0]["task_card_path"]).read_text()
        )
        transaction = board.merge_delta(
            delta={
                "base_snapshot_id": card["blackboard_view"]["snapshot_id"],
                "add_nodes": [],
                "add_edges": [],
            },
            task_card=card,
            return_sha256="6" * 64,
        )
        forged_semantic = {
            key: transaction[key]
            for key in (
                "schema_version",
                "policy_revision",
                "kind",
                "actor",
                "assignment_id",
                "base_snapshot_id",
                "return_sha256",
                "node_ids",
                "edge_ids",
                "capability",
            )
        }
        forged_semantic["capability"] = {
            **forged_semantic["capability"],
            "write_space_ids": ["bbn-" + "f" * 64],
        }
        forged_id = sha256_json(forged_semantic)
        board._write_json_once(
            board.transactions_dir / f"{forged_id}.json",
            {**forged_semantic, "transaction_id": forged_id},
        )

        # Corrupt the graph only after the legitimate task snapshot and the
        # capability fixture have been sealed.  Otherwise planning itself
        # correctly fails closed before this audit can exercise all classes.
        dangling = make_edge(
            edge_type="motivates",
            source_node_id=left["node_id"],
            target_node_id="bbn-" + "0" * 64,
            payload={},
            created_by_assignment_id="main",
        )
        board._stage_and_commit(
            nodes=[],
            edges=[dangling],
            kind="audit-fixture",
            actor="main",
        )
        cycle_edges = [
            make_edge(
                edge_type="derived_from",
                source_node_id=left["node_id"],
                target_node_id=right["node_id"],
                payload={"direction": "forward"},
                created_by_assignment_id="main",
            ),
            make_edge(
                edge_type="derived_from",
                source_node_id=right["node_id"],
                target_node_id=left["node_id"],
                payload={"direction": "backward"},
                created_by_assignment_id="main",
            ),
        ]
        board._stage_and_commit(
            nodes=[],
            edges=cycle_edges,
            kind="audit-fixture",
            actor="main",
        )
        errors = board.audit()["errors"]
        self.assertTrue(any("dangling endpoint" in item for item in errors))
        self.assertTrue(any("cycle" in item for item in errors))
        self.assertTrue(any("capability" in item for item in errors))

        tamper_path = board.nodes_dir / f"{left['node_id']}.json"
        tampered = json.loads(tamper_path.read_text())
        tampered["payload"]["text"] = "tampered"
        tamper_path.write_text(json.dumps(tampered), encoding="utf-8")
        self.assertFalse(board.audit()["ok"])

    def test_upgrade_workflow_dry_run_is_read_only_and_apply_preserves_legacy_bytes(self) -> None:
        legacy_root = self.root / "legacy"
        legacy = MathGraphStore._for_legacy_workflow_fixture(legacy_root)
        legacy.initialize(project_id="legacy", title="Legacy")
        before = legacy._legacy_immutable_inventory()
        project_before = legacy.project_path.read_bytes()
        planned = legacy.upgrade_workflow(
            to_version=4,
            dry_run=True,
        )
        self.assertEqual(planned["status"], "planned")
        self.assertEqual(before, legacy._legacy_immutable_inventory())
        self.assertEqual(project_before, legacy.project_path.read_bytes())
        applied = legacy.upgrade_workflow(
            to_version=4,
            dry_run=False,
            actor="operator",
        )
        self.assertEqual(applied["status"], "upgraded")
        self.assertEqual(before, legacy._legacy_immutable_inventory())
        report = legacy.audit()
        self.assertTrue(report.current_ok)
        self.assertTrue(report.history_clean)

    def test_upgrade_workflow_dry_run_is_read_only(self) -> None:
        legacy = MathGraphStore._for_legacy_workflow_fixture(
            self.root / "dry-run-legacy"
        )
        legacy.initialize(project_id="legacy-dry", title="Legacy dry")
        before = legacy._legacy_immutable_inventory()
        project_before = legacy.project_path.read_bytes()
        result = legacy.upgrade_workflow(to_version=4, dry_run=True)
        self.assertEqual(result["status"], "planned")
        self.assertEqual(before, legacy._legacy_immutable_inventory())
        self.assertEqual(project_before, legacy.project_path.read_bytes())

    def test_upgrade_workflow_does_not_rewrite_legacy_bytes(self) -> None:
        legacy = MathGraphStore._for_legacy_workflow_fixture(
            self.root / "apply-legacy"
        )
        legacy.initialize(project_id="legacy-apply", title="Legacy apply")
        fact = Fact(
            problem_id="legacy-apply",
            author="legacy",
            predecessors=[],
            statement="Legacy immutable statement.",
            proof="Legacy immutable proof.",
        )
        fact_path = legacy.facts_dir / f"{fact.fact_id}.md"
        fact_path.write_text(serialize_fact(fact), encoding="utf-8")
        before = fact_path.read_bytes()
        legacy.upgrade_workflow(
            to_version=4,
            dry_run=False,
            actor="operator",
        )
        self.assertEqual(before, fact_path.read_bytes())

    def test_upgrade_rejects_preexisting_reserved_v4_roots(self) -> None:
        legacy = MathGraphStore._for_legacy_workflow_fixture(
            self.root / "reserved-root-collision"
        )
        legacy.initialize(
            project_id="reserved-root-collision",
            title="Reserved root collision",
        )
        collision = legacy.root / "campaigns" / "legacy-note.txt"
        collision.parent.mkdir(parents=True, exist_ok=True)
        collision.write_text("legacy bytes\n", encoding="utf-8")
        before = project_tree_snapshot(legacy.root)
        with self.assertRaisesRegex(
            ValueError,
            "nonempty V4-reserved paths: campaigns",
        ):
            legacy.upgrade_workflow(to_version=4, dry_run=True)
        self.assertEqual(before, project_tree_snapshot(legacy.root))

    def test_cli_low_level_upgrade_apply_requires_copy_confirmation(
        self,
    ) -> None:
        legacy = MathGraphStore._for_legacy_workflow_fixture(
            self.root / "cli-low-level-upgrade"
        )
        legacy.initialize(
            project_id="cli-low-level-upgrade",
            title="CLI low-level upgrade",
        )
        stderr = StringIO()
        with redirect_stderr(stderr):
            status = cli_main(
                [
                    "--root",
                    str(legacy.root),
                    "--role",
                    "operator",
                    "upgrade-workflow",
                    "--to",
                    "4",
                    "--actor",
                    "operator",
                ]
            )
        self.assertEqual(status, 2)
        self.assertIn("--confirm-isolated-copy", stderr.getvalue())
        self.assertEqual(legacy.workflow_evidence_version(), 3)

    def test_cli_upgrade_project_copy_dry_run_and_apply(self) -> None:
        stable = MathGraphStore._for_legacy_workflow_fixture(
            self.root / "cli-stable-source"
        )
        stable.initialize(
            project_id="cli-stable-source",
            title="CLI stable source",
        )
        destination = self.root / "cli-chalk-copy"
        stdout = StringIO()
        with redirect_stdout(stdout):
            dry_status = cli_main(
                [
                    "--root",
                    str(destination),
                    "--role",
                    "operator",
                    "upgrade-project-copy",
                    "--source",
                    str(stable.root),
                    "--dry-run",
                ]
            )
        self.assertEqual(dry_status, 0)
        self.assertFalse(destination.exists())
        self.assertEqual(json.loads(stdout.getvalue())["status"], "planned")

        stdout = StringIO()
        with redirect_stdout(stdout):
            apply_status = cli_main(
                [
                    "--root",
                    str(destination),
                    "--role",
                    "operator",
                    "upgrade-project-copy",
                    "--source",
                    str(stable.root),
                    "--actor",
                    "operator",
                ]
            )
        self.assertEqual(apply_status, 0)
        self.assertEqual(
            json.loads(stdout.getvalue())["status"],
            "upgraded_copy",
        )
        self.assertTrue(MathGraphStore(destination).audit().current_ok)

    def test_migrated_v3_append_only_memory_can_continue_without_rewriting_prefix(
        self,
    ) -> None:
        legacy = MathGraphStore._for_legacy_workflow_fixture(
            self.root / "append-after-migration"
        )
        legacy.initialize(
            project_id="append-after-migration",
            title="Append after migration",
        )
        legacy.memory_add(
            {
                "kind": "direction",
                "claim": "Historical V3 direction.",
            },
            actor="legacy",
        )
        memory_path = legacy.memory_dir / "global.jsonl"
        legacy_prefix = memory_path.read_bytes()
        applied = legacy.upgrade_workflow(
            to_version=4,
            dry_run=False,
            actor="operator",
        )
        receipt = legacy._read_json(
            legacy.migrations_dir
            / f"{applied['migration_receipt_id']}.json"
        )
        binding = receipt["legacy_append_only_prefixes"][
            "memory/global.jsonl"
        ]
        self.assertEqual(binding["byte_length"], len(legacy_prefix))
        self.assertEqual(
            binding["sha256"],
            hashlib.sha256(legacy_prefix).hexdigest(),
        )
        legacy.reasoning_modes().initialize(
            reasoning_mode="auto",
            actor="operator",
            reason="Activate the migrated copy before appending V4 memory.",
            source_kind="legacy_chalk_v4_upgrade",
        )
        legacy.memory_add(
            {
                "kind": "guidance",
                "claim": "New V4 direction after migration.",
            },
            actor="main",
        )
        anchor_path = next(legacy.append_anchors_dir.glob("*.json"))
        self.assertEqual(
            legacy._read_json(anchor_path)["writer_engine"],
            "operate-mathgraph-unified",
        )
        self.assertTrue(memory_path.read_bytes().startswith(legacy_prefix))
        report = legacy.audit()
        self.assertTrue(report.current_ok, report.errors)

    def test_historical_chalk_append_anchor_identity_remains_readable(self) -> None:
        legacy = MathGraphStore._for_legacy_workflow_fixture(
            self.root / "historical-anchor"
        )
        legacy.initialize(project_id="historical-anchor", title="Historical anchor")
        legacy.memory_add(
            {"kind": "direction", "claim": "Historical prefix."},
            actor="legacy",
        )
        legacy.upgrade_workflow(to_version=4, dry_run=False, actor="operator")
        legacy.reasoning_modes().initialize(
            reasoning_mode="auto",
            actor="operator",
            reason="Activate the migrated copy before appending V4 memory.",
            source_kind="legacy_chalk_v4_upgrade",
        )
        legacy.memory_add(
            {"kind": "guidance", "claim": "Anchored suffix."},
            actor="main",
        )
        current_path = next(legacy.append_anchors_dir.glob("*.json"))
        historical = legacy._read_json(current_path)
        historical["writer_engine"] = "mathgraph-chalk-version"
        semantic = {
            key: historical[key]
            for key in (
                "schema_version",
                "policy_revision",
                "writer_engine",
                "log_path",
                "event_id",
                "event_sha256",
                "event",
            )
        }
        historical["anchor_id"] = sha256_json(semantic)
        historical_path = (
            legacy.append_anchors_dir / f"{historical['anchor_id']}.json"
        )
        legacy._write_json_once(historical_path, historical)
        current_path.unlink()
        self.assertTrue(legacy.audit().current_ok)

    def test_migrated_v3_append_only_prefix_tamper_fails(self) -> None:
        legacy = MathGraphStore._for_legacy_workflow_fixture(
            self.root / "tamper-prefix"
        )
        legacy.initialize(
            project_id="tamper-prefix",
            title="Tamper prefix",
        )
        legacy.memory_add(
            {
                "kind": "direction",
                "claim": "Protected historical direction.",
            },
            actor="legacy",
        )
        legacy.upgrade_workflow(
            to_version=4,
            dry_run=False,
            actor="operator",
        )
        legacy.reasoning_modes().initialize(
            reasoning_mode="auto",
            actor="operator",
            reason="Activate the migrated copy before appending V4 memory.",
            source_kind="legacy_chalk_v4_upgrade",
        )
        legacy.memory_add(
            {
                "kind": "guidance",
                "claim": "Permitted appended direction.",
            },
            actor="main",
        )
        memory_path = legacy.memory_dir / "global.jsonl"
        tampered = memory_path.read_bytes().replace(
            b'"actor": "legacy"',
            b'"actor": "tampered"',
            1,
        )
        memory_path.write_bytes(tampered)
        report = legacy.audit()
        self.assertFalse(report.current_ok)
        self.assertTrue(
            any(
                "append-only prefix changed" in item
                for item in report.workflow_errors
            ),
            report.errors,
        )

    def test_migrated_v4_suffix_truncation_fails_audit(self) -> None:
        legacy = MathGraphStore._for_legacy_workflow_fixture(
            self.root / "truncate-v4-suffix"
        )
        legacy.initialize(
            project_id="truncate-v4-suffix",
            title="Truncate V4 suffix",
        )
        legacy.memory_add(
            {
                "kind": "direction",
                "claim": "Historical prefix.",
            },
            actor="legacy",
        )
        memory_path = legacy.memory_dir / "global.jsonl"
        prefix = memory_path.read_bytes()
        legacy.upgrade_workflow(
            to_version=4,
            dry_run=False,
            actor="operator",
        )
        legacy.reasoning_modes().initialize(
            reasoning_mode="auto",
            actor="operator",
            reason="Activate the migrated copy before appending V4 memory.",
            source_kind="legacy_chalk_v4_upgrade",
        )
        legacy.memory_add(
            {
                "kind": "guidance",
                "claim": "Anchored V4 suffix.",
            },
            actor="main",
        )
        self.assertTrue(legacy.audit().current_ok)
        memory_path.write_bytes(prefix)
        report = legacy.audit()
        self.assertFalse(report.current_ok)
        self.assertTrue(
            any(
                "anchor has no visible log event" in item
                for item in report.workflow_errors
            ),
            report.errors,
        )

    def test_wrong_stable_engine_write_is_detected_in_chalk_audit(self) -> None:
        legacy = MathGraphStore._for_legacy_workflow_fixture(
            self.root / "wrong-engine-write"
        )
        legacy.initialize(
            project_id="wrong-engine-write",
            title="Wrong engine write",
        )
        legacy.upgrade_workflow(
            to_version=4,
            dry_run=False,
            actor="operator",
        )
        MathGraphStore._append_jsonl(
            legacy.memory_dir / "global.jsonl",
            {
                "id": "a" * 12,
                "event_id": "b" * 24,
                "kind": "direction",
                "status": "open",
                "claim": "Unanchored legacy-shaped suffix.",
                "dependencies": [],
                "actor": "stable-engine",
                "timestamp": "2026-07-24T00:00:00+00:00",
            },
        )
        report = legacy.audit()
        self.assertFalse(report.current_ok)
        self.assertTrue(
            any(
                "has no Chalk sidecar anchor" in item
                for item in report.workflow_errors
            ),
            report.errors,
        )

    def test_stable_project_copy_upgrade_preserves_source_and_binds_lineage(
        self,
    ) -> None:
        stable = MathGraphStore._for_legacy_workflow_fixture(
            self.root / "stable-source"
        )
        stable.initialize(
            project_id="stable-source",
            title="Stable source",
        )
        stable.memory_add(
            {
                "kind": "direction",
                "claim": "Historical stable direction.",
            },
            actor="stable-main",
        )
        source_before = project_tree_snapshot(stable.root)
        destination = self.root / "chalk-copy"

        planned = upgrade_stable_project_copy(
            source=stable.root,
            destination=destination,
            dry_run=True,
        )
        self.assertEqual(planned["status"], "planned")
        self.assertFalse(destination.exists())
        self.assertEqual(source_before, project_tree_snapshot(stable.root))

        applied = upgrade_stable_project_copy(
            source=stable.root,
            destination=destination,
            actor="operator",
            dry_run=False,
        )
        self.assertEqual(applied["status"], "upgraded_copy")
        self.assertEqual(applied["cutover_status"], "not_performed")
        self.assertTrue(applied["source_unchanged"])
        self.assertEqual(source_before, project_tree_snapshot(stable.root))
        self.assertEqual(stable.workflow_evidence_version(), 3)

        chalk = MathGraphStore(destination)
        self.assertEqual(chalk.workflow_evidence_version(), 4)
        receipt = chalk._read_json(
            chalk.migrations_dir
            / f"{applied['migration_receipt_id']}.json"
        )
        inheritance = receipt["stable_copy_inheritance"]
        self.assertEqual(
            inheritance["source_tree_sha256"],
            source_before["tree_sha256"],
        )
        self.assertEqual(
            inheritance["assurance_policy"],
            "preserve-recorded-legacy-assurance;never-relabel-as-v4",
        )
        chalk.reasoning_modes().initialize(
            reasoning_mode="auto",
            actor="operator",
            reason="Activate the isolated upgraded copy for new work.",
            source_kind="legacy_chalk_v4_upgrade",
        )
        chalk.memory_add(
            {
                "kind": "guidance",
                "claim": "Chalk-only continuation.",
            },
            actor="main",
        )
        self.assertEqual(source_before, project_tree_snapshot(stable.root))
        self.assertTrue(chalk.audit().current_ok)

    def test_migrated_target_projection_can_change_without_rewriting_stable(
        self,
    ) -> None:
        stable = MathGraphStore._for_legacy_workflow_fixture(
            self.root / "stable-target-source"
        )
        stable.initialize(
            project_id="stable-target-source",
            title="Stable target source",
        )
        fact = Fact(
            problem_id=stable.project_id(),
            author="legacy",
            predecessors=[],
            statement="Legacy target fact.",
            proof="Legacy proof.",
        )
        stable.submit(fact, worker="legacy")
        packet = stable.freeze_verification_packet(fact.fact_id)
        review_path = stable.record_review(
            {
                "fact_id": fact.fact_id,
                "submission_sha256": packet["submission_sha256"],
                "packet_sha256": packet["packet_sha256"],
                "verdict": "correct",
                "critical_errors": [],
                "gaps": [],
                "repair_hints": [],
                "reviewer": "fresh-legacy-verifier",
            }
        )
        stable.admit(
            fact.fact_id,
            review_id=review_path.stem,
            gateway="legacy-gateway",
        )
        stable.set_targets([fact.fact_id])
        source_before = project_tree_snapshot(stable.root)
        destination = self.root / "chalk-target-copy"
        applied = upgrade_stable_project_copy(
            source=stable.root,
            destination=destination,
            actor="operator",
            dry_run=False,
        )
        chalk = MathGraphStore(destination)
        chalk.reasoning_modes().initialize(
            reasoning_mode="auto",
            actor="operator",
            reason="Activate the isolated upgraded copy before target changes.",
            source_kind="legacy_chalk_v4_upgrade",
        )
        campaigns = chalk.campaigns()
        campaign_id = applied["legacy_default_campaign_id"]
        status = campaigns.status(campaign_id)
        target_id = next(iter(status["targets"]))
        campaigns.target_archive(
            campaign_id,
            target_id,
            reason="Superseded by a Chalk campaign.",
            actor="main",
        )
        chalk.sync_active_campaign_targets(campaign_id=campaign_id)

        self.assertEqual(chalk.targets(), [])
        self.assertEqual(stable.targets(), [fact.fact_id])
        self.assertEqual(source_before, project_tree_snapshot(stable.root))
        self.assertTrue(chalk.audit().current_ok)

    def test_stable_copy_lineage_tamper_fails_audit(self) -> None:
        stable = MathGraphStore._for_legacy_workflow_fixture(
            self.root / "stable-lineage-source"
        )
        stable.initialize(
            project_id="stable-lineage-source",
            title="Stable lineage source",
        )
        destination = self.root / "chalk-lineage-copy"
        applied = upgrade_stable_project_copy(
            source=stable.root,
            destination=destination,
            actor="operator",
            dry_run=False,
        )
        chalk = MathGraphStore(destination)
        receipt_path = (
            chalk.migrations_dir
            / f"{applied['migration_receipt_id']}.json"
        )
        receipt = chalk._read_json(receipt_path)
        receipt["stable_copy_inheritance"]["source_tree_sha256"] = "0" * 64
        receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        report = chalk.audit()
        self.assertFalse(report.current_ok)
        self.assertTrue(
            any(
                "migration receipt id/hash mismatch" in item
                for item in report.workflow_errors
            ),
            report.errors,
        )

    def test_migrated_legacy_fact_export_keeps_v3_assurance(self) -> None:
        stable = MathGraphStore._for_legacy_workflow_fixture(
            self.root / "legacy-export-source"
        )
        stable.initialize(
            project_id="legacy-export-source",
            title="Legacy export source",
        )
        fact = Fact(
            problem_id=stable.project_id(),
            author="legacy-worker",
            predecessors=[],
            statement="A legacy admitted theorem.",
            proof="Legacy proof.",
        )
        stable.submit(fact, worker="legacy-worker")
        packet = stable.freeze_verification_packet(fact.fact_id)
        review_path = stable.record_review(
            {
                "fact_id": fact.fact_id,
                "submission_sha256": packet["submission_sha256"],
                "packet_sha256": packet["packet_sha256"],
                "verdict": "correct",
                "critical_errors": [],
                "gaps": [],
                "repair_hints": [],
                "reviewer": "fresh-legacy-verifier",
            }
        )
        stable.admit(
            fact.fact_id,
            review_id=review_path.stem,
            gateway="legacy-gateway",
        )
        destination = self.root / "legacy-export-chalk"
        upgrade_stable_project_copy(
            source=stable.root,
            destination=destination,
            actor="operator",
            dry_run=False,
        )
        chalk = MathGraphStore(destination)
        card = chalk.claim_card(fact.fact_id, audience="advisor")
        self.assertEqual(card["admission_evidence_version"], 3)
        self.assertEqual(
            card["assurance_label"],
            "legacy-v3-inherited",
        )
        self.assertTrue(
            any(
                "does not relabel the fact as V4-reviewed" in limitation
                for limitation in card["limitations"]
            )
        )
        self.assertTrue(chalk.audit().current_ok)

    def test_v3_fixture_is_checked_by_v3_validator(self) -> None:
        legacy = MathGraphStore._for_legacy_workflow_fixture(
            self.root / "v3-fixture"
        )
        legacy.initialize(project_id="v3-fixture", title="V3 fixture")
        fact = Fact(
            problem_id="v3-fixture",
            author="legacy",
            predecessors=[],
            statement="A v3 fact.",
            proof="Direct.",
        )
        (legacy.facts_dir / f"{fact.fact_id}.md").write_text(
            serialize_fact(fact),
            encoding="utf-8",
        )
        (legacy.imports_dir / "v3-fixture-import.json").write_text(
            json.dumps(
                {
                    "kind": "v3-fixture-import",
                    "project_id": "v3-fixture",
                    "facts": [fact.fact_id],
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        # A v3 audit must not retroactively interpret additive v4 storage as
        # historical v3 truth.
        (legacy.root / "blackboard").mkdir()
        (legacy.root / "blackboard" / "not-v3-truth.json").write_text(
            "{broken",
            encoding="utf-8",
        )
        report = legacy.audit()
        self.assertTrue(report.current_ok, report.errors)

    def test_default_audit_separates_historical_warnings(self) -> None:
        report = self.store.audit()
        self.assertEqual(report.ok, report.current_ok)
        self.assertTrue(report.history_clean)
        report.historical_workflow_warnings.append("legacy debt")
        self.assertTrue(report.current_ok)
        self.assertFalse(report.history_clean)

    def test_strict_history_fails_on_history_debt(self) -> None:
        report = self.store.audit()
        report.historical_workflow_warnings.append("legacy debt")
        self.assertTrue(report.current_ok)
        self.assertFalse(report.history_clean)
        self.assertFalse(report.current_ok and report.history_clean)


if __name__ == "__main__":
    unittest.main()

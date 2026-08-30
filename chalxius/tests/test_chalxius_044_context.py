from __future__ import annotations

import copy
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from mathgraph.adoption import workload_profile_for_entry
from mathgraph.blackboard import make_edge, make_node
from mathgraph.cli import main as cli_main
from mathgraph.contracts import sha256_bytes, sha256_json
from mathgraph.roles import allowed_commands_for_workflow
from mathgraph.store import MathGraphStore
from mathgraph.v5_lifecycle import (
    V5_CONTEXT_SELECTION_REVISION,
    V5_LEGACY_TASK_CONTEXT_REVISION,
    V5_TASK_CONTEXT_REVISION,
)


class Chalxius044ContextTests(unittest.TestCase):
    @staticmethod
    def _store(root: Path, project_id: str) -> MathGraphStore:
        store = MathGraphStore(root)
        store.initialize(
            project_id=project_id,
            title="Chalxius 0.4.4 context fixture",
            workflow_evidence_version=5,
        )
        return store

    @staticmethod
    def _card(store: MathGraphStore, planned: dict) -> tuple[Path, dict]:
        path = Path(planned["assignments"][0]["task_card_path"])
        return path, store._read_json(path)

    @staticmethod
    def _promoted_research(store: MathGraphStore) -> tuple[str, dict, dict, dict]:
        lifecycle = store.v5_lifecycle()
        board = store.blackboard()
        space_id = next(
            node_id
            for node_id, node in board.current_nodes().items()
            if node["node_type"] == "space"
        )
        node = make_node(
            node_type="conjecture",
            logical_key="v5-l1-promoted-context",
            payload={"statement": "Attack the promoted local conjecture."},
            created_by_assignment_id="host",
        )
        query = {
            "seed_node_ids": [node["node_id"]],
            "direction": "both",
            "max_hops": 2,
            "edge_type_allowlist": ["*"],
            "node_type_allowlist": ["*"],
            "node_budget": 24,
            "edge_budget": 32,
        }
        with store.v5_mutation_lock(command="0.4.4-context-fixture"):
            board.add_node_with_placements(
                node=node,
                space_ids=[space_id],
                actor="host",
            )
            board.reindex(apply=True, actor="host")
            origin_snapshot = board.snapshot(query=query, actor="host")
            campaign_id = store.campaigns().create(
                {
                    "name": "L1 fixture",
                    "objective": "Exercise exact promoted context selection.",
                    "source_claim_ids": [],
                    "targets": [],
                    "constraints": ["No Fact effect."],
                    "stop_conditions": ["The context receipt validates."],
                    "value_definition": "Prefer exact bounded provenance.",
                },
                actor="host",
                fact_exists=lambda _fact_id: False,
            )
            research_id = store.campaigns().promote_blackboard_node(
                node["node_id"],
                {
                    "snapshot_id": origin_snapshot["snapshot_id"],
                    "campaign_id": campaign_id,
                    "memory_kind": "conjecture",
                    "claim": "Refute the promoted local conjecture.",
                    "rationale": "Use the exact promoted Blackboard neighborhood.",
                    "mode_suggestions": ["refute", "prove"],
                    "decision_profile": {
                        "impact": 0.8,
                        "information_value": 0.9,
                        "tractability": 0.8,
                        "burden": 0.2,
                    },
                    "blackboard_query": query,
                },
                actor="host",
                memory_add=lambda payload, actor: lifecycle.add_research(
                    payload,
                    actor=actor,
                )["research_id"],
            )
        return research_id, node, query, origin_snapshot

    def test_background_is_indexed_snapshotted_and_rehydratable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "v5"
            store = self._store(root, "v5-background-index")
            body = (
                "# Project history\n\n"
                "This sentence records an abandoned historical direction.\n\n"
                "## Conventions\n\n"
                + ("Use the exact source before a load-bearing claim.\n" * 260)
            )
            background_path = root / "PROJECT_BACKGROUND.md"
            background_path.write_text(body, encoding="utf-8")
            lifecycle = store.v5_lifecycle()
            current_index = lifecycle.project_background_index()
            assert current_index is not None
            self.assertNotIn("body", current_index)
            self.assertEqual(
                current_index["index"]["coverage_receipt"],
                {
                    "partition": "complete_exact_byte_partition",
                    "covered_byte_count": len(body.encode("utf-8")),
                    "omitted_byte_count": 0,
                    "chunk_count": len(current_index["index"]["chunks"]),
                },
            )
            selected_chunk_id = current_index["index"]["chunks"][0]["chunk_id"]
            research = lifecycle.add_research(
                {"kind": "plan", "claim": "Plan the indexed-context task."},
                actor="host",
            )
            planned = lifecycle.create_round(
                workers=1,
                research_ids=[research["research_id"]],
                background_chunk_ids=[selected_chunk_id],
            )
            card_path, card = self._card(store, planned)
            background = card["mathematical_state"]["project_background"]
            self.assertNotIn("body", background)
            self.assertEqual(
                background["selection_receipt"]["selected_chunk_ids"],
                [selected_chunk_id],
            )
            self.assertEqual(
                card["context_selection"]["revision"],
                V5_CONTEXT_SELECTION_REVISION,
            )
            self.assertEqual(
                card["context_selection"]["precedence"][-1],
                "project_background_index",
            )
            frozen_path = root / background["snapshot_relpath"]
            self.assertEqual(frozen_path.read_text(encoding="utf-8"), body)
            self.assertNotIn(
                "This sentence records an abandoned historical direction.",
                json.dumps(card, ensure_ascii=False),
            )

            background_path.write_text("# Refreshed later\n\nNew history.\n", encoding="utf-8")
            lifecycle.validate_task_card(card, expected_path=card_path)
            reconstructed = "".join(
                lifecycle.project_background_chunk(
                    card=card,
                    chunk_id=entry["chunk_id"],
                )["content"]
                for entry in background["index"]["chunks"]
            )
            self.assertEqual(reconstructed, body)

            original_frozen = frozen_path.read_bytes()
            frozen_path.write_bytes(original_frozen + b"tamper")
            with self.assertRaisesRegex(ValueError, "snapshot drifted"):
                lifecycle.validate_task_card(card, expected_path=card_path)
            with self.assertRaisesRegex(ValueError, "snapshot drifted"):
                lifecycle.project_background_chunk(
                    card=card,
                    chunk_id=selected_chunk_id,
                )
            frozen_path.write_bytes(original_frozen)
            lifecycle.validate_task_card(card, expected_path=card_path)

            rounds_before_rejected_selection = sorted(store.rounds_dir.iterdir())
            with self.assertRaisesRegex(ValueError, "must be unique"):
                lifecycle.create_round(
                    workers=1,
                    research_ids=[research["research_id"]],
                    background_chunk_ids=[selected_chunk_id, selected_chunk_id],
                )
            self.assertEqual(
                sorted(store.rounds_dir.iterdir()),
                rounds_before_rejected_selection,
            )
            with self.assertRaisesRegex(ValueError, "unknown PROJECT_BACKGROUND"):
                lifecycle.create_round(
                    workers=1,
                    research_ids=[research["research_id"]],
                    background_chunk_ids=["bgc-" + "0" * 64],
                )
            self.assertEqual(
                sorted(store.rounds_dir.iterdir()),
                rounds_before_rejected_selection,
            )
            prompt = Path(planned["assignments"][0]["prompt_path"]).read_text(
                encoding="utf-8"
            )
            self.assertIn("After context compaction", prompt)
            self.assertIn("project-background-read", prompt)

    def test_l1_promoted_query_and_l2_mode_hint_are_exact_and_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "v5"
            store = self._store(root, "v5-l1-l2")
            lifecycle = store.v5_lifecycle()
            research_id, node, query, origin_snapshot = self._promoted_research(store)
            planned = lifecycle.create_round(
                workers=1,
                research_ids=[research_id],
            )
            card_path, card = self._card(store, planned)
            selection = card["context_selection"]
            blackboard = selection["blackboard"]
            self.assertEqual(blackboard["source"], "promoted_blackboard_query")
            self.assertEqual(blackboard["query"], query)
            self.assertEqual(
                blackboard["origin_bindings"][0]["origin_blackboard_node_id"],
                node["node_id"],
            )
            self.assertEqual(
                blackboard["origin_bindings"][0]["origin_blackboard_snapshot_id"],
                origin_snapshot["snapshot_id"],
            )
            manifest = store.blackboard().snapshot_manifest(
                blackboard["snapshot_id"]
            )
            self.assertEqual(manifest["query"], query)
            self.assertEqual(card["work_mode"], "refute")
            self.assertEqual(
                selection["mode"]["source"],
                "bounded_research_suggestion",
            )
            self.assertEqual(
                selection["mode"]["effect"],
                "hint_applies_only_when_assurance_equivalent",
            )
            lifecycle.validate_task_card(card, expected_path=card_path)

            tampered = copy.deepcopy(card)
            tampered["context_selection"]["blackboard"]["query"]["max_hops"] = 1
            context_semantic = {
                key: value
                for key, value in tampered["context_selection"].items()
                if key != "context_selection_sha256"
            }
            tampered["context_selection"]["context_selection_sha256"] = (
                sha256_json(context_semantic)
            )
            tampered_semantic = {
                key: value
                for key, value in tampered.items()
                if key != "task_card_semantic_sha256"
            }
            tampered["task_card_semantic_sha256"] = sha256_json(tampered_semantic)
            with self.assertRaisesRegex(ValueError, "context-selection hash mismatch"):
                lifecycle.validate_task_card(tampered)

            ordinary = lifecycle.add_research(
                {"kind": "proof_attempt", "claim": "An unrelated task."},
                actor="host",
            )
            before = sorted(store.rounds_dir.iterdir())
            with self.assertRaisesRegex(ValueError, "one exact V5 task"):
                lifecycle.create_round(
                    workers=2,
                    research_ids=[research_id, ordinary["research_id"]],
                )
            self.assertEqual(sorted(store.rounds_dir.iterdir()), before)

            explicit = lifecycle.create_round(
                workers=1,
                mode="compute",
                research_ids=[research_id],
            )
            _, explicit_card = self._card(store, explicit)
            self.assertEqual(explicit_card["work_mode"], "compute")
            self.assertEqual(
                explicit_card["context_selection"]["mode"]["source"],
                "explicit_user_mode",
            )

            board = store.blackboard()
            space_id = next(
                node_id
                for node_id, current in board.current_nodes().items()
                if current["node_type"] == "space"
            )
            closer = make_node(
                node_type="obstacle",
                logical_key="v5-l1-origin-closed",
                payload={"statement": "Close the promoted exploration node."},
                created_by_assignment_id="host",
            )
            with store.v5_mutation_lock(command="0.4.4-close-promoted-origin"):
                board.add_node_with_placements(
                    node=closer,
                    space_ids=[space_id],
                    actor="host",
                )
                board.add_objects(
                    nodes=[],
                    edges=[
                        make_edge(
                            edge_type="closes",
                            source_node_id=closer["node_id"],
                            target_node_id=node["node_id"],
                            payload={},
                            created_by_assignment_id="host",
                        )
                    ],
                    actor="host",
                )
                board.reindex(apply=True, actor="host")
            lifecycle.validate_task_card(card, expected_path=card_path)
            before_replan = sorted(store.rounds_dir.iterdir())
            with self.assertRaisesRegex(ValueError, "no longer active"):
                lifecycle.create_round(
                    workers=1,
                    research_ids=[research_id],
                )
            self.assertEqual(sorted(store.rounds_dir.iterdir()), before_replan)

    def test_l2_rejects_free_text_as_a_route_and_falls_back_visibly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "v5", "v5-l2-bounded")
            lifecycle = store.v5_lifecycle()
            research = lifecycle.add_research(
                {
                    "kind": "plan",
                    "claim": "Plan without treating prose as a mode.",
                    "suggested_actions": ["prove directly", "literature", "prove"],
                },
                actor="host",
            )
            planned = lifecycle.create_round(
                workers=1,
                research_ids=[research["research_id"]],
            )
            pre_enable_card_path, card = self._card(store, planned)
            mode = card["context_selection"]["mode"]
            self.assertEqual(card["work_mode"], "prove")
            self.assertEqual(mode["accepted_suggestions"], ["literature", "prove"])
            self.assertEqual(mode["eligible_suggestions"], ["prove"])
            self.assertEqual(
                mode["blocked_suggestions"],
                [
                    {
                        "mode": "literature",
                        "reason": "would_change_assurance_contract",
                    }
                ],
            )
            self.assertEqual(mode["rejected_suggestions"], ["prove directly"])

            malformed = lifecycle.add_research(
                {
                    "kind": "plan",
                    "claim": "Ignore a malformed legacy suggestion visibly.",
                    "suggested_actions": {"mode": "compute"},
                },
                actor="host",
            )
            fallback = lifecycle.create_round(
                workers=1,
                research_ids=[malformed["research_id"]],
            )
            _, fallback_card = self._card(store, fallback)
            fallback_mode = fallback_card["context_selection"]["mode"]
            self.assertEqual(fallback_card["work_mode"], "prove")
            self.assertTrue(fallback_mode["malformed_suggestions_ignored"])
            self.assertEqual(fallback_mode["source"], "research_kind_default")

            assurance_blocked = lifecycle.add_research(
                {
                    "kind": "plan",
                    "claim": "Do not let a hint create a computation contract.",
                    "suggested_actions": ["compute"],
                },
                actor="host",
            )
            blocked_round = lifecycle.create_round(
                workers=1,
                research_ids=[assurance_blocked["research_id"]],
            )
            _, blocked_card = self._card(store, blocked_round)
            blocked_mode = blocked_card["context_selection"]["mode"]
            self.assertEqual(blocked_card["work_mode"], "prove")
            self.assertEqual(
                blocked_mode["blocked_suggestions"],
                [
                    {
                        "mode": "compute",
                        "reason": "would_change_assurance_contract",
                    }
                ],
            )

            program_math_profile = workload_profile_for_entry(
                {"kind": "computation", "suggested_actions": ["compute"]}
            )
            program_math_profile["computation"]["stage_count"] = 2
            future_review_blocked = lifecycle.add_research(
                {
                    "kind": "plan",
                    "claim": (
                        "Do not let a refute hint suppress the future "
                        "program-math adverse review."
                    ),
                    "suggested_actions": ["refute"],
                    "workload_profile": program_math_profile,
                },
                actor="host",
            )
            future_review_round = lifecycle.create_round(
                workers=1,
                research_ids=[future_review_blocked["research_id"]],
            )
            _, future_review_card = self._card(store, future_review_round)
            future_review_mode = future_review_card["context_selection"]["mode"]
            self.assertEqual(future_review_card["work_mode"], "refute")
            self.assertEqual(future_review_mode["blocked_suggestions"], [])
            self.assertNotIn("adverse_routing", future_review_card)

            store.adverse_routes().initialize(
                actor="operator",
                reason="Exercise L2 capability-equivalence blocking.",
            )
            lifecycle.validate_task_card(card, expected_path=pre_enable_card_path)
            routing_blocked = lifecycle.add_research(
                {
                    "kind": "plan",
                    "claim": "Do not let a hint add adverse capability.",
                    "suggested_actions": ["refute"],
                },
                actor="host",
            )
            routing_round = lifecycle.create_round(
                workers=1,
                research_ids=[routing_blocked["research_id"]],
            )
            _, routing_card = self._card(store, routing_round)
            routing_mode = routing_card["context_selection"]["mode"]
            self.assertEqual(routing_card["work_mode"], "refute")
            self.assertEqual(routing_mode["blocked_suggestions"], [])
            self.assertNotIn("adverse_routing", routing_card)

    def test_legacy_043_card_remains_valid_without_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "v5"
            store = self._store(root, "v5-legacy-card")
            body = "# Historical background\n\nFrozen 0.4.3 bytes.\n"
            (root / "PROJECT_BACKGROUND.md").write_text(body, encoding="utf-8")
            lifecycle = store.v5_lifecycle()
            research = lifecycle.add_research(
                {"kind": "proof_attempt", "claim": "Preserve the old card."},
                actor="host",
            )
            planned = lifecycle.create_round(
                workers=1,
                research_ids=[research["research_id"]],
            )
            _, current = self._card(store, planned)
            legacy = copy.deepcopy(current)
            legacy["task_context_revision"] = V5_LEGACY_TASK_CONTEXT_REVISION
            legacy.pop("context_selection")
            legacy["mathematical_state"]["authority_snapshot"] = (
                lifecycle._task_authority_snapshot(
                    lifecycle._research_record(research["research_id"]),
                    contract_revision=V5_LEGACY_TASK_CONTEXT_REVISION,
                )
            )
            legacy["mathematical_state"]["project_background"] = {
                "read_policy": "default_if_present",
                "relpath": "PROJECT_BACKGROUND.md",
                "sha256": sha256_bytes(body.encode("utf-8")),
                "body": body,
                "truth_effect": "nontruth_background_only",
                "load_bearing_rule": "return_to_exact_cited_source",
            }
            semantic = {
                key: value
                for key, value in legacy.items()
                if key != "task_card_semantic_sha256"
            }
            legacy["task_card_semantic_sha256"] = sha256_json(semantic)
            lifecycle.validate_task_card(legacy)
            self.assertEqual(legacy["task_context_revision"], "chalxius-v5-task-context-0.4.3-2")

    def test_background_cli_exposes_index_and_exact_frozen_chunk(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "v5"
            store = self._store(root, "v5-background-cli")
            (root / "PROJECT_BACKGROUND.md").write_text(
                "# Background\n\nExact CLI chunk.\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            with redirect_stdout(stdout), redirect_stderr(StringIO()):
                code = cli_main(
                    [
                        "--root",
                        str(root),
                        "--role",
                        "main",
                        "project-background-index",
                    ]
                )
            self.assertEqual(code, 0)
            index = json.loads(stdout.getvalue())
            chunk_id = index["index"]["chunks"][0]["chunk_id"]
            research = store.v5_lifecycle().add_research(
                {"kind": "plan", "claim": "Exercise the background CLI."},
                actor="host",
            )
            planned = store.v5_lifecycle().create_round(
                workers=1,
                research_ids=[research["research_id"]],
            )
            card_path = planned["assignments"][0]["task_card_path"]
            stdout = StringIO()
            with redirect_stdout(stdout), redirect_stderr(StringIO()):
                code = cli_main(
                    [
                        "--root",
                        str(root),
                        "--role",
                        "worker",
                        "project-background-read",
                        chunk_id,
                        "--task-card",
                        card_path,
                    ]
                )
            self.assertEqual(code, 0)
            chunk = json.loads(stdout.getvalue())
            self.assertEqual(chunk["content"], "# Background\n\nExact CLI chunk.\n")
            self.assertEqual(chunk["sha256"], sha256_bytes(chunk["content"].encode("utf-8")))

            stderr = StringIO()
            with redirect_stdout(StringIO()), redirect_stderr(stderr):
                code = cli_main(
                    [
                        "--root",
                        str(root),
                        "--role",
                        "worker",
                        "project-background-read",
                        chunk_id,
                    ]
                )
            self.assertEqual(code, 2)
            self.assertIn("requires --task-card", stderr.getvalue())

    def test_host_v5_verification_extension_is_additive_and_v4_does_not_expand(self) -> None:
        self.assertEqual(
            allowed_commands_for_workflow("host", 5),
            {
                "pulse-dispatch",
                "pulse-status",
                "pulse-audit",
                "verification-packet-prepare",
                "verification-packet-record",
                "verification-status",
            },
        )
        self.assertEqual(
            allowed_commands_for_workflow("host", 4),
            {
                "pulse-dispatch",
                "pulse-status",
                "pulse-audit",
            },
        )
        self.assertNotIn("plan-round", allowed_commands_for_workflow("host", 5))
        self.assertNotIn(
            "project-background-read",
            allowed_commands_for_workflow("worker", 4),
        )
        self.assertEqual(
            allowed_commands_for_workflow("worker", 5)
            - allowed_commands_for_workflow("worker", 4),
            {"project-background-read"},
        )


if __name__ == "__main__":
    unittest.main()

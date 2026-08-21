from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from mathgraph.cli import main as cli_main
from mathgraph.roles import allowed_commands
from mathgraph.store import MathGraphStore


class SelectiveFactCheckpointTests(unittest.TestCase):
    @staticmethod
    def _store(root: Path) -> MathGraphStore:
        store = MathGraphStore(root)
        store.initialize(
            project_id="selective-fact-checkpoint",
            title="Selective Fact checkpoint",
            workflow_evidence_version=5,
        )
        return store

    @staticmethod
    def _input(target_id: str, *, excluded_id: str | None = None) -> dict[str, object]:
        return {
            "schema_version": 1,
            "objective": "Certify shared premises before downstream research depends on them.",
            "target_rationales": [
                {
                    "research_id": target_id,
                    "reason": "This result is reused by later branches.",
                }
            ],
            "excluded_research": (
                []
                if excluded_id is None
                else [
                    {
                        "research_id": excluded_id,
                        "reason": "This branch remains geometry-specific and open.",
                    }
                ]
            ),
        }

    def test_checkpoint_is_main_owned_idempotent_and_nonauthorizing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            store = self._store(root)
            lifecycle = store.v5_lifecycle()
            ancestor = lifecycle.add_research(
                {"kind": "direction", "claim": "Establish a reusable premise."},
                actor="main",
            )
            target = lifecycle.add_research(
                {
                    "kind": "proof_attempt",
                    "claim": "The reusable premise holds conditionally.",
                    "relation": "refines",
                    "related_research_ids": [ancestor["research_id"]],
                },
                actor="worker",
            )
            lifecycle.add_research(
                {
                    "kind": "insight",
                    "claim": "A later branch reuses the premise.",
                    "relation": "uses",
                    "related_research_ids": [target["research_id"]],
                },
                actor="worker",
            )
            payload = self._input(target["research_id"])
            first = lifecycle.selective_fact_checkpoint(payload, actor="main")
            second = lifecycle.selective_fact_checkpoint(payload, actor="main")
            self.assertEqual(first["checkpoint_id"], second["checkpoint_id"])
            self.assertEqual(first["record_sha256"], second["record_sha256"])
            self.assertEqual(
                first["selected"][0]["ancestor_ids"],
                [ancestor["research_id"]],
            )
            self.assertEqual(first["selected"][0]["downstream_reuse_count"], 1)
            self.assertEqual(first["selection_authority"], "main_explicit_only")
            self.assertEqual(first["truth_effect"], "none")
            checkpoint = json.loads(Path(first["checkpoint_path"]).read_text())
            self.assertFalse(checkpoint["automatic_ranking"])
            self.assertTrue(checkpoint["candidate_release_preflight_required"])
            self.assertEqual(
                list((root / "candidate_releases" / "by-id").glob("release-*.json")),
                [],
            )
            self.assertEqual(store.fact_ids(), [])
            self.assertIn("selective-fact-checkpoint", allowed_commands("main"))
            self.assertNotIn("selective-fact-checkpoint", allowed_commands("worker"))
            self.assertNotIn("selective-fact-checkpoint", allowed_commands("operator"))
            self.assertEqual(
                first["candidate_batch_seed"]["default_partition"],
                [{"unit": 1, "research_entry_ids": [target["research_id"]]}],
            )
            self.assertTrue(
                first["candidate_batch_seed"]["main_approval_required"]
            )
            self.assertEqual(
                first["candidate_batch_seed"]["partition_semantics"],
                "dependency_closed_authoring_batches_not_fact_atoms",
            )
            self.assertEqual(
                first["candidate_batch_seed"]["candidate_fact_atomicity_contract"],
                "exactly_one_semantic_conclusion_atom_per_fact",
            )
            self.assertFalse(
                first["candidate_batch_seed"]["automatic_atomization"]
            )
            self.assertTrue(
                first["candidate_batch_seed"]["candidate_dag_closure_required"]
            )

    def test_checkpoint_reports_stale_target_and_keeps_main_selection_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            target = lifecycle.add_research(
                {"kind": "proof_attempt", "claim": "A provisional route works."},
                actor="worker",
            )
            invalidator = lifecycle.add_research(
                {
                    "kind": "challenge",
                    "claim": "The provisional route has a counterexample.",
                    "relation": "challenges",
                    "related_research_ids": [target["research_id"]],
                    "route_invalidations": [target["research_id"]],
                },
                actor="supervisor",
            )
            checkpoint = lifecycle.selective_fact_checkpoint(
                self._input(target["research_id"], excluded_id=invalidator["research_id"]),
                actor="main",
            )
            selected = checkpoint["selected"][0]
            self.assertEqual(selected["checkpoint_status"], "blocked")
            self.assertIn(
                "route_invalidated",
                {item["kind"] for item in selected["blockers"]},
            )

    def test_cli_freezes_one_checkpoint_and_target_cap_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            store = self._store(root)
            target = store.v5_lifecycle().add_research(
                {"kind": "proof_attempt", "claim": "One bounded theorem."},
                actor="worker",
            )
            input_path = Path(temporary) / "checkpoint.json"
            input_path.write_text(
                json.dumps(self._input(target["research_id"])),
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
                        "selective-fact-checkpoint",
                        "--input",
                        str(input_path),
                        "--actor",
                        "main",
                    ]
                )
            self.assertEqual(code, 0)
            self.assertTrue(json.loads(stdout.getvalue())["checkpoint_id"].startswith("fact-checkpoint-"))

            oversized = self._input(target["research_id"])
            oversized["target_rationales"] = [
                {"research_id": target["research_id"], "reason": str(index)}
                for index in range(17)
            ]
            with self.assertRaisesRegex(ValueError, "at most 16"):
                store.v5_lifecycle().selective_fact_checkpoint(oversized, actor="main")

    def test_checkpoint_uses_structural_envelopes_for_unselected_research(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            target = lifecycle.add_research(
                {"kind": "proof_attempt", "claim": "Selected theorem."},
                actor="worker",
            )
            lifecycle.add_research(
                {"kind": "direction", "claim": "Unrelated direction."},
                actor="worker",
            )
            original = lifecycle._research_record

            def selected_only(research_id: str, **kwargs: object) -> dict[str, object]:
                if research_id != target["research_id"]:
                    raise AssertionError("unselected Research received full validation")
                return original(research_id, **kwargs)

            with patch.object(lifecycle, "_research_record", side_effect=selected_only):
                checkpoint = lifecycle.selective_fact_checkpoint(
                    self._input(target["research_id"]), actor="main"
                )
            self.assertEqual(checkpoint["selected"][0]["research_id"], target["research_id"])

    def test_checkpoint_reuses_one_inspection_context_across_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            targets = [
                lifecycle.add_research(
                    {"kind": "proof_attempt", "claim": f"Selected claim {index}."},
                    actor="worker",
                )
                for index in range(2)
            ]
            payload = {
                "schema_version": 1,
                "objective": "Inspect two independent selected claims once.",
                "target_rationales": [
                    {
                        "research_id": item["research_id"],
                        "reason": "Explicit Main selection.",
                    }
                    for item in targets
                ],
                "excluded_research": [],
            }
            contexts: list[object] = []
            original = lifecycle._required_supervision_results_for_candidate

            def capture(records: list[dict[str, object]], **kwargs: object) -> set[str]:
                contexts.append(kwargs.get("_inspection_context"))
                return original(records, **kwargs)

            with patch.object(
                lifecycle,
                "_required_supervision_results_for_candidate",
                side_effect=capture,
            ):
                checkpoint = lifecycle.selective_fact_checkpoint(
                    payload,
                    actor="main",
                )
            self.assertEqual(len(checkpoint["selected"]), 2)
            self.assertEqual(len(contexts), 2)
            self.assertIsNotNone(contexts[0])
            self.assertIs(contexts[0], contexts[1])

    def test_atomization_closes_selected_dependencies_and_propagates_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            premise = lifecycle.add_research(
                {"kind": "proof_attempt", "claim": "Selected load-bearing premise."},
                actor="worker",
            )
            dependent = lifecycle.add_research(
                {
                    "kind": "proof_attempt",
                    "claim": "Selected consequence.",
                    "relation": "uses",
                    "related_research_ids": [premise["research_id"]],
                },
                actor="worker",
            )
            unrelated = lifecycle.add_research(
                {"kind": "proof_attempt", "claim": "Independent selected claim."},
                actor="worker",
            )
            checkpoint = lifecycle.selective_fact_checkpoint(
                {
                    "schema_version": 1,
                    "objective": "Partition only dependency-closed selected units.",
                    "target_rationales": [
                        {"research_id": premise["research_id"], "reason": "premise"},
                        {"research_id": dependent["research_id"], "reason": "dependent"},
                        {"research_id": unrelated["research_id"], "reason": "unrelated"},
                    ],
                    "excluded_research": [],
                },
                actor="main",
            )
            seed = checkpoint["candidate_batch_seed"]
            self.assertEqual(
                seed["selected_dependency_edges"],
                [[premise["research_id"], dependent["research_id"]]],
            )
            units = [set(item["research_entry_ids"]) for item in seed["default_partition"]]
            self.assertIn({premise["research_id"], dependent["research_id"]}, units)
            self.assertIn({unrelated["research_id"]}, units)
            self.assertEqual(sum(map(len, units)), 3)

            review_only_premise = lifecycle.add_research(
                {
                    "kind": "proof_attempt",
                    "status": "blocked",
                    "claim": "A selected review-only record cannot anchor a Candidate.",
                },
                actor="supervisor",
            )
            review_dependent = lifecycle.add_research(
                {
                    "kind": "proof_attempt",
                    "claim": "A selected target depends on the review-only record.",
                    "relation": "uses",
                    "related_research_ids": [review_only_premise["research_id"]],
                },
                actor="worker",
            )
            blocked = lifecycle.selective_fact_checkpoint(
                {
                    "schema_version": 1,
                    "objective": "Propagate selected dependency blockers.",
                    "target_rationales": [
                        {
                            "research_id": review_only_premise["research_id"],
                            "reason": "review-only premise",
                        },
                        {
                            "research_id": review_dependent["research_id"],
                            "reason": "dependent",
                        },
                    ],
                    "excluded_research": [],
                },
                actor="main",
            )
            by_id = {item["research_id"]: item for item in blocked["selected"]}
            self.assertEqual(
                by_id[review_only_premise["research_id"]]["checkpoint_status"],
                "blocked",
            )
            self.assertEqual(
                by_id[review_dependent["research_id"]]["checkpoint_status"],
                "blocked",
            )
            self.assertIn(
                "selected_dependency_blocked",
                {
                    item["kind"]
                    for item in by_id[review_dependent["research_id"]]["blockers"]
                },
            )
            self.assertEqual(blocked["candidate_batch_seed"]["default_partition"], [])

            repaired = lifecycle.add_research(
                {
                    "kind": "repair",
                    "claim": "A repair retains lineage without inheriting the blocker.",
                    "relation": "repairs",
                    "related_research_ids": [review_only_premise["research_id"]],
                },
                actor="worker",
            )
            repair_checkpoint = lifecycle.selective_fact_checkpoint(
                {
                    "schema_version": 1,
                    "objective": "Do not treat repair lineage as a positive dependency.",
                    "target_rationales": [
                        {
                            "research_id": review_only_premise["research_id"],
                            "reason": "blocked source",
                        },
                        {"research_id": repaired["research_id"], "reason": "repair"},
                    ],
                    "excluded_research": [],
                },
                actor="main",
            )
            repair_seed = repair_checkpoint["candidate_batch_seed"]
            self.assertEqual(repair_seed["selected_dependency_edges"], [])
            self.assertEqual(repair_seed["ready_research_ids"], [repaired["research_id"]])
            self.assertEqual(
                repair_seed["default_partition"],
                [{"unit": 1, "research_entry_ids": [repaired["research_id"]]}],
            )


if __name__ == "__main__":
    unittest.main()

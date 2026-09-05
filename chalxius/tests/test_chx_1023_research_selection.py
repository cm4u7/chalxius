from __future__ import annotations

import copy
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import test_research_two_subround as research_fixtures
from mathgraph.cli import main as cli_main
from mathgraph.contracts import sha256_bytes, sha256_json
from mathgraph.store import MathGraphStore


class ResearchSelectionContinuityTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "project"
        self.store = MathGraphStore(self.root)
        self.store.initialize(
            project_id="selection-continuity",
            title="Exact selected work history",
            workflow_evidence_version=5,
        )
        self.lifecycle = self.store.v5_lifecycle()

    def _research(self, claim: str = "One bounded task.", **fields: object) -> str:
        return self.lifecycle.add_research(
            {"kind": "direction", "claim": claim, **fields}, actor="main",
        )["research_id"]

    def _plan(self, research_id: str, *, host: str = "selection-host") -> dict:
        return self.lifecycle.create_production_round(
            workers=1, mode="prove", research_ids=[research_id], host_task_scope_id=host,
        )

    def _snapshot(self) -> dict[str, str]:
        return {
            path.relative_to(self.root).as_posix(): sha256_bytes(path.read_bytes())
            for path in self.root.rglob("*") if path.is_file()
        }

    def _cli(self, *args: str) -> tuple[int, dict, str]:
        stdout, stderr = StringIO(), StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = cli_main(["--root", str(self.root), "--role", "main", *args])
        return code, json.loads(stdout.getvalue()) if code == 0 else {}, stderr.getvalue()

    def test_completed_exact_work_is_named_while_explicit_rerun_remains_legal(self) -> None:
        research_id = self._research()
        first = self._plan(research_id)
        receipt = research_fixtures.ResearchTwoSubroundTests()._ingest_plain_assignment(
            self.store, first, first["assignments"][0],
        )
        old_round = (self.store.rounds_dir / first["round_id"] / "round.json").read_bytes()
        second = self._plan(research_id, host="different-host")
        self.assertNotEqual(second["round_id"], first["round_id"])
        advisory = second["selected_work_history"]
        self.assertEqual(advisory["matching_assignment_count"], 1)
        row = advisory["entries"][0]["history"][0]
        self.assertEqual(row["round_id"], first["round_id"])
        self.assertEqual(row["state"], "ingested")
        self.assertEqual(row["research_product_id"], receipt["research_id"])
        self.assertEqual(advisory["selection_effect"], "none")
        self.assertEqual(advisory["truth_effect"], "none")
        self.assertEqual(old_round, (self.store.rounds_dir / first["round_id"] / "round.json").read_bytes())
        manifest = json.loads((self.store.rounds_dir / second["round_id"] / "round.json").read_bytes())
        self.assertNotIn("selected_work_history", manifest)
        card = json.loads(Path(second["assignments"][0]["task_card_path"]).read_bytes())
        self.assertNotIn("selected_work_history", card)

    def test_exact_history_ignores_same_claim_and_related_identity(self) -> None:
        first_id = self._research()
        first = self._plan(first_id)
        second_id = self._research(relation="context", related_research_ids=[first_id])
        second = self._plan(second_id)
        self.assertNotIn("selected_work_history", second)
        result = self.lifecycle.selected_work_history([first_id], exclude_round_id=first["round_id"])
        self.assertEqual(result["matching_assignment_count"], 0)

    def test_in_flight_exact_work_and_read_only_full_drilldown(self) -> None:
        research_id = self._research()
        first = self._plan(research_id)
        second = self._plan(research_id)
        row = second["selected_work_history"]["entries"][0]["history"][0]
        self.assertEqual(row["state"], "awaiting_return")
        self.assertEqual(row["round_id"], first["round_id"])
        before = self._snapshot()
        code, history, stderr = self._cli("round-status", "--research-id", research_id)
        self.assertEqual(code, 0, stderr)
        self.assertEqual(history["matching_assignment_count"], 2)
        self.assertFalse(history["entries"][0]["history_truncated"])
        self.assertEqual(before, self._snapshot())

    def test_only_bounded_exact_matches_are_deeply_inspected(self) -> None:
        research_id = self._research()
        rounds = [
            self.lifecycle.create_round(workers=1, mode="prove", research_ids=[research_id])
            for _ in range(6)
        ]
        unrelated_id = self._research("Unrelated task.")
        unrelated = self._plan(unrelated_id)
        called: list[str] = []
        original = self.lifecycle._round_status_with_context

        def inspect(round_id, inspection):
            called.append(round_id)
            return original(round_id, inspection)

        with patch.object(self.lifecycle, "_round_status_with_context", side_effect=inspect):
            history = self.lifecycle.selected_work_history([research_id])
        expected_ids = sorted(item["round_id"] for item in rounds)
        self.assertEqual(sorted(set(called)), expected_ids[-4:])
        self.assertNotIn(unrelated["round_id"], called)
        row = history["entries"][0]
        self.assertEqual(row["matching_assignment_count"], 6)
        self.assertTrue(row["history_truncated"])
        self.assertEqual(row["diagnostic_argv"], ["round-status", "--research-id", research_id])
        identities = sorted((item["round_id"], item["assignments"][0]["assignment_id"]) for item in rounds)
        self.assertEqual(row["assignment_identities_sha256"], sha256_json(identities))
        full = self.lifecycle.selected_work_history([research_id], full=True)
        self.assertEqual([item["round_id"] for item in full["entries"][0]["history"]], expected_ids)
        self.assertFalse(full["entries"][0]["history_truncated"])

    def test_shared_unreadable_round_is_counted_once_across_selected_ids(self) -> None:
        selected = [self._research("First task."), self._research("Second task.")]
        planned = self.lifecycle.create_round(workers=2, mode="prove", research_ids=selected)
        path = Path(planned["assignments"][0]["task_card_path"])
        card = json.loads(path.read_bytes())
        card["task_card_sha256"] = "0" * 64
        path.write_text(json.dumps(card), encoding="utf-8")
        before = self._snapshot()
        history = self.lifecycle.selected_work_history(selected)
        self.assertEqual(history["matching_assignment_count"], 2)
        self.assertEqual(history["unreadable_round_count"], 1)
        self.assertEqual(history["unreadable_rounds"][0]["round_id"], planned["round_id"])
        for entry in history["entries"]:
            self.assertEqual(entry["history"][0]["state"], "unreadable")
        self.assertEqual(before, self._snapshot())

    def test_drifted_history_is_nonblocking_and_never_reported_as_absent(self) -> None:
        research_id = self._research()
        first = self._plan(research_id)
        path = self.store.rounds_dir / first["round_id"] / "round.json"
        payload = json.loads(path.read_bytes())
        payload["manifest_sha256"] = "0" * 64
        path.write_text(json.dumps(payload), encoding="utf-8")
        second = self._plan(research_id)
        self.assertTrue((self.store.rounds_dir / second["round_id"] / "round.json").is_file())
        history = second["selected_work_history"]
        self.assertEqual(history["unreadable_round_count"], 1)
        self.assertEqual(history["unreadable_rounds"][0]["round_id"], first["round_id"])
        self.assertIn("hash mismatch", history["unreadable_rounds"][0]["reason"])

    def test_nested_metadata_warning_does_not_rewrite_input_or_record(self) -> None:
        payload = {
            "kind": "direction", "claim": "Nested input fixture.",
            "metadata": {"work_mode": "prove", "obligations": [], "stop_conditions": ["Stop here."]},
        }
        original = copy.deepcopy(payload)
        path = self.root / "input.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        code, result, stderr = self._cli("memory-add", "--input", str(path), "--actor", "main")
        self.assertEqual(code, 0, stderr)
        self.assertEqual(result["advisories"][0]["code"], "nested_research_metadata")
        record = self.lifecycle._research_record(result["research_id"])
        self.assertEqual(record["metadata"]["metadata"], original["metadata"])
        self.assertNotIn("work_mode", record["metadata"])
        self.assertEqual(json.loads(path.read_bytes()), original)
        flat = {"kind": "direction", "claim": "Flat input fixture.", **original["metadata"]}
        path.write_text(json.dumps(flat), encoding="utf-8")
        code, result, stderr = self._cli("memory-add", "--input", str(path), "--actor", "main")
        self.assertEqual(code, 0, stderr)
        self.assertNotIn("advisories", result)
        record = self.lifecycle._research_record(result["research_id"])
        self.assertEqual(record["metadata"]["work_mode"], "prove")

    def test_round_status_exact_selector_does_not_expand_all_implicitly(self) -> None:
        research_id = self._research()
        code, _result, stderr = self._cli("round-status", "--all", "--research-id", research_id)
        self.assertNotEqual(code, 0)
        self.assertIn("accepts one ROUND_ID, --all, or --research-id", stderr)


if __name__ == "__main__":
    unittest.main()

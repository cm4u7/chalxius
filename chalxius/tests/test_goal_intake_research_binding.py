from __future__ import annotations

import json
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest

from mathgraph.brave_future import BF_GOAL_INTAKE_REVISION
from mathgraph.cli import main as cli_main
from mathgraph.store import MathGraphStore


class GoalIntakeResearchBindingTests(unittest.TestCase):
    def _store(self, root: Path) -> MathGraphStore:
        store = MathGraphStore(root)
        store.initialize(
            project_id="goal-intake-research-binding",
            title="Goal intake Research lineage",
            workflow_evidence_version=5,
            reasoning_mode="auto",
        )
        return store

    @staticmethod
    def _goal(objective: str) -> dict[str, str]:
        return {"revision": BF_GOAL_INTAKE_REVISION, "objective": objective}

    def test_public_goal_command_binds_root_research_without_campaign_jargon(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            store = self._store(root)
            goal_path = Path(temporary) / "goal.json"
            goal_path.write_text(
                json.dumps(self._goal("Strengthen the exact draft argument.")) + "\n",
                encoding="utf-8",
            )
            stdout, stderr = StringIO(), StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = cli_main(
                    [
                        "--root",
                        str(root),
                        "--role",
                        "operator",
                        "research-goal-intake",
                        "--input",
                        str(goal_path),
                        "--actor",
                        "user",
                    ]
                )
            self.assertEqual(code, 0, stderr.getvalue())
            result = json.loads(stdout.getvalue())
            research = store.v5_lifecycle()._research_record(
                result["root_research_id"]
            )
            binding = research["metadata"]["goal_intake_binding"]
            self.assertEqual(binding["intake_token"], result["intake_token"])
            self.assertEqual(binding["campaign_id"], result["campaign_id"])
            self.assertEqual(research["metadata"]["campaign_id"], result["campaign_id"])
            self.assertTrue(result["research_scope"]["intake_token_bound"])
            self.assertFalse(result["automatic_plan"])
            self.assertFalse(result["automatic_dispatch"])
            self.assertEqual(store.fact_ids(), [])
            self.assertEqual(list(store.rounds_dir.iterdir()), [])

            repeated_out, repeated_err = StringIO(), StringIO()
            with redirect_stdout(repeated_out), redirect_stderr(repeated_err):
                repeated_code = cli_main(
                    [
                        "--root",
                        str(root),
                        "--role",
                        "operator",
                        "research-goal-intake",
                        "--input",
                        str(goal_path),
                        "--actor",
                        "user",
                    ]
                )
            self.assertEqual(repeated_code, 0, repeated_err.getvalue())
            repeated = json.loads(repeated_out.getvalue())
            self.assertEqual(repeated["root_research_id"], result["root_research_id"])
            self.assertEqual(
                repeated["research_write_effect"], "none_existing_root_reused"
            )
            self.assertEqual(len(store.v5_lifecycle().research_records()), 1)

    def test_plain_research_has_no_spurious_goal_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            record = store.v5_lifecycle().add_research(
                {
                    "kind": "direction",
                    "claim": "A plain Research direction.",
                    "content": "No ordinary-goal intake preceded this record.",
                },
                actor="main",
            )
            self.assertNotIn("goal_intake_binding", record["metadata"])
            self.assertNotIn("campaign_id", record["metadata"])

    def test_tampered_or_conflicting_intake_fails_before_research_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            store = self._store(root)
            intake = store.brave_future().intake_research_goal(
                goal_input=self._goal("One exact tamper target."),
                actor="user",
            )
            before = store.v5_lifecycle().research_records()
            with self.assertRaisesRegex(ValueError, "conflicts"):
                store.v5_lifecycle().add_research(
                    {
                        "kind": "direction",
                        "claim": "Conflicting scope.",
                        "content": "The payload must not override the intake scope.",
                        "campaign_id": "campaign-" + "f" * 16,
                    },
                    actor="main",
                    goal_intake_token=intake["intake_token"],
                )
            self.assertEqual(store.v5_lifecycle().research_records(), before)

            terminal = (
                root
                / "governance"
                / "brave-future"
                / "goal-intakes"
                / "terminal-receipts"
                / "by-token"
                / f"{intake['intake_token']}.json"
            )
            payload = json.loads(terminal.read_text(encoding="utf-8"))
            payload["receipt_sha256"] = "0" * 64
            terminal.write_text(
                json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                store.v5_lifecycle().add_research(
                    {
                        "kind": "direction",
                        "claim": "Tampered lineage.",
                        "content": "This record must not be written.",
                    },
                    actor="main",
                    goal_intake_token=intake["intake_token"],
                )
            self.assertEqual(list(store.v5_lifecycle().research_entries_dir.glob("*.json")), [])


if __name__ == "__main__":
    unittest.main()

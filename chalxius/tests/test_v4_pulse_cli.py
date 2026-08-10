from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from mathgraph.cli import main as cli_main
from mathgraph.orchestrator import create_round
from mathgraph.store import MathGraphStore


class PulseCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = MathGraphStore(self.root)
        self.store.initialize(
            project_id="pulse-cli-test",
            title="Pulse CLI test",
            workflow_evidence_version=4,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _run(self, *args: str) -> tuple[int, dict]:
        output = StringIO()
        errors = StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = cli_main(
                [
                    "--root",
                    str(self.root),
                    "--role",
                    "main",
                    *args,
                ]
            )
        if code != 0:
            self.fail(errors.getvalue())
        return code, json.loads(output.getvalue())

    def test_plan_status_and_audit_are_exposed_by_cli(self) -> None:
        memory_ids = [
            self.store.memory_add(
                {
                    "kind": "direction",
                    "claim": f"Pulse CLI lane {index}.",
                    "rationale": "CLI coverage.",
                    "suggested_actions": ["prove"],
                },
                actor="main",
            )
            for index in range(2)
        ]
        planned = create_round(
            self.store,
            workers=2,
            memory_ids=memory_ids,
            host_task_scope_id="hosttask-" + "a" * 32,
        )
        config = self.root / "pulse-plan-input.json"
        config.write_text(
            json.dumps(
                {
                    "wave1_assignments": [
                        {
                            "round_id": planned["round_id"],
                            "assignment_id": item["assignment_id"],
                        }
                        for item in planned["assignments"]
                    ],
                    "minimum_wave1_contributors": 2,
                }
            ),
            encoding="utf-8",
        )
        _, plan = self._run(
            "pulse-plan",
            "--input",
            str(config),
        )
        pulse_id = plan["pulse_id"]
        _, status = self._run("pulse-status", pulse_id)
        self.assertEqual(status["state"], "wave1_open")
        self.assertFalse(status["procedural_ready"])
        _, audit = self._run("pulse-audit", pulse_id)
        self.assertTrue(audit["ok"])
        self.assertTrue(
            any("no barrier" in item for item in audit["warnings"])
        )
        _, abort = self._run(
            "pulse-abort",
            pulse_id,
            "--failure-phase",
            "wave1_graph_preflight",
            "--reason",
            "A core worker return failed graph preflight.",
        )
        self.assertTrue(abort["abort_id"].startswith("bbabort-"))
        _, aborted_status = self._run("pulse-status", pulse_id)
        self.assertEqual(aborted_status["state"], "aborted")
        self.assertFalse(aborted_status["procedural_ready"])
        _, aborted_audit = self._run("pulse-audit", pulse_id)
        self.assertTrue(aborted_audit["ok"])
        self.assertEqual(aborted_audit["warnings"], [])

    def test_v5_retires_new_pulse_planning_without_touching_v4(self) -> None:
        v5_root = self.root / "v5"
        v5_store = MathGraphStore(v5_root)
        v5_store.initialize(
            project_id="v5-retired-pulse-plan",
            title="V5 retired Pulse planning",
            workflow_evidence_version=5,
        )
        output = StringIO()
        errors = StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = cli_main(
                [
                    "--root",
                    str(v5_root),
                    "--role",
                    "main",
                    "pulse-plan",
                    "--input",
                    str(v5_root / "unused-input.json"),
                ]
            )
        self.assertEqual(code, 2)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("new Pulse planning is retired for V5", errors.getvalue())
        self.assertFalse((v5_root / "collaboration").exists())


if __name__ == "__main__":
    unittest.main()

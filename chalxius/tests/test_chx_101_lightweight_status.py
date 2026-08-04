"""CHX-101: routine status must not hide a complete forensic audit."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from mathgraph.cli import main
from mathgraph.store import MathGraphStore


class CHX101LightweightStatusTests(unittest.TestCase):
    def test_routine_status_skips_audit_and_explicit_flag_preserves_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            MathGraphStore(root).initialize(
                project_id="chx-101-status",
                title="CHX-101 status",
                workflow_evidence_version=5,
            )
            argv = [
                "--root",
                str(root),
                "--role",
                "operator",
                "status",
            ]

            routine_output = io.StringIO()
            with patch.object(
                MathGraphStore,
                "audit",
                side_effect=AssertionError("routine status invoked forensic audit"),
            ) as audit:
                with redirect_stdout(routine_output):
                    self.assertEqual(main(argv), 0)
            audit.assert_not_called()
            routine = json.loads(routine_output.getvalue())
            self.assertEqual(
                routine["audit"],
                {
                    "performed": False,
                    "current_ok": None,
                    "history_clean": None,
                    "next_safe_command": "audit",
                    "truth_effect": "none",
                },
            )

            report = Mock()
            report.as_dict.return_value = {
                "current_ok": True,
                "history_clean": True,
                "truth_effect": "none",
            }
            forensic_output = io.StringIO()
            with patch.object(
                MathGraphStore,
                "audit",
                return_value=report,
            ) as audit:
                with redirect_stdout(forensic_output):
                    self.assertEqual(main([*argv, "--with-audit"]), 0)
            audit.assert_called_once_with()
            forensic = json.loads(forensic_output.getvalue())
            self.assertEqual(forensic["audit"], report.as_dict.return_value)


if __name__ == "__main__":
    unittest.main()

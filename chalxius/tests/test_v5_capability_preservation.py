from __future__ import annotations

import ast
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]


class V5CapabilityPreservationTests(unittest.TestCase):
    def test_every_036_cli_command_is_accounted_for(self) -> None:
        cli_path = SKILL_ROOT / "scripts" / "mathgraph" / "cli.py"
        tree = ast.parse(cli_path.read_text(encoding="utf-8"))
        commands = {
            node.args[0].value
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_parser"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        }
        matrix = (
            SKILL_ROOT / "references" / "v5_capability_matrix.md"
        ).read_text(encoding="utf-8")
        missing = sorted(command for command in commands if f"`{command}`" not in matrix)
        self.assertEqual(missing, [], f"unmapped 0.3.6 public commands: {missing}")

    def test_three_planes_and_task_cards_are_preservation_invariants(self) -> None:
        matrix = (
            SKILL_ROOT / "references" / "v5_capability_matrix.md"
        ).read_text(encoding="utf-8")
        for required in (
            "control: compact prompt",
            "mathematical state: one frozen bounded snapshot",
            "narrative: bounded rationale",
            "task card remains immutable capability data",
        ):
            self.assertIn(required, matrix)

    def test_original_danus_is_reference_only(self) -> None:
        matrix = (
            SKILL_ROOT / "references" / "v5_capability_matrix.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Original Danus versions", matrix)
        self.assertIn(
            "no source module, runtime, writer, fact, review, receipt, or mutable store",
            matrix,
        )


if __name__ == "__main__":
    unittest.main()

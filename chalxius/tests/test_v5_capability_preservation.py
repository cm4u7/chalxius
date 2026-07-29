from __future__ import annotations

import ast
import hashlib
import json
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]


class V5CapabilityPreservationTests(unittest.TestCase):
    def test_044_runtime_extension_is_exact_and_legacy_behavior_is_explicit(self) -> None:
        lock = json.loads(
            (SKILL_ROOT / "INHERITANCE.lock.json").read_text(encoding="utf-8")
        )
        compatibility = lock["runtime_compatibility"]
        paths: list[Path] = []
        for spec in (
            "scripts/mathgraph",
            "scripts/mgraph",
            "scripts/mgraph_cli.py",
            "scripts/chx_ledger.py",
            "scripts/notation_inventory.py",
            "scripts/prepare_verifier_capsule.py",
            "scripts/learning_graph.py",
            "scripts/learn",
            "assets/reader_html_template.html",
            "assets/reader_html_app.js",
            "assets/reader_html.css",
            "assets/vendor",
        ):
            path = SKILL_ROOT / spec
            if path.is_dir():
                paths.extend(
                    child
                    for child in path.rglob("*")
                    if child.is_file() and "__pycache__" not in child.parts
                )
            else:
                paths.append(path)
        digest = hashlib.sha256()
        for path in sorted(set(paths), key=lambda item: item.relative_to(SKILL_ROOT).as_posix()):
            relative = path.relative_to(SKILL_ROOT).as_posix().encode("utf-8")
            file_hash = hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii")
            digest.update(relative + b"\0" + file_hash + b"\n")
        self.assertEqual(compatibility["baseline"], "chalxius-0.4.3")
        self.assertEqual(compatibility["protected_file_count"], len(set(paths)))
        self.assertEqual(compatibility["protected_tree_sha256"], digest.hexdigest())
        self.assertEqual(
            compatibility["changed_from_0.4.3_runtime_paths"],
            [
                "assets/reader_html_app.js",
                "assets/reader_html_template.html",
                "scripts/chx_ledger.py",
                "scripts/mathgraph/cli.py",
                "scripts/mathgraph/interfaces.py",
                "scripts/mathgraph/modes.py",
                "scripts/mathgraph/project_background.py",
                "scripts/mathgraph/reader_html.py",
                "scripts/mathgraph/roles.py",
                "scripts/mathgraph/v5_lifecycle.py",
                "scripts/mathgraph/v5_reader.py",
            ],
        )
        self.assertEqual(
            compatibility["project_schema_change"],
            "prospective_v5_context_selection_indexed_background_runtime_binding_source_capability_and_adverse_provenance_only",
        )
        self.assertEqual(
            compatibility["activation_absent_behavior"],
            "legacy_frozen_task_cards_returns_releases_and_decisions_preserved",
        )
        self.assertFalse(compatibility["fact_admission_change"])
        self.assertEqual(
            compatibility["fact_admission_change_scope"],
            "contract_unchanged_implementation_hardened_for_nonrecursive_recovery_and_future_legacy_premise_validation",
        )
        task_context = lock["v5_task_context_surface"]
        self.assertEqual(
            task_context["contract_revision"],
            "chalxius-v5-task-context-0.4.4-1",
        )
        self.assertEqual(
            task_context["activation"],
            "prospective_new_task_cards_only",
        )
        self.assertEqual(task_context["truth_effect"], "none")
        self.assertFalse(task_context["fact_admission_change"])

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

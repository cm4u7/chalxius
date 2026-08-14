from __future__ import annotations

import os
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import aggressive_bug_audit as aggressive_bug_audit_module
import mathgraph.runtime_cutover as runtime_cutover_module


SOURCE_SCRIPTS = Path(runtime_cutover_module.__file__).resolve().parents[1]


class HostEntrypointNonMutationTests(unittest.TestCase):
    def test_mutant_registry_preflight_runs_before_any_test_subprocess(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            scripts = root / "scripts"
            target = scripts / "mathgraph" / "probe.py"
            target.parent.mkdir(parents=True)
            target.write_text("current target\n", encoding="utf-8")
            stale = aggressive_bug_audit_module.Mutant(
                name="stale-probe",
                old="removed target\n",
                new="mutated\n",
                test="tests.test_probe.Probe.test_target",
                target="mathgraph/probe.py",
            )
            with self.assertRaisesRegex(
                SystemExit, "mutant registry preflight: stale-probe.*found 0"
            ):
                aggressive_bug_audit_module._validate_mutant_targets(
                    candidate_root=root,
                    source_scripts=scripts,
                    mutants=(stale,),
                )

        with (
            mock.patch.object(aggressive_bug_audit_module, "MUTANTS", ()),
            mock.patch.object(
                aggressive_bug_audit_module,
                "_validate_mutant_targets",
                side_effect=SystemExit("preflight sentinel"),
            ) as preflight,
            mock.patch.object(aggressive_bug_audit_module, "_run_test") as run_test,
        ):
            with self.assertRaisesRegex(SystemExit, "preflight sentinel"):
                aggressive_bug_audit_module.main([])
            preflight.assert_called_once()
            run_test.assert_not_called()

        original_preflight = aggressive_bug_audit_module._validate_mutant_targets
        with (
            mock.patch.object(aggressive_bug_audit_module, "MUTANTS", ()),
            mock.patch.object(
                aggressive_bug_audit_module,
                "_validate_mutant_targets",
                wraps=original_preflight,
            ) as preflight,
            mock.patch.object(
                aggressive_bug_audit_module,
                "_candidate_is_unchanged",
                side_effect=SystemExit("post-preflight sentinel"),
            ),
            mock.patch.object(aggressive_bug_audit_module, "_run_test") as run_test,
        ):
            with self.assertRaisesRegex(SystemExit, "post-preflight sentinel"):
                aggressive_bug_audit_module.main(["--preflight-only"])
            preflight.assert_called_once()
            run_test.assert_not_called()

    def test_aggressive_audit_child_boundary_and_snapshot_are_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scripts = root / "scripts"
            tests = root / "tests"
            shutil.copytree(
                SOURCE_SCRIPTS,
                scripts,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
            tests.mkdir()
            (tests / "__init__.py").write_text("", encoding="utf-8")
            (tests / "test_probe.py").write_text(
                "import unittest\n"
                "import mathgraph.roles\n"
                "class BytecodeProbe(unittest.TestCase):\n"
                "    def test_import(self):\n"
                "        self.assertIn('research-goal-intake', mathgraph.roles.ALL_COMMANDS)\n",
                encoding="utf-8",
            )
            before = aggressive_bug_audit_module._candidate_snapshot(root)
            with mock.patch.dict(os.environ, {}, clear=True):
                outcome = aggressive_bug_audit_module._run_test(
                    repo=root,
                    scripts=scripts,
                    test="tests.test_probe.BytecodeProbe.test_import",
                )
            self.assertEqual(outcome.returncode, 0, outcome.stdout)
            self.assertEqual(list(root.rglob("__pycache__")), [])
            self.assertEqual(list(root.rglob("*.pyc")), [])
            self.assertTrue(
                aggressive_bug_audit_module._candidate_is_unchanged(before, root)
            )
            (root / "unexpected.txt").write_text("drift\n", encoding="utf-8")
            self.assertFalse(
                aggressive_bug_audit_module._candidate_is_unchanged(before, root)
            )

    def test_mutant_runtime_is_complete_canonical_and_manifest_rebound(self) -> None:
        candidate = SOURCE_SCRIPTS.parent
        with tempfile.TemporaryDirectory() as temporary:
            runtime = aggressive_bug_audit_module._copy_complete_runtime(
                candidate_root=candidate,
                parent=Path(temporary),
            )
            self.assertEqual(runtime.name, "chalxius")
            self.assertEqual(runtime.parent, Path(temporary).resolve())
            target = runtime / "scripts" / "mathgraph" / "roles.py"
            target.write_text(
                target.read_text(encoding="utf-8") + "\n# deliberate test mutation\n",
                encoding="utf-8",
            )
            manifest_sha256 = (
                aggressive_bug_audit_module._rebind_mutant_manifest(
                    runtime_root=runtime,
                    target=target,
                )
            )
            manifest = runtime / "MANIFEST.sha256"
            self.assertEqual(
                manifest_sha256,
                hashlib.sha256(manifest.read_bytes()).hexdigest(),
            )
            row = next(
                line
                for line in manifest.read_text(encoding="utf-8").splitlines()
                if line.endswith("  scripts/mathgraph/roles.py")
            )
            self.assertEqual(
                row.split("  ", 1)[0],
                hashlib.sha256(target.read_bytes()).hexdigest(),
            )

    def test_default_python_entrypoints_do_not_create_bytecode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scripts = root / "scripts"
            shutil.copytree(
                SOURCE_SCRIPTS,
                scripts,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
            environment = dict(os.environ)
            environment.pop("PYTHONDONTWRITEBYTECODE", None)
            environment.pop("PYTHONPYCACHEPREFIX", None)
            for name in (
                "archive_runtime.py",
                "chx_ledger.py",
                "runtime_cutover.py",
                "runtime_cutover_project_validation.py",
            ):
                outcome = subprocess.run(
                    [sys.executable, str(scripts / name), "--help"],
                    cwd=root,
                    env=environment,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
                self.assertEqual(outcome.returncode, 0, outcome.stdout)
            self.assertEqual(list(root.rglob("__pycache__")), [])
            self.assertEqual(list(root.rglob("*.pyc")), [])


if __name__ == "__main__":
    unittest.main()

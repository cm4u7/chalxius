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
PUBLIC_HELP_ENTRYPOINTS = (
    "aggressive_bug_audit.py",
    "architecture_reconnaissance.py",
    "archive_runtime.py",
    "behavioral_feature_gate.py",
    "chx_ledger.py",
    "learning_graph.py",
    "mgraph_cli.py",
    "notation_inventory.py",
    "paper_library.py",
    "paper_research_pipeline.py",
    "phx_ledger.py",
    "prepare_verifier_capsule.py",
    "release_validation.py",
    "runtime_cutover.py",
    "runtime_cutover_project_validation.py",
    "submit_neutral_review.py",
)


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
            for name in PUBLIC_HELP_ENTRYPOINTS:
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
            probe = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "import runpy, sys; "
                        "runpy.run_path(sys.argv[1], run_name='bytecode_probe')"
                    ),
                    str(scripts / "self_test.py"),
                ],
                cwd=root,
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(probe.returncode, 0, probe.stdout)
            package_probe = subprocess.run(
                [sys.executable, "-m", "mathgraph", "--help"],
                cwd=root,
                env={**environment, "PYTHONPATH": str(scripts)},
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(package_probe.returncode, 0, package_probe.stdout)
            self.assertEqual(list(root.rglob("__pycache__")), [])
            self.assertEqual(list(root.rglob("*.pyc")), [])

    def test_read_only_runtime_tolerates_a_preexisting_package_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scripts = root / "scripts"
            shutil.copytree(
                SOURCE_SCRIPTS,
                scripts,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
            package = scripts / "mathgraph"
            cache = package / "__pycache__" / (
                f"__init__.{sys.implementation.cache_tag}.pyc"
            )
            cache.parent.mkdir()
            cache.write_bytes(b"stale cache bytes")
            for path in sorted(package.rglob("*"), reverse=True):
                os.chmod(path, 0o555 if path.is_dir() else 0o444)
            os.chmod(package, 0o555)
            try:
                outcome = subprocess.run(
                    [sys.executable, "-c", "import mathgraph; print('ok')"],
                    cwd=root,
                    env={**os.environ, "PYTHONPATH": str(scripts)},
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
                self.assertEqual(outcome.returncode, 0, outcome.stdout)
                self.assertIn("ok", outcome.stdout)
            finally:
                for path in [package, *package.rglob("*")]:
                    if path.exists() and not path.is_symlink():
                        os.chmod(path, 0o700 if path.is_dir() else 0o600)


if __name__ == "__main__":
    unittest.main()

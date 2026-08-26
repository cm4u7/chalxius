from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mathgraph.contracts import sha256_bytes
from mathgraph._local_install import (
    default_focused_test_runner,
    default_global_paths,
    perform_local_install,
)


class LocalInstallTests(unittest.TestCase):
    @staticmethod
    def _runtime(root: Path, version: str, payload: str) -> Path:
        root.mkdir(parents=True)
        version_path = root / "VERSION"
        payload_path = root / "runtime_payload.txt"
        manifest_path = root / "MANIFEST.sha256"
        version_path.write_text(version + "\n", encoding="utf-8")
        payload_path.write_text(payload + "\n", encoding="utf-8")
        manifest_path.write_text(
            f"{sha256_bytes(version_path.read_bytes())}  VERSION\n"
            f"{sha256_bytes(payload_path.read_bytes())}  runtime_payload.txt\n",
            encoding="utf-8",
        )
        return root

    @staticmethod
    def _no_self_test(_root: Path) -> None:
        return None

    @staticmethod
    def _no_focused_tests(_root: Path) -> None:
        return None

    def test_default_paths_are_host_global_and_rollback_is_outside_discovery(self) -> None:
        paths = default_global_paths(Path("/private/example-home"))
        self.assertEqual(
            paths["installed_root"],
            Path("/private/example-home/.codex/skills/chalxius"),
        )
        self.assertEqual(
            paths["archive_root"],
            Path("/private/example-home/.codex/skill-runtime-archives/chalxius"),
        )
        self.assertEqual(
            paths["rollback_root"],
            Path("/private/example-home/.codex/skill-rollbacks/chalxius-current"),
        )
        self.assertFalse(paths["rollback_root"].is_relative_to(paths["installed_root"].parent))

    def test_only_public_installer_path_has_the_unqualified_name(self) -> None:
        skill_root = Path(__file__).resolve().parents[1]
        self.assertTrue((skill_root / "scripts" / "local_install.py").is_file())
        self.assertTrue(
            (skill_root / "scripts" / "mathgraph" / "_local_install.py").is_file()
        )
        self.assertFalse(
            (skill_root / "scripts" / "mathgraph" / "local_install.py").exists()
        )

    def test_focused_install_regressions_include_semantic_recovery(self) -> None:
        with patch("mathgraph._local_install.subprocess.run") as run:
            run.return_value.returncode = 0
            run.return_value.stderr = ""
            run.return_value.stdout = "OK"
            default_focused_test_runner(Path("/private/example-candidate"))
        command = run.call_args.args[0]
        self.assertIn(
            "test_chx_0812_semantic_recovery.SemanticRecovery0812Tests",
            command,
        )
        self.assertIn(
            "test_chx_095_terminal_frontier_context.TerminalFrontierContextTests",
            command,
        )

    def test_install_archives_prior_and_rotates_one_direct_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            installed = self._runtime(base / "skills" / "chalxius", "0.8.1", "old")
            first_candidate = self._runtime(base / "candidate-one", "0.8.2", "first")
            archive = base / "archives" / "chalxius"
            rollback = base / "rollbacks" / "chalxius-current"

            first = perform_local_install(
                candidate_root=first_candidate,
                installed_root=installed,
                archive_root=archive,
                rollback_root=rollback,
                self_test_runner=self._no_self_test,
                focused_test_runner=self._no_focused_tests,
            )
            self.assertEqual(first["status"], "installed")
            self.assertTrue(first["rollback_available"])
            self.assertEqual((installed / "VERSION").read_text(encoding="utf-8"), "0.8.2\n")
            self.assertEqual((rollback / "VERSION").read_text(encoding="utf-8"), "0.8.1\n")
            self.assertTrue((archive / "by-content").is_dir())
            self.assertTrue((archive / "by-identity").is_dir())

            second_candidate = self._runtime(base / "candidate-two", "0.8.3", "second")
            second = perform_local_install(
                candidate_root=second_candidate,
                installed_root=installed,
                archive_root=archive,
                rollback_root=rollback,
                self_test_runner=self._no_self_test,
                focused_test_runner=self._no_focused_tests,
            )
            self.assertEqual(second["status"], "installed")
            self.assertEqual((installed / "VERSION").read_text(encoding="utf-8"), "0.8.3\n")
            self.assertEqual((rollback / "VERSION").read_text(encoding="utf-8"), "0.8.2\n")
            self.assertEqual(
                sorted(path.name for path in rollback.parent.iterdir()),
                ["chalxius-current"],
            )

    def test_candidate_failure_leaves_the_installed_runtime_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            installed = self._runtime(base / "skills" / "chalxius", "0.8.1", "old")
            candidate = self._runtime(base / "candidate", "0.8.2", "new")

            def reject_candidate(_root: Path) -> None:
                raise ValueError("fixture candidate failure")

            with self.assertRaisesRegex(ValueError, "fixture candidate failure"):
                perform_local_install(
                    candidate_root=candidate,
                    installed_root=installed,
                    archive_root=base / "archives" / "chalxius",
                    rollback_root=base / "rollbacks" / "chalxius-current",
                    self_test_runner=reject_candidate,
                    focused_test_runner=self._no_focused_tests,
                )
            self.assertEqual((installed / "VERSION").read_text(encoding="utf-8"), "0.8.1\n")

    def test_post_swap_failure_restores_the_prior_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            installed = self._runtime(base / "skills" / "chalxius", "0.8.1", "old")
            candidate = self._runtime(base / "candidate", "0.8.2", "new")
            calls = 0

            def fail_after_swap(_root: Path) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise ValueError("fixture installed self-test failure")

            with self.assertRaisesRegex(RuntimeError, "prior installation was restored"):
                perform_local_install(
                    candidate_root=candidate,
                    installed_root=installed,
                    archive_root=base / "archives" / "chalxius",
                    rollback_root=base / "rollbacks" / "chalxius-current",
                    self_test_runner=fail_after_swap,
                    focused_test_runner=self._no_focused_tests,
                )
            self.assertEqual(calls, 2)
            self.assertEqual((installed / "VERSION").read_text(encoding="utf-8"), "0.8.1\n")

    def test_dry_run_never_creates_archives_or_changes_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            installed = self._runtime(base / "skills" / "chalxius", "0.8.1", "old")
            candidate = self._runtime(base / "candidate", "0.8.2", "new")
            archive = base / "archives" / "chalxius"
            rollback = base / "rollbacks" / "chalxius-current"
            result = perform_local_install(
                candidate_root=candidate,
                installed_root=installed,
                archive_root=archive,
                rollback_root=rollback,
                dry_run=True,
                self_test_runner=self._no_self_test,
                focused_test_runner=self._no_focused_tests,
            )
            self.assertEqual(result["status"], "validated_no_install")
            self.assertEqual((installed / "VERSION").read_text(encoding="utf-8"), "0.8.1\n")
            self.assertFalse(archive.exists())
            self.assertFalse(rollback.exists())

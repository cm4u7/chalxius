from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mathgraph.contracts import sha256_bytes
from mathgraph.runtime_archive import archive_runtime, runtime_binding_from_root
from mathgraph.runtime_cutover import perform_cutover


class RuntimeCutoverTests(unittest.TestCase):
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
    def _approved_manifest(root: Path) -> str:
        return sha256_bytes((root / "MANIFEST.sha256").read_bytes())

    def test_cutover_requires_an_explicit_protected_project_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            candidate = self._runtime(
                base / "candidate" / "chalxius-new", "0.6.1", "new"
            )
            installed = self._runtime(
                base / "skills" / "chalxius", "0.6.0", "old"
            )
            with self.assertRaisesRegex(ValueError, "protected project roots"):
                perform_cutover(
                    candidate_root=candidate,
                    installed_root=installed,
                    rollback_root=base / "skills" / "chalxius-rollback",
                    archive_root=base / "skill-runtime-archives" / "chalxius",
                    expected_candidate_manifest_sha256=self._approved_manifest(candidate),
                    dry_run=True,
                    self_test_runner=self._no_self_test,
                )
            self.assertEqual(
                (installed / "VERSION").read_text(encoding="utf-8"), "0.6.0\n"
            )

    def test_install_and_explicit_rollback_both_archive_and_swap_exact_trees(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            candidate = self._runtime(
                base / "candidate" / "chalxius-new", "0.6.1", "new"
            )
            installed = self._runtime(
                base / "skills" / "chalxius", "0.6.0", "old"
            )
            archive = base / "skill-runtime-archives" / "chalxius"
            old_backup = base / "skills" / "chalxius-0.6.0-rollback"
            installed_receipt = perform_cutover(
                candidate_root=candidate,
                installed_root=installed,
                rollback_root=old_backup,
                archive_root=archive,
                expected_candidate_manifest_sha256=self._approved_manifest(candidate),
                confirm_no_protected_projects=True,
                self_test_runner=self._no_self_test,
            )
            self.assertEqual(installed_receipt["status"], "cutover_complete")
            self.assertEqual(
                (installed / "VERSION").read_text(encoding="utf-8"), "0.6.1\n"
            )
            self.assertEqual(
                (old_backup / "VERSION").read_text(encoding="utf-8"), "0.6.0\n"
            )
            self.assertTrue(Path(installed_receipt["archived_installed"]["archive_path"]).is_dir())
            self.assertTrue(installed_receipt["archived_prior"])
            self.assertTrue(
                all(Path(item["archive_path"]).is_dir() for item in installed_receipt["archived_prior"])
            )

            new_backup = base / "skills" / "chalxius-0.6.1-rollback"
            rollback_receipt = perform_cutover(
                candidate_root=old_backup,
                installed_root=installed,
                rollback_root=new_backup,
                archive_root=archive,
                expected_candidate_manifest_sha256=self._approved_manifest(old_backup),
                confirm_no_protected_projects=True,
                operation="rollback",
                self_test_runner=self._no_self_test,
            )
            self.assertEqual(rollback_receipt["operation"], "rollback")
            self.assertEqual(
                (installed / "VERSION").read_text(encoding="utf-8"), "0.6.0\n"
            )
            self.assertEqual(
                (new_backup / "VERSION").read_text(encoding="utf-8"), "0.6.1\n"
            )

    def test_multiversion_project_uses_sealed_history_instead_of_one_live_alias(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            installed = self._runtime(
                base / "skills" / "chalxius", "0.5.0", "historical"
            )
            archive = base / "skill-runtime-archives" / "chalxius"
            historical_binding = runtime_binding_from_root(
                installed,
                archive_root=archive,
            )
            archive_runtime(
                installed,
                historical_binding,
                archive_root=archive,
            )
            installed.rename(base / "historical-source")
            installed = self._runtime(
                base / "skills" / "chalxius", "0.6.0", "current"
            )
            candidate = self._runtime(
                base / "candidate" / "chalxius-new", "0.6.1", "new"
            )
            project = base / "protected-project"
            project.mkdir()

            def multiversion_project(
                _runtime_root: Path,
                _projects: object,
                **_kwargs: object,
            ) -> dict[str, object]:
                return {
                    "projects": [{"project_root": str(project)}],
                    "runtime_bindings": [historical_binding],
                }

            receipt = perform_cutover(
                candidate_root=candidate,
                installed_root=installed,
                rollback_root=base / "skills" / "chalxius-0.6.0-rollback",
                archive_root=archive,
                expected_candidate_manifest_sha256=self._approved_manifest(candidate),
                project_roots=[project],
                self_test_runner=self._no_self_test,
                project_validator=multiversion_project,
            )
            self.assertEqual(receipt["status"], "cutover_complete")
            self.assertEqual(
                (installed / "VERSION").read_text(encoding="utf-8"), "0.6.1\n"
            )
            self.assertEqual(
                [
                    item["runtime_identity_sha256"]
                    for item in receipt["preflight_historical_runtimes"]
                ],
                [historical_binding["runtime_identity_sha256"]],
            )

    def test_post_cutover_failure_restores_the_prior_installation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            candidate = self._runtime(
                base / "candidate" / "chalxius-new", "0.6.1", "new"
            )
            installed = self._runtime(
                base / "skills" / "chalxius", "0.6.0", "old"
            )
            rollback = base / "skills" / "chalxius-rollback"

            def fail_only_after_swap(root: Path) -> None:
                if root == installed:
                    raise ValueError("post-cutover sentinel failure")

            with self.assertRaisesRegex(RuntimeError, "prior installation was restored"):
                perform_cutover(
                    candidate_root=candidate,
                    installed_root=installed,
                    rollback_root=rollback,
                    archive_root=base / "skill-runtime-archives" / "chalxius",
                    expected_candidate_manifest_sha256=self._approved_manifest(candidate),
                    confirm_no_protected_projects=True,
                    self_test_runner=fail_only_after_swap,
                )
            self.assertEqual(
                (installed / "VERSION").read_text(encoding="utf-8"), "0.6.0\n"
            )
            self.assertFalse(rollback.exists())

    def test_post_cutover_project_gate_failure_also_restores_the_prior_installation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            candidate = self._runtime(
                base / "candidate" / "chalxius-new", "0.6.1", "new"
            )
            installed = self._runtime(
                base / "skills" / "chalxius", "0.6.0", "old"
            )
            rollback = base / "skills" / "chalxius-rollback"

            def fail_postflight(runtime_root: Path, _projects: object, **_kwargs: object) -> dict[str, object]:
                if runtime_root == installed:
                    raise ValueError("post-cutover project sentinel failure")
                return {"projects": [], "runtime_bindings": []}

            with self.assertRaisesRegex(RuntimeError, "prior installation was restored"):
                perform_cutover(
                    candidate_root=candidate,
                    installed_root=installed,
                    rollback_root=rollback,
                    archive_root=base / "skill-runtime-archives" / "chalxius",
                    expected_candidate_manifest_sha256=self._approved_manifest(candidate),
                    confirm_no_protected_projects=True,
                    self_test_runner=self._no_self_test,
                    project_validator=fail_postflight,
                )
            self.assertEqual(
                (installed / "VERSION").read_text(encoding="utf-8"), "0.6.0\n"
            )
            self.assertFalse(rollback.exists())

    def test_candidate_with_an_unexpected_file_is_rejected_before_cutover(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            candidate = self._runtime(
                base / "candidate" / "chalxius-new", "0.6.1", "new"
            )
            (candidate / "unexpected.txt").write_text("extra\n", encoding="utf-8")
            installed = self._runtime(
                base / "skills" / "chalxius", "0.6.0", "old"
            )
            with self.assertRaisesRegex(ValueError, "file set"):
                perform_cutover(
                    candidate_root=candidate,
                    installed_root=installed,
                    rollback_root=base / "skills" / "chalxius-rollback",
                    archive_root=base / "skill-runtime-archives" / "chalxius",
                    expected_candidate_manifest_sha256=self._approved_manifest(candidate),
                    confirm_no_protected_projects=True,
                    self_test_runner=self._no_self_test,
                )
            self.assertEqual(
                (installed / "VERSION").read_text(encoding="utf-8"), "0.6.0\n"
            )

    def test_cutover_rejects_a_missing_candidate_approval_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            candidate = self._runtime(
                base / "candidate" / "chalxius-new", "0.6.1", "new"
            )
            installed = self._runtime(
                base / "skills" / "chalxius", "0.6.0", "old"
            )
            with self.assertRaisesRegex(ValueError, "approved candidate"):
                perform_cutover(
                    candidate_root=candidate,
                    installed_root=installed,
                    rollback_root=base / "skills" / "chalxius-rollback",
                    archive_root=base / "skill-runtime-archives" / "chalxius",
                    confirm_no_protected_projects=True,
                    self_test_runner=self._no_self_test,
                )
            self.assertEqual(
                (installed / "VERSION").read_text(encoding="utf-8"), "0.6.0\n"
            )


if __name__ == "__main__":
    unittest.main()

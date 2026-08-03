from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from mathgraph.contracts import sha256_bytes
from mathgraph.runtime_archive import archive_runtime, runtime_binding_from_root
from mathgraph.runtime_cutover import (
    build_cutover_project_validation_receipt,
    perform_cutover,
)


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

    @staticmethod
    def _write_json(path: Path, payload: dict[str, object]) -> str:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return sha256_bytes(path.read_bytes())

    def _bounded_receipt(
        self,
        *,
        base: Path,
        candidate: Path,
        installed: Path,
        project: Path,
        archive: Path,
        validator: object,
        deep_audit_required: bool = False,
        deep_validator: object | None = None,
    ) -> tuple[Path, str]:
        prior_identity = runtime_binding_from_root(
            installed,
            archive_root=archive,
        )["runtime_identity_sha256"]
        anchor_path = base / "prior-audit.json"
        anchor_sha256 = self._write_json(
            anchor_path,
            {
                "captured_at": datetime.now(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
                "installed_runtime_identity": prior_identity,
                "cutover": {
                    "preflight_audit_current_ok": True,
                    "postflight_audit_current_ok": True,
                    "protected_project": str(project),
                },
            },
        )
        manifest_sha256 = self._approved_manifest(candidate)
        matrix_path = base / "release-matrix.json"
        matrix_sha256 = self._write_json(
            matrix_path,
            {
                "contract_revision": "chalxius-release-validation-matrix-1",
                "manifest_sha256": manifest_sha256,
                "ok": True,
                "complete_lane_set": True,
                "one_manifest_identity": True,
                "source_unchanged": True,
                "lanes": [
                    {
                        "lane": lane,
                        "manifest_sha256": manifest_sha256,
                        "ok": True,
                        "lane_unchanged": True,
                    }
                    for lane in (
                        "self_test",
                        "full_suite",
                        "aggressive_bug_audit",
                    )
                ],
            },
        )
        request_path = base / "cutover-project-request.json"
        request_sha256 = self._write_json(
            request_path,
            {
                "schema_version": 1,
                "contract_revision": "chalxius-cutover-project-validation-request-1",
                "candidate_manifest_sha256": manifest_sha256,
                "prior_runtime_identity": prior_identity,
                "project_roots": [str(project)],
                "prior_audit_anchor": {
                    "path": str(anchor_path),
                    "sha256": anchor_sha256,
                },
                "release_validation_evidence": [
                    {"path": str(matrix_path), "sha256": matrix_sha256}
                ],
                "change_classification": {
                    "classification_revision": "chalxius-cutover-change-classification-1",
                    "deep_audit_required": deep_audit_required,
                    "changed_paths": ["VERSION", "runtime_payload.txt"],
                    "rationale": "Toy changes do not alter protected-project interpretation.",
                },
                "truth_effect": "none",
            },
        )
        receipt_path = base / "cutover-project-receipt.json"
        build_cutover_project_validation_receipt(
            candidate_root=candidate,
            installed_root=installed,
            archive_root=archive,
            request_path=request_path,
            expected_request_sha256=request_sha256,
            output_path=receipt_path,
            bounded_project_validator=validator,  # type: ignore[arg-type]
            deep_project_validator=(
                deep_validator if deep_validator is not None else validator
            ),  # type: ignore[arg-type]
        )
        return receipt_path, sha256_bytes(receipt_path.read_bytes())

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

    def test_protected_cutover_refuses_implicit_duplicate_full_audits(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            candidate = self._runtime(
                base / "candidate" / "chalxius-new", "0.6.1", "new"
            )
            installed = self._runtime(
                base / "skills" / "chalxius", "0.6.0", "old"
            )
            project = base / "protected-project"
            project.mkdir()
            with self.assertRaisesRegex(ValueError, "prevalidated receipt"):
                perform_cutover(
                    candidate_root=candidate,
                    installed_root=installed,
                    rollback_root=base / "skills" / "chalxius-rollback",
                    archive_root=base / "skill-runtime-archives" / "chalxius",
                    project_roots=[project],
                    expected_candidate_manifest_sha256=self._approved_manifest(candidate),
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
            round_id = "round-20260101T000000Z-1234abcd"
            cards = project / "rounds" / round_id / "task-cards"
            cards.mkdir(parents=True)
            self._write_json(
                cards / "a01.json",
                {"runtime_binding": historical_binding},
            )
            project_validation_calls = 0

            def multiversion_project(
                _runtime_root: Path,
                _projects: object,
                **_kwargs: object,
            ) -> dict[str, object]:
                nonlocal project_validation_calls
                project_validation_calls += 1
                return {
                    "projects": [
                        {
                            "project_root": str(project),
                            "round_states": {round_id: "completed"},
                            "audit_current_ok": True,
                        }
                    ],
                    "runtime_bindings": [historical_binding],
                }

            receipt = perform_cutover(
                candidate_root=candidate,
                installed_root=installed,
                rollback_root=base / "skills" / "chalxius-0.6.0-rollback",
                archive_root=archive,
                expected_candidate_manifest_sha256=self._approved_manifest(candidate),
                project_roots=[project],
                force_full_project_audit=True,
                self_test_runner=self._no_self_test,
                project_validator=multiversion_project,
            )
            self.assertEqual(receipt["status"], "cutover_complete")
            self.assertEqual(project_validation_calls, 1)
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

    def test_bounded_project_receipt_replaces_duplicate_cutover_audits(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            candidate = self._runtime(
                base / "candidate" / "chalxius-new", "0.6.1", "new"
            )
            installed = self._runtime(
                base / "skills" / "chalxius", "0.6.0", "old"
            )
            project = base / "protected-project"
            project.mkdir()
            archive = base / "skill-runtime-archives" / "chalxius"
            validation_calls: list[str] = []

            def bounded_validator(
                runtime_root: Path,
                projects: object,
                **_kwargs: object,
            ) -> dict[str, object]:
                validation_calls.append(str(runtime_root))
                return {
                    "projects": [
                        {"project_root": str(project), "round_states": {}}
                    ],
                    "runtime_bindings": [],
                }

            receipt_path, receipt_sha256 = self._bounded_receipt(
                base=base,
                candidate=candidate,
                installed=installed,
                project=project,
                archive=archive,
                validator=bounded_validator,
            )
            self.assertEqual(validation_calls, [str(candidate)])

            def duplicate_audit_forbidden(
                _runtime_root: Path,
                _projects: object,
                **_kwargs: object,
            ) -> dict[str, object]:
                raise AssertionError("cutover repeated the project audit")

            result = perform_cutover(
                candidate_root=candidate,
                installed_root=installed,
                rollback_root=base / "skills" / "chalxius-rollback",
                archive_root=archive,
                project_roots=[project],
                expected_candidate_manifest_sha256=self._approved_manifest(candidate),
                expected_installed_runtime_identity=runtime_binding_from_root(
                    installed, archive_root=archive
                )["runtime_identity_sha256"],
                project_validation_receipt=receipt_path,
                expected_project_validation_receipt_sha256=receipt_sha256,
                self_test_runner=self._no_self_test,
                project_validator=duplicate_audit_forbidden,
            )
            self.assertEqual(result["status"], "cutover_complete")
            self.assertEqual(
                result["project_validation_receipt"]["sha256"],
                receipt_sha256,
            )
            self.assertEqual(
                result["preflight_projects"][0]["audit_evidence_mode"],
                "bounded_reuse_of_prior_deep_audit",
            )
            self.assertEqual(
                result["postflight_projects"][0]["audit_evidence_mode"],
                "bounded_reuse_of_prior_deep_audit",
            )
            self.assertEqual(validation_calls, [str(candidate)])

    def test_deep_project_validation_runs_once_while_building_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            candidate = self._runtime(
                base / "candidate" / "chalxius-new", "0.6.1", "new"
            )
            installed = self._runtime(
                base / "skills" / "chalxius", "0.6.0", "old"
            )
            project = base / "protected-project"
            project.mkdir()
            archive = base / "skill-runtime-archives" / "chalxius"
            deep_calls: list[str] = []

            def bounded_forbidden(
                _runtime_root: Path,
                _projects: object,
                **_kwargs: object,
            ) -> dict[str, object]:
                raise AssertionError("bounded validator replaced a required deep audit")

            def deep_validator(
                runtime_root: Path,
                _projects: object,
                **_kwargs: object,
            ) -> dict[str, object]:
                deep_calls.append(str(runtime_root))
                return {
                    "projects": [
                        {
                            "project_root": str(project),
                            "round_states": {},
                            "audit_current_ok": True,
                        }
                    ],
                    "runtime_bindings": [],
                }

            receipt_path, receipt_sha256 = self._bounded_receipt(
                base=base,
                candidate=candidate,
                installed=installed,
                project=project,
                archive=archive,
                validator=bounded_forbidden,
                deep_audit_required=True,
                deep_validator=deep_validator,
            )
            self.assertEqual(deep_calls, [str(candidate)])
            result = perform_cutover(
                candidate_root=candidate,
                installed_root=installed,
                rollback_root=base / "skills" / "chalxius-rollback",
                archive_root=archive,
                project_roots=[project],
                expected_candidate_manifest_sha256=self._approved_manifest(candidate),
                project_validation_receipt=receipt_path,
                expected_project_validation_receipt_sha256=receipt_sha256,
                self_test_runner=self._no_self_test,
                project_validator=bounded_forbidden,
            )
            self.assertEqual(result["status"], "cutover_complete")
            self.assertEqual(
                result["preflight_projects"][0]["audit_evidence_mode"],
                "single_prevalidated_deep_audit",
            )
            self.assertEqual(deep_calls, [str(candidate)])

    def test_bounded_project_receipt_rejects_project_drift_before_swap(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            candidate = self._runtime(
                base / "candidate" / "chalxius-new", "0.6.1", "new"
            )
            installed = self._runtime(
                base / "skills" / "chalxius", "0.6.0", "old"
            )
            project = base / "protected-project"
            project.mkdir()
            archive = base / "skill-runtime-archives" / "chalxius"

            def bounded_validator(
                _runtime_root: Path,
                _projects: object,
                **_kwargs: object,
            ) -> dict[str, object]:
                return {
                    "projects": [
                        {"project_root": str(project), "round_states": {}}
                    ],
                    "runtime_bindings": [],
                }

            receipt_path, receipt_sha256 = self._bounded_receipt(
                base=base,
                candidate=candidate,
                installed=installed,
                project=project,
                archive=archive,
                validator=bounded_validator,
            )
            (project / "project.json").write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "changed after validation receipt"):
                perform_cutover(
                    candidate_root=candidate,
                    installed_root=installed,
                    rollback_root=base / "skills" / "chalxius-rollback",
                    archive_root=archive,
                    project_roots=[project],
                    expected_candidate_manifest_sha256=self._approved_manifest(candidate),
                    project_validation_receipt=receipt_path,
                    expected_project_validation_receipt_sha256=receipt_sha256,
                    self_test_runner=self._no_self_test,
                )
            self.assertEqual(
                (installed / "VERSION").read_text(encoding="utf-8"), "0.6.0\n"
            )

    def test_bounded_project_receipt_post_swap_drift_restores_prior_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            candidate = self._runtime(
                base / "candidate" / "chalxius-new", "0.6.1", "new"
            )
            installed = self._runtime(
                base / "skills" / "chalxius", "0.6.0", "old"
            )
            project = base / "protected-project"
            project.mkdir()
            archive = base / "skill-runtime-archives" / "chalxius"

            def bounded_validator(
                _runtime_root: Path,
                _projects: object,
                **_kwargs: object,
            ) -> dict[str, object]:
                return {
                    "projects": [
                        {"project_root": str(project), "round_states": {}}
                    ],
                    "runtime_bindings": [],
                }

            receipt_path, receipt_sha256 = self._bounded_receipt(
                base=base,
                candidate=candidate,
                installed=installed,
                project=project,
                archive=archive,
                validator=bounded_validator,
            )

            def mutate_only_after_swap(runtime_root: Path) -> None:
                if runtime_root == installed:
                    (project / "late-change.json").write_text("{}\n", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "prior installation was restored"):
                perform_cutover(
                    candidate_root=candidate,
                    installed_root=installed,
                    rollback_root=base / "skills" / "chalxius-rollback",
                    archive_root=archive,
                    project_roots=[project],
                    expected_candidate_manifest_sha256=self._approved_manifest(candidate),
                    project_validation_receipt=receipt_path,
                    expected_project_validation_receipt_sha256=receipt_sha256,
                    self_test_runner=mutate_only_after_swap,
                )
            self.assertEqual(
                (installed / "VERSION").read_text(encoding="utf-8"), "0.6.0\n"
            )
            self.assertFalse((base / "skills" / "chalxius-rollback").exists())

    def test_bounded_project_receipt_hash_is_mandatory_and_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            candidate = self._runtime(
                base / "candidate" / "chalxius-new", "0.6.1", "new"
            )
            installed = self._runtime(
                base / "skills" / "chalxius", "0.6.0", "old"
            )
            project = base / "protected-project"
            project.mkdir()
            archive = base / "skill-runtime-archives" / "chalxius"

            def bounded_validator(
                _runtime_root: Path,
                _projects: object,
                **_kwargs: object,
            ) -> dict[str, object]:
                return {
                    "projects": [
                        {"project_root": str(project), "round_states": {}}
                    ],
                    "runtime_bindings": [],
                }

            receipt_path, _ = self._bounded_receipt(
                base=base,
                candidate=candidate,
                installed=installed,
                project=project,
                archive=archive,
                validator=bounded_validator,
            )
            with self.assertRaisesRegex(ValueError, "approved SHA-256"):
                perform_cutover(
                    candidate_root=candidate,
                    installed_root=installed,
                    rollback_root=base / "skills" / "chalxius-rollback",
                    archive_root=archive,
                    project_roots=[project],
                    expected_candidate_manifest_sha256=self._approved_manifest(candidate),
                    project_validation_receipt=receipt_path,
                    expected_project_validation_receipt_sha256="0" * 64,
                    dry_run=True,
                    self_test_runner=self._no_self_test,
                )

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

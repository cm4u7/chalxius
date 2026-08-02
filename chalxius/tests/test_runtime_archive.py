from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mathgraph.contracts import sha256_bytes, sha256_json
from mathgraph.runtime_archive import (
    RUNTIME_ARCHIVE_ENV,
    archive_runtime,
    historical_archive_path,
    historical_registry_path,
    read_json_file_nofollow,
    resolve_historical_runtime,
    runtime_binding_from_root,
)


class RuntimeArchiveTests(unittest.TestCase):
    def _legacy_runtime(
        self,
        root: Path,
        *,
        bound_skill_root: Path | None = None,
    ) -> tuple[dict[str, object], Path]:
        root.mkdir(parents=True)
        version_path = root / "VERSION"
        payload_path = root / "payload.txt"
        manifest_path = root / "MANIFEST.sha256"
        version_path.write_text("0.5.0-test\n", encoding="utf-8")
        payload_path.write_text("historical payload\n", encoding="utf-8")
        manifest_path.write_text(
            f"{sha256_bytes(version_path.read_bytes())}  VERSION\n"
            f"{sha256_bytes(payload_path.read_bytes())}  payload.txt\n",
            encoding="utf-8",
        )
        semantic = {
            "schema_version": 1,
            "skill_root": str(bound_skill_root or root),
            "skill_version": "0.5.0-test",
            "version_file_sha256": sha256_bytes(version_path.read_bytes()),
            "manifest_file_sha256": sha256_bytes(manifest_path.read_bytes()),
            "worker_ledger_contract": "exact_task_card_runtime_binding_required",
        }
        return (
            {**semantic, "runtime_identity_sha256": sha256_json(semantic)},
            payload_path,
        )

    def test_bound_root_rejects_a_symlink_in_any_ancestor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            real_parent = base / "real"
            alias_parent = base / "alias"
            real_root = real_parent / "chalxius"
            alias_root = alias_parent / "chalxius"
            binding, _ = self._legacy_runtime(
                real_root, bound_skill_root=alias_root
            )
            alias_parent.symlink_to(real_parent, target_is_directory=True)
            with patch.dict(
                os.environ,
                {RUNTIME_ARCHIVE_ENV: str(base / "host-archive")},
            ):
                with self.assertRaisesRegex(ValueError, "traverses a symlink"):
                    resolve_historical_runtime(binding)

    def test_original_bound_root_rehashes_every_manifest_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            runtime_root = base / "original" / "chalxius"
            binding, payload = self._legacy_runtime(runtime_root)
            payload.write_text("tampered but identity files unchanged\n", encoding="utf-8")
            with patch.dict(
                os.environ,
                {RUNTIME_ARCHIVE_ENV: str(base / "host-archive")},
            ):
                with self.assertRaisesRegex(ValueError, "no valid content-addressed"):
                    resolve_historical_runtime(binding)

    def test_source_and_archive_roots_reject_ancestor_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            source_parent = base / "source-real"
            source_root = source_parent / "chalxius"
            binding, _ = self._legacy_runtime(source_root)
            source_alias_parent = base / "source-alias"
            source_alias_parent.symlink_to(source_parent, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "traverses a symlink"):
                archive_runtime(
                    source_alias_parent / "chalxius",
                    binding,
                    archive_root=base / "host-archive",
                )

            archive_real = base / "archive-real"
            archive_real.mkdir()
            archive_alias = base / "archive-alias"
            archive_alias.symlink_to(archive_real, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "traverses a symlink"):
                archive_runtime(
                    source_root,
                    binding,
                    archive_root=archive_alias / "chalxius",
                )

    def test_registry_and_archive_are_both_required_and_revalidated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            archive_root = base / "host-archive"
            source_root = base / "source" / "chalxius"
            binding, _ = self._legacy_runtime(source_root)
            with patch.dict(os.environ, {RUNTIME_ARCHIVE_ENV: str(archive_root)}):
                receipt = archive_runtime(source_root, binding)
                source_root.joinpath("VERSION").write_text(
                    "0.6.1-drifted\n", encoding="utf-8"
                )
                resolved = resolve_historical_runtime(binding)
                self.assertEqual(
                    resolved["resolution"],
                    "content_addressed_historical_archive",
                )
                registry_path = Path(receipt["registry_path"])
                registry_path.chmod(0o600)
                registry = json.loads(registry_path.read_text(encoding="utf-8"))
                registry["archive_tree_sha256"] = "0" * 64
                registry_path.write_text(
                    json.dumps(registry, sort_keys=True) + "\n", encoding="utf-8"
                )
                registry_path.chmod(0o400)
                with self.assertRaisesRegex(ValueError, "no valid content-addressed"):
                    resolve_historical_runtime(binding)

    def test_writable_archive_object_is_rejected_even_when_bytes_match(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            archive_root = base / "host-archive"
            source_root = base / "source" / "chalxius"
            binding, _ = self._legacy_runtime(source_root)
            with patch.dict(os.environ, {RUNTIME_ARCHIVE_ENV: str(archive_root)}):
                archive_runtime(source_root, binding)
                source_root.joinpath("VERSION").write_text(
                    "0.6.1-drifted\n", encoding="utf-8"
                )
                historical_archive_path(binding).chmod(0o700)
                with self.assertRaisesRegex(ValueError, "no valid content-addressed"):
                    resolve_historical_runtime(binding)

    def test_archive_rejects_internal_symlink_and_hardlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            archive_root = base / "host-archive"
            source_root = base / "source-one" / "chalxius"
            binding, _ = self._legacy_runtime(source_root)
            with patch.dict(os.environ, {RUNTIME_ARCHIVE_ENV: str(archive_root)}):
                archive_runtime(source_root, binding)
                source_root.joinpath("VERSION").write_text(
                    "0.6.1-drifted\n", encoding="utf-8"
                )
                object_root = historical_archive_path(binding)
                payload = object_root / "payload.txt"
                object_root.chmod(0o700)
                payload.unlink()
                payload.symlink_to(base / "outside-payload")
                with self.assertRaisesRegex(ValueError, "no valid content-addressed"):
                    resolve_historical_runtime(binding)

            second_archive = base / "host-archive-two"
            second_source = base / "source-two" / "chalxius"
            second_binding, _ = self._legacy_runtime(second_source)
            with patch.dict(os.environ, {RUNTIME_ARCHIVE_ENV: str(second_archive)}):
                archive_runtime(second_source, second_binding)
                second_source.joinpath("VERSION").write_text(
                    "0.6.1-drifted\n", encoding="utf-8"
                )
                object_root = historical_archive_path(second_binding)
                payload = object_root / "payload.txt"
                duplicate = base / "hardlink-source"
                duplicate.write_bytes(payload.read_bytes())
                object_root.chmod(0o700)
                payload.unlink()
                os.link(duplicate, payload)
                payload.chmod(0o400)
                object_root.chmod(0o500)
                with self.assertRaisesRegex(ValueError, "no valid content-addressed"):
                    resolve_historical_runtime(second_binding)

    def test_schema2_locator_must_match_current_host_trust_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            source_root = base / "skills" / "chalxius"
            self._legacy_runtime(source_root)
            first_root = base / "host-one"
            second_root = base / "host-two"
            binding = runtime_binding_from_root(
                source_root, archive_root=first_root
            )
            archive_runtime(source_root, binding, archive_root=first_root)
            source_root.joinpath("VERSION").write_text(
                "0.6.1-drifted\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "differs from the host trust root"):
                resolve_historical_runtime(binding, archive_root=second_root)

    def test_cli_json_inputs_reject_symlinked_files_and_ancestors(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            real_parent = base / "real"
            real_parent.mkdir()
            input_path = real_parent / "binding.json"
            input_path.write_text("{}\n", encoding="utf-8")
            leaf_alias = real_parent / "leaf-alias.json"
            leaf_alias.symlink_to(input_path)
            with self.assertRaisesRegex(ValueError, "missing or unsafe"):
                read_json_file_nofollow(leaf_alias, label="test input")

            ancestor_alias = base / "ancestor-alias"
            ancestor_alias.symlink_to(real_parent, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "traverses a symlink"):
                read_json_file_nofollow(
                    ancestor_alias / "binding.json", label="test input"
                )

    def test_archive_paths_and_registry_are_sealed_and_outside_skills(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            runtime_root = base / "skills" / "chalxius"
            self._legacy_runtime(runtime_root)
            archive_root = base / "skill-runtime-archives" / "chalxius"
            binding = runtime_binding_from_root(
                runtime_root, archive_root=archive_root
            )
            receipt = archive_runtime(
                runtime_root, binding, archive_root=archive_root
            )
            object_root = historical_archive_path(
                binding, archive_root=archive_root
            )
            registry_path = historical_registry_path(
                binding, archive_root=archive_root
            )
            self.assertFalse(str(object_root).startswith(str(base / "skills") + "/"))
            self.assertEqual(receipt["registry_path"], str(registry_path))
            self.assertEqual(os.lstat(object_root).st_mode & 0o222, 0)
            self.assertEqual(os.lstat(registry_path).st_mode & 0o222, 0)


if __name__ == "__main__":
    unittest.main()

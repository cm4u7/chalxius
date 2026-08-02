from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from mathgraph.runtime_compatibility import (
    RuntimeCompatibilityError,
    changed_path_inventory_sha256,
    compute_protected_tree,
    validate_runtime_compatibility,
)


class RuntimeCompatibilityClosureTests(unittest.TestCase):
    def _fixture(self, root: Path) -> dict:
        (root / "scripts" / "mathgraph").mkdir(parents=True)
        (root / "scripts" / "mathgraph" / "a.py").write_text(
            "A = 1\n", encoding="utf-8"
        )
        (root / "scripts" / "public").write_text("public\n", encoding="utf-8")
        protected_paths = ["scripts/mathgraph/**", "scripts/public"]
        status = compute_protected_tree(root, protected_paths)
        changed_paths = [
            "scripts/mathgraph/a.py",
            "scripts/public",
        ]
        return {
            "baseline": "chalxius-0.4.3",
            "protected_paths": protected_paths,
            "protected_file_count": status["protected_file_count"],
            "protected_tree_sha256": status["protected_tree_sha256"],
            "changed_from_0.4.3_runtime_paths": changed_paths,
            "changed_path_inventory_sha256": changed_path_inventory_sha256(
                changed_paths
            ),
        }

    def test_exact_closure_is_shared_by_validator_and_release_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            compatibility = self._fixture(root)
            status = validate_runtime_compatibility(root, compatibility)
            self.assertEqual(status["protected_file_count"], 2)
            self.assertEqual(status["status"], "current")

    def test_new_runtime_file_fails_stale_count_and_digest(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            compatibility = self._fixture(root)
            (root / "scripts" / "mathgraph" / "new.py").write_text(
                "NEW = True\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(
                RuntimeCompatibilityError, "protected_file_count drifted"
            ):
                validate_runtime_compatibility(root, compatibility)

    def test_content_drift_fails_stale_digest_with_same_file_count(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            compatibility = self._fixture(root)
            (root / "scripts" / "mathgraph" / "a.py").write_text(
                "A = 2\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(
                RuntimeCompatibilityError, "protected_tree_sha256 drifted"
            ):
                validate_runtime_compatibility(root, compatibility)

    def test_changed_path_cannot_escape_protected_closure(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            compatibility = self._fixture(root)
            compatibility["changed_from_0.4.3_runtime_paths"].append("README.md")
            compatibility["changed_from_0.4.3_runtime_paths"].sort()
            with self.assertRaisesRegex(
                RuntimeCompatibilityError, "outside the protected closure"
            ):
                validate_runtime_compatibility(root, compatibility)

    def test_changed_path_inventory_fails_stale_digest(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            compatibility = self._fixture(root)
            compatibility["changed_from_0.4.3_runtime_paths"].pop()
            with self.assertRaisesRegex(
                RuntimeCompatibilityError, "changed path inventory digest drifted"
            ):
                validate_runtime_compatibility(root, compatibility)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink support required")
    def test_symlink_in_protected_tree_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            compatibility = self._fixture(root)
            os.symlink(
                root / "scripts" / "mathgraph" / "a.py",
                root / "scripts" / "mathgraph" / "alias.py",
            )
            with self.assertRaisesRegex(RuntimeCompatibilityError, "symlink"):
                compute_protected_tree(root, compatibility["protected_paths"])

    def test_metadata_round_trip_is_json_serializable(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            compatibility = self._fixture(root)
            json.dumps(validate_runtime_compatibility(root, compatibility))


if __name__ == "__main__":
    unittest.main()

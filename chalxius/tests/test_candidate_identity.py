from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from candidate_identity import project_candidate_identity
from mathgraph.contracts import sha256_bytes


class CandidateIdentityTests(unittest.TestCase):
    @staticmethod
    def _runtime(root: Path, *, version: str, payload: str) -> Path:
        root.mkdir(parents=True)
        version_path = root / "VERSION"
        payload_path = root / "payload.txt"
        version_path.write_text(version + "\n", encoding="utf-8")
        payload_path.write_text(payload + "\n", encoding="utf-8")
        (root / "MANIFEST.sha256").write_text(
            "".join(
                [
                    f"{sha256_bytes(version_path.read_bytes())}  VERSION\n",
                    f"{sha256_bytes(payload_path.read_bytes())}  payload.txt\n",
                ]
            ),
            encoding="utf-8",
        )
        return root

    def test_exact_installed_baseline_does_not_trust_path_hint(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            candidate = self._runtime(
                base / "chalxius-0.8.6-worktree" / "chalxius",
                version="0.9.6",
                payload="same",
            )
            installed = self._runtime(
                base / "skills" / "chalxius",
                version="0.9.6",
                payload="same",
            )
            result = project_candidate_identity(candidate, installed)
            self.assertEqual(
                result["selection_status"], "exact_installed_baseline"
            )
            self.assertTrue(result["candidate_manifest_valid"])
            self.assertTrue(result["manifest_identity_matches_installed"])
            self.assertEqual(
                result["path_version_hints"]["hints"][0]["version_hint"],
                "0.8.6",
            )
            self.assertEqual(
                result["path_version_hints"]["selection_effect"], "none"
            )

    def test_same_version_candidate_changes_are_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            candidate = self._runtime(
                base / "candidate", version="0.9.6", payload="new"
            )
            installed = self._runtime(
                base / "installed", version="0.9.6", payload="old"
            )
            result = project_candidate_identity(candidate, installed)
            self.assertEqual(
                result["selection_status"],
                "same_version_candidate_changes_present",
            )
            self.assertTrue(result["version_matches_installed"])
            self.assertFalse(result["manifest_identity_matches_installed"])
            self.assertEqual(
                result["manifest_difference"]["content_changed_paths"],
                ["payload.txt"],
            )

    def test_manifest_drift_is_visible_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            candidate = self._runtime(
                base / "candidate", version="0.9.6", payload="before"
            )
            installed = self._runtime(
                base / "installed", version="0.9.6", payload="before"
            )
            (candidate / "payload.txt").write_text(
                "after\n", encoding="utf-8"
            )
            result = project_candidate_identity(candidate, installed)
            self.assertEqual(
                result["selection_status"], "candidate_manifest_invalid"
            )
            self.assertFalse(result["candidate_manifest_valid"])
            self.assertIn("manifest", result["candidate_manifest_error"].lower())


if __name__ == "__main__":
    unittest.main()

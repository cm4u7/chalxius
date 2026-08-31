from __future__ import annotations

import json
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
UPDATER = REPOSITORY_ROOT / "tools" / "update_release_metadata.py"


@unittest.skipUnless(
    UPDATER.is_file(),
    "repository-only release authoring tool is not part of an installed skill",
)
class ReleaseMetadataUpdateTests(unittest.TestCase):
    def _fixture(self, root: Path) -> Path:
        skill = root / "chalxius"
        (skill / "assets").mkdir(parents=True)
        (skill / "VERSION").write_text("1.0.8\n", encoding="utf-8")
        (skill / "INHERITANCE.lock.json").write_text(
            json.dumps(
                {
                    "schema_version": 3,
                    "skill_name": "chalxius",
                    "version": "1.0.8",
                    "release_codename": "Old",
                    "release_display_name": "Chalxius 1.0.8 — Old",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (skill / "SKILL.md").write_text(
            "---\nname: chalxius\n---\n\n# Chalxius 1.0.8 — Old\n",
            encoding="utf-8",
        )
        (skill / "assets" / "DEPLOY_PROMPT.txt").write_text(
            "Chalxius 1.0.8 — Old\n\nThe 1.0.8 runtime coordinates work.\n",
            encoding="utf-8",
        )
        (skill / "MANIFEST.sha256").write_text("stale\n", encoding="utf-8")
        return skill

    def _run(self, skill: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "python3",
                "-B",
                str(UPDATER),
                "--skill-root",
                str(skill),
                "--version",
                "1.0.9",
                "--codename",
                "Working Memory Maintenance",
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_updates_all_identity_projections_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            skill = self._fixture(Path(temporary))
            modes = {
                path: stat.S_IMODE(path.stat().st_mode)
                for path in (
                    skill / "VERSION",
                    skill / "INHERITANCE.lock.json",
                    skill / "SKILL.md",
                    skill / "assets" / "DEPLOY_PROMPT.txt",
                    skill / "MANIFEST.sha256",
                )
            }
            first = self._run(skill)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual((skill / "VERSION").read_text(), "1.0.9\n")
            lock = json.loads((skill / "INHERITANCE.lock.json").read_text())
            self.assertEqual(lock["release_codename"], "Working Memory Maintenance")
            self.assertIn(
                "# Chalxius 1.0.9 — Working Memory Maintenance",
                (skill / "SKILL.md").read_text(),
            )
            deploy = (skill / "assets" / "DEPLOY_PROMPT.txt").read_text()
            self.assertTrue(deploy.startswith("Chalxius 1.0.9 — Working Memory Maintenance"))
            self.assertIn("The current runtime coordinates work.", deploy)
            self.assertEqual(
                modes,
                {path: stat.S_IMODE(path.stat().st_mode) for path in modes},
            )
            before = {path: path.read_bytes() for path in modes}
            second = self._run(skill)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(json.loads(second.stdout)["changed_paths"], [])
            self.assertEqual(before, {path: path.read_bytes() for path in modes})

    def test_invalid_anchor_fails_before_any_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            skill = self._fixture(Path(temporary))
            skill_md = skill / "SKILL.md"
            skill_md.write_text(
                skill_md.read_text() + "# Chalxius 0.0.0 — Duplicate\n",
                encoding="utf-8",
            )
            tracked = [
                skill / "VERSION",
                skill / "INHERITANCE.lock.json",
                skill_md,
                skill / "assets" / "DEPLOY_PROMPT.txt",
                skill / "MANIFEST.sha256",
            ]
            before = {path: path.read_bytes() for path in tracked}
            result = self._run(skill)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(before, {path: path.read_bytes() for path in tracked})

    def test_manifest_tree_preflight_fails_before_identity_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            skill = self._fixture(Path(temporary))
            cache = skill / "scripts" / "__pycache__"
            cache.mkdir(parents=True)
            tracked = [
                skill / "VERSION",
                skill / "INHERITANCE.lock.json",
                skill / "SKILL.md",
                skill / "assets" / "DEPLOY_PROMPT.txt",
                skill / "MANIFEST.sha256",
            ]
            before = {path: path.read_bytes() for path in tracked}
            result = self._run(skill)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("cache directory", result.stderr)
            self.assertEqual(before, {path: path.read_bytes() for path in tracked})


if __name__ == "__main__":
    unittest.main()

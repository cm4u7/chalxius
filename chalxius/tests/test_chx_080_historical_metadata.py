from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from mathgraph.store import MathGraphStore
from mathgraph.v5_lifecycle import V5LifecycleManager


class CHX080HistoricalMetadataTests(unittest.TestCase):
    def test_writable_terminal_directories_do_not_replace_file_seal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "terminal"
            files = root / "artifacts"
            files.mkdir(parents=True)
            payload = files / "return.json"
            payload.write_text("{}\n", encoding="utf-8")
            os.chmod(root, 0o700)
            os.chmod(files, 0o700)
            os.chmod(payload, 0o400)
            inventory = V5LifecycleManager._validate_readonly_tree(root)
            self.assertEqual(len(inventory), 3)

            os.chmod(payload, 0o600)
            with self.assertRaisesRegex(ValueError, "sealed tree became writable"):
                V5LifecycleManager._validate_readonly_tree(root)

    def test_campaign_inputs_are_preserved_but_not_campaign_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = MathGraphStore(root)
            store.initialize(
                project_id="chx-080-campaign-inputs",
                title="Historical campaign input compatibility",
                workflow_evidence_version=5,
            )
            inputs = root / "campaigns" / "inputs"
            inputs.mkdir(parents=True)
            marker = inputs / "pro-note.json"
            marker.write_text("{\"kind\": \"advisory\"}\n", encoding="utf-8")
            campaign_id = "campaign-0123456789ab"
            (root / "campaigns" / campaign_id).mkdir()
            self.assertEqual(store.campaigns().campaign_ids(), [campaign_id])
            self.assertTrue(marker.exists())


if __name__ == "__main__":
    unittest.main()

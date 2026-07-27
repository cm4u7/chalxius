from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mathgraph.computations import ExperimentManager
from mathgraph.contracts import sha256_json
from mathgraph.event_ledger import ExperimentEventLedger


class HardCapTests(unittest.TestCase):
    def test_event_exact_limit_and_limit_plus_one_are_atomic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "events.jsonl"
            caps = {
                "max_experiment_worker_event_count": 1,
                "max_experiment_event_count_total": 1,
                "max_experiment_event_bytes_each": 4096,
                "max_experiment_event_bytes_total": 4096,
            }
            ledger = ExperimentEventLedger(path, hard_caps=caps)
            semantic = {"event": "heartbeat", "value": 1}
            first = {**semantic, "event_id": sha256_json(semantic)}
            ledger.mutate(lambda session: session.append(first))
            exact = path.read_bytes()

            # Caller-level idempotence checks precede append and therefore stay
            # valid even when every cap is already exact.
            found = ledger.mutate(lambda session: session.find(first["event_id"]))
            self.assertEqual(found, first)
            self.assertEqual(path.read_bytes(), exact)

            second_semantic = {"event": "heartbeat", "value": 2}
            second = {
                **second_semantic,
                "event_id": sha256_json(second_semantic),
            }
            with self.assertRaisesRegex(ValueError, "hard cap"):
                ledger.mutate(lambda session: session.append(second))
            self.assertEqual(path.read_bytes(), exact)

    def test_checkpoint_inventory_exact_and_limit_plus_one(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            root = directory / "checkpoints"
            root.mkdir()
            (root / "one.bin").write_bytes(b"1234")
            caps = {
                "max_checkpoint_files": 1,
                "max_checkpoint_bytes_each": 4,
                "max_checkpoint_bytes_total": 4,
            }
            inventory = ExperimentManager._checkpoint_inventory(directory, caps)
            self.assertEqual(inventory["file_count"], 1)
            self.assertEqual(inventory["bytes_total"], 4)
            (root / "two.bin").write_bytes(b"x")
            with self.assertRaisesRegex(ValueError, "file-count hard cap"):
                ExperimentManager._checkpoint_inventory(directory, caps)


if __name__ == "__main__":
    unittest.main()

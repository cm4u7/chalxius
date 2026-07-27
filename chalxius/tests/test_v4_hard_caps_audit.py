from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mathgraph.computations import ExperimentManager
from mathgraph.contracts import sha256_json
from mathgraph.event_ledger import INDEX_FILENAME


class HardCapAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.experiment_id = "experiment-0123456789abcdef"
        self.directory = (
            self.root / "work" / "experiments" / self.experiment_id
        )
        (self.directory / "checkpoints").mkdir(parents=True)
        self.caps = {
            "max_experiment_worker_event_count": 8,
            "max_experiment_event_count_total": 16,
            "max_experiment_event_bytes_each": 4096,
            "max_experiment_event_bytes_total": 16384,
            "max_checkpoint_files": 2,
            "max_checkpoint_bytes_each": 16,
            "max_checkpoint_bytes_total": 32,
        }
        self.card = {"work_dir_relpath": "work", "hard_caps": self.caps}

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _write_event(self, semantic: dict) -> None:
        payload = {**semantic, "event_id": sha256_json(semantic)}
        (self.directory / "events.jsonl").write_bytes(
            (json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n").encode()
        )

    def test_audit_is_read_only_and_binds_checkpoint(self) -> None:
        checkpoint = self.directory / "checkpoints" / "one.bin"
        checkpoint.write_bytes(b"1234")
        semantic = {
            "event": "checkpoint",
            "checkpoint_path": "checkpoints/one.bin",
            "checkpoint_sha256": ExperimentManager._stream_sha256(checkpoint),
            "checkpoint_bytes": 4,
        }
        self._write_event(semantic)
        result = ExperimentManager(self.root).audit_hard_caps(
            task_card=self.card, experiment_id=self.experiment_id
        )
        self.assertTrue(result["current_ok"], result["errors"])
        self.assertFalse((self.directory / INDEX_FILENAME).exists())

    def test_audit_rejects_noncanonical_and_orphan_checkpoint(self) -> None:
        semantic = {"event": "heartbeat", "value": 1}
        payload = {**semantic, "event_id": sha256_json(semantic)}
        (self.directory / "events.jsonl").write_text(
            json.dumps(payload, sort_keys=False) + "\n", encoding="utf-8"
        )
        (self.directory / "checkpoints" / "orphan.bin").write_bytes(b"x")
        result = ExperimentManager(self.root).audit_hard_caps(
            task_card=self.card, experiment_id=self.experiment_id
        )
        self.assertFalse(result["current_ok"])
        self.assertTrue(any("not canonical" in item for item in result["errors"]))
        self.assertTrue(any("not registered" in item for item in result["errors"]))
        self.assertFalse((self.directory / INDEX_FILENAME).exists())


if __name__ == "__main__":
    unittest.main()

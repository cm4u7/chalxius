"""CHX-107: aggregate inspection is project-owned and writer-stable."""

from __future__ import annotations

import fcntl
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from mathgraph.store import MathGraphStore
from mathgraph.v5_lifecycle import RoundInspectionContext


class CHX107SnapshotBoundInspectionTests(unittest.TestCase):
    def _store(self, parent: Path, name: str) -> MathGraphStore:
        store = MathGraphStore(parent / name)
        store.initialize(
            project_id=name,
            title=name,
            workflow_evidence_version=5,
        )
        return store

    def test_snapshot_lock_excludes_a_cross_process_style_exclusive_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary), "snapshot-exclusion")
            with store.snapshot_lock():
                descriptor = os.open(store.lock_path, os.O_RDWR)
                try:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(
                            descriptor,
                            fcntl.LOCK_EX | fcntl.LOCK_NB,
                        )
                finally:
                    os.close(descriptor)

    def test_snapshot_lock_is_reentrant_under_the_writer_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary), "snapshot-reentrant")
            with store.v5_mutation_lock(command="test-snapshot-reentrant"):
                with store.snapshot_lock():
                    self.assertEqual(store._lock_depth, 1)

    def test_mutation_cannot_begin_inside_snapshot_read(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary), "snapshot-no-upgrade")
            with store.snapshot_lock():
                with self.assertRaisesRegex(
                    ValueError,
                    "cannot begin inside a snapshot read",
                ):
                    with store.v5_mutation_lock(
                        command="test-snapshot-no-upgrade"
                    ):
                        self.fail("mutation lock unexpectedly acquired")

    def test_context_rejects_cross_project_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self._store(root, "owner-first")
            second = self._store(root, "owner-second")
            inspection = RoundInspectionContext()

            self.assertEqual(
                first.v5_lifecycle().research_records(
                    _inspection_context=inspection
                ),
                [],
            )
            with self.assertRaisesRegex(ValueError, "different project root"):
                second.v5_lifecycle().research_records(
                    _inspection_context=inspection
                )

    def test_public_audits_hold_the_snapshot_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary), "audit-lock")
            lifecycle = store.v5_lifecycle()
            entered = 0

            @contextmanager
            def observed_lock():
                nonlocal entered
                entered += 1
                yield

            with patch.object(store, "snapshot_lock", observed_lock):
                with patch.object(
                    lifecycle,
                    "_audit_snapshot_bound",
                    return_value="audit-result",
                ):
                    self.assertEqual(lifecycle.audit(), "audit-result")
                with patch.object(
                    lifecycle,
                    "_fact_evidence_audit_snapshot_bound",
                    return_value={"ok": True},
                ):
                    self.assertEqual(
                        lifecycle.fact_evidence_audit(),
                        {"ok": True},
                    )
            self.assertEqual(entered, 2)


if __name__ == "__main__":
    unittest.main()

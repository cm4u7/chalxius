"""CHX-103: empty task authority must not open the full Fact closure."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mathgraph.store import MathGraphStore
from mathgraph.v5_lifecycle import RoundInspectionContext


class CHX103EmptyAuthorityGateTests(unittest.TestCase):
    @staticmethod
    def _store(root: Path, project_id: str) -> MathGraphStore:
        store = MathGraphStore(root)
        store.initialize(
            project_id=project_id,
            title="Task authority applicability fixture",
            workflow_evidence_version=5,
        )
        return store

    def test_empty_authority_never_reads_active_or_revoked_facts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(
                Path(temporary).resolve(),
                "chx-103-empty-authority",
            )
            lifecycle = store.v5_lifecycle()
            inspection = RoundInspectionContext()
            research = {
                "research_id": "memory-" + "1" * 64,
                "dependencies": [],
                "metadata": {},
            }

            with (
                patch.object(
                    lifecycle,
                    "active_fact_paths",
                    side_effect=AssertionError(
                        "empty authority reconstructed active Facts"
                    ),
                ) as active_fact_paths,
                patch.object(
                    lifecycle,
                    "revoked_fact_ids",
                    side_effect=AssertionError(
                        "empty authority reconstructed revocations"
                    ),
                ) as revoked_fact_ids,
            ):
                snapshot = lifecycle._task_authority_snapshot(
                    research,
                    _inspection_context=inspection,
                )

            active_fact_paths.assert_not_called()
            revoked_fact_ids.assert_not_called()
            self.assertEqual(snapshot["fact_bindings"], [])
            self.assertIsNone(snapshot["attack_target"])
            self.assertEqual(snapshot["capabilities"], [])

    def test_nonempty_authority_retains_complete_context_aware_reads(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            store = self._store(root, "chx-103-nonempty-authority")
            lifecycle = store.v5_lifecycle()
            inspection = RoundInspectionContext()
            fact_id = "fact-" + "2" * 64
            fact_path = root / "authority-fixture.md"
            fact_path.write_text("fixture Fact bytes\n", encoding="utf-8")
            research = {
                "research_id": "memory-" + "3" * 64,
                "dependencies": [fact_id],
                "metadata": {},
            }
            interface = {"fact_id": fact_id, "truth_effect": "none"}

            with (
                patch.object(
                    lifecycle,
                    "active_fact_paths",
                    return_value={fact_id: fact_path},
                ) as active_fact_paths,
                patch.object(
                    lifecycle,
                    "revoked_fact_ids",
                    return_value=set(),
                ) as revoked_fact_ids,
                patch.object(
                    store,
                    "statement_interface",
                    return_value=interface,
                ) as statement_interface,
            ):
                snapshot = lifecycle._task_authority_snapshot(
                    research,
                    _inspection_context=inspection,
                )

            active_fact_paths.assert_called_once_with(
                _inspection_context=inspection
            )
            revoked_fact_ids.assert_called_once_with(
                _inspection_context=inspection
            )
            statement_interface.assert_called_once_with(
                fact_id,
                materialize=False,
                _inspection_context=inspection,
            )
            self.assertEqual(snapshot["fact_bindings"][0]["status"], "active")
            self.assertEqual(
                snapshot["fact_bindings"][0]["statement_interface"],
                interface,
            )


if __name__ == "__main__":
    unittest.main()

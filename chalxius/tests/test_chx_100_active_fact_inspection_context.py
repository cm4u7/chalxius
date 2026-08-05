"""Regression contract for one V5 active-Fact reconstruction per inspection."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from mathgraph.contracts import sha256_bytes
from mathgraph.markdown import serialize_fact
from mathgraph.model import Fact
from mathgraph.store import MathGraphStore
from mathgraph.v5_lifecycle import RoundInspectionContext


class CHX100ActiveFactInspectionContextTests(unittest.TestCase):
    @staticmethod
    def _tree_snapshot(root: Path) -> dict[str, str]:
        return {
            path.relative_to(root).as_posix(): sha256_bytes(path.read_bytes())
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }

    def test_store_fact_read_apis_share_one_v5_active_fact_reconstruction(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve() / "project"
            store = MathGraphStore(root)
            store.initialize(
                project_id="chx-100-active-fact-cache",
                title="Active Fact inspection cache fixture",
                workflow_evidence_version=5,
            )
            facts = [
                Fact(
                    problem_id=store.project_id(),
                    author="fixture",
                    predecessors=[],
                    statement=f"[CLAIM:CACHE_{index}] Cached Fact {index} holds.",
                    proof=f"Fixture proof {index}.",
                )
                for index in range(3)
            ]
            fixture_dir = root / "inspection-fixtures"
            fixture_dir.mkdir()
            active_paths: dict[str, Path] = {}
            active_facts: dict[str, Fact] = {}
            for fact in facts:
                path = fixture_dir / f"{fact.fact_id}.md"
                path.write_text(serialize_fact(fact), encoding="utf-8")
                active_paths[fact.fact_id] = path
                active_facts[fact.fact_id] = fact

            lifecycle = store.v5_lifecycle()
            lineage_reconstruction = Mock(
                return_value=(active_facts, active_paths)
            )
            lineage_validation = Mock(return_value=None)
            lifecycle._lineage_snapshot = lineage_reconstruction  # type: ignore[method-assign]
            lifecycle._validate_lineage_snapshot = lineage_validation  # type: ignore[method-assign]
            inspection = RoundInspectionContext()
            before = self._tree_snapshot(root)

            with patch.object(store, "v5_lifecycle", return_value=lifecycle):
                observed_facts = store.facts(_inspection_context=inspection)
                observed_ids = store.fact_ids(_inspection_context=inspection)
                observed_individual = {
                    fact_id: store.get_fact(
                        fact_id,
                        _inspection_context=inspection,
                    )
                    for fact_id in observed_ids
                }

            after = self._tree_snapshot(root)
            self.assertEqual(observed_facts, active_facts)
            self.assertEqual(observed_ids, sorted(active_facts))
            self.assertEqual(observed_individual, active_facts)
            self.assertEqual(inspection.active_fact_paths, active_paths)
            self.assertEqual(inspection.active_facts, active_facts)
            self.assertEqual(before, after)

            # The active-Fact path map is derived by _lineage_snapshot.  Three
            # Facts and three public read APIs in one inspection still permit
            # exactly one such reconstruction and one validation.
            self.assertEqual(lineage_reconstruction.call_count, 1)
            self.assertEqual(lineage_validation.call_count, 1)


if __name__ == "__main__":
    unittest.main()

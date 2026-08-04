"""CHX-104: partition reads derive from one validated collection."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mathgraph.paper_continuation import PaperContinuationManager
from mathgraph.store import MathGraphStore
from mathgraph.v5_lifecycle import RoundInspectionContext


class CHX104PartitionedCollectionTests(unittest.TestCase):
    def test_plan_partitions_validate_the_full_disposition_store_once(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = MathGraphStore(Path(temporary).resolve())
            store.initialize(
                project_id="chx-104-partition-reader",
                title="Partitioned collection fixture",
                workflow_evidence_version=5,
            )
            lifecycle = store.v5_lifecycle()
            manager = PaperContinuationManager(
                lifecycle,
                _inspection_context=RoundInspectionContext(),
            )
            manager.dispositions_dir.mkdir(parents=True, exist_ok=True)
            plan_a = "pcp-" + "1" * 64
            plan_b = "pcp-" + "2" * 64
            paths = [
                manager.dispositions_dir / ("pcd-" + "3" * 64 + ".json"),
                manager.dispositions_dir / ("pcd-" + "4" * 64 + ".json"),
            ]
            for path in paths:
                path.write_text("{}\n", encoding="utf-8")
            records = {
                paths[0].stem: {
                    "disposition_id": paths[0].stem,
                    "plan_id": plan_a,
                    "target_node_id": "node-a",
                    "supersedes_disposition_id": "",
                },
                paths[1].stem: {
                    "disposition_id": paths[1].stem,
                    "plan_id": plan_b,
                    "target_node_id": "node-b",
                    "supersedes_disposition_id": "",
                },
            }

            def validate(_payload: object, *, path: Path) -> dict[str, str]:
                return records[path.stem]

            with patch.object(
                manager,
                "_validate_disposition_record",
                side_effect=validate,
            ) as validator:
                self.assertEqual(manager.dispositions(plan_a), [records[paths[0].stem]])
                self.assertEqual(manager.dispositions(plan_b), [records[paths[1].stem]])
                self.assertEqual(manager.dispositions(plan_a), [records[paths[0].stem]])

            self.assertEqual(
                validator.call_count,
                len(paths),
                "plan partitions revalidated the complete disposition store",
            )


if __name__ == "__main__":
    unittest.main()

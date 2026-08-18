from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mathgraph.contracts import sha256_bytes
from mathgraph.runtime_archive import (
    RUNTIME_ARCHIVE_ENV,
    runtime_binding_from_root,
)
from mathgraph.store import MathGraphStore


class MathGraphFirstDirectOperationTests(unittest.TestCase):
    @staticmethod
    def _runtime(root: Path, *, version: str, payload: str) -> dict[str, object]:
        """Build a minimal, independently verifiable runtime fixture."""

        root.mkdir()
        version_path = root / "VERSION"
        payload_path = root / "runtime_payload.txt"
        manifest_path = root / "MANIFEST.sha256"
        version_path.write_text(version + "\n", encoding="utf-8")
        payload_path.write_text(payload + "\n", encoding="utf-8")
        manifest_path.write_text(
            f"{sha256_bytes(version_path.read_bytes())}  VERSION\n"
            f"{sha256_bytes(payload_path.read_bytes())}  runtime_payload.txt\n",
            encoding="utf-8",
        )
        return runtime_binding_from_root(root)

    def test_terminal_runtime_location_is_not_a_graph_operation_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            root = base / "project"
            store = MathGraphStore(root)
            store.initialize(
                project_id="chx-080-mathgraph-first",
                title="MathGraph-first direct operation",
                workflow_evidence_version=5,
            )
            lifecycle = store.v5_lifecycle()
            source = lifecycle.add_research(
                {
                    "kind": "insight",
                    "claim": "A legacy graph node can seed new Research.",
                    "content": "The source node remains nontruth until the normal workflow verifies it.",
                },
                actor="legacy-main",
            )

            historical_runtime = self._runtime(
                base / "chalxius-historical-runtime",
                version="0.7.16",
                payload="historical task-card runtime",
            )
            with patch.object(
                lifecycle, "_runtime_binding", return_value=historical_runtime
            ):
                planned = lifecycle.create_production_round(
                    workers=1,
                    mode="prove",
                    research_ids=[source["research_id"]],
                    host_task_scope_id="legacy-direct-operation",
                )
            # The lifecycle API owns its V5 mutation authority.  A direct
            # agent call must not require a compatibility adapter or an
            # external lock wrapper.
            store.reasoning_modes().abort_work_unit(
                round_id=str(planned["round_id"]),
                actor="main",
                reason="Leave a terminal historical round for direct-operation testing.",
            )

            # The old implementation attempted to locate the historical
            # runtime archive before exposing the graph frontier.  A new host
            # may not have that path, and this must not stop graph work.
            foreign_archive = base / "foreign-runtime-archive"
            (base / "chalxius-historical-runtime").rename(
                base / "chalxius-removed-runtime"
            )
            with patch.dict(
                os.environ, {RUNTIME_ARCHIVE_ENV: str(foreign_archive)}
            ), patch(
                "mathgraph.runtime_archive.resolve_historical_runtime",
                side_effect=AssertionError("historical runtime lookup is forbidden"),
            ):
                terminal = lifecycle.round_status(str(planned["round_id"]))
                self.assertEqual(terminal["work_unit_state"], "aborted")
                frontier_ids = {
                    item["research_id"] for item in lifecycle.frontier(limit=20)
                }
                self.assertIn(source["research_id"], frontier_ids)

                successor = lifecycle.add_research(
                    {
                        "kind": "insight",
                        "claim": "A current agent can extend the legacy node directly.",
                        "content": "This is a copy-on-write continuation with ordinary Research status.",
                        "relation": "strengthens",
                        "related_research_ids": [source["research_id"]],
                    },
                    actor="main",
                )

                current_runtime = self._runtime(
                    base / "chalxius-current-runtime",
                    version="0.8.0",
                    payload="current task-card runtime",
                )
                with patch.object(
                    lifecycle, "_runtime_binding", return_value=current_runtime
                ):
                    next_round = lifecycle.create_production_round(
                        workers=1,
                        mode="prove",
                        research_ids=[successor["research_id"]],
                        host_task_scope_id="legacy-direct-operation-next",
                    )

            self.assertEqual(next_round["assignments"][0]["research_id"], successor["research_id"])
            self.assertIn(
                source["research_id"],
                {record["research_id"] for record in lifecycle.research_records()},
            )

    def test_legacy_graph_can_continue_without_upgrade_or_adapter(self) -> None:
        """Legacy graph bytes are native inputs for append-only Research work."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve() / "legacy-v3"
            fixture = MathGraphStore._for_legacy_workflow_fixture(root)
            fixture.initialize(
                project_id="chx-080-legacy-direct",
                title="Legacy direct operation",
            )
            project_before = (root / "project.json").read_bytes()
            facts_before = {
                path.relative_to(root).as_posix(): sha256_bytes(path.read_bytes())
                for path in (root / "fact_graph").rglob("*")
                if path.is_file() and not path.is_symlink()
            }

            # Reopen through the ordinary store.  No fixture authority,
            # upgrade copy, or adapter is available to this agent call.
            store = MathGraphStore(root)
            memory_id = store.memory_add(
                {
                    "kind": "direction",
                    "claim": "A legacy graph can seed a new Research direction.",
                    "content": "The append is nontruth and leaves historical Facts untouched.",
                },
                actor="main",
            )

            self.assertEqual(store.workflow_evidence_version(), 3)
            self.assertEqual((root / "project.json").read_bytes(), project_before)
            self.assertEqual(
                facts_before,
                {
                    path.relative_to(root).as_posix(): sha256_bytes(path.read_bytes())
                    for path in (root / "fact_graph").rglob("*")
                    if path.is_file() and not path.is_symlink()
                },
            )
            self.assertIn(memory_id, store.memory_latest())


if __name__ == "__main__":
    unittest.main()

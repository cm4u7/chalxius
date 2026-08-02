from __future__ import annotations

import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from mathgraph.cli import build_parser, main
from mathgraph.contracts import sha256_bytes
from mathgraph.paper_continuation import PaperContinuationManager
from tests import test_v5_lifecycle as v5_fixture


class PaperContinuationStatusProjectionTests(unittest.TestCase):
    @staticmethod
    def _full_status(size: int = 20_000) -> dict[str, object]:
        plan_id = "pcp-" + "a" * 64
        repeated = [f"object-{index:05d}" for index in range(size)]
        return {
            "schema_version": 1,
            "contract_revision": "chalxius-v5-paper-continuation-1",
            "plan_id": plan_id,
            "paper_id": "paper-fixture",
            "snapshot_id": "pls-" + "b" * 64,
            "domain_profile": "mathematics",
            "selection_mode": "all_targets",
            "state": "complete",
            "source_snapshot_current": True,
            "adequacy_complete": True,
            "counts": {
                "total": size,
                "frontier_materialized": size,
                "researched": size,
                "dispositioned": size,
                "unresolved": 0,
                "successor_mapped": size,
                "revised_manuscript_covered": size,
            },
            "unresolved_target_node_ids": [],
            "target_research_bindings": [
                {"target_node_id": item, "research_id": "research-" + item}
                for item in repeated
            ],
            "current_disposition_ids": ["disposition-" + item for item in repeated],
            "selected_reconstruction_node_ids": repeated,
            "selected_source_node_ids": ["source-" + item for item in repeated],
            "selected_edge_ids": ["edge-" + item for item in repeated],
            "adequacy_receipt_sha256": "c" * 64,
            "truth_effect": "none",
        }

    def test_summary_is_bounded_and_receipt_identical_to_full_view(self) -> None:
        manager = object.__new__(PaperContinuationManager)
        full = self._full_status()
        expected = {
            key: full[key]
            for key in (
                "schema_version",
                "contract_revision",
                "plan_id",
                "paper_id",
                "snapshot_id",
                "domain_profile",
                "selection_mode",
                "state",
                "source_snapshot_current",
                "adequacy_complete",
                "counts",
                "adequacy_receipt_sha256",
                "truth_effect",
            )
        } | {
            "detail": {
                "included": False,
                "omitted_fields": [
                    "current_disposition_ids",
                    "selected_edge_ids",
                    "selected_reconstruction_node_ids",
                    "selected_source_node_ids",
                    "target_research_bindings",
                    "unresolved_target_node_ids",
                ],
                "request": [
                    "paper-continuation-status",
                    full["plan_id"],
                    "--full",
                ],
            }
        }

        class Index:
            def summary(self, plan_id: str) -> dict[str, object]:
                self.plan_id = plan_id
                return expected

        index = Index()
        manager._status_index = index  # type: ignore[attr-defined]
        manager.status = lambda plan_id: (_ for _ in ()).throw(  # type: ignore[method-assign]
            AssertionError("routine summary reconstructed full status")
        )

        summary = manager.status_summary(str(full["plan_id"]))
        encoded = json.dumps(summary, ensure_ascii=False, sort_keys=True).encode()

        self.assertEqual(index.plan_id, full["plan_id"])
        self.assertLess(len(encoded), 4_096)
        self.assertEqual(
            summary["adequacy_receipt_sha256"],
            full["adequacy_receipt_sha256"],
        )
        self.assertEqual(summary["counts"], full["counts"])
        self.assertEqual(summary["truth_effect"], "none")
        for field in summary["detail"]["omitted_fields"]:  # type: ignore[index]
            self.assertNotIn(field, summary)
            self.assertIn(field, full)
        self.assertEqual(
            summary["detail"]["request"],  # type: ignore[index]
            ["paper-continuation-status", full["plan_id"], "--full"],
        )

    def test_cli_defaults_to_summary_and_full_is_explicit(self) -> None:
        plan_id = "pcp-" + "d" * 64
        calls: list[tuple[str, str]] = []

        class Continuation:
            def status_summary(self, value: str) -> dict[str, object]:
                calls.append(("summary", value))
                return {"view": "summary", "truth_effect": "none"}

            def status(self, value: str) -> dict[str, object]:
                calls.append(("full", value))
                return {"view": "full", "truth_effect": "none"}

            def status_all_summary(self) -> dict[str, object]:
                calls.append(("summary-all", ""))
                return {"view": "summary-all", "truth_effect": "none"}

            def status_all(self) -> dict[str, object]:
                calls.append(("full-all", ""))
                return {"view": "full-all", "truth_effect": "none"}

        continuation = Continuation()

        class Lifecycle:
            def paper_continuation(self) -> Continuation:
                return continuation

        with tempfile.TemporaryDirectory() as temporary:
            project_path = Path(temporary) / "not-initialized"

            class Store:
                def __init__(self, *_: object, **__: object) -> None:
                    self.project_path = project_path

                def workflow_evidence_version(self) -> int:
                    return 5

                def v5_lifecycle(self) -> Lifecycle:
                    return Lifecycle()

            def invoke(extra: list[str]) -> dict[str, object]:
                output = StringIO()
                with patch("mathgraph.cli.MathGraphStore", Store), redirect_stdout(output):
                    result = main(
                        [
                            "--root",
                            str(project_path),
                            "--role",
                            "main",
                            "paper-continuation-status",
                            *extra,
                        ]
                    )
                self.assertEqual(result, 0)
                return json.loads(output.getvalue())

            self.assertEqual(invoke([plan_id])["view"], "summary")
            self.assertEqual(invoke([plan_id, "--full"])["view"], "full")
            self.assertEqual(invoke([])["view"], "summary-all")
            self.assertEqual(invoke(["--full"])["view"], "full-all")

        self.assertEqual(
            calls,
            [
                ("summary", plan_id),
                ("full", plan_id),
                ("summary-all", ""),
                ("full-all", ""),
            ],
        )

    def test_parser_exposes_only_an_explicit_full_detail_switch(self) -> None:
        plan_id = "pcp-" + "e" * 64
        base = ["--root", "/tmp/project", "--role", "main"]
        compact = build_parser().parse_args(
            [*base, "paper-continuation-status", plan_id]
        )
        detailed = build_parser().parse_args(
            [*base, "paper-continuation-status", plan_id, "--full"]
        )
        self.assertFalse(compact.full)
        self.assertTrue(detailed.full)

        rebuild = build_parser().parse_args(
            [
                *base,
                "paper-continuation-status-index-rebuild",
                "--actor",
                "main",
            ]
        )
        self.assertEqual(rebuild.command, "paper-continuation-status-index-rebuild")

    def test_indexed_summary_is_two_json_reads_stale_safe_and_rebuildable(self) -> None:
        fixture = v5_fixture.V5LifecycleTests(methodName="runTest")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "v5"
            store = fixture._store(root, "v5-indexed-paper-status")
            lifecycle = store.v5_lifecycle()
            artifact = root / "paper.txt"
            artifact.write_text(
                "The supporting lemma holds.\n"
                "The root theorem follows from the supporting lemma.\n",
                encoding="utf-8",
            )
            artifact_sha = sha256_bytes(artifact.read_bytes())
            source = {
                "artifact_sha256": artifact_sha,
                "artifact_locator": str(artifact),
                "title": "Indexed status fixture",
                "version": "test-v1",
                "mime_type": "text/plain",
                "retrieved_at": "2026-08-03T00:00:00Z",
                "inspection_methods": [
                    "rendered_primary",
                    "text_extraction_secondary",
                ],
            }
            with store.v5_mutation_lock(command="paper-logic-init"):
                store.paper_logic().initialize(actor="main")
            bundle = fixture._paper_logic_bundle(store=store, source=source)
            with store.v5_mutation_lock(command="paper-logic-freeze"):
                _, frozen = fixture._freeze_paper_bundle(
                    store=store,
                    bundle=bundle,
                    artifact=artifact,
                )
            continuation = lifecycle.paper_continuation()
            full = continuation.create_plan(
                frozen["snapshot_id"],
                {
                    "selection_mode": "all_targets",
                    "target_node_ids": [],
                    "objective": "Preserve the exact mathematical target.",
                    "source_artifact_sha256": artifact_sha,
                },
                actor="main",
            )
            plan_id = full["plan_id"]

            reads: list[Path] = []
            original_read = store._read_json

            def counted(path: Path) -> dict[str, object]:
                reads.append(Path(path))
                return original_read(path)

            with (
                patch.object(
                    continuation,
                    "status",
                    side_effect=AssertionError("summary called full status"),
                ),
                patch.object(
                    continuation,
                    "plans",
                    side_effect=AssertionError("summary enumerated full plans"),
                ),
                patch.object(store, "_read_json", side_effect=counted),
            ):
                summary = continuation.status_summary(plan_id)
            self.assertEqual(summary["adequacy_receipt_sha256"], full["adequacy_receipt_sha256"])
            self.assertEqual(summary["counts"], full["counts"])
            self.assertEqual(len(reads), 2, reads)
            self.assertEqual(reads[0].name, "HEAD.json")
            self.assertEqual(reads[1].parent.parent.name, "receipts")

            with patch.object(
                PaperContinuationManager,
                "status_all",
                side_effect=AssertionError("top-level status called full continuation"),
            ):
                top_level = lifecycle.status()
            self.assertEqual(
                top_level["paper_continuation"]["plans"][0]["plan_id"],
                plan_id,
            )

            research_dir = lifecycle.research_entries_dir
            stat = research_dir.stat()
            os.utime(
                research_dir,
                ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000),
            )
            with self.assertRaisesRegex(ValueError, "status index is stale"):
                continuation.status_summary(plan_id)

            rebuilt = continuation.rebuild_status_index()
            self.assertEqual(rebuilt["status"], "rebuilt_after_full_validation")
            refreshed = continuation.status_summary(plan_id)
            exact = continuation.status(plan_id)
            self.assertEqual(
                refreshed["adequacy_receipt_sha256"],
                exact["adequacy_receipt_sha256"],
            )


if __name__ == "__main__":
    unittest.main()

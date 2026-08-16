from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mathgraph.contracts import sha256_bytes
from mathgraph.runtime_archive import runtime_binding_from_root
from mathgraph.store import MathGraphStore
from mathgraph.v5_lifecycle import V5LifecycleManager


class TextArtifactHygieneTests(unittest.TestCase):
    def setUp(self) -> None:
        runtime_patch = patch.object(
            V5LifecycleManager,
            "_validate_bound_runtime_binding",
            new=staticmethod(lambda value, **_: value),
        )
        runtime_patch.start()
        self.addCleanup(runtime_patch.stop)

    @staticmethod
    def _blank_assurance() -> dict[str, list[object]]:
        return {
            "source_uses": [],
            "route_invalidations": [],
            "extremal_cases": [],
            "claim_strength": [],
            "contour_substitutions": [],
            "claimed_structures": [],
            "program_math_alignments": [],
        }

    @staticmethod
    def _store(root: Path, *, project_id: str) -> MathGraphStore:
        store = MathGraphStore(root)
        store.initialize(
            project_id=project_id,
            title="Prospective textual artifact hygiene",
            workflow_evidence_version=5,
        )
        return store

    def _assignment(
        self,
        root: Path,
        *,
        project_id: str,
    ) -> tuple[
        MathGraphStore,
        V5LifecycleManager,
        dict[str, object],
        dict[str, object],
        dict[str, object],
    ]:
        store = self._store(root, project_id=project_id)
        lifecycle = store.v5_lifecycle()
        source = lifecycle.add_research(
            {"claim": "Inspect one exact textual worker artifact."},
            actor="main",
        )
        planned = lifecycle.create_production_round(
            workers=1,
            mode="prove",
            research_ids=[source["research_id"]],
            host_task_scope_id=f"{project_id}-host",
        )
        assignment = planned["assignments"][0]
        card = json.loads(
            Path(str(assignment["task_card_path"])).read_text(encoding="utf-8")
        )
        return store, lifecycle, planned, assignment, card

    @staticmethod
    def _historical_runtime(temporary: str) -> dict[str, object]:
        # TemporaryDirectory may be returned through macOS's /var -> /private/var
        # compatibility link.  Runtime binding intentionally rejects symlink
        # components, so the fixture must bind the canonical path explicitly.
        runtime = (Path(temporary).resolve() / "chalxius-0.7.15").resolve()
        runtime.mkdir()
        (runtime / "VERSION").write_text("0.7.15\n", encoding="utf-8")
        (runtime / "MANIFEST.sha256").write_text("", encoding="utf-8")
        return runtime_binding_from_root(runtime)

    def _write_return(
        self,
        store: MathGraphStore,
        planned: dict[str, object],
        assignment: dict[str, object],
        card: dict[str, object],
        *,
        artifact_name: str,
        artifact_bytes: bytes,
    ) -> tuple[Path, Path]:
        artifact_dir = store.root / str(assignment["artifact_dir_relpath"])
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifact_dir / artifact_name
        artifact_path.write_bytes(artifact_bytes)
        artifact = {
            "path": artifact_path.relative_to(store.root).as_posix(),
            "sha256": sha256_bytes(artifact_bytes),
            "role": "research_report",
        }
        assurance_contract = card["assurance_contract"]
        assert isinstance(assurance_contract, dict)
        obligations = assurance_contract["obligations"]
        assert isinstance(obligations, list)
        payload = {
            "schema_version": 5,
            "project_id": store.project_id(),
            "round_id": planned["round_id"],
            "assignment_id": assignment["assignment_id"],
            "worker_id": assignment["worker_id"],
            "task_card_sha256": assignment["task_card_sha256"],
            "blackboard_snapshot_sha256": assignment[
                "blackboard_snapshot_sha256"
            ],
            "outcome": "proof",
            "claim": "One bounded artifact was produced.",
            "content": "The artifact remains nontruth Research.",
            "narrative": {
                "rationale": "Exercise the shared worker-return validator.",
                "summary": "One artifact is ready for validation.",
                "intuition": "Only the frozen artifact bytes are relevant.",
                "limitations": "No Candidate or Fact authority is created.",
            },
            "artifacts": [artifact],
            "obligation_dispositions": [
                {
                    "obligation_id": obligation["obligation_id"],
                    "status": "complete",
                    "witness_artifact_sha256s": [artifact["sha256"]],
                    "rationale": "The exact artifact is hash-bound.",
                }
                for obligation in obligations
            ],
            "computation_manifest": None,
            "research_assurance": self._blank_assurance(),
        }
        return_path = Path(str(assignment["return_path"]))
        return_path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        return return_path, artifact_path

    @staticmethod
    def _prospective_gate(lifecycle: V5LifecycleManager):
        original = lifecycle._task_card_skill_version_at_least

        def at_least(
            card: dict[str, object], minimum: tuple[int, int, int]
        ) -> bool:
            if minimum == (0, 7, 16):
                return True
            return original(card, minimum)

        return patch.object(
            lifecycle,
            "_task_card_skill_version_at_least",
            side_effect=at_least,
        )

    def test_skill_version_gate_starts_at_0716(self) -> None:
        card_0715 = {"runtime_binding": {"skill_version": "0.7.15"}}
        card_0716 = {"runtime_binding": {"skill_version": "0.7.16"}}
        self.assertFalse(
            V5LifecycleManager._task_card_skill_version_at_least(
                card_0715, (0, 7, 16)
            )
        )
        self.assertTrue(
            V5LifecycleManager._task_card_skill_version_at_least(
                card_0716, (0, 7, 16)
            )
        )

    def test_markdown_tab_is_rejected_prospectively(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store, lifecycle, planned, assignment, card = self._assignment(
                Path(temporary) / "project",
                project_id="chx-0716-markdown-tab",
            )
            _, artifact_path = self._write_return(
                store,
                planned,
                assignment,
                card,
                artifact_name="report.md",
                artifact_bytes=b"alpha\tbeta\n",
            )
            expected = (
                "V5 worker textual artifact contains forbidden control byte; "
                f"role=research_report; "
                f"path={artifact_path.relative_to(store.root).as_posix()}; "
                "byte=0x09; offset=5"
            )
            with self._prospective_gate(lifecycle), self.assertRaisesRegex(
                ValueError, re.escape(expected)
            ):
                lifecycle.preflight_return(
                    round_id=str(planned["round_id"]),
                    assignment_id=str(assignment["assignment_id"]),
                )

    def test_preflight_and_ingest_share_backspace_failure_without_sealing(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store, lifecycle, planned, assignment, card = self._assignment(
                Path(temporary) / "project",
                project_id="chx-0716-shared-failure",
            )
            return_path, artifact_path = self._write_return(
                store,
                planned,
                assignment,
                card,
                artifact_name="report.markdown",
                artifact_bytes=b"alpha\x08beta\n",
            )
            expected = (
                "V5 worker textual artifact contains forbidden control byte; "
                f"role=research_report; "
                f"path={artifact_path.relative_to(store.root).as_posix()}; "
                "byte=0x08; offset=5"
            )
            research_count = len(lifecycle.research_records())
            terminal_dir = (
                store.rounds_dir
                / str(planned["round_id"])
                / "terminal"
                / str(assignment["assignment_id"])
            )
            with self._prospective_gate(lifecycle):
                with self.assertRaisesRegex(ValueError, re.escape(expected)):
                    lifecycle.preflight_return(
                        round_id=str(planned["round_id"]),
                        assignment_id=str(assignment["assignment_id"]),
                    )
                self.assertEqual(len(lifecycle.research_records()), research_count)
                self.assertFalse(terminal_dir.exists())

                result = lifecycle.ingest_return(
                    round_id=str(planned["round_id"]),
                    assignment_id=str(assignment["assignment_id"]),
                    worker_final_sha256=sha256_bytes(return_path.read_bytes()),
                )
            self.assertEqual(result["status"], "quarantined")
            self.assertEqual(result["error"], expected)
            self.assertEqual(len(lifecycle.research_records()), research_count)
            self.assertFalse(terminal_dir.exists())

    def test_valid_unicode_markdown_is_accepted_and_read_once(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store, lifecycle, planned, assignment, card = self._assignment(
                Path(temporary) / "project",
                project_id="chx-0716-unicode",
            )
            return_path, artifact_path = self._write_return(
                store,
                planned,
                assignment,
                card,
                artifact_name="report.md",
                artifact_bytes="中文说明与公式 \\(x^2+α\\)。\n".encode("utf-8"),
            )
            original_read = V5LifecycleManager._read_regular_bytes_once
            read_paths: list[Path] = []

            def counted_read(
                path: Path,
                *,
                label: str,
                containment_root: Path | None = None,
                require_single_link: bool = False,
            ) -> bytes:
                read_paths.append(path.resolve())
                return original_read(
                    path,
                    label=label,
                    containment_root=containment_root,
                    require_single_link=require_single_link,
                )

            with self._prospective_gate(lifecycle), patch.object(
                V5LifecycleManager,
                "_read_regular_bytes_once",
                side_effect=counted_read,
            ):
                result = lifecycle.preflight_return(
                    round_id=str(planned["round_id"]),
                    assignment_id=str(assignment["assignment_id"]),
                )
            self.assertTrue(result["valid"])
            self.assertEqual(read_paths.count(return_path.resolve()), 1)
            self.assertEqual(read_paths.count(artifact_path.resolve()), 1)

    def test_tabs_remain_valid_in_python_and_plain_text(self) -> None:
        cases = (
            ("python", "report.py", b"def value():\n\treturn 1\n"),
            ("text", "report.txt", b"left\tright\r\n"),
        )
        for label, artifact_name, artifact_bytes in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                store, lifecycle, planned, assignment, card = self._assignment(
                    Path(temporary) / "project",
                    project_id=f"chx-0716-{label}-tab",
                )
                self._write_return(
                    store,
                    planned,
                    assignment,
                    card,
                    artifact_name=artifact_name,
                    artifact_bytes=artifact_bytes,
                )
                with self._prospective_gate(lifecycle):
                    result = lifecycle.preflight_return(
                        round_id=str(planned["round_id"]),
                        assignment_id=str(assignment["assignment_id"]),
                    )
                self.assertTrue(result["valid"])

    def test_binary_control_bytes_remain_outside_the_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store, lifecycle, planned, assignment, card = self._assignment(
                Path(temporary) / "project",
                project_id="chx-0716-binary",
            )
            self._write_return(
                store,
                planned,
                assignment,
                card,
                artifact_name="report.bin",
                artifact_bytes=b"\x00\x08\x09\x0a\x0d\x1f",
            )
            with self._prospective_gate(lifecycle):
                result = lifecycle.preflight_return(
                    round_id=str(planned["round_id"]),
                    assignment_id=str(assignment["assignment_id"]),
                )
            self.assertTrue(result["valid"])

    def test_current_0715_card_keeps_its_frozen_markdown_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            binding = self._historical_runtime(temporary)
            with patch.object(
                V5LifecycleManager,
                "_runtime_binding",
                new=staticmethod(lambda: binding),
            ):
                store, lifecycle, planned, assignment, card = self._assignment(
                    Path(temporary) / "project",
                    project_id="chx-0715-frozen-markdown",
                )
                runtime_binding = card["runtime_binding"]
                assert isinstance(runtime_binding, dict)
                self.assertEqual(runtime_binding["skill_version"], "0.7.15")
                self._write_return(
                    store,
                    planned,
                    assignment,
                    card,
                    artifact_name="legacy.md",
                    artifact_bytes=b"legacy\tmarkdown\x08\n",
                )
                result = lifecycle.preflight_return(
                    round_id=str(planned["round_id"]),
                    assignment_id=str(assignment["assignment_id"]),
                )
                self.assertTrue(result["valid"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from mathgraph.cli import main as cli_main
from mathgraph.contracts import POLICY_REVISION_V4
from mathgraph.orchestrator import create_round
from mathgraph.roles import allowed_commands
from mathgraph.store import MathGraphStore


class V4PreflightReturnTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = MathGraphStore(self.root)
        self.store.initialize(
            project_id="v4-preflight-return",
            title="V4 preflight return",
            workflow_evidence_version=4,
        )
        self.memory_counter = 0

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _cli(
        self,
        role: str,
        *args: str,
    ) -> tuple[int, dict | None, str]:
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = cli_main(
                [
                    "--root",
                    str(self.root),
                    "--role",
                    role,
                    *args,
                ]
            )
        payload = (
            json.loads(stdout.getvalue())
            if stdout.getvalue().strip()
            else None
        )
        return code, payload, stderr.getvalue()

    def _planned_interpret(self) -> tuple[dict, dict, Path, Path]:
        self.memory_counter += 1
        memory_id = self.store.memory_add(
            {
                "kind": "direction",
                "claim": (
                    "Preflight interpret direction "
                    f"{self.memory_counter}."
                ),
                "rationale": "Exercise mutable-draft validation.",
                "suggested_actions": ["interpret"],
            },
            actor="main",
        )
        planned = create_round(
            self.store,
            workers=1,
            mode="interpret",
            memory_ids=[memory_id],
            host_task_scope_id="hosttask-" + "8" * 32,
        )
        assignment = planned["assignments"][0]
        card_path = Path(assignment["task_card_path"])
        card = json.loads(card_path.read_text(encoding="utf-8"))
        draft_path = (
            Path(assignment["work_dir_path"]) / "return-draft.json"
        )
        return (
            planned,
            card,
            draft_path,
            Path(assignment["return_path"]),
        )

    @staticmethod
    def _common_return(
        planned: dict,
        card: dict,
        *,
        outcome: str,
    ) -> dict:
        card_path = Path(
            planned["assignments"][0]["task_card_path"]
        )
        return {
            "schema_version": 4,
            "policy_revision": POLICY_REVISION_V4,
            "protocol": "mathgraph-agent-v4",
            "project_id": card["project_id"],
            "round_id": card["round_id"],
            "assignment_id": card["assignment_id"],
            "assignment_sha256": card["assignment_sha256"],
            "task_card_sha256": hashlib.sha256(
                card_path.read_bytes()
            ).hexdigest(),
            "blackboard_snapshot_sha256": card[
                "blackboard_snapshot_sha256"
            ],
            "worker": card["worker_id"],
            "memory_id": card["memory_id"],
            "mode": card["mode"],
            "outcome": outcome,
            "obligation_ledger": [],
            "blackboard_graph_delta": {
                "base_snapshot_id": card["blackboard_view"][
                    "snapshot_id"
                ],
                "add_nodes": [],
                "add_edges": [],
            },
            "narrative_summary": "Mutable preflight draft.",
        }

    def _project_bytes(self) -> dict[str, bytes]:
        return {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in sorted(self.root.rglob("*"))
            if path.is_file() and not path.is_symlink()
        }

    def test_incomplete_interpret_fails_before_canonical_write(
        self,
    ) -> None:
        planned, card, draft_path, return_path = (
            self._planned_interpret()
        )
        payload = {
            **self._common_return(
                planned,
                card,
                outcome="evidence",
            ),
            "claim": "A possible cancellation.",
            "method": "Interpret the frozen snapshot.",
            "result": {"status": "candidate"},
            "artifacts": [],
            "limitations": "No mechanism node was supplied.",
        }
        draft_path.write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
        before = self._project_bytes()
        code, result, error = self._cli(
            "worker",
            "preflight-return",
            planned["round_id"],
            card["assignment_id"],
            "--input",
            str(draft_path),
        )
        self.assertEqual(code, 2)
        self.assertIsNone(result)
        self.assertIn("mechanism node", error)
        self.assertFalse(return_path.exists())
        self.assertFalse(
            return_path.with_suffix(".receipt.json").exists()
        )
        self.assertEqual(self._project_bytes(), before)

    def test_legal_draft_sha_matches_later_canonical_validation(
        self,
    ) -> None:
        planned, card, draft_path, return_path = (
            self._planned_interpret()
        )
        payload = {
            **self._common_return(
                planned,
                card,
                outcome="dead_end",
            ),
            "claim": "The mechanism remains unidentified.",
            "method": "Inspect the frozen snapshot.",
            "failure_mode": "No falsifiable mechanism survived.",
            "what_remains_open": "A new independent interpretation.",
            "artifacts": [],
        }
        draft_path.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        before = self._project_bytes()
        code, preflight, error = self._cli(
            "worker",
            "preflight-return",
            planned["round_id"],
            card["assignment_id"],
            "--input",
            str(draft_path),
        )
        self.assertEqual(code, 0, error)
        self.assertEqual(preflight["status"], "preflight_passed")
        self.assertEqual(preflight["outcome"], "dead_end")
        self.assertFalse(return_path.exists())
        self.assertEqual(self._project_bytes(), before)

        return_path.write_bytes(draft_path.read_bytes())
        code, validated, error = self._cli(
            "worker",
            "validate-return",
            planned["round_id"],
            card["assignment_id"],
        )
        self.assertEqual(code, 0, error)
        self.assertEqual(
            preflight["return_sha256"],
            validated["return_sha256"],
        )
        self.assertEqual(preflight["outcome"], validated["outcome"])

    def test_only_worker_role_has_preflight_capability(self) -> None:
        planned, card, draft_path, return_path = (
            self._planned_interpret()
        )
        payload = {
            **self._common_return(
                planned,
                card,
                outcome="dead_end",
            ),
            "claim": "No interpretation was retained.",
            "method": "Inspect the frozen snapshot.",
            "failure_mode": "No mechanism.",
            "what_remains_open": "A different interpretation.",
            "artifacts": [],
        }
        draft_path.write_text(
            json.dumps(payload),
            encoding="utf-8",
        )
        self.assertIn(
            "preflight-return",
            allowed_commands("worker"),
        )
        for role in (
            "main",
            "operator",
            "host",
            "gateway",
            "verifier",
        ):
            with self.subTest(role=role):
                code, result, error = self._cli(
                    role,
                    "preflight-return",
                    planned["round_id"],
                    card["assignment_id"],
                    "--input",
                    str(draft_path),
                )
                self.assertEqual(code, 3)
                self.assertIsNone(result)
                self.assertIn("not allowed", error)
        self.assertFalse(return_path.exists())


if __name__ == "__main__":
    unittest.main()

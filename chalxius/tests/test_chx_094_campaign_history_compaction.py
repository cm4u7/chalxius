from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from mathgraph.campaigns import CampaignStore
from mathgraph.cli import main as cli_main
from mathgraph.contracts import sha256_json
from mathgraph.store import MathGraphStore


class CampaignHistoryCompactionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.campaigns = CampaignStore(self.root)
        self.campaigns.initialize()
        self.campaign_id = self.campaigns.create(
            {
                "name": "long-running-campaign",
                "objective": "Keep current state readable without truncating history.",
                "source_claim_ids": [],
                "targets": [],
                "constraints": [],
                "stop_conditions": [],
                "value_definition": "Preserve exact append-only provenance.",
            },
            actor="main",
        )
        for index in range(37):
            self.campaigns.update(
                self.campaign_id,
                {
                    "type": "note",
                    "payload": {"text": f"history-{index:03d}"},
                },
                actor="main",
            )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _events(self) -> list[dict]:
        path = self.root / "campaigns" / self.campaign_id / "events.jsonl"
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    @staticmethod
    def _run_cli(*arguments: str) -> tuple[int, str, str]:
        output = io.StringIO()
        error = io.StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            status = cli_main(list(arguments))
        return status, output.getvalue(), error.getvalue()

    def test_full_status_and_prefix_commitment_preserve_exact_history(self) -> None:
        events = self._events()
        status = self.campaigns.status(self.campaign_id)
        self.assertEqual(len(status["updates"]), 37)
        self.assertEqual(
            status["history"],
            {
                "event_count": len(events),
                "last_event_id": events[-1]["event_id"],
                "events_sha256": sha256_json(events),
            },
        )
        self.assertEqual(
            self.campaigns.history_summary(
                self.campaign_id,
                event_count=9,
            ),
            {
                "event_count": 9,
                "last_event_id": events[8]["event_id"],
                "events_sha256": sha256_json(events[:9]),
            },
        )
        with self.assertRaisesRegex(ValueError, "outside verified history"):
            self.campaigns.history_summary(
                self.campaign_id,
                event_count=len(events) + 1,
            )

    def test_compact_status_is_one_current_view_with_a_fixed_recent_tail(self) -> None:
        events = self._events()
        compact = self.campaigns.compact_status(self.campaign_id)
        self.assertNotIn("updates", compact)
        self.assertIsNone(compact["latest_frontier_checkpoint"])
        self.assertEqual(compact["history"]["event_count"], len(events))
        recent = compact["recent_history"]
        self.assertEqual(recent["shown_count"], 8)
        self.assertEqual(recent["start_ordinal"], len(events) - 7)
        self.assertEqual(recent["end_ordinal"], len(events))
        self.assertEqual(recent["older_event_count"], len(events) - 8)
        self.assertEqual(
            [event["event_id"] for event in recent["events"]],
            [event["event_id"] for event in events[-8:]],
        )
        self.assertNotIn("payload", recent["events"][-1])
        self.assertEqual(recent["events"][-1]["text_preview"], "history-036")

    def test_checkpoint_write_keeps_only_routing_references(self) -> None:
        event_id = self.campaigns.update(
            self.campaign_id,
            {
                "type": "note",
                "payload": {
                    "kind": "campaign_frontier_head_checkpoint",
                    "generation": 1,
                    "supersedes_event_id": None,
                    "semantics": "duplicated prose is not routing state",
                    "attention_boundary": "x" * 8192,
                    "target_frontiers": [
                        {
                            "target_id": "camtarget-0123456789abcdef",
                            "label": "copied target body",
                            "recovery_root_research_id": "111111111111",
                            "main_disposition": "continue from exact heads",
                            "active_heads": [
                                {
                                    "research_id": "222222222222",
                                    "reason": "y" * 8192,
                                    "product_research_id": "333333333333",
                                }
                            ],
                            "attained_checkpoints": [
                                {
                                    "research_id": "444444444444",
                                    "review_research_id": "555555555555",
                                }
                            ],
                        }
                    ],
                },
            },
            actor="main",
        )
        update = self.campaigns.status(self.campaign_id)["updates"][-1]
        self.assertEqual(update["event_id"], event_id)
        checkpoint = update["payload"]
        self.assertEqual(
            set(checkpoint),
            {
                "kind",
                "generation",
                "supersedes_event_id",
                "target_frontiers",
            },
        )
        frontier = checkpoint["target_frontiers"][0]
        self.assertEqual(
            frontier["active_heads"],
            [{"research_id": "222222222222"}],
        )
        self.assertEqual(
            frontier["attained_checkpoints"],
            [{"research_id": "444444444444"}],
        )
        self.assertLess(
            len(json.dumps(update, ensure_ascii=False).encode("utf-8")),
            2048,
        )
        current = self.campaigns.compact_status(self.campaign_id)
        self.assertEqual(
            current["latest_frontier_checkpoint"]["event_id"],
            event_id,
        )
        self.assertEqual(
            current["latest_frontier_checkpoint"]["target_frontiers"],
            checkpoint["target_frontiers"],
        )
        self.assertNotIn(
            "checkpoint",
            current["recent_history"]["events"][-1],
        )

    def test_default_cli_output_remains_bounded_as_history_grows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            store = MathGraphStore(project_root)
            store.initialize(
                project_id="campaign-history-compaction",
                title="Campaign history compaction",
                workflow_evidence_version=4,
            )
            campaign_id = store.campaigns().active()
            assert campaign_id is not None
            large_text = "x" * 4096
            for _ in range(25):
                store.campaigns().update(
                    campaign_id,
                    {"type": "note", "payload": {"text": large_text}},
                    actor="main",
                )
            status, first_output, error = self._run_cli(
                "--root",
                str(project_root),
                "--role",
                "main",
                "campaign-status",
                campaign_id,
            )
            self.assertEqual(status, 0, error)
            for _ in range(60):
                store.campaigns().update(
                    campaign_id,
                    {"type": "note", "payload": {"text": large_text}},
                    actor="main",
                )
            status, second_output, error = self._run_cli(
                "--root",
                str(project_root),
                "--role",
                "main",
                "campaign-status",
                campaign_id,
            )
            self.assertEqual(status, 0, error)
            result = json.loads(second_output)
            self.assertNotIn("updates", result)
            self.assertEqual(result["recent_history"]["shown_count"], 8)
            self.assertLess(len(second_output), len(first_output) + 512)
            self.assertLess(len(second_output), 20 * 1024)

    def test_event_tamper_still_fails_closed(self) -> None:
        path = self.root / "campaigns" / self.campaign_id / "events.jsonl"
        events = self._events()
        events[-1]["payload"] = {"text": "tampered-without-new-event-id"}
        path.write_text(
            "".join(
                json.dumps(event, sort_keys=True) + "\n" for event in events
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "event id/hash mismatch"):
            self.campaigns.compact_status(self.campaign_id)


if __name__ == "__main__":
    unittest.main()

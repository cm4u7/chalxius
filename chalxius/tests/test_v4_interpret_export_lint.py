from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from mathgraph.adoption import (
    build_adoption_plan,
    compact_adoption_binding,
)
from mathgraph.blackboard import make_node
from mathgraph.cli import main as cli_main
from mathgraph.contracts import sha256_json
from mathgraph.fact_bundles import (
    INTERPRET_TRUTH_BOUNDARY,
    build_claim_card,
    build_interpret_lint_receipt,
    lint_interpret_document,
    validate_claim_card,
    validate_expert_lint_receipt,
    validate_interpret_card,
    validate_interpret_communication_readiness,
    validate_interpret_lint_receipt,
)
from mathgraph.model import Fact
from mathgraph.roles import allowed_commands
from mathgraph.store import MathGraphStore


class V4InterpretExportLintTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = MathGraphStore(self.root)
        self.store.initialize(
            project_id="v4-interpret-export",
            title="V4 interpretation export",
            workflow_evidence_version=4,
        )
        self.node = self._add_mechanism()
        self.card = self.store.interpret_card(
            self.node["node_id"],
            audience="advisor",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _add_mechanism(
        self,
        *,
        node_type: str = "mechanism",
        truth_status: str = "exploration",
    ) -> dict:
        board = self.store.blackboard()
        space = next(
            node_id
            for node_id, node in board.nodes().items()
            if node["node_type"] == "space"
        )
        payload = {
            "explains_refs": ["bbn-" + "1" * 64],
            "domain_clause_refs": [
                "DOMAIN-POLES",
                "DOMAIN-VITAL-POINTS",
            ],
            "convention_profile_ids": ["conv-0123456789abcdef"],
            "mechanism_statement": (
                "Pairwise cancellation is the candidate mechanism."
            ),
            "falsifiable_consequences": [
                {
                    "id": "P1",
                    "statement": (
                        "Odd unpaired summands survive after the symmetry "
                        "is broken."
                    ),
                    "suggested_mode": "refute",
                },
                {
                    "id": "P2",
                    "statement": (
                        "The paired table has zero total in the stated domain."
                    ),
                    "suggested_mode": "compute",
                },
            ],
            "known_failures": [
                "The mechanism fails when the pairing has a fixed point."
            ],
            "remaining_gaps": [
                "No geometric origin for the pairing is proved."
            ],
            "truth_status": "exploration",
            "terminology": [],
        }
        node = make_node(
            node_type=node_type,
            logical_key=f"interpret-export-{node_type}-{truth_status}",
            payload=payload,
            truth_status=truth_status,
            convention_profile_ids=["conv-0123456789abcdef"],
            source_refs=[
                "reports/toy-cancellation-table.json#sha256="
                + "2" * 64
            ],
            created_by_assignment_id="main",
        )
        board.add_node_with_placements(
            node=node,
            space_ids=[space],
            actor="main",
        )
        board.reindex(apply=True, actor="main")
        return node

    def _draft(self, card: dict | None = None) -> str:
        card = card or self.card
        lines = [
            card["mechanism_statement"],
            *card["source_refs"],
            *card["explains_refs"],
            *card["domain_clause_refs"],
            *card["convention_profile_ids"],
        ]
        for prediction in card["falsifiable_consequences"]:
            lines.extend(
                [
                    prediction["id"],
                    prediction["statement"],
                    prediction["suggested_mode"],
                ]
            )
        lines.extend(card["known_failures"])
        lines.extend(card["remaining_gaps"])
        lines.extend(
            [
                card["truth_boundary"],
                (
                    "AI assistance: AI tools helped organize this "
                    "candidate interpretation and run communication checks; "
                    "no theorem admission is claimed."
                ),
            ]
        )
        return "\n".join(lines) + "\n"

    def _card_bytes(self) -> bytes:
        return (
            json.dumps(
                self.card,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")

    @staticmethod
    def _rehash_card(card: dict) -> dict:
        semantic = {
            key: value
            for key, value in card.items()
            if key != "interpret_card_sha256"
        }
        return {
            **semantic,
            "interpret_card_sha256": sha256_json(semantic),
        }

    def _adoption_binding(self) -> dict:
        return compact_adoption_binding(
            build_adoption_plan(
                {
                    "schema_version": 1,
                    "policy_revision": "mathgraph-0.3.0",
                    "activity": "interpretation",
                    "audience": "advisor",
                    "computation": {
                        "role": "none",
                        "estimated_wall_seconds": 0,
                        "stage_count": 0,
                        "resume_required": False,
                    },
                    "fact_output": {
                        "candidate_count": 0,
                        "internal_dependency_count": 0,
                        "atomic_visibility_required": False,
                    },
                    "semantics": {
                        "source_claim": False,
                        "convention_sensitive": True,
                        "quantifier_sensitive": False,
                        "terminology_sensitive": False,
                    },
                }
            )
        )

    def _receipt(self, draft: str | None = None) -> dict:
        return build_interpret_lint_receipt(
            project_id=self.store.project_id(),
            receipt_relpath=(
                "reports/interpret-lint-receipts/advisor.json"
            ),
            interpret_card_relpath="reports/interpret-card.json",
            draft_bytes=(draft or self._draft()).encode("utf-8"),
            interpret_card_bytes=self._card_bytes(),
        )

    def test_complete_export_lint_and_readiness_are_nontruth(self) -> None:
        before = {
            "facts": self.store.fact_ids(),
            "memory": self.store.memory_latest(),
            "frontier": self.store.frontier(limit=50),
        }
        draft = self._draft()
        receipt = self._receipt(draft)
        self.assertTrue(receipt["ok"], receipt["errors"])
        readiness = validate_interpret_communication_readiness(
            adoption_binding=self._adoption_binding(),
            lint_receipt=receipt,
            draft_bytes=draft.encode("utf-8"),
            interpret_card_bytes=self._card_bytes(),
        )
        self.assertEqual(readiness["truth_effect"], "none")
        self.assertEqual(self.card["truth_boundary"], INTERPRET_TRUTH_BOUNDARY)
        self.assertNotIn("fact_id", self.card)
        self.assertNotIn("admission", json.dumps(self.card))
        after = {
            "facts": self.store.fact_ids(),
            "memory": self.store.memory_latest(),
            "frontier": self.store.frontier(limit=50),
        }
        self.assertEqual(after, before)

    def test_lint_rejects_missing_failure_prediction_boundary_and_ai(self) -> None:
        removals = {
            "failure": self.card["known_failures"][0],
            "gap": self.card["remaining_gaps"][0],
            "prediction": self.card["falsifiable_consequences"][0][
                "statement"
            ],
            "boundary": self.card["truth_boundary"],
            "AI": "AI assistance:",
        }
        complete = self._draft()
        for label, marker in removals.items():
            with self.subTest(label=label):
                if label == "AI":
                    broken = "\n".join(
                        line
                        for line in complete.splitlines()
                        if not line.startswith(marker)
                    )
                else:
                    broken = complete.replace(marker, "")
                self.assertTrue(
                    lint_interpret_document(
                        broken,
                        interpret_card=self.card,
                    )
                )
        hidden = complete.replace(
            self.card["truth_boundary"],
            f"<!-- {self.card['truth_boundary']} -->",
        )
        self.assertTrue(
            lint_interpret_document(hidden, interpret_card=self.card)
        )
        terse = "\n".join(
            (
                "AI assistance: x"
                if line.startswith("AI assistance:")
                else line
            )
            for line in complete.splitlines()
        )
        self.assertTrue(
            lint_interpret_document(terse, interpret_card=self.card)
        )

    def test_nonmechanism_and_nonexploration_nodes_are_rejected(self) -> None:
        nonmechanism = self._add_mechanism(node_type="note")
        with self.assertRaisesRegex(ValueError, "mechanism"):
            self.store.interpret_card(
                nonmechanism["node_id"],
                audience="expert",
            )
        promoted_truth = self._add_mechanism(
            truth_status="supported_evidence"
        )
        with self.assertRaisesRegex(ValueError, "exploration"):
            self.store.interpret_card(
                promoted_truth["node_id"],
                audience="expert",
            )

    def test_interpret_lint_reuses_terminology_export_policies(self) -> None:
        terminology = [
            {
                "key": "cap",
                "term": "cold cap",
                "definition": "a local regularization contribution",
                "origin": "local_shorthand",
                "source_locator": "",
                "export_policy": "replace",
                "replacement": "local regularization contribution",
                "proof_anchor": "[TERM:cap]",
            }
        ]
        card = validate_interpret_card(
            self._rehash_card(
                {
                    **self.card,
                    "terminology": terminology,
                }
            )
        )
        good = self._draft(card) + "local regularization contribution\n"
        self.assertEqual(
            lint_interpret_document(good, interpret_card=card),
            [],
        )
        self.assertTrue(
            lint_interpret_document(
                good + "Cold Cap\n",
                interpret_card=card,
            )
        )

    def test_promoted_memory_does_not_replace_the_original_node_binding(
        self,
    ) -> None:
        board = self.store.blackboard()
        query = {
            "seed_node_ids": [self.node["node_id"]],
            "direction": "both",
            "max_hops": 1,
            "edge_type_allowlist": ["*"],
            "node_type_allowlist": ["*"],
            "node_budget": 20,
            "edge_budget": 20,
        }
        snapshot = board.snapshot(query=query, actor="main")
        campaign_id = self.store.campaigns().active()
        assert campaign_id is not None
        memory_id = self.store.campaigns().promote_blackboard_node(
            self.node["node_id"],
            {
                "snapshot_id": snapshot["snapshot_id"],
                "campaign_id": campaign_id,
                "memory_kind": "conjecture",
                "claim": "Test the promoted prediction.",
                "rationale": "It is explicitly falsifiable.",
                "mode_suggestions": ["refute"],
                "decision_profile": {
                    "impact": 0.7,
                    "information_value": 0.8,
                    "tractability": 0.8,
                    "burden": 0.2,
                },
                "blackboard_query": query,
            },
            actor="main",
            memory_add=lambda payload, actor: self.store.memory_add(
                payload, actor=actor
            ),
        )
        promoted = self.store.memory_latest()[memory_id]
        card = self.store.interpret_card(
            self.node["node_id"],
            audience="expert",
        )
        self.assertEqual(card["node_id"], self.node["node_id"])
        self.assertNotIn("memory_id", card)
        self.assertEqual(
            promoted["origin_blackboard_node_id"],
            card["node_id"],
        )
        self.assertEqual(card["truth_boundary"], INTERPRET_TRUTH_BOUNDARY)

    def test_fact_and_interpret_cards_and_receipts_cross_reject(self) -> None:
        fact = Fact(
            problem_id=self.store.project_id(),
            author="worker",
            predecessors=[],
            statement="[CLAIM:F] A toy fact.",
            proof="Direct.",
        )
        claim_card = build_claim_card(
            fact=fact,
            audience="advisor",
            literal_source_claim="Literal.",
            researcher_variant="No variant.",
            variant_diff=[],
            source_locator="Source.",
            convention_profile="Convention.",
            reproduction_bundle=[],
        )
        with self.assertRaises(ValueError):
            validate_interpret_card(claim_card)
        with self.assertRaises(ValueError):
            validate_claim_card(self.card)
        receipt = self._receipt()
        with self.assertRaises(ValueError):
            validate_expert_lint_receipt(receipt)
        fake_fact_receipt = {
            key: value
            for key, value in receipt.items()
            if key != "receipt_kind"
        }
        with self.assertRaises(ValueError):
            validate_interpret_lint_receipt(fake_fact_receipt)

    def test_tamper_stale_and_write_once_collision_fail(self) -> None:
        draft = self._draft().encode("utf-8")
        receipt = self._receipt()
        tampered = {
            **receipt,
            "node_content_sha256": "0" * 64,
        }
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            validate_interpret_lint_receipt(tampered)
        with self.assertRaisesRegex(ValueError, "draft bytes mismatch"):
            validate_interpret_communication_readiness(
                adoption_binding=self._adoption_binding(),
                lint_receipt=receipt,
                draft_bytes=draft + b"changed",
                interpret_card_bytes=self._card_bytes(),
            )
        path = (
            self.store.reports_dir
            / "interpret-lint-receipts"
            / "collision.json"
        )
        self.store._write_json_once(path, receipt)
        self.store._write_json_once(path, receipt)
        with self.assertRaisesRegex(ValueError, "collision"):
            self.store._write_json_once(
                path,
                {**receipt, "ok": False},
            )

    def test_required_readiness_fails_closed_without_or_failed_receipt(
        self,
    ) -> None:
        with self.assertRaisesRegex(ValueError, "required"):
            validate_interpret_communication_readiness(
                adoption_binding=self._adoption_binding(),
                lint_receipt=None,
                draft_bytes=self._draft().encode("utf-8"),
                interpret_card_bytes=self._card_bytes(),
            )
        failed = self._receipt(
            self._draft().replace(self.card["truth_boundary"], "")
        )
        self.assertFalse(failed["ok"])
        with self.assertRaisesRegex(ValueError, "lint failed"):
            validate_interpret_communication_readiness(
                adoption_binding=self._adoption_binding(),
                lint_receipt=failed,
                draft_bytes=self._draft()
                .replace(self.card["truth_boundary"], "")
                .encode("utf-8"),
                interpret_card_bytes=self._card_bytes(),
            )

    def test_audit_checks_receipt_project_path_node_and_card(self) -> None:
        card_path = self.store.reports_dir / "interpret-card.json"
        receipt_path = (
            self.store.reports_dir
            / "interpret-lint-receipts"
            / "advisor.json"
        )
        self.store._write_json_once(card_path, self.card)
        self.store._write_json_once(receipt_path, self._receipt())
        self.assertTrue(self.store.audit().current_ok)
        card_path.write_text('{"tampered": true}\n', encoding="utf-8")
        report = self.store.audit()
        self.assertFalse(report.current_ok)
        self.assertTrue(
            any(
                "interpret lint receipt" in error
                for error in report.errors
            )
        )

    def test_cli_surface_and_roles_are_distinct_and_discoverable(self) -> None:
        for command in (
            "export-interpret-card",
            "lint-interpret-document",
        ):
            self.assertIn(command, allowed_commands("main"))
            self.assertIn(command, allowed_commands("operator"))
            for role in ("worker", "verifier", "gateway", "host"):
                self.assertNotIn(command, allowed_commands(role))

        card_path = self.store.reports_dir / "cli-card.json"
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = cli_main(
                [
                    "--root",
                    str(self.root),
                    "--role",
                    "main",
                    "export-interpret-card",
                    self.node["node_id"],
                    "--audience",
                    "advisor",
                    "--output",
                    "reports/cli-card.json",
                ]
            )
        self.assertEqual(code, 0, stderr.getvalue())
        draft_path = self.root / "advisor-draft.md"
        draft_path.write_text(self._draft(), encoding="utf-8")
        with redirect_stdout(StringIO()), redirect_stderr(stderr):
            code = cli_main(
                [
                    "--root",
                    str(self.root),
                    "--role",
                    "main",
                    "lint-interpret-document",
                    "--input",
                    str(draft_path),
                    "--interpret-card",
                    str(card_path),
                ]
            )
        self.assertEqual(code, 0, stderr.getvalue())
        receipts = list(
            (
                self.store.reports_dir
                / "interpret-lint-receipts"
            ).glob("*.json")
        )
        self.assertEqual(len(receipts), 1)
        self.assertTrue(
            validate_interpret_lint_receipt(
                json.loads(receipts[0].read_text(encoding="utf-8")),
                draft_bytes=draft_path.read_bytes(),
                interpret_card_bytes=card_path.read_bytes(),
            )["ok"]
        )


if __name__ == "__main__":
    unittest.main()

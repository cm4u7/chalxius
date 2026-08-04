from __future__ import annotations

import json
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest

from mathgraph.adoption import build_adoption_plan, compact_adoption_binding
from mathgraph.cli import main as cli_main
from mathgraph.fact_bundles import (
    INTERPRET_TRUTH_BOUNDARY,
    build_interpret_card,
    build_interpret_lint_receipt,
    publish_interpret_communication,
)
from mathgraph.store import MathGraphStore


class CommunicationReadinessNormalFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "project"
        self.store = MathGraphStore(self.root)
        self.store.initialize(
            project_id="behavioral-communication",
            title="Behavioral communication fixture",
            workflow_evidence_version=4,
        )
        node = {
            "node_id": "bbn-" + "1" * 64,
            "node_type": "mechanism",
            "truth_status": "exploration",
            "source_refs": ["source:fixture"],
            "convention_profile_ids": ["conv-fixture"],
            "payload": {
                "explains_refs": ["claim:fixture"],
                "domain_clause_refs": ["DOMAIN-BASE"],
                "convention_profile_ids": ["conv-fixture"],
                "mechanism_statement": "A bounded candidate mechanism is under review.",
                "falsifiable_consequences": [
                    {
                        "id": "P1",
                        "statement": "A counterexample defeats the mechanism.",
                        "suggested_mode": "refute",
                    }
                ],
                "known_failures": ["The mechanism is not established outside the fixture."],
                "remaining_gaps": ["No theorem admission is claimed."],
                "truth_status": "exploration",
                "terminology": [],
            },
        }
        self.card = build_interpret_card(
            project_id=self.store.project_id(), node=node, audience="advisor"
        )
        self.card_bytes = (
            json.dumps(self.card, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        self.draft = self._draft().encode("utf-8")
        self.binding = compact_adoption_binding(
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
        self.receipt = build_interpret_lint_receipt(
            project_id=self.store.project_id(),
            receipt_relpath="reports/interpret-lint-receipts/behavior.json",
            interpret_card_relpath="reports/interpret-card.json",
            draft_bytes=self.draft,
            interpret_card_bytes=self.card_bytes,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _draft(self) -> str:
        consequence = self.card["falsifiable_consequences"][0]
        return "\n".join(
            [
                self.card["mechanism_statement"],
                *self.card["source_refs"],
                *self.card["explains_refs"],
                *self.card["domain_clause_refs"],
                *self.card["convention_profile_ids"],
                consequence["id"],
                consequence["statement"],
                consequence["suggested_mode"],
                *self.card["known_failures"],
                *self.card["remaining_gaps"],
                INTERPRET_TRUTH_BOUNDARY,
                (
                    "AI assistance: AI tools organized the candidate interpretation; "
                    "no theorem admission is claimed."
                ),
                "",
            ]
        )

    def _write_inputs(self) -> tuple[Path, Path, Path, Path]:
        reports = self.store.reports_dir
        card_path = reports / "interpret-card.json"
        lint_path = reports / "interpret-lint-receipts" / "behavior.json"
        self.store._write_json_once(card_path, self.card)
        self.store._write_json_once(lint_path, self.receipt)
        draft_path = Path(self.temporary.name) / "draft.md"
        binding_path = Path(self.temporary.name) / "binding.json"
        draft_path.write_bytes(self.draft)
        binding_path.write_text(
            json.dumps(self.binding, sort_keys=True) + "\n", encoding="utf-8"
        )
        return draft_path, card_path, lint_path, binding_path

    def test_public_publish_command_consumes_readiness_before_emission(self) -> None:
        draft_path, card_path, lint_path, binding_path = self._write_inputs()
        before_facts = self.store.fact_ids()
        stdout, stderr = StringIO(), StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = cli_main(
                [
                    "--root",
                    str(self.root),
                    "--role",
                    "main",
                    "publish-interpret-document",
                    "--input",
                    str(draft_path),
                    "--interpret-card",
                    str(card_path),
                    "--lint-receipt",
                    str(lint_path),
                    "--adoption-binding",
                    str(binding_path),
                ]
            )
        self.assertEqual(code, 0, stderr.getvalue())
        published = json.loads(stdout.getvalue())
        self.assertTrue(published["published"])
        self.assertEqual(published["readiness"]["requirement"], "satisfied")
        self.assertEqual(published["truth_effect"], "none")
        self.assertEqual(self.store.fact_ids(), before_facts)
        document = self.root / published["document_relpath"]
        receipt = self.root / published["receipt_relpath"]
        self.assertEqual(document.read_bytes(), self.draft)
        self.assertTrue(receipt.is_file())

    def test_internal_only_path_skips_readiness_without_emission(self) -> None:
        result = publish_interpret_communication(
            store=self.store,
            external_communication_requested=False,
        )
        self.assertFalse(result["published"])
        self.assertEqual(result["write_effect"], "none")
        self.assertFalse(
            (self.store.reports_dir / "interpret-communications").exists()
        )

    def test_tampered_draft_fails_before_emission(self) -> None:
        with self.assertRaisesRegex(ValueError, "draft bytes mismatch"):
            publish_interpret_communication(
                store=self.store,
                external_communication_requested=True,
                adoption_binding=self.binding,
                lint_receipt=self.receipt,
                draft_bytes=self.draft + b"tampered",
                interpret_card_bytes=self.card_bytes,
            )
        self.assertFalse(
            (self.store.reports_dir / "interpret-communications").exists()
        )


if __name__ == "__main__":
    unittest.main()

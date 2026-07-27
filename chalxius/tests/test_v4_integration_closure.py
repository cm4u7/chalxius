from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from mathgraph.adoption import (
    build_adoption_plan,
    compact_adoption_binding,
)
from mathgraph.blackboard import make_edge, make_node
from mathgraph.fact_bundles import FactBundleStore, lint_expert_document
from mathgraph.model import Fact
from mathgraph.orchestrator import (
    create_round,
    ingest_return,
    validate_return,
)
from mathgraph.protocol import validate_task_card
from mathgraph.store import MathGraphStore


POLICY_REVISION = "mathgraph-0.3.0"


def workload_profile(
    *,
    candidates: int = 1,
    internal_edges: int = 0,
    atomic: bool = False,
    source_claim: bool = False,
    convention: bool = False,
    quantifier: bool = False,
) -> dict:
    return {
        "schema_version": 1,
        "policy_revision": POLICY_REVISION,
        "activity": "proof",
        "audience": "internal",
        "computation": {
            "role": "none",
            "estimated_wall_seconds": 0,
            "stage_count": 0,
            "resume_required": False,
        },
        "fact_output": {
            "candidate_count": candidates,
            "internal_dependency_count": internal_edges,
            "atomic_visibility_required": atomic,
        },
        "semantics": {
            "source_claim": source_claim,
            "convention_sensitive": convention,
            "quantifier_sensitive": quantifier,
            "terminology_sensitive": False,
        },
    }


class V4IntegrationClosureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = MathGraphStore(self.root)
        self.store.initialize(
            project_id="v4-integration-closure",
            title="V4 integration closure",
            workflow_evidence_version=4,
        )
        self.root_space = next(
            node_id
            for node_id, node in self.store.blackboard().nodes().items()
            if node["node_type"] == "space"
        )
        self.memory_counter = 0

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _planned_round(
        self,
        *,
        profile: dict | None = None,
        mode: str = "prove",
        budgets: dict | None = None,
    ) -> dict:
        self.memory_counter += 1
        memory_id = self.store.memory_add(
            {
                "kind": "direction",
                "claim": (
                    "Integration closure fixture "
                    f"{self.memory_counter}."
                ),
                "rationale": "Exercise one bound V4 return.",
                "suggested_actions": [mode],
                **(
                    {"workload_profile": profile}
                    if profile is not None
                    else {}
                ),
                **(
                    {"budgets": budgets}
                    if budgets is not None
                    else {}
                ),
            },
            actor="main",
        )
        return create_round(
            self.store,
            workers=1,
            mode=mode,
            memory_ids=[memory_id],
        )

    @staticmethod
    def _card_and_path(planned: dict) -> tuple[dict, Path]:
        assignment = planned["assignments"][0]
        card_path = Path(assignment["task_card_path"])
        return (
            json.loads(card_path.read_text(encoding="utf-8")),
            Path(assignment["return_path"]),
        )

    @staticmethod
    def _common_return(
        card: dict,
        card_path: Path,
        *,
        outcome: str,
    ) -> dict:
        return {
            "schema_version": 4,
            "policy_revision": POLICY_REVISION,
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
            "narrative_summary": "Integration closure fixture.",
        }

    def _fact_return(self, planned: dict) -> tuple[dict, dict, Path]:
        card, return_path = self._card_and_path(planned)
        card_path = Path(planned["assignments"][0]["task_card_path"])
        payload = {
            **self._common_return(
                card,
                card_path,
                outcome="fact_submission",
            ),
            "claim_relation": "proves",
            "statement": "[CLAIM:MAIN] The fixture identity holds.",
            "proof": "Both sides are definitionally identical.",
            "predecessors": [],
            "predecessor_uses": [],
            "quantifier_ledger": [],
            "convention_profile_ids": [],
            "computational_evidence": [],
            "terminology": [],
            "glossary_introduces": {},
            "external_refs": [],
            "elementary_uses": [],
            "intuition": "",
            "artifacts": [],
        }
        return payload, card, return_path

    def _bundle_return(
        self,
        planned: dict,
        *,
        fact_count: int = 2,
    ) -> tuple[dict, dict, Path]:
        card, return_path = self._card_and_path(planned)
        card_path = Path(planned["assignments"][0]["task_card_path"])
        facts = [
            Fact(
                problem_id=card["project_id"],
                author=card["worker_id"],
                predecessors=[],
                statement=f"[CLAIM:F{index}] Bundle fact {index}.",
                proof=f"Direct proof {index}.",
            ).as_submission_dict()
            for index in range(1, fact_count + 1)
        ]
        payload = {
            **self._common_return(
                card,
                card_path,
                outcome="fact_bundle_submission",
            ),
            "bundle_claim": "These candidates require atomic review.",
            "facts": facts,
            "artifacts": [],
        }
        return payload, card, return_path

    @staticmethod
    def _write_return(path: Path, payload: dict) -> None:
        path.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    def test_bound_bundle_dry_run_then_ingest_binds_receipt_and_memory(
        self,
    ) -> None:
        planned = self._planned_round(
            profile=workload_profile(candidates=2, atomic=True)
        )
        payload, card, return_path = self._bundle_return(planned)
        self._write_return(return_path, payload)

        validated = validate_return(
            self.store,
            planned["round_id"],
            card["assignment_id"],
        )
        bundle_id = validated["fact_bundle_id"]
        bundle_dir = self.store.fact_bundles().root / bundle_id
        self.assertFalse(bundle_dir.exists())

        receipt = ingest_return(
            self.store,
            planned["round_id"],
            card["assignment_id"],
            worker_final_sha256=validated["return_sha256"],
        )
        self.assertEqual(
            receipt["effect"],
            {
                "fact_bundle_id": bundle_id,
                "status": "pending_bundle_review",
            },
        )
        self.assertEqual(
            receipt["task_card_sha256"],
            payload["task_card_sha256"],
        )
        manifest = self.store.fact_bundles().manifest(bundle_id)
        self.assertEqual(manifest["worker"], card["worker_id"])
        self.assertEqual(
            manifest["provenance"],
            {
                "round_id": card["round_id"],
                "assignment_id": card["assignment_id"],
                "task_card_sha256": payload["task_card_sha256"],
                "return_sha256": validated["return_sha256"],
            },
        )
        self.assertEqual(
            self.store.memory_latest()[card["memory_id"]]["status"],
            "verifying",
        )
        self.assertEqual(self.store.fact_ids(), [])
        audit = self.store.audit()
        self.assertTrue(audit.current_ok, audit.errors)
        self.assertEqual(
            ingest_return(
                self.store,
                planned["round_id"],
                card["assignment_id"],
                worker_final_sha256=validated["return_sha256"],
            ),
            receipt,
        )

    def test_bundle_outcome_requires_atomic_card_and_two_facts(self) -> None:
        ordinary = self._planned_round()
        payload, card, return_path = self._bundle_return(ordinary)
        self._write_return(return_path, payload)
        with self.assertRaisesRegex(ValueError, "only when"):
            validate_return(
                self.store,
                ordinary["round_id"],
                card["assignment_id"],
            )

        atomic = self._planned_round(
            profile=workload_profile(candidates=2, atomic=True)
        )
        payload, card, return_path = self._bundle_return(
            atomic,
            fact_count=1,
        )
        self._write_return(return_path, payload)
        with self.assertRaisesRegex(ValueError, "at least two"):
            validate_return(
                self.store,
                atomic["round_id"],
                card["assignment_id"],
            )

    def test_bound_bundle_validates_internal_predecessor_interfaces(
        self,
    ) -> None:
        planned = self._planned_round(
            profile=workload_profile(
                candidates=2,
                internal_edges=1,
            )
        )
        payload, card, return_path = self._bundle_return(planned)
        first = Fact.from_dict(payload["facts"][0])
        use_anchor = f"[USE:{first.fact_id}:F1:bundle-step]"
        second = Fact(
            problem_id=card["project_id"],
            author=card["worker_id"],
            predecessors=[first.fact_id],
            statement="[CLAIM:F2] The second fact uses the first.",
            proof=f"Apply the first candidate. {use_anchor}",
            predecessor_uses=[
                {
                    "fact_id": first.fact_id,
                    "clause_id": "F1",
                    "use_anchor": use_anchor,
                    "used_conclusion": "Bundle fact 1.",
                    "hypothesis_witnesses": [],
                    "convention_bridge": None,
                }
            ],
        )
        payload["facts"][1] = second.as_submission_dict()
        self._write_return(return_path, payload)
        validated = validate_return(
            self.store,
            planned["round_id"],
            card["assignment_id"],
        )
        self.assertTrue(
            validated["fact_bundle_id"].startswith("factbundle-")
        )

    def test_bound_bundle_stays_unreadable_until_shared_receipt(self) -> None:
        planned = self._planned_round(
            profile=workload_profile(candidates=2, atomic=True)
        )
        payload, card, return_path = self._bundle_return(planned)
        self._write_return(return_path, payload)
        validated = validate_return(
            self.store,
            planned["round_id"],
            card["assignment_id"],
        )
        bundle_id = validated["fact_bundle_id"]
        receipt_path = return_path.with_suffix(".receipt.json")
        original_write = self.store._write_json_once

        def crash_before_receipt(path: Path, value: dict) -> None:
            if Path(path) == receipt_path:
                raise RuntimeError("simulated pre-receipt crash")
            original_write(path, value)

        with patch.object(
            self.store,
            "_write_json_once",
            side_effect=crash_before_receipt,
        ):
            with self.assertRaisesRegex(RuntimeError, "pre-receipt"):
                ingest_return(
                    self.store,
                    planned["round_id"],
                    card["assignment_id"],
                    worker_final_sha256=validated["return_sha256"],
                )
        self.assertTrue(
            (self.store.fact_bundles().root / bundle_id).is_dir()
        )
        with self.assertRaisesRegex(ValueError, "not visible"):
            self.store.fact_bundles().manifest(bundle_id)
        self.assertEqual(
            self.store.memory_latest()[card["memory_id"]]["status"],
            "open",
        )

        ingest_return(
            self.store,
            planned["round_id"],
            card["assignment_id"],
            worker_final_sha256=validated["return_sha256"],
        )
        self.assertEqual(
            self.store.fact_bundles().manifest(bundle_id)[
                "fact_bundle_id"
            ],
            bundle_id,
        )

    def test_bound_bundle_recovers_exact_pre_manifest_staging_crash(
        self,
    ) -> None:
        planned = self._planned_round(
            profile=workload_profile(candidates=2, atomic=True)
        )
        payload, card, return_path = self._bundle_return(planned)
        self._write_return(return_path, payload)
        validated = validate_return(
            self.store,
            planned["round_id"],
            card["assignment_id"],
        )
        bundle_id = validated["fact_bundle_id"]
        original_write_json = FactBundleStore._write_json_once

        def crash_before_manifest(path: Path, value: dict) -> None:
            if (
                Path(path).name == "manifest.json"
                and Path(path).parent.name == bundle_id
            ):
                raise RuntimeError("simulated bundle manifest crash")
            original_write_json(path, value)

        with patch.object(
            FactBundleStore,
            "_write_json_once",
            side_effect=crash_before_manifest,
        ):
            with self.assertRaisesRegex(RuntimeError, "manifest crash"):
                ingest_return(
                    self.store,
                    planned["round_id"],
                    card["assignment_id"],
                    worker_final_sha256=validated["return_sha256"],
                )

        bundle_dir = self.store.fact_bundles().root / bundle_id
        self.assertTrue((bundle_dir / "facts").is_dir())
        self.assertFalse((bundle_dir / "manifest.json").exists())
        self.assertFalse(
            return_path.with_suffix(".receipt.json").exists()
        )

        receipt = ingest_return(
            self.store,
            planned["round_id"],
            card["assignment_id"],
            worker_final_sha256=validated["return_sha256"],
        )
        self.assertEqual(
            receipt["effect"]["fact_bundle_id"],
            bundle_id,
        )
        self.assertEqual(
            self.store.fact_bundles().manifest(bundle_id)[
                "fact_bundle_id"
            ],
            bundle_id,
        )

    def test_legacy_direct_operator_bundle_remains_readable(self) -> None:
        facts = [
            Fact(
                problem_id=self.store.project_id(),
                author="legacy-worker",
                predecessors=[],
                statement=f"[CLAIM:L{index}] Legacy fact {index}.",
                proof="Direct.",
            )
            for index in (1,)
        ]
        bundle_id = self.store.fact_bundles().submit(
            {
                "schema_version": 4,
                "policy_revision": POLICY_REVISION,
                "project_id": self.store.project_id(),
                "facts": [
                    fact.as_submission_dict() for fact in facts
                ],
                "bundle_claim": "Legacy direct operator bundle.",
            },
            worker="operator-selected-worker",
            external_fact_exists=lambda _fact_id: False,
        )
        manifest = self.store.fact_bundles().manifest(bundle_id)
        self.assertNotIn("provenance", manifest)
        self.assertEqual(
            manifest["worker"],
            "operator-selected-worker",
        )

    def test_interpret_non_dead_end_requires_valid_mechanism_node(
        self,
    ) -> None:
        planned = self._planned_round(mode="interpret")
        card, return_path = self._card_and_path(planned)
        card_path = Path(planned["assignments"][0]["task_card_path"])
        payload = {
            **self._common_return(
                card,
                card_path,
                outcome="evidence",
            ),
            "claim": "A candidate cancellation mechanism.",
            "method": "Interpret the frozen graph.",
            "result": {"status": "candidate"},
            "artifacts": [],
            "limitations": "Exploration only.",
        }
        self._write_return(return_path, payload)
        with self.assertRaisesRegex(ValueError, "mechanism node"):
            validate_return(
                self.store,
                planned["round_id"],
                card["assignment_id"],
            )

        mechanism = make_node(
            node_type="mechanism",
            logical_key="integration-mechanism",
            payload={
                "explains_refs": [self.root_space],
                "domain_clause_refs": [],
                "convention_profile_ids": [],
                "mechanism_statement": (
                    "A cancellation may explain the observed relation."
                ),
                "falsifiable_consequences": [
                    {
                        "id": "P1",
                        "statement": (
                            "The next coefficient vanishes in the toy model."
                        ),
                        "suggested_mode": "compute",
                    }
                ],
                "known_failures": [],
                "remaining_gaps": ["No proof is claimed."],
                "truth_status": "exploration",
            },
            created_by_assignment_id=card["assignment_id"],
        )
        placement = make_edge(
            edge_type="placed_in",
            source_node_id=mechanism["node_id"],
            target_node_id=self.root_space,
            payload={},
            created_by_assignment_id=card["assignment_id"],
        )
        payload["blackboard_graph_delta"]["add_nodes"] = [mechanism]
        payload["blackboard_graph_delta"]["add_edges"] = [placement]
        self._write_return(return_path, payload)
        self.assertEqual(
            validate_return(
                self.store,
                planned["round_id"],
                card["assignment_id"],
            )["outcome"],
            "evidence",
        )

        unbound = deepcopy(payload)
        unbound["blackboard_graph_delta"]["add_nodes"][0]["payload"][
            "explains_refs"
        ] = ["bbn-" + ("f" * 64)]
        self._write_return(return_path, unbound)
        with self.assertRaisesRegex(ValueError, "frozen blackboard snapshot"):
            validate_return(
                self.store,
                planned["round_id"],
                card["assignment_id"],
            )

        broken = deepcopy(payload)
        broken["blackboard_graph_delta"]["add_nodes"][0]["payload"][
            "falsifiable_consequences"
        ] = []
        self._write_return(return_path, broken)
        with self.assertRaisesRegex(ValueError, "falsifiable"):
            validate_return(
                self.store,
                planned["round_id"],
                card["assignment_id"],
            )

        dead_end = {
            **self._common_return(
                card,
                card_path,
                outcome="dead_end",
            ),
            "claim": "No mechanism survived.",
            "method": "Interpret the frozen graph.",
            "failure_mode": "No falsifiable consequence was found.",
            "what_remains_open": "The original explanation remains open.",
            "artifacts": [],
        }
        self._write_return(return_path, dead_end)
        self.assertEqual(
            validate_return(
                self.store,
                planned["round_id"],
                card["assignment_id"],
            )["outcome"],
            "dead_end",
        )

    def test_domain_and_required_quantifier_gates_run_on_fact_returns(
        self,
    ) -> None:
        domain_round = self._planned_round()
        payload, card, return_path = self._fact_return(domain_round)
        payload["statement"] = (
            "[CLAIM:DOMAIN-BASE] Only the base clause is present."
        )
        self._write_return(return_path, payload)
        with self.assertRaisesRegex(ValueError, "DOMAIN-"):
            validate_return(
                self.store,
                domain_round["round_id"],
                card["assignment_id"],
            )

        quantified_round = self._planned_round(
            profile=workload_profile(quantifier=True)
        )
        payload, card, return_path = self._fact_return(
            quantified_round
        )
        self._write_return(return_path, payload)
        with self.assertRaisesRegex(ValueError, "nonempty"):
            validate_return(
                self.store,
                quantified_round["round_id"],
                card["assignment_id"],
            )

    def test_required_source_and_convention_gates_need_card_bindings(
        self,
    ) -> None:
        planned = self._planned_round()
        card, _ = self._card_and_path(planned)

        source_card = deepcopy(card)
        source_card["adoption_plan"] = compact_adoption_binding(
            build_adoption_plan(
                workload_profile(source_claim=True)
            )
        )
        with self.assertRaisesRegex(ValueError, "source_claim_id"):
            validate_task_card(source_card)

        convention_card = deepcopy(card)
        convention_card["adoption_plan"] = compact_adoption_binding(
            build_adoption_plan(
                workload_profile(convention=True)
            )
        )
        with self.assertRaisesRegex(
            ValueError,
            "convention_profile_ids",
        ):
            validate_task_card(convention_card)

    def test_prompt_and_zero_wall_budget_preserve_advisory_estimate(
        self,
    ) -> None:
        planned = self._planned_round(
            mode="compute",
            budgets={"max_wall_seconds": 900},
        )
        assignment = planned["assignments"][0]
        prompt = Path(assignment["prompt_path"]).read_text(
            encoding="utf-8"
        )
        self.assertIn("references/agent_protocol_v4.md", prompt)
        self.assertNotIn(
            "multi_agent_adapter.md#launch-workers",
            prompt,
        )

        card, _ = self._card_and_path(planned)
        self.assertEqual(
            card["adoption_plan"]["workload_profile"]["computation"][
                "estimated_wall_seconds"
            ],
            900,
        )
        self.assertEqual(card["budgets"]["max_wall_seconds"], 0)
        invalid = deepcopy(card)
        invalid["budgets"]["max_wall_seconds"] = 1
        with self.assertRaisesRegex(ValueError, "exactly 0"):
            validate_task_card(invalid)

    def test_expert_document_lint_calls_quantifier_export_lint(self) -> None:
        errors = lint_expert_document(
            "Use one uniform canonical witness independent of the point.",
            claim_card={
                "terminology": [],
                "quantifier_ledger": [
                    {
                        "id": "Q-dependent",
                        "depends_on": ["Q-base"],
                    }
                ],
            },
        )
        self.assertTrue(
            any("dependent witness Q-dependent" in error for error in errors)
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from mathgraph.contracts import sha256_bytes, sha256_json
from mathgraph.store import MathGraphStore


class ResearchTwoSubroundTests(unittest.TestCase):
    @staticmethod
    def _store(root: Path) -> MathGraphStore:
        store = MathGraphStore(root)
        store.initialize(
            project_id="research-two-subround",
            title="Research two subround",
            workflow_evidence_version=5,
        )
        return store

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
    def _artifact(store: MathGraphStore, path: Path, role: str) -> dict[str, str]:
        return {
            "path": path.relative_to(store.root).as_posix(),
            "sha256": sha256_bytes(path.read_bytes()),
            "role": role,
        }

    def _design_round(
        self,
        store: MathGraphStore,
    ) -> tuple[dict[str, object], dict[str, str], bytes, bytes]:
        lifecycle = store.v5_lifecycle()
        research = lifecycle.add_research(
            {
                "kind": "computation",
                "claim": "Compute one exact finite sum from a reviewable program.",
            },
            actor="main",
        )
        planned = lifecycle.create_production_round(
            workers=1,
            mode="compute",
            research_ids=[research["research_id"]],
            host_task_scope_id="research-design-host",
        )
        assignment = planned["assignments"][0]
        card = json.loads(
            Path(str(assignment["task_card_path"])).read_text(encoding="utf-8")
        )
        self.assertEqual(card["research_cycle"]["subround"], "production")
        self.assertEqual(card["assurance_contract"]["computation_stage_count"], 0)
        artifact_dir = store.root / assignment["artifact_dir_relpath"]
        artifact_dir.mkdir(parents=True, exist_ok=True)
        source_bytes = b"# FORMULA_STAGE_1\nresult = sum(range(4))\n"
        dependency_bytes = b'{"python":"stdlib-only","version":"3.13"}\n'
        source_path = artifact_dir / "program.py"
        design_path = artifact_dir / "program-math-design.md"
        dependency_path = artifact_dir / "dependencies.json"
        source_path.write_bytes(source_bytes)
        design_path.write_text(
            "The program computes the exact integer sum over 0 <= i <= 3.\n",
            encoding="utf-8",
        )
        dependency_path.write_bytes(dependency_bytes)
        artifacts = [
            self._artifact(store, dependency_path, "computation_dependencies"),
            self._artifact(store, design_path, "computation_design"),
            self._artifact(store, source_path, "computation_source"),
        ]
        hashes = {item["role"]: item["sha256"] for item in artifacts}
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
            "outcome": "evidence",
            "claim": "The exact core program and its mathematical projection are ready for review.",
            "content": "No formal computation has been executed in this return.",
            "narrative": {
                "rationale": "Review code before paying execution cost.",
                "summary": "Core code is frozen.",
                "intuition": "The supervisor sees the exact future executable bytes.",
                "limitations": "There is no computed result yet.",
            },
            "artifacts": artifacts,
            "obligation_dispositions": [
                {
                    "obligation_id": obligation["obligation_id"],
                    "status": "complete",
                    "witness_artifact_sha256s": sorted(hashes.values()),
                    "rationale": "The three exact design artifacts are hash-bound.",
                }
                for obligation in card["assurance_contract"]["obligations"]
            ],
            "computation_manifest": None,
            "research_assurance": self._blank_assurance(),
        }
        return_path = Path(str(assignment["return_path"]))
        return_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        receipt = lifecycle.ingest_return(
            round_id=planned["round_id"],
            assignment_id=assignment["assignment_id"],
            worker_final_sha256=sha256_bytes(return_path.read_bytes()),
        )
        self.assertEqual(receipt["status"], "ingested", receipt)
        self.assertNotIn("program_math_review_research_id", receipt)
        return planned, assignment, source_bytes, dependency_bytes

    def _ingest_supervision(
        self,
        store: MathGraphStore,
        source_round_id: str,
    ) -> tuple[dict[str, object], dict[str, object]]:
        lifecycle = store.v5_lifecycle()
        supervision = lifecycle.create_supervision_round(
            source_round_id,
            host_task_scope_id="research-supervision-host",
        )
        self.assertEqual(
            supervision["research_cycle"]["supervisor_scopes"],
            ["program_math"],
        )
        assignment = supervision["assignments"][0]
        card = json.loads(
            Path(str(assignment["task_card_path"])).read_text(encoding="utf-8")
        )
        self.assertEqual(card["work_mode"], "refute")
        self.assertIn(
            "computation_source",
            {
                role.split(":", 1)[-1]
                for role in card["assurance_contract"][
                    "related_artifact_roles"
                ]
            },
        )
        artifact_dir = store.root / assignment["artifact_dir_relpath"]
        artifact_dir.mkdir(parents=True, exist_ok=True)
        report_path = artifact_dir / "supervision-report.md"
        report_path.write_text(
            "No obstruction found in the exact formula, domain, dependency, and code projection.\n",
            encoding="utf-8",
        )
        report = self._artifact(store, report_path, "research_supervision_report")
        payload = {
            "schema_version": 5,
            "project_id": store.project_id(),
            "round_id": supervision["round_id"],
            "assignment_id": assignment["assignment_id"],
            "worker_id": assignment["worker_id"],
            "task_card_sha256": assignment["task_card_sha256"],
            "blackboard_snapshot_sha256": assignment[
                "blackboard_snapshot_sha256"
            ],
            "outcome": "challenge",
            "claim": "The frozen computation design has no identified program-math obstruction.",
            "content": "The report attacks the exact source, dependencies, and design.",
            "narrative": {
                "rationale": "Independent supervision precedes execution.",
                "summary": "No bounded obstruction found.",
                "intuition": "The executable and reviewed object are identical.",
                "limitations": "This is Research supervision, not Fact authority.",
            },
            "artifacts": [report],
            "obligation_dispositions": [
                {
                    "obligation_id": obligation["obligation_id"],
                    "status": "complete",
                    "witness_artifact_sha256s": [report["sha256"]],
                    "rationale": "The exact supervision report covers the frozen receipt.",
                }
                for obligation in card["assurance_contract"]["obligations"]
            ],
            "computation_manifest": None,
            "research_assurance": self._blank_assurance(),
        }
        if "adverse_routing" in card:
            payload["attack_learning"] = None
        return_path = Path(str(assignment["return_path"]))
        return_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        receipt = lifecycle.ingest_return(
            round_id=supervision["round_id"],
            assignment_id=assignment["assignment_id"],
            worker_final_sha256=sha256_bytes(return_path.read_bytes()),
        )
        self.assertEqual(receipt["status"], "ingested", receipt)
        return supervision, receipt

    def _execution_payload(
        self,
        store: MathGraphStore,
        execution: dict[str, object],
        source_bytes: bytes,
        dependency_bytes: bytes,
    ) -> dict[str, object]:
        assignment = execution["assignments"][0]
        card = json.loads(
            Path(str(assignment["task_card_path"])).read_text(encoding="utf-8")
        )
        artifact_dir = store.root / assignment["artifact_dir_relpath"]
        artifact_dir.mkdir(parents=True, exist_ok=True)
        paths = {
            "computation_source": artifact_dir / "program.py",
            "computation_dependencies": artifact_dir / "dependencies.json",
            "computation_log": artifact_dir / "execution.log",
            "computation_output": artifact_dir / "output.json",
            "semantic_witness": artifact_dir / "semantic-witness.json",
            "independent_check": artifact_dir / "independent-check.json",
        }
        paths["computation_source"].write_bytes(source_bytes)
        paths["computation_dependencies"].write_bytes(dependency_bytes)
        paths["computation_log"].write_text(
            "command=python3 program.py\nexit_status=0\n",
            encoding="utf-8",
        )
        paths["computation_output"].write_text('{"result":6}\n', encoding="utf-8")
        paths["semantic_witness"].write_text(
            '{"domain":"0<=i<4","representation":"integer"}\n',
            encoding="utf-8",
        )
        paths["independent_check"].write_text(
            '{"metamorphic":"prefix-plus-endpoint","status":"pass"}\n',
            encoding="utf-8",
        )
        artifacts = [
            self._artifact(store, path, role) for role, path in paths.items()
        ]
        hashes = {item["role"]: item["sha256"] for item in artifacts}
        obligation = card["assurance_contract"]["obligations"][0]
        formula = "c_3 = sum_{i=0}^{3} i"
        return {
            "schema_version": 5,
            "project_id": store.project_id(),
            "round_id": execution["round_id"],
            "assignment_id": assignment["assignment_id"],
            "worker_id": assignment["worker_id"],
            "task_card_sha256": assignment["task_card_sha256"],
            "blackboard_snapshot_sha256": assignment[
                "blackboard_snapshot_sha256"
            ],
            "outcome": "evidence",
            "claim": "The supervised finite sum equals 6.",
            "content": "The exact supervised source produced the bound output.",
            "narrative": {
                "rationale": "Exercise the preexecution code gate.",
                "summary": "Exact finite sum result.",
                "intuition": "Review and execution share source hashes.",
                "limitations": "The result remains nontruth Research.",
            },
            "artifacts": artifacts,
            "obligation_dispositions": [
                {
                    "obligation_id": obligation["obligation_id"],
                    "status": "complete",
                    "witness_artifact_sha256s": [
                        hashes["computation_output"],
                        hashes["computation_source"],
                    ],
                    "rationale": "Exact source and output bytes are bound.",
                }
            ],
            "computation_manifest": {
                "stage_count": 1,
                "entries": [
                    {
                        "obligation_id": obligation["obligation_id"],
                        "source_artifact_sha256": hashes["computation_source"],
                        "output_artifact_sha256": hashes["computation_output"],
                        "command": ["python3", "program.py"],
                        "runtime": {"implementation": "CPython", "version": "3.13"},
                        "role": "supporting",
                        "manual_contract": "The loop implements the exact finite sum.",
                    }
                ],
            },
            "research_assurance": {
                **self._blank_assurance(),
                "program_math_alignments": [
                    {
                        "stage_index": 1,
                        "obligation_id": obligation["obligation_id"],
                        "formula_projection": {
                            "formula_literal": formula,
                            "formula_sha256": sha256_json(formula),
                            "source_locator": "frozen computation design",
                            "code_artifact_sha256": hashes["computation_source"],
                            "code_anchor": "FORMULA_STAGE_1",
                            "sign_and_convention_map": [
                                "inclusive upper bound 3 maps to range(4)"
                            ],
                        },
                        "domain_projection": {
                            "mathematical_domain": "integers 0 <= i <= 3",
                            "code_iteration_domain": "range(4)",
                            "boundary_cases": ["i=0", "i=3"],
                            "witness_artifact_sha256": hashes["semantic_witness"],
                        },
                        "representation_projection": {
                            "mathematical_objects": ["integer coefficient"],
                            "code_types": ["Python int"],
                            "identity_and_multiplicity_policy": "Each index occurs once.",
                            "witness_artifact_sha256": hashes["semantic_witness"],
                        },
                        "approximation_budget": {
                            "mode": "exact",
                            "required_order": None,
                            "implemented_order": None,
                            "precision_or_error_bound": "Exact integer arithmetic.",
                            "derivation_artifact_sha256": hashes["semantic_witness"],
                        },
                        "output_interpretation": {
                            "output_artifact_sha256": hashes["computation_output"],
                            "claimed_quantity": "coefficient c_3",
                            "units_and_conventions": "dimensionless positive sum",
                        },
                        "independent_checks": [
                            {
                                "kind": "metamorphic_relation",
                                "artifact_sha256": hashes["independent_check"],
                                "finding": "Adding endpoint 3 increases the prefix by 3.",
                            }
                        ],
                    }
                ],
            },
        }

    def test_code_is_supervised_before_exact_execution_and_output_is_rechecked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            design, assignment, source_bytes, dependency_bytes = self._design_round(store)
            _, supervision_receipt = self._ingest_supervision(
                store, design["round_id"]
            )
            with self.assertRaisesRegex(ValueError, "explicitly disposed"):
                lifecycle.create_computation_execution_round(
                    design["round_id"], assignment["assignment_id"]
                )
            lifecycle.update_research(
                supervision_receipt["research_id"],
                status="resolved_no_obstruction",
                actor="main",
                note="The exact core source and dependencies survived supervision.",
            )
            execution = lifecycle.create_computation_execution_round(
                design["round_id"],
                assignment["assignment_id"],
                host_task_scope_id="research-execution-host",
            )
            execution_card = json.loads(
                Path(str(execution["assignments"][0]["task_card_path"])).read_text(
                    encoding="utf-8"
                )
            )
            approved = execution_card["mathematical_state"][
                "source_research_dossier"
            ]["metadata"]["approved_computation_execution"]
            self.assertEqual(
                {item["role"] for item in approved["design_artifacts"]},
                {
                    "computation_dependencies",
                    "computation_design",
                    "computation_source",
                },
            )
            payload = self._execution_payload(
                store, execution, source_bytes, dependency_bytes
            )
            return_path = Path(str(execution["assignments"][0]["return_path"]))
            return_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
            valid = lifecycle.preflight_return(
                round_id=execution["round_id"],
                assignment_id=execution["assignments"][0]["assignment_id"],
            )
            self.assertTrue(valid["valid"])
            receipt = lifecycle.ingest_return(
                round_id=execution["round_id"],
                assignment_id=execution["assignments"][0]["assignment_id"],
                worker_final_sha256=valid["return_sha256"],
            )
            self.assertNotIn("program_math_review_research_id", receipt)
            output_supervision = lifecycle.create_supervision_round(
                execution["round_id"]
            )
            output_card = json.loads(
                Path(
                    str(output_supervision["assignments"][0]["task_card_path"])
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(
                set(
                    output_card["mathematical_state"]["source_research_dossier"][
                        "metadata"
                    ]["required_related_artifact_roles"]
                ),
                {
                    "computation_dependencies",
                    "computation_design",
                    "computation_log",
                    "computation_output",
                    "computation_source",
                },
            )

    def test_changed_code_is_rejected_and_requires_a_new_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            design, assignment, source_bytes, dependency_bytes = self._design_round(store)
            _, supervision_receipt = self._ingest_supervision(
                store, design["round_id"]
            )
            lifecycle.update_research(
                supervision_receipt["research_id"],
                status="resolved_no_obstruction",
                actor="main",
            )
            execution = lifecycle.create_computation_execution_round(
                design["round_id"], assignment["assignment_id"]
            )
            payload = self._execution_payload(
                store, execution, source_bytes, dependency_bytes
            )
            source_artifact = next(
                item
                for item in payload["artifacts"]
                if item["role"] == "computation_source"
            )
            source_path = store.root / source_artifact["path"]
            source_path.write_text(
                "# FORMULA_STAGE_1\nresult = sum(range(5))\n",
                encoding="utf-8",
            )
            source_artifact["sha256"] = sha256_bytes(source_path.read_bytes())
            manifest_entry = payload["computation_manifest"]["entries"][0]
            manifest_entry["source_artifact_sha256"] = source_artifact["sha256"]
            payload["obligation_dispositions"][0]["witness_artifact_sha256s"][1] = (
                source_artifact["sha256"]
            )
            payload["research_assurance"]["program_math_alignments"][0][
                "formula_projection"
            ]["code_artifact_sha256"] = source_artifact["sha256"]
            return_path = Path(str(execution["assignments"][0]["return_path"]))
            return_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "changed supervised source"):
                lifecycle.preflight_return(
                    round_id=execution["round_id"],
                    assignment_id=execution["assignments"][0]["assignment_id"],
                )

    def test_execution_gate_rejects_missing_supervision_disposition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            design, assignment, _, _ = self._design_round(store)
            self._ingest_supervision(store, design["round_id"])
            rounds_before = {item.name for item in store.rounds_dir.iterdir()}
            with self.assertRaisesRegex(ValueError, "explicitly disposed"):
                lifecycle.create_computation_execution_round(
                    design["round_id"], assignment["assignment_id"]
                )
            self.assertEqual(
                rounds_before, {item.name for item in store.rounds_dir.iterdir()}
            )

    def test_supervisor_finding_opens_copy_on_write_mode_preserving_repair(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            design, _, _, _ = self._design_round(store)
            _, supervision_receipt = self._ingest_supervision(
                store, design["round_id"]
            )
            _, descriptors = lifecycle._source_round_receipt_descriptors(
                design["round_id"]
            )
            design_result_id = descriptors[0]["result_research_id"]
            repair = lifecycle.create_repair_round(
                design_result_id,
                trigger_research_id=supervision_receipt["research_id"],
            )
            self.assertEqual(repair["repair_of_research_id"], design_result_id)
            self.assertEqual(
                repair["trigger_research_id"], supervision_receipt["research_id"]
            )
            self.assertEqual(repair["research_cycle"]["subround"], "production")
            repair_card = json.loads(
                Path(str(repair["assignments"][0]["task_card_path"])).read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(repair_card["work_mode"], "compute")
            self.assertEqual(
                repair_card["assurance_contract"]["computation_stage_count"], 0
            )

    def test_first_wave_refute_attacks_the_proposition_and_is_itself_supervised(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            research = lifecycle.add_research(
                {
                    "kind": "direction",
                    "claim": "For every integer n under H, the bounded conclusion T holds.",
                },
                actor="main",
            )
            production = lifecycle.create_production_round(
                workers=1,
                mode="refute",
                research_ids=[research["research_id"]],
            )
            assignment = production["assignments"][0]
            prompt = Path(str(assignment["prompt_path"])).read_text(encoding="utf-8")
            self.assertIn("assigned proposition T under its exact hypotheses H", prompt)
            self.assertIn("cannot see or attack mutable same-subround peer outputs", prompt)
            card = json.loads(
                Path(str(assignment["task_card_path"])).read_text(encoding="utf-8")
            )
            payload: dict[str, object] = {
                "schema_version": 5,
                "project_id": store.project_id(),
                "round_id": production["round_id"],
                "assignment_id": assignment["assignment_id"],
                "worker_id": assignment["worker_id"],
                "task_card_sha256": assignment["task_card_sha256"],
                "blackboard_snapshot_sha256": assignment[
                    "blackboard_snapshot_sha256"
                ],
                "outcome": "challenge",
                "claim": "A boundary instance exposes an unresolved H-to-T gap.",
                "content": "The exact boundary attack is recorded in the argument.",
                "narrative": {
                    "rationale": "Search for H and not-T rather than proving a nearby claim.",
                    "summary": "One bounded counterexample.",
                    "intuition": "The endpoint is load-bearing.",
                    "limitations": "Only the stated boundary is refuted.",
                },
                "artifacts": [],
                "obligation_dispositions": [],
                "computation_manifest": None,
                "research_assurance": self._blank_assurance(),
            }
            if "adverse_routing" in card:
                payload["attack_learning"] = None
            return_path = Path(str(assignment["return_path"]))
            return_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
            receipt = lifecycle.ingest_return(
                round_id=production["round_id"],
                assignment_id=assignment["assignment_id"],
                worker_final_sha256=sha256_bytes(return_path.read_bytes()),
            )
            self.assertEqual(receipt["status"], "ingested", receipt)
            supervision = lifecycle.create_supervision_round(production["round_id"])
            self.assertEqual(
                supervision["research_cycle"]["supervisor_scopes"],
                ["proof_logic"],
            )
            supervisor_card = json.loads(
                Path(
                    str(supervision["assignments"][0]["task_card_path"])
                ).read_text(encoding="utf-8")
            )
            binding = supervisor_card["mathematical_state"][
                "source_research_dossier"
            ]["metadata"]["research_supervision"]
            self.assertEqual(binding["supervisor_scope"], "proof_logic")
            self.assertEqual(
                [item["result_research_id"] for item in binding["source_receipts"]],
                [receipt["research_id"]],
            )

    def test_legacy_round_is_not_backfilled(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            legacy_source = lifecycle.add_research(
                {"kind": "computation", "claim": "Legacy direct planner fixture."},
                actor="main",
            )
            legacy = lifecycle.create_round(
                workers=1,
                mode="compute",
                research_ids=[legacy_source["research_id"]],
            )
            legacy_card = json.loads(
                Path(str(legacy["assignments"][0]["task_card_path"])).read_text(
                    encoding="utf-8"
                )
            )
            self.assertNotIn("research_cycle", legacy_card)
            self.assertEqual(
                legacy_card["assurance_contract"]["computation_stage_count"], 1
            )
            with self.assertRaisesRegex(ValueError, "prospective production"):
                lifecycle.create_supervision_round(legacy["round_id"])

    def test_supervision_scope_errors_write_no_round(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            design, _, _, _ = self._design_round(store)
            rounds_before = {item.name for item in store.rounds_dir.iterdir()}
            with self.assertRaisesRegex(ValueError, "one to three"):
                lifecycle.create_supervision_round(
                    design["round_id"],
                    supervisor_scopes=[
                        "program_math",
                        "proof_logic",
                        "source_scope",
                        "integration",
                    ],
                )
            self.assertEqual(
                rounds_before, {item.name for item in store.rounds_dir.iterdir()}
            )
            with self.assertRaisesRegex(ValueError, "do not apply"):
                lifecycle.create_supervision_round(
                    design["round_id"], supervisor_scopes=["proof_logic"]
                )

    def test_supervision_binding_tamper_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            design, _, _, _ = self._design_round(store)
            supervision = lifecycle.create_supervision_round(design["round_id"])
            card = json.loads(
                Path(
                    str(supervision["assignments"][0]["task_card_path"])
                ).read_text(encoding="utf-8")
            )
            binding = copy.deepcopy(
                card["mathematical_state"]["source_research_dossier"][
                    "metadata"
                ]["research_supervision"]
            )
            binding["source_receipts"][0]["return_sha256"] = "0" * 64
            binding["source_receipts_sha256"] = sha256_json(
                binding["source_receipts"]
            )
            with self.assertRaisesRegex(ValueError, "coverage drifted"):
                lifecycle._validate_research_supervision_binding(binding)


if __name__ == "__main__":
    unittest.main()

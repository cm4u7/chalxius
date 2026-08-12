from __future__ import annotations

import copy
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from chx_ledger import (
    close_ledger,
    record_finding,
    record_issue,
    reconcile_finding,
    start_ledger,
)
from mathgraph.contracts import sha256_bytes, sha256_json
from mathgraph.model import Fact
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
    def _architecture_issue() -> dict[str, object]:
        return {
            "classification": "worker architecture observation handoff",
            "causation": "caused",
            "mechanism_type": "interface_contract",
            "mechanism": (
                "A card-bound worker finding needs an explicit lifecycle handoff."
            ),
            "trigger": "Main ingests the matching mathematical worker return.",
            "observed_effect": (
                "Without projection the reusable architecture observation is lost."
            ),
            "mathematical_effect": "none",
            "current_workaround": "Main copies the worker report manually.",
            "upgrade_requirement": (
                "Project genuine findings into one nontruth CHX observation inbox."
            ),
            "audit_anchors": [
                "scripts/mathgraph/v5_lifecycle.py:_capture_worker_chx_observations"
            ],
        }

    @staticmethod
    def _artifact(store: MathGraphStore, path: Path, role: str) -> dict[str, str]:
        return {
            "path": path.relative_to(store.root).as_posix(),
            "sha256": sha256_bytes(path.read_bytes()),
            "role": role,
        }

    @staticmethod
    def _candidate_payload(
        store: MathGraphStore,
        research_id: str,
    ) -> dict[str, object]:
        fact = Fact(
            problem_id=store.project_id(),
            author="candidate-producer",
            predecessors=[],
            statement="[CLAIM:ROOT] Candidate supervision gate fixture.",
            proof="This fixture exercises the Research-to-Candidate boundary.",
        )
        return {
            "schema_version": 5,
            "bundle_claim": fact.statement,
            "candidates": [fact.as_submission_dict()],
            "research_entry_ids": [research_id],
            "claim_relation": "proves",
            "artifacts": [],
            "verification_plan": {
                "mode": "closed_capsule",
                "authorized_artifact_roles": [],
                "required_checks": [
                    "mathematical",
                    "typing",
                    "scope",
                    "source_and_applicability",
                    "predecessor_interfaces",
                    "computation_replay",
                    "challenge_dispositions",
                    "assurance_scope",
                ],
            },
            "requested_assurance": {
                "validation_subject": {
                    "kind": "theorem",
                    "subject_id": fact.fact_id,
                    "artifact_sha256": None,
                    "load_bearing_node_ids": [],
                },
                "validation_granularity": "monolithic_theorem",
                "coverage": [],
            },
            "challenge_dispositions": [],
            "paper_evidence_refs": [],
            "adverse_actor_ids": [],
        }

    def _design_round(
        self,
        store: MathGraphStore,
        *,
        invalidate_source: bool = False,
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
            "outcome": "challenge" if invalidate_source else "evidence",
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
            "research_assurance": {
                **self._blank_assurance(),
                "route_invalidations": (
                    [research["research_id"]] if invalidate_source else []
                ),
            },
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

    def _ingest_design_assignment(
        self,
        store: MathGraphStore,
        planned: dict[str, object],
        assignment: dict[str, object],
    ) -> tuple[bytes, bytes, dict[str, object]]:
        lifecycle = store.v5_lifecycle()
        card = json.loads(
            Path(str(assignment["task_card_path"])).read_text(encoding="utf-8")
        )
        artifact_dir = store.root / str(assignment["artifact_dir_relpath"])
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
            "claim": "One exact computation design is ready for component review.",
            "content": "No formal computation has been executed in this return.",
            "narrative": {
                "rationale": "Review code before execution.",
                "summary": "Component-local code is frozen.",
                "intuition": "Each logical component owns its exact executable.",
                "limitations": "There is no computed result yet.",
            },
            "artifacts": artifacts,
            "obligation_dispositions": [
                {
                    "obligation_id": obligation["obligation_id"],
                    "status": "complete",
                    "witness_artifact_sha256s": sorted(hashes.values()),
                    "rationale": "The exact design artifacts are hash-bound.",
                }
                for obligation in card["assurance_contract"]["obligations"]
            ],
            "computation_manifest": None,
            "research_assurance": self._blank_assurance(),
        }
        return_path = Path(str(assignment["return_path"]))
        return_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        receipt = lifecycle.ingest_return(
            round_id=str(planned["round_id"]),
            assignment_id=str(assignment["assignment_id"]),
            worker_final_sha256=sha256_bytes(return_path.read_bytes()),
        )
        self.assertEqual(receipt["status"], "ingested", receipt)
        return source_bytes, dependency_bytes, receipt

    def _ingest_plain_assignment(
        self,
        store: MathGraphStore,
        planned: dict[str, object],
        assignment: dict[str, object],
        *,
        outcome: str = "proof",
    ) -> dict[str, object]:
        lifecycle = store.v5_lifecycle()
        card = json.loads(
            Path(str(assignment["task_card_path"])).read_text(encoding="utf-8")
        )
        artifact_dir = store.root / str(assignment["artifact_dir_relpath"])
        artifact_dir.mkdir(parents=True, exist_ok=True)
        report_path = artifact_dir / "worker-report.md"
        report_path.write_text(
            "The bounded constructive output and its declared scope are frozen.\n",
            encoding="utf-8",
        )
        report = self._artifact(store, report_path, "research_report")
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
            "outcome": outcome,
            "claim": "One exact constructive Research output is ready for supervision.",
            "content": "This fixture binds one report and changes no Fact authority.",
            "narrative": {
                "rationale": "Freeze a component output before supervision.",
                "summary": "One assignment is complete.",
                "intuition": "Unrelated work need not delay review.",
                "limitations": "This is nontruth Research only.",
            },
            "artifacts": [report],
            "obligation_dispositions": [
                {
                    "obligation_id": obligation["obligation_id"],
                    "status": "complete",
                    "witness_artifact_sha256s": [report["sha256"]],
                    "rationale": "The exact report is hash-bound.",
                }
                for obligation in card["assurance_contract"]["obligations"]
            ],
            "computation_manifest": None,
            "research_assurance": self._blank_assurance(),
        }
        return_path = Path(str(assignment["return_path"]))
        return_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        receipt = lifecycle.ingest_return(
            round_id=str(planned["round_id"]),
            assignment_id=str(assignment["assignment_id"]),
            worker_final_sha256=sha256_bytes(return_path.read_bytes()),
        )
        self.assertEqual(receipt["status"], "ingested", receipt)
        return receipt

    def _ingest_supervision(
        self,
        store: MathGraphStore,
        source_round_id: str,
        *,
        source_component_id: str | None = None,
    ) -> tuple[dict[str, object], dict[str, object]]:
        lifecycle = store.v5_lifecycle()
        supervision = lifecycle.create_supervision_round(
            source_round_id,
            source_component_id=source_component_id,
            supervisor_scopes=["program_math"],
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

    def test_multi_component_computation_uses_assignment_local_supervision(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            first = lifecycle.add_research(
                {"kind": "computation", "claim": "Independent computation A."},
                actor="main",
            )
            second = lifecycle.add_research(
                {"kind": "computation", "claim": "Independent computation B."},
                actor="main",
            )
            design = lifecycle.create_production_round(
                workers=2,
                mode="compute",
                research_ids=[first["research_id"], second["research_id"]],
                host_task_scope_id="multi-component-design-host",
            )
            self.assertEqual(len(design["supervision_components"]), 2)
            first_assignment, second_assignment = design["assignments"]
            self._ingest_design_assignment(store, design, first_assignment)
            self._ingest_design_assignment(store, design, second_assignment)
            first_component = next(
                component
                for component in design["supervision_components"]
                if first_assignment["assignment_id"]
                in component["assignment_ids"]
            )
            _, supervision_receipt = self._ingest_supervision(
                store,
                design["round_id"],
                source_component_id=first_component["component_id"],
            )
            lifecycle.update_research(
                supervision_receipt["research_id"],
                status="resolved_no_obstruction",
                actor="main",
                note="The first component's exact code survived review.",
            )
            execution = lifecycle.create_computation_execution_round(
                design["round_id"],
                first_assignment["assignment_id"],
                host_task_scope_id="multi-component-execution-host",
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
                approved["design_assignment_id"],
                first_assignment["assignment_id"],
            )
            self.assertNotEqual(
                approved["design_assignment_id"],
                second_assignment["assignment_id"],
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

    def test_compute_design_custom_roles_fail_before_round_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            research = lifecycle.add_research(
                {
                    "kind": "computation",
                    "claim": "Design one adapter without executing it.",
                    "obligations": [
                        {
                            "obligation_id": "adapter-custom-role",
                            "description": "Return task-specific adapter files.",
                            "required_artifact_roles": [
                                "adapter_design",
                                "adapter_source",
                            ],
                            "evidence_types": ["program_math_design"],
                            "not_applicable_allowed": False,
                        }
                    ],
                },
                actor="main",
            )
            historical_projection = lifecycle._mode_architecture_signature(
                research,
                work_mode="compute",
                adverse_routing_enabled=False,
                computation_design_only=True,
            )
            historical_roles = {
                role
                for obligation in historical_projection[
                    "assurance_contract_without_artifact_roles"
                ]["obligations"]
                for role in obligation["required_artifact_roles"]
            }
            self.assertTrue(
                {"adapter_design", "adapter_source"}.issubset(
                    historical_roles
                )
            )
            before = (
                set(store.rounds_dir.iterdir())
                if store.rounds_dir.exists()
                else set()
            )
            with self.assertRaisesRegex(
                ValueError,
                "unsupported artifact roles: adapter_design, adapter_source",
            ):
                lifecycle.create_production_round(
                    workers=1,
                    mode="compute",
                    research_ids=[research["research_id"]],
                    host_task_scope_id="unsatisfiable-compute-role-card",
                )
            after = (
                set(store.rounds_dir.iterdir())
                if store.rounds_dir.exists()
                else set()
            )
            self.assertEqual(before, after)

    def test_execution_gate_rejects_missing_supervision_disposition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            design, assignment, _, _ = self._design_round(store)
            self._ingest_supervision(store, design["round_id"])
            rounds_before = {item.name for item in store.rounds_dir.iterdir()}
            with patch.object(
                lifecycle,
                "_canonical_design_artifacts",
                side_effect=AssertionError(
                    "design closure must not run before disposition rejection"
                ),
            ):
                with self.assertRaisesRegex(ValueError, "explicitly disposed"):
                    lifecycle.create_computation_execution_round(
                        design["round_id"], assignment["assignment_id"]
                    )
            self.assertEqual(
                rounds_before, {item.name for item in store.rounds_dir.iterdir()}
            )

    def test_ingest_projects_only_genuine_card_bound_chx_findings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            research = lifecycle.add_research(
                {"kind": "direction", "claim": "Produce one bounded lemma."},
                actor="main",
            )
            planned = lifecycle.create_production_round(
                workers=1,
                mode="prove",
                research_ids=[research["research_id"]],
            )
            assignment = planned["assignments"][0]
            started = start_ledger(
                project_root=store.root,
                task="Exercise card-bound CHX observation projection.",
                run_id="run-card-bound-observation",
                task_card=assignment["task_card_path"],
            )
            ledger = Path(started["ledger_path"])
            first_event = json.loads(
                ledger.read_text(encoding="utf-8").splitlines()[0]
            )
            self.assertEqual(
                first_event["task_card_binding"],
                {
                    "round_id": planned["round_id"],
                    "assignment_id": assignment["assignment_id"],
                    "task_card_sha256": assignment["task_card_sha256"],
                    "task_card_semantic_sha256": json.loads(
                        Path(str(assignment["task_card_path"])).read_text(
                            encoding="utf-8"
                        )
                    )["task_card_semantic_sha256"],
                },
            )
            record_issue(ledger, self._architecture_issue())
            close_ledger(ledger)

            receipt = self._ingest_plain_assignment(store, planned, assignment)
            observation_ids = receipt["architecture_observation_ids"]
            self.assertEqual(len(observation_ids), 1)
            observation_path = (
                store.root
                / "chx-observations"
                / "by-id"
                / f"{observation_ids[0]}.json"
            )
            observation = json.loads(
                observation_path.read_text(encoding="utf-8")
            )
            self.assertEqual(observation["round_id"], planned["round_id"])
            self.assertEqual(
                observation["assignment_id"], assignment["assignment_id"]
            )
            self.assertEqual(observation["truth_effect"], "none")
            self.assertEqual(observation["project_effect"], "none")

    def test_empty_card_bound_chx_ledger_creates_no_observation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            research = lifecycle.add_research(
                {"kind": "direction", "claim": "Produce a clean bounded lemma."},
                actor="main",
            )
            planned = lifecycle.create_production_round(
                workers=1,
                mode="prove",
                research_ids=[research["research_id"]],
            )
            assignment = planned["assignments"][0]
            started = start_ledger(
                project_root=store.root,
                task="Exercise silent-zero card-bound CHX behavior.",
                run_id="run-card-bound-silent-zero",
                task_card=assignment["task_card_path"],
            )
            close_ledger(Path(started["ledger_path"]))
            excluded = start_ledger(
                project_root=store.root,
                task="Exercise excluded card-bound CHX finding behavior.",
                run_id="run-card-bound-excluded",
                task_card=assignment["task_card_path"],
            )
            excluded_ledger = Path(excluded["ledger_path"])
            issue = self._architecture_issue()
            finding = {
                key: value for key, value in issue.items() if key != "causation"
            }
            observed = record_finding(excluded_ledger, finding)
            reconcile_finding(
                excluded_ledger,
                finding_id=observed["finding_id"],
                status="excluded_with_reason",
                reason="The frozen causal check ruled out an architecture issue.",
            )
            close_ledger(excluded_ledger)

            receipt = self._ingest_plain_assignment(store, planned, assignment)
            self.assertNotIn("architecture_observation_ids", receipt)
            self.assertFalse((store.root / "chx-observations").exists())

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
            with store.v5_mutation_lock(command="work-unit-abort"):
                store.reasoning_modes().abort_work_unit(
                    round_id=repair["round_id"],
                    actor="main",
                    reason="Exercise mode-preserving repair replan.",
                )
            successor = lifecycle.create_production_round(
                workers=1,
                mode="auto",
                research_ids=[repair["research_id"]],
                host_task_scope_id="mode-preserving-repair-replan",
            )
            successor_card = json.loads(
                Path(
                    str(successor["assignments"][0]["task_card_path"])
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(successor_card["work_mode"], "compute")

    def test_supervision_retry_reuses_pre_round_supervisor_research(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            design, _, _, _ = self._design_round(store)

            with patch.object(
                lifecycle,
                "create_round",
                side_effect=RuntimeError("fixture stop after Research append"),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "fixture stop after Research append",
                ):
                    lifecycle.create_supervision_round(
                        design["round_id"],
                        supervisor_scopes=["program_math"],
                        host_task_scope_id="supervision-recovery-host",
                    )

            orphaned = [
                item
                for item in lifecycle.research_records()
                if item.get("metadata", {})
                .get("research_supervision", {})
                .get("source_round_id")
                == design["round_id"]
            ]
            self.assertEqual(len(orphaned), 1)

            resumed = lifecycle.create_supervision_round(
                design["round_id"],
                supervisor_scopes=["program_math"],
                host_task_scope_id="supervision-recovery-host",
            )
            repeated = lifecycle.create_supervision_round(
                design["round_id"],
                supervisor_scopes=["program_math"],
                host_task_scope_id="supervision-recovery-host",
            )
            self.assertEqual(repeated["round_id"], resumed["round_id"])
            supervisors = [
                item
                for item in lifecycle.research_records()
                if item.get("metadata", {})
                .get("research_supervision", {})
                .get("source_round_id")
                == design["round_id"]
            ]
            self.assertEqual(
                [item["research_id"] for item in supervisors],
                [orphaned[0]["research_id"]],
            )

    def test_supervision_planning_shares_one_read_phase(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            design, _, _, _ = self._design_round(store)
            with patch.object(
                lifecycle,
                "frontier",
                wraps=lifecycle.frontier,
            ) as frontier_spy, patch.object(
                lifecycle,
                "_validate_supervision_round_selection",
                wraps=lifecycle._validate_supervision_round_selection,
            ) as selection_spy:
                lifecycle.create_supervision_round(
                    design["round_id"],
                    supervisor_scopes=["program_math"],
                    host_task_scope_id="shared-supervision-read-phase",
                )
            contexts = [
                call.kwargs.get("_inspection_context")
                for call in [
                    *frontier_spy.call_args_list,
                    *selection_spy.call_args_list,
                ]
            ]
            self.assertTrue(contexts)
            self.assertNotIn(None, contexts)
            self.assertEqual(1, len({id(context) for context in contexts}))

    def test_exact_invalidator_review_lane_does_not_reactivate_stale_routes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            design, assignment, _, _ = self._design_round(
                store,
                invalidate_source=True,
            )
            _, descriptors = lifecycle._source_round_receipt_descriptors(
                design["round_id"]
            )
            invalidated_id = assignment["research_id"]
            invalidator_id = descriptors[0]["result_research_id"]
            ordinary_descendant = lifecycle.add_research(
                {
                    "kind": "direction",
                    "claim": "An ordinary descendant still relies on the invalidated route.",
                    "relation": "supports",
                    "related_research_ids": [invalidated_id],
                },
                actor="main",
            )

            active_ids = {
                item["research_id"]
                for item in lifecycle.frontier(
                    limit=lifecycle._json_count(lifecycle.research_entries_dir)
                )
            }
            self.assertNotIn(invalidated_id, active_ids)
            self.assertNotIn(ordinary_descendant["research_id"], active_ids)
            self.assertIn(invalidator_id, active_ids)

            supervision = lifecycle.create_supervision_round(
                design["round_id"],
                supervisor_scopes=["program_math"],
                host_task_scope_id="invalidator-review-host",
            )
            supervisor_id = supervision["assignments"][0]["research_id"]
            history = {
                item["research_id"]: item
                for item in lifecycle.frontier(
                    limit=lifecycle._json_count(lifecycle.research_entries_dir),
                    include_history=True,
                )
            }
            self.assertEqual(
                history[supervisor_id]["route_status"],
                "current",
            )
            self.assertEqual(
                history[supervisor_id]["route_invalidated_by"],
                [],
            )
            with self.assertRaisesRegex(
                ValueError,
                "reserved for subround-2 supervision",
            ):
                lifecycle.create_production_round(
                    workers=1,
                    mode="auto",
                    research_ids=[supervisor_id],
                )

    def test_invalidator_review_retry_reuses_one_stale_supervisor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            design, _, _, _ = self._design_round(
                store,
                invalidate_source=True,
            )

            with patch.object(
                lifecycle,
                "create_round",
                side_effect=RuntimeError("fixture stop after invalidator review append"),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "fixture stop after invalidator review append",
                ):
                    lifecycle.create_supervision_round(
                        design["round_id"],
                        supervisor_scopes=["program_math"],
                        host_task_scope_id="invalidator-recovery-host",
                    )

            orphaned = [
                item
                for item in lifecycle.research_records()
                if item.get("metadata", {})
                .get("research_supervision", {})
                .get("source_round_id")
                == design["round_id"]
            ]
            self.assertEqual(len(orphaned), 1)
            resumed = lifecycle.create_supervision_round(
                design["round_id"],
                supervisor_scopes=["program_math"],
                host_task_scope_id="invalidator-recovery-host",
            )
            repeated = lifecycle.create_supervision_round(
                design["round_id"],
                supervisor_scopes=["program_math"],
                host_task_scope_id="invalidator-recovery-host",
            )
            self.assertEqual(repeated["round_id"], resumed["round_id"])
            supervisors = [
                item
                for item in lifecycle.research_records()
                if item.get("metadata", {})
                .get("research_supervision", {})
                .get("source_round_id")
                == design["round_id"]
            ]
            self.assertEqual(
                [item["research_id"] for item in supervisors],
                [orphaned[0]["research_id"]],
            )

    def test_supervision_lane_rejects_unreviewed_external_invalidator(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            design, assignment, _, _ = self._design_round(store)
            external_invalidator = lifecycle.add_research(
                {
                    "kind": "challenge",
                    "status": "open",
                    "claim": "A later challenge invalidates the production input route.",
                    "relation": "challenges",
                    "related_research_ids": [assignment["research_id"]],
                    "route_invalidations": [assignment["research_id"]],
                },
                actor="main",
            )

            with self.assertRaisesRegex(ValueError, "not active V5 Research"):
                lifecycle.create_supervision_round(
                    design["round_id"],
                    supervisor_scopes=["program_math"],
                    host_task_scope_id="external-invalidator-host",
                )
            orphaned = [
                item
                for item in lifecycle.research_records()
                if item.get("metadata", {})
                .get("research_supervision", {})
                .get("source_round_id")
                == design["round_id"]
            ]
            self.assertEqual(len(orphaned), 1)
            history = {
                item["research_id"]: item
                for item in lifecycle.frontier(
                    limit=lifecycle._json_count(lifecycle.research_entries_dir),
                    include_history=True,
                )
            }
            self.assertEqual(
                history[orphaned[0]["research_id"]]["route_invalidated_by"],
                [external_invalidator["research_id"]],
            )

    def test_invalidator_and_repair_are_path_barriers_not_route_reactivation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            target = lifecycle.add_research(
                {"kind": "proof_attempt", "claim": "The original route target."},
                actor="main",
            )
            first = lifecycle.add_research(
                {
                    "kind": "challenge",
                    "claim": "First independent invalidator.",
                    "relation": "challenges",
                    "related_research_ids": [target["research_id"]],
                    "route_invalidations": [target["research_id"]],
                },
                actor="first-adverse",
            )
            second = lifecycle.add_research(
                {
                    "kind": "challenge",
                    "claim": "Second independent invalidator.",
                    "relation": "challenges",
                    "related_research_ids": [target["research_id"]],
                    "route_invalidations": [target["research_id"]],
                },
                actor="second-adverse",
            )
            acknowledges_one = lifecycle.add_research(
                {
                    "kind": "insight",
                    "claim": "This branch acknowledges only the first invalidator.",
                    "relation": "responds_to",
                    "related_research_ids": [first["research_id"]],
                },
                actor="main",
            )
            acknowledges_both = lifecycle.add_research(
                {
                    "kind": "insight",
                    "claim": "This branch acknowledges both invalidators.",
                    "relation": "responds_to",
                    "related_research_ids": [
                        first["research_id"],
                        second["research_id"],
                    ],
                },
                actor="main",
            )
            mixed_direct = lifecycle.add_research(
                {
                    "kind": "insight",
                    "claim": "This branch still directly depends on the old target.",
                    "relation": "responds_to",
                    "related_research_ids": [
                        target["research_id"],
                        first["research_id"],
                        second["research_id"],
                    ],
                },
                actor="main",
            )
            repair = lifecycle.add_research(
                {
                    "kind": "repair",
                    "status": "open",
                    "claim": "A later copy-on-write repair of the target.",
                    "relation": "repairs",
                    "related_research_ids": [
                        target["research_id"],
                        first["research_id"],
                        second["research_id"],
                    ],
                    "repair_of_research_id": target["research_id"],
                },
                actor="main",
            )
            history = {
                item["research_id"]: item
                for item in lifecycle.frontier(
                    limit=lifecycle._json_count(lifecycle.research_entries_dir),
                    include_history=True,
                )
            }
            self.assertEqual(
                history[target["research_id"]]["route_invalidated_by"],
                sorted([first["research_id"], second["research_id"]]),
            )
            self.assertEqual(
                history[acknowledges_one["research_id"]]["route_invalidated_by"],
                [],
            )
            self.assertEqual(
                history[acknowledges_both["research_id"]]["route_status"],
                "current",
            )
            self.assertEqual(
                history[mixed_direct["research_id"]]["route_invalidated_by"],
                sorted([first["research_id"], second["research_id"]]),
            )
            self.assertEqual(history[repair["research_id"]]["route_status"], "current")

    def test_invalidator_branch_supports_disposition_execution_and_repair(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            design, assignment, _, _ = self._design_round(
                store,
                invalidate_source=True,
            )
            _, descriptors = lifecycle._source_round_receipt_descriptors(
                design["round_id"]
            )
            invalidated_id = assignment["research_id"]
            invalidator_id = descriptors[0]["result_research_id"]
            _, supervision_receipt = self._ingest_supervision(
                store,
                design["round_id"],
            )
            lifecycle.update_research(
                supervision_receipt["research_id"],
                status="resolved_no_obstruction",
                actor="main",
            )
            execution = lifecycle.create_computation_execution_round(
                design["round_id"],
                assignment["assignment_id"],
                host_task_scope_id="invalidator-execution-host",
            )
            self.assertEqual(execution["research_cycle"]["subround"], "production")
            repair = lifecycle.create_repair_round(
                invalidator_id,
                trigger_research_id=supervision_receipt["research_id"],
                host_task_scope_id="invalidator-repair-host",
            )
            self.assertEqual(repair["repair_of_research_id"], invalidator_id)
            history = {
                item["research_id"]: item
                for item in lifecycle.frontier(
                    limit=lifecycle._json_count(lifecycle.research_entries_dir),
                    include_history=True,
                )
            }
            self.assertEqual(
                history[invalidated_id]["route_status"],
                "stale_pending_copy_on_write_repair",
            )
            self.assertEqual(history[repair["research_id"]]["route_status"], "current")

    def test_candidate_cannot_use_supervisor_task_as_constructive_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            design, _, _, _ = self._design_round(store, invalidate_source=True)
            supervision = lifecycle.create_supervision_round(
                design["round_id"],
                supervisor_scopes=["program_math"],
                host_task_scope_id="candidate-review-only-host",
            )
            supervisor_id = supervision["assignments"][0]["research_id"]
            payload = self._candidate_payload(store, supervisor_id)
            with self.assertRaisesRegex(ValueError, "review-only"):
                lifecycle.candidate_release(
                    payload,
                    producer="candidate-producer",
                )

    def test_candidate_waits_for_completed_ingested_supervision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            design, _, _, _ = self._design_round(store)
            _, descriptors = lifecycle._source_round_receipt_descriptors(
                design["round_id"]
            )
            constructive_result_id = descriptors[0]["result_research_id"]
            payload = self._candidate_payload(store, constructive_result_id)
            with self.assertRaisesRegex(
                ValueError,
                "requires exactly one completed and ingested Research supervision",
            ):
                lifecycle.candidate_release(
                    payload,
                    producer="candidate-producer",
                )

            lifecycle.create_supervision_round(
                design["round_id"],
                supervisor_scopes=["program_math"],
                host_task_scope_id="candidate-pending-supervision-host",
            )
            with self.assertRaisesRegex(
                ValueError,
                "blocked by pending Research supervision",
            ):
                lifecycle.candidate_release(
                    payload,
                    producer="candidate-producer",
                )

    def test_candidate_gate_binds_completed_supervision_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            design, _, _, _ = self._design_round(store)
            _, descriptors = lifecycle._source_round_receipt_descriptors(
                design["round_id"]
            )
            constructive_result = lifecycle._research_record(
                descriptors[0]["result_research_id"]
            )
            _, supervision_receipt = self._ingest_supervision(
                store,
                design["round_id"],
            )
            self.assertEqual(
                lifecycle._required_supervision_results_for_candidate(
                    [constructive_result]
                ),
                {supervision_receipt["research_id"]},
            )

    def test_candidate_seal_rechecks_live_supervision_under_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            design, _, _, _ = self._design_round(store)
            _, descriptors = lifecycle._source_round_receipt_descriptors(
                design["round_id"]
            )
            constructive_result_id = descriptors[0]["result_research_id"]
            supervision, supervision_receipt = self._ingest_supervision(
                store,
                design["round_id"],
            )
            lifecycle.update_research(
                supervision_receipt["research_id"],
                status="resolved_no_obstruction",
                actor="main",
                note="The exact supervision result is nonblocking.",
            )
            payload = self._candidate_payload(store, constructive_result_id)
            bound_records = lifecycle._release_research_records(
                [lifecycle._research_record(constructive_result_id)]
            )
            bound_artifacts = {
                item["sha256"]: item
                for record in bound_records
                for item in record.get("metadata", {}).get("artifacts", [])
            }
            payload["artifacts"] = [
                bound_artifacts[digest] for digest in sorted(bound_artifacts)
            ]
            payload["verification_plan"]["authorized_artifact_roles"] = sorted(
                {item["role"] for item in payload["artifacts"]}
            )
            payload["verification_plan"]["required_checks"].append(
                "research_obligation_evidence"
            )
            supervisor_task_id = supervision["assignments"][0]["research_id"]
            payload["challenge_dispositions"] = [
                {
                    "research_id": supervisor_task_id,
                    "disposition": "nonblocking_with_reason",
                    "rationale": (
                        "The frozen verifier must adjudicate the exact "
                        "supervision task and its result."
                    ),
                },
                {
                    "research_id": supervision_receipt["research_id"],
                    "disposition": "nonblocking_with_reason",
                    "rationale": (
                        "The frozen verifier must adjudicate the exact "
                        "supervision result."
                    ),
                }
            ]
            payload["adverse_actor_ids"] = [
                lifecycle._research_record(supervisor_task_id)["actor"],
                supervision["assignments"][0]["worker_id"],
            ]
            original_required_supervision = (
                lifecycle._required_supervision_results_for_candidate
            )
            required_supervision_calls = 0

            def abort_on_locked_recheck(
                records: list[dict[str, object]],
            ) -> set[str]:
                nonlocal required_supervision_calls
                required_supervision_calls += 1
                if required_supervision_calls == 2:
                    store.reasoning_modes().abort_work_unit(
                        round_id=supervision["round_id"],
                        actor="main",
                        reason="Exercise the seal-time supervision liveness gate.",
                    )
                return original_required_supervision(records)

            with patch.object(
                lifecycle,
                "_required_supervision_results_for_candidate",
                side_effect=abort_on_locked_recheck,
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "supervision liveness changed between preflight and seal",
                ):
                    lifecycle.candidate_release(
                        payload,
                        producer="candidate-producer",
                    )
            self.assertEqual(
                list(lifecycle.candidate_releases_dir.glob("release-*.json")),
                [],
            )

    def test_candidate_cannot_use_supervisor_return_as_constructive_anchor(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            design, _, _, _ = self._design_round(store)
            _, supervision_receipt = self._ingest_supervision(
                store,
                design["round_id"],
            )
            payload = self._candidate_payload(
                store,
                supervision_receipt["research_id"],
            )
            with self.assertRaisesRegex(ValueError, "review-only"):
                lifecycle.candidate_release(
                    payload,
                    producer="candidate-producer",
                )

    def test_aborted_program_math_supervision_cannot_authorize_execution(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            design, assignment, _, _ = self._design_round(store)
            aborted_supervision, aborted_receipt = self._ingest_supervision(
                store,
                design["round_id"],
            )
            lifecycle.update_research(
                aborted_receipt["research_id"],
                status="resolved_no_obstruction",
                actor="main",
                note="This disposition is withdrawn by the round abort.",
            )
            with store.v5_mutation_lock(command="work-unit-abort"):
                store.reasoning_modes().abort_work_unit(
                    round_id=aborted_supervision["round_id"],
                    actor="main",
                    reason="Aborted supervision cannot authorize computation.",
                )
            with self.assertRaisesRegex(
                ValueError,
                "no program-math supervision covers",
            ):
                lifecycle.create_computation_execution_round(
                    design["round_id"],
                    assignment["assignment_id"],
                )

            successor_supervision, successor_receipt = self._ingest_supervision(
                store,
                design["round_id"],
            )
            lifecycle.update_research(
                successor_receipt["research_id"],
                status="resolved_no_obstruction",
                actor="main",
                note="The live successor supervision permits execution.",
            )
            execution = lifecycle.create_computation_execution_round(
                design["round_id"],
                assignment["assignment_id"],
                host_task_scope_id="successor-supervision-execution-host",
            )
            card = json.loads(
                Path(str(execution["assignments"][0]["task_card_path"])).read_text(
                    encoding="utf-8"
                )
            )
            approved = card["mathematical_state"][
                "source_research_dossier"
            ]["metadata"]["approved_computation_execution"]
            self.assertEqual(
                approved["supervision_round_id"],
                successor_supervision["round_id"],
            )

    def test_execution_round_rechecks_supervision_liveness_under_lock(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            design, assignment, _, _ = self._design_round(store)
            supervision, supervision_receipt = self._ingest_supervision(
                store,
                design["round_id"],
            )
            lifecycle.update_research(
                supervision_receipt["research_id"],
                status="resolved_no_obstruction",
                actor="main",
                note="Exercise the lock-held execution authority gate.",
            )
            original_liveness_check = (
                lifecycle._validate_selected_execution_authority_liveness
            )

            def abort_then_check(
                selected: list[dict[str, object]],
            ) -> None:
                store.reasoning_modes().abort_work_unit(
                    round_id=supervision["round_id"],
                    actor="main",
                    reason="Abort after selection but before execution round bytes.",
                )
                original_liveness_check(selected)

            with patch.object(
                lifecycle,
                "_validate_selected_execution_authority_liveness",
                side_effect=abort_then_check,
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "execution authority changed before round creation",
                ):
                    lifecycle.create_computation_execution_round(
                        design["round_id"],
                        assignment["assignment_id"],
                        host_task_scope_id="execution-abort-race-host",
                    )

    def test_execution_round_rechecks_latest_disposition_under_lock(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            design, assignment, _, _ = self._design_round(store)
            supervision, supervision_receipt = self._ingest_supervision(
                store,
                design["round_id"],
            )
            lifecycle.update_research(
                supervision_receipt["research_id"],
                status="resolved_no_obstruction",
                actor="main",
                note="Initial safe disposition for the execution selection.",
            )
            original_liveness_check = (
                lifecycle._validate_selected_execution_authority_liveness
            )
            round_ids_before = {
                path.name for path in store.rounds_dir.glob("round-*")
            }

            def block_then_check(
                selected: list[dict[str, object]],
            ) -> None:
                lifecycle.update_research(
                    supervision_receipt["research_id"],
                    status="blocked",
                    actor="main",
                    note=(
                        "A later blocking disposition supersedes the approval "
                        "before execution-round bytes are written."
                    ),
                )
                original_liveness_check(selected)

            with patch.object(
                lifecycle,
                "_validate_selected_execution_authority_liveness",
                side_effect=block_then_check,
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "execution authority changed before round creation",
                ):
                    lifecycle.create_computation_execution_round(
                        design["round_id"],
                        assignment["assignment_id"],
                        host_task_scope_id="execution-disposition-race-host",
                    )
            self.assertEqual(
                {path.name for path in store.rounds_dir.glob("round-*")},
                round_ids_before,
            )
            dispositions = [
                record
                for record in lifecycle.research_records()
                if record["kind"] == "disposition"
                and record.get("metadata", {}).get("target_research_id")
                == supervision_receipt["research_id"]
            ]
            latest = max(
                dispositions,
                key=lambda item: (item["created_at"], item["research_id"]),
            )
            self.assertEqual(
                latest["metadata"]["disposition_status"],
                "blocked",
            )

    def test_completed_component_can_be_supervised_while_unrelated_worker_runs(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            first = lifecycle.add_research(
                {"kind": "direction", "claim": "Independent constructive branch A."},
                actor="main",
            )
            second = lifecycle.add_research(
                {"kind": "direction", "claim": "Independent constructive branch B."},
                actor="main",
            )
            planned = lifecycle.create_production_round(
                workers=2,
                mode="prove",
                research_ids=[first["research_id"], second["research_id"]],
                host_task_scope_id="logical-component-production-host",
            )
            components = planned["supervision_components"]
            self.assertEqual(len(components), 2)
            assignment_by_research = {
                item["research_id"]: item for item in planned["assignments"]
            }
            first_assignment = assignment_by_research[first["research_id"]]
            second_assignment = assignment_by_research[second["research_id"]]
            first_component = next(
                item
                for item in components
                if first_assignment["assignment_id"] in item["assignment_ids"]
            )
            second_component = next(
                item
                for item in components
                if second_assignment["assignment_id"] in item["assignment_ids"]
            )
            self._ingest_plain_assignment(store, planned, first_assignment)

            status = lifecycle.round_status(planned["round_id"])
            self.assertEqual(status["work_unit_state"], "active")
            self.assertEqual(status["ingested_count"], 1)
            self.assertEqual(status["awaiting_count"], 1)
            supervision = lifecycle.create_supervision_round(
                planned["round_id"],
                source_component_id=first_component["component_id"],
                supervisor_scopes=["proof_logic"],
                host_task_scope_id="logical-component-supervision-host",
            )
            self.assertEqual(
                supervision["research_cycle"]["source_component_id"],
                first_component["component_id"],
            )
            with self.assertRaisesRegex(ValueError, "receipt is missing"):
                lifecycle.create_supervision_round(
                    planned["round_id"],
                    source_component_id=second_component["component_id"],
                    supervisor_scopes=["proof_logic"],
                )
            with self.assertRaisesRegex(ValueError, "component id is required"):
                lifecycle.create_supervision_round(
                    planned["round_id"],
                    supervisor_scopes=["proof_logic"],
                )

    def test_related_component_waits_and_integration_sees_complete_component(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            premise = lifecycle.add_research(
                {"kind": "literature", "claim": "Constructive source component premise."},
                actor="main",
            )
            dependent = lifecycle.add_research(
                {
                    "kind": "direction",
                    "claim": "Constructive output depending on the selected premise.",
                    "relation": "supports",
                    "related_research_ids": [premise["research_id"]],
                },
                actor="main",
            )
            planned = lifecycle.create_production_round(
                workers=2,
                mode="auto",
                research_ids=[premise["research_id"], dependent["research_id"]],
                host_task_scope_id="related-component-production-host",
            )
            self.assertEqual(len(planned["supervision_components"]), 1)
            assignment_by_research = {
                item["research_id"]: item for item in planned["assignments"]
            }
            source_assignment = assignment_by_research[premise["research_id"]]
            proof_assignment = assignment_by_research[dependent["research_id"]]
            self._ingest_plain_assignment(
                store,
                planned,
                source_assignment,
                outcome="evidence",
            )
            with self.assertRaisesRegex(ValueError, "receipt is missing"):
                lifecycle.create_supervision_round(
                    planned["round_id"],
                    supervisor_scopes=["integration"],
                )
            self._ingest_plain_assignment(store, planned, proof_assignment)
            supervision = lifecycle.create_supervision_round(
                planned["round_id"],
                supervisor_scopes=["integration"],
                host_task_scope_id="related-component-integration-host",
            )
            binding = json.loads(
                Path(
                    str(supervision["assignments"][0]["task_card_path"])
                ).read_text(encoding="utf-8")
            )["mathematical_state"]["source_research_dossier"]["metadata"][
                "research_supervision"
            ]
            self.assertEqual(len(binding["source_receipts"]), 2)

    def test_failure_informed_assurance_removes_same_scope_integration_and_defaults_to_minimal_blackboard(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            premise = lifecycle.add_research(
                {"kind": "direction", "claim": "First proof branch."},
                actor="main",
            )
            dependent = lifecycle.add_research(
                {
                    "kind": "direction",
                    "claim": "Second proof branch uses the first.",
                    "relation": "supports",
                    "related_research_ids": [premise["research_id"]],
                },
                actor="main",
            )
            planned = lifecycle.create_production_round(
                workers=2,
                mode="prove",
                research_ids=[premise["research_id"], dependent["research_id"]],
                host_task_scope_id="same-scope-selective-assurance-host",
            )
            first_card = json.loads(
                Path(str(planned["assignments"][0]["task_card_path"])).read_text(
                    encoding="utf-8"
                )
            )
            query = first_card["context_selection"]["blackboard"]["query"]
            self.assertEqual(
                (query["max_hops"], query["node_budget"], query["edge_budget"]),
                (0, 1, 0),
            )
            self.assertEqual(
                first_card["mathematical_state"]["write_space_ids"], []
            )
            self.assertEqual(
                first_card["mathematical_state"]["read_space_ids"],
                query["seed_node_ids"],
            )
            for assignment in planned["assignments"]:
                self._ingest_plain_assignment(store, planned, assignment)
            with self.assertRaisesRegex(ValueError, "do not apply"):
                lifecycle.create_supervision_round(
                    planned["round_id"],
                    supervisor_scopes=["integration"],
                )
            supervision = lifecycle.create_supervision_round(
                planned["round_id"],
                host_task_scope_id="same-scope-selective-supervision-host",
            )
            self.assertEqual(
                supervision["research_cycle"]["supervisor_scopes"],
                ["proof_logic"],
            )
            supervisor_card = json.loads(
                Path(
                    str(supervision["assignments"][0]["task_card_path"])
                ).read_text(encoding="utf-8")
            )
            source = supervisor_card["mathematical_state"][
                "source_research_dossier"
            ]
            assurance = source["metadata"]["failure_informed_assurance"]
            self.assertEqual(assurance["family_ids"], ["proof_boundary_scope"])
            self.assertIn("claim-scope inflation", source["content"])

            production_prompt = Path(
                str(planned["assignments"][0]["prompt_path"])
            ).read_text(encoding="utf-8")
            self.assertIn(
                "references/v5_production_worker_bootstrap.md",
                production_prompt,
            )
            self.assertIn(
                "references/v5_worker_return_contract.md", production_prompt
            )
            production_contract = (
                Path(__file__).resolve().parents[1]
                / "references"
                / "v5_production_worker_bootstrap.md"
            ).read_text(encoding="utf-8")
            for required_boundary in (
                'research_cycle.subround="production"',
                "Do not preload",
                "Role-specific expansion",
                "computational_verification_v4.md",
                "external_theorem_applicability.md",
                "adverse_routing_evolution.md",
                "computation_source",
                "computation_design",
                "computation_dependencies",
                "preflight-return",
                "Candidate Release",
                "First-output checkpoint",
                "consecutive status-only updates",
            ):
                self.assertIn(required_boundary, production_contract)
            supervisor_prompt = Path(
                str(supervision["assignments"][0]["prompt_path"])
            ).read_text(encoding="utf-8")
            self.assertIn(
                "references/v5_supervisor_worker_bootstrap.md",
                supervisor_prompt,
            )
            for broad_startup_reference in (
                "references/agent_protocol_v4.md",
                "references/v5_worker_return_contract.md",
                "references/adverse_routing_evolution.md",
                "references/chx_runtime_ledger.md",
                "references/unified_architecture.md",
            ):
                self.assertNotIn(broad_startup_reference, supervisor_prompt)
            compact_contract = (
                Path(__file__).resolve().parents[1]
                / "references"
                / "v5_supervisor_worker_bootstrap.md"
            ).read_text(encoding="utf-8")
            for required_boundary in (
                'research_cycle.subround="supervision"',
                "Do not preload",
                "Conditional expansion is local",
                "computational_verification_v4.md",
                "external_theorem_applicability.md",
                "adverse_routing_evolution.md",
                "--task-card /absolute/path/to/exact-task-card.json",
                "research_supervision_report",
                "preflight-return",
                "Candidate Release, fresh Candidate adverse review",
                "First-output checkpoint",
                "consecutive",
            ):
                self.assertIn(required_boundary, compact_contract)

            skill_root = Path(__file__).resolve().parents[1]
            skill_router = (skill_root / "SKILL.md").read_text(encoding="utf-8")
            learner_contract = (
                skill_root / "references" / "learner_document_edit_bootstrap.md"
            ).read_text(encoding="utf-8")
            self.assertIn(
                "references/learner_document_edit_bootstrap.md", skill_router
            )
            for required_boundary in (
                "existing academic teaching Markdown file",
                "no new research result",
                "Fact admission",
                "global architecture change",
                "no-chat-context",
                "Stop the compact path",
            ):
                self.assertIn(required_boundary, learner_contract)
            for forbidden_preload in (
                "Read `references/unified_architecture.md` completely",
                "Read `references/admission_contract.md` completely",
                "Read `references/agent_protocol_v4.md` completely",
            ):
                self.assertNotIn(forbidden_preload, learner_contract)

    def test_failure_informed_source_status_and_one_off_compute_budget(self) -> None:
        references = Path(__file__).resolve().parents[1] / "references"
        source_policy = (references / "external_source_reliability.md").read_text(
            encoding="utf-8"
        )
        compute_policy = (
            references / "computational_verification_v4.md"
        ).read_text(encoding="utf-8")
        source_policy = " ".join(source_policy.split())
        compute_policy = " ".join(compute_policy.split())
        for marker in (
            "current-status assessment may be `not_assessed`",
            "`unresolved`. Absence of a frozen response receipt",
            "must not trigger copy-on-write repair or repeat supervision",
            "negative status conclusion requires replayable response receipts",
        ):
            self.assertIn(marker, source_policy)
        for marker in (
            "smallest independent mathematical check",
            "recorded mathematical-correctness or evidential-credibility failure family",
            "optional diagnostic and cannot block execution",
            "eliminate it as redundant at planning",
        ):
            self.assertIn(marker, compute_policy)

    def test_interpretive_insight_does_not_receive_a_blanket_proof_supervisor(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            descriptor = {
                "work_mode": "interpret",
                "outcome": "insight",
                "artifact_bindings": [],
                "has_source_uses": False,
            }
            self.assertEqual(
                lifecycle._default_research_supervisor_scopes([descriptor]),
                [],
            )
            self.assertTrue(
                lifecycle._supervisor_scope_applies("proof_logic", descriptor)
            )
            descriptor["outcome"] = "proof"
            self.assertEqual(
                lifecycle._default_research_supervisor_scopes([descriptor]),
                ["proof_logic"],
            )

    def test_interpretive_proof_boundary_signal_receives_proof_supervisor(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            research = lifecycle.add_research(
                {
                    "kind": "insight",
                    "claim": "Classify every proof module at its authority boundary.",
                    "logic_signals": [
                        "authority_boundary",
                        "proof_architecture",
                    ],
                },
                actor="main",
            )
            planned = lifecycle.create_production_round(
                workers=1,
                mode="interpret",
                research_ids=[research["research_id"]],
                host_task_scope_id="typed-proof-boundary-production-host",
            )
            self._ingest_plain_assignment(
                store,
                planned,
                planned["assignments"][0],
                outcome="insight",
            )
            supervision = lifecycle.create_supervision_round(
                planned["round_id"],
                host_task_scope_id="typed-proof-boundary-supervision-host",
            )
            self.assertEqual(
                supervision["research_cycle"]["supervisor_scopes"],
                ["proof_logic"],
            )
            card = json.loads(
                Path(
                    str(supervision["assignments"][0]["task_card_path"])
                ).read_text(encoding="utf-8")
            )
            assurance = card["mathematical_state"][
                "source_research_dossier"
            ]["metadata"]["failure_informed_assurance"]
            self.assertEqual(
                assurance["selection_policy"],
                "static_role_artifact_outcome_or_frozen_logic_signal_with_"
                "cross_scope_integration",
            )

    def test_failure_informed_assurance_tamper_fails_closed(self) -> None:
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
            assurance = copy.deepcopy(
                card["mathematical_state"]["source_research_dossier"][
                    "metadata"
                ]["failure_informed_assurance"]
            )
            historical = lifecycle._research_record(
                supervision["assignments"][0]["research_id"]
            )
            historical_metadata = copy.deepcopy(historical["metadata"])
            historical_metadata.pop("failure_informed_assurance")
            lifecycle._validate_research_supervision_record_fields(
                kind=historical["kind"],
                status=historical["status"],
                relation=historical["relation"],
                related_research_ids=historical["related_research_ids"],
                metadata=historical_metadata,
            )
            legacy_assurance = copy.deepcopy(assurance)
            legacy_assurance["selection_policy"] = (
                "static_role_artifact_outcome_with_cross_scope_integration"
            )
            lifecycle._validate_failure_informed_assurance(
                legacy_assurance,
                supervisor_scope="program_math",
            )
            assurance["registry_sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "binding drifted"):
                lifecycle._validate_failure_informed_assurance(
                    assurance,
                    supervisor_scope="program_math",
                )

    def test_component_scope_coverage_is_idempotent_and_nonoverlapping(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            first = lifecycle.add_research(
                {"kind": "literature", "claim": "Primary-source branch one."},
                actor="main",
            )
            second = lifecycle.add_research(
                {
                    "kind": "literature",
                    "claim": "Primary-source branch two depends on branch one.",
                    "relation": "supports",
                    "related_research_ids": [first["research_id"]],
                },
                actor="main",
            )
            planned = lifecycle.create_production_round(
                workers=2,
                mode="literature",
                research_ids=[first["research_id"], second["research_id"]],
                host_task_scope_id="coverage-component-production-host",
            )
            for assignment in planned["assignments"]:
                self._ingest_plain_assignment(
                    store,
                    planned,
                    assignment,
                    outcome="evidence",
                )
            first_supervision = lifecycle.create_supervision_round(
                planned["round_id"],
                supervisor_scopes=["source_scope"],
                host_task_scope_id="coverage-component-supervision-host",
            )
            repeated = lifecycle.create_supervision_round(
                planned["round_id"],
                supervisor_scopes=["source_scope"],
                host_task_scope_id="coverage-component-supervision-host",
            )
            self.assertEqual(first_supervision["round_id"], repeated["round_id"])
            with self.assertRaisesRegex(ValueError, "overlapping supervisor"):
                lifecycle.create_supervision_round(
                    planned["round_id"],
                    supervisor_scopes=["source_scope"],
                    host_task_scope_id="different-supervision-host",
                )
            with self.assertRaisesRegex(ValueError, "do not apply"):
                lifecycle.create_supervision_round(
                    planned["round_id"],
                    supervisor_scopes=["source_scope", "integration"],
                )
            with store.v5_mutation_lock(command="work-unit-abort"):
                store.reasoning_modes().abort_work_unit(
                    round_id=first_supervision["round_id"],
                    actor="main",
                    reason="Aborted supervision must not reserve coverage.",
                )
            successor = lifecycle.create_supervision_round(
                planned["round_id"],
                supervisor_scopes=["source_scope"],
                host_task_scope_id="different-supervision-host",
            )
            self.assertNotEqual(
                first_supervision["round_id"], successor["round_id"]
            )

    def test_concurrent_exact_supervision_retry_creates_one_round(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            design, _, _, _ = self._design_round(store)

            def create_from_fresh_store() -> str:
                fresh_store = MathGraphStore(store.root)
                status = fresh_store.v5_lifecycle().create_supervision_round(
                    design["round_id"],
                    supervisor_scopes=["program_math"],
                    host_task_scope_id="concurrent-supervision-host",
                )
                return str(status["round_id"])

            with ThreadPoolExecutor(max_workers=2) as executor:
                round_ids = list(executor.map(lambda _: create_from_fresh_store(), range(2)))
            self.assertEqual(len(set(round_ids)), 1)
            live_supervision_rounds = []
            for round_dir in store.rounds_dir.glob("round-*"):
                manifest = json.loads(
                    (round_dir / "round.json").read_text(encoding="utf-8")
                )
                cycle = manifest.get("research_cycle")
                if (
                    isinstance(cycle, dict)
                    and cycle.get("subround") == "supervision"
                    and store.reasoning_modes().work_unit_abort(
                        manifest["round_id"]
                    )
                    is None
                ):
                    live_supervision_rounds.append(manifest["round_id"])
            self.assertEqual(live_supervision_rounds, round_ids[:1])

    def test_component_partition_tamper_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            first = lifecycle.add_research(
                {"kind": "direction", "claim": "Partition branch A."},
                actor="main",
            )
            second = lifecycle.add_research(
                {"kind": "direction", "claim": "Partition branch B."},
                actor="main",
            )
            planned = lifecycle.create_production_round(
                workers=2,
                mode="prove",
                research_ids=[first["research_id"], second["research_id"]],
            )
            tampered = copy.deepcopy(planned["supervision_components"])
            tampered[0]["assignment_ids"] = tampered[1]["assignment_ids"]
            with self.assertRaisesRegex(ValueError, "Research projection drifted"):
                lifecycle._validate_logical_supervision_components(
                    tampered,
                    assignments=planned["assignments"],
                )

    def test_rehashed_component_partition_is_rederived_from_ancestry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            premise = lifecycle.add_research(
                {"kind": "direction", "claim": "Related partition premise."},
                actor="main",
            )
            dependent = lifecycle.add_research(
                {
                    "kind": "direction",
                    "claim": "Related partition dependent.",
                    "relation": "supports",
                    "related_research_ids": [premise["research_id"]],
                },
                actor="main",
            )
            planned = lifecycle.create_production_round(
                workers=2,
                mode="prove",
                research_ids=[premise["research_id"], dependent["research_id"]],
            )
            self.assertEqual(len(planned["supervision_components"]), 1)
            forged: list[dict[str, object]] = []
            for assignment in planned["assignments"]:
                semantic = {
                    "revision": "chalxius-v5-logical-supervision-component-1",
                    "assignment_ids": [assignment["assignment_id"]],
                    "research_ids": [assignment["research_id"]],
                    "relation_policy": (
                        "selected_research_ancestry_connected_components"
                    ),
                    "truth_effect": "none",
                }
                component_sha = sha256_json(semantic)
                forged.append(
                    {
                        **semantic,
                        "component_id": "component-" + component_sha[:16],
                        "component_sha256": component_sha,
                    }
                )
            forged.sort(key=lambda item: str(item["component_id"]))
            with self.assertRaisesRegex(
                ValueError,
                "partition drifted from Research ancestry",
            ):
                lifecycle._validate_logical_supervision_components(
                    forged,
                    assignments=planned["assignments"],
                )

    def test_supervision_binding_cycle_guard_keeps_outer_hash_check(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            design, _, _, _ = self._design_round(store)
            manifest, descriptors = lifecycle._source_round_receipt_descriptors(
                design["round_id"]
            )
            component = manifest["supervision_components"][0]
            binding = {
                "revision": "chalxius-v5-research-supervision-2",
                "supervisor_scope": "program_math",
                "source_round_id": design["round_id"],
                "source_round_manifest_sha256": manifest["manifest_sha256"],
                "source_receipts": descriptors,
                "source_receipts_sha256": sha256_json(descriptors),
                "source_component_id": component["component_id"],
                "source_component_sha256": component["component_sha256"],
                "review_policy": "attack_exact_production_outputs",
                "repair_policy": "copy_on_write_next_research_cycle",
                "pulse_policy": "not_used",
                "truth_effect": "none",
            }
            original = lifecycle._source_round_receipt_descriptors
            outer_calls = 0

            def recursive_source_check(
                round_id: str,
                *,
                source_component_id: str | None = None,
                _inspection_context: object | None = None,
            ) -> tuple[dict[str, object], list[dict[str, object]]]:
                nonlocal outer_calls
                outer_calls += 1
                lifecycle._validate_research_supervision_binding(
                    copy.deepcopy(binding),
                    _inspection_context=_inspection_context,
                )
                return original(
                    round_id,
                    source_component_id=source_component_id,
                    _inspection_context=_inspection_context,
                )

            with patch.object(
                lifecycle,
                "_source_round_receipt_descriptors",
                side_effect=recursive_source_check,
            ):
                validated = lifecycle._validate_research_supervision_binding(
                    copy.deepcopy(binding)
                )
            self.assertEqual(validated, binding)
            self.assertEqual(outer_calls, 1)

            tampered = copy.deepcopy(binding)
            tampered["source_receipts"][0]["return_sha256"] = "0" * 64
            tampered["source_receipts_sha256"] = sha256_json(
                tampered["source_receipts"]
            )
            with self.assertRaisesRegex(
                ValueError,
                "scope/receipt coverage drifted",
            ):
                lifecycle._validate_research_supervision_binding(tampered)

    def test_supervision_cycle_guard_includes_component_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            design, _, _, _ = self._design_round(store)
            manifest, descriptors = lifecycle._source_round_receipt_descriptors(
                design["round_id"]
            )
            component = manifest["supervision_components"][0]
            binding = {
                "revision": "chalxius-v5-research-supervision-2",
                "supervisor_scope": "program_math",
                "source_round_id": design["round_id"],
                "source_round_manifest_sha256": manifest["manifest_sha256"],
                "source_receipts": descriptors,
                "source_receipts_sha256": sha256_json(descriptors),
                "source_component_id": component["component_id"],
                "source_component_sha256": component["component_sha256"],
                "review_policy": "attack_exact_production_outputs",
                "repair_policy": "copy_on_write_next_research_cycle",
                "pulse_policy": "not_used",
                "truth_effect": "none",
            }
            forged = copy.deepcopy(binding)
            forged_component_sha = sha256_json({"forged": "component"})
            forged["source_component_id"] = (
                "component-" + forged_component_sha[:16]
            )
            forged["source_component_sha256"] = forged_component_sha
            original = lifecycle._source_round_receipt_descriptors
            calls = 0

            def recursive_source_check(
                round_id: str,
                *,
                source_component_id: str | None = None,
                _inspection_context: object | None = None,
            ) -> tuple[dict[str, object], list[dict[str, object]]]:
                nonlocal calls
                calls += 1
                if calls == 1:
                    lifecycle._validate_research_supervision_binding(
                        copy.deepcopy(forged),
                        _inspection_context=_inspection_context,
                    )
                return original(
                    round_id,
                    source_component_id=source_component_id,
                    _inspection_context=_inspection_context,
                )

            with patch.object(
                lifecycle,
                "_source_round_receipt_descriptors",
                side_effect=recursive_source_check,
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "unknown logical supervision component",
                ):
                    lifecycle._validate_research_supervision_binding(
                        copy.deepcopy(binding)
                    )
            self.assertEqual(calls, 2)

    def test_first_wave_refute_is_reserved_for_second_subround(self) -> None:
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
            with self.assertRaisesRegex(
                ValueError,
                "reserved for subround-2 supervision",
            ):
                lifecycle.create_production_round(
                    workers=1,
                    mode="refute",
                    research_ids=[research["research_id"]],
                )
            self.assertEqual(list(store.rounds_dir.glob("round-*")), [])

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

    def test_new_legacy_production_revision_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            research = lifecycle.add_research(
                {"kind": "direction", "claim": "Legacy cycle creation fixture."},
                actor="main",
            )
            legacy_cycle = lifecycle.production_research_cycle_binding()
            legacy_cycle["revision"] = "chalxius-v5-two-subround-research-1"
            legacy_cycle.pop("source_component_id")
            legacy_cycle.pop("source_component_sha256")
            with self.assertRaisesRegex(ValueError, "current logical-component"):
                lifecycle.create_round(
                    workers=1,
                    mode="prove",
                    research_ids=[research["research_id"]],
                    research_cycle=legacy_cycle,
                )

    def test_mixed_legacy_cycle_and_current_allocation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            research = lifecycle.add_research(
                {"kind": "direction", "claim": "Mixed revision fixture."},
                actor="main",
            )
            planned = lifecycle.create_production_round(
                workers=1,
                mode="prove",
                research_ids=[research["research_id"]],
            )
            manifest_path = store.rounds_dir / planned["round_id"] / "round.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            cycle = manifest["research_cycle"]
            cycle["revision"] = "chalxius-v5-two-subround-research-1"
            cycle.pop("source_component_id")
            cycle.pop("source_component_sha256")
            manifest.pop("supervision_components")
            semantic = {
                key: value
                for key, value in manifest.items()
                if key != "manifest_sha256"
            }
            manifest["manifest_sha256"] = sha256_json(semantic)
            manifest_path.write_text(
                json.dumps(manifest, sort_keys=True),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ValueError,
                "legacy production allocation revision drifted",
            ):
                lifecycle._round_manifest(planned["round_id"])

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

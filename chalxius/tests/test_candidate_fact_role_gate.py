from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mathgraph.contracts import sha256_bytes
from mathgraph.markdown import validate_fact_round_trip
from mathgraph.model import Fact
from mathgraph.store import MathGraphStore


class CandidateFactRoleGateTests(unittest.TestCase):
    @staticmethod
    def _store(root: Path) -> MathGraphStore:
        store = MathGraphStore(root)
        store.initialize(
            project_id="candidate-fact-role-gate",
            title="Candidate Fact role gate",
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

    def _planned_assignment(
        self,
        store: MathGraphStore,
    ) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
        lifecycle = store.v5_lifecycle()
        research = lifecycle.add_research(
            {
                "kind": "proof_attempt",
                "claim": "Produce one exact atomic Candidate Fact.",
                "obligations": [
                    {
                        "obligation_id": "obl-candidate-fact",
                        "description": "Return one exact atomic Candidate Fact.",
                        "required_artifact_roles": ["candidate_fact"],
                        "evidence_types": ["bounded_argument"],
                        "not_applicable_allowed": False,
                    }
                ],
                "stop_conditions": [
                    "Stop if the proposed Fact contains separable conclusions."
                ],
            },
            actor="main",
        )
        with patch.object(
            lifecycle,
            "_validate_bound_runtime_binding",
            side_effect=lambda value, **_: value,
        ):
            planned = lifecycle.create_production_round(
                workers=1,
                mode="prove",
                research_ids=[research["research_id"]],
                host_task_scope_id="candidate-fact-role-gate",
            )
        assignment = planned["assignments"][0]
        card = json.loads(
            Path(str(assignment["task_card_path"])).read_text(encoding="utf-8")
        )
        return planned, assignment, card

    def _draft(
        self,
        store: MathGraphStore,
        planned: dict[str, object],
        assignment: dict[str, object],
        card: dict[str, object],
        artifact_bytes: bytes,
    ) -> Path:
        artifact_dir = store.root / str(assignment["artifact_dir_relpath"])
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifact_dir / "candidate-fact.md"
        artifact_path.write_bytes(artifact_bytes)
        artifact_sha256 = sha256_bytes(artifact_bytes)
        payload: dict[str, object] = {
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
            "claim": "The exact atomic Candidate Fact is complete.",
            "content": "The artifact contains the complete bounded proof.",
            "narrative": {
                "rationale": "Bind exact Candidate bytes before supervision.",
                "summary": "One Candidate Fact is returned.",
                "intuition": "Early byte validation avoids late packaging repair.",
                "limitations": "This remains nontruth Research.",
            },
            "artifacts": [
                {
                    "path": artifact_path.relative_to(store.root).as_posix(),
                    "sha256": artifact_sha256,
                    "role": "candidate_fact",
                }
            ],
            "obligation_dispositions": [
                {
                    "obligation_id": item["obligation_id"],
                    "status": "complete",
                    "witness_artifact_sha256s": [artifact_sha256],
                    "rationale": "The exact Candidate Fact artifact is bound.",
                }
                for item in card["assurance_contract"]["obligations"]
            ],
            "computation_manifest": None,
            "research_assurance": self._blank_assurance(),
        }
        if "adverse_routing" in card:
            payload["attack_learning"] = None
        draft_path = store.root / str(assignment["work_dir_relpath"]) / "draft.json"
        draft_path.parent.mkdir(parents=True, exist_ok=True)
        draft_path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        return draft_path

    @staticmethod
    def _preflight(
        store: MathGraphStore,
        *,
        planned: dict[str, object],
        assignment: dict[str, object],
        draft: Path,
    ) -> dict[str, object]:
        lifecycle = store.v5_lifecycle()
        with patch.object(
            lifecycle,
            "_validate_bound_runtime_binding",
            side_effect=lambda value, **_: value,
        ):
            return lifecycle.preflight_return(
                round_id=str(planned["round_id"]),
                assignment_id=str(assignment["assignment_id"]),
                input_path=draft,
            )

    def test_non_fact_candidate_artifact_fails_worker_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            planned, assignment, card = self._planned_assignment(store)
            draft = self._draft(
                store,
                planned,
                assignment,
                card,
                b"research notes, not canonical Fact Markdown\n",
            )
            with self.assertRaisesRegex(
                ValueError,
                "candidate_fact artifact is invalid",
            ):
                self._preflight(
                    store,
                    planned=planned,
                    assignment=assignment,
                    draft=draft,
                )

    def test_multi_claim_candidate_artifact_fails_worker_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            planned, assignment, card = self._planned_assignment(store)
            fact = Fact(
                problem_id=store.project_id(),
                author="proof-worker",
                predecessors=[],
                statement=(
                    "[CLAIM:ROOT] The root theorem holds.\n\n"
                    "[CLAIM:COROLLARY] A separable corollary holds."
                ),
                proof="Prove both assertions independently.",
            )
            draft = self._draft(
                store,
                planned,
                assignment,
                card,
                validate_fact_round_trip(fact).encode("utf-8"),
            )
            with self.assertRaisesRegex(
                ValueError,
                "exactly one semantic conclusion atom",
            ):
                self._preflight(
                    store,
                    planned=planned,
                    assignment=assignment,
                    draft=draft,
                )

    def test_single_claim_canonical_candidate_artifact_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            planned, assignment, card = self._planned_assignment(store)
            fact = Fact(
                problem_id=store.project_id(),
                author="proof-worker",
                predecessors=[],
                statement="[CLAIM:ROOT] The bounded theorem holds.",
                proof="Direct bounded proof.",
            )
            draft = self._draft(
                store,
                planned,
                assignment,
                card,
                validate_fact_round_trip(fact).encode("utf-8"),
            )
            preflight = self._preflight(
                store,
                planned=planned,
                assignment=assignment,
                draft=draft,
            )
            self.assertTrue(preflight["valid"])


if __name__ == "__main__":
    unittest.main()

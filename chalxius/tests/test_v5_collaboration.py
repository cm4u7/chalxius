from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mathgraph.collaboration import FRESH_CONTEXT_CONTRACT_V1
from mathgraph.contracts import POLICY_REVISION_V4, sha256_bytes
from mathgraph.store import MathGraphStore


class V5CollaborationTests(unittest.TestCase):
    def _store(self, root: Path) -> MathGraphStore:
        store = MathGraphStore(root)
        store.initialize(
            project_id="v5-pulse",
            title="V5 constructive pulse",
            workflow_evidence_version=5,
        )
        (root / "host_adapter.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "policy_revision": POLICY_REVISION_V4,
                    "project_id": store.project_id(),
                    "adapter_mode": "cooperative",
                    "trusted_host_issuers": ["test-host"],
                }
            ),
            encoding="utf-8",
        )
        return store

    @staticmethod
    def _return_payload(
        store: MathGraphStore,
        round_id: str,
        assignment: dict[str, object],
        *,
        outcome: str,
        claim: str,
    ) -> dict[str, object]:
        card = json.loads(
            (store.root / str(assignment["task_card_relpath"])).read_text(
                encoding="utf-8"
            )
        )
        payload: dict[str, object] = {
            "schema_version": 5,
            "project_id": store.project_id(),
            "round_id": round_id,
            "assignment_id": assignment["assignment_id"],
            "worker_id": assignment["worker_id"],
            "task_card_sha256": assignment["task_card_sha256"],
            "blackboard_snapshot_sha256": assignment[
                "blackboard_snapshot_sha256"
            ],
            "outcome": outcome,
            "claim": claim,
            "content": "Exact cumulative contribution for the pulse fixture.",
            "narrative": {
                "rationale": "Keep useful work while isolating malformed peers.",
                "summary": "One cumulative contribution.",
                "intuition": "The contribution remains local and reusable.",
                "limitations": "This is nontruth Research.",
            },
            "artifacts": [],
        }
        if "assurance_contract" in card:
            payload.update(
                {
                    "obligation_dispositions": [],
                    "computation_manifest": None,
                    "research_assurance": {
                        "source_uses": [],
                        "route_invalidations": [],
                        "extremal_cases": [],
                        "claim_strength": [],
                        "contour_substitutions": [],
                        "claimed_structures": [],
                        "program_math_alignments": [],
                    },
                }
            )
        if "adverse_routing" in card:
            payload["attack_learning"] = None
        return payload

    def test_two_wave_pulse_keeps_good_work_when_one_peer_is_quarantined(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "v5"
            store = self._store(root)
            lifecycle = store.v5_lifecycle()
            pulse_space_id = next(
                node_id
                for node_id, node in store.blackboard().current_nodes().items()
                if node["node_type"] == "space"
            )
            wave1_sources = [
                lifecycle.add_research(
                    {
                        "kind": "direction",
                        "claim": f"Explore branch {index}.",
                        "blackboard_write_space_ids": [pulse_space_id],
                    },
                    actor="main",
                )
                for index in (1, 2)
            ]
            wave1_round = lifecycle.create_round(
                workers=2,
                research_ids=[item["research_id"] for item in wave1_sources],
            )
            with store.v5_mutation_lock(command="pulse-plan"):
                pulse = store.collaboration()
                wave1_commitments = [
                    pulse.make_wave1_commitment(
                        round_id=wave1_round["round_id"],
                        assignment_id=item["assignment_id"],
                    )
                    for item in wave1_round["assignments"]
                ]
                plan = pulse.create_plan(
                    wave1_commitments=wave1_commitments,
                    minimum_wave1_contributors=1,
                    actor="main",
                )

            good, bad = wave1_round["assignments"]
            good_path = root / good["return_relpath"]
            good_path.write_text(
                json.dumps(
                    self._return_payload(
                        store,
                        wave1_round["round_id"],
                        good,
                        outcome="insight",
                        claim="The first branch yields a stable reduction.",
                    )
                ),
                encoding="utf-8",
            )
            good_receipt = lifecycle.ingest_return(
                round_id=wave1_round["round_id"],
                assignment_id=good["assignment_id"],
                worker_final_sha256=sha256_bytes(good_path.read_bytes()),
            )
            bad_path = root / bad["return_relpath"]
            bad_path.write_text('{"malformed":true}', encoding="utf-8")
            bad_receipt = lifecycle.ingest_return(
                round_id=wave1_round["round_id"],
                assignment_id=bad["assignment_id"],
                worker_final_sha256=sha256_bytes(bad_path.read_bytes()),
            )
            self.assertEqual(good_receipt["status"], "ingested")
            self.assertEqual(bad_receipt["status"], "quarantined")

            review_source = lifecycle.add_research(
                {
                    "kind": "challenge",
                    "claim": "Adversarially test the stable reduction.",
                    "relation": "challenges",
                    "related_research_ids": [good_receipt["research_id"]],
                    "blackboard_write_space_ids": [pulse_space_id],
                },
                actor="main",
            )
            review_round = lifecycle.create_round(
                workers=1,
                research_ids=[review_source["research_id"]],
                mode="refute",
            )
            review_assignment = review_round["assignments"][0]
            with store.v5_mutation_lock(command="pulse-barrier"):
                pulse = store.collaboration()
                review_commitment = pulse.make_review_commitment(
                    pulse_id=plan["pulse_id"],
                    round_id=review_round["round_id"],
                    assignment_id=review_assignment["assignment_id"],
                    peer_node_id=good_receipt["research_id"],
                )
                barrier = pulse.derive_barrier(
                    plan["pulse_id"],
                    after_snapshot_id=review_assignment[
                        "blackboard_snapshot_id"
                    ],
                    review_commitments=[review_commitment],
                    actor="main",
                )
            self.assertEqual(
                barrier["wave1_evidence"][0]["research_id"],
                good_receipt["research_id"],
            )

            review_path = root / review_assignment["return_relpath"]
            review_path.write_text(
                json.dumps(
                    self._return_payload(
                        store,
                        review_round["round_id"],
                        review_assignment,
                        outcome="challenge",
                        claim="The reduction survives the tested boundary.",
                    )
                ),
                encoding="utf-8",
            )
            review_receipt = lifecycle.ingest_return(
                round_id=review_round["round_id"],
                assignment_id=review_assignment["assignment_id"],
                worker_final_sha256=sha256_bytes(review_path.read_bytes()),
            )
            self.assertEqual(review_receipt["status"], "ingested")
            with store.v5_mutation_lock(command="pulse-close"):
                closure = store.collaboration().derive_closure(
                    plan["pulse_id"], actor="main"
                )
            self.assertTrue(closure["coordination_complete"])
            self.assertFalse(closure["admission_authority"])
            status = store.collaboration().status(plan["pulse_id"])
            self.assertEqual(
                {item["state"] for item in status["wave1"]},
                {"ingested", "quarantined"},
            )
            self.assertTrue(
                lifecycle._research_path(good_receipt["research_id"]).is_file()
            )

            with store.v5_mutation_lock(command="work-unit-abort"):
                store.reasoning_modes().abort_work_unit(
                    round_id=review_round["round_id"],
                    actor="main",
                    reason="Cancel future managed activity for this work unit.",
                )
            with store.v5_mutation_lock(command="pulse-barrier"):
                with self.assertRaisesRegex(ValueError, "explicitly aborted"):
                    store.collaboration().make_review_commitment(
                        pulse_id=plan["pulse_id"],
                        round_id=review_round["round_id"],
                        assignment_id=review_assignment["assignment_id"],
                        peer_node_id=good_receipt["research_id"],
                    )
            with store.v5_mutation_lock(command="pulse-dispatch"):
                with self.assertRaisesRegex(ValueError, "explicitly aborted"):
                    store.collaboration().record_host_dispatch(
                        plan["pulse_id"],
                        review_commitment["commitment_id"],
                        issuer="test-host",
                        host_context_id="fresh-test-context",
                        agent_identity="review-worker",
                        fresh_context_contract=FRESH_CONTEXT_CONTRACT_V1,
                    )


if __name__ == "__main__":
    unittest.main()

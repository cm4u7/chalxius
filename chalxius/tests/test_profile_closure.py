from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from mathgraph.blackboard import make_edge, make_node
from mathgraph.collaboration import PulseStore
from mathgraph.contracts import (
    POLICY_REVISION_V4,
    canonical_json_bytes,
    sha256_bytes,
    sha256_json,
)
from mathgraph.fact_bundles import build_claim_card, build_expert_lint_receipt
from mathgraph.model import Fact
from mathgraph.modes import FACT_ADMISSION_CONTRACT_SHA256
from mathgraph.orchestrator import (
    create_round,
    create_verifier_assignment,
    ingest_return,
    validate_return,
)
from mathgraph.store import MathGraphStore
from mathgraph.verification_bundles import VerificationBundleStore


class ProfileClosureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.store = MathGraphStore(self.root)
        self.store.initialize(
            project_id="profile-closure",
            title="Profile closure",
            workflow_evidence_version=4,
            reasoning_mode="deep",
        )
        self._write_json(
            self.root / "host_adapter.json",
            {
                "schema_version": 1,
                "policy_revision": POLICY_REVISION_V4,
                "project_id": self.store.project_id(),
                "adapter_mode": "cooperative",
                "trusted_host_issuers": ["codex-test-host"],
            },
        )
        self.pulses = PulseStore(
            self.root,
            mutation_lock=self.store.mutation_lock,
            trusted_host_issuers={"codex-test-host"},
        )
        self.host_scope = "hosttask-" + "7" * 32
        self.root_space = next(
            node_id
            for node_id, node in self.store.blackboard().nodes().items()
            if node["node_type"] == "space"
        )
        self.memory_counter = 0

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _write_json(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )

    def _planned_round(
        self,
        workers: int,
        *,
        workload_profile: dict | None = None,
    ) -> dict:
        memory_ids: list[str] = []
        for _ in range(workers):
            self.memory_counter += 1
            memory_ids.append(
                self.store.memory_add(
                    {
                        "kind": "direction",
                        "claim": f"Profile closure direction {self.memory_counter}.",
                        "rationale": "Independent profile-closure fixture.",
                        "suggested_actions": ["prove"],
                        **(
                            {"workload_profile": workload_profile}
                            if workload_profile is not None
                            else {}
                        ),
                    },
                    actor="main",
                )
            )
        return create_round(
            self.store,
            workers=workers,
            memory_ids=memory_ids,
            host_task_scope_id=self.host_scope,
        )

    def _ingest(
        self,
        planned: dict,
        index: int,
        *,
        node_key: str,
        outcome: str,
        cross_edge: dict | None = None,
    ) -> tuple[dict, dict]:
        assignment = planned["assignments"][index]
        card_path = Path(assignment["task_card_path"])
        card = json.loads(card_path.read_text(encoding="utf-8"))
        node = make_node(
            node_type="mechanism",
            logical_key=node_key,
            payload={"mechanism": node_key},
            created_by_assignment_id=card["assignment_id"],
        )
        edges = [
            make_edge(
                edge_type="placed_in",
                source_node_id=node["node_id"],
                target_node_id=self.root_space,
                payload={},
                created_by_assignment_id=card["assignment_id"],
            )
        ]
        if cross_edge is not None:
            edges.append(
                make_edge(
                    edge_type=cross_edge["edge_type"],
                    source_node_id=node["node_id"],
                    target_node_id=cross_edge["target_node_id"],
                    payload=cross_edge["payload"],
                    created_by_assignment_id=card["assignment_id"],
                )
            )
        payload = {
            "schema_version": 4,
            "policy_revision": POLICY_REVISION_V4,
            "protocol": "mathgraph-agent-v4",
            "project_id": card["project_id"],
            "round_id": card["round_id"],
            "assignment_id": card["assignment_id"],
            "assignment_sha256": card["assignment_sha256"],
            "task_card_sha256": hashlib.sha256(card_path.read_bytes()).hexdigest(),
            "blackboard_snapshot_sha256": card["blackboard_snapshot_sha256"],
            "worker": card["worker_id"],
            "memory_id": card["memory_id"],
            "mode": card["mode"],
            "outcome": outcome,
            "obligation_ledger": [],
            "blackboard_graph_delta": {
                "base_snapshot_id": card["blackboard_view"]["snapshot_id"],
                "add_nodes": [node],
                "add_edges": edges,
            },
            "narrative_summary": "Profile-closure fixture.",
            "artifacts": [],
        }
        if outcome == "fact_submission":
            payload.update(
                {
                    "claim_relation": "proves",
                    "statement": "[CLAIM:MAIN] The profile fixture identity holds.",
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
                }
            )
        elif outcome == "fact_bundle_submission":
            facts = [
                Fact(
                    problem_id=self.store.project_id(),
                    author=card["worker_id"],
                    predecessors=[],
                    statement=f"[CLAIM:PB{number}] Profile bundle fact {number}.",
                    proof="Direct proof.",
                ).as_submission_dict()
                for number in (1, 2)
            ]
            payload.update(
                {
                    "bundle_claim": "Profile-bound atomic candidates.",
                    "facts": facts,
                }
            )
        else:
            payload.update(
                {
                    "claim": "Profile fixture",
                    "method": "Independent structural inspection",
                    "failure_mode": "No truth claim is made",
                    "what_remains_open": "Mathematical verification",
                }
            )
        return_path = Path(assignment["return_path"])
        self._write_json(return_path, payload)
        validated = validate_return(
            self.store, planned["round_id"], card["assignment_id"]
        )
        receipt = ingest_return(
            self.store,
            planned["round_id"],
            card["assignment_id"],
            worker_final_sha256=validated["return_sha256"],
        )
        return node, receipt

    def _meaningful_payload(self, fixture: dict, source_id: str) -> dict:
        return {
            "exchange_schema_version": 1,
            "pulse_id": fixture["plan"]["pulse_id"],
            "barrier_id": fixture["barrier"]["barrier_id"],
            "commitment_id": fixture["review"]["commitment_id"],
            "peer_node_id": fixture["left"]["node_id"],
            "peer_node_sha256": hashlib.sha256(
                canonical_json_bytes(fixture["left"])
            ).hexdigest(),
            "check": {
                "kind": "scope_audit",
                "method": "Rechecked the peer endpoint in a fresh context.",
                "witness_refs": [source_id],
            },
            "disposition": {
                "kind": "no_correction",
                "boundary": "No correction; truth remains outside this pulse.",
            },
        }

    def _deep_fixture(
        self,
        *,
        omit_second_commitment: bool = False,
        machine_ready: bool = True,
        same_campaign_scope: bool = False,
        first_outcome: str = "fact_submission",
    ) -> dict:
        atomic_profile = None
        if first_outcome == "fact_bundle_submission":
            atomic_profile = {
                "schema_version": 1,
                "policy_revision": POLICY_REVISION_V4,
                "activity": "proof",
                "audience": "internal",
                "computation": {
                    "role": "none",
                    "estimated_wall_seconds": 0,
                    "stage_count": 0,
                    "resume_required": False,
                },
                "fact_output": {
                    "candidate_count": 2,
                    "internal_dependency_count": 0,
                    "atomic_visibility_required": True,
                },
                "semantics": {
                    "source_claim": False,
                    "convention_sensitive": False,
                    "quantifier_sensitive": False,
                    "terminology_sensitive": False,
                },
            }
        wave1 = self._planned_round(2, workload_profile=atomic_profile)
        commitments = [
            self.pulses.make_wave1_commitment(
                round_id=wave1["round_id"],
                assignment_id=item["assignment_id"],
            )
            for item in wave1["assignments"]
        ]
        if omit_second_commitment:
            commitments = commitments[:1]
        plan = self.pulses.create_plan(
            wave1_commitments=commitments,
            minimum_wave1_contributors=len(commitments),
        )
        left, left_receipt = self._ingest(
            wave1,
            0,
            node_key="profile-wave1-left",
            outcome=first_outcome,
        )
        right, right_receipt = self._ingest(
            wave1,
            1,
            node_key="profile-wave1-right",
            outcome="dead_end",
        )
        wave2 = self._planned_round(1)
        review = self.pulses.make_review_commitment(
            pulse_id=plan["pulse_id"],
            round_id=wave2["round_id"],
            assignment_id=wave2["assignments"][0]["assignment_id"],
            peer_node_id=left["node_id"],
            allowed_edge_types=["refines"],
        )
        barrier = self.pulses.derive_barrier(
            plan["pulse_id"],
            after_snapshot_id=wave2["blackboard_snapshot_id"],
            review_commitments=[review],
        )
        if machine_ready:
            self.pulses.record_host_dispatch(
                plan["pulse_id"],
                review["commitment_id"],
                issuer="codex-test-host",
                host_context_id="fresh-profile-review-context",
            )
        source = make_node(
            node_type="mechanism",
            logical_key="profile-review-source",
            payload={"mechanism": "profile-review-source"},
            created_by_assignment_id=wave2["assignments"][0]["assignment_id"],
        )
        fixture = {
            "wave1": wave1,
            "wave2": wave2,
            "left": left,
            "right": right,
            "left_receipt": left_receipt,
            "right_receipt": right_receipt,
            "plan": plan,
            "review": review,
            "barrier": barrier,
        }
        review_node, _ = self._ingest(
            wave2,
            0,
            node_key="profile-review-source",
            outcome="dead_end",
            cross_edge={
                "edge_type": "refines",
                "target_node_id": left["node_id"],
                "payload": self._meaningful_payload(fixture, source["node_id"]),
            },
        )
        self.assertEqual(review_node["node_id"], source["node_id"])
        self.pulses.derive_closure(plan["pulse_id"])

        assignment_ids = sorted(
            item["assignment_id"] for item in wave1["assignments"]
        )
        active_campaign = self.store.campaigns().active()
        assert active_campaign is not None
        campaign_event_id = self.store.campaigns().update(
            active_campaign,
            {
                "type": "constraint_added",
                "payload": {"constraint": "Inspect the orthogonal branch."},
            },
            actor="main",
        )
        evidence_dir = self.root / "reports" / "profile-closure-evidence"
        before_path = evidence_dir / "campaign-before.json"
        after_path = evidence_dir / "campaign-after.json"
        before_scope = {"directions": 1}
        after_scope = before_scope if same_campaign_scope else {"directions": 2}
        common = {
            "schema_version": 1,
            "campaign_id": active_campaign,
            "host_task_scope_id": self.host_scope,
            "covered_assignment_ids": assignment_ids,
        }
        self._write_json(
            before_path,
            {**common, "phase": "before", "scope": before_scope},
        )
        self._write_json(
            after_path,
            {**common, "phase": "after", "scope": after_scope},
        )
        return_specs = []
        for item in wave1["assignments"]:
            path = Path(item["return_path"])
            return_specs.append(
                {
                    "relpath": path.relative_to(self.root).as_posix(),
                    "sha256": sha256_bytes(path.read_bytes()),
                }
            )
        fixture["evidence"] = [
            {
                "feature": "parallel_clean_context_panel",
                "evidence_kind": "native_pulse_with_host_capacity",
                "pulse_id": plan["pulse_id"],
                "host_task_scope_id": self.host_scope,
                "host_callable_slots": 2,
                "eligible_distinct_directions": 2,
                "selected_assignment_ids": assignment_ids,
            },
            {
                "feature": "barriered_blackboard_pulse",
                "evidence_kind": "native_pulse_closure",
                "pulse_id": plan["pulse_id"],
            },
            {
                "feature": "orthogonal_specialist_escalation",
                "evidence_kind": "host_specialist_artifacts",
                "evidence_level": "procedural_host_attestation",
                "host_task_scope_id": self.host_scope,
                "contexts": [
                    {
                        "context_id": "profile-core-context",
                        "assignment_id": assignment_ids[0],
                        "role": "core",
                        "specialty": "direct-proof",
                        "artifact": return_specs[0],
                    },
                    {
                        "context_id": "profile-specialist-context",
                        "assignment_id": assignment_ids[1],
                        "role": "specialist",
                        "specialty": "boundary-analysis",
                        "artifact": return_specs[1],
                    },
                ],
            },
            {
                "feature": "long_horizon_campaign_expansion",
                "evidence_kind": "campaign_expansion_artifacts",
                "evidence_level": "procedural_host_attestation",
                "host_task_scope_id": self.host_scope,
                "campaigns": [
                    {
                        "campaign_id": active_campaign,
                        "covered_assignment_ids": assignment_ids,
                        "campaign_event_ids": [campaign_event_id],
                        "before": {
                            "relpath": before_path.relative_to(self.root).as_posix(),
                            "sha256": sha256_bytes(before_path.read_bytes()),
                        },
                        "after": {
                            "relpath": after_path.relative_to(self.root).as_posix(),
                            "sha256": sha256_bytes(after_path.read_bytes()),
                        },
                    }
                ],
            },
        ]
        return fixture

    @staticmethod
    def _spec(evidence: list[dict], feature: str) -> dict:
        return next(item for item in evidence if item["feature"] == feature)

    def _record(self, fixture: dict, evidence: list[dict] | None = None) -> dict:
        return self.store.profile_closures().record(
            fixture["wave1"]["round_id"],
            {"evidence": evidence if evidence is not None else fixture["evidence"]},
            actor="main",
        )

    def _review_and_admit(self, submission_id: str) -> tuple[dict, str]:
        verifier = create_verifier_assignment(self.store, submission_id)
        review_path = self.store.record_review(
            {
                "schema_version": 4,
                "policy_revision": POLICY_REVISION_V4,
                "fact_id": submission_id,
                "submission_sha256": verifier["submission_sha256"],
                "bundle_sha256": verifier["bundle_sha256"],
                "verdict": "correct",
                "findings": [],
                "prior_review_dispositions": [],
                "reviewer": "fresh-profile-verifier",
                "host_attestation": {
                    "host": "unittest",
                    "agent_id": "fresh-profile-verifier",
                    "isolation": "fresh_context",
                    "fork_turns": "none",
                    "allowed_bundle_sha256": verifier["bundle_sha256"],
                },
            }
        )
        fact_id = self.store.admit(
            submission_id,
            review_id=review_path.stem,
            gateway="profile-gateway",
        )
        return verifier, fact_id

    def test_deep_closure_enables_admission_then_tamper_invalidates_it(self) -> None:
        fixture = self._deep_fixture()
        submission_id = fixture["left_receipt"]["effect"]["submission_id"]
        with self.assertRaisesRegex(ValueError, "profile is not closed"):
            create_verifier_assignment(self.store, submission_id)
        verification_root = self.store.verification_bundles().root
        before_verification = {
            path.relative_to(verification_root).as_posix(): sha256_bytes(
                path.read_bytes()
            )
            for path in verification_root.rglob("*")
            if path.is_file()
        }
        with self.assertRaisesRegex(
            ValueError,
            "requires MathGraphStore authority",
        ):
            self.store.verification_bundles().create(
                submission={},
                predecessor_statements={},
                interfaces={},
                verification_plan={},
            )
        self.assertEqual(
            before_verification,
            {
                path.relative_to(verification_root).as_posix(): sha256_bytes(
                    path.read_bytes()
                )
                for path in verification_root.rglob("*")
                if path.is_file()
            },
        )

        # Even a package planted through the private inherited-fixture seam
        # cannot make the owning store record a review before closure.
        submission = self.store.submission(submission_id)
        planted = VerificationBundleStore._for_inherited_chalk_fixture(
            self.root
        ).create(
            submission=submission,
            predecessor_statements={},
            interfaces={},
            verification_plan=submission["verification_plan"],
        )
        review_payload = {
            "schema_version": 4,
            "policy_revision": POLICY_REVISION_V4,
            "fact_id": submission_id,
            "submission_sha256": submission["submission_sha256"],
            "bundle_sha256": planted["bundle_sha256"],
            "verdict": "correct",
            "findings": [],
            "prior_review_dispositions": [],
            "reviewer": "fresh-preclosure-verifier",
            "host_attestation": {
                "host": "unittest",
                "agent_id": "fresh-preclosure-verifier",
                "isolation": "fresh_context",
                "fork_turns": "none",
                "allowed_bundle_sha256": planted["bundle_sha256"],
            },
        }
        submission_path = self.store.submission_path(submission_id)
        before_review = {
            "submission": submission_path.read_bytes(),
            "reviews": {
                path.relative_to(self.store.reviews_dir).as_posix(): (
                    path.read_bytes()
                )
                for path in self.store.reviews_dir.rglob("*")
                if path.is_file()
            },
        }
        with self.assertRaisesRegex(ValueError, "profile is not closed"):
            self.store.record_review(review_payload)
        self.assertEqual(submission_path.read_bytes(), before_review["submission"])
        self.assertEqual(
            before_review["reviews"],
            {
                path.relative_to(self.store.reviews_dir).as_posix(): (
                    path.read_bytes()
                )
                for path in self.store.reviews_dir.rglob("*")
                if path.is_file()
            },
        )
        closure = self._record(fixture)
        self.assertEqual(
            self.store.profile_closures().status(fixture["wave1"]["round_id"])[
                "state"
            ],
            "closed",
        )
        _, fact_id = self._review_and_admit(submission_id)
        self.assertIn(fact_id, self.store.fact_ids())
        acceptance = next(
            event
            for event in reversed(
                self.store._read_jsonl(self.store.verification_log)
            )
            if event.get("event") == "accepted"
            and event.get("fact_id") == submission_id
        )
        self.assertEqual(acceptance["profile_closure_id"], closure["closure_id"])
        self.assertEqual(
            acceptance["profile_closure_sha256"], closure["receipt_sha256"]
        )

        closure_path = self.root / closure["receipt_relpath"]
        tampered = json.loads(closure_path.read_text(encoding="utf-8"))
        tampered["actor"] = "tampered-actor"
        self._write_json(closure_path, tampered)
        self.assertFalse(self.store.audit().current_ok)
        with self.assertRaisesRegex(ValueError, "receipt header/hash"):
            self.store.admit(
                submission_id,
                review_id=acceptance["review_id"],
                gateway="profile-gateway",
            )

    def test_missing_extra_and_partial_panel_evidence_fail_closed(self) -> None:
        fixture = self._deep_fixture()
        missing = deepcopy(fixture["evidence"][:-1])
        with self.assertRaisesRegex(ValueError, "missing=.*long_horizon"):
            self._record(fixture, missing)
        extra = deepcopy(fixture["evidence"])
        extra.append(
            {
                "feature": "paper_logic_graph",
                "evidence_kind": "reviewed_paper_snapshots",
                "snapshots": [],
            }
        )
        with self.assertRaisesRegex(ValueError, "extra=.*paper_logic"):
            self._record(fixture, extra)
        partial = deepcopy(fixture["evidence"])
        panel = self._spec(partial, "parallel_clean_context_panel")
        panel["selected_assignment_ids"] = panel["selected_assignment_ids"][:1]
        panel["host_callable_slots"] = 1
        with self.assertRaisesRegex(ValueError, "exactly the assignments"):
            self._record(fixture, partial)

    def test_pulse_must_cover_every_required_assignment(self) -> None:
        fixture = self._deep_fixture(omit_second_commitment=True)
        with self.assertRaisesRegex(ValueError, "cover every governed assignment"):
            self._record(fixture)

    def test_unrelated_round_commitment_does_not_substitute_or_false_block(self) -> None:
        fixture = self._deep_fixture()
        feature = "barriered_blackboard_pulse"
        view = self.store.profile_closures().obligation_view(
            fixture["wave1"]["round_id"]
        )
        assignment_ids = sorted(view["assignments"])
        view["assignments"][assignment_ids[1]]["feature_statuses"][feature] = (
            "not_applicable"
        )
        binding = self.store.profile_closures()._pulse_binding(
            {
                "feature": feature,
                "evidence_kind": "native_pulse_closure",
                "pulse_id": fixture["plan"]["pulse_id"],
            },
            feature=feature,
            view=view,
        )
        self.assertEqual(binding["covered_assignment_ids"], assignment_ids[:1])
        self.assertEqual(len(binding["bound_round_commitment_ids"]), 1)

    def test_pulse_must_be_machine_ready(self) -> None:
        fixture = self._deep_fixture(machine_ready=False)
        with self.assertRaisesRegex(ValueError, "machine-verified closed"):
            self._record(fixture)

    def test_specialist_distinct_hash_and_safe_path_are_required(self) -> None:
        fixture = self._deep_fixture()
        evidence_dir = self.root / "rounds" / fixture["wave1"]["round_id"] / "artifacts"
        assignments = sorted(
            item["assignment_id"] for item in fixture["wave1"]["assignments"]
        )
        identical = b"same specialist evidence\n"
        artifacts: list[dict[str, str]] = []
        for assignment_id in assignments:
            path = evidence_dir / assignment_id / "specialist.txt"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(identical)
            artifacts.append(
                {
                    "relpath": path.relative_to(self.root).as_posix(),
                    "sha256": sha256_bytes(path.read_bytes()),
                }
            )
        same_hash = deepcopy(fixture["evidence"])
        contexts = self._spec(
            same_hash, "orthogonal_specialist_escalation"
        )["contexts"]
        contexts[0]["artifact"] = artifacts[0]
        contexts[1]["artifact"] = artifacts[1]
        with self.assertRaisesRegex(ValueError, "distinct hashes"):
            self._record(fixture, same_hash)

        unsafe = deepcopy(fixture["evidence"])
        link = evidence_dir / assignments[0] / "unsafe-link.txt"
        link.symlink_to(Path(fixture["wave1"]["assignments"][0]["return_path"]))
        self._spec(unsafe, "orthogonal_specialist_escalation")["contexts"][0][
            "artifact"
        ] = {
            "relpath": link.relative_to(self.root).as_posix(),
            "sha256": sha256_bytes(link.read_bytes()),
        }
        with self.assertRaisesRegex(ValueError, "missing or unsafe"):
            self._record(fixture, unsafe)

    def test_campaign_expansion_requires_distinct_scope(self) -> None:
        fixture = self._deep_fixture(same_campaign_scope=True)
        with self.assertRaisesRegex(ValueError, "scope must differ"):
            self._record(fixture)

    def test_previous_round_novelty_and_campaign_events_cannot_close_new_work(
        self,
    ) -> None:
        memory_id = self.store.memory_add(
            {"kind": "literature", "claim": "Reuse-sensitive literature query."},
            actor="main",
        )
        old_novelty = self.store.novelty_record(
            {
                "subject_kind": "memory",
                "subject_id": memory_id,
                "corpus": "fixture-corpus",
                "query": "fixture exact query",
                "status": "no_exact_match_found",
                "hits": [],
            },
            actor="main",
        )
        campaign_id = self.store.campaigns().active()
        assert campaign_id is not None
        old_campaign = self.store.campaigns().update(
            campaign_id,
            {
                "type": "constraint_added",
                "payload": {"constraint": "Old expansion event."},
            },
            actor="main",
        )
        planned = create_round(
            self.store,
            workers=1,
            memory_ids=[memory_id],
            host_task_scope_id=self.host_scope,
        )
        assignment_id = planned["assignments"][0]["assignment_id"]
        view = self.store.profile_closures().obligation_view(planned["round_id"])
        view["assignments"][assignment_id]["feature_statuses"][
            "novelty_search_lane"
        ] = "required"
        with self.assertRaisesRegex(ValueError, "novelty event predates"):
            self.store.profile_closures()._novelty_binding(
                {
                    "feature": "novelty_search_lane",
                    "evidence_kind": "native_novelty_records",
                    "event_ids": [old_novelty],
                },
                view=view,
            )

        evidence_dir = self.root / "reports" / "profile-closure-evidence"
        before_path = evidence_dir / "old-campaign-before.json"
        after_path = evidence_dir / "old-campaign-after.json"
        common = {
            "schema_version": 1,
            "campaign_id": campaign_id,
            "host_task_scope_id": self.host_scope,
            "covered_assignment_ids": [assignment_id],
        }
        self._write_json(
            before_path, {**common, "phase": "before", "scope": {"size": 1}}
        )
        self._write_json(
            after_path, {**common, "phase": "after", "scope": {"size": 2}}
        )
        with self.assertRaisesRegex(ValueError, "campaign expansion event predates"):
            self.store.profile_closures()._campaign_binding(
                {
                    "feature": "long_horizon_campaign_expansion",
                    "evidence_kind": "campaign_expansion_artifacts",
                    "evidence_level": "procedural_host_attestation",
                    "host_task_scope_id": self.host_scope,
                    "campaigns": [
                        {
                            "campaign_id": campaign_id,
                            "covered_assignment_ids": [assignment_id],
                            "campaign_event_ids": [old_campaign],
                            "before": {
                                "relpath": before_path.relative_to(self.root).as_posix(),
                                "sha256": sha256_bytes(before_path.read_bytes()),
                            },
                            "after": {
                                "relpath": after_path.relative_to(self.root).as_posix(),
                                "sha256": sha256_bytes(after_path.read_bytes()),
                            },
                        }
                    ],
                },
                view=view,
            )

    def test_expert_synthesis_is_mixed_and_requires_exact_subject_scope(
        self,
    ) -> None:
        planned = self._planned_round(1)
        self._ingest(
            planned,
            0,
            node_key="expert-synthesis-subject",
            outcome="dead_end",
        )
        assignment_id = planned["assignments"][0]["assignment_id"]
        manager = self.store.profile_closures()
        view = manager.obligation_view(planned["round_id"])
        view["assignments"][assignment_id]["feature_statuses"][
            "expert_synthesis_pass"
        ] = "required"
        subject = manager._subject_bindings(view)[assignment_id]

        fact = Fact(
            problem_id=self.store.project_id(),
            author="synthesis-fixture",
            predecessors=[],
            statement="[CLAIM:SYNTHESIS] The communication fixture is bounded.",
            proof="Direct fixture proof.",
        )
        card = build_claim_card(
            fact=fact,
            audience="expert",
            literal_source_claim="Literal synthesis fixture claim.",
            researcher_variant="Bounded synthesis fixture variant.",
            variant_diff=[],
            source_locator="Fixture locator",
            convention_profile="fixture-convention",
            reproduction_bundle=[],
        )
        draft = "\n".join(
            [
                card["literal_source_claim"],
                card["researcher_variant"],
                card["source_locator"],
                card["convention_profile"],
                card["admitted_conclusion"],
                "AI assistance: AI assisted drafting and protocol checks.",
            ]
        ).encode("utf-8")
        card_path = self.root / "reports" / "synthesis-card.json"
        draft_path = self.root / "reports" / "synthesis-draft.md"
        receipt_path = (
            self.root
            / "reports"
            / "expert-lint-receipts"
            / "synthesis.json"
        )
        card_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        card_path.write_text(
            json.dumps(card, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        draft_path.write_bytes(draft)
        receipt_relpath = receipt_path.relative_to(self.root).as_posix()
        receipt = build_expert_lint_receipt(
            project_id=self.store.project_id(),
            receipt_relpath=receipt_relpath,
            draft_bytes=draft_path.read_bytes(),
            claim_card_bytes=card_path.read_bytes(),
        )
        self.assertTrue(receipt["ok"])
        self._write_json(receipt_path, receipt)
        scope_path = (
            self.root
            / "reports"
            / "profile-closure-evidence"
            / "synthesis-scope.json"
        )
        scope = {
            "schema_version": 1,
            "feature": "expert_synthesis_pass",
            "project_id": self.store.project_id(),
            "round_id": planned["round_id"],
            "round_created_at": view["round_created_at"],
            "assignment_id": assignment_id,
            "host_task_scope_id": self.host_scope,
            "task_card_sha256": subject["task_card_sha256"],
            "return_sha256": subject["return_sha256"],
            "ingestion_sha256": subject["ingestion_sha256"],
            "outcome": subject["outcome"],
            "effect": subject["effect"],
            "lint_receipt_file_sha256": sha256_bytes(receipt_path.read_bytes()),
            "lint_receipt_sha256": receipt["lint_receipt_sha256"],
            "draft_sha256": sha256_bytes(draft_path.read_bytes()),
            "card_sha256": sha256_bytes(card_path.read_bytes()),
        }
        self._write_json(scope_path, scope)

        def artifact(path: Path) -> dict[str, str]:
            return {
                "relpath": path.relative_to(self.root).as_posix(),
                "sha256": sha256_bytes(path.read_bytes()),
            }

        spec = {
            "feature": "expert_synthesis_pass",
            "evidence_kind": "native_lint_receipts",
            "receipts": [
                {
                    "assignment_id": assignment_id,
                    "receipt": artifact(receipt_path),
                    "draft": artifact(draft_path),
                    "card": artifact(card_path),
                    "scope": artifact(scope_path),
                }
            ],
        }
        binding = manager._synthesis_binding(spec, view=view)
        self.assertEqual(
            binding["evidence_level"],
            "mixed_procedural_and_machine_verified",
        )
        self.assertEqual(binding["lint_receipt_level"], "machine_verified")
        self.assertEqual(
            binding["assignment_scope_level"],
            "procedural_host_attestation",
        )

        scope["return_sha256"] = "0" * 64
        self._write_json(scope_path, scope)
        stale = deepcopy(spec)
        stale["receipts"][0]["scope"] = artifact(scope_path)
        with self.assertRaisesRegex(ValueError, "current assignment subject"):
            manager._synthesis_binding(stale, view=view)

    def test_deep_atomic_bundle_cannot_bypass_profile_closure(self) -> None:
        profile = {
            "schema_version": 1,
            "policy_revision": POLICY_REVISION_V4,
            "activity": "proof",
            "audience": "internal",
            "computation": {
                "role": "none",
                "estimated_wall_seconds": 0,
                "stage_count": 0,
                "resume_required": False,
            },
            "fact_output": {
                "candidate_count": 2,
                "internal_dependency_count": 0,
                "atomic_visibility_required": True,
            },
            "semantics": {
                "source_claim": False,
                "convention_sensitive": False,
                "quantifier_sensitive": False,
                "terminology_sensitive": False,
            },
        }
        planned = self._planned_round(1, workload_profile=profile)
        assignment = planned["assignments"][0]
        card_path = Path(assignment["task_card_path"])
        card = json.loads(card_path.read_text(encoding="utf-8"))
        facts = [
            Fact(
                problem_id=self.store.project_id(),
                author=card["worker_id"],
                predecessors=[],
                statement=f"[CLAIM:B{index}] Atomic candidate {index}.",
                proof="Direct proof.",
            ).as_submission_dict()
            for index in (1, 2)
        ]
        payload = {
            "schema_version": 4,
            "policy_revision": POLICY_REVISION_V4,
            "protocol": "mathgraph-agent-v4",
            "project_id": card["project_id"],
            "round_id": card["round_id"],
            "assignment_id": card["assignment_id"],
            "assignment_sha256": card["assignment_sha256"],
            "task_card_sha256": sha256_bytes(card_path.read_bytes()),
            "blackboard_snapshot_sha256": card["blackboard_snapshot_sha256"],
            "worker": card["worker_id"],
            "memory_id": card["memory_id"],
            "mode": card["mode"],
            "outcome": "fact_bundle_submission",
            "obligation_ledger": [],
            "blackboard_graph_delta": {
                "base_snapshot_id": card["blackboard_view"]["snapshot_id"],
                "add_nodes": [],
                "add_edges": [],
            },
            "narrative_summary": "Atomic closure bypass fixture.",
            "bundle_claim": "The candidates require atomic review.",
            "facts": facts,
            "artifacts": [],
        }
        return_path = Path(assignment["return_path"])
        self._write_json(return_path, payload)
        validated = validate_return(
            self.store, planned["round_id"], card["assignment_id"]
        )
        receipt = ingest_return(
            self.store,
            planned["round_id"],
            card["assignment_id"],
            worker_final_sha256=validated["return_sha256"],
        )
        with self.assertRaisesRegex(ValueError, "profile is not closed"):
            self.store.fact_bundle_verifier_task(
                receipt["effect"]["fact_bundle_id"]
            )
        bundle_id = receipt["effect"]["fact_bundle_id"]
        bundles = self.store.fact_bundles()
        manifest = bundles.manifest(bundle_id)
        directory = bundles.root / bundle_id
        before = {
            path.relative_to(directory).as_posix(): sha256_bytes(
                path.read_bytes()
            )
            for path in directory.rglob("*")
            if path.is_file()
        }
        low_level_calls = (
            lambda: bundles.verifier_task(bundle_id),
            lambda: bundles.record_review(bundle_id, {}),
            lambda: bundles.admit(bundle_id, review_id="0" * 64),
        )
        for call in low_level_calls:
            with self.assertRaisesRegex(
                ValueError,
                "requires MathGraphStore authority",
            ):
                call()
            self.assertEqual(
                before,
                {
                    path.relative_to(directory).as_posix(): sha256_bytes(
                        path.read_bytes()
                    )
                    for path in directory.rglob("*")
                    if path.is_file()
                },
            )
        self.assertFalse(
            (bundles.root / bundle_id / "ACCEPTED.json").exists()
        )
        self.assertTrue(
            set(manifest["fact_ids"]).isdisjoint(self.store.fact_ids())
        )

    def test_atomic_bundle_acceptance_revalidates_bound_closure(self) -> None:
        fixture = self._deep_fixture(first_outcome="fact_bundle_submission")
        closure = self._record(fixture)
        bundle_id = fixture["left_receipt"]["effect"]["fact_bundle_id"]
        manifest = self.store.fact_bundles().manifest(bundle_id)
        task = self.store.fact_bundle_verifier_task(bundle_id)
        review_id = self.store.record_fact_bundle_review(
            bundle_id,
            {
                "fact_bundle_id": bundle_id,
                "manifest_sha256": manifest["manifest_sha256"],
                "verification_manifest_sha256": task[
                    "verification_manifest_sha256"
                ],
                "packet_sha256": task["packet_sha256"],
                "verdict": "correct",
                "findings": [],
                "reviewer": "fresh-profile-bundle-verifier",
            },
        )
        marker = self.store.admit_fact_bundle(bundle_id, review_id=review_id)
        self.assertEqual(marker["profile_closure_id"], closure["closure_id"])
        self.assertEqual(
            marker["profile_closure_sha256"], closure["receipt_sha256"]
        )
        clean = self.store.audit()
        self.assertTrue(clean.current_ok, clean.errors)
        self.assertEqual(
            set(self.store.fact_ids()),
            set(manifest["fact_ids"]),
        )

        marker_path = self.store.fact_bundles().root / bundle_id / "ACCEPTED.json"
        marker_bytes = marker_path.read_bytes()
        tampered_marker = json.loads(marker_bytes)
        tampered_marker["profile_closure_sha256"] = "0" * 64
        tampered_marker["acceptance_sha256"] = sha256_json(
            {
                key: value
                for key, value in tampered_marker.items()
                if key != "acceptance_sha256"
            }
        )
        self._write_json(marker_path, tampered_marker)
        marker_report = self.store.audit()
        self.assertFalse(marker_report.current_ok)
        self.assertTrue(
            any(
                "fact bundle acceptance profile-closure binding mismatch"
                in error
                for error in marker_report.errors
            ),
            marker_report.errors,
        )
        self.assertTrue(
            any(
                "accepted bundle is not atomically visible" in error
                for error in marker_report.errors
            ),
            marker_report.errors,
        )
        self.assertEqual(self.store.fact_ids(), [])
        marker_path.write_bytes(marker_bytes)
        restored = self.store.audit()
        self.assertTrue(restored.current_ok, restored.errors)

        closure_path = self.root / closure["receipt_relpath"]
        tampered = json.loads(closure_path.read_text(encoding="utf-8"))
        tampered["actor"] = "tampered-bundle-closure"
        self._write_json(closure_path, tampered)
        closure_report = self.store.audit()
        self.assertFalse(closure_report.current_ok)
        self.assertTrue(
            any(
                "profile closure receipt header/hash mismatch" in error
                for error in closure_report.errors
            ),
            closure_report.errors,
        )
        self.assertEqual(self.store.fact_ids(), [])
        with self.assertRaisesRegex(ValueError, "receipt header/hash"):
            self.store.admit_fact_bundle(bundle_id, review_id=review_id)

    def test_fast_round_needs_no_fake_closure_and_keeps_truth_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = MathGraphStore(root)
            store.initialize(
                project_id="profile-fast",
                title="Profile fast",
                workflow_evidence_version=4,
                reasoning_mode="fast",
            )
            memory_id = store.memory_add(
                {"kind": "direction", "claim": "A low-cost direct proof."},
                actor="main",
            )
            planned = create_round(store, workers=1, memory_ids=[memory_id])
            assignment = planned["assignments"][0]
            card_path = Path(assignment["task_card_path"])
            card = json.loads(card_path.read_text(encoding="utf-8"))
            payload = {
                "schema_version": 4,
                "policy_revision": POLICY_REVISION_V4,
                "protocol": "mathgraph-agent-v4",
                "project_id": card["project_id"],
                "round_id": card["round_id"],
                "assignment_id": card["assignment_id"],
                "assignment_sha256": card["assignment_sha256"],
                "task_card_sha256": sha256_bytes(card_path.read_bytes()),
                "blackboard_snapshot_sha256": card["blackboard_snapshot_sha256"],
                "worker": card["worker_id"],
                "memory_id": card["memory_id"],
                "mode": card["mode"],
                "outcome": "fact_submission",
                "obligation_ledger": [],
                "blackboard_graph_delta": {
                    "base_snapshot_id": card["blackboard_view"]["snapshot_id"],
                    "add_nodes": [],
                    "add_edges": [],
                },
                "narrative_summary": "Fast profile fixture.",
                "claim_relation": "proves",
                "statement": "[CLAIM:FAST] The fast identity holds.",
                "proof": "Both sides are identical.",
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
            return_path = Path(assignment["return_path"])
            self._write_json(return_path, payload)
            validated = validate_return(
                store, planned["round_id"], card["assignment_id"]
            )
            receipt = ingest_return(
                store,
                planned["round_id"],
                card["assignment_id"],
                worker_final_sha256=validated["return_sha256"],
            )
            status = store.profile_closures().status(planned["round_id"])
            self.assertEqual(status["state"], "not_required")
            self.assertFalse(
                store.profile_closures()._path(planned["round_id"]).exists()
            )
            with self.assertRaisesRegex(ValueError, "no required exploration"):
                store.profile_closures().record(
                    planned["round_id"], {"evidence": []}, actor="main"
                )
            task = create_verifier_assignment(
                store, receipt["effect"]["submission_id"]
            )
            self.assertEqual(
                store.reasoning_modes().status()[
                    "fact_admission_contract_sha256"
                ],
                FACT_ADMISSION_CONTRACT_SHA256,
            )
            self.assertTrue(task["bundle_sha256"])


if __name__ == "__main__":
    unittest.main()

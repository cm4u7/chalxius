from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from mathgraph.contracts import sha256_bytes, sha256_json
from mathgraph.research_draft import (
    MATHEMATICAL_REFINEMENT_DAG_REVISION,
    MATHEMATICAL_TARGET_POLICY_REVISION,
    PROFILE_OBLIGATIONS,
    RESEARCH_DRAFT_PLAN_REVISION,
    ResearchDraftManager,
    _profile_obligations,
    failure_surface_uid,
    validate_mathematical_target_policy,
    validate_term_registry,
)
from mathgraph.roles import allowed_commands


EXACT_LIMITED_RESTORATIVE_STANCE = (
    "Defend compulsory biomedical moral enhancement only as a conditional, "
    "restorative intervention for persons whose moral-agency or motivational "
    "capacity falls below a justified minimum threshold, aimed at restoring "
    "capacity for later voluntary moral choice; reject universal or "
    "maximization-oriented compulsion."
)


class _Store:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def project_id(self) -> str:
        return "research-draft-fixture"

    @staticmethod
    def _read_json(path: Path):
        return json.loads(path.read_text(encoding="utf-8"))

    @contextmanager
    def v5_mutation_lock(self, *, command: str):
        yield


class _Lifecycle:
    def __init__(self, root: Path) -> None:
        self.root = root / "v5"
        self.store = _Store(root)
        self._records = [
            {
                "research_id": "mem-research-1",
                "record_sha256": "7" * 64,
            }
        ]

    def research_records(self):
        return list(self._records)


class ResearchDraftContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.lifecycle = _Lifecycle(self.root)
        self.manager = ResearchDraftManager(self.lifecycle)
        self.manager.initialize()
        self.declared_stance = EXACT_LIMITED_RESTORATIVE_STANCE
        self.writing = self.root / "revised.md"
        self.writing.write_text(self.declared_stance + "\n", encoding="utf-8")
        self.plan = {
            "contract_revision": RESEARCH_DRAFT_PLAN_REVISION,
            "plan_id": "rdp-" + "1" * 64,
            "record_sha256": "2" * 64,
            "target_node_ids": ["pn-target-headline"],
            "domain_profile": "philosophy",
            "required_profile_obligations": [
                "claim",
                "normative_bridge",
                "objection",
                "defeater",
                "authority_route",
                "scope",
                "failure_surface",
            ],
            "stance_policy": {
                "policy": "steelman_headline",
                "headline_target_ids": ["pn-target-headline"],
                "declared_stance": self.declared_stance,
                "major_revision_requires_operator_authorization": True,
            },
            "term_registry": [
                {
                    "term": "responsibility threshold",
                    "sense_id": "sense-responsibility-threshold",
                    "exact_definition": "The threshold relevant to attributable agency.",
                    "necessity": "It distinguishes capacity from blame.",
                }
            ],
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _surface(self) -> dict[str, object]:
        statement = "The intervention fails the exact authorization threshold."
        surface = {
            "surface_id": "fs-authorization",
            "surface_uid": "",
            "target_node_id": "pn-target-headline",
            "component_id": "component-authorization",
            "statement": statement,
            "statement_sha256": sha256_bytes(statement.encode("utf-8")),
            "trigger": "The authorization condition is absent.",
            "modality": "defeasible",
            "quantifier": "for this intervention class",
            "applicability_scope": "competent adults under the proposed regime",
            "negates_exact_conclusion": True,
            "why_sufficient": "The component asserts authorization only under that condition.",
            "resolution": "Keep the claim conditional and expose the unmet condition.",
        }
        surface["surface_uid"] = failure_surface_uid(surface)
        return surface

    def _entry(self) -> dict[str, object]:
        return {
            "target_node_id": "pn-target-headline",
            "node_disposition": "repaired",
            "disposition_reason": "The support is strengthened without reversing the thesis.",
            "research_record_ids": ["mem-research-1"],
            "stance_impact": "preserves_headline",
            "major_revision_authorization": None,
            "successor_mappings": [
                {
                    "successor_id": "component-authorization",
                    "relation_kind": "splits_into",
                    "reason": "The target is represented by a separately defeasible component.",
                },
                {
                    "successor_id": "component-capacity",
                    "relation_kind": "splits_into",
                    "reason": "A second component preserves the independent capacity condition.",
                },
            ],
            "term_sense_refs": ["sense-responsibility-threshold"],
            "profile_obligations": [
                {
                    "obligation_kind": kind,
                    "status": "satisfied",
                    "evidence_ids": [f"evidence-{kind}"],
                    "reason": f"Exact {kind} evidence is bound.",
                }
                for kind in self.plan["required_profile_obligations"]
            ],
            "failure_surfaces": [self._surface()],
            "writing_coverage": {
                "artifact_relpath": self.writing.relative_to(self.root).as_posix(),
                "artifact_sha256": sha256_bytes(self.writing.read_bytes()),
                "section_ids": ["headline-defense"],
                "reason": "The revised section states the constrained defense explicitly.",
            },
        }

    def _mathematical_plan_and_entry(self) -> tuple[dict, dict]:
        target = "Determine whether C follows from P1 and P2."
        domain = "All objects in the exact declared class."
        policy = validate_mathematical_target_policy(
            {
                "contract_revision": MATHEMATICAL_TARGET_POLICY_REVISION,
                "exact_target_statement": target,
                "exact_target_statement_sha256": sha256_bytes(
                    target.encode("utf-8")
                ),
                "target_claim_ids": ["c1"],
                "hypothesis_claim_ids": ["p1", "p2"],
                "domain_bindings": [
                    {
                        "binding_id": "domain-main",
                        "exact_domain": domain,
                        "exact_domain_sha256": sha256_bytes(
                            domain.encode("utf-8")
                        ),
                        "source_claim_ids": ["p1", "p2"],
                    }
                ],
                "quantifier_bindings": [],
                "permitted_exact_target_outcomes": [
                    "proved",
                    "disproved",
                    "unresolved_with_obstruction",
                ],
                "target_revision_requires_operator_authorization": True,
                "partial_progress_policy": (
                    "typed_refinement_dag_keeps_exact_target_open"
                ),
            },
            available_claim_ids={"p1", "p2", "c1"},
            exact_target_claim_ids={"c1"},
        )
        added_hypothesis = "Additional compactness hypothesis H."
        weak_statement = "Under P1, P2, and H, conclusion C holds."
        progress = {
            "schema_version": 1,
            "contract_revision": MATHEMATICAL_REFINEMENT_DAG_REVISION,
            "root_target": {
                "root_id": "exact-target-root",
                "exact_target_statement_sha256": policy[
                    "exact_target_statement_sha256"
                ],
                "target_claim_ids": ["c1"],
                "hypothesis_claim_ids": ["p1", "p2"],
                "domain_bindings_sha256": sha256_json(policy["domain_bindings"]),
                "quantifier_bindings_sha256": sha256_json([]),
                "resolution_status": "unresolved_with_obstruction",
                "resolution_evidence_ids": [],
                "obstruction": "The proof uses H, absent from the exact target.",
                "original_target_open": True,
            },
            "nodes": [
                {
                    "node_id": "weak-with-H",
                    "node_type": "added_hypothesis_theorem",
                    "statement": weak_statement,
                    "statement_sha256": sha256_bytes(
                        weak_statement.encode("utf-8")
                    ),
                    "resolution_status": "proved",
                    "evidence_ids": ["proof-weak-with-H"],
                    "obstruction": "",
                    "logical_relation_to_original": (
                        "stronger_hypotheses_than_original"
                    ),
                    "refinement_mapping_relation": "weakened_from",
                    "candidate_fact_id_or_null": "a" * 16,
                    "hypothesis_deltas": [
                        {
                            "dimension": "hypothesis",
                            "binding_id": "hypothesis-H",
                            "before": "",
                            "before_sha256": sha256_bytes(b""),
                            "after": added_hypothesis,
                            "after_sha256": sha256_bytes(
                                added_hypothesis.encode("utf-8")
                            ),
                            "change_type": "added",
                            "rationale": (
                                "H is exactly the added sufficient hypothesis."
                            ),
                        }
                    ],
                    "domain_deltas": [],
                    "quantifier_deltas": [],
                    "conclusion_strength_deltas": [],
                    "remaining_gap_to_exact_target": "Remove H without weakening C.",
                    "truth_effect": "none",
                }
            ],
            "edges": [
                {
                    "parent_id": "exact-target-root",
                    "child_id": "weak-with-H",
                    "relation": "refines_toward_exact_target",
                }
            ],
            "topological_order": ["exact-target-root", "weak-with-H"],
            "truth_effect": "none",
        }
        plan = {
            **{
                key: value
                for key, value in self.plan.items()
                if key not in {"stance_policy", "required_profile_obligations"}
            },
            "domain_profile": "mathematics",
            "required_profile_obligations": _profile_obligations("mathematics"),
            "mathematical_target_policy": policy,
            "term_registry": [],
        }
        entry = {
            "target_node_id": "pn-target-headline",
            "node_disposition": "repaired",
            "disposition_reason": (
                "A verified weaker theorem is retained without closing the root."
            ),
            "research_record_ids": ["mem-research-1"],
            "mathematical_progress": progress,
            "successor_mappings": [
                {
                    "successor_id": "a" * 16,
                    "relation_kind": "weakened_from",
                    "reason": "The added-hypothesis theorem is weaker progress only.",
                }
            ],
            "term_sense_refs": [],
            "profile_obligations": [
                {
                    "obligation_kind": kind,
                    "status": "satisfied",
                    "evidence_ids": [f"evidence-{kind}"],
                    "reason": f"Exact {kind} evidence is bound.",
                }
                for kind in plan["required_profile_obligations"]
            ],
            "failure_surfaces": [],
            "writing_coverage": {
                "artifact_relpath": self.writing.relative_to(self.root).as_posix(),
                "artifact_sha256": sha256_bytes(self.writing.read_bytes()),
                "section_ids": ["mathematical-progress"],
                "reason": "The exact target and remaining gap are explicit.",
            },
        }
        return plan, entry

    def test_term_registry_is_sense_aware_and_unicode_normalized(self) -> None:
        registry = validate_term_registry(
            [
                {
                    "term": "Agency",
                    "sense_id": "sense-capacity",
                    "exact_definition": "Capacity for reasons-responsive action.",
                    "necessity": "Names capacity.",
                },
                {
                    "term": "agency",
                    "sense_id": "sense-institution",
                    "exact_definition": "An institution acting through officials.",
                    "necessity": "Names an institutional actor.",
                },
            ]
        )
        self.assertEqual(len(registry), 2)
        conflicting = [dict(item) for item in registry]
        conflicting.append(
            {
                "term": "capacity",
                "sense_id": "sense-capacity",
                "exact_definition": "A conflicting definition.",
                "necessity": "Conflict probe.",
            }
        )
        with self.assertRaisesRegex(ValueError, "conflicting exact definitions"):
            validate_term_registry(conflicting)

    def test_batch_is_one_atomic_visible_head_and_preserves_many_to_many_mapping(self) -> None:
        payload = {"supersedes_batch_id": "", "entries": [self._entry()]}
        with patch.object(self.manager, "plan", return_value=self.plan), patch.object(
            self.manager, "current_batch", return_value=None
        ):
            result = self.manager.record_batch(
                self.plan["plan_id"], payload, actor="main"
            )
        self.assertEqual(result["status"], "committed_all_or_none")
        mappings = result["batch"]["entries"][0]["successor_mappings"]
        self.assertEqual(len(mappings), 2)
        batch_dirs = list(self.manager.batches_dir.glob("rdb-*"))
        self.assertEqual(len(batch_dirs), 1)
        self.assertFalse(list(self.manager.batches_dir.glob(".staging-*")))
        head = json.loads(
            self.manager._head_path(self.plan["plan_id"]).read_text(encoding="utf-8")
        )
        self.assertEqual(head["batch_id"], result["batch"]["batch_id"])
        self.assertEqual(
            result["batch"]["term_registry_sha256"],
            sha256_json(self.plan["term_registry"]),
        )

    def test_batch_rejects_partial_target_set_before_publish(self) -> None:
        two_target_plan = dict(self.plan)
        two_target_plan["target_node_ids"] = [
            "pn-target-headline",
            "pn-target-support",
        ]
        payload = {"supersedes_batch_id": "", "entries": [self._entry()]}
        with patch.object(
            self.manager, "plan", return_value=two_target_plan
        ), patch.object(self.manager, "current_batch", return_value=None):
            with self.assertRaisesRegex(ValueError, "complete Paper target set"):
                self.manager.record_batch(
                    two_target_plan["plan_id"], payload, actor="main"
                )
        self.assertFalse(list(self.manager.batches_dir.glob("rdb-*")))
        self.assertFalse(self.manager._head_path(two_target_plan["plan_id"]).exists())

    def test_exact_limited_restorative_stance_is_frozen_without_clause_loss(self) -> None:
        self.assertEqual(
            self.plan["stance_policy"]["declared_stance"],
            EXACT_LIMITED_RESTORATIVE_STANCE,
        )
        for clause in (
            "only as a conditional, restorative intervention",
            "moral-agency or motivational capacity",
            "below a justified minimum threshold",
            "later voluntary moral choice",
            "reject universal or maximization-oriented compulsion",
        ):
            self.assertIn(clause, self.plan["stance_policy"]["declared_stance"])
        entry = self._entry()
        normalized = self.manager._entry(
            entry,
            plan=self.plan,
            research_index={"mem-research-1": self.lifecycle._records[0]},
        )
        self.assertEqual(normalized["stance_impact"], "preserves_headline")

    def test_two_target_batch_commits_without_topology_compression(self) -> None:
        two_target_plan = dict(self.plan)
        two_target_plan["target_node_ids"] = [
            "pn-target-headline",
            "pn-target-support",
        ]
        supporting = self._entry()
        supporting["target_node_id"] = "pn-target-support"
        supporting["stance_impact"] = "not_headline"
        supporting["successor_mappings"] = [
            {
                "successor_id": "component-support",
                "relation_kind": "directly_reconstructs",
                "reason": "The supporting target remains independently inspectable.",
            }
        ]
        supporting_surface = dict(supporting["failure_surfaces"][0])
        supporting_surface["surface_id"] = "fs-support"
        supporting_surface["target_node_id"] = "pn-target-support"
        supporting_surface["component_id"] = "component-support"
        supporting_surface["surface_uid"] = failure_surface_uid(supporting_surface)
        supporting["failure_surfaces"] = [supporting_surface]
        payload = {
            "supersedes_batch_id": "",
            "entries": [self._entry(), supporting],
        }
        with patch.object(
            self.manager, "plan", return_value=two_target_plan
        ), patch.object(self.manager, "current_batch", return_value=None):
            result = self.manager.record_batch(
                two_target_plan["plan_id"], payload, actor="main"
            )
        self.assertEqual(result["status"], "committed_all_or_none")
        self.assertEqual(
            {entry["target_node_id"] for entry in result["batch"]["entries"]},
            set(two_target_plan["target_node_ids"]),
        )
        self.assertEqual(result["adequacy_receipt"]["target_node_ids"], two_target_plan["target_node_ids"])

    def test_external_finished_publication_is_routed_to_evidence(self) -> None:
        for source_role in ("external_reference", "external_finished_publication"):
            with self.subTest(source_role=source_role), self.assertRaisesRegex(
                ValueError, "belongs to Evidence"
            ):
                self.manager._source_role({"source_role": source_role})
        self.assertEqual(
            self.manager._source_role({"source_role": "research_draft"}),
            "research_draft",
        )

    def test_domain_profiles_specialize_one_lifecycle_without_dropping_obligations(self) -> None:
        for profile in ("philosophy", "mathematics", "empirical"):
            with self.subTest(profile=profile):
                self.assertEqual(
                    _profile_obligations(profile),
                    list(PROFILE_OBLIGATIONS[profile]),
                )
        expected_mixed = sorted(
            {
                obligation
                for obligations in PROFILE_OBLIGATIONS.values()
                for obligation in obligations
            }
        )
        self.assertEqual(_profile_obligations("mixed"), expected_mixed)
        with self.assertRaisesRegex(ValueError, "unsupported"):
            _profile_obligations("generic")

    def test_mathematics_entry_has_no_stance_and_keeps_weaker_result_open(self) -> None:
        plan, entry = self._mathematical_plan_and_entry()
        normalized = self.manager._entry(
            entry,
            plan=plan,
            research_index={"mem-research-1": self.lifecycle._records[0]},
        )
        self.assertNotIn("stance_impact", normalized)
        self.assertNotIn("major_revision_authorization", normalized)
        progress = normalized["mathematical_progress"]
        self.assertTrue(progress["root_target"]["original_target_open"])
        self.assertEqual(progress["progress_class"], "partial_verified_progress")
        self.assertEqual(
            normalized["successor_mappings"][0]["relation_kind"],
            "weakened_from",
        )

    def test_mathematics_batch_publishes_target_progress_without_substitution(self) -> None:
        plan, entry = self._mathematical_plan_and_entry()
        with patch.object(self.manager, "plan", return_value=plan), patch.object(
            self.manager, "current_batch", return_value=None
        ):
            result = self.manager.record_batch(
                plan["plan_id"],
                {"supersedes_batch_id": "", "entries": [entry]},
                actor="main",
            )
        adequacy = result["adequacy_receipt"]["mathematical_target_progress"]
        self.assertFalse(adequacy["weakening_closes_exact_target"])
        self.assertTrue(adequacy["target_progress"][0]["original_target_open"])
        self.assertEqual(
            adequacy["target_progress"][0]["progress_class"],
            "partial_verified_progress",
        )
        stored = self.manager.batch(result["batch"]["batch_id"], deep=False)
        self.assertEqual(stored, result["batch"])

    def test_mathematics_weaker_result_cannot_directly_reconstruct_root(self) -> None:
        plan, entry = self._mathematical_plan_and_entry()
        entry["successor_mappings"].append(
            {
                "successor_id": "b" * 16,
                "relation_kind": "directly_reconstructs",
                "reason": "Forbidden exact-target substitution probe.",
            }
        )
        with self.assertRaisesRegex(ValueError, "cannot masquerade as the exact target"):
            self.manager._entry(
                entry,
                plan=plan,
                research_index={"mem-research-1": self.lifecycle._records[0]},
            )

    def test_headline_reversal_without_authorization_fails_before_publish(self) -> None:
        entry = self._entry()
        entry["stance_impact"] = "reverses_headline"
        payload = {"supersedes_batch_id": "", "entries": [entry]}
        with patch.object(self.manager, "plan", return_value=self.plan), patch.object(
            self.manager, "current_batch", return_value=None
        ):
            with self.assertRaisesRegex(ValueError, "Operator authorization"):
                self.manager.record_batch(
                    self.plan["plan_id"], payload, actor="main"
                )
        self.assertFalse(list(self.manager.batches_dir.glob("rdb-*")))

    def test_major_revision_requires_operator_record_bound_to_exact_plan_target_and_impact(self) -> None:
        authorization_input = {
            "target_node_id": "pn-target-headline",
            "authorized_stance_impact": "reverses_headline",
            "reason": "The Operator explicitly authorizes testing the opposite thesis.",
        }
        with patch.object(self.manager, "plan", return_value=self.plan):
            with self.assertRaisesRegex(PermissionError, "Operator role"):
                self.manager.authorize_major_revision(
                    self.plan["plan_id"],
                    authorization_input,
                    actor="untrusted-main",
                    authority_role="main",
                )
            decision = self.manager.authorize_major_revision(
                self.plan["plan_id"],
                authorization_input,
                actor="operator-one",
                authority_role="operator",
            )
            self.assertEqual(
                decision["declared_stance_sha256"],
                sha256_bytes(self.declared_stance.encode("utf-8")),
            )
            entry = self._entry()
            entry["stance_impact"] = "reverses_headline"
            entry["major_revision_authorization"] = {
                "decision_id": decision["decision_id"],
                "decision_record_sha256": decision["record_sha256"],
            }
            normalized = self.manager._entry(
                entry,
                plan=self.plan,
                research_index={
                    "mem-research-1": self.lifecycle._records[0]
                },
            )
            self.assertEqual(
                normalized["major_revision_authorization"], decision
            )
            wrong_impact = dict(entry)
            wrong_impact["stance_impact"] = "narrows_headline"
            with self.assertRaisesRegex(ValueError, "exact plan, target, and stance impact"):
                self.manager._entry(
                    wrong_impact,
                    plan=self.plan,
                    research_index={
                        "mem-research-1": self.lifecycle._records[0]
                    },
                )

    def test_self_asserted_authorization_payload_is_not_a_valid_reference(self) -> None:
        entry = self._entry()
        entry["stance_impact"] = "reverses_headline"
        entry["major_revision_authorization"] = {
            "actor": "untrusted-main",
            "decision_id": "not-an-operator-ledger-decision",
            "reason": "self asserted",
            "authorized_effect": "reverse_headline",
        }
        with self.assertRaisesRegex(ValueError, "fields are not exact"):
            self.manager._entry(
                entry,
                plan=self.plan,
                research_index={"mem-research-1": self.lifecycle._records[0]},
            )

    def test_failure_surface_is_target_qualified_and_statement_bound(self) -> None:
        surface = self._surface()
        crossed = dict(surface)
        crossed["target_node_id"] = "pn-other-target"
        with self.assertRaisesRegex(ValueError, "crosses Paper targets"):
            self.manager._failure_surface(
                crossed, target_id="pn-target-headline"
            )
        drifted = dict(surface)
        drifted["statement"] = "A different failure statement."
        with self.assertRaisesRegex(ValueError, "statement hash"):
            self.manager._failure_surface(
                drifted, target_id="pn-target-headline"
            )

    def test_role_surface_is_additive_and_not_given_to_workers_or_gateway(self) -> None:
        for command in (
            "research-draft-plan",
            "research-draft-disposition-batch",
            "research-draft-status",
        ):
            self.assertIn(command, allowed_commands("main"))
            self.assertIn(command, allowed_commands("operator"))
            self.assertNotIn(command, allowed_commands("worker"))
            self.assertNotIn(command, allowed_commands("gateway"))
        self.assertIn(
            "research-draft-authorize-major-revision",
            allowed_commands("operator"),
        )
        self.assertNotIn(
            "research-draft-authorize-major-revision", allowed_commands("main")
        )


if __name__ == "__main__":
    unittest.main()

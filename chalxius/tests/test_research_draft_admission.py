from __future__ import annotations

import copy
import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone

from mathgraph import parallel_verification as pv
from mathgraph.contracts import sha256_bytes
from mathgraph.interfaces import SEMANTIC_INTERFACE_REVISION
from mathgraph.model import Fact
from mathgraph.paper_logic import PaperLogicStore
from mathgraph.paper_logic_contracts import (
    PAPER_LOGIC_FEATURE_REVISION,
    REVIEW_GLOBAL_CHECKS,
    scan_high_risk_operators,
)
from mathgraph.research_draft import failure_surface_uid
from mathgraph.research_draft_preflight import (
    ASSURANCE_REVISION,
    derive_paper_transport_closure,
    research_draft_ref,
)
from mathgraph.store import MathGraphStore
from mathgraph.v5_assurance import V5_ASSURANCE_CONTRACT_REVISION


EXACT_LIMITED_RESTORATIVE_STANCE = (
    "Defend compulsory biomedical moral enhancement only as a conditional, "
    "restorative intervention for persons whose moral-agency or motivational "
    "capacity falls below a justified minimum threshold, aimed at restoring "
    "capacity for later voluntary moral choice; reject universal or "
    "maximization-oriented compulsion."
)


def _encodepoint(point: tuple[int, int]) -> bytes:
    x, y = point
    raw = bytearray(y.to_bytes(32, "little"))
    raw[31] |= (x & 1) << 7
    return bytes(raw)


def _key_and_signer(seed: bytes):
    digest = hashlib.sha512(seed).digest()
    scalar = int.from_bytes(
        bytes([digest[0] & 248]) + digest[1:31] + bytes([(digest[31] & 63) | 64]),
        "little",
    )
    public = _encodepoint(pv._scalarmult(pv._B, scalar))
    prefix = digest[32:]

    def sign(message: bytes) -> bytes:
        nonce = int.from_bytes(hashlib.sha512(prefix + message).digest(), "little") % pv._L
        encoded_r = _encodepoint(pv._scalarmult(pv._B, nonce))
        challenge = int.from_bytes(
            hashlib.sha512(encoded_r + public + message).digest(), "little"
        ) % pv._L
        scalar_s = (nonce + challenge * scalar) % pv._L
        return encoded_r + scalar_s.to_bytes(32, "little")

    return public, sign


def _operators(text: str) -> list[dict[str, object]]:
    return [
        {
            "operator_id": f"op-{index}",
            "token": item["token"],
            "occurrence": item["occurrence"],
            "kind": item["kind"],
            "scope": "exact source-local scope",
            "disposition": "logical",
            "depends_on": [],
        }
        for index, item in enumerate(scan_high_risk_operators(text))
    ]


class ResearchDraftAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = MathGraphStore(self.root)
        self.store.initialize(
            project_id="strict-research-draft",
            title="Strict research draft",
            workflow_evidence_version=5,
        )
        self.lifecycle = self.store.v5_lifecycle()
        with self.store.v5_mutation_lock(command="paper-logic-init"):
            self.store.paper_logic().initialize(actor="main")
        self.declared_stance = EXACT_LIMITED_RESTORATIVE_STANCE
        self.source_text = "A constrained intervention may be justified."
        self.source = self.root / "draft.txt"
        self.source.write_text(self.source_text, encoding="utf-8")
        self.source_sha = sha256_bytes(self.source.read_bytes())

    def test_project_registry_rejects_cross_role_public_key_alias_before_plan(self) -> None:
        manager = self.lifecycle.parallel_verification()
        public, _ = _key_and_signer(bytes([79]) * 32)
        planner = manager.register_key(
            {
                "key_role": "planner",
                "public_key_hex": public.hex(),
                "principal_id": "alias-planner",
                "reviewer_role_or_null": None,
                "host_context_id_or_null": None,
                "trust_domain_id": "alias-control",
            },
            actor="operator",
            authority_role="operator",
        )
        self.assertEqual(len(manager.trusted_keys()), 1)
        with self.assertRaisesRegex(ValueError, "aliases one Ed25519 public key"):
            manager.register_key(
                {
                    "key_role": "host",
                    "public_key_hex": public.hex(),
                    "principal_id": "alias-host",
                    "reviewer_role_or_null": None,
                    "host_context_id_or_null": "alias-host-context",
                    "trust_domain_id": "alias-host-domain",
                },
                actor="operator",
                authority_role="operator",
            )
        self.assertEqual(manager.trusted_keys(), {planner["key_id"]: planner})
        self.assertEqual(list(manager.plans_dir.glob("vsp-*.json")), [])
        self.assertEqual(list(manager.plan_heads_dir.glob("*.json")), [])

    def test_disk_registry_alias_fails_status_subsystem_and_top_level_audit(self) -> None:
        manager = self.lifecycle.parallel_verification()
        public, _ = _key_and_signer(bytes([81]) * 32)
        planner = manager.register_key(
            {
                "key_role": "planner",
                "public_key_hex": public.hex(),
                "principal_id": "disk-alias-planner",
                "reviewer_role_or_null": None,
                "host_context_id_or_null": None,
                "trust_domain_id": "disk-alias-control",
            },
            actor="operator",
            authority_role="operator",
        )
        host = pv.build_trusted_key_record(
            project_id=self.store.project_id(),
            key_role="host",
            public_key_hex=public.hex(),
            principal_id="disk-alias-host",
            reviewer_role_or_null=None,
            host_context_id_or_null="disk-alias-host-context",
            trust_domain_id="disk-alias-host-domain",
            registered_by="operator",
        )
        with self.store.v5_mutation_lock(command="verification-key-register"):
            self.store._write_json_once(
                manager.keys_dir / f"{host['key_id']}.json", host
            )
        self.assertNotEqual(planner["key_id"], host["key_id"])
        with self.assertRaisesRegex(ValueError, "aliases one Ed25519 public key"):
            manager.register_key(
                {
                    "key_role": "planner",
                    "public_key_hex": public.hex(),
                    "principal_id": "disk-alias-planner",
                    "reviewer_role_or_null": None,
                    "host_context_id_or_null": None,
                    "trust_domain_id": "disk-alias-control",
                },
                actor="operator",
                authority_role="operator",
            )
        with self.assertRaisesRegex(ValueError, "aliases one Ed25519 public key"):
            manager.trusted_keys()
        with self.assertRaisesRegex(ValueError, "aliases one Ed25519 public key"):
            self.lifecycle.parallel_verification().trusted_keys()
        with self.assertRaisesRegex(ValueError, "aliases one Ed25519 public key"):
            manager.status("release-" + "0" * 64)
        subsystem = manager.audit()
        self.assertFalse(subsystem["current_ok"])
        self.assertEqual(subsystem["counts"]["keys"], 2)
        self.assertTrue(
            any("trusted_key_registry" in error for error in subsystem["errors"])
        )
        top_level = self.lifecycle.audit()
        self.assertFalse(top_level.current_ok)
        self.assertTrue(
            any(
                "parallel_verification: trusted_key_registry" in error
                for error in top_level.workflow_errors
            )
        )

    def test_disk_registry_alias_invalidates_cached_public_record_reads(self) -> None:
        payload, _ = self._build_payload()
        release = self.lifecycle.candidate_release(payload, producer="producer")
        aggregate = self._parallel_aggregate(release)
        manager = self.lifecycle.parallel_verification()
        signed_plan_id = aggregate["signed_plan_id"]
        packet_id = aggregate["aggregate"]["packet_ids"][0]
        receipt_id = aggregate["aggregate"]["receipt_ids"][0]
        aggregate_id = aggregate["aggregate"]["aggregate_id"]
        signed = manager.signed_plan(signed_plan_id)
        planner_key_id = signed["planner_attestation"]["key_id"]
        planner = manager.key(planner_key_id)

        # Warm every public immutable-record cache before introducing a second
        # identity for the planner's exact public key on disk.
        manager.signed_plan(signed_plan_id)
        manager.packet(packet_id)
        manager.receipt(receipt_id)
        alias = pv.build_trusted_key_record(
            project_id=self.store.project_id(),
            key_role="host",
            public_key_hex=planner["public_key_hex"],
            principal_id="cached-alias-host",
            reviewer_role_or_null=None,
            host_context_id_or_null="cached-alias-host-context",
            trust_domain_id="cached-alias-host-domain",
            registered_by="operator",
        )
        with self.store.v5_mutation_lock(command="verification-key-register"):
            self.store._write_json_once(
                manager.keys_dir / f"{alias['key_id']}.json", alias
            )

        calls = (
            lambda: manager.key(planner_key_id),
            lambda: manager.signed_plan(signed_plan_id),
            lambda: manager.packet(packet_id),
            lambda: manager.receipt(receipt_id),
            lambda: manager.aggregate_record(aggregate_id),
            lambda: manager.require_eligible_for_release(
                release["release_id"], aggregate_id
            ),
        )
        for call in calls:
            with self.subTest(call=call):
                with self.assertRaisesRegex(
                    ValueError, "aliases one Ed25519 public key"
                ):
                    call()

    def _source_record(self) -> dict[str, object]:
        return {
            "artifact_sha256": self.source_sha,
            "artifact_locator": str(self.source),
            "title": "Research draft fixture",
            "version": "draft-v1",
            "mime_type": "text/plain",
            "retrieved_at": "2026-08-02T00:00:00Z",
            "inspection_methods": [
                "rendered_primary",
                "text_extraction_secondary",
            ],
        }

    def _logic_bundle(self) -> dict[str, object]:
        span_sha = sha256_bytes(self.source_text.encode("utf-8"))
        source_qualifiers = [
            {
                "qualifier_id": "q-source-modality",
                "kind": "modality",
                "value": "may",
                "scope": "the constrained intervention",
            }
        ]
        component = {
            "component_id": "source-component-1",
            "exact_span": {
                "start": 0,
                "end": len(self.source_text),
                "text": self.source_text,
                "text_sha256": span_sha,
            },
            "proposition_kind": "headline_conclusion",
            "attribution": "author",
            "speaker": "author",
            "quotation_status": "author_text",
            "operator_ledger": _operators(self.source_text),
            "qualifiers": source_qualifiers,
            "challengeability": "independently_challengeable",
            "expected_graph_roles": ["headline_conclusion"],
            "mapped_node_ids": ["c1", "t1"],
            "disposition": "represented",
            "reason": "The exact source proposition remains load-bearing.",
            "composition_witness": "One independently challengeable proposition.",
        }
        source_unit = {
            "local_id": "s1",
            "object_type": "source_unit",
            "payload": {
                "unit_kind": "sentence",
                "order": 1,
                "locator": {
                    "kind": "pdf",
                    "pdf_page_index": 0,
                    "printed_page_label": "1",
                    "region": "sentence-1",
                },
                "text": self.source_text,
                "text_sha256": span_sha,
                "speaker": "author",
                "inspection_methods": [
                    "rendered_primary",
                    "text_extraction_secondary",
                ],
                "render_sha256": span_sha,
                "context_before": "",
                "context_after": "",
                "operator_ledger": _operators(self.source_text),
                "proposition_inventory": [component],
            },
        }
        claim = {
            "local_id": "c1",
            "object_type": "claim",
            "payload": {
                "representation_kind": "source_literal",
                "attribution": "author",
                "discourse_role": "headline_conclusion",
                "content_type": "normative",
                "statement": self.source_text,
                "statement_sha256": span_sha,
                "source_unit_ids": ["s1"],
                "semantic_diff": "",
                "modality": "possible",
                "scope_notes": "The intervention is constrained by the stated defense.",
                "operator_ledger": _operators(self.source_text),
                "definition_ids": [],
                "parent_claim_id": "",
                "semantic_direction": "exact_literal",
                "source_component_ids": ["source-component-1"],
                "residual_component_dispositions": [],
                "qualifier_set": source_qualifiers,
            },
        }
        target = {
            "local_id": "t1",
            "object_type": "paper_target",
            "payload": {
                "target_role": "headline",
                "claim_id": "c1",
                "rationale": "This is the draft's own headline position.",
            },
        }
        nodes = [source_unit, claim, target]
        local_nodes = {item["local_id"]: item for item in nodes}
        return {
            "schema_version": 1,
            "feature_revision": PAPER_LOGIC_FEATURE_REVISION,
            "project_id": self.store.project_id(),
            "paper_id": "draft-paper",
            "graph_kind": "logic",
            "domain_profile": "philosophy",
            "source_role": "research_draft",
            "builder": "paper-builder",
            "builder_context_id": "paper-builder-context",
            "source": self._source_record(),
            "base_snapshot_id": "",
            "supersedes_snapshot_id": "",
            "coverage": {
                "scope_kind": "full_artifact",
                "included_locators": ["text:fixture"],
                "excluded_locators": [],
                "units": [
                    {
                        "unit_id": "s1",
                        "classification": "argumentative",
                        "mapped_node_ids": ["s1", "c1", "t1"],
                        "reason": "",
                        "proposition_component_ids": ["source-component-1"],
                        "component_dispositions": [
                            {
                                "component_id": "source-component-1",
                                "disposition": "represented",
                                "mapped_node_ids": ["c1", "t1"],
                                "reason": (
                                    "The exact source proposition remains load-bearing."
                                ),
                            }
                        ],
                    }
                ],
                "unresolved_load_bearing_units": [],
                "completeness_claim": "Every source proposition is dispositioned.",
            },
            "nodes": nodes,
            "edges": PaperLogicStore._expected_logic_edges(local_nodes),
        }

    def _audit_bundle(
        self,
        *,
        base_snapshot_id: str,
        target_id: str,
        source_id: str,
    ) -> dict[str, object]:
        nodes = [
            {
                "local_id": "finding",
                "object_type": "audit_finding",
                "payload": {
                    "finding_kind": "negation_or_polarity",
                    "severity": "critical",
                    "status": "corroborated",
                    "target_id": target_id,
                    "claim": "The constrained scope must remain explicit.",
                    "rationale": "Removing the constraint changes the draft's position.",
                    "evidence_unit_ids": [source_id],
                    "observed_excerpt": self.source_text,
                    "compared_text": "Any intervention is justified.",
                    "load_bearing_tokens": ["constrained"],
                },
            }
        ]
        local_nodes = {item["local_id"]: item for item in nodes}
        return {
            "schema_version": 1,
            "feature_revision": PAPER_LOGIC_FEATURE_REVISION,
            "project_id": self.store.project_id(),
            "paper_id": "draft-paper",
            "graph_kind": "audit",
            "domain_profile": "philosophy",
            "source_role": "research_draft",
            "builder": "audit-builder",
            "builder_context_id": "audit-builder-context",
            "source": self._source_record(),
            "base_snapshot_id": base_snapshot_id,
            "supersedes_snapshot_id": "",
            "coverage": {
                "scope_kind": "audit_subset",
                "included_locators": ["text:fixture"],
                "excluded_locators": [],
                "units": [
                    {
                        "unit_id": "audit-fixture",
                        "classification": "audit_target",
                        "mapped_node_ids": ["finding"],
                        "reason": "",
                    }
                ],
                "unresolved_load_bearing_units": [],
                "completeness_claim": "The load-bearing qualifier was audited.",
            },
            "nodes": nodes,
            "edges": PaperLogicStore._expected_audit_edges(local_nodes),
        }

    def _freeze(
        self, bundle: dict[str, object]
    ) -> tuple[dict[str, object], dict[str, object]]:
        paper = self.store.paper_logic()
        with self.store.v5_mutation_lock(command="paper-logic-freeze"):
            staged = paper.stage(
                bundle,
                artifact_path=self.source,
                actor=str(bundle["builder"]),
            )
            revision = paper.revision(staged["revision_id"])
            for index, profile in enumerate(revision["required_review_profiles"], 1):
                object_ids = paper._expected_review_object_ids(revision, profile)
                paper.record_review({
                    "schema_version": 1,
                    "feature_revision": PAPER_LOGIC_FEATURE_REVISION,
                    "project_id": self.store.project_id(),
                    "revision_id": revision["revision_id"],
                    "bundle_sha256": revision["bundle_sha256"],
                    "profile": profile,
                    "verdict": "correct",
                    "reviewer": f"reviewer-{index}-{profile}",
                    "reviewer_context_id": f"fresh-{index}-{profile}",
                    "fresh_context_contract": "fresh-context-v1",
                    "object_checks": [
                        {
                            "object_id": object_id,
                            "status": "pass",
                            "finding": "Independently checked.",
                        }
                        for object_id in sorted(object_ids)
                    ],
                    "global_checks": [
                        {
                            "kind": kind,
                            "status": "pass",
                            "finding": "Required global check passed.",
                        }
                        for kind in sorted(REVIEW_GLOBAL_CHECKS[profile])
                    ],
                    "critical_errors": [],
                    "gaps": [],
                    "truth_effect": "none",
                })
            frozen = paper.freeze(revision["revision_id"], actor="main")
        return revision, frozen

    def test_source_unit_cannot_count_as_its_own_proposition_coverage(self) -> None:
        bundle = self._logic_bundle()
        source_payload = bundle["nodes"][0]["payload"]
        source_payload["proposition_inventory"][0]["mapped_node_ids"] = [
            "s1",
            "c1",
            "t1",
        ]
        bundle["coverage"]["units"][0]["component_dispositions"][0][
            "mapped_node_ids"
        ] = ["s1", "c1", "t1"]
        with self.store.v5_mutation_lock(command="paper-logic-stage"):
            with self.assertRaisesRegex(ValueError, "source unit as semantic coverage"):
                self.store.paper_logic().stage(
                    bundle,
                    artifact_path=self.source,
                    actor="paper-builder",
                )

    def test_source_claim_contract_rejects_direction_operator_version_and_locality_drift(self) -> None:
        narrowing = self._logic_bundle()
        narrowing_claim = narrowing["nodes"][1]["payload"]
        narrowing_claim["representation_kind"] = "source_paraphrase"
        narrowing_claim["semantic_diff"] = "The paraphrase narrows the source claim."
        narrowing_claim["semantic_direction"] = "narrowing"
        narrowing_claim["residual_component_dispositions"] = []
        with self.store.v5_mutation_lock(command="paper-logic-stage"):
            with self.assertRaisesRegex(ValueError, "dispose every residual claim"):
                self.store.paper_logic().stage(
                    narrowing, artifact_path=self.source, actor="paper-builder"
                )

        operator_drift = self._logic_bundle()
        operator_drift["nodes"][1]["payload"]["operator_ledger"] = []
        with self.store.v5_mutation_lock(command="paper-logic-stage"):
            with self.assertRaisesRegex(ValueError, "operator ledger misses|changes source operators"):
                self.store.paper_logic().stage(
                    operator_drift, artifact_path=self.source, actor="paper-builder"
                )

        stale_witness = self._logic_bundle()
        stale_witness["nodes"][1]["payload"]["scope_notes"] = (
            "Generated for V8 claim rather than the current revision."
        )
        with self.store.v5_mutation_lock(command="paper-logic-stage"):
            with self.assertRaisesRegex(ValueError, "stale version-specific"):
                self.store.paper_logic().stage(
                    stale_witness, artifact_path=self.source, actor="paper-builder"
                )

        wrong_speaker = self._logic_bundle()
        wrong_speaker["nodes"][0]["payload"]["speaker"] = "objection"
        wrong_speaker["nodes"][0]["payload"]["proposition_inventory"][0][
            "speaker"
        ] = "objection"
        wrong_speaker["nodes"][0]["payload"]["proposition_inventory"][0][
            "attribution"
        ] = "objection"
        with self.store.v5_mutation_lock(command="paper-logic-stage"):
            with self.assertRaisesRegex(ValueError, "attribution/speaker mismatch"):
                self.store.paper_logic().stage(
                    wrong_speaker, artifact_path=self.source, actor="paper-builder"
                )

        nonreciprocal = self._logic_bundle()
        nonreciprocal["nodes"][0]["payload"]["proposition_inventory"][0][
            "mapped_node_ids"
        ] = ["t1"]
        nonreciprocal["coverage"]["units"][0]["component_dispositions"][0][
            "mapped_node_ids"
        ] = ["t1"]
        with self.store.v5_mutation_lock(command="paper-logic-stage"):
            with self.assertRaisesRegex(ValueError, "no reciprocal"):
                self.store.paper_logic().stage(
                    nonreciprocal, artifact_path=self.source, actor="paper-builder"
                )

    def test_independent_source_components_require_an_explicit_mini_dag(self) -> None:
        bundle = self._logic_bundle()
        source = bundle["nodes"][0]["payload"]
        second = copy.deepcopy(source["proposition_inventory"][0])
        second["component_id"] = "source-component-2"
        second["exact_span"] = {
            "start": 2,
            "end": len(self.source_text),
            "text": self.source_text[2:],
            "text_sha256": sha256_bytes(self.source_text[2:].encode("utf-8")),
        }
        second["reason"] = "A separately challengeable proposition cannot be hidden."
        source["proposition_inventory"].append(second)
        claim = bundle["nodes"][1]["payload"]
        claim["source_component_ids"].append("source-component-2")
        coverage = bundle["coverage"]["units"][0]
        coverage["proposition_component_ids"].append("source-component-2")
        coverage["component_dispositions"].append(
            {
                "component_id": "source-component-2",
                "disposition": "represented",
                "mapped_node_ids": ["c1", "t1"],
                "reason": second["reason"],
            }
        )
        with self.store.v5_mutation_lock(command="paper-logic-stage"):
            with self.assertRaisesRegex(ValueError, "explicit mini-DAG"):
                self.store.paper_logic().stage(
                    bundle, artifact_path=self.source, actor="paper-builder"
                )

    def _current_research(self) -> dict[str, object]:
        return self.lifecycle.add_research(
            {
                "kind": "direction",
                "status": "open",
                "claim": "The constrained defense survives the strongest scoped objection.",
                "content": "Research reconstructs the exact source proposition.",
                "rationale": "This record is bound to the full Paper target.",
                "source": "sealed Paper Graph",
                "artifacts": [],
                "source_dependent": False,
                "route_invalidations": [],
                "logic_signals": [],
                "obligation_dispositions": [],
                "computation_manifest": [],
                "research_assurance": {"scope": "full Paper target closure"},
            },
            actor="researcher",
            task_binding={"assignment_id": "strict-fixture-assignment"},
            assurance_contract_revision=V5_ASSURANCE_CONTRACT_REVISION,
        )

    @staticmethod
    def _semantic_interface(statement: str) -> list[dict[str, object]]:
        clause = statement.removeprefix("[CLAIM:C1] ")
        return [
            {
                "interface_revision": SEMANTIC_INTERFACE_REVISION,
                "domain_profile": "philosophy",
                "clause_id": "C1",
                "component_id": "component-defense",
                "component_kind": "conclusion",
                "statement": clause,
                "statement_sha256": sha256_bytes(clause.encode("utf-8")),
                "operators": [
                    {
                        "operator_id": "semantic-op-modal",
                        "kind": "modality",
                        "value": "may",
                        "scope": "exact source-local scope",
                        "depends_on": [],
                    }
                ],
                "hypotheses": [],
                "typed_objects": [
                    {
                        "object_id": "intervention-object",
                        "kind": "intervention",
                        "role": "object of the defended policy",
                        "scope": "the constrained intervention",
                    }
                ],
                "qualifiers": [
                    {
                        "qualifier_id": "q-source-modality",
                        "kind": "modality",
                        "value": "may",
                        "scope": "the constrained intervention",
                    }
                ],
                "comparison": None,
                "source_component_ids": ["source-component-1"],
                "failure_mode_ids": ["failure-defense"],
            }
        ]

    def _build_payload(self) -> tuple[dict[str, object], Path]:
        logic_revision, logic_frozen = self._freeze(self._logic_bundle())
        logic_ids = logic_revision["local_id_map"]
        audit_revision, audit_frozen = self._freeze(
            self._audit_bundle(
                base_snapshot_id=logic_frozen["snapshot_id"],
                target_id=logic_ids["c1"],
                source_id=logic_ids["s1"],
            )
        )
        audit_ids = audit_revision["local_id_map"]
        research = self._current_research()
        manager = self.lifecycle.research_draft()
        plan = manager.create_plan(
            logic_frozen["snapshot_id"],
            {
                "objective": "Strengthen the draft while preserving its constrained defense.",
                "source_artifact_sha256": self.source_sha,
                "stance_policy": {
                    "policy": "steelman_headline",
                    "headline_target_ids": [logic_ids["t1"]],
                    "declared_stance": self.declared_stance,
                    "major_revision_requires_operator_authorization": True,
                },
                "term_registry": [],
            },
            actor="main",
        )
        self.assertEqual(
            plan["stance_policy"]["declared_stance"],
            self.declared_stance,
        )
        statement = f"[CLAIM:C1] {self.source_text}"
        fact = Fact(
            problem_id=self.store.project_id(),
            author="candidate-author",
            predecessors=[],
            statement=statement,
            proof="The exact scoped source component supports this bounded conclusion.",
            semantic_interface=self._semantic_interface(statement),
        )
        surface_statement = "The intervention is not justified outside the constrained scope."
        surface = {
            "surface_id": "failure-defense",
            "surface_uid": "",
            "target_node_id": logic_ids["t1"],
            "component_id": "component-defense",
            "statement": surface_statement,
            "statement_sha256": sha256_bytes(surface_statement.encode("utf-8")),
            "trigger": "The stated constraint is absent.",
            "modality": "defeasible",
            "quantifier": "for interventions outside the constrained class",
            "applicability_scope": "the draft's proposed institutional regime",
            "negates_exact_conclusion": True,
            "why_sufficient": "The Candidate conclusion is explicitly scope-bound.",
            "resolution": "Retain the scope qualifier and reject generalization.",
        }
        surface["surface_uid"] = failure_surface_uid(surface)
        writing = self.root / "revised.md"
        writing.write_text(
            "# Revised defense\n\n" + self.declared_stance + "\n",
            encoding="utf-8",
        )
        obligations = [
            {
                "obligation_kind": kind,
                "status": "satisfied",
                "evidence_ids": [f"evidence-{kind}"],
                "reason": f"The {kind} obligation is explicit.",
            }
            for kind in plan["required_profile_obligations"]
        ]
        batch_result = manager.record_batch(
            plan["plan_id"],
            {
                "supersedes_batch_id": "",
                "entries": [
                    {
                        "target_node_id": logic_ids["t1"],
                        "node_disposition": "repaired",
                        "disposition_reason": "The exact qualifier is made explicit.",
                        "research_record_ids": [research["research_id"]],
                        "stance_impact": "preserves_headline",
                        "major_revision_authorization": None,
                        "successor_mappings": [
                            {
                                "successor_id": fact.fact_id,
                                "relation_kind": "directly_reconstructs",
                                "reason": "The atomic Fact reconstructs the headline target.",
                            }
                        ],
                        "term_sense_refs": [],
                        "profile_obligations": obligations,
                        "failure_surfaces": [surface],
                        "writing_coverage": {
                            "artifact_relpath": writing.relative_to(self.root).as_posix(),
                            "artifact_sha256": sha256_bytes(writing.read_bytes()),
                            "section_ids": ["revised-defense"],
                            "reason": "The revised writing states the preserved headline.",
                        },
                    }
                ],
            },
            actor="main",
        )
        batch = batch_result["batch"]
        adequacy = batch_result["adequacy_receipt"]
        ref = research_draft_ref(plan=plan, batch=batch, adequacy_receipt=adequacy)
        load_bearing = sorted(
            {
                *plan["selected_reconstruction_node_ids"],
                *plan["selected_source_node_ids"],
            }
        )
        paper = self.store.paper_logic()
        logic_manifest = paper.snapshots_dir / logic_frozen["snapshot_id"] / "manifest.json"
        audit_manifest = paper.snapshots_dir / audit_frozen["snapshot_id"] / "manifest.json"
        paper_refs = [
            {
                "paper_id": "draft-paper",
                "snapshot_id": logic_frozen["snapshot_id"],
                "snapshot_sha256": sha256_bytes(logic_manifest.read_bytes()),
                "graph_kind": "logic",
                "target_artifact_sha256": self.source_sha,
                "target_node_ids": load_bearing,
            },
            {
                "paper_id": "draft-paper",
                "snapshot_id": audit_frozen["snapshot_id"],
                "snapshot_sha256": sha256_bytes(audit_manifest.read_bytes()),
                "graph_kind": "audit",
                "target_artifact_sha256": self.source_sha,
                "target_node_ids": [audit_ids["finding"]],
            },
        ]
        logic_nodes, logic_edges = paper.snapshot_objects(logic_frozen["snapshot_id"])
        incident = {
            node_id: sorted(
                edge_id
                for edge_id, edge in logic_edges.items()
                if node_id in {edge["source_id"], edge["target_id"]}
            )[0]
            for node_id in load_bearing
        }
        disposition = {
            node_id: (
                "repaired"
                if node_id == logic_ids["t1"]
                else "retained_as_source"
                if logic_nodes[node_id]["object_type"]
                in {"source_artifact", "source_unit"}
                else "represented"
            )
            for node_id in load_bearing
        }
        relation = {
            node_id: (
                "source_grounded"
                if logic_nodes[node_id]["object_type"]
                in {"source_artifact", "source_unit"}
                else "directly_reconstructs"
            )
            for node_id in load_bearing
        }
        assurance = {
            "contract_revision": ASSURANCE_REVISION,
            "validation_subject": {
                "kind": "paper",
                "subject_id": "draft-paper",
                "artifact_sha256": self.source_sha,
                "load_bearing_node_ids": load_bearing,
            },
            "validation_granularity": "paper_target_closure",
            "paper_node_dispositions": [
                {
                    "paper_node_id": node_id,
                    "disposition": disposition[node_id],
                    "reason": "The node has an explicit lifecycle disposition.",
                }
                for node_id in load_bearing
            ],
            "paper_fact_mappings": [
                {
                    "paper_node_id": node_id,
                    "fact_id": fact.fact_id,
                    "relation_kind": relation[node_id],
                    "edge_ids": [incident[node_id]],
                    "reason": "The exact Paper relation remains inspectable.",
                }
                for node_id in load_bearing
            ],
            "component_inventory": [
                {
                    "component_id": "component-defense",
                    "fact_id": fact.fact_id,
                    "statement": fact.statement,
                    "statement_sha256": sha256_bytes(fact.statement.encode("utf-8")),
                    "source_component_refs": [
                        {
                            "source_node_id": logic_ids["s1"],
                            "source_component_id": "source-component-1",
                            "exact_span_sha256": sha256_bytes(
                                self.source_text.encode("utf-8")
                            ),
                        }
                    ],
                    "failure_surface_uids": [surface["surface_uid"]],
                    "independence_rationale": (
                        "This conclusion can be defeated without hiding another claim."
                    ),
                }
            ],
            "stance_preservation": {
                "policy": "steelman_headline",
                "declared_stance_sha256": sha256_bytes(
                    self.declared_stance.encode("utf-8")
                ),
                "headline_target_ids": [logic_ids["t1"]],
                "headline_impacts": [
                    {
                        "target_node_id": logic_ids["t1"],
                        "impact": "preserves_headline",
                        "reason": "The Candidate strengthens rather than reverses the thesis.",
                    }
                ],
                "major_revision_authorization_ids": [],
            },
        }
        closure = derive_paper_transport_closure(self.store, paper_refs)
        artifacts: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for member in closure["members"]:
            key = (member["artifact_sha256"], member["role"])
            if key in seen:
                continue
            seen.add(key)
            artifacts.append(
                {
                    "path": member["source_relpath"],
                    "sha256": member["artifact_sha256"],
                    "role": member["role"],
                }
            )
        artifacts.append(
            {
                "path": writing.relative_to(self.root).as_posix(),
                "sha256": sha256_bytes(writing.read_bytes()),
                "role": "paper_revised_writing",
            }
        )
        required_checks = {
            "mathematical",
            "typing",
            "scope",
            "source_and_applicability",
            "predecessor_interfaces",
            "computation_replay",
            "challenge_dispositions",
            "assurance_scope",
            "research_obligation_evidence",
            "program_math_semantic_alignment",
            "paper_source_fidelity",
            "paper_graph_structure",
            "paper_audit",
            "paper_target_coverage",
            "research_draft_admission_preflight",
            "composable_parallel_verification",
            "paper_evidence_transport_closure",
            "validated_dependency_receipt",
            "language_neutral_statement_interfaces",
            "semantic_component_atomicity",
            "stance_preservation",
        }
        payload = {
            "schema_version": 5,
            "bundle_claim": fact.statement,
            "candidates": [fact.as_submission_dict()],
            "research_entry_ids": [research["research_id"]],
            "claim_relation": "proves",
            "artifacts": artifacts,
            "verification_plan": {
                "mode": "closed_capsule",
                "authorized_artifact_roles": sorted(
                    {item["role"] for item in artifacts}
                ),
                "required_checks": sorted(required_checks),
            },
            "requested_assurance": assurance,
            "challenge_dispositions": [],
            "paper_evidence_refs": paper_refs,
            "adverse_actor_ids": [],
            "research_draft_ref": ref,
        }
        return payload, self.source

    def _parallel_aggregate(self, release: dict[str, object]) -> dict[str, object]:
        manager = self.lifecycle.parallel_verification()
        signers: dict[str, object] = {}

        def register(
            seed_byte: int,
            *,
            key_role: str,
            principal_id: str,
            reviewer_role: str | None = None,
            host_context: str | None = None,
            trust_domain: str,
        ) -> str:
            public, signer = _key_and_signer(bytes([seed_byte]) * 32)
            record = manager.register_key(
                {
                    "key_role": key_role,
                    "public_key_hex": public.hex(),
                    "principal_id": principal_id,
                    "reviewer_role_or_null": reviewer_role,
                    "host_context_id_or_null": host_context,
                    "trust_domain_id": trust_domain,
                },
                actor="fixture-operator",
                authority_role="operator",
            )
            signers[record["key_id"]] = signer
            return record["key_id"]

        planner_key = register(
            80,
            key_role="planner",
            principal_id="fixture-planner",
            trust_domain="fixture-control",
        )
        host_keys = [
            register(
                81 + index,
                key_role="host",
                principal_id=f"fixture-host-{index}",
                host_context=f"fixture-host-context-{index}",
                trust_domain=f"fixture-host-domain-{index}",
            )
            for index in range(2)
        ]
        reviewer_keys: list[str] = []
        seed = 1
        for role in sorted(pv.REVIEWER_ROLES):
            for overlap in range(2):
                reviewer_keys.append(
                    register(
                        seed,
                        key_role="reviewer",
                        principal_id=f"fixture-{role}-{overlap}",
                        reviewer_role=role,
                        trust_domain=f"fixture-review-domain-{role}-{overlap}",
                    )
                )
                seed += 1
        prepared_plan = manager.prepare_plan(
            release["release_id"],
            {
                "planner_key_id": planner_key,
                "host_key_ids": host_keys,
                "reviewer_key_ids": reviewer_keys,
                "context_budget": 5_000_000,
            },
        )
        plan_projection = {
            **prepared_plan["planner_attestation_body"],
            **prepared_plan["planner_attestation_projection_additions"],
        }
        plan_signature = signers[planner_key](pv.jcs_bytes(plan_projection))
        with self.assertRaisesRegex(ValueError, "signed-plan input"):
            manager.record_plan(
                release["release_id"],
                {"work_plan": prepared_plan["work_plan"]},
            )
        signed = manager.record_plan(
            release["release_id"],
            {
                "work_plan": prepared_plan["work_plan"],
                "planner_attestation": {
                    "algorithm": "Ed25519",
                    "key_id": planner_key,
                    "signature_hex": plan_signature.hex(),
                    "scope": f"plan:{prepared_plan['work_plan']['plan_id']}",
                },
            },
        )
        subjects = {
            item["object_id"]: item
            for item in signed["work_plan"]["obligation_register"]["subjects"]
        }

        def attest(prepared: dict[str, object], key_id: str, nonce: str):
            now = datetime.now(timezone.utc)
            issued = (now - timedelta(minutes=1)).isoformat()
            expires = (now + timedelta(minutes=10)).isoformat()
            fields = {
                "nonce": nonce,
                "scope": prepared["required_scope"],
                "issued_at": issued,
                "expires_at": expires,
                "result_visibility": "blind_to_peers",
                "key_id": key_id,
            }
            projection = {
                **prepared["attestation_body"],
                **fields,
                **prepared["attestation_projection_additions"],
            }
            signature = signers[key_id](pv.jcs_bytes(projection))
            return {
                "algorithm": "Ed25519",
                "key_id": key_id,
                "signature_hex": signature.hex(),
                "nonce": nonce,
                "scope": fields["scope"],
                "issued_at": issued,
                "expires_at": expires,
                "result_visibility": "blind_to_peers",
            }

        for index, assignment in enumerate(signed["work_plan"]["assignments"], 1):
            packet_prepared = manager.prepare_packet(
                signed["signed_plan_id"], assignment["slot_id"]
            )
            host_attestation = attest(
                packet_prepared,
                assignment["host_key_id"],
                f"fixture-packet-{index}",
            )
            if index == 2:
                replayed_attestation = attest(
                    packet_prepared,
                    assignment["host_key_id"],
                    "fixture-packet-1",
                )
                replayed_packet = {
                    **packet_prepared["record"],
                    "host_attestation": replayed_attestation,
                }
                with self.assertRaisesRegex(ValueError, "nonce was replayed"):
                    manager.record_packet(
                        signed["signed_plan_id"], replayed_packet
                    )
            packet = {
                **packet_prepared["record"],
                "host_attestation": host_attestation,
            }
            manager.record_packet(signed["signed_plan_id"], packet)
            receipt_payload = {
                "obligation_results": [
                    {
                        "obligation_id": obligation_id,
                        "status": "supported",
                        "finding_ids": [],
                        "proof_anchor_ids": [f"proof:{obligation_id}"],
                        "not_applicable_witness_or_null": None,
                    }
                    for obligation_id in assignment["obligation_ids"]
                ],
                "subject_hashes": [
                    {
                        "object_id": subject_id,
                        "semantic_sha256_or_null": subjects[subject_id][
                            "object_semantic_sha256_or_null"
                        ],
                        "file_sha256_or_null": subjects[subject_id][
                            "object_file_sha256_or_null"
                        ],
                    }
                    for subject_id in assignment["subject_ids"]
                ],
                "conflicts": [],
                "new_obligations": [],
            }
            receipt_prepared = manager.prepare_receipt(
                signed["signed_plan_id"], assignment["slot_id"], receipt_payload
            )
            reviewer_attestation = attest(
                receipt_prepared,
                assignment["reviewer_key_id"],
                f"fixture-receipt-{index}",
            )
            receipt = {
                **receipt_prepared["record"],
                "reviewer_attestation": reviewer_attestation,
            }
            manager.record_receipt(signed["signed_plan_id"], receipt)
        return manager.aggregate(signed["signed_plan_id"])

    def test_strict_release_closes_every_plane_and_invalidates_only_changed_dependency(self) -> None:
        payload, _ = self._build_payload()
        checked = self.lifecycle.candidate_release(
            payload, producer="producer", preflight_only=True
        )
        self.assertTrue(checked["valid"])
        release = self.lifecycle.candidate_release(payload, producer="producer")
        self.assertEqual(
            release["research_draft_admission_preflight"]["structural_status"],
            "PASS",
        )
        self.assertEqual(
            release["research_draft_admission_preflight"]["truth_effect"],
            "none",
        )
        cache_path = (
            self.lifecycle.candidate_releases_dir
            / "_dependency_cache"
            / f"{release['release_id']}.json"
        )
        self.assertTrue(cache_path.is_file())
        before = cache_path.read_bytes()
        reread = self.lifecycle.release(release["release_id"])
        self.assertEqual(reread["release_id"], release["release_id"])
        self.assertEqual(cache_path.read_bytes(), before)
        capsule = self.lifecycle.verifier_capsule(release["release_id"])
        self.assertEqual(
            capsule["research_draft_admission_preflight"]["preflight_id"],
            release["research_draft_admission_preflight"]["preflight_id"],
        )
        reviewer = "fresh-verifier"
        decision_payload = {
            "schema_version": 5,
            "release_id": release["release_id"],
            "release_sha256": release["release_sha256"],
            "capsule_sha256": capsule["capsule_sha256"],
            "verdict": "correct",
            "findings": [],
            "check_results": [
                {"check_id": check, "status": "pass", "findings": []}
                for check in capsule["required_checks"]
            ],
            "candidate_checks": [
                {"fact_id": fact_id, "verdict": "correct", "findings": []}
                for fact_id in release["fact_ids"]
            ],
            "edge_checks": [],
            "assurance_matrix": self.lifecycle._expected_assurance_matrix(release),
            "reviewer": reviewer,
            "host_attestation": {
                "host": "fresh-host",
                "agent_id": reviewer,
                "isolation": "fresh_context",
                "fork_turns": "none",
                "allowed_capsule_sha256": capsule["capsule_sha256"],
            },
        }
        with self.assertRaisesRegex(
            ValueError, "missing=/parallel_verification_aggregate_id"
        ):
            self.lifecycle.certification_record(decision_payload, preflight_only=True)
        aggregate = self._parallel_aggregate(release)
        decision_payload["parallel_verification_aggregate_id"] = aggregate[
            "aggregate"
        ]["aggregate_id"]
        decision = self.lifecycle.certification_record(decision_payload)
        admitted = self.lifecycle.fact_admit(
            release_id=release["release_id"],
            decision_id=decision["decision_id"],
            gateway="independent-gateway",
        )
        self.assertEqual(admitted["fact_ids"], release["fact_ids"])
        dependency = next(
            item
            for item in release["validated_dependency_receipt"]["dependencies"]
            if item["kind"] == "paper_source_artifact"
            and item["relpath_or_null"] is not None
        )
        dependency_path = self.root / dependency["relpath_or_null"]
        os.utime(dependency_path, None)
        refreshed = self.lifecycle.release(release["release_id"])
        self.assertEqual(refreshed["release_id"], release["release_id"])
        dependency_path.write_text("Drifted source bytes.", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "file key changed"):
            self.lifecycle.release(release["release_id"])

    def test_strict_release_rejects_mapping_component_and_stance_seam_drift(self) -> None:
        payload, _ = self._build_payload()
        missing_mapping = copy.deepcopy(payload)
        missing_mapping["requested_assurance"]["paper_fact_mappings"].pop()
        with self.assertRaisesRegex(ValueError, "retained Paper node"):
            self.lifecycle.candidate_release(
                missing_mapping, producer="producer", preflight_only=True
            )
        missing_component = copy.deepcopy(payload)
        missing_component["requested_assurance"]["component_inventory"] = []
        with self.assertRaisesRegex(ValueError, "Candidate-total"):
            self.lifecycle.candidate_release(
                missing_component, producer="producer", preflight_only=True
            )
        stance_drift = copy.deepcopy(payload)
        stance_drift["requested_assurance"]["stance_preservation"][
            "declared_stance_sha256"
        ] = "0" * 64
        with self.assertRaisesRegex(ValueError, "stance preservation drifted"):
            self.lifecycle.candidate_release(
                stance_drift, producer="producer", preflight_only=True
            )
        authorization_drift = copy.deepcopy(payload)
        authorization_drift["requested_assurance"]["stance_preservation"][
            "major_revision_authorization_ids"
        ] = ["rda-" + "0" * 64]
        with self.assertRaisesRegex(ValueError, "non-major research-draft stance"):
            self.lifecycle.candidate_release(
                authorization_drift, producer="producer", preflight_only=True
            )
        interface_component_drift = copy.deepcopy(payload)
        interface_component_drift["candidates"][0]["semantic_interface"][0][
            "component_id"
        ] = "component-hidden"
        with self.assertRaisesRegex(ValueError, "component identity drifts"):
            self.lifecycle.candidate_release(
                interface_component_drift,
                producer="producer",
                preflight_only=True,
            )
        interface_operator_drop = copy.deepcopy(payload)
        interface_operator_drop["candidates"][0]["semantic_interface"][0][
            "operators"
        ] = []
        with self.assertRaisesRegex(ValueError, "drops a source operator"):
            self.lifecycle.candidate_release(
                interface_operator_drop,
                producer="producer",
                preflight_only=True,
            )
        interface_qualifier_drop = copy.deepcopy(payload)
        interface_qualifier_drop["candidates"][0]["semantic_interface"][0][
            "qualifiers"
        ] = []
        with self.assertRaisesRegex(ValueError, "drops a source qualifier"):
            self.lifecycle.candidate_release(
                interface_qualifier_drop,
                producer="producer",
                preflight_only=True,
            )


if __name__ == "__main__":
    unittest.main()

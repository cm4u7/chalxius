from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mathgraph.store import MathGraphStore
from mathgraph.contracts import sha256_bytes, sha256_json
from mathgraph.roles import allowed_commands_for_workflow


class FactAlphaTests(unittest.TestCase):
    def test_fact_packager_role_is_narrow_and_worker_does_not_inherit_it(
        self,
    ) -> None:
        self.assertEqual(
            allowed_commands_for_workflow("fact-packager", 5),
            {"fact-frontier", "fact-package-seal"},
        )
        worker_commands = allowed_commands_for_workflow("worker", 5)
        self.assertNotIn("fact-frontier", worker_commands)
        self.assertNotIn("fact-package-seal", worker_commands)
        self.assertNotIn("fact-verification-record", worker_commands)
        self.assertNotIn("fact-certify", worker_commands)

        self.assertEqual(
            allowed_commands_for_workflow("verifier", 5),
            {
                "fact-verifier-capsule",
                "fact-verification-record",
                "fact-verification-check",
            },
        )
        self.assertEqual(
            allowed_commands_for_workflow("verifier", 4),
            set(),
        )

    @staticmethod
    def _store(root: Path) -> MathGraphStore:
        store = MathGraphStore(root)
        store.initialize(
            project_id="fact-alpha-fixture",
            title="Fact alpha fixture",
            workflow_evidence_version=5,
        )
        return store

    @staticmethod
    def _interface(
        research: dict[str, object],
        *,
        predecessors: list[str] | None = None,
    ) -> dict[str, object]:
        return {
            "conclusion": research["claim"],
            "assumptions": ["The hypotheses stated in the Research claim hold."],
            "domain_and_types": ["Objects and maps have the types fixed in the proof."],
            "quantifiers": ["All quantifiers are those of the exact Research claim."],
            "certified_predecessor_research_ids": predecessors or [],
            "limitations": ["No conclusion beyond the exact Research claim is certified."],
        }

    @staticmethod
    def _correct_component_check(
        component: dict[str, object],
    ) -> dict[str, object]:
        entries = component["entries"]
        edges = component["edges"]
        assert isinstance(entries, list)
        assert isinstance(edges, list)
        all_edges = [*edges]
        for entry in entries:
            all_edges.extend(
                {
                    "predecessor_research_id": binding[
                        "predecessor_research_id"
                    ],
                    "research_id": entry["research_id"],
                }
                for binding in entry["external_predecessor_bindings"]
            )
        return {
            "component_id": component["component_id"],
            "verdict": "correct",
            "research_checks": [
                {
                    "research_id": entry["research_id"],
                    "verdict": "correct",
                    "notes": "The complete Research claim and proof bytes are correct.",
                }
                for entry in entries
            ],
            "edge_checks": [
                {
                    "predecessor_research_id": edge[
                        "predecessor_research_id"
                    ],
                    "research_id": edge["research_id"],
                    "verdict": "correct",
                    "notes": "The predecessor is necessary and sufficient as used.",
                }
                for edge in all_edges
            ],
            "interface_checks": [
                {
                    "research_id": entry["research_id"],
                    "verdict": "correct",
                    "notes": "The semi-formal interface faithfully preserves the claim.",
                }
                for entry in entries
            ],
            "findings": [],
            "notes": "Independent whole-node verification passed.",
        }

    def _package(
        self,
        manager: object,
        research: list[dict[str, object]],
        *,
        predecessor_map: dict[str, list[str]] | None = None,
        separate_components: bool = False,
    ) -> dict[str, object]:
        predecessor_map = predecessor_map or {}
        marks = [
            manager.mark(
                item["research_id"],
                rationale="This Research claim is load-bearing for the current program.",
            )
            for item in research
        ]
        plan = manager.plan_packaging([item["mark_id"] for item in marks])
        self.assertEqual(
            plan["mechanical_package_state"],
            "interface_preparation_required",
        )
        components = (
            [
                {
                    "component_key": f"component-{index}",
                    "entries": [
                        {
                            "research_id": item["research_id"],
                            "statement_interface": self._interface(
                                item,
                                predecessors=predecessor_map.get(
                                    item["research_id"], []
                                ),
                            ),
                        }
                    ],
                }
                for index, item in enumerate(research, 1)
            ]
            if separate_components
            else [
                {
                    "component_key": "one-load-bearing-component",
                    "entries": [
                        {
                            "research_id": item["research_id"],
                            "statement_interface": self._interface(
                                item,
                                predecessors=predecessor_map.get(
                                    item["research_id"], []
                                ),
                            ),
                        }
                        for item in research
                    ],
                }
            ]
        )
        return manager.seal_package(
            {
                "schema_version": 1,
                "plan_id": plan["plan_id"],
                "packager": "fact-packager-agent",
                "components": components,
                "blocked_entries": [],
            }
        )

    def _correct_decision(
        self,
        manager: object,
        package: dict[str, object],
    ) -> dict[str, object]:
        capsule = manager.verifier_capsule(package["package_id"])
        return manager.record_decision(
            {
                "schema_version": 1,
                "package_id": package["package_id"],
                "package_record_sha256": package["record_sha256"],
                "capsule_sha256": capsule["capsule_sha256"],
                "reviewer": "independent-fact-verifier",
                "component_checks": [
                    self._correct_component_check(component)
                    for component in package["components"]
                ],
                "overall_notes": "Every selected component passed independent verification.",
            }
        )

    def test_single_research_graph_node_receives_fact_overlay(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            research = lifecycle.add_research(
                {
                    "claim": "For every object in the fixed domain, property P holds.",
                    "content": "A complete direct proof of property P.",
                },
                actor="research-author",
            )
            manager = lifecycle.fact_alpha()
            package = self._package(manager, [research])
            decision = self._correct_decision(manager, package)
            acceptance = manager.certify(
                decision["decision_id"], gateway="mechanical-gateway"
            )

            self.assertEqual(len(acceptance["grant_ids"]), 1)
            frontier = manager.frontier()
            self.assertEqual(frontier["counts"], {"certified": 1})
            self.assertEqual(
                frontier["certified_heads"][0]["research_id"],
                research["research_id"],
            )
            self.assertEqual(frontier["entries"][0]["state"], "certified")
            downstream = lifecycle.add_research(
                {
                    "claim": "A downstream result uses the certified property P.",
                    "content": "Invoke the exact certified Research premise.",
                    "certified_research_dependencies": [
                        research["research_id"]
                    ],
                },
                actor="downstream-author",
            )
            premise = downstream["metadata"][
                "certified_research_premises"
            ][0]
            self.assertEqual(premise["research_id"], research["research_id"])
            self.assertEqual(premise["grant_id"], acceptance["grant_ids"][0])
            mark_files = list(manager.marks_dir.glob("*.json"))
            self.assertEqual(len(mark_files), 1)
            mark_text = mark_files[0].read_text(encoding="utf-8")
            self.assertNotIn("A complete direct proof", mark_text)

    def test_certified_predecessor_closure_and_heads_are_research_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            predecessor = lifecycle.add_research(
                {
                    "claim": "Lemma L holds.",
                    "content": "Proof of L.",
                },
                actor="research-author-a",
            )
            theorem = lifecycle.add_research(
                {
                    "claim": "Theorem T follows from Lemma L.",
                    "content": "Apply L in the fixed setting.",
                },
                actor="research-author-b",
            )
            manager = lifecycle.fact_alpha()
            package = self._package(
                manager,
                [predecessor, theorem],
                predecessor_map={
                    theorem["research_id"]: [predecessor["research_id"]]
                },
            )
            decision = self._correct_decision(manager, package)
            manager.certify(decision["decision_id"], gateway="mechanical-gateway")

            frontier = manager.frontier()
            self.assertEqual(
                [item["research_id"] for item in frontier["certified_heads"]],
                [theorem["research_id"]],
            )
            grants = manager._accepted_grants()
            theorem_grant = next(
                grant
                for grant in grants.values()
                if grant["research_id"] == theorem["research_id"]
            )
            self.assertEqual(
                theorem_grant["predecessor_bindings"][0][
                    "predecessor_research_id"
                ],
                predecessor["research_id"],
            )

            repaired_predecessor = lifecycle.add_research(
                {
                    "claim": "A corrected form of Lemma L holds.",
                    "content": "A corrected proof of L.",
                },
                actor="repair-author",
            )

            def terminal(research_id: str, **_kwargs: object) -> str:
                return (
                    repaired_predecessor["research_id"]
                    if research_id == predecessor["research_id"]
                    else research_id
                )

            with patch.object(manager, "_terminal_for", side_effect=terminal):
                stale_frontier = manager.frontier()
            stale_states = {
                item["current_research_id"]: item["state"]
                for item in stale_frontier["entries"]
            }
            self.assertEqual(
                stale_states[repaired_predecessor["research_id"]],
                "needs_reverification",
            )
            self.assertEqual(
                stale_states[theorem["research_id"]],
                "needs_reverification",
            )

    def test_one_bad_component_does_not_discard_an_independent_good_component(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            good = lifecycle.add_research(
                {"claim": "Independent claim A is true.", "content": "Proof A."},
                actor="author-a",
            )
            bad = lifecycle.add_research(
                {"claim": "Independent claim B is true.", "content": "Flawed proof B."},
                actor="author-b",
            )
            manager = lifecycle.fact_alpha()
            package = self._package(
                manager, [good, bad], separate_components=True
            )
            capsule = manager.verifier_capsule(package["package_id"])
            component_by_research = {
                component["entries"][0]["research_id"]: component
                for component in package["components"]
            }
            bad_component = component_by_research[bad["research_id"]]
            bad_check = {
                "component_id": bad_component["component_id"],
                "verdict": "fundamental_error",
                "research_checks": [
                    {
                        "research_id": bad["research_id"],
                        "verdict": "fundamental_error",
                        "notes": "The central implication is false.",
                    }
                ],
                "edge_checks": [],
                "interface_checks": [
                    {
                        "research_id": bad["research_id"],
                        "verdict": "reject",
                        "notes": "The interface exposes the false conclusion faithfully.",
                    }
                ],
                "findings": [
                    {
                        "finding_id": "false-central-implication",
                        "severity": "fundamental",
                        "research_ids": [bad["research_id"]],
                        "description": "The proof uses an invalid central implication.",
                        "repair_guidance": "Return to ordinary Research and rebuild the argument.",
                    }
                ],
                "notes": "This component cannot be certified.",
            }
            decision = manager.record_decision(
                {
                    "schema_version": 1,
                    "package_id": package["package_id"],
                    "package_record_sha256": package["record_sha256"],
                    "capsule_sha256": capsule["capsule_sha256"],
                    "reviewer": "independent-fact-verifier",
                    "component_checks": [
                        self._correct_component_check(
                            component_by_research[good["research_id"]]
                        ),
                        bad_check,
                    ],
                    "overall_notes": "Component A passes; component B fails fundamentally.",
                }
            )
            acceptance = manager.certify(
                decision["decision_id"], gateway="mechanical-gateway"
            )

            self.assertEqual(len(acceptance["grant_ids"]), 1)
            grant = next(iter(manager._accepted_grants().values()))
            self.assertEqual(grant["research_id"], good["research_id"])
            frontier = manager.frontier()
            states = {
                item["current_research_id"]: item["state"]
                for item in frontier["entries"]
            }
            self.assertEqual(states[good["research_id"]], "certified")
            self.assertEqual(states[bad["research_id"]], "blocked_by_research")

    def test_self_consistent_acceptance_rewrite_cannot_rebind_grants(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            research = lifecycle.add_research(
                {
                    "claim": "The load-bearing claim survives exact verification.",
                    "content": "A complete proof bound to this Research record.",
                },
                actor="research-author",
            )
            manager = lifecycle.fact_alpha()
            package = self._package(manager, [research])
            decision = self._correct_decision(manager, package)
            acceptance = manager.certify(
                decision["decision_id"], gateway="mechanical-gateway"
            )
            path = manager.acceptances_dir / f"{decision['decision_id']}.json"
            rewritten = json.loads(path.read_text(encoding="utf-8"))
            rewritten["gateway"] = "substituted-gateway"
            semantic = {
                key: value
                for key, value in rewritten.items()
                if key not in {"acceptance_id", "record_sha256"}
            }
            rewritten["acceptance_id"] = "fact-acceptance-" + sha256_json(
                semantic
            )
            rewritten["record_sha256"] = sha256_json(
                {
                    key: value
                    for key, value in rewritten.items()
                    if key != "record_sha256"
                }
            )
            path.write_text(
                json.dumps(rewritten, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "acceptance/grant binding"):
                manager._accepted_grants()
            self.assertEqual(len(acceptance["grant_ids"]), 1)

    def test_fact_frontier_limit_bounds_entries_heads_and_batch_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            manager = lifecycle.fact_alpha()
            for index in range(5):
                research = lifecycle.add_research(
                    {
                        "claim": f"Independent bounded claim {index}.",
                        "content": f"Complete bounded proof {index}.",
                    },
                    actor=f"author-{index}",
                )
                manager.mark(
                    research["research_id"],
                    rationale=f"Load-bearing claim {index}.",
                )

            frontier = manager.frontier(limit=2)
            self.assertEqual(frontier["entry_count"], 5)
            self.assertEqual(frontier["shown_count"], 2)
            self.assertEqual(len(frontier["entries"]), 2)
            self.assertEqual(frontier["ready_for_packaging_count"], 5)
            self.assertEqual(
                sum(
                    len(batch["research_ids"])
                    for batch in frontier["batch_opportunities"]
                ),
                2,
            )
            self.assertLessEqual(len(frontier["certified_heads"]), 2)

    def test_gateway_does_not_substitute_a_newer_external_predecessor_grant(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            predecessor = lifecycle.add_research(
                {"claim": "Certified lemma L.", "content": "Proof of L."},
                actor="lemma-author",
            )
            dependent = lifecycle.add_research(
                {
                    "claim": "Theorem T uses certified lemma L.",
                    "content": "Proof of T from L.",
                },
                actor="theorem-author",
            )
            manager = lifecycle.fact_alpha()

            first_package = self._package(manager, [predecessor])
            first_decision = self._correct_decision(manager, first_package)
            first_acceptance = manager.certify(
                first_decision["decision_id"], gateway="mechanical-gateway"
            )
            dependent_package = self._package(
                manager,
                [dependent],
                predecessor_map={
                    dependent["research_id"]: [predecessor["research_id"]]
                },
            )
            dependent_decision = self._correct_decision(
                manager, dependent_package
            )

            replacement_package = self._package(manager, [predecessor])
            replacement_decision = self._correct_decision(
                manager, replacement_package
            )
            replacement_acceptance = manager.certify(
                replacement_decision["decision_id"],
                gateway="mechanical-gateway",
            )
            self.assertNotEqual(
                first_acceptance["grant_ids"],
                replacement_acceptance["grant_ids"],
            )
            with self.assertRaisesRegex(
                ValueError, "external predecessor changed after verification"
            ):
                manager.certify(
                    dependent_decision["decision_id"],
                    gateway="mechanical-gateway",
                )

    def test_minor_error_cow_returns_to_same_verifier_without_supervisor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            original = lifecycle.add_research(
                {
                    "claim": "Claim C holds with the stated normalization.",
                    "content": "The argument contains one repairable sign typo.",
                },
                actor="original-author",
            )
            manager = lifecycle.fact_alpha()
            package = self._package(manager, [original])
            component = package["components"][0]
            capsule = manager.verifier_capsule(package["package_id"])
            minor_decision = manager.record_decision(
                {
                    "schema_version": 1,
                    "package_id": package["package_id"],
                    "package_record_sha256": package["record_sha256"],
                    "capsule_sha256": capsule["capsule_sha256"],
                    "reviewer": "same-independent-verifier",
                    "component_checks": [
                        {
                            "component_id": component["component_id"],
                            "verdict": "minor_repair",
                            "research_checks": [
                                {
                                    "research_id": original["research_id"],
                                    "verdict": "minor_error",
                                    "notes": "One displayed sign is inconsistent with the proof.",
                                }
                            ],
                            "edge_checks": [],
                            "interface_checks": [
                                {
                                    "research_id": original["research_id"],
                                    "verdict": "reject",
                                    "notes": "The interface must use the corrected sign convention.",
                                }
                            ],
                            "findings": [
                                {
                                    "finding_id": "sign-normalization",
                                    "severity": "minor",
                                    "research_ids": [original["research_id"]],
                                    "description": "A sign typo affects the displayed normalization.",
                                    "repair_guidance": "COW the complete Research node and correct the sign.",
                                }
                            ],
                            "notes": "The mathematical mechanism is intact after a local COW.",
                        }
                    ],
                    "overall_notes": "A bounded same-verifier repair is sufficient.",
                }
            )
            repaired = lifecycle.add_research(
                {
                    "claim": "Claim C holds with the corrected stated normalization.",
                    "content": "The same complete argument with the sign corrected.",
                },
                actor="repair-author",
            )
            mark_id = next(iter(manager._marks()))
            missing_coverage = [
                {
                    "production_round_id": "round-20260829T000000Z-00000001",
                    "source_component_id": None,
                    "scope": "proof_logic",
                    "state": "missing",
                    "result_research_ids": [],
                    "pending_round_ids": [],
                }
            ]

            def terminal(research_id: str, **_kwargs: object) -> str:
                return (
                    repaired["research_id"]
                    if research_id == original["research_id"]
                    else research_id
                )

            with patch.object(manager, "_terminal_for", side_effect=terminal), patch.object(
                lifecycle,
                "_candidate_supervision_scope_coverage",
                return_value=missing_coverage,
            ):
                repair_plan = manager.plan_packaging(
                    [mark_id],
                    minor_repair_decision_id=minor_decision["decision_id"],
                )
            self.assertEqual(repair_plan["selection"][0]["eligibility"], "eligible")
            self.assertIn(
                "same_verifier_minor_repair_lane_replaces_ordinary_supervision",
                repair_plan["selection"][0]["warnings"],
            )
            repair_package = manager.seal_package(
                {
                    "schema_version": 1,
                    "plan_id": repair_plan["plan_id"],
                    "packager": "repair-packager",
                    "components": [
                        {
                            "component_key": "corrected-component",
                            "entries": [
                                {
                                    "research_id": repaired["research_id"],
                                    "statement_interface": self._interface(repaired),
                                }
                            ],
                        }
                    ],
                    "blocked_entries": [],
                }
            )
            repair_capsule = manager.verifier_capsule(
                repair_package["package_id"]
            )
            repair_decision = manager.record_decision(
                {
                    "schema_version": 1,
                    "package_id": repair_package["package_id"],
                    "package_record_sha256": repair_package["record_sha256"],
                    "capsule_sha256": repair_capsule["capsule_sha256"],
                    "reviewer": "same-independent-verifier",
                    "component_checks": [
                        self._correct_component_check(
                            repair_package["components"][0]
                        )
                    ],
                    "overall_notes": "The complete COW node now passes.",
                }
            )
            acceptance = manager.certify(
                repair_decision["decision_id"], gateway="mechanical-gateway"
            )
            self.assertEqual(len(acceptance["grant_ids"]), 1)

    def test_scoped_frontier_explains_filtered_unbound_marks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            research = lifecycle.add_research(
                {
                    "claim": "A shared root claim is available globally.",
                    "content": "A complete root argument.",
                },
                actor="root-author",
            )
            manager = lifecycle.fact_alpha()
            manager.mark(
                research["research_id"],
                rationale="This is a shared load-bearing root.",
            )

            scoped = manager.frontier(campaign_id="campaign-aaaaaaaaaaaa")

            self.assertEqual(scoped["entries"], [])
            self.assertEqual(
                scoped["scope_projection"]["global_active_mark_count"], 1
            )
            self.assertEqual(
                scoped["scope_projection"]["in_scope_active_mark_count"], 0
            )
            self.assertEqual(
                scoped["scope_projection"]["filtered_out_unbound_mark_count"], 1
            )
            self.assertIn(
                "global Fact frontier",
                scoped["scope_projection"]["note"],
            )

    def test_empty_overlay_advises_unique_legacy_production_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            artifact = store.root / "evidence" / "legacy-root.md"
            artifact.parent.mkdir(parents=True)
            artifact.write_text("legacy root bytes", encoding="utf-8")
            artifact_binding = {
                "path": artifact.relative_to(store.root).as_posix(),
                "sha256": sha256_bytes(artifact.read_bytes()),
                "role": "candidate_fact",
            }
            production = lifecycle.add_research(
                {
                    "kind": "proof_attempt",
                    "claim": "The exact legacy root statement holds.",
                    "content": "A complete constructive proof.",
                    "worker_outcome": "proof",
                    "assignment_provenance": {
                        "schema_version": 1,
                        "round_id": "round-20260830T000000Z-00000001",
                        "assignment_id": "a01-aaaaaaaaaaaa-prove",
                        "worker_id": "a01-aaaaaaaaaaaa-prove",
                        "task_card_sha256": "a" * 64,
                        "work_mode": "prove",
                        "adverse_assignment": False,
                    },
                    "artifacts": [artifact_binding],
                },
                actor="a01-aaaaaaaaaaaa-prove",
            )
            lifecycle.add_research(
                {
                    "kind": "synthesis",
                    "claim": "A synthesis reuses the legacy bytes.",
                    "content": "This is not a production carrier.",
                    "artifacts": [artifact_binding],
                },
                actor="main-synthesis",
            )
            manager = lifecycle.fact_alpha()
            legacy_fact = SimpleNamespace(
                fact_id="1111111111111111",
                predecessors=[],
                statement="The exact legacy root statement holds.",
            )
            with patch.object(
                store,
                "facts",
                return_value={legacy_fact.fact_id: legacy_fact},
            ), patch.object(
                store,
                "statement_interface",
                return_value={"stored_fact_sha256": artifact_binding["sha256"]},
            ):
                frontier = manager.frontier()

            bootstrap = frontier["legacy_root_bootstrap"]
            self.assertEqual(
                bootstrap["state"], "exact_legacy_roots_available"
            )
            self.assertEqual(bootstrap["exact_candidate_count"], 1)
            self.assertEqual(bootstrap["ambiguous_count"], 0)
            self.assertEqual(
                bootstrap["candidates"][0]["production_carrier_research_id"],
                production["research_id"],
            )
            self.assertEqual(manager._marks(), {})
            self.assertEqual(manager._accepted_grants(), {})

    def test_supervised_interface_mechanically_seals_and_preserves_evidence_layer(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            evidence = store.root / "evidence" / "proof.md"
            evidence.parent.mkdir(parents=True)
            evidence.write_text("complete proof evidence", encoding="utf-8")
            evidence_binding = {
                "path": evidence.relative_to(store.root).as_posix(),
                "sha256": sha256_bytes(evidence.read_bytes()),
                "role": "research_product",
            }
            research = lifecycle.add_research(
                {
                    "claim": "The supervised whole-node theorem holds.",
                    "content": "A complete proof of the theorem.",
                    "artifacts": [evidence_binding],
                },
                actor="research-author",
            )
            interface_artifact = (
                store.root / "evidence" / "supervised-interface.json"
            )
            interface_payload = {
                "schema_version": 1,
                "contract_revision": (
                    "chalxius-supervised-statement-interfaces-1"
                ),
                "entries": [
                    {
                        "research_id": research["research_id"],
                        "research_record_sha256": research["record_sha256"],
                        "disposition": "ready",
                        "rationale": (
                            "The complete Research claim is one coherent surface."
                        ),
                        "statement_interface": self._interface(research),
                    }
                ],
                "truth_effect": "none",
            }
            interface_artifact.write_text(
                json.dumps(interface_payload, sort_keys=True), encoding="utf-8"
            )
            supervisor = lifecycle.add_research(
                {
                    "kind": "insight",
                    "claim": "Bounded proof-logic supervision is clean.",
                    "content": "The complete theorem and interface were reviewed.",
                    "artifacts": [
                        {
                            "path": interface_artifact.relative_to(
                                store.root
                            ).as_posix(),
                            "sha256": sha256_bytes(
                                interface_artifact.read_bytes()
                            ),
                            "role": "fact_statement_interfaces",
                        }
                    ],
                },
                actor="independent-supervisor",
            )
            coverage = [
                {
                    "production_round_id": "round-20260830T000000Z-00000002",
                    "source_component_id": None,
                    "scope": "proof_logic",
                    "state": "completed",
                    "result_research_ids": [supervisor["research_id"]],
                    "pending_round_ids": [],
                }
            ]
            manager = lifecycle.fact_alpha()
            mark = manager.mark(
                research["research_id"],
                rationale="This theorem is load-bearing.",
            )
            with patch.object(
                lifecycle,
                "_candidate_supervision_scope_coverage",
                return_value=coverage,
            ):
                plan = manager.plan_packaging([mark["mark_id"]])

            self.assertEqual(
                plan["mechanical_package_state"], "mechanically_sealed"
            )
            package = manager.package(plan["mechanical_package_id"])
            self.assertEqual(
                package["packager"],
                "mechanical-supervision-interface-projection",
            )
            self.assertEqual(
                set(
                    package["components"][0]["entries"][0][
                        "statement_interface"
                    ]
                ),
                {
                    "conclusion",
                    "assumptions",
                    "domain_and_types",
                    "quantifiers",
                    "certified_predecessor_research_ids",
                    "limitations",
                },
            )
            capsule = manager.verifier_capsule(package["package_id"])
            capsule_research = capsule["research_records"][0][
                "research_record"
            ]
            self.assertEqual(
                capsule_research["metadata"]["artifacts"], [evidence_binding]
            )
            self.assertNotIn(
                evidence_binding["path"],
                package["components"][0]["entries"][0][
                    "statement_interface"
                ]["limitations"],
            )

    def test_supervisor_needs_split_blocks_mechanical_packaging(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            research = lifecycle.add_research(
                {
                    "claim": (
                        "One node currently mixes a lemma and a stronger theorem."
                    ),
                    "content": (
                        "The two strengths require separate certification surfaces."
                    ),
                },
                actor="research-author",
            )
            manager = lifecycle.fact_alpha()
            mark = manager.mark(
                research["research_id"],
                rationale="The node is important but structurally mixed.",
            )
            coverage = [
                {
                    "production_round_id": "round-20260830T000000Z-00000003",
                    "source_component_id": None,
                    "scope": "proof_logic",
                    "state": "completed",
                    "result_research_ids": [],
                    "pending_round_ids": [],
                }
            ]
            split_projection = {
                "state": "needs_split",
                "statement_interface": None,
                "source_bindings": [],
                "source_count": 1,
                "rationales": [
                    "The lemma and stronger theorem have different assumptions."
                ],
                "diagnostic_sha256": "b" * 64,
            }
            with patch.object(
                lifecycle,
                "_candidate_supervision_scope_coverage",
                return_value=coverage,
            ), patch.object(
                manager,
                "_supervised_interface_projection",
                return_value=split_projection,
            ):
                plan = manager.plan_packaging([mark["mark_id"]])
                frontier = manager.frontier()

            self.assertEqual(
                plan["mechanical_package_state"], "research_split_required"
            )
            self.assertEqual(plan["mechanical_package_id"], None)
            self.assertEqual(plan["next_action"], "research-cow-or-split")
            self.assertEqual(
                frontier["entries"][0]["state"], "blocked_by_research"
            )
            self.assertEqual(
                frontier["entries"][0]["interface_preparation"]["state"],
                "needs_split",
            )


if __name__ == "__main__":
    unittest.main()

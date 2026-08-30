from __future__ import annotations

import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mathgraph.store import MathGraphStore
from mathgraph.contracts import sha256_bytes, sha256_json
from mathgraph.roles import allowed_commands_for_workflow
from mathgraph.cli import main as mgraph_main


class FactAlphaTests(unittest.TestCase):
    def test_plan_cli_exposes_packager_mechanical_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            proposal = {
                "schema_version": 1,
                "plan_id": "fact-plan-" + "a" * 64,
                "packager": "fact-packager",
                "components": [],
                "blocked_entries": [],
            }
            projected = {
                "plan_id": proposal["plan_id"],
                "record_sha256": "b" * 64,
                "selection": [],
                "mechanical_package_state": "mechanical_proposal_ready",
                "mechanical_package_id": None,
                "mechanical_package_record_sha256": None,
                "mechanical_package_proposal": proposal,
                "mechanical_package_proposal_sha256": sha256_json(proposal),
                "interface_source_bindings_sha256": sha256_json([]),
                "interface_preparation_unavailable": [],
                "next_action": "fact-package-seal",
            }
            output = StringIO()
            with patch(
                "mathgraph.fact_alpha.FactAlphaManager.plan_packaging",
                return_value=projected,
            ), redirect_stdout(output):
                mgraph_main(
                    [
                        "--root",
                        str(store.root),
                        "--role",
                        "fact-packager",
                        "plan-fact-packaging",
                        "--mark-id",
                        "fact-mark-" + "c" * 64,
                    ]
                )
            rendered = json.loads(output.getvalue())
            self.assertEqual(
                rendered["mechanical_package_state"],
                "mechanical_proposal_ready",
            )
            self.assertEqual(
                rendered["mechanical_package_proposal"], proposal
            )
            self.assertEqual(
                rendered["mechanical_package_proposal_sha256"],
                sha256_json(proposal),
            )
            self.assertEqual(rendered["next_action"], "fact-package-seal")

    def test_fact_packager_role_is_narrow_and_worker_does_not_inherit_it(
        self,
    ) -> None:
        self.assertEqual(
            allowed_commands_for_workflow("fact-packager", 5),
            {
                "fact-frontier",
                "plan-fact-packaging",
                "fact-package-seal",
            },
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

    def test_packager_selects_landmark_route_and_unmarked_predecessor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            with store.v5_mutation_lock(command="fact-packager-fixture"):
                campaign_id = store.campaigns().create(
                    {
                        "name": "Fact route",
                        "objective": "Certify a sparse load-bearing route.",
                        "source_claim_ids": [],
                        "targets": [],
                        "constraints": [],
                        "stop_conditions": [],
                        "value_definition": "Preserve exact Research ancestry.",
                    },
                    actor="main",
                    fact_exists=lambda _fact_id: False,
                )
            lifecycle = store.v5_lifecycle()
            predecessor = lifecycle.add_research(
                {
                    "claim": "A predecessor lemma holds.",
                    "content": "Proof of the predecessor lemma.",
                    "campaign_id": campaign_id,
                },
                actor="research-author",
            )
            landmark = lifecycle.add_research(
                {
                    "claim": "The load-bearing theorem follows.",
                    "content": "Proof using the predecessor lemma.",
                    "campaign_id": campaign_id,
                },
                actor="research-author",
            )
            unrelated = lifecycle.add_research(
                {
                    "claim": "An unrelated theorem happens to share the Campaign.",
                    "content": "This result is not on the selected Fact route.",
                    "campaign_id": campaign_id,
                },
                actor="research-author",
            )
            alternative_predecessor = lifecycle.add_research(
                {
                    "claim": "A prerequisite found by the Fact packager holds.",
                    "content": (
                        "This exact prerequisite was not a Main landmark and "
                        "was not named by the supervisor recommendation."
                    ),
                    "campaign_id": campaign_id,
                },
                actor="research-author",
            )
            with store.v5_mutation_lock(command="fact-packager-fixture"):
                target_id = store.campaigns().target_add(
                    campaign_id,
                    {
                        "role": "research_goal",
                        "subject_kind": "research",
                        "subject_id": landmark["research_id"],
                        "label": "Certify the load-bearing route",
                    },
                    actor="main",
                    fact_exists=lambda _fact_id: False,
                    research_exists=lambda item: item == landmark["research_id"],
                )
                store.campaigns().activate(campaign_id, actor="main")
            lifecycle._replace_campaign_frontier_working_state(
                campaign_id,
                targets={
                    target_id: {
                        "recovery_root_research_id": landmark["research_id"],
                        "active_head_research_ids": [landmark["research_id"]],
                        "historical_landmark_research_ids": [
                            predecessor["research_id"]
                        ],
                        "historical_landmark_reasons": {
                            predecessor["research_id"]: (
                                "This is the oldest load-bearing certified-route entry."
                            )
                        },
                        "head_contexts": [],
                        "recent_attained_research_ids": [],
                    }
                },
            )
            manager = lifecycle.fact_alpha()
            main_mark = manager.mark(
                landmark["research_id"],
                rationale=(
                    "Main identifies this active Research head as a sparse "
                    "load-bearing Fact route entry."
                ),
                campaign_id=campaign_id,
                target_id=target_id,
                actor="main",
            )
            existing_mark_plan = manager.plan_packaging(
                [main_mark["mark_id"]],
                planned_by="fact-packager",
            )
            self.assertEqual(
                existing_mark_plan["selection_mode"], "existing_marks"
            )
            self.assertEqual(
                existing_mark_plan["route_anchor_research_ids"], []
            )
            self.assertEqual(
                manager.plan(existing_mark_plan["plan_id"])["plan_id"],
                existing_mark_plan["plan_id"],
            )
            cli_output = StringIO()
            with redirect_stdout(cli_output):
                mgraph_main(
                    [
                        "--root",
                        str(store.root),
                        "--role",
                        "fact-packager",
                        "plan-fact-packaging",
                        "--mark-id",
                        main_mark["mark_id"],
                    ]
                )
            self.assertEqual(
                json.loads(cli_output.getvalue())["plan_id"],
                existing_mark_plan["plan_id"],
            )
            before = manager.frontier(campaign_id=campaign_id)
            self.assertEqual(before["landmark_route_count"], 1)
            self.assertEqual(
                before["landmark_routes"][0]["route_state"],
                "needs_packager_route",
            )

            def plan_route() -> dict[str, object]:
                return manager.plan_packaging(
                    research_ids=[
                        predecessor["research_id"],
                        landmark["research_id"],
                    ],
                    campaign_id=campaign_id,
                    target_id=target_id,
                    planned_by="fact-packager",
                )

            with ThreadPoolExecutor(max_workers=2) as executor:
                plans = list(executor.map(lambda _index: plan_route(), range(2)))
            self.assertEqual(plans[0]["plan_id"], plans[1]["plan_id"])
            self.assertEqual(len(list(manager.plans_dir.glob("*.json"))), 2)
            self.assertEqual(len(list(manager.marks_dir.glob("*.json"))), 2)
            plan = plans[0]
            self.assertEqual(plan["planned_by"], "fact-packager")
            self.assertEqual(len(plan["selection"]), 2)
            self.assertEqual(
                {mark["actor"] for mark in manager._marks().values()},
                {"main", "fact-packager"},
            )
            state = lifecycle._read_campaign_frontier_working_state(
                campaign_id
            )
            self.assertEqual(
                state["targets"][target_id][
                    "historical_landmark_research_ids"
                ],
                [predecessor["research_id"]],
            )
            with self.assertRaisesRegex(
                ValueError, "lacks an exact Main-owned"
            ):
                manager.plan_packaging(
                    research_ids=[unrelated["research_id"]],
                    campaign_id=campaign_id,
                    target_id=target_id,
                    planned_by="fact-packager",
                )

            coverage = [
                {
                    "production_round_id": "round-20260830T000000Z-00000008",
                    "source_component_id": None,
                    "scope": "proof_logic",
                    "state": "completed",
                    "result_research_ids": [],
                    "pending_round_ids": [],
                }
            ]

            def ready_projection(
                research: dict[str, object], _coverage: object
            ) -> dict[str, object]:
                return {
                    "state": "ready",
                    "statement_interface": self._interface(research),
                    "source_bindings": [],
                    "source_count": 1,
                    "rationales": ["One coherent Research surface."],
                    "diagnostic_sha256": "d" * 64,
                }

            with patch.object(
                lifecycle,
                "_candidate_supervision_scope_coverage",
                return_value=coverage,
            ), patch.object(
                manager,
                "_supervised_interface_projection",
                side_effect=ready_projection,
            ):
                alternative_plan = manager.plan_packaging(
                    research_ids=[
                        alternative_predecessor["research_id"],
                        landmark["research_id"],
                    ],
                    campaign_id=campaign_id,
                    target_id=target_id,
                    planned_by="fact-packager",
                )
                landmark_interface = self._interface(landmark)
                landmark_interface[
                    "certified_predecessor_research_ids"
                ] = [alternative_predecessor["research_id"]]
                alternative_package = manager.seal_package(
                    {
                        "schema_version": 1,
                        "plan_id": alternative_plan["plan_id"],
                        "packager": "fact-packager",
                        "components": [
                            {
                                "component_key": "packager-alternative-route",
                                "entries": [
                                    {
                                        "research_id": alternative_predecessor[
                                            "research_id"
                                        ],
                                        "statement_interface": self._interface(
                                            alternative_predecessor
                                        ),
                                    },
                                    {
                                        "research_id": landmark["research_id"],
                                        "statement_interface": landmark_interface,
                                    },
                                ],
                            }
                        ],
                        "blocked_entries": [],
                    }
                )
            self.assertEqual(
                alternative_package["components"][0]["entries"][1][
                    "statement_interface"
                ]["certified_predecessor_research_ids"],
                [alternative_predecessor["research_id"]],
            )

            with patch.object(
                lifecycle,
                "_candidate_supervision_scope_coverage",
                return_value=coverage,
            ), patch.object(
                manager,
                "_supervised_interface_projection",
                side_effect=ready_projection,
            ):
                unrelated_plan = manager.plan_packaging(
                    research_ids=[
                        unrelated["research_id"],
                        landmark["research_id"],
                    ],
                    campaign_id=campaign_id,
                    target_id=target_id,
                    planned_by="fact-packager",
                )
                with self.assertRaisesRegex(
                    ValueError, "lacks a frozen Main route anchor"
                ):
                    manager.seal_package(
                        {
                            "schema_version": 1,
                            "plan_id": unrelated_plan["plan_id"],
                            "packager": "fact-packager",
                            "components": [
                                {
                                    "component_key": "anchored-component",
                                    "entries": [
                                        {
                                            "research_id": landmark[
                                                "research_id"
                                            ],
                                            "statement_interface": self._interface(
                                                landmark
                                            ),
                                        }
                                    ],
                                },
                                {
                                    "component_key": "unrelated-component",
                                    "entries": [
                                        {
                                            "research_id": unrelated[
                                                "research_id"
                                            ],
                                            "statement_interface": self._interface(
                                                unrelated
                                            ),
                                        }
                                    ],
                                },
                            ],
                            "blocked_entries": [],
                        }
                    )
                with self.assertRaisesRegex(
                    ValueError, "outside its frozen Main-anchored"
                ):
                    manager.seal_package(
                        {
                            "schema_version": 1,
                            "plan_id": unrelated_plan["plan_id"],
                            "packager": "fact-packager",
                            "components": [
                                {
                                    "component_key": "disconnected-component",
                                    "entries": [
                                        {
                                            "research_id": landmark[
                                                "research_id"
                                            ],
                                            "statement_interface": self._interface(
                                                landmark
                                            ),
                                        },
                                        {
                                            "research_id": unrelated[
                                                "research_id"
                                            ],
                                            "statement_interface": self._interface(
                                                unrelated
                                            ),
                                        },
                                    ],
                                }
                            ],
                            "blocked_entries": [],
                        }
                    )

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

    def test_fact_frontier_limit_bounds_entries_without_eager_batch_selection(self) -> None:
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
            self.assertEqual(frontier["route_entry_count"], 5)
            self.assertNotIn("batch_opportunities", frontier)
            self.assertTrue(
                all(
                    entry["state"] == "needs_packager_route"
                    for entry in frontier["entries"]
                )
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

    def test_supervised_interface_proposes_package_and_preserves_evidence_layer(
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
            original_research_record = lifecycle._research_record

            def source_scoped_research_record(
                research_id: str, *args: object, **kwargs: object
            ) -> dict[str, object]:
                record = original_research_record(
                    research_id, *args, **kwargs
                )
                if research_id != supervisor["research_id"]:
                    return record
                projected = json.loads(json.dumps(record))
                projected["metadata"]["research_supervision"] = {
                    "supervisor_scope": "source_scope"
                }
                return projected

            source_coverage = [
                {**coverage[0], "scope": "source_scope"}
            ]
            with patch.object(
                lifecycle,
                "_research_record",
                side_effect=source_scoped_research_record,
            ):
                source_projection = manager._supervised_interface_projection(
                    research,
                    source_coverage,
                )
            self.assertEqual(
                source_projection["state"], "missing_or_legacy"
            )

            def scoped_research_record(
                research_id: str, *args: object, **kwargs: object
            ) -> dict[str, object]:
                record = original_research_record(
                    research_id, *args, **kwargs
                )
                if research_id != supervisor["research_id"]:
                    return record
                projected = json.loads(json.dumps(record))
                projected["metadata"]["research_supervision"] = {
                    "supervisor_scope": "proof_logic"
                }
                return projected

            with patch.object(
                lifecycle,
                "_candidate_supervision_scope_coverage",
                return_value=coverage,
            ), patch.object(
                lifecycle,
                "_research_record",
                side_effect=scoped_research_record,
            ):
                plan = manager.plan_packaging([mark["mark_id"]])

            self.assertEqual(
                plan["mechanical_package_state"],
                "mechanical_proposal_ready",
            )
            self.assertIsNone(plan["mechanical_package_id"])
            proposal = plan["mechanical_package_proposal"]
            self.assertEqual(
                plan["mechanical_package_proposal_sha256"],
                sha256_json(proposal),
            )
            package = manager.seal_package(proposal)
            self.assertEqual(
                package["packager"],
                "fact-packager",
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
            self.assertEqual(
                plan["next_action"],
                "fact-package-seal-or-research-cow-split",
            )
            self.assertEqual(
                frontier["entries"][0]["state"], "needs_packager_route"
            )
            self.assertEqual(
                frontier["entries"][0]["interface_preparation"]["state"],
                "needs_split",
            )
            self.assertIn(
                "supervisor_recommends_statement_split",
                frontier["entries"][0]["warnings"],
            )
            with patch.object(
                lifecycle,
                "_candidate_supervision_scope_coverage",
                return_value=coverage,
            ), patch.object(
                manager,
                "_supervised_interface_projection",
                return_value=split_projection,
            ):
                manual_package = manager.seal_package(
                    {
                        "schema_version": 1,
                        "plan_id": plan["plan_id"],
                        "packager": "fact-packager-agent",
                        "components": [
                            {
                                "component_key": "packager-whole-node-proposal",
                                "entries": [
                                    {
                                        "research_id": research["research_id"],
                                        "statement_interface": self._interface(
                                            research
                                        ),
                                    }
                                ],
                            }
                        ],
                        "blocked_entries": [],
                    }
                )
            self.assertEqual(
                manual_package["packager"], "fact-packager-agent"
            )

    def test_packager_may_propose_alternative_to_supervised_interface(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            research = lifecycle.add_research(
                {
                    "claim": "A load-bearing theorem has one supervised surface.",
                    "content": "The proof establishes exactly that theorem.",
                },
                actor="research-author",
            )
            manager = lifecycle.fact_alpha()
            mark = manager.mark(
                research["research_id"],
                rationale="The theorem is load-bearing.",
            )
            coverage = [
                {
                    "production_round_id": "round-20260830T000000Z-00000004",
                    "source_component_id": None,
                    "scope": "proof_logic",
                    "state": "completed",
                    "result_research_ids": [],
                    "pending_round_ids": [],
                }
            ]
            exact_interface = self._interface(research)
            ready_projection = {
                "state": "ready",
                "statement_interface": exact_interface,
                "source_bindings": [],
                "source_count": 1,
                "rationales": ["The node is one coherent statement."],
                "diagnostic_sha256": "c" * 64,
            }
            with patch.object(
                lifecycle,
                "_candidate_supervision_scope_coverage",
                return_value=coverage,
            ), patch.object(
                manager,
                "_supervised_interface_projection",
                return_value=ready_projection,
            ):
                plan = manager.plan_packaging([mark["mark_id"]])
            self.assertEqual(
                plan["mechanical_package_state"],
                "mechanical_proposal_ready",
            )
            self.assertIsNone(plan["mechanical_package_id"])
            altered_interface = json.loads(json.dumps(exact_interface))
            altered_interface["limitations"] = [
                "The packager tried to replace the supervisor-owned boundary."
            ]
            with patch.object(
                lifecycle,
                "_candidate_supervision_scope_coverage",
                return_value=coverage,
            ), patch.object(
                manager,
                "_supervised_interface_projection",
                return_value=ready_projection,
            ):
                package = manager.seal_package(
                    {
                        "schema_version": 1,
                        "plan_id": plan["plan_id"],
                        "packager": "fact-packager-agent",
                        "components": [
                            {
                                "component_key": "altered-interface",
                                "entries": [
                                    {
                                        "research_id": research["research_id"],
                                        "statement_interface": altered_interface,
                                    }
                                ],
                            }
                        ],
                        "blocked_entries": [],
                    }
                )
            self.assertEqual(
                package["components"][0]["entries"][0][
                    "statement_interface"
                ]["limitations"],
                altered_interface["limitations"],
            )

    def test_main_mark_exposes_complete_committed_split_to_packager(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            records = [
                lifecycle.add_research(
                    {
                        "claim": f"Research surface {index}.",
                        "content": f"Exact content for surface {index}.",
                    },
                    actor="research-author",
                )
                for index in range(7)
            ]
            source, repair, owner, pending_repair, *members = records
            manager = lifecycle.fact_alpha()
            mark = manager.mark(
                source["research_id"],
                rationale="This mixed source is a sparse Fact route entry.",
            )
            bases = {
                item["research_id"]: json.loads(json.dumps(item))
                for item in records
            }
            batch_id = "research-split-" + "d" * 64
            bases[owner["research_id"]].setdefault("metadata", {})[
                "research_split_owner"
            ] = {"batch_id": batch_id}
            member_ids = [item["research_id"] for item in members]
            repair_children = {
                source["research_id"]: (repair["research_id"],),
                repair["research_id"]: tuple(member_ids),
            }
            projection = {
                "route_children": repair_children,
                "details": {
                    repair["research_id"]: {
                        "state": "committed_split_members",
                        "split_owner_research_id": owner["research_id"],
                        "split_member_research_ids": member_ids,
                    }
                },
            }

            def route_projection(*, inspection: object) -> tuple[object, ...]:
                inspection.frontier_cow_route_projection = projection
                inspection.frontier_cow_repair_children = repair_children
                return bases, {}, {}, repair_children

            with patch.object(
                manager, "_route_projection", side_effect=route_projection
            ):
                frontier = manager.frontier()
            self.assertEqual(len(frontier["entries"]), 1)
            entry = frontier["entries"][0]
            self.assertEqual(entry["state"], "needs_packager_route")
            self.assertEqual(entry["next_action"], "fact-packager-route")
            self.assertEqual(entry["exact_split_batch_count"], 1)
            self.assertEqual(
                entry["exact_split_batches"][0]["member_research_ids"],
                sorted(member_ids),
            )
            self.assertEqual(
                entry["interface_preparation"]["state"],
                "deferred_to_split_members",
            )
            self.assertNotIn("research_cow_route_is_ambiguous", entry["blockers"])
            self.assertEqual(
                frontier["entries"][0]["rationale"], mark["rationale"]
            )
            mixed_children = {
                source["research_id"]: (
                    pending_repair["research_id"],
                    repair["research_id"],
                ),
                repair["research_id"]: tuple(member_ids),
            }
            mixed_projection = {
                **projection,
                "route_children": mixed_children,
            }

            def mixed_route_projection(
                *, inspection: object
            ) -> tuple[object, ...]:
                inspection.frontier_cow_route_projection = mixed_projection
                inspection.frontier_cow_repair_children = mixed_children
                return bases, {}, {}, mixed_children

            with patch.object(
                manager,
                "_route_projection",
                side_effect=mixed_route_projection,
            ):
                mixed_frontier = manager.frontier()
            mixed_entry = mixed_frontier["entries"][0]
            self.assertEqual(
                mixed_entry["state"], "needs_packager_route"
            )
            self.assertEqual(
                mixed_entry["next_action"], "fact-packager-route"
            )
            self.assertNotIn(
                "research_cow_route_is_ambiguous", mixed_entry["blockers"]
            )
            self.assertEqual(
                set(mixed_entry["candidate_terminal_research_ids"]),
                {pending_repair["research_id"], *member_ids},
            )
            manager.mark(
                owner["research_id"],
                rationale=(
                    "The atomic split owner is the ingested Research result."
                ),
            )
            owner_children = {
                **repair_children,
                owner["research_id"]: tuple(member_ids),
            }
            owner_projection = {
                **projection,
                "route_children": owner_children,
            }

            def owner_route_projection(
                *, inspection: object
            ) -> tuple[object, ...]:
                inspection.frontier_cow_route_projection = owner_projection
                inspection.frontier_cow_repair_children = owner_children
                return bases, {}, {}, owner_children

            with patch.object(
                manager,
                "_route_projection",
                side_effect=owner_route_projection,
            ):
                owner_frontier = manager.frontier()
            self.assertEqual(len(owner_frontier["entries"]), 1)
            self.assertEqual(owner_frontier["entries"][0]["mark_count"], 2)
            self.assertEqual(
                owner_frontier["entries"][0]["exact_split_batches"][0][
                    "member_research_ids"
                ],
                sorted(member_ids),
            )

    def test_distinct_ambiguous_cow_marks_remain_distinct_packager_routes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            records = [
                lifecycle.add_research(
                    {
                        "claim": f"Independent COW route node {index}.",
                        "content": f"Exact route content {index}.",
                    },
                    actor="research-author",
                )
                for index in range(6)
            ]
            first_root, first_left, first_right, second_root, second_left, second_right = (
                records
            )
            manager = lifecycle.fact_alpha()
            first_mark = manager.mark(
                first_root["research_id"],
                rationale="First independent Fact attention route.",
            )
            second_mark = manager.mark(
                second_root["research_id"],
                rationale="Second independent Fact attention route.",
            )
            bases = {
                item["research_id"]: json.loads(json.dumps(item))
                for item in records
            }
            repair_children = {
                first_root["research_id"]: (
                    first_left["research_id"],
                    first_right["research_id"],
                ),
                second_root["research_id"]: (
                    second_left["research_id"],
                    second_right["research_id"],
                ),
            }
            projection = {
                "route_children": repair_children,
                "details": {},
            }

            def route_projection(*, inspection: object) -> tuple[object, ...]:
                inspection.frontier_cow_route_projection = projection
                inspection.frontier_cow_repair_children = repair_children
                return bases, {}, {}, repair_children

            with patch.object(
                manager, "_route_projection", side_effect=route_projection
            ):
                frontier = manager.frontier()
                plan = manager.plan_packaging(
                    [first_mark["mark_id"], second_mark["mark_id"]]
                )

            self.assertEqual(len(frontier["entries"]), 2)
            terminal_sets = {
                frozenset(entry["candidate_terminal_research_ids"])
                for entry in frontier["entries"]
            }
            self.assertEqual(
                terminal_sets,
                {
                    frozenset(
                        {
                            first_left["research_id"],
                            first_right["research_id"],
                        }
                    ),
                    frozenset(
                        {
                            second_left["research_id"],
                            second_right["research_id"],
                        }
                    ),
                },
            )
            self.assertTrue(
                all(
                    entry["state"] == "needs_packager_route"
                    and entry["next_action"] == "fact-packager-route"
                    for entry in frontier["entries"]
                )
            )
            self.assertEqual(len(plan["selection"]), 2)
            self.assertEqual(
                {
                    item["marked_research_id"]
                    for item in plan["selection"]
                },
                {first_root["research_id"], second_root["research_id"]},
            )

    def test_candidate_cow_preview_reports_depth_cut(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            manager = store.v5_lifecycle().fact_alpha()
            node_ids = [f"{index:012x}" for index in range(40)]
            branch_ids = [f"{100 + index:012x}" for index in range(20)]
            bases = {
                research_id: {
                    "research_id": research_id,
                    "record_sha256": "a" * 64,
                    "kind": "repair",
                    "status": "open",
                    "relation": "repairs",
                    "claim": f"Exact terminal claim {research_id}.",
                    "rationale": "Bounded packager route evidence.",
                }
                for research_id in [*node_ids, *branch_ids]
            }
            repair_children = {
                node_ids[index]: (node_ids[index + 1],)
                for index in range(len(node_ids) - 1)
            }
            result = manager._candidate_cow_route_projection(
                node_ids[0],
                repair_children=repair_children,
                bases=bases,
            )
            self.assertTrue(result["candidate_cow_paths_truncated"])
            self.assertEqual(
                result["candidate_cow_path_details"][0]["endpoint_state"],
                "depth_cut",
            )
            self.assertEqual(
                result["candidate_terminal_research_ids"], [node_ids[-1]]
            )
            self.assertEqual(
                result["candidate_terminal_summaries"][0]["research_id"],
                node_ids[-1],
            )
            self.assertEqual(
                result["candidate_terminal_summaries"][0][
                    "research_record_sha256"
                ],
                "a" * 64,
            )

            wide_children = {
                **{
                    node_ids[index]: (node_ids[index + 1],)
                    for index in range(31)
                },
                node_ids[31]: tuple(branch_ids),
            }
            wide_result = manager._candidate_cow_route_projection(
                node_ids[0],
                repair_children=wide_children,
                bases=bases,
            )
            self.assertLessEqual(
                wide_result["candidate_cow_paths_shown_count"], 8
            )
            self.assertEqual(
                len(wide_result["candidate_cow_path_details"]), 8
            )
            self.assertTrue(wide_result["candidate_cow_paths_truncated"])
            self.assertEqual(wide_result["candidate_terminal_count"], 20)
            self.assertEqual(
                len(wide_result["candidate_terminal_bindings"]), 20
            )
            self.assertEqual(
                wide_result["candidate_terminal_ids_sha256"],
                sha256_json(sorted(branch_ids)),
            )
            self.assertEqual(
                len(wide_result["candidate_terminal_summaries"]), 8
            )

    def test_uncertified_landmark_cannot_be_starved_by_bounded_window(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            manager = lifecycle.fact_alpha()
            campaign_id = "campaign-" + "a" * 12
            research_ids = [f"{index:012x}" for index in range(257)]
            target_ids = [
                f"camtarget-{index:016x}" for index in range(257)
            ]
            bases = {
                research_id: {
                    "research_id": research_id,
                    "claim": f"Landmark theorem {index}",
                    "kind": "direction",
                }
                for index, research_id in enumerate(research_ids)
            }
            campaign_state = {
                "targets": {
                    target_id: {
                        "historical_landmark_research_ids": [research_id],
                        "historical_landmark_reasons": {
                            research_id: "Exact durable route."
                        },
                    }
                    for target_id, research_id in zip(
                        target_ids, research_ids, strict=True
                    )
                }
            }
            certified_ids = research_ids[:256]
            grant_projection = {
                "active_by_research": {
                    research_id: {
                        "grant_id": "fact-grant-" + "b" * 64
                    }
                    for research_id in certified_ids
                },
                "stale_by_research": {},
                "grants": {
                    research_id: {} for research_id in certified_ids
                },
                "certified_heads": certified_ids,
            }

            def route_projection(*, inspection: object) -> tuple[object, ...]:
                inspection.frontier_cow_route_projection = {
                    "route_children": {},
                    "details": {},
                }
                inspection.frontier_cow_repair_children = {}
                return bases, {}, {}, {}

            with patch.object(
                manager, "_route_projection", side_effect=route_projection
            ), patch.object(
                manager,
                "_grant_projection",
                return_value=grant_projection,
            ), patch.object(
                lifecycle,
                "_read_campaign_frontier_working_state",
                return_value=campaign_state,
            ), patch.object(
                manager,
                "_legacy_root_bootstrap_advisory",
                return_value=None,
            ):
                frontier = manager.frontier(
                    limit=1, campaign_id=campaign_id
                )
                selected = manager.frontier(
                    limit=1,
                    campaign_id=campaign_id,
                    target_id=target_ids[-1],
                )

            self.assertEqual(frontier["landmark_route_count"], 257)
            self.assertEqual(
                frontier["landmark_routes"][0][
                    "landmark_research_id"
                ],
                research_ids[-1],
            )
            self.assertEqual(
                frontier["landmark_routes"][0]["route_state"],
                "needs_packager_route",
            )
            self.assertEqual(selected["landmark_route_count"], 1)
            self.assertEqual(
                selected["landmark_routes"][0]["target_id"],
                target_ids[-1],
            )
            self.assertEqual(
                frontier["landmark_route_identities_sha256"],
                sha256_json(
                    [
                        {
                            "campaign_id": item["campaign_id"],
                            "target_id": item["target_id"],
                            "landmark_research_id": item[
                                "landmark_research_id"
                            ],
                            "current_research_id": item[
                                "current_research_id"
                            ],
                        }
                        for item in frontier["landmark_routes"]
                    ]
                    + [
                        {
                            "campaign_id": campaign_id,
                            "target_id": target_id,
                            "landmark_research_id": research_id,
                            "current_research_id": research_id,
                        }
                        for target_id, research_id in zip(
                            target_ids[:-1],
                            research_ids[:-1],
                            strict=True,
                        )
                    ]
                ),
            )


if __name__ == "__main__":
    unittest.main()

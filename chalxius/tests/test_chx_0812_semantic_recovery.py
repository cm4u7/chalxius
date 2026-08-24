from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mathgraph.contracts import sha256_json
from mathgraph.store import MathGraphStore
from mathgraph.v5_lifecycle import RoundInspectionContext, V5LifecycleManager


ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = "campaign-123456789abc"


def _record(
    research_id: str,
    *,
    created_at: str,
    kind: str = "direction",
    relation: str = "investigates",
    related: list[str] | None = None,
    source: str = "",
    metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "research_id": research_id,
        "created_at": created_at,
        "kind": kind,
        "status": "open",
        "relation": relation,
        "related_research_ids": list(related or []),
        "source": source,
        "dependencies": [],
        "metadata": {"campaign_id": CAMPAIGN, **(metadata or {})},
    }


def _product(
    research_id: str,
    parent_id: str,
    *,
    created_at: str,
) -> dict[str, object]:
    return _record(
        research_id,
        created_at=created_at,
        kind="proof_attempt",
        relation="responds_to",
        related=[parent_id],
        metadata={
            "assignment_provenance": {
                "adverse_assignment": False,
                "work_mode": "prove",
            },
            "obligation_dispositions": [
                {"obligation_id": "O", "status": "complete"}
            ],
            "route_invalidations": [],
            "worker_outcome": "proof",
        },
    )


def _challenge(
    research_id: str,
    product_id: str,
    *,
    created_at: str,
) -> dict[str, object]:
    return _record(
        research_id,
        created_at=created_at,
        kind="challenge",
        relation="responds_to",
        metadata={"route_invalidations": [product_id]},
    )


def _repair(
    research_id: str,
    product_id: str,
    trigger_id: str,
    *,
    created_at: str,
) -> dict[str, object]:
    obligations = [
        {
            "obligation_id": "repair-O",
            "description": "Publish the exact bounded COW successor.",
            "required_artifact_roles": ["repair_certificate"],
            "evidence_types": ["bounded_argument"],
            "not_applicable_allowed": False,
        }
    ]
    stop_conditions = ["Do not broaden the selected mathematical scope."]
    spec = {
        "schema_version": 1,
        "claim": "Repair the exact defect without changing the objective.",
        "content": "Preserve the surviving result and repair only the trigger.",
        "rationale": "The trigger identifies one bounded copy-on-write defect.",
        "work_mode": "prove",
        "obligations": obligations,
        "stop_conditions": stop_conditions,
    }
    return _record(
        research_id,
        created_at=created_at,
        kind="repair",
        relation="repairs",
        related=sorted([product_id, trigger_id]),
        source=f"research:{product_id}",
        metadata={
            "repair_of_research_id": product_id,
            "trigger_research_id": trigger_id,
            "repair_spec": spec,
            "repair_spec_sha256": sha256_json(spec),
            "obligations": obligations,
            "stop_conditions": stop_conditions,
        },
    )


class SemanticRecovery0812Tests(unittest.TestCase):
    @staticmethod
    def _two_hop_chain() -> tuple[dict[str, dict[str, object]], list[str]]:
        ids = [f"{index:012x}" for index in range(1, 9)]
        root, first_product, first_trigger, first_repair = ids[:4]
        second_product, second_trigger, second_repair, terminal_product = ids[4:]
        records = [
            _record(root, created_at="2026-01-01T00:00:01+00:00"),
            _product(
                first_product,
                root,
                created_at="2026-01-01T00:00:02+00:00",
            ),
            _challenge(
                first_trigger,
                first_product,
                created_at="2026-01-01T00:00:03+00:00",
            ),
            _repair(
                first_repair,
                first_product,
                first_trigger,
                created_at="2026-01-01T00:00:04+00:00",
            ),
            _product(
                second_product,
                first_repair,
                created_at="2026-01-01T00:00:05+00:00",
            ),
            _challenge(
                second_trigger,
                second_product,
                created_at="2026-01-01T00:00:06+00:00",
            ),
            _repair(
                second_repair,
                second_product,
                second_trigger,
                created_at="2026-01-01T00:00:07+00:00",
            ),
            _product(
                terminal_product,
                second_repair,
                created_at="2026-01-01T00:00:08+00:00",
            ),
        ]
        return {item["research_id"]: item for item in records}, ids

    @staticmethod
    def _two_hop_staleness(ids: list[str]) -> dict[str, list[str]]:
        return {ids[1]: [ids[2]], ids[4]: [ids[5]]}

    def test_exact_multihop_cow_completion_projects_to_original_workgroup(self) -> None:
        bases, ids = self._two_hop_chain()
        root, first_product, first_trigger, _, second_product, second_trigger, terminal, _ = ids
        terminals = V5LifecycleManager._frontier_cow_terminal_members(
            seed_members=[root],
            bases=bases,
            route_staleness=self._two_hop_staleness(ids),
        )
        self.assertEqual(terminals, {root: terminal})

        with tempfile.TemporaryDirectory() as temporary:
            store = MathGraphStore(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            with patch.object(
                lifecycle,
                "_validated_completed_research_obligation_statuses",
                return_value={terminal: "completed_production"},
            ):
                projected = lifecycle._frontier_group_completion(
                    workgroups={"work": [root]},
                    work_keys={"work"},
                    bases=bases,
                    dispositions={},
                    route_staleness={
                        first_product: [first_trigger],
                        second_product: [second_trigger],
                    },
                    _inspection_context=RoundInspectionContext(),
                )["work"]
        self.assertEqual(
            projected,
            ("completed_production", root, 1, sha256_json([root])),
        )

    def test_terminal_product_invalidation_and_incomplete_obligations_reopen(self) -> None:
        bases, ids = self._two_hop_chain()
        terminal_product = bases[ids[-1]]
        self.assertTrue(
            V5LifecycleManager._frontier_completion_product_is_safe(
                product=terminal_product,
                dispositions={},
                route_staleness={},
            )
        )
        self.assertFalse(
            V5LifecycleManager._frontier_completion_product_is_safe(
                product=terminal_product,
                dispositions={},
                route_staleness={ids[-1]: ["f" * 12]},
            )
        )
        incomplete = copy.deepcopy(terminal_product)
        incomplete["metadata"]["obligation_dispositions"][0]["status"] = "pending"
        self.assertFalse(
            V5LifecycleManager._frontier_completion_product_is_safe(
                product=incomplete,
                dispositions={},
                route_staleness={},
            )
        )

    def test_malformed_or_ambiguous_repair_lineage_never_closes_predecessor(self) -> None:
        bases, ids = self._two_hop_chain()
        root, product, trigger, repair = ids[:4]
        negative_variants: list[dict[str, dict[str, object]]] = []
        for mutate in ("extends", "wrong_product", "unrelated_trigger", "campaign"):
            variant = copy.deepcopy(bases)
            if mutate == "extends":
                variant[repair]["relation"] = "extends"
            elif mutate == "wrong_product":
                variant[repair]["metadata"]["repair_of_research_id"] = ids[-1]
            elif mutate == "unrelated_trigger":
                variant[trigger]["metadata"]["route_invalidations"] = [ids[-1]]
            else:
                variant[repair]["metadata"]["campaign_id"] = "campaign-ffffffffffff"
            negative_variants.append(variant)
        for variant in negative_variants:
            with self.subTest():
                self.assertEqual(
                    V5LifecycleManager._frontier_cow_terminal_members(
                        seed_members=[root],
                        bases=variant,
                        route_staleness=self._two_hop_staleness(ids),
                    )[root],
                    root,
                )

        ambiguous = copy.deepcopy(bases)
        other_repair = "b" * 12
        ambiguous[other_repair] = _repair(
            other_repair,
            product,
            trigger,
            created_at="2026-01-01T00:00:04.5+00:00",
        )
        self.assertIsNone(
            V5LifecycleManager._frontier_cow_terminal_members(
                seed_members=[root],
                bases=ambiguous,
                route_staleness=self._two_hop_staleness(ids),
            )[root]
        )

    def test_repair_requires_exact_active_invalidator_coverage(self) -> None:
        bases, ids = self._two_hop_chain()
        root, product, trigger = ids[:3]
        other_trigger = "a" * 12
        bases[other_trigger] = _challenge(
            other_trigger,
            product,
            created_at="2026-01-01T00:00:03.5+00:00",
        )
        self.assertEqual(
            V5LifecycleManager._frontier_cow_terminal_members(
                seed_members=[root],
                bases=bases,
                route_staleness={
                    **self._two_hop_staleness(ids),
                    product: sorted([trigger, other_trigger]),
                },
            )[root],
            root,
        )

    def test_repair_requires_hash_bound_objective_projection(self) -> None:
        bases, ids = self._two_hop_chain()
        root, _, _, repair = ids[:4]
        variants: list[dict[str, dict[str, object]]] = []

        missing_spec = copy.deepcopy(bases)
        missing_spec[repair]["metadata"].pop("repair_spec")
        variants.append(missing_spec)

        bad_hash = copy.deepcopy(bases)
        bad_hash[repair]["metadata"]["repair_spec_sha256"] = "0" * 64
        variants.append(bad_hash)

        obligation_drift = copy.deepcopy(bases)
        obligation_drift[repair]["metadata"]["obligations"] = []
        variants.append(obligation_drift)

        for variant in variants:
            with self.subTest():
                self.assertEqual(
                    V5LifecycleManager._frontier_cow_terminal_members(
                        seed_members=[root],
                        bases=variant,
                        route_staleness=self._two_hop_staleness(ids),
                    )[root],
                    root,
                )

    def test_distinct_nonaborted_products_are_ambiguous_but_exact_retry_is_not(self) -> None:
        root, first_product, second_product, supervisor_id = [
            f"{index:012x}" for index in range(31, 35)
        ]
        products = {
            "round-a": _product(
                first_product,
                root,
                created_at="2026-01-01T00:00:02+00:00",
            ),
            "round-b": _product(
                second_product,
                root,
                created_at="2026-01-01T00:00:03+00:00",
            ),
        }
        supervisor = _product(
            supervisor_id,
            "f" * 12,
            created_at="2026-01-01T00:00:04+00:00",
        )
        bases = {
            root: _record(root, created_at="2026-01-01T00:00:01+00:00"),
            first_product: products["round-a"],
            second_product: products["round-b"],
            supervisor_id: supervisor,
        }
        context = RoundInspectionContext(
            completion_obligation_rounds={
                root: [
                    ("round-a", "production"),
                    ("round-b", "production"),
                ]
            },
            supervision_round_ids_by_production_round={},
        )

        def round_manifest(round_id: str, **_kwargs):
            return Path(round_id), {
                "round_id": round_id,
                "assignments": [
                    {"research_id": root, "assignment_role": "primary"}
                ],
            }

        def research_product(*, manifest, **_kwargs):
            return products[manifest["round_id"]], {}

        with tempfile.TemporaryDirectory() as temporary:
            store = MathGraphStore(Path(temporary) / "project")
            store.rounds_dir.mkdir(parents=True)
            lifecycle = store.v5_lifecycle()
            patches = (
                patch.object(lifecycle, "_round_manifest", side_effect=round_manifest),
                patch.object(
                    lifecycle,
                    "_research_product_for_assignment",
                    side_effect=research_product,
                ),
                patch.object(
                    lifecycle,
                    "_required_supervision_results_for_candidate",
                    return_value={supervisor_id},
                ),
                patch.object(
                    lifecycle,
                    "_inspection_research_record",
                    return_value=supervisor,
                ),
            )
            with patches[0], patches[1], patches[2], patches[3]:
                ambiguous = lifecycle._validated_completed_research_obligation_statuses(
                    {root},
                    _inspection_context=context,
                    _all_bases=bases,
                    _latest_dispositions={},
                    _route_staleness={},
                )
                products["round-b"] = products["round-a"]
                exact_retry = lifecycle._validated_completed_research_obligation_statuses(
                    {root},
                    _inspection_context=context,
                    _all_bases=bases,
                    _latest_dispositions={},
                    _route_staleness={},
                )
        self.assertEqual(ambiguous, {})
        self.assertEqual(exact_retry, {root: "completed_production"})

    def test_main_semantics_cover_slots_reconnect_and_scout_non_authority(self) -> None:
        required_by_path = {
            "SKILL.md": (
                "Main owns cross-round and copy-on-write search",
                "visible free slots",
                "at least two workers active",
                "Scouts may collect bounded evidence only",
                "Reconnecting...",
                "transport state, not worker or round state",
                "canonical return bytes",
                "no reconnect gate or liveness scheduler",
            ),
            "references/agent_protocol_v4.md": (
                "Main owns cross-round",
                "Scouts may collect bounded evidence",
                "visible free slots",
                "at least two workers active",
                "Reconnecting...",
                "transport state, not worker or round state",
                "canonical return bytes",
                "no reconnect",
                "liveness scheduler",
            ),
            "references/multi_agent_adapter.md": (
                "Main, not a scout, owns cross-round and copy-on-write search",
                "visible free slots",
                "at least two workers active",
                "Reconnecting...",
                "transport state, not worker or round",
                "canonical return bytes",
                "no reconnect gate",
                "liveness scheduler",
            ),
            "references/unified_architecture.md": (
                "Main owns this cross-round and copy-on-write search",
                "scouts may only return bounded evidence",
                "visible free slots",
                "at least two workers active",
                "Reconnecting...",
                "transport state, not worker or round state",
                "canonical return bytes",
                "no reconnect gate or liveness scheduler",
            ),
        }
        for path, markers in required_by_path.items():
            text = " ".join((ROOT / path).read_text(encoding="utf-8").split())
            for marker in markers:
                with self.subTest(path=path, marker=marker):
                    self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()

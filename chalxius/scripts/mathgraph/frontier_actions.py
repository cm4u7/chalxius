from __future__ import annotations

from typing import Any

from .contracts import sha256_bytes, sha256_json


class _ActionProjector:
    """Derive frontier actions from immutable Research and round bytes."""

    def __init__(
        self,
        lifecycle: Any,
        *,
        bases: dict[str, dict[str, Any]],
        dispositions: dict[str, dict[str, Any]],
        route_staleness: dict[str, list[str]],
        inspection: Any,
    ) -> None:
        self.lifecycle = lifecycle
        self.bases = bases
        self.dispositions = dispositions
        self.route_staleness = route_staleness
        self.inspection = inspection

    def action(
        self,
        next_action: str,
        reason: str,
        *,
        research_ids: list[str] | tuple[str, ...] = (),
        round_ids: list[str] | tuple[str, ...] = (),
        primary_research_id: str | None = None,
        primary_round_id: str | None = None,
        supervision_coverage: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        ordered_research = sorted(
            set(research_ids),
            key=lambda item: (
                self.bases.get(item, {}).get("created_at", ""),
                item,
            ),
        )
        ordered_rounds = sorted(set(round_ids))
        primary_research_id = primary_research_id or (
            ordered_research[0] if ordered_research else None
        )
        primary_round_id = primary_round_id or (
            ordered_rounds[0] if ordered_rounds else None
        )
        primary = self.bases.get(primary_research_id or "", {})
        claim = primary.get("claim", "")
        kind = primary.get("kind")
        claim = claim if isinstance(claim, str) else ""
        kind = kind if isinstance(kind, str) else None
        explicit_disposition = self.dispositions.get(
            primary_research_id or "", {}
        ).get("metadata", {}).get("attention_disposition")
        if explicit_disposition not in {
            "superseded",
            "equivalent_review_accepted",
        }:
            explicit_disposition = None
        if next_action == "production":
            next_attention = "production"
        elif next_action == "repair":
            next_attention = "repair"
        elif next_action == "supervision" or reason.startswith("supervision_"):
            next_attention = "supervision"
        elif next_action in {"await_return", "ingest_return"}:
            next_attention = (
                "supervision"
                if reason.startswith("supervision_")
                else "production"
            )
        elif next_action == "none":
            next_attention = "none"
        else:
            next_attention = "reconcile"
        disposition = (
            explicit_disposition
            if explicit_disposition is not None
            else "in_flight"
            if next_action in {"await_return", "ingest_return"}
            else "complete"
            if next_action == "none"
            else "active"
        )
        projected = {
            "next_action": next_action,
            "pending_reason": reason,
            "next_attention": next_attention,
            "disposition": disposition,
            "attention_basis_research_ids": ordered_research,
            "attention_basis_round_ids": ordered_rounds,
            "attention_reason": reason,
            "actionable_research_id": primary_research_id,
            "actionable_round_id": primary_round_id,
            "actionable_research_ids": ordered_research,
            "actionable_research_count": len(ordered_research),
            "actionable_research_ids_sha256": sha256_json(ordered_research),
            "actionable_round_ids": ordered_rounds,
            "actionable_round_count": len(ordered_rounds),
            "actionable_round_ids_sha256": sha256_json(ordered_rounds),
            "actionable_claim": claim,
            "actionable_claim_sha256": sha256_bytes(claim.encode("utf-8")),
            "actionable_kind": kind,
        }
        if supervision_coverage is not None:
            projected["supervision_coverage"] = supervision_coverage
            projected["supervision_coverage_count"] = len(
                supervision_coverage
            )
            projected["supervision_coverage_sha256"] = sha256_json(
                supervision_coverage
            )
        return projected

    @staticmethod
    def _supervision_coverage_route(
        coverage: list[dict[str, Any]],
    ) -> tuple[str, str] | None:
        """Map exact non-complete scope coverage to Main's next operation."""

        states = {
            item["state"]
            for item in coverage
            if item["state"] != "completed"
        }
        if not states:
            return None
        if "unsafe" in states:
            return (
                "main_reconciliation",
                "supervision_scope_coverage_unsafe",
            )
        if "conflicting" in states:
            return "main_reconciliation", "supervision_scope_conflicting"
        if "pending" in states:
            return "await_return", "supervision_scope_pending"
        return "supervision", "supervision_scope_missing"

    def explicit_attention_disposition(
        self,
        research_id: str,
    ) -> str | None:
        """Return Main's exact COW semantic disposition, when present."""

        value = self.dispositions.get(research_id, {}).get(
            "metadata", {}
        ).get("attention_disposition")
        return (
            value
            if value in {"superseded", "equivalent_review_accepted"}
            else None
        )

    def historical_repairs(
        self,
        product_id: str,
        invalidator_ids: list[str],
    ) -> list[str]:
        """Expose exact older repair links without inferring equivalence."""

        invalidators = set(invalidator_ids)
        product_created_at = self.bases.get(product_id, {}).get(
            "created_at", ""
        )
        candidates = []
        for research_id, record in self.bases.items():
            if record.get("kind") != "repair":
                continue
            lineage = self.lifecycle._structured_repair_lineage(
                repair_id=research_id,
                repair=record,
                bases=self.bases,
            )
            if lineage is not None:
                source_id, trigger_id = lineage
                if source_id == product_id and trigger_id in invalidators:
                    candidates.append(research_id)
                continue

            # Old unstructured repair records have no rigid repair_of/trigger
            # fields.  Preserve their bounded historical reader, where the
            # conventional relation label remains part of the legacy shape.
            if record.get("relation") not in {"repairs", "extends"}:
                continue
            related = record.get("related_research_ids")
            related_ids = set(related) if isinstance(related, list) else set()
            if (
                product_id in related_ids
                and invalidators.intersection(related_ids)
                and record.get("created_at", "") > product_created_at
            ):
                candidates.append(research_id)
        return sorted(
            candidates,
            key=lambda item: (self.bases[item]["created_at"], item),
        )

    def research(
        self,
        research_id: str,
        *,
        preferred_production_round_id: str | None = None,
    ) -> dict[str, Any]:
        """Derive one exact Research's next lifecycle operation."""

        explicit_disposition = self.explicit_attention_disposition(
            research_id
        )
        if explicit_disposition is not None:
            return self.action(
                "none",
                f"main_{explicit_disposition}",
                research_ids=[research_id],
                primary_research_id=research_id,
            )

        bindings = self.inspection.completion_obligation_rounds
        if bindings is None:
            return self.action(
                "main_reconciliation",
                "round_index_unavailable",
                research_ids=[research_id],
                primary_research_id=research_id,
            )
        production_rounds = sorted(
            {
                round_id
                for round_id, subround in bindings.get(research_id, [])
                if subround == "production"
            }
        )
        if preferred_production_round_id is not None:
            if preferred_production_round_id not in production_rounds:
                return self.action(
                    "main_reconciliation",
                    "preferred_production_round_binding_missing",
                    research_ids=[research_id],
                    round_ids=[preferred_production_round_id],
                    primary_research_id=research_id,
                    primary_round_id=preferred_production_round_id,
                )
            # Campaign active-head projection owns one exact current workflow
            # lane.  Historical rounds for the same Research remain readable
            # history, but cannot donate product, completion, or supervision
            # state to the target-bound round selected by Main.
            production_rounds = [preferred_production_round_id]
        product_rounds: dict[str, str] = {}
        awaiting: set[str] = set()
        returns: set[str] = set()
        unsafe: set[str] = set()
        for round_id in production_rounds:
            try:
                status = self.lifecycle._round_status_with_context(
                    round_id, self.inspection
                )
            except (KeyError, OSError, ValueError):
                unsafe.add(round_id)
                continue
            matched = False
            for assignment in status["assignments"]:
                if (
                    assignment.get("research_id") != research_id
                    or assignment.get("assignment_role") == "paired_adverse"
                ):
                    continue
                matched = True
                state = assignment.get("state")
                if state == "ingested":
                    product_id = assignment.get("research_product_id")
                    if isinstance(product_id, str) and product_id in self.bases:
                        product_rounds[product_id] = round_id
                    else:
                        unsafe.add(round_id)
                elif state == "return_present":
                    returns.add(round_id)
                elif state == "awaiting_return":
                    awaiting.add(round_id)
                elif state != "frozen_aborted":
                    unsafe.add(round_id)
            if not matched:
                unsafe.add(round_id)

        products = sorted(
            product_rounds,
            key=lambda item: (self.bases[item]["created_at"], item),
        )
        all_rounds = [*production_rounds, *returns, *awaiting, *unsafe]
        if len(products) > 1:
            return self.action(
                "main_reconciliation",
                "multiple_ingested_production_products",
                research_ids=[research_id, *products],
                round_ids=all_rounds,
                primary_research_id=research_id,
            )
        if not products:
            if returns:
                return self.action(
                    "ingest_return",
                    "production_return_present",
                    research_ids=[research_id],
                    round_ids=list(returns),
                    primary_research_id=research_id,
                )
            if awaiting:
                return self.action(
                    "await_return",
                    "production_round_in_flight",
                    research_ids=[research_id],
                    round_ids=list(awaiting),
                    primary_research_id=research_id,
                )
            if unsafe:
                return self.action(
                    "main_reconciliation",
                    "production_round_unreadable_or_quarantined",
                    research_ids=[research_id],
                    round_ids=list(unsafe),
                    primary_research_id=research_id,
                )
            return self.action(
                "production",
                "no_ingested_production_product",
                research_ids=[research_id],
                primary_research_id=research_id,
            )

        product_id = products[0]
        production_round = product_rounds[product_id]
        if returns or awaiting or unsafe:
            return self.action(
                "main_reconciliation",
                "ingested_product_with_additional_open_or_unsafe_production_branch",
                research_ids=[research_id, product_id],
                round_ids=all_rounds,
                primary_research_id=product_id,
                primary_round_id=production_round,
            )

        invalidators = self.route_staleness.get(product_id, [])
        if invalidators:
            repairs = self.historical_repairs(product_id, invalidators)
            if repairs:
                return self.action(
                    "main_reconciliation",
                    "historical_or_ambiguous_repair_lineage",
                    research_ids=[product_id, *invalidators, *repairs],
                    round_ids=[production_round],
                    primary_research_id=repairs[0],
                    primary_round_id=production_round,
                )
            return self.action(
                "repair",
                "production_product_invalidated",
                research_ids=[product_id, *invalidators],
                round_ids=[production_round],
                primary_research_id=product_id,
                primary_round_id=production_round,
            )

        product = self.bases[product_id]
        product_disposition = self.explicit_attention_disposition(product_id)
        if product_disposition is not None:
            return self.action(
                "none",
                f"main_{product_disposition}",
                research_ids=[product_id],
                round_ids=[production_round],
                primary_research_id=product_id,
                primary_round_id=production_round,
            )

        supervision_index = (
            self.inspection.supervision_round_ids_by_production_round or {}
        )
        supervision_rounds = supervision_index.get(production_round, [])
        if not supervision_rounds:
            if not self.lifecycle._frontier_completion_product_is_safe(
                product=product,
                dispositions=self.dispositions,
                route_staleness=self.route_staleness,
            ):
                return self.action(
                    "main_reconciliation",
                    "ingested_product_not_safe_for_automatic_routing",
                    research_ids=[research_id, product_id],
                    round_ids=[production_round],
                    primary_research_id=product_id,
                    primary_round_id=production_round,
                )
            try:
                coverage = self.lifecycle._candidate_supervision_scope_coverage(
                    [product], _inspection_context=self.inspection
                )
            except (KeyError, OSError, ValueError):
                return self.action(
                    "main_reconciliation",
                    "supervision_result_lineage_unreadable",
                    research_ids=[product_id],
                    round_ids=[production_round],
                    primary_research_id=product_id,
                    primary_round_id=production_round,
                )
            coverage_route = self._supervision_coverage_route(coverage)
            next_action, reason = coverage_route or (
                "supervision",
                "production_product_awaits_supervision",
            )
            coverage_rounds = sorted(
                {
                    round_id
                    for item in coverage
                    for field in ("pending_round_ids", "unsafe_round_ids")
                    for round_id in item.get(field, [])
                }
            )
            return self.action(
                next_action,
                reason,
                research_ids=[product_id],
                round_ids=[production_round, *coverage_rounds],
                primary_research_id=product_id,
                primary_round_id=production_round,
                supervision_coverage=coverage,
            )

        supervision_awaiting: set[str] = set()
        supervision_returns: set[str] = set()
        supervision_quarantined: set[str] = set()
        supervision_unreadable: set[str] = set()
        for round_id in supervision_rounds:
            try:
                status = self.lifecycle._round_status_with_context(
                    round_id, self.inspection
                )
            except (KeyError, OSError, ValueError):
                supervision_unreadable.add(round_id)
                continue
            states = {
                assignment.get("state")
                for assignment in status["assignments"]
            }
            if "quarantined" in states:
                supervision_quarantined.add(round_id)
            if "return_present" in states:
                supervision_returns.add(round_id)
            if "awaiting_return" in states:
                supervision_awaiting.add(round_id)
        if supervision_unreadable:
            return self.action(
                "main_reconciliation",
                "supervision_result_lineage_unreadable",
                research_ids=[product_id],
                round_ids=list(supervision_unreadable),
                primary_research_id=product_id,
            )
        try:
            coverage = self.lifecycle._candidate_supervision_scope_coverage(
                [product], _inspection_context=self.inspection
            )
        except (KeyError, OSError, ValueError):
            return self.action(
                "main_reconciliation",
                "supervision_result_lineage_unreadable",
                research_ids=[product_id],
                round_ids=supervision_rounds,
                primary_research_id=product_id,
            )
        if supervision_quarantined:
            coverage_route = self._supervision_coverage_route(coverage)
            if coverage_route != (
                "main_reconciliation",
                "supervision_scope_coverage_unsafe",
            ):
                return self.action(
                    "main_reconciliation",
                    "supervision_result_lineage_unreadable",
                    research_ids=[product_id],
                    round_ids=list(supervision_quarantined),
                    primary_research_id=product_id,
                )
            return self.action(
                *coverage_route,
                research_ids=[product_id],
                round_ids=list(supervision_quarantined),
                primary_research_id=product_id,
                supervision_coverage=coverage,
            )
        if supervision_returns:
            return self.action(
                "ingest_return",
                "supervision_return_present",
                research_ids=[product_id],
                round_ids=list(supervision_returns),
                primary_research_id=product_id,
                supervision_coverage=coverage,
            )
        if supervision_awaiting:
            return self.action(
                "await_return",
                "supervision_round_in_flight",
                research_ids=[product_id],
                round_ids=list(supervision_awaiting),
                primary_research_id=product_id,
                supervision_coverage=coverage,
            )

        # Existing live supervision is an operational fact and remains visible
        # even when the pre-supervision product is semantically unsafe.  Once
        # no live state remains, safety again controls interpretation of the
        # completed supervision lineage.
        if not self.lifecycle._frontier_completion_product_is_safe(
            product=product,
            dispositions=self.dispositions,
            route_staleness=self.route_staleness,
        ):
            return self.action(
                "main_reconciliation",
                "ingested_product_not_safe_for_automatic_routing",
                research_ids=[research_id, product_id],
                round_ids=[production_round, *supervision_rounds],
                primary_research_id=product_id,
                primary_round_id=production_round,
                supervision_coverage=coverage,
            )

        try:
            incomplete = [
                item for item in coverage if item["state"] != "completed"
            ]
            coverage_rounds = sorted(
                {
                    round_id
                    for item in coverage
                    for field in ("pending_round_ids", "unsafe_round_ids")
                    for round_id in item.get(field, [])
                }
            )
            result_ids = sorted(
                {
                    result_id
                    for item in coverage
                    for result_id in item["result_research_ids"]
                }
            )
            results = [
                self.lifecycle._inspection_research_record(
                    result_id, self.inspection
                )
                for result_id in result_ids
            ]
        except (KeyError, OSError, ValueError):
            return self.action(
                "main_reconciliation",
                "supervision_result_lineage_unreadable",
                research_ids=[product_id],
                round_ids=supervision_rounds,
                primary_research_id=product_id,
            )
        if incomplete:
            coverage_route = self._supervision_coverage_route(coverage)
            assert coverage_route is not None
            next_action, reason = coverage_route
            return self.action(
                next_action,
                reason,
                research_ids=[product_id, *result_ids],
                round_ids=[
                    production_round,
                    *supervision_rounds,
                    *coverage_rounds,
                ],
                primary_research_id=product_id,
                primary_round_id=production_round,
                supervision_coverage=coverage,
            )
        unsafe_results = [
            item["research_id"]
            for item in results
            if not self.lifecycle._frontier_completion_product_is_safe(
                product=item,
                dispositions=self.dispositions,
                route_staleness=self.route_staleness,
            )
        ]
        if unsafe_results:
            unsafe_ids = set(unsafe_results)
            coverage = [
                {
                    **item,
                    "state": "unsafe",
                    "reason": "supervision_result_requires_semantic_disposition",
                }
                if unsafe_ids.intersection(item["result_research_ids"])
                else item
                for item in coverage
            ]
            return self.action(
                "main_reconciliation",
                "supervision_result_requires_semantic_disposition",
                research_ids=[product_id, *unsafe_results],
                round_ids=supervision_rounds,
                primary_research_id=product_id,
                supervision_coverage=coverage,
            )
        reason = (
            "clean_supervision_not_reflected_in_automatic_completion"
            if result_ids
            else "supervision_round_completed_without_result"
        )
        return self.action(
            "main_reconciliation",
            reason,
            research_ids=[product_id, *result_ids],
            round_ids=supervision_rounds,
            primary_research_id=product_id,
            supervision_coverage=coverage,
        )

    def groups(
        self,
        *,
        workgroups: dict[str, list[str]],
        work_keys: set[str],
        group_completion: dict[str, tuple[str, str | None, int, str]],
    ) -> dict[str, dict[str, Any]]:
        terminals = {
            work_key: self.lifecycle._frontier_cow_terminal_members_for_inspection(
                seed_members=workgroups.get(work_key, []),
                bases=self.bases,
                route_staleness=self.route_staleness,
                inspection=self.inspection,
            )
            for work_key in work_keys
        }
        projected: dict[str, dict[str, Any]] = {}
        for work_key in sorted(work_keys):
            completion = group_completion[work_key]
            members = workgroups.get(work_key, [])
            if completion[0] != "pending":
                completed_id = completion[1]
                projected[work_key] = self.action(
                    "none",
                    "workgroup_completed",
                    research_ids=[completed_id] if completed_id else [],
                    primary_research_id=completed_id,
                )
                continue
            terminal_map = terminals[work_key]
            if any(value is None for value in terminal_map.values()):
                projected[work_key] = self.action(
                    "main_reconciliation",
                    "ambiguous_or_cyclic_canonical_repair_branch",
                    research_ids=members,
                    primary_research_id=members[0] if members else None,
                )
                continue
            # COW terminals decide whether this exact workgroup is complete or
            # has an ambiguous repair branch.  They are not workflow aliases:
            # a later repair task owns its own production assignment, product,
            # component, and supervision lineage.  Project those operational
            # identities only from the physical members of this workgroup.
            # Campaign product heads are redirected to their bound assignment
            # source before work-key selection, where the explicit workflow
            # identity can be validated against task binding and provenance.
            workflow_ids = sorted(
                set(members),
                key=lambda item: (self.bases[item]["created_at"], item),
            )
            states = [self.research(item) for item in workflow_ids]
            nonproduction = [
                item for item in states if item["next_action"] != "production"
            ]
            if len(nonproduction) == 1:
                projected[work_key] = nonproduction[0]
                continue
            if not nonproduction and states:
                projected[work_key] = states[0]
                continue
            if len(states) == 1:
                projected[work_key] = states[0]
                continue
            research_ids = sorted(
                {
                    value
                    for state in states
                    for value in state["actionable_research_ids"]
                }
            )
            round_ids = sorted(
                {
                    value
                    for state in states
                    for value in state["actionable_round_ids"]
                }
            )
            projected[work_key] = self.action(
                "main_reconciliation",
                "multiple_active_work_branches",
                research_ids=research_ids or members,
                round_ids=round_ids,
                primary_research_id=(
                    research_ids[0]
                    if research_ids
                    else members[0] if members else None
                ),
            )
        return projected


def _project_research_action(
    lifecycle: Any,
    *,
    research_id: str,
    bases: dict[str, dict[str, Any]],
    dispositions: dict[str, dict[str, Any]],
    route_staleness: dict[str, list[str]],
    inspection: Any,
    preferred_production_round_id: str | None = None,
) -> dict[str, Any]:
    return _ActionProjector(
        lifecycle,
        bases=bases,
        dispositions=dispositions,
        route_staleness=route_staleness,
        inspection=inspection,
    ).research(
        research_id,
        preferred_production_round_id=preferred_production_round_id,
    )


def project_frontier_group_actions(
    lifecycle: Any,
    *,
    workgroups: dict[str, list[str]],
    work_keys: set[str],
    bases: dict[str, dict[str, Any]],
    dispositions: dict[str, dict[str, Any]],
    route_staleness: dict[str, list[str]],
    group_completion: dict[str, tuple[str, str | None, int, str]],
    inspection: Any,
) -> dict[str, dict[str, Any]]:
    return _ActionProjector(
        lifecycle,
        bases=bases,
        dispositions=dispositions,
        route_staleness=route_staleness,
        inspection=inspection,
    ).groups(
        workgroups=workgroups,
        work_keys=work_keys,
        group_completion=group_completion,
    )

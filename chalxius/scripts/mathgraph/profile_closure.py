from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .computations import validate_experiment_final_receipt
from .contracts import (
    ROUND_ID_RE,
    SHA256_RE,
    contained_path,
    require_exact_keys,
    require_string,
    sha256_bytes,
    sha256_json,
    validate_assignment_id,
    validate_campaign_id,
    validate_round_id,
)
from .fact_bundles import (
    validate_expert_lint_receipt,
    validate_interpret_lint_receipt,
)
from .modes import (
    EXPLORATION_FEATURES,
    UNIFIED_POLICY_REVISION,
    build_round_profile_obligations,
)
from .protocol import validate_task_card


PROFILE_CLOSURE_SCHEMA_VERSION = 1
PROFILE_CLOSURE_PREFIX = "profileclose-"
_PULSE_FEATURES = {
    "parallel_clean_context_panel",
    "barriered_blackboard_pulse",
}
_PAPER_SNAPSHOT_FEATURES = {
    "paper_logic_graph": "logic",
    "paper_audit_graph": "audit",
}
_HOST_EVIDENCE_LEVEL = "procedural_host_attestation"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _parse_utc_timestamp(value: Any, *, label: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} is not a valid ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label} must include a UTC offset")
    return parsed.astimezone(timezone.utc)


class ProfileClosureManager:
    """Hash-bound closure of required high-cost exploration obligations.

    This is a workflow gate adjacent to, but deliberately outside, the
    reasoning-mode-invariant Fact admission contract.
    """

    def __init__(self, store: Any) -> None:
        self.store = store
        self.root = (
            store.root
            / "governance"
            / "unified-mode"
            / "profile-closures"
            / "by-round"
        )

    def _path(self, round_id: str) -> Path:
        return self.root / f"{validate_round_id(round_id)}.json"

    def _round_manifest(self, round_id: str) -> dict[str, Any]:
        round_id = validate_round_id(round_id)
        path = self.store.rounds_dir / round_id / "round.json"
        if path.is_symlink() or not path.is_file():
            raise ValueError("profile closure round manifest is missing or unsafe")
        manifest = self.store._read_json(path)
        if (
            manifest.get("schema_version") != 4
            or manifest.get("project_id") != self.store.project_id()
            or manifest.get("round_id") != round_id
            or "reasoning_mode" not in manifest
        ):
            raise ValueError("profile closure requires a unified V4 round")
        return manifest

    def obligation_view(self, round_id: str) -> dict[str, Any]:
        manifest = self._round_manifest(round_id)
        manifest_path = self.store.rounds_dir / round_id / "round.json"
        profiles: dict[str, dict[str, Any]] = {}
        assignment_contexts: dict[str, dict[str, Any]] = {}
        assignments = manifest.get("assignments")
        if not isinstance(assignments, list) or not assignments:
            raise ValueError("profile closure round assignments are invalid")
        host_scopes: set[str] = set()
        memory_ids: set[str] = set()
        campaign_ids: set[str] = set()
        for assignment in assignments:
            if not isinstance(assignment, dict):
                raise ValueError("profile closure assignment is invalid")
            assignment_id = validate_assignment_id(
                require_string(assignment, "assignment_id")
            )
            task_path = contained_path(
                self.store.root,
                require_string(assignment, "task_card_relpath"),
                "profile closure task card",
            )
            if task_path.is_symlink() or not task_path.is_file():
                raise ValueError("profile closure task card is missing or unsafe")
            if sha256_bytes(task_path.read_bytes()) != assignment.get(
                "task_card_sha256"
            ):
                raise ValueError("profile closure task-card hash mismatch")
            card = self.store._read_json(task_path)
            validate_task_card(card, allow_legacy_adoption=True)
            if (
                card.get("round_id") != round_id
                or card.get("assignment_id") != assignment_id
            ):
                raise ValueError("profile closure task-card binding mismatch")
            profile = card.get("execution_profile")
            if not isinstance(profile, dict):
                raise ValueError("profile closure task card has no execution profile")
            profiles[assignment_id] = profile
            contract = assignment.get("contract")
            if not isinstance(contract, dict) or sha256_json(contract) != assignment.get(
                "assignment_sha256"
            ):
                raise ValueError("profile closure assignment contract hash mismatch")
            if (
                contract.get("round_id") != round_id
                or contract.get("assignment_id") != assignment_id
                or contract.get("execution_profile") != profile
                or contract.get("reasoning_mode_event_id")
                != card.get("reasoning_mode_event_id")
            ):
                raise ValueError(
                    "profile closure assignment/task-card profile binding mismatch"
                )
            host_scopes.add(require_string(card, "host_task_scope_id"))
            memory_ids.add(require_string(card, "memory_id"))
            campaign_ids.add(require_string(card, "campaign_id"))
            source_claim_id = card.get("source_claim_id")
            source_artifact_sha256: str | None = None
            if source_claim_id is not None:
                claim = self.store.claims().show_claim(source_claim_id)
                source = claim.get("source")
                if not isinstance(source, dict):
                    raise ValueError("profile closure source claim is malformed")
                source_artifact_sha256 = require_string(
                    source, "artifact_sha256"
                )
            assignment_contexts[assignment_id] = {
                "memory_id": card["memory_id"],
                "campaign_id": card["campaign_id"],
                "source_claim_id": source_claim_id,
                "source_artifact_sha256": source_artifact_sha256,
                "assignment_sha256": assignment["assignment_sha256"],
                "task_card_sha256": assignment["task_card_sha256"],
            }
        if len(host_scopes) != 1:
            raise ValueError("profile closure round has inconsistent host-task scopes")
        round_created_at = require_string(manifest, "created_at")
        _parse_utc_timestamp(
            round_created_at,
            label="profile closure round created_at",
        )
        obligations = build_round_profile_obligations(profiles)
        frozen = manifest.get("profile_obligations")
        if frozen is None:
            raise ValueError(
                "unified round predates profile-obligation closure; replan instead "
                "of synthesizing closure evidence"
            )
        if frozen != obligations:
            raise ValueError("round profile-obligation manifest binding mismatch")
        profile_hashes = manifest.get("execution_profile")
        expected_hashes = {
            assignment_id: profile["execution_profile_sha256"]
            for assignment_id, profile in sorted(profiles.items())
        }
        if profile_hashes != expected_hashes:
            raise ValueError("round execution-profile hash map mismatch")
        return {
            **obligations,
            "round_id": round_id,
            "round_created_at": round_created_at,
            "reasoning_mode": manifest["reasoning_mode"],
            "reasoning_mode_event_id": manifest["reasoning_mode_event_id"],
            "host_task_scope_id": next(iter(host_scopes)),
            "memory_ids": sorted(memory_ids),
            "campaign_ids": sorted(campaign_ids),
            "assignment_contexts": assignment_contexts,
            "round_manifest_sha256": sha256_bytes(manifest_path.read_bytes()),
            "manifest_binding": "frozen",
        }

    @staticmethod
    def _required_assignments(
        view: dict[str, Any], feature: str
    ) -> list[str]:
        return sorted(
            assignment_id
            for assignment_id, binding in view["assignments"].items()
            if binding["feature_statuses"][feature] == "required"
        )

    def _artifact(
        self,
        payload: Any,
        *,
        label: str,
        allowed_relpaths: tuple[str, ...] = (),
        allowed_prefixes: tuple[str, ...] = (),
    ) -> dict[str, str]:
        if not isinstance(payload, dict):
            raise ValueError(f"{label} must be one object")
        require_exact_keys(
            payload,
            required={"relpath", "sha256"},
            label=label,
        )
        relpath = require_string(payload, "relpath")
        if (allowed_relpaths or allowed_prefixes) and not (
            relpath in allowed_relpaths
            or any(relpath.startswith(prefix) for prefix in allowed_prefixes)
        ):
            raise ValueError(f"{label} is outside the allowed evidence paths")
        digest = require_string(payload, "sha256")
        if SHA256_RE.fullmatch(digest) is None:
            raise ValueError(f"{label}.sha256 is invalid")
        path = contained_path(self.store.root, relpath, label)
        lexical_path = self.store.root / relpath
        lexical_parents = []
        current = lexical_path.parent
        while current != self.store.root and current != current.parent:
            lexical_parents.append(current)
            current = current.parent
        if (
            lexical_path.is_symlink()
            or any(parent.is_symlink() for parent in lexical_parents)
            or path.is_symlink()
            or not path.is_file()
        ):
            raise ValueError(f"{label} is missing or unsafe")
        if path.is_relative_to(self.root):
            raise ValueError(f"{label} cannot cite the profile closure itself")
        if sha256_bytes(path.read_bytes()) != digest:
            raise ValueError(f"{label} hash mismatch")
        return {"relpath": relpath, "sha256": digest}

    def _pulse_binding(
        self,
        spec: dict[str, Any],
        *,
        feature: str,
        view: dict[str, Any],
    ) -> dict[str, Any]:
        required_assignment_ids = self._required_assignments(view, feature)
        required_assignment_set = set(required_assignment_ids)
        if feature == "parallel_clean_context_panel":
            require_exact_keys(
                spec,
                required={
                    "feature",
                    "evidence_kind",
                    "pulse_id",
                    "host_task_scope_id",
                    "host_callable_slots",
                    "eligible_distinct_directions",
                    "selected_assignment_ids",
                },
                label=f"profile closure evidence {feature}",
            )
            if spec.get("evidence_kind") != "native_pulse_with_host_capacity":
                raise ValueError(
                    f"{feature} requires native_pulse_with_host_capacity evidence"
                )
            if spec.get("host_task_scope_id") != view["host_task_scope_id"]:
                raise ValueError("panel host-task scope mismatch")
            callable_slots = spec.get("host_callable_slots")
            eligible_directions = spec.get("eligible_distinct_directions")
            if any(
                isinstance(value, bool) or not isinstance(value, int) or value < 1
                for value in (callable_slots, eligible_directions)
            ):
                raise ValueError("panel host capacity values must be positive integers")
            selected_assignment_ids = spec.get("selected_assignment_ids")
            if (
                not isinstance(selected_assignment_ids, list)
                or selected_assignment_ids != sorted(set(selected_assignment_ids))
                or selected_assignment_ids != required_assignment_ids
                or len(selected_assignment_ids)
                != min(callable_slots, eligible_directions)
            ):
                raise ValueError(
                    "panel selection must fill min(callable slots, eligible directions) "
                    "with exactly the assignments requiring the panel"
                )
        else:
            require_exact_keys(
                spec,
                required={"feature", "evidence_kind", "pulse_id"},
                label=f"profile closure evidence {feature}",
            )
            if spec.get("evidence_kind") != "native_pulse_closure":
                raise ValueError(
                    f"{feature} requires native_pulse_closure evidence"
                )
        pulse_id = require_string(spec, "pulse_id")
        pulses = self.store.collaboration()
        plan = pulses.plan(pulse_id)
        status = pulses.status(pulse_id)
        if status.get("state") != "closed_machine_ready":
            raise ValueError(
                f"{feature} requires a machine-verified closed Blackboard pulse"
            )
        closure = pulses.closure(pulse_id)
        barrier = pulses.barrier(pulse_id)
        commitments = [
            *plan.get("wave1_commitments", []),
            *barrier.get("review_commitments", []),
        ]
        round_commitments = [
            item
            for item in commitments
            if isinstance(item, dict) and item.get("round_id") == view["round_id"]
        ]
        relevant_commitments = [
            item
            for item in round_commitments
            if item.get("assignment_id") in required_assignment_set
        ]
        if not relevant_commitments:
            raise ValueError(f"{feature} pulse does not bind the governed round")
        bound_assignment_ids = {
            item.get("assignment_id") for item in relevant_commitments
        }
        if bound_assignment_ids != required_assignment_set:
            raise ValueError(
                f"{feature} pulse must cover every governed assignment requiring it"
            )
        if feature == "parallel_clean_context_panel":
            if len(bound_assignment_ids) < 2:
                raise ValueError(
                    "parallel_clean_context_panel requires at least two distinct "
                    "assignments from the governed round"
                )
        closure_path = pulses.root / pulse_id / "closure.json"
        return {
            "feature": feature,
            "evidence_kind": spec["evidence_kind"],
            "evidence_level": (
                "mixed_procedural_and_machine_verified"
                if feature == "parallel_clean_context_panel"
                else "machine_verified"
            ),
            "pulse_id": pulse_id,
            "pulse_closure_id": closure["closure_id"],
            "pulse_closure_sha256": sha256_bytes(closure_path.read_bytes()),
            "bound_round_commitment_ids": sorted(
                item["commitment_id"] for item in relevant_commitments
            ),
            "covered_assignment_ids": required_assignment_ids,
            **(
                {
                    "host_task_scope_id": view["host_task_scope_id"],
                    "host_callable_slots": callable_slots,
                    "eligible_distinct_directions": eligible_directions,
                    "selected_assignment_ids": selected_assignment_ids,
                    "capacity_attestation_level": _HOST_EVIDENCE_LEVEL,
                    "pulse_commitment_level": "machine_verified",
                }
                if feature == "parallel_clean_context_panel"
                else {}
            ),
        }

    def _specialist_binding(
        self,
        spec: dict[str, Any],
        *,
        view: dict[str, Any],
    ) -> dict[str, Any]:
        feature = "orthogonal_specialist_escalation"
        require_exact_keys(
            spec,
            required={
                "feature",
                "evidence_kind",
                "evidence_level",
                "host_task_scope_id",
                "contexts",
            },
            label=f"profile closure evidence {feature}",
        )
        if (
            spec.get("evidence_kind") != "host_specialist_artifacts"
            or spec.get("evidence_level") != _HOST_EVIDENCE_LEVEL
            or spec.get("host_task_scope_id") != view["host_task_scope_id"]
        ):
            raise ValueError("specialist evidence kind/level/host scope mismatch")
        contexts = spec.get("contexts")
        if not isinstance(contexts, list) or len(contexts) < 2:
            raise ValueError("specialist evidence requires core and specialist contexts")
        normalized: list[dict[str, Any]] = []
        context_ids: set[str] = set()
        roles: set[str] = set()
        specialties: set[str] = set()
        for index, context in enumerate(contexts, 1):
            if not isinstance(context, dict):
                raise ValueError("specialist context must be one object")
            require_exact_keys(
                context,
                required={
                    "context_id",
                    "assignment_id",
                    "role",
                    "specialty",
                    "artifact",
                },
                label=f"specialist context {index}",
            )
            context_id = require_string(context, "context_id")
            assignment_id = validate_assignment_id(
                require_string(context, "assignment_id")
            )
            if assignment_id not in view["assignments"]:
                raise ValueError("specialist context belongs to another round")
            role = require_string(context, "role")
            specialty = require_string(context, "specialty")
            if context_id in context_ids:
                raise ValueError("specialist context ids must be unique")
            context_ids.add(context_id)
            roles.add(role)
            specialties.add(specialty)
            normalized.append(
                {
                    "context_id": context_id,
                    "assignment_id": assignment_id,
                    "role": role,
                    "specialty": specialty,
                    "artifact": self._artifact(
                        context["artifact"],
                        label=f"specialist context {index} artifact",
                        allowed_relpaths=(
                            f"rounds/{view['round_id']}/returns/{assignment_id}.json",
                        ),
                        allowed_prefixes=(
                            f"rounds/{view['round_id']}/artifacts/{assignment_id}/",
                        ),
                    ),
                }
            )
        if "specialist" not in roles or len(roles) < 2 or len(specialties) < 2:
            raise ValueError(
                "specialist evidence requires an orthogonal specialist and core role"
            )
        if len({item["artifact"]["sha256"] for item in normalized}) < 2:
            raise ValueError(
                "specialist core and specialist artifacts must have distinct hashes"
            )
        covered = sorted({item["assignment_id"] for item in normalized})
        if covered != self._required_assignments(view, feature):
            raise ValueError(
                "specialist evidence must cover every assignment requiring the feature"
            )
        return {
            "feature": feature,
            "evidence_kind": "host_specialist_artifacts",
            "evidence_level": _HOST_EVIDENCE_LEVEL,
            "host_task_scope_id": view["host_task_scope_id"],
            "round_manifest_sha256": view["round_manifest_sha256"],
            "assignment_profiles": view["assignments"],
            "covered_assignment_ids": covered,
            "contexts": normalized,
        }

    def _campaign_binding(
        self,
        spec: dict[str, Any],
        *,
        view: dict[str, Any],
    ) -> dict[str, Any]:
        feature = "long_horizon_campaign_expansion"
        require_exact_keys(
            spec,
            required={
                "feature",
                "evidence_kind",
                "evidence_level",
                "host_task_scope_id",
                "campaigns",
            },
            label=f"profile closure evidence {feature}",
        )
        if (
            spec.get("evidence_kind") != "campaign_expansion_artifacts"
            or spec.get("evidence_level") != _HOST_EVIDENCE_LEVEL
            or spec.get("host_task_scope_id") != view["host_task_scope_id"]
        ):
            raise ValueError("campaign expansion evidence kind/level/host scope mismatch")
        campaigns = spec.get("campaigns")
        if not isinstance(campaigns, list) or not campaigns:
            raise ValueError("campaign expansion campaigns must be nonempty")
        bindings: list[dict[str, Any]] = []
        campaign_ids: set[str] = set()
        covered_all: set[str] = set()
        required = set(self._required_assignments(view, feature))
        for index, campaign in enumerate(campaigns, 1):
            if not isinstance(campaign, dict):
                raise ValueError("campaign expansion entry must be one object")
            require_exact_keys(
                campaign,
                required={
                    "campaign_id",
                    "covered_assignment_ids",
                    "campaign_event_ids",
                    "before",
                    "after",
                },
                label=f"campaign expansion entry {index}",
            )
            campaign_id = validate_campaign_id(
                require_string(campaign, "campaign_id")
            )
            if campaign_id in campaign_ids:
                raise ValueError("campaign expansion campaign ids must be unique")
            campaign_ids.add(campaign_id)
            covered = campaign.get("covered_assignment_ids")
            if (
                not isinstance(covered, list)
                or not covered
                or covered != sorted(set(covered))
                or any(assignment_id not in required for assignment_id in covered)
                or covered_all.intersection(covered)
            ):
                raise ValueError("campaign expansion assignment coverage is invalid")
            if any(
                view["assignment_contexts"][assignment_id]["campaign_id"]
                != campaign_id
                for assignment_id in covered
            ):
                raise ValueError(
                    "campaign expansion assignment belongs to another campaign"
                )
            bindings.append(
                self._campaign_entry_binding(
                    campaign,
                    campaign_id=campaign_id,
                    covered=covered,
                    view=view,
                )
            )
            covered_all.update(covered)
        if covered_all != required:
            raise ValueError(
                "campaign expansion must cover every assignment requiring the feature"
            )
        return {
            "feature": feature,
            "evidence_kind": "campaign_expansion_artifacts",
            "evidence_level": _HOST_EVIDENCE_LEVEL,
            "host_task_scope_id": view["host_task_scope_id"],
            "round_manifest_sha256": view["round_manifest_sha256"],
            "assignment_profiles": view["assignments"],
            "covered_assignment_ids": sorted(covered_all),
            "campaigns": sorted(bindings, key=lambda item: item["campaign_id"]),
        }

    def _campaign_entry_binding(
        self,
        spec: dict[str, Any],
        *,
        campaign_id: str,
        covered: list[str],
        view: dict[str, Any],
    ) -> dict[str, Any]:
        self.store.campaigns().status(campaign_id)
        campaign_events = self.store._read_jsonl(
            self.store.campaigns().root / campaign_id / "events.jsonl"
        )
        if not campaign_events or campaign_events[0].get("event") != "created":
            raise ValueError("campaign expansion has no immutable create event")
        event_ids = spec.get("campaign_event_ids")
        if (
            not isinstance(event_ids, list)
            or not event_ids
            or event_ids != sorted(set(event_ids))
        ):
            raise ValueError("campaign expansion event ids must be nonempty and unique")
        by_event_id = {event.get("event_id"): event for event in campaign_events}
        selected_events = [by_event_id.get(event_id) for event_id in event_ids]
        if any(event is None for event in selected_events) or any(
            event.get("event")
            not in {
                "target_added",
                "constraint_added",
                "stop_condition_disposition",
                "value_definition_updated",
            }
            for event in selected_events
            if isinstance(event, dict)
        ):
            raise ValueError(
                "campaign expansion must bind concrete non-note expansion events"
            )
        round_created_at = _parse_utc_timestamp(
            view["round_created_at"], label="profile closure round created_at"
        )
        if any(
            _parse_utc_timestamp(
                event.get("recorded_at"),
                label="campaign expansion event recorded_at",
            )
            < round_created_at
            for event in selected_events
            if isinstance(event, dict)
        ):
            raise ValueError(
                "campaign expansion event predates the governed round"
            )
        before = self._campaign_scope_artifact(
            spec["before"],
            label="campaign expansion before",
            phase="before",
            campaign_id=campaign_id,
            view=view,
            covered=covered,
        )
        after = self._campaign_scope_artifact(
            spec["after"],
            label="campaign expansion after",
            phase="after",
            campaign_id=campaign_id,
            view=view,
            covered=covered,
        )
        if before["sha256"] == after["sha256"]:
            raise ValueError("campaign expansion before/after artifacts must differ")
        if before["scope_sha256"] == after["scope_sha256"]:
            raise ValueError("campaign expansion before/after scope must differ")
        return {
            "campaign_id": campaign_id,
            "covered_assignment_ids": covered,
            "campaign_create_event_id": campaign_events[0]["event_id"],
            "campaign_event_ids": event_ids,
            "campaign_events_sha256": sha256_json(selected_events),
            "before": before,
            "after": after,
        }

    def _campaign_scope_artifact(
        self,
        payload: Any,
        *,
        label: str,
        phase: str,
        campaign_id: str,
        view: dict[str, Any],
        covered: list[str],
    ) -> dict[str, Any]:
        artifact = self._artifact(
            payload,
            label=label,
            allowed_prefixes=("reports/profile-closure-evidence/",),
        )
        path = contained_path(self.store.root, artifact["relpath"], label)
        try:
            content = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"{label} must be canonical JSON evidence") from exc
        if not isinstance(content, dict):
            raise ValueError(f"{label} must contain one JSON object")
        require_exact_keys(
            content,
            required={
                "schema_version",
                "phase",
                "campaign_id",
                "host_task_scope_id",
                "covered_assignment_ids",
                "scope",
            },
            label=label,
        )
        if (
            content.get("schema_version") != 1
            or content.get("phase") != phase
            or content.get("campaign_id") != campaign_id
            or content.get("host_task_scope_id") != view["host_task_scope_id"]
            or content.get("covered_assignment_ids") != covered
            or not isinstance(content.get("scope"), dict)
            or not content["scope"]
        ):
            raise ValueError(f"{label} scope binding is invalid or empty")
        return {
            **artifact,
            "scope_sha256": sha256_json(content["scope"]),
        }

    def _paper_snapshot_binding(
        self,
        spec: dict[str, Any],
        *,
        feature: str,
        view: dict[str, Any],
    ) -> dict[str, Any]:
        require_exact_keys(
            spec,
            required={"feature", "evidence_kind", "snapshots"},
            label=f"profile closure evidence {feature}",
        )
        if spec.get("evidence_kind") != "reviewed_paper_snapshots":
            raise ValueError(f"{feature} requires reviewed_paper_snapshots evidence")
        snapshots = spec.get("snapshots")
        if not isinstance(snapshots, list) or not snapshots:
            raise ValueError(f"{feature} snapshot evidence must be nonempty")
        bindings: list[dict[str, Any]] = []
        covered_all: set[str] = set()
        snapshot_ids: set[str] = set()
        required_assignments = set(self._required_assignments(view, feature))
        paper_status = self.store.paper_logic().status()
        current_snapshot_ids = set(paper_status["current_snapshot_ids"])
        superseded_snapshot_ids = set(paper_status["superseded_snapshot_ids"])
        for index, item in enumerate(snapshots, 1):
            if not isinstance(item, dict):
                raise ValueError("paper snapshot evidence entry must be one object")
            require_exact_keys(
                item,
                required={"snapshot_id", "covered_assignment_ids"},
                label=f"paper snapshot evidence {index}",
            )
            snapshot_id = require_string(item, "snapshot_id")
            if snapshot_id in snapshot_ids:
                raise ValueError("paper snapshot evidence ids must be unique")
            snapshot_ids.add(snapshot_id)
            covered = item.get("covered_assignment_ids")
            if (
                not isinstance(covered, list)
                or not covered
                or covered != sorted(set(covered))
                or any(item_id not in required_assignments for item_id in covered)
            ):
                raise ValueError("paper snapshot assignment coverage is invalid")
            manifest = self.store.paper_logic().snapshot_manifest(snapshot_id)
            if manifest.get("graph_kind") != _PAPER_SNAPSHOT_FEATURES[feature]:
                raise ValueError(f"{feature} paper snapshot graph kind mismatch")
            if (
                snapshot_id not in current_snapshot_ids
                or snapshot_id in superseded_snapshot_ids
            ):
                raise ValueError(f"{feature} paper snapshot is stale or superseded")
            if feature == "paper_audit_graph":
                base_snapshot_id = manifest.get("base_snapshot_id")
                if (
                    not isinstance(base_snapshot_id, str)
                    or not base_snapshot_id
                    or base_snapshot_id not in current_snapshot_ids
                    or base_snapshot_id in superseded_snapshot_ids
                ):
                    raise ValueError(
                        "paper audit snapshot is stale because its logic base was superseded"
                    )
            if not manifest.get("review_ids") or not all(
                value is True
                for key, value in manifest.get("readiness", {}).items()
                if key.endswith("_ready")
            ):
                raise ValueError(f"{feature} paper snapshot is not review-ready")
            artifact_hashes = {
                artifact.get("artifact_sha256")
                for artifact in manifest.get("source_artifacts", [])
                if isinstance(artifact, dict)
            }
            for assignment_id in covered:
                source_sha = view["assignment_contexts"][assignment_id][
                    "source_artifact_sha256"
                ]
                if not isinstance(source_sha, str) or source_sha not in artifact_hashes:
                    raise ValueError(
                        "paper snapshot does not cover the assignment source artifact"
                    )
            manifest_path = (
                self.store.paper_logic().snapshots_dir
                / snapshot_id
                / "manifest.json"
            )
            bindings.append(
                {
                    "snapshot_id": snapshot_id,
                    "paper_id": manifest["paper_id"],
                    "base_snapshot_id": manifest["base_snapshot_id"],
                    "supersedes_snapshot_id": manifest[
                        "supersedes_snapshot_id"
                    ],
                    "snapshot_manifest_sha256": sha256_bytes(
                        manifest_path.read_bytes()
                    ),
                    "review_ids": sorted(manifest["review_ids"]),
                    "source_artifact_sha256s": sorted(artifact_hashes),
                    "covered_assignment_ids": covered,
                }
            )
            overlap = covered_all.intersection(covered)
            if overlap:
                raise ValueError(
                    "paper snapshot assignment coverage must not overlap"
                )
            covered_all.update(covered)
        if covered_all != required_assignments:
            raise ValueError(
                "paper snapshot evidence must cover every assignment requiring the feature"
            )
        return {
            "feature": feature,
            "evidence_kind": "reviewed_paper_snapshots",
            "evidence_level": "machine_verified",
            "covered_assignment_ids": sorted(covered_all),
            "snapshots": sorted(bindings, key=lambda item: item["snapshot_id"]),
        }

    def _mirror_binding(
        self,
        spec: dict[str, Any],
        *,
        view: dict[str, Any],
    ) -> dict[str, Any]:
        feature = "full_fidelity_paper_mirror"
        require_exact_keys(
            spec,
            required={"feature", "evidence_kind", "projections"},
            label=f"profile closure evidence {feature}",
        )
        if spec.get("evidence_kind") != "native_paper_projections":
            raise ValueError(f"{feature} requires native_paper_projections evidence")
        projections = spec.get("projections")
        if not isinstance(projections, list) or not projections:
            raise ValueError("paper mirror projection evidence must be nonempty")
        required_assignments = set(self._required_assignments(view, feature))
        paper_status = self.store.paper_logic().status()
        current_snapshot_ids = set(paper_status["current_snapshot_ids"])
        superseded_snapshot_ids = set(paper_status["superseded_snapshot_ids"])
        covered_all: set[str] = set()
        bindings: list[dict[str, Any]] = []
        projection_ids: set[str] = set()
        for index, item in enumerate(projections, 1):
            if not isinstance(item, dict):
                raise ValueError("paper projection evidence entry must be one object")
            require_exact_keys(
                item,
                required={"projection_id", "covered_assignment_ids"},
                label=f"paper projection evidence {index}",
            )
            projection_id = require_string(item, "projection_id")
            if projection_id in projection_ids:
                raise ValueError("paper projection evidence ids must be unique")
            projection_ids.add(projection_id)
            covered = item.get("covered_assignment_ids")
            if (
                not isinstance(covered, list)
                or not covered
                or covered != sorted(set(covered))
                or any(item_id not in required_assignments for item_id in covered)
                or covered_all.intersection(covered)
            ):
                raise ValueError("paper projection assignment coverage is invalid")
            path = (
                self.store.paper_logic().projections_dir
                / f"{projection_id}.json"
            )
            if path.is_symlink() or not path.is_file():
                raise ValueError("paper projection receipt is missing or unsafe")
            projection = self.store._read_json(path)
            semantic = {
                key: value
                for key, value in projection.items()
                if key != "projection_id"
            }
            if (
                projection_id != "plp-" + sha256_json(semantic)
                or projection.get("projection_mode") != "full_fidelity"
                or projection.get("project_id") != self.store.project_id()
            ):
                raise ValueError("paper projection receipt binding mismatch")
            projected_snapshot_id = projection["paper_snapshot_id"]
            self.store.paper_logic().snapshot_manifest(projected_snapshot_id)
            if (
                projected_snapshot_id not in current_snapshot_ids
                or projected_snapshot_id in superseded_snapshot_ids
            ):
                raise ValueError("paper projection targets a stale or superseded snapshot")
            bindings.append(
                {
                    "projection_id": projection_id,
                    "projection_sha256": sha256_bytes(path.read_bytes()),
                    "paper_snapshot_id": projection["paper_snapshot_id"],
                    "blackboard_transaction_id": projection[
                        "blackboard_transaction_id"
                    ],
                    "covered_assignment_ids": covered,
                }
            )
            covered_all.update(covered)
        if covered_all != required_assignments:
            raise ValueError(
                "paper projection evidence must cover every assignment requiring the feature"
            )
        return {
            "feature": feature,
            "evidence_kind": "native_paper_projections",
            "evidence_level": "machine_verified",
            "covered_assignment_ids": sorted(covered_all),
            "projections": sorted(
                bindings, key=lambda item: item["projection_id"]
            ),
        }

    def _paper_ancestors(self, snapshot_id: str) -> set[str]:
        ancestors: set[str] = set()
        pending = [snapshot_id]
        while pending:
            current = pending.pop()
            if not current or current in ancestors:
                continue
            ancestors.add(current)
            manifest = self.store.paper_logic().snapshot_manifest(current)
            pending.extend(
                item
                for item in (
                    manifest.get("base_snapshot_id"),
                    manifest.get("supersedes_snapshot_id"),
                )
                if isinstance(item, str) and item
            )
        return ancestors

    def _validate_cross_feature_coherence(
        self,
        bindings: list[dict[str, Any]],
        *,
        view: dict[str, Any],
    ) -> None:
        by_feature = {item["feature"]: item for item in bindings}
        logic = by_feature.get("paper_logic_graph")
        audit = by_feature.get("paper_audit_graph")
        mirror = by_feature.get("full_fidelity_paper_mirror")
        logic_by_assignment: dict[str, dict[str, Any]] = {}
        if logic is not None:
            for snapshot in logic["snapshots"]:
                for assignment_id in snapshot["covered_assignment_ids"]:
                    logic_by_assignment[assignment_id] = snapshot
        audit_by_assignment: dict[str, dict[str, Any]] = {}
        if audit is not None:
            for snapshot in audit["snapshots"]:
                ancestors = self._paper_ancestors(snapshot["snapshot_id"])
                for assignment_id in snapshot["covered_assignment_ids"]:
                    logic_snapshot = logic_by_assignment.get(assignment_id)
                    if logic_snapshot is None:
                        raise ValueError(
                            "paper audit evidence lacks the assignment logic snapshot"
                        )
                    if (
                        snapshot["paper_id"] != logic_snapshot["paper_id"]
                        or logic_snapshot["snapshot_id"] not in ancestors
                    ):
                        raise ValueError(
                            "paper audit snapshot is not descended from the selected logic snapshot"
                        )
                    audit_by_assignment[assignment_id] = snapshot
        if mirror is not None:
            for projection in mirror["projections"]:
                for assignment_id in projection["covered_assignment_ids"]:
                    permitted = {
                        item["snapshot_id"]
                        for item in (
                            logic_by_assignment.get(assignment_id),
                            audit_by_assignment.get(assignment_id),
                        )
                        if item is not None
                    }
                    if projection["paper_snapshot_id"] not in permitted:
                        raise ValueError(
                            "paper mirror does not project the selected assignment Paper snapshot"
                        )

    def _experiment_binding(
        self,
        spec: dict[str, Any],
        *,
        view: dict[str, Any],
    ) -> dict[str, Any]:
        feature = "computation_exploration_lane"
        require_exact_keys(
            spec,
            required={"feature", "evidence_kind", "experiments"},
            label=f"profile closure evidence {feature}",
        )
        if spec.get("evidence_kind") != "native_finalized_experiments":
            raise ValueError(f"{feature} requires native finalized experiments")
        experiments = spec.get("experiments")
        if not isinstance(experiments, list) or not experiments:
            raise ValueError("computation exploration evidence must be nonempty")
        bindings: list[dict[str, str]] = []
        for index, item in enumerate(experiments, 1):
            if not isinstance(item, dict):
                raise ValueError("experiment evidence entry must be one object")
            require_exact_keys(
                item,
                required={"assignment_id", "experiment_id"},
                label=f"experiment evidence {index}",
            )
            assignment_id = validate_assignment_id(
                require_string(item, "assignment_id")
            )
            if assignment_id not in view["assignments"]:
                raise ValueError("experiment evidence assignment belongs to another round")
            task_path = (
                self.store.rounds_dir
                / view["round_id"]
                / "task-cards"
                / f"{assignment_id}.json"
            )
            card = self.store._read_json(task_path)
            experiment_id = require_string(item, "experiment_id")
            receipt_path = (
                contained_path(
                    self.store.root,
                    require_string(card, "work_dir_relpath"),
                    "experiment work directory",
                )
                / "experiments"
                / experiment_id
                / "final_receipt.json"
            )
            receipt = validate_experiment_final_receipt(
                project_root=self.store.root,
                task_card=card,
                receipt_path=receipt_path,
            )
            bindings.append(
                {
                    "assignment_id": assignment_id,
                    "experiment_id": experiment_id,
                    "receipt_sha256": receipt["receipt_sha256"],
                    "receipt_file_sha256": sha256_bytes(receipt_path.read_bytes()),
                }
            )
        covered = sorted({item["assignment_id"] for item in bindings})
        if covered != self._required_assignments(view, feature):
            raise ValueError(
                "experiment evidence must cover every assignment requiring the feature"
            )
        return {
            "feature": feature,
            "evidence_kind": "native_finalized_experiments",
            "evidence_level": "machine_verified",
            "covered_assignment_ids": covered,
            "experiments": sorted(
                bindings,
                key=lambda item: (item["assignment_id"], item["experiment_id"]),
            ),
        }

    def _novelty_binding(
        self,
        spec: dict[str, Any],
        *,
        view: dict[str, Any],
    ) -> dict[str, Any]:
        feature = "novelty_search_lane"
        require_exact_keys(
            spec,
            required={"feature", "evidence_kind", "event_ids"},
            label=f"profile closure evidence {feature}",
        )
        if spec.get("evidence_kind") != "native_novelty_records":
            raise ValueError(f"{feature} requires native novelty records")
        event_ids = spec.get("event_ids")
        if (
            not isinstance(event_ids, list)
            or not event_ids
            or event_ids != sorted(set(event_ids))
            or any(
                not isinstance(item, str) or SHA256_RE.fullmatch(item) is None
                for item in event_ids
            )
        ):
            raise ValueError("novelty evidence event_ids are invalid")
        events = {
            event.get("event_id"): event
            for event in self.store._read_jsonl(self.store.novelty_log)
        }
        selected = [events.get(event_id) for event_id in event_ids]
        if any(event is None for event in selected):
            raise ValueError("novelty evidence references a missing event")
        round_created_at = _parse_utc_timestamp(
            view["round_created_at"], label="profile closure round created_at"
        )
        if any(
            _parse_utc_timestamp(
                event.get("searched_at"),
                label="novelty event searched_at",
            )
            < round_created_at
            for event in selected
            if isinstance(event, dict)
        ):
            raise ValueError("novelty event predates the governed round")
        covered = sorted(
            assignment_id
            for assignment_id in self._required_assignments(view, feature)
            if any(
                isinstance(event, dict)
                and event.get("subject_kind") == "memory"
                and event.get("subject_id")
                == view["assignment_contexts"][assignment_id]["memory_id"]
                for event in selected
            )
        )
        if covered != self._required_assignments(view, feature):
            raise ValueError(
                "novelty evidence must cover every assignment requiring the feature"
            )
        return {
            "feature": feature,
            "evidence_kind": "native_novelty_records",
            "evidence_level": "machine_verified",
            "covered_assignment_ids": covered,
            "event_ids": event_ids,
            "events_sha256": sha256_json(selected),
        }

    def _synthesis_binding(
        self,
        spec: dict[str, Any],
        *,
        view: dict[str, Any],
    ) -> dict[str, Any]:
        feature = "expert_synthesis_pass"
        require_exact_keys(
            spec,
            required={"feature", "evidence_kind", "receipts"},
            label=f"profile closure evidence {feature}",
        )
        if spec.get("evidence_kind") != "native_lint_receipts":
            raise ValueError(f"{feature} requires native lint receipts")
        refs = spec.get("receipts")
        if not isinstance(refs, list) or not refs:
            raise ValueError("expert synthesis receipt list must be nonempty")
        bindings: list[dict[str, Any]] = []
        for index, ref in enumerate(refs, 1):
            if not isinstance(ref, dict):
                raise ValueError("lint evidence entry must be one object")
            require_exact_keys(
                ref,
                required={
                    "assignment_id",
                    "receipt",
                    "draft",
                    "card",
                    "scope",
                },
                label=f"lint evidence {index}",
            )
            assignment_id = validate_assignment_id(
                require_string(ref, "assignment_id")
            )
            if assignment_id not in view["assignments"]:
                raise ValueError("lint evidence assignment belongs to another round")
            receipt_artifact = self._artifact(
                ref["receipt"],
                label=f"lint receipt {index}",
                allowed_prefixes=(
                    "reports/expert-lint-receipts/",
                    "reports/interpret-lint-receipts/",
                ),
            )
            draft_artifact = self._artifact(
                ref["draft"],
                label=f"lint draft {index}",
                allowed_prefixes=("reports/",),
            )
            card_artifact = self._artifact(
                ref["card"],
                label=f"lint card {index}",
                allowed_prefixes=("reports/",),
            )
            path = contained_path(
                self.store.root,
                receipt_artifact["relpath"],
                "lint receipt",
            )
            receipt = self.store._read_json(path)
            draft_path = contained_path(
                self.store.root, draft_artifact["relpath"], "lint draft"
            )
            card_path = contained_path(
                self.store.root, card_artifact["relpath"], "lint card"
            )
            if receipt_artifact["relpath"].startswith(
                "reports/expert-lint-receipts/"
            ):
                validated = validate_expert_lint_receipt(
                    receipt,
                    draft_bytes=draft_path.read_bytes(),
                    claim_card_bytes=card_path.read_bytes(),
                )
            elif receipt_artifact["relpath"].startswith(
                "reports/interpret-lint-receipts/"
            ):
                if receipt.get("interpret_card_relpath") != card_artifact[
                    "relpath"
                ]:
                    raise ValueError("interpret lint evidence card path mismatch")
                validated = validate_interpret_lint_receipt(
                    receipt,
                    draft_bytes=draft_path.read_bytes(),
                    interpret_card_bytes=card_path.read_bytes(),
                )
            else:
                raise ValueError("expert synthesis evidence is not a native lint receipt")
            if validated.get("project_id") != self.store.project_id() or not validated.get(
                "ok"
            ):
                raise ValueError("expert synthesis lint receipt is not current and passing")
            subject_binding = self._subject_bindings(view)[assignment_id]
            scope_artifact = self._synthesis_scope_artifact(
                ref["scope"],
                assignment_id=assignment_id,
                receipt=receipt_artifact,
                draft=draft_artifact,
                card=card_artifact,
                lint_receipt_sha256=validated["lint_receipt_sha256"],
                subject_binding=subject_binding,
                view=view,
                index=index,
            )
            bindings.append(
                {
                    "assignment_id": assignment_id,
                    "receipt": receipt_artifact,
                    "draft": draft_artifact,
                    "card": card_artifact,
                    "scope": scope_artifact,
                    "lint_receipt_sha256": validated[
                        "lint_receipt_sha256"
                    ],
                    "subject_binding": subject_binding,
                }
            )
        covered = sorted({item["assignment_id"] for item in bindings})
        if covered != self._required_assignments(view, feature):
            raise ValueError(
                "expert synthesis evidence must cover every assignment requiring the feature"
            )
        return {
            "feature": feature,
            "evidence_kind": "native_lint_receipts",
            "evidence_level": "mixed_procedural_and_machine_verified",
            "lint_receipt_level": "machine_verified",
            "assignment_scope_level": _HOST_EVIDENCE_LEVEL,
            "covered_assignment_ids": covered,
            "receipts": sorted(
                bindings,
                key=lambda item: item["receipt"]["relpath"],
            ),
        }

    def _synthesis_scope_artifact(
        self,
        payload: Any,
        *,
        assignment_id: str,
        receipt: dict[str, str],
        draft: dict[str, str],
        card: dict[str, str],
        lint_receipt_sha256: str,
        subject_binding: dict[str, Any],
        view: dict[str, Any],
        index: int,
    ) -> dict[str, str]:
        label = f"lint assignment scope {index}"
        artifact = self._artifact(
            payload,
            label=label,
            allowed_prefixes=("reports/profile-closure-evidence/",),
        )
        path = contained_path(self.store.root, artifact["relpath"], label)
        try:
            content = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"{label} must be canonical JSON evidence") from exc
        expected = {
            "schema_version": 1,
            "feature": "expert_synthesis_pass",
            "project_id": self.store.project_id(),
            "round_id": view["round_id"],
            "round_created_at": view["round_created_at"],
            "assignment_id": assignment_id,
            "host_task_scope_id": view["host_task_scope_id"],
            "task_card_sha256": subject_binding["task_card_sha256"],
            "return_sha256": subject_binding["return_sha256"],
            "ingestion_sha256": subject_binding["ingestion_sha256"],
            "outcome": subject_binding["outcome"],
            "effect": subject_binding["effect"],
            "lint_receipt_file_sha256": receipt["sha256"],
            "lint_receipt_sha256": lint_receipt_sha256,
            "draft_sha256": draft["sha256"],
            "card_sha256": card["sha256"],
        }
        if content != expected:
            raise ValueError(
                "expert synthesis scope does not bind the current assignment subject"
            )
        return artifact

    def _materialize(
        self,
        spec: Any,
        *,
        view: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(spec, dict):
            raise ValueError("profile closure evidence must be one object")
        feature = require_string(spec, "feature")
        if feature not in EXPLORATION_FEATURES:
            raise ValueError("profile closure evidence feature is invalid")
        if feature in _PULSE_FEATURES:
            return self._pulse_binding(spec, feature=feature, view=view)
        if feature == "orthogonal_specialist_escalation":
            return self._specialist_binding(spec, view=view)
        if feature == "long_horizon_campaign_expansion":
            return self._campaign_binding(spec, view=view)
        if feature in _PAPER_SNAPSHOT_FEATURES:
            return self._paper_snapshot_binding(
                spec,
                feature=feature,
                view=view,
            )
        if feature == "full_fidelity_paper_mirror":
            return self._mirror_binding(spec, view=view)
        if feature == "computation_exploration_lane":
            return self._experiment_binding(spec, view=view)
        if feature == "novelty_search_lane":
            return self._novelty_binding(spec, view=view)
        if feature == "expert_synthesis_pass":
            return self._synthesis_binding(spec, view=view)
        raise ValueError(f"no profile closure evidence validator for {feature}")

    def _materialize_all(
        self,
        specs: Any,
        *,
        view: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if not isinstance(specs, list):
            raise ValueError("profile closure evidence must be a list")
        features = [
            require_string(spec, "feature") if isinstance(spec, dict) else ""
            for spec in specs
        ]
        if len(set(features)) != len(features):
            raise ValueError("profile closure evidence features must be unique")
        if set(features) != set(view["required_features"]):
            missing = sorted(set(view["required_features"]).difference(features))
            extra = sorted(set(features).difference(view["required_features"]))
            raise ValueError(
                "profile closure evidence must cover exactly required features; "
                f"missing={missing} extra={extra}"
            )
        bindings = sorted(
            (self._materialize(spec, view=view) for spec in specs),
            key=lambda item: item["feature"],
        )
        self._validate_cross_feature_coherence(bindings, view=view)
        return bindings

    def _subject_bindings(
        self,
        view: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        receipts = self.store._v4_ingestion_receipts()
        bindings: dict[str, dict[str, Any]] = {}
        for assignment_id, assignment in view["assignments"].items():
            matches = [
                receipt
                for receipt in receipts
                if receipt["round_id"] == view["round_id"]
                and receipt["assignment_id"] == assignment_id
            ]
            if len(matches) != 1:
                raise ValueError(
                    "profile closure requires exactly one canonical ingestion "
                    f"receipt for assignment {assignment_id}"
                )
            receipt = matches[0]
            effect = receipt.get("effect")
            if not isinstance(effect, dict) or not effect:
                raise ValueError("profile closure ingestion effect is empty")
            bindings[assignment_id] = {
                "execution_profile_sha256": assignment[
                    "execution_profile_sha256"
                ],
                "assignment_sha256": view["assignment_contexts"][assignment_id][
                    "assignment_sha256"
                ],
                "task_card_sha256": view["assignment_contexts"][assignment_id][
                    "task_card_sha256"
                ],
                "return_sha256": receipt["return_sha256"],
                "ingestion_sha256": receipt["ingestion_sha256"],
                "outcome": receipt["outcome"],
                "effect": effect,
            }
        return dict(sorted(bindings.items()))

    def record(
        self,
        round_id: str,
        payload: Any,
        *,
        actor: str,
    ) -> dict[str, Any]:
        with self.store.mutation_lock():
            return self._record_locked(
                round_id,
                payload,
                actor=actor,
            )

    def _record_locked(
        self,
        round_id: str,
        payload: Any,
        *,
        actor: str,
    ) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("profile closure input must be one object")
        require_exact_keys(
            payload,
            required={"evidence"},
            label="profile closure input",
        )
        actor = require_string({"actor": actor}, "actor")
        view = self.obligation_view(round_id)
        if not view["required_features"]:
            raise ValueError("round has no required exploration features to close")
        specs = payload["evidence"]
        bindings = self._materialize_all(specs, view=view)
        subject_bindings = self._subject_bindings(view)
        semantic = {
            "schema_version": PROFILE_CLOSURE_SCHEMA_VERSION,
            "policy_revision": UNIFIED_POLICY_REVISION,
            "project_id": self.store.project_id(),
            "round_id": view["round_id"],
            "round_created_at": view["round_created_at"],
            "reasoning_mode": view["reasoning_mode"],
            "reasoning_mode_event_id": view["reasoning_mode_event_id"],
            "profile_obligations_sha256": view["obligations_sha256"],
            "round_manifest_sha256": view["round_manifest_sha256"],
            "assignment_profiles": view["assignments"],
            "feature_statuses": view["feature_statuses"],
            "required_features": view["required_features"],
            "evidence": specs,
            "evidence_bindings": bindings,
            "subject_bindings": subject_bindings,
            "actor": actor,
            "recorded_at": _utc_now(),
            "truth_effect": "workflow_readiness_only",
        }
        receipt = {
            **semantic,
            "closure_id": PROFILE_CLOSURE_PREFIX + sha256_json(semantic),
        }
        path = self._path(round_id)
        self.store._write_json_once(path, receipt)
        return {
            **receipt,
            "receipt_relpath": path.relative_to(self.store.root).as_posix(),
            "receipt_sha256": sha256_bytes(path.read_bytes()),
        }

    def validate_receipt(self, round_id: str) -> dict[str, Any]:
        path = self._path(round_id)
        if path.is_symlink() or not path.is_file():
            raise ValueError("required profile closure receipt is missing or unsafe")
        receipt = self.store._read_json(path)
        require_exact_keys(
            receipt,
            required={
                "schema_version",
                "policy_revision",
                "project_id",
                "round_id",
                "round_created_at",
                "reasoning_mode",
                "reasoning_mode_event_id",
                "profile_obligations_sha256",
                "round_manifest_sha256",
                "assignment_profiles",
                "feature_statuses",
                "required_features",
                "evidence",
                "evidence_bindings",
                "subject_bindings",
                "actor",
                "recorded_at",
                "truth_effect",
                "closure_id",
            },
            label="profile closure receipt",
        )
        semantic = {
            key: value for key, value in receipt.items() if key != "closure_id"
        }
        if (
            receipt.get("schema_version") != PROFILE_CLOSURE_SCHEMA_VERSION
            or receipt.get("policy_revision") != UNIFIED_POLICY_REVISION
            or receipt.get("project_id") != self.store.project_id()
            or receipt.get("round_id") != round_id
            or receipt.get("truth_effect") != "workflow_readiness_only"
            or receipt.get("closure_id")
            != PROFILE_CLOSURE_PREFIX + sha256_json(semantic)
        ):
            raise ValueError("profile closure receipt header/hash mismatch")
        view = self.obligation_view(round_id)
        for key in (
            "reasoning_mode",
            "reasoning_mode_event_id",
            "round_created_at",
            "feature_statuses",
            "required_features",
        ):
            if receipt.get(key) != view[key]:
                raise ValueError(f"profile closure receipt {key} mismatch")
        if receipt.get("profile_obligations_sha256") != view[
            "obligations_sha256"
        ]:
            raise ValueError("profile closure obligation hash mismatch")
        if receipt.get("round_manifest_sha256") != view[
            "round_manifest_sha256"
        ] or receipt.get("assignment_profiles") != view["assignments"]:
            raise ValueError("profile closure round/profile binding mismatch")
        bindings = self._materialize_all(receipt["evidence"], view=view)
        if receipt.get("evidence_bindings") != bindings:
            raise ValueError("profile closure native evidence binding drift")
        if receipt.get("subject_bindings") != self._subject_bindings(view):
            raise ValueError("profile closure ingestion/subject binding drift")
        require_string(receipt, "actor")
        require_string(receipt, "recorded_at")
        return {
            **receipt,
            "receipt_relpath": path.relative_to(self.store.root).as_posix(),
            "receipt_sha256": sha256_bytes(path.read_bytes()),
        }

    def status(self, round_id: str) -> dict[str, Any]:
        view = self.obligation_view(round_id)
        if not view["required_features"]:
            return {
                **view,
                "state": "not_required",
                "closed": True,
                "truth_effect": "workflow_readiness_only",
            }
        path = self._path(round_id)
        if not path.exists():
            return {
                **view,
                "state": "blocked_missing_closure",
                "closed": False,
                "missing_features": view["required_features"],
                "truth_effect": "workflow_readiness_only",
            }
        receipt = self.validate_receipt(round_id)
        return {
            **view,
            "state": "closed",
            "closed": True,
            "closure_id": receipt["closure_id"],
            "receipt_sha256": receipt["receipt_sha256"],
            "subject_bindings": receipt["subject_bindings"],
            "truth_effect": "workflow_readiness_only",
        }

    def require_submission_ready(self, submission: dict[str, Any]) -> dict[str, Any]:
        mode_status = self.store.reasoning_modes().status()
        if not mode_status.get("initialized"):
            if self.store.reasoning_modes().is_historical_accepted_submission(
                submission
            ):
                return {
                    "state": "historical_chalk_v4_read_only_baseline",
                    "required_features": [],
                    "closed": True,
                }
            raise ValueError(
                "legacy Chalk V4 submission is not closure-ready before "
                "mode-init"
            )
        if self.store.reasoning_modes().is_historical_accepted_submission(
            submission
        ):
            return {
                "state": "historical_chalk_v4_activation_baseline",
                "required_features": [],
                "closed": True,
            }
        round_id = submission.get("round_id")
        assignment_id = submission.get("assignment_id")
        if not isinstance(round_id, str) or ROUND_ID_RE.fullmatch(round_id) is None:
            raise ValueError(
                "unified V4 submission requires a profile-bound round before verification"
            )
        assignment_id = validate_assignment_id(str(assignment_id))
        return self.require_round_assignment_ready(
            round_id,
            assignment_id,
            expected_outcome="fact_submission",
            expected_effect_key="submission_id",
            expected_subject_id=str(
                submission.get("submission_id") or submission.get("fact_id")
            ),
        )

    def require_round_assignment_ready(
        self,
        round_id: str,
        assignment_id: str,
        *,
        expected_outcome: str | None = None,
        expected_effect_key: str | None = None,
        expected_subject_id: str | None = None,
    ) -> dict[str, Any]:
        round_id = validate_round_id(round_id)
        assignment_id = validate_assignment_id(assignment_id)
        status = self.status(round_id)
        if assignment_id not in status["assignments"]:
            raise ValueError("submission assignment is outside its profile-bound round")
        if not status["closed"]:
            raise ValueError(
                "required exploration profile is not closed: "
                + ", ".join(status["missing_features"])
            )
        if expected_outcome is not None:
            subject_bindings = status.get("subject_bindings")
            if not isinstance(subject_bindings, dict):
                subject_bindings = self._subject_bindings(status)
            subject = subject_bindings.get(assignment_id)
            if (
                not isinstance(subject, dict)
                or subject.get("outcome") != expected_outcome
                or not isinstance(expected_effect_key, str)
                or subject.get("effect", {}).get(expected_effect_key)
                != expected_subject_id
            ):
                raise ValueError(
                    "profile closure is not bound to the requested submission subject"
                )
        return status

    def audit(self) -> dict[str, Any]:
        errors: list[str] = []
        warnings: list[str] = []
        blocked_rounds: list[str] = []
        receipts = 0
        if self.root.exists():
            for path in sorted(self.root.glob("*.json")):
                try:
                    if path.is_symlink() or not path.is_file():
                        raise ValueError("receipt is not a regular file")
                    round_id = path.stem
                    validate_round_id(round_id)
                    self.validate_receipt(round_id)
                    receipts += 1
                except Exception as exc:
                    errors.append(f"{path.name}: {exc}")
        for path in sorted(self.store.rounds_dir.glob("*/round.json")):
            try:
                manifest = self.store._read_json(path)
                if manifest.get("schema_version") != 4 or "reasoning_mode" not in manifest:
                    continue
                view = self.obligation_view(path.parent.name)
                if (
                    view["required_features"]
                    and not self._path(path.parent.name).is_file()
                ):
                    blocked_rounds.append(path.parent.name)
                    warnings.append(
                        f"{path.parent.name}: required exploration profile is still open"
                    )
            except Exception as exc:
                errors.append(f"round {path.parent.name}: {exc}")
        for path in sorted(self.store.submissions_dir.glob("*.json")):
            try:
                submission = self.store._read_json(path)
                if (
                    submission.get("evidence_version") == 4
                    and submission.get("status") in {"accepted", "revoked"}
                ):
                    self.require_submission_ready(submission)
            except Exception as exc:
                errors.append(f"accepted submission {path.name}: {exc}")
        return {
            "ok": not errors,
            "errors": errors,
            "warnings": warnings,
            "blocked_rounds": blocked_rounds,
            "receipts": receipts,
            "truth_effect": "workflow_readiness_only",
        }

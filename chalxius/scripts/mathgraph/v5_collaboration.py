from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, ContextManager

from .collaboration import FRESH_CONTEXT_CONTRACT_V1
from .contracts import (
    SHA256_RE,
    sha256_bytes,
    sha256_json,
    validate_assignment_id,
    validate_memory_id,
    validate_round_id,
)
from .v5_lifecycle import V5_POLICY_REVISION


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    return value.strip()


class V5PulseStore:
    """Optional two-wave coordination over cumulative V5 Research.

    Pulse records are control-plane evidence only.  They never close a round,
    invalidate a peer contribution, or authorize Fact admission.  Each worker
    return is still ingested or quarantined independently by the V5 lifecycle.
    """

    def __init__(
        self,
        store: Any,
        *,
        mutation_lock: Callable[[], ContextManager[Any]],
        trusted_host_issuers: tuple[str, ...] = (),
    ) -> None:
        self.store = store
        self.project_root = Path(store.root).resolve()
        self.root = self.project_root / "governance" / "v5" / "pulses" / "by-id"
        self._mutation_lock = mutation_lock
        self.trusted_host_issuers = tuple(sorted(set(trusted_host_issuers)))

    def _write_record(
        self,
        *,
        prefix: str,
        id_field: str,
        semantic: dict[str, Any],
        path_for_id: Callable[[str], Path],
    ) -> dict[str, Any]:
        identifier = prefix + sha256_json(semantic)
        path = path_for_id(identifier)
        if path.exists():
            existing = self._read_record(path, prefix=prefix, id_field=id_field)
            if existing[id_field] != identifier:
                raise ValueError("immutable V5 pulse record collision")
            return existing
        without_hash = {
            **semantic,
            id_field: identifier,
            "created_at": _utc_now(),
        }
        record = {
            **without_hash,
            "record_sha256": sha256_json(without_hash),
        }
        self.store._write_json_once(path, record)
        return record

    def _read_record(
        self,
        path: Path,
        *,
        prefix: str,
        id_field: str,
    ) -> dict[str, Any]:
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"missing or unsafe V5 pulse record: {path}")
        record = self.store._read_json(path)
        identifier = record.get(id_field)
        if not isinstance(identifier, str) or not identifier.startswith(prefix):
            raise ValueError("V5 pulse record id is invalid")
        without_hash = {
            key: value for key, value in record.items() if key != "record_sha256"
        }
        if record.get("record_sha256") != sha256_json(without_hash):
            raise ValueError("V5 pulse record hash mismatch")
        semantic = {
            key: value
            for key, value in record.items()
            if key not in {id_field, "created_at", "record_sha256"}
        }
        if identifier != prefix + sha256_json(semantic):
            raise ValueError("V5 pulse content id mismatch")
        if (
            record.get("schema_version") != 5
            or record.get("policy_revision") != V5_POLICY_REVISION
            or record.get("project_id") != self.store.project_id()
        ):
            raise ValueError("V5 pulse record schema/policy/project mismatch")
        return record

    def _pulse_dir(self, pulse_id: str) -> Path:
        if not isinstance(pulse_id, str) or not pulse_id.startswith("v5pulse-"):
            raise ValueError("invalid V5 pulse id")
        digest = pulse_id.removeprefix("v5pulse-")
        if SHA256_RE.fullmatch(digest) is None:
            raise ValueError("invalid V5 pulse id")
        return self.root / pulse_id

    def _plan(self, pulse_id: str) -> dict[str, Any]:
        return self._read_record(
            self._pulse_dir(pulse_id) / "plan.json",
            prefix="v5pulse-",
            id_field="pulse_id",
        )

    def _barrier(self, pulse_id: str, *, required: bool = False) -> dict[str, Any] | None:
        path = self._pulse_dir(pulse_id) / "barrier.json"
        if not path.exists() and not required:
            return None
        return self._read_record(path, prefix="v5bar-", id_field="barrier_id")

    def _assignment(self, round_id: str, assignment_id: str) -> dict[str, Any]:
        _, manifest = self.store.v5_lifecycle()._round_manifest(
            validate_round_id(round_id)
        )
        return self.store.v5_lifecycle()._assignment(
            manifest, validate_assignment_id(assignment_id)
        )

    def make_wave1_commitment(
        self,
        *,
        round_id: str,
        assignment_id: str,
        criticality: str = "core",
        minimum_peer_nodes: int = 1,
    ) -> dict[str, Any]:
        self.store.reasoning_modes().require_work_unit_active(round_id)
        if criticality not in {"core", "optional"}:
            raise ValueError("V5 pulse criticality must be core or optional")
        if (
            isinstance(minimum_peer_nodes, bool)
            or not isinstance(minimum_peer_nodes, int)
            or minimum_peer_nodes < 1
        ):
            raise ValueError("minimum_peer_nodes must be positive")
        assignment = self._assignment(round_id, assignment_id)
        if (
            assignment["blackboard_snapshot_id"] is None
            or assignment["blackboard_snapshot_sha256"] is None
        ):
            raise ValueError(
                "V5 Pulse compatibility requires a round with an explicitly "
                "bound Blackboard snapshot"
            )
        semantic = {
            "phase": "wave1",
            "project_id": self.store.project_id(),
            "round_id": round_id,
            "assignment_id": assignment_id,
            "task_card_sha256": assignment["task_card_sha256"],
            "snapshot_id": assignment["blackboard_snapshot_id"],
            "snapshot_sha256": assignment["blackboard_snapshot_sha256"],
            "criticality": criticality,
            "minimum_peer_nodes": minimum_peer_nodes,
        }
        return {**semantic, "commitment_id": "v5pc-" + sha256_json(semantic)}

    def make_review_commitment(
        self,
        *,
        pulse_id: str,
        round_id: str,
        assignment_id: str,
        peer_node_id: str,
        criticality: str = "core",
        allowed_edge_types: list[str] | None = None,
        peer_project_id: str | None = None,
    ) -> dict[str, Any]:
        self._plan(pulse_id)
        self.store.reasoning_modes().require_work_unit_active(round_id)
        if criticality not in {"core", "optional"}:
            raise ValueError("V5 pulse criticality must be core or optional")
        if peer_project_id not in {None, self.store.project_id()}:
            raise ValueError("V5 pulse review peers must remain project-local")
        peer_research_id = validate_memory_id(peer_node_id)
        self.store.v5_lifecycle()._research_record(peer_research_id)
        assignment = self._assignment(round_id, assignment_id)
        if (
            assignment["blackboard_snapshot_id"] is None
            or assignment["blackboard_snapshot_sha256"] is None
        ):
            raise ValueError(
                "V5 Pulse compatibility requires a round with an explicitly "
                "bound Blackboard snapshot"
            )
        card = self.store._read_json(
            self.project_root / assignment["task_card_relpath"]
        )
        self.store.v5_lifecycle().validate_task_card(card)
        context_ids = {
            item["research_id"]
            for item in card["mathematical_state"]["research_context"]
        }
        if peer_research_id not in context_ids:
            raise ValueError(
                "V5 Wave-2 task card does not bind the peer Research entry"
            )
        allowed = sorted(set(allowed_edge_types or ["challenges", "refines"]))
        if not allowed or any(
            item not in {"challenges", "refines", "duplicates", "supports_candidate"}
            for item in allowed
        ):
            raise ValueError("V5 pulse review edge types are invalid")
        semantic = {
            "phase": "wave2",
            "pulse_id": pulse_id,
            "project_id": self.store.project_id(),
            "round_id": round_id,
            "assignment_id": assignment_id,
            "task_card_sha256": assignment["task_card_sha256"],
            "snapshot_id": assignment["blackboard_snapshot_id"],
            "snapshot_sha256": assignment["blackboard_snapshot_sha256"],
            "peer_node_id": peer_research_id,
            "peer_research_sha256": self.store.v5_lifecycle()._research_record(
                peer_research_id
            )["record_sha256"],
            "criticality": criticality,
            "allowed_edge_types": allowed,
        }
        return {**semantic, "commitment_id": "v5pc-" + sha256_json(semantic)}

    @staticmethod
    def _validate_unique_commitments(commitments: list[dict[str, Any]]) -> None:
        ids = [item.get("commitment_id") for item in commitments]
        assignments = [
            (item.get("round_id"), item.get("assignment_id"))
            for item in commitments
        ]
        if len(ids) != len(set(ids)) or len(assignments) != len(set(assignments)):
            raise ValueError("V5 pulse commitments must be unique")

    def create_plan(
        self,
        *,
        wave1_commitments: list[dict[str, Any]],
        minimum_wave1_contributors: int,
        actor: str,
    ) -> dict[str, Any]:
        if not self.trusted_host_issuers:
            raise ValueError(
                "V5 pulse-plan requires a configured trusted host before writing"
            )
        if not wave1_commitments or any(
            item.get("phase") != "wave1" for item in wave1_commitments
        ):
            raise ValueError("V5 pulse plan requires Wave-1 commitments")
        self._validate_unique_commitments(wave1_commitments)
        if (
            isinstance(minimum_wave1_contributors, bool)
            or not isinstance(minimum_wave1_contributors, int)
            or not 1 <= minimum_wave1_contributors <= len(wave1_commitments)
        ):
            raise ValueError("minimum Wave-1 contributors is invalid")
        snapshots = {
            (item["snapshot_id"], item["snapshot_sha256"])
            for item in wave1_commitments
        }
        if len(snapshots) != 1:
            raise ValueError("all V5 Wave-1 assignments must share one snapshot")
        snapshot_id, snapshot_sha = next(iter(snapshots))
        semantic = {
            "schema_version": 5,
            "policy_revision": V5_POLICY_REVISION,
            "project_id": self.store.project_id(),
            "actor": _text(actor, "pulse actor"),
            "wave1_snapshot_id": snapshot_id,
            "wave1_snapshot_sha256": snapshot_sha,
            "minimum_wave1_contributors": minimum_wave1_contributors,
            "wave1_commitments": sorted(
                wave1_commitments, key=lambda item: item["commitment_id"]
            ),
            "trusted_host_issuers": list(self.trusted_host_issuers),
            "truth_effect": "none",
            "failure_policy": "local_quarantine_existing_contributions_survive",
        }
        with self._mutation_lock():
            return self._write_record(
                prefix="v5pulse-",
                id_field="pulse_id",
                semantic=semantic,
                path_for_id=lambda identifier: self._pulse_dir(identifier) / "plan.json",
            )

    def _receipt_for(self, commitment: dict[str, Any]) -> dict[str, Any] | None:
        path = (
            self.project_root
            / "rounds"
            / commitment["round_id"]
            / "returns"
            / f"{commitment['assignment_id']}.receipt.json"
        )
        if not path.exists():
            return None
        if path.is_symlink() or not path.is_file():
            raise ValueError("V5 pulse references an unsafe ingestion receipt")
        receipt = self.store._read_json(path)
        if (
            receipt.get("round_id") != commitment["round_id"]
            or receipt.get("assignment_id") != commitment["assignment_id"]
            or receipt.get("task_card_sha256") != commitment["task_card_sha256"]
        ):
            raise ValueError("V5 pulse ingestion receipt binding mismatch")
        self.store.v5_lifecycle()._research_record(receipt["research_id"])
        return receipt

    def derive_barrier(
        self,
        pulse_id: str,
        *,
        after_snapshot_id: str,
        review_commitments: list[dict[str, Any]],
        actor: str,
    ) -> dict[str, Any]:
        plan = self._plan(pulse_id)
        if not review_commitments or any(
            item.get("phase") != "wave2" or item.get("pulse_id") != pulse_id
            for item in review_commitments
        ):
            raise ValueError("V5 pulse barrier requires bound Wave-2 commitments")
        self._validate_unique_commitments(review_commitments)
        evidence = []
        for commitment in plan["wave1_commitments"]:
            receipt = self._receipt_for(commitment)
            if receipt is not None:
                research = self.store.v5_lifecycle()._research_record(
                    receipt["research_id"]
                )
                evidence.append(
                    {
                        "commitment_id": commitment["commitment_id"],
                        "research_id": research["research_id"],
                        "research_sha256": research["record_sha256"],
                        "return_sha256": receipt["return_sha256"],
                    }
                )
        if len(evidence) < plan["minimum_wave1_contributors"]:
            raise ValueError(
                "V5 pulse barrier lacks the minimum independently ingested Wave-1 contributions"
            )
        peer_ids = {item["research_id"] for item in evidence}
        if any(item["peer_node_id"] not in peer_ids for item in review_commitments):
            raise ValueError("V5 Wave-2 commitment targets unbound Wave-1 Research")
        snapshot_path = (
            self.store.blackboard().snapshots_dir
            / after_snapshot_id
            / "manifest.json"
        )
        self.store.blackboard().snapshot_manifest(after_snapshot_id)
        after_sha = sha256_bytes(snapshot_path.read_bytes())
        if any(
            item["snapshot_id"] != after_snapshot_id
            or item["snapshot_sha256"] != after_sha
            for item in review_commitments
        ):
            raise ValueError("V5 Wave-2 assignments do not share the barrier snapshot")
        semantic = {
            "schema_version": 5,
            "policy_revision": V5_POLICY_REVISION,
            "project_id": self.store.project_id(),
            "pulse_id": pulse_id,
            "plan_sha256": plan["record_sha256"],
            "actor": _text(actor, "barrier actor"),
            "after_snapshot_id": after_snapshot_id,
            "after_snapshot_sha256": after_sha,
            "wave1_evidence": sorted(evidence, key=lambda item: item["commitment_id"]),
            "review_commitments": sorted(
                review_commitments, key=lambda item: item["commitment_id"]
            ),
            "truth_effect": "none",
        }
        with self._mutation_lock():
            return self._write_record(
                prefix="v5bar-",
                id_field="barrier_id",
                semantic=semantic,
                path_for_id=lambda _identifier: self._pulse_dir(pulse_id)
                / "barrier.json",
            )

    def void_optional(
        self,
        pulse_id: str,
        commitment_id: str,
        *,
        reason: str,
        actor: str,
    ) -> dict[str, Any]:
        plan = self._plan(pulse_id)
        barrier = self._barrier(pulse_id)
        commitments = list(plan["wave1_commitments"])
        if barrier is not None:
            commitments.extend(barrier["review_commitments"])
        matches = [item for item in commitments if item["commitment_id"] == commitment_id]
        if len(matches) != 1 or matches[0]["criticality"] != "optional":
            raise ValueError("only one optional V5 pulse commitment may be voided")
        semantic = {
            "schema_version": 5,
            "policy_revision": V5_POLICY_REVISION,
            "project_id": self.store.project_id(),
            "pulse_id": pulse_id,
            "commitment_id": commitment_id,
            "reason": _text(reason, "void reason"),
            "actor": _text(actor, "void actor"),
            "effect": "future_coordination_only_existing_research_preserved",
        }
        with self._mutation_lock():
            return self._write_record(
                prefix="v5void-",
                id_field="void_id",
                semantic=semantic,
                path_for_id=lambda identifier: self._pulse_dir(pulse_id)
                / "voids"
                / f"{identifier}.json",
            )

    def abort(
        self,
        pulse_id: str,
        *,
        failure_phase: str,
        reason: str,
        actor: str,
    ) -> dict[str, Any]:
        plan = self._plan(pulse_id)
        semantic = {
            "schema_version": 5,
            "policy_revision": V5_POLICY_REVISION,
            "project_id": self.store.project_id(),
            "pulse_id": pulse_id,
            "plan_sha256": plan["record_sha256"],
            "failure_phase": _text(failure_phase, "failure phase"),
            "reason": _text(reason, "stop reason"),
            "actor": _text(actor, "stop actor"),
            "effect": "stop_future_dispatch_only_existing_research_preserved",
            "truth_effect": "none",
        }
        with self._mutation_lock():
            return self._write_record(
                prefix="v5stop-",
                id_field="stop_id",
                semantic=semantic,
                path_for_id=lambda _identifier: self._pulse_dir(pulse_id) / "stop.json",
            )

    def record_host_dispatch(
        self,
        pulse_id: str,
        commitment_id: str,
        *,
        issuer: str,
        host_context_id: str,
        agent_identity: str,
        fresh_context_contract: dict[str, Any],
    ) -> dict[str, Any]:
        plan = self._plan(pulse_id)
        if (self._pulse_dir(pulse_id) / "stop.json").exists():
            raise ValueError("V5 pulse was stopped; future dispatch is disabled")
        barrier = self._barrier(pulse_id)
        commitments = list(plan["wave1_commitments"])
        if barrier is not None:
            commitments.extend(barrier["review_commitments"])
        matches = [item for item in commitments if item["commitment_id"] == commitment_id]
        if len(matches) != 1:
            raise ValueError("unknown V5 pulse commitment")
        commitment = matches[0]
        self.store.reasoning_modes().require_work_unit_active(
            commitment["round_id"]
        )
        if issuer not in plan["trusted_host_issuers"]:
            raise ValueError("V5 pulse dispatch issuer is not trusted")
        if fresh_context_contract != FRESH_CONTEXT_CONTRACT_V1:
            raise ValueError("V5 pulse dispatch requires the exact fresh-context contract")
        semantic = {
            "schema_version": 5,
            "policy_revision": V5_POLICY_REVISION,
            "project_id": self.store.project_id(),
            "pulse_id": pulse_id,
            "commitment_id": commitment_id,
            "round_id": commitment["round_id"],
            "assignment_id": commitment["assignment_id"],
            "task_card_sha256": commitment["task_card_sha256"],
            "issuer": issuer,
            "host_context_id": _text(host_context_id, "host context id"),
            "agent_identity": _text(agent_identity, "agent identity"),
            "fresh_context_contract": fresh_context_contract,
        }
        with self._mutation_lock():
            return self._write_record(
                prefix="v5host-",
                id_field="dispatch_id",
                semantic=semantic,
                path_for_id=lambda identifier: self._pulse_dir(pulse_id)
                / "dispatches"
                / f"{identifier}.json",
            )

    def _void_ids(self, pulse_id: str) -> set[str]:
        directory = self._pulse_dir(pulse_id) / "voids"
        if not directory.exists():
            return set()
        return {
            self._read_record(path, prefix="v5void-", id_field="void_id")[
                "commitment_id"
            ]
            for path in sorted(directory.glob("*.json"))
        }

    def derive_closure(self, pulse_id: str, *, actor: str) -> dict[str, Any]:
        plan = self._plan(pulse_id)
        barrier = self._barrier(pulse_id, required=True)
        if barrier is None:  # Defensive narrowing; required=True already fails closed.
            raise ValueError("V5 pulse closure requires a barrier")
        voided = self._void_ids(pulse_id)
        reviews = []
        blockers = []
        for commitment in barrier["review_commitments"]:
            receipt = self._receipt_for(commitment)
            if receipt is None:
                if commitment["commitment_id"] not in voided:
                    blockers.append(
                        {
                            "commitment_id": commitment["commitment_id"],
                            "reason": "review contribution is not independently ingested",
                        }
                    )
                continue
            research = self.store.v5_lifecycle()._research_record(receipt["research_id"])
            reviews.append(
                {
                    "commitment_id": commitment["commitment_id"],
                    "peer_research_id": commitment["peer_node_id"],
                    "review_research_id": research["research_id"],
                    "review_research_sha256": research["record_sha256"],
                }
            )
        semantic = {
            "schema_version": 5,
            "policy_revision": V5_POLICY_REVISION,
            "project_id": self.store.project_id(),
            "pulse_id": pulse_id,
            "plan_sha256": plan["record_sha256"],
            "barrier_id": barrier["barrier_id"],
            "barrier_sha256": barrier["record_sha256"],
            "actor": _text(actor, "closure actor"),
            "review_evidence": sorted(reviews, key=lambda item: item["commitment_id"]),
            "blockers": blockers,
            "coordination_complete": not blockers,
            "admission_authority": False,
            "truth_effect": "none",
        }
        with self._mutation_lock():
            return self._write_record(
                prefix="v5close-",
                id_field="closure_id",
                semantic=semantic,
                path_for_id=lambda _identifier: self._pulse_dir(pulse_id)
                / "closure.json",
            )

    def status(self, pulse_id: str) -> dict[str, Any]:
        plan = self._plan(pulse_id)
        barrier = self._barrier(pulse_id)
        voided = self._void_ids(pulse_id)

        def state(commitment: dict[str, Any]) -> str:
            if commitment["commitment_id"] in voided:
                return "voided_optional"
            if self._receipt_for(commitment) is not None:
                return "ingested"
            round_status = self.store.v5_lifecycle().round_status(
                commitment["round_id"]
            )
            match = next(
                item
                for item in round_status["assignments"]
                if item["assignment_id"] == commitment["assignment_id"]
            )
            return match["state"]

        wave1 = [
            {**item, "state": state(item)} for item in plan["wave1_commitments"]
        ]
        wave2 = (
            [
                {**item, "state": state(item)}
                for item in barrier["review_commitments"]
            ]
            if barrier is not None
            else []
        )
        closure_path = self._pulse_dir(pulse_id) / "closure.json"
        stop_path = self._pulse_dir(pulse_id) / "stop.json"
        if stop_path.exists():
            self._read_record(stop_path, prefix="v5stop-", id_field="stop_id")
        dispatch_dir = self._pulse_dir(pulse_id) / "dispatches"
        if dispatch_dir.exists():
            for path in sorted(dispatch_dir.glob("*.json")):
                self._read_record(path, prefix="v5host-", id_field="dispatch_id")
        return {
            "schema_version": 5,
            "policy_revision": V5_POLICY_REVISION,
            "project_id": self.store.project_id(),
            "pulse_id": pulse_id,
            "wave1": wave1,
            "wave2": wave2,
            "barrier_id": barrier["barrier_id"] if barrier else None,
            "closure_id": (
                self._read_record(
                    closure_path, prefix="v5close-", id_field="closure_id"
                )["closure_id"]
                if closure_path.exists()
                else None
            ),
            "stopped": stop_path.exists(),
            "failure_policy": "local_quarantine_existing_contributions_survive",
            "admission_authority": False,
        }

    def audit(self, pulse_id: str | None = None) -> dict[str, Any]:
        errors: list[str] = []
        pulse_ids = (
            [pulse_id]
            if pulse_id is not None
            else (
                sorted(path.name for path in self.root.glob("v5pulse-*") if path.is_dir())
                if self.root.exists()
                else []
            )
        )
        statuses = []
        for current in pulse_ids:
            try:
                statuses.append(self.status(current))
            except Exception as exc:
                errors.append(f"{current}: {exc}")
        return {
            "schema_version": 5,
            "project_id": self.store.project_id(),
            "pulse_count": len(pulse_ids),
            "statuses": statuses,
            "ok": not errors,
            "errors": errors,
            "truth_effect": "none",
        }

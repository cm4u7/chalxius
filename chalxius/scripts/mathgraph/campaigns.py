from __future__ import annotations

import json
import math
import os
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .blackboard import BlackboardStore
from .claims import ClaimRegistry
from .contracts import (
    CAMPAIGN_ID_RE,
    CAMPAIGN_TARGET_ID_RE,
    CLAIM_ID_RE,
    FACT_ID_RE,
    MEMORY_ID_RE,
    POLICY_REVISION_V4,
    require_exact_keys,
    require_string,
    sha256_bytes,
    sha256_json,
    validate_campaign_id,
    validate_campaign_target_id,
)


CAMPAIGN_TARGET_ROLES = {
    "headline_proof",
    "supporting_proof",
    "research_goal",
    "communication",
}
COMMUNICATION_SUBJECT_KINDS = {
    "fact",
    "source_claim",
    "report",
    "verification_bundle",
}
# Historical project work stores source/advisory material below this
# non-Campaign namespace.  It is deliberately excluded from the Campaign id
# projection but remains an explicitly recognized, safe directory rather than
# an invitation to ignore arbitrary unknown entries.
RESERVED_CAMPAIGN_STORE_DIRECTORIES = {"inputs"}
LEGACY_V4_SCORE_FIELDS = {
    "priority",
    "novelty",
    "testability",
    "risk",
    "target_relevance",
    "decisiveness",
    "information_gain",
    "estimated_cost",
}
DECISION_PROFILE_FIELDS = {
    "impact",
    "information_value",
    "tractability",
    "burden",
}
# User-authorized V4 revision: these four factors intentionally supersede the
# guide's eight raw scheduling metrics for new memory.  The legacy projection
# below is compatibility-only and does not restore eight-dimensional authority.
COMPACT_SCORE_MODEL = "compact-4d-v1"
COMPACT_SCORE_ROLE = "priority_ordering_only"
COMPACT_SCORE_WEIGHTS = {
    "impact": 0.35,
    "information_value": 0.25,
    "feasibility": 0.20,
    "economy": 0.20,
}
RECENT_CAMPAIGN_EVENT_SUMMARIES = 20


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _bounded_metric(value: Any, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    number = float(value)
    if not math.isfinite(number) or not 0 <= number <= 1:
        raise ValueError(f"{label} must lie in [0,1]")
    return number


def validate_decision_profile(payload: Any) -> dict[str, float]:
    if not isinstance(payload, dict):
        raise ValueError("decision_profile must be an object")
    require_exact_keys(
        payload,
        required=DECISION_PROFILE_FIELDS,
        label="decision_profile",
    )
    return {
        field: _bounded_metric(
            payload[field],
            label=f"decision_profile.{field}",
        )
        for field in sorted(DECISION_PROFILE_FIELDS)
    }


def project_legacy_decision_profile(entry: dict[str, Any]) -> dict[str, float]:
    values: dict[str, float] = {}
    for field in LEGACY_V4_SCORE_FIELDS:
        value = entry.get(field, 0.5)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"memory {field} must be numeric")
        value = float(value)
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"memory {field} must lie in [0,1]")
        values[field] = value
    return {
        "impact": round(
            0.5 * values["priority"] + 0.5 * values["target_relevance"],
            6,
        ),
        "information_value": round(
            0.4 * values["decisiveness"]
            + 0.4 * values["information_gain"]
            + 0.2 * values["novelty"],
            6,
        ),
        "tractability": round(values["testability"], 6),
        "burden": round(
            0.6 * values["estimated_cost"] + 0.4 * values["risk"],
            6,
        ),
    }


def decision_factors(
    entry: dict[str, Any],
    *,
    readiness: float,
) -> dict[str, float]:
    readiness = _bounded_metric(readiness, label="memory readiness")
    supplied = entry.get("decision_profile")
    profile = (
        validate_decision_profile(supplied)
        if supplied is not None
        else project_legacy_decision_profile(entry)
    )
    return {
        "impact": profile["impact"],
        "information_value": profile["information_value"],
        "feasibility": round(
            0.5 * profile["tractability"] + 0.5 * readiness,
            6,
        ),
        "burden": profile["burden"],
    }


def actionable_score(entry: dict[str, Any], *, readiness: float) -> float:
    """Return a non-authoritative ordering score without mutating memory."""

    factors = decision_factors(entry, readiness=readiness)
    raw = (
        COMPACT_SCORE_WEIGHTS["impact"] * factors["impact"]
        + COMPACT_SCORE_WEIGHTS["information_value"]
        * factors["information_value"]
        + COMPACT_SCORE_WEIGHTS["feasibility"] * factors["feasibility"]
        + COMPACT_SCORE_WEIGHTS["economy"] * (1.0 - factors["burden"])
    )
    return round(max(0.0, min(1.0, raw)), 4)


def collapse_actionable_frontier(
    entries: list[dict[str, Any]],
    *,
    include_history: bool,
) -> list[dict[str, Any]]:
    if include_history:
        return entries
    active = [
        entry
        for entry in entries
        if not entry.get("killed_by_fact")
        and entry.get("status") in {"open", "supported", "challenged", "verifying"}
    ]
    children: dict[str, list[dict[str, Any]]] = {}
    for entry in active:
        parent = entry.get("repair_of_memory_id")
        if isinstance(parent, str) and parent:
            children.setdefault(parent, []).append(entry)
    hidden_roots = set(children)
    leaves = [
        entry
        for entry in active
        if entry.get("id") not in hidden_roots
    ]
    return leaves


class CampaignStore:
    def __init__(self, project_root: Path | str) -> None:
        self.project_root = Path(project_root).resolve()
        self.root = self.project_root / "campaigns"
        self.active_path = self.root / "ACTIVE"

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        result: list[dict[str, Any]] = []
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"non-object campaign event at {path}:{number}")
            result.append(payload)
        return result

    @staticmethod
    def _append(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    @staticmethod
    def _write_atomic(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except BaseException:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise

    def initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def campaign_ids(self) -> list[str]:
        """Return every exact stored Campaign id without using ``ACTIVE``."""

        if not self.root.exists():
            return []
        if self.root.is_symlink() or not self.root.is_dir():
            raise ValueError("campaign store is not a safe directory")
        campaign_ids: list[str] = []
        for path in sorted(self.root.iterdir(), key=lambda item: item.name):
            if path.name == "ACTIVE":
                continue
            if path.name in RESERVED_CAMPAIGN_STORE_DIRECTORIES:
                if path.is_symlink() or not path.is_dir():
                    raise ValueError(
                        f"reserved campaign store entry is unsafe: {path.name}"
                    )
                continue
            if CAMPAIGN_ID_RE.fullmatch(path.name) is None:
                raise ValueError(
                    f"unexpected campaign store entry: {path.name}"
                )
            if path.is_symlink() or not path.is_dir():
                raise ValueError(f"campaign path is unsafe: {path.name}")
            campaign_ids.append(path.name)
        return campaign_ids

    def _events_path(self, campaign_id: str) -> Path:
        return self.root / validate_campaign_id(campaign_id) / "events.jsonl"

    def _publish_new_ledger(
        self,
        campaign_id: str,
        events: list[dict[str, Any]],
    ) -> None:
        """Publish one complete new-campaign ledger without partial visibility."""

        campaign_id = validate_campaign_id(campaign_id)
        if (
            not self.root.is_dir()
            or self.root.is_symlink()
        ):
            raise ValueError("campaign store is not an initialized safe directory")
        destination = self.root / campaign_id
        if os.path.lexists(destination):
            raise ValueError(f"campaign id collision: {campaign_id}")
        ledger = "".join(
            json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n"
            for event in events
        )
        temporary = Path(
            tempfile.mkdtemp(prefix=".campaign-create.", dir=self.root)
        )
        try:
            events_path = temporary / "events.jsonl"
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            fd = os.open(events_path, flags, 0o600)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(ledger)
                    handle.flush()
                    os.fsync(handle.fileno())
            except BaseException:
                try:
                    os.close(fd)
                except OSError:
                    pass
                raise
            if os.path.lexists(destination):
                raise ValueError(f"campaign id collision: {campaign_id}")
            try:
                os.rename(temporary, destination)
            except OSError as exc:
                if os.path.lexists(destination):
                    raise ValueError(
                        f"campaign id collision: {campaign_id}"
                    ) from exc
                raise
        except BaseException:
            shutil.rmtree(temporary, ignore_errors=True)
            raise

    @staticmethod
    def _validate_create(payload: dict[str, Any]) -> dict[str, Any]:
        require_exact_keys(
            payload,
            required={
                "name",
                "objective",
                "source_claim_ids",
                "targets",
                "constraints",
                "stop_conditions",
                "value_definition",
            },
            label="campaign create payload",
        )
        for key in ("name", "objective", "value_definition"):
            require_string(payload, key)
        for key in (
            "source_claim_ids",
            "targets",
            "constraints",
            "stop_conditions",
        ):
            if not isinstance(payload.get(key), list):
                raise ValueError(f"campaign {key} must be a list")
        for claim_id in payload["source_claim_ids"]:
            if not isinstance(claim_id, str) or CLAIM_ID_RE.fullmatch(claim_id) is None:
                raise ValueError("campaign source_claim_ids are invalid")
        if len(set(payload["source_claim_ids"])) != len(
            payload["source_claim_ids"]
        ):
            raise ValueError(
                "campaign source_claim_ids must be unique"
            )
        if any(not isinstance(value, str) for value in payload["constraints"]):
            raise ValueError("campaign constraints must be strings")
        if any(not isinstance(value, str) for value in payload["stop_conditions"]):
            raise ValueError("campaign stop_conditions must be strings")
        return payload

    def create(
        self,
        payload: dict[str, Any],
        *,
        actor: str,
        fact_exists: Callable[[str], bool] | None = None,
    ) -> str:
        validated = self._validate_create(dict(payload))
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError("campaign actor must be nonempty")
        if fact_exists is not None and not callable(fact_exists):
            raise ValueError(
                "campaign admitted-fact predicate must be callable"
            )
        normalized_actor = actor.strip()
        registry = ClaimRegistry(self.project_root)
        for claim_id in validated["source_claim_ids"]:
            try:
                registry.show_claim(claim_id)
            except (KeyError, ValueError, OSError) as exc:
                raise ValueError(
                    f"campaign source claim is not registered: {claim_id}"
                ) from exc
        initial_targets: list[dict[str, Any]] = []
        seen_targets: set[str] = set()
        for target_payload in validated["targets"]:
            if not isinstance(target_payload, dict):
                raise ValueError("campaign initial targets must be objects")
            role = target_payload.get("role")
            if role == "research_goal":
                raise ValueError(
                    "campaign research_goal targets must be added after "
                    "Campaign creation so their exact Campaign-bound Research "
                    "root can be checked"
                )
            if (
                role in {"headline_proof", "supporting_proof"}
                and fact_exists is None
            ):
                raise ValueError(
                    "campaign proof targets require an active admitted-fact "
                    "predicate"
                )
            target = self._validate_target(
                dict(target_payload),
                fact_exists=(
                    fact_exists
                    if fact_exists is not None
                    else lambda _fact_id: False
                ),
            )
            semantic_target = {**target, "status": "active"}
            semantic_key = sha256_json(semantic_target)
            if semantic_key in seen_targets:
                raise ValueError(
                    "campaign initial targets must be unique"
                )
            seen_targets.add(semantic_key)
            initial_targets.append(target)
        normalized_payload = {
            **validated,
            "source_claim_ids": list(validated["source_claim_ids"]),
            "targets": [dict(target) for target in initial_targets],
            "constraints": list(validated["constraints"]),
            "stop_conditions": list(validated["stop_conditions"]),
        }
        campaign_id = "campaign-" + sha256_json(
            [
                normalized_payload,
                time.time_ns(),
                len(list(self.root.glob("campaign-*"))),
            ]
        )[:12]
        destination = self.root / campaign_id
        if os.path.lexists(destination):
            raise ValueError(f"campaign id collision: {campaign_id}")
        event_body = {
            "schema_version": 4,
            "policy_revision": POLICY_REVISION_V4,
            "event": "created",
            "campaign_id": campaign_id,
            "payload": normalized_payload,
            "actor": normalized_actor,
        }
        events = [
            {**event_body, "event_id": sha256_json(event_body)}
        ]
        target_ids: set[str] = set()
        for target in initial_targets:
            target_id = "camtarget-" + sha256_json(
                [campaign_id, target]
            )[:16]
            if target_id in target_ids:
                raise ValueError(
                    "campaign initial target id collision"
                )
            target_ids.add(target_id)
            target_body = {
                "schema_version": 4,
                "policy_revision": POLICY_REVISION_V4,
                "event": "target_added",
                "campaign_id": campaign_id,
                "target_id": target_id,
                "target": {**target, "status": "active"},
                "actor": normalized_actor,
            }
            events.append(
                {
                    **target_body,
                    "event_id": sha256_json(target_body),
                }
            )
        self._publish_new_ledger(campaign_id, events)
        return campaign_id

    def activate(self, campaign_id: str, *, actor: str) -> None:
        campaign_id = validate_campaign_id(campaign_id)
        self.status(campaign_id)
        self._write_atomic(self.active_path, campaign_id + "\n")
        body = {
            "schema_version": 4,
            "policy_revision": POLICY_REVISION_V4,
            "event": "activated",
            "campaign_id": campaign_id,
            "actor": actor,
        }
        self._append(
            self._events_path(campaign_id),
            {**body, "event_id": sha256_json(body)},
        )

    def active(self) -> str | None:
        if not self.active_path.exists():
            return None
        value = self.active_path.read_text(encoding="utf-8").strip()
        return validate_campaign_id(value) if value else None

    @staticmethod
    def _validate_target(
        payload: dict[str, Any],
        *,
        fact_exists: Callable[[str], bool],
        research_exists: Callable[[str], bool] | None = None,
    ) -> dict[str, Any]:
        require_exact_keys(
            payload,
            required={"role", "subject_kind", "subject_id", "label"},
            optional={"status"},
            label="campaign target",
        )
        role = require_string(payload, "role")
        if role not in CAMPAIGN_TARGET_ROLES:
            raise ValueError("campaign target role is invalid")
        subject_kind = require_string(payload, "subject_kind")
        subject_id = require_string(payload, "subject_id")
        require_string(payload, "label")
        if payload.get("status", "active") != "active":
            raise ValueError("new campaign target status must be active")
        if role in {"headline_proof", "supporting_proof"}:
            if subject_kind != "fact" or FACT_ID_RE.fullmatch(subject_id) is None:
                raise ValueError("proof campaign targets must be fact ids")
            if not fact_exists(subject_id):
                raise ValueError("campaign proof target is not an active admitted fact")
        elif role == "research_goal":
            if (
                subject_kind != "research"
                or MEMORY_ID_RE.fullmatch(subject_id) is None
            ):
                raise ValueError(
                    "campaign research_goal targets must name exact Research ids"
                )
            if research_exists is None or not research_exists(subject_id):
                raise ValueError(
                    "campaign research_goal target is not an exact "
                    "Campaign-bound Research root"
                )
        elif subject_kind not in COMMUNICATION_SUBJECT_KINDS:
            raise ValueError("campaign communication subject kind is invalid")
        return payload

    def target_add(
        self,
        campaign_id: str,
        payload: dict[str, Any],
        *,
        actor: str,
        fact_exists: Callable[[str], bool],
        research_exists: Callable[[str], bool] | None = None,
    ) -> str:
        campaign_id = validate_campaign_id(campaign_id)
        self.status(campaign_id)
        target = self._validate_target(
            dict(payload),
            fact_exists=fact_exists,
            research_exists=research_exists,
        )
        target_id = "camtarget-" + sha256_json(
            [campaign_id, target]
        )[:16]
        existing = self.status(campaign_id)["targets"]
        if target_id in existing:
            return target_id
        body = {
            "schema_version": 4,
            "policy_revision": POLICY_REVISION_V4,
            "event": "target_added",
            "campaign_id": campaign_id,
            "target_id": target_id,
            "target": {**target, "status": "active"},
            "actor": actor,
        }
        self._append(
            self._events_path(campaign_id),
            {**body, "event_id": sha256_json(body)},
        )
        return target_id

    def target_archive(
        self,
        campaign_id: str,
        target_id: str,
        *,
        reason: str,
        actor: str,
    ) -> None:
        campaign_id = validate_campaign_id(campaign_id)
        target_id = validate_campaign_target_id(target_id)
        status = self.status(campaign_id)
        target = status["targets"].get(target_id)
        if target is None:
            raise KeyError(f"unknown campaign target: {target_id}")
        if target["status"] == "archived":
            return
        body = {
            "schema_version": 4,
            "policy_revision": POLICY_REVISION_V4,
            "event": "target_archived",
            "campaign_id": campaign_id,
            "target_id": target_id,
            "reason": require_string({"reason": reason}, "reason"),
            "actor": actor,
        }
        self._append(
            self._events_path(campaign_id),
            {**body, "event_id": sha256_json(body)},
        )

    def update(self, campaign_id: str, payload: dict[str, Any], *, actor: str) -> str:
        campaign_id = validate_campaign_id(campaign_id)
        self.status(campaign_id)
        require_exact_keys(
            payload,
            required={"type", "payload"},
            label="campaign update",
        )
        update_type = require_string(payload, "type")
        if update_type not in {
            "constraint_added",
            "stop_condition_disposition",
            "value_definition_updated",
            "note",
        }:
            raise ValueError(
                "campaign update type must be one of: constraint_added, "
                "stop_condition_disposition, value_definition_updated, note"
            )
        if not isinstance(payload.get("payload"), dict):
            raise ValueError("campaign update payload must be an object")
        update_payload = self._compact_frontier_checkpoint_payload(
            payload["payload"]
        )
        body = {
            "schema_version": 4,
            "policy_revision": POLICY_REVISION_V4,
            "event": update_type,
            "campaign_id": campaign_id,
            "payload": update_payload,
            "actor": actor,
            "recorded_at": _utc_now(),
        }
        event_id = sha256_json(body)
        self._append(
            self._events_path(campaign_id),
            {**body, "event_id": event_id},
        )
        return event_id

    @staticmethod
    def _compact_frontier_checkpoint_payload(
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Keep a frontier checkpoint self-contained without copying nodes.

        Campaign checkpoints are advisory navigation snapshots.  Their reader
        resolves exact Research and round content from identifiers and consumes
        only the small routing projection below.  Persisting worker reasons,
        products, reviews, labels, and other node bodies in every generation
        merely duplicates canonical records and makes a long Campaign harder
        to read.  Malformed values are preserved in the fields the reader
        inspects so its existing diagnostics remain available; this is a write
        projection, not a new admission gate.
        """

        if payload.get("kind") != "campaign_frontier_head_checkpoint":
            return dict(payload)
        compact = {
            key: payload[key]
            for key in (
                "kind",
                "generation",
                "supersedes_event_id",
            )
            if key in payload
        }
        raw_frontiers = payload.get("target_frontiers")
        if not isinstance(raw_frontiers, list):
            compact["target_frontiers"] = raw_frontiers
            return compact
        frontiers: list[Any] = []
        for raw_frontier in raw_frontiers:
            if not isinstance(raw_frontier, dict):
                frontiers.append(raw_frontier)
                continue
            frontier = {
                key: raw_frontier[key]
                for key in (
                    "target_id",
                    "recovery_root_research_id",
                    "main_disposition",
                )
                if key in raw_frontier
            }
            for field in ("active_heads", "attained_checkpoints"):
                if field not in raw_frontier:
                    continue
                values = raw_frontier[field]
                if not isinstance(values, list):
                    frontier[field] = values
                    continue
                frontier[field] = [
                    (
                        {"research_id": value["research_id"]}
                        if isinstance(value, dict) and "research_id" in value
                        else value
                    )
                    for value in values
                ]
            frontiers.append(frontier)
        compact["target_frontiers"] = frontiers
        return compact

    def _verified_events(
        self,
        campaign_id: str,
    ) -> list[dict[str, Any]]:
        campaign_id = validate_campaign_id(campaign_id)
        campaign_path = self.root / campaign_id
        if (
            not campaign_path.exists()
            or campaign_path.is_symlink()
            or not campaign_path.is_dir()
        ):
            raise KeyError(f"unknown campaign: {campaign_id}")
        events = self._read_jsonl(self._events_path(campaign_id))
        if not events or events[0].get("event") != "created":
            raise KeyError(f"unknown campaign: {campaign_id}")
        create = events[0]
        expected_first = {
            key: create[key]
            for key in (
                "schema_version",
                "policy_revision",
                "event",
                "campaign_id",
                "payload",
                "actor",
            )
        }
        if create.get("event_id") != sha256_json(expected_first):
            raise ValueError("campaign create event hash mismatch")
        for event in events[1:]:
            semantic = {
                key: value for key, value in event.items() if key != "event_id"
            }
            if event.get("event_id") != sha256_json(semantic):
                raise ValueError("campaign event id/hash mismatch")
        return events

    @staticmethod
    def _history_summary_from_verified_events(
        events: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "event_count": len(events),
            "last_event_id": events[-1]["event_id"] if events else None,
            "events_sha256": sha256_json(events),
        }

    def history_summary(
        self,
        campaign_id: str,
        *,
        event_count: int | None = None,
    ) -> dict[str, Any]:
        """Return a fixed-size digest after validating every Campaign event."""

        events = self._verified_events(campaign_id)
        selected = events
        if event_count is not None:
            if isinstance(event_count, bool) or not isinstance(event_count, int):
                raise ValueError("campaign event_count must be an integer")
            if not 1 <= event_count <= len(events):
                raise ValueError(
                    "campaign event_count lies outside verified history"
                )
            selected = events[:event_count]
        return self._history_summary_from_verified_events(selected)

    def _status_from_verified_events(
        self,
        campaign_id: str,
        events: list[dict[str, Any]],
        *,
        include_updates: bool,
    ) -> dict[str, Any]:
        create = events[0]
        targets: dict[str, dict[str, Any]] = {}
        updates: list[dict[str, Any]] = []
        for event in events[1:]:
            event_type = event.get("event")
            if event_type == "target_added":
                target_id = validate_campaign_target_id(str(event.get("target_id")))
                target = event.get("target")
                if not isinstance(target, dict):
                    raise ValueError("campaign target event is malformed")
                targets[target_id] = {
                    **target,
                    "target_id": target_id,
                    "added_by_event_id": event["event_id"],
                }
            elif event_type == "target_archived":
                target_id = validate_campaign_target_id(str(event.get("target_id")))
                if target_id not in targets:
                    raise ValueError("campaign archives a missing target")
                targets[target_id] = {
                    **targets[target_id],
                    "status": "archived",
                    "archive_reason": event.get("reason", ""),
                }
            elif include_updates and event_type not in {"activated"}:
                updates.append(event)
        status = {
            "campaign_id": campaign_id,
            "active": self.active() == campaign_id,
            **create["payload"],
            "targets": targets,
            "event_count": len(events),
            "history": self._history_summary_from_verified_events(events),
        }
        if include_updates:
            status["updates"] = updates
        return status

    def status(self, campaign_id: str) -> dict[str, Any]:
        campaign_id = validate_campaign_id(campaign_id)
        events = self._verified_events(campaign_id)
        return self._status_from_verified_events(
            campaign_id,
            events,
            include_updates=True,
        )

    @staticmethod
    def _event_read_summary(event: dict[str, Any]) -> dict[str, Any]:
        """Project one immutable event without replaying a copied node body."""

        summary = {
            key: event[key]
            for key in (
                "event_id",
                "event",
                "actor",
                "recorded_at",
                "target_id",
                "reason",
            )
            if key in event
        }
        target = event.get("target")
        if isinstance(target, dict):
            summary["target"] = {
                key: target[key]
                for key in (
                    "role",
                    "subject_kind",
                    "subject_id",
                    "label",
                    "status",
                )
                if key in target
            }
        payload = event.get("payload")
        if not isinstance(payload, dict):
            return summary
        summary["payload_sha256"] = sha256_json(payload)
        summary["payload_keys"] = sorted(payload)
        if payload.get("kind") == "campaign_frontier_head_checkpoint":
            summary["checkpoint_generation"] = payload.get("generation")
            summary["checkpoint_supersedes_event_id"] = payload.get(
                "supersedes_event_id"
            )
        elif isinstance(payload.get("text"), str):
            text = payload["text"]
            summary["text_preview"] = (
                text if len(text) <= 400 else text[:400] + "…"
            )
            summary["text_truncated"] = len(text) > 400
        return summary

    def compact_status(self, campaign_id: str) -> dict[str, Any]:
        """Return one stable current view with a fixed recent event tail.

        This deliberately is not a paging protocol.  Routine Main reads see
        current Campaign semantics and a small recent provenance tail.  Exact
        old bytes remain in the append-only ledger for targeted forensics.
        """

        campaign_id = validate_campaign_id(campaign_id)
        events = self._verified_events(campaign_id)
        compact = self._status_from_verified_events(
            campaign_id,
            events,
            include_updates=False,
        )
        start = max(0, len(events) - RECENT_CAMPAIGN_EVENT_SUMMARIES)
        recent_events = events[start:]
        latest_checkpoint: dict[str, Any] | None = None
        for event in reversed(events):
            payload = event.get("payload")
            if (
                event.get("event") == "note"
                and isinstance(payload, dict)
                and payload.get("kind")
                == "campaign_frontier_head_checkpoint"
            ):
                latest_checkpoint = {
                    "event_id": event["event_id"],
                    **self._compact_frontier_checkpoint_payload(payload),
                }
                break
        compact["latest_frontier_checkpoint"] = latest_checkpoint
        compact["recent_history"] = {
            "event_count": len(events),
            "shown_count": len(recent_events),
            "start_ordinal": start + 1,
            "end_ordinal": len(events),
            "older_event_count": start,
            "events": [
                self._event_read_summary(event) for event in recent_events
            ],
        }
        return compact

    def derived_targets(self, campaign_id: str | None = None) -> list[str]:
        campaign_id = campaign_id or self.active()
        if campaign_id is None:
            return []
        status = self.status(campaign_id)
        return [
            target["subject_id"]
            for target in status["targets"].values()
            if target["status"] == "active"
            and target["role"] in {"headline_proof", "supporting_proof"}
        ]

    def promote_blackboard_node(
        self,
        node_id: str,
        task_spec: dict[str, Any],
        *,
        actor: str,
        memory_add: Callable[[dict[str, Any], str], str],
    ) -> str:
        require_exact_keys(
            task_spec,
            required={
                "snapshot_id",
                "campaign_id",
                "memory_kind",
                "claim",
                "rationale",
                "mode_suggestions",
                "blackboard_query",
            },
            optional={"decision_profile", "metrics"},
            label="blackboard promotion task spec",
        )
        campaign_id = validate_campaign_id(
            require_string(task_spec, "campaign_id")
        )
        self.status(campaign_id)
        blackboard = BlackboardStore(self.project_root)
        nodes, _ = blackboard.snapshot_objects(
            require_string(task_spec, "snapshot_id")
        )
        if node_id not in nodes:
            raise ValueError("promotion origin node is absent from the bound snapshot")
        if nodes[node_id].get("node_type") == "paper_logic_mirror":
            raise ValueError(
                "a Paper Logic mirror is a read-only exploration aid and "
                "cannot be promoted directly; promote a new agent exploration "
                "node that cites the mirror instead"
            )
        decision_profile = task_spec.get("decision_profile")
        metrics = task_spec.get("metrics")
        if (decision_profile is None) == (metrics is None):
            raise ValueError(
                "promotion requires exactly one of decision_profile or legacy metrics"
            )
        scoring_payload: dict[str, Any]
        if decision_profile is not None:
            scoring_payload = {
                "decision_profile": validate_decision_profile(decision_profile),
                "score_model": COMPACT_SCORE_MODEL,
            }
        else:
            if not isinstance(metrics, dict):
                raise ValueError("promotion metrics must be an object")
            require_exact_keys(
                metrics,
                required=LEGACY_V4_SCORE_FIELDS,
                label="promotion legacy metrics",
            )
            project_legacy_decision_profile(metrics)
            scoring_payload = {
                **{key: float(value) for key, value in metrics.items()},
            }
        modes = task_spec.get("mode_suggestions")
        if not isinstance(modes, list) or any(not isinstance(mode, str) for mode in modes):
            raise ValueError("promotion mode_suggestions must be a list of strings")
        query = task_spec.get("blackboard_query")
        if not isinstance(query, dict):
            raise ValueError("promotion blackboard_query must be an object")
        BlackboardStore.validate_query(query)
        snapshot_id = task_spec["snapshot_id"]
        node_hash = sha256_bytes(
            json.dumps(
                nodes[node_id],
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        )
        task_hash = sha256_json(task_spec)
        payload = {
            "kind": require_string(task_spec, "memory_kind"),
            "status": "open",
            "claim": require_string(task_spec, "claim"),
            "rationale": require_string(task_spec, "rationale"),
            "suggested_actions": list(modes),
            "campaign_id": campaign_id,
            **scoring_payload,
            "origin_blackboard_node_id": node_id,
            "origin_blackboard_snapshot_id": snapshot_id,
            "origin_blackboard_node_sha256": node_hash,
            "blackboard_query_sha256": sha256_json(query),
            "blackboard_query": query,
            "promotion_task_sha256": task_hash,
            "source": f"blackboard:{node_id}",
        }
        return memory_add(payload, actor)

    def audit(
        self,
        *,
        fact_exists: Callable[[str], bool],
        source_claim_exists: Callable[[str], bool],
    ) -> dict[str, Any]:
        errors: list[str] = []
        campaigns = 0
        try:
            visible_campaign_ids = self.campaign_ids()
        except Exception as exc:
            return {
                "ok": False,
                "errors": [f"campaign inventory: {exc}"],
                "campaigns": 0,
                "active_campaign": self.active(),
            }
        for campaign_id in visible_campaign_ids:
            try:
                status = self.status(campaign_id)
                for claim_id in status["source_claim_ids"]:
                    if not source_claim_exists(claim_id):
                        raise ValueError(
                            "campaign source claim is not registered: "
                            f"{claim_id}"
                        )
                for target in status["targets"].values():
                    if (
                        target["status"] == "active"
                        and target["role"]
                        in {"headline_proof", "supporting_proof"}
                        and not fact_exists(target["subject_id"])
                    ):
                        raise ValueError(
                            f"active proof target is not admitted: {target['subject_id']}"
                        )
                campaigns += 1
            except Exception as exc:
                errors.append(f"{campaign_id}: {exc}")
        active = self.active()
        if active is not None and not (self.root / active / "events.jsonl").exists():
            errors.append("ACTIVE points to a missing campaign")
        return {
            "ok": not errors,
            "errors": errors,
            "campaigns": campaigns,
            "active_campaign": active,
        }

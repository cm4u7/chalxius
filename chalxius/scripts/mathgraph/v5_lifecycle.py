from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import (
    ACTIVE_MEMORY_STATUSES,
    CLAIM_RELATIONS,
    FACT_ID_RE,
    MEMORY_KINDS,
    MEMORY_ID_RE,
    MEMORY_STATUSES,
    NOVELTY_STATUSES,
    SHA256_RE,
    WORK_MODES,
    contained_path,
    sha256_bytes,
    sha256_json,
    validate_assignment_id,
    validate_fact_id,
    validate_memory_id,
    validate_round_id,
)
from .applicability import validate_external_refs_for_submission
from .computations import validate_computational_evidence
from .elementary import validate_elementary_uses_for_submission
from .fact_bundles import validate_terminology
from .graph import DependencyGraph
from .interfaces import (
    build_statement_interface,
    extract_statement_clauses,
    validate_predecessor_uses,
    validate_quantifier_ledger,
    write_interface_once,
)
from .markdown import parse_fact_markdown, validate_fact_round_trip
from .model import Fact
from .modes import FACT_ADMISSION_CONTRACT_SHA256


V5_WORKFLOW_EVIDENCE_VERSION = 5
V5_POLICY_REVISION = "chalxius-v5-minimal-core-2"
V5_LIFECYCLE_CONTRACT: dict[str, Any] = {
    "schema_version": 1,
    "workflow_evidence_version": V5_WORKFLOW_EVIDENCE_VERSION,
    "policy_revision": V5_POLICY_REVISION,
    "truth_path": {
        "states": [
            "Research",
            "Candidate Release",
            "Certification Decision",
            "Fact",
        ],
        "transitions": ["release", "decide", "admit"],
    },
    "authority_domains": {
        "research": "nontruth",
        "candidate_release": "sealed_nontruth",
        "certification_decision": "certification_evidence_only",
        "fact_graph": "sole_premise_store",
    },
    "collaboration_contract": {
        "planes": ["control", "mathematical_state", "narrative"],
        "task_card": "immutable_capability_boundary",
        "contribution_failure": "local_quarantine",
    },
    "legacy_authority": {
        "v4": "readable_historical_nontruth_only",
        "original_danus": "read_only_reference_only",
    },
    "load_bearing_computation": {
        "verification_check": "program_math_truncation",
        "series_product_coefficient": (
            "machine_checked_valuation_budget_and_bound_depth_extension"
        ),
    },
    "fact_admission_contract_sha256": FACT_ADMISSION_CONTRACT_SHA256,
}
V5_LIFECYCLE_CONTRACT_SHA256 = sha256_json(V5_LIFECYCLE_CONTRACT)
V5_RESEARCH_KINDS = frozenset(
    {
        *MEMORY_KINDS,
        "challenge",
        "insight",
        "boundary",
        "synthesis",
        "repair",
        "disposition",
    }
)
V5_RETURN_OUTCOMES = frozenset(
    {"proof", "counterexample", "evidence", "dead_end", "insight", "challenge"}
)
V5_VALIDATION_GRANULARITIES = frozenset(
    {"monolithic_theorem", "atomic_fact_dag", "nodewise_proof_dag"}
)
V5_CHALLENGE_DISPOSITIONS = frozenset(
    {
        "resolved_by_candidate",
        "incorporated_as_boundary",
        "nonblocking_with_reason",
        "superseded_by_research",
    }
)
V5_COVERAGE_DISPOSITIONS = frozenset(
    {
        "fact_bundle_member",
        "definition_only",
        "source_only",
        "audit_only",
        "excluded_with_reason",
    }
)
V5_PROJECT_BACKGROUND_FILENAME = "PROJECT_BACKGROUND.md"
V5_MAX_PROJECT_BACKGROUND_BYTES = 256 * 1024


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _require_nonempty_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    return value.strip()


def _require_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) for item in value
    ):
        raise ValueError(f"{label} must be a list of strings")
    return list(value)


# These V4 commands write directly into a truth or migration path.  They stay
# visible for V4 projects but must be routed through the V5 lifecycle before a
# V5 project can use them.  Keeping this list near the V5 authority contract
# makes an accidental legacy-writer bypass reviewable and testable.
V5_LEGACY_TRUTH_WRITER_COMMANDS = frozenset(
    {
        "fact-bundle-submit",
        "make-bundle-verifier-task",
        "fact-bundle-verifier-task",
        "fact-bundle-record-review",
        "fact-bundle-admit",
        "import-danus",
        "upgrade-workflow",
        "upgrade-project-copy",
    }
)


@dataclass(slots=True)
class V5AuditReport:
    facts: int = 0
    edges: int = 0
    targets: int = 0
    target_closure: int = 0
    max_depth: int = 0
    candidates: int = 0
    memory_entries: int = 0
    novelty_entries: int = 0
    research_entries: int = 0
    candidate_releases: int = 0
    certification_decisions: int = 0
    quarantined_contributions: int = 0
    graph_errors: list[str] = field(default_factory=list)
    workflow_errors: list[str] = field(default_factory=list)
    blackboard_graph_errors: list[str] = field(default_factory=list)
    blackboard_graph_warnings: list[str] = field(default_factory=list)
    paper_logic_errors: list[str] = field(default_factory=list)
    paper_logic_warnings: list[str] = field(default_factory=list)
    paper_source_nodes: int = 0
    paper_reconstruction_nodes: int = 0
    paper_audit_nodes: int = 0
    historical_workflow_warnings: list[str] = field(default_factory=list)
    trust_debt: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def current_ok(self) -> bool:
        return self.ok

    @property
    def history_clean(self) -> bool:
        return not self.historical_workflow_warnings and not self.trust_debt

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "current_ok": self.current_ok,
            "history_clean": self.history_clean,
            "workflow_evidence_version": V5_WORKFLOW_EVIDENCE_VERSION,
            "facts": self.facts,
            "edges": self.edges,
            "targets": self.targets,
            "target_closure": self.target_closure,
            "max_depth": self.max_depth,
            "candidates": self.candidates,
            "memory_entries": self.memory_entries,
            "novelty_entries": self.novelty_entries,
            "research_entries": self.research_entries,
            "candidate_releases": self.candidate_releases,
            "certification_decisions": self.certification_decisions,
            "quarantined_contributions": self.quarantined_contributions,
            "graph_errors": self.graph_errors,
            "workflow_errors": self.workflow_errors,
            "current_workflow_errors": self.workflow_errors,
            "blackboard_graph_errors": self.blackboard_graph_errors,
            "blackboard_graph_warnings": self.blackboard_graph_warnings,
            "paper_logic_errors": self.paper_logic_errors,
            "paper_logic_warnings": self.paper_logic_warnings,
            "paper_source_nodes": self.paper_source_nodes,
            "paper_reconstruction_nodes": self.paper_reconstruction_nodes,
            "paper_audit_nodes": self.paper_audit_nodes,
            "historical_workflow_warnings": self.historical_workflow_warnings,
            "trust_debt": self.trust_debt,
            "errors": self.errors,
            "warnings": self.warnings,
        }


class V5LifecycleManager:
    """Own the V5 authority boundary without importing a retired runtime."""

    def __init__(self, store: Any) -> None:
        self.store = store
        self.root = store.root / "governance" / "v5"
        self.contract_path = self.root / "lifecycle-contract.json"
        self.research_root = store.root / "research"
        self.research_entries_dir = self.research_root / "entries" / "by-id"
        self.quarantine_dir = self.research_root / "quarantine" / "by-id"
        self.candidate_releases_dir = (
            store.root / "candidate_releases" / "by-id"
        )
        self.candidate_artifacts_dir = (
            store.root / "candidate_releases" / "artifacts" / "by-hash"
        )
        self.certification_decisions_dir = (
            store.root / "certification" / "decisions" / "by-id"
        )
        self.admissions_dir = (
            store.fact_graph_dir / "v5_admissions" / "by-release"
        )
        self.revocations_dir = (
            store.fact_graph_dir / "v5_revocations" / "by-fact"
        )

    def initialize(self) -> None:
        for path in (
            self.root,
            self.research_entries_dir,
            self.quarantine_dir,
            self.candidate_releases_dir,
            self.candidate_artifacts_dir,
            self.certification_decisions_dir,
            self.admissions_dir,
            self.revocations_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)
        payload = {
            **V5_LIFECYCLE_CONTRACT,
            "contract_sha256": V5_LIFECYCLE_CONTRACT_SHA256,
        }
        self.store._write_json_once(self.contract_path, payload)

    def _research_path(self, research_id: str) -> Path:
        return self.research_entries_dir / f"{validate_memory_id(research_id)}.json"

    def _research_record(self, research_id: str) -> dict[str, Any]:
        path = self._research_path(research_id)
        if path.is_symlink() or not path.is_file():
            raise KeyError(f"unknown V5 research entry: {research_id}")
        record = self.store._read_json(path)
        self._validate_research_record(record, path=path)
        return record

    def _validate_research_record(
        self,
        record: Any,
        *,
        path: Path,
    ) -> dict[str, Any]:
        if not isinstance(record, dict):
            raise ValueError("research record must be one object")
        required = {
            "schema_version",
            "policy_revision",
            "project_id",
            "research_id",
            "kind",
            "status",
            "claim",
            "content",
            "rationale",
            "dependencies",
            "source",
            "relation",
            "related_research_ids",
            "metadata",
            "actor",
            "created_at",
            "semantic_sha256",
            "record_sha256",
        }
        if set(record) != required:
            raise ValueError("research record fields are not exact")
        research_id = validate_memory_id(
            _require_nonempty_text(record.get("research_id"), "research id")
        )
        if path.stem != research_id:
            raise ValueError("research path/id mismatch")
        if (
            record.get("schema_version") != 5
            or record.get("policy_revision") != V5_POLICY_REVISION
            or record.get("project_id") != self.store.project_id()
        ):
            raise ValueError("research schema/policy/project mismatch")
        if record.get("kind") not in V5_RESEARCH_KINDS:
            raise ValueError("research kind is invalid")
        if record.get("status") not in MEMORY_STATUSES:
            raise ValueError("research status is invalid")
        _require_nonempty_text(record.get("claim"), "research claim")
        for field_name in ("content", "rationale", "source", "actor", "created_at"):
            if not isinstance(record.get(field_name), str):
                raise ValueError(f"research {field_name} must be a string")
        dependencies = _require_string_list(
            record.get("dependencies"), "research dependencies"
        )
        for fact_id in dependencies:
            validate_fact_id(fact_id)
        related = _require_string_list(
            record.get("related_research_ids"), "related research ids"
        )
        for related_id in related:
            validate_memory_id(related_id)
        relation = record.get("relation")
        if relation is not None and not isinstance(relation, str):
            raise ValueError("research relation must be a string or null")
        if not isinstance(record.get("metadata"), dict):
            raise ValueError("research metadata must be an object")
        semantic = {
            key: record[key]
            for key in required.difference(
                {"research_id", "created_at", "semantic_sha256", "record_sha256"}
            )
        }
        semantic_sha = sha256_json(semantic)
        if record.get("semantic_sha256") != semantic_sha:
            raise ValueError("research semantic hash mismatch")
        if research_id != semantic_sha[:12]:
            raise ValueError("research content id mismatch")
        record_without_hash = {
            key: value for key, value in record.items() if key != "record_sha256"
        }
        if record.get("record_sha256") != sha256_json(record_without_hash):
            raise ValueError("research record hash mismatch")
        return record

    def add_research(
        self,
        payload: dict[str, Any],
        *,
        actor: str,
        task_binding: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("research input must be one object")
        if "id" in payload or "research_id" in payload:
            raise ValueError("research ids are generated internally")
        actor = _require_nonempty_text(actor, "research actor")
        kind = payload.get("kind", "direction")
        if not isinstance(kind, str) or kind not in V5_RESEARCH_KINDS:
            raise ValueError(f"unsupported V5 research kind: {kind!r}")
        status = payload.get("status", "open")
        if not isinstance(status, str) or status not in MEMORY_STATUSES:
            raise ValueError(f"unsupported V5 research status: {status!r}")
        claim = _require_nonempty_text(payload.get("claim"), "research claim")
        content = payload.get("content", payload.get("body", ""))
        rationale = payload.get("rationale", "")
        source = payload.get("source", "")
        for label, value in (
            ("content", content),
            ("rationale", rationale),
            ("source", source),
        ):
            if not isinstance(value, str):
                raise ValueError(f"research {label} must be a string")
        dependencies = _require_string_list(
            payload.get("dependencies", []), "research dependencies"
        )
        dependencies = sorted(dict.fromkeys(validate_fact_id(item) for item in dependencies))
        active_facts = set(self.store.fact_ids())
        missing_facts = sorted(set(dependencies).difference(active_facts))
        if missing_facts:
            raise ValueError(
                "research dependencies are not active V5 Facts: "
                + ", ".join(missing_facts)
            )
        related = _require_string_list(
            payload.get("related_research_ids", []), "related research ids"
        )
        related = sorted(dict.fromkeys(validate_memory_id(item) for item in related))
        for related_id in related:
            self._research_record(related_id)
        relation = payload.get("relation")
        if relation is not None:
            relation = _require_nonempty_text(relation, "research relation")
        if bool(related) != bool(relation):
            raise ValueError(
                "research relation and related_research_ids must be supplied together"
            )
        reserved = {
            "kind",
            "status",
            "claim",
            "content",
            "body",
            "rationale",
            "dependencies",
            "source",
            "relation",
            "related_research_ids",
        }
        metadata = {
            key: value for key, value in payload.items() if key not in reserved
        }
        if task_binding is not None:
            if not isinstance(task_binding, dict) or any(
                not isinstance(key, str) or not isinstance(value, str)
                for key, value in task_binding.items()
            ):
                raise ValueError("research task binding must map strings to strings")
            metadata["task_binding"] = dict(sorted(task_binding.items()))
        semantic = {
            "schema_version": 5,
            "policy_revision": V5_POLICY_REVISION,
            "project_id": self.store.project_id(),
            "kind": kind,
            "status": status,
            "claim": claim,
            "content": content,
            "rationale": rationale,
            "dependencies": dependencies,
            "source": source,
            "relation": relation,
            "related_research_ids": related,
            "metadata": metadata,
            "actor": actor,
        }
        semantic_sha = sha256_json(semantic)
        research_id = semantic_sha[:12]
        created_at = _utc_now()
        record_without_hash = {
            **semantic,
            "research_id": research_id,
            "created_at": created_at,
            "semantic_sha256": semantic_sha,
        }
        record = {
            **record_without_hash,
            "record_sha256": sha256_json(record_without_hash),
        }
        path = self._research_path(research_id)
        with self.store.v5_mutation_lock(command="research-add"):
            if path.exists():
                existing = self._research_record(research_id)
                if existing["semantic_sha256"] != semantic_sha:
                    raise ValueError(f"research id collision at {path}")
                return existing
            self.store._write_json_once(path, record)
        return record

    def update_research(
        self,
        research_id: str,
        *,
        status: str,
        actor: str,
        note: str = "",
        resolution_fact_id: str | None = None,
        claim_relation: str | None = None,
        related_fact_id: str | None = None,
    ) -> dict[str, Any]:
        target = self._research_record(research_id)
        if status not in MEMORY_STATUSES:
            raise ValueError(f"unsupported V5 research status: {status}")
        if not isinstance(note, str):
            raise ValueError("research disposition note must be a string")
        if resolution_fact_id is not None:
            resolution_fact_id = validate_fact_id(resolution_fact_id)
            self.store.get_fact(resolution_fact_id)
        if claim_relation is not None:
            if claim_relation not in CLAIM_RELATIONS or related_fact_id is None:
                raise ValueError(
                    "research disposition claim relation requires a related Fact"
                )
            related_fact_id = validate_fact_id(related_fact_id)
            self.store.get_fact(related_fact_id)
        elif related_fact_id is not None:
            raise ValueError("related Fact requires a claim relation")
        return self.add_research(
            {
                "kind": "disposition",
                "status": status,
                "claim": f"Disposition of {research_id}: {target['claim']}",
                "content": note,
                "relation": "disposes",
                "related_research_ids": [research_id],
                "target_research_id": research_id,
                "disposition_status": status,
                "resolution_fact_id": resolution_fact_id,
                "claim_relation": claim_relation,
                "related_fact_id": related_fact_id,
            },
            actor=actor,
        )

    def create_repair_round(
        self,
        research_id: str,
        *,
        trigger_research_id: str | None = None,
        actor: str = "v5-orchestrator",
        host_task_scope_id: str | None = None,
    ) -> dict[str, Any]:
        """Append one repair branch and plan exactly one bounded work unit."""

        source = self._research_record(research_id)
        related_ids = [source["research_id"]]
        trigger: dict[str, Any] | None = None
        if trigger_research_id is not None:
            trigger = self._research_record(trigger_research_id)
            related_ids.append(trigger["research_id"])
        related_ids = sorted(dict.fromkeys(related_ids))
        copied_metadata = {
            key: source["metadata"][key]
            for key in (
                "source_claim_id",
                "convention_profile_ids",
                "campaign_id",
                "blackboard_write_space_ids",
                "obligations",
                "stop_conditions",
                "goal_relation",
            )
            if key in source["metadata"]
        }
        trigger_note = (
            f" Triggered by Research {trigger['research_id']}: {trigger['claim']}"
            if trigger is not None
            else ""
        )
        repair = self.add_research(
            {
                "kind": "repair",
                "status": "open",
                "claim": f"Repair branch for: {source['claim']}",
                "content": (
                    "Re-examine the bounded claim while preserving prior "
                    "counterexamples, challenges, and evidence."
                    + trigger_note
                ),
                "rationale": (
                    "A new cumulative branch is required; the source Research "
                    "record remains immutable and readable."
                ),
                "dependencies": source["dependencies"],
                "source": f"research:{source['research_id']}",
                "relation": "repairs",
                "related_research_ids": related_ids,
                "repair_of_research_id": source["research_id"],
                "trigger_research_id": (
                    trigger["research_id"] if trigger is not None else None
                ),
                **copied_metadata,
            },
            actor=actor,
        )
        planned = self.create_round(
            workers=1,
            mode="auto",
            research_ids=[repair["research_id"]],
            host_task_scope_id=host_task_scope_id,
        )
        return {
            **planned,
            "memory_id": repair["research_id"],
            "research_id": repair["research_id"],
            "repair_of_research_id": source["research_id"],
            "trigger_research_id": (
                trigger["research_id"] if trigger is not None else None
            ),
        }

    def research_records(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        if not self.research_entries_dir.exists():
            return records
        for path in sorted(self.research_entries_dir.glob("*.json")):
            if path.is_symlink() or not path.is_file():
                raise ValueError("research ledger contains an unsafe entry")
            record = self.store._read_json(path)
            records.append(self._validate_research_record(record, path=path))
        return records

    def novelty_record(
        self,
        payload: dict[str, Any],
        *,
        actor: str,
    ) -> str:
        """Append query-bounded novelty evidence for V5 Research or Fact.

        Novelty remains nontruth evidence.  The adapter deliberately reuses the
        compact 0.3.6 ledger instead of creating a second novelty subsystem.
        """

        if not isinstance(payload, dict):
            raise ValueError("novelty record must be one object")
        required = {
            "subject_kind",
            "subject_id",
            "corpus",
            "query",
            "status",
            "hits",
        }
        if set(payload).difference(required | {"notes"}) or not required.issubset(
            payload
        ):
            raise ValueError("novelty record fields are not exact")
        subject_kind = _require_nonempty_text(
            payload.get("subject_kind"), "novelty subject kind"
        )
        subject_id = _require_nonempty_text(
            payload.get("subject_id"), "novelty subject id"
        )
        if subject_kind in {"research", "memory"}:
            subject_kind = "research"
            subject_id = validate_memory_id(subject_id)
            self._research_record(subject_id)
        elif subject_kind == "fact":
            subject_id = validate_fact_id(subject_id)
            if subject_id not in set(self.store.fact_ids()).union(
                self.revoked_fact_ids()
            ):
                raise ValueError("novelty subject is not a known V5 Fact")
        else:
            raise ValueError(
                "V5 novelty subject_kind must be research, memory, or fact"
            )
        corpus = _require_nonempty_text(payload.get("corpus"), "novelty corpus")
        query = _require_nonempty_text(payload.get("query"), "novelty query")
        status = _require_nonempty_text(payload.get("status"), "novelty status")
        if status not in NOVELTY_STATUSES:
            raise ValueError(
                "novelty status must be one of: "
                + ", ".join(sorted(NOVELTY_STATUSES))
            )
        hits = payload.get("hits")
        if not isinstance(hits, list):
            raise ValueError("novelty hits must be a list")
        normalized_hits: list[dict[str, str]] = []
        for index, hit in enumerate(hits, 1):
            if not isinstance(hit, dict) or set(hit) != {
                "title",
                "locator",
                "relation",
            }:
                raise ValueError(
                    f"novelty hits[{index}] fields are not exact"
                )
            relation = _require_nonempty_text(
                hit.get("relation"), f"novelty hits[{index}] relation"
            )
            if relation not in {"exact", "partial", "background"}:
                raise ValueError(
                    f"novelty hits[{index}] relation must be exact, partial, "
                    "or background"
                )
            normalized_hits.append(
                {
                    "title": _require_nonempty_text(
                        hit.get("title"), f"novelty hits[{index}] title"
                    ),
                    "locator": _require_nonempty_text(
                        hit.get("locator"), f"novelty hits[{index}] locator"
                    ),
                    "relation": relation,
                }
            )
        if status == "known" and not any(
            hit["relation"] == "exact" for hit in normalized_hits
        ):
            raise ValueError("novelty status known requires an exact hit")
        if status == "no_exact_match_found" and any(
            hit["relation"] == "exact" for hit in normalized_hits
        ):
            raise ValueError("no_exact_match_found conflicts with an exact hit")
        notes = payload.get("notes", "")
        if not isinstance(notes, str):
            raise ValueError("novelty notes must be a string")
        semantic = {
            "subject_kind": subject_kind,
            "subject_id": subject_id,
            "corpus": corpus,
            "query": query,
            "status": status,
            "hits": normalized_hits,
            "notes": notes,
            "actor": _require_nonempty_text(actor, "novelty actor"),
        }
        event_id = sha256_json(semantic)
        event = {
            **semantic,
            "event": "novelty-query",
            "event_id": event_id,
            "searched_at": _utc_now(),
        }
        with self.store.v5_mutation_lock(command="novelty-record"):
            self.store._append_jsonl_once(
                self.store.novelty_log,
                event,
                event_id=event_id,
            )
        return event_id

    def novelty_status(self, subject_id: str) -> list[dict[str, Any]]:
        if FACT_ID_RE.fullmatch(subject_id):
            subject_kind = "fact"
        elif MEMORY_ID_RE.fullmatch(subject_id):
            subject_kind = "research"
        else:
            raise ValueError("novelty subject id must be a Fact or Research id")
        return [
            event
            for event in self.store._read_jsonl(self.store.novelty_log)
            if event.get("subject_kind") == subject_kind
            and event.get("subject_id") == subject_id
        ]

    def _audit_novelty(self) -> list[str]:
        errors: list[str] = []
        events = self.store._read_jsonl(self.store.novelty_log)
        known_facts = set(self.store.fact_ids()).union(self.revoked_fact_ids())
        known_research = {
            record["research_id"] for record in self.research_records()
        }
        for index, event in enumerate(events, 1):
            try:
                if event.get("event") != "novelty-query":
                    raise ValueError("invalid event kind")
                subject_kind = event.get("subject_kind")
                subject_id = event.get("subject_id")
                if subject_kind == "fact":
                    validate_fact_id(subject_id)
                    if subject_id not in known_facts:
                        raise ValueError("unknown Fact subject")
                elif subject_kind == "research":
                    validate_memory_id(subject_id)
                    if subject_id not in known_research:
                        raise ValueError("unknown Research subject")
                else:
                    raise ValueError("invalid V5 subject_kind")
                if event.get("status") not in NOVELTY_STATUSES:
                    raise ValueError("invalid novelty status")
                for field_name in (
                    "corpus",
                    "query",
                    "notes",
                    "actor",
                    "searched_at",
                ):
                    if not isinstance(event.get(field_name), str):
                        raise ValueError(f"invalid {field_name}")
                hits = event.get("hits")
                if not isinstance(hits, list):
                    raise ValueError("hits is not a list")
                for hit in hits:
                    if not isinstance(hit, dict) or set(hit) != {
                        "title",
                        "locator",
                        "relation",
                    }:
                        raise ValueError("invalid novelty hit")
                    if hit["relation"] not in {"exact", "partial", "background"}:
                        raise ValueError("invalid novelty hit relation")
                    _require_nonempty_text(hit["title"], "novelty hit title")
                    _require_nonempty_text(hit["locator"], "novelty hit locator")
                semantic = {
                    key: event.get(key)
                    for key in (
                        "subject_kind",
                        "subject_id",
                        "corpus",
                        "query",
                        "status",
                        "hits",
                        "notes",
                        "actor",
                    )
                }
                if event.get("event_id") != sha256_json(semantic):
                    raise ValueError("event_id mismatch")
            except Exception as exc:
                errors.append(f"event {index}: {exc}")
        return errors

    def _release_research_records(
        self,
        explicit_records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Include linked adverse work without creating another review layer.

        A release author chooses its constructive Research anchors.  Their
        ancestor chain identifies the research branch.  Every adverse record
        that directly targets that branch is then bound automatically, so an
        existing challenge cannot be hidden by omitting its id from the input.
        Unrelated project-wide challenges remain outside the release.
        """

        records = {item["research_id"]: item for item in self.research_records()}
        selected = {item["research_id"] for item in explicit_records}
        branch = set(selected)
        pending = list(selected)
        while pending:
            current = records[pending.pop()]
            for related_id in current["related_research_ids"]:
                if related_id not in branch:
                    branch.add(related_id)
                    pending.append(related_id)

        adverse_kinds = {"challenge", "counterexample", "obstacle"}
        changed = True
        while changed:
            changed = False
            for research_id, record in records.items():
                if record["kind"] not in adverse_kinds or research_id in selected:
                    continue
                if research_id in branch or set(record["related_research_ids"]).intersection(
                    branch
                ):
                    selected.add(research_id)
                    branch.add(research_id)
                    pending = list(record["related_research_ids"])
                    while pending:
                        related_id = pending.pop()
                        if related_id in branch:
                            continue
                        branch.add(related_id)
                        pending.extend(records[related_id]["related_research_ids"])
                    changed = True
        return [records[research_id] for research_id in sorted(selected)]

    def frontier(
        self,
        *,
        limit: int = 10,
        include_history: bool = False,
    ) -> list[dict[str, Any]]:
        if limit < 1:
            raise ValueError("frontier limit must be positive")
        bases: dict[str, dict[str, Any]] = {}
        dispositions: dict[str, dict[str, Any]] = {}
        for record in self.research_records():
            if record["kind"] == "disposition":
                target_id = record["metadata"].get("target_research_id")
                if isinstance(target_id, str):
                    previous = dispositions.get(target_id)
                    if previous is None or record["created_at"] > previous["created_at"]:
                        dispositions[target_id] = record
                continue
            bases[record["research_id"]] = record
        visible: list[dict[str, Any]] = []
        for research_id, record in bases.items():
            projection = dict(record)
            disposition = dispositions.get(research_id)
            if disposition is not None:
                projection["status"] = disposition["metadata"][
                    "disposition_status"
                ]
                projection["latest_disposition_id"] = disposition["research_id"]
                projection["latest_disposition_note"] = disposition["content"]
            if not include_history and projection["status"] not in ACTIVE_MEMORY_STATUSES:
                continue
            projection["id"] = research_id
            visible.append(projection)
        visible.sort(key=lambda item: (item["created_at"], item["research_id"]))
        return visible[:limit]

    def _work_mode(self, entry: dict[str, Any], index: int) -> str:
        kind = entry["kind"]
        if kind in {"counterexample", "obstacle", "challenge"}:
            return "refute"
        if kind == "computation":
            return "compute"
        if kind == "literature":
            return "literature"
        return WORK_MODES[index % len(WORK_MODES)] if kind == "plan" else "prove"

    def _snapshot_for_round(self) -> dict[str, Any]:
        blackboard = self.store.blackboard()
        nodes = blackboard.nodes()
        spaces = sorted(
            node_id
            for node_id, node in nodes.items()
            if node.get("node_type") == "space"
        )
        if not spaces:
            raise ValueError("V5 round planning requires one Blackboard space")
        return blackboard.snapshot(
            query={
                "seed_node_ids": [spaces[0]],
                "direction": "both",
                "max_hops": 3,
                "edge_type_allowlist": ["*"],
                "node_type_allowlist": ["*"],
                "node_budget": 256,
                "edge_budget": 512,
            },
            actor="v5-orchestrator",
        )

    def _task_card_path(self, round_id: str, assignment_id: str) -> Path:
        return (
            self.store.rounds_dir
            / validate_round_id(round_id)
            / "task-cards"
            / f"{validate_assignment_id(assignment_id)}.json"
        )

    def _project_background_binding(
        self,
    ) -> dict[str, Any] | None:
        """Read the one summary by default, but never generate it implicitly."""

        path = self.store.root / V5_PROJECT_BACKGROUND_FILENAME
        if path.is_symlink():
            raise ValueError("PROJECT_BACKGROUND.md may not be a symlink")
        if not path.exists():
            return None
        if not path.is_file():
            raise ValueError(
                "PROJECT_BACKGROUND.md must be a regular file; summary "
                "generation is never automatic"
            )
        raw = path.read_bytes()
        if len(raw) > V5_MAX_PROJECT_BACKGROUND_BYTES:
            raise ValueError("PROJECT_BACKGROUND.md exceeds the 256 KiB task-card limit")
        try:
            body = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("PROJECT_BACKGROUND.md must be UTF-8") from exc
        if not body.strip():
            raise ValueError("PROJECT_BACKGROUND.md must have a nonempty body")
        return {
            "read_policy": "default_if_present",
            "relpath": V5_PROJECT_BACKGROUND_FILENAME,
            "sha256": sha256_bytes(raw),
            "body": body,
            "truth_effect": "nontruth_background_only",
            "load_bearing_rule": "return_to_exact_cited_source",
        }

    def validate_task_card(
        self,
        card: Any,
        *,
        expected_path: Path | None = None,
    ) -> dict[str, Any]:
        if not isinstance(card, dict):
            raise ValueError("V5 task card must be one object")
        required = {
            "schema_version",
            "policy_revision",
            "project_id",
            "round_id",
            "assignment_id",
            "worker_id",
            "research_id",
            "work_mode",
            "requested_claim_relation",
            "source_claim_id",
            "convention_profile_ids",
            "campaign_id",
            "control_plane",
            "mathematical_state",
            "blackboard_view",
            "narrative_plane",
            "obligations",
            "stop_conditions",
            "artifact_capability",
            "return_contract",
            "reasoning_mode_binding",
            "task_card_semantic_sha256",
        }
        if set(card) != required:
            raise ValueError("V5 task card fields are not exact")
        if (
            card.get("schema_version") != 5
            or card.get("policy_revision") != V5_POLICY_REVISION
            or card.get("project_id") != self.store.project_id()
        ):
            raise ValueError("V5 task card schema/policy/project mismatch")
        round_id = validate_round_id(
            _require_nonempty_text(card.get("round_id"), "task-card round id")
        )
        assignment_id = validate_assignment_id(
            _require_nonempty_text(
                card.get("assignment_id"), "task-card assignment id"
            )
        )
        validate_memory_id(
            _require_nonempty_text(card.get("research_id"), "task-card research id")
        )
        if card.get("work_mode") not in WORK_MODES:
            raise ValueError("V5 task card work mode is invalid")
        if card.get("requested_claim_relation") not in CLAIM_RELATIONS:
            raise ValueError("V5 task card claim relation is invalid")
        if not isinstance(card.get("worker_id"), str):
            raise ValueError("V5 task card worker id must be a string")
        if card.get("source_claim_id") is not None and not isinstance(
            card.get("source_claim_id"), str
        ):
            raise ValueError("V5 task card source claim id is invalid")
        convention_ids = _require_string_list(
            card.get("convention_profile_ids"), "task-card convention profile ids"
        )
        for convention_id in convention_ids:
            self.store.claims().show_convention(convention_id)
        if card.get("campaign_id") is not None and not isinstance(
            card.get("campaign_id"), str
        ):
            raise ValueError("V5 task card campaign id is invalid")
        if card.get("campaign_id") is not None:
            self.store.campaigns().status(card["campaign_id"])
        if card.get("source_claim_id") is not None:
            self.store.claims().show_claim(card["source_claim_id"])
        for name in (
            "control_plane",
            "mathematical_state",
            "blackboard_view",
            "narrative_plane",
            "artifact_capability",
            "return_contract",
            "reasoning_mode_binding",
        ):
            if not isinstance(card.get(name), dict):
                raise ValueError(f"V5 task card {name} must be an object")
        if card["control_plane"].get("plane") != "control":
            raise ValueError("V5 control-plane marker is missing")
        if card["mathematical_state"].get("plane") != "mathematical_state":
            raise ValueError("V5 mathematical-state-plane marker is missing")
        if card["narrative_plane"].get("plane") != "narrative":
            raise ValueError("V5 narrative-plane marker is missing")
        if (
            card["mathematical_state"].get("blackboard_snapshot_id")
            != card["blackboard_view"].get("snapshot_id")
            or card["mathematical_state"].get("blackboard_snapshot_sha256")
            != card["blackboard_view"].get("snapshot_sha256")
        ):
            raise ValueError("V5 task card snapshot projections disagree")
        research_context = card["mathematical_state"].get("research_context")
        if not isinstance(research_context, list) or any(
            not isinstance(item, dict) for item in research_context
        ):
            raise ValueError("V5 task card research_context must be object entries")
        context_ids: list[str] = []
        for item in research_context:
            expected_fields = {
                "research_id",
                "record_sha256",
                "kind",
                "status",
                "claim",
                "content",
                "rationale",
                "actor",
            }
            if set(item) != expected_fields:
                raise ValueError("V5 task card research_context fields are not exact")
            related = self._research_record(item["research_id"])
            expected = {key: related[key] for key in expected_fields}
            if item != expected:
                raise ValueError("V5 task card research_context bytes/hash mismatch")
            context_ids.append(item["research_id"])
        source_research = self._research_record(card["research_id"])
        if context_ids != source_research["related_research_ids"]:
            raise ValueError(
                "V5 task card research_context does not exactly match Research links"
            )
        if "project_background" not in card["mathematical_state"]:
            raise ValueError("V5 task card project_background binding is missing")
        background = card["mathematical_state"]["project_background"]
        if background is not None:
            expected_fields = {
                "read_policy",
                "relpath",
                "sha256",
                "body",
                "truth_effect",
                "load_bearing_rule",
            }
            if not isinstance(background, dict) or set(background) != expected_fields:
                raise ValueError("V5 task-card project background fields are not exact")
            if (
                background["read_policy"] != "default_if_present"
                or background["relpath"] != V5_PROJECT_BACKGROUND_FILENAME
                or background["truth_effect"] != "nontruth_background_only"
                or background["load_bearing_rule"]
                != "return_to_exact_cited_source"
                or not isinstance(background["body"], str)
                or not background["body"].strip()
                or background["sha256"]
                != sha256_bytes(background["body"].encode("utf-8"))
            ):
                raise ValueError("V5 task-card project background binding is invalid")
        if not isinstance(card.get("obligations"), list) or any(
            not isinstance(item, dict) for item in card["obligations"]
        ):
            raise ValueError("V5 task card obligations must be objects")
        _require_string_list(card.get("stop_conditions"), "task-card stop conditions")
        semantic = {
            key: value
            for key, value in card.items()
            if key != "task_card_semantic_sha256"
        }
        if card.get("task_card_semantic_sha256") != sha256_json(semantic):
            raise ValueError("V5 task card semantic hash mismatch")
        if expected_path is not None:
            canonical = self._task_card_path(round_id, assignment_id)
            if expected_path.resolve() != canonical.resolve():
                raise ValueError("V5 task card path is noncanonical")
        return card

    def _compact_prompt(
        self,
        *,
        card: dict[str, Any],
        task_card_sha256: str,
    ) -> str:
        return (
            "# Chalxius V5 worker assignment\n\n"
            f"Round: `{card['round_id']}`  \n"
            f"Assignment: `{card['assignment_id']}`  \n"
            f"Task-card SHA-256: `{task_card_sha256}`\n\n"
            "Read the immutable task card for exact capabilities. Use only its frozen "
            "mathematical-state snapshot. Keep rationale and intuition in the bounded "
            "narrative return fields; do not move them into the control channel.\n\n"
            f"Research claim: {card['narrative_plane']['claim']}\n\n"
            f"Write the exact return to `{card['return_contract']['return_relpath']}` "
            "and hand off only its SHA-256 plus status.\n"
        )

    def create_round(
        self,
        *,
        workers: int,
        mode: str = "auto",
        research_ids: list[str] | None = None,
        host_task_scope_id: str | None = None,
    ) -> dict[str, Any]:
        if workers < 1:
            raise ValueError("workers must be positive")
        if mode != "auto" and mode not in WORK_MODES:
            raise ValueError(f"unsupported work mode: {mode}")
        if host_task_scope_id is not None:
            host_task_scope_id = _require_nonempty_text(
                host_task_scope_id, "host task scope id"
            )
        if research_ids is not None:
            normalized_ids = [validate_memory_id(item) for item in research_ids]
            if len(set(normalized_ids)) != len(normalized_ids):
                raise ValueError("requested research ids must be unique")
            if workers != len(normalized_ids):
                raise ValueError(
                    "--workers must equal the number of explicit research ids"
                )
            by_id = {
                item["research_id"]: item
                for item in self.frontier(
                    limit=max(self._json_count(self.research_entries_dir), workers)
                )
            }
            missing = sorted(set(normalized_ids).difference(by_id))
            if missing:
                raise ValueError(
                    "not active V5 research entries: " + ", ".join(missing)
                )
            selected = [by_id[item] for item in normalized_ids]
        else:
            selected = self.frontier(limit=workers)
        if len(selected) != workers:
            raise ValueError(
                f"requested {workers} workers but only {len(selected)} active "
                "V5 research entries are available"
            )

        with self.store.v5_mutation_lock(command="plan-round"):
            snapshot = self._snapshot_for_round()
            project_background = self._project_background_binding()
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            round_id = (
                f"round-{stamp}-"
                f"{sha256_json([[item['research_id'] for item in selected], time.time_ns()])[:8]}"
            )
            validate_round_id(round_id)
            round_dir = self.store.rounds_dir / round_id
            assignments_dir = round_dir / "assignments"
            task_cards_dir = round_dir / "task-cards"
            returns_dir = round_dir / "returns"
            artifacts_dir = round_dir / "artifacts"
            work_dir = round_dir / "work"
            for directory in (
                assignments_dir,
                task_cards_dir,
                returns_dir,
                artifacts_dir,
                work_dir,
            ):
                directory.mkdir(parents=True, exist_ok=False)

            mode_status = self.store.reasoning_modes().status()
            reasoning_binding = {
                "reasoning_mode": mode_status["reasoning_mode"],
                "reasoning_mode_event_id": mode_status[
                    "reasoning_mode_event_id"
                ],
                "reasoning_mode_policy_sha256": mode_status[
                    "reasoning_mode_policy_sha256"
                ],
                "fact_admission_contract_sha256": mode_status[
                    "fact_admission_contract_sha256"
                ],
                "effect": "future_research_budget_only",
            }
            all_nodes = self.store.blackboard().nodes()
            default_spaces = sorted(
                node_id
                for node_id, node in all_nodes.items()
                if node.get("node_type") == "space"
            )[:1]
            assignments: list[dict[str, Any]] = []
            for index, entry in enumerate(selected, 1):
                work_mode = mode if mode != "auto" else self._work_mode(entry, index - 1)
                assignment_id = f"a{index:02d}-{entry['research_id']}-{work_mode}"
                validate_assignment_id(assignment_id)
                prompt_relpath = f"rounds/{round_id}/assignments/{assignment_id}.md"
                task_card_relpath = f"rounds/{round_id}/task-cards/{assignment_id}.json"
                return_relpath = f"rounds/{round_id}/returns/{assignment_id}.json"
                artifact_dir_relpath = f"rounds/{round_id}/artifacts/{assignment_id}"
                work_dir_relpath = f"rounds/{round_id}/work/{assignment_id}"
                requested_spaces = entry["metadata"].get(
                    "blackboard_write_space_ids", default_spaces
                )
                write_spaces = _require_string_list(
                    requested_spaces, "research Blackboard write spaces"
                )
                for space_id in write_spaces:
                    if all_nodes.get(space_id, {}).get("node_type") != "space":
                        raise ValueError(
                            "research Blackboard write spaces must name existing spaces"
                        )
                obligations = entry["metadata"].get("obligations", [])
                if not isinstance(obligations, list) or any(
                    not isinstance(item, dict) for item in obligations
                ):
                    raise ValueError("research obligations must be objects")
                stop_conditions = _require_string_list(
                    entry["metadata"].get("stop_conditions", []),
                    "research stop conditions",
                )
                convention_ids = _require_string_list(
                    entry["metadata"].get("convention_profile_ids", []),
                    "research convention profile ids",
                )
                for convention_id in convention_ids:
                    self.store.claims().show_convention(convention_id)
                source_claim_id = entry["metadata"].get("source_claim_id")
                if source_claim_id is not None:
                    if not isinstance(source_claim_id, str):
                        raise ValueError("research source claim id must be a string")
                    self.store.claims().show_claim(source_claim_id)
                campaign_id = entry["metadata"].get("campaign_id")
                if campaign_id is not None:
                    if not isinstance(campaign_id, str):
                        raise ValueError("research campaign id must be a string")
                    self.store.campaigns().status(campaign_id)
                requested_relation = entry["metadata"].get(
                    "goal_relation", "proves"
                )
                if requested_relation not in CLAIM_RELATIONS:
                    raise ValueError("research goal relation is invalid")
                predecessor_interfaces = [
                    self.store.statement_interface(
                        fact_id, materialize=False
                    )
                    for fact_id in entry["dependencies"]
                ]
                research_context = []
                for related_id in entry["related_research_ids"]:
                    related_record = self._research_record(related_id)
                    research_context.append(
                        {
                            key: related_record[key]
                            for key in (
                                "research_id",
                                "record_sha256",
                                "kind",
                                "status",
                                "claim",
                                "content",
                                "rationale",
                                "actor",
                            )
                        }
                    )
                card_semantic = {
                    "schema_version": 5,
                    "policy_revision": V5_POLICY_REVISION,
                    "project_id": self.store.project_id(),
                    "round_id": round_id,
                    "assignment_id": assignment_id,
                    "worker_id": assignment_id,
                    "research_id": entry["research_id"],
                    "work_mode": work_mode,
                    "requested_claim_relation": requested_relation,
                    "source_claim_id": source_claim_id,
                    "convention_profile_ids": convention_ids,
                    "campaign_id": campaign_id,
                    "control_plane": {
                        "plane": "control",
                        "prompt_relpath": prompt_relpath,
                        "allowed_followups": [
                            "continue",
                            "clarify_control",
                            "stop",
                        ],
                        "final_handoff_fields": [
                            "assignment_id",
                            "return_sha256",
                            "status",
                        ],
                        "host_task_scope_id": host_task_scope_id,
                    },
                    "mathematical_state": {
                        "plane": "mathematical_state",
                        "blackboard_snapshot_id": snapshot["snapshot_id"],
                        "blackboard_snapshot_sha256": snapshot[
                            "snapshot_sha256"
                        ],
                        "predecessor_interfaces": predecessor_interfaces,
                        "research_context": research_context,
                        "project_background": project_background,
                        "read_space_ids": default_spaces,
                        "write_space_ids": write_spaces,
                    },
                    "blackboard_view": {
                        "snapshot_id": snapshot["snapshot_id"],
                        "snapshot_sha256": snapshot["snapshot_sha256"],
                    },
                    "narrative_plane": {
                        "plane": "narrative",
                        "claim": entry["claim"],
                        "rationale": entry["rationale"],
                        "summary_word_cap": 400,
                        "intuition_word_cap": 400,
                        "limitations_word_cap": 400,
                    },
                    "obligations": [dict(item) for item in obligations],
                    "stop_conditions": stop_conditions,
                    "artifact_capability": {
                        "artifact_dir_relpath": artifact_dir_relpath,
                        "work_dir_relpath": work_dir_relpath,
                        "max_files": 256,
                        "max_file_bytes": 16 * 1024 * 1024,
                        "max_total_bytes": 64 * 1024 * 1024,
                    },
                    "return_contract": {
                        "return_relpath": return_relpath,
                        "allowed_outcomes": sorted(V5_RETURN_OUTCOMES),
                        "hash_contract": (
                            "sha256_of_exact_return_bytes_reported_in_final_handoff"
                        ),
                    },
                    "reasoning_mode_binding": reasoning_binding,
                }
                card = {
                    **card_semantic,
                    "task_card_semantic_sha256": sha256_json(card_semantic),
                }
                card_path = self.store.root / task_card_relpath
                self.store._write_json_once(card_path, card)
                self.validate_task_card(card, expected_path=card_path)
                task_card_sha = sha256_bytes(card_path.read_bytes())
                prompt = self._compact_prompt(
                    card=card, task_card_sha256=task_card_sha
                )
                prompt_path = self.store.root / prompt_relpath
                self.store._write_text_atomic(prompt_path, prompt)
                assignment_semantic = {
                    "assignment_id": assignment_id,
                    "research_id": entry["research_id"],
                    "worker_id": assignment_id,
                    "work_mode": work_mode,
                    "prompt_relpath": prompt_relpath,
                    "prompt_sha256": sha256_bytes(prompt_path.read_bytes()),
                    "task_card_relpath": task_card_relpath,
                    "task_card_sha256": task_card_sha,
                    "return_relpath": return_relpath,
                    "artifact_dir_relpath": artifact_dir_relpath,
                    "work_dir_relpath": work_dir_relpath,
                    "blackboard_snapshot_id": snapshot["snapshot_id"],
                    "blackboard_snapshot_sha256": snapshot["snapshot_sha256"],
                }
                assignment = {
                    **assignment_semantic,
                    "assignment_sha256": sha256_json(assignment_semantic),
                }
                self.store._write_json_once(
                    assignments_dir / f"{assignment_id}.json", assignment
                )
                assignments.append(assignment)
            manifest_semantic = {
                "schema_version": 5,
                "policy_revision": V5_POLICY_REVISION,
                "project_id": self.store.project_id(),
                "round_id": round_id,
                "created_at": _utc_now(),
                "blackboard_snapshot_id": snapshot["snapshot_id"],
                "blackboard_snapshot_sha256": snapshot["snapshot_sha256"],
                "reasoning_mode_binding": reasoning_binding,
                "contribution_policy": "independent_ingest_local_quarantine",
                "assignments": assignments,
            }
            manifest = {
                **manifest_semantic,
                "manifest_sha256": sha256_json(manifest_semantic),
            }
            self.store._write_json_once(round_dir / "round.json", manifest)
        return self.round_status(round_id)

    def _round_manifest(self, round_id: str) -> tuple[Path, dict[str, Any]]:
        round_id = validate_round_id(round_id)
        round_dir = self.store.rounds_dir / round_id
        path = round_dir / "round.json"
        if path.is_symlink() or not path.is_file():
            raise KeyError(f"unknown V5 round: {round_id}")
        manifest = self.store._read_json(path)
        required = {
            "schema_version",
            "policy_revision",
            "project_id",
            "round_id",
            "created_at",
            "blackboard_snapshot_id",
            "blackboard_snapshot_sha256",
            "reasoning_mode_binding",
            "contribution_policy",
            "assignments",
            "manifest_sha256",
        }
        if set(manifest) != required:
            raise ValueError("V5 round manifest fields are not exact")
        if (
            manifest.get("schema_version") != 5
            or manifest.get("policy_revision") != V5_POLICY_REVISION
            or manifest.get("project_id") != self.store.project_id()
            or manifest.get("round_id") != round_id
            or manifest.get("contribution_policy")
            != "independent_ingest_local_quarantine"
        ):
            raise ValueError("V5 round schema/policy/project/id mismatch")
        semantic = {
            key: value
            for key, value in manifest.items()
            if key != "manifest_sha256"
        }
        if manifest.get("manifest_sha256") != sha256_json(semantic):
            raise ValueError("V5 round manifest hash mismatch")
        assignments = manifest.get("assignments")
        if not isinstance(assignments, list) or not assignments:
            raise ValueError("V5 round assignments must be nonempty")
        seen: set[str] = set()
        for assignment in assignments:
            if not isinstance(assignment, dict):
                raise ValueError("V5 round assignment must be an object")
            assignment_id = validate_assignment_id(
                _require_nonempty_text(
                    assignment.get("assignment_id"), "V5 assignment id"
                )
            )
            if assignment_id in seen:
                raise ValueError("V5 round assignment ids must be unique")
            seen.add(assignment_id)
            assignment_semantic = {
                key: value
                for key, value in assignment.items()
                if key != "assignment_sha256"
            }
            if assignment.get("assignment_sha256") != sha256_json(
                assignment_semantic
            ):
                raise ValueError("V5 assignment hash mismatch")
            sidecar = round_dir / "assignments" / f"{assignment_id}.json"
            if (
                sidecar.is_symlink()
                or not sidecar.is_file()
                or self.store._read_json(sidecar) != assignment
            ):
                raise ValueError("V5 assignment sidecar is missing or mismatched")
            card_path = contained_path(
                self.store.root,
                assignment["task_card_relpath"],
                "V5 task card path",
            )
            if (
                card_path.is_symlink()
                or not card_path.is_file()
                or sha256_bytes(card_path.read_bytes())
                != assignment["task_card_sha256"]
            ):
                raise ValueError("V5 task card bytes/hash mismatch")
            self.validate_task_card(
                self.store._read_json(card_path), expected_path=card_path
            )
            prompt_path = contained_path(
                self.store.root,
                assignment["prompt_relpath"],
                "V5 prompt path",
            )
            if (
                prompt_path.is_symlink()
                or not prompt_path.is_file()
                or sha256_bytes(prompt_path.read_bytes())
                != assignment["prompt_sha256"]
            ):
                raise ValueError("V5 prompt bytes/hash mismatch")
        snapshot_path = (
            self.store.blackboard().snapshots_dir
            / manifest["blackboard_snapshot_id"]
            / "manifest.json"
        )
        if (
            snapshot_path.is_symlink()
            or not snapshot_path.is_file()
            or sha256_bytes(snapshot_path.read_bytes())
            != manifest["blackboard_snapshot_sha256"]
        ):
            raise ValueError("V5 round Blackboard snapshot bytes/hash mismatch")
        return round_dir, manifest

    def _assignment(
        self,
        manifest: dict[str, Any],
        assignment_id: str,
    ) -> dict[str, Any]:
        assignment_id = validate_assignment_id(assignment_id)
        matches = [
            item
            for item in manifest["assignments"]
            if item["assignment_id"] == assignment_id
        ]
        if len(matches) != 1:
            raise KeyError(f"unknown V5 assignment: {assignment_id}")
        return matches[0]

    def _quarantine_records(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        if not self.quarantine_dir.exists():
            return records
        for path in sorted(self.quarantine_dir.glob("*.json")):
            if path.is_symlink() or not path.is_file():
                raise ValueError("V5 quarantine contains an unsafe entry")
            payload = self.store._read_json(path)
            if not isinstance(payload, dict) or payload.get("quarantine_id") != path.stem:
                raise ValueError("V5 quarantine path/id mismatch")
            semantic = {
                key: value
                for key, value in payload.items()
                if key not in {"quarantine_id", "created_at", "record_sha256"}
            }
            expected_id = "quarantine-" + sha256_json(semantic)
            if payload.get("quarantine_id") != expected_id:
                raise ValueError("V5 quarantine content id mismatch")
            without_hash = {
                key: value
                for key, value in payload.items()
                if key != "record_sha256"
            }
            if payload.get("record_sha256") != sha256_json(without_hash):
                raise ValueError("V5 quarantine record hash mismatch")
            records.append(payload)
        return records

    def round_status(self, round_id: str) -> dict[str, Any]:
        round_dir, manifest = self._round_manifest(round_id)
        quarantined = {
            item["assignment_id"]: item
            for item in self._quarantine_records()
            if item.get("round_id") == round_id
        }
        assignments: list[dict[str, Any]] = []
        for assignment in manifest["assignments"]:
            assignment_id = assignment["assignment_id"]
            return_path = self.store.root / assignment["return_relpath"]
            receipt_path = round_dir / "returns" / f"{assignment_id}.receipt.json"
            if receipt_path.exists():
                state = "ingested"
            elif assignment_id in quarantined:
                state = "quarantined"
            elif return_path.exists():
                state = "return_present"
            else:
                state = "awaiting_return"
            assignments.append(
                {
                    **assignment,
                    "state": state,
                    "task_card_path": str(
                        self.store.root / assignment["task_card_relpath"]
                    ),
                    "prompt_path": str(
                        self.store.root / assignment["prompt_relpath"]
                    ),
                    "return_path": str(return_path),
                }
            )
        return {
            **manifest,
            "assignments": assignments,
            "ingested_count": sum(
                item["state"] == "ingested" for item in assignments
            ),
            "quarantined_count": sum(
                item["state"] == "quarantined" for item in assignments
            ),
            "awaiting_count": sum(
                item["state"] == "awaiting_return" for item in assignments
            ),
            "round_closure_required": False,
        }

    @staticmethod
    def _readiness_action(
        *,
        category: str,
        object_id: str,
        reason: str,
        suggested_command: str,
        enforced_at: str,
    ) -> dict[str, str]:
        semantic = {
            "category": category,
            "object_id": object_id,
            "reason": reason,
            "suggested_command": suggested_command,
            "enforced_at": enforced_at,
        }
        return {
            **semantic,
            "action_id": "advice-" + sha256_json(semantic)[:16],
            "authority": "process_advice_only",
        }

    def process_readiness_status(self, round_id: str) -> dict[str, Any]:
        """Describe repairable process gaps without creating admission authority."""

        status = self.round_status(round_id)
        research_ids = {
            assignment["research_id"] for assignment in status["assignments"]
        }
        actions: list[dict[str, str]] = []
        quarantines = [
            item
            for item in self._quarantine_records()
            if item.get("round_id") == round_id
        ]
        latest_quarantine: dict[str, dict[str, Any]] = {}
        for item in quarantines:
            assignment_id = item["assignment_id"]
            previous = latest_quarantine.get(assignment_id)
            if previous is None or item["created_at"] > previous["created_at"]:
                latest_quarantine[assignment_id] = item
        round_dir = self.store.rounds_dir / round_id
        for assignment in status["assignments"]:
            assignment_id = assignment["assignment_id"]
            state = assignment["state"]
            if state == "awaiting_return":
                actions.append(
                    self._readiness_action(
                        category="return_missing",
                        object_id=assignment_id,
                        reason=(
                            "No return exists for this task card. Other valid "
                            "assignments remain usable."
                        ),
                        suggested_command=(
                            f"complete {assignment['return_relpath']}, then run "
                            f"preflight-return {round_id} {assignment_id}"
                        ),
                        enforced_at="ingest-return for this assignment only",
                    )
                )
            elif state == "return_present":
                actions.append(
                    self._readiness_action(
                        category="return_needs_preflight",
                        object_id=assignment_id,
                        reason="Return bytes exist but have no ingestion receipt.",
                        suggested_command=(
                            f"preflight-return {round_id} {assignment_id}; if valid, "
                            "run ingest-return with the reported SHA-256"
                        ),
                        enforced_at="ingest-return for this assignment only",
                    )
                )
            elif state == "quarantined":
                quarantine = latest_quarantine[assignment_id]
                actions.append(
                    self._readiness_action(
                        category="return_quarantined",
                        object_id=assignment_id,
                        reason=(
                            f"Local validation failed: {quarantine['error']}. "
                            "The quarantine has no effect on valid peers."
                        ),
                        suggested_command=(
                            f"repair {assignment['return_relpath']}; run preflight-return "
                            f"{round_id} {assignment_id}; retry ingest-return"
                        ),
                        enforced_at="ingest-return for this assignment only",
                    )
                )
            elif state == "ingested":
                receipt_path = (
                    round_dir / "returns" / f"{assignment_id}.receipt.json"
                )
                receipt = self.store._read_json(receipt_path)
                research_id = receipt.get("research_id")
                if isinstance(research_id, str):
                    research_ids.add(research_id)

        relevant_releases = [
            release
            for release in self.releases()
            if research_ids.intersection(
                binding["research_id"]
                for binding in release["research_bindings"]
            )
        ]
        decisions_by_release = {
            decision["release_id"]: decision for decision in self.decisions()
        }
        visible_facts = set(self.store.fact_ids())
        if status["ingested_count"] and not relevant_releases:
            actions.append(
                self._readiness_action(
                    category="candidate_release_missing",
                    object_id=round_id,
                    reason=(
                        "At least one cumulative contribution is available, but no "
                        "Candidate Release binds this round's research yet."
                    ),
                    suggested_command=(
                        "prepare an explicit candidate-release input with the requested "
                        "assurance and challenge dispositions"
                    ),
                    enforced_at="candidate-release",
                )
            )
        for release in relevant_releases:
            decision = decisions_by_release.get(release["release_id"])
            if decision is None:
                actions.append(
                    self._readiness_action(
                        category="certification_missing",
                        object_id=release["release_id"],
                        reason="The sealed Candidate Release has no independent decision.",
                        suggested_command=(
                            f"verifier-capsule {release['release_id']}, then obtain a "
                            "fresh certification-record"
                        ),
                        enforced_at="certification-record",
                    )
                )
            elif decision["verdict"] == "reject":
                actions.append(
                    self._readiness_action(
                        category="candidate_rejected",
                        object_id=release["release_id"],
                        reason=(
                            "The immutable decision rejected this release; repair must "
                            "continue as new Research and a new release."
                        ),
                        suggested_command="research-add, then seal a new candidate-release",
                        enforced_at="candidate-release",
                    )
                )
            elif not set(release["fact_ids"]).issubset(visible_facts):
                actions.append(
                    self._readiness_action(
                        category="gateway_admission_missing",
                        object_id=release["release_id"],
                        reason=(
                            "A correct Certification Decision exists, but its Facts are "
                            "not all active in the V5 Fact Graph."
                        ),
                        suggested_command=(
                            f"fact-admit {release['release_id']} "
                            f"{decision['decision_id']}"
                        ),
                        enforced_at="fact-admit",
                    )
                )

        if any(item["category"] == "return_quarantined" for item in actions):
            advisory_state = "local_repairs_recommended"
        elif any(
            item["category"] in {"return_missing", "return_needs_preflight"}
            for item in actions
        ):
            advisory_state = "contributions_in_progress"
        elif actions:
            advisory_state = "next_transition_recommended"
        else:
            advisory_state = "no_process_gap_detected"
        return {
            "schema_version": 5,
            "policy_revision": V5_POLICY_REVISION,
            "project_id": self.store.project_id(),
            "round_id": round_id,
            "advisory_state": advisory_state,
            "recommended_actions": sorted(
                actions, key=lambda item: (item["category"], item["object_id"])
            ),
            "assignment_summary": {
                "total": len(status["assignments"]),
                "ingested": status["ingested_count"],
                "quarantined": status["quarantined_count"],
                "awaiting": status["awaiting_count"],
            },
            "admission_authority": False,
            "truth_effect": "none",
            "recording_effect": (
                "profile-closure-record appends guidance to Research only; "
                "it never marks the process complete"
            ),
        }

    def record_process_readiness(
        self,
        round_id: str,
        payload: dict[str, Any],
        *,
        actor: str,
    ) -> dict[str, Any]:
        if not isinstance(payload, dict) or not set(payload).issubset(
            {"note", "acknowledged_action_ids", "deferred_action_ids"}
        ):
            raise ValueError(
                "V5 readiness record accepts only note, "
                "acknowledged_action_ids, and deferred_action_ids"
            )
        note = payload.get("note", "")
        if not isinstance(note, str):
            raise ValueError("V5 readiness note must be a string")
        acknowledged = _require_string_list(
            payload.get("acknowledged_action_ids", []),
            "acknowledged readiness action ids",
        )
        deferred = _require_string_list(
            payload.get("deferred_action_ids", []),
            "deferred readiness action ids",
        )
        if set(acknowledged).intersection(deferred):
            raise ValueError("a readiness action cannot be acknowledged and deferred")
        report = self.process_readiness_status(round_id)
        known = {item["action_id"] for item in report["recommended_actions"]}
        unknown = sorted(set(acknowledged + deferred).difference(known))
        if unknown:
            raise ValueError(
                "readiness record references unknown current actions: "
                + ", ".join(unknown)
            )
        related = sorted(
            {
                assignment["research_id"]
                for assignment in self.round_status(round_id)["assignments"]
            }
        )
        research = self.add_research(
            {
                "kind": "guidance",
                "status": (
                    "open"
                    if report["recommended_actions"]
                    else "resolved_no_obstruction"
                ),
                "claim": f"Process readiness advice for {round_id}",
                "content": json.dumps(
                    report["recommended_actions"],
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                "rationale": note,
                "relation": "advises",
                "related_research_ids": related,
                "round_id": round_id,
                "advisory_report_sha256": sha256_json(report),
                "acknowledged_action_ids": sorted(dict.fromkeys(acknowledged)),
                "deferred_action_ids": sorted(dict.fromkeys(deferred)),
                "admission_authority": False,
                "truth_effect": "none",
            },
            actor=actor,
        )
        return {
            **report,
            "recorded_research_id": research["research_id"],
            "recorded_research_sha256": research["record_sha256"],
        }

    def _validate_return_payload(
        self,
        *,
        round_id: str,
        assignment_id: str,
        payload: Any,
        return_path: Path,
    ) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("V5 worker return must be one object")
        required = {
            "schema_version",
            "project_id",
            "round_id",
            "assignment_id",
            "worker_id",
            "task_card_sha256",
            "blackboard_snapshot_sha256",
            "outcome",
            "claim",
            "content",
            "narrative",
            "artifacts",
        }
        if set(payload) != required:
            raise ValueError("V5 worker return fields are not exact")
        round_dir, manifest = self._round_manifest(round_id)
        assignment = self._assignment(manifest, assignment_id)
        if (
            payload.get("schema_version") != 5
            or payload.get("project_id") != self.store.project_id()
            or payload.get("round_id") != round_id
            or payload.get("assignment_id") != assignment_id
            or payload.get("worker_id") != assignment["worker_id"]
            or payload.get("task_card_sha256")
            != assignment["task_card_sha256"]
            or payload.get("blackboard_snapshot_sha256")
            != assignment["blackboard_snapshot_sha256"]
        ):
            raise ValueError("V5 worker return binding mismatch")
        if payload.get("outcome") not in V5_RETURN_OUTCOMES:
            raise ValueError("V5 worker return outcome is invalid")
        _require_nonempty_text(payload.get("claim"), "worker return claim")
        _require_nonempty_text(payload.get("content"), "worker return content")
        narrative = payload.get("narrative")
        if not isinstance(narrative, dict) or set(narrative) != {
            "rationale",
            "summary",
            "intuition",
            "limitations",
        }:
            raise ValueError("V5 worker narrative fields are not exact")
        for name, value in narrative.items():
            if not isinstance(value, str):
                raise ValueError(f"V5 worker narrative {name} must be a string")
            cap = 400
            if len(value.split()) > cap:
                raise ValueError(f"V5 worker narrative {name} exceeds {cap} words")
        artifacts = payload.get("artifacts")
        if not isinstance(artifacts, list) or any(
            not isinstance(item, dict) or set(item) != {"path", "sha256"}
            for item in artifacts
        ):
            raise ValueError("V5 worker artifacts must be exact path/hash objects")
        card = self.store._read_json(
            self.store.root / assignment["task_card_relpath"]
        )
        capability = card["artifact_capability"]
        if len(artifacts) > capability["max_files"]:
            raise ValueError("V5 worker artifact file count exceeds task-card cap")
        total_bytes = 0
        artifact_root = contained_path(
            self.store.root,
            capability["artifact_dir_relpath"],
            "V5 artifact root",
        )
        for item in artifacts:
            if not isinstance(item["path"], str) or not isinstance(
                item["sha256"], str
            ):
                raise ValueError("V5 worker artifact fields must be strings")
            if SHA256_RE.fullmatch(item["sha256"]) is None:
                raise ValueError("V5 worker artifact hash is invalid")
            artifact_path = contained_path(
                self.store.root, item["path"], "V5 worker artifact path"
            )
            try:
                artifact_path.relative_to(artifact_root)
            except ValueError as exc:
                raise ValueError(
                    "V5 worker artifact is outside its task-card directory"
                ) from exc
            if artifact_path.is_symlink() or not artifact_path.is_file():
                raise ValueError("V5 worker artifact is missing or unsafe")
            size = artifact_path.stat().st_size
            if size > capability["max_file_bytes"]:
                raise ValueError("V5 worker artifact exceeds per-file cap")
            total_bytes += size
            if sha256_bytes(artifact_path.read_bytes()) != item["sha256"]:
                raise ValueError("V5 worker artifact bytes/hash mismatch")
        if total_bytes > capability["max_total_bytes"]:
            raise ValueError("V5 worker artifacts exceed total-byte cap")
        canonical_return = self.store.root / assignment["return_relpath"]
        if return_path.resolve() != canonical_return.resolve():
            # Preflight may inspect a draft elsewhere, but its declared
            # bindings and artifact capabilities remain those of the card.
            if return_path.is_symlink() or not return_path.is_file():
                raise ValueError("V5 worker draft return is missing or unsafe")
        return payload

    def preflight_return(
        self,
        *,
        round_id: str,
        assignment_id: str,
        input_path: Path | None = None,
    ) -> dict[str, Any]:
        self.store.reasoning_modes().require_work_unit_active(round_id)
        _, manifest = self._round_manifest(round_id)
        assignment = self._assignment(manifest, assignment_id)
        return_path = (
            Path(input_path).expanduser().resolve()
            if input_path is not None
            else (self.store.root / assignment["return_relpath"])
        )
        if return_path.is_symlink() or not return_path.is_file():
            raise ValueError("V5 worker return is missing or unsafe")
        try:
            payload = json.loads(return_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("V5 worker return is not valid UTF-8 JSON") from exc
        self._validate_return_payload(
            round_id=round_id,
            assignment_id=assignment_id,
            payload=payload,
            return_path=return_path,
        )
        return {
            "valid": True,
            "round_id": round_id,
            "assignment_id": assignment_id,
            "return_path": str(return_path),
            "return_sha256": sha256_bytes(return_path.read_bytes()),
            "outcome": payload["outcome"],
        }

    def _quarantine(
        self,
        *,
        round_id: str,
        assignment_id: str,
        assignment: dict[str, Any],
        error: str,
    ) -> dict[str, Any]:
        return_path = self.store.root / assignment["return_relpath"]
        return_sha = (
            sha256_bytes(return_path.read_bytes())
            if return_path.is_file() and not return_path.is_symlink()
            else None
        )
        semantic = {
            "schema_version": 5,
            "policy_revision": V5_POLICY_REVISION,
            "project_id": self.store.project_id(),
            "round_id": round_id,
            "assignment_id": assignment_id,
            "task_card_sha256": assignment["task_card_sha256"],
            "return_relpath": assignment["return_relpath"],
            "return_sha256": return_sha,
            "error": error,
            "effect": "local_contribution_only;valid_peers_unchanged",
            "next_safe_command": "repair this return and retry ingest-return",
        }
        quarantine_id = "quarantine-" + sha256_json(semantic)
        created_at = _utc_now()
        without_hash = {
            **semantic,
            "quarantine_id": quarantine_id,
            "created_at": created_at,
        }
        record = {
            **without_hash,
            "record_sha256": sha256_json(without_hash),
        }
        path = self.quarantine_dir / f"{quarantine_id}.json"
        self.store._write_json_once(path, record)
        return record

    def ingest_return(
        self,
        *,
        round_id: str,
        assignment_id: str,
        worker_final_sha256: str,
    ) -> dict[str, Any]:
        if SHA256_RE.fullmatch(worker_final_sha256) is None:
            raise ValueError("worker final SHA-256 is invalid")
        round_dir, manifest = self._round_manifest(round_id)
        assignment = self._assignment(manifest, assignment_id)
        receipt_path = round_dir / "returns" / f"{assignment_id}.receipt.json"
        if receipt_path.exists():
            return self.store._read_json(receipt_path)
        self.store.reasoning_modes().require_work_unit_active(round_id)
        with self.store.v5_mutation_lock(command="ingest-return"):
            try:
                preflight = self.preflight_return(
                    round_id=round_id,
                    assignment_id=assignment_id,
                )
                if preflight["return_sha256"] != worker_final_sha256:
                    raise ValueError(
                        "worker final handoff hash does not match return bytes"
                    )
            except Exception as exc:
                quarantine = self._quarantine(
                    round_id=round_id,
                    assignment_id=assignment_id,
                    assignment=assignment,
                    error=str(exc),
                )
                return {
                    "status": "quarantined",
                    "quarantine_id": quarantine["quarantine_id"],
                    "error": quarantine["error"],
                    "effect": quarantine["effect"],
                    "next_safe_command": quarantine["next_safe_command"],
                }
            return_path = self.store.root / assignment["return_relpath"]
            payload = json.loads(return_path.read_text(encoding="utf-8"))
            kind_by_outcome = {
                "proof": "proof_attempt",
                "counterexample": "counterexample",
                "evidence": "insight",
                "dead_end": "dead_end",
                "insight": "insight",
                "challenge": "challenge",
            }
            card = self.store._read_json(
                self.store.root / assignment["task_card_relpath"]
            )
            research = self.add_research(
                {
                    "kind": kind_by_outcome[payload["outcome"]],
                    "claim": payload["claim"],
                    "content": payload["content"],
                    "rationale": payload["narrative"]["rationale"],
                    "relation": "responds_to",
                    "related_research_ids": [assignment["research_id"]],
                    "worker_outcome": payload["outcome"],
                    "narrative": payload["narrative"],
                    "artifacts": payload["artifacts"],
                    "requested_claim_relation": card[
                        "requested_claim_relation"
                    ],
                },
                actor=assignment["worker_id"],
                task_binding={
                    "round_id": round_id,
                    "assignment_id": assignment_id,
                    "task_card_sha256": assignment["task_card_sha256"],
                    "blackboard_snapshot_sha256": assignment[
                        "blackboard_snapshot_sha256"
                    ],
                    "return_sha256": worker_final_sha256,
                },
            )
            receipt_semantic = {
                "schema_version": 5,
                "policy_revision": V5_POLICY_REVISION,
                "project_id": self.store.project_id(),
                "round_id": round_id,
                "assignment_id": assignment_id,
                "task_card_sha256": assignment["task_card_sha256"],
                "return_sha256": worker_final_sha256,
                "outcome": payload["outcome"],
                "research_id": research["research_id"],
                "effect": "one_cumulative_research_entry",
            }
            receipt = {
                **receipt_semantic,
                "receipt_id": "research-ingest-" + sha256_json(receipt_semantic),
                "created_at": _utc_now(),
            }
            self.store._write_json_once(receipt_path, receipt)
            return {**receipt, "status": "ingested"}

    def _release_path(self, release_id: str) -> Path:
        if not isinstance(release_id, str) or not release_id.startswith("release-"):
            raise ValueError("invalid V5 Candidate Release id")
        digest = release_id.removeprefix("release-")
        if SHA256_RE.fullmatch(digest) is None:
            raise ValueError("invalid V5 Candidate Release id")
        return self.candidate_releases_dir / f"{release_id}.json"

    def _decision_path(self, decision_id: str) -> Path:
        if not isinstance(decision_id, str) or not decision_id.startswith("decision-"):
            raise ValueError("invalid V5 Certification Decision id")
        digest = decision_id.removeprefix("decision-")
        if SHA256_RE.fullmatch(digest) is None:
            raise ValueError("invalid V5 Certification Decision id")
        return self.certification_decisions_dir / f"{decision_id}.json"

    def _normalize_artifacts(
        self,
        artifacts: Any,
        *,
        seal: bool,
    ) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        if not isinstance(artifacts, list) or any(
            not isinstance(item, dict)
            or set(item) != {"path", "sha256", "role"}
            for item in artifacts
        ):
            raise ValueError(
                "candidate artifacts must be exact path/sha256/role objects"
            )
        normalized: list[dict[str, str]] = []
        validation_view: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        total_bytes = 0
        for item in artifacts:
            relpath = _require_nonempty_text(item["path"], "candidate artifact path")
            digest = _require_nonempty_text(
                item["sha256"], "candidate artifact SHA-256"
            )
            role = _require_nonempty_text(item["role"], "candidate artifact role")
            if SHA256_RE.fullmatch(digest) is None:
                raise ValueError("candidate artifact SHA-256 is invalid")
            key = (digest, role)
            if key in seen:
                raise ValueError("candidate artifact hash/role binding is duplicated")
            seen.add(key)
            source = contained_path(
                self.store.root, relpath, "candidate artifact source path"
            )
            if source.is_symlink() or not source.is_file():
                raise ValueError("candidate artifact source is missing or unsafe")
            raw = source.read_bytes()
            if sha256_bytes(raw) != digest:
                raise ValueError("candidate artifact source bytes/hash mismatch")
            total_bytes += len(raw)
            if total_bytes > 64 * 1024 * 1024:
                raise ValueError("candidate artifacts exceed the 64 MiB release cap")
            safe_name = source.name
            sealed_relpath = (
                f"candidate_releases/artifacts/by-hash/{digest}/{safe_name}"
            )
            if seal:
                sealed = self.store.root / sealed_relpath
                self.store._write_bytes_once(sealed, raw)
            normalized.append(
                {
                    "artifact_sha256": digest,
                    "role": role,
                    "name": safe_name,
                    "sealed_relpath": sealed_relpath,
                }
            )
            validation_view.append(
                {"path": sealed_relpath, "sha256": digest, "role": role}
            )
        normalized.sort(
            key=lambda item: (
                item["artifact_sha256"],
                item["role"],
                item["name"],
            )
        )
        validation_view.sort(
            key=lambda item: (item["sha256"], item["role"], item["path"])
        )
        return normalized, validation_view

    def _validate_paper_evidence_refs(
        self,
        refs: Any,
        *,
        validation_subject: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if not isinstance(refs, list) or any(not isinstance(item, dict) for item in refs):
            raise ValueError("paper_evidence_refs must be a list of objects")
        if validation_subject["kind"] != "paper":
            if refs:
                raise ValueError(
                    "paper_evidence_refs are only valid for a paper validation subject"
                )
            return []
        if not refs:
            raise ValueError("paper validation requires Logic and Audit EvidenceRefs")
        paper = self.store.paper_logic()
        current = set(paper.status()["current_snapshot_ids"])
        normalized: list[dict[str, Any]] = []
        graph_kinds: set[str] = set()
        bound_target_ids: set[str] = set()
        ref_bindings: set[tuple[str, str]] = set()
        for index, ref in enumerate(refs, 1):
            required = {
                "paper_id",
                "snapshot_id",
                "snapshot_sha256",
                "graph_kind",
                "target_artifact_sha256",
                "target_node_ids",
            }
            if set(ref) != required:
                raise ValueError(
                    f"paper EvidenceRef {index} fields are not exact"
                )
            snapshot_id = _require_nonempty_text(
                ref["snapshot_id"], "paper snapshot id"
            )
            if snapshot_id not in current:
                raise ValueError(
                    "paper EvidenceRef must bind a current, nonsuperseded snapshot"
                )
            manifest = paper.snapshot_manifest(snapshot_id)
            manifest_path = paper.snapshots_dir / snapshot_id / "manifest.json"
            if ref["snapshot_sha256"] != sha256_bytes(manifest_path.read_bytes()):
                raise ValueError("paper EvidenceRef snapshot bytes/hash mismatch")
            if (
                ref["paper_id"] != validation_subject["subject_id"]
                or manifest["paper_id"] != ref["paper_id"]
                or manifest["graph_kind"] != ref["graph_kind"]
            ):
                raise ValueError("paper EvidenceRef target/snapshot mismatch")
            artifact_sha = validation_subject["artifact_sha256"]
            if (
                ref["target_artifact_sha256"] != artifact_sha
                or artifact_sha
                not in {
                    item.get("artifact_sha256")
                    for item in manifest["source_artifacts"]
                    if isinstance(item, dict)
                }
            ):
                raise ValueError(
                    "paper EvidenceRef does not bind the requested source artifact"
                )
            target_ids = _require_string_list(
                ref["target_node_ids"], "paper EvidenceRef target node ids"
            )
            if len(target_ids) != len(set(target_ids)):
                raise ValueError("paper EvidenceRef target node ids are duplicated")
            nodes, _ = paper.snapshot_objects(snapshot_id)
            missing = sorted(set(target_ids).difference(nodes))
            if missing:
                raise ValueError(
                    "paper EvidenceRef target nodes are absent: "
                    + ", ".join(missing)
                )
            bound_target_ids.update(target_ids)
            graph_kinds.add(ref["graph_kind"])
            binding = (ref["graph_kind"], snapshot_id)
            if binding in ref_bindings:
                raise ValueError("paper EvidenceRef snapshot binding is duplicated")
            ref_bindings.add(binding)
            normalized.append(
                {
                    "paper_id": ref["paper_id"],
                    "snapshot_id": snapshot_id,
                    "snapshot_sha256": ref["snapshot_sha256"],
                    "graph_kind": ref["graph_kind"],
                    "target_artifact_sha256": artifact_sha,
                    "target_node_ids": sorted(dict.fromkeys(target_ids)),
                }
            )
        if not {"logic", "audit"}.issubset(graph_kinds):
            raise ValueError(
                "paper validation requires both current Logic and Audit snapshots"
            )
        load_bearing = set(validation_subject["load_bearing_node_ids"])
        unbound = sorted(load_bearing.difference(bound_target_ids))
        if unbound:
            raise ValueError(
                "paper load-bearing nodes are not bound by any EvidenceRef: "
                + ", ".join(unbound)
            )
        normalized.sort(key=lambda item: (item["graph_kind"], item["snapshot_id"]))
        return normalized

    def _validate_requested_assurance(
        self,
        assurance: Any,
        *,
        candidate_ids: set[str],
        internal_edges: list[list[str]],
    ) -> dict[str, Any]:
        if not isinstance(assurance, dict) or set(assurance) != {
            "validation_subject",
            "validation_granularity",
            "coverage",
        }:
            raise ValueError("requested_assurance fields are not exact")
        subject = assurance["validation_subject"]
        if not isinstance(subject, dict) or set(subject) != {
            "kind",
            "subject_id",
            "artifact_sha256",
            "load_bearing_node_ids",
        }:
            raise ValueError("validation_subject fields are not exact")
        if subject.get("kind") not in {"theorem", "paper"}:
            raise ValueError("validation_subject kind must be theorem or paper")
        subject_id = _require_nonempty_text(
            subject.get("subject_id"), "validation subject id"
        )
        load_bearing = _require_string_list(
            subject.get("load_bearing_node_ids"),
            "validation subject load-bearing node ids",
        )
        if len(set(load_bearing)) != len(load_bearing):
            raise ValueError("load-bearing node ids must be unique")
        artifact_sha = subject.get("artifact_sha256")
        if subject["kind"] == "paper":
            if not isinstance(artifact_sha, str) or SHA256_RE.fullmatch(
                artifact_sha
            ) is None:
                raise ValueError("paper validation subject requires an artifact SHA-256")
        elif artifact_sha is not None:
            raise ValueError("theorem validation subject artifact_sha256 must be null")
        granularity = assurance.get("validation_granularity")
        if granularity not in V5_VALIDATION_GRANULARITIES:
            raise ValueError("validation_granularity is invalid")
        coverage = assurance.get("coverage")
        if not isinstance(coverage, list) or any(
            not isinstance(item, dict) for item in coverage
        ):
            raise ValueError("validation coverage must be a list of objects")
        normalized_coverage: list[dict[str, Any]] = []
        covered: set[str] = set()
        for item in coverage:
            if set(item) != {"paper_node_id", "disposition", "fact_id", "reason"}:
                raise ValueError("validation coverage entry fields are not exact")
            node_id = _require_nonempty_text(
                item["paper_node_id"], "coverage paper node id"
            )
            if node_id in covered:
                raise ValueError("validation coverage contains a duplicate node")
            covered.add(node_id)
            disposition = item["disposition"]
            if disposition not in V5_COVERAGE_DISPOSITIONS:
                raise ValueError("validation coverage disposition is invalid")
            fact_id = item["fact_id"]
            reason = item["reason"]
            if not isinstance(reason, str):
                raise ValueError("validation coverage reason must be a string")
            if disposition == "fact_bundle_member":
                if not isinstance(fact_id, str) or fact_id not in candidate_ids:
                    raise ValueError(
                        "fact_bundle_member coverage must name a release candidate"
                    )
            elif fact_id is not None:
                raise ValueError(
                    "non-Fact coverage dispositions must use fact_id=null"
                )
            if disposition != "fact_bundle_member" and not reason.strip():
                raise ValueError(
                    "non-Fact coverage disposition requires an explicit reason"
                )
            normalized_coverage.append(
                {
                    "paper_node_id": node_id,
                    "disposition": disposition,
                    "fact_id": fact_id,
                    "reason": reason.strip(),
                }
            )
        if set(load_bearing) != covered:
            missing = sorted(set(load_bearing).difference(covered))
            extra = sorted(covered.difference(load_bearing))
            raise ValueError(
                "validation coverage does not exactly cover load-bearing nodes; "
                f"missing={missing} extra={extra}"
            )
        if granularity == "monolithic_theorem":
            if len(candidate_ids) != 1:
                raise ValueError(
                    "monolithic_theorem requires exactly one candidate Fact"
                )
            if load_bearing or coverage:
                raise ValueError(
                    "monolithic_theorem cannot claim nodewise paper coverage"
                )
        elif granularity == "atomic_fact_dag":
            if len(candidate_ids) < 2 or not internal_edges:
                raise ValueError(
                    "atomic_fact_dag requires multiple candidates and an internal edge"
                )
            if subject["kind"] != "theorem" or load_bearing or coverage:
                raise ValueError(
                    "atomic_fact_dag without a paper target cannot claim paper coverage"
                )
        else:
            if len(candidate_ids) < 2 or not internal_edges:
                raise ValueError(
                    "nodewise_proof_dag requires multiple candidates and an internal edge"
                )
            if subject["kind"] != "paper" or not load_bearing:
                raise ValueError(
                    "nodewise_proof_dag requires a paper target and load-bearing nodes"
                )
        return {
            "validation_subject": {
                "kind": subject["kind"],
                "subject_id": subject_id,
                "artifact_sha256": artifact_sha,
                "load_bearing_node_ids": sorted(load_bearing),
            },
            "validation_granularity": granularity,
            "coverage": sorted(
                normalized_coverage, key=lambda item: item["paper_node_id"]
            ),
        }

    def _candidate_interface(
        self,
        fact: Fact,
        rendered: bytes,
    ) -> dict[str, Any]:
        placeholder = sha256_json(["v5-candidate-interface", fact.fact_id])
        return build_statement_interface(
            fact=fact,
            stored_fact_sha256=sha256_bytes(rendered),
            acceptance_event_sha256=placeholder,
            admission_review_id=placeholder,
            workflow_evidence_version=5,
        )

    def _prepare_candidate_facts(
        self,
        fact_payloads: Any,
        *,
        artifacts: list[dict[str, str]],
        verification_plan: dict[str, Any],
    ) -> tuple[
        dict[str, Fact],
        dict[str, bytes],
        list[str],
        list[list[str]],
        list[str],
    ]:
        if not isinstance(fact_payloads, list) or not fact_payloads or any(
            not isinstance(item, dict) for item in fact_payloads
        ):
            raise ValueError("Candidate Release facts must be a nonempty object list")
        facts: dict[str, Fact] = {}
        rendered: dict[str, bytes] = {}
        for payload in fact_payloads:
            fact = Fact.from_dict(payload)
            errors = fact.validate()
            if errors:
                raise ValueError("; ".join(errors))
            if fact.problem_id != self.store.project_id():
                raise ValueError("Candidate Release Fact belongs to another project")
            raw = validate_fact_round_trip(fact).encode("utf-8")
            if fact.fact_id in facts:
                raise ValueError("Candidate Release has a duplicate Fact id")
            validate_external_refs_for_submission(
                fact.external_refs,
                fact.proof,
                require_formula_fidelity=True,
                require_critical_audit=True,
            )
            validate_elementary_uses_for_submission(
                fact.elementary_uses,
                fact.proof,
            )
            clauses = extract_statement_clauses(fact.statement, require_v4=True)
            validate_quantifier_ledger(
                fact.quantifier_ledger,
                statement=fact.statement,
                proof=fact.proof,
                clause_ids={item["clause_id"] for item in clauses},
            )
            for convention_id in fact.convention_profile_ids:
                self.store.claims().show_convention(convention_id)
            validate_computational_evidence(
                fact.computational_evidence,
                proof=fact.proof,
                artifacts=artifacts,
                verification_plan=verification_plan,
                workflow_evidence_version=V5_WORKFLOW_EVIDENCE_VERSION,
            )
            validate_terminology(fact.terminology, proof=fact.proof)
            facts[fact.fact_id] = fact
            rendered[fact.fact_id] = raw
        active = self.store.facts()
        collisions = sorted(set(facts).intersection(active))
        if collisions:
            raise ValueError(
                "Candidate Release collides with active V5 Facts: "
                + ", ".join(collisions)
            )
        combined = {**active, **facts}
        graph = DependencyGraph(combined)
        missing = graph.missing_predecessors()
        if missing:
            raise ValueError(
                "Candidate Release has unavailable predecessors: "
                + ", ".join(
                    f"{fact_id}->{predecessor}"
                    for fact_id, predecessor in missing
                )
            )
        graph.topological_order()
        candidate_interfaces = {
            fact_id: self._candidate_interface(fact, rendered[fact_id])
            for fact_id, fact in facts.items()
        }

        def interface_lookup(fact_id: str) -> dict[str, Any]:
            if fact_id in candidate_interfaces:
                return candidate_interfaces[fact_id]
            return self.store.statement_interface(fact_id, materialize=False)

        for fact in facts.values():
            validate_predecessor_uses(
                fact.predecessor_uses,
                predecessors=fact.predecessors,
                proof=fact.proof,
                interface_lookup=interface_lookup,
                convention_profile_ids=fact.convention_profile_ids,
            )
        internal_edges = sorted(
            [
                [predecessor, fact_id]
                for fact_id, fact in facts.items()
                for predecessor in fact.predecessors
                if predecessor in facts
            ]
        )
        external_predecessors = sorted(
            {
                predecessor
                for fact in facts.values()
                for predecessor in fact.predecessors
                if predecessor not in facts
            }
        )
        order = [
            fact_id
            for fact_id in graph.topological_order(set(facts))
            if fact_id in facts
        ]
        return facts, rendered, order, internal_edges, external_predecessors

    def candidate_release(
        self,
        payload: dict[str, Any],
        *,
        producer: str,
    ) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Candidate Release input must be one object")
        required = {
            "schema_version",
            "bundle_claim",
            "candidates",
            "research_entry_ids",
            "claim_relation",
            "artifacts",
            "verification_plan",
            "requested_assurance",
            "challenge_dispositions",
            "paper_evidence_refs",
            "adverse_actor_ids",
        }
        if set(payload) != required:
            raise ValueError("Candidate Release input fields are not exact")
        if payload.get("schema_version") != 5:
            raise ValueError("Candidate Release schema_version must be 5")
        producer = _require_nonempty_text(producer, "Candidate Release producer")
        bundle_claim = _require_nonempty_text(
            payload.get("bundle_claim"), "Candidate Release bundle claim"
        )
        claim_relation = payload.get("claim_relation")
        if claim_relation not in CLAIM_RELATIONS:
            raise ValueError("Candidate Release claim_relation is invalid")
        research_ids = _require_string_list(
            payload.get("research_entry_ids"), "Candidate Release research ids"
        )
        research_ids = [validate_memory_id(item) for item in research_ids]
        if not research_ids or len(set(research_ids)) != len(research_ids):
            raise ValueError(
                "Candidate Release research ids must be nonempty and unique"
            )
        explicit_research_records = [
            self._research_record(item) for item in research_ids
        ]
        research_records = self._release_research_records(
            explicit_research_records
        )
        research_bindings = [
            {
                "research_id": record["research_id"],
                "record_sha256": record["record_sha256"],
                "kind": record["kind"],
                "actor": record["actor"],
            }
            for record in research_records
        ]
        verification_plan = payload.get("verification_plan")
        if not isinstance(verification_plan, dict) or set(verification_plan) != {
            "mode",
            "authorized_artifact_roles",
            "required_checks",
        }:
            raise ValueError("Candidate Release verification_plan fields are not exact")
        if verification_plan.get("mode") != "closed_capsule":
            raise ValueError("Candidate Release verification mode must be closed_capsule")
        authorized_roles = _require_string_list(
            verification_plan.get("authorized_artifact_roles"),
            "verification authorized artifact roles",
        )
        required_checks = _require_string_list(
            verification_plan.get("required_checks"),
            "verification required checks",
        )
        if len(authorized_roles) != len(set(authorized_roles)):
            raise ValueError("verification authorized artifact roles are duplicated")
        if len(required_checks) != len(set(required_checks)):
            raise ValueError("verification required checks are duplicated")
        minimum_checks = {
            "mathematical",
            "typing",
            "scope",
            "source_and_applicability",
            "predecessor_interfaces",
            "computation_replay",
            "challenge_dispositions",
            "assurance_scope",
        }
        if not minimum_checks.issubset(required_checks):
            raise ValueError(
                "Candidate Release verification_plan omits invariant checks: "
                + ", ".join(sorted(minimum_checks.difference(required_checks)))
            )
        normalized_artifacts, validation_artifacts = self._normalize_artifacts(
            payload.get("artifacts"), seal=False
        )
        artifact_roles = {item["role"] for item in normalized_artifacts}
        if not set(authorized_roles).issubset(artifact_roles):
            raise ValueError(
                "verification plan authorizes an undeclared artifact role"
            )
        normalized_plan = {
            "mode": "closed_capsule",
            "authorized_artifact_roles": sorted(dict.fromkeys(authorized_roles)),
            "required_checks": sorted(dict.fromkeys(required_checks)),
        }
        (
            facts,
            rendered,
            order,
            internal_edges,
            external_predecessors,
        ) = self._prepare_candidate_facts(
            payload.get("candidates"),
            artifacts=validation_artifacts,
            verification_plan=normalized_plan,
        )
        if any(
            entry.get("role") == "load_bearing"
            for fact in facts.values()
            for entry in fact.computational_evidence
        ) and "program_math_truncation" not in normalized_plan["required_checks"]:
            raise ValueError(
                "load-bearing V5 computation requires the "
                "program_math_truncation certification check"
            )
        assurance = self._validate_requested_assurance(
            payload.get("requested_assurance"),
            candidate_ids=set(facts),
            internal_edges=internal_edges,
        )
        if assurance["validation_granularity"] == "nodewise_proof_dag":
            mapped_fact_ids = {
                item["fact_id"]
                for item in assurance["coverage"]
                if item["disposition"] == "fact_bundle_member"
            }
            if mapped_fact_ids != set(facts):
                raise ValueError(
                    "nodewise paper coverage must map every Candidate Release "
                    "Fact exactly through one or more load-bearing nodes; "
                    f"mapped={sorted(mapped_fact_ids)} candidates={sorted(facts)}"
                )
        paper_refs = self._validate_paper_evidence_refs(
            payload.get("paper_evidence_refs"),
            validation_subject=assurance["validation_subject"],
        )
        if assurance["validation_subject"]["kind"] == "paper":
            paper_checks = {
                "paper_source_fidelity",
                "paper_graph_structure",
                "paper_audit",
                "paper_target_coverage",
            }
            missing_paper_checks = sorted(
                paper_checks.difference(normalized_plan["required_checks"])
            )
            if missing_paper_checks:
                raise ValueError(
                    "paper Candidate Release omits required certification checks: "
                    + ", ".join(missing_paper_checks)
                )
        subject_artifact = assurance["validation_subject"]["artifact_sha256"]
        if (
            subject_artifact is not None
            and subject_artifact
            not in {item["artifact_sha256"] for item in normalized_artifacts}
        ):
            raise ValueError(
                "paper validation subject artifact is not sealed by the release"
            )
        challenge_dispositions = payload.get("challenge_dispositions")
        if not isinstance(challenge_dispositions, list) or any(
            not isinstance(item, dict) for item in challenge_dispositions
        ):
            raise ValueError("challenge_dispositions must be a list of objects")
        normalized_dispositions: list[dict[str, str]] = []
        disposed_ids: set[str] = set()
        for item in challenge_dispositions:
            if set(item) != {"research_id", "disposition", "rationale"}:
                raise ValueError("challenge disposition fields are not exact")
            research_id = validate_memory_id(
                _require_nonempty_text(
                    item["research_id"], "challenge research id"
                )
            )
            if research_id in disposed_ids:
                raise ValueError("challenge disposition is duplicated")
            disposed_ids.add(research_id)
            challenge = self._research_record(research_id)
            if challenge["kind"] not in {"challenge", "counterexample", "obstacle"}:
                raise ValueError(
                    "challenge disposition must reference adverse research"
                )
            if item["disposition"] not in V5_CHALLENGE_DISPOSITIONS:
                raise ValueError("challenge disposition is invalid")
            rationale = _require_nonempty_text(
                item["rationale"], "challenge disposition rationale"
            )
            normalized_dispositions.append(
                {
                    "research_id": research_id,
                    "disposition": item["disposition"],
                    "rationale": rationale,
                }
            )
        bound_challenges = {
            record["research_id"]
            for record in research_records
            if record["kind"] in {"challenge", "counterexample", "obstacle"}
        }
        missing_dispositions = sorted(bound_challenges.difference(disposed_ids))
        if missing_dispositions:
            raise ValueError(
                "Candidate Release has undisposed bound challenges: "
                + ", ".join(missing_dispositions)
            )
        adverse_actor_ids = _require_string_list(
            payload.get("adverse_actor_ids"), "adverse actor ids"
        )
        if any(not item.strip() for item in adverse_actor_ids):
            raise ValueError("adverse actor ids must be nonempty strings")
        if len(adverse_actor_ids) != len(set(adverse_actor_ids)):
            raise ValueError("adverse actor ids are duplicated")
        actual_adverse_actor_ids = sorted(
            {
                record["actor"]
                for record in research_records
                if record["kind"] in {"challenge", "counterexample", "obstacle"}
            }
        )
        if set(adverse_actor_ids) != set(actual_adverse_actor_ids):
            raise ValueError(
                "adverse actor ids must exactly match bound adverse Research actors: "
                + ", ".join(actual_adverse_actor_ids)
            )
        excluded_verifier_ids = sorted(
            {
                producer,
                *adverse_actor_ids,
                *(fact.author for fact in facts.values()),
                *(record["actor"] for record in research_records),
            }
        )
        child_ids = {edge[0] for edge in internal_edges}
        root_fact_ids = sorted(set(facts).difference(child_ids))
        intermediate_fact_ids = sorted(set(facts).difference(root_fact_ids))
        candidate_records = [
            {
                "fact_id": fact_id,
                "fact_sha256": sha256_bytes(rendered[fact_id]),
                "fact_markdown": rendered[fact_id].decode("utf-8"),
            }
            for fact_id in order
        ]
        semantic = {
            "schema_version": 5,
            "policy_revision": V5_POLICY_REVISION,
            "project_id": self.store.project_id(),
            "bundle_claim": bundle_claim,
            "producer": producer,
            "claim_relation": claim_relation,
            "research_bindings": research_bindings,
            "candidates": candidate_records,
            "fact_ids": order,
            "root_fact_ids": root_fact_ids,
            "intermediate_fact_ids": intermediate_fact_ids,
            "internal_edges": internal_edges,
            "external_predecessors": external_predecessors,
            "artifacts": normalized_artifacts,
            "verification_plan": normalized_plan,
            "requested_assurance": assurance,
            "challenge_dispositions": sorted(
                normalized_dispositions, key=lambda item: item["research_id"]
            ),
            "paper_evidence_refs": paper_refs,
            "excluded_verifier_ids": excluded_verifier_ids,
            "fact_admission_contract_sha256": FACT_ADMISSION_CONTRACT_SHA256,
            "truth_effect": "none",
        }
        release_sha = sha256_json(semantic)
        release_id = "release-" + release_sha
        created_at = _utc_now()
        without_record_hash = {
            **semantic,
            "release_id": release_id,
            "release_sha256": release_sha,
            "created_at": created_at,
        }
        record = {
            **without_record_hash,
            "record_sha256": sha256_json(without_record_hash),
        }
        path = self._release_path(release_id)
        with self.store.v5_mutation_lock(command="candidate-release"):
            if path.exists():
                existing = self.release(release_id)
                if existing["release_sha256"] != release_sha:
                    raise ValueError(f"Candidate Release id collision at {path}")
                return existing
            sealed, _ = self._normalize_artifacts(
                payload.get("artifacts"), seal=True
            )
            if sealed != normalized_artifacts:
                raise ValueError(
                    "candidate artifact binding changed between preflight and seal"
                )
            self.store._write_json_once(path, record)
        return record

    def release(self, release_id: str) -> dict[str, Any]:
        path = self._release_path(release_id)
        if path.is_symlink() or not path.is_file():
            raise KeyError(f"unknown V5 Candidate Release: {release_id}")
        record = self.store._read_json(path)
        if not isinstance(record, dict):
            raise ValueError("Candidate Release record must be one object")
        record_only = {"release_id", "release_sha256", "created_at", "record_sha256"}
        semantic = {
            key: value for key, value in record.items() if key not in record_only
        }
        release_sha = sha256_json(semantic)
        if (
            record.get("schema_version") != 5
            or record.get("policy_revision") != V5_POLICY_REVISION
            or record.get("project_id") != self.store.project_id()
            or record.get("truth_effect") != "none"
            or record.get("release_id") != "release-" + release_sha
            or record.get("release_sha256") != release_sha
            or path.stem != record.get("release_id")
        ):
            raise ValueError("Candidate Release schema/project/id/hash mismatch")
        without_hash = {
            key: value for key, value in record.items() if key != "record_sha256"
        }
        if record.get("record_sha256") != sha256_json(without_hash):
            raise ValueError("Candidate Release record hash mismatch")
        if record.get("fact_admission_contract_sha256") != FACT_ADMISSION_CONTRACT_SHA256:
            raise ValueError("Candidate Release Fact contract mismatch")
        candidates = record.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise ValueError("Candidate Release candidates are invalid")
        seen: list[str] = []
        for candidate in candidates:
            if not isinstance(candidate, dict) or set(candidate) != {
                "fact_id",
                "fact_sha256",
                "fact_markdown",
            }:
                raise ValueError("Candidate Release candidate fields are not exact")
            raw = candidate["fact_markdown"].encode("utf-8")
            if sha256_bytes(raw) != candidate["fact_sha256"]:
                raise ValueError("Candidate Release Fact bytes/hash mismatch")
            fact = parse_fact_markdown(candidate["fact_markdown"])
            if fact.fact_id != candidate["fact_id"]:
                raise ValueError("Candidate Release Fact id mismatch")
            seen.append(fact.fact_id)
        if seen != record.get("fact_ids"):
            raise ValueError("Candidate Release Fact order is inconsistent")
        for artifact in record.get("artifacts", []):
            sealed = contained_path(
                self.store.root,
                artifact["sealed_relpath"],
                "sealed Candidate Release artifact",
            )
            if (
                sealed.is_symlink()
                or not sealed.is_file()
                or sha256_bytes(sealed.read_bytes())
                != artifact["artifact_sha256"]
            ):
                raise ValueError("sealed Candidate Release artifact drifted")
        for binding in record.get("research_bindings", []):
            research = self._research_record(binding["research_id"])
            if research["record_sha256"] != binding["record_sha256"]:
                raise ValueError("Candidate Release research binding drifted")
        self._validate_paper_evidence_refs(
            record.get("paper_evidence_refs"),
            validation_subject=record["requested_assurance"]["validation_subject"],
        )
        return record

    def releases(self) -> list[dict[str, Any]]:
        if not self.candidate_releases_dir.exists():
            return []
        return [
            self.release(path.stem)
            for path in sorted(self.candidate_releases_dir.glob("release-*.json"))
        ]

    def release_for_fact(self, fact_id: str) -> dict[str, Any]:
        fact_id = validate_fact_id(fact_id)
        matches = [
            release for release in self.releases() if fact_id in release["fact_ids"]
        ]
        if len(matches) != 1:
            raise ValueError(
                f"V5 Fact candidate {fact_id} does not belong to one unique release"
            )
        return matches[0]

    def verifier_capsule(self, release_id: str) -> dict[str, Any]:
        release = self.release(release_id)
        predecessor_packets = []
        for fact_id in release["external_predecessors"]:
            fact_path = self.store.active_fact_path(fact_id)
            predecessor_packets.append(
                {
                    "fact_id": fact_id,
                    "fact_sha256": sha256_bytes(fact_path.read_bytes()),
                    "statement": self.store.get_fact(fact_id).statement,
                    "statement_interface": self.store.statement_interface(
                        fact_id, materialize=False
                    ),
                }
            )
        authorized_roles = set(
            release["verification_plan"]["authorized_artifact_roles"]
        )
        authorized_artifacts = [
            artifact
            for artifact in release["artifacts"]
            if artifact["role"] in authorized_roles
        ]
        semantic = {
            "schema_version": 5,
            "policy_revision": V5_POLICY_REVISION,
            "project_id": self.store.project_id(),
            "release_id": release_id,
            "release_sha256": release["release_sha256"],
            "fact_admission_contract_sha256": FACT_ADMISSION_CONTRACT_SHA256,
            "candidates": release["candidates"],
            "fact_ids": release["fact_ids"],
            "root_fact_ids": release["root_fact_ids"],
            "intermediate_fact_ids": release["intermediate_fact_ids"],
            "internal_edges": release["internal_edges"],
            "predecessor_packets": predecessor_packets,
            "authorized_artifacts": authorized_artifacts,
            "required_checks": release["verification_plan"]["required_checks"],
            "requested_assurance": release["requested_assurance"],
            "paper_evidence_refs": release["paper_evidence_refs"],
            "challenge_dispositions": release["challenge_dispositions"],
            "excluded_verifier_ids": release["excluded_verifier_ids"],
            "instructions": {
                "workspace_access": "forbidden",
                "allowed_input": "this_exact_capsule_only",
                "review_scope": (
                    "check every candidate, internal edge, predecessor use, source, "
                    "computation, challenge disposition, and requested assurance"
                ),
                "truth_effect": "none_until_gateway_admission",
            },
        }
        capsule_sha = sha256_json(semantic)
        return {
            **semantic,
            "capsule_id": "capsule-" + capsule_sha,
            "capsule_sha256": capsule_sha,
        }

    def _validate_finding(self, finding: Any, *, label: str) -> dict[str, str]:
        if not isinstance(finding, dict) or set(finding) != {
            "id",
            "severity",
            "class",
            "description",
            "repair_hint",
        }:
            raise ValueError(f"{label} fields are not exact")
        normalized = {
            key: _require_nonempty_text(finding[key], f"{label} {key}")
            for key in ("id", "severity", "class", "description")
        }
        if finding["severity"] not in {"critical_error", "gap"}:
            raise ValueError(f"{label} severity is invalid")
        if finding["class"] not in {
            "mathematical",
            "typing",
            "scope",
            "source_mismatch",
            "source_access",
            "reproducibility",
            "evidence_access",
            "protocol",
            "assurance_scope",
            "coverage",
        }:
            raise ValueError(f"{label} class is invalid")
        repair_hint = finding["repair_hint"]
        if not isinstance(repair_hint, str):
            raise ValueError(f"{label} repair_hint must be a string")
        return {**normalized, "repair_hint": repair_hint}

    def _expected_assurance_matrix(
        self,
        release: dict[str, Any],
    ) -> dict[str, Any]:
        paper_requested = (
            release["requested_assurance"]["validation_subject"]["kind"]
            == "paper"
        )
        return {
            "paper_source_fidelity": (
                "complete" if paper_requested else "not_requested"
            ),
            "paper_graph_structure": (
                "complete" if paper_requested else "not_requested"
            ),
            "paper_audit": "complete" if paper_requested else "not_requested",
            "root_fact_admission": "candidate",
            "intermediate_fact_coverage": {
                "admitted_count": 0,
                "required_count": len(release["intermediate_fact_ids"]),
            },
            "validation_granularity": release["requested_assurance"][
                "validation_granularity"
            ],
        }

    def certification_record(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Certification Decision input must be one object")
        required = {
            "schema_version",
            "release_id",
            "release_sha256",
            "capsule_sha256",
            "verdict",
            "findings",
            "check_results",
            "candidate_checks",
            "edge_checks",
            "assurance_matrix",
            "reviewer",
            "host_attestation",
        }
        if set(payload) != required:
            raise ValueError("Certification Decision input fields are not exact")
        if payload.get("schema_version") != 5:
            raise ValueError("Certification Decision schema_version must be 5")
        release = self.release(payload.get("release_id"))
        capsule = self.verifier_capsule(release["release_id"])
        if (
            payload.get("release_sha256") != release["release_sha256"]
            or payload.get("capsule_sha256") != capsule["capsule_sha256"]
        ):
            raise ValueError("Certification Decision release/capsule binding mismatch")
        verdict = payload.get("verdict")
        if verdict not in {"correct", "reject"}:
            raise ValueError("Certification Decision verdict must be correct or reject")
        findings_value = payload.get("findings")
        if not isinstance(findings_value, list):
            raise ValueError("Certification Decision findings must be a list")
        findings = [
            self._validate_finding(item, label=f"finding[{index}]")
            for index, item in enumerate(findings_value, 1)
        ]
        if len({item["id"] for item in findings}) != len(findings):
            raise ValueError("Certification Decision finding ids must be unique")
        check_results = payload.get("check_results")
        if not isinstance(check_results, list) or any(
            not isinstance(item, dict)
            or set(item) != {"check_id", "status", "findings"}
            for item in check_results
        ):
            raise ValueError("Certification check_results fields are not exact")
        normalized_check_results: list[dict[str, Any]] = []
        for item in check_results:
            check_id = _require_nonempty_text(
                item["check_id"], "Certification check id"
            )
            if item["status"] not in {"pass", "fail"}:
                raise ValueError("Certification check status is invalid")
            check_findings = _require_string_list(
                item["findings"], "Certification check finding ids"
            )
            if any(finding_id not in {f["id"] for f in findings} for finding_id in check_findings):
                raise ValueError("Certification check references an unknown finding")
            normalized_check_results.append(
                {
                    "check_id": check_id,
                    "status": item["status"],
                    "findings": sorted(dict.fromkeys(check_findings)),
                }
            )
        if {item["check_id"] for item in normalized_check_results} != set(
            capsule["required_checks"]
        ):
            raise ValueError(
                "Certification check_results do not exactly cover required checks"
            )
        if len(normalized_check_results) != len(
            {item["check_id"] for item in normalized_check_results}
        ):
            raise ValueError("Certification check_results contain duplicate checks")
        candidate_checks = payload.get("candidate_checks")
        if not isinstance(candidate_checks, list) or any(
            not isinstance(item, dict)
            or set(item) != {"fact_id", "verdict", "findings"}
            for item in candidate_checks
        ):
            raise ValueError("Certification candidate_checks fields are not exact")
        normalized_candidate_checks: list[dict[str, Any]] = []
        for item in candidate_checks:
            fact_id = validate_fact_id(item["fact_id"])
            if item["verdict"] not in {"correct", "reject"}:
                raise ValueError("Certification candidate verdict is invalid")
            check_findings = _require_string_list(
                item["findings"], "candidate check finding ids"
            )
            if any(finding_id not in {f["id"] for f in findings} for finding_id in check_findings):
                raise ValueError("candidate check references an unknown finding")
            normalized_candidate_checks.append(
                {
                    "fact_id": fact_id,
                    "verdict": item["verdict"],
                    "findings": sorted(dict.fromkeys(check_findings)),
                }
            )
        if {item["fact_id"] for item in normalized_candidate_checks} != set(
            release["fact_ids"]
        ):
            raise ValueError(
                "Certification candidate_checks do not exactly cover release Facts"
            )
        if len(normalized_candidate_checks) != len(
            {item["fact_id"] for item in normalized_candidate_checks}
        ):
            raise ValueError("Certification candidate_checks contain duplicate Facts")
        edge_checks = payload.get("edge_checks")
        if not isinstance(edge_checks, list) or any(
            not isinstance(item, dict)
            or set(item)
            != {"predecessor_fact_id", "fact_id", "verdict", "findings"}
            for item in edge_checks
        ):
            raise ValueError("Certification edge_checks fields are not exact")
        normalized_edge_checks: list[dict[str, Any]] = []
        for item in edge_checks:
            predecessor = validate_fact_id(item["predecessor_fact_id"])
            fact_id = validate_fact_id(item["fact_id"])
            if item["verdict"] not in {"correct", "reject"}:
                raise ValueError("Certification edge verdict is invalid")
            check_findings = _require_string_list(
                item["findings"], "edge check finding ids"
            )
            if any(finding_id not in {f["id"] for f in findings} for finding_id in check_findings):
                raise ValueError("edge check references an unknown finding")
            normalized_edge_checks.append(
                {
                    "predecessor_fact_id": predecessor,
                    "fact_id": fact_id,
                    "verdict": item["verdict"],
                    "findings": sorted(dict.fromkeys(check_findings)),
                }
            )
        expected_edges = {tuple(edge) for edge in release["internal_edges"]}
        actual_edges = {
            (item["predecessor_fact_id"], item["fact_id"])
            for item in normalized_edge_checks
        }
        if actual_edges != expected_edges:
            raise ValueError(
                "Certification edge_checks do not exactly cover internal edges"
            )
        if len(normalized_edge_checks) != len(actual_edges):
            raise ValueError("Certification edge_checks contain duplicate edges")
        expected_matrix = self._expected_assurance_matrix(release)
        if payload.get("assurance_matrix") != expected_matrix:
            raise ValueError("Certification assurance matrix is incorrect")
        reviewer = _require_nonempty_text(payload.get("reviewer"), "reviewer")
        if reviewer.casefold() in {
            item.casefold() for item in release["excluded_verifier_ids"]
        }:
            raise ValueError(
                "Certification reviewer participated in candidate/adverse research"
            )
        attestation = payload.get("host_attestation")
        if not isinstance(attestation, dict) or set(attestation) != {
            "host",
            "agent_id",
            "isolation",
            "fork_turns",
            "allowed_capsule_sha256",
        }:
            raise ValueError("Certification host_attestation fields are not exact")
        for key in ("host", "agent_id", "isolation", "fork_turns"):
            _require_nonempty_text(attestation[key], f"host attestation {key}")
        if (
            attestation["agent_id"] != reviewer
            or attestation["isolation"] != "fresh_context"
            or attestation["fork_turns"] != "none"
            or attestation["allowed_capsule_sha256"] != capsule["capsule_sha256"]
        ):
            raise ValueError("Certification fresh-context attestation is invalid")
        clean = (
            not findings
            and all(item["status"] == "pass" for item in normalized_check_results)
            and all(item["verdict"] == "correct" for item in normalized_candidate_checks)
            and all(item["verdict"] == "correct" for item in normalized_edge_checks)
        )
        if verdict == "correct" and not clean:
            raise ValueError("correct Certification Decision must be completely clean")
        if verdict == "reject" and clean:
            raise ValueError("rejecting Certification Decision requires a failed check")
        existing_for_release = [
            decision
            for decision in self.decisions()
            if decision["release_id"] == release["release_id"]
        ]
        semantic = {
            "schema_version": 5,
            "policy_revision": V5_POLICY_REVISION,
            "project_id": self.store.project_id(),
            "release_id": release["release_id"],
            "release_sha256": release["release_sha256"],
            "capsule_sha256": capsule["capsule_sha256"],
            "verdict": verdict,
            "findings": findings,
            "check_results": sorted(
                normalized_check_results, key=lambda item: item["check_id"]
            ),
            "candidate_checks": sorted(
                normalized_candidate_checks, key=lambda item: item["fact_id"]
            ),
            "edge_checks": sorted(
                normalized_edge_checks,
                key=lambda item: (item["predecessor_fact_id"], item["fact_id"]),
            ),
            "assurance_matrix": expected_matrix,
            "reviewer": reviewer,
            "host_attestation": attestation,
            "truth_effect": "none",
        }
        decision_sha = sha256_json(semantic)
        decision_id = "decision-" + decision_sha
        if existing_for_release:
            existing = existing_for_release[0]
            if existing["decision_id"] == decision_id:
                return existing
            raise ValueError(
                "Candidate Release already has a Certification Decision; "
                "repair Research and seal a new release"
            )
        reviewed_at = _utc_now()
        without_hash = {
            **semantic,
            "decision_id": decision_id,
            "decision_sha256": decision_sha,
            "reviewed_at": reviewed_at,
        }
        record = {**without_hash, "record_sha256": sha256_json(without_hash)}
        with self.store.v5_mutation_lock(command="certification-record"):
            self.store._write_json_once(self._decision_path(decision_id), record)
            if verdict == "reject":
                self.add_research(
                    {
                        "kind": "repair",
                        "claim": f"Repair rejected Candidate Release {release['release_id']}",
                        "content": "; ".join(
                            item["description"] for item in findings
                        ),
                        "release_id": release["release_id"],
                        "decision_id": decision_id,
                        "finding_ids": [item["id"] for item in findings],
                    },
                    actor="certification-gateway",
                )
        return record

    def decision(
        self,
        decision_id: str,
        *,
        validate_bindings: bool = True,
    ) -> dict[str, Any]:
        path = self._decision_path(decision_id)
        if path.is_symlink() or not path.is_file():
            raise KeyError(f"unknown V5 Certification Decision: {decision_id}")
        record = self.store._read_json(path)
        if not isinstance(record, dict):
            raise ValueError("Certification Decision record must be one object")
        record_only = {
            "decision_id",
            "decision_sha256",
            "reviewed_at",
            "record_sha256",
        }
        semantic = {
            key: value for key, value in record.items() if key not in record_only
        }
        decision_sha = sha256_json(semantic)
        if (
            record.get("schema_version") != 5
            or record.get("policy_revision") != V5_POLICY_REVISION
            or record.get("project_id") != self.store.project_id()
            or record.get("truth_effect") != "none"
            or record.get("decision_id") != "decision-" + decision_sha
            or record.get("decision_sha256") != decision_sha
            or path.stem != record.get("decision_id")
        ):
            raise ValueError("Certification Decision schema/project/id/hash mismatch")
        without_hash = {
            key: value for key, value in record.items() if key != "record_sha256"
        }
        if record.get("record_sha256") != sha256_json(without_hash):
            raise ValueError("Certification Decision record hash mismatch")
        if validate_bindings:
            release = self.release(record["release_id"])
            capsule = self.verifier_capsule(release["release_id"])
            if (
                record["release_sha256"] != release["release_sha256"]
                or record["capsule_sha256"] != capsule["capsule_sha256"]
            ):
                raise ValueError("Certification Decision binding drifted")
        return record

    def decisions(self) -> list[dict[str, Any]]:
        if not self.certification_decisions_dir.exists():
            return []
        return [
            self.decision(path.stem)
            for path in sorted(self.certification_decisions_dir.glob("decision-*.json"))
        ]

    def _admission_dir(self, release_id: str) -> Path:
        self._release_path(release_id)
        return self.admissions_dir / release_id

    def _validated_admission(
        self,
        release_id: str,
    ) -> tuple[dict[str, Any], dict[str, Path]]:
        directory = self._admission_dir(release_id)
        marker_path = directory / "ACCEPTED.json"
        if marker_path.is_symlink() or not marker_path.is_file():
            raise ValueError("V5 admission marker is missing or unsafe")
        marker = self.store._read_json(marker_path)
        required = {
            "schema_version",
            "policy_revision",
            "project_id",
            "release_id",
            "release_sha256",
            "decision_id",
            "decision_sha256",
            "capsule_sha256",
            "fact_ids",
            "fact_sha256",
            "gateway",
            "reviewer",
            "accepted_at",
            "acceptance_id",
        }
        if not isinstance(marker, dict) or set(marker) != required:
            raise ValueError("V5 admission marker fields are not exact")
        semantic = {
            key: value for key, value in marker.items() if key != "acceptance_id"
        }
        if (
            marker.get("schema_version") != 5
            or marker.get("policy_revision") != V5_POLICY_REVISION
            or marker.get("project_id") != self.store.project_id()
            or marker.get("release_id") != release_id
            or marker.get("acceptance_id")
            != "acceptance-" + sha256_json(semantic)
        ):
            raise ValueError("V5 admission marker schema/project/id/hash mismatch")
        release = self.release(release_id)
        decision = self.decision(
            marker["decision_id"], validate_bindings=False
        )
        if (
            decision["verdict"] != "correct"
            or marker["release_sha256"] != release["release_sha256"]
            or marker["decision_sha256"] != decision["decision_sha256"]
            or marker["capsule_sha256"] != decision["capsule_sha256"]
            or marker["reviewer"] != decision["reviewer"]
            or marker["fact_ids"] != release["fact_ids"]
        ):
            raise ValueError("V5 admission release/decision/capsule binding mismatch")
        candidate_by_id = {
            item["fact_id"]: item for item in release["candidates"]
        }
        paths: dict[str, Path] = {}
        expected_sha: dict[str, str] = {}
        for fact_id in release["fact_ids"]:
            path = directory / "facts" / f"{fact_id}.md"
            candidate = candidate_by_id[fact_id]
            if (
                path.is_symlink()
                or not path.is_file()
                or path.read_text(encoding="utf-8")
                != candidate["fact_markdown"]
            ):
                raise ValueError("V5 admitted Fact bytes differ from Candidate Release")
            digest = sha256_bytes(path.read_bytes())
            if digest != candidate["fact_sha256"]:
                raise ValueError("V5 admitted Fact hash mismatch")
            paths[fact_id] = path
            expected_sha[fact_id] = digest
        if marker["fact_sha256"] != expected_sha:
            raise ValueError("V5 admission marker Fact hash map mismatch")
        return marker, paths

    def active_fact_paths(self) -> dict[str, Path]:
        revoked = self.revoked_fact_ids()
        result: dict[str, Path] = {}
        if not self.admissions_dir.exists():
            return result
        for directory in sorted(self.admissions_dir.glob("release-*")):
            if directory.is_symlink() or not directory.is_dir():
                raise ValueError("V5 admission store contains an unsafe entry")
            marker_path = directory / "ACCEPTED.json"
            if not marker_path.exists():
                continue
            _, paths = self._validated_admission(directory.name)
            for fact_id, path in paths.items():
                if fact_id in revoked:
                    continue
                if fact_id in result:
                    raise ValueError(
                        f"V5 Fact {fact_id} has multiple active admissions"
                    )
                result[fact_id] = path
        return result

    def fact_admit(
        self,
        *,
        release_id: str,
        decision_id: str,
        gateway: str,
    ) -> dict[str, Any]:
        gateway = _require_nonempty_text(gateway, "V5 admission gateway")
        directory = self._admission_dir(release_id)
        marker_path = directory / "ACCEPTED.json"
        if marker_path.exists():
            marker, _ = self._validated_admission(release_id)
            if marker["decision_id"] != decision_id or marker["gateway"] != gateway:
                raise ValueError(
                    "Candidate Release was already admitted with different evidence"
                )
            self._materialize_admission_projections(marker)
            return marker
        release = self.release(release_id)
        decision = self.decision(decision_id)
        capsule = self.verifier_capsule(release_id)
        if (
            decision["release_id"] != release_id
            or decision["verdict"] != "correct"
            or decision["release_sha256"] != release["release_sha256"]
            or decision["capsule_sha256"] != capsule["capsule_sha256"]
        ):
            raise ValueError(
                "V5 admission requires the clean exact Certification Decision"
            )
        if gateway.casefold() == decision["reviewer"].casefold():
            raise ValueError("V5 admission gateway must differ from the verifier")
        candidate_payloads = [
            parse_fact_markdown(item["fact_markdown"]).as_submission_dict()
            for item in release["candidates"]
        ]
        validation_artifacts = [
            {
                "path": item["sealed_relpath"],
                "sha256": item["artifact_sha256"],
                "role": item["role"],
            }
            for item in release["artifacts"]
        ]
        (
            _,
            rendered,
            order,
            internal_edges,
            external_predecessors,
        ) = self._prepare_candidate_facts(
            candidate_payloads,
            artifacts=validation_artifacts,
            verification_plan=release["verification_plan"],
        )
        if (
            order != release["fact_ids"]
            or internal_edges != release["internal_edges"]
            or external_predecessors != release["external_predecessors"]
        ):
            raise ValueError("Candidate Release mathematical graph binding drifted")
        self._validate_paper_evidence_refs(
            release["paper_evidence_refs"],
            validation_subject=release["requested_assurance"]["validation_subject"],
        )
        with self.store.v5_mutation_lock(command="fact-admit"):
            facts_dir = directory / "facts"
            facts_dir.mkdir(parents=True, exist_ok=True)
            if directory.is_symlink() or facts_dir.is_symlink():
                raise ValueError("V5 admission staging directory is unsafe")
            expected_files = {
                facts_dir / f"{fact_id}.md" for fact_id in release["fact_ids"]
            }
            unexpected = {
                path
                for path in directory.rglob("*")
                if (path.is_file() or path.is_symlink())
                and path not in expected_files
                and path != marker_path
            }
            if unexpected:
                raise ValueError(
                    "V5 admission staging contains unexpected files: "
                    + ", ".join(
                        sorted(
                            path.relative_to(directory).as_posix()
                            for path in unexpected
                        )
                    )
                )
            fact_sha: dict[str, str] = {}
            for fact_id in release["fact_ids"]:
                path = facts_dir / f"{fact_id}.md"
                self.store._write_bytes_once(path, rendered[fact_id], mode=0o644)
                fact_sha[fact_id] = sha256_bytes(rendered[fact_id])
            accepted_at = _utc_now()
            marker_semantic = {
                "schema_version": 5,
                "policy_revision": V5_POLICY_REVISION,
                "project_id": self.store.project_id(),
                "release_id": release_id,
                "release_sha256": release["release_sha256"],
                "decision_id": decision_id,
                "decision_sha256": decision["decision_sha256"],
                "capsule_sha256": capsule["capsule_sha256"],
                "fact_ids": release["fact_ids"],
                "fact_sha256": fact_sha,
                "gateway": gateway,
                "reviewer": decision["reviewer"],
                "accepted_at": accepted_at,
            }
            marker = {
                **marker_semantic,
                "acceptance_id": "acceptance-" + sha256_json(marker_semantic),
            }
            # This write is the sole all-or-none visibility switch.
            self.store._write_json_once(marker_path, marker)
            self._materialize_admission_projections(marker)
        return marker

    def _materialize_admission_projections(
        self,
        marker: dict[str, Any],
    ) -> None:
        release = self.release(marker["release_id"])
        candidate_by_id = {
            item["fact_id"]: item for item in release["candidates"]
        }
        for fact_id in release["fact_ids"]:
            event_id = sha256_json(
                [
                    "accepted-v5",
                    fact_id,
                    marker["release_id"],
                    marker["decision_id"],
                    marker["acceptance_id"],
                ]
            )
            event = {
                "evidence_version": 5,
                "event": "accepted",
                "event_id": event_id,
                "fact_id": fact_id,
                "release_id": marker["release_id"],
                "release_sha256": marker["release_sha256"],
                "decision_id": marker["decision_id"],
                "decision_sha256": marker["decision_sha256"],
                "capsule_sha256": marker["capsule_sha256"],
                "acceptance_id": marker["acceptance_id"],
                "gateway": marker["gateway"],
                "reviewer": marker["reviewer"],
                "fact_sha256": marker["fact_sha256"][fact_id],
                "claim_relation": release["claim_relation"],
                "timestamp": marker["accepted_at"],
            }
            self.store._append_jsonl_once(
                self.store.verification_log, event, event_id=event_id
            )
            fact = parse_fact_markdown(
                candidate_by_id[fact_id]["fact_markdown"]
            )
            interface = build_statement_interface(
                fact=fact,
                stored_fact_sha256=marker["fact_sha256"][fact_id],
                acceptance_event_sha256=event_id,
                admission_review_id=marker["decision_sha256"],
                workflow_evidence_version=5,
            )
            write_interface_once(
                self.store.interfaces_dir / f"{fact_id}.json", interface
            )

    def revoked_fact_ids(self) -> set[str]:
        if not self.revocations_dir.exists():
            return set()
        result: set[str] = set()
        for path in sorted(self.revocations_dir.glob("*.json")):
            if path.is_symlink() or not path.is_file():
                raise ValueError("V5 revocation store contains an unsafe entry")
            record = self.store._read_json(path)
            fact_id = validate_fact_id(record.get("fact_id"))
            if path.stem != fact_id:
                raise ValueError("V5 revocation path/id mismatch")
            semantic = {
                key: value for key, value in record.items() if key != "record_sha256"
            }
            if record.get("record_sha256") != sha256_json(semantic):
                raise ValueError("V5 revocation record hash mismatch")
            result.add(fact_id)
        return result

    def revoke(
        self,
        fact_id: str,
        *,
        reason: str,
        actor: str,
    ) -> list[str]:
        fact_id = validate_fact_id(fact_id)
        reason = _require_nonempty_text(reason, "V5 revocation reason")
        actor = _require_nonempty_text(actor, "V5 revocation actor")
        facts = self.store.facts()
        if fact_id not in facts:
            raise KeyError(f"unknown active V5 Fact: {fact_id}")
        graph = DependencyGraph(facts)
        revoked = [fact_id, *sorted(graph.descendants([fact_id]))]
        with self.store.v5_mutation_lock(command="v5-revoke"):
            for current in revoked:
                semantic = {
                    "schema_version": 5,
                    "policy_revision": V5_POLICY_REVISION,
                    "project_id": self.store.project_id(),
                    "fact_id": current,
                    "root_fact_id": fact_id,
                    "reason": reason,
                    "actor": actor,
                    "revoked_at": _utc_now(),
                }
                record = {
                    **semantic,
                    "record_sha256": sha256_json(semantic),
                }
                self.store._write_json_once(
                    self.revocations_dir / f"{current}.json", record
                )
                event_id = sha256_json(["revoked", current, fact_id, reason])
                self.store._append_jsonl_once(
                    self.store.revocation_log,
                    {
                        "evidence_version": 5,
                        "event_id": event_id,
                        "fact_id": current,
                        "root_fact_id": fact_id,
                        "reason": reason,
                        "actor": actor,
                        "timestamp": semantic["revoked_at"],
                    },
                    event_id=event_id,
                )
        return revoked

    def _json_count(self, directory: Path) -> int:
        if not directory.exists():
            return 0
        return sum(
            1
            for path in directory.glob("*.json")
            if path.is_file() and not path.is_symlink()
        )

    def status(self) -> dict[str, Any]:
        research_entries = self._json_count(self.research_entries_dir)
        quarantined = self._json_count(self.quarantine_dir)
        releases = self._json_count(self.candidate_releases_dir)
        decisions = self._json_count(self.certification_decisions_dir)
        facts = len(self.store.fact_ids())
        decision_records = self.decisions() if decisions else []
        latest_decision = (
            max(decision_records, key=lambda item: item["reviewed_at"])
            if decision_records
            else None
        )
        if facts:
            current_state = "Fact"
            blocking_issue = None
            next_safe_command = "status"
        elif latest_decision is not None and latest_decision["verdict"] == "correct":
            current_state = "Certification Decision"
            blocking_issue = "accepted decision has not been gateway-admitted"
            next_safe_command = "fact-admit"
        elif decisions:
            current_state = "Research"
            blocking_issue = "latest Candidate Release was rejected"
            next_safe_command = "research-add"
        elif releases:
            current_state = "Candidate Release"
            blocking_issue = "candidate release has no certification decision"
            next_safe_command = "verifier-capsule"
        else:
            current_state = "Research"
            blocking_issue = None
            next_safe_command = "research-add"
        return {
            "schema_version": 1,
            "workflow_evidence_version": V5_WORKFLOW_EVIDENCE_VERSION,
            "policy_revision": V5_POLICY_REVISION,
            "lifecycle_contract_sha256": V5_LIFECYCLE_CONTRACT_SHA256,
            "current_state": current_state,
            "blocking_issue": blocking_issue,
            "next_safe_command": next_safe_command,
            "counts": {
                "research_entries": research_entries,
                "quarantined_contributions": quarantined,
                "candidate_releases": releases,
                "certification_decisions": decisions,
                "facts": facts,
            },
        }

    def audit(self) -> V5AuditReport:
        report = V5AuditReport()

        def workflow_error(message: str) -> None:
            report.workflow_errors.append(message)
            report.errors.append(f"workflow: {message}")

        def graph_error(message: str) -> None:
            report.graph_errors.append(message)
            report.errors.append(message)

        try:
            project = self.store.project()
        except Exception as exc:
            graph_error(f"invalid project.json: {exc}")
            return report
        if project.get("workflow_evidence_version") != V5_WORKFLOW_EVIDENCE_VERSION:
            workflow_error("V5 audit received a non-V5 project")
            return report
        if project.get("policy_revision") != V5_POLICY_REVISION:
            workflow_error("V5 project policy_revision is missing or mismatched")

        if self.contract_path.is_symlink() or not self.contract_path.is_file():
            workflow_error("V5 lifecycle contract is missing or unsafe")
        else:
            try:
                contract = self.store._read_json(self.contract_path)
                semantic = {
                    key: contract[key]
                    for key in V5_LIFECYCLE_CONTRACT
                }
                if semantic != V5_LIFECYCLE_CONTRACT:
                    raise ValueError("semantic contract differs from the release contract")
                if contract.get("contract_sha256") != sha256_json(semantic):
                    raise ValueError("contract hash mismatch")
            except Exception as exc:
                workflow_error(f"invalid V5 lifecycle contract: {exc}")

        for label, directory in (
            ("research entries", self.research_entries_dir),
            ("research quarantine", self.quarantine_dir),
            ("candidate releases", self.candidate_releases_dir),
            ("candidate artifacts", self.candidate_artifacts_dir),
            ("certification decisions", self.certification_decisions_dir),
            ("Fact admissions", self.admissions_dir),
            ("Fact revocations", self.revocations_dir),
        ):
            if directory.is_symlink() or not directory.is_dir():
                workflow_error(f"V5 {label} directory is missing or unsafe")

        try:
            report.research_entries = len(self.research_records())
        except Exception as exc:
            workflow_error(f"invalid V5 Research Ledger: {exc}")
        try:
            novelty_events = self.store._read_jsonl(self.store.novelty_log)
            report.novelty_entries = len(novelty_events)
            for message in self._audit_novelty():
                workflow_error(f"novelty: {message}")
        except Exception as exc:
            workflow_error(f"invalid V5 novelty ledger: {exc}")
        try:
            report.quarantined_contributions = len(
                self._quarantine_records()
            )
        except Exception as exc:
            workflow_error(f"invalid V5 research quarantine: {exc}")
        releases: list[dict[str, Any]] = []
        try:
            releases = self.releases()
            report.candidate_releases = len(releases)
            report.candidates = sum(len(item["fact_ids"]) for item in releases)
        except Exception as exc:
            workflow_error(f"invalid V5 Candidate Release store: {exc}")
        decisions: list[dict[str, Any]] = []
        try:
            decisions = self.decisions()
            report.certification_decisions = len(decisions)
        except Exception as exc:
            workflow_error(f"invalid V5 Certification Ledger: {exc}")
        decision_release_ids = [item["release_id"] for item in decisions]
        if len(decision_release_ids) != len(set(decision_release_ids)):
            workflow_error("a Candidate Release has multiple Certification Decisions")

        for manifest_path in sorted(self.store.rounds_dir.glob("*/round.json")):
            try:
                manifest = self.store._read_json(manifest_path)
                if manifest.get("schema_version") != 5:
                    raise ValueError(
                        "V5 root contains a non-V5 mutable round"
                    )
                self._round_manifest(manifest_path.parent.name)
            except Exception as exc:
                workflow_error(
                    f"V5 round {manifest_path.parent.name}: {exc}"
                )

        try:
            facts = self.store.facts()
        except Exception as exc:
            graph_error(f"active Fact visibility failed: {exc}")
            facts = {}
        report.facts = len(facts)
        report.edges = sum(len(fact.predecessors) for fact in facts.values())
        graph = DependencyGraph(facts)
        for fact_id, predecessor in graph.missing_predecessors():
            graph_error(f"{fact_id}: missing active V5 predecessor {predecessor}")
        try:
            graph.topological_order()
            depths = graph.depths()
            report.max_depth = max(depths.values(), default=0)
        except ValueError as exc:
            graph_error(str(exc))

        admission_markers: dict[str, dict[str, Any]] = {}
        admitted_fact_markers: dict[str, dict[str, Any]] = {}
        for directory in sorted(self.admissions_dir.glob("release-*")):
            if directory.is_symlink() or not directory.is_dir():
                workflow_error("V5 admission store contains an unsafe entry")
                continue
            marker_path = directory / "ACCEPTED.json"
            if not marker_path.exists():
                report.warnings.append(
                    f"V5 admission staging {directory.name} has no visibility marker; "
                    "retry fact-admit with the same evidence"
                )
                continue
            try:
                marker, paths = self._validated_admission(directory.name)
                admission_markers[directory.name] = marker
                for fact_id in paths:
                    if fact_id in admitted_fact_markers:
                        raise ValueError(
                            f"Fact {fact_id} has more than one admission marker"
                        )
                    admitted_fact_markers[fact_id] = marker
            except Exception as exc:
                workflow_error(f"V5 admission {directory.name}: {exc}")

        try:
            revoked_ids = self.revoked_fact_ids()
        except Exception as exc:
            workflow_error(f"invalid V5 revocation store: {exc}")
            revoked_ids = set()
        visible_expected = set(admitted_fact_markers).difference(revoked_ids)
        if set(facts) != visible_expected:
            workflow_error(
                "active V5 Fact visibility differs from admission/revocation provenance"
            )

        verification_events = self.store._read_jsonl(self.store.verification_log)
        events_by_fact: dict[str, list[dict[str, Any]]] = {}
        for event in verification_events:
            if event.get("evidence_version") != V5_WORKFLOW_EVIDENCE_VERSION:
                workflow_error(
                    "V5 verification log contains non-V5 admission authority"
                )
                continue
            fact_id = str(event.get("fact_id", ""))
            events_by_fact.setdefault(fact_id, []).append(event)
        for fact_id, marker in admitted_fact_markers.items():
            events = events_by_fact.get(fact_id, [])
            if len(events) != 1:
                workflow_error(
                    f"V5 Fact {fact_id} must have exactly one acceptance event"
                )
                continue
            event = events[0]
            expected_id = sha256_json(
                [
                    "accepted-v5",
                    fact_id,
                    marker["release_id"],
                    marker["decision_id"],
                    marker["acceptance_id"],
                ]
            )
            for key, expected in (
                ("event", "accepted"),
                ("event_id", expected_id),
                ("release_id", marker["release_id"]),
                ("decision_id", marker["decision_id"]),
                ("capsule_sha256", marker["capsule_sha256"]),
                ("acceptance_id", marker["acceptance_id"]),
                ("fact_sha256", marker["fact_sha256"][fact_id]),
            ):
                if event.get(key) != expected:
                    workflow_error(
                        f"V5 Fact {fact_id} acceptance event {key} mismatch"
                    )
                    break
        unknown_event_facts = sorted(set(events_by_fact).difference(admitted_fact_markers))
        if unknown_event_facts:
            workflow_error(
                "V5 acceptance events have no admission marker: "
                + ", ".join(unknown_event_facts)
            )

        for fact_id in sorted(facts):
            try:
                self.store.statement_interface(fact_id, materialize=False)
            except Exception as exc:
                workflow_error(f"V5 statement interface {fact_id}: {exc}")

        targets = self.store.targets()
        report.targets = len(targets)
        unknown_targets = sorted(set(targets).difference(facts))
        if unknown_targets:
            graph_error(
                "V5 targets are not active Facts: " + ", ".join(unknown_targets)
            )
        elif targets:
            try:
                report.target_closure = len(graph.closure(targets))
            except Exception as exc:
                graph_error(f"V5 target closure failed: {exc}")

        try:
            blackboard_report = self.store.blackboard().audit()
        except Exception as exc:
            workflow_error(f"blackboard audit failed: {exc}")
        else:
            report.blackboard_graph_errors.extend(blackboard_report["errors"])
            report.blackboard_graph_warnings.extend(blackboard_report["warnings"])
            for message in blackboard_report["errors"]:
                workflow_error(f"blackboard: {message}")
            report.warnings.extend(
                f"blackboard: {message}" for message in blackboard_report["warnings"]
            )

        try:
            paper_report = self.store.paper_logic().audit(
                blackboard=self.store.blackboard()
            )
        except Exception as exc:
            workflow_error(f"Paper Logic/Audit audit failed: {exc}")
        else:
            report.paper_logic_errors.extend(paper_report["errors"])
            report.paper_logic_warnings.extend(paper_report["warnings"])
            report.paper_source_nodes = paper_report["source_nodes"]
            report.paper_reconstruction_nodes = paper_report[
                "reconstruction_nodes"
            ]
            report.paper_audit_nodes = paper_report["audit_nodes"]
            for message in paper_report["errors"]:
                workflow_error(f"paper_logic: {message}")
            report.warnings.extend(
                f"paper_logic: {message}" for message in paper_report["warnings"]
            )

        try:
            claims_report = self.store.claims().audit()
        except Exception as exc:
            workflow_error(f"claim/convention registry audit failed: {exc}")
        else:
            for message in claims_report["errors"]:
                workflow_error(f"claim/convention registry: {message}")

        def source_claim_exists(claim_id: str) -> bool:
            try:
                self.store.claims().show_claim(claim_id)
            except (KeyError, ValueError, OSError):
                return False
            return True

        try:
            campaign_report = self.store.campaigns().audit(
                fact_exists=lambda fact_id: fact_id in facts,
                source_claim_exists=source_claim_exists,
            )
        except Exception as exc:
            workflow_error(f"campaign audit failed: {exc}")
        else:
            for message in campaign_report["errors"]:
                workflow_error(f"campaign: {message}")

        try:
            pulse_report = self.store.collaboration().audit()
        except Exception as exc:
            workflow_error(f"V5 pulse audit failed: {exc}")
        else:
            for message in pulse_report["errors"]:
                workflow_error(f"V5 pulse: {message}")

        try:
            experiment_report = self.store.experiments().audit_all()
        except Exception as exc:
            workflow_error(f"V5 experiment audit failed: {exc}")
        else:
            for message in experiment_report["errors"]:
                workflow_error(f"V5 experiment: {message}")

        try:
            mode_report = self.store.reasoning_modes().audit()
        except Exception as exc:
            workflow_error(f"reasoning mode audit failed: {exc}")
        else:
            for message in mode_report["errors"]:
                workflow_error(f"reasoning mode: {message}")
            report.warnings.extend(
                f"reasoning mode: {message}"
                for message in mode_report["warnings"]
            )

        return report


def v5_contract_file_sha256(path: Path) -> str:
    """Expose a small test/diagnostic helper without granting write authority."""

    return sha256_bytes(path.read_bytes())

from __future__ import annotations

import json
import os
import re
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
    validate_campaign_id,
    validate_fact_id,
    validate_memory_id,
    validate_round_id,
)
from .applicability import validate_external_refs_for_submission
from .adoption import validate_workload_profile, workload_profile_for_entry
from .campaigns import (
    COMPACT_SCORE_MODEL,
    COMPACT_SCORE_ROLE,
    LEGACY_V4_SCORE_FIELDS,
    actionable_score,
    decision_factors,
    project_legacy_decision_profile,
    validate_decision_profile,
)
from .computations import validate_computational_evidence
from .decision_preflight import V5_FINDING_CLASSES, validate_decision_against_capsule
from .elementary import validate_elementary_uses_for_submission
from .fact_bundles import validate_terminology
from .graph import DependencyGraph
from .proof_lineage import validate_successor_contracts
from .research_draft_preflight import (
    ASSURANCE_REVISION as RESEARCH_DRAFT_ASSURANCE_REVISION,
    PAPER_TRANSPORT_REVISION,
    PREFLIGHT_REVISION as RESEARCH_DRAFT_PREFLIGHT_REVISION,
    research_draft_admission_preflight,
    validate_dependency_receipt,
    validate_research_draft_ref,
    validate_research_draft_assurance,
)
from .project_background import (
    BACKGROUND_BINDING_REVISION,
    BACKGROUND_CHUNK_MAX_BYTES,
    BACKGROUND_INDEX_REVISION,
    MAX_PROJECT_BACKGROUND_BYTES,
    PROJECT_BACKGROUND_FILENAME,
    background_chunk_from_binding,
    build_background_index,
    build_frozen_background_binding,
    current_background_index,
    read_project_background,
    validate_frozen_background_binding,
)
from .interfaces import (
    build_statement_interface,
    clause_is_stage_sensitive,
    extract_geometric_objects,
    extract_statement_clauses,
    referenced_premise_clause_tokens,
    validate_predecessor_uses,
    validate_quantifier_ledger,
    validate_statement_interface,
    write_interface_once,
)
from .markdown import parse_fact_markdown, validate_fact_round_trip
from .model import Fact
from .modes import FACT_ADMISSION_CONTRACT_SHA256
from .adverse_routing import (
    ADVERSE_STRUCTURED_ATTACK_TASK_CARD_SCHEMAS,
    PRODUCTIVE_ATTACK_OUTCOMES,
    validate_adverse_domain_profile,
    validate_attack_learning,
)
from .v5_assurance import (
    V5_ASSURANCE_CONTRACT_REVISION,
    V5_LEGACY_ASSURANCE_CONTRACT_REVISION,
    build_assurance_contract,
    validate_assurance_contract,
    validate_return_assurance,
)
from .runtime_archive import (
    resolve_historical_runtime,
    runtime_binding_from_root,
    validate_bound_runtime_at,
    validate_runtime_binding,
)


V5_WORKFLOW_EVIDENCE_VERSION = 5
V5_POLICY_REVISION = "chalxius-v5-minimal-core-2"
V5_FACT_EVIDENCE_AUDIT_REVISION = "chalxius-v5-fact-evidence-audit-1"
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
_LOCAL_SOURCE_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_])/(?:Users|Volumes|private|tmp)/[^\s`'\"<>]+"
)
V5_VALIDATION_GRANULARITIES = frozenset(
    {
        "monolithic_theorem",
        "atomic_fact_dag",
        "nodewise_proof_dag",
        "paper_target_closure",
    }
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
V5_PROJECT_BACKGROUND_FILENAME = PROJECT_BACKGROUND_FILENAME
V5_MAX_PROJECT_BACKGROUND_BYTES = MAX_PROJECT_BACKGROUND_BYTES
V5_LEGACY_TASK_CONTEXT_REVISION = "chalxius-v5-task-context-0.4.3-2"
V5_TASK_CONTEXT_REVISION = "chalxius-v5-task-context-0.4.4-1"
V5_CONTEXT_SELECTION_REVISION = "chalxius-v5-context-selection-0.4.4-1"
V5_CAMPAIGN_SCOPE_REVISION = "chalxius-v5-campaign-scope-1"
V5_MAX_CONTEXT_SNAPSHOT_NODES = 256
V5_MAX_CONTEXT_SNAPSHOT_EDGES = 512
V5_MAX_SOURCE_RESEARCH_DOSSIER_BYTES = 256 * 1024
V5_MAX_CAMPAIGN_SNAPSHOT_BYTES = 256 * 1024
V5_SOURCE_RESEARCH_DOSSIER_FIELDS = (
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
)
V5_ATTACK_TARGET_METADATA_FIELDS = (
    "attack_target_release_id",
    "attack_target_decision_id",
)
V5_NEUTRAL_DECISION_PROFILE = {
    "impact": 0.5,
    "information_value": 0.5,
    "tractability": 0.5,
    "burden": 0.5,
}
V5_PROGRAM_MATH_REVIEW_DECISION_PROFILE = {
    "impact": 0.95,
    "information_value": 0.95,
    "tractability": 0.8,
    "burden": 0.35,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _parse_utc_timestamp(value: Any, *, label: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} is not an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _require_nonempty_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    return value.strip()


def _require_exact_object_fields(
    payload: Any,
    required: set[str],
    *,
    label: str,
    pointer: str,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError(f"{label} at {pointer or '/'} must be an object")
    missing = sorted(required.difference(payload))
    unexpected = sorted(set(payload).difference(required))
    if missing or unexpected:
        diagnostics = [
            *[f"missing={pointer}/{key}" for key in missing],
            *[f"unexpected={pointer}/{key}" for key in unexpected],
        ]
        raise ValueError(f"{label} fields are not exact: " + "; ".join(diagnostics))
    return payload


def _require_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) for item in value
    ):
        raise ValueError(f"{label} must be a list of strings")
    return list(value)


def _research_decision_profile(metadata: dict[str, Any]) -> dict[str, float]:
    """Project frozen Research metadata into the compact ordering model.

    This is an ephemeral scheduling projection only.  Legacy eight-field
    records remain byte-for-byte unchanged and explicit Research ids remain
    schedulable regardless of score.
    """

    supplied = metadata.get("decision_profile")
    legacy_present = set(LEGACY_V4_SCORE_FIELDS).intersection(metadata)
    if supplied is not None and legacy_present:
        raise ValueError(
            "Research scheduling metadata cannot mix decision_profile with legacy metrics"
        )
    if supplied is not None:
        return validate_decision_profile(supplied)
    if legacy_present:
        missing = sorted(set(LEGACY_V4_SCORE_FIELDS).difference(metadata))
        if missing:
            raise ValueError(
                "Research legacy scheduling metrics are incomplete: "
                + ", ".join(missing)
            )
        return project_legacy_decision_profile(
            {key: metadata[key] for key in LEGACY_V4_SCORE_FIELDS}
        )
    return dict(V5_NEUTRAL_DECISION_PROFILE)


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
    paper_continuation_plans: int = 0
    paper_continuation_complete_plans: int = 0
    paper_continuation_targets: int = 0
    paper_continuation_researched: int = 0
    paper_continuation_dispositioned: int = 0
    paper_continuation_unresolved: int = 0
    paper_continuation_successor_mapped: int = 0
    paper_continuation_revised_manuscript_covered: int = 0
    paper_continuation_adequacy_complete: bool | None = None
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
            "paper_continuation": {
                "plans": self.paper_continuation_plans,
                "complete_plans": self.paper_continuation_complete_plans,
                "targets": self.paper_continuation_targets,
                "researched": self.paper_continuation_researched,
                "dispositioned": self.paper_continuation_dispositioned,
                "unresolved": self.paper_continuation_unresolved,
                "successor_mapped": self.paper_continuation_successor_mapped,
                "revised_manuscript_covered": (
                    self.paper_continuation_revised_manuscript_covered
                ),
                "adequacy_complete": (
                    self.paper_continuation_adequacy_complete
                ),
                "authority_effect": "none",
            },
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
        self.paper_continuation().initialize()
        self.research_draft().initialize()
        self.parallel_verification().initialize()

    def paper_continuation(self) -> Any:
        from .paper_continuation import PaperContinuationManager

        return PaperContinuationManager(self)

    def research_draft(self) -> Any:
        from .research_draft import ResearchDraftManager

        return ResearchDraftManager(self)

    def parallel_verification(self) -> Any:
        from .parallel_verification_lifecycle import (
            ParallelVerificationLifecycleManager,
        )

        return ParallelVerificationLifecycleManager(self)

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
        metadata = record["metadata"]
        _research_decision_profile(metadata)
        validate_adverse_domain_profile(metadata.get("adverse_domain_profile"))
        self._research_is_adverse_assignment(record)
        if "workload_profile" in metadata:
            validate_workload_profile(metadata["workload_profile"])
        assurance_revision = metadata.get(
            "assurance_contract_revision",
            V5_LEGACY_ASSURANCE_CONTRACT_REVISION,
        )
        if assurance_revision not in {
            V5_ASSURANCE_CONTRACT_REVISION,
            V5_LEGACY_ASSURANCE_CONTRACT_REVISION,
        }:
            raise ValueError("research assurance contract revision is invalid")
        if assurance_revision == V5_ASSURANCE_CONTRACT_REVISION:
            artifacts = metadata.get("artifacts", [])
            if not isinstance(artifacts, list) or any(
                not isinstance(item, dict)
                or set(item) != {"path", "sha256", "role"}
                for item in artifacts
            ):
                raise ValueError(
                    "current Research artifacts must be exact path/hash/role objects"
                )
            seen_artifact_roles: set[str] = set()
            for item in artifacts:
                relpath = _require_nonempty_text(
                    item["path"], "Research artifact path"
                )
                digest = _require_nonempty_text(
                    item["sha256"], "Research artifact SHA-256"
                )
                role = _require_nonempty_text(
                    item["role"], "Research artifact role"
                )
                if SHA256_RE.fullmatch(digest) is None:
                    raise ValueError("Research artifact SHA-256 is invalid")
                if role in seen_artifact_roles:
                    raise ValueError("Research artifact roles must be unique")
                seen_artifact_roles.add(role)
                artifact_path = contained_path(
                    self.store.root, relpath, "Research artifact path"
                )
                if (
                    artifact_path.is_symlink()
                    or not artifact_path.is_file()
                    or sha256_bytes(artifact_path.read_bytes()) != digest
                ):
                    raise ValueError("Research artifact is missing, unsafe, or drifted")
            invalidations = metadata.get("route_invalidations", [])
            if not isinstance(invalidations, list) or any(
                not isinstance(item, str) or MEMORY_ID_RE.fullmatch(item) is None
                for item in invalidations
            ):
                raise ValueError("Research route_invalidations must be V5 Research ids")
            if len(invalidations) != len(set(invalidations)):
                raise ValueError("Research route_invalidations must be unique")
        if "brave_future_repair_contract" in metadata:
            # Prospective only.  Replay performs exact structural validation;
            # cross-record coverage/cycle semantics are rechecked by the BF
            # projector and BF audit without changing historical authority.
            from .brave_future import validate_repair_contract_structure

            validate_repair_contract_structure(record)
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

    @staticmethod
    def _research_assurance_revision(record: dict[str, Any]) -> str:
        metadata = record.get("metadata", {})
        if not isinstance(metadata, dict):
            return V5_LEGACY_ASSURANCE_CONTRACT_REVISION
        value = metadata.get(
            "assurance_contract_revision",
            V5_LEGACY_ASSURANCE_CONTRACT_REVISION,
        )
        return str(value)

    @staticmethod
    def _research_is_adverse_assignment(record: dict[str, Any]) -> bool:
        metadata = record.get("metadata", {})
        if not isinstance(metadata, dict):
            return False
        provenance = metadata.get("assignment_provenance")
        if provenance is None:
            return False
        required = {
            "schema_version",
            "round_id",
            "assignment_id",
            "worker_id",
            "task_card_sha256",
            "work_mode",
            "adverse_assignment",
        }
        if not isinstance(provenance, dict) or set(provenance) != required:
            raise ValueError("Research assignment provenance fields are not exact")
        if provenance.get("schema_version") != 1:
            raise ValueError("Research assignment provenance schema is unsupported")
        validate_round_id(
            _require_nonempty_text(provenance.get("round_id"), "provenance round id")
        )
        validate_assignment_id(
            _require_nonempty_text(
                provenance.get("assignment_id"), "provenance assignment id"
            )
        )
        worker_id = _require_nonempty_text(
            provenance.get("worker_id"), "provenance worker id"
        )
        if worker_id != record.get("actor"):
            raise ValueError("Research assignment provenance worker/actor mismatch")
        task_card_sha = _require_nonempty_text(
            provenance.get("task_card_sha256"), "provenance task-card hash"
        )
        if SHA256_RE.fullmatch(task_card_sha) is None:
            raise ValueError("Research assignment provenance task-card hash is invalid")
        work_mode = provenance.get("work_mode")
        if work_mode not in WORK_MODES:
            raise ValueError("Research assignment provenance work mode is invalid")
        adverse = provenance.get("adverse_assignment")
        if not isinstance(adverse, bool) or adverse != (work_mode == "refute"):
            raise ValueError("Research adverse-assignment provenance is inconsistent")
        task_binding = metadata.get("task_binding")
        if isinstance(task_binding, dict):
            for key in ("round_id", "assignment_id", "task_card_sha256"):
                if task_binding.get(key) != provenance[key]:
                    raise ValueError(
                        "Research assignment provenance/task binding mismatch"
                    )
        return adverse

    def _typed_research_artifacts(
        self,
        record: dict[str, Any],
    ) -> list[dict[str, str]]:
        if (
            self._research_assurance_revision(record)
            != V5_ASSURANCE_CONTRACT_REVISION
        ):
            return []
        artifacts = record["metadata"].get("artifacts", [])
        result: list[dict[str, str]] = []
        for item in artifacts:
            path = contained_path(
                self.store.root,
                item["path"],
                "Research capability artifact",
            )
            if (
                path.is_symlink()
                or not path.is_file()
                or sha256_bytes(path.read_bytes()) != item["sha256"]
            ):
                raise ValueError("Research capability artifact drifted")
            result.append(
                {
                    "path": item["path"],
                    "sha256": item["sha256"],
                    "role": f"{record['research_id']}:{item['role']}",
                    "source_research_id": record["research_id"],
                }
            )
        return result

    @staticmethod
    def _research_is_source_dependent(record: dict[str, Any]) -> bool:
        metadata = record.get("metadata", {})
        explicit = metadata.get("source_dependent", False)
        if not isinstance(explicit, bool):
            raise ValueError("Research source_dependent must be boolean")
        source_text = "\n".join(
            str(record.get(field, ""))
            for field in ("claim", "content", "rationale", "source")
        )
        return explicit or _LOCAL_SOURCE_PATH_RE.search(source_text) is not None

    def add_research(
        self,
        payload: dict[str, Any],
        *,
        actor: str,
        task_binding: dict[str, str] | None = None,
        assurance_contract_revision: str = V5_LEGACY_ASSURANCE_CONTRACT_REVISION,
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
            "assurance_contract_revision",
        }
        metadata = {
            key: value for key, value in payload.items() if key not in reserved
        }
        decision_profile = _research_decision_profile(metadata)
        validate_adverse_domain_profile(metadata.get("adverse_domain_profile"))
        if "decision_profile" in metadata:
            metadata["decision_profile"] = decision_profile
            metadata["score_model"] = COMPACT_SCORE_MODEL
        if "workload_profile" in metadata:
            metadata["workload_profile"] = validate_workload_profile(
                metadata["workload_profile"]
            )
        if assurance_contract_revision not in {
            V5_ASSURANCE_CONTRACT_REVISION,
            V5_LEGACY_ASSURANCE_CONTRACT_REVISION,
        }:
            raise ValueError("research assurance contract revision is invalid")
        metadata["assurance_contract_revision"] = assurance_contract_revision
        if assurance_contract_revision == V5_ASSURANCE_CONTRACT_REVISION:
            artifacts = metadata.get("artifacts", [])
            if not isinstance(artifacts, list) or any(
                not isinstance(item, dict)
                or set(item) != {"path", "sha256", "role"}
                for item in artifacts
            ):
                raise ValueError(
                    "current Research artifacts must be exact path/hash/role objects"
                )
            seen_roles: set[str] = set()
            for item in artifacts:
                relpath = _require_nonempty_text(
                    item["path"], "Research artifact path"
                )
                digest = _require_nonempty_text(
                    item["sha256"], "Research artifact SHA-256"
                )
                role = _require_nonempty_text(
                    item["role"], "Research artifact role"
                )
                if SHA256_RE.fullmatch(digest) is None:
                    raise ValueError("Research artifact SHA-256 is invalid")
                if role in seen_roles:
                    raise ValueError("Research artifact roles must be unique")
                seen_roles.add(role)
                artifact_path = contained_path(
                    self.store.root, relpath, "Research artifact path"
                )
                if (
                    artifact_path.is_symlink()
                    or not artifact_path.is_file()
                    or sha256_bytes(artifact_path.read_bytes()) != digest
                ):
                    raise ValueError(
                        "Research artifact is missing, unsafe, or hash-mismatched"
                    )
            source_dependent = metadata.get("source_dependent", False)
            if not isinstance(source_dependent, bool):
                raise ValueError("Research source_dependent must be boolean")
            prospective_record = {
                "claim": claim,
                "content": content,
                "rationale": rationale,
                "source": source,
                "metadata": metadata,
            }
            if self._research_is_source_dependent(prospective_record) and not artifacts:
                raise ValueError(
                    "source-dependent current Research requires at least one exact "
                    "project-relative path/SHA-256/role artifact capability"
                )
            invalidations = metadata.get("route_invalidations", [])
            if not isinstance(invalidations, list) or any(
                not isinstance(item, str) or MEMORY_ID_RE.fullmatch(item) is None
                for item in invalidations
            ):
                raise ValueError("Research route_invalidations must be V5 Research ids")
            if len(invalidations) != len(set(invalidations)):
                raise ValueError("Research route_invalidations must be unique")
            if invalidations and kind not in {
                "challenge",
                "counterexample",
                "obstacle",
                "dead_end",
            }:
                raise ValueError(
                    "only adverse or dead-end Research may invalidate a route"
                )
            for target_id in invalidations:
                self._research_record(target_id)
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
        self._research_is_adverse_assignment(semantic)
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
        if "brave_future_repair_contract" in metadata:
            from .brave_future import validate_repair_contract_semantics

            campaign_id = metadata.get("campaign_id")
            if not isinstance(campaign_id, str):
                raise ValueError(
                    "Brave Future repair Research requires an explicit Campaign id"
                )
            self.store.campaigns().status(campaign_id)
            existing_records = {
                item["research_id"]: item for item in self.research_records()
            }
            validate_repair_contract_semantics(
                record,
                {**existing_records, research_id: record},
            )
        path = self._research_path(research_id)
        with self.store.v5_mutation_lock(command="research-add"):
            if path.exists():
                existing = self._research_record(research_id)
                if existing["semantic_sha256"] != semantic_sha:
                    raise ValueError(f"research id collision at {path}")
                return existing
            continuation = self.paper_continuation()
            prepared_status_index = continuation._status_index.prepare_research(
                record
            )
            self.store._write_json_once(path, record)
            continuation._status_index.commit_research(prepared_status_index)
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
                if (
                    record["kind"] not in adverse_kinds
                    and not self._research_is_adverse_assignment(record)
                ) or research_id in selected:
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

    def _route_staleness(
        self,
        records: dict[str, dict[str, Any]],
    ) -> dict[str, list[str]]:
        """Project explicit route invalidations without rewriting Research.

        A current-contract adverse/dead-end Research entry may invalidate exact
        earlier Research ids.  Descendants remain visibly stale until a later
        copy-on-write repair branch names the invalidated id.  Historical bytes
        and statuses are unchanged; this projection only prevents accidental
        reuse of a known-bad route.
        """

        invalidations: list[tuple[str, str, str]] = []
        for invalidator_id, record in records.items():
            metadata = record.get("metadata", {})
            if not isinstance(metadata, dict):
                continue
            for target_id in metadata.get("route_invalidations", []):
                if target_id in records:
                    invalidations.append(
                        (target_id, invalidator_id, record["created_at"])
                    )

        def ancestors(research_id: str) -> set[str]:
            seen: set[str] = set()
            pending = [research_id]
            while pending:
                current_id = pending.pop()
                if current_id in seen or current_id not in records:
                    continue
                seen.add(current_id)
                pending.extend(records[current_id]["related_research_ids"])
            return seen

        stale: dict[str, list[str]] = {}
        for research_id, record in records.items():
            lineage = ancestors(research_id)
            for target_id, invalidator_id, invalidated_at in invalidations:
                if research_id == invalidator_id or target_id not in lineage:
                    continue
                repaired = any(
                    candidate["kind"] == "repair"
                    and candidate["created_at"] > invalidated_at
                    and candidate.get("metadata", {}).get(
                        "repair_of_research_id"
                    )
                    == target_id
                    for candidate_id, candidate in records.items()
                    if candidate_id in lineage
                )
                if not repaired:
                    stale.setdefault(research_id, []).append(invalidator_id)
        return {
            research_id: sorted(dict.fromkeys(invalidator_ids))
            for research_id, invalidator_ids in stale.items()
        }

    @staticmethod
    def _campaign_snapshot_bytes(snapshot: dict[str, Any]) -> bytes:
        raw = (
            json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n"
        ).encode("utf-8")
        if len(raw) > V5_MAX_CAMPAIGN_SNAPSHOT_BYTES:
            raise ValueError(
                "V5 Campaign snapshot exceeds the 256 KiB planning cap"
            )
        return raw

    def _campaign_snapshot_for_planning(
        self,
        campaign_id: str,
    ) -> tuple[dict[str, Any], bytes]:
        """Validate and freeze one explicit nontruth Campaign envelope."""

        campaign_id = validate_campaign_id(campaign_id)
        status = self.store.campaigns().status(campaign_id)
        expected_status_fields = {
            "campaign_id",
            "active",
            "name",
            "objective",
            "source_claim_ids",
            "targets",
            "constraints",
            "stop_conditions",
            "value_definition",
            "updates",
            "event_count",
        }
        if not isinstance(status, dict) or set(status) != expected_status_fields:
            raise ValueError("V5 Campaign status fields are not exact")
        if status.get("campaign_id") != campaign_id:
            raise ValueError("V5 Campaign status id mismatch")
        if not isinstance(status.get("active"), bool):
            raise ValueError("V5 Campaign active projection must be boolean")
        for key in ("name", "objective", "value_definition"):
            if not isinstance(status.get(key), str) or not status[key].strip():
                raise ValueError(f"V5 Campaign {key} must be nonempty")
        for key in ("source_claim_ids", "constraints", "stop_conditions"):
            values = status.get(key)
            if (
                not isinstance(values, list)
                or any(not isinstance(item, str) for item in values)
                or len(values) != len(set(values))
            ):
                raise ValueError(f"V5 Campaign {key} must be unique strings")
        event_count = status.get("event_count")
        if (
            isinstance(event_count, bool)
            or not isinstance(event_count, int)
            or event_count < 1
        ):
            raise ValueError("V5 Campaign event count is invalid")
        if not isinstance(status.get("updates"), list) or any(
            not isinstance(item, dict) for item in status["updates"]
        ):
            raise ValueError("V5 Campaign updates must be objects")
        for source_claim_id in status["source_claim_ids"]:
            self.store.claims().show_claim(source_claim_id)
        targets = status.get("targets")
        if not isinstance(targets, dict):
            raise ValueError("V5 Campaign targets must be an object")
        active_fact_ids = set(self.store.fact_ids())
        for target_id, target in targets.items():
            if not isinstance(target_id, str) or not isinstance(target, dict):
                raise ValueError("V5 Campaign target projection is malformed")
            if target.get("target_id") != target_id:
                raise ValueError("V5 Campaign target id projection mismatch")
            if target.get("role") not in {
                "headline_proof",
                "supporting_proof",
                "communication",
            }:
                raise ValueError("V5 Campaign target role is invalid")
            if target.get("status") not in {"active", "archived"}:
                raise ValueError("V5 Campaign target status is invalid")
            for key in ("subject_kind", "subject_id", "label"):
                if not isinstance(target.get(key), str) or not target[key].strip():
                    raise ValueError(f"V5 Campaign target {key} must be nonempty")
            if (
                target["status"] == "active"
                and target["role"] in {"headline_proof", "supporting_proof"}
                and target["subject_id"] not in active_fact_ids
            ):
                raise ValueError(
                    "V5 Campaign active proof target is not an admitted Fact: "
                    + target["subject_id"]
                )
        snapshot = {
            "schema_version": 1,
            "revision": V5_CAMPAIGN_SCOPE_REVISION,
            "campaign_id": campaign_id,
            "campaign_status": status,
            "selection_policy": "explicit_exact_research_campaign_id_match",
            "scheduler": "v5_main_four_factor_frontier",
            "truth_effect": "none",
            "fact_admission_effect": "none",
        }
        return snapshot, self._campaign_snapshot_bytes(snapshot)

    @staticmethod
    def _campaign_scope_from_snapshot(
        snapshot: dict[str, Any],
        *,
        snapshot_relpath: str,
        snapshot_sha256: str,
    ) -> dict[str, Any]:
        required = {
            "schema_version",
            "revision",
            "campaign_id",
            "campaign_status",
            "selection_policy",
            "scheduler",
            "truth_effect",
            "fact_admission_effect",
        }
        if not isinstance(snapshot, dict) or set(snapshot) != required:
            raise ValueError("V5 Campaign snapshot fields are not exact")
        if (
            snapshot.get("schema_version") != 1
            or snapshot.get("revision") != V5_CAMPAIGN_SCOPE_REVISION
            or snapshot.get("selection_policy")
            != "explicit_exact_research_campaign_id_match"
            or snapshot.get("scheduler") != "v5_main_four_factor_frontier"
            or snapshot.get("truth_effect") != "none"
            or snapshot.get("fact_admission_effect") != "none"
        ):
            raise ValueError("V5 Campaign snapshot contract mismatch")
        campaign_id = validate_campaign_id(snapshot.get("campaign_id"))
        status = snapshot.get("campaign_status")
        if not isinstance(status, dict) or status.get("campaign_id") != campaign_id:
            raise ValueError("V5 Campaign snapshot status mismatch")
        targets = status.get("targets")
        if not isinstance(targets, dict):
            raise ValueError("V5 Campaign snapshot targets are invalid")
        active_targets: list[dict[str, str]] = []
        for target_id, target in sorted(targets.items()):
            if not isinstance(target, dict) or target.get("target_id") != target_id:
                raise ValueError("V5 Campaign snapshot target projection is invalid")
            if target.get("status") != "active":
                continue
            compact = {
                key: target.get(key)
                for key in (
                    "target_id",
                    "role",
                    "subject_kind",
                    "subject_id",
                    "label",
                )
            }
            if any(not isinstance(value, str) or not value for value in compact.values()):
                raise ValueError("V5 Campaign active target is not compactable")
            active_targets.append(compact)
        event_count = status.get("event_count")
        if (
            isinstance(event_count, bool)
            or not isinstance(event_count, int)
            or event_count < 1
        ):
            raise ValueError("V5 Campaign snapshot event count is invalid")
        source_claim_ids = _require_string_list(
            status.get("source_claim_ids"), "Campaign snapshot source claim ids"
        )
        constraints = _require_string_list(
            status.get("constraints"), "Campaign snapshot constraints"
        )
        stop_conditions = _require_string_list(
            status.get("stop_conditions"), "Campaign snapshot stop conditions"
        )
        for key in ("objective", "value_definition"):
            if not isinstance(status.get(key), str) or not status[key].strip():
                raise ValueError(f"V5 Campaign snapshot {key} must be nonempty")
        if not isinstance(status.get("active"), bool):
            raise ValueError("V5 Campaign snapshot active state is invalid")
        return {
            "revision": V5_CAMPAIGN_SCOPE_REVISION,
            "campaign_id": campaign_id,
            "selection_policy": snapshot["selection_policy"],
            "scheduler": snapshot["scheduler"],
            "snapshot_relpath": snapshot_relpath,
            "snapshot_sha256": snapshot_sha256,
            "event_count": event_count,
            "active_at_freeze": status["active"],
            "objective": status["objective"],
            "source_claim_ids": source_claim_ids,
            "constraints": constraints,
            "stop_conditions": stop_conditions,
            "value_definition": status["value_definition"],
            "active_targets": active_targets,
            "truth_effect": "none",
            "fact_admission_effect": "none",
        }

    def _validate_campaign_scope_binding(
        self,
        scope: Any,
        *,
        round_id: str,
    ) -> dict[str, Any]:
        if not isinstance(scope, dict):
            raise ValueError("V5 Campaign scope must be one object")
        expected_fields = {
            "revision",
            "campaign_id",
            "selection_policy",
            "scheduler",
            "snapshot_relpath",
            "snapshot_sha256",
            "event_count",
            "active_at_freeze",
            "objective",
            "source_claim_ids",
            "constraints",
            "stop_conditions",
            "value_definition",
            "active_targets",
            "truth_effect",
            "fact_admission_effect",
        }
        if set(scope) != expected_fields:
            raise ValueError("V5 Campaign scope fields are not exact")
        campaign_id = validate_campaign_id(scope.get("campaign_id"))
        expected_relpath = f"rounds/{round_id}/context/campaign.snapshot.json"
        if scope.get("snapshot_relpath") != expected_relpath:
            raise ValueError("V5 Campaign snapshot path is noncanonical")
        digest = scope.get("snapshot_sha256")
        if not isinstance(digest, str) or SHA256_RE.fullmatch(digest) is None:
            raise ValueError("V5 Campaign snapshot hash is invalid")
        snapshot_path = contained_path(
            self.store.root,
            expected_relpath,
            "V5 Campaign snapshot path",
        )
        if snapshot_path.is_symlink() or not snapshot_path.is_file():
            raise ValueError("V5 Campaign snapshot is missing or unsafe")
        raw = snapshot_path.read_bytes()
        if (
            len(raw) > V5_MAX_CAMPAIGN_SNAPSHOT_BYTES
            or sha256_bytes(raw) != digest
        ):
            raise ValueError("V5 Campaign snapshot bytes/hash mismatch")
        try:
            snapshot = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("V5 Campaign snapshot is not valid UTF-8 JSON") from exc
        expected_scope = self._campaign_scope_from_snapshot(
            snapshot,
            snapshot_relpath=expected_relpath,
            snapshot_sha256=digest,
        )
        if scope != expected_scope:
            raise ValueError("V5 Campaign scope drifted from its frozen snapshot")
        current = self.store.campaigns().status(campaign_id)
        if current.get("event_count", 0) < scope["event_count"]:
            raise ValueError("V5 Campaign history was truncated after round freeze")
        return scope

    def frontier(
        self,
        *,
        limit: int = 10,
        include_history: bool = False,
        campaign_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if limit < 1:
            raise ValueError("frontier limit must be positive")
        if campaign_id is not None:
            campaign_id = validate_campaign_id(campaign_id)
            self.store.campaigns().status(campaign_id)
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
        route_staleness = self._route_staleness(bases)
        active_fact_ids = set(self.store.fact_ids())
        visible: list[dict[str, Any]] = []
        for research_id, record in bases.items():
            if (
                campaign_id is not None
                and record["metadata"].get("campaign_id") != campaign_id
            ):
                continue
            projection = dict(record)
            disposition = dispositions.get(research_id)
            if disposition is not None:
                projection["status"] = disposition["metadata"][
                    "disposition_status"
                ]
                projection["latest_disposition_id"] = disposition["research_id"]
                projection["latest_disposition_note"] = disposition["content"]
            if research_id in route_staleness:
                projection["route_status"] = "stale_pending_copy_on_write_repair"
                projection["route_invalidated_by"] = route_staleness[research_id]
                if not include_history:
                    continue
            else:
                projection["route_status"] = "current"
                projection["route_invalidated_by"] = []
            if not include_history and projection["status"] not in ACTIVE_MEMORY_STATUSES:
                continue
            readiness = (
                1.0
                if all(
                    fact_id in active_fact_ids
                    for fact_id in projection["dependencies"]
                )
                else 0.0
            )
            decision_profile = _research_decision_profile(
                projection["metadata"]
            )
            scoring_entry = {"decision_profile": decision_profile}
            projection["decision_profile"] = decision_profile
            projection["decision_factors"] = decision_factors(
                scoring_entry,
                readiness=readiness,
            )
            projection["score_model"] = COMPACT_SCORE_MODEL
            projection["score_role"] = COMPACT_SCORE_ROLE
            projection["readiness"] = readiness
            projection["score"] = actionable_score(
                scoring_entry,
                readiness=readiness,
            )
            projection["id"] = research_id
            visible.append(projection)
        visible.sort(
            key=lambda item: (
                -item["score"],
                item["created_at"],
                item["research_id"],
            )
        )
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

    @staticmethod
    def _mode_architecture_signature(
        entry: dict[str, Any],
        *,
        work_mode: str,
        adverse_routing_enabled: bool,
    ) -> dict[str, Any]:
        """Project every mode-sensitive cross-component effect.

        L2 suggestions are advisory.  They may alter the worker's research
        posture, but they may not silently alter an assurance contract, attach
        an adverse capability, or suppress the later program-math review path.
        Explicit user modes are intentionally outside this equivalence gate.
        """

        obligations = entry["metadata"].get("obligations", [])
        assurance = build_assurance_contract(
            entry=entry,
            obligations=obligations,
            work_mode=work_mode,
            related_artifacts=[],
        )
        stage_count = assurance["computation_stage_count"]
        semantic = {
            "revision": "chalxius-v5-mode-architecture-signature-1",
            "assurance_contract_without_artifact_roles": assurance,
            "frozen_adverse_task_binding": (
                "available_when_refute_selected"
                if adverse_routing_enabled
                else "absent"
            ),
            "program_math_adverse_review": (
                "suppressed_by_refute_mode"
                if stage_count > 0 and work_mode == "refute"
                else (
                    "eligible_when_routing_enabled"
                    if stage_count > 0
                    else "not_applicable"
                )
            ),
        }
        return {**semantic, "signature_sha256": sha256_json(semantic)}

    def _mode_selection(
        self,
        entry: dict[str, Any],
        *,
        requested_mode: str,
        index: int,
        adverse_routing_enabled: bool | None = None,
    ) -> dict[str, Any]:
        if requested_mode != "auto" and requested_mode not in WORK_MODES:
            raise ValueError(f"unsupported work mode: {requested_mode}")
        supplied = entry["metadata"].get("suggested_actions")
        malformed = supplied is not None and (
            not isinstance(supplied, list)
            or any(not isinstance(item, str) for item in supplied)
        )
        suggestions = list(supplied) if isinstance(supplied, list) and not malformed else []
        accepted: list[str] = []
        rejected: list[str] = []
        for suggestion in suggestions:
            if suggestion in WORK_MODES:
                if suggestion not in accepted:
                    accepted.append(suggestion)
            else:
                rejected.append(suggestion)
        default_mode = self._work_mode(entry, index)
        eligible: list[str] = []
        blocked: list[dict[str, str]] = []
        adverse_enabled = (
            self.store.adverse_routes().enabled()
            if adverse_routing_enabled is None
            else adverse_routing_enabled
        )
        if not isinstance(adverse_enabled, bool):
            raise ValueError("adverse-routing freeze state must be boolean")
        default_signature = self._mode_architecture_signature(
            entry,
            work_mode=default_mode,
            adverse_routing_enabled=adverse_enabled,
        )
        eligible_signatures: list[dict[str, str]] = []
        for suggestion in accepted:
            reason: str | None = None
            suggestion_signature = self._mode_architecture_signature(
                entry,
                work_mode=suggestion,
                adverse_routing_enabled=adverse_enabled,
            )
            if (
                suggestion_signature[
                    "assurance_contract_without_artifact_roles"
                ]
                != default_signature[
                    "assurance_contract_without_artifact_roles"
                ]
            ):
                reason = "would_change_assurance_contract"
            elif (
                suggestion_signature["frozen_adverse_task_binding"]
                != default_signature["frozen_adverse_task_binding"]
            ):
                reason = "would_change_active_adverse_routing_capability"
            elif (
                suggestion_signature["program_math_adverse_review"]
                != default_signature["program_math_adverse_review"]
            ):
                reason = "would_change_program_math_adverse_review"
            if reason is None:
                eligible.append(suggestion)
                eligible_signatures.append(
                    {
                        "mode": suggestion,
                        "signature_sha256": suggestion_signature[
                            "signature_sha256"
                        ],
                    }
                )
            else:
                blocked.append({"mode": suggestion, "reason": reason})
        if requested_mode != "auto":
            selected_mode = requested_mode
            source = "explicit_user_mode"
        elif eligible:
            selected_mode = eligible[0]
            source = "bounded_research_suggestion"
        else:
            selected_mode = default_mode
            source = "research_kind_default"
        semantic = {
            "source": source,
            "requested_mode": requested_mode,
            "fallback_index": index,
            "default_mode": default_mode,
            "adverse_routing_enabled_at_freeze": adverse_enabled,
            "raw_suggestions": suggestions,
            "accepted_suggestions": accepted,
            "eligible_suggestions": eligible,
            "rejected_suggestions": rejected,
            "blocked_suggestions": blocked,
            "malformed_suggestions_ignored": malformed,
            "selected_mode": selected_mode,
            "architecture_equivalence": {
                "revision": "chalxius-v5-mode-equivalence-1",
                "rule": "automatic_suggestion_signature_must_equal_default",
                "default_signature_sha256": default_signature[
                    "signature_sha256"
                ],
                "eligible_suggestion_signatures": eligible_signatures,
            },
            "precedence": "explicit_user_mode_over_suggestion_over_kind_default",
            "effect": (
                "hint_applies_only_when_assurance_and_capability_equivalent"
            ),
        }
        return {**semantic, "selection_sha256": sha256_json(semantic)}

    def _promoted_context_binding(
        self,
        entry: dict[str, Any],
        *,
        require_current_origin: bool = True,
    ) -> tuple[dict[str, Any], dict[str, Any]] | None:
        metadata = entry["metadata"]
        required = {
            "origin_blackboard_node_id",
            "origin_blackboard_snapshot_id",
            "origin_blackboard_node_sha256",
            "blackboard_query_sha256",
            "blackboard_query",
            "promotion_task_sha256",
        }
        present = required.intersection(metadata)
        if not present:
            return None
        if present != required:
            raise ValueError(
                "promoted V5 Research has incomplete Blackboard provenance"
            )
        node_id = _require_nonempty_text(
            metadata["origin_blackboard_node_id"],
            "promoted Blackboard origin node id",
        )
        snapshot_id = _require_nonempty_text(
            metadata["origin_blackboard_snapshot_id"],
            "promoted Blackboard origin snapshot id",
        )
        node_sha256 = _require_nonempty_text(
            metadata["origin_blackboard_node_sha256"],
            "promoted Blackboard origin node hash",
        )
        query_sha256 = _require_nonempty_text(
            metadata["blackboard_query_sha256"],
            "promoted Blackboard query hash",
        )
        promotion_task_sha256 = _require_nonempty_text(
            metadata["promotion_task_sha256"],
            "promoted Blackboard task hash",
        )
        if any(
            SHA256_RE.fullmatch(value) is None
            for value in (node_sha256, query_sha256, promotion_task_sha256)
        ):
            raise ValueError("promoted V5 Research has an invalid provenance hash")
        query_value = metadata["blackboard_query"]
        if not isinstance(query_value, dict):
            raise ValueError("promoted V5 Research lacks its Blackboard query")
        query = json.loads(json.dumps(query_value))
        blackboard = self.store.blackboard()
        blackboard.validate_query(query)
        if sha256_json(query) != query_sha256:
            raise ValueError("promoted V5 Research Blackboard query hash mismatch")
        if node_id not in query["seed_node_ids"]:
            raise ValueError(
                "promoted V5 Research query does not seed its origin node"
            )
        if (
            query["node_budget"] > V5_MAX_CONTEXT_SNAPSHOT_NODES
            or query["edge_budget"] > V5_MAX_CONTEXT_SNAPSHOT_EDGES
        ):
            raise ValueError(
                "promoted V5 Research query exceeds the V5 context snapshot budget"
            )
        origin_manifest = blackboard.snapshot_manifest(snapshot_id)
        if origin_manifest["query_sha256"] != query_sha256:
            raise ValueError(
                "promoted V5 Research query disagrees with its origin snapshot"
            )
        origin_entries = {
            item["node_id"]: item["sha256"]
            for item in origin_manifest["node_entries"]
        }
        if origin_entries.get(node_id) != node_sha256:
            raise ValueError(
                "promoted V5 Research node disagrees with its origin snapshot"
            )
        if require_current_origin:
            current_nodes = blackboard.current_nodes()
            if node_id not in current_nodes:
                raise ValueError("promoted V5 Research origin node is no longer active")
            current_sha256 = sha256_bytes(
                json.dumps(
                    current_nodes[node_id],
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("utf-8")
            )
            if current_sha256 != node_sha256:
                raise ValueError("promoted V5 Research origin node hash mismatch")
        lineage = {
            "research_id": entry["research_id"],
            "origin_blackboard_node_id": node_id,
            "origin_blackboard_node_sha256": node_sha256,
            "origin_blackboard_snapshot_id": snapshot_id,
            "blackboard_query_sha256": query_sha256,
            "promotion_task_sha256": promotion_task_sha256,
        }
        return query, lineage

    def _snapshot_for_round(
        self,
        selected: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        blackboard = self.store.blackboard()
        nodes = blackboard.current_nodes()
        spaces = sorted(
            node_id
            for node_id, node in nodes.items()
            if node.get("node_type") == "space"
        )
        if not spaces:
            raise ValueError("V5 round planning requires one Blackboard space")
        promoted = [
            binding
            for entry in selected
            if (binding := self._promoted_context_binding(entry)) is not None
        ]
        if promoted and len(selected) != 1:
            raise ValueError(
                "a promoted Blackboard query must be planned as one exact V5 task; "
                "plan unrelated Research in a separate round"
            )
        if promoted:
            query, lineage = promoted[0]
            source = "promoted_blackboard_query"
            origins = [lineage]
        else:
            query = {
                "seed_node_ids": [spaces[0]],
                "direction": "both",
                "max_hops": 3,
                "edge_type_allowlist": ["*"],
                "node_type_allowlist": ["*"],
                "node_budget": 256,
                "edge_budget": 512,
            }
            source = "default_project_space"
            origins = []
        snapshot = blackboard.snapshot(
            query=query,
            actor="v5-orchestrator",
        )
        semantic = {
            "source": source,
            "query": query,
            "query_sha256": snapshot["query_sha256"],
            "origin_bindings": origins,
            "snapshot_id": snapshot["snapshot_id"],
            "snapshot_sha256": snapshot["snapshot_sha256"],
            "omission_receipt": snapshot["omission_receipt"],
            "budget_contract": {
                "max_nodes": V5_MAX_CONTEXT_SNAPSHOT_NODES,
                "max_edges": V5_MAX_CONTEXT_SNAPSHOT_EDGES,
                "overflow": "fail_before_round_or_explicit_snapshot_omission_receipt",
            },
            "truth_effect": "none",
        }
        return snapshot, {
            **semantic,
            "selection_sha256": sha256_json(semantic),
        }

    def project_background_index(self) -> dict[str, Any] | None:
        return current_background_index(self.store.root)

    @staticmethod
    def _background_snapshot_relpath(round_id: str, source_sha256: str) -> str:
        return (
            f"rounds/{validate_round_id(round_id)}/context/"
            f"project-background-{source_sha256}.md"
        )

    def _freeze_project_background(
        self,
        *,
        round_id: str,
        raw: bytes | None,
        selected_chunk_ids: list[str],
    ) -> dict[str, Any] | None:
        if raw is None:
            if selected_chunk_ids:
                raise ValueError(
                    "background chunk selection requires PROJECT_BACKGROUND.md"
                )
            return None
        source_sha256 = sha256_bytes(raw)
        snapshot_relpath = self._background_snapshot_relpath(
            round_id, source_sha256
        )
        snapshot_path = self.store.root / snapshot_relpath
        self.store._write_bytes_once(snapshot_path, raw)
        return build_frozen_background_binding(
            raw=raw,
            snapshot_relpath=snapshot_relpath,
            selected_chunk_ids=selected_chunk_ids,
        )

    def project_background_chunk(
        self,
        *,
        card: dict[str, Any],
        chunk_id: str,
    ) -> dict[str, Any]:
        self.validate_task_card(card)
        if card.get("task_context_revision") != V5_TASK_CONTEXT_REVISION:
            raise ValueError(
                "exact background chunks require a current indexed V5 task card"
            )
        binding = card["mathematical_state"]["project_background"]
        if binding is None:
            raise ValueError("this V5 task card has no project background")
        return background_chunk_from_binding(
            self.store.root,
            binding,
            chunk_id=_require_nonempty_text(chunk_id, "background chunk id"),
        )

    def current_project_background_chunk(self, chunk_id: str) -> dict[str, Any]:
        raw = read_project_background(self.store.root)
        if raw is None:
            raise ValueError("this V5 project has no PROJECT_BACKGROUND.md")
        binding = build_frozen_background_binding(
            raw=raw,
            snapshot_relpath=V5_PROJECT_BACKGROUND_FILENAME,
            selected_chunk_ids=[],
        )
        return background_chunk_from_binding(
            self.store.root,
            binding,
            chunk_id=_require_nonempty_text(chunk_id, "background chunk id"),
        )

    @staticmethod
    def _context_selection_binding(
        *,
        blackboard_selection: dict[str, Any],
        project_background: dict[str, Any] | None,
        mode_selection: dict[str, Any],
    ) -> dict[str, Any]:
        background_selection = (
            {
                "source_sha256": None,
                "index_sha256": None,
                "selection_receipt": {
                    "compiler_role": "v5_main_planner",
                    "policy": "background_absent",
                    "selected_chunk_ids": [],
                    "unselected_chunk_count": 0,
                    "all_unselected_chunks_retrievable": True,
                    "omission_effect": "none",
                    "selection_sha256": sha256_json(
                        {
                            "compiler_role": "v5_main_planner",
                            "policy": "background_absent",
                            "selected_chunk_ids": [],
                            "unselected_chunk_count": 0,
                            "all_unselected_chunks_retrievable": True,
                            "omission_effect": "none",
                        }
                    ),
                },
            }
            if project_background is None
            else {
                "source_sha256": project_background["source_sha256"],
                "index_sha256": project_background["index"]["index_sha256"],
                "selection_receipt": project_background["selection_receipt"],
            }
        )
        semantic = {
            "revision": V5_CONTEXT_SELECTION_REVISION,
            "compiler_role": "v5_main_planner",
            "blackboard": blackboard_selection,
            "background": background_selection,
            "mode": mode_selection,
            "precedence": [
                "machine_validated_authority",
                "source_research_dossier",
                "task_specific_blackboard_snapshot",
                "project_background_index",
            ],
            "host_mathematical_output_rule": (
                "durable_mathematical_findings_must_enter_research_or_worker_return"
            ),
            "truth_effect": "none",
            "admission_effect": "none",
        }
        return {
            **semantic,
            "context_selection_sha256": sha256_json(semantic),
        }

    def _task_card_path(self, round_id: str, assignment_id: str) -> Path:
        return (
            self.store.rounds_dir
            / validate_round_id(round_id)
            / "task-cards"
            / f"{validate_assignment_id(assignment_id)}.json"
        )

    @staticmethod
    def _runtime_binding() -> dict[str, Any]:
        skill_root = Path(__file__).resolve().parents[2]
        return runtime_binding_from_root(skill_root)

    @staticmethod
    def _validate_bound_runtime_binding(
        value: Any,
        *,
        historical_runtime: bool = False,
    ) -> dict[str, Any]:
        normalized = validate_runtime_binding(value)
        if historical_runtime:
            resolve_historical_runtime(normalized)
        else:
            validate_bound_runtime_at(
                Path(normalized["skill_root"]),
                normalized,
                verify_manifest_tree=True,
            )
        return normalized

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

    def _source_research_dossier(
        self,
        record: dict[str, Any],
    ) -> dict[str, Any]:
        """Project the complete immutable source Research record into a task card."""

        dossier = {
            key: record[key] for key in V5_SOURCE_RESEARCH_DOSSIER_FIELDS
        }
        encoded = json.dumps(
            dossier,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(encoded) > V5_MAX_SOURCE_RESEARCH_DOSSIER_BYTES:
            raise ValueError(
                "source Research dossier exceeds the 256 KiB task-card limit"
            )
        return dossier

    def _task_authority_snapshot(
        self,
        record: dict[str, Any],
        *,
        contract_revision: str = V5_TASK_CONTEXT_REVISION,
    ) -> dict[str, Any]:
        """Bind only task-referenced V5 authority and exact read capabilities.

        PROJECT_BACKGROUND.md remains useful historical context, but it is a
        nontruth document and cannot state the current admission status.  This
        projection is deliberately narrow: ordinary tasks see only their
        explicit Fact references, while an attack receives the exact
        Release/Decision/Admission bundle named in frozen Research metadata.
        """

        metadata = record["metadata"]
        related_fact_id = metadata.get("related_fact_id")
        if related_fact_id is not None:
            if not isinstance(related_fact_id, str):
                raise ValueError("Research related_fact_id must be a Fact id or null")
            related_fact_id = validate_fact_id(related_fact_id)

        attack_values = {
            key: metadata.get(key) for key in V5_ATTACK_TARGET_METADATA_FIELDS
        }
        attack_present = {
            key for key, value in attack_values.items() if value is not None
        }
        if attack_present and attack_present != set(V5_ATTACK_TARGET_METADATA_FIELDS):
            raise ValueError(
                "Research attack target must bind both Candidate Release and "
                "Certification Decision ids"
            )
        if attack_present and related_fact_id is None:
            raise ValueError("Research attack target requires related_fact_id")

        active_paths = self.active_fact_paths()
        revoked_fact_ids = self.revoked_fact_ids()
        referenced_fact_ids = set(record["dependencies"])
        if related_fact_id is not None:
            referenced_fact_ids.add(related_fact_id)

        capabilities: list[dict[str, str]] = []

        def add_capability(path: Path, *, role: str) -> None:
            resolved_root = self.store.root.resolve()
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"V5 authority capability is missing or unsafe: {role}")
            resolved = path.resolve()
            if not resolved.is_relative_to(resolved_root):
                raise ValueError(f"V5 authority capability escapes project root: {role}")
            capabilities.append(
                {
                    "path": resolved.relative_to(resolved_root).as_posix(),
                    "sha256": sha256_bytes(resolved.read_bytes()),
                    "role": role,
                }
            )

        attack_target: dict[str, Any] | None = None
        candidate_sha256: dict[str, str] = {}
        if attack_present:
            release_id = attack_values["attack_target_release_id"]
            decision_id = attack_values["attack_target_decision_id"]
            if not isinstance(release_id, str) or not isinstance(decision_id, str):
                raise ValueError("Research attack target ids must be strings")
            release = self.release(release_id)
            decision = self.decision(decision_id)
            if (
                decision["release_id"] != release_id
                or decision["release_sha256"] != release["release_sha256"]
            ):
                raise ValueError(
                    "Research attack target Release/Decision binding is inconsistent"
                )
            if related_fact_id not in release["fact_ids"]:
                raise ValueError(
                    "Research related_fact_id is outside the attack target Release"
                )

            referenced_fact_ids.update(release["fact_ids"])
            candidate_sha256 = {
                item["fact_id"]: item["fact_sha256"]
                for item in release["candidates"]
            }
            release_path = self._release_path(release_id)
            decision_path = self._decision_path(decision_id)
            add_capability(
                release_path,
                role="attack_target_candidate_release",
            )
            add_capability(
                decision_path,
                role="attack_target_certification_decision",
            )
            for artifact in release["artifacts"]:
                add_capability(
                    contained_path(
                        self.store.root,
                        artifact["sealed_relpath"],
                        "attack target sealed artifact",
                    ),
                    role=f"attack_target_artifact:{artifact['role']}",
                )

            marker_path = self._admission_dir(release_id) / "ACCEPTED.json"
            marker: dict[str, Any] | None = None
            admitted_paths: dict[str, Path] = {}
            if marker_path.is_symlink() or marker_path.exists():
                marker, admitted_paths = self._validated_admission(release_id)
                if marker["decision_id"] != decision_id:
                    raise ValueError(
                        "Research attack target admission used a different Decision"
                    )
                add_capability(
                    marker_path,
                    role="attack_target_admission_marker",
                )
                for fact_id in release["fact_ids"]:
                    add_capability(
                        admitted_paths[fact_id],
                        role=f"attack_target_admitted_fact:{fact_id}",
                    )

            if marker is None:
                admission_status = "not_admitted"
                acceptance_id = None
            elif related_fact_id in revoked_fact_ids:
                admission_status = "revoked"
                acceptance_id = marker["acceptance_id"]
            elif related_fact_id in active_paths:
                admission_status = "active"
                acceptance_id = marker["acceptance_id"]
            else:
                raise ValueError(
                    "Research attack target admission is not visible as active or revoked"
                )
            attack_target = {
                "release_id": release_id,
                "release_sha256": release["release_sha256"],
                "release_record_sha256": release["record_sha256"],
                "decision_id": decision_id,
                "decision_sha256": decision["decision_sha256"],
                "decision_record_sha256": decision["record_sha256"],
                "decision_verdict": decision["verdict"],
                "target_fact_id": related_fact_id,
                "release_fact_ids": list(release["fact_ids"]),
                "admission_status": admission_status,
                "acceptance_id": acceptance_id,
            }

        fact_bindings: list[dict[str, Any]] = []
        for fact_id in sorted(referenced_fact_ids):
            if fact_id in active_paths:
                path = active_paths[fact_id]
                fact_sha = sha256_bytes(path.read_bytes())
                status = "active"
                statement_interface = self.store.statement_interface(
                    fact_id,
                    materialize=False,
                )
            elif fact_id in revoked_fact_ids:
                fact_sha = candidate_sha256.get(fact_id)
                status = "revoked"
                statement_interface = None
            elif fact_id in candidate_sha256:
                fact_sha = candidate_sha256[fact_id]
                status = "candidate_only"
                statement_interface = None
            else:
                fact_sha = None
                status = "missing"
                statement_interface = None
            fact_bindings.append(
                {
                    "fact_id": fact_id,
                    "status": status,
                    "fact_sha256": fact_sha,
                    "statement_interface": statement_interface,
                }
            )

        capabilities.sort(
            key=lambda item: (item["role"], item["path"], item["sha256"])
        )
        semantic = {
            "schema_version": 1,
            "contract_revision": contract_revision,
            "research_id": record["research_id"],
            "scope": "task_referenced_v5_authority_only",
            "precedence_rule": (
                "machine_validated_v5_authority_overrides_nontruth_"
                "project_background_status_claims"
            ),
            "background_truth_effect": "none",
            "fact_bindings": fact_bindings,
            "attack_target": attack_target,
            "capabilities": capabilities,
        }
        return {**semantic, "snapshot_sha256": sha256_json(semantic)}

    def _validate_context_selection(
        self,
        *,
        card: dict[str, Any],
        source_research: dict[str, Any],
    ) -> dict[str, Any]:
        selection = card.get("context_selection")
        required = {
            "revision",
            "compiler_role",
            "blackboard",
            "background",
            "mode",
            "precedence",
            "host_mathematical_output_rule",
            "truth_effect",
            "admission_effect",
            "context_selection_sha256",
        }
        if not isinstance(selection, dict) or set(selection) != required:
            raise ValueError("V5 context-selection fields are not exact")
        selection_semantic = {
            key: value
            for key, value in selection.items()
            if key != "context_selection_sha256"
        }
        if (
            selection["revision"] != V5_CONTEXT_SELECTION_REVISION
            or selection["compiler_role"] != "v5_main_planner"
            or selection["precedence"]
            != [
                "machine_validated_authority",
                "source_research_dossier",
                "task_specific_blackboard_snapshot",
                "project_background_index",
            ]
            or selection["host_mathematical_output_rule"]
            != "durable_mathematical_findings_must_enter_research_or_worker_return"
            or selection["truth_effect"] != "none"
            or selection["admission_effect"] != "none"
            or selection["context_selection_sha256"]
            != sha256_json(selection_semantic)
        ):
            raise ValueError("V5 context-selection contract/hash is invalid")
        blackboard_selection = selection.get("blackboard")
        blackboard_required = {
            "source",
            "query",
            "query_sha256",
            "origin_bindings",
            "snapshot_id",
            "snapshot_sha256",
            "omission_receipt",
            "budget_contract",
            "truth_effect",
            "selection_sha256",
        }
        if (
            not isinstance(blackboard_selection, dict)
            or set(blackboard_selection) != blackboard_required
        ):
            raise ValueError("V5 Blackboard context-selection fields are not exact")
        blackboard_semantic = {
            key: value
            for key, value in blackboard_selection.items()
            if key != "selection_sha256"
        }
        if blackboard_selection["selection_sha256"] != sha256_json(
            blackboard_semantic
        ):
            raise ValueError("V5 Blackboard context-selection hash mismatch")
        if (
            blackboard_selection["snapshot_id"]
            != card["blackboard_view"]["snapshot_id"]
            or blackboard_selection["snapshot_sha256"]
            != card["blackboard_view"]["snapshot_sha256"]
            or blackboard_selection["truth_effect"] != "none"
            or blackboard_selection["budget_contract"]
            != {
                "max_nodes": V5_MAX_CONTEXT_SNAPSHOT_NODES,
                "max_edges": V5_MAX_CONTEXT_SNAPSHOT_EDGES,
                "overflow": (
                    "fail_before_round_or_explicit_snapshot_omission_receipt"
                ),
            }
        ):
            raise ValueError("V5 Blackboard context-selection binding is invalid")
        query = blackboard_selection.get("query")
        if not isinstance(query, dict):
            raise ValueError("V5 Blackboard context-selection query is invalid")
        self.store.blackboard().validate_query(query)
        if (
            blackboard_selection["query_sha256"] != sha256_json(query)
            or query["node_budget"] > V5_MAX_CONTEXT_SNAPSHOT_NODES
            or query["edge_budget"] > V5_MAX_CONTEXT_SNAPSHOT_EDGES
        ):
            raise ValueError("V5 Blackboard context-selection query/hash is invalid")
        snapshot_id = blackboard_selection["snapshot_id"]
        manifest = self.store.blackboard().snapshot_manifest(snapshot_id)
        manifest_path = (
            self.store.blackboard().snapshots_dir / snapshot_id / "manifest.json"
        )
        if (
            sha256_bytes(manifest_path.read_bytes())
            != blackboard_selection["snapshot_sha256"]
            or manifest["query"] != query
            or manifest["query_sha256"] != blackboard_selection["query_sha256"]
            or manifest["omission_receipt"]
            != blackboard_selection["omission_receipt"]
        ):
            raise ValueError("V5 Blackboard context-selection snapshot drifted")
        source = blackboard_selection["source"]
        if source == "promoted_blackboard_query":
            promoted = self._promoted_context_binding(
                source_research,
                require_current_origin=False,
            )
            if promoted is None:
                raise ValueError(
                    "V5 promoted context selection lacks Research provenance"
                )
            expected_query, expected_lineage = promoted
            if (
                query != expected_query
                or blackboard_selection["origin_bindings"]
                != [expected_lineage]
            ):
                raise ValueError("V5 promoted context selection drifted")
        elif source == "default_project_space":
            if blackboard_selection["origin_bindings"] != []:
                raise ValueError("V5 default context selection has promotion lineage")
            snapshot_nodes, _ = self.store.blackboard().snapshot_objects(snapshot_id)
            if (
                len(query["seed_node_ids"]) != 1
                or snapshot_nodes.get(query["seed_node_ids"][0], {}).get("node_type")
                != "space"
                or query["direction"] != "both"
                or query["max_hops"] != 3
                or query["edge_type_allowlist"] != ["*"]
                or query["node_type_allowlist"] != ["*"]
                or query["node_budget"] != V5_MAX_CONTEXT_SNAPSHOT_NODES
                or query["edge_budget"] != V5_MAX_CONTEXT_SNAPSHOT_EDGES
            ):
                raise ValueError("V5 default context selection query is invalid")
        else:
            raise ValueError("V5 Blackboard context-selection source is unsupported")
        mode_selection = selection.get("mode")
        if not isinstance(mode_selection, dict):
            raise ValueError("V5 mode-selection binding must be an object")
        requested_mode = mode_selection.get("requested_mode")
        fallback_index = mode_selection.get("fallback_index")
        if (
            not isinstance(requested_mode, str)
            or isinstance(fallback_index, bool)
            or not isinstance(fallback_index, int)
            or fallback_index < 0
        ):
            raise ValueError("V5 mode-selection request/index is invalid")
        expected_mode = self._mode_selection(
            source_research,
            requested_mode=requested_mode,
            index=fallback_index,
            adverse_routing_enabled=mode_selection.get(
                "adverse_routing_enabled_at_freeze"
            ),
        )
        if (
            (
                "adverse_routing" in card
                and mode_selection.get("adverse_routing_enabled_at_freeze")
                is not True
            )
            or mode_selection != expected_mode
            or card["work_mode"] != expected_mode["selected_mode"]
        ):
            raise ValueError("V5 mode-selection binding drifted")
        background = card["mathematical_state"].get("project_background")
        if background is not None:
            if not isinstance(background, dict):
                raise ValueError(
                    "V5 indexed project-background binding must be an object"
                )
            expected_snapshot_relpath = self._background_snapshot_relpath(
                card["round_id"],
                _require_nonempty_text(
                    background.get("source_sha256"),
                    "indexed project-background source hash",
                ),
            )
            validate_frozen_background_binding(
                self.store.root,
                background,
                expected_snapshot_relpath=expected_snapshot_relpath,
            )
        expected = self._context_selection_binding(
            blackboard_selection=blackboard_selection,
            project_background=background,
            mode_selection=expected_mode,
        )
        if selection != expected:
            raise ValueError("V5 host context-selection receipt drifted")
        return selection

    def validate_task_card(
        self,
        card: Any,
        *,
        expected_path: Path | None = None,
        historical_runtime: bool = False,
        _runtime_validation_cache: set[tuple[bool, str]] | None = None,
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
        if "adverse_routing" in card:
            required.add("adverse_routing")
        if "assurance_contract" in card:
            required.add("assurance_contract")
        if "task_context_revision" in card:
            required.add("task_context_revision")
        if "runtime_binding" in card:
            required.add("runtime_binding")
        if "campaign_scope" in card:
            required.add("campaign_scope")
        if "paper_continuation_scope" in card:
            required.add("paper_continuation_scope")
        if card.get("task_context_revision") == V5_TASK_CONTEXT_REVISION:
            required.add("context_selection")
        if set(card) != required:
            raise ValueError("V5 task card fields are not exact")
        if (
            card.get("schema_version") != 5
            or card.get("policy_revision") != V5_POLICY_REVISION
            or card.get("project_id") != self.store.project_id()
        ):
            raise ValueError("V5 task card schema/policy/project mismatch")
        if "runtime_binding" in card:
            normalized_runtime = validate_runtime_binding(card["runtime_binding"])
            runtime_cache_key = (
                historical_runtime,
                normalized_runtime["runtime_identity_sha256"],
            )
            if (
                _runtime_validation_cache is None
                or runtime_cache_key not in _runtime_validation_cache
            ):
                self._validate_bound_runtime_binding(
                    normalized_runtime,
                    historical_runtime=historical_runtime,
                )
                if (
                    not historical_runtime
                    and normalized_runtime != self._runtime_binding()
                ):
                    raise ValueError("V5 task-card Chalxius runtime binding drifted")
                if _runtime_validation_cache is not None:
                    _runtime_validation_cache.add(runtime_cache_key)
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
        if "campaign_scope" in card:
            if card.get("campaign_id") is None:
                raise ValueError(
                    "V5 Campaign scope requires an exact task-card campaign id"
                )
            scope = self._validate_campaign_scope_binding(
                card["campaign_scope"],
                round_id=round_id,
            )
            if scope["campaign_id"] != card["campaign_id"]:
                raise ValueError("V5 task-card Campaign scope/id mismatch")
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
        expected_paper_scope = self.paper_continuation().scope_for_research(
            source_research
        )
        if card.get("paper_continuation_scope") != expected_paper_scope:
            raise ValueError(
                "V5 task-card Paper continuation scope drifted or was omitted"
            )
        if context_ids != source_research["related_research_ids"]:
            raise ValueError(
                "V5 task card research_context does not exactly match Research links"
            )
        task_context_revision = card.get("task_context_revision")
        if task_context_revision is not None:
            if task_context_revision not in {
                V5_LEGACY_TASK_CONTEXT_REVISION,
                V5_TASK_CONTEXT_REVISION,
            }:
                raise ValueError("V5 task context revision is unsupported")
            dossier = card["mathematical_state"].get(
                "source_research_dossier"
            )
            if dossier != self._source_research_dossier(source_research):
                raise ValueError(
                    "V5 task-card source Research dossier drifted or is incomplete"
                )
            authority_snapshot = card["mathematical_state"].get(
                "authority_snapshot"
            )
            if authority_snapshot != self._task_authority_snapshot(
                source_research,
                contract_revision=task_context_revision,
            ):
                raise ValueError(
                    "V5 task-card authority snapshot is stale or incomplete"
                )
            if (
                card["narrative_plane"].get("claim") != source_research["claim"]
                or card["narrative_plane"].get("rationale")
                != source_research["rationale"]
            ):
                raise ValueError(
                    "V5 task-card narrative does not match source Research"
                )
            if task_context_revision == V5_TASK_CONTEXT_REVISION:
                self._validate_context_selection(
                    card=card,
                    source_research=source_research,
                )
        if "assurance_contract" in card:
            contract = validate_assurance_contract(card["assurance_contract"])
            if card["obligations"] != contract["obligations"]:
                raise ValueError(
                    "V5 task-card obligations do not match the frozen assurance contract"
                )
            related_artifacts = card["mathematical_state"].get(
                "related_artifacts"
            )
            if not isinstance(related_artifacts, list) or any(
                not isinstance(item, dict)
                or set(item)
                != {"path", "sha256", "role", "source_research_id"}
                for item in related_artifacts
            ):
                raise ValueError(
                    "V5 task-card related_artifacts must be exact capability objects"
                )
            roles: set[str] = set()
            for item in related_artifacts:
                validate_memory_id(item["source_research_id"])
                _require_nonempty_text(item["role"], "related artifact role")
                if item["role"] in roles:
                    raise ValueError(
                        "V5 task-card related artifact roles must be unique"
                    )
                roles.add(item["role"])
                if SHA256_RE.fullmatch(item["sha256"]) is None:
                    raise ValueError("V5 task-card related artifact hash is invalid")
                path = contained_path(
                    self.store.root,
                    item["path"],
                    "V5 task-card related artifact",
                )
                if (
                    path.is_symlink()
                    or not path.is_file()
                    or sha256_bytes(path.read_bytes()) != item["sha256"]
                ):
                    raise ValueError("V5 task-card related artifact drifted")
            if sorted(roles) != contract["related_artifact_roles"]:
                raise ValueError(
                    "V5 task-card related artifact roles disagree with assurance contract"
                )
        if "project_background" not in card["mathematical_state"]:
            raise ValueError("V5 task card project_background binding is missing")
        background = card["mathematical_state"]["project_background"]
        if background is not None:
            if task_context_revision == V5_TASK_CONTEXT_REVISION:
                if not isinstance(background, dict):
                    raise ValueError(
                        "V5 indexed project-background binding must be an object"
                    )
                expected_snapshot_relpath = self._background_snapshot_relpath(
                    round_id,
                    _require_nonempty_text(
                        background.get("source_sha256"),
                        "indexed project-background source hash",
                    ),
                )
                validate_frozen_background_binding(
                    self.store.root,
                    background,
                    expected_snapshot_relpath=expected_snapshot_relpath,
                )
            else:
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
        if "adverse_routing" in card:
            self.store.adverse_routes().validate_task_card_binding(
                card["adverse_routing"],
                work_mode=card["work_mode"],
                related_artifacts=card["mathematical_state"].get(
                    "related_artifacts", []
                ),
                entry=source_research,
            )
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
        adverse_note = ""
        if "adverse_routing" in card:
            adverse_note = (
                "Adverse routing, approved rules, and the attack-learning contract are "
                "frozen in the task card. Include exact structured `attack_learning` for "
                "a surviving counterexample, or for a productive challenge that forces a "
                "load-bearing hypothesis, scope, definition, source, computation, boundary, "
                "or proof-route repair even when the theorem survives. Otherwise return "
                "`attack_learning=null`. A proposal never changes routing without a later "
                "user/operator decision.\n\n"
            )
        assurance_note = ""
        if "assurance_contract" in card:
            assurance_note = (
                "Exact public worker-return schema: "
                "references/v5_worker_return_contract.md; copyable template: "
                "assets/worker_return.v5.assurance-no-adverse.template.json. "
                "This task card uses the prospective assurance contract. "
                "Return exact per-obligation dispositions, a typed computation manifest "
                "when required, and the exact research_assurance object. Related "
                "Research artifacts are authorized only through the frozen allowlist.\n\n"
            )
        campaign_note = ""
        if "campaign_scope" in card:
            campaign_note = (
                "This round was explicitly scoped to the frozen Campaign envelope in "
                "the task card. Use its objective, active targets, constraints, value "
                "definition, and stop conditions as nontruth planning context. Main's "
                "four-factor frontier remains the only scheduler; Campaign status does "
                "not close this task, certify a result, or change Fact admission.\n\n"
            )
        paper_continuation_note = ""
        if "paper_continuation_scope" in card:
            paper_continuation_note = (
                "This is one exact Paper continuation target. Read its complete frozen "
                "target closure and source capabilities from paper_continuation_scope; "
                "state the issue, importance, burden holder, strongest charitable "
                "objection, response or revision, and every independent failure surface. "
                "Produce the required paper_target_analysis artifact. A clean worker "
                "return remains Research only: Main must separately record a current "
                "target disposition and revised-writing mapping before Paper adequacy can "
                "be complete.\n\n"
            )
        task_context_note = ""
        if card.get("task_context_revision") == V5_TASK_CONTEXT_REVISION:
            background = card["mathematical_state"]["project_background"]
            if background is None:
                background_note = (
                    "No PROJECT_BACKGROUND.md was present when this card was frozen. "
                )
            else:
                selected = background["selection_receipt"]["selected_chunk_ids"]
                selected_text = ", ".join(selected) if selected else "none"
                task_card_relpath = (
                    f"rounds/{card['round_id']}/task-cards/"
                    f"{card['assignment_id']}.json"
                )
                background_note = (
                    "PROJECT_BACKGROUND.md is represented only by its complete exact-byte "
                    "index; it is lower-priority nontruth context, not task authority. "
                    f"Planner-committed chunk ids: {selected_text}. Retrieve any exact chunk "
                    "on demand with `project-background-read CHUNK_ID --task-card "
                    f"{task_card_relpath}`. After context compaction, reread the card/index "
                    "and rerun the same retrieval instead of relying on memory. "
                )
            task_context_note = (
                "Read the complete source_research_dossier and the machine-validated "
                "authority_snapshot in mathematical_state. When project-background "
                "prose disagrees about current Fact, Release, Decision, or admission "
                "status, the authority_snapshot controls. Read target evidence only "
                "through its exact path/hash capability list. The context_selection "
                "receipt records the Main-planner-compiled Blackboard query and bounded "
                "mode hint; it does not change capabilities, assurance, truth, or "
                "admission. "
                f"{background_note}\n\n"
            )
        return (
            "# Chalxius V5 worker assignment\n\n"
            f"Round: `{card['round_id']}`  \n"
            f"Assignment: `{card['assignment_id']}`  \n"
            f"Task-card SHA-256: `{task_card_sha256}`\n\n"
            "Read the immutable task card for exact capabilities. Use only its frozen "
            "mathematical-state snapshot. Keep rationale and intuition in the bounded "
            "narrative return fields; do not move them into the control channel.\n\n"
            "Start the worker CHX ledger with this candidate's `scripts/chx_ledger.py` "
            f"and pass `--task-card {self._task_card_path(card['round_id'], card['assignment_id'])}`; "
            "runtime mismatch must fail before the ledger is created.\n\n"
            f"Research claim: {card['narrative_plane']['claim']}\n\n"
            f"{adverse_note}"
            f"{assurance_note}"
            f"{campaign_note}"
            f"{paper_continuation_note}"
            f"{task_context_note}"
            f"Write the exact return to `{card['return_contract']['return_relpath']}` "
            "and hand off only its SHA-256 plus status.\n"
        )

    def create_round(
        self,
        *,
        workers: int,
        mode: str = "auto",
        research_ids: list[str] | None = None,
        campaign_id: str | None = None,
        host_task_scope_id: str | None = None,
        background_chunk_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        if workers < 1:
            raise ValueError("workers must be positive")
        if mode != "auto" and mode not in WORK_MODES:
            raise ValueError(f"unsupported work mode: {mode}")
        if host_task_scope_id is not None:
            host_task_scope_id = _require_nonempty_text(
                host_task_scope_id, "host task scope id"
            )
        if campaign_id is not None:
            campaign_id = validate_campaign_id(campaign_id)
            # Read-only preflight keeps unknown, malformed, or currently invalid
            # Campaigns from influencing selection or creating round bytes.
            self._campaign_snapshot_for_planning(campaign_id)
        selected_background_chunks = _require_string_list(
            background_chunk_ids or [],
            "background chunk ids",
        )
        if len(set(selected_background_chunks)) != len(selected_background_chunks):
            raise ValueError("background chunk ids must be unique")
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
                    limit=max(self._json_count(self.research_entries_dir), workers),
                    campaign_id=campaign_id,
                )
            }
            missing = sorted(set(normalized_ids).difference(by_id))
            if missing:
                scope_note = (
                    f" in Campaign {campaign_id}" if campaign_id is not None else ""
                )
                raise ValueError(
                    "not active V5 Research entries"
                    + scope_note
                    + ": "
                    + ", ".join(missing)
                )
            selected = [by_id[item] for item in normalized_ids]
        else:
            selected = self.frontier(limit=workers, campaign_id=campaign_id)
        if len(selected) != workers:
            scope_note = (
                f" in Campaign {campaign_id}" if campaign_id is not None else ""
            )
            raise ValueError(
                f"requested {workers} workers but only {len(selected)} active "
                f"V5 Research entries{scope_note} are available"
            )

        with self.store.v5_mutation_lock(command="plan-round"):
            planned_runtime_binding = validate_runtime_binding(
                self._runtime_binding()
            )
            self._validate_bound_runtime_binding(
                planned_runtime_binding,
                historical_runtime=False,
            )
            if planned_runtime_binding != self._runtime_binding():
                raise ValueError(
                    "V5 round runtime changed during preflight"
                )
            runtime_validation_cache: set[tuple[bool, str]] = {
                (
                    False,
                    planned_runtime_binding["runtime_identity_sha256"],
                )
            }
            campaign_snapshot: dict[str, Any] | None = None
            campaign_snapshot_raw: bytes | None = None
            if campaign_id is not None:
                campaign_snapshot, campaign_snapshot_raw = (
                    self._campaign_snapshot_for_planning(campaign_id)
                )
                mismatched = sorted(
                    entry["research_id"]
                    for entry in selected
                    if entry["metadata"].get("campaign_id") != campaign_id
                )
                if mismatched:
                    raise ValueError(
                        "selected Research drifted outside explicit Campaign scope: "
                        + ", ".join(mismatched)
                    )
            source_records = {
                entry["research_id"]: self._research_record(entry["research_id"])
                for entry in selected
            }
            source_dossiers = {
                research_id: self._source_research_dossier(record)
                for research_id, record in source_records.items()
            }
            authority_snapshots = {
                research_id: self._task_authority_snapshot(record)
                for research_id, record in source_records.items()
            }
            for research_id, record in source_records.items():
                if (
                    self._research_is_source_dependent(record)
                    and not self._typed_research_artifacts(record)
                    and not authority_snapshots[research_id]["capabilities"]
                ):
                    raise ValueError(
                        "source-dependent Research cannot be planned without an exact "
                        "project-relative path/SHA-256/role artifact capability; append "
                        "a current-assurance Research successor instead of trusting prose"
                    )
            background_raw = read_project_background(self.store.root)
            if background_raw is None:
                if selected_background_chunks:
                    raise ValueError(
                        "background chunk ids require PROJECT_BACKGROUND.md"
                    )
            else:
                available_background_chunks = {
                    item["chunk_id"]
                    for item in build_background_index(background_raw)["chunks"]
                }
                unknown_background_chunks = sorted(
                    set(selected_background_chunks).difference(
                        available_background_chunks
                    )
                )
                if unknown_background_chunks:
                    raise ValueError(
                        "unknown PROJECT_BACKGROUND.md chunk ids: "
                        + ", ".join(unknown_background_chunks)
                    )
            mode_selections = {
                entry["research_id"]: self._mode_selection(
                    entry,
                    requested_mode=mode,
                    index=index,
                )
                for index, entry in enumerate(selected)
            }
            snapshot, blackboard_selection = self._snapshot_for_round(selected)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            round_id = (
                f"round-{stamp}-"
                f"{sha256_json([[item['research_id'] for item in selected], time.time_ns()])[:8]}"
            )
            validate_round_id(round_id)
            campaign_scope: dict[str, Any] | None = None
            campaign_snapshot_relpath: str | None = None
            if campaign_snapshot is not None and campaign_snapshot_raw is not None:
                campaign_snapshot_relpath = (
                    f"rounds/{round_id}/context/campaign.snapshot.json"
                )
                campaign_scope = self._campaign_scope_from_snapshot(
                    campaign_snapshot,
                    snapshot_relpath=campaign_snapshot_relpath,
                    snapshot_sha256=sha256_bytes(campaign_snapshot_raw),
                )
            round_dir = self.store.rounds_dir / round_id
            assignments_dir = round_dir / "assignments"
            task_cards_dir = round_dir / "task-cards"
            returns_dir = round_dir / "returns"
            artifacts_dir = round_dir / "artifacts"
            work_dir = round_dir / "work"
            context_dir = round_dir / "context"
            for directory in (
                assignments_dir,
                task_cards_dir,
                returns_dir,
                artifacts_dir,
                work_dir,
                context_dir,
            ):
                directory.mkdir(parents=True, exist_ok=False)
            if (
                campaign_snapshot_raw is not None
                and campaign_snapshot_relpath is not None
            ):
                self.store._write_bytes_once(
                    self.store.root / campaign_snapshot_relpath,
                    campaign_snapshot_raw,
                )
            project_background = self._freeze_project_background(
                round_id=round_id,
                raw=background_raw,
                selected_chunk_ids=selected_background_chunks,
            )

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
            snapshot_nodes, _ = self.store.blackboard().snapshot_objects(
                snapshot["snapshot_id"]
            )
            default_spaces = sorted(
                node_id
                for node_id, node in all_nodes.items()
                if node.get("node_type") == "space"
            )[:1]
            assignments: list[dict[str, Any]] = []
            for index, entry in enumerate(selected, 1):
                mode_selection = mode_selections[entry["research_id"]]
                work_mode = mode_selection["selected_mode"]
                assignment_id = f"a{index:02d}-{entry['research_id']}-{work_mode}"
                validate_assignment_id(assignment_id)
                prompt_relpath = f"rounds/{round_id}/assignments/{assignment_id}.md"
                task_card_relpath = f"rounds/{round_id}/task-cards/{assignment_id}.json"
                return_relpath = f"rounds/{round_id}/returns/{assignment_id}.json"
                artifact_dir_relpath = f"rounds/{round_id}/artifacts/{assignment_id}"
                work_dir_relpath = f"rounds/{round_id}/work/{assignment_id}"
                requested_spaces = entry["metadata"].get(
                    "blackboard_write_space_ids"
                )
                if requested_spaces is None:
                    requested_spaces = [
                        space_id
                        for space_id in default_spaces
                        if space_id in snapshot_nodes
                    ]
                write_spaces = _require_string_list(
                    requested_spaces, "research Blackboard write spaces"
                )
                for space_id in write_spaces:
                    if (
                        all_nodes.get(space_id, {}).get("node_type") != "space"
                        or space_id not in snapshot_nodes
                    ):
                        raise ValueError(
                            "research Blackboard write spaces must name spaces in the "
                            "frozen snapshot"
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
                related_artifacts: list[dict[str, str]] = []
                related_artifacts.extend(self._typed_research_artifacts(entry))
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
                    related_artifacts.extend(
                        self._typed_research_artifacts(related_record)
                    )
                deduplicated_related_artifacts: dict[
                    tuple[str, str], dict[str, str]
                ] = {}
                for artifact in related_artifacts:
                    key = (artifact["source_research_id"], artifact["role"])
                    existing = deduplicated_related_artifacts.get(key)
                    if existing is not None and existing != artifact:
                        raise ValueError(
                            "Research artifact capability role has conflicting bytes"
                        )
                    deduplicated_related_artifacts[key] = artifact
                related_artifacts = sorted(
                    deduplicated_related_artifacts.values(),
                    key=lambda item: (
                        item["source_research_id"],
                        item["role"],
                        item["sha256"],
                    ),
                )
                required_related_roles = _require_string_list(
                    entry["metadata"].get(
                        "required_related_artifact_roles", []
                    ),
                    "research required related artifact roles",
                )
                available_unqualified_roles = {
                    item["role"].split(":", 1)[-1]
                    for item in related_artifacts
                }
                missing_related_roles = sorted(
                    set(required_related_roles).difference(
                        available_unqualified_roles
                    )
                )
                if missing_related_roles:
                    raise ValueError(
                        "Research work requires capability-bound related artifacts: "
                        + ", ".join(missing_related_roles)
                    )
                adverse_routing = self.store.adverse_routes().task_card_binding(
                    entry=entry,
                    work_mode=work_mode,
                    related_artifacts=related_artifacts,
                )
                assurance_contract = build_assurance_contract(
                    entry=entry,
                    obligations=obligations,
                    work_mode=work_mode,
                    related_artifacts=related_artifacts,
                )
                context_selection = self._context_selection_binding(
                    blackboard_selection=blackboard_selection,
                    project_background=project_background,
                    mode_selection=mode_selection,
                )
                paper_continuation_scope = (
                    self.paper_continuation().scope_for_research(entry)
                )
                card_semantic = {
                    "schema_version": 5,
                    "policy_revision": V5_POLICY_REVISION,
                    "task_context_revision": V5_TASK_CONTEXT_REVISION,
                    "runtime_binding": planned_runtime_binding,
                    "context_selection": context_selection,
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
                        "source_research_dossier": source_dossiers[
                            entry["research_id"]
                        ],
                        "research_context": research_context,
                        "related_artifacts": related_artifacts,
                        "authority_snapshot": authority_snapshots[
                            entry["research_id"]
                        ],
                        "project_background": project_background,
                        "read_space_ids": sorted(
                            node_id
                            for node_id, node in snapshot_nodes.items()
                            if node.get("node_type") == "space"
                        ),
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
                    "obligations": assurance_contract["obligations"],
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
                    "assurance_contract": assurance_contract,
                }
                if adverse_routing is not None:
                    card_semantic["adverse_routing"] = adverse_routing
                if campaign_scope is not None:
                    card_semantic["campaign_scope"] = campaign_scope
                if paper_continuation_scope is not None:
                    card_semantic["paper_continuation_scope"] = (
                        paper_continuation_scope
                    )
                card = {
                    **card_semantic,
                    "task_card_semantic_sha256": sha256_json(card_semantic),
                }
                card_path = self.store.root / task_card_relpath
                self.store._write_json_once(card_path, card)
                self.validate_task_card(
                    card,
                    expected_path=card_path,
                    _runtime_validation_cache=runtime_validation_cache,
                )
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
            if campaign_scope is not None:
                manifest_semantic["campaign_scope"] = campaign_scope
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
        if "campaign_scope" in manifest:
            required.add("campaign_scope")
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
        campaign_scope = manifest.get("campaign_scope")
        if campaign_scope is not None:
            campaign_scope = self._validate_campaign_scope_binding(
                campaign_scope,
                round_id=round_id,
            )
        abort = self.store.reasoning_modes().work_unit_abort(round_id)
        assignments = manifest.get("assignments")
        if not isinstance(assignments, list) or not assignments:
            raise ValueError("V5 round assignments must be nonempty")
        seen: set[str] = set()
        frozen_cards: list[tuple[Path, dict[str, Any]]] = []
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
            frozen_cards.append((card_path, self.store._read_json(card_path)))
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
        completed = self._round_is_completed(round_dir, manifest)
        runtime_validation_cache: set[tuple[bool, str]] = set()
        for card_path, card in frozen_cards:
            self.validate_task_card(
                card,
                expected_path=card_path,
                historical_runtime=abort is not None or completed,
                _runtime_validation_cache=runtime_validation_cache,
            )
            if card.get("campaign_scope") != campaign_scope:
                raise ValueError(
                    "V5 round/task-card Campaign scope projections disagree"
                )
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

    def _validated_ingest_receipt(
        self,
        *,
        round_dir: Path,
        assignment: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate one receipt strongly enough to make its task historical."""

        assignment_id = validate_assignment_id(
            _require_nonempty_text(
                assignment.get("assignment_id"), "V5 receipt assignment id"
            )
        )
        receipt_path = round_dir / "returns" / f"{assignment_id}.receipt.json"
        if receipt_path.is_symlink() or not receipt_path.is_file():
            raise ValueError("V5 ingestion receipt is missing or unsafe")
        receipt = self.store._read_json(receipt_path)
        base_fields = {
            "schema_version",
            "policy_revision",
            "project_id",
            "round_id",
            "assignment_id",
            "task_card_sha256",
            "return_sha256",
            "outcome",
            "research_id",
            "effect",
            "receipt_id",
            "created_at",
        }
        attack_fields = {
            "attack_case_id",
            "route_proposal_id",
            "attack_evidence_status",
            "route_activation_policy",
        }
        program_math_fields = {
            "program_math_review_research_id",
            "program_math_review_policy",
        }
        if not isinstance(receipt, dict):
            raise ValueError("V5 ingestion receipt must be one object")
        receipt_fields = set(receipt)
        has_attack = bool(receipt_fields.intersection(attack_fields))
        has_program_math = bool(receipt_fields.intersection(program_math_fields))
        expected_fields = set(base_fields)
        if has_attack:
            expected_fields.update(attack_fields)
        if has_program_math:
            expected_fields.update(program_math_fields)
        if receipt_fields != expected_fields:
            raise ValueError("V5 ingestion receipt fields are not exact")
        if (
            receipt.get("schema_version") != 5
            or receipt.get("policy_revision") != V5_POLICY_REVISION
            or receipt.get("project_id") != self.store.project_id()
            or receipt.get("round_id") != round_dir.name
            or receipt.get("assignment_id") != assignment_id
            or receipt.get("task_card_sha256")
            != assignment.get("task_card_sha256")
            or receipt.get("outcome") not in V5_RETURN_OUTCOMES
        ):
            raise ValueError("V5 ingestion receipt binding is invalid")
        for field_name in ("task_card_sha256", "return_sha256"):
            value = receipt.get(field_name)
            if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
                raise ValueError(f"V5 ingestion receipt {field_name} is invalid")
        _parse_utc_timestamp(
            receipt.get("created_at"), label="V5 ingestion receipt created_at"
        )
        research_id = validate_memory_id(
            _require_nonempty_text(
                receipt.get("research_id"), "V5 ingestion receipt research id"
            )
        )
        self._research_record(research_id)
        return_path = contained_path(
            self.store.root,
            assignment["return_relpath"],
            "V5 ingested return path",
        )
        if (
            return_path.is_symlink()
            or not return_path.is_file()
            or sha256_bytes(return_path.read_bytes()) != receipt["return_sha256"]
        ):
            raise ValueError("V5 ingested return bytes/hash mismatch")

        expected_effect = "one_cumulative_research_entry"
        if has_attack:
            case_id = receipt.get("attack_case_id")
            proposal_id = receipt.get("route_proposal_id")
            if (
                not isinstance(case_id, str)
                or not case_id.startswith("attack-case-")
                or SHA256_RE.fullmatch(case_id.removeprefix("attack-case-")) is None
                or not isinstance(proposal_id, str)
                or not proposal_id.startswith("route-proposal-")
                or SHA256_RE.fullmatch(
                    proposal_id.removeprefix("route-proposal-")
                )
                is None
                or receipt.get("attack_evidence_status")
                not in {
                    "worker_reported_counterexample_nontruth",
                    "worker_reported_productive_challenge_nontruth",
                }
                or receipt.get("route_activation_policy") != "user_decision_only"
            ):
                raise ValueError("V5 ingestion receipt attack binding is invalid")
            cases = {
                item["case_id"]: item for item in self.store.adverse_routes().cases()
            }
            proposals = {
                item["proposal_id"]: item
                for item in self.store.adverse_routes().proposals()
            }
            case = cases.get(case_id)
            proposal = proposals.get(proposal_id)
            if (
                case is None
                or proposal is None
                or proposal.get("case_id") != case_id
                or case.get("round_id") != round_dir.name
                or case.get("assignment_id") != assignment_id
                or case.get("attack_research_id") != research_id
                or case.get("task_card_sha256") != receipt["task_card_sha256"]
                or case.get("return_sha256") != receipt["return_sha256"]
                or case.get("evidence_status")
                != receipt["attack_evidence_status"]
                or proposal.get("activation_policy")
                != receipt["route_activation_policy"]
            ):
                raise ValueError("V5 ingestion receipt attack records are mismatched")
            expected_effect += "_plus_nontruth_attack_proposal"
        if has_program_math:
            program_research_id = validate_memory_id(
                _require_nonempty_text(
                    receipt.get("program_math_review_research_id"),
                    "V5 program-math review Research id",
                )
            )
            if (
                receipt.get("program_math_review_policy")
                != "queued_for_future_multidimensional_frontier"
            ):
                raise ValueError("V5 ingestion receipt program-math policy is invalid")
            self._research_record(program_research_id)
            expected_effect += "_plus_nontruth_program_math_adverse_review"
        if receipt.get("effect") != expected_effect:
            raise ValueError("V5 ingestion receipt effect is invalid")
        semantic = {
            key: value
            for key, value in receipt.items()
            if key not in {"receipt_id", "created_at"}
        }
        if receipt.get("receipt_id") != "research-ingest-" + sha256_json(semantic):
            raise ValueError("V5 ingestion receipt content id mismatch")
        return receipt

    def _round_is_completed(
        self,
        round_dir: Path,
        manifest: dict[str, Any],
    ) -> bool:
        """A round is historical only after every assignment has a valid receipt."""

        completed = True
        for assignment in manifest["assignments"]:
            assignment_id = validate_assignment_id(assignment["assignment_id"])
            receipt_path = round_dir / "returns" / f"{assignment_id}.receipt.json"
            if receipt_path.is_symlink():
                raise ValueError("V5 ingestion receipt path is unsafe")
            if not receipt_path.is_file():
                completed = False
                continue
            self._validated_ingest_receipt(
                round_dir=round_dir,
                assignment=assignment,
            )
        return completed

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
        abort = self.store.reasoning_modes().work_unit_abort(round_id)
        completed = self._round_is_completed(round_dir, manifest)
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
            elif abort is not None:
                state = "frozen_aborted"
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
            "frozen_aborted_count": sum(
                item["state"] == "frozen_aborted" for item in assignments
            ),
            "work_unit_state": (
                "aborted"
                if abort is not None
                else "completed"
                if completed
                else "active"
            ),
            "abort_id": abort["abort_id"] if abort is not None else None,
            "work_unit_abort": abort,
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

        if status["work_unit_state"] == "aborted":
            advisory_state = "work_unit_aborted"
        elif any(item["category"] == "return_quarantined" for item in actions):
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
                "frozen_aborted": status["frozen_aborted_count"],
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
        round_dir, manifest = self._round_manifest(round_id)
        assignment = self._assignment(manifest, assignment_id)
        card = self.store._read_json(
            self.store.root / assignment["task_card_relpath"]
        )
        adverse_enabled = "adverse_routing" in card
        if adverse_enabled:
            required.add("attack_learning")
        assurance_enabled = "assurance_contract" in card
        if assurance_enabled:
            required.update(
                {
                    "obligation_dispositions",
                    "computation_manifest",
                    "research_assurance",
                }
            )
        if set(payload) != required:
            missing = sorted(required.difference(payload))
            unknown = sorted(set(payload).difference(required))
            raise ValueError(
                "V5 worker return fields are not exact; "
                f"missing={missing}; unknown={unknown}; exact schema: "
                "references/v5_worker_return_contract.md"
            )
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
        if adverse_enabled:
            current_adverse = card["adverse_routing"].get("schema_version") in (
                ADVERSE_STRUCTURED_ATTACK_TASK_CARD_SCHEMAS
            )
            learning = payload.get("attack_learning")
            if current_adverse:
                if payload["outcome"] == "counterexample":
                    validate_attack_learning(
                        learning,
                        require_current=True,
                        expected_result_kind="surviving_counterexample",
                    )
                elif payload["outcome"] in PRODUCTIVE_ATTACK_OUTCOMES:
                    if learning is not None:
                        validate_attack_learning(
                            learning,
                            require_current=True,
                            expected_result_kind="productive_challenge",
                        )
                elif learning is not None:
                    raise ValueError(
                        "only a surviving counterexample or productive challenge may "
                        "include attack_learning"
                    )
            elif payload["outcome"] == "counterexample":
                validate_attack_learning(learning)
            elif learning is not None:
                raise ValueError(
                    "legacy non-counterexample V5 return requires attack_learning=null"
                )
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
        artifact_fields = (
            {"path", "sha256", "role"}
            if assurance_enabled
            else {"path", "sha256"}
        )
        if not isinstance(artifacts, list) or any(
            not isinstance(item, dict) or set(item) != artifact_fields
            for item in artifacts
        ):
            raise ValueError(
                "V5 worker artifacts must be exact "
                + ("path/hash/role" if assurance_enabled else "path/hash")
                + " objects"
            )
        capability = card["artifact_capability"]
        if len(artifacts) > capability["max_files"]:
            raise ValueError("V5 worker artifact file count exceeds task-card cap")
        total_bytes = 0
        seen_roles: set[str] = set()
        artifact_bytes_by_sha256: dict[str, bytes] = {}
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
            if assurance_enabled:
                role = _require_nonempty_text(
                    item["role"], "V5 worker artifact role"
                )
                if role in seen_roles:
                    raise ValueError("V5 worker artifact roles must be unique")
                seen_roles.add(role)
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
            raw_artifact = artifact_path.read_bytes()
            size = len(raw_artifact)
            if size > capability["max_file_bytes"]:
                raise ValueError("V5 worker artifact exceeds per-file cap")
            total_bytes += size
            if sha256_bytes(raw_artifact) != item["sha256"]:
                raise ValueError("V5 worker artifact bytes/hash mismatch")
            existing_bytes = artifact_bytes_by_sha256.get(item["sha256"])
            if existing_bytes is not None and existing_bytes != raw_artifact:
                raise ValueError("V5 worker artifact SHA-256 collision")
            artifact_bytes_by_sha256[item["sha256"]] = raw_artifact
        if total_bytes > capability["max_total_bytes"]:
            raise ValueError("V5 worker artifacts exceed total-byte cap")
        if assurance_enabled:
            validate_return_assurance(
                payload=payload,
                contract=card["assurance_contract"],
                artifacts=artifacts,
                artifact_bytes_by_sha256=artifact_bytes_by_sha256,
            )
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

    def _enqueue_program_math_adverse_review(
        self,
        *,
        card: dict[str, Any],
        assignment: dict[str, Any],
        result_research: dict[str, Any],
        payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Create a typed Research-stage challenge for a computed return.

        The review is queued only for future scheduling.  It does not run a
        worker, change routing, reject the source Research, or affect Fact
        truth.  Exact program/output bytes are inherited through the normal
        related-Research capability boundary.
        """

        if not self.store.adverse_routes().enabled():
            return None
        if card.get("work_mode") == "refute" or "assurance_contract" not in card:
            return None
        stage_count = card["assurance_contract"].get("computation_stage_count", 0)
        if isinstance(stage_count, bool) or not isinstance(stage_count, int):
            raise ValueError("program-math review stage count is invalid")
        if stage_count == 0 or payload.get("outcome") not in {
            "proof",
            "evidence",
            "insight",
        }:
            return None
        artifacts = payload.get("artifacts", [])
        by_role = {
            item["role"]: item
            for item in artifacts
            if isinstance(item, dict) and isinstance(item.get("role"), str)
        }
        required_roles = {"computation_source", "computation_output"}
        if not required_roles.issubset(by_role):
            raise ValueError(
                "computed Research cannot queue an adverse review without canonical "
                "computation_source and computation_output artifacts"
            )
        manifest = payload.get("computation_manifest")
        manifest_entries = (
            manifest.get("entries", []) if isinstance(manifest, dict) else []
        )
        load_bearing = any(
            isinstance(item, dict) and item.get("role") == "load_bearing"
            for item in manifest_entries
        )
        workload = workload_profile_for_entry(
            {
                "kind": "computation",
                "verification_plan": {
                    "mode": "artifact_replay" if load_bearing else "closed_packet"
                },
                "budgets": {"max_wall_seconds": 0},
            }
        )
        workload["computation"]["stage_count"] = stage_count
        workload = validate_workload_profile(workload)
        source_artifacts = [
            {
                "role": role,
                "sha256": by_role[role]["sha256"],
            }
            for role in sorted(required_roles)
        ]
        review = self.add_research(
            {
                "kind": "challenge",
                "status": "open",
                "claim": (
                    "Adversarially verify the program-mathematics semantic projection for: "
                    + result_research["claim"]
                ),
                "content": (
                    "Attack formula-to-code projection, signs and conventions, index/domain "
                    "boundaries, mathematical-object representation, truncation or precision, "
                    "output interpretation, and non-independent replay. Preserve any valid "
                    "mathematical conclusion outside the exact failure boundary."
                ),
                "rationale": (
                    "A computation-bearing Research result needs an adverse semantic review "
                    "before Candidate promotion; this queue entry has no truth effect."
                ),
                "source": f"research:{result_research['research_id']}",
                "relation": "challenges",
                "related_research_ids": [result_research["research_id"]],
                "logic_signals": [
                    "formula_to_code",
                    "program_math_hybrid",
                ],
                "workload_profile": workload,
                "decision_profile": dict(
                    V5_PROGRAM_MATH_REVIEW_DECISION_PROFILE
                ),
                "required_related_artifact_roles": sorted(required_roles),
                "obligations": [
                    {
                        "obligation_id": "obl-program-math-adverse-review",
                        "description": (
                            "Construct an independent or metamorphic attack on the exact "
                            "formula-code-output chain and report the narrow success boundary."
                        ),
                        "required_artifact_roles": [
                            "computation_output",
                            "computation_source",
                        ],
                        "evidence_types": [
                            "deterministic_output",
                            "executable_source",
                            "runtime_receipt",
                        ],
                        "not_applicable_allowed": False,
                    }
                ],
                "program_math_review": {
                    "source_research_id": result_research["research_id"],
                    "source_task_card_sha256": assignment["task_card_sha256"],
                    "source_artifacts": source_artifacts,
                    "activation": "typed_program_and_output_artifacts",
                },
                "truth_effect": "none",
                "route_effect": "future_refute_task_only",
            },
            actor="v5-adverse-router",
            assurance_contract_revision=V5_ASSURANCE_CONTRACT_REVISION,
        )
        return review

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
            assurance_revision = (
                card["assurance_contract"]["revision"]
                if "assurance_contract" in card
                else V5_LEGACY_ASSURANCE_CONTRACT_REVISION
            )
            assurance_metadata: dict[str, Any] = {}
            if "assurance_contract" in card:
                research_assurance = payload["research_assurance"]
                route_invalidations = list(
                    research_assurance["route_invalidations"]
                )
                for target_id in route_invalidations:
                    self._research_record(target_id)
                assurance_metadata = {
                    "obligation_dispositions": payload[
                        "obligation_dispositions"
                    ],
                    "computation_manifest": payload["computation_manifest"],
                    "research_assurance": research_assurance,
                    "route_invalidations": route_invalidations,
                    "source_uses": research_assurance["source_uses"],
                    "logic_signals": card["assurance_contract"][
                        "risk_signals"
                    ],
                }
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
                    **(
                        {"campaign_id": card["campaign_id"]}
                        if card.get("campaign_id") is not None
                        else {}
                    ),
                    **assurance_metadata,
                    "requested_claim_relation": card[
                        "requested_claim_relation"
                    ],
                    "assignment_provenance": {
                        "schema_version": 1,
                        "round_id": round_id,
                        "assignment_id": assignment_id,
                        "worker_id": assignment["worker_id"],
                        "task_card_sha256": assignment["task_card_sha256"],
                        "work_mode": card["work_mode"],
                        "adverse_assignment": card["work_mode"] == "refute",
                    },
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
                assurance_contract_revision=assurance_revision,
            )
            program_math_review = self._enqueue_program_math_adverse_review(
                card=card,
                assignment=assignment,
                result_research=research,
                payload=payload,
            )
            attack_capture = None
            if "adverse_routing" in card and payload.get("attack_learning") is not None:
                if card["adverse_routing"].get("schema_version") in (
                    ADVERSE_STRUCTURED_ATTACK_TASK_CARD_SCHEMAS
                ):
                    attack_capture = self.store.adverse_routes().capture_attack(
                        card=card,
                        assignment=assignment,
                        payload=payload,
                        attack_research_id=research["research_id"],
                        return_sha256=worker_final_sha256,
                    )
                elif payload["outcome"] == "counterexample":
                    attack_capture = self.store.adverse_routes().capture_counterexample(
                        card=card,
                        assignment=assignment,
                        payload=payload,
                        counterexample_research_id=research["research_id"],
                        return_sha256=worker_final_sha256,
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
            if attack_capture is not None:
                receipt_semantic.update(
                    {
                        "attack_case_id": attack_capture["case_id"],
                        "route_proposal_id": attack_capture["proposal_id"],
                        "attack_evidence_status": attack_capture[
                            "evidence_status"
                        ],
                        "route_activation_policy": attack_capture[
                            "activation_policy"
                        ],
                        "effect": (
                            "one_cumulative_research_entry_plus_nontruth_attack_proposal"
                        ),
                    }
                )
            if program_math_review is not None:
                receipt_semantic.update(
                    {
                        "program_math_review_research_id": program_math_review[
                            "research_id"
                        ],
                        "program_math_review_policy": (
                            "queued_for_future_multidimensional_frontier"
                        ),
                        "effect": (
                            receipt_semantic["effect"]
                            + "_plus_nontruth_program_math_adverse_review"
                        ),
                    }
                )
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
        require_current: bool = True,
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
            if require_current and snapshot_id not in current:
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

    def _validate_evidence_bridge_refs(
        self,
        refs: Any,
        *,
        artifacts: list[dict[str, Any]],
        sealed_record: bool,
        require_current: bool,
    ) -> list[dict[str, Any]]:
        if not isinstance(refs, list) or any(not isinstance(item, dict) for item in refs):
            raise ValueError("evidence_bridge_refs must be a list of objects")
        expected_fields = (
            {
                "bridge_id",
                "bridge_record_sha256",
                "bridge_artifact_sha256",
                "library_id",
                "evidence_ids",
            }
            if sealed_record
            else {"bridge_id", "bridge_artifact_sha256"}
        )
        artifact_bindings: dict[str, Path] = {}
        bridge_artifact_hashes: set[str] = set()
        for artifact in artifacts:
            if sealed_record:
                digest = artifact.get("artifact_sha256")
                role = artifact.get("role")
                relpath = artifact.get("sealed_relpath")
            else:
                digest = artifact.get("sha256")
                role = artifact.get("role")
                relpath = artifact.get("path")
            if role != "evidence_bridge_capsule":
                continue
            if not isinstance(digest, str) or not isinstance(relpath, str):
                raise ValueError("Evidence bridge artifact binding is malformed")
            if digest in artifact_bindings:
                raise ValueError("Evidence bridge artifact hash is duplicated")
            artifact_bindings[digest] = contained_path(
                self.store.root,
                relpath,
                "Evidence bridge capsule artifact",
            )
            bridge_artifact_hashes.add(digest)
        normalized: list[dict[str, Any]] = []
        seen_bridge_ids: set[str] = set()
        seen_evidence_ids: set[str] = set()
        for index, ref in enumerate(refs, 1):
            if set(ref) != expected_fields:
                raise ValueError(
                    f"Evidence bridge ref {index} fields are not exact"
                )
            bridge_id = _require_nonempty_text(ref["bridge_id"], "Evidence bridge id")
            digest = _require_nonempty_text(
                ref["bridge_artifact_sha256"], "Evidence bridge artifact SHA-256"
            )
            if SHA256_RE.fullmatch(digest) is None or digest not in artifact_bindings:
                raise ValueError(
                    "Evidence bridge ref must bind a declared bridge capsule artifact"
                )
            if bridge_id in seen_bridge_ids:
                raise ValueError("Evidence bridge ref is duplicated")
            seen_bridge_ids.add(bridge_id)
            artifact_record = self.store._read_json(artifact_bindings[digest])
            expected_record_sha = artifact_record.get("record_sha256")
            if not isinstance(expected_record_sha, str):
                raise ValueError("Evidence bridge artifact lacks its record hash")
            validated = self.store.evidence().validate_bridge_artifact(
                path=artifact_bindings[digest],
                expected_sha256=digest,
                expected_bridge_id=bridge_id,
                expected_record_sha256=expected_record_sha,
                require_current=require_current,
            )
            if sealed_record and validated != ref:
                raise ValueError("sealed Evidence bridge ref drifted from its capsule")
            overlap = seen_evidence_ids.intersection(validated["evidence_ids"])
            if overlap:
                raise ValueError(
                    "Evidence item is selected by multiple bridge refs: "
                    + ", ".join(sorted(overlap))
                )
            seen_evidence_ids.update(validated["evidence_ids"])
            normalized.append(validated)
        if set(item["bridge_artifact_sha256"] for item in normalized) != bridge_artifact_hashes:
            raise ValueError(
                "every evidence_bridge_capsule artifact must have exactly one Evidence bridge ref"
            )
        normalized.sort(key=lambda item: item["bridge_id"])
        return normalized

    def _validate_requested_assurance(
        self,
        assurance: Any,
        *,
        candidate_ids: set[str],
        internal_edges: list[list[str]],
        candidate_facts: dict[str, Fact] | None = None,
    ) -> dict[str, Any]:
        if (
            isinstance(assurance, dict)
            and assurance.get("contract_revision")
            == RESEARCH_DRAFT_ASSURANCE_REVISION
        ):
            if candidate_facts is None or set(candidate_facts) != candidate_ids:
                raise ValueError(
                    "research-draft assurance requires the exact Candidate Fact set"
                )
            return validate_research_draft_assurance(
                assurance,
                candidate_facts=candidate_facts,
                internal_edges=internal_edges,
            )
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
        elif granularity == "nodewise_proof_dag":
            if len(candidate_ids) < 2 or not internal_edges:
                raise ValueError(
                    "nodewise_proof_dag requires multiple candidates and an internal edge"
                )
            if subject["kind"] != "paper" or not load_bearing:
                raise ValueError(
                    "nodewise_proof_dag requires a paper target and load-bearing nodes"
                )
        else:
            if not candidate_ids:
                raise ValueError(
                    "paper_target_closure requires at least one Candidate Fact"
                )
            if subject["kind"] != "paper" or not load_bearing:
                raise ValueError(
                    "paper_target_closure requires a paper subject and exact closure nodes"
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
        *,
        assurance_contract_revision: str,
    ) -> dict[str, Any]:
        placeholder = sha256_json(["v5-candidate-interface", fact.fact_id])
        return build_statement_interface(
            fact=fact,
            stored_fact_sha256=sha256_bytes(rendered),
            acceptance_event_sha256=placeholder,
            admission_review_id=placeholder,
            workflow_evidence_version=5,
            assurance_contract_revision=assurance_contract_revision,
        )

    def _validate_sealed_research_draft_release(
        self,
        record: dict[str, Any],
        *,
        candidate_facts: dict[str, Fact],
        deep_dependencies: bool,
    ) -> dict[str, Any]:
        """Validate the prospective Paper-admission seam without reopening it N times."""

        evidence = record.get("research_draft_evidence")
        if not isinstance(evidence, dict) or set(evidence) != {
            "plan",
            "batch",
            "adequacy_receipt",
            "research_records",
        }:
            raise ValueError("sealed research-draft evidence fields are not exact")
        plan = evidence["plan"]
        batch = evidence["batch"]
        adequacy = evidence["adequacy_receipt"]
        if not all(isinstance(item, dict) for item in (plan, batch, adequacy)):
            raise ValueError("sealed research-draft evidence records are malformed")
        if plan.get("record_sha256") != sha256_json(
            {key: value for key, value in plan.items() if key != "record_sha256"}
        ):
            raise ValueError("sealed research-draft plan hash mismatch")
        if batch.get("record_sha256") != sha256_json(
            {key: value for key, value in batch.items() if key != "record_sha256"}
        ):
            raise ValueError("sealed research-draft batch hash mismatch")
        if adequacy.get("adequacy_receipt_sha256") != sha256_json(
            {
                key: value
                for key, value in adequacy.items()
                if key != "adequacy_receipt_sha256"
            }
        ):
            raise ValueError("sealed research-draft adequacy receipt hash mismatch")
        validate_research_draft_ref(
            record.get("research_draft_ref"),
            plan=plan,
            batch=batch,
            adequacy_receipt=adequacy,
        )
        research_records = evidence["research_records"]
        if not isinstance(research_records, list) or any(
            not isinstance(item, dict) for item in research_records
        ):
            raise ValueError("sealed research-draft Research records are malformed")
        embedded_research: dict[str, dict[str, Any]] = {}
        for item in research_records:
            research_id = item.get("research_id")
            if not isinstance(research_id, str) or research_id in embedded_research:
                raise ValueError("sealed research-draft Research id is invalid or duplicated")
            if item.get("record_sha256") != sha256_json(
                {key: value for key, value in item.items() if key != "record_sha256"}
            ):
                raise ValueError("sealed research-draft Research record hash mismatch")
            embedded_research[research_id] = item
        expected_research = {
            binding["research_id"]: binding["record_sha256"]
            for binding in record.get("research_bindings", [])
        }
        if set(embedded_research) != set(expected_research) or any(
            embedded_research[research_id]["record_sha256"] != digest
            for research_id, digest in expected_research.items()
        ):
            raise ValueError("sealed research-draft Research closure drifted")
        assurance = validate_research_draft_assurance(
            record.get("requested_assurance"),
            candidate_facts=candidate_facts,
            internal_edges=record.get("internal_edges", []),
        )
        if assurance != record.get("requested_assurance"):
            raise ValueError("sealed research-draft assurance normalization drifted")
        preflight = record.get("research_draft_admission_preflight")
        if not isinstance(preflight, dict):
            raise ValueError("sealed research-draft preflight is missing")
        preflight_semantic = {
            key: value
            for key, value in preflight.items()
            if key not in {"preflight_id", "preflight_sha256"}
        }
        preflight_sha = sha256_json(preflight_semantic)
        if (
            preflight.get("contract_revision")
            != RESEARCH_DRAFT_PREFLIGHT_REVISION
            or preflight.get("preflight_id") != "rdpf-" + preflight_sha
            or preflight.get("preflight_sha256") != preflight_sha
            or preflight.get("structural_status") != "PASS"
            or preflight.get("truth_effect") != "none"
            or set(preflight.get("candidate_fact_ids", [])) != set(candidate_facts)
            or preflight.get("plan_id") != plan.get("plan_id")
            or preflight.get("batch_id") != batch.get("batch_id")
        ):
            raise ValueError("sealed research-draft preflight binding is invalid")
        closure = record.get("paper_evidence_transport_closure")
        if not isinstance(closure, dict):
            raise ValueError("sealed Paper EvidenceRef transport closure is missing")
        closure_semantic = {
            key: value for key, value in closure.items() if key != "closure_sha256"
        }
        if (
            closure.get("contract_revision") != PAPER_TRANSPORT_REVISION
            or closure.get("closure_sha256") != sha256_json(closure_semantic)
            or closure.get("off_project_reconstructable") is not True
            or preflight.get("paper_transport_closure_sha256")
            != closure.get("closure_sha256")
        ):
            raise ValueError("sealed Paper EvidenceRef transport closure drifted")
        members = closure.get("members")
        if not isinstance(members, list) or any(
            not isinstance(item, dict) for item in members
        ):
            raise ValueError("sealed Paper transport members are malformed")
        artifact_bindings = {
            (item.get("artifact_sha256"), item.get("role"))
            for item in record.get("artifacts", [])
        }
        required_members = {
            (item.get("artifact_sha256"), item.get("role")) for item in members
        }
        if not required_members.issubset(artifact_bindings):
            raise ValueError("sealed release omits a Paper transport member")
        ref_snapshot_ids = {
            item.get("snapshot_id") for item in record.get("paper_evidence_refs", [])
        }
        if not ref_snapshot_ids.issubset(set(closure.get("snapshot_ids", []))):
            raise ValueError("sealed Paper EvidenceRef/transport snapshot set drifted")
        receipt = record.get("validated_dependency_receipt")
        receipt_result = self._validate_research_draft_dependency_cache(
            record,
            force_deep=deep_dependencies,
        )
        if receipt.get("validation_subject_sha256") != preflight_sha:
            raise ValueError("validated dependency receipt binds the wrong preflight")
        return receipt_result

    def _validate_research_draft_dependency_cache(
        self,
        record: dict[str, Any],
        *,
        force_deep: bool,
    ) -> dict[str, Any]:
        """Hash only dependency files whose stable local fingerprint changed."""

        receipt = record["validated_dependency_receipt"]
        validate_dependency_receipt(
            receipt,
            project_root=self.store.root,
            changed_dependency_ids=set(),
        )
        fingerprints: dict[str, dict[str, int]] = {}
        for item in receipt["dependencies"]:
            relpath = item["relpath_or_null"]
            if relpath is None:
                continue
            path = contained_path(
                self.store.root,
                relpath,
                "research-draft cached dependency",
            )
            if path.is_symlink() or not path.is_file():
                raise ValueError("research-draft dependency is missing or unsafe")
            stat = path.stat()
            fingerprints[item["dependency_id"]] = {
                "device": stat.st_dev,
                "inode": stat.st_ino,
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "ctime_ns": stat.st_ctime_ns,
            }
        cache_dir = self.candidate_releases_dir / "_dependency_cache"
        cache_path = cache_dir / f"{record['release_id']}.json"
        previous: dict[str, Any] | None = None
        if cache_path.exists():
            if cache_path.is_symlink() or not cache_path.is_file():
                raise ValueError("research-draft dependency cache is unsafe")
            value = self.store._read_json(cache_path)
            if (
                isinstance(value, dict)
                and value.get("release_id") == record["release_id"]
                and value.get("receipt_id") == receipt["receipt_id"]
                and value.get("truth_effect") == "none"
            ):
                previous = value
        previous_fingerprints = (
            previous.get("file_fingerprints", {}) if previous is not None else {}
        )
        changed = (
            set(fingerprints)
            if force_deep or previous is None
            else {
                dependency_id
                for dependency_id, fingerprint in fingerprints.items()
                if previous_fingerprints.get(dependency_id) != fingerprint
            }
        )
        removed = set(previous_fingerprints).difference(fingerprints)
        if removed:
            raise ValueError("research-draft dependency cache inventory drifted")
        if not changed and previous is not None:
            return {
                "receipt_id": receipt["receipt_id"],
                "checked_dependency_ids": [],
                "reuse_mode": "sealed_record_only",
                "truth_effect": "none",
                "cache_status": "reused",
                "changed_dependency_ids": [],
            }
        validation = validate_dependency_receipt(
            receipt,
            project_root=self.store.root,
            changed_dependency_ids=changed,
        )
        cache = {
            "schema_version": 1,
            "release_id": record["release_id"],
            "release_sha256": record["release_sha256"],
            "receipt_id": receipt["receipt_id"],
            "file_fingerprints": fingerprints,
            "last_checked_dependency_ids": validation["checked_dependency_ids"],
            "cache_effect": "performance_only",
            "truth_effect": "none",
        }
        if previous != cache:
            self.store._write_json_atomic(cache_path, cache)
        return {
            **validation,
            "cache_status": "refreshed" if changed else "reused",
            "changed_dependency_ids": sorted(changed),
        }

    def _research_assurance_evidence(
        self,
        *,
        research_records: list[dict[str, Any]],
        authorized_artifact_hashes: set[str],
        assurance_contract_revision: str,
    ) -> list[dict[str, Any]]:
        if assurance_contract_revision != V5_ASSURANCE_CONTRACT_REVISION:
            return []
        evidence: list[dict[str, Any]] = []
        for record in research_records:
            if self._research_assurance_revision(record) != V5_ASSURANCE_CONTRACT_REVISION:
                continue
            metadata = record["metadata"]
            if "task_binding" not in metadata:
                continue
            required = {
                "obligation_dispositions",
                "computation_manifest",
                "research_assurance",
                "artifacts",
            }
            missing = sorted(required.difference(metadata))
            if missing:
                raise ValueError(
                    "task-bound current Research is missing assurance evidence: "
                    + ", ".join(missing)
                )
            artifact_bindings = [
                {
                    "artifact_sha256": item["sha256"],
                    "role": item["role"],
                }
                for item in metadata["artifacts"]
            ]
            missing_hashes = sorted(
                {
                    item["artifact_sha256"] for item in artifact_bindings
                }.difference(authorized_artifact_hashes)
            )
            if missing_hashes:
                raise ValueError(
                    "Candidate Release does not seal and authorize every bound Research "
                    "artifact needed by the verifier: "
                    + ", ".join(missing_hashes)
                )
            evidence.append(
                {
                    "research_id": record["research_id"],
                    "record_sha256": record["record_sha256"],
                    "task_binding": metadata["task_binding"],
                    "obligation_dispositions": metadata[
                        "obligation_dispositions"
                    ],
                    "computation_manifest": metadata["computation_manifest"],
                    "research_assurance": metadata["research_assurance"],
                    "artifact_bindings": sorted(
                        artifact_bindings,
                        key=lambda item: (
                            item["role"],
                            item["artifact_sha256"],
                        ),
                    ),
                }
            )
        if not evidence:
            raise ValueError(
                "current Candidate Release requires at least one task-bound Research "
                "assurance-evidence record"
            )
        return sorted(evidence, key=lambda item: item["research_id"])

    def _applicable_assurance_checks(
        self,
        *,
        facts: dict[str, Fact],
        research_records: list[dict[str, Any]],
        assurance_contract_revision: str,
    ) -> list[str]:
        """Derive only the 0.4.3 checks triggered by this exact release."""

        if assurance_contract_revision != V5_ASSURANCE_CONTRACT_REVISION:
            return []
        checks = {"research_obligation_evidence"}
        risk_signals = {
            signal
            for record in research_records
            for signal in record.get("metadata", {}).get("logic_signals", [])
            if isinstance(signal, str)
        }
        if "topology_extremal_invariants" in risk_signals:
            checks.add("extremal_edge_cases")
        if "parametric_contour_substitution" in risk_signals:
            checks.add("contour_substitution")
        if "claimed_combinatorial_structure" in risk_signals:
            checks.add("structural_computation")
        if "geometric_stage_typing" in risk_signals:
            checks.add("geometric_stage_typing")
        if "program_math_semantic_alignment" in risk_signals or any(
            record.get("metadata", {}).get("computation_manifest") is not None
            for record in research_records
        ):
            checks.add("program_math_semantic_alignment")
        if "source_formula" in risk_signals or "fixed_to_family_transport" in risk_signals:
            checks.add("research_source_use")

        for fact in facts.values():
            for ref in fact.external_refs:
                if ref.get("source_evidence_version") != 4:
                    continue
                checks.update(
                    {
                        "source_transcription_coverage",
                        "source_conclusion_transport",
                        "source_status_evidence",
                    }
                )
                audit = ref.get("critical_audit")
                if isinstance(audit, dict) and any(
                    isinstance(item, dict) and item.get("status") != "pass"
                    for item in audit.get("sanity_checks", [])
                ):
                    checks.add("source_nonpass_reconciliation")
                applicability = ref.get("applicability")
                if isinstance(applicability, dict) and any(
                    isinstance(item, dict) and "contour_substitution" in item
                    for item in applicability.get("transport_obligations", [])
                ):
                    checks.add("contour_substitution")
            if any(
                isinstance(entry, dict) and "claimed_structure" in entry
                for entry in fact.computational_evidence
            ):
                checks.add("structural_computation")
        return sorted(checks)

    def _prepare_candidate_facts(
        self,
        fact_payloads: Any,
        *,
        artifacts: list[dict[str, str]],
        authorized_artifact_hashes: set[str],
        verification_plan: dict[str, Any],
        assurance_contract_revision: str,
        require_geometric_stage_typing: bool = False,
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
                required_source_evidence_version=(
                    4
                    if assurance_contract_revision
                    == V5_ASSURANCE_CONTRACT_REVISION
                    else 3
                ),
                artifact_hashes=authorized_artifact_hashes,
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
                assurance_contract_revision=assurance_contract_revision,
            )
            validate_terminology(fact.terminology, proof=fact.proof)
            typed_objects = extract_geometric_objects(fact.statement)
            if (
                assurance_contract_revision == V5_ASSURANCE_CONTRACT_REVISION
                and require_geometric_stage_typing
                and any(
                    clause_is_stage_sensitive(clause["text"])
                    for clause in clauses
                )
                and not typed_objects
            ):
                raise ValueError(
                    "stage-sensitive Candidate Fact requires explicit [GEO:*] "
                    "stage/ambient/space/genus ownership anchors"
                )
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
            fact_id: self._candidate_interface(
                fact,
                rendered[fact_id],
                assurance_contract_revision=assurance_contract_revision,
            )
            for fact_id, fact in facts.items()
        }

        def interface_lookup(fact_id: str) -> dict[str, Any]:
            if fact_id in candidate_interfaces:
                return candidate_interfaces[fact_id]
            return self.store.statement_interface(fact_id, materialize=False)

        def legacy_premise_resolver(
            source_fact_id: str,
            source_clause: dict[str, Any],
        ) -> list[dict[str, str]]:
            tokens = referenced_premise_clause_tokens(source_clause["text"])
            if not tokens:
                return []
            source_fact = combined[source_fact_id]
            matches: list[dict[str, str]] = []
            for premise_fact_id in source_fact.predecessors:
                interface = validate_statement_interface(
                    interface_lookup(premise_fact_id)
                )
                for clause in interface["clauses"]:
                    if clause["clause_id"].upper() not in tokens:
                        continue
                    statement_sha = sha256_bytes(
                        clause["text"].encode("utf-8")
                    )
                    matches.append(
                        {
                            "fact_id": premise_fact_id,
                            "clause_id": clause["clause_id"],
                            "statement_sha256": statement_sha,
                            "witness_id": (
                                "LEGACY-PREMISE:"
                                f"{premise_fact_id}:{clause['clause_id']}:{statement_sha}"
                            ),
                        }
                    )
            if not matches:
                raise ValueError(
                    "legacy conditional predecessor names a premise clause that "
                    "is not exported by an exact declared predecessor"
                )
            if len(matches) != 1:
                raise ValueError(
                    "legacy conditional predecessor premise reference is ambiguous"
                )
            return sorted(
                matches,
                key=lambda item: (item["fact_id"], item["clause_id"]),
            )

        for fact in facts.values():
            validate_predecessor_uses(
                fact.predecessor_uses,
                predecessors=fact.predecessors,
                proof=fact.proof,
                interface_lookup=interface_lookup,
                convention_profile_ids=fact.convention_profile_ids,
                assurance_contract_revision=assurance_contract_revision,
                target_typed_objects=extract_geometric_objects(fact.statement),
                target_statement_interface=candidate_interfaces[fact.fact_id],
                legacy_premise_resolver=legacy_premise_resolver,
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
        preflight_only: bool = False,
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
        allowed = {
            *required,
            "successor_contracts",
            "evidence_bridge_refs",
            "paper_continuation_ref",
            "philosophy_atomicity",
            "research_draft_ref",
        }
        missing_fields = sorted(required.difference(payload))
        unknown_fields = sorted(set(payload).difference(allowed))
        if missing_fields or unknown_fields:
            raise ValueError(
                "Candidate Release input fields are not exact; "
                f"missing={missing_fields} unknown={unknown_fields} "
                "schema=references/paper_input_contracts.md"
            )
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
        all_research_records = {
            item["research_id"]: item for item in self.research_records()
        }
        stale_routes = self._route_staleness(all_research_records)
        stale_selected = {
            item["research_id"]: stale_routes[item["research_id"]]
            for item in explicit_research_records
            if item["research_id"] in stale_routes
        }
        if stale_selected:
            details = ", ".join(
                f"{research_id} invalidated_by={invalidators}"
                for research_id, invalidators in sorted(stale_selected.items())
            )
            raise ValueError(
                "Candidate Release selects stale Research; create a copy-on-write "
                f"repair branch first: {details}"
            )
        research_records = self._release_research_records(
            explicit_research_records
        )
        assurance_contract_revision = (
            V5_ASSURANCE_CONTRACT_REVISION
            if any(
                self._research_assurance_revision(record)
                == V5_ASSURANCE_CONTRACT_REVISION
                for record in research_records
            )
            else V5_LEGACY_ASSURANCE_CONTRACT_REVISION
        )
        research_logic_signals = {
            signal
            for record in research_records
            for signal in record.get("metadata", {}).get("logic_signals", [])
            if isinstance(signal, str)
        }
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
        authorized_artifact_hashes = {
            item["sha256"]
            for item in validation_artifacts
            if item["role"] in set(authorized_roles)
        }
        bridge_refs = self._validate_evidence_bridge_refs(
            payload.get("evidence_bridge_refs", []),
            artifacts=payload.get("artifacts"),
            sealed_record=False,
            require_current=True,
        )
        if bridge_refs and (
            "evidence_bridge_capsule" not in authorized_roles
            or "evidence_bridge_current" not in required_checks
        ):
            raise ValueError(
                "Evidence bridge use requires an authorized evidence_bridge_capsule "
                "artifact and the evidence_bridge_current certification check"
            )
        (
            facts,
            rendered,
            order,
            internal_edges,
            external_predecessors,
        ) = self._prepare_candidate_facts(
            payload.get("candidates"),
            artifacts=validation_artifacts,
            authorized_artifact_hashes=authorized_artifact_hashes,
            verification_plan=normalized_plan,
            assurance_contract_revision=assurance_contract_revision,
            require_geometric_stage_typing=(
                "geometric_stage_typing" in research_logic_signals
            ),
        )
        successor_input = payload.get("successor_contracts", [])
        if (
            successor_input
            and assurance_contract_revision
            != V5_ASSURANCE_CONTRACT_REVISION
        ):
            raise ValueError(
                "copy-on-write successor contracts are prospective current-assurance only"
            )
        successor_contracts = (
            validate_successor_contracts(
                successor_input,
                candidates=facts,
                active_facts=self.store.facts(),
                active_fact_sha256=lambda fact_id: sha256_bytes(
                    self.store.active_fact_path(fact_id).read_bytes()
                ),
            )
            if assurance_contract_revision == V5_ASSURANCE_CONTRACT_REVISION
            else []
        )
        research_assurance_evidence = self._research_assurance_evidence(
            research_records=research_records,
            authorized_artifact_hashes=authorized_artifact_hashes,
            assurance_contract_revision=assurance_contract_revision,
        )
        applicable_assurance_checks = self._applicable_assurance_checks(
            facts=facts,
            research_records=research_records,
            assurance_contract_revision=assurance_contract_revision,
        )
        if successor_contracts:
            applicable_assurance_checks = sorted(
                {
                    *applicable_assurance_checks,
                    "proof_lineage_conservation",
                }
            )
        missing_assurance_checks = sorted(
            set(applicable_assurance_checks).difference(
                normalized_plan["required_checks"]
            )
        )
        if missing_assurance_checks:
            raise ValueError(
                "Candidate Release omits assurance checks applicable to its exact evidence: "
                + ", ".join(missing_assurance_checks)
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
            candidate_facts=facts,
        )
        strict_research_draft = (
            assurance.get("contract_revision")
            == RESEARCH_DRAFT_ASSURANCE_REVISION
        )
        if (
            strict_research_draft
            and assurance_contract_revision != V5_ASSURANCE_CONTRACT_REVISION
        ):
            raise ValueError(
                "research-draft admission requires current Research assurance"
            )
        if strict_research_draft and (
            "paper_continuation_ref" in payload
            or "philosophy_atomicity" in payload
        ):
            raise ValueError(
                "research_draft_ref cannot be mixed with the legacy Paper continuation path"
            )
        if not strict_research_draft and "research_draft_ref" in payload:
            raise ValueError(
                "research_draft_ref requires the prospective research-draft assurance"
            )
        if (
            assurance.get("contract_revision")
            != RESEARCH_DRAFT_ASSURANCE_REVISION
            and assurance["validation_granularity"] in {
            "nodewise_proof_dag",
            "paper_target_closure",
            }
        ):
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
        continuation = self.paper_continuation()
        continuation_plan_ids = continuation.plan_ids_for_research(
            research_records
        )
        if strict_research_draft and continuation_plan_ids:
            raise ValueError(
                "prospective research-draft admission cannot inherit a legacy continuation plan"
            )
        if len(continuation_plan_ids) > 1:
            raise ValueError(
                "one Candidate Release cannot mix Paper continuation plans"
            )
        continuation_binding: dict[str, Any] | None = None
        continuation_evidence: dict[str, Any] | None = None
        if continuation_plan_ids:
            plan_id = continuation_plan_ids[0]
            continuation_binding = continuation.validate_release_binding(
                plan_id=plan_id,
                ref=payload.get("paper_continuation_ref"),
                philosophy_atomicity=payload.get("philosophy_atomicity"),
                facts=facts,
            )
            plan = continuation_binding["plan"]
            expected_nodes = {
                *plan["selected_reconstruction_node_ids"],
                *plan["selected_source_node_ids"],
            }
            subject = assurance["validation_subject"]
            if (
                assurance["validation_granularity"]
                != "paper_target_closure"
                or subject["kind"] != "paper"
                or subject["subject_id"] != plan["paper_id"]
                or subject["artifact_sha256"]
                != plan["source_artifact_sha256"]
                or set(subject["load_bearing_node_ids"]) != expected_nodes
            ):
                raise ValueError(
                    "Paper continuation release must use paper_target_closure over "
                    "the exact selected source and reconstruction nodes"
                )
            continuation_checks = {"paper_continuation_adequacy"}
            if plan["domain_profile"] in {"philosophy", "mixed"}:
                continuation_checks.update(
                    {
                        "philosophy_semantic_atomicity",
                        "philosophy_plain_language_clarity",
                    }
                )
            missing_continuation_checks = sorted(
                continuation_checks.difference(
                    normalized_plan["required_checks"]
                )
            )
            if missing_continuation_checks:
                raise ValueError(
                    "Paper continuation release omits required certification checks: "
                    + ", ".join(missing_continuation_checks)
                )
            continuation_evidence = continuation.release_evidence(
                plan_id=plan_id,
                disposition_ids=continuation_binding[
                    "paper_continuation_ref"
                ]["disposition_ids"],
                require_current=True,
            )
            required_writing_hashes = {
                item["artifact_sha256"]
                for item in continuation_evidence[
                    "writing_artifact_bindings"
                ]
            }
            authorized_writing_hashes = {
                item["sha256"]
                for item in validation_artifacts
                if item["role"] == "paper_revised_writing"
                and item["role"] in set(authorized_roles)
            }
            missing_writing = sorted(
                required_writing_hashes.difference(authorized_writing_hashes)
            )
            if missing_writing:
                raise ValueError(
                    "Paper continuation release must seal and authorize every revised "
                    "writing artifact as paper_revised_writing: "
                    + ", ".join(missing_writing)
                )
        elif (
            "paper_continuation_ref" in payload
            or "philosophy_atomicity" in payload
        ):
            raise ValueError(
                "Paper continuation release fields require bound continuation Research"
            )
        research_draft_context: dict[str, Any] | None = None
        if strict_research_draft:
            release_ref = payload.get("research_draft_ref")
            if not isinstance(release_ref, dict):
                raise ValueError(
                    "prospective research-draft release requires research_draft_ref"
                )
            plan_id = _require_nonempty_text(
                release_ref.get("plan_id"), "research-draft release plan id"
            )
            manager = self.research_draft()
            plan = manager.plan(plan_id, deep=True)
            current_batch = manager.current_batch(plan_id)
            if current_batch is None:
                raise ValueError(
                    "research-draft plan has no complete current disposition batch"
                )
            batch_id = _require_nonempty_text(
                release_ref.get("batch_id"), "research-draft release batch id"
            )
            if current_batch["batch_id"] != batch_id:
                raise ValueError(
                    "research_draft_ref must bind the exact current disposition batch"
                )
            batch = manager.batch(batch_id, deep=True)
            adequacy_receipt = current_batch["cached_summary"][
                "adequacy_receipt"
            ]
            research_draft_context = {
                "release_ref": release_ref,
                "plan": plan,
                "batch": batch,
                "adequacy_receipt": adequacy_receipt,
            }
        paper_refs = self._validate_paper_evidence_refs(
            payload.get("paper_evidence_refs"),
            validation_subject=assurance["validation_subject"],
        )
        if assurance["validation_subject"]["kind"] == "paper":
            subject_sha = assurance["validation_subject"]["artifact_sha256"]
            if subject_sha not in authorized_artifact_hashes:
                raise ValueError(
                    "paper Candidate Release must authorize its exact source artifact "
                    "for the fresh verifier"
                )
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
        if strict_research_draft:
            research_draft_checks = {
                "composable_parallel_verification",
                "research_draft_admission_preflight",
                "paper_evidence_transport_closure",
                "validated_dependency_receipt",
                "language_neutral_statement_interfaces",
                "semantic_component_atomicity",
                "stance_preservation",
            }
            missing_research_draft_checks = sorted(
                research_draft_checks.difference(normalized_plan["required_checks"])
            )
            if missing_research_draft_checks:
                raise ValueError(
                    "research-draft release omits required certification checks: "
                    + ", ".join(missing_research_draft_checks)
                )
        if continuation_binding is not None:
            plan = continuation_binding["plan"]
            expected_nodes = {
                *plan["selected_reconstruction_node_ids"],
                *plan["selected_source_node_ids"],
            }
            matching_logic_refs = [
                item
                for item in paper_refs
                if item["graph_kind"] == "logic"
                and item["snapshot_id"] == plan["snapshot_id"]
            ]
            if (
                len(matching_logic_refs) != 1
                or set(matching_logic_refs[0]["target_node_ids"])
                != expected_nodes
            ):
                raise ValueError(
                    "Paper continuation release must bind its exact Logic snapshot "
                    "and complete selected closure in one EvidenceRef"
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
            if (
                challenge["kind"]
                not in {"challenge", "counterexample", "obstacle"}
                and not self._research_is_adverse_assignment(challenge)
            ):
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
            or self._research_is_adverse_assignment(record)
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
                or self._research_is_adverse_assignment(record)
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
        candidate_interfaces = [
            self._candidate_interface(
                facts[fact_id],
                rendered[fact_id],
                assurance_contract_revision=assurance_contract_revision,
            )
            for fact_id in order
        ]
        research_draft_preflight: dict[str, Any] | None = None
        if research_draft_context is not None:
            research_draft_preflight = research_draft_admission_preflight(
                store=self.store,
                plan=research_draft_context["plan"],
                batch=research_draft_context["batch"],
                adequacy_receipt=research_draft_context["adequacy_receipt"],
                release_ref=research_draft_context["release_ref"],
                assurance=assurance,
                candidate_facts=facts,
                candidate_fact_file_sha256={
                    fact_id: sha256_bytes(rendered[fact_id])
                    for fact_id in facts
                },
                candidate_interfaces=candidate_interfaces,
                internal_edges=internal_edges,
                external_predecessor_ids=external_predecessors,
                research_bindings=research_bindings,
                paper_evidence_refs=paper_refs,
                artifacts=validation_artifacts,
                authorized_artifact_roles=authorized_roles,
                active_fact_file_sha256=lambda fact_id: sha256_bytes(
                    self.store.active_fact_path(fact_id).read_bytes()
                ),
                revoked_fact_ids=self.revoked_fact_ids(),
            )
            if research_draft_preflight["normalized_assurance"] != assurance:
                raise ValueError(
                    "research-draft assurance normalization drifted across preflight"
                )
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
            **(
                {
                    "research_draft_ref": research_draft_context[
                        "release_ref"
                    ],
                    "research_draft_evidence": {
                        "plan": research_draft_context["plan"],
                        "batch": research_draft_context["batch"],
                        "adequacy_receipt": research_draft_context[
                            "adequacy_receipt"
                        ],
                        "research_records": research_records,
                    },
                    "research_draft_admission_preflight": (
                        research_draft_preflight["preflight"]
                    ),
                    "paper_evidence_transport_closure": (
                        research_draft_preflight["paper_transport_closure"]
                    ),
                    "validated_dependency_receipt": (
                        research_draft_preflight[
                            "validated_dependency_receipt"
                        ]
                    ),
                }
                if research_draft_context is not None
                and research_draft_preflight is not None
                else {}
            ),
            **(
                {
                    "paper_continuation_ref": continuation_binding[
                        "paper_continuation_ref"
                    ],
                    "paper_continuation_evidence": continuation_evidence,
                    **(
                        {
                            "philosophy_atomicity": continuation_binding[
                                "philosophy_atomicity"
                            ]
                        }
                        if continuation_binding["philosophy_atomicity"]
                        is not None
                        else {}
                    ),
                }
                if continuation_binding is not None
                else {}
            ),
            **(
                {"evidence_bridge_refs": bridge_refs}
                if "evidence_bridge_refs" in payload
                else {}
            ),
            "excluded_verifier_ids": excluded_verifier_ids,
            "fact_admission_contract_sha256": FACT_ADMISSION_CONTRACT_SHA256,
            "assurance_contract_revision": assurance_contract_revision,
            **(
                {
                    "applicable_assurance_checks": applicable_assurance_checks,
                    "candidate_interfaces": candidate_interfaces,
                    "research_assurance_evidence": research_assurance_evidence,
                    "successor_contracts": successor_contracts,
                }
                if assurance_contract_revision
                == V5_ASSURANCE_CONTRACT_REVISION
                else {}
            ),
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
        if preflight_only:
            return {
                "valid": True,
                "release_id": release_id,
                "release_sha256": release_sha,
                "assurance_contract_revision": assurance_contract_revision,
                "applicable_assurance_checks": applicable_assurance_checks,
                "successor_contract_count": len(successor_contracts),
                "project_effect": "none",
                "truth_effect": "none",
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
            if strict_research_draft:
                self._validate_research_draft_dependency_cache(
                    record,
                    force_deep=True,
                )
            self.store._write_json_once(path, record)
        return record

    def release(
        self,
        release_id: str,
        *,
        _lineage_facts: dict[str, Fact] | None = None,
        _lineage_paths: dict[str, Path] | None = None,
        _skip_successor_validation: bool = False,
        _deep_dependencies: bool = False,
    ) -> dict[str, Any]:
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
        created_at = _parse_utc_timestamp(
            record.get("created_at"), label="Candidate Release created_at"
        )
        if record.get("fact_admission_contract_sha256") != FACT_ADMISSION_CONTRACT_SHA256:
            raise ValueError("Candidate Release Fact contract mismatch")
        strict_research_draft = (
            record.get("requested_assurance", {}).get("contract_revision")
            == RESEARCH_DRAFT_ASSURANCE_REVISION
        )
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
        if not strict_research_draft:
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
        assurance_revision = record.get(
            "assurance_contract_revision",
            V5_LEGACY_ASSURANCE_CONTRACT_REVISION,
        )
        if assurance_revision not in {
            V5_ASSURANCE_CONTRACT_REVISION,
            V5_LEGACY_ASSURANCE_CONTRACT_REVISION,
        }:
            raise ValueError("Candidate Release assurance revision is unsupported")
        if assurance_revision == V5_ASSURANCE_CONTRACT_REVISION:
            for field in (
                "applicable_assurance_checks",
                "candidate_interfaces",
                "research_assurance_evidence",
                "successor_contracts",
            ):
                if not isinstance(record.get(field), list):
                    raise ValueError(
                        f"current Candidate Release {field} must be a list"
                    )
            candidate_facts = {
                candidate["fact_id"]: parse_fact_markdown(
                    candidate["fact_markdown"]
                )
                for candidate in candidates
            }
            successor_input_fields = {
                "mode",
                "predecessor_fact_id",
                "successor_fact_id",
                "predecessor_fact_sha256",
                "predecessor_proof_sha256",
                "successor_proof_sha256",
                "statement_projection",
                "proof_unit_conservation",
            }
            reconstructed_successor_input = [
                {key: item[key] for key in successor_input_fields}
                for item in record["successor_contracts"]
            ]
            if _skip_successor_validation:
                # Admission discovery is deliberately two phase.  The first
                # phase validates immutable release/admission bytes without
                # asking the active-Fact projection to validate itself.  The
                # second phase supplies a complete, read-only lineage snapshot
                # and replays this contract normally.
                expected_successors = record["successor_contracts"]
            else:
                if (_lineage_facts is None) != (_lineage_paths is None):
                    raise ValueError(
                        "Candidate Release lineage snapshot is incomplete"
                    )
                if _lineage_facts is None or _lineage_paths is None:
                    _lineage_facts, _lineage_paths = self._lineage_snapshot(
                        admitted_before=created_at,
                        exclude_release_ids={release_id},
                    )
                expected_successors = validate_successor_contracts(
                    reconstructed_successor_input,
                    candidates=candidate_facts,
                    active_facts=_lineage_facts,
                    active_fact_sha256=lambda fact_id: sha256_bytes(
                        _lineage_paths[fact_id].read_bytes()
                    ),
                )
            if expected_successors != record["successor_contracts"]:
                raise ValueError("Candidate Release successor contract drifted")
            authorized_roles = set(
                record["verification_plan"]["authorized_artifact_roles"]
            )
            authorized_hashes = {
                item["artifact_sha256"]
                for item in record["artifacts"]
                if item["role"] in authorized_roles
            }
            bound_research = (
                record["research_draft_evidence"]["research_records"]
                if strict_research_draft
                else [
                    self._research_record(binding["research_id"])
                    for binding in record["research_bindings"]
                ]
            )
            expected_evidence = self._research_assurance_evidence(
                research_records=bound_research,
                authorized_artifact_hashes=authorized_hashes,
                assurance_contract_revision=assurance_revision,
            )
            if expected_evidence != record["research_assurance_evidence"]:
                raise ValueError("Candidate Release Research assurance evidence drifted")
            expected_interfaces = [
                self._candidate_interface(
                    candidate_facts[fact_id],
                    next(
                        item["fact_markdown"].encode("utf-8")
                        for item in candidates
                        if item["fact_id"] == fact_id
                    ),
                    assurance_contract_revision=assurance_revision,
                )
                for fact_id in record["fact_ids"]
            ]
            if expected_interfaces != record["candidate_interfaces"]:
                raise ValueError("Candidate Release statement interfaces drifted")
            expected_checks = self._applicable_assurance_checks(
                facts=candidate_facts,
                research_records=bound_research,
                assurance_contract_revision=assurance_revision,
            )
            if expected_successors:
                expected_checks = sorted(
                    {*expected_checks, "proof_lineage_conservation"}
                )
            if expected_checks != record["applicable_assurance_checks"]:
                raise ValueError("Candidate Release applicable assurance checks drifted")
        sealed_candidate_facts = {
            candidate["fact_id"]: parse_fact_markdown(
                candidate["fact_markdown"]
            )
            for candidate in candidates
        }
        if strict_research_draft:
            self._validate_sealed_research_draft_release(
                record,
                candidate_facts=sealed_candidate_facts,
                deep_dependencies=_deep_dependencies,
            )
            bound_research = record["research_draft_evidence"][
                "research_records"
            ]
        else:
            bound_research = [
                self._research_record(binding["research_id"])
                for binding in record["research_bindings"]
            ]
        continuation = self.paper_continuation()
        continuation_plan_ids = continuation.plan_ids_for_research(
            bound_research
        )
        continuation_binding: dict[str, Any] | None = None
        if len(continuation_plan_ids) > 1:
            raise ValueError("Candidate Release mixes Paper continuation plans")
        if continuation_plan_ids:
            continuation_binding = continuation.validate_release_binding(
                plan_id=continuation_plan_ids[0],
                ref=record.get("paper_continuation_ref"),
                philosophy_atomicity=record.get("philosophy_atomicity"),
                facts=sealed_candidate_facts,
                require_current=False,
            )
            expected_nodes = {
                *continuation_binding["plan"][
                    "selected_reconstruction_node_ids"
                ],
                *continuation_binding["plan"]["selected_source_node_ids"],
            }
            subject = record["requested_assurance"]["validation_subject"]
            if (
                record["requested_assurance"]["validation_granularity"]
                != "paper_target_closure"
                or set(subject["load_bearing_node_ids"]) != expected_nodes
            ):
                raise ValueError("Candidate Release Paper continuation scope drifted")
            expected_continuation_evidence = continuation.release_evidence(
                plan_id=continuation_plan_ids[0],
                disposition_ids=record["paper_continuation_ref"][
                    "disposition_ids"
                ],
                require_current=False,
            )
            if record.get("paper_continuation_evidence") != (
                expected_continuation_evidence
            ):
                raise ValueError(
                    "Candidate Release Paper continuation verifier evidence drifted"
                )
        elif (
            "paper_continuation_ref" in record
            or "philosophy_atomicity" in record
            or "paper_continuation_evidence" in record
        ):
            raise ValueError(
                "Candidate Release has unbound Paper continuation fields"
            )
        validated_paper_refs = (
            record.get("paper_evidence_refs", [])
            if strict_research_draft
            else self._validate_paper_evidence_refs(
                record.get("paper_evidence_refs"),
                validation_subject=record["requested_assurance"][
                    "validation_subject"
                ],
                require_current=False,
            )
        )
        if continuation_binding is not None:
            plan = continuation_binding["plan"]
            expected_nodes = {
                *plan["selected_reconstruction_node_ids"],
                *plan["selected_source_node_ids"],
            }
            matching_logic_refs = [
                item
                for item in validated_paper_refs
                if item["graph_kind"] == "logic"
                and item["snapshot_id"] == plan["snapshot_id"]
            ]
            if (
                len(matching_logic_refs) != 1
                or set(matching_logic_refs[0]["target_node_ids"])
                != expected_nodes
            ):
                raise ValueError(
                    "Candidate Release Paper continuation Logic binding drifted"
                )
        if "evidence_bridge_refs" in record:
            self._validate_evidence_bridge_refs(
                record["evidence_bridge_refs"],
                artifacts=record.get("artifacts", []),
                sealed_record=True,
                require_current=False,
            )
        return record

    def releases(self) -> list[dict[str, Any]]:
        if not self.candidate_releases_dir.exists():
            return []
        return [
            self.release(path.stem)
            for path in sorted(self.candidate_releases_dir.glob("release-*.json"))
        ]

    def _require_current_paper_continuation_release(
        self,
        release: dict[str, Any],
    ) -> None:
        bound_research = [
            self._research_record(binding["research_id"])
            for binding in release["research_bindings"]
        ]
        continuation = self.paper_continuation()
        plan_ids = continuation.plan_ids_for_research(bound_research)
        if not plan_ids:
            return
        if len(plan_ids) != 1:
            raise ValueError("Candidate Release mixes Paper continuation plans")
        facts = {
            item["fact_id"]: parse_fact_markdown(item["fact_markdown"])
            for item in release["candidates"]
        }
        binding = continuation.validate_release_binding(
            plan_id=plan_ids[0],
            ref=release.get("paper_continuation_ref"),
            philosophy_atomicity=release.get("philosophy_atomicity"),
            facts=facts,
            require_current=True,
        )
        paper_refs = self._validate_paper_evidence_refs(
            release["paper_evidence_refs"],
            validation_subject=release["requested_assurance"][
                "validation_subject"
            ],
            require_current=True,
        )
        plan = binding["plan"]
        expected_nodes = {
            *plan["selected_reconstruction_node_ids"],
            *plan["selected_source_node_ids"],
        }
        matching_logic_refs = [
            item
            for item in paper_refs
            if item["graph_kind"] == "logic"
            and item["snapshot_id"] == plan["snapshot_id"]
        ]
        if (
            len(matching_logic_refs) != 1
            or set(matching_logic_refs[0]["target_node_ids"])
            != expected_nodes
        ):
            raise ValueError("Candidate Release Paper continuation is stale")

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

    def _source_nonpass_checks(
        self,
        release: dict[str, Any],
    ) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        for candidate in release["candidates"]:
            fact = parse_fact_markdown(candidate["fact_markdown"])
            for ref in fact.external_refs:
                if ref.get("source_evidence_version") != 4:
                    continue
                audit = ref.get("critical_audit")
                if not isinstance(audit, dict):
                    continue
                for check in audit.get("sanity_checks", []):
                    if not isinstance(check, dict) or check.get("status") == "pass":
                        continue
                    result.append(
                        {
                            "fact_id": fact.fact_id,
                            "source_key": str(ref.get("key", "")),
                            "check_kind": str(check.get("kind", "")),
                            "status": str(check.get("status", "")),
                            "finding": str(check.get("finding", "")),
                        }
                    )
        return sorted(
            result,
            key=lambda item: (
                item["fact_id"],
                item["source_key"],
                item["check_kind"],
            ),
        )

    def _source_query_capabilities(
        self,
        release: dict[str, Any],
    ) -> list[dict[str, Any]]:
        capabilities: list[dict[str, Any]] = []
        for candidate in release["candidates"]:
            fact = parse_fact_markdown(candidate["fact_markdown"])
            for ref in fact.external_refs:
                if ref.get("source_evidence_version") != 4:
                    continue
                audit = ref.get("critical_audit")
                if not isinstance(audit, dict):
                    continue
                source_audit = audit.get("source_audit")
                if not isinstance(source_audit, dict):
                    continue
                for search in source_audit.get("issue_searches", []):
                    if (
                        isinstance(search, dict)
                        and search.get("evidence_mode") == "narrow_live_query"
                        and isinstance(search.get("live_query_capability"), dict)
                    ):
                        capabilities.append(
                            {
                                "fact_id": fact.fact_id,
                                "source_key": str(ref.get("key", "")),
                                "search_kind": str(search.get("kind", "")),
                                **search["live_query_capability"],
                            }
                        )
        capabilities.sort(
            key=lambda item: (
                item["fact_id"],
                item["source_key"],
                item["search_kind"],
            )
        )
        return capabilities

    def _certification_decision_template(
        self,
        release: dict[str, Any],
    ) -> dict[str, Any]:
        source_nonpass = self._source_nonpass_checks(release)
        template: dict[str, Any] = {
            "schema_version": 5,
            "release_id": release["release_id"],
            "release_sha256": release["release_sha256"],
            "capsule_sha256": "COPY_EXACT_CAPSULE_SHA256_FROM_CAPSULE_JSON",
            "verdict": "correct",
            "findings": [],
            "check_results": [
                {"check_id": check_id, "status": "pass", "findings": []}
                for check_id in release["verification_plan"]["required_checks"]
            ],
            "candidate_checks": [
                {"fact_id": fact_id, "verdict": "correct", "findings": []}
                for fact_id in release["fact_ids"]
            ],
            "edge_checks": [
                {
                    "predecessor_fact_id": predecessor,
                    "fact_id": fact_id,
                    "verdict": "correct",
                    "findings": [],
                }
                for predecessor, fact_id in release["internal_edges"]
            ],
            "assurance_matrix": self._expected_assurance_matrix(release),
            "reviewer": "REPLACE_WITH_FRESH_VERIFIER_ID",
            "host_attestation": {
                "host": "REPLACE_WITH_HOST_ID",
                "agent_id": "REPLACE_WITH_FRESH_VERIFIER_ID",
                "isolation": "fresh_context",
                "fork_turns": "none",
                "allowed_capsule_sha256": "COPY_EXACT_CAPSULE_SHA256_FROM_CAPSULE_JSON",
            },
        }
        if source_nonpass:
            template["source_check_reconciliation"] = [
                {
                    **{
                        key: item[key]
                        for key in ("fact_id", "source_key", "check_kind", "status")
                    },
                    "disposition": "bound_correction",
                    "rationale": "REPLACE_WITH_EXACT_RECONCILIATION_OR_REJECT",
                }
                for item in source_nonpass
            ]
        if (
            release["requested_assurance"].get("contract_revision")
            == RESEARCH_DRAFT_ASSURANCE_REVISION
        ):
            template["parallel_verification_aggregate_id"] = (
                "COPY_EXACT_ELIGIBLE_AGGREGATE_ID_FROM_PROJECT"
            )
        return template

    def verifier_capsule(self, release_id: str) -> dict[str, Any]:
        release = self.release(release_id)
        self._require_current_paper_continuation_release(release)
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
        semantic: dict[str, Any] = {
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
        if "paper_continuation_ref" in release:
            semantic["paper_continuation_ref"] = release[
                "paper_continuation_ref"
            ]
            if "philosophy_atomicity" in release:
                semantic["philosophy_atomicity"] = release[
                    "philosophy_atomicity"
                ]
            semantic["paper_continuation_evidence"] = release[
                "paper_continuation_evidence"
            ]
            semantic["instructions"]["paper_continuation_boundary"] = (
                "verify exact target-closure adequacy separately from Fact truth; "
                "for philosophy, independently reconstruct the conjunct inventory and "
                "reject any Fact that hides more than one independently falsifiable "
                "component behind its single declared conjunct; compare every ordinary-"
                "language paraphrase with the formal claim and reject undefined or "
                "unnecessary jargon that conceals a premise, burden, or inferential step"
            )
        if (
            release["requested_assurance"].get("contract_revision")
            == RESEARCH_DRAFT_ASSURANCE_REVISION
        ):
            semantic.update(
                {
                    "research_draft_ref": release["research_draft_ref"],
                    "research_draft_evidence": release[
                        "research_draft_evidence"
                    ],
                    "research_draft_admission_preflight": release[
                        "research_draft_admission_preflight"
                    ],
                    "paper_evidence_transport_closure": release[
                        "paper_evidence_transport_closure"
                    ],
                    "validated_dependency_receipt": release[
                        "validated_dependency_receipt"
                    ],
                }
            )
            semantic["instructions"]["research_draft_boundary"] = (
                "reconstruct the complete Paper target closure from the sealed transport; "
                "check node dispositions separately from many-to-many Paper-Fact mappings; "
                "check every source-derived atomic component and qualified failure surface; "
                "preserve the declared stance unless an exact Operator authorization is sealed"
            )
        if "evidence_bridge_refs" in release:
            current_bridge_refs = self._validate_evidence_bridge_refs(
                release["evidence_bridge_refs"],
                artifacts=release["artifacts"],
                sealed_record=True,
                require_current=True,
            )
            semantic["evidence_bridge_refs"] = current_bridge_refs
            semantic["instructions"]["evidence_boundary"] = (
                "bridge capsules are nontruth source inputs; independently verify every "
                "selected claim before recommending Fact admission"
            )
        if (
            release.get("assurance_contract_revision")
            == V5_ASSURANCE_CONTRACT_REVISION
        ):
            source_nonpass = self._source_nonpass_checks(release)
            template = self._certification_decision_template(release)
            successor_predecessor_packets = []
            for contract in release.get("successor_contracts", []):
                predecessor_id = contract["predecessor_fact_id"]
                predecessor_path = self.store.active_fact_path(predecessor_id)
                predecessor_raw = predecessor_path.read_bytes()
                predecessor = self.store.get_fact(predecessor_id)
                successor_predecessor_packets.append(
                    {
                        "fact_id": predecessor_id,
                        "fact_sha256": sha256_bytes(predecessor_raw),
                        "fact_markdown": predecessor_raw.decode("utf-8"),
                        "statement": predecessor.statement,
                        "proof": predecessor.proof,
                    }
                )
            semantic.update(
                {
                    "assurance_contract_revision": V5_ASSURANCE_CONTRACT_REVISION,
                    "applicable_assurance_checks": release.get(
                        "applicable_assurance_checks", []
                    ),
                    "candidate_interfaces": release.get(
                        "candidate_interfaces", []
                    ),
                    "research_assurance_evidence": release.get(
                        "research_assurance_evidence", []
                    ),
                    "successor_contracts": release.get(
                        "successor_contracts", []
                    ),
                    "successor_predecessor_packets": sorted(
                        successor_predecessor_packets,
                        key=lambda item: item["fact_id"],
                    ),
                    "proof_diff_policy": {
                        "display": "statement_and_proof_diffs_separately",
                        "interface_only": "predecessor_proof_bytes_must_match_exactly",
                        "rewritten_proof": (
                            "every_predecessor_proof_unit_mapped_or_explicitly_pruned"
                        ),
                    },
                    "source_nonpass_checks": source_nonpass,
                    "source_query_capabilities": self._source_query_capabilities(
                        release
                    ),
                    "decision_return": {
                        "template": template,
                        "allowed_nested_keys": {
                            "finding": [
                                "id",
                                "severity",
                                "class",
                                "description",
                                "repair_hint",
                            ],
                            "check_result": ["check_id", "status", "findings"],
                            "candidate_check": ["fact_id", "verdict", "findings"],
                            "edge_check": [
                                "predecessor_fact_id",
                                "fact_id",
                                "verdict",
                                "findings",
                            ],
                            "source_check_reconciliation": [
                                "fact_id",
                                "source_key",
                                "check_kind",
                                "status",
                                "disposition",
                                "rationale",
                            ],
                        },
                        "verifier_action": (
                            "write and locally preflight output/review.json only; "
                            "do not record into the project"
                        ),
                        "gateway_action": (
                            "after byte-preserving handoff, the gateway runs "
                            "certification-record and fact-admit"
                        ),
                        "local_validator": "host/validate_decision.py",
                    },
                }
            )
        capsule_sha = sha256_json(semantic)
        return {
            **semantic,
            "capsule_id": "capsule-" + capsule_sha,
            "capsule_sha256": capsule_sha,
        }

    def _validate_finding(self, finding: Any, *, label: str) -> dict[str, str]:
        finding = _require_exact_object_fields(
            finding,
            {"id", "severity", "class", "description", "repair_hint"},
            label=label,
            pointer=f"/{label.replace('[', '/').replace(']', '')}",
        )
        normalized = {
            key: _require_nonempty_text(finding[key], f"{label} {key}")
            for key in ("id", "severity", "class", "description")
        }
        if finding["severity"] not in {"critical_error", "gap"}:
            raise ValueError(f"{label} severity is invalid")
        if finding["class"] not in V5_FINDING_CLASSES:
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
        *,
        preflight_only: bool = False,
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
        release_id = payload.get("release_id")
        if not isinstance(release_id, str):
            raise ValueError(
                "Certification Decision fields are not exact: missing=/release_id"
            )
        release = self.release(release_id)
        strict_research_draft = (
            release["requested_assurance"].get("contract_revision")
            == RESEARCH_DRAFT_ASSURANCE_REVISION
        )
        if strict_research_draft:
            required.add("parallel_verification_aggregate_id")
        source_nonpass = self._source_nonpass_checks(release)
        if source_nonpass:
            required.add("source_check_reconciliation")
        _require_exact_object_fields(
            payload,
            required,
            label="Certification Decision input",
            pointer="",
        )
        if payload.get("schema_version") != 5:
            raise ValueError("Certification Decision schema_version must be 5")
        capsule = self.verifier_capsule(release["release_id"])
        if (
            payload.get("release_sha256") != release["release_sha256"]
            or payload.get("capsule_sha256") != capsule["capsule_sha256"]
        ):
            raise ValueError("Certification Decision release/capsule binding mismatch")
        parallel_aggregate: dict[str, Any] | None = None
        if strict_research_draft:
            aggregate_id = _require_nonempty_text(
                payload.get("parallel_verification_aggregate_id"),
                "parallel verification aggregate id",
            )
            parallel_aggregate = self.parallel_verification().require_eligible_for_release(
                release["release_id"], aggregate_id
            )
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
        if not isinstance(check_results, list):
            raise ValueError("Certification /check_results must be a list")
        normalized_check_results: list[dict[str, Any]] = []
        for index, raw_item in enumerate(check_results):
            item = _require_exact_object_fields(
                raw_item,
                {"check_id", "status", "findings"},
                label="Certification check_result",
                pointer=f"/check_results/{index}",
            )
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
        if not isinstance(candidate_checks, list):
            raise ValueError("Certification /candidate_checks must be a list")
        normalized_candidate_checks: list[dict[str, Any]] = []
        for index, raw_item in enumerate(candidate_checks):
            item = _require_exact_object_fields(
                raw_item,
                {"fact_id", "verdict", "findings"},
                label="Certification candidate_check",
                pointer=f"/candidate_checks/{index}",
            )
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
        if not isinstance(edge_checks, list):
            raise ValueError("Certification /edge_checks must be a list")
        normalized_edge_checks: list[dict[str, Any]] = []
        for index, raw_item in enumerate(edge_checks):
            item = _require_exact_object_fields(
                raw_item,
                {"predecessor_fact_id", "fact_id", "verdict", "findings"},
                label="Certification edge_check",
                pointer=f"/edge_checks/{index}",
            )
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
        normalized_reconciliation: list[dict[str, str]] = []
        if source_nonpass:
            reconciliation = payload.get("source_check_reconciliation")
            if not isinstance(reconciliation, list):
                raise ValueError(
                    "Certification /source_check_reconciliation must be a list"
                )
            expected_nonpass = {
                (
                    item["fact_id"],
                    item["source_key"],
                    item["check_kind"],
                    item["status"],
                )
                for item in source_nonpass
            }
            seen_nonpass: set[tuple[str, str, str, str]] = set()
            for index, raw_item in enumerate(reconciliation):
                item = _require_exact_object_fields(
                    raw_item,
                    {
                        "fact_id",
                        "source_key",
                        "check_kind",
                        "status",
                        "disposition",
                        "rationale",
                    },
                    label="Certification source_check_reconciliation",
                    pointer=f"/source_check_reconciliation/{index}",
                )
                identity = tuple(
                    _require_nonempty_text(
                        item[key],
                        f"source reconciliation {key}",
                    )
                    for key in ("fact_id", "source_key", "check_kind", "status")
                )
                if identity not in expected_nonpass or identity in seen_nonpass:
                    raise ValueError(
                        "Certification source reconciliation is unknown or duplicated: "
                        + ":".join(identity)
                    )
                seen_nonpass.add(identity)
                disposition = item.get("disposition")
                if disposition not in {
                    "bound_correction",
                    "scope_restriction",
                    "reject",
                }:
                    raise ValueError(
                        "Certification source reconciliation disposition is invalid"
                    )
                rationale = _require_nonempty_text(
                    item.get("rationale"),
                    "source reconciliation rationale",
                )
                normalized_reconciliation.append(
                    {
                        "fact_id": identity[0],
                        "source_key": identity[1],
                        "check_kind": identity[2],
                        "status": identity[3],
                        "disposition": disposition,
                        "rationale": rationale,
                    }
                )
            if seen_nonpass != expected_nonpass:
                raise ValueError(
                    "Certification source reconciliation does not exactly cover every non-pass check"
                )
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
        attestation = _require_exact_object_fields(
            attestation,
            {
                "host",
                "agent_id",
                "isolation",
                "fork_turns",
                "allowed_capsule_sha256",
            },
            label="Certification host_attestation",
            pointer="/host_attestation",
        )
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
            and all(
                item["disposition"] != "reject"
                for item in normalized_reconciliation
            )
        )
        if verdict == "correct" and not clean:
            raise ValueError("correct Certification Decision must be completely clean")
        if verdict == "reject" and clean:
            raise ValueError("rejecting Certification Decision requires a failed check")
        # Execute the byte-identical validator transported to the neutral capsule
        # before storage.  Gateway-specific diagnostics above remain stable, while
        # no locally preflighted shape or finding class can diverge at admission.
        validate_decision_against_capsule(payload, capsule)
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
            **(
                {
                    "parallel_verification_aggregate_id": parallel_aggregate[
                        "aggregate"
                    ]["aggregate_id"],
                    "parallel_verification_aggregate_record_sha256": (
                        parallel_aggregate["record_sha256"]
                    ),
                }
                if parallel_aggregate is not None
                else {}
            ),
            **(
                {
                    "source_check_reconciliation": sorted(
                        normalized_reconciliation,
                        key=lambda item: (
                            item["fact_id"],
                            item["source_key"],
                            item["check_kind"],
                        ),
                    )
                }
                if source_nonpass
                else {}
            ),
            "truth_effect": "none",
        }
        decision_sha = sha256_json(semantic)
        decision_id = "decision-" + decision_sha
        if preflight_only:
            return {
                "valid": True,
                "decision_id": decision_id,
                "decision_sha256": decision_sha,
                "release_id": release["release_id"],
                "capsule_sha256": capsule["capsule_sha256"],
                "project_effect": "none",
                "truth_effect": "none",
            }
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
            strict_research_draft = (
                release["requested_assurance"].get("contract_revision")
                == RESEARCH_DRAFT_ASSURANCE_REVISION
            )
            if strict_research_draft:
                aggregate_id = record.get("parallel_verification_aggregate_id")
                if not isinstance(aggregate_id, str):
                    raise ValueError(
                        "research-draft Certification Decision lacks parallel verification"
                    )
                aggregate = self.parallel_verification().require_eligible_for_release(
                    release["release_id"], aggregate_id
                )
                if (
                    record.get("parallel_verification_aggregate_record_sha256")
                    != aggregate["record_sha256"]
                ):
                    raise ValueError(
                        "Certification Decision parallel aggregate binding drifted"
                    )
            elif any(
                key in record
                for key in (
                    "parallel_verification_aggregate_id",
                    "parallel_verification_aggregate_record_sha256",
                )
            ):
                raise ValueError(
                    "non-research-draft Certification Decision has parallel aggregate fields"
                )
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
        *,
        _lineage_facts: dict[str, Fact] | None = None,
        _lineage_paths: dict[str, Path] | None = None,
        _skip_successor_validation: bool = False,
    ) -> tuple[dict[str, Any], dict[str, Path]]:
        directory = self._admission_dir(release_id)
        marker_path = directory / "ACCEPTED.json"
        if marker_path.is_symlink() or not marker_path.is_file():
            raise ValueError("V5 admission marker is missing or unsafe")
        marker = self.store._read_json(marker_path)
        release = self.release(
            release_id,
            _lineage_facts=_lineage_facts,
            _lineage_paths=_lineage_paths,
            _skip_successor_validation=_skip_successor_validation,
        )
        strict_research_draft = (
            release["requested_assurance"].get("contract_revision")
            == RESEARCH_DRAFT_ASSURANCE_REVISION
        )
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
        if strict_research_draft:
            required.update(
                {
                    "parallel_verification_aggregate_id",
                    "parallel_verification_aggregate_record_sha256",
                }
            )
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
        _parse_utc_timestamp(
            marker.get("accepted_at"), label="V5 admission accepted_at"
        )
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
        if strict_research_draft:
            aggregate_id = marker["parallel_verification_aggregate_id"]
            aggregate = self.parallel_verification().require_eligible_for_release(
                release_id, aggregate_id
            )
            if (
                marker["parallel_verification_aggregate_record_sha256"]
                != aggregate["record_sha256"]
                or decision.get("parallel_verification_aggregate_id")
                != aggregate_id
                or decision.get("parallel_verification_aggregate_record_sha256")
                != aggregate["record_sha256"]
            ):
                raise ValueError(
                    "V5 admission parallel-verification binding drifted"
                )
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

    def _lineage_snapshot(
        self,
        *,
        admitted_before: datetime | str | None = None,
        exclude_release_ids: set[str] | None = None,
    ) -> tuple[dict[str, Fact], dict[str, Path]]:
        """Build an immutable active-Fact snapshot without recursive lineage reads.

        Release/admission bytes are validated in a first pass with successor
        replay deferred.  Callers then replay successor contracts against this
        explicit snapshot.  Facts from an excluded release are never eligible
        to serve as their own historical active predecessors.
        """

        cutoff = (
            _parse_utc_timestamp(admitted_before, label="lineage admission cutoff")
            if isinstance(admitted_before, str)
            else admitted_before
        )
        if cutoff is not None:
            if not isinstance(cutoff, datetime) or cutoff.tzinfo is None:
                raise ValueError("lineage admission cutoff must be timezone-aware")
            cutoff = cutoff.astimezone(timezone.utc)
        excluded = exclude_release_ids or set()
        revoked = self.revoked_fact_ids()
        paths: dict[str, Path] = {}
        if not self.admissions_dir.exists():
            return {}, paths
        for directory in sorted(self.admissions_dir.glob("release-*")):
            if directory.is_symlink() or not directory.is_dir():
                raise ValueError("V5 admission store contains an unsafe entry")
            marker_path = directory / "ACCEPTED.json"
            if not marker_path.exists():
                continue
            if directory.name in excluded:
                continue
            marker, admitted_paths = self._validated_admission(
                directory.name,
                _skip_successor_validation=True,
            )
            if cutoff is not None and _parse_utc_timestamp(
                marker["accepted_at"], label="V5 admission accepted_at"
            ) >= cutoff:
                continue
            for fact_id, path in admitted_paths.items():
                if fact_id in revoked:
                    continue
                if fact_id in paths:
                    raise ValueError(
                        f"V5 Fact {fact_id} has multiple active admissions"
                    )
                paths[fact_id] = path
        facts: dict[str, Fact] = {}
        for fact_id, path in paths.items():
            fact = parse_fact_markdown(path.read_text(encoding="utf-8"))
            errors = fact.validate()
            if errors:
                raise ValueError(
                    f"invalid admitted V5 Fact {fact_id}: " + "; ".join(errors)
                )
            if fact.fact_id != fact_id or fact.problem_id != self.store.project_id():
                raise ValueError("admitted V5 Fact id/project binding mismatch")
            facts[fact_id] = fact
        return facts, paths

    def _validate_lineage_snapshot(
        self,
        facts: dict[str, Fact],
        paths: dict[str, Path],
        *,
        exclude_release_ids: set[str] | None = None,
    ) -> None:
        excluded = exclude_release_ids or set()
        if not self.admissions_dir.exists():
            return
        for directory in sorted(self.admissions_dir.glob("release-*")):
            marker_path = directory / "ACCEPTED.json"
            if directory.name in excluded or not marker_path.exists():
                continue
            release = self.release(
                directory.name,
                _skip_successor_validation=True,
            )
            _, own_paths = self._validated_admission(
                directory.name,
                _skip_successor_validation=True,
            )
            own_fact_ids = set(own_paths)
            historical_facts, historical_paths = self._lineage_snapshot(
                admitted_before=release["created_at"],
                exclude_release_ids={directory.name},
            )
            _, admitted_paths = self._validated_admission(
                directory.name,
                _lineage_facts=historical_facts,
                _lineage_paths=historical_paths,
            )
            if set(admitted_paths) != own_fact_ids:
                raise ValueError("V5 admission Fact set drifted between validation phases")

    def active_fact_paths(self) -> dict[str, Path]:
        facts, paths = self._lineage_snapshot()
        self._validate_lineage_snapshot(facts, paths)
        return paths

    def _preflight_post_admission_history(
        self,
        *,
        release: dict[str, Any],
        accepted_at: str,
    ) -> None:
        """Prove that a prospective admission cannot rewrite sealed history.

        Existing releases are replayed against their own seal-time snapshots.  The
        prospective marker is necessarily later than its release and therefore is
        absent from every already-sealed release snapshot.
        """

        accepted = _parse_utc_timestamp(
            accepted_at, label="prospective V5 admission accepted_at"
        )
        release_created = _parse_utc_timestamp(
            release.get("created_at"), label="Candidate Release created_at"
        )
        if accepted <= release_created:
            raise ValueError("V5 admission timestamp must follow Candidate Release sealing")
        for path in sorted(self.candidate_releases_dir.glob("release-*.json")):
            if path.is_symlink() or not path.is_file():
                raise ValueError("V5 Candidate Release store contains an unsafe entry")
            historical = self.release(path.stem)
            historical_created = _parse_utc_timestamp(
                historical.get("created_at"), label="Candidate Release created_at"
            )
            if accepted <= historical_created:
                raise ValueError(
                    "prospective V5 admission does not postdate sealed release history"
                )
        facts, paths = self._lineage_snapshot()
        self._validate_lineage_snapshot(facts, paths)

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
        release = self.release(release_id, _deep_dependencies=True)
        self._require_current_paper_continuation_release(release)
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
        strict_research_draft = (
            release["requested_assurance"].get("contract_revision")
            == RESEARCH_DRAFT_ASSURANCE_REVISION
        )
        parallel_aggregate: dict[str, Any] | None = None
        if strict_research_draft:
            aggregate_id = decision.get("parallel_verification_aggregate_id")
            if not isinstance(aggregate_id, str):
                raise ValueError(
                    "research-draft admission lacks parallel verification aggregate"
                )
            parallel_aggregate = self.parallel_verification().require_eligible_for_release(
                release_id, aggregate_id
            )
            if (
                decision.get("parallel_verification_aggregate_record_sha256")
                != parallel_aggregate["record_sha256"]
            ):
                raise ValueError(
                    "research-draft admission aggregate binding differs from the decision"
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
            authorized_artifact_hashes={
                item["sha256"]
                for item in validation_artifacts
                if item["role"]
                in set(release["verification_plan"]["authorized_artifact_roles"])
            },
            verification_plan=release["verification_plan"],
            assurance_contract_revision=release.get(
                "assurance_contract_revision",
                V5_LEGACY_ASSURANCE_CONTRACT_REVISION,
            ),
            require_geometric_stage_typing=(
                "geometric_stage_typing"
                in release.get("applicable_assurance_checks", [])
            ),
        )
        if (
            order != release["fact_ids"]
            or internal_edges != release["internal_edges"]
            or external_predecessors != release["external_predecessors"]
        ):
            raise ValueError("Candidate Release mathematical graph binding drifted")
        if (
            release["requested_assurance"].get("contract_revision")
            != RESEARCH_DRAFT_ASSURANCE_REVISION
        ):
            self._validate_paper_evidence_refs(
                release["paper_evidence_refs"],
                validation_subject=release["requested_assurance"][
                    "validation_subject"
                ],
            )
        fact_sha = {
            fact_id: sha256_bytes(rendered[fact_id])
            for fact_id in release["fact_ids"]
        }
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
            **(
                {
                    "parallel_verification_aggregate_id": parallel_aggregate[
                        "aggregate"
                    ]["aggregate_id"],
                    "parallel_verification_aggregate_record_sha256": (
                        parallel_aggregate["record_sha256"]
                    ),
                }
                if parallel_aggregate is not None
                else {}
            ),
            "accepted_at": accepted_at,
        }
        marker = {
            **marker_semantic,
            "acceptance_id": "acceptance-" + sha256_json(marker_semantic),
        }
        projection_plan = self._admission_projection_plan(
            marker,
            release=release,
        )
        self._preflight_admission_projections(projection_plan)
        with self.store.v5_mutation_lock(command="fact-admit"):
            if marker_path.exists():
                existing, _ = self._validated_admission(release_id)
                if (
                    existing["decision_id"] != decision_id
                    or existing["gateway"] != gateway
                ):
                    raise ValueError(
                        "Candidate Release was already admitted with different evidence"
                    )
                self._materialize_admission_projections(existing)
                return existing
            self._preflight_post_admission_history(
                release=release,
                accepted_at=accepted_at,
            )
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
            for fact_id in release["fact_ids"]:
                path = facts_dir / f"{fact_id}.md"
                self.store._write_bytes_once(path, rendered[fact_id], mode=0o644)
            # This write is the sole all-or-none visibility switch.
            self.store._write_json_once(marker_path, marker)
            self._materialize_admission_projections(
                marker,
                release=release,
                projection_plan=projection_plan,
            )
        return marker

    def _admission_projection_plan(
        self,
        marker: dict[str, Any],
        *,
        release: dict[str, Any],
    ) -> list[dict[str, Any]]:
        candidate_by_id = {
            item["fact_id"]: item for item in release["candidates"]
        }
        plan: list[dict[str, Any]] = []
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
            fact = parse_fact_markdown(
                candidate_by_id[fact_id]["fact_markdown"]
            )
            interface = build_statement_interface(
                fact=fact,
                stored_fact_sha256=marker["fact_sha256"][fact_id],
                acceptance_event_sha256=event_id,
                admission_review_id=marker["decision_sha256"],
                workflow_evidence_version=5,
                assurance_contract_revision=release.get(
                    "assurance_contract_revision",
                    V5_LEGACY_ASSURANCE_CONTRACT_REVISION,
                ),
            )
            validate_statement_interface(interface)
            plan.append(
                {
                    "event": event,
                    "interface": interface,
                    "interface_path": self.store.interfaces_dir / f"{fact_id}.json",
                }
            )
        return plan

    def _preflight_admission_projections(
        self,
        projection_plan: list[dict[str, Any]],
    ) -> None:
        existing_events = self.store._read_jsonl(self.store.verification_log)
        for item in projection_plan:
            event = item["event"]
            matches = [
                existing
                for existing in existing_events
                if existing.get("event_id") == event["event_id"]
            ]
            if len(matches) > 1:
                raise ValueError(
                    "duplicate admission projection event: " + event["event_id"]
                )
            if matches:
                existing_semantic = {
                    key: value
                    for key, value in matches[0].items()
                    if key != "timestamp"
                }
                expected_semantic = {
                    key: value for key, value in event.items() if key != "timestamp"
                }
                if existing_semantic != expected_semantic:
                    raise ValueError(
                        "divergent admission projection event: " + event["event_id"]
                    )
            interface_path = item["interface_path"]
            if interface_path.is_symlink():
                raise ValueError(
                    f"immutable statement interface is unsafe: {interface_path}"
                )
            rendered = (
                json.dumps(
                    item["interface"],
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            ).encode("utf-8")
            if interface_path.exists() and (
                not interface_path.is_file()
                or interface_path.read_bytes() != rendered
            ):
                raise ValueError(
                    f"immutable statement interface collision at {interface_path}"
                )

    def _materialize_admission_projections(
        self,
        marker: dict[str, Any],
        *,
        release: dict[str, Any] | None = None,
        projection_plan: list[dict[str, Any]] | None = None,
    ) -> None:
        if release is None:
            release = self.release(marker["release_id"])
        if projection_plan is None:
            projection_plan = self._admission_projection_plan(
                marker,
                release=release,
            )
        self._preflight_admission_projections(projection_plan)
        for item in projection_plan:
            event = item["event"]
            self.store._append_jsonl_once(
                self.store.verification_log,
                event,
                event_id=event["event_id"],
            )
            write_interface_once(
                item["interface_path"],
                item["interface"],
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
        paper_continuation = self.paper_continuation().status_all_summary()
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
            "paper_continuation": paper_continuation,
        }

    def fact_evidence_audit(self) -> dict[str, Any]:
        """Audit only the V5 authority bytes required for Fact Evidence.

        External Evidence capture must remain readable across Chalxius runtime
        upgrades.  Frozen rounds, task cards, modes, Blackboard, Paper, and
        other nontruth workflow surfaces are therefore deliberately outside
        this audit.  The active Fact projection and every authority object that
        makes it visible remain fully validated.
        """

        authority_errors: list[str] = []
        graph_errors: list[str] = []
        warnings: list[str] = []
        trust_debt: list[str] = []
        facts: dict[str, Fact] = {}
        active_paths: dict[str, Path] = {}
        admitted_fact_markers: dict[str, dict[str, Any]] = {}

        def authority_error(message: str) -> None:
            authority_errors.append(message)

        def graph_error(message: str) -> None:
            graph_errors.append(message)

        try:
            project = self.store.project()
            project_id = self.store.project_id()
        except Exception as exc:
            authority_error(f"invalid project.json: {exc}")
            project = {}
            project_id = ""
        if project:
            if (
                project.get("workflow_evidence_version")
                != V5_WORKFLOW_EVIDENCE_VERSION
            ):
                authority_error("Fact Evidence audit requires a V5 source project")
            if project.get("policy_revision") != V5_POLICY_REVISION:
                authority_error("V5 source project policy_revision is mismatched")
            if project.get("truth_policy") != "verifier-gated":
                authority_error("V5 source project truth policy is not verifier-gated")

        if self.contract_path.is_symlink() or not self.contract_path.is_file():
            authority_error("V5 lifecycle contract is missing or unsafe")
        else:
            try:
                contract = self.store._read_json(self.contract_path)
                semantic = {key: contract[key] for key in V5_LIFECYCLE_CONTRACT}
                if semantic != V5_LIFECYCLE_CONTRACT:
                    raise ValueError(
                        "semantic contract differs from the release contract"
                    )
                if contract.get("contract_sha256") != sha256_json(semantic):
                    raise ValueError("contract hash mismatch")
            except Exception as exc:
                authority_error(f"invalid V5 lifecycle contract: {exc}")

        for label, directory in (
            ("research entries", self.research_entries_dir),
            ("candidate releases", self.candidate_releases_dir),
            ("candidate artifacts", self.candidate_artifacts_dir),
            ("certification decisions", self.certification_decisions_dir),
            ("Fact admissions", self.admissions_dir),
            ("Fact revocations", self.revocations_dir),
        ):
            if directory.is_symlink() or not directory.is_dir():
                authority_error(f"V5 {label} directory is missing or unsafe")

        try:
            active_paths = self.active_fact_paths()
        except Exception as exc:
            authority_error(f"active V5 Fact lineage failed: {exc}")

        for directory in sorted(self.admissions_dir.glob("release-*")):
            if directory.is_symlink() or not directory.is_dir():
                authority_error("V5 admission store contains an unsafe entry")
                continue
            marker_path = directory / "ACCEPTED.json"
            if not marker_path.exists():
                warnings.append(
                    f"V5 admission staging {directory.name} has no visibility marker"
                )
                continue
            try:
                marker, paths = self._validated_admission(directory.name)
                for fact_id in paths:
                    if fact_id in admitted_fact_markers:
                        raise ValueError(
                            f"Fact {fact_id} has more than one admission marker"
                        )
                    admitted_fact_markers[fact_id] = marker
            except Exception as exc:
                authority_error(f"V5 admission {directory.name}: {exc}")

        try:
            revoked_ids = self.revoked_fact_ids()
        except Exception as exc:
            authority_error(f"invalid V5 revocation store: {exc}")
            revoked_ids = set()
        unknown_revocations = sorted(
            revoked_ids.difference(admitted_fact_markers)
        )
        if unknown_revocations:
            authority_error(
                "V5 revocations have no admitted Fact: "
                + ", ".join(unknown_revocations)
            )
        visible_expected = set(admitted_fact_markers).difference(revoked_ids)
        if set(active_paths) != visible_expected:
            authority_error(
                "active V5 Fact visibility differs from admission/revocation provenance"
            )

        for fact_id, path in sorted(active_paths.items()):
            try:
                fact = parse_fact_markdown(path.read_text(encoding="utf-8"))
                validation_errors = fact.validate()
                if validation_errors:
                    raise ValueError("; ".join(validation_errors))
                if fact.fact_id != fact_id or fact.problem_id != project_id:
                    raise ValueError("Fact id/project binding mismatch")
                facts[fact_id] = fact
            except Exception as exc:
                graph_error(f"invalid active V5 Fact {fact_id}: {exc}")

        if not facts:
            authority_error("external Fact Evidence requires at least one active Fact")
        graph = DependencyGraph(facts)
        for fact_id, predecessor in graph.missing_predecessors():
            graph_error(f"{fact_id}: missing active V5 predecessor {predecessor}")
        try:
            graph.topological_order()
            depths = graph.depths()
            max_depth = max(depths.values(), default=0)
        except ValueError as exc:
            graph_error(str(exc))
            max_depth = 0

        try:
            verification_events = self.store._read_jsonl(
                self.store.verification_log
            )
        except Exception as exc:
            authority_error(f"invalid V5 verification log: {exc}")
            verification_events = []
        events_by_fact: dict[str, list[dict[str, Any]]] = {}
        for event in verification_events:
            if event.get("evidence_version") != V5_WORKFLOW_EVIDENCE_VERSION:
                authority_error(
                    "V5 verification log contains non-V5 admission authority"
                )
                continue
            fact_id = str(event.get("fact_id", ""))
            events_by_fact.setdefault(fact_id, []).append(event)
        for fact_id, marker in admitted_fact_markers.items():
            events = events_by_fact.get(fact_id, [])
            if len(events) != 1:
                authority_error(
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
                    authority_error(
                        f"V5 Fact {fact_id} acceptance event {key} mismatch"
                    )
                    break
        unknown_event_facts = sorted(
            set(events_by_fact).difference(admitted_fact_markers)
        )
        if unknown_event_facts:
            authority_error(
                "V5 acceptance events have no admission marker: "
                + ", ".join(unknown_event_facts)
            )

        for fact_id in sorted(facts):
            try:
                self.store.statement_interface(fact_id, materialize=False)
            except Exception as exc:
                authority_error(f"V5 statement interface {fact_id}: {exc}")

        errors = [
            *graph_errors,
            *(f"authority: {message}" for message in authority_errors),
        ]
        return {
            "schema_version": 1,
            "contract_revision": V5_FACT_EVIDENCE_AUDIT_REVISION,
            "scope": "active_v5_fact_authority_only",
            "source_runtime_policy": "independent_of_frozen_nontruth_workflow_runtime",
            "workflow_evidence_version": V5_WORKFLOW_EVIDENCE_VERSION,
            "fact_admission_contract_sha256": FACT_ADMISSION_CONTRACT_SHA256,
            "current_ok": not errors,
            "history_clean": not trust_debt,
            "facts": len(facts),
            "edges": sum(len(fact.predecessors) for fact in facts.values()),
            "max_depth": max_depth,
            "active_fact_ids": sorted(facts),
            "graph_errors": graph_errors,
            "authority_errors": authority_errors,
            "errors": errors,
            "warnings": warnings,
            "trust_debt": trust_debt,
            "ignored_nontruth_surfaces": [
                "rounds_and_task_cards",
                "reasoning_modes",
                "blackboard",
                "paper_logic_and_audit",
                "campaigns",
                "pulses",
                "experiments",
            ],
            "truth_effect": "none",
            "project_effect": "none",
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
            continuation_report = self.paper_continuation().audit()
        except Exception as exc:
            workflow_error(f"Paper continuation audit failed: {exc}")
        else:
            for message in continuation_report["errors"]:
                workflow_error(f"paper_continuation: {message}")
            continuation_counts = continuation_report["counts"]
            report.paper_continuation_plans = continuation_counts["plans"]
            report.paper_continuation_complete_plans = continuation_counts[
                "complete_plans"
            ]
            report.paper_continuation_targets = continuation_counts["targets"]
            report.paper_continuation_researched = continuation_counts[
                "researched"
            ]
            report.paper_continuation_dispositioned = continuation_counts[
                "dispositioned"
            ]
            report.paper_continuation_unresolved = continuation_counts[
                "unresolved"
            ]
            report.paper_continuation_successor_mapped = continuation_counts[
                "successor_mapped"
            ]
            report.paper_continuation_revised_manuscript_covered = (
                continuation_counts["revised_manuscript_covered"]
            )
            report.paper_continuation_adequacy_complete = (
                continuation_report["adequacy_complete"]
            )

        try:
            research_draft_report = self.research_draft().audit()
        except Exception as exc:
            workflow_error(f"research-draft lifecycle audit failed: {exc}")
        else:
            for message in research_draft_report["errors"]:
                workflow_error(f"research_draft: {message}")

        try:
            parallel_verification_report = self.parallel_verification().audit()
        except Exception as exc:
            workflow_error(f"parallel-verification lifecycle audit failed: {exc}")
        else:
            for message in parallel_verification_report["errors"]:
                workflow_error(f"parallel_verification: {message}")

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

        try:
            abort_records = self.store.reasoning_modes().work_unit_aborts()
        except Exception as exc:
            workflow_error(f"work-unit abort projection audit failed: {exc}")
        else:
            for abort in abort_records:
                round_id = abort["round_id"]
                try:
                    status = self.round_status(round_id)
                except Exception as exc:
                    workflow_error(
                        f"work-unit abort/status projection failed for {round_id}: {exc}"
                    )
                    continue
                if (
                    status.get("work_unit_state") != "aborted"
                    or status.get("abort_id") != abort["abort_id"]
                    or status.get("awaiting_count") != 0
                    or any(
                        assignment.get("state")
                        in {"awaiting_return", "return_present"}
                        for assignment in status.get("assignments", [])
                    )
                ):
                    workflow_error(
                        "work-unit abort/status projection mismatch for "
                        f"{round_id}"
                    )

        return report


def v5_contract_file_sha256(path: Path) -> str:
    """Expose a small test/diagnostic helper without granting write authority."""

    return sha256_bytes(path.read_bytes())

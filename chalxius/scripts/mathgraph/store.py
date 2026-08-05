from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator
from zipfile import ZipFile

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback keeps cooperative semantics.
    fcntl = None  # type: ignore[assignment]


_LEGACY_APPEND_ONLY_PATHS = {
    "fact_graph/fact_metadata.jsonl",
    "fact_graph/revocation_log.jsonl",
    "fact_graph/verification_log.jsonl",
    "memory/global.jsonl",
    "novelty/ledger.jsonl",
}
_LEGACY_MUTABLE_PROJECTION_PATHS = {
    "TARGETS.txt",
    "reports/target-closure-certificate.json",
}
_V4_RESERVED_ADDITIVE_PATHS = {
    "blackboard",
    "campaigns",
    "claims",
    "conventions",
    "experiments",
    "evidence",
    "fact_graph/bundles",
    "fact_graph/interfaces",
    "governance/unified-mode",
    "migrations",
    "paper_logic",
    "verification_queue/bundles",
}
_STABLE_COPY_INHERITANCE_KIND = "stable-project-copy-to-chalk-v4"
_STABLE_COPY_ASSURANCE_POLICY = (
    "preserve-recorded-legacy-assurance;never-relabel-as-v4"
)
_STABLE_COPY_STATE_BOUNDARY = (
    "stable-source-read-only;chalk-copy-v4-only"
)
_APPEND_ANCHOR_WRITER_ENGINE = "operate-mathgraph-unified"
_LEGACY_APPEND_ANCHOR_WRITER_ENGINES = {
    "mathgraph-chalk-version",
}
_ACCEPTED_APPEND_ANCHOR_WRITER_ENGINES = {
    _APPEND_ANCHOR_WRITER_ENGINE,
    *_LEGACY_APPEND_ANCHOR_WRITER_ENGINES,
}
HOST_ADAPTER_CONFIG_FILENAME = "host_adapter.json"
_HOST_ADAPTER_CONFIG_FIELDS = {
    "schema_version",
    "policy_revision",
    "project_id",
    "adapter_mode",
    "trusted_host_issuers",
}
_PROJECT_THREAD_LOCKS: dict[str, threading.RLock] = {}
_PROJECT_THREAD_LOCKS_GUARD = threading.Lock()
_INHERITED_CHALK_FIXTURE_AUTHORITY = object()
_LEGACY_WORKFLOW_FIXTURE_AUTHORITY = object()


class _MutationGuardedChild:
    """Route every exposed child-store writer through the project guard."""

    def __init__(
        self,
        target: Any,
        mutation_guard: Callable[[], Any],
        mutating_methods: frozenset[str],
        read_only_calls: dict[str, Callable[..., bool]] | None = None,
    ) -> None:
        self._target = target
        self._mutation_guard = mutation_guard
        self._mutating_methods = mutating_methods
        self._read_only_calls = read_only_calls or {}

    def __getattr__(self, name: str) -> Any:
        attribute = getattr(self._target, name)
        if name not in self._mutating_methods or not callable(attribute):
            return attribute

        def guarded(*args: Any, **kwargs: Any) -> Any:
            read_only = self._read_only_calls.get(name)
            if read_only is not None and read_only(*args, **kwargs):
                return attribute(*args, **kwargs)
            with self._mutation_guard():
                return attribute(*args, **kwargs)

        return guarded


_BLACKBOARD_MUTATORS = frozenset(
    {
        "initialize",
        "ensure_paper_projection_types",
        "register_type",
        "add_objects",
        "add_paper_projection",
        "create_space",
        "add_node_with_placements",
        "snapshot",
        "merge_delta",
        "reindex",
    }
)
_CLAIM_MUTATORS = frozenset(
    {"initialize", "add_convention", "add_claim", "create_variant"}
)
_CAMPAIGN_MUTATORS = frozenset(
    {
        "initialize",
        "create",
        "activate",
        "target_add",
        "target_archive",
        "update",
        "promote_blackboard_node",
    }
)
_PAPER_LOGIC_MUTATORS = frozenset(
    {
        "initialize",
        "stage",
        "record_review",
        "freeze",
        "link_exploration",
        "project_to_blackboard",
    }
)
_VERIFICATION_BUNDLE_MUTATORS = frozenset({"initialize", "create"})
_FACT_BUNDLE_MUTATORS = frozenset(
    {"submit", "verifier_task", "record_review", "admit"}
)
_EXPERIMENT_MUTATORS = frozenset(
    {"observe", "decision", "start", "event", "resume", "finalize"}
)
_PULSE_MUTATORS = frozenset(
    {
        "make_wave1_commitment",
        "make_review_commitment",
        "create_plan",
        "abort",
        "record_core_ingest_failure",
        "void_optional",
        "record_host_dispatch",
        "derive_barrier",
        "derive_closure",
    }
)
_PROFILE_CLOSURE_MUTATORS = frozenset({"record"})


def _blackboard_reindex_is_read_only(*args: Any, **kwargs: Any) -> bool:
    """Only the explicit dry-run form of the dual reindex API is read-only."""

    return not args and kwargs.get("apply") is False


def _project_thread_lock(root: Path) -> threading.RLock:
    key = str(root)
    with _PROJECT_THREAD_LOCKS_GUARD:
        lock = _PROJECT_THREAD_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _PROJECT_THREAD_LOCKS[key] = lock
        return lock

from .applicability import (
    SOURCE_EVIDENCE_VERSION,
    validate_external_refs_for_submission,
)
from .contracts import (
    ACTIVE_MEMORY_STATUSES,
    ASSIGNMENT_ID_RE,
    CLAIM_RELATIONS,
    FACT_ID_RE,
    MEMORY_ID_RE,
    MEMORY_KINDS,
    MEMORY_STATUSES,
    NOVELTY_STATUSES,
    REVIEW_ID_RE,
    ROUND_ID_RE,
    SHA256_RE,
    SUBMISSION_STATUSES,
    contained_path,
    require_exact_keys,
    require_string,
    require_string_list,
    sha256_bytes,
    sha256_json,
    validate_fact_id,
    validate_assignment_id,
    validate_campaign_id,
    validate_claim_id,
    validate_memory_id,
    validate_review_id,
    validate_round_id,
)
from .graph import DependencyGraph
from .elementary import validate_elementary_uses_for_submission
from .markdown import parse_fact_markdown, statement_snippet, validate_fact_round_trip
from .model import AuditReport, Fact
from .search import bm25
from .worker_returns import validate_worker_return
from .blackboard import BlackboardStore
from .collaboration import PulseStore
from .campaigns import (
    COMPACT_SCORE_MODEL,
    COMPACT_SCORE_ROLE,
    LEGACY_V4_SCORE_FIELDS,
    CampaignStore,
    actionable_score,
    collapse_actionable_frontier,
    decision_factors,
    project_legacy_decision_profile,
    validate_decision_profile,
)
from .adoption import validate_workload_profile
from .claims import ClaimRegistry
from .computations import ExperimentManager, validate_computational_evidence
from .fact_bundles import (
    FactBundleStore,
    build_claim_card,
    build_interpret_card,
    validate_expert_lint_receipt,
    validate_interpret_lint_receipt,
    validate_terminology,
)
from .interfaces import (
    build_statement_interface,
    extract_statement_clauses,
    validate_quantifier_ledger,
    validate_statement_interface,
    validate_predecessor_uses,
    write_interface_once,
)
from .verification_bundles import (
    VerificationBundleStore,
    admission_gate_v4,
    validate_review_v4,
)
from .contracts import POLICY_REVISION_V4
from .protocol import validate_ingestion_receipt_v4, validate_task_card
from .paper_logic import PaperLogicStore
from .evidence import EvidencePlane
from .profile_closure import ProfileClosureManager
from .modes import ReasoningModeManager
from .v5_lifecycle import (
    V5_LEGACY_TRUTH_WRITER_COMMANDS,
    V5_POLICY_REVISION,
    V5_WORKFLOW_EVIDENCE_VERSION,
    V5AuditReport,
    V5LifecycleManager,
)
from .adverse_routing import AdverseRoutingManager
from .v5_collaboration import V5PulseStore
from .v5_experiments import V5ExperimentManager


def utc_now() -> str:
    # Round-scoped evidence freshness is security-sensitive: events recorded
    # immediately before a round must not compare equal to that round merely
    # because both timestamps were truncated to the same second.
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _json_hash(payload: Any, length: int = 16) -> str:
    return sha256_json(payload)[:length]


_SUBMISSION_DIGEST_FIELDS_V2 = (
    "fact_id",
    "problem_id",
    "author",
    "predecessors",
    "glossary_introduces",
    "external_refs",
    "statement",
    "proof",
    "intuition",
    "worker",
    "task_id",
    "round_id",
    "assignment_id",
)
_SUBMISSION_DIGEST_FIELDS_V3 = (
    *_SUBMISSION_DIGEST_FIELDS_V2,
    "claim_relation",
    "assigned_claim",
)
_SUBMISSION_DIGEST_FIELDS_V3_ELEMENTARY = (
    *_SUBMISSION_DIGEST_FIELDS_V3,
    "elementary_uses",
)
_SUBMISSION_DIGEST_FIELDS_V4 = (
    *_SUBMISSION_DIGEST_FIELDS_V3_ELEMENTARY,
    "predecessor_uses",
    "quantifier_ledger",
    "convention_profile_ids",
    "computational_evidence",
    "terminology",
    "policy_revision",
    "task_card_sha256",
    "blackboard_snapshot_sha256",
    "verification_plan",
    "artifacts",
)

_REVIEW_INPUT_FIELDS = {
    "fact_id",
    "submission_sha256",
    "packet_sha256",
    "verdict",
    "critical_errors",
    "gaps",
    "repair_hints",
    "reviewer",
}

_STATUS_RELATIONS = {
    "resolved_by_fact": {"proves", "strengthens"},
    "refuted_by_fact": {"refutes"},
    "replaced_by_fact": {"replaces"},
}


def _submission_digest(payload: dict[str, Any]) -> str:
    if payload.get("evidence_version") == 4:
        fields = _SUBMISSION_DIGEST_FIELDS_V4
    elif payload.get("evidence_version") == 3:
        fields = (
            _SUBMISSION_DIGEST_FIELDS_V3_ELEMENTARY
            if "elementary_uses" in payload
            else _SUBMISSION_DIGEST_FIELDS_V3
        )
    else:
        fields = _SUBMISSION_DIGEST_FIELDS_V2
    return sha256_json({key: payload.get(key, "") for key in fields})


def _acceptance_evidence_kind(event: dict[str, Any]) -> str:
    """Classify admission evidence without turning malformed versions into legacy.

    The pre-hash workflow either omitted ``evidence_version`` or explicitly
    used integer version 1.  Any other explicit value is not historical
    evidence and must not acquire provenance merely because it is unknown to
    the current verifier.
    """

    if "evidence_version" not in event:
        return "legacy"
    evidence_version = event["evidence_version"]
    if type(evidence_version) is int:  # Reject bool, which is an int subclass.
        if evidence_version in {2, 3, 4}:
            return "hash-bound"
        if evidence_version == 1:
            return "legacy"
    return "invalid"


def _review_semantic_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: payload[key] for key in sorted(_REVIEW_INPUT_FIELDS)}


class MathGraphStore:
    """Filesystem-backed truth graph, exploration memory, and verification evidence."""

    def __init__(
        self,
        root: Path | str,
        *,
        host_config_path: Path | str | None = None,
        _fixture_authority: object | None = None,
        _legacy_workflow_authority: object | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        self._inherited_chalk_fixture = (
            _fixture_authority is _INHERITED_CHALK_FIXTURE_AUTHORITY
        )
        self._legacy_workflow_fixture = (
            _legacy_workflow_authority
            is _LEGACY_WORKFLOW_FIXTURE_AUTHORITY
        )
        self._uninitialized_v4_mutation_depth = 0
        self._v5_mutation_depth = 0
        self._fact_bundle_admission_authority = object()
        self._verification_bundle_creation_authority = object()
        if host_config_path is None:
            self.host_config_path: Path | None = None
        else:
            supplied_host_config = Path(host_config_path).expanduser()
            if not supplied_host_config.is_absolute():
                supplied_host_config = (
                    Path.cwd() / supplied_host_config
                )
            self.host_config_path = supplied_host_config.absolute()
        self.fact_graph_dir = self.root / "fact_graph"
        self.facts_dir = self.fact_graph_dir / "facts"
        self.revoked_dir = self.fact_graph_dir / "_revoked"
        self.revocation_log = self.fact_graph_dir / "revocation_log.jsonl"
        self.verification_log = self.fact_graph_dir / "verification_log.jsonl"
        self.metadata_log = self.fact_graph_dir / "fact_metadata.jsonl"
        self.interfaces_dir = self.fact_graph_dir / "interfaces"
        self.submissions_dir = self.root / "submissions"
        self.reviews_dir = self.root / "reviews"
        self.reviews_by_id_dir = self.reviews_dir / "by-id"
        self.review_inbox_dir = self.root / "review_inbox"
        self.verification_queue_dir = self.root / "verification_queue"
        self.packet_by_hash_dir = self.verification_queue_dir / "by-hash"
        self.packet_by_fact_dir = self.verification_queue_dir / "by-fact"
        self.memory_dir = self.root / "memory"
        self.memory_log = self.memory_dir / "global.jsonl"
        self.novelty_dir = self.root / "novelty"
        self.novelty_log = self.novelty_dir / "ledger.jsonl"
        self.imports_dir = self.root / "imports"
        self.rounds_dir = self.root / "rounds"
        self.reports_dir = self.root / "reports"
        self.targets_path = self.root / "TARGETS.txt"
        self.project_path = self.root / "project.json"
        self.lock_path = self.root / ".mathgraph.lock"
        self.migrations_dir = self.root / "migrations"
        self.append_anchors_dir = self.migrations_dir / "append-anchors"
        self._thread_lock = _project_thread_lock(self.root)
        self._lock_depth = 0
        self._lock_handle: Any = None
        self._snapshot_lock_depth = 0
        self._snapshot_lock_handle: Any = None

    @classmethod
    def _for_inherited_chalk_fixture(
        cls,
        root: Path | str,
        *,
        host_config_path: Path | str | None = None,
    ) -> "MathGraphStore":
        """Create the explicit test-only seam for pre-unified Chalk V4 bytes."""

        return cls(
            root,
            host_config_path=host_config_path,
            _fixture_authority=_INHERITED_CHALK_FIXTURE_AUTHORITY,
        )

    @classmethod
    def _for_legacy_workflow_fixture(
        cls,
        root: Path | str,
        *,
        host_config_path: Path | str | None = None,
    ) -> "MathGraphStore":
        """Create the private V1-V3 fixture/copy-migration writer seam."""

        return cls(
            root,
            host_config_path=host_config_path,
            _legacy_workflow_authority=(
                _LEGACY_WORKFLOW_FIXTURE_AUTHORITY
            ),
        )

    def _allows_inherited_chalk_fixture_writes(self) -> bool:
        return self._inherited_chalk_fixture

    def _guard_child(
        self,
        target: Any,
        mutating_methods: frozenset[str],
        *,
        read_only_calls: dict[str, Callable[..., bool]] | None = None,
    ) -> Any:
        return _MutationGuardedChild(
            target,
            self.mutation_lock,
            mutating_methods,
            read_only_calls,
        )

    def _assert_mutation_allowed(self) -> None:
        if not self.project_path.exists():
            return
        workflow_version = self.workflow_evidence_version()
        if workflow_version == V5_WORKFLOW_EVIDENCE_VERSION:
            if self._v5_mutation_depth > 0:
                return
            raise ValueError(
                "V5 writes require an explicit lifecycle or capability adapter; "
                "legacy V4 writers are read-only on a V5 project"
            )
        if workflow_version < 4:
            if not self._legacy_workflow_fixture:
                raise ValueError(
                    "legacy workflow V1-V3 is read-only in the unified engine; "
                    "use upgrade-project-copy before any mutation"
                )
            return
        if (
            self._inherited_chalk_fixture
            or self._uninitialized_v4_mutation_depth > 0
        ):
            return
        try:
            status = self.reasoning_modes().status()
        except Exception as exc:
            raise ValueError(
                "legacy Chalk V4 project has invalid or partial unified-mode "
                "governance and is read-only"
            ) from exc
        if not status.get("initialized"):
            raise ValueError(
                "legacy Chalk V4 project is read-only in the unified engine; "
                "run mode-init explicitly before any new write"
            )

    @contextmanager
    def _uninitialized_v4_transition_lock(self) -> Iterator[None]:
        """Narrow internal authority for initialization or isolated migration."""

        self._uninitialized_v4_mutation_depth += 1
        try:
            with self.mutation_lock():
                yield
        finally:
            self._uninitialized_v4_mutation_depth -= 1

    @contextmanager
    def _uninitialized_v5_transition_lock(self) -> Iterator[None]:
        """Narrow authority for creating a new empty V5 authority root."""

        self._v5_mutation_depth += 1
        try:
            with self.mutation_lock():
                yield
        finally:
            self._v5_mutation_depth -= 1

    @contextmanager
    def v5_mutation_lock(self, *, command: str) -> Iterator[None]:
        """Authorize one named V5 adapter while blocking legacy truth writers."""

        self.require_initialized()
        if self.workflow_evidence_version() != V5_WORKFLOW_EVIDENCE_VERSION:
            raise ValueError("V5 mutation authority requires a V5 project")
        if command in V5_LEGACY_TRUTH_WRITER_COMMANDS:
            raise ValueError(
                f"{command} is a legacy V4 truth/migration writer and cannot "
                "mutate V5; use the corresponding V5 lifecycle command"
            )
        self._v5_mutation_depth += 1
        try:
            with self.mutation_lock():
                yield
        finally:
            self._v5_mutation_depth -= 1

    @contextmanager
    def mutation_lock(self) -> Iterator[None]:
        with self._thread_lock:
            self._assert_mutation_allowed()
            if self._snapshot_lock_depth:
                raise ValueError(
                    "project mutation cannot begin inside a snapshot read"
                )
            if self._lock_depth:
                self._lock_depth += 1
                try:
                    yield
                finally:
                    self._lock_depth -= 1
                return
            self.root.mkdir(parents=True, exist_ok=True)
            handle = self.lock_path.open("a+b")
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            self._lock_handle = handle
            self._lock_depth = 1
            try:
                yield
            finally:
                self._lock_depth = 0
                self._lock_handle = None
                if fcntl is not None:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                handle.close()

    @contextmanager
    def snapshot_lock(self) -> Iterator[None]:
        """Hold one low-cost project snapshot against normal Chalxius writers.

        The shared flock coordinates with mutation_lock's exclusive flock.  An
        audit already nested under a normal mutation keeps the stronger lock;
        nested snapshot reads share one handle and never touch project data.
        """

        with self._thread_lock:
            if self._lock_depth:
                yield
                return
            if self._snapshot_lock_depth:
                self._snapshot_lock_depth += 1
                try:
                    yield
                finally:
                    self._snapshot_lock_depth -= 1
                return
            if self.lock_path.is_symlink() or not self.lock_path.is_file():
                raise ValueError("project snapshot lock is missing or unsafe")
            handle = self.lock_path.open("r+b")
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
            self._snapshot_lock_handle = handle
            self._snapshot_lock_depth = 1
            try:
                yield
            finally:
                self._snapshot_lock_depth = 0
                self._snapshot_lock_handle = None
                if fcntl is not None:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                handle.close()

    @contextmanager
    def read_lock(self) -> Iterator[None]:
        """Serialize an in-process read without touching project bytes."""

        with self._thread_lock:
            yield

    def initialize(
        self,
        *,
        project_id: str,
        title: str,
        description: str = "",
        workflow_evidence_version: int = 3,
        reasoning_mode: str | None = "auto",
    ) -> None:
        if not isinstance(project_id, str) or not project_id.strip():
            raise ValueError("project_id must be a nonempty string")
        if "\n" in project_id or "\r" in project_id:
            raise ValueError("project_id must be one line")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("title must be a nonempty string")
        if not isinstance(description, str):
            raise ValueError("description must be a string")
        if workflow_evidence_version not in {3, 4, 5}:
            raise ValueError("workflow_evidence_version must be 3, 4, or 5")
        if (
            workflow_evidence_version < 4
            and not self._legacy_workflow_fixture
        ):
            raise ValueError(
                "the unified engine creates V4 projects only; legacy V3 writer "
                "tests or rollback tooling must opt in explicitly"
            )
        if (
            workflow_evidence_version == 4
            and reasoning_mode is None
            and not self._inherited_chalk_fixture
        ):
            raise ValueError(
                "reasoning_mode=None is reserved for the internal inherited-Chalk "
                "fixture seam; public V4 projects require an initialized mode"
            )
        project_preexists = self.project_path.exists()
        if (
            project_preexists
            and workflow_evidence_version == 4
            and not self._inherited_chalk_fixture
            and not self.reasoning_modes().is_initialized()
        ):
            raise ValueError(
                "legacy Chalk V4 project is read-only in the unified engine; "
                "run mode-init explicitly instead of init"
            )
        lock = (
            self._uninitialized_v4_transition_lock()
            if workflow_evidence_version == 4 and not project_preexists
            else (
                self._uninitialized_v5_transition_lock()
                if workflow_evidence_version == 5 and not project_preexists
                else self.mutation_lock()
            )
        )
        with lock:
            for path in (
                self.facts_dir,
                self.revoked_dir,
                self.submissions_dir,
                self.reviews_by_id_dir,
                self.review_inbox_dir,
                self.packet_by_hash_dir,
                self.packet_by_fact_dir,
                self.memory_dir,
                self.novelty_dir,
                self.imports_dir,
                self.rounds_dir,
                self.reports_dir,
                self.interfaces_dir,
                self.migrations_dir,
            ):
                path.mkdir(parents=True, exist_ok=True)
            if self.project_path.exists():
                existing = self._read_json(self.project_path)
                if existing.get("project_id") != project_id:
                    raise ValueError(
                        "initialized project_id mismatch: "
                        f"stored={existing.get('project_id')!r} requested={project_id!r}"
                    )
            else:
                project_payload = {
                    "schema_version": 2,
                    "workflow_evidence_version": workflow_evidence_version,
                    "project_id": project_id,
                    "title": title,
                    "description": description,
                    "created_at": utc_now(),
                    "truth_policy": "verifier-gated",
                    "glossary_policy": "fact-scoped",
                    "workflow_policy": "packet-and-review-hash-bound",
                }
                if workflow_evidence_version == 4:
                    project_payload["policy_revision"] = POLICY_REVISION_V4
                elif workflow_evidence_version == 5:
                    project_payload["schema_version"] = 3
                    project_payload["policy_revision"] = V5_POLICY_REVISION
                    project_payload["workflow_policy"] = (
                        "research-release-decision-admission"
                    )
                self._write_json_atomic(
                    self.project_path,
                    project_payload,
                )
            if not self.targets_path.exists():
                self._write_text_atomic(self.targets_path, "")
            certificate = self.reports_dir / "target-closure-certificate.json"
            if not certificate.exists():
                self._write_target_certificate(self.targets())
            if workflow_evidence_version == 4:
                self._initialize_v4_state(actor="operator")
                if reasoning_mode is not None:
                    self.reasoning_modes().initialize(
                        reasoning_mode=reasoning_mode,
                        actor="operator",
                        reason="initialize Chalxius project",
                        source_kind="new_unified_project",
                    )
            elif workflow_evidence_version == 5:
                self.v5_lifecycle().initialize()
                # Preserve the mature optional stores without activating a
                # campaign or adding campaign closure to the V5 truth path.
                self._initialize_v4_state(
                    actor="operator",
                    create_default_campaign=False,
                )
                if reasoning_mode is not None:
                    self.reasoning_modes().initialize(
                        reasoning_mode=reasoning_mode,
                        actor="operator",
                        reason="initialize Chalxius V5 project",
                        source_kind="new_v5_project",
                    )

    def require_initialized(self) -> None:
        if not self.project_path.exists():
            raise RuntimeError(f"not an initialized math graph: {self.root}")

    def workflow_evidence_version(self) -> int:
        value = self.project().get("workflow_evidence_version", 1)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("project workflow_evidence_version must be an integer")
        return value

    def v5_lifecycle(self) -> V5LifecycleManager:
        return V5LifecycleManager(self)

    def brave_future(self) -> Any:
        """Return the optional V5 advisory sidecar without materializing it.

        The manager owns its V5 mutation locking.  Merely asking for the
        accessor is read-only, which preserves byte-for-byte absent behavior
        for projects that never opt in.
        """

        if self.workflow_evidence_version() != V5_WORKFLOW_EVIDENCE_VERSION:
            raise ValueError("Brave Future is available only for V5 projects")
        from .brave_future import BraveFutureManager

        return BraveFutureManager(self)

    def adverse_routes(self) -> AdverseRoutingManager:
        return AdverseRoutingManager(self)

    def blackboard(self) -> BlackboardStore:
        return self._guard_child(
            BlackboardStore(self.root),
            _BLACKBOARD_MUTATORS,
            read_only_calls={
                "reindex": _blackboard_reindex_is_read_only,
            },
        )

    def paper_logic(
        self,
        *,
        _inspection_cache: dict[tuple[Any, ...], Any] | None = None,
    ) -> PaperLogicStore:
        return self._guard_child(
            PaperLogicStore(
                self.root,
                owner=self,
                _inspection_cache=_inspection_cache,
            ),
            _PAPER_LOGIC_MUTATORS,
        )

    def evidence(self) -> EvidencePlane:
        return EvidencePlane(self)

    def profile_closures(self) -> ProfileClosureManager:
        return self._guard_child(
            ProfileClosureManager(self),
            _PROFILE_CLOSURE_MUTATORS,
        )

    def reasoning_modes(self) -> ReasoningModeManager:
        return ReasoningModeManager(self)

    def trusted_host_issuers(self) -> tuple[str, ...]:
        """Load explicit cooperative host-adapter trust configuration.

        The default is fail-closed: an absent project-local configuration
        yields no trusted issuer.  Supplying ``host_config_path`` makes that
        file mandatory and permits a host-owned configuration outside the
        project tree.
        """

        config_path = (
            self.host_config_path
            if self.host_config_path is not None
            else self.root / HOST_ADAPTER_CONFIG_FILENAME
        )
        if not config_path.exists():
            if self.host_config_path is not None:
                raise ValueError(
                    "explicit host-adapter configuration is missing"
                )
            return ()
        if config_path.is_symlink() or not config_path.is_file():
            raise ValueError(
                "host-adapter configuration is missing or unsafe"
            )
        payload = self._read_json(config_path)
        require_exact_keys(
            payload,
            required=_HOST_ADAPTER_CONFIG_FIELDS,
            label="host-adapter configuration",
        )
        if (
            payload.get("schema_version") != 1
            or payload.get("policy_revision") != POLICY_REVISION_V4
            or payload.get("project_id") != self.project_id()
            or payload.get("adapter_mode") != "cooperative"
        ):
            raise ValueError(
                "host-adapter configuration binding mismatch"
            )
        issuers = require_string_list(
            payload,
            "trusted_host_issuers",
        )
        if not issuers:
            raise ValueError(
                "host-adapter trusted_host_issuers must be nonempty"
            )
        if any(not item.strip() for item in issuers):
            raise ValueError(
                "host-adapter trusted_host_issuers must contain "
                "nonempty strings"
            )
        if len(issuers) != len(set(issuers)):
            raise ValueError(
                "host-adapter trusted_host_issuers are duplicated"
            )
        return tuple(sorted(issuers))

    def collaboration(self) -> PulseStore | V5PulseStore:
        if (
            self.project_path.exists()
            and self.workflow_evidence_version() == V5_WORKFLOW_EVIDENCE_VERSION
        ):
            return self._guard_child(
                V5PulseStore(
                    self,
                    mutation_lock=self.mutation_lock,
                    trusted_host_issuers=self.trusted_host_issuers(),
                ),
                _PULSE_MUTATORS,
            )
        return self._guard_child(
            PulseStore(
                self.root,
                mutation_lock=self.mutation_lock,
                trusted_host_issuers=self.trusted_host_issuers(),
            ),
            _PULSE_MUTATORS,
        )

    def claims(self) -> ClaimRegistry:
        return self._guard_child(
            ClaimRegistry(self.root),
            _CLAIM_MUTATORS,
        )

    def campaigns(self) -> CampaignStore:
        return self._guard_child(
            CampaignStore(self.root),
            _CAMPAIGN_MUTATORS,
        )

    def experiments(self) -> ExperimentManager | V5ExperimentManager:
        if (
            self.project_path.exists()
            and self.workflow_evidence_version() == V5_WORKFLOW_EVIDENCE_VERSION
        ):
            return self._guard_child(
                V5ExperimentManager(
                    self,
                    mutation_lock=self.mutation_lock,
                    read_lock=self.read_lock,
                ),
                _EXPERIMENT_MUTATORS,
            )
        return self._guard_child(
            ExperimentManager(
                self.root,
                mutation_lock=self.mutation_lock,
                read_lock=self.read_lock,
            ),
            _EXPERIMENT_MUTATORS,
        )

    def verification_bundles(self) -> VerificationBundleStore:
        bundle_store = (
            VerificationBundleStore._for_inherited_chalk_fixture(
                self.root
            )
            if self._inherited_chalk_fixture
            else VerificationBundleStore(
                self.root,
                creation_authority=(
                    self._verification_bundle_creation_authority
                ),
            )
        )
        return self._guard_child(
            bundle_store,
            _VERIFICATION_BUNDLE_MUTATORS,
        )

    def fact_bundles(self) -> FactBundleStore:
        bundle_store = (
            FactBundleStore._for_inherited_chalk_fixture(
                self.root,
                acceptance_validator=(
                    self._validate_fact_bundle_profile_closure_binding
                ),
            )
            if self._inherited_chalk_fixture
            else FactBundleStore(
                self.root,
                admission_authority=self._fact_bundle_admission_authority,
                acceptance_validator=(
                    self._validate_fact_bundle_profile_closure_binding
                ),
            )
        )
        return self._guard_child(
            bundle_store,
            _FACT_BUNDLE_MUTATORS,
        )

    def _fact_bundle_profile_closure(
        self,
        manifest: dict[str, Any],
    ) -> dict[str, Any]:
        mode_status = self.reasoning_modes().status()
        fact_bundle_id = str(manifest.get("fact_bundle_id", ""))
        if not mode_status.get("initialized"):
            if self.reasoning_modes().is_historical_accepted_bundle(
                fact_bundle_id
            ):
                return {
                    "state": "historical_chalk_v4_read_only_baseline",
                    "required_features": [],
                    "closed": True,
                }
            raise ValueError(
                "legacy Chalk V4 fact bundle is not closure-ready before "
                "mode-init"
            )
        if self.reasoning_modes().is_historical_accepted_bundle(
            fact_bundle_id
        ):
            return {
                "state": "historical_chalk_v4_activation_baseline",
                "required_features": [],
                "closed": True,
            }
        provenance = manifest.get("provenance")
        if not isinstance(provenance, dict):
            raise ValueError(
                "unified V4 fact bundle requires profile-bound round provenance"
            )
        return self.profile_closures().require_round_assignment_ready(
            require_string(provenance, "round_id"),
            require_string(provenance, "assignment_id"),
            expected_outcome="fact_bundle_submission",
            expected_effect_key="fact_bundle_id",
            expected_subject_id=manifest["fact_bundle_id"],
        )

    def _validate_fact_bundle_profile_closure_binding(
        self,
        manifest: dict[str, Any],
        marker: dict[str, Any],
    ) -> dict[str, Any]:
        """Revalidate one accepted bundle's exact workflow-closure binding."""

        profile_closure = self._fact_bundle_profile_closure(manifest)
        closure_sha = profile_closure.get("receipt_sha256")
        if isinstance(closure_sha, str):
            if (
                marker.get("profile_closure_id")
                != profile_closure.get("closure_id")
                or marker.get("profile_closure_sha256") != closure_sha
            ):
                raise ValueError(
                    "fact bundle acceptance profile-closure binding mismatch"
                )
        elif {
            "profile_closure_id",
            "profile_closure_sha256",
        }.intersection(marker):
            raise ValueError(
                "fact bundle acceptance binds a spurious profile closure"
            )
        return profile_closure

    def _validated_fact_bundle_provenance_ids(
        self,
    ) -> tuple[set[str], list[str]]:
        """Return Fact ids backed by fully valid atomic acceptance evidence.

        Marker, manifest, verifier package, clean review, and any required
        profile closure are all revalidated before an id can count as local
        admission provenance. Invalid or colliding bundles contribute no such
        ids and remain explicit audit errors.
        """

        bundles = self.fact_bundles()
        records: list[tuple[str, list[str]]] = []
        errors: list[str] = []
        for directory in sorted(bundles.root.glob("factbundle-*")):
            marker_path = directory / "ACCEPTED.json"
            if not marker_path.exists():
                continue
            try:
                manifest, _, marker = bundles._validated_acceptance(
                    directory.name
                )
                self._validate_fact_bundle_profile_closure_binding(
                    manifest,
                    marker,
                )
                records.append((directory.name, list(manifest["fact_ids"])))
            except Exception as exc:
                errors.append(f"{directory.name}: {exc}")

        owners: dict[str, list[str]] = {}
        for bundle_id, fact_ids in records:
            for fact_id in fact_ids:
                owners.setdefault(fact_id, []).append(bundle_id)
        for fact_id, bundle_ids in sorted(owners.items()):
            if len(bundle_ids) > 1:
                errors.append(
                    "accepted fact bundle id collision for "
                    f"{fact_id}: " + ", ".join(sorted(bundle_ids))
                )
        valid = {
            fact_id
            for fact_id, bundle_ids in owners.items()
            if len(bundle_ids) == 1
        }
        return valid, errors

    def fact_bundle_verifier_task(
        self,
        fact_bundle_id: str,
    ) -> dict[str, Any]:
        """Freeze a least-privilege atomic-bundle verifier package."""

        with self.mutation_lock():
            bundles = self.fact_bundles()
            manifest = bundles.manifest(fact_bundle_id)
            self._fact_bundle_profile_closure(manifest)
            directory = bundles.root / fact_bundle_id
            candidate_ids = set(manifest["fact_ids"])
            external_predecessors: set[str] = set()
            for fact_id in manifest["fact_ids"]:
                fact = parse_fact_markdown(
                    (
                        directory / "facts" / f"{fact_id}.md"
                    ).read_text(encoding="utf-8")
                )
                external_predecessors.update(
                    predecessor
                    for predecessor in fact.predecessors
                    if predecessor not in candidate_ids
                )
            active = set(self.fact_ids())
            missing = sorted(external_predecessors.difference(active))
            if missing:
                raise ValueError(
                    "fact bundle verifier has unavailable predecessors: "
                    + ", ".join(missing)
                )
            predecessor_packets = {
                predecessor: {
                    "statement": self.get_fact(predecessor).statement,
                    "interface": self.statement_interface(predecessor),
                }
                for predecessor in sorted(external_predecessors)
            }
            return bundles.verifier_task(
                fact_bundle_id,
                predecessor_packets=predecessor_packets,
                _verification_authority=(
                    self._fact_bundle_admission_authority
                ),
            )

    def record_fact_bundle_review(
        self,
        fact_bundle_id: str,
        review: dict[str, Any],
    ) -> str:
        """Record one atomic review only after the same closure revalidation."""

        with self.mutation_lock():
            bundles = self.fact_bundles()
            manifest = bundles.manifest(fact_bundle_id)
            self._fact_bundle_profile_closure(manifest)
            return bundles.record_review(
                fact_bundle_id,
                review,
                _verification_authority=(
                    self._fact_bundle_admission_authority
                ),
            )

    def admit_fact_bundle(
        self,
        fact_bundle_id: str,
        *,
        review_id: str,
    ) -> dict[str, Any]:
        """Preflight the unified DAG, then reveal one atomic bundle marker."""

        with self.mutation_lock():
            bundles = self.fact_bundles()
            manifest = bundles.manifest(fact_bundle_id)
            profile_closure = self._fact_bundle_profile_closure(manifest)
            directory = bundles.root / fact_bundle_id
            candidates = {
                fact_id: parse_fact_markdown(
                    (
                        directory / "facts" / f"{fact_id}.md"
                    ).read_text(encoding="utf-8")
                )
                for fact_id in manifest["fact_ids"]
            }
            current = self.facts()
            already_visible = set(current).intersection(candidates)
            if (directory / "ACCEPTED.json").exists():
                acceptance = bundles.acceptance_for_fact(
                    manifest["fact_ids"][0]
                )
                if acceptance["marker"]["review_id"] != review_id:
                    raise ValueError(
                        "fact bundle was already accepted with another review"
                    )
                self._validate_fact_bundle_profile_closure_binding(
                    manifest,
                    acceptance["marker"],
                )
                return acceptance["marker"]
            if already_visible:
                raise ValueError(
                    "fact bundle collides with active fact ids: "
                    + ", ".join(sorted(already_visible))
                )
            combined = {**current, **candidates}
            graph = DependencyGraph(combined)
            missing = graph.missing_predecessors()
            if missing:
                raise ValueError(
                    "fact bundle has unavailable predecessors: "
                    + ", ".join(
                        f"{fact_id}->{predecessor}"
                        for fact_id, predecessor in missing
                    )
                )
            graph.topological_order()
            marker = bundles.admit(
                fact_bundle_id,
                review_id=review_id,
                _admission_authority=self._fact_bundle_admission_authority,
                profile_closure=(
                    {
                        "profile_closure_id": profile_closure[
                            "closure_id"
                        ],
                        "profile_closure_sha256": profile_closure[
                            "receipt_sha256"
                        ],
                    }
                    if isinstance(
                        profile_closure.get("receipt_sha256"), str
                    )
                    else None
                ),
            )
            # The marker is now the sole visibility switch. Generate derived
            # statement interfaces only after every candidate is visible.
            for fact_id in manifest["fact_ids"]:
                self.statement_interface(fact_id)
            return marker

    def _initialize_v4_state(
        self,
        *,
        actor: str,
        create_default_campaign: bool = True,
    ) -> None:
        """Create only additive v4 state; never rewrite a legacy evidence object."""

        blackboard = self.blackboard()
        blackboard.initialize(actor=actor)
        self.claims().initialize()
        campaigns = self.campaigns()
        campaigns.initialize()
        self.verification_bundles().initialize()
        (self.root / "experiments").mkdir(parents=True, exist_ok=True)
        (self.root / "fact_graph" / "bundles").mkdir(parents=True, exist_ok=True)
        self.append_anchors_dir.mkdir(parents=True, exist_ok=True)

        if not blackboard.nodes():
            blackboard.create_space(
                name="project",
                scope="Project-wide exploration; never a proof premise.",
                actor=actor,
            )
        blackboard.reindex(apply=True, actor=actor)

        if create_default_campaign and campaigns.active() is None:
            admitted_fact_ids = set(self.fact_ids())
            campaign_id = campaigns.create(
                {
                    "name": "v4-default",
                    "objective": self.project().get("description")
                    or self.project().get("title")
                    or self.project_id(),
                    "source_claim_ids": [],
                    "targets": [],
                    "constraints": [],
                    "stop_conditions": [],
                    "value_definition": (
                        "Prefer work that changes a target claim's mathematical status "
                        "at the lowest justified cost."
                    ),
                },
                actor=actor,
                fact_exists=admitted_fact_ids.__contains__,
            )
            campaigns.activate(campaign_id, actor=actor)

    def _legacy_immutable_inventory(self) -> dict[str, str]:
        """Hash records migration is forbidden to rewrite.

        The inventory deliberately excludes project.json, because changing its
        workflow label is the one permitted legacy mutation, append-only logs
        whose old byte prefix is protected separately, mutable derived
        projections, and all additive v4 roots.
        """

        excluded_roots = {
            "blackboard",
            "campaigns",
            "claims",
            "conventions",
            "experiments",
            "migrations",
        }
        excluded_prefixes = {
            "fact_graph/bundles",
            "fact_graph/interfaces",
            "verification_queue/bundles",
        }
        excluded_files = {"project.json", ".mathgraph.lock"}
        inventory: dict[str, str] = {}
        if not self.root.exists():
            return inventory
        for path in sorted(self.root.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            relative = path.relative_to(self.root).as_posix()
            first = relative.split("/", 1)[0]
            if first in excluded_roots or relative in excluded_files:
                continue
            if (
                relative in _LEGACY_APPEND_ONLY_PATHS
                or relative in _LEGACY_MUTABLE_PROJECTION_PATHS
            ):
                continue
            if any(
                relative == prefix or relative.startswith(prefix + "/")
                for prefix in excluded_prefixes
            ):
                continue
            inventory[relative] = sha256_bytes(path.read_bytes())
        return inventory

    def _legacy_append_only_prefix_inventory(
        self,
    ) -> dict[str, dict[str, Any]]:
        """Bind the exact pre-migration prefix of logs V4 may append to."""

        inventory: dict[str, dict[str, Any]] = {}
        for relative in sorted(_LEGACY_APPEND_ONLY_PATHS):
            path = self.root / relative
            if not path.exists():
                continue
            if not path.is_file() or path.is_symlink():
                raise ValueError(
                    f"legacy append-only path is not a regular file: {relative}"
                )
            raw = path.read_bytes()
            inventory[relative] = {
                "byte_length": len(raw),
                "sha256": sha256_bytes(raw),
            }
        return inventory

    def _assert_v4_reserved_paths_clean(self) -> None:
        """Fail closed when legacy bytes collide with V4-owned namespaces."""

        collisions: list[str] = []
        for relative in sorted(_V4_RESERVED_ADDITIVE_PATHS):
            path = self.root / relative
            if not os.path.lexists(path):
                continue
            if path.is_symlink() or path.is_file():
                collisions.append(relative)
                continue
            children = list(path.iterdir())
            if children:
                collisions.append(relative)
        if collisions:
            raise ValueError(
                "legacy project already contains nonempty V4-reserved paths: "
                + ", ".join(collisions)
            )

    @staticmethod
    def _validate_stable_copy_inheritance(
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate the copy boundary recorded by a project-level upgrade."""

        if not isinstance(payload, dict):
            raise ValueError("stable-copy inheritance must be an object")
        require_exact_keys(
            payload,
            required={
                "schema_version",
                "inheritance_kind",
                "source_project_id",
                "source_workflow_evidence_version",
                "source_tree_sha256",
                "source_file_count",
                "source_total_bytes",
                "source_project_semantic_sha256",
                "assurance_policy",
                "state_boundary",
            },
            label="stable-copy inheritance",
        )
        if payload.get("schema_version") != 1:
            raise ValueError("stable-copy inheritance schema_version must be 1")
        if payload.get("inheritance_kind") != _STABLE_COPY_INHERITANCE_KIND:
            raise ValueError("stable-copy inheritance kind mismatch")
        source_project_id = payload.get("source_project_id")
        if (
            not isinstance(source_project_id, str)
            or not source_project_id.strip()
            or "\n" in source_project_id
            or "\r" in source_project_id
        ):
            raise ValueError(
                "stable-copy inheritance source_project_id is invalid"
            )
        if payload.get("source_workflow_evidence_version") != 3:
            raise ValueError(
                "stable-copy inheritance source workflow must be 3"
            )
        for key in ("source_tree_sha256", "source_project_semantic_sha256"):
            value = payload.get(key)
            if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
                raise ValueError(
                    f"stable-copy inheritance {key} is invalid"
                )
        for key in ("source_file_count", "source_total_bytes"):
            value = payload.get(key)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
            ):
                raise ValueError(
                    f"stable-copy inheritance {key} is invalid"
                )
        if payload["source_file_count"] < 1:
            raise ValueError(
                "stable-copy inheritance source_file_count must be positive"
            )
        if payload.get("assurance_policy") != _STABLE_COPY_ASSURANCE_POLICY:
            raise ValueError("stable-copy inheritance assurance policy mismatch")
        if payload.get("state_boundary") != _STABLE_COPY_STATE_BOUNDARY:
            raise ValueError("stable-copy inheritance state boundary mismatch")
        return dict(payload)

    def upgrade_workflow(
        self,
        *,
        to_version: int,
        dry_run: bool,
        actor: str = "",
        stable_copy_inheritance: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Add a v4 projection without rewriting v1-v3 evidence bytes."""

        self.require_initialized()
        if to_version != 4:
            raise ValueError("only workflow upgrade --to 4 is supported")
        current = self.workflow_evidence_version()
        if current not in {3, 4}:
            raise ValueError(
                f"workflow upgrade requires an explicit v3 project, found {current}"
            )
        if current == 3:
            self._assert_v4_reserved_paths_clean()
        before_project = self.project()
        inventory = self._legacy_immutable_inventory()
        append_only_prefixes = self._legacy_append_only_prefix_inventory()
        inventory_sha = sha256_json(inventory)
        append_only_prefixes_sha = sha256_json(append_only_prefixes)
        inheritance = (
            self._validate_stable_copy_inheritance(
                stable_copy_inheritance
            )
            if stable_copy_inheritance is not None
            else None
        )
        plan = {
            "schema_version": 4,
            "policy_revision": POLICY_REVISION_V4,
            "from_workflow_evidence_version": current,
            "to_workflow_evidence_version": 4,
            "legacy_file_count": len(inventory) + len(append_only_prefixes),
            "legacy_inventory_sha256": inventory_sha,
            "legacy_append_only_prefixes_sha256": append_only_prefixes_sha,
            "legacy_append_only_file_count": len(append_only_prefixes),
            "legacy_mutable_projections": sorted(
                _LEGACY_MUTABLE_PROJECTION_PATHS
            ),
            "will_rewrite": ["project.json"] if current == 3 else [],
            "will_create": [
                "blackboard/",
                "campaigns/",
                "claims/",
                "conventions/",
                "experiments/",
                "fact_graph/bundles/",
                "fact_graph/interfaces/",
                "verification_queue/bundles/",
                "migrations/",
            ],
            "dry_run": dry_run,
        }
        if dry_run or current == 4:
            return {
                **plan,
                "status": "already_v4" if current == 4 else "planned",
            }
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError("workflow upgrade requires a nonempty actor")

        with self._uninitialized_v4_transition_lock():
            if self.workflow_evidence_version() != 3:
                raise ValueError("workflow version changed after dry-run planning")
            upgraded_project = {
                **before_project,
                "workflow_evidence_version": 4,
                "policy_revision": POLICY_REVISION_V4,
            }
            self._write_json_atomic(self.project_path, upgraded_project)
            self._initialize_v4_state(
                actor=actor.strip(),
                create_default_campaign=False,
            )
            campaigns = self.campaigns()
            legacy_targets = self.targets()
            admitted_fact_ids = set(self.fact_ids())
            campaign_id = campaigns.create(
                {
                    "name": "legacy-default",
                    "objective": (
                        "Read-time projection of the pre-v4 project targets and "
                        "research direction."
                    ),
                    "source_claim_ids": [],
                    "targets": [
                        {
                            "role": "headline_proof",
                            "subject_kind": "fact",
                            "subject_id": fact_id,
                            "label": f"Legacy target {fact_id}",
                        }
                        for fact_id in legacy_targets
                    ],
                    "constraints": ["Preserve all v1-v3 evidence bytes."],
                    "stop_conditions": [],
                    "value_definition": (
                        "Preserve the legacy target closure while new work uses "
                        "cost-aware v4 campaigns."
                    ),
                },
                actor=actor.strip(),
                fact_exists=admitted_fact_ids.__contains__,
            )
            campaigns.activate(campaign_id, actor=actor.strip())
            semantic = {
                "schema_version": 4,
                "policy_revision": POLICY_REVISION_V4,
                "migration": "workflow-evidence-v3-to-v4",
                "actor": actor.strip(),
                "project_id": self.project_id(),
                "project_before_sha256": sha256_json(before_project),
                "project_after_sha256": sha256_json(upgraded_project),
                "legacy_inventory_sha256": inventory_sha,
                "legacy_inventory": inventory,
                "legacy_append_only_prefixes_sha256": (
                    append_only_prefixes_sha
                ),
                "legacy_append_only_prefixes": append_only_prefixes,
                "legacy_mutable_projections": sorted(
                    _LEGACY_MUTABLE_PROJECTION_PATHS
                ),
                "legacy_default_campaign_id": campaign_id,
                "legacy_targets": legacy_targets,
            }
            if inheritance is not None:
                if inheritance["source_project_id"] != self.project_id():
                    raise ValueError(
                        "stable-copy source project id does not match the copy"
                    )
                if (
                    inheritance["source_project_semantic_sha256"]
                    != sha256_json(before_project)
                ):
                    raise ValueError(
                        "stable-copy source project declaration does not "
                        "match the copy"
                    )
                semantic["stable_copy_inheritance"] = inheritance
            receipt_id = sha256_json(semantic)
            receipt = {
                **semantic,
                "migration_receipt_id": receipt_id,
                "applied_at": utc_now(),
            }
            self._write_json_once(
                self.migrations_dir / f"{receipt_id}.json",
                receipt,
            )
            after_inventory = self._legacy_immutable_inventory()
            after_append_only = self._legacy_append_only_prefix_inventory()
            if (
                after_inventory != inventory
                or after_append_only != append_only_prefixes
            ):
                raise RuntimeError(
                    "legacy evidence changed during migration; staged project is unsafe"
                )
        return {
            **plan,
            "dry_run": False,
            "status": "upgraded",
            "migration_receipt_id": receipt_id,
            "legacy_default_campaign_id": campaign_id,
        }

    @staticmethod
    def _write_bytes_atomic(path: Path, payload: bytes, mode: int = 0o600) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
        try:
            os.fchmod(fd, mode)
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except BaseException:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise

    @classmethod
    def _write_text_atomic(cls, path: Path, payload: str, mode: int = 0o600) -> None:
        cls._write_bytes_atomic(path, payload.encode("utf-8"), mode=mode)

    @classmethod
    def _write_json_atomic(cls, path: Path, payload: Any) -> None:
        cls._write_text_atomic(
            path,
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )

    @staticmethod
    def _write_bytes_once(path: Path, payload: bytes, mode: int = 0o600) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            raise ValueError(f"refusing to write through symlink: {path}")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            fd = os.open(path, flags, mode)
        except FileExistsError:
            if not path.is_file() or path.is_symlink():
                raise ValueError(f"immutable evidence path is not a regular file: {path}")
            if path.read_bytes() != payload:
                raise ValueError(f"immutable evidence collision at {path}")
            return
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            raise

    @classmethod
    def _write_json_once(cls, path: Path, payload: Any) -> None:
        cls._write_bytes_once(
            path,
            (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
                "utf-8"
            ),
        )

    @staticmethod
    def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def _append_jsonl_once(
        self,
        path: Path,
        payload: dict[str, Any],
        *,
        event_id: str,
    ) -> None:
        for existing in self._read_jsonl(path):
            if existing.get("event_id") == event_id:
                existing_semantic = {
                    key: value for key, value in existing.items() if key != "timestamp"
                }
                payload_semantic = {
                    key: value for key, value in payload.items() if key != "timestamp"
                }
                if existing_semantic != payload_semantic:
                    raise ValueError(f"event id collision in {path}: {event_id}")
                return
        if (
            self.workflow_evidence_version() >= 4
            and path.resolve().is_relative_to(self.root)
            and path.resolve().relative_to(self.root).as_posix()
            in _LEGACY_APPEND_ONLY_PATHS
        ):
            self._write_v4_append_anchor(
                path=path,
                payload=payload,
                event_id=event_id,
            )
        self._append_jsonl(path, payload)

    def _write_v4_append_anchor(
        self,
        *,
        path: Path,
        payload: dict[str, Any],
        event_id: str,
    ) -> str:
        relative = path.resolve().relative_to(self.root).as_posix()
        if relative not in _LEGACY_APPEND_ONLY_PATHS:
            raise ValueError("append anchor path is not governed")
        if payload.get("event_id") != event_id:
            raise ValueError("append anchor event_id/payload mismatch")
        semantic = {
            "schema_version": 4,
            "policy_revision": POLICY_REVISION_V4,
            "writer_engine": _APPEND_ANCHOR_WRITER_ENGINE,
            "log_path": relative,
            "event_id": event_id,
            "event_sha256": sha256_json(payload),
            "event": payload,
        }
        anchor_id = sha256_json(semantic)
        anchor = {
            **semantic,
            "anchor_id": anchor_id,
        }
        self._write_json_once(
            self.append_anchors_dir / f"{anchor_id}.json",
            anchor,
        )
        return anchor_id

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"expected one JSON object in {path}")
        return payload

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        entries: list[dict[str, Any]] = []
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at {path}:{number}: {exc}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"JSONL entry is not an object at {path}:{number}")
            entries.append(payload)
        return entries

    def _audit_v4_append_anchors(
        self,
        legacy_prefix_lengths: dict[str, int],
    ) -> list[str]:
        """Cross-check every V4 suffix event against a write-once sidecar."""

        errors: list[str] = []
        anchors: dict[
            tuple[str, str, str],
            dict[str, Any],
        ] = {}
        if self.append_anchors_dir.exists():
            for path in sorted(self.append_anchors_dir.rglob("*")):
                if path.is_dir():
                    continue
                if path.is_symlink() or not path.is_file():
                    errors.append(
                        "append anchor is not a regular file: "
                        f"{path.relative_to(self.root).as_posix()}"
                    )
                    continue
                try:
                    anchor = self._read_json(path)
                    require_exact_keys(
                        anchor,
                        required={
                            "schema_version",
                            "policy_revision",
                            "writer_engine",
                            "log_path",
                            "event_id",
                            "event_sha256",
                            "event",
                            "anchor_id",
                        },
                        label="V4 append anchor",
                    )
                    if anchor.get("schema_version") != 4:
                        raise ValueError("schema_version must be 4")
                    if anchor.get("policy_revision") != POLICY_REVISION_V4:
                        raise ValueError("policy revision mismatch")
                    if anchor.get("writer_engine") not in (
                        _ACCEPTED_APPEND_ANCHOR_WRITER_ENGINES
                    ):
                        raise ValueError("writer engine mismatch")
                    log_path = require_string(anchor, "log_path")
                    if log_path not in _LEGACY_APPEND_ONLY_PATHS:
                        raise ValueError("log path is not governed")
                    event_id = require_string(anchor, "event_id")
                    event_sha = require_string(anchor, "event_sha256")
                    if SHA256_RE.fullmatch(event_sha) is None:
                        raise ValueError("event_sha256 is invalid")
                    event = anchor.get("event")
                    if not isinstance(event, dict):
                        raise ValueError("event must be an object")
                    if event.get("event_id") != event_id:
                        raise ValueError("event id binding mismatch")
                    if sha256_json(event) != event_sha:
                        raise ValueError("event hash mismatch")
                    semantic = {
                        key: anchor[key]
                        for key in (
                            "schema_version",
                            "policy_revision",
                            "writer_engine",
                            "log_path",
                            "event_id",
                            "event_sha256",
                            "event",
                        )
                    }
                    anchor_id = sha256_json(semantic)
                    if (
                        path.stem != anchor_id
                        or anchor.get("anchor_id") != anchor_id
                    ):
                        raise ValueError("anchor id/hash mismatch")
                    key = (log_path, event_id, event_sha)
                    if key in anchors:
                        raise ValueError("duplicate append anchor")
                    anchors[key] = anchor
                except Exception as exc:
                    errors.append(f"append anchor {path.name}: {exc}")

        suffix_events: dict[
            tuple[str, str, str],
            dict[str, Any],
        ] = {}
        for relative in sorted(_LEGACY_APPEND_ONLY_PATHS):
            path = self.root / relative
            raw = path.read_bytes() if path.is_file() else b""
            prefix_length = legacy_prefix_lengths.get(relative, 0)
            if prefix_length > len(raw):
                errors.append(
                    f"append-only log is shorter than its legacy prefix: "
                    f"{relative}"
                )
                continue
            if prefix_length and raw[prefix_length - 1 : prefix_length] != b"\n":
                errors.append(
                    f"legacy append-only prefix is not line-aligned: {relative}"
                )
                continue
            suffix = raw[prefix_length:]
            for line_number, line in enumerate(
                suffix.splitlines(keepends=True),
                1,
            ):
                if not line.strip():
                    errors.append(
                        f"blank V4 append-only line in {relative}:"
                        f"{line_number}"
                    )
                    continue
                if not line.endswith(b"\n"):
                    errors.append(
                        f"unterminated V4 append-only line in {relative}:"
                        f"{line_number}"
                    )
                try:
                    event = json.loads(line.decode("utf-8"))
                    if not isinstance(event, dict):
                        raise ValueError("event is not an object")
                    event_id = require_string(event, "event_id")
                    event_sha = sha256_json(event)
                    key = (relative, event_id, event_sha)
                    if key in suffix_events:
                        raise ValueError("duplicate event")
                    suffix_events[key] = event
                except Exception as exc:
                    errors.append(
                        f"invalid V4 append-only event in {relative}:"
                        f"{line_number}: {exc}"
                    )

        for key, event in suffix_events.items():
            anchor = anchors.get(key)
            if anchor is None:
                errors.append(
                    "V4 append-only event has no Chalk sidecar anchor: "
                    f"{key[0]}:{key[1]}"
                )
            elif anchor["event"] != event:
                errors.append(
                    "V4 append-only event/anchor mismatch: "
                    f"{key[0]}:{key[1]}"
                )
        for key in anchors:
            if key not in suffix_events:
                errors.append(
                    "V4 append anchor has no visible log event: "
                    f"{key[0]}:{key[1]}"
                )
        return errors

    def project(self) -> dict[str, Any]:
        self.require_initialized()
        return self._read_json(self.project_path)

    def project_id(self) -> str:
        value = self.project().get("project_id")
        if not isinstance(value, str) or not value.strip():
            raise ValueError("project.json has an invalid project_id")
        return value

    def fact_path(self, fact_id: str) -> Path:
        return self.facts_dir / f"{validate_fact_id(fact_id)}.md"

    def submission_path(self, fact_id: str) -> Path:
        return self.submissions_dir / f"{validate_fact_id(fact_id)}.json"

    def review_path(self, review_id: str) -> Path:
        return self.reviews_by_id_dir / f"{validate_review_id(review_id)}.json"

    def _revoked_fact_ids(self) -> set[str]:
        result = {
            path.stem for path in self.revoked_dir.glob("*.md")
        }
        for event in self._read_jsonl(self.revocation_log):
            fact_id = event.get("fact_id")
            if isinstance(fact_id, str) and FACT_ID_RE.fullmatch(fact_id):
                result.add(fact_id)
        return result

    def _active_fact_paths(
        self,
        *,
        _inspection_context: Any | None = None,
    ) -> dict[str, Path]:
        if (
            self.project_path.exists()
            and self.workflow_evidence_version()
            == V5_WORKFLOW_EVIDENCE_VERSION
        ):
            ordinary = sorted(self.facts_dir.glob("*.md"))
            if ordinary:
                raise ValueError(
                    "V5 Fact visibility forbids legacy ordinary Fact files; "
                    "only V5 admission markers may expose Facts"
                )
            return self.v5_lifecycle().active_fact_paths(
                _inspection_context=_inspection_context
            )
        revoked = self._revoked_fact_ids()
        ordinary = {
            path.stem: path
            for path in sorted(self.facts_dir.glob("*.md"))
            if path.stem not in revoked
        }
        bundled = self.fact_bundles().accepted_fact_paths(
            excluded_fact_ids=revoked,
            strict=False,
        )
        collisions = set(ordinary).intersection(bundled)
        if collisions:
            raise ValueError(
                "fact id appears in both ordinary and atomic bundle stores: "
                + ", ".join(sorted(collisions))
            )
        return {**ordinary, **bundled}

    def active_fact_path(
        self,
        fact_id: str,
        *,
        _inspection_context: Any | None = None,
    ) -> Path:
        fact_id = validate_fact_id(fact_id)
        path = self._active_fact_paths(
            _inspection_context=_inspection_context
        ).get(fact_id)
        if path is None:
            raise KeyError(f"unknown verified fact: {fact_id}")
        return path

    def fact_ids(self, *, _inspection_context: Any | None = None) -> list[str]:
        return sorted(
            self._active_fact_paths(
                _inspection_context=_inspection_context
            )
        )

    def get_raw_fact(
        self,
        fact_id: str,
        *,
        _inspection_context: Any | None = None,
    ) -> str:
        path = self.active_fact_path(
            fact_id,
            _inspection_context=_inspection_context,
        )
        return path.read_text(encoding="utf-8")

    def get_fact(
        self,
        fact_id: str,
        *,
        _inspection_context: Any | None = None,
    ) -> Fact:
        fact_id = validate_fact_id(fact_id)
        if (
            _inspection_context is not None
            and _inspection_context.active_facts is not None
            and fact_id in _inspection_context.active_facts
        ):
            return _inspection_context.active_facts[fact_id]
        fact = parse_fact_markdown(
            self.get_raw_fact(
                fact_id,
                _inspection_context=_inspection_context,
            )
        )
        errors = fact.validate()
        if errors:
            raise ValueError(f"invalid verified fact {fact_id}: {'; '.join(errors)}")
        if fact.problem_id != self.project_id():
            raise ValueError(f"verified fact {fact_id} belongs to another project")
        return fact

    def facts(
        self,
        *,
        _inspection_context: Any | None = None,
    ) -> dict[str, Fact]:
        if (
            _inspection_context is not None
            and _inspection_context.active_facts is not None
        ):
            return dict(_inspection_context.active_facts)
        return {
            fact_id: self.get_fact(
                fact_id,
                _inspection_context=_inspection_context,
            )
            for fact_id in self.fact_ids(
                _inspection_context=_inspection_context
            )
        }

    def statement_interface(
        self,
        fact_id: str,
        *,
        materialize: bool = True,
        _inspection_context: Any | None = None,
    ) -> dict[str, Any]:
        """Return the statement-only interface for one active fact.

        ``materialize=True`` is a mutation-capable operation and therefore
        shares the project mutation guard even when the projection already
        exists. Read-only callers must set ``materialize=False``; a missing
        legacy projection is then reconstructed only in memory.
        """

        if materialize:
            with self.mutation_lock():
                return self._statement_interface(
                    fact_id,
                    materialize=True,
                    _inspection_context=_inspection_context,
                )
        return self._statement_interface(
            fact_id,
            materialize=False,
            _inspection_context=_inspection_context,
        )

    def _statement_interface(
        self,
        fact_id: str,
        *,
        materialize: bool,
        _inspection_context: Any | None = None,
    ) -> dict[str, Any]:
        """Implement guarded materialization or a byte-pure reconstruction."""

        fact_id = validate_fact_id(fact_id)
        fact = self.get_fact(
            fact_id,
            _inspection_context=_inspection_context,
        )
        path = self.interfaces_dir / f"{fact_id}.json"
        if path.exists():
            return validate_statement_interface(
                self._read_json(path),
                active_fact_ids=set(
                    self.fact_ids(
                        _inspection_context=_inspection_context
                    )
                ),
            )
        fact_path = self.active_fact_path(
            fact_id,
            _inspection_context=_inspection_context,
        )
        fact_bytes = fact_path.read_bytes()
        submission_path = self.submission_path(fact_id)
        submission = (
            self._read_json(submission_path) if submission_path.exists() else {}
        )
        review_id = submission.get("accepted_review_id")
        bundle_acceptance: dict[str, Any] | None = None
        if not submission and fact_path.is_relative_to(self.fact_bundles().root):
            bundle_acceptance = self.fact_bundles().acceptance_for_fact(fact_id)
            review_id = bundle_acceptance["marker"]["review_id"]
        if not isinstance(review_id, str) or SHA256_RE.fullmatch(review_id) is None:
            review_id = sha256_json(
                ["legacy-admission-review-projection", fact_id, sha256_bytes(fact_bytes)]
            )
        acceptance_event_sha = ""
        if bundle_acceptance is not None:
            acceptance_event_sha = bundle_acceptance["marker"][
                "acceptance_sha256"
            ]
        for event in self._read_jsonl(self.verification_log):
            if event.get("event") == "accepted" and event.get("fact_id") == fact_id:
                candidate = event.get("event_id")
                if isinstance(candidate, str) and SHA256_RE.fullmatch(candidate):
                    acceptance_event_sha = candidate
        if not acceptance_event_sha:
            acceptance_event_sha = sha256_json(
                ["legacy-acceptance-projection", fact_id, review_id]
            )
        interface = build_statement_interface(
            fact=fact,
            stored_fact_sha256=sha256_bytes(fact_bytes),
            acceptance_event_sha256=acceptance_event_sha,
            admission_review_id=review_id,
            workflow_evidence_version=(
                4
                if submission.get("evidence_version") == 4
                or bundle_acceptance is not None
                else 3
            ),
        )
        if materialize:
            write_interface_once(path, interface)
        return interface

    def targets(self) -> list[str]:
        if not self.targets_path.exists():
            return []
        return [
            line.strip()
            for line in self.targets_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]

    def _write_targets_projection(self, target_ids: list[str]) -> None:
        target_ids = [validate_fact_id(item) for item in target_ids]
        facts = set(self.fact_ids())
        unknown = [fact_id for fact_id in target_ids if fact_id not in facts]
        if unknown:
            raise ValueError(
                f"targets are not verified facts: {', '.join(unknown)}"
            )
        for fact_id in target_ids:
            self.get_fact(fact_id)
        unique = list(dict.fromkeys(target_ids))
        self._write_text_atomic(
            self.targets_path,
            "\n".join(unique) + ("\n" if unique else ""),
        )
        self._write_target_certificate(unique)

    def set_targets(self, target_ids: list[str]) -> None:
        with self.mutation_lock():
            if self.workflow_evidence_version() >= 4:
                raise ValueError(
                    "V4 TARGETS.txt is an active-campaign derived projection; "
                    "use campaign target events"
                )
            self._write_targets_projection(target_ids)

    def sync_active_campaign_targets(
        self,
        *,
        campaign_id: str | None = None,
    ) -> list[str]:
        with self.mutation_lock():
            if self.workflow_evidence_version() < 4:
                raise ValueError(
                    "campaign target projection requires workflow evidence v4"
                )
            campaigns = self.campaigns()
            active = campaigns.active()
            selected = campaign_id or active
            if selected is None or selected != active:
                raise ValueError(
                    "only the active campaign may drive TARGETS.txt"
                )
            targets = campaigns.derived_targets(selected)
            self._write_targets_projection(targets)
            return targets

    def _target_certificate_payload(self, target_ids: list[str]) -> dict[str, Any]:
        facts = self.facts()
        graph = DependencyGraph(facts)
        closure = graph.closure(target_ids) if target_ids else set()
        order = graph.topological_order(closure) if closure else []
        fact_sha256 = {
            fact_id: hashlib.sha256(
                self.active_fact_path(fact_id).read_bytes()
            ).hexdigest()
            for fact_id in order
        }
        payload: dict[str, Any] = {
            "targets": target_ids,
            "closure": order,
            "closure_size": len(order),
            "edges_in_closure": sum(
                1
                for fact_id in order
                for predecessor in facts[fact_id].predecessors
                if predecessor in closure
            ),
            "fact_sha256": fact_sha256,
        }
        payload["certificate_sha256"] = sha256_json(payload)
        return payload

    def _write_target_certificate(self, target_ids: list[str]) -> None:
        payload = self._target_certificate_payload(target_ids)
        payload["generated_at"] = utc_now()
        self._write_json_atomic(self.reports_dir / "target-closure-certificate.json", payload)

    def _validate_predecessors(self, predecessors: list[str]) -> None:
        active_paths = self._active_fact_paths()
        for predecessor in predecessors:
            validate_fact_id(predecessor)
            if predecessor not in active_paths:
                raise ValueError(f"predecessor is not verified: {predecessor}")
            self.get_fact(predecessor)
            if predecessor in self._revoked_fact_ids():
                raise ValueError(f"submission cites revoked fact: {predecessor}")

    def submit(
        self,
        fact: Fact,
        *,
        worker: str,
        task_id: str = "",
        round_id: str = "",
        assignment_id: str = "",
        claim_relation: str = "proves",
        task_card_sha256: str = "",
        blackboard_snapshot_sha256: str = "",
        artifacts: list[dict[str, str]] | None = None,
        verification_plan: dict[str, Any] | None = None,
    ) -> str:
        self.require_initialized()
        if self.workflow_evidence_version() == V5_WORKFLOW_EVIDENCE_VERSION:
            raise ValueError(
                "legacy submit cannot write V5; use Candidate Release"
            )
        with self.mutation_lock():
            workflow_version = self.workflow_evidence_version()
            is_v4 = workflow_version >= 4
            worker = self._validate_actor(worker, "worker")
            errors = fact.validate()
            if errors:
                raise ValueError("; ".join(errors))
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
            normalized_artifacts = list(artifacts or [])
            normalized_plan = dict(
                verification_plan
                or {
                    "mode": "closed_packet",
                    "authorized_artifact_roles": [],
                    "required_checks": [],
                }
            )
            if is_v4:
                clauses = extract_statement_clauses(
                    fact.statement,
                    require_v4=True,
                )
                validate_quantifier_ledger(
                    fact.quantifier_ledger,
                    statement=fact.statement,
                    proof=fact.proof,
                    clause_ids={item["clause_id"] for item in clauses},
                )
                validate_predecessor_uses(
                    fact.predecessor_uses,
                    predecessors=fact.predecessors,
                    proof=fact.proof,
                    interface_lookup=self.statement_interface,
                    convention_profile_ids=fact.convention_profile_ids,
                )
                for convention_id in fact.convention_profile_ids:
                    self.claims().show_convention(convention_id)
                validate_computational_evidence(
                    fact.computational_evidence,
                    proof=fact.proof,
                    artifacts=normalized_artifacts,
                    verification_plan=normalized_plan,
                )
                validate_terminology(fact.terminology, proof=fact.proof)
                for key, value in (
                    ("task_card_sha256", task_card_sha256),
                    ("blackboard_snapshot_sha256", blackboard_snapshot_sha256),
                ):
                    if round_id and SHA256_RE.fullmatch(value) is None:
                        raise ValueError(f"v4 round submission {key} is invalid")
            if any(ref.get("use_kind") == "formula" for ref in fact.external_refs) and not round_id:
                raise ValueError(
                    "formula source use must be submitted through a bound schema-v3 "
                    "round so source_fidelity.artifact_sha256 is tied to a declared artifact"
                )
            if claim_relation not in CLAIM_RELATIONS:
                raise ValueError(
                    "claim_relation must be one of: "
                    + ", ".join(sorted(CLAIM_RELATIONS))
                )
            if fact.problem_id != self.project_id():
                raise ValueError(
                    f"fact problem_id {fact.problem_id!r} does not match project "
                    f"{self.project_id()!r}"
                )
            validate_fact_round_trip(fact)
            self._validate_predecessors(fact.predecessors)
            if task_id:
                validate_memory_id(task_id)
                memory = self.memory_latest()
                if task_id not in memory:
                    raise ValueError(f"unknown task memory id: {task_id}")
                assigned_claim = str(memory[task_id].get("claim", "")).strip()
            else:
                assigned_claim = ""
            if bool(round_id) != bool(assignment_id):
                raise ValueError("round_id and assignment_id must be supplied together")
            if round_id:
                validate_round_id(round_id)
                validate_assignment_id(assignment_id)
                manifest_path = self.rounds_dir / round_id / "round.json"
                if not manifest_path.exists():
                    raise ValueError("submission references an unknown round")
                manifest = self._read_json(manifest_path)
                assignments = manifest.get("assignments", [])
                matches = [
                    item
                    for item in assignments
                    if isinstance(item, dict)
                    and item.get("assignment_id") == assignment_id
                ]
                if len(matches) != 1:
                    raise ValueError("submission references an unknown assignment")
                assignment = matches[0]
                if manifest.get("project_id") != self.project_id():
                    raise ValueError("submission round belongs to another project")
                if assignment.get("memory_id") != task_id:
                    raise ValueError("submission task does not match its assignment")
                if assignment.get("worker_id") != worker:
                    raise ValueError("submission worker does not match its assignment")
            payload = fact.as_submission_dict()
            payload.update(
                {
                    "evidence_version": 4 if is_v4 else 3,
                    "submission_id": fact.fact_id,
                    "submitted_at": utc_now(),
                    "worker": worker,
                    "task_id": task_id,
                    "round_id": round_id,
                    "assignment_id": assignment_id,
                    "claim_relation": claim_relation,
                    "assigned_claim": assigned_claim,
                    "status": "pending_review",
                    "review_ids": [],
                }
            )
            if is_v4:
                payload.update(
                    {
                        "policy_revision": POLICY_REVISION_V4,
                        "task_card_sha256": task_card_sha256,
                        "blackboard_snapshot_sha256": blackboard_snapshot_sha256,
                        "verification_plan": normalized_plan,
                        "artifacts": normalized_artifacts,
                    }
                )
            payload["submission_sha256"] = _submission_digest(payload)
            path = self.submission_path(fact.fact_id)
            if path.exists():
                existing = self._read_json(path)
                if existing.get("submission_sha256") != payload["submission_sha256"]:
                    raise ValueError(f"submission id collision at {path}")
                return fact.fact_id
            self._write_json_once(path, payload)
            return fact.fact_id

    def _v4_ingestion_receipts(self) -> list[dict[str, Any]]:
        receipts: list[dict[str, Any]] = []
        project_id = self.project_id()
        for path in sorted(
            self.rounds_dir.glob("*/returns/*.receipt.json")
        ):
            payload = self._read_json(path)
            if payload.get("schema_version") != 4:
                continue
            validate_ingestion_receipt_v4(payload)
            round_id = require_string(payload, "round_id")
            assignment_id = require_string(payload, "assignment_id")
            if payload["project_id"] != project_id:
                raise ValueError(
                    "v4 ingestion receipt belongs to another project"
                )
            round_dir = path.parent.parent
            if (
                round_dir.name != round_id
                or path.name != f"{assignment_id}.receipt.json"
            ):
                raise ValueError(
                    "v4 ingestion receipt path/binding mismatch"
                )
            manifest_path = round_dir / "round.json"
            if not manifest_path.is_file() or manifest_path.is_symlink():
                raise ValueError(
                    "v4 ingestion receipt has no frozen round manifest"
                )
            manifest = self._read_json(manifest_path)
            if (
                manifest.get("schema_version") != 4
                or manifest.get("project_id") != project_id
                or manifest.get("round_id") != round_id
            ):
                raise ValueError(
                    "v4 ingestion receipt round binding mismatch"
                )
            matches = [
                assignment
                for assignment in manifest.get("assignments", [])
                if isinstance(assignment, dict)
                and assignment.get("assignment_id") == assignment_id
            ]
            if len(matches) != 1:
                raise ValueError(
                    "v4 ingestion receipt assignment is not uniquely bound"
                )
            assignment = matches[0]
            if (
                payload.get("assignment_sha256")
                != assignment.get("assignment_sha256")
                or payload.get("return_relpath")
                != assignment.get("return_relpath")
            ):
                raise ValueError(
                    "v4 ingestion receipt assignment contract mismatch"
                )
            return_path = contained_path(
                self.root,
                require_string(assignment, "return_relpath"),
                "v4 ingestion receipt return path",
            )
            if (
                return_path != path.parent / f"{assignment_id}.json"
                or not return_path.is_file()
                or return_path.is_symlink()
            ):
                raise ValueError(
                    "v4 ingestion receipt return is missing or noncanonical"
                )
            return_sha = sha256_bytes(return_path.read_bytes())
            if (
                payload.get("return_sha256") != return_sha
                or payload.get("worker_final_sha256") != return_sha
            ):
                raise ValueError(
                    "v4 ingestion receipt return hash mismatch"
                )
            receipts.append(payload)
        return receipts

    def _v4_submission_is_visible(self, submission: dict[str, Any]) -> bool:
        round_id = submission.get("round_id")
        assignment_id = submission.get("assignment_id")
        if not round_id and not assignment_id:
            return True
        if not isinstance(round_id, str) or not isinstance(assignment_id, str):
            return False
        matches = [
            receipt
            for receipt in self._v4_ingestion_receipts()
            if receipt["round_id"] == round_id
            and receipt["assignment_id"] == assignment_id
            and receipt["outcome"] == "fact_submission"
            and receipt["effect"].get("submission_id")
            == submission.get("fact_id")
        ]
        if len(matches) > 1:
            raise ValueError("v4 submission has multiple ingestion visibility markers")
        return len(matches) == 1

    def submission(
        self,
        fact_id: str,
        *,
        include_uncommitted: bool = False,
    ) -> dict[str, Any]:
        path = self.submission_path(fact_id)
        if not path.exists():
            raise KeyError(f"unknown submission: {fact_id}")
        payload = self._read_json(path)
        if (
            not include_uncommitted
            and payload.get("evidence_version") == 4
            and not self._v4_submission_is_visible(payload)
        ):
            raise KeyError(f"uncommitted v4 submission: {fact_id}")
        return payload

    def verification_packet(self, fact_id: str) -> str:
        submission = self.submission(fact_id)
        fact = Fact.from_dict(submission)
        submission_sha = _submission_digest(submission)
        if submission.get("evidence_version") in {2, 3} and (
            submission.get("submission_sha256") != submission_sha
        ):
            raise ValueError(f"submission hash mismatch for {fact_id}")
        lines = [
            "# Stateless verification packet",
            "",
            f"Fact ID: `{fact_id}`",
            f"Submission SHA-256: `{submission_sha}`",
            "",
            "Judge only the submission below against the supplied verified predecessors.",
            "Do not search, show, or read any other project fact or exploration memory.",
            "If an external-source certificate is present, independently open only its exact",
            "primary-source locator. Confirm the cited version and result, enumerate every source",
            "hypothesis, and check its target witness, convention map, conclusion-strength comparison,",
            "exclusions, and every base-change/limit/continuation/residue or other transport step.",
            "Do not assume that a versioned primary source is mathematically reliable merely because",
            "it is citable. Verify each source_trace statement transcription and hash; hash identical",
            "source artifact bytes once per distinct artifact SHA-256. For every source item, repeat",
            "the baseline notation/binding, type/domain, and quantifier/scope checks.",
            "Group source-level status evidence by source_audit.audit_sha256. Recompute that hash,",
            "check its exact-artifact binding and at-most-30-day reuse provenance, and inspect all",
            "three stored version-history, erratum, and retraction/counterexample locators once per",
            "distinct audit rather than once per theorem. For a baseline-only group, independently",
            "repeat at least one unpredictably selected current status query. If any item is strict,",
            "repeat all three current status searches for that group.",
            "For every strict item, additionally repeat the boundary/toy-case and literal",
            "statement/proof-consistency checks. Formula or sign-sensitive use, bridge/transport or",
            "degeneration, a target-critical theorem, any correction, conflict, failed cheap check,",
            "or suspicious source signal requires strict treatment. Reject or escalate an item that",
            "was incorrectly labelled baseline; workload classification never relaxes the truth gate.",
            "A minor typo correction is admissible only when it is uniquely forced, non-semantic,",
            "does not strengthen the source, and is bound in the proof by its [CRIT:...] anchor.",
            "An official erratum must itself have an exact locator and artifact hash. An ambiguous,",
            "material, contradicted, retracted, or unresolved source claim requires `reject`; do not",
            "repair it silently or replace it with a more convenient theorem.",
            "Do not use secondary summaries or discover a replacement theorem. If the exact primary",
            "source is unavailable, the locator is inexact, a source hypothesis is omitted, or a",
            "bridge is unproved, return `reject` and name the gap.",
            "First inventory every external attribution or named result used in the proof. If any",
            "external logical source use lacks a certificate in the packet, return `reject`; an",
            "empty external_refs list is not evidence that the proof is self-contained.",
            "A load-bearing named result must be proved in the packet, supplied by a verified",
            "predecessor, covered by a source certificate, or declared in the controlled",
            "elementary-result ledger. The ledger is valid only for a whitelisted fixed/local",
            "result with explicit hypothesis witnesses, scope limitations, a reproducible",
            "reconstruction, and one proof anchor. Words such as standard, classical, or well",
            "known do not create an exemption. Reject any ledger entry involving Weierstrass",
            "preparation, parameter-uniform or degenerating families, topology/monodromy/plumbing,",
            "global Riemann-surface normalization, topological recursion, or an external formula,",
            "sign, coefficient, or normalization.",
            "Treat each verified predecessor's statement as its complete reusable interface.",
            "A stronger coefficient, estimate, side condition, or lemma appearing only in a",
            "predecessor proof is not available to this submission. Bind every predecessor use",
            "to an entailing statement clause; otherwise return `reject` unless the submitted",
            "proof establishes that step independently.",
            "After locating a clause, check every scope restriction and hypothesis stated by that",
            "predecessor against a current witness. Shared terminology is not a transport proof;",
            "any ambient-category change (fixed/family, connected/componentwise, globally",
            "meromorphic/logarithmic atlas, smooth/degenerate, or cover-local/descended) must be",
            "proved explicitly in the submission, or the review must reject it.",
            "Return exactly one JSON object using the hashes supplied by the host spawn contract.",
            "Required keys: `fact_id`, `submission_sha256`, `packet_sha256`, `verdict`,",
            "`critical_errors`, `gaps`, `repair_hints`, and `reviewer`.",
            "Acceptance requires verdict `correct` and both error lists empty.",
            "",
            "## Claim-relation assertion",
            "",
            f"Claim relation: `{submission.get('claim_relation', 'legacy-unspecified')}`",
            "",
            "Assigned research claim:",
            "",
            submission.get("assigned_claim", "")
            or "(No assigned memory claim was hash-bound for this legacy/direct submission.)",
            "",
            "Check that the submitted statement has exactly this logical relation to the assigned",
            "claim. A corrected theorem that does not prove the literal original must be labelled",
            "`replaces` or `weakens`, not `proves`; a counterexample theorem must be `refutes`.",
            "",
            "## Submitted statement",
            "",
            fact.statement,
            "",
            "## Submitted proof",
            "",
            fact.proof,
        ]
        if fact.external_refs:
            lines.extend(
                [
                    "",
                    "## Submission-bound external-source applicability and critical-audit evidence",
                    "",
                    "The certificate metadata is submission-hash-bound. Its `[APP:...]` applicability",
                    "witnesses and `[CRIT:...]` source-reliability findings must also occur in the",
                    "fact-id-hashed proof above.",
                    "",
                    "```json",
                    json.dumps(fact.external_refs, ensure_ascii=False, indent=2),
                    "```",
                ]
            )
        if fact.elementary_uses:
            lines.extend(
                [
                    "",
                    "## Submission-bound controlled elementary-result ledger",
                    "",
                    "Each `[ELM:...]` anchor occurs in the fact-id-hashed proof above. Verify the",
                    "listed hypotheses, reconstruction, used conclusion, and scope limitations.",
                    "The metadata schema is not a mathematical eligibility decision: reject any",
                    "substantive or family/global/transport result disguised as elementary.",
                    "",
                    "```json",
                    json.dumps(fact.elementary_uses, ensure_ascii=False, indent=2),
                    "```",
                ]
            )
        for predecessor in fact.predecessors:
            lines.extend(
                [
                    "",
                    f"## Verified predecessor `{predecessor}`",
                    "",
                    self.get_raw_fact(predecessor),
                ]
            )
        return "\n".join(lines).rstrip() + "\n"

    def freeze_verification_packet(self, fact_id: str) -> dict[str, Any]:
        validate_fact_id(fact_id)
        with self.mutation_lock():
            submission = self.submission(fact_id)
            submission_sha = _submission_digest(submission)
            if submission.get("evidence_version") not in {2, 3}:
                raise ValueError("legacy submission must be resubmitted before hash-bound verification")
            if submission.get("submission_sha256") != submission_sha:
                raise ValueError("submission hash mismatch")
            packet_bytes = self.verification_packet(fact_id).encode("utf-8")
            packet_sha = sha256_bytes(packet_bytes)
            packet_path = self.packet_by_hash_dir / f"{packet_sha}.md"
            self._write_bytes_once(packet_path, packet_bytes)
            review_return_path = self.review_inbox_dir / f"{fact_id}-{packet_sha[:12]}.json"
            manifest = {
                "evidence_version": submission["evidence_version"],
                "fact_id": fact_id,
                "submission_sha256": submission_sha,
                "packet_sha256": packet_sha,
                "packet_relpath": packet_path.relative_to(self.root).as_posix(),
                "review_return_relpath": review_return_path.relative_to(self.root).as_posix(),
            }
            manifest_path = self.packet_by_fact_dir / f"{fact_id}.json"
            if manifest_path.exists():
                existing = self._read_json(manifest_path)
                comparable = {key: existing.get(key) for key in manifest}
                if comparable != manifest:
                    raise ValueError(f"frozen packet manifest collision for {fact_id}")
            else:
                self._write_json_once(
                    manifest_path,
                    {**manifest, "created_at": utc_now()},
                )
            return {
                **manifest,
                "packet_path": str(packet_path),
                "review_return_path": str(review_return_path),
            }

    def freeze_verification_bundle(
        self,
        fact_id: str,
        *,
        authorized_artifacts: list[dict[str, str]] | None = None,
        supersedes_bundle_id: str | None = None,
        prior_review_id: str | None = None,
    ) -> dict[str, Any]:
        """Freeze the only bytes a fresh v4 verifier may inspect.

        A follow-up bundle keeps the submission hash fixed and is permitted only
        after an evidence/source-access or reproducibility finding. Mathematical,
        typing, scope, and source-mismatch findings require a new submission.
        """

        fact_id = validate_fact_id(fact_id)
        with self.mutation_lock():
            submission = self.submission(fact_id)
            if submission.get("evidence_version") != 4:
                raise ValueError("verification bundles require a v4 submission")
            self.profile_closures().require_submission_ready(submission)
            submission_sha = _submission_digest(submission)
            if submission.get("submission_sha256") != submission_sha:
                raise ValueError("submission hash mismatch")
            if submission.get("status") == "accepted":
                raise ValueError("accepted facts cannot receive another verification bundle")
            if submission.get("invalidated_by_revocation"):
                raise ValueError(
                    "submission was invalidated by predecessor revocation; submit a new fact"
                )
            plan = submission.get("verification_plan")
            if not isinstance(plan, dict):
                raise ValueError("v4 submission has no verification plan")

            if supersedes_bundle_id is None:
                if prior_review_id is not None:
                    raise ValueError(
                        "prior_review_id is only valid for a follow-up bundle"
                    )
                bundle_reason = "initial"
            else:
                if prior_review_id is None:
                    raise ValueError(
                        "follow-up bundle requires the rejecting prior review id"
                    )
                prior_review = self.review(prior_review_id)
                VerificationBundleStore.validate_followup_eligibility(prior_review)
                if prior_review["fact_id"] != fact_id:
                    raise ValueError("follow-up review belongs to another fact")
                if prior_review["submission_sha256"] != submission_sha:
                    raise ValueError("follow-up review belongs to another submission")
                if prior_review["bundle_sha256"] != supersedes_bundle_id.removeprefix(
                    "bundle-"
                ):
                    raise ValueError("follow-up bundle does not supersede the reviewed bundle")
                bundle_reason = "evidence_expansion"

            predecessor_statements = {
                predecessor: self.get_fact(predecessor).statement
                for predecessor in submission.get("predecessors", [])
            }
            interfaces = {
                predecessor: self.statement_interface(predecessor)
                for predecessor in submission.get("predecessors", [])
            }
            if authorized_artifacts is None:
                allowed_roles = set(plan.get("authorized_artifact_roles", []))
                authorized_artifacts = sorted(
                    [
                        {
                            "key": evidence["key"],
                            "role": artifact["role"],
                        }
                        for evidence in submission.get(
                            "computational_evidence", []
                        )
                        for artifact in evidence.get("artifact_refs", [])
                        if artifact.get("role") in allowed_roles
                    ],
                    key=lambda item: (item["key"], item["role"]),
                )
            bundle = self.verification_bundles().create(
                submission=submission,
                predecessor_statements=predecessor_statements,
                interfaces=interfaces,
                verification_plan=plan,
                authorized_artifacts=authorized_artifacts,
                supersedes_bundle_id=supersedes_bundle_id,
                bundle_reason=bundle_reason,
                _creation_authority=(
                    self._verification_bundle_creation_authority
                ),
            )
            review_return_path = (
                self.review_inbox_dir
                / f"{fact_id}-{bundle['bundle_sha256'][:12]}.v4.json"
            )
            return {
                **bundle,
                "review_return_path": str(review_return_path),
                "capability": self.verification_bundles().capability(
                    bundle_sha256=bundle["bundle_sha256"],
                    review_return_path=review_return_path,
                ),
            }

    def packet_manifest(self, fact_id: str) -> dict[str, Any]:
        path = self.packet_by_fact_dir / f"{validate_fact_id(fact_id)}.json"
        if not path.exists():
            raise KeyError(f"no frozen packet for {fact_id}")
        return self._read_json(path)

    @staticmethod
    def _validate_reviewer(value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("reviewer must be a nonempty string")
        if any(ord(character) < 32 for character in value):
            raise ValueError("reviewer contains control characters")
        return value.strip()

    @staticmethod
    def _validate_actor(value: Any, label: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{label} must be a nonempty string")
        if any(ord(character) < 32 for character in value):
            raise ValueError(f"{label} contains control characters")
        return value.strip()

    def _validate_review_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        require_exact_keys(
            payload,
            required=_REVIEW_INPUT_FIELDS
            | {"review_id", "reviewed_at", "record_sha256"},
            label="stored review",
        )
        fact_id = validate_fact_id(require_string(payload, "fact_id"))
        submission_sha = require_string(payload, "submission_sha256")
        packet_sha = require_string(payload, "packet_sha256")
        review_id = validate_review_id(require_string(payload, "review_id"))
        if SHA256_RE.fullmatch(submission_sha) is None or SHA256_RE.fullmatch(packet_sha) is None:
            raise ValueError("review hashes must be full lowercase SHA-256 values")
        verdict = require_string(payload, "verdict")
        if verdict not in {"correct", "reject"}:
            raise ValueError("review verdict must be 'correct' or 'reject'")
        errors = require_string_list(payload, "critical_errors")
        gaps = require_string_list(payload, "gaps")
        hints = require_string_list(payload, "repair_hints")
        reviewer = self._validate_reviewer(payload.get("reviewer"))
        reviewed_at = require_string(payload, "reviewed_at")
        record_sha = require_string(payload, "record_sha256")
        semantic = {
            "fact_id": fact_id,
            "submission_sha256": submission_sha,
            "packet_sha256": packet_sha,
            "verdict": verdict,
            "critical_errors": errors,
            "gaps": gaps,
            "repair_hints": hints,
            "reviewer": reviewer,
        }
        if sha256_json(semantic) != review_id:
            raise ValueError("stored review_id does not match review content")
        if record_sha != sha256_json({**semantic, "reviewed_at": reviewed_at}):
            raise ValueError("stored review record hash mismatch")
        if verdict == "correct" and (errors or gaps):
            raise ValueError("a correct verdict cannot contain critical errors or gaps")
        if verdict == "reject" and not (errors or gaps):
            raise ValueError("a rejecting verdict must identify a critical error or gap")
        return {
            **semantic,
            "review_id": review_id,
            "reviewed_at": reviewed_at,
            "record_sha256": record_sha,
        }

    @staticmethod
    def _validate_v4_review_record(payload: dict[str, Any]) -> dict[str, Any]:
        validate_review_v4(payload)
        review_id = require_string(payload, "review_id")
        if SHA256_RE.fullmatch(review_id) is None:
            raise ValueError("stored v4 review id is invalid")
        require_string(payload, "reviewed_at")
        record_sha = require_string(payload, "record_sha256")
        if SHA256_RE.fullmatch(record_sha) is None:
            raise ValueError("stored v4 review record hash is invalid")
        return payload

    def _prior_v4_reviews(
        self,
        submission: dict[str, Any],
        *,
        exclude_review_id: str | None = None,
    ) -> list[dict[str, Any]]:
        review_ids = submission.get("review_ids", [])
        if not isinstance(review_ids, list) or any(
            not isinstance(item, str) for item in review_ids
        ):
            raise ValueError("submission review_ids is invalid")
        result: list[dict[str, Any]] = []
        for review_id in review_ids:
            if review_id == exclude_review_id:
                continue
            review = self.review(review_id)
            if review.get("schema_version") != 4:
                raise ValueError("v4 submission references a non-v4 review")
            if (
                review["fact_id"] != submission["fact_id"]
                or review["submission_sha256"]
                != submission["submission_sha256"]
            ):
                raise ValueError("v4 submission review lineage mismatch")
            result.append(review)
        return result

    def _record_review_v4(self, payload: dict[str, Any]) -> Path:
        if any(key in payload for key in ("review_id", "reviewed_at", "record_sha256")):
            raise ValueError("v4 review input must not contain stored-record fields")
        validate_review_v4(payload)
        fact_id = payload["fact_id"]
        submission = self.submission(fact_id)
        if submission.get("evidence_version") != 4:
            raise ValueError("v4 review requires a v4 submission")
        self.profile_closures().require_submission_ready(submission)
        if submission.get("status") == "accepted":
            raise ValueError("accepted facts cannot be re-reviewed; use revoke for a challenge")
        if submission.get("invalidated_by_revocation"):
            raise ValueError(
                "submission was invalidated by predecessor revocation; submit a new fact"
            )
        submission_sha = _submission_digest(submission)
        if (
            submission.get("submission_sha256") != submission_sha
            or payload["submission_sha256"] != submission_sha
        ):
            raise ValueError("v4 review does not match the frozen submission")
        manifest = self.verification_bundles().verify(payload["bundle_sha256"])
        if (
            manifest["fact_id"] != fact_id
            or manifest["submission_sha256"] != submission_sha
        ):
            raise ValueError("v4 review bundle does not match the submission")
        reviewer = self._validate_reviewer(payload.get("reviewer"))
        worker = require_string(submission, "worker")
        if reviewer.casefold() == worker.strip().casefold():
            raise ValueError("reviewer must be independent of the submitting worker")

        semantic_keys = (
            "schema_version",
            "policy_revision",
            "fact_id",
            "submission_sha256",
            "bundle_sha256",
            "verdict",
            "findings",
            "prior_review_dispositions",
            "reviewer",
            "host_attestation",
        )
        semantic = {key: payload[key] for key in semantic_keys}
        review_id = sha256_json(semantic)
        prior_reviews = self._prior_v4_reviews(submission)
        if payload["verdict"] == "correct":
            admission_gate_v4(
                review={**semantic, "review_id": review_id},
                bundle_store=self.verification_bundles(),
                prior_reviews=prior_reviews,
            )
        else:
            known_prior_findings = {
                (prior["review_id"], finding["id"])
                for prior in prior_reviews
                for finding in prior["findings"]
            }
            supplied = {
                (item["prior_review_id"], item["finding_id"])
                for item in payload["prior_review_dispositions"]
            }
            if not supplied.issubset(known_prior_findings):
                raise ValueError("v4 review dispositions reference unknown prior findings")

        reviewed_at = utc_now()
        normalized = {
            **semantic,
            "review_id": review_id,
            "reviewed_at": reviewed_at,
            "record_sha256": sha256_json(
                {**semantic, "reviewed_at": reviewed_at}
            ),
        }
        path = self.review_path(review_id)
        if path.exists():
            existing = self._validate_v4_review_record(self._read_json(path))
            existing_semantic = {
                key: existing[key] for key in semantic_keys
            }
            if existing_semantic != semantic:
                raise ValueError(f"review id collision at {path}")
        else:
            self._write_json_once(path, normalized)
        review_ids = submission.get("review_ids", [])
        if review_id not in review_ids:
            review_ids = [*review_ids, review_id]
        submission["review_ids"] = review_ids
        submission["last_review_id"] = review_id
        submission["last_bundle_sha256"] = payload["bundle_sha256"]
        submission["status"] = (
            "rejected" if payload["verdict"] == "reject" else "pending_review"
        )
        self._write_json_atomic(self.submission_path(fact_id), submission)
        if payload["verdict"] == "reject":
            task_id = submission.get("task_id", "")
            if isinstance(task_id, str) and MEMORY_ID_RE.fullmatch(task_id):
                self.memory_update(
                    task_id,
                    status="challenged",
                    actor="gateway",
                    note=f"review {review_id} rejected submission {fact_id}",
                    event_id=_json_hash(["review-reject", review_id], 24),
                )
        return path

    def record_review(self, payload: dict[str, Any]) -> Path:
        if self.workflow_evidence_version() == V5_WORKFLOW_EVIDENCE_VERSION:
            raise ValueError(
                "legacy record-review cannot write V5; use Certification Decision"
            )
        with self.mutation_lock():
            if payload.get("schema_version") == 4:
                return self._record_review_v4(payload)
            require_exact_keys(payload, required=_REVIEW_INPUT_FIELDS, label="review")
            fact_id = validate_fact_id(require_string(payload, "fact_id"))
            submission_sha = require_string(payload, "submission_sha256")
            packet_sha = require_string(payload, "packet_sha256")
            if SHA256_RE.fullmatch(submission_sha) is None or SHA256_RE.fullmatch(packet_sha) is None:
                raise ValueError("review hashes must be full lowercase SHA-256 values")
            verdict = require_string(payload, "verdict")
            if verdict not in {"correct", "reject"}:
                raise ValueError("review verdict must be 'correct' or 'reject'")
            errors = require_string_list(payload, "critical_errors")
            gaps = require_string_list(payload, "gaps")
            hints = require_string_list(payload, "repair_hints")
            reviewer = self._validate_reviewer(payload.get("reviewer"))
            if verdict == "correct" and (errors or gaps):
                raise ValueError("a correct verdict cannot contain critical errors or gaps")
            if verdict == "reject" and not (errors or gaps):
                raise ValueError("a rejecting verdict must identify a critical error or gap")
            submission = self.submission(fact_id)
            if submission.get("status") == "accepted":
                raise ValueError("accepted facts cannot be re-reviewed; use revoke for a challenge")
            if submission.get("invalidated_by_revocation"):
                raise ValueError(
                    "submission was invalidated by predecessor revocation; submit a new fact"
                )
            if submission.get("evidence_version") not in {2, 3}:
                raise ValueError(
                    "legacy submission must be resubmitted before hash-bound review"
                )
            if submission.get("submission_sha256") != submission_sha:
                raise ValueError("review does not match the frozen submission")
            if _submission_digest(submission) != submission_sha:
                raise ValueError("current submission bytes do not match their recorded hash")
            manifest = self.packet_manifest(fact_id)
            if manifest.get("submission_sha256") != submission_sha:
                raise ValueError("packet manifest does not match the submission")
            if manifest.get("packet_sha256") != packet_sha:
                raise ValueError("review does not match the frozen packet")
            packet_path = contained_path(
                self.root,
                require_string(manifest, "packet_relpath"),
                "packet_relpath",
            )
            if not packet_path.is_file() or packet_path.is_symlink():
                raise ValueError("frozen packet is missing or not a regular file")
            if sha256_bytes(packet_path.read_bytes()) != packet_sha:
                raise ValueError("frozen packet hash mismatch")
            worker = submission.get("worker")
            if not isinstance(worker, str) or reviewer.casefold() == worker.strip().casefold():
                raise ValueError("reviewer must be independent of the submitting worker")
            semantic = {
                "fact_id": fact_id,
                "submission_sha256": submission_sha,
                "packet_sha256": packet_sha,
                "verdict": verdict,
                "critical_errors": errors,
                "gaps": gaps,
                "repair_hints": hints,
                "reviewer": reviewer,
            }
            review_id = sha256_json(semantic)
            reviewed_at = utc_now()
            normalized = {
                **semantic,
                "review_id": review_id,
                "reviewed_at": reviewed_at,
                "record_sha256": sha256_json({**semantic, "reviewed_at": reviewed_at}),
            }
            path = self.review_path(review_id)
            if path.exists():
                existing = self._validate_review_record(self._read_json(path))
                if _review_semantic_payload(existing) != semantic:
                    raise ValueError(f"review id collision at {path}")
            else:
                self._write_json_once(path, normalized)
            review_ids = submission.get("review_ids", [])
            if not isinstance(review_ids, list) or any(not isinstance(item, str) for item in review_ids):
                raise ValueError("submission review_ids is invalid")
            if review_id not in review_ids:
                review_ids = [*review_ids, review_id]
            submission["review_ids"] = review_ids
            submission["last_review_id"] = review_id
            submission["status"] = "rejected" if verdict == "reject" else "pending_review"
            self._write_json_atomic(self.submission_path(fact_id), submission)
            if verdict == "reject":
                task_id = submission.get("task_id", "")
                if isinstance(task_id, str) and MEMORY_ID_RE.fullmatch(task_id):
                    self.memory_update(
                        task_id,
                        status="challenged",
                        actor="gateway",
                        note=f"review {review_id} rejected submission {fact_id}",
                        event_id=_json_hash(["review-reject", review_id], 24),
                    )
            return path

    def review(self, review_id: str) -> dict[str, Any]:
        path = self.review_path(review_id)
        if not path.exists():
            raise KeyError(f"unknown review: {review_id}")
        payload = self._read_json(path)
        if payload.get("schema_version") == 4:
            return self._validate_v4_review_record(payload)
        return self._validate_review_record(payload)

    def _admit_v4(
        self,
        *,
        fact_id: str,
        review_id: str,
        gateway: str,
        submission: dict[str, Any],
    ) -> str:
        path = self.fact_path(fact_id)
        if (self.revoked_dir / f"{fact_id}.md").exists():
            raise ValueError(
                f"fact {fact_id} was revoked and cannot be re-admitted from a stale submission"
            )
        profile_closure = self.profile_closures().require_submission_ready(
            submission
        )
        status = submission.get("status")
        if status == "accepted":
            if submission.get("accepted_review_id") != review_id or not path.exists():
                raise ValueError("submission was already accepted with different evidence")
            return fact_id
        if status != "pending_review":
            raise ValueError("submission is not pending a clean review")
        if submission.get("last_review_id") != review_id:
            raise ValueError("admission requires the latest recorded review")
        review = self.review(review_id)
        if review.get("schema_version") != 4 or review["fact_id"] != fact_id:
            raise ValueError("v4 review does not belong to this fact")
        submission_sha = _submission_digest(submission)
        if (
            submission.get("submission_sha256") != submission_sha
            or review["submission_sha256"] != submission_sha
        ):
            raise ValueError("review is not bound to the current v4 submission")
        prior_reviews = self._prior_v4_reviews(
            submission,
            exclude_review_id=review_id,
        )
        admission_gate_v4(
            review=review,
            bundle_store=self.verification_bundles(),
            prior_reviews=prior_reviews,
        )
        manifest = self.verification_bundles().verify(review["bundle_sha256"])
        if (
            manifest["fact_id"] != fact_id
            or manifest["submission_sha256"] != submission_sha
        ):
            raise ValueError("admission bundle is not bound to the current submission")
        worker = require_string(submission, "worker")
        if review["reviewer"].casefold() == worker.strip().casefold():
            raise ValueError("submitting worker cannot verify its own fact")
        fact = Fact.from_dict(submission)
        errors = fact.validate()
        if errors:
            raise ValueError("; ".join(errors))
        if fact.problem_id != self.project_id():
            raise ValueError("submission belongs to another project")
        self._validate_predecessors(fact.predecessors)
        rendered = validate_fact_round_trip(fact).encode("utf-8")
        self._write_bytes_once(path, rendered, mode=0o644)
        fact_sha = sha256_bytes(rendered)
        submission["status"] = "accepted"
        submission["accepted_review_id"] = review_id
        submission["accepted_bundle_sha256"] = review["bundle_sha256"]
        submission["accepted_at"] = utc_now()
        self._write_json_atomic(self.submission_path(fact_id), submission)
        profile_closure_sha256 = profile_closure.get("receipt_sha256")
        event_id = sha256_json(
            [
                "accepted-v4",
                fact_id,
                review_id,
                review["bundle_sha256"],
                *(
                    ["profile-closure", profile_closure_sha256]
                    if isinstance(profile_closure_sha256, str)
                    else []
                ),
            ]
        )
        event = {
            "schema_version": 4,
            "policy_revision": POLICY_REVISION_V4,
            "evidence_version": 4,
            "event": "accepted",
            "event_id": event_id,
            "fact_id": fact_id,
            "gateway": gateway,
            "review_id": review_id,
            "reviewer": review["reviewer"],
            "submission_sha256": submission_sha,
            "bundle_sha256": review["bundle_sha256"],
            "fact_sha256": fact_sha,
            "claim_relation": submission.get(
                "claim_relation", "legacy-unspecified"
            ),
            "assigned_claim_sha256": sha256_bytes(
                str(submission.get("assigned_claim", "")).encode("utf-8")
            ),
            **(
                {
                    "profile_closure_id": profile_closure["closure_id"],
                    "profile_closure_sha256": profile_closure_sha256,
                }
                if isinstance(profile_closure_sha256, str)
                else {}
            ),
            "timestamp": utc_now(),
        }
        self._append_jsonl_once(self.verification_log, event, event_id=event_id)
        interface = build_statement_interface(
            fact=fact,
            stored_fact_sha256=fact_sha,
            acceptance_event_sha256=event_id,
            admission_review_id=review_id,
            workflow_evidence_version=4,
        )
        write_interface_once(
            self.interfaces_dir / f"{fact_id}.json",
            interface,
        )
        task_id = submission.get("task_id", "")
        if isinstance(task_id, str) and MEMORY_ID_RE.fullmatch(task_id):
            claim_relation = str(submission.get("claim_relation", "proves"))
            status_by_relation = {
                "proves": "resolved_by_fact",
                "strengthens": "resolved_by_fact",
                "refutes": "refuted_by_fact",
                "replaces": "replaced_by_fact",
                "weakens": "challenged",
                "unrelated": "open",
            }
            self.memory_update(
                task_id,
                status=status_by_relation[claim_relation],
                actor="gateway",
                note=f"admitted as fact {fact_id} with relation {claim_relation}",
                resolution_fact_id=(
                    fact_id
                    if claim_relation
                    in {"proves", "strengthens", "refutes", "replaces"}
                    else None
                ),
                claim_relation=claim_relation,
                related_fact_id=fact_id,
                event_id=_json_hash(
                    ["memory-resolve", task_id, fact_id, claim_relation], 24
                ),
            )
        return fact_id

    def admit(
        self,
        fact_id: str,
        *,
        review_id: str,
        gateway: str = "local-gateway",
    ) -> str:
        validate_fact_id(fact_id)
        validate_review_id(review_id)
        gateway = self._validate_actor(gateway, "gateway")
        if self.workflow_evidence_version() == V5_WORKFLOW_EVIDENCE_VERSION:
            raise ValueError(
                "legacy admit cannot write V5; use the V5 admission gateway"
            )
        with self.mutation_lock():
            submission = self.submission(fact_id)
            if submission.get("evidence_version") == 4:
                return self._admit_v4(
                    fact_id=fact_id,
                    review_id=review_id,
                    gateway=gateway,
                    submission=submission,
                )
            path = self.fact_path(fact_id)
            if (self.revoked_dir / f"{fact_id}.md").exists():
                raise ValueError(
                    f"fact {fact_id} was revoked and cannot be re-admitted from a stale submission"
                )
            status = submission.get("status")
            if status == "accepted":
                if submission.get("accepted_review_id") != review_id or not path.exists():
                    raise ValueError("submission was already accepted with different evidence")
            elif status != "pending_review":
                raise ValueError("submission is not pending a clean review")
            if submission.get("last_review_id") != review_id:
                raise ValueError("admission requires the latest recorded review")
            review = self.review(review_id)
            if review["fact_id"] != fact_id:
                raise ValueError("review does not belong to this fact")
            if review["verdict"] != "correct":
                raise ValueError(f"review did not accept {fact_id}")
            if review["critical_errors"] or review["gaps"]:
                raise ValueError(f"review for {fact_id} contains unresolved errors or gaps")
            submission_sha = _submission_digest(submission)
            if submission.get("submission_sha256") != submission_sha:
                raise ValueError("submission hash mismatch")
            if review["submission_sha256"] != submission_sha:
                raise ValueError("review is not bound to the current submission")
            manifest = self.packet_manifest(fact_id)
            if manifest.get("packet_sha256") != review["packet_sha256"]:
                raise ValueError("review is not bound to the current frozen packet")
            packet_path = contained_path(
                self.root,
                require_string(manifest, "packet_relpath"),
                "packet_relpath",
            )
            if sha256_bytes(packet_path.read_bytes()) != review["packet_sha256"]:
                raise ValueError("frozen packet hash mismatch")
            worker = require_string(submission, "worker")
            if review["reviewer"].casefold() == worker.strip().casefold():
                raise ValueError("submitting worker cannot verify its own fact")
            fact = Fact.from_dict(submission)
            errors = fact.validate()
            if errors:
                raise ValueError("; ".join(errors))
            if fact.problem_id != self.project_id():
                raise ValueError("submission belongs to another project")
            self._validate_predecessors(fact.predecessors)
            rendered = validate_fact_round_trip(fact).encode("utf-8")
            self._write_bytes_once(path, rendered, mode=0o644)
            fact_sha = sha256_bytes(rendered)
            submission["status"] = "accepted"
            submission["accepted_review_id"] = review_id
            submission["accepted_at"] = utc_now()
            self._write_json_atomic(self.submission_path(fact_id), submission)
            event_id = sha256_json(["accepted", fact_id, review_id])
            event = {
                "evidence_version": submission["evidence_version"],
                "event": "accepted",
                "event_id": event_id,
                "fact_id": fact_id,
                "gateway": gateway,
                "review_id": review_id,
                "reviewer": review["reviewer"],
                "submission_sha256": submission_sha,
                "packet_sha256": review["packet_sha256"],
                "fact_sha256": fact_sha,
                "claim_relation": submission.get("claim_relation", "legacy-unspecified"),
                "assigned_claim_sha256": sha256_bytes(
                    str(submission.get("assigned_claim", "")).encode("utf-8")
                ),
                "timestamp": utc_now(),
            }
            self._append_jsonl_once(self.verification_log, event, event_id=event_id)
            task_id = submission.get("task_id", "")
            if isinstance(task_id, str) and MEMORY_ID_RE.fullmatch(task_id):
                claim_relation = str(submission.get("claim_relation", "proves"))
                status_by_relation = {
                    "proves": "resolved_by_fact",
                    "strengthens": "resolved_by_fact",
                    "refutes": "refuted_by_fact",
                    "replaces": "replaced_by_fact",
                    "weakens": "challenged",
                    "unrelated": "open",
                }
                self.memory_update(
                    task_id,
                    status=status_by_relation[claim_relation],
                    actor="gateway",
                    note=f"admitted as fact {fact_id} with relation {claim_relation}",
                    resolution_fact_id=(
                        fact_id
                        if claim_relation
                        in {"proves", "strengthens", "refutes", "replaces"}
                        else None
                    ),
                    claim_relation=claim_relation,
                    related_fact_id=fact_id,
                    event_id=_json_hash(
                        ["memory-resolve", task_id, fact_id, claim_relation], 24
                    ),
                )
            return fact_id

    def add_fact_metadata(self, fact_id: str, **metadata: Any) -> None:
        with self.mutation_lock():
            if fact_id not in set(self.fact_ids()):
                raise KeyError(f"unknown verified fact: {fact_id}")
            event = {"fact_id": fact_id, "timestamp": utc_now(), **metadata}
            event_id = str(event.get("event_id") or _json_hash(event, 24))
            event["event_id"] = event_id
            self._append_jsonl_once(self.metadata_log, event, event_id=event_id)

    def fact_metadata(self) -> dict[str, dict[str, Any]]:
        latest: dict[str, dict[str, Any]] = {}
        for event in self._read_jsonl(self.metadata_log):
            fact_id = str(event.get("fact_id", ""))
            if fact_id:
                latest.setdefault(fact_id, {}).update(event)
        return latest

    def revoke(self, fact_id: str, *, reason: str, actor: str) -> list[str]:
        validate_fact_id(fact_id)
        reason = self._validate_actor(reason, "revocation reason")
        actor = self._validate_actor(actor, "revocation actor")
        if self.workflow_evidence_version() == V5_WORKFLOW_EVIDENCE_VERSION:
            raise ValueError(
                "legacy revoke cannot write V5; use the V5 revocation adapter"
            )
        with self.mutation_lock():
            facts = self.facts()
            if fact_id not in facts:
                raise KeyError(f"unknown verified fact: {fact_id}")
            graph = DependencyGraph(facts)
            revoked = [fact_id] + sorted(graph.descendants([fact_id]))
            self.revoked_dir.mkdir(parents=True, exist_ok=True)
            for current in revoked:
                source = self.fact_path(current)
                if source.exists():
                    destination = self.revoked_dir / source.name
                    if destination.exists():
                        raise ValueError(f"revoked fact collision at {destination}")
                    os.replace(source, destination)
                event_id = sha256_json(["revoked", current, fact_id, reason])
                self._append_jsonl_once(
                    self.revocation_log,
                    {
                        "event_id": event_id,
                        "fact_id": current,
                        "root_fact_id": fact_id,
                        "reason": reason,
                        "actor": actor,
                        "timestamp": utc_now(),
                    },
                    event_id=event_id,
                )
                submission_path = self.submission_path(current)
                if submission_path.exists():
                    submission = self._read_json(submission_path)
                    if submission.get("evidence_version") in {2, 3, 4}:
                        submission["status"] = "revoked"
                        submission["revoked_at"] = utc_now()
                        submission["revocation_reason"] = reason
                        self._write_json_atomic(submission_path, submission)
            revoked_set = set(revoked)
            for submission_path in self.submissions_dir.glob("*.json"):
                submission = self._read_json(submission_path)
                if (
                    submission.get("evidence_version") in {2, 3, 4}
                    and submission.get("status") == "pending_review"
                ):
                    invalidated = sorted(
                        revoked_set.intersection(submission.get("predecessors", []))
                    )
                    if invalidated:
                        submission["status"] = "rejected"
                        submission["invalidated_by_revocation"] = invalidated
                        submission["invalidated_at"] = utc_now()
                        self._write_json_atomic(submission_path, submission)
            if self.workflow_evidence_version() >= 4:
                campaigns = self.campaigns()
                campaign_id = campaigns.active()
                if campaign_id is not None:
                    status = campaigns.status(campaign_id)
                    for target_id, target in status["targets"].items():
                        if (
                            target["status"] == "active"
                            and target["role"]
                            in {"headline_proof", "supporting_proof"}
                            and target["subject_id"] in revoked_set
                        ):
                            campaigns.target_archive(
                                campaign_id,
                                target_id,
                                reason=(
                                    "Target fact was cascade-revoked from "
                                    f"{fact_id}."
                                ),
                                actor=actor,
                            )
                    self.sync_active_campaign_targets(
                        campaign_id=campaign_id
                    )
            else:
                surviving_targets = [
                    target
                    for target in self.targets()
                    if target not in revoked
                ]
                self.set_targets(surviving_targets)
            for memory_id, entry in self.memory_latest().items():
                resolution_was_revoked = entry.get("resolution_fact_id") in revoked_set
                relation_was_revoked = entry.get("related_fact_id") in revoked_set
                if resolution_was_revoked or relation_was_revoked:
                    current_status = entry.get("status")
                    reopened_status = (
                        "challenged"
                        if resolution_was_revoked or current_status not in MEMORY_STATUSES
                        else str(current_status)
                    )
                    self.memory_update(
                        memory_id,
                        status=reopened_status,
                        actor=actor,
                        note=(
                            "resolving fact was revoked"
                            if resolution_was_revoked
                            else "related fact was revoked"
                        ),
                        event_id=_json_hash(["memory-reopen", memory_id, fact_id], 24),
                    )
            return revoked

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        fact_ids = self.fact_ids()
        raw = [self.get_raw_fact(fact_id) for fact_id in fact_ids]
        scores = bm25(query, raw)
        ranked = sorted(zip(fact_ids, raw, scores), key=lambda item: (-item[2], item[0]))
        return [
            {
                "fact_id": fact_id,
                "score": round(score, 6),
                "statement": statement_snippet(text),
            }
            for fact_id, text, score in ranked[:limit]
            if score > 0
        ]

    def closure(self, target_ids: list[str]) -> list[str]:
        target_ids = [validate_fact_id(item) for item in target_ids]
        graph = DependencyGraph(self.facts())
        selected = graph.closure(target_ids)
        return graph.topological_order(selected)

    def bounded_context(self, fact_id: str, max_nodes: int = 20) -> str:
        validate_fact_id(fact_id)
        if max_nodes < 1:
            raise ValueError("max_nodes must be positive")
        facts = self.facts()
        graph = DependencyGraph(facts)
        if fact_id not in facts:
            raise KeyError(f"unknown verified fact: {fact_id}")
        selected: set[str] = set()
        queue = [fact_id]
        while queue and len(selected) < max_nodes:
            current = queue.pop(0)
            if current in selected:
                continue
            selected.add(current)
            queue.extend(graph.predecessors[current])
        order = graph.topological_order(selected)
        lines = [f"# Bounded verified context for `{fact_id}`", ""]
        for current in order:
            lines.extend([f"## Fact `{current}`", "", self.get_raw_fact(current)])
        omitted = len(graph.closure([fact_id])) - len(selected)
        if omitted > 0:
            lines.extend(["", f"> Context limit omitted {omitted} deeper predecessor facts."])
        return "\n".join(lines).rstrip() + "\n"

    def scoped_glossary_conflicts(self, fact_ids: list[str]) -> dict[str, dict[str, list[str]]]:
        definitions: dict[str, dict[str, list[str]]] = {}
        for fact_id in fact_ids:
            fact = self.get_fact(fact_id)
            for symbol, definition in fact.glossary_introduces.items():
                definitions.setdefault(symbol, {}).setdefault(definition, []).append(fact_id)
        return {
            symbol: variants for symbol, variants in definitions.items() if len(variants) > 1
        }

    def memory_add(
        self,
        payload: dict[str, Any],
        *,
        actor: str,
        entry_id: str | None = None,
    ) -> str:
        with self.mutation_lock():
            is_v4 = self.workflow_evidence_version() >= 4
            actor = self._validate_actor(actor, "memory actor")
            if "id" in payload:
                raise ValueError("memory ids are generated internally")
            kind = payload.get("kind", "direction")
            if not isinstance(kind, str):
                raise ValueError("memory kind must be a string")
            if kind not in MEMORY_KINDS:
                raise ValueError(f"unsupported memory kind: {kind}")
            status = payload.get("status", "open")
            if not isinstance(status, str):
                raise ValueError("memory status must be a string")
            if status not in MEMORY_STATUSES:
                raise ValueError(f"unsupported memory status: {status}")
            claim_value = payload.get("claim", "")
            if not isinstance(claim_value, str):
                raise ValueError("memory claim must be a string")
            claim = claim_value.strip()
            if not claim:
                raise ValueError("memory entry requires a nonempty claim")
            if entry_id is None:
                entry_id = _json_hash({"kind": kind, "claim": claim}, 12)
            validate_memory_id(entry_id)
            dependencies_value = payload.get("dependencies", [])
            if not isinstance(dependencies_value, list) or any(
                not isinstance(item, str) for item in dependencies_value
            ):
                raise ValueError("memory dependencies must be a list of fact ids")
            dependencies = [validate_fact_id(item) for item in dependencies_value]
            active_fact_ids = set(self.fact_ids())
            unknown = [
                item for item in dependencies if item not in active_fact_ids
            ]
            if unknown:
                raise ValueError(
                    "memory dependencies are not verified facts: " + ", ".join(unknown)
                )
            resolution = payload.get("resolution_fact_id")
            if status in _STATUS_RELATIONS:
                if not isinstance(resolution, str):
                    raise ValueError(f"{status} requires resolution_fact_id")
                resolution = validate_fact_id(resolution)
                self.get_fact(resolution)
            elif resolution is not None:
                raise ValueError("resolution_fact_id is only valid for fact-resolved statuses")
            claim_relation = payload.get("claim_relation")
            related_fact_id = payload.get("related_fact_id")
            if claim_relation is not None:
                if not isinstance(claim_relation, str) or claim_relation not in CLAIM_RELATIONS:
                    raise ValueError("memory claim_relation is invalid")
                if not isinstance(related_fact_id, str):
                    raise ValueError("memory claim_relation requires related_fact_id")
                related_fact_id = validate_fact_id(related_fact_id)
                self.get_fact(related_fact_id)
            elif related_fact_id is not None:
                raise ValueError("related_fact_id requires claim_relation")
            if status in _STATUS_RELATIONS:
                allowed = _STATUS_RELATIONS[status]
                claim_relation = claim_relation or sorted(allowed)[0]
                related_fact_id = related_fact_id or resolution
                if claim_relation not in allowed or related_fact_id != resolution:
                    raise ValueError(f"{status} has an incompatible claim_relation")
            for field in (
                "parent_memory_id",
                "repair_of_memory_id",
                "trigger_memory_id",
            ):
                value = payload.get(field)
                if value in {None, ""}:
                    continue
                if not isinstance(value, str):
                    raise ValueError(f"memory {field} must be a memory id")
                value = validate_memory_id(value)
                if value not in self.memory_latest():
                    raise ValueError(f"memory {field} is unknown: {value}")
            for field in ("rationale", "source"):
                if not isinstance(payload.get(field, ""), str):
                    raise ValueError(f"memory {field} must be a string")
            for field in ("suggested_actions", "tags"):
                values = payload.get(field, [])
                if not isinstance(values, list) or any(
                    not isinstance(item, str) for item in values
                ):
                    raise ValueError(f"memory {field} must be a list of strings")
            metrics: dict[str, float] = {}
            decision_profile: dict[str, float] | None = None
            if is_v4:
                raw_supplied = LEGACY_V4_SCORE_FIELDS.intersection(payload)
                supplied_profile = payload.get("decision_profile")
                if supplied_profile is not None and raw_supplied:
                    raise ValueError(
                        "memory cannot mix decision_profile with legacy eight-metric input"
                    )
                if supplied_profile is not None:
                    decision_profile = validate_decision_profile(supplied_profile)
                elif raw_supplied:
                    for field in LEGACY_V4_SCORE_FIELDS:
                        value = payload.get(field, 0.5)
                        if isinstance(value, bool) or not isinstance(
                            value, (int, float)
                        ):
                            raise ValueError(
                                f"memory {field} must be a number from 0 to 1"
                            )
                        number = float(value)
                        if not math.isfinite(number) or not 0.0 <= number <= 1.0:
                            raise ValueError(
                                f"memory {field} must be a number from 0 to 1"
                            )
                        metrics[field] = number
                    decision_profile = project_legacy_decision_profile(metrics)
                else:
                    decision_profile = {
                        "burden": 0.5,
                        "impact": 0.5,
                        "information_value": 0.5,
                        "tractability": 0.5,
                    }
            else:
                for field in ("priority", "novelty", "testability", "risk"):
                    value = payload.get(field, 0.5)
                    if isinstance(value, bool) or not isinstance(value, (int, float)):
                        raise ValueError(
                            f"memory {field} must be a number from 0 to 1"
                        )
                    number = float(value)
                    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
                        raise ValueError(
                            f"memory {field} must be a number from 0 to 1"
                        )
                    metrics[field] = number
            v4_fields: dict[str, Any] = {}
            if is_v4:
                stop_conditions = payload.get("stop_conditions", [])
                if not isinstance(stop_conditions, list) or any(
                    not isinstance(item, str) for item in stop_conditions
                ):
                    raise ValueError("memory stop_conditions must be strings")
                user_value_note = payload.get("user_value_note", "")
                if not isinstance(user_value_note, str):
                    raise ValueError("memory user_value_note must be a string")
                killed_by_fact = payload.get("killed_by_fact")
                if killed_by_fact is not None:
                    if actor not in {"main", "operator"}:
                        raise ValueError(
                            "only main or operator may set killed_by_fact"
                        )
                    killed_by_fact = validate_fact_id(killed_by_fact)
                    self.get_fact(killed_by_fact)
                campaign_id = payload.get("campaign_id")
                campaign_status: dict[str, Any] | None = None
                if campaign_id is None:
                    campaign_id = self.campaigns().active()
                if campaign_id is not None:
                    campaign_id = validate_campaign_id(campaign_id)
                    campaign_status = self.campaigns().status(campaign_id)
                source_claim_id = payload.get("source_claim_id")
                if source_claim_id is not None:
                    source_claim_id = validate_claim_id(source_claim_id)
                    self.claims().show_claim(source_claim_id)
                goal_relation = payload.get("goal_relation", "proves")
                if goal_relation not in CLAIM_RELATIONS:
                    raise ValueError("memory goal_relation is invalid")
                campaign_source_claim_ids = (
                    set(campaign_status.get("source_claim_ids", []))
                    if campaign_status is not None
                    else set()
                )
                if (
                    goal_relation == "refutes"
                    and campaign_source_claim_ids
                    and source_claim_id is None
                ):
                    raise ValueError(
                        "refuting a published campaign claim requires "
                        "source_claim_id"
                    )
                if (
                    source_claim_id is not None
                    and campaign_source_claim_ids
                    and source_claim_id not in campaign_source_claim_ids
                ):
                    raise ValueError(
                        "memory source_claim_id is not bound to the campaign"
                    )
                convention_ids = payload.get("convention_profile_ids", [])
                if not isinstance(convention_ids, list) or any(
                    not isinstance(item, str) for item in convention_ids
                ):
                    raise ValueError(
                        "memory convention_profile_ids must be strings"
                    )
                for convention_id in convention_ids:
                    self.claims().show_convention(convention_id)
                obligations = payload.get("obligations", [])
                if not isinstance(obligations, list) or any(
                    not isinstance(item, dict) for item in obligations
                ):
                    raise ValueError("memory obligations must be objects")
                blackboard_nodes = self.blackboard().nodes()
                requested_write_spaces = payload.get(
                    "blackboard_write_space_ids"
                )
                if requested_write_spaces is not None:
                    if (
                        not isinstance(requested_write_spaces, list)
                        or any(
                            not isinstance(item, str)
                            for item in requested_write_spaces
                        )
                        or len(set(requested_write_spaces))
                        != len(requested_write_spaces)
                    ):
                        raise ValueError(
                            "memory blackboard_write_space_ids must be "
                            "a unique list of strings"
                        )
                    for space_id in requested_write_spaces:
                        node = blackboard_nodes.get(space_id)
                        if node is None or node.get("node_type") != "space":
                            raise ValueError(
                                "memory blackboard_write_space_ids must "
                                "name existing spaces"
                            )
                cross_space_endpoints = payload.get(
                    "blackboard_cross_space_endpoint_node_ids",
                    [],
                )
                if (
                    not isinstance(cross_space_endpoints, list)
                    or any(
                        not isinstance(item, str)
                        for item in cross_space_endpoints
                    )
                    or len(set(cross_space_endpoints))
                    != len(cross_space_endpoints)
                ):
                    raise ValueError(
                        "memory blackboard_cross_space_endpoint_node_ids "
                        "must be a unique list of strings"
                    )
                if any(
                    node_id not in blackboard_nodes
                    for node_id in cross_space_endpoints
                ):
                    raise ValueError(
                        "memory blackboard_cross_space_endpoint_node_ids "
                        "must name visible nodes"
                    )
                workload_profile = payload.get("workload_profile")
                if workload_profile is not None:
                    workload_profile = validate_workload_profile(workload_profile)
                v4_fields = {
                    "campaign_id": campaign_id,
                    "source_claim_id": source_claim_id,
                    "goal_relation": goal_relation,
                    "stop_conditions": list(stop_conditions),
                    "user_value_note": user_value_note,
                    "killed_by_fact": killed_by_fact,
                    "convention_profile_ids": list(convention_ids),
                    "obligations": [dict(item) for item in obligations],
                    "verification_plan": dict(
                        payload.get(
                            "verification_plan",
                            {
                                "mode": "closed_packet",
                                "authorized_artifact_roles": [],
                                "required_checks": [
                                    "mathematical",
                                    "scope",
                                    "typing",
                                ],
                            },
                        )
                    ),
                    "budgets": dict(payload.get("budgets", {})),
                    "decision_profile": decision_profile,
                    "score_model": COMPACT_SCORE_MODEL,
                    "workload_profile": workload_profile,
                    "blackboard_write_space_ids": (
                        None
                        if requested_write_spaces is None
                        else list(requested_write_spaces)
                    ),
                    "blackboard_cross_space_endpoint_node_ids": list(
                        cross_space_endpoints
                    ),
                }
                for key in (
                    "origin_blackboard_node_id",
                    "origin_blackboard_snapshot_id",
                    "origin_blackboard_node_sha256",
                    "blackboard_query_sha256",
                    "blackboard_query",
                    "promotion_task_sha256",
                    "failed_obligation_ids",
                    "preserve_obligation_ids",
                    "repair_mode",
                ):
                    if key in payload:
                        v4_fields[key] = payload[key]
            event = {
                "id": entry_id,
                "event_id": _json_hash(["memory-create", entry_id], 24),
                "kind": kind,
                "status": status,
                "claim": claim,
                "rationale": payload.get("rationale", ""),
                "dependencies": dependencies,
                **metrics,
                "suggested_actions": list(payload.get("suggested_actions", [])),
                "tags": list(payload.get("tags", [])),
                "source": payload.get("source", ""),
                "resolution_fact_id": resolution,
                "claim_relation": claim_relation,
                "related_fact_id": related_fact_id,
                "parent_memory_id": payload.get("parent_memory_id") or None,
                "repair_of_memory_id": payload.get("repair_of_memory_id") or None,
                "trigger_memory_id": payload.get("trigger_memory_id") or None,
                **v4_fields,
                "actor": actor,
                "timestamp": utc_now(),
            }
            existing = self.memory_latest().get(entry_id)
            if existing:
                if existing.get("kind") == kind and existing.get("claim") == claim:
                    return entry_id
                raise ValueError(f"memory id collision: {entry_id}")
            self._append_jsonl_once(
                self.memory_log,
                event,
                event_id=event["event_id"],
            )
            return entry_id

    def memory_update(
        self,
        entry_id: str,
        *,
        status: str,
        actor: str,
        note: str = "",
        resolution_fact_id: str | None = None,
        claim_relation: str | None = None,
        related_fact_id: str | None = None,
        event_id: str | None = None,
    ) -> None:
        with self.mutation_lock():
            actor = self._validate_actor(actor, "memory actor")
            if not isinstance(note, str):
                raise ValueError("memory update note must be a string")
            validate_memory_id(entry_id)
            if entry_id not in self.memory_latest():
                raise KeyError(f"unknown memory entry: {entry_id}")
            if status not in MEMORY_STATUSES:
                raise ValueError(f"unsupported memory status: {status}")
            if status in _STATUS_RELATIONS:
                if resolution_fact_id is None:
                    raise ValueError(f"{status} requires resolution_fact_id")
                resolution_fact_id = validate_fact_id(resolution_fact_id)
                self.get_fact(resolution_fact_id)
            elif resolution_fact_id is not None:
                raise ValueError("resolution_fact_id is only valid for fact-resolved statuses")
            if claim_relation is not None:
                if claim_relation not in CLAIM_RELATIONS:
                    raise ValueError("invalid memory claim_relation")
                if related_fact_id is None:
                    raise ValueError("claim_relation requires related_fact_id")
                related_fact_id = validate_fact_id(related_fact_id)
                self.get_fact(related_fact_id)
            elif related_fact_id is not None:
                raise ValueError("related_fact_id requires claim_relation")
            if status in _STATUS_RELATIONS:
                allowed = _STATUS_RELATIONS[status]
                claim_relation = claim_relation or sorted(allowed)[0]
                related_fact_id = related_fact_id or resolution_fact_id
                if (
                    claim_relation not in allowed
                    or related_fact_id != resolution_fact_id
                ):
                    raise ValueError(f"{status} has an incompatible claim_relation")
            event_id = event_id or _json_hash(
                [
                    "memory-update",
                    entry_id,
                    status,
                    note,
                    resolution_fact_id,
                    claim_relation,
                    related_fact_id,
                ],
                24,
            )
            event = {
                "id": entry_id,
                "event": "status-update",
                "event_id": event_id,
                "status": status,
                "note": note,
                "resolution_fact_id": resolution_fact_id,
                "claim_relation": claim_relation,
                "related_fact_id": related_fact_id,
                "actor": actor,
                "timestamp": utc_now(),
            }
            self._append_jsonl_once(self.memory_log, event, event_id=event_id)

    def memory_latest(self) -> dict[str, dict[str, Any]]:
        latest: dict[str, dict[str, Any]] = {}
        for event in self._read_jsonl(self.memory_log):
            entry_id = str(event.get("id", ""))
            if not entry_id:
                continue
            latest.setdefault(entry_id, {}).update(event)
        return latest

    def frontier(
        self,
        limit: int = 10,
        *,
        campaign_id: str | None = None,
        actionable: bool = True,
        collapse_repairs: bool = True,
        include_history: bool = False,
    ) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        verified = set(self.fact_ids())
        is_v4 = self.workflow_evidence_version() >= 4
        if is_v4:
            campaign_id = campaign_id or self.campaigns().active()
            if campaign_id is not None:
                campaign_id = validate_campaign_id(campaign_id)
                self.campaigns().status(campaign_id)
        for entry_id, entry in self.memory_latest().items():
            if (
                not include_history
                and entry.get("status") not in ACTIVE_MEMORY_STATUSES
            ):
                continue
            if (
                is_v4
                and campaign_id is not None
                and entry.get("campaign_id", campaign_id) != campaign_id
            ):
                continue
            dependencies = entry.get("dependencies", [])
            readiness = 1.0 if all(item in verified for item in dependencies) else 0.0
            if is_v4:
                score = actionable_score(entry, readiness=readiness)
                factors = decision_factors(entry, readiness=readiness)
                entries.append(
                    {
                        **entry,
                        "id": entry_id,
                        "campaign_id": entry.get("campaign_id", campaign_id),
                        "readiness": readiness,
                        "score_model": entry.get(
                            "score_model", COMPACT_SCORE_MODEL
                        ),
                        "score_role": COMPACT_SCORE_ROLE,
                        "decision_factors": factors,
                        "score": score,
                    }
                )
                continue
            priority = float(entry.get("priority", 0.5))
            novelty = float(entry.get("novelty", 0.5))
            testability = float(entry.get("testability", 0.5))
            risk = float(entry.get("risk", 0.5))
            score = (
                0.30 * priority
                + 0.25 * readiness
                + 0.20 * testability
                + 0.20 * novelty
                + 0.05 * (1.0 - risk)
            )
            entries.append({**entry, "id": entry_id, "readiness": readiness, "score": round(score, 4)})
        if is_v4 and actionable and collapse_repairs:
            entries = collapse_actionable_frontier(
                entries,
                include_history=include_history,
            )
        elif is_v4 and actionable:
            entries = [
                entry
                for entry in entries
                if not entry.get("killed_by_fact")
                and entry.get("status") in ACTIVE_MEMORY_STATUSES
            ]
        return sorted(entries, key=lambda item: (-item["score"], item["id"]))[:limit]

    def novelty_record(self, payload: dict[str, Any], *, actor: str) -> str:
        """Append one query-level literature search record without making a priority claim."""

        with self.mutation_lock():
            actor = self._validate_actor(actor, "novelty actor")
            require_exact_keys(
                payload,
                required={
                    "subject_kind",
                    "subject_id",
                    "corpus",
                    "query",
                    "status",
                    "hits",
                },
                optional={"notes"},
                label="novelty record",
            )
            subject_kind = require_string(payload, "subject_kind")
            subject_id = require_string(payload, "subject_id")
            if subject_kind == "memory":
                subject_id = validate_memory_id(subject_id)
                if subject_id not in self.memory_latest():
                    raise ValueError("novelty subject is not an existing memory entry")
            elif subject_kind == "fact":
                subject_id = validate_fact_id(subject_id)
                self.get_fact(subject_id)
            else:
                raise ValueError("novelty subject_kind must be memory or fact")
            corpus = require_string(payload, "corpus")
            query = require_string(payload, "query")
            status = require_string(payload, "status")
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
                if not isinstance(hit, dict):
                    raise ValueError(f"novelty hits[{index}] must be an object")
                require_exact_keys(
                    hit,
                    required={"title", "locator", "relation"},
                    label=f"novelty hits[{index}]",
                )
                relation = require_string(hit, "relation")
                if relation not in {"exact", "partial", "background"}:
                    raise ValueError(
                        f"novelty hits[{index}].relation must be exact, partial, or background"
                    )
                normalized_hits.append(
                    {
                        "title": require_string(hit, "title"),
                        "locator": require_string(hit, "locator"),
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
                "actor": actor,
            }
            event_id = sha256_json(semantic)
            event = {
                **semantic,
                "event": "novelty-query",
                "event_id": event_id,
                "searched_at": utc_now(),
            }
            self._append_jsonl_once(self.novelty_log, event, event_id=event_id)
            return event_id

    def novelty_status(self, subject_id: str) -> list[dict[str, Any]]:
        if FACT_ID_RE.fullmatch(subject_id):
            subject_kind = "fact"
        elif MEMORY_ID_RE.fullmatch(subject_id):
            subject_kind = "memory"
        else:
            raise ValueError("novelty subject id must be a fact id or memory id")
        return [
            event
            for event in self._read_jsonl(self.novelty_log)
            if event.get("subject_kind") == subject_kind
            and event.get("subject_id") == subject_id
        ]

    def report_output_path(self, relative: str) -> Path:
        return contained_path(self.reports_dir, relative, "report output")

    def claim_card(self, fact_id: str, *, audience: str) -> dict[str, Any]:
        """Build a hash-bound expert communication card from admitted state only."""

        if self.workflow_evidence_version() < 4:
            raise ValueError("expert claim cards require workflow evidence v4")
        fact = self.get_fact(fact_id)
        submission = (
            self._read_json(self.submission_path(fact.fact_id))
            if self.submission_path(fact.fact_id).exists()
            else {}
        )
        memory_entry: dict[str, Any] = {}
        task_id = submission.get("task_id")
        if isinstance(task_id, str):
            memory_entry = self.memory_latest().get(task_id, {})
        source_claim_id = memory_entry.get("source_claim_id")
        claim: dict[str, Any] | None = None
        literal: dict[str, Any] | None = None
        if isinstance(source_claim_id, str):
            claim = self.claims().show_claim(source_claim_id)
            literal = claim
            if claim["kind"] == "researcher_variant":
                literal = self.claims().show_claim(claim["parent_claim_id"])

        convention_ids = list(fact.convention_profile_ids)
        if claim is not None and claim["convention_profile_id"] not in convention_ids:
            convention_ids.append(claim["convention_profile_id"])
        conventions = [
            self.claims().show_convention(convention_id)
            for convention_id in convention_ids
        ]
        convention_profile = (
            " | ".join(
                (
                    f"{item['convention_id']}: "
                    + "; ".join(
                        f"{key}={value}"
                        for key, value in sorted(item["dimensions"].items())
                    )
                    + f"; source={item['source_version']}; "
                    + f"authority={item['authority']}"
                )
                for item in conventions
            )
            if conventions
            else "No convention profile is bound to this admitted fact."
        )
        literal_statement = (
            str(literal["statement"])
            if literal is not None
            else "No versioned source claim is bound to this admitted fact."
        )
        researcher_variant = (
            str(claim["statement"])
            if claim is not None and claim["kind"] == "researcher_variant"
            else (
                "No researcher variant; the literal source claim is used."
                if claim is not None
                else "No researcher variant is bound to this admitted fact."
            )
        )
        source_locator = (
            str(literal["source"]["locator"])
            if literal is not None
            else "No source locator is bound to this admitted fact."
        )
        artifacts = submission.get("artifacts", [])
        if not isinstance(artifacts, list) or any(
            not isinstance(item, dict) for item in artifacts
        ):
            raise ValueError("submission artifact manifest is invalid")
        interface = self.statement_interface(
            fact.fact_id,
            materialize=False,
        )
        admission_version = int(interface["schema_version"])
        assurance_label = (
            "v4-independent-review"
            if admission_version == 4
            else "legacy-v3-inherited"
        )
        return build_claim_card(
            fact=fact,
            audience=audience,
            literal_source_claim=literal_statement,
            researcher_variant=researcher_variant,
            variant_diff=(
                list(claim["variant_diff"]) if claim is not None else []
            ),
            source_locator=source_locator,
            convention_profile=convention_profile,
            reproduction_bundle=[dict(item) for item in artifacts],
            admission_evidence_version=admission_version,
            assurance_label=assurance_label,
        )

    def interpret_card(
        self,
        node_id: str,
        *,
        audience: str,
    ) -> dict[str, Any]:
        """Build a nontruth export card from current immutable blackboard state."""

        if self.workflow_evidence_version() < 4:
            raise ValueError(
                "interpretation cards require workflow evidence v4"
            )
        node = self.blackboard().show(node_id)
        return build_interpret_card(
            project_id=self.project_id(),
            node=node,
            audience=audience,
        )

    def import_danus_zip(self, archive: Path | str) -> dict[str, Any]:
        self.require_initialized()
        with self.mutation_lock():
            archive_path = Path(archive).resolve()
            archive_hash = hashlib.sha256(archive_path.read_bytes()).hexdigest()
            archive_prefix = archive_hash[:12]
            imported_facts: dict[str, tuple[Fact, str]] = {}
            target_ids: list[str] = []
            source_documents: dict[str, bytes] = {}
            with ZipFile(archive_path) as zipped:
                fact_names = sorted(
                    name
                    for name in zipped.namelist()
                    if "/facts/" in name
                    and name.endswith(".md")
                    and not name.startswith("__MACOSX/")
                )
                for name in fact_names:
                    raw = zipped.read(name).decode("utf-8")
                    fact = parse_fact_markdown(raw)
                    errors = fact.validate()
                    if errors:
                        raise ValueError(f"{name}: {'; '.join(errors)}")
                    if fact.problem_id != self.project_id():
                        raise ValueError(
                            f"archive fact {fact.fact_id} belongs to project {fact.problem_id!r}"
                        )
                    if fact.fact_id in imported_facts:
                        previous, _ = imported_facts[fact.fact_id]
                        logical_fields = (
                            "problem_id",
                            "predecessors",
                            "glossary_introduces",
                            "statement",
                            "proof",
                        )
                        if any(
                            getattr(previous, field) != getattr(fact, field)
                            for field in logical_fields
                        ):
                            raise ValueError(
                                f"duplicate fact id collision in archive: {fact.fact_id}"
                            )
                        continue
                    imported_facts[fact.fact_id] = (fact, raw)
                target_name = next(
                    (
                        name
                        for name in zipped.namelist()
                        if name.endswith("/TARGET.md") and not name.startswith("__MACOSX/")
                    ),
                    "",
                )
                if target_name:
                    target_ids = [
                        validate_fact_id(line.strip())
                        for line in zipped.read(target_name).decode("utf-8").splitlines()
                        if line.strip() and not line.lstrip().startswith("#")
                    ]
                for source_name in ("PROBLEM.md", "SOURCE.md", "TARGET.md"):
                    member = next(
                        (
                            name
                            for name in zipped.namelist()
                            if name.endswith("/" + source_name)
                            and not name.startswith("__MACOSX/")
                        ),
                        "",
                    )
                    if member:
                        source_documents[source_name] = zipped.read(member)

            existing = self.facts()
            revoked_ids = {path.stem for path in self.revoked_dir.glob("*.md")}
            resurrected = sorted(set(imported_facts).intersection(revoked_ids))
            if resurrected:
                raise ValueError("import would resurrect revoked facts: " + ", ".join(resurrected))
            combined = dict(existing)
            combined.update({fact_id: item[0] for fact_id, item in imported_facts.items()})
            graph = DependencyGraph(combined)
            missing = graph.missing_predecessors()
            if missing:
                rendered = ", ".join(
                    f"{fact}->{predecessor}" for fact, predecessor in missing
                )
                raise ValueError("archive has missing predecessors: " + rendered)
            graph.topological_order()
            unknown_targets = sorted(set(target_ids).difference(combined))
            if unknown_targets:
                raise ValueError(
                    "archive targets are not verified facts: " + ", ".join(unknown_targets)
                )

            imported = sorted(imported_facts)
            for fact_id, (_, raw) in imported_facts.items():
                self._write_bytes_once(self.fact_path(fact_id), raw.encode("utf-8"), mode=0o644)
            for source_name, raw in source_documents.items():
                self._write_bytes_once(
                    self.imports_dir / f"danus-{archive_prefix}-{source_name.lower()}", raw
                )
            record = {
                "kind": "danus-finalized-export",
                "project_id": self.project_id(),
                "archive_name": archive_path.name,
                "archive_sha256": archive_hash,
                "facts": imported,
                "targets": target_ids,
                "imported_at": utc_now(),
            }
            self._write_json_once(
                self.imports_dir / f"danus-import-{archive_prefix}.json", record
            )
            for fact_id in imported:
                self.add_fact_metadata(
                    fact_id,
                    kind="imported-fact",
                    assurance="inherited-danus-verifier",
                    provenance_archive_sha256=archive_hash,
                    event_id=_json_hash(["import", archive_hash, fact_id], 24),
                )
            if self.workflow_evidence_version() >= 4:
                campaigns = self.campaigns()
                campaign_id = campaigns.active()
                if campaign_id is None:
                    raise ValueError(
                        "V4 import requires an active campaign"
                    )
                for target_id in target_ids:
                    campaigns.target_add(
                        campaign_id,
                        {
                            "role": "supporting_proof",
                            "subject_kind": "fact",
                            "subject_id": target_id,
                            "label": f"Imported target {target_id}",
                        },
                        actor="operator-import",
                        fact_exists=lambda candidate: (
                            candidate in set(self.fact_ids())
                        ),
                    )
                self.sync_active_campaign_targets(
                    campaign_id=campaign_id
                )
            else:
                self.set_targets(
                    list(dict.fromkeys(self.targets() + target_ids))
                )
            return {
                "facts": len(imported),
                "targets": target_ids,
                "archive_sha256": archive_hash,
            }

    def _audit_v4_components(
        self,
        report: AuditReport,
        *,
        facts: dict[str, Fact],
        project_id: str,
    ) -> None:
        def workflow_error(message: str) -> None:
            report.workflow_errors.append(message)
            report.errors.append(f"workflow: {message}")

        mode_report = self.reasoning_modes().audit()
        for message in mode_report["errors"]:
            workflow_error(f"reasoning mode: {message}")
        report.warnings.extend(
            f"reasoning mode: {message}"
            for message in mode_report["warnings"]
        )

        profile_closure_report = self.profile_closures().audit()
        for message in profile_closure_report["errors"]:
            workflow_error(f"profile closure: {message}")
        report.warnings.extend(
            f"profile closure: {message}"
            for message in profile_closure_report["warnings"]
        )

        try:
            self._v4_ingestion_receipts()
        except Exception as exc:
            workflow_error(f"v4 ingestion receipt: {exc}")

        blackboard_report = self.blackboard().audit()
        report.blackboard_graph_errors.extend(blackboard_report["errors"])
        report.blackboard_graph_warnings.extend(blackboard_report["warnings"])
        report.errors.extend(
            f"blackboard: {message}" for message in blackboard_report["errors"]
        )

        paper_logic_report = self.paper_logic().audit(
            blackboard=self.blackboard()
        )
        report.paper_logic_errors.extend(paper_logic_report["errors"])
        report.paper_logic_warnings.extend(paper_logic_report["warnings"])
        report.paper_source_nodes = paper_logic_report["source_nodes"]
        report.paper_reconstruction_nodes = paper_logic_report[
            "reconstruction_nodes"
        ]
        report.paper_audit_nodes = paper_logic_report["audit_nodes"]
        report.errors.extend(
            f"paper_logic: {message}"
            for message in paper_logic_report["errors"]
        )
        report.warnings.extend(
            f"paper_logic: {message}"
            for message in paper_logic_report["warnings"]
        )

        try:
            collaboration_report = self.collaboration().audit()
        except Exception as exc:
            workflow_error(
                f"collaboration host adapter: {exc}"
            )
        else:
            for message in collaboration_report["errors"]:
                workflow_error(f"collaboration pulse: {message}")
            report.warnings.extend(
                f"collaboration pulse: {message}"
                for message in collaboration_report["warnings"]
            )

        experiments = self.experiments()
        audited_governance: set[str] = set()
        for task_card_path in sorted(
            self.rounds_dir.glob("*/task-cards/*.json")
        ):
            try:
                task_card = self._read_json(task_card_path)
                validate_task_card(
                    task_card,
                    allow_legacy_adoption=True,
                )
                if "hard_caps" not in task_card:
                    # Historical cards are inspectable but deliberately
                    # read-only; only replanned cards acquire the new profile.
                    continue
                governance_id = experiments.governance_task_id(task_card)
                if governance_id not in audited_governance:
                    governance = experiments.audit_governance_hard_caps(
                        task_card=task_card,
                    )
                    for message in governance["errors"]:
                        workflow_error(
                            f"governance hard-cap audit "
                            f"{governance_id}: {message}"
                        )
                    audited_governance.add(governance_id)
                work_dir = contained_path(
                    self.root,
                    task_card["work_dir_relpath"],
                    "hard-cap audit work directory",
                )
                experiment_root = work_dir / "experiments"
                if not experiment_root.exists():
                    continue
                if (
                    experiment_root.is_symlink()
                    or not experiment_root.is_dir()
                ):
                    raise ValueError(
                        "experiment root is not a safe directory"
                    )
                for experiment_dir in sorted(experiment_root.iterdir()):
                    if (
                        experiment_dir.is_symlink()
                        or not experiment_dir.is_dir()
                    ):
                        raise ValueError(
                            "experiment root contains an unsafe entry"
                        )
                    hard_cap_report = experiments.audit_hard_caps(
                        task_card=task_card,
                        experiment_id=experiment_dir.name,
                    )
                    for message in hard_cap_report["errors"]:
                        workflow_error(
                            f"experiment hard-cap audit "
                            f"{task_card['assignment_id']}/"
                            f"{experiment_dir.name}: {message}"
                        )
            except Exception as exc:
                workflow_error(
                    f"hard-cap audit {task_card_path.parent.parent.name}/"
                    f"{task_card_path.name}: {exc}"
                )

        claims_report = self.claims().audit()
        for message in claims_report["errors"]:
            workflow_error(f"claim/convention registry: {message}")

        for path in sorted(
            (
                self.reports_dir / "expert-lint-receipts"
            ).glob("*.json")
        ):
            try:
                receipt = validate_expert_lint_receipt(
                    self._read_json(path)
                )
                if (
                    receipt["project_id"] != project_id
                    or contained_path(
                        self.root,
                        receipt["receipt_relpath"],
                        "expert lint receipt path",
                    )
                    != path
                ):
                    raise ValueError(
                        "expert lint receipt project/path binding mismatch"
                    )
            except Exception as exc:
                workflow_error(
                    f"expert lint receipt {path.name}: {exc}"
                )

        for path in sorted(
            (
                self.reports_dir / "interpret-lint-receipts"
            ).glob("*.json")
        ):
            try:
                if path.is_symlink() or not path.is_file():
                    raise ValueError(
                        "interpret lint receipt is not a regular file"
                    )
                raw_receipt = self._read_json(path)
                card_path = contained_path(
                    self.root,
                    require_string(
                        raw_receipt, "interpret_card_relpath"
                    ),
                    "interpret lint card path",
                )
                if card_path.is_symlink() or not card_path.is_file():
                    raise ValueError(
                        "interpret lint card is missing or unsafe"
                    )
                card_bytes = card_path.read_bytes()
                receipt = validate_interpret_lint_receipt(
                    raw_receipt,
                    interpret_card_bytes=card_bytes,
                )
                if (
                    receipt["project_id"] != project_id
                    or contained_path(
                        self.root,
                        receipt["receipt_relpath"],
                        "interpret lint receipt path",
                    )
                    != path
                ):
                    raise ValueError(
                        "interpret lint receipt project/path binding mismatch"
                    )
                card = json.loads(card_bytes.decode("utf-8"))
                expected_card = self.interpret_card(
                    receipt["node_id"],
                    audience=receipt["audience"],
                )
                if card != expected_card:
                    raise ValueError(
                        "interpret lint card differs from current immutable "
                        "mechanism node"
                    )
            except Exception as exc:
                workflow_error(
                    f"interpret lint receipt {path.name}: {exc}"
                )

        def source_claim_exists(claim_id: str) -> bool:
            try:
                self.claims().show_claim(claim_id)
            except (KeyError, ValueError, OSError):
                return False
            return True

        campaign_report = self.campaigns().audit(
            fact_exists=lambda fact_id: fact_id in facts,
            source_claim_exists=source_claim_exists,
        )
        for message in campaign_report["errors"]:
            workflow_error(f"campaign: {message}")
        try:
            campaign_id = self.campaigns().active()
            expected_targets = (
                self.campaigns().derived_targets(campaign_id)
                if campaign_id is not None
                else []
            )
            if self.targets() != expected_targets:
                raise ValueError(
                    "TARGETS.txt does not equal the active campaign "
                    "proof-target projection"
                )
        except Exception as exc:
            workflow_error(f"campaign target projection: {exc}")

        fact_bundle_report = self.fact_bundles().audit()
        for message in fact_bundle_report["errors"]:
            workflow_error(f"fact bundle: {message}")

        for path in sorted(self.interfaces_dir.glob("*.json")):
            try:
                interface = validate_statement_interface(self._read_json(path))
                if path.stem != interface["fact_id"]:
                    raise ValueError("filename/fact id mismatch")
                if (
                    interface["fact_id"] not in facts
                    and interface["fact_id"] not in self._revoked_fact_ids()
                ):
                    raise ValueError(
                        "interface has neither an active nor revoked admitted fact"
                    )
            except Exception as exc:
                workflow_error(f"statement interface {path.name}: {exc}")

        bundle_store = self.verification_bundles()
        if bundle_store.by_hash_dir.exists():
            bundle_report = bundle_store.audit()
            for message in bundle_report["errors"]:
                workflow_error(f"verification bundle: {message}")

        legacy_prefix_lengths: dict[str, int] = {}
        for path in sorted(self.migrations_dir.glob("*.json")):
            try:
                receipt = self._read_json(path)
                if receipt.get("schema_version") != 4:
                    raise ValueError("schema_version must be 4")
                if receipt.get("policy_revision") != POLICY_REVISION_V4:
                    raise ValueError("policy revision mismatch")
                if receipt.get("project_id") != project_id:
                    raise ValueError("migration belongs to another project")
                inventory = receipt.get("legacy_inventory")
                if not isinstance(inventory, dict) or any(
                    not isinstance(key, str)
                    or not isinstance(value, str)
                    or SHA256_RE.fullmatch(value) is None
                    for key, value in inventory.items()
                ):
                    raise ValueError("legacy inventory is invalid")
                if receipt.get("legacy_inventory_sha256") != sha256_json(inventory):
                    raise ValueError("legacy inventory digest mismatch")
                base_semantic = {
                    key: receipt[key]
                    for key in (
                        "schema_version",
                        "policy_revision",
                        "migration",
                        "actor",
                        "project_id",
                        "project_before_sha256",
                        "project_after_sha256",
                        "legacy_inventory_sha256",
                        "legacy_inventory",
                        "legacy_default_campaign_id",
                        "legacy_targets",
                    )
                }
                stable_copy_inheritance = receipt.get(
                    "stable_copy_inheritance"
                )
                if stable_copy_inheritance is not None:
                    stable_copy_inheritance = (
                        self._validate_stable_copy_inheritance(
                            stable_copy_inheritance
                        )
                    )
                    if (
                        stable_copy_inheritance["source_project_id"]
                        != project_id
                    ):
                        raise ValueError(
                            "stable-copy source project id mismatch"
                        )
                    if (
                        stable_copy_inheritance[
                            "source_project_semantic_sha256"
                        ]
                        != receipt["project_before_sha256"]
                    ):
                        raise ValueError(
                            "stable-copy source project declaration mismatch"
                        )
                    base_semantic["stable_copy_inheritance"] = (
                        stable_copy_inheritance
                    )
                prefix_inventory = receipt.get(
                    "legacy_append_only_prefixes"
                )
                if prefix_inventory is None:
                    semantic = base_semantic
                else:
                    if not isinstance(prefix_inventory, dict):
                        raise ValueError(
                            "legacy append-only prefix inventory is invalid"
                        )
                    normalized_prefixes: dict[str, dict[str, Any]] = {}
                    for relative, binding in prefix_inventory.items():
                        if (
                            not isinstance(relative, str)
                            or relative not in _LEGACY_APPEND_ONLY_PATHS
                            or not isinstance(binding, dict)
                        ):
                            raise ValueError(
                                "legacy append-only prefix entry is invalid"
                            )
                        require_exact_keys(
                            binding,
                            required={"byte_length", "sha256"},
                            label=(
                                "legacy append-only prefix "
                                f"{relative}"
                            ),
                        )
                        byte_length = binding.get("byte_length")
                        expected_sha = binding.get("sha256")
                        if (
                            isinstance(byte_length, bool)
                            or not isinstance(byte_length, int)
                            or byte_length < 0
                            or not isinstance(expected_sha, str)
                            or SHA256_RE.fullmatch(expected_sha) is None
                        ):
                            raise ValueError(
                                "legacy append-only prefix binding is invalid"
                            )
                        normalized_prefixes[relative] = {
                            "byte_length": byte_length,
                            "sha256": expected_sha,
                        }
                        previous_length = legacy_prefix_lengths.get(relative)
                        if (
                            previous_length is not None
                            and previous_length != byte_length
                        ):
                            raise ValueError(
                                "conflicting legacy append-only prefix "
                                f"length for {relative}"
                            )
                        legacy_prefix_lengths[relative] = byte_length
                    if (
                        receipt.get(
                            "legacy_append_only_prefixes_sha256"
                        )
                        != sha256_json(normalized_prefixes)
                    ):
                        raise ValueError(
                            "legacy append-only prefix digest mismatch"
                        )
                    mutable_projections = receipt.get(
                        "legacy_mutable_projections"
                    )
                    if mutable_projections != sorted(
                        _LEGACY_MUTABLE_PROJECTION_PATHS
                    ):
                        raise ValueError(
                            "legacy mutable projection policy mismatch"
                        )
                    if set(inventory).intersection(
                        _LEGACY_APPEND_ONLY_PATHS
                        | _LEGACY_MUTABLE_PROJECTION_PATHS
                    ):
                        raise ValueError(
                            "legacy immutable inventory overlaps a mutable policy"
                        )
                    semantic = {
                        **base_semantic,
                        "legacy_append_only_prefixes_sha256": receipt[
                            "legacy_append_only_prefixes_sha256"
                        ],
                        "legacy_append_only_prefixes": normalized_prefixes,
                        "legacy_mutable_projections": mutable_projections,
                    }
                receipt_id = sha256_json(semantic)
                if (
                    path.stem != receipt_id
                    or receipt.get("migration_receipt_id") != receipt_id
                ):
                    raise ValueError("migration receipt id/hash mismatch")
                for relative, expected in inventory.items():
                    legacy_path = contained_path(
                        self.root, relative, "migration legacy inventory path"
                    )
                    if (
                        not legacy_path.is_file()
                        or legacy_path.is_symlink()
                        or sha256_bytes(legacy_path.read_bytes()) != expected
                    ):
                        raise ValueError(
                            f"legacy evidence changed after migration: {relative}"
                        )
                    if (
                        prefix_inventory is None
                        and relative in _LEGACY_APPEND_ONLY_PATHS
                    ):
                        legacy_prefix_lengths[relative] = len(
                            legacy_path.read_bytes()
                        )
                if prefix_inventory is not None:
                    for relative, binding in normalized_prefixes.items():
                        legacy_path = contained_path(
                            self.root,
                            relative,
                            "migration legacy append-only path",
                        )
                        if (
                            not legacy_path.is_file()
                            or legacy_path.is_symlink()
                        ):
                            raise ValueError(
                                "legacy append-only evidence disappeared "
                                f"after migration: {relative}"
                            )
                        raw = legacy_path.read_bytes()
                        prefix_length = binding["byte_length"]
                        if (
                            len(raw) < prefix_length
                            or sha256_bytes(raw[:prefix_length])
                            != binding["sha256"]
                        ):
                            raise ValueError(
                                "legacy append-only prefix changed after "
                                f"migration: {relative}"
                            )
            except Exception as exc:
                workflow_error(f"migration receipt {path.name}: {exc}")

        for message in self._audit_v4_append_anchors(
            legacy_prefix_lengths
        ):
            workflow_error(message)

        for round_path in sorted(self.rounds_dir.glob("*/round.json")):
            try:
                manifest = self._read_json(round_path)
                if manifest.get("schema_version") != 4:
                    continue
                require_exact_keys(
                    manifest,
                    required={
                        "schema_version",
                        "policy_revision",
                        "project_id",
                        "round_id",
                        "created_at",
                        "blackboard_snapshot_id",
                        "blackboard_snapshot_sha256",
                        "assignments",
                    },
                    optional={
                        "reasoning_mode",
                        "reasoning_mode_event_id",
                        "reasoning_mode_policy_sha256",
                        "fact_admission_contract_sha256",
                        "execution_profile",
                        "profile_obligations",
                    },
                    label="v4 round manifest",
                )
                if manifest.get("policy_revision") != POLICY_REVISION_V4:
                    raise ValueError("policy revision mismatch")
                if manifest.get("project_id") != project_id:
                    raise ValueError("round belongs to another project")
                if manifest.get("round_id") != round_path.parent.name:
                    raise ValueError("round directory/id mismatch")
                if "reasoning_mode" in manifest:
                    self.profile_closures().obligation_view(
                        manifest["round_id"]
                    )
                snapshot = self.blackboard().snapshot_manifest(
                    require_string(manifest, "blackboard_snapshot_id")
                )
                snapshot_path = (
                    self.blackboard().snapshots_dir
                    / snapshot["snapshot_id"]
                    / "manifest.json"
                )
                if (
                    sha256_bytes(snapshot_path.read_bytes())
                    != manifest["blackboard_snapshot_sha256"]
                ):
                    raise ValueError("round blackboard snapshot hash mismatch")
                assignments = manifest.get("assignments")
                if not isinstance(assignments, list) or not assignments:
                    raise ValueError("round assignments must be a nonempty list")
                for assignment in assignments:
                    if not isinstance(assignment, dict):
                        raise ValueError("round assignment must be an object")
                    task_path = contained_path(
                        self.root,
                        require_string(assignment, "task_card_relpath"),
                        "task card path",
                    )
                    if not task_path.is_file() or task_path.is_symlink():
                        raise ValueError("task card is missing or not regular")
                    if (
                        sha256_bytes(task_path.read_bytes())
                        != assignment.get("task_card_sha256")
                    ):
                        raise ValueError("task card hash mismatch")
                    card = self._read_json(task_path)
                    self.experiments()._validate_bound_task_card(
                        card,
                        allow_historical_estimate_policy=True,
                    )
                    contract = assignment.get("contract")
                    if not isinstance(contract, dict):
                        raise ValueError("assignment contract is invalid")
                    if sha256_json(contract) != assignment.get(
                        "assignment_sha256"
                    ):
                        raise ValueError("assignment contract hash mismatch")
                    if (
                        card["round_id"] != manifest["round_id"]
                        or card["assignment_id"] != assignment.get("assignment_id")
                        or card["blackboard_view"]["snapshot_id"]
                        != manifest["blackboard_snapshot_id"]
                    ):
                        raise ValueError("task card/round binding mismatch")
                    if "reasoning_mode" in manifest:
                        for key in (
                            "reasoning_mode",
                            "reasoning_mode_event_id",
                            "reasoning_mode_policy_sha256",
                            "fact_admission_contract_sha256",
                        ):
                            if card.get(key) != manifest.get(key):
                                raise ValueError(
                                    f"task card/round {key} binding mismatch"
                                )
                            if contract.get(key) != manifest.get(key):
                                raise ValueError(
                                    f"assignment contract/round {key} binding mismatch"
                                )
                        profile_hashes = manifest.get("execution_profile")
                        if (
                            not isinstance(profile_hashes, dict)
                            or card.get("execution_profile", {}).get(
                                "execution_profile_sha256"
                            )
                            != profile_hashes.get(
                                assignment.get("assignment_id")
                            )
                        ):
                            raise ValueError(
                                "task card/round execution-profile binding mismatch"
                            )
                        if contract.get("execution_profile", {}).get(
                            "execution_profile_sha256"
                        ) != profile_hashes.get(
                            assignment.get("assignment_id")
                        ):
                            raise ValueError(
                                "assignment contract/round execution-profile binding mismatch"
                            )
                    if "campaign_snapshot_relpath" in card:
                        campaign_snapshot_path = contained_path(
                            self.root,
                            card["campaign_snapshot_relpath"],
                            "campaign snapshot path",
                        )
                        if (
                            campaign_snapshot_path
                            != round_path.parent / "campaign.snapshot.json"
                            or not campaign_snapshot_path.is_file()
                            or campaign_snapshot_path.is_symlink()
                            or sha256_bytes(
                                campaign_snapshot_path.read_bytes()
                            )
                            != card["campaign_snapshot_sha256"]
                        ):
                            raise ValueError(
                                "round campaign snapshot path/hash mismatch"
                            )
                        campaign_snapshot = self._read_json(
                            campaign_snapshot_path
                        )
                        if (
                            campaign_snapshot.get("campaign_id")
                            != card["campaign_id"]
                        ):
                            raise ValueError(
                                "round campaign snapshot id mismatch"
                            )
                    return_path = contained_path(
                        self.root,
                        require_string(assignment, "return_relpath"),
                        "return path",
                    )
                    if return_path.exists():
                        payload = self._read_json(return_path)
                        validate_worker_return(
                            payload,
                            assignment,
                            manifest,
                            project_root=self.root,
                            historical_policy=True,
                            interface_lookup=lambda fact_id: self._read_json(
                                self.interfaces_dir / f"{fact_id}.json"
                            ),
                        )
            except Exception as exc:
                workflow_error(
                    f"{round_path.parent.name}: invalid v4 round workflow: {exc}"
                )

    def audit(self) -> AuditReport | V5AuditReport:
        if self.project_path.exists():
            try:
                if (
                    self.workflow_evidence_version()
                    == V5_WORKFLOW_EVIDENCE_VERSION
                ):
                    return self.v5_lifecycle().audit()
            except Exception:
                # The legacy audit below produces the structured project.json
                # diagnostic for malformed or partially written roots.
                pass
        report = AuditReport()

        def graph_error(message: str) -> None:
            report.graph_errors.append(message)
            report.errors.append(message)

        def workflow_error(message: str) -> None:
            rendered = f"workflow: {message}"
            report.workflow_errors.append(message)
            report.errors.append(rendered)

        if not self.project_path.exists():
            graph_error("project.json is missing")
            return report
        try:
            project = self.project()
            project_id = self.project_id()
        except Exception as exc:
            graph_error(f"invalid project.json: {exc}")
            return report
        schema_version = int(project.get("schema_version", 1))
        workflow_evidence_version = project.get("workflow_evidence_version")
        is_v4 = workflow_evidence_version == 4
        if workflow_evidence_version is None:
            if schema_version >= 2:
                report.warnings.append(
                    "project predates the explicit workflow_evidence_version label"
                )
        elif workflow_evidence_version not in {3, 4}:
            workflow_error(
                "project workflow_evidence_version must be 3 or 4 when explicitly declared"
            )
        elif is_v4 and project.get("policy_revision") != POLICY_REVISION_V4:
            # Keep the pre-v4 diagnostic for a bare, manually edited version
            # label. A valid v4 migration always adds the policy revision too.
            workflow_error(
                "project workflow_evidence_version must be 3 when explicitly declared"
            )
            workflow_error("v4 project policy_revision is missing or mismatched")

        facts: dict[str, Fact] = {}
        legacy_external_ref_facts: set[str] = set()
        legacy_source_reliability_facts: set[str] = set()
        try:
            active_fact_paths = self._active_fact_paths()
        except Exception as exc:
            graph_error(f"active fact visibility failed: {exc}")
            active_fact_paths = {
                path.stem: path
                for path in sorted(self.facts_dir.glob("*.md"))
            }
        for expected_fact_id, path in sorted(active_fact_paths.items()):
            try:
                fact = parse_fact_markdown(path.read_text(encoding="utf-8"))
            except Exception as exc:
                graph_error(f"{path.name}: parse failed: {exc}")
                continue
            if expected_fact_id != fact.fact_id:
                graph_error(f"{path.name}: filename does not match fact_id {fact.fact_id}")
            for error in fact.validate():
                graph_error(f"{path.name}: {error}")
            if fact.problem_id != project_id:
                graph_error(f"{path.name}: problem_id does not match project")
            if fact.fact_id in facts:
                graph_error(f"duplicate fact id: {fact.fact_id}")
            facts[fact.fact_id] = fact
            if fact.external_refs:
                if any(not isinstance(ref.get("applicability"), dict) for ref in fact.external_refs):
                    legacy_external_ref_facts.add(fact.fact_id)
                else:
                    if any(
                        ref.get("source_evidence_version") != SOURCE_EVIDENCE_VERSION
                        for ref in fact.external_refs
                    ):
                        legacy_source_reliability_facts.add(fact.fact_id)
                    try:
                        validate_external_refs_for_submission(fact.external_refs, fact.proof)
                    except ValueError as exc:
                        graph_error(f"{path.name}: invalid external-source certificate: {exc}")
            try:
                validate_elementary_uses_for_submission(
                    fact.elementary_uses,
                    fact.proof,
                )
            except ValueError as exc:
                graph_error(f"{path.name}: invalid elementary-use ledger: {exc}")
        report.facts = len(facts)
        report.edges = sum(len(fact.predecessors) for fact in facts.values())
        graph = DependencyGraph(facts)
        for fact_id, predecessor in graph.missing_predecessors():
            graph_error(f"{fact_id}: missing predecessor {predecessor}")
        try:
            graph.topological_order()
            depths = graph.depths()
            report.max_depth = max(depths.values(), default=0)
        except ValueError as exc:
            graph_error(str(exc))
        targets = self.targets()
        report.targets = len(targets)
        unknown_targets = [target for target in targets if target not in facts]
        for target in unknown_targets:
            graph_error(f"unknown target: {target}")
        target_closure_ids: set[str] = set()
        if targets and not unknown_targets:
            target_closure_ids = graph.closure(targets)
            report.target_closure = len(target_closure_ids)
            conflicts = self.scoped_glossary_conflicts(sorted(target_closure_ids))
            if conflicts:
                report.warnings.append(
                    f"target closure has {len(conflicts)} fact-scoped symbol redefinitions; "
                    "contexts must not flatten them into one global glossary"
                )
        if legacy_external_ref_facts:
            closure_count = len(legacy_external_ref_facts.intersection(target_closure_ids))
            message = (
                f"{len(legacy_external_ref_facts)} admitted facts use pre-certificate external_refs"
                f" ({closure_count} in the target closure); their source applicability is inherited"
                " historical trust, not certified by the current external-theorem gate"
            )
            if is_v4:
                report.historical_workflow_warnings.append(message)
                if closure_count:
                    report.trust_debt.append(message)
            else:
                report.warnings.append(message)
        if legacy_source_reliability_facts:
            closure_count = len(
                legacy_source_reliability_facts.intersection(target_closure_ids)
            )
            message = (
                f"{len(legacy_source_reliability_facts)} admitted facts use pre-v3 tiered "
                f"external-source evidence ({closure_count} in the target closure); their source "
                "bytes, theorem transcription, typo checks, version comparison, and issue searches "
                "are inherited historical trust"
            )
            if is_v4:
                report.historical_workflow_warnings.append(message)
                if closure_count:
                    report.trust_debt.append(message)
            else:
                report.warnings.append(message)
        certificate_path = self.reports_dir / "target-closure-certificate.json"
        if certificate_path.exists() and not unknown_targets:
            try:
                stored_certificate = self._read_json(certificate_path)
                current_certificate = self._target_certificate_payload(targets)
                for key in (
                    "targets",
                    "closure",
                    "closure_size",
                    "edges_in_closure",
                    "fact_sha256",
                    "certificate_sha256",
                ):
                    expected = current_certificate.get(key)
                    if key == "certificate_sha256" and schema_version < 2:
                        legacy_payload = {
                            name: value
                            for name, value in current_certificate.items()
                            if name != "certificate_sha256"
                        }
                        legacy_hash = hashlib.sha256(
                            json.dumps(
                                legacy_payload, ensure_ascii=False, sort_keys=True
                            ).encode("utf-8")
                        ).hexdigest()
                        if stored_certificate.get(key) in {expected, legacy_hash}:
                            continue
                    if stored_certificate.get(key) != expected:
                        graph_error(f"target closure certificate is stale at field {key}")
                        break
            except Exception as exc:
                graph_error(f"invalid target closure certificate: {exc}")
        else:
            graph_error("target closure certificate is missing")

        revoked_ids = self._revoked_fact_ids()
        revoked_facts: dict[str, Fact] = {}
        revoked_paths = {
            path.stem: path for path in sorted(self.revoked_dir.glob("*.md"))
        }
        try:
            for fact_id, path in self.fact_bundles().accepted_fact_paths(
                strict=True
            ).items():
                if fact_id in revoked_ids:
                    revoked_paths[fact_id] = path
        except Exception as exc:
            workflow_error(f"revoked fact bundle visibility: {exc}")
        for expected_fact_id, path in sorted(revoked_paths.items()):
            try:
                fact = parse_fact_markdown(path.read_text(encoding="utf-8"))
                if expected_fact_id != fact.fact_id:
                    raise ValueError("filename does not match fact_id")
                errors = fact.validate()
                if errors:
                    raise ValueError("; ".join(errors))
                if fact.problem_id != project_id:
                    raise ValueError("problem_id does not match project")
                revoked_facts[fact.fact_id] = fact
            except Exception as exc:
                workflow_error(f"revoked {path.name}: invalid historical fact: {exc}")
        for fact_id in sorted(set(facts).intersection(revoked_ids)):
            graph_error(f"fact exists in both verified and revoked stores: {fact_id}")

        submissions: dict[str, dict[str, Any]] = {}
        legacy_submissions = 0
        legacy_source_reliability_submissions = 0
        for path in sorted(self.submissions_dir.glob("*.json")):
            try:
                payload = self._read_json(path)
                fact_id = validate_fact_id(str(payload.get("submission_id", path.stem)))
                if path.stem != fact_id:
                    raise ValueError("filename/submission id mismatch")
                if payload.get("submission_id") != fact_id:
                    raise ValueError("submission_id is missing or mismatched")
                fact = Fact.from_dict(payload)
                errors = fact.validate()
                if errors:
                    raise ValueError("; ".join(errors))
                if fact.problem_id != project_id:
                    raise ValueError("submission problem_id does not match project")
                evidence_version = payload.get("evidence_version")
                if evidence_version in {2, 3, 4}:
                    self._validate_actor(payload.get("worker"), "submission worker")
                    require_string(payload, "submitted_at")
                    if payload.get("submission_sha256") != _submission_digest(payload):
                        raise ValueError("submission hash mismatch")
                    status = payload.get("status")
                    if status not in SUBMISSION_STATUSES:
                        raise ValueError("invalid submission status")
                    review_ids = payload.get("review_ids")
                    if not isinstance(review_ids, list) or any(
                        not isinstance(item, str) or REVIEW_ID_RE.fullmatch(item) is None
                        for item in review_ids
                    ):
                        raise ValueError("review_ids must contain full review hashes")
                    if status == "accepted" and fact_id not in facts:
                        raise ValueError("accepted submission has no verified fact")
                    if status == "revoked" and fact_id not in revoked_facts:
                        raise ValueError("revoked submission has no revoked fact")
                    if status in {"pending_review", "rejected"} and fact_id in facts:
                        raise ValueError("non-accepted submission already exists in truth")
                    if status == "pending_review":
                        unknown_predecessors = set(fact.predecessors).difference(facts)
                        if unknown_predecessors:
                            raise ValueError(
                                "pending submission has unavailable predecessors: "
                                + ", ".join(sorted(unknown_predecessors))
                            )
                    round_id = payload.get("round_id", "")
                    assignment_id = payload.get("assignment_id", "")
                    if bool(round_id) != bool(assignment_id):
                        raise ValueError("round/assignment binding is incomplete")
                    if round_id:
                        validate_round_id(round_id)
                        validate_assignment_id(assignment_id)
                    if evidence_version in {3, 4}:
                        relation = require_string(payload, "claim_relation")
                        if relation not in CLAIM_RELATIONS:
                            raise ValueError("submission claim_relation is invalid")
                        if not isinstance(payload.get("assigned_claim"), str):
                            raise ValueError("submission assigned_claim must be a string")
                        if fact.external_refs and any(
                            ref.get("source_evidence_version") != SOURCE_EVIDENCE_VERSION
                            for ref in fact.external_refs
                        ):
                            legacy_source_reliability_submissions += 1
                        validate_external_refs_for_submission(
                            fact.external_refs,
                            fact.proof,
                            require_formula_fidelity=(
                                evidence_version == 4 or not is_v4
                            ),
                            require_critical_audit=(evidence_version == 4),
                        )
                        validate_elementary_uses_for_submission(
                            fact.elementary_uses,
                            fact.proof,
                        )
                    if evidence_version == 4:
                        if payload.get("policy_revision") != POLICY_REVISION_V4:
                            raise ValueError("v4 submission policy revision mismatch")
                        clauses = extract_statement_clauses(
                            fact.statement,
                            require_v4=True,
                        )
                        validate_quantifier_ledger(
                            fact.quantifier_ledger,
                            statement=fact.statement,
                            proof=fact.proof,
                            clause_ids={
                                item["clause_id"] for item in clauses
                            },
                        )
                        validate_predecessor_uses(
                            fact.predecessor_uses,
                            predecessors=fact.predecessors,
                            proof=fact.proof,
                            interface_lookup=(
                                lambda predecessor_id: self.statement_interface(
                                    predecessor_id,
                                    materialize=False,
                                )
                            ),
                            convention_profile_ids=fact.convention_profile_ids,
                        )
                        validate_computational_evidence(
                            fact.computational_evidence,
                            proof=fact.proof,
                            artifacts=payload.get("artifacts", []),
                            verification_plan=payload.get(
                                "verification_plan", {}
                            ),
                        )
                        validate_terminology(
                            fact.terminology,
                            proof=fact.proof,
                        )
                    stored_fact = facts.get(fact_id) or revoked_facts.get(fact_id)
                    if stored_fact is not None and (
                        stored_fact.as_submission_dict() != fact.as_submission_dict()
                    ):
                        raise ValueError("submission content does not match stored fact")
                else:
                    legacy_submissions += 1
                submissions[fact_id] = payload
            except Exception as exc:
                workflow_error(f"{path.name}: invalid submission: {exc}")
        report.candidates = sum(
            1
            for fact_id, payload in submissions.items()
            if (
                payload.get("evidence_version") in {2, 3, 4}
                and payload.get("status") == "pending_review"
            )
            or (
                payload.get("evidence_version") not in {2, 3, 4}
                and fact_id not in facts
            )
        )
        if legacy_submissions:
            message = (
                f"{legacy_submissions} legacy v1 submissions have no hash-bound state; "
                "preserved as historical evidence"
            )
            if is_v4:
                report.historical_workflow_warnings.append(message)
            else:
                report.warnings.append(message)
        if legacy_source_reliability_submissions:
            message = (
                f"{legacy_source_reliability_submissions} schema-v3 submissions predate tiered "
                "external-source evidence v3; preserve them as historical source trust and use a new "
                "submission for any corrected citation"
            )
            if is_v4:
                report.historical_workflow_warnings.append(message)
            else:
                report.warnings.append(message)

        valid_packets: dict[str, dict[str, Any]] = {}
        referenced_packet_hashes: set[str] = set()
        for path in sorted(self.packet_by_fact_dir.glob("*.json")):
            try:
                manifest = self._read_json(path)
                require_exact_keys(
                    manifest,
                    required={
                        "evidence_version",
                        "fact_id",
                        "submission_sha256",
                        "packet_sha256",
                        "packet_relpath",
                        "review_return_relpath",
                        "created_at",
                    },
                    label="packet manifest",
                )
                if manifest.get("evidence_version") not in {2, 3}:
                    raise ValueError("unsupported packet evidence version")
                fact_id = validate_fact_id(require_string(manifest, "fact_id"))
                if path.stem != fact_id:
                    raise ValueError("packet manifest filename/fact mismatch")
                submission = submissions.get(fact_id)
                if (
                    submission is None
                    or submission.get("evidence_version") != manifest.get("evidence_version")
                ):
                    raise ValueError("packet has no matching hash-bound submission")
                submission_sha = require_string(manifest, "submission_sha256")
                packet_sha = require_string(manifest, "packet_sha256")
                if SHA256_RE.fullmatch(submission_sha) is None or SHA256_RE.fullmatch(packet_sha) is None:
                    raise ValueError("packet hashes must be full SHA-256 values")
                if submission_sha != submission.get("submission_sha256"):
                    raise ValueError("packet/submission hash mismatch")
                packet_path = contained_path(
                    self.root,
                    require_string(manifest, "packet_relpath"),
                    "packet_relpath",
                )
                if packet_path.parent != self.packet_by_hash_dir or packet_path.name != f"{packet_sha}.md":
                    raise ValueError("packet path is not the canonical hash path")
                if not packet_path.is_file() or packet_path.is_symlink():
                    raise ValueError("packet path is not a regular file")
                if sha256_bytes(packet_path.read_bytes()) != packet_sha:
                    raise ValueError("packet bytes were modified")
                review_return = contained_path(
                    self.root,
                    require_string(manifest, "review_return_relpath"),
                    "review_return_relpath",
                )
                if review_return.parent != self.review_inbox_dir:
                    raise ValueError("review return path is outside review_inbox")
                valid_packets[fact_id] = manifest
                referenced_packet_hashes.add(packet_sha)
            except Exception as exc:
                workflow_error(f"{path.name}: invalid packet manifest: {exc}")
        for path in sorted(self.packet_by_hash_dir.glob("*.md")):
            if path.stem not in referenced_packet_hashes:
                workflow_error(f"{path.name}: frozen packet has no manifest")

        valid_reviews: dict[str, dict[str, Any]] = {}
        for path in sorted(self.reviews_by_id_dir.glob("*.json")):
            try:
                raw_review = self._read_json(path)
                is_v4_review = raw_review.get("schema_version") == 4
                review = (
                    self._validate_v4_review_record(raw_review)
                    if is_v4_review
                    else self._validate_review_record(raw_review)
                )
                if path.stem != review["review_id"]:
                    raise ValueError("review filename/id mismatch")
                submission = submissions.get(review["fact_id"])
                if submission is None:
                    raise ValueError("review has no submission")
                if review["submission_sha256"] != submission.get("submission_sha256"):
                    raise ValueError("review/submission hash mismatch")
                if is_v4_review:
                    if submission.get("evidence_version") != 4:
                        raise ValueError("v4 review has a non-v4 submission")
                    bundle_manifest = self.verification_bundles().verify(
                        review["bundle_sha256"]
                    )
                    if (
                        bundle_manifest["fact_id"] != review["fact_id"]
                        or bundle_manifest["submission_sha256"]
                        != review["submission_sha256"]
                    ):
                        raise ValueError("review/bundle/submission mismatch")
                else:
                    manifest = valid_packets.get(review["fact_id"])
                    if manifest is None:
                        raise ValueError("review has no valid frozen packet")
                    if review["packet_sha256"] != manifest.get("packet_sha256"):
                        raise ValueError("review/packet hash mismatch")
                    packet_path = contained_path(
                        self.root,
                        require_string(manifest, "packet_relpath"),
                        "packet_relpath",
                    )
                    if sha256_bytes(packet_path.read_bytes()) != review["packet_sha256"]:
                        raise ValueError("packet bytes were modified")
                worker = require_string(submission, "worker")
                if review["reviewer"].casefold() == worker.strip().casefold():
                    raise ValueError("reviewer is not independent of worker")
                review_ids = submission.get("review_ids", [])
                if review["review_id"] not in review_ids:
                    raise ValueError("review is not linked from its submission")
                valid_reviews[review["review_id"]] = review
            except Exception as exc:
                workflow_error(f"{path.name}: invalid immutable review: {exc}")
        legacy_reviews = list(self.reviews_dir.glob("*.json"))
        if legacy_reviews:
            report.warnings.append(
                f"{len(legacy_reviews)} legacy flat reviews are mutable and are not v2 attestations"
            )
        for fact_id, submission in submissions.items():
            if submission.get("evidence_version") not in {2, 3, 4}:
                continue
            review_ids = submission.get("review_ids", [])
            missing_review_ids = [
                review_id for review_id in review_ids if review_id not in valid_reviews
            ]
            if missing_review_ids:
                workflow_error(
                    f"{fact_id}: submission references missing/invalid reviews: "
                    + ", ".join(missing_review_ids)
                )
            last_review_id = submission.get("last_review_id")
            if review_ids and last_review_id != review_ids[-1]:
                workflow_error(f"{fact_id}: last_review_id does not match review order")
            if not review_ids and last_review_id is not None:
                workflow_error(f"{fact_id}: last_review_id exists without reviews")
            last_review = valid_reviews.get(last_review_id) if isinstance(last_review_id, str) else None
            if submission.get("status") == "rejected" and (
                last_review is None or last_review.get("verdict") != "reject"
            ):
                invalidated = submission.get("invalidated_by_revocation", [])
                if not isinstance(invalidated, list) or not invalidated or any(
                    item not in revoked_ids for item in invalidated
                ):
                    workflow_error(
                        f"{fact_id}: rejected submission has no latest rejecting review"
                    )
            if submission.get("status") == "pending_review" and last_review is not None and (
                last_review.get("verdict") != "correct"
                or (
                    bool(last_review.get("findings"))
                    if last_review.get("schema_version") == 4
                    else bool(last_review.get("critical_errors"))
                    or bool(last_review.get("gaps"))
                )
            ):
                workflow_error(f"{fact_id}: pending submission has a non-clean latest review")
            if submission.get("status") in {"accepted", "revoked"} and (
                submission.get("accepted_review_id") != last_review_id
            ):
                workflow_error(f"{fact_id}: accepted review is not the latest review")

        accepted_events: dict[str, list[dict[str, Any]]] = {}
        valid_hash_acceptances: set[str] = set()
        for event in self._read_jsonl(self.verification_log):
            if event.get("event") != "accepted":
                continue
            fact_id = str(event.get("fact_id", ""))
            accepted_events.setdefault(fact_id, []).append(event)
            evidence_kind = _acceptance_evidence_kind(event)
            if evidence_kind == "invalid":
                workflow_error(
                    f"acceptance event for {fact_id}: unsupported evidence_version"
                )
                continue
            if evidence_kind == "legacy":
                continue
            try:
                validate_fact_id(fact_id)
                review_id = validate_review_id(str(event.get("review_id", "")))
                review = valid_reviews[review_id]
                submission = submissions[fact_id]
                if event.get("evidence_version") != submission.get("evidence_version"):
                    raise ValueError("acceptance/submission evidence version mismatch")
                if event.get("evidence_version") == 4:
                    profile_closure = (
                        self.profile_closures().require_submission_ready(
                            submission
                        )
                    )
                    closure_sha = profile_closure.get("receipt_sha256")
                    if isinstance(closure_sha, str):
                        if (
                            event.get("profile_closure_id")
                            != profile_closure.get("closure_id")
                            or event.get("profile_closure_sha256")
                            != closure_sha
                        ):
                            raise ValueError(
                                "acceptance profile-closure binding mismatch"
                            )
                    elif {
                        "profile_closure_id",
                        "profile_closure_sha256",
                    }.intersection(event):
                        raise ValueError(
                            "acceptance binds a closure for a no-required-feature round"
                        )
                    expected_event_id = sha256_json(
                        [
                            "accepted-v4",
                            fact_id,
                            review_id,
                            review["bundle_sha256"],
                            *(
                                ["profile-closure", closure_sha]
                                if isinstance(closure_sha, str)
                                else []
                            ),
                        ]
                    )
                else:
                    expected_event_id = sha256_json(
                        ["accepted", fact_id, review_id]
                    )
                if event.get("event_id") != expected_event_id:
                    raise ValueError("acceptance event_id mismatch")
                if review["fact_id"] != fact_id:
                    raise ValueError("acceptance review belongs to another fact")
                if review["verdict"] != "correct" or (
                    bool(review.get("findings"))
                    if event.get("evidence_version") == 4
                    else bool(review.get("critical_errors"))
                    or bool(review.get("gaps"))
                ):
                    raise ValueError(
                        "acceptance is bound to a non-clean review"
                    )
                evidence_binding_keys = (
                    ("submission_sha256", "bundle_sha256")
                    if event.get("evidence_version") == 4
                    else ("submission_sha256", "packet_sha256")
                )
                for key in evidence_binding_keys:
                    if event.get(key) != review.get(key):
                        raise ValueError(f"acceptance {key} mismatch")
                if event.get("evidence_version") == 4:
                    prior_reviews = [
                        valid_reviews[item]
                        for item in submission.get("review_ids", [])
                        if item != review_id and item in valid_reviews
                    ]
                    admission_gate_v4(
                        review=review,
                        bundle_store=self.verification_bundles(),
                        prior_reviews=prior_reviews,
                    )
                if event.get("reviewer") != review["reviewer"]:
                    raise ValueError("acceptance reviewer mismatch")
                if event.get("evidence_version") in {3, 4}:
                    if event.get("claim_relation") != submission.get("claim_relation"):
                        raise ValueError("acceptance claim_relation mismatch")
                    expected_claim_sha = sha256_bytes(
                        str(submission.get("assigned_claim", "")).encode("utf-8")
                    )
                    if event.get("assigned_claim_sha256") != expected_claim_sha:
                        raise ValueError("acceptance assigned_claim hash mismatch")
                require_string(event, "gateway")
                historical_path = (
                    revoked_paths[fact_id]
                    if fact_id in revoked_ids
                    else self.active_fact_path(fact_id)
                )
                if event.get("fact_sha256") != sha256_bytes(historical_path.read_bytes()):
                    raise ValueError("accepted fact bytes were modified")
                if submission.get("accepted_review_id") != review_id:
                    raise ValueError("submission accepted_review_id mismatch")
                expected_status = "revoked" if fact_id in revoked_ids else "accepted"
                if submission.get("status") != expected_status:
                    raise ValueError("accepted submission status mismatch")
                stored_fact = revoked_facts.get(fact_id) or facts.get(fact_id)
                if stored_fact is None or (
                    stored_fact.as_submission_dict()
                    != Fact.from_dict(submission).as_submission_dict()
                ):
                    raise ValueError("accepted fact/submission content mismatch")
                valid_hash_acceptances.add(fact_id)
            except Exception as exc:
                workflow_error(f"acceptance event for {fact_id}: {exc}")
        for fact_id, events in accepted_events.items():
            hash_events = [
                event
                for event in events
                if _acceptance_evidence_kind(event) == "hash-bound"
            ]
            if len(hash_events) > 1:
                workflow_error(f"{fact_id}: duplicate hash-bound acceptance events")
        for fact_id, submission in submissions.items():
            if (
                submission.get("evidence_version") in {2, 3, 4}
                and submission.get("status") in {"accepted", "revoked"}
                and fact_id not in valid_hash_acceptances
            ):
                workflow_error(
                    f"{fact_id}: accepted/revoked submission has no valid hash-bound acceptance"
                )
        legacy_acceptances = sum(
            1
            for events in accepted_events.values()
            for event in events
            if _acceptance_evidence_kind(event) == "legacy"
        )
        if legacy_acceptances:
            report.warnings.append(
                f"{legacy_acceptances} legacy acceptance events lack packet/submission hashes"
            )

        revocation_events: dict[str, list[dict[str, Any]]] = {}
        for event in self._read_jsonl(self.revocation_log):
            fact_id = str(event.get("fact_id", ""))
            revocation_events.setdefault(fact_id, []).append(event)
            try:
                validate_fact_id(fact_id)
                root_fact_id = validate_fact_id(require_string(event, "root_fact_id"))
                reason = require_string(event, "reason")
                require_string(event, "actor")
                expected = sha256_json(["revoked", fact_id, root_fact_id, reason])
                if event.get("event_id") != expected:
                    raise ValueError("revocation event_id mismatch")
            except Exception as exc:
                workflow_error(f"revocation event for {fact_id}: {exc}")
        for fact_id in revoked_ids:
            if len(revocation_events.get(fact_id, [])) != 1:
                workflow_error(f"{fact_id}: revoked fact must have exactly one revocation event")

        imported_ids: set[str] = set()
        for path in self.imports_dir.glob("*.json"):
            try:
                receipt = self._read_json(path)
                if receipt.get("project_id") not in {None, project_id}:
                    raise ValueError("import receipt belongs to another project")
                imported_ids.update(str(item) for item in receipt.get("facts", []))
            except Exception as exc:
                workflow_error(f"{path.name}: invalid import receipt: {exc}")
        valid_bundle_acceptance_ids: set[str] = set()
        if is_v4:
            (
                valid_bundle_acceptance_ids,
                fact_bundle_provenance_errors,
            ) = self._validated_fact_bundle_provenance_ids()
            for message in fact_bundle_provenance_errors:
                workflow_error(f"fact bundle profile closure {message}")
        legacy_accepted_ids = {
            fact_id
            for fact_id, events in accepted_events.items()
            if any(
                _acceptance_evidence_kind(event) == "legacy"
                for event in events
            )
        }
        locally_accepted = (
            valid_hash_acceptances
            | valid_bundle_acceptance_ids
            | legacy_accepted_ids
        )
        unprovenanced = sorted(set(facts).difference(imported_ids | locally_accepted))
        for fact_id in unprovenanced:
            workflow_error(f"verified fact has no admission/import provenance: {fact_id}")

        memory = self.memory_latest()
        report.memory_entries = len(memory)
        legacy_memory_statuses = 0
        legacy_memory_resolutions = 0
        legacy_memory_relations = 0
        for entry_id, entry in memory.items():
            if MEMORY_ID_RE.fullmatch(entry_id) is None:
                workflow_error(f"memory id is not canonical: {entry_id!r}")
                continue
            if entry.get("kind") not in MEMORY_KINDS:
                workflow_error(f"memory {entry_id} has invalid kind {entry.get('kind')!r}")
            if not isinstance(entry.get("claim"), str) or not entry.get("claim", "").strip():
                workflow_error(f"memory {entry_id} has no nonempty claim")
            dependencies = entry.get("dependencies", [])
            if not isinstance(dependencies, list) or any(
                not isinstance(item, str) or FACT_ID_RE.fullmatch(item) is None
                for item in dependencies
            ):
                workflow_error(f"memory {entry_id} has invalid dependencies")
                dependencies = []
            unknown_dependencies = set(dependencies).difference(facts).difference(revoked_ids)
            if unknown_dependencies:
                workflow_error(
                    f"memory {entry_id} cites unknown dependencies: "
                    + ", ".join(sorted(unknown_dependencies))
                )
            revoked_dependencies = set(dependencies).intersection(revoked_ids)
            if revoked_dependencies and entry.get("status") in ACTIVE_MEMORY_STATUSES:
                report.warnings.append(
                    f"memory {entry_id} is active but depends on revoked facts: "
                    + ", ".join(sorted(revoked_dependencies))
                )
            status = entry.get("status")
            if status not in MEMORY_STATUSES:
                if schema_version < 2:
                    legacy_memory_statuses += 1
                else:
                    workflow_error(f"memory {entry_id} has invalid status {status!r}")
            resolution = entry.get("resolution_fact_id")
            if status in _STATUS_RELATIONS and resolution not in facts:
                if schema_version < 2 and resolution is None:
                    legacy_memory_resolutions += 1
                else:
                    workflow_error(f"memory {entry_id} has no verified resolution fact")
            if status not in _STATUS_RELATIONS and resolution is not None:
                workflow_error(f"memory {entry_id} has an invalid resolution_fact_id")
            relation = entry.get("claim_relation")
            related_fact_id = entry.get("related_fact_id")
            if relation is not None:
                if relation not in CLAIM_RELATIONS:
                    workflow_error(f"memory {entry_id} has invalid claim_relation")
                if related_fact_id not in facts:
                    workflow_error(f"memory {entry_id} has no admitted related fact")
            elif related_fact_id is not None:
                workflow_error(f"memory {entry_id} has related_fact_id without claim_relation")
            if status in _STATUS_RELATIONS and resolution in facts:
                allowed = _STATUS_RELATIONS[status]
                if relation is None:
                    resolution_submission = submissions.get(str(resolution), {})
                    if resolution_submission.get("evidence_version") == 2:
                        legacy_memory_relations += 1
                    else:
                        workflow_error(
                            f"memory {entry_id} fact resolution has no claim_relation"
                        )
                elif relation not in allowed or related_fact_id != resolution:
                    workflow_error(
                        f"memory {entry_id} status/relation/fact semantics disagree"
                    )
            for field in (
                "parent_memory_id",
                "repair_of_memory_id",
                "trigger_memory_id",
            ):
                referenced = entry.get(field)
                if referenced is not None and referenced not in memory:
                    workflow_error(
                        f"memory {entry_id} has unknown {field} {referenced!r}"
                    )
        if legacy_memory_statuses:
            report.warnings.append(
                f"{legacy_memory_statuses} legacy memory statuses are noncanonical and read-only"
            )
        if legacy_memory_resolutions:
            report.warnings.append(
                f"{legacy_memory_resolutions} legacy fact-resolved memory entries do not name "
                "their resolution fact and are retained as historical state"
            )
        if legacy_memory_relations:
            report.warnings.append(
                f"{legacy_memory_relations} schema-v2 fact resolutions have no typed "
                "claim_relation; retained as historical state"
            )

        novelty_events = self._read_jsonl(self.novelty_log)
        report.novelty_entries = len(novelty_events)
        for index, event in enumerate(novelty_events, 1):
            try:
                if event.get("event") != "novelty-query":
                    raise ValueError("invalid event kind")
                subject_kind = require_string(event, "subject_kind")
                subject_id = require_string(event, "subject_id")
                if subject_kind == "fact":
                    validate_fact_id(subject_id)
                    if subject_id not in facts and subject_id not in revoked_ids:
                        raise ValueError("unknown fact subject")
                elif subject_kind == "memory":
                    validate_memory_id(subject_id)
                    if subject_id not in memory:
                        raise ValueError("unknown memory subject")
                else:
                    raise ValueError("invalid subject_kind")
                status = require_string(event, "status")
                if status not in NOVELTY_STATUSES:
                    raise ValueError("invalid novelty status")
                require_string(event, "corpus")
                require_string(event, "query")
                require_string(event, "actor")
                require_string(event, "searched_at")
                hits = event.get("hits")
                if not isinstance(hits, list):
                    raise ValueError("hits is not a list")
                for hit in hits:
                    if not isinstance(hit, dict):
                        raise ValueError("hit is not an object")
                    require_exact_keys(
                        hit,
                        required={"title", "locator", "relation"},
                        label="novelty hit",
                    )
                    require_string(hit, "title")
                    require_string(hit, "locator")
                    if require_string(hit, "relation") not in {
                        "exact",
                        "partial",
                        "background",
                    }:
                        raise ValueError("invalid hit relation")
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
                workflow_error(f"novelty event {index}: {exc}")

        legacy_rounds = 0
        for round_path in sorted(self.rounds_dir.glob("*/round.json")):
            round_id = round_path.parent.name
            try:
                manifest = self._read_json(round_path)
                round_schema = manifest.get("schema_version")
                if round_schema == 4:
                    if not is_v4:
                        raise ValueError("v4 round exists in a non-v4 project")
                    continue
                if round_schema not in {2, 3}:
                    legacy_rounds += 1
                    continue
                require_exact_keys(
                    manifest,
                    required={
                        "schema_version",
                        "project_id",
                        "round_id",
                        "created_at",
                        "assignments",
                    },
                    label="round manifest",
                )
                validate_round_id(round_id)
                if manifest.get("round_id") != round_id:
                    raise ValueError("round directory/manifest id mismatch")
                if manifest.get("project_id") != project_id:
                    raise ValueError("round belongs to another project")
                require_string(manifest, "created_at")
                assignments = manifest.get("assignments")
                if not isinstance(assignments, list) or not assignments:
                    raise ValueError("round assignments must be a nonempty list")
                seen_assignment_ids: set[str] = set()
                expected_returns: set[Path] = set()
                expected_receipts: set[Path] = set()
                expected_artifact_dirs: set[Path] = set()
                for assignment in assignments:
                    if not isinstance(assignment, dict):
                        raise ValueError("round assignment must be an object")
                    v3_fields = {"artifact_dir_relpath"} if round_schema == 3 else set()
                    require_exact_keys(
                        assignment,
                        required={
                            "assignment_id",
                            "memory_id",
                            "mode",
                            "worker_id",
                            "prompt_relpath",
                            "return_relpath",
                            "assignment_sha256",
                            "prompt_sha256",
                            "contract",
                        }
                        | v3_fields,
                        label="round assignment",
                    )
                    assignment_id = validate_assignment_id(
                        require_string(assignment, "assignment_id")
                    )
                    if assignment_id in seen_assignment_ids:
                        raise ValueError("duplicate assignment id")
                    seen_assignment_ids.add(assignment_id)
                    memory_id = validate_memory_id(require_string(assignment, "memory_id"))
                    if memory_id not in memory:
                        raise ValueError("assignment references unknown memory")
                    mode = require_string(assignment, "mode")
                    if mode not in {"prove", "refute", "compute", "literature"}:
                        raise ValueError("invalid assignment mode")
                    if assignment.get("worker_id") != assignment_id:
                        raise ValueError("assignment worker/id mismatch")
                    assignment_sha = require_string(assignment, "assignment_sha256")
                    prompt_sha = require_string(assignment, "prompt_sha256")
                    if SHA256_RE.fullmatch(assignment_sha) is None or SHA256_RE.fullmatch(prompt_sha) is None:
                        raise ValueError("assignment hashes must be full SHA-256 values")
                    contract = assignment.get("contract")
                    if not isinstance(contract, dict):
                        raise ValueError("assignment contract must be an object")
                    contract_v3_fields = (
                        {"artifact_dir_relpath"} if round_schema == 3 else set()
                    )
                    require_exact_keys(
                        contract,
                        required={
                            "project_id",
                            "round_id",
                            "assignment_id",
                            "memory_id",
                            "mode",
                            "worker_id",
                            "claim",
                            "rationale",
                            "dependencies",
                            "return_relpath",
                        }
                        | contract_v3_fields,
                        optional={"source"},
                        label="assignment contract",
                    )
                    if sha256_json(contract) != assignment_sha:
                        raise ValueError("assignment contract hash mismatch")
                    binding_pairs = [
                        ("project_id", project_id),
                        ("round_id", round_id),
                        ("assignment_id", assignment_id),
                        ("memory_id", memory_id),
                        ("mode", mode),
                        ("worker_id", assignment_id),
                        ("return_relpath", assignment["return_relpath"]),
                    ]
                    if round_schema == 3:
                        binding_pairs.append(
                            (
                                "artifact_dir_relpath",
                                assignment["artifact_dir_relpath"],
                            )
                        )
                    for key, expected in binding_pairs:
                        if contract.get(key) != expected:
                            raise ValueError(f"assignment contract {key} mismatch")
                    prompt_path = contained_path(
                        round_path.parent,
                        require_string(assignment, "prompt_relpath"),
                        "prompt_relpath",
                    )
                    return_path = contained_path(
                        round_path.parent,
                        require_string(assignment, "return_relpath"),
                        "return_relpath",
                    )
                    if prompt_path != round_path.parent / "assignments" / f"{assignment_id}.md":
                        raise ValueError("assignment prompt path is noncanonical")
                    if return_path != round_path.parent / "returns" / f"{assignment_id}.json":
                        raise ValueError("assignment return path is noncanonical")
                    artifact_dir: Path | None = None
                    if round_schema == 3:
                        artifact_dir = contained_path(
                            self.root,
                            require_string(assignment, "artifact_dir_relpath"),
                            "artifact_dir_relpath",
                        )
                        expected_artifact_dir = (
                            round_path.parent / "artifacts" / assignment_id
                        )
                        if artifact_dir != expected_artifact_dir:
                            raise ValueError("assignment artifact directory is noncanonical")
                        if (
                            not artifact_dir.is_dir()
                            or artifact_dir.is_symlink()
                        ):
                            raise ValueError(
                                "assignment artifact directory is missing or not regular"
                            )
                        expected_artifact_dirs.add(artifact_dir)
                    if not prompt_path.is_file() or prompt_path.is_symlink():
                        raise ValueError("assignment prompt is missing or not regular")
                    if sha256_bytes(prompt_path.read_bytes()) != prompt_sha:
                        raise ValueError("assignment prompt hash mismatch")
                    receipt_path = return_path.with_suffix(".receipt.json")
                    expected_returns.add(return_path)
                    expected_receipts.add(receipt_path)
                    if receipt_path.exists() and not return_path.exists():
                        raise ValueError("ingest receipt exists without worker return")
                    if not return_path.exists():
                        continue
                    if not return_path.is_file() or return_path.is_symlink():
                        raise ValueError("worker return is not a regular file")
                    return_bytes = return_path.read_bytes()
                    returned = json.loads(return_bytes.decode("utf-8"))
                    if not isinstance(returned, dict):
                        raise ValueError("worker return is not an object")
                    outcome, artifacts = validate_worker_return(
                        returned,
                        assignment,
                        manifest,
                        project_root=self.root,
                        historical_policy=is_v4,
                    )
                    if round_schema == 3 and artifact_dir is not None:
                        declared_paths = {
                            contained_path(self.root, item["path"], "artifact path")
                            for item in artifacts
                        }
                        actual_paths = {
                            path
                            for path in artifact_dir.rglob("*")
                            if path.is_file() or path.is_symlink()
                        }
                        if any(path.is_symlink() for path in actual_paths):
                            raise ValueError("artifact directory contains a symlink")
                        unexpected_artifacts = actual_paths.difference(declared_paths)
                        missing_artifacts = declared_paths.difference(actual_paths)
                        if unexpected_artifacts:
                            raise ValueError(
                                "undeclared artifact files: "
                                + ", ".join(
                                    sorted(path.relative_to(artifact_dir).as_posix()
                                           for path in unexpected_artifacts)
                                )
                            )
                        if missing_artifacts:
                            raise ValueError("declared artifact file is missing")
                    if not receipt_path.exists():
                        if any(
                            submission.get("round_id") == round_id
                            and submission.get("assignment_id") == assignment_id
                            for submission in submissions.values()
                        ):
                            raise ValueError("assignment effect exists without an ingest receipt")
                        continue
                    if not receipt_path.is_file() or receipt_path.is_symlink():
                        raise ValueError("ingest receipt is not a regular file")
                    receipt = self._read_json(receipt_path)
                    for key, expected in (
                        ("schema_version", round_schema),
                        ("project_id", project_id),
                        ("round_id", round_id),
                        ("assignment_id", assignment_id),
                        ("assignment_sha256", assignment_sha),
                        ("return_relpath", assignment["return_relpath"]),
                        ("return_sha256", sha256_bytes(return_bytes)),
                        ("outcome", outcome),
                        ("status", "ingested"),
                    ):
                        if receipt.get(key) != expected:
                            raise ValueError(f"ingest receipt {key} mismatch")
                    if round_schema == 3 and receipt.get("artifacts") != artifacts:
                        raise ValueError("ingest receipt artifact manifest mismatch")
                    if receipt.get("return_locked") is True:
                        if receipt.get("worker_final_sha256") != sha256_bytes(
                            return_bytes
                        ):
                            raise ValueError(
                                "ingest receipt worker final SHA-256 mismatch"
                            )
                        if return_path.stat().st_mode & 0o222:
                            raise ValueError(
                                "finalized worker return is not read-only"
                            )
                        for artifact in artifacts:
                            artifact_path = contained_path(
                                self.root, artifact["path"], "artifact path"
                            )
                            if artifact_path.stat().st_mode & 0o222:
                                raise ValueError(
                                    "finalized artifact is not read-only"
                                )
                    elif "worker_final_sha256" in receipt or "return_locked" in receipt:
                        raise ValueError(
                            "ingest receipt has an incomplete worker-finalization record"
                        )
                    if outcome == "fact_submission":
                        submission_id = validate_fact_id(
                            require_string(receipt, "submission_id")
                        )
                        submitted = submissions.get(submission_id)
                        if submitted is None:
                            raise ValueError("receipt submission does not exist")
                        if submitted.get("round_id") != round_id or submitted.get("assignment_id") != assignment_id:
                            raise ValueError("receipt submission is not assignment-bound")
                    else:
                        effect_id = validate_memory_id(
                            require_string(receipt, "memory_entry_id")
                        )
                        if effect_id not in memory:
                            raise ValueError("receipt memory effect does not exist")
                returns_dir = round_path.parent / "returns"
                actual_returns = {
                    path for path in returns_dir.glob("*.json") if not path.name.endswith(".receipt.json")
                }
                actual_receipts = set(returns_dir.glob("*.receipt.json"))
                for unexpected in sorted(actual_returns.difference(expected_returns)):
                    raise ValueError(f"unassigned worker return: {unexpected.name}")
                for unexpected in sorted(actual_receipts.difference(expected_receipts)):
                    raise ValueError(f"unassigned ingest receipt: {unexpected.name}")
                if round_schema == 3:
                    artifacts_root = round_path.parent / "artifacts"
                    if not artifacts_root.is_dir() or artifacts_root.is_symlink():
                        raise ValueError("round artifact root is missing or not regular")
                    actual_artifact_dirs = {
                        path for path in artifacts_root.iterdir() if path.is_dir()
                    }
                    unexpected_dirs = actual_artifact_dirs.difference(
                        expected_artifact_dirs
                    )
                    if unexpected_dirs:
                        raise ValueError(
                            "unassigned artifact directories: "
                            + ", ".join(sorted(path.name for path in unexpected_dirs))
                        )
            except Exception as exc:
                workflow_error(f"{round_id}: invalid round workflow: {exc}")
        if legacy_rounds:
            message = (
                f"{legacy_rounds} legacy round manifests are retained as historical state"
            )
            if is_v4:
                report.historical_workflow_warnings.append(message)
            else:
                report.warnings.append(message)
        if is_v4:
            self._audit_v4_components(
                report,
                facts=facts,
                project_id=project_id,
            )
        return report

from __future__ import annotations

import json
import os
import re
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Callable, ContextManager

from .blackboard import BlackboardStore
from .contracts import (
    POLICY_REVISION_V4,
    SHA256_RE,
    canonical_json_bytes,
    contained_path,
    require_exact_keys,
    require_string,
    sha256_bytes,
    sha256_json,
    validate_assignment_id,
    validate_bb_node_id,
    validate_bb_snapshot_id,
    validate_round_id,
)
from .protocol import (
    DEFAULT_HARD_CAPS,
    validate_ingestion_receipt_v4,
    validate_task_card,
)
from .modes import require_unaborted_work_unit


PULSE_ID_RE = re.compile(r"bbp-[0-9a-f]{64}")
COMMITMENT_ID_RE = re.compile(r"bbpc-[0-9a-f]{64}")
BARRIER_ID_RE = re.compile(r"bbbar-[0-9a-f]{64}")
CLOSURE_ID_RE = re.compile(r"bbclose-[0-9a-f]{64}")
VOID_ID_RE = re.compile(r"bbvoid-[0-9a-f]{64}")
ABORT_ID_RE = re.compile(r"bbabort-[0-9a-f]{64}")
CORE_FAILURE_ID_RE = re.compile(r"bbfail-[0-9a-f]{64}")
HOST_DISPATCH_ID_RE = re.compile(r"bbhost-[0-9a-f]{64}")
FRESH_CONTEXT_CONTRACT_V1 = {
    "schema_version": 1,
    "prior_worker_context_inherited": False,
    "orchestrator_expected_answer_provided": False,
}

CRITICALITIES = {"core", "optional"}
MEANINGFUL_EDGE_TYPES = {
    "challenges",
    "refines",
    "duplicates",
    "supports_candidate",
}
CHECK_KINDS = {
    "independent_reproduction",
    "scope_audit",
    "counterexample_search",
    "deduplication",
}
DISPOSITIONS = {
    "correction",
    "no_correction",
    "conflict",
    "duplicate",
}
RELATION_DISPOSITIONS = {
    "challenges": {"correction", "conflict"},
    "refines": {"correction", "no_correction"},
    "duplicates": {"duplicate"},
    "supports_candidate": {"no_correction"},
}
NON_PEER_NODE_TYPES = {
    "space",
    "note",
    "intuition",
    "fact_interface_mirror",
    "type_registry",
}

_WAVE1_COMMITMENT_FIELDS = {
    "commitment_id",
    "phase",
    "project_id",
    "round_id",
    "assignment_id",
    "criticality",
    "minimum_peer_nodes",
}
_REVIEW_COMMITMENT_FIELDS = {
    "commitment_id",
    "phase",
    "pulse_id",
    "project_id",
    "peer_project_id",
    "round_id",
    "assignment_id",
    "peer_node_id",
    "criticality",
    "allowed_edge_types",
}
_PLAN_FIELDS = {
    "schema_version",
    "policy_revision",
    "project_id",
    "pulse_id",
    "actor",
    "host_task_scope_id",
    "campaign_id",
    "wave1_snapshot_id",
    "wave1_snapshot_sha256",
    "minimum_wave1_contributors",
    "wave1_commitments",
    "federation",
    "trusted_host_issuers",
}
_VOID_FIELDS = {
    "schema_version",
    "policy_revision",
    "project_id",
    "pulse_id",
    "commitment_id",
    "phase",
    "actor",
    "reason",
    "void_id",
}
_ABORT_FIELDS = {
    "schema_version",
    "policy_revision",
    "project_id",
    "pulse_id",
    "plan_sha256",
    "failure_phase",
    "actor",
    "reason",
    "abort_id",
}
_ABORT_CORE_FAILURE_FIELDS = {
    "core_failure_id",
    "core_failure_sha256",
}
_CORE_FAILURE_FIELDS = {
    "schema_version",
    "policy_revision",
    "project_id",
    "pulse_id",
    "plan_sha256",
    "commitment_id",
    "phase",
    "round_id",
    "assignment_id",
    "return_relpath",
    "return_sha256",
    "worker_final_sha256",
    "error_class",
    "error_message",
    "actor",
    "failure_id",
}
_BARRIER_FIELDS = {
    "schema_version",
    "policy_revision",
    "project_id",
    "pulse_id",
    "plan_sha256",
    "barrier_index",
    "wave1_snapshot_id",
    "after_snapshot_id",
    "after_snapshot_sha256",
    "wave1_evidence",
    "wave1_void_ids",
    "peer_nodes",
    "review_commitments",
    "actor",
    "barrier_id",
}
_CLOSURE_FIELDS = {
    "schema_version",
    "policy_revision",
    "project_id",
    "pulse_id",
    "plan_sha256",
    "barrier_id",
    "barrier_sha256",
    "review_evidence",
    "optional_void_ids",
    "procedural_ready",
    "machine_verified_ready",
    "blockers",
    "truth_boundary",
    "actor",
    "closure_id",
}
_HOST_DISPATCH_FIELDS = {
    "schema_version",
    "policy_revision",
    "project_id",
    "pulse_id",
    "barrier_id",
    "commitment_id",
    "round_id",
    "assignment_id",
    "prompt_sha256",
    "issuer",
    "host_task_scope_id",
    "host_context_id",
    "agent_identity",
    "fresh_context_contract",
    "clean_context",
    "dispatch_id",
}


def _content_id(prefix: str, payload: dict[str, Any], id_key: str) -> str:
    return prefix + sha256_json(
        {key: value for key, value in payload.items() if key != id_key}
    )


def _positive_integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(f"{label} must be a list of nonempty strings")
    return list(value)


class PulseStore:
    """Cooperative, project-local evidence for a two-wave blackboard pulse.

    A pulse is control-plane evidence, never a fact or a blackboard truth
    object.  Plans are immutable.  Barrier and closure receipts are derived
    from frozen round manifests, final ingestion receipts, and currently
    visible content-addressed blackboard objects.

    This module deliberately has no network federation implementation.  Every
    peer endpoint must resolve in the same project-local blackboard.
    """

    def __init__(
        self,
        project_root: Path | str,
        *,
        mutation_lock: Callable[[], ContextManager[Any]] | None = None,
        trusted_host_issuers: set[str] | list[str] | tuple[str, ...] = (),
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.root = (
            self.project_root / "blackboard" / "pulses" / "by-hash"
        )
        self.blackboard = BlackboardStore(self.project_root)
        self._mutation_lock = mutation_lock or nullcontext
        self.trusted_host_issuers = tuple(
            sorted(set(trusted_host_issuers))
        )
        if any(
            not isinstance(item, str) or not item.strip()
            for item in self.trusted_host_issuers
        ):
            raise ValueError(
                "trusted_host_issuers must contain nonempty strings"
            )

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"missing or unsafe pulse evidence: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"pulse evidence is not one JSON object: {path}")
        return payload

    @staticmethod
    def _encoded_json(payload: dict[str, Any]) -> bytes:
        return (
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")

    @staticmethod
    def _write_json_once(path: Path, payload: dict[str, Any]) -> None:
        encoded = PulseStore._encoded_json(payload)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            raise ValueError(f"refusing to write through symlink: {path}")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(path, flags, 0o600)
        except FileExistsError:
            if (
                not path.is_file()
                or path.is_symlink()
                or path.read_bytes() != encoded
            ):
                raise ValueError(f"immutable pulse evidence collision: {path}")
            return
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            raise

    def _pulse_control_inventory(self) -> tuple[int, int]:
        count = 0
        total = 0
        if not self.root.exists():
            return count, total
        for path in sorted(self.root.rglob("*.json")):
            if not path.is_file() or path.is_symlink():
                raise ValueError(
                    "pulse control inventory contains an unsafe entry"
                )
            count += 1
            size = path.stat().st_size
            if size > DEFAULT_HARD_CAPS[
                "max_pulse_control_bytes_each"
            ]:
                raise ValueError(
                    "existing pulse control record exceeds the per-file cap"
                )
            total += size
        return count, total

    def _write_control_record(
        self,
        path: Path,
        payload: dict[str, Any],
    ) -> None:
        self._write_control_records([(path, payload)])

    def _write_control_records(
        self,
        records: list[tuple[Path, dict[str, Any]]],
    ) -> None:
        """Preflight one logical control transaction before any marker."""

        if not records:
            return
        paths = [path for path, _ in records]
        if len(paths) != len(set(paths)):
            raise ValueError("pulse control transaction repeats a path")
        pending: list[tuple[Path, dict[str, Any], bytes]] = []
        for path, payload in records:
            encoded = self._encoded_json(payload)
            if path.exists() or path.is_symlink():
                if (
                    not path.is_file()
                    or path.is_symlink()
                    or path.read_bytes() != encoded
                ):
                    raise ValueError(
                        f"immutable pulse evidence collision: {path}"
                    )
                continue
            if len(encoded) > DEFAULT_HARD_CAPS[
                "max_pulse_control_bytes_each"
            ]:
                raise ValueError(
                    "pulse control record exceeds the per-file hard cap"
                )
            pending.append((path, payload, encoded))
        if not pending:
            return
        count, total = self._pulse_control_inventory()
        if count + len(pending) > DEFAULT_HARD_CAPS[
            "max_pulse_control_records"
        ]:
            raise ValueError(
                "pulse control record count hard cap exceeded"
            )
        if total + sum(len(encoded) for _, _, encoded in pending) > DEFAULT_HARD_CAPS[
            "max_pulse_control_bytes_total"
        ]:
            raise ValueError(
                "pulse control total-byte hard cap exceeded"
            )
        for path, payload, _ in pending:
            self._write_json_once(path, payload)

    def _project_id(self) -> str:
        project = self._read_json(self.project_root / "project.json")
        if project.get("workflow_evidence_version") != 4:
            raise ValueError("collaboration pulses require workflow evidence v4")
        if project.get("policy_revision") != POLICY_REVISION_V4:
            raise ValueError("project policy revision does not support pulses")
        return require_string(project, "project_id")

    def _require_commitments_active(
        self,
        commitments: list[dict[str, Any]],
    ) -> None:
        round_ids = {
            require_string(item, "round_id") for item in commitments
        }
        for round_id in sorted(round_ids):
            require_unaborted_work_unit(self.project_root, round_id)

    def _require_plan_work_units_active(
        self,
        plan: dict[str, Any],
        *,
        barrier: dict[str, Any] | None = None,
    ) -> None:
        commitments = list(plan["wave1_commitments"])
        if barrier is not None:
            commitments.extend(barrier["review_commitments"])
        self._require_commitments_active(commitments)

    def _pulse_dir(self, pulse_id: str) -> Path:
        if not isinstance(pulse_id, str) or PULSE_ID_RE.fullmatch(pulse_id) is None:
            raise ValueError("invalid collaboration pulse id")
        return self.root / pulse_id

    def _plan_path(self, pulse_id: str) -> Path:
        return self._pulse_dir(pulse_id) / "plan.json"

    def _barrier_path(self, pulse_id: str) -> Path:
        return self._pulse_dir(pulse_id) / "barrier.json"

    def _closure_path(self, pulse_id: str) -> Path:
        return self._pulse_dir(pulse_id) / "closure.json"

    def _abort_path(self, pulse_id: str) -> Path:
        return self._pulse_dir(pulse_id) / "abort.json"

    def _core_failure_path(
        self,
        pulse_id: str,
        commitment_id: str,
    ) -> Path:
        if (
            not isinstance(commitment_id, str)
            or COMMITMENT_ID_RE.fullmatch(commitment_id) is None
        ):
            raise ValueError("invalid collaboration commitment id")
        return (
            self._pulse_dir(pulse_id)
            / "core-failures"
            / f"{commitment_id}.json"
        )

    def _void_path(self, pulse_id: str, commitment_id: str) -> Path:
        if (
            not isinstance(commitment_id, str)
            or COMMITMENT_ID_RE.fullmatch(commitment_id) is None
        ):
            raise ValueError("invalid collaboration commitment id")
        return self._pulse_dir(pulse_id) / "voids" / f"{commitment_id}.json"

    def _dispatch_path(
        self,
        pulse_id: str,
        commitment_id: str,
    ) -> Path:
        if (
            not isinstance(commitment_id, str)
            or COMMITMENT_ID_RE.fullmatch(commitment_id) is None
        ):
            raise ValueError("invalid collaboration commitment id")
        return (
            self._pulse_dir(pulse_id)
            / "host-dispatches"
            / f"{commitment_id}.json"
        )

    def make_wave1_commitment(
        self,
        *,
        round_id: str,
        assignment_id: str,
        criticality: str = "core",
        minimum_peer_nodes: int = 1,
    ) -> dict[str, Any]:
        project_id = self._project_id()
        body = {
            "phase": "wave1",
            "project_id": project_id,
            "round_id": validate_round_id(round_id),
            "assignment_id": validate_assignment_id(assignment_id),
            "criticality": criticality,
            "minimum_peer_nodes": _positive_integer(
                minimum_peer_nodes,
                "minimum_peer_nodes",
            ),
        }
        if criticality not in CRITICALITIES:
            raise ValueError("commitment criticality must be core or optional")
        return {
            **body,
            "commitment_id": _content_id(
                "bbpc-",
                body,
                "commitment_id",
            ),
        }

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
        plan = self.plan(pulse_id)
        project_id = plan["project_id"]
        peer_project_id = peer_project_id or project_id
        if peer_project_id != project_id:
            raise ValueError(
                "federation is disabled; raw cross-project peer endpoints "
                "are forbidden"
            )
        edge_types = sorted(
            set(allowed_edge_types or MEANINGFUL_EDGE_TYPES)
        )
        if (
            not edge_types
            or not set(edge_types).issubset(MEANINGFUL_EDGE_TYPES)
        ):
            raise ValueError(
                "review commitment has unsupported meaningful edge types"
            )
        if criticality not in CRITICALITIES:
            raise ValueError("commitment criticality must be core or optional")
        body = {
            "phase": "wave2_cross_review",
            "pulse_id": pulse_id,
            "project_id": project_id,
            "peer_project_id": peer_project_id,
            "round_id": validate_round_id(round_id),
            "assignment_id": validate_assignment_id(assignment_id),
            "peer_node_id": validate_bb_node_id(peer_node_id),
            "criticality": criticality,
            "allowed_edge_types": edge_types,
        }
        return {
            **body,
            "commitment_id": _content_id(
                "bbpc-",
                body,
                "commitment_id",
            ),
        }

    def _validate_wave1_commitment(
        self,
        commitment: dict[str, Any],
        *,
        project_id: str,
    ) -> dict[str, Any]:
        require_exact_keys(
            commitment,
            required=_WAVE1_COMMITMENT_FIELDS,
            label="wave-1 commitment",
        )
        if (
            commitment.get("phase") != "wave1"
            or commitment.get("project_id") != project_id
        ):
            raise ValueError("wave-1 commitment binding mismatch")
        validate_round_id(require_string(commitment, "round_id"))
        validate_assignment_id(require_string(commitment, "assignment_id"))
        if commitment.get("criticality") not in CRITICALITIES:
            raise ValueError("wave-1 commitment criticality is invalid")
        _positive_integer(
            commitment.get("minimum_peer_nodes"),
            "wave-1 minimum_peer_nodes",
        )
        commitment_id = require_string(commitment, "commitment_id")
        if (
            COMMITMENT_ID_RE.fullmatch(commitment_id) is None
            or commitment_id
            != _content_id("bbpc-", commitment, "commitment_id")
        ):
            raise ValueError("wave-1 commitment id/hash mismatch")
        return commitment

    def _validate_review_commitment(
        self,
        commitment: dict[str, Any],
        *,
        plan: dict[str, Any],
    ) -> dict[str, Any]:
        require_exact_keys(
            commitment,
            required=_REVIEW_COMMITMENT_FIELDS,
            label="cross-review commitment",
        )
        project_id = plan["project_id"]
        if (
            commitment.get("phase") != "wave2_cross_review"
            or commitment.get("pulse_id") != plan["pulse_id"]
            or commitment.get("project_id") != project_id
        ):
            raise ValueError("cross-review commitment binding mismatch")
        if commitment.get("peer_project_id") != project_id:
            raise ValueError(
                "federation is disabled; raw cross-project peer endpoints "
                "are forbidden"
            )
        validate_round_id(require_string(commitment, "round_id"))
        validate_assignment_id(require_string(commitment, "assignment_id"))
        validate_bb_node_id(require_string(commitment, "peer_node_id"))
        if commitment.get("criticality") not in CRITICALITIES:
            raise ValueError("cross-review commitment criticality is invalid")
        allowed = _string_list(
            commitment.get("allowed_edge_types"),
            "cross-review allowed_edge_types",
        )
        if len(allowed) != len(set(allowed)) or not set(allowed).issubset(
            MEANINGFUL_EDGE_TYPES
        ):
            raise ValueError(
                "cross-review allowed_edge_types are invalid"
            )
        commitment_id = require_string(commitment, "commitment_id")
        if (
            COMMITMENT_ID_RE.fullmatch(commitment_id) is None
            or commitment_id
            != _content_id("bbpc-", commitment, "commitment_id")
        ):
            raise ValueError("cross-review commitment id/hash mismatch")
        return commitment

    def _round_binding(
        self,
        *,
        round_id: str,
        assignment_id: str,
    ) -> dict[str, Any]:
        project_id = self._project_id()
        round_path = (
            self.project_root / "rounds" / round_id / "round.json"
        )
        manifest = self._read_json(round_path)
        if (
            manifest.get("schema_version") != 4
            or manifest.get("policy_revision") != POLICY_REVISION_V4
            or manifest.get("project_id") != project_id
            or manifest.get("round_id") != round_id
        ):
            raise ValueError("pulse round manifest binding mismatch")
        matches = [
            item
            for item in manifest.get("assignments", [])
            if isinstance(item, dict)
            and item.get("assignment_id") == assignment_id
        ]
        if len(matches) != 1:
            raise ValueError("pulse assignment is not uniquely bound")
        assignment = matches[0]
        task_path = contained_path(
            self.project_root,
            require_string(assignment, "task_card_relpath"),
            "pulse task card path",
        )
        card = self._read_json(task_path)
        validate_task_card(card, allow_legacy_adoption=True)
        if (
            card["project_id"] != project_id
            or card["round_id"] != round_id
            or card["assignment_id"] != assignment_id
            or card["blackboard_view"]["snapshot_id"]
            != manifest.get("blackboard_snapshot_id")
            or sha256_bytes(task_path.read_bytes())
            != assignment.get("task_card_sha256")
        ):
            raise ValueError("pulse task-card/round binding mismatch")
        snapshot_id = validate_bb_snapshot_id(
            require_string(manifest, "blackboard_snapshot_id")
        )
        snapshot_path = (
            self.blackboard.snapshots_dir / snapshot_id / "manifest.json"
        )
        if (
            sha256_bytes(snapshot_path.read_bytes())
            != manifest.get("blackboard_snapshot_sha256")
        ):
            raise ValueError("pulse round snapshot hash mismatch")
        return {
            "manifest": manifest,
            "assignment": assignment,
            "card": card,
            "round_sha256": sha256_bytes(round_path.read_bytes()),
            "snapshot_id": snapshot_id,
            "snapshot_sha256": manifest["blackboard_snapshot_sha256"],
        }

    def _assignment_execution_signals(
        self,
        *,
        round_id: str,
        assignment_id: str,
    ) -> list[str]:
        """Return durable evidence that a bound assignment has started.

        Canonical return files are only one signal.  A completed or interrupted
        V4 ingestion also leaves a content-addressed blackboard transaction,
        which remains authoritative if the return or ingestion marker is later
        removed.  A broken transaction ledger makes pristine state
        unprovable, so callers fail closed instead of permitting a
        retrospective pulse plan or host dispatch.
        """

        binding = self._round_binding(
            round_id=round_id,
            assignment_id=assignment_id,
        )
        return_path = contained_path(
            self.project_root,
            binding["assignment"]["return_relpath"],
            "pulse return path",
        )
        receipt_path = return_path.with_suffix(".receipt.json")
        signals: list[str] = []
        if return_path.exists() or return_path.is_symlink():
            signals.append("canonical_return")
        if receipt_path.exists() or receipt_path.is_symlink():
            signals.append("ingestion_receipt")

        try:
            transactions = self.blackboard._receipts()
            events = self.blackboard._read_jsonl(
                self.blackboard.events_path
            )
        except Exception as exc:
            raise ValueError(
                "cannot establish pristine assignment state: "
                f"blackboard transaction ledger is invalid: {exc}"
            ) from exc
        transactions_by_id = {
            item["transaction_id"]: item for item in transactions
        }
        event_transaction_ids: set[str] = set()
        for event in events:
            if event.get("event") != "transaction_visible":
                continue
            transaction_id = event.get("transaction_id")
            if (
                not isinstance(transaction_id, str)
                or SHA256_RE.fullmatch(transaction_id) is None
            ):
                raise ValueError(
                    "cannot establish pristine assignment state: "
                    "blackboard transaction event is invalid"
                )
            event_transaction_ids.add(transaction_id)
        missing_transactions = (
            event_transaction_ids - set(transactions_by_id)
        )
        if missing_transactions:
            raise ValueError(
                "cannot establish pristine assignment state: "
                "blackboard transaction event references a missing receipt"
            )

        for transaction in transactions:
            if (
                transaction.get("kind") == "worker_delta_merge"
                and transaction.get("assignment_id") == assignment_id
                and transaction.get("base_snapshot_id")
                == binding["snapshot_id"]
            ):
                signals.append(
                    "blackboard_transaction:"
                    + transaction["transaction_id"]
                )
        return signals

    def _require_assignment_pristine(
        self,
        *,
        round_id: str,
        assignment_id: str,
        phase: str,
    ) -> None:
        signals = self._assignment_execution_signals(
            round_id=round_id,
            assignment_id=assignment_id,
        )
        if signals:
            raise ValueError(
                f"{phase} assignment is not pristine; pulse evidence "
                "cannot be recorded retrospectively: "
                f"{round_id}/{assignment_id} "
                f"({', '.join(signals)})"
            )

    def _validate_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        require_exact_keys(
            plan,
            required=_PLAN_FIELDS,
            label="collaboration pulse plan",
        )
        project_id = self._project_id()
        if (
            plan.get("schema_version") != 1
            or plan.get("policy_revision") != POLICY_REVISION_V4
            or plan.get("project_id") != project_id
        ):
            raise ValueError("collaboration pulse plan header mismatch")
        pulse_id = require_string(plan, "pulse_id")
        if (
            PULSE_ID_RE.fullmatch(pulse_id) is None
            or pulse_id != _content_id("bbp-", plan, "pulse_id")
        ):
            raise ValueError("collaboration pulse id/hash mismatch")
        require_string(plan, "actor")
        require_string(plan, "host_task_scope_id")
        require_string(plan, "campaign_id")
        validate_bb_snapshot_id(
            require_string(plan, "wave1_snapshot_id")
        )
        snapshot_sha = require_string(plan, "wave1_snapshot_sha256")
        if SHA256_RE.fullmatch(snapshot_sha) is None:
            raise ValueError("pulse wave-1 snapshot hash is invalid")
        minimum = _positive_integer(
            plan.get("minimum_wave1_contributors"),
            "minimum_wave1_contributors",
        )
        commitments = plan.get("wave1_commitments")
        if (
            not isinstance(commitments, list)
            or not commitments
            or any(not isinstance(item, dict) for item in commitments)
        ):
            raise ValueError("pulse wave1_commitments must be nonempty")
        for item in commitments:
            self._validate_wave1_commitment(
                item,
                project_id=project_id,
            )
        ids = [item["commitment_id"] for item in commitments]
        assignments = [
            (item["round_id"], item["assignment_id"])
            for item in commitments
        ]
        if len(ids) != len(set(ids)) or len(assignments) != len(
            set(assignments)
        ):
            raise ValueError("pulse wave-1 commitments are duplicated")
        if minimum > len(commitments):
            raise ValueError(
                "minimum_wave1_contributors exceeds commitments"
            )
        federation = plan.get("federation")
        if federation != {"mode": "disabled"}:
            raise ValueError(
                "first-slice collaboration federation must be disabled"
            )
        trusted_issuers = _string_list(
            plan.get("trusted_host_issuers"),
            "pulse trusted_host_issuers",
        ) if plan.get("trusted_host_issuers") else []
        if len(trusted_issuers) != len(set(trusted_issuers)):
            raise ValueError("pulse trusted_host_issuers are duplicated")
        return plan

    def create_plan(
        self,
        *,
        wave1_commitments: list[dict[str, Any]],
        minimum_wave1_contributors: int = 2,
        actor: str = "main",
        federation_mode: str = "disabled",
    ) -> dict[str, Any]:
        project_id = self._project_id()
        if federation_mode != "disabled":
            raise ValueError(
                "federation is disabled in the local cooperative pulse slice"
            )
        if (
            not isinstance(wave1_commitments, list)
            or not wave1_commitments
            or any(not isinstance(item, dict) for item in wave1_commitments)
        ):
            raise ValueError("wave1_commitments must be a nonempty list")
        normalized = [
            dict(
                self._validate_wave1_commitment(
                    dict(item),
                    project_id=project_id,
                )
            )
            for item in wave1_commitments
        ]
        self._require_commitments_active(normalized)
        bindings = [
            self._round_binding(
                round_id=item["round_id"],
                assignment_id=item["assignment_id"],
            )
            for item in normalized
        ]
        snapshot_ids = {item["snapshot_id"] for item in bindings}
        snapshot_hashes = {item["snapshot_sha256"] for item in bindings}
        campaigns = {item["card"]["campaign_id"] for item in bindings}
        host_scopes = {
            item["card"].get("host_task_scope_id") for item in bindings
        }
        if len(snapshot_ids) != 1 or len(snapshot_hashes) != 1:
            raise ValueError(
                "wave-1 assignments must share one frozen snapshot"
            )
        if len(campaigns) != 1 or len(host_scopes) != 1 or None in host_scopes:
            raise ValueError(
                "wave-1 assignments must share campaign and host-task scope"
            )
        body = {
            "schema_version": 1,
            "policy_revision": POLICY_REVISION_V4,
            "project_id": project_id,
            "actor": actor,
            "host_task_scope_id": next(iter(host_scopes)),
            "campaign_id": next(iter(campaigns)),
            "wave1_snapshot_id": next(iter(snapshot_ids)),
            "wave1_snapshot_sha256": next(iter(snapshot_hashes)),
            "minimum_wave1_contributors": minimum_wave1_contributors,
            "wave1_commitments": sorted(
                normalized,
                key=lambda item: item["commitment_id"],
            ),
            "federation": {"mode": "disabled"},
            "trusted_host_issuers": list(
                self.trusted_host_issuers
            ),
        }
        plan = {
            **body,
            "pulse_id": _content_id("bbp-", body, "pulse_id"),
        }
        self._validate_plan(plan)
        with self._mutation_lock():
            self._require_commitments_active(
                plan["wave1_commitments"]
            )
            for commitment in plan["wave1_commitments"]:
                self._require_assignment_pristine(
                    round_id=commitment["round_id"],
                    assignment_id=commitment["assignment_id"],
                    phase="Wave-1 pulse-plan",
                )
            self._write_control_record(
                self._plan_path(plan["pulse_id"]),
                plan,
            )
        return {
            **plan,
            "plan_sha256": sha256_bytes(
                self._plan_path(plan["pulse_id"]).read_bytes()
            ),
        }

    def plan(self, pulse_id: str) -> dict[str, Any]:
        plan = self._validate_plan(
            self._read_json(self._plan_path(pulse_id))
        )
        if plan["pulse_id"] != pulse_id:
            raise ValueError("pulse directory/plan id mismatch")
        return plan

    def _validate_abort(
        self,
        payload: dict[str, Any],
        *,
        plan: dict[str, Any],
    ) -> dict[str, Any]:
        require_exact_keys(
            payload,
            required=_ABORT_FIELDS,
            optional=_ABORT_CORE_FAILURE_FIELDS,
            label="pulse abort receipt",
        )
        if (
            payload.get("schema_version") != 1
            or payload.get("policy_revision") != POLICY_REVISION_V4
            or payload.get("project_id") != plan["project_id"]
            or payload.get("pulse_id") != plan["pulse_id"]
        ):
            raise ValueError("pulse abort header/binding mismatch")
        expected_plan_sha256 = sha256_bytes(
            self._plan_path(plan["pulse_id"]).read_bytes()
        )
        plan_sha256 = require_string(payload, "plan_sha256")
        if (
            SHA256_RE.fullmatch(plan_sha256) is None
            or plan_sha256 != expected_plan_sha256
        ):
            raise ValueError("pulse abort plan hash mismatch")
        require_string(payload, "failure_phase")
        require_string(payload, "actor")
        require_string(payload, "reason")
        failure_keys = set(payload).intersection(
            _ABORT_CORE_FAILURE_FIELDS
        )
        if failure_keys and failure_keys != _ABORT_CORE_FAILURE_FIELDS:
            raise ValueError(
                "pulse abort core-failure binding is incomplete"
            )
        if failure_keys:
            if CORE_FAILURE_ID_RE.fullmatch(
                require_string(payload, "core_failure_id")
            ) is None:
                raise ValueError(
                    "pulse abort core-failure id is invalid"
                )
            if SHA256_RE.fullmatch(
                require_string(payload, "core_failure_sha256")
            ) is None:
                raise ValueError(
                    "pulse abort core-failure hash is invalid"
                )
        abort_id = require_string(payload, "abort_id")
        if (
            ABORT_ID_RE.fullmatch(abort_id) is None
            or abort_id != _content_id(
                "bbabort-",
                payload,
                "abort_id",
            )
        ):
            raise ValueError("pulse abort id/hash mismatch")
        return payload

    def _validate_core_failure(
        self,
        payload: dict[str, Any],
        *,
        plan: dict[str, Any],
        commitment: dict[str, Any],
    ) -> dict[str, Any]:
        require_exact_keys(
            payload,
            required=_CORE_FAILURE_FIELDS,
            label="pulse core-ingest failure evidence",
        )
        if (
            payload.get("schema_version") != 1
            or payload.get("policy_revision") != POLICY_REVISION_V4
            or payload.get("project_id") != plan["project_id"]
            or payload.get("pulse_id") != plan["pulse_id"]
            or payload.get("commitment_id")
            != commitment["commitment_id"]
            or payload.get("phase") != commitment["phase"]
            or payload.get("round_id") != commitment["round_id"]
            or payload.get("assignment_id")
            != commitment["assignment_id"]
        ):
            raise ValueError(
                "pulse core-ingest failure binding mismatch"
            )
        if commitment["criticality"] != "core":
            raise ValueError(
                "pulse core-ingest failure names an optional commitment"
            )
        expected_plan_sha256 = sha256_bytes(
            self._plan_path(plan["pulse_id"]).read_bytes()
        )
        if payload.get("plan_sha256") != expected_plan_sha256:
            raise ValueError(
                "pulse core-ingest failure plan hash mismatch"
            )
        binding = self._round_binding(
            round_id=commitment["round_id"],
            assignment_id=commitment["assignment_id"],
        )
        if payload.get("return_relpath") != binding[
            "assignment"
        ]["return_relpath"]:
            raise ValueError(
                "pulse core-ingest failure return path mismatch"
            )
        for key in ("return_sha256", "worker_final_sha256"):
            if SHA256_RE.fullmatch(
                require_string(payload, key)
            ) is None:
                raise ValueError(
                    f"pulse core-ingest failure {key} is invalid"
                )
        require_string(payload, "error_class")
        require_string(payload, "error_message")
        require_string(payload, "actor")
        failure_id = require_string(payload, "failure_id")
        if (
            CORE_FAILURE_ID_RE.fullmatch(failure_id) is None
            or failure_id
            != _content_id("bbfail-", payload, "failure_id")
        ):
            raise ValueError(
                "pulse core-ingest failure id/hash mismatch"
            )
        return payload

    def _core_failure(
        self,
        plan: dict[str, Any],
        commitment: dict[str, Any],
    ) -> dict[str, Any] | None:
        path = self._core_failure_path(
            plan["pulse_id"],
            commitment["commitment_id"],
        )
        if not path.exists():
            return None
        return self._validate_core_failure(
            self._read_json(path),
            plan=plan,
            commitment=commitment,
        )

    def _abort_receipt(
        self,
        plan: dict[str, Any],
    ) -> dict[str, Any] | None:
        path = self._abort_path(plan["pulse_id"])
        if not path.exists():
            return None
        return self._validate_abort(
            self._read_json(path),
            plan=plan,
        )

    def _require_not_aborted(
        self,
        plan: dict[str, Any],
        *,
        action: str,
    ) -> None:
        receipt = self._abort_receipt(plan)
        if receipt is not None:
            raise ValueError(
                f"aborted pulse cannot {action}: "
                f"{receipt['abort_id']}"
            )

    def abort(
        self,
        pulse_id: str,
        *,
        failure_phase: str,
        reason: str,
        actor: str = "main",
    ) -> dict[str, Any]:
        """Persist the distinct terminal state for a failed pulse.

        An abort closes the whole pulse rather than weakening or voiding any
        commitment.  In particular, core commitments remain core and are
        never converted into optional work.
        """

        plan = self.plan(pulse_id)
        body = {
            "schema_version": 1,
            "policy_revision": POLICY_REVISION_V4,
            "project_id": plan["project_id"],
            "pulse_id": pulse_id,
            "plan_sha256": sha256_bytes(
                self._plan_path(pulse_id).read_bytes()
            ),
            "failure_phase": failure_phase,
            "actor": actor,
            "reason": reason,
        }
        receipt = {
            **body,
            "abort_id": _content_id(
                "bbabort-",
                body,
                "abort_id",
            ),
        }
        self._validate_abort(receipt, plan=plan)
        with self._mutation_lock():
            if self._closure_path(pulse_id).exists():
                raise ValueError("closed pulse cannot be aborted")
            self._write_control_record(
                self._abort_path(pulse_id),
                receipt,
            )
        return {
            **receipt,
            "abort_sha256": sha256_bytes(
                self._abort_path(pulse_id).read_bytes()
            ),
        }

    def abort_receipt(self, pulse_id: str) -> dict[str, Any]:
        plan = self.plan(pulse_id)
        receipt = self._abort_receipt(plan)
        if receipt is None:
            raise ValueError("pulse abort receipt is missing")
        return receipt

    def _assignment_memberships(
        self,
        *,
        round_id: str,
        assignment_id: str,
    ) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        validate_round_id(round_id)
        validate_assignment_id(assignment_id)
        memberships: list[
            tuple[dict[str, Any], dict[str, Any]]
        ] = []
        for plan_path in sorted(self.root.glob("bbp-*/plan.json")):
            plan = self.plan(plan_path.parent.name)
            candidates = list(plan["wave1_commitments"])
            barrier_path = self._barrier_path(plan["pulse_id"])
            if barrier_path.exists():
                barrier = self._validate_barrier(
                    self._read_json(barrier_path),
                    plan=plan,
                )
                candidates.extend(barrier["review_commitments"])
            matches = [
                item
                for item in candidates
                if item["round_id"] == round_id
                and item["assignment_id"] == assignment_id
            ]
            if len(matches) > 1:
                raise ValueError(
                    "assignment has duplicate commitments in one pulse"
                )
            if matches:
                memberships.append((plan, matches[0]))
        return memberships

    def require_ingest_allowed(
        self,
        *,
        round_id: str,
        assignment_id: str,
    ) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        """Fail before ingestion when a bound pulse is terminal."""

        memberships = self._assignment_memberships(
            round_id=round_id,
            assignment_id=assignment_id,
        )
        for plan, commitment in memberships:
            abort = self._abort_receipt(plan)
            if abort is not None:
                raise ValueError(
                    "aborted pulse cannot ingest a return: "
                    f"{abort['abort_id']}"
                )
            failure = self._core_failure(plan, commitment)
            if failure is not None:
                raise ValueError(
                    "pulse has core-ingest failure evidence without an "
                    "abort receipt; audit and fail closed: "
                    f"{failure['failure_id']}"
                )
            void = self._void_receipt(plan, commitment)
            if void is not None:
                raise ValueError(
                    "voided optional commitment cannot ingest a return: "
                    f"{void['void_id']}"
                )
        return memberships

    def record_core_ingest_failure(
        self,
        *,
        round_id: str,
        assignment_id: str,
        return_sha256: str,
        worker_final_sha256: str,
        error_class: str,
        error_message: str,
        actor: str = "main",
    ) -> list[dict[str, Any]]:
        """Atomically preflight durable failure evidence and pulse aborts."""

        require_unaborted_work_unit(self.project_root, round_id)
        if SHA256_RE.fullmatch(return_sha256) is None:
            raise ValueError(
                "core-ingest failure return SHA-256 is invalid"
            )
        if SHA256_RE.fullmatch(worker_final_sha256) is None:
            raise ValueError(
                "core-ingest failure worker-final SHA-256 is invalid"
            )
        if not isinstance(error_class, str) or not error_class.strip():
            raise ValueError(
                "core-ingest failure error class must be nonempty"
            )
        if not isinstance(error_message, str) or not error_message.strip():
            raise ValueError(
                "core-ingest failure error message must be nonempty"
            )
        memberships = [
            (plan, commitment)
            for plan, commitment in self._assignment_memberships(
                round_id=round_id,
                assignment_id=assignment_id,
            )
            if commitment["criticality"] == "core"
        ]
        if not memberships:
            return []
        records: list[tuple[Path, dict[str, Any]]] = []
        results: list[dict[str, Any]] = []
        for plan, commitment in memberships:
            if self._closure_path(plan["pulse_id"]).exists():
                raise ValueError(
                    "closed pulse cannot record a core-ingest failure"
                )
            existing_abort = self._abort_receipt(plan)
            if existing_abort is not None:
                raise ValueError(
                    "aborted pulse cannot record another core-ingest "
                    f"failure: {existing_abort['abort_id']}"
                )
            binding = self._round_binding(
                round_id=round_id,
                assignment_id=assignment_id,
            )
            failure_body = {
                "schema_version": 1,
                "policy_revision": POLICY_REVISION_V4,
                "project_id": plan["project_id"],
                "pulse_id": plan["pulse_id"],
                "plan_sha256": sha256_bytes(
                    self._plan_path(plan["pulse_id"]).read_bytes()
                ),
                "commitment_id": commitment["commitment_id"],
                "phase": commitment["phase"],
                "round_id": round_id,
                "assignment_id": assignment_id,
                "return_relpath": binding["assignment"][
                    "return_relpath"
                ],
                "return_sha256": return_sha256,
                "worker_final_sha256": worker_final_sha256,
                "error_class": error_class,
                "error_message": error_message,
                "actor": actor,
            }
            failure = {
                **failure_body,
                "failure_id": _content_id(
                    "bbfail-",
                    failure_body,
                    "failure_id",
                ),
            }
            self._validate_core_failure(
                failure,
                plan=plan,
                commitment=commitment,
            )
            failure_path = self._core_failure_path(
                plan["pulse_id"],
                commitment["commitment_id"],
            )
            failure_sha256 = sha256_bytes(
                self._encoded_json(failure)
            )
            abort_body = {
                "schema_version": 1,
                "policy_revision": POLICY_REVISION_V4,
                "project_id": plan["project_id"],
                "pulse_id": plan["pulse_id"],
                "plan_sha256": failure["plan_sha256"],
                "failure_phase": (
                    f"{commitment['phase']}_core_ingest"
                ),
                "actor": actor,
                "reason": (
                    "Core commitment ingest failed; immutable failure "
                    f"evidence {failure['failure_id']} records: "
                    f"{error_message}"
                ),
                "core_failure_id": failure["failure_id"],
                "core_failure_sha256": failure_sha256,
            }
            abort = {
                **abort_body,
                "abort_id": _content_id(
                    "bbabort-",
                    abort_body,
                    "abort_id",
                ),
            }
            self._validate_abort(abort, plan=plan)
            records.extend(
                [
                    (failure_path, failure),
                    (self._abort_path(plan["pulse_id"]), abort),
                ]
            )
            results.append(
                {
                    "pulse_id": plan["pulse_id"],
                    "commitment_id": commitment["commitment_id"],
                    "failure": failure,
                    "abort": abort,
                }
            )
        with self._mutation_lock():
            require_unaborted_work_unit(self.project_root, round_id)
            self._write_control_records(records)
        return results

    def core_failure_receipts(
        self,
        pulse_id: str,
    ) -> list[dict[str, Any]]:
        plan = self.plan(pulse_id)
        candidates = list(plan["wave1_commitments"])
        barrier_path = self._barrier_path(pulse_id)
        if barrier_path.exists():
            barrier = self._validate_barrier(
                self._read_json(barrier_path),
                plan=plan,
            )
            candidates.extend(barrier["review_commitments"])
        by_id = {
            item["commitment_id"]: item for item in candidates
        }
        failures: list[dict[str, Any]] = []
        for path in sorted(
            self._pulse_dir(pulse_id).glob(
                "core-failures/*.json"
            )
        ):
            commitment = by_id.get(path.stem)
            if commitment is None:
                raise ValueError(
                    "core-ingest failure names an unknown commitment"
                )
            failures.append(
                self._validate_core_failure(
                    self._read_json(path),
                    plan=plan,
                    commitment=commitment,
                )
            )
        return failures

    def _find_commitment(
        self,
        plan: dict[str, Any],
        commitment_id: str,
    ) -> dict[str, Any]:
        candidates = list(plan["wave1_commitments"])
        barrier_path = self._barrier_path(plan["pulse_id"])
        if barrier_path.exists():
            barrier = self._validate_barrier(
                self._read_json(barrier_path),
                plan=plan,
            )
            candidates.extend(barrier["review_commitments"])
        matches = [
            item
            for item in candidates
            if item["commitment_id"] == commitment_id
        ]
        if len(matches) != 1:
            raise KeyError("unknown or duplicate pulse commitment")
        return matches[0]

    def _validate_void(
        self,
        payload: dict[str, Any],
        *,
        plan: dict[str, Any],
        commitment: dict[str, Any],
    ) -> dict[str, Any]:
        require_exact_keys(
            payload,
            required=_VOID_FIELDS,
            label="pulse optional-void receipt",
        )
        if (
            payload.get("schema_version") != 1
            or payload.get("policy_revision") != POLICY_REVISION_V4
            or payload.get("project_id") != plan["project_id"]
            or payload.get("pulse_id") != plan["pulse_id"]
            or payload.get("commitment_id")
            != commitment["commitment_id"]
            or payload.get("phase") != commitment["phase"]
        ):
            raise ValueError("pulse optional-void binding mismatch")
        if commitment["criticality"] != "optional":
            raise ValueError("core commitments can never be voided")
        require_string(payload, "actor")
        require_string(payload, "reason")
        void_id = require_string(payload, "void_id")
        if (
            VOID_ID_RE.fullmatch(void_id) is None
            or void_id != _content_id("bbvoid-", payload, "void_id")
        ):
            raise ValueError("pulse optional-void id/hash mismatch")
        return payload

    def _void_receipt(
        self,
        plan: dict[str, Any],
        commitment: dict[str, Any],
    ) -> dict[str, Any] | None:
        path = self._void_path(
            plan["pulse_id"],
            commitment["commitment_id"],
        )
        if not path.exists():
            return None
        return self._validate_void(
            self._read_json(path),
            plan=plan,
            commitment=commitment,
        )

    def void_optional(
        self,
        pulse_id: str,
        commitment_id: str,
        *,
        reason: str,
        actor: str = "operator",
    ) -> dict[str, Any]:
        plan = self.plan(pulse_id)
        self._require_not_aborted(
            plan,
            action="void an optional commitment",
        )
        commitment = self._find_commitment(plan, commitment_id)
        require_unaborted_work_unit(
            self.project_root,
            commitment["round_id"],
        )
        if commitment["criticality"] != "optional":
            raise ValueError("core commitments can never be voided")
        if self._ingestion_evidence(
            round_id=commitment["round_id"],
            assignment_id=commitment["assignment_id"],
            required=False,
        ) is not None:
            raise ValueError(
                "an ingested commitment cannot be retroactively voided"
            )
        body = {
            "schema_version": 1,
            "policy_revision": POLICY_REVISION_V4,
            "project_id": plan["project_id"],
            "pulse_id": pulse_id,
            "commitment_id": commitment_id,
            "phase": commitment["phase"],
            "actor": actor,
            "reason": reason,
        }
        receipt = {
            **body,
            "void_id": _content_id("bbvoid-", body, "void_id"),
        }
        self._validate_void(
            receipt,
            plan=plan,
            commitment=commitment,
        )
        with self._mutation_lock():
            self._require_not_aborted(
                plan,
                action="void an optional commitment",
            )
            require_unaborted_work_unit(
                self.project_root,
                commitment["round_id"],
            )
            self._write_control_record(
                self._void_path(pulse_id, commitment_id),
                receipt,
            )
        return receipt

    def _validate_host_dispatch(
        self,
        payload: dict[str, Any],
        *,
        plan: dict[str, Any],
        barrier: dict[str, Any],
        commitment: dict[str, Any],
    ) -> dict[str, Any]:
        require_exact_keys(
            payload,
            required=_HOST_DISPATCH_FIELDS,
            label="pulse host-dispatch receipt",
        )
        if (
            payload.get("schema_version") != 1
            or payload.get("policy_revision") != POLICY_REVISION_V4
            or payload.get("project_id") != plan["project_id"]
            or payload.get("pulse_id") != plan["pulse_id"]
            or payload.get("barrier_id") != barrier["barrier_id"]
            or payload.get("commitment_id")
            != commitment["commitment_id"]
            or payload.get("round_id") != commitment["round_id"]
            or payload.get("assignment_id")
            != commitment["assignment_id"]
        ):
            raise ValueError("pulse host-dispatch binding mismatch")
        require_string(payload, "issuer")
        if payload["issuer"] not in plan["trusted_host_issuers"]:
            raise ValueError(
                "pulse host-dispatch issuer is not trusted by the "
                "immutable pulse plan"
            )
        if payload.get("host_task_scope_id") != plan["host_task_scope_id"]:
            raise ValueError(
                "pulse host-dispatch host-task scope mismatch"
            )
        require_string(payload, "host_context_id")
        require_string(payload, "agent_identity")
        if (
            payload.get("fresh_context_contract")
            != FRESH_CONTEXT_CONTRACT_V1
        ):
            raise ValueError(
                "pulse host-dispatch fresh-context contract mismatch"
            )
        if payload.get("clean_context") is not True:
            raise ValueError(
                "pulse host-dispatch must attest a clean context"
            )
        binding = self._round_binding(
            round_id=commitment["round_id"],
            assignment_id=commitment["assignment_id"],
        )
        if (
            payload.get("prompt_sha256")
            != binding["assignment"].get("prompt_sha256")
        ):
            raise ValueError(
                "pulse host-dispatch prompt hash mismatch"
            )
        dispatch_id = require_string(payload, "dispatch_id")
        if (
            HOST_DISPATCH_ID_RE.fullmatch(dispatch_id) is None
            or dispatch_id
            != _content_id("bbhost-", payload, "dispatch_id")
        ):
            raise ValueError("pulse host-dispatch id/hash mismatch")
        return payload

    def record_host_dispatch(
        self,
        pulse_id: str,
        commitment_id: str,
        *,
        issuer: str,
        host_context_id: str,
        agent_identity: str | None = None,
        fresh_context_contract: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        plan = self.plan(pulse_id)
        self._require_not_aborted(
            plan,
            action="record a host dispatch",
        )
        self._require_plan_work_units_active(plan)
        if issuer not in self.trusted_host_issuers:
            raise ValueError(
                "host-dispatch issuer is not trusted by the active "
                "host-adapter configuration"
            )
        if issuer not in plan["trusted_host_issuers"]:
            raise ValueError(
                "host-dispatch issuer is not trusted by the immutable "
                "pulse plan"
            )
        barrier = self.barrier(pulse_id)
        matches = [
            item
            for item in barrier["review_commitments"]
            if item["commitment_id"] == commitment_id
        ]
        if len(matches) != 1:
            raise KeyError(
                "host dispatch requires one bound review commitment"
            )
        commitment = matches[0]
        require_unaborted_work_unit(
            self.project_root,
            commitment["round_id"],
        )
        dispatch_path = self._dispatch_path(pulse_id, commitment_id)
        normalized_agent_identity = (
            host_context_id
            if agent_identity is None
            else agent_identity
        )
        normalized_contract = (
            dict(FRESH_CONTEXT_CONTRACT_V1)
            if fresh_context_contract is None
            else fresh_context_contract
        )
        require_string(
            {"agent_identity": normalized_agent_identity},
            "agent_identity",
        )
        if normalized_contract != FRESH_CONTEXT_CONTRACT_V1:
            raise ValueError(
                "host dispatch requires the exact fresh-context-v1 "
                "contract"
            )
        binding = self._round_binding(
            round_id=commitment["round_id"],
            assignment_id=commitment["assignment_id"],
        )
        body = {
            "schema_version": 1,
            "policy_revision": POLICY_REVISION_V4,
            "project_id": plan["project_id"],
            "pulse_id": pulse_id,
            "barrier_id": barrier["barrier_id"],
            "commitment_id": commitment_id,
            "round_id": commitment["round_id"],
            "assignment_id": commitment["assignment_id"],
            "prompt_sha256": binding["assignment"]["prompt_sha256"],
            "issuer": issuer,
            "host_task_scope_id": plan["host_task_scope_id"],
            "host_context_id": host_context_id,
            "agent_identity": normalized_agent_identity,
            "fresh_context_contract": normalized_contract,
            "clean_context": True,
        }
        receipt = {
            **body,
            "dispatch_id": _content_id(
                "bbhost-",
                body,
                "dispatch_id",
            ),
        }
        self._validate_host_dispatch(
            receipt,
            plan=plan,
            barrier=barrier,
            commitment=commitment,
        )
        with self._mutation_lock():
            self._require_not_aborted(
                plan,
                action="record a host dispatch",
            )
            require_unaborted_work_unit(
                self.project_root,
                commitment["round_id"],
            )
            self._require_assignment_pristine(
                round_id=commitment["round_id"],
                assignment_id=commitment["assignment_id"],
                phase="Wave-2 host-dispatch",
            )
            if dispatch_path.exists() or dispatch_path.is_symlink():
                raise ValueError(
                    "host dispatch receipt already exists; replay is not "
                    "accepted"
                )
            for existing_path in sorted(
                self.root.glob(
                    "bbp-*/host-dispatches/bbpc-*.json"
                )
            ):
                existing = self._read_json(existing_path)
                if (
                    existing.get("host_task_scope_id")
                    == plan["host_task_scope_id"]
                    and existing.get("host_context_id")
                    == host_context_id
                ):
                    raise ValueError(
                        "host context id replay is not accepted inside "
                        "one host-task scope"
                    )
            self._write_control_record(
                dispatch_path,
                receipt,
            )
        return receipt

    def _host_dispatch(
        self,
        plan: dict[str, Any],
        barrier: dict[str, Any],
        commitment: dict[str, Any],
    ) -> dict[str, Any] | None:
        path = self._dispatch_path(
            plan["pulse_id"],
            commitment["commitment_id"],
        )
        if not path.exists():
            return None
        return self._validate_host_dispatch(
            self._read_json(path),
            plan=plan,
            barrier=barrier,
            commitment=commitment,
        )

    def _pending_canonical_return(
        self,
        *,
        round_id: str,
        assignment_id: str,
    ) -> dict[str, Any] | None:
        binding = self._round_binding(
            round_id=round_id,
            assignment_id=assignment_id,
        )
        return_path = contained_path(
            self.project_root,
            binding["assignment"]["return_relpath"],
            "pulse return path",
        )
        receipt_path = return_path.with_suffix(".receipt.json")
        if receipt_path.exists() or receipt_path.is_symlink():
            return None
        if not return_path.exists() and not return_path.is_symlink():
            return None
        if not return_path.is_file() or return_path.is_symlink():
            raise ValueError(
                "canonical return without an ingestion receipt is unsafe: "
                f"{round_id}/{assignment_id}"
            )
        return {
            "round_id": round_id,
            "assignment_id": assignment_id,
            "return_relpath": binding["assignment"]["return_relpath"],
            "return_sha256": sha256_bytes(return_path.read_bytes()),
        }

    @staticmethod
    def _pending_return_blocker(
        commitment: dict[str, Any],
        pending: dict[str, Any],
    ) -> str:
        resolution = (
            "run ingest-return or pulse-abort"
            if commitment["criticality"] == "core"
            else "run ingest-return or pulse-void"
        )
        return (
            "canonical return exists without an ingestion receipt for "
            f"{pending['round_id']}/{pending['assignment_id']} "
            f"(sha256={pending['return_sha256']}); {resolution}. "
            "Deleting or replacing the canonical return does not repair "
            "a recorded failure or terminal pulse"
        )

    def _ingestion_evidence(
        self,
        *,
        round_id: str,
        assignment_id: str,
        required: bool,
    ) -> dict[str, Any] | None:
        binding = self._round_binding(
            round_id=round_id,
            assignment_id=assignment_id,
        )
        return_path = contained_path(
            self.project_root,
            binding["assignment"]["return_relpath"],
            "pulse return path",
        )
        receipt_path = return_path.with_suffix(".receipt.json")
        if not receipt_path.exists():
            if required:
                raise ValueError(
                    f"commitment has no ingestion receipt: "
                    f"{round_id}/{assignment_id}"
                )
            return None
        receipt = validate_ingestion_receipt_v4(
            self._read_json(receipt_path)
        )
        if (
            receipt["project_id"] != self._project_id()
            or receipt["round_id"] != round_id
            or receipt["assignment_id"] != assignment_id
            or receipt["assignment_sha256"]
            != binding["assignment"]["assignment_sha256"]
            or receipt["return_relpath"]
            != binding["assignment"]["return_relpath"]
            or not return_path.is_file()
            or return_path.is_symlink()
            or receipt["return_sha256"]
            != sha256_bytes(return_path.read_bytes())
            or receipt["worker_final_sha256"]
            != receipt["return_sha256"]
        ):
            raise ValueError("pulse ingestion receipt binding mismatch")
        transactions = {
            item["transaction_id"]: item
            for item in self.blackboard._receipts()
        }
        transaction = transactions.get(
            receipt["blackboard_transaction_id"]
        )
        if transaction is None or (
            transaction.get("assignment_id") != assignment_id
            or transaction.get("return_sha256")
            != receipt["return_sha256"]
            or transaction.get("base_snapshot_id")
            != binding["snapshot_id"]
            or transaction.get("node_ids")
            != receipt["blackboard_node_ids"]
            or transaction.get("edge_ids")
            != receipt["blackboard_edge_ids"]
        ):
            raise ValueError(
                "pulse ingestion/blackboard transaction mismatch"
            )
        visible_nodes, visible_edges = self.blackboard.visible_ids()
        if not set(receipt["blackboard_node_ids"]).issubset(
            visible_nodes
        ) or not set(receipt["blackboard_edge_ids"]).issubset(
            visible_edges
        ):
            raise ValueError(
                "pulse commitment transaction is not visibly ingested"
            )
        return {
            "round_id": round_id,
            "assignment_id": assignment_id,
            "round_sha256": binding["round_sha256"],
            "ingestion_sha256": receipt["ingestion_sha256"],
            "blackboard_transaction_id": receipt[
                "blackboard_transaction_id"
            ],
            "node_ids": list(receipt["blackboard_node_ids"]),
            "edge_ids": list(receipt["blackboard_edge_ids"]),
            "artifacts": list(receipt["artifacts"]),
            "outcome": receipt["outcome"],
        }

    def _wave1_evidence(
        self,
        plan: dict[str, Any],
    ) -> tuple[
        list[dict[str, Any]],
        list[str],
        list[dict[str, Any]],
    ]:
        pending_returns: list[
            tuple[dict[str, Any], dict[str, Any]]
        ] = []
        for commitment in plan["wave1_commitments"]:
            if self._void_receipt(plan, commitment) is not None:
                continue
            pending = self._pending_canonical_return(
                round_id=commitment["round_id"],
                assignment_id=commitment["assignment_id"],
            )
            if pending is not None:
                pending_returns.append((commitment, pending))
        if pending_returns:
            commitment, pending = sorted(
                pending_returns,
                key=lambda pair: (
                    pair[0]["criticality"] != "core",
                    pair[0]["commitment_id"],
                ),
            )[0]
            raise ValueError(
                self._pending_return_blocker(
                    commitment,
                    pending,
                )
            )
        nodes = self.blackboard.nodes()
        evidence: list[dict[str, Any]] = []
        void_ids: list[str] = []
        peer_nodes: list[dict[str, Any]] = []
        contributors: set[tuple[str, str]] = set()
        for commitment in plan["wave1_commitments"]:
            void = self._void_receipt(plan, commitment)
            ingestion = self._ingestion_evidence(
                round_id=commitment["round_id"],
                assignment_id=commitment["assignment_id"],
                required=False,
            )
            if void is not None and ingestion is not None:
                raise ValueError(
                    "voided wave-1 commitment later gained an ingestion "
                    "receipt"
                )
            if void is not None:
                void_ids.append(void["void_id"])
                continue
            if ingestion is None:
                pending = self._pending_canonical_return(
                    round_id=commitment["round_id"],
                    assignment_id=commitment["assignment_id"],
                )
                if pending is not None:
                    raise ValueError(
                        self._pending_return_blocker(
                            commitment,
                            pending,
                        )
                    )
                raise ValueError(
                    f"unfulfilled {commitment['criticality']} wave-1 "
                    f"commitment: {commitment['commitment_id']}"
                )
            candidates = [
                nodes[node_id]
                for node_id in ingestion["node_ids"]
                if node_id in nodes
                and nodes[node_id]["created_by_assignment_id"]
                == commitment["assignment_id"]
                and nodes[node_id]["node_type"]
                not in NON_PEER_NODE_TYPES
            ]
            if len(candidates) < commitment["minimum_peer_nodes"]:
                raise ValueError(
                    "wave-1 commitment lacks enough typed peer nodes: "
                    + commitment["commitment_id"]
                )
            contributors.add(
                (commitment["round_id"], commitment["assignment_id"])
            )
            evidence.append(
                {
                    "commitment_id": commitment["commitment_id"],
                    **ingestion,
                    "peer_node_ids": sorted(
                        item["node_id"] for item in candidates
                    ),
                }
            )
            for node in candidates:
                peer_nodes.append(
                    {
                        "node_id": node["node_id"],
                        "node_sha256": sha256_bytes(
                            canonical_json_bytes(node)
                        ),
                        "created_by_assignment_id": node[
                            "created_by_assignment_id"
                        ],
                        "source_commitment_id": commitment[
                            "commitment_id"
                        ],
                    }
                )
        if len(contributors) < plan["minimum_wave1_contributors"]:
            raise ValueError(
                "pulse has too few distinct wave-1 contributors"
            )
        unique_peers = {
            item["node_id"]: item for item in peer_nodes
        }
        return (
            sorted(evidence, key=lambda item: item["commitment_id"]),
            sorted(void_ids),
            [unique_peers[key] for key in sorted(unique_peers)],
        )

    def _barrier_semantic(
        self,
        plan: dict[str, Any],
        *,
        after_snapshot_id: str,
        review_commitments: list[dict[str, Any]],
        actor: str,
        require_wave2_unstarted: bool,
    ) -> dict[str, Any]:
        wave1_evidence, wave1_void_ids, peer_nodes = (
            self._wave1_evidence(plan)
        )
        after_snapshot_id = validate_bb_snapshot_id(after_snapshot_id)
        if after_snapshot_id == plan["wave1_snapshot_id"]:
            raise ValueError(
                "barrier requires a fresh post-wave-1 snapshot"
            )
        snapshot = self.blackboard.snapshot_manifest(
            after_snapshot_id
        )
        snapshot_path = (
            self.blackboard.snapshots_dir
            / after_snapshot_id
            / "manifest.json"
        )
        snapshot_node_ids = {
            item["node_id"] for item in snapshot["node_entries"]
        }
        normalized_reviews = [
            dict(
                self._validate_review_commitment(
                    dict(item),
                    plan=plan,
                )
            )
            for item in review_commitments
        ]
        if not normalized_reviews:
            raise ValueError(
                "barrier requires at least one cross-review commitment"
            )
        review_ids = [
            item["commitment_id"] for item in normalized_reviews
        ]
        review_assignments = [
            (item["round_id"], item["assignment_id"])
            for item in normalized_reviews
        ]
        if len(review_ids) != len(set(review_ids)) or len(
            review_assignments
        ) != len(set(review_assignments)):
            raise ValueError("cross-review commitments are duplicated")
        if not any(
            item["criticality"] == "core" for item in normalized_reviews
        ):
            raise ValueError(
                "barrier requires at least one core cross-review"
            )
        wave1_assignment_ids = {
            item["assignment_id"]
            for item in plan["wave1_commitments"]
        }
        peer_by_id = {item["node_id"]: item for item in peer_nodes}
        for commitment in normalized_reviews:
            if commitment["assignment_id"] in wave1_assignment_ids:
                raise ValueError(
                    "fresh wave requires a new assignment id"
                )
            if commitment["peer_node_id"] not in peer_by_id:
                raise ValueError(
                    "cross-review peer is not a wave-1 typed node"
                )
            if commitment["peer_node_id"] not in snapshot_node_ids:
                raise ValueError(
                    "cross-review peer is absent from the fresh snapshot"
                )
            binding = self._round_binding(
                round_id=commitment["round_id"],
                assignment_id=commitment["assignment_id"],
            )
            if (
                binding["snapshot_id"] != after_snapshot_id
                or binding["card"]["campaign_id"]
                != plan["campaign_id"]
                or binding["card"].get("host_task_scope_id")
                != plan["host_task_scope_id"]
            ):
                raise ValueError(
                    "cross-review round is not bound to the barrier "
                    "snapshot/campaign/host scope"
                )
            if require_wave2_unstarted and self._ingestion_evidence(
                round_id=commitment["round_id"],
                assignment_id=commitment["assignment_id"],
                required=False,
            ) is not None:
                raise ValueError(
                    "barrier must be sealed before wave-2 ingestion"
                )
            if require_wave2_unstarted:
                pending = self._pending_canonical_return(
                    round_id=commitment["round_id"],
                    assignment_id=commitment["assignment_id"],
                )
                if pending is not None:
                    raise ValueError(
                        "barrier must be sealed before a wave-2 canonical "
                        "return is written; "
                        + self._pending_return_blocker(
                            commitment,
                            pending,
                        )
                    )
        plan_path = self._plan_path(plan["pulse_id"])
        return {
            "schema_version": 1,
            "policy_revision": POLICY_REVISION_V4,
            "project_id": plan["project_id"],
            "pulse_id": plan["pulse_id"],
            "plan_sha256": sha256_bytes(plan_path.read_bytes()),
            "barrier_index": 1,
            "wave1_snapshot_id": plan["wave1_snapshot_id"],
            "after_snapshot_id": after_snapshot_id,
            "after_snapshot_sha256": sha256_bytes(
                snapshot_path.read_bytes()
            ),
            "wave1_evidence": wave1_evidence,
            "wave1_void_ids": wave1_void_ids,
            "peer_nodes": peer_nodes,
            "review_commitments": sorted(
                normalized_reviews,
                key=lambda item: item["commitment_id"],
            ),
            "actor": actor,
        }

    def _validate_barrier(
        self,
        barrier: dict[str, Any],
        *,
        plan: dict[str, Any],
    ) -> dict[str, Any]:
        require_exact_keys(
            barrier,
            required=_BARRIER_FIELDS,
            label="pulse barrier receipt",
        )
        if (
            barrier.get("schema_version") != 1
            or barrier.get("policy_revision") != POLICY_REVISION_V4
            or barrier.get("project_id") != plan["project_id"]
            or barrier.get("pulse_id") != plan["pulse_id"]
            or barrier.get("barrier_index") != 1
            or barrier.get("wave1_snapshot_id")
            != plan["wave1_snapshot_id"]
        ):
            raise ValueError("pulse barrier header/binding mismatch")
        barrier_id = require_string(barrier, "barrier_id")
        if (
            BARRIER_ID_RE.fullmatch(barrier_id) is None
            or barrier_id
            != _content_id("bbbar-", barrier, "barrier_id")
        ):
            raise ValueError("pulse barrier id/hash mismatch")
        require_string(barrier, "actor")
        validate_bb_snapshot_id(
            require_string(barrier, "after_snapshot_id")
        )
        for key in (
            "plan_sha256",
            "after_snapshot_sha256",
        ):
            if SHA256_RE.fullmatch(require_string(barrier, key)) is None:
                raise ValueError(f"pulse barrier {key} is invalid")
        reviews = barrier.get("review_commitments")
        if not isinstance(reviews, list) or any(
            not isinstance(item, dict) for item in reviews
        ):
            raise ValueError(
                "pulse barrier review_commitments must be objects"
            )
        for item in reviews:
            self._validate_review_commitment(item, plan=plan)
        for key in (
            "wave1_evidence",
            "wave1_void_ids",
            "peer_nodes",
        ):
            if not isinstance(barrier.get(key), list):
                raise ValueError(f"pulse barrier {key} must be a list")
        return barrier

    def derive_barrier(
        self,
        pulse_id: str,
        *,
        after_snapshot_id: str,
        review_commitments: list[dict[str, Any]],
        actor: str = "main",
    ) -> dict[str, Any]:
        plan = self.plan(pulse_id)
        self._require_not_aborted(plan, action="derive a barrier")
        self._require_plan_work_units_active(plan)
        self._require_commitments_active(review_commitments)
        semantic = self._barrier_semantic(
            plan,
            after_snapshot_id=after_snapshot_id,
            review_commitments=review_commitments,
            actor=actor,
            require_wave2_unstarted=True,
        )
        barrier = {
            **semantic,
            "barrier_id": _content_id(
                "bbbar-",
                semantic,
                "barrier_id",
            ),
        }
        self._validate_barrier(barrier, plan=plan)
        with self._mutation_lock():
            self._require_not_aborted(
                plan,
                action="derive a barrier",
            )
            self._require_plan_work_units_active(plan)
            self._require_commitments_active(
                barrier["review_commitments"]
            )
            self._write_control_record(
                self._barrier_path(pulse_id),
                barrier,
            )
        return {
            **barrier,
            "barrier_sha256": sha256_bytes(
                self._barrier_path(pulse_id).read_bytes()
            ),
        }

    def barrier(self, pulse_id: str) -> dict[str, Any]:
        plan = self.plan(pulse_id)
        barrier = self._validate_barrier(
            self._read_json(self._barrier_path(pulse_id)),
            plan=plan,
        )
        return barrier

    def _review_edge_errors(
        self,
        *,
        plan: dict[str, Any],
        barrier: dict[str, Any],
        commitment: dict[str, Any],
        ingestion: dict[str, Any],
        edge: dict[str, Any],
        nodes: dict[str, dict[str, Any]],
    ) -> list[str]:
        """Apply the same review semantics before and after ingestion."""

        errors: list[str] = []
        if edge["edge_id"] not in ingestion["edge_ids"]:
            errors.append(
                "cross-review edge is not in the assignee ingestion receipt"
            )
        if edge["edge_type"] not in commitment["allowed_edge_types"]:
            errors.append("cross-review edge type is not authorized")
        if (
            edge["created_by_assignment_id"]
            != commitment["assignment_id"]
        ):
            errors.append("cross-review edge author/assignment mismatch")
        if edge["target_node_id"] != commitment["peer_node_id"]:
            errors.append("cross-review edge target is not the bound peer")
        if edge["source_node_id"] not in ingestion["node_ids"]:
            errors.append(
                "cross-review edge source is not fresh return evidence"
            )
        source = nodes.get(edge["source_node_id"])
        peer = nodes.get(commitment["peer_node_id"])
        if source is None or peer is None:
            errors.append("cross-review edge has a missing local endpoint")
            return errors
        if (
            source["created_by_assignment_id"]
            != commitment["assignment_id"]
            or source["node_type"] in NON_PEER_NODE_TYPES
        ):
            errors.append(
                "cross-review source is not a fresh typed assignee node"
            )
        peer_bindings = [
            item
            for item in barrier["peer_nodes"]
            if item["node_id"] == commitment["peer_node_id"]
        ]
        if len(peer_bindings) != 1:
            errors.append("barrier does not uniquely bind the peer node")
        elif (
            peer["created_by_assignment_id"]
            != peer_bindings[0]["created_by_assignment_id"]
            or peer["created_by_assignment_id"]
            == commitment["assignment_id"]
        ):
            errors.append("cross-review is not cross-worker")
        payload = edge.get("payload")
        required_payload = {
            "exchange_schema_version",
            "pulse_id",
            "barrier_id",
            "commitment_id",
            "peer_node_id",
            "peer_node_sha256",
            "check",
            "disposition",
        }
        if not isinstance(payload, dict) or set(payload) != required_payload:
            return errors + ["cross-review payload schema is not exact"]
        if (
            payload.get("exchange_schema_version") != 1
            or payload.get("pulse_id") != plan["pulse_id"]
            or payload.get("barrier_id") != barrier["barrier_id"]
            or payload.get("commitment_id")
            != commitment["commitment_id"]
            or payload.get("peer_node_id")
            != commitment["peer_node_id"]
            or payload.get("peer_node_sha256")
            != sha256_bytes(canonical_json_bytes(peer))
        ):
            errors.append("cross-review payload binding mismatch")
        check = payload.get("check")
        if not isinstance(check, dict) or set(check) != {
            "kind",
            "method",
            "witness_refs",
        }:
            errors.append("cross-review check schema is not exact")
        else:
            if check.get("kind") not in CHECK_KINDS:
                errors.append("cross-review check kind is invalid")
            if (
                not isinstance(check.get("method"), str)
                or not check["method"].strip()
            ):
                errors.append(
                    "cross-review check method must be nonempty"
                )
            witness_refs = check.get("witness_refs")
            if (
                not isinstance(witness_refs, list)
                or not witness_refs
                or any(
                    not isinstance(item, str) or not item.strip()
                    for item in witness_refs
                )
                or len(witness_refs) != len(set(witness_refs))
            ):
                errors.append(
                    "cross-review witness_refs must be unique and nonempty"
                )
            else:
                artifact_refs = {
                    item.get("path")
                    for item in ingestion["artifacts"]
                    if isinstance(item, dict)
                }
                authorized = (
                    set(ingestion["node_ids"])
                    | set(ingestion["edge_ids"])
                    | artifact_refs
                )
                if not set(witness_refs).issubset(authorized):
                    errors.append(
                        "cross-review witness_refs contain unbound evidence"
                    )
                if edge["source_node_id"] not in witness_refs:
                    errors.append(
                        "cross-review witnesses must name the fresh source node"
                    )
        disposition = payload.get("disposition")
        if not isinstance(disposition, dict) or set(disposition) != {
            "kind",
            "boundary",
        }:
            errors.append(
                "cross-review disposition schema is not exact"
            )
        else:
            kind = disposition.get("kind")
            if kind not in DISPOSITIONS:
                errors.append("cross-review disposition kind is invalid")
            if kind not in RELATION_DISPOSITIONS.get(
                edge["edge_type"],
                set(),
            ):
                errors.append(
                    "cross-review disposition is incompatible with relation"
                )
            if (
                not isinstance(disposition.get("boundary"), str)
                or not disposition["boundary"].strip()
            ):
                errors.append(
                    "cross-review correction/no-correction boundary "
                    "must be nonempty"
                )
        return errors

    def preflight_review_delta(
        self,
        *,
        task_card: dict[str, Any],
        delta: dict[str, Any],
        artifacts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Reject a malformed pulse exchange before it gains visibility."""

        candidate_edges = [
            edge
            for edge in delta.get("add_edges", [])
            if isinstance(edge, dict)
            and isinstance(edge.get("payload"), dict)
            and {
                "exchange_schema_version",
                "pulse_id",
                "barrier_id",
                "commitment_id",
            }.intersection(edge["payload"])
        ]
        if not candidate_edges:
            return {"checked_review_edges": 0}
        if len(candidate_edges) != 1:
            raise ValueError(
                "pulse cross-review preflight requires exactly one "
                "commitment-bound edge"
            )
        edge = candidate_edges[0]
        payload = edge["payload"]
        pulse_id = payload.get("pulse_id")
        commitment_id = payload.get("commitment_id")
        if not isinstance(pulse_id, str) or not isinstance(
            commitment_id, str
        ):
            raise ValueError(
                "pulse cross-review preflight requires pulse_id and "
                "commitment_id"
            )
        plan = self.plan(pulse_id)
        self._require_not_aborted(
            plan,
            action="preflight a review delta",
        )
        if self._closure_path(pulse_id).exists():
            existing = self._ingestion_evidence(
                round_id=task_card["round_id"],
                assignment_id=task_card["assignment_id"],
                required=False,
            )
            if existing is not None:
                return {
                    "checked_review_edges": 0,
                    "historical_ingested": True,
                }
            raise ValueError("closed pulse cannot accept a review delta")
        barrier = self.barrier(pulse_id)
        matches = [
            item
            for item in barrier["review_commitments"]
            if item["commitment_id"] == commitment_id
        ]
        if len(matches) != 1:
            raise ValueError(
                "pulse cross-review preflight commitment is not unique"
            )
        commitment = matches[0]
        if (
            commitment["round_id"] != task_card["round_id"]
            or commitment["assignment_id"]
            != task_card["assignment_id"]
            or plan["project_id"] != task_card["project_id"]
        ):
            raise ValueError(
                "pulse cross-review preflight task binding mismatch"
            )
        nodes = self.blackboard.nodes()
        nodes.update(
            {
                node["node_id"]: node
                for node in delta.get("add_nodes", [])
                if isinstance(node, dict)
                and isinstance(node.get("node_id"), str)
            }
        )
        ingestion = {
            "node_ids": [
                node["node_id"] for node in delta.get("add_nodes", [])
            ],
            "edge_ids": [
                item["edge_id"] for item in delta.get("add_edges", [])
            ],
            "artifacts": list(artifacts),
        }
        errors = self._review_edge_errors(
            plan=plan,
            barrier=barrier,
            commitment=commitment,
            ingestion=ingestion,
            edge=edge,
            nodes=nodes,
        )
        if errors:
            raise ValueError(
                "pulse cross-review preflight failed: "
                + "; ".join(sorted(set(errors)))
            )
        return {
            "checked_review_edges": 1,
            "commitment_id": commitment_id,
            "edge_id": edge["edge_id"],
        }

    def _meaningful_edge(
        self,
        *,
        plan: dict[str, Any],
        barrier: dict[str, Any],
        commitment: dict[str, Any],
        ingestion: dict[str, Any],
    ) -> tuple[str | None, list[str]]:
        errors: list[str] = []
        nodes = self.blackboard.nodes()
        edges = self.blackboard.edges()
        matches = [
            edge
            for edge in edges.values()
            if edge.get("payload", {}).get("commitment_id")
            == commitment["commitment_id"]
        ]
        if len(matches) != 1:
            return None, [
                "commitment must bind exactly one visible cross-review edge"
            ]
        edge = matches[0]
        errors.extend(
            self._review_edge_errors(
                plan=plan,
                barrier=barrier,
                commitment=commitment,
                ingestion=ingestion,
                edge=edge,
                nodes=nodes,
            )
        )
        return edge["edge_id"], errors

    def _review_assessment(
        self,
        plan: dict[str, Any],
        barrier: dict[str, Any],
    ) -> dict[str, Any]:
        evidence: list[dict[str, Any]] = []
        blockers: list[str] = []
        optional_void_ids: list[str] = []
        procedural_ready = True
        seen_host_context_ids: set[str] = set()
        for commitment in barrier["review_commitments"]:
            void = self._void_receipt(plan, commitment)
            ingestion = self._ingestion_evidence(
                round_id=commitment["round_id"],
                assignment_id=commitment["assignment_id"],
                required=False,
            )
            if void is not None and ingestion is not None:
                blockers.append(
                    f"{commitment['commitment_id']}: voided commitment "
                    "later gained an ingestion receipt"
                )
                evidence.append(
                    {
                        "commitment_id": commitment["commitment_id"],
                        "status": "breached",
                        "edge_id": None,
                        "errors": [blockers[-1]],
                    }
                )
                continue
            if void is not None:
                optional_void_ids.append(void["void_id"])
                evidence.append(
                    {
                        "commitment_id": commitment["commitment_id"],
                        "status": "voided_optional",
                        "edge_id": None,
                        "errors": [],
                    }
                )
                continue
            if ingestion is None:
                procedural_ready = False
                pending = self._pending_canonical_return(
                    round_id=commitment["round_id"],
                    assignment_id=commitment["assignment_id"],
                )
                detail = (
                    self._pending_return_blocker(
                        commitment,
                        pending,
                    )
                    if pending is not None
                    else "ingestion receipt is missing"
                )
                blockers.append(
                    f"{commitment['commitment_id']}: {detail}"
                )
                evidence.append(
                    {
                        "commitment_id": commitment["commitment_id"],
                        "status": "open",
                        "edge_id": None,
                        "errors": [blockers[-1]],
                    }
                )
                continue
            edge_id, errors = self._meaningful_edge(
                plan=plan,
                barrier=barrier,
                commitment=commitment,
                ingestion=ingestion,
            )
            dispatch = self._host_dispatch(
                plan,
                barrier,
                commitment,
            )
            dispatch_id: str | None = None
            if dispatch is None:
                errors.append(
                    "trusted host clean-context receipt is missing"
                )
            else:
                dispatch_id = dispatch["dispatch_id"]
                if dispatch["issuer"] not in plan[
                    "trusted_host_issuers"
                ]:
                    errors.append(
                        "host-dispatch issuer is not trusted by the "
                        "immutable pulse plan"
                    )
                if (
                    dispatch["host_context_id"]
                    in seen_host_context_ids
                ):
                    errors.append(
                        "host context id is reused inside wave 2"
                    )
                seen_host_context_ids.add(
                    dispatch["host_context_id"]
                )
            status = "fulfilled" if not errors else "breached"
            if errors:
                blockers.extend(
                    f"{commitment['commitment_id']}: {item}"
                    for item in errors
                )
            evidence.append(
                {
                    "commitment_id": commitment["commitment_id"],
                    "status": status,
                    "ingestion_sha256": ingestion[
                        "ingestion_sha256"
                    ],
                    "blackboard_transaction_id": ingestion[
                        "blackboard_transaction_id"
                    ],
                    "host_dispatch_id": dispatch_id,
                    "edge_id": edge_id,
                    "errors": errors,
                }
            )
        machine_verified_ready = procedural_ready and all(
            item["status"] in {"fulfilled", "voided_optional"}
            for item in evidence
        )
        return {
            "review_evidence": sorted(
                evidence,
                key=lambda item: item["commitment_id"],
            ),
            "optional_void_ids": sorted(optional_void_ids),
            "procedural_ready": procedural_ready,
            "machine_verified_ready": machine_verified_ready,
            "blockers": sorted(blockers),
        }

    def _closure_semantic(
        self,
        plan: dict[str, Any],
        barrier: dict[str, Any],
        *,
        actor: str,
    ) -> dict[str, Any]:
        assessment = self._review_assessment(plan, barrier)
        if not assessment["procedural_ready"]:
            raise ValueError(
                "pulse closure is premature: "
                + "; ".join(assessment["blockers"])
            )
        return {
            "schema_version": 1,
            "policy_revision": POLICY_REVISION_V4,
            "project_id": plan["project_id"],
            "pulse_id": plan["pulse_id"],
            "plan_sha256": sha256_bytes(
                self._plan_path(plan["pulse_id"]).read_bytes()
            ),
            "barrier_id": barrier["barrier_id"],
            "barrier_sha256": sha256_bytes(
                self._barrier_path(plan["pulse_id"]).read_bytes()
            ),
            **assessment,
            "truth_boundary": (
                "collaboration readiness only; no mathematical truth or "
                "fact admission"
            ),
            "actor": actor,
        }

    def _validate_closure(
        self,
        closure: dict[str, Any],
        *,
        plan: dict[str, Any],
        barrier: dict[str, Any],
    ) -> dict[str, Any]:
        require_exact_keys(
            closure,
            required=_CLOSURE_FIELDS,
            label="pulse closure receipt",
        )
        if (
            closure.get("schema_version") != 1
            or closure.get("policy_revision") != POLICY_REVISION_V4
            or closure.get("project_id") != plan["project_id"]
            or closure.get("pulse_id") != plan["pulse_id"]
            or closure.get("barrier_id") != barrier["barrier_id"]
        ):
            raise ValueError("pulse closure header/binding mismatch")
        closure_id = require_string(closure, "closure_id")
        if (
            CLOSURE_ID_RE.fullmatch(closure_id) is None
            or closure_id
            != _content_id("bbclose-", closure, "closure_id")
        ):
            raise ValueError("pulse closure id/hash mismatch")
        for key in ("plan_sha256", "barrier_sha256"):
            if SHA256_RE.fullmatch(require_string(closure, key)) is None:
                raise ValueError(f"pulse closure {key} is invalid")
        if closure.get("procedural_ready") is not True:
            raise ValueError("persisted pulse closure must be procedural")
        if not isinstance(closure.get("machine_verified_ready"), bool):
            raise ValueError(
                "pulse machine_verified_ready must be boolean"
            )
        for key in (
            "review_evidence",
            "optional_void_ids",
            "blockers",
        ):
            if not isinstance(closure.get(key), list):
                raise ValueError(f"pulse closure {key} must be a list")
        require_string(closure, "truth_boundary")
        require_string(closure, "actor")
        return closure

    def derive_closure(
        self,
        pulse_id: str,
        *,
        actor: str = "main",
    ) -> dict[str, Any]:
        plan = self.plan(pulse_id)
        self._require_not_aborted(plan, action="derive a closure")
        self._require_plan_work_units_active(plan)
        barrier = self.barrier(pulse_id)
        self._require_plan_work_units_active(plan, barrier=barrier)
        semantic = self._closure_semantic(
            plan,
            barrier,
            actor=actor,
        )
        closure = {
            **semantic,
            "closure_id": _content_id(
                "bbclose-",
                semantic,
                "closure_id",
            ),
        }
        self._validate_closure(
            closure,
            plan=plan,
            barrier=barrier,
        )
        with self._mutation_lock():
            self._require_not_aborted(
                plan,
                action="derive a closure",
            )
            self._require_plan_work_units_active(
                plan,
                barrier=barrier,
            )
            self._write_control_record(
                self._closure_path(pulse_id),
                closure,
            )
        return {
            **closure,
            "closure_sha256": sha256_bytes(
                self._closure_path(pulse_id).read_bytes()
            ),
        }

    def closure(self, pulse_id: str) -> dict[str, Any]:
        plan = self.plan(pulse_id)
        barrier = self.barrier(pulse_id)
        return self._validate_closure(
            self._read_json(self._closure_path(pulse_id)),
            plan=plan,
            barrier=barrier,
        )

    def status(self, pulse_id: str) -> dict[str, Any]:
        plan = self.plan(pulse_id)
        abort = self._abort_receipt(plan)
        if abort is not None:
            return {
                "pulse_id": pulse_id,
                "state": "aborted",
                "procedural_ready": False,
                "machine_verified_ready": False,
                "abort_id": abort["abort_id"],
                **(
                    {
                        "core_failure_id": abort[
                            "core_failure_id"
                        ]
                    }
                    if "core_failure_id" in abort
                    else {}
                ),
                "failure_phase": abort["failure_phase"],
                "blockers": [
                    "pulse aborted during "
                    f"{abort['failure_phase']}: {abort['reason']}"
                ],
            }
        barrier_path = self._barrier_path(pulse_id)
        closure_path = self._closure_path(pulse_id)
        if not barrier_path.exists():
            blockers = ["barrier receipt is missing"]
            for commitment in plan["wave1_commitments"]:
                if self._void_receipt(plan, commitment) is not None:
                    continue
                if self._ingestion_evidence(
                    round_id=commitment["round_id"],
                    assignment_id=commitment["assignment_id"],
                    required=False,
                ) is not None:
                    continue
                pending = self._pending_canonical_return(
                    round_id=commitment["round_id"],
                    assignment_id=commitment["assignment_id"],
                )
                if pending is not None:
                    blockers.append(
                        self._pending_return_blocker(
                            commitment,
                            pending,
                        )
                    )
            return {
                "pulse_id": pulse_id,
                "state": "wave1_open",
                "procedural_ready": False,
                "machine_verified_ready": False,
                "blockers": blockers,
            }
        barrier = self.barrier(pulse_id)
        assessment = self._review_assessment(plan, barrier)
        if closure_path.exists():
            closure = self.closure(pulse_id)
            state = (
                "closed_machine_ready"
                if closure["machine_verified_ready"]
                else "closed_fail_closed"
            )
        elif assessment["procedural_ready"]:
            state = (
                "ready_to_close"
                if assessment["machine_verified_ready"]
                else "breached_ready_to_close"
            )
        else:
            state = "wave2_open"
        return {
            "pulse_id": pulse_id,
            "state": state,
            **assessment,
        }

    def audit(self, pulse_id: str | None = None) -> dict[str, Any]:
        errors: list[str] = []
        warnings: list[str] = []
        try:
            control_count, control_bytes = (
                self._pulse_control_inventory()
            )
            if control_count > DEFAULT_HARD_CAPS[
                "max_pulse_control_records"
            ]:
                raise ValueError(
                    "pulse control record count exceeds the hard cap"
                )
            if control_bytes > DEFAULT_HARD_CAPS[
                "max_pulse_control_bytes_total"
            ]:
                raise ValueError(
                    "pulse control bytes exceed the total hard cap"
                )
        except Exception as exc:
            errors.append(f"pulse control hard-cap audit: {exc}")
        if pulse_id is None:
            pulse_ids = sorted(
                path.parent.name
                for path in self.root.glob("bbp-*/plan.json")
            )
        else:
            pulse_ids = [pulse_id]
        statuses: dict[str, dict[str, Any]] = {}
        for current in pulse_ids:
            try:
                plan = self.plan(current)
                abort = self._abort_receipt(plan)
                known_commitments = {
                    item["commitment_id"]: item
                    for item in plan["wave1_commitments"]
                }
                barrier_path = self._barrier_path(current)
                closure_path = self._closure_path(current)
                if abort is not None and closure_path.exists():
                    raise ValueError(
                        "pulse has mutually exclusive abort and closure "
                        "receipts"
                    )
                barrier: dict[str, Any] | None = None
                if barrier_path.exists():
                    barrier = self.barrier(current)
                    known_commitments.update(
                        {
                            item["commitment_id"]: item
                            for item in barrier["review_commitments"]
                        }
                    )
                    recomputed = self._barrier_semantic(
                        plan,
                        after_snapshot_id=barrier[
                            "after_snapshot_id"
                        ],
                        review_commitments=barrier[
                            "review_commitments"
                        ],
                        actor=barrier["actor"],
                        require_wave2_unstarted=False,
                    )
                    expected = {
                        **recomputed,
                        "barrier_id": _content_id(
                            "bbbar-",
                            recomputed,
                            "barrier_id",
                        ),
                    }
                    if expected != barrier:
                        raise ValueError(
                            "barrier differs from recomputed evidence"
                        )
                failures: list[tuple[dict[str, Any], Path]] = []
                for failure_path in sorted(
                    self._pulse_dir(current).glob(
                        "core-failures/*.json"
                    )
                ):
                    commitment = known_commitments.get(
                        failure_path.stem
                    )
                    if commitment is None:
                        raise ValueError(
                            "core-ingest failure names an unknown "
                            "commitment"
                        )
                    failure = self._validate_core_failure(
                        self._read_json(failure_path),
                        plan=plan,
                        commitment=commitment,
                    )
                    return_path = contained_path(
                        self.project_root,
                        failure["return_relpath"],
                        "core-ingest failure return path",
                    )
                    if (
                        not return_path.is_file()
                        or return_path.is_symlink()
                    ):
                        raise ValueError(
                            "core-ingest failure canonical return is "
                            "missing or unsafe"
                        )
                    if sha256_bytes(
                        return_path.read_bytes()
                    ) != failure["return_sha256"]:
                        raise ValueError(
                            "core-ingest failure canonical return hash "
                            "mismatch"
                        )
                    failures.append((failure, failure_path))
                abort_failure_keys = (
                    set(abort).intersection(
                        _ABORT_CORE_FAILURE_FIELDS
                    )
                    if abort is not None
                    else set()
                )
                if failures:
                    if abort is None:
                        raise ValueError(
                            "core-ingest failure evidence exists without "
                            "a pulse abort"
                        )
                    if len(failures) != 1:
                        raise ValueError(
                            "one pulse abort cannot bind multiple "
                            "core-ingest failures"
                        )
                    failure, failure_path = failures[0]
                    if (
                        abort_failure_keys
                        != _ABORT_CORE_FAILURE_FIELDS
                        or abort.get("core_failure_id")
                        != failure["failure_id"]
                        or abort.get("core_failure_sha256")
                        != sha256_bytes(failure_path.read_bytes())
                    ):
                        raise ValueError(
                            "pulse abort/core-ingest failure evidence "
                            "mismatch"
                        )
                elif abort_failure_keys:
                    raise ValueError(
                        "pulse abort binds missing core-ingest failure "
                        "evidence"
                    )
                for void_path in sorted(
                    self._pulse_dir(current).glob(
                        "voids/bbpc-*.json"
                    )
                ):
                    commitment = known_commitments.get(void_path.stem)
                    if commitment is None:
                        raise ValueError(
                            "void receipt names an unknown commitment"
                        )
                    self._validate_void(
                        self._read_json(void_path),
                        plan=plan,
                        commitment=commitment,
                    )
                if barrier is not None:
                    for dispatch_path in sorted(
                        self._pulse_dir(current).glob(
                            "host-dispatches/bbpc-*.json"
                        )
                    ):
                        commitment = known_commitments.get(
                            dispatch_path.stem
                        )
                        if (
                            commitment is None
                            or commitment.get("phase")
                            != "wave2_cross_review"
                        ):
                            raise ValueError(
                                "host-dispatch receipt names an unknown "
                                "review commitment"
                            )
                        self._validate_host_dispatch(
                            self._read_json(dispatch_path),
                            plan=plan,
                            barrier=barrier,
                            commitment=commitment,
                        )
                if closure_path.exists():
                    if barrier is None:
                        raise ValueError(
                            "closure exists without a barrier"
                        )
                    closure = self.closure(current)
                    semantic = self._closure_semantic(
                        plan,
                        barrier,
                        actor=closure["actor"],
                    )
                    expected_closure = {
                        **semantic,
                        "closure_id": _content_id(
                            "bbclose-",
                            semantic,
                            "closure_id",
                        ),
                    }
                    if expected_closure != closure:
                        raise ValueError(
                            "closure differs from recomputed evidence"
                        )
                statuses[current] = self.status(current)
                if abort is None and not barrier_path.exists():
                    warnings.append(
                        f"{current}: pulse has no barrier"
                    )
            except Exception as exc:
                errors.append(f"{current}: {exc}")
        return {
            "ok": not errors,
            "errors": errors,
            "warnings": warnings,
            "pulses": statuses,
            "federation": {
                "mode": "disabled",
                "raw_remote_endpoints": "rejected",
            },
        }


__all__ = [
    "ABORT_ID_RE",
    "BARRIER_ID_RE",
    "CHECK_KINDS",
    "CLOSURE_ID_RE",
    "COMMITMENT_ID_RE",
    "CORE_FAILURE_ID_RE",
    "DISPOSITIONS",
    "FRESH_CONTEXT_CONTRACT_V1",
    "HOST_DISPATCH_ID_RE",
    "MEANINGFUL_EDGE_TYPES",
    "PULSE_ID_RE",
    "PulseStore",
    "VOID_ID_RE",
]

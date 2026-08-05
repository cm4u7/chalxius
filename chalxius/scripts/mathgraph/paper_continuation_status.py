from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import SHA256_RE, sha256_bytes, sha256_json, validate_memory_id


PAPER_CONTINUATION_STATUS_INDEX_REVISION = (
    "chalxius-v5-paper-continuation-status-index-1"
)

_COUNT_FIELDS = {
    "total",
    "frontier_materialized",
    "researched",
    "dispositioned",
    "unresolved",
    "successor_mapped",
    "revised_manuscript_covered",
}
_DEPENDENCY_NAMES = {
    "plans",
    "materializations",
    "dispositions",
    "writing_artifacts",
    "research_entries",
    "paper_snapshots",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _exact(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{label} fields are not exact")
    return value


def _strings(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise ValueError(f"{label} must be a list of nonempty strings")
    if len(value) != len(set(value)):
        raise ValueError(f"{label} must not contain duplicates")
    return list(value)


class PaperContinuationStatusIndex:
    """Content-addressed, fail-closed routine status for Paper continuation.

    Full ``PaperContinuationManager.status`` remains the forensic validator.
    This index is a derived nontruth monitor: immutable states and receipts are
    selected by one atomically replaced head.  The head binds directory
    generation fingerprints for every source family that can change adequacy.
    A crash or an out-of-band append therefore makes routine reads fail closed
    instead of silently falling back to a graph-scale reconstruction.
    """

    def __init__(
        self,
        continuation: Any,
        *,
        continuation_contract_revision: str,
        worker_outcomes: set[str] | frozenset[str],
        status_detail_fields: list[str],
    ) -> None:
        self.continuation = continuation
        self.lifecycle = continuation.lifecycle
        self.store = continuation.store
        self.project_id = self.store.project_id()
        self.continuation_contract_revision = continuation_contract_revision
        self.worker_outcomes = frozenset(worker_outcomes)
        self.status_detail_fields = list(status_detail_fields)
        self.root = continuation.root / "status-index"
        self.states_dir = self.root / "states" / "by-sha256"
        self.receipts_dir = self.root / "receipts" / "by-sha256"
        self.lineage_dir = self.root / "research-lineage" / "by-id"
        self.head_path = self.root / "HEAD.json"

    def initialize(self) -> None:
        for path in (self.states_dir, self.receipts_dir, self.lineage_dir):
            path.mkdir(parents=True, exist_ok=True)

    def _plan_files_present(self) -> bool:
        return self.continuation.plans_dir.exists() and any(
            self.continuation.plans_dir.glob("pcp-*.json")
        )

    def _dependency_directories(self) -> dict[str, Path]:
        return {
            "plans": self.continuation.plans_dir,
            "materializations": self.continuation.materializations_dir,
            "dispositions": self.continuation.dispositions_dir,
            "writing_artifacts": self.continuation.writing_artifacts_dir,
            "research_entries": self.lifecycle.research_entries_dir,
            "paper_snapshots": self.store.paper_logic().snapshots_dir,
        }

    def _directory_fingerprint(self, path: Path) -> dict[str, Any]:
        relative = path.relative_to(self.store.root).as_posix()
        if not path.exists():
            return {
                "path": relative,
                "exists": False,
                "device": 0,
                "inode": 0,
                "mtime_ns": 0,
                "ctime_ns": 0,
            }
        if path.is_symlink() or not path.is_dir():
            raise ValueError(f"Paper status dependency is unsafe: {relative}")
        stat = path.stat()
        return {
            "path": relative,
            "exists": True,
            "device": int(stat.st_dev),
            "inode": int(stat.st_ino),
            "mtime_ns": int(stat.st_mtime_ns),
            "ctime_ns": int(stat.st_ctime_ns),
        }

    def _dependency_fingerprints(self) -> dict[str, dict[str, Any]]:
        return {
            name: self._directory_fingerprint(path)
            for name, path in sorted(self._dependency_directories().items())
        }

    def _validate_head(
        self,
        value: Any,
        *,
        require_current: bool,
    ) -> dict[str, Any]:
        fields = {
            "schema_version",
            "contract_revision",
            "index_revision",
            "project_id",
            "generation",
            "plan_heads",
            "dependency_fingerprints",
            "last_event",
            "updated_at",
            "truth_effect",
            "head_sha256",
        }
        head = _exact(value, fields, "Paper continuation status head")
        if (
            head["schema_version"] != 1
            or head["contract_revision"] != self.continuation_contract_revision
            or head["index_revision"]
            != PAPER_CONTINUATION_STATUS_INDEX_REVISION
            or head["project_id"] != self.project_id
            or not isinstance(head["generation"], int)
            or head["generation"] < 1
            or not isinstance(head["last_event"], str)
            or not head["last_event"]
            or not isinstance(head["updated_at"], str)
            or not head["updated_at"]
            or head["truth_effect"] != "none"
        ):
            raise ValueError("Paper continuation status head binding is invalid")
        plan_heads = head["plan_heads"]
        if not isinstance(plan_heads, dict):
            raise ValueError("Paper continuation status plan heads must be an object")
        for plan_id, item in plan_heads.items():
            self.continuation.validate_plan_id(plan_id)
            _exact(
                item,
                {"state_sha256", "status_receipt_sha256"},
                "Paper continuation status plan head",
            )
            if any(
                not isinstance(item[key], str)
                or SHA256_RE.fullmatch(item[key]) is None
                for key in ("state_sha256", "status_receipt_sha256")
            ):
                raise ValueError("Paper continuation status plan digest is invalid")
        fingerprints = head["dependency_fingerprints"]
        if not isinstance(fingerprints, dict) or set(fingerprints) != _DEPENDENCY_NAMES:
            raise ValueError(
                "Paper continuation status dependency inventory is invalid"
            )
        for name, item in fingerprints.items():
            _exact(
                item,
                {"path", "exists", "device", "inode", "mtime_ns", "ctime_ns"},
                f"Paper continuation dependency fingerprint {name}",
            )
            if (
                not isinstance(item["path"], str)
                or not isinstance(item["exists"], bool)
                or any(
                    not isinstance(item[key], int) or item[key] < 0
                    for key in ("device", "inode", "mtime_ns", "ctime_ns")
                )
            ):
                raise ValueError(
                    "Paper continuation dependency fingerprint is invalid"
                )
        without_hash = {key: item for key, item in head.items() if key != "head_sha256"}
        if head["head_sha256"] != sha256_json(without_hash):
            raise ValueError("Paper continuation status head hash mismatch")
        if require_current and fingerprints != self._dependency_fingerprints():
            raise ValueError(
                "Paper continuation status index is stale after a source mutation; "
                "run paper-continuation-status-index-rebuild explicitly"
            )
        return head

    def _load_head(
        self,
        *,
        require_current: bool,
        allow_missing: bool = False,
    ) -> dict[str, Any] | None:
        if not self.head_path.exists():
            if self.head_path.is_symlink():
                raise ValueError("Paper continuation status head is unsafe")
            if self._plan_files_present() and not allow_missing:
                raise ValueError(
                    "Paper continuation status index is missing for declared plans; "
                    "run paper-continuation-status-index-rebuild explicitly"
                )
            return None
        if self.head_path.is_symlink() or not self.head_path.is_file():
            raise ValueError("Paper continuation status head is unsafe")
        return self._validate_head(
            self.store._read_json(self.head_path),
            require_current=require_current,
        )

    def require_current_if_declared(self) -> None:
        if self._plan_files_present():
            self._load_head(require_current=True)

    def release_generation_surface(self) -> dict[str, Any]:
        """Return the bounded filesystem generation used by release fallback.

        This deliberately does not interpret an untrusted or stale HEAD.  The
        raw HEAD file hash and the current protected-directory fingerprints
        let a completed full-validation fallback be reused only while the
        exact surface it validated remains unchanged.
        """

        observed_head: dict[str, Any] = {
            "present": False,
            "file_sha256": None,
            "declared_generation": None,
            "declared_head_sha256": None,
        }
        if self.head_path.exists():
            if self.head_path.is_symlink() or not self.head_path.is_file():
                raise ValueError("Paper continuation status head is unsafe")
            raw = self.head_path.read_bytes()
            observed_head["present"] = True
            observed_head["file_sha256"] = sha256_bytes(raw)
            try:
                value = self.store._read_json(self.head_path)
            except Exception:
                value = None
            if isinstance(value, dict):
                generation = value.get("generation")
                digest = value.get("head_sha256")
                if isinstance(generation, int) and generation >= 1:
                    observed_head["declared_generation"] = generation
                if isinstance(digest, str) and SHA256_RE.fullmatch(digest):
                    observed_head["declared_head_sha256"] = digest
        elif self.head_path.is_symlink():
            raise ValueError("Paper continuation status head is unsafe")
        semantic = {
            "index_revision": PAPER_CONTINUATION_STATUS_INDEX_REVISION,
            "project_id": self.project_id,
            "observed_head": observed_head,
            "dependency_fingerprints": self._dependency_fingerprints(),
        }
        return {**semantic, "surface_sha256": sha256_json(semantic)}

    def release_witness(self, plan_id: str) -> dict[str, Any]:
        """Return one bounded, current, content-addressed plan witness.

        The witness selects existing immutable state and receipt objects.  It
        is a release proof projection, not a second continuation state owner.
        """

        plan_id = self.continuation.validate_plan_id(plan_id)
        head = self._load_head(require_current=True)
        if head is None or plan_id not in head["plan_heads"]:
            raise KeyError(f"unknown Paper continuation plan: {plan_id}")
        entry = head["plan_heads"][plan_id]
        state = self._load_state(entry["state_sha256"])
        receipt = self._load_receipt(entry["status_receipt_sha256"])
        if (
            state["plan_id"] != plan_id
            or receipt["plan_id"] != plan_id
            or receipt["state_sha256"] != state["state_sha256"]
            or entry["state_sha256"] != state["state_sha256"]
            or entry["status_receipt_sha256"]
            != receipt["status_receipt_sha256"]
        ):
            raise ValueError("Paper continuation release witness binding drifted")
        semantic = {
            "schema_version": 1,
            "contract_revision": self.continuation_contract_revision,
            "index_revision": PAPER_CONTINUATION_STATUS_INDEX_REVISION,
            "project_id": self.project_id,
            "plan_id": plan_id,
            "plan_record_sha256": state["plan_record_sha256"],
            "generation": head["generation"],
            "head_sha256": head["head_sha256"],
            "state_sha256": state["state_sha256"],
            "status_receipt_sha256": receipt["status_receipt_sha256"],
            "adequacy_receipt_sha256": receipt["adequacy_receipt_sha256"],
            "adequacy_complete": receipt["adequacy_complete"],
            "source_snapshot_current": receipt["source_snapshot_current"],
            "truth_effect": "none",
        }
        return {**semantic, "witness_sha256": sha256_json(semantic)}

    def validate_release_witness(
        self,
        value: Any,
        *,
        require_current: bool,
    ) -> dict[str, Any]:
        fields = {
            "schema_version",
            "contract_revision",
            "index_revision",
            "project_id",
            "plan_id",
            "plan_record_sha256",
            "generation",
            "head_sha256",
            "state_sha256",
            "status_receipt_sha256",
            "adequacy_receipt_sha256",
            "adequacy_complete",
            "source_snapshot_current",
            "truth_effect",
            "witness_sha256",
        }
        witness = _exact(value, fields, "Paper continuation release witness")
        plan_id = self.continuation.validate_plan_id(witness["plan_id"])
        if (
            witness["schema_version"] != 1
            or witness["contract_revision"]
            != self.continuation_contract_revision
            or witness["index_revision"]
            != PAPER_CONTINUATION_STATUS_INDEX_REVISION
            or witness["project_id"] != self.project_id
            or not isinstance(witness["generation"], int)
            or witness["generation"] < 1
            or any(
                not isinstance(witness[field], str)
                or SHA256_RE.fullmatch(witness[field]) is None
                for field in (
                    "plan_record_sha256",
                    "head_sha256",
                    "state_sha256",
                    "status_receipt_sha256",
                    "adequacy_receipt_sha256",
                    "witness_sha256",
                )
            )
            or not isinstance(witness["adequacy_complete"], bool)
            or not isinstance(witness["source_snapshot_current"], bool)
            or witness["truth_effect"] != "none"
        ):
            raise ValueError("Paper continuation release witness is invalid")
        semantic = {
            key: item for key, item in witness.items() if key != "witness_sha256"
        }
        if witness["witness_sha256"] != sha256_json(semantic):
            raise ValueError("Paper continuation release witness hash mismatch")
        state = self._load_state(witness["state_sha256"])
        receipt = self._load_receipt(witness["status_receipt_sha256"])
        if (
            state["plan_id"] != plan_id
            or state["plan_record_sha256"] != witness["plan_record_sha256"]
            or receipt["state_sha256"] != witness["state_sha256"]
            or receipt["plan_id"] != plan_id
            or receipt["adequacy_receipt_sha256"]
            != witness["adequacy_receipt_sha256"]
            or receipt["adequacy_complete"] != witness["adequacy_complete"]
            or receipt["source_snapshot_current"]
            != witness["source_snapshot_current"]
        ):
            raise ValueError("Paper continuation release witness CAS binding drifted")
        head: dict[str, Any] | None = None
        if require_current:
            head = self._load_head(require_current=True)
            if head is None:
                raise ValueError("Paper continuation release witness HEAD is missing")
            entry = head["plan_heads"].get(plan_id)
            if (
                head["generation"] != witness["generation"]
                or head["head_sha256"] != witness["head_sha256"]
                or entry
                != {
                    "state_sha256": witness["state_sha256"],
                    "status_receipt_sha256": witness[
                        "status_receipt_sha256"
                    ],
                }
            ):
                raise ValueError(
                    "Paper continuation release witness is stale against current HEAD"
                )
        return {
            "witness": witness,
            "state": state,
            "receipt": receipt,
            "head": head,
        }

    def _write_head(
        self,
        *,
        base_head: dict[str, Any] | None,
        plan_heads: dict[str, dict[str, str]],
        event: str,
    ) -> dict[str, Any]:
        semantic = {
            "schema_version": 1,
            "contract_revision": self.continuation_contract_revision,
            "index_revision": PAPER_CONTINUATION_STATUS_INDEX_REVISION,
            "project_id": self.project_id,
            "generation": (base_head["generation"] + 1 if base_head else 1),
            "plan_heads": {
                plan_id: dict(plan_heads[plan_id]) for plan_id in sorted(plan_heads)
            },
            "dependency_fingerprints": self._dependency_fingerprints(),
            "last_event": event,
            "updated_at": _utc_now(),
            "truth_effect": "none",
        }
        head = {**semantic, "head_sha256": sha256_json(semantic)}
        self.initialize()
        self.store._write_json_atomic(self.head_path, head)
        return self._validate_head(head, require_current=True)

    def _validate_state(self, value: Any, *, digest: str) -> dict[str, Any]:
        fields = {
            "schema_version",
            "contract_revision",
            "index_revision",
            "project_id",
            "plan_id",
            "plan_record_sha256",
            "paper_id",
            "snapshot_id",
            "domain_profile",
            "selection_mode",
            "target_node_ids",
            "materialization_record_sha256",
            "target_research_count",
            "researched_target_node_ids",
            "current_dispositions",
            "source_snapshot_current",
            "truth_effect",
            "state_sha256",
        }
        state = _exact(value, fields, "Paper continuation status state")
        self.continuation.validate_plan_id(state["plan_id"])
        if (
            state["schema_version"] != 1
            or state["contract_revision"] != self.continuation_contract_revision
            or state["index_revision"]
            != PAPER_CONTINUATION_STATUS_INDEX_REVISION
            or state["project_id"] != self.project_id
            or not isinstance(state["paper_id"], str)
            or not state["paper_id"]
            or not isinstance(state["snapshot_id"], str)
            or not state["snapshot_id"]
            or not isinstance(state["domain_profile"], str)
            or not state["domain_profile"]
            or not isinstance(state["selection_mode"], str)
            or not state["selection_mode"]
            or not isinstance(state["source_snapshot_current"], bool)
            or state["truth_effect"] != "none"
        ):
            raise ValueError("Paper continuation status state binding is invalid")
        if (
            not isinstance(state["plan_record_sha256"], str)
            or SHA256_RE.fullmatch(state["plan_record_sha256"]) is None
            or (
                state["materialization_record_sha256"] is not None
                and (
                    not isinstance(state["materialization_record_sha256"], str)
                    or SHA256_RE.fullmatch(
                        state["materialization_record_sha256"]
                    )
                    is None
                )
            )
            or not isinstance(state["target_research_count"], int)
            or state["target_research_count"] < 0
        ):
            raise ValueError("Paper continuation status state hashes are invalid")
        targets = _strings(state["target_node_ids"], "Paper status targets")
        researched = _strings(
            state["researched_target_node_ids"], "Paper status researched targets"
        )
        if targets != sorted(targets) or researched != sorted(researched):
            raise ValueError("Paper continuation status target order is invalid")
        target_set = set(targets)
        if not set(researched).issubset(target_set):
            raise ValueError("Paper status researched targets escape the plan")
        dispositions = state["current_dispositions"]
        if not isinstance(dispositions, list):
            raise ValueError("Paper status dispositions must be a list")
        seen_targets: set[str] = set()
        for item in dispositions:
            _exact(
                item,
                {
                    "target_node_id",
                    "disposition_id",
                    "record_sha256",
                    "successor_mapped",
                    "writing_covered",
                },
                "Paper status disposition",
            )
            target_id = item["target_node_id"]
            if (
                target_id not in target_set
                or target_id in seen_targets
                or not isinstance(item["disposition_id"], str)
                or not item["disposition_id"]
                or not isinstance(item["record_sha256"], str)
                or SHA256_RE.fullmatch(item["record_sha256"]) is None
                or not isinstance(item["successor_mapped"], bool)
                or not isinstance(item["writing_covered"], bool)
            ):
                raise ValueError("Paper continuation status disposition is invalid")
            seen_targets.add(target_id)
        if [item["target_node_id"] for item in dispositions] != sorted(seen_targets):
            raise ValueError("Paper status dispositions are not target-sorted")
        without_hash = {key: item for key, item in state.items() if key != "state_sha256"}
        expected = sha256_json(without_hash)
        if state["state_sha256"] != expected or digest != expected:
            raise ValueError("Paper continuation status state hash mismatch")
        return state

    def _validate_receipt(self, value: Any, *, digest: str) -> dict[str, Any]:
        fields = {
            "schema_version",
            "contract_revision",
            "index_revision",
            "project_id",
            "state_sha256",
            "plan_id",
            "paper_id",
            "snapshot_id",
            "domain_profile",
            "selection_mode",
            "state",
            "source_snapshot_current",
            "adequacy_complete",
            "counts",
            "adequacy_receipt_sha256",
            "truth_effect",
            "status_receipt_sha256",
        }
        receipt = _exact(value, fields, "Paper continuation status receipt")
        self.continuation.validate_plan_id(receipt["plan_id"])
        if (
            receipt["schema_version"] != 1
            or receipt["contract_revision"] != self.continuation_contract_revision
            or receipt["index_revision"]
            != PAPER_CONTINUATION_STATUS_INDEX_REVISION
            or receipt["project_id"] != self.project_id
            or not isinstance(receipt["state_sha256"], str)
            or SHA256_RE.fullmatch(receipt["state_sha256"]) is None
            or receipt["state"]
            not in {
                "complete",
                "research_and_disposition_pending",
                "frontier_materialization_incomplete",
            }
            or not isinstance(receipt["source_snapshot_current"], bool)
            or not isinstance(receipt["adequacy_complete"], bool)
            or not isinstance(receipt["adequacy_receipt_sha256"], str)
            or SHA256_RE.fullmatch(receipt["adequacy_receipt_sha256"]) is None
            or receipt["truth_effect"] != "none"
        ):
            raise ValueError("Paper continuation status receipt binding is invalid")
        counts = receipt["counts"]
        if (
            not isinstance(counts, dict)
            or set(counts) != _COUNT_FIELDS
            or any(not isinstance(item, int) or item < 0 for item in counts.values())
        ):
            raise ValueError("Paper continuation status receipt counts are invalid")
        without_hash = {
            key: item for key, item in receipt.items() if key != "status_receipt_sha256"
        }
        expected = sha256_json(without_hash)
        if receipt["status_receipt_sha256"] != expected or digest != expected:
            raise ValueError("Paper continuation status receipt hash mismatch")
        return receipt

    def _state_path(self, digest: str) -> Path:
        if SHA256_RE.fullmatch(digest) is None:
            raise ValueError("invalid Paper continuation status state digest")
        return self.states_dir / f"{digest}.json"

    def _receipt_path(self, digest: str) -> Path:
        if SHA256_RE.fullmatch(digest) is None:
            raise ValueError("invalid Paper continuation status receipt digest")
        return self.receipts_dir / f"{digest}.json"

    def _load_state(self, digest: str) -> dict[str, Any]:
        path = self._state_path(digest)
        if path.is_symlink() or not path.is_file():
            raise ValueError("Paper continuation status state is missing or unsafe")
        return self._validate_state(self.store._read_json(path), digest=digest)

    def _load_receipt(self, digest: str) -> dict[str, Any]:
        path = self._receipt_path(digest)
        if path.is_symlink() or not path.is_file():
            raise ValueError("Paper continuation status receipt is missing or unsafe")
        return self._validate_receipt(self.store._read_json(path), digest=digest)

    def _receipt_for_state(self, state: dict[str, Any]) -> dict[str, Any]:
        targets = set(state["target_node_ids"])
        dispositioned = {
            item["target_node_id"] for item in state["current_dispositions"]
        }
        successor_mapped = {
            item["target_node_id"]
            for item in state["current_dispositions"]
            if item["successor_mapped"]
        }
        writing_covered = {
            item["target_node_id"]
            for item in state["current_dispositions"]
            if item["writing_covered"]
        }
        total = len(targets)
        counts = {
            "total": total,
            "frontier_materialized": state["target_research_count"],
            "researched": len(state["researched_target_node_ids"]),
            "dispositioned": len(dispositioned),
            "unresolved": len(targets.difference(dispositioned)),
            "successor_mapped": len(successor_mapped),
            "revised_manuscript_covered": len(writing_covered),
        }
        complete = bool(
            state["materialization_record_sha256"] is not None
            and state["source_snapshot_current"]
            and state["target_research_count"] == total
            and counts["unresolved"] == 0
            and counts["successor_mapped"] == total
            and counts["revised_manuscript_covered"] == total
        )
        adequacy_semantic = {
            "contract_revision": self.continuation_contract_revision,
            "plan_id": state["plan_id"],
            "plan_record_sha256": state["plan_record_sha256"],
            "materialization_record_sha256": state[
                "materialization_record_sha256"
            ],
            "current_dispositions": [
                {
                    "target_node_id": item["target_node_id"],
                    "disposition_id": item["disposition_id"],
                    "record_sha256": item["record_sha256"],
                }
                for item in state["current_dispositions"]
            ],
            "counts": counts,
            "source_snapshot_current": state["source_snapshot_current"],
            "adequacy_complete": complete,
        }
        semantic = {
            "schema_version": 1,
            "contract_revision": self.continuation_contract_revision,
            "index_revision": PAPER_CONTINUATION_STATUS_INDEX_REVISION,
            "project_id": self.project_id,
            "state_sha256": state["state_sha256"],
            "plan_id": state["plan_id"],
            "paper_id": state["paper_id"],
            "snapshot_id": state["snapshot_id"],
            "domain_profile": state["domain_profile"],
            "selection_mode": state["selection_mode"],
            "state": (
                "complete"
                if complete
                else (
                    "research_and_disposition_pending"
                    if state["materialization_record_sha256"] is not None
                    else "frontier_materialization_incomplete"
                )
            ),
            "source_snapshot_current": state["source_snapshot_current"],
            "adequacy_complete": complete,
            "counts": counts,
            "adequacy_receipt_sha256": sha256_json(adequacy_semantic),
            "truth_effect": "none",
        }
        return {**semantic, "status_receipt_sha256": sha256_json(semantic)}

    def _store_state(self, semantic: dict[str, Any]) -> dict[str, str]:
        state = {**semantic, "state_sha256": sha256_json(semantic)}
        state = self._validate_state(state, digest=state["state_sha256"])
        receipt = self._receipt_for_state(state)
        receipt = self._validate_receipt(
            receipt, digest=receipt["status_receipt_sha256"]
        )
        self.initialize()
        self.store._write_json_once(
            self._state_path(state["state_sha256"]), state
        )
        self.store._write_json_once(
            self._receipt_path(receipt["status_receipt_sha256"]), receipt
        )
        return {
            "state_sha256": state["state_sha256"],
            "status_receipt_sha256": receipt["status_receipt_sha256"],
        }

    def _state_semantic_from_plan(
        self,
        plan: dict[str, Any],
        *,
        materialization: dict[str, Any] | None,
        researched_target_node_ids: list[str],
        current_dispositions: list[dict[str, Any]],
        source_snapshot_current: bool,
    ) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "contract_revision": self.continuation_contract_revision,
            "index_revision": PAPER_CONTINUATION_STATUS_INDEX_REVISION,
            "project_id": self.project_id,
            "plan_id": plan["plan_id"],
            "plan_record_sha256": plan["record_sha256"],
            "paper_id": plan["paper_id"],
            "snapshot_id": plan["snapshot_id"],
            "domain_profile": plan["domain_profile"],
            "selection_mode": plan["selection_mode"],
            "target_node_ids": sorted(plan["target_node_ids"]),
            "materialization_record_sha256": (
                materialization["record_sha256"]
                if materialization is not None
                else None
            ),
            "target_research_count": (
                len(materialization["target_research_bindings"])
                if materialization is not None
                else 0
            ),
            "researched_target_node_ids": sorted(researched_target_node_ids),
            "current_dispositions": sorted(
                current_dispositions, key=lambda item: item["target_node_id"]
            ),
            "source_snapshot_current": source_snapshot_current,
            "truth_effect": "none",
        }

    @staticmethod
    def _disposition_projection(record: dict[str, Any]) -> dict[str, Any]:
        return {
            "target_node_id": record["target_node_id"],
            "disposition_id": record["disposition_id"],
            "record_sha256": record["record_sha256"],
            "successor_mapped": (
                record["outcome"] != "replaced"
                or bool(record["successor_research_ids"])
            ),
            "writing_covered": record["writing_coverage"]["status"]
            in {"covered", "not_applicable"},
        }

    def index_plan_record(
        self,
        plan: dict[str, Any],
        *,
        source_snapshot_current: bool,
    ) -> dict[str, Any]:
        base = self._load_head(require_current=False, allow_missing=True)
        plan_heads = dict(base["plan_heads"]) if base else {}
        existing = plan_heads.get(plan["plan_id"])
        if existing is not None:
            state = self._load_state(existing["state_sha256"])
            if state["plan_record_sha256"] != plan["record_sha256"]:
                raise ValueError("Paper continuation status plan binding drifted")
        else:
            semantic = self._state_semantic_from_plan(
                plan,
                materialization=None,
                researched_target_node_ids=[],
                current_dispositions=[],
                source_snapshot_current=source_snapshot_current,
            )
            plan_heads[plan["plan_id"]] = self._store_state(semantic)
        return self._write_head(
            base_head=base,
            plan_heads=plan_heads,
            event="plan_record_indexed",
        )

    def index_materialization(
        self,
        plan: dict[str, Any],
        materialization: dict[str, Any],
    ) -> dict[str, Any]:
        base = self._load_head(require_current=False)
        plan_heads = dict(base["plan_heads"])
        entry = plan_heads.get(plan["plan_id"])
        if entry is None:
            raise ValueError("Paper status plan head is absent during materialization")
        state = self._load_state(entry["state_sha256"])
        semantic = {
            key: item for key, item in state.items() if key != "state_sha256"
        }
        semantic["materialization_record_sha256"] = materialization[
            "record_sha256"
        ]
        semantic["target_research_count"] = len(
            materialization["target_research_bindings"]
        )
        plan_heads[plan["plan_id"]] = self._store_state(semantic)
        return self._write_head(
            base_head=base,
            plan_heads=plan_heads,
            event="materialization_indexed",
        )

    def _lineage_path(self, research_id: str) -> Path:
        return self.lineage_dir / f"{validate_memory_id(research_id)}.json"

    def _validate_lineage(self, value: Any, *, path: Path) -> dict[str, Any]:
        fields = {
            "schema_version",
            "contract_revision",
            "index_revision",
            "project_id",
            "research_id",
            "research_record_sha256",
            "paper_targets",
            "worker_outcome",
            "truth_effect",
            "lineage_sha256",
        }
        record = _exact(value, fields, "Paper continuation research lineage")
        research_id = validate_memory_id(record["research_id"])
        if (
            path.stem != research_id
            or record["schema_version"] != 1
            or record["contract_revision"] != self.continuation_contract_revision
            or record["index_revision"]
            != PAPER_CONTINUATION_STATUS_INDEX_REVISION
            or record["project_id"] != self.project_id
            or not isinstance(record["research_record_sha256"], str)
            or SHA256_RE.fullmatch(record["research_record_sha256"]) is None
            or not isinstance(record["worker_outcome"], bool)
            or record["truth_effect"] != "none"
        ):
            raise ValueError("Paper continuation research lineage binding is invalid")
        targets = record["paper_targets"]
        if not isinstance(targets, list):
            raise ValueError("Paper continuation research lineage targets must be a list")
        normalized: list[tuple[str, str]] = []
        for item in targets:
            _exact(
                item,
                {"plan_id", "target_node_id"},
                "Paper continuation research lineage target",
            )
            plan_id = self.continuation.validate_plan_id(item["plan_id"])
            target_id = item["target_node_id"]
            if not isinstance(target_id, str) or not target_id:
                raise ValueError("Paper continuation lineage target id is invalid")
            normalized.append((plan_id, target_id))
        if normalized != sorted(set(normalized)):
            raise ValueError("Paper continuation lineage targets are not unique/sorted")
        without_hash = {
            key: item for key, item in record.items() if key != "lineage_sha256"
        }
        if record["lineage_sha256"] != sha256_json(without_hash):
            raise ValueError("Paper continuation research lineage hash mismatch")
        return record

    def _load_lineage(self, research_id: str) -> dict[str, Any]:
        path = self._lineage_path(research_id)
        if path.is_symlink() or not path.is_file():
            raise KeyError(research_id)
        return self._validate_lineage(self.store._read_json(path), path=path)

    def _lineage_record(
        self,
        research: dict[str, Any],
        paper_targets: set[tuple[str, str]],
    ) -> dict[str, Any]:
        semantic = {
            "schema_version": 1,
            "contract_revision": self.continuation_contract_revision,
            "index_revision": PAPER_CONTINUATION_STATUS_INDEX_REVISION,
            "project_id": self.project_id,
            "research_id": research["research_id"],
            "research_record_sha256": research["record_sha256"],
            "paper_targets": [
                {"plan_id": plan_id, "target_node_id": target_id}
                for plan_id, target_id in sorted(paper_targets)
            ],
            "worker_outcome": research["metadata"].get("worker_outcome")
            in self.worker_outcomes,
            "truth_effect": "none",
        }
        return {**semantic, "lineage_sha256": sha256_json(semantic)}

    def _write_lineage(self, record: dict[str, Any]) -> None:
        self.initialize()
        path = self._lineage_path(record["research_id"])
        if path.exists():
            existing = self._validate_lineage(self.store._read_json(path), path=path)
            if existing != record:
                raise ValueError("Paper continuation research lineage collision")
            return
        self.store._write_json_once(path, record)

    def _prepare_research_against_base(
        self,
        research: dict[str, Any],
        *,
        base: dict[str, Any] | None,
    ) -> dict[str, Any]:
        targets: set[tuple[str, str]] = set()
        binding = research["metadata"].get("paper_continuation")
        if binding is not None:
            if not isinstance(binding, dict):
                raise ValueError("Paper continuation Research binding must be an object")
            plan_id = self.continuation.validate_plan_id(binding.get("plan_id"))
            target_id = binding.get("target_node_id")
            if not isinstance(target_id, str) or not target_id:
                raise ValueError("Paper continuation Research target id is invalid")
            targets.add((plan_id, target_id))
        for related_id in research.get("related_research_ids", []):
            try:
                related = self._load_lineage(related_id)
            except KeyError:
                if base is not None:
                    raise ValueError(
                        "Paper continuation status index lacks Research ancestry; "
                        "run paper-continuation-status-index-rebuild explicitly"
                    ) from None
                continue
            targets.update(
                (item["plan_id"], item["target_node_id"])
                for item in related["paper_targets"]
            )
        lineage = self._lineage_record(research, targets)
        state_updates: dict[str, dict[str, Any]] = {}
        if base is not None and lineage["worker_outcome"]:
            for plan_id, target_id in sorted(targets):
                entry = base["plan_heads"].get(plan_id)
                if entry is None:
                    continue
                state = state_updates.get(plan_id)
                if state is None:
                    loaded = self._load_state(entry["state_sha256"])
                    state = {
                        key: item
                        for key, item in loaded.items()
                        if key != "state_sha256"
                    }
                if target_id not in state["target_node_ids"]:
                    raise ValueError("Paper Research lineage escapes the selected plan")
                researched = set(state["researched_target_node_ids"])
                researched.add(target_id)
                state["researched_target_node_ids"] = sorted(researched)
                state_updates[plan_id] = state
        return {
            "base_head": base,
            "lineage": lineage,
            "state_updates": state_updates,
        }

    def prepare_research(self, research: dict[str, Any]) -> dict[str, Any]:
        base = self._load_head(require_current=True, allow_missing=True)
        if base is None and self._plan_files_present():
            raise ValueError(
                "Paper continuation status index is missing for declared plans; "
                "run paper-continuation-status-index-rebuild explicitly"
            )
        return self._prepare_research_against_base(research, base=base)

    def _prepared_research_is_committed(
        self,
        prepared: dict[str, Any],
    ) -> bool:
        try:
            lineage = self._load_lineage(prepared["lineage"]["research_id"])
        except KeyError:
            return False
        if lineage != prepared["lineage"]:
            raise ValueError("Paper continuation research lineage collision")
        base = prepared["base_head"]
        if base is None:
            return True
        for plan_id, semantic in prepared["state_updates"].items():
            entry = base["plan_heads"].get(plan_id)
            if entry is None:
                return False
            loaded = self._load_state(entry["state_sha256"])
            current_semantic = {
                key: item for key, item in loaded.items() if key != "state_sha256"
            }
            if current_semantic != semantic:
                return False
        return True

    def reconcile_research(
        self,
        research: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Idempotently finish a Research/status-index transaction on retry.

        A normal Research write prepares the status update before publishing
        the immutable Research object.  If the process stops between that
        publication and ``commit_research``, the Research directory is the
        only permitted dependency to be ahead of the old HEAD.  The explicit
        retrying writer then reuses the existing full rebuild mechanism so a
        crash after either the Research object *or* its lineage receipt cannot
        cause a partial incremental recovery.  Readers never invoke this path.
        """

        base = self._load_head(require_current=False, allow_missing=True)
        if base is None:
            if self._plan_files_present():
                raise ValueError(
                    "Paper continuation status index is missing for declared plans; "
                    "run paper-continuation-status-index-rebuild explicitly"
                )
            prepared = self._prepare_research_against_base(research, base=None)
            if self._prepared_research_is_committed(prepared):
                return None
            return self.commit_research(prepared)

        current_fingerprints = self._dependency_fingerprints()
        head_current = base["dependency_fingerprints"] == current_fingerprints
        if not head_current:
            drifted = {
                name
                for name in _DEPENDENCY_NAMES
                if base["dependency_fingerprints"][name]
                != current_fingerprints[name]
            }
            if drifted != {"research_entries"}:
                raise ValueError(
                    "Paper continuation status index is stale beyond the exact "
                    "retried Research write; run "
                    "paper-continuation-status-index-rebuild explicitly"
                )
            # Recovery is exceptional rather than a routine read path.  A full
            # canonical replay is preferable here to guessing which side of
            # the lineage/HEAD boundary the interrupted process reached.
            self.rebuild()
            base = self._load_head(require_current=True)
            prepared = self._prepare_research_against_base(
                research,
                base=base,
            )
            if not self._prepared_research_is_committed(prepared):
                raise ValueError(
                    "Paper continuation status rebuild did not reconcile the "
                    "retried Research record"
                )
            return base
        prepared = self._prepare_research_against_base(research, base=base)
        if self._prepared_research_is_committed(prepared):
            return base
        return self.commit_research(prepared)

    def commit_research(self, prepared: dict[str, Any]) -> dict[str, Any] | None:
        self._write_lineage(prepared["lineage"])
        base = prepared["base_head"]
        if base is None:
            return None
        plan_heads = dict(base["plan_heads"])
        for plan_id, semantic in prepared["state_updates"].items():
            plan_heads[plan_id] = self._store_state(semantic)
        return self._write_head(
            base_head=base,
            plan_heads=plan_heads,
            event="research_indexed",
        )

    def index_disposition(self, record: dict[str, Any]) -> dict[str, Any]:
        base = self._load_head(require_current=False)
        plan_id = record["plan_id"]
        entry = base["plan_heads"].get(plan_id)
        if entry is None:
            raise ValueError("Paper status plan head is absent during disposition")
        loaded = self._load_state(entry["state_sha256"])
        semantic = {
            key: item for key, item in loaded.items() if key != "state_sha256"
        }
        current = {
            item["target_node_id"]: item for item in semantic["current_dispositions"]
        }
        target_id = record["target_node_id"]
        existing = current.get(target_id)
        expected_previous = existing["disposition_id"] if existing else ""
        if record["supersedes_disposition_id"] != expected_previous:
            raise ValueError("Paper status disposition supersession is stale")
        current[target_id] = self._disposition_projection(record)
        semantic["current_dispositions"] = [
            current[item] for item in sorted(current)
        ]
        researched = set(semantic["researched_target_node_ids"])
        researched.add(target_id)
        semantic["researched_target_node_ids"] = sorted(researched)
        plan_heads = dict(base["plan_heads"])
        plan_heads[plan_id] = self._store_state(semantic)
        return self._write_head(
            base_head=base,
            plan_heads=plan_heads,
            event="disposition_indexed",
        )

    def index_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any] | None:
        base = self._load_head(require_current=False, allow_missing=True)
        if base is None:
            return None
        superseded = snapshot.get("supersedes_snapshot_id", "")
        plan_heads = dict(base["plan_heads"])
        if superseded:
            for plan_id, entry in sorted(base["plan_heads"].items()):
                loaded = self._load_state(entry["state_sha256"])
                if loaded["snapshot_id"] != superseded:
                    continue
                semantic = {
                    key: item
                    for key, item in loaded.items()
                    if key != "state_sha256"
                }
                semantic["source_snapshot_current"] = False
                plan_heads[plan_id] = self._store_state(semantic)
        return self._write_head(
            base_head=base,
            plan_heads=plan_heads,
            event="paper_snapshot_indexed",
        )

    def _summary_from_receipt(self, receipt: dict[str, Any]) -> dict[str, Any]:
        return {
            key: receipt[key]
            for key in (
                "schema_version",
                "contract_revision",
                "plan_id",
                "paper_id",
                "snapshot_id",
                "domain_profile",
                "selection_mode",
                "state",
                "source_snapshot_current",
                "adequacy_complete",
                "counts",
                "adequacy_receipt_sha256",
                "truth_effect",
            )
        } | {
            "detail": {
                "included": False,
                "omitted_fields": list(self.status_detail_fields),
                "request": [
                    "paper-continuation-status",
                    receipt["plan_id"],
                    "--full",
                ],
            }
        }

    def summary(
        self,
        plan_id: str,
        *,
        head: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        plan_id = self.continuation.validate_plan_id(plan_id)
        active = head or self._load_head(require_current=True)
        if active is None or plan_id not in active["plan_heads"]:
            raise KeyError(f"unknown Paper continuation plan: {plan_id}")
        entry = active["plan_heads"][plan_id]
        receipt = self._load_receipt(entry["status_receipt_sha256"])
        if receipt["state_sha256"] != entry["state_sha256"]:
            raise ValueError("Paper continuation status head/receipt mismatch")
        return self._summary_from_receipt(receipt)

    def all_summary(self) -> dict[str, Any]:
        head = self._load_head(require_current=True, allow_missing=True)
        if head is None:
            if self._plan_files_present():
                raise ValueError(
                    "Paper continuation status index is missing for declared plans; "
                    "run paper-continuation-status-index-rebuild explicitly"
                )
            statuses: list[dict[str, Any]] = []
        else:
            statuses = [
                self.summary(plan_id, head=head)
                for plan_id in sorted(head["plan_heads"])
            ]
        counts = {
            "plans": len(statuses),
            "complete_plans": sum(item["adequacy_complete"] for item in statuses),
            "targets": sum(item["counts"]["total"] for item in statuses),
            "frontier_materialized": sum(
                item["counts"]["frontier_materialized"] for item in statuses
            ),
            "researched": sum(item["counts"]["researched"] for item in statuses),
            "dispositioned": sum(
                item["counts"]["dispositioned"] for item in statuses
            ),
            "unresolved": sum(item["counts"]["unresolved"] for item in statuses),
            "successor_mapped": sum(
                item["counts"]["successor_mapped"] for item in statuses
            ),
            "revised_manuscript_covered": sum(
                item["counts"]["revised_manuscript_covered"]
                for item in statuses
            ),
        }
        return {
            "schema_version": 1,
            "contract_revision": self.continuation_contract_revision,
            "declaration_state": "declared" if statuses else "not_declared",
            "adequacy_complete": (
                all(item["adequacy_complete"] for item in statuses)
                if statuses
                else None
            ),
            "counts": counts,
            "plans": statuses,
            "detail": {
                "included": False,
                "omitted_fields": list(self.status_detail_fields),
                "request": ["paper-continuation-status", "--full"],
            },
            "truth_effect": "none",
        }

    def rebuild(self) -> dict[str, Any]:
        """Perform one explicit graph-scale validation and rebuild the index."""

        self.initialize()
        plans = self.continuation.plans()
        full_statuses = {
            plan["plan_id"]: self.continuation.status(plan["plan_id"])
            for plan in plans
        }
        research_records = self.lifecycle.research_records()
        research_by_id = {
            record["research_id"]: record for record in research_records
        }
        materializations: dict[str, dict[str, Any] | None] = {}
        direct_targets: dict[str, set[tuple[str, str]]] = {
            research_id: set() for research_id in research_by_id
        }
        for plan in plans:
            path = self.continuation._materialization_path(plan["plan_id"])
            materialization = (
                self.store._read_json(path)
                if path.exists() and path.is_file() and not path.is_symlink()
                else None
            )
            materializations[plan["plan_id"]] = materialization
            if materialization is None:
                continue
            for binding in materialization["target_research_bindings"]:
                research_id = binding["research_id"]
                if research_id not in direct_targets:
                    raise ValueError(
                        "Paper status rebuild found a missing target Research record"
                    )
                direct_targets[research_id].add(
                    (plan["plan_id"], binding["target_node_id"])
                )
        lineage_targets = {
            research_id: set(items)
            for research_id, items in direct_targets.items()
        }
        for record in research_records:
            missing = set(record.get("related_research_ids", [])).difference(
                research_by_id
            )
            if missing:
                raise ValueError(
                    "Paper status rebuild found incomplete Research ancestry"
                )
        changed = True
        while changed:
            changed = False
            for record in research_records:
                targets = lineage_targets[record["research_id"]]
                before = len(targets)
                for related_id in record.get("related_research_ids", []):
                    targets.update(lineage_targets[related_id])
                if len(targets) != before:
                    changed = True
        for record in research_records:
            self._write_lineage(
                self._lineage_record(
                    record, lineage_targets[record["research_id"]]
                )
            )
        researched_by_plan: dict[str, set[str]] = {
            plan["plan_id"]: set() for plan in plans
        }
        for record in research_records:
            if record["metadata"].get("worker_outcome") not in self.worker_outcomes:
                continue
            for plan_id, target_id in lineage_targets[record["research_id"]]:
                if plan_id in researched_by_plan:
                    researched_by_plan[plan_id].add(target_id)
        plan_heads: dict[str, dict[str, str]] = {}
        for plan in plans:
            full = full_statuses[plan["plan_id"]]
            current_dispositions: list[dict[str, Any]] = []
            for disposition_id in full["current_disposition_ids"]:
                path = self.continuation._disposition_path(disposition_id)
                if path.is_symlink() or not path.is_file():
                    raise ValueError(
                        "Paper status rebuild lost a current disposition record"
                    )
                current_dispositions.append(
                    self._disposition_projection(self.store._read_json(path))
                )
            semantic = self._state_semantic_from_plan(
                plan,
                materialization=materializations[plan["plan_id"]],
                researched_target_node_ids=sorted(
                    researched_by_plan[plan["plan_id"]]
                ),
                current_dispositions=current_dispositions,
                source_snapshot_current=full["source_snapshot_current"],
            )
            plan_head = self._store_state(semantic)
            indexed = self._load_receipt(plan_head["status_receipt_sha256"])
            if (
                indexed["counts"] != full["counts"]
                or indexed["adequacy_complete"] != full["adequacy_complete"]
                or indexed["adequacy_receipt_sha256"]
                != full["adequacy_receipt_sha256"]
            ):
                raise ValueError(
                    "Paper continuation status rebuild disagrees with full validation"
                )
            plan_heads[plan["plan_id"]] = plan_head
        base = self._load_head(require_current=False, allow_missing=True)
        head = self._write_head(
            base_head=base,
            plan_heads=plan_heads,
            event="explicit_full_index_rebuild",
        )
        return {
            "schema_version": 1,
            "contract_revision": self.continuation_contract_revision,
            "index_revision": PAPER_CONTINUATION_STATUS_INDEX_REVISION,
            "status": "rebuilt_after_full_validation",
            "generation": head["generation"],
            "head_sha256": head["head_sha256"],
            "plans": len(plan_heads),
            "research_lineage_records": len(research_records),
            "summary": self.all_summary(),
            "truth_effect": "none",
        }

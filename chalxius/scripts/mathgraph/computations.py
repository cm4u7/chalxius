from __future__ import annotations

import json
import hashlib
import math
import os
from contextlib import nullcontext
from functools import wraps
from pathlib import Path, PurePosixPath
from typing import Any, Callable, ContextManager

from .adoption import (
    feature_required,
    feature_status,
    uses_legacy_estimate_policy,
)
from .contracts import (
    CAMPAIGN_ID_RE,
    MEMORY_ID_RE,
    POLICY_REVISION_V4,
    SHA256_RE,
    canonical_json_bytes,
    contained_path,
    require_exact_keys,
    require_relative_path,
    require_string,
    sha256_bytes,
    sha256_json,
    validate_experiment_id,
)
from .event_ledger import ExperimentEventLedger
from .modes import require_unaborted_work_unit
from .protocol import validate_task_card


INDEPENDENCE_AXES = {
    "input_transcription",
    "algorithm_derivation",
    "implementation",
    "runtime",
    "truncation_method",
    "orientation_generation",
    "functional_evaluation",
    "final_arithmetic",
}
INDEPENDENCE_VALUES = {
    "not_applicable",
    "shared",
    "same_runtime",
    "cross_checked",
    "independent_reimplementation",
    "formally_derived",
}
COMPUTATION_ROLES = {"load_bearing", "corroborative"}
V5_LOAD_BEARING_TRUNCATION_KINDS = {
    "finite_exhaustive",
    "symbolic_exact",
    "series_product_coefficient",
}
V5_SERIES_REPLAY_CHECKS = {
    "inspect_algorithm",
    "execute",
    "verify_order_budget",
    "extend_truncation_depth",
}
V5_STRONG_TRUNCATION_METHODS = {
    "cross_checked",
    "independent_reimplementation",
    "formally_derived",
}
EXPERIMENT_EVENTS = {
    "started",
    "stage_started",
    "stage_completed",
    "checkpoint",
    "heartbeat",
    "failed",
    "resumed",
    "finalized",
}
CONTINUATION_THRESHOLD_SECONDS = 20 * 60
CONTINUATION_THRESHOLD_NS = CONTINUATION_THRESHOLD_SECONDS * 1_000_000_000
GOVERNANCE_MEASUREMENT_METHOD = "host_monotonic_active_intervals_union"
GOVERNANCE_DECISIONS = {"continue", "stop"}
GOVERNANCE_ACTOR_ROLES = {"main", "operator"}
HEARTBEAT_FIELDS = {
    "event",
    "timestamp",
    "stage",
    "completed_units",
    "total_units_or_null",
    "cpu_seconds",
    "wall_seconds",
    "rss_bytes",
    "latest_check",
}


def _nonnegative_number(value: Any, *, label: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) < 0
    ):
        raise ValueError(f"{label} must be a nonnegative finite number")
    return float(value)


def _canonical_active_intervals(
    intervals: Any,
) -> tuple[list[dict[str, Any]], int]:
    """Return canonical source intervals and task-timeline union duration.

    ``start_ns`` and ``end_ns`` are positions on one host-maintained,
    task-relative monotonic timeline. ``clock_epoch`` records source-clock
    provenance; it is not a second duration bucket. Consequently parallel
    leases that report the same physical span under different source epochs
    are counted once.
    """

    if not isinstance(intervals, list) or any(
        not isinstance(item, dict) for item in intervals
    ):
        raise ValueError("active_intervals must be a list of objects")
    grouped: dict[str, list[tuple[int, int]]] = {}
    for index, item in enumerate(intervals, 1):
        require_exact_keys(
            item,
            required={"clock_epoch", "lease_id", "start_ns", "end_ns"},
            label=f"active_intervals[{index}]",
        )
        epoch = require_string(item, "clock_epoch")
        require_string(item, "lease_id")
        start = item.get("start_ns")
        end = item.get("end_ns")
        if (
            isinstance(start, bool)
            or not isinstance(start, int)
            or start < 0
            or isinstance(end, bool)
            or not isinstance(end, int)
            or end < start
        ):
            raise ValueError(
                f"active_intervals[{index}] must have integer 0 <= start_ns <= end_ns"
            )
        grouped.setdefault(epoch, []).append((start, end))

    canonical: list[dict[str, Any]] = []
    task_timeline_spans: list[tuple[int, int]] = []
    for epoch in sorted(grouped):
        merged: list[list[int]] = []
        for start, end in sorted(grouped[epoch]):
            if not merged or start > merged[-1][1]:
                merged.append([start, end])
            else:
                merged[-1][1] = max(merged[-1][1], end)
        for start, end in merged:
            canonical.append(
                {
                    "clock_epoch": epoch,
                    "start_ns": start,
                    "end_ns": end,
                }
            )
            task_timeline_spans.append((start, end))
    task_union: list[list[int]] = []
    for start, end in sorted(task_timeline_spans):
        if not task_union or start > task_union[-1][1]:
            task_union.append([start, end])
        else:
            task_union[-1][1] = max(task_union[-1][1], end)
    total = sum(end - start for start, end in task_union)
    return canonical, total


def _interval_union_extends(
    previous: list[dict[str, Any]],
    current: list[dict[str, Any]],
) -> bool:
    """Return whether every previously observed active interval remains covered."""

    by_epoch: dict[str, list[tuple[int, int]]] = {}
    for item in current:
        by_epoch.setdefault(str(item["clock_epoch"]), []).append(
            (int(item["start_ns"]), int(item["end_ns"]))
        )
    for old in previous:
        old_start = int(old["start_ns"])
        old_end = int(old["end_ns"])
        candidates = by_epoch.get(str(old["clock_epoch"]), [])
        if not any(start <= old_start and end >= old_end for start, end in candidates):
            return False
    return True


def _ledger_prefix(path: Path, count: int | None = None) -> dict[str, Any]:
    if not path.exists():
        lines: list[bytes] = []
    else:
        if not path.is_file() or path.is_symlink():
            raise ValueError("ledger path is missing or unsafe")
        lines = [line for line in path.read_bytes().splitlines(keepends=True) if line.strip()]
    if count is None:
        count = len(lines)
    if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= len(lines):
        raise ValueError("ledger prefix count is invalid")
    prefix = b"".join(lines[:count])
    return {
        "event_count": count,
        "sha256": sha256_bytes(prefix),
    }


def _serialized_experiment(method: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(method)
    def wrapped(self: "ExperimentManager", *args: Any, **kwargs: Any) -> Any:
        with self._mutation_lock():
            return method(self, *args, **kwargs)

    return wrapped


def _serialized_experiment_read(
    method: Callable[..., Any],
) -> Callable[..., Any]:
    """Serialize an in-process read without creating a filesystem lock."""

    @wraps(method)
    def wrapped(self: "ExperimentManager", *args: Any, **kwargs: Any) -> Any:
        with self._read_lock():
            return method(self, *args, **kwargs)

    return wrapped


def validate_independence_matrix(payload: Any) -> dict[str, str]:
    if not isinstance(payload, dict):
        raise ValueError("independence_matrix must be an object")
    if "confidence_score" in payload or "independent" in payload:
        raise ValueError(
            "independence_matrix cannot use a scalar confidence or independent flag"
        )
    require_exact_keys(
        payload,
        required=INDEPENDENCE_AXES,
        label="independence_matrix",
    )
    for axis, value in payload.items():
        if not isinstance(value, str) or value not in INDEPENDENCE_VALUES:
            raise ValueError(f"independence axis {axis} has an invalid value")
    return dict(payload)


def _require_string_list(payload: dict[str, Any], key: str) -> list[str]:
    value = payload.get(key)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{key} must be a list of strings")
    return list(value)


def _require_integer(value: Any, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    return value


def _validate_v5_series_product_certificate(
    certificate: dict[str, Any],
    *,
    artifact_roles: set[str],
    label: str,
) -> str:
    """Validate a valuation-derived order budget for one product coefficient.

    If ``[t^p] prod_i f_i`` is requested and ``v_i`` is the lowest power of
    ``f_i``, factor ``i`` must be retained through at least
    ``p - sum_{j != i} v_j``.  A ``None`` retained bound means that the factor
    is exact rather than truncated.  This catches the common error of
    truncating factors independently before multiplying them.
    """

    require_exact_keys(
        certificate,
        required={
            "kind",
            "statement",
            "checked_orders",
            "limitations",
            "target_power",
            "factors",
            "depth_extension",
        },
        label=f"{label}.truncation_certificate",
    )
    target_power = _require_integer(
        certificate.get("target_power"),
        label=f"{label}.truncation_certificate.target_power",
    )
    factors = certificate.get("factors")
    if (
        not isinstance(factors, list)
        or len(factors) < 2
        or any(not isinstance(item, dict) for item in factors)
    ):
        raise ValueError(
            f"{label}.truncation_certificate.factors must contain at least two objects"
        )
    normalized: dict[str, tuple[int, int | None]] = {}
    for index, factor in enumerate(factors, 1):
        factor_label = f"{label}.truncation_certificate.factors[{index}]"
        require_exact_keys(
            factor,
            required={"factor_id", "lowest_power", "retained_through"},
            label=factor_label,
        )
        factor_id = require_string(factor, "factor_id")
        if factor_id in normalized:
            raise ValueError(f"{label} has duplicate truncation factor ids")
        lowest_power = _require_integer(
            factor.get("lowest_power"), label=f"{factor_label}.lowest_power"
        )
        retained = factor.get("retained_through")
        if retained is not None:
            retained = _require_integer(
                retained, label=f"{factor_label}.retained_through"
            )
            if retained < lowest_power:
                raise ValueError(
                    f"{factor_label}.retained_through precedes its lowest power"
                )
        normalized[factor_id] = (lowest_power, retained)
    truncated = {
        factor_id: values
        for factor_id, values in normalized.items()
        if values[1] is not None
    }
    if not truncated:
        raise ValueError(
            f"{label} series_product_coefficient must identify a truncated factor"
        )

    valuation_sum = sum(lowest for lowest, _ in normalized.values())
    required_through: dict[str, int] = {}
    for factor_id, (lowest, retained) in truncated.items():
        required = target_power - (valuation_sum - lowest)
        required_through[factor_id] = required
        assert retained is not None
        if retained < required:
            raise ValueError(
                f"{label} truncates {factor_id} through t^{retained}, "
                f"but coefficient t^{target_power} requires it through t^{required}"
            )

    extension = certificate.get("depth_extension")
    if not isinstance(extension, dict):
        raise ValueError(
            f"{label}.truncation_certificate.depth_extension must be an object"
        )
    require_exact_keys(
        extension,
        required={"artifact_role", "factor_orders"},
        label=f"{label}.truncation_certificate.depth_extension",
    )
    extension_role = require_string(extension, "artifact_role")
    if extension_role not in artifact_roles:
        raise ValueError(f"{label} depth-extension artifact role is not declared")
    factor_orders = extension.get("factor_orders")
    if not isinstance(factor_orders, list) or any(
        not isinstance(item, dict) for item in factor_orders
    ):
        raise ValueError(f"{label} depth-extension factor_orders must be objects")
    extension_by_factor: dict[str, int] = {}
    for index, item in enumerate(factor_orders, 1):
        order_label = (
            f"{label}.truncation_certificate.depth_extension.factor_orders[{index}]"
        )
        require_exact_keys(
            item,
            required={"factor_id", "retained_through"},
            label=order_label,
        )
        factor_id = require_string(item, "factor_id")
        if factor_id in extension_by_factor:
            raise ValueError(f"{label} has duplicate depth-extension factor ids")
        extension_by_factor[factor_id] = _require_integer(
            item.get("retained_through"),
            label=f"{order_label}.retained_through",
        )
    if set(extension_by_factor) != set(truncated):
        raise ValueError(
            f"{label} depth extension must exactly cover every truncated factor"
        )
    for factor_id, (_, retained) in truncated.items():
        assert retained is not None
        extension_order = extension_by_factor[factor_id]
        if extension_order <= retained:
            raise ValueError(
                f"{label} depth extension does not extend {factor_id} beyond t^{retained}"
            )
        if extension_order < required_through[factor_id]:
            raise ValueError(
                f"{label} depth extension for {factor_id} remains below the required order"
            )
    return extension_role


def validate_computational_evidence(
    entries: Any,
    *,
    proof: str,
    artifacts: list[dict[str, str]],
    verification_plan: dict[str, Any],
    workflow_evidence_version: int = 4,
) -> list[dict[str, Any]]:
    if not isinstance(entries, list) or any(not isinstance(item, dict) for item in entries):
        raise ValueError("computational_evidence must be a list of objects")
    artifact_by_path = {item["path"]: item["sha256"] for item in artifacts}
    artifact_hashes = {item["sha256"] for item in artifacts}
    keys: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, entry in enumerate(entries, 1):
        label = f"computational_evidence[{index}]"
        require_exact_keys(
            entry,
            required={
                "key",
                "role",
                "proof_anchor",
                "artifact_refs",
                "entrypoint_role",
                "command",
                "interpreter",
                "arithmetic",
                "algorithm_spec",
                "truncation_certificate",
                "expected_outputs",
                "replay_checks",
                "independence_matrix",
            },
            label=label,
        )
        key = require_string(entry, "key")
        if key in keys:
            raise ValueError(f"duplicate computation key: {key}")
        keys.add(key)
        role = require_string(entry, "role")
        if role not in COMPUTATION_ROLES:
            raise ValueError(f"{label}.role is invalid")
        anchor = require_string(entry, "proof_anchor")
        expected_anchor = f"[COMP:{key}]"
        if anchor != expected_anchor or proof.count(anchor) != 1:
            raise ValueError(
                f"computation proof anchor {expected_anchor} must occur exactly once"
            )
        refs = entry.get("artifact_refs")
        if not isinstance(refs, list) or not refs or any(
            not isinstance(item, dict) for item in refs
        ):
            raise ValueError(f"{label}.artifact_refs must be nonempty")
        roles: set[str] = set()
        for ref_index, ref in enumerate(refs, 1):
            require_exact_keys(
                ref,
                required={"role", "path", "sha256"},
                label=f"{label}.artifact_refs[{ref_index}]",
            )
            artifact_role = require_string(ref, "role")
            if artifact_role in roles:
                raise ValueError(f"{label} has duplicate artifact roles")
            roles.add(artifact_role)
            path = require_string(ref, "path")
            digest = require_string(ref, "sha256")
            require_relative_path(path, f"{label}.artifact path")
            if "/work/" in f"/{path}/" or "/checkpoints/" in f"/{path}/":
                raise ValueError("work/checkpoint paths cannot be computational evidence")
            if SHA256_RE.fullmatch(digest) is None:
                raise ValueError(f"{label} artifact hash is invalid")
            if artifact_by_path.get(path) != digest or digest not in artifact_hashes:
                raise ValueError(
                    f"{label} artifact is not bound to the validated assignment manifest"
                )
        entrypoint_role = require_string(entry, "entrypoint_role")
        if entrypoint_role not in roles:
            raise ValueError(f"{label}.entrypoint_role is not declared")
        command = entry.get("command")
        if not isinstance(command, list) or not command or any(
            not isinstance(item, str) or not item for item in command
        ):
            raise ValueError(f"{label}.command must be a nonempty argv list")
        for argument in command[1:]:
            if argument.startswith("/") or ".." in PurePosixPath(argument).parts:
                raise ValueError(f"{label}.command references a path outside the bundle")
        interpreter = entry.get("interpreter")
        if not isinstance(interpreter, dict):
            raise ValueError(f"{label}.interpreter must be an object")
        require_exact_keys(
            interpreter,
            required={"implementation", "version"},
            label=f"{label}.interpreter",
        )
        require_string(interpreter, "implementation")
        require_string(interpreter, "version")
        require_string(entry, "arithmetic")
        require_string(entry, "algorithm_spec")
        certificate = entry.get("truncation_certificate")
        if not isinstance(certificate, dict):
            raise ValueError(f"{label}.truncation_certificate must be an object")
        certificate_kind = require_string(certificate, "kind")
        extension_artifact_role: str | None = None
        if (
            workflow_evidence_version >= 5
            and certificate_kind == "series_product_coefficient"
        ):
            extension_artifact_role = _validate_v5_series_product_certificate(
                certificate,
                artifact_roles=roles,
                label=label,
            )
        else:
            require_exact_keys(
                certificate,
                required={"kind", "statement", "checked_orders", "limitations"},
                label=f"{label}.truncation_certificate",
            )
        require_string(certificate, "statement")
        checked_orders = certificate.get("checked_orders")
        if not isinstance(checked_orders, list) or any(
            isinstance(value, bool) or not isinstance(value, int)
            for value in checked_orders
        ):
            raise ValueError(f"{label}.checked_orders must be a list of integers")
        _require_string_list(certificate, "limitations")
        if role == "load_bearing" and certificate_kind == "two_depth_agreement":
            raise ValueError(
                "two-depth agreement alone is corroborative, not a truncation proof"
            )
        if (
            workflow_evidence_version >= 5
            and role == "load_bearing"
            and certificate_kind not in V5_LOAD_BEARING_TRUNCATION_KINDS
        ):
            raise ValueError(
                f"{label} load-bearing V5 computation must classify truncation as "
                "finite_exhaustive, symbolic_exact, or series_product_coefficient"
            )
        expected_outputs = entry.get("expected_outputs")
        if not isinstance(expected_outputs, list) or not expected_outputs or any(
            not isinstance(item, dict) for item in expected_outputs
        ):
            raise ValueError(f"{label}.expected_outputs must be nonempty")
        ref_by_role = {ref["role"]: ref for ref in refs}
        expected_output_roles: set[str] = set()
        for output_index, output in enumerate(expected_outputs, 1):
            require_exact_keys(
                output,
                required={"role", "sha256"},
                label=f"{label}.expected_outputs[{output_index}]",
            )
            output_role = require_string(output, "role")
            output_hash = require_string(output, "sha256")
            if output_role in expected_output_roles:
                raise ValueError(f"{label} has duplicate expected output roles")
            expected_output_roles.add(output_role)
            if (
                output_role not in ref_by_role
                or ref_by_role[output_role]["sha256"] != output_hash
            ):
                raise ValueError(f"{label} expected output is not artifact-bound")
        if (
            extension_artifact_role is not None
            and extension_artifact_role not in expected_output_roles
        ):
            raise ValueError(
                f"{label} depth-extension artifact must be an expected output"
            )
        replay_checks = _require_string_list(entry, "replay_checks")
        if role == "load_bearing" and not {
            "inspect_algorithm",
            "execute",
        }.issubset(replay_checks):
            raise ValueError(
                f"{label} load-bearing evidence lacks algorithm inspection/replay"
            )
        if (
            workflow_evidence_version >= 5
            and role == "load_bearing"
            and certificate_kind == "series_product_coefficient"
            and not V5_SERIES_REPLAY_CHECKS.issubset(replay_checks)
        ):
            raise ValueError(
                f"{label} series evidence lacks order-budget/depth-extension replay"
            )
        independence = validate_independence_matrix(entry["independence_matrix"])
        if (
            workflow_evidence_version >= 5
            and role == "load_bearing"
            and certificate_kind == "series_product_coefficient"
            and independence["truncation_method"]
            not in V5_STRONG_TRUNCATION_METHODS
        ):
            raise ValueError(
                f"{label} series truncation method lacks an independent or formal check"
            )
        if role == "load_bearing":
            required_mode = (
                "closed_capsule"
                if workflow_evidence_version >= 5
                else "artifact_replay"
            )
            if verification_plan.get("mode") != required_mode:
                raise ValueError(
                    "load-bearing computation requires "
                    f"{required_mode} verification"
                )
            authorized = set(
                verification_plan.get("authorized_artifact_roles", [])
            )
            if not roles.issubset(authorized):
                raise ValueError(
                    f"{label} uses an artifact role outside the verification capability"
                )
        normalized.append(dict(entry))
    return normalized


class ExperimentManager:
    def __init__(
        self,
        project_root: Path | str,
        *,
        mutation_lock: Callable[[], ContextManager[Any]] | None = None,
        read_lock: Callable[[], ContextManager[Any]] | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self._mutation_lock = mutation_lock or nullcontext
        self._read_lock = read_lock or nullcontext

    @staticmethod
    def _hard_caps(task_card: dict[str, Any]) -> dict[str, int] | None:
        caps = task_card.get("hard_caps")
        return caps if isinstance(caps, dict) else None

    @classmethod
    def _require_hard_caps(cls, task_card: dict[str, Any]) -> dict[str, int]:
        caps = cls._hard_caps(task_card)
        if caps is None:
            raise ValueError(
                "historical task card has no hard_caps and is read-only; replan"
            )
        return caps

    @classmethod
    def _governance_hard_caps(
        cls, task_card: dict[str, Any]
    ) -> dict[str, int] | None:
        caps = cls._hard_caps(task_card)
        if caps is None:
            return None
        return {
            "max_experiment_worker_event_count": caps[
                "max_governance_event_count"
            ],
            "max_experiment_event_count_total": caps[
                "max_governance_event_count"
            ],
            "max_experiment_event_bytes_each": caps[
                "max_governance_event_bytes_each"
            ],
            "max_experiment_event_bytes_total": caps[
                "max_governance_event_bytes_total"
            ],
        }

    @classmethod
    def _governance_ledger(
        cls, task_card: dict[str, Any], events_path: Path
    ) -> ExperimentEventLedger:
        return ExperimentEventLedger(
            events_path,
            hard_caps=cls._governance_hard_caps(task_card),
        )

    @staticmethod
    def _stream_sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @classmethod
    def _checkpoint_inventory(
        cls, directory: Path, caps: dict[str, int] | None
    ) -> dict[str, Any]:
        root = directory / "checkpoints"
        entries: list[dict[str, Any]] = []
        total = 0
        for path in sorted(root.rglob("*")):
            if path.is_dir() and not path.is_symlink():
                continue
            if path.is_symlink() or not path.is_file():
                raise ValueError("checkpoint tree contains an unsafe entry")
            size = path.stat().st_size
            if caps and size > caps["max_checkpoint_bytes_each"]:
                raise ValueError("checkpoint exceeds per-file hard cap")
            total += size
            entries.append({
                "path": path.relative_to(directory).as_posix(),
                "bytes": size,
                "sha256": cls._stream_sha256(path),
            })
        if caps:
            if len(entries) > caps["max_checkpoint_files"]:
                raise ValueError("checkpoint tree exceeds file-count hard cap")
            if total > caps["max_checkpoint_bytes_total"]:
                raise ValueError("checkpoint tree exceeds total-byte hard cap")
        return {
            "files": entries,
            "file_count": len(entries),
            "bytes_total": total,
            "sha256": sha256_json(entries),
        }

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
        result: list[dict[str, Any]] = []
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"non-object event at {path}:{number}")
            result.append(payload)
        return result

    @staticmethod
    def _write_once(path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            fd = os.open(path, flags, 0o600)
        except FileExistsError:
            if not path.is_file() or path.is_symlink() or path.read_bytes() != payload:
                raise ValueError(f"immutable experiment collision at {path}")
            return
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

    @classmethod
    def _write_json_once(cls, path: Path, payload: dict[str, Any]) -> None:
        cls._write_once(
            path,
            (
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n"
            ).encode("utf-8"),
        )

    def _validate_bound_task_card(
        self,
        task_card: dict[str, Any],
        *,
        allow_historical_estimate_policy: bool = False,
        require_active_work_unit: bool = False,
    ) -> dict[str, Any]:
        validate_task_card(task_card, allow_legacy_adoption=True)
        legacy_estimate_policy = uses_legacy_estimate_policy(
            task_card["adoption_plan"]
        )
        round_path = (
            self.project_root
            / "rounds"
            / task_card["round_id"]
            / "round.json"
        )
        if not round_path.is_file() or round_path.is_symlink():
            raise ValueError(
                "experiment task card has no frozen round manifest"
            )
        round_manifest = self._read_json(round_path)
        if (
            round_manifest.get("schema_version") != 4
            or round_manifest.get("project_id") != task_card["project_id"]
            or round_manifest.get("round_id") != task_card["round_id"]
        ):
            raise ValueError(
                "experiment task card round binding mismatch"
            )
        matches = [
            assignment
            for assignment in round_manifest.get("assignments", [])
            if isinstance(assignment, dict)
            and assignment.get("assignment_id")
            == task_card["assignment_id"]
        ]
        if len(matches) != 1:
            raise ValueError(
                "experiment task card assignment is not uniquely bound"
            )
        assignment = matches[0]
        card_path = contained_path(
            self.project_root,
            require_string(assignment, "task_card_relpath"),
            "experiment task card path",
        )
        if not card_path.is_file() or card_path.is_symlink():
            raise ValueError(
                "experiment task card file is missing or unsafe"
            )
        if (
            self._read_json(card_path) != task_card
            or require_string(assignment, "task_card_sha256")
            != sha256_bytes(card_path.read_bytes())
            or assignment.get("assignment_sha256")
            != task_card["assignment_sha256"]
        ):
            raise ValueError(
                "experiment task card differs from the frozen round card"
            )
        contract = assignment.get("contract")
        if (
            not isinstance(contract, dict)
            or sha256_json(contract)
            != assignment.get("assignment_sha256")
            or assignment.get("assignment_sha256")
            != task_card["assignment_sha256"]
        ):
            raise ValueError(
                "experiment task card assignment contract mismatch"
            )
        for key in (
            "project_id",
            "round_id",
            "assignment_id",
            "memory_id",
            "mode",
            "worker_id",
            "campaign_id",
            "source_claim_id",
            "return_relpath",
            "artifact_dir_relpath",
            "work_dir_relpath",
        ):
            if contract.get(key) != task_card.get(key):
                raise ValueError(
                    f"experiment task card contract {key} mismatch"
                )
        if "host_task_scope_id" in task_card and (
            contract.get("host_task_scope_id")
            != task_card["host_task_scope_id"]
        ):
            raise ValueError(
                "experiment task card contract host task scope mismatch"
            )
        if "campaign_snapshot_relpath" in task_card:
            for key in (
                "campaign_snapshot_relpath",
                "campaign_snapshot_sha256",
            ):
                if contract.get(key) != task_card[key]:
                    raise ValueError(
                        f"experiment task card contract {key} mismatch"
                    )
            campaign_snapshot_path = contained_path(
                self.project_root,
                task_card["campaign_snapshot_relpath"],
                "experiment campaign snapshot path",
            )
            if (
                campaign_snapshot_path
                != round_path.parent / "campaign.snapshot.json"
                or not campaign_snapshot_path.is_file()
                or campaign_snapshot_path.is_symlink()
                or sha256_bytes(campaign_snapshot_path.read_bytes())
                != task_card["campaign_snapshot_sha256"]
            ):
                raise ValueError(
                    "experiment campaign snapshot path/hash mismatch"
                )
            campaign_snapshot = self._read_json(
                campaign_snapshot_path
            )
            if (
                campaign_snapshot.get("campaign_id")
                != task_card["campaign_id"]
            ):
                raise ValueError(
                    "experiment campaign snapshot id mismatch"
                )
            source_claim_ids = set(
                campaign_snapshot.get("source_claim_ids", [])
            )
            if (
                task_card.get("source_claim_id") is not None
                and source_claim_ids
                and task_card["source_claim_id"] not in source_claim_ids
            ):
                raise ValueError(
                    "experiment task source claim is outside the campaign"
                )
            if (
                task_card["goal_relation"] == "refutes"
                and source_claim_ids
                and task_card.get("source_claim_id") is None
            ):
                raise ValueError(
                    "experiment refutation task lacks campaign source claim"
                )
        if (
            legacy_estimate_policy
            and not allow_historical_estimate_policy
        ):
            raise ValueError(
                "historical estimate-gated adoption binding is read-only; "
                "replan under current policy"
            )
        if require_active_work_unit:
            require_unaborted_work_unit(
                self.project_root,
                task_card["round_id"],
            )
        return task_card

    @staticmethod
    def validate_manifest(
        manifest: dict[str, Any],
        *,
        assignment_id: str,
    ) -> dict[str, Any]:
        require_exact_keys(
            manifest,
            required={
                "schema_version",
                "policy_revision",
                "experiment_id",
                "assignment_id",
                "objective",
                "command",
                "environment",
                "cost_model",
                "stages",
                "escalation_ladder",
                "checkpoint_policy",
                "resume_contract",
                "truth_status",
            },
            label="experiment manifest",
        )
        if manifest.get("schema_version") != 1:
            raise ValueError("experiment schema_version must be 1")
        if manifest.get("policy_revision") != POLICY_REVISION_V4:
            raise ValueError("experiment policy_revision mismatch")
        validate_experiment_id(require_string(manifest, "experiment_id"))
        if require_string(manifest, "assignment_id") != assignment_id:
            raise ValueError("experiment assignment mismatch")
        require_string(manifest, "objective")
        command = manifest.get("command")
        if not isinstance(command, list) or not command or any(
            not isinstance(value, str) or not value for value in command
        ):
            raise ValueError("experiment command must be a nonempty argv list")
        environment = manifest.get("environment")
        if not isinstance(environment, dict):
            raise ValueError("experiment environment must be an object")
        require_exact_keys(
            environment,
            required={"implementation", "version"},
            label="experiment environment",
        )
        require_string(environment, "implementation")
        require_string(environment, "version")
        cost = manifest.get("cost_model")
        if not isinstance(cost, dict):
            raise ValueError("experiment cost_model must be an object")
        require_exact_keys(
            cost,
            required={
                "dominant_operation",
                "estimated_cost",
                "expected_memory",
                "parallelism",
                "complexity_model",
            },
            label="experiment cost_model",
        )
        require_string(cost, "dominant_operation")
        if isinstance(cost.get("estimated_cost"), bool) or not isinstance(
            cost.get("estimated_cost"), (int, float)
        ):
            raise ValueError("experiment estimated_cost must be numeric")
        require_string(cost, "expected_memory")
        require_string(cost, "parallelism")
        complexity = cost.get("complexity_model")
        if not isinstance(complexity, dict):
            raise ValueError("experiment complexity_model must be an object")
        require_exact_keys(
            complexity,
            required={
                "parameters",
                "asymptotic_time",
                "asymptotic_space",
                "estimated_operation_count",
                "estimate_basis",
                "intermediate_object_estimates",
            },
            label="experiment complexity_model",
        )
        if not isinstance(complexity["parameters"], dict):
            raise ValueError("experiment complexity parameters must be an object")
        for key in ("asymptotic_time", "asymptotic_space", "estimate_basis"):
            require_string(complexity, key)
        operation_count = complexity["estimated_operation_count"]
        if operation_count is not None and (
            isinstance(operation_count, bool)
            or not isinstance(operation_count, int)
            or operation_count < 0
        ):
            raise ValueError("estimated_operation_count must be null or nonnegative")
        if not isinstance(complexity["intermediate_object_estimates"], list):
            raise ValueError("intermediate_object_estimates must be a list")
        stages = _require_string_list(manifest, "stages")
        if not stages or len(set(stages)) != len(stages):
            raise ValueError("experiment stages must be unique and nonempty")
        ladder = manifest.get("escalation_ladder")
        if not isinstance(ladder, list) or any(not isinstance(item, dict) for item in ladder):
            raise ValueError("experiment escalation_ladder must be a list of objects")
        for index, stage in enumerate(ladder, 1):
            require_exact_keys(
                stage,
                required={"stage_id", "arithmetic", "advance_condition"},
                label=f"escalation_ladder[{index}]",
            )
            require_string(stage, "stage_id")
            require_string(stage, "arithmetic")
            require_string(stage, "advance_condition")
        require_string(manifest, "checkpoint_policy")
        resume = manifest.get("resume_contract")
        if not isinstance(resume, dict):
            raise ValueError("experiment resume_contract must be an object")
        require_exact_keys(
            resume,
            required={
                "checkpoint_format",
                "resume_command",
                "compatibility_fields",
                "deterministic_replay_required",
            },
            label="experiment resume_contract",
        )
        require_string(resume, "checkpoint_format")
        if not isinstance(resume["resume_command"], list) or any(
            not isinstance(value, str) for value in resume["resume_command"]
        ):
            raise ValueError("resume_command must be an argv list")
        _require_string_list(resume, "compatibility_fields")
        if not isinstance(resume["deterministic_replay_required"], bool):
            raise ValueError("deterministic_replay_required must be boolean")
        if manifest.get("truth_status") != "exploration":
            raise ValueError("experiment truth_status must be exploration")
        expected_id = "experiment-" + sha256_json(
            {
                key: value
                for key, value in manifest.items()
                if key != "experiment_id"
            }
        )[:16]
        if manifest["experiment_id"] != expected_id:
            raise ValueError("experiment id/hash mismatch")
        return manifest

    def _directory(
        self,
        *,
        task_card: dict[str, Any],
        experiment_id: str,
    ) -> Path:
        work_dir = contained_path(
            self.project_root,
            task_card["work_dir_relpath"],
            "task card work directory",
        )
        return work_dir / "experiments" / validate_experiment_id(experiment_id)

    @staticmethod
    def governance_task_id(task_card: dict[str, Any]) -> str:
        validate_task_card(task_card, allow_legacy_adoption=True)
        host_task_scope_id = task_card.get("host_task_scope_id")
        if host_task_scope_id is None:
            semantic = {
                "schema_version": 1,
                "policy_revision": POLICY_REVISION_V4,
                "project_id": task_card["project_id"],
                "campaign_id": task_card["campaign_id"],
            }
        else:
            semantic = {
                "schema_version": 2,
                "policy_revision": POLICY_REVISION_V4,
                "project_id": task_card["project_id"],
                "host_task_scope_id": host_task_scope_id,
            }
        return "taskgov-" + sha256_json(semantic)[:32]

    def _governance_events_path(self, task_card: dict[str, Any]) -> Path:
        return (
            self.project_root
            / "experiments"
            / "task-governance"
            / self.governance_task_id(task_card)
            / "events.jsonl"
        )

    def _governance_state(
        self,
        task_card: dict[str, Any],
    ) -> dict[str, Any]:
        governance_task_id = self.governance_task_id(task_card)
        events_path = self._governance_events_path(task_card)
        events = self._read_jsonl(events_path)
        state = "pre_threshold"
        notice: dict[str, Any] | None = None
        latest_observation: dict[str, Any] | None = None
        decision: dict[str, Any] | None = None
        seen_event_ids: set[str] = set()
        for index, event in enumerate(events, 1):
            event_id = require_string(event, "event_id")
            semantic = dict(event)
            semantic.pop("event_id")
            if sha256_json(semantic) != event_id:
                raise ValueError(
                    f"task governance event {index} id/hash mismatch"
                )
            if event_id in seen_event_ids:
                raise ValueError("task governance ledger repeats an event id")
            seen_event_ids.add(event_id)
            if (
                event.get("governance_task_id") != governance_task_id
                or event.get("project_id") != task_card["project_id"]
            ):
                raise ValueError("task governance event binding mismatch")
            host_task_scope_id = task_card.get("host_task_scope_id")
            if (
                host_task_scope_id is not None
                and event.get("host_task_scope_id")
                != host_task_scope_id
            ):
                raise ValueError(
                    "task governance host-task scope mismatch"
                )
            event_campaign_id = event.get("campaign_id")
            event_memory_id = event.get("memory_id")
            if (
                not isinstance(event_campaign_id, str)
                or CAMPAIGN_ID_RE.fullmatch(event_campaign_id) is None
                or not isinstance(event_memory_id, str)
                or MEMORY_ID_RE.fullmatch(event_memory_id) is None
            ):
                raise ValueError(
                    "task governance event provenance ids are invalid"
                )
            if (
                host_task_scope_id is None
                and "host_task_scope_id" in event
            ):
                raise ValueError(
                    "legacy task governance event has unexpected host scope"
                )
            if (
                host_task_scope_id is None
                and event_campaign_id != task_card["campaign_id"]
            ):
                raise ValueError(
                    "legacy task governance campaign binding mismatch"
                )
            event_type = event.get("event")
            if event_type in {"observation", "continuation_notice"}:
                canonical = event.get("canonical_active_intervals")
                if not isinstance(canonical, list):
                    raise ValueError(
                        "task governance observation lacks canonical intervals"
                    )
                elapsed_ns = event.get("actual_cumulative_task_ns")
                if (
                    isinstance(elapsed_ns, bool)
                    or not isinstance(elapsed_ns, int)
                    or elapsed_ns < 0
                ):
                    raise ValueError(
                        "task governance elapsed time is invalid"
                    )
                recomputed, recomputed_ns = _canonical_active_intervals(
                    [
                        {
                            "clock_epoch": item["clock_epoch"],
                            "lease_id": f"canonical-{item_index}",
                            "start_ns": item["start_ns"],
                            "end_ns": item["end_ns"],
                        }
                        for item_index, item in enumerate(canonical, 1)
                    ]
                )
                if recomputed != canonical or recomputed_ns != elapsed_ns:
                    raise ValueError(
                        "task governance interval union is not canonical"
                    )
                if latest_observation is not None and not _interval_union_extends(
                    latest_observation["canonical_active_intervals"],
                    canonical,
                ):
                    raise ValueError(
                        "task governance observation regresses active intervals"
                    )
                if event_type == "continuation_notice":
                    if notice is not None or elapsed_ns <= CONTINUATION_THRESHOLD_NS:
                        raise ValueError(
                            "task governance has an invalid continuation notice"
                        )
                    notice = event
                    state = "notice_issued"
                elif notice is None and elapsed_ns > CONTINUATION_THRESHOLD_NS:
                    raise ValueError(
                        "strict threshold crossing lacks a continuation notice"
                    )
                latest_observation = event
            elif event_type == "continuation_decision":
                if (
                    notice is None
                    or event.get("notice_id") != notice.get("notice_id")
                ):
                    raise ValueError(
                        "task governance response does not bind the issued notice"
                    )
                choice = event.get("decision")
                if choice not in GOVERNANCE_DECISIONS:
                    raise ValueError("task governance decision is invalid")
                if (
                    choice == "continue"
                    and state != "notice_issued"
                ) or (
                    choice == "stop"
                    and state not in {"notice_issued", "acknowledged"}
                ):
                    raise ValueError(
                        "task governance has an invalid notice response transition"
                    )
                authorized_prefix = _ledger_prefix(events_path, index - 1)
                if (
                    event.get("authorized_prior_event_count")
                    != authorized_prefix["event_count"]
                    or event.get("authorized_prior_events_sha256")
                    != authorized_prefix["sha256"]
                ):
                    raise ValueError(
                        "task governance decision prior-prefix binding mismatch"
                    )
                decision = event
                state = "acknowledged" if choice == "continue" else "stopped"
            else:
                raise ValueError(
                    f"unsupported task governance event: {event_type!r}"
                )
        prefix = _ledger_prefix(events_path)
        return {
            "governance_task_id": governance_task_id,
            "state": state,
            "notice": notice,
            "decision": decision,
            "latest_observation": latest_observation,
            "event_count": prefix["event_count"],
            "events_sha256": prefix["sha256"],
            "events_path": str(events_path),
        }

    def _assert_governance_allows(
        self,
        task_card: dict[str, Any],
        *,
        action: str,
    ) -> dict[str, Any]:
        status = self._governance_state(task_card)
        if status["state"] == "stopped":
            raise ValueError(
                f"task was explicitly stopped by host/user response; "
                f"{action} is forbidden"
            )
        return status

    @_serialized_experiment
    def observe(
        self,
        *,
        task_card: dict[str, Any],
        payload: dict[str, Any],
        actor_role: str,
    ) -> dict[str, Any]:
        """Record host-observed task time; estimates never enter this state."""

        self._validate_bound_task_card(
            task_card,
            require_active_work_unit=True,
        )
        self._require_hard_caps(task_card)
        if actor_role not in GOVERNANCE_ACTOR_ROLES:
            raise ValueError(
                "experiment-observe requires the main or operator role"
            )
        require_exact_keys(
            payload,
            required={
                "schema_version",
                "observation_id",
                "measurement_method",
                "active_intervals",
                "actual_resources",
                "experimental_nature",
                "progress",
                "latest_checkpoint",
                "importance_and_continuation_value",
                "stopping_impact",
            },
            label="task-time observation",
        )
        if payload.get("schema_version") != 1:
            raise ValueError("task-time observation schema_version must be 1")
        observation_id = require_string(payload, "observation_id")
        if payload.get("measurement_method") != GOVERNANCE_MEASUREMENT_METHOD:
            raise ValueError(
                "task time must use host monotonic active-interval union"
            )
        actual_resources = payload.get("actual_resources")
        if (
            not isinstance(actual_resources, dict)
            or not actual_resources
            or any(not isinstance(key, str) or not key for key in actual_resources)
        ):
            raise ValueError("actual_resources must be a nonempty keyed object")
        for key, value in actual_resources.items():
            if isinstance(value, bool):
                raise ValueError(f"actual_resources.{key} cannot be boolean")
            if isinstance(value, (int, float)):
                _nonnegative_number(
                    value,
                    label=f"actual_resources.{key}",
                )
            elif not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"actual_resources.{key} must be nonnegative numeric "
                    "or an explicit nonempty status string"
                )
        for key in (
            "experimental_nature",
            "progress",
            "importance_and_continuation_value",
            "stopping_impact",
        ):
            require_string(payload, key)
        require_string(payload, "latest_checkpoint", allow_empty=True)
        canonical, elapsed_ns = _canonical_active_intervals(
            payload["active_intervals"]
        )
        observation_semantic = {
            "schema_version": 1,
            "observation_id": observation_id,
            "measurement_method": GOVERNANCE_MEASUREMENT_METHOD,
            "canonical_active_intervals": canonical,
            "actual_cumulative_task_ns": elapsed_ns,
            "actual_resources": actual_resources,
            "experimental_nature": payload["experimental_nature"],
            "progress": payload["progress"],
            "latest_checkpoint": payload["latest_checkpoint"],
            "importance_and_continuation_value": payload[
                "importance_and_continuation_value"
            ],
            "stopping_impact": payload["stopping_impact"],
        }
        observation_sha256 = sha256_json(observation_semantic)
        state = self._governance_state(task_card)
        if state["state"] == "stopped":
            raise ValueError("stopped task cannot accept new time observations")
        events_path = self._governance_events_path(task_card)
        for existing in self._read_jsonl(events_path):
            if existing.get("observation_id") != observation_id:
                continue
            if existing.get("observation_sha256") != observation_sha256:
                raise ValueError(
                    "task-time observation id was reused with different evidence"
                )
            return {
                "governance_task_id": state["governance_task_id"],
                "event_id": existing["event_id"],
                "event": existing["event"],
                "notice_id": existing.get("notice_id"),
                "state": self._governance_state(task_card)["state"],
                "actual_cumulative_task_seconds": (
                    existing["actual_cumulative_task_ns"] / 1_000_000_000
                ),
                "status": "already_recorded",
                **(
                    {
                        "notice": {
                            key: existing[key]
                            for key in (
                                "experimental_nature",
                                "actual_resources",
                                "progress",
                                "latest_checkpoint",
                                "importance_and_continuation_value",
                                "stopping_impact",
                            )
                        }
                    }
                    if existing["event"] == "continuation_notice"
                    else {}
                ),
            }
        latest = state["latest_observation"]
        if latest is not None:
            if not _interval_union_extends(
                latest["canonical_active_intervals"],
                canonical,
            ):
                raise ValueError(
                    "task-time observation cannot remove or shrink prior active intervals"
                )
            if elapsed_ns < latest["actual_cumulative_task_ns"]:
                raise ValueError(
                    "task-time observation cannot regress cumulative active time"
                )
        crosses = (
            state["notice"] is None
            and (latest is None or latest["actual_cumulative_task_ns"] <= CONTINUATION_THRESHOLD_NS)
            and elapsed_ns > CONTINUATION_THRESHOLD_NS
        )
        event_type = "continuation_notice" if crosses else "observation"
        semantic = {
            "schema_version": 1,
            "policy_revision": POLICY_REVISION_V4,
            "event": event_type,
            "governance_task_id": state["governance_task_id"],
            "project_id": task_card["project_id"],
            "campaign_id": task_card["campaign_id"],
            "memory_id": task_card["memory_id"],
            **(
                {
                    "host_task_scope_id": task_card[
                        "host_task_scope_id"
                    ]
                }
                if "host_task_scope_id" in task_card
                else {}
            ),
            **observation_semantic,
            "observation_sha256": observation_sha256,
        }
        if crosses:
            semantic["notice_id"] = "notice-" + sha256_json(
                {
                    "governance_task_id": state["governance_task_id"],
                    "observation_sha256": observation_sha256,
                    "threshold_ns": CONTINUATION_THRESHOLD_NS,
                }
            )[:32]
            semantic["threshold_seconds"] = CONTINUATION_THRESHOLD_SECONDS
            semantic["strictly_exceeded"] = True
        event_id = sha256_json(semantic)
        event = {**semantic, "event_id": event_id}
        self._governance_ledger(task_card, events_path).mutate(
            lambda session: (
                None
                if session.find(event_id) is not None
                else session.append(event)
            )
        )
        result = {
            "governance_task_id": state["governance_task_id"],
            "event_id": event_id,
            "event": event_type,
            "notice_id": semantic.get("notice_id"),
            "state": "notice_issued" if crosses else state["state"],
            "actual_cumulative_task_seconds": elapsed_ns / 1_000_000_000,
            "status": "notice_issued" if crosses else "observed",
        }
        if crosses:
            result["notice"] = {
                "experimental_nature": payload["experimental_nature"],
                "actual_cumulative_task_seconds": (
                    elapsed_ns / 1_000_000_000
                ),
                "actual_resources": actual_resources,
                "progress": payload["progress"],
                "latest_checkpoint": payload["latest_checkpoint"],
                "importance_and_continuation_value": payload[
                    "importance_and_continuation_value"
                ],
                "stopping_impact": payload["stopping_impact"],
            }
        return result

    @_serialized_experiment
    def decision(
        self,
        *,
        task_card: dict[str, Any],
        payload: dict[str, Any],
        actor_role: str,
    ) -> dict[str, Any]:
        self._validate_bound_task_card(
            task_card,
            require_active_work_unit=True,
        )
        self._require_hard_caps(task_card)
        if actor_role not in GOVERNANCE_ACTOR_ROLES:
            raise ValueError(
                "experiment-decision requires the main or operator role"
            )
        require_exact_keys(
            payload,
            required={
                "schema_version",
                "decision_id",
                "notice_id",
                "decision",
                "authority_kind",
                "authority_reference",
                "reason",
            },
            label="task continuation decision",
        )
        if payload.get("schema_version") != 1:
            raise ValueError("task continuation decision schema_version must be 1")
        decision_id = require_string(payload, "decision_id")
        notice_id = require_string(payload, "notice_id")
        choice = require_string(payload, "decision")
        if choice not in GOVERNANCE_DECISIONS:
            raise ValueError("task continuation decision must be continue or stop")
        if require_string(payload, "authority_kind") not in {"host", "user"}:
            raise ValueError("decision authority_kind must be host or user")
        require_string(payload, "authority_reference")
        require_string(payload, "reason")
        state = self._governance_state(task_card)
        semantic_input = {
            "schema_version": 1,
            "decision_id": decision_id,
            "notice_id": notice_id,
            "decision": choice,
            "authority_kind": payload["authority_kind"],
            "authority_reference": payload["authority_reference"],
            "reason": payload["reason"],
        }
        decision_sha256 = sha256_json(semantic_input)
        events_path = self._governance_events_path(task_card)
        for existing in self._read_jsonl(events_path):
            if existing.get("decision_id") != decision_id:
                continue
            if existing.get("decision_sha256") != decision_sha256:
                raise ValueError(
                    "continuation decision id was reused with different evidence"
                )
            return {
                "governance_task_id": state["governance_task_id"],
                "event_id": existing["event_id"],
                "decision": existing["decision"],
                "state": self._governance_state(task_card)["state"],
                "status": "already_recorded",
            }
        if state["notice"] is None:
            raise ValueError("no task continuation notice has been issued")
        if notice_id != state["notice"]["notice_id"]:
            raise ValueError("response does not bind the issued notice")
        if (
            choice == "continue"
            and state["state"] != "notice_issued"
        ) or (
            choice == "stop"
            and state["state"] not in {"notice_issued", "acknowledged"}
        ):
            raise ValueError(
                "no further response is available for this continuation notice"
            )
        semantic = {
            "schema_version": 1,
            "policy_revision": POLICY_REVISION_V4,
            "event": "continuation_decision",
            "governance_task_id": state["governance_task_id"],
            "project_id": task_card["project_id"],
            "campaign_id": task_card["campaign_id"],
            "memory_id": task_card["memory_id"],
            **(
                {
                    "host_task_scope_id": task_card[
                        "host_task_scope_id"
                    ]
                }
                if "host_task_scope_id" in task_card
                else {}
            ),
            **semantic_input,
            "decision_sha256": decision_sha256,
            "authorized_prior_event_count": state["event_count"],
            "authorized_prior_events_sha256": state["events_sha256"],
        }
        event_id = sha256_json(semantic)
        self._governance_ledger(task_card, events_path).mutate(
            lambda session: session.append({**semantic, "event_id": event_id})
        )
        return {
            "governance_task_id": state["governance_task_id"],
            "event_id": event_id,
            "decision": choice,
            "state": "acknowledged" if choice == "continue" else "stopped",
            "status": "recorded",
        }

    @_serialized_experiment
    def start(
        self,
        *,
        task_card: dict[str, Any],
        manifest: dict[str, Any],
    ) -> dict[str, Any]:
        self._validate_bound_task_card(
            task_card,
            require_active_work_unit=True,
        )
        self._require_hard_caps(task_card)
        if feature_status(
            task_card["adoption_plan"],
            "experiment_checkpoint",
            allow_legacy_estimate_policy=True,
        ) == "not_applicable":
            raise ValueError(
                "task card declares experiment/checkpoint as not applicable"
            )
        body = dict(manifest)
        body.setdefault("schema_version", 1)
        body.setdefault("policy_revision", POLICY_REVISION_V4)
        body["assignment_id"] = task_card["assignment_id"]
        if "experiment_id" not in body:
            body["experiment_id"] = "experiment-" + sha256_json(body)[:16]
        self.validate_manifest(body, assignment_id=task_card["assignment_id"])
        directory = self._directory(
            task_card=task_card, experiment_id=body["experiment_id"]
        )
        manifest_path = directory / "manifest.json"
        if manifest_path.exists():
            if (
                not manifest_path.is_file()
                or manifest_path.is_symlink()
                or self._read_json(manifest_path) != body
            ):
                raise ValueError("experiment manifest collision")
            return {
                "experiment_id": body["experiment_id"],
                "directory": str(directory),
                "status": (
                    "finalized"
                    if (directory / "final_receipt.json").exists()
                    else "already_started"
                ),
            }
        self._assert_governance_allows(
            task_card,
            action="starting an experiment",
        )
        started_event = {
            "event": "started",
            "stage": "",
            "completed_units": 0,
            "total_units_or_null": None,
            "cpu_seconds": 0.0,
            "wall_seconds": 0.0,
            "rss_bytes": 0,
            "latest_check": "manifest validated",
        }
        hard_caps = self._require_hard_caps(task_card)
        started_bytes = len(ExperimentEventLedger._encode_line(started_event))
        if (
            hard_caps["max_experiment_event_count_total"] < 1
            or started_bytes > hard_caps["max_experiment_event_bytes_each"]
            or started_bytes > hard_caps["max_experiment_event_bytes_total"]
        ):
            raise ValueError(
                "experiment started event cannot fit within hard caps"
            )
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "checkpoints").mkdir(parents=True, exist_ok=True)
        self._write_json_once(manifest_path, body)
        events_path = directory / "events.jsonl"
        if not events_path.exists():
            ExperimentEventLedger(
                events_path, hard_caps=self._hard_caps(task_card)
            ).mutate(
                lambda session: (
                    session.append(started_event)
                    if session.event_count == 0
                    else None
                )
            )
        return {
            "experiment_id": body["experiment_id"],
            "directory": str(directory),
            "status": "started",
        }

    @_serialized_experiment
    def event(
        self,
        *,
        task_card: dict[str, Any],
        experiment_id: str,
        payload: dict[str, Any],
    ) -> str:
        self._validate_bound_task_card(
            task_card,
            require_active_work_unit=True,
        )
        self._require_hard_caps(task_card)
        directory = self._directory(
            task_card=task_card, experiment_id=experiment_id
        )
        manifest = self.validate_manifest(
            self._read_json(directory / "manifest.json"),
            assignment_id=task_card["assignment_id"],
        )
        if (directory / "final_receipt.json").exists():
            raise ValueError("finalized experiment cannot accept new events")
        event = require_string(payload, "event")
        if event not in EXPERIMENT_EVENTS or event in {"finalized", "resumed"}:
            raise ValueError("unsupported direct experiment event")
        stage = payload.get("stage")
        if stage is not None:
            if not isinstance(stage, str):
                raise ValueError("experiment event stage must be a string")
            if stage and stage not in manifest["stages"]:
                raise ValueError("experiment event stage is unknown")
        if event == "stage_completed":
            require_string(payload, "stage")
            require_string(payload, "advance_condition_disposition")
            counts = payload.get("actual_intermediate_object_counts", [])
            if not isinstance(counts, list) or any(
                not isinstance(item, dict) for item in counts
            ):
                raise ValueError(
                    "stage_completed actual_intermediate_object_counts "
                    "must be a list of objects"
                )
            for index, item in enumerate(counts, 1):
                require_exact_keys(
                    item,
                    required={"object_kind", "count"},
                    label=f"actual_intermediate_object_counts[{index}]",
                )
                require_string(item, "object_kind")
                count = item.get("count")
                if (
                    isinstance(count, bool)
                    or not isinstance(count, int)
                    or count < 0
                ):
                    raise ValueError(
                        "actual intermediate-object count must be nonnegative"
                    )
        if event == "heartbeat":
            require_exact_keys(
                payload,
                required=HEARTBEAT_FIELDS.difference({"timestamp"}),
                optional={"timestamp"},
                label="experiment heartbeat",
            )
            if "timestamp" in payload:
                require_string(payload, "timestamp")
            require_string(payload, "stage")
            require_string(payload, "latest_check")
            completed = _nonnegative_number(
                payload.get("completed_units"),
                label="heartbeat completed_units",
            )
            total = payload.get("total_units_or_null")
            if total is not None:
                total_number = _nonnegative_number(
                    total,
                    label="heartbeat total_units_or_null",
                )
                if completed > total_number:
                    raise ValueError(
                        "heartbeat completed_units exceeds total_units_or_null"
                    )
            _nonnegative_number(
                payload.get("cpu_seconds"),
                label="heartbeat cpu_seconds",
            )
            _nonnegative_number(
                payload.get("wall_seconds"),
                label="heartbeat wall_seconds",
            )
            rss = payload.get("rss_bytes")
            if isinstance(rss, bool) or not isinstance(rss, int) or rss < 0:
                raise ValueError(
                    "heartbeat rss_bytes must be a nonnegative integer"
                )
        if event == "checkpoint":
            checkpoint_path = require_string(payload, "checkpoint_path")
            checkpoint = contained_path(
                directory, checkpoint_path, "checkpoint path"
            )
            checkpoint_root = (directory / "checkpoints").resolve()
            if (
                not checkpoint.is_relative_to(checkpoint_root)
                or not checkpoint.is_file()
                or checkpoint.is_symlink()
            ):
                raise ValueError("checkpoint is missing or not a regular file")
            self._checkpoint_inventory(
                directory, self._hard_caps(task_card)
            )
            checkpoint_bytes = checkpoint.stat().st_size
            supplied_bytes = payload.get("checkpoint_bytes")
            if supplied_bytes is not None and supplied_bytes != checkpoint_bytes:
                raise ValueError("checkpoint byte count mismatch")
            payload = {**payload, "checkpoint_bytes": checkpoint_bytes}
            if require_string(payload, "checkpoint_sha256") != self._stream_sha256(
                checkpoint
            ):
                raise ValueError("checkpoint hash mismatch")
            completed_stage = require_string(payload, "completed_stage")
            if completed_stage not in manifest["stages"]:
                raise ValueError("checkpoint completed stage is unknown")
            if "checkpoint_format_version" in payload:
                require_string(payload, "checkpoint_format_version")
            require_string(payload, "resume_compatibility_hash")
        semantic = {
            "schema_version": 1,
            "policy_revision": POLICY_REVISION_V4,
            **payload,
        }
        event_id = sha256_json(semantic)
        ledger = ExperimentEventLedger(
            directory / "events.jsonl",
            hard_caps=self._hard_caps(task_card),
        )
        self._assert_governance_allows(
            task_card,
            action=f"recording experiment event {event}",
        )
        if ledger.mutate(lambda session: session.find(event_id)) is not None:
            return event_id

        def record(
            session: Any,
        ) -> str:
            if session.find(event_id) is not None:
                return event_id
            if event == "checkpoint" and not session.has_stage_completed(
                completed_stage
            ):
                raise ValueError(
                    "checkpoint requires a recorded completed stage"
                )
            if (directory / "final_receipt.json").exists():
                raise ValueError(
                    "finalized experiment cannot accept new events"
                )
            latest = session.latest()
            if latest is not None and latest.get("event") == "failed":
                raise ValueError(
                    "failed experiment requires a "
                    "compatibility-validated resume"
                )
            if event == "heartbeat":
                previous = next(
                    (
                        item
                        for item in reversed(
                            self._read_jsonl(directory / "events.jsonl")
                        )
                        if item.get("event") == "heartbeat"
                        and item.get("stage") == payload["stage"]
                    ),
                    None,
                )
                if previous is not None:
                    for key in (
                        "completed_units",
                        "cpu_seconds",
                        "wall_seconds",
                    ):
                        if float(payload[key]) < float(previous[key]):
                            raise ValueError(
                                f"heartbeat {key} cannot regress within one stage"
                            )
            session.append({**semantic, "event_id": event_id})
            return event_id

        return ledger.mutate(record)

    def audit_hard_caps(
        self,
        *,
        task_card: dict[str, Any],
        experiment_id: str,
    ) -> dict[str, Any]:
        """Read-only audit of one experiment's canonical log and checkpoints."""
        directory = self._directory(
            task_card=task_card, experiment_id=experiment_id
        )
        caps = self._require_hard_caps(task_card)
        ledger_result = ExperimentEventLedger(
            directory / "events.jsonl", hard_caps=caps
        ).audit_read_only()
        errors = list(ledger_result["errors"])
        try:
            inventory = self._checkpoint_inventory(directory, caps)
        except (OSError, ValueError) as exc:
            inventory = {
                "files": [], "file_count": 0, "bytes_total": 0, "sha256": ""
            }
            errors.append(str(exc))
        actual = {item["path"]: item for item in inventory["files"]}
        registered: dict[str, dict[str, Any]] = {}
        for event in ledger_result["events"]:
            if event.get("event") != "checkpoint":
                continue
            path = event.get("checkpoint_path")
            if not isinstance(path, str):
                errors.append("checkpoint event has invalid path")
                continue
            if path in registered and registered[path] != event:
                errors.append(f"checkpoint path has conflicting registrations: {path}")
            registered[path] = event
        for path, item in actual.items():
            event = registered.get(path)
            if event is None:
                errors.append(f"checkpoint file is not registered: {path}")
            elif (
                event.get("checkpoint_sha256") != item["sha256"]
                or event.get("checkpoint_bytes") != item["bytes"]
            ):
                errors.append(f"checkpoint registration mismatch: {path}")
        for path in sorted(set(registered) - set(actual)):
            errors.append(f"registered checkpoint file is missing: {path}")
        return {
            "current_ok": not errors,
            "errors": errors,
            "event_count": ledger_result["event_count"],
            "worker_event_count": ledger_result["worker_event_count"],
            "event_bytes_total": ledger_result["event_bytes_total"],
            "checkpoint_file_count": inventory["file_count"],
            "checkpoint_bytes_total": inventory["bytes_total"],
            "checkpoint_inventory_sha256": inventory["sha256"],
        }

    def audit_governance_hard_caps(
        self,
        *,
        task_card: dict[str, Any],
    ) -> dict[str, Any]:
        """Read-only audit of the host-task governance ledger."""

        self._require_hard_caps(task_card)
        events_path = self._governance_events_path(task_card)
        if not events_path.exists():
            return {
                "current_ok": True,
                "errors": [],
                "event_count": 0,
                "worker_event_count": 0,
                "event_bytes_total": 0,
            }
        return self._governance_ledger(
            task_card,
            events_path,
        ).audit_read_only()

    @_serialized_experiment
    def resume(
        self,
        *,
        task_card: dict[str, Any],
        experiment_id: str,
        checkpoint_event_id: str,
        current_compatibility: dict[str, Any],
    ) -> dict[str, Any]:
        self._validate_bound_task_card(
            task_card,
            require_active_work_unit=True,
        )
        self._require_hard_caps(task_card)
        directory = self._directory(
            task_card=task_card,
            experiment_id=experiment_id,
        )
        if (directory / "final_receipt.json").exists():
            raise ValueError("finalized experiment cannot be resumed")
        validated = self.validate_resume(
            task_card=task_card,
            experiment_id=experiment_id,
            checkpoint_event_id=checkpoint_event_id,
            current_compatibility=current_compatibility,
        )
        manifest = self.validate_manifest(
            self._read_json(directory / "manifest.json"),
            assignment_id=task_card["assignment_id"],
        )
        compatibility_fields = manifest["resume_contract"][
            "compatibility_fields"
        ]
        bound_compatibility = {
            key: current_compatibility.get(key)
            for key in compatibility_fields
        }
        semantic = {
            "schema_version": 1,
            "policy_revision": POLICY_REVISION_V4,
            "event": "resumed",
            "checkpoint_event_id": checkpoint_event_id,
            "checkpoint_path": validated["checkpoint_path"],
            "resume_from_stage": validated["resume_from_stage"],
            "resume_compatibility_hash": sha256_json(bound_compatibility),
        }
        event_id = sha256_json(semantic)
        events = self._read_jsonl(directory / "events.jsonl")
        for existing in events:
            if existing.get("event_id") == event_id:
                return {
                    **validated,
                    "experiment_id": experiment_id,
                    "resume_event_id": event_id,
                    "status": "resumed",
                }
        self._assert_governance_allows(
            task_card,
            action="resuming an experiment",
        )
        resumed_event = {**semantic, "event_id": event_id}
        ExperimentEventLedger(
            directory / "events.jsonl",
            hard_caps=self._hard_caps(task_card),
        ).mutate(
            lambda session: (
                None
                if session.find(event_id) is not None
                else session.append(resumed_event)
            )
        )
        return {
            **validated,
            "experiment_id": experiment_id,
            "resume_event_id": event_id,
            "status": "resumed",
        }

    @_serialized_experiment_read
    def status(
        self,
        *,
        task_card: dict[str, Any],
        experiment_id: str,
    ) -> dict[str, Any]:
        self._validate_bound_task_card(task_card)
        directory = self._directory(
            task_card=task_card, experiment_id=experiment_id
        )
        manifest = self.validate_manifest(
            self._read_json(directory / "manifest.json"),
            assignment_id=task_card["assignment_id"],
        )
        events = self._read_jsonl(directory / "events.jsonl")
        finalized = (directory / "final_receipt.json").exists()
        completed = [
            event.get("stage")
            for event in events
            if event.get("event") == "stage_completed"
        ]
        governance = self._governance_state(task_card)
        issued_notice = governance["notice"]
        return {
            "experiment_id": experiment_id,
            "objective": manifest["objective"],
            "status": "finalized" if finalized else (
                "failed" if events and events[-1].get("event") == "failed" else "running"
            ),
            "completed_stages": completed,
            "event_count": len(events),
            "latest_event": events[-1] if events else None,
            "task_governance": {
                key: governance[key]
                for key in (
                    "governance_task_id",
                    "state",
                    "event_count",
                    "events_sha256",
                )
            }
            | (
                {
                    "issued_notice": {
                        key: issued_notice[key]
                        for key in (
                            "notice_id",
                            "experimental_nature",
                            "actual_cumulative_task_ns",
                            "actual_resources",
                            "progress",
                            "latest_checkpoint",
                            "importance_and_continuation_value",
                            "stopping_impact",
                        )
                    }
                }
                if issued_notice is not None
                else {}
            ),
        }

    @_serialized_experiment_read
    def validate_resume(
        self,
        *,
        task_card: dict[str, Any],
        experiment_id: str,
        checkpoint_event_id: str,
        current_compatibility: dict[str, Any],
    ) -> dict[str, Any]:
        self._validate_bound_task_card(task_card)
        directory = self._directory(
            task_card=task_card, experiment_id=experiment_id
        )
        manifest = self.validate_manifest(
            self._read_json(directory / "manifest.json"),
            assignment_id=task_card["assignment_id"],
        )
        events = self._read_jsonl(directory / "events.jsonl")
        matches = [
            event
            for event in events
            if event.get("event_id") == checkpoint_event_id
            and event.get("event") == "checkpoint"
        ]
        if len(matches) != 1:
            raise ValueError("unknown checkpoint event")
        checkpoint = contained_path(
            directory,
            require_string(matches[0], "checkpoint_path"),
            "checkpoint path",
        )
        checkpoint_root = (directory / "checkpoints").resolve()
        if (
            not checkpoint.is_relative_to(checkpoint_root)
            or not checkpoint.is_file()
            or checkpoint.is_symlink()
            or self._stream_sha256(checkpoint)
            != require_string(matches[0], "checkpoint_sha256")
        ):
            raise ValueError(
                "checkpoint bytes changed after the recorded checkpoint event"
            )
        fields = manifest["resume_contract"]["compatibility_fields"]
        bound = {key: current_compatibility.get(key) for key in fields}
        if sha256_json(bound) != matches[0]["resume_compatibility_hash"]:
            raise ValueError("checkpoint is incompatible with the current resume contract")
        return {
            "compatible": True,
            "checkpoint_path": matches[0]["checkpoint_path"],
            "resume_from_stage": matches[0]["completed_stage"],
        }

    @_serialized_experiment
    def finalize(
        self,
        *,
        task_card: dict[str, Any],
        experiment_id: str,
        selected_paths: list[str],
    ) -> dict[str, Any]:
        self._validate_bound_task_card(
            task_card,
            require_active_work_unit=True,
        )
        self._require_hard_caps(task_card)
        governance = self._assert_governance_allows(
            task_card,
            action="finalizing an experiment",
        )
        if not selected_paths:
            raise ValueError("experiment finalize requires selected outputs")
        directory = self._directory(
            task_card=task_card, experiment_id=experiment_id
        )
        manifest = self.validate_manifest(
            self._read_json(directory / "manifest.json"),
            assignment_id=task_card["assignment_id"],
        )
        receipt_path = directory / "final_receipt.json"
        if receipt_path.exists():
            receipt = validate_experiment_final_receipt(
                project_root=self.project_root,
                task_card=task_card,
                receipt_path=receipt_path,
                require_terminal_event=False,
            )
            finalized_semantic = {
                "schema_version": 1,
                "policy_revision": POLICY_REVISION_V4,
                "event": "finalized",
                "receipt_sha256": receipt["receipt_sha256"],
            }
            finalized_event = {
                **finalized_semantic,
                "event_id": sha256_json(finalized_semantic),
            }
            ExperimentEventLedger(
                directory / "events.jsonl",
                hard_caps=self._hard_caps(task_card),
            ).mutate(
                lambda session: (
                    None
                    if session.find(finalized_event["event_id"]) is not None
                    else session.append(finalized_event)
                )
            )
            return validate_experiment_final_receipt(
                project_root=self.project_root,
                task_card=task_card,
                receipt_path=receipt_path,
            )
        events = self._read_jsonl(directory / "events.jsonl")
        if events and events[-1].get("event") == "failed":
            raise ValueError(
                "failed experiment requires a compatibility-validated resume"
            )
        if not any(event.get("event") == "stage_completed" for event in events):
            raise ValueError(
                "experiment finalize requires at least one completed stage"
            )
        artifact_dir = contained_path(
            self.project_root,
            task_card["artifact_dir_relpath"],
            "task card artifact directory",
        )
        artifact_dir.mkdir(parents=True, exist_ok=True)
        planned_outputs: list[tuple[Path, bytes, dict[str, str]]] = []
        destinations: set[Path] = set()
        for selected in selected_paths:
            relative = require_relative_path(selected, "selected experiment output")
            source = (directory / Path(*relative.parts)).resolve()
            if not source.is_relative_to(directory) or not source.is_file() or source.is_symlink():
                raise ValueError("selected experiment output is missing or unsafe")
            destination = artifact_dir / source.name
            if destination in destinations:
                raise ValueError(
                    "experiment selected outputs have a destination name collision"
                )
            destinations.add(destination)
            data = source.read_bytes()
            if destination.exists() and destination.read_bytes() != data:
                raise ValueError("experiment finalized output name collision")
            planned_outputs.append(
                (
                    destination,
                    data,
                    {
                        "path": destination.relative_to(
                            self.project_root
                        ).as_posix(),
                        "sha256": sha256_bytes(data),
                    },
                )
            )
        outputs: list[dict[str, str]] = []
        for destination, data, output in planned_outputs:
            self._write_once(destination, data)
            outputs.append(
                {
                    "path": output["path"],
                    "sha256": output["sha256"],
                }
            )
        experiment_prefix = _ledger_prefix(directory / "events.jsonl")
        governance_prefix = _ledger_prefix(
            self._governance_events_path(task_card)
        )
        checkpoint_inventory = self._checkpoint_inventory(
            directory, self._hard_caps(task_card)
        )
        hard_caps = self._hard_caps(task_card)
        semantic = {
            "schema_version": 3 if hard_caps is not None else 2,
            "policy_revision": POLICY_REVISION_V4,
            "experiment_id": experiment_id,
            "assignment_id": manifest["assignment_id"],
            "selected_outputs": sorted(outputs, key=lambda item: item["path"]),
            "manifest_sha256": sha256_bytes(
                (directory / "manifest.json").read_bytes()
            ),
            "experiment_event_count": experiment_prefix["event_count"],
            "experiment_events_sha256": experiment_prefix["sha256"],
            "governance_task_id": governance["governance_task_id"],
            "governance_state": governance["state"],
            "governance_event_count": governance_prefix["event_count"],
            "governance_events_sha256": governance_prefix["sha256"],
            **(
                {
                    "hard_caps_sha256": sha256_json(hard_caps),
                    "checkpoint_file_count": checkpoint_inventory["file_count"],
                    "checkpoint_bytes_total": checkpoint_inventory["bytes_total"],
                    "checkpoint_inventory_sha256": checkpoint_inventory["sha256"],
                }
                if hard_caps is not None
                else {}
            ),
        }
        receipt = {
            **semantic,
            "receipt_sha256": sha256_json(semantic),
        }
        finalized_semantic = {
            "schema_version": 1,
            "policy_revision": POLICY_REVISION_V4,
            "event": "finalized",
            "receipt_sha256": receipt["receipt_sha256"],
        }
        finalized_event = {
            **finalized_semantic,
            "event_id": sha256_json(finalized_semantic),
        }
        final_ledger = ExperimentEventLedger(
            directory / "events.jsonl",
            hard_caps=self._hard_caps(task_card),
        )
        final_ledger.mutate(
            lambda session: (
                None
                if session.find(finalized_event["event_id"]) is not None
                else session.preflight(finalized_event)
            )
        )
        self._write_json_once(receipt_path, receipt)

        def append_finalized(session: Any) -> None:
            latest = session.latest()
            if (
                latest is not None
                and latest.get("event") == "finalized"
                and latest.get("receipt_sha256")
                == receipt["receipt_sha256"]
            ):
                return
            session.append(finalized_event)

        final_ledger.mutate(append_finalized)
        return validate_experiment_final_receipt(
            project_root=self.project_root,
            task_card=task_card,
            receipt_path=receipt_path,
        )


def validate_experiment_final_receipt(
    *,
    project_root: Path,
    task_card: dict[str, Any],
    receipt_path: Path,
    artifacts: list[dict[str, str]] | None = None,
    require_terminal_event: bool = True,
) -> dict[str, Any]:
    """Validate a frozen experiment receipt, its manifest, and selected bytes."""

    validate_task_card(task_card, allow_legacy_adoption=True)
    project_root = Path(project_root).resolve()
    supplied_receipt_path = Path(receipt_path)
    if supplied_receipt_path.is_symlink():
        raise ValueError("experiment final receipt path is missing or unsafe")
    receipt_path = supplied_receipt_path.resolve()
    if (
        not receipt_path.is_relative_to(project_root)
        or receipt_path.name != "final_receipt.json"
        or not receipt_path.is_file()
        or receipt_path.is_symlink()
    ):
        raise ValueError("experiment final receipt path is missing or unsafe")
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("experiment final receipt must be one object")
    receipt_version = payload.get("schema_version")
    common_fields = {
        "schema_version",
        "policy_revision",
        "experiment_id",
        "assignment_id",
        "selected_outputs",
        "manifest_sha256",
        "receipt_sha256",
    }
    if receipt_version == 1:
        required_fields = common_fields
    elif receipt_version in {2, 3}:
        required_fields = common_fields | {
            "experiment_event_count",
            "experiment_events_sha256",
            "governance_task_id",
            "governance_state",
            "governance_event_count",
            "governance_events_sha256",
        }
        if receipt_version == 3:
            required_fields |= {
                "hard_caps_sha256",
                "checkpoint_file_count",
                "checkpoint_bytes_total",
                "checkpoint_inventory_sha256",
            }
    else:
        raise ValueError(
            "experiment final receipt schema_version must be 1, 2, or 3"
        )
    require_exact_keys(
        payload,
        required=required_fields,
        label="experiment final receipt",
    )
    if payload["policy_revision"] != POLICY_REVISION_V4:
        raise ValueError("experiment final receipt policy_revision mismatch")
    experiment_id = validate_experiment_id(
        require_string(payload, "experiment_id")
    )
    if receipt_path.parent.name != experiment_id:
        raise ValueError("experiment final receipt directory/id mismatch")
    if payload["assignment_id"] != task_card["assignment_id"]:
        raise ValueError("experiment final receipt assignment mismatch")

    manifest_path = receipt_path.parent / "manifest.json"
    if (
        not manifest_path.is_file()
        or manifest_path.is_symlink()
        or require_string(payload, "manifest_sha256")
        != sha256_bytes(manifest_path.read_bytes())
    ):
        raise ValueError("experiment final receipt manifest hash mismatch")
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest_payload, dict):
        raise ValueError("experiment manifest must be one object")
    manifest = ExperimentManager.validate_manifest(
        manifest_payload,
        assignment_id=task_card["assignment_id"],
    )
    if manifest["experiment_id"] != experiment_id:
        raise ValueError("experiment final receipt references another manifest")
    if receipt_version in {2, 3}:
        manager = ExperimentManager(project_root)
        if receipt_version == 3:
            hard_caps = manager._hard_caps(task_card)
            if (
                hard_caps is None
                or payload.get("hard_caps_sha256") != sha256_json(hard_caps)
            ):
                raise ValueError("experiment final receipt hard-cap binding mismatch")
            inventory = manager._checkpoint_inventory(
                receipt_path.parent, hard_caps
            )
            if (
                payload.get("checkpoint_file_count") != inventory["file_count"]
                or payload.get("checkpoint_bytes_total") != inventory["bytes_total"]
                or payload.get("checkpoint_inventory_sha256") != inventory["sha256"]
            ):
                raise ValueError(
                    "experiment final receipt checkpoint inventory mismatch"
                )
        governance_task_id = manager.governance_task_id(task_card)
        if payload.get("governance_task_id") != governance_task_id:
            raise ValueError(
                "experiment final receipt governance task binding mismatch"
            )
        if payload.get("governance_state") not in {
            "pre_threshold",
            "notice_issued",
            "acknowledged",
            "continued",
        }:
            raise ValueError(
                "experiment final receipt has an unsupported governance state"
            )
        for count_key in (
            "experiment_event_count",
            "governance_event_count",
        ):
            count = payload.get(count_key)
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValueError(
                    f"experiment final receipt {count_key} is invalid"
                )
        experiment_prefix = _ledger_prefix(
            receipt_path.parent / "events.jsonl",
            payload["experiment_event_count"],
        )
        if (
            require_string(payload, "experiment_events_sha256")
            != experiment_prefix["sha256"]
        ):
            raise ValueError(
                "experiment final receipt event-ledger prefix mismatch"
            )
        if require_terminal_event:
            experiment_events = ExperimentManager._read_jsonl(
                receipt_path.parent / "events.jsonl"
            )
            if (
                len(experiment_events)
                != payload["experiment_event_count"] + 1
                or experiment_events[-1].get("event") != "finalized"
                or experiment_events[-1].get("receipt_sha256")
                != payload["receipt_sha256"]
            ):
                raise ValueError(
                    "experiment final receipt lacks its unique terminal event"
                )
        governance_prefix = _ledger_prefix(
            manager._governance_events_path(task_card),
            payload["governance_event_count"],
        )
        if (
            require_string(payload, "governance_events_sha256")
            != governance_prefix["sha256"]
        ):
            raise ValueError(
                "experiment final receipt governance-ledger prefix mismatch"
            )
        manager._governance_state(task_card)

    outputs = payload.get("selected_outputs")
    if (
        not isinstance(outputs, list)
        or not outputs
        or any(not isinstance(item, dict) for item in outputs)
    ):
        raise ValueError(
            "experiment final receipt selected_outputs must be nonempty"
        )
    artifact_dir = contained_path(
        project_root,
        task_card["artifact_dir_relpath"],
        "task card artifact directory",
    )
    normalized_outputs: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in outputs:
        require_exact_keys(
            item,
            required={"path", "sha256"},
            label="experiment selected output",
        )
        output_path = require_string(item, "path")
        output_hash = require_string(item, "sha256")
        if SHA256_RE.fullmatch(output_hash) is None:
            raise ValueError("experiment selected output hash is invalid")
        relative_output = require_relative_path(
            output_path,
            "experiment selected output path",
        )
        supplied_output_file = project_root.joinpath(*relative_output.parts)
        if supplied_output_file.is_symlink():
            raise ValueError(
                "experiment selected output is outside the artifact directory "
                "or its bytes do not match"
            )
        output_file = contained_path(
            project_root,
            output_path,
            "experiment selected output path",
        )
        if (
            not output_file.is_relative_to(artifact_dir)
            or not output_file.is_file()
            or output_file.is_symlink()
            or sha256_bytes(output_file.read_bytes()) != output_hash
        ):
            raise ValueError(
                "experiment selected output is outside the artifact directory "
                "or its bytes do not match"
            )
        pair = (output_path, output_hash)
        if pair in seen:
            raise ValueError("experiment final receipt repeats a selected output")
        seen.add(pair)
        normalized_outputs.append({"path": output_path, "sha256": output_hash})
    if normalized_outputs != sorted(
        normalized_outputs,
        key=lambda item: item["path"],
    ):
        raise ValueError("experiment selected outputs must be stably ordered")

    semantic = {
        key: value
        for key, value in payload.items()
        if key != "receipt_sha256"
    }
    receipt_hash = require_string(payload, "receipt_sha256")
    if (
        SHA256_RE.fullmatch(receipt_hash) is None
        or receipt_hash != sha256_json(semantic)
    ):
        raise ValueError("experiment final receipt hash mismatch")
    if artifacts is not None:
        artifact_manifest = {
            (item["path"], item["sha256"]) for item in artifacts
        }
        if not seen.issubset(artifact_manifest):
            raise ValueError(
                "experiment selected outputs are not all declared artifacts"
            )
    return payload


def validate_required_experiment_receipt(
    *,
    project_root: Path,
    task_card: dict[str, Any],
    artifacts: list[dict[str, str]],
) -> None:
    """Require a valid finalized experiment whenever the bound adoption plan does."""

    if uses_legacy_estimate_policy(task_card["adoption_plan"]):
        raise ValueError(
            "historical estimate-gated adoption binding is read-only; "
            "replan under current policy"
        )
    if not feature_required(
        task_card["adoption_plan"],
        "experiment_checkpoint",
    ):
        return
    work_dir = contained_path(
        project_root,
        task_card["work_dir_relpath"],
        "task card work directory",
    )
    receipts = sorted(
        (work_dir / "experiments").glob("experiment-*/final_receipt.json")
    )
    if not receipts:
        raise ValueError(
            "adoption plan requires a finalized experiment receipt"
        )
    valid = 0
    for path in receipts:
        try:
            validate_experiment_final_receipt(
                project_root=project_root,
                task_card=task_card,
                receipt_path=path,
                artifacts=artifacts,
            )
            valid += 1
        except (
            json.JSONDecodeError,
            KeyError,
            OSError,
            TypeError,
            ValueError,
        ):
            continue
    if valid < 1:
        raise ValueError(
            "adoption plan requires a valid finalized experiment receipt "
            "whose selected outputs are declared artifacts"
        )

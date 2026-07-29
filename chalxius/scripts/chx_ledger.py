#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence


SCHEMA_VERSION = 1
LEGACY_CONTRACT_REVISION = "chalxius-chx-run-ledger-1"
CONTRACT_REVISION = "chalxius-chx-run-ledger-2"
SUPPORTED_CONTRACT_REVISIONS = frozenset(
    {LEGACY_CONTRACT_REVISION, CONTRACT_REVISION}
)
DEFAULT_PROJECT_LEDGER_DIR = "chx-ledgers"
CAUSATIONS = frozenset({"caused", "materially_amplified"})
MECHANISM_TYPES = frozenset(
    {
        "state_model",
        "coupling",
        "automatic_trigger",
        "validation_boundary",
        "recovery_rule",
        "authority_boundary",
        "interface_contract",
    }
)
DISPOSITION_STATUSES = frozenset({"resolved", "excluded_nonarchitectural"})
RUN_ID_RE = re.compile(r"run-[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
ISSUE_ID_RE = re.compile(r"CHX-[0-9]{3,}")
SHA256_RE = re.compile(r"[0-9a-f]{64}")


def _canonical_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _event_sha256(event: dict[str, Any]) -> str:
    return _sha256(
        _canonical_bytes(
            {key: value for key, value in event.items() if key != "event_sha256"}
        )
    )


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _require_text(value: Any, label: str, *, maximum: int = 8_192) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be nonempty text")
    if len(value) > maximum:
        raise ValueError(f"{label} exceeds {maximum} code points")
    return value


def _require_string_list(
    value: Any,
    label: str,
    *,
    nonempty: bool,
) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(f"{label} must be a list of nonempty strings")
    if nonempty and not value:
        raise ValueError(f"{label} must contain at least one entry")
    if len(value) > 128:
        raise ValueError(f"{label} exceeds 128 entries")
    return list(value)


def _skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _skill_version() -> str:
    version = (_skill_root() / "VERSION").read_text(encoding="utf-8").strip()
    return _require_text(version, "skill version", maximum=64)


def _runtime_binding() -> dict[str, Any]:
    root = _skill_root()
    version_path = root / "VERSION"
    manifest_path = root / "MANIFEST.sha256"
    if (
        version_path.is_symlink()
        or not version_path.is_file()
        or manifest_path.is_symlink()
        or not manifest_path.is_file()
    ):
        raise ValueError("Chalxius runtime identity files are missing or unsafe")
    semantic = {
        "schema_version": 1,
        "skill_root": str(root),
        "skill_version": _skill_version(),
        "version_file_sha256": _sha256(version_path.read_bytes()),
        "manifest_file_sha256": _sha256(manifest_path.read_bytes()),
        "worker_ledger_contract": "exact_task_card_runtime_binding_required",
    }
    return {
        **semantic,
        "runtime_identity_sha256": _sha256(_canonical_bytes(semantic)),
    }


def _validate_task_card_runtime(task_card: Path | str) -> dict[str, Any]:
    path = _resolved_path(task_card)
    if path.is_symlink() or not path.is_file():
        raise ValueError("CHX worker task card is missing, unsafe, or not a file")
    card = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(card, dict):
        raise ValueError("CHX worker task card must contain one object")
    runtime = card.get("runtime_binding")
    if runtime != _runtime_binding():
        raise ValueError(
            "CHX worker runtime does not match the task-card candidate skill root/version"
        )
    semantic = {
        key: value
        for key, value in card.items()
        if key != "task_card_semantic_sha256"
    }
    if card.get("task_card_semantic_sha256") != _sha256(
        _canonical_bytes(semantic)
    ):
        raise ValueError("CHX worker task-card semantic hash mismatch")
    return card


def _resolved_path(path: Path | str) -> Path:
    requested = Path(path).expanduser()
    if requested.is_symlink():
        raise ValueError("CHX paths must not be symlinks")
    return requested.resolve(strict=False)


def _assert_outside_skill(path: Path) -> None:
    root = _skill_root()
    if path == root or root in path.parents:
        raise ValueError("the CHX ledger root must be outside the skill")


def _assert_outside_projects(path: Path, project_roots: Sequence[Path | str]) -> None:
    for project_root_value in project_roots:
        project_root = _resolved_path(project_root_value)
        if path == project_root or project_root in path.parents:
            raise ValueError(
                "the CHX ledger root must be outside every Chalxius project"
            )


def _new_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"run-{stamp}-{secrets.token_hex(6)}"


def _validate_run_id(run_id: Any) -> str:
    if not isinstance(run_id, str) or RUN_ID_RE.fullmatch(run_id) is None:
        raise ValueError("run_id is invalid")
    return run_id


def _with_hash(payload: dict[str, Any], previous: str) -> dict[str, Any]:
    record = {**payload, "previous_event_sha256": previous}
    return {**record, "event_sha256": _event_sha256(record)}


def _write_new_ledger(path: Path, event: dict[str, Any]) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(_canonical_bytes(event) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            path.unlink(missing_ok=True)
        finally:
            raise


def _parse_events(raw: str, *, ledger_path: Path) -> list[dict[str, Any]]:
    if not raw or not raw.endswith("\n"):
        raise ValueError("CHX ledger is empty or lacks a complete final line")
    events: list[dict[str, Any]] = []
    for number, line in enumerate(raw.splitlines(), 1):
        if not line:
            raise ValueError(f"CHX ledger line {number} is blank")
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"CHX ledger line {number} is invalid JSON") from exc
        if not isinstance(event, dict):
            raise ValueError(f"CHX ledger line {number} must be an object")
        events.append(event)
    _validate_events(events, ledger_path=ledger_path)
    return events


def _validate_common_event(
    event: dict[str, Any],
    *,
    expected_previous: str,
    run_id: str,
    schema_version: int,
    contract_revision: str,
) -> None:
    if event.get("schema_version") != schema_version:
        raise ValueError("CHX ledger schema version mismatch")
    if event.get("contract_revision") != contract_revision:
        raise ValueError("CHX ledger contract revision mismatch")
    if event.get("run_id") != run_id:
        raise ValueError("CHX ledger run binding mismatch")
    _require_text(event.get("occurred_at"), "event occurred_at", maximum=64)
    if event.get("previous_event_sha256") != expected_previous:
        raise ValueError("CHX ledger hash-chain predecessor mismatch")
    event_hash = event.get("event_sha256")
    if not isinstance(event_hash, str) or SHA256_RE.fullmatch(event_hash) is None:
        raise ValueError("CHX ledger event hash is invalid")
    if event_hash != _event_sha256(event):
        raise ValueError("CHX ledger event hash mismatch")


def _validate_issue_fields(event: dict[str, Any]) -> None:
    if event.get("causation") not in CAUSATIONS:
        raise ValueError("CHX issue causation is invalid")
    if event.get("mechanism_type") not in MECHANISM_TYPES:
        raise ValueError("CHX issue mechanism_type is invalid")
    for field_name in (
        "classification",
        "mechanism",
        "trigger",
        "observed_effect",
        "mathematical_effect",
        "current_workaround",
        "upgrade_requirement",
    ):
        _require_text(event.get(field_name), f"CHX issue {field_name}")
    _require_string_list(
        event.get("audit_anchors"),
        "CHX issue audit_anchors",
        nonempty=True,
    )


def _validate_events(events: list[dict[str, Any]], *, ledger_path: Path) -> None:
    if not events or events[0].get("event") != "run_started":
        raise ValueError("CHX ledger must begin with run_started")
    start = events[0]
    run_id = _validate_run_id(start.get("run_id"))
    schema_version = start.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        raise ValueError("CHX ledger schema version mismatch")
    contract_revision = start.get("contract_revision")
    if contract_revision not in SUPPORTED_CONTRACT_REVISIONS:
        raise ValueError("CHX ledger contract revision mismatch")
    if ledger_path.stem != run_id:
        raise ValueError("CHX ledger path/run id mismatch")
    start_keys = {
        "schema_version",
        "contract_revision",
        "event",
        "run_id",
        "task",
        "skill_version",
        "host_task_scope_id",
        "prospective_only",
        "truth_effect",
        "project_effect",
        "occurred_at",
        "previous_event_sha256",
        "event_sha256",
    }
    if set(start) != start_keys:
        raise ValueError("CHX run_started fields are not exact")
    _require_text(start.get("task"), "CHX run task", maximum=2_000)
    _require_text(start.get("skill_version"), "CHX run skill_version", maximum=64)
    if not isinstance(start.get("host_task_scope_id"), str):
        raise ValueError("CHX run host_task_scope_id must be text")
    if (
        start.get("prospective_only") is not True
        or start.get("truth_effect") != "none"
        or start.get("project_effect") != "none"
    ):
        raise ValueError("CHX run authority boundary is invalid")

    expected_previous = ""
    observed: dict[str, dict[str, Any]] = {}
    dispositions: dict[str, dict[str, Any]] = {}
    closed = False
    for index, event in enumerate(events):
        _validate_common_event(
            event,
            expected_previous=expected_previous,
            run_id=run_id,
            schema_version=schema_version,
            contract_revision=contract_revision,
        )
        expected_previous = event["event_sha256"]
        event_type = event.get("event")
        if index == 0:
            continue
        if closed:
            raise ValueError("CHX ledger contains an event after run_closed")
        if event_type == "issue_observed":
            issue_keys = {
                "schema_version",
                "contract_revision",
                "event",
                "run_id",
                "issue_id",
                "classification",
                "causation",
                "mechanism_type",
                "mechanism",
                "trigger",
                "observed_effect",
                "mathematical_effect",
                "current_workaround",
                "upgrade_requirement",
                "audit_anchors",
                "occurred_at",
                "previous_event_sha256",
                "event_sha256",
            }
            if set(event) != issue_keys:
                raise ValueError("CHX issue_observed fields are not exact")
            issue_id = event.get("issue_id")
            if not isinstance(issue_id, str) or ISSUE_ID_RE.fullmatch(issue_id) is None:
                raise ValueError("CHX issue id is invalid")
            expected_issue_id = f"CHX-{len(observed) + 1:03d}"
            if issue_id != expected_issue_id or issue_id in observed:
                raise ValueError("CHX issue sequence is invalid")
            _validate_issue_fields(event)
            observed[issue_id] = event
        elif event_type == "issue_disposition":
            disposition_keys = {
                "schema_version",
                "contract_revision",
                "event",
                "run_id",
                "issue_id",
                "status",
                "reason",
                "regression_evidence",
                "occurred_at",
                "previous_event_sha256",
                "event_sha256",
            }
            if set(event) != disposition_keys:
                raise ValueError("CHX issue_disposition fields are not exact")
            issue_id = event.get("issue_id")
            if issue_id not in observed:
                raise ValueError("CHX disposition targets an unknown issue")
            if issue_id in dispositions:
                raise ValueError("CHX issue already has a disposition")
            if event.get("status") not in DISPOSITION_STATUSES:
                raise ValueError("CHX disposition status is invalid")
            _require_text(event.get("reason"), "CHX disposition reason")
            evidence = _require_string_list(
                event.get("regression_evidence"),
                "CHX disposition regression_evidence",
                nonempty=False,
            )
            if event.get("status") == "resolved" and not evidence:
                raise ValueError(
                    "resolved CHX issue requires regression evidence"
                )
            dispositions[issue_id] = event
        elif event_type == "run_closed":
            close_keys = {
                "schema_version",
                "contract_revision",
                "event",
                "run_id",
                "included_issue_ids",
                "excluded_issue_ids",
                "report_required",
                "occurred_at",
                "previous_event_sha256",
                "event_sha256",
            }
            if set(event) != close_keys:
                raise ValueError("CHX run_closed fields are not exact")
            included = sorted(
                issue_id
                for issue_id in observed
                if dispositions.get(issue_id, {}).get("status")
                != "excluded_nonarchitectural"
            )
            excluded = sorted(set(observed).difference(included))
            if (
                event.get("included_issue_ids") != included
                or event.get("excluded_issue_ids") != excluded
                or event.get("report_required") is not bool(included)
            ):
                raise ValueError("CHX run_closed summary mismatch")
            closed = True
        else:
            raise ValueError(f"unsupported CHX ledger event: {event_type!r}")


def _status_from_events(
    events: list[dict[str, Any]], *, ledger_path: Path
) -> dict[str, Any]:
    start = events[0]
    issue_events = {
        event["issue_id"]: event
        for event in events
        if event["event"] == "issue_observed"
    }
    dispositions = {
        event["issue_id"]: event
        for event in events
        if event["event"] == "issue_disposition"
    }
    issues: list[dict[str, Any]] = []
    excluded = 0
    for issue_id, event in issue_events.items():
        disposition = dispositions.get(issue_id)
        status = disposition["status"] if disposition else "open"
        if status == "excluded_nonarchitectural":
            excluded += 1
            continue
        issue = {
            key: event[key]
            for key in (
                "issue_id",
                "classification",
                "causation",
                "mechanism_type",
                "mechanism",
                "trigger",
                "observed_effect",
                "mathematical_effect",
                "current_workaround",
                "upgrade_requirement",
                "audit_anchors",
                "occurred_at",
            )
        }
        issue["status"] = status
        if disposition:
            issue["disposition_reason"] = disposition["reason"]
            issue["regression_evidence"] = disposition["regression_evidence"]
        issues.append(issue)
    return {
        "schema_version": start["schema_version"],
        "contract_revision": start["contract_revision"],
        "run_id": start["run_id"],
        "skill_version": start["skill_version"],
        "task": start["task"],
        "host_task_scope_id": start["host_task_scope_id"],
        "ledger_path": str(ledger_path),
        "state": "closed" if events[-1]["event"] == "run_closed" else "open",
        "issue_count": len(issues),
        "excluded_issue_count": excluded,
        "report_required": bool(issues),
        "issues": issues,
        "truth_effect": "none",
        "project_effect": "none",
    }


def _read_locked(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("CHX ledger path is missing, unsafe, or not a file")
    with path.open("r", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
        try:
            events = _parse_events(handle.read(), ledger_path=path)
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return events, _status_from_events(events, ledger_path=path)


def _mutate_locked(
    path: Path,
    builder: Callable[[list[dict[str, Any]]], dict[str, Any] | None],
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("CHX ledger path is missing, unsafe, or not a file")
    with path.open("r+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            events = _parse_events(handle.read(), ledger_path=path)
            payload = builder(events)
            if payload is None:
                return None, _status_from_events(events, ledger_path=path)
            event = _with_hash(payload, events[-1]["event_sha256"])
            candidate = [*events, event]
            _validate_events(candidate, ledger_path=path)
            handle.seek(0, os.SEEK_END)
            handle.write(_canonical_bytes(event).decode("utf-8") + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return event, _status_from_events(candidate, ledger_path=path)


def start_ledger(
    *,
    task: str,
    project_root: Path | str | None = None,
    root: Path | str | None = None,
    run_id: str | None = None,
    host_task_scope_id: str = "",
    project_roots: Sequence[Path | str] = (),
    task_card: Path | str | None = None,
) -> dict[str, Any]:
    if task_card is not None:
        _validate_task_card_runtime(task_card)
    if (project_root is None) == (root is None):
        raise ValueError("exactly one of project_root or root is required")
    if project_root is not None:
        project_path = _resolved_path(project_root)
        _assert_outside_skill(project_path)
        if project_path.exists() and (
            project_path.is_symlink() or not project_path.is_dir()
        ):
            raise ValueError("Chalxius project root is unsafe or not a directory")
        project_path.mkdir(parents=True, exist_ok=True)
        ledger_candidate = project_path / DEFAULT_PROJECT_LEDGER_DIR
        if ledger_candidate.is_symlink():
            raise ValueError("CHX paths must not be symlinks")
        ledger_root = ledger_candidate.resolve(strict=False)
    else:
        assert root is not None
        ledger_root = _resolved_path(root)
        _assert_outside_skill(ledger_root)
        _assert_outside_projects(ledger_root, project_roots)
    if ledger_root.exists() and (ledger_root.is_symlink() or not ledger_root.is_dir()):
        raise ValueError("CHX ledger root is unsafe or not a directory")
    ledger_root.mkdir(parents=True, exist_ok=True)
    run_id = _validate_run_id(run_id or _new_run_id())
    task = _require_text(task, "CHX run task", maximum=2_000)
    if not isinstance(host_task_scope_id, str) or len(host_task_scope_id) > 512:
        raise ValueError("host_task_scope_id must be text with at most 512 code points")
    path = ledger_root / f"{run_id}.jsonl"
    event = _with_hash(
        {
            "schema_version": SCHEMA_VERSION,
            "contract_revision": CONTRACT_REVISION,
            "event": "run_started",
            "run_id": run_id,
            "task": task,
            "skill_version": _skill_version(),
            "host_task_scope_id": host_task_scope_id,
            "prospective_only": True,
            "truth_effect": "none",
            "project_effect": "none",
            "occurred_at": _utc_now(),
        },
        "",
    )
    _write_new_ledger(path, event)
    return ledger_status(path)


def _validate_issue_input(issue: Any) -> dict[str, Any]:
    expected = {
        "classification",
        "causation",
        "mechanism_type",
        "mechanism",
        "trigger",
        "observed_effect",
        "mathematical_effect",
        "current_workaround",
        "upgrade_requirement",
        "audit_anchors",
    }
    if not isinstance(issue, dict) or set(issue) != expected:
        raise ValueError("CHX issue input fields are not exact")
    _validate_issue_fields(issue)
    return dict(issue)


def record_issue(ledger_path: Path | str, issue: dict[str, Any]) -> dict[str, Any]:
    path = _resolved_path(ledger_path)
    normalized = _validate_issue_input(issue)

    def build(events: list[dict[str, Any]]) -> dict[str, Any]:
        if events[-1]["event"] == "run_closed":
            raise ValueError("CHX ledger is closed")
        observed_count = sum(
            event["event"] == "issue_observed" for event in events
        )
        return {
            "schema_version": events[0]["schema_version"],
            "contract_revision": events[0]["contract_revision"],
            "event": "issue_observed",
            "run_id": events[0]["run_id"],
            "issue_id": f"CHX-{observed_count + 1:03d}",
            **normalized,
            "occurred_at": _utc_now(),
        }

    event, _ = _mutate_locked(path, build)
    if event is None:  # pragma: no cover - builder always returns an event
        raise RuntimeError("CHX record mutation produced no event")
    return event


def dispose_issue(
    ledger_path: Path | str,
    *,
    issue_id: str,
    disposition: dict[str, Any],
) -> dict[str, Any]:
    path = _resolved_path(ledger_path)
    if not isinstance(issue_id, str) or ISSUE_ID_RE.fullmatch(issue_id) is None:
        raise ValueError("CHX disposition issue_id is invalid")
    expected = {"status", "reason", "regression_evidence"}
    if not isinstance(disposition, dict) or set(disposition) != expected:
        raise ValueError("CHX disposition input fields are not exact")
    disposition_status = disposition.get("status")
    if disposition_status not in DISPOSITION_STATUSES:
        raise ValueError("CHX disposition status is invalid")
    reason = _require_text(disposition.get("reason"), "CHX disposition reason")
    evidence = _require_string_list(
        disposition.get("regression_evidence"),
        "CHX disposition regression_evidence",
        nonempty=False,
    )
    if disposition_status == "resolved" and not evidence:
        raise ValueError("resolved CHX issue requires regression evidence")
    def build(events: list[dict[str, Any]]) -> dict[str, Any]:
        if events[-1]["event"] == "run_closed":
            raise ValueError("CHX ledger is closed")
        known = {
            event["issue_id"]
            for event in events
            if event["event"] == "issue_observed"
        }
        disposed = {
            event["issue_id"]
            for event in events
            if event["event"] == "issue_disposition"
        }
        if issue_id not in known:
            raise ValueError("CHX disposition targets an unknown issue")
        if issue_id in disposed:
            raise ValueError("CHX issue already has a disposition")
        return {
            "schema_version": events[0]["schema_version"],
            "contract_revision": events[0]["contract_revision"],
            "event": "issue_disposition",
            "run_id": events[0]["run_id"],
            "issue_id": issue_id,
            "status": disposition_status,
            "reason": reason,
            "regression_evidence": evidence,
            "occurred_at": _utc_now(),
        }

    event, _ = _mutate_locked(path, build)
    if event is None:  # pragma: no cover - builder always returns an event
        raise RuntimeError("CHX disposition mutation produced no event")
    return event


def close_ledger(ledger_path: Path | str) -> dict[str, Any]:
    path = _resolved_path(ledger_path)

    def build(events: list[dict[str, Any]]) -> dict[str, Any] | None:
        if events[-1]["event"] == "run_closed":
            return None
        observed_ids = {
            event["issue_id"]
            for event in events
            if event["event"] == "issue_observed"
        }
        excluded_ids = {
            event["issue_id"]
            for event in events
            if event["event"] == "issue_disposition"
            and event["status"] == "excluded_nonarchitectural"
        }
        included_ids = observed_ids.difference(excluded_ids)
        return {
            "schema_version": events[0]["schema_version"],
            "contract_revision": events[0]["contract_revision"],
            "event": "run_closed",
            "run_id": events[0]["run_id"],
            "included_issue_ids": sorted(included_ids),
            "excluded_issue_ids": sorted(excluded_ids),
            "report_required": bool(included_ids),
            "occurred_at": _utc_now(),
        }

    _, status = _mutate_locked(path, build)
    return status


def ledger_status(ledger_path: Path | str) -> dict[str, Any]:
    path = _resolved_path(ledger_path)
    _, status = _read_locked(path)
    return status


def _json_file(path_value: str) -> dict[str, Any]:
    path = _resolved_path(path_value)
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"input JSON is missing, unsafe, or not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("input JSON must contain one object")
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Operate a task-scoped CHX ledger.")
    commands = parser.add_subparsers(dest="command", required=True)

    start = commands.add_parser("start")
    placement = start.add_mutually_exclusive_group(required=True)
    placement.add_argument("--project-root")
    placement.add_argument("--root")
    start.add_argument("--task", required=True)
    start.add_argument("--run-id")
    start.add_argument("--host-task-scope-id", default="")
    start.add_argument(
        "--task-card",
        help=(
            "for a worker run, fail closed unless this exact task card binds "
            "the current candidate skill root and version"
        ),
    )

    record = commands.add_parser("record")
    record.add_argument("--ledger", required=True)
    record.add_argument("--input", required=True)

    dispose = commands.add_parser("dispose")
    dispose.add_argument("--ledger", required=True)
    dispose.add_argument("--issue-id", required=True)
    dispose.add_argument("--input", required=True)

    status = commands.add_parser("status")
    status.add_argument("--ledger", required=True)

    close = commands.add_parser("close")
    close.add_argument("--ledger", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "start":
        result = start_ledger(
            root=args.root,
            project_root=args.project_root,
            task=args.task,
            run_id=args.run_id,
            host_task_scope_id=args.host_task_scope_id,
            task_card=args.task_card,
        )
    elif args.command == "record":
        result = record_issue(args.ledger, _json_file(args.input))
    elif args.command == "dispose":
        result = dispose_issue(
            args.ledger,
            issue_id=args.issue_id,
            disposition=_json_file(args.input),
        )
    elif args.command == "status":
        result = ledger_status(args.ledger)
    else:
        result = close_ledger(args.ledger)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"CHX_LEDGER_ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)

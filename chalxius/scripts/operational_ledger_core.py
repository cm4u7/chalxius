"""Shared byte-exact mechanics for nontruth operational ledgers.

Domain schemas belong to their CHX or PHX adapters.  This module owns only
canonical bytes, hash chaining, locked reads, atomic creation, and append/fsync.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import secrets
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def require_text(value: Any, label: str, *, maximum: int = 8192) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be nonempty text")
    if len(value) > maximum:
        raise ValueError(f"{label} exceeds {maximum} code points")
    return value


def canonical_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def normalize_unicode(value: Any) -> Any:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [normalize_unicode(item) for item in value]
    if isinstance(value, dict):
        return {
            normalize_unicode(key): normalize_unicode(item)
            for key, item in value.items()
        }
    return value


def canonical_nfc_bytes(payload: Any) -> bytes:
    return canonical_bytes(normalize_unicode(payload))


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def event_sha256(event: dict[str, Any]) -> str:
    return sha256(
        canonical_bytes(
            {key: value for key, value in event.items() if key != "event_sha256"}
        )
    )


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def new_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"run-{stamp}-{secrets.token_hex(6)}"


def with_hash(payload: dict[str, Any], previous: str) -> dict[str, Any]:
    record = {**payload, "previous_event_sha256": previous}
    return {**record, "event_sha256": event_sha256(record)}


def write_new_ledger_events(path: Path, events: list[dict[str, Any]]) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            for event in events:
                handle.write(canonical_bytes(event) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            path.unlink(missing_ok=True)
        finally:
            raise


Parser = Callable[[str, Path], list[dict[str, Any]]]
StatusBuilder = Callable[[list[dict[str, Any]], Path], dict[str, Any]]


def read_locked(
    path: Path,
    *,
    label: str,
    parser: Parser,
    status_builder: StatusBuilder,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{label} ledger path is missing, unsafe, or not a file")
    with path.open("r", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
        try:
            events = parser(handle.read(), path)
            status = status_builder(events, path)
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return events, status


def mutate_locked(
    path: Path,
    *,
    label: str,
    parser: Parser,
    status_builder: StatusBuilder,
    builder: Callable[
        [list[dict[str, Any]]],
        dict[str, Any] | None,
    ],
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{label} ledger path is missing, unsafe, or not a file")
    with path.open("r+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            events = parser(handle.read(), path)
            payload = builder(events)
            if payload is None:
                return None, status_builder(events, path)
            event = with_hash(payload, events[-1]["event_sha256"])
            candidate = [*events, event]
            # The adapter parser is the authoritative complete validator.
            parser(
                "".join(
                    canonical_bytes(item).decode("utf-8") + "\n"
                    for item in candidate
                ),
                path,
            )
            handle.seek(0, os.SEEK_END)
            handle.write(canonical_bytes(event).decode("utf-8") + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            status = status_builder(candidate, path)
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return event, status

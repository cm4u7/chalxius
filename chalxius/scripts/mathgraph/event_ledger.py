from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Callable, TypeVar

from .contracts import sha256_json


INDEX_SCHEMA_VERSION = 2
INDEX_FILENAME = "events.index.sqlite3"

_T = TypeVar("_T")


class _IndexInvalid(RuntimeError):
    """Internal signal that the derived index must be rebuilt."""


class ExperimentEventIndexSession:
    def __init__(
        self,
        owner: "ExperimentEventLedger",
        connection: sqlite3.Connection,
        *,
        indexed_size: int,
        event_count: int,
    ) -> None:
        self.owner = owner
        self.connection = connection
        self.indexed_size = indexed_size
        self.event_count = event_count

    def _payload_for_row(self, row: sqlite3.Row) -> dict[str, Any]:
        line, payload = self.owner._read_payload_at(
            byte_offset=int(row["byte_offset"]),
            byte_length=int(row["byte_length"]),
        )
        if hashlib.sha256(line).digest() != row["line_sha256"]:
            raise _IndexInvalid("event index points to changed canonical bytes")
        self.owner._validate_event_id(payload)
        indexed_event_key = row["event_key"]
        if (
            indexed_event_key is not None
            and self.owner._event_key(payload.get("event_id"))
            != indexed_event_key
        ):
            raise _IndexInvalid("event-id index points to different canonical bytes")
        return payload

    def find(self, event_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            """
            SELECT ordinal, event_key, byte_offset, byte_length, line_sha256
            FROM events
            WHERE event_key = ?
            ORDER BY ordinal
            LIMIT 1
            """,
            (self.owner._event_key(event_id),),
        ).fetchone()
        if row is None:
            return None
        return self._payload_for_row(row)

    def latest(self) -> dict[str, Any] | None:
        row = self.connection.execute(
            """
            SELECT ordinal, event_key, byte_offset, byte_length, line_sha256
            FROM events
            ORDER BY ordinal DESC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            return None
        return self._payload_for_row(row)

    def has_stage_completed(self, stage: str) -> bool:
        rows = self.connection.execute(
            """
            SELECT
                events.ordinal,
                events.event_key,
                events.byte_offset,
                events.byte_length,
                events.line_sha256
            FROM completed_stages
            JOIN events USING(ordinal)
            WHERE completed_stages.stage = ?
            ORDER BY events.ordinal
            """,
            (stage,),
        )
        for row in rows:
            payload = self._payload_for_row(row)
            if (
                payload.get("event") == "stage_completed"
                and payload.get("stage") == stage
            ):
                return True
        return False

    def append(self, payload: dict[str, Any]) -> None:
        line = self.owner._encode_line(payload)
        self.owner._preflight_append(
            self.connection,
            payload=payload,
            line_length=len(line),
            event_count=self.event_count,
            indexed_size=self.indexed_size,
        )
        descriptor = self.owner._open_log_for_append()
        try:
            before = os.fstat(descriptor)
            if before.st_size != self.indexed_size:
                raise _IndexInvalid(
                    "canonical event log changed after index synchronization"
                )
            with os.fdopen(descriptor, "ab", closefd=True) as handle:
                descriptor = -1
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())
            after = self.owner.events_path.stat()
            ordinal = self.event_count + 1
            self.connection.execute("BEGIN IMMEDIATE")
            self.owner._insert_event(
                self.connection,
                ordinal=ordinal,
                byte_offset=self.indexed_size,
                byte_length=len(line),
                line=line,
                payload=payload,
            )
            self.indexed_size += len(line)
            self.event_count = ordinal
            self.owner._write_metadata(
                self.connection,
                stat_result=after,
                indexed_size=self.indexed_size,
                event_count=self.event_count,
            )
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    def preflight(self, payload: dict[str, Any]) -> None:
        line = self.owner._encode_line(payload)
        self.owner._preflight_append(
            self.connection,
            payload=payload,
            line_length=len(line),
            event_count=self.event_count,
            indexed_size=self.indexed_size,
        )


class ExperimentEventLedger:
    """Canonical JSONL event log with a rebuildable SQLite lookup cache."""

    def __init__(
        self,
        events_path: Path | str,
        *,
        hard_caps: dict[str, int] | None = None,
    ) -> None:
        supplied = Path(events_path)
        if not supplied.is_absolute():
            supplied = Path.cwd() / supplied
        self.events_path = supplied
        self.index_path = self.events_path.parent / INDEX_FILENAME
        self.hard_caps = hard_caps

    def _preflight_append(
        self,
        connection: sqlite3.Connection,
        *,
        payload: dict[str, Any],
        line_length: int,
        event_count: int,
        indexed_size: int,
    ) -> None:
        if self.hard_caps is None:
            return
        each = self.hard_caps["max_experiment_event_bytes_each"]
        total = self.hard_caps["max_experiment_event_bytes_total"]
        count = self.hard_caps["max_experiment_event_count_total"]
        if line_length > each:
            raise ValueError("experiment event exceeds per-event hard cap")
        if indexed_size + line_length > total:
            raise ValueError("experiment event ledger exceeds total-byte hard cap")
        if event_count + 1 > count:
            raise ValueError("experiment event ledger exceeds count hard cap")
        if payload.get("event") in {
            "heartbeat",
            "stage_started",
            "stage_completed",
        }:
            worker_count = int(
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM events
                    WHERE event_type IN (
                        'heartbeat', 'stage_started', 'stage_completed'
                    )
                    """
                ).fetchone()[0]
            )
            if (
                worker_count + 1
                > self.hard_caps["max_experiment_worker_event_count"]
            ):
                raise ValueError("experiment worker events exceed hard cap")

    @staticmethod
    def _encode_line(payload: dict[str, Any]) -> bytes:
        return (
            json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"
        ).encode("utf-8")

    def audit_read_only(self) -> dict[str, Any]:
        """Validate canonical JSONL and hard caps without touching the index."""
        errors: list[str] = []
        events: list[dict[str, Any]] = []
        total_bytes = 0
        worker_count = 0
        seen: set[str] = set()
        if not self.events_path.is_file() or self.events_path.is_symlink():
            errors.append("canonical event log is missing or unsafe")
        else:
            with self.events_path.open("rb") as handle:
                for number, line in enumerate(handle, 1):
                    total_bytes += len(line)
                    if not line.endswith(b"\n"):
                        errors.append(f"event line {number} lacks final newline")
                        continue
                    try:
                        payload = json.loads(line)
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        errors.append(f"event line {number} is invalid JSON")
                        continue
                    if not isinstance(payload, dict):
                        errors.append(f"event line {number} is not an object")
                        continue
                    if self._encode_line(payload) != line:
                        errors.append(f"event line {number} is not canonical")
                    try:
                        self._validate_event_id(payload)
                    except ValueError as exc:
                        errors.append(f"event line {number}: {exc}")
                    event_id = payload.get("event_id")
                    if isinstance(event_id, str):
                        if event_id in seen:
                            errors.append(f"event line {number} repeats event_id")
                        seen.add(event_id)
                    if payload.get("event") in {
                        "heartbeat", "stage_started", "stage_completed"
                    }:
                        worker_count += 1
                    if (
                        self.hard_caps
                        and len(line)
                        > self.hard_caps["max_experiment_event_bytes_each"]
                    ):
                        errors.append(f"event line {number} exceeds hard cap")
                    events.append(payload)
        if self.hard_caps:
            if len(events) > self.hard_caps["max_experiment_event_count_total"]:
                errors.append("event count exceeds hard cap")
            if worker_count > self.hard_caps["max_experiment_worker_event_count"]:
                errors.append("worker event count exceeds hard cap")
            if total_bytes > self.hard_caps["max_experiment_event_bytes_total"]:
                errors.append("event total bytes exceed hard cap")
        return {
            "current_ok": not errors,
            "errors": errors,
            "event_count": len(events),
            "worker_event_count": worker_count,
            "event_bytes_total": total_bytes,
            "events": events,
        }

    @staticmethod
    def _event_key(event_id: Any) -> bytes | str | None:
        if not isinstance(event_id, str):
            return None
        if len(event_id) == 64:
            try:
                return bytes.fromhex(event_id)
            except ValueError:
                pass
        return event_id

    @staticmethod
    def _validate_event_id(payload: dict[str, Any]) -> None:
        event_id = payload.get("event_id")
        if event_id is None:
            return
        if not isinstance(event_id, str):
            raise ValueError("experiment event id must be a string")
        semantic = dict(payload)
        semantic.pop("event_id")
        if sha256_json(semantic) != event_id:
            raise ValueError("experiment event id/hash mismatch")

    def _ensure_log(self) -> None:
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        if self.events_path.exists() or self.events_path.is_symlink():
            if (
                self.events_path.is_symlink()
                or not self.events_path.is_file()
            ):
                raise ValueError("experiment event log is not a regular file")
            return
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(self.events_path, flags, 0o600)
        os.close(descriptor)

    def _open_log_for_append(self) -> int:
        self._ensure_log()
        flags = os.O_WRONLY | os.O_APPEND
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        return os.open(self.events_path, flags)

    def _read_payload_at(
        self,
        *,
        byte_offset: int,
        byte_length: int,
    ) -> tuple[bytes, dict[str, Any]]:
        if byte_offset < 0 or byte_length <= 0:
            raise _IndexInvalid("event index contains an invalid byte range")
        self._ensure_log()
        with self.events_path.open("rb") as handle:
            handle.seek(byte_offset)
            line = handle.read(byte_length)
        if len(line) != byte_length or not line.endswith(b"\n"):
            raise _IndexInvalid("event index byte range is not a complete line")
        try:
            payload = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise _IndexInvalid("event index points to invalid JSON") from exc
        if not isinstance(payload, dict):
            raise _IndexInvalid("event index points to a non-object event")
        return line, payload

    @staticmethod
    def _connect(path: Path) -> sqlite3.Connection:
        connection = sqlite3.connect(path, timeout=0)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA journal_mode = DELETE")
            connection.execute("PRAGMA synchronous = FULL")
            return connection
        except Exception:
            connection.close()
            raise

    @staticmethod
    def _initialize_schema(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            ) WITHOUT ROWID;
            CREATE TABLE events (
                ordinal INTEGER PRIMARY KEY,
                event_key,
                event_type TEXT,
                byte_offset INTEGER NOT NULL,
                byte_length INTEGER NOT NULL,
                line_sha256 BLOB NOT NULL
            );
            CREATE INDEX events_by_id ON events(event_key);
            CREATE INDEX events_by_type ON events(event_type);
            CREATE TABLE completed_stages (
                stage TEXT NOT NULL,
                ordinal INTEGER NOT NULL,
                PRIMARY KEY(stage, ordinal),
                FOREIGN KEY(ordinal) REFERENCES events(ordinal)
            ) WITHOUT ROWID;
            CREATE TRIGGER events_no_update
            BEFORE UPDATE ON events
            BEGIN
                SELECT RAISE(ABORT, 'derived event index rows are immutable');
            END;
            CREATE TRIGGER events_no_delete
            BEFORE DELETE ON events
            BEGIN
                SELECT RAISE(ABORT, 'derived event index rows are immutable');
            END;
            CREATE TRIGGER stages_no_update
            BEFORE UPDATE ON completed_stages
            BEGIN
                SELECT RAISE(ABORT, 'derived stage index rows are immutable');
            END;
            CREATE TRIGGER stages_no_delete
            BEFORE DELETE ON completed_stages
            BEGIN
                SELECT RAISE(ABORT, 'derived stage index rows are immutable');
            END;
            """
        )

    @staticmethod
    def _metadata(connection: sqlite3.Connection) -> dict[str, str]:
        try:
            rows = connection.execute(
                "SELECT key, value FROM metadata"
            ).fetchall()
        except sqlite3.DatabaseError as exc:
            raise _IndexInvalid("event index metadata is unreadable") from exc
        return {str(row["key"]): str(row["value"]) for row in rows}

    @staticmethod
    def _insert_event(
        connection: sqlite3.Connection,
        *,
        ordinal: int,
        byte_offset: int,
        byte_length: int,
        line: bytes,
        payload: dict[str, Any],
    ) -> None:
        ExperimentEventLedger._validate_event_id(payload)
        event_id = payload.get("event_id")
        event_key = ExperimentEventLedger._event_key(event_id)
        connection.execute(
            """
            INSERT INTO events(
                ordinal,
                event_key,
                event_type,
                byte_offset,
                byte_length,
                line_sha256
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                ordinal,
                event_key,
                payload.get("event"),
                byte_offset,
                byte_length,
                hashlib.sha256(line).digest(),
            ),
        )
        if (
            payload.get("event") == "stage_completed"
            and isinstance(payload.get("stage"), str)
        ):
            connection.execute(
                "INSERT INTO completed_stages(stage, ordinal) VALUES (?, ?)",
                (payload["stage"], ordinal),
            )

    @staticmethod
    def _write_metadata(
        connection: sqlite3.Connection,
        *,
        stat_result: os.stat_result,
        indexed_size: int,
        event_count: int,
    ) -> None:
        values = {
            "schema_version": INDEX_SCHEMA_VERSION,
            "log_device": stat_result.st_dev,
            "log_inode": stat_result.st_ino,
            "log_mtime_ns": stat_result.st_mtime_ns,
            "log_ctime_ns": stat_result.st_ctime_ns,
            "indexed_size": indexed_size,
            "event_count": event_count,
        }
        connection.executemany(
            """
            INSERT INTO metadata(key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            [(key, str(value)) for key, value in values.items()],
        )

    def _scan_into(
        self,
        connection: sqlite3.Connection,
        *,
        start_offset: int,
        start_ordinal: int,
    ) -> tuple[int, int]:
        offset = start_offset
        ordinal = start_ordinal
        with self.events_path.open("rb") as handle:
            handle.seek(start_offset)
            while True:
                line = handle.readline()
                if not line:
                    break
                line_offset = offset
                offset += len(line)
                if not line.strip():
                    continue
                if not line.endswith(b"\n"):
                    raise ValueError(
                        "experiment event log ends with a partial JSON line"
                    )
                try:
                    payload = json.loads(line)
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise ValueError(
                        "experiment event log contains invalid JSON"
                    ) from exc
                if not isinstance(payload, dict):
                    raise ValueError(
                        "experiment event log contains a non-object event"
                    )
                ordinal += 1
                self._insert_event(
                    connection,
                    ordinal=ordinal,
                    byte_offset=line_offset,
                    byte_length=len(line),
                    line=line,
                    payload=payload,
                )
        return offset, ordinal

    def _remove_transient_database_files(self) -> None:
        for suffix in ("-journal", "-wal", "-shm"):
            transient = Path(str(self.index_path) + suffix)
            if transient.exists() or transient.is_symlink():
                transient.unlink()

    def _fsync_parent(self) -> None:
        flags = os.O_RDONLY
        if hasattr(os, "O_DIRECTORY"):
            flags |= os.O_DIRECTORY
        descriptor = os.open(self.index_path.parent, flags)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def rebuild(self) -> None:
        self._ensure_log()
        if self.index_path.is_symlink():
            raise ValueError("experiment event index cannot be a symlink")
        descriptor, raw_path = tempfile.mkstemp(
            prefix=".events-index-",
            suffix=".sqlite3",
            dir=self.index_path.parent,
        )
        os.close(descriptor)
        temporary_path = Path(raw_path)
        connection: sqlite3.Connection | None = None
        try:
            connection = self._connect(temporary_path)
            self._initialize_schema(connection)
            indexed_size, event_count = self._scan_into(
                connection,
                start_offset=0,
                start_ordinal=0,
            )
            stat_result = self.events_path.stat()
            if indexed_size != stat_result.st_size:
                raise ValueError(
                    "experiment event log changed during index rebuild"
                )
            self._write_metadata(
                connection,
                stat_result=stat_result,
                indexed_size=indexed_size,
                event_count=event_count,
            )
            connection.commit()
            connection.close()
            connection = None
            os.chmod(temporary_path, 0o600)
            os.replace(temporary_path, self.index_path)
            self._remove_transient_database_files()
            self._fsync_parent()
        finally:
            if connection is not None:
                connection.close()
            if temporary_path.exists() or temporary_path.is_symlink():
                temporary_path.unlink()
            for suffix in ("-journal", "-wal", "-shm"):
                transient = Path(str(temporary_path) + suffix)
                if transient.exists() or transient.is_symlink():
                    transient.unlink()

    def _open_synchronized(self) -> ExperimentEventIndexSession:
        self._ensure_log()
        if (
            not self.index_path.is_file()
            or self.index_path.is_symlink()
        ):
            raise _IndexInvalid("experiment event index is missing or unsafe")
        connection = self._connect(self.index_path)
        try:
            metadata = self._metadata(connection)
            schema_objects = {
                (str(row["type"]), str(row["name"]))
                for row in connection.execute(
                    """
                    SELECT type, name
                    FROM sqlite_master
                    WHERE name NOT LIKE 'sqlite_%'
                    """
                )
            }
            expected_schema_objects = {
                ("table", "metadata"),
                ("table", "events"),
                ("table", "completed_stages"),
                ("index", "events_by_id"),
                ("index", "events_by_type"),
                ("trigger", "events_no_update"),
                ("trigger", "events_no_delete"),
                ("trigger", "stages_no_update"),
                ("trigger", "stages_no_delete"),
            }
            if schema_objects != expected_schema_objects:
                raise _IndexInvalid(
                    "experiment event index schema objects mismatch"
                )
            required = {
                "schema_version",
                "log_device",
                "log_inode",
                "log_mtime_ns",
                "log_ctime_ns",
                "indexed_size",
                "event_count",
            }
            if set(metadata) != required:
                raise _IndexInvalid("experiment event index metadata mismatch")
            try:
                schema_version = int(metadata["schema_version"])
                log_device = int(metadata["log_device"])
                log_inode = int(metadata["log_inode"])
                log_mtime_ns = int(metadata["log_mtime_ns"])
                log_ctime_ns = int(metadata["log_ctime_ns"])
                indexed_size = int(metadata["indexed_size"])
                event_count = int(metadata["event_count"])
            except ValueError as exc:
                raise _IndexInvalid(
                    "experiment event index metadata is not numeric"
                ) from exc
            if schema_version != INDEX_SCHEMA_VERSION:
                raise _IndexInvalid("experiment event index schema mismatch")
            stat_result = self.events_path.stat()
            if (
                stat_result.st_dev != log_device
                or stat_result.st_ino != log_inode
                or stat_result.st_size < indexed_size
            ):
                raise _IndexInvalid(
                    "experiment event index does not bind the current log"
                )
            if (
                stat_result.st_size == indexed_size
                and (
                    stat_result.st_mtime_ns != log_mtime_ns
                    or stat_result.st_ctime_ns != log_ctime_ns
                )
            ):
                raise _IndexInvalid(
                    "experiment event log changed without an append"
                )
            maximum = connection.execute(
                "SELECT COALESCE(MAX(ordinal), 0) FROM events"
            ).fetchone()[0]
            if int(maximum) != event_count:
                raise _IndexInvalid("experiment event index ordinal mismatch")
            session = ExperimentEventIndexSession(
                self,
                connection,
                indexed_size=indexed_size,
                event_count=event_count,
            )
            if event_count:
                session.latest()
            if stat_result.st_size > indexed_size:
                connection.execute("BEGIN IMMEDIATE")
                indexed_size, event_count = self._scan_into(
                    connection,
                    start_offset=indexed_size,
                    start_ordinal=event_count,
                )
                stat_result = self.events_path.stat()
                if indexed_size != stat_result.st_size:
                    raise _IndexInvalid(
                        "experiment event log changed during index recovery"
                    )
                self._write_metadata(
                    connection,
                    stat_result=stat_result,
                    indexed_size=indexed_size,
                    event_count=event_count,
                )
                connection.commit()
                session.indexed_size = indexed_size
                session.event_count = event_count
            return session
        except Exception:
            connection.rollback()
            connection.close()
            raise

    def mutate(
        self,
        operation: Callable[[ExperimentEventIndexSession], _T],
    ) -> _T:
        last_error: Exception | None = None
        for attempt in range(2):
            session: ExperimentEventIndexSession | None = None
            try:
                session = self._open_synchronized()
                return operation(session)
            except (_IndexInvalid, sqlite3.DatabaseError) as exc:
                last_error = exc
                if attempt:
                    raise ValueError(
                        "experiment event index could not be recovered"
                    ) from exc
                self.rebuild()
            finally:
                if session is not None:
                    session.connection.close()
        raise ValueError("experiment event index could not be recovered") from last_error

#!/usr/bin/env python3
"""Local content-addressed literature and Paper-Graph repository."""

from __future__ import annotations

import argparse
import base64
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import stat
import sys
import tempfile
from typing import Any, Iterable
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


SCHEMA_VERSION = 1
CONTRACT_REVISION = "chalxius-paper-library-1"
EVENT_REVISION = "chalxius-paper-library-event-1"
CAPSULE_REVISION = "chalxius-paper-context-capsule-1"
EVIDENCE_ATTESTATION_REVISION = "chalxius-paper-evidence-attestation-1"
FACT_EVIDENCE_CAPSULE_REVISION = "chalxius-external-fact-evidence-capsule-1"
FACT_EVIDENCE_SOURCE_AUDIT_REVISION = "chalxius-v5-fact-evidence-audit-1"
BRIDGE_CAPSULE_REVISION = "chalxius-evidence-bridge-capsule-1"
COLLECTION_PREFIXES = {
    "zotero_exports": "zex",
    "papers": "zpr",
    "versions": "zpv",
    "graphs": "zpg",
    "corrections": "zpc",
    "source_checks": "psc",
    "evidence_items": "evd",
    "evidence_dispositions": "evs",
    "bridge_capsules": "evb",
}
EVIDENCE_KINDS = {"reviewed_paper_graph", "external_fact_graph"}
EVIDENCE_DISPOSITIONS = {
    "active",
    "challenged",
    "superseded",
    "withdrawn",
    "stale_source",
}
ARXIV_API_ENDPOINT = "https://export.arxiv.org/api/query"
ARXIV_MODERN_RE = re.compile(r"^(?P<base>\d{4}\.\d{4,5})(?:v(?P<version>[1-9]\d*))?$")
ARXIV_LEGACY_RE = re.compile(
    r"^(?P<base>[A-Za-z][A-Za-z0-9.\-]*/\d{7})(?:v(?P<version>[1-9]\d*))?$"
)
ATOM_NAMESPACE = "http://www.w3.org/2005/Atom"
MAX_ARXIV_BATCH = 100
MAX_ARXIV_RESPONSE_BYTES = 16 * 1024 * 1024
MAX_PDF_BYTES = 256 * 1024 * 1024


class LibraryError(RuntimeError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def object_hash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def require_text(value: str | None, label: str) -> str:
    text = (value or "").strip()
    if not text:
        raise LibraryError(f"{label} must be nonempty")
    return text


def require_date(value: str, label: str) -> str:
    try:
        parsed = dt.date.fromisoformat(value)
    except ValueError as exc:
        raise LibraryError(f"{label} must be YYYY-MM-DD") from exc
    return parsed.isoformat()


def require_timestamp(value: str, label: str) -> str:
    text = require_text(value, label)
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = dt.datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise LibraryError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise LibraryError(f"{label} must include a timezone")
    return parsed.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def normalized_whitespace(value: str) -> str:
    return " ".join(value.split())


def normalize_arxiv_id(value: str, *, require_version: bool = False) -> tuple[str, int | None, str]:
    text = require_text(value, "arxiv_id").strip()
    text = re.sub(r"^arxiv:\s*", "", text, flags=re.IGNORECASE)
    if "://" in text:
        parsed = urllib.parse.urlparse(text)
        path = parsed.path.strip("/")
        if path.startswith("abs/") or path.startswith("pdf/"):
            text = path.split("/", 1)[1]
        else:
            raise LibraryError("arxiv_id URL must use /abs/ or /pdf/")
    text = text.removesuffix(".pdf")
    match = ARXIV_MODERN_RE.fullmatch(text) or ARXIV_LEGACY_RE.fullmatch(text)
    if not match:
        raise LibraryError(f"invalid arxiv_id: {value}")
    base = match.group("base").lower()
    version_text = match.group("version")
    version = int(version_text) if version_text else None
    if require_version and version is None:
        raise LibraryError("arxiv_id must include an explicit vN version")
    full = f"{base}v{version}" if version is not None else base
    return base, version, full


def normalize_doi(value: str) -> str:
    text = require_text(value, "doi").strip().lower()
    text = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", text)
    text = re.sub(r"^doi:\s*", "", text)
    if not text.startswith("10.") or "/" not in text:
        raise LibraryError(f"invalid doi: {value}")
    return text


def normalize_identity(scheme: str, key: str) -> dict[str, str]:
    normalized_scheme = require_text(scheme, "identity_scheme").lower()
    raw_key = require_text(key, "identity_key")
    if normalized_scheme == "arxiv":
        normalized_key, _, _ = normalize_arxiv_id(raw_key)
    elif normalized_scheme == "doi":
        normalized_key = normalize_doi(raw_key)
    elif normalized_scheme in {"isbn", "local", "zotero"}:
        normalized_key = raw_key.strip()
        if len(normalized_key) > 512:
            raise LibraryError("identity_key is too long")
    else:
        raise LibraryError(f"unsupported identity_scheme: {scheme}")
    return {
        "revision": "paper-native-identity-1",
        "scheme": normalized_scheme,
        "key": normalized_key,
        "canonical": f"{normalized_scheme}:{normalized_key}",
    }


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LibraryError(f"cannot read JSON {path}: {exc}") from exc


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def root_path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def config_path(root: Path) -> Path:
    return root / "library.json"


def assert_repository(root: Path) -> dict[str, Any]:
    path = config_path(root)
    if not path.is_file():
        raise LibraryError(f"not an initialized paper library: {root}")
    config = read_json(path)
    if config.get("schema_version") != SCHEMA_VERSION:
        raise LibraryError("unsupported library schema_version")
    if config.get("contract_revision") != CONTRACT_REVISION:
        raise LibraryError("unsupported library contract_revision")
    return config


@contextlib.contextmanager
def library_lock(root: Path) -> Iterable[None]:
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / ".paper-library.lock"
    with lock_path.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def event_path(root: Path) -> Path:
    return root / "events" / "library.jsonl"


def load_events(root: Path) -> list[dict[str, Any]]:
    path = event_path(root)
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    previous = ""
    with path.open("r", encoding="utf-8") as handle:
        for expected_sequence, line in enumerate(handle, start=1):
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise LibraryError(f"invalid event JSON at sequence {expected_sequence}") from exc
            if event.get("sequence") != expected_sequence:
                raise LibraryError("event sequence mismatch")
            if event.get("previous_event_sha256") != previous:
                raise LibraryError("event chain mismatch")
            stored_hash = event.get("event_sha256")
            core = {key: value for key, value in event.items() if key != "event_sha256"}
            if stored_hash != object_hash(core):
                raise LibraryError("event hash mismatch")
            previous = stored_hash
            events.append(event)
    return events


def append_event_locked(
    root: Path,
    event_type: str,
    object_id: str,
    object_sha256: str,
) -> dict[str, Any]:
    events = load_events(root)
    for event in events:
        if (
            event.get("event_type") == event_type
            and event.get("object_id") == object_id
            and event.get("object_sha256") == object_sha256
        ):
            return event
    core = {
        "schema_version": SCHEMA_VERSION,
        "contract_revision": EVENT_REVISION,
        "sequence": len(events) + 1,
        "previous_event_sha256": events[-1]["event_sha256"] if events else "",
        "event_type": require_text(event_type, "event_type"),
        "object_id": require_text(object_id, "object_id"),
        "object_sha256": require_text(object_sha256, "object_sha256"),
        "occurred_at": utc_now(),
        "truth_effect": "none",
    }
    event = {**core, "event_sha256": object_hash(core)}
    path = event_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(canonical_bytes(event).decode("utf-8") + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return event


def record_path(root: Path, collection: str, object_id: str) -> Path:
    if collection not in COLLECTION_PREFIXES:
        raise LibraryError(f"unknown record collection: {collection}")
    return root / "records" / collection / "by-id" / f"{object_id}.json"


def record_payload(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in record.items()
        if key not in {"object_id", "record_sha256"}
    }


def record_identity_payload(
    collection: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if collection == "papers":
        identity = payload.get("identity")
        if isinstance(identity, dict) and identity.get("canonical"):
            return {
                "schema_version": payload.get("schema_version"),
                "contract_revision": payload.get("contract_revision"),
                "object_type": payload.get("object_type"),
                "identity_revision": identity.get("revision"),
                "identity_canonical": identity.get("canonical"),
            }
        # Read-compatible identity rule for records created before the native
        # registry became available.
        zotero = payload.get("zotero", {})
        return {
            "schema_version": payload.get("schema_version"),
            "contract_revision": payload.get("contract_revision"),
            "object_type": payload.get("object_type"),
            "zotero_library_id": zotero.get("library_id"),
            "zotero_item_key": zotero.get("item_key"),
        }
    return payload


def make_record(collection: str, payload: dict[str, Any]) -> dict[str, Any]:
    prefix = COLLECTION_PREFIXES[collection]
    object_id = f"{prefix}-{object_hash(record_identity_payload(collection, payload))}"
    core = {**payload, "object_id": object_id}
    return {**core, "record_sha256": object_hash(core)}


def validate_record(collection: str, record: dict[str, Any]) -> None:
    expected = make_record(collection, record_payload(record))
    if record != expected:
        raise LibraryError(f"record hash or id mismatch: {record.get('object_id')}")


def write_record(
    root: Path,
    collection: str,
    payload: dict[str, Any],
    event_type: str,
) -> dict[str, Any]:
    record = make_record(collection, payload)
    path = record_path(root, collection, record["object_id"])
    with library_lock(root):
        if path.exists():
            current = read_json(path)
            if current != record:
                raise LibraryError(f"immutable record collision: {path}")
        else:
            atomic_json(path, record)
        append_event_locked(
            root,
            event_type,
            record["object_id"],
            record["record_sha256"],
        )
    return record


def load_collection(root: Path, collection: str) -> dict[str, dict[str, Any]]:
    directory = root / "records" / collection / "by-id"
    records: dict[str, dict[str, Any]] = {}
    if not directory.exists():
        return records
    for path in sorted(directory.glob("*.json")):
        record = read_json(path)
        validate_record(collection, record)
        if path.stem != record["object_id"]:
            raise LibraryError(f"record filename mismatch: {path}")
        records[record["object_id"]] = record
    return records


def get_record(root: Path, collection: str, object_id: str) -> dict[str, Any]:
    path = record_path(root, collection, object_id)
    if not path.is_file():
        raise LibraryError(f"unknown {collection} id: {object_id}")
    record = read_json(path)
    validate_record(collection, record)
    return record


def store_regular_file(
    source: Path,
    target_directory: Path,
    suffix: str,
    require_pdf: bool = False,
) -> tuple[str, int, str]:
    source = source.expanduser()
    if source.is_symlink():
        raise LibraryError(f"source must not be a symlink: {source}")
    source = source.resolve()
    if not source.is_file():
        raise LibraryError(f"source must be a regular file: {source}")
    if require_pdf:
        with source.open("rb") as handle:
            if handle.read(5) != b"%PDF-":
                raise LibraryError(f"source is not a PDF: {source}")
    digest = file_hash(source)
    target_directory.mkdir(parents=True, exist_ok=True)
    target = target_directory / f"{digest}{suffix}"
    if target.exists():
        if file_hash(target) != digest:
            raise LibraryError(f"content-address collision: {target}")
    else:
        fd, temporary = tempfile.mkstemp(prefix=f".{digest}.", dir=target_directory)
        os.close(fd)
        temporary_path = Path(temporary)
        try:
            shutil.copyfile(source, temporary_path)
            if file_hash(temporary_path) != digest:
                raise LibraryError("copy verification failed")
            os.replace(temporary_path, target)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()
    return digest, source.stat().st_size, target.name


def store_bytes(
    data: bytes,
    target_directory: Path,
    suffix: str,
) -> tuple[str, int, str]:
    digest = hashlib.sha256(data).hexdigest()
    target_directory.mkdir(parents=True, exist_ok=True)
    target = target_directory / f"{digest}{suffix}"
    if target.exists():
        if target.is_symlink() or not target.is_file() or file_hash(target) != digest:
            raise LibraryError(f"content-address collision: {target}")
    else:
        fd, temporary = tempfile.mkstemp(prefix=f".{digest}.", dir=target_directory)
        temporary_path = Path(temporary)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            if file_hash(temporary_path) != digest:
                raise LibraryError("byte-store verification failed")
            os.replace(temporary_path, target)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()
    return digest, len(data), target.name


def fetch_arxiv_feed(arxiv_ids: list[str]) -> tuple[str, bytes]:
    if not arxiv_ids:
        raise LibraryError("at least one arXiv identity is required")
    if len(arxiv_ids) > MAX_ARXIV_BATCH:
        raise LibraryError(
            f"one arxiv-check is limited to {MAX_ARXIV_BATCH} papers"
        )
    query = urllib.parse.urlencode(
        {"id_list": ",".join(arxiv_ids), "max_results": len(arxiv_ids)}
    )
    endpoint = f"{ARXIV_API_ENDPOINT}?{query}"
    request = urllib.request.Request(
        endpoint,
        headers={
            "Accept": "application/atom+xml",
            "User-Agent": "ChalxiusPaperLibrary/1 (+local research archive)",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status = getattr(response, "status", 200)
            if status != 200:
                raise LibraryError(f"arXiv API returned HTTP {status}")
            data = response.read(MAX_ARXIV_RESPONSE_BYTES + 1)
    except (OSError, TimeoutError) as exc:
        raise LibraryError(f"arXiv API request failed: {exc}") from exc
    if len(data) > MAX_ARXIV_RESPONSE_BYTES:
        raise LibraryError("arXiv API response exceeds the byte limit")
    return endpoint, data


def fetch_arxiv_pdf(arxiv_id: str) -> tuple[str, bytes]:
    _, _, full = normalize_arxiv_id(arxiv_id, require_version=True)
    quoted_id = urllib.parse.quote(full, safe="/")
    locator = f"https://arxiv.org/pdf/{quoted_id}"
    request = urllib.request.Request(
        locator,
        headers={
            "Accept": "application/pdf",
            "User-Agent": "ChalxiusPaperLibrary/1 (+local research archive)",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            status = getattr(response, "status", 200)
            if status != 200:
                raise LibraryError(f"arXiv PDF request returned HTTP {status}")
            final_host = (urllib.parse.urlparse(response.geturl()).hostname or "").lower()
            if final_host not in {"arxiv.org", "www.arxiv.org"}:
                raise LibraryError(f"arXiv PDF redirected to an unexpected host: {final_host}")
            data = response.read(MAX_PDF_BYTES + 1)
    except (OSError, TimeoutError) as exc:
        raise LibraryError(f"arXiv PDF request failed: {exc}") from exc
    if len(data) > MAX_PDF_BYTES:
        raise LibraryError("arXiv PDF exceeds the byte limit")
    if not data.startswith(b"%PDF-"):
        raise LibraryError("arXiv PDF response is not a PDF")
    return locator, data


def xml_text(parent: ET.Element, name: str) -> str:
    element = parent.find(f"{{{ATOM_NAMESPACE}}}{name}")
    return normalized_whitespace(element.text or "") if element is not None else ""


def parse_arxiv_feed(data: bytes) -> dict[str, dict[str, Any]]:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise LibraryError(f"invalid arXiv Atom response: {exc}") from exc
    if root.tag != f"{{{ATOM_NAMESPACE}}}feed":
        raise LibraryError("arXiv response root is not an Atom feed")
    observations: dict[str, dict[str, Any]] = {}
    for entry in root.findall(f"{{{ATOM_NAMESPACE}}}entry"):
        entry_id = xml_text(entry, "id")
        if not entry_id:
            raise LibraryError("arXiv entry has no id")
        base, version, full = normalize_arxiv_id(entry_id, require_version=True)
        if base in observations:
            raise LibraryError(f"duplicate arXiv entry in response: {base}")
        authors = [
            xml_text(author, "name")
            for author in entry.findall(f"{{{ATOM_NAMESPACE}}}author")
        ]
        links: list[dict[str, str]] = []
        for link in entry.findall(f"{{{ATOM_NAMESPACE}}}link"):
            links.append(
                {
                    "href": link.attrib.get("href", ""),
                    "rel": link.attrib.get("rel", ""),
                    "type": link.attrib.get("type", ""),
                    "title": link.attrib.get("title", ""),
                }
            )
        observations[base] = {
            "arxiv_id": full,
            "base_arxiv_id": base,
            "version": version,
            "title": xml_text(entry, "title"),
            "authors": authors,
            "summary": xml_text(entry, "summary"),
            "published_at": xml_text(entry, "published"),
            "updated_at": xml_text(entry, "updated"),
            "links": links,
            "pdf_available": any(
                link["title"] == "pdf" or link["type"] == "application/pdf"
                for link in links
            ),
        }
    return observations


def safe_relative_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise LibraryError(f"unsafe relative path: {value}")
    return path


def graph_entries(source: Path) -> list[dict[str, Any]]:
    if not source.is_dir() or source.is_symlink():
        raise LibraryError(f"graph root must be a directory: {source}")
    entries: list[dict[str, Any]] = []
    for directory, directory_names, filenames in os.walk(source, followlinks=False):
        base = Path(directory)
        for name in directory_names:
            candidate = base / name
            if candidate.is_symlink():
                raise LibraryError(f"graph tree contains symlink: {candidate}")
            metadata = candidate.lstat()
            if not stat.S_ISDIR(metadata.st_mode):
                raise LibraryError(f"graph tree contains non-directory: {candidate}")
            relative = candidate.relative_to(source).as_posix()
            safe_relative_path(relative)
            entries.append(
                {
                    "path": relative,
                    "kind": "directory",
                    "mode": stat.S_IMODE(metadata.st_mode),
                }
            )
        for name in filenames:
            candidate = base / name
            metadata = candidate.lstat()
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
                raise LibraryError(f"graph tree contains non-regular file: {candidate}")
            relative = candidate.relative_to(source).as_posix()
            safe_relative_path(relative)
            entries.append(
                {
                    "path": relative,
                    "kind": "file",
                    "mode": stat.S_IMODE(metadata.st_mode),
                    "size": metadata.st_size,
                    "sha256": file_hash(candidate),
                }
            )
    return sorted(entries, key=lambda item: item["path"])


def graph_tree_hash(entries: list[dict[str, Any]]) -> str:
    return object_hash(
        {
            "contract_revision": "chalxius-paper-graph-tree-1",
            "entries": entries,
        }
    )


def store_graph_tree(root: Path, source: Path) -> tuple[str, list[dict[str, Any]]]:
    source = source.expanduser()
    if source.is_symlink():
        raise LibraryError(f"graph root must not be a symlink: {source}")
    source = source.resolve()
    entries = graph_entries(source)
    tree_hash = graph_tree_hash(entries)
    parent = root / "objects" / "graphs" / "by-sha256"
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / tree_hash
    if target.exists():
        verify_graph_object(target, tree_hash)
        return tree_hash, entries
    temporary = Path(tempfile.mkdtemp(prefix=f".{tree_hash}.", dir=parent))
    try:
        files_root = temporary / "files"
        files_root.mkdir()
        for entry in entries:
            if entry["kind"] != "directory":
                continue
            relative = safe_relative_path(entry["path"])
            target_directory = files_root.joinpath(*relative.parts)
            target_directory.mkdir(parents=True, exist_ok=True)
            os.chmod(target_directory, entry["mode"])
        for entry in entries:
            if entry["kind"] != "file":
                continue
            relative = safe_relative_path(entry["path"])
            source_file = source.joinpath(*relative.parts)
            target_file = files_root.joinpath(*relative.parts)
            target_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_file, target_file)
            os.chmod(target_file, entry["mode"])
            if file_hash(target_file) != entry["sha256"]:
                raise LibraryError("graph copy verification failed")
        atomic_json(
            temporary / "manifest.json",
            {
                "schema_version": SCHEMA_VERSION,
                "contract_revision": "chalxius-paper-graph-tree-1",
                "tree_sha256": tree_hash,
                "entries": entries,
            },
        )
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    verify_graph_object(target, tree_hash)
    return tree_hash, entries


def verify_graph_object(path: Path, expected_tree_hash: str) -> None:
    if path.is_symlink() or not path.is_dir():
        raise LibraryError(f"invalid graph object directory: {path}")
    manifest = read_json(path / "manifest.json")
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise LibraryError(f"invalid graph manifest: {path}")
    if manifest.get("tree_sha256") != expected_tree_hash:
        raise LibraryError("graph manifest tree id mismatch")
    if graph_tree_hash(entries) != expected_tree_hash:
        raise LibraryError("graph manifest hash mismatch")
    expected_files: set[str] = set()
    expected_directories: set[str] = set()
    files_root = path / "files"
    for entry in entries:
        relative = safe_relative_path(entry["path"])
        candidate = files_root.joinpath(*relative.parts)
        if entry.get("kind") == "directory":
            expected_directories.add(relative.as_posix())
            if not candidate.is_dir() or candidate.is_symlink():
                raise LibraryError(f"missing graph object directory: {candidate}")
            if stat.S_IMODE(candidate.stat().st_mode) != entry["mode"]:
                raise LibraryError(f"graph object directory mode mismatch: {candidate}")
            continue
        if entry.get("kind") != "file":
            raise LibraryError(f"unknown graph manifest entry kind: {entry}")
        expected_files.add(relative.as_posix())
        if not candidate.is_file() or candidate.is_symlink():
            raise LibraryError(f"missing graph object file: {candidate}")
        metadata = candidate.stat()
        if metadata.st_size != entry["size"]:
            raise LibraryError(f"graph object size mismatch: {candidate}")
        if stat.S_IMODE(metadata.st_mode) != entry["mode"]:
            raise LibraryError(f"graph object mode mismatch: {candidate}")
        if file_hash(candidate) != entry["sha256"]:
            raise LibraryError(f"graph object hash mismatch: {candidate}")
    actual_files = {
        candidate.relative_to(files_root).as_posix()
        for candidate in files_root.rglob("*")
        if candidate.is_file()
    }
    actual_directories = {
        candidate.relative_to(files_root).as_posix()
        for candidate in files_root.rglob("*")
        if candidate.is_dir()
    }
    if actual_files != expected_files or actual_directories != expected_directories:
        raise LibraryError(f"graph object exact-set mismatch: {path}")


def runtime_provenance(chalxius_root: Path) -> dict[str, Any]:
    chalxius_root = chalxius_root.expanduser().resolve()
    version_path = chalxius_root / "VERSION"
    manifest_path = chalxius_root / "MANIFEST.sha256"
    if not version_path.is_file() or not manifest_path.is_file():
        raise LibraryError("chalxius root must contain VERSION and MANIFEST.sha256")
    inheritance_path = chalxius_root / "INHERITANCE.lock.json"
    return {
        "capture_locator": str(chalxius_root),
        "version": require_text(version_path.read_text(encoding="utf-8"), "VERSION"),
        "version_sha256": file_hash(version_path),
        "manifest_file_sha256": file_hash(manifest_path),
        "inheritance_lock_sha256": (
            file_hash(inheritance_path) if inheritance_path.is_file() else ""
        ),
    }


def detect_graph_metadata(graph_root: Path) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "feature_revision": "",
        "source_project_id": "",
        "snapshot_ids": [],
    }
    store = graph_root / "store.json"
    if store.is_file():
        data = read_json(store)
        metadata["feature_revision"] = str(data.get("feature_revision", ""))
        metadata["source_project_id"] = str(data.get("project_id", ""))
    project = graph_root.parent / "project.json"
    if project.is_file():
        data = read_json(project)
        metadata["source_project_id"] = str(
            data.get("project_id", metadata["source_project_id"])
        )
    snapshots = graph_root / "snapshots" / "by-id"
    if snapshots.is_dir():
        metadata["snapshot_ids"] = sorted(
            path.name
            for path in snapshots.iterdir()
            if path.name.startswith("pls-")
        )
    return metadata


def base_payload(object_type: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_revision": CONTRACT_REVISION,
        "object_type": object_type,
        "truth_effect": "none",
    }


def cmd_init(args: argparse.Namespace) -> dict[str, Any]:
    root = root_path(args.root)
    with library_lock(root):
        path = config_path(root)
        if path.exists():
            config = read_json(path)
            if (
                config.get("schema_version") != SCHEMA_VERSION
                or config.get("contract_revision") != CONTRACT_REVISION
            ):
                raise LibraryError("existing library has an incompatible contract")
            if config.get("library_id") != require_text(args.library_id, "library_id"):
                raise LibraryError("existing library_id does not match --library-id")
            if config.get("name") != require_text(args.name, "name"):
                raise LibraryError("existing library name does not match --name")
        else:
            config = {
                "schema_version": SCHEMA_VERSION,
                "contract_revision": CONTRACT_REVISION,
                "library_id": require_text(args.library_id, "library_id"),
                "name": require_text(args.name, "name"),
                "created_at": utc_now(),
                "authority": "cross_project_nontruth_evidence_sidecar",
            }
            atomic_json(path, config)
        for directory in (
            "events",
            "records",
            "objects/pdfs/by-sha256",
            "objects/zotero-exports/by-sha256",
            "objects/source-responses/by-sha256",
            "objects/corrections/by-sha256",
            "objects/graphs/by-sha256",
            "objects/evidence-attestations/by-sha256",
            "objects/fact-evidence/by-sha256",
            "objects/evidence-dispositions/by-sha256",
            "index",
        ):
            (root / directory).mkdir(parents=True, exist_ok=True)
        append_event_locked(root, "library_initialized", config["library_id"], object_hash(config))
    return {"ok": True, "root": str(root), "library": config}


def cmd_zotero_snapshot(args: argparse.Namespace) -> dict[str, Any]:
    root = root_path(args.root)
    assert_repository(root)
    source = Path(args.input).expanduser().resolve()
    parsed = read_json(source)
    if isinstance(parsed, list):
        item_count = len(parsed)
    elif isinstance(parsed, dict) and isinstance(parsed.get("items"), list):
        item_count = len(parsed["items"])
    else:
        item_count = 0
    digest, size, filename = store_regular_file(
        source,
        root / "objects" / "zotero-exports" / "by-sha256",
        ".json",
    )
    payload = {
        **base_payload("zotero_export_snapshot"),
        "zotero_library_id": require_text(args.library_id, "library_id"),
        "export_format": require_text(args.format, "format"),
        "artifact": {
            "sha256": digest,
            "size": size,
            "path": f"objects/zotero-exports/by-sha256/{filename}",
        },
        "item_count": item_count,
    }
    record = write_record(root, "zotero_exports", payload, "zotero_export_captured")
    return {"ok": True, "record": record}


def cmd_paper_add(args: argparse.Namespace) -> dict[str, Any]:
    root = root_path(args.root)
    assert_repository(root)
    export_id = (args.zotero_export_id or "").strip()
    if export_id:
        get_record(root, "zotero_exports", export_id)
    zotero_library_id = (args.zotero_library_id or "").strip()
    zotero_item_key = (args.zotero_item_key or "").strip()
    if bool(zotero_library_id) != bool(zotero_item_key):
        raise LibraryError(
            "zotero_library_id and zotero_item_key must be supplied together"
        )
    identity_scheme = (args.identity_scheme or "").strip()
    identity_key = (args.identity_key or "").strip()
    if bool(identity_scheme) != bool(identity_key):
        raise LibraryError("identity_scheme and identity_key must be supplied together")
    arxiv_id = ""
    if args.arxiv_id:
        arxiv_id, _, _ = normalize_arxiv_id(args.arxiv_id)
    doi = normalize_doi(args.doi) if args.doi else ""
    if identity_scheme:
        identity = normalize_identity(identity_scheme, identity_key)
    elif arxiv_id:
        identity = normalize_identity("arxiv", arxiv_id)
    elif doi:
        identity = normalize_identity("doi", doi)
    elif args.local_key:
        identity = normalize_identity("local", args.local_key)
    elif zotero_library_id:
        identity = normalize_identity(
            "zotero", f"{zotero_library_id}:{zotero_item_key}"
        )
    else:
        raise LibraryError(
            "paper identity requires --identity-scheme/--identity-key, "
            "--arxiv-id, --doi, --local-key, or a Zotero key pair"
        )
    payload = {
        **base_payload("paper_identity"),
        "identity": identity,
        "zotero": {
            "library_id": zotero_library_id,
            "item_key": zotero_item_key,
            "citekey": (args.citekey or "").strip(),
            "export_id": export_id,
        },
        "bibliographic": {
            "title": require_text(args.title, "title"),
            "authors": [require_text(author, "author") for author in args.author],
            "doi": doi,
            "arxiv_id": arxiv_id,
            "issued": (args.issued or "").strip(),
        },
        "trust_tier": "bibliographic_identity",
        "premise_eligible": False,
    }
    record = write_record(root, "papers", payload, "paper_registered")
    return {"ok": True, "paper_id": record["object_id"], "record": record}


def cmd_version_add(args: argparse.Namespace) -> dict[str, Any]:
    root = root_path(args.root)
    assert_repository(root)
    paper = get_record(root, "papers", args.paper_id)
    version_kind = require_text(args.kind, "kind")
    arxiv_id = ""
    if version_kind == "arxiv":
        _, _, arxiv_id = normalize_arxiv_id(args.arxiv_id, require_version=True)
        paper_arxiv_id = paper.get("bibliographic", {}).get("arxiv_id", "")
        if paper_arxiv_id and normalize_arxiv_id(arxiv_id)[0] != normalize_arxiv_id(
            paper_arxiv_id
        )[0]:
            raise LibraryError("version arxiv_id does not match the paper identity")
    elif args.arxiv_id:
        _, _, arxiv_id = normalize_arxiv_id(args.arxiv_id)
    supersedes = sorted(set(args.supersedes_version_id))
    for version_id in supersedes:
        prior = get_record(root, "versions", version_id)
        if prior["paper_id"] != args.paper_id:
            raise LibraryError("superseded version belongs to another paper")
    digest, size, filename = store_regular_file(
        Path(args.pdf),
        root / "objects" / "pdfs" / "by-sha256",
        ".pdf",
        require_pdf=True,
    )
    if arxiv_id:
        for existing in load_collection(root, "versions").values():
            if (
                existing["paper_id"] == args.paper_id
                and existing.get("identifiers", {}).get("arxiv_id") == arxiv_id
            ):
                if existing["pdf"]["sha256"] != digest:
                    raise LibraryError(
                        "the same explicit arXiv version has different PDF bytes"
                    )
                return {
                    "ok": True,
                    "version_id": existing["object_id"],
                    "pdf_sha256": digest,
                    "record": existing,
                    "already_captured": True,
                }
    payload = {
        **base_payload("paper_version"),
        "paper_id": args.paper_id,
        "version_label": require_text(args.label, "label"),
        "version_kind": version_kind,
        "source_locator": require_text(args.source_locator, "source_locator"),
        "retrieved_at": require_date(args.retrieved_at, "retrieved_at"),
        "published_at": (args.published_at or "").strip(),
        "identifiers": {
            "doi": normalize_doi(args.doi) if args.doi else "",
            "arxiv_id": arxiv_id,
        },
        "pdf": {
            "sha256": digest,
            "size": size,
            "path": f"objects/pdfs/by-sha256/{filename}",
        },
        "supersedes_version_ids": supersedes,
        "trust_tier": "source_frozen",
        "premise_eligible": False,
    }
    record = write_record(root, "versions", payload, "paper_version_captured")
    return {
        "ok": True,
        "version_id": record["object_id"],
        "pdf_sha256": digest,
        "record": record,
    }


def paper_arxiv_identity(paper: dict[str, Any]) -> str:
    identity = paper.get("identity", {})
    if identity.get("scheme") == "arxiv":
        return normalize_arxiv_id(identity.get("key", ""))[0]
    arxiv_id = paper.get("bibliographic", {}).get("arxiv_id", "")
    return normalize_arxiv_id(arxiv_id)[0] if arxiv_id else ""


def cmd_arxiv_check(args: argparse.Namespace) -> dict[str, Any]:
    root = root_path(args.root)
    assert_repository(root)
    all_papers = load_collection(root, "papers")
    if args.all:
        selected = [
            paper
            for _, paper in sorted(all_papers.items())
            if paper_arxiv_identity(paper)
        ]
        if args.paper_id:
            raise LibraryError("--all cannot be combined with --paper-id")
    else:
        paper_ids = sorted(set(args.paper_id))
        if not paper_ids:
            raise LibraryError("arxiv-check requires --paper-id or --all")
        selected = [get_record(root, "papers", paper_id) for paper_id in paper_ids]
    if not selected:
        raise LibraryError("no arXiv-tracked papers were selected")
    if len(selected) > MAX_ARXIV_BATCH:
        raise LibraryError(
            f"one arxiv-check is limited to {MAX_ARXIV_BATCH} papers"
        )
    override = (args.arxiv_id or "").strip()
    if override and len(selected) != 1:
        raise LibraryError("--arxiv-id override requires exactly one paper")
    tracked: list[tuple[dict[str, Any], str]] = []
    for paper in selected:
        arxiv_id = normalize_arxiv_id(override)[0] if override else paper_arxiv_identity(paper)
        if not arxiv_id:
            raise LibraryError(
                f"paper has no arXiv identity or alias: {paper['object_id']}"
            )
        tracked.append((paper, arxiv_id))
    if args.input_atom:
        source = Path(args.input_atom).expanduser()
        if source.is_symlink():
            raise LibraryError(f"Atom input must not be a symlink: {source}")
        source = source.resolve()
        if not source.is_file():
            raise LibraryError(f"Atom input must be a regular file: {source}")
        data = source.read_bytes()
        if len(data) > MAX_ARXIV_RESPONSE_BYTES:
            raise LibraryError("arXiv Atom input exceeds the byte limit")
        endpoint = (args.response_locator or str(source)).strip()
    else:
        if args.response_locator:
            raise LibraryError("--response-locator is only valid with --input-atom")
        endpoint, data = fetch_arxiv_feed([arxiv_id for _, arxiv_id in tracked])
    if b"<!DOCTYPE" in data.upper():
        raise LibraryError("arXiv Atom response must not contain a DOCTYPE")
    observations = parse_arxiv_feed(data)
    digest, size, filename = store_bytes(
        data,
        root / "objects" / "source-responses" / "by-sha256",
        ".atom",
    )
    checked_at = require_timestamp(args.checked_at, "checked_at") if args.checked_at else utc_now()
    versions = load_collection(root, "versions")
    records: list[dict[str, Any]] = []
    status_counts: dict[str, int] = {}
    for paper, arxiv_id in tracked:
        observation = observations.get(arxiv_id)
        if observation is None:
            raise LibraryError(f"arXiv response omitted requested id: {arxiv_id}")
        local_versions: list[tuple[int, str, str]] = []
        for version_id, version_record in versions.items():
            if version_record["paper_id"] != paper["object_id"]:
                continue
            stored_arxiv_id = version_record.get("identifiers", {}).get("arxiv_id", "")
            if not stored_arxiv_id:
                continue
            base, number, full = normalize_arxiv_id(stored_arxiv_id)
            if base == arxiv_id and number is not None:
                local_versions.append((number, full, version_id))
        local_versions.sort()
        local_latest = local_versions[-1][0] if local_versions else 0
        remote_latest = observation["version"]
        if not observation["pdf_available"]:
            status = "latest_withdrawn_or_no_pdf"
        elif not local_versions:
            status = "not_captured"
        elif remote_latest > local_latest:
            status = "new_version_available"
        elif remote_latest == local_latest:
            status = "up_to_date"
        else:
            status = "remote_behind_local"
        payload = {
            **base_payload("source_version_check"),
            "paper_id": paper["object_id"],
            "source": {
                "scheme": "arxiv",
                "identity_key": arxiv_id,
                "query_locator": endpoint,
            },
            "checked_at": checked_at,
            "response": {
                "sha256": digest,
                "size": size,
                "path": f"objects/source-responses/by-sha256/{filename}",
            },
            "observation": observation,
            "local_versions": [
                {
                    "version": number,
                    "arxiv_id": full,
                    "version_id": version_id,
                }
                for number, full, version_id in local_versions
            ],
            "status": status,
            "trust_tier": "source_observation",
            "premise_eligible": False,
        }
        record = write_record(
            root, "source_checks", payload, "source_version_checked"
        )
        records.append(record)
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "ok": True,
        "checked_at": checked_at,
        "paper_count": len(records),
        "status_counts": status_counts,
        "checks": [
            {
                "check_id": record["object_id"],
                "paper_id": record["paper_id"],
                "arxiv_id": record["observation"]["arxiv_id"],
                "status": record["status"],
            }
            for record in records
        ],
    }


def cmd_arxiv_capture(args: argparse.Namespace) -> dict[str, Any]:
    root = root_path(args.root)
    assert_repository(root)
    paper = get_record(root, "papers", args.paper_id)
    base, number, full = normalize_arxiv_id(args.arxiv_id, require_version=True)
    paper_arxiv_id = paper_arxiv_identity(paper)
    if paper_arxiv_id and paper_arxiv_id != base:
        raise LibraryError("captured arxiv_id does not match the paper identity")
    if args.pdf:
        locator = f"https://arxiv.org/pdf/{urllib.parse.quote(full, safe='/')}"
        digest, size, filename = store_regular_file(
            Path(args.pdf),
            root / "objects" / "pdfs" / "by-sha256",
            ".pdf",
            require_pdf=True,
        )
        downloaded = False
    else:
        locator, data = fetch_arxiv_pdf(full)
        digest, size, filename = store_bytes(
            data,
            root / "objects" / "pdfs" / "by-sha256",
            ".pdf",
        )
        downloaded = True
    versions = load_collection(root, "versions")
    lower_versions: list[tuple[int, str]] = []
    for version_id, existing in versions.items():
        if existing["paper_id"] != args.paper_id:
            continue
        stored = existing.get("identifiers", {}).get("arxiv_id", "")
        if not stored:
            continue
        stored_base, stored_number, stored_full = normalize_arxiv_id(stored)
        if stored_base != base or stored_number is None:
            continue
        if stored_full == full:
            if existing["pdf"]["sha256"] != digest:
                raise LibraryError(
                    "the same explicit arXiv version has different PDF bytes"
                )
            return {
                "ok": True,
                "version_id": existing["object_id"],
                "pdf_sha256": digest,
                "record": existing,
                "already_captured": True,
                "downloaded": downloaded,
            }
        if stored_number < number:
            lower_versions.append((stored_number, version_id))
    supersedes = [max(lower_versions)[1]] if lower_versions else []
    retrieved_at = (
        require_date(args.retrieved_at, "retrieved_at")
        if args.retrieved_at
        else dt.datetime.now(dt.timezone.utc).date().isoformat()
    )
    payload = {
        **base_payload("paper_version"),
        "paper_id": args.paper_id,
        "version_label": (args.label or f"arxiv-v{number}").strip(),
        "version_kind": "arxiv",
        "source_locator": locator,
        "retrieved_at": retrieved_at,
        "published_at": (args.published_at or "").strip(),
        "identifiers": {"doi": "", "arxiv_id": full},
        "pdf": {
            "sha256": digest,
            "size": size,
            "path": f"objects/pdfs/by-sha256/{filename}",
        },
        "supersedes_version_ids": supersedes,
        "trust_tier": "source_frozen",
        "premise_eligible": False,
    }
    record = write_record(root, "versions", payload, "paper_version_captured")
    return {
        "ok": True,
        "version_id": record["object_id"],
        "pdf_sha256": digest,
        "record": record,
        "already_captured": False,
        "downloaded": downloaded,
    }


def cmd_graph_add(args: argparse.Namespace) -> dict[str, Any]:
    root = root_path(args.root)
    assert_repository(root)
    get_record(root, "papers", args.paper_id)
    version = get_record(root, "versions", args.version_id)
    if version["paper_id"] != args.paper_id:
        raise LibraryError("version belongs to another paper")
    supersedes = sorted(set(args.supersedes_graph_id))
    for graph_id in supersedes:
        prior = get_record(root, "graphs", graph_id)
        if prior["paper_id"] != args.paper_id:
            raise LibraryError("superseded graph belongs to another paper")
    graph_root = Path(args.graph_root).expanduser().resolve()
    tree_hash, entries = store_graph_tree(root, graph_root)
    detected = detect_graph_metadata(graph_root)
    supplied_snapshots = sorted(set(args.snapshot_id))
    snapshot_ids = supplied_snapshots or detected["snapshot_ids"]
    payload = {
        **base_payload("paper_graph_capture"),
        "paper_id": args.paper_id,
        "version_id": args.version_id,
        "pdf_sha256": version["pdf"]["sha256"],
        "graph_kind": require_text(args.graph_kind, "graph_kind"),
        "graph_format_revision": detected["feature_revision"],
        "source": {
            "capture_locator": str(graph_root),
            "project_id": (args.source_project_id or detected["source_project_id"]).strip(),
            "snapshot_ids": snapshot_ids,
        },
        "tree": {
            "sha256": tree_hash,
            "file_count": len(entries),
            "path": f"objects/graphs/by-sha256/{tree_hash}",
        },
        "chalxius": runtime_provenance(Path(args.chalxius_root)),
        "supersedes_graph_ids": supersedes,
        "trust_tier": "research",
        "evidence_status": "imported_nontruth",
        "premise_eligible": False,
    }
    record = write_record(root, "graphs", payload, "paper_graph_captured")
    return {
        "ok": True,
        "graph_id": record["object_id"],
        "tree_sha256": tree_hash,
        "record": record,
    }


def cmd_correction_add(args: argparse.Namespace) -> dict[str, Any]:
    root = root_path(args.root)
    assert_repository(root)
    get_record(root, "papers", args.paper_id)
    version = get_record(root, "versions", args.version_id)
    if version["paper_id"] != args.paper_id:
        raise LibraryError("version belongs to another paper")
    graph_id = (args.graph_id or "").strip()
    if graph_id:
        graph = get_record(root, "graphs", graph_id)
        if graph["paper_id"] != args.paper_id or graph["version_id"] != args.version_id:
            raise LibraryError("correction graph target does not match paper/version")
    supersedes = sorted(set(args.supersedes_correction_id))
    for correction_id in supersedes:
        prior = get_record(root, "corrections", correction_id)
        if prior["paper_id"] != args.paper_id:
            raise LibraryError("superseded correction belongs to another paper")
    artifact: dict[str, Any] | None = None
    if args.artifact:
        digest, size, filename = store_regular_file(
            Path(args.artifact),
            root / "objects" / "corrections" / "by-sha256",
            ".artifact",
        )
        artifact = {
            "sha256": digest,
            "size": size,
            "path": f"objects/corrections/by-sha256/{filename}",
        }
    payload = {
        **base_payload("paper_correction"),
        "paper_id": args.paper_id,
        "version_id": args.version_id,
        "graph_id": graph_id,
        "correction_kind": require_text(args.kind, "kind"),
        "status": require_text(args.status, "status"),
        "summary": require_text(args.summary, "summary"),
        "official_locator": (args.official_locator or "").strip(),
        "artifact": artifact,
        "supersedes_correction_ids": supersedes,
        "trust_tier": "research",
        "evidence_status": "uncertified_correction",
        "premise_eligible": False,
    }
    record = write_record(root, "corrections", payload, "paper_correction_recorded")
    return {"ok": True, "correction_id": record["object_id"], "record": record}


def require_sha256(value: Any, label: str) -> str:
    text = require_text(value if isinstance(value, str) else "", label)
    if re.fullmatch(r"[0-9a-f]{64}", text) is None:
        raise LibraryError(f"{label} must be a full lowercase SHA-256")
    return text


def evidence_disposition_heads(
    dispositions: dict[str, dict[str, Any]],
    evidence_id: str,
) -> list[str]:
    relevant = {
        object_id: record
        for object_id, record in dispositions.items()
        if record["evidence_id"] == evidence_id
    }
    superseded = {
        prior
        for record in relevant.values()
        for prior in record["supersedes_disposition_ids"]
    }
    return sorted(set(relevant).difference(superseded))


def evidence_state_map(root: Path) -> dict[str, dict[str, Any]]:
    evidence = load_collection(root, "evidence_items")
    dispositions = load_collection(root, "evidence_dispositions")
    superseded = {
        prior
        for record in evidence.values()
        for prior in record["supersedes_evidence_ids"]
    }
    states: dict[str, dict[str, Any]] = {}
    for evidence_id in sorted(evidence):
        heads = evidence_disposition_heads(dispositions, evidence_id)
        if len(heads) > 1:
            state = "conflicted"
            head_id = ""
        elif heads:
            head_id = heads[0]
            state = dispositions[head_id]["status"]
        else:
            head_id = ""
            state = "active"
        if evidence_id in superseded and state == "active":
            state = "superseded"
        states[evidence_id] = {
            "status": state,
            "disposition_head_id": head_id,
            "bridge_eligible": bool(
                evidence[evidence_id]["bridge_eligible"] and state == "active"
            ),
            "stale_upstream_evidence_ids": [],
        }
    # External Fact Evidence is not an independent trust root when any source
    # Candidate Release was admitted from an Evidence bridge.  Propagate
    # ineligibility to a fixed point so a correction cannot be hidden by
    # re-exporting the downstream Fact Graph through another project.
    changed = True
    while changed:
        changed = False
        for evidence_id in sorted(evidence):
            if states[evidence_id]["status"] != "active":
                continue
            upstream_ids = evidence[evidence_id].get("source", {}).get(
                "upstream_evidence_ids", []
            )
            missing = sorted(
                upstream_id
                for upstream_id in upstream_ids
                if upstream_id not in states
            )
            if missing:
                raise LibraryError(
                    "Evidence item references missing upstream Evidence: "
                    + ", ".join(missing)
                )
            stale_upstream = sorted(
                upstream_id
                for upstream_id in upstream_ids
                if not states[upstream_id]["bridge_eligible"]
            )
            if not stale_upstream:
                continue
            states[evidence_id] = {
                **states[evidence_id],
                "status": "stale_source",
                "bridge_eligible": False,
                "stale_upstream_evidence_ids": stale_upstream,
            }
            changed = True
    return states


def validate_paper_attestation(
    attestation: dict[str, Any],
    *,
    graph: dict[str, Any],
) -> None:
    required = {
        "schema_version",
        "contract_revision",
        "graph_id",
        "graph_tree_sha256",
        "paper_snapshot_id",
        "snapshot_manifest_sha256",
        "snapshot_graph_kind",
        "source_project_id",
        "pdf_sha256",
        "node_ids",
        "review_ids",
        "review_profiles",
        "paper_logic_audit",
        "paper_logic_audit_sha256",
        "truth_effect",
    }
    if set(attestation) != required:
        raise LibraryError("paper Evidence attestation fields are not exact")
    if (
        attestation["schema_version"] != 1
        or attestation["contract_revision"] != EVIDENCE_ATTESTATION_REVISION
        or attestation["truth_effect"] != "none"
    ):
        raise LibraryError("paper Evidence attestation contract mismatch")
    if attestation["graph_id"] != graph["object_id"]:
        raise LibraryError("paper Evidence attestation graph id mismatch")
    if attestation["graph_tree_sha256"] != graph["tree"]["sha256"]:
        raise LibraryError("paper Evidence attestation graph tree mismatch")
    if attestation["source_project_id"] != graph["source"]["project_id"]:
        raise LibraryError("paper Evidence attestation project mismatch")
    if attestation["pdf_sha256"] != graph["pdf_sha256"]:
        raise LibraryError("paper Evidence attestation PDF mismatch")
    snapshot_id = require_text(attestation["paper_snapshot_id"], "paper_snapshot_id")
    if snapshot_id not in graph["source"]["snapshot_ids"]:
        raise LibraryError("attested Paper snapshot is absent from graph capture")
    require_sha256(attestation["snapshot_manifest_sha256"], "snapshot_manifest_sha256")
    graph_kind = attestation["snapshot_graph_kind"]
    expected_graph_kind = {"logic": "paper_logic", "audit": "paper_audit"}.get(
        graph_kind
    )
    if expected_graph_kind != graph["graph_kind"]:
        raise LibraryError("paper Evidence snapshot/graph kind mismatch")
    node_ids = attestation["node_ids"]
    if (
        not isinstance(node_ids, list)
        or not node_ids
        or len(node_ids) != len(set(node_ids))
        or any(not isinstance(item, str) or not item.strip() for item in node_ids)
    ):
        raise LibraryError("paper Evidence node ids are invalid")
    reviews = attestation["review_ids"]
    profiles = attestation["review_profiles"]
    if (
        not isinstance(reviews, list)
        or len(reviews) != len(set(reviews))
        or not reviews
        or any(not isinstance(item, str) or not item.strip() for item in reviews)
    ):
        raise LibraryError("paper Evidence review_ids are invalid")
    expected_profiles = {
        "logic": {"source_fidelity", "graph_structure"},
        "audit": {"target_binding", "audit_reasoning"},
    }[graph_kind]
    if not isinstance(profiles, list) or set(profiles) != expected_profiles:
        raise LibraryError("paper Evidence review profiles are incomplete")
    audit = attestation["paper_logic_audit"]
    if (
        not isinstance(audit, dict)
        or audit.get("ok") is not True
        or audit.get("errors") != []
    ):
        raise LibraryError("paper Evidence requires a clean Paper Logic audit")
    if attestation["paper_logic_audit_sha256"] != object_hash(audit):
        raise LibraryError("paper Evidence audit hash mismatch")


def cmd_evidence_paper_add(args: argparse.Namespace) -> dict[str, Any]:
    root = root_path(args.root)
    assert_repository(root)
    graph = get_record(root, "graphs", args.graph_id)
    paper = get_record(root, "papers", graph["paper_id"])
    version = get_record(root, "versions", graph["version_id"])
    attestation_source = Path(args.attestation).expanduser().resolve()
    attestation = read_json(attestation_source)
    if not isinstance(attestation, dict):
        raise LibraryError("paper Evidence attestation must be an object")
    validate_paper_attestation(attestation, graph=graph)
    digest, size, filename = store_regular_file(
        attestation_source,
        root / "objects" / "evidence-attestations" / "by-sha256",
        ".json",
    )
    supersedes = sorted(set(args.supersedes_evidence_id))
    for prior_id in supersedes:
        prior = get_record(root, "evidence_items", prior_id)
        if (
            prior["evidence_kind"] != "reviewed_paper_graph"
            or prior["source"]["paper_id"] != paper["object_id"]
        ):
            raise LibraryError("superseded Evidence belongs to another paper or kind")
    sync_mode = require_text(args.sync_mode, "sync_mode")
    if sync_mode not in {"automatic_after_reviewed_freeze", "explicit_import"}:
        raise LibraryError("invalid paper Evidence sync_mode")
    payload = {
        **base_payload("evidence_item"),
        "evidence_kind": "reviewed_paper_graph",
        "source": {
            "paper_id": paper["object_id"],
            "version_id": version["object_id"],
            "graph_id": graph["object_id"],
            "paper_snapshot_id": attestation["paper_snapshot_id"],
            "pdf_sha256": graph["pdf_sha256"],
        },
        "attestation": {
            "sha256": digest,
            "size": size,
            "path": f"objects/evidence-attestations/by-sha256/{filename}",
        },
        "source_project_id": graph["source"]["project_id"],
        "sync_mode": sync_mode,
        "trust_tier": "reviewed_paper_graph",
        "bridge_eligible": True,
        "premise_eligible": False,
        "supersedes_evidence_ids": supersedes,
    }
    record = write_record(root, "evidence_items", payload, "paper_evidence_admitted")
    return {
        "ok": True,
        "evidence_id": record["object_id"],
        "status": evidence_state_map(root)[record["object_id"]]["status"],
        "record": record,
    }


def fact_capsule_upstream_evidence_refs(
    capsule: dict[str, Any],
) -> list[dict[str, Any]]:
    active_release_ids = {
        item["release_id"]
        for item in capsule.get("active_facts", [])
        if isinstance(item, dict) and isinstance(item.get("release_id"), str)
    }
    releases: dict[str, dict[str, Any]] = {}
    for item in capsule.get("objects", []):
        if (
            not isinstance(item, dict)
            or item.get("role") != "release"
            or item.get("object_id") not in active_release_ids
        ):
            continue
        try:
            raw = base64.b64decode(item["bytes_base64"], validate=True)
            release = json.loads(raw)
        except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LibraryError(
                "external Fact Evidence release object is not valid JSON"
            ) from exc
        if not isinstance(release, dict):
            raise LibraryError("external Fact Evidence release object must be an object")
        releases[item["object_id"]] = release
    if set(releases) != active_release_ids:
        raise LibraryError("external Fact Evidence omits an active release object")

    refs_by_bridge: dict[str, dict[str, Any]] = {}
    required_ref_fields = {
        "bridge_id",
        "bridge_record_sha256",
        "bridge_artifact_sha256",
        "library_id",
        "evidence_ids",
    }
    for release_id in sorted(releases):
        release = releases[release_id]
        refs = release.get("evidence_bridge_refs", [])
        if not isinstance(refs, list) or any(not isinstance(ref, dict) for ref in refs):
            raise LibraryError("source release evidence_bridge_refs must be a list of objects")
        artifacts = release.get("artifacts", [])
        if not isinstance(artifacts, list):
            raise LibraryError("source release artifacts must be a list")
        bridge_artifact_hashes = {
            artifact.get("artifact_sha256")
            for artifact in artifacts
            if isinstance(artifact, dict)
            and artifact.get("role") == "evidence_bridge_capsule"
        }
        ref_artifact_hashes: set[str] = set()
        release_evidence_ids: set[str] = set()
        for ref in refs:
            if set(ref) != required_ref_fields:
                raise LibraryError("source release Evidence bridge ref fields are not exact")
            bridge_id = require_text(ref["bridge_id"], "source Evidence bridge id")
            record_sha = require_sha256(
                ref["bridge_record_sha256"], "source Evidence bridge record sha256"
            )
            artifact_sha = require_sha256(
                ref["bridge_artifact_sha256"], "source Evidence bridge artifact sha256"
            )
            library_id = require_text(ref["library_id"], "source Evidence library id")
            evidence_ids = ref["evidence_ids"]
            if (
                not isinstance(evidence_ids, list)
                or not evidence_ids
                or len(evidence_ids) != len(set(evidence_ids))
                or any(not isinstance(value, str) or not value.strip() for value in evidence_ids)
            ):
                raise LibraryError("source Evidence bridge evidence_ids are invalid")
            overlap = release_evidence_ids.intersection(evidence_ids)
            if overlap:
                raise LibraryError(
                    "source release selects Evidence through multiple bridges: "
                    + ", ".join(sorted(overlap))
                )
            release_evidence_ids.update(evidence_ids)
            normalized = {
                "bridge_id": bridge_id,
                "bridge_record_sha256": record_sha,
                "bridge_artifact_sha256": artifact_sha,
                "library_id": library_id,
                "evidence_ids": sorted(evidence_ids),
            }
            previous = refs_by_bridge.get(bridge_id)
            if previous is not None and previous != normalized:
                raise LibraryError("source Evidence bridge binding is inconsistent")
            refs_by_bridge[bridge_id] = normalized
            ref_artifact_hashes.add(artifact_sha)
        if ref_artifact_hashes != bridge_artifact_hashes:
            raise LibraryError(
                "source release Evidence bridge refs do not exactly bind its bridge artifacts"
            )
    return [refs_by_bridge[bridge_id] for bridge_id in sorted(refs_by_bridge)]


def validate_fact_capsule_upstream_bindings(
    root: Path,
    capsule: dict[str, Any],
    *,
    require_current: bool,
) -> list[str]:
    config = assert_repository(root)
    states = evidence_state_map(root) if require_current else {}
    upstream_evidence_ids: set[str] = set()
    for ref in fact_capsule_upstream_evidence_refs(capsule):
        if ref["library_id"] != config["library_id"]:
            raise LibraryError("source Fact Evidence references another Evidence library")
        bridge = get_record(root, "bridge_capsules", ref["bridge_id"])
        bridge_evidence_ids = sorted(
            item["evidence_id"] for item in bridge["selection"]["items"]
        )
        if (
            bridge["record_sha256"] != ref["bridge_record_sha256"]
            or bridge["library_id"] != config["library_id"]
            or bridge["destination_project_id"] != capsule["source_project_id"]
            or bridge_evidence_ids != ref["evidence_ids"]
        ):
            raise LibraryError("source Fact Evidence bridge lineage binding mismatch")
        if require_current and not bridge_check(root, bridge)["current"]:
            raise LibraryError("source Fact Evidence depends on a stale Evidence bridge")
        for evidence_id in ref["evidence_ids"]:
            get_record(root, "evidence_items", evidence_id)
            if require_current and not states[evidence_id]["bridge_eligible"]:
                raise LibraryError("source Fact Evidence depends on ineligible Evidence")
            upstream_evidence_ids.add(evidence_id)
    return sorted(upstream_evidence_ids)


def validate_fact_evidence_capsule(capsule: dict[str, Any]) -> None:
    required = {
        "schema_version",
        "contract_revision",
        "source_project_id",
        "source_root_locator",
        "source_audit",
        "active_facts",
        "revoked_fact_ids",
        "objects",
        "runtime",
        "truth_effect",
        "premise_eligible",
        "capsule_id",
    }
    if set(capsule) != required:
        raise LibraryError("external Fact Evidence capsule fields are not exact")
    if (
        capsule["schema_version"] != 1
        or capsule["contract_revision"] != FACT_EVIDENCE_CAPSULE_REVISION
        or capsule["truth_effect"] != "none"
        or capsule["premise_eligible"] is not False
    ):
        raise LibraryError("external Fact Evidence capsule contract mismatch")
    core = {key: value for key, value in capsule.items() if key != "capsule_id"}
    if capsule["capsule_id"] != "efc-" + object_hash(core):
        raise LibraryError("external Fact Evidence capsule id/hash mismatch")
    audit = capsule["source_audit"]
    if (
        not isinstance(audit, dict)
        or audit.get("current_ok") is not True
        or audit.get("history_clean") is not True
        or audit.get("errors") != []
    ):
        raise LibraryError("external Fact Evidence source audit is not clean")
    audit_scope = audit.get("scope")
    if audit_scope is not None and (
        audit_scope != "active_v5_fact_authority_only"
        or audit.get("contract_revision")
        != FACT_EVIDENCE_SOURCE_AUDIT_REVISION
        or audit.get("workflow_evidence_version") != 5
        or audit.get("source_runtime_policy")
        != "independent_of_frozen_nontruth_workflow_runtime"
        or audit.get("truth_effect") != "none"
        or audit.get("project_effect") != "none"
    ):
        raise LibraryError("external Fact Evidence scoped source audit is invalid")
    active_facts = capsule["active_facts"]
    if not isinstance(active_facts, list) or not active_facts:
        raise LibraryError("external Fact Evidence must contain active Facts")
    fact_ids: set[str] = set()
    for item in active_facts:
        if not isinstance(item, dict) or set(item) != {
            "fact_id",
            "fact_sha256",
            "interface_sha256",
            "interface_schema_version",
            "release_id",
            "release_sha256",
            "decision_id",
            "decision_sha256",
            "gateway",
            "acceptance_id",
        }:
            raise LibraryError("external Fact Evidence active_fact fields are not exact")
        fact_id = require_text(item["fact_id"], "active Fact id")
        if fact_id in fact_ids:
            raise LibraryError("external Fact Evidence duplicates an active Fact")
        fact_ids.add(fact_id)
        for key in ("fact_sha256", "interface_sha256", "release_sha256", "decision_sha256"):
            require_sha256(item[key], f"active Fact {key}")
        if (
            not isinstance(item["interface_schema_version"], int)
            or isinstance(item["interface_schema_version"], bool)
            or item["interface_schema_version"] < 1
        ):
                raise LibraryError("external Fact Evidence interface schema version is invalid")
    if audit_scope is not None and (
        audit.get("active_fact_ids") != sorted(fact_ids)
        or audit.get("facts") != len(fact_ids)
    ):
        raise LibraryError(
            "external Fact Evidence scoped audit Fact set does not match the capsule"
        )
    revoked_fact_ids = capsule["revoked_fact_ids"]
    if (
        not isinstance(revoked_fact_ids, list)
        or len(revoked_fact_ids) != len(set(revoked_fact_ids))
        or any(not isinstance(item, str) or not item.strip() for item in revoked_fact_ids)
        or fact_ids.intersection(revoked_fact_ids)
    ):
        raise LibraryError("external Fact Evidence revoked Fact ids are invalid")
    objects = capsule["objects"]
    if not isinstance(objects, list) or not objects:
        raise LibraryError("external Fact Evidence capsule objects are empty")
    seen_objects: set[tuple[str, str]] = set()
    available_fact_ids: set[str] = set()
    decoded_objects: dict[tuple[str, str], tuple[dict[str, Any], bytes]] = {}
    for item in objects:
        if not isinstance(item, dict) or set(item) != {
            "role",
            "object_id",
            "sha256",
            "bytes_base64",
        }:
            raise LibraryError("external Fact Evidence object fields are not exact")
        role = require_text(item["role"], "Evidence object role")
        object_id = require_text(item["object_id"], "Evidence object id")
        identity = (role, object_id)
        if identity in seen_objects:
            raise LibraryError("external Fact Evidence duplicates an object")
        seen_objects.add(identity)
        try:
            raw = base64.b64decode(item["bytes_base64"], validate=True)
        except (ValueError, TypeError) as exc:
            raise LibraryError("external Fact Evidence object base64 is invalid") from exc
        if hashlib.sha256(raw).hexdigest() != require_sha256(
            item["sha256"], "Evidence object sha256"
        ):
            raise LibraryError("external Fact Evidence object hash mismatch")
        if role == "fact":
            available_fact_ids.add(object_id)
        decoded_objects[identity] = (item, raw)
    if available_fact_ids != fact_ids:
        raise LibraryError("external Fact Evidence fact objects do not match active Facts")
    expected_objects: set[tuple[str, str]] = set()
    source_project_id = require_text(
        capsule["source_project_id"], "source_project_id"
    )
    for item in active_facts:
        fact_id = item["fact_id"]
        identities = {
            "fact": fact_id,
            "release": item["release_id"],
            "decision": item["decision_id"],
            "admission": item["acceptance_id"],
            "interface": fact_id,
        }
        expected_objects.update(identities.items())
        missing = sorted(set(identities.items()).difference(decoded_objects))
        if missing:
            raise LibraryError(
                "external Fact Evidence omits required lineage objects: "
                + ", ".join(f"{role}:{object_id}" for role, object_id in missing)
            )
        fact_meta, fact_raw = decoded_objects[("fact", fact_id)]
        if fact_meta["sha256"] != item["fact_sha256"]:
            raise LibraryError("external Fact Evidence Fact hash binding mismatch")
        parsed: dict[str, dict[str, Any]] = {}
        for role in ("release", "decision", "admission", "interface"):
            _, raw = decoded_objects[(role, identities[role])]
            try:
                value = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise LibraryError(
                    f"external Fact Evidence {role} object is not JSON"
                ) from exc
            if not isinstance(value, dict):
                raise LibraryError(
                    f"external Fact Evidence {role} object must be an object"
                )
            parsed[role] = value
        release = parsed["release"]
        decision = parsed["decision"]
        admission = parsed["admission"]
        interface = parsed["interface"]
        if (
            release.get("project_id") != source_project_id
            or release.get("release_id") != item["release_id"]
            or release.get("release_sha256") != item["release_sha256"]
            or fact_id not in release.get("fact_ids", [])
            or not any(
                candidate.get("fact_id") == fact_id
                and candidate.get("fact_sha256") == item["fact_sha256"]
                for candidate in release.get("candidates", [])
                if isinstance(candidate, dict)
            )
        ):
            raise LibraryError("external Fact Evidence release binding mismatch")
        if (
            decision.get("project_id") != source_project_id
            or decision.get("decision_id") != item["decision_id"]
            or decision.get("decision_sha256") != item["decision_sha256"]
            or decision.get("release_id") != item["release_id"]
            or decision.get("release_sha256") != item["release_sha256"]
            or decision.get("verdict") != "correct"
        ):
            raise LibraryError("external Fact Evidence decision binding mismatch")
        if (
            admission.get("project_id") != source_project_id
            or admission.get("acceptance_id") != item["acceptance_id"]
            or admission.get("release_id") != item["release_id"]
            or admission.get("release_sha256") != item["release_sha256"]
            or admission.get("decision_id") != item["decision_id"]
            or admission.get("decision_sha256") != item["decision_sha256"]
            or admission.get("gateway") != item["gateway"]
            or fact_id not in admission.get("fact_ids", [])
        ):
            raise LibraryError("external Fact Evidence admission binding mismatch")
        if (
            interface.get("fact_id") != fact_id
            or interface.get("interface_sha256") != item["interface_sha256"]
            or interface.get("schema_version") != item["interface_schema_version"]
        ):
            raise LibraryError("external Fact Evidence interface binding mismatch")
        if not fact_raw:
            raise LibraryError("external Fact Evidence Fact bytes are empty")
    if set(decoded_objects) != expected_objects:
        raise LibraryError("external Fact Evidence capsule contains unbound objects")
    fact_capsule_upstream_evidence_refs(capsule)


def cmd_evidence_fact_add(args: argparse.Namespace) -> dict[str, Any]:
    root = root_path(args.root)
    assert_repository(root)
    capsule_source = Path(args.capsule).expanduser().resolve()
    capsule = read_json(capsule_source)
    if not isinstance(capsule, dict):
        raise LibraryError("external Fact Evidence capsule must be an object")
    validate_fact_evidence_capsule(capsule)
    upstream_evidence_ids = validate_fact_capsule_upstream_bindings(
        root, capsule, require_current=True
    )
    digest, size, filename = store_regular_file(
        capsule_source,
        root / "objects" / "fact-evidence" / "by-sha256",
        ".json",
    )
    supersedes = sorted(set(args.supersedes_evidence_id))
    for prior_id in supersedes:
        prior = get_record(root, "evidence_items", prior_id)
        if (
            prior["evidence_kind"] != "external_fact_graph"
            or prior["source_project_id"] != capsule["source_project_id"]
        ):
            raise LibraryError("superseded Evidence belongs to another Fact project")
    payload = {
        **base_payload("evidence_item"),
        "evidence_kind": "external_fact_graph",
        "source": {
            "capsule_id": capsule["capsule_id"],
            "capsule_sha256": digest,
            "capsule_size": size,
            "capsule_path": f"objects/fact-evidence/by-sha256/{filename}",
            "active_fact_ids": sorted(item["fact_id"] for item in capsule["active_facts"]),
            "upstream_evidence_ids": upstream_evidence_ids,
        },
        "source_project_id": capsule["source_project_id"],
        "sync_mode": "explicit_user_fact_graph_bridge",
        "authorization": {
            "actor": require_text(args.actor, "actor"),
            "reason": require_text(args.reason, "reason"),
        },
        "trust_tier": "source_project_fact_certified",
        "bridge_eligible": True,
        "premise_eligible": False,
        "supersedes_evidence_ids": supersedes,
    }
    record = write_record(root, "evidence_items", payload, "fact_graph_evidence_admitted")
    return {
        "ok": True,
        "evidence_id": record["object_id"],
        "status": evidence_state_map(root)[record["object_id"]]["status"],
        "record": record,
    }


def cmd_evidence_disposition_add(args: argparse.Namespace) -> dict[str, Any]:
    root = root_path(args.root)
    assert_repository(root)
    states_before = evidence_state_map(root)
    evidence = get_record(root, "evidence_items", args.evidence_id)
    dispositions = load_collection(root, "evidence_dispositions")
    current_heads = evidence_disposition_heads(dispositions, evidence["object_id"])
    supersedes = sorted(set(args.supersedes_disposition_id))
    if supersedes != current_heads:
        raise LibraryError(
            "Evidence disposition must supersede the complete current head set"
        )
    status = require_text(args.status, "status")
    if status not in EVIDENCE_DISPOSITIONS:
        raise LibraryError("invalid Evidence disposition status")
    replacements = sorted(set(args.replacement_evidence_id))
    for replacement_id in replacements:
        if replacement_id == evidence["object_id"]:
            raise LibraryError("Evidence cannot replace itself")
        get_record(root, "evidence_items", replacement_id)
    if status == "superseded" and not replacements:
        raise LibraryError("superseded Evidence requires a replacement")
    artifact: dict[str, Any] | None = None
    if args.artifact:
        digest, size, filename = store_regular_file(
            Path(args.artifact),
            root / "objects" / "evidence-dispositions" / "by-sha256",
            ".artifact",
        )
        artifact = {
            "sha256": digest,
            "size": size,
            "path": f"objects/evidence-dispositions/by-sha256/{filename}",
        }
    payload = {
        **base_payload("evidence_disposition"),
        "evidence_id": evidence["object_id"],
        "status": status,
        "reason": require_text(args.reason, "reason"),
        "actor": require_text(args.actor, "actor"),
        "replacement_evidence_ids": replacements,
        "supersedes_disposition_ids": supersedes,
        "artifact": artifact,
        "premise_eligible": False,
    }
    record = write_record(
        root,
        "evidence_dispositions",
        payload,
        "evidence_disposition_recorded",
    )
    states_after = evidence_state_map(root)
    state = states_after[evidence["object_id"]]
    affected_evidence_ids = sorted(
        evidence_id
        for evidence_id in states_after
        if states_before.get(evidence_id) != states_after[evidence_id]
    )
    affected_bridges = [
        {
            "bridge_id": bridge["object_id"],
            "destination_project_id": bridge["destination_project_id"],
        }
        for bridge in load_collection(root, "bridge_capsules").values()
        if any(
            item["evidence_id"] in affected_evidence_ids
            for item in bridge["selection"]["items"]
        )
    ]
    affected_bridges.sort(
        key=lambda item: (item["destination_project_id"], item["bridge_id"])
    )
    return {
        "ok": True,
        "disposition_id": record["object_id"],
        "evidence_id": evidence["object_id"],
        **state,
        "affected_evidence_ids": affected_evidence_ids,
        "affected_bridges": affected_bridges,
        "record": record,
    }


def validate_bridge_selection(
    selection: dict[str, Any],
    *,
    destination_project_id: str,
) -> list[dict[str, Any]]:
    if set(selection) != {
        "schema_version",
        "destination_project_id",
        "items",
        "target_claim",
        "rationale",
    } or selection.get("schema_version") != 1:
        raise LibraryError("Evidence bridge selection fields are not exact")
    if selection["destination_project_id"] != destination_project_id:
        raise LibraryError("Evidence bridge destination project mismatch")
    require_text(selection["target_claim"], "target_claim")
    require_text(selection["rationale"], "rationale")
    items = selection["items"]
    if not isinstance(items, list) or not items:
        raise LibraryError("Evidence bridge selection items must be nonempty")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {
            "evidence_id",
            "node_ids",
            "fact_ids",
        }:
            raise LibraryError("Evidence bridge item fields are not exact")
        evidence_id = require_text(item["evidence_id"], "evidence_id")
        if evidence_id in seen:
            raise LibraryError("Evidence bridge duplicates an Evidence item")
        seen.add(evidence_id)
        node_ids = item["node_ids"]
        fact_ids = item["fact_ids"]
        if (
            not isinstance(node_ids, list)
            or not isinstance(fact_ids, list)
            or any(not isinstance(value, str) or not value.strip() for value in node_ids + fact_ids)
            or len(node_ids) != len(set(node_ids))
            or len(fact_ids) != len(set(fact_ids))
        ):
            raise LibraryError("Evidence bridge node/fact selections are invalid")
        normalized.append(
            {
                "evidence_id": evidence_id,
                "node_ids": sorted(node_ids),
                "fact_ids": sorted(fact_ids),
            }
        )
    return sorted(normalized, key=lambda item: item["evidence_id"])


def cmd_bridge_prepare(args: argparse.Namespace) -> dict[str, Any]:
    root = root_path(args.root)
    config = assert_repository(root)
    destination_project_id = require_text(
        args.destination_project_id, "destination_project_id"
    )
    selection_source = Path(args.selection).expanduser().resolve()
    selection = read_json(selection_source)
    if not isinstance(selection, dict):
        raise LibraryError("Evidence bridge selection must be an object")
    items = validate_bridge_selection(
        selection, destination_project_id=destination_project_id
    )
    states = evidence_state_map(root)
    bindings: list[dict[str, Any]] = []
    for item in items:
        evidence = get_record(root, "evidence_items", item["evidence_id"])
        state = states[evidence["object_id"]]
        if not state["bridge_eligible"]:
            raise LibraryError(
                f"Evidence is not current and bridge eligible: {evidence['object_id']}"
            )
        if evidence["evidence_kind"] == "reviewed_paper_graph":
            if not item["node_ids"] or item["fact_ids"]:
                raise LibraryError("Paper Evidence bridge requires node_ids only")
            attestation = read_json(root / evidence["attestation"]["path"])
            if not isinstance(attestation, dict) or not set(item["node_ids"]).issubset(
                set(attestation.get("node_ids", []))
            ):
                raise LibraryError("Paper Evidence bridge selects an unattested node")
        elif evidence["evidence_kind"] == "external_fact_graph":
            allowed = set(evidence["source"]["active_fact_ids"])
            if not item["fact_ids"] or item["node_ids"]:
                raise LibraryError("Fact Graph Evidence bridge requires fact_ids only")
            if not set(item["fact_ids"]).issubset(allowed):
                raise LibraryError("Evidence bridge selects a noncaptured source Fact")
        else:
            raise LibraryError("unsupported Evidence kind")
        bindings.append(
            {
                **item,
                "evidence_kind": evidence["evidence_kind"],
                "evidence_record_sha256": evidence["record_sha256"],
                "state": state["status"],
                "disposition_head_id": state["disposition_head_id"],
            }
        )
    payload = {
        **base_payload("evidence_bridge_capsule"),
        "contract_revision": BRIDGE_CAPSULE_REVISION,
        "library_id": config["library_id"],
        "destination_project_id": destination_project_id,
        "selection": {
            "target_claim": selection["target_claim"],
            "rationale": selection["rationale"],
            "items": bindings,
        },
        "authorization": {
            "actor": require_text(args.actor, "actor"),
            "reason": require_text(args.reason, "reason"),
        },
        "bridge_status": "prepared_nontruth",
        "requires_destination_candidate_release": True,
        "requires_fresh_verifier": True,
        "requires_fact_gateway": True,
        "premise_eligible": False,
    }
    record = write_record(root, "bridge_capsules", payload, "evidence_bridge_prepared")
    if args.output:
        output = Path(args.output).expanduser().resolve()
        if output.exists():
            if read_json(output) != record:
                raise LibraryError(f"refusing to overwrite different bridge capsule: {output}")
        else:
            atomic_json(output, record)
    return {
        "ok": True,
        "bridge_id": record["object_id"],
        "bridge_record_sha256": record["record_sha256"],
        "destination_project_id": destination_project_id,
        "output": str(Path(args.output).expanduser().resolve()) if args.output else "",
        "truth_effect": "none",
        "premise_eligible": False,
    }


def bridge_check(root: Path, bridge: dict[str, Any]) -> dict[str, Any]:
    states = evidence_state_map(root)
    changes: list[dict[str, str]] = []
    for binding in bridge["selection"]["items"]:
        evidence = get_record(root, "evidence_items", binding["evidence_id"])
        current = states[evidence["object_id"]]
        if (
            evidence["record_sha256"] != binding["evidence_record_sha256"]
            or current["status"] != binding["state"]
            or current["disposition_head_id"] != binding["disposition_head_id"]
            or not current["bridge_eligible"]
        ):
            changes.append(
                {
                    "evidence_id": evidence["object_id"],
                    "prepared_status": binding["state"],
                    "current_status": current["status"],
                    "prepared_head": binding["disposition_head_id"],
                    "current_head": current["disposition_head_id"],
                }
            )
    return {
        "ok": not changes,
        "bridge_id": bridge["object_id"],
        "bridge_record_sha256": bridge["record_sha256"],
        "destination_project_id": bridge["destination_project_id"],
        "current": not changes,
        "changes": changes,
        "truth_effect": "none",
        "premise_eligible": False,
    }


def cmd_bridge_check(args: argparse.Namespace) -> dict[str, Any]:
    root = root_path(args.root)
    assert_repository(root)
    bridge = get_record(root, "bridge_capsules", args.bridge_id)
    result = bridge_check(root, bridge)
    if not result["ok"]:
        raise LibraryError("Evidence bridge is stale or no longer eligible")
    return result


def cmd_evidence_query(args: argparse.Namespace) -> dict[str, Any]:
    root = root_path(args.root)
    assert_repository(root)
    evidence_items = load_collection(root, "evidence_items")
    states = evidence_state_map(root)
    papers = load_collection(root, "papers")
    query = normalized_whitespace(args.query or "").casefold()
    terms = query.split()
    limit = args.limit
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
        raise LibraryError("Evidence query limit must be between 1 and 100")
    rank = {"external_fact_graph": 0, "reviewed_paper_graph": 1}
    results: list[dict[str, Any]] = []
    for evidence_id, record in sorted(evidence_items.items()):
        state = states[evidence_id]
        if not args.include_inactive and not state["bridge_eligible"]:
            continue
        paper: dict[str, Any] | None = None
        if record["evidence_kind"] == "reviewed_paper_graph":
            paper = papers.get(record["source"]["paper_id"])
        searchable = json.dumps(
            {"evidence": record, "state": state, "paper": paper or {}},
            ensure_ascii=False,
            sort_keys=True,
        ).casefold()
        if any(term not in searchable for term in terms):
            continue
        results.append(
            {
                "evidence_id": evidence_id,
                "evidence_kind": record["evidence_kind"],
                "trust_tier": record["trust_tier"],
                "status": state["status"],
                "bridge_eligible": state["bridge_eligible"],
                "stale_upstream_evidence_ids": state[
                    "stale_upstream_evidence_ids"
                ],
                "source_project_id": record["source_project_id"],
                "source": record["source"],
                "paper": (
                    {
                        "paper_id": paper["object_id"],
                        "title": paper["bibliographic"]["title"],
                        "identity": paper["identity"],
                    }
                    if paper is not None
                    else None
                ),
                "premise_eligible": False,
            }
        )
    results.sort(
        key=lambda item: (
            rank.get(item["evidence_kind"], 99),
            item["evidence_id"],
        )
    )
    selected = results[:limit]
    return {
        "ok": True,
        "query": query,
        "include_inactive": bool(args.include_inactive),
        "trust_order": ["external_fact_graph", "reviewed_paper_graph"],
        "matched_count": len(results),
        "returned_count": len(selected),
        "results": selected,
        "truth_effect": "none",
        "premise_eligible": False,
    }


def build_catalog(root: Path) -> dict[str, Any]:
    papers = load_collection(root, "papers")
    versions = load_collection(root, "versions")
    graphs = load_collection(root, "graphs")
    corrections = load_collection(root, "corrections")
    source_checks = load_collection(root, "source_checks")
    evidence_items = load_collection(root, "evidence_items")
    evidence_dispositions = load_collection(root, "evidence_dispositions")
    bridge_capsules = load_collection(root, "bridge_capsules")
    evidence_states = evidence_state_map(root)
    version_superseded = {
        item
        for record in versions.values()
        for item in record.get("supersedes_version_ids", [])
    }
    graph_superseded = {
        item
        for record in graphs.values()
        for item in record.get("supersedes_graph_ids", [])
    }
    correction_superseded = {
        item
        for record in corrections.values()
        for item in record.get("supersedes_correction_ids", [])
    }
    entries = []
    for paper_id, paper in sorted(papers.items()):
        arxiv_latest: dict[str, int] = {}
        for record in versions.values():
            if record["paper_id"] != paper_id:
                continue
            arxiv_id = record.get("identifiers", {}).get("arxiv_id", "")
            if not arxiv_id:
                continue
            base, number, _ = normalize_arxiv_id(arxiv_id)
            if number is not None:
                arxiv_latest[base] = max(arxiv_latest.get(base, 0), number)

        def version_is_current(record_id: str, record: dict[str, Any]) -> bool:
            if record_id in version_superseded:
                return False
            arxiv_id = record.get("identifiers", {}).get("arxiv_id", "")
            if not arxiv_id:
                return True
            base, number, _ = normalize_arxiv_id(arxiv_id)
            return number is not None and number == arxiv_latest.get(base)

        paper_versions = [
            {**record, "current": version_is_current(record_id, record)}
            for record_id, record in sorted(versions.items())
            if record["paper_id"] == paper_id
        ]
        paper_graphs = [
            {**record, "current": record_id not in graph_superseded}
            for record_id, record in sorted(graphs.items())
            if record["paper_id"] == paper_id
        ]
        paper_corrections = [
            {**record, "current": record_id not in correction_superseded}
            for record_id, record in sorted(corrections.items())
            if record["paper_id"] == paper_id
        ]
        paper_source_checks = [
            record
            for _, record in sorted(source_checks.items())
            if record["paper_id"] == paper_id
        ]
        latest_check_id = ""
        if paper_source_checks:
            latest_check_id = max(
                paper_source_checks,
                key=lambda record: (record["checked_at"], record["object_id"]),
            )["object_id"]
        entries.append(
            {
                "paper": paper,
                "versions": paper_versions,
                "graphs": paper_graphs,
                "corrections": paper_corrections,
                "source_checks": [
                    {**record, "latest": record["object_id"] == latest_check_id}
                    for record in paper_source_checks
                ],
            }
        )
    state = {
        collection: sorted(
            (object_id, record["record_sha256"])
            for object_id, record in load_collection(root, collection).items()
        )
        for collection in COLLECTION_PREFIXES
    }
    core = {
        "schema_version": SCHEMA_VERSION,
        "contract_revision": "chalxius-paper-library-catalog-1",
        "source_state_sha256": object_hash(state),
        "authority": "derived_nontruth_index",
        "truth_effect": "none",
        "entries": entries,
        "evidence": [
            {**record, **evidence_states[evidence_id]}
            for evidence_id, record in sorted(evidence_items.items())
        ],
        "evidence_dispositions": [
            record for _, record in sorted(evidence_dispositions.items())
        ],
        "bridge_capsules": [
            {**record, "current": bridge_check(root, record)["current"]}
            for _, record in sorted(bridge_capsules.items())
        ],
    }
    return {**core, "catalog_sha256": object_hash(core)}


def build_sqlite_index(root: Path, catalog: dict[str, Any]) -> Path:
    index_directory = root / "index"
    index_directory.mkdir(parents=True, exist_ok=True)
    target = index_directory / "library.sqlite3"
    descriptor, temporary = tempfile.mkstemp(
        prefix=".library.", suffix=".sqlite3", dir=index_directory
    )
    os.close(descriptor)
    temporary_path = Path(temporary)
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(temporary_path)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(
            """
            CREATE TABLE metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                identity_scheme TEXT NOT NULL,
                identity_key TEXT NOT NULL,
                title TEXT NOT NULL,
                authors_json TEXT NOT NULL,
                doi TEXT NOT NULL,
                arxiv_id TEXT NOT NULL,
                issued TEXT NOT NULL,
                citekey TEXT NOT NULL,
                record_json TEXT NOT NULL,
                UNIQUE(identity_scheme, identity_key)
            );
            CREATE TABLE versions (
                version_id TEXT PRIMARY KEY,
                paper_id TEXT NOT NULL REFERENCES papers(paper_id),
                label TEXT NOT NULL,
                kind TEXT NOT NULL,
                source_locator TEXT NOT NULL,
                retrieved_at TEXT NOT NULL,
                published_at TEXT NOT NULL,
                arxiv_id TEXT NOT NULL,
                pdf_sha256 TEXT NOT NULL,
                is_current INTEGER NOT NULL CHECK(is_current IN (0, 1)),
                record_json TEXT NOT NULL
            );
            CREATE TABLE graphs (
                graph_id TEXT PRIMARY KEY,
                paper_id TEXT NOT NULL REFERENCES papers(paper_id),
                version_id TEXT NOT NULL REFERENCES versions(version_id),
                graph_kind TEXT NOT NULL,
                source_project_id TEXT NOT NULL,
                tree_sha256 TEXT NOT NULL,
                chalxius_version TEXT NOT NULL,
                evidence_status TEXT NOT NULL,
                is_current INTEGER NOT NULL CHECK(is_current IN (0, 1)),
                record_json TEXT NOT NULL
            );
            CREATE TABLE corrections (
                correction_id TEXT PRIMARY KEY,
                paper_id TEXT NOT NULL REFERENCES papers(paper_id),
                version_id TEXT NOT NULL REFERENCES versions(version_id),
                graph_id TEXT NOT NULL,
                correction_kind TEXT NOT NULL,
                status TEXT NOT NULL,
                summary TEXT NOT NULL,
                is_current INTEGER NOT NULL CHECK(is_current IN (0, 1)),
                record_json TEXT NOT NULL
            );
            CREATE TABLE source_checks (
                check_id TEXT PRIMARY KEY,
                paper_id TEXT NOT NULL REFERENCES papers(paper_id),
                source_scheme TEXT NOT NULL,
                source_identity TEXT NOT NULL,
                checked_at TEXT NOT NULL,
                observed_version INTEGER NOT NULL,
                observed_arxiv_id TEXT NOT NULL,
                status TEXT NOT NULL,
                is_latest INTEGER NOT NULL CHECK(is_latest IN (0, 1)),
                response_sha256 TEXT NOT NULL,
                record_json TEXT NOT NULL
            );
            CREATE TABLE evidence_items (
                evidence_id TEXT PRIMARY KEY,
                evidence_kind TEXT NOT NULL,
                source_project_id TEXT NOT NULL,
                trust_tier TEXT NOT NULL,
                status TEXT NOT NULL,
                bridge_eligible INTEGER NOT NULL CHECK(bridge_eligible IN (0, 1)),
                record_json TEXT NOT NULL
            );
            CREATE TABLE evidence_dispositions (
                disposition_id TEXT PRIMARY KEY,
                evidence_id TEXT NOT NULL REFERENCES evidence_items(evidence_id),
                status TEXT NOT NULL,
                actor TEXT NOT NULL,
                reason TEXT NOT NULL,
                record_json TEXT NOT NULL
            );
            CREATE TABLE bridge_capsules (
                bridge_id TEXT PRIMARY KEY,
                destination_project_id TEXT NOT NULL,
                bridge_status TEXT NOT NULL,
                is_current INTEGER NOT NULL CHECK(is_current IN (0, 1)),
                record_json TEXT NOT NULL
            );
            CREATE INDEX versions_by_paper ON versions(paper_id, kind, label);
            CREATE INDEX graphs_by_paper ON graphs(paper_id, graph_kind);
            CREATE INDEX corrections_by_paper ON corrections(paper_id, status);
            CREATE INDEX source_checks_by_paper ON source_checks(paper_id, checked_at);
            CREATE INDEX evidence_by_kind ON evidence_items(evidence_kind, status);
            CREATE INDEX evidence_dispositions_by_item ON evidence_dispositions(evidence_id, status);
            CREATE INDEX bridges_by_destination ON bridge_capsules(destination_project_id, is_current);
            """
        )
        metadata = {
            "contract_revision": "chalxius-paper-library-sqlite-1",
            "source_state_sha256": catalog["source_state_sha256"],
            "catalog_sha256": catalog["catalog_sha256"],
            "authority": "derived_nontruth_index",
            "truth_effect": "none",
        }
        connection.executemany(
            "INSERT INTO metadata(key, value) VALUES (?, ?)", metadata.items()
        )
        for entry in catalog["entries"]:
            paper = entry["paper"]
            identity = paper.get("identity", {})
            if not identity:
                zotero = paper.get("zotero", {})
                identity = {
                    "scheme": "zotero",
                    "key": f"{zotero.get('library_id', '')}:{zotero.get('item_key', '')}",
                }
            bibliographic = paper["bibliographic"]
            connection.execute(
                """INSERT INTO papers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    paper["object_id"],
                    identity["scheme"],
                    identity["key"],
                    bibliographic["title"],
                    canonical_bytes(bibliographic["authors"]).decode("utf-8"),
                    bibliographic["doi"],
                    bibliographic["arxiv_id"],
                    bibliographic["issued"],
                    paper.get("zotero", {}).get("citekey", ""),
                    canonical_bytes(paper).decode("utf-8"),
                ),
            )
            for version in entry["versions"]:
                connection.execute(
                    """INSERT INTO versions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        version["object_id"],
                        paper["object_id"],
                        version["version_label"],
                        version["version_kind"],
                        version["source_locator"],
                        version["retrieved_at"],
                        version["published_at"],
                        version["identifiers"]["arxiv_id"],
                        version["pdf"]["sha256"],
                        int(version["current"]),
                        canonical_bytes(version).decode("utf-8"),
                    ),
                )
            for graph in entry["graphs"]:
                connection.execute(
                    """INSERT INTO graphs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        graph["object_id"],
                        paper["object_id"],
                        graph["version_id"],
                        graph["graph_kind"],
                        graph["source"]["project_id"],
                        graph["tree"]["sha256"],
                        graph["chalxius"]["version"],
                        graph["evidence_status"],
                        int(graph["current"]),
                        canonical_bytes(graph).decode("utf-8"),
                    ),
                )
            for correction in entry["corrections"]:
                connection.execute(
                    """INSERT INTO corrections VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        correction["object_id"],
                        paper["object_id"],
                        correction["version_id"],
                        correction["graph_id"],
                        correction["correction_kind"],
                        correction["status"],
                        correction["summary"],
                        int(correction["current"]),
                        canonical_bytes(correction).decode("utf-8"),
                    ),
                )
            for source_check in entry["source_checks"]:
                connection.execute(
                    """INSERT INTO source_checks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        source_check["object_id"],
                        paper["object_id"],
                        source_check["source"]["scheme"],
                        source_check["source"]["identity_key"],
                        source_check["checked_at"],
                        source_check["observation"]["version"],
                        source_check["observation"]["arxiv_id"],
                        source_check["status"],
                        int(source_check["latest"]),
                        source_check["response"]["sha256"],
                        canonical_bytes(source_check).decode("utf-8"),
                    ),
                )
        for evidence in catalog["evidence"]:
            connection.execute(
                """INSERT INTO evidence_items VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    evidence["object_id"],
                    evidence["evidence_kind"],
                    evidence["source_project_id"],
                    evidence["trust_tier"],
                    evidence["status"],
                    int(evidence["bridge_eligible"]),
                    canonical_bytes(evidence).decode("utf-8"),
                ),
            )
        for disposition in catalog["evidence_dispositions"]:
            connection.execute(
                """INSERT INTO evidence_dispositions VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    disposition["object_id"],
                    disposition["evidence_id"],
                    disposition["status"],
                    disposition["actor"],
                    disposition["reason"],
                    canonical_bytes(disposition).decode("utf-8"),
                ),
            )
        for bridge in catalog["bridge_capsules"]:
            connection.execute(
                """INSERT INTO bridge_capsules VALUES (?, ?, ?, ?, ?)""",
                (
                    bridge["object_id"],
                    bridge["destination_project_id"],
                    bridge["bridge_status"],
                    int(bridge["current"]),
                    canonical_bytes(bridge).decode("utf-8"),
                ),
            )
        connection.commit()
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if integrity != ("ok",):
            raise LibraryError("new SQLite index failed integrity_check")
        connection.close()
        connection = None
        with temporary_path.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary_path, target)
    finally:
        if connection is not None:
            connection.close()
        if temporary_path.exists():
            temporary_path.unlink()
    return target


def verify_sqlite_index(path: Path, catalog: dict[str, Any]) -> None:
    if path.is_symlink() or not path.is_file():
        raise LibraryError(f"invalid SQLite index: {path}")
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if integrity != ("ok",):
            raise LibraryError("SQLite index integrity_check failed")
        if connection.execute("PRAGMA foreign_key_check").fetchall():
            raise LibraryError("SQLite index foreign-key check failed")
        metadata = dict(connection.execute("SELECT key, value FROM metadata"))
        expected = {
            "contract_revision": "chalxius-paper-library-sqlite-1",
            "source_state_sha256": catalog["source_state_sha256"],
            "catalog_sha256": catalog["catalog_sha256"],
            "authority": "derived_nontruth_index",
            "truth_effect": "none",
        }
        if metadata != expected:
            raise LibraryError("SQLite index is stale or has wrong authority metadata")
        expected_counts = {
            "papers": len(catalog["entries"]),
            "versions": sum(len(entry["versions"]) for entry in catalog["entries"]),
            "graphs": sum(len(entry["graphs"]) for entry in catalog["entries"]),
            "corrections": sum(
                len(entry["corrections"]) for entry in catalog["entries"]
            ),
            "source_checks": sum(
                len(entry["source_checks"]) for entry in catalog["entries"]
            ),
            "evidence_items": len(catalog["evidence"]),
            "evidence_dispositions": len(catalog["evidence_dispositions"]),
            "bridge_capsules": len(catalog["bridge_capsules"]),
        }
        for table, expected_count in expected_counts.items():
            actual_count = connection.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
            if actual_count != expected_count:
                raise LibraryError(f"SQLite index count mismatch for {table}")
    except sqlite3.DatabaseError as exc:
        raise LibraryError(f"SQLite index verification failed: {exc}") from exc
    finally:
        connection.close()


def cmd_index(args: argparse.Namespace) -> dict[str, Any]:
    root = root_path(args.root)
    assert_repository(root)
    with library_lock(root):
        catalog = build_catalog(root)
        atomic_json(root / "index" / "catalog.json", catalog)
        sqlite_index = build_sqlite_index(root, catalog)
    return {
        "ok": True,
        "catalog_sha256": catalog["catalog_sha256"],
        "paper_count": len(catalog["entries"]),
        "path": str(root / "index" / "catalog.json"),
        "sqlite_path": str(sqlite_index),
    }


def validate_references(root: Path) -> dict[str, int]:
    papers = load_collection(root, "papers")
    versions = load_collection(root, "versions")
    graphs = load_collection(root, "graphs")
    corrections = load_collection(root, "corrections")
    source_checks = load_collection(root, "source_checks")
    evidence_items = load_collection(root, "evidence_items")
    evidence_dispositions = load_collection(root, "evidence_dispositions")
    bridge_capsules = load_collection(root, "bridge_capsules")
    for version in versions.values():
        if version["paper_id"] not in papers:
            raise LibraryError("version references missing paper")
        for prior in version["supersedes_version_ids"]:
            if prior not in versions:
                raise LibraryError("version references missing superseded version")
    for graph in graphs.values():
        if graph["paper_id"] not in papers or graph["version_id"] not in versions:
            raise LibraryError("graph references missing paper/version")
        if versions[graph["version_id"]]["paper_id"] != graph["paper_id"]:
            raise LibraryError("graph paper/version mismatch")
        if versions[graph["version_id"]]["pdf"]["sha256"] != graph["pdf_sha256"]:
            raise LibraryError("graph PDF hash does not match its exact paper version")
        for prior in graph["supersedes_graph_ids"]:
            if prior not in graphs:
                raise LibraryError("graph references missing superseded graph")
    for correction in corrections.values():
        if correction["paper_id"] not in papers or correction["version_id"] not in versions:
            raise LibraryError("correction references missing paper/version")
        graph_id = correction["graph_id"]
        if graph_id and graph_id not in graphs:
            raise LibraryError("correction references missing graph")
        for prior in correction["supersedes_correction_ids"]:
            if prior not in corrections:
                raise LibraryError("correction references missing predecessor")
    for source_check in source_checks.values():
        if source_check["paper_id"] not in papers:
            raise LibraryError("source check references missing paper")
    for evidence in evidence_items.values():
        if evidence["evidence_kind"] not in EVIDENCE_KINDS:
            raise LibraryError("Evidence item kind is invalid")
        for prior in evidence["supersedes_evidence_ids"]:
            if prior not in evidence_items:
                raise LibraryError("Evidence item references missing predecessor")
        if evidence["evidence_kind"] == "reviewed_paper_graph":
            source = evidence["source"]
            if (
                source["paper_id"] not in papers
                or source["version_id"] not in versions
                or source["graph_id"] not in graphs
            ):
                raise LibraryError("Paper Evidence references missing paper/version/graph")
            graph = graphs[source["graph_id"]]
            if (
                graph["paper_id"] != source["paper_id"]
                or graph["version_id"] != source["version_id"]
                or graph["pdf_sha256"] != source["pdf_sha256"]
                or source["paper_snapshot_id"] not in graph["source"]["snapshot_ids"]
            ):
                raise LibraryError("Paper Evidence exact binding mismatch")
        elif evidence["evidence_kind"] == "external_fact_graph":
            source = evidence["source"]
            if not source["active_fact_ids"]:
                raise LibraryError("Fact Graph Evidence has no active Facts")
            upstream_ids = source.get("upstream_evidence_ids", [])
            if (
                not isinstance(upstream_ids, list)
                or len(upstream_ids) != len(set(upstream_ids))
                or any(not isinstance(item, str) or not item.strip() for item in upstream_ids)
            ):
                raise LibraryError("Fact Graph Evidence upstream ids are invalid")
            missing = sorted(set(upstream_ids).difference(evidence_items))
            if missing:
                raise LibraryError(
                    "Fact Graph Evidence references missing upstream Evidence: "
                    + ", ".join(missing)
                )
    for disposition in evidence_dispositions.values():
        if disposition["evidence_id"] not in evidence_items:
            raise LibraryError("Evidence disposition references missing Evidence")
        for prior in disposition["supersedes_disposition_ids"]:
            if prior not in evidence_dispositions:
                raise LibraryError("Evidence disposition references missing predecessor")
        for replacement in disposition["replacement_evidence_ids"]:
            if replacement not in evidence_items:
                raise LibraryError("Evidence disposition references missing replacement")
    for evidence_id in evidence_items:
        if len(evidence_disposition_heads(evidence_dispositions, evidence_id)) > 1:
            raise LibraryError("Evidence disposition history has multiple current heads")
    evidence_state_map(root)
    for bridge in bridge_capsules.values():
        for binding in bridge["selection"]["items"]:
            if binding["evidence_id"] not in evidence_items:
                raise LibraryError("Evidence bridge references missing Evidence")
    return {
        "papers": len(papers),
        "versions": len(versions),
        "graphs": len(graphs),
        "corrections": len(corrections),
        "source_checks": len(source_checks),
        "evidence_items": len(evidence_items),
        "evidence_dispositions": len(evidence_dispositions),
        "bridge_capsules": len(bridge_capsules),
    }


def verify_objects(root: Path) -> dict[str, int]:
    assert_repository(root)
    versions = load_collection(root, "versions")
    exports = load_collection(root, "zotero_exports")
    graphs = load_collection(root, "graphs")
    corrections = load_collection(root, "corrections")
    source_checks = load_collection(root, "source_checks")
    evidence_items = load_collection(root, "evidence_items")
    evidence_dispositions = load_collection(root, "evidence_dispositions")
    for version in versions.values():
        pdf = root / version["pdf"]["path"]
        if pdf.is_symlink() or not pdf.is_file() or file_hash(pdf) != version["pdf"]["sha256"]:
            raise LibraryError(f"PDF verification failed: {pdf}")
        with pdf.open("rb") as handle:
            if handle.read(5) != b"%PDF-":
                raise LibraryError(f"stored object is not PDF: {pdf}")
    for export in exports.values():
        artifact = root / export["artifact"]["path"]
        if (
            artifact.is_symlink()
            or not artifact.is_file()
            or file_hash(artifact) != export["artifact"]["sha256"]
        ):
            raise LibraryError(f"Zotero export verification failed: {artifact}")
        read_json(artifact)
    for graph in graphs.values():
        verify_graph_object(root / graph["tree"]["path"], graph["tree"]["sha256"])
    for correction in corrections.values():
        artifact = correction.get("artifact")
        if artifact:
            path = root / artifact["path"]
            if path.is_symlink() or not path.is_file() or file_hash(path) != artifact["sha256"]:
                raise LibraryError(f"correction artifact verification failed: {path}")
    for source_check in source_checks.values():
        response = source_check["response"]
        path = root / response["path"]
        if path.is_symlink() or not path.is_file() or file_hash(path) != response["sha256"]:
            raise LibraryError(f"source response verification failed: {path}")
        parsed = parse_arxiv_feed(path.read_bytes())
        observed_base = source_check["observation"]["base_arxiv_id"]
        if observed_base not in parsed:
            raise LibraryError("source response does not contain its observation")
    paper_attestations = 0
    fact_capsules = 0
    for evidence in evidence_items.values():
        if evidence["evidence_kind"] == "reviewed_paper_graph":
            artifact = evidence["attestation"]
            path = root / artifact["path"]
            if (
                path.is_symlink()
                or not path.is_file()
                or file_hash(path) != artifact["sha256"]
            ):
                raise LibraryError(f"paper Evidence attestation verification failed: {path}")
            graph = graphs[evidence["source"]["graph_id"]]
            attestation = read_json(path)
            if not isinstance(attestation, dict):
                raise LibraryError("paper Evidence attestation is not an object")
            validate_paper_attestation(attestation, graph=graph)
            paper_attestations += 1
        elif evidence["evidence_kind"] == "external_fact_graph":
            source = evidence["source"]
            path = root / source["capsule_path"]
            if (
                path.is_symlink()
                or not path.is_file()
                or file_hash(path) != source["capsule_sha256"]
            ):
                raise LibraryError(f"Fact Evidence capsule verification failed: {path}")
            capsule = read_json(path)
            if not isinstance(capsule, dict):
                raise LibraryError("Fact Evidence capsule is not an object")
            validate_fact_evidence_capsule(capsule)
            derived_upstream_ids = validate_fact_capsule_upstream_bindings(
                root, capsule, require_current=False
            )
            if source.get("upstream_evidence_ids", []) != derived_upstream_ids:
                raise LibraryError(
                    "Fact Evidence stored upstream dependency binding mismatch"
                )
            fact_capsules += 1
    disposition_artifacts = 0
    for disposition in evidence_dispositions.values():
        artifact = disposition.get("artifact")
        if not artifact:
            continue
        path = root / artifact["path"]
        if (
            path.is_symlink()
            or not path.is_file()
            or file_hash(path) != artifact["sha256"]
        ):
            raise LibraryError(f"Evidence disposition artifact verification failed: {path}")
        disposition_artifacts += 1
    return {
        "pdfs": len({record["pdf"]["sha256"] for record in versions.values()}),
        "zotero_exports": len(exports),
        "graph_trees": len({record["tree"]["sha256"] for record in graphs.values()}),
        "correction_artifacts": sum(
            1 for record in corrections.values() if record.get("artifact")
        ),
        "source_responses": len(
            {record["response"]["sha256"] for record in source_checks.values()}
        ),
        "paper_evidence_attestations": paper_attestations,
        "fact_evidence_capsules": fact_capsules,
        "evidence_disposition_artifacts": disposition_artifacts,
    }


def cmd_verify(args: argparse.Namespace) -> dict[str, Any]:
    root = root_path(args.root)
    assert_repository(root)
    events = load_events(root)
    counts = validate_references(root)
    object_counts = verify_objects(root)
    recorded_ids = {event["object_id"] for event in events}
    for collection in COLLECTION_PREFIXES:
        for object_id in load_collection(root, collection):
            if object_id not in recorded_ids:
                raise LibraryError(f"record missing event: {object_id}")
    expected_catalog = build_catalog(root)
    catalog_path = root / "index" / "catalog.json"
    if catalog_path.exists() and read_json(catalog_path) != expected_catalog:
        raise LibraryError("derived catalog is stale or corrupted")
    sqlite_path = root / "index" / "library.sqlite3"
    if sqlite_path.exists():
        verify_sqlite_index(sqlite_path, expected_catalog)
    return {
        "ok": True,
        "root": str(root),
        "events": len(events),
        **counts,
        **object_counts,
        "catalog": "verified" if catalog_path.exists() else "absent",
        "sqlite_index": "verified" if sqlite_path.exists() else "absent",
    }


def cmd_context_export(args: argparse.Namespace) -> dict[str, Any]:
    root = root_path(args.root)
    assert_repository(root)
    graph_ids = sorted(set(args.graph_id))
    if not graph_ids:
        raise LibraryError("at least one --graph-id is required")
    graphs = [get_record(root, "graphs", graph_id) for graph_id in graph_ids]
    paper_ids = sorted({graph["paper_id"] for graph in graphs})
    version_ids = sorted({graph["version_id"] for graph in graphs})
    papers = [get_record(root, "papers", paper_id) for paper_id in paper_ids]
    versions = [get_record(root, "versions", version_id) for version_id in version_ids]
    all_corrections = load_collection(root, "corrections")
    corrections = [
        record
        for _, record in sorted(all_corrections.items())
        if record["paper_id"] in paper_ids
        and (
            record["version_id"] in version_ids
            or (record["graph_id"] and record["graph_id"] in graph_ids)
        )
    ]
    all_source_checks = load_collection(root, "source_checks")
    latest_source_checks: list[dict[str, Any]] = []
    for paper_id in paper_ids:
        matches = [
            record
            for record in all_source_checks.values()
            if record["paper_id"] == paper_id
        ]
        if matches:
            latest_source_checks.append(
                max(matches, key=lambda record: (record["checked_at"], record["object_id"]))
            )
    core = {
        "schema_version": SCHEMA_VERSION,
        "contract_revision": CAPSULE_REVISION,
        "purpose": "cross_project_literature_context",
        "authority": "frozen_nontruth_source_context",
        "truth_effect": "none",
        "premise_eligible": False,
        "trust_order": [
            "active_local_fact",
            "external_fact_evidence",
            "certified_paper_evidence",
            "reviewed_paper_graph",
            "research",
            "background",
        ],
        "papers": papers,
        "versions": versions,
        "graphs": graphs,
        "corrections": corrections,
        "latest_source_checks": sorted(
            latest_source_checks, key=lambda record: record["paper_id"]
        ),
    }
    capsule = {**core, "capsule_id": f"plc-{object_hash(core)}"}
    output = Path(args.output).expanduser().resolve()
    if output.exists():
        if read_json(output) != capsule:
            raise LibraryError(f"refusing to overwrite different capsule: {output}")
    else:
        atomic_json(output, capsule)
    return {
        "ok": True,
        "capsule_id": capsule["capsule_id"],
        "path": str(output),
        "graph_count": len(graphs),
        "truth_effect": "none",
        "premise_eligible": False,
    }


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(description=__doc__)
    commands = top.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init")
    init.add_argument("--root", required=True)
    init.add_argument("--library-id", required=True)
    init.add_argument("--name", required=True)
    init.set_defaults(function=cmd_init)

    zotero = commands.add_parser("zotero-snapshot")
    zotero.add_argument("--root", required=True)
    zotero.add_argument("--library-id", required=True)
    zotero.add_argument("--input", required=True)
    zotero.add_argument(
        "--format",
        choices=["csl-json", "better-bibtex-json", "zotero-json", "other-json"],
        default="csl-json",
    )
    zotero.set_defaults(function=cmd_zotero_snapshot)

    paper = commands.add_parser("paper-add")
    paper.add_argument("--root", required=True)
    paper.add_argument(
        "--identity-scheme", choices=["arxiv", "doi", "isbn", "local", "zotero"]
    )
    paper.add_argument("--identity-key")
    paper.add_argument("--local-key")
    paper.add_argument("--zotero-library-id")
    paper.add_argument("--zotero-item-key")
    paper.add_argument("--zotero-export-id")
    paper.add_argument("--citekey")
    paper.add_argument("--title", required=True)
    paper.add_argument("--author", action="append", default=[])
    paper.add_argument("--doi")
    paper.add_argument("--arxiv-id")
    paper.add_argument("--issued")
    paper.set_defaults(function=cmd_paper_add)

    version = commands.add_parser("version-add")
    version.add_argument("--root", required=True)
    version.add_argument("--paper-id", required=True)
    version.add_argument("--label", required=True)
    version.add_argument(
        "--kind",
        choices=[
            "arxiv",
            "journal",
            "conference",
            "author_manuscript",
            "book_chapter",
            "other",
        ],
        required=True,
    )
    version.add_argument("--pdf", required=True)
    version.add_argument("--source-locator", required=True)
    version.add_argument("--retrieved-at", required=True)
    version.add_argument("--published-at")
    version.add_argument("--doi")
    version.add_argument("--arxiv-id")
    version.add_argument("--supersedes-version-id", action="append", default=[])
    version.set_defaults(function=cmd_version_add)

    arxiv_check = commands.add_parser("arxiv-check")
    arxiv_check.add_argument("--root", required=True)
    arxiv_check.add_argument("--paper-id", action="append", default=[])
    arxiv_check.add_argument("--all", action="store_true")
    arxiv_check.add_argument("--arxiv-id")
    arxiv_check.add_argument("--input-atom")
    arxiv_check.add_argument("--response-locator")
    arxiv_check.add_argument("--checked-at")
    arxiv_check.set_defaults(function=cmd_arxiv_check)

    arxiv_capture = commands.add_parser("arxiv-capture")
    arxiv_capture.add_argument("--root", required=True)
    arxiv_capture.add_argument("--paper-id", required=True)
    arxiv_capture.add_argument("--arxiv-id", required=True)
    arxiv_capture.add_argument("--pdf")
    arxiv_capture.add_argument("--label")
    arxiv_capture.add_argument("--retrieved-at")
    arxiv_capture.add_argument("--published-at")
    arxiv_capture.set_defaults(function=cmd_arxiv_capture)

    graph = commands.add_parser("graph-add")
    graph.add_argument("--root", required=True)
    graph.add_argument("--paper-id", required=True)
    graph.add_argument("--version-id", required=True)
    graph.add_argument("--graph-root", required=True)
    graph.add_argument(
        "--graph-kind",
        choices=[
            "paper_logic_audit",
            "paper_logic",
            "paper_audit",
            "reader_packet",
            "other",
        ],
        required=True,
    )
    graph.add_argument("--chalxius-root", required=True)
    graph.add_argument("--source-project-id")
    graph.add_argument("--snapshot-id", action="append", default=[])
    graph.add_argument("--supersedes-graph-id", action="append", default=[])
    graph.set_defaults(function=cmd_graph_add)

    correction = commands.add_parser("correction-add")
    correction.add_argument("--root", required=True)
    correction.add_argument("--paper-id", required=True)
    correction.add_argument("--version-id", required=True)
    correction.add_argument("--graph-id")
    correction.add_argument(
        "--kind",
        choices=[
            "source_version",
            "logic_reconstruction",
            "audit_correction",
            "official_erratum",
            "local_emendation",
            "other",
        ],
        required=True,
    )
    correction.add_argument(
        "--status",
        choices=["proposed", "official", "accepted_local", "withdrawn", "unresolved"],
        required=True,
    )
    correction.add_argument("--summary", required=True)
    correction.add_argument("--official-locator")
    correction.add_argument("--artifact")
    correction.add_argument("--supersedes-correction-id", action="append", default=[])
    correction.set_defaults(function=cmd_correction_add)

    evidence_paper = commands.add_parser("evidence-paper-add")
    evidence_paper.add_argument("--root", required=True)
    evidence_paper.add_argument("--graph-id", required=True)
    evidence_paper.add_argument("--attestation", required=True)
    evidence_paper.add_argument(
        "--sync-mode",
        choices=["automatic_after_reviewed_freeze", "explicit_import"],
        required=True,
    )
    evidence_paper.add_argument(
        "--supersedes-evidence-id", action="append", default=[]
    )
    evidence_paper.set_defaults(function=cmd_evidence_paper_add)

    evidence_fact = commands.add_parser("evidence-fact-add")
    evidence_fact.add_argument("--root", required=True)
    evidence_fact.add_argument("--capsule", required=True)
    evidence_fact.add_argument("--actor", required=True)
    evidence_fact.add_argument("--reason", required=True)
    evidence_fact.add_argument(
        "--supersedes-evidence-id", action="append", default=[]
    )
    evidence_fact.set_defaults(function=cmd_evidence_fact_add)

    evidence_disposition = commands.add_parser("evidence-disposition-add")
    evidence_disposition.add_argument("--root", required=True)
    evidence_disposition.add_argument("--evidence-id", required=True)
    evidence_disposition.add_argument(
        "--status", choices=sorted(EVIDENCE_DISPOSITIONS), required=True
    )
    evidence_disposition.add_argument("--reason", required=True)
    evidence_disposition.add_argument("--actor", required=True)
    evidence_disposition.add_argument("--replacement-evidence-id", action="append", default=[])
    evidence_disposition.add_argument("--supersedes-disposition-id", action="append", default=[])
    evidence_disposition.add_argument("--artifact")
    evidence_disposition.set_defaults(function=cmd_evidence_disposition_add)

    bridge_prepare_parser = commands.add_parser("bridge-prepare")
    bridge_prepare_parser.add_argument("--root", required=True)
    bridge_prepare_parser.add_argument("--destination-project-id", required=True)
    bridge_prepare_parser.add_argument("--selection", required=True)
    bridge_prepare_parser.add_argument("--actor", required=True)
    bridge_prepare_parser.add_argument("--reason", required=True)
    bridge_prepare_parser.add_argument("--output")
    bridge_prepare_parser.set_defaults(function=cmd_bridge_prepare)

    bridge_check_parser = commands.add_parser("bridge-check")
    bridge_check_parser.add_argument("--root", required=True)
    bridge_check_parser.add_argument("--bridge-id", required=True)
    bridge_check_parser.set_defaults(function=cmd_bridge_check)

    evidence_query = commands.add_parser("evidence-query")
    evidence_query.add_argument("--root", required=True)
    evidence_query.add_argument("--query", default="")
    evidence_query.add_argument("--limit", type=int, default=20)
    evidence_query.add_argument("--include-inactive", action="store_true")
    evidence_query.set_defaults(function=cmd_evidence_query)

    index = commands.add_parser("index")
    index.add_argument("--root", required=True)
    index.set_defaults(function=cmd_index)

    verify = commands.add_parser("verify")
    verify.add_argument("--root", required=True)
    verify.set_defaults(function=cmd_verify)

    context = commands.add_parser("context-export")
    context.add_argument("--root", required=True)
    context.add_argument("--graph-id", action="append", default=[])
    context.add_argument("--output", required=True)
    context.set_defaults(function=cmd_context_export)
    return top


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        result = args.function(args)
    except LibraryError as exc:
        print(
            json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, sort_keys=True),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

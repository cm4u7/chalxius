from __future__ import annotations

import errno
import json
import os
import stat
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from .contracts import SHA256_RE, canonical_json_bytes, sha256_bytes, sha256_json


RUNTIME_ARCHIVE_REVISION = "chalxius-runtime-archive-2"
RUNTIME_ARCHIVE_ENV = "CHALXIUS_RUNTIME_ARCHIVE_ROOT"
RUNTIME_ARCHIVE_OBJECTS_DIRNAME = "by-content"
RUNTIME_ARCHIVE_BINDINGS_DIRNAME = "by-identity"
RUNTIME_ARCHIVE_BINDING_FIELDS_V1 = {
    "schema_version",
    "skill_root",
    "skill_version",
    "version_file_sha256",
    "manifest_file_sha256",
    "worker_ledger_contract",
    "runtime_identity_sha256",
}
RUNTIME_ARCHIVE_BINDING_FIELDS_V2 = {
    "schema_version",
    "skill_root",
    "skill_version",
    "version_file_sha256",
    "manifest_file_sha256",
    "runtime_content_sha256",
    "historical_archive_root",
    "worker_ledger_contract",
    "runtime_identity_sha256",
}
RUNTIME_ARCHIVE_REGISTRY_FIELDS = {
    "schema_version",
    "archive_revision",
    "runtime_identity_sha256",
    "runtime_content_sha256",
    "skill_version",
    "version_file_sha256",
    "manifest_file_sha256",
    "bound_skill_root",
    "archive_path",
    "manifest_entry_count",
    "archive_tree_sha256",
    "truth_effect",
    "runtime_effect",
    "record_sha256",
}


def validate_runtime_binding(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("V5 task-card runtime binding fields are not exact")
    schema_version = value.get("schema_version")
    expected_fields = (
        RUNTIME_ARCHIVE_BINDING_FIELDS_V1
        if schema_version == 1
        else RUNTIME_ARCHIVE_BINDING_FIELDS_V2
        if schema_version == 2
        else None
    )
    if expected_fields is None or set(value) != expected_fields:
        raise ValueError("V5 task-card runtime binding fields are not exact")
    semantic = {
        key: value[key]
        for key in expected_fields
        if key != "runtime_identity_sha256"
    }
    if (
        value.get("worker_ledger_contract")
        != "exact_task_card_runtime_binding_required"
        or value.get("runtime_identity_sha256") != sha256_json(semantic)
    ):
        raise ValueError("V5 task-card runtime binding identity is invalid")
    digest_fields = ["version_file_sha256", "manifest_file_sha256"]
    if schema_version == 2:
        digest_fields.append("runtime_content_sha256")
    digest_fields.append("runtime_identity_sha256")
    for field_name in digest_fields:
        field_value = value.get(field_name)
        if not isinstance(field_value, str) or SHA256_RE.fullmatch(field_value) is None:
            raise ValueError(f"V5 task-card runtime {field_name} is invalid")
    skill_root = _validate_absolute_path_text(
        value.get("skill_root"), label="V5 task-card runtime skill root"
    )
    skill_version = value.get("skill_version")
    if not isinstance(skill_version, str) or not skill_version.strip():
        raise ValueError("V5 task-card runtime skill version is invalid")
    if schema_version == 2:
        if value.get("runtime_content_sha256") != _runtime_content_sha256(value):
            raise ValueError("V5 task-card runtime content identity is invalid")
        archive_path = _validate_absolute_path_text(
            value.get("historical_archive_root"),
            label="V5 task-card historical runtime archive root",
        )
        if (
            archive_path.name != value["runtime_content_sha256"]
            or archive_path.parent.name != RUNTIME_ARCHIVE_OBJECTS_DIRNAME
        ):
            raise ValueError(
                "V5 task-card historical runtime archive locator is malformed"
            )
    del skill_root
    return dict(value)


def trusted_runtime_archive_root(
    explicit_root: Path | str | None = None,
    *,
    runtime_skill_root: Path | str | None = None,
) -> Path:
    configured = explicit_root
    if configured is None:
        configured = os.environ.get(RUNTIME_ARCHIVE_ENV)
    if configured is not None:
        archive_root = _validate_absolute_path_text(
            str(configured), label="Chalxius trusted runtime archive root"
        )
    else:
        skill_root = (
            Path(runtime_skill_root)
            if runtime_skill_root is not None
            else Path(__file__).absolute().parents[2]
        )
        skill_root = _safe_runtime_root(
            skill_root, label="current Chalxius runtime"
        )
        if skill_root.name != "chalxius" and not skill_root.name.startswith(
            "chalxius-"
        ):
            raise ValueError("current Chalxius runtime root has an unsafe name")
        if skill_root.parent.name == "skills":
            archive_root = (
                skill_root.parent.parent / "skill-runtime-archives" / "chalxius"
            )
        else:
            archive_root = (
                skill_root.parent / ".chalxius-runtime-archives" / "chalxius"
            )
    _assert_no_symlink_components(
        archive_root,
        label="Chalxius trusted runtime archive root",
        allow_missing=True,
    )
    return archive_root


def runtime_binding_from_root(
    source_root: Path | str,
    *,
    bound_skill_root: Path | str | None = None,
    archive_root: Path | str | None = None,
) -> dict[str, Any]:
    source = _safe_runtime_root(Path(source_root), label="Chalxius source runtime")
    bound = (
        _safe_runtime_root(
            Path(bound_skill_root), label="bound Chalxius skill runtime"
        )
        if bound_skill_root is not None
        else source
    )
    _, _, version_raw, manifest_raw = _identity_files(source)
    if bound != source:
        _, _, bound_version_raw, bound_manifest_raw = _identity_files(bound)
        if (
            bound_version_raw != version_raw
            or bound_manifest_raw != manifest_raw
        ):
            raise ValueError(
                "bound Chalxius skill runtime differs from the source identity"
            )
    try:
        skill_version = version_raw.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise ValueError("Chalxius VERSION is not UTF-8") from exc
    if not skill_version:
        raise ValueError("Chalxius VERSION is empty")
    content_semantic = {
        "schema_version": 1,
        "skill_version": skill_version,
        "version_file_sha256": sha256_bytes(version_raw),
        "manifest_file_sha256": sha256_bytes(manifest_raw),
    }
    runtime_content_sha256 = sha256_json(content_semantic)
    host_archive_root = trusted_runtime_archive_root(
        archive_root, runtime_skill_root=bound
    )
    object_root = (
        host_archive_root
        / RUNTIME_ARCHIVE_OBJECTS_DIRNAME
        / runtime_content_sha256
    )
    semantic = {
        "schema_version": 2,
        "skill_root": str(bound),
        "skill_version": skill_version,
        "version_file_sha256": sha256_bytes(version_raw),
        "manifest_file_sha256": sha256_bytes(manifest_raw),
        "runtime_content_sha256": runtime_content_sha256,
        "historical_archive_root": str(object_root),
        "worker_ledger_contract": "exact_task_card_runtime_binding_required",
    }
    return {
        **semantic,
        "runtime_identity_sha256": sha256_json(semantic),
    }


def historical_archive_path(
    binding: Any,
    *,
    archive_root: Path | str | None = None,
) -> Path:
    normalized = validate_runtime_binding(binding)
    host_archive_root = trusted_runtime_archive_root(archive_root)
    expected = (
        host_archive_root
        / RUNTIME_ARCHIVE_OBJECTS_DIRNAME
        / _runtime_content_sha256(normalized)
    )
    if (
        normalized["schema_version"] == 2
        and Path(normalized["historical_archive_root"]) != expected
    ):
        raise ValueError(
            "V5 task-card historical runtime archive root differs from the host trust root"
        )
    return expected


def historical_registry_path(
    binding: Any,
    *,
    archive_root: Path | str | None = None,
) -> Path:
    normalized = validate_runtime_binding(binding)
    host_archive_root = trusted_runtime_archive_root(archive_root)
    return (
        host_archive_root
        / RUNTIME_ARCHIVE_BINDINGS_DIRNAME
        / f"{normalized['runtime_identity_sha256']}.json"
    )


def validate_bound_runtime_at(
    root: Path | str,
    binding: Any,
    *,
    verify_manifest_tree: bool,
    require_exact_file_set: bool = False,
    require_read_only: bool = False,
) -> dict[str, Any]:
    normalized = validate_runtime_binding(binding)
    runtime_root = _safe_runtime_root(Path(root), label="bound Chalxius runtime")
    _, _, version_raw, manifest_raw = _identity_files(runtime_root)
    try:
        actual_version = version_raw.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise ValueError("V5 task-card bound Chalxius VERSION is not UTF-8") from exc
    if (
        not actual_version
        or normalized["skill_version"] != actual_version
        or normalized["version_file_sha256"] != sha256_bytes(version_raw)
        or normalized["manifest_file_sha256"] != sha256_bytes(manifest_raw)
    ):
        raise ValueError("V5 task-card bound Chalxius runtime identity drifted")
    entry_count = None
    archive_tree_sha256 = None
    if verify_manifest_tree:
        entries = _manifest_entries(manifest_raw)
        _verify_manifest_entries(runtime_root, entries)
        if require_exact_file_set:
            _verify_exact_archive_file_set(
                runtime_root,
                set(entries),
                require_read_only=require_read_only,
            )
        entry_count = len(entries)
        archive_tree_sha256 = _archive_tree_sha256(runtime_root, entries)
    return {
        "binding": normalized,
        "runtime_root": str(runtime_root),
        "manifest_entry_count": entry_count,
        "archive_tree_sha256": archive_tree_sha256,
    }


def resolve_historical_runtime(
    binding: Any,
    *,
    archive_root: Path | str | None = None,
) -> dict[str, Any]:
    normalized = validate_runtime_binding(binding)
    object_root = historical_archive_path(normalized, archive_root=archive_root)
    registry_path = historical_registry_path(normalized, archive_root=archive_root)
    bound_root = Path(normalized["skill_root"])
    _assert_no_symlink_components(
        bound_root,
        label="V5 task-card bound Chalxius runtime root",
        allow_missing=True,
    )
    original_error: ValueError | None = None
    if bound_root.is_dir():
        try:
            result = validate_bound_runtime_at(
                bound_root,
                normalized,
                verify_manifest_tree=True,
            )
            return {**result, "resolution": "original_bound_root"}
        except ValueError as exc:
            original_error = exc
    elif bound_root.exists():
        raise ValueError("V5 task-card bound Chalxius runtime root is unsafe")

    try:
        result = validate_bound_runtime_at(
            object_root,
            normalized,
            verify_manifest_tree=True,
            require_exact_file_set=True,
            require_read_only=True,
        )
        registry = _validate_registry_record(
            registry_path,
            normalized,
            archive_path=object_root,
            manifest_entry_count=result["manifest_entry_count"],
            archive_tree_sha256=result["archive_tree_sha256"],
        )
    except ValueError as archive_error:
        if original_error is not None:
            raise ValueError(
                "V5 task-card bound Chalxius runtime identity drifted and no valid "
                "content-addressed historical archive is available"
            ) from archive_error
        raise ValueError(
            "V5 task-card bound Chalxius runtime root is missing and no valid "
            "content-addressed historical archive is available"
        ) from archive_error
    return {
        **result,
        "resolution": "content_addressed_historical_archive",
        "registry_path": str(registry_path),
        "registry_record_sha256": registry["record_sha256"],
    }


def archive_runtime(
    source_root: Path | str,
    binding: Any,
    *,
    archive_root: Path | str | None = None,
) -> dict[str, Any]:
    normalized = validate_runtime_binding(binding)
    source = _safe_runtime_root(Path(source_root), label="Chalxius archive source")
    validate_bound_runtime_at(
        source,
        normalized,
        verify_manifest_tree=True,
        require_exact_file_set=False,
    )
    manifest_raw = _read_regular_file_nofollow(
        source / "MANIFEST.sha256", label="Chalxius source manifest"
    )
    entries = _manifest_entries(manifest_raw)
    host_archive_root = trusted_runtime_archive_root(archive_root)
    object_parent = host_archive_root / RUNTIME_ARCHIVE_OBJECTS_DIRNAME
    registry_parent = host_archive_root / RUNTIME_ARCHIVE_BINDINGS_DIRNAME
    _ensure_directory_chain(object_parent)
    _ensure_directory_chain(registry_parent)
    destination = historical_archive_path(normalized, archive_root=host_archive_root)
    registry_path = historical_registry_path(
        normalized, archive_root=host_archive_root
    )
    archive_created = False

    if destination.exists() or destination.is_symlink():
        existing = validate_bound_runtime_at(
            destination,
            normalized,
            verify_manifest_tree=True,
            require_exact_file_set=True,
            require_read_only=True,
        )
        archive_tree_sha256 = existing["archive_tree_sha256"]
    else:
        staging = Path(
            tempfile.mkdtemp(prefix=".runtime-stage-", dir=object_parent)
        )
        published = False
        try:
            for relpath in sorted(entries):
                source_bytes = _manifest_file_bytes(source, relpath)
                target_path = staging.joinpath(*PurePosixPath(relpath).parts)
                _ensure_directory_chain(target_path.parent)
                _write_new_regular_file(target_path, source_bytes)
            _write_new_regular_file(staging / "MANIFEST.sha256", manifest_raw)
            staged = validate_bound_runtime_at(
                staging,
                normalized,
                verify_manifest_tree=True,
                require_exact_file_set=True,
            )
            archive_tree_sha256 = staged["archive_tree_sha256"]
            try:
                os.rename(staging, destination)
                published = True
                archive_created = True
            except OSError as exc:
                if exc.errno not in {errno.EEXIST, errno.ENOTEMPTY}:
                    raise
            if published:
                _seal_archive_tree(destination)
            existing = validate_bound_runtime_at(
                destination,
                normalized,
                verify_manifest_tree=True,
                require_exact_file_set=True,
                require_read_only=True,
            )
            if existing["archive_tree_sha256"] != archive_tree_sha256:
                raise ValueError("Chalxius historical archive collision is not exact")
        finally:
            if not published and staging.exists():
                _remove_private_staging(staging)

    registry = _registry_record(
        normalized,
        archive_path=destination,
        manifest_entry_count=len(entries),
        archive_tree_sha256=archive_tree_sha256,
    )
    registry_created = _publish_registry_record(registry_path, registry)
    _validate_registry_record(
        registry_path,
        normalized,
        archive_path=destination,
        manifest_entry_count=len(entries),
        archive_tree_sha256=archive_tree_sha256,
    )
    return _archive_receipt(
        normalized,
        source=source,
        destination=destination,
        registry_path=registry_path,
        entry_count=len(entries),
        archive_tree_sha256=archive_tree_sha256,
        archive_created=archive_created,
        registry_created=registry_created,
    )


def read_json_file_nofollow(path: Path | str, *, label: str) -> Any:
    candidate = Path(path)
    if not candidate.is_absolute():
        raise ValueError(f"{label} path must be absolute")
    raw = _read_regular_file_nofollow(candidate, label=label)
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be one UTF-8 JSON value") from exc


def _runtime_content_sha256(binding: dict[str, Any]) -> str:
    semantic = {
        "schema_version": 1,
        "skill_version": binding["skill_version"],
        "version_file_sha256": binding["version_file_sha256"],
        "manifest_file_sha256": binding["manifest_file_sha256"],
    }
    return sha256_json(semantic)


def _validate_absolute_path_text(value: Any, *, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} is invalid")
    path = Path(value)
    if (
        not path.is_absolute()
        or path.anchor != "/"
        or ".." in path.parts
        or str(path) != value
    ):
        raise ValueError(f"{label} must be one canonical absolute path")
    return path


def _assert_no_symlink_components(
    path: Path,
    *,
    label: str,
    allow_missing: bool,
) -> None:
    if not path.is_absolute() or path.anchor != "/" or ".." in path.parts:
        raise ValueError(f"{label} is not a canonical absolute path")
    current = Path("/")
    for part in path.parts[1:]:
        current = current / part
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            if allow_missing:
                return
            raise ValueError(f"{label} is missing or unsafe") from None
        except OSError as exc:
            raise ValueError(f"{label} is missing or unsafe") from exc
        if stat.S_ISLNK(info.st_mode):
            raise ValueError(f"{label} traverses a symlink")


def _open_directory_nofollow(path: Path, *, label: str) -> int:
    _assert_no_symlink_components(path, label=label, allow_missing=False)
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ValueError(f"{label} is missing or unsafe") from exc
    info = os.fstat(descriptor)
    if not stat.S_ISDIR(info.st_mode):
        os.close(descriptor)
        raise ValueError(f"{label} is missing or unsafe")
    return descriptor


def _safe_runtime_root(root: Path, *, label: str) -> Path:
    descriptor = _open_directory_nofollow(root, label=f"{label} root")
    os.close(descriptor)
    return root


def _read_regular_file_nofollow(
    path: Path,
    *,
    label: str,
    require_single_link: bool = True,
) -> bytes:
    parent_fd = _open_directory_nofollow(path.parent, label=f"{label} parent")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        try:
            descriptor = os.open(path.name, flags, dir_fd=parent_fd)
        except OSError as exc:
            raise ValueError(f"{label} is missing or unsafe") from exc
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or (
                require_single_link and info.st_nlink != 1
            ):
                raise ValueError(f"{label} is not a unique regular file")
            with os.fdopen(descriptor, "rb", closefd=True) as stream:
                descriptor = -1
                return stream.read()
        finally:
            if descriptor >= 0:
                os.close(descriptor)
    finally:
        os.close(parent_fd)


def _identity_files(root: Path) -> tuple[Path, Path, bytes, bytes]:
    version_path = root / "VERSION"
    manifest_path = root / "MANIFEST.sha256"
    version_raw = _read_regular_file_nofollow(
        version_path, label="Chalxius VERSION identity file"
    )
    manifest_raw = _read_regular_file_nofollow(
        manifest_path, label="Chalxius MANIFEST identity file"
    )
    return version_path, manifest_path, version_raw, manifest_raw


def _manifest_entries(manifest_raw: bytes) -> dict[str, str]:
    try:
        body = manifest_raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Chalxius MANIFEST.sha256 is not UTF-8") from exc
    entries: dict[str, str] = {}
    lines = body.splitlines()
    if not lines or len(lines) > 10000:
        raise ValueError("Chalxius manifest entry count is invalid")
    for line in lines:
        if not line or "  " not in line:
            raise ValueError("Chalxius manifest line is malformed")
        digest, relpath = line.split("  ", 1)
        if SHA256_RE.fullmatch(digest) is None:
            raise ValueError("Chalxius manifest digest is invalid")
        pure = PurePosixPath(relpath)
        if (
            not relpath
            or pure.is_absolute()
            or "\\" in relpath
            or any(part in {"", ".", ".."} for part in pure.parts)
            or str(pure) != relpath
            or relpath == "MANIFEST.sha256"
            or relpath in entries
        ):
            raise ValueError("Chalxius manifest path is unsafe or duplicated")
        entries[relpath] = digest
    if "VERSION" not in entries:
        raise ValueError("Chalxius manifest must bind VERSION")
    return entries


def _manifest_file_bytes(root: Path, relpath: str) -> bytes:
    path = root.joinpath(*PurePosixPath(relpath).parts)
    return _read_regular_file_nofollow(
        path, label="Chalxius manifest file", require_single_link=True
    )


def _verify_manifest_entries(root: Path, entries: dict[str, str]) -> None:
    for relpath, digest in entries.items():
        if sha256_bytes(_manifest_file_bytes(root, relpath)) != digest:
            raise ValueError("Chalxius archived runtime manifest entry drifted")


def _expected_archive_directories(expected_files: set[str]) -> set[str]:
    expected_directories: set[str] = set()
    for relpath in expected_files:
        parent = PurePosixPath(relpath).parent
        while str(parent) not in {"", "."}:
            expected_directories.add(str(parent))
            parent = parent.parent
    return expected_directories


_IGNORABLE_EMPTY_RUNTIME_DIRECTORY_NAMES = frozenset({"__pycache__"})


def _ignorable_empty_runtime_directories(
    actual_directories: set[str],
    actual_files: set[str],
) -> set[str]:
    """Return byte-free interpreter cache leaves that cannot affect identity.

    Runtime identity is manifest-file based.  An empty ``__pycache__`` leaf can
    be left behind by local Python tooling even when bytecode writing is
    disabled; it contains no installable bytes and must not be confused with an
    unmanifested file.  Nonempty caches, nested unexpected directory trees, and
    every other extra directory remain exact-set failures.
    """

    ignorable: set[str] = set()
    for relative in actual_directories:
        path = PurePosixPath(relative)
        if path.name not in _IGNORABLE_EMPTY_RUNTIME_DIRECTORY_NAMES:
            continue
        prefix = relative + "/"
        if any(item.startswith(prefix) for item in actual_files):
            continue
        if any(
            item != relative and item.startswith(prefix)
            for item in actual_directories
        ):
            continue
        ignorable.add(relative)
    return ignorable


def _verify_exact_archive_file_set(
    root: Path,
    expected: set[str],
    *,
    require_read_only: bool,
) -> None:
    _assert_no_symlink_components(
        root, label="Chalxius archived runtime", allow_missing=False
    )
    root_info = os.lstat(root)
    if not stat.S_ISDIR(root_info.st_mode):
        raise ValueError("Chalxius archived runtime root is unsafe")
    if require_read_only and root_info.st_mode & 0o222:
        raise ValueError("Chalxius archived runtime root is not sealed read-only")
    expected_files = set(expected) | {"MANIFEST.sha256"}
    expected_directories = _expected_archive_directories(expected_files)
    actual_files: set[str] = set()
    actual_directories: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        directory = Path(dirpath)
        directory_info = os.lstat(directory)
        if (
            not stat.S_ISDIR(directory_info.st_mode)
            or stat.S_ISLNK(directory_info.st_mode)
            or directory_info.st_dev != root_info.st_dev
            or (require_read_only and directory_info.st_mode & 0o222)
        ):
            raise ValueError("Chalxius archived runtime contains an unsafe directory")
        for dirname in dirnames:
            child = directory / dirname
            child_info = os.lstat(child)
            if (
                not stat.S_ISDIR(child_info.st_mode)
                or stat.S_ISLNK(child_info.st_mode)
                or child_info.st_dev != root_info.st_dev
            ):
                raise ValueError("Chalxius archived runtime contains an unsafe directory")
            actual_directories.add(child.relative_to(root).as_posix())
        for filename in filenames:
            path = directory / filename
            info = os.lstat(path)
            if (
                not stat.S_ISREG(info.st_mode)
                or stat.S_ISLNK(info.st_mode)
                or info.st_nlink != 1
                or info.st_dev != root_info.st_dev
                or (require_read_only and info.st_mode & 0o222)
            ):
                raise ValueError("Chalxius archived runtime contains an unsafe file")
            actual_files.add(path.relative_to(root).as_posix())
    ignorable_directories = _ignorable_empty_runtime_directories(
        actual_directories,
        actual_files,
    )
    if (
        actual_files != expected_files
        or actual_directories - ignorable_directories != expected_directories
    ):
        raise ValueError("Chalxius archived runtime file set differs from its manifest")


def _archive_tree_sha256(root: Path, entries: dict[str, str]) -> str:
    rows: list[dict[str, Any]] = []
    for relpath in sorted(set(entries) | {"MANIFEST.sha256"}):
        raw = _read_regular_file_nofollow(
            root.joinpath(*PurePosixPath(relpath).parts),
            label="Chalxius archived runtime tree file",
        )
        rows.append(
            {"path": relpath, "sha256": sha256_bytes(raw), "size": len(raw)}
        )
    return sha256_json(rows)


def _ensure_directory_chain(path: Path) -> None:
    if not path.is_absolute() or path.anchor != "/" or ".." in path.parts:
        raise ValueError("Chalxius runtime archive directory is not canonical")
    current_fd = os.open(
        "/", os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    )
    try:
        for part in path.parts[1:]:
            flags = (
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0)
            )
            try:
                next_fd = os.open(part, flags, dir_fd=current_fd)
            except FileNotFoundError:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=current_fd)
                except FileExistsError:
                    pass
                try:
                    next_fd = os.open(part, flags, dir_fd=current_fd)
                except OSError as exc:
                    raise ValueError(
                        "Chalxius runtime archive directory is unsafe"
                    ) from exc
            except OSError as exc:
                raise ValueError("Chalxius runtime archive directory is unsafe") from exc
            info = os.fstat(next_fd)
            if not stat.S_ISDIR(info.st_mode):
                os.close(next_fd)
                raise ValueError("Chalxius runtime archive directory is unsafe")
            os.close(current_fd)
            current_fd = next_fd
    finally:
        os.close(current_fd)


def _write_new_regular_file(path: Path, raw: bytes) -> None:
    parent_fd = _open_directory_nofollow(
        path.parent, label="Chalxius archive output parent"
    )
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        try:
            descriptor = os.open(path.name, flags, 0o600, dir_fd=parent_fd)
        except OSError as exc:
            raise ValueError("Chalxius archive output file collision") from exc
        try:
            view = memoryview(raw)
            while view:
                written = os.write(descriptor, view)
                view = view[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        os.close(parent_fd)


def _seal_archive_tree(root: Path) -> None:
    for dirpath, dirnames, filenames in os.walk(root, topdown=False, followlinks=False):
        directory = Path(dirpath)
        for filename in filenames:
            path = directory / filename
            info = os.lstat(path)
            if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
                raise ValueError("Chalxius archive cannot seal an unsafe file")
            os.chmod(path, 0o400, follow_symlinks=False)
        for dirname in dirnames:
            path = directory / dirname
            info = os.lstat(path)
            if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
                raise ValueError("Chalxius archive cannot seal an unsafe directory")
            os.chmod(path, 0o500, follow_symlinks=False)
        os.chmod(directory, 0o500, follow_symlinks=False)


def _remove_private_staging(path: Path) -> None:
    if path.is_symlink() or not path.is_dir():
        return
    for dirpath, dirnames, filenames in os.walk(path, topdown=False, followlinks=False):
        directory = Path(dirpath)
        os.chmod(directory, 0o700, follow_symlinks=False)
        for filename in filenames:
            candidate = directory / filename
            if not candidate.is_symlink():
                os.chmod(candidate, 0o600, follow_symlinks=False)
            candidate.unlink(missing_ok=True)
        for dirname in dirnames:
            candidate = directory / dirname
            if candidate.is_symlink():
                candidate.unlink()
            else:
                os.chmod(candidate, 0o700, follow_symlinks=False)
                candidate.rmdir()
    path.rmdir()


def _registry_record(
    binding: dict[str, Any],
    *,
    archive_path: Path,
    manifest_entry_count: int,
    archive_tree_sha256: str,
) -> dict[str, Any]:
    semantic = {
        "schema_version": 1,
        "archive_revision": RUNTIME_ARCHIVE_REVISION,
        "runtime_identity_sha256": binding["runtime_identity_sha256"],
        "runtime_content_sha256": _runtime_content_sha256(binding),
        "skill_version": binding["skill_version"],
        "version_file_sha256": binding["version_file_sha256"],
        "manifest_file_sha256": binding["manifest_file_sha256"],
        "bound_skill_root": binding["skill_root"],
        "archive_path": str(archive_path),
        "manifest_entry_count": manifest_entry_count,
        "archive_tree_sha256": archive_tree_sha256,
        "truth_effect": "none",
        "runtime_effect": "historical_read_and_audit_only",
    }
    return {**semantic, "record_sha256": sha256_json(semantic)}


def _publish_registry_record(path: Path, record: dict[str, Any]) -> bool:
    expected_raw = canonical_json_bytes(record) + b"\n"
    if path.exists() or path.is_symlink():
        if _read_regular_file_nofollow(
            path, label="Chalxius runtime archive registry record"
        ) != expected_raw:
            raise ValueError("Chalxius runtime archive registry collision is not exact")
        return False
    parent_fd = _open_directory_nofollow(
        path.parent, label="Chalxius runtime archive registry parent"
    )
    staging_fd, staging_name = tempfile.mkstemp(
        prefix=".registry-stage-", dir=path.parent
    )
    staging_path = Path(staging_name)
    try:
        with os.fdopen(staging_fd, "wb", closefd=True) as stream:
            stream.write(expected_raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(staging_path, 0o400, follow_symlinks=False)
        try:
            os.link(
                staging_path.name,
                path.name,
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
                follow_symlinks=False,
            )
            created = True
        except FileExistsError:
            created = False
        staging_path.unlink()
        if _read_regular_file_nofollow(
            path, label="Chalxius runtime archive registry record"
        ) != expected_raw:
            raise ValueError("Chalxius runtime archive registry collision is not exact")
        return created
    finally:
        staging_path.unlink(missing_ok=True)
        os.close(parent_fd)


def _validate_registry_record(
    path: Path,
    binding: dict[str, Any],
    *,
    archive_path: Path,
    manifest_entry_count: int | None,
    archive_tree_sha256: str | None,
) -> dict[str, Any]:
    raw = _read_regular_file_nofollow(
        path, label="Chalxius runtime archive registry record"
    )
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Chalxius runtime archive registry is invalid") from exc
    if not isinstance(value, dict) or set(value) != RUNTIME_ARCHIVE_REGISTRY_FIELDS:
        raise ValueError("Chalxius runtime archive registry fields are not exact")
    expected = _registry_record(
        binding,
        archive_path=archive_path,
        manifest_entry_count=int(manifest_entry_count),
        archive_tree_sha256=str(archive_tree_sha256),
    )
    if value != expected or raw != canonical_json_bytes(expected) + b"\n":
        raise ValueError("Chalxius runtime archive registry binding is invalid")
    info = os.lstat(path)
    if info.st_mode & 0o222:
        raise ValueError("Chalxius runtime archive registry is not sealed read-only")
    return value


def _archive_receipt(
    binding: dict[str, Any],
    *,
    source: Path,
    destination: Path,
    registry_path: Path,
    entry_count: int,
    archive_tree_sha256: str,
    archive_created: bool,
    registry_created: bool,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "archive_revision": RUNTIME_ARCHIVE_REVISION,
        "runtime_identity_sha256": binding["runtime_identity_sha256"],
        "runtime_content_sha256": _runtime_content_sha256(binding),
        "skill_version": binding["skill_version"],
        "bound_skill_root": binding["skill_root"],
        "source_root": str(source),
        "archive_path": str(destination),
        "registry_path": str(registry_path),
        "manifest_entry_count": entry_count,
        "archive_tree_sha256": archive_tree_sha256,
        "archive_created": archive_created,
        "registry_created": registry_created,
        "created": archive_created or registry_created,
        "truth_effect": "none",
        "runtime_effect": "historical_read_and_audit_only",
    }

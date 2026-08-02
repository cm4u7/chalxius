from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


CONTRACT_REVISION = "chalxius-runtime-compatibility-closure-1"


class RuntimeCompatibilityError(ValueError):
    """The declared compatibility-protected runtime closure is not exact."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeCompatibilityError(message)


def _relative_spec(value: Any) -> tuple[PurePosixPath, bool]:
    _require(isinstance(value, str) and value.strip(), "protected path is invalid")
    recursive = value.endswith("/**")
    raw = value[:-3] if recursive else value
    path = PurePosixPath(raw)
    _require(not path.is_absolute(), "protected path must be relative")
    _require(
        bool(path.parts)
        and all(part not in {"", ".", ".."} for part in path.parts),
        "protected path contains traversal or empty components",
    )
    return path, recursive


def _checked_path(root: Path, relative: PurePosixPath) -> Path:
    current = root
    for part in relative.parts:
        current = current / part
        try:
            mode = os.lstat(current).st_mode
        except FileNotFoundError as exc:
            raise RuntimeCompatibilityError(
                f"protected path is missing: {relative.as_posix()}"
            ) from exc
        _require(not stat.S_ISLNK(mode), "protected path contains a symlink")
    return current


def _recursive_regular_files(root: Path, base: Path) -> Iterable[Path]:
    for current_raw, directory_names, file_names in os.walk(base, followlinks=False):
        current = Path(current_raw)
        kept_directories: list[str] = []
        for name in sorted(directory_names):
            child = current / name
            mode = os.lstat(child).st_mode
            _require(not stat.S_ISLNK(mode), "protected tree contains a symlink")
            _require(stat.S_ISDIR(mode), "protected tree contains a non-directory")
            if name != "__pycache__":
                kept_directories.append(name)
        directory_names[:] = kept_directories
        for name in sorted(file_names):
            child = current / name
            mode = os.lstat(child).st_mode
            _require(not stat.S_ISLNK(mode), "protected tree contains a symlink")
            _require(stat.S_ISREG(mode), "protected tree contains a nonregular file")
            child.relative_to(root)
            yield child


def protected_runtime_files(
    skill_root: Path | str, protected_paths: Any
) -> list[Path]:
    root = Path(skill_root).resolve()
    _require(root.is_dir() and not root.is_symlink(), "skill root is invalid")
    _require(
        isinstance(protected_paths, list)
        and protected_paths
        and len(protected_paths) == len(set(protected_paths)),
        "protected_paths must be a nonempty unique list",
    )
    files: set[Path] = set()
    for raw in protected_paths:
        relative, recursive = _relative_spec(raw)
        path = _checked_path(root, relative)
        mode = os.lstat(path).st_mode
        if recursive:
            _require(stat.S_ISDIR(mode), "recursive protected path is not a directory")
            files.update(_recursive_regular_files(root, path))
        else:
            _require(stat.S_ISREG(mode), "protected path is not a regular file")
            files.add(path)
    _require(files, "protected runtime closure is empty")
    return sorted(files, key=lambda item: item.relative_to(root).as_posix())


def compute_protected_tree(
    skill_root: Path | str, protected_paths: Any
) -> dict[str, Any]:
    root = Path(skill_root).resolve()
    files = protected_runtime_files(root, protected_paths)
    digest = hashlib.sha256()
    relative_paths: list[str] = []
    for path in files:
        relative = path.relative_to(root).as_posix()
        relative_paths.append(relative)
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        digest.update(relative.encode("utf-8") + b"\0")
        digest.update(file_hash.encode("ascii") + b"\n")
    return {
        "contract_revision": CONTRACT_REVISION,
        "protected_file_count": len(files),
        "protected_tree_sha256": digest.hexdigest(),
        "protected_file_paths": relative_paths,
        "truth_effect": "none",
    }


def changed_path_inventory_sha256(paths: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.encode("utf-8") + b"\n")
    return digest.hexdigest()


def validate_runtime_compatibility(
    skill_root: Path | str, compatibility: Any
) -> dict[str, Any]:
    _require(isinstance(compatibility, dict), "runtime_compatibility is malformed")
    status = compute_protected_tree(
        skill_root, compatibility.get("protected_paths")
    )
    _require(
        compatibility.get("protected_file_count") == status["protected_file_count"],
        "runtime compatibility protected_file_count drifted",
    )
    _require(
        compatibility.get("protected_tree_sha256")
        == status["protected_tree_sha256"],
        "runtime compatibility protected_tree_sha256 drifted",
    )
    changed = compatibility.get("changed_from_0.4.3_runtime_paths")
    _require(
        isinstance(changed, list)
        and all(isinstance(item, str) and item for item in changed)
        and changed == sorted(set(changed)),
        "runtime compatibility changed paths must be sorted and unique",
    )
    protected = set(status["protected_file_paths"])
    _require(
        set(changed).issubset(protected),
        "runtime compatibility changed path is outside the protected closure",
    )
    changed_digest = changed_path_inventory_sha256(changed)
    _require(
        compatibility.get("changed_path_inventory_sha256") == changed_digest,
        "runtime compatibility changed path inventory digest drifted",
    )
    return {
        **status,
        "baseline": compatibility.get("baseline"),
        "changed_path_count": len(changed),
        "changed_path_inventory_sha256": changed_digest,
        "status": "current",
    }

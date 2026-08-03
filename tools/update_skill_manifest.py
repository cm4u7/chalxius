#!/usr/bin/env python3
"""Regenerate one exact, sorted Chalxius skill manifest atomically."""

from __future__ import annotations

import argparse
import hashlib
import os
import stat
import tempfile
from pathlib import Path


EXCLUDED_NAMES = {"MANIFEST.sha256", ".DS_Store"}
EXCLUDED_DIRECTORY_NAMES = {"__pycache__"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def exact_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for current_raw, directory_names, file_names in os.walk(root, followlinks=False):
        current = Path(current_raw)
        kept: list[str] = []
        for name in sorted(directory_names):
            child = current / name
            mode = os.lstat(child).st_mode
            if stat.S_ISLNK(mode):
                raise ValueError(f"skill tree contains a symlink: {child.relative_to(root)}")
            if not stat.S_ISDIR(mode):
                raise ValueError(f"skill tree contains a non-directory: {child.relative_to(root)}")
            if name in EXCLUDED_DIRECTORY_NAMES:
                raise ValueError(f"skill tree contains a cache directory: {child.relative_to(root)}")
            kept.append(name)
        directory_names[:] = kept
        for name in sorted(file_names):
            child = current / name
            relative = child.relative_to(root)
            mode = os.lstat(child).st_mode
            if stat.S_ISLNK(mode):
                raise ValueError(f"skill tree contains a symlink: {relative}")
            if not stat.S_ISREG(mode):
                raise ValueError(f"skill tree contains a nonregular file: {relative}")
            if name in EXCLUDED_NAMES:
                continue
            if name.endswith((".pyc", ".pyo")):
                raise ValueError(f"skill tree contains bytecode: {relative}")
            files.append(child)
    return sorted(files, key=lambda item: item.relative_to(root).as_posix())


def atomic_write(path: Path, payload: bytes) -> None:
    with tempfile.NamedTemporaryFile(
        dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.skill_root.expanduser().resolve()
    if root.is_symlink() or not root.is_dir():
        raise ValueError("--skill-root must be one regular directory")
    rows = [
        f"{sha256_file(path)}  {path.relative_to(root).as_posix()}"
        for path in exact_files(root)
    ]
    payload = ("\n".join(rows) + "\n").encode("utf-8")
    atomic_write(root / "MANIFEST.sha256", payload)
    print(
        f"entries={len(rows)} manifest_sha256="
        f"{hashlib.sha256(payload).hexdigest()}"
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build and verify a deterministic Chalxius release archive from its manifest."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import stat
import tarfile
import tempfile
from pathlib import Path, PurePosixPath


FIXED_MTIME = 0


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def parse_manifest(skill_root: Path) -> list[str]:
    manifest = skill_root / "MANIFEST.sha256"
    entries: list[str] = []
    for line_number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        digest, separator, relative = line.partition("  ")
        if not separator or len(digest) != 64:
            raise ValueError(f"invalid manifest row {line_number}")
        path = PurePosixPath(relative)
        if path.is_absolute() or ".." in path.parts or relative == "MANIFEST.sha256":
            raise ValueError(f"unsafe manifest path: {relative!r}")
        source = skill_root / relative
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"manifest member is not a regular file: {relative}")
        actual = sha256_bytes(source.read_bytes())
        if actual != digest:
            raise ValueError(f"manifest digest mismatch: {relative}")
        entries.append(relative)
    if entries != sorted(entries) or len(entries) != len(set(entries)):
        raise ValueError("manifest paths must be sorted and unique")
    actual_files = sorted(
        path.relative_to(skill_root).as_posix()
        for path in skill_root.rglob("*")
        if path.is_file() and not path.is_symlink() and path.name != "MANIFEST.sha256"
    )
    if entries != actual_files:
        raise ValueError("manifest path set does not equal the skill file set")
    return entries


def build_bytes(skill_root: Path, members: list[str]) -> bytes:
    output = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            for relative in sorted([*members, "MANIFEST.sha256"]):
                source = skill_root / relative
                payload = source.read_bytes()
                info = tarfile.TarInfo(name=f"chalxius/{relative}")
                source_mode = stat.S_IMODE(source.stat().st_mode)
                info.mode = 0o755 if source_mode & 0o111 else 0o644
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                info.size = len(payload)
                info.mtime = FIXED_MTIME
                info.type = tarfile.REGTYPE
                archive.addfile(info, io.BytesIO(payload))
    return output.getvalue()


def validate_archive(payload: bytes, members: list[str]) -> None:
    expected = [f"chalxius/{relative}" for relative in sorted([*members, "MANIFEST.sha256"])]
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        records = archive.getmembers()
        names = [record.name for record in records]
        if names != expected or len(names) != len(set(names)):
            raise RuntimeError("archive member list is incomplete, reordered, or duplicated")
        for record in records:
            path = PurePosixPath(record.name)
            if not record.isfile() or path.is_absolute() or ".." in path.parts:
                raise RuntimeError(f"unsafe archive member: {record.name}")
            if record.uid != 0 or record.gid != 0 or record.mtime != FIXED_MTIME:
                raise RuntimeError(f"nondeterministic archive metadata: {record.name}")


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-root", type=Path, default=Path(__file__).resolve().parents[1] / "chalxius")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    skill_root = args.skill_root.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if output.suffixes[-2:] != [".tar", ".gz"]:
        raise ValueError("--output must end in .tar.gz")
    members = parse_manifest(skill_root)
    first = build_bytes(skill_root, members)
    second = build_bytes(skill_root, members)
    if first != second:
        raise RuntimeError("two independent archive builds were not byte-identical")
    validate_archive(first, members)
    atomic_write(output, first)
    digest = sha256_bytes(first)
    checksum = f"{digest}  {output.name}\n".encode("utf-8")
    atomic_write(output.with_name(output.name + ".sha256"), checksum)
    print(
        json.dumps(
            {
                "archive": str(output),
                "archive_bytes": len(first),
                "archive_members": len(members) + 1,
                "archive_sha256": digest,
                "deterministic_double_build": "pass",
                "manifest_entries": len(members),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

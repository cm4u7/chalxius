#!/usr/bin/env python3
"""Update the four Chalxius candidate-release identity projections once."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import tempfile
from pathlib import Path

import update_skill_manifest


SEMVER_RE = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
SKILL_HEADING_RE = re.compile(r"^# Chalxius [^\n]+$", re.MULTILINE)


def _regular_file(path: Path) -> None:
    mode = os.lstat(path).st_mode
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise ValueError(f"release identity path is not one regular file: {path}")


def _atomic_replace_preserving_mode(path: Path, payload: bytes) -> None:
    mode = stat.S_IMODE(os.lstat(path).st_mode)
    with tempfile.NamedTemporaryFile(
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        try:
            os.fchmod(handle.fileno(), mode)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    os.replace(temporary, path)


def _manifest_payload(
    root: Path,
    *,
    pending_updates: dict[Path, bytes],
) -> bytes:
    rows = []
    for path in update_skill_manifest.exact_files(root):
        payload = pending_updates.get(path)
        digest = (
            hashlib.sha256(payload).hexdigest()
            if payload is not None
            else update_skill_manifest.sha256_file(path)
        )
        rows.append(f"{digest}  {path.relative_to(root).as_posix()}")
    return ("\n".join(rows) + "\n").encode("utf-8")


def prepare_updates(
    root: Path,
    *,
    version: str,
    codename: str,
) -> dict[Path, bytes]:
    """Validate every anchor before returning any candidate bytes."""

    if SEMVER_RE.fullmatch(version) is None:
        raise ValueError("--version must be a three-part semantic version")
    if not codename.strip() or codename != codename.strip() or "\n" in codename:
        raise ValueError("--codename must be one nonempty trimmed line")
    display = f"Chalxius {version} — {codename}"
    version_path = root / "VERSION"
    lock_path = root / "INHERITANCE.lock.json"
    skill_path = root / "SKILL.md"
    deploy_path = root / "assets" / "DEPLOY_PROMPT.txt"
    for path in (version_path, lock_path, skill_path, deploy_path):
        _regular_file(path)

    current_version = version_path.read_text(encoding="utf-8")
    if SEMVER_RE.fullmatch(current_version.strip()) is None:
        raise ValueError("VERSION is not one existing three-part release identity")

    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if (
        not isinstance(lock, dict)
        or lock.get("skill_name") != "chalxius"
        or not isinstance(lock.get("version"), str)
        or not isinstance(lock.get("release_codename"), str)
        or not isinstance(lock.get("release_display_name"), str)
    ):
        raise ValueError("INHERITANCE.lock.json release identity shape is invalid")
    lock["version"] = version
    lock["release_codename"] = codename
    lock["release_display_name"] = display

    skill = skill_path.read_text(encoding="utf-8")
    headings = SKILL_HEADING_RE.findall(skill)
    if len(headings) != 1:
        raise ValueError("SKILL.md must contain exactly one Chalxius release heading")
    skill = SKILL_HEADING_RE.sub(f"# {display}", skill, count=1)

    deploy = deploy_path.read_text(encoding="utf-8")
    deploy_lines = deploy.splitlines(keepends=True)
    if not deploy_lines or not deploy_lines[0].startswith("Chalxius "):
        raise ValueError("DEPLOY_PROMPT.txt first line is not a release identity")
    deploy_lines[0] = display + ("\n" if deploy_lines[0].endswith("\n") else "")
    deploy = "".join(deploy_lines)
    # Runtime prose should not create an untracked fifth version projection.
    deploy = re.sub(
        r"^The [0-9]+\.[0-9]+\.[0-9]+ runtime ",
        "The current runtime ",
        deploy,
        count=1,
        flags=re.MULTILINE,
    )

    return {
        version_path: (version + "\n").encode("utf-8"),
        lock_path: (
            json.dumps(lock, ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8"),
        skill_path: skill.encode("utf-8"),
        deploy_path: deploy.encode("utf-8"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-root", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--codename", required=True)
    args = parser.parse_args()
    root = args.skill_root.expanduser().resolve()
    if root.is_symlink() or not root.is_dir():
        raise ValueError("--skill-root must be one regular directory")

    updates = prepare_updates(
        root,
        version=args.version,
        codename=args.codename,
    )
    manifest_path = root / "MANIFEST.sha256"
    manifest_payload: bytes | None = None
    if manifest_path.exists():
        _regular_file(manifest_path)
        # Validate the complete candidate file set and compute its future
        # manifest before changing any release-identity byte.  A stray cache,
        # symlink, or nonregular file must leave all projections untouched.
        manifest_payload = _manifest_payload(
            root,
            pending_updates=updates,
        )
    changed: list[str] = []
    for path, payload in updates.items():
        if path.read_bytes() != payload:
            _atomic_replace_preserving_mode(path, payload)
            changed.append(path.relative_to(root).as_posix())
    if manifest_payload is not None:
        if manifest_path.read_bytes() != manifest_payload:
            _atomic_replace_preserving_mode(manifest_path, manifest_payload)
            changed.append("MANIFEST.sha256")
    result = {
        "version": args.version,
        "release_codename": args.codename,
        "release_display_name": f"Chalxius {args.version} — {args.codename}",
        "changed_paths": changed,
        "manifest_sha256": (
            hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            if manifest_path.exists()
            else None
        ),
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

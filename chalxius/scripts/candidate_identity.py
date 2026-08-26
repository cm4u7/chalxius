#!/usr/bin/env python3
"""Show one proposed Chalxius source root's exact, read-only identity."""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from typing import Any

sys.dont_write_bytecode = True

from mathgraph._local_install import default_global_paths
from mathgraph.contracts import sha256_bytes, sha256_json


SHA256_RE = re.compile(r"[0-9a-f]{64}")
VERSION_HINT_RE = re.compile(r"(?<!\d)(\d+\.\d+(?:\.\d+)?)(?!\d)")


def _safe_root(value: Path, *, label: str) -> Path:
    expanded = value.expanduser()
    if expanded.is_symlink():
        raise ValueError(f"{label} cannot be a symlink")
    root = expanded.resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"{label} must be a directory")
    return root


def _manifest_entries(root: Path) -> dict[str, str]:
    path = root / "MANIFEST.sha256"
    if path.is_symlink() or not path.is_file():
        raise ValueError("MANIFEST.sha256 is missing or unsafe")
    entries: dict[str, str] = {}
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line:
            continue
        try:
            digest, relpath = line.split("  ", 1)
        except ValueError as exc:
            raise ValueError(
                f"manifest line {line_number} is malformed"
            ) from exc
        pure = PurePosixPath(relpath)
        if (
            SHA256_RE.fullmatch(digest) is None
            or pure.is_absolute()
            or not pure.parts
            or any(part in {"", ".", ".."} for part in pure.parts)
            or relpath == "MANIFEST.sha256"
            or relpath in entries
        ):
            raise ValueError(
                f"manifest line {line_number} is unsafe or duplicated"
            )
        entries[relpath] = digest
    if not entries:
        raise ValueError("MANIFEST.sha256 is empty")
    return entries


def _manifest_status(root: Path) -> dict[str, Any]:
    try:
        entries = _manifest_entries(root)
        for relpath, expected_digest in entries.items():
            candidate = root.joinpath(*PurePosixPath(relpath).parts)
            cursor = root
            for part in PurePosixPath(relpath).parts:
                cursor = cursor / part
                if cursor.is_symlink():
                    raise ValueError(
                        f"manifest path traverses a symlink: {relpath}"
                    )
            if not candidate.is_file():
                raise ValueError(f"manifest file is missing: {relpath}")
            if sha256_bytes(candidate.read_bytes()) != expected_digest:
                raise ValueError(
                    f"manifest entry drifted: {relpath}"
                )
        actual_files: set[str] = set()
        for candidate in root.rglob("*"):
            if candidate.is_symlink():
                raise ValueError(
                    "candidate tree contains a symlink: "
                    + candidate.relative_to(root).as_posix()
                )
            if candidate.is_dir():
                continue
            if not candidate.is_file():
                raise ValueError(
                    "candidate tree contains a non-file entry: "
                    + candidate.relative_to(root).as_posix()
                )
            actual_files.add(candidate.relative_to(root).as_posix())
        expected_files = set(entries).union({"MANIFEST.sha256"})
        if actual_files != expected_files:
            missing = sorted(expected_files.difference(actual_files))
            untracked = sorted(actual_files.difference(expected_files))
            raise ValueError(
                "manifest exact file set drifted; "
                f"missing={missing[:8]}; untracked={untracked[:8]}"
            )
        manifest_digest = sha256_bytes(
            (root / "MANIFEST.sha256").read_bytes()
        )
        return {
            "valid": True,
            "error": "",
            "manifest_file_sha256": manifest_digest,
            "manifest_entry_count": len(entries),
            "entries": entries,
        }
    except (OSError, UnicodeError, ValueError) as exc:
        manifest_path = root / "MANIFEST.sha256"
        digest = (
            sha256_bytes(manifest_path.read_bytes())
            if manifest_path.is_file() and not manifest_path.is_symlink()
            else ""
        )
        try:
            entries = _manifest_entries(root)
        except (OSError, UnicodeError, ValueError):
            entries = {}
        return {
            "valid": False,
            "error": f"{type(exc).__name__}: {exc}",
            "manifest_file_sha256": digest,
            "manifest_entry_count": len(entries),
            "entries": entries,
        }


def _run_git(root: Path, *arguments: str) -> tuple[int, str]:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    return completed.returncode, completed.stdout.rstrip("\n")


def _git_status(root: Path) -> dict[str, Any]:
    status, top = _run_git(root, "rev-parse", "--show-toplevel")
    if status != 0 or not top:
        return {
            "present": False,
            "worktree_root": "",
            "branch": "",
            "head": "",
            "dirty": False,
            "dirty_path_count": 0,
            "dirty_paths": [],
            "dirty_status_sha256": sha256_json([]),
        }
    worktree_root = Path(top).resolve(strict=True)
    _, head = _run_git(root, "rev-parse", "HEAD")
    branch_status, branch = _run_git(
        root, "symbolic-ref", "--quiet", "--short", "HEAD"
    )
    _, porcelain = _run_git(
        root, "status", "--porcelain=v1", "--untracked-files=all"
    )
    lines = porcelain.splitlines() if porcelain else []
    return {
        "present": True,
        "worktree_root": str(worktree_root),
        "branch": branch if branch_status == 0 else "(detached)",
        "head": head,
        "dirty": bool(lines),
        "dirty_path_count": len(lines),
        "dirty_paths": lines[:64],
        "dirty_status_sha256": sha256_json(lines),
    }


def _version(root: Path) -> str:
    path = root / "VERSION"
    if path.is_symlink() or not path.is_file():
        raise ValueError("VERSION is missing or unsafe")
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise ValueError("VERSION is empty")
    return value


def _path_version_hint(root: Path) -> dict[str, Any]:
    hints: list[dict[str, str]] = []
    for path in (root, root.parent):
        match = VERSION_HINT_RE.search(path.name)
        if match is not None:
            hints.append({"path": str(path), "version_hint": match.group(1)})
    return {"hints": hints, "selection_effect": "none"}


def _manifest_difference(
    candidate: dict[str, str], installed: dict[str, str]
) -> dict[str, Any]:
    candidate_paths = set(candidate)
    installed_paths = set(installed)
    candidate_only = sorted(candidate_paths.difference(installed_paths))
    installed_only = sorted(installed_paths.difference(candidate_paths))
    changed = sorted(
        path
        for path in candidate_paths.intersection(installed_paths)
        if candidate[path] != installed[path]
    )
    all_differences = [
        *(f"candidate_only:{path}" for path in candidate_only),
        *(f"installed_only:{path}" for path in installed_only),
        *(f"changed:{path}" for path in changed),
    ]
    return {
        "candidate_only_count": len(candidate_only),
        "candidate_only_paths": candidate_only[:32],
        "installed_only_count": len(installed_only),
        "installed_only_paths": installed_only[:32],
        "content_changed_count": len(changed),
        "content_changed_paths": changed[:32],
        "difference_sha256": sha256_json(all_differences),
    }


def project_candidate_identity(
    candidate_root: Path, installed_root: Path | None
) -> dict[str, Any]:
    candidate = _safe_root(candidate_root, label="candidate root")
    candidate_version = _version(candidate)
    candidate_manifest = _manifest_status(candidate)
    installed: Path | None = None
    installed_version = ""
    installed_manifest: dict[str, Any] = {
        "valid": False,
        "error": "installed root not supplied or absent",
        "manifest_file_sha256": "",
        "manifest_entry_count": 0,
        "entries": {},
    }
    if installed_root is not None and installed_root.expanduser().exists():
        installed = _safe_root(installed_root, label="installed root")
        installed_version = _version(installed)
        installed_manifest = _manifest_status(installed)
    same_version = bool(installed) and candidate_version == installed_version
    same_manifest = bool(installed) and (
        candidate_manifest["manifest_file_sha256"]
        == installed_manifest["manifest_file_sha256"]
    )
    if not candidate_manifest["valid"]:
        selection_status = "candidate_manifest_invalid"
    elif installed is None:
        selection_status = "candidate_valid_installed_comparison_unavailable"
    elif same_version and same_manifest and installed_manifest["valid"]:
        selection_status = "exact_installed_baseline"
    elif same_version:
        selection_status = "same_version_candidate_changes_present"
    else:
        selection_status = "different_version_from_installed"
    difference = _manifest_difference(
        candidate_manifest["entries"], installed_manifest["entries"]
    )
    return {
        "schema_version": 1,
        "projection": "chalxius_candidate_identity",
        "candidate_root": str(candidate),
        "candidate_version": candidate_version,
        "candidate_manifest_valid": candidate_manifest["valid"],
        "candidate_manifest_error": candidate_manifest["error"],
        "candidate_manifest_sha256": candidate_manifest[
            "manifest_file_sha256"
        ],
        "candidate_manifest_entry_count": candidate_manifest[
            "manifest_entry_count"
        ],
        "git": _git_status(candidate),
        "path_version_hints": _path_version_hint(candidate),
        "installed_root": str(installed) if installed is not None else "",
        "installed_version": installed_version,
        "installed_manifest_valid": installed_manifest["valid"],
        "installed_manifest_error": installed_manifest["error"],
        "installed_manifest_sha256": installed_manifest[
            "manifest_file_sha256"
        ],
        "version_matches_installed": same_version,
        "manifest_identity_matches_installed": same_manifest,
        "manifest_difference": difference,
        "selection_status": selection_status,
        "selection_effect": "none",
        "instruction": (
            "Main selects the candidate explicitly from these exact bytes; "
            "directory names and path version hints are diagnostic only."
        ),
    }


def _parser() -> argparse.ArgumentParser:
    defaults = default_global_paths()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Proposed Chalxius candidate root.",
    )
    parser.add_argument(
        "--installed-root",
        type=Path,
        default=defaults["installed_root"],
        help="Installed Chalxius root used only for a read-only comparison.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    projection = project_candidate_identity(args.root, args.installed_root)
    print(json.dumps(projection, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

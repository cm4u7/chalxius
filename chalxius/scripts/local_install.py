#!/usr/bin/env python3
"""Install this Chalxius candidate globally through the default fast path."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True

from mathgraph._local_install import default_global_paths, perform_local_install


def _candidate_root_argument(
    value: Path,
    *,
    cwd: Path | None = None,
) -> Path:
    """Anchor a read-only candidate path without hiding symlink components."""

    if value.is_absolute():
        return value
    return (Path.cwd() if cwd is None else cwd) / value


def _parser() -> argparse.ArgumentParser:
    defaults = default_global_paths()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidate-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help=(
            "Candidate tree; relative paths are anchored to the current "
            "directory and the default is the tree containing this script."
        ),
    )
    parser.add_argument("--installed-root", type=Path, default=defaults["installed_root"])
    parser.add_argument("--archive-root", type=Path, default=defaults["archive_root"])
    parser.add_argument("--rollback-root", type=Path, default=defaults["rollback_root"])
    parser.add_argument(
        "--expected-candidate-manifest-sha256",
        help="Optional independently recorded MANIFEST.sha256 digest.",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    result = perform_local_install(
        candidate_root=_candidate_root_argument(args.candidate_root),
        installed_root=args.installed_root,
        archive_root=args.archive_root,
        rollback_root=args.rollback_root,
        expected_candidate_manifest_sha256=args.expected_candidate_manifest_sha256,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

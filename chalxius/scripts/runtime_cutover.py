#!/usr/bin/env python3
"""Perform one fail-closed Chalxius install or rollback cutover."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True

from mathgraph.runtime_cutover import perform_cutover


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--installed-root", type=Path, required=True)
    parser.add_argument("--rollback-root", type=Path)
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, action="append", default=[])
    parser.add_argument("--confirm-no-protected-projects", action="store_true")
    parser.add_argument(
        "--expected-candidate-manifest-sha256",
        required=True,
        help="Exact SHA-256 of the externally approved candidate MANIFEST.sha256 bytes.",
    )
    parser.add_argument("--expected-installed-runtime-identity")
    parser.add_argument(
        "--project-validation-receipt",
        type=Path,
        help="Approved reusable project-validation receipt built for this exact cutover.",
    )
    parser.add_argument(
        "--expected-project-validation-receipt-sha256",
        help="Exact SHA-256 of the approved project-validation receipt bytes.",
    )
    parser.add_argument(
        "--force-full-project-audit",
        action="store_true",
        help="Run one full protected-project audit before cutover, then reuse its exact snapshot after swap.",
    )
    parser.add_argument("--allow-fresh-install", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--operation", choices=("install", "rollback"), default="install")
    return parser


def main() -> int:
    args = _parser().parse_args()
    result = perform_cutover(
        candidate_root=args.candidate_root,
        installed_root=args.installed_root,
        rollback_root=args.rollback_root,
        archive_root=args.archive_root,
        project_roots=args.project_root,
        confirm_no_protected_projects=args.confirm_no_protected_projects,
        expected_candidate_manifest_sha256=args.expected_candidate_manifest_sha256,
        expected_installed_runtime_identity=args.expected_installed_runtime_identity,
        project_validation_receipt=args.project_validation_receipt,
        expected_project_validation_receipt_sha256=(
            args.expected_project_validation_receipt_sha256
        ),
        force_full_project_audit=args.force_full_project_audit,
        allow_fresh_install=args.allow_fresh_install,
        dry_run=args.dry_run,
        operation=args.operation,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

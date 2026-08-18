#!/usr/bin/env python3
"""Run the release matrix in exact, manifest-bound, mutually isolated lanes."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any

sys.dont_write_bytecode = True

from mathgraph.release_contracts import RELEASE_VALIDATION_MATRIX_REVISION


CONTRACT_REVISION = RELEASE_VALIDATION_MATRIX_REVISION


@dataclass(frozen=True)
class Lane:
    name: str
    command: tuple[str, ...]
    phase: int = 1
    mutation_profile: str | None = None


ROUTINE_LANE_NAMES = frozenset(
    {
        "self_test",
        "changed_surface_tests",
        "aggressive_bug_audit",
    }
)
FORENSIC_LANE_NAMES = frozenset(
    {
        "mutant_registry_preflight",
        "architecture_reconnaissance",
        "behavioral_feature_gate",
        "self_test",
        "full_suite",
        "aggressive_bug_audit",
    }
)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _snapshot(root: Path) -> tuple[tuple[str, str, str, str], ...]:
    entries: list[tuple[str, str, str, str]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root).as_posix()
        mode = f"{stat.S_IMODE(path.lstat().st_mode):o}"
        if path.is_symlink():
            entries.append((relative, "symlink", mode, os.readlink(path)))
        elif path.is_file():
            entries.append((relative, "file", mode, _sha256_bytes(path.read_bytes())))
        elif path.is_dir():
            entries.append((relative, "directory", mode, ""))
        else:
            entries.append((relative, "other", mode, ""))
    return tuple(entries)


def _manifest_entries(root: Path) -> tuple[list[str], str]:
    manifest = root / "MANIFEST.sha256"
    if manifest.is_symlink() or not manifest.is_file():
        raise ValueError("MANIFEST.sha256 must be one regular file")
    manifest_bytes = manifest.read_bytes()
    entries: list[str] = []
    for line_number, line in enumerate(
        manifest_bytes.decode("utf-8").splitlines(), 1
    ):
        digest, separator, relative = line.partition("  ")
        path = PurePosixPath(relative)
        if (
            not separator
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or path.is_absolute()
            or ".." in path.parts
            or relative == "MANIFEST.sha256"
        ):
            raise ValueError(f"invalid manifest row {line_number}")
        source = root / relative
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"manifest member is not a regular file: {relative}")
        if _sha256_bytes(source.read_bytes()) != digest:
            raise ValueError(f"manifest digest mismatch: {relative}")
        entries.append(relative)
    if entries != sorted(entries) or len(entries) != len(set(entries)):
        raise ValueError("manifest paths must be sorted and unique")
    actual = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink() and path.name != "MANIFEST.sha256"
    )
    links_or_other = [
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_symlink() or (not path.is_file() and not path.is_dir())
    ]
    if links_or_other or actual != entries:
        raise ValueError("manifest path set does not equal the exact regular-file set")
    return entries, _sha256_bytes(manifest_bytes)


def _copy_manifest_tree(source: Path, destination: Path, entries: list[str]) -> None:
    if destination.exists():
        raise ValueError(f"validation lane already exists: {destination}")
    destination.mkdir(parents=True)
    for relative in [*entries, "MANIFEST.sha256"]:
        origin = source / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, target, follow_symlinks=False)
        os.chmod(target, stat.S_IMODE(origin.stat().st_mode))
    lane_entries, lane_manifest = _manifest_entries(destination)
    source_manifest = _sha256_bytes((source / "MANIFEST.sha256").read_bytes())
    if lane_entries != entries or lane_manifest != source_manifest:
        raise RuntimeError("isolated validation lane identity mismatch")


def _run_lane(
    *,
    lane: Lane,
    lane_root: Path,
    manifest_sha256: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    before = _snapshot(lane_root)
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment.pop("PYTHONPYCACHEPREFIX", None)
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(lane_root / "scripts"), environment.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    lane_temp = lane_root.parent / "host-temp"
    lane_temp.mkdir(parents=True, exist_ok=True)
    environment["TMPDIR"] = str(lane_temp)
    environment["TMP"] = str(lane_temp)
    environment["TEMP"] = str(lane_temp)
    environment["CHALXIUS_RUNTIME_ARCHIVE_ROOT"] = str(
        lane_root.parent / "runtime-archive" / "chalxius"
    )
    started = time.monotonic()
    timed_out = False
    try:
        outcome = subprocess.run(
            list(lane.command),
            cwd=lane_root,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=timeout_seconds,
        )
        returncode = outcome.returncode
        output = outcome.stdout
    except subprocess.TimeoutExpired as error:
        timed_out = True
        returncode = 124
        raw_output = error.stdout or ""
        output = (
            raw_output.decode("utf-8", errors="replace")
            if isinstance(raw_output, bytes)
            else raw_output
        )
    duration = round(time.monotonic() - started, 3)
    lane_unchanged = before == _snapshot(lane_root)
    return {
        "lane": lane.name,
        "phase": lane.phase,
        "mutation_profile": lane.mutation_profile,
        "manifest_sha256": manifest_sha256,
        "returncode": returncode,
        "timed_out": timed_out,
        "duration_seconds": duration,
        "lane_unchanged": lane_unchanged,
        "output_sha256": _sha256_bytes(output.encode("utf-8")),
        "output_tail": output[-2000:],
        "ok": returncode == 0 and not timed_out and lane_unchanged,
    }


def _default_lanes(python: str, *, forensic: bool = False) -> tuple[Lane, ...]:
    if not forensic:
        return (
            Lane("self_test", (python, "scripts/self_test.py"), phase=1),
            Lane(
                "changed_surface_tests",
                (
                    python,
                    "-m",
                    "unittest",
                    "tests.test_release_validation",
                    "tests.test_host_entrypoint_nonmutation",
                    "tests.test_architecture_reconnaissance",
                ),
                phase=1,
            ),
            Lane(
                "aggressive_bug_audit",
                (
                    python,
                    "scripts/aggressive_bug_audit.py",
                    "--profile",
                    "semantic",
                ),
                phase=2,
                mutation_profile="semantic",
            ),
        )

    return (
        Lane(
            "mutant_registry_preflight",
            (
                python,
                "scripts/aggressive_bug_audit.py",
                "--preflight-only",
                "--profile",
                "full",
            ),
            phase=1,
            mutation_profile="full",
        ),
        Lane(
            "architecture_reconnaissance",
            (
                python,
                "scripts/architecture_reconnaissance.py",
                "--root",
                ".",
                "--quiet",
                "--strict",
            ),
            phase=1,
        ),
        Lane(
            "behavioral_feature_gate",
            (
                python,
                "scripts/behavioral_feature_gate.py",
                "--root",
                ".",
            ),
            phase=2,
        ),
        Lane("self_test", (python, "scripts/self_test.py"), phase=3),
        Lane(
            "full_suite",
            (
                python,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                "test_*.py",
            ),
            phase=3,
        ),
        Lane(
            "aggressive_bug_audit",
            (
                python,
                "scripts/aggressive_bug_audit.py",
                "--profile",
                "full",
            ),
            phase=4,
            mutation_profile="full",
        ),
    )


def _skipped_lane_result(
    *, lane: Lane, manifest_sha256: str, failed_phase: int
) -> dict[str, Any]:
    return {
        "lane": lane.name,
        "phase": lane.phase,
        "mutation_profile": lane.mutation_profile,
        "manifest_sha256": manifest_sha256,
        "returncode": 126,
        "timed_out": False,
        "duration_seconds": 0.0,
        "lane_unchanged": True,
        "output_sha256": _sha256_bytes(
            f"skipped_after_failed_phase:{failed_phase}".encode("utf-8")
        ),
        "output_tail": f"skipped: prior validation phase {failed_phase} failed",
        "skipped_due_to_prior_phase": True,
        "ok": False,
    }


def _isolated_lane_roots(
    workspace: Path, lane_names: list[str]
) -> dict[str, Path]:
    canonical_workspace = workspace.resolve()
    roots = {
        name: canonical_workspace / name / "chalxius" for name in lane_names
    }
    resolved = [root.resolve() for root in roots.values()]
    if len(resolved) != len(set(resolved)):
        raise RuntimeError("validation lanes must not share a mutable root")
    return roots


def _aggregate(
    *,
    expected_lanes: tuple[Lane, ...],
    manifest_sha256: str,
    results: list[dict[str, Any]],
    source_unchanged: bool,
) -> dict[str, Any]:
    expected_names = sorted(lane.name for lane in expected_lanes)
    observed_names = sorted(str(result.get("lane", "")) for result in results)
    complete = observed_names == expected_names and len(observed_names) == len(
        set(observed_names)
    )
    one_identity = all(
        result.get("manifest_sha256") == manifest_sha256 for result in results
    )
    lanes_ok = complete and all(result.get("ok") is True for result in results)
    return {
        "schema_version": 1,
        "contract_revision": CONTRACT_REVISION,
        "manifest_sha256": manifest_sha256,
        "source_unchanged": source_unchanged,
        "lanes": sorted(results, key=lambda item: str(item.get("lane", ""))),
        "truth_effect": "none",
        "ok": (
            source_unchanged
            and one_identity
            and lanes_ok
        ),
    }


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidate-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--timeout-seconds", type=int, default=1200)
    parser.add_argument(
        "--forensic",
        action="store_true",
        help=(
            "run the complete forensic matrix, including the full mutation "
            "registry, full suite, behavioral gate, and architecture scan"
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    candidate = args.candidate_root.expanduser().resolve()
    expected_manifest = args.expected_manifest_sha256
    if len(expected_manifest) != 64 or any(
        character not in "0123456789abcdef" for character in expected_manifest
    ):
        raise ValueError("--expected-manifest-sha256 must be lowercase SHA-256")
    if args.timeout_seconds <= 0:
        raise ValueError("--timeout-seconds must be positive")
    receipt = args.receipt.expanduser().resolve() if args.receipt else None
    if receipt is not None and (receipt == candidate or candidate in receipt.parents):
        raise ValueError("--receipt must be outside the candidate tree")

    entries, manifest_sha256 = _manifest_entries(candidate)
    if manifest_sha256 != expected_manifest:
        raise ValueError("candidate manifest identity does not match approved identity")
    source_before = _snapshot(candidate)

    lock_dir = Path(tempfile.gettempdir()) / "chalxius-release-validation-locks"
    lock_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock_key = _sha256_bytes(str(candidate).encode("utf-8"))
    lock_path = lock_dir / f"{lock_key}.lock"
    lock_handle = lock_path.open("a+b")
    try:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("another validation matrix owns this candidate") from error
        lanes = _default_lanes(args.python, forensic=args.forensic)
        with tempfile.TemporaryDirectory(prefix="chalxius-release-validation-") as temporary:
            workspace = Path(temporary)
            lane_roots = _isolated_lane_roots(
                workspace, [lane.name for lane in lanes]
            )
            for root in lane_roots.values():
                _copy_manifest_tree(candidate, root, entries)
            results: list[dict[str, Any]] = []
            failed_phase: int | None = None
            for phase in sorted({lane.phase for lane in lanes}):
                phase_lanes = [lane for lane in lanes if lane.phase == phase]
                if failed_phase is not None:
                    results.extend(
                        _skipped_lane_result(
                            lane=lane,
                            manifest_sha256=manifest_sha256,
                            failed_phase=failed_phase,
                        )
                        for lane in phase_lanes
                    )
                    continue
                with ThreadPoolExecutor(max_workers=len(phase_lanes)) as executor:
                    futures = {
                        executor.submit(
                            _run_lane,
                            lane=lane,
                            lane_root=lane_roots[lane.name],
                            manifest_sha256=manifest_sha256,
                            timeout_seconds=args.timeout_seconds,
                        ): lane
                        for lane in phase_lanes
                    }
                    for future in as_completed(futures):
                        lane = futures[future]
                        try:
                            results.append(future.result())
                        except Exception as error:  # fail closed into the aggregate receipt
                            results.append(
                                {
                                    "lane": lane.name,
                                    "phase": lane.phase,
                                    "manifest_sha256": manifest_sha256,
                                    "returncode": 125,
                                    "timed_out": False,
                                    "duration_seconds": 0.0,
                                    "lane_unchanged": False,
                                    "output_sha256": _sha256_bytes(str(error).encode("utf-8")),
                                    "output_tail": f"{type(error).__name__}: {error}",
                                    "ok": False,
                                }
                            )
                if any(
                    result.get("phase") == phase and result.get("ok") is not True
                    for result in results
                ):
                    failed_phase = phase
        source_unchanged = source_before == _snapshot(candidate)
        report = _aggregate(
            expected_lanes=lanes,
            manifest_sha256=manifest_sha256,
            results=results,
            source_unchanged=source_unchanged,
        )
        payload = (
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        if receipt is not None:
            _atomic_write(receipt, payload)
        sys.stdout.buffer.write(payload)
        return 0 if report["ok"] else 1
    finally:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        lock_handle.close()


if __name__ == "__main__":
    raise SystemExit(main())

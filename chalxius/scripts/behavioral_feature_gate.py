#!/usr/bin/env python3
"""Execute the normal-flow and lifecycle-boundary feature probes.

Architecture reconnaissance proves that a production entry calls a producer,
that a consumer calls the handoff validator, and that named probes exist.  This
second gate executes the positive, predicate-false, and tamper probes in fresh
subprocesses.  It also executes one boundary probe for each deliberately
manual, external, compatibility, replaced, or retired feature so an orphan
disposition cannot remain prose-only.  It is nontruth release evidence:
passing it proves the declared behavior under the probes, not that any research
claim is true.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any

sys.dont_write_bytecode = True


CONTRACT_REVISION = "chalxius-behavioral-feature-gate-2"
REGISTRY_REVISION = "chalxius-behavioral-feature-registry-3"
REGISTRY_RELATIVE = Path("references/behavioral_feature_registry.json")
PROBE_ROLES = ("positive", "predicate_false", "tamper")
BOUNDARY_PROBE_ROLE = "boundary"
ROLE_ORDER = (*PROBE_ROLES, BOUNDARY_PROBE_ROLE)
QUALNAME_RE = re.compile(
    r"tests\.test_[a-zA-Z0-9_]+(?:\.[a-zA-Z_][a-zA-Z0-9_]*)+\.test_[a-zA-Z0-9_]+"
)
GENERATED_PARTS = frozenset(
    {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON object key: {key}")
        value[key] = item
    return value


def _snapshot(root: Path) -> tuple[tuple[str, str, str, str], ...]:
    """Content-bind the candidate while excluding no source-like artifacts."""

    records: list[tuple[str, str, str, str]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root).as_posix()
        if any(part in GENERATED_PARTS for part in path.parts):
            # Generated caches are rejected by architecture reconnaissance and
            # are irrelevant to whether a probe changed the source tree.
            continue
        mode = f"{stat.S_IMODE(path.lstat().st_mode):o}"
        if path.is_symlink():
            records.append((relative, "symlink", mode, os.readlink(path)))
        elif path.is_file():
            records.append((relative, "file", mode, _sha256(path.read_bytes())))
        elif path.is_dir():
            records.append((relative, "directory", mode, ""))
        else:
            records.append((relative, "other", mode, ""))
    return tuple(records)


def _snapshot_sha256(snapshot: tuple[tuple[str, str, str, str], ...]) -> str:
    return _sha256(_canonical_bytes(snapshot))


def _load_probe_plan(root: Path) -> tuple[str, list[dict[str, str]]]:
    path = root / REGISTRY_RELATIVE
    if path.is_symlink() or not path.is_file():
        raise ValueError("behavioral feature registry is missing or unsafe")
    raw_bytes = path.read_bytes()
    try:
        raw = json.loads(raw_bytes, object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("behavioral feature registry is invalid JSON") from error
    if not isinstance(raw, dict) or set(raw) != {
        "schema_version",
        "contract_revision",
        "truth_effect",
        "features",
    }:
        raise ValueError("behavioral feature registry top-level fields are invalid")
    if (
        raw["schema_version"] != 1
        or raw["contract_revision"] != REGISTRY_REVISION
        or raw["truth_effect"] != "none"
        or not isinstance(raw["features"], dict)
    ):
        raise ValueError("behavioral feature registry contract is invalid")

    plan: list[dict[str, str]] = []
    required_features = 0
    for feature_id, feature in sorted(raw["features"].items()):
        if not isinstance(feature_id, str) or not isinstance(feature, dict):
            raise ValueError("behavioral feature record is invalid")
        classification = feature.get("classification")
        if classification != "normal_flow":
            if feature.get("required") is not False:
                raise ValueError(f"bounded feature is unexpectedly required: {feature_id}")
            lifecycle_decision = feature.get("lifecycle_decision")
            valid_boundary_decision = (
                classification in {"explicit_manual", "external_api", "compatibility"}
                and lifecycle_decision == "retain_bounded"
            ) or (
                classification == "dormant"
                and lifecycle_decision
                in {"replace_with_authoritative_mechanism", "retire"}
            ) or (
                classification == "deprecated" and lifecycle_decision == "retire"
            )
            if not valid_boundary_decision:
                raise ValueError(
                    f"feature classification/lifecycle disposition is invalid: {feature_id}"
                )
            boundary_probe = feature.get("boundary_probe")
            if (
                not isinstance(boundary_probe, str)
                or QUALNAME_RE.fullmatch(boundary_probe) is None
            ):
                raise ValueError(f"invalid boundary probe qualname: {feature_id}")
            plan.append(
                {
                    "feature_id": feature_id,
                    "probe_role": BOUNDARY_PROBE_ROLE,
                    "qualname": boundary_probe,
                }
            )
            continue
        required_features += 1
        if feature.get("required") is not True:
            raise ValueError(f"normal-flow feature is not required: {feature_id}")
        if feature.get("lifecycle_decision") != "retain_and_integrate":
            raise ValueError(
                f"normal-flow feature is not dispositioned for integration: {feature_id}"
            )
        probes = feature.get("probes")
        if not isinstance(probes, dict) or set(probes) != set(PROBE_ROLES):
            raise ValueError(f"feature probe roles are incomplete: {feature_id}")
        qualnames: list[str] = []
        for role in PROBE_ROLES:
            qualname = probes.get(role)
            if not isinstance(qualname, str) or QUALNAME_RE.fullmatch(qualname) is None:
                raise ValueError(f"invalid {role} probe qualname: {feature_id}")
            qualnames.append(qualname)
            plan.append(
                {"feature_id": feature_id, "probe_role": role, "qualname": qualname}
            )
        if len(set(qualnames)) != len(PROBE_ROLES):
            raise ValueError(
                f"positive, predicate-false, and tamper probes must be distinct: {feature_id}"
            )
    if required_features == 0:
        raise ValueError("behavioral registry has no required normal-flow features")
    return _sha256(raw_bytes), plan


def _run_probe(
    *,
    root: Path,
    probe: dict[str, str],
    python: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment.pop("PYTHONPYCACHEPREFIX", None)
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(root / "scripts"), str(root), environment.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    started = time.monotonic()
    timed_out = False
    try:
        outcome = subprocess.run(
            [python, "-B", "-m", "unittest", "-v", probe["qualname"]],
            cwd=root,
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
    return {
        **probe,
        "returncode": returncode,
        "timed_out": timed_out,
        "duration_seconds": duration,
        "output_sha256": _sha256(output.encode("utf-8")),
        "output_tail": output[-1000:],
        "ok": returncode == 0 and not timed_out,
    }


def _execute_probe_plan(
    *,
    root: Path,
    plan: list[dict[str, str]],
    python: str,
    timeout_seconds: int,
    workers: int,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(workers, len(plan))) as executor:
        futures = {
            executor.submit(
                _run_probe,
                root=root,
                probe=probe,
                python=python,
                timeout_seconds=timeout_seconds,
            ): probe
            for probe in plan
        }
        for future in as_completed(futures):
            probe = futures[future]
            try:
                results.append(future.result())
            except Exception as error:
                message = f"{type(error).__name__}: {error}"
                results.append(
                    {
                        **probe,
                        "returncode": 125,
                        "timed_out": False,
                        "duration_seconds": 0.0,
                        "output_sha256": _sha256(message.encode("utf-8")),
                        "output_tail": message,
                        "ok": False,
                    }
                )
    return sorted(
        results,
        key=lambda item: (item["feature_id"], ROLE_ORDER.index(item["probe_role"])),
    )


def _report(
    *,
    registry_sha256: str,
    plan: list[dict[str, str]],
    results: list[dict[str, Any]],
    source_before_sha256: str,
    source_after_sha256: str,
) -> dict[str, Any]:
    feature_ids = sorted({item["feature_id"] for item in plan})
    feature_results = []
    for feature_id in feature_ids:
        probes = [item for item in results if item["feature_id"] == feature_id]
        observed_roles = [item["probe_role"] for item in probes]
        expected_roles = (
            [BOUNDARY_PROBE_ROLE]
            if BOUNDARY_PROBE_ROLE in observed_roles
            else list(PROBE_ROLES)
        )
        feature_results.append(
            {
                "feature_id": feature_id,
                "probe_count": len(probes),
                "roles": observed_roles,
                "ok": observed_roles == expected_roles
                and all(item.get("ok") is True for item in probes),
            }
        )
    semantic = {
        "schema_version": 1,
        "contract_revision": CONTRACT_REVISION,
        "registry_sha256": registry_sha256,
        "probe_plan_sha256": _sha256(_canonical_bytes(plan)),
        "feature_count": len(feature_ids),
        "probe_count": len(plan),
        "source_before_sha256": source_before_sha256,
        "source_after_sha256": source_after_sha256,
        "source_unchanged": source_before_sha256 == source_after_sha256,
        "features": feature_results,
        "probes": results,
        "truth_effect": "none",
        "ok": (
            len(results) == len(plan)
            and source_before_sha256 == source_after_sha256
            and all(item["ok"] for item in feature_results)
        ),
    }
    return {**semantic, "receipt_sha256": _sha256(_canonical_bytes(semantic))}


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--timeout-seconds", type=int, default=240)
    parser.add_argument("--workers", type=int, default=4)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    root = args.root.expanduser().resolve()
    if root.is_symlink() or not root.is_dir():
        raise ValueError("candidate root must be one regular directory")
    if args.timeout_seconds <= 0 or args.workers <= 0 or args.workers > 16:
        raise ValueError("probe timeout/workers are outside the supported range")
    receipt_path = args.receipt.expanduser().resolve() if args.receipt else None
    if receipt_path is not None and (
        receipt_path == root or root in receipt_path.parents
    ):
        raise ValueError("behavioral feature receipt must be outside the candidate tree")

    registry_sha256, plan = _load_probe_plan(root)
    before = _snapshot(root)
    results = _execute_probe_plan(
        root=root,
        plan=plan,
        python=args.python,
        timeout_seconds=args.timeout_seconds,
        workers=args.workers,
    )
    after = _snapshot(root)
    report = _report(
        registry_sha256=registry_sha256,
        plan=plan,
        results=results,
        source_before_sha256=_snapshot_sha256(before),
        source_after_sha256=_snapshot_sha256(after),
    )
    payload = (
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    if receipt_path is not None:
        _atomic_write(receipt_path, payload)
    sys.stdout.buffer.write(payload)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
import hashlib
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable

from .contracts import SHA256_RE, sha256_bytes, validate_round_id
from .runtime_archive import (
    _assert_no_symlink_components,
    archive_runtime,
    resolve_historical_runtime,
    runtime_binding_from_root,
    trusted_runtime_archive_root,
    validate_bound_runtime_at,
    validate_runtime_binding,
)


CUTOVER_CONTRACT_REVISION = "chalxius-runtime-cutover-2"
CUTOVER_PROJECT_REQUEST_REVISION = "chalxius-cutover-project-validation-request-1"
CUTOVER_PROJECT_RECEIPT_REVISION = "chalxius-cutover-project-validation-receipt-2"
LEGACY_CUTOVER_PROJECT_RECEIPT_REVISION = (
    "chalxius-cutover-project-validation-receipt-1"
)
PRIOR_AUDIT_ANCHOR_REVISION = "chalxius-prior-project-audit-anchor-2"
PROJECT_STATE_SNAPSHOT_REVISION = "chalxius-project-state-snapshot-1"
ADMINISTRATIVE_SLO_SECONDS = 120
ADMINISTRATIVE_EXTENDED_SLO_SECONDS = 240
PROJECT_VALIDATION_TIMEOUT_SECONDS = 1200
MAX_PROJECT_VALIDATION_TIMEOUT_SECONDS = 86_400
MAX_PRIOR_RECEIPT_ANCESTRY_DEPTH = 32

_PROJECT_SNAPSHOT_EXCLUDED_TOP_LEVEL = frozenset({"output", "work"})
_PROJECT_SNAPSHOT_EXCLUDED_NAMES = frozenset(
    {".DS_Store", ".mathgraph.lock", "__pycache__"}
)


def _validated_project_validation_timeout(value: Any) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 1
        or value > MAX_PROJECT_VALIDATION_TIMEOUT_SECONDS
    ):
        raise ValueError("protected-project runtime timeout is invalid")
    return value


def _canonical_path(
    value: Path | str,
    *,
    label: str,
    allow_missing: bool,
) -> Path:
    text = str(value)
    path = Path(text)
    if (
        not path.is_absolute()
        or path.anchor != "/"
        or ".." in path.parts
        or str(path) != text
    ):
        raise ValueError(f"{label} must be one canonical absolute path")
    _assert_no_symlink_components(
        path,
        label=label,
        allow_missing=allow_missing,
    )
    return path


def _existing_directory(value: Path | str, *, label: str) -> Path:
    path = _canonical_path(value, label=label, allow_missing=False)
    if path.is_symlink() or not path.is_dir():
        raise ValueError(f"{label} must be an existing regular directory")
    return path


def _nonexistent_sibling(value: Path | str, *, installed_root: Path) -> Path:
    path = _canonical_path(
        value,
        label="Chalxius rollback root",
        allow_missing=True,
    )
    if path.parent != installed_root.parent or path == installed_root:
        raise ValueError("Chalxius rollback root must be a distinct installed-root sibling")
    if path.exists() or path.is_symlink():
        raise ValueError("Chalxius rollback root already exists")
    return path


def _read_json_file(path: Path, *, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{label} must be one regular file")
    try:
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must contain one object")
    return payload


def _approved_json_file(
    value: Path | str,
    expected_sha256: str | None,
    *,
    label: str,
) -> tuple[Path, dict[str, Any], str]:
    path = _canonical_path(value, label=label, allow_missing=False)
    if not isinstance(expected_sha256, str) or SHA256_RE.fullmatch(
        expected_sha256
    ) is None:
        raise ValueError(f"{label} requires an approved SHA-256")
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{label} must be one regular file")
    raw = path.read_bytes()
    actual = sha256_bytes(raw)
    if actual != expected_sha256:
        raise ValueError(f"{label} differs from the approved SHA-256")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must contain one object")
    return path, payload, actual


def _exact_sha256(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{label} is not one SHA-256 digest")
    return value


def _canonical_path_text(value: Any, *, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be one canonical absolute path")
    return str(_canonical_path(value, label=label, allow_missing=True))


def _manifest_hashes(root: Path) -> dict[str, str]:
    manifest = root / "MANIFEST.sha256"
    if manifest.is_symlink() or not manifest.is_file():
        raise ValueError("Chalxius runtime manifest is missing or unsafe")
    try:
        lines = manifest.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise ValueError("Chalxius runtime manifest is not UTF-8") from exc
    entries: dict[str, str] = {}
    for line in lines:
        if line.count("  ") != 1:
            raise ValueError("Chalxius runtime manifest line is malformed")
        digest, relative = line.split("  ", 1)
        path = Path(relative)
        if (
            SHA256_RE.fullmatch(digest) is None
            or not relative
            or path.is_absolute()
            or ".." in path.parts
            or relative == "MANIFEST.sha256"
            or relative in entries
        ):
            raise ValueError("Chalxius runtime manifest entry is malformed")
        entries[relative] = digest
    if not entries:
        raise ValueError("Chalxius runtime manifest is empty")
    return entries


def _changed_runtime_paths(candidate: Path, installed: Path) -> list[str]:
    candidate_entries = _manifest_hashes(candidate)
    installed_entries = _manifest_hashes(installed)
    return sorted(
        relative
        for relative in set(candidate_entries) | set(installed_entries)
        if candidate_entries.get(relative) != installed_entries.get(relative)
    )


def _project_state_snapshot(project: Path) -> dict[str, Any]:
    """Hash the audit-relevant project bytes without reconstructing graph semantics."""

    digest = hashlib.sha256()
    file_count = 0
    byte_count = 0
    latest_mtime_ns = 0
    for current_raw, directory_names, file_names in os.walk(
        project, followlinks=False
    ):
        current = Path(current_raw)
        relative_current = current.relative_to(project)
        kept_directories: list[str] = []
        for name in sorted(directory_names):
            if (
                relative_current == Path(".")
                and name in _PROJECT_SNAPSHOT_EXCLUDED_TOP_LEVEL
            ) or name in _PROJECT_SNAPSHOT_EXCLUDED_NAMES:
                continue
            child = current / name
            mode = os.lstat(child).st_mode
            if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
                raise ValueError("protected project state contains an unsafe directory")
            relative = child.relative_to(project).as_posix()
            digest.update(b"D\0" + relative.encode("utf-8") + b"\n")
            kept_directories.append(name)
        directory_names[:] = kept_directories
        for name in sorted(file_names):
            if name in _PROJECT_SNAPSHOT_EXCLUDED_NAMES or name.endswith(".pyc"):
                continue
            child = current / name
            mode = os.lstat(child).st_mode
            if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
                raise ValueError("protected project state contains an unsafe file")
            raw = child.read_bytes()
            relative = child.relative_to(project).as_posix()
            content_sha256 = sha256_bytes(raw)
            digest.update(b"F\0" + relative.encode("utf-8") + b"\0")
            digest.update(content_sha256.encode("ascii") + b"\n")
            metadata = os.lstat(child)
            file_count += 1
            byte_count += len(raw)
            latest_mtime_ns = max(latest_mtime_ns, metadata.st_mtime_ns)
    return {
        "snapshot_revision": PROJECT_STATE_SNAPSHOT_REVISION,
        "project_root": str(project),
        "state_sha256": digest.hexdigest(),
        "state_file_count": file_count,
        "state_byte_count": byte_count,
        "latest_mtime_ns": latest_mtime_ns,
        "excluded_top_level": sorted(_PROJECT_SNAPSHOT_EXCLUDED_TOP_LEVEL),
        "truth_effect": "none",
    }


def _same_project_snapshot(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return left == right


def _validate_project_state_payload(
    value: Any,
    *,
    project_root: Path,
) -> dict[str, Any]:
    expected = {
        "snapshot_revision",
        "project_root",
        "state_sha256",
        "state_file_count",
        "state_byte_count",
        "latest_mtime_ns",
        "excluded_top_level",
        "truth_effect",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("prior project-audit snapshot fields are not exact")
    if (
        value.get("snapshot_revision") != PROJECT_STATE_SNAPSHOT_REVISION
        or value.get("project_root") != str(project_root)
        or not isinstance(value.get("state_sha256"), str)
        or SHA256_RE.fullmatch(value["state_sha256"]) is None
        or any(
            isinstance(value.get(field), bool)
            or not isinstance(value.get(field), int)
            or value[field] < 0
            for field in (
                "state_file_count",
                "state_byte_count",
                "latest_mtime_ns",
            )
        )
        or value.get("excluded_top_level")
        != sorted(_PROJECT_SNAPSHOT_EXCLUDED_TOP_LEVEL)
        or value.get("truth_effect") != "none"
    ):
        raise ValueError("prior project-audit snapshot is invalid")
    return dict(value)


def _parse_utc_timestamp_ns(value: Any) -> int:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("prior project-audit anchor timestamp is invalid")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("prior project-audit anchor timestamp is invalid") from exc
    return int(parsed.timestamp() * 1_000_000_000)


def _validate_runtime_tree(
    root: Path,
    *,
    archive_root: Path,
    exact_file_set: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    binding = runtime_binding_from_root(root, archive_root=archive_root)
    result = validate_bound_runtime_at(
        root,
        binding,
        verify_manifest_tree=True,
        require_exact_file_set=exact_file_set,
    )
    return binding, result


def _run_json_command(
    runtime_root: Path,
    args: list[str],
    *,
    archive_root: Path,
    phase: str = "protected_project_validation",
    timeout_seconds: int = PROJECT_VALIDATION_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    executable = runtime_root / "scripts" / "mgraph"
    if executable.is_symlink() or not executable.is_file():
        raise ValueError("candidate runtime has no safe scripts/mgraph entrypoint")
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["CHALXIUS_RUNTIME_ARCHIVE_ROOT"] = str(archive_root)
    timeout_seconds = _validated_project_validation_timeout(timeout_seconds)
    started = time.monotonic()
    print(
        f"[chalxius-cutover] phase={phase} status=started "
        f"timeout_seconds={timeout_seconds}",
        file=sys.stderr,
        flush=True,
    )
    try:
        outcome = subprocess.run(
            [str(executable), *args],
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        duration = round(time.monotonic() - started, 3)
        print(
            f"[chalxius-cutover] phase={phase} status=timed_out "
            f"duration_seconds={duration}",
            file=sys.stderr,
            flush=True,
        )
        raise ValueError(
            f"protected-project runtime check timed out in {phase} after "
            f"{timeout_seconds} seconds"
        ) from exc
    duration = round(time.monotonic() - started, 3)
    if duration > ADMINISTRATIVE_EXTENDED_SLO_SECONDS:
        print(
            f"[chalxius-cutover] phase={phase} status=slo_overrun "
            f"target_seconds={ADMINISTRATIVE_EXTENDED_SLO_SECONDS} "
            f"duration_seconds={duration}",
            file=sys.stderr,
            flush=True,
        )
    elif duration > ADMINISTRATIVE_SLO_SECONDS:
        print(
            f"[chalxius-cutover] phase={phase} status=slo_warning "
            f"target_seconds={ADMINISTRATIVE_SLO_SECONDS} "
            f"duration_seconds={duration}",
            file=sys.stderr,
            flush=True,
        )
    print(
        f"[chalxius-cutover] phase={phase} status=completed "
        f"duration_seconds={duration} returncode={outcome.returncode}",
        file=sys.stderr,
        flush=True,
    )
    if outcome.returncode != 0:
        detail = (outcome.stderr or outcome.stdout).strip()
        raise ValueError(f"protected-project runtime check failed: {detail}")
    try:
        payload = json.loads(outcome.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("protected-project runtime check did not return one JSON object") from exc
    if not isinstance(payload, dict):
        raise ValueError("protected-project runtime check returned a non-object")
    return payload


def _round_bindings(project_root: Path) -> list[dict[str, Any]]:
    rounds_root = project_root / "rounds"
    if not rounds_root.exists() and not rounds_root.is_symlink():
        return []
    rounds_root = _existing_directory(rounds_root, label="Chalxius project rounds root")
    bindings: list[dict[str, Any]] = []
    for round_root in sorted(rounds_root.iterdir(), key=lambda item: item.name):
        if round_root.is_symlink() or not round_root.is_dir():
            raise ValueError("Chalxius project rounds root contains an unsafe entry")
        # Atomic round construction uses a hidden same-filesystem staging
        # directory.  It is intentionally not a published round and therefore
        # has no terminal-state or historical-runtime authority.  A process
        # interruption may leave one behind; ignore only this exact private
        # namespace while retaining fail-closed treatment for every other
        # unexpected entry.
        if _is_private_round_staging_name(round_root.name):
            continue
        validate_round_id(round_root.name)
        cards_root = _existing_directory(
            round_root / "task-cards",
            label="Chalxius round task-card root",
        )
        cards = sorted(cards_root.glob("*.json"))
        if not cards:
            raise ValueError("Chalxius protected round has no task cards")
        identities: set[str] = set()
        binding_presence: set[bool] = set()
        for card_path in cards:
            if card_path.is_symlink() or not card_path.is_file():
                raise ValueError("Chalxius protected round has an unsafe task card")
            try:
                card = json.loads(card_path.read_text(encoding="utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("Chalxius protected task card is not valid JSON") from exc
            if not isinstance(card, dict):
                raise ValueError("Chalxius protected task card must contain one object")
            has_runtime_binding = "runtime_binding" in card
            binding_presence.add(has_runtime_binding)
            if not has_runtime_binding:
                continue
            binding = validate_runtime_binding(card["runtime_binding"])
            identities.add(binding["runtime_identity_sha256"])
            bindings.append(binding)
        if len(binding_presence) != 1:
            raise ValueError(
                "one protected round mixes legacy and runtime-bound task cards"
            )
        if len(identities) > 1:
            raise ValueError("one protected round binds multiple Chalxius runtimes")
    return bindings


def _is_private_round_staging_name(name: str) -> bool:
    """Recognize only the unpublished atomic-round staging namespace."""

    return re.fullmatch(r"\.round-[^.]+\.staging-[0-9a-f]+", name) is not None


def _protected_round_ids(project_root: Path) -> list[str]:
    rounds_root = project_root / "rounds"
    if not rounds_root.exists() and not rounds_root.is_symlink():
        return []
    rounds_root = _existing_directory(
        rounds_root,
        label="Chalxius project rounds root",
    )
    round_ids: list[str] = []
    for child in sorted(rounds_root.iterdir(), key=lambda item: item.name):
        if child.is_symlink() or not child.is_dir():
            raise ValueError("Chalxius project rounds root contains an unsafe entry")
        if _is_private_round_staging_name(child.name):
            continue
        round_ids.append(validate_round_id(child.name))
    return round_ids


def _validated_round_states(
    payload: dict[str, Any],
    *,
    project_root: Path,
    require_current_audit: bool,
) -> dict[str, str]:
    if require_current_audit and payload.get("current_ok") is not True:
        raise ValueError("protected project audit is not current_ok")
    round_states = payload.get("round_states")
    expected_ids = _protected_round_ids(project_root)
    if (
        not isinstance(round_states, dict)
        or list(round_states) != expected_ids
        or any(not isinstance(key, str) for key in round_states)
        or any(
            state not in {"active", "aborted", "completed"}
            for state in round_states.values()
        )
    ):
        raise ValueError("protected-project batch round state is malformed or incomplete")
    nonterminal = [
        round_id
        for round_id, state in round_states.items()
        if state not in {"aborted", "completed"}
    ]
    if nonterminal:
        raise ValueError(
            "protected rounds are not terminal: " + ", ".join(nonterminal)
        )
    return dict(round_states)


def validate_protected_projects(
    runtime_root: Path,
    project_roots: Iterable[Path],
    *,
    archive_root: Path,
    timeout_seconds: int = PROJECT_VALIDATION_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    projects: list[dict[str, Any]] = []
    bindings: dict[str, dict[str, Any]] = {}
    candidate_subprocess_count = 0
    for raw_project in project_roots:
        project = _existing_directory(raw_project, label="Chalxius protected project")
        round_bindings = _round_bindings(project)
        audit = _run_json_command(
            runtime_root,
            ["--root", str(project), "--role", "operator", "audit"],
            archive_root=archive_root,
            phase=f"deep_project_audit:{project.name}",
            timeout_seconds=timeout_seconds,
        )
        candidate_subprocess_count += 1
        round_states = _validated_round_states(
            audit,
            project_root=project,
            require_current_audit=True,
        )
        for binding in round_bindings:
            bindings[binding["runtime_identity_sha256"]] = binding
        projects.append(
            {
                "project_root": str(project),
                "round_states": round_states,
                "audit_current_ok": True,
            }
        )
    return {
        "projects": projects,
        "runtime_bindings": sorted(
            bindings.values(),
            key=lambda item: item["runtime_identity_sha256"],
        ),
        "candidate_subprocess_count": candidate_subprocess_count,
    }


def validate_protected_projects_bounded(
    runtime_root: Path,
    project_roots: Iterable[Path],
    *,
    archive_root: Path,
    prior_audit_projects: Iterable[dict[str, Any]] | None = None,
    prior_audit_runtime_bindings: Iterable[dict[str, Any]] | None = None,
    project_snapshots: dict[str, dict[str, Any]] | None = None,
    timeout_seconds: int = PROJECT_VALIDATION_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Reuse one exact prior audit without replaying project semantics.

    The immutable prior receipt remains the evidence owner.  This function is
    only a read-only equivalence witness: exact project bytes, exact terminal
    round inventory, and readable historical runtime bindings.
    """

    _existing_directory(runtime_root, label="Chalxius candidate root")
    _validated_project_validation_timeout(timeout_seconds)
    trusted_runtime_archive_root(archive_root)
    raw_projects = list(project_roots)
    anchors = list(prior_audit_projects or [])
    if len(anchors) != len(raw_projects):
        raise ValueError("bounded validation requires one exact prior-audit project witness")
    projects: list[dict[str, Any]] = []
    bindings = _normalized_receipt_bindings(
        list(prior_audit_runtime_bindings or [])
    )
    for raw_project, anchor in zip(raw_projects, anchors, strict=True):
        project = _existing_directory(raw_project, label="Chalxius protected project")
        if not isinstance(anchor, dict) or set(anchor) != {
            "project_root",
            "project_state",
            "round_states",
            "audit_evidence_mode",
            "audit_current_ok",
        }:
            raise ValueError("bounded prior-audit project witness fields are not exact")
        if anchor.get("project_root") != str(project):
            raise ValueError("bounded prior-audit project root drifted")
        anchored_state = _validate_project_state_payload(
            anchor.get("project_state"),
            project_root=project,
        )
        before = (
            project_snapshots.get(str(project))
            if project_snapshots is not None
            else _project_state_snapshot(project)
        )
        if before != anchored_state:
            raise ValueError("protected project differs from the exact prior deep audit")
        round_states = anchor.get("round_states")
        if (
            not isinstance(round_states, dict)
            or list(round_states) != _protected_round_ids(project)
            or any(
                state not in {"aborted", "completed"}
                for state in round_states.values()
            )
            or anchor.get("audit_current_ok") is not True
        ):
            raise ValueError("bounded prior-audit terminal witness drifted")
        projects.append(
            {
                "project_root": str(project),
                "round_states": dict(round_states),
                "project_state": before,
                "audit_evidence_mode": "exact_prior_deep_audit_snapshot_reuse",
                "audit_current_ok": True,
            }
        )
    return {
        "projects": projects,
        "runtime_bindings": bindings,
        "candidate_subprocess_count": 0,
    }


def _validate_release_matrix_evidence(
    entries: Any,
    *,
    candidate_manifest_sha256: str,
    candidate_skill_version: str,
) -> list[dict[str, str]]:
    if not isinstance(entries, list) or not entries:
        raise ValueError("cutover project request requires release-validation evidence")
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in entries:
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            raise ValueError("release-validation evidence fields are not exact")
        path, payload, actual = _approved_json_file(
            item["path"],
            item["sha256"],
            label="Chalxius release-validation receipt",
        )
        if str(path) in seen:
            raise ValueError("release-validation evidence path is duplicated")
        seen.add(str(path))
        lanes = payload.get("lanes")
        revision = payload.get("contract_revision")
        version_parts = candidate_skill_version.split(".")
        try:
            current_architecture_gate_required = tuple(
                int(part) for part in version_parts[:3]
            ) >= (0, 6, 5)
        except ValueError as error:
            raise ValueError("candidate skill version is not numeric semver") from error
        if revision in {
            "chalxius-release-validation-matrix-6",
            "chalxius-release-validation-matrix-7",
        }:
            expected_lanes = set()
        elif revision == "chalxius-release-validation-matrix-4":
            expected_lanes = {
                "architecture_reconnaissance",
                "mutant_registry_preflight",
                "behavioral_feature_gate",
                "self_test",
                "full_suite",
                "aggressive_bug_audit",
            }
        elif revision == "chalxius-release-validation-matrix-3":
            expected_lanes = {
                "architecture_reconnaissance",
                "behavioral_feature_gate",
                "self_test",
                "full_suite",
                "aggressive_bug_audit",
            }
        elif revision == "chalxius-release-validation-matrix-2":
            expected_lanes = {
                "architecture_reconnaissance",
                "self_test",
                "full_suite",
                "aggressive_bug_audit",
            }
        else:
            expected_lanes = {"self_test", "full_suite", "aggressive_bug_audit"}
        revision_valid = revision in {
            "chalxius-release-validation-matrix-1",
            "chalxius-release-validation-matrix-2",
            "chalxius-release-validation-matrix-3",
            "chalxius-release-validation-matrix-4",
            "chalxius-release-validation-matrix-6",
            "chalxius-release-validation-matrix-7",
        }
        if current_architecture_gate_required:
            required_revision = (
                "chalxius-release-validation-matrix-7"
                if tuple(int(part) for part in version_parts[:3]) >= (0, 9, 0)
                else "chalxius-release-validation-matrix-6"
                if tuple(int(part) for part in version_parts[:3]) >= (0, 8, 0)
                else "chalxius-release-validation-matrix-4"
            )
            revision_valid = revision == required_revision
        lanes_is_list = isinstance(lanes, list)
        validation_profile: str | None = None
        if revision in {
            "chalxius-release-validation-matrix-6",
            "chalxius-release-validation-matrix-7",
        }:
            if not lanes_is_list:
                architecture_valid = False
            else:
                lane_phases = {
                    entry.get("lane"): entry.get("phase")
                    for entry in lanes
                    if isinstance(entry, dict)
                }
                lane_profiles = {
                    entry.get("lane"): entry.get("mutation_profile")
                    for entry in lanes
                    if isinstance(entry, dict)
                }
                routine_phases = {
                    "self_test": 1,
                    "changed_surface_tests": 1,
                    "aggressive_bug_audit": 2,
                }
                routine_profiles = {
                    "self_test": None,
                    "changed_surface_tests": None,
                    "aggressive_bug_audit": "semantic",
                }
                forensic_phases = {
                    "architecture_reconnaissance": 1,
                    "mutant_registry_preflight": 1,
                    "behavioral_feature_gate": 2,
                    "self_test": 3,
                    "full_suite": 3,
                    "aggressive_bug_audit": 4,
                }
                forensic_profiles = {
                    "architecture_reconnaissance": None,
                    "mutant_registry_preflight": "full",
                    "behavioral_feature_gate": None,
                    "self_test": None,
                    "full_suite": None,
                    "aggressive_bug_audit": "full",
                }
                if (
                    lane_phases == routine_phases
                    and lane_profiles == routine_profiles
                    and len(lanes) == len(routine_phases)
                ):
                    expected_lanes = set(routine_phases)
                    validation_profile = "routine"
                    architecture_valid = True
                elif (
                    lane_phases == forensic_phases
                    and lane_profiles == forensic_profiles
                    and len(lanes) == len(forensic_phases)
                ):
                    expected_lanes = set(forensic_phases)
                    validation_profile = "forensic"
                    architecture_valid = True
                else:
                    architecture_valid = False
        elif revision == "chalxius-release-validation-matrix-4":
            architecture_valid = (
                payload.get("architecture_gate_before_baseline") is True
                and payload.get(
                    "behavioral_gate_after_architecture_before_baseline"
                )
                is True
                and payload.get("mutant_registry_preflight_before_baseline")
                is True
                and payload.get("prior_phase_failure_short_circuit") is True
                and payload.get("skipped_lanes") == []
                and payload.get("phase_order") == [1, 2, 3, 4]
                and {
                    entry.get("lane"): entry.get("phase")
                    for entry in lanes
                    if isinstance(entry, dict)
                }
                == {
                    "architecture_reconnaissance": 1,
                    "mutant_registry_preflight": 1,
                    "behavioral_feature_gate": 2,
                    "self_test": 3,
                    "full_suite": 3,
                    "aggressive_bug_audit": 4,
                }
            )
        elif revision == "chalxius-release-validation-matrix-3":
            architecture_valid = (
                payload.get("architecture_gate_before_baseline") is True
                and payload.get(
                    "behavioral_gate_after_architecture_before_baseline"
                )
                is True
                and payload.get("prior_phase_failure_short_circuit") is True
                and payload.get("skipped_lanes") == []
                and payload.get("phase_order") == [1, 2, 3, 4]
                and {
                    entry.get("lane"): entry.get("phase")
                    for entry in lanes
                    if isinstance(entry, dict)
                }
                == {
                    "architecture_reconnaissance": 1,
                    "behavioral_feature_gate": 2,
                    "self_test": 3,
                    "full_suite": 3,
                    "aggressive_bug_audit": 4,
                }
            )
        elif revision == "chalxius-release-validation-matrix-2":
            architecture_valid = (
                payload.get("architecture_gate_before_baseline") is True
                and payload.get("prior_phase_failure_short_circuit") is True
                and payload.get("skipped_lanes") == []
                and payload.get("phase_order") == [1, 2, 3]
                and {
                    entry.get("lane"): entry.get("phase")
                    for entry in lanes
                    if isinstance(entry, dict)
                }
                == {
                    "architecture_reconnaissance": 1,
                    "self_test": 2,
                    "full_suite": 2,
                    "aggressive_bug_audit": 3,
                }
            )
        else:
            architecture_valid = True
        if revision == "chalxius-release-validation-matrix-7":
            performance = payload.get("performance_summary")
            durations = [
                (entry.get("lane"), entry.get("duration_seconds"))
                for entry in lanes
                if isinstance(entry, dict)
            ] if lanes_is_list else []
            duration_values_valid = bool(durations) and all(
                isinstance(name, str)
                and isinstance(duration, (int, float))
                and not isinstance(duration, bool)
                and duration >= 0
                for name, duration in durations
            )
            slowest = (
                max(durations, key=lambda item: (item[1], item[0]))
                if duration_values_valid
                else None
            )
            expected_subsumption = (
                ["routine"] if validation_profile == "forensic" else []
            )
            repository_metadata = payload.get("repository_release_metadata")
            repository_metadata_valid = (
                repository_metadata is None
                or (
                    isinstance(repository_metadata, dict)
                    and repository_metadata.get("ok") is True
                    and repository_metadata.get("manifest_sha256")
                    == candidate_manifest_sha256
                )
            )
            receipt_shape_valid = (
                payload.get("source_unchanged") is True
                and payload.get("validation_profile") == validation_profile
                and payload.get("same_manifest_subsumes_profiles")
                == expected_subsumption
                and isinstance(performance, dict)
                and isinstance(performance.get("elapsed_seconds"), (int, float))
                and not isinstance(performance.get("elapsed_seconds"), bool)
                and performance.get("elapsed_seconds") >= 0
                and duration_values_valid
                and performance.get("recorded_lane_seconds")
                == round(sum(item[1] for item in durations), 3)
                and performance.get("slowest_lane")
                == {
                    "lane": slowest[0],
                    "duration_seconds": round(slowest[1], 3),
                }
                and repository_metadata_valid
            )
        elif revision == "chalxius-release-validation-matrix-6":
            receipt_shape_valid = payload.get("source_unchanged") is True
        else:
            receipt_shape_valid = (
                payload.get("complete_lane_set") is True
                and payload.get("one_manifest_identity") is True
            )
        if (
            not revision_valid
            or payload.get("manifest_sha256") != candidate_manifest_sha256
            or payload.get("ok") is not True
            or not receipt_shape_valid
            or not lanes_is_list
            or {entry.get("lane") for entry in lanes} != expected_lanes
            or not architecture_valid
            or any(
                not isinstance(entry, dict)
                or entry.get("ok") is not True
                or entry.get("lane_unchanged") is not True
                or entry.get("manifest_sha256") != candidate_manifest_sha256
                for entry in lanes
            )
        ):
            raise ValueError("release-validation evidence is not one complete current matrix")
        normalized.append({"path": str(path), "sha256": actual})
    return normalized


def _receipt_project_lineage_projection(
    receipt: dict[str, Any],
) -> list[dict[str, Any]]:
    projects = receipt.get("projects")
    if not isinstance(projects, list):
        raise ValueError("exact prior receipt has no project lineage")
    return [
        {
            "project_root": item["project_root"],
            "project_state": item["project_state"],
            "round_states": item["round_states"],
        }
        for item in projects
    ]


def _validate_exact_prior_receipt_ancestry(
    *,
    receipt_path: Path,
    receipt_sha256: str,
    receipt: dict[str, Any],
) -> None:
    """Follow one immutable v2 reuse chain to its deep-audit genesis."""

    current_path = _canonical_path(
        receipt_path,
        label="exact prior project-audit receipt path",
        allow_missing=False,
    )
    current_sha256 = _exact_sha256(
        receipt_sha256,
        label="exact prior project-audit receipt SHA-256",
    )
    current_receipt = receipt
    seen_paths: set[str] = set()
    seen_sha256: set[str] = set()

    _validate_cutover_project_validation_receipt_payload(
        current_receipt,
        allow_legacy=False,
    )
    for depth in range(1, MAX_PRIOR_RECEIPT_ANCESTRY_DEPTH + 1):
        current_path_text = str(current_path)
        if current_path_text in seen_paths or current_sha256 in seen_sha256:
            raise ValueError("exact prior receipt ancestry repeats one path or SHA-256")
        seen_paths.add(current_path_text)
        seen_sha256.add(current_sha256)

        validation_mode = current_receipt.get("validation_mode")
        if validation_mode == "single_deep_audit":
            return
        if validation_mode != "exact_prior_receipt_reuse":
            raise ValueError("exact prior receipt ancestry lacks a deep-audit genesis")
        if depth >= MAX_PRIOR_RECEIPT_ANCESTRY_DEPTH:
            raise ValueError("exact prior receipt ancestry exceeds the depth bound")

        predecessor = current_receipt.get("prior_audit_anchor")
        if (
            not isinstance(predecessor, dict)
            or predecessor.get("anchor_kind")
            != "exact_project_validation_receipt_v2"
            or predecessor.get("contract_revision")
            != CUTOVER_PROJECT_RECEIPT_REVISION
        ):
            raise ValueError("exact prior receipt reuse points to a legacy predecessor")
        predecessor_path_text = _canonical_path_text(
            predecessor.get("path"),
            label="exact prior receipt predecessor path",
        )
        predecessor_sha256 = _exact_sha256(
            predecessor.get("sha256"),
            label="exact prior receipt predecessor SHA-256",
        )
        if (
            predecessor_path_text in seen_paths
            or predecessor_sha256 in seen_sha256
        ):
            raise ValueError("exact prior receipt ancestry repeats one path or SHA-256")

        predecessor_path, predecessor_receipt, actual_sha256 = _approved_json_file(
            predecessor_path_text,
            predecessor_sha256,
            label=f"exact prior receipt ancestor at depth {depth + 1}",
        )
        if (
            str(predecessor_path) != predecessor_path_text
            or actual_sha256 != predecessor_sha256
        ):
            raise ValueError("exact prior receipt ancestor identity drifted")
        _validate_cutover_project_validation_receipt_payload(
            predecessor_receipt,
            allow_legacy=False,
        )
        if _receipt_project_lineage_projection(
            current_receipt
        ) != _receipt_project_lineage_projection(predecessor_receipt):
            raise ValueError("exact prior receipt project lineage drifted")

        current_path = predecessor_path
        current_sha256 = actual_sha256
        current_receipt = predecessor_receipt

    raise ValueError("exact prior receipt ancestry exceeds the depth bound")


def _validate_prior_audit_anchor(
    value: Any,
    *,
    prior_runtime_binding: dict[str, Any],
    project_roots: list[Path],
    require_exact_snapshot: bool,
) -> dict[str, Any]:
    normalized_prior_runtime = validate_runtime_binding(prior_runtime_binding)
    if not isinstance(value, dict) or set(value) != {"path", "sha256"}:
        raise ValueError("prior project-audit anchor fields are not exact")
    path, payload, actual = _approved_json_file(
        value["path"],
        value["sha256"],
        label="prior project-audit anchor",
    )

    if payload.get("contract_revision") == CUTOVER_PROJECT_RECEIPT_REVISION:
        _validate_cutover_project_validation_receipt_payload(
            payload,
            allow_legacy=False,
        )
        if (
            payload.get("candidate_runtime_content_sha256")
            != normalized_prior_runtime.get("runtime_content_sha256")
            or payload.get("candidate_manifest_sha256")
            != normalized_prior_runtime.get("manifest_file_sha256")
            or payload.get("anchor_contract_revision")
            != PRIOR_AUDIT_ANCHOR_REVISION
            or payload.get("premise_eligible") is not False
        ):
            raise ValueError("exact prior project-audit anchor identity drifted")
        _validate_exact_prior_receipt_ancestry(
            receipt_path=path,
            receipt_sha256=actual,
            receipt=payload,
        )
        raw_projects = payload.get("projects")
        if (
            not isinstance(raw_projects, list)
            or [
                item.get("project_root") if isinstance(item, dict) else None
                for item in raw_projects
            ]
            != [str(item) for item in project_roots]
        ):
            raise ValueError("exact prior project-audit project inventory drifted")
        exact_projects: list[dict[str, Any]] = []
        for raw, project in zip(raw_projects, project_roots, strict=True):
            if not isinstance(raw, dict) or set(raw) != {
                "project_root",
                "project_state",
                "round_states",
                "audit_evidence_mode",
                "audit_current_ok",
            }:
                raise ValueError("exact prior project-audit project fields are not exact")
            project_state = _validate_project_state_payload(
                raw.get("project_state"),
                project_root=project,
            )
            round_states = raw.get("round_states")
            actual_round_ids = _protected_round_ids(project)
            if (
                raw.get("audit_current_ok") is not True
                or raw.get("audit_evidence_mode")
                not in {
                    "single_prevalidated_deep_audit",
                    "exact_prior_deep_audit_snapshot_reuse",
                }
                or not isinstance(round_states, dict)
                or list(round_states) != actual_round_ids
                or any(
                    state not in {"aborted", "completed"}
                    for state in round_states.values()
                )
            ):
                raise ValueError("exact prior project-audit terminal witness is invalid")
            exact_projects.append(
                {
                    **raw,
                    "project_state": project_state,
                    "round_states": dict(round_states),
                }
            )
        exact_runtime_bindings = _normalized_receipt_bindings(
            payload.get("runtime_bindings")
        )
        nested_anchor = payload.get("prior_audit_anchor")
        if not isinstance(nested_anchor, dict):
            raise ValueError("exact prior project-audit source anchor is invalid")
        captured_at = nested_anchor.get("captured_at")
        captured_at_ns = _parse_utc_timestamp_ns(captured_at)
        return {
            "path": str(path),
            "sha256": actual,
            "captured_at": captured_at,
            "captured_at_ns": captured_at_ns,
            "anchor_kind": "exact_project_validation_receipt_v2",
            "contract_revision": CUTOVER_PROJECT_RECEIPT_REVISION,
            "exact_projects": exact_projects,
            "exact_runtime_bindings": exact_runtime_bindings,
        }

    captured_at = payload.get("captured_at")
    captured_at_ns = _parse_utc_timestamp_ns(captured_at)
    if captured_at_ns > time.time_ns() + 5_000_000_000:
        raise ValueError("prior project-audit anchor timestamp is in the future")
    if (
        payload.get("installed_runtime_identity")
        != normalized_prior_runtime["runtime_identity_sha256"]
    ):
        raise ValueError("prior project-audit anchor runtime identity drifted")
    cutover = payload.get("cutover")
    if not isinstance(cutover, dict):
        raise ValueError("prior project-audit anchor has no cutover evidence")
    if (
        cutover.get("preflight_audit_current_ok") is not True
        or cutover.get("postflight_audit_current_ok") is not True
    ):
        raise ValueError("prior project-audit anchor is not current_ok")
    protected = cutover.get("protected_projects")
    if protected is None:
        single = cutover.get("protected_project")
        protected = [single] if isinstance(single, str) else None
    if protected != [str(item) for item in project_roots]:
        raise ValueError("prior project-audit anchor project inventory drifted")
    if require_exact_snapshot:
        raise ValueError(
            "legacy prior-audit anchor cannot authorize non-impacting reuse; "
            "an exact v2 project-validation receipt is required"
        )
    return {
        "path": str(path),
        "sha256": actual,
        "captured_at": captured_at,
        "captured_at_ns": captured_at_ns,
        "anchor_kind": "legacy_current_ok_report",
        "contract_revision": "legacy_current_ok_report",
        "exact_projects": None,
        "exact_runtime_bindings": None,
    }


def _prior_audit_anchor_projection(anchor: dict[str, Any]) -> dict[str, Any]:
    return {
        key: anchor[key]
        for key in (
            "path",
            "sha256",
            "captured_at",
            "anchor_kind",
            "contract_revision",
        )
    }


def validate_or_reuse_project_validation_anchor(
    anchor_path: Path | str,
    expected_anchor_sha256: str,
    *,
    runtime_root: Path | str,
    project_roots: Iterable[Path | str],
    archive_root: Path | str,
    prior_runtime_binding: dict[str, Any],
    deep_audit_required: bool,
    deep_project_validator: Callable[..., dict[str, Any]] = validate_protected_projects,
    timeout_seconds: int = PROJECT_VALIDATION_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Run one deep audit or reuse one exact, immutable v2 receipt.

    This is a deployment-compatibility witness only.  It never creates project
    state and it is never premise-eligible.
    """

    runtime = _existing_directory(runtime_root, label="Chalxius candidate root")
    projects = [
        _existing_directory(item, label="Chalxius protected project")
        for item in project_roots
    ]
    if not projects or len(projects) != len({str(item) for item in projects}):
        raise ValueError("protected-project validation inventory is invalid")
    archive = trusted_runtime_archive_root(
        _canonical_path(
            archive_root,
            label="Chalxius cutover archive root",
            allow_missing=True,
        )
    )
    timeout_seconds = _validated_project_validation_timeout(timeout_seconds)
    if not isinstance(deep_audit_required, bool):
        raise ValueError("deep_audit_required must be one exact boolean")
    anchor = _validate_prior_audit_anchor(
        {"path": str(anchor_path), "sha256": expected_anchor_sha256},
        prior_runtime_binding=prior_runtime_binding,
        project_roots=projects,
        require_exact_snapshot=not deep_audit_required,
    )
    snapshots_before = {
        str(project): _project_state_snapshot(project) for project in projects
    }

    if deep_audit_required:
        validation = deep_project_validator(
            runtime,
            projects,
            archive_root=archive,
            timeout_seconds=timeout_seconds,
        )
        validation_mode = "single_deep_audit"
    else:
        exact_projects = anchor.get("exact_projects")
        exact_bindings = anchor.get("exact_runtime_bindings")
        if not isinstance(exact_projects, list) or not isinstance(
            exact_bindings, list
        ):
            raise ValueError("non-impacting reuse requires an exact v2 receipt")
        anchored_snapshots = {
            item["project_root"]: item["project_state"] for item in exact_projects
        }
        if snapshots_before != anchored_snapshots:
            raise ValueError("exact v2 prior-audit project state drifted")
        validation = validate_protected_projects_bounded(
            runtime,
            projects,
            archive_root=archive,
            prior_audit_projects=exact_projects,
            prior_audit_runtime_bindings=exact_bindings,
            project_snapshots=snapshots_before,
            timeout_seconds=timeout_seconds,
        )
        validation_mode = "exact_v2_project_validation_receipt_reuse"

    if not isinstance(validation, dict) or set(validation) != {
        "projects",
        "runtime_bindings",
        "candidate_subprocess_count",
    }:
        raise ValueError("project validator returned fields that are not exact")
    candidate_subprocess_count = validation.get("candidate_subprocess_count")
    expected_subprocess_count = len(projects) if deep_audit_required else 0
    if (
        type(candidate_subprocess_count) is not int
        or candidate_subprocess_count != expected_subprocess_count
    ):
        raise ValueError("project validator subprocess count is not exact")
    raw_validation_projects = validation.get("projects")
    if (
        not isinstance(raw_validation_projects, list)
        or [
            item.get("project_root") if isinstance(item, dict) else None
            for item in raw_validation_projects
        ]
        != [str(item) for item in projects]
    ):
        raise ValueError("project validator returned an incomplete project inventory")
    for raw, project in zip(raw_validation_projects, projects, strict=True):
        expected_fields = (
            {"project_root", "round_states", "audit_current_ok"}
            if deep_audit_required
            else {
                "project_root",
                "project_state",
                "round_states",
                "audit_evidence_mode",
                "audit_current_ok",
            }
        )
        round_states = raw.get("round_states")
        if (
            not isinstance(raw, dict)
            or set(raw) != expected_fields
            or not isinstance(round_states, dict)
            or list(round_states) != _protected_round_ids(project)
            or any(
                state not in {"aborted", "completed"}
                for state in round_states.values()
            )
            or (
                deep_audit_required
                and raw.get("audit_current_ok") is not True
            )
        ):
            raise ValueError("project validator returned a nonterminal project witness")
    if not deep_audit_required:
        anchored_states = {
            item["project_root"]: item["round_states"]
            for item in anchor["exact_projects"]
        }
        for raw in raw_validation_projects:
            project_root = raw["project_root"]
            if (
                raw["round_states"] != anchored_states[project_root]
                or raw["project_state"] != snapshots_before[project_root]
                or raw["audit_evidence_mode"]
                != "exact_prior_deep_audit_snapshot_reuse"
                or raw["audit_current_ok"] is not True
            ):
                raise ValueError("bounded validator changed the anchored project witness")
    bindings = _normalized_receipt_bindings(validation.get("runtime_bindings"))
    if not deep_audit_required and bindings != anchor["exact_runtime_bindings"]:
        raise ValueError("bounded validator changed the anchored runtime bindings")
    snapshots_after = {
        str(project): _project_state_snapshot(project) for project in projects
    }
    if snapshots_before != snapshots_after:
        raise ValueError("protected project changed during project validation")
    return {
        "projects": raw_validation_projects,
        "runtime_bindings": bindings,
        "validation_mode": validation_mode,
        "candidate_subprocess_count": candidate_subprocess_count,
        "project_effect": "validation_only",
        "truth_effect": "none",
        "premise_eligible": False,
        "_project_snapshots": snapshots_after,
    }


def _validate_project_request(
    request: Any,
    *,
    candidate: Path,
    installed: Path,
    archive_root: Path,
    candidate_binding: dict[str, Any],
    installed_binding: dict[str, Any],
    candidate_manifest_sha256: str,
    allow_legacy_bounded_anchor: bool = False,
) -> dict[str, Any]:
    expected = {
        "schema_version",
        "contract_revision",
        "candidate_manifest_sha256",
        "prior_runtime_identity",
        "project_roots",
        "prior_audit_anchor",
        "release_validation_evidence",
        "change_classification",
        "truth_effect",
    }
    if not isinstance(request, dict) or set(request) != expected:
        raise ValueError("cutover project-validation request fields are not exact")
    if (
        type(request.get("schema_version")) is not int
        or request.get("schema_version") != 1
        or request.get("contract_revision") != CUTOVER_PROJECT_REQUEST_REVISION
        or request.get("truth_effect") != "none"
        or request.get("candidate_manifest_sha256")
        != candidate_manifest_sha256
        or request.get("prior_runtime_identity")
        != installed_binding["runtime_identity_sha256"]
    ):
        raise ValueError("cutover project-validation request identity drifted")
    raw_projects = request.get("project_roots")
    if (
        not isinstance(raw_projects, list)
        or not raw_projects
        or len(raw_projects) != len(set(raw_projects))
    ):
        raise ValueError("cutover project-validation project roots are invalid")
    projects = [
        _existing_directory(item, label="Chalxius protected project")
        for item in raw_projects
    ]
    classification = request.get("change_classification")
    if not isinstance(classification, dict) or set(classification) != {
        "classification_revision",
        "deep_audit_required",
        "changed_paths",
        "rationale",
    }:
        raise ValueError("cutover change classification fields are not exact")
    if (
        classification.get("classification_revision")
        != "chalxius-cutover-change-classification-1"
        or not isinstance(classification.get("deep_audit_required"), bool)
        or not isinstance(classification.get("rationale"), str)
        or not classification["rationale"].strip()
    ):
        raise ValueError("cutover change classification is invalid")
    changed_paths = _changed_runtime_paths(candidate, installed)
    if classification.get("changed_paths") != changed_paths:
        raise ValueError("cutover change classification does not cover the exact runtime diff")
    anchor = _validate_prior_audit_anchor(
        request.get("prior_audit_anchor"),
        prior_runtime_binding=installed_binding,
        project_roots=projects,
        require_exact_snapshot=(
            not classification["deep_audit_required"]
            and not allow_legacy_bounded_anchor
        ),
    )
    evidence = _validate_release_matrix_evidence(
        request.get("release_validation_evidence"),
        candidate_manifest_sha256=candidate_manifest_sha256,
        candidate_skill_version=candidate_binding["skill_version"],
    )
    return {
        "candidate_binding": candidate_binding,
        "installed_binding": installed_binding,
        "candidate_manifest_sha256": candidate_manifest_sha256,
        "projects": projects,
        "change_classification": dict(classification),
        "prior_audit_anchor": anchor,
        "release_validation_evidence": evidence,
        "archive_root": archive_root,
    }


def build_cutover_project_validation_receipt(
    *,
    candidate_root: Path | str,
    installed_root: Path | str,
    archive_root: Path | str,
    request_path: Path | str,
    expected_request_sha256: str,
    output_path: Path | str | None = None,
    deep_project_validator: Callable[..., dict[str, Any]] = validate_protected_projects,
    validation_timeout_seconds: int = PROJECT_VALIDATION_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    validation_timeout_seconds = _validated_project_validation_timeout(
        validation_timeout_seconds
    )
    candidate = _existing_directory(candidate_root, label="Chalxius candidate root")
    installed = _existing_directory(installed_root, label="Chalxius installed root")
    archive = trusted_runtime_archive_root(
        _canonical_path(
            archive_root,
            label="Chalxius cutover archive root",
            allow_missing=True,
        )
    )
    candidate_binding, _ = _validate_runtime_tree(
        candidate, archive_root=archive, exact_file_set=True
    )
    installed_binding, _ = _validate_runtime_tree(
        installed, archive_root=archive, exact_file_set=False
    )
    candidate_manifest_sha256 = sha256_bytes(
        (candidate / "MANIFEST.sha256").read_bytes()
    )
    request_file, request, request_sha256 = _approved_json_file(
        request_path,
        expected_request_sha256,
        label="cutover project-validation request",
    )
    context = _validate_project_request(
        request,
        candidate=candidate,
        installed=installed,
        archive_root=archive,
        candidate_binding=candidate_binding,
        installed_binding=installed_binding,
        candidate_manifest_sha256=candidate_manifest_sha256,
    )
    validation = validate_or_reuse_project_validation_anchor(
        context["prior_audit_anchor"]["path"],
        context["prior_audit_anchor"]["sha256"],
        runtime_root=candidate,
        project_roots=context["projects"],
        archive_root=archive,
        prior_runtime_binding=installed_binding,
        deep_audit_required=context["change_classification"][
            "deep_audit_required"
        ],
        deep_project_validator=deep_project_validator,
        timeout_seconds=validation_timeout_seconds,
    )
    if validation["validation_mode"] == "single_deep_audit":
        audit_evidence_mode = "single_prevalidated_deep_audit"
        validation_mode = "single_deep_audit"
    else:
        audit_evidence_mode = "exact_prior_deep_audit_snapshot_reuse"
        validation_mode = "exact_prior_receipt_reuse"
    candidate_subprocess_count = validation["candidate_subprocess_count"]
    snapshots_after = {
        str(project): _project_state_snapshot(project)
        for project in context["projects"]
    }
    if snapshots_after != validation["_project_snapshots"]:
        raise ValueError("protected project changed while validation receipt was built")
    project_results: list[dict[str, Any]] = []
    validation_projects = {
        item["project_root"]: item for item in validation["projects"]
    }
    for project in context["projects"]:
        root_text = str(project)
        item = validation_projects.get(root_text)
        if not isinstance(item, dict):
            raise ValueError("project validator omitted one protected project")
        round_states = item.get("round_states")
        if not isinstance(round_states, dict) or any(
            state not in {"aborted", "completed"}
            for state in round_states.values()
        ):
            raise ValueError("project validator returned a nonterminal round")
        project_results.append(
            {
                "project_root": root_text,
                "project_state": snapshots_after[root_text],
                "round_states": round_states,
                "audit_evidence_mode": audit_evidence_mode,
                "audit_current_ok": (
                    item.get("audit_current_ok") is True
                    if context["change_classification"]["deep_audit_required"]
                    else True
                ),
            }
        )
    bindings = sorted(
        validation["runtime_bindings"],
        key=lambda item: item["runtime_identity_sha256"],
    )
    receipt = {
        "schema_version": 1,
        "contract_revision": CUTOVER_PROJECT_RECEIPT_REVISION,
        "request_path": str(request_file),
        "request_sha256": request_sha256,
        "candidate_root": str(candidate),
        "installed_root": str(installed),
        "archive_root": str(archive),
        "candidate_manifest_sha256": candidate_manifest_sha256,
        "candidate_runtime_identity": candidate_binding[
            "runtime_identity_sha256"
        ],
        "candidate_runtime_content_sha256": candidate_binding[
            "runtime_content_sha256"
        ],
        "prior_runtime_identity": installed_binding[
            "runtime_identity_sha256"
        ],
        "changed_runtime_paths": context["change_classification"][
            "changed_paths"
        ],
        "deep_audit_required": context["change_classification"][
            "deep_audit_required"
        ],
        "change_classification_rationale": context["change_classification"][
            "rationale"
        ],
        "prior_audit_anchor": _prior_audit_anchor_projection(
            context["prior_audit_anchor"]
        ),
        "release_validation_evidence": context[
            "release_validation_evidence"
        ],
        "projects": project_results,
        "runtime_bindings": bindings,
        "anchor_contract_revision": PRIOR_AUDIT_ANCHOR_REVISION,
        "validation_mode": validation_mode,
        "candidate_subprocess_count": candidate_subprocess_count,
        "project_effect": "validation_only",
        "truth_effect": "none",
        "premise_eligible": False,
    }
    if output_path is not None:
        destination = _canonical_path(
            output_path,
            label="cutover project-validation receipt output",
            allow_missing=True,
        )
        if destination.exists() or destination.is_symlink():
            existing = _read_json_file(
                destination,
                label="cutover project-validation receipt output",
            )
            if existing != receipt:
                raise ValueError("cutover project-validation receipt output already exists")
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(f".{destination.name}.tmp-{os.getpid()}")
            try:
                with temporary.open("x", encoding="utf-8") as handle:
                    json.dump(receipt, handle, ensure_ascii=False, indent=2, sort_keys=True)
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.rename(temporary, destination)
                _fsync_directory(destination.parent)
            finally:
                if temporary.exists():
                    temporary.unlink()
    return receipt


def _validate_v2_project_validation_receipt_semantics(
    receipt: dict[str, Any],
) -> None:
    for field, label in (
        ("request_path", "cutover project-validation request path"),
        ("candidate_root", "cutover project-validation candidate root"),
        ("installed_root", "cutover project-validation installed root"),
        ("archive_root", "cutover project-validation archive root"),
    ):
        _canonical_path_text(receipt.get(field), label=label)
    for field in (
        "request_sha256",
        "candidate_manifest_sha256",
        "candidate_runtime_identity",
        "candidate_runtime_content_sha256",
        "prior_runtime_identity",
    ):
        _exact_sha256(
            receipt.get(field),
            label=f"cutover project-validation {field}",
        )

    changed_paths = receipt.get("changed_runtime_paths")
    if (
        not isinstance(changed_paths, list)
        or any(
            not isinstance(item, str)
            or not item
            or Path(item).is_absolute()
            or ".." in Path(item).parts
            or Path(item).as_posix() != item
            for item in changed_paths
        )
        or changed_paths != sorted(set(changed_paths))
    ):
        raise ValueError("cutover project-validation changed paths are invalid")

    prior_anchor = receipt.get("prior_audit_anchor")
    if not isinstance(prior_anchor, dict) or set(prior_anchor) != {
        "path",
        "sha256",
        "captured_at",
        "anchor_kind",
        "contract_revision",
    }:
        raise ValueError("cutover project-validation v2 prior anchor is invalid")
    _canonical_path_text(
        prior_anchor.get("path"),
        label="cutover project-validation prior anchor path",
    )
    _exact_sha256(
        prior_anchor.get("sha256"),
        label="cutover project-validation prior anchor SHA-256",
    )
    allowed_anchor_kinds = {
        ("legacy_current_ok_report", "legacy_current_ok_report"),
        (
            "exact_project_validation_receipt_v2",
            CUTOVER_PROJECT_RECEIPT_REVISION,
        ),
    }
    if (
        prior_anchor.get("anchor_kind"),
        prior_anchor.get("contract_revision"),
    ) not in allowed_anchor_kinds:
        raise ValueError("cutover project-validation v2 prior anchor lineage is invalid")
    captured_at_ns = _parse_utc_timestamp_ns(prior_anchor.get("captured_at"))
    if captured_at_ns > time.time_ns() + 5_000_000_000:
        raise ValueError("cutover project-validation prior anchor timestamp is in the future")

    release_evidence = receipt.get("release_validation_evidence")
    if not isinstance(release_evidence, list) or not release_evidence:
        raise ValueError("cutover project-validation release evidence is invalid")
    evidence_paths: list[str] = []
    for item in release_evidence:
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            raise ValueError("cutover project-validation release evidence is invalid")
        evidence_paths.append(
            _canonical_path_text(
                item.get("path"),
                label="cutover project-validation release evidence path",
            )
        )
        _exact_sha256(
            item.get("sha256"),
            label="cutover project-validation release evidence SHA-256",
        )
    if len(evidence_paths) != len(set(evidence_paths)):
        raise ValueError("cutover project-validation release evidence is duplicated")

    projects = receipt.get("projects")
    if not isinstance(projects, list) or not projects:
        raise ValueError("cutover project-validation v2 project inventory is invalid")
    validation_mode = receipt.get("validation_mode")
    expected_project_mode = (
        "single_prevalidated_deep_audit"
        if validation_mode == "single_deep_audit"
        else "exact_prior_deep_audit_snapshot_reuse"
    )
    project_roots: list[str] = []
    for raw in projects:
        if not isinstance(raw, dict) or set(raw) != {
            "project_root",
            "project_state",
            "round_states",
            "audit_evidence_mode",
            "audit_current_ok",
        }:
            raise ValueError("cutover project-validation project fields are not exact")
        root_text = _canonical_path_text(
            raw.get("project_root"),
            label="cutover project-validation project root",
        )
        project_roots.append(root_text)
        _validate_project_state_payload(
            raw.get("project_state"),
            project_root=Path(root_text),
        )
        round_states = raw.get("round_states")
        if (
            not isinstance(round_states, dict)
            or list(round_states) != sorted(round_states)
            or any(not isinstance(round_id, str) for round_id in round_states)
            or any(
                state not in {"aborted", "completed"}
                for state in round_states.values()
            )
            or raw.get("audit_evidence_mode") != expected_project_mode
            or raw.get("audit_current_ok") is not True
        ):
            raise ValueError("cutover project-validation project witness is invalid")
        for round_id in round_states:
            validate_round_id(round_id)
    if len(project_roots) != len(set(project_roots)):
        raise ValueError("cutover project-validation project roots are duplicated")
    _normalized_receipt_bindings(receipt.get("runtime_bindings"))

    if (
        validation_mode == "exact_prior_receipt_reuse"
        and prior_anchor.get("anchor_kind")
        != "exact_project_validation_receipt_v2"
    ):
        raise ValueError(
            "cutover project-validation reuse lacks one exact v2 predecessor"
        )


def _validate_cutover_project_validation_receipt_payload(
    receipt: Any,
    *,
    allow_legacy: bool,
) -> dict[str, Any]:
    base_expected = {
        "schema_version",
        "contract_revision",
        "request_path",
        "request_sha256",
        "candidate_root",
        "installed_root",
        "archive_root",
        "candidate_manifest_sha256",
        "candidate_runtime_identity",
        "candidate_runtime_content_sha256",
        "prior_runtime_identity",
        "changed_runtime_paths",
        "deep_audit_required",
        "change_classification_rationale",
        "prior_audit_anchor",
        "release_validation_evidence",
        "projects",
        "runtime_bindings",
        "project_effect",
        "truth_effect",
    }
    if not isinstance(receipt, dict):
        raise ValueError("cutover project-validation receipt must contain one object")
    revision = receipt.get("contract_revision")
    if revision == CUTOVER_PROJECT_RECEIPT_REVISION:
        expected = base_expected | {
            "anchor_contract_revision",
            "validation_mode",
            "candidate_subprocess_count",
            "premise_eligible",
        }
    elif allow_legacy and revision == LEGACY_CUTOVER_PROJECT_RECEIPT_REVISION:
        expected = base_expected
    else:
        raise ValueError("cutover project-validation receipt revision is unsupported")
    if set(receipt) != expected:
        raise ValueError("cutover project-validation receipt fields are not exact")
    if (
        type(receipt.get("schema_version")) is not int
        or receipt.get("schema_version") != 1
        or receipt.get("project_effect") != "validation_only"
        or receipt.get("truth_effect") != "none"
        or not isinstance(receipt.get("deep_audit_required"), bool)
        or not isinstance(receipt.get("change_classification_rationale"), str)
        or not receipt["change_classification_rationale"].strip()
    ):
        raise ValueError("cutover project-validation receipt is invalid")
    if revision == CUTOVER_PROJECT_RECEIPT_REVISION:
        projects = receipt.get("projects")
        project_count = len(projects) if isinstance(projects, list) else -1
        validation_mode = receipt.get("validation_mode")
        expected_process_count = (
            project_count if validation_mode == "single_deep_audit" else 0
        )
        if (
            receipt.get("anchor_contract_revision")
            != PRIOR_AUDIT_ANCHOR_REVISION
            or validation_mode
            not in {"single_deep_audit", "exact_prior_receipt_reuse"}
            or type(receipt.get("candidate_subprocess_count")) is not int
            or receipt.get("candidate_subprocess_count")
            != expected_process_count
            or receipt.get("premise_eligible") is not False
            or (
                validation_mode == "single_deep_audit"
                and receipt.get("deep_audit_required") is not True
            )
            or (
                validation_mode == "exact_prior_receipt_reuse"
                and receipt.get("deep_audit_required") is not False
            )
        ):
            raise ValueError("cutover project-validation v2 witness is invalid")
        _validate_v2_project_validation_receipt_semantics(receipt)
    return dict(receipt)


def _load_cutover_project_validation_receipt(
    value: Path | str,
    expected_sha256: str | None,
) -> tuple[Path, dict[str, Any], str]:
    path, receipt, actual = _approved_json_file(
        value,
        expected_sha256,
        label="cutover project-validation receipt",
    )
    receipt = _validate_cutover_project_validation_receipt_payload(
        receipt,
        allow_legacy=True,
    )
    return path, receipt, actual


def _normalized_receipt_bindings(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("cutover project-validation runtime bindings are invalid")
    bindings = [validate_runtime_binding(item) for item in value]
    identities = [item["runtime_identity_sha256"] for item in bindings]
    if identities != sorted(set(identities)):
        raise ValueError("cutover project-validation runtime bindings are not canonical")
    return bindings


def _validate_receipt_project_state(
    receipt: dict[str, Any],
    project_roots: list[Path],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw_projects = receipt.get("projects")
    if not isinstance(raw_projects, list) or len(raw_projects) != len(project_roots):
        raise ValueError("cutover project-validation project inventory drifted")
    expected_roots = [str(item) for item in project_roots]
    if [item.get("project_root") if isinstance(item, dict) else None for item in raw_projects] != expected_roots:
        raise ValueError("cutover project-validation project order drifted")
    projects: list[dict[str, Any]] = []
    actual_bindings: dict[str, dict[str, Any]] = {}
    for raw, project in zip(raw_projects, project_roots, strict=True):
        if not isinstance(raw, dict) or set(raw) != {
            "project_root",
            "project_state",
            "round_states",
            "audit_evidence_mode",
            "audit_current_ok",
        }:
            raise ValueError("cutover project-validation project fields are not exact")
        expected_mode = (
            "single_prevalidated_deep_audit"
            if receipt["deep_audit_required"]
            else (
                "exact_prior_deep_audit_snapshot_reuse"
                if receipt.get("contract_revision")
                == CUTOVER_PROJECT_RECEIPT_REVISION
                else "bounded_reuse_of_prior_deep_audit"
            )
        )
        if (
            raw.get("audit_evidence_mode") != expected_mode
            or raw.get("audit_current_ok") is not True
        ):
            raise ValueError("cutover project-validation audit evidence is invalid")
        snapshot = _project_state_snapshot(project)
        if (
            receipt.get("contract_revision")
            == LEGACY_CUTOVER_PROJECT_RECEIPT_REVISION
        ):
            comparable_snapshot = dict(snapshot)
            comparable_snapshot.pop("snapshot_revision")
        else:
            comparable_snapshot = snapshot
        if raw.get("project_state") != comparable_snapshot:
            raise ValueError("protected project changed after validation receipt")
        round_states = raw.get("round_states")
        actual_round_ids = _protected_round_ids(project)
        if (
            not isinstance(round_states, dict)
            or list(round_states) != actual_round_ids
            or any(state not in {"aborted", "completed"} for state in round_states.values())
        ):
            raise ValueError("cutover project-validation terminal round state drifted")
        for binding in _round_bindings(project):
            actual_bindings[binding["runtime_identity_sha256"]] = binding
        projects.append(
            {
                "project_root": str(project),
                "round_states": dict(round_states),
                "audit_current_ok": True,
                "audit_evidence_mode": expected_mode,
                "project_state_sha256": snapshot["state_sha256"],
            }
        )
    bindings = sorted(
        actual_bindings.values(),
        key=lambda item: item["runtime_identity_sha256"],
    )
    return projects, bindings


def _validate_cutover_project_receipt_preflight(
    *,
    receipt_path: Path | str,
    expected_receipt_sha256: str | None,
    candidate: Path,
    installed: Path,
    archive_root: Path,
    project_roots: list[Path],
    candidate_binding: dict[str, Any],
    installed_binding: dict[str, Any],
    candidate_manifest_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    path, receipt, receipt_sha256 = _load_cutover_project_validation_receipt(
        receipt_path,
        expected_receipt_sha256,
    )
    if (
        receipt.get("candidate_root") != str(candidate)
        or receipt.get("installed_root") != str(installed)
        or receipt.get("archive_root") != str(archive_root)
        or receipt.get("candidate_manifest_sha256")
        != candidate_manifest_sha256
        or receipt.get("candidate_runtime_identity")
        != candidate_binding["runtime_identity_sha256"]
        or receipt.get("candidate_runtime_content_sha256")
        != candidate_binding["runtime_content_sha256"]
        or receipt.get("prior_runtime_identity")
        != installed_binding["runtime_identity_sha256"]
        or receipt.get("changed_runtime_paths")
        != _changed_runtime_paths(candidate, installed)
    ):
        raise ValueError("cutover project-validation receipt runtime identity drifted")
    request_path, request, request_sha256 = _approved_json_file(
        receipt["request_path"],
        receipt["request_sha256"],
        label="cutover project-validation request",
    )
    context = _validate_project_request(
        request,
        candidate=candidate,
        installed=installed,
        archive_root=archive_root,
        candidate_binding=candidate_binding,
        installed_binding=installed_binding,
        candidate_manifest_sha256=candidate_manifest_sha256,
        allow_legacy_bounded_anchor=(
            receipt.get("contract_revision")
            == LEGACY_CUTOVER_PROJECT_RECEIPT_REVISION
        ),
    )
    if (
        str(request_path) != receipt["request_path"]
        or request_sha256 != receipt["request_sha256"]
        or context["projects"] != project_roots
        or receipt["deep_audit_required"]
        != context["change_classification"]["deep_audit_required"]
        or receipt["change_classification_rationale"]
        != context["change_classification"]["rationale"]
        or receipt["prior_audit_anchor"]
        != (
            _prior_audit_anchor_projection(context["prior_audit_anchor"])
            if receipt.get("contract_revision")
            == CUTOVER_PROJECT_RECEIPT_REVISION
            else {
                key: context["prior_audit_anchor"][key]
                for key in ("path", "sha256", "captured_at")
            }
        )
        or receipt["release_validation_evidence"]
        != context["release_validation_evidence"]
    ):
        raise ValueError("cutover project-validation receipt request binding drifted")
    projects, actual_bindings = _validate_receipt_project_state(
        receipt, project_roots
    )
    receipt_bindings = _normalized_receipt_bindings(receipt["runtime_bindings"])
    if receipt_bindings != actual_bindings:
        raise ValueError("cutover project-validation runtime bindings drifted")
    if (
        not receipt["deep_audit_required"]
        and receipt.get("contract_revision")
        == LEGACY_CUTOVER_PROJECT_RECEIPT_REVISION
    ):
        captured_at_ns = context["prior_audit_anchor"]["captured_at_ns"]
        if any(
            item["project_state"]["latest_mtime_ns"] > captured_at_ns
            for item in receipt["projects"]
        ):
            raise ValueError("bounded project-validation receipt is stale")
    return (
        {
            "projects": projects,
            "runtime_bindings": receipt_bindings,
            "validation_mode": "prevalidated_receipt",
            "receipt_path": str(path),
            "receipt_sha256": receipt_sha256,
        },
        receipt,
        receipt_sha256,
    )


def _validate_cutover_project_receipt_postflight(
    *,
    receipt: dict[str, Any],
    receipt_path: Path | str,
    receipt_sha256: str,
    installed: Path,
    archive_root: Path,
    project_roots: list[Path],
    installed_binding: dict[str, Any],
) -> dict[str, Any]:
    _, current_receipt, current_sha256 = _load_cutover_project_validation_receipt(
        receipt_path,
        receipt_sha256,
    )
    if current_receipt != receipt or current_sha256 != receipt_sha256:
        raise ValueError("cutover project-validation receipt changed during cutover")
    if (
        installed_binding["runtime_content_sha256"]
        != receipt["candidate_runtime_content_sha256"]
        or str(archive_root) != receipt["archive_root"]
    ):
        raise ValueError("post-cutover runtime differs from the validated candidate")
    projects, actual_bindings = _validate_receipt_project_state(
        receipt, project_roots
    )
    if _normalized_receipt_bindings(receipt["runtime_bindings"]) != actual_bindings:
        raise ValueError("post-cutover historical runtime bindings drifted")
    return {
        "projects": projects,
        "runtime_bindings": actual_bindings,
        "validation_mode": "receipt_reuse_after_exact_swap",
        "receipt_path": str(receipt_path),
        "receipt_sha256": receipt_sha256,
    }


def _freeze_single_full_project_validation(
    validation: dict[str, Any],
    project_roots: list[Path],
    snapshots_before: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    snapshots_after = {
        str(project): _project_state_snapshot(project) for project in project_roots
    }
    if snapshots_before != snapshots_after:
        raise ValueError("protected project changed during the single deep audit")
    indexed = {
        item.get("project_root"): item
        for item in validation.get("projects", [])
        if isinstance(item, dict)
    }
    projects: list[dict[str, Any]] = []
    for project in project_roots:
        root_text = str(project)
        item = indexed.get(root_text)
        if (
            not isinstance(item, dict)
            or item.get("audit_current_ok") is not True
            or not isinstance(item.get("round_states"), dict)
            or any(
                state not in {"aborted", "completed"}
                for state in item["round_states"].values()
            )
        ):
            raise ValueError("single deep project audit did not return current terminal state")
        projects.append(
            {
                "project_root": root_text,
                "project_state": snapshots_after[root_text],
                "round_states": dict(item["round_states"]),
                "audit_evidence_mode": "single_prevalidated_deep_audit",
                "audit_current_ok": True,
            }
        )
    receipt_like = {
        "deep_audit_required": True,
        "projects": projects,
        "runtime_bindings": sorted(
            validation.get("runtime_bindings", []),
            key=lambda item: item["runtime_identity_sha256"],
        ),
    }
    _, actual_bindings = _validate_receipt_project_state(
        receipt_like, project_roots
    )
    if _normalized_receipt_bindings(receipt_like["runtime_bindings"]) != actual_bindings:
        raise ValueError("single deep project audit runtime bindings drifted")
    return receipt_like


def _prepare_runtime_archive_plan(
    installed_root: Path,
    installed_binding: dict[str, Any] | None,
    project_bindings: Iterable[dict[str, Any]],
    *,
    archive_root: Path,
) -> dict[str, Any]:
    bindings_to_archive: dict[str, dict[str, Any]] = {}
    if installed_binding is not None:
        bindings_to_archive[
            installed_binding["runtime_identity_sha256"]
        ] = installed_binding
    verified_historical: list[dict[str, Any]] = []
    for raw_binding in project_bindings:
        normalized = validate_runtime_binding(raw_binding)
        if Path(normalized["skill_root"]) != installed_root:
            continue
        identity = normalized["runtime_identity_sha256"]
        if identity in bindings_to_archive:
            continue
        live_matches = False
        if installed_root.is_dir():
            try:
                validate_bound_runtime_at(
                    installed_root,
                    normalized,
                    verify_manifest_tree=True,
                )
            except ValueError:
                pass
            else:
                live_matches = True
        if live_matches:
            bindings_to_archive[identity] = normalized
            continue
        resolved = resolve_historical_runtime(
            normalized,
            archive_root=archive_root,
        )
        if resolved.get("resolution") != "content_addressed_historical_archive":
            raise ValueError(
                "historical runtime at the installed alias did not resolve through the host archive"
            )
        verified_historical.append(
            {
                "runtime_identity_sha256": identity,
                "runtime_content_sha256": normalized.get(
                    "runtime_content_sha256"
                ),
                "archive_path": resolved["runtime_root"],
                "registry_path": resolved["registry_path"],
                "registry_record_sha256": resolved[
                    "registry_record_sha256"
                ],
            }
        )
    return {
        "bindings_to_archive": list(bindings_to_archive.values()),
        "verified_historical": verified_historical,
    }


def _default_self_test(runtime_root: Path) -> None:
    script = runtime_root / "scripts" / "self_test.py"
    if script.is_symlink() or not script.is_file():
        raise ValueError("candidate runtime has no safe self-test")
    outcome = subprocess.run(
        [sys.executable, "-B", str(script)],
        cwd=runtime_root,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if outcome.returncode != 0:
        raise ValueError(
            "Chalxius runtime self-test failed: "
            + (outcome.stderr or outcome.stdout).strip()
        )


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def perform_cutover(
    *,
    candidate_root: Path | str,
    installed_root: Path | str,
    rollback_root: Path | str | None,
    archive_root: Path | str,
    project_roots: Iterable[Path | str] = (),
    confirm_no_protected_projects: bool = False,
    expected_candidate_manifest_sha256: str | None = None,
    expected_installed_runtime_identity: str | None = None,
    project_validation_receipt: Path | str | None = None,
    expected_project_validation_receipt_sha256: str | None = None,
    force_full_project_audit: bool = False,
    project_validation_timeout_seconds: int = PROJECT_VALIDATION_TIMEOUT_SECONDS,
    allow_fresh_install: bool = False,
    dry_run: bool = False,
    operation: str = "install",
    self_test_runner: Callable[[Path], None] = _default_self_test,
    project_validator: Callable[..., dict[str, Any]] = validate_protected_projects,
) -> dict[str, Any]:
    project_validation_timeout_seconds = _validated_project_validation_timeout(
        project_validation_timeout_seconds
    )
    if operation not in {"install", "rollback"}:
        raise ValueError("runtime cutover operation must be install or rollback")
    if (project_validation_receipt is None) != (
        expected_project_validation_receipt_sha256 is None
    ):
        raise ValueError(
            "cutover project-validation receipt and approved SHA-256 are inseparable"
        )
    candidate = _existing_directory(candidate_root, label="Chalxius candidate root")
    installed = _canonical_path(
        installed_root,
        label="Chalxius installed root",
        allow_missing=allow_fresh_install,
    )
    if installed.exists() and (installed.is_symlink() or not installed.is_dir()):
        raise ValueError("Chalxius installed root is unsafe")
    if not installed.exists() and not allow_fresh_install:
        raise ValueError("Chalxius installed root is missing")
    archive = trusted_runtime_archive_root(
        _canonical_path(
            archive_root,
            label="Chalxius cutover archive root",
            allow_missing=True,
        )
    )
    for protected in (candidate, installed):
        if archive == protected or archive.is_relative_to(protected):
            raise ValueError("runtime archive root must remain outside skill roots")
    normalized_projects = [
        _existing_directory(item, label="Chalxius protected project")
        for item in project_roots
    ]
    if normalized_projects and confirm_no_protected_projects:
        raise ValueError("protected projects and no-project confirmation are exclusive")
    if not normalized_projects and not confirm_no_protected_projects:
        raise ValueError(
            "cutover requires protected project roots or explicit no-project confirmation"
        )
    if project_validation_receipt is not None and not normalized_projects:
        raise ValueError(
            "cutover project-validation receipt requires protected projects"
        )
    if (
        normalized_projects
        and project_validation_receipt is None
        and not force_full_project_audit
    ):
        raise ValueError(
            "protected-project cutover requires a prevalidated receipt or explicit force_full_project_audit"
        )
    if project_validation_receipt is not None and force_full_project_audit:
        raise ValueError(
            "prevalidated project receipt and forced full audit are exclusive"
        )
    rollback = None
    if installed.exists():
        if rollback_root is None:
            raise ValueError("replacement cutover requires an explicit rollback root")
        rollback = _nonexistent_sibling(rollback_root, installed_root=installed)
    elif rollback_root is not None:
        raise ValueError("fresh install must not declare a rollback root")

    candidate_binding, candidate_validation = _validate_runtime_tree(
        candidate,
        archive_root=archive,
        exact_file_set=True,
    )
    candidate_manifest_sha = sha256_bytes(
        (candidate / "MANIFEST.sha256").read_bytes()
    )
    if expected_candidate_manifest_sha256 is None:
        raise ValueError(
            "cutover requires an approved candidate MANIFEST.sha256 hash"
        )
    if candidate_manifest_sha != expected_candidate_manifest_sha256:
        raise ValueError("candidate MANIFEST.sha256 hash differs from the approved value")
    installed_binding = None
    if installed.exists():
        installed_binding, _ = _validate_runtime_tree(
            installed,
            archive_root=archive,
            exact_file_set=False,
        )
        if (
            expected_installed_runtime_identity is not None
            and installed_binding["runtime_identity_sha256"]
            != expected_installed_runtime_identity
        ):
            raise ValueError("installed runtime identity differs from the approved value")

    self_test_runner(candidate)
    bounded_receipt: dict[str, Any] | None = None
    bounded_receipt_sha256: str | None = None
    in_memory_full_receipt: dict[str, Any] | None = None
    if project_validation_receipt is not None:
        if installed_binding is None:
            raise ValueError(
                "bounded project-validation receipt cannot authorize a fresh install"
            )
        preflight, bounded_receipt, bounded_receipt_sha256 = (
            _validate_cutover_project_receipt_preflight(
                receipt_path=project_validation_receipt,
                expected_receipt_sha256=expected_project_validation_receipt_sha256,
                candidate=candidate,
                installed=installed,
                archive_root=archive,
                project_roots=normalized_projects,
                candidate_binding=candidate_binding,
                installed_binding=installed_binding,
                candidate_manifest_sha256=candidate_manifest_sha,
            )
        )
    else:
        snapshots_before = {
            str(project): _project_state_snapshot(project)
            for project in normalized_projects
        }
        preflight = project_validator(
            candidate,
            normalized_projects,
            archive_root=archive,
            timeout_seconds=project_validation_timeout_seconds,
        )
        if normalized_projects:
            in_memory_full_receipt = _freeze_single_full_project_validation(
                preflight,
                normalized_projects,
                snapshots_before,
            )
    archive_plan = _prepare_runtime_archive_plan(
        installed,
        installed_binding,
        preflight["runtime_bindings"],
        archive_root=archive,
    )
    receipt: dict[str, Any] = {
        "schema_version": 1,
        "contract_revision": CUTOVER_CONTRACT_REVISION,
        "operation": operation,
        "dry_run": dry_run,
        "candidate_root": str(candidate),
        "candidate_manifest_sha256": candidate_manifest_sha,
        "candidate_runtime_identity": candidate_binding[
            "runtime_identity_sha256"
        ],
        "candidate_manifest_entry_count": candidate_validation[
            "manifest_entry_count"
        ],
        "installed_root": str(installed),
        "prior_runtime_identity": (
            installed_binding["runtime_identity_sha256"]
            if installed_binding is not None
            else None
        ),
        "rollback_root": str(rollback) if rollback is not None else None,
        "archive_root": str(archive),
        "preflight_projects": preflight["projects"],
        "preflight_historical_runtimes": archive_plan[
            "verified_historical"
        ],
        "project_validation_receipt": (
            {
                "path": str(project_validation_receipt),
                "sha256": bounded_receipt_sha256,
                "deep_audit_required": bounded_receipt["deep_audit_required"],
            }
            if bounded_receipt is not None
            else None
        ),
        "forced_full_project_audit_once": in_memory_full_receipt is not None,
        "truth_effect": "none",
        "project_effect": "validation_only",
    }
    if dry_run:
        return {**receipt, "status": "validated_no_cutover"}

    archived_prior: list[dict[str, Any]] = []
    if installed_binding is not None:
        for binding in archive_plan["bindings_to_archive"]:
            archived_prior.append(
                archive_runtime(installed, binding, archive_root=archive)
            )

    installed.parent.mkdir(parents=True, exist_ok=True)
    stage_container = Path(
        tempfile.mkdtemp(prefix=".chalxius-cutover-", dir=installed.parent)
    )
    stage_payload = stage_container / "chalxius"
    swapped = False
    prior_moved = False
    try:
        shutil.copytree(candidate, stage_payload, symlinks=False, copy_function=shutil.copy2)
        _validate_runtime_tree(
            stage_payload,
            archive_root=archive,
            exact_file_set=True,
        )
        if installed.exists():
            assert rollback is not None
            os.rename(installed, rollback)
            prior_moved = True
            _fsync_directory(installed.parent)
        os.rename(stage_payload, installed)
        swapped = True
        _fsync_directory(installed.parent)
        new_binding, installed_validation = _validate_runtime_tree(
            installed,
            archive_root=archive,
            exact_file_set=True,
        )
        archived_new = archive_runtime(
            installed,
            new_binding,
            archive_root=archive,
        )
        self_test_runner(installed)
        if bounded_receipt is not None:
            assert project_validation_receipt is not None
            assert bounded_receipt_sha256 is not None
            postflight = _validate_cutover_project_receipt_postflight(
                receipt=bounded_receipt,
                receipt_path=project_validation_receipt,
                receipt_sha256=bounded_receipt_sha256,
                installed=installed,
                archive_root=archive,
                project_roots=normalized_projects,
                installed_binding=new_binding,
            )
        elif in_memory_full_receipt is not None:
            projects, actual_bindings = _validate_receipt_project_state(
                in_memory_full_receipt,
                normalized_projects,
            )
            if (
                _normalized_receipt_bindings(
                    in_memory_full_receipt["runtime_bindings"]
                )
                != actual_bindings
            ):
                raise ValueError("post-cutover deep-audit runtime bindings drifted")
            postflight = {
                "projects": projects,
                "runtime_bindings": actual_bindings,
                "validation_mode": "single_deep_audit_reused_after_exact_swap",
            }
        else:
            postflight = project_validator(
                installed,
                normalized_projects,
                archive_root=archive,
            )
        return {
            **receipt,
            "status": "cutover_complete",
            "installed_runtime_identity": new_binding[
                "runtime_identity_sha256"
            ],
            "installed_manifest_entry_count": installed_validation[
                "manifest_entry_count"
            ],
            "archived_prior": archived_prior,
            "archived_installed": archived_new,
            "postflight_projects": postflight["projects"],
            "rollback_available": rollback is not None,
        }
    except Exception as exc:
        restore_error: Exception | None = None
        try:
            if swapped and installed.exists():
                failed_payload = stage_container / "failed-installed"
                os.rename(installed, failed_payload)
            if prior_moved and rollback is not None and rollback.exists():
                os.rename(rollback, installed)
            _fsync_directory(installed.parent)
        except Exception as rollback_exc:  # pragma: no cover - catastrophic host I/O
            restore_error = rollback_exc
        if restore_error is not None:
            raise RuntimeError(
                f"cutover failed ({exc}); automatic rollback also failed ({restore_error})"
            ) from exc
        raise RuntimeError(
            f"cutover failed and the prior installation was restored: {exc}"
        ) from exc
    finally:
        if stage_container.exists():
            shutil.rmtree(stage_container)

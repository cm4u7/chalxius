from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Iterable

from .contracts import sha256_bytes, validate_round_id
from .runtime_archive import (
    _assert_no_symlink_components,
    archive_runtime,
    resolve_historical_runtime,
    runtime_binding_from_root,
    trusted_runtime_archive_root,
    validate_bound_runtime_at,
    validate_runtime_binding,
)


CUTOVER_CONTRACT_REVISION = "chalxius-runtime-cutover-1"


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
) -> dict[str, Any]:
    executable = runtime_root / "scripts" / "mgraph"
    if executable.is_symlink() or not executable.is_file():
        raise ValueError("candidate runtime has no safe scripts/mgraph entrypoint")
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["CHALXIUS_RUNTIME_ARCHIVE_ROOT"] = str(archive_root)
    outcome = subprocess.run(
        [str(executable), *args],
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
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
        validate_round_id(round_root.name)
        cards_root = _existing_directory(
            round_root / "task-cards",
            label="Chalxius round task-card root",
        )
        cards = sorted(cards_root.glob("*.json"))
        if not cards:
            raise ValueError("Chalxius protected round has no task cards")
        identities: set[str] = set()
        for card_path in cards:
            if card_path.is_symlink() or not card_path.is_file():
                raise ValueError("Chalxius protected round has an unsafe task card")
            try:
                card = json.loads(card_path.read_text(encoding="utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("Chalxius protected task card is not valid JSON") from exc
            if not isinstance(card, dict):
                raise ValueError("Chalxius protected task card must contain one object")
            binding = validate_runtime_binding(card.get("runtime_binding"))
            identities.add(binding["runtime_identity_sha256"])
            bindings.append(binding)
        if len(identities) != 1:
            raise ValueError("one protected round binds multiple Chalxius runtimes")
    return bindings


def validate_protected_projects(
    runtime_root: Path,
    project_roots: Iterable[Path],
    *,
    archive_root: Path,
) -> dict[str, Any]:
    projects: list[dict[str, Any]] = []
    bindings: dict[str, dict[str, Any]] = {}
    for raw_project in project_roots:
        project = _existing_directory(raw_project, label="Chalxius protected project")
        round_bindings = _round_bindings(project)
        rounds_root = project / "rounds"
        round_ids = (
            sorted(
                child.name
                for child in rounds_root.iterdir()
                if child.is_dir() and not child.is_symlink()
            )
            if rounds_root.is_dir()
            else []
        )
        round_states: dict[str, str] = {}
        for round_id in round_ids:
            status = _run_json_command(
                runtime_root,
                [
                    "--root",
                    str(project),
                    "--role",
                    "operator",
                    "round-status",
                    round_id,
                ],
                archive_root=archive_root,
            )
            state = status.get("work_unit_state")
            if state not in {"aborted", "completed"}:
                raise ValueError(
                    f"protected round {round_id} is not terminal: {state!r}"
                )
            round_states[round_id] = state
        audit = _run_json_command(
            runtime_root,
            ["--root", str(project), "--role", "operator", "audit"],
            archive_root=archive_root,
        )
        if audit.get("current_ok") is not True:
            raise ValueError("protected project audit is not current_ok")
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
        "runtime_bindings": list(bindings.values()),
    }


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
    allow_fresh_install: bool = False,
    dry_run: bool = False,
    operation: str = "install",
    self_test_runner: Callable[[Path], None] = _default_self_test,
    project_validator: Callable[..., dict[str, Any]] = validate_protected_projects,
) -> dict[str, Any]:
    if operation not in {"install", "rollback"}:
        raise ValueError("runtime cutover operation must be install or rollback")
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
    preflight = project_validator(
        candidate,
        normalized_projects,
        archive_root=archive,
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

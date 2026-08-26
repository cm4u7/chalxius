"""Private implementation of the one public host-global installer.

The public entrypoint is ``scripts/local_install.py``.  This module is
intentionally narrower than :mod:`mathgraph.runtime_cutover`.  It is
the normal local-development path: validate one complete candidate tree, run
the local self-check plus focused regressions, archive the old and new runtime,
atomically replace the discovery alias, and retain exactly one immediate
rollback tree outside skill discovery.  It never reads or mutates a project.

Protected-project or forensic deployment remains an explicit
``runtime_cutover`` operation.  This installer is deployment plumbing only;
it has no graph, Research, Candidate, Certification, Gateway, or Fact effect.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Callable

from .contracts import SHA256_RE, sha256_bytes
from .runtime_archive import (
    _assert_no_symlink_components,
    archive_runtime,
    runtime_binding_from_root,
    trusted_runtime_archive_root,
    validate_bound_runtime_at,
)


LOCAL_INSTALL_CONTRACT_REVISION = "chalxius-global-local-install-1"

FocusedTestRunner = Callable[[Path], None]
SelfTestRunner = Callable[[Path], None]


def default_global_paths(home_root: Path | str | None = None) -> dict[str, Path]:
    """Return the one host-global install, archive, and rollback layout."""

    home = Path.home() if home_root is None else Path(home_root)
    codex_root = home / ".codex"
    return {
        "installed_root": codex_root / "skills" / "chalxius",
        "archive_root": codex_root / "skill-runtime-archives" / "chalxius",
        "rollback_root": codex_root / "skill-rollbacks" / "chalxius-current",
    }


def _canonical_path(
    value: Path | str,
    *,
    label: str,
    allow_missing: bool,
) -> Path:
    path = Path(value)
    if (
        not path.is_absolute()
        or path.anchor != "/"
        or ".." in path.parts
        or str(path) != str(value)
    ):
        raise ValueError(f"{label} must be one canonical absolute path")
    _assert_no_symlink_components(path, label=label, allow_missing=allow_missing)
    return path


def _existing_directory(value: Path | str, *, label: str) -> Path:
    path = _canonical_path(value, label=label, allow_missing=False)
    if path.is_symlink() or not path.is_dir():
        raise ValueError(f"{label} must be one regular directory")
    return path


def _ensure_directory(value: Path | str, *, label: str) -> Path:
    path = _canonical_path(value, label=label, allow_missing=True)
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    _assert_no_symlink_components(path, label=label, allow_missing=False)
    if path.is_symlink() or not path.is_dir():
        raise ValueError(f"{label} must be one regular directory")
    return path


def _validate_runtime(root: Path, *, archive_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    binding = runtime_binding_from_root(root, archive_root=archive_root)
    validation = validate_bound_runtime_at(
        root,
        binding,
        verify_manifest_tree=True,
        require_exact_file_set=True,
    )
    return binding, validation


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _run_process(root: Path, args: list[str], *, label: str) -> None:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    outcome = subprocess.run(
        args,
        cwd=root,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if outcome.returncode != 0:
        detail = (outcome.stderr or outcome.stdout).strip()
        raise ValueError(f"{label} failed: {detail}")


def default_self_test_runner(root: Path) -> None:
    script = root / "scripts" / "self_test.py"
    if script.is_symlink() or not script.is_file():
        raise ValueError("candidate has no safe scripts/self_test.py")
    _run_process(root, [sys.executable, "-B", str(script)], label="Chalxius self-test")


def default_focused_test_runner(root: Path) -> None:
    """Run the bounded seams that a host-global install must preserve."""

    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    existing_python_path = environment.get("PYTHONPATH")
    paths = [str(root / "scripts"), str(root / "tests")]
    if existing_python_path:
        paths.append(existing_python_path)
    environment["PYTHONPATH"] = os.pathsep.join(paths)
    outcome = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "unittest",
            "test_local_install.LocalInstallTests",
            "test_chx_0811_agent_judgment_integrity.AgentJudgmentIntegrity0811Tests",
            "test_chx_0812_semantic_recovery.SemanticRecovery0812Tests",
            "test_chx_090_frontier_active_fix.FrontierActiveFix090Tests",
            "test_chx_093_integrated_cleanup.IntegratedCleanup093Tests",
            (
                "test_chx_094_campaign_history_compaction."
                "CampaignHistoryCompactionTests"
            ),
            (
                "test_chx_095_terminal_frontier_context."
                "TerminalFrontierContextTests"
            ),
            (
                "test_v5_campaign_envelope.V5CampaignEnvelopeTests."
                "test_worker_result_preserves_campaign_binding"
            ),
            (
                "test_v5_campaign_envelope.V5CampaignEnvelopeTests."
                "test_repair_inherits_exact_source_campaign_into_round_scope"
            ),
            "test_release_validation.ReleaseValidationTests",
            (
                "test_research_two_subround.ResearchTwoSubroundTests."
                "test_failure_informed_assurance_removes_same_scope_integration_and_defaults_to_minimal_blackboard"
            ),
            (
                "test_research_two_subround.ResearchTwoSubroundTests."
                "test_route_invalidations_are_explicit_targets_only"
            ),
            (
                "test_research_two_subround.ResearchTwoSubroundTests."
                "test_main_can_select_proof_scope_for_literature_complete_successor"
            ),
            (
                "test_chx_0714_bounded_handoff.BoundedHandoff0714Tests."
                "test_structured_source_evidence_normalizes_frozen_field_spellings"
            ),
            (
                "test_chx_0714_bounded_handoff.BoundedHandoff0714Tests."
                "test_structured_source_evidence_skips_locator_only_and_rejects_path_drift"
            ),
            (
                "test_v5_lifecycle.V5LifecycleTests."
                "test_candidate_release_does_not_walk_administrative_related_history"
            ),
        ],
        cwd=root,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if outcome.returncode != 0:
        detail = (outcome.stderr or outcome.stdout).strip()
        raise ValueError(f"focused local-install regressions failed: {detail}")


def perform_local_install(
    *,
    candidate_root: Path | str,
    installed_root: Path | str | None = None,
    archive_root: Path | str | None = None,
    rollback_root: Path | str | None = None,
    expected_candidate_manifest_sha256: str | None = None,
    dry_run: bool = False,
    self_test_runner: SelfTestRunner = default_self_test_runner,
    focused_test_runner: FocusedTestRunner = default_focused_test_runner,
) -> dict[str, Any]:
    """Install one candidate through the low-cost global path.

    The default invocation needs only ``candidate_root``.  It never opens a
    project and deliberately does not accept project roots, project receipts,
    or release-matrix inputs.  Those belong to the explicit forensic cutover
    contract instead.
    """

    if not isinstance(dry_run, bool):
        raise ValueError("dry_run must be one exact boolean")
    defaults = default_global_paths()
    candidate = _existing_directory(candidate_root, label="Chalxius candidate root")
    installed = _canonical_path(
        installed_root or defaults["installed_root"],
        label="Chalxius installed root",
        allow_missing=True,
    )
    rollback = _canonical_path(
        rollback_root or defaults["rollback_root"],
        label="Chalxius direct rollback root",
        allow_missing=True,
    )
    archive = trusted_runtime_archive_root(
        _canonical_path(
            archive_root or defaults["archive_root"],
            label="Chalxius runtime archive root",
            allow_missing=True,
        )
    )
    if candidate == installed or rollback == installed or rollback == candidate:
        raise ValueError("candidate, installed, and direct rollback roots must differ")
    if rollback.is_relative_to(installed.parent):
        raise ValueError("direct rollback root must remain outside skill discovery")
    for root in (candidate, installed, rollback):
        if archive == root or archive.is_relative_to(root):
            raise ValueError("runtime archive root must remain outside runtime roots")
    if installed.exists() and (installed.is_symlink() or not installed.is_dir()):
        raise ValueError("Chalxius installed root is unsafe")
    if rollback.exists() and (rollback.is_symlink() or not rollback.is_dir()):
        raise ValueError("Chalxius direct rollback root is unsafe")

    candidate_binding, candidate_validation = _validate_runtime(
        candidate,
        archive_root=archive,
    )
    candidate_manifest_sha256 = sha256_bytes((candidate / "MANIFEST.sha256").read_bytes())
    if expected_candidate_manifest_sha256 is not None:
        if (
            not isinstance(expected_candidate_manifest_sha256, str)
            or SHA256_RE.fullmatch(expected_candidate_manifest_sha256) is None
        ):
            raise ValueError("expected candidate manifest hash is invalid")
        if candidate_manifest_sha256 != expected_candidate_manifest_sha256:
            raise ValueError("candidate MANIFEST.sha256 differs from the expected hash")

    self_test_runner(candidate)
    focused_test_runner(candidate)
    installed_binding: dict[str, Any] | None = None
    installed_validation: dict[str, Any] | None = None
    if installed.exists():
        installed_binding, installed_validation = _validate_runtime(
            installed,
            archive_root=archive,
        )
    direct_rollback_binding: dict[str, Any] | None = None
    if rollback.exists():
        direct_rollback_binding, _ = _validate_runtime(
            rollback,
            archive_root=archive,
        )

    receipt: dict[str, Any] = {
        "schema_version": 1,
        "contract_revision": LOCAL_INSTALL_CONTRACT_REVISION,
        "candidate_root": str(candidate),
        "candidate_manifest_sha256": candidate_manifest_sha256,
        "candidate_runtime_identity": candidate_binding["runtime_identity_sha256"],
        "candidate_manifest_entry_count": candidate_validation["manifest_entry_count"],
        "installed_root": str(installed),
        "prior_runtime_identity": (
            installed_binding["runtime_identity_sha256"]
            if installed_binding is not None
            else None
        ),
        "rollback_root": str(rollback),
        "archive_root": str(archive),
        "project_reads": 0,
        "project_writes": 0,
        "truth_effect": "none",
        "project_effect": "none",
    }
    if dry_run:
        return {
            **receipt,
            "status": "validated_no_install",
            "direct_rollback_present": direct_rollback_binding is not None,
        }

    installed_parent = _ensure_directory(installed.parent, label="Chalxius skill discovery directory")
    rollback_parent = _ensure_directory(rollback.parent, label="Chalxius rollback directory")
    if os.stat(installed_parent).st_dev != os.stat(rollback_parent).st_dev:
        raise ValueError("direct rollback root must share the installed runtime volume")

    archived_prior: dict[str, Any] | None = None
    archived_previous_rollback: dict[str, Any] | None = None
    if installed_binding is not None:
        archived_prior = archive_runtime(
            installed,
            installed_binding,
            archive_root=archive,
        )
    if direct_rollback_binding is not None:
        archived_previous_rollback = archive_runtime(
            rollback,
            direct_rollback_binding,
            archive_root=archive,
        )

    stage_container = Path(
        tempfile.mkdtemp(prefix=".chalxius-local-install-", dir=installed_parent)
    )
    staged = stage_container / "chalxius"
    prior_staged = stage_container / "prior-installed"
    retired_rollback = stage_container / "retired-direct-rollback"
    installed_swapped = False
    prior_moved = False
    rollback_rotated = False
    original_rollback_moved = False
    try:
        shutil.copytree(candidate, staged, symlinks=False, copy_function=shutil.copy2)
        _validate_runtime(staged, archive_root=archive)
        if installed_binding is not None:
            os.rename(installed, prior_staged)
            prior_moved = True
            _fsync_directory(installed_parent)
        os.rename(staged, installed)
        installed_swapped = True
        _fsync_directory(installed_parent)

        new_binding, new_validation = _validate_runtime(installed, archive_root=archive)
        self_test_runner(installed)
        archived_installed = archive_runtime(
            installed,
            new_binding,
            archive_root=archive,
        )

        if prior_moved:
            if rollback.exists():
                os.rename(rollback, retired_rollback)
                original_rollback_moved = True
                _fsync_directory(rollback_parent)
            os.rename(prior_staged, rollback)
            rollback_rotated = True
            _fsync_directory(rollback_parent)

        return {
            **receipt,
            "status": "installed",
            "installed_runtime_identity": new_binding["runtime_identity_sha256"],
            "installed_manifest_entry_count": new_validation["manifest_entry_count"],
            "archived_prior": archived_prior,
            "archived_installed": archived_installed,
            "archived_previous_direct_rollback": archived_previous_rollback,
            "rollback_available": rollback_rotated,
            "focused_regressions": "passed",
        }
    except Exception as exc:
        restore_error: Exception | None = None
        try:
            failed_install = stage_container / "failed-installed"
            if installed_swapped and installed.exists():
                os.rename(installed, failed_install)
            if rollback_rotated and rollback.exists():
                os.rename(rollback, installed)
            elif prior_moved and prior_staged.exists():
                os.rename(prior_staged, installed)
            if original_rollback_moved and retired_rollback.exists():
                os.rename(retired_rollback, rollback)
            _fsync_directory(installed_parent)
            _fsync_directory(rollback_parent)
        except Exception as rollback_exc:  # pragma: no cover - catastrophic host I/O
            restore_error = rollback_exc
        if restore_error is not None:
            raise RuntimeError(
                f"local install failed ({exc}); automatic restoration also failed ({restore_error})"
            ) from exc
        raise RuntimeError(f"local install failed and the prior installation was restored: {exc}") from exc
    finally:
        if stage_container.exists():
            shutil.rmtree(stage_container)

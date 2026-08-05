#!/usr/bin/env python3
"""Host-controlled return path for a neutral V5 verifier review.

The verifier writes only ``output/review-draft.json``.  This module preserves
that draft, runs the byte-identical decision preflight shipped in the capsule,
and only then publishes an immutable ``output/review.json`` plus a
content-addressed success receipt.  Failed drafts are moved into an immutable
quarantine with machine-readable diagnostics and have no project authority.

The file deliberately uses only the Python standard library.  It is copied
beside ``validate_decision.py`` into each neutral capsule and can therefore run
without importing the Chalxius project or its skill tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

try:  # Package import in the installed Chalxius runtime.
    from .decision_preflight import validate_decision_against_capsule
except ImportError:  # Copied host program inside a neutral capsule.
    from validate_decision import validate_decision_against_capsule  # type: ignore


NEUTRAL_REVIEW_SUBMISSION_REVISION = "chalxius-neutral-review-submission-1"
DRAFT_RELPATH = Path("output/review-draft.json")
FORMAL_REVIEW_RELPATH = Path("output/review.json")
HANDOFF_RELPATH = Path("output/handoff")
SUBMITTED_RELPATH = Path("output/submitted")
QUARANTINE_RELPATH = Path("output/quarantine")
STATUS_VALUES = (
    "draft_written",
    "preflight_failed",
    "preflight_passed",
    "formally_returned",
)
_ZERO_AUTHORITY = {
    "candidate": 0,
    "certification": 0,
    "gateway": 0,
    "fact": 0,
}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _pretty_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _strict_json(raw: bytes, *, label: str) -> Any:
    try:
        return json.loads(raw, object_pairs_hook=_unique_object)
    except UnicodeDecodeError as error:
        raise ValueError(f"{label} is not UTF-8") from error
    except json.JSONDecodeError as error:
        raise ValueError(
            f"{label} is invalid JSON at line {error.lineno} column {error.colno}: "
            f"{error.msg}"
        ) from error


def _capsule_root(value: Path | str) -> Path:
    root = Path(value).resolve()
    if root.is_symlink() or not root.is_dir():
        raise ValueError("neutral capsule root is missing or unsafe")
    return root


def _regular_file(path: Path, *, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{label} is missing or unsafe")
    return path.read_bytes()


def _capsule(value: Path | str) -> tuple[Path, dict[str, Any]]:
    root = _capsule_root(value)
    raw = _regular_file(root / "input" / "capsule.json", label="capsule input")
    capsule = _strict_json(raw, label="capsule input")
    if not isinstance(capsule, dict):
        raise ValueError("capsule input must be an object")
    semantic = {
        key: item
        for key, item in capsule.items()
        if key not in {"capsule_id", "capsule_sha256"}
    }
    semantic_sha = _sha256(_canonical_bytes(semantic))
    if (
        capsule.get("schema_version") != 5
        or capsule.get("capsule_sha256") != semantic_sha
        or capsule.get("capsule_id") != "capsule-" + semantic_sha
        or not isinstance(capsule.get("release_id"), str)
        or not isinstance(capsule.get("release_sha256"), str)
    ):
        raise ValueError("capsule identity or release binding is invalid")
    return root, capsule


def _publish_immutable(path: Path, raw: bytes, *, mode: int = 0o400) -> None:
    """Atomically expose complete immutable bytes, with idempotent retry."""

    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise ValueError(f"immutable handoff path is a symlink: {path}")
    if path.exists():
        if not path.is_file() or path.read_bytes() != raw:
            raise ValueError(f"immutable handoff collision at {path}")
        return
    descriptor, temporary_name = tempfile.mkstemp(
        prefix="." + path.name + ".", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.is_symlink() or not path.is_file() or path.read_bytes() != raw:
                raise ValueError(f"immutable handoff collision at {path}")
        os.chmod(path, mode)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _write_receipt(directory: Path, prefix: str, semantic: dict[str, Any]) -> dict[str, Any]:
    digest = _sha256(_canonical_bytes(semantic))
    receipt = {**semantic, "receipt_id": prefix + digest}
    _publish_immutable(directory / f"{receipt['receipt_id']}.json", _pretty_bytes(receipt))
    return receipt


def _pointer_diagnostics(error: Exception) -> list[dict[str, Any]]:
    """Translate strict-preflight failures into stable JSON-pointer diagnostics."""

    message = str(error) or type(error).__name__
    diagnostics: list[dict[str, Any]] = []
    exact_fields = re.findall(r"(missing|unexpected)=(/[A-Za-z0-9_~/-]+)", message)
    if exact_fields:
        for kind, pointer in exact_fields:
            diagnostics.append(
                {
                    "code": f"field_{kind}",
                    "json_pointer": pointer,
                    "message": message,
                    "allowed_values": [],
                }
            )
        return diagnostics

    pointers = re.findall(r"(?<![A-Za-z0-9_~])(/[A-Za-z0-9_~/-]*)", message)
    pointer = pointers[0] if pointers else "/"
    allowed: list[str] = []
    allowed_match = re.search(r"allowed=([A-Za-z0-9_,.-]+)", message)
    if allowed_match:
        allowed = [item for item in allowed_match.group(1).split(",") if item]
    elif "verdict must be correct or reject" in message or (
        pointer.endswith("/verdict") and "verdict is invalid" in message
    ):
        allowed = ["correct", "reject"]
    elif pointer.endswith("/status") and "status is invalid" in message:
        allowed = ["pass", "fail"]
    elif pointer.endswith("/severity") and "severity is invalid" in message:
        allowed = ["critical_error", "gap"]
    elif pointer.endswith("/disposition") and "disposition is invalid" in message:
        allowed = ["bound_correction", "scope_restriction", "reject"]

    lowered = message.casefold()
    if "invalid json" in lowered or "not utf-8" in lowered or "duplicate json" in lowered:
        code = "invalid_json"
    elif allowed:
        code = "enum_invalid"
    elif "does not match" in lowered or "binding" in lowered:
        code = "binding_mismatch"
    elif "must be" in lowered or "invalid" in lowered:
        code = "schema_invalid"
    else:
        code = "preflight_rejected"
    return [
        {
            "code": code,
            "json_pointer": pointer,
            "message": message,
            "allowed_values": allowed,
        }
    ]


def _base_semantic(*, capsule: dict[str, Any], status: str) -> dict[str, Any]:
    if status not in STATUS_VALUES:
        raise ValueError("neutral review status is invalid")
    return {
        "schema_version": 1,
        "contract_revision": NEUTRAL_REVIEW_SUBMISSION_REVISION,
        "status": status,
        "capsule_id": capsule["capsule_id"],
        "capsule_sha256": capsule["capsule_sha256"],
        "release_id": capsule["release_id"],
        "release_sha256": capsule["release_sha256"],
        "authority_effects": dict(_ZERO_AUTHORITY),
        "project_effect": "none",
        "truth_effect": "none",
    }


def _receipt_files(root: Path, prefix: str) -> list[Path]:
    directory = root / HANDOFF_RELPATH
    if not directory.exists():
        return []
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("neutral review handoff directory is unsafe")
    result = sorted(directory.glob(prefix + "*.json"))
    if any(path.is_symlink() or not path.is_file() for path in result):
        raise ValueError("neutral review handoff contains an unsafe receipt")
    return result


def _read_receipt(path: Path) -> dict[str, Any]:
    value = _strict_json(_regular_file(path, label="handoff receipt"), label="handoff receipt")
    if not isinstance(value, dict):
        raise ValueError("handoff receipt must be an object")
    return value


def _retire_incoming_if_unchanged(path: Path, raw: bytes) -> None:
    if path.is_symlink():
        raise ValueError("neutral review draft path became a symlink")
    if path.is_file() and path.read_bytes() == raw:
        path.unlink()


def preflight_neutral_review_draft(capsule_root: Path | str) -> dict[str, Any]:
    """Preserve and strictly preflight one incoming neutral-review draft."""

    root, capsule = _capsule(capsule_root)
    formal = root / FORMAL_REVIEW_RELPATH
    if formal.exists() and _receipt_files(root, "neutral-review-return-"):
        return load_formally_returned_review(root)["receipt"]
    passed = _receipt_files(root, "neutral-review-preflight-")
    draft_path = root / DRAFT_RELPATH
    if passed:
        if len(passed) != 1:
            raise ValueError("neutral review has multiple passed preflight receipts")
        existing = _read_receipt(passed[0])
        validate_neutral_review_preflight_receipt(existing, capsule_root=root)
        if draft_path.exists():
            incoming = _regular_file(draft_path, label="neutral review draft")
            if _sha256(incoming) != existing["draft_sha256"]:
                raise ValueError(
                    "a different review draft cannot replace a passed preflight"
                )
            _retire_incoming_if_unchanged(draft_path, incoming)
        return existing
    if draft_path.is_symlink() or not draft_path.is_file():
        return {
            **_base_semantic(capsule=capsule, status="draft_written"),
            "draft_present": False,
            "activation": "predicate_false",
        }

    raw = draft_path.read_bytes()
    draft_sha = _sha256(raw)
    handoff_dir = root / HANDOFF_RELPATH
    draft_receipt = _write_receipt(
        handoff_dir,
        "neutral-review-draft-",
        {
            **_base_semantic(capsule=capsule, status="draft_written"),
            "draft_present": True,
            "activation": "predicate_true",
            "draft_relpath": DRAFT_RELPATH.as_posix(),
            "draft_sha256": draft_sha,
        },
    )
    try:
        decision = _strict_json(raw, label="neutral review draft")
        validation = validate_decision_against_capsule(decision, capsule)
    except (TypeError, ValueError) as error:
        quarantine_relpath = (
            QUARANTINE_RELPATH / draft_sha / "review-draft.json"
        )
        _publish_immutable(root / quarantine_relpath, raw)
        failed = _write_receipt(
            handoff_dir,
            "neutral-review-failed-",
            {
                **_base_semantic(capsule=capsule, status="preflight_failed"),
                "draft_sha256": draft_sha,
                "draft_receipt_id": draft_receipt["receipt_id"],
                "quarantine_draft_relpath": quarantine_relpath.as_posix(),
                "diagnostics": _pointer_diagnostics(error),
                "retry": "write_a_corrected_output/review-draft.json_and_resubmit",
            },
        )
        _retire_incoming_if_unchanged(draft_path, raw)
        return failed

    archive_relpath = SUBMITTED_RELPATH / draft_sha / "review-draft.json"
    _publish_immutable(root / archive_relpath, raw)
    passed_receipt = _write_receipt(
        handoff_dir,
        "neutral-review-preflight-",
        {
            **_base_semantic(capsule=capsule, status="preflight_passed"),
            "draft_sha256": draft_sha,
            "draft_receipt_id": draft_receipt["receipt_id"],
            "draft_archive_relpath": archive_relpath.as_posix(),
            "validation": validation,
        },
    )
    _retire_incoming_if_unchanged(draft_path, raw)
    return passed_receipt


def validate_neutral_review_preflight_receipt(
    receipt: dict[str, Any],
    *,
    capsule_root: Path | str,
) -> dict[str, Any]:
    """Validate the exact passed-preflight handoff and its archived bytes."""

    root, capsule = _capsule(capsule_root)
    fields = {
        "schema_version",
        "contract_revision",
        "status",
        "capsule_id",
        "capsule_sha256",
        "release_id",
        "release_sha256",
        "authority_effects",
        "project_effect",
        "truth_effect",
        "draft_sha256",
        "draft_receipt_id",
        "draft_archive_relpath",
        "validation",
        "receipt_id",
    }
    if not isinstance(receipt, dict) or set(receipt) != fields:
        raise ValueError("neutral review preflight receipt fields are not exact")
    semantic = {key: value for key, value in receipt.items() if key != "receipt_id"}
    expected_id = "neutral-review-preflight-" + _sha256(_canonical_bytes(semantic))
    if (
        receipt.get("schema_version") != 1
        or receipt.get("contract_revision") != NEUTRAL_REVIEW_SUBMISSION_REVISION
        or receipt.get("status") != "preflight_passed"
        or receipt.get("receipt_id") != expected_id
        or receipt.get("capsule_id") != capsule["capsule_id"]
        or receipt.get("capsule_sha256") != capsule["capsule_sha256"]
        or receipt.get("release_id") != capsule["release_id"]
        or receipt.get("release_sha256") != capsule["release_sha256"]
        or receipt.get("authority_effects") != _ZERO_AUTHORITY
        or receipt.get("project_effect") != "none"
        or receipt.get("truth_effect") != "none"
    ):
        raise ValueError("neutral review preflight receipt identity is invalid")
    relpath = receipt.get("draft_archive_relpath")
    if not isinstance(relpath, str):
        raise ValueError("neutral review draft archive path is invalid")
    archive = (root / relpath).resolve()
    submitted_root = (root / SUBMITTED_RELPATH).resolve()
    try:
        archive.relative_to(submitted_root)
    except ValueError as error:
        raise ValueError("neutral review draft archive escaped its capsule") from error
    raw = _regular_file(archive, label="neutral review archived draft")
    if _sha256(raw) != receipt.get("draft_sha256"):
        raise ValueError("neutral review archived draft hash drifted")
    decision = _strict_json(raw, label="neutral review archived draft")
    validation = validate_decision_against_capsule(decision, capsule)
    if receipt.get("validation") != validation:
        raise ValueError("neutral review preflight validation receipt drifted")
    return receipt


def formal_return_neutral_review(
    capsule_root: Path | str,
    *,
    preflight_receipt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Consume one passed preflight and publish the immutable formal return."""

    root, capsule = _capsule(capsule_root)
    if preflight_receipt is None:
        paths = _receipt_files(root, "neutral-review-preflight-")
        if len(paths) != 1:
            raise ValueError("formal return requires exactly one passed preflight")
        preflight_receipt = _read_receipt(paths[0])
    validated = validate_neutral_review_preflight_receipt(
        preflight_receipt,
        capsule_root=root,
    )
    archive = root / validated["draft_archive_relpath"]
    raw = _regular_file(archive, label="neutral review archived draft")
    review_sha = _sha256(raw)
    _publish_immutable(root / FORMAL_REVIEW_RELPATH, raw)
    success = _write_receipt(
        root / HANDOFF_RELPATH,
        "neutral-review-return-",
        {
            **_base_semantic(capsule=capsule, status="formally_returned"),
            "draft_sha256": validated["draft_sha256"],
            "preflight_receipt_id": validated["receipt_id"],
            "formal_review_relpath": FORMAL_REVIEW_RELPATH.as_posix(),
            "formal_review_sha256": review_sha,
        },
    )
    return success


def load_formally_returned_review(capsule_root: Path | str) -> dict[str, Any]:
    """Validate and load the formal review plus its content-addressed receipt."""

    root, capsule = _capsule(capsule_root)
    paths = _receipt_files(root, "neutral-review-return-")
    if len(paths) != 1:
        raise ValueError("neutral capsule does not have exactly one formal return receipt")
    receipt = _read_receipt(paths[0])
    fields = {
        "schema_version",
        "contract_revision",
        "status",
        "capsule_id",
        "capsule_sha256",
        "release_id",
        "release_sha256",
        "authority_effects",
        "project_effect",
        "truth_effect",
        "draft_sha256",
        "preflight_receipt_id",
        "formal_review_relpath",
        "formal_review_sha256",
        "receipt_id",
    }
    if set(receipt) != fields:
        raise ValueError("neutral formal return receipt fields are not exact")
    semantic = {key: value for key, value in receipt.items() if key != "receipt_id"}
    if (
        receipt.get("schema_version") != 1
        or receipt.get("contract_revision") != NEUTRAL_REVIEW_SUBMISSION_REVISION
        or receipt.get("status") != "formally_returned"
        or receipt.get("receipt_id")
        != "neutral-review-return-" + _sha256(_canonical_bytes(semantic))
        or receipt.get("capsule_id") != capsule["capsule_id"]
        or receipt.get("capsule_sha256") != capsule["capsule_sha256"]
        or receipt.get("release_id") != capsule["release_id"]
        or receipt.get("release_sha256") != capsule["release_sha256"]
        or receipt.get("authority_effects") != _ZERO_AUTHORITY
        or receipt.get("project_effect") != "none"
        or receipt.get("truth_effect") != "none"
        or receipt.get("formal_review_relpath") != FORMAL_REVIEW_RELPATH.as_posix()
    ):
        raise ValueError("neutral formal return receipt identity is invalid")
    review_raw = _regular_file(root / FORMAL_REVIEW_RELPATH, label="formal review")
    if (
        _sha256(review_raw) != receipt.get("formal_review_sha256")
        or receipt.get("draft_sha256") != receipt.get("formal_review_sha256")
    ):
        raise ValueError("neutral formal review bytes drifted")
    preflight_paths = _receipt_files(root, "neutral-review-preflight-")
    matches = [
        _read_receipt(path)
        for path in preflight_paths
        if path.stem == receipt.get("preflight_receipt_id")
    ]
    if len(matches) != 1:
        raise ValueError("neutral formal return lost its passed preflight")
    validate_neutral_review_preflight_receipt(matches[0], capsule_root=root)
    decision = _strict_json(review_raw, label="formal review")
    validate_decision_against_capsule(decision, capsule)
    return {
        "status": "formally_returned",
        "receipt": receipt,
        "review": decision,
        "review_sha256": receipt["formal_review_sha256"],
        "project_effect": "none",
        "truth_effect": "none",
    }


def neutral_review_handoff_status(capsule_root: Path | str) -> dict[str, Any]:
    """Return the highest validated neutral-review handoff stage."""

    root, capsule = _capsule(capsule_root)
    if _receipt_files(root, "neutral-review-return-"):
        return load_formally_returned_review(root)
    draft_path = root / DRAFT_RELPATH
    if draft_path.is_file() and not draft_path.is_symlink():
        return {
            **_base_semantic(capsule=capsule, status="draft_written"),
            "draft_present": True,
            "draft_sha256": _sha256(draft_path.read_bytes()),
        }
    passed = _receipt_files(root, "neutral-review-preflight-")
    if passed:
        if len(passed) != 1:
            raise ValueError("neutral review has multiple passed preflight receipts")
        receipt = _read_receipt(passed[0])
        validate_neutral_review_preflight_receipt(receipt, capsule_root=root)
        # The success receipt is the formal visibility switch.  If the host was
        # interrupted after atomically publishing the canonical bytes but
        # before publishing that receipt, status remains preflight_passed and a
        # retry deterministically completes the same handoff.
        formal = root / FORMAL_REVIEW_RELPATH
        if formal.exists():
            raw = _regular_file(formal, label="pending formal review")
            archive = _regular_file(
                root / receipt["draft_archive_relpath"],
                label="neutral review archived draft",
            )
            if raw != archive:
                raise ValueError("pending formal review bytes differ from preflight")
        return receipt
    failed = _receipt_files(root, "neutral-review-failed-")
    if failed:
        receipt = _read_receipt(failed[-1])
        return receipt
    return {
        **_base_semantic(capsule=capsule, status="draft_written"),
        "draft_present": False,
        "activation": "predicate_false",
    }


def submit_neutral_review(
    capsule_root: Path | str,
    *,
    preflight_only: bool = False,
) -> dict[str, Any]:
    """Run the normal host path from draft through formal immutable return."""

    status = neutral_review_handoff_status(capsule_root)
    if status["status"] == "formally_returned":
        return status["receipt"]
    if status["status"] == "preflight_passed":
        passed = validate_neutral_review_preflight_receipt(
            status,
            capsule_root=capsule_root,
        )
    else:
        passed = preflight_neutral_review_draft(capsule_root)
    if passed["status"] != "preflight_passed" or preflight_only:
        return passed
    return formal_return_neutral_review(
        capsule_root,
        preflight_receipt=passed,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Preflight and formally return one neutral V5 verifier draft."
    )
    parser.add_argument("--capsule-root", type=Path, default=Path("."))
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--status", action="store_true")
    action.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    result = (
        neutral_review_handoff_status(args.capsule_root)
        if args.status
        else submit_neutral_review(
            args.capsule_root,
            preflight_only=args.preflight_only,
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 2 if result.get("status") == "preflight_failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())

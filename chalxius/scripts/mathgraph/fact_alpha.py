from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import (
    MEMORY_ID_RE,
    SHA256_RE,
    contained_path,
    sha256_bytes,
    sha256_json,
    validate_campaign_id,
    validate_campaign_target_id,
    validate_memory_id,
)


FACT_ALPHA_CONTRACT_REVISION = "chalxius-fact-alpha-1"
FACT_FRONTIER_MARK_REVISION = "chalxius-fact-frontier-mark-1"
FACT_FRONTIER_DISPOSITION_REVISION = (
    "chalxius-fact-frontier-disposition-1"
)
FACT_PACKAGING_PLAN_REVISION = "chalxius-fact-packaging-plan-1"
FACT_CANDIDATE_PACKAGE_REVISION = "chalxius-fact-candidate-package-1"
FACT_VERIFIER_CAPSULE_REVISION = "chalxius-fact-verifier-capsule-1"
FACT_CERTIFICATION_DECISION_REVISION = (
    "chalxius-research-certification-decision-1"
)
FACT_CERTIFICATION_GRANT_REVISION = (
    "chalxius-research-certification-grant-1"
)
FACT_CERTIFICATION_ACCEPTANCE_REVISION = (
    "chalxius-research-certification-acceptance-1"
)
FACT_SUPERVISED_INTERFACE_ARTIFACT_REVISION = (
    "chalxius-supervised-statement-interfaces-1"
)
FACT_SUPERVISED_INTERFACE_ARTIFACT_ROLE = "fact_statement_interfaces"

FACT_ALPHA_MAX_MARKS_PER_PLAN = 128
FACT_ALPHA_MAX_FRONTIER_LIMIT = 256
FACT_ALPHA_MAX_INTERFACE_ITEMS = 128
FACT_ALPHA_MAX_COMPONENTS = 128
FACT_ALPHA_MAX_FINDINGS = 256

_MARK_STATUSES = {"active", "deferred", "dropped"}
_BLOCKED_PACKAGING_STATUSES = {"needs_split", "blocked"}
_COMPONENT_VERDICTS = {"correct", "minor_repair", "fundamental_error"}
_RESEARCH_CHECK_VERDICTS = {
    "correct",
    "minor_error",
    "fundamental_error",
}
_BINARY_CHECK_VERDICTS = {"correct", "reject"}
_FINDING_SEVERITIES = {"minor", "fundamental"}

_STATEMENT_INTERFACE_FIELDS = {
    "conclusion",
    "assumptions",
    "domain_and_types",
    "quantifiers",
    "certified_predecessor_research_ids",
    "limitations",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _require_object(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be one object")
    return value


def _require_exact_fields(
    value: Any,
    fields: set[str],
    *,
    label: str,
) -> dict[str, Any]:
    value = _require_object(value, label=label)
    if set(value) != fields:
        missing = sorted(fields.difference(value))
        extra = sorted(set(value).difference(fields))
        raise ValueError(
            f"{label} fields are not exact; missing={missing} extra={extra}"
        )
    return value


def _require_text(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    if "\x00" in value:
        raise ValueError(f"{label} contains a NUL byte")
    return value


def _require_optional_text(value: Any, *, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    if "\x00" in value:
        raise ValueError(f"{label} contains a NUL byte")
    return value


def _require_text_list(
    value: Any,
    *,
    label: str,
    maximum: int = FACT_ALPHA_MAX_INTERFACE_ITEMS,
    allow_empty: bool = True,
) -> list[str]:
    if (
        not isinstance(value, list)
        or len(value) > maximum
        or any(not isinstance(item, str) or not item.strip() for item in value)
    ):
        raise ValueError(
            f"{label} must be a list of at most {maximum} nonempty strings"
        )
    normalized = list(value)
    if not allow_empty and not normalized:
        raise ValueError(f"{label} cannot be empty")
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{label} contains duplicates")
    return normalized


def _require_sha256(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{label} must be one SHA-256 digest")
    return value


def _require_prefixed_sha_id(
    value: Any,
    *,
    prefix: str,
    label: str,
) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith(prefix)
        or SHA256_RE.fullmatch(value.removeprefix(prefix)) is None
    ):
        raise ValueError(f"{label} is invalid")
    return value


def _record_hash(record: dict[str, Any]) -> str:
    return sha256_json(
        {key: value for key, value in record.items() if key != "record_sha256"}
    )


class FactAlphaManager:
    """Prospective Fact certification over immutable Research records.

    The mathematical object graph remains the Research graph.  This manager
    stores only Main's importance selections, frozen batch evidence, verifier
    decisions, and append-only certification grants.  It never rewrites a
    Research claim and never imports legacy Fact prose as a fake Research
    lineage.
    """

    def __init__(self, lifecycle: Any) -> None:
        self.lifecycle = lifecycle
        self.store = lifecycle.store
        self.root = lifecycle.root / "fact-alpha"
        self.contract_path = self.root / "contract.json"
        self.marks_dir = self.root / "frontier" / "marks" / "by-id"
        self.dispositions_dir = (
            self.root / "frontier" / "dispositions" / "by-id"
        )
        self.plans_dir = self.root / "packaging" / "plans" / "by-id"
        self.packages_dir = self.root / "packaging" / "packages" / "by-plan"
        self.decisions_dir = (
            self.root / "certification" / "decisions" / "by-package"
        )
        self.grants_dir = (
            self.store.fact_graph_dir
            / "research_certifications"
            / "grants"
            / "by-id"
        )
        self.acceptances_dir = (
            self.store.fact_graph_dir
            / "research_certifications"
            / "acceptances"
            / "by-decision"
        )

    @property
    def contract(self) -> dict[str, Any]:
        semantic = {
            "schema_version": 1,
            "contract_revision": FACT_ALPHA_CONTRACT_REVISION,
            "project_id": self.store.project_id(),
            "mathematical_graph": "research_graph",
            "fact_semantics": "append_only_certification_overlay",
            "candidate_semantics": "frozen_multi_research_transaction",
            "certification_unit": "whole_research_claim",
            "dependency_semantics": (
                "explicit_certified_predecessor_research_ids"
            ),
            "legacy_fact_authority": "read_only_unmapped",
            "truth_effects": {
                "frontier": "none",
                "packaging": "none",
                "verifier_decision": "certification_evidence_only",
                "gateway_acceptance": "fact_certification",
            },
        }
        return {**semantic, "contract_sha256": sha256_json(semantic)}

    def initialize(self) -> None:
        for path in (
            self.root,
            self.marks_dir,
            self.dispositions_dir,
            self.plans_dir,
            self.packages_dir,
            self.decisions_dir,
            self.grants_dir,
            self.acceptances_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)
        self.store._write_json_once(self.contract_path, self.contract)

    def _ensure_storage(self) -> None:
        self.initialize()

    @staticmethod
    def _regular_json_records(directory: Path, *, label: str) -> list[dict[str, Any]]:
        if not directory.exists():
            return []
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError(f"{label} directory is unsafe")
        records: list[dict[str, Any]] = []
        for path in sorted(directory.glob("*.json")):
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"{label} contains an unsafe record")
            value = FactAlphaManager._read_json(path)
            value["__path_stem__"] = path.stem
            records.append(value)
        return records

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        import json

        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"expected one JSON object at {path}")
        return value

    def _validate_mark(self, raw: dict[str, Any]) -> dict[str, Any]:
        path_stem = raw.pop("__path_stem__", None)
        record = _require_exact_fields(
            raw,
            {
                "schema_version",
                "contract_revision",
                "project_id",
                "research_id",
                "research_record_sha256",
                "campaign_id",
                "target_id",
                "rationale",
                "actor",
                "created_at",
                "truth_effect",
                "mark_id",
                "record_sha256",
            },
            label="Fact frontier mark",
        )
        mark_id = _require_prefixed_sha_id(
            record["mark_id"], prefix="fact-mark-", label="Fact frontier mark id"
        )
        if path_stem is not None and path_stem != mark_id:
            raise ValueError("Fact frontier mark path/id mismatch")
        research_id = validate_memory_id(record["research_id"])
        _require_sha256(
            record["research_record_sha256"],
            label="Fact frontier Research record hash",
        )
        campaign_id = record["campaign_id"]
        target_id = record["target_id"]
        if campaign_id is not None:
            campaign_id = validate_campaign_id(campaign_id)
        if target_id is not None:
            target_id = validate_campaign_target_id(target_id)
            if campaign_id is None:
                raise ValueError("Fact frontier target requires a Campaign")
        if (
            record["schema_version"] != 1
            or record["contract_revision"] != FACT_FRONTIER_MARK_REVISION
            or record["project_id"] != self.store.project_id()
            or record["actor"] != "main"
            or record["truth_effect"] != "none"
        ):
            raise ValueError("Fact frontier mark identity is invalid")
        _require_text(record["rationale"], label="Fact frontier rationale")
        _require_text(record["created_at"], label="Fact frontier timestamp")
        semantic = {
            key: value
            for key, value in record.items()
            if key not in {"mark_id", "record_sha256"}
        }
        if mark_id != "fact-mark-" + sha256_json(semantic):
            raise ValueError("Fact frontier mark content identity drifted")
        if record["record_sha256"] != _record_hash(record):
            raise ValueError("Fact frontier mark record hash drifted")
        return record

    def _validate_disposition(self, raw: dict[str, Any]) -> dict[str, Any]:
        path_stem = raw.pop("__path_stem__", None)
        record = _require_exact_fields(
            raw,
            {
                "schema_version",
                "contract_revision",
                "project_id",
                "mark_id",
                "mark_record_sha256",
                "status",
                "reason",
                "actor",
                "created_at",
                "truth_effect",
                "disposition_id",
                "record_sha256",
            },
            label="Fact frontier disposition",
        )
        disposition_id = _require_prefixed_sha_id(
            record["disposition_id"],
            prefix="fact-disposition-",
            label="Fact frontier disposition id",
        )
        if path_stem is not None and path_stem != disposition_id:
            raise ValueError("Fact frontier disposition path/id mismatch")
        _require_prefixed_sha_id(
            record["mark_id"], prefix="fact-mark-", label="Fact frontier mark id"
        )
        _require_sha256(
            record["mark_record_sha256"], label="Fact frontier mark record hash"
        )
        if (
            record["schema_version"] != 1
            or record["contract_revision"]
            != FACT_FRONTIER_DISPOSITION_REVISION
            or record["project_id"] != self.store.project_id()
            or record["status"] not in _MARK_STATUSES
            or record["actor"] != "main"
            or record["truth_effect"] != "none"
        ):
            raise ValueError("Fact frontier disposition identity is invalid")
        _require_text(record["reason"], label="Fact frontier disposition reason")
        _require_text(record["created_at"], label="Fact frontier disposition timestamp")
        semantic = {
            key: value
            for key, value in record.items()
            if key not in {"disposition_id", "record_sha256"}
        }
        if disposition_id != "fact-disposition-" + sha256_json(semantic):
            raise ValueError("Fact frontier disposition identity drifted")
        if record["record_sha256"] != _record_hash(record):
            raise ValueError("Fact frontier disposition record hash drifted")
        return record

    def _marks(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for raw in self._regular_json_records(
            self.marks_dir, label="Fact frontier marks"
        ):
            record = self._validate_mark(raw)
            result[record["mark_id"]] = record
        return result

    def _dispositions(self) -> dict[str, dict[str, Any]]:
        marks = self._marks()
        latest: dict[str, dict[str, Any]] = {}
        for raw in self._regular_json_records(
            self.dispositions_dir, label="Fact frontier dispositions"
        ):
            record = self._validate_disposition(raw)
            mark = marks.get(record["mark_id"])
            if (
                mark is None
                or mark["record_sha256"] != record["mark_record_sha256"]
            ):
                raise ValueError(
                    "Fact frontier disposition does not bind an exact mark"
                )
            previous = latest.get(record["mark_id"])
            if previous is None or (
                record["created_at"], record["disposition_id"]
            ) > (previous["created_at"], previous["disposition_id"]):
                latest[record["mark_id"]] = record
        return latest

    def mark(
        self,
        research_id: str,
        *,
        rationale: str,
        campaign_id: str | None = None,
        target_id: str | None = None,
    ) -> dict[str, Any]:
        research_id = validate_memory_id(research_id)
        rationale = _require_text(rationale, label="Fact frontier rationale")
        research = self.lifecycle._research_record(research_id)
        self.lifecycle._research_split_commit_for_record(research)
        if campaign_id is not None:
            campaign_id = validate_campaign_id(campaign_id)
            campaign = self.store.campaigns().status(campaign_id)
            if research["metadata"].get("campaign_id") != campaign_id:
                raise ValueError(
                    "Fact frontier Campaign must match the Research binding"
                )
            if target_id is not None:
                target_id = validate_campaign_target_id(target_id)
                if target_id not in campaign["targets"]:
                    raise ValueError("unknown Fact frontier Campaign target")
        elif target_id is not None:
            raise ValueError("Fact frontier target requires --campaign")
        semantic = {
            "schema_version": 1,
            "contract_revision": FACT_FRONTIER_MARK_REVISION,
            "project_id": self.store.project_id(),
            "research_id": research_id,
            "research_record_sha256": research["record_sha256"],
            "campaign_id": campaign_id,
            "target_id": target_id,
            "rationale": rationale,
            "actor": "main",
            "created_at": _utc_now(),
            "truth_effect": "none",
        }
        mark_id = "fact-mark-" + sha256_json(semantic)
        record_without_hash = {**semantic, "mark_id": mark_id}
        record = {
            **record_without_hash,
            "record_sha256": sha256_json(record_without_hash),
        }
        with self.store.v5_mutation_lock(command="fact-frontier-mark"):
            self._ensure_storage()
            self.store._write_json_once(
                self.marks_dir / f"{mark_id}.json", record
            )
        return record

    def dispose(
        self,
        mark_id: str,
        *,
        status: str,
        reason: str,
    ) -> dict[str, Any]:
        mark_id = _require_prefixed_sha_id(
            mark_id, prefix="fact-mark-", label="Fact frontier mark id"
        )
        if status not in _MARK_STATUSES:
            raise ValueError("Fact frontier status must be active, deferred, or dropped")
        reason = _require_text(reason, label="Fact frontier disposition reason")
        marks = self._marks()
        if mark_id not in marks:
            raise KeyError(f"unknown Fact frontier mark: {mark_id}")
        mark = marks[mark_id]
        semantic = {
            "schema_version": 1,
            "contract_revision": FACT_FRONTIER_DISPOSITION_REVISION,
            "project_id": self.store.project_id(),
            "mark_id": mark_id,
            "mark_record_sha256": mark["record_sha256"],
            "status": status,
            "reason": reason,
            "actor": "main",
            "created_at": _utc_now(),
            "truth_effect": "none",
        }
        disposition_id = "fact-disposition-" + sha256_json(semantic)
        record_without_hash = {
            **semantic,
            "disposition_id": disposition_id,
        }
        record = {
            **record_without_hash,
            "record_sha256": sha256_json(record_without_hash),
        }
        with self.store.v5_mutation_lock(command="fact-frontier-dispose"):
            self._ensure_storage()
            self.store._write_json_once(
                self.dispositions_dir / f"{disposition_id}.json", record
            )
        return record

    def _validate_plan(self, raw: dict[str, Any]) -> dict[str, Any]:
        path_stem = raw.pop("__path_stem__", None)
        record = _require_exact_fields(
            raw,
            {
                "schema_version",
                "contract_revision",
                "project_id",
                "selection",
                "selection_sha256",
                "planned_by",
                "minor_repair_context",
                "truth_effect",
                "plan_id",
                "record_sha256",
            },
            label="Fact packaging plan",
        )
        plan_id = _require_prefixed_sha_id(
            record["plan_id"], prefix="fact-plan-", label="Fact packaging plan id"
        )
        if path_stem is not None and path_stem != plan_id:
            raise ValueError("Fact packaging plan path/id mismatch")
        selection = record["selection"]
        if (
            not isinstance(selection, list)
            or not selection
            or len(selection) > FACT_ALPHA_MAX_MARKS_PER_PLAN
        ):
            raise ValueError("Fact packaging plan selection is invalid")
        expected_fields = {
            "mark_ids",
            "mark_record_sha256s",
            "marked_research_id",
            "marked_research_record_sha256",
            "current_research_id",
            "current_research_record_sha256",
            "research_relpath",
            "campaign_id",
            "target_id",
            "eligibility",
            "blockers",
            "warnings",
            "supervision_coverage",
        }
        marks = self._marks()
        seen_mark_ids: set[str] = set()
        current_ids: list[str] = []
        for index, item in enumerate(selection, 1):
            _require_exact_fields(
                item,
                expected_fields,
                label=f"Fact packaging selection {index}",
            )
            mark_ids = _require_text_list(
                item["mark_ids"],
                label=f"Fact packaging selection {index} mark ids",
                maximum=FACT_ALPHA_MAX_MARKS_PER_PLAN,
                allow_empty=False,
            )
            for mark_id in mark_ids:
                _require_prefixed_sha_id(
                    mark_id, prefix="fact-mark-", label="Fact frontier mark id"
                )
                if mark_id in seen_mark_ids:
                    raise ValueError("Fact packaging plan repeats a mark")
                seen_mark_ids.add(mark_id)
            hashes = item["mark_record_sha256s"]
            if (
                not isinstance(hashes, list)
                or len(hashes) != len(mark_ids)
                or any(
                    not isinstance(value, str)
                    or SHA256_RE.fullmatch(value) is None
                    for value in hashes
                )
            ):
                raise ValueError("Fact packaging mark hash binding is invalid")
            bound_marks: list[dict[str, Any]] = []
            for mark_id, digest in zip(mark_ids, hashes, strict=True):
                mark = marks.get(mark_id)
                if mark is None or mark["record_sha256"] != digest:
                    raise ValueError(
                        "Fact packaging plan does not bind exact Main marks"
                    )
                bound_marks.append(mark)
            marked_research_id = validate_memory_id(item["marked_research_id"])
            current_id = validate_memory_id(item["current_research_id"])
            current_ids.append(current_id)
            _require_sha256(
                item["marked_research_record_sha256"],
                label="marked Research record hash",
            )
            _require_sha256(
                item["current_research_record_sha256"],
                label="current Research record hash",
            )
            _require_text(item["research_relpath"], label="Research relpath")
            latest_mark = max(
                bound_marks,
                key=lambda mark: (mark["created_at"], mark["mark_id"]),
            )
            if (
                latest_mark["research_id"] != marked_research_id
                or latest_mark["research_record_sha256"]
                != item["marked_research_record_sha256"]
                or any(
                    mark["campaign_id"] != item["campaign_id"]
                    or mark["target_id"] != item["target_id"]
                    for mark in bound_marks
                )
            ):
                raise ValueError("Fact packaging plan mark semantics drifted")
            current_research = self.lifecycle._research_record(current_id)
            expected_relpath = (
                self.lifecycle._research_path(current_id)
                .relative_to(self.store.root)
                .as_posix()
            )
            if (
                current_research["record_sha256"]
                != item["current_research_record_sha256"]
                or item["research_relpath"] != expected_relpath
            ):
                raise ValueError("Fact packaging plan Research binding drifted")
            if item["campaign_id"] is not None:
                validate_campaign_id(item["campaign_id"])
            if item["target_id"] is not None:
                validate_campaign_target_id(item["target_id"])
            if item["eligibility"] not in {"eligible", "blocked"}:
                raise ValueError("Fact packaging eligibility is invalid")
            _require_text_list(
                item["blockers"], label="Fact packaging blockers"
            )
            _require_text_list(
                item["warnings"], label="Fact packaging warnings"
            )
            if not isinstance(item["supervision_coverage"], list):
                raise ValueError("Fact packaging supervision coverage is invalid")
        if len(current_ids) != len(set(current_ids)):
            raise ValueError("Fact packaging plan repeats a current Research node")
        if (
            record["schema_version"] != 1
            or record["contract_revision"] != FACT_PACKAGING_PLAN_REVISION
            or record["project_id"] != self.store.project_id()
            or record["planned_by"] != "main"
            or record["truth_effect"] != "none"
            or record["selection_sha256"] != sha256_json(selection)
        ):
            raise ValueError("Fact packaging plan identity is invalid")
        minor_context = record["minor_repair_context"]
        if minor_context is not None:
            _require_exact_fields(
                minor_context,
                {
                    "prior_decision_id",
                    "prior_decision_record_sha256",
                    "prior_package_id",
                    "prior_package_record_sha256",
                    "component_ids",
                    "same_verifier",
                    "affected_research_ids",
                    "complete_recheck_research_ids",
                    "replacement_map",
                },
                label="Fact minor-repair context",
            )
            for key, prefix in (
                ("prior_decision_id", "fact-decision-"),
                ("prior_package_id", "fact-package-"),
            ):
                _require_prefixed_sha_id(
                    minor_context[key], prefix=prefix, label=key
                )
            for key in (
                "prior_decision_record_sha256",
                "prior_package_record_sha256",
            ):
                _require_sha256(minor_context[key], label=key)
            component_ids = _require_text_list(
                minor_context["component_ids"],
                label="minor-repair component ids",
                maximum=FACT_ALPHA_MAX_COMPONENTS,
                allow_empty=False,
            )
            for component_id in component_ids:
                _require_prefixed_sha_id(
                    component_id,
                    prefix="fact-component-",
                    label="minor-repair component id",
                )
            _require_text(
                minor_context["same_verifier"],
                label="minor-repair verifier",
            )
            affected = _require_text_list(
                minor_context["affected_research_ids"],
                label="minor-repair affected Research ids",
                allow_empty=False,
            )
            rechecked = _require_text_list(
                minor_context["complete_recheck_research_ids"],
                label="minor-repair complete recheck ids",
                allow_empty=False,
            )
            for research_id in [*affected, *rechecked]:
                validate_memory_id(research_id)
            replacement_map = minor_context["replacement_map"]
            if (
                not isinstance(replacement_map, list)
                or not replacement_map
                or any(
                    not isinstance(item, dict)
                    or set(item) != {
                        "prior_research_id",
                        "current_research_id",
                    }
                    for item in replacement_map
                )
            ):
                raise ValueError("Fact minor-repair replacement map is invalid")
            for item in replacement_map:
                validate_memory_id(item["prior_research_id"])
                validate_memory_id(item["current_research_id"])
        semantic = {
            key: value
            for key, value in record.items()
            if key not in {"plan_id", "record_sha256"}
        }
        if plan_id != "fact-plan-" + sha256_json(semantic):
            raise ValueError("Fact packaging plan content identity drifted")
        if record["record_sha256"] != _record_hash(record):
            raise ValueError("Fact packaging plan record hash drifted")
        return record

    def _plans(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for raw in self._regular_json_records(
            self.plans_dir, label="Fact packaging plans"
        ):
            record = self._validate_plan(raw)
            result[record["plan_id"]] = record
        return result

    def plan(self, plan_id: str) -> dict[str, Any]:
        plan_id = _require_prefixed_sha_id(
            plan_id, prefix="fact-plan-", label="Fact packaging plan id"
        )
        path = self.plans_dir / f"{plan_id}.json"
        if path.is_symlink() or not path.is_file():
            raise KeyError(f"unknown Fact packaging plan: {plan_id}")
        raw = self.store._read_json(path)
        raw["__path_stem__"] = path.stem
        return self._validate_plan(raw)

    def _validate_statement_interface(
        self,
        value: Any,
        *,
        research: dict[str, Any],
    ) -> dict[str, Any]:
        interface = _require_exact_fields(
            value,
            _STATEMENT_INTERFACE_FIELDS,
            label="Research statement interface",
        )
        conclusion = _require_text(
            interface["conclusion"], label="statement interface conclusion"
        )
        if conclusion != research["claim"]:
            raise ValueError(
                "statement interface conclusion must preserve the exact Research claim"
            )
        assumptions = _require_text_list(
            interface["assumptions"], label="statement interface assumptions"
        )
        domain_and_types = _require_text_list(
            interface["domain_and_types"],
            label="statement interface domain and types",
        )
        quantifiers = _require_text_list(
            interface["quantifiers"], label="statement interface quantifiers"
        )
        predecessors = _require_text_list(
            interface["certified_predecessor_research_ids"],
            label="statement interface certified predecessors",
        )
        predecessors = sorted(
            validate_memory_id(item) for item in predecessors
        )
        if research["research_id"] in predecessors:
            raise ValueError("a Research certification cannot depend on itself")
        limitations = _require_text_list(
            interface["limitations"], label="statement interface limitations"
        )
        return {
            "conclusion": conclusion,
            "assumptions": assumptions,
            "domain_and_types": domain_and_types,
            "quantifiers": quantifiers,
            "certified_predecessor_research_ids": predecessors,
            "limitations": limitations,
        }

    def _validate_supervised_interface_artifact(
        self,
        value: Any,
    ) -> dict[str, dict[str, Any]]:
        record = _require_exact_fields(
            value,
            {
                "schema_version",
                "contract_revision",
                "entries",
                "truth_effect",
            },
            label="supervised statement-interface artifact",
        )
        if (
            record["schema_version"] != 1
            or record["contract_revision"]
            != FACT_SUPERVISED_INTERFACE_ARTIFACT_REVISION
            or record["truth_effect"] != "none"
        ):
            raise ValueError("supervised statement-interface identity is invalid")
        raw_interfaces = record["entries"]
        if (
            not isinstance(raw_interfaces, list)
            or not raw_interfaces
            or len(raw_interfaces) > FACT_ALPHA_MAX_INTERFACE_ITEMS
        ):
            raise ValueError(
                "supervised statement-interface artifact has invalid interfaces"
            )
        interfaces: dict[str, dict[str, Any]] = {}
        for index, raw in enumerate(raw_interfaces, 1):
            item = _require_exact_fields(
                raw,
                {
                    "research_id",
                    "research_record_sha256",
                    "disposition",
                    "rationale",
                    "statement_interface",
                },
                label=f"supervised statement interface {index}",
            )
            research_id = validate_memory_id(item["research_id"])
            if research_id in interfaces:
                raise ValueError(
                    "supervised statement-interface artifact repeats Research"
                )
            research = self.lifecycle._research_record(research_id)
            if research["record_sha256"] != item["research_record_sha256"]:
                raise ValueError(
                    "supervised statement interface Research binding drifted"
                )
            disposition = item["disposition"]
            if disposition not in {"ready", "needs_split"}:
                raise ValueError(
                    "supervised statement-interface disposition is invalid"
                )
            rationale = _require_text(
                item["rationale"],
                label="supervised statement-interface rationale",
            )
            statement_interface: dict[str, Any] | None = None
            if disposition == "ready":
                statement_interface = self._validate_statement_interface(
                    item["statement_interface"], research=research
                )
            elif item["statement_interface"] is not None:
                raise ValueError(
                    "needs_split statement-interface disposition must not "
                    "supply a whole-node interface"
                )
            interfaces[research_id] = {
                "research_id": research_id,
                "research_record_sha256": research["record_sha256"],
                "disposition": disposition,
                "rationale": rationale,
                "statement_interface": statement_interface,
            }
        return interfaces

    def _supervised_interface_projection(
        self,
        research: dict[str, Any],
        coverage: list[dict[str, Any]],
    ) -> dict[str, Any]:
        research_id = research["research_id"]
        candidates: list[dict[str, Any]] = []
        invalid_bindings: list[dict[str, str]] = []
        for scope in coverage:
            if scope.get("state") != "completed":
                continue
            result_ids = scope.get("result_research_ids", [])
            if not isinstance(result_ids, list):
                continue
            for result_id in result_ids:
                try:
                    result = self.lifecycle._research_record(result_id)
                except (KeyError, OSError, ValueError) as exc:
                    invalid_bindings.append(
                        {
                            "result_research_id": str(result_id),
                            "reason": str(exc),
                        }
                    )
                    continue
                artifacts = result.get("metadata", {}).get("artifacts", [])
                if not isinstance(artifacts, list):
                    continue
                for artifact in artifacts:
                    if (
                        not isinstance(artifact, dict)
                        or artifact.get("role")
                        != FACT_SUPERVISED_INTERFACE_ARTIFACT_ROLE
                    ):
                        continue
                    binding = {
                        "result_research_id": result["research_id"],
                        "result_research_record_sha256": result[
                            "record_sha256"
                        ],
                        "artifact_path": str(artifact.get("path", "")),
                        "artifact_sha256": str(artifact.get("sha256", "")),
                    }
                    try:
                        artifact_path = contained_path(
                            self.store.root,
                            binding["artifact_path"],
                            "supervised statement-interface artifact",
                        )
                        if artifact_path.is_symlink() or not artifact_path.is_file():
                            raise ValueError(
                                "supervised statement-interface artifact is unsafe"
                            )
                        raw_bytes = artifact_path.read_bytes()
                        if sha256_bytes(raw_bytes) != binding["artifact_sha256"]:
                            raise ValueError(
                                "supervised statement-interface artifact hash drifted"
                            )
                        payload = json.loads(raw_bytes.decode("utf-8"))
                        interfaces = self._validate_supervised_interface_artifact(
                            payload
                        )
                        interface = interfaces.get(research_id)
                        if interface is not None:
                            candidates.append(
                                {
                                    "disposition": interface["disposition"],
                                    "rationale": interface["rationale"],
                                    "statement_interface": interface[
                                        "statement_interface"
                                    ],
                                    "source_binding": binding,
                                }
                            )
                    except (
                        OSError,
                        UnicodeDecodeError,
                        ValueError,
                    ) as exc:
                        invalid_bindings.append(
                            {
                                "result_research_id": result["research_id"],
                                "reason": str(exc),
                            }
                        )
        if invalid_bindings:
            return {
                "state": "invalid",
                "statement_interface": None,
                "source_bindings": [],
                "source_count": 0,
                "rationales": [],
                "diagnostic_sha256": sha256_json(invalid_bindings),
            }
        if not candidates:
            return {
                "state": "missing_or_legacy",
                "statement_interface": None,
                "source_bindings": [],
                "source_count": 0,
                "rationales": [],
                "diagnostic_sha256": sha256_json([]),
            }
        by_interface: dict[str, list[dict[str, Any]]] = {}
        for candidate in candidates:
            digest = sha256_json(
                {
                    "disposition": candidate["disposition"],
                    "statement_interface": candidate["statement_interface"],
                }
            )
            by_interface.setdefault(digest, []).append(candidate)
        if len(by_interface) != 1:
            return {
                "state": "conflicting",
                "statement_interface": None,
                "source_bindings": [],
                "source_count": len(candidates),
                "rationales": sorted(
                    {item["rationale"] for item in candidates}
                ),
                "diagnostic_sha256": sha256_json(sorted(by_interface)),
            }
        selected = next(iter(by_interface.values()))
        sources = sorted(
            [item["source_binding"] for item in selected],
            key=lambda item: (
                item["result_research_id"],
                item["artifact_sha256"],
            ),
        )
        disposition = selected[0]["disposition"]
        return {
            "state": disposition,
            "statement_interface": (
                selected[0]["statement_interface"]
                if disposition == "ready"
                else None
            ),
            "source_bindings": sources,
            "source_count": len(sources),
            "rationales": sorted(
                {item["rationale"] for item in selected}
            ),
            "diagnostic_sha256": sha256_json(
                {
                    "sources": sources,
                    "disposition": disposition,
                    "rationales": sorted(
                        {item["rationale"] for item in selected}
                    ),
                }
            ),
        }

    def _mechanical_package_from_supervision(
        self,
        plan: dict[str, Any],
    ) -> dict[str, Any]:
        existing = sorted(
            (
                package
                for package in self._packages().values()
                if package["plan_id"] == plan["plan_id"]
            ),
            key=lambda package: package["package_id"],
        )
        if len(existing) > 1:
            return {
                "state": "existing_package_conflict",
                "package": None,
                "unavailable": [],
                "source_bindings_sha256": sha256_json([]),
            }
        if existing:
            return {
                "state": "already_sealed",
                "package": existing[0],
                "unavailable": [],
                "source_bindings_sha256": sha256_json([]),
            }
        prepared: dict[str, dict[str, Any]] = {}
        unavailable: list[dict[str, str]] = []
        for item in plan["selection"]:
            research_id = item["current_research_id"]
            if item["eligibility"] != "eligible":
                unavailable.append(
                    {"research_id": research_id, "state": "plan_blocked"}
                )
                continue
            research = self.lifecycle._research_record(research_id)
            projection = self._supervised_interface_projection(
                research, item["supervision_coverage"]
            )
            if projection["state"] != "ready":
                unavailable.append(
                    {"research_id": research_id, "state": projection["state"]}
                )
                continue
            prepared[research_id] = {
                "research_id": research_id,
                "statement_interface": projection["statement_interface"],
                "source_bindings": projection["source_bindings"],
            }
        if unavailable or not prepared:
            return {
                "state": (
                    "research_split_required"
                    if any(
                        item["state"] == "needs_split"
                        for item in unavailable
                    )
                    else "interface_preparation_required"
                ),
                "package": None,
                "unavailable": sorted(
                    unavailable, key=lambda item: item["research_id"]
                ),
                "source_bindings_sha256": sha256_json(
                    [
                        binding
                        for item in prepared.values()
                        for binding in item["source_bindings"]
                    ]
                ),
            }

        selected_ids = set(prepared)
        adjacency = {research_id: set() for research_id in selected_ids}
        for research_id, item in prepared.items():
            predecessors = item["statement_interface"][
                "certified_predecessor_research_ids"
            ]
            for predecessor_id in predecessors:
                if predecessor_id in selected_ids:
                    adjacency[research_id].add(predecessor_id)
                    adjacency[predecessor_id].add(research_id)
        components: list[list[str]] = []
        remaining = set(selected_ids)
        while remaining:
            root = min(remaining)
            stack = [root]
            component: set[str] = set()
            while stack:
                current = stack.pop()
                if current in component:
                    continue
                component.add(current)
                stack.extend(sorted(adjacency[current].difference(component)))
            remaining.difference_update(component)
            components.append(sorted(component))
        payload = {
            "schema_version": 1,
            "plan_id": plan["plan_id"],
            "packager": "mechanical-supervision-interface-projection",
            "components": [
                {
                    "component_key": "supervised-interface-"
                    + sha256_json(component_ids)[:16],
                    "entries": [
                        {
                            "research_id": research_id,
                            "statement_interface": prepared[research_id][
                                "statement_interface"
                            ],
                        }
                        for research_id in component_ids
                    ],
                }
                for component_ids in components
            ],
            "blocked_entries": [],
        }
        try:
            package = self.seal_package(payload)
        except (KeyError, OSError, ValueError) as exc:
            return {
                "state": "mechanical_seal_blocked",
                "package": None,
                "unavailable": [],
                "reason": str(exc),
                "source_bindings_sha256": sha256_json(
                    [
                        binding
                        for item in prepared.values()
                        for binding in item["source_bindings"]
                    ]
                ),
            }
        return {
            "state": "mechanically_sealed",
            "package": package,
            "unavailable": [],
            "source_bindings_sha256": sha256_json(
                [
                    binding
                    for item in prepared.values()
                    for binding in item["source_bindings"]
                ]
            ),
        }

    def _validate_grant(self, raw: dict[str, Any]) -> dict[str, Any]:
        path_stem = raw.pop("__path_stem__", None)
        record = _require_exact_fields(
            raw,
            {
                "schema_version",
                "contract_revision",
                "project_id",
                "research_id",
                "research_record_sha256",
                "statement_interface",
                "predecessor_bindings",
                "package_id",
                "package_record_sha256",
                "decision_id",
                "decision_record_sha256",
                "capsule_sha256",
                "component_id",
                "reviewer",
                "gateway",
                "certified_at",
                "grant_id",
                "record_sha256",
            },
            label="Research certification grant",
        )
        grant_id = _require_prefixed_sha_id(
            record["grant_id"], prefix="fact-grant-", label="Fact grant id"
        )
        if path_stem is not None and path_stem != grant_id:
            raise ValueError("Research certification grant path/id mismatch")
        research_id = validate_memory_id(record["research_id"])
        research = self.lifecycle._research_record(research_id)
        if research["record_sha256"] != record["research_record_sha256"]:
            raise ValueError("Research certification grant record binding drifted")
        record["statement_interface"] = self._validate_statement_interface(
            record["statement_interface"], research=research
        )
        bindings = record["predecessor_bindings"]
        if not isinstance(bindings, list) or len(bindings) > FACT_ALPHA_MAX_INTERFACE_ITEMS:
            raise ValueError("Research certification predecessor bindings are invalid")
        seen: set[str] = set()
        for index, binding in enumerate(bindings, 1):
            _require_exact_fields(
                binding,
                {
                    "predecessor_research_id",
                    "predecessor_grant_id",
                    "predecessor_grant_record_sha256",
                },
                label=f"Research certification predecessor binding {index}",
            )
            predecessor_id = validate_memory_id(
                binding["predecessor_research_id"]
            )
            if predecessor_id in seen:
                raise ValueError("duplicate certification predecessor binding")
            seen.add(predecessor_id)
            _require_prefixed_sha_id(
                binding["predecessor_grant_id"],
                prefix="fact-grant-",
                label="predecessor grant id",
            )
            _require_sha256(
                binding["predecessor_grant_record_sha256"],
                label="predecessor grant record hash",
            )
        if sorted(seen) != record["statement_interface"][
            "certified_predecessor_research_ids"
        ]:
            raise ValueError(
                "grant predecessor bindings differ from the statement interface"
            )
        for key, prefix in (
            ("package_id", "fact-package-"),
            ("decision_id", "fact-decision-"),
            ("component_id", "fact-component-"),
        ):
            _require_prefixed_sha_id(record[key], prefix=prefix, label=key)
        for key in (
            "research_record_sha256",
            "package_record_sha256",
            "decision_record_sha256",
            "capsule_sha256",
        ):
            _require_sha256(record[key], label=key)
        if (
            record["schema_version"] != 1
            or record["contract_revision"]
            != FACT_CERTIFICATION_GRANT_REVISION
            or record["project_id"] != self.store.project_id()
        ):
            raise ValueError("Research certification grant identity is invalid")
        _require_text(record["reviewer"], label="Fact verifier")
        _require_text(record["gateway"], label="Fact gateway")
        _require_text(record["certified_at"], label="Fact certification timestamp")
        semantic = {
            key: value
            for key, value in record.items()
            if key not in {"grant_id", "record_sha256"}
        }
        if grant_id != "fact-grant-" + sha256_json(semantic):
            raise ValueError("Research certification grant identity drifted")
        if record["record_sha256"] != _record_hash(record):
            raise ValueError("Research certification grant record hash drifted")
        return record

    def _validate_acceptance(self, raw: dict[str, Any]) -> dict[str, Any]:
        path_stem = raw.pop("__path_stem__", None)
        record = _require_exact_fields(
            raw,
            {
                "schema_version",
                "contract_revision",
                "project_id",
                "package_id",
                "package_record_sha256",
                "decision_id",
                "decision_record_sha256",
                "accepted_component_ids",
                "grant_ids",
                "reviewer",
                "gateway",
                "accepted_at",
                "acceptance_id",
                "record_sha256",
            },
            label="Research certification acceptance",
        )
        acceptance_id = _require_prefixed_sha_id(
            record["acceptance_id"],
            prefix="fact-acceptance-",
            label="Fact acceptance id",
        )
        if path_stem is not None and path_stem != record["decision_id"]:
            raise ValueError("Research certification acceptance path/decision mismatch")
        for key, prefix in (
            ("package_id", "fact-package-"),
            ("decision_id", "fact-decision-"),
        ):
            _require_prefixed_sha_id(record[key], prefix=prefix, label=key)
        for key in ("package_record_sha256", "decision_record_sha256"):
            _require_sha256(record[key], label=key)
        components = _require_text_list(
            record["accepted_component_ids"],
            label="accepted component ids",
            maximum=FACT_ALPHA_MAX_COMPONENTS,
            allow_empty=False,
        )
        for component_id in components:
            _require_prefixed_sha_id(
                component_id,
                prefix="fact-component-",
                label="Fact component id",
            )
        grant_ids = _require_text_list(
            record["grant_ids"],
            label="accepted grant ids",
            maximum=FACT_ALPHA_MAX_MARKS_PER_PLAN,
            allow_empty=False,
        )
        for grant_id in grant_ids:
            _require_prefixed_sha_id(
                grant_id, prefix="fact-grant-", label="Fact grant id"
            )
        if (
            record["schema_version"] != 1
            or record["contract_revision"]
            != FACT_CERTIFICATION_ACCEPTANCE_REVISION
            or record["project_id"] != self.store.project_id()
        ):
            raise ValueError("Research certification acceptance identity is invalid")
        for key in ("reviewer", "gateway", "accepted_at"):
            _require_text(record[key], label=f"Fact acceptance {key}")
        semantic = {
            key: value
            for key, value in record.items()
            if key not in {"acceptance_id", "record_sha256"}
        }
        if acceptance_id != "fact-acceptance-" + sha256_json(semantic):
            raise ValueError("Research certification acceptance identity drifted")
        if record["record_sha256"] != _record_hash(record):
            raise ValueError("Research certification acceptance record hash drifted")

        decision = self.decision(record["decision_id"])
        package = self.package(record["package_id"])
        if (
            decision["package_id"] != package["package_id"]
            or record["package_record_sha256"] != package["record_sha256"]
            or record["decision_record_sha256"] != decision["record_sha256"]
            or record["reviewer"] != decision["reviewer"]
            or record["accepted_at"] != decision["reviewed_at"]
        ):
            raise ValueError("Research certification acceptance authority drifted")
        expected_components = {
            item["component_id"]
            for item in decision["component_checks"]
            if item["verdict"] == "correct"
        }
        if set(components) != expected_components or len(components) != len(
            expected_components
        ):
            raise ValueError(
                "Research certification acceptance does not exactly select "
                "the correct decision components"
            )
        package_components = {
            component["component_id"]: component
            for component in package["components"]
        }
        expected_entries = {
            entry["research_id"]: (component_id, entry)
            for component_id in expected_components
            for entry in package_components[component_id]["entries"]
        }
        seen_research: set[str] = set()
        acceptance_grants: dict[str, dict[str, Any]] = {}
        for grant_id in grant_ids:
            path = self.grants_dir / f"{grant_id}.json"
            if path.is_symlink() or not path.is_file():
                raise ValueError(
                    "Research certification acceptance references a missing grant"
                )
            grant_raw = self.store._read_json(path)
            grant_raw["__path_stem__"] = path.stem
            grant = self._validate_grant(grant_raw)
            expected = expected_entries.get(grant["research_id"])
            if expected is None or grant["research_id"] in seen_research:
                raise ValueError(
                    "Research certification acceptance grant coverage is invalid"
                )
            seen_research.add(grant["research_id"])
            acceptance_grants[grant["research_id"]] = grant
            component_id, entry = expected
            if (
                grant["component_id"] != component_id
                or grant["research_record_sha256"]
                != entry["research_record_sha256"]
                or grant["statement_interface"] != entry["statement_interface"]
                or grant["package_id"] != package["package_id"]
                or grant["package_record_sha256"] != package["record_sha256"]
                or grant["decision_id"] != decision["decision_id"]
                or grant["decision_record_sha256"] != decision["record_sha256"]
                or grant["capsule_sha256"] != decision["capsule_sha256"]
                or grant["reviewer"] != decision["reviewer"]
                or grant["gateway"] != record["gateway"]
                or grant["certified_at"] != decision["reviewed_at"]
            ):
                raise ValueError(
                    "Research certification acceptance/grant binding drifted"
                )
        if seen_research != set(expected_entries):
            raise ValueError(
                "Research certification acceptance does not cover every Research "
                "entry in its accepted components"
            )
        for research_id, grant in acceptance_grants.items():
            _component_id, entry = expected_entries[research_id]
            frozen_external = {
                binding["predecessor_research_id"]: binding
                for binding in entry["external_predecessor_bindings"]
            }
            for binding in grant["predecessor_bindings"]:
                predecessor_id = binding["predecessor_research_id"]
                predecessor = acceptance_grants.get(predecessor_id)
                if predecessor is not None:
                    expected_grant_id = predecessor["grant_id"]
                    expected_grant_hash = predecessor["record_sha256"]
                else:
                    frozen = frozen_external.get(predecessor_id)
                    if frozen is None:
                        raise ValueError(
                            "Research certification grant has an unreviewed "
                            "predecessor"
                        )
                    expected_grant_id = frozen["predecessor_grant_id"]
                    expected_grant_hash = frozen[
                        "predecessor_grant_record_sha256"
                    ]
                if (
                    binding["predecessor_grant_id"] != expected_grant_id
                    or binding["predecessor_grant_record_sha256"]
                    != expected_grant_hash
                ):
                    raise ValueError(
                        "Research certification grant predecessor differs from "
                        "the verified package"
                    )
        return record

    def _accepted_grants(self) -> dict[str, dict[str, Any]]:
        grants: dict[str, dict[str, Any]] = {}
        for raw in self._regular_json_records(
            self.grants_dir, label="Research certification grants"
        ):
            grant = self._validate_grant(raw)
            grants[grant["grant_id"]] = grant
        accepted_ids: set[str] = set()
        for raw in self._regular_json_records(
            self.acceptances_dir, label="Research certification acceptances"
        ):
            acceptance = self._validate_acceptance(raw)
            repeated = accepted_ids.intersection(acceptance["grant_ids"])
            if repeated:
                raise ValueError(
                    "Research certification grants appear in multiple acceptances: "
                    + ", ".join(sorted(repeated))
                )
            accepted_ids.update(acceptance["grant_ids"])
        missing = accepted_ids.difference(grants)
        if missing:
            raise ValueError(
                "Fact acceptance references missing grants: "
                + ", ".join(sorted(missing))
            )
        accepted = {
            grant_id: grants[grant_id] for grant_id in sorted(accepted_ids)
        }
        for grant in accepted.values():
            for binding in grant["predecessor_bindings"]:
                predecessor = accepted.get(binding["predecessor_grant_id"])
                if (
                    predecessor is None
                    or predecessor["research_id"]
                    != binding["predecessor_research_id"]
                    or predecessor["record_sha256"]
                    != binding["predecessor_grant_record_sha256"]
                ):
                    raise ValueError(
                        "Research certification predecessor is not an accepted "
                        "exact grant"
                    )
        return accepted

    def _route_projection(
        self,
        *,
        inspection: Any,
    ) -> tuple[
        dict[str, dict[str, Any]],
        dict[str, dict[str, Any]],
        dict[str, list[str]],
        dict[str, tuple[str, ...]],
    ]:
        records = self.lifecycle.research_envelopes(
            _inspection_context=inspection
        )
        (
            bases,
            dispositions,
            route_staleness,
            _workgroups,
            _work_keys,
        ) = self.lifecycle._frontier_structural_state_for_inspection(
            records, inspection
        )
        repair_children = self.lifecycle._frontier_cow_repair_children_index(
            bases=bases,
            route_staleness=route_staleness,
        )
        return bases, dispositions, route_staleness, repair_children

    def _terminal_for(
        self,
        research_id: str,
        *,
        bases: dict[str, dict[str, Any]],
        route_staleness: dict[str, list[str]],
        repair_children: dict[str, tuple[str, ...]],
    ) -> str | None:
        result = self.lifecycle._frontier_cow_terminal_members(
            seed_members=[research_id],
            bases=bases,
            route_staleness=route_staleness,
            repair_children=repair_children,
        )
        return result.get(research_id)

    def _grant_projection(
        self,
        *,
        bases: dict[str, dict[str, Any]],
        route_staleness: dict[str, list[str]],
        repair_children: dict[str, tuple[str, ...]],
    ) -> dict[str, Any]:
        grants = self._accepted_grants()
        by_research: dict[str, list[dict[str, Any]]] = {}
        for grant in grants.values():
            by_research.setdefault(grant["research_id"], []).append(grant)
        latest: dict[str, dict[str, Any]] = {
            research_id: max(
                items,
                key=lambda item: (item["certified_at"], item["grant_id"]),
            )
            for research_id, items in by_research.items()
        }
        states: dict[str, str] = {}
        reasons: dict[str, list[str]] = {}
        visiting: set[str] = set()

        def state(grant_id: str) -> str:
            if grant_id in states:
                return states[grant_id]
            if grant_id in visiting:
                states[grant_id] = "needs_reverification"
                reasons[grant_id] = ["certification_dependency_cycle"]
                return states[grant_id]
            visiting.add(grant_id)
            grant = grants[grant_id]
            local_reasons: list[str] = []
            latest_grant = latest.get(grant["research_id"])
            if latest_grant is None or latest_grant["grant_id"] != grant_id:
                local_reasons.append("newer_certification_grant_exists")
            terminal = self._terminal_for(
                grant["research_id"],
                bases=bases,
                route_staleness=route_staleness,
                repair_children=repair_children,
            )
            if terminal is None:
                local_reasons.append("research_cow_route_is_ambiguous")
            elif terminal != grant["research_id"]:
                local_reasons.append("research_has_a_cow_successor")
            if grant["research_id"] in route_staleness:
                local_reasons.append("research_route_is_invalidated")
            for binding in grant["predecessor_bindings"]:
                predecessor_grant_id = binding["predecessor_grant_id"]
                predecessor = grants.get(predecessor_grant_id)
                if predecessor is None:
                    local_reasons.append("certified_predecessor_grant_is_missing")
                    continue
                if (
                    predecessor["record_sha256"]
                    != binding["predecessor_grant_record_sha256"]
                    or predecessor["research_id"]
                    != binding["predecessor_research_id"]
                ):
                    local_reasons.append("certified_predecessor_binding_drifted")
                    continue
                if state(predecessor_grant_id) != "active":
                    local_reasons.append("certified_predecessor_needs_reverification")
            visiting.discard(grant_id)
            states[grant_id] = (
                "active" if not local_reasons else "needs_reverification"
            )
            reasons[grant_id] = sorted(set(local_reasons))
            return states[grant_id]

        for grant_id in grants:
            state(grant_id)
        active_by_research = {
            research_id: grant
            for research_id, grant in latest.items()
            if states.get(grant["grant_id"]) == "active"
        }
        stale_by_research = {
            research_id: {
                "grant": grant,
                "reasons": reasons.get(grant["grant_id"], []),
            }
            for research_id, grant in latest.items()
            if states.get(grant["grant_id"]) != "active"
        }
        children: dict[str, set[str]] = {
            research_id: set() for research_id in active_by_research
        }
        for research_id, grant in active_by_research.items():
            for binding in grant["predecessor_bindings"]:
                predecessor_id = binding["predecessor_research_id"]
                if predecessor_id in active_by_research:
                    children.setdefault(predecessor_id, set()).add(research_id)
        heads = sorted(
            research_id
            for research_id in active_by_research
            if not children.get(research_id)
        )
        return {
            "grants": grants,
            "active_by_research": active_by_research,
            "stale_by_research": stale_by_research,
            "certified_heads": heads,
        }

    def active_bindings(
        self,
        research_ids: list[str],
        *,
        inspection: Any | None = None,
    ) -> list[dict[str, str]]:
        """Resolve exact active Fact overlays for new Research premises."""

        normalized = sorted(
            validate_memory_id(research_id) for research_id in research_ids
        )
        if len(normalized) != len(set(normalized)):
            raise ValueError("certified Research dependencies contain duplicates")
        if inspection is None:
            from .v5_lifecycle import RoundInspectionContext

            inspection = self.lifecycle._bind_inspection_context(
                RoundInspectionContext(), create=True
            )
        assert inspection is not None
        bases, _dispositions, route_staleness, repair_children = (
            self._route_projection(inspection=inspection)
        )
        projection = self._grant_projection(
            bases=bases,
            route_staleness=route_staleness,
            repair_children=repair_children,
        )
        active = projection["active_by_research"]
        missing = [research_id for research_id in normalized if research_id not in active]
        if missing:
            raise ValueError(
                "Research premises are not actively Fact-certified: "
                + ", ".join(missing)
            )
        return [
            {
                "research_id": research_id,
                "research_record_sha256": active[research_id][
                    "research_record_sha256"
                ],
                "grant_id": active[research_id]["grant_id"],
                "grant_record_sha256": active[research_id]["record_sha256"],
            }
            for research_id in normalized
        ]

    def _validate_package(self, raw: dict[str, Any]) -> dict[str, Any]:
        path_stem = raw.pop("__path_stem__", None)
        record = _require_exact_fields(
            raw,
            {
                "schema_version",
                "contract_revision",
                "project_id",
                "plan_id",
                "plan_record_sha256",
                "packager",
                "components",
                "blocked_entries",
                "truth_effect",
                "package_id",
                "record_sha256",
            },
            label="Fact Candidate package",
        )
        package_id = _require_prefixed_sha_id(
            record["package_id"],
            prefix="fact-package-",
            label="Fact Candidate package id",
        )
        if path_stem is not None and path_stem != record["plan_id"]:
            raise ValueError("Fact Candidate package path/plan mismatch")
        _require_prefixed_sha_id(
            record["plan_id"], prefix="fact-plan-", label="Fact packaging plan id"
        )
        _require_sha256(record["plan_record_sha256"], label="Fact plan record hash")
        _require_text(record["packager"], label="Fact packager")
        plan = self.plan(record["plan_id"])
        if record["plan_record_sha256"] != plan["record_sha256"]:
            raise ValueError("Fact Candidate package plan binding drifted")
        plan_by_research = {
            item["current_research_id"]: item for item in plan["selection"]
        }
        components = record["components"]
        if (
            not isinstance(components, list)
            or len(components) > FACT_ALPHA_MAX_COMPONENTS
        ):
            raise ValueError("Fact Candidate components are invalid")
        seen_components: set[str] = set()
        seen_research: set[str] = set()
        cross_component_dependencies: set[tuple[str, str]] = set()
        component_fields = {
            "component_id",
            "component_key",
            "entries",
            "edges",
        }
        entry_fields = {
            "research_id",
            "research_record_sha256",
            "statement_interface",
            "external_predecessor_bindings",
        }
        edge_fields = {"predecessor_research_id", "research_id"}
        binding_fields = {
            "predecessor_research_id",
            "predecessor_grant_id",
            "predecessor_grant_record_sha256",
        }
        for component_index, component in enumerate(components, 1):
            _require_exact_fields(
                component,
                component_fields,
                label=f"Fact Candidate component {component_index}",
            )
            component_id = _require_prefixed_sha_id(
                component["component_id"],
                prefix="fact-component-",
                label="Fact component id",
            )
            if component_id in seen_components:
                raise ValueError("Fact Candidate repeats a component id")
            seen_components.add(component_id)
            _require_text(component["component_key"], label="Fact component key")
            entries = component["entries"]
            if not isinstance(entries, list) or not entries:
                raise ValueError("Fact Candidate component entries are invalid")
            local_ids: set[str] = set()
            local_entries: dict[str, dict[str, Any]] = {}
            for entry_index, entry in enumerate(entries, 1):
                _require_exact_fields(
                    entry,
                    entry_fields,
                    label=(
                        f"Fact Candidate component {component_index} "
                        f"entry {entry_index}"
                    ),
                )
                research_id = validate_memory_id(entry["research_id"])
                if research_id in seen_research:
                    raise ValueError("Fact Candidate repeats a Research node")
                seen_research.add(research_id)
                local_ids.add(research_id)
                local_entries[research_id] = entry
                research = self.lifecycle._research_record(research_id)
                if research["record_sha256"] != entry["research_record_sha256"]:
                    raise ValueError("Fact Candidate Research hash drifted")
                planned = plan_by_research.get(research_id)
                if (
                    planned is None
                    or planned["eligibility"] != "eligible"
                    or planned["current_research_record_sha256"]
                    != entry["research_record_sha256"]
                ):
                    raise ValueError(
                        "Fact Candidate Research is outside the eligible frozen plan"
                    )
                entry["statement_interface"] = self._validate_statement_interface(
                    entry["statement_interface"], research=research
                )
                bindings = entry["external_predecessor_bindings"]
                if not isinstance(bindings, list):
                    raise ValueError(
                        "Fact Candidate external predecessor bindings are invalid"
                    )
                for binding_index, binding in enumerate(bindings, 1):
                    _require_exact_fields(
                        binding,
                        binding_fields,
                        label=(
                            "Fact Candidate predecessor binding "
                            f"{component_index}.{entry_index}.{binding_index}"
                        ),
                    )
                    validate_memory_id(binding["predecessor_research_id"])
                    _require_prefixed_sha_id(
                        binding["predecessor_grant_id"],
                        prefix="fact-grant-",
                        label="predecessor grant id",
                    )
                    _require_sha256(
                        binding["predecessor_grant_record_sha256"],
                        label="predecessor grant record hash",
                    )
                    grant_path = self.grants_dir / (
                        f"{binding['predecessor_grant_id']}.json"
                    )
                    if grant_path.is_symlink() or not grant_path.is_file():
                        raise ValueError(
                            "Fact Candidate external predecessor grant is missing"
                        )
                    grant_raw = self.store._read_json(grant_path)
                    grant_raw["__path_stem__"] = grant_path.stem
                    grant = self._validate_grant(grant_raw)
                    if (
                        grant["research_id"]
                        != binding["predecessor_research_id"]
                        or grant["record_sha256"]
                        != binding["predecessor_grant_record_sha256"]
                    ):
                        raise ValueError(
                            "Fact Candidate external predecessor binding drifted"
                        )
            edges = component["edges"]
            if not isinstance(edges, list):
                raise ValueError("Fact Candidate component edges are invalid")
            normalized_edges: set[tuple[str, str]] = set()
            for edge_index, edge in enumerate(edges, 1):
                _require_exact_fields(
                    edge,
                    edge_fields,
                    label=f"Fact Candidate edge {component_index}.{edge_index}",
                )
                predecessor_id = validate_memory_id(
                    edge["predecessor_research_id"]
                )
                research_id = validate_memory_id(edge["research_id"])
                if predecessor_id not in local_ids or research_id not in local_ids:
                    raise ValueError("Fact Candidate internal edge crosses components")
                normalized_edges.add((predecessor_id, research_id))
            if len(normalized_edges) != len(edges):
                raise ValueError("Fact Candidate component repeats an edge")
            expected_internal_edges: set[tuple[str, str]] = set()
            for research_id, entry in local_entries.items():
                predecessors = set(
                    entry["statement_interface"][
                        "certified_predecessor_research_ids"
                    ]
                )
                expected_internal_edges.update(
                    (predecessor_id, research_id)
                    for predecessor_id in predecessors
                    if predecessor_id in local_ids
                )
                expected_external = predecessors.difference(local_ids)
                bindings = entry["external_predecessor_bindings"]
                binding_ids = [
                    binding["predecessor_research_id"] for binding in bindings
                ]
                if (
                    set(binding_ids) != expected_external
                    or len(binding_ids) != len(expected_external)
                ):
                    raise ValueError(
                        "Fact Candidate external predecessor bindings differ "
                        "from the statement interface"
                    )
                cross_component_dependencies.update(
                    (predecessor_id, research_id)
                    for predecessor_id in expected_external
                )
            if normalized_edges != expected_internal_edges:
                raise ValueError(
                    "Fact Candidate internal edges differ from statement interfaces"
                )
            component_semantic = {
                "component_key": component["component_key"],
                "entries": component["entries"],
                "edges": component["edges"],
            }
            if component_id != "fact-component-" + sha256_json(component_semantic):
                raise ValueError("Fact Candidate component identity drifted")
        blocked_entries = record["blocked_entries"]
        if not isinstance(blocked_entries, list):
            raise ValueError("Fact Candidate blocked entries are invalid")
        blocked_seen: set[str] = set()
        for index, item in enumerate(blocked_entries, 1):
            _require_exact_fields(
                item,
                {"research_id", "status", "reason"},
                label=f"Fact Candidate blocked entry {index}",
            )
            research_id = validate_memory_id(item["research_id"])
            if research_id in blocked_seen or research_id in seen_research:
                raise ValueError("Fact Candidate repeats a blocked Research node")
            blocked_seen.add(research_id)
            if research_id not in plan_by_research:
                raise ValueError(
                    "Fact Candidate blocked Research is outside the frozen plan"
                )
            if item["status"] not in _BLOCKED_PACKAGING_STATUSES:
                raise ValueError("Fact Candidate blocked status is invalid")
            _require_text(item["reason"], label="Fact Candidate blocked reason")
        if any(
            predecessor_id in seen_research
            for predecessor_id, _research_id in cross_component_dependencies
        ):
            raise ValueError(
                "Fact Candidate certified dependency crosses package components"
            )
        if seen_research.union(blocked_seen) != set(plan_by_research):
            raise ValueError(
                "Fact Candidate package does not exactly classify the frozen plan"
            )
        if (
            record["schema_version"] != 1
            or record["contract_revision"] != FACT_CANDIDATE_PACKAGE_REVISION
            or record["project_id"] != self.store.project_id()
            or record["truth_effect"] != "none"
        ):
            raise ValueError("Fact Candidate package identity is invalid")
        semantic = {
            key: value
            for key, value in record.items()
            if key not in {"package_id", "record_sha256"}
        }
        if package_id != "fact-package-" + sha256_json(semantic):
            raise ValueError("Fact Candidate package identity drifted")
        if record["record_sha256"] != _record_hash(record):
            raise ValueError("Fact Candidate package record hash drifted")
        return record

    def _packages(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for raw in self._regular_json_records(
            self.packages_dir, label="Fact Candidate packages"
        ):
            record = self._validate_package(raw)
            result[record["package_id"]] = record
        return result

    def package(self, package_id: str) -> dict[str, Any]:
        package_id = _require_prefixed_sha_id(
            package_id,
            prefix="fact-package-",
            label="Fact Candidate package id",
        )
        matches = [
            record
            for record in self._packages().values()
            if record["package_id"] == package_id
        ]
        if len(matches) != 1:
            raise KeyError(f"unknown Fact Candidate package: {package_id}")
        return matches[0]

    def _validate_decision(self, raw: dict[str, Any]) -> dict[str, Any]:
        path_stem = raw.pop("__path_stem__", None)
        record = _require_exact_fields(
            raw,
            {
                "schema_version",
                "contract_revision",
                "project_id",
                "package_id",
                "package_record_sha256",
                "capsule_sha256",
                "reviewer",
                "component_checks",
                "overall_notes",
                "reviewed_at",
                "truth_effect",
                "decision_id",
                "record_sha256",
            },
            label="Research certification decision",
        )
        decision_id = _require_prefixed_sha_id(
            record["decision_id"],
            prefix="fact-decision-",
            label="Fact certification decision id",
        )
        if path_stem is not None and path_stem != record["package_id"]:
            raise ValueError("Fact certification decision path/package mismatch")
        _require_prefixed_sha_id(
            record["package_id"],
            prefix="fact-package-",
            label="Fact Candidate package id",
        )
        _require_sha256(record["package_record_sha256"], label="package record hash")
        _require_sha256(record["capsule_sha256"], label="verifier capsule hash")
        _require_text(record["reviewer"], label="Fact verifier")
        _require_text(record["overall_notes"], label="Fact verifier overall notes")
        _require_text(record["reviewed_at"], label="Fact verifier timestamp")
        if not isinstance(record["component_checks"], list):
            raise ValueError("Fact certification component checks are invalid")
        for component in record["component_checks"]:
            self._validate_component_check_shape(component)
        if (
            record["schema_version"] != 1
            or record["contract_revision"]
            != FACT_CERTIFICATION_DECISION_REVISION
            or record["project_id"] != self.store.project_id()
            or record["truth_effect"] != "certification_evidence_only"
        ):
            raise ValueError("Fact certification decision identity is invalid")
        semantic = {
            key: value
            for key, value in record.items()
            if key not in {"decision_id", "record_sha256"}
        }
        if decision_id != "fact-decision-" + sha256_json(semantic):
            raise ValueError("Fact certification decision identity drifted")
        if record["record_sha256"] != _record_hash(record):
            raise ValueError("Fact certification decision record hash drifted")
        package = self.package(record["package_id"])
        capsule = self.verifier_capsule(package["package_id"])
        if (
            record["package_record_sha256"] != package["record_sha256"]
            or record["capsule_sha256"] != capsule["capsule_sha256"]
        ):
            raise ValueError("Fact certification decision authority binding drifted")
        components_by_id = {
            component["component_id"]: component
            for component in package["components"]
        }
        if (
            {item["component_id"] for item in record["component_checks"]}
            != set(components_by_id)
            or len(record["component_checks"]) != len(components_by_id)
        ):
            raise ValueError(
                "Fact certification decision does not cover package components"
            )
        normalized_checks = [
            self._normalize_component_check(
                item,
                package_component=components_by_id[item["component_id"]],
            )
            for item in record["component_checks"]
        ]
        if sorted(
            normalized_checks, key=lambda item: item["component_id"]
        ) != record["component_checks"]:
            raise ValueError("Fact certification decision normalization drifted")
        plan = self.plan(package["plan_id"])
        minor_context = plan["minor_repair_context"]
        if (
            minor_context is not None
            and record["reviewer"] != minor_context["same_verifier"]
        ):
            raise ValueError("Fact minor-repair verifier continuity drifted")
        return record

    def _decisions(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for raw in self._regular_json_records(
            self.decisions_dir, label="Research certification decisions"
        ):
            record = self._validate_decision(raw)
            result[record["package_id"]] = record
        return result

    def decision(self, decision_id: str) -> dict[str, Any]:
        decision_id = _require_prefixed_sha_id(
            decision_id,
            prefix="fact-decision-",
            label="Fact certification decision id",
        )
        matches = [
            record
            for record in self._decisions().values()
            if record["decision_id"] == decision_id
        ]
        if len(matches) != 1:
            raise KeyError(f"unknown Fact certification decision: {decision_id}")
        return matches[0]

    def _active_mark_records(self) -> list[dict[str, Any]]:
        marks = self._marks()
        dispositions = self._dispositions()
        active: list[dict[str, Any]] = []
        for mark_id, mark in marks.items():
            disposition = dispositions.get(mark_id)
            status = disposition["status"] if disposition is not None else "active"
            if status == "active":
                active.append(mark)
        return active

    def _legacy_root_bootstrap_advisory(
        self,
        *,
        bases: dict[str, dict[str, Any]],
        route_staleness: dict[str, list[str]],
        repair_children: dict[str, tuple[str, ...]],
        inspection: Any,
        active_mark_count: int,
        accepted_grant_count: int,
        limit: int,
    ) -> dict[str, Any] | None:
        """Suggest exact old Fact roots only while the alpha overlay is empty.

        This projection is deliberately advisory.  It recognizes a legacy
        Fact only through an exact ``candidate_fact`` artifact SHA on one
        constructive, non-adverse worker result.  Synthesis reuse and prose
        similarity do not create a mapping or any authority effect.
        """

        if active_mark_count or accepted_grant_count:
            return None

        roots = [
            fact
            for fact in self.store.facts(
                _inspection_context=inspection
            ).values()
            if not fact.predecessors
        ]
        roots.sort(key=lambda fact: fact.fact_id)
        production_by_fact_sha: dict[str, list[str]] = {}
        for research_id, research in bases.items():
            metadata = research.get("metadata")
            if not isinstance(metadata, dict):
                continue
            provenance = metadata.get("assignment_provenance")
            if (
                not isinstance(provenance, dict)
                or provenance.get("adverse_assignment") is not False
                or metadata.get("worker_outcome")
                not in {"proof", "evidence", "insight"}
            ):
                continue
            artifacts = metadata.get("artifacts")
            if not isinstance(artifacts, list):
                continue
            for artifact in artifacts:
                if (
                    isinstance(artifact, dict)
                    and artifact.get("role") == "candidate_fact"
                    and isinstance(artifact.get("sha256"), str)
                    and SHA256_RE.fullmatch(artifact["sha256"]) is not None
                ):
                    production_by_fact_sha.setdefault(
                        artifact["sha256"], []
                    ).append(research_id)

        candidates: list[dict[str, Any]] = []
        ambiguous: list[dict[str, Any]] = []
        unsafe: list[dict[str, str]] = []
        for fact in roots:
            try:
                interface = self.store.statement_interface(
                    fact.fact_id,
                    materialize=False,
                    _inspection_context=inspection,
                )
                fact_sha = interface["stored_fact_sha256"]
            except (KeyError, OSError, ValueError) as exc:
                unsafe.append(
                    {"legacy_fact_id": fact.fact_id, "reason": str(exc)}
                )
                continue
            carrier_ids = sorted(
                set(production_by_fact_sha.get(fact_sha, []))
            )
            if len(carrier_ids) != 1:
                if len(carrier_ids) > 1:
                    ambiguous.append(
                        {
                            "legacy_fact_id": fact.fact_id,
                            "production_carrier_ids": carrier_ids,
                        }
                    )
                continue
            carrier_id = carrier_ids[0]
            terminal_id = self._terminal_for(
                carrier_id,
                bases=bases,
                route_staleness=route_staleness,
                repair_children=repair_children,
            )
            current: dict[str, Any] | None = bases[carrier_id]
            coverage: list[dict[str, Any]] = []
            coverage_state = "cow_route_ambiguous"
            if terminal_id is not None and terminal_id in bases:
                current = self.lifecycle._inspection_research_record(
                    terminal_id, inspection
                )
                try:
                    coverage = (
                        self.lifecycle._candidate_supervision_scope_coverage(
                            [current], _inspection_context=inspection
                        )
                    )
                    coverage_states = {
                        item.get("state") for item in coverage
                    }
                    coverage_state = (
                        "settled"
                        if coverage
                        and not coverage_states.intersection(
                            {"missing", "pending", "conflicting", "unsafe"}
                        )
                        else "missing"
                        if not coverage or "missing" in coverage_states
                        else "not_settled"
                    )
                except (KeyError, OSError, ValueError) as exc:
                    coverage_state = "unsafe"
                    unsafe.append(
                        {
                            "legacy_fact_id": fact.fact_id,
                            "reason": str(exc),
                        }
                    )
            suggested_id = terminal_id or carrier_id
            candidates.append(
                {
                    "legacy_fact_id": fact.fact_id,
                    "legacy_fact_statement": fact.statement,
                    "legacy_fact_sha256": fact_sha,
                    "production_carrier_research_id": carrier_id,
                    "suggested_research_id": suggested_id,
                    "suggested_research_record_sha256": current[
                        "record_sha256"
                    ],
                    "claim": current["claim"],
                    "cow_route_state": (
                        "current"
                        if terminal_id == carrier_id
                        else "advanced"
                        if terminal_id is not None
                        else "ambiguous"
                    ),
                    "supervision_state": coverage_state,
                    "supervision_coverage_sha256": sha256_json(coverage),
                    "next_action": "fact-frontier-mark",
                }
            )

        candidates.sort(
            key=lambda item: (
                item["supervision_state"] != "settled",
                item["legacy_fact_id"],
            )
        )
        diagnostic = {
            "ambiguous": ambiguous,
            "unsafe": unsafe,
        }
        return {
            "state": (
                "exact_legacy_roots_available"
                if candidates
                else "no_exact_legacy_root_carrier"
            ),
            "legacy_root_count": len(roots),
            "exact_candidate_count": len(candidates),
            "ambiguous_count": len(ambiguous),
            "unsafe_count": len(unsafe),
            "diagnostic_sha256": sha256_json(diagnostic),
            "candidates": candidates[:limit],
            "shown_count": min(limit, len(candidates)),
            "truth_effect": "none",
            "selection_effect": "none",
        }

    def status(self) -> dict[str, Any]:
        """Return a bounded lifecycle summary without rebuilding Research."""

        marks = self._marks()
        dispositions = self._dispositions()
        active_mark_count = sum(
            1
            for mark_id in marks
            if dispositions.get(mark_id, {}).get("status", "active") == "active"
        )
        accepted_grants = self._accepted_grants()
        decisions = self._decisions()
        accepted_decision_ids = {
            self._validate_acceptance(raw)["decision_id"]
            for raw in self._regular_json_records(
                self.acceptances_dir,
                label="Research certification acceptances",
            )
        }
        gateway_pending_packages = sum(
            1
            for decision in decisions.values()
            if decision["decision_id"] not in accepted_decision_ids
            and any(
                item["verdict"] == "correct"
                for item in decision["component_checks"]
            )
        )
        rejected_packages = sum(
            1
            for decision in decisions.values()
            if all(
                item["verdict"] != "correct"
                for item in decision["component_checks"]
            )
        )
        return {
            "contract_revision": FACT_ALPHA_CONTRACT_REVISION,
            "authority_model": "research_graph_with_fact_certification_overlay",
            "legacy_fact_authority": "read_only_unmapped",
            "counts": {
                "importance_marks": len(marks),
                "active_importance_marks": active_mark_count,
                "packaging_plans": len(self._plans()),
                "candidate_packages": len(self._packages()),
                "verifier_decisions": len(decisions),
                "accepted_research_certifications": len(accepted_grants),
                "gateway_pending_packages": gateway_pending_packages,
                "rejected_packages": rejected_packages,
            },
        }

    def frontier(
        self,
        *,
        limit: int = 32,
        campaign_id: str | None = None,
        diagnostic: bool = False,
    ) -> dict[str, Any]:
        started = time.monotonic()
        if not isinstance(limit, int) or not 1 <= limit <= FACT_ALPHA_MAX_FRONTIER_LIMIT:
            raise ValueError(
                f"Fact frontier limit must be between 1 and {FACT_ALPHA_MAX_FRONTIER_LIMIT}"
            )
        if campaign_id is not None:
            campaign_id = validate_campaign_id(campaign_id)
        from .v5_lifecycle import RoundInspectionContext

        inspection = self.lifecycle._bind_inspection_context(
            RoundInspectionContext(), create=True
        )
        assert inspection is not None
        bases, dispositions, route_staleness, repair_children = (
            self._route_projection(inspection=inspection)
        )
        grant_projection = self._grant_projection(
            bases=bases,
            route_staleness=route_staleness,
            repair_children=repair_children,
        )
        active_grants = grant_projection["active_by_research"]
        stale_grants = grant_projection["stale_by_research"]
        plans = self._plans()
        packages = self._packages()
        decisions = self._decisions()
        package_by_plan = {item["plan_id"]: item for item in packages.values()}
        decision_by_package = decisions
        all_active_marks = self._active_mark_records()
        active_marks = [
            mark
            for mark in all_active_marks
            if campaign_id is None or mark["campaign_id"] == campaign_id
        ]
        in_scope_mark_ids = {mark["mark_id"] for mark in active_marks}
        filtered_marks = [
            mark
            for mark in all_active_marks
            if mark["mark_id"] not in in_scope_mark_ids
        ]
        scope_projection = {
            "requested_campaign_id": campaign_id,
            "global_active_mark_count": len(all_active_marks),
            "in_scope_active_mark_count": len(active_marks),
            "filtered_out_active_mark_count": len(filtered_marks),
            "filtered_out_unbound_mark_count": sum(
                1 for mark in filtered_marks if mark["campaign_id"] is None
            ),
            "note": (
                "Campaign scope excludes unbound shared roots; use the global "
                "Fact frontier to inspect them."
                if campaign_id is not None
                and any(mark["campaign_id"] is None for mark in filtered_marks)
                else None
            ),
        }

        grouped: dict[tuple[str | None, str | None, str | None], list[dict[str, Any]]] = {}
        route_details: dict[str, dict[str, Any]] = {}
        for mark in active_marks:
            marked_id = mark["research_id"]
            terminal = self._terminal_for(
                marked_id,
                bases=bases,
                route_staleness=route_staleness,
                repair_children=repair_children,
            )
            key = (terminal, mark["campaign_id"], mark["target_id"])
            grouped.setdefault(key, []).append(mark)
            route_details[mark["mark_id"]] = {
                "terminal_research_id": terminal,
                "route_invalidated_by": route_staleness.get(marked_id, []),
            }

        entries: list[dict[str, Any]] = []
        for (current_id, group_campaign, target_id), marks in grouped.items():
            marks.sort(key=lambda item: (item["created_at"], item["mark_id"]))
            latest_mark = marks[-1]
            blockers: list[str] = []
            warnings: list[str] = []
            coverage: list[dict[str, Any]] = []
            state = "waiting_for_batch"
            next_action = "plan-fact-packaging"
            research: dict[str, Any] | None = None
            if current_id is None or current_id not in bases:
                blockers.append("research_cow_route_is_ambiguous")
                state = "superseded_or_ambiguous"
                next_action = "main_reconciliation"
            else:
                research = self.lifecycle._inspection_research_record(
                    current_id, inspection
                )
                effective_status = research["status"]
                if current_id in dispositions:
                    effective_status = dispositions[current_id]["metadata"].get(
                        "disposition_status", effective_status
                    )
                if current_id in route_staleness:
                    blockers.append("research_route_is_invalidated")
                if effective_status not in {"open", "supported", "resolved"}:
                    blockers.append("research_status_is_not_certifiable")
                try:
                    coverage = self.lifecycle._candidate_supervision_scope_coverage(
                        [research], _inspection_context=inspection
                    )
                except (KeyError, OSError, ValueError) as exc:
                    blockers.append("research_supervision_projection_is_unsafe")
                    if diagnostic:
                        warnings.append(str(exc))
                coverage_states = {item.get("state") for item in coverage}
                if coverage_states.intersection({"pending", "conflicting", "unsafe"}):
                    blockers.append("research_supervision_is_not_settled")
                elif "missing" in coverage_states:
                    blockers.append("research_supervision_is_missing")
                elif not coverage:
                    warnings.append("manual_or_legacy_research_has_no_round_binding")

                marked_grant_reasons = sorted(
                    {
                        reason
                        for mark in marks
                        for reason in (
                            stale_grants.get(mark["research_id"], {}).get(
                                "reasons", []
                            )
                        )
                    }
                )
                marked_certification_moved = any(
                    mark["research_id"] != current_id
                    and (
                        mark["research_id"] in active_grants
                        or mark["research_id"] in stale_grants
                    )
                    for mark in marks
                )
                if current_id in active_grants:
                    state = "certified"
                    next_action = "none"
                elif current_id in stale_grants:
                    state = "needs_reverification"
                    next_action = "plan-fact-packaging"
                    blockers.extend(stale_grants[current_id]["reasons"])
                elif marked_grant_reasons or marked_certification_moved:
                    state = "needs_reverification"
                    next_action = "plan-fact-packaging"
                    blockers.extend(marked_grant_reasons)
                    if marked_certification_moved:
                        blockers.append("certified_research_has_a_cow_successor")
                else:
                    related_plans = [
                        plan
                        for plan in plans.values()
                        if any(
                            item["current_research_id"] == current_id
                            for item in plan["selection"]
                        )
                    ]
                    related_plans.sort(key=lambda item: item["plan_id"])
                    if related_plans:
                        latest_plan = related_plans[-1]
                        package = package_by_plan.get(latest_plan["plan_id"])
                        if package is None:
                            state = "packaging_or_verifying"
                            next_action = "fact-package-seal"
                        else:
                            decision = decision_by_package.get(package["package_id"])
                            if decision is None:
                                state = "packaging_or_verifying"
                                next_action = "fact-verifier-capsule"
                            else:
                                checked_component = next(
                                    (
                                        check
                                        for check in decision["component_checks"]
                                        if any(
                                            entry["research_id"] == current_id
                                            for component in package["components"]
                                            if component["component_id"]
                                            == check["component_id"]
                                            for entry in component["entries"]
                                        )
                                    ),
                                    None,
                                )
                                if (
                                    checked_component is not None
                                    and checked_component["verdict"] == "correct"
                                ):
                                    state = "packaging_or_verifying"
                                    next_action = "fact-certify"
                                else:
                                    state = "blocked_by_research"
                                    next_action = "research-cow"
                    elif blockers:
                        state = "blocked_by_research"
                        next_action = "research-supervision-or-cow"

            interface_preparation: dict[str, Any] | None = None
            if research is not None and (
                state
                in {
                    "waiting_for_batch",
                    "needs_reverification",
                    "blocked_by_research",
                }
                or (
                    state == "packaging_or_verifying"
                    and next_action == "fact-package-seal"
                )
            ):
                projection = self._supervised_interface_projection(
                    research, coverage
                )
                interface_preparation = {
                    "state": projection["state"],
                    "source_count": projection["source_count"],
                    "diagnostic_sha256": projection["diagnostic_sha256"],
                    "packaging_mode": (
                        "mechanical_on_plan"
                        if projection["state"] == "ready"
                        else "research_cow_or_split"
                        if projection["state"] == "needs_split"
                        else "human_interface_fallback"
                        if projection["state"] == "missing_or_legacy"
                        else "main_reconciliation"
                    ),
                    **(
                        {"rationales": projection["rationales"]}
                        if projection["state"] == "needs_split"
                        else {}
                    ),
                }
                if projection["state"] == "needs_split":
                    blockers.append("supervisor_requires_statement_split")
                    state = "blocked_by_research"
                    next_action = "research-cow-or-split"
                elif projection["state"] in {"invalid", "conflicting"}:
                    warnings.append(
                        "supervised_statement_interface_requires_reconciliation"
                    )

            entry = {
                "mark_ids": [item["mark_id"] for item in marks],
                "marked_research_ids": sorted(
                    {item["research_id"] for item in marks}
                ),
                "current_research_id": current_id,
                "current_research_record_sha256": (
                    research["record_sha256"] if research is not None else None
                ),
                "campaign_id": group_campaign,
                "target_id": target_id,
                "rationale": latest_mark["rationale"],
                "state": state,
                "readiness": (
                    "ready_for_packaging"
                    if state == "waiting_for_batch" and not blockers
                    else "blocked"
                    if blockers
                    else state
                ),
                "blockers": sorted(set(blockers)),
                "warnings": sorted(set(warnings)),
                "next_action": next_action,
                "claim": research["claim"] if research is not None else None,
                "kind": research["kind"] if research is not None else None,
                "supervision_coverage": coverage,
                "interface_preparation": interface_preparation,
                **(
                    {
                        "route_details": {
                            mark_id: route_details[mark_id]
                            for mark_id in [item["mark_id"] for item in marks]
                        }
                    }
                    if diagnostic
                    else {}
                ),
            }
            entries.append(entry)

        entries.sort(
            key=lambda item: (
                item["state"] == "certified",
                item["campaign_id"] or "",
                item["target_id"] or "",
                item["current_research_id"] or "",
            )
        )
        all_ready = [
            item
            for item in entries
            if item["readiness"] == "ready_for_packaging"
        ]
        visible_entries = entries[:limit]
        ready = [
            item
            for item in visible_entries
            if item["readiness"] == "ready_for_packaging"
        ]
        opportunities: dict[tuple[str | None, str | None], list[dict[str, Any]]] = {}
        for item in ready:
            opportunities.setdefault(
                (item["campaign_id"], item["target_id"]), []
            ).append(item)
        batches = [
            {
                "campaign_id": key[0],
                "target_id": key[1],
                "research_ids": [
                    item["current_research_id"] for item in items
                ],
                "mark_ids": [
                    mark_id for item in items for mark_id in item["mark_ids"]
                ],
                "research_count": len(items),
                "selection_sha256": sha256_json(
                    [item["current_research_id"] for item in items]
                ),
                "next_action": "plan-fact-packaging",
            }
            for key, items in sorted(
                opportunities.items(), key=lambda item: ((item[0][0] or ""), (item[0][1] or ""))
            )
        ]
        elapsed_ms = round((time.monotonic() - started) * 1000, 3)
        counts: dict[str, int] = {}
        for entry in entries:
            counts[entry["state"]] = counts.get(entry["state"], 0) + 1
        all_certified_heads = grant_projection["certified_heads"]
        bootstrap = self._legacy_root_bootstrap_advisory(
            bases=bases,
            route_staleness=route_staleness,
            repair_children=repair_children,
            inspection=inspection,
            active_mark_count=len(all_active_marks),
            accepted_grant_count=len(grant_projection["grants"]),
            limit=limit,
        )
        return {
            "schema_version": 1,
            "contract_revision": FACT_ALPHA_CONTRACT_REVISION,
            "project_id": self.store.project_id(),
            "authority_model": "research_graph_with_fact_certification_overlay",
            "legacy_fact_authority": "read_only_unmapped",
            "scope_projection": scope_projection,
            "legacy_root_bootstrap": bootstrap,
            "counts": counts,
            "certified_heads": [
                {
                    "research_id": research_id,
                    "grant_id": active_grants[research_id]["grant_id"],
                    "claim": bases[research_id]["claim"],
                }
                for research_id in all_certified_heads[:limit]
            ],
            "certified_head_count": len(all_certified_heads),
            "certified_head_ids_sha256": sha256_json(all_certified_heads),
            "batch_opportunities": batches,
            "batch_opportunity_count": len(
                {
                    (item["campaign_id"], item["target_id"])
                    for item in all_ready
                }
            ),
            "ready_for_packaging_count": len(all_ready),
            "ready_research_ids_sha256": sha256_json(
                [item["current_research_id"] for item in all_ready]
            ),
            "entries": visible_entries,
            "entry_count": len(entries),
            "shown_count": min(limit, len(entries)),
            "performance": {
                "elapsed_ms": elapsed_ms,
                "research_envelopes_scanned": len(bases),
                "active_marks_scanned": len(all_active_marks),
                "in_scope_active_marks": len(active_marks),
                "legacy_roots_scanned": (
                    bootstrap["legacy_root_count"]
                    if bootstrap is not None
                    else 0
                ),
                "accepted_grants_scanned": len(grant_projection["grants"]),
            },
        }

    def plan_packaging(
        self,
        mark_ids: list[str],
        *,
        minor_repair_decision_id: str | None = None,
    ) -> dict[str, Any]:
        if (
            not isinstance(mark_ids, list)
            or not mark_ids
            or len(mark_ids) > FACT_ALPHA_MAX_MARKS_PER_PLAN
        ):
            raise ValueError(
                f"Fact packaging requires 1-{FACT_ALPHA_MAX_MARKS_PER_PLAN} marks"
            )
        mark_ids = sorted(set(mark_ids))
        if len(mark_ids) == 0:
            raise ValueError("Fact packaging marks cannot be empty")
        marks = self._marks()
        dispositions = self._dispositions()
        selected_marks: list[dict[str, Any]] = []
        for mark_id in mark_ids:
            _require_prefixed_sha_id(
                mark_id, prefix="fact-mark-", label="Fact frontier mark id"
            )
            mark = marks.get(mark_id)
            if mark is None:
                raise KeyError(f"unknown Fact frontier mark: {mark_id}")
            disposition = dispositions.get(mark_id)
            if disposition is not None and disposition["status"] != "active":
                raise ValueError(f"Fact frontier mark is {disposition['status']}: {mark_id}")
            selected_marks.append(mark)

        minor_context: dict[str, Any] | None = None
        minor_original_ids: set[str] = set()
        minor_affected_ids: set[str] = set()
        prior_decision: dict[str, Any] | None = None
        if minor_repair_decision_id is not None:
            prior_decision = self.decision(minor_repair_decision_id)
            prior_package = self.package(prior_decision["package_id"])
            minor_checks = [
                item
                for item in prior_decision["component_checks"]
                if item["verdict"] == "minor_repair"
            ]
            if not minor_checks:
                raise ValueError(
                    "Fact minor-repair planning requires a minor_repair decision"
                )
            component_ids = {item["component_id"] for item in minor_checks}
            minor_components = [
                component
                for component in prior_package["components"]
                if component["component_id"] in component_ids
            ]
            minor_original_ids = {
                entry["research_id"]
                for component in minor_components
                for entry in component["entries"]
            }
            minor_affected_ids = {
                research_id
                for check in minor_checks
                for finding in check["findings"]
                for research_id in finding["research_ids"]
            }
            if not minor_affected_ids:
                raise ValueError(
                    "Fact minor-repair decision lacks affected Research nodes"
                )
            marked_original_ids = {item["research_id"] for item in selected_marks}
            if marked_original_ids != minor_original_ids:
                raise ValueError(
                    "Fact minor-repair batch must recheck the complete affected component"
                )

        from .v5_lifecycle import RoundInspectionContext

        inspection = self.lifecycle._bind_inspection_context(
            RoundInspectionContext(), create=True
        )
        assert inspection is not None
        bases, _dispositions, route_staleness, repair_children = (
            self._route_projection(inspection=inspection)
        )
        grouped: dict[
            tuple[str | None, str | None, str | None], list[dict[str, Any]]
        ] = {}
        for mark in selected_marks:
            terminal = self._terminal_for(
                mark["research_id"],
                bases=bases,
                route_staleness=route_staleness,
                repair_children=repair_children,
            )
            grouped.setdefault(
                (terminal, mark["campaign_id"], mark["target_id"]), []
            ).append(mark)

        selection: list[dict[str, Any]] = []
        replacement_map: list[dict[str, str]] = []
        for (current_id, campaign_id, target_id), group_marks in sorted(
            grouped.items(),
            key=lambda item: (
                item[0][1] or "",
                item[0][2] or "",
                item[0][0] or "",
            ),
        ):
            group_marks.sort(
                key=lambda item: (item["created_at"], item["mark_id"])
            )
            blockers: list[str] = []
            warnings: list[str] = []
            coverage: list[dict[str, Any]] = []
            if current_id is None or current_id not in bases:
                blockers.append("research_cow_route_is_ambiguous")
                marked = group_marks[-1]
                current_id = marked["research_id"]
                current_record_hash = marked["research_record_sha256"]
            else:
                current = self.lifecycle._inspection_research_record(
                    current_id, inspection
                )
                current_record_hash = current["record_sha256"]
                if current_id in route_staleness:
                    blockers.append("research_route_is_invalidated")
                try:
                    coverage = self.lifecycle._candidate_supervision_scope_coverage(
                        [current], _inspection_context=inspection
                    )
                except (KeyError, OSError, ValueError) as exc:
                    blockers.append("research_supervision_projection_is_unsafe")
                    warnings.append(str(exc))
                states = {item.get("state") for item in coverage}
                if states.intersection({"pending", "conflicting", "unsafe"}):
                    blockers.append("research_supervision_is_not_settled")
                elif "missing" in states:
                    blockers.append("research_supervision_is_missing")
                elif not coverage:
                    warnings.append("manual_or_legacy_research_has_no_round_binding")
            if minor_repair_decision_id is not None:
                if len({item["research_id"] for item in group_marks}) != 1:
                    blockers.append("minor_repair_cow_route_is_not_one_to_one")
                marked_original_id = group_marks[-1]["research_id"]
                if (
                    marked_original_id in minor_affected_ids
                    and current_id == marked_original_id
                ):
                    blockers.append("minor_repair_affected_node_lacks_cow_successor")
                # This lane deliberately replaces ordinary Research
                # supervision only for the complete verifier-defined minor
                # component.  Structural/COW ambiguity remains blocking.
                bypassed = {
                    "research_supervision_is_missing",
                    "research_supervision_is_not_settled",
                }
                removed = sorted(set(blockers).intersection(bypassed))
                blockers = [item for item in blockers if item not in bypassed]
                if removed:
                    warnings.append(
                        "same_verifier_minor_repair_lane_replaces_ordinary_supervision"
                    )
                replacement_map.append(
                    {
                        "prior_research_id": marked_original_id,
                        "current_research_id": current_id,
                    }
                )
            latest = group_marks[-1]
            selection.append(
                {
                    "mark_ids": [item["mark_id"] for item in group_marks],
                    "mark_record_sha256s": [
                        item["record_sha256"] for item in group_marks
                    ],
                    "marked_research_id": latest["research_id"],
                    "marked_research_record_sha256": latest[
                        "research_record_sha256"
                    ],
                    "current_research_id": current_id,
                    "current_research_record_sha256": current_record_hash,
                    "research_relpath": (
                        self.lifecycle._research_path(current_id)
                        .relative_to(self.store.root)
                        .as_posix()
                    ),
                    "campaign_id": campaign_id,
                    "target_id": target_id,
                    "eligibility": "blocked" if blockers else "eligible",
                    "blockers": sorted(set(blockers)),
                    "warnings": sorted(set(warnings)),
                    "supervision_coverage": coverage,
                }
            )
        if prior_decision is not None:
            prior_package = self.package(prior_decision["package_id"])
            minor_context = {
                "prior_decision_id": prior_decision["decision_id"],
                "prior_decision_record_sha256": prior_decision[
                    "record_sha256"
                ],
                "prior_package_id": prior_package["package_id"],
                "prior_package_record_sha256": prior_package[
                    "record_sha256"
                ],
                "component_ids": sorted(
                    item["component_id"]
                    for item in prior_decision["component_checks"]
                    if item["verdict"] == "minor_repair"
                ),
                "same_verifier": prior_decision["reviewer"],
                "affected_research_ids": sorted(minor_affected_ids),
                "complete_recheck_research_ids": sorted(minor_original_ids),
                "replacement_map": sorted(
                    replacement_map,
                    key=lambda item: item["prior_research_id"],
                ),
            }
        semantic = {
            "schema_version": 1,
            "contract_revision": FACT_PACKAGING_PLAN_REVISION,
            "project_id": self.store.project_id(),
            "selection": selection,
            "selection_sha256": sha256_json(selection),
            "planned_by": "main",
            "minor_repair_context": minor_context,
            "truth_effect": "none",
        }
        plan_id = "fact-plan-" + sha256_json(semantic)
        record_without_hash = {**semantic, "plan_id": plan_id}
        record = {
            **record_without_hash,
            "record_sha256": sha256_json(record_without_hash),
        }
        with self.store.v5_mutation_lock(command="plan-fact-packaging"):
            self._ensure_storage()
            path = self.plans_dir / f"{plan_id}.json"
            self.store._write_json_once(path, record)
        mechanical = self._mechanical_package_from_supervision(record)
        package = mechanical.get("package")
        return {
            **record,
            "mechanical_package_state": mechanical["state"],
            "mechanical_package_id": (
                package["package_id"] if package is not None else None
            ),
            "mechanical_package_record_sha256": (
                package["record_sha256"] if package is not None else None
            ),
            "interface_source_bindings_sha256": mechanical[
                "source_bindings_sha256"
            ],
            "interface_preparation_unavailable": mechanical.get(
                "unavailable", []
            ),
            "next_action": (
                "fact-verifier-capsule"
                if package is not None
                else "research-cow-or-split"
                if mechanical["state"] == "research_split_required"
                else "fact-package-seal"
            ),
        }

    @staticmethod
    def _topological_order(
        research_ids: list[str], edges: list[tuple[str, str]]
    ) -> list[str]:
        predecessors = {research_id: set() for research_id in research_ids}
        children = {research_id: set() for research_id in research_ids}
        for predecessor, child in edges:
            predecessors[child].add(predecessor)
            children[predecessor].add(child)
        ready = sorted(
            research_id
            for research_id, values in predecessors.items()
            if not values
        )
        order: list[str] = []
        while ready:
            current = ready.pop(0)
            order.append(current)
            for child in sorted(children[current]):
                predecessors[child].discard(current)
                if not predecessors[child] and child not in order and child not in ready:
                    ready.append(child)
                    ready.sort()
        if len(order) != len(research_ids):
            raise ValueError("Fact Candidate component dependency graph has a cycle")
        return order

    def seal_package(self, payload: dict[str, Any]) -> dict[str, Any]:
        payload = _require_exact_fields(
            payload,
            {"schema_version", "plan_id", "packager", "components", "blocked_entries"},
            label="Fact Candidate package input",
        )
        if payload["schema_version"] != 1:
            raise ValueError("Fact Candidate package input schema_version must be 1")
        plan = self.plan(payload["plan_id"])
        packager = _require_text(payload["packager"], label="Fact packager")
        components_input = payload["components"]
        blocked_input = payload["blocked_entries"]
        if (
            not isinstance(components_input, list)
            or len(components_input) > FACT_ALPHA_MAX_COMPONENTS
            or not isinstance(blocked_input, list)
        ):
            raise ValueError("Fact Candidate package input lists are invalid")
        plan_by_research = {
            item["current_research_id"]: item for item in plan["selection"]
        }
        selected_ids = set(plan_by_research)
        # Reuse the complete derived projection so an older/superseded grant
        # cannot become a package predecessor merely because its file exists.
        from .v5_lifecycle import RoundInspectionContext

        inspection = self.lifecycle._bind_inspection_context(
            RoundInspectionContext(), create=True
        )
        assert inspection is not None
        bases, _dispositions, route_staleness, repair_children = (
            self._route_projection(inspection=inspection)
        )
        grant_projection = self._grant_projection(
            bases=bases,
            route_staleness=route_staleness,
            repair_children=repair_children,
        )
        active_external = grant_projection["active_by_research"]

        seen_research: set[str] = set()
        components: list[dict[str, Any]] = []
        for component_index, raw_component in enumerate(components_input, 1):
            component = _require_exact_fields(
                raw_component,
                {"component_key", "entries"},
                label=f"Fact Candidate component input {component_index}",
            )
            component_key = _require_text(
                component["component_key"], label="Fact Candidate component key"
            )
            raw_entries = component["entries"]
            if not isinstance(raw_entries, list) or not raw_entries:
                raise ValueError("Fact Candidate component entries cannot be empty")
            component_ids: set[str] = set()
            prepared: dict[str, dict[str, Any]] = {}
            for entry_index, raw_entry in enumerate(raw_entries, 1):
                entry = _require_exact_fields(
                    raw_entry,
                    {"research_id", "statement_interface"},
                    label=(
                        f"Fact Candidate component input {component_index} "
                        f"entry {entry_index}"
                    ),
                )
                research_id = validate_memory_id(entry["research_id"])
                if research_id not in selected_ids:
                    raise ValueError("Fact Candidate entry is outside the frozen plan")
                if research_id in seen_research:
                    raise ValueError("Fact Candidate repeats a Research node")
                seen_research.add(research_id)
                component_ids.add(research_id)
                plan_item = plan_by_research[research_id]
                if plan_item["eligibility"] != "eligible":
                    raise ValueError("blocked Fact packaging selection cannot be certified")
                research = self.lifecycle._research_record(research_id)
                if research["record_sha256"] != plan_item[
                    "current_research_record_sha256"
                ]:
                    raise ValueError("Fact Candidate Research changed after planning")
                interface = self._validate_statement_interface(
                    entry["statement_interface"], research=research
                )
                prepared[research_id] = {
                    "research_id": research_id,
                    "research_record_sha256": research["record_sha256"],
                    "statement_interface": interface,
                    "external_predecessor_bindings": [],
                }
            edges: list[tuple[str, str]] = []
            for research_id, entry in prepared.items():
                for predecessor_id in entry["statement_interface"][
                    "certified_predecessor_research_ids"
                ]:
                    if predecessor_id in component_ids:
                        edges.append((predecessor_id, research_id))
                        continue
                    if predecessor_id in selected_ids:
                        raise ValueError(
                            "Fact Candidate dependency crosses package components"
                        )
                    grant = active_external.get(predecessor_id)
                    if grant is None:
                        raise ValueError(
                            "Fact Candidate predecessor is neither in the component "
                            "nor actively certified: "
                            + predecessor_id
                        )
                    entry["external_predecessor_bindings"].append(
                        {
                            "predecessor_research_id": predecessor_id,
                            "predecessor_grant_id": grant["grant_id"],
                            "predecessor_grant_record_sha256": grant[
                                "record_sha256"
                            ],
                        }
                    )
                entry["external_predecessor_bindings"].sort(
                    key=lambda item: item["predecessor_research_id"]
                )
            order = self._topological_order(sorted(component_ids), edges)
            entries = [prepared[research_id] for research_id in order]
            rendered_edges = [
                {
                    "predecessor_research_id": predecessor,
                    "research_id": child,
                }
                for predecessor, child in sorted(set(edges))
            ]
            component_semantic = {
                "component_key": component_key,
                "entries": entries,
                "edges": rendered_edges,
            }
            component_id = "fact-component-" + sha256_json(component_semantic)
            components.append(
                {"component_id": component_id, **component_semantic}
            )

        blocked_entries: list[dict[str, str]] = []
        blocked_seen: set[str] = set()
        for index, raw_item in enumerate(blocked_input, 1):
            item = _require_exact_fields(
                raw_item,
                {"research_id", "status", "reason"},
                label=f"Fact Candidate blocked input {index}",
            )
            research_id = validate_memory_id(item["research_id"])
            if research_id not in selected_ids:
                raise ValueError("blocked Fact Candidate entry is outside the plan")
            if research_id in seen_research or research_id in blocked_seen:
                raise ValueError("Fact Candidate repeats a blocked Research node")
            blocked_seen.add(research_id)
            if item["status"] not in _BLOCKED_PACKAGING_STATUSES:
                raise ValueError("Fact Candidate blocked status is invalid")
            blocked_entries.append(
                {
                    "research_id": research_id,
                    "status": item["status"],
                    "reason": _require_text(
                        item["reason"], label="Fact Candidate blocked reason"
                    ),
                }
            )
        if seen_research.union(blocked_seen) != selected_ids:
            missing = sorted(selected_ids.difference(seen_research, blocked_seen))
            raise ValueError(
                "Fact Candidate must classify every planned Research node: "
                + ", ".join(missing)
            )
        semantic = {
            "schema_version": 1,
            "contract_revision": FACT_CANDIDATE_PACKAGE_REVISION,
            "project_id": self.store.project_id(),
            "plan_id": plan["plan_id"],
            "plan_record_sha256": plan["record_sha256"],
            "packager": packager,
            "components": components,
            "blocked_entries": sorted(
                blocked_entries, key=lambda item: item["research_id"]
            ),
            "truth_effect": "none",
        }
        package_id = "fact-package-" + sha256_json(semantic)
        record_without_hash = {**semantic, "package_id": package_id}
        record = {
            **record_without_hash,
            "record_sha256": sha256_json(record_without_hash),
        }
        with self.store.v5_mutation_lock(command="fact-package-seal"):
            self._ensure_storage()
            path = self.packages_dir / f"{plan['plan_id']}.json"
            if path.exists():
                existing = self.store._read_json(path)
                existing["__path_stem__"] = path.stem
                existing = self._validate_package(existing)
                if existing != record:
                    raise ValueError(
                        "Fact packaging plan already has a different sealed package"
                    )
                return existing
            self.store._write_json_once(path, record)
        return record

    def verifier_capsule(self, package_id: str) -> dict[str, Any]:
        package = self.package(package_id)
        plan = self.plan(package["plan_id"])
        research_records: list[dict[str, Any]] = []
        for component in package["components"]:
            for entry in component["entries"]:
                research = self.lifecycle._research_record(entry["research_id"])
                research_records.append(
                    {
                        "research_id": research["research_id"],
                        "research_record_sha256": research["record_sha256"],
                        "research_relpath": (
                            self.lifecycle._research_path(research["research_id"])
                            .relative_to(self.store.root)
                            .as_posix()
                        ),
                        "research_record": research,
                    }
                )
        external_grants: dict[str, dict[str, Any]] = {}
        for component in package["components"]:
            for entry in component["entries"]:
                for binding in entry["external_predecessor_bindings"]:
                    grant_id = binding["predecessor_grant_id"]
                    path = self.grants_dir / f"{grant_id}.json"
                    if path.is_symlink() or not path.is_file():
                        raise ValueError(
                            "Fact verifier capsule predecessor grant is missing"
                        )
                    raw = self.store._read_json(path)
                    raw["__path_stem__"] = path.stem
                    grant = self._validate_grant(raw)
                    if (
                        grant["research_id"]
                        != binding["predecessor_research_id"]
                        or grant["record_sha256"]
                        != binding["predecessor_grant_record_sha256"]
                    ):
                        raise ValueError(
                            "Fact verifier capsule predecessor binding drifted"
                        )
                    external_grants[grant_id] = grant
        semantic = {
            "schema_version": 1,
            "contract_revision": FACT_VERIFIER_CAPSULE_REVISION,
            "project_id": self.store.project_id(),
            "package_id": package["package_id"],
            "package_record_sha256": package["record_sha256"],
            "packager": package["packager"],
            "minor_repair_context": plan["minor_repair_context"],
            "components": package["components"],
            "research_records": research_records,
            "external_predecessor_grants": [
                external_grants[grant_id]
                for grant_id in sorted(external_grants)
            ],
            "required_checks": [
                "mathematical_correctness",
                "assumption_and_scope_fidelity",
                "proof_dependency_sufficiency",
                "source_and_computation_replay",
                "statement_interface_fidelity",
                "component_isolation",
            ],
            "review_policy": {
                "role": "independent_correctness_verifier",
                "fresh_falsification_allowed": True,
                "learned_attack_rule_training": False,
                "per_component_failure_isolation": True,
                "minor_error_route": "research_cow_then_same_verifier_recheck",
                "fundamental_error_route": "abandon_component_and_return_to_research",
            },
            "truth_effect": "none",
        }
        return {**semantic, "capsule_sha256": sha256_json(semantic)}

    @staticmethod
    def _validate_component_check_shape(value: Any) -> dict[str, Any]:
        component = _require_exact_fields(
            value,
            {
                "component_id",
                "verdict",
                "research_checks",
                "edge_checks",
                "interface_checks",
                "findings",
                "notes",
            },
            label="Fact certification component check",
        )
        _require_prefixed_sha_id(
            component["component_id"],
            prefix="fact-component-",
            label="Fact component id",
        )
        if component["verdict"] not in _COMPONENT_VERDICTS:
            raise ValueError("Fact certification component verdict is invalid")
        for field in ("research_checks", "edge_checks", "interface_checks", "findings"):
            if not isinstance(component[field], list):
                raise ValueError(f"Fact certification {field} must be a list")
        _require_text(component["notes"], label="Fact certification component notes")
        return component

    def _normalize_component_check(
        self,
        value: Any,
        *,
        package_component: dict[str, Any],
    ) -> dict[str, Any]:
        component = self._validate_component_check_shape(value)
        if component["component_id"] != package_component["component_id"]:
            raise ValueError("Fact certification component binding mismatch")
        research_ids = {
            entry["research_id"] for entry in package_component["entries"]
        }
        research_checks: list[dict[str, str]] = []
        for index, raw in enumerate(component["research_checks"], 1):
            item = _require_exact_fields(
                raw,
                {"research_id", "verdict", "notes"},
                label=f"Fact certification Research check {index}",
            )
            research_id = validate_memory_id(item["research_id"])
            if item["verdict"] not in _RESEARCH_CHECK_VERDICTS:
                raise ValueError("Fact certification Research verdict is invalid")
            research_checks.append(
                {
                    "research_id": research_id,
                    "verdict": item["verdict"],
                    "notes": _require_text(
                        item["notes"], label="Fact certification Research notes"
                    ),
                }
            )
        if (
            {item["research_id"] for item in research_checks} != research_ids
            or len(research_checks) != len(research_ids)
        ):
            raise ValueError(
                "Fact certification Research checks do not exactly cover the component"
            )
        expected_edges = {
            (edge["predecessor_research_id"], edge["research_id"])
            for edge in package_component["edges"]
        }
        for entry in package_component["entries"]:
            expected_edges.update(
                (
                    binding["predecessor_research_id"],
                    entry["research_id"],
                )
                for binding in entry["external_predecessor_bindings"]
            )
        edge_checks: list[dict[str, str]] = []
        for index, raw in enumerate(component["edge_checks"], 1):
            item = _require_exact_fields(
                raw,
                {"predecessor_research_id", "research_id", "verdict", "notes"},
                label=f"Fact certification edge check {index}",
            )
            predecessor_id = validate_memory_id(item["predecessor_research_id"])
            research_id = validate_memory_id(item["research_id"])
            if item["verdict"] not in _BINARY_CHECK_VERDICTS:
                raise ValueError("Fact certification edge verdict is invalid")
            edge_checks.append(
                {
                    "predecessor_research_id": predecessor_id,
                    "research_id": research_id,
                    "verdict": item["verdict"],
                    "notes": _require_text(
                        item["notes"], label="Fact certification edge notes"
                    ),
                }
            )
        if (
            {
                (item["predecessor_research_id"], item["research_id"])
                for item in edge_checks
            }
            != expected_edges
            or len(edge_checks) != len(expected_edges)
        ):
            raise ValueError(
                "Fact certification edge checks do not exactly cover dependencies"
            )
        interface_checks: list[dict[str, str]] = []
        for index, raw in enumerate(component["interface_checks"], 1):
            item = _require_exact_fields(
                raw,
                {"research_id", "verdict", "notes"},
                label=f"Fact certification interface check {index}",
            )
            research_id = validate_memory_id(item["research_id"])
            if item["verdict"] not in _BINARY_CHECK_VERDICTS:
                raise ValueError("Fact certification interface verdict is invalid")
            interface_checks.append(
                {
                    "research_id": research_id,
                    "verdict": item["verdict"],
                    "notes": _require_text(
                        item["notes"], label="Fact certification interface notes"
                    ),
                }
            )
        if (
            {item["research_id"] for item in interface_checks} != research_ids
            or len(interface_checks) != len(research_ids)
        ):
            raise ValueError(
                "Fact certification interface checks do not cover the component"
            )
        findings: list[dict[str, Any]] = []
        if len(component["findings"]) > FACT_ALPHA_MAX_FINDINGS:
            raise ValueError("Fact certification has too many findings")
        seen_findings: set[str] = set()
        for index, raw in enumerate(component["findings"], 1):
            item = _require_exact_fields(
                raw,
                {
                    "finding_id",
                    "severity",
                    "research_ids",
                    "description",
                    "repair_guidance",
                },
                label=f"Fact certification finding {index}",
            )
            finding_id = _require_text(
                item["finding_id"], label="Fact certification finding id"
            )
            if finding_id in seen_findings:
                raise ValueError("Fact certification finding ids must be unique")
            seen_findings.add(finding_id)
            if item["severity"] not in _FINDING_SEVERITIES:
                raise ValueError("Fact certification finding severity is invalid")
            affected = sorted(
                validate_memory_id(research_id)
                for research_id in _require_text_list(
                    item["research_ids"],
                    label="Fact certification affected Research ids",
                    allow_empty=False,
                )
            )
            if not set(affected).issubset(research_ids):
                raise ValueError("Fact certification finding escapes its component")
            findings.append(
                {
                    "finding_id": finding_id,
                    "severity": item["severity"],
                    "research_ids": affected,
                    "description": _require_text(
                        item["description"], label="Fact certification finding"
                    ),
                    "repair_guidance": _require_optional_text(
                        item["repair_guidance"],
                        label="Fact certification repair guidance",
                    ),
                }
            )
        verdict = component["verdict"]
        research_verdicts = {item["verdict"] for item in research_checks}
        binary_verdicts = {
            item["verdict"] for item in [*edge_checks, *interface_checks]
        }
        severities = {item["severity"] for item in findings}
        if verdict == "correct" and (
            findings
            or research_verdicts != {"correct"}
            or binary_verdicts.difference({"correct"})
        ):
            raise ValueError("correct Fact component contains a failing check")
        if verdict == "minor_repair" and (
            "fundamental" in severities
            or "fundamental_error" in research_verdicts
            or not findings
            or "minor" not in severities
        ):
            raise ValueError("minor-repair Fact component evidence is inconsistent")
        if verdict == "fundamental_error" and (
            "fundamental" not in severities
            and "fundamental_error" not in research_verdicts
        ):
            raise ValueError("fundamental Fact error lacks fundamental evidence")
        return {
            "component_id": component["component_id"],
            "verdict": verdict,
            "research_checks": sorted(
                research_checks, key=lambda item: item["research_id"]
            ),
            "edge_checks": sorted(
                edge_checks,
                key=lambda item: (
                    item["predecessor_research_id"], item["research_id"]
                ),
            ),
            "interface_checks": sorted(
                interface_checks, key=lambda item: item["research_id"]
            ),
            "findings": findings,
            "notes": component["notes"],
        }

    def record_decision(
        self,
        payload: dict[str, Any],
        *,
        preflight_only: bool = False,
    ) -> dict[str, Any]:
        payload = _require_exact_fields(
            payload,
            {
                "schema_version",
                "package_id",
                "package_record_sha256",
                "capsule_sha256",
                "reviewer",
                "component_checks",
                "overall_notes",
            },
            label="Fact certification decision input",
        )
        if payload["schema_version"] != 1:
            raise ValueError("Fact certification decision schema_version must be 1")
        package = self.package(payload["package_id"])
        capsule = self.verifier_capsule(package["package_id"])
        if (
            payload["package_record_sha256"] != package["record_sha256"]
            or payload["capsule_sha256"] != capsule["capsule_sha256"]
        ):
            raise ValueError("Fact certification package/capsule binding mismatch")
        reviewer = _require_text(payload["reviewer"], label="Fact verifier")
        plan = self.plan(package["plan_id"])
        minor_context = plan["minor_repair_context"]
        if (
            minor_context is not None
            and reviewer != minor_context["same_verifier"]
        ):
            raise ValueError(
                "Fact minor-repair package must return to the same verifier"
            )
        if reviewer.casefold() == package["packager"].casefold():
            raise ValueError("Fact verifier must differ from the packager")
        authors = {
            self.lifecycle._research_record(entry["research_id"])["actor"].casefold()
            for component in package["components"]
            for entry in component["entries"]
        }
        if reviewer.casefold() in authors:
            raise ValueError("Fact verifier must differ from Research authors")
        raw_checks = payload["component_checks"]
        if not isinstance(raw_checks, list):
            raise ValueError("Fact certification component checks must be a list")
        components_by_id = {
            component["component_id"]: component
            for component in package["components"]
        }
        if (
            {item.get("component_id") for item in raw_checks if isinstance(item, dict)}
            != set(components_by_id)
            or len(raw_checks) != len(components_by_id)
        ):
            raise ValueError(
                "Fact certification checks do not exactly cover package components"
            )
        normalized_checks = [
            self._normalize_component_check(
                item,
                package_component=components_by_id[item["component_id"]],
            )
            for item in raw_checks
        ]
        semantic_without_time = {
            "schema_version": 1,
            "contract_revision": FACT_CERTIFICATION_DECISION_REVISION,
            "project_id": self.store.project_id(),
            "package_id": package["package_id"],
            "package_record_sha256": package["record_sha256"],
            "capsule_sha256": capsule["capsule_sha256"],
            "reviewer": reviewer,
            "component_checks": sorted(
                normalized_checks, key=lambda item: item["component_id"]
            ),
            "overall_notes": _require_text(
                payload["overall_notes"], label="Fact verifier overall notes"
            ),
            "truth_effect": "certification_evidence_only",
        }
        existing_path = self.decisions_dir / f"{package['package_id']}.json"
        if existing_path.exists():
            existing = self.store._read_json(existing_path)
            existing["__path_stem__"] = existing_path.stem
            existing = self._validate_decision(existing)
            existing_without_time = {
                key: value
                for key, value in existing.items()
                if key not in {"reviewed_at", "decision_id", "record_sha256"}
            }
            if existing_without_time != semantic_without_time:
                raise ValueError(
                    "Fact Candidate package already has a different verifier decision"
                )
            return existing
        reviewed_at = _utc_now()
        semantic = {**semantic_without_time, "reviewed_at": reviewed_at}
        decision_id = "fact-decision-" + sha256_json(semantic)
        record_without_hash = {**semantic, "decision_id": decision_id}
        record = {
            **record_without_hash,
            "record_sha256": sha256_json(record_without_hash),
        }
        if preflight_only:
            return record
        with self.store.v5_mutation_lock(command="fact-verification-record"):
            self._ensure_storage()
            self.store._write_json_once(existing_path, record)
        return record

    def certify(
        self,
        decision_id: str,
        *,
        gateway: str,
    ) -> dict[str, Any]:
        decision = self.decision(decision_id)
        package = self.package(decision["package_id"])
        gateway = _require_text(gateway, label="Fact gateway")
        if gateway.casefold() in {
            decision["reviewer"].casefold(),
            package["packager"].casefold(),
        }:
            raise ValueError("Fact gateway must differ from verifier and packager")
        accepted_components = {
            item["component_id"]
            for item in decision["component_checks"]
            if item["verdict"] == "correct"
        }
        if not accepted_components:
            raise ValueError("Fact decision has no correct component to certify")
        acceptance_path = self.acceptances_dir / f"{decision['decision_id']}.json"
        if acceptance_path.exists():
            existing = self.store._read_json(acceptance_path)
            existing["__path_stem__"] = acceptance_path.stem
            existing = self._validate_acceptance(existing)
            if existing["gateway"] != gateway:
                raise ValueError(
                    "Fact decision was already accepted by a different gateway"
                )
            return existing

        from .v5_lifecycle import RoundInspectionContext

        inspection = self.lifecycle._bind_inspection_context(
            RoundInspectionContext(), create=True
        )
        assert inspection is not None
        bases, _dispositions, route_staleness, repair_children = (
            self._route_projection(inspection=inspection)
        )
        grant_projection = self._grant_projection(
            bases=bases,
            route_staleness=route_staleness,
            repair_children=repair_children,
        )
        active_external = grant_projection["active_by_research"]
        grants_to_write: list[dict[str, Any]] = []
        new_by_research: dict[str, dict[str, Any]] = {}
        for component in package["components"]:
            if component["component_id"] not in accepted_components:
                continue
            for entry in component["entries"]:
                research_id = entry["research_id"]
                research = self.lifecycle._research_record(research_id)
                if research["record_sha256"] != entry["research_record_sha256"]:
                    raise ValueError("Fact Research changed after verification")
                terminal = self._terminal_for(
                    research_id,
                    bases=bases,
                    route_staleness=route_staleness,
                    repair_children=repair_children,
                )
                if terminal != research_id or research_id in route_staleness:
                    raise ValueError("Fact Research route changed after verification")
                predecessor_bindings: list[dict[str, str]] = []
                frozen_external = {
                    binding["predecessor_research_id"]: binding
                    for binding in entry["external_predecessor_bindings"]
                }
                for predecessor_id in entry["statement_interface"][
                    "certified_predecessor_research_ids"
                ]:
                    predecessor = new_by_research.get(predecessor_id)
                    if predecessor is None:
                        predecessor = active_external.get(predecessor_id)
                        frozen = frozen_external.get(predecessor_id)
                        if (
                            predecessor is None
                            or frozen is None
                            or predecessor["grant_id"]
                            != frozen["predecessor_grant_id"]
                            or predecessor["record_sha256"]
                            != frozen["predecessor_grant_record_sha256"]
                        ):
                            raise ValueError(
                                "Fact external predecessor changed after verification"
                            )
                    if predecessor is None:
                        raise ValueError(
                            "Fact predecessor lost active certification before gateway"
                        )
                    predecessor_bindings.append(
                        {
                            "predecessor_research_id": predecessor_id,
                            "predecessor_grant_id": predecessor["grant_id"],
                            "predecessor_grant_record_sha256": predecessor[
                                "record_sha256"
                            ],
                        }
                    )
                semantic = {
                    "schema_version": 1,
                    "contract_revision": FACT_CERTIFICATION_GRANT_REVISION,
                    "project_id": self.store.project_id(),
                    "research_id": research_id,
                    "research_record_sha256": research["record_sha256"],
                    "statement_interface": entry["statement_interface"],
                    "predecessor_bindings": sorted(
                        predecessor_bindings,
                        key=lambda item: item["predecessor_research_id"],
                    ),
                    "package_id": package["package_id"],
                    "package_record_sha256": package["record_sha256"],
                    "decision_id": decision["decision_id"],
                    "decision_record_sha256": decision["record_sha256"],
                    "capsule_sha256": decision["capsule_sha256"],
                    "component_id": component["component_id"],
                    "reviewer": decision["reviewer"],
                    "gateway": gateway,
                    "certified_at": decision["reviewed_at"],
                }
                grant_id = "fact-grant-" + sha256_json(semantic)
                record_without_hash = {**semantic, "grant_id": grant_id}
                grant = {
                    **record_without_hash,
                    "record_sha256": sha256_json(record_without_hash),
                }
                grants_to_write.append(grant)
                new_by_research[research_id] = grant

        acceptance_semantic = {
            "schema_version": 1,
            "contract_revision": FACT_CERTIFICATION_ACCEPTANCE_REVISION,
            "project_id": self.store.project_id(),
            "package_id": package["package_id"],
            "package_record_sha256": package["record_sha256"],
            "decision_id": decision["decision_id"],
            "decision_record_sha256": decision["record_sha256"],
            "accepted_component_ids": sorted(accepted_components),
            "grant_ids": [grant["grant_id"] for grant in grants_to_write],
            "reviewer": decision["reviewer"],
            "gateway": gateway,
            "accepted_at": decision["reviewed_at"],
        }
        acceptance_id = "fact-acceptance-" + sha256_json(acceptance_semantic)
        acceptance_without_hash = {
            **acceptance_semantic,
            "acceptance_id": acceptance_id,
        }
        acceptance = {
            **acceptance_without_hash,
            "record_sha256": sha256_json(acceptance_without_hash),
        }
        with self.store.v5_mutation_lock(command="fact-certify"):
            self._ensure_storage()
            for grant in grants_to_write:
                self.store._write_json_once(
                    self.grants_dir / f"{grant['grant_id']}.json", grant
                )
            # Sole visibility switch: readers ignore staged grants until this
            # exact acceptance record lists them.
            self.store._write_json_once(acceptance_path, acceptance)
        return acceptance

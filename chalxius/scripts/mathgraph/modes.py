from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .adoption import (
    TRIGGERED_FEATURES,
    uses_legacy_estimate_policy,
    validate_adoption_binding,
)
from .contracts import (
    FACT_BUNDLE_ID_RE,
    FACT_ID_RE,
    ROUND_ID_RE,
    SHA256_RE,
    require_exact_keys,
    require_string,
    sha256_bytes,
    sha256_json,
)


UNIFIED_GOVERNANCE_SCHEMA_VERSION = 1
UNIFIED_POLICY_REVISION = "mathgraph-unified-0.1.0"
REASONING_MODES = ("fast", "auto", "deep")
MODE_EVENT_PREFIX = "modeevt-"
MODE_INITIALIZATION_RECEIPT_PREFIX = "modeinit-"
WORK_UNIT_ABORT_PREFIX = "workabort-"


def require_unaborted_work_unit(
    project_root: Path | str,
    round_id: str,
) -> None:
    """Reject managed writes for one explicitly aborted frozen round."""

    if ROUND_ID_RE.fullmatch(round_id) is None:
        raise ValueError("invalid round id")
    abort_path = (
        Path(project_root).resolve()
        / "governance"
        / "unified-mode"
        / "work-unit-aborts"
        / "by-round"
        / f"{round_id}.json"
    )
    if abort_path.exists() or abort_path.is_symlink():
        raise ValueError(
            f"work unit {round_id} was explicitly aborted; managed continuation is forbidden"
        )


# This object is deliberately independent of every execution profile.  Its
# canonical JSON hash is the one truth-admission contract bound by all modes.
# A mode policy may only change exploration/governance intensity.
FACT_ADMISSION_CONTRACT: dict[str, Any] = {
    "schema_version": 1,
    "contract_id": "mathgraph-fact-admission-v1",
    "truth_store": "fact_graph/facts/*.md",
    "mode_invariance": "identical_across_fast_auto_deep",
    "candidate_rule": (
        "anything not admitted through this contract remains nontruth candidate evidence"
    ),
    "gates": [
        {
            "id": "content_addressed_candidate",
            "requirement": (
                "bind exact statement, proof, direct predecessors, source evidence, "
                "task card, and submission or bundle bytes"
            ),
        },
        {
            "id": "statement_only_predecessors",
            "requirement": (
                "reuse only active admitted predecessor statement clauses; proof-only "
                "dependencies and candidate-on-candidate chains are forbidden"
            ),
        },
        {
            "id": "source_and_applicability_fidelity",
            "requirement": (
                "bind exact source artifact and statement, hypothesis/witness mapping, "
                "status audit, formula glyphs, conventions, quantifiers, and transports"
            ),
        },
        {
            "id": "load_bearing_computation_replay",
            "requirement": (
                "load-bearing computation requires authorized immutable artifacts and "
                "independent replay evidence"
            ),
        },
        {
            "id": "atomic_internal_fact_dag",
            "requirement": (
                "internally dependent or all-or-none candidate facts use one frozen "
                "mini-DAG package and all-or-none admission"
            ),
        },
        {
            "id": "fresh_independent_verifier",
            "requirement": (
                "a different fresh verifier receives only the frozen packet or bundle "
                "capability and returns one structured review"
            ),
        },
        {
            "id": "review_and_admission_binding",
            "requirement": (
                "the latest clean review, submission or bundle, verification package, "
                "gateway acceptance, and stored fact are hash-bound"
            ),
        },
        {
            "id": "revocation_and_audit",
            "requirement": (
                "wrong facts are cascade-revoked and current graph/workflow audit must pass"
            ),
        },
    ],
}
FACT_ADMISSION_CONTRACT_SHA256 = sha256_json(FACT_ADMISSION_CONTRACT)


EXPLORATION_FEATURES = (
    "parallel_clean_context_panel",
    "barriered_blackboard_pulse",
    "paper_logic_graph",
    "paper_audit_graph",
    "full_fidelity_paper_mirror",
    "orthogonal_specialist_escalation",
    "long_horizon_campaign_expansion",
    "computation_exploration_lane",
    "novelty_search_lane",
    "expert_synthesis_pass",
)
PROFILE_FEATURE_STATUSES = ("required", "available", "not_applicable")
ADMISSION_RELEVANT_ADOPTION_FEATURES = (
    "experiment_checkpoint",
    "artifact_replay",
    "atomic_fact_bundle",
    "source_claim_gate",
    "convention_gate",
    "quantifier_gate",
)


MODE_POLICY: dict[str, Any] = {
    "schema_version": 1,
    "policy_revision": UNIFIED_POLICY_REVISION,
    # Frozen wire identifier for existing project hashes, not current product wording.
    "policy_id": "chalk-native-reasoning-modes-v1",
    "architectural_base": "mathgraph-chalk-0.4.0",
    "fact_admission_contract_sha256": FACT_ADMISSION_CONTRACT_SHA256,
    "mode_switch_semantics": {
        "effect": "future_work_units_only",
        "frozen_work_units": "retain_original_reasoning_mode_until_complete_or_abort",
        "frozen_evidence": "never_rewritten_or_relabelled",
        "truth_gate_override": "forbidden",
    },
    "modes": {
        "fast": {
            "execution_profile": "chalk_v4_low_orchestration",
            "rule": (
                "do not auto-activate high-cost exploration features; retain the full "
                "Chalk V4 object, snapshot, hash, audit, and truth-admission model"
            ),
        },
        "auto": {
            "execution_profile": "chalk_v4_workload_routed",
            "rule": (
                "activate high-cost exploration features only through deterministic "
                "workload and semantic applicability"
            ),
        },
        "deep": {
            "execution_profile": "chalk_v4_all_applicable_high_cost",
            "rule": (
                "activate every applicable high-cost exploration feature; record truly "
                "inapplicable features as not_applicable"
            ),
        },
    },
    "exploration_features": list(EXPLORATION_FEATURES),
}
MODE_POLICY_SHA256 = sha256_json(MODE_POLICY)


_MODE_BINDING_FIELDS = {
    "reasoning_mode",
    "reasoning_mode_event_id",
    "reasoning_mode_policy_sha256",
    "fact_admission_contract_sha256",
    "execution_profile",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _require_reasoning_mode(value: Any) -> str:
    if not isinstance(value, str) or value not in REASONING_MODES:
        raise ValueError(
            "reasoning_mode must be one of fast, auto, or deep"
        )
    return value


def _feature_decision(*, applicable: bool, required: bool, reason: str) -> dict[str, str]:
    if not applicable:
        status = "not_applicable"
    elif required:
        status = "required"
    else:
        status = "available"
    return {"status": status, "reason": reason}


def build_round_profile_obligations(
    execution_profiles: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Freeze assignment and round-wide exploration-feature statuses."""

    if not isinstance(execution_profiles, dict) or not execution_profiles:
        raise ValueError("round execution profiles must be a nonempty object")
    assignments: dict[str, dict[str, Any]] = {}
    aggregate = {feature: "not_applicable" for feature in EXPLORATION_FEATURES}
    rank = {"not_applicable": 0, "available": 1, "required": 2}
    for assignment_id, profile in sorted(execution_profiles.items()):
        if not isinstance(assignment_id, str) or not assignment_id:
            raise ValueError("round execution profile assignment id is invalid")
        if not isinstance(profile, dict):
            raise ValueError("round execution profile must be one object")
        profile_sha = profile.get("execution_profile_sha256")
        if not isinstance(profile_sha, str) or SHA256_RE.fullmatch(profile_sha) is None:
            raise ValueError("round execution profile hash is invalid")
        feature_payload = profile.get("exploration_features")
        if not isinstance(feature_payload, dict) or set(feature_payload) != set(
            EXPLORATION_FEATURES
        ):
            raise ValueError("round execution profile feature set is invalid")
        statuses: dict[str, str] = {}
        for feature in EXPLORATION_FEATURES:
            decision = feature_payload.get(feature)
            status = decision.get("status") if isinstance(decision, dict) else None
            if status not in PROFILE_FEATURE_STATUSES:
                raise ValueError(
                    f"round execution profile {feature} status is invalid"
                )
            statuses[feature] = status
            if rank[status] > rank[aggregate[feature]]:
                aggregate[feature] = status
        assignments[assignment_id] = {
            "execution_profile_sha256": profile_sha,
            "feature_statuses": statuses,
        }
    semantic = {
        "schema_version": 1,
        "policy_revision": UNIFIED_POLICY_REVISION,
        "assignments": assignments,
        "feature_statuses": aggregate,
        "required_features": sorted(
            feature
            for feature, status in aggregate.items()
            if status == "required"
        ),
    }
    return {**semantic, "obligations_sha256": sha256_json(semantic)}


def _exploration_feature_plan(
    reasoning_mode: str,
    workload_profile: dict[str, Any],
) -> dict[str, dict[str, str]]:
    reasoning_mode = _require_reasoning_mode(reasoning_mode)
    activity = workload_profile["activity"]
    audience = workload_profile["audience"]
    computation = workload_profile["computation"]
    fact_output = workload_profile["fact_output"]
    semantics = workload_profile["semantics"]

    substantive = activity in {
        "proof",
        "refutation",
        "computation",
        "literature",
        "interpretation",
    }
    paper_led = semantics["source_claim"] and activity in {
        "literature",
        "interpretation",
        "refutation",
    }
    source_ambiguity = semantics.get("source_ambiguity", False)
    sensitive = any(
        (
            source_ambiguity,
            semantics["convention_sensitive"],
            semantics["quantifier_sensitive"],
            semantics["terminology_sensitive"],
        )
    )
    multi_candidate = (
        fact_output["candidate_count"] > 1
        or fact_output["internal_dependency_count"] > 0
        or fact_output["atomic_visibility_required"]
    )
    computational = computation["role"] != "none"
    external_output = (
        audience != "internal"
        or activity == "export"
        or semantics["terminology_sensitive"]
    )

    applicability = {
        "parallel_clean_context_panel": substantive,
        "barriered_blackboard_pulse": substantive,
        "paper_logic_graph": paper_led,
        "paper_audit_graph": paper_led,
        "full_fidelity_paper_mirror": paper_led,
        "orthogonal_specialist_escalation": substantive,
        "long_horizon_campaign_expansion": substantive,
        "computation_exploration_lane": computational,
        "novelty_search_lane": activity == "literature",
        "expert_synthesis_pass": external_output,
    }
    auto_triggers = {
        "parallel_clean_context_panel": substantive and (
            sensitive or multi_candidate or computational
        ),
        "barriered_blackboard_pulse": substantive and (
            sensitive or multi_candidate or computational
        ),
        "paper_logic_graph": paper_led,
        "paper_audit_graph": paper_led and (
            source_ambiguity
            or activity in {"interpretation", "refutation"}
        ),
        "full_fidelity_paper_mirror": paper_led and (
            source_ambiguity or activity == "interpretation"
        ),
        "orthogonal_specialist_escalation": substantive and sensitive,
        "long_horizon_campaign_expansion": substantive and multi_candidate,
        "computation_exploration_lane": computational,
        "novelty_search_lane": activity == "literature",
        "expert_synthesis_pass": external_output,
    }

    decisions: dict[str, dict[str, str]] = {}
    for feature in EXPLORATION_FEATURES:
        applicable = applicability[feature]
        if reasoning_mode == "fast":
            required = False
            reason = (
                "fast leaves applicable high-cost exploration opt-in"
                if applicable
                else "feature does not apply to this workload"
            )
        elif reasoning_mode == "auto":
            required = auto_triggers[feature]
            reason = (
                "auto workload trigger is active"
                if required
                else (
                    "auto workload trigger is inactive"
                    if applicable
                    else "feature does not apply to this workload"
                )
            )
        else:
            required = applicable
            reason = (
                "deep activates every applicable high-cost research feature"
                if applicable
                else "feature is genuinely inapplicable to this workload"
            )
        decisions[feature] = _feature_decision(
            applicable=applicable,
            required=required,
            reason=reason,
        )
    return decisions


def build_execution_profile(
    *,
    reasoning_mode: str,
    reasoning_mode_event_id: str,
    adoption_binding: dict[str, Any],
) -> dict[str, Any]:
    reasoning_mode = _require_reasoning_mode(reasoning_mode)
    if not isinstance(reasoning_mode_event_id, str) or not reasoning_mode_event_id.startswith(
        MODE_EVENT_PREFIX
    ):
        raise ValueError("reasoning_mode_event_id is invalid")
    adoption_binding = validate_adoption_binding(adoption_binding)
    nonnegotiable_obligations = [
        {
            "feature": feature,
            "status": "required",
            "mode_override": "forbidden",
            "unsatisfied_effect": "candidate_only",
        }
        for feature in ADMISSION_RELEVANT_ADOPTION_FEATURES
        if adoption_binding["feature_statuses"][feature] == "required"
    ]
    blocking_state = (
        "candidate_only_until_gate_satisfied"
        if nonnegotiable_obligations
        else "ready_with_nonnegotiable_truth_gates"
    )
    semantic = {
        "schema_version": 1,
        "policy_revision": UNIFIED_POLICY_REVISION,
        "execution_profile": MODE_POLICY["modes"][reasoning_mode][
            "execution_profile"
        ],
        "reasoning_mode": reasoning_mode,
        "reasoning_mode_event_id": reasoning_mode_event_id,
        "reasoning_mode_policy_sha256": MODE_POLICY_SHA256,
        "fact_admission_contract_sha256": FACT_ADMISSION_CONTRACT_SHA256,
        "adoption_binding_sha256": adoption_binding["binding_sha256"],
        "adoption_feature_statuses": {
            feature: adoption_binding["feature_statuses"][feature]
            for feature in sorted(TRIGGERED_FEATURES)
        },
        "mode_may_override_adoption_or_truth_gates": False,
        "nonnegotiable_admission_obligations": nonnegotiable_obligations,
        "exploration_features": _exploration_feature_plan(
            reasoning_mode,
            adoption_binding["workload_profile"],
        ),
        "blocking_state": blocking_state,
    }
    return {**semantic, "execution_profile_sha256": sha256_json(semantic)}


def validate_execution_profile(
    payload: Any,
    *,
    adoption_binding: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("execution_profile must be one object")
    expected = build_execution_profile(
        reasoning_mode=require_string(payload, "reasoning_mode"),
        reasoning_mode_event_id=require_string(
            payload,
            "reasoning_mode_event_id",
        ),
        adoption_binding=adoption_binding,
    )
    if payload != expected:
        raise ValueError(
            "execution_profile does not match the deterministic reasoning-mode policy"
        )
    return payload


def validate_mode_binding_fields(
    payload: dict[str, Any],
    *,
    adoption_binding: dict[str, Any],
    allow_legacy_adoption: bool = False,
) -> dict[str, Any] | None:
    present = _MODE_BINDING_FIELDS.intersection(payload)
    if not present:
        return None
    if present != _MODE_BINDING_FIELDS:
        raise ValueError(
            "unified reasoning-mode fields must appear as one complete binding"
        )
    reasoning_mode = _require_reasoning_mode(payload["reasoning_mode"])
    if payload["reasoning_mode_policy_sha256"] != MODE_POLICY_SHA256:
        raise ValueError("reasoning-mode policy hash mismatch")
    if (
        payload["fact_admission_contract_sha256"]
        != FACT_ADMISSION_CONTRACT_SHA256
    ):
        raise ValueError("fact-admission contract hash mismatch")
    if allow_legacy_adoption and uses_legacy_estimate_policy(
        adoption_binding
    ):
        execution_profile = payload["execution_profile"]
        if not isinstance(execution_profile, dict):
            raise ValueError("historical execution_profile must be one object")
        if (
            execution_profile.get("reasoning_mode") != reasoning_mode
            or execution_profile.get("reasoning_mode_event_id")
            != payload["reasoning_mode_event_id"]
            or execution_profile.get("reasoning_mode_policy_sha256")
            != MODE_POLICY_SHA256
            or execution_profile.get("fact_admission_contract_sha256")
            != FACT_ADMISSION_CONTRACT_SHA256
        ):
            raise ValueError("historical execution-profile/mode binding mismatch")
        semantic = {
            key: value
            for key, value in execution_profile.items()
            if key != "execution_profile_sha256"
        }
        if execution_profile.get("execution_profile_sha256") != sha256_json(
            semantic
        ):
            raise ValueError("historical execution-profile hash mismatch")
        return execution_profile
    execution_profile = validate_execution_profile(
        payload["execution_profile"],
        adoption_binding=adoption_binding,
    )
    if (
        execution_profile["reasoning_mode"] != reasoning_mode
        or execution_profile["reasoning_mode_event_id"]
        != payload["reasoning_mode_event_id"]
    ):
        raise ValueError("execution-profile/mode binding mismatch")
    return execution_profile


class ReasoningModeManager:
    """Append-only Chalxius reasoning-mode governance for one project."""

    def __init__(self, store: Any) -> None:
        self.store = store
        self.root = store.root / "governance" / "unified-mode"
        self.contract_path = self.root / "fact-admission-contract.json"
        self.policy_path = self.root / "reasoning-mode-policy.json"
        self.ledger_path = self.root / "mode-events.jsonl"
        self.events_dir = self.root / "events" / "by-id"
        self.current_path = self.root / "current.json"
        self.activation_receipt_path = self.root / "activation-receipt.json"
        self.abort_dir = self.root / "work-unit-aborts" / "by-round"

    def _governance_paths(self) -> tuple[Path, ...]:
        return (
            self.contract_path,
            self.policy_path,
            self.ledger_path,
            self.current_path,
            self.activation_receipt_path,
        )

    def has_any_state(self) -> bool:
        return self.root.exists() and any(self.root.iterdir())

    def is_initialized(self) -> bool:
        return all(path.is_file() and not path.is_symlink() for path in self._governance_paths())

    @staticmethod
    def _event_semantic(event: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in event.items() if key != "event_id"}

    def _validate_event(self, event: Any) -> dict[str, Any]:
        if not isinstance(event, dict):
            raise ValueError("mode event must be one object")
        require_exact_keys(
            event,
            required={
                "schema_version",
                "policy_revision",
                "event",
                "event_id",
                "project_id",
                "sequence",
                "previous_event_id",
                "previous_reasoning_mode",
                "reasoning_mode",
                "reason",
                "actor",
                "applies_to",
                "frozen_work_units",
                "reasoning_mode_policy_sha256",
                "fact_admission_contract_sha256",
                "created_at",
            },
            label="reasoning-mode event",
        )
        if event.get("schema_version") != 1:
            raise ValueError("mode event schema_version must be 1")
        if event.get("policy_revision") != UNIFIED_POLICY_REVISION:
            raise ValueError("mode event policy revision mismatch")
        if event.get("event") not in {"mode_initialized", "mode_switched"}:
            raise ValueError("mode event kind is invalid")
        if event.get("project_id") != self.store.project_id():
            raise ValueError("mode event belongs to another project")
        sequence = event.get("sequence")
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
            raise ValueError("mode event sequence must be a positive integer")
        _require_reasoning_mode(event.get("reasoning_mode"))
        if event.get("event") == "mode_initialized":
            if event.get("previous_event_id") is not None or event.get(
                "previous_reasoning_mode"
            ) is not None:
                raise ValueError("initial mode event cannot have a predecessor")
        else:
            previous_id = event.get("previous_event_id")
            previous_mode = event.get("previous_reasoning_mode")
            if not isinstance(previous_id, str) or not previous_id.startswith(
                MODE_EVENT_PREFIX
            ):
                raise ValueError("mode switch previous_event_id is invalid")
            _require_reasoning_mode(previous_mode)
        require_string(event, "reason")
        require_string(event, "actor")
        require_string(event, "created_at")
        if event.get("applies_to") != "future_work_units_only":
            raise ValueError("mode event may apply only to future work units")
        if (
            event.get("frozen_work_units")
            != "retain_original_mode_until_complete_or_explicit_abort"
        ):
            raise ValueError("mode event frozen-work-unit semantics mismatch")
        if event.get("reasoning_mode_policy_sha256") != MODE_POLICY_SHA256:
            raise ValueError("mode event policy hash mismatch")
        if (
            event.get("fact_admission_contract_sha256")
            != FACT_ADMISSION_CONTRACT_SHA256
        ):
            raise ValueError("mode event admission contract hash mismatch")
        expected_id = MODE_EVENT_PREFIX + sha256_json(self._event_semantic(event))
        if event.get("event_id") != expected_id:
            raise ValueError("mode event id/hash mismatch")
        return event

    def events(self) -> list[dict[str, Any]]:
        return [self._validate_event(item) for item in self.store._read_jsonl(self.ledger_path)]

    def _current_projection(self, event: dict[str, Any]) -> dict[str, Any]:
        semantic = {
            "schema_version": 1,
            "policy_revision": UNIFIED_POLICY_REVISION,
            "project_id": self.store.project_id(),
            "reasoning_mode": event["reasoning_mode"],
            "reasoning_mode_event_id": event["event_id"],
            "sequence": event["sequence"],
            "reasoning_mode_policy_sha256": MODE_POLICY_SHA256,
            "fact_admission_contract_sha256": FACT_ADMISSION_CONTRACT_SHA256,
            "projection_rule": "latest_valid_append_only_mode_event",
        }
        return {**semantic, "projection_sha256": sha256_json(semantic)}

    def _round_inventory(self) -> dict[str, str]:
        return {
            path.parent.name: sha256_bytes(path.read_bytes())
            for path in sorted(self.store.rounds_dir.glob("*/round.json"))
            if path.is_file() and not path.is_symlink()
        }

    def _has_symlink_component(self, path: Path) -> bool:
        """Reject a symlink before resolution can erase that evidence."""

        unresolved = path.absolute()
        if not unresolved.is_relative_to(self.store.root):
            return True
        cursor = self.store.root
        for component in unresolved.relative_to(self.store.root).parts:
            cursor = cursor / component
            if cursor.is_symlink():
                return True
        return False

    def _file_binding(self, path: Path) -> dict[str, Any]:
        if self._has_symlink_component(path):
            raise ValueError("mode activation baseline path is missing or unsafe")
        path = path.resolve()
        if (
            not path.is_relative_to(self.store.root)
            or not path.is_file()
        ):
            raise ValueError("mode activation baseline path is missing or unsafe")
        raw = path.read_bytes()
        return {
            "relpath": path.relative_to(self.store.root).as_posix(),
            "byte_length": len(raw),
            "sha256": sha256_bytes(raw),
        }

    def _tree_binding(self, directory: Path) -> dict[str, Any]:
        if self._has_symlink_component(directory):
            raise ValueError(
                "mode activation baseline directory is missing or unsafe"
            )
        directory = directory.resolve()
        if (
            not directory.is_relative_to(self.store.root)
            or not directory.is_dir()
        ):
            raise ValueError(
                "mode activation baseline directory is missing or unsafe"
            )
        files = {
            path.relative_to(self.store.root).as_posix(): self._file_binding(
                path
            )
            for path in sorted(directory.rglob("*"))
            if path.is_file() or path.is_symlink()
        }
        if any((self.store.root / relpath).is_symlink() for relpath in files):
            raise ValueError("mode activation baseline contains a symlink")
        return {"files": files, "files_sha256": sha256_json(files)}

    def _jsonl_event_line_binding(
        self,
        path: Path,
        *,
        event_id: str,
    ) -> dict[str, Any]:
        if self._has_symlink_component(path):
            raise ValueError(
                "mode activation event log path is missing or unsafe"
            )
        resolved = path.resolve()
        if not resolved.is_file() or not resolved.is_relative_to(
            self.store.root
        ):
            raise ValueError(
                "mode activation event log path is missing or unsafe"
            )
        matches: list[tuple[int, bytes]] = []
        for line_number, raw_line in enumerate(
            resolved.read_bytes().splitlines(keepends=True),
            1,
        ):
            if not raw_line.strip():
                continue
            try:
                event = json.loads(raw_line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError(
                    "mode activation event log contains invalid JSONL"
                ) from exc
            if not isinstance(event, dict):
                raise ValueError(
                    "mode activation event log entry must be an object"
                )
            if event.get("event_id") == event_id:
                matches.append((line_number, raw_line))
        if len(matches) != 1:
            raise ValueError(
                "mode activation acceptance event line is missing or duplicated"
            )
        line_number, raw_line = matches[0]
        return {
            "relpath": resolved.relative_to(self.store.root).as_posix(),
            "line_number": line_number,
            "byte_length": len(raw_line),
            "sha256": sha256_bytes(raw_line),
        }

    def _ordinary_admission_entry(
        self,
        fact_id: str,
        event: dict[str, Any],
    ) -> dict[str, Any]:
        fact_path = self.store.fact_path(fact_id)
        submission_path = self.store.submission_path(fact_id)
        review_id = require_string(event, "review_id")
        review_path = self.store.review_path(review_id)
        review = self.store._read_json(review_path)
        verification_files: dict[str, dict[str, Any]] = {}
        if event.get("evidence_version") == 4:
            bundle_sha256 = require_string(review, "bundle_sha256")
            if SHA256_RE.fullmatch(bundle_sha256) is None:
                raise ValueError(
                    "mode activation V4 review bundle hash is invalid"
                )
            verification = self._tree_binding(
                self.store.verification_bundles().by_hash_dir
                / bundle_sha256
            )
            verification_files = verification["files"]
        else:
            packet_manifest = self.store.packet_by_fact_dir / f"{fact_id}.json"
            manifest = self.store._read_json(packet_manifest)
            packet_relpath = require_string(manifest, "packet_relpath")
            packet_path = (self.store.root / packet_relpath).resolve()
            for path in (packet_manifest, packet_path):
                binding = self._file_binding(path)
                verification_files[binding["relpath"]] = binding
        event_id = require_string(event, "event_id")
        return {
            "acceptance_event_id": event_id,
            "acceptance_event_sha256": sha256_json(event),
            "acceptance_event_line": self._jsonl_event_line_binding(
                self.store.verification_log,
                event_id=event_id,
            ),
            "fact": self._file_binding(fact_path),
            "submission": self._file_binding(submission_path),
            "review": self._file_binding(review_path),
            "verification_files": verification_files,
            "verification_files_sha256": sha256_json(
                verification_files
            ),
        }

    def _legacy_admission_inventory(self) -> dict[str, Any]:
        ordinary: dict[str, dict[str, Any]] = {}
        for event in self.store._read_jsonl(self.store.verification_log):
            if event.get("event") != "accepted":
                continue
            fact_id = event.get("fact_id")
            if (
                not isinstance(fact_id, str)
                or FACT_ID_RE.fullmatch(fact_id) is None
                or not self.store.fact_path(fact_id).is_file()
            ):
                continue
            if fact_id in ordinary:
                raise ValueError(
                    f"mode activation has duplicate accepted events for {fact_id}"
                )
            ordinary[fact_id] = self._ordinary_admission_entry(
                fact_id,
                event,
            )

        from .fact_bundles import FactBundleStore

        atomic_bundles: dict[str, dict[str, Any]] = {}
        raw_bundles = FactBundleStore._for_inherited_chalk_fixture(
            self.store.root
        )
        for directory in sorted(raw_bundles.root.glob("factbundle-*")):
            if not (directory / "ACCEPTED.json").is_file():
                continue
            manifest, _, marker = raw_bundles._validated_acceptance(
                directory.name
            )
            if manifest["fact_bundle_id"] != directory.name:
                raise ValueError("mode activation fact-bundle id mismatch")
            tree = self._tree_binding(directory)
            atomic_bundles[directory.name] = {
                "acceptance_sha256": marker["acceptance_sha256"],
                "files": tree["files"],
                "files_sha256": tree["files_sha256"],
            }
        return {
            "ordinary": ordinary,
            "atomic_bundles": atomic_bundles,
        }

    def _validate_file_binding(
        self,
        payload: Any,
        *,
        label: str,
    ) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError(f"{label} must be one object")
        require_exact_keys(
            payload,
            required={"relpath", "byte_length", "sha256"},
            label=label,
        )
        relpath = require_string(payload, "relpath")
        unresolved_path = self.store.root / relpath
        if self._has_symlink_component(unresolved_path):
            raise ValueError(f"{label} path is missing or unsafe")
        path = unresolved_path.resolve()
        if (
            not path.is_relative_to(self.store.root)
            or path.relative_to(self.store.root).as_posix() != relpath
            or not path.is_file()
        ):
            raise ValueError(f"{label} path is missing or unsafe")
        byte_length = payload.get("byte_length")
        if (
            isinstance(byte_length, bool)
            or not isinstance(byte_length, int)
            or byte_length < 0
        ):
            raise ValueError(f"{label} byte_length is invalid")
        digest = require_string(payload, "sha256")
        if SHA256_RE.fullmatch(digest) is None:
            raise ValueError(f"{label} sha256 is invalid")
        raw = path.read_bytes()
        if len(raw) != byte_length or sha256_bytes(raw) != digest:
            raise ValueError(f"{label} bytes drifted after mode activation")
        return dict(payload)

    def _validate_legacy_admission_inventory(
        self,
        payload: Any,
    ) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError(
                "mode activation legacy admission inventory must be an object"
            )
        require_exact_keys(
            payload,
            required={"ordinary", "atomic_bundles"},
            label="mode activation legacy admission inventory",
        )
        ordinary = payload.get("ordinary")
        atomic = payload.get("atomic_bundles")
        if not isinstance(ordinary, dict) or not isinstance(atomic, dict):
            raise ValueError(
                "mode activation admission inventories must be objects"
            )
        current_events = self.store._read_jsonl(self.store.verification_log)
        for fact_id, entry in ordinary.items():
            if (
                not isinstance(fact_id, str)
                or FACT_ID_RE.fullmatch(fact_id) is None
                or not isinstance(entry, dict)
            ):
                raise ValueError(
                    "mode activation ordinary admission id/entry is invalid"
                )
            require_exact_keys(
                entry,
                required={
                    "acceptance_event_id",
                    "acceptance_event_sha256",
                    "acceptance_event_line",
                    "fact",
                    "submission",
                    "review",
                    "verification_files",
                    "verification_files_sha256",
                },
                label=f"mode activation ordinary admission {fact_id}",
            )
            event_id = require_string(entry, "acceptance_event_id")
            event_sha = require_string(entry, "acceptance_event_sha256")
            if SHA256_RE.fullmatch(event_sha) is None:
                raise ValueError(
                    "mode activation acceptance event hash is invalid"
                )
            matches = [
                event
                for event in current_events
                if event.get("event") == "accepted"
                and event.get("fact_id") == fact_id
                and event.get("event_id") == event_id
                and sha256_json(event) == event_sha
            ]
            if len(matches) != 1:
                raise ValueError(
                    f"mode activation acceptance event drifted for {fact_id}"
                )
            if entry.get("acceptance_event_line") != (
                self._jsonl_event_line_binding(
                    self.store.verification_log,
                    event_id=event_id,
                )
            ):
                raise ValueError(
                    f"mode activation acceptance event bytes drifted for {fact_id}"
                )
            for key in ("fact", "submission", "review"):
                self._validate_file_binding(
                    entry[key],
                    label=f"mode activation {fact_id} {key}",
                )
            verification_files = entry.get("verification_files")
            if not isinstance(verification_files, dict):
                raise ValueError(
                    "mode activation verification_files must be an object"
                )
            if entry.get("verification_files_sha256") != sha256_json(
                verification_files
            ):
                raise ValueError(
                    "mode activation verification_files hash mismatch"
                )
            for relpath, binding in verification_files.items():
                validated = self._validate_file_binding(
                    binding,
                    label=f"mode activation verification file {relpath}",
                )
                if validated["relpath"] != relpath:
                    raise ValueError(
                        "mode activation verification file key/path mismatch"
                    )

        for bundle_id, entry in atomic.items():
            if (
                not isinstance(bundle_id, str)
                or FACT_BUNDLE_ID_RE.fullmatch(bundle_id) is None
                or not isinstance(entry, dict)
            ):
                raise ValueError(
                    "mode activation atomic admission id/entry is invalid"
                )
            require_exact_keys(
                entry,
                required={"acceptance_sha256", "files", "files_sha256"},
                label=f"mode activation atomic admission {bundle_id}",
            )
            acceptance_sha = require_string(entry, "acceptance_sha256")
            if SHA256_RE.fullmatch(acceptance_sha) is None:
                raise ValueError(
                    "mode activation atomic acceptance hash is invalid"
                )
            files = entry.get("files")
            if (
                not isinstance(files, dict)
                or entry.get("files_sha256") != sha256_json(files)
            ):
                raise ValueError(
                    "mode activation atomic file inventory hash mismatch"
                )
            current_paths = {
                path.relative_to(self.store.root).as_posix()
                for path in sorted(
                    (self.store.fact_bundles().root / bundle_id).rglob("*")
                )
                if path.is_file() or path.is_symlink()
            }
            if current_paths != set(files):
                raise ValueError(
                    f"mode activation atomic bundle bytes drifted: {bundle_id}"
                )
            for relpath, binding in files.items():
                validated = self._validate_file_binding(
                    binding,
                    label=f"mode activation atomic file {relpath}",
                )
                if validated["relpath"] != relpath:
                    raise ValueError(
                        "mode activation atomic file key/path mismatch"
                    )
            marker = self.store._read_json(
                self.store.fact_bundles().root
                / bundle_id
                / "ACCEPTED.json"
            )
            if marker.get("acceptance_sha256") != acceptance_sha:
                raise ValueError(
                    f"mode activation atomic acceptance drifted: {bundle_id}"
                )
        return payload

    def is_historical_accepted_submission(
        self,
        submission: dict[str, Any],
    ) -> bool:
        fact_id = submission.get("submission_id") or submission.get("fact_id")
        if not isinstance(fact_id, str) or FACT_ID_RE.fullmatch(fact_id) is None:
            return False
        if self.store._allows_inherited_chalk_fixture_writes():
            return True
        if not self.is_initialized():
            if submission.get("status") not in {"accepted", "revoked"}:
                return False
            matches = [
                event
                for event in self.store._read_jsonl(self.store.verification_log)
                if event.get("event") == "accepted"
                and event.get("fact_id") == fact_id
            ]
            if len(matches) != 1:
                return False
            try:
                self._ordinary_admission_entry(fact_id, matches[0])
            except Exception:
                return False
            return True
        receipt = self._validate_activation_receipt(
            self.store._read_json(self.activation_receipt_path)
        )
        return fact_id in receipt["legacy_admission_inventory"]["ordinary"]

    def is_historical_accepted_bundle(self, fact_bundle_id: str) -> bool:
        if FACT_BUNDLE_ID_RE.fullmatch(fact_bundle_id) is None:
            return False
        if self.store._allows_inherited_chalk_fixture_writes():
            return True
        if not self.is_initialized():
            from .fact_bundles import FactBundleStore

            try:
                FactBundleStore._for_inherited_chalk_fixture(
                    self.store.root
                )._validated_acceptance(fact_bundle_id)
            except Exception:
                return False
            return True
        receipt = self._validate_activation_receipt(
            self.store._read_json(self.activation_receipt_path)
        )
        return fact_bundle_id in receipt["legacy_admission_inventory"][
            "atomic_bundles"
        ]

    def initialize(
        self,
        *,
        reasoning_mode: str,
        actor: str,
        reason: str,
        source_kind: str,
    ) -> dict[str, Any]:
        reasoning_mode = _require_reasoning_mode(reasoning_mode)
        workflow_version = self.store.workflow_evidence_version()
        if workflow_version not in {4, 5}:
            raise ValueError(
                "unified reasoning-mode governance requires workflow evidence v4 or v5"
            )
        if source_kind not in {
            "new_unified_project",
            "legacy_chalk_v4_upgrade",
            "new_v5_project",
        }:
            raise ValueError("mode initialization source_kind is invalid")
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError("mode initialization actor must be nonempty")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("mode initialization reason must be nonempty")

        # A dirty mode-less project must fail without even creating the OS lock
        # file. The same audit and inventory are repeated under the transition
        # lock below so this preflight does not become a TOCTOU authorization.
        if not self.has_any_state():
            preflight_audit = self.store.audit()
            if not preflight_audit.current_ok:
                raise ValueError(
                    "mode-init requires a clean pre-activation audit: "
                    + "; ".join(preflight_audit.errors)
                )
        transition_lock = (
            self.store._uninitialized_v5_transition_lock()
            if workflow_version == 5
            else self.store._uninitialized_v4_transition_lock()
        )
        with transition_lock:
            if self.has_any_state():
                if not self.is_initialized():
                    raise ValueError(
                        "partial unified mode governance exists; audit and repair before retry"
                    )
                status = self.status()
                if status["reasoning_mode"] != reasoning_mode:
                    raise ValueError(
                        "mode governance is already initialized; use mode-switch"
                    )
                return status

            locked_audit = self.store.audit()
            if not locked_audit.current_ok:
                raise ValueError(
                    "mode-init requires a clean pre-activation audit: "
                    + "; ".join(locked_audit.errors)
                )
            legacy_admission_inventory = (
                self._legacy_admission_inventory()
            )

            contract_envelope = {
                "contract": FACT_ADMISSION_CONTRACT,
                "contract_sha256": FACT_ADMISSION_CONTRACT_SHA256,
            }
            policy_envelope = {
                "policy": MODE_POLICY,
                "policy_sha256": MODE_POLICY_SHA256,
            }
            self.store._write_json_once(self.contract_path, contract_envelope)
            self.store._write_json_once(self.policy_path, policy_envelope)

            event_semantic = {
                "schema_version": 1,
                "policy_revision": UNIFIED_POLICY_REVISION,
                "event": "mode_initialized",
                "project_id": self.store.project_id(),
                "sequence": 1,
                "previous_event_id": None,
                "previous_reasoning_mode": None,
                "reasoning_mode": reasoning_mode,
                "reason": reason.strip(),
                "actor": actor.strip(),
                "applies_to": "future_work_units_only",
                "frozen_work_units": (
                    "retain_original_mode_until_complete_or_explicit_abort"
                ),
                "reasoning_mode_policy_sha256": MODE_POLICY_SHA256,
                "fact_admission_contract_sha256": (
                    FACT_ADMISSION_CONTRACT_SHA256
                ),
                "created_at": _utc_now(),
            }
            event = {
                **event_semantic,
                "event_id": MODE_EVENT_PREFIX + sha256_json(event_semantic),
            }
            self.store._write_json_once(
                self.events_dir / f"{event['event_id']}.json",
                event,
            )
            self.store._append_jsonl(self.ledger_path, event)
            self.store._write_json_atomic(
                self.current_path,
                self._current_projection(event),
            )

            legacy_round_inventory = self._round_inventory()
            receipt_semantic = {
                "schema_version": 2,
                "policy_revision": UNIFIED_POLICY_REVISION,
                "project_id": self.store.project_id(),
                "source_kind": source_kind,
                "actor": actor.strip(),
                "reason": reason.strip(),
                "initial_event_id": event["event_id"],
                "initial_reasoning_mode": reasoning_mode,
                "reasoning_mode_policy_sha256": MODE_POLICY_SHA256,
                "fact_admission_contract_sha256": (
                    FACT_ADMISSION_CONTRACT_SHA256
                ),
                "legacy_round_inventory": legacy_round_inventory,
                "legacy_round_inventory_sha256": sha256_json(
                    legacy_round_inventory
                ),
                "legacy_admission_inventory": (
                    legacy_admission_inventory
                ),
                "legacy_admission_inventory_sha256": sha256_json(
                    legacy_admission_inventory
                ),
                "created_at": event["created_at"],
            }
            receipt = {
                **receipt_semantic,
                "receipt_id": MODE_INITIALIZATION_RECEIPT_PREFIX
                + sha256_json(receipt_semantic),
            }
            self.store._write_json_once(self.activation_receipt_path, receipt)
        return self.status()

    def _validate_activation_receipt(self, receipt: Any) -> dict[str, Any]:
        if not isinstance(receipt, dict):
            raise ValueError("mode activation receipt must be one object")
        require_exact_keys(
            receipt,
            required={
                "schema_version",
                "policy_revision",
                "project_id",
                "source_kind",
                "actor",
                "reason",
                "initial_event_id",
                "initial_reasoning_mode",
                "reasoning_mode_policy_sha256",
                "fact_admission_contract_sha256",
                "legacy_round_inventory",
                "legacy_round_inventory_sha256",
                "legacy_admission_inventory",
                "legacy_admission_inventory_sha256",
                "created_at",
                "receipt_id",
            },
            label="mode activation receipt",
        )
        if receipt.get("schema_version") != 2:
            raise ValueError("mode activation receipt schema_version must be 2")
        if receipt.get("policy_revision") != UNIFIED_POLICY_REVISION:
            raise ValueError("mode activation receipt policy mismatch")
        if receipt.get("project_id") != self.store.project_id():
            raise ValueError("mode activation receipt project mismatch")
        if receipt.get("source_kind") not in {
            "new_unified_project",
            "legacy_chalk_v4_upgrade",
            "new_v5_project",
        }:
            raise ValueError("mode activation receipt source kind is invalid")
        _require_reasoning_mode(receipt.get("initial_reasoning_mode"))
        for key, expected in (
            ("reasoning_mode_policy_sha256", MODE_POLICY_SHA256),
            (
                "fact_admission_contract_sha256",
                FACT_ADMISSION_CONTRACT_SHA256,
            ),
        ):
            if receipt.get(key) != expected:
                raise ValueError(f"mode activation receipt {key} mismatch")
        inventory = receipt.get("legacy_round_inventory")
        if not isinstance(inventory, dict) or any(
            not isinstance(round_id, str)
            or ROUND_ID_RE.fullmatch(round_id) is None
            or not isinstance(digest, str)
            or SHA256_RE.fullmatch(digest) is None
            for round_id, digest in inventory.items()
        ):
            raise ValueError("mode activation legacy round inventory is invalid")
        if receipt.get("legacy_round_inventory_sha256") != sha256_json(inventory):
            raise ValueError("mode activation legacy round inventory hash mismatch")
        admission_inventory = self._validate_legacy_admission_inventory(
            receipt.get("legacy_admission_inventory")
        )
        if receipt.get("legacy_admission_inventory_sha256") != sha256_json(
            admission_inventory
        ):
            raise ValueError(
                "mode activation legacy admission inventory hash mismatch"
            )
        semantic = {key: value for key, value in receipt.items() if key != "receipt_id"}
        if receipt.get("receipt_id") != MODE_INITIALIZATION_RECEIPT_PREFIX + sha256_json(
            semantic
        ):
            raise ValueError("mode activation receipt id/hash mismatch")
        return receipt

    def status(self) -> dict[str, Any]:
        if (
            self.store.project_path.exists()
            and self.store.workflow_evidence_version() < 4
        ):
            return {
                "initialized": False,
                "compatibility": "native_graph_operation_no_upgrade_required",
                "reasoning_modes": list(REASONING_MODES),
                "reasoning_mode_policy_sha256": MODE_POLICY_SHA256,
                "fact_admission_contract_sha256": (
                    FACT_ADMISSION_CONTRACT_SHA256
                ),
            }
        if not self.has_any_state():
            return {
                "initialized": False,
                "compatibility": "native_graph_operation_mode_optional",
                "reasoning_modes": list(REASONING_MODES),
                "reasoning_mode_policy_sha256": MODE_POLICY_SHA256,
                "fact_admission_contract_sha256": (
                    FACT_ADMISSION_CONTRACT_SHA256
                ),
            }
        if not self.is_initialized():
            raise ValueError("partial unified mode governance state")
        events = self.events()
        if not events:
            raise ValueError("mode ledger is empty")
        current = self.store._read_json(self.current_path)
        expected_current = self._current_projection(events[-1])
        if current != expected_current:
            raise ValueError("current reasoning-mode projection is stale or invalid")
        receipt = self._validate_activation_receipt(
            self.store._read_json(self.activation_receipt_path)
        )
        return {
            "initialized": True,
            "reasoning_mode": current["reasoning_mode"],
            "reasoning_mode_event_id": current["reasoning_mode_event_id"],
            "sequence": current["sequence"],
            "reasoning_mode_policy_sha256": MODE_POLICY_SHA256,
            "fact_admission_contract_sha256": FACT_ADMISSION_CONTRACT_SHA256,
            "activation_receipt_id": receipt["receipt_id"],
            "future_work_units_only": True,
        }

    @contextmanager
    def _lifecycle_mutation_lock(self, *, command: str) -> Iterator[None]:
        """Use the lock owned by the current workflow lifecycle.

        Public mode operations are lifecycle operations, not legacy-writer
        calls.  Keeping the choice here means an agent can call the API
        directly on a V5 graph; callers do not need to know about an adapter
        or wrap the operation in a second compatibility protocol.  V4 keeps
        its existing lock semantics while V5 receives the named lifecycle
        authority required by the store.
        """

        if self.store.workflow_evidence_version() == 5:
            with self.store.v5_mutation_lock(command=command):
                yield
        else:
            with self.store.mutation_lock():
                yield

    def switch(
        self,
        *,
        to_mode: str,
        actor: str,
        reason: str,
    ) -> dict[str, Any]:
        to_mode = _require_reasoning_mode(to_mode)
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError("mode switch actor must be nonempty")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("mode switch reason must be nonempty")
        with self._lifecycle_mutation_lock(command="mode-switch"):
            current = self.status()
            if not current["initialized"]:
                raise ValueError("run mode-init before switching modes")
            if current["reasoning_mode"] == to_mode:
                return {**current, "changed": False}
            previous_event = self.events()[-1]
            event_semantic = {
                "schema_version": 1,
                "policy_revision": UNIFIED_POLICY_REVISION,
                "event": "mode_switched",
                "project_id": self.store.project_id(),
                "sequence": previous_event["sequence"] + 1,
                "previous_event_id": previous_event["event_id"],
                "previous_reasoning_mode": previous_event["reasoning_mode"],
                "reasoning_mode": to_mode,
                "reason": reason.strip(),
                "actor": actor.strip(),
                "applies_to": "future_work_units_only",
                "frozen_work_units": (
                    "retain_original_mode_until_complete_or_explicit_abort"
                ),
                "reasoning_mode_policy_sha256": MODE_POLICY_SHA256,
                "fact_admission_contract_sha256": (
                    FACT_ADMISSION_CONTRACT_SHA256
                ),
                "created_at": _utc_now(),
            }
            event = {
                **event_semantic,
                "event_id": MODE_EVENT_PREFIX + sha256_json(event_semantic),
            }
            self.store._write_json_once(
                self.events_dir / f"{event['event_id']}.json",
                event,
            )
            self.store._append_jsonl(self.ledger_path, event)
            self.store._write_json_atomic(
                self.current_path,
                self._current_projection(event),
            )
        return {**self.status(), "changed": True}

    def binding_for_new_work_unit(
        self,
        *,
        adoption_binding: dict[str, Any],
    ) -> dict[str, Any]:
        current = self.status()
        if not current["initialized"]:
            raise ValueError(
                "reasoning-mode binding is unavailable until mode-init; "
                "ordinary graph operations remain available"
            )
        execution_profile = build_execution_profile(
            reasoning_mode=current["reasoning_mode"],
            reasoning_mode_event_id=current["reasoning_mode_event_id"],
            adoption_binding=adoption_binding,
        )
        return {
            "reasoning_mode": current["reasoning_mode"],
            "reasoning_mode_event_id": current["reasoning_mode_event_id"],
            "reasoning_mode_policy_sha256": MODE_POLICY_SHA256,
            "fact_admission_contract_sha256": FACT_ADMISSION_CONTRACT_SHA256,
            "execution_profile": execution_profile,
        }

    def abort_work_unit(
        self,
        *,
        round_id: str,
        actor: str,
        reason: str,
    ) -> dict[str, Any]:
        if ROUND_ID_RE.fullmatch(round_id) is None:
            raise ValueError("invalid round id")
        if not actor.strip() or not reason.strip():
            raise ValueError("work-unit abort actor and reason must be nonempty")
        round_path = self.store.rounds_dir / round_id / "round.json"
        if not round_path.is_file() or round_path.is_symlink():
            raise ValueError("work-unit round manifest is missing or unsafe")
        abort_path = self.abort_dir / f"{round_id}.json"
        with self._lifecycle_mutation_lock(command="work-unit-abort"):
            semantic = {
                "schema_version": 1,
                "policy_revision": UNIFIED_POLICY_REVISION,
                "project_id": self.store.project_id(),
                "round_id": round_id,
                "round_manifest_sha256": sha256_bytes(round_path.read_bytes()),
                "actor": actor.strip(),
                "reason": reason.strip(),
                "effect": "reject_future_managed_work_for_this_frozen_unit",
                "created_at": _utc_now(),
            }
            receipt = {
                **semantic,
                "abort_id": WORK_UNIT_ABORT_PREFIX + sha256_json(semantic),
            }
            self.store._write_json_once(abort_path, receipt)
        return receipt

    def require_work_unit_active(self, round_id: str) -> None:
        require_unaborted_work_unit(self.store.root, round_id)

    def work_unit_abort(self, round_id: str) -> dict[str, Any] | None:
        """Return one validated abort authority without mutating its projection."""

        if ROUND_ID_RE.fullmatch(round_id) is None:
            raise ValueError("invalid round id")
        path = self.abort_dir / f"{round_id}.json"
        if not path.exists() and not path.is_symlink():
            return None
        if path.is_symlink() or not path.is_file():
            raise ValueError("work-unit abort record is missing or unsafe")
        return self._validate_abort(self.store._read_json(path), path=path)

    def work_unit_aborts(self) -> list[dict[str, Any]]:
        """Return every validated abort authority in deterministic round order."""

        if not self.abort_dir.exists() and not self.abort_dir.is_symlink():
            return []
        if self.abort_dir.is_symlink() or not self.abort_dir.is_dir():
            raise ValueError("work-unit abort directory is missing or unsafe")
        records: list[dict[str, Any]] = []
        for path in sorted(self.abort_dir.glob("*.json")):
            record = self.work_unit_abort(path.stem)
            if record is None:
                raise ValueError("work-unit abort record disappeared during inspection")
            records.append(record)
        return records

    def _validate_abort(self, payload: Any, *, path: Path) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("work-unit abort must be one object")
        require_exact_keys(
            payload,
            required={
                "schema_version",
                "policy_revision",
                "project_id",
                "round_id",
                "round_manifest_sha256",
                "actor",
                "reason",
                "effect",
                "created_at",
                "abort_id",
            },
            label="work-unit abort",
        )
        round_id = require_string(payload, "round_id")
        if path.stem != round_id or ROUND_ID_RE.fullmatch(round_id) is None:
            raise ValueError("work-unit abort path/id mismatch")
        if payload.get("schema_version") != 1 or payload.get(
            "policy_revision"
        ) != UNIFIED_POLICY_REVISION:
            raise ValueError("work-unit abort schema/policy mismatch")
        if payload.get("project_id") != self.store.project_id():
            raise ValueError("work-unit abort project mismatch")
        round_path = self.store.rounds_dir / round_id / "round.json"
        if (
            not round_path.is_file()
            or round_path.is_symlink()
            or payload.get("round_manifest_sha256")
            != sha256_bytes(round_path.read_bytes())
        ):
            raise ValueError("work-unit abort round manifest binding mismatch")
        if (
            payload.get("effect")
            != "reject_future_managed_work_for_this_frozen_unit"
        ):
            raise ValueError("work-unit abort effect mismatch")
        semantic = {key: value for key, value in payload.items() if key != "abort_id"}
        if payload.get("abort_id") != WORK_UNIT_ABORT_PREFIX + sha256_json(semantic):
            raise ValueError("work-unit abort id/hash mismatch")
        return payload

    def validate_round_binding(
        self,
        *,
        manifest: dict[str, Any],
        manifest_path: Path,
    ) -> None:
        receipt = self._validate_activation_receipt(
            self.store._read_json(self.activation_receipt_path)
        )
        present = _MODE_BINDING_FIELDS.intersection(manifest)
        if not present:
            legacy_digest = receipt["legacy_round_inventory"].get(
                manifest_path.parent.name
            )
            if legacy_digest == sha256_bytes(manifest_path.read_bytes()):
                return
            raise ValueError(
                "post-activation round lacks a unified reasoning-mode binding"
            )
        if present != _MODE_BINDING_FIELDS:
            raise ValueError("round has an incomplete reasoning-mode binding")
        if manifest["reasoning_mode_policy_sha256"] != MODE_POLICY_SHA256:
            raise ValueError("round reasoning-mode policy hash mismatch")
        if (
            manifest["fact_admission_contract_sha256"]
            != FACT_ADMISSION_CONTRACT_SHA256
        ):
            raise ValueError("round fact-admission contract hash mismatch")
        event_by_id = {event["event_id"]: event for event in self.events()}
        event = event_by_id.get(manifest["reasoning_mode_event_id"])
        if event is None:
            raise ValueError("round references an unknown reasoning-mode event")
        if event["reasoning_mode"] != manifest["reasoning_mode"]:
            raise ValueError("round reasoning mode/event mismatch")
        profiles = manifest["execution_profile"]
        if not isinstance(profiles, dict):
            raise ValueError("round execution_profile must map assignments to hashes")
        assignments = manifest.get("assignments", [])
        assignment_ids = {
            item.get("assignment_id")
            for item in assignments
            if isinstance(item, dict)
        }
        if set(profiles) != assignment_ids or any(
            not isinstance(value, str) or SHA256_RE.fullmatch(value) is None
            for value in profiles.values()
        ):
            raise ValueError("round execution-profile hash map mismatch")

    def audit(self) -> dict[str, Any]:
        errors: list[str] = []
        warnings: list[str] = []
        if not self.has_any_state():
            return {
                "initialized": False,
                "errors": [],
                "warnings": [
                    "legacy Chalk V4 project has no unified mode governance; "
                    "it is read-only under this engine until mode-init"
                ],
            }
        if not self.is_initialized():
            return {
                "initialized": False,
                "errors": ["partial unified mode governance state"],
                "warnings": [],
            }
        try:
            contract = self.store._read_json(self.contract_path)
            if contract != {
                "contract": FACT_ADMISSION_CONTRACT,
                "contract_sha256": FACT_ADMISSION_CONTRACT_SHA256,
            }:
                raise ValueError("fact-admission contract object/hash mismatch")
        except Exception as exc:
            errors.append(str(exc))
        try:
            policy = self.store._read_json(self.policy_path)
            if policy != {
                "policy": MODE_POLICY,
                "policy_sha256": MODE_POLICY_SHA256,
            }:
                raise ValueError("reasoning-mode policy object/hash mismatch")
        except Exception as exc:
            errors.append(str(exc))
        events: list[dict[str, Any]] = []
        try:
            events = self.events()
            if not events:
                raise ValueError("mode event ledger is empty")
            for index, event in enumerate(events, 1):
                if event["sequence"] != index:
                    raise ValueError("mode event sequence is not contiguous")
                if index == 1:
                    if event["event"] != "mode_initialized":
                        raise ValueError("first mode event is not initialization")
                else:
                    previous = events[index - 2]
                    if (
                        event["event"] != "mode_switched"
                        or event["previous_event_id"] != previous["event_id"]
                        or event["previous_reasoning_mode"]
                        != previous["reasoning_mode"]
                    ):
                        raise ValueError("mode event chain is broken")
                sidecar = self.events_dir / f"{event['event_id']}.json"
                if (
                    not sidecar.is_file()
                    or sidecar.is_symlink()
                    or self.store._read_json(sidecar) != event
                ):
                    raise ValueError("mode event sidecar is missing or mismatched")
            if set(path.stem for path in self.events_dir.glob("*.json")) != {
                event["event_id"] for event in events
            }:
                raise ValueError("unexpected or missing mode event sidecar")
            if self.store._read_json(self.current_path) != self._current_projection(
                events[-1]
            ):
                raise ValueError("current reasoning-mode projection is invalid")
            receipt = self._validate_activation_receipt(
                self.store._read_json(self.activation_receipt_path)
            )
            if (
                receipt["initial_event_id"] != events[0]["event_id"]
                or receipt["initial_reasoning_mode"]
                != events[0]["reasoning_mode"]
            ):
                raise ValueError("mode activation receipt/initial event mismatch")
        except Exception as exc:
            errors.append(str(exc))

        if events:
            for manifest_path in sorted(self.store.rounds_dir.glob("*/round.json")):
                try:
                    manifest = self.store._read_json(manifest_path)
                    if manifest.get("schema_version") == 4:
                        self.validate_round_binding(
                            manifest=manifest,
                            manifest_path=manifest_path,
                        )
                except Exception as exc:
                    errors.append(
                        f"round {manifest_path.parent.name}: {exc}"
                    )
            for path in sorted(self.abort_dir.glob("*.json")):
                try:
                    self._validate_abort(self.store._read_json(path), path=path)
                except Exception as exc:
                    errors.append(f"work-unit abort {path.name}: {exc}")
        return {
            "initialized": not errors,
            "errors": errors,
            "warnings": warnings,
            "event_count": len(events),
            "reasoning_mode": events[-1]["reasoning_mode"] if events else None,
            "reasoning_mode_policy_sha256": MODE_POLICY_SHA256,
            "fact_admission_contract_sha256": FACT_ADMISSION_CONTRACT_SHA256,
        }

from __future__ import annotations

import re
from typing import Any

from .contracts import SHA256_RE, sha256_json


V5_ASSURANCE_CONTRACT_REVISION = "chalxius-v5-assurance-0.4.3-1"
V5_LEGACY_ASSURANCE_CONTRACT_REVISION = "chalxius-v5-assurance-0.4.2-legacy"

_OBLIGATION_ID_RE = re.compile(r"[A-Za-z0-9._:-]+")
_RESEARCH_ID_RE = re.compile(r"[0-9a-f]{12}")
_SOURCE_STRENGTHS = {
    "fixed_object": 0,
    "local_family": 1,
    "relative_family": 2,
}
_RISK_SIGNALS = {
    "source_formula",
    "fixed_to_family_transport",
    "topology_extremal_invariants",
    "parametric_contour_substitution",
    "claimed_combinatorial_structure",
    "geometric_stage_typing",
    "program_math_semantic_alignment",
}
_TOPOLOGY_EDGE_CASES = {
    "genus_zero_left",
    "genus_zero_right",
    "both_positive_genus",
    "empty_inherited_cycles",
    "disc_bounding_cycle",
}
_STRUCTURE_KINDS = {"bijection", "involution", "matching", "pairing"}
_PROGRAM_MATH_LAYERS = (
    "formula_projection",
    "domain_projection",
    "representation_projection",
    "approximation_budget",
    "output_interpretation",
    "independent_checks",
)
_PROGRAM_MATH_APPROXIMATION_MODES = {
    "exact",
    "symbolic",
    "truncated",
    "numeric",
    "mixed",
}
_PROGRAM_MATH_CHECK_KINDS = {
    "independent_reimplementation",
    "symbolic_oracle",
    "metamorphic_relation",
    "degeneration_case",
    "boundary_exhaustion",
    "negative_control",
    "dimensional_analysis",
}
_PROGRAM_MATH_STRONG_CHECK_KINDS = {
    "independent_reimplementation",
    "symbolic_oracle",
    "metamorphic_relation",
}


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    return value.strip()


def _strings(value: Any, label: str, *, allow_empty: bool = True) -> list[str]:
    if (
        not isinstance(value, list)
        or (not allow_empty and not value)
        or any(not isinstance(item, str) or not item.strip() for item in value)
    ):
        qualifier = "a list" if allow_empty else "a nonempty list"
        raise ValueError(f"{label} must be {qualifier} of nonempty strings")
    return [item.strip() for item in value]


def _hashes(value: Any, label: str, *, allow_empty: bool = True) -> list[str]:
    values = _strings(value, label, allow_empty=allow_empty)
    if any(SHA256_RE.fullmatch(item) is None for item in values):
        raise ValueError(f"{label} must contain full lowercase SHA-256 values")
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must not contain duplicates")
    return values


def _exact(payload: Any, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != fields:
        raise ValueError(f"{label} fields are not exact")
    return payload


def normalize_obligations(obligations: Any) -> list[dict[str, Any]]:
    if not isinstance(obligations, list) or any(
        not isinstance(item, dict) for item in obligations
    ):
        raise ValueError("research obligations must be a list of objects")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(obligations, 1):
        raw_id = item.get("obligation_id", item.get("id"))
        if raw_id is None:
            obligation_id = "obl-" + sha256_json(item)[:12]
        else:
            obligation_id = _text(raw_id, f"obligation[{index}] id")
            if _OBLIGATION_ID_RE.fullmatch(obligation_id) is None:
                raise ValueError(
                    f"obligation[{index}] id may contain only ASCII letters, digits, . _ : -"
                )
        if obligation_id in seen:
            raise ValueError("research obligation ids must be unique")
        seen.add(obligation_id)
        description_value = item.get(
            "description",
            item.get("obligation", item.get("text", "")),
        )
        description = (
            description_value.strip()
            if isinstance(description_value, str) and description_value.strip()
            else f"Structured obligation {index}: {sha256_json(item)[:16]}"
        )
        roles = item.get("required_artifact_roles", [])
        required_roles = sorted(
            dict.fromkeys(
                _strings(
                    roles,
                    f"obligation[{index}].required_artifact_roles",
                )
            )
        )
        evidence_types_value = item.get("evidence_types")
        if evidence_types_value is None:
            lowered = description.casefold()
            if any(token in lowered for token in ("compute", "replay", "program", "symbolic")):
                evidence_types = [
                    "deterministic_output",
                    "executable_source",
                    "runtime_receipt",
                ]
            else:
                evidence_types = ["bounded_argument"]
        else:
            evidence_types = sorted(
                dict.fromkeys(
                    _strings(
                        evidence_types_value,
                        f"obligation[{index}].evidence_types",
                        allow_empty=False,
                    )
                )
            )
        not_applicable_allowed = item.get("not_applicable_allowed", False)
        if not isinstance(not_applicable_allowed, bool):
            raise ValueError(
                f"obligation[{index}].not_applicable_allowed must be boolean"
            )
        normalized.append(
            {
                "obligation_id": obligation_id,
                "description": description,
                "required_artifact_roles": required_roles,
                "evidence_types": evidence_types,
                "not_applicable_allowed": not_applicable_allowed,
                "source_sha256": sha256_json(item),
            }
        )
    return normalized


def detect_risk_signals(entry: dict[str, Any]) -> list[str]:
    metadata = entry.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("research metadata must be an object")
    declared = metadata.get("logic_signals", [])
    if not isinstance(declared, list) or any(not isinstance(item, str) for item in declared):
        raise ValueError("research logic_signals must be a list of strings")
    combined = "\n".join(
        str(entry.get(field, "")) for field in ("claim", "content", "source")
    ).casefold()
    signals: set[str] = set()
    declared_set = {item.casefold() for item in declared}
    workload = metadata.get("workload_profile", {})
    computation = workload.get("computation", {}) if isinstance(workload, dict) else {}
    stage_count = computation.get("stage_count", 0) if isinstance(computation, dict) else 0
    if isinstance(stage_count, bool) or not isinstance(stage_count, int) or stage_count < 0:
        raise ValueError("workload_profile.computation.stage_count must be nonnegative")
    if stage_count > 0 or declared_set.intersection(
        {
            "program_math_hybrid",
            "program_math_semantic_alignment",
            "formula_to_code",
            "computational_semantics",
        }
    ):
        signals.add("program_math_semantic_alignment")
    if declared_set.intersection(
        {"source_formula", "formula_use", "formula_sensitive"}
    ):
        signals.add("source_formula")
    if declared_set.intersection(
        {"fixed_to_family", "fixed_to_family_transport", "source_strength"}
    ):
        signals.add("fixed_to_family_transport")
    if declared_set.intersection(
        {"topology", "topology_extremal", "genus_sensitive", "dehn_twist"}
    ) or any(token in combined for token in ("dehn twist", "vanishing cycle")):
        signals.add("topology_extremal_invariants")
    if declared_set.intersection(
        {"geometric_stage", "ambient_fiber", "capped_resewn", "cycle_ownership"}
    ) or any(
        token in combined
        for token in ("capped family", "nodal", "resewn", "re-sewn", "neck core")
    ):
        signals.add("geometric_stage_typing")
    if declared_set.intersection(
        {"parametric_contour", "contour_substitution", "moving_poles"}
    ) or ("contour" in combined and "residue" in combined and "parameter" in combined):
        signals.add("parametric_contour_substitution")
    if declared_set.intersection(
        {"claimed_bijection", "claimed_involution", "claimed_matching", "claimed_pairing"}
    ) or any(token in combined for token in ("bijection", "involution")):
        signals.add("claimed_combinatorial_structure")
    source_uses = metadata.get("source_uses", [])
    if isinstance(source_uses, list):
        for item in source_uses:
            if not isinstance(item, dict):
                continue
            if item.get("use_kind") == "formula":
                signals.add("source_formula")
            source_strength = item.get("source_strength")
            target_strength = item.get("target_strength")
            if (
                source_strength in _SOURCE_STRENGTHS
                and target_strength in _SOURCE_STRENGTHS
                and _SOURCE_STRENGTHS[str(target_strength)]
                > _SOURCE_STRENGTHS[str(source_strength)]
            ):
                signals.add("fixed_to_family_transport")
    return sorted(signals)


def build_assurance_contract(
    *,
    entry: dict[str, Any],
    obligations: Any,
    work_mode: str,
    related_artifacts: list[dict[str, str]],
) -> dict[str, Any]:
    normalized_obligations = normalize_obligations(obligations)
    metadata = entry.get("metadata", {})
    workload = metadata.get("workload_profile", {}) if isinstance(metadata, dict) else {}
    computation = workload.get("computation", {}) if isinstance(workload, dict) else {}
    stage_count = computation.get("stage_count", 0) if isinstance(computation, dict) else 0
    if isinstance(stage_count, bool) or not isinstance(stage_count, int) or stage_count < 0:
        raise ValueError("workload_profile.computation.stage_count must be nonnegative")
    if work_mode == "compute" and stage_count == 0:
        stage_count = 1
    if stage_count > 0 and not any(
        {"computation_source", "computation_output"}.issubset(
            set(item["required_artifact_roles"])
        )
        for item in normalized_obligations
    ):
        generated = {
            "kind": "generated_computation_contract",
            "stage_count": stage_count,
        }
        normalized_obligations.append(
            {
                "obligation_id": "obl-computation-contract",
                "description": (
                    "Bind executable source, deterministic output, argv command, "
                    "runtime/version receipt, role, and manual program-mathematics contract."
                ),
                "required_artifact_roles": [
                    "computation_output",
                    "computation_source",
                ],
                "evidence_types": [
                    "deterministic_output",
                    "executable_source",
                    "runtime_receipt",
                ],
                "not_applicable_allowed": False,
                "source_sha256": sha256_json(generated),
            }
        )
    return {
        "revision": V5_ASSURANCE_CONTRACT_REVISION,
        "activation": "prospective_new_task_card_only",
        "legacy_frozen_cards": "preserve_original_schema_and_status",
        "required_return_fields": [
            "obligation_dispositions",
            "computation_manifest",
            "research_assurance",
        ],
        "obligations": normalized_obligations,
        "computation_stage_count": stage_count,
        "program_math_contract": {
            "required": stage_count > 0,
            "activation": "computation_stage_count_gt_zero",
            "required_layers": list(_PROGRAM_MATH_LAYERS),
            "research_stage_adverse_policy": (
                "enqueue_typed_review_when_project_adverse_routing_enabled"
            ),
            "architecture_issue_import": "forbidden",
        },
        "risk_signals": detect_risk_signals(entry),
        "related_artifact_roles": sorted(
            dict.fromkeys(item["role"] for item in related_artifacts)
        ),
    }


def validate_assurance_contract(payload: Any) -> dict[str, Any]:
    contract = _exact(
        payload,
        {
            "revision",
            "activation",
            "legacy_frozen_cards",
            "required_return_fields",
            "obligations",
            "computation_stage_count",
            "program_math_contract",
            "risk_signals",
            "related_artifact_roles",
        },
        "V5 assurance contract",
    )
    if (
        contract["revision"] != V5_ASSURANCE_CONTRACT_REVISION
        or contract["activation"] != "prospective_new_task_card_only"
        or contract["legacy_frozen_cards"] != "preserve_original_schema_and_status"
        or contract["required_return_fields"]
        != ["obligation_dispositions", "computation_manifest", "research_assurance"]
    ):
        raise ValueError("V5 assurance contract revision/policy is invalid")
    obligations = contract["obligations"]
    if not isinstance(obligations, list):
        raise ValueError("V5 assurance obligations must be a list")
    ids: set[str] = set()
    for index, item in enumerate(obligations, 1):
        _exact(
            item,
            {
                "obligation_id",
                "description",
                "required_artifact_roles",
                "evidence_types",
                "not_applicable_allowed",
                "source_sha256",
            },
            f"V5 assurance obligation[{index}]",
        )
        obligation_id = _text(item["obligation_id"], "obligation id")
        if _OBLIGATION_ID_RE.fullmatch(obligation_id) is None or obligation_id in ids:
            raise ValueError("V5 assurance obligation ids are invalid or duplicated")
        ids.add(obligation_id)
        _text(item["description"], "obligation description")
        _strings(item["required_artifact_roles"], "required artifact roles")
        _strings(item["evidence_types"], "obligation evidence types", allow_empty=False)
        if not isinstance(item["not_applicable_allowed"], bool):
            raise ValueError("obligation not_applicable_allowed must be boolean")
        if not isinstance(item["source_sha256"], str) or SHA256_RE.fullmatch(
            item["source_sha256"]
        ) is None:
            raise ValueError("obligation source_sha256 is invalid")
    stage_count = contract["computation_stage_count"]
    if isinstance(stage_count, bool) or not isinstance(stage_count, int) or stage_count < 0:
        raise ValueError("V5 assurance computation_stage_count is invalid")
    program_math = _exact(
        contract["program_math_contract"],
        {
            "required",
            "activation",
            "required_layers",
            "research_stage_adverse_policy",
            "architecture_issue_import",
        },
        "V5 program-math contract",
    )
    if (
        program_math["required"] is not (stage_count > 0)
        or program_math["activation"] != "computation_stage_count_gt_zero"
        or program_math["required_layers"] != list(_PROGRAM_MATH_LAYERS)
        or program_math["research_stage_adverse_policy"]
        != "enqueue_typed_review_when_project_adverse_routing_enabled"
        or program_math["architecture_issue_import"] != "forbidden"
    ):
        raise ValueError("V5 program-math contract is invalid")
    signals = _strings(contract["risk_signals"], "V5 assurance risk signals")
    if len(signals) != len(set(signals)) or not set(signals).issubset(_RISK_SIGNALS):
        raise ValueError("V5 assurance risk signals are invalid or duplicated")
    roles = _strings(contract["related_artifact_roles"], "related artifact roles")
    if len(roles) != len(set(roles)):
        raise ValueError("related artifact roles must not be duplicated")
    return contract


def validate_contour_substitution(payload: Any, *, label: str) -> dict[str, Any]:
    item = _exact(
        payload,
        {
            "source_contour",
            "target_contour",
            "swept_region",
            "poles",
            "crossed_pole_ids",
            "uniform_noncollision_witness",
            "residue_accounting",
            "degeneration_test",
        },
        label,
    )
    for key in ("source_contour", "target_contour", "swept_region"):
        _text(item[key], f"{label}.{key}")
    poles = item["poles"]
    if not isinstance(poles, list) or not poles or any(
        not isinstance(pole, dict) for pole in poles
    ):
        raise ValueError(f"{label}.poles must be a nonempty list of objects")
    pole_ids: set[str] = set()
    dispositions: dict[str, str] = {}
    for index, pole in enumerate(poles, 1):
        _exact(
            pole,
            {"pole_id", "multiplicity", "parameter_behavior", "disposition"},
            f"{label}.poles[{index}]",
        )
        pole_id = _text(pole["pole_id"], f"{label}.poles[{index}].pole_id")
        if pole_id in pole_ids:
            raise ValueError(f"{label}.poles has duplicate pole ids")
        pole_ids.add(pole_id)
        multiplicity = pole["multiplicity"]
        if isinstance(multiplicity, bool) or not isinstance(multiplicity, int) or multiplicity < 1:
            raise ValueError(f"{label}.poles[{index}].multiplicity must be positive")
        _text(pole["parameter_behavior"], f"{label}.poles[{index}].parameter_behavior")
        disposition = _text(pole["disposition"], f"{label}.poles[{index}].disposition")
        if disposition not in {
            "distinguished",
            "excluded_by_uniform_witness",
            "retained_additional_residue",
        }:
            raise ValueError(f"{label}.poles[{index}].disposition is invalid")
        dispositions[pole_id] = disposition
    crossed = _strings(item["crossed_pole_ids"], f"{label}.crossed_pole_ids")
    if len(crossed) != len(set(crossed)) or not set(crossed).issubset(pole_ids):
        raise ValueError(f"{label}.crossed_pole_ids are invalid or duplicated")
    witness = _text(
        item["uniform_noncollision_witness"],
        f"{label}.uniform_noncollision_witness",
    )
    accounting = item["residue_accounting"]
    if accounting not in {
        "distinguished_is_complete_enclosed_sum",
        "all_additional_residues_retained",
    }:
        raise ValueError(f"{label}.residue_accounting is invalid")
    if accounting == "distinguished_is_complete_enclosed_sum":
        if crossed or any(
            disposition == "retained_additional_residue"
            for disposition in dispositions.values()
        ):
            raise ValueError(
                f"{label} cannot claim a distinguished complete residue while crossing or retaining additional poles"
            )
        if "uniform" not in witness.casefold():
            raise ValueError(f"{label} complete-residue claim needs an explicit uniform witness")
    else:
        unretained = [
            pole_id
            for pole_id in crossed
            if dispositions[pole_id] != "retained_additional_residue"
        ]
        if unretained:
            raise ValueError(
                f"{label} crossed poles are not retained: {', '.join(sorted(unretained))}"
            )
    test = _exact(
        item["degeneration_test"],
        {"family", "boundary_behavior", "interior_zero_behavior", "result"},
        f"{label}.degeneration_test",
    )
    for key in ("family", "boundary_behavior", "interior_zero_behavior", "result"):
        _text(test[key], f"{label}.degeneration_test.{key}")
    return item


def validate_return_assurance(
    *,
    payload: dict[str, Any],
    contract: dict[str, Any],
    artifacts: list[dict[str, str]],
    artifact_bytes_by_sha256: dict[str, bytes] | None = None,
) -> dict[str, Any]:
    validate_assurance_contract(contract)
    artifact_hashes = {item["sha256"] for item in artifacts}
    artifact_by_role = {item["role"]: item["sha256"] for item in artifacts}
    dispositions = payload.get("obligation_dispositions")
    if not isinstance(dispositions, list) or any(
        not isinstance(item, dict) for item in dispositions
    ):
        raise ValueError("obligation_dispositions must be a list of objects")
    expected = {item["obligation_id"]: item for item in contract["obligations"]}
    actual: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(dispositions, 1):
        _exact(
            item,
            {"obligation_id", "status", "witness_artifact_sha256s", "rationale"},
            f"obligation_dispositions[{index}]",
        )
        obligation_id = _text(item["obligation_id"], "obligation disposition id")
        if obligation_id in actual:
            raise ValueError("obligation dispositions contain duplicate ids")
        if obligation_id not in expected:
            raise ValueError(f"unknown obligation disposition id: {obligation_id}")
        status = item["status"]
        if status not in {"complete", "blocked", "not_applicable"}:
            raise ValueError("obligation disposition status is invalid")
        witnesses = _hashes(
            item["witness_artifact_sha256s"],
            f"obligation_dispositions[{index}].witness_artifact_sha256s",
        )
        if not set(witnesses).issubset(artifact_hashes):
            raise ValueError("obligation disposition cites an undeclared artifact hash")
        rationale = _text(item["rationale"], "obligation disposition rationale")
        obligation = expected[obligation_id]
        if status == "not_applicable" and not obligation["not_applicable_allowed"]:
            raise ValueError(f"obligation {obligation_id} does not permit not_applicable")
        if status == "complete":
            required_hashes = {
                artifact_by_role[role]
                for role in obligation["required_artifact_roles"]
                if role in artifact_by_role
            }
            missing_roles = sorted(
                set(obligation["required_artifact_roles"]).difference(artifact_by_role)
            )
            if missing_roles:
                raise ValueError(
                    f"obligation {obligation_id} lacks required artifact roles: "
                    + ", ".join(missing_roles)
                )
            if not required_hashes.issubset(witnesses):
                raise ValueError(
                    f"obligation {obligation_id} does not bind all required artifact witnesses"
                )
        actual[obligation_id] = {
            "obligation_id": obligation_id,
            "status": status,
            "witness_artifact_sha256s": witnesses,
            "rationale": rationale,
        }
    if set(actual) != set(expected):
        raise ValueError(
            "obligation dispositions do not exactly cover task-card obligations; "
            f"missing={sorted(set(expected).difference(actual))}"
        )
    if payload.get("outcome") == "proof" and any(
        item["status"] == "blocked" for item in actual.values()
    ):
        raise ValueError("a proof return cannot mark an obligation blocked")

    manifest = payload.get("computation_manifest")
    stage_count = contract["computation_stage_count"]
    manifest_entries: list[dict[str, Any]] = []
    if stage_count == 0:
        if manifest is not None:
            raise ValueError("computation_manifest must be null when no computation stage is required")
    else:
        manifest = _exact(
            manifest,
            {"stage_count", "entries"},
            "computation_manifest",
        )
        if manifest["stage_count"] != stage_count:
            raise ValueError("computation_manifest stage_count does not match the task card")
        entries = manifest["entries"]
        if not isinstance(entries, list) or len(entries) != stage_count or any(
            not isinstance(item, dict) for item in entries
        ):
            raise ValueError("computation_manifest entries must exactly cover every stage")
        for index, item in enumerate(entries, 1):
            _exact(
                item,
                {
                    "obligation_id",
                    "source_artifact_sha256",
                    "output_artifact_sha256",
                    "command",
                    "runtime",
                    "role",
                    "manual_contract",
                },
                f"computation_manifest.entries[{index}]",
            )
            obligation_id = _text(item["obligation_id"], "computation obligation id")
            if obligation_id not in expected:
                raise ValueError("computation manifest references an unknown obligation")
            for key in ("source_artifact_sha256", "output_artifact_sha256"):
                digest = item[key]
                if not isinstance(digest, str) or digest not in artifact_hashes:
                    raise ValueError(f"computation manifest {key} is not artifact-bound")
            command = _strings(
                item["command"],
                "computation manifest command",
                allow_empty=False,
            )
            if any(argument.startswith("/") or ".." in argument.split("/") for argument in command[1:]):
                raise ValueError("computation manifest command escapes the artifact capability")
            runtime = _exact(
                item["runtime"],
                {"implementation", "version"},
                "computation manifest runtime",
            )
            _text(runtime["implementation"], "runtime implementation")
            _text(runtime["version"], "runtime version")
            if item["role"] not in {"load_bearing", "supporting"}:
                raise ValueError("computation manifest role is invalid")
            _text(item["manual_contract"], "computation manual contract")
            manifest_entries.append(item)

    assurance = _exact(
        payload.get("research_assurance"),
        {
            "source_uses",
            "route_invalidations",
            "extremal_cases",
            "claim_strength",
            "contour_substitutions",
            "claimed_structures",
            "program_math_alignments",
        },
        "research_assurance",
    )
    source_uses = assurance["source_uses"]
    if not isinstance(source_uses, list) or any(not isinstance(item, dict) for item in source_uses):
        raise ValueError("research_assurance.source_uses must be a list of objects")
    has_formula = False
    has_strength_bridge = False
    for index, item in enumerate(source_uses, 1):
        _exact(
            item,
            {
                "source_key",
                "use_kind",
                "source_strength",
                "target_strength",
                "source_artifact_sha256",
                "toy_check_artifact_sha256",
                "bridge_artifact_sha256s",
            },
            f"research_assurance.source_uses[{index}]",
        )
        _text(item["source_key"], "source-use key")
        if item["use_kind"] not in {"result", "definition", "formula"}:
            raise ValueError("research source use_kind is invalid")
        if item["source_strength"] not in _SOURCE_STRENGTHS or item["target_strength"] not in _SOURCE_STRENGTHS:
            raise ValueError("research source strength is invalid")
        source_hash = item["source_artifact_sha256"]
        if not isinstance(source_hash, str) or source_hash not in artifact_hashes:
            raise ValueError("research source use is not bound to a returned artifact")
        toy_hash = item["toy_check_artifact_sha256"]
        if item["use_kind"] == "formula":
            has_formula = True
            if not isinstance(toy_hash, str) or toy_hash not in artifact_hashes:
                raise ValueError("research formula use requires an artifact-bound toy check")
        elif toy_hash is not None:
            if not isinstance(toy_hash, str) or toy_hash not in artifact_hashes:
                raise ValueError("research toy-check hash is not artifact-bound")
        bridges = _hashes(
            item["bridge_artifact_sha256s"],
            f"research_assurance.source_uses[{index}].bridge_artifact_sha256s",
        )
        if not set(bridges).issubset(artifact_hashes):
            raise ValueError("research source bridge is not artifact-bound")
        if _SOURCE_STRENGTHS[item["target_strength"]] > _SOURCE_STRENGTHS[item["source_strength"]]:
            has_strength_bridge = True
            if not bridges:
                raise ValueError("fixed-object to stronger family use requires a bridge artifact")

    invalidations = _strings(
        assurance["route_invalidations"],
        "research_assurance.route_invalidations",
    )
    if len(invalidations) != len(set(invalidations)) or any(
        _RESEARCH_ID_RE.fullmatch(item) is None for item in invalidations
    ):
        raise ValueError("route invalidations must be unique V5 Research ids")
    if invalidations and payload.get("outcome") not in {
        "counterexample",
        "challenge",
        "dead_end",
    }:
        raise ValueError("only an adverse or dead-end return may invalidate a Research route")

    cases = assurance["extremal_cases"]
    if not isinstance(cases, list) or any(not isinstance(item, dict) for item in cases):
        raise ValueError("research_assurance.extremal_cases must be a list of objects")
    case_ids: set[str] = set()
    for index, item in enumerate(cases, 1):
        _exact(
            item,
            {"case_id", "status", "witness_artifact_sha256s", "finding"},
            f"research_assurance.extremal_cases[{index}]",
        )
        case_id = _text(item["case_id"], "extremal case id")
        if case_id in case_ids:
            raise ValueError("extremal cases contain duplicate ids")
        case_ids.add(case_id)
        if item["status"] not in {"pass", "counterexample", "not_applicable"}:
            raise ValueError("extremal case status is invalid")
        witnesses = _hashes(item["witness_artifact_sha256s"], "extremal case witnesses")
        if not set(witnesses).issubset(artifact_hashes):
            raise ValueError("extremal case cites an undeclared artifact")
        _text(item["finding"], "extremal case finding")

    strengths = assurance["claim_strength"]
    if not isinstance(strengths, list) or any(not isinstance(item, dict) for item in strengths):
        raise ValueError("research_assurance.claim_strength must be a list of objects")
    for index, item in enumerate(strengths, 1):
        _exact(
            item,
            {
                "claim_id",
                "claimed_strength",
                "downstream_required_strength",
                "comparison",
                "disposition",
                "rationale",
            },
            f"research_assurance.claim_strength[{index}]",
        )
        for key in ("claim_id", "claimed_strength", "downstream_required_strength", "rationale"):
            _text(item[key], f"claim strength {key}")
        if item["comparison"] not in {"equal", "stronger_than_required"}:
            raise ValueError("claim strength comparison is invalid")
        if item["comparison"] == "stronger_than_required" and item["disposition"] not in {
            "pruned",
            "retained_with_necessity",
        }:
            raise ValueError("a stronger claim must be pruned or justified as necessary")
        if item["comparison"] == "equal" and item["disposition"] != "retained":
            raise ValueError("an equal-strength claim must use disposition=retained")

    contours = assurance["contour_substitutions"]
    if not isinstance(contours, list):
        raise ValueError("research_assurance.contour_substitutions must be a list")
    for index, contour in enumerate(contours, 1):
        validate_contour_substitution(
            contour,
            label=f"research_assurance.contour_substitutions[{index}]",
        )

    structures = assurance["claimed_structures"]
    if not isinstance(structures, list) or any(not isinstance(item, dict) for item in structures):
        raise ValueError("research_assurance.claimed_structures must be a list of objects")
    for index, item in enumerate(structures, 1):
        _exact(
            item,
            {
                "kind",
                "domain_artifact_sha256",
                "forward_map_artifact_sha256",
                "inverse_map_artifact_sha256",
                "multiplicity_artifact_sha256",
                "negative_control_artifact_sha256",
                "typed_record_fields",
                "automorphism_controls",
                "value_free",
            },
            f"research_assurance.claimed_structures[{index}]",
        )
        if item["kind"] not in _STRUCTURE_KINDS:
            raise ValueError("claimed structure kind is invalid")
        for key in (
            "domain_artifact_sha256",
            "forward_map_artifact_sha256",
            "inverse_map_artifact_sha256",
            "multiplicity_artifact_sha256",
            "negative_control_artifact_sha256",
        ):
            if not isinstance(item[key], str) or item[key] not in artifact_hashes:
                raise ValueError(f"claimed structure {key} is not artifact-bound")
        fields = _strings(item["typed_record_fields"], "claimed structure typed fields", allow_empty=False)
        if not {"occurrence_identity", "multiplicity"}.issubset(set(fields)):
            raise ValueError("claimed structure must retain occurrence_identity and multiplicity")
        _strings(item["automorphism_controls"], "claimed structure automorphism controls", allow_empty=False)
        if item["value_free"] is not True:
            raise ValueError("claimed structure validation must be value-free")

    alignments = assurance["program_math_alignments"]
    if not isinstance(alignments, list) or any(
        not isinstance(item, dict) for item in alignments
    ):
        raise ValueError(
            "research_assurance.program_math_alignments must be a list of objects"
        )
    if len(alignments) != stage_count:
        raise ValueError(
            "program-math alignments must exactly cover every computation stage"
        )
    manifest_by_stage = {
        index: item for index, item in enumerate(manifest_entries, 1)
    }
    seen_stages: set[int] = set()
    artifact_bytes_by_sha256 = artifact_bytes_by_sha256 or {}
    for index, item in enumerate(alignments, 1):
        label = f"research_assurance.program_math_alignments[{index}]"
        _exact(
            item,
            {
                "stage_index",
                "obligation_id",
                "formula_projection",
                "domain_projection",
                "representation_projection",
                "approximation_budget",
                "output_interpretation",
                "independent_checks",
            },
            label,
        )
        stage_index = item["stage_index"]
        if (
            isinstance(stage_index, bool)
            or not isinstance(stage_index, int)
            or stage_index not in manifest_by_stage
            or stage_index in seen_stages
        ):
            raise ValueError(f"{label}.stage_index is invalid or duplicated")
        seen_stages.add(stage_index)
        manifest_entry = manifest_by_stage[stage_index]
        obligation_id = _text(item["obligation_id"], f"{label}.obligation_id")
        if obligation_id != manifest_entry["obligation_id"]:
            raise ValueError(f"{label} obligation does not match its computation stage")

        formula = _exact(
            item["formula_projection"],
            {
                "formula_literal",
                "formula_sha256",
                "source_locator",
                "code_artifact_sha256",
                "code_anchor",
                "sign_and_convention_map",
            },
            f"{label}.formula_projection",
        )
        formula_literal = _text(
            formula["formula_literal"], f"{label}.formula_projection.formula_literal"
        )
        if formula["formula_sha256"] != sha256_json(formula_literal):
            raise ValueError(f"{label} formula literal/hash binding is invalid")
        _text(formula["source_locator"], f"{label}.formula_projection.source_locator")
        if formula["code_artifact_sha256"] != manifest_entry["source_artifact_sha256"]:
            raise ValueError(f"{label} formula projection is not bound to the stage source")
        code_anchor = _text(
            formula["code_anchor"], f"{label}.formula_projection.code_anchor"
        )
        convention_map = _strings(
            formula["sign_and_convention_map"],
            f"{label}.formula_projection.sign_and_convention_map",
            allow_empty=False,
        )
        if len(convention_map) != len(set(convention_map)):
            raise ValueError(f"{label} sign/convention map contains duplicates")
        source_bytes = artifact_bytes_by_sha256.get(
            manifest_entry["source_artifact_sha256"]
        )
        if source_bytes is not None:
            try:
                source_text = source_bytes.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError(f"{label} computation source must be UTF-8 text") from exc
            if source_text.count(code_anchor) != 1:
                raise ValueError(
                    f"{label} code anchor must occur exactly once in the bound source"
                )

        domain = _exact(
            item["domain_projection"],
            {
                "mathematical_domain",
                "code_iteration_domain",
                "boundary_cases",
                "witness_artifact_sha256",
            },
            f"{label}.domain_projection",
        )
        _text(domain["mathematical_domain"], f"{label}.domain_projection.mathematical_domain")
        _text(domain["code_iteration_domain"], f"{label}.domain_projection.code_iteration_domain")
        boundary_cases = _strings(
            domain["boundary_cases"],
            f"{label}.domain_projection.boundary_cases",
            allow_empty=False,
        )
        if len(boundary_cases) != len(set(boundary_cases)):
            raise ValueError(f"{label} boundary cases contain duplicates")
        if domain["witness_artifact_sha256"] not in artifact_hashes:
            raise ValueError(f"{label} domain witness is not artifact-bound")

        representation = _exact(
            item["representation_projection"],
            {
                "mathematical_objects",
                "code_types",
                "identity_and_multiplicity_policy",
                "witness_artifact_sha256",
            },
            f"{label}.representation_projection",
        )
        _strings(
            representation["mathematical_objects"],
            f"{label}.representation_projection.mathematical_objects",
            allow_empty=False,
        )
        _strings(
            representation["code_types"],
            f"{label}.representation_projection.code_types",
            allow_empty=False,
        )
        _text(
            representation["identity_and_multiplicity_policy"],
            f"{label}.representation_projection.identity_and_multiplicity_policy",
        )
        if representation["witness_artifact_sha256"] not in artifact_hashes:
            raise ValueError(f"{label} representation witness is not artifact-bound")

        approximation = _exact(
            item["approximation_budget"],
            {
                "mode",
                "required_order",
                "implemented_order",
                "precision_or_error_bound",
                "derivation_artifact_sha256",
            },
            f"{label}.approximation_budget",
        )
        approximation_mode = approximation["mode"]
        if approximation_mode not in _PROGRAM_MATH_APPROXIMATION_MODES:
            raise ValueError(f"{label} approximation mode is invalid")
        required_order = approximation["required_order"]
        implemented_order = approximation["implemented_order"]
        if approximation_mode in {"truncated", "mixed"}:
            if any(
                isinstance(value, bool) or not isinstance(value, int) or value < 0
                for value in (required_order, implemented_order)
            ):
                raise ValueError(f"{label} truncated order budget must use nonnegative integers")
            if implemented_order < required_order:
                raise ValueError(f"{label} implemented truncation order is insufficient")
        elif required_order is not None or implemented_order is not None:
            raise ValueError(
                f"{label} non-truncated computation must use null order fields"
            )
        _text(
            approximation["precision_or_error_bound"],
            f"{label}.approximation_budget.precision_or_error_bound",
        )
        if approximation["derivation_artifact_sha256"] not in artifact_hashes:
            raise ValueError(f"{label} approximation derivation is not artifact-bound")

        output = _exact(
            item["output_interpretation"],
            {
                "output_artifact_sha256",
                "claimed_quantity",
                "units_and_conventions",
            },
            f"{label}.output_interpretation",
        )
        if output["output_artifact_sha256"] != manifest_entry["output_artifact_sha256"]:
            raise ValueError(f"{label} output interpretation is not bound to stage output")
        _text(output["claimed_quantity"], f"{label}.output_interpretation.claimed_quantity")
        _text(output["units_and_conventions"], f"{label}.output_interpretation.units_and_conventions")

        checks = item["independent_checks"]
        if not isinstance(checks, list) or not checks or any(
            not isinstance(check, dict) for check in checks
        ):
            raise ValueError(f"{label}.independent_checks must be a nonempty object list")
        check_kinds: set[str] = set()
        for check_index, check in enumerate(checks, 1):
            _exact(
                check,
                {"kind", "artifact_sha256", "finding"},
                f"{label}.independent_checks[{check_index}]",
            )
            kind = _text(
                check["kind"], f"{label}.independent_checks[{check_index}].kind"
            )
            if kind not in _PROGRAM_MATH_CHECK_KINDS or kind in check_kinds:
                raise ValueError(f"{label} independent check kind is invalid or duplicated")
            check_kinds.add(kind)
            if check["artifact_sha256"] not in artifact_hashes:
                raise ValueError(f"{label} independent check is not artifact-bound")
            _text(
                check["finding"],
                f"{label}.independent_checks[{check_index}].finding",
            )
        minimum_checks = 2 if manifest_entry["role"] == "load_bearing" else 1
        if len(check_kinds) < minimum_checks:
            raise ValueError(
                f"{label} needs at least {minimum_checks} distinct independent checks"
            )
        if manifest_entry["role"] == "load_bearing" and not check_kinds.intersection(
            _PROGRAM_MATH_STRONG_CHECK_KINDS
        ):
            raise ValueError(
                f"{label} load-bearing computation needs an independent implementation, "
                "symbolic oracle, or metamorphic relation"
            )

    signals = set(contract["risk_signals"])
    if "source_formula" in signals and not has_formula:
        raise ValueError("task-card formula risk requires a formula source-use record")
    if "fixed_to_family_transport" in signals and not has_strength_bridge:
        raise ValueError("task-card fixed-to-family risk requires an explicit strength bridge")
    if "topology_extremal_invariants" in signals:
        missing = sorted(_TOPOLOGY_EDGE_CASES.difference(case_ids))
        if missing:
            raise ValueError(
                "topology assurance omits extremal cases: " + ", ".join(missing)
            )
        if not strengths:
            raise ValueError("topology assurance requires downstream claim-strength comparison")
    if "parametric_contour_substitution" in signals and not contours:
        raise ValueError("parametric contour risk requires a typed contour substitution")
    if "claimed_combinatorial_structure" in signals and not structures:
        raise ValueError("claimed combinatorial structure requires a value-free constructor record")
    if "program_math_semantic_alignment" in signals and stage_count == 0:
        raise ValueError(
            "program-math semantic alignment risk requires an actual computation stage"
        )
    return assurance

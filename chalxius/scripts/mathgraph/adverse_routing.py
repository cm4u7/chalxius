from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any

from .contracts import (
    ASSIGNMENT_ID_RE,
    MEMORY_ID_RE,
    ROUND_ID_RE,
    SHA256_RE,
    contained_path,
    sha256_bytes,
    sha256_json,
)
from .protocol import normalize_host_task_scope_id


ADVERSE_ROUTING_SCHEMA_VERSION = 1
ADVERSE_PRODUCTIVE_CASE_SCHEMA_VERSION = 2
ADVERSE_CASE_SCHEMA_VERSION = 3
ADVERSE_ATTACK_LEARNING_RULE_SCHEMA_VERSION = 2
ADVERSE_ATTACK_LEARNING_SCHEMA_VERSION = 3
ADVERSE_TASK_CARD_SCHEMA_VERSION = 5
ADVERSE_ROUTING_LEGACY_CONTRACT_REVISION = "chalxius-adverse-routing-evolution-1"
ADVERSE_ROUTING_PRODUCTIVE_CONTRACT_REVISION = "chalxius-adverse-routing-evolution-2"
ADVERSE_ROUTING_USER_RULE_CONTRACT_REVISION = "chalxius-adverse-routing-evolution-3"
ADVERSE_ROUTING_CONTRACT_REVISION = "chalxius-adverse-routing-evolution-4"
ADVERSE_ROUTING_CONTRACT_REVISIONS = {
    ADVERSE_ROUTING_LEGACY_CONTRACT_REVISION,
    ADVERSE_ROUTING_PRODUCTIVE_CONTRACT_REVISION,
    ADVERSE_ROUTING_USER_RULE_CONTRACT_REVISION,
    ADVERSE_ROUTING_CONTRACT_REVISION,
}
ADVERSE_STRUCTURED_ATTACK_TASK_CARD_SCHEMAS = frozenset({3, 4, 5})
ADVERSE_ROUTING_TRUTH_EFFECT = "none"
ADVERSE_ROUTING_PROJECT_EFFECT = "future_exploration_routing_only"
ATTACK_ROUTE_RECOMMENDATION_REPORT_REVISION = (
    "chalxius-main-route-synthesis-queue-3"
)
MAX_ATTACK_ROUTE_RECOMMENDATIONS = 3
INDEPENDENT_ADVERSE_PAIR_CONTRACT_REVISION = (
    "chalxius-independent-adverse-pair-1"
)
INDEPENDENT_ADVERSE_REQUIREMENT_FIELD = "independent_adverse_required"
MAX_TEXT_BYTES = 8 * 1024
MAX_LIST_ITEMS = 32
LEGACY_MAX_SELECTED_RULES = 24
MAX_SELECTED_RULES = 16
MAX_ACTIVE_ROUTE_RULES = 16
MAX_PERSISTED_ROUTE_CODEPOINTS = 720
MAX_ROUTE_INSTRUCTION_CODEPOINTS = 280
MAX_ROUTE_SCOPE_CODEPOINTS = 180
MAX_ROUTE_GUARD_CODEPOINTS = 180
MAX_ROUTE_GUARDS = 2
MAX_ROUTE_TRIGGER_ITEMS = 8
MAX_ROUTE_TRIGGER_ITEM_CODEPOINTS = 64
_SLUG_RE = re.compile(r"[a-z][a-z0-9_]{1,63}")
_CJK_SCRIPT_RE = re.compile(
    "["
    "\\u2e80-\\u2fff"
    "\\u3040-\\u30ff"
    "\\u31c0-\\u31ef"
    "\\u3400-\\u4dbf"
    "\\u4e00-\\u9fff"
    "\\uac00-\\ud7af"
    "\\uf900-\\ufaff"
    "]"
)
ADVERSE_DOMAIN_PROFILES = frozenset({"mathematics", "philosophy", "mixed"})
PRODUCTIVE_ATTACK_OUTCOMES = frozenset({"evidence", "insight", "challenge"})
ATTACK_RESULT_KINDS = frozenset(
    {"surviving_counterexample", "productive_challenge"}
)
ATTACK_VALUE_EFFECT_KINDS = frozenset(
    {
        "claim_refuted",
        "hypothesis_added",
        "scope_narrowed",
        "definition_repaired",
        "proof_route_replaced",
        "source_defect_isolated",
        "computation_corrected",
        "boundary_made_explicit",
    }
)


LEGACY_BASELINE_ATTACK_RULES: tuple[dict[str, Any], ...] = (
    {
        "rule_id": "baseline_exact_claim_match",
        "attack_family": "exact_claim_mismatch",
        "instruction": (
            "Compare the literal target with the claimed conclusion; attack any "
            "strengthening, weakening, converse, or replacement of the assigned claim."
        ),
        "false_positive_guards": [
            "Distinguish an explicitly declared repaired claim from a silent target change."
        ],
    },
    {
        "rule_id": "baseline_implication_direction",
        "attack_family": "implication_direction",
        "instruction": (
            "Test necessity versus sufficiency, converse and inverse directions, and every "
            "claimed iff as two separately justified implications."
        ),
        "false_positive_guards": [
            "Do not reject a direction that is independently proved in the return."
        ],
    },
    {
        "rule_id": "baseline_missing_premise",
        "attack_family": "missing_premise",
        "instruction": (
            "Inventory premises and theorem-applicability conditions; search for a model "
            "satisfying the stated premises while violating one hidden assumption."
        ),
        "false_positive_guards": [
            "Count an assumption only when it is load-bearing for the challenged inference."
        ],
    },
    {
        "rule_id": "baseline_type_domain",
        "attack_family": "type_domain_mismatch",
        "instruction": (
            "Check every object, map, operation, and equality in its declared type, domain, "
            "codomain, category, and convention."
        ),
        "false_positive_guards": [
            "Accept an ambient change only when an explicit bridge proves it."
        ],
    },
    {
        "rule_id": "baseline_quantifier_witness",
        "attack_family": "quantifier_witness",
        "instruction": (
            "Negate the exact quantifier prefix; vary order, polarity, witness dependency, "
            "uniformity, uniqueness, and exceptional sets."
        ),
        "false_positive_guards": [
            "Keep explicitly dependent witnesses dependent rather than demanding canonicity."
        ],
    },
    {
        "rule_id": "baseline_scope_transport",
        "attack_family": "scope_transport",
        "instruction": (
            "Attack local-to-global, fixed-to-family, special-to-general, pointwise-to-uniform, "
            "smooth-to-degenerate, and cover-local-to-descended transports."
        ),
        "false_positive_guards": [
            "Do not flag a transport whose bridge and witnesses are explicitly supplied."
        ],
    },
    {
        "rule_id": "baseline_case_boundary",
        "attack_family": "case_boundary",
        "instruction": (
            "Check that cases are exhaustive and test endpoints, empty domains, vacuous cases, "
            "degenerate objects, and excluded parameter values."
        ),
        "false_positive_guards": [
            "Respect exclusions that are literal hypotheses of the target claim."
        ],
    },
    {
        "rule_id": "baseline_circularity",
        "attack_family": "circularity",
        "instruction": (
            "Trace the dependency chain and attack any step that assumes the conclusion, an "
            "equivalent reformulation, or a downstream lemma."
        ),
        "false_positive_guards": [
            "Do not confuse legitimate induction or fixed-point hypotheses with circular proof."
        ],
    },
)

HIDDEN_CONJUNCT_ATTACK_RULE: dict[str, Any] = {
    "rule_id": "baseline_hidden_conjunct_split",
    "attack_family": "hidden_conjunct_split",
    "instruction": (
        "Rewrite the target as independently falsifiable conjuncts. Attack any sentence "
        "that hides several claims behind one label, so that support, repair, or refutation "
        "of one conjunct is presented as support, repair, or refutation of them all. Seek a "
        "separating case for each proposed conjunct."
    ),
    "false_positive_guards": [
        "Split only when the components have distinct truth conditions or a separating case; grammatical coordination alone is not enough.",
        "Do not split one explicitly defined relation or construction into artificial claims merely because its definition has several clauses.",
        "Preserve an openly stated conjunction; attack hidden bundling or unsupported transfer between conjuncts, not conjunction as such.",
    ],
}

PHILOSOPHY_ATTACK_RULES: tuple[dict[str, Any], ...] = (
    {
        "rule_id": "baseline_philosophy_plain_language_substitution",
        "attack_family": "plain_language_substitution",
        "instruction": (
            "Replace each load-bearing term with a clear ordinary-language statement that "
            "preserves its declared definition, then rerun the inference. If the conclusion, "
            "burden, scope, or apparent plausibility changes, identify the hidden premise, "
            "equivocation, or unsupported step carried by the term."
        ),
        "false_positive_guards": [
            "Do not count information lost by a knowingly rough paraphrase as a defect in the original argument.",
            "Do not reject an indispensable precise term merely because its faithful ordinary-language replacement is longer.",
            "Keep stipulated definitions fixed and expose any disputed definition separately.",
        ],
    },
    {
        "rule_id": "baseline_philosophy_burden_charity_failure_surface",
        "attack_family": "burden_charity_failure_surface",
        "instruction": (
            "Assign the burden of proof for each atomic claim, formulate the strongest "
            "good-faith objection or reconstruction supported by the text, and test the "
            "reply against independent failure surfaces. Attack any move that shifts the "
            "burden, answers only a weaker objection, or repairs one surface while treating "
            "premise, inference, definition, scope, and application failures as jointly closed."
        ),
        "false_positive_guards": [
            "Do not invent a stronger opponent position that the source could not reasonably support.",
            "Do not demand that one reply answer genuinely independent objections it explicitly leaves open.",
            "Distinguish a local repair from a refutation or vindication of the whole thesis.",
        ],
    },
    {
        "rule_id": "baseline_philosophy_operator_scope_equivalence",
        "attack_family": "quantifier_modality_scope_exception_equivalence",
        "instruction": (
            "Normalize the claim and every relied-on paraphrase, then test whether quantifiers, "
            "negation, modal or normative operators, their scopes, and all exception clauses "
            "have the same truth or obligation conditions. Produce a separating scenario when "
            "all/some, must/may, ought/can, normally/unless, or operator scope has changed."
        ),
        "false_positive_guards": [
            "Do not require equivalence between alternatives that are explicitly presented as a strengthening, weakening, or repair.",
            "Preserve declared context restrictions and literal exception clauses.",
            "Separate semantic non-equivalence from the further question whether either formulation is substantively true.",
        ],
    },
)

BASELINE_ATTACK_RULES: tuple[dict[str, Any], ...] = (
    *LEGACY_BASELINE_ATTACK_RULES,
    HIDDEN_CONJUNCT_ATTACK_RULE,
)
BASELINE_ATTACK_RULES_SHA256 = sha256_json(list(BASELINE_ATTACK_RULES))
PHILOSOPHY_ATTACK_RULES_SHA256 = sha256_json(list(PHILOSOPHY_ATTACK_RULES))

PROGRAM_MATH_ATTACK_RULE: dict[str, Any] = {
    "rule_id": "baseline_program_math_semantic_alignment",
    "attack_family": "program_math_semantic_alignment",
    "instruction": (
        "Trace each mathematical formula into the exact code anchor and then into the "
        "bound output. Attack sign or convention drift, index/domain and boundary "
        "mismatches, lossy object representations, insufficient truncation or precision, "
        "incorrect output interpretation, and checks that merely replay the same bug."
    ),
    "false_positive_guards": [
        "Activate only when exact executable-source and computation-output artifacts are capability-bound.",
        "Do not treat an implementation choice as an error when an explicit mathematical equivalence and convention map justify it.",
        "Separate numerical instability from a semantic formula-to-code mismatch.",
    ],
}

# This is a deliberately curated user-facing vocabulary.  The concise report
# never copies worker-authored instructions or technical case material.  A new
# family remains available in --full but is omitted from the default report
# until it has a reviewed ordinary-language explanation here.
ATTACK_FAMILY_PLAIN_LANGUAGE: dict[str, str] = {
    "exact_claim_mismatch": (
        "Checks whether the conclusion silently changes the exact claim it was meant to establish."
    ),
    "implication_direction": (
        "Checks whether necessity, sufficiency, converse, and equivalence directions are each justified."
    ),
    "missing_premise": (
        "Checks whether the conclusion depends on an unstated premise or applicability condition."
    ),
    "type_domain_mismatch": (
        "Checks whether every object, map, operation, and equality is used in the correct type and domain."
    ),
    "quantifier_witness": (
        "Checks whether quantifier order or witness dependence was changed without justification."
    ),
    "scope_transport": (
        "Checks whether a local, special, or pointwise result was extended to a global, general, or uniform claim without a valid bridge."
    ),
    "case_boundary": (
        "Checks whether the cases are exhaustive and whether boundary or degenerate cases break the claim."
    ),
    "circularity": (
        "Checks whether the reasoning assumes the conclusion or an equivalent downstream result."
    ),
    "hidden_conjunct_split": (
        "Checks whether several independently falsifiable claims were bundled and supported as if they were one."
    ),
    "plain_language_substitution": (
        "Checks whether replacing load-bearing jargon with faithful ordinary language exposes a hidden premise or unsupported step."
    ),
    "burden_charity_failure_surface": (
        "Checks burdens of proof, the strongest fair objection, and whether independent failure routes remain unresolved."
    ),
    "quantifier_modality_scope_exception_equivalence": (
        "Checks whether paraphrases preserve quantifiers, modality, operator scope, and stated exceptions."
    ),
    "program_math_semantic_alignment": (
        "Checks whether the mathematical design, executable code, and interpreted output still represent the same computation."
    ),
}


def independent_adverse_required(entry: dict[str, Any]) -> bool:
    """Return the exact prospective Research predicate; never infer from prose."""

    metadata = entry.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("research metadata must be an object")
    value = metadata.get(INDEPENDENT_ADVERSE_REQUIREMENT_FIELD, False)
    if not isinstance(value, bool):
        raise ValueError("Research independent_adverse_required must be boolean")
    return value


def independent_adverse_pair_is_required(
    entry: dict[str, Any],
    *,
    primary_work_mode: str,
) -> bool:
    """Decide only whether a second worker is needed for this primary.

    A refutation-mode primary or an explicitly challenge-shaped primary already
    occupies the adverse slot and is not duplicated.  Domain and stance do not
    create authority here; the exact Research boolean is the only trigger.
    """

    return (
        independent_adverse_required(entry)
        and primary_work_mode != "refute"
        and entry.get("kind") != "challenge"
    )


def _independent_context_id(
    *,
    round_id: str,
    assignment_id: str,
    role: str,
) -> str:
    return "hostctx-" + sha256_json(
        {
            "namespace": "chalxius-independent-worker-context-1",
            "round_id": round_id,
            "assignment_id": assignment_id,
            "role": role,
        }
    )


def build_paired_proof_philosophy_attack_handoff(
    *,
    research_id: str,
    round_id: str,
    primary_assignment_id: str,
    adverse_assignment_id: str,
) -> dict[str, Any]:
    """Build one domain-neutral paired adverse allocation handoff.

    The historical registry name is retained for traceability.  Applicability
    is now the exact Research predicate, so mathematical proof targets and
    Paper-continuation targets use the same mechanism without importing a
    philosophy stance rule into mathematics.
    """

    if MEMORY_ID_RE.fullmatch(research_id) is None:
        raise ValueError("independent adverse pair Research id is invalid")
    if ROUND_ID_RE.fullmatch(round_id) is None:
        raise ValueError("independent adverse pair round id is invalid")
    for label, assignment_id in (
        ("primary", primary_assignment_id),
        ("adverse", adverse_assignment_id),
    ):
        if ASSIGNMENT_ID_RE.fullmatch(assignment_id) is None:
            raise ValueError(f"independent adverse pair {label} assignment id is invalid")
    primary_context_id = _independent_context_id(
        round_id=round_id,
        assignment_id=primary_assignment_id,
        role="primary",
    )
    adverse_context_id = _independent_context_id(
        round_id=round_id,
        assignment_id=adverse_assignment_id,
        role="paired_adverse",
    )
    pair_semantic = {
        "contract_revision": INDEPENDENT_ADVERSE_PAIR_CONTRACT_REVISION,
        "research_id": research_id,
        "primary_assignment_id": primary_assignment_id,
        "adverse_assignment_id": adverse_assignment_id,
        "primary_worker_id": primary_assignment_id,
        "adverse_worker_id": adverse_assignment_id,
        "primary_context_id": primary_context_id,
        "adverse_context_id": adverse_context_id,
        "adverse_work_mode": "refute",
        "attack_rules_source": "paired_task_card.adverse_routing",
        "context_isolation_contract": {
            "distinct_worker_required": True,
            "distinct_context_required": True,
            "primary_context_inheritance_forbidden": True,
            "cross_worker_context_sharing_forbidden": True,
        },
        "authority_contract": {
            "result_plane": "Research_nontruth",
            "route_proposal_activation": "operator_decision_only",
            "candidate_adverse_closure": "sole_release_review_authority",
            "second_review_authority": False,
        },
    }
    pair_id = "adverse-pair-" + sha256_json(pair_semantic)
    pair_without_hash = {**pair_semantic, "pair_id": pair_id}
    pair = {**pair_without_hash, "pair_sha256": sha256_json(pair_without_hash)}

    def binding(*, role: str) -> dict[str, Any]:
        if role == "primary":
            assignment_id = primary_assignment_id
            worker_id = primary_assignment_id
            context_id = primary_context_id
            counterpart = adverse_assignment_id
        else:
            assignment_id = adverse_assignment_id
            worker_id = adverse_assignment_id
            context_id = adverse_context_id
            counterpart = primary_assignment_id
        return {
            "contract_revision": INDEPENDENT_ADVERSE_PAIR_CONTRACT_REVISION,
            "pair_id": pair_id,
            "pair_sha256": pair["pair_sha256"],
            "role": role,
            "research_id": research_id,
            "assignment_id": assignment_id,
            "worker_id": worker_id,
            "worker_context_id": context_id,
            "counterpart_assignment_id": counterpart,
            "shared_context_forbidden": True,
            "truth_effect": "none",
        }

    return {
        "pair": pair,
        "primary_binding": binding(role="primary"),
        "adverse_binding": binding(role="paired_adverse"),
    }


def validate_independent_adverse_pair(
    value: Any,
    *,
    primary_binding: Any | None = None,
    adverse_binding: Any | None = None,
) -> dict[str, Any]:
    fields = {
        "contract_revision",
        "research_id",
        "primary_assignment_id",
        "adverse_assignment_id",
        "primary_worker_id",
        "adverse_worker_id",
        "primary_context_id",
        "adverse_context_id",
        "adverse_work_mode",
        "attack_rules_source",
        "context_isolation_contract",
        "authority_contract",
        "pair_id",
        "pair_sha256",
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError("independent adverse pair fields are not exact")
    semantic = {key: item for key, item in value.items() if key not in {"pair_id", "pair_sha256"}}
    expected_id = "adverse-pair-" + sha256_json(semantic)
    without_hash = {key: item for key, item in value.items() if key != "pair_sha256"}
    if (
        value["contract_revision"] != INDEPENDENT_ADVERSE_PAIR_CONTRACT_REVISION
        or value["pair_id"] != expected_id
        or value["pair_sha256"] != sha256_json(without_hash)
        or value["primary_worker_id"] != value["primary_assignment_id"]
        or value["adverse_worker_id"] != value["adverse_assignment_id"]
        or value["primary_assignment_id"] == value["adverse_assignment_id"]
        or value["primary_context_id"] == value["adverse_context_id"]
        or value["adverse_work_mode"] != "refute"
        or value["attack_rules_source"] != "paired_task_card.adverse_routing"
        or value["context_isolation_contract"]
        != {
            "distinct_worker_required": True,
            "distinct_context_required": True,
            "primary_context_inheritance_forbidden": True,
            "cross_worker_context_sharing_forbidden": True,
        }
        or value["authority_contract"]
        != {
            "result_plane": "Research_nontruth",
            "route_proposal_activation": "operator_decision_only",
            "candidate_adverse_closure": "sole_release_review_authority",
            "second_review_authority": False,
        }
    ):
        raise ValueError("independent adverse pair contract is invalid")

    def validate_binding(binding: Any, role: str) -> None:
        binding_fields = {
            "contract_revision",
            "pair_id",
            "pair_sha256",
            "role",
            "research_id",
            "assignment_id",
            "worker_id",
            "worker_context_id",
            "counterpart_assignment_id",
            "shared_context_forbidden",
            "truth_effect",
        }
        if not isinstance(binding, dict) or set(binding) != binding_fields:
            raise ValueError("independent adverse pair binding fields are not exact")
        primary = role == "primary"
        expected = {
            "contract_revision": INDEPENDENT_ADVERSE_PAIR_CONTRACT_REVISION,
            "pair_id": value["pair_id"],
            "pair_sha256": value["pair_sha256"],
            "role": role,
            "research_id": value["research_id"],
            "assignment_id": value[
                "primary_assignment_id" if primary else "adverse_assignment_id"
            ],
            "worker_id": value[
                "primary_worker_id" if primary else "adverse_worker_id"
            ],
            "worker_context_id": value[
                "primary_context_id" if primary else "adverse_context_id"
            ],
            "counterpart_assignment_id": value[
                "adverse_assignment_id" if primary else "primary_assignment_id"
            ],
            "shared_context_forbidden": True,
            "truth_effect": "none",
        }
        if binding != expected:
            raise ValueError("independent adverse pair binding drifted")

    if primary_binding is not None:
        validate_binding(primary_binding, "primary")
    if adverse_binding is not None:
        validate_binding(adverse_binding, "paired_adverse")
    return value


def validate_host_scope_attack_report(value: Any) -> dict[str, Any]:
    """Validate the read-only, scope-complete attack-report projection."""

    required = {
        "schema_version",
        "contract_revision",
        "coverage_contract_revision",
        "project_id",
        "host_task_scope_id",
        "generated_at",
        "summary",
        "rounds",
        "assignments",
        "cards",
        "returns",
        "paired_adverse_coverage",
        "coverage_status",
        "scope_complete",
        "zero_attack_interpretation",
        "dispatch_semantics",
        "attacks",
        "user_decision_required",
        "allowed_user_actions",
        "routing_change_policy",
        "evidence_boundary",
        "truth_effect",
        "project_effect",
        "report_sha256",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("host-scope attack report fields are not exact")
    semantic = {key: item for key, item in value.items() if key != "report_sha256"}
    if (
        value["schema_version"] != ADVERSE_ROUTING_SCHEMA_VERSION
        or value["contract_revision"] != ADVERSE_ROUTING_CONTRACT_REVISION
        or value["coverage_contract_revision"]
        != "chalxius-host-scope-attack-report-1"
        or value["truth_effect"] != ADVERSE_ROUTING_TRUTH_EFFECT
        or value["project_effect"] != "report_only"
        or value["report_sha256"] != sha256_json(semantic)
    ):
        raise ValueError("host-scope attack report identity/hash is invalid")
    for field in (
        "rounds",
        "assignments",
        "cards",
        "returns",
        "paired_adverse_coverage",
        "attacks",
    ):
        if not isinstance(value[field], list) or any(
            not isinstance(item, dict) for item in value[field]
        ):
            raise ValueError(f"host-scope attack report {field} is invalid")
    status = value["coverage_status"]
    if status not in {
        "attack-recorded",
        "dispatched-no-surviving-attack",
        "pending",
        "missing-dispatch",
        "not-required",
    }:
        raise ValueError("host-scope attack report coverage status is invalid")
    if not isinstance(value["scope_complete"], bool) or value[
        "scope_complete"
    ] != (status not in {"pending", "missing-dispatch"}):
        raise ValueError("host-scope attack report completion projection is invalid")
    if value["attacks"]:
        expected_zero = "nonzero_attack_cases_enumerated"
    elif status == "dispatched-no-surviving-attack":
        expected_zero = "complete_dispatch_with_zero_surviving_attack_cases"
    elif status == "not-required":
        expected_zero = "no_independent_adverse_dispatch_required_in_scope"
    else:
        expected_zero = "zero_cases_does_not_establish_completed_dispatch"
    if value["zero_attack_interpretation"] != expected_zero:
        raise ValueError("host-scope attack report zero interpretation is invalid")
    summary = value.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("host-scope attack report summary is invalid")
    expected_counts = {
        "round_count": len(value["rounds"]),
        "assignment_count": len(value["assignments"]),
        "card_count": len(value["cards"]),
        "return_count": len(value["returns"]),
        "paired_adverse_count": len(value["paired_adverse_coverage"]),
        "worker_reported_success_count": len(value["attacks"]),
        "surviving_counterexample_count": sum(
            item.get("attack_result") == "surviving_counterexample"
            for item in value["attacks"]
        ),
        "productive_challenge_count": sum(
            item.get("attack_result") == "productive_challenge"
            for item in value["attacks"]
        ),
        "pending_user_decision_count": sum(
            item.get("proposal_status") == "pending_user_decision"
            for item in value["attacks"]
        ),
        "pending_main_synthesis_count": sum(
            item.get("proposal_status") == "pending_main_synthesis"
            for item in value["attacks"]
        ),
        "approved_count": sum(
            item.get("proposal_status") in {"approve", "approve_modified"}
            for item in value["attacks"]
        ),
        "rejected_count": sum(
            item.get("proposal_status") == "reject"
            for item in value["attacks"]
        ),
        "missing_dispatch_count": sum(
            item.get("coverage_status") == "missing-dispatch"
            for item in value["paired_adverse_coverage"]
        ),
        "pending_dispatch_count": sum(
            item.get("coverage_status") == "pending"
            for item in value["paired_adverse_coverage"]
        ),
        "dispatched_no_surviving_attack_count": sum(
            item.get("coverage_status")
            == "dispatched-no-surviving-attack"
            for item in value["paired_adverse_coverage"]
        ),
    }
    if summary != expected_counts:
        raise ValueError("host-scope attack report summary counts drifted")
    expected_user_decision = any(
        item.get("proposal_status") == "pending_user_decision"
        for item in value["attacks"]
    )
    if value["user_decision_required"] != expected_user_decision:
        raise ValueError("host-scope attack report decision projection is invalid")
    scope_id = value.get("host_task_scope_id")
    if not isinstance(scope_id, str) or not scope_id.strip():
        raise ValueError("host-scope attack report scope id is invalid")
    for field in (
        "rounds",
        "assignments",
        "cards",
        "returns",
        "paired_adverse_coverage",
        "attacks",
    ):
        if any(item.get("host_task_scope_id") != scope_id for item in value[field]):
            raise ValueError("host-scope attack report contains mixed scope")
    pair_ids = [item.get("pair_id") for item in value["paired_adverse_coverage"]]
    if any(not isinstance(item, str) for item in pair_ids) or len(pair_ids) != len(
        set(pair_ids)
    ):
        raise ValueError("host-scope attack report pair coverage is duplicated")
    assignment_fields = {
        "round_id",
        "assignment_id",
        "research_id",
        "worker_id",
        "worker_context_id",
        "work_mode",
        "assignment_role",
        "pair_id",
        "state",
        "host_task_scope_id",
    }
    card_fields = {
        "round_id",
        "assignment_id",
        "task_card_sha256",
        "worker_id",
        "worker_context_id",
        "assignment_role",
        "pair_id",
        "host_task_scope_id",
    }
    return_fields = {
        "round_id",
        "assignment_id",
        "state",
        "return_present",
        "return_sha256",
        "receipt_id",
        "result_research_id",
        "host_task_scope_id",
    }
    pair_fields = {
        "pair_id",
        "round_id",
        "research_id",
        "primary_assignment_id",
        "adverse_assignment_id",
        "primary_worker_id",
        "adverse_worker_id",
        "primary_context_id",
        "adverse_context_id",
        "adverse_return_state",
        "attack_case_ids",
        "coverage_status",
        "host_task_scope_id",
    }
    round_fields = {
        "round_id",
        "manifest_sha256",
        "primary_worker_count",
        "assignment_count",
        "paired_adverse_count",
        "host_task_scope_id",
    }
    attack_fields = {
        "case_id",
        "round_id",
        "assignment_id",
        "proposal_id",
        "evidence_status",
        "attack_result",
        "worker_outcome",
        "attack_family",
        "target_claim",
        "failure_mechanism",
        "premise_witnesses",
        "conclusion_failure_witness",
        "reproduction_steps",
        "success_boundary",
        "value_effects",
        "proposed_rule",
        "proposal_status",
        "decision_id",
        "active_rule_id",
        "host_task_scope_id",
    }
    if any(set(item) != round_fields for item in value["rounds"]):
        raise ValueError("host-scope attack report round fields are not exact")
    if any(set(item) != assignment_fields for item in value["assignments"]):
        raise ValueError("host-scope attack report assignment fields are not exact")
    if any(set(item) != card_fields for item in value["cards"]):
        raise ValueError("host-scope attack report card fields are not exact")
    if any(set(item) != return_fields for item in value["returns"]):
        raise ValueError("host-scope attack report return fields are not exact")
    if any(
        set(item) != pair_fields for item in value["paired_adverse_coverage"]
    ):
        raise ValueError("host-scope attack report pair fields are not exact")
    if any(set(item) != attack_fields for item in value["attacks"]):
        raise ValueError("host-scope attack report attack fields are not exact")
    rounds = {item["round_id"]: item for item in value["rounds"]}
    if len(rounds) != len(value["rounds"]):
        raise ValueError("host-scope attack report rounds are duplicated")
    assignments = {
        (item["round_id"], item["assignment_id"]): item
        for item in value["assignments"]
    }
    cards = {
        (item["round_id"], item["assignment_id"]): item
        for item in value["cards"]
    }
    returns = {
        (item["round_id"], item["assignment_id"]): item
        for item in value["returns"]
    }
    if (
        len(assignments) != len(value["assignments"])
        or set(assignments) != set(cards)
        or set(assignments) != set(returns)
        or any(key[0] not in rounds for key in assignments)
    ):
        raise ValueError("host-scope attack report assignment/card/return closure drifted")
    for round_id, round_item in rounds.items():
        round_assignments = [
            item for item in value["assignments"] if item["round_id"] == round_id
        ]
        if (
            round_item["assignment_count"] != len(round_assignments)
            or round_item["primary_worker_count"]
            != sum(item["assignment_role"] == "primary" for item in round_assignments)
            or round_item["paired_adverse_count"]
            != sum(
                item["assignment_role"] == "paired_adverse"
                for item in round_assignments
            )
        ):
            raise ValueError("host-scope attack report round counts drifted")
    attack_case_ids = [item.get("case_id") for item in value["attacks"]]
    if (
        any(not isinstance(item, str) or not item for item in attack_case_ids)
        or len(attack_case_ids) != len(set(attack_case_ids))
        or any(
            (item["round_id"], item["assignment_id"]) not in assignments
            for item in value["attacks"]
        )
    ):
        raise ValueError("host-scope attack report case closure drifted")
    attack_case_id_set = set(attack_case_ids)
    for pair in value["paired_adverse_coverage"]:
        primary_key = (pair["round_id"], pair["primary_assignment_id"])
        if primary_key not in assignments:
            raise ValueError("host-scope attack report pair primary is missing")
        if pair["coverage_status"] == "missing-dispatch":
            if any(
                pair[field] is not None
                for field in (
                    "adverse_assignment_id",
                    "adverse_worker_id",
                    "adverse_context_id",
                )
            ) or pair["adverse_return_state"] != "not_dispatched":
                raise ValueError("host-scope missing-dispatch projection is invalid")
            if pair["attack_case_ids"] != []:
                raise ValueError("host-scope missing-dispatch case closure is invalid")
            continue
        adverse_key = (pair["round_id"], pair["adverse_assignment_id"])
        adverse_assignment = assignments.get(adverse_key)
        adverse_card = cards.get(adverse_key)
        adverse_return = returns.get(adverse_key)
        if adverse_assignment is None or adverse_card is None or adverse_return is None:
            raise ValueError("host-scope attack report pair adverse assignment is missing")
        primary_assignment = assignments[primary_key]
        primary_card = cards[primary_key]
        if (
            primary_assignment["worker_id"] != pair["primary_worker_id"]
            or adverse_assignment["worker_id"] != pair["adverse_worker_id"]
            or primary_card["worker_context_id"] != pair["primary_context_id"]
            or adverse_card["worker_context_id"] != pair["adverse_context_id"]
            or pair["primary_worker_id"] == pair["adverse_worker_id"]
            or pair["primary_context_id"] == pair["adverse_context_id"]
            or adverse_assignment["assignment_role"] != "paired_adverse"
            or adverse_assignment["work_mode"] != "refute"
            or adverse_return["state"] != pair["adverse_return_state"]
        ):
            raise ValueError("host-scope attack report pair binding drifted")
        case_ids = pair["attack_case_ids"]
        expected_case_ids = {
            item["case_id"]
            for item in value["attacks"]
            if item["round_id"] == pair["round_id"]
            and item["assignment_id"] == pair["adverse_assignment_id"]
        }
        if (
            not isinstance(case_ids, list)
            or any(not isinstance(item, str) for item in case_ids)
            or len(case_ids) != len(set(case_ids))
            or set(case_ids) != expected_case_ids
            or not set(case_ids).issubset(attack_case_id_set)
        ):
            raise ValueError("host-scope attack report pair case closure drifted")
        expected_pair_status = (
            "attack-recorded"
            if adverse_return["state"] == "ingested" and case_ids
            else "dispatched-no-surviving-attack"
            if adverse_return["state"] == "ingested"
            else "pending"
        )
        if pair["coverage_status"] != expected_pair_status:
            raise ValueError("host-scope attack report pair status drifted")
    pair_statuses = {
        item["coverage_status"] for item in value["paired_adverse_coverage"]
    }
    expected_status = (
        "missing-dispatch"
        if not value["rounds"] or "missing-dispatch" in pair_statuses
        else "pending"
        if "pending" in pair_statuses
        else "attack-recorded"
        if value["attacks"]
        else "dispatched-no-surviving-attack"
        if value["paired_adverse_coverage"]
        else "not-required"
    )
    if value["coverage_status"] != expected_status:
        raise ValueError("host-scope attack report aggregate coverage drifted")
    return value


def validate_attack_route_recommendation_report(
    value: Any,
) -> dict[str, Any]:
    """Validate the small Main-facing queue of concrete worker failure reports."""

    fields = {
        "schema_version",
        "contract_revision",
        "project_id",
        "host_task_scope_id",
        "coverage_status",
        "scope_complete",
        "recommendation_policy",
        "recommendations",
        "pending_proposal_count",
        "omitted_pending_count",
        "main_synthesis_required",
        "main_instruction",
        "routing_change_policy",
        "evidence_boundary",
        "truth_effect",
        "project_effect",
        "report_sha256",
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError("attack-route recommendation report fields are not exact")
    semantic = {
        key: item for key, item in value.items() if key != "report_sha256"
    }
    if (
        value["schema_version"] != ADVERSE_ROUTING_SCHEMA_VERSION
        or value["contract_revision"]
        != ATTACK_ROUTE_RECOMMENDATION_REPORT_REVISION
        or value["truth_effect"] != ADVERSE_ROUTING_TRUTH_EFFECT
        or value["project_effect"] != "report_only"
        or value["routing_change_policy"]
        != "no_route_change_without_main_synthesis"
        or value["coverage_status"] != "case-projection"
        or value["scope_complete"] is not False
        or value["report_sha256"] != sha256_json(semantic)
    ):
        raise ValueError("attack-route recommendation report identity is invalid")
    policy = value["recommendation_policy"]
    if policy != {
        "maximum": MAX_ATTACK_ROUTE_RECOMMENDATIONS,
        "selection": (
            "pending_worker_failure_reports_family_deduplicated_for_main_review"
        ),
        "quality_bias": "omit_instead_of_broaden",
    }:
        raise ValueError("attack-route recommendation policy drifted")
    recommendations = value["recommendations"]
    item_fields = {
        "number",
        "attack_type",
        "what_it_checks",
        "reported_failure",
        "applies_when",
        "support_kind",
        "support_count",
        "main_disposition",
    }
    if (
        not isinstance(recommendations, list)
        or len(recommendations) > MAX_ATTACK_ROUTE_RECOMMENDATIONS
        or any(
            not isinstance(item, dict) or set(item) != item_fields
            for item in recommendations
        )
    ):
        raise ValueError("attack-route recommendations are invalid")
    attack_types: set[str] = set()
    for number, item in enumerate(recommendations, 1):
        attack_type = _require_slug(
            item["attack_type"],
            "recommendation attack type",
        )
        if (
            item["number"] != number
            or attack_type in attack_types
            or attack_type not in ATTACK_FAMILY_PLAIN_LANGUAGE
            or item["what_it_checks"]
            != ATTACK_FAMILY_PLAIN_LANGUAGE[attack_type]
            or not isinstance(item["support_count"], int)
            or isinstance(item["support_count"], bool)
            or item["support_count"] < 1
            or item["support_kind"]
            not in {"surviving_counterexample", "productive_challenge", "mixed"}
            or item["main_disposition"] != "synthesize_compress_or_reject"
        ):
            raise ValueError("attack-route recommendation item is invalid")
        _require_text(item["applies_when"], "recommendation applicability")
        _require_text(item["reported_failure"], "reported worker failure")
        _require_text(item["what_it_checks"], "recommendation explanation")
        attack_types.add(attack_type)
    for field_name in ("pending_proposal_count", "omitted_pending_count"):
        count = value[field_name]
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError("attack-route recommendation counts are invalid")
    if (
        value["omitted_pending_count"]
        != value["pending_proposal_count"] - len(recommendations)
        or value["main_synthesis_required"] != bool(recommendations)
    ):
        raise ValueError("attack-route recommendation count projection drifted")
    return value


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _require_text(value: Any, label: str, *, max_bytes: int = MAX_TEXT_BYTES) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    text = value.strip()
    if len(text.encode("utf-8")) > max_bytes:
        raise ValueError(f"{label} exceeds {max_bytes} UTF-8 bytes")
    return text


def _require_slug(value: Any, label: str) -> str:
    value = _require_text(value, label, max_bytes=64)
    if _SLUG_RE.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase underscore slug")
    return value


def validate_adverse_domain_profile(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or value not in ADVERSE_DOMAIN_PROFILES:
        raise ValueError(
            "research adverse_domain_profile must be mathematics, philosophy, or mixed"
        )
    return value


def _require_text_list(
    value: Any,
    label: str,
    *,
    nonempty: bool,
    slug: bool = False,
) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{label} must be a list of strings")
    if nonempty and not value:
        raise ValueError(f"{label} must be nonempty")
    if len(value) > MAX_LIST_ITEMS:
        raise ValueError(f"{label} exceeds {MAX_LIST_ITEMS} items")
    normalized = [
        _require_slug(item, f"{label} item")
        if slug
        else _require_text(item, f"{label} item", max_bytes=1024)
        for item in value
    ]
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{label} contains duplicates")
    return normalized


def _require_internal_english_text(value: Any, label: str) -> str:
    """Keep current governance prose English without restricting mathematics.

    Mathematical symbols, formulas, identifiers, and source locators remain
    valid. Exact user claims and external quotations are outside this helper.
    Historical schemas are validated by their original contract.
    """

    text = _require_text(value, label)
    if _CJK_SCRIPT_RE.search(text) is not None:
        raise ValueError(f"{label} must use English internal prose")
    return text


def _require_internal_english_text_list(
    value: Any, label: str, *, nonempty: bool
) -> list[str]:
    items = _require_text_list(value, label, nonempty=nonempty)
    for item in items:
        if _CJK_SCRIPT_RE.search(item) is not None:
            raise ValueError(f"{label} must use English internal prose")
    return items


def _validate_id(value: Any, prefix: str, label: str) -> str:
    value = _require_text(value, label, max_bytes=len(prefix) + 64)
    if not value.startswith(prefix) or SHA256_RE.fullmatch(value.removeprefix(prefix)) is None:
        raise ValueError(f"{label} is invalid")
    return value


def validate_route_trigger(value: Any, *, label: str) -> dict[str, Any]:
    required = {
        "research_kinds",
        "claim_terms_any",
        "metadata_signals_any",
        "universal_refute",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError(f"{label} fields are not exact")
    research_kinds = _require_text_list(
        value["research_kinds"], f"{label} research_kinds", nonempty=False, slug=True
    )
    claim_terms = _require_text_list(
        value["claim_terms_any"], f"{label} claim_terms_any", nonempty=False
    )
    metadata_signals = _require_text_list(
        value["metadata_signals_any"],
        f"{label} metadata_signals_any",
        nonempty=False,
        slug=True,
    )
    universal = value["universal_refute"]
    if not isinstance(universal, bool):
        raise ValueError(f"{label} universal_refute must be boolean")
    if universal and (research_kinds or claim_terms or metadata_signals):
        raise ValueError(f"{label} universal trigger cannot also name filters")
    if not universal and not (research_kinds or claim_terms or metadata_signals):
        raise ValueError(f"{label} needs a filter or universal_refute=true")
    return {
        "research_kinds": research_kinds,
        "claim_terms_any": claim_terms,
        "metadata_signals_any": metadata_signals,
        "universal_refute": universal,
    }


def validate_route_rule(value: Any, *, label: str = "route rule") -> dict[str, Any]:
    required = {
        "attack_family",
        "trigger",
        "instruction",
        "false_positive_guards",
        "scope_note",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError(f"{label} fields are not exact")
    return {
        "attack_family": _require_slug(value["attack_family"], f"{label} attack_family"),
        "trigger": validate_route_trigger(value["trigger"], label=f"{label} trigger"),
        "instruction": _require_text(value["instruction"], f"{label} instruction"),
        "false_positive_guards": _require_text_list(
            value["false_positive_guards"],
            f"{label} false_positive_guards",
            nonempty=True,
        ),
        "scope_note": _require_text(value["scope_note"], f"{label} scope_note"),
    }


def validate_persistent_route_rule(
    value: Any, *, label: str = "persistent route rule"
) -> dict[str, Any]:
    """Validate one Main-synthesized, compact mechanism-level route rule.

    Worker reports deliberately do not pass through this interface.  The caps
    apply only to the small persistent rule that Main chooses to place on future
    task cards; truncation is never used as a substitute for semantic compression.
    """

    rule = validate_route_rule(value, label=label)
    _require_internal_english_text(rule["instruction"], f"{label} instruction")
    _require_internal_english_text(rule["scope_note"], f"{label} scope")
    _require_internal_english_text_list(
        rule["false_positive_guards"],
        f"{label} false_positive_guards",
        nonempty=True,
    )
    _require_internal_english_text_list(
        rule["trigger"]["claim_terms_any"],
        f"{label} claim_terms_any",
        nonempty=False,
    )
    trigger = rule["trigger"]
    trigger_items = (
        trigger["research_kinds"]
        + trigger["claim_terms_any"]
        + trigger["metadata_signals_any"]
    )
    texts = [
        rule["attack_family"],
        rule["instruction"],
        rule["scope_note"],
        *trigger_items,
        *rule["false_positive_guards"],
    ]
    total_codepoints = sum(len(item) for item in texts)
    if len(rule["instruction"]) > MAX_ROUTE_INSTRUCTION_CODEPOINTS:
        raise ValueError(
            f"{label} instruction exceeds {MAX_ROUTE_INSTRUCTION_CODEPOINTS} Unicode "
            "code points; Main must compress the mechanism semantically"
        )
    if len(rule["scope_note"]) > MAX_ROUTE_SCOPE_CODEPOINTS:
        raise ValueError(
            f"{label} scope exceeds {MAX_ROUTE_SCOPE_CODEPOINTS} Unicode code points; "
            "Main must compress the mechanism semantically"
        )
    if len(rule["false_positive_guards"]) > MAX_ROUTE_GUARDS or any(
        len(item) > MAX_ROUTE_GUARD_CODEPOINTS
        for item in rule["false_positive_guards"]
    ):
        raise ValueError(
            f"{label} guards exceed the compact {MAX_ROUTE_GUARDS}-guard budget; "
            "Main must merge or compress them"
        )
    if len(trigger_items) > MAX_ROUTE_TRIGGER_ITEMS or any(
        len(item) > MAX_ROUTE_TRIGGER_ITEM_CODEPOINTS for item in trigger_items
    ):
        raise ValueError(
            f"{label} trigger exceeds the compact trigger budget; Main must generalize "
            "the mechanism rather than enumerate concrete cases"
        )
    if total_codepoints > MAX_PERSISTED_ROUTE_CODEPOINTS:
        raise ValueError(
            f"{label} contains {total_codepoints} Unicode code points, exceeding the "
            f"hard cap {MAX_PERSISTED_ROUTE_CODEPOINTS}; Main must submit a semantically "
            "compressed rule and automatic truncation is forbidden"
        )
    return rule


def _persistent_route_codepoints(rule: dict[str, Any]) -> int:
    trigger = rule["trigger"]
    return sum(
        len(item)
        for item in (
            [rule["attack_family"], rule["instruction"], rule["scope_note"]]
            + trigger["research_kinds"]
            + trigger["claim_terms_any"]
            + trigger["metadata_signals_any"]
            + rule["false_positive_guards"]
        )
    )


def validate_attack_learning(
    value: Any,
    *,
    require_current: bool = False,
    expected_result_kind: str | None = None,
) -> dict[str, Any]:
    legacy_required = {
        "attack_family",
        "target_pattern",
        "failure_mechanism",
        "premise_witnesses",
        "conclusion_failure_witness",
        "reproduction_steps",
        "success_boundary",
        "route_rule",
    }
    rule_bearing_required = {
        *legacy_required,
        "schema_version",
        "result_kind",
        "value_effects",
    }
    report_required = {
        "schema_version",
        "result_kind",
        "attack_family",
        "target_pattern",
        "failure_mechanism",
        "premise_witnesses",
        "conclusion_failure_witness",
        "reproduction_steps",
        "success_boundary",
        "value_effects",
    }
    if not isinstance(value, dict):
        raise ValueError("attack_learning must be an object")
    is_rule_bearing = set(value) == rule_bearing_required
    is_report = set(value) == report_required
    if set(value) != legacy_required and not is_rule_bearing and not is_report:
        raise ValueError("attack_learning fields are not exact")
    if require_current and not is_report:
        raise ValueError("current adverse task requires worker failure-report schema_version=3")
    result_kind: str | None = None
    value_effects: list[dict[str, str]] = []
    if is_rule_bearing or is_report:
        expected_schema = (
            ADVERSE_ATTACK_LEARNING_SCHEMA_VERSION
            if is_report
            else ADVERSE_ATTACK_LEARNING_RULE_SCHEMA_VERSION
        )
        if value["schema_version"] != expected_schema:
            raise ValueError("attack_learning schema version is unsupported")
        result_kind = value["result_kind"]
        if result_kind not in ATTACK_RESULT_KINDS:
            raise ValueError("attack_learning result_kind is invalid")
        if expected_result_kind is not None and result_kind != expected_result_kind:
            raise ValueError("attack_learning result_kind disagrees with worker outcome")
        raw_effects = value["value_effects"]
        if not isinstance(raw_effects, list) or not raw_effects:
            raise ValueError("attack_learning value_effects must be nonempty")
        for index, raw in enumerate(raw_effects):
            if not isinstance(raw, dict) or set(raw) != {
                "effect_kind",
                "before",
                "after",
                "evidence",
            }:
                raise ValueError(
                    f"attack_learning value_effects[{index}] fields are not exact"
                )
            effect_kind = _require_slug(
                raw["effect_kind"],
                f"attack_learning value_effects[{index}] effect_kind",
            )
            if effect_kind not in ATTACK_VALUE_EFFECT_KINDS:
                raise ValueError("attack_learning value effect kind is invalid")
            value_effects.append(
                {
                    "effect_kind": effect_kind,
                    "before": _require_internal_english_text(
                        raw["before"],
                        f"attack_learning value_effects[{index}] before",
                    ) if is_report else _require_text(
                        raw["before"],
                        f"attack_learning value_effects[{index}] before",
                    ),
                    "after": _require_internal_english_text(
                        raw["after"],
                        f"attack_learning value_effects[{index}] after",
                    ) if is_report else _require_text(
                        raw["after"],
                        f"attack_learning value_effects[{index}] after",
                    ),
                    "evidence": _require_internal_english_text(
                        raw["evidence"],
                        f"attack_learning value_effects[{index}] evidence",
                    ) if is_report else _require_text(
                        raw["evidence"],
                        f"attack_learning value_effects[{index}] evidence",
                    ),
                }
            )
    attack_family = _require_slug(value["attack_family"], "attack family")
    route_rule = None
    if not is_report:
        route_rule = validate_route_rule(value["route_rule"])
        if route_rule["attack_family"] != attack_family:
            raise ValueError("attack_learning family and route rule family disagree")
    normalized = {
        "attack_family": attack_family,
        "target_pattern": _require_internal_english_text(
            value["target_pattern"], "attack target pattern"
        ) if is_report else _require_text(
            value["target_pattern"], "attack target pattern"
        ),
        "failure_mechanism": _require_internal_english_text(
            value["failure_mechanism"], "attack failure mechanism"
        ) if is_report else _require_text(
            value["failure_mechanism"], "attack failure mechanism"
        ),
        "premise_witnesses": _require_internal_english_text_list(
            value["premise_witnesses"], "attack premise witnesses", nonempty=True
        ) if is_report else _require_text_list(
            value["premise_witnesses"], "attack premise witnesses", nonempty=True
        ),
        "conclusion_failure_witness": _require_internal_english_text(
            value["conclusion_failure_witness"],
            "attack conclusion-failure witness",
        ) if is_report else _require_text(
            value["conclusion_failure_witness"],
            "attack conclusion-failure witness",
        ),
        "reproduction_steps": _require_internal_english_text_list(
            value["reproduction_steps"], "attack reproduction steps", nonempty=True
        ) if is_report else _require_text_list(
            value["reproduction_steps"], "attack reproduction steps", nonempty=True
        ),
        "success_boundary": _require_internal_english_text(
            value["success_boundary"], "attack success boundary"
        ) if is_report else _require_text(
            value["success_boundary"], "attack success boundary"
        ),
    }
    if route_rule is not None:
        normalized["route_rule"] = route_rule
    if is_rule_bearing or is_report:
        return {
            "schema_version": value["schema_version"],
            "result_kind": result_kind,
            **normalized,
            "value_effects": value_effects,
        }
    if expected_result_kind is not None:
        raise ValueError("legacy attack_learning cannot bind a current result kind")
    return normalized


class AdverseRoutingManager:
    """Project-local, nontruth failure reporting and Main-governed routing."""

    def __init__(self, store: Any) -> None:
        self.store = store
        self.root = store.root / "governance" / "adverse-routing"
        self.contract_path = self.root / "contract.json"
        self.cases_dir = self.root / "cases" / "by-id"
        self.proposals_dir = self.root / "proposals" / "by-id"
        self.decisions_dir = self.root / "decisions" / "by-id"
        self.rules_dir = self.root / "rules" / "by-id"
        self.disablements_dir = self.root / "disablements" / "by-rule"

    def _validate_contract(self, payload: Any) -> dict[str, Any]:
        required = {
            "schema_version",
            "contract_revision",
            "project_id",
            "activation_kind",
            "actor",
            "reason",
            "truth_effect",
            "project_effect",
            "activated_at",
            "record_sha256",
        }
        if not isinstance(payload, dict) or set(payload) != required:
            raise ValueError("adverse-routing contract fields are not exact")
        revision = payload["contract_revision"]
        activation_kind = payload["activation_kind"]
        allowed_activation = (
            {"explicit_operator_opt_in"}
            if revision == ADVERSE_ROUTING_LEGACY_CONTRACT_REVISION
            else {
                "explicit_operator_opt_in",
                "prospective_default_user_authorization",
            }
        )
        if (
            payload["schema_version"] != ADVERSE_ROUTING_SCHEMA_VERSION
            or revision not in ADVERSE_ROUTING_CONTRACT_REVISIONS
            or payload["project_id"] != self.store.project_id()
            or activation_kind not in allowed_activation
            or payload["truth_effect"] != ADVERSE_ROUTING_TRUTH_EFFECT
            or payload["project_effect"] != ADVERSE_ROUTING_PROJECT_EFFECT
        ):
            raise ValueError("adverse-routing contract identity is invalid")
        _require_text(payload["actor"], "adverse-routing contract actor")
        _require_text(payload["reason"], "adverse-routing contract reason")
        _require_text(payload["activated_at"], "adverse-routing activation time")
        without_hash = {key: value for key, value in payload.items() if key != "record_sha256"}
        if payload["record_sha256"] != sha256_json(without_hash):
            raise ValueError("adverse-routing contract hash mismatch")
        return payload

    def enabled(self) -> bool:
        if self.contract_path.is_symlink():
            raise ValueError("adverse-routing contract may not be a symlink")
        if self.contract_path.exists():
            if not self.contract_path.is_file():
                raise ValueError("adverse-routing contract is unsafe")
            self._validate_contract(self.store._read_json(self.contract_path))
            if self.store.workflow_evidence_version() != 5:
                raise ValueError("adverse-routing state is invalid outside a V5 project")
            return True
        if self.root.exists() and any(self.root.iterdir()):
            raise ValueError("adverse-routing state exists without its activation contract")
        return self.store.workflow_evidence_version() == 5

    def _materialize_state(
        self,
        *,
        activation_kind: str,
        actor: str,
        reason: str,
    ) -> None:
        if self.contract_path.exists():
            self._validate_contract(self.store._read_json(self.contract_path))
            return
        if self.root.exists() and any(self.root.iterdir()):
            raise ValueError(
                "adverse-routing state exists without its activation contract"
            )
        if self.store.workflow_evidence_version() != 5:
            raise ValueError("adverse-routing state may be materialized only for V5")
        for path in (
            self.cases_dir,
            self.proposals_dir,
            self.decisions_dir,
            self.rules_dir,
            self.disablements_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)
        without_hash = {
            "schema_version": ADVERSE_ROUTING_SCHEMA_VERSION,
            "contract_revision": ADVERSE_ROUTING_CONTRACT_REVISION,
            "project_id": self.store.project_id(),
            "activation_kind": activation_kind,
            "actor": actor,
            "reason": reason,
            "truth_effect": ADVERSE_ROUTING_TRUTH_EFFECT,
            "project_effect": ADVERSE_ROUTING_PROJECT_EFFECT,
            "activated_at": _utc_now(),
        }
        contract = {**without_hash, "record_sha256": sha256_json(without_hash)}
        self.store._write_json_once(self.contract_path, contract)

    def initialize(self, *, actor: str, reason: str) -> dict[str, Any]:
        actor = _require_text(actor, "adverse-routing actor")
        reason = _require_text(reason, "adverse-routing reason")
        if self.store.workflow_evidence_version() != 5:
            raise ValueError(
                "adverse-routing evolution is V5-only and cannot be enabled on an "
                "earlier workflow project"
            )
        with self.store.v5_mutation_lock(command="attack-route-enable"):
            if self.contract_path.exists():
                return self.status()
            self._materialize_state(
                activation_kind="explicit_operator_opt_in",
                actor=actor,
                reason=reason,
            )
        return self.status()

    def require_enabled(self) -> None:
        if not self.enabled():
            raise ValueError(
                "default adverse reporting and routing evolution are V5-only"
            )

    def _write_content_record(
        self,
        *,
        directory: Path,
        id_field: str,
        prefix: str,
        semantic: dict[str, Any],
    ) -> dict[str, Any]:
        semantic_sha = sha256_json(semantic)
        record_id = prefix + semantic_sha
        path = directory / f"{record_id}.json"
        if path.exists():
            return self.store._read_json(path)
        without_hash = {
            **semantic,
            id_field: record_id,
            "created_at": _utc_now(),
            "semantic_sha256": semantic_sha,
        }
        record = {**without_hash, "record_sha256": sha256_json(without_hash)}
        self.store._write_json_once(path, record)
        return record

    def _validate_content_record(
        self,
        payload: Any,
        *,
        path: Path,
        id_field: str,
        prefix: str,
        semantic_fields: set[str],
        label: str,
    ) -> dict[str, Any]:
        required = semantic_fields | {
            id_field,
            "created_at",
            "semantic_sha256",
            "record_sha256",
        }
        if not isinstance(payload, dict) or set(payload) != required:
            raise ValueError(f"{label} fields are not exact")
        record_id = _validate_id(payload[id_field], prefix, f"{label} id")
        if path.stem != record_id:
            raise ValueError(f"{label} path/id mismatch")
        semantic = {key: payload[key] for key in semantic_fields}
        semantic_sha = sha256_json(semantic)
        if payload["semantic_sha256"] != semantic_sha or record_id != prefix + semantic_sha:
            raise ValueError(f"{label} semantic hash mismatch")
        without_hash = {key: value for key, value in payload.items() if key != "record_sha256"}
        if payload["record_sha256"] != sha256_json(without_hash):
            raise ValueError(f"{label} record hash mismatch")
        _require_text(payload["created_at"], f"{label} created_at")
        return payload

    def _safe_records(self, directory: Path) -> list[tuple[Path, dict[str, Any]]]:
        records: list[tuple[Path, dict[str, Any]]] = []
        if not self.contract_path.exists() and (
            not self.root.exists() or not any(self.root.iterdir())
        ):
            return records
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError(f"adverse-routing record directory is missing or unsafe: {directory}")
        for path in sorted(directory.iterdir()):
            if path.is_symlink() or not path.is_file() or path.suffix != ".json":
                raise ValueError(f"unsafe adverse-routing entry: {path}")
            records.append((path, self.store._read_json(path)))
        return records

    def _validate_case(self, payload: Any, path: Path) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("attack case must be an object")
        schema_version = payload.get("schema_version")
        legacy = schema_version == ADVERSE_ROUTING_SCHEMA_VERSION
        worker_report = schema_version == ADVERSE_CASE_SCHEMA_VERSION
        fields = (
            {
                "schema_version",
                "contract_revision",
                "project_id",
                "round_id",
                "assignment_id",
                "host_task_scope_id",
                "target_research_id",
                "counterexample_research_id",
                "task_card_sha256",
                "return_sha256",
                "target_claim",
                "attack_learning",
                "evidence_status",
                "truth_effect",
            }
            if legacy
            else {
                "schema_version",
                "contract_revision",
                "project_id",
                "round_id",
                "assignment_id",
                "host_task_scope_id",
                "target_research_id",
                "attack_research_id",
                "attack_result",
                "worker_outcome",
                "task_card_sha256",
                "return_sha256",
                "target_claim",
                "attack_learning",
                "evidence_status",
                "truth_effect",
            }
        )
        record = self._validate_content_record(
            payload,
            path=path,
            id_field="case_id",
            prefix="attack-case-",
            semantic_fields=fields,
            label="attack case",
        )
        self._validate_common_identity(
            record,
            "attack case",
            allowed_schema_versions=(
                {ADVERSE_ROUTING_SCHEMA_VERSION}
                if legacy
                else {
                    ADVERSE_PRODUCTIVE_CASE_SCHEMA_VERSION,
                    ADVERSE_CASE_SCHEMA_VERSION,
                }
            ),
        )
        for name in (
            "round_id",
            "assignment_id",
            "host_task_scope_id",
            "target_research_id",
            "target_claim",
        ):
            _require_text(record[name], f"attack case {name}")
        for name in ("task_card_sha256", "return_sha256"):
            if not isinstance(record[name], str) or SHA256_RE.fullmatch(record[name]) is None:
                raise ValueError(f"attack case {name} is invalid")
        if legacy:
            _require_text(
                record["counterexample_research_id"],
                "attack case counterexample_research_id",
            )
            validate_attack_learning(record["attack_learning"])
            if record["evidence_status"] != "worker_reported_counterexample_nontruth":
                raise ValueError("attack case evidence status is invalid")
        else:
            _require_text(record["attack_research_id"], "attack case attack_research_id")
            attack_result = record["attack_result"]
            if attack_result not in ATTACK_RESULT_KINDS:
                raise ValueError("attack case result is invalid")
            worker_outcome = _require_slug(
                record["worker_outcome"], "attack case worker outcome"
            )
            if (
                attack_result == "surviving_counterexample"
                and worker_outcome != "counterexample"
            ) or (
                attack_result == "productive_challenge"
                and worker_outcome not in PRODUCTIVE_ATTACK_OUTCOMES
            ):
                raise ValueError("attack case result/outcome binding is invalid")
            validate_attack_learning(
                record["attack_learning"],
                require_current=worker_report,
                expected_result_kind=attack_result,
            )
            expected_status = (
                "worker_reported_counterexample_nontruth"
                if attack_result == "surviving_counterexample"
                else "worker_reported_productive_challenge_nontruth"
            )
            if record["evidence_status"] != expected_status:
                raise ValueError("attack case evidence status is invalid")
        return record

    def _validate_proposal(self, payload: Any, path: Path) -> dict[str, Any]:
        legacy_fields = {
            "schema_version",
            "contract_revision",
            "project_id",
            "case_id",
            "route_rule",
            "proposal_status",
            "activation_policy",
            "truth_effect",
        }
        report_fields = {
            "schema_version",
            "contract_revision",
            "project_id",
            "case_id",
            "proposal_status",
            "activation_policy",
            "truth_effect",
        }
        report_only = (
            isinstance(payload, dict)
            and payload.get("contract_revision") == ADVERSE_ROUTING_CONTRACT_REVISION
        )
        record = self._validate_content_record(
            payload,
            path=path,
            id_field="proposal_id",
            prefix="route-proposal-",
            semantic_fields=report_fields if report_only else legacy_fields,
            label="route proposal",
        )
        self._validate_common_identity(record, "route proposal")
        _validate_id(record["case_id"], "attack-case-", "route proposal case id")
        if report_only:
            expected_status = "pending_main_synthesis"
            expected_policy = "main_synthesis_only"
        else:
            validate_route_rule(record["route_rule"])
            expected_status = "pending_user_decision"
            expected_policy = "user_decision_only"
        if (
            record["proposal_status"] != expected_status
            or record["activation_policy"] != expected_policy
        ):
            raise ValueError("route proposal policy is invalid")
        return record

    def _validate_decision(self, payload: Any, path: Path) -> dict[str, Any]:
        legacy_fields = {
            "schema_version",
            "contract_revision",
            "project_id",
            "proposal_id",
            "action",
            "reason",
            "actor",
            "approved_rule",
            "effect",
            "truth_effect",
        }
        current_fields = {*legacy_fields, "governance"}
        current = (
            isinstance(payload, dict)
            and payload.get("contract_revision") == ADVERSE_ROUTING_CONTRACT_REVISION
        )
        record = self._validate_content_record(
            payload,
            path=path,
            id_field="decision_id",
            prefix="route-decision-",
            semantic_fields=current_fields if current else legacy_fields,
            label="route decision",
        )
        self._validate_common_identity(record, "route decision")
        _validate_id(record["proposal_id"], "route-proposal-", "route decision proposal id")
        allowed_actions = (
            {"approve_modified", "reject"}
            if current
            else {"approve", "approve_modified", "reject"}
        )
        if record["action"] not in allowed_actions:
            raise ValueError("route decision action is invalid")
        if current:
            _require_internal_english_text(
                record["reason"], "route decision reason"
            )
        else:
            _require_text(record["reason"], "route decision reason")
        _require_text(record["actor"], "route decision actor")
        if record["action"] == "reject":
            if record["approved_rule"] is not None:
                raise ValueError("rejected route decision cannot carry a rule")
        else:
            if current:
                validate_persistent_route_rule(
                    record["approved_rule"], label="approved route rule"
                )
            else:
                validate_route_rule(record["approved_rule"], label="approved route rule")
        if current:
            governance = record["governance"]
            if record["action"] == "reject":
                if governance is not None:
                    raise ValueError("rejected route decision cannot carry governance")
            elif not isinstance(governance, dict) or set(governance) != {
                "decision_authority",
                "abstraction_level",
                "concrete_evidence_excluded",
                "compression",
                "persistent_text_codepoints",
            }:
                raise ValueError("Main route governance fields are not exact")
            elif (
                governance["decision_authority"] != "main"
                or governance["abstraction_level"] != "mechanism"
                or governance["concrete_evidence_excluded"] is not True
                or governance["compression"] not in {"within_budget", "compressed"}
                or not isinstance(governance["persistent_text_codepoints"], int)
                or governance["persistent_text_codepoints"] < 1
                or governance["persistent_text_codepoints"]
                > MAX_PERSISTED_ROUTE_CODEPOINTS
                or governance["persistent_text_codepoints"]
                != _persistent_route_codepoints(record["approved_rule"])
            ):
                raise ValueError("Main route governance is invalid")
        if record["effect"] != "future_task_cards_only":
            raise ValueError("route decision effect is invalid")
        return record

    def _validate_rule(self, payload: Any, path: Path) -> dict[str, Any]:
        fields = {
            "schema_version",
            "contract_revision",
            "project_id",
            "source_case_id",
            "source_proposal_id",
            "source_decision_id",
            "route_rule",
            "effect",
            "truth_effect",
        }
        record = self._validate_content_record(
            payload,
            path=path,
            id_field="rule_id",
            prefix="route-rule-",
            semantic_fields=fields,
            label="active route rule",
        )
        self._validate_common_identity(record, "active route rule")
        _validate_id(record["source_case_id"], "attack-case-", "route rule case id")
        _validate_id(
            record["source_proposal_id"], "route-proposal-", "route rule proposal id"
        )
        _validate_id(
            record["source_decision_id"], "route-decision-", "route rule decision id"
        )
        if record["contract_revision"] == ADVERSE_ROUTING_CONTRACT_REVISION:
            validate_persistent_route_rule(record["route_rule"])
        else:
            validate_route_rule(record["route_rule"])
        if record["effect"] != "future_task_cards_only":
            raise ValueError("route rule effect is invalid")
        return record

    def _validate_disablement(self, payload: Any, path: Path) -> dict[str, Any]:
        fields = {
            "schema_version",
            "contract_revision",
            "project_id",
            "rule_id",
            "reason",
            "actor",
            "effect",
            "truth_effect",
        }
        record = self._validate_content_record(
            payload,
            path=path,
            id_field="disablement_id",
            prefix="route-disablement-",
            semantic_fields=fields,
            label="route disablement",
        )
        self._validate_common_identity(record, "route disablement")
        _validate_id(record["rule_id"], "route-rule-", "route disablement rule id")
        if record["contract_revision"] == ADVERSE_ROUTING_CONTRACT_REVISION:
            _require_internal_english_text(
                record["reason"], "route disablement reason"
            )
        else:
            _require_text(record["reason"], "route disablement reason")
        _require_text(record["actor"], "route disablement actor")
        if record["effect"] != "future_task_cards_only":
            raise ValueError("route disablement effect is invalid")
        return record

    def _validate_common_identity(
        self,
        record: dict[str, Any],
        label: str,
        *,
        allowed_schema_versions: set[int] | None = None,
    ) -> None:
        allowed_schema_versions = allowed_schema_versions or {
            ADVERSE_ROUTING_SCHEMA_VERSION
        }
        if (
            record["schema_version"] not in allowed_schema_versions
            or record["contract_revision"] not in ADVERSE_ROUTING_CONTRACT_REVISIONS
            or record["project_id"] != self.store.project_id()
            or record["truth_effect"] != ADVERSE_ROUTING_TRUTH_EFFECT
        ):
            raise ValueError(f"{label} identity is invalid")

    def cases(self) -> list[dict[str, Any]]:
        self.require_enabled()
        return [self._validate_case(payload, path) for path, payload in self._safe_records(self.cases_dir)]

    def proposals(self) -> list[dict[str, Any]]:
        self.require_enabled()
        return [
            self._validate_proposal(payload, path)
            for path, payload in self._safe_records(self.proposals_dir)
        ]

    def decisions(self) -> list[dict[str, Any]]:
        self.require_enabled()
        return [
            self._validate_decision(payload, path)
            for path, payload in self._safe_records(self.decisions_dir)
        ]

    def rules(self) -> list[dict[str, Any]]:
        self.require_enabled()
        return [self._validate_rule(payload, path) for path, payload in self._safe_records(self.rules_dir)]

    def disablements(self) -> list[dict[str, Any]]:
        self.require_enabled()
        return [
            self._validate_disablement(payload, path)
            for path, payload in self._safe_records(self.disablements_dir)
        ]

    def _validated_state(self) -> dict[str, list[dict[str, Any]]]:
        cases = self.cases()
        proposals = self.proposals()
        decisions = self.decisions()
        rules = self.rules()
        disablements = self.disablements()
        cases_by_id = {item["case_id"]: item for item in cases}
        proposals_by_id = {item["proposal_id"]: item for item in proposals}
        decisions_by_id = {item["decision_id"]: item for item in decisions}
        rules_by_id = {item["rule_id"]: item for item in rules}
        if any(
            len(mapping) != len(items)
            for mapping, items in (
                (cases_by_id, cases),
                (proposals_by_id, proposals),
                (decisions_by_id, decisions),
                (rules_by_id, rules),
            )
        ):
            raise ValueError("adverse-routing state contains duplicate ids")
        proposal_cases: set[str] = set()
        for proposal in proposals:
            case_id = proposal["case_id"]
            if case_id not in cases_by_id or case_id in proposal_cases:
                raise ValueError("route proposal has missing or duplicate case lineage")
            proposal_cases.add(case_id)
        if proposal_cases != set(cases_by_id):
            raise ValueError("attack case is missing its immutable route proposal")
        decided_proposals: set[str] = set()
        for decision in decisions:
            proposal_id = decision["proposal_id"]
            if proposal_id not in proposals_by_id or proposal_id in decided_proposals:
                raise ValueError("route decision has missing or duplicate proposal lineage")
            decided_proposals.add(proposal_id)
        materialized_decisions: set[str] = set()
        for rule in rules:
            proposal = proposals_by_id.get(rule["source_proposal_id"])
            decision = decisions_by_id.get(rule["source_decision_id"])
            if (
                proposal is None
                or decision is None
                or decision["decision_id"] in materialized_decisions
                or proposal["case_id"] != rule["source_case_id"]
                or decision["proposal_id"] != proposal["proposal_id"]
                or decision["action"] not in {"approve", "approve_modified"}
                or decision["approved_rule"] != rule["route_rule"]
            ):
                raise ValueError("active route rule lineage is invalid")
            materialized_decisions.add(decision["decision_id"])
        approved_decisions = {
            item["decision_id"]
            for item in decisions
            if item["action"] in {"approve", "approve_modified"}
        }
        if materialized_decisions != approved_decisions:
            raise ValueError("approved route decision is missing its immutable route rule")
        disabled_rules: set[str] = set()
        for disablement in disablements:
            rule_id = disablement["rule_id"]
            if rule_id not in rules_by_id or rule_id in disabled_rules:
                raise ValueError("route disablement has missing or duplicate rule lineage")
            disabled_rules.add(rule_id)
        return {
            "cases": cases,
            "proposals": proposals,
            "decisions": decisions,
            "rules": rules,
            "disablements": disablements,
        }

    def active_rules(self) -> list[dict[str, Any]]:
        state = self._validated_state()
        disabled = {item["rule_id"] for item in state["disablements"]}
        return [item for item in state["rules"] if item["rule_id"] not in disabled]

    @staticmethod
    def _program_math_scope(
        *,
        entry: dict[str, Any],
        related_artifacts: list[dict[str, str]],
    ) -> dict[str, Any]:
        inactive = {
            "active": False,
            "activation": "typed_program_and_output_artifacts",
            "source_research_id": None,
            "source_task_card_sha256": None,
            "artifact_bindings": [],
        }
        metadata = entry.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ValueError("research metadata must be an object")
        review = metadata.get("program_math_review")
        if review is None:
            return inactive
        required = {
            "source_research_id",
            "source_task_card_sha256",
            "source_artifacts",
            "activation",
        }
        if not isinstance(review, dict) or set(review) != required:
            raise ValueError("program-math review metadata fields are not exact")
        source_research_id = review["source_research_id"]
        if (
            not isinstance(source_research_id, str)
            or re.fullmatch(r"[0-9a-f]{12}", source_research_id) is None
        ):
            raise ValueError("program-math review source Research id is invalid")
        task_hash = review["source_task_card_sha256"]
        if not isinstance(task_hash, str) or SHA256_RE.fullmatch(task_hash) is None:
            raise ValueError("program-math review source task-card hash is invalid")
        if review["activation"] != "typed_program_and_output_artifacts":
            raise ValueError("program-math review activation policy is invalid")
        declared = review["source_artifacts"]
        if not isinstance(declared, list) or any(
            not isinstance(item, dict) or set(item) != {"role", "sha256"}
            for item in declared
        ):
            raise ValueError("program-math review source_artifacts are invalid")
        declared_by_role: dict[str, str] = {}
        for item in declared:
            role = item["role"]
            digest = item["sha256"]
            if role not in {"computation_source", "computation_output"}:
                raise ValueError("program-math review names a non-program artifact role")
            if role in declared_by_role or not isinstance(digest, str) or SHA256_RE.fullmatch(digest) is None:
                raise ValueError("program-math review artifact role/hash is invalid")
            declared_by_role[role] = digest
        if set(declared_by_role) != {"computation_source", "computation_output"}:
            raise ValueError("program-math review requires source and output artifacts")
        available: dict[str, str] = {}
        for artifact in related_artifacts:
            if artifact.get("source_research_id") != source_research_id:
                continue
            qualified_role = artifact.get("role")
            if not isinstance(qualified_role, str):
                continue
            role = qualified_role.split(":", 1)[-1]
            if role in declared_by_role:
                if role in available and available[role] != artifact.get("sha256"):
                    raise ValueError("program-math review artifact capability conflicts")
                available[role] = str(artifact.get("sha256"))
        if available != declared_by_role:
            raise ValueError(
                "program-math review is not capability-bound to its exact source/output bytes"
            )
        bindings = [
            {
                "role": role,
                "sha256": declared_by_role[role],
                "source_research_id": source_research_id,
            }
            for role in sorted(declared_by_role)
        ]
        return {
            "active": True,
            "activation": "typed_program_and_output_artifacts",
            "source_research_id": source_research_id,
            "source_task_card_sha256": task_hash,
            "artifact_bindings": bindings,
        }

    @staticmethod
    def _philosophy_scope(*, entry: dict[str, Any]) -> dict[str, Any]:
        metadata = entry.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ValueError("research metadata must be an object")
        declared = validate_adverse_domain_profile(
            metadata.get("adverse_domain_profile")
        )
        paper_binding = metadata.get("paper_continuation")
        paper_profile = None
        if paper_binding is not None:
            if not isinstance(paper_binding, dict):
                raise ValueError("Paper continuation Research binding must be an object")
            paper_profile = paper_binding.get("domain_profile")
            if paper_profile not in ADVERSE_DOMAIN_PROFILES:
                raise ValueError(
                    "Paper continuation Research domain_profile is invalid"
                )
        if declared is not None and paper_profile is not None and declared != paper_profile:
            raise ValueError(
                "Research adverse_domain_profile disagrees with Paper continuation"
            )
        domain_profile = paper_profile or declared
        if paper_profile is not None and declared is not None:
            domain_source = "paper_continuation_and_research_metadata"
        elif paper_profile is not None:
            domain_source = "paper_continuation_binding"
        elif declared is not None:
            domain_source = "explicit_research_metadata"
        else:
            domain_source = "none"
        return {
            "philosophy_active": domain_profile in {"philosophy", "mixed"},
            "philosophy_activation": "validated_research_domain_profile",
            "domain_profile": domain_profile,
            "domain_source": domain_source,
        }

    @staticmethod
    def _matches(rule: dict[str, Any], *, entry: dict[str, Any], work_mode: str) -> bool:
        if work_mode != "refute":
            return False
        trigger = rule["route_rule"]["trigger"]
        if trigger["universal_refute"]:
            return True
        if trigger["research_kinds"] and entry["kind"] not in trigger["research_kinds"]:
            return False
        claim = entry["claim"].casefold()
        if trigger["claim_terms_any"] and not any(
            term.casefold() in claim for term in trigger["claim_terms_any"]
        ):
            return False
        metadata = entry.get("metadata", {})
        raw_signals = metadata.get("logic_signals", [])
        if not isinstance(raw_signals, list) or any(not isinstance(item, str) for item in raw_signals):
            raise ValueError("research logic_signals must be a list of strings")
        signals = {item.strip() for item in raw_signals if item.strip()}
        if trigger["metadata_signals_any"] and not signals.intersection(
            trigger["metadata_signals_any"]
        ):
            return False
        return True

    @staticmethod
    def _rule_projection(record: dict[str, Any]) -> dict[str, Any]:
        rule = record["route_rule"]
        return {
            "rule_id": record["rule_id"],
            "attack_family": rule["attack_family"],
            "trigger": rule["trigger"],
            "instruction": rule["instruction"],
            "false_positive_guards": rule["false_positive_guards"],
            "scope_note": rule["scope_note"],
            "source_case_id": record["source_case_id"],
            "source_decision_id": record["source_decision_id"],
            "truth_effect": ADVERSE_ROUTING_TRUTH_EFFECT,
            "effect": "future_task_cards_only",
        }

    def task_card_binding(
        self,
        *,
        entry: dict[str, Any],
        work_mode: str,
        related_artifacts: list[dict[str, str]] | None = None,
    ) -> dict[str, Any] | None:
        if not self.enabled() or work_mode != "refute":
            return None
        if not self.contract_path.exists():
            self._materialize_state(
                activation_kind="prospective_default_user_authorization",
                actor="v5-adverse-router",
                reason=(
                    "Default future-only worker failure reporting and Main-governed "
                    "route synthesis for newly frozen V5 refute tasks."
                ),
            )
        related_artifacts = related_artifacts or []
        program_math_scope = self._program_math_scope(
            entry=entry,
            related_artifacts=related_artifacts,
        )
        philosophy_scope = self._philosophy_scope(entry=entry)
        selected = [
            self._rule_projection(record)
            for record in self.active_rules()
            if self._matches(record, entry=entry, work_mode=work_mode)
        ]
        selected.sort(key=lambda item: item["rule_id"])
        if len(selected) > MAX_SELECTED_RULES:
            raise ValueError(
                "too many approved adverse rules match this assignment; refine or disable rules"
            )
        baseline = list(BASELINE_ATTACK_RULES)
        if philosophy_scope["philosophy_active"]:
            baseline.extend(dict(item) for item in PHILOSOPHY_ATTACK_RULES)
        if program_math_scope["active"]:
            baseline.append(dict(PROGRAM_MATH_ATTACK_RULE))
        return {
            "schema_version": ADVERSE_TASK_CARD_SCHEMA_VERSION,
            "contract_revision": ADVERSE_ROUTING_CONTRACT_REVISION,
            "enabled": True,
            "selection_policy": "baseline_plus_main_synthesized_future_only",
            "baseline_rules": baseline,
            "baseline_rules_sha256": sha256_json(baseline),
            "approved_rules": selected,
            "approved_rules_sha256": sha256_json(selected),
            "scope_evidence": {**program_math_scope, **philosophy_scope},
            "learning_contract": {
                "counterexample_requires_attack_learning": True,
                "productive_challenge_learning": (
                    "worker_failure_report_when_attack_forces_a_load_bearing_repair"
                ),
                "attack_learning_schema_version": (
                    ADVERSE_ATTACK_LEARNING_SCHEMA_VERSION
                ),
                "reportable_result_kinds": sorted(ATTACK_RESULT_KINDS),
                "worker_rule_proposal": "forbidden",
                "route_synthesis": "main_only",
                "attack_report": "required_at_host_task_completion",
                "truth_effect": ADVERSE_ROUTING_TRUTH_EFFECT,
            },
        }

    def validate_task_card_binding(
        self,
        value: Any,
        *,
        work_mode: str,
        related_artifacts: list[dict[str, str]] | None = None,
        entry: dict[str, Any] | None = None,
        _stored_rules: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        self.require_enabled()
        legacy_required = {
            "schema_version",
            "contract_revision",
            "enabled",
            "selection_policy",
            "baseline_rules",
            "baseline_rules_sha256",
            "approved_rules",
            "approved_rules_sha256",
            "learning_contract",
        }
        if not isinstance(value, dict):
            raise ValueError("adverse-routing task card must be an object")
        task_schema = value.get("schema_version")
        if task_schema == ADVERSE_ROUTING_SCHEMA_VERSION:
            if set(value) != legacy_required:
                raise ValueError("legacy adverse-routing task-card fields are not exact")
            expected_baseline = (
                list(LEGACY_BASELINE_ATTACK_RULES) if work_mode == "refute" else []
            )
            if (
                value["contract_revision"]
                != ADVERSE_ROUTING_LEGACY_CONTRACT_REVISION
                or value["enabled"] is not True
                or value["selection_policy"] != "baseline_plus_user_approved_future_only"
                or value["baseline_rules"] != expected_baseline
                or value["baseline_rules_sha256"] != sha256_json(expected_baseline)
            ):
                raise ValueError("legacy adverse-routing task-card baseline binding is invalid")
        elif task_schema in {2, 3, 4, ADVERSE_TASK_CARD_SCHEMA_VERSION}:
            required = {*legacy_required, "scope_evidence"}
            if set(value) != required:
                raise ValueError("adverse-routing task-card fields are not exact")
            if work_mode != "refute":
                raise ValueError("current adverse-routing binding is refute-only")
            scope = value["scope_evidence"]
            program_scope_fields = {
                "active",
                "activation",
                "source_research_id",
                "source_task_card_sha256",
                "artifact_bindings",
            }
            philosophy_scope_fields = {
                "philosophy_active",
                "philosophy_activation",
                "domain_profile",
                "domain_source",
            }
            expected_scope_fields = (
                program_scope_fields | philosophy_scope_fields
                if task_schema in {4, ADVERSE_TASK_CARD_SCHEMA_VERSION}
                else program_scope_fields
            )
            if not isinstance(scope, dict) or set(scope) != expected_scope_fields:
                raise ValueError("adverse-routing scope evidence fields are not exact")
            if scope["activation"] != "typed_program_and_output_artifacts" or not isinstance(
                scope["active"], bool
            ):
                raise ValueError("adverse-routing scope evidence is invalid")
            if scope["active"]:
                if (
                    not isinstance(scope["source_research_id"], str)
                    or re.fullmatch(r"[0-9a-f]{12}", scope["source_research_id"]) is None
                    or not isinstance(scope["source_task_card_sha256"], str)
                    or SHA256_RE.fullmatch(scope["source_task_card_sha256"]) is None
                ):
                    raise ValueError("active program-math scope identity is invalid")
                bindings = scope["artifact_bindings"]
                expected_bindings = {
                    (
                        item.get("role", "").split(":", 1)[-1],
                        item.get("sha256"),
                        item.get("source_research_id"),
                    )
                    for item in (related_artifacts or [])
                    if item.get("source_research_id") == scope["source_research_id"]
                    and item.get("role", "").split(":", 1)[-1]
                    in {"computation_source", "computation_output"}
                }
                actual_bindings = {
                    (item.get("role"), item.get("sha256"), item.get("source_research_id"))
                    for item in bindings
                    if isinstance(item, dict)
                    and set(item) == {"role", "sha256", "source_research_id"}
                }
                if actual_bindings != expected_bindings or {
                    role for role, _, _ in actual_bindings
                } != {"computation_source", "computation_output"}:
                    raise ValueError("active program-math scope artifacts are not exact")
            elif (
                scope["source_research_id"] is not None
                or scope["source_task_card_sha256"] is not None
                or scope["artifact_bindings"] != []
            ):
                raise ValueError("inactive program-math scope must be empty")
            if task_schema in {4, ADVERSE_TASK_CARD_SCHEMA_VERSION}:
                if entry is None:
                    raise ValueError(
                        "current adverse-routing validation requires source Research"
                    )
                expected_philosophy_scope = self._philosophy_scope(entry=entry)
                if any(
                    scope[key] != expected_philosophy_scope[key]
                    for key in philosophy_scope_fields
                ):
                    raise ValueError(
                        "adverse-routing philosophy scope drifted or was inferred from text"
                    )
                expected_baseline = list(BASELINE_ATTACK_RULES)
                if expected_philosophy_scope["philosophy_active"]:
                    expected_baseline.extend(
                        dict(item) for item in PHILOSOPHY_ATTACK_RULES
                    )
                expected_revision = (
                    ADVERSE_ROUTING_CONTRACT_REVISION
                    if task_schema == ADVERSE_TASK_CARD_SCHEMA_VERSION
                    else ADVERSE_ROUTING_USER_RULE_CONTRACT_REVISION
                )
            else:
                expected_baseline = list(LEGACY_BASELINE_ATTACK_RULES)
                expected_revision = (
                    ADVERSE_ROUTING_LEGACY_CONTRACT_REVISION
                    if task_schema == 2
                    else ADVERSE_ROUTING_PRODUCTIVE_CONTRACT_REVISION
                )
            if scope["active"]:
                expected_baseline.append(dict(PROGRAM_MATH_ATTACK_RULE))
            if (
                value["contract_revision"] != expected_revision
                or value["enabled"] is not True
                or value["selection_policy"]
                != (
                    "baseline_plus_main_synthesized_future_only"
                    if task_schema == ADVERSE_TASK_CARD_SCHEMA_VERSION
                    else "baseline_plus_user_approved_future_only"
                )
                or value["baseline_rules"] != expected_baseline
                or value["baseline_rules_sha256"] != sha256_json(expected_baseline)
            ):
                raise ValueError("adverse-routing task-card baseline binding is invalid")
        else:
            raise ValueError("adverse-routing task-card schema version is unsupported")
        approved = value["approved_rules"]
        selected_cap = (
            MAX_SELECTED_RULES
            if task_schema == ADVERSE_TASK_CARD_SCHEMA_VERSION
            else LEGACY_MAX_SELECTED_RULES
        )
        if not isinstance(approved, list) or len(approved) > selected_cap:
            raise ValueError("adverse-routing approved rules are invalid")
        if value["approved_rules_sha256"] != sha256_json(approved):
            raise ValueError("adverse-routing approved-rule hash mismatch")
        stored = (
            _stored_rules
            if _stored_rules is not None
            else {
                record["rule_id"]: self._rule_projection(record)
                for record in self.rules()
            }
        )
        if any(not isinstance(item, dict) or stored.get(item.get("rule_id")) != item for item in approved):
            raise ValueError("adverse-routing task card names an unapproved or drifted rule")
        expected_learning = (
            {
                "counterexample_requires_attack_learning": True,
                "proposal_activation": "user_decision_only",
                "attack_report": "required_at_host_task_completion",
                "truth_effect": ADVERSE_ROUTING_TRUTH_EFFECT,
            }
            if task_schema in {1, 2}
            else {
                "counterexample_requires_attack_learning": True,
                "productive_challenge_learning": (
                    "worker_failure_report_when_attack_forces_a_load_bearing_repair"
                    if task_schema == ADVERSE_TASK_CARD_SCHEMA_VERSION
                    else "structured_when_attack_forces_a_load_bearing_repair"
                ),
                "attack_learning_schema_version": (
                    ADVERSE_ATTACK_LEARNING_SCHEMA_VERSION
                    if task_schema == ADVERSE_TASK_CARD_SCHEMA_VERSION
                    else ADVERSE_ATTACK_LEARNING_RULE_SCHEMA_VERSION
                ),
                "reportable_result_kinds": sorted(ATTACK_RESULT_KINDS),
                **(
                    {
                        "worker_rule_proposal": "forbidden",
                        "route_synthesis": "main_only",
                    }
                    if task_schema == ADVERSE_TASK_CARD_SCHEMA_VERSION
                    else {"proposal_activation": "user_decision_only"}
                ),
                "attack_report": "required_at_host_task_completion",
                "truth_effect": ADVERSE_ROUTING_TRUTH_EFFECT,
            }
        )
        if value["learning_contract"] != expected_learning:
            raise ValueError("adverse-routing task-card learning contract is invalid")
        return value

    def capture_counterexample(
        self,
        *,
        card: dict[str, Any],
        assignment: dict[str, Any],
        payload: dict[str, Any],
        counterexample_research_id: str,
        return_sha256: str,
    ) -> dict[str, Any]:
        self.require_enabled()
        if card.get("adverse_routing", {}).get("schema_version") in (
            ADVERSE_STRUCTURED_ATTACK_TASK_CARD_SCHEMAS
        ):
            return self.capture_attack(
                card=card,
                assignment=assignment,
                payload=payload,
                attack_research_id=counterexample_research_id,
                return_sha256=return_sha256,
            )
        if payload.get("outcome") != "counterexample":
            raise ValueError("only counterexample returns can create attack cases")
        learning = validate_attack_learning(payload.get("attack_learning"))
        scope_id = card["control_plane"].get("host_task_scope_id")
        if not isinstance(scope_id, str) or not scope_id.strip():
            scope_id = f"round:{card['round_id']}"
        case_semantic = {
            "schema_version": ADVERSE_ROUTING_SCHEMA_VERSION,
            "contract_revision": card["adverse_routing"]["contract_revision"],
            "project_id": self.store.project_id(),
            "round_id": card["round_id"],
            "assignment_id": card["assignment_id"],
            "host_task_scope_id": scope_id,
            "target_research_id": assignment["research_id"],
            "counterexample_research_id": counterexample_research_id,
            "task_card_sha256": assignment["task_card_sha256"],
            "return_sha256": return_sha256,
            "target_claim": card["narrative_plane"]["claim"],
            "attack_learning": learning,
            "evidence_status": "worker_reported_counterexample_nontruth",
            "truth_effect": ADVERSE_ROUTING_TRUTH_EFFECT,
        }
        case_record = self._write_content_record(
            directory=self.cases_dir,
            id_field="case_id",
            prefix="attack-case-",
            semantic=case_semantic,
        )
        case_path = self.cases_dir / f"{case_record['case_id']}.json"
        self._validate_case(case_record, case_path)
        proposal_semantic = {
            "schema_version": ADVERSE_ROUTING_SCHEMA_VERSION,
            "contract_revision": card["adverse_routing"]["contract_revision"],
            "project_id": self.store.project_id(),
            "case_id": case_record["case_id"],
            "route_rule": learning["route_rule"],
            "proposal_status": "pending_user_decision",
            "activation_policy": "user_decision_only",
            "truth_effect": ADVERSE_ROUTING_TRUTH_EFFECT,
        }
        proposal_record = self._write_content_record(
            directory=self.proposals_dir,
            id_field="proposal_id",
            prefix="route-proposal-",
            semantic=proposal_semantic,
        )
        proposal_path = self.proposals_dir / f"{proposal_record['proposal_id']}.json"
        self._validate_proposal(proposal_record, proposal_path)
        return {
            "case_id": case_record["case_id"],
            "proposal_id": proposal_record["proposal_id"],
            "evidence_status": case_record["evidence_status"],
            "activation_policy": proposal_record["activation_policy"],
        }

    def capture_attack(
        self,
        *,
        card: dict[str, Any],
        assignment: dict[str, Any],
        payload: dict[str, Any],
        attack_research_id: str,
        return_sha256: str,
    ) -> dict[str, Any]:
        """Capture one surviving counterexample or productive challenge as nontruth."""

        self.require_enabled()
        if card.get("adverse_routing", {}).get("schema_version") not in (
            ADVERSE_STRUCTURED_ATTACK_TASK_CARD_SCHEMAS
        ):
            raise ValueError("current attack capture requires a current adverse task card")
        outcome = payload.get("outcome")
        if outcome == "counterexample":
            attack_result = "surviving_counterexample"
            evidence_status = "worker_reported_counterexample_nontruth"
        elif outcome in PRODUCTIVE_ATTACK_OUTCOMES:
            attack_result = "productive_challenge"
            evidence_status = "worker_reported_productive_challenge_nontruth"
        else:
            raise ValueError(
                "only surviving counterexamples or productive challenges create attack cases"
            )
        learning = validate_attack_learning(
            payload.get("attack_learning"),
            require_current=(
                card["adverse_routing"]["schema_version"]
                == ADVERSE_TASK_CARD_SCHEMA_VERSION
            ),
            expected_result_kind=attack_result,
        )
        scope_id = card["control_plane"].get("host_task_scope_id")
        if not isinstance(scope_id, str) or not scope_id.strip():
            scope_id = f"round:{card['round_id']}"
        case_semantic = {
            "schema_version": (
                ADVERSE_CASE_SCHEMA_VERSION
                if card["adverse_routing"]["schema_version"]
                == ADVERSE_TASK_CARD_SCHEMA_VERSION
                else ADVERSE_PRODUCTIVE_CASE_SCHEMA_VERSION
            ),
            "contract_revision": card["adverse_routing"]["contract_revision"],
            "project_id": self.store.project_id(),
            "round_id": card["round_id"],
            "assignment_id": card["assignment_id"],
            "host_task_scope_id": scope_id,
            "target_research_id": assignment["research_id"],
            "attack_research_id": _require_text(
                attack_research_id, "attack Research id"
            ),
            "attack_result": attack_result,
            "worker_outcome": outcome,
            "task_card_sha256": assignment["task_card_sha256"],
            "return_sha256": return_sha256,
            "target_claim": card["narrative_plane"]["claim"],
            "attack_learning": learning,
            "evidence_status": evidence_status,
            "truth_effect": ADVERSE_ROUTING_TRUTH_EFFECT,
        }
        case_record = self._write_content_record(
            directory=self.cases_dir,
            id_field="case_id",
            prefix="attack-case-",
            semantic=case_semantic,
        )
        case_path = self.cases_dir / f"{case_record['case_id']}.json"
        self._validate_case(case_record, case_path)
        current = (
            card["adverse_routing"]["schema_version"]
            == ADVERSE_TASK_CARD_SCHEMA_VERSION
        )
        proposal_semantic = {
            "schema_version": ADVERSE_ROUTING_SCHEMA_VERSION,
            "contract_revision": card["adverse_routing"]["contract_revision"],
            "project_id": self.store.project_id(),
            "case_id": case_record["case_id"],
            **({} if current else {"route_rule": learning["route_rule"]}),
            "proposal_status": (
                "pending_main_synthesis" if current else "pending_user_decision"
            ),
            "activation_policy": (
                "main_synthesis_only" if current else "user_decision_only"
            ),
            "truth_effect": ADVERSE_ROUTING_TRUTH_EFFECT,
        }
        proposal_record = self._write_content_record(
            directory=self.proposals_dir,
            id_field="proposal_id",
            prefix="route-proposal-",
            semantic=proposal_semantic,
        )
        proposal_path = self.proposals_dir / f"{proposal_record['proposal_id']}.json"
        self._validate_proposal(proposal_record, proposal_path)
        return {
            "case_id": case_record["case_id"],
            "proposal_id": proposal_record["proposal_id"],
            "attack_result": attack_result,
            "evidence_status": evidence_status,
            "activation_policy": proposal_record["activation_policy"],
        }

    def _proposal(self, proposal_id: str) -> dict[str, Any]:
        proposal_id = _validate_id(proposal_id, "route-proposal-", "route proposal id")
        path = self.proposals_dir / f"{proposal_id}.json"
        if path.is_symlink() or not path.is_file():
            raise KeyError(f"unknown route proposal: {proposal_id}")
        return self._validate_proposal(self.store._read_json(path), path)

    def _rule(self, rule_id: str) -> dict[str, Any]:
        rule_id = _validate_id(rule_id, "route-rule-", "route rule id")
        path = self.rules_dir / f"{rule_id}.json"
        if path.is_symlink() or not path.is_file():
            raise KeyError(f"unknown route rule: {rule_id}")
        return self._validate_rule(self.store._read_json(path), path)

    def _materialize_rule(
        self, *, proposal: dict[str, Any], decision: dict[str, Any]
    ) -> dict[str, Any] | None:
        if decision["action"] == "reject":
            return None
        rule_semantic = {
            "schema_version": ADVERSE_ROUTING_SCHEMA_VERSION,
            "contract_revision": ADVERSE_ROUTING_CONTRACT_REVISION,
            "project_id": self.store.project_id(),
            "source_case_id": proposal["case_id"],
            "source_proposal_id": proposal["proposal_id"],
            "source_decision_id": decision["decision_id"],
            "route_rule": decision["approved_rule"],
            "effect": "future_task_cards_only",
            "truth_effect": ADVERSE_ROUTING_TRUTH_EFFECT,
        }
        rule = self._write_content_record(
            directory=self.rules_dir,
            id_field="rule_id",
            prefix="route-rule-",
            semantic=rule_semantic,
        )
        return self._validate_rule(rule, self.rules_dir / f"{rule['rule_id']}.json")

    def decide(
        self,
        proposal_id: str,
        payload: dict[str, Any],
        *,
        actor: str,
    ) -> dict[str, Any]:
        self.require_enabled()
        actor = _require_text(actor, "route decision actor")
        if actor.casefold() not in {"main", "chalxius-main"}:
            raise ValueError("route decisions require Main authority")
        if not isinstance(payload, dict) or set(payload) != {
            "action",
            "reason",
            "rule",
            "governance",
        }:
            raise ValueError("route decision input fields are not exact")
        action = payload["action"]
        if action not in {"approve_modified", "reject"}:
            raise ValueError("route decision action is invalid")
        reason = _require_internal_english_text(
            payload["reason"], "route decision reason"
        )
        proposal = self._proposal(proposal_id)
        current_proposal = (
            proposal["contract_revision"] == ADVERSE_ROUTING_CONTRACT_REVISION
        )
        if not current_proposal:
            if action == "reject":
                pass
            elif action == "approve_modified":
                # Main may synthesize an abstract successor from a legacy worker
                # suggestion, but the legacy text is never copied directly.
                pass
        governance = payload["governance"]
        if action == "approve_modified":
            if not isinstance(governance, dict) or set(governance) != {
                "abstraction_level",
                "concrete_evidence_excluded",
                "compression",
            }:
                raise ValueError("Main synthesis governance fields are not exact")
            if (
                governance["abstraction_level"] != "mechanism"
                or governance["concrete_evidence_excluded"] is not True
                or governance["compression"] not in {"within_budget", "compressed"}
            ):
                raise ValueError("Main synthesis governance is invalid")
            approved_rule = validate_persistent_route_rule(
                payload["rule"], label="Main-synthesized route rule"
            )
            decision_governance = {
                "decision_authority": "main",
                **governance,
                "persistent_text_codepoints": _persistent_route_codepoints(
                    approved_rule
                ),
            }
        else:
            if payload["rule"] is not None or governance is not None:
                raise ValueError("reject requires rule=null and governance=null")
            approved_rule = None
            decision_governance = None
        with self.store.v5_mutation_lock(command="attack-route-decide"):
            prior = [item for item in self.decisions() if item["proposal_id"] == proposal_id]
            expected = {
                "action": action,
                "reason": reason,
                "actor": actor,
                "approved_rule": approved_rule,
                "governance": decision_governance,
            }
            if prior:
                if len(prior) != 1 or any(
                    prior[0][key] != value for key, value in expected.items()
                ):
                    raise ValueError("route proposal already has a different immutable decision")
                decision = prior[0]
            else:
                if (
                    approved_rule is not None
                    and len(self.active_rules()) >= MAX_ACTIVE_ROUTE_RULES
                ):
                    raise ValueError(
                        f"active route hard cap {MAX_ACTIVE_ROUTE_RULES} reached; Main "
                        "must consolidate or disable a route before adding another"
                    )
                semantic = {
                    "schema_version": ADVERSE_ROUTING_SCHEMA_VERSION,
                    "contract_revision": ADVERSE_ROUTING_CONTRACT_REVISION,
                    "project_id": self.store.project_id(),
                    "proposal_id": proposal_id,
                    **expected,
                    "effect": "future_task_cards_only",
                    "truth_effect": ADVERSE_ROUTING_TRUTH_EFFECT,
                }
                decision = self._write_content_record(
                    directory=self.decisions_dir,
                    id_field="decision_id",
                    prefix="route-decision-",
                    semantic=semantic,
                )
                decision = self._validate_decision(
                    decision, self.decisions_dir / f"{decision['decision_id']}.json"
                )
            rule = self._materialize_rule(proposal=proposal, decision=decision)
        return {
            "decision_id": decision["decision_id"],
            "proposal_id": proposal_id,
            "action": action,
            "rule_id": rule["rule_id"] if rule is not None else None,
            "effect": "future_task_cards_only",
            "truth_effect": ADVERSE_ROUTING_TRUTH_EFFECT,
        }

    def disable(self, rule_id: str, *, reason: str, actor: str) -> dict[str, Any]:
        self.require_enabled()
        rule = self._rule(rule_id)
        reason = _require_internal_english_text(reason, "route disablement reason")
        actor = _require_text(actor, "route disablement actor")
        with self.store.v5_mutation_lock(command="attack-route-disable"):
            prior = [item for item in self.disablements() if item["rule_id"] == rule_id]
            if prior:
                if len(prior) != 1 or prior[0]["reason"] != reason or prior[0]["actor"] != actor:
                    raise ValueError("route rule already has a different immutable disablement")
                record = prior[0]
            else:
                semantic = {
                    "schema_version": ADVERSE_ROUTING_SCHEMA_VERSION,
                    "contract_revision": ADVERSE_ROUTING_CONTRACT_REVISION,
                    "project_id": self.store.project_id(),
                    "rule_id": rule["rule_id"],
                    "reason": reason,
                    "actor": actor,
                    "effect": "future_task_cards_only",
                    "truth_effect": ADVERSE_ROUTING_TRUTH_EFFECT,
                }
                record = self._write_content_record(
                    directory=self.disablements_dir,
                    id_field="disablement_id",
                    prefix="route-disablement-",
                    semantic=semantic,
                )
                record = self._validate_disablement(
                    record,
                    self.disablements_dir / f"{record['disablement_id']}.json",
                )
        return {
            "disablement_id": record["disablement_id"],
            "rule_id": rule_id,
            "effect": "future_task_cards_only",
            "truth_effect": ADVERSE_ROUTING_TRUTH_EFFECT,
        }

    def report(self, *, host_task_scope_id: str) -> dict[str, Any]:
        self.require_enabled()
        requested_scope = _require_text(
            host_task_scope_id, "attack report host task scope id"
        )
        normalized_scope = normalize_host_task_scope_id(
            requested_scope,
            workflow_evidence_version=self.store.workflow_evidence_version(),
        )
        if normalized_scope is None:
            raise RuntimeError("attack report host scope normalization returned null")
        scope_id = normalized_scope
        accepted_scope_ids = {requested_scope, scope_id}
        state = self._validated_state()
        decisions = {item["proposal_id"]: item for item in state["decisions"]}
        rules_by_decision = {
            item["source_decision_id"]: item for item in state["rules"]
        }
        disabled = {item["rule_id"] for item in state["disablements"]}
        proposals_by_case = {item["case_id"]: item for item in state["proposals"]}
        selected_cases = [
            case
            for case in state["cases"]
            if case["host_task_scope_id"] in accepted_scope_ids
        ]
        cases_by_assignment: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for case in state["cases"]:
            cases_by_assignment.setdefault(
                (case["round_id"], case["assignment_id"]), []
            ).append(case)

        lifecycle = self.store.v5_lifecycle()
        round_items: list[dict[str, Any]] = []
        assignment_items: list[dict[str, Any]] = []
        card_items: list[dict[str, Any]] = []
        return_items: list[dict[str, Any]] = []
        pair_items: list[dict[str, Any]] = []
        included_assignments: set[tuple[str, str]] = set()
        quarantines_by_round: dict[str, dict[str, dict[str, Any]]] = {}
        for item in lifecycle._quarantine_records():
            round_id = item.get("round_id")
            assignment_id = item.get("assignment_id")
            if isinstance(round_id, str) and isinstance(assignment_id, str):
                quarantines_by_round.setdefault(round_id, {})[
                    assignment_id
                ] = item
        if self.store.rounds_dir.exists():
            for round_path in sorted(self.store.rounds_dir.glob("round-*")):
                manifest_path = round_path / "round.json"
                if manifest_path.is_symlink() or not manifest_path.is_file():
                    continue
                raw_manifest = self.store._read_json(manifest_path)
                if not isinstance(raw_manifest, dict) or raw_manifest.get(
                    "schema_version"
                ) != 5:
                    continue
                manifest_scope = raw_manifest.get("host_task_scope_id")
                current_markers = {
                    "assignment_contract_revision",
                    "primary_worker_count",
                    "independent_adverse_pairs",
                }.intersection(raw_manifest)
                if manifest_scope is not None:
                    if manifest_scope not in accepted_scope_ids:
                        continue
                elif current_markers:
                    # A current manifest may never make its scope unknowable.
                    lifecycle._round_manifest(round_path.name)
                    raise ValueError("current V5 round manifest host scope is missing")
                else:
                    # Historical null-scope cards remain readable but cannot be
                    # silently attributed to a new host task.  A historical
                    # non-null unanimous card scope remains reportable.
                    legacy_scopes: set[str | None] = set()
                    for assignment in raw_manifest.get("assignments", []):
                        if not isinstance(assignment, dict):
                            continue
                        relpath = assignment.get("task_card_relpath")
                        if not isinstance(relpath, str):
                            continue
                        card_path = contained_path(
                            self.store.root,
                            relpath,
                            "legacy attack-report task card path",
                        )
                        if card_path.is_symlink() or not card_path.is_file():
                            continue
                        card = self.store._read_json(card_path)
                        control = card.get("control_plane", {})
                        legacy_scopes.add(control.get("host_task_scope_id"))
                    matching = legacy_scopes.intersection(accepted_scope_ids)
                    if not matching:
                        continue
                    if None in legacy_scopes or len(legacy_scopes) != 1:
                        raise ValueError(
                            "host-scope attack report found mixed or missing card scope"
                        )
                round_dir, manifest = lifecycle._round_manifest(round_path.name)
                effective_scope = manifest.get("host_task_scope_id")
                if effective_scope is None:
                    effective_scope = next(
                        iter(
                            {
                                lifecycle.store._read_json(
                                    lifecycle.store.root
                                    / assignment["task_card_relpath"]
                                )["control_plane"].get("host_task_scope_id")
                                for assignment in manifest["assignments"]
                            }
                        )
                    )
                if effective_scope not in accepted_scope_ids:
                    raise ValueError("host-scope attack report round scope drifted")
                abort = self.store.reasoning_modes().work_unit_abort(
                    manifest["round_id"]
                )
                quarantined = quarantines_by_round.get(manifest["round_id"], {})
                status_by_assignment: dict[str, str] = {}
                card_by_assignment: dict[str, dict[str, Any]] = {}
                assignment_by_id = {
                    item["assignment_id"]: item for item in manifest["assignments"]
                }
                for assignment in manifest["assignments"]:
                    assignment_id = assignment["assignment_id"]
                    included_assignments.add((manifest["round_id"], assignment_id))
                    assignment_cases = cases_by_assignment.get(
                        (manifest["round_id"], assignment_id), []
                    )
                    if any(
                        item["host_task_scope_id"] not in accepted_scope_ids
                        for item in assignment_cases
                    ):
                        raise ValueError(
                            "attack case carries a mixed host task scope"
                        )
                    card_path = self.store.root / assignment["task_card_relpath"]
                    card = self.store._read_json(card_path)
                    card_by_assignment[assignment_id] = card
                    control = card["control_plane"]
                    card_scope = control.get("host_task_scope_id")
                    if card_scope not in accepted_scope_ids:
                        raise ValueError(
                            "host-scope attack report found mixed or missing card scope"
                        )
                    role = control.get("assignment_role", "primary")
                    pair_binding = control.get("independent_adverse_pair")
                    receipt_path = (
                        round_dir / "returns" / f"{assignment_id}.receipt.json"
                    )
                    return_path = self.store.root / assignment["return_relpath"]
                    receipt = None
                    if receipt_path.exists():
                        receipt = lifecycle._validated_ingest_receipt(
                            round_dir=round_dir,
                            assignment=assignment,
                        )
                        assignment_state = "ingested"
                    elif assignment_id in quarantined:
                        assignment_state = "quarantined"
                    elif abort is not None:
                        assignment_state = "frozen_aborted"
                    elif return_path.exists():
                        assignment_state = "return_present"
                    else:
                        assignment_state = "awaiting_return"
                    status_by_assignment[assignment_id] = assignment_state
                    assignment_items.append(
                        {
                            "round_id": manifest["round_id"],
                            "assignment_id": assignment_id,
                            "research_id": assignment["research_id"],
                            "worker_id": assignment["worker_id"],
                            "worker_context_id": control.get("worker_context_id"),
                            "work_mode": assignment["work_mode"],
                            "assignment_role": role,
                            "pair_id": (
                                pair_binding.get("pair_id")
                                if isinstance(pair_binding, dict)
                                else None
                            ),
                            "state": assignment_state,
                            "host_task_scope_id": scope_id,
                        }
                    )
                    card_items.append(
                        {
                            "round_id": manifest["round_id"],
                            "assignment_id": assignment_id,
                            "task_card_sha256": assignment["task_card_sha256"],
                            "worker_id": card["worker_id"],
                            "worker_context_id": control.get("worker_context_id"),
                            "assignment_role": role,
                            "pair_id": (
                                pair_binding.get("pair_id")
                                if isinstance(pair_binding, dict)
                                else None
                            ),
                            "host_task_scope_id": scope_id,
                        }
                    )
                    return_items.append(
                        {
                            "round_id": manifest["round_id"],
                            "assignment_id": assignment_id,
                            "state": assignment_state,
                            "return_present": return_path.is_file()
                            and not return_path.is_symlink(),
                            "return_sha256": (
                                sha256_bytes(return_path.read_bytes())
                                if return_path.is_file()
                                and not return_path.is_symlink()
                                else None
                            ),
                            "receipt_id": (
                                receipt.get("receipt_id")
                                if isinstance(receipt, dict)
                                else None
                            ),
                            "result_research_id": (
                                receipt.get("research_id")
                                if isinstance(receipt, dict)
                                else None
                            ),
                            "host_task_scope_id": scope_id,
                        }
                    )
                pairs = manifest.get("independent_adverse_pairs", [])
                for pair in pairs:
                    adverse_id = pair["adverse_assignment_id"]
                    assignment_cases = cases_by_assignment.get(
                        (manifest["round_id"], adverse_id), []
                    )
                    if any(
                        item["host_task_scope_id"] not in accepted_scope_ids
                        for item in assignment_cases
                    ):
                        raise ValueError(
                            "paired adverse case carries a mixed host task scope"
                        )
                    case_ids = sorted(item["case_id"] for item in assignment_cases)
                    adverse_state = status_by_assignment[adverse_id]
                    if adverse_state == "ingested":
                        pair_status = (
                            "attack-recorded"
                            if case_ids
                            else "dispatched-no-surviving-attack"
                        )
                    else:
                        pair_status = "pending"
                    pair_items.append(
                        {
                            "pair_id": pair["pair_id"],
                            "round_id": manifest["round_id"],
                            "research_id": pair["research_id"],
                            "primary_assignment_id": pair[
                                "primary_assignment_id"
                            ],
                            "adverse_assignment_id": adverse_id,
                            "primary_worker_id": pair["primary_worker_id"],
                            "adverse_worker_id": pair["adverse_worker_id"],
                            "primary_context_id": pair["primary_context_id"],
                            "adverse_context_id": pair["adverse_context_id"],
                            "adverse_return_state": adverse_state,
                            "attack_case_ids": case_ids,
                            "coverage_status": pair_status,
                            "host_task_scope_id": scope_id,
                        }
                    )
                paired_primary_ids = {
                    item["primary_assignment_id"] for item in pairs
                }
                for assignment in manifest["assignments"]:
                    card = card_by_assignment[assignment["assignment_id"]]
                    role = card["control_plane"].get(
                        "assignment_role", "primary"
                    )
                    if role != "primary":
                        continue
                    source = lifecycle._research_record(assignment["research_id"])
                    if (
                        independent_adverse_pair_is_required(
                            source,
                            primary_work_mode=assignment["work_mode"],
                        )
                        and assignment["assignment_id"] not in paired_primary_ids
                    ):
                        pair_items.append(
                            {
                                "pair_id": "missing-pair-"
                                + sha256_json(
                                    {
                                        "round_id": manifest["round_id"],
                                        "assignment_id": assignment[
                                            "assignment_id"
                                        ],
                                    }
                                ),
                                "round_id": manifest["round_id"],
                                "research_id": assignment["research_id"],
                                "primary_assignment_id": assignment[
                                    "assignment_id"
                                ],
                                "adverse_assignment_id": None,
                                "primary_worker_id": assignment["worker_id"],
                                "adverse_worker_id": None,
                                "primary_context_id": card["control_plane"].get(
                                    "worker_context_id"
                                ),
                                "adverse_context_id": None,
                                "adverse_return_state": "not_dispatched",
                                "attack_case_ids": [],
                                "coverage_status": "missing-dispatch",
                                "host_task_scope_id": scope_id,
                            }
                        )
                round_items.append(
                    {
                        "round_id": manifest["round_id"],
                        "manifest_sha256": manifest["manifest_sha256"],
                        "primary_worker_count": manifest.get(
                            "primary_worker_count",
                            len(manifest["assignments"]),
                        ),
                        "assignment_count": len(manifest["assignments"]),
                        "paired_adverse_count": len(pairs),
                        "host_task_scope_id": scope_id,
                    }
                )

        items: list[dict[str, Any]] = []
        for case in selected_cases:
            if (case["round_id"], case["assignment_id"]) not in included_assignments:
                raise ValueError(
                    "attack case scope has no matching validated round assignment"
                )
            proposal = proposals_by_case[case["case_id"]]
            decision = decisions.get(proposal["proposal_id"])
            rule = rules_by_decision.get(decision["decision_id"]) if decision else None
            if decision is None:
                proposal_status = "pending_main_synthesis"
            else:
                proposal_status = decision["action"]
            items.append(
                {
                    "case_id": case["case_id"],
                    "round_id": case["round_id"],
                    "assignment_id": case["assignment_id"],
                    "proposal_id": proposal["proposal_id"],
                    "evidence_status": case["evidence_status"],
                    "attack_result": case.get(
                        "attack_result", "surviving_counterexample"
                    ),
                    "worker_outcome": case.get("worker_outcome", "counterexample"),
                    "attack_family": case["attack_learning"]["attack_family"],
                    "target_claim": case["target_claim"],
                    "failure_mechanism": case["attack_learning"]["failure_mechanism"],
                    "premise_witnesses": case["attack_learning"]["premise_witnesses"],
                    "conclusion_failure_witness": case["attack_learning"][
                        "conclusion_failure_witness"
                    ],
                    "reproduction_steps": case["attack_learning"]["reproduction_steps"],
                    "success_boundary": case["attack_learning"]["success_boundary"],
                    "value_effects": case["attack_learning"].get(
                        "value_effects", []
                    ),
                    "proposed_rule": proposal.get("route_rule"),
                    "proposal_status": proposal_status,
                    "decision_id": decision["decision_id"] if decision else None,
                    "active_rule_id": (
                        rule["rule_id"]
                        if rule is not None and rule["rule_id"] not in disabled
                        else None
                    ),
                    "host_task_scope_id": scope_id,
                }
            )
        items.sort(key=lambda item: item["case_id"])
        pending_user = sum(
            item["proposal_status"] == "pending_user_decision" for item in items
        )
        pending_main = sum(
            item["proposal_status"] == "pending_main_synthesis" for item in items
        )
        approved = sum(
            item["proposal_status"] in {"approve", "approve_modified"} for item in items
        )
        rejected = sum(item["proposal_status"] == "reject" for item in items)
        pair_statuses = {item["coverage_status"] for item in pair_items}
        if not round_items or "missing-dispatch" in pair_statuses:
            coverage_status = "missing-dispatch"
        elif "pending" in pair_statuses:
            coverage_status = "pending"
        elif items:
            coverage_status = "attack-recorded"
        elif pair_items:
            coverage_status = "dispatched-no-surviving-attack"
        else:
            coverage_status = "not-required"
        if items:
            zero_interpretation = "nonzero_attack_cases_enumerated"
        elif coverage_status == "dispatched-no-surviving-attack":
            zero_interpretation = (
                "complete_dispatch_with_zero_surviving_attack_cases"
            )
        elif coverage_status == "not-required":
            zero_interpretation = (
                "no_independent_adverse_dispatch_required_in_scope"
            )
        else:
            zero_interpretation = (
                "zero_cases_does_not_establish_completed_dispatch"
            )
        summary = {
            "round_count": len(round_items),
            "assignment_count": len(assignment_items),
            "card_count": len(card_items),
            "return_count": len(return_items),
            "paired_adverse_count": len(pair_items),
            "worker_reported_success_count": len(items),
            "surviving_counterexample_count": sum(
                item["attack_result"] == "surviving_counterexample"
                for item in items
            ),
            "productive_challenge_count": sum(
                item["attack_result"] == "productive_challenge"
                for item in items
            ),
            "pending_user_decision_count": pending_user,
            "pending_main_synthesis_count": pending_main,
            "approved_count": approved,
            "rejected_count": rejected,
            "missing_dispatch_count": sum(
                item["coverage_status"] == "missing-dispatch"
                for item in pair_items
            ),
            "pending_dispatch_count": sum(
                item["coverage_status"] == "pending" for item in pair_items
            ),
            "dispatched_no_surviving_attack_count": sum(
                item["coverage_status"] == "dispatched-no-surviving-attack"
                for item in pair_items
            ),
        }
        report_semantic = {
            "schema_version": ADVERSE_ROUTING_SCHEMA_VERSION,
            "contract_revision": ADVERSE_ROUTING_CONTRACT_REVISION,
            "coverage_contract_revision": "chalxius-host-scope-attack-report-1",
            "project_id": self.store.project_id(),
            "host_task_scope_id": scope_id,
            "generated_at": _utc_now(),
            "summary": summary,
            "rounds": round_items,
            "assignments": assignment_items,
            "cards": card_items,
            "returns": return_items,
            "paired_adverse_coverage": pair_items,
            "coverage_status": coverage_status,
            "scope_complete": coverage_status
            not in {"pending", "missing-dispatch"},
            "zero_attack_interpretation": zero_interpretation,
            "dispatch_semantics": (
                "dispatch means one immutable assignment plus task card; actual host "
                "process isolation remains a Host attestation, while distinct worker "
                "and context ids are mandatory frozen contracts"
            ),
            "attacks": items,
            "user_decision_required": False,
            "allowed_user_actions": [],
            "routing_change_policy": "no_route_change_without_main_synthesis",
            "evidence_boundary": (
                "worker-reported counterexamples and productive challenges are nontruth "
                "Research; attack-report and routing approval neither certify a refutation "
                "nor create a Fact"
            ),
            "truth_effect": ADVERSE_ROUTING_TRUTH_EFFECT,
            "project_effect": "report_only",
        }
        report = {
            **report_semantic,
            "report_sha256": sha256_json(report_semantic),
        }
        return validate_host_scope_attack_report(report)

    def recommendation_report(
        self,
        *,
        host_task_scope_id: str,
    ) -> dict[str, Any]:
        """Project a few concrete worker failure reports for Main synthesis."""

        self.require_enabled()
        requested_scope = _require_text(
            host_task_scope_id, "attack report host task scope id"
        )
        scope_id = normalize_host_task_scope_id(
            requested_scope,
            workflow_evidence_version=self.store.workflow_evidence_version(),
        )
        if scope_id is None:
            raise RuntimeError("attack report host scope normalization returned null")
        accepted_scope_ids = {requested_scope, scope_id}
        state = self._validated_state()
        proposals_by_case = {
            item["case_id"]: item for item in state["proposals"]
        }
        decisions_by_proposal = {
            item["proposal_id"]: item for item in state["decisions"]
        }
        groups: dict[str, dict[str, Any]] = {}
        pending_proposal_ids: set[str] = set()
        for case in state["cases"]:
            if case["host_task_scope_id"] not in accepted_scope_ids:
                continue
            proposal = proposals_by_case[case["case_id"]]
            if proposal["proposal_id"] in decisions_by_proposal:
                continue
            pending_proposal_ids.add(proposal["proposal_id"])
            learning = case["attack_learning"]
            signature = learning["attack_family"]
            if signature not in ATTACK_FAMILY_PLAIN_LANGUAGE:
                # Unknown families remain in --full. Main never receives an
                # invented abstraction merely to fill a queue quota.
                continue
            group = groups.setdefault(
                signature,
                {
                    "attack_family": signature,
                    "entries": [],
                    "result_kinds": [],
                },
            )
            group["entries"].append(
                {
                    "proposal_id": proposal["proposal_id"],
                    "failure_mechanism": learning["failure_mechanism"],
                    "success_boundary": learning["success_boundary"],
                }
            )
            group["result_kinds"].append(
                case.get("attack_result", "surviving_counterexample")
            )

        ranked = sorted(
            groups.values(),
            key=lambda item: (
                -len(item["entries"]),
                -sum(
                    result == "surviving_counterexample"
                    for result in item["result_kinds"]
                ),
                item["attack_family"],
                min(entry["proposal_id"] for entry in item["entries"]),
            ),
        )
        recommendations: list[dict[str, Any]] = []
        for number, item in enumerate(
            ranked[:MAX_ATTACK_ROUTE_RECOMMENDATIONS],
            1,
        ):
            selected = min(
                item["entries"],
                key=lambda entry: entry["proposal_id"],
            )
            result_kinds = set(item["result_kinds"])
            support_kind = (
                next(iter(result_kinds))
                if len(result_kinds) == 1
                else "mixed"
            )
            recommendations.append(
                {
                    "number": number,
                    "attack_type": item["attack_family"],
                    "what_it_checks": ATTACK_FAMILY_PLAIN_LANGUAGE[
                        item["attack_family"]
                    ],
                    "reported_failure": selected["failure_mechanism"],
                    "applies_when": selected["success_boundary"],
                    "support_kind": support_kind,
                    "support_count": len(item["entries"]),
                    "main_disposition": "synthesize_compress_or_reject",
                }
            )

        semantic = {
            "schema_version": ADVERSE_ROUTING_SCHEMA_VERSION,
            "contract_revision": ATTACK_ROUTE_RECOMMENDATION_REPORT_REVISION,
            "project_id": self.store.project_id(),
            "host_task_scope_id": scope_id,
            "coverage_status": "case-projection",
            "scope_complete": False,
            "recommendation_policy": {
                "maximum": MAX_ATTACK_ROUTE_RECOMMENDATIONS,
                "selection": (
                    "pending_worker_failure_reports_family_deduplicated_for_main_review"
                ),
                "quality_bias": "omit_instead_of_broaden",
            },
            "recommendations": recommendations,
            "pending_proposal_count": len(pending_proposal_ids),
            "omitted_pending_count": (
                len(pending_proposal_ids) - len(recommendations)
            ),
            "main_synthesis_required": bool(recommendations),
            "main_instruction": (
                "Main must compare concrete reports, then synthesize, semantically "
                "compress, or reject; worker wording is never activated directly."
                if recommendations
                else "No Main route synthesis is warranted from this scope."
            ),
            "routing_change_policy": (
                "no_route_change_without_main_synthesis"
            ),
            "evidence_boundary": (
                "items are concrete nontruth worker failure reports, not route rules; "
                "only a separately bounded Main synthesis changes future task cards"
            ),
            "truth_effect": ADVERSE_ROUTING_TRUTH_EFFECT,
            "project_effect": "report_only",
        }
        report = {**semantic, "report_sha256": sha256_json(semantic)}
        return validate_attack_route_recommendation_report(report)

    def status(self) -> dict[str, Any]:
        if not self.enabled():
            return {
                "enabled": False,
                "contract_revision": ADVERSE_ROUTING_CONTRACT_REVISION,
                "activation": "unsupported_before_v5",
                "truth_effect": ADVERSE_ROUTING_TRUTH_EFFECT,
                "project_effect": "none",
            }
        state = self._validated_state()
        cases = state["cases"]
        proposals = state["proposals"]
        decisions = state["decisions"]
        rules = state["rules"]
        disabled = {item["rule_id"] for item in state["disablements"]}
        active = [item for item in rules if item["rule_id"] not in disabled]
        return {
            "enabled": True,
            "contract_revision": ADVERSE_ROUTING_CONTRACT_REVISION,
            "activation": (
                self._validate_contract(self.store._read_json(self.contract_path))[
                    "activation_kind"
                ]
                if self.contract_path.exists()
                else "prospective_default_user_authorization"
            ),
            "state_materialized": self.contract_path.exists(),
            "reporting_default": True,
            "baseline_rule_count": len(BASELINE_ATTACK_RULES),
            "baseline_rules_sha256": BASELINE_ATTACK_RULES_SHA256,
            "philosophy_additional_rule_count": len(PHILOSOPHY_ATTACK_RULES),
            "philosophy_rules_sha256": PHILOSOPHY_ATTACK_RULES_SHA256,
            "philosophy_activation": (
                "explicit_research_or_validated_paper_domain_profile_only"
            ),
            "case_count": len(cases),
            "proposal_count": len(proposals),
            "pending_proposal_count": len(proposals) - len(decisions),
            "decision_count": len(decisions),
            "rule_count": len(rules),
            "active_rule_count": len(active),
            "active_rule_hard_cap": MAX_ACTIVE_ROUTE_RULES,
            "active_rule_ids": [item["rule_id"] for item in active],
            "activation_policy": "main_synthesis_only",
            "effect": ADVERSE_ROUTING_PROJECT_EFFECT,
            "truth_effect": ADVERSE_ROUTING_TRUTH_EFFECT,
        }

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any

from .contracts import SHA256_RE, sha256_json


ADVERSE_ROUTING_SCHEMA_VERSION = 1
ADVERSE_TASK_CARD_SCHEMA_VERSION = 2
ADVERSE_ROUTING_CONTRACT_REVISION = "chalxius-adverse-routing-evolution-1"
ADVERSE_ROUTING_TRUTH_EFFECT = "none"
ADVERSE_ROUTING_PROJECT_EFFECT = "future_exploration_routing_only"
MAX_TEXT_BYTES = 8 * 1024
MAX_LIST_ITEMS = 32
MAX_SELECTED_RULES = 24
_SLUG_RE = re.compile(r"[a-z][a-z0-9_]{1,63}")


BASELINE_ATTACK_RULES: tuple[dict[str, Any], ...] = (
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
BASELINE_ATTACK_RULES_SHA256 = sha256_json(list(BASELINE_ATTACK_RULES))

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


def validate_attack_learning(value: Any) -> dict[str, Any]:
    required = {
        "attack_family",
        "target_pattern",
        "failure_mechanism",
        "premise_witnesses",
        "conclusion_failure_witness",
        "reproduction_steps",
        "success_boundary",
        "route_rule",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("attack_learning fields are not exact")
    attack_family = _require_slug(value["attack_family"], "attack family")
    route_rule = validate_route_rule(value["route_rule"])
    if route_rule["attack_family"] != attack_family:
        raise ValueError("attack_learning family and route rule family disagree")
    return {
        "attack_family": attack_family,
        "target_pattern": _require_text(value["target_pattern"], "attack target pattern"),
        "failure_mechanism": _require_text(
            value["failure_mechanism"], "attack failure mechanism"
        ),
        "premise_witnesses": _require_text_list(
            value["premise_witnesses"], "attack premise witnesses", nonempty=True
        ),
        "conclusion_failure_witness": _require_text(
            value["conclusion_failure_witness"],
            "attack conclusion-failure witness",
        ),
        "reproduction_steps": _require_text_list(
            value["reproduction_steps"], "attack reproduction steps", nonempty=True
        ),
        "success_boundary": _require_text(
            value["success_boundary"], "attack success boundary"
        ),
        "route_rule": route_rule,
    }


class AdverseRoutingManager:
    """Project-local, nontruth learning and user-governed adverse routing."""

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
        if (
            payload["schema_version"] != ADVERSE_ROUTING_SCHEMA_VERSION
            or payload["contract_revision"] != ADVERSE_ROUTING_CONTRACT_REVISION
            or payload["project_id"] != self.store.project_id()
            or payload["activation_kind"] != "explicit_operator_opt_in"
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
            return True
        if self.root.exists() and any(self.root.iterdir()):
            raise ValueError("adverse-routing state exists without its activation contract")
        return False

    def initialize(self, *, actor: str, reason: str) -> dict[str, Any]:
        actor = _require_text(actor, "adverse-routing actor")
        reason = _require_text(reason, "adverse-routing reason")
        if self.store.workflow_evidence_version() != 5:
            raise ValueError(
                "adverse-routing evolution is V5-only and cannot be enabled on an "
                "earlier workflow project"
            )
        with self.store.v5_mutation_lock(command="attack-route-enable"):
            if self.enabled():
                return self.status()
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
                "activation_kind": "explicit_operator_opt_in",
                "actor": actor,
                "reason": reason,
                "truth_effect": ADVERSE_ROUTING_TRUTH_EFFECT,
                "project_effect": ADVERSE_ROUTING_PROJECT_EFFECT,
                "activated_at": _utc_now(),
            }
            contract = {**without_hash, "record_sha256": sha256_json(without_hash)}
            self.store._write_json_once(self.contract_path, contract)
        return self.status()

    def require_enabled(self) -> None:
        if not self.enabled():
            raise ValueError(
                "adverse routing is not enabled for this project; an operator must run "
                "attack-route-enable explicitly"
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
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError(f"adverse-routing record directory is missing or unsafe: {directory}")
        for path in sorted(directory.iterdir()):
            if path.is_symlink() or not path.is_file() or path.suffix != ".json":
                raise ValueError(f"unsafe adverse-routing entry: {path}")
            records.append((path, self.store._read_json(path)))
        return records

    def _validate_case(self, payload: Any, path: Path) -> dict[str, Any]:
        fields = {
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
        record = self._validate_content_record(
            payload,
            path=path,
            id_field="case_id",
            prefix="attack-case-",
            semantic_fields=fields,
            label="attack case",
        )
        self._validate_common_identity(record, "attack case")
        for name in (
            "round_id",
            "assignment_id",
            "host_task_scope_id",
            "target_research_id",
            "counterexample_research_id",
            "target_claim",
        ):
            _require_text(record[name], f"attack case {name}")
        for name in ("task_card_sha256", "return_sha256"):
            if not isinstance(record[name], str) or SHA256_RE.fullmatch(record[name]) is None:
                raise ValueError(f"attack case {name} is invalid")
        validate_attack_learning(record["attack_learning"])
        if record["evidence_status"] != "worker_reported_counterexample_nontruth":
            raise ValueError("attack case evidence status is invalid")
        return record

    def _validate_proposal(self, payload: Any, path: Path) -> dict[str, Any]:
        fields = {
            "schema_version",
            "contract_revision",
            "project_id",
            "case_id",
            "route_rule",
            "proposal_status",
            "activation_policy",
            "truth_effect",
        }
        record = self._validate_content_record(
            payload,
            path=path,
            id_field="proposal_id",
            prefix="route-proposal-",
            semantic_fields=fields,
            label="route proposal",
        )
        self._validate_common_identity(record, "route proposal")
        _validate_id(record["case_id"], "attack-case-", "route proposal case id")
        validate_route_rule(record["route_rule"])
        if (
            record["proposal_status"] != "pending_user_decision"
            or record["activation_policy"] != "user_decision_only"
        ):
            raise ValueError("route proposal policy is invalid")
        return record

    def _validate_decision(self, payload: Any, path: Path) -> dict[str, Any]:
        fields = {
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
        record = self._validate_content_record(
            payload,
            path=path,
            id_field="decision_id",
            prefix="route-decision-",
            semantic_fields=fields,
            label="route decision",
        )
        self._validate_common_identity(record, "route decision")
        _validate_id(record["proposal_id"], "route-proposal-", "route decision proposal id")
        if record["action"] not in {"approve", "approve_modified", "reject"}:
            raise ValueError("route decision action is invalid")
        _require_text(record["reason"], "route decision reason")
        _require_text(record["actor"], "route decision actor")
        if record["action"] == "reject":
            if record["approved_rule"] is not None:
                raise ValueError("rejected route decision cannot carry a rule")
        else:
            validate_route_rule(record["approved_rule"], label="approved route rule")
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
        _require_text(record["reason"], "route disablement reason")
        _require_text(record["actor"], "route disablement actor")
        if record["effect"] != "future_task_cards_only":
            raise ValueError("route disablement effect is invalid")
        return record

    def _validate_common_identity(self, record: dict[str, Any], label: str) -> None:
        if (
            record["schema_version"] != ADVERSE_ROUTING_SCHEMA_VERSION
            or record["contract_revision"] != ADVERSE_ROUTING_CONTRACT_REVISION
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
        related_artifacts = related_artifacts or []
        program_math_scope = self._program_math_scope(
            entry=entry,
            related_artifacts=related_artifacts,
        )
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
        if program_math_scope["active"]:
            baseline.append(dict(PROGRAM_MATH_ATTACK_RULE))
        return {
            "schema_version": ADVERSE_TASK_CARD_SCHEMA_VERSION,
            "contract_revision": ADVERSE_ROUTING_CONTRACT_REVISION,
            "enabled": True,
            "selection_policy": "baseline_plus_user_approved_future_only",
            "baseline_rules": baseline,
            "baseline_rules_sha256": sha256_json(baseline),
            "approved_rules": selected,
            "approved_rules_sha256": sha256_json(selected),
            "scope_evidence": program_math_scope,
            "learning_contract": {
                "counterexample_requires_attack_learning": True,
                "proposal_activation": "user_decision_only",
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
        if value.get("schema_version") == ADVERSE_ROUTING_SCHEMA_VERSION:
            if set(value) != legacy_required:
                raise ValueError("legacy adverse-routing task-card fields are not exact")
            expected_baseline = list(BASELINE_ATTACK_RULES) if work_mode == "refute" else []
            if (
                value["contract_revision"] != ADVERSE_ROUTING_CONTRACT_REVISION
                or value["enabled"] is not True
                or value["selection_policy"] != "baseline_plus_user_approved_future_only"
                or value["baseline_rules"] != expected_baseline
                or value["baseline_rules_sha256"] != sha256_json(expected_baseline)
            ):
                raise ValueError("legacy adverse-routing task-card baseline binding is invalid")
        else:
            required = {*legacy_required, "scope_evidence"}
            if set(value) != required:
                raise ValueError("adverse-routing task-card fields are not exact")
            if value.get("schema_version") != ADVERSE_TASK_CARD_SCHEMA_VERSION:
                raise ValueError("adverse-routing task-card schema version is unsupported")
            if work_mode != "refute":
                raise ValueError("current adverse-routing binding is refute-only")
            scope = value["scope_evidence"]
            if not isinstance(scope, dict) or set(scope) != {
                "active",
                "activation",
                "source_research_id",
                "source_task_card_sha256",
                "artifact_bindings",
            }:
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
            expected_baseline = list(BASELINE_ATTACK_RULES)
            if scope["active"]:
                expected_baseline.append(dict(PROGRAM_MATH_ATTACK_RULE))
            if (
                value["contract_revision"] != ADVERSE_ROUTING_CONTRACT_REVISION
                or value["enabled"] is not True
                or value["selection_policy"] != "baseline_plus_user_approved_future_only"
                or value["baseline_rules"] != expected_baseline
                or value["baseline_rules_sha256"] != sha256_json(expected_baseline)
            ):
                raise ValueError("adverse-routing task-card baseline binding is invalid")
        approved = value["approved_rules"]
        if not isinstance(approved, list) or len(approved) > MAX_SELECTED_RULES:
            raise ValueError("adverse-routing approved rules are invalid")
        if value["approved_rules_sha256"] != sha256_json(approved):
            raise ValueError("adverse-routing approved-rule hash mismatch")
        stored = {record["rule_id"]: self._rule_projection(record) for record in self.rules()}
        if any(not isinstance(item, dict) or stored.get(item.get("rule_id")) != item for item in approved):
            raise ValueError("adverse-routing task card names an unapproved or drifted rule")
        expected_learning = {
            "counterexample_requires_attack_learning": True,
            "proposal_activation": "user_decision_only",
            "attack_report": "required_at_host_task_completion",
            "truth_effect": ADVERSE_ROUTING_TRUTH_EFFECT,
        }
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
        if payload.get("outcome") != "counterexample":
            raise ValueError("only counterexample returns can create attack cases")
        learning = validate_attack_learning(payload.get("attack_learning"))
        scope_id = card["control_plane"].get("host_task_scope_id")
        if not isinstance(scope_id, str) or not scope_id.strip():
            scope_id = f"round:{card['round_id']}"
        case_semantic = {
            "schema_version": ADVERSE_ROUTING_SCHEMA_VERSION,
            "contract_revision": ADVERSE_ROUTING_CONTRACT_REVISION,
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
            "contract_revision": ADVERSE_ROUTING_CONTRACT_REVISION,
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
        if not isinstance(payload, dict) or set(payload) != {"action", "reason", "rule"}:
            raise ValueError("route decision input fields are not exact")
        action = payload["action"]
        if action not in {"approve", "approve_modified", "reject"}:
            raise ValueError("route decision action is invalid")
        reason = _require_text(payload["reason"], "route decision reason")
        proposal = self._proposal(proposal_id)
        if action == "approve":
            if payload["rule"] is not None:
                raise ValueError("approve copies the proposal and requires rule=null")
            approved_rule = proposal["route_rule"]
        elif action == "approve_modified":
            approved_rule = validate_route_rule(payload["rule"], label="modified route rule")
        else:
            if payload["rule"] is not None:
                raise ValueError("reject requires rule=null")
            approved_rule = None
        with self.store.v5_mutation_lock(command="attack-route-decide"):
            prior = [item for item in self.decisions() if item["proposal_id"] == proposal_id]
            expected = {
                "action": action,
                "reason": reason,
                "actor": actor,
                "approved_rule": approved_rule,
            }
            if prior:
                if len(prior) != 1 or any(
                    prior[0][key] != value for key, value in expected.items()
                ):
                    raise ValueError("route proposal already has a different immutable decision")
                decision = prior[0]
            else:
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
        reason = _require_text(reason, "route disablement reason")
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
        scope_id = _require_text(host_task_scope_id, "attack report host task scope id")
        state = self._validated_state()
        decisions = {item["proposal_id"]: item for item in state["decisions"]}
        rules_by_decision = {
            item["source_decision_id"]: item for item in state["rules"]
        }
        disabled = {item["rule_id"] for item in state["disablements"]}
        proposals_by_case = {item["case_id"]: item for item in state["proposals"]}
        items: list[dict[str, Any]] = []
        for case in state["cases"]:
            if case["host_task_scope_id"] != scope_id:
                continue
            proposal = proposals_by_case[case["case_id"]]
            decision = decisions.get(proposal["proposal_id"])
            rule = rules_by_decision.get(decision["decision_id"]) if decision else None
            if decision is None:
                proposal_status = "pending_user_decision"
            else:
                proposal_status = decision["action"]
            items.append(
                {
                    "case_id": case["case_id"],
                    "proposal_id": proposal["proposal_id"],
                    "evidence_status": case["evidence_status"],
                    "attack_family": case["attack_learning"]["attack_family"],
                    "target_claim": case["target_claim"],
                    "failure_mechanism": case["attack_learning"]["failure_mechanism"],
                    "premise_witnesses": case["attack_learning"]["premise_witnesses"],
                    "conclusion_failure_witness": case["attack_learning"][
                        "conclusion_failure_witness"
                    ],
                    "reproduction_steps": case["attack_learning"]["reproduction_steps"],
                    "success_boundary": case["attack_learning"]["success_boundary"],
                    "proposed_rule": proposal["route_rule"],
                    "proposal_status": proposal_status,
                    "decision_id": decision["decision_id"] if decision else None,
                    "active_rule_id": (
                        rule["rule_id"]
                        if rule is not None and rule["rule_id"] not in disabled
                        else None
                    ),
                }
            )
        items.sort(key=lambda item: item["case_id"])
        pending = sum(item["proposal_status"] == "pending_user_decision" for item in items)
        approved = sum(
            item["proposal_status"] in {"approve", "approve_modified"} for item in items
        )
        rejected = sum(item["proposal_status"] == "reject" for item in items)
        return {
            "schema_version": ADVERSE_ROUTING_SCHEMA_VERSION,
            "contract_revision": ADVERSE_ROUTING_CONTRACT_REVISION,
            "project_id": self.store.project_id(),
            "host_task_scope_id": scope_id,
            "generated_at": _utc_now(),
            "summary": {
                "worker_reported_success_count": len(items),
                "pending_user_decision_count": pending,
                "approved_count": approved,
                "rejected_count": rejected,
            },
            "attacks": items,
            "user_decision_required": pending > 0,
            "allowed_user_actions": ["approve", "approve_modified", "reject"],
            "routing_change_policy": "no_route_change_without_operator_decision",
            "evidence_boundary": (
                "worker-reported counterexamples are nontruth Research; attack-report and "
                "routing approval do not certify the refutation or create a Fact"
            ),
            "truth_effect": ADVERSE_ROUTING_TRUTH_EFFECT,
            "project_effect": "report_only",
        }

    def status(self) -> dict[str, Any]:
        if not self.enabled():
            return {
                "enabled": False,
                "contract_revision": ADVERSE_ROUTING_CONTRACT_REVISION,
                "activation": "explicit_operator_opt_in_required",
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
            "baseline_rule_count": len(BASELINE_ATTACK_RULES),
            "baseline_rules_sha256": BASELINE_ATTACK_RULES_SHA256,
            "case_count": len(cases),
            "proposal_count": len(proposals),
            "pending_proposal_count": len(proposals) - len(decisions),
            "decision_count": len(decisions),
            "rule_count": len(rules),
            "active_rule_count": len(active),
            "active_rule_ids": [item["rule_id"] for item in active],
            "activation_policy": "user_decision_only",
            "effect": ADVERSE_ROUTING_PROJECT_EFFECT,
            "truth_effect": ADVERSE_ROUTING_TRUTH_EFFECT,
        }

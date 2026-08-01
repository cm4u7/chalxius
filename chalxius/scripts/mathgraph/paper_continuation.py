from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import (
    SHA256_RE,
    contained_path,
    sha256_bytes,
    sha256_json,
    validate_memory_id,
)
from .paper_logic_contracts import PAPER_NODE_ID_RE, PAPER_SNAPSHOT_ID_RE
from .v5_assurance import V5_ASSURANCE_CONTRACT_REVISION


PAPER_CONTINUATION_CONTRACT_REVISION = "chalxius-v5-paper-continuation-1"
PHILOSOPHY_ATOMICITY_CONTRACT_REVISION = (
    "chalxius-v5-philosophy-semantic-atomicity-1"
)

_PLAN_ID_RE = re.compile(r"pcp-[0-9a-f]{64}")
_DISPOSITION_ID_RE = re.compile(r"pcd-[0-9a-f]{64}")
_LOCAL_ID_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.:-]{0,127}")
_SELECTION_MODES = {"all_targets", "explicit_targets"}
_OUTCOMES = {"retained", "rejected", "replaced", "out_of_scope"}
_WRITING_STATUSES = {"covered", "not_applicable"}
_WORKER_OUTCOMES = {
    "proof",
    "counterexample",
    "evidence",
    "dead_end",
    "insight",
    "challenge",
}
_REQUIRED_ANALYSIS_FIELDS = [
    "issue",
    "importance",
    "burden_holder",
    "plain_language_summary",
    "technical_term_ledger",
    "strongest_charitable_objection",
    "response_or_revision",
    "independent_failure_surfaces",
    "writing_coverage",
]


def _text(value: Any, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    result = value.strip()
    if not allow_empty and not result:
        raise ValueError(f"{label} must be nonempty")
    return result


def _strings(value: Any, label: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        qualifier = "a nonempty list" if nonempty else "a list"
        raise ValueError(f"{label} must be {qualifier} of nonempty strings")
    result = [item.strip() for item in value]
    if nonempty and not result:
        raise ValueError(f"{label} must be nonempty")
    if len(result) != len(set(result)):
        raise ValueError(f"{label} must not contain duplicates")
    return result


def _exact(payload: Any, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != fields:
        raise ValueError(f"{label} fields are not exact")
    return payload


def validate_plan_id(value: str) -> str:
    if not isinstance(value, str) or _PLAN_ID_RE.fullmatch(value) is None:
        raise ValueError("invalid Paper continuation plan id")
    return value


def validate_disposition_id(value: str) -> str:
    if not isinstance(value, str) or _DISPOSITION_ID_RE.fullmatch(value) is None:
        raise ValueError("invalid Paper continuation disposition id")
    return value


class PaperContinuationManager:
    """Prospective Paper-led Research adequacy, separate from Fact authority."""

    def __init__(self, lifecycle: Any) -> None:
        self.lifecycle = lifecycle
        self.store = lifecycle.store
        self.root = lifecycle.root / "paper-continuations"
        self.plans_dir = self.root / "plans" / "by-id"
        self.materializations_dir = self.root / "materializations" / "by-plan"
        self.dispositions_dir = self.root / "dispositions" / "by-id"
        self.writing_artifacts_dir = (
            self.root / "writing-artifacts" / "by-sha256"
        )

    def initialize(self) -> None:
        for path in (
            self.plans_dir,
            self.materializations_dir,
            self.dispositions_dir,
            self.writing_artifacts_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def _plan_path(self, plan_id: str) -> Path:
        return self.plans_dir / f"{validate_plan_id(plan_id)}.json"

    def _materialization_path(self, plan_id: str) -> Path:
        return self.materializations_dir / f"{validate_plan_id(plan_id)}.json"

    def _disposition_path(self, disposition_id: str) -> Path:
        return self.dispositions_dir / (
            f"{validate_disposition_id(disposition_id)}.json"
        )

    @staticmethod
    def _snapshot_binding(paper: Any, snapshot_id: str) -> dict[str, str]:
        directory = paper.snapshots_dir / snapshot_id
        result: dict[str, str] = {}
        for name, role in (
            ("manifest.json", "paper_snapshot_manifest"),
            ("nodes.jsonl", "paper_snapshot_nodes"),
            ("edges.jsonl", "paper_snapshot_edges"),
        ):
            path = directory / name
            if path.is_symlink() or not path.is_file():
                raise ValueError("Paper continuation snapshot bytes are missing or unsafe")
            result[role] = sha256_bytes(path.read_bytes())
        return result

    @staticmethod
    def _target_closure(
        *,
        target_id: str,
        nodes: dict[str, dict[str, Any]],
        edges: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        target = nodes.get(target_id)
        if target is None or target.get("object_type") != "paper_target":
            raise ValueError(f"Paper continuation target is not a paper_target: {target_id}")
        reconstruction: set[str] = {target_id}
        upstream_relations = {"targets", "concludes", "premise_of", "defeats"}
        changed = True
        while changed:
            changed = False
            for edge in edges.values():
                relation = edge["relation_type"]
                source_id = edge["source_id"]
                target_node_id = edge["target_id"]
                candidate: str | None = None
                if relation == "targets" and source_id in reconstruction:
                    candidate = target_node_id
                elif relation == "concludes" and target_node_id in reconstruction:
                    candidate = source_id
                elif relation in {"premise_of", "defeats"} and target_node_id in reconstruction:
                    candidate = source_id
                elif relation == "uses_definition" and source_id in reconstruction:
                    candidate = target_node_id
                elif relation == "variant_of" and (
                    source_id in reconstruction or target_node_id in reconstruction
                ):
                    candidate = (
                        target_node_id
                        if source_id in reconstruction
                        else source_id
                    )
                if (
                    candidate is not None
                    and candidate not in reconstruction
                    and nodes.get(candidate, {}).get("plane")
                    == "paper_reconstruction"
                ):
                    reconstruction.add(candidate)
                    changed = True
        target_edges = [
            edge
            for edge in edges.values()
            if edge["relation_type"] == "targets"
            and edge["source_id"] == target_id
        ]
        if len(target_edges) != 1:
            raise ValueError(
                "each Paper continuation target must have exactly one targets edge"
            )
        target_claim_id = target_edges[0]["target_id"]
        source_nodes: set[str] = {
            edge["target_id"]
            for edge in edges.values()
            if edge["relation_type"] == "anchors"
            and edge["source_id"] in reconstruction
        }
        source_artifact_nodes = {
            edge["source_id"]
            for edge in edges.values()
            if edge["relation_type"] == "contains"
            and edge["target_id"] in source_nodes
        }
        source_nodes.update(source_artifact_nodes)
        selected_nodes = reconstruction | source_nodes
        selected_edges = sorted(
            edge_id
            for edge_id, edge in edges.items()
            if edge["source_id"] in selected_nodes
            and edge["target_id"] in selected_nodes
            and edge["relation_type"]
            in {
                *upstream_relations,
                "uses_definition",
                "variant_of",
                "anchors",
                "contains",
            }
        )
        claim = nodes[target_claim_id]
        statement = claim.get("payload", {}).get("statement")
        if not isinstance(statement, str) or not statement.strip():
            raise ValueError("Paper continuation target claim lacks a statement")
        semantic = {
            "target_node_id": target_id,
            "target_claim_node_id": target_claim_id,
            "target_role": target["payload"]["target_role"],
            "target_rationale": target["payload"]["rationale"],
            "target_statement": statement.strip(),
            "target_discourse_role": claim["payload"].get("discourse_role", ""),
            "reconstruction_node_ids": sorted(reconstruction),
            "source_node_ids": sorted(source_nodes),
            "edge_ids": selected_edges,
        }
        return {**semantic, "work_unit_sha256": sha256_json(semantic)}

    def _validate_plan_record(self, record: Any, *, path: Path) -> dict[str, Any]:
        fields = {
            "schema_version",
            "contract_revision",
            "project_id",
            "paper_id",
            "snapshot_id",
            "snapshot_sha256",
            "snapshot_file_sha256",
            "source_artifact_sha256",
            "source_artifact_relpath",
            "domain_profile",
            "selection_mode",
            "target_node_ids",
            "work_units",
            "selected_reconstruction_node_ids",
            "selected_source_node_ids",
            "selected_edge_ids",
            "objective",
            "created_by",
            "truth_effect",
            "plan_id",
            "created_at",
            "record_sha256",
        }
        _exact(record, fields, "Paper continuation plan")
        plan_id = validate_plan_id(record["plan_id"])
        if path.stem != plan_id:
            raise ValueError("Paper continuation plan path/id mismatch")
        if (
            record["schema_version"] != 1
            or record["contract_revision"]
            != PAPER_CONTINUATION_CONTRACT_REVISION
            or record["project_id"] != self.store.project_id()
            or record["truth_effect"] != "none"
        ):
            raise ValueError("Paper continuation plan schema/project mismatch")
        semantic = {
            key: value
            for key, value in record.items()
            if key not in {"plan_id", "created_at", "record_sha256"}
        }
        if plan_id != "pcp-" + sha256_json(semantic):
            raise ValueError("Paper continuation plan content id mismatch")
        without_hash = {
            key: value for key, value in record.items() if key != "record_sha256"
        }
        if record["record_sha256"] != sha256_json(without_hash):
            raise ValueError("Paper continuation plan record hash mismatch")
        snapshot_id = record["snapshot_id"]
        if PAPER_SNAPSHOT_ID_RE.fullmatch(snapshot_id) is None:
            raise ValueError("Paper continuation snapshot id is invalid")
        paper = self.store.paper_logic()
        manifest = paper.snapshot_manifest(snapshot_id)
        manifest_path = paper.snapshots_dir / snapshot_id / "manifest.json"
        if (
            record["snapshot_sha256"] != sha256_bytes(manifest_path.read_bytes())
            or manifest["paper_id"] != record["paper_id"]
            or manifest["domain_profile"] != record["domain_profile"]
            or manifest["graph_kind"] != "logic"
        ):
            raise ValueError("Paper continuation snapshot binding drifted")
        if self._snapshot_binding(paper, snapshot_id) != record["snapshot_file_sha256"]:
            raise ValueError("Paper continuation snapshot file binding drifted")
        source_path = contained_path(
            self.store.root,
            record["source_artifact_relpath"],
            "Paper continuation source artifact",
        )
        if (
            source_path.is_symlink()
            or not source_path.is_file()
            or sha256_bytes(source_path.read_bytes())
            != record["source_artifact_sha256"]
        ):
            raise ValueError("Paper continuation source artifact drifted")
        nodes, edges = paper.snapshot_objects(snapshot_id)
        targets = _strings(
            record["target_node_ids"], "Paper continuation target ids", nonempty=True
        )
        if any(PAPER_NODE_ID_RE.fullmatch(item) is None for item in targets):
            raise ValueError("Paper continuation target id is invalid")
        work_units = record["work_units"]
        if not isinstance(work_units, list) or len(work_units) != len(targets):
            raise ValueError("Paper continuation work-unit inventory is invalid")
        expected_units = [
            self._target_closure(target_id=item, nodes=nodes, edges=edges)
            for item in targets
        ]
        if work_units != expected_units:
            raise ValueError("Paper continuation target closure drifted")
        expected_reconstruction = sorted(
            {
                item
                for unit in expected_units
                for item in unit["reconstruction_node_ids"]
            }
        )
        expected_source = sorted(
            {item for unit in expected_units for item in unit["source_node_ids"]}
        )
        expected_edges = sorted(
            {item for unit in expected_units for item in unit["edge_ids"]}
        )
        if (
            record["selected_reconstruction_node_ids"] != expected_reconstruction
            or record["selected_source_node_ids"] != expected_source
            or record["selected_edge_ids"] != expected_edges
        ):
            raise ValueError("Paper continuation aggregate closure drifted")
        return record

    def plan(self, plan_id: str) -> dict[str, Any]:
        path = self._plan_path(plan_id)
        if path.is_symlink() or not path.is_file():
            raise KeyError(f"unknown Paper continuation plan: {plan_id}")
        return self._validate_plan_record(self.store._read_json(path), path=path)

    def plans(self) -> list[dict[str, Any]]:
        if not self.plans_dir.exists():
            return []
        return [
            self.plan(path.stem)
            for path in sorted(self.plans_dir.glob("pcp-*.json"))
        ]

    def _research_payload(
        self,
        *,
        plan: dict[str, Any],
        unit: dict[str, Any],
    ) -> dict[str, Any]:
        snapshot_id = plan["snapshot_id"]
        snapshot_dir = self.store.paper_logic().snapshots_dir / snapshot_id
        source_path = contained_path(
            self.store.root,
            plan["source_artifact_relpath"],
            "Paper continuation source artifact",
        )
        artifacts = [
            {
                "path": (
                    snapshot_dir / filename
                ).relative_to(self.store.root).as_posix(),
                "sha256": plan["snapshot_file_sha256"][role],
                "role": role,
            }
            for filename, role in (
                ("manifest.json", "paper_snapshot_manifest"),
                ("nodes.jsonl", "paper_snapshot_nodes"),
                ("edges.jsonl", "paper_snapshot_edges"),
            )
        ]
        artifacts.append(
            {
                "path": source_path.relative_to(self.store.root).as_posix(),
                "sha256": plan["source_artifact_sha256"],
                "role": "paper_source_artifact",
            }
        )
        role = unit["target_role"]
        discourse_role = unit["target_discourse_role"]
        impact = 0.98 if role == "headline" else 0.8
        kind = "challenge" if discourse_role == "objection" else "direction"
        paper_binding = {
            "contract_revision": PAPER_CONTINUATION_CONTRACT_REVISION,
            "plan_id": plan["plan_id"],
            "plan_record_sha256": plan["record_sha256"],
            "snapshot_id": snapshot_id,
            "snapshot_sha256": plan["snapshot_sha256"],
            "paper_id": plan["paper_id"],
            "domain_profile": plan["domain_profile"],
            "source_artifact_sha256": plan["source_artifact_sha256"],
            "target_node_id": unit["target_node_id"],
            "target_claim_node_id": unit["target_claim_node_id"],
            "target_role": role,
            "work_unit_sha256": unit["work_unit_sha256"],
            "closure_reconstruction_node_ids": unit[
                "reconstruction_node_ids"
            ],
            "closure_source_node_ids": unit["source_node_ids"],
            "closure_edge_ids": unit["edge_ids"],
            "required_analysis_fields": list(_REQUIRED_ANALYSIS_FIELDS),
        }
        obligations = [
            {
                "obligation_id": "obl-paper-origin-closure",
                "description": (
                    "Use every exact target, claim, inference, defeater, definition, "
                    "source anchor, and edge in the frozen target closure; do not replace "
                    "the closure with a thematic summary."
                ),
                "required_artifact_roles": ["paper_target_analysis"],
                "evidence_types": ["bounded_argument", "exact_graph_coverage"],
                "not_applicable_allowed": False,
            },
            {
                "obligation_id": "obl-dialectical-salience",
                "description": (
                    "State the dispute, why it matters, and who bears which burden; "
                    "do not leave philosophical salience implicit."
                ),
                "required_artifact_roles": ["paper_target_analysis"],
                "evidence_types": ["dialectical_analysis"],
                "not_applicable_allowed": False,
            },
            {
                "obligation_id": "obl-charity-and-failure-surfaces",
                "description": (
                    "Give the strongest charitable objection or reconstruction, the "
                    "reply or revision, and independently challengeable failure surfaces."
                ),
                "required_artifact_roles": ["paper_target_analysis"],
                "evidence_types": ["adverse_analysis", "failure_surface_inventory"],
                "not_applicable_allowed": False,
            },
            {
                "obligation_id": "obl-plain-language-clarity",
                "description": (
                    "Restate the target in clear ordinary language and inventory each "
                    "necessary technical term with a plain definition and a reason it "
                    "cannot be replaced; terminology must not conceal an inferential step."
                ),
                "required_artifact_roles": ["paper_target_analysis"],
                "evidence_types": ["plain_language_paraphrase", "term_ledger"],
                "not_applicable_allowed": False,
            },
            {
                "obligation_id": "obl-terminal-disposition",
                "description": (
                    "Return enough exact evidence for Main to record retained, rejected, "
                    "replaced, or out-of-scope disposition and revised-writing coverage."
                ),
                "required_artifact_roles": ["paper_target_analysis"],
                "evidence_types": ["disposition_evidence", "writing_mapping"],
                "not_applicable_allowed": False,
            },
        ]
        return {
            "kind": kind,
            "status": "open",
            "claim": f"Paper target {unit['target_node_id']}: {unit['target_statement']}",
            "content": (
                "Continue the frozen Paper graph target without thematic compression. "
                "Produce one exact paper_target_analysis artifact covering dialectical "
                "salience, charity, failure surfaces, disposition evidence, and the "
                "revised-writing location."
            ),
            "rationale": unit["target_rationale"],
            "source": f"paper_snapshot:{snapshot_id}",
            "source_dependent": True,
            "artifacts": artifacts,
            "required_related_artifact_roles": [
                "paper_snapshot_manifest",
                "paper_snapshot_nodes",
                "paper_snapshot_edges",
                "paper_source_artifact",
            ],
            "decision_profile": {
                "impact": impact,
                "information_value": 0.95,
                "tractability": 0.75,
                "burden": 0.35,
            },
            "logic_signals": [
                "paper_target_closure",
                "philosophy_dialectical_atomicity",
            ],
            "obligations": obligations,
            "stop_conditions": [
                "Do not claim the whole Paper continuation complete from this target alone.",
                "Do not promote Paper or Research claims directly to Fact authority.",
                "Return blocked rather than silently dropping an unresolved failure surface.",
            ],
            "paper_continuation": paper_binding,
            "truth_effect": "none",
        }

    def _validate_materialization(
        self,
        record: Any,
        *,
        plan: dict[str, Any],
        path: Path,
    ) -> dict[str, Any]:
        fields = {
            "schema_version",
            "contract_revision",
            "project_id",
            "plan_id",
            "plan_record_sha256",
            "target_research_bindings",
            "effect",
            "truth_effect",
            "created_at",
            "record_sha256",
        }
        _exact(record, fields, "Paper continuation materialization")
        if (
            path.stem != plan["plan_id"]
            or record["schema_version"] != 1
            or record["contract_revision"]
            != PAPER_CONTINUATION_CONTRACT_REVISION
            or record["project_id"] != self.store.project_id()
            or record["plan_id"] != plan["plan_id"]
            or record["plan_record_sha256"] != plan["record_sha256"]
            or record["truth_effect"] != "none"
        ):
            raise ValueError("Paper continuation materialization binding mismatch")
        bindings = record["target_research_bindings"]
        if not isinstance(bindings, list):
            raise ValueError("Paper continuation Research bindings must be a list")
        expected_targets = plan["target_node_ids"]
        if [item.get("target_node_id") for item in bindings] != expected_targets:
            raise ValueError("Paper continuation Research target order drifted")
        for item in bindings:
            _exact(
                item,
                {"target_node_id", "research_id", "research_record_sha256"},
                "Paper continuation Research binding",
            )
            research = self.lifecycle._research_record(
                validate_memory_id(item["research_id"])
            )
            if research["record_sha256"] != item["research_record_sha256"]:
                raise ValueError("Paper continuation Research binding drifted")
            binding = research["metadata"].get("paper_continuation")
            if (
                not isinstance(binding, dict)
                or binding.get("plan_id") != plan["plan_id"]
                or binding.get("target_node_id") != item["target_node_id"]
            ):
                raise ValueError("Paper continuation Research provenance drifted")
        without_hash = {
            key: value for key, value in record.items() if key != "record_sha256"
        }
        if record["record_sha256"] != sha256_json(without_hash):
            raise ValueError("Paper continuation materialization hash mismatch")
        return record

    def materialization(self, plan_id: str) -> dict[str, Any] | None:
        plan = self.plan(plan_id)
        path = self._materialization_path(plan_id)
        if not path.exists():
            return None
        if path.is_symlink() or not path.is_file():
            raise ValueError("Paper continuation materialization path is unsafe")
        return self._validate_materialization(
            self.store._read_json(path), plan=plan, path=path
        )

    def create_plan(
        self,
        snapshot_id: str,
        payload: dict[str, Any],
        *,
        actor: str,
    ) -> dict[str, Any]:
        _exact(
            payload,
            {
                "selection_mode",
                "target_node_ids",
                "objective",
                "source_artifact_sha256",
            },
            "Paper continuation plan input",
        )
        actor = _text(actor, "Paper continuation actor")
        if PAPER_SNAPSHOT_ID_RE.fullmatch(snapshot_id) is None:
            raise ValueError("Paper continuation snapshot id is invalid")
        paper = self.store.paper_logic()
        current = set(paper.status()["current_snapshot_ids"])
        if snapshot_id not in current:
            raise ValueError(
                "Paper continuation must start from a current, nonsuperseded snapshot"
            )
        manifest = paper.snapshot_manifest(snapshot_id)
        if manifest["graph_kind"] != "logic":
            raise ValueError("Paper continuation requires a frozen Logic snapshot")
        nodes, edges = paper.snapshot_objects(snapshot_id)
        available_targets = sorted(
            object_id
            for object_id, node in nodes.items()
            if node["object_type"] == "paper_target"
        )
        if not available_targets:
            raise ValueError("Paper continuation snapshot has zero paper targets")
        selection_mode = payload["selection_mode"]
        if selection_mode not in _SELECTION_MODES:
            raise ValueError("Paper continuation selection_mode is invalid")
        requested = _strings(
            payload["target_node_ids"], "Paper continuation requested targets"
        )
        if selection_mode == "all_targets":
            if requested:
                raise ValueError("all_targets requires target_node_ids=[]")
            selected_targets = available_targets
        else:
            if not requested:
                raise ValueError("explicit_targets requires at least one target")
            missing = sorted(set(requested).difference(available_targets))
            if missing:
                raise ValueError(
                    "Paper continuation requested unknown targets: "
                    + ", ".join(missing)
                )
            selected_targets = sorted(requested)
        objective = _text(payload["objective"], "Paper continuation objective")
        source_artifacts = manifest["source_artifacts"]
        requested_source = _text(
            payload["source_artifact_sha256"],
            "Paper continuation source artifact SHA-256",
            allow_empty=True,
        )
        by_sha = {
            item["artifact_sha256"]: item["artifact_relpath"]
            for item in source_artifacts
        }
        if requested_source:
            if requested_source not in by_sha:
                raise ValueError(
                    "Paper continuation source artifact is absent from the snapshot"
                )
            source_sha = requested_source
        elif len(by_sha) == 1:
            source_sha = next(iter(by_sha))
        else:
            raise ValueError(
                "Paper continuation snapshot has multiple source artifacts; select one"
            )
        if SHA256_RE.fullmatch(source_sha) is None:
            raise ValueError("Paper continuation source artifact hash is invalid")
        work_units = [
            self._target_closure(target_id=item, nodes=nodes, edges=edges)
            for item in selected_targets
        ]
        semantic = {
            "schema_version": 1,
            "contract_revision": PAPER_CONTINUATION_CONTRACT_REVISION,
            "project_id": self.store.project_id(),
            "paper_id": manifest["paper_id"],
            "snapshot_id": snapshot_id,
            "snapshot_sha256": sha256_bytes(
                (paper.snapshots_dir / snapshot_id / "manifest.json").read_bytes()
            ),
            "snapshot_file_sha256": self._snapshot_binding(paper, snapshot_id),
            "source_artifact_sha256": source_sha,
            "source_artifact_relpath": by_sha[source_sha],
            "domain_profile": manifest["domain_profile"],
            "selection_mode": selection_mode,
            "target_node_ids": selected_targets,
            "work_units": work_units,
            "selected_reconstruction_node_ids": sorted(
                {
                    item
                    for unit in work_units
                    for item in unit["reconstruction_node_ids"]
                }
            ),
            "selected_source_node_ids": sorted(
                {item for unit in work_units for item in unit["source_node_ids"]}
            ),
            "selected_edge_ids": sorted(
                {item for unit in work_units for item in unit["edge_ids"]}
            ),
            "objective": objective,
            "created_by": actor,
            "truth_effect": "none",
        }
        plan_id = "pcp-" + sha256_json(semantic)
        created_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        without_hash = {
            **semantic,
            "plan_id": plan_id,
            "created_at": created_at,
        }
        record = {**without_hash, "record_sha256": sha256_json(without_hash)}
        with self.store.v5_mutation_lock(command="paper-continuation-plan"):
            self.initialize()
            path = self._plan_path(plan_id)
            if path.exists():
                record = self.plan(plan_id)
            else:
                self.store._write_json_once(path, record)
            bindings: list[dict[str, str]] = []
            for unit in record["work_units"]:
                research = self.lifecycle.add_research(
                    self._research_payload(plan=record, unit=unit),
                    actor="v5-paper-continuation-main",
                    assurance_contract_revision=V5_ASSURANCE_CONTRACT_REVISION,
                )
                bindings.append(
                    {
                        "target_node_id": unit["target_node_id"],
                        "research_id": research["research_id"],
                        "research_record_sha256": research["record_sha256"],
                    }
                )
            materialization_path = self._materialization_path(plan_id)
            materialization = {
                "schema_version": 1,
                "contract_revision": PAPER_CONTINUATION_CONTRACT_REVISION,
                "project_id": self.store.project_id(),
                "plan_id": plan_id,
                "plan_record_sha256": record["record_sha256"],
                "target_research_bindings": bindings,
                "effect": "complete_low_cost_frontier_without_score_cutoff",
                "truth_effect": "none",
                "created_at": created_at,
            }
            materialization["record_sha256"] = sha256_json(materialization)
            if materialization_path.exists():
                existing = self._validate_materialization(
                    self.store._read_json(materialization_path),
                    plan=record,
                    path=materialization_path,
                )
                comparable = {
                    key: value
                    for key, value in materialization.items()
                    if key not in {"created_at", "record_sha256"}
                }
                existing_comparable = {
                    key: value
                    for key, value in existing.items()
                    if key not in {"created_at", "record_sha256"}
                }
                if comparable != existing_comparable:
                    raise ValueError("Paper continuation materialization collision")
            else:
                self.store._write_json_once(materialization_path, materialization)
        return self.status(plan_id)

    def _validate_research_binding(
        self,
        binding: Any,
        *,
        record: dict[str, Any],
    ) -> dict[str, Any]:
        fields = {
            "contract_revision",
            "plan_id",
            "plan_record_sha256",
            "snapshot_id",
            "snapshot_sha256",
            "paper_id",
            "domain_profile",
            "source_artifact_sha256",
            "target_node_id",
            "target_claim_node_id",
            "target_role",
            "work_unit_sha256",
            "closure_reconstruction_node_ids",
            "closure_source_node_ids",
            "closure_edge_ids",
            "required_analysis_fields",
        }
        _exact(binding, fields, "Paper continuation Research binding")
        plan = self.plan(validate_plan_id(binding["plan_id"]))
        if (
            binding["contract_revision"]
            != PAPER_CONTINUATION_CONTRACT_REVISION
            or binding["plan_record_sha256"] != plan["record_sha256"]
            or binding["snapshot_id"] != plan["snapshot_id"]
            or binding["snapshot_sha256"] != plan["snapshot_sha256"]
            or binding["paper_id"] != plan["paper_id"]
            or binding["domain_profile"] != plan["domain_profile"]
            or binding["source_artifact_sha256"]
            != plan["source_artifact_sha256"]
        ):
            raise ValueError("Paper continuation Research/plan binding drifted")
        units = {
            item["target_node_id"]: item for item in plan["work_units"]
        }
        unit = units.get(binding["target_node_id"])
        if unit is None:
            raise ValueError("Paper continuation Research target is not selected")
        expected = {
            "target_claim_node_id": unit["target_claim_node_id"],
            "target_role": unit["target_role"],
            "work_unit_sha256": unit["work_unit_sha256"],
            "closure_reconstruction_node_ids": unit[
                "reconstruction_node_ids"
            ],
            "closure_source_node_ids": unit["source_node_ids"],
            "closure_edge_ids": unit["edge_ids"],
            "required_analysis_fields": list(_REQUIRED_ANALYSIS_FIELDS),
        }
        if any(binding[key] != value for key, value in expected.items()):
            raise ValueError("Paper continuation Research target closure drifted")
        if record["metadata"].get("assurance_contract_revision") != (
            V5_ASSURANCE_CONTRACT_REVISION
        ):
            raise ValueError("Paper continuation Research lacks current assurance")
        return binding

    def scope_for_research(self, record: dict[str, Any]) -> dict[str, Any] | None:
        binding = record.get("metadata", {}).get("paper_continuation")
        if binding is None:
            return None
        validated = self._validate_research_binding(binding, record=record)
        return {
            **validated,
            "research_id": record["research_id"],
            "research_record_sha256": record["record_sha256"],
            "completion_rule": (
                "worker_return_is_research_only;Main_must_record_one_current_"
                "dialectical_disposition_and_writing_mapping"
            ),
            "truth_effect": "none",
        }

    def plan_ids_for_research(
        self, records: list[dict[str, Any]]
    ) -> list[str]:
        by_id = {
            item["research_id"]: item for item in self.lifecycle.research_records()
        }
        result: set[str] = set()
        pending = [record["research_id"] for record in records]
        seen: set[str] = set()
        while pending:
            research_id = pending.pop()
            if research_id in seen:
                continue
            seen.add(research_id)
            record = by_id.get(research_id)
            if record is None:
                raise ValueError(
                    "Paper continuation release Research ancestry is incomplete"
                )
            binding = record.get("metadata", {}).get("paper_continuation")
            if binding is not None:
                validated = self._validate_research_binding(binding, record=record)
                result.add(validated["plan_id"])
            pending.extend(record.get("related_research_ids", []))
        return sorted(result)

    @staticmethod
    def _descends_from(
        research_id: str,
        ancestor_id: str,
        by_id: dict[str, dict[str, Any]],
    ) -> bool:
        pending = [research_id]
        seen: set[str] = set()
        while pending:
            current = pending.pop()
            if current == ancestor_id:
                return True
            if current in seen:
                continue
            seen.add(current)
            record = by_id.get(current)
            if record is not None:
                pending.extend(record.get("related_research_ids", []))
        return False

    def _validate_managed_result(self, result: dict[str, Any]) -> None:
        if result["metadata"].get("worker_outcome") not in _WORKER_OUTCOMES:
            raise ValueError("Paper disposition requires an ingested managed worker result")
        provenance = result["metadata"].get("assignment_provenance")
        if not isinstance(provenance, dict):
            raise ValueError("Paper disposition result lacks assignment provenance")
        self.lifecycle._research_is_adverse_assignment(result)
        round_dir, manifest = self.lifecycle._round_manifest(
            provenance["round_id"]
        )
        assignment = self.lifecycle._assignment(
            manifest, provenance["assignment_id"]
        )
        receipt = self.lifecycle._validated_ingest_receipt(
            round_dir=round_dir,
            assignment=assignment,
        )
        if receipt["research_id"] != result["research_id"]:
            raise ValueError("Paper disposition result/ingestion receipt mismatch")

    def _validate_dialectical_analysis(
        self,
        value: Any,
        *,
        domain_profile: str,
    ) -> dict[str, Any]:
        fields = {
            "issue",
            "importance",
            "burden_holder",
            "plain_language_summary",
            "technical_term_ledger",
            "strongest_charitable_objection",
            "response_or_revision",
            "independent_failure_surfaces",
        }
        _exact(value, fields, "Paper continuation dialectical analysis")
        text_fields = fields.difference(
            {"independent_failure_surfaces", "technical_term_ledger"}
        )
        normalized = {
            key: _text(value[key], f"dialectical analysis {key}")
            for key in text_fields
        }
        normalized["technical_term_ledger"] = self._validate_term_ledger(
            value["technical_term_ledger"],
            label="Paper continuation technical-term ledger",
        )
        surfaces = value["independent_failure_surfaces"]
        if not isinstance(surfaces, list):
            raise ValueError("independent_failure_surfaces must be a list")
        if domain_profile in {"philosophy", "mixed"} and not surfaces:
            raise ValueError(
                "philosophy Paper disposition requires an independent failure surface"
            )
        normalized_surfaces: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in surfaces:
            _exact(
                item,
                {"surface_id", "statement", "why_independent", "resolution"},
                "Paper continuation failure surface",
            )
            surface_id = _text(item["surface_id"], "failure surface id")
            if _LOCAL_ID_RE.fullmatch(surface_id) is None or surface_id in seen:
                raise ValueError("failure surface id is invalid or duplicated")
            seen.add(surface_id)
            normalized_surfaces.append(
                {
                    "surface_id": surface_id,
                    "statement": _text(item["statement"], "failure surface statement"),
                    "why_independent": _text(
                        item["why_independent"], "failure surface independence"
                    ),
                    "resolution": _text(
                        item["resolution"], "failure surface resolution"
                    ),
                }
            )
        normalized["independent_failure_surfaces"] = sorted(
            normalized_surfaces, key=lambda item: item["surface_id"]
        )
        return normalized

    @staticmethod
    def _validate_term_ledger(value: Any, *, label: str) -> list[dict[str, str]]:
        if not isinstance(value, list) or any(
            not isinstance(item, dict) for item in value
        ):
            raise ValueError(f"{label} must be a list of objects")
        normalized: list[dict[str, str]] = []
        seen: set[str] = set()
        for index, item in enumerate(value, 1):
            _exact(
                item,
                {"term", "plain_definition", "necessity"},
                f"{label}[{index}]",
            )
            term = _text(item["term"], f"{label}[{index}] term")
            key = term.casefold()
            if key in seen:
                raise ValueError(f"{label} contains a duplicate term")
            seen.add(key)
            normalized.append(
                {
                    "term": term,
                    "plain_definition": _text(
                        item["plain_definition"],
                        f"{label}[{index}] plain definition",
                    ),
                    "necessity": _text(
                        item["necessity"], f"{label}[{index}] necessity"
                    ),
                }
            )
        return sorted(normalized, key=lambda item: item["term"].casefold())

    def _validate_writing_coverage(
        self,
        value: Any,
        *,
        outcome: str,
    ) -> dict[str, Any]:
        _exact(
            value,
            {
                "status",
                "artifact_path",
                "artifact_sha256",
                "section_ids",
                "rationale",
            },
            "Paper continuation writing coverage",
        )
        status = value["status"]
        if status not in _WRITING_STATUSES:
            raise ValueError("Paper continuation writing status is invalid")
        rationale = _text(value["rationale"], "writing coverage rationale")
        if status == "not_applicable":
            if outcome != "out_of_scope":
                raise ValueError(
                    "only an out_of_scope target may omit revised-writing coverage"
                )
            if (
                value["artifact_path"] is not None
                or value["artifact_sha256"] is not None
                or value["section_ids"] != []
            ):
                raise ValueError("not_applicable writing coverage must be empty")
            return {
                "status": status,
                "artifact_path": None,
                "artifact_sha256": None,
                "section_ids": [],
                "rationale": rationale,
            }
        path_value = _text(value["artifact_path"], "writing artifact path")
        digest = _text(value["artifact_sha256"], "writing artifact SHA-256")
        if SHA256_RE.fullmatch(digest) is None:
            raise ValueError("writing artifact SHA-256 is invalid")
        path = contained_path(
            self.store.root, path_value, "Paper continuation writing artifact"
        )
        if (
            path.is_symlink()
            or not path.is_file()
            or sha256_bytes(path.read_bytes()) != digest
        ):
            raise ValueError("Paper continuation writing artifact drifted")
        sealed_relpath = (
            self.writing_artifacts_dir
            / digest
            / path.name
        ).relative_to(self.store.root).as_posix()
        sections = _strings(
            value["section_ids"], "Paper continuation writing sections", nonempty=True
        )
        return {
            "status": status,
            "artifact_path": sealed_relpath,
            "artifact_sha256": digest,
            "section_ids": sorted(sections),
            "rationale": rationale,
        }

    def _validate_disposition_record(
        self,
        record: Any,
        *,
        path: Path,
        validate_managed_evidence: bool = True,
    ) -> dict[str, Any]:
        fields = {
            "schema_version",
            "contract_revision",
            "project_id",
            "plan_id",
            "target_node_id",
            "target_research_id",
            "result_research_id",
            "result_research_record_sha256",
            "outcome",
            "rationale",
            "successor_research_ids",
            "dialectical_analysis",
            "writing_coverage",
            "supersedes_disposition_id",
            "actor",
            "truth_effect",
            "disposition_id",
            "created_at",
            "record_sha256",
        }
        _exact(record, fields, "Paper continuation disposition")
        disposition_id = validate_disposition_id(record["disposition_id"])
        if path.stem != disposition_id:
            raise ValueError("Paper continuation disposition path/id mismatch")
        plan = self.plan(validate_plan_id(record["plan_id"]))
        if (
            record["schema_version"] != 1
            or record["contract_revision"]
            != PAPER_CONTINUATION_CONTRACT_REVISION
            or record["project_id"] != self.store.project_id()
            or record["truth_effect"] != "none"
            or record["target_node_id"] not in plan["target_node_ids"]
        ):
            raise ValueError("Paper continuation disposition schema/binding mismatch")
        semantic = {
            key: value
            for key, value in record.items()
            if key not in {"disposition_id", "created_at", "record_sha256"}
        }
        if disposition_id != "pcd-" + sha256_json(semantic):
            raise ValueError("Paper continuation disposition content id mismatch")
        without_hash = {
            key: value for key, value in record.items() if key != "record_sha256"
        }
        if record["record_sha256"] != sha256_json(without_hash):
            raise ValueError("Paper continuation disposition record hash mismatch")
        result = self.lifecycle._research_record(
            validate_memory_id(record["result_research_id"])
        )
        if result["record_sha256"] != record["result_research_record_sha256"]:
            raise ValueError("Paper continuation disposition result Research drifted")
        materialization = self.materialization(plan["plan_id"])
        if materialization is None:
            raise ValueError(
                "Paper continuation disposition lacks materialized frontier"
            )
        target_bindings = {
            item["target_node_id"]: item
            for item in materialization["target_research_bindings"]
        }
        target_binding = target_bindings[record["target_node_id"]]
        if record["target_research_id"] != target_binding["research_id"]:
            raise ValueError("Paper continuation disposition target Research drifted")
        by_id = {
            item["research_id"]: item
            for item in self.lifecycle.research_records()
        }
        if not self._descends_from(
            result["research_id"], target_binding["research_id"], by_id
        ):
            raise ValueError(
                "Paper disposition result does not descend from its target"
            )
        if validate_managed_evidence:
            self._validate_managed_result(result)
        if record["outcome"] not in _OUTCOMES:
            raise ValueError("Paper continuation disposition outcome is invalid")
        successors = _strings(
            record["successor_research_ids"], "Paper successor Research ids"
        )
        for research_id in successors:
            self.lifecycle._research_record(validate_memory_id(research_id))
        if record["outcome"] == "replaced" and not successors:
            raise ValueError("a replaced Paper target requires successor Research")
        if record["outcome"] != "replaced" and successors:
            raise ValueError("only a replaced Paper target may name successor Research")
        expected_dialectical = self._validate_dialectical_analysis(
            record["dialectical_analysis"],
            domain_profile=plan["domain_profile"],
        )
        expected_writing = self._validate_writing_coverage(
            record["writing_coverage"], outcome=record["outcome"]
        )
        if (
            record["dialectical_analysis"] != expected_dialectical
            or record["writing_coverage"] != expected_writing
        ):
            raise ValueError("Paper continuation disposition normalization drifted")
        supersedes = record["supersedes_disposition_id"]
        if not isinstance(supersedes, str):
            raise ValueError("supersedes_disposition_id must be a string")
        if supersedes:
            validate_disposition_id(supersedes)
        return record

    def dispositions(self, plan_id: str = "") -> list[dict[str, Any]]:
        if not self.dispositions_dir.exists():
            return []
        result = [
            self._validate_disposition_record(
                self.store._read_json(path), path=path
            )
            for path in sorted(self.dispositions_dir.glob("pcd-*.json"))
        ]
        if plan_id:
            validate_plan_id(plan_id)
            result = [item for item in result if item["plan_id"] == plan_id]
        return result

    def _current_dispositions(self, plan_id: str) -> dict[str, dict[str, Any]]:
        records = self.dispositions(plan_id)
        by_id = {item["disposition_id"]: item for item in records}
        superseded: set[str] = set()
        for item in records:
            previous = item["supersedes_disposition_id"]
            if not previous:
                continue
            prior = by_id.get(previous)
            if prior is None:
                raise ValueError("Paper disposition supersedes an unknown record")
            if (
                prior["plan_id"] != item["plan_id"]
                or prior["target_node_id"] != item["target_node_id"]
            ):
                raise ValueError("Paper disposition supersession crosses targets")
            if previous in superseded:
                raise ValueError("Paper disposition has multiple direct successors")
            superseded.add(previous)
        current_records = [
            item for item in records if item["disposition_id"] not in superseded
        ]
        result: dict[str, dict[str, Any]] = {}
        for item in current_records:
            target_id = item["target_node_id"]
            if target_id in result:
                raise ValueError("Paper target has multiple current dispositions")
            result[target_id] = item
        return result

    def record_disposition(
        self,
        plan_id: str,
        payload: dict[str, Any],
        *,
        actor: str,
    ) -> dict[str, Any]:
        plan = self.plan(plan_id)
        _exact(
            payload,
            {
                "target_node_id",
                "result_research_id",
                "outcome",
                "rationale",
                "successor_research_ids",
                "dialectical_analysis",
                "writing_coverage",
                "supersedes_disposition_id",
            },
            "Paper continuation disposition input",
        )
        actor = _text(actor, "Paper continuation disposition actor")
        target_id = _text(payload["target_node_id"], "Paper target id")
        if target_id not in plan["target_node_ids"]:
            raise ValueError("Paper disposition target is not selected by the plan")
        materialization = self.materialization(plan_id)
        if materialization is None:
            raise ValueError("Paper continuation frontier is not fully materialized")
        target_research = {
            item["target_node_id"]: item["research_id"]
            for item in materialization["target_research_bindings"]
        }[target_id]
        result = self.lifecycle._research_record(
            validate_memory_id(
                _text(payload["result_research_id"], "Paper result Research id")
            )
        )
        self._validate_managed_result(result)
        outcome = payload["outcome"]
        if outcome not in _OUTCOMES:
            raise ValueError("Paper continuation disposition outcome is invalid")
        rationale = _text(payload["rationale"], "Paper disposition rationale")
        successors = _strings(
            payload["successor_research_ids"], "Paper successor Research ids"
        )
        for research_id in successors:
            self.lifecycle._research_record(validate_memory_id(research_id))
        if outcome == "replaced" and not successors:
            raise ValueError("a replaced Paper target requires successor Research")
        if outcome != "replaced" and successors:
            raise ValueError("only a replaced Paper target may name successor Research")
        dialectical = self._validate_dialectical_analysis(
            payload["dialectical_analysis"],
            domain_profile=plan["domain_profile"],
        )
        writing = self._validate_writing_coverage(
            payload["writing_coverage"], outcome=outcome
        )
        current = self._current_dispositions(plan_id)
        expected_previous = (
            current[target_id]["disposition_id"] if target_id in current else ""
        )
        supplied_previous = payload["supersedes_disposition_id"]
        if supplied_previous != expected_previous:
            raise ValueError(
                "Paper disposition correction must supersede the exact current record"
            )
        semantic = {
            "schema_version": 1,
            "contract_revision": PAPER_CONTINUATION_CONTRACT_REVISION,
            "project_id": self.store.project_id(),
            "plan_id": plan_id,
            "target_node_id": target_id,
            "target_research_id": target_research,
            "result_research_id": result["research_id"],
            "result_research_record_sha256": result["record_sha256"],
            "outcome": outcome,
            "rationale": rationale,
            "successor_research_ids": sorted(successors),
            "dialectical_analysis": dialectical,
            "writing_coverage": writing,
            "supersedes_disposition_id": supplied_previous,
            "actor": actor,
            "truth_effect": "none",
        }
        disposition_id = "pcd-" + sha256_json(semantic)
        created_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        without_hash = {
            **semantic,
            "disposition_id": disposition_id,
            "created_at": created_at,
        }
        record = {**without_hash, "record_sha256": sha256_json(without_hash)}
        with self.store.v5_mutation_lock(command="paper-continuation-dispose"):
            self.initialize()
            locked_current = self._current_dispositions(plan_id)
            locked_expected_previous = (
                locked_current[target_id]["disposition_id"]
                if target_id in locked_current
                else ""
            )
            if supplied_previous != locked_expected_previous:
                raise ValueError(
                    "Paper disposition correction lost a concurrent update; retry "
                    "against the exact current record"
                )
            if writing["status"] == "covered":
                source_path = contained_path(
                    self.store.root,
                    payload["writing_coverage"]["artifact_path"],
                    "Paper continuation writing artifact",
                )
                raw = source_path.read_bytes()
                if sha256_bytes(raw) != writing["artifact_sha256"]:
                    raise ValueError(
                        "Paper continuation writing artifact changed before sealing"
                    )
                self.store._write_bytes_once(
                    self.store.root / writing["artifact_path"], raw
                )
            path = self._disposition_path(disposition_id)
            if path.exists():
                existing = self._validate_disposition_record(
                    self.store._read_json(path), path=path
                )
                return existing
            self.store._write_json_once(path, record)
        return record

    def status(self, plan_id: str) -> dict[str, Any]:
        plan = self.plan(plan_id)
        materialization = self.materialization(plan_id)
        target_bindings = (
            materialization["target_research_bindings"]
            if materialization is not None
            else []
        )
        by_id = {
            item["research_id"]: item for item in self.lifecycle.research_records()
        }
        researched: set[str] = set()
        for binding in target_bindings:
            if any(
                record["metadata"].get("worker_outcome") in _WORKER_OUTCOMES
                and self._descends_from(
                    record["research_id"], binding["research_id"], by_id
                )
                for record in by_id.values()
            ):
                researched.add(binding["target_node_id"])
        current = self._current_dispositions(plan_id)
        dispositioned = set(current)
        successor_mapped = {
            target_id
            for target_id, item in current.items()
            if item["outcome"] != "replaced"
            or bool(item["successor_research_ids"])
        }
        writing_covered = {
            target_id
            for target_id, item in current.items()
            if item["writing_coverage"]["status"] in _WRITING_STATUSES
        }
        current_snapshots = set(
            self.store.paper_logic().status()["current_snapshot_ids"]
        )
        snapshot_current = plan["snapshot_id"] in current_snapshots
        total = len(plan["target_node_ids"])
        unresolved = sorted(set(plan["target_node_ids"]).difference(dispositioned))
        complete = bool(
            materialization is not None
            and snapshot_current
            and len(target_bindings) == total
            and not unresolved
            and len(successor_mapped) == total
            and len(writing_covered) == total
        )
        receipt_semantic = {
            "contract_revision": PAPER_CONTINUATION_CONTRACT_REVISION,
            "plan_id": plan_id,
            "plan_record_sha256": plan["record_sha256"],
            "materialization_record_sha256": (
                materialization["record_sha256"]
                if materialization is not None
                else None
            ),
            "current_dispositions": [
                {
                    "target_node_id": target_id,
                    "disposition_id": item["disposition_id"],
                    "record_sha256": item["record_sha256"],
                }
                for target_id, item in sorted(current.items())
            ],
            "counts": {
                "total": total,
                "frontier_materialized": len(target_bindings),
                "researched": len(researched),
                "dispositioned": len(dispositioned),
                "unresolved": len(unresolved),
                "successor_mapped": len(successor_mapped),
                "revised_manuscript_covered": len(writing_covered),
            },
            "source_snapshot_current": snapshot_current,
            "adequacy_complete": complete,
        }
        return {
            "schema_version": 1,
            "contract_revision": PAPER_CONTINUATION_CONTRACT_REVISION,
            "plan_id": plan_id,
            "paper_id": plan["paper_id"],
            "snapshot_id": plan["snapshot_id"],
            "domain_profile": plan["domain_profile"],
            "selection_mode": plan["selection_mode"],
            "state": (
                "complete"
                if complete
                else (
                    "research_and_disposition_pending"
                    if materialization is not None
                    else "frontier_materialization_incomplete"
                )
            ),
            "source_snapshot_current": snapshot_current,
            "adequacy_complete": complete,
            "counts": receipt_semantic["counts"],
            "unresolved_target_node_ids": unresolved,
            "target_research_bindings": target_bindings,
            "current_disposition_ids": sorted(
                item["disposition_id"] for item in current.values()
            ),
            "selected_reconstruction_node_ids": plan[
                "selected_reconstruction_node_ids"
            ],
            "selected_source_node_ids": plan["selected_source_node_ids"],
            "selected_edge_ids": plan["selected_edge_ids"],
            "adequacy_receipt_sha256": sha256_json(receipt_semantic),
            "truth_effect": "none",
        }

    def status_all(self) -> dict[str, Any]:
        statuses = [self.status(plan["plan_id"]) for plan in self.plans()]
        counts = {
            "plans": len(statuses),
            "complete_plans": sum(item["adequacy_complete"] for item in statuses),
            "targets": sum(item["counts"]["total"] for item in statuses),
            "frontier_materialized": sum(
                item["counts"]["frontier_materialized"] for item in statuses
            ),
            "researched": sum(item["counts"]["researched"] for item in statuses),
            "dispositioned": sum(
                item["counts"]["dispositioned"] for item in statuses
            ),
            "unresolved": sum(item["counts"]["unresolved"] for item in statuses),
            "successor_mapped": sum(
                item["counts"]["successor_mapped"] for item in statuses
            ),
            "revised_manuscript_covered": sum(
                item["counts"]["revised_manuscript_covered"] for item in statuses
            ),
        }
        return {
            "contract_revision": PAPER_CONTINUATION_CONTRACT_REVISION,
            "declaration_state": "declared" if statuses else "not_declared",
            "adequacy_complete": (
                all(item["adequacy_complete"] for item in statuses)
                if statuses
                else None
            ),
            "counts": counts,
            "plans": statuses,
            "truth_effect": "none",
        }

    def _validate_atomicity(
        self,
        value: Any,
        *,
        plan: dict[str, Any],
        facts: dict[str, Any],
        current_dispositions: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        _exact(
            value,
            {
                "contract_revision",
                "plan_id",
                "fact_units",
                "conjunct_inventory",
                "clarity_review",
            },
            "philosophy atomicity contract",
        )
        if (
            value["contract_revision"]
            != PHILOSOPHY_ATOMICITY_CONTRACT_REVISION
            or value["plan_id"] != plan["plan_id"]
        ):
            raise ValueError("philosophy atomicity contract binding mismatch")
        units = value["fact_units"]
        if not isinstance(units, list):
            raise ValueError("philosophy atomicity fact_units must be a list")
        normalized: list[dict[str, Any]] = []
        seen_facts: set[str] = set()
        fact_targets: dict[str, list[str]] = {}
        for item in units:
            _exact(
                item,
                {
                    "fact_id",
                    "primary_conclusion",
                    "plain_language_paraphrase",
                    "source_target_node_ids",
                    "conjunct_ids",
                    "defeasible_condition_ids",
                    "decomposition_rationale",
                },
                "philosophy atomicity fact unit",
            )
            fact_id = _text(item["fact_id"], "atomicity Fact id")
            if fact_id not in facts or fact_id in seen_facts:
                raise ValueError("atomicity Fact id is unknown or duplicated")
            seen_facts.add(fact_id)
            primary = _text(item["primary_conclusion"], "primary conclusion")
            if primary != facts[fact_id].statement.strip():
                raise ValueError(
                    "atomicity primary conclusion must equal the exact Candidate Fact statement"
                )
            paraphrase = _text(
                item["plain_language_paraphrase"],
                "philosophy Fact plain-language paraphrase",
            )
            if re.search(r"\[(?:CLAIM|HYP|USE|COMP|TERM|EXT):", paraphrase):
                raise ValueError(
                    "plain-language paraphrase must not expose machine protocol anchors"
                )
            target_ids = _strings(
                item["source_target_node_ids"],
                "atomicity source targets",
                nonempty=True,
            )
            if not set(target_ids).issubset(plan["target_node_ids"]):
                raise ValueError("atomicity source target is outside the selected plan")
            conjunct_ids = _strings(
                item["conjunct_ids"], "atomicity conjunct ids", nonempty=True
            )
            if len(conjunct_ids) != 1:
                raise ValueError(
                    "one philosophy Fact must expose exactly one independently "
                    "falsifiable conjunct; split additional conjuncts into a Fact mini-DAG"
                )
            fact_targets[fact_id] = sorted(target_ids)
            conditions = _strings(
                item["defeasible_condition_ids"], "atomicity defeasible conditions"
            )
            normalized.append(
                {
                    "fact_id": fact_id,
                    "primary_conclusion": primary,
                    "plain_language_paraphrase": paraphrase,
                    "source_target_node_ids": sorted(target_ids),
                    "conjunct_ids": conjunct_ids,
                    "defeasible_condition_ids": sorted(conditions),
                    "decomposition_rationale": _text(
                        item["decomposition_rationale"],
                        "atomicity decomposition rationale",
                    ),
                }
            )
        if seen_facts != set(facts):
            raise ValueError(
                "philosophy atomicity must cover every Candidate Fact exactly once"
            )
        inventory = value["conjunct_inventory"]
        if not isinstance(inventory, list):
            raise ValueError("philosophy conjunct_inventory must be a list")
        normalized_inventory: list[dict[str, Any]] = []
        seen_conjuncts: set[str] = set()
        represented_facts: set[str] = set()
        for item in inventory:
            _exact(
                item,
                {
                    "conjunct_id",
                    "statement",
                    "represented_by_fact_id",
                    "failure_surface_ids",
                    "independence_rationale",
                },
                "philosophy conjunct inventory item",
            )
            conjunct_id = _text(item["conjunct_id"], "conjunct id")
            if (
                _LOCAL_ID_RE.fullmatch(conjunct_id) is None
                or conjunct_id in seen_conjuncts
            ):
                raise ValueError("atomicity conjunct id is invalid or duplicated")
            seen_conjuncts.add(conjunct_id)
            fact_id = _text(
                item["represented_by_fact_id"], "conjunct represented Fact id"
            )
            if fact_id not in facts or fact_id in represented_facts:
                raise ValueError(
                    "each atomicity conjunct must map to one distinct Candidate Fact"
                )
            represented_facts.add(fact_id)
            statement = _text(item["statement"], "atomicity conjunct statement")
            if statement != facts[fact_id].statement.strip():
                raise ValueError(
                    "atomicity conjunct statement must equal its exact Candidate Fact statement"
                )
            expected_ids = next(
                unit["conjunct_ids"]
                for unit in normalized
                if unit["fact_id"] == fact_id
            )
            if expected_ids != [conjunct_id]:
                raise ValueError("atomicity Fact/conjunct mapping is inconsistent")
            available_surfaces = {
                surface["surface_id"]
                for target_id in fact_targets[fact_id]
                for surface in current_dispositions[target_id][
                    "dialectical_analysis"
                ]["independent_failure_surfaces"]
            }
            surface_ids = _strings(
                item["failure_surface_ids"],
                "atomicity conjunct failure surfaces",
                nonempty=True,
            )
            if not set(surface_ids).issubset(available_surfaces):
                raise ValueError("atomicity cites an unavailable failure surface")
            normalized_inventory.append(
                {
                    "conjunct_id": conjunct_id,
                    "statement": statement,
                    "represented_by_fact_id": fact_id,
                    "failure_surface_ids": sorted(surface_ids),
                    "independence_rationale": _text(
                        item["independence_rationale"],
                        "atomicity conjunct independence rationale",
                    ),
                }
            )
        if represented_facts != set(facts) or seen_conjuncts != {
            conjunct_id
            for unit in normalized
            for conjunct_id in unit["conjunct_ids"]
        }:
            raise ValueError(
                "philosophy conjunct inventory must represent every Candidate Fact "
                "exactly once without hidden declared conjuncts"
            )
        clarity = _exact(
            value["clarity_review"],
            {"plain_language_abstract", "technical_term_ledger"},
            "philosophy clarity review",
        )
        plain_abstract = _text(
            clarity["plain_language_abstract"],
            "philosophy plain-language abstract",
        )
        if re.search(r"\[(?:CLAIM|HYP|USE|COMP|TERM|EXT):", plain_abstract):
            raise ValueError(
                "plain-language abstract must not expose machine protocol anchors"
            )
        term_ledger = self._validate_term_ledger(
            clarity["technical_term_ledger"],
            label="philosophy release technical-term ledger",
        )
        disposition_terms: dict[str, dict[str, str]] = {}
        for disposition in current_dispositions.values():
            for term in disposition["dialectical_analysis"][
                "technical_term_ledger"
            ]:
                key = term["term"].casefold()
                previous = disposition_terms.get(key)
                if previous is not None and previous != term:
                    raise ValueError(
                        "Paper targets give conflicting plain definitions for one term"
                    )
                disposition_terms[key] = term
        if {item["term"].casefold(): item for item in term_ledger} != (
            disposition_terms
        ):
            raise ValueError(
                "philosophy release term ledger must exactly preserve every target-level "
                "technical term and introduce no unreviewed jargon"
            )
        return {
            "contract_revision": PHILOSOPHY_ATOMICITY_CONTRACT_REVISION,
            "plan_id": plan["plan_id"],
            "fact_units": sorted(normalized, key=lambda item: item["fact_id"]),
            "conjunct_inventory": sorted(
                normalized_inventory, key=lambda item: item["conjunct_id"]
            ),
            "clarity_review": {
                "plain_language_abstract": plain_abstract,
                "technical_term_ledger": term_ledger,
            },
        }

    def validate_release_binding(
        self,
        *,
        plan_id: str,
        ref: Any,
        philosophy_atomicity: Any,
        facts: dict[str, Any],
        require_current: bool = True,
    ) -> dict[str, Any]:
        plan = self.plan(plan_id)
        _exact(
            ref,
            {
                "contract_revision",
                "plan_id",
                "plan_record_sha256",
                "adequacy_receipt_sha256",
                "disposition_ids",
            },
            "Paper continuation release ref",
        )
        status: dict[str, Any] | None = None
        if require_current:
            status = self.status(plan_id)
            if not status["adequacy_complete"]:
                raise ValueError(
                    "Paper continuation Candidate Release requires complete target "
                    "dispositions, current source, and revised-writing coverage"
                )
            expected_ref = {
                "contract_revision": PAPER_CONTINUATION_CONTRACT_REVISION,
                "plan_id": plan_id,
                "plan_record_sha256": plan["record_sha256"],
                "adequacy_receipt_sha256": status["adequacy_receipt_sha256"],
                "disposition_ids": status["current_disposition_ids"],
            }
            if ref != expected_ref:
                raise ValueError(
                    "Paper continuation release ref is stale or incomplete"
                )
            selected_dispositions = self._current_dispositions(plan_id)
        else:
            if (
                ref["contract_revision"]
                != PAPER_CONTINUATION_CONTRACT_REVISION
                or ref["plan_id"] != plan_id
                or ref["plan_record_sha256"] != plan["record_sha256"]
                or SHA256_RE.fullmatch(ref["adequacy_receipt_sha256"]) is None
            ):
                raise ValueError("sealed Paper continuation release ref is invalid")
            disposition_ids = _strings(
                ref["disposition_ids"],
                "sealed Paper continuation disposition ids",
                nonempty=True,
            )
            selected_dispositions: dict[str, dict[str, Any]] = {}
            for disposition_id in disposition_ids:
                path = self._disposition_path(disposition_id)
                if path.is_symlink() or not path.is_file():
                    raise ValueError("sealed Paper disposition is missing or unsafe")
                item = self._validate_disposition_record(
                    self.store._read_json(path),
                    path=path,
                    validate_managed_evidence=False,
                )
                if item["plan_id"] != plan_id:
                    raise ValueError("sealed Paper disposition belongs to another plan")
                if item["target_node_id"] in selected_dispositions:
                    raise ValueError("sealed Paper release duplicates a target disposition")
                selected_dispositions[item["target_node_id"]] = item
            if set(selected_dispositions) != set(plan["target_node_ids"]):
                raise ValueError(
                    "sealed Paper release does not cover every selected target"
                )
        normalized_atomicity = None
        if plan["domain_profile"] in {"philosophy", "mixed"}:
            normalized_atomicity = self._validate_atomicity(
                philosophy_atomicity,
                plan=plan,
                facts=facts,
                current_dispositions=selected_dispositions,
            )
        elif philosophy_atomicity is not None:
            normalized_atomicity = self._validate_atomicity(
                philosophy_atomicity,
                plan=plan,
                facts=facts,
                current_dispositions=selected_dispositions,
            )
        return {
            "paper_continuation_ref": ref,
            "philosophy_atomicity": normalized_atomicity,
            "plan": plan,
            "status": status,
        }

    def release_evidence(
        self,
        *,
        plan_id: str,
        disposition_ids: list[str],
        require_current: bool,
    ) -> dict[str, Any]:
        """Materialize exact nontruth evidence for the fresh verifier capsule."""

        plan = self.plan(plan_id)
        requested_ids = _strings(
            disposition_ids,
            "Paper continuation verifier disposition ids",
            nonempty=True,
        )
        if require_current:
            dispositions = self._current_dispositions(plan_id)
            if sorted(
                item["disposition_id"] for item in dispositions.values()
            ) != sorted(requested_ids):
                raise ValueError(
                    "Paper continuation verifier evidence requires current dispositions"
                )
        else:
            dispositions: dict[str, dict[str, Any]] = {}
            for disposition_id in requested_ids:
                path = self._disposition_path(disposition_id)
                if path.is_symlink() or not path.is_file():
                    raise ValueError(
                        "Paper continuation verifier disposition is missing or unsafe"
                    )
                item = self._validate_disposition_record(
                    self.store._read_json(path),
                    path=path,
                    validate_managed_evidence=False,
                )
                if (
                    item["plan_id"] != plan_id
                    or item["target_node_id"] in dispositions
                ):
                    raise ValueError(
                        "Paper continuation verifier dispositions cross or duplicate targets"
                    )
                dispositions[item["target_node_id"]] = item
        if set(dispositions) != set(plan["target_node_ids"]):
            raise ValueError(
                "Paper continuation verifier evidence does not cover every target"
            )
        paper = self.store.paper_logic()
        nodes, edges = paper.snapshot_objects(plan["snapshot_id"])
        selected_node_ids = sorted(
            {
                *plan["selected_reconstruction_node_ids"],
                *plan["selected_source_node_ids"],
            }
        )
        if not set(selected_node_ids).issubset(nodes):
            raise ValueError("Paper continuation verifier nodes are missing")
        if not set(plan["selected_edge_ids"]).issubset(edges):
            raise ValueError("Paper continuation verifier edges are missing")
        materialization = self.materialization(plan_id)
        if materialization is None:
            raise ValueError("Paper continuation verifier evidence lacks its frontier")
        result_research = [
            self.lifecycle._research_record(item["result_research_id"])
            for item in dispositions.values()
        ]
        semantic = {
            "schema_version": 1,
            "contract_revision": PAPER_CONTINUATION_CONTRACT_REVISION,
            "project_id": self.store.project_id(),
            "plan_id": plan_id,
            "plan_record_sha256": plan["record_sha256"],
            "paper_id": plan["paper_id"],
            "snapshot_id": plan["snapshot_id"],
            "snapshot_sha256": plan["snapshot_sha256"],
            "snapshot_file_sha256": plan["snapshot_file_sha256"],
            "source_artifact_sha256": plan["source_artifact_sha256"],
            "domain_profile": plan["domain_profile"],
            "work_units": plan["work_units"],
            "selected_nodes": [nodes[node_id] for node_id in selected_node_ids],
            "selected_edges": [
                edges[edge_id] for edge_id in plan["selected_edge_ids"]
            ],
            "materialization": materialization,
            "dispositions": [
                dispositions[target_id] for target_id in sorted(dispositions)
            ],
            "result_research": sorted(
                result_research, key=lambda item: item["research_id"]
            ),
            "writing_artifact_bindings": [
                {"artifact_sha256": digest, "artifact_path": path}
                for digest, path in sorted(
                    {
                        (
                            item["writing_coverage"]["artifact_sha256"],
                            item["writing_coverage"]["artifact_path"],
                        )
                        for item in dispositions.values()
                        if item["writing_coverage"]["status"] == "covered"
                    }
                )
            ],
            "truth_effect": "none",
        }
        return {
            **semantic,
            "evidence_sha256": sha256_json(semantic),
        }

    def audit(self) -> dict[str, Any]:
        errors: list[str] = []
        summary: dict[str, Any]
        try:
            summary = self.status_all()
        except Exception as exc:
            errors.append(str(exc))
            summary = {
                "declaration_state": "invalid",
                "adequacy_complete": False,
                "counts": {
                    "plans": 0,
                    "complete_plans": 0,
                    "targets": 0,
                    "frontier_materialized": 0,
                    "researched": 0,
                    "dispositioned": 0,
                    "unresolved": 0,
                    "successor_mapped": 0,
                    "revised_manuscript_covered": 0,
                },
                "plans": [],
            }
        return {
            **summary,
            "errors": errors,
            "current_ok": not errors,
            "truth_effect": "none",
        }

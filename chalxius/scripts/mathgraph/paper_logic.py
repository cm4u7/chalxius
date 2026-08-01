from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections import deque
from pathlib import Path
from typing import Any, Iterable

from .contracts import (
    SHA256_RE,
    canonical_json_bytes,
    require_exact_keys,
    require_string,
    sha256_bytes,
    sha256_json,
)
from .paper_logic_contracts import (
    BRIDGE_RELATIONS,
    DOMAIN_PROFILES,
    GRAPH_KINDS,
    PAPER_AUDIT_TYPES,
    PAPER_EDGE_ID_RE,
    PAPER_LOGIC_FEATURE_REVISION,
    PAPER_LOGIC_TRUTH_BOUNDARY,
    PAPER_NODE_ID_RE,
    PAPER_OBJECT_ID_RE,
    PAPER_PLANES,
    PAPER_RECONSTRUCTION_TYPES,
    PAPER_RELATION_TYPES,
    PAPER_REVIEW_ID_RE,
    PAPER_REVISION_ID_RE,
    PAPER_SNAPSHOT_ID_RE,
    REPRESENTATION_KINDS,
    REVIEW_GLOBAL_CHECKS,
    REVIEW_PROFILES_BY_GRAPH_KIND,
    make_paper_edge,
    make_paper_node,
    validate_local_node,
    validate_paper_edge,
    validate_paper_edge_id,
    validate_paper_node,
    validate_paper_node_id,
    validate_paper_object_id,
    validate_paper_revision_id,
    validate_paper_review_id,
    validate_paper_snapshot_id,
    validate_source,
)


_FEATURE_FIELDS = {
    "schema_version",
    "feature_revision",
    "project_id",
    "truth_boundary",
    "initialized_by",
}
_BUNDLE_FIELDS = {
    "schema_version",
    "feature_revision",
    "project_id",
    "paper_id",
    "graph_kind",
    "domain_profile",
    "builder",
    "builder_context_id",
    "source",
    "base_snapshot_id",
    "supersedes_snapshot_id",
    "coverage",
    "nodes",
    "edges",
}
_REVISION_FIELDS = {
    "schema_version",
    "feature_revision",
    "project_id",
    "revision_id",
    "bundle_sha256",
    "paper_id",
    "graph_kind",
    "domain_profile",
    "builder",
    "builder_context_id",
    "source",
    "artifact_relpath",
    "base_snapshot_id",
    "supersedes_snapshot_id",
    "coverage",
    "node_entries",
    "edge_entries",
    "local_id_map",
    "required_review_profiles",
    "truth_effect",
}
_REVIEW_FIELDS = {
    "schema_version",
    "feature_revision",
    "project_id",
    "revision_id",
    "bundle_sha256",
    "profile",
    "verdict",
    "reviewer",
    "reviewer_context_id",
    "fresh_context_contract",
    "object_checks",
    "global_checks",
    "critical_errors",
    "gaps",
    "truth_effect",
    "review_id",
}
_SNAPSHOT_FIELDS = {
    "schema_version",
    "feature_revision",
    "project_id",
    "snapshot_id",
    "paper_id",
    "graph_kind",
    "domain_profile",
    "revision_ids",
    "base_snapshot_id",
    "supersedes_snapshot_id",
    "transaction_id",
    "review_ids",
    "source_artifacts",
    "node_entries",
    "edge_entries",
    "local_id_maps",
    "planes",
    "readiness",
    "current_audit_node_ids",
    "inactive_audit_node_ids",
    "truth_effect",
}

_LOGIC_RELATIONS = {
    "contains",
    "anchors",
    "premise_of",
    "concludes",
    "uses_definition",
    "variant_of",
    "defeats",
    "targets",
}
_AUDIT_RELATIONS = {
    "audits",
    "evidence_for",
    "counterexample_targets",
    "repairs",
    "responds_to",
    "assesses",
    "challenges_audit",
    "disposes",
    "supersedes_audit",
}


class PaperLogicStore:
    """Immutable Paper Logic/Audit Graph evidence, separate from truth and exploration.

    Candidate objects may exist in CAS, but only a reviewed immutable snapshot
    makes them query-visible. Blackboard interoperability uses receipts or an
    explicit mirror projection; neither changes this store's authority.
    """

    def __init__(self, project_root: Path | str, *, owner: Any | None = None) -> None:
        self.project_root = Path(project_root).resolve()
        self.owner = owner
        self.root = self.project_root / "paper_logic"
        self.feature_path = self.root / "store.json"
        self.artifacts_dir = self.root / "artifacts" / "by-sha256"
        self.nodes_dir = self.root / "cas" / "nodes" / "by-hash"
        self.edges_dir = self.root / "cas" / "edges" / "by-hash"
        self.revisions_dir = self.root / "revisions" / "by-id"
        self.reviews_dir = self.root / "reviews" / "by-id"
        self.transactions_dir = self.root / "transactions" / "by-id"
        self.snapshots_dir = self.root / "snapshots" / "by-id"
        self.bridges_dir = self.root / "bridges" / "by-id"
        self.projections_dir = self.root / "projections" / "by-id"

    @staticmethod
    def _write_bytes_once(path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            raise ValueError(f"refusing to write through symlink: {path}")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(path, flags, 0o600)
        except FileExistsError:
            if not path.is_file() or path.is_symlink() or path.read_bytes() != payload:
                raise ValueError(f"immutable paper-logic collision at {path}")
            return
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            raise

    @classmethod
    def _write_json_once(cls, path: Path, payload: Any) -> None:
        cls._write_bytes_once(
            path,
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ).encode("utf-8")
            + b"\n",
        )

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"paper-logic JSON is missing or unsafe: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"paper-logic JSON must be an object: {path}")
        return payload

    @staticmethod
    def _require_strings(
        value: Any,
        label: str,
        *,
        nonempty: bool = False,
    ) -> list[str]:
        if not isinstance(value, list) or any(
            not isinstance(item, str) for item in value
        ):
            raise ValueError(f"{label} must be a list of strings")
        if nonempty and not value:
            raise ValueError(f"{label} must be nonempty")
        if any(not item.strip() for item in value):
            raise ValueError(f"{label} must contain nonempty strings")
        if len(value) != len(set(value)):
            raise ValueError(f"{label} must not contain duplicates")
        return list(value)

    def _project(self) -> dict[str, Any]:
        path = self.project_root / "project.json"
        if path.is_symlink() or not path.is_file():
            raise ValueError("paper-logic project.json is missing or unsafe")
        payload = self._read_json(path)
        if payload.get("workflow_evidence_version") not in {4, 5}:
            raise ValueError(
                "Paper Logic Graph requires a workflow-evidence V4 or V5 project"
            )
        return payload

    def _feature(self) -> dict[str, Any]:
        payload = self._read_json(self.feature_path)
        require_exact_keys(
            payload,
            required=_FEATURE_FIELDS,
            label="paper-logic feature manifest",
        )
        if (
            payload.get("schema_version") != 1
            or payload.get("feature_revision") != PAPER_LOGIC_FEATURE_REVISION
            or payload.get("project_id") != self._project().get("project_id")
            or payload.get("truth_boundary") != PAPER_LOGIC_TRUTH_BOUNDARY
        ):
            raise ValueError("paper-logic feature manifest binding mismatch")
        require_string(payload, "initialized_by")
        return payload

    def initialize(self, *, actor: str) -> dict[str, Any]:
        project = self._project()
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError("paper-logic initializer must be nonempty")
        if self.root.exists() and not self.feature_path.exists():
            entries = list(self.root.iterdir())
            if entries:
                raise ValueError(
                    "nonempty unmanaged paper_logic directory cannot be initialized"
                )
        for directory in (
            self.artifacts_dir,
            self.nodes_dir,
            self.edges_dir,
            self.revisions_dir,
            self.reviews_dir,
            self.transactions_dir,
            self.snapshots_dir,
            self.bridges_dir,
            self.projections_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        manifest = {
            "schema_version": 1,
            "feature_revision": PAPER_LOGIC_FEATURE_REVISION,
            "project_id": project["project_id"],
            "truth_boundary": PAPER_LOGIC_TRUTH_BOUNDARY,
            "initialized_by": actor.strip(),
        }
        self._write_json_once(self.feature_path, manifest)
        return manifest

    def _node_path(self, object_id: str) -> Path:
        validate_paper_node_id(object_id)
        return self.nodes_dir / f"{object_id}.json"

    def _edge_path(self, object_id: str) -> Path:
        validate_paper_edge_id(object_id)
        return self.edges_dir / f"{object_id}.json"

    def _revision_path(self, revision_id: str) -> Path:
        validate_paper_revision_id(revision_id)
        return self.revisions_dir / f"{revision_id}.json"

    def _review_path(self, review_id: str) -> Path:
        validate_paper_review_id(review_id)
        return self.reviews_dir / f"{review_id}.json"

    def _snapshot_path(self, snapshot_id: str) -> Path:
        validate_paper_snapshot_id(snapshot_id)
        return self.snapshots_dir / snapshot_id

    @staticmethod
    def _entry(payload: dict[str, Any]) -> dict[str, str]:
        return {
            "object_id": str(payload["object_id"]),
            "sha256": sha256_json(payload),
        }

    @staticmethod
    def _validate_entry(value: Any, label: str) -> dict[str, str]:
        if not isinstance(value, dict):
            raise ValueError(f"{label} must be an object")
        require_exact_keys(
            value,
            required={"object_id", "sha256"},
            label=label,
        )
        validate_paper_object_id(require_string(value, "object_id"))
        digest = require_string(value, "sha256")
        if SHA256_RE.fullmatch(digest) is None:
            raise ValueError(f"{label} sha256 must be a full lowercase hash")
        return value

    @staticmethod
    def _validate_coverage(
        coverage: Any,
        *,
        graph_kind: str,
        local_nodes: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        if not isinstance(coverage, dict):
            raise ValueError("paper graph coverage must be an object")
        require_exact_keys(
            coverage,
            required={
                "scope_kind",
                "included_locators",
                "excluded_locators",
                "units",
                "unresolved_load_bearing_units",
                "completeness_claim",
            },
            label="paper graph coverage",
        )
        allowed_scope = (
            {"bounded", "full_artifact"}
            if graph_kind == "logic"
            else {"audit_subset"}
        )
        if coverage["scope_kind"] not in allowed_scope:
            raise ValueError("paper graph coverage scope_kind is invalid")
        for key in ("included_locators", "unresolved_load_bearing_units"):
            PaperLogicStore._require_strings(
                coverage[key], f"paper graph coverage {key}"
            )
        excluded = coverage["excluded_locators"]
        if not isinstance(excluded, list) or any(
            not isinstance(item, dict) for item in excluded
        ):
            raise ValueError("paper graph excluded_locators must be objects")
        for item in excluded:
            require_exact_keys(
                item,
                required={"locator", "reason"},
                label="paper graph excluded locator",
            )
            require_string(item, "locator")
            require_string(item, "reason")
        units = coverage["units"]
        if not isinstance(units, list) or any(
            not isinstance(item, dict) for item in units
        ):
            raise ValueError("paper graph coverage units must be objects")
        seen: set[str] = set()
        mapped: set[str] = set()
        for item in units:
            require_exact_keys(
                item,
                required={
                    "unit_id",
                    "classification",
                    "mapped_node_ids",
                    "reason",
                },
                label="paper graph coverage unit",
            )
            unit_id = require_string(item, "unit_id")
            if unit_id in seen:
                raise ValueError(
                    f"paper graph coverage duplicates unit {unit_id}"
                )
            seen.add(unit_id)
            allowed_classifications = (
                {
                    "argumentative",
                    "context",
                    "quotation",
                    "bibliography",
                    "figure",
                    "excluded",
                }
                if graph_kind == "logic"
                else {"audit_target", "audit_evidence", "excluded"}
            )
            if item["classification"] not in allowed_classifications:
                raise ValueError(
                    "paper graph coverage classification is invalid"
                )
            mapped_ids = PaperLogicStore._require_strings(
                item["mapped_node_ids"],
                "paper graph coverage mapped_node_ids",
            )
            mapped.update(mapped_ids)
            reason = require_string(item, "reason", allow_empty=True)
            if item["classification"] in {
                "argumentative",
                "audit_target",
                "audit_evidence",
            } and not mapped_ids:
                raise ValueError(
                    f"paper graph {item['classification']} coverage needs a mapping"
                )
            if item["classification"] == "excluded" and not reason:
                raise ValueError(
                    "excluded paper graph coverage needs a reason"
                )
        if graph_kind == "logic":
            source_units = {
                local_id
                for local_id, node in local_nodes.items()
                if node["object_type"] == "source_unit"
            }
            if seen != source_units:
                missing = sorted(source_units.difference(seen))
                extra = sorted(seen.difference(source_units))
                raise ValueError(
                    "paper graph coverage/source-unit mismatch: "
                    f"missing={missing} extra={extra}"
                )
        unknown_mapped = mapped.difference(local_nodes)
        if unknown_mapped:
            raise ValueError(
                "paper graph coverage maps unknown nodes: "
                + ", ".join(sorted(unknown_mapped))
            )
        require_string(coverage, "completeness_claim")
        return coverage

    @staticmethod
    def _edge_spec(
        relation_type: str,
        source: str,
        target: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "relation_type": relation_type,
            "source": source,
            "target": target,
            "payload": payload,
        }

    @classmethod
    def _expected_logic_edges(
        cls,
        local_nodes: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        expected: list[dict[str, Any]] = []
        for local_id, node in sorted(local_nodes.items()):
            object_type = node["object_type"]
            payload = node["payload"]
            if object_type == "source_unit":
                expected.append(
                    cls._edge_spec(
                        "contains",
                        "__source__",
                        local_id,
                        {"order": payload["order"]},
                    )
                )
            if object_type in {"claim", "definition", "formula", "inference"}:
                for source_unit in payload.get("source_unit_ids", []):
                    expected.append(
                        cls._edge_spec(
                            "anchors", local_id, source_unit, {}
                        )
                    )
            if object_type == "claim":
                for definition_id in payload["definition_ids"]:
                    expected.append(
                        cls._edge_spec(
                            "uses_definition", local_id, definition_id, {}
                        )
                    )
                if payload["parent_claim_id"]:
                    expected.append(
                        cls._edge_spec(
                            "variant_of",
                            local_id,
                            payload["parent_claim_id"],
                            {"semantic_diff": payload["semantic_diff"]},
                        )
                    )
            elif object_type == "inference":
                for position, premise_id in enumerate(payload["premise_ids"]):
                    expected.append(
                        cls._edge_spec(
                            "premise_of",
                            premise_id,
                            local_id,
                            {"position": position},
                        )
                    )
                expected.append(
                    cls._edge_spec(
                        "concludes",
                        local_id,
                        payload["conclusion_id"],
                        {},
                    )
                )
                for defeater_id in payload["defeater_claim_ids"]:
                    expected.append(
                        cls._edge_spec(
                            "defeats",
                            defeater_id,
                            local_id,
                            {},
                        )
                    )
            elif object_type == "paper_target":
                expected.append(
                    cls._edge_spec(
                        "targets",
                        local_id,
                        payload["claim_id"],
                        {"role": payload["target_role"]},
                    )
                )
        return sorted(expected, key=canonical_json_bytes)

    @classmethod
    def _expected_audit_edges(
        cls,
        local_nodes: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        expected: list[dict[str, Any]] = []
        for local_id, node in sorted(local_nodes.items()):
            object_type = node["object_type"]
            payload = node["payload"]
            if object_type == "audit_finding":
                expected.append(
                    cls._edge_spec(
                        "audits",
                        local_id,
                        payload["target_id"],
                        {"finding_kind": payload["finding_kind"]},
                    )
                )
                for evidence_id in payload["evidence_unit_ids"]:
                    expected.append(
                        cls._edge_spec(
                            "evidence_for", evidence_id, local_id, {}
                        )
                    )
            elif object_type == "counterexample":
                expected.append(
                    cls._edge_spec(
                        "counterexample_targets",
                        local_id,
                        payload["target_id"],
                        {},
                    )
                )
            elif object_type == "repair_proposal":
                expected.append(
                    cls._edge_spec(
                        "repairs",
                        local_id,
                        payload["target_id"],
                        {"repair_kind": payload["repair_kind"]},
                    )
                )
                for addressed in payload["addresses_ids"]:
                    expected.append(
                        cls._edge_spec(
                            "responds_to", local_id, addressed, {}
                        )
                    )
            elif object_type == "impact_assessment":
                expected.append(
                    cls._edge_spec(
                        "assesses",
                        local_id,
                        payload["challenge_id"],
                        {},
                    )
                )
                if payload["repair_id"]:
                    expected.append(
                        cls._edge_spec(
                            "assesses",
                            local_id,
                            payload["repair_id"],
                            {},
                        )
                    )
            elif object_type == "audit_challenge":
                expected.append(
                    cls._edge_spec(
                        "challenges_audit",
                        local_id,
                        payload["target_audit_id"],
                        {},
                    )
                )
            elif object_type == "audit_disposition":
                expected.append(
                    cls._edge_spec(
                        "disposes",
                        local_id,
                        payload["target_audit_id"],
                        {"disposition": payload["disposition"]},
                    )
                )
                for challenge_id in payload["challenge_ids"]:
                    expected.append(
                        cls._edge_spec(
                            "responds_to", local_id, challenge_id, {}
                        )
                    )
                for replacement_id in payload["replacement_ids"]:
                    expected.append(
                        cls._edge_spec(
                            "supersedes_audit",
                            replacement_id,
                            payload["target_audit_id"],
                            {},
                        )
                    )
        return sorted(expected, key=canonical_json_bytes)

    @staticmethod
    def _validate_input_edges(
        edges: Any,
        expected: list[dict[str, Any]],
        *,
        graph_kind: str,
    ) -> list[dict[str, Any]]:
        if not isinstance(edges, list) or any(
            not isinstance(item, dict) for item in edges
        ):
            raise ValueError("paper graph edges must be a list of objects")
        allowed = _LOGIC_RELATIONS if graph_kind == "logic" else _AUDIT_RELATIONS
        normalized: list[dict[str, Any]] = []
        for edge in edges:
            require_exact_keys(
                edge,
                required={"relation_type", "source", "target", "payload"},
                label="paper graph input edge",
            )
            relation = require_string(edge, "relation_type")
            if relation not in PAPER_RELATION_TYPES or relation not in allowed:
                raise ValueError(
                    f"paper {graph_kind} graph relation is invalid: {relation}"
                )
            require_string(edge, "source")
            require_string(edge, "target")
            if not isinstance(edge["payload"], dict):
                raise ValueError("paper graph edge payload must be an object")
            normalized.append(dict(edge))
        normalized.sort(key=canonical_json_bytes)
        if normalized != expected:
            missing = [item for item in expected if item not in normalized]
            extra = [item for item in normalized if item not in expected]
            raise ValueError(
                "paper graph edges do not exactly match node-declared "
                "ports/directions; "
                f"missing_count={len(missing)} extra_count={len(extra)} "
                "missing="
                + json.dumps(missing[:8], ensure_ascii=False, sort_keys=True)
                + " extra="
                + json.dumps(extra[:8], ensure_ascii=False, sort_keys=True)
                + " schema=references/paper_input_contracts.md"
            )
        return normalized

    @staticmethod
    def _reference(
        value: str,
        *,
        local_nodes: dict[str, dict[str, Any]],
        base_nodes: dict[str, dict[str, Any]],
        expected_local_types: set[str] | None = None,
        expected_base_types: set[str] | None = None,
        label: str,
    ) -> None:
        if value in local_nodes:
            if (
                expected_local_types is not None
                and local_nodes[value]["object_type"] not in expected_local_types
            ):
                raise ValueError(f"{label} has the wrong local node type")
            return
        if value in base_nodes:
            if (
                expected_base_types is not None
                and base_nodes[value]["object_type"] not in expected_base_types
            ):
                raise ValueError(f"{label} has the wrong base node type")
            return
        raise ValueError(f"{label} references an unknown object: {value}")

    @classmethod
    def _validate_logic_semantics(
        cls,
        local_nodes: dict[str, dict[str, Any]],
    ) -> None:
        claims = {
            local_id: node
            for local_id, node in local_nodes.items()
            if node["object_type"] == "claim"
        }
        definitions = {
            local_id
            for local_id, node in local_nodes.items()
            if node["object_type"] == "definition"
        }
        source_units = {
            local_id: node
            for local_id, node in local_nodes.items()
            if node["object_type"] == "source_unit"
        }
        if not claims or not source_units:
            raise ValueError(
                "paper logic graph requires source units and claim nodes"
            )
        order_values = [node["payload"]["order"] for node in source_units.values()]
        if len(order_values) != len(set(order_values)):
            raise ValueError("paper source-unit order values must be unique")
        for local_id, node in local_nodes.items():
            payload = node["payload"]
            object_type = node["object_type"]
            for source_unit in payload.get("source_unit_ids", []):
                cls._reference(
                    source_unit,
                    local_nodes=local_nodes,
                    base_nodes={},
                    expected_local_types={"source_unit"},
                    label=f"paper node {local_id} source unit",
                )
            if object_type == "claim":
                for definition_id in payload["definition_ids"]:
                    if definition_id not in definitions:
                        raise ValueError(
                            f"claim {local_id} uses unknown definition "
                            f"{definition_id}"
                        )
                parent = payload["parent_claim_id"]
                if parent and parent not in claims:
                    raise ValueError(
                        f"claim {local_id} has unknown parent {parent}"
                    )
                if payload["representation_kind"] == "source_literal":
                    source_text = "\n".join(
                        source_units[item]["payload"]["text"]
                        for item in payload["source_unit_ids"]
                    )
                    if payload["statement"] not in source_text:
                        raise ValueError(
                            f"literal claim {local_id} is not an exact source "
                            "substring"
                        )
                    speaker_map = {
                        "author": {"author"},
                        "cited_author": {"quoted_source"},
                        "interlocutor": {"interlocutor"},
                        "objection": {"objection", "interlocutor"},
                        "editor": {"editor"},
                    }
                    allowed_speakers = speaker_map.get(
                        payload["attribution"], set()
                    )
                    observed = {
                        source_units[item]["payload"]["speaker"]
                        for item in payload["source_unit_ids"]
                    }
                    if allowed_speakers and not observed.issubset(
                        allowed_speakers
                    ):
                        raise ValueError(
                            f"literal claim {local_id} attribution/speaker "
                            "mismatch"
                        )
            elif object_type == "inference":
                for premise_id in payload["premise_ids"]:
                    if premise_id not in claims:
                        raise ValueError(
                            f"inference {local_id} has nonclaim premise "
                            f"{premise_id}"
                        )
                conclusion_id = payload["conclusion_id"]
                if conclusion_id not in claims:
                    raise ValueError(
                        f"inference {local_id} has nonclaim conclusion "
                        f"{conclusion_id}"
                    )
                for bridge_id in payload["bridge_claim_ids"]:
                    if bridge_id not in claims:
                        raise ValueError(
                            f"inference {local_id} has unknown bridge claim "
                            f"{bridge_id}"
                        )
                for defeater_id in payload["defeater_claim_ids"]:
                    if defeater_id not in claims:
                        raise ValueError(
                            f"inference {local_id} has unknown defeater claim "
                            f"{defeater_id}"
                        )
                conclusion = claims[conclusion_id]["payload"]
                premises = [
                    claims[item]["payload"] for item in payload["premise_ids"]
                ]
                if conclusion["content_type"] == "normative" and not any(
                    item["content_type"] == "normative" for item in premises
                ):
                    if payload["inference_kind"] != "normative_bridge":
                        raise ValueError(
                            f"inference {local_id} hides a normative bridge"
                        )
                if (
                    payload["inference_kind"] == "default_presumption"
                    and conclusion["modality"] != "defeasible"
                ):
                    raise ValueError(
                        f"inference {local_id} default conclusion must be "
                        "defeasible"
                    )
            elif object_type == "paper_target":
                if payload["claim_id"] not in claims:
                    raise ValueError(
                        f"paper target {local_id} references a nonclaim"
                    )
        dependency: dict[str, set[str]] = {claim_id: set() for claim_id in claims}
        for local_id, node in local_nodes.items():
            if node["object_type"] != "inference":
                continue
            conclusion = node["payload"]["conclusion_id"]
            dependency[conclusion].update(node["payload"]["premise_ids"])
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(claim_id: str) -> None:
            if claim_id in visiting:
                raise ValueError("paper inference dependency cycle")
            if claim_id in visited:
                return
            visiting.add(claim_id)
            for premise in dependency[claim_id]:
                visit(premise)
            visiting.remove(claim_id)
            visited.add(claim_id)

        for claim_id in sorted(dependency):
            visit(claim_id)
        target_claims = {
            node["payload"]["claim_id"]
            for node in local_nodes.values()
            if node["object_type"] == "paper_target"
        }
        headline_claims = {
            node["payload"]["claim_id"]
            for node in local_nodes.values()
            if node["object_type"] == "paper_target"
            and node["payload"]["target_role"] == "headline"
        }
        if not headline_claims:
            raise ValueError("paper logic graph needs a headline target")
        forward: dict[str, set[str]] = {}
        for conclusion, premises in dependency.items():
            for premise in premises:
                forward.setdefault(premise, set()).add(conclusion)
        for claim_id, node in claims.items():
            if node["payload"]["discourse_role"] == "background":
                continue
            queue = [claim_id]
            seen: set[str] = set()
            reaches = False
            while queue:
                current = queue.pop()
                if current in target_claims:
                    reaches = True
                    break
                if current in seen:
                    continue
                seen.add(current)
                queue.extend(forward.get(current, ()))
            if not reaches:
                raise ValueError(
                    f"argument-relevant claim {claim_id} does not reach a "
                    "declared paper target"
                )

    @classmethod
    def _validate_audit_semantics(
        cls,
        local_nodes: dict[str, dict[str, Any]],
        *,
        base_nodes: dict[str, dict[str, Any]],
        base_edges: dict[str, dict[str, Any]],
    ) -> None:
        if not base_nodes:
            raise ValueError("paper audit graph needs a frozen base snapshot")
        anchored: dict[str, set[str]] = {}
        for edge in base_edges.values():
            if edge["relation_type"] == "anchors":
                anchored.setdefault(edge["source_id"], set()).add(
                    edge["target_id"]
                )
        for local_id, node in local_nodes.items():
            payload = node["payload"]
            object_type = node["object_type"]
            if object_type == "audit_finding":
                target = payload["target_id"]
                cls._reference(
                    target,
                    local_nodes=local_nodes,
                    base_nodes=base_nodes,
                    expected_base_types=None,
                    label=f"audit finding {local_id} target",
                )
                evidence_ids = payload["evidence_unit_ids"]
                for evidence_id in evidence_ids:
                    cls._reference(
                        evidence_id,
                        local_nodes=local_nodes,
                        base_nodes=base_nodes,
                        expected_base_types={"source_unit"},
                        label=f"audit finding {local_id} evidence",
                    )
                if evidence_ids:
                    excerpt = payload["observed_excerpt"]
                    if not any(
                        excerpt
                        in str(base_nodes[evidence_id]["payload"].get("text", ""))
                        for evidence_id in evidence_ids
                    ):
                        raise ValueError(
                            f"audit finding {local_id} excerpt is not in its "
                            "evidence unit"
                        )
                    allowed_evidence = (
                        {target}
                        if base_nodes[target]["object_type"] == "source_unit"
                        else anchored.get(target, set())
                    )
                    if not set(evidence_ids).issubset(allowed_evidence):
                        raise ValueError(
                            f"audit finding {local_id} evidence is not anchored "
                            "to the exact target"
                        )
            elif object_type == "counterexample":
                target_id = payload["target_id"]
                cls._reference(
                    target_id,
                    local_nodes=local_nodes,
                    base_nodes=base_nodes,
                    expected_base_types={"claim", "inference"},
                    label=f"counterexample {local_id} target",
                )
                witness_ids = {
                    item["premise_id"]
                    for item in payload["premise_witnesses"]
                }
                unknown_witnesses = {
                    witness_id
                    for witness_id in witness_ids
                    if witness_id not in base_nodes
                    or base_nodes[witness_id]["object_type"] != "claim"
                }
                if unknown_witnesses:
                    raise ValueError(
                        f"counterexample {local_id} premise witnesses are not "
                        "base claim nodes: "
                        + ", ".join(sorted(unknown_witnesses))
                    )
                if (
                    payload["provisional_logical_effect"]
                    == "refutes_exact_representation"
                ):
                    target = base_nodes[target_id]
                    if target["object_type"] == "inference":
                        candidate_premise_sets = [
                            {
                                edge["source_id"]
                                for edge in base_edges.values()
                                if edge["relation_type"] == "premise_of"
                                and edge["target_id"] == target_id
                            }
                        ]
                    else:
                        concluding_inference_ids = {
                            edge["source_id"]
                            for edge in base_edges.values()
                            if edge["relation_type"] == "concludes"
                            and edge["target_id"] == target_id
                        }
                        candidate_premise_sets = [
                            {
                                edge["source_id"]
                                for edge in base_edges.values()
                                if edge["relation_type"] == "premise_of"
                                and edge["target_id"] == inference_id
                            }
                            for inference_id in concluding_inference_ids
                        ]
                    if witness_ids not in candidate_premise_sets:
                        raise ValueError(
                            f"counterexample {local_id} does not witness every "
                            "premise of one exact targeted inference"
                        )
            elif object_type == "repair_proposal":
                cls._reference(
                    payload["target_id"],
                    local_nodes=local_nodes,
                    base_nodes=base_nodes,
                    expected_base_types={"claim", "inference"},
                    label=f"repair {local_id} target",
                )
                for addressed in payload["addresses_ids"]:
                    cls._reference(
                        addressed,
                        local_nodes=local_nodes,
                        base_nodes=base_nodes,
                        expected_local_types={
                            "audit_finding",
                            "counterexample",
                            "audit_challenge",
                        },
                        expected_base_types=PAPER_AUDIT_TYPES,
                        label=f"repair {local_id} addressed challenge",
                    )
            elif object_type == "impact_assessment":
                cls._reference(
                    payload["challenge_id"],
                    local_nodes=local_nodes,
                    base_nodes=base_nodes,
                    expected_local_types={
                        "audit_finding",
                        "counterexample",
                        "audit_challenge",
                    },
                    expected_base_types=PAPER_AUDIT_TYPES,
                    label=f"impact {local_id} challenge",
                )
                if payload["repair_id"]:
                    cls._reference(
                        payload["repair_id"],
                        local_nodes=local_nodes,
                        base_nodes=base_nodes,
                        expected_local_types={"repair_proposal"},
                        expected_base_types={"repair_proposal"},
                        label=f"impact {local_id} repair",
                    )
                cls._reference(
                    payload["core_target_id"],
                    local_nodes=local_nodes,
                    base_nodes=base_nodes,
                    expected_base_types={"claim", "inference"},
                    label=f"impact {local_id} core target",
                )
            elif object_type == "audit_challenge":
                cls._reference(
                    payload["target_audit_id"],
                    local_nodes=local_nodes,
                    base_nodes=base_nodes,
                    expected_base_types=PAPER_AUDIT_TYPES,
                    label=f"audit challenge {local_id} target",
                )
            elif object_type == "audit_disposition":
                cls._reference(
                    payload["target_audit_id"],
                    local_nodes=local_nodes,
                    base_nodes=base_nodes,
                    expected_base_types=PAPER_AUDIT_TYPES,
                    label=f"audit disposition {local_id} target",
                )
                for challenge in payload["challenge_ids"]:
                    cls._reference(
                        challenge,
                        local_nodes=local_nodes,
                        base_nodes=base_nodes,
                        expected_local_types={"audit_challenge"},
                        expected_base_types={"audit_challenge"},
                        label=f"audit disposition {local_id} challenge",
                    )
                for replacement in payload["replacement_ids"]:
                    cls._reference(
                        replacement,
                        local_nodes=local_nodes,
                        base_nodes=base_nodes,
                        expected_local_types=PAPER_AUDIT_TYPES,
                        expected_base_types=PAPER_AUDIT_TYPES,
                        label=f"audit disposition {local_id} replacement",
                    )
        counterexamples = {
            local_id: node
            for local_id, node in local_nodes.items()
            if node["object_type"] == "counterexample"
        }
        impacts = [
            node["payload"]
            for node in local_nodes.values()
            if node["object_type"] == "impact_assessment"
        ]
        repairs = {
            local_id: node["payload"]
            for local_id, node in local_nodes.items()
            if node["object_type"] == "repair_proposal"
        }
        for counterexample_id in counterexamples:
            matching = [
                item for item in impacts if item["challenge_id"] == counterexample_id
            ]
            if len(matching) != 1:
                raise ValueError(
                    f"counterexample {counterexample_id} needs exactly one "
                    "impact assessment"
                )
            if (
                matching[0]["logical_effect"]
                != counterexamples[counterexample_id]["payload"][
                    "provisional_logical_effect"
                ]
            ):
                raise ValueError(
                    f"counterexample {counterexample_id} logical impact mismatch"
                )
            impact = matching[0]
            counterexample = counterexamples[counterexample_id]["payload"]
            if impact["repair_id"]:
                repair = repairs.get(impact["repair_id"])
                if repair is None:
                    base_repair = base_nodes.get(impact["repair_id"])
                    repair = (
                        base_repair["payload"]
                        if base_repair is not None
                        and base_repair["object_type"] == "repair_proposal"
                        else None
                    )
                if repair is None:
                    raise ValueError(
                        f"impact for {counterexample_id} names no valid repair"
                    )
                if (
                    repair["core_preservation"]
                    != impact["core_preservation"]
                ):
                    raise ValueError(
                        f"impact for {counterexample_id} disagrees with its "
                        "repair about core preservation"
                    )
            if impact["domain_profile"] == "philosophy":
                if (
                    counterexample["nontriviality"] == "trivial"
                    and impact["dialectical_effect"]
                    in {"refutes_variant", "refutes_core"}
                ):
                    raise ValueError(
                        f"trivial counterexample {counterexample_id} cannot be "
                        "inflated into philosophical refutation"
                    )
                available_core_preserving_repairs = [
                    repair
                    for repair in repairs.values()
                    if counterexample_id in repair["addresses_ids"]
                    and repair["core_preservation"] == "preserved"
                    and repair["ad_hoc_risk"] != "high"
                ]
                if (
                    impact["dialectical_effect"] == "refutes_core"
                    and available_core_preserving_repairs
                ):
                    raise ValueError(
                        f"philosophical core refutation for "
                        f"{counterexample_id} ignores a viable "
                        "core-preserving repair"
                    )

    @staticmethod
    def _resolve_endpoint(
        value: str,
        *,
        local_id_map: dict[str, str],
        base_nodes: dict[str, dict[str, Any]],
    ) -> str:
        if value in local_id_map:
            return local_id_map[value]
        if value in base_nodes:
            return value
        raise ValueError(f"paper edge endpoint is unknown: {value}")

    def stage(
        self,
        bundle: dict[str, Any],
        *,
        artifact_path: Path | str,
        actor: str,
    ) -> dict[str, Any]:
        feature = self._feature()
        require_exact_keys(
            bundle,
            required=_BUNDLE_FIELDS,
            label="paper graph bundle",
        )
        if (
            bundle.get("schema_version") != 1
            or bundle.get("feature_revision")
            != PAPER_LOGIC_FEATURE_REVISION
            or bundle.get("project_id") != feature["project_id"]
        ):
            raise ValueError("paper graph bundle binding mismatch")
        paper_id = require_string(bundle, "paper_id")
        graph_kind = bundle["graph_kind"]
        if graph_kind not in GRAPH_KINDS:
            raise ValueError("paper graph bundle graph_kind is invalid")
        domain_profile = bundle["domain_profile"]
        if domain_profile not in DOMAIN_PROFILES:
            raise ValueError("paper graph bundle domain_profile is invalid")
        builder = require_string(bundle, "builder")
        builder_context_id = require_string(bundle, "builder_context_id")
        if builder != actor:
            raise ValueError("paper graph builder must equal the staging actor")
        source = validate_source(bundle["source"])
        base_snapshot_id = require_string(
            bundle, "base_snapshot_id", allow_empty=True
        )
        supersedes_snapshot_id = require_string(
            bundle, "supersedes_snapshot_id", allow_empty=True
        )
        base_nodes: dict[str, dict[str, Any]] = {}
        base_edges: dict[str, dict[str, Any]] = {}
        base_manifest: dict[str, Any] | None = None
        if graph_kind == "logic":
            if base_snapshot_id:
                raise ValueError("logic graph bundle cannot have a base snapshot")
        else:
            if not base_snapshot_id:
                raise ValueError("audit graph bundle needs a base snapshot")
            base_manifest = self.snapshot_manifest(base_snapshot_id)
            base_nodes, base_edges = self.snapshot_objects(base_snapshot_id)
            if (
                base_manifest["paper_id"] != paper_id
                or base_manifest["domain_profile"] != domain_profile
            ):
                raise ValueError("audit graph/base snapshot paper binding mismatch")
            if source["artifact_sha256"] not in {
                item["artifact_sha256"]
                for item in base_manifest["source_artifacts"]
            }:
                raise ValueError("audit graph source hash is absent from base snapshot")
        if supersedes_snapshot_id:
            superseded = self.snapshot_manifest(supersedes_snapshot_id)
            if (
                superseded["paper_id"] != paper_id
                or superseded["graph_kind"] != graph_kind
            ):
                raise ValueError(
                    "superseded snapshot kind/paper binding mismatch"
                )
        artifact = Path(artifact_path).expanduser().resolve()
        if artifact.is_symlink() or not artifact.is_file():
            raise ValueError("paper source artifact is missing or unsafe")
        artifact_bytes = artifact.read_bytes()
        if sha256_bytes(artifact_bytes) != source["artifact_sha256"]:
            raise ValueError("paper source artifact SHA-256 mismatch")
        nodes_input = bundle["nodes"]
        if not isinstance(nodes_input, list) or not nodes_input or any(
            not isinstance(item, dict) for item in nodes_input
        ):
            raise ValueError("paper graph bundle nodes must be nonempty objects")
        local_nodes: dict[str, dict[str, Any]] = {}
        for item in nodes_input:
            validate_local_node(
                item,
                graph_kind=graph_kind,
                domain_profile=domain_profile,
            )
            local_id = item["local_id"]
            if local_id in local_nodes:
                raise ValueError(f"duplicate paper local node id: {local_id}")
            local_nodes[local_id] = item
        coverage = self._validate_coverage(
            bundle["coverage"],
            graph_kind=graph_kind,
            local_nodes=local_nodes,
        )
        if graph_kind == "logic":
            self._validate_logic_semantics(local_nodes)
            expected_edges = self._expected_logic_edges(local_nodes)
        else:
            self._validate_audit_semantics(
                local_nodes,
                base_nodes=base_nodes,
                base_edges=base_edges,
            )
            expected_edges = self._expected_audit_edges(local_nodes)
        input_edges = self._validate_input_edges(
            bundle["edges"],
            expected_edges,
            graph_kind=graph_kind,
        )
        bundle_sha256 = sha256_json(bundle)
        provenance = {
            "builder": builder,
            "builder_context_id": builder_context_id,
            "bundle_sha256": bundle_sha256,
            "base_snapshot_id": base_snapshot_id,
        }
        nodes: list[dict[str, Any]] = []
        local_id_map: dict[str, str] = {}
        if graph_kind == "logic":
            source_node = make_paper_node(
                project_id=feature["project_id"],
                paper_id=paper_id,
                plane="paper_source",
                object_type="source_artifact",
                logical_key="__source__",
                payload=dict(source),
                provenance=provenance,
            )
            nodes.append(source_node)
            local_id_map["__source__"] = source_node["object_id"]
        for local_id, item in sorted(local_nodes.items()):
            object_type = item["object_type"]
            plane = (
                "paper_source"
                if object_type == "source_unit"
                else (
                    "paper_reconstruction"
                    if object_type in PAPER_RECONSTRUCTION_TYPES
                    else "paper_audit"
                )
            )
            node = make_paper_node(
                project_id=feature["project_id"],
                paper_id=paper_id,
                plane=plane,
                object_type=object_type,
                logical_key=local_id,
                payload=dict(item["payload"]),
                provenance=provenance,
            )
            validate_paper_node(node)
            nodes.append(node)
            local_id_map[local_id] = node["object_id"]
        edges: list[dict[str, Any]] = []
        for item in input_edges:
            relation = item["relation_type"]
            plane = (
                "paper_source"
                if relation == "contains"
                else (
                    "paper_reconstruction"
                    if relation in _LOGIC_RELATIONS
                    else "paper_audit"
                )
            )
            edge = make_paper_edge(
                project_id=feature["project_id"],
                paper_id=paper_id,
                plane=plane,
                relation_type=relation,
                source_id=self._resolve_endpoint(
                    item["source"],
                    local_id_map=local_id_map,
                    base_nodes=base_nodes,
                ),
                target_id=self._resolve_endpoint(
                    item["target"],
                    local_id_map=local_id_map,
                    base_nodes=base_nodes,
                ),
                payload=dict(item["payload"]),
                provenance=provenance,
            )
            validate_paper_edge(edge)
            edges.append(edge)
        node_entries = sorted(
            (self._entry(node) for node in nodes),
            key=lambda item: item["object_id"],
        )
        edge_entries = sorted(
            (self._entry(edge) for edge in edges),
            key=lambda item: item["object_id"],
        )
        artifact_relpath = (
            Path("paper_logic")
            / "artifacts"
            / "by-sha256"
            / f"{source['artifact_sha256']}.artifact"
        ).as_posix()
        revision_body = {
            "schema_version": 1,
            "feature_revision": PAPER_LOGIC_FEATURE_REVISION,
            "project_id": feature["project_id"],
            "bundle_sha256": bundle_sha256,
            "paper_id": paper_id,
            "graph_kind": graph_kind,
            "domain_profile": domain_profile,
            "builder": builder,
            "builder_context_id": builder_context_id,
            "source": source,
            "artifact_relpath": artifact_relpath,
            "base_snapshot_id": base_snapshot_id,
            "supersedes_snapshot_id": supersedes_snapshot_id,
            "coverage": coverage,
            "node_entries": node_entries,
            "edge_entries": edge_entries,
            "local_id_map": dict(sorted(local_id_map.items())),
            "required_review_profiles": list(
                REVIEW_PROFILES_BY_GRAPH_KIND[graph_kind]
            ),
            "truth_effect": "none",
        }
        revision_id = "plr-" + sha256_json(revision_body)
        revision = {**revision_body, "revision_id": revision_id}
        self._write_bytes_once(
            self.project_root / artifact_relpath,
            artifact_bytes,
        )
        for node in nodes:
            self._write_json_once(self._node_path(node["object_id"]), node)
        for edge in edges:
            self._write_json_once(self._edge_path(edge["object_id"]), edge)
        self._write_json_once(self._revision_path(revision_id), revision)
        return {
            "revision_id": revision_id,
            "bundle_sha256": bundle_sha256,
            "review_packet_path": str(self._revision_path(revision_id)),
            "required_review_profiles": revision["required_review_profiles"],
            "status": "staged_nontruth",
            "truth_effect": "none",
        }

    def revision(self, revision_id: str) -> dict[str, Any]:
        revision = self._read_json(self._revision_path(revision_id))
        require_exact_keys(
            revision,
            required=_REVISION_FIELDS,
            label="paper graph revision",
        )
        if (
            revision.get("schema_version") != 1
            or revision.get("feature_revision")
            != PAPER_LOGIC_FEATURE_REVISION
            or revision.get("project_id") != self._feature()["project_id"]
        ):
            raise ValueError("paper graph revision binding mismatch")
        semantic = {
            key: value
            for key, value in revision.items()
            if key != "revision_id"
        }
        expected = "plr-" + sha256_json(semantic)
        if revision.get("revision_id") != expected:
            raise ValueError("paper graph revision id/hash mismatch")
        if revision["graph_kind"] not in GRAPH_KINDS:
            raise ValueError("paper graph revision graph_kind is invalid")
        if revision["domain_profile"] not in DOMAIN_PROFILES:
            raise ValueError("paper graph revision domain_profile is invalid")
        if revision["required_review_profiles"] != list(
            REVIEW_PROFILES_BY_GRAPH_KIND[revision["graph_kind"]]
        ):
            raise ValueError("paper graph required review profiles mismatch")
        for entry in revision["node_entries"]:
            self._validate_entry(entry, "paper revision node entry")
            if not entry["object_id"].startswith(("psn-", "prn-", "pan-")):
                raise ValueError("paper revision node entry has edge id")
        for entry in revision["edge_entries"]:
            self._validate_entry(entry, "paper revision edge entry")
            if not entry["object_id"].startswith(("pse-", "pre-", "pae-")):
                raise ValueError("paper revision edge entry has node id")
        local_map = revision["local_id_map"]
        if not isinstance(local_map, dict) or any(
            not isinstance(key, str)
            or not isinstance(value, str)
            or PAPER_NODE_ID_RE.fullmatch(value) is None
            for key, value in local_map.items()
        ):
            raise ValueError("paper graph revision local_id_map is invalid")
        if revision["truth_effect"] != "none":
            raise ValueError("paper graph revision truth_effect must be none")
        return revision

    def _revision_objects(
        self, revision: dict[str, Any]
    ) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
        nodes: dict[str, dict[str, Any]] = {}
        edges: dict[str, dict[str, Any]] = {}
        for entry in revision["node_entries"]:
            node = validate_paper_node(
                self._read_json(self._node_path(entry["object_id"]))
            )
            if sha256_json(node) != entry["sha256"]:
                raise ValueError(
                    f"paper node hash mismatch: {entry['object_id']}"
                )
            nodes[node["object_id"]] = node
        for entry in revision["edge_entries"]:
            edge = validate_paper_edge(
                self._read_json(self._edge_path(entry["object_id"]))
            )
            if sha256_json(edge) != entry["sha256"]:
                raise ValueError(
                    f"paper edge hash mismatch: {entry['object_id']}"
                )
            edges[edge["object_id"]] = edge
        available_nodes = set(nodes)
        if revision["base_snapshot_id"]:
            base_nodes, _ = self.snapshot_objects(
                revision["base_snapshot_id"]
            )
            available_nodes.update(base_nodes)
        for edge in edges.values():
            if (
                edge["source_id"] not in available_nodes
                or edge["target_id"] not in available_nodes
            ):
                raise ValueError(
                    f"paper edge {edge['object_id']} has a dangling endpoint"
                )
        return nodes, edges

    def _expected_review_object_ids(
        self,
        revision: dict[str, Any],
        profile: str,
    ) -> set[str]:
        nodes, edges = self._revision_objects(revision)
        if profile == "source_fidelity":
            result = {
                node_id
                for node_id, node in nodes.items()
                if node["plane"] == "paper_source"
                or (
                    node["plane"] == "paper_reconstruction"
                    and node["object_type"]
                    in {"claim", "definition", "formula", "inference"}
                    and bool(node["payload"].get("source_unit_ids", []))
                )
            }
            result.update(
                edge_id
                for edge_id, edge in edges.items()
                if edge["relation_type"] in {"contains", "anchors"}
            )
            return result
        if profile == "graph_structure":
            return {
                object_id
                for object_id, node in nodes.items()
                if node["plane"] == "paper_reconstruction"
            } | {
                object_id
                for object_id, edge in edges.items()
                if edge["plane"] == "paper_reconstruction"
            }
        if profile == "target_binding":
            return set(nodes) | set(edges)
        if profile == "audit_reasoning":
            return set(nodes)
        raise ValueError(f"unknown paper review profile: {profile}")

    def _validate_review_payload(
        self,
        payload: dict[str, Any],
        *,
        require_id: bool,
    ) -> dict[str, Any]:
        expected_fields = set(_REVIEW_FIELDS)
        if not require_id:
            expected_fields.remove("review_id")
        require_exact_keys(
            payload,
            required=expected_fields,
            label="paper graph review",
        )
        if (
            payload.get("schema_version") != 1
            or payload.get("feature_revision")
            != PAPER_LOGIC_FEATURE_REVISION
            or payload.get("project_id") != self._feature()["project_id"]
        ):
            raise ValueError("paper graph review binding mismatch")
        revision = self.revision(
            validate_paper_revision_id(require_string(payload, "revision_id"))
        )
        if payload.get("bundle_sha256") != revision["bundle_sha256"]:
            raise ValueError("paper graph review bundle hash mismatch")
        profile = require_string(payload, "profile")
        if profile not in revision["required_review_profiles"]:
            raise ValueError("paper graph review profile is not required")
        verdict = payload.get("verdict")
        if verdict not in {"correct", "reject", "blocked"}:
            raise ValueError("paper graph review verdict is invalid")
        reviewer = require_string(payload, "reviewer")
        reviewer_context_id = require_string(payload, "reviewer_context_id")
        if reviewer == revision["builder"]:
            raise ValueError("paper graph builder cannot review its own graph")
        if reviewer_context_id == revision["builder_context_id"]:
            raise ValueError("paper graph review reused the builder context")
        if payload.get("fresh_context_contract") != "fresh-context-v1":
            raise ValueError("paper graph review needs fresh-context-v1")
        object_checks = payload["object_checks"]
        if not isinstance(object_checks, list) or any(
            not isinstance(item, dict) for item in object_checks
        ):
            raise ValueError("paper graph object_checks must be objects")
        seen_objects: set[str] = set()
        for item in object_checks:
            require_exact_keys(
                item,
                required={"object_id", "status", "finding"},
                label="paper graph object check",
            )
            object_id = validate_paper_object_id(
                require_string(item, "object_id")
            )
            if object_id in seen_objects:
                raise ValueError(
                    f"paper review duplicates object check {object_id}"
                )
            seen_objects.add(object_id)
            if item["status"] not in {"pass", "issue", "not_applicable"}:
                raise ValueError("paper graph object check status is invalid")
            require_string(item, "finding")
        required_objects = self._expected_review_object_ids(
            revision, profile
        )
        if seen_objects != required_objects:
            raise ValueError(
                "paper graph review object coverage mismatch: "
                f"missing={sorted(required_objects.difference(seen_objects))} "
                f"extra={sorted(seen_objects.difference(required_objects))}"
            )
        global_checks = payload["global_checks"]
        if not isinstance(global_checks, list) or any(
            not isinstance(item, dict) for item in global_checks
        ):
            raise ValueError("paper graph global_checks must be objects")
        seen_kinds: set[str] = set()
        for item in global_checks:
            require_exact_keys(
                item,
                required={"kind", "status", "finding"},
                label="paper graph global check",
            )
            kind = require_string(item, "kind")
            if kind in seen_kinds:
                raise ValueError(f"paper review duplicates global check {kind}")
            seen_kinds.add(kind)
            if item["status"] not in {"pass", "issue", "not_applicable"}:
                raise ValueError("paper graph global check status is invalid")
            require_string(item, "finding")
            if (
                item["status"] == "not_applicable"
                and kind != "formula_glyphs"
            ):
                raise ValueError(
                    "only formula_glyphs may be not_applicable"
                )
        if seen_kinds != REVIEW_GLOBAL_CHECKS[profile]:
            raise ValueError("paper graph review global-check coverage mismatch")
        critical_errors = self._require_strings(
            payload["critical_errors"], "paper graph review critical_errors"
        )
        gaps = self._require_strings(
            payload["gaps"], "paper graph review gaps"
        )
        if payload.get("truth_effect") != "none":
            raise ValueError("paper graph review truth_effect must be none")
        if verdict == "correct":
            if critical_errors or gaps:
                raise ValueError(
                    "correct paper graph review cannot have errors or gaps"
                )
            for item in [*object_checks, *global_checks]:
                if item["status"] == "issue":
                    raise ValueError(
                        "correct paper graph review cannot contain an issue"
                    )
            formula_present = any(
                node["object_type"] == "formula"
                for node in self._revision_objects(revision)[0].values()
            )
            if formula_present and any(
                item["kind"] == "formula_glyphs"
                and item["status"] != "pass"
                for item in global_checks
            ):
                raise ValueError(
                    "formula-bearing graph needs a passing glyph review"
                )
        elif not critical_errors and not gaps:
            raise ValueError(
                "reject/blocked paper graph review needs an error or gap"
            )
        if require_id:
            review_id = validate_paper_review_id(
                require_string(payload, "review_id")
            )
            semantic = {
                key: value
                for key, value in payload.items()
                if key != "review_id"
            }
            if review_id != "plv-" + sha256_json(semantic):
                raise ValueError("paper graph review id/hash mismatch")
        return payload

    def record_review(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._feature()
        self._validate_review_payload(payload, require_id=False)
        semantic = dict(payload)
        review_id = "plv-" + sha256_json(semantic)
        review = {**semantic, "review_id": review_id}
        self._validate_review_payload(review, require_id=True)
        self._write_json_once(self._review_path(review_id), review)
        return {
            "review_id": review_id,
            "revision_id": review["revision_id"],
            "profile": review["profile"],
            "verdict": review["verdict"],
            "truth_effect": "none",
            "status": "recorded",
        }

    def review(self, review_id: str) -> dict[str, Any]:
        payload = self._read_json(self._review_path(review_id))
        return self._validate_review_payload(payload, require_id=True)

    def reviews_for_revision(self, revision_id: str) -> list[dict[str, Any]]:
        validate_paper_revision_id(revision_id)
        result: list[dict[str, Any]] = []
        for path in sorted(self.reviews_dir.glob("plv-*.json")):
            review = self.review(path.stem)
            if review["revision_id"] == revision_id:
                result.append(review)
        return result

    def _selected_reviews(
        self, revision: dict[str, Any]
    ) -> list[dict[str, Any]]:
        reviews = self.reviews_for_revision(revision["revision_id"])
        if any(review["verdict"] == "reject" for review in reviews):
            raise ValueError(
                "rejected paper graph revision must be replaced, not repaired "
                "in place"
            )
        selected: list[dict[str, Any]] = []
        for profile in revision["required_review_profiles"]:
            candidates = [
                review
                for review in reviews
                if review["profile"] == profile
                and review["verdict"] == "correct"
            ]
            if not candidates:
                raise ValueError(
                    f"paper graph revision lacks correct {profile} review"
                )
            selected.append(
                sorted(candidates, key=lambda item: item["review_id"])[0]
            )
        reviewers = [item["reviewer"] for item in selected]
        contexts = [item["reviewer_context_id"] for item in selected]
        if len(reviewers) != len(set(reviewers)):
            raise ValueError(
                "paper graph review profiles need distinct reviewers"
            )
        if len(contexts) != len(set(contexts)):
            raise ValueError(
                "paper graph review profiles need distinct fresh contexts"
            )
        return selected

    @staticmethod
    def _canonical_jsonl(
        objects: Iterable[dict[str, Any]],
    ) -> bytes:
        return b"".join(
            canonical_json_bytes(item) + b"\n"
            for item in sorted(objects, key=lambda value: value["object_id"])
        )

    def _write_snapshot_once(
        self,
        manifest: dict[str, Any],
        *,
        nodes: dict[str, dict[str, Any]],
        edges: dict[str, dict[str, Any]],
    ) -> None:
        snapshot_id = manifest["snapshot_id"]
        destination = self._snapshot_path(snapshot_id)
        manifest_bytes = (
            json.dumps(
                manifest,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ).encode("utf-8")
            + b"\n"
        )
        nodes_bytes = self._canonical_jsonl(nodes.values())
        edges_bytes = self._canonical_jsonl(edges.values())
        if destination.exists():
            if destination.is_symlink() or not destination.is_dir():
                raise ValueError("paper snapshot collision is unsafe")
            expected = {
                "manifest.json": manifest_bytes,
                "nodes.jsonl": nodes_bytes,
                "edges.jsonl": edges_bytes,
            }
            actual_names = {
                path.name
                for path in destination.iterdir()
                if path.is_file() and not path.is_symlink()
            }
            if actual_names != set(expected):
                raise ValueError("paper snapshot immutable file-set collision")
            for name, payload in expected.items():
                if (destination / name).read_bytes() != payload:
                    raise ValueError("paper snapshot immutable byte collision")
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(
            tempfile.mkdtemp(
                prefix=f".{snapshot_id}.",
                dir=destination.parent,
            )
        )
        try:
            (temporary / "manifest.json").write_bytes(manifest_bytes)
            (temporary / "nodes.jsonl").write_bytes(nodes_bytes)
            (temporary / "edges.jsonl").write_bytes(edges_bytes)
            for path in temporary.iterdir():
                with path.open("rb") as handle:
                    os.fsync(handle.fileno())
            os.replace(temporary, destination)
        except BaseException:
            shutil.rmtree(temporary, ignore_errors=True)
            raise

    @staticmethod
    def _audit_projection(
        nodes: dict[str, dict[str, Any]],
    ) -> tuple[list[str], list[str]]:
        inactive: set[str] = set()
        for node in nodes.values():
            if node["object_type"] != "audit_disposition":
                continue
            payload = node["payload"]
            if payload["disposition"] in {
                "narrowed",
                "corrected",
                "withdrawn",
            }:
                inactive.add(payload["target_audit_id"])
        current = sorted(
            node_id
            for node_id, node in nodes.items()
            if node["plane"] == "paper_audit" and node_id not in inactive
        )
        return current, sorted(inactive)

    def freeze(
        self,
        revision_id: str,
        *,
        actor: str,
    ) -> dict[str, Any]:
        self._feature()
        revision = self.revision(revision_id)
        if revision["coverage"]["unresolved_load_bearing_units"]:
            raise ValueError(
                "paper graph has unresolved load-bearing coverage units"
            )
        selected_reviews = self._selected_reviews(revision)
        new_nodes, new_edges = self._revision_objects(revision)
        nodes: dict[str, dict[str, Any]] = {}
        edges: dict[str, dict[str, Any]] = {}
        revision_ids: list[str] = []
        local_maps: dict[str, dict[str, str]] = {}
        source_artifacts: list[dict[str, str]] = []
        if revision["base_snapshot_id"]:
            base_manifest = self.snapshot_manifest(
                revision["base_snapshot_id"]
            )
            nodes, edges = self.snapshot_objects(
                revision["base_snapshot_id"]
            )
            revision_ids.extend(base_manifest["revision_ids"])
            local_maps.update(base_manifest["local_id_maps"])
            source_artifacts.extend(base_manifest["source_artifacts"])
        collisions = set(nodes).intersection(new_nodes) | set(edges).intersection(
            new_edges
        )
        if collisions:
            raise ValueError(
                "paper graph revision collides with base objects: "
                + ", ".join(sorted(collisions))
            )
        nodes.update(new_nodes)
        edges.update(new_edges)
        revision_ids.append(revision_id)
        local_maps[revision_id] = revision["local_id_map"]
        source_entry = {
            "artifact_sha256": revision["source"]["artifact_sha256"],
            "artifact_relpath": revision["artifact_relpath"],
        }
        if source_entry not in source_artifacts:
            source_artifacts.append(source_entry)
        source_artifacts.sort(
            key=lambda item: (
                item["artifact_sha256"],
                item["artifact_relpath"],
            )
        )
        node_entries = sorted(
            (self._entry(node) for node in nodes.values()),
            key=lambda item: item["object_id"],
        )
        edge_entries = sorted(
            (self._entry(edge) for edge in edges.values()),
            key=lambda item: item["object_id"],
        )
        transaction_body = {
            "schema_version": 1,
            "feature_revision": PAPER_LOGIC_FEATURE_REVISION,
            "project_id": revision["project_id"],
            "revision_id": revision_id,
            "review_ids": sorted(
                item["review_id"] for item in selected_reviews
            ),
            "node_entries": revision["node_entries"],
            "edge_entries": revision["edge_entries"],
            "actor": actor,
            "truth_effect": "none",
        }
        transaction_id = "plt-" + sha256_json(transaction_body)
        transaction = {
            **transaction_body,
            "transaction_id": transaction_id,
        }
        current_audit, inactive_audit = self._audit_projection(nodes)
        readiness = {
            "schema_ready": True,
            "source_fidelity_ready": True,
            "operator_scope_ready": True,
            "inference_structure_ready": True,
            "coverage_ready": True,
            "independence_ready": True,
            "scope": (
                "full_scope_plg_ready"
                if revision["coverage"]["scope_kind"] == "full_artifact"
                else (
                    "bounded_plg_ready"
                    if revision["graph_kind"] == "logic"
                    else "audit_scope_ready"
                )
            ),
            "truth_effect": "none",
        }
        snapshot_body = {
            "schema_version": 1,
            "feature_revision": PAPER_LOGIC_FEATURE_REVISION,
            "project_id": revision["project_id"],
            "paper_id": revision["paper_id"],
            "graph_kind": revision["graph_kind"],
            "domain_profile": revision["domain_profile"],
            "revision_ids": revision_ids,
            "base_snapshot_id": revision["base_snapshot_id"],
            "supersedes_snapshot_id": revision["supersedes_snapshot_id"],
            "transaction_id": transaction_id,
            "review_ids": transaction["review_ids"],
            "source_artifacts": source_artifacts,
            "node_entries": node_entries,
            "edge_entries": edge_entries,
            "local_id_maps": local_maps,
            "planes": sorted({node["plane"] for node in nodes.values()}),
            "readiness": readiness,
            "current_audit_node_ids": current_audit,
            "inactive_audit_node_ids": inactive_audit,
            "truth_effect": "none",
        }
        snapshot_id = "pls-" + sha256_json(snapshot_body)
        snapshot = {**snapshot_body, "snapshot_id": snapshot_id}
        self._write_json_once(
            self.transactions_dir / f"{transaction_id}.json",
            transaction,
        )
        self._write_snapshot_once(
            snapshot,
            nodes=nodes,
            edges=edges,
        )
        result = {
            "snapshot_id": snapshot_id,
            "revision_id": revision_id,
            "readiness": readiness,
            "status": "frozen_nontruth",
            "truth_effect": "none",
        }
        if self.owner is not None:
            result["evidence_sync"] = self.owner.evidence().paper_snapshot_frozen(
                snapshot_id,
                actor=actor,
            )
        return result

    def snapshot_manifest(self, snapshot_id: str) -> dict[str, Any]:
        directory = self._snapshot_path(snapshot_id)
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError("paper snapshot is missing or unsafe")
        expected_names = {"manifest.json", "nodes.jsonl", "edges.jsonl"}
        actual_names = {
            path.name
            for path in directory.iterdir()
            if path.is_file() and not path.is_symlink()
        }
        if actual_names != expected_names:
            raise ValueError("paper snapshot file set is invalid")
        manifest = self._read_json(directory / "manifest.json")
        require_exact_keys(
            manifest,
            required=_SNAPSHOT_FIELDS,
            label="paper snapshot manifest",
        )
        if (
            manifest.get("schema_version") != 1
            or manifest.get("feature_revision")
            != PAPER_LOGIC_FEATURE_REVISION
            or manifest.get("project_id") != self._feature()["project_id"]
            or manifest.get("truth_effect") != "none"
        ):
            raise ValueError("paper snapshot manifest binding mismatch")
        semantic = {
            key: value
            for key, value in manifest.items()
            if key != "snapshot_id"
        }
        if manifest.get("snapshot_id") != "pls-" + sha256_json(semantic):
            raise ValueError("paper snapshot id/hash mismatch")
        if manifest["snapshot_id"] != snapshot_id:
            raise ValueError("paper snapshot directory/id mismatch")
        for entry in manifest["node_entries"]:
            self._validate_entry(entry, "paper snapshot node entry")
        for entry in manifest["edge_entries"]:
            self._validate_entry(entry, "paper snapshot edge entry")
        if manifest["truth_effect"] != "none":
            raise ValueError("paper snapshot truth_effect must be none")
        return manifest

    @staticmethod
    def _read_jsonl_objects(
        path: Path,
        *,
        kind: str,
    ) -> dict[str, dict[str, Any]]:
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"paper snapshot {kind} JSONL is unsafe")
        result: dict[str, dict[str, Any]] = {}
        for number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            if not line:
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(
                    f"paper snapshot {kind} line {number} is not an object"
                )
            if kind == "node":
                validate_paper_node(payload)
            else:
                validate_paper_edge(payload)
            object_id = payload["object_id"]
            if object_id in result:
                raise ValueError(
                    f"paper snapshot duplicates {kind} {object_id}"
                )
            result[object_id] = payload
        return result

    def snapshot_objects(
        self, snapshot_id: str
    ) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
        manifest = self.snapshot_manifest(snapshot_id)
        directory = self._snapshot_path(snapshot_id)
        nodes = self._read_jsonl_objects(directory / "nodes.jsonl", kind="node")
        edges = self._read_jsonl_objects(directory / "edges.jsonl", kind="edge")
        expected_nodes = {
            item["object_id"]: item["sha256"]
            for item in manifest["node_entries"]
        }
        expected_edges = {
            item["object_id"]: item["sha256"]
            for item in manifest["edge_entries"]
        }
        if set(nodes) != set(expected_nodes) or set(edges) != set(expected_edges):
            raise ValueError("paper snapshot object inventory mismatch")
        for object_id, node in nodes.items():
            if sha256_json(node) != expected_nodes[object_id]:
                raise ValueError(
                    f"paper snapshot node hash mismatch: {object_id}"
                )
        for object_id, edge in edges.items():
            if sha256_json(edge) != expected_edges[object_id]:
                raise ValueError(
                    f"paper snapshot edge hash mismatch: {object_id}"
                )
            if edge["source_id"] not in nodes or edge["target_id"] not in nodes:
                raise ValueError(
                    f"paper snapshot edge has dangling endpoint: {object_id}"
                )
        return nodes, edges

    def show(
        self,
        object_id: str,
        *,
        snapshot_id: str = "",
    ) -> dict[str, Any]:
        if PAPER_REVISION_ID_RE.fullmatch(object_id):
            return self.status(object_id)
        if PAPER_SNAPSHOT_ID_RE.fullmatch(object_id):
            return self.snapshot_manifest(object_id)
        validate_paper_object_id(object_id)
        if snapshot_id:
            nodes, edges = self.snapshot_objects(snapshot_id)
            if object_id in nodes:
                return nodes[object_id]
            if object_id in edges:
                return edges[object_id]
            raise KeyError(
                f"paper object is absent from snapshot {snapshot_id}: {object_id}"
            )
        for directory in sorted(self.snapshots_dir.glob("pls-*")):
            nodes, edges = self.snapshot_objects(directory.name)
            if object_id in nodes:
                return nodes[object_id]
            if object_id in edges:
                return edges[object_id]
        raise KeyError(f"paper object is not visible in a frozen snapshot: {object_id}")

    @staticmethod
    def _validate_query(query: dict[str, Any]) -> dict[str, Any]:
        require_exact_keys(
            query,
            required={
                "seed_ids",
                "direction",
                "max_hops",
                "node_budget",
                "edge_budget",
            },
            label="paper graph query",
        )
        PaperLogicStore._require_strings(
            query["seed_ids"], "paper graph query seed_ids"
        )
        if query["direction"] not in {"out", "in", "both"}:
            raise ValueError("paper graph query direction is invalid")
        for key in ("max_hops", "node_budget", "edge_budget"):
            value = query[key]
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"paper graph query {key} must be nonnegative")
        if query["node_budget"] < 1:
            raise ValueError("paper graph query node_budget must be positive")
        return query

    def query(
        self,
        snapshot_id: str,
        *,
        view: str,
        query: dict[str, Any],
    ) -> dict[str, Any]:
        manifest = self.snapshot_manifest(snapshot_id)
        nodes, edges = self.snapshot_objects(snapshot_id)
        if view not in {
            "source",
            "reconstruction",
            "audit",
            "current_audit",
            "combined",
        }:
            raise ValueError("paper graph query view is invalid")
        self._validate_query(query)
        allowed_planes = {
            "source": {"paper_source"},
            "reconstruction": {"paper_reconstruction"},
            "audit": {"paper_audit"},
            "current_audit": {"paper_audit"},
            "combined": set(PAPER_PLANES),
        }[view]
        allowed_nodes = {
            object_id: node
            for object_id, node in nodes.items()
            if node["plane"] in allowed_planes
        }
        if view == "current_audit":
            current = set(manifest["current_audit_node_ids"])
            allowed_nodes = {
                object_id: node
                for object_id, node in allowed_nodes.items()
                if object_id in current
            }
        allowed_edges = {
            object_id: edge
            for object_id, edge in edges.items()
            if edge["source_id"] in allowed_nodes
            and edge["target_id"] in allowed_nodes
        }
        seeds = query["seed_ids"] or sorted(allowed_nodes)
        missing = set(seeds).difference(allowed_nodes)
        if missing:
            raise ValueError(
                "paper graph query has unavailable seeds: "
                + ", ".join(sorted(missing))
            )
        incident: dict[str, list[tuple[str, str]]] = {}
        for edge_id, edge in sorted(allowed_edges.items()):
            if query["direction"] in {"out", "both"}:
                incident.setdefault(edge["source_id"], []).append(
                    (edge_id, edge["target_id"])
                )
            if query["direction"] in {"in", "both"}:
                incident.setdefault(edge["target_id"], []).append(
                    (edge_id, edge["source_id"])
                )
        selected_nodes: list[str] = []
        selected_edges: list[str] = []
        node_seen: set[str] = set()
        edge_seen: set[str] = set()
        omitted_nodes: set[str] = set()
        omitted_edges: set[str] = set()
        queue: deque[tuple[int, str]] = deque(
            (0, seed) for seed in sorted(seeds)
        )
        while queue:
            hop, node_id = queue.popleft()
            if node_id not in node_seen:
                if len(selected_nodes) >= query["node_budget"]:
                    omitted_nodes.add(node_id)
                    continue
                node_seen.add(node_id)
                selected_nodes.append(node_id)
            if hop >= query["max_hops"]:
                continue
            for edge_id, neighbor in sorted(incident.get(node_id, [])):
                if edge_id not in edge_seen:
                    if len(selected_edges) >= query["edge_budget"]:
                        omitted_edges.add(edge_id)
                        continue
                    edge_seen.add(edge_id)
                    selected_edges.append(edge_id)
                if neighbor not in node_seen:
                    queue.append((hop + 1, neighbor))
        return {
            "snapshot_id": snapshot_id,
            "view": view,
            "query_sha256": sha256_json(query),
            "nodes": [allowed_nodes[item] for item in sorted(selected_nodes)],
            "edges": [allowed_edges[item] for item in sorted(selected_edges)],
            "omission": {
                "node_budget_hit": bool(omitted_nodes),
                "edge_budget_hit": bool(omitted_edges),
                "omitted_node_ids": sorted(omitted_nodes),
                "omitted_edge_ids": sorted(omitted_edges),
            },
            "truth_effect": "none",
        }

    def status(self, revision_id: str = "") -> dict[str, Any]:
        if revision_id:
            revisions = [self.revision(revision_id)]
        else:
            revisions = [
                self.revision(path.stem)
                for path in sorted(self.revisions_dir.glob("plr-*.json"))
            ]
        snapshots = [
            self.snapshot_manifest(path.name)
            for path in sorted(self.snapshots_dir.glob("pls-*"))
            if path.is_dir() and not path.is_symlink()
        ]
        superseded = {
            manifest["supersedes_snapshot_id"]
            for manifest in snapshots
            if manifest["supersedes_snapshot_id"]
        }
        results: list[dict[str, Any]] = []
        for revision in revisions:
            reviews = self.reviews_for_revision(revision["revision_id"])
            frozen = [
                manifest["snapshot_id"]
                for manifest in snapshots
                if revision["revision_id"] in manifest["revision_ids"]
            ]
            if any(item["verdict"] == "reject" for item in reviews):
                state = "rejected_requires_new_revision"
            elif frozen:
                state = "frozen"
            elif all(
                any(
                    item["profile"] == profile
                    and item["verdict"] == "correct"
                    for item in reviews
                )
                for profile in revision["required_review_profiles"]
            ):
                state = "reviewed_pending_freeze"
            else:
                state = "staged_pending_review"
            results.append(
                {
                    "revision_id": revision["revision_id"],
                    "paper_id": revision["paper_id"],
                    "graph_kind": revision["graph_kind"],
                    "domain_profile": revision["domain_profile"],
                    "state": state,
                    "reviews": [
                        {
                            "review_id": item["review_id"],
                            "profile": item["profile"],
                            "verdict": item["verdict"],
                        }
                        for item in reviews
                    ],
                    "snapshot_ids": frozen,
                }
            )
        return {
            "feature_revision": PAPER_LOGIC_FEATURE_REVISION,
            "revisions": results,
            "current_snapshot_ids": sorted(
                manifest["snapshot_id"]
                for manifest in snapshots
                if manifest["snapshot_id"] not in superseded
            ),
            "superseded_snapshot_ids": sorted(superseded),
            "truth_effect": "none",
        }

    def link_exploration(
        self,
        payload: dict[str, Any],
        *,
        actor: str,
        blackboard: Any,
    ) -> dict[str, Any]:
        self._feature()
        require_exact_keys(
            payload,
            required={
                "paper_snapshot_id",
                "paper_object_id",
                "blackboard_snapshot_id",
                "blackboard_object_id",
                "relation",
                "rationale",
            },
            label="paper/blackboard bridge",
        )
        paper_snapshot_id = validate_paper_snapshot_id(
            require_string(payload, "paper_snapshot_id")
        )
        paper_object_id = validate_paper_object_id(
            require_string(payload, "paper_object_id")
        )
        paper_nodes, paper_edges = self.snapshot_objects(paper_snapshot_id)
        paper_object = paper_nodes.get(paper_object_id) or paper_edges.get(
            paper_object_id
        )
        if paper_object is None:
            raise ValueError("paper bridge object is absent from its snapshot")
        blackboard_snapshot_id = require_string(
            payload, "blackboard_snapshot_id"
        )
        blackboard_nodes, blackboard_edges = blackboard.snapshot_objects(
            blackboard_snapshot_id
        )
        blackboard_object_id = require_string(
            payload, "blackboard_object_id"
        )
        blackboard_object = blackboard_nodes.get(
            blackboard_object_id
        ) or blackboard_edges.get(blackboard_object_id)
        if blackboard_object is None:
            raise ValueError(
                "paper bridge blackboard object is absent from its snapshot"
            )
        relation = require_string(payload, "relation")
        if relation not in BRIDGE_RELATIONS:
            raise ValueError("paper/blackboard bridge relation is invalid")
        rationale = require_string(payload, "rationale")
        semantic = {
            "schema_version": 1,
            "feature_revision": PAPER_LOGIC_FEATURE_REVISION,
            "project_id": self._feature()["project_id"],
            "paper_object": {
                "store": "paper_logic",
                "plane": paper_object["plane"],
                "object_id": paper_object_id,
                "snapshot_id": paper_snapshot_id,
                "object_sha256": sha256_json(paper_object),
            },
            "exploration_object": {
                "store": "blackboard",
                "plane": "agent_exploration",
                "object_id": blackboard_object_id,
                "snapshot_id": blackboard_snapshot_id,
                "object_sha256": sha256_json(blackboard_object),
            },
            "relation": relation,
            "rationale": rationale,
            "actor": actor,
            "truth_effect": "none",
        }
        bridge_id = "plb-" + sha256_json(semantic)
        bridge = {**semantic, "bridge_id": bridge_id}
        self._write_json_once(
            self.bridges_dir / f"{bridge_id}.json",
            bridge,
        )
        return bridge

    def project_to_blackboard(
        self,
        payload: dict[str, Any],
        *,
        actor: str,
        blackboard: Any,
    ) -> dict[str, Any]:
        """Project an exact frozen paper slice into a blackboard sandbox.

        The mirror is deliberately full-fidelity but remains an exploration
        object. Agents may reason around it; they cannot mutate or promote the
        mirror as authoritative paper or truth state.
        """

        require_exact_keys(
            payload,
            required={
                "paper_snapshot_id",
                "view",
                "query",
                "blackboard_space_id",
                "projection_mode",
                "name",
            },
            label="paper blackboard projection",
        )
        if payload["projection_mode"] != "full_fidelity":
            raise ValueError(
                "paper blackboard projection supports only full_fidelity"
            )
        name = require_string(payload, "name")
        result = self.query(
            require_string(payload, "paper_snapshot_id"),
            view=require_string(payload, "view"),
            query=payload["query"],
        )
        if result["omission"]["node_budget_hit"] or result["omission"][
            "edge_budget_hit"
        ]:
            raise ValueError(
                "paper blackboard projection refuses an omitted graph slice"
            )
        space_id = require_string(payload, "blackboard_space_id")
        space = blackboard.show(space_id)
        if space["node_type"] != "space":
            raise ValueError("paper projection target must be a blackboard space")
        from .blackboard import make_edge as make_blackboard_edge
        from .blackboard import make_node as make_blackboard_node

        source_to_mirror: dict[str, str] = {}
        mirror_nodes: list[dict[str, Any]] = []
        placement_edges: list[dict[str, Any]] = []
        creator = f"paper-projection:{actor}"
        for paper_node in result["nodes"]:
            mirror = make_blackboard_node(
                node_type="paper_logic_mirror",
                logical_key=(
                    f"paper-mirror:{result['snapshot_id']}:"
                    f"{paper_node['object_id']}"
                ),
                payload={
                    "mirror_schema_version": 1,
                    "source_store": "paper_logic",
                    "source_snapshot_id": result["snapshot_id"],
                    "source_object_id": paper_node["object_id"],
                    "source_object_sha256": sha256_json(paper_node),
                    "source_plane": paper_node["plane"],
                    "source_object_type": paper_node["object_type"],
                    "projection_mode": "full_fidelity",
                    "paper_object": paper_node,
                    "truth_boundary": (
                        "Read-only paper snapshot mirror in agent_exploration; "
                        "not authoritative paper state and not a fact."
                    ),
                },
                created_by_assignment_id=creator,
                truth_status="exploration",
                source_refs=[
                    f"paper_logic:{result['snapshot_id']}:"
                    f"{paper_node['object_id']}"
                ],
            )
            source_to_mirror[paper_node["object_id"]] = mirror["node_id"]
            mirror_nodes.append(mirror)
            placement_edges.append(
                make_blackboard_edge(
                    edge_type="placed_in",
                    source_node_id=mirror["node_id"],
                    target_node_id=space_id,
                    payload={"region": f"paper-sandbox:{name}"},
                    created_by_assignment_id=creator,
                )
            )
        mirror_edges: list[dict[str, Any]] = []
        for paper_edge in result["edges"]:
            source = source_to_mirror.get(paper_edge["source_id"])
            target = source_to_mirror.get(paper_edge["target_id"])
            if source is None or target is None:
                continue
            mirror_edges.append(
                make_blackboard_edge(
                    edge_type="paper_relation_mirror",
                    source_node_id=source,
                    target_node_id=target,
                    payload={
                        "mirror_schema_version": 1,
                        "source_snapshot_id": result["snapshot_id"],
                        "source_edge_id": paper_edge["object_id"],
                        "source_edge_sha256": sha256_json(paper_edge),
                        "source_plane": paper_edge["plane"],
                        "source_relation_type": paper_edge["relation_type"],
                        "paper_edge": paper_edge,
                        "truth_effect": "none",
                    },
                    created_by_assignment_id=creator,
                )
            )
        receipt = blackboard.add_paper_projection(
            nodes=mirror_nodes,
            edges=[*placement_edges, *mirror_edges],
            actor=actor,
            paper_snapshot_id=result["snapshot_id"],
        )
        semantic = {
            "schema_version": 1,
            "feature_revision": PAPER_LOGIC_FEATURE_REVISION,
            "project_id": self._feature()["project_id"],
            "paper_snapshot_id": result["snapshot_id"],
            "paper_query_sha256": result["query_sha256"],
            "paper_view": result["view"],
            "projection_mode": "full_fidelity",
            "name": name,
            "blackboard_space_id": space_id,
            "blackboard_transaction_id": receipt["transaction_id"],
            "node_map": dict(sorted(source_to_mirror.items())),
            "mirrored_edge_ids": sorted(
                edge["edge_id"] for edge in mirror_edges
            ),
            "actor": actor,
            "truth_effect": "none",
        }
        projection_id = "plp-" + sha256_json(semantic)
        projection = {**semantic, "projection_id": projection_id}
        self._write_json_once(
            self.projections_dir / f"{projection_id}.json",
            projection,
        )
        blackboard.reindex(apply=True, actor=actor)
        return projection

    def _validate_bridge(self, payload: dict[str, Any], blackboard: Any) -> None:
        require_exact_keys(
            payload,
            required={
                "schema_version",
                "feature_revision",
                "project_id",
                "paper_object",
                "exploration_object",
                "relation",
                "rationale",
                "actor",
                "truth_effect",
                "bridge_id",
            },
            label="paper/blackboard bridge",
        )
        semantic = {
            key: value
            for key, value in payload.items()
            if key != "bridge_id"
        }
        if payload["bridge_id"] != "plb-" + sha256_json(semantic):
            raise ValueError("paper/blackboard bridge id/hash mismatch")
        if (
            payload["feature_revision"] != PAPER_LOGIC_FEATURE_REVISION
            or payload["project_id"] != self._feature()["project_id"]
            or payload["relation"] not in BRIDGE_RELATIONS
            or payload["truth_effect"] != "none"
        ):
            raise ValueError("paper/blackboard bridge binding mismatch")
        paper = payload["paper_object"]
        exploration = payload["exploration_object"]
        if not isinstance(paper, dict) or not isinstance(exploration, dict):
            raise ValueError("paper/blackboard bridge endpoints must be objects")
        paper_nodes, paper_edges = self.snapshot_objects(
            paper["snapshot_id"]
        )
        paper_object = paper_nodes.get(paper["object_id"]) or paper_edges.get(
            paper["object_id"]
        )
        if (
            paper_object is None
            or sha256_json(paper_object) != paper["object_sha256"]
            or paper["plane"] != paper_object["plane"]
        ):
            raise ValueError("paper/blackboard bridge paper endpoint mismatch")
        bb_nodes, bb_edges = blackboard.snapshot_objects(
            exploration["snapshot_id"]
        )
        bb_object = bb_nodes.get(exploration["object_id"]) or bb_edges.get(
            exploration["object_id"]
        )
        if (
            bb_object is None
            or sha256_json(bb_object) != exploration["object_sha256"]
            or exploration.get("plane") != "agent_exploration"
        ):
            raise ValueError(
                "paper/blackboard bridge exploration endpoint mismatch"
            )

    def audit(self, *, blackboard: Any | None = None) -> dict[str, Any]:
        errors: list[str] = []
        warnings: list[str] = []
        if not self.root.exists():
            return {
                "present": False,
                "ok": True,
                "errors": [],
                "warnings": [],
                "source_nodes": 0,
                "reconstruction_nodes": 0,
                "audit_nodes": 0,
                "snapshots": 0,
                "bridges": 0,
                "projections": 0,
            }
        if not self.feature_path.exists():
            entries = list(self.root.iterdir())
            if entries:
                warnings.append(
                    "unmanaged paper_logic directory has no feature manifest"
                )
            return {
                "present": False,
                "ok": True,
                "errors": [],
                "warnings": warnings,
                "source_nodes": 0,
                "reconstruction_nodes": 0,
                "audit_nodes": 0,
                "snapshots": 0,
                "bridges": 0,
                "projections": 0,
            }
        try:
            self._feature()
        except Exception as exc:
            return {
                "present": True,
                "ok": False,
                "errors": [f"feature manifest: {exc}"],
                "warnings": [],
                "source_nodes": 0,
                "reconstruction_nodes": 0,
                "audit_nodes": 0,
                "snapshots": 0,
                "bridges": 0,
                "projections": 0,
            }
        revisions: dict[str, dict[str, Any]] = {}
        referenced_nodes: set[str] = set()
        referenced_edges: set[str] = set()
        for path in sorted(self.revisions_dir.glob("*.json")):
            try:
                revision = self.revision(path.stem)
                revisions[path.stem] = revision
                nodes, edges = self._revision_objects(revision)
                referenced_nodes.update(nodes)
                referenced_edges.update(edges)
                artifact = self.project_root / revision["artifact_relpath"]
                if artifact.is_symlink() or not artifact.is_file():
                    raise ValueError("source artifact is missing or unsafe")
                if sha256_bytes(artifact.read_bytes()) != revision["source"][
                    "artifact_sha256"
                ]:
                    raise ValueError("source artifact hash mismatch")
            except Exception as exc:
                errors.append(f"revision {path.name}: {exc}")
        reviews: dict[str, dict[str, Any]] = {}
        for path in sorted(self.reviews_dir.glob("*.json")):
            try:
                review = self.review(path.stem)
                reviews[path.stem] = review
                if review["revision_id"] not in revisions:
                    raise ValueError("review references an unknown revision")
            except Exception as exc:
                errors.append(f"review {path.name}: {exc}")
        transactions: dict[str, dict[str, Any]] = {}
        for path in sorted(self.transactions_dir.glob("*.json")):
            try:
                transaction = self._read_json(path)
                expected = "plt-" + sha256_json(
                    {
                        key: value
                        for key, value in transaction.items()
                        if key != "transaction_id"
                    }
                )
                if path.stem != expected or transaction.get(
                    "transaction_id"
                ) != expected:
                    raise ValueError("transaction id/hash mismatch")
                if transaction.get("revision_id") not in revisions:
                    raise ValueError("transaction references an unknown revision")
                if any(
                    review_id not in reviews
                    for review_id in transaction.get("review_ids", [])
                ):
                    raise ValueError("transaction references an unknown review")
                transactions[path.stem] = transaction
            except Exception as exc:
                errors.append(f"transaction {path.name}: {exc}")
        snapshots: dict[str, dict[str, Any]] = {}
        visible_nodes: dict[str, dict[str, Any]] = {}
        visible_edges: dict[str, dict[str, Any]] = {}
        for directory in sorted(self.snapshots_dir.glob("pls-*")):
            try:
                manifest = self.snapshot_manifest(directory.name)
                nodes, edges = self.snapshot_objects(directory.name)
                if manifest["transaction_id"] not in transactions:
                    raise ValueError("snapshot transaction is missing")
                snapshots[directory.name] = manifest
                visible_nodes.update(nodes)
                visible_edges.update(edges)
            except Exception as exc:
                errors.append(f"snapshot {directory.name}: {exc}")
        used_transactions = {
            item["transaction_id"] for item in snapshots.values()
        }
        pending_transactions = sorted(
            set(transactions).difference(used_transactions)
        )
        if pending_transactions:
            warnings.append(
                "reviewed freeze transactions lack a visible snapshot: "
                + ", ".join(pending_transactions)
            )
        orphan_nodes = sorted(
            path.stem
            for path in self.nodes_dir.glob("*.json")
            if path.stem not in referenced_nodes
        )
        orphan_edges = sorted(
            path.stem
            for path in self.edges_dir.glob("*.json")
            if path.stem not in referenced_edges
        )
        if orphan_nodes or orphan_edges:
            warnings.append(
                f"paper-logic CAS orphans: {len(orphan_nodes)} nodes, "
                f"{len(orphan_edges)} edges"
            )
        superseded = {
            item["supersedes_snapshot_id"]
            for item in snapshots.values()
            if item["supersedes_snapshot_id"]
        }
        for snapshot_id, manifest in snapshots.items():
            if (
                manifest["graph_kind"] == "audit"
                and manifest["base_snapshot_id"] in superseded
                and manifest["base_snapshot_id"]
                != manifest["supersedes_snapshot_id"]
            ):
                warnings.append(
                    f"audit snapshot {snapshot_id} is stale because its base "
                    "paper snapshot was superseded"
                )
        bridge_count = 0
        for path in sorted(self.bridges_dir.glob("*.json")):
            try:
                if blackboard is None:
                    warnings.append(
                        f"bridge {path.stem} not revalidated without blackboard"
                    )
                    continue
                self._validate_bridge(self._read_json(path), blackboard)
                bridge_count += 1
            except Exception as exc:
                errors.append(f"bridge {path.name}: {exc}")
        projection_count = 0
        projected_mirror_nodes: set[str] = set()
        projected_mirror_edges: set[str] = set()
        for path in sorted(self.projections_dir.glob("*.json")):
            try:
                projection = self._read_json(path)
                semantic = {
                    key: value
                    for key, value in projection.items()
                    if key != "projection_id"
                }
                expected = "plp-" + sha256_json(semantic)
                if path.stem != expected or projection.get(
                    "projection_id"
                ) != expected:
                    raise ValueError("projection id/hash mismatch")
                self.snapshot_manifest(projection["paper_snapshot_id"])
                if projection.get("truth_effect") != "none":
                    raise ValueError("projection truth_effect must be none")
                if blackboard is None:
                    warnings.append(
                        f"projection {path.stem} not revalidated without blackboard"
                    )
                else:
                    transaction = blackboard.transaction_receipt(
                        projection["blackboard_transaction_id"]
                    )
                    if (
                        transaction.get("kind") != "paper_logic_projection"
                        or transaction.get("capability")
                        != {
                            "role": "paper_projection",
                            "paper_snapshot_id": projection[
                                "paper_snapshot_id"
                            ],
                        }
                    ):
                        raise ValueError(
                            "projection blackboard transaction binding mismatch"
                        )
                    paper_nodes, paper_edges = self.snapshot_objects(
                        projection["paper_snapshot_id"]
                    )
                    node_map = projection.get("node_map")
                    if not isinstance(node_map, dict) or any(
                        not isinstance(source_id, str)
                        or not isinstance(mirror_id, str)
                        for source_id, mirror_id in node_map.items()
                    ):
                        raise ValueError("projection node_map is invalid")
                    if set(node_map.values()) != set(
                        transaction.get("node_ids", [])
                    ):
                        raise ValueError(
                            "projection node_map/transaction inventory mismatch"
                        )
                    for source_id, mirror_id in node_map.items():
                        source_node = paper_nodes.get(source_id)
                        if source_node is None:
                            raise ValueError(
                                "projection maps an absent paper node"
                            )
                        mirror = blackboard.show(mirror_id)
                        if (
                            mirror.get("node_type") != "paper_logic_mirror"
                            or mirror["payload"].get("source_snapshot_id")
                            != projection["paper_snapshot_id"]
                            or mirror["payload"].get("source_object_id")
                            != source_id
                            or mirror["payload"].get("source_object_sha256")
                            != sha256_json(source_node)
                        ):
                            raise ValueError(
                                "projection mirror/source binding mismatch"
                            )
                        projected_mirror_nodes.add(mirror_id)
                    mirrored_edges = projection.get("mirrored_edge_ids")
                    if not isinstance(mirrored_edges, list) or any(
                        not isinstance(item, str) for item in mirrored_edges
                    ):
                        raise ValueError(
                            "projection mirrored_edge_ids is invalid"
                        )
                    if not set(mirrored_edges).issubset(
                        set(transaction.get("edge_ids", []))
                    ):
                        raise ValueError(
                            "projection edge inventory is outside transaction"
                        )
                    for mirror_edge_id in mirrored_edges:
                        mirror_edge = blackboard.show(mirror_edge_id)
                        source_edge_id = mirror_edge["payload"].get(
                            "source_edge_id"
                        )
                        source_edge = paper_edges.get(str(source_edge_id))
                        if (
                            mirror_edge.get("edge_type")
                            != "paper_relation_mirror"
                            or source_edge is None
                            or mirror_edge["payload"].get(
                                "source_edge_sha256"
                            )
                            != sha256_json(source_edge)
                        ):
                            raise ValueError(
                                "projection relation mirror binding mismatch"
                            )
                        projected_mirror_edges.add(mirror_edge_id)
                projection_count += 1
            except Exception as exc:
                errors.append(f"projection {path.name}: {exc}")
        if blackboard is not None:
            try:
                visible_mirror_nodes = {
                    node_id
                    for node_id, node in blackboard.nodes().items()
                    if node.get("node_type") == "paper_logic_mirror"
                }
                visible_mirror_edges = {
                    edge_id
                    for edge_id, edge in blackboard.edges().items()
                    if edge.get("edge_type") == "paper_relation_mirror"
                }
                unbound_nodes = sorted(
                    visible_mirror_nodes.difference(projected_mirror_nodes)
                )
                unbound_edges = sorted(
                    visible_mirror_edges.difference(projected_mirror_edges)
                )
                if unbound_nodes or unbound_edges:
                    errors.append(
                        "blackboard contains paper mirrors without exact "
                        "Paper Logic projection receipts: "
                        f"nodes={unbound_nodes} edges={unbound_edges}"
                    )
            except Exception as exc:
                errors.append(f"paper mirror inventory audit: {exc}")
        plane_counts = {
            plane: sum(
                node["plane"] == plane for node in visible_nodes.values()
            )
            for plane in PAPER_PLANES
        }
        return {
            "present": True,
            "ok": not errors,
            "errors": errors,
            "warnings": warnings,
            "source_nodes": plane_counts["paper_source"],
            "reconstruction_nodes": plane_counts[
                "paper_reconstruction"
            ],
            "audit_nodes": plane_counts["paper_audit"],
            "snapshots": len(snapshots),
            "bridges": bridge_count,
            "projections": projection_count,
            "current_snapshot_ids": sorted(set(snapshots).difference(superseded)),
            "superseded_snapshot_ids": sorted(superseded),
        }

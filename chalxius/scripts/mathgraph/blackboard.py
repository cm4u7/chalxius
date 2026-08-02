from __future__ import annotations

import json
import os
import tempfile
from collections import deque
from pathlib import Path
from typing import Any, Iterable

from .contracts import (
    BB_EDGE_ID_RE,
    BB_NODE_ID_RE,
    BB_SNAPSHOT_ID_RE,
    POLICY_REVISION_V4,
    SHA256_RE,
    canonical_json_bytes,
    require_exact_keys,
    require_string,
    sha256_bytes,
    sha256_json,
    validate_bb_edge_id,
    validate_bb_node_id,
    validate_bb_snapshot_id,
)
from .protocol import validate_ingestion_receipt_v4, validate_task_card


TRUTH_STATUSES = {
    "exploration",
    "supported_evidence",
    "challenged",
    "blocked",
}
CORE_NODE_TYPES = {
    "space": ("unique_conflict", "space"),
    "conjecture": ("unique_conflict", "conjecture_candidate"),
    "formula": ("unique_conflict", "formula_candidate"),
    "definition": ("unique_conflict", "definition_candidate"),
    "obligation": ("unique_conflict", "obligation_candidate"),
    "obstacle": ("multi_value", "obstacle"),
    "experiment": ("multi_value", "experiment"),
    "computation_result": ("multi_value", "computation_evidence"),
    "source_locator": ("multi_value", "source_locator"),
    "intuition": ("multi_value", "narrative_only"),
    "note": ("multi_value", "narrative_only"),
    "conflict": ("multi_value", "conflict"),
    "mechanism": ("multi_value", "mechanism_candidate"),
    "prediction": ("unique_conflict", "prediction_candidate"),
    "fact_interface_mirror": ("unique_conflict", "display_only"),
    "paper_logic_mirror": ("unique_conflict", "paper_logic_mirror"),
    "type_registry": ("unique_conflict", "registry"),
}
CORE_EDGE_TYPES = {
    "placed_in": ("forbid", "placement"),
    "subspace_of": ("forbid", "space_hierarchy"),
    "overlaps_with": ("allow", "space_relation"),
    "suggests_proof": ("allow", "exploration_only"),
    "suggests_refutation": ("allow", "exploration_only"),
    "supports_candidate": ("allow", "exploration_only"),
    "challenges": ("allow", "exploration_only"),
    "refines": ("allow", "exploration_only"),
    "generalizes": ("allow", "exploration_only"),
    "specializes": ("allow", "exploration_only"),
    "analogous_to": ("allow", "exploration_only"),
    "depends_on_experiment": ("allow", "exploration_only"),
    "motivates": ("allow", "exploration_only"),
    "blocks": ("allow", "exploration_only"),
    "resolves": ("allow", "exploration_only"),
    "convention_variant_of": ("allow", "provenance_only"),
    "source_for": ("allow", "provenance_only"),
    "derived_from": ("forbid", "provenance_only"),
    "duplicates": ("allow", "projection"),
    "supersedes": ("forbid", "projection"),
    "closes": ("allow", "projection"),
    "retracts_placement": ("allow", "projection"),
    "explains_candidate": ("allow", "interpretation"),
    "predicts": ("allow", "interpretation"),
    "fails_on": ("allow", "interpretation"),
    "paper_relation_mirror": ("allow", "paper_logic_mirror"),
}
FORBIDDEN_TRUTH_EDGE_TYPES = {"proves", "refutes"}
PAPER_PROJECTION_NODE_TYPES = frozenset({"paper_logic_mirror"})
PAPER_PROJECTION_EDGE_TYPES = frozenset({"paper_relation_mirror"})
NODE_DEACTIVATING_EDGE_TYPES = frozenset({"supersedes", "closes"})
PROJECTION_CONTROL_EDGE_TYPES = frozenset(
    {*NODE_DEACTIVATING_EDGE_TYPES, "retracts_placement"}
)

_NODE_FIELDS = {
    "schema_version",
    "policy_revision",
    "node_id",
    "node_type",
    "type_version",
    "logical_key",
    "payload",
    "truth_status",
    "convention_profile_ids",
    "source_refs",
    "created_by_assignment_id",
}
_EDGE_FIELDS = {
    "schema_version",
    "policy_revision",
    "edge_id",
    "edge_type",
    "type_version",
    "source_node_id",
    "target_node_id",
    "payload",
    "created_by_assignment_id",
}


def _canonical_id(prefix: str, payload: dict[str, Any], id_key: str) -> str:
    body = {key: value for key, value in payload.items() if key != id_key}
    return prefix + sha256_json(body)


def _is_namespaced_custom_type(name: str) -> bool:
    namespace, separator, local_name = name.partition(":")
    return (
        separator == ":"
        and namespace.startswith("x-")
        and len(namespace) > 2
        and bool(local_name)
        and not any(character.isspace() for character in name)
    )


def make_node(
    *,
    node_type: str,
    logical_key: str,
    payload: dict[str, Any],
    created_by_assignment_id: str,
    truth_status: str = "exploration",
    convention_profile_ids: list[str] | None = None,
    source_refs: list[str] | None = None,
    type_version: int = 1,
) -> dict[str, Any]:
    node = {
        "schema_version": 4,
        "policy_revision": POLICY_REVISION_V4,
        "node_type": node_type,
        "type_version": type_version,
        "logical_key": logical_key,
        "payload": payload,
        "truth_status": truth_status,
        "convention_profile_ids": convention_profile_ids or [],
        "source_refs": source_refs or [],
        "created_by_assignment_id": created_by_assignment_id,
    }
    node["node_id"] = _canonical_id("bbn-", node, "node_id")
    return node


def make_edge(
    *,
    edge_type: str,
    source_node_id: str,
    target_node_id: str,
    payload: dict[str, Any],
    created_by_assignment_id: str,
    type_version: int = 1,
) -> dict[str, Any]:
    edge = {
        "schema_version": 4,
        "policy_revision": POLICY_REVISION_V4,
        "edge_type": edge_type,
        "type_version": type_version,
        "source_node_id": source_node_id,
        "target_node_id": target_node_id,
        "payload": payload,
        "created_by_assignment_id": created_by_assignment_id,
    }
    edge["edge_id"] = _canonical_id("bbe-", edge, "edge_id")
    return edge


class BlackboardStore:
    """Project-local content-addressed exploration graph.

    CAS bytes are staged first. A transaction receipt is the sole visibility
    marker, so a crash before that marker leaves only auditable orphans.
    """

    def __init__(self, project_root: Path | str) -> None:
        self.project_root = Path(project_root).resolve()
        self.root = self.project_root / "blackboard"
        self.nodes_dir = self.root / "nodes" / "by-hash"
        self.edges_dir = self.root / "edges" / "by-hash"
        self.node_registry_path = self.root / "registries" / "node-types.jsonl"
        self.edge_registry_path = self.root / "registries" / "edge-types.jsonl"
        self.events_path = self.root / "events.jsonl"
        self.snapshots_dir = self.root / "snapshots" / "by-hash"
        self.transactions_dir = self.root / "transactions" / "by-hash"
        self.indices_dir = self.root / "indices"
        self.index_path = self.indices_dir / "index.json"

    @staticmethod
    def _write_atomic(path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except BaseException:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise

    @staticmethod
    def _write_once(path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            raise ValueError(f"refusing to write through symlink: {path}")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            fd = os.open(path, flags, 0o600)
        except FileExistsError:
            if not path.is_file() or path.is_symlink() or path.read_bytes() != payload:
                raise ValueError(f"immutable blackboard collision at {path}")
            return
        try:
            with os.fdopen(fd, "wb") as handle:
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
        cls._write_once(
            path,
            json.dumps(
                payload, ensure_ascii=False, indent=2, sort_keys=True
            ).encode("utf-8")
            + b"\n",
        )

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"expected one JSON object in {path}")
        return payload

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        result: list[dict[str, Any]] = []
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"non-object registry/event at {path}:{number}")
            result.append(payload)
        return result

    @staticmethod
    def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def initialize(self, *, actor: str = "operator") -> None:
        for path in (
            self.nodes_dir,
            self.edges_dir,
            self.snapshots_dir,
            self.transactions_dir,
            self.indices_dir,
            self.node_registry_path.parent,
        ):
            path.mkdir(parents=True, exist_ok=True)
        for name, (policy, semantics) in sorted(CORE_NODE_TYPES.items()):
            self.register_type(
                kind="node",
                definition={
                    "name": name,
                    "type_version": 1,
                    "logical_key_policy": policy,
                    "automation_semantics": semantics,
                },
                actor=actor,
            )
        for name, (cycle_policy, semantics) in sorted(CORE_EDGE_TYPES.items()):
            self.register_type(
                kind="edge",
                definition={
                    "name": name,
                    "type_version": 1,
                    "allowed_source_types": ["*"],
                    "allowed_target_types": ["*"],
                    "allow_self_edge": False,
                    "cycle_policy": cycle_policy,
                    "automation_semantics": semantics,
                },
                actor=actor,
            )

    def ensure_paper_projection_types(self, *, actor: str) -> None:
        """Register the reserved mirror types in an existing v4 project.

        Projects initialized before the Paper Logic feature do not yet contain
        these additive registry entries. Registration is idempotent and does
        not grant the generic or worker write paths permission to create
        mirrors.
        """

        policy, semantics = CORE_NODE_TYPES["paper_logic_mirror"]
        self.register_type(
            kind="node",
            definition={
                "name": "paper_logic_mirror",
                "type_version": 1,
                "logical_key_policy": policy,
                "automation_semantics": semantics,
            },
            actor=actor,
        )
        cycle_policy, semantics = CORE_EDGE_TYPES["paper_relation_mirror"]
        self.register_type(
            kind="edge",
            definition={
                "name": "paper_relation_mirror",
                "type_version": 1,
                "allowed_source_types": ["*"],
                "allowed_target_types": ["*"],
                "allow_self_edge": False,
                "cycle_policy": cycle_policy,
                "automation_semantics": semantics,
            },
            actor=actor,
        )

    def register_type(
        self,
        *,
        kind: str,
        definition: dict[str, Any],
        actor: str,
    ) -> str:
        if kind not in {"node", "edge"}:
            raise ValueError("blackboard registry kind must be node or edge")
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError("blackboard registry actor must be nonempty")
        name = require_string(definition, "name")
        version = definition.get("type_version")
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise ValueError("type_version must be a positive integer")
        if name in FORBIDDEN_TRUTH_EDGE_TYPES:
            raise ValueError("blackboard cannot register truth-bearing proves/refutes")
        if name not in (CORE_NODE_TYPES if kind == "node" else CORE_EDGE_TYPES):
            if not _is_namespaced_custom_type(name):
                raise ValueError("custom blackboard types must be namespaced x-<ns>:<name>")
        if kind == "node":
            require_exact_keys(
                definition,
                required={
                    "name",
                    "type_version",
                    "logical_key_policy",
                    "automation_semantics",
                },
                label="blackboard node type",
            )
            if definition["logical_key_policy"] not in {
                "unique_conflict",
                "multi_value",
                "ignored",
            }:
                raise ValueError("invalid logical_key_policy")
            require_string(definition, "automation_semantics")
        else:
            require_exact_keys(
                definition,
                required={
                    "name",
                    "type_version",
                    "allowed_source_types",
                    "allowed_target_types",
                    "allow_self_edge",
                    "cycle_policy",
                    "automation_semantics",
                },
                label="blackboard edge type",
            )
            for key in ("allowed_source_types", "allowed_target_types"):
                if not isinstance(definition[key], list) or any(
                    not isinstance(item, str) for item in definition[key]
                ):
                    raise ValueError(f"{key} must be a list of strings")
            if not isinstance(definition["allow_self_edge"], bool):
                raise ValueError("allow_self_edge must be boolean")
            if definition["cycle_policy"] not in {"allow", "forbid"}:
                raise ValueError("cycle_policy must be allow or forbid")
            require_string(definition, "automation_semantics")
        semantic = {
            "schema_version": 4,
            "policy_revision": POLICY_REVISION_V4,
            "kind": kind,
            "definition": definition,
            "actor": actor.strip(),
        }
        registry_id = sha256_json(semantic)
        event = {**semantic, "registry_id": registry_id}
        path = self.node_registry_path if kind == "node" else self.edge_registry_path
        for existing in self._read_jsonl(path):
            old = existing.get("definition")
            if (
                isinstance(old, dict)
                and old.get("name") == name
                and old.get("type_version") == version
            ):
                if old != definition:
                    raise ValueError(
                        f"append-only type redefinition for {kind} {name} v{version}"
                    )
                return str(existing["registry_id"])
        self._append_jsonl(path, event)
        return registry_id

    def _registry(self, kind: str) -> dict[tuple[str, int], dict[str, Any]]:
        path = self.node_registry_path if kind == "node" else self.edge_registry_path
        result: dict[tuple[str, int], dict[str, Any]] = {}
        for event in self._read_jsonl(path):
            definition = event.get("definition")
            if isinstance(definition, dict):
                result[(str(definition.get("name")), int(definition.get("type_version", 0)))] = dict(
                    definition
                )
        return result

    def type_definition(
        self, kind: str, name: str, version: int
    ) -> dict[str, Any] | None:
        return self._registry(kind).get((name, version))

    def effective_type_definition(
        self, kind: str, name: str, version: int
    ) -> dict[str, Any] | None:
        """Return registered semantics or the fail-closed opaque custom fallback."""

        definition = self.type_definition(kind, name, version)
        if definition is not None:
            return definition
        if not _is_namespaced_custom_type(name):
            return None
        if kind == "node":
            return {
                "name": name,
                "type_version": version,
                "logical_key_policy": "ignored",
                "automation_semantics": "opaque",
            }
        if kind == "edge":
            return {
                "name": name,
                "type_version": version,
                "allowed_source_types": ["*"],
                "allowed_target_types": ["*"],
                "allow_self_edge": False,
                "cycle_policy": "allow",
                "automation_semantics": "opaque",
            }
        raise ValueError("blackboard registry kind must be node or edge")

    @staticmethod
    def _validate_projection_edge_payload(edge: dict[str, Any]) -> None:
        edge_type = edge["edge_type"]
        payload = edge["payload"]
        if edge_type in NODE_DEACTIVATING_EDGE_TYPES:
            require_exact_keys(
                payload,
                required=set(),
                label=f"blackboard {edge_type} payload",
            )
        elif edge_type == "retracts_placement":
            require_exact_keys(
                payload,
                required={"placement_edge_id"},
                label="blackboard retracts_placement payload",
            )
            validate_bb_edge_id(require_string(payload, "placement_edge_id"))

    def validate_node(self, node: dict[str, Any]) -> dict[str, Any]:
        require_exact_keys(node, required=_NODE_FIELDS, label="blackboard node")
        if node.get("schema_version") != 4:
            raise ValueError("blackboard node schema_version must be 4")
        if node.get("policy_revision") != POLICY_REVISION_V4:
            raise ValueError("blackboard node policy_revision mismatch")
        node_id = validate_bb_node_id(require_string(node, "node_id"))
        if node_id != _canonical_id("bbn-", node, "node_id"):
            raise ValueError("blackboard node id/hash mismatch")
        node_type = require_string(node, "node_type")
        version = node.get("type_version")
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise ValueError("blackboard node type_version must be positive")
        if node_type not in CORE_NODE_TYPES and not _is_namespaced_custom_type(
            node_type
        ):
            raise ValueError("unregistered core-like blackboard node type")
        if self.effective_type_definition("node", node_type, version) is None:
            raise ValueError(
                f"blackboard node type is not registered: {node_type} v{version}"
            )
        require_string(node, "logical_key")
        if not isinstance(node.get("payload"), dict):
            raise ValueError("blackboard node payload must be an object")
        if node.get("truth_status") not in TRUTH_STATUSES:
            raise ValueError("blackboard node truth_status is invalid")
        if node_type == "paper_logic_mirror":
            if node["truth_status"] != "exploration":
                raise ValueError(
                    "paper-logic blackboard mirror must remain exploration"
                )
            payload = node["payload"]
            require_exact_keys(
                payload,
                required={
                    "mirror_schema_version",
                    "source_store",
                    "source_snapshot_id",
                    "source_object_id",
                    "source_object_sha256",
                    "source_plane",
                    "source_object_type",
                    "projection_mode",
                    "paper_object",
                    "truth_boundary",
                },
                label="paper-logic blackboard mirror payload",
            )
            if (
                payload.get("mirror_schema_version") != 1
                or payload.get("source_store") != "paper_logic"
                or payload.get("projection_mode") != "full_fidelity"
            ):
                raise ValueError(
                    "paper-logic blackboard mirror binding mismatch"
                )
            from .paper_logic_contracts import (
                PAPER_SNAPSHOT_ID_RE,
                validate_paper_node,
            )

            if PAPER_SNAPSHOT_ID_RE.fullmatch(
                require_string(payload, "source_snapshot_id")
            ) is None:
                raise ValueError(
                    "paper-logic mirror snapshot id is invalid"
                )
            source_object = validate_paper_node(payload["paper_object"])
            if (
                payload.get("source_object_id")
                != source_object["object_id"]
                or payload.get("source_object_sha256")
                != sha256_json(source_object)
                or payload.get("source_plane") != source_object["plane"]
                or payload.get("source_object_type")
                != source_object["object_type"]
            ):
                raise ValueError(
                    "paper-logic mirror source object/hash mismatch"
                )
            require_string(payload, "truth_boundary")
        for key in ("convention_profile_ids", "source_refs"):
            if not isinstance(node.get(key), list) or any(
                not isinstance(item, str) for item in node[key]
            ):
                raise ValueError(f"blackboard node {key} must be a list of strings")
        require_string(node, "created_by_assignment_id")
        return node

    def validate_edge(self, edge: dict[str, Any]) -> dict[str, Any]:
        require_exact_keys(edge, required=_EDGE_FIELDS, label="blackboard edge")
        if edge.get("schema_version") != 4:
            raise ValueError("blackboard edge schema_version must be 4")
        if edge.get("policy_revision") != POLICY_REVISION_V4:
            raise ValueError("blackboard edge policy_revision mismatch")
        edge_id = validate_bb_edge_id(require_string(edge, "edge_id"))
        if edge_id != _canonical_id("bbe-", edge, "edge_id"):
            raise ValueError("blackboard edge id/hash mismatch")
        edge_type = require_string(edge, "edge_type")
        if edge_type in FORBIDDEN_TRUTH_EDGE_TYPES:
            raise ValueError("blackboard edges cannot be proves/refutes")
        version = edge.get("type_version")
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise ValueError("blackboard edge type_version must be positive")
        if edge_type not in CORE_EDGE_TYPES and not _is_namespaced_custom_type(
            edge_type
        ):
            raise ValueError("unregistered core-like blackboard edge type")
        if self.effective_type_definition("edge", edge_type, version) is None:
            raise ValueError(
                f"blackboard edge type is not registered: {edge_type} v{version}"
            )
        validate_bb_node_id(require_string(edge, "source_node_id"))
        validate_bb_node_id(require_string(edge, "target_node_id"))
        if not isinstance(edge.get("payload"), dict):
            raise ValueError("blackboard edge payload must be an object")
        if edge_type == "paper_relation_mirror":
            payload = edge["payload"]
            require_exact_keys(
                payload,
                required={
                    "mirror_schema_version",
                    "source_snapshot_id",
                    "source_edge_id",
                    "source_edge_sha256",
                    "source_plane",
                    "source_relation_type",
                    "paper_edge",
                    "truth_effect",
                },
                label="paper-relation blackboard mirror payload",
            )
            if (
                payload.get("mirror_schema_version") != 1
                or payload.get("truth_effect") != "none"
            ):
                raise ValueError(
                    "paper-relation blackboard mirror binding mismatch"
                )
            from .paper_logic_contracts import (
                PAPER_SNAPSHOT_ID_RE,
                validate_paper_edge,
            )

            if PAPER_SNAPSHOT_ID_RE.fullmatch(
                require_string(payload, "source_snapshot_id")
            ) is None:
                raise ValueError(
                    "paper-relation mirror snapshot id is invalid"
                )
            source_edge = validate_paper_edge(payload["paper_edge"])
            if (
                payload.get("source_edge_id")
                != source_edge["object_id"]
                or payload.get("source_edge_sha256")
                != sha256_json(source_edge)
                or payload.get("source_plane") != source_edge["plane"]
                or payload.get("source_relation_type")
                != source_edge["relation_type"]
            ):
                raise ValueError(
                    "paper-relation mirror source edge/hash mismatch"
                )
        self._validate_projection_edge_payload(edge)
        require_string(edge, "created_by_assignment_id")
        return edge

    def _node_path(self, node_id: str) -> Path:
        return self.nodes_dir / f"{validate_bb_node_id(node_id)}.json"

    def _edge_path(self, edge_id: str) -> Path:
        return self.edges_dir / f"{validate_bb_edge_id(edge_id)}.json"

    def _transaction_path(self, transaction_id: str) -> Path:
        if SHA256_RE.fullmatch(transaction_id) is None:
            raise ValueError("transaction id must be a SHA-256")
        return self.transactions_dir / f"{transaction_id}.json"

    def transaction_receipt(self, transaction_id: str) -> dict[str, Any]:
        """Return and validate one immutable blackboard transaction receipt."""

        path = self._transaction_path(transaction_id)
        if path.is_symlink() or not path.is_file():
            raise ValueError(
                f"blackboard transaction is missing or unsafe: {transaction_id}"
            )
        receipt = self._read_json(path)
        semantic = {
            key: value
            for key, value in receipt.items()
            if key != "transaction_id"
        }
        if (
            receipt.get("transaction_id") != transaction_id
            or sha256_json(semantic) != transaction_id
        ):
            raise ValueError("blackboard transaction id/hash mismatch")
        return receipt

    def _receipts(self) -> list[dict[str, Any]]:
        receipts: list[dict[str, Any]] = []
        for path in sorted(self.transactions_dir.glob("*.json")):
            receipt = self._read_json(path)
            if receipt.get("transaction_id") != path.stem:
                raise ValueError(f"blackboard transaction filename/id mismatch: {path}")
            semantic = {
                key: receipt[key]
                for key in (
                    "schema_version",
                    "policy_revision",
                    "kind",
                    "actor",
                    "assignment_id",
                    "base_snapshot_id",
                    "return_sha256",
                    "node_ids",
                    "edge_ids",
                    "capability",
                )
            }
            if sha256_json(semantic) != path.stem:
                raise ValueError(f"blackboard transaction hash mismatch: {path}")
            receipts.append(receipt)
        return receipts

    def _ingestion_markers(self) -> dict[str, dict[str, Any]]:
        markers: dict[str, dict[str, Any]] = {}
        rounds_dir = self.project_root / "rounds"
        for path in sorted(
            rounds_dir.glob("*/returns/*.receipt.json")
        ):
            payload = self._read_json(path)
            if payload.get("schema_version") != 4:
                continue
            validate_ingestion_receipt_v4(payload)
            transaction_id = payload["blackboard_transaction_id"]
            existing = markers.get(transaction_id)
            if existing is not None and existing != payload:
                raise ValueError(
                    "multiple v4 ingestion markers bind one blackboard transaction"
                )
            markers[transaction_id] = payload
        return markers

    def visible_ids(self) -> tuple[set[str], set[str]]:
        nodes: set[str] = set()
        edges: set[str] = set()
        ingestion_markers = self._ingestion_markers()
        for receipt in self._receipts():
            if (
                receipt.get("kind") == "worker_delta_merge"
                and receipt.get("capability", {}).get(
                    "ingestion_marker_required", False
                )
            ):
                marker = ingestion_markers.get(receipt["transaction_id"])
                if marker is None:
                    continue
                if (
                    marker["assignment_id"] != receipt["assignment_id"]
                    or marker["return_sha256"] != receipt["return_sha256"]
                    or marker["blackboard_node_ids"] != receipt["node_ids"]
                    or marker["blackboard_edge_ids"] != receipt["edge_ids"]
                ):
                    raise ValueError(
                        "v4 ingestion marker/blackboard transaction mismatch"
                    )
            nodes.update(receipt.get("node_ids", []))
            edges.update(receipt.get("edge_ids", []))
        return nodes, edges

    def nodes(self) -> dict[str, dict[str, Any]]:
        node_ids, _ = self.visible_ids()
        return {node_id: self.validate_node(self._read_json(self._node_path(node_id))) for node_id in sorted(node_ids)}

    def edges(self) -> dict[str, dict[str, Any]]:
        _, edge_ids = self.visible_ids()
        return {edge_id: self.validate_edge(self._read_json(self._edge_path(edge_id))) for edge_id in sorted(edge_ids)}

    def show(self, object_id: str) -> dict[str, Any]:
        if BB_NODE_ID_RE.fullmatch(object_id):
            if object_id not in self.visible_ids()[0]:
                raise KeyError(f"unknown visible blackboard node: {object_id}")
            return self.validate_node(self._read_json(self._node_path(object_id)))
        if BB_EDGE_ID_RE.fullmatch(object_id):
            if object_id not in self.visible_ids()[1]:
                raise KeyError(f"unknown visible blackboard edge: {object_id}")
            return self.validate_edge(self._read_json(self._edge_path(object_id)))
        raise ValueError("blackboard object id must be a node or edge id")

    def _stage_and_commit(
        self,
        *,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        kind: str,
        actor: str,
        assignment_id: str = "",
        base_snapshot_id: str = "",
        return_sha256: str = "",
        capability: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_nodes = sorted(
            (self.validate_node(dict(node)) for node in nodes),
            key=lambda item: item["node_id"],
        )
        normalized_edges = sorted(
            (self.validate_edge(dict(edge)) for edge in edges),
            key=lambda item: item["edge_id"],
        )
        if len({item["node_id"] for item in normalized_nodes}) != len(normalized_nodes):
            raise ValueError("duplicate node id in blackboard transaction")
        if len({item["edge_id"] for item in normalized_edges}) != len(normalized_edges):
            raise ValueError("duplicate edge id in blackboard transaction")
        semantic = {
            "schema_version": 4,
            "policy_revision": POLICY_REVISION_V4,
            "kind": kind,
            "actor": actor,
            "assignment_id": assignment_id,
            "base_snapshot_id": base_snapshot_id,
            "return_sha256": return_sha256,
            "node_ids": [item["node_id"] for item in normalized_nodes],
            "edge_ids": [item["edge_id"] for item in normalized_edges],
            "capability": capability or {},
        }
        transaction_id = sha256_json(semantic)
        receipt_path = self._transaction_path(transaction_id)
        if receipt_path.exists():
            receipt = self._read_json(receipt_path)
            if receipt.get("transaction_id") != transaction_id:
                raise ValueError("blackboard transaction replay collision")
            return receipt
        for node in normalized_nodes:
            self._write_json_once(self._node_path(node["node_id"]), node)
        for edge in normalized_edges:
            self._write_json_once(self._edge_path(edge["edge_id"]), edge)
        receipt = {**semantic, "transaction_id": transaction_id}
        self._write_json_once(receipt_path, receipt)
        self._append_jsonl(
            self.events_path,
            {
                "schema_version": 4,
                "policy_revision": POLICY_REVISION_V4,
                "event": "transaction_visible",
                "transaction_id": transaction_id,
            },
        )
        return receipt

    @staticmethod
    def _adjacency(
        edges: Iterable[dict[str, Any]], edge_type: str
    ) -> dict[str, set[str]]:
        graph: dict[str, set[str]] = {}
        for edge in edges:
            if edge["edge_type"] != edge_type:
                continue
            graph.setdefault(edge["source_node_id"], set()).add(
                edge["target_node_id"]
            )
        return graph

    @staticmethod
    def _would_cycle(
        edges: Iterable[dict[str, Any]],
        candidate: dict[str, Any],
    ) -> bool:
        graph = BlackboardStore._adjacency(edges, candidate["edge_type"])
        graph.setdefault(candidate["source_node_id"], set()).add(
            candidate["target_node_id"]
        )
        source = candidate["source_node_id"]
        stack = [candidate["target_node_id"]]
        seen: set[str] = set()
        while stack:
            current = stack.pop()
            if current == source:
                return True
            if current in seen:
                continue
            seen.add(current)
            stack.extend(graph.get(current, ()))
        return False

    def _validate_graph_objects(
        self,
        *,
        new_nodes: list[dict[str, Any]],
        new_edges: list[dict[str, Any]],
        allowed_existing_endpoints: set[str] | None = None,
        write_spaces: set[str] | None = None,
        allow_create_space: bool = True,
        allow_paper_projection: bool = False,
    ) -> None:
        visible_nodes = self.nodes()
        visible_edges = self.edges()
        new_node_map = {node["node_id"]: self.validate_node(node) for node in new_nodes}
        all_nodes = {**visible_nodes, **new_node_map}
        allowed_existing_endpoints = allowed_existing_endpoints or set(visible_nodes)
        write_spaces = write_spaces if write_spaces is not None else {
            node_id
            for node_id, node in visible_nodes.items()
            if node["node_type"] == "space"
        }
        pending_edges: list[dict[str, Any]] = []
        if not allow_paper_projection:
            if any(
                node.get("node_type") in PAPER_PROJECTION_NODE_TYPES
                for node in new_nodes
            ) or any(
                edge.get("edge_type") in PAPER_PROJECTION_EDGE_TYPES
                for edge in new_edges
            ):
                raise ValueError(
                    "paper-logic mirrors require a governed projection receipt"
                )
        for edge in sorted(new_edges, key=lambda item: item["edge_id"]):
            self.validate_edge(edge)
            source = edge["source_node_id"]
            target = edge["target_node_id"]
            for endpoint in (source, target):
                if endpoint not in new_node_map and endpoint not in allowed_existing_endpoints:
                    raise ValueError(
                        f"blackboard edge endpoint is outside the bound capability: {endpoint}"
                    )
                if endpoint not in all_nodes:
                    raise ValueError(f"blackboard edge has a dangling endpoint: {endpoint}")
            definition = self.effective_type_definition(
                "edge", edge["edge_type"], edge["type_version"]
            )
            if definition is not None:
                if (
                    not definition["allow_self_edge"]
                    and source == target
                ):
                    raise ValueError("blackboard edge type forbids self edges")
                if definition["cycle_policy"] == "forbid" and self._would_cycle(
                    [*visible_edges.values(), *pending_edges], edge
                ):
                    raise ValueError(
                        f"blackboard {edge['edge_type']} relation would create a cycle"
                    )
                for endpoint, key in (
                    (source, "allowed_source_types"),
                    (target, "allowed_target_types"),
                ):
                    allowed_types = definition[key]
                    endpoint_type = all_nodes[endpoint]["node_type"]
                    if (
                        "*" not in allowed_types
                        and endpoint_type not in allowed_types
                    ):
                        raise ValueError(
                            f"blackboard {edge['edge_type']} endpoint type "
                            f"is not allowed: {endpoint_type}"
                        )
            if edge["edge_type"] == "placed_in":
                target_node = all_nodes[target]
                if target_node["node_type"] != "space":
                    raise ValueError("placed_in target must be a space node")
                if target in visible_nodes and target not in write_spaces:
                    raise ValueError("worker cannot write an unbound existing space")
            if edge["edge_type"] == "paper_relation_mirror":
                if (
                    all_nodes[source]["node_type"] != "paper_logic_mirror"
                    or all_nodes[target]["node_type"] != "paper_logic_mirror"
                ):
                    raise ValueError(
                        "paper relation mirrors must connect paper logic mirrors"
                    )
            if edge["edge_type"] == "retracts_placement":
                placement_id = edge["payload"]["placement_edge_id"]
                placement = visible_edges.get(str(placement_id))
                if (
                    placement is None
                    or placement.get("edge_type") != "placed_in"
                    or placement.get("source_node_id") != source
                    or placement.get("target_node_id") != target
                ):
                    raise ValueError(
                        "retracts_placement must name a matching visible placement edge"
                    )
            pending_edges.append(edge)
        if not allow_create_space and any(
            node["node_type"] == "space" for node in new_nodes
        ):
            raise ValueError("task card does not allow creating a space")
        placements = {
            edge["source_node_id"]
            for edge in new_edges
            if edge["edge_type"] == "placed_in"
        }
        for node in new_nodes:
            if node["node_type"] != "space" and node["node_id"] not in placements:
                raise ValueError(
                    f"new blackboard node {node['node_id']} has no authorized placement"
                )
            if node["node_type"] == "space":
                connected = any(
                    edge["source_node_id"] == node["node_id"]
                    and edge["edge_type"] in {"subspace_of", "overlaps_with"}
                    for edge in new_edges
                )
                existing_spaces = any(
                    item["node_type"] == "space" for item in visible_nodes.values()
                )
                if existing_spaces and not connected:
                    raise ValueError("new space must connect to an existing or new space")

    def add_objects(
        self,
        *,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        actor: str,
    ) -> dict[str, Any]:
        self._validate_graph_objects(new_nodes=nodes, new_edges=edges)
        return self._stage_and_commit(
            nodes=nodes,
            edges=edges,
            kind="direct_mutation",
            actor=actor,
            capability={"role": "operator_or_main"},
        )

    def add_paper_projection(
        self,
        *,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        actor: str,
        paper_snapshot_id: str,
    ) -> dict[str, Any]:
        """Publish one exact Paper Logic mirror transaction.

        This is the only blackboard write path for the reserved mirror types.
        The Paper Logic store separately records and audits the projection
        receipt that binds this transaction to its source snapshot.
        """

        if not nodes or any(
            node.get("node_type") != "paper_logic_mirror" for node in nodes
        ):
            raise ValueError(
                "paper projection requires only paper_logic_mirror nodes"
            )
        if any(
            edge.get("edge_type")
            not in {"placed_in", "paper_relation_mirror"}
            for edge in edges
        ):
            raise ValueError("paper projection contains a nonprojection edge")
        self.ensure_paper_projection_types(actor=actor)
        self._validate_graph_objects(
            new_nodes=nodes,
            new_edges=edges,
            allow_paper_projection=True,
        )
        return self._stage_and_commit(
            nodes=nodes,
            edges=edges,
            kind="paper_logic_projection",
            actor=actor,
            capability={
                "role": "paper_projection",
                "paper_snapshot_id": paper_snapshot_id,
            },
        )

    def create_space(
        self,
        *,
        name: str,
        scope: str,
        actor: str,
        parent_space_id: str | None = None,
        overlaps_with: str | None = None,
    ) -> str:
        node = make_node(
            node_type="space",
            logical_key=f"space:{name}",
            payload={"name": name, "scope": scope, "layout_policy": "free"},
            created_by_assignment_id=actor,
        )
        edges: list[dict[str, Any]] = []
        if parent_space_id:
            edges.append(
                make_edge(
                    edge_type="subspace_of",
                    source_node_id=node["node_id"],
                    target_node_id=parent_space_id,
                    payload={},
                    created_by_assignment_id=actor,
                )
            )
        if overlaps_with:
            edges.append(
                make_edge(
                    edge_type="overlaps_with",
                    source_node_id=node["node_id"],
                    target_node_id=overlaps_with,
                    payload={},
                    created_by_assignment_id=actor,
                )
            )
        self.add_objects(nodes=[node], edges=edges, actor=actor)
        return str(node["node_id"])

    def add_node_with_placements(
        self,
        *,
        node: dict[str, Any],
        space_ids: list[str],
        actor: str,
        placement_payloads: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if not space_ids and node.get("node_type") != "space":
            raise ValueError("a non-space node requires at least one placement")
        placement_payloads = placement_payloads or [{} for _ in space_ids]
        if len(placement_payloads) != len(space_ids):
            raise ValueError("placement payload count mismatch")
        edges = [
            make_edge(
                edge_type="placed_in",
                source_node_id=node["node_id"],
                target_node_id=space_id,
                payload=payload,
                created_by_assignment_id=actor,
            )
            for space_id, payload in zip(space_ids, placement_payloads)
        ]
        return self.add_objects(nodes=[node], edges=edges, actor=actor)

    def _projection_from_objects(
        self,
        *,
        nodes: dict[str, dict[str, Any]],
        edges: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        inactive_node_causes: dict[str, list[str]] = {}
        retracted_placements: set[str] = set()
        projection_edges: set[str] = set()
        for edge_id in sorted(edges):
            edge = edges[edge_id]
            source = edge["source_node_id"]
            target = edge["target_node_id"]
            if source not in nodes or target not in nodes:
                raise ValueError(
                    f"blackboard edge has a dangling endpoint: {edge_id}"
                )
            definition = self.effective_type_definition(
                "edge", edge["edge_type"], edge["type_version"]
            )
            if definition is None:
                raise ValueError(
                    "blackboard edge type has no effective definition: "
                    f"{edge['edge_type']} v{edge['type_version']}"
                )
            for endpoint, key in (
                (source, "allowed_source_types"),
                (target, "allowed_target_types"),
            ):
                allowed_types = definition[key]
                endpoint_type = nodes[endpoint]["node_type"]
                if "*" not in allowed_types and endpoint_type not in allowed_types:
                    raise ValueError(
                        f"blackboard {edge['edge_type']} endpoint type is not allowed: "
                        f"{endpoint_type}"
                    )
            if (
                edge["edge_type"] == "placed_in"
                and nodes[target]["node_type"] != "space"
            ):
                raise ValueError("placed_in target must be a space node")
            if edge["edge_type"] in NODE_DEACTIVATING_EDGE_TYPES:
                inactive_node_causes.setdefault(target, []).append(edge_id)
                projection_edges.add(edge_id)
            elif edge["edge_type"] == "retracts_placement":
                placement_id = edge["payload"]["placement_edge_id"]
                placement = edges.get(placement_id)
                if (
                    placement is None
                    or placement["edge_type"] != "placed_in"
                    or placement["source_node_id"] != source
                    or placement["target_node_id"] != target
                ):
                    raise ValueError(
                        "retracts_placement must name a matching visible "
                        "placement edge"
                    )
                retracted_placements.add(placement_id)
                projection_edges.add(edge_id)

        inactive_nodes = set(inactive_node_causes)
        active_nodes = set(nodes).difference(inactive_nodes)
        active_edges: set[str] = set()
        inactive_edges: set[str] = set()
        for edge_id, edge in edges.items():
            if (
                edge["edge_type"] in PROJECTION_CONTROL_EDGE_TYPES
                or edge_id in retracted_placements
                or edge["source_node_id"] not in active_nodes
                or edge["target_node_id"] not in active_nodes
            ):
                inactive_edges.add(edge_id)
            else:
                active_edges.add(edge_id)
        return {
            "schema_version": 4,
            "policy_revision": POLICY_REVISION_V4,
            "active_node_ids": sorted(active_nodes),
            "inactive_node_ids": sorted(inactive_nodes),
            "active_edge_ids": sorted(active_edges),
            "inactive_edge_ids": sorted(inactive_edges),
            "projection_edge_ids": sorted(projection_edges),
            "retracted_placement_edge_ids": sorted(retracted_placements),
            "inactive_node_causes": {
                node_id: sorted(edge_ids)
                for node_id, edge_ids in sorted(
                    inactive_node_causes.items()
                )
            },
        }

    def _current_objects(
        self,
    ) -> tuple[
        dict[str, dict[str, Any]],
        dict[str, dict[str, Any]],
        dict[str, Any],
    ]:
        nodes = self.nodes()
        edges = self.edges()
        projection = self._projection_from_objects(
            nodes=nodes,
            edges=edges,
        )
        current_nodes = {
            node_id: nodes[node_id]
            for node_id in projection["active_node_ids"]
        }
        current_edges = {
            edge_id: edges[edge_id]
            for edge_id in projection["active_edge_ids"]
        }
        return current_nodes, current_edges, projection

    def current_projection(self) -> dict[str, Any]:
        """Derive the deterministic active view without deleting graph history."""

        return self._current_objects()[2]

    def current_nodes(self) -> dict[str, dict[str, Any]]:
        return self._current_objects()[0]

    def current_edges(self) -> dict[str, dict[str, Any]]:
        return self._current_objects()[1]

    def _graph_event_offset(self) -> int:
        return len(self._receipts())

    @staticmethod
    def validate_query(query: dict[str, Any]) -> dict[str, Any]:
        require_exact_keys(
            query,
            required={
                "seed_node_ids",
                "direction",
                "max_hops",
                "edge_type_allowlist",
                "node_type_allowlist",
                "node_budget",
                "edge_budget",
            },
            label="blackboard query",
        )
        for key in ("seed_node_ids", "edge_type_allowlist", "node_type_allowlist"):
            if not isinstance(query.get(key), list) or any(
                not isinstance(item, str) for item in query[key]
            ):
                raise ValueError(f"blackboard query {key} must be a list of strings")
        if not query["seed_node_ids"]:
            raise ValueError("blackboard query needs at least one seed node")
        if query["direction"] not in {"out", "in", "both"}:
            raise ValueError("blackboard query direction must be out, in, or both")
        for key in ("max_hops", "node_budget", "edge_budget"):
            value = query.get(key)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"blackboard query {key} must be nonnegative")
        if query["node_budget"] < 1:
            raise ValueError("blackboard query node_budget must be positive")
        return query

    def _bounded_query(
        self,
        *,
        nodes: dict[str, dict[str, Any]],
        edges: dict[str, dict[str, Any]],
        query: dict[str, Any],
    ) -> tuple[list[str], list[str], dict[str, Any]]:
        self.validate_query(query)
        seeds = [validate_bb_node_id(item) for item in query["seed_node_ids"]]
        missing = sorted(set(seeds).difference(nodes))
        if missing:
            raise ValueError("blackboard query has unknown seeds: " + ", ".join(missing))
        allowed_edges = set(query["edge_type_allowlist"])
        allow_all_edges = "*" in allowed_edges
        allowed_nodes = set(query["node_type_allowlist"])
        allow_all_nodes = "*" in allowed_nodes
        direction = query["direction"]
        max_hops = query["max_hops"]

        incident: dict[str, list[tuple[str, str, str]]] = {}
        opaque_edges: list[tuple[str, dict[str, Any]]] = []
        for edge_id, edge in sorted(edges.items()):
            if not allow_all_edges and edge["edge_type"] not in allowed_edges:
                continue
            definition = self.effective_type_definition(
                "edge", edge["edge_type"], edge["type_version"]
            )
            if (
                definition is not None
                and definition["automation_semantics"] == "opaque"
            ):
                opaque_edges.append((edge_id, edge))
                continue
            source = edge["source_node_id"]
            target = edge["target_node_id"]
            if direction in {"out", "both"}:
                incident.setdefault(source, []).append(
                    (edge["edge_type"], edge_id, target)
                )
            if direction in {"in", "both"}:
                incident.setdefault(target, []).append(
                    (edge["edge_type"], edge_id, source)
                )
        selected_nodes: list[str] = []
        selected_edges: list[str] = []
        node_seen: set[str] = set()
        edge_seen: set[str] = set()
        boundary: set[str] = set()
        queue: deque[tuple[int, str]] = deque((0, seed) for seed in sorted(seeds))
        omitted_nodes: set[str] = set()
        omitted_edges: set[str] = set()
        while queue:
            hop, node_id = queue.popleft()
            node = nodes[node_id]
            if not allow_all_nodes and node["node_type"] not in allowed_nodes:
                continue
            if node_id not in node_seen:
                if len(selected_nodes) >= query["node_budget"]:
                    omitted_nodes.add(node_id)
                    boundary.add(node_id)
                    continue
                node_seen.add(node_id)
                selected_nodes.append(node_id)
            if hop >= max_hops:
                boundary.add(node_id)
                continue
            candidates = sorted(
                incident.get(node_id, []),
                key=lambda item: (hop + 1, item[0], item[1], item[2]),
            )
            for edge_type, edge_id, neighbor in candidates:
                if edge_id not in edge_seen:
                    if len(selected_edges) >= query["edge_budget"]:
                        omitted_edges.add(edge_id)
                        boundary.add(node_id)
                        continue
                    edge_seen.add(edge_id)
                    selected_edges.append(edge_id)
                if neighbor not in node_seen:
                    queue.append((hop + 1, neighbor))
        for edge_id, edge in opaque_edges:
            source = edge["source_node_id"]
            target = edge["target_node_id"]
            if source not in node_seen or target not in node_seen:
                continue
            if len(selected_edges) >= query["edge_budget"]:
                omitted_edges.add(edge_id)
                boundary.update((source, target))
                continue
            edge_seen.add(edge_id)
            selected_edges.append(edge_id)
        receipt = {
            "node_budget_hit": bool(omitted_nodes),
            "edge_budget_hit": bool(omitted_edges),
            "omitted_node_count": len(omitted_nodes),
            "omitted_edge_count": len(omitted_edges),
            "boundary_node_ids": sorted(boundary),
        }
        return sorted(selected_nodes), sorted(selected_edges), receipt

    def preview_snapshot(self, *, query: dict[str, Any]) -> dict[str, Any]:
        """Build the exact snapshot payload without publishing any bytes.

        Planning extensions may need to bind the current Blackboard cut while
        remaining genuinely read-only.  Keeping construction here also makes
        ``snapshot`` a publisher over the same canonical payload instead of a
        subtly different second implementation.
        """

        nodes, edges, _ = self._current_objects()
        node_ids, edge_ids, omission = self._bounded_query(
            nodes=nodes, edges=edges, query=query
        )
        manifest_body = {
            "schema_version": 4,
            "policy_revision": POLICY_REVISION_V4,
            "seed_node_ids": sorted(query["seed_node_ids"]),
            "query": query,
            "query_sha256": sha256_json(query),
            "node_entries": [
                {
                    "node_id": node_id,
                    "sha256": sha256_bytes(canonical_json_bytes(nodes[node_id])),
                }
                for node_id in node_ids
            ],
            "edge_entries": [
                {
                    "edge_id": edge_id,
                    "sha256": sha256_bytes(canonical_json_bytes(edges[edge_id])),
                }
                for edge_id in edge_ids
            ],
            "omission_receipt": omission,
            "created_from_event_offset": self._graph_event_offset(),
        }
        snapshot_id = "bbs-" + sha256_json(manifest_body)
        manifest = {**manifest_body, "snapshot_id": snapshot_id}
        node_bytes = b"".join(
            canonical_json_bytes(nodes[node_id]) + b"\n" for node_id in node_ids
        )
        edge_bytes = b"".join(
            canonical_json_bytes(edges[edge_id]) + b"\n" for edge_id in edge_ids
        )
        return {
            "snapshot_id": snapshot_id,
            "snapshot_sha256": sha256_bytes(
                (
                    json.dumps(
                        manifest,
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    )
                    + "\n"
                ).encode("utf-8")
            ),
            "query_sha256": manifest["query_sha256"],
            "omission_receipt": omission,
            "manifest": manifest,
            "nodes_bytes": node_bytes,
            "edges_bytes": edge_bytes,
            "publication_effect": "none",
            "truth_effect": "none",
        }

    def snapshot(self, *, query: dict[str, Any], actor: str) -> dict[str, Any]:
        preview = self.preview_snapshot(query=query)
        manifest = preview["manifest"]
        snapshot_id = preview["snapshot_id"]
        directory = self.snapshots_dir / snapshot_id
        manifest_path = directory / "manifest.json"
        if manifest_path.exists():
            existing = self._read_json(manifest_path)
            if existing != manifest:
                raise ValueError("blackboard snapshot id collision")
        else:
            directory.mkdir(parents=True, exist_ok=False)
            self._write_json_once(manifest_path, manifest)
            self._write_once(directory / "nodes.jsonl", preview["nodes_bytes"])
            self._write_once(directory / "edges.jsonl", preview["edges_bytes"])
        return {
            "snapshot_id": snapshot_id,
            "snapshot_sha256": sha256_bytes(manifest_path.read_bytes()),
            "query_sha256": manifest["query_sha256"],
            "omission_receipt": preview["omission_receipt"],
            "manifest_path": str(manifest_path),
            "actor": actor,
        }

    def query(self, query: dict[str, Any]) -> dict[str, Any]:
        nodes, edges, _ = self._current_objects()
        node_ids, edge_ids, omission = self._bounded_query(
            nodes=nodes,
            edges=edges,
            query=query,
        )
        return {
            "node_ids": node_ids,
            "edge_ids": edge_ids,
            "nodes": [nodes[node_id] for node_id in node_ids],
            "edges": [edges[edge_id] for edge_id in edge_ids],
            "omission_receipt": omission,
        }

    def snapshot_manifest(self, snapshot_id: str) -> dict[str, Any]:
        validate_bb_snapshot_id(snapshot_id)
        path = self.snapshots_dir / snapshot_id / "manifest.json"
        if not path.exists():
            raise KeyError(f"unknown blackboard snapshot: {snapshot_id}")
        manifest = self._read_json(path)
        body = {key: value for key, value in manifest.items() if key != "snapshot_id"}
        if manifest.get("snapshot_id") != "bbs-" + sha256_json(body):
            raise ValueError("blackboard snapshot id/hash mismatch")
        return manifest

    def snapshot_objects(
        self, snapshot_id: str
    ) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
        manifest = self.snapshot_manifest(snapshot_id)
        nodes: dict[str, dict[str, Any]] = {}
        edges: dict[str, dict[str, Any]] = {}
        for entry in manifest["node_entries"]:
            node = self.validate_node(self._read_json(self._node_path(entry["node_id"])))
            if sha256_bytes(canonical_json_bytes(node)) != entry["sha256"]:
                raise ValueError("blackboard snapshot node hash mismatch")
            nodes[node["node_id"]] = node
        for entry in manifest["edge_entries"]:
            edge = self.validate_edge(self._read_json(self._edge_path(entry["edge_id"])))
            if sha256_bytes(canonical_json_bytes(edge)) != entry["sha256"]:
                raise ValueError("blackboard snapshot edge hash mismatch")
            edges[edge["edge_id"]] = edge
        return nodes, edges

    def snapshot_query(
        self, *, snapshot_id: str, query: dict[str, Any]
    ) -> dict[str, Any]:
        nodes, edges = self.snapshot_objects(snapshot_id)
        node_ids, edge_ids, omission = self._bounded_query(
            nodes=nodes, edges=edges, query=query
        )
        return {
            "snapshot_id": snapshot_id,
            "node_ids": node_ids,
            "edge_ids": edge_ids,
            "omission_receipt": omission,
        }

    def _conflict_delta(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        *,
        assignment_id: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        existing = self.nodes()
        all_nodes = [*existing.values(), *nodes]
        additions_nodes = list(nodes)
        additions_edges = list(edges)
        placements_by_node: dict[str, list[str]] = {}
        for edge in edges:
            if edge["edge_type"] == "placed_in":
                placements_by_node.setdefault(edge["source_node_id"], []).append(
                    edge["target_node_id"]
                )
        for node in nodes:
            definition = self.effective_type_definition(
                "node", node["node_type"], node["type_version"]
            )
            policy = (
                definition["logical_key_policy"]
                if definition is not None
                else "ignored"
            )
            if policy != "unique_conflict":
                continue
            conflicts = sorted(
                candidate["node_id"]
                for candidate in all_nodes
                if candidate["node_id"] != node["node_id"]
                and candidate["node_type"] == node["node_type"]
                and candidate["logical_key"] == node["logical_key"]
            )
            if not conflicts:
                continue
            conflict_node = make_node(
                node_type="conflict",
                logical_key=f"conflict:{node['node_type']}:{node['logical_key']}",
                payload={
                    "node_type": node["node_type"],
                    "logical_key": node["logical_key"],
                    "candidate_node_ids": sorted([node["node_id"], *conflicts]),
                },
                created_by_assignment_id="orchestrator-merge",
                truth_status="challenged",
            )
            additions_nodes.append(conflict_node)
            placement_targets = placements_by_node.get(node["node_id"], [])
            if placement_targets:
                additions_edges.append(
                    make_edge(
                        edge_type="placed_in",
                        source_node_id=conflict_node["node_id"],
                        target_node_id=sorted(placement_targets)[0],
                        payload={"region": "conflicts"},
                        created_by_assignment_id="orchestrator-merge",
                    )
                )
            for candidate_id in sorted([node["node_id"], *conflicts]):
                additions_edges.append(
                    make_edge(
                        edge_type="challenges",
                        source_node_id=conflict_node["node_id"],
                        target_node_id=candidate_id,
                        payload={"reason": "unique logical key collision"},
                        created_by_assignment_id="orchestrator-merge",
                    )
                )
        dedup_nodes = {
            item["node_id"]: item for item in additions_nodes
        }
        dedup_edges = {
            item["edge_id"]: item for item in additions_edges
        }
        return (
            [dedup_nodes[key] for key in sorted(dedup_nodes)],
            [dedup_edges[key] for key in sorted(dedup_edges)],
        )

    def validate_delta(
        self,
        *,
        delta: dict[str, Any],
        task_card: dict[str, Any],
        return_sha256: str,
        defer_visibility: bool = False,
        allow_legacy_adoption: bool = False,
    ) -> dict[str, Any]:
        """Validate and deterministically expand a worker delta without writing."""

        validate_task_card(
            task_card,
            allow_legacy_adoption=allow_legacy_adoption,
        )
        require_exact_keys(
            delta,
            required={"base_snapshot_id", "add_nodes", "add_edges"},
            label="blackboard graph delta",
        )
        if delta.get("base_snapshot_id") != task_card["blackboard_view"]["snapshot_id"]:
            raise ValueError("blackboard delta base snapshot mismatch")
        if SHA256_RE.fullmatch(return_sha256) is None:
            raise ValueError("return_sha256 must be a full lowercase SHA-256")
        nodes = delta.get("add_nodes")
        edges = delta.get("add_edges")
        if not isinstance(nodes, list) or any(not isinstance(item, dict) for item in nodes):
            raise ValueError("blackboard delta add_nodes must be a list of objects")
        if not isinstance(edges, list) or any(not isinstance(item, dict) for item in edges):
            raise ValueError("blackboard delta add_edges must be a list of objects")
        budgets = task_card["budgets"]
        if len(nodes) > budgets["max_blackboard_nodes_added"]:
            raise ValueError("blackboard node budget exceeded; entire return rejected")
        if len(edges) > budgets["max_blackboard_edges_added"]:
            raise ValueError("blackboard edge budget exceeded; entire return rejected")
        delta_bytes = canonical_json_bytes(delta)
        if len(delta_bytes) > budgets["max_blackboard_delta_bytes_total"]:
            raise ValueError("blackboard delta byte budget exceeded; entire return rejected")
        for item in [*nodes, *edges]:
            if len(canonical_json_bytes(item)) > budgets[
                "max_blackboard_object_bytes_each"
            ]:
                raise ValueError("blackboard object byte budget exceeded; entire return rejected")
        assignment_id = task_card["assignment_id"]
        for item in [*nodes, *edges]:
            if item.get("created_by_assignment_id") != assignment_id:
                raise ValueError("blackboard delta object creator/assignment mismatch")
        snapshot_nodes, _ = self.snapshot_objects(delta["base_snapshot_id"])
        allowed_existing = set(snapshot_nodes) | set(
            task_card["blackboard_view"]["cross_space_endpoint_node_ids"]
        )
        expanded_nodes, expanded_edges = self._conflict_delta(
            [dict(item) for item in nodes],
            [dict(item) for item in edges],
            assignment_id=assignment_id,
        )
        self._validate_graph_objects(
            new_nodes=expanded_nodes,
            new_edges=expanded_edges,
            allowed_existing_endpoints=allowed_existing,
            write_spaces=set(task_card["blackboard_view"]["write_space_ids"]),
            allow_create_space=task_card["blackboard_view"]["allow_create_space"],
        )
        capability = {
            "snapshot_id": delta["base_snapshot_id"],
            "write_space_ids": sorted(task_card["blackboard_view"]["write_space_ids"]),
            "cross_space_endpoint_node_ids": sorted(
                task_card["blackboard_view"]["cross_space_endpoint_node_ids"]
            ),
            "allow_create_space": task_card["blackboard_view"]["allow_create_space"],
            "ingestion_marker_required": defer_visibility,
        }
        return {
            "nodes": expanded_nodes,
            "edges": expanded_edges,
            "assignment_id": assignment_id,
            "base_snapshot_id": delta["base_snapshot_id"],
            "return_sha256": return_sha256,
            "capability": capability,
        }

    def merge_delta(
        self,
        *,
        delta: dict[str, Any],
        task_card: dict[str, Any],
        return_sha256: str,
        defer_visibility: bool = False,
        allow_legacy_adoption: bool = False,
    ) -> dict[str, Any]:
        prepared = self.validate_delta(
            delta=delta,
            task_card=task_card,
            return_sha256=return_sha256,
            defer_visibility=defer_visibility,
            allow_legacy_adoption=allow_legacy_adoption,
        )
        return self._stage_and_commit(
            nodes=prepared["nodes"],
            edges=prepared["edges"],
            kind="worker_delta_merge",
            actor="orchestrator",
            assignment_id=prepared["assignment_id"],
            base_snapshot_id=prepared["base_snapshot_id"],
            return_sha256=prepared["return_sha256"],
            capability=prepared["capability"],
        )

    def _desired_index(self) -> dict[str, Any]:
        nodes, edges, projection = self._current_objects()
        by_space: dict[str, list[str]] = {}
        by_type: dict[str, list[str]] = {}
        adjacency: dict[str, list[str]] = {}
        for node_id, node in nodes.items():
            by_type.setdefault(node["node_type"], []).append(node_id)
        for edge_id, edge in edges.items():
            adjacency.setdefault(edge["source_node_id"], []).append(edge_id)
            adjacency.setdefault(edge["target_node_id"], []).append(edge_id)
            if edge["edge_type"] == "placed_in":
                by_space.setdefault(edge["target_node_id"], []).append(
                    edge["source_node_id"]
                )
        return {
            "schema_version": 4,
            "policy_revision": POLICY_REVISION_V4,
            "event_offset": self._graph_event_offset(),
            "current_projection": projection,
            "by_space": {
                key: sorted(set(value)) for key, value in sorted(by_space.items())
            },
            "by_type": {
                key: sorted(set(value)) for key, value in sorted(by_type.items())
            },
            "adjacency": {
                key: sorted(set(value)) for key, value in sorted(adjacency.items())
            },
        }

    def reindex(self, *, apply: bool, actor: str = "") -> dict[str, Any]:
        desired = self._desired_index()
        current = self._read_json(self.index_path) if self.index_path.exists() else None
        result = {
            "clean": current == desired,
            "current_sha256": sha256_json(current) if current is not None else None,
            "desired_sha256": sha256_json(desired),
            "applied": False,
        }
        if apply and current != desired:
            if not actor.strip():
                raise ValueError("blackboard reindex --apply requires an actor")
            self._write_atomic(
                self.index_path,
                json.dumps(
                    desired, ensure_ascii=False, indent=2, sort_keys=True
                ).encode("utf-8")
                + b"\n",
            )
            result["applied"] = True
            result["clean"] = True
        return result

    def audit(self) -> dict[str, Any]:
        errors: list[str] = []
        warnings: list[str] = []
        try:
            visible_nodes, visible_edges = self.visible_ids()
            markers = self._ingestion_markers()
            pending_worker_transactions = [
                receipt["transaction_id"]
                for receipt in self._receipts()
                if receipt.get("kind") == "worker_delta_merge"
                and receipt.get("capability", {}).get(
                    "ingestion_marker_required", False
                )
                and receipt["transaction_id"] not in markers
            ]
        except Exception as exc:
            return {
                "ok": False,
                "errors": [f"transaction receipt error: {exc}"],
                "warnings": [],
            }
        if pending_worker_transactions:
            warnings.append(
                "pre-receipt worker transactions are invisible: "
                + ", ".join(sorted(pending_worker_transactions))
            )
        for receipt in self._receipts():
            if receipt.get("kind") != "worker_delta_merge":
                continue
            try:
                matching_cards: list[dict[str, Any]] = []
                for round_path in sorted(
                    (self.project_root / "rounds").glob("*/round.json")
                ):
                    round_manifest = self._read_json(round_path)
                    for assignment in round_manifest.get("assignments", []):
                        if (
                            not isinstance(assignment, dict)
                            or assignment.get("assignment_id")
                            != receipt["assignment_id"]
                        ):
                            continue
                        task_path = (
                            self.project_root
                            / str(assignment.get("task_card_relpath", ""))
                        ).resolve()
                        if (
                            not task_path.is_relative_to(self.project_root)
                            or not task_path.is_file()
                            or task_path.is_symlink()
                        ):
                            continue
                        card = self._read_json(task_path)
                        validate_task_card(
                            card,
                            allow_legacy_adoption=True,
                        )
                        if (
                            card["blackboard_view"]["snapshot_id"]
                            == receipt["base_snapshot_id"]
                        ):
                            matching_cards.append(card)
                if len(matching_cards) != 1:
                    raise ValueError(
                        "worker transaction has no unique bound task card"
                    )
                card = matching_cards[0]
                expected_capability = {
                    "snapshot_id": receipt["base_snapshot_id"],
                    "write_space_ids": sorted(
                        card["blackboard_view"]["write_space_ids"]
                    ),
                    "cross_space_endpoint_node_ids": sorted(
                        card["blackboard_view"][
                            "cross_space_endpoint_node_ids"
                        ]
                    ),
                    "allow_create_space": card["blackboard_view"][
                        "allow_create_space"
                    ],
                    "ingestion_marker_required": receipt.get(
                        "capability", {}
                    ).get("ingestion_marker_required", False),
                }
                if receipt.get("capability") != expected_capability:
                    raise ValueError(
                        "worker transaction capability/task-card mismatch"
                    )
            except Exception as exc:
                errors.append(
                    f"{receipt.get('transaction_id', 'unknown')}: "
                    f"capability audit failed: {exc}"
                )
        nodes: dict[str, dict[str, Any]] = {}
        edges: dict[str, dict[str, Any]] = {}
        for node_id in sorted(visible_nodes):
            try:
                path = self._node_path(node_id)
                if not path.is_file() or path.is_symlink():
                    raise ValueError("CAS object is missing or not regular")
                nodes[node_id] = self.validate_node(self._read_json(path))
            except Exception as exc:
                errors.append(f"{node_id}: {exc}")
        for edge_id in sorted(visible_edges):
            try:
                path = self._edge_path(edge_id)
                if not path.is_file() or path.is_symlink():
                    raise ValueError("CAS object is missing or not regular")
                edge = self.validate_edge(self._read_json(path))
                if (
                    edge["source_node_id"] not in nodes
                    or edge["target_node_id"] not in nodes
                ):
                    raise ValueError("dangling endpoint")
                if (
                    edge["edge_type"] == "placed_in"
                    and nodes[edge["target_node_id"]]["node_type"] != "space"
                ):
                    raise ValueError("placed_in target is not a space")
                definition = self.effective_type_definition(
                    "edge", edge["edge_type"], edge["type_version"]
                )
                if definition and definition["cycle_policy"] == "forbid":
                    if self._would_cycle(edges.values(), edge):
                        raise ValueError(f"{edge['edge_type']} cycle")
                edges[edge_id] = edge
            except Exception as exc:
                errors.append(f"{edge_id}: {exc}")
        projection: dict[str, Any] | None = None
        if len(nodes) == len(visible_nodes) and len(edges) == len(visible_edges):
            try:
                projection = self._projection_from_objects(
                    nodes=nodes,
                    edges=edges,
                )
            except Exception as exc:
                errors.append(f"current projection replay failed: {exc}")
        orphan_nodes = sorted(
            path.stem
            for path in self.nodes_dir.glob("bbn-*.json")
            if path.stem not in visible_nodes
        )
        orphan_edges = sorted(
            path.stem
            for path in self.edges_dir.glob("bbe-*.json")
            if path.stem not in visible_edges
        )
        if orphan_nodes or orphan_edges:
            warnings.append(
                f"pre-receipt CAS orphans: {len(orphan_nodes)} nodes, "
                f"{len(orphan_edges)} edges"
            )
        for directory in sorted(self.snapshots_dir.glob("bbs-*")):
            try:
                self.snapshot_manifest(directory.name)
                self.snapshot_objects(directory.name)
            except Exception as exc:
                errors.append(f"snapshot {directory.name}: {exc}")
        try:
            index = self.reindex(apply=False)
            if not index["clean"]:
                errors.append(
                    "blackboard indices are missing or stale; run reindex --apply"
                )
        except Exception as exc:
            index = {
                "clean": False,
                "current_sha256": None,
                "desired_sha256": None,
                "applied": False,
            }
            errors.append(f"blackboard index replay failed: {exc}")
        return {
            "ok": not errors,
            "errors": errors,
            "warnings": warnings,
            "visible_nodes": len(nodes),
            "visible_edges": len(edges),
            "current_projection": projection,
            "orphan_node_ids": orphan_nodes,
            "orphan_edge_ids": orphan_edges,
            "index": index,
        }

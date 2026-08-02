from __future__ import annotations

"""Project-bound lifecycle for composable parallel verification.

The pure protocol in :mod:`parallel_verification` defines hashes, signatures,
work-plan cardinalities, packets, receipts, and mechanical aggregation.  This
manager supplies the missing authority boundary: Operator-trusted keys,
inventory derived from one real Candidate Release and its exact verifier
capsule, immutable record stores, and a release-scoped eligible aggregate that
Certification and the Gateway can require.

This is a verifier-work partition only.  It never schedules Research and never
writes Fact authority.
"""

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import parallel_verification as pv
from .contracts import sha256_bytes, sha256_json


LIFECYCLE_REVISION = "chalxius-parallel-verification-lifecycle-1"
SIGNED_PLAN_ID_RE = re.compile(r"vsp-[0-9a-f]{64}")
PACKET_ID_RE = re.compile(r"vpk-[0-9a-f]{64}")
RECEIPT_ID_RE = re.compile(r"vmr-[0-9a-f]{64}")
AGGREGATE_ID_RE = re.compile(r"vag-[0-9a-f]{64}")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _parse_time(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} is invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _exact(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{label} fields are not exact")
    return value


def _strings(value: Any, label: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(f"{label} must be a list of nonempty strings")
    if nonempty and not value:
        raise ValueError(f"{label} must be nonempty")
    if len(value) != len(set(value)):
        raise ValueError(f"{label} contains duplicates")
    return sorted(value)


class ParallelVerificationLifecycleManager:
    def __init__(self, lifecycle: Any) -> None:
        self.lifecycle = lifecycle
        self.store = lifecycle.store
        self.root = lifecycle.root / "parallel-verification"
        self.keys_dir = self.root / "trusted-keys" / "by-id"
        self.plans_dir = self.root / "signed-plans" / "by-id"
        self.plan_heads_dir = self.root / "signed-plans" / "by-release"
        self.packets_dir = self.root / "packets" / "by-id"
        self.packet_slots_dir = self.root / "packets" / "by-plan-slot"
        self.receipts_dir = self.root / "receipts" / "by-id"
        self.receipt_slots_dir = self.root / "receipts" / "by-plan-slot"
        self.aggregates_dir = self.root / "aggregates" / "by-id"
        self.aggregate_heads_dir = self.root / "aggregates" / "by-release"
        self._signed_plan_cache: dict[
            str, tuple[tuple[int, int, int, int, int], dict[str, Any]]
        ] = {}
        self._packet_cache: dict[
            str, tuple[tuple[int, int, int, int, int], dict[str, Any]]
        ] = {}
        self._receipt_cache: dict[
            str, tuple[tuple[int, int, int, int, int], dict[str, Any]]
        ] = {}

    def initialize(self) -> None:
        for path in (
            self.keys_dir,
            self.plans_dir,
            self.plan_heads_dir,
            self.packets_dir,
            self.packet_slots_dir,
            self.receipts_dir,
            self.receipt_slots_dir,
            self.aggregates_dir,
            self.aggregate_heads_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def register_key(
        self,
        payload: dict[str, Any],
        *,
        actor: str,
        authority_role: str,
    ) -> dict[str, Any]:
        _exact(
            payload,
            {
                "key_role",
                "public_key_hex",
                "principal_id",
                "reviewer_role_or_null",
                "host_context_id_or_null",
                "trust_domain_id",
            },
            "verification key registration input",
        )
        if authority_role != "operator":
            raise PermissionError("verification key registration requires the Operator role")
        record = pv.build_trusted_key_record(
            project_id=self.store.project_id(),
            key_role=payload["key_role"],
            public_key_hex=payload["public_key_hex"],
            principal_id=payload["principal_id"],
            reviewer_role_or_null=payload["reviewer_role_or_null"],
            host_context_id_or_null=payload["host_context_id_or_null"],
            trust_domain_id=payload["trust_domain_id"],
            registered_by=actor,
        )
        with self.store.v5_mutation_lock(command="verification-key-register"):
            self.initialize()
            # Validate the complete immutable registry before every branch,
            # including the idempotent existing-record return. Idempotence is
            # not permission to report success from a corrupted authority set.
            current = self._load_trusted_keys()
            path = self.keys_dir / f"{record['key_id']}.json"
            if path.exists():
                existing = current.get(record["key_id"])
                if existing is None:
                    raise ValueError("verification trusted key registry/path mismatch")
                if existing != record:
                    raise ValueError("verification trusted key id collision")
                return existing
            pv.validate_trusted_key_registry(
                {**current, record["key_id"]: record},
                project_id=self.store.project_id(),
            )
            self.store._write_json_once(path, record)
        return record

    def _key_record(self, key_id: str) -> dict[str, Any]:
        if not isinstance(key_id, str) or not key_id.startswith("vtk-"):
            raise ValueError("verification trusted key id is invalid")
        path = self.keys_dir / f"{key_id}.json"
        if path.is_symlink() or not path.is_file():
            raise KeyError(f"unknown verification trusted key: {key_id}")
        record = self.store._read_json(path)
        pv.validate_trusted_key_record(record, project_id=self.store.project_id())
        if path.stem != record["key_id"]:
            raise ValueError("verification trusted key path/id mismatch")
        return record

    def key(self, key_id: str) -> dict[str, Any]:
        if not isinstance(key_id, str) or not key_id.startswith("vtk-"):
            raise ValueError("verification trusted key id is invalid")
        registry = self._load_trusted_keys()
        if key_id not in registry:
            raise KeyError(f"unknown verification trusted key: {key_id}")
        return registry[key_id]

    def _load_trusted_keys(self) -> dict[str, dict[str, Any]]:
        if not self.keys_dir.exists():
            return {}
        result = {
            path.stem: self._key_record(path.stem)
            for path in sorted(self.keys_dir.glob("vtk-*.json"))
        }
        return pv.validate_trusted_key_registry(
            result, project_id=self.store.project_id()
        )

    def trusted_keys(self) -> dict[str, dict[str, Any]]:
        # Always rebuild from immutable disk records. A cache owned by another
        # process cannot hide a newly introduced registry alias or key.
        return self._load_trusted_keys()

    @staticmethod
    def _subject(
        namespace: str,
        object_id: str,
        *,
        semantic: Any | None = None,
        file_sha256: str | None = None,
        use_anchors: list[str] | None = None,
        artifact_refs: list[str] | None = None,
        dependency_refs: list[str] | None = None,
        risk: str,
    ) -> dict[str, Any]:
        return {
            "namespace": namespace,
            "object_id": object_id,
            "object_semantic_sha256_or_null": (
                sha256_json(semantic) if semantic is not None else None
            ),
            "object_file_sha256_or_null": file_sha256,
            "use_anchors": use_anchors or [],
            "required_artifact_refs": artifact_refs or [],
            "dependency_ref_ids": dependency_refs or [],
            "risk_class": risk,
        }

    @staticmethod
    def _relation(
        kind: str,
        source_ref: str,
        target_ref: str,
        *,
        purpose: str,
        anchor: str | None = None,
    ) -> dict[str, Any]:
        semantic = {
            "relation_kind": kind,
            "source_ref": source_ref,
            "target_ref": target_ref,
            "traversal_purpose": purpose,
            "exact_use_anchor_or_null": anchor,
        }
        return {
            "relation_id": "rel-" + sha256_json(semantic),
            **semantic,
            "relation_semantic_sha256_or_null": sha256_json(semantic),
        }

    def _inventory(
        self, release: dict[str, Any], capsule: dict[str, Any]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        subjects: dict[str, dict[str, Any]] = {}
        relations: dict[str, dict[str, Any]] = {}

        def add_subject(item: dict[str, Any]) -> None:
            object_id = item["object_id"]
            if object_id in subjects:
                raise ValueError("verification lifecycle derived a duplicate subject id")
            subjects[object_id] = item

        def add_relation(item: dict[str, Any]) -> None:
            relation_id = item["relation_id"]
            if relation_id in relations:
                raise ValueError("verification lifecycle derived a duplicate relation id")
            relations[relation_id] = item

        artifact_ids = {
            item["artifact_sha256"]: f"artifact:{item['artifact_sha256']}"
            for item in release["artifacts"]
        }
        authorized_artifact_ids = sorted(
            artifact_ids[item["artifact_sha256"]]
            for item in capsule["authorized_artifacts"]
        )
        for candidate in release["candidates"]:
            add_subject(
                self._subject(
                    "candidate_fact",
                    f"fact:{candidate['fact_id']}",
                    semantic={
                        "fact_id": candidate["fact_id"],
                        "release_id": release["release_id"],
                    },
                    file_sha256=candidate["fact_sha256"],
                    artifact_refs=authorized_artifact_ids,
                    risk="high",
                )
            )
        for index, interface in enumerate(release.get("candidate_interfaces", []), 1):
            fact_id = interface.get("fact_id", release["fact_ids"][index - 1])
            add_subject(
                self._subject(
                    "candidate_interface",
                    f"interface:{fact_id}:{index}",
                    semantic=interface,
                    dependency_refs=[f"fact:{fact_id}"],
                    risk="high",
                )
            )
        for predecessor, fact_id in release["internal_edges"]:
            object_id = f"internal-edge:{predecessor}:{fact_id}"
            edge = [predecessor, fact_id]
            add_subject(
                self._subject(
                    "internal_predecessor_use",
                    object_id,
                    semantic=edge,
                    use_anchors=[object_id],
                    dependency_refs=[f"fact:{predecessor}", f"fact:{fact_id}"],
                    risk="high",
                )
            )
            add_relation(
                self._relation(
                    "predecessor_use",
                    f"fact:{predecessor}",
                    f"fact:{fact_id}",
                    purpose="premise_closure",
                    anchor=object_id,
                )
            )
        for predecessor in release["external_predecessors"]:
            object_id = f"external-edge:{predecessor}"
            packet = next(
                item
                for item in capsule["predecessor_packets"]
                if item["fact_id"] == predecessor
            )
            add_subject(
                self._subject(
                    "external_predecessor_use",
                    object_id,
                    semantic=packet,
                    file_sha256=packet["fact_sha256"],
                    use_anchors=[object_id],
                    risk="high",
                )
            )
        strict = (
            release["requested_assurance"].get("contract_revision")
            == "chalxius-research-draft-assurance-1"
        )
        if strict:
            plan = release["research_draft_evidence"]["plan"]
            batch = release["research_draft_evidence"]["batch"]
            assurance = release["requested_assurance"]
            for target_id in plan["target_node_ids"]:
                entry = next(
                    item for item in batch["entries"] if item["target_node_id"] == target_id
                )
                add_subject(
                    self._subject(
                        "paper_target",
                        f"paper-target:{target_id}",
                        semantic=entry,
                        artifact_refs=[
                            f"artifact:{plan['source_artifact_sha256']}"
                        ],
                        risk="high",
                    )
                )
            for component in assurance["component_inventory"]:
                add_subject(
                    self._subject(
                        "atomic_component",
                        f"component:{component['component_id']}",
                        semantic=component,
                        dependency_refs=[f"fact:{component['fact_id']}"],
                        risk="high",
                    )
                )
            for entry in batch["entries"]:
                for surface in entry["failure_surfaces"]:
                    add_subject(
                        self._subject(
                            "failure_surface",
                            f"failure:{surface['surface_uid']}",
                            semantic=surface,
                            dependency_refs=[
                                f"paper-target:{entry['target_node_id']}",
                                f"component:{surface['component_id']}",
                            ],
                            risk="high",
                        )
                    )
                    add_relation(
                        self._relation(
                            "defeats_or_challenges",
                            f"failure:{surface['surface_uid']}",
                            f"component:{surface['component_id']}",
                            purpose="premise_closure",
                        )
                    )
            for mapping in assurance["paper_fact_mappings"]:
                source = f"fact:{mapping['fact_id']}"
                target = f"paper-target:{mapping['paper_node_id']}"
                if target in subjects:
                    add_relation(
                        self._relation(
                            "paper_maps_or_binds",
                            source,
                            target,
                            purpose="premise_closure",
                        )
                    )
        for index, disposition in enumerate(release["challenge_dispositions"], 1):
            add_subject(
                self._subject(
                    "challenge_or_defeater",
                    f"challenge:{disposition['research_id']}:{index}",
                    semantic=disposition,
                    risk="high",
                )
            )
        add_subject(
            self._subject(
                "assurance_item",
                f"assurance:{release['release_id']}",
                semantic=release["requested_assurance"],
                dependency_refs=[f"fact:{item}" for item in release["fact_ids"]],
                risk="high",
            )
        )
        for index, ref in enumerate(release["paper_evidence_refs"], 1):
            add_subject(
                self._subject(
                    "paper_evidence_ref",
                    f"paper-ref:{ref['snapshot_id']}:{index}",
                    semantic=ref,
                    artifact_refs=[f"artifact:{ref['target_artifact_sha256']}"],
                    risk="high",
                )
            )
        for artifact in release["artifacts"]:
            object_id = artifact_ids[artifact["artifact_sha256"]]
            add_subject(
                self._subject(
                    "artifact",
                    object_id,
                    semantic={
                        "role": artifact["role"],
                        "sealed_relpath": artifact["sealed_relpath"],
                    },
                    file_sha256=artifact["artifact_sha256"],
                    risk=(
                        "high"
                        if artifact["role"]
                        in {"paper_source", "paper_revised_writing", "source"}
                        else "ordinary"
                    ),
                )
            )
        global_id = f"global:{release['release_id']}"
        add_subject(
            self._subject(
                "global_invariant",
                global_id,
                semantic={
                    "release_id": release["release_id"],
                    "release_sha256": release["release_sha256"],
                    "capsule_sha256": capsule["capsule_sha256"],
                    "fact_ids": release["fact_ids"],
                    "required_checks": capsule["required_checks"],
                    "strict_research_draft": strict,
                },
                dependency_refs=sorted(subjects),
                risk="high",
            )
        )
        for artifact_id in artifact_ids.values():
            add_relation(
                self._relation(
                    "artifact_contains_or_authorizes",
                    artifact_id,
                    global_id,
                    purpose="artifact_closure",
                )
            )
        known = set(subjects)
        for relation in relations.values():
            if relation["source_ref"] not in known or relation["target_ref"] not in known:
                raise ValueError("verification lifecycle relation endpoint is not inventoried")
        return (
            sorted(subjects.values(), key=lambda item: item["object_id"]),
            sorted(relations.values(), key=lambda item: item["relation_id"]),
        )

    def _release_binding(
        self, release_id: str
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
        release = self.lifecycle.release(release_id, _deep_dependencies=True)
        capsule = self.lifecycle.verifier_capsule(release_id)
        hashes = {
            "release_semantic_sha256": release["release_sha256"],
            "release_file_sha256": sha256_bytes(
                self.lifecycle._release_path(release_id).read_bytes()
            ),
            "capsule_semantic_sha256": capsule["capsule_sha256"],
            "capsule_file_sha256": sha256_bytes(pv.file_bytes(capsule)),
        }
        return release, capsule, hashes

    def _assignments(
        self,
        *,
        subjects: list[dict[str, Any]],
        relations: list[dict[str, Any]],
        trusted_keys: dict[str, dict[str, Any]],
        host_key_ids: list[str],
        reviewer_key_ids: list[str],
        context_budget: int,
    ) -> list[dict[str, Any]]:
        if (
            not isinstance(context_budget, int)
            or isinstance(context_budget, bool)
            or context_budget <= 0
            or context_budget > pv.SAFE_INTEGER
        ):
            raise ValueError("verification context budget is invalid")
        hosts = [
            pv._trusted_key(trusted_keys, key_id, expected_role="host")
            for key_id in host_key_ids
        ]
        if len(hosts) < 2:
            raise ValueError("verification high-risk plan requires two trusted hosts")
        if len({item["host_context_id_or_null"] for item in hosts[:2]}) < 2 or len(
            {item["trust_domain_id"] for item in hosts[:2]}
        ) < 2:
            raise ValueError("verification high-risk hosts lack context/trust diversity")
        reviewers = [
            pv._trusted_key(trusted_keys, key_id, expected_role="reviewer")
            for key_id in reviewer_key_ids
        ]
        by_role: dict[str, list[dict[str, Any]]] = {}
        for item in reviewers:
            by_role.setdefault(item["reviewer_role_or_null"], []).append(item)
        register = pv.derive_obligation_register(subjects)
        subject_by_id = {item["object_id"]: item for item in register["subjects"]}
        relation_by_id = {item["relation_id"]: item for item in relations}
        groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for obligation in register["obligations"]:
            role = obligation["allowed_reviewer_roles"][0]
            groups.setdefault((role, obligation["cutoff_profile_id"]), []).append(
                obligation
            )
        assignments: list[dict[str, Any]] = []

        def closure(seed_ids: set[str]) -> tuple[list[str], list[str]]:
            result = set(seed_ids)
            changed = True
            while changed:
                changed = False
                for relation in relations:
                    if (
                        relation["source_ref"] in result
                        or relation["target_ref"] in result
                    ):
                        before = len(result)
                        result.update(
                            {relation["source_ref"], relation["target_ref"]}
                        )
                        changed = changed or len(result) != before
            relation_ids = sorted(
                relation["relation_id"]
                for relation in relations
                if relation["source_ref"] in result
                and relation["target_ref"] in result
            )
            return sorted(result), relation_ids

        def append_assignment(
            role: str,
            cutoff: str,
            obligations: list[dict[str, Any]],
            *,
            slot_role: str,
            pool_index: int,
        ) -> None:
            pool = by_role.get(role, [])
            if len(pool) <= pool_index:
                raise ValueError(
                    f"verification role {role} lacks distinct trusted reviewer keys"
                )
            reviewer = pool[pool_index]
            host = hosts[pool_index]
            obligation_ids = sorted(item["obligation_id"] for item in obligations)
            seed_ids = {
                item["subject_ref"]["object_id"] for item in obligations
            }
            subject_ids, relation_ids = closure(seed_ids)
            estimated = len(
                pv.jcs_bytes(
                    {
                        "obligations": obligations,
                        "subjects": [subject_by_id[item] for item in subject_ids],
                        "relations": [relation_by_id[item] for item in relation_ids],
                    }
                )
            )
            if estimated > context_budget:
                raise ValueError(
                    "verification closure exceeds context budget; increase the budget or seal a new release"
                )
            slot_seed = {
                "slot_role": slot_role,
                "reviewer_role": role,
                "cutoff": cutoff,
                "obligation_ids": obligation_ids,
                "reviewer_key_id": reviewer["key_id"],
                "host_key_id": host["key_id"],
            }
            assignments.append(
                {
                    "slot_id": f"slot-{slot_role}-" + sha256_json(slot_seed),
                    "slot_role": slot_role,
                    "reviewer_role": role,
                    "principal_id": reviewer["principal_id"],
                    "host_context_id": host["host_context_id_or_null"],
                    "trust_domain_id": host["trust_domain_id"],
                    "host_key_id": host["key_id"],
                    "reviewer_key_id": reviewer["key_id"],
                    "obligation_ids": obligation_ids,
                    "subject_ids": subject_ids,
                    "relation_ids": relation_ids,
                    "boundary_stub_ids": [],
                    "context_budget": context_budget,
                    "closure_complete": True,
                    "cutoff_profile_id": cutoff,
                }
            )

        for (role, cutoff), obligations in sorted(groups.items()):
            append_assignment(
                role, cutoff, obligations, slot_role="primary", pool_index=0
            )
            high = [item for item in obligations if item["risk_class"] == "high"]
            if high:
                append_assignment(
                    role, cutoff, high, slot_role="overlap", pool_index=1
                )
        return assignments

    def prepare_plan(
        self, release_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        _exact(
            payload,
            {
                "planner_key_id",
                "host_key_ids",
                "reviewer_key_ids",
                "context_budget",
            },
            "verification plan preparation input",
        )
        trusted = self.trusted_keys()
        planner = pv._trusted_key(
            trusted, payload["planner_key_id"], expected_role="planner"
        )
        host_ids = _strings(
            payload["host_key_ids"], "verification host key ids", nonempty=True
        )
        reviewer_ids = _strings(
            payload["reviewer_key_ids"],
            "verification reviewer key ids",
            nonempty=True,
        )
        release, capsule, hashes = self._release_binding(release_id)
        subjects, relations = self._inventory(release, capsule)
        assignments = self._assignments(
            subjects=subjects,
            relations=relations,
            trusted_keys=trusted,
            host_key_ids=host_ids,
            reviewer_key_ids=reviewer_ids,
            context_budget=payload["context_budget"],
        )
        plan = pv.build_work_plan(
            **hashes,
            subjects=subjects,
            relations=relations,
            assignments=assignments,
        )
        body = pv.prepare_work_plan_attestation(plan)
        return {
            "release_id": release_id,
            "release_sha256": release["release_sha256"],
            "capsule_sha256": capsule["capsule_sha256"],
            "work_plan": plan,
            "planner_key_id": planner["key_id"],
            "planner_attestation_body": body,
            "planner_attestation_projection_additions": {
                "key_id": planner["key_id"],
                "scope": f"plan:{plan['plan_id']}",
                "key_role": planner["key_role"],
                "principal_id": planner["principal_id"],
                "trust_domain_id": planner["trust_domain_id"],
            },
            "truth_effect": "none",
        }

    def _validate_plan_binding(
        self, release_id: str, signed_plan: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        trusted = self.trusted_keys()
        signed_plan = pv.validate_signed_work_plan(signed_plan, trusted_keys=trusted)
        release, capsule, hashes = self._release_binding(release_id)
        subjects, relations = self._inventory(release, capsule)
        plan = signed_plan["work_plan"]
        rebuilt = pv.build_work_plan(
            **hashes,
            subjects=subjects,
            relations=relations,
            assignments=plan["assignments"],
            parent_plan_id=plan["parent_plan_id"],
            discovery_receipt_ids=plan["discovery_receipt_ids"],
        )
        if rebuilt != plan:
            raise ValueError(
                "verification work plan was not derived from the exact release/capsule inventory"
            )
        return signed_plan, trusted

    def record_plan(
        self, release_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        _exact(
            payload,
            {"work_plan", "planner_attestation"},
            "verification signed-plan input",
        )
        trusted = self.trusted_keys()
        signed = pv.build_signed_work_plan(
            plan=payload["work_plan"],
            planner_attestation=payload["planner_attestation"],
            trusted_keys=trusted,
        )
        signed, _ = self._validate_plan_binding(release_id, signed)
        with self.store.v5_mutation_lock(command="verification-plan-record"):
            self.initialize()
            head = self.plan_heads_dir / f"{release_id}.json"
            path = self.plans_dir / f"{signed['signed_plan_id']}.json"
            if head.exists():
                existing_head = self.store._read_json(head)
                if existing_head.get("signed_plan_id") != signed["signed_plan_id"]:
                    raise ValueError(
                        "Candidate Release already has a different signed verification plan"
                    )
                return self.signed_plan(signed["signed_plan_id"], deep=True)
            self.store._write_json_once(path, signed)
            self.store._write_json_once(
                head,
                {
                    "schema_version": 1,
                    "contract_revision": LIFECYCLE_REVISION,
                    "release_id": release_id,
                    "signed_plan_id": signed["signed_plan_id"],
                    "signed_plan_body_sha256": signed["body_sha256"],
                    "truth_effect": "none",
                },
            )
        return signed

    def signed_plan(
        self, signed_plan_id: str, *, deep: bool = False
    ) -> dict[str, Any]:
        if SIGNED_PLAN_ID_RE.fullmatch(signed_plan_id) is None:
            raise ValueError("verification signed plan id is invalid")
        path = self.plans_dir / f"{signed_plan_id}.json"
        if path.is_symlink() or not path.is_file():
            raise KeyError(f"unknown verification signed plan: {signed_plan_id}")
        stat = path.stat()
        fingerprint = (
            stat.st_dev,
            stat.st_ino,
            stat.st_size,
            stat.st_mtime_ns,
            stat.st_ctime_ns,
        )
        cached = self._signed_plan_cache.get(signed_plan_id)
        if not deep and cached is not None and cached[0] == fingerprint:
            # A cache is a byte-I/O optimization only, never cached authority.
            self.trusted_keys()
            return cached[1]
        trusted = self.trusted_keys()
        signed = self.store._read_json(path)
        pv.validate_signed_work_plan(signed, trusted_keys=trusted)
        if signed["signed_plan_id"] != path.stem:
            raise ValueError("verification signed plan path/id mismatch")
        if deep:
            heads = [
                self.store._read_json(item)
                for item in self.plan_heads_dir.glob("release-*.json")
                if item.is_file() and not item.is_symlink()
            ]
            matching = [
                item for item in heads if item.get("signed_plan_id") == signed_plan_id
            ]
            if len(matching) != 1:
                raise ValueError("verification signed plan release binding is missing")
            self._validate_plan_binding(matching[0]["release_id"], signed)
        self._signed_plan_cache[signed_plan_id] = (fingerprint, signed)
        return signed

    def _release_id_for_plan(self, signed_plan_id: str) -> str:
        matches: list[str] = []
        if self.plan_heads_dir.exists():
            for path in sorted(self.plan_heads_dir.glob("release-*.json")):
                if path.is_symlink() or not path.is_file():
                    raise ValueError("verification signed-plan head is unsafe")
                head = self.store._read_json(path)
                if head.get("signed_plan_id") == signed_plan_id:
                    matches.append(head.get("release_id"))
        if len(matches) != 1 or not isinstance(matches[0], str):
            raise ValueError("verification signed plan has no unique release binding")
        return matches[0]

    def prepare_packet(self, signed_plan_id: str, slot_id: str) -> dict[str, Any]:
        signed = self.signed_plan(signed_plan_id, deep=False)
        trusted = self.trusted_keys()
        prepared = pv.prepare_dispatch_packet(
            signed_plan=signed, slot_id=slot_id, trusted_keys=trusted
        )
        assignment = next(
            item
            for item in signed["work_plan"]["assignments"]
            if item["slot_id"] == slot_id
        )
        key = trusted[assignment["host_key_id"]]
        return {
            **prepared,
            "attestation_projection_additions": {
                "key_id": key["key_id"],
                "key_role": key["key_role"],
                "principal_id": key["principal_id"],
                "reviewer_role_or_null": key["reviewer_role_or_null"],
                "host_context_id_or_null": key["host_context_id_or_null"],
                "trust_domain_id": key["trust_domain_id"],
            },
            "required_scope": (
                f"dispatch:{signed['work_plan']['plan_id']}:{slot_id}"
            ),
            "truth_effect": "none",
        }

    def _packet_slot_path(self, signed_plan_id: str, slot_id: str) -> Path:
        if SIGNED_PLAN_ID_RE.fullmatch(signed_plan_id) is None:
            raise ValueError("verification signed plan id is invalid")
        if pv.ID_RE.fullmatch(slot_id) is None:
            raise ValueError("verification slot id is invalid")
        return self.packet_slots_dir / signed_plan_id / f"{slot_id}.json"

    def _fresh_nonce_owners(self) -> dict[str, str]:
        owners: dict[str, str] = {}
        sources = (
            (self.packets_dir, "vpk-*.json", "packet", "host_attestation"),
            (
                self.receipts_dir,
                "vmr-*.json",
                "receipt",
                "reviewer_attestation",
            ),
        )
        for directory, pattern, record_field, attestation_field in sources:
            if not directory.exists():
                continue
            for path in sorted(directory.glob(pattern)):
                if path.is_symlink() or not path.is_file():
                    raise ValueError("verification nonce registry source is unsafe")
                wrapper = self.store._read_json(path)
                record = wrapper.get(record_field, {})
                attestation = record.get(attestation_field, {})
                nonce = attestation.get("nonce")
                if not isinstance(nonce, str) or not nonce:
                    raise ValueError("verification stored attestation nonce is malformed")
                owner = record.get(
                    "packet_id" if record_field == "packet" else "receipt_id"
                )
                if nonce in owners and owners[nonce] != owner:
                    raise ValueError(
                        "verification freshness nonce was reused across immutable records"
                    )
                owners[nonce] = owner
        return owners

    def _require_fresh_nonce_available(
        self, attestation: dict[str, Any], *, owner_id: str
    ) -> None:
        existing = self._fresh_nonce_owners().get(attestation["nonce"])
        if existing is not None and existing != owner_id:
            raise ValueError("verification freshness nonce was replayed")

    def record_packet(
        self, signed_plan_id: str, packet: dict[str, Any]
    ) -> dict[str, Any]:
        signed = self.signed_plan(signed_plan_id, deep=False)
        trusted = self.trusted_keys()
        packet = pv.validate_dispatch_packet(
            packet,
            signed_plan=signed,
            trusted_keys=trusted,
            now=datetime.now(timezone.utc),
        )
        recorded_at = _utc_now()
        semantic = {
            "schema_version": 1,
            "contract_revision": LIFECYCLE_REVISION,
            "project_id": self.store.project_id(),
            "signed_plan_id": signed_plan_id,
            "slot_id": packet["slot_id"],
            "packet": packet,
            "recorded_at": recorded_at,
            "truth_effect": "none",
        }
        wrapper = {**semantic, "record_sha256": sha256_json(semantic)}
        with self.store.v5_mutation_lock(command="verification-packet-record"):
            self.initialize()
            path = self.packets_dir / f"{packet['packet_id']}.json"
            slot_path = self._packet_slot_path(signed_plan_id, packet["slot_id"])
            slot_path.parent.mkdir(parents=True, exist_ok=True)
            if slot_path.exists():
                head = self.store._read_json(slot_path)
                if head.get("packet_id") != packet["packet_id"]:
                    raise ValueError("verification plan slot already has another packet")
                return self.packet(packet["packet_id"], deep=True)
            self._require_fresh_nonce_available(
                packet["host_attestation"], owner_id=packet["packet_id"]
            )
            self.store._write_json_once(path, wrapper)
            self.store._write_json_once(
                slot_path,
                {
                    "schema_version": 1,
                    "contract_revision": LIFECYCLE_REVISION,
                    "signed_plan_id": signed_plan_id,
                    "slot_id": packet["slot_id"],
                    "packet_id": packet["packet_id"],
                    "packet_body_sha256": packet["body_sha256"],
                    "truth_effect": "none",
                },
            )
        return wrapper

    def packet(self, packet_id: str, *, deep: bool = False) -> dict[str, Any]:
        if PACKET_ID_RE.fullmatch(packet_id) is None:
            raise ValueError("verification packet id is invalid")
        path = self.packets_dir / f"{packet_id}.json"
        if path.is_symlink() or not path.is_file():
            raise KeyError(f"unknown verification packet: {packet_id}")
        stat = path.stat()
        fingerprint = (
            stat.st_dev,
            stat.st_ino,
            stat.st_size,
            stat.st_mtime_ns,
            stat.st_ctime_ns,
        )
        cached = self._packet_cache.get(packet_id)
        if not deep and cached is not None and cached[0] == fingerprint:
            # A cache is a byte-I/O optimization only, never cached authority.
            self.trusted_keys()
            return cached[1]
        trusted = self.trusted_keys()
        wrapper = self.store._read_json(path)
        fields = {
            "schema_version",
            "contract_revision",
            "project_id",
            "signed_plan_id",
            "slot_id",
            "packet",
            "recorded_at",
            "truth_effect",
            "record_sha256",
        }
        _exact(wrapper, fields, "verification packet wrapper")
        semantic = {
            key: value for key, value in wrapper.items() if key != "record_sha256"
        }
        if (
            wrapper["schema_version"] != 1
            or wrapper["contract_revision"] != LIFECYCLE_REVISION
            or wrapper["project_id"] != self.store.project_id()
            or wrapper["truth_effect"] != "none"
            or wrapper["record_sha256"] != sha256_json(semantic)
            or wrapper["packet"].get("packet_id") != packet_id
            or path.stem != packet_id
        ):
            raise ValueError("verification packet wrapper binding is invalid")
        signed = self.signed_plan(wrapper["signed_plan_id"], deep=deep)
        pv.validate_dispatch_packet(
            wrapper["packet"],
            signed_plan=signed,
            trusted_keys=trusted,
            now=_parse_time(wrapper["recorded_at"], "verification packet recorded_at"),
        )
        slot_path = self._packet_slot_path(
            wrapper["signed_plan_id"], wrapper["slot_id"]
        )
        if slot_path.is_symlink() or not slot_path.is_file():
            raise ValueError("verification packet slot binding is missing")
        head = self.store._read_json(slot_path)
        if (
            head.get("packet_id") != packet_id
            or head.get("packet_body_sha256") != wrapper["packet"]["body_sha256"]
        ):
            raise ValueError("verification packet slot binding drifted")
        self._packet_cache[packet_id] = (fingerprint, wrapper)
        return wrapper

    def _packet_for_slot(
        self, signed_plan_id: str, slot_id: str
    ) -> dict[str, Any]:
        path = self._packet_slot_path(signed_plan_id, slot_id)
        if path.is_symlink() or not path.is_file():
            raise ValueError("verification slot has no recorded host packet")
        head = self.store._read_json(path)
        return self.packet(head["packet_id"], deep=False)

    def prepare_receipt(
        self, signed_plan_id: str, slot_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        _exact(
            payload,
            {
                "obligation_results",
                "subject_hashes",
                "conflicts",
                "new_obligations",
            },
            "verification receipt preparation input",
        )
        signed = self.signed_plan(signed_plan_id, deep=False)
        trusted = self.trusted_keys()
        packet_wrapper = self._packet_for_slot(signed_plan_id, slot_id)
        prepared = pv.prepare_machine_receipt(
            signed_plan=signed,
            packet=packet_wrapper["packet"],
            obligation_results=payload["obligation_results"],
            subject_hashes=payload["subject_hashes"],
            conflicts=payload["conflicts"],
            new_obligations=payload["new_obligations"],
            trusted_keys=trusted,
            now=datetime.now(timezone.utc),
        )
        assignment = next(
            item
            for item in signed["work_plan"]["assignments"]
            if item["slot_id"] == slot_id
        )
        key = trusted[assignment["reviewer_key_id"]]
        return {
            **prepared,
            "attestation_projection_additions": {
                "key_id": key["key_id"],
                "key_role": key["key_role"],
                "principal_id": key["principal_id"],
                "reviewer_role_or_null": key["reviewer_role_or_null"],
                "host_context_id_or_null": key["host_context_id_or_null"],
                "trust_domain_id": key["trust_domain_id"],
            },
            "required_scope": (
                f"result:{signed['work_plan']['plan_id']}:{slot_id}"
            ),
            "truth_effect": "none",
        }

    def _receipt_slot_path(self, signed_plan_id: str, slot_id: str) -> Path:
        if SIGNED_PLAN_ID_RE.fullmatch(signed_plan_id) is None:
            raise ValueError("verification signed plan id is invalid")
        if pv.ID_RE.fullmatch(slot_id) is None:
            raise ValueError("verification slot id is invalid")
        return self.receipt_slots_dir / signed_plan_id / f"{slot_id}.json"

    def record_receipt(
        self, signed_plan_id: str, receipt: dict[str, Any]
    ) -> dict[str, Any]:
        signed = self.signed_plan(signed_plan_id, deep=False)
        trusted = self.trusted_keys()
        slot_id = receipt.get("slot_id")
        if not isinstance(slot_id, str):
            raise ValueError("verification receipt has no slot id")
        packet_wrapper = self._packet_for_slot(signed_plan_id, slot_id)
        receipt = pv.validate_receipt(
            receipt,
            signed_plan=signed,
            packet=packet_wrapper["packet"],
            trusted_keys=trusted,
            now=datetime.now(timezone.utc),
        )
        recorded_at = _utc_now()
        semantic = {
            "schema_version": 1,
            "contract_revision": LIFECYCLE_REVISION,
            "project_id": self.store.project_id(),
            "signed_plan_id": signed_plan_id,
            "slot_id": slot_id,
            "packet_id": packet_wrapper["packet"]["packet_id"],
            "receipt": receipt,
            "recorded_at": recorded_at,
            "truth_effect": "none",
        }
        wrapper = {**semantic, "record_sha256": sha256_json(semantic)}
        with self.store.v5_mutation_lock(command="verification-receipt-record"):
            self.initialize()
            path = self.receipts_dir / f"{receipt['receipt_id']}.json"
            slot_path = self._receipt_slot_path(signed_plan_id, slot_id)
            slot_path.parent.mkdir(parents=True, exist_ok=True)
            if slot_path.exists():
                head = self.store._read_json(slot_path)
                if head.get("receipt_id") != receipt["receipt_id"]:
                    raise ValueError("verification plan slot already has another receipt")
                return self.receipt(receipt["receipt_id"], deep=True)
            self._require_fresh_nonce_available(
                receipt["reviewer_attestation"], owner_id=receipt["receipt_id"]
            )
            self.store._write_json_once(path, wrapper)
            self.store._write_json_once(
                slot_path,
                {
                    "schema_version": 1,
                    "contract_revision": LIFECYCLE_REVISION,
                    "signed_plan_id": signed_plan_id,
                    "slot_id": slot_id,
                    "receipt_id": receipt["receipt_id"],
                    "receipt_body_sha256": receipt["body_sha256"],
                    "truth_effect": "none",
                },
            )
        return wrapper

    def receipt(self, receipt_id: str, *, deep: bool = False) -> dict[str, Any]:
        if RECEIPT_ID_RE.fullmatch(receipt_id) is None:
            raise ValueError("verification receipt id is invalid")
        path = self.receipts_dir / f"{receipt_id}.json"
        if path.is_symlink() or not path.is_file():
            raise KeyError(f"unknown verification receipt: {receipt_id}")
        stat = path.stat()
        fingerprint = (
            stat.st_dev,
            stat.st_ino,
            stat.st_size,
            stat.st_mtime_ns,
            stat.st_ctime_ns,
        )
        cached = self._receipt_cache.get(receipt_id)
        if not deep and cached is not None and cached[0] == fingerprint:
            # A cache is a byte-I/O optimization only, never cached authority.
            self.trusted_keys()
            return cached[1]
        trusted = self.trusted_keys()
        wrapper = self.store._read_json(path)
        fields = {
            "schema_version",
            "contract_revision",
            "project_id",
            "signed_plan_id",
            "slot_id",
            "packet_id",
            "receipt",
            "recorded_at",
            "truth_effect",
            "record_sha256",
        }
        _exact(wrapper, fields, "verification receipt wrapper")
        semantic = {
            key: value for key, value in wrapper.items() if key != "record_sha256"
        }
        if (
            wrapper["schema_version"] != 1
            or wrapper["contract_revision"] != LIFECYCLE_REVISION
            or wrapper["project_id"] != self.store.project_id()
            or wrapper["truth_effect"] != "none"
            or wrapper["record_sha256"] != sha256_json(semantic)
            or wrapper["receipt"].get("receipt_id") != receipt_id
            or path.stem != receipt_id
        ):
            raise ValueError("verification receipt wrapper binding is invalid")
        signed = self.signed_plan(wrapper["signed_plan_id"], deep=deep)
        packet_wrapper = self.packet(wrapper["packet_id"], deep=deep)
        pv.validate_receipt(
            wrapper["receipt"],
            signed_plan=signed,
            packet=packet_wrapper["packet"],
            trusted_keys=trusted,
            now=_parse_time(wrapper["recorded_at"], "verification receipt recorded_at"),
        )
        slot_path = self._receipt_slot_path(
            wrapper["signed_plan_id"], wrapper["slot_id"]
        )
        if slot_path.is_symlink() or not slot_path.is_file():
            raise ValueError("verification receipt slot binding is missing")
        head = self.store._read_json(slot_path)
        if (
            head.get("receipt_id") != receipt_id
            or head.get("receipt_body_sha256") != wrapper["receipt"]["body_sha256"]
        ):
            raise ValueError("verification receipt slot binding drifted")
        self._receipt_cache[receipt_id] = (fingerprint, wrapper)
        return wrapper

    def _receipt_for_slot(
        self, signed_plan_id: str, slot_id: str
    ) -> dict[str, Any]:
        path = self._receipt_slot_path(signed_plan_id, slot_id)
        if path.is_symlink() or not path.is_file():
            raise ValueError("verification slot has no recorded reviewer receipt")
        head = self.store._read_json(path)
        return self.receipt(head["receipt_id"], deep=False)

    @staticmethod
    def _aggregate_projection(
        signed: dict[str, Any],
        packets: list[dict[str, Any]],
        receipts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Independently replay the mechanical aggregate over signed receipts."""

        plan = signed["work_plan"]
        by_slot = {item["slot_id"]: item for item in receipts}
        missing = sorted(
            {item["slot_id"] for item in plan["assignments"]}.difference(by_slot)
        )
        results: dict[str, list[dict[str, Any]]] = {}
        for receipt in receipts:
            for row in receipt["obligation_results"]:
                results.setdefault(row["obligation_id"], []).append(
                    {"slot_id": receipt["slot_id"], **row}
                )
        unresolved: list[dict[str, Any]] = []
        rejects: list[dict[str, Any]] = []
        for obligation in plan["obligation_register"]["obligations"]:
            obligation_id = obligation["obligation_id"]
            rows = results.get(obligation_id, [])
            expected = {
                item["slot_id"]
                for item in plan["assignments"]
                if obligation_id in item["obligation_ids"]
            }
            if {item["slot_id"] for item in rows} != expected:
                unresolved.append(
                    {
                        "obligation_id": obligation_id,
                        "reason": "machine_receipt_coverage_incomplete",
                    }
                )
                continue
            for row in rows:
                if row["status"] == "reject":
                    rejects.append(
                        {
                            "obligation_id": obligation_id,
                            "slot_id": row["slot_id"],
                            "finding_ids": row["finding_ids"],
                        }
                    )
                elif row["status"] in {"needs_adjudication", "not_applicable"}:
                    unresolved.append(
                        {
                            "obligation_id": obligation_id,
                            "slot_id": row["slot_id"],
                            "reason": row["status"],
                        }
                    )
        conflicts = [
            {"receipt_id": item["receipt_id"], "conflict": conflict}
            for item in receipts
            for conflict in item["conflicts"]
        ]
        new_obligations = [
            {"receipt_id": item["receipt_id"], "new_obligation": obligation}
            for item in receipts
            for obligation in item["new_obligations"]
        ]
        eligible = not (missing or rejects or unresolved or conflicts or new_obligations)
        return {
            "schema_version": 1,
            "contract_revision": pv.AGGREGATE_REVISION,
            "protocol_revision": pv.CONTRACT_REVISION,
            "plan_id": plan["plan_id"],
            "plan_body_sha256": plan["body_sha256"],
            "signed_plan_id": signed["signed_plan_id"],
            "signed_plan_body_sha256": signed["body_sha256"],
            "packet_ids": sorted(item["packet_id"] for item in packets),
            "receipt_ids": sorted(item["receipt_id"] for item in receipts),
            "missing_slot_ids": missing,
            "rejects": sorted(rejects, key=pv.jcs_bytes),
            "unresolved": sorted(unresolved, key=pv.jcs_bytes),
            "conflicts": sorted(conflicts, key=pv.jcs_bytes),
            "new_obligations": sorted(new_obligations, key=pv.jcs_bytes),
            "aggregate_eligible_for_decision": eligible,
            "semantic_inference_performed": False,
            "majority_vote_performed": False,
            "truth_effect": "none",
            "fact_admission_effect": "none",
        }

    def aggregate(self, signed_plan_id: str) -> dict[str, Any]:
        signed = self.signed_plan(signed_plan_id, deep=True)
        release_id = self._release_id_for_plan(signed_plan_id)
        packets = [
            self._packet_for_slot(signed_plan_id, item["slot_id"])["packet"]
            for item in signed["work_plan"]["assignments"]
        ]
        receipts = [
            self._receipt_for_slot(signed_plan_id, item["slot_id"])["receipt"]
            for item in signed["work_plan"]["assignments"]
        ]
        projection = self._aggregate_projection(signed, packets, receipts)
        aggregate = pv._content_record(
            projection, prefix="vag", id_field="aggregate_id"
        )
        pv.validate_aggregate(
            aggregate,
            signed_plan=signed,
            trusted_keys=self.trusted_keys(),
        )
        release, capsule, _ = self._release_binding(release_id)
        semantic = {
            "schema_version": 1,
            "contract_revision": LIFECYCLE_REVISION,
            "project_id": self.store.project_id(),
            "release_id": release_id,
            "release_sha256": release["release_sha256"],
            "capsule_sha256": capsule["capsule_sha256"],
            "signed_plan_id": signed_plan_id,
            "signed_plan_body_sha256": signed["body_sha256"],
            "aggregate": aggregate,
            "created_at": _utc_now(),
            "truth_effect": "none",
        }
        wrapper = {**semantic, "record_sha256": sha256_json(semantic)}
        with self.store.v5_mutation_lock(command="verification-aggregate"):
            self.initialize()
            path = self.aggregates_dir / f"{aggregate['aggregate_id']}.json"
            head = self.aggregate_heads_dir / f"{release_id}.json"
            if head.exists():
                existing_head = self.store._read_json(head)
                if existing_head.get("aggregate_id") != aggregate["aggregate_id"]:
                    raise ValueError(
                        "Candidate Release already has another verification aggregate"
                    )
                return self.aggregate_record(aggregate["aggregate_id"], deep=True)
            self.store._write_json_once(path, wrapper)
            self.store._write_json_once(
                head,
                {
                    "schema_version": 1,
                    "contract_revision": LIFECYCLE_REVISION,
                    "release_id": release_id,
                    "aggregate_id": aggregate["aggregate_id"],
                    "aggregate_record_sha256": wrapper["record_sha256"],
                    "truth_effect": "none",
                },
            )
        return wrapper

    def aggregate_record(
        self, aggregate_id: str, *, deep: bool = False
    ) -> dict[str, Any]:
        if AGGREGATE_ID_RE.fullmatch(aggregate_id) is None:
            raise ValueError("verification aggregate id is invalid")
        path = self.aggregates_dir / f"{aggregate_id}.json"
        if path.is_symlink() or not path.is_file():
            raise KeyError(f"unknown verification aggregate: {aggregate_id}")
        wrapper = self.store._read_json(path)
        fields = {
            "schema_version",
            "contract_revision",
            "project_id",
            "release_id",
            "release_sha256",
            "capsule_sha256",
            "signed_plan_id",
            "signed_plan_body_sha256",
            "aggregate",
            "created_at",
            "truth_effect",
            "record_sha256",
        }
        _exact(wrapper, fields, "verification aggregate wrapper")
        semantic = {
            key: value for key, value in wrapper.items() if key != "record_sha256"
        }
        if (
            wrapper["schema_version"] != 1
            or wrapper["contract_revision"] != LIFECYCLE_REVISION
            or wrapper["project_id"] != self.store.project_id()
            or wrapper["truth_effect"] != "none"
            or wrapper["record_sha256"] != sha256_json(semantic)
            or wrapper["aggregate"].get("aggregate_id") != aggregate_id
            or path.stem != aggregate_id
        ):
            raise ValueError("verification aggregate wrapper binding is invalid")
        _parse_time(wrapper["created_at"], "verification aggregate created_at")
        signed = self.signed_plan(wrapper["signed_plan_id"], deep=deep)
        pv.validate_aggregate(
            wrapper["aggregate"],
            signed_plan=signed,
            trusted_keys=self.trusted_keys(),
        )
        if deep:
            release, capsule, _ = self._release_binding(wrapper["release_id"])
            if (
                wrapper["release_sha256"] != release["release_sha256"]
                or wrapper["capsule_sha256"] != capsule["capsule_sha256"]
                or wrapper["signed_plan_body_sha256"] != signed["body_sha256"]
            ):
                raise ValueError("verification aggregate release/capsule binding drifted")
            packets = [
                self.packet(packet_id, deep=True)["packet"]
                for packet_id in wrapper["aggregate"]["packet_ids"]
            ]
            receipts = [
                self.receipt(receipt_id, deep=True)["receipt"]
                for receipt_id in wrapper["aggregate"]["receipt_ids"]
            ]
            expected = pv._content_record(
                self._aggregate_projection(signed, packets, receipts),
                prefix="vag",
                id_field="aggregate_id",
            )
            if expected != wrapper["aggregate"]:
                raise ValueError("verification aggregate drifted from signed receipts")
        head = self.aggregate_heads_dir / f"{wrapper['release_id']}.json"
        if head.is_symlink() or not head.is_file():
            raise ValueError("verification aggregate release head is missing")
        head_record = self.store._read_json(head)
        if (
            head_record.get("aggregate_id") != aggregate_id
            or head_record.get("aggregate_record_sha256")
            != wrapper["record_sha256"]
        ):
            raise ValueError("verification aggregate release head drifted")
        return wrapper

    def require_eligible_for_release(
        self, release_id: str, aggregate_id: str
    ) -> dict[str, Any]:
        wrapper = self.aggregate_record(aggregate_id, deep=True)
        if (
            wrapper["release_id"] != release_id
            or wrapper["aggregate"]["aggregate_eligible_for_decision"] is not True
        ):
            raise ValueError(
                "Candidate Release lacks an eligible exact parallel-verification aggregate"
            )
        return wrapper

    def status(self, release_id: str) -> dict[str, Any]:
        # Status is a public integrity projection, not a per-file inventory.
        # Fail before returning a reassuring state when the project trust
        # registry contains cross-record identity aliases.
        self.trusted_keys()
        plan_head = self.plan_heads_dir / f"{release_id}.json"
        aggregate_head = self.aggregate_heads_dir / f"{release_id}.json"
        if not plan_head.exists():
            return {
                "release_id": release_id,
                "state": "awaiting_signed_plan",
                "truth_effect": "none",
            }
        plan_binding = self.store._read_json(plan_head)
        signed = self.signed_plan(plan_binding["signed_plan_id"], deep=True)
        slot_ids = [item["slot_id"] for item in signed["work_plan"]["assignments"]]
        packet_count = sum(
            self._packet_slot_path(signed["signed_plan_id"], slot_id).is_file()
            for slot_id in slot_ids
        )
        receipt_count = sum(
            self._receipt_slot_path(signed["signed_plan_id"], slot_id).is_file()
            for slot_id in slot_ids
        )
        result = {
            "release_id": release_id,
            "signed_plan_id": signed["signed_plan_id"],
            "slot_count": len(slot_ids),
            "packet_count": packet_count,
            "receipt_count": receipt_count,
            "state": (
                "awaiting_packets"
                if packet_count < len(slot_ids)
                else "awaiting_receipts"
                if receipt_count < len(slot_ids)
                else "ready_to_aggregate"
            ),
            "truth_effect": "none",
        }
        if aggregate_head.exists():
            head = self.store._read_json(aggregate_head)
            wrapper = self.aggregate_record(head["aggregate_id"], deep=True)
            result.update(
                {
                    "aggregate_id": wrapper["aggregate"]["aggregate_id"],
                    "aggregate_eligible_for_decision": wrapper["aggregate"][
                        "aggregate_eligible_for_decision"
                    ],
                    "state": (
                        "eligible_for_certification_decision"
                        if wrapper["aggregate"]["aggregate_eligible_for_decision"]
                        else "blocked_by_verification_findings"
                    ),
                }
            )
        return result

    def audit(self) -> dict[str, Any]:
        errors: list[str] = []
        counts = {"keys": 0, "plans": 0, "packets": 0, "receipts": 0, "aggregates": 0}
        checks = (
            (
                "keys",
                self.keys_dir,
                "vtk-*.json",
                lambda item: self._key_record(item),
            ),
            (
                "plans",
                self.plans_dir,
                "vsp-*.json",
                lambda item: self.signed_plan(item, deep=True),
            ),
            (
                "packets",
                self.packets_dir,
                "vpk-*.json",
                lambda item: self.packet(item, deep=True),
            ),
            (
                "receipts",
                self.receipts_dir,
                "vmr-*.json",
                lambda item: self.receipt(item, deep=True),
            ),
            (
                "aggregates",
                self.aggregates_dir,
                "vag-*.json",
                lambda item: self.aggregate_record(item, deep=True),
            ),
        )
        try:
            self.trusted_keys()
        except Exception as exc:
            errors.append(f"trusted_key_registry: {exc}")
        try:
            self._fresh_nonce_owners()
        except Exception as exc:
            errors.append(f"freshness_nonce_registry: {exc}")
        for label, directory, pattern, validator in checks:
            if not directory.exists():
                continue
            for path in sorted(directory.glob(pattern)):
                counts[label] += 1
                try:
                    validator(path.stem)
                except Exception as exc:
                    errors.append(f"{label}:{path.stem}: {exc}")
        return {
            "schema_version": 1,
            "contract_revision": LIFECYCLE_REVISION,
            "scope": "verification_work_partition_not_research_scheduling",
            "counts": counts,
            "errors": errors,
            "current_ok": not errors,
            "truth_effect": "none",
            "fact_admission_effect": "none",
        }

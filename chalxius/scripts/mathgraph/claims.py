from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .contracts import (
    CLAIM_ID_RE,
    CONVENTION_ID_RE,
    POLICY_REVISION_V4,
    SHA256_RE,
    require_exact_keys,
    require_string,
    sha256_bytes,
    sha256_json,
    validate_claim_id,
    validate_convention_id,
)


CLAIM_KINDS = {"published_literal", "researcher_variant"}
AUTHORITIES = {"literal_source", "researcher_defined", "official_correction"}

_SOURCE_FIELDS = {
    "title",
    "version",
    "artifact_sha256",
    "locator",
    "retrieved_at",
}
_CLAIM_FIELDS = {
    "schema_version",
    "policy_revision",
    "claim_id",
    "kind",
    "title",
    "statement",
    "statement_sha256",
    "source",
    "convention_profile_id",
    "parent_claim_id",
    "variant_diff",
    "authority",
    "author_confirmed",
}
_CONVENTION_FIELDS = {
    "schema_version",
    "policy_revision",
    "convention_id",
    "theory",
    "source_version",
    "source_artifact_sha256",
    "authority",
    "parent_convention_id",
    "dimensions",
}


def _claim_id(payload: dict[str, Any]) -> str:
    body = {key: value for key, value in payload.items() if key != "claim_id"}
    return "claim-" + sha256_json(body)[:16]


def _convention_id(payload: dict[str, Any]) -> str:
    body = {key: value for key, value in payload.items() if key != "convention_id"}
    return "conv-" + sha256_json(body)[:16]


class ClaimRegistry:
    def __init__(self, project_root: Path | str) -> None:
        self.project_root = Path(project_root).resolve()
        self.claims_dir = self.project_root / "claims" / "by-hash"
        self.conventions_dir = self.project_root / "conventions" / "by-hash"
        self.events_path = self.project_root / "claims" / "events.jsonl"

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"expected one JSON object in {path}")
        return payload

    @staticmethod
    def _write_json_once(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        rendered = (
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            fd = os.open(path, flags, 0o600)
        except FileExistsError:
            if not path.is_file() or path.is_symlink() or path.read_bytes() != rendered:
                raise ValueError(f"immutable registry collision at {path}")
            return
        with os.fdopen(fd, "wb") as handle:
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())

    @staticmethod
    def _append_event(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def initialize(self) -> None:
        self.claims_dir.mkdir(parents=True, exist_ok=True)
        self.conventions_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def validate_convention(payload: dict[str, Any]) -> dict[str, Any]:
        require_exact_keys(
            payload,
            required=_CONVENTION_FIELDS,
            label="convention profile",
        )
        if payload.get("schema_version") != 1:
            raise ValueError("convention schema_version must be 1")
        if payload.get("policy_revision") != POLICY_REVISION_V4:
            raise ValueError("convention policy_revision mismatch")
        convention_id = validate_convention_id(
            require_string(payload, "convention_id")
        )
        if convention_id != _convention_id(payload):
            raise ValueError("convention id/hash mismatch")
        require_string(payload, "theory")
        require_string(payload, "source_version")
        artifact_hash = require_string(payload, "source_artifact_sha256")
        if SHA256_RE.fullmatch(artifact_hash) is None:
            raise ValueError("convention source_artifact_sha256 is invalid")
        authority = require_string(payload, "authority")
        if authority not in AUTHORITIES:
            raise ValueError("convention authority is invalid")
        parent = payload.get("parent_convention_id")
        if parent is not None:
            validate_convention_id(parent)
        dimensions = payload.get("dimensions")
        if not isinstance(dimensions, dict) or not dimensions or any(
            not isinstance(key, str)
            or not key
            or not isinstance(value, str)
            or not value
            for key, value in dimensions.items()
        ):
            raise ValueError(
                "convention dimensions must be a nonempty string-to-string map"
            )
        return payload

    @staticmethod
    def validate_claim(payload: dict[str, Any]) -> dict[str, Any]:
        require_exact_keys(payload, required=_CLAIM_FIELDS, label="source claim")
        if payload.get("schema_version") != 1:
            raise ValueError("claim schema_version must be 1")
        if payload.get("policy_revision") != POLICY_REVISION_V4:
            raise ValueError("claim policy_revision mismatch")
        claim_id = validate_claim_id(require_string(payload, "claim_id"))
        if claim_id != _claim_id(payload):
            raise ValueError("claim id/hash mismatch")
        kind = require_string(payload, "kind")
        if kind not in CLAIM_KINDS:
            raise ValueError("claim kind is invalid")
        require_string(payload, "title")
        statement = require_string(payload, "statement")
        statement_sha = require_string(payload, "statement_sha256")
        if (
            SHA256_RE.fullmatch(statement_sha) is None
            or statement_sha != sha256_bytes(statement.encode("utf-8"))
        ):
            raise ValueError("claim statement_sha256 does not match exact UTF-8")
        source = payload.get("source")
        if not isinstance(source, dict):
            raise ValueError("claim source must be an object")
        require_exact_keys(source, required=_SOURCE_FIELDS, label="claim source")
        for key in ("title", "version", "locator", "retrieved_at"):
            require_string(source, key)
        artifact_hash = require_string(source, "artifact_sha256")
        if SHA256_RE.fullmatch(artifact_hash) is None:
            raise ValueError("claim source artifact_sha256 is invalid")
        validate_convention_id(require_string(payload, "convention_profile_id"))
        parent = payload.get("parent_claim_id")
        diffs = payload.get("variant_diff")
        if not isinstance(diffs, list) or any(not isinstance(item, dict) for item in diffs):
            raise ValueError("claim variant_diff must be a list of objects")
        authority = require_string(payload, "authority")
        if authority not in AUTHORITIES:
            raise ValueError("claim authority is invalid")
        if not isinstance(payload.get("author_confirmed"), bool):
            raise ValueError("claim author_confirmed must be boolean")
        if kind == "published_literal":
            if parent is not None or diffs:
                raise ValueError(
                    "published literal claim cannot have a parent or variant diff"
                )
            if authority != "literal_source":
                raise ValueError("published literal authority must be literal_source")
            if "arxiv:" in source["version"].lower() and not any(
                marker in source["version"].lower() for marker in ("v1", "v2", "v3", "v4", "v5", "v6", "v7", "v8", "v9")
            ):
                raise ValueError("published claim must pin an exact source version")
        else:
            if not isinstance(parent, str):
                raise ValueError("researcher variant requires parent_claim_id")
            validate_claim_id(parent)
            if not diffs:
                raise ValueError("researcher variant requires a nonempty variant_diff")
            if authority != "researcher_defined":
                raise ValueError(
                    "researcher variant authority must be researcher_defined"
                )
            if payload["author_confirmed"]:
                raise ValueError(
                    "author_confirmed requires a separately stored author-confirmation artifact"
                )
            for index, diff in enumerate(diffs, 1):
                require_exact_keys(
                    diff,
                    required={"field", "from", "to", "authority"},
                    label=f"variant_diff[{index}]",
                )
                for key in ("field", "from", "to", "authority"):
                    require_string(diff, key, allow_empty=(key in {"from", "to"}))
                if diff["authority"] != "researcher_defined":
                    raise ValueError("variant diff authority must be researcher_defined")
        return payload

    def add_convention(
        self,
        payload: dict[str, Any],
        *,
        actor: str,
    ) -> str:
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError("convention actor must be nonempty")
        body = dict(payload)
        body.setdefault("schema_version", 1)
        body.setdefault("policy_revision", POLICY_REVISION_V4)
        body.setdefault("parent_convention_id", None)
        if "convention_id" not in body:
            body["convention_id"] = _convention_id(body)
        self.validate_convention(body)
        parent = body["parent_convention_id"]
        if parent is not None:
            self.show_convention(parent)
        path = self.conventions_dir / f"{body['convention_id']}.json"
        self._write_json_once(path, body)
        self._append_event(
            self.events_path,
            {
                "event": "convention_added",
                "object_id": body["convention_id"],
                "object_sha256": sha256_json(body),
                "actor": actor.strip(),
            },
        )
        return str(body["convention_id"])

    def add_claim(self, payload: dict[str, Any], *, actor: str) -> str:
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError("claim actor must be nonempty")
        body = dict(payload)
        body.setdefault("schema_version", 1)
        body.setdefault("policy_revision", POLICY_REVISION_V4)
        body.setdefault("parent_claim_id", None)
        body.setdefault("variant_diff", [])
        body.setdefault("author_confirmed", False)
        statement = require_string(body, "statement")
        body.setdefault("statement_sha256", sha256_bytes(statement.encode("utf-8")))
        if "claim_id" not in body:
            body["claim_id"] = _claim_id(body)
        self.validate_claim(body)
        self.show_convention(body["convention_profile_id"])
        parent = body["parent_claim_id"]
        if parent is not None:
            self.show_claim(parent)
        path = self.claims_dir / f"{body['claim_id']}.json"
        self._write_json_once(path, body)
        self._append_event(
            self.events_path,
            {
                "event": "claim_added",
                "object_id": body["claim_id"],
                "object_sha256": sha256_json(body),
                "actor": actor.strip(),
            },
        )
        return str(body["claim_id"])

    def create_variant(
        self,
        parent_claim_id: str,
        payload: dict[str, Any],
        *,
        actor: str,
    ) -> str:
        parent = self.show_claim(parent_claim_id)
        body = {
            "schema_version": 1,
            "policy_revision": POLICY_REVISION_V4,
            "kind": "researcher_variant",
            "title": payload.get("title", f"Variant of {parent['title']}"),
            "statement": payload.get("statement"),
            "source": payload.get(
                "source",
                {
                    "title": f"Derived from {parent_claim_id}",
                    "version": "researcher-defined",
                    "artifact_sha256": parent["source"]["artifact_sha256"],
                    "locator": parent_claim_id,
                    "retrieved_at": parent["source"]["retrieved_at"],
                },
            ),
            "convention_profile_id": payload.get(
                "convention_profile_id", parent["convention_profile_id"]
            ),
            "parent_claim_id": parent_claim_id,
            "variant_diff": payload.get("variant_diff", []),
            "authority": "researcher_defined",
            "author_confirmed": False,
        }
        if not isinstance(body["statement"], str):
            raise ValueError("researcher variant requires an exact statement")
        body["statement_sha256"] = sha256_bytes(body["statement"].encode("utf-8"))
        body["claim_id"] = _claim_id(body)
        return self.add_claim(body, actor=actor)

    def show_claim(self, claim_id: str) -> dict[str, Any]:
        claim_id = validate_claim_id(claim_id)
        path = self.claims_dir / f"{claim_id}.json"
        if not path.exists():
            raise KeyError(f"unknown source claim: {claim_id}")
        return self.validate_claim(self._read_json(path))

    def show_convention(self, convention_id: str) -> dict[str, Any]:
        convention_id = validate_convention_id(convention_id)
        path = self.conventions_dir / f"{convention_id}.json"
        if not path.exists():
            raise KeyError(f"unknown convention profile: {convention_id}")
        return self.validate_convention(self._read_json(path))

    def audit(self) -> dict[str, Any]:
        errors: list[str] = []
        claims = 0
        conventions = 0
        for path in sorted(self.conventions_dir.glob("conv-*.json")):
            try:
                payload = self.validate_convention(self._read_json(path))
                if path.stem != payload["convention_id"]:
                    raise ValueError("filename/id mismatch")
                conventions += 1
            except Exception as exc:
                errors.append(f"{path.name}: {exc}")
        for path in sorted(self.claims_dir.glob("claim-*.json")):
            try:
                payload = self.validate_claim(self._read_json(path))
                if path.stem != payload["claim_id"]:
                    raise ValueError("filename/id mismatch")
                self.show_convention(payload["convention_profile_id"])
                if payload["parent_claim_id"] is not None:
                    self.show_claim(payload["parent_claim_id"])
                claims += 1
            except Exception as exc:
                errors.append(f"{path.name}: {exc}")
        return {
            "ok": not errors,
            "errors": errors,
            "claims": claims,
            "conventions": conventions,
        }

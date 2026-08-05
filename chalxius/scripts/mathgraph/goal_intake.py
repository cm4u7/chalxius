from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .contracts import SHA256_RE, canonical_json_bytes, sha256_json, validate_campaign_id


GOAL_INTAKE_INTENT_REVISION = "chalxius-bf-goal-intake-intent-1"
GOAL_INTAKE_EFFECT_REVISION = "chalxius-bf-goal-intake-effect-1"
GOAL_INTAKE_EFFECT_RECEIPT_REVISION = (
    "chalxius-bf-goal-intake-effect-receipt-1"
)
GOAL_INTAKE_TERMINAL_REVISION = "chalxius-bf-goal-intake-terminal-receipt-1"
GOAL_INTAKE_CAMPAIGN_MARKER_REVISION = (
    "chalxius-bf-goal-intake-campaign-marker-1"
)
GOAL_INTAKE_ACTIVATION_LINK_REVISION = (
    "chalxius-bf-goal-intake-activation-link-1"
)
GOAL_INTAKE_RESEARCH_BINDING_REVISION = (
    "chalxius-bf-goal-intake-research-binding-1"
)

GOAL_INTAKE_EFFECT_KINDS = {
    "campaign",
    "activation",
    "planning_snapshot",
    "frontier_projection",
}
GOAL_INTAKE_TOKEN_PREFIX = "bfit-"
GOAL_INTAKE_EFFECT_PREFIX = "bfie-"


def _exact(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{label} fields are not exact")
    return value


def _sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{label} is not a sha256 digest")
    return value


def _token(value: Any) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith(GOAL_INTAKE_TOKEN_PREFIX)
        or SHA256_RE.fullmatch(value[len(GOAL_INTAKE_TOKEN_PREFIX) :]) is None
    ):
        raise ValueError("goal-intake token is invalid")
    return value


def _effect_id(value: Any) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith(GOAL_INTAKE_EFFECT_PREFIX)
        or SHA256_RE.fullmatch(value[len(GOAL_INTAKE_EFFECT_PREFIX) :]) is None
    ):
        raise ValueError("goal-intake effect id is invalid")
    return value


def _payload_binding(kind: str, payload: Any) -> str:
    if kind in {"planning_snapshot", "frontier_projection"}:
        if not isinstance(payload, dict):
            raise ValueError(f"goal-intake {kind} effect payload is invalid")
        semantic_sha256 = _sha(
            payload.get("semantic_sha256"),
            f"goal-intake {kind} semantic binding",
        )
        id_key, prefix = (
            ("planning_snapshot_id", "bfps-")
            if kind == "planning_snapshot"
            else ("projection_id", "bfp-")
        )
        if payload.get(id_key) != prefix + semantic_sha256:
            raise ValueError(f"goal-intake {kind} content id mismatch")
        without_hash = {
            key: item for key, item in payload.items() if key != "record_sha256"
        }
        if payload.get("record_sha256") != sha256_json(without_hash):
            raise ValueError(f"goal-intake {kind} record hash mismatch")
        semantic = {
            key: item
            for key, item in payload.items()
            if key
            not in {
                id_key,
                "created_at",
                "semantic_sha256",
                "record_sha256",
            }
        }
        if semantic_sha256 != sha256_json(semantic):
            raise ValueError(f"goal-intake {kind} semantic hash mismatch")
        return semantic_sha256
    return sha256_json(payload)


def seal_goal_intake_effect(*, kind: str, payload: Any) -> dict[str, Any]:
    if kind not in GOAL_INTAKE_EFFECT_KINDS:
        raise ValueError("goal-intake effect kind is invalid")
    binding = _payload_binding(kind, payload)
    effect_id = GOAL_INTAKE_EFFECT_PREFIX + sha256_json(
        {
            "revision": GOAL_INTAKE_EFFECT_REVISION,
            "effect_kind": kind,
            "payload_binding_sha256": binding,
        }
    )
    semantic = {
        "revision": GOAL_INTAKE_EFFECT_REVISION,
        "effect_id": effect_id,
        "effect_kind": kind,
        "payload_binding_sha256": binding,
        "payload": payload,
        "truth_effect": "none",
        "fact_admission_effect": "none",
    }
    return {**semantic, "record_sha256": sha256_json(semantic)}


def validate_goal_intake_effect(value: Any) -> dict[str, Any]:
    effect = _exact(
        value,
        {
            "revision",
            "effect_id",
            "effect_kind",
            "payload_binding_sha256",
            "payload",
            "truth_effect",
            "fact_admission_effect",
            "record_sha256",
        },
        "goal-intake effect",
    )
    if effect["revision"] != GOAL_INTAKE_EFFECT_REVISION:
        raise ValueError("goal-intake effect revision mismatch")
    kind = effect["effect_kind"]
    if kind not in GOAL_INTAKE_EFFECT_KINDS:
        raise ValueError("goal-intake effect kind is invalid")
    effect_id = _effect_id(effect["effect_id"])
    binding = _payload_binding(kind, effect["payload"])
    if effect["payload_binding_sha256"] != binding:
        raise ValueError("goal-intake effect payload binding mismatch")
    expected_id = GOAL_INTAKE_EFFECT_PREFIX + sha256_json(
        {
            "revision": GOAL_INTAKE_EFFECT_REVISION,
            "effect_kind": kind,
            "payload_binding_sha256": binding,
        }
    )
    if effect_id != expected_id:
        raise ValueError("goal-intake effect content id mismatch")
    if effect["truth_effect"] != "none" or effect["fact_admission_effect"] != "none":
        raise ValueError("goal-intake effect crosses the truth boundary")
    semantic = {key: item for key, item in effect.items() if key != "record_sha256"}
    if effect["record_sha256"] != sha256_json(semantic):
        raise ValueError("goal-intake effect record hash mismatch")
    return effect


def seal_goal_intake_intent(
    *,
    project_id: str,
    request: dict[str, Any],
    campaign_id: str,
    campaign_resolution: str,
    campaign_created: bool,
    effect_ids: dict[str, str],
) -> dict[str, Any]:
    semantic = {
        "revision": GOAL_INTAKE_INTENT_REVISION,
        "project_id": project_id,
        "request": request,
        "campaign_id": validate_campaign_id(campaign_id),
        "campaign_resolution": campaign_resolution,
        "campaign_created": bool(campaign_created),
        "effect_ids": dict(effect_ids),
        "truth_effect": "none",
        "fact_admission_effect": "none",
    }
    token = GOAL_INTAKE_TOKEN_PREFIX + sha256_json(semantic)
    without_hash = {**semantic, "intake_token": token}
    return {**without_hash, "record_sha256": sha256_json(without_hash)}


def validate_goal_intake_intent(value: Any) -> dict[str, Any]:
    intent = _exact(
        value,
        {
            "revision",
            "project_id",
            "request",
            "campaign_id",
            "campaign_resolution",
            "campaign_created",
            "effect_ids",
            "truth_effect",
            "fact_admission_effect",
            "intake_token",
            "record_sha256",
        },
        "goal-intake intent",
    )
    if intent["revision"] != GOAL_INTAKE_INTENT_REVISION:
        raise ValueError("goal-intake intent revision mismatch")
    if not isinstance(intent["project_id"], str) or not intent["project_id"]:
        raise ValueError("goal-intake intent project binding is invalid")
    if not isinstance(intent["request"], dict):
        raise ValueError("goal-intake intent request is invalid")
    validate_campaign_id(intent["campaign_id"])
    if not isinstance(intent["campaign_resolution"], str) or not intent["campaign_resolution"]:
        raise ValueError("goal-intake intent Campaign resolution is invalid")
    if not isinstance(intent["campaign_created"], bool):
        raise ValueError("goal-intake intent Campaign creation flag is invalid")
    refs = intent["effect_ids"]
    if not isinstance(refs, dict) or set(refs) != GOAL_INTAKE_EFFECT_KINDS:
        raise ValueError("goal-intake intent effect inventory is invalid")
    for value in refs.values():
        _effect_id(value)
    if intent["truth_effect"] != "none" or intent["fact_admission_effect"] != "none":
        raise ValueError("goal-intake intent crosses the truth boundary")
    semantic = {
        key: item
        for key, item in intent.items()
        if key not in {"intake_token", "record_sha256"}
    }
    expected_token = GOAL_INTAKE_TOKEN_PREFIX + sha256_json(semantic)
    if _token(intent["intake_token"]) != expected_token:
        raise ValueError("goal-intake intent content id mismatch")
    without_hash = {key: item for key, item in intent.items() if key != "record_sha256"}
    if intent["record_sha256"] != sha256_json(without_hash):
        raise ValueError("goal-intake intent record hash mismatch")
    return intent


class GoalIntakeTransactionStore:
    """Fail-atomic, receipt-gated storage for ordinary research-goal intake.

    Intent, effects, and effect receipts are deliberately non-selectable.  A
    single terminal receipt is the only normal-read visibility gate.  All
    recovery methods are invoked by the explicit retrying writer; read paths
    only validate already-terminal state.
    """

    def __init__(self, store_or_root: Any) -> None:
        if callable(getattr(store_or_root, "_write_json_once", None)):
            self.store = store_or_root
            self.project_root = Path(store_or_root.root).resolve()
        else:
            self.store = None
            self.project_root = Path(store_or_root).resolve()
        self.root = self.project_root / "governance" / "brave-future" / "goal-intakes"
        self.intents_dir = self.root / "intents" / "by-token"
        self.effects_dir = self.root / "effects" / "by-id"
        self.effect_receipts_dir = self.root / "effect-receipts" / "by-token"
        self.terminals_dir = self.root / "terminal-receipts" / "by-token"
        self.activation_links_dir = self.root / "activation-links" / "by-campaign"

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"goal-intake object is unsafe: {path}")
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"goal-intake object is not a JSON object: {path}")
        return value

    @staticmethod
    def _write_atomic(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(canonical_json_bytes(payload) + b"\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except BaseException:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise

    def _write_once(self, path: Path, payload: dict[str, Any]) -> None:
        if path.exists():
            if self._read_json(path) != payload:
                raise ValueError(f"goal-intake immutable object collision: {path}")
            return
        if path.is_symlink():
            raise ValueError(f"goal-intake immutable object is unsafe: {path}")
        if self.store is not None:
            self.store._write_json_once(path, payload)
        else:
            self._write_atomic(path, payload)

    def _intent_path(self, token: str) -> Path:
        return self.intents_dir / f"{_token(token)}.json"

    def _effect_path(self, effect_id: str) -> Path:
        return self.effects_dir / f"{_effect_id(effect_id)}.json"

    def _effect_receipt_path(self, token: str, kind: str) -> Path:
        if kind not in GOAL_INTAKE_EFFECT_KINDS:
            raise ValueError("goal-intake effect kind is invalid")
        return self.effect_receipts_dir / _token(token) / f"{kind}.json"

    def _terminal_path(self, token: str) -> Path:
        return self.terminals_dir / f"{_token(token)}.json"

    def activation_link_path(self, campaign_id: str) -> Path:
        return self.activation_links_dir / f"{validate_campaign_id(campaign_id)}.json"

    def write_intent(self, intent: dict[str, Any]) -> dict[str, Any]:
        intent = validate_goal_intake_intent(intent)
        self._write_once(self._intent_path(intent["intake_token"]), intent)
        return intent

    def write_effect(self, effect: dict[str, Any]) -> dict[str, Any]:
        desired = validate_goal_intake_effect(effect)
        path = self._effect_path(desired["effect_id"])
        if path.exists():
            existing = validate_goal_intake_effect(self._read_json(path))
            if (
                existing["effect_kind"] != desired["effect_kind"]
                or existing["payload_binding_sha256"]
                != desired["payload_binding_sha256"]
            ):
                raise ValueError("goal-intake effect semantic collision")
            return existing
        self._write_once(path, desired)
        return desired

    def load_effect(self, effect_id: str) -> dict[str, Any]:
        return validate_goal_intake_effect(self._read_json(self._effect_path(effect_id)))

    def write_effect_receipt(
        self,
        *,
        token: str,
        effect: dict[str, Any],
        side_effect_state: str,
    ) -> dict[str, Any]:
        token = _token(token)
        effect = validate_goal_intake_effect(effect)
        semantic = {
            "revision": GOAL_INTAKE_EFFECT_RECEIPT_REVISION,
            "intake_token": token,
            "effect_id": effect["effect_id"],
            "effect_kind": effect["effect_kind"],
            "effect_record_sha256": effect["record_sha256"],
            "side_effect_state": side_effect_state,
            "truth_effect": "none",
            "fact_admission_effect": "none",
        }
        receipt = {**semantic, "receipt_sha256": sha256_json(semantic)}
        self._write_once(
            self._effect_receipt_path(token, effect["effect_kind"]), receipt
        )
        return receipt

    def _validate_effect_receipt(
        self, value: Any, *, token: str, effect: dict[str, Any]
    ) -> dict[str, Any]:
        receipt = _exact(
            value,
            {
                "revision",
                "intake_token",
                "effect_id",
                "effect_kind",
                "effect_record_sha256",
                "side_effect_state",
                "truth_effect",
                "fact_admission_effect",
                "receipt_sha256",
            },
            "goal-intake effect receipt",
        )
        if receipt["revision"] != GOAL_INTAKE_EFFECT_RECEIPT_REVISION:
            raise ValueError("goal-intake effect receipt revision mismatch")
        if receipt["intake_token"] != _token(token):
            raise ValueError("goal-intake effect receipt token mismatch")
        effect = validate_goal_intake_effect(effect)
        if (
            receipt["effect_id"] != effect["effect_id"]
            or receipt["effect_kind"] != effect["effect_kind"]
            or receipt["effect_record_sha256"] != effect["record_sha256"]
            or not isinstance(receipt["side_effect_state"], str)
            or not receipt["side_effect_state"]
        ):
            raise ValueError("goal-intake effect receipt binding mismatch")
        if receipt["truth_effect"] != "none" or receipt["fact_admission_effect"] != "none":
            raise ValueError("goal-intake effect receipt crosses the truth boundary")
        semantic = {key: item for key, item in receipt.items() if key != "receipt_sha256"}
        if receipt["receipt_sha256"] != sha256_json(semantic):
            raise ValueError("goal-intake effect receipt hash mismatch")
        return receipt

    def write_activation_link(
        self, *, token: str, campaign_effect_id: str, activation_effect: dict[str, Any]
    ) -> dict[str, Any] | None:
        activation_effect = validate_goal_intake_effect(activation_effect)
        payload = activation_effect["payload"]
        if payload.get("operation") != "activate":
            return None
        campaign_id = validate_campaign_id(payload.get("campaign_id"))
        semantic = {
            "revision": GOAL_INTAKE_ACTIVATION_LINK_REVISION,
            "campaign_id": campaign_id,
            "intake_token": _token(token),
            "campaign_effect_id": _effect_id(campaign_effect_id),
            "activation_effect_id": activation_effect["effect_id"],
        }
        link = {**semantic, "link_sha256": sha256_json(semantic)}
        self._write_once(self.activation_link_path(campaign_id), link)
        return link

    def _validate_activation_link(self, value: Any) -> dict[str, Any]:
        link = _exact(
            value,
            {
                "revision",
                "campaign_id",
                "intake_token",
                "campaign_effect_id",
                "activation_effect_id",
                "link_sha256",
            },
            "goal-intake activation link",
        )
        if link["revision"] != GOAL_INTAKE_ACTIVATION_LINK_REVISION:
            raise ValueError("goal-intake activation link revision mismatch")
        validate_campaign_id(link["campaign_id"])
        _token(link["intake_token"])
        _effect_id(link["campaign_effect_id"])
        _effect_id(link["activation_effect_id"])
        semantic = {key: item for key, item in link.items() if key != "link_sha256"}
        if link["link_sha256"] != sha256_json(semantic):
            raise ValueError("goal-intake activation link hash mismatch")
        return link

    def write_terminal_receipt(
        self,
        *,
        intent: dict[str, Any],
        effects: dict[str, dict[str, Any]],
        effect_receipts: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        intent = validate_goal_intake_intent(intent)
        token = intent["intake_token"]
        effect_record_sha256s: dict[str, str] = {}
        effect_receipt_sha256s: dict[str, str] = {}
        for kind in sorted(GOAL_INTAKE_EFFECT_KINDS):
            effect = validate_goal_intake_effect(effects[kind])
            if effect["effect_id"] != intent["effect_ids"][kind]:
                raise ValueError("goal-intake terminal effect inventory mismatch")
            receipt = self._validate_effect_receipt(
                effect_receipts[kind], token=token, effect=effect
            )
            effect_record_sha256s[kind] = effect["record_sha256"]
            effect_receipt_sha256s[kind] = receipt["receipt_sha256"]
        semantic = {
            "revision": GOAL_INTAKE_TERMINAL_REVISION,
            "intake_token": token,
            "project_id": intent["project_id"],
            "campaign_id": intent["campaign_id"],
            "intent_record_sha256": intent["record_sha256"],
            "effect_ids": intent["effect_ids"],
            "effect_record_sha256s": effect_record_sha256s,
            "effect_receipt_sha256s": effect_receipt_sha256s,
            "terminal_state": "committed",
            "truth_effect": "none",
            "fact_admission_effect": "none",
        }
        terminal = {**semantic, "receipt_sha256": sha256_json(semantic)}
        self._write_once(self._terminal_path(token), terminal)
        return terminal

    def terminal_exists(self, token: str) -> bool:
        path = self._terminal_path(token)
        if path.is_symlink():
            raise ValueError("goal-intake terminal receipt is unsafe")
        return path.is_file()

    def terminal_gate(
        self,
        token: str,
        *,
        campaign_id: str | None = None,
        required_effect_ids: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Validate only the small terminal visibility gate, without repair."""

        token = _token(token)
        terminal = _exact(
            self._read_json(self._terminal_path(token)),
            {
                "revision",
                "intake_token",
                "project_id",
                "campaign_id",
                "intent_record_sha256",
                "effect_ids",
                "effect_record_sha256s",
                "effect_receipt_sha256s",
                "terminal_state",
                "truth_effect",
                "fact_admission_effect",
                "receipt_sha256",
            },
            "goal-intake terminal receipt",
        )
        if terminal["revision"] != GOAL_INTAKE_TERMINAL_REVISION:
            raise ValueError("goal-intake terminal receipt revision mismatch")
        if terminal["intake_token"] != token or terminal["terminal_state"] != "committed":
            raise ValueError("goal-intake terminal state binding mismatch")
        validate_campaign_id(terminal["campaign_id"])
        if campaign_id is not None and terminal["campaign_id"] != validate_campaign_id(
            campaign_id
        ):
            raise ValueError("goal-intake terminal Campaign binding mismatch")
        if (
            not isinstance(terminal["effect_ids"], dict)
            or set(terminal["effect_ids"]) != GOAL_INTAKE_EFFECT_KINDS
        ):
            raise ValueError("goal-intake terminal effect inventory is invalid")
        for effect_id in terminal["effect_ids"].values():
            _effect_id(effect_id)
        if required_effect_ids is not None:
            for kind, effect_id in required_effect_ids.items():
                if (
                    kind not in GOAL_INTAKE_EFFECT_KINDS
                    or terminal["effect_ids"].get(kind) != _effect_id(effect_id)
                ):
                    raise ValueError("goal-intake terminal effect gate mismatch")
        if terminal["truth_effect"] != "none" or terminal["fact_admission_effect"] != "none":
            raise ValueError("goal-intake terminal receipt crosses the truth boundary")
        semantic = {key: item for key, item in terminal.items() if key != "receipt_sha256"}
        if terminal["receipt_sha256"] != sha256_json(semantic):
            raise ValueError("goal-intake terminal receipt hash mismatch")
        return terminal

    def validate_intake_receipt(self, token: str) -> dict[str, Any]:
        """Pure-read validation of one terminal goal-intake transaction."""

        token = _token(token)
        terminal = self.terminal_gate(token)
        intent = validate_goal_intake_intent(self._read_json(self._intent_path(token)))
        if (
            intent["record_sha256"] != terminal["intent_record_sha256"]
            or intent["project_id"] != terminal["project_id"]
            or intent["campaign_id"] != terminal["campaign_id"]
            or intent["effect_ids"] != terminal["effect_ids"]
        ):
            raise ValueError("goal-intake terminal/intent binding mismatch")
        if set(terminal["effect_record_sha256s"]) != GOAL_INTAKE_EFFECT_KINDS or set(
            terminal["effect_receipt_sha256s"]
        ) != GOAL_INTAKE_EFFECT_KINDS:
            raise ValueError("goal-intake terminal effect receipt inventory is invalid")
        effects: dict[str, dict[str, Any]] = {}
        for kind in sorted(GOAL_INTAKE_EFFECT_KINDS):
            effect = self.load_effect(intent["effect_ids"][kind])
            if (
                effect["effect_kind"] != kind
                or effect["record_sha256"]
                != terminal["effect_record_sha256s"][kind]
            ):
                raise ValueError("goal-intake terminal effect binding mismatch")
            receipt = self._validate_effect_receipt(
                self._read_json(self._effect_receipt_path(token, kind)),
                token=token,
                effect=effect,
            )
            if receipt["receipt_sha256"] != terminal["effect_receipt_sha256s"][kind]:
                raise ValueError("goal-intake terminal effect-receipt binding mismatch")
            effects[kind] = effect
        campaign_payload = effects["campaign"]["payload"]
        if campaign_payload.get("operation") == "create":
            marker_path = (
                self.project_root
                / "campaigns"
                / intent["campaign_id"]
                / "GOAL_INTAKE.json"
            )
            marker = validate_goal_intake_campaign_marker(self._read_json(marker_path))
            if (
                marker["intake_token"] != token
                or marker["campaign_id"] != intent["campaign_id"]
                or marker["campaign_effect_id"] != effects["campaign"]["effect_id"]
            ):
                raise ValueError("goal-intake Campaign marker binding mismatch")
        activation_payload = effects["activation"]["payload"]
        if activation_payload.get("operation") == "activate":
            link = self._validate_activation_link(
                self._read_json(self.activation_link_path(intent["campaign_id"]))
            )
            if (
                link["intake_token"] != token
                or link["campaign_effect_id"] != effects["campaign"]["effect_id"]
                or link["activation_effect_id"] != effects["activation"]["effect_id"]
            ):
                raise ValueError("goal-intake activation link binding mismatch")
        return {
            **terminal,
            "validated": True,
            "campaign_resolution": intent["campaign_resolution"],
            "campaign_created": intent["campaign_created"],
            "objective_sha256": intent["request"]["objective_sha256"],
        }

    def load_committed_transaction(
        self, token: str
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, dict[str, Any]]]:
        terminal = self.validate_intake_receipt(token)
        intent = validate_goal_intake_intent(
            self._read_json(self._intent_path(token))
        )
        effects = {
            kind: self.load_effect(intent["effect_ids"][kind])
            for kind in GOAL_INTAKE_EFFECT_KINDS
        }
        return terminal, intent, effects

    def find_matching_committed(
        self,
        *,
        request: dict[str, Any],
        campaign_id: str,
        planning_snapshot_semantic_sha256: str,
        frontier_projection_semantic_sha256: str,
    ) -> str | None:
        """Find an already-terminal semantic retry without changing state."""

        campaign_id = validate_campaign_id(campaign_id)
        _sha(planning_snapshot_semantic_sha256, "planning snapshot semantic digest")
        _sha(frontier_projection_semantic_sha256, "frontier projection semantic digest")
        if not self.terminals_dir.exists():
            return None
        if self.terminals_dir.is_symlink() or not self.terminals_dir.is_dir():
            raise ValueError("goal-intake terminal receipt store is unsafe")
        for path in sorted(self.terminals_dir.glob("bfit-*.json")):
            token = path.stem
            _terminal, intent, effects = self.load_committed_transaction(token)
            if intent["campaign_id"] != campaign_id or intent["request"] != request:
                continue
            snapshot = effects["planning_snapshot"]["payload"]
            projection = effects["frontier_projection"]["payload"]
            if (
                snapshot.get("semantic_sha256")
                == planning_snapshot_semantic_sha256
                and projection.get("semantic_sha256")
                == frontier_projection_semantic_sha256
            ):
                return token
        return None

    def is_committed(self, token: str) -> bool:
        if not self.terminal_exists(token):
            return False
        self.terminal_gate(token)
        return True

    def committed_activation(self, campaign_id: str) -> dict[str, Any] | None:
        campaign_id = validate_campaign_id(campaign_id)
        path = self.activation_link_path(campaign_id)
        if not path.exists():
            if path.is_symlink():
                raise ValueError("goal-intake activation link is unsafe")
            return None
        link = self._validate_activation_link(self._read_json(path))
        if not self.terminal_exists(link["intake_token"]):
            return None
        self.terminal_gate(
            link["intake_token"],
            campaign_id=campaign_id,
            required_effect_ids={
                "campaign": link["campaign_effect_id"],
                "activation": link["activation_effect_id"],
            },
        )
        effect = self.load_effect(link["activation_effect_id"])
        payload = effect["payload"]
        if payload.get("campaign_id") != campaign_id or payload.get("operation") != "activate":
            raise ValueError("goal-intake activation effect is invalid")
        return {**payload, "intake_token": link["intake_token"], "effect_id": effect["effect_id"]}

    @staticmethod
    def _checkpoint(_name: str) -> None:
        """Test seam for injected process interruption; production is a no-op."""


def validate_goal_intake_research_binding(value: Any) -> dict[str, Any]:
    binding = _exact(
        value,
        {
            "revision",
            "project_id",
            "intake_token",
            "campaign_id",
            "objective_sha256",
            "terminal_receipt_sha256",
            "truth_effect",
            "fact_admission_effect",
            "binding_sha256",
        },
        "goal-intake Research binding",
    )
    if binding["revision"] != GOAL_INTAKE_RESEARCH_BINDING_REVISION:
        raise ValueError("goal-intake Research binding revision mismatch")
    if not isinstance(binding["project_id"], str) or not binding["project_id"]:
        raise ValueError("goal-intake Research project binding is invalid")
    _token(binding["intake_token"])
    validate_campaign_id(binding["campaign_id"])
    _sha(binding["objective_sha256"], "goal-intake Research objective binding")
    _sha(
        binding["terminal_receipt_sha256"],
        "goal-intake Research terminal receipt binding",
    )
    if binding["truth_effect"] != "none" or binding["fact_admission_effect"] != "none":
        raise ValueError("goal-intake Research binding crosses the truth boundary")
    semantic = {key: item for key, item in binding.items() if key != "binding_sha256"}
    if binding["binding_sha256"] != sha256_json(semantic):
        raise ValueError("goal-intake Research binding hash mismatch")
    return binding


def build_goal_intake_research_binding(
    store_or_root: Any,
    intake_token: str,
) -> dict[str, Any]:
    """Consume a committed intake and return its exact Research lineage handoff."""

    terminal = GoalIntakeTransactionStore(store_or_root).validate_intake_receipt(
        intake_token
    )
    semantic = {
        "revision": GOAL_INTAKE_RESEARCH_BINDING_REVISION,
        "project_id": terminal["project_id"],
        "intake_token": terminal["intake_token"],
        "campaign_id": terminal["campaign_id"],
        "objective_sha256": terminal["objective_sha256"],
        "terminal_receipt_sha256": terminal["receipt_sha256"],
        "truth_effect": "none",
        "fact_admission_effect": "none",
    }
    return validate_goal_intake_research_binding(
        {**semantic, "binding_sha256": sha256_json(semantic)}
    )


def seal_goal_intake_campaign_marker(
    *, token: str, campaign_id: str, campaign_effect_id: str
) -> dict[str, Any]:
    semantic = {
        "revision": GOAL_INTAKE_CAMPAIGN_MARKER_REVISION,
        "intake_token": _token(token),
        "campaign_id": validate_campaign_id(campaign_id),
        "campaign_effect_id": _effect_id(campaign_effect_id),
    }
    return {**semantic, "marker_sha256": sha256_json(semantic)}


def validate_goal_intake_campaign_marker(value: Any) -> dict[str, Any]:
    marker = _exact(
        value,
        {
            "revision",
            "intake_token",
            "campaign_id",
            "campaign_effect_id",
            "marker_sha256",
        },
        "goal-intake Campaign marker",
    )
    if marker["revision"] != GOAL_INTAKE_CAMPAIGN_MARKER_REVISION:
        raise ValueError("goal-intake Campaign marker revision mismatch")
    _token(marker["intake_token"])
    validate_campaign_id(marker["campaign_id"])
    _effect_id(marker["campaign_effect_id"])
    semantic = {key: item for key, item in marker.items() if key != "marker_sha256"}
    if marker["marker_sha256"] != sha256_json(semantic):
        raise ValueError("goal-intake Campaign marker hash mismatch")
    return marker

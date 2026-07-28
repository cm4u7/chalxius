from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, ContextManager

from .computations import ExperimentManager, _ledger_prefix
from .contracts import (
    POLICY_REVISION_V4,
    SHA256_RE,
    contained_path,
    require_exact_keys,
    require_relative_path,
    require_string,
    sha256_bytes,
    sha256_json,
    validate_experiment_id,
)
from .event_ledger import ExperimentEventLedger
from .protocol import DEFAULT_HARD_CAPS
from .v5_lifecycle import V5_POLICY_REVISION


_VIEW_FIELDS = {
    "_v5_experiment_view",
    "_v5_original_campaign_id",
    "work_dir_relpath",
    "artifact_dir_relpath",
    "hard_caps",
    "assignment_sha256",
    "memory_id",
    "mode",
    "goal_relation",
    "return_relpath",
    "host_task_scope_id",
}


class V5ExperimentManager(ExperimentManager):
    """Reuse the mature experiment ledger through a V5 task-card adapter."""

    def __init__(
        self,
        store: Any,
        *,
        mutation_lock: Callable[[], ContextManager[Any]],
        read_lock: Callable[[], ContextManager[Any]],
    ) -> None:
        super().__init__(
            store.root,
            mutation_lock=mutation_lock,
            read_lock=read_lock,
        )
        self.store = store

    @staticmethod
    def _v5_caps(task_card: dict[str, Any]) -> dict[str, int]:
        artifact = task_card["artifact_capability"]
        caps = dict(DEFAULT_HARD_CAPS)
        caps["max_checkpoint_files"] = min(
            caps["max_checkpoint_files"], artifact["max_files"]
        )
        caps["max_checkpoint_bytes_each"] = min(
            caps["max_checkpoint_bytes_each"], artifact["max_file_bytes"]
        )
        caps["max_checkpoint_bytes_total"] = min(
            caps["max_checkpoint_bytes_total"], artifact["max_total_bytes"]
        )
        return caps

    @staticmethod
    def _raw_card(task_card: dict[str, Any]) -> dict[str, Any]:
        if task_card.get("_v5_experiment_view") is True:
            raw = {
                key: value
                for key, value in task_card.items()
                if key not in _VIEW_FIELDS
            }
            raw["campaign_id"] = task_card.get("_v5_original_campaign_id")
            return raw
        return dict(task_card)

    def _validate_bound_task_card(
        self,
        task_card: dict[str, Any],
        *,
        allow_historical_estimate_policy: bool = False,
        require_active_work_unit: bool = False,
    ) -> dict[str, Any]:
        del allow_historical_estimate_policy
        raw = self._raw_card(task_card)
        self.store.v5_lifecycle().validate_task_card(raw)
        if require_active_work_unit:
            self.store.reasoning_modes().require_work_unit_active(
                raw["round_id"]
            )
        _, manifest = self.store.v5_lifecycle()._round_manifest(raw["round_id"])
        assignment = self.store.v5_lifecycle()._assignment(
            manifest, raw["assignment_id"]
        )
        card_path = contained_path(
            self.project_root,
            assignment["task_card_relpath"],
            "V5 experiment task card path",
        )
        if (
            card_path.is_symlink()
            or not card_path.is_file()
            or self.store._read_json(card_path) != raw
            or sha256_bytes(card_path.read_bytes())
            != assignment["task_card_sha256"]
        ):
            raise ValueError("V5 experiment card differs from the frozen task card")
        for key in list(task_card):
            if key in _VIEW_FIELDS:
                task_card.pop(key)
        task_card.update(raw)
        task_card.update(
            {
                "_v5_experiment_view": True,
                "_v5_original_campaign_id": raw["campaign_id"],
                "work_dir_relpath": raw["artifact_capability"][
                    "work_dir_relpath"
                ],
                "artifact_dir_relpath": raw["artifact_capability"][
                    "artifact_dir_relpath"
                ],
                "hard_caps": self._v5_caps(raw),
                "assignment_sha256": assignment["assignment_sha256"],
                "memory_id": raw["research_id"],
                "campaign_id": (
                    raw["campaign_id"]
                    if raw["campaign_id"] is not None
                    else "campaign-"
                    + sha256_json(
                        [
                            "v5-task-local-experiment-governance",
                            raw["round_id"],
                            raw["assignment_id"],
                        ]
                    )[:12]
                ),
                "mode": raw["work_mode"],
                "goal_relation": raw["requested_claim_relation"],
                "return_relpath": raw["return_contract"]["return_relpath"],
            }
        )
        host_scope = raw["control_plane"].get("host_task_scope_id")
        if host_scope is not None:
            task_card["host_task_scope_id"] = host_scope
        return task_card

    def governance_task_id(self, task_card: dict[str, Any]) -> str:
        self._validate_bound_task_card(task_card)
        semantic = {
            "schema_version": 5,
            "policy_revision": V5_POLICY_REVISION,
            "project_id": task_card["project_id"],
            "round_id": task_card["round_id"],
            "assignment_id": task_card["assignment_id"],
            "host_task_scope_id": task_card.get("host_task_scope_id"),
        }
        return "taskgov-v5-" + sha256_json(semantic)[:32]

    def start(
        self,
        *,
        task_card: dict[str, Any],
        manifest: dict[str, Any],
    ) -> dict[str, Any]:
        with self._mutation_lock():
            self._validate_bound_task_card(
                task_card,
                require_active_work_unit=True,
            )
            hard_caps = self._require_hard_caps(task_card)
            body = dict(manifest)
            body.setdefault("schema_version", 1)
            body.setdefault("policy_revision", POLICY_REVISION_V4)
            body["assignment_id"] = task_card["assignment_id"]
            if "experiment_id" not in body:
                body["experiment_id"] = "experiment-" + sha256_json(body)[:16]
            self.validate_manifest(body, assignment_id=task_card["assignment_id"])
            directory = self._directory(
                task_card=task_card, experiment_id=body["experiment_id"]
            )
            manifest_path = directory / "manifest.json"
            if manifest_path.exists():
                if self._read_json(manifest_path) != body:
                    raise ValueError("immutable V5 experiment manifest collision")
            else:
                started = {
                    "event": "started",
                    "stage": "",
                    "completed_units": 0,
                    "total_units_or_null": None,
                    "cpu_seconds": 0.0,
                    "wall_seconds": 0.0,
                    "rss_bytes": 0,
                    "latest_check": "V5 task-local manifest validated",
                }
                directory.mkdir(parents=True, exist_ok=True)
                (directory / "checkpoints").mkdir(parents=True, exist_ok=True)
                self._write_json_once(manifest_path, body)
                ExperimentEventLedger(
                    directory / "events.jsonl", hard_caps=hard_caps
                ).mutate(
                    lambda session: (
                        session.append(started) if session.event_count == 0 else None
                    )
                )
            return {
                "experiment_id": body["experiment_id"],
                "directory": str(directory),
                "status": "started",
                "workflow_evidence_version": 5,
                "truth_effect": "none",
            }

    def status(
        self,
        *,
        task_card: dict[str, Any],
        experiment_id: str,
    ) -> dict[str, Any]:
        with self._read_lock():
            self._validate_bound_task_card(task_card)
            directory = self._directory(
                task_card=task_card, experiment_id=experiment_id
            )
            manifest = self.validate_manifest(
                self._read_json(directory / "manifest.json"),
                assignment_id=task_card["assignment_id"],
            )
            events = self._read_jsonl(directory / "events.jsonl")
            finalized = (directory / "final_receipt.json").exists()
            return {
                "experiment_id": experiment_id,
                "objective": manifest["objective"],
                "status": (
                    "finalized"
                    if finalized
                    else (
                        "failed"
                        if events and events[-1].get("event") == "failed"
                        else "running"
                    )
                ),
                "completed_stages": [
                    item.get("stage")
                    for item in events
                    if item.get("event") == "stage_completed"
                ],
                "event_count": len(events),
                "latest_event": events[-1] if events else None,
                "task_governance": {
                    "governance_task_id": self.governance_task_id(task_card),
                    "state": self._governance_state(task_card)["state"],
                    "admission_authority": False,
                },
            }

    def _validate_final_receipt(
        self,
        *,
        task_card: dict[str, Any],
        receipt_path: Path,
        require_terminal_event: bool = True,
    ) -> dict[str, Any]:
        self._validate_bound_task_card(task_card)
        if receipt_path.is_symlink() or not receipt_path.is_file():
            raise ValueError("V5 experiment final receipt is missing or unsafe")
        payload = self._read_json(receipt_path)
        required = {
            "schema_version",
            "policy_revision",
            "project_id",
            "experiment_id",
            "assignment_id",
            "task_card_sha256",
            "selected_outputs",
            "manifest_sha256",
            "experiment_event_count",
            "experiment_events_sha256",
            "hard_caps_sha256",
            "checkpoint_file_count",
            "checkpoint_bytes_total",
            "checkpoint_inventory_sha256",
            "truth_effect",
            "receipt_sha256",
        }
        require_exact_keys(payload, required=required, label="V5 experiment receipt")
        if (
            payload.get("schema_version") != 5
            or payload.get("policy_revision") != V5_POLICY_REVISION
            or payload.get("project_id") != self.store.project_id()
            or payload.get("assignment_id") != task_card["assignment_id"]
            or payload.get("truth_effect") != "none"
        ):
            raise ValueError("V5 experiment final receipt binding mismatch")
        experiment_id = validate_experiment_id(payload["experiment_id"])
        if receipt_path.parent.name != experiment_id:
            raise ValueError("V5 experiment receipt directory/id mismatch")
        card_path = self.project_root / "rounds" / task_card["round_id"] / "task-cards" / f"{task_card['assignment_id']}.json"
        if payload["task_card_sha256"] != sha256_bytes(card_path.read_bytes()):
            raise ValueError("V5 experiment receipt task-card hash mismatch")
        manifest_path = receipt_path.parent / "manifest.json"
        if payload["manifest_sha256"] != sha256_bytes(manifest_path.read_bytes()):
            raise ValueError("V5 experiment receipt manifest hash mismatch")
        self.validate_manifest(
            self._read_json(manifest_path), assignment_id=task_card["assignment_id"]
        )
        caps = self._require_hard_caps(task_card)
        if payload["hard_caps_sha256"] != sha256_json(caps):
            raise ValueError("V5 experiment receipt hard-cap mismatch")
        inventory = self._checkpoint_inventory(receipt_path.parent, caps)
        if (
            payload["checkpoint_file_count"] != inventory["file_count"]
            or payload["checkpoint_bytes_total"] != inventory["bytes_total"]
            or payload["checkpoint_inventory_sha256"] != inventory["sha256"]
        ):
            raise ValueError("V5 experiment receipt checkpoint inventory mismatch")
        prefix = _ledger_prefix(
            receipt_path.parent / "events.jsonl", payload["experiment_event_count"]
        )
        if prefix["sha256"] != payload["experiment_events_sha256"]:
            raise ValueError("V5 experiment receipt event-prefix mismatch")
        events = self._read_jsonl(receipt_path.parent / "events.jsonl")
        if require_terminal_event and (
            len(events) != payload["experiment_event_count"] + 1
            or events[-1].get("event") != "finalized"
            or events[-1].get("receipt_sha256") != payload["receipt_sha256"]
        ):
            raise ValueError("V5 experiment receipt lacks its terminal event")
        outputs = payload["selected_outputs"]
        if not isinstance(outputs, list) or not outputs:
            raise ValueError("V5 experiment receipt requires selected outputs")
        artifact_root = contained_path(
            self.project_root,
            task_card["artifact_dir_relpath"],
            "V5 experiment artifact directory",
        )
        seen: set[tuple[str, str]] = set()
        for output in outputs:
            require_exact_keys(
                output,
                required={"path", "sha256"},
                label="V5 selected output",
            )
            path = contained_path(
                self.project_root, output["path"], "V5 selected output"
            )
            digest = output["sha256"]
            if (
                SHA256_RE.fullmatch(digest) is None
                or not path.is_relative_to(artifact_root)
                or path.is_symlink()
                or not path.is_file()
                or sha256_bytes(path.read_bytes()) != digest
            ):
                raise ValueError("V5 selected output bytes/hash/path mismatch")
            pair = (output["path"], digest)
            if pair in seen:
                raise ValueError("V5 selected output is duplicated")
            seen.add(pair)
        semantic = {key: value for key, value in payload.items() if key != "receipt_sha256"}
        if payload["receipt_sha256"] != sha256_json(semantic):
            raise ValueError("V5 experiment receipt content hash mismatch")
        return payload

    def finalize(
        self,
        *,
        task_card: dict[str, Any],
        experiment_id: str,
        selected_paths: list[str],
    ) -> dict[str, Any]:
        with self._mutation_lock():
            self._validate_bound_task_card(task_card)
            if not selected_paths:
                raise ValueError("V5 experiment finalize requires selected outputs")
            directory = self._directory(
                task_card=task_card, experiment_id=experiment_id
            )
            manifest = self.validate_manifest(
                self._read_json(directory / "manifest.json"),
                assignment_id=task_card["assignment_id"],
            )
            receipt_path = directory / "final_receipt.json"
            if receipt_path.exists():
                receipt = self._validate_final_receipt(
                    task_card=task_card,
                    receipt_path=receipt_path,
                    require_terminal_event=False,
                )
                finalized_semantic = {
                    "schema_version": 5,
                    "policy_revision": V5_POLICY_REVISION,
                    "event": "finalized",
                    "receipt_sha256": receipt["receipt_sha256"],
                }
                finalized = {
                    **finalized_semantic,
                    "event_id": sha256_json(finalized_semantic),
                }
                ExperimentEventLedger(
                    directory / "events.jsonl",
                    hard_caps=self._require_hard_caps(task_card),
                ).mutate(
                    lambda session: (
                        None
                        if session.find(finalized["event_id"]) is not None
                        else session.append(finalized)
                    )
                )
                return self._validate_final_receipt(
                    task_card=task_card, receipt_path=receipt_path
                )
            events = self._read_jsonl(directory / "events.jsonl")
            if events and events[-1].get("event") == "failed":
                raise ValueError("failed V5 experiment requires a validated resume")
            if not any(item.get("event") == "stage_completed" for item in events):
                raise ValueError("V5 experiment requires a completed stage")
            artifact_dir = contained_path(
                self.project_root,
                task_card["artifact_dir_relpath"],
                "V5 task-card artifact directory",
            )
            artifact_dir.mkdir(parents=True, exist_ok=True)
            planned = []
            destinations: set[Path] = set()
            for selected in selected_paths:
                relative = require_relative_path(selected, "selected V5 output")
                source = (directory / Path(*relative.parts)).resolve()
                if (
                    not source.is_relative_to(directory)
                    or source.is_symlink()
                    or not source.is_file()
                ):
                    raise ValueError("selected V5 experiment output is missing or unsafe")
                destination = artifact_dir / source.name
                if destination in destinations:
                    raise ValueError("selected V5 output names collide")
                destinations.add(destination)
                raw = source.read_bytes()
                if destination.exists() and destination.read_bytes() != raw:
                    raise ValueError("V5 finalized output name collision")
                planned.append((destination, raw))
            outputs = []
            for destination, raw in planned:
                self._write_once(destination, raw)
                outputs.append(
                    {
                        "path": destination.relative_to(self.project_root).as_posix(),
                        "sha256": sha256_bytes(raw),
                    }
                )
            prefix = _ledger_prefix(directory / "events.jsonl")
            caps = self._require_hard_caps(task_card)
            inventory = self._checkpoint_inventory(directory, caps)
            card_path = self.project_root / "rounds" / task_card["round_id"] / "task-cards" / f"{task_card['assignment_id']}.json"
            semantic = {
                "schema_version": 5,
                "policy_revision": V5_POLICY_REVISION,
                "project_id": self.store.project_id(),
                "experiment_id": experiment_id,
                "assignment_id": manifest["assignment_id"],
                "task_card_sha256": sha256_bytes(card_path.read_bytes()),
                "selected_outputs": sorted(outputs, key=lambda item: item["path"]),
                "manifest_sha256": sha256_bytes((directory / "manifest.json").read_bytes()),
                "experiment_event_count": prefix["event_count"],
                "experiment_events_sha256": prefix["sha256"],
                "hard_caps_sha256": sha256_json(caps),
                "checkpoint_file_count": inventory["file_count"],
                "checkpoint_bytes_total": inventory["bytes_total"],
                "checkpoint_inventory_sha256": inventory["sha256"],
                "truth_effect": "none",
            }
            receipt = {**semantic, "receipt_sha256": sha256_json(semantic)}
            finalized_semantic = {
                "schema_version": 5,
                "policy_revision": V5_POLICY_REVISION,
                "event": "finalized",
                "receipt_sha256": receipt["receipt_sha256"],
            }
            finalized = {
                **finalized_semantic,
                "event_id": sha256_json(finalized_semantic),
            }
            ledger = ExperimentEventLedger(
                directory / "events.jsonl", hard_caps=caps
            )
            ledger.mutate(lambda session: session.preflight(finalized))
            self._write_json_once(receipt_path, receipt)
            ledger.mutate(
                lambda session: (
                    None
                    if session.find(finalized["event_id"]) is not None
                    else session.append(finalized)
                )
            )
            return self._validate_final_receipt(
                task_card=task_card, receipt_path=receipt_path
            )

    def audit_all(self) -> dict[str, Any]:
        errors: list[str] = []
        experiments = 0
        for card_path in sorted(self.store.rounds_dir.glob("*/task-cards/*.json")):
            try:
                card = self.store._read_json(card_path)
                self._validate_bound_task_card(card)
                root = contained_path(
                    self.project_root,
                    card["work_dir_relpath"],
                    "V5 experiment work directory",
                ) / "experiments"
                if not root.exists():
                    continue
                for directory in sorted(root.glob("experiment-*")):
                    experiments += 1
                    self.validate_manifest(
                        self._read_json(directory / "manifest.json"),
                        assignment_id=card["assignment_id"],
                    )
                    ledger = ExperimentEventLedger(
                        directory / "events.jsonl",
                        hard_caps=self._require_hard_caps(card),
                    ).audit_read_only()
                    errors.extend(
                        f"{directory.name}: {message}" for message in ledger["errors"]
                    )
                    receipt = directory / "final_receipt.json"
                    if receipt.exists():
                        self._validate_final_receipt(
                            task_card=card, receipt_path=receipt
                        )
            except Exception as exc:
                errors.append(f"{card_path}: {exc}")
        return {
            "schema_version": 5,
            "experiment_count": experiments,
            "ok": not errors,
            "errors": errors,
            "truth_effect": "none",
        }

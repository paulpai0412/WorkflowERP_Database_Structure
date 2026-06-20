from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any


USER_STEP_MAPPING: dict[int, dict[str, Any]] = {
    1: {
        "title": "Source-to-Output Logic",
        "label": "source_to_output_logic",
        "phases": [0, 1, 2, 3],
    },
    2: {
        "title": "SQL Query",
        "label": "sql_query",
        "phases": [4, 5],
    },
    3: {
        "title": "Data Result and Report Design",
        "label": "data_result_and_report_design",
        "phases": [6, 7, 8, 9],
    },
    4: {
        "title": "Final Delivery",
        "label": "final_delivery",
        "phases": [10, 11, 12],
    },
}


GATE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "phase_3_field_formula": {
        "user_step": 1,
        "required_artifacts": ["checkpoints/01b_field_formula_classification.json"],
        "required_validators": [
            "requirement_understanding_reviewer",
            "schema_mapping_reviewer",
        ],
        "confirmation_checkpoint": "field_formula_classification",
        "allowed_next_actions": ["generate_sql", "request_changes"],
    },
    "phase_4_sql_review": {
        "user_step": 2,
        "required_artifacts": ["sql/query.sql", "checkpoints/02_sql_review.json"],
        "required_validators": ["sql_safety_reviewer", "schema_mapping_reviewer"],
        "confirmation_checkpoint": "sql_review",
        "allowed_next_actions": ["execute_select", "request_changes"],
    },
    "phase_6_data_preview": {
        "user_step": 3,
        "required_artifacts": [
            "checkpoints/03a_raw_data_preview.json",
            "checkpoints/03b_enriched_data_preview.json",
        ],
        "required_validators": ["db_execution_reviewer", "data_preview_reviewer"],
        "confirmation_checkpoint": "enriched_data_preview",
        "allowed_next_actions": ["render_report_design", "request_changes"],
    },
    "phase_12_delivery": {
        "user_step": 4,
        "required_artifacts": [
            "report/delivery/report.html",
            "report/delivery/report.xlsx",
            "review/final-review.json",
        ],
        "required_validators": [
            "report_content_reviewer",
            "visual_taste_reviewer",
            "react_technical_reviewer",
            "delivery_reviewer",
        ],
        "confirmation_checkpoint": "final_review",
        "allowed_next_actions": ["deliver", "request_changes"],
    },
}


class GateBlockedError(RuntimeError):
    def __init__(self, gate: str, evaluation: dict[str, Any]) -> None:
        self.gate = gate
        self.evaluation = evaluation
        reasons = ", ".join(evaluation.get("blocking_reason", [])) or "gate is blocked"
        super().__init__(f"{gate} cannot advance: {reasons}")


@dataclass(frozen=True)
class GateEvaluation:
    gate: str
    status: str
    user_step: int
    required_artifacts: list[str]
    required_validators: list[str]
    confirmation: dict[str, Any]
    allowed_next_actions: list[str]
    blocking_reason: list[str]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("gate")
        return data


def initialize_state_machine(state: dict[str, Any]) -> dict[str, Any]:
    initialized = deepcopy(state)
    initialized.setdefault("current_user_step", 1)
    initialized.setdefault("current_internal_phase", 0)
    initialized.setdefault("user_step_mapping", deepcopy(USER_STEP_MAPPING))
    initialized.setdefault("artifact_status", {})
    initialized.setdefault("validator_results", [])
    initialized.setdefault("confirmation_identity", {})
    initialized.setdefault("blocking_repair_request", None)
    initialized.setdefault("delivery_status", "not_ready")
    initialized.setdefault("allowed_next_actions", ["prepare_source_logic"])
    initialized["gate_status"] = _merge_gate_status(initialized)
    initialized["phase_status"] = {
        gate: entry["status"] for gate, entry in initialized["gate_status"].items()
    }
    initialized["required_artifacts"] = {
        gate: deepcopy(definition["required_artifacts"])
        for gate, definition in GATE_DEFINITIONS.items()
    }
    initialized["required_validators"] = {
        gate: deepcopy(definition["required_validators"])
        for gate, definition in GATE_DEFINITIONS.items()
    }
    return initialized


def evaluate_gate(state: dict[str, Any], gate: str) -> dict[str, Any]:
    if gate not in GATE_DEFINITIONS:
        raise KeyError(f"Unknown gate: {gate}")

    definition = GATE_DEFINITIONS[gate]
    blocking_reason: list[str] = []

    blocking_repair_request = state.get("blocking_repair_request")
    if blocking_repair_request:
        if not isinstance(blocking_repair_request, dict) or blocking_repair_request.get("gate") in (None, gate):
            blocking_reason.append("blocking_repair_request")

    artifact_status = state.get("artifact_status") or {}
    for artifact in definition["required_artifacts"]:
        if not _artifact_is_present(artifact_status.get(artifact)):
            blocking_reason.append(f"missing_artifact:{artifact}")

    validator_results = _validator_status_by_role(state.get("validator_results") or [])
    for validator in definition["required_validators"]:
        if not _validator_passed(validator_results.get(validator)):
            blocking_reason.append(f"missing_validator:{validator}")

    checkpoint_id = definition["confirmation_checkpoint"]
    confirmation = _confirmation_for_checkpoint(state.get("confirmation_identity") or {}, checkpoint_id)
    if confirmation is None:
        blocking_reason.append(f"missing_confirmation:{checkpoint_id}")
        payload_hash = None
    else:
        payload_hash = confirmation.get("payload_hash") if isinstance(confirmation, dict) else None

    status = "complete" if not blocking_reason else "blocked"
    return GateEvaluation(
        gate=gate,
        status=status,
        user_step=definition["user_step"],
        required_artifacts=deepcopy(definition["required_artifacts"]),
        required_validators=deepcopy(definition["required_validators"]),
        confirmation={
            "required": True,
            "checkpoint_id": checkpoint_id,
            "payload_hash": payload_hash,
        },
        allowed_next_actions=deepcopy(definition["allowed_next_actions"]),
        blocking_reason=blocking_reason,
    ).to_dict()


def assert_can_advance(state: dict[str, Any], gate: str) -> dict[str, Any]:
    evaluation = evaluate_gate(state, gate)
    if evaluation["status"] != "complete":
        raise GateBlockedError(gate, evaluation)
    return evaluation


def _artifact_is_present(status: Any) -> bool:
    if isinstance(status, dict):
        return status.get("status") in ("complete", "ready", "present", "pass", "passed") or status.get("present") is True
    return status in ("complete", "ready", "present", "pass", "passed", True)


def _validator_passed(status: Any) -> bool:
    if isinstance(status, dict):
        status = status.get("status")
    return status in ("pass", "passed")


def _confirmation_for_checkpoint(confirmation_identity: dict[str, Any], checkpoint_id: str) -> dict[str, Any] | None:
    confirmation = confirmation_identity.get(checkpoint_id)
    if not isinstance(confirmation, dict):
        return None
    if confirmation.get("checkpoint_id") not in (None, checkpoint_id):
        return None
    if not confirmation.get("confirmation_id"):
        return None
    return confirmation


def _validator_status_by_role(validator_results: list[Any]) -> dict[str, Any]:
    statuses: dict[str, Any] = {}
    for result in validator_results:
        if not isinstance(result, dict):
            continue
        name = result.get("role") or result.get("validator")
        if name:
            statuses[name] = result
    return statuses


def _merge_gate_status(state: dict[str, Any]) -> dict[str, Any]:
    existing_gate_status = state.get("gate_status") or {}
    gate_status: dict[str, Any] = {}
    for gate, definition in GATE_DEFINITIONS.items():
        evaluated = evaluate_gate(state, gate)
        existing = existing_gate_status.get(gate)
        if not isinstance(existing, dict):
            gate_status[gate] = evaluated
            continue

        merged = deepcopy(existing)
        merged.setdefault("status", evaluated["status"])
        merged.setdefault("blocking_reason", deepcopy(evaluated["blocking_reason"]))
        merged["user_step"] = definition["user_step"]
        merged["required_artifacts"] = deepcopy(definition["required_artifacts"])
        merged["required_validators"] = deepcopy(definition["required_validators"])
        merged["allowed_next_actions"] = deepcopy(definition["allowed_next_actions"])
        merged["confirmation"] = _merge_confirmation_metadata(
            existing.get("confirmation"),
            evaluated["confirmation"],
        )
        gate_status[gate] = merged
    return gate_status


def _merge_confirmation_metadata(existing: Any, evaluated: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(existing, dict):
        return deepcopy(evaluated)
    merged = deepcopy(existing)
    merged["required"] = evaluated["required"]
    merged["checkpoint_id"] = evaluated["checkpoint_id"]
    if "payload_hash" not in merged:
        merged["payload_hash"] = evaluated.get("payload_hash")
    return merged

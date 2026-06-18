from __future__ import annotations

from datetime import datetime
from typing import Any


REQUIRED_VALIDATORS = [
    "source_intake",
    "excel_formula",
    "sql_safety",
    "schema_relationship",
    "data_preview",
    "report_content",
    "visual_technical",
]

REQUIRED_PACKET_FIELDS = [
    "validator",
    "status",
    "checked_at",
    "inputs",
    "checks",
    "findings",
    "residual_risks",
]


class ValidatorContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidatorContractError(message)


def _has_quantitative_data_preview_check(checks: list[dict[str, Any]]) -> bool:
    required_metrics = {"row_count", "column_count"}
    for check in checks:
        metrics = check.get("metrics")
        if not isinstance(metrics, dict) or not required_metrics.issubset(metrics):
            continue
        if all(isinstance(metrics[name], (int, float)) and not isinstance(metrics[name], bool) for name in required_metrics):
            return True
    return False


def validate_evidence_packet(packet: dict[str, Any]) -> dict[str, Any]:
    for field in REQUIRED_PACKET_FIELDS:
        _require(field in packet, f"Evidence packet missing required field: {field}")

    _require(packet["validator"] in REQUIRED_VALIDATORS, f"Unknown validator: {packet['validator']}")
    _require(packet["status"] in {"pass", "fail", "warning", "blocked"}, "Invalid validator status")
    try:
        datetime.fromisoformat(str(packet["checked_at"]))
    except ValueError as exc:
        raise ValidatorContractError("checked_at must be ISO formatted") from exc
    _require(isinstance(packet["inputs"], list), "inputs must be a list")
    _require(isinstance(packet["checks"], list) and packet["checks"], "checks must be a non-empty list")
    _require(isinstance(packet["findings"], list), "findings must be a list")
    _require(isinstance(packet["residual_risks"], list), "residual_risks must be a list")

    for check in packet["checks"]:
        _require(isinstance(check, dict), "each check must be an object")
        for field in ("name", "status", "evidence"):
            _require(field in check, f"check missing required field: {field}")
        _require(check["status"] in {"pass", "fail", "warning", "blocked"}, "Invalid check status")

    if packet["validator"] == "data_preview":
        _require(
            _has_quantitative_data_preview_check(packet["checks"]),
            "data_preview validator requires quantitative row_count and column_count checks",
        )
    return packet


def build_final_review_gate(
    packets: list[dict[str, Any]],
    *,
    explicit_user_acceptance: bool = False,
) -> dict[str, Any]:
    validated = [validate_evidence_packet(packet) for packet in packets]
    by_validator = {packet["validator"]: packet for packet in validated}
    missing = [validator for validator in REQUIRED_VALIDATORS if validator not in by_validator]
    _require(not missing, "Missing validator evidence: " + ", ".join(missing))

    non_pass = [packet for packet in validated if packet["status"] != "pass"]
    if non_pass and not explicit_user_acceptance:
        raise ValidatorContractError(
            "Final review requires all validators to pass or explicit user acceptance of residual risks"
        )
    return {
        "status": "accepted_with_risks" if non_pass else "pass",
        "validator_results": validated,
        "non_pass_validators": [packet["validator"] for packet in non_pass],
        "explicit_user_acceptance": explicit_user_acceptance,
    }

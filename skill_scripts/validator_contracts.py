from __future__ import annotations

from dataclasses import dataclass
from typing import Any


REQUIRED_VALIDATORS = [
    "source_requirement_reviewer",
    "excel_formula_reviewer",
    "sql_safety_reviewer",
    "schema_relationship_reviewer",
    "data_preview_reviewer",
    "report_content_reviewer",
    "visual_taste_reviewer",
    "data_visualization_reviewer",
    "react_technical_reviewer",
]

VALIDATOR_STATUSES = {"pass", "fail", "warning", "blocked"}

REQUIRED_PACKET_FIELDS = [
    "role",
    "status",
    "evidence",
    "findings",
    "requiredFixes",
    "residualRisks",
]


class ValidatorContractError(ValueError):
    pass


@dataclass(frozen=True)
class ValidatorResult:
    role: str
    status: str
    evidence: list[dict[str, Any]]
    findings: list[str]
    requiredFixes: list[str]
    residualRisks: list[str]

    def to_dict(self) -> dict[str, Any]:
        return validate_evidence_packet(
            {
                "role": self.role,
                "status": self.status,
                "evidence": self.evidence,
                "findings": self.findings,
                "requiredFixes": self.requiredFixes,
                "residualRisks": self.residualRisks,
            }
        )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidatorContractError(message)


def _require_string_list(value: Any, field: str) -> None:
    _require(isinstance(value, list), f"{field} must be a list")
    _require(all(isinstance(item, str) for item in value), f"{field} must contain strings")


def _has_quantitative_data_preview_check(evidence: list[dict[str, Any]]) -> bool:
    required_metrics = {"row_count", "column_count"}
    for item in evidence:
        metrics = item.get("metrics")
        if not isinstance(metrics, dict) or not required_metrics.issubset(metrics):
            continue
        if all(isinstance(metrics[name], (int, float)) and not isinstance(metrics[name], bool) for name in required_metrics):
            return True
    return False


def validate_evidence_packet(packet: dict[str, Any]) -> dict[str, Any]:
    for field in REQUIRED_PACKET_FIELDS:
        _require(field in packet, f"Evidence packet missing required field: {field}")

    _require(packet["role"] in REQUIRED_VALIDATORS, f"Unknown validator role: {packet['role']}")
    _require(packet["status"] in VALIDATOR_STATUSES, "Invalid validator status")
    _require(isinstance(packet["evidence"], list), "evidence must be a list")
    _require(all(isinstance(item, dict) for item in packet["evidence"]), "evidence must contain objects")
    _require_string_list(packet["findings"], "findings")
    _require_string_list(packet["requiredFixes"], "requiredFixes")
    _require_string_list(packet["residualRisks"], "residualRisks")

    if packet["status"] in {"fail", "blocked"}:
        _require(packet["findings"], "failed or blocked validators require findings")
        _require(packet["requiredFixes"], "failed or blocked validators require requiredFixes")

    if packet["role"] == "data_preview_reviewer":
        _require(
            _has_quantitative_data_preview_check(packet["evidence"]),
            "data_preview_reviewer requires quantitative row_count and column_count checks",
        )
    return packet


def build_final_review_gate(
    packets: list[dict[str, Any]],
    *,
    explicit_user_acceptance: bool = False,
    accepted_residual_risks: list[str] | None = None,
) -> dict[str, Any]:
    validated = [validate_evidence_packet(packet) for packet in packets]
    by_role: dict[str, dict[str, Any]] = {}
    duplicate_roles: list[str] = []
    for packet in validated:
        role = packet["role"]
        if role in by_role:
            duplicate_roles.append(role)
        by_role[role] = packet
    _require(not duplicate_roles, "Duplicate validator evidence: " + ", ".join(duplicate_roles))

    missing_roles = [role for role in REQUIRED_VALIDATORS if role not in by_role]
    non_pass_roles = [
        role
        for role in REQUIRED_VALIDATORS
        if role in by_role and by_role[role]["status"] != "pass"
    ]
    accepted = list(accepted_residual_risks or [])
    blocking = [] if explicit_user_acceptance and not missing_roles else [*non_pass_roles, *missing_roles]

    return {
        "allowed": not blocking,
        "blocking_validators": blocking,
        "accepted_residual_risks": accepted,
    }

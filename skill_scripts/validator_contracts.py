from __future__ import annotations

from dataclasses import dataclass
from typing import Any


REQUIRED_VALIDATORS = [
    "source_requirement_reviewer",
    "excel_classification_reviewer",
    "excel_formula_reviewer",
    "schema_relationship_reviewer",
    "sql_safety_reviewer",
    "sqlite_enrichment_reviewer",
    "data_preview_reviewer",
    "report_content_reviewer",
    "data_visualization_reviewer",
    "visual_taste_reviewer",
    "react_technical_reviewer",
]

VALIDATOR_STATUSES = {"pass", "fail", "warning", "blocked"}

REQUIRED_PACKET_FIELDS = [
    "role",
    "status",
    "reviewer_identity",
    "checked_scope",
    "input_artifact_paths",
    "reviewed_at",
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
                "reviewer_identity": {"kind": "subagent", "id": f"{self.role}-agent"},
                "checked_scope": ["run-dir"],
                "input_artifact_paths": ["checkpoints/current.json"],
                "reviewed_at": "1970-01-01T00:00:00Z",
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


def _validate_typed_evidence(item: dict[str, Any]) -> None:
    evidence_type = item.get("type")
    if evidence_type is None:
        return
    _require(evidence_type in {"file", "metric", "inspection", "command"}, f"Unknown evidence type: {evidence_type}")
    if evidence_type == "file":
        _require(bool(str(item.get("path", "")).strip()), "file evidence requires path")
    elif evidence_type == "metric":
        _require(bool(str(item.get("name", "")).strip()), "metric evidence requires name")
        _require("value" in item, "metric evidence requires value")
    elif evidence_type == "inspection":
        _require(bool(str(item.get("name", "")).strip()), "inspection evidence requires name")
        _require(bool(str(item.get("status", "")).strip()), "inspection evidence requires status")
    elif evidence_type == "command":
        _require(bool(str(item.get("command", "")).strip()), "command evidence requires command")


def _has_metric(evidence: list[dict[str, Any]], name: str) -> bool:
    return _metric_value(evidence, name) is not None


def _metric_value(evidence: list[dict[str, Any]], name: str) -> Any:
    for item in evidence:
        if item.get("type") == "metric" and item.get("name") == name and "value" in item:
            return item["value"]
        metrics = item.get("metrics")
        if isinstance(metrics, dict) and name in metrics:
            return metrics[name]
    return None


def _has_non_negative_numeric_metric(evidence: list[dict[str, Any]], name: str) -> bool:
    value = _metric_value(evidence, name)
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0


def _has_file_evidence(evidence: list[dict[str, Any]], *, required_name_part: str) -> bool:
    for item in evidence:
        if item.get("type") != "file":
            continue
        path = str(item.get("path", ""))
        if path.endswith(".json") and required_name_part in path:
            return True
    return False


def _has_inspection(evidence: list[dict[str, Any]], name: str) -> bool:
    for item in evidence:
        if item.get("type") == "inspection" and item.get("name") == name:
            return bool(str(item.get("status", "")).strip())
    return False


def _has_manifest_file(evidence: list[dict[str, Any]]) -> bool:
    return _has_file_evidence(evidence, required_name_part="wferp_run_sqlite_manifest")


def validate_evidence_packet(packet: dict[str, Any]) -> dict[str, Any]:
    for field in REQUIRED_PACKET_FIELDS:
        _require(field in packet, f"Evidence packet missing required field: {field}")

    _require(packet["role"] in REQUIRED_VALIDATORS, f"Unknown validator role: {packet['role']}")
    _require(packet["status"] in VALIDATOR_STATUSES, "Invalid validator status")
    reviewer_identity = packet["reviewer_identity"]
    _require(isinstance(reviewer_identity, dict), "reviewer_identity must be an object")
    _require(bool(str(reviewer_identity.get("kind", "")).strip()), "reviewer_identity.kind is required")
    _require(bool(str(reviewer_identity.get("id", "")).strip()), "reviewer_identity.id is required")
    _require_string_list(packet["checked_scope"], "checked_scope")
    _require(packet["checked_scope"], "checked_scope is required")
    _require_string_list(packet["input_artifact_paths"], "input_artifact_paths")
    _require(packet["input_artifact_paths"], "input_artifact_paths is required")
    _require(isinstance(packet["reviewed_at"], str) and bool(packet["reviewed_at"].strip()), "reviewed_at is required")
    _require(isinstance(packet["evidence"], list), "evidence must be a list")
    _require(all(isinstance(item, dict) for item in packet["evidence"]), "evidence must contain objects")
    for item in packet["evidence"]:
        _validate_typed_evidence(item)
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
    if packet["role"] == "excel_classification_reviewer":
        _require(
            _has_file_evidence(packet["evidence"], required_name_part="classification"),
            "excel_classification_reviewer requires classification json file evidence",
        )
        for metric in (
            "classified_columns",
            "db_field_count",
            "formula_field_count",
            "lookup_field_count",
            "manual_only_count",
        ):
            _require(
                _has_non_negative_numeric_metric(packet["evidence"], metric),
                f"excel_classification_reviewer requires non-negative numeric {metric} metric",
            )
        _require(
            _has_inspection(packet["evidence"], "metadata_readability"),
            "excel_classification_reviewer requires metadata_readability inspection evidence",
        )
    if packet["role"] == "sqlite_enrichment_reviewer":
        _require(
            _has_manifest_file(packet["evidence"]),
            "sqlite_enrichment_reviewer requires sqlite manifest file evidence",
        )
        for metric in ("raw_row_count", "enriched_row_count", "ignored_lookup_rows"):
            _require(
                _has_non_negative_numeric_metric(packet["evidence"], metric),
                f"sqlite_enrichment_reviewer requires non-negative numeric {metric} metric",
            )
    return {"valid": True, **packet}


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
    if accepted_residual_risks is None:
        accepted = []
    else:
        _require(isinstance(accepted_residual_risks, list), "accepted_residual_risks must be a list")
        _require(
            all(isinstance(item, str) for item in accepted_residual_risks),
            "accepted_residual_risks must contain strings",
        )
        accepted = list(accepted_residual_risks)

    accepted_set = set(accepted)
    blocking = list(missing_roles)
    for role in non_pass_roles:
        residual_risks = by_role[role]["residualRisks"]
        role_accepted = explicit_user_acceptance and any(
            f"{role}: {risk}" in accepted_set for risk in residual_risks
        )
        if not role_accepted:
            blocking.append(role)

    return {
        "allowed": not blocking,
        "blocking_validators": blocking,
        "accepted_residual_risks": accepted,
    }

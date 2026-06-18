from __future__ import annotations

import pytest

from skill_scripts import validator_contracts
from skill_scripts.validator_contracts import (
    REQUIRED_VALIDATORS,
    ValidatorContractError,
    build_final_review_gate,
    validate_evidence_packet,
)


def test_validator_contracts_include_required_roles():
    assert REQUIRED_VALIDATORS == [
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


def test_validator_result_requires_evidence_and_repair_fields():
    result = validator_contracts.ValidatorResult(
        role="sql_safety_reviewer",
        status="fail",
        evidence=[{"command": "python3 -m skill_scripts.cli_report_harness validate-sql"}],
        findings=["SELECT INTO is blocked"],
        requiredFixes=["Remove SELECT INTO"],
        residualRisks=[],
    )

    assert result.to_dict() == {
        "role": "sql_safety_reviewer",
        "status": "fail",
        "evidence": [{"command": "python3 -m skill_scripts.cli_report_harness validate-sql"}],
        "findings": ["SELECT INTO is blocked"],
        "requiredFixes": ["Remove SELECT INTO"],
        "residualRisks": [],
    }


def test_validator_contract_requires_status_evidence_findings_and_repair_fields():
    packet = {
        "role": "sql_safety_reviewer",
        "status": "pass",
        "evidence": [{"command": "python3 -m skill_scripts.cli_report_harness validate-sql"}],
        "findings": [],
        "requiredFixes": [],
        "residualRisks": [],
    }

    assert validate_evidence_packet(packet) == packet

    for field in ("role", "status", "evidence", "findings", "requiredFixes", "residualRisks"):
        incomplete = dict(packet)
        incomplete.pop(field)
        with pytest.raises(ValidatorContractError, match=field):
            validate_evidence_packet(incomplete)


def test_validator_contract_rejects_missing_quantitative_checks_for_data_validator():
    packet = {
        "role": "data_preview_reviewer",
        "status": "pass",
        "evidence": [{"name": "preview_shape", "status": "pass", "metrics": {"row_count": 10}}],
        "findings": [],
        "requiredFixes": [],
        "residualRisks": [],
    }

    with pytest.raises(ValidatorContractError, match="quantitative"):
        validate_evidence_packet(packet)


def test_data_preview_quantitative_checks_require_numeric_metrics():
    packet = {
        "role": "data_preview_reviewer",
        "status": "pass",
        "evidence": [
            {
                "name": "preview_shape",
                "status": "pass",
                "detail": "row_count=10; column_count=4",
            }
        ],
        "findings": [],
        "requiredFixes": [],
        "residualRisks": [],
    }

    with pytest.raises(ValidatorContractError, match="quantitative"):
        validate_evidence_packet(packet)

    packet["evidence"][0]["metrics"] = {"row_count": 10, "column_count": 4}
    assert validate_evidence_packet(packet) == packet


def test_report_final_review_requires_all_validators_pass_or_explicit_user_acceptance():
    packets = [
        {
            "role": validator,
            "status": "pass",
            "evidence": [
                {
                    "name": "row_count",
                    "status": "pass",
                    "detail": "row_count=10; column_count=4",
                    "metrics": {"row_count": 10, "column_count": 4},
                }
            ],
            "findings": [],
            "requiredFixes": [],
            "residualRisks": [],
        }
        for validator in REQUIRED_VALIDATORS
    ]

    assert build_final_review_gate(packets)["allowed"] is True

    packets[0] = dict(packets[0], status="fail", findings=["來源不完整"], requiredFixes=["補齊來源檔案"])
    gate = build_final_review_gate(packets)
    assert gate["allowed"] is False
    assert gate["blocking_validators"] == ["source_requirement_reviewer"]

    gate = build_final_review_gate(packets, explicit_user_acceptance=True)
    assert gate["allowed"] is True


def test_report_final_review_blocks_missing_validator_roles():
    packet = {
        "role": "source_requirement_reviewer",
        "status": "pass",
        "evidence": [{"command": "review source inputs"}],
        "findings": [],
        "requiredFixes": [],
        "residualRisks": [],
    }

    gate = build_final_review_gate([packet])

    assert gate["allowed"] is False
    assert "excel_formula_reviewer" in gate["blocking_validators"]

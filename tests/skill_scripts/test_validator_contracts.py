from __future__ import annotations

from datetime import datetime, timezone

import pytest

from skill_scripts.validator_contracts import (
    REQUIRED_VALIDATORS,
    ValidatorContractError,
    build_final_review_gate,
    validate_evidence_packet,
)


def test_validator_contracts_include_required_roles():
    assert REQUIRED_VALIDATORS == [
        "source_intake",
        "excel_formula",
        "sql_safety",
        "schema_relationship",
        "data_preview",
        "report_content",
        "visual_technical",
    ]


def test_validator_contract_requires_status_evidence_and_findings():
    packet = {
        "validator": "sql_safety",
        "status": "pass",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "inputs": ["sql/query.sql"],
        "checks": [{"name": "readonly_select_only", "status": "pass", "evidence": "blocked keywords: 0"}],
        "findings": [],
        "residual_risks": [],
    }

    assert validate_evidence_packet(packet) == packet

    incomplete = dict(packet)
    incomplete.pop("findings")
    with pytest.raises(ValidatorContractError, match="findings"):
        validate_evidence_packet(incomplete)


def test_validator_contract_rejects_missing_quantitative_checks_for_data_validator():
    packet = {
        "validator": "data_preview",
        "status": "pass",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "inputs": ["data/preview.json"],
        "checks": [{"name": "preview_shape", "status": "pass", "evidence": "looks ok"}],
        "findings": [],
        "residual_risks": [],
    }

    with pytest.raises(ValidatorContractError, match="quantitative"):
        validate_evidence_packet(packet)


def test_data_preview_quantitative_checks_require_numeric_metrics():
    packet = {
        "validator": "data_preview",
        "status": "pass",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "inputs": ["data/preview.json"],
        "checks": [
            {
                "name": "preview_shape",
                "status": "pass",
                "evidence": "row_count=10; column_count=4",
            }
        ],
        "findings": [],
        "residual_risks": [],
    }

    with pytest.raises(ValidatorContractError, match="quantitative"):
        validate_evidence_packet(packet)

    packet["checks"][0]["metrics"] = {"row_count": 10, "column_count": 4}
    assert validate_evidence_packet(packet) == packet


def test_report_final_review_requires_all_validators_pass_or_explicit_user_acceptance():
    packets = [
        {
            "validator": validator,
            "status": "pass",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "inputs": ["input.json"],
            "checks": [
                {
                    "name": "row_count",
                    "status": "pass",
                    "evidence": "row_count=10; column_count=4",
                    "metrics": {"row_count": 10, "column_count": 4},
                }
            ],
            "findings": [],
            "residual_risks": [],
        }
        for validator in REQUIRED_VALIDATORS
    ]

    assert build_final_review_gate(packets)["status"] == "pass"

    packets[0] = dict(packets[0], status="fail", findings=["來源不完整"])
    with pytest.raises(ValidatorContractError, match="explicit user acceptance"):
        build_final_review_gate(packets)

    gate = build_final_review_gate(packets, explicit_user_acceptance=True)
    assert gate["status"] == "accepted_with_risks"

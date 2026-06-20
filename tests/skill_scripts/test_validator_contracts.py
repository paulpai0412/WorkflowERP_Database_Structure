from __future__ import annotations

import pytest

from skill_scripts import validator_contracts
from skill_scripts.validator_contracts import (
    REQUIRED_VALIDATORS,
    ValidatorContractError,
    build_final_review_gate,
    validate_evidence_packet,
)


def _with_fresh_reviewer(packet: dict[str, object]) -> dict[str, object]:
    role = str(packet.get("role", "validator"))
    return {
        "reviewer_identity": {"kind": "subagent", "id": f"{role}-agent"},
        "checked_scope": ["run-dir"],
        "input_artifact_paths": ["checkpoints/current.json"],
        "reviewed_at": "2026-06-20T00:00:00Z",
        **packet,
    }


def test_validator_contracts_include_required_roles():
    assert REQUIRED_VALIDATORS == [
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


def test_required_validators_include_classification_and_sqlite_enrichment():
    assert "excel_classification_reviewer" in REQUIRED_VALIDATORS
    assert "sqlite_enrichment_reviewer" in REQUIRED_VALIDATORS


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
        "valid": True,
        "role": "sql_safety_reviewer",
        "status": "fail",
        "reviewer_identity": {"kind": "subagent", "id": "sql_safety_reviewer-agent"},
        "checked_scope": ["run-dir"],
        "input_artifact_paths": ["checkpoints/current.json"],
        "reviewed_at": "1970-01-01T00:00:00Z",
        "evidence": [{"command": "python3 -m skill_scripts.cli_report_harness validate-sql"}],
        "findings": ["SELECT INTO is blocked"],
        "requiredFixes": ["Remove SELECT INTO"],
        "residualRisks": [],
    }


def test_validator_contract_requires_fresh_reviewer_metadata():
    packet = {
        "role": "sql_safety_reviewer",
        "status": "pass",
        "evidence": [{"type": "file", "path": "sql/query.sql"}],
        "findings": [],
        "requiredFixes": [],
        "residualRisks": [],
    }

    with pytest.raises(ValidatorContractError, match="reviewer_identity"):
        validate_evidence_packet(packet)


def test_validator_contract_requires_status_evidence_findings_and_repair_fields():
    packet = {
        "role": "sql_safety_reviewer",
        "status": "pass",
        "evidence": [{"command": "python3 -m skill_scripts.cli_report_harness validate-sql"}],
        "findings": [],
        "requiredFixes": [],
        "residualRisks": [],
    }

    packet = _with_fresh_reviewer(packet)
    assert validate_evidence_packet(packet) == {"valid": True, **packet}

    for field in (
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
    ):
        incomplete = dict(packet)
        incomplete.pop(field)
        with pytest.raises(ValidatorContractError, match=field):
            validate_evidence_packet(incomplete)


def test_validator_contract_accepts_structured_evidence_types():
    packet = {
        "role": "excel_classification_reviewer",
        "status": "pass",
        "evidence": [
            {"type": "file", "path": "data/column-classification.json", "detail": "classification payload"},
            {"type": "metric", "name": "classified_columns", "value": 12},
            {"type": "metric", "name": "db_field_count", "value": 7},
            {"type": "metric", "name": "formula_field_count", "value": 3},
            {"type": "metric", "name": "lookup_field_count", "value": 1},
            {"type": "metric", "name": "manual_only_count", "value": 1},
            {"type": "inspection", "name": "metadata_readability", "status": "pass"},
            {"type": "command", "command": "pytest tests/skill_scripts/test_workbook_classifier.py -v"},
        ],
        "findings": [],
        "requiredFixes": [],
        "residualRisks": [],
    }

    packet = _with_fresh_reviewer(packet)
    assert validate_evidence_packet(packet) == {"valid": True, **packet}


def test_excel_classification_reviewer_requires_file_metrics_and_metadata_inspection():
    packet = {
        "role": "excel_classification_reviewer",
        "status": "pass",
        "evidence": [
            {"type": "file", "path": "data/field-classification.json"},
            {"type": "metric", "name": "classified_columns", "value": 12},
            {"type": "metric", "name": "db_field_count", "value": 7},
            {"type": "metric", "name": "formula_field_count", "value": 3},
            {"type": "metric", "name": "lookup_field_count", "value": 1},
            {"type": "metric", "name": "manual_only_count", "value": 1},
            {"type": "inspection", "name": "metadata_readability", "status": "pass"},
        ],
        "findings": [],
        "requiredFixes": [],
        "residualRisks": [],
    }

    packet = _with_fresh_reviewer(packet)
    assert validate_evidence_packet(packet)["valid"] is True

    for evidence_index, expected_message in [
        (0, "classification json file"),
        (1, "classified_columns"),
        (2, "db_field_count"),
        (3, "formula_field_count"),
        (4, "lookup_field_count"),
        (5, "manual_only_count"),
        (6, "metadata_readability"),
    ]:
        missing = dict(packet)
        missing["evidence"] = list(packet["evidence"])
        missing["evidence"].pop(evidence_index)
        with pytest.raises(ValidatorContractError, match=expected_message):
            validate_evidence_packet(missing)


def test_sqlite_enrichment_reviewer_requires_manifest_and_row_counts():
    packet = {
        "role": "sqlite_enrichment_reviewer",
        "status": "pass",
        "evidence": [
            {
                "type": "file",
                "path": "sqlite/wferp_run_sqlite_manifest.json",
                "detail": "manifest with raw/enriched row counts",
            },
            {"type": "metric", "name": "raw_row_count", "value": 2},
            {"type": "metric", "name": "enriched_row_count", "value": 2},
            {"type": "metric", "name": "ignored_lookup_rows", "value": 0},
        ],
        "findings": [],
        "requiredFixes": [],
        "residualRisks": [],
    }

    packet = _with_fresh_reviewer(packet)
    result = validate_evidence_packet(packet)

    assert result["valid"] is True


def test_sqlite_enrichment_metrics_must_be_non_negative_numbers():
    packet = {
        "role": "sqlite_enrichment_reviewer",
        "status": "pass",
        "evidence": [
            {"type": "file", "path": "sqlite/wferp_run_sqlite_manifest.json"},
            {"type": "metric", "name": "raw_row_count", "value": 2},
            {"type": "metric", "name": "enriched_row_count", "value": 2},
            {"type": "metric", "name": "ignored_lookup_rows", "value": 0},
        ],
        "findings": [],
        "requiredFixes": [],
        "residualRisks": [],
    }
    packet = _with_fresh_reviewer(packet)

    for bad_value in ("2", None, False, -1):
        invalid = dict(packet)
        invalid["evidence"] = list(packet["evidence"])
        invalid["evidence"][1] = {"type": "metric", "name": "raw_row_count", "value": bad_value}
        with pytest.raises(ValidatorContractError, match="raw_row_count"):
            validate_evidence_packet(invalid)


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
        validate_evidence_packet(_with_fresh_reviewer(packet))


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
        validate_evidence_packet(_with_fresh_reviewer(packet))

    packet["evidence"][0]["metrics"] = {"row_count": 10, "column_count": 4}
    packet = _with_fresh_reviewer(packet)
    assert validate_evidence_packet(packet) == {"valid": True, **packet}


def test_report_final_review_requires_all_validators_pass_or_explicit_user_acceptance():
    packets = []
    for validator in REQUIRED_VALIDATORS:
        evidence = [
            {
                "name": "row_count",
                "status": "pass",
                "detail": "row_count=10; column_count=4",
                "metrics": {"row_count": 10, "column_count": 4},
            }
        ]
        if validator == "sqlite_enrichment_reviewer":
            evidence = [
                {"type": "file", "path": "sqlite/wferp_run_sqlite_manifest.json"},
                {"type": "metric", "name": "raw_row_count", "value": 10},
                {"type": "metric", "name": "enriched_row_count", "value": 10},
                {"type": "metric", "name": "ignored_lookup_rows", "value": 0},
            ]
        if validator == "excel_classification_reviewer":
            evidence = [
                {"type": "file", "path": "data/field-classification.json"},
                {"type": "metric", "name": "classified_columns", "value": 10},
                {"type": "metric", "name": "db_field_count", "value": 6},
                {"type": "metric", "name": "formula_field_count", "value": 2},
                {"type": "metric", "name": "lookup_field_count", "value": 1},
                {"type": "metric", "name": "manual_only_count", "value": 1},
                {"type": "inspection", "name": "metadata_readability", "status": "pass"},
            ]
        packets.append(
            _with_fresh_reviewer(
                {
                    "role": validator,
                    "status": "pass",
                    "evidence": evidence,
                    "findings": [],
                    "requiredFixes": [],
                    "residualRisks": [],
                }
            )
        )

    assert build_final_review_gate(packets)["allowed"] is True

    packets[0] = dict(
        packets[0],
        status="fail",
        findings=["來源不完整"],
        requiredFixes=["補齊來源檔案"],
        residualRisks=["使用者確認來源缺口後仍接受"],
    )
    gate = build_final_review_gate(packets)
    assert gate["allowed"] is False
    assert gate["blocking_validators"] == ["source_requirement_reviewer"]

    gate = build_final_review_gate(
        packets,
        explicit_user_acceptance=True,
        accepted_residual_risks=["source_requirement_reviewer: 使用者確認來源缺口後仍接受"],
    )
    assert gate["allowed"] is True


def test_report_final_review_blocks_missing_validator_roles():
    packet = _with_fresh_reviewer(
        {
            "role": "source_requirement_reviewer",
            "status": "pass",
            "evidence": [{"command": "review source inputs"}],
            "findings": [],
            "requiredFixes": [],
            "residualRisks": [],
        }
    )

    gate = build_final_review_gate([packet])

    assert gate["allowed"] is False
    assert "excel_formula_reviewer" in gate["blocking_validators"]

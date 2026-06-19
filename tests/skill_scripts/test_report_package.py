from __future__ import annotations

from pathlib import Path

from skill_scripts.dynamic_design_brief import build_design_brief, validate_design_brief
from skill_scripts.report_harness import ReportHarness
from skill_scripts.report_package import build_report_package, validate_report_package
from skill_scripts.validator_contracts import REQUIRED_VALIDATORS
from skill_scripts.visual_checkpoint import build_visual_checkpoint_payload


def _validator_result(role: str, status: str = "pass") -> dict[str, object]:
    evidence: list[dict[str, object]] = [{"command": f"review {role}"}]
    if role == "data_preview_reviewer":
        evidence = [
            {
                "name": "preview_shape",
                "status": "pass",
                "metrics": {"row_count": 2, "column_count": 2},
            }
        ]
    if role == "excel_classification_reviewer":
        evidence = [
            {"type": "file", "path": "data/field-classification.json"},
            {"type": "metric", "name": "classified_columns", "value": 2},
            {"type": "metric", "name": "db_field_count", "value": 1},
            {"type": "metric", "name": "formula_field_count", "value": 1},
            {"type": "metric", "name": "lookup_field_count", "value": 0},
            {"type": "metric", "name": "manual_only_count", "value": 0},
            {"type": "inspection", "name": "metadata_readability", "status": "pass"},
        ]
    if role == "sqlite_enrichment_reviewer":
        evidence = [
            {"type": "file", "path": "sqlite/wferp_run_sqlite_manifest.json"},
            {"type": "metric", "name": "raw_row_count", "value": 2},
            {"type": "metric", "name": "enriched_row_count", "value": 2},
            {"type": "metric", "name": "ignored_lookup_rows", "value": 0},
        ]
    return {
        "role": role,
        "status": status,
        "evidence": evidence,
        "findings": [] if status == "pass" else [f"{role} failed"],
        "requiredFixes": [] if status == "pass" else [f"repair {role}"],
        "residualRisks": [] if status == "pass" else [f"accepted risk for {role}"],
    }


def _all_validator_results() -> list[dict[str, object]]:
    return [_validator_result(role) for role in REQUIRED_VALIDATORS]


def _confirm_design_brief(harness: ReportHarness) -> None:
    brief = build_design_brief(
        {
            "catalog_guardrail": "financial-control",
            "prompt": harness.state().get("prompt"),
            "report_type": harness.state().get("report_type"),
            "data_profile": {"columns": ["department", "amount"], "row_count": 2},
            "datasets": {"columns": ["department", "amount"]},
        }
    )
    assert validate_design_brief(brief)["valid"] is True
    harness.write_design_brief(brief)
    harness.confirm("design_brief", "確認設計")


def _confirm_visual_design(harness: ReportHarness) -> None:
    package = {
        "catalog_guardrail": "financial-control",
        "prompt": harness.state().get("prompt"),
        "report_type": harness.state().get("report_type"),
        "data_profile": {"columns": ["department", "amount"], "row_count": 2},
        "datasets": {
            "columns": ["department", "amount"],
            "embedded_rows": [
                {"department": "管理部", "amount": 1000},
                {"department": "研發部", "amount": 2500},
            ],
        },
        "aggregates": {"amount_sum": 3500, "amount_avg": 1750},
    }
    payload = build_visual_checkpoint_payload(harness.state()["report_design_brief"], package)
    harness.write_visual_design(payload)
    harness.confirm("visual_design", "確認視覺設計")


def _accepted_report_run(tmp_path: Path) -> ReportHarness:
    harness = ReportHarness.create(
        tmp_path,
        run_id="run-001",
        prompt="查詢 2026 年費用明細",
    )
    harness.write_sql_review(
        "SELECT department, amount FROM expenses",
        {"readonly": True, "status": "pass"},
    )
    harness.confirm("sql_review", "同意查詢")
    harness.write_data_preview(
        {
            "rows": [
                {"department": "管理部", "amount": 1000},
                {"department": "研發部", "amount": 2500},
            ],
            "columns": ["department", "amount"],
            "row_count": 2,
            "aggregates": {"amount_sum": 3500},
            "excluded_rows": [],
        }
    )
    harness.confirm("data_preview", "確認資料")
    harness.write_report_selection(
        {
            "selected_report_type": "管理摘要",
            "selected_report_design": "financial-control",
            "selected_options": {"include_table": True, "include_chart": False},
        }
    )
    harness.confirm("report_selection", "產生報告")
    _confirm_design_brief(harness)
    _confirm_visual_design(harness)
    harness.write_report_draft({"sections": ["executive-summary", "data-table"]})
    harness.confirm("report_draft", "接受")
    harness.write_final_review({"validator_results": _all_validator_results()})
    harness.confirm("final_review", "完成")
    return harness


def test_build_report_package_uses_confirmed_run_state(tmp_path: Path):
    harness = _accepted_report_run(tmp_path)

    package = build_report_package(harness.run_dir)

    assert package["schema_version"] == "wferp.report-package.v1"
    assert package["run_id"] == "run-001"
    assert package["package_id"] == "run-001"
    assert package["catalog_guardrail"] == "financial-control"
    assert package["report_type"] == "管理摘要"
    assert package["report_options"] == {"include_table": True, "include_chart": False}
    assert package["sql"]["text"] == "SELECT department, amount FROM expenses"
    assert package["data_profile"]["row_count"] == 2
    assert package["data_profile"]["columns"] == ["department", "amount"]
    assert package["data_profile"]["embedded_mode"] == "full_rows"
    assert package["data_profile"]["embedded_rows"] == 2
    assert package["data_profile"]["full_rows_in_evidence_packet"] is False
    assert package["datasets"]["embedded_rows"] == [
        {"department": "管理部", "amount": 1000},
        {"department": "研發部", "amount": 2500},
    ]
    assert package["aggregates"] == {"amount_sum": 3500}
    assert package["evidence_index"] == [
        {"id": "sql", "path": "evidence/query.sql"},
        {"id": "execution_result", "path": "evidence/execution-result.json"},
        {"id": "validators", "path": "evidence/validator-results.json"},
    ]
    assert package["hashes"]["sql_sha256"]
    assert package["hashes"]["package_sha256"]
    assert validate_report_package(package)["valid"] is True


def test_report_package_hash_is_deterministic(tmp_path: Path):
    harness = _accepted_report_run(tmp_path)

    first = build_report_package(harness.run_dir)
    second = build_report_package(harness.run_dir)

    assert first["hashes"]["package_sha256"] == second["hashes"]["package_sha256"]
    assert first["package_id"] == second["package_id"]


def test_large_row_count_uses_summary_plus_preview_policy(tmp_path: Path):
    harness = _accepted_report_run(tmp_path)
    preview_rows = [
        {"department": "管理部", "amount": 1000},
        {"department": "研發部", "amount": 2500},
        {"department": "業務部", "amount": 3000},
    ]
    harness.write_data_preview(
        {
            "rows": preview_rows,
            "columns": ["department", "amount"],
            "row_count": 6000,
            "aggregates": {"amount_sum": 6500},
            "excluded_rows": [],
        }
    )

    package = build_report_package(harness.run_dir)

    assert package["data_profile"]["embedded_mode"] == "summary_plus_preview"
    assert package["data_profile"]["embedded_rows"] == len(preview_rows)
    assert package["data_profile"]["full_rows_in_evidence_packet"] is True


def test_rewriting_data_preview_invalidates_downstream_delivery_state(tmp_path: Path):
    harness = _accepted_report_run(tmp_path)

    harness.write_data_preview(
        {
            "rows": [{"department": "客服部", "amount": 9000}],
            "columns": ["department", "amount"],
            "row_count": 1,
            "aggregates": {"amount_sum": 9000},
            "excluded_rows": [],
        }
    )

    package = build_report_package(harness.run_dir)
    result = validate_report_package(package)
    state = harness.state()

    assert result["valid"] is False
    assert "delivery_gate" in result["errors"]
    assert state["user_confirmations"]["sql_review"] == "同意查詢"
    assert "report_selection" not in state["user_confirmations"]
    assert "report_draft" not in state["user_confirmations"]
    assert "final_review" not in state["user_confirmations"]
    assert "report_selection" not in {item["checkpoint"] for item in state["checkpoints"]}
    assert "report_draft" not in {item["checkpoint"] for item in state["checkpoints"]}
    assert "final_review" not in {item["checkpoint"] for item in state["checkpoints"]}
    assert state["report_type"] is None
    assert state["report_design"] is None
    assert state["report_options"] == {}
    assert state["validator_results"] == []


def test_credentials_and_unconfirmed_delivery_are_rejected(tmp_path: Path):
    harness = _accepted_report_run(tmp_path)
    harness.update_state(db_connection_string="server=prod;password=secret")
    harness.confirm("final_review", "回到初稿")

    package = build_report_package(harness.run_dir)
    result = validate_report_package(package)

    assert result["valid"] is False
    assert "credentials" in result["errors"]
    assert "delivery_gate" in result["errors"]

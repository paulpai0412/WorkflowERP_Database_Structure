from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from skill_scripts.checkpoint_companion import CheckpointCompanionServer
from skill_scripts.dynamic_design_brief import build_design_brief, validate_design_brief
from skill_scripts.report_harness import ReportHarness
from skill_scripts.report_harness_state import CHECKPOINT_DEFINITIONS
from skill_scripts.validator_contracts import REQUIRED_VALIDATORS
from skill_scripts.visual_checkpoint import build_visual_checkpoint_payload


def _validator_result(role: str, status: str = "pass") -> dict[str, object]:
    evidence: list[dict[str, object]] = [{"command": f"review {role}"}]
    if role == "data_preview_reviewer":
        evidence = [
            {
                "name": "preview_shape",
                "status": "pass",
                "metrics": {"row_count": 10, "column_count": 4},
            }
        ]
    if role == "excel_classification_reviewer":
        evidence = [
            {"type": "file", "path": "data/field-classification.json"},
            {"type": "metric", "name": "classified_columns", "value": 10},
            {"type": "metric", "name": "db_field_count", "value": 6},
            {"type": "metric", "name": "formula_field_count", "value": 2},
            {"type": "metric", "name": "lookup_field_count", "value": 1},
            {"type": "metric", "name": "manual_only_count", "value": 1},
            {"type": "inspection", "name": "metadata_readability", "status": "pass"},
        ]
    if role == "sqlite_enrichment_reviewer":
        evidence = [
            {"type": "file", "path": "sqlite/wferp_run_sqlite_manifest.json"},
            {"type": "metric", "name": "raw_row_count", "value": 10},
            {"type": "metric", "name": "enriched_row_count", "value": 10},
            {"type": "metric", "name": "ignored_lookup_rows", "value": 0},
        ]
    return {
        "role": role,
        "status": status,
        "reviewer_identity": {"kind": "subagent", "id": f"{role}-agent"},
        "checked_scope": ["run-dir"],
        "input_artifact_paths": ["checkpoints/current.json"],
        "reviewed_at": "2026-06-20T00:00:00Z",
        "evidence": evidence,
        "findings": [] if status == "pass" else [f"{role} failed"],
        "requiredFixes": [] if status == "pass" else [f"repair {role}"],
        "residualRisks": [] if status == "pass" else [f"accepted risk for {role}"],
    }


def _all_validator_results(status_overrides: dict[str, str] | None = None) -> list[dict[str, object]]:
    overrides = status_overrides or {}
    return [_validator_result(role, overrides.get(role, "pass")) for role in REQUIRED_VALIDATORS]


def _confirm_design_brief(harness: ReportHarness) -> None:
    brief = build_design_brief(
        {
            "catalog_guardrail": "financial-control",
            "prompt": harness.state().get("prompt"),
            "report_type": harness.state().get("report_type"),
            "data_profile": {"columns": ["department", "amount"], "row_count": 1},
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


def post_json(url: str, payload: dict) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def request_bytes(url: str, data: bytes, content_type: str = "application/json") -> tuple[int, dict]:
    request = Request(
        url,
        data=data,
        headers={"Content-Type": content_type},
        method="POST",
    )
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


def test_confirmation_post_writes_confirmation_and_audit(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="查詢費用")
    harness.write_sql_review("SELECT department, amount FROM expenses", {"status": "pass"})

    with CheckpointCompanionServer.serve(tmp_path / "run-001") as server:
        result = post_json(
            f"{server.base_url}/api/runs/run-001/checkpoints/sql_review/confirm",
            {
                "action": "同意查詢",
                "checkpointId": "sql_review",
                "comment": "條件正確，可以查詢",
                "selectedOptions": {"view": "management"},
            },
        )

    assert result["status"] == "confirmed"
    confirmation = json.loads(
        (tmp_path / "run-001" / "checkpoints" / "02_sql_review.confirmation.json").read_text(
            encoding="utf-8"
        )
    )
    assert confirmation["action"] == "同意查詢"
    assert confirmation["comment"] == "條件正確，可以查詢"
    assert confirmation["selectedOptions"] == {"view": "management"}
    audit_lines = (tmp_path / "run-001" / "audit" / "events.jsonl").read_text(
        encoding="utf-8"
    ).splitlines()
    assert len(audit_lines) == 1
    assert json.loads(audit_lines[0])["event"] == "checkpoint_confirmed"


def test_companion_prompt_repair_posts_changes_requested_with_scope(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="query expenses")
    harness.write_sql_review("SELECT department, amount FROM expenses", {"status": "pass"})
    repair_action = CHECKPOINT_DEFINITIONS["sql_review"]["actions"][1]

    with CheckpointCompanionServer.serve(tmp_path / "run-001") as server:
        result = post_json(
            f"{server.base_url}/api/runs/run-001/checkpoints/sql_review/confirm",
            {
                "action": repair_action,
                "checkpointId": "sql_review",
                "comment": "add date condition",
                "selectedOptions": {
                    "changeScope": "sql_conditions",
                    "targetUserStep": 2,
                    "requiresRerender": True,
                },
            },
        )

    assert result["status"] == "confirmed"
    state = harness.state()
    assert state["blocking_repair_request"]["comment"] == "add date condition"
    assert state["blocking_repair_request"]["changeScope"] == "sql_conditions"
    assert state["allowed_next_actions"] == ["repair_current_step"]


def test_companion_server_uses_daemon_request_threads(tmp_path: Path):
    ReportHarness.create(tmp_path, run_id="run-001", prompt="查詢費用")

    with CheckpointCompanionServer.serve(tmp_path / "run-001") as server:
        assert server.httpd.daemon_threads is True


def test_confirmation_post_rejects_malformed_json_and_invalid_utf8(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="查詢費用")
    harness.write_sql_review("SELECT department, amount FROM expenses", {"status": "pass"})

    with CheckpointCompanionServer.serve(tmp_path / "run-001") as server:
        malformed_status, malformed_body = request_bytes(
            f"{server.base_url}/api/runs/run-001/checkpoints/sql_review/confirm",
            b'{"action":',
        )
        utf8_status, utf8_body = request_bytes(
            f"{server.base_url}/api/runs/run-001/checkpoints/sql_review/confirm",
            b"\xff\xfe\xfd",
        )

    assert malformed_status == 400
    assert malformed_body == {"status": "bad_request"}
    assert utf8_status == 400
    assert utf8_body == {"status": "bad_request"}


def test_confirmation_post_rejects_body_that_is_too_large(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="查詢費用")
    harness.write_sql_review("SELECT department, amount FROM expenses", {"status": "pass"})

    with CheckpointCompanionServer.serve(tmp_path / "run-001") as server:
        status, body = request_bytes(
            f"{server.base_url}/api/runs/run-001/checkpoints/sql_review/confirm",
            b'{"action":"' + ("同意查詢".encode("utf-8") * 20000) + b'"}',
        )

    assert status == 413
    assert body == {"status": "request_too_large"}


def test_current_checkpoint_page_returns_html_with_confirm_url(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="查詢費用")
    harness.write_sql_review("SELECT department, amount FROM expenses", {"status": "pass"})

    with CheckpointCompanionServer.serve(tmp_path / "run-001") as server:
        with urlopen(f"{server.base_url}/runs/run-001/checkpoints/current", timeout=5) as response:
            html = response.read().decode("utf-8")
            content_type = response.headers["Content-Type"]

    assert response.status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "SQL 查詢確認" in html
    assert "/api/runs/run-001/checkpoints/sql_review/confirm" in html
    assert "SELECT department, amount FROM expenses" in html
    assert "status" in html
    assert "fetch(confirmUrl" in html
    assert "data-action=\"同意查詢\"" in html


def test_current_checkpoint_page_renders_data_preview_payload(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="查詢費用")
    harness.write_sql_review("SELECT department, amount FROM expenses", {"status": "pass"})
    harness.confirm("sql_review", "同意查詢")
    harness.write_data_preview(
        {
            "columns": ["expense_account_name", "actual_amount", "budget_amount"],
            "row_count": 2,
            "rows": [
                {"expense_account_name": "旅費", "actual_amount": 50000, "budget_amount": 40000},
                {"expense_account_name": "文具", "actual_amount": 12000, "budget_amount": 15000},
            ],
            "aggregates": {"actual_amount_sum": 62000, "budget_amount_sum": 55000},
            "acceptance_checks": {"min_rows_1": True, "asset_account_excluded": True},
        }
    )

    with CheckpointCompanionServer.serve(tmp_path / "run-001") as server:
        with urlopen(f"{server.base_url}/runs/run-001/checkpoints/current", timeout=5) as response:
            html = response.read().decode("utf-8")

    assert "資料預覽確認" in html
    assert "旅費" in html
    assert "actual_amount_sum" in html
    assert "asset_account_excluded" in html
    assert "<table" in html


def test_data_preview_page_renders_sample_rows_as_table(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="查詢訂單專案")
    harness.write_sql_review("SELECT project_code, order_no FROM orders", {"status": "pass"})
    harness.confirm("sql_review", "同意查詢")
    harness.write_data_preview(
        {
            "status": "executed",
            "row_count": 5305,
            "column_count": 3,
            "duration_ms": 1239,
            "columns": ["project_code", "order_no", "project_local_amount"],
            "sample_rows": [
                {
                    "project_code": "A15-003",
                    "order_no": "150331006",
                    "project_local_amount": 1490000,
                },
                {
                    "project_code": "A15-005",
                    "order_no": "150331007",
                    "project_local_amount": 11000000,
                },
            ],
        }
    )

    with CheckpointCompanionServer.serve(tmp_path / "run-001") as server:
        with urlopen(f"{server.base_url}/runs/run-001/checkpoints/current", timeout=5) as response:
            html = response.read().decode("utf-8")

    assert "Sample Rows" in html
    assert "A15-003" in html
    assert "150331006" in html
    assert "project_local_amount" in html
    assert html.count("<table") >= 2


def test_classification_checkpoint_renders_readable_db_metadata(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="費用分析")
    harness.write_field_formula_classification(
        {
            "columns": [
                {
                    "excel_header": "科目編號",
                    "classification": "db_source_field",
                    "processing_location": "formal_db_sql",
                    "field_metadata": [
                        {
                            "table_id": "ACTML",
                            "table_name": "分類帳檔",
                            "column_id": "ML006",
                            "column_name": "明細科目編號",
                            "business_meaning": "Main ledger account code",
                            "metadata_status": "ok",
                        }
                    ],
                    "confidence": "high",
                    "reason": "Header matched schema.",
                }
            ]
        }
    )

    with CheckpointCompanionServer.serve(tmp_path / "run-001") as server:
        with urlopen(f"{server.base_url}/runs/run-001/checkpoints/current", timeout=5) as response:
            html = response.read().decode("utf-8")

    assert "科目編號" in html
    assert "db_source_field" in html
    assert "formal_db_sql" in html
    assert "明細科目編號" in html
    assert "分類帳檔" in html
    assert "ACTML.ML006" in html


def test_current_checkpoint_page_renders_sqlite_preview_and_retention_payloads(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="費用分析")
    harness.write_raw_data_preview(
        {
            "row_count": 1,
            "columns": ["account_code", "amount"],
            "sample_rows": [{"account_code": "6111", "amount": 100}],
        }
    )

    with CheckpointCompanionServer.serve(tmp_path / "run-001") as server:
        with urlopen(f"{server.base_url}/runs/run-001/checkpoints/current", timeout=5) as response:
            raw_html = response.read().decode("utf-8")

    assert "DB 原始資料確認" in raw_html
    assert "Row Count" in raw_html
    assert "account_code" in raw_html
    assert "6111" in raw_html

    harness.write_enriched_data_preview(
        {
            "row_count": 1,
            "columns": ["account_code", "amount", "amount_twice"],
            "sample_rows": [{"account_code": "6111", "amount": 100, "amount_twice": 200}],
        }
    )

    with CheckpointCompanionServer.serve(tmp_path / "run-001") as server:
        with urlopen(f"{server.base_url}/runs/run-001/checkpoints/current", timeout=5) as response:
            enriched_html = response.read().decode("utf-8")

    assert "SQLite 補欄資料確認" in enriched_html
    assert "amount_twice" in enriched_html
    assert "200" in enriched_html

    harness.write_sqlite_retention(
        {
            "manifest_path": "/tmp/run/sqlite/manifest.json",
            "tables": [{"table_name": "wferp_run_raw_ledger", "row_count": 1}],
            "default_action": "保留本地資料",
        }
    )

    with CheckpointCompanionServer.serve(tmp_path / "run-001") as server:
        with urlopen(f"{server.base_url}/runs/run-001/checkpoints/current", timeout=5) as response:
            retention_html = response.read().decode("utf-8")

    assert "SQLite 暫存資料保留確認" in retention_html
    assert "/tmp/run/sqlite/manifest.json" in retention_html
    assert "wferp_run_raw_ledger" in retention_html
    assert "保留本地資料" in retention_html


def test_excel_confirmation_page_renders_fields_and_formulas_as_tables(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="費用分析")
    harness.write_excel_confirmation(
        {
            "summary": "確認欄位與公式",
            "technical_details": {
                "database_fields": [
                    {
                        "semantic_name": "費用科目",
                        "candidate_columns": ["ACTMA.MA001", "ACTMA.MA003"],
                        "status": "mapped",
                    }
                ],
                "derived_formula_fields": [
                    {"field": "預算差異", "formula": "實際費用合計 - 預算合計"}
                ],
                "recommended_defaults": {"budget_basis": "ACTMK.MK006"},
            },
        }
    )

    with CheckpointCompanionServer.serve(tmp_path / "run-001") as server:
        with urlopen(
            f"{server.base_url}/runs/run-001/checkpoints/excel_confirmation",
            timeout=5,
        ) as response:
            html = response.read().decode("utf-8")

    assert "資料庫欄位來源驗證" in html
    assert "Excel / 報表公式驗證" in html
    assert "ACTMA.MA001, ACTMA.MA003" in html
    assert "實際費用合計 - 預算合計" in html
    assert html.count("<table") >= 2


def test_visual_design_page_renders_html_component_preview(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="查詢費用")
    harness.write_report_selection(
        {"selected_report_type": "管理摘要", "selected_report_design": "financial-control"}
    )
    harness.confirm("report_selection", "產生報告")
    _confirm_design_brief(harness)
    package = {
        "catalog_guardrail": "financial-control",
        "data_profile": {"columns": ["department", "amount"], "row_count": 2},
        "datasets": {"columns": ["department", "amount"]},
        "aggregates": {"amount_sum": 3500},
    }
    payload = build_visual_checkpoint_payload(harness.state()["report_design_brief"], package)
    harness.write_visual_design(payload)

    with CheckpointCompanionServer.serve(tmp_path / "run-001") as server:
        with urlopen(f"{server.base_url}/runs/run-001/checkpoints/visual_design", timeout=5) as response:
            html = response.read().decode("utf-8")

    assert "HTML 版面與元件預覽" in html
    assert 'class="report-preview"' in html
    assert "preview-chart" in html
    assert "preview-table-component" in html
    assert "expense-detail-table" in html
    assert "data-layout-mode" in html
    assert "four-chart-grid" in html
    assert "data-chart-count" in html
    assert "data-chart-type=\"0\"" in html
    assert "Combo：實際 / 預算 / 差異" in html
    assert "Refresh HTML 預覽" in html
    assert "function refreshPreview" in html
    assert "visualSelection" in html


def test_report_draft_page_renders_report_preview_with_actual_table_data(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="查詢費用")
    harness.write_report_selection(
        {"selected_report_type": "管理摘要", "selected_report_design": "financial-control"}
    )
    harness.confirm("report_selection", "產生報告")
    _confirm_design_brief(harness)
    _confirm_visual_design(harness)
    harness.write_report_draft(
        {
            "title": "費用分析財務管控報表",
            "summary": {
                "actual_amount_sum": 62000,
                "budget_amount_sum": 55000,
                "management_conclusion": "旅費為主要超支科目。",
            },
            "charts": [{"id": "expense-driver-ranking", "type": "bar", "x": "expense_account_name", "y": "actual_amount"}],
            "tables": [
                {
                    "id": "expense-detail-table",
                    "columns": ["expense_account_name", "actual_amount", "budget_amount"],
                    "features": ["filter", "sort"],
                    "rows": [
                        {"expense_account_name": "旅費", "actual_amount": 50000, "budget_amount": 40000},
                        {"expense_account_name": "文具", "actual_amount": 12000, "budget_amount": 15000},
                    ],
                }
            ],
            "analysis": ["實際費用合計 62,000。"],
            "recommendations": ["追蹤旅費超支。"],
        }
    )

    with CheckpointCompanionServer.serve(tmp_path / "run-001") as server:
        with urlopen(f"{server.base_url}/runs/run-001/checkpoints/report_draft", timeout=5) as response:
            html = response.read().decode("utf-8")

    assert "HTML 報告初稿預覽" in html
    assert "費用分析財務管控報表" in html
    assert "preview-chart" in html
    assert "旅費" in html
    assert "文具" in html
    assert "追蹤旅費超支" in html
    assert "呈現方式：" in html
    assert "data-refresh-preview" in html


def test_current_checkpoint_page_links_to_available_checkpoint_history(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="查詢費用")
    harness.write_sql_review("SELECT department, amount FROM expenses", {"status": "pass"})
    harness.confirm("sql_review", "同意查詢")
    harness.write_data_preview(
        {
            "columns": ["department", "amount"],
            "row_count": 1,
            "rows": [{"department": "管理部", "amount": 1000}],
        }
    )

    with CheckpointCompanionServer.serve(tmp_path / "run-001") as server:
        with urlopen(f"{server.base_url}/runs/run-001/checkpoints/current", timeout=5) as response:
            html = response.read().decode("utf-8")

    assert 'href="/runs/run-001/checkpoints/sql_review"' in html
    assert 'href="/runs/run-001/checkpoints/data_preview"' in html
    assert "資料預覽確認" in html


def test_specific_checkpoint_history_page_renders_requested_payload(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="查詢費用")
    harness.write_sql_review("SELECT department, amount FROM expenses", {"status": "pass"})
    harness.confirm("sql_review", "同意查詢")
    harness.write_data_preview(
        {
            "columns": ["department", "amount"],
            "row_count": 1,
            "rows": [{"department": "管理部", "amount": 1000}],
        }
    )

    with CheckpointCompanionServer.serve(tmp_path / "run-001") as server:
        with urlopen(f"{server.base_url}/runs/run-001/checkpoints/sql_review", timeout=5) as response:
            html = response.read().decode("utf-8")

    assert response.status == 200
    assert "SQL 查詢確認" in html
    assert "SELECT department, amount FROM expenses" in html
    assert "/api/runs/run-001/checkpoints/sql_review/confirm" in html
    assert "data-action=\"同意查詢\"" in html
    assert 'class="step current"' in html


def test_current_checkpoint_page_click_script_posts_confirmation(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="查詢費用")
    harness.write_sql_review("SELECT department, amount FROM expenses", {"status": "pass"})

    with CheckpointCompanionServer.serve(tmp_path / "run-001") as server:
        with urlopen(f"{server.base_url}/runs/run-001/checkpoints/current", timeout=5) as response:
            html = response.read().decode("utf-8")
        result = post_json(
            f"{server.base_url}/api/runs/run-001/checkpoints/sql_review/confirm",
            {
                "action": "同意查詢",
                "checkpointId": "sql_review",
                "comment": "from companion",
                "selectedOptions": {"source": "visual_companion"},
            },
        )

    assert "async function confirmCheckpoint" in html
    assert "confirmation-status" in html
    assert result["status"] == "confirmed"
    assert harness.state()["user_confirmations"]["sql_review"] == "同意查詢"


def test_final_review_post_selected_options_allow_matching_residual_risk_delivery(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="查詢費用")
    harness.write_report_selection(
        {"selected_report_type": "管理摘要", "selected_report_design": "financial-control"}
    )
    harness.confirm("report_selection", "產生報告")
    _confirm_design_brief(harness)
    _confirm_visual_design(harness)
    harness.write_report_draft({"sections": ["摘要"]})
    harness.confirm("report_draft", "接受")
    harness.write_final_review(
        {
            "validator_results": _all_validator_results({"visual_taste_reviewer": "warning"}),
        }
    )

    with CheckpointCompanionServer.serve(tmp_path / "run-001") as server:
        result = post_json(
            f"{server.base_url}/api/runs/run-001/checkpoints/final_review/confirm",
            {
                "action": "完成",
                "checkpointId": "final_review",
                "selectedOptions": {
                    "acceptedResidualRisks": [
                        "visual_taste_reviewer: accepted risk for visual_taste_reviewer"
                    ]
                },
            },
        )

    state = harness.state()
    assert result["status"] == "confirmed"
    assert state["user_confirmation_options"]["final_review"] == {
        "acceptedResidualRisks": ["visual_taste_reviewer: accepted risk for visual_taste_reviewer"]
    }
    assert harness.can_deliver() == {
        "allowed": True,
        "blocking_validators": [],
        "accepted_residual_risks": ["visual_taste_reviewer: accepted risk for visual_taste_reviewer"],
    }


def test_final_review_page_renders_role_prefixed_residual_risk_values(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="查詢費用")
    harness.write_report_selection(
        {"selected_report_type": "管理摘要", "selected_report_design": "financial-control"}
    )
    harness.confirm("report_selection", "產生報告")
    _confirm_design_brief(harness)
    _confirm_visual_design(harness)
    harness.write_report_draft({"sections": ["摘要"]})
    harness.confirm("report_draft", "接受")
    harness.write_final_review(
        {
            "validator_results": _all_validator_results({"visual_taste_reviewer": "warning"}),
            "residual_risks": ["accepted risk for visual_taste_reviewer"],
        }
    )

    with CheckpointCompanionServer.serve(tmp_path / "run-001") as server:
        with urlopen(f"{server.base_url}/runs/run-001/checkpoints/current", timeout=5) as response:
            html = response.read().decode("utf-8")

    assert 'data-risk="visual_taste_reviewer: accepted risk for visual_taste_reviewer"' in html

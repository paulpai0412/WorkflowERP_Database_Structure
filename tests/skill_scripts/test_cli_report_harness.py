from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from skill_scripts.report_package import build_report_package
from skill_scripts.validator_contracts import REQUIRED_VALIDATORS
from tests.skill_scripts.test_excel_intake import _write_requirement_workbook
from tests.skill_scripts.test_report_package import _accepted_report_run


def _run_cli(args: list[str], cwd: Path, env: dict[str, str] | None = None):
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        [sys.executable, "-m", "skill_scripts.cli_report_harness", *args],
        cwd=cwd,
        env=merged_env,
        text=True,
        capture_output=True,
        check=False,
    )


def _passing_final_review_payload() -> dict[str, object]:
    validator_results = []
    for role in REQUIRED_VALIDATORS:
        evidence: list[dict[str, object]] = [{"command": f"review {role}", "status": "pass"}]
        if role == "data_preview_reviewer":
            evidence = [
                {
                    "name": "preview_shape",
                    "status": "pass",
                    "metrics": {"row_count": 1, "column_count": 2},
                }
            ]
        validator_results.append(
            {
                "role": role,
                "status": "pass",
                "evidence": evidence,
                "findings": [],
                "requiredFixes": [],
                "residualRisks": [],
            }
        )
    return {"validator_results": validator_results}


def _single_html_package(tmp_path: Path) -> dict[str, object]:
    harness = _accepted_report_run(tmp_path)
    return build_report_package(harness.run_dir)


def _single_html_brief() -> dict[str, object]:
    return {
        "schema_version": "wferp.report-design-brief.v1",
        "title": "採購單查詢",
        "layout": {"sections": ["summary", "table"]},
    }


def test_cli_report_harness_creates_run_from_prompt_only(tmp_path: Path):
    run_dir = tmp_path / "runs" / "prompt-only"

    result = _run_cli(
        ["--prompt", "請產出費用分析", "--run-dir", str(run_dir)],
        cwd=Path.cwd(),
    )

    assert result.returncode == 0, result.stderr
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert state["prompt"] == "請產出費用分析"


def test_cli_report_harness_help_is_available():
    result = _run_cli(["--help"], cwd=Path.cwd())

    assert result.returncode == 0
    assert "Create and advance WFERP report harness runs" in result.stdout


def test_cli_export_single_html_writes_delivery_output(tmp_path: Path):
    run_dir = tmp_path / "runs" / "single-html"

    result = _run_cli(
        [
            "export-single-html",
            "--run-dir",
            str(run_dir),
            "--package",
            json.dumps(_single_html_package(tmp_path), ensure_ascii=False),
            "--brief",
            json.dumps(_single_html_brief(), ensure_ascii=False),
        ],
        cwd=Path.cwd(),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "exported"
    assert (run_dir / "delivery" / "report.html").exists()
    assert (run_dir / "delivery" / "delivery-manifest.json").exists()


def test_cli_export_single_html_rejects_invalid_package_without_writing_html(tmp_path: Path):
    run_dir = tmp_path / "runs" / "readonly-reject"
    package = _single_html_package(tmp_path)
    package["sql"]["text"] = "DELETE FROM expenses"

    result = _run_cli(
        [
            "export-single-html",
            "--run-dir",
            str(run_dir),
            "--package",
            json.dumps(package, ensure_ascii=False),
            "--brief",
            json.dumps(_single_html_brief(), ensure_ascii=False),
        ],
        cwd=Path.cwd(),
    )

    assert result.returncode == 2
    error = json.loads(result.stderr)
    assert error["status"] == "error"
    assert error["code"] == "single_html_export_error"
    assert "sql_readonly" in error["message"]
    assert not (run_dir / "delivery" / "report.html").exists()


def test_cli_validate_single_html_reports_static_result(tmp_path: Path):
    html = tmp_path / "report.html"
    html.write_text(
        """<!doctype html><html><body>
        <script>window.__WFERP_REPORT_PACKAGE__="abc";</script>
        </body></html>""",
        encoding="utf-8",
    )

    result = _run_cli(["validate-single-html", "--html", str(html)], cwd=Path.cwd())

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "validated"
    assert payload["valid"] is True
    assert payload["errors"] == []


def test_cli_validate_single_html_exits_nonzero_for_network_reference(tmp_path: Path):
    html = tmp_path / "report.html"
    html.write_text(
        """<!doctype html><html><head>
        <script src="https://cdn.example/app.js"></script>
        </head><body></body></html>""",
        encoding="utf-8",
    )

    result = _run_cli(["validate-single-html", "--html", str(html)], cwd=Path.cwd())

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "validated"
    assert "external_script" in payload["errors"]
    assert "missing_package" in payload["errors"]


def test_cli_validate_single_html_reports_missing_file_on_stderr(tmp_path: Path):
    missing = tmp_path / "missing-report.html"

    result = _run_cli(["validate-single-html", "--html", str(missing)], cwd=Path.cwd())

    assert result.returncode == 2
    assert result.stdout == ""
    payload = json.loads(result.stderr)
    assert payload["status"] == "error"
    assert payload["code"] == "single_html_validation_error"
    assert str(missing) in payload["message"]


def test_cli_report_harness_accepts_excel_input_path(tmp_path: Path):
    workbook = tmp_path / "requirement.xlsx"
    _write_requirement_workbook(workbook)
    run_dir = tmp_path / "runs" / "with-excel"

    result = _run_cli(
        ["--prompt", "請產出費用分析", "--input-file", str(workbook), "--run-dir", str(run_dir)],
        cwd=Path.cwd(),
    )

    assert result.returncode == 0, result.stderr
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert str(workbook) in state["input_files"]
    assert state["excel_requirement"]["database_fields"]


def test_cli_report_harness_builds_excel_checkpoint(tmp_path: Path):
    workbook = tmp_path / "requirement.xlsx"
    _write_requirement_workbook(workbook)
    run_dir = tmp_path / "runs" / "excel-checkpoint"

    result = _run_cli(
        [
            "--prompt",
            "請產出費用分析",
            "--input-file",
            str(workbook),
            "--run-dir",
            str(run_dir),
            "--checkpoint",
            "excel",
        ],
        cwd=Path.cwd(),
    )

    assert result.returncode == 0, result.stderr
    checkpoint = json.loads(
        (run_dir / "checkpoints" / "01_excel_confirmation.json").read_text(encoding="utf-8")
    )
    assert checkpoint["title"] == "確認欄位與公式"


def test_cli_report_harness_builds_sql_checkpoint(tmp_path: Path):
    run_dir = tmp_path / "runs" / "sql-checkpoint"

    result = _run_cli(
        [
            "--prompt",
            "查詢採購單前 20 筆",
            "--run-dir",
            str(run_dir),
            "--checkpoint",
            "sql",
            "--mode",
            "rule",
        ],
        cwd=Path.cwd(),
    )

    assert result.returncode == 0, result.stderr
    checkpoint = json.loads((run_dir / "checkpoints" / "02_sql_review.json").read_text(encoding="utf-8"))
    assert checkpoint["title"] == "SQL 查詢確認"
    assert checkpoint["payload"]["sql"].lstrip().upper().startswith("SELECT")


def test_cli_report_harness_does_not_execute_db_without_confirmation_flag(tmp_path: Path):
    run_dir = tmp_path / "runs" / "no-execution"

    result = _run_cli(
        [
            "--prompt",
            "查詢採購單前 20 筆",
            "--run-dir",
            str(run_dir),
            "--checkpoint",
            "sql",
            "--validate-execution",
        ],
        cwd=Path.cwd(),
        env={"DB_ENV": "test"},
    )

    assert result.returncode == 0, result.stderr
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert state["execution_result_summary"] is None
    assert "SQL 尚未確認" in result.stdout


def test_cli_report_harness_requires_allow_non_test_db_execution_for_non_test_env(tmp_path: Path):
    run_dir = tmp_path / "runs" / "prod-block"

    result = _run_cli(
        [
            "--prompt",
            "查詢採購單前 20 筆",
            "--run-dir",
            str(run_dir),
            "--confirm-sql",
            "--validate-execution",
        ],
        cwd=Path.cwd(),
        env={"DB_ENV": "production"},
    )

    assert result.returncode != 0
    assert "--allow-non-test-db-execution" in result.stderr


def test_cli_confirm_sql_requires_existing_sql_review(tmp_path: Path):
    run_dir = tmp_path / "runs" / "confirm-without-sql"

    result = _run_cli(
        [
            "--prompt",
            "請產出費用分析",
            "--run-dir",
            str(run_dir),
            "--confirm-sql",
            "--validate-execution",
        ],
        cwd=Path.cwd(),
        env={"DB_ENV": "test"},
    )

    assert result.returncode != 0
    assert "reviewed SQL" in result.stderr


def test_cli_report_selection_persists_report_type_and_design(tmp_path: Path):
    run_dir = tmp_path / "runs" / "report-selection"

    result = _run_cli(
        [
            "--prompt",
            "請產出費用分析",
            "--run-dir",
            str(run_dir),
            "--report-type",
            "管理摘要",
            "--report-design",
            "financial-control",
            "--include-chart",
            "--include-table",
            "--include-analysis",
        ],
        cwd=Path.cwd(),
    )

    assert result.returncode == 0, result.stderr
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert state["report_type"] == "管理摘要"
    assert state["report_design"] == "financial-control"
    assert state["report_options"]["include_chart"] is True


def test_cli_report_selection_rejects_unknown_report_design(tmp_path: Path):
    run_dir = tmp_path / "runs" / "unknown-report-design"

    result = _run_cli(
        [
            "--prompt",
            "請產出費用分析",
            "--run-dir",
            str(run_dir),
            "--checkpoint",
            "report-selection",
            "--report-design",
            "rogue-design",
        ],
        cwd=Path.cwd(),
    )

    assert result.returncode == 2
    error = json.loads(result.stderr)
    assert error == {
        "status": "error",
        "code": "unknown_report_design",
        "message": "Unknown report design profile: rogue-design",
    }
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert state["report_design"] is None
    assert not (run_dir / "checkpoints" / "04_report_selection.json").exists()


def test_cli_full_flow_blocks_and_advances_by_confirmation(tmp_path: Path):
    run_root = tmp_path / "runs"
    run_dir = run_root / "run-001"

    created = _run_cli(
        [
            "create-run",
            "--run-root",
            str(run_root),
            "--run-id",
            "run-001",
            "--prompt",
            "查詢費用分析",
        ],
        cwd=Path.cwd(),
    )

    assert created.returncode == 0, created.stderr
    assert json.loads(created.stdout)["status"] == "created"

    sql_review = _run_cli(
        [
            "write-sql-review",
            "--run-dir",
            str(run_dir),
            "--sql",
            "SELECT department, amount FROM expenses",
        ],
        cwd=Path.cwd(),
    )

    assert sql_review.returncode == 0, sql_review.stderr
    assert json.loads(sql_review.stdout)["checkpoint"] == "sql_review"

    blocked_preview = _run_cli(
        [
            "write-data-preview",
            "--run-dir",
            str(run_dir),
            "--payload",
            '{"rows":[]}',
        ],
        cwd=Path.cwd(),
    )

    assert blocked_preview.returncode == 2
    assert "SQL must be confirmed" in blocked_preview.stderr
    assert not (run_dir / "data" / "execution-result.json").exists()

    confirmed = _run_cli(
        [
            "confirm",
            "--run-dir",
            str(run_dir),
            "--checkpoint",
            "sql_review",
            "--action",
            "同意查詢",
        ],
        cwd=Path.cwd(),
    )

    assert confirmed.returncode == 0, confirmed.stderr
    assert json.loads(confirmed.stdout)["status"] == "confirmed"

    data_preview = _run_cli(
        [
            "write-data-preview",
            "--run-dir",
            str(run_dir),
            "--payload",
            '{"rows":[{"department":"管理部","amount":1000}],"columns":["department","amount"],"row_count":1}',
        ],
        cwd=Path.cwd(),
    )

    assert data_preview.returncode == 0, data_preview.stderr
    assert json.loads(data_preview.stdout)["checkpoint"] == "data_preview"


def test_cli_full_flow_writes_draft_final_review_and_delivery_gate(tmp_path: Path):
    run_root = tmp_path / "runs"
    run_dir = run_root / "run-002"
    final_review_payload = tmp_path / "final-review.json"
    final_review_payload.write_text(
        json.dumps(_passing_final_review_payload(), ensure_ascii=False),
        encoding="utf-8",
    )
    visual_brief = json.dumps(
        {
            "schema_version": "wferp.design-brief.v1",
            "report_intent": {
                "prompt": "查詢費用分析",
                "report_type": "管理摘要",
                "primary_goal": "Expose financial-control exceptions.",
            },
            "catalog_guardrail": "financial-control",
            "target_audience": {"role": "finance controller", "needs": ["expense review"]},
            "layout_recipe": {
                "mode": "kpi-first-dashboard",
                "sections": ["executive-summary", "kpi-overview", "data-table"],
                "density": "analysis-first",
            },
            "chart_recipe": [
                {
                    "id": "expense-trend",
                    "type": "line",
                    "purpose": "Reveal period trend and month-over-month movement.",
                }
            ],
            "table_recipe": [
                {
                    "id": "expense-detail-table",
                    "type": "data-table",
                    "features": ["filter", "sort", "drilldown", "column_visibility"],
                    "row_count": 1,
                }
            ],
            "interaction_recipe": {
                "filters": ["department", "amount"],
                "drilldowns": ["department"],
            },
            "visual_direction": {
                "tone": "quiet financial operations dashboard",
                "emphasis": ["variance", "outliers"],
            },
            "embedded_data_policy": {"mode": "smart-tiered", "summary_threshold_rows": 5000},
        },
        ensure_ascii=False,
    )
    visual_package = json.dumps(
        {
            "catalog_guardrail": "financial-control",
            "prompt": "查詢費用分析",
            "report_type": "管理摘要",
            "data_profile": {"columns": ["department", "amount"], "row_count": 1},
            "datasets": {
                "columns": ["department", "amount"],
                "embedded_rows": [{"department": "管理部", "amount": 1000}],
            },
            "aggregates": {"amount_sum": 1000, "amount_avg": 1000},
        },
        ensure_ascii=False,
    )

    steps = [
        [
            "create-run",
            "--run-root",
            str(run_root),
            "--run-id",
            "run-002",
            "--prompt",
            "查詢費用分析",
        ],
        [
            "write-sql-review",
            "--run-dir",
            str(run_dir),
            "--sql",
            "SELECT department, amount FROM expenses",
        ],
        [
            "confirm",
            "--run-dir",
            str(run_dir),
            "--checkpoint",
            "sql_review",
            "--action",
            "同意查詢",
        ],
        [
            "write-data-preview",
            "--run-dir",
            str(run_dir),
            "--payload",
            '{"rows":[{"department":"管理部","amount":1000}],"columns":["department","amount"],"row_count":1}',
        ],
        [
            "write-report-selection",
            "--run-dir",
            str(run_dir),
            "--report-type",
            "管理摘要",
            "--report-design",
            "financial-control",
            "--include-chart",
            "--include-table",
        ],
        [
            "confirm",
            "--run-dir",
            str(run_dir),
            "--checkpoint",
            "report_selection",
            "--action",
            "產生報告",
        ],
        [
            "write-design-brief",
            "--run-dir",
            str(run_dir),
            "--package",
            '{"catalog_guardrail":"financial-control","prompt":"查詢費用分析","data_profile":{"columns":["department","amount"],"row_count":1},"datasets":{"columns":["department","amount"]}}',
        ],
        [
            "confirm",
            "--run-dir",
            str(run_dir),
            "--checkpoint",
            "design_brief",
            "--action",
            "確認設計",
        ],
        [
            "write-visual-checkpoint",
            "--run-dir",
            str(run_dir),
            "--brief",
            visual_brief,
            "--package",
            visual_package,
        ],
        [
            "confirm",
            "--run-dir",
            str(run_dir),
            "--checkpoint",
            "visual_design",
            "--action",
            "確認視覺設計",
        ],
        [
            "write-report-draft",
            "--run-dir",
            str(run_dir),
            "--payload",
            '{"sections":["executive-summary","data-table"],"workspace":"report"}',
        ],
        [
            "confirm",
            "--run-dir",
            str(run_dir),
            "--checkpoint",
            "report_draft",
            "--action",
            "接受",
        ],
        [
            "write-final-review",
            "--run-dir",
            str(run_dir),
            "--payload",
            str(final_review_payload),
        ],
    ]

    for step in steps:
        result = _run_cli(step, cwd=Path.cwd())
        assert result.returncode == 0, result.stderr

    delivery = _run_cli(["can-deliver", "--run-dir", str(run_dir)], cwd=Path.cwd())

    assert delivery.returncode == 0, delivery.stderr
    assert json.loads(delivery.stdout)["allowed"] is True
    assert (run_dir / "checkpoints" / "04a_design_brief.json").exists()
    assert (run_dir / "checkpoints" / "04b_visual_design.json").exists()
    assert (run_dir / "visual" / "visual-checkpoint.html").exists()
    assert (run_dir / "checkpoints" / "05_report_draft.json").exists()
    assert (run_dir / "checkpoints" / "06_final_review.json").exists()


def test_cli_write_design_brief_success(tmp_path: Path):
    run_root = tmp_path / "runs"
    run_dir = run_root / "run-design"
    package = tmp_path / "package.json"
    package.write_text(
        json.dumps(
            {
                "catalog_guardrail": "financial-control",
                "prompt": "查詢費用分析",
                "data_profile": {
                    "columns": ["month", "department", "amount"],
                    "row_count": 1,
                },
                "datasets": {"columns": ["month", "department", "amount"]},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    created = _run_cli(
        [
            "create-run",
            "--run-root",
            str(run_root),
            "--run-id",
            "run-design",
            "--prompt",
            "查詢費用分析",
        ],
        cwd=Path.cwd(),
    )
    assert created.returncode == 0, created.stderr

    result = _run_cli(
        ["write-design-brief", "--run-dir", str(run_dir), "--package", str(package)],
        cwd=Path.cwd(),
    )

    assert result.returncode == 0, result.stderr
    checkpoint = json.loads(result.stdout)
    assert checkpoint["checkpoint"] == "design_brief"
    assert checkpoint["payload"]["embedded_data_policy"]["mode"] == "smart-tiered"
    assert checkpoint["payload"]["chart_recipe"][0]["type"] == "line"


def test_cli_write_visual_checkpoint_success(tmp_path: Path):
    run_root = tmp_path / "runs"
    run_dir = run_root / "run-visual"
    created = _run_cli(
        [
            "create-run",
            "--run-root",
            str(run_root),
            "--run-id",
            "run-visual",
            "--prompt",
            "查詢費用分析",
        ],
        cwd=Path.cwd(),
    )
    assert created.returncode == 0, created.stderr

    brief = {
        "schema_version": "wferp.design-brief.v1",
        "report_intent": {
            "prompt": "查詢費用分析",
            "report_type": "管理摘要",
            "primary_goal": "Expose financial-control exceptions.",
        },
        "catalog_guardrail": "financial-control",
        "target_audience": {"role": "finance controller", "needs": ["expense review"]},
        "layout_recipe": {
            "mode": "kpi-first-dashboard",
            "sections": ["executive-summary", "kpi-overview", "data-table"],
            "density": "analysis-first",
        },
        "chart_recipe": [
            {
                "id": "expense-trend",
                "type": "line",
                "purpose": "Reveal period trend and month-over-month movement.",
            }
        ],
        "table_recipe": [
            {
                "id": "expense-detail-table",
                "type": "data-table",
                "features": ["filter", "sort", "drilldown", "column_visibility"],
                "row_count": 1,
            }
        ],
        "interaction_recipe": {"filters": ["department", "amount"], "drilldowns": ["department"]},
        "visual_direction": {
            "tone": "quiet financial operations dashboard",
            "emphasis": ["variance", "outliers"],
        },
        "embedded_data_policy": {"mode": "smart-tiered", "summary_threshold_rows": 5000},
    }
    package = {
        "catalog_guardrail": "financial-control",
        "prompt": "查詢費用分析",
        "report_type": "管理摘要",
        "data_profile": {"columns": ["department", "amount"], "row_count": 1},
        "datasets": {
            "columns": ["department", "amount"],
            "embedded_rows": [{"department": "管理部", "amount": 1000}],
        },
        "aggregates": {"amount_sum": 1000, "amount_avg": 1000},
    }
    harness_steps = [
        [
            "write-design-brief",
            "--run-dir",
            str(run_dir),
            "--package",
            json.dumps(package, ensure_ascii=False),
        ],
        [
            "confirm",
            "--run-dir",
            str(run_dir),
            "--checkpoint",
            "design_brief",
            "--action",
            "確認設計",
        ],
    ]
    for step in harness_steps:
        result = _run_cli(step, cwd=Path.cwd())
        assert result.returncode == 0, result.stderr

    result = _run_cli(
        [
            "write-visual-checkpoint",
            "--run-dir",
            str(run_dir),
            "--brief",
            json.dumps(brief, ensure_ascii=False),
            "--package",
            json.dumps(package, ensure_ascii=False),
        ],
        cwd=Path.cwd(),
    )

    assert result.returncode == 0, result.stderr
    checkpoint = json.loads(result.stdout)
    html_text = (run_dir / "visual" / "visual-checkpoint.html").read_text(encoding="utf-8")
    assert checkpoint["checkpoint"] == "visual_design"
    assert checkpoint["payload"]["kpis"][0] == {"label": "amount_sum", "value": 1000}
    assert "費用分析視覺設計確認" in html_text or "visual-checkpoint" in html_text
    assert not html_text.lstrip().startswith("{")
    assert '"html":' not in html_text
    assert "fetch(" not in html_text


def test_cli_rewriting_design_brief_removes_stale_visual_checkpoint_html(tmp_path: Path):
    run_root = tmp_path / "runs"
    run_dir = run_root / "run-visual-invalidation"
    created = _run_cli(
        [
            "create-run",
            "--run-root",
            str(run_root),
            "--run-id",
            "run-visual-invalidation",
            "--prompt",
            "查詢費用分析",
        ],
        cwd=Path.cwd(),
    )
    assert created.returncode == 0, created.stderr

    package = {
        "catalog_guardrail": "financial-control",
        "prompt": "查詢費用分析",
        "report_type": "管理摘要",
        "data_profile": {"columns": ["department", "amount"], "row_count": 1},
        "datasets": {
            "columns": ["department", "amount"],
            "embedded_rows": [{"department": "管理部", "amount": 1000}],
        },
        "aggregates": {"amount_sum": 1000, "amount_avg": 1000},
    }
    design_brief = _run_cli(
        [
            "write-design-brief",
            "--run-dir",
            str(run_dir),
            "--package",
            json.dumps(package, ensure_ascii=False),
        ],
        cwd=Path.cwd(),
    )
    assert design_brief.returncode == 0, design_brief.stderr
    brief_payload = json.loads(design_brief.stdout)["payload"]

    confirmed = _run_cli(
        [
            "confirm",
            "--run-dir",
            str(run_dir),
            "--checkpoint",
            "design_brief",
            "--action",
            "確認設計",
        ],
        cwd=Path.cwd(),
    )
    assert confirmed.returncode == 0, confirmed.stderr

    visual = _run_cli(
        [
            "write-visual-checkpoint",
            "--run-dir",
            str(run_dir),
            "--brief",
            json.dumps(brief_payload, ensure_ascii=False),
            "--package",
            json.dumps(package, ensure_ascii=False),
        ],
        cwd=Path.cwd(),
    )
    assert visual.returncode == 0, visual.stderr
    assert (run_dir / "checkpoints" / "04b_visual_design.json").exists()
    assert (run_dir / "visual" / "visual-checkpoint.html").exists()

    rewritten = _run_cli(
        [
            "write-design-brief",
            "--run-dir",
            str(run_dir),
            "--package",
            json.dumps({**package, "prompt": "重寫費用分析設計"}, ensure_ascii=False),
        ],
        cwd=Path.cwd(),
    )
    assert rewritten.returncode == 0, rewritten.stderr
    rewritten_brief_payload = json.loads(rewritten.stdout)["payload"]
    assert not (run_dir / "checkpoints" / "04b_visual_design.json").exists()
    assert not (run_dir / "visual" / "visual-checkpoint.html").exists()

    blocked_visual = _run_cli(
        [
            "write-visual-checkpoint",
            "--run-dir",
            str(run_dir),
            "--brief",
            json.dumps(rewritten_brief_payload, ensure_ascii=False),
            "--package",
            json.dumps(package, ensure_ascii=False),
        ],
        cwd=Path.cwd(),
    )
    assert blocked_visual.returncode == 2
    error = json.loads(blocked_visual.stderr)
    assert error["code"] == "visual_checkpoint_error"
    assert "Design brief must be confirmed" in error["message"]
    assert not (run_dir / "visual" / "visual-checkpoint.html").exists()


def test_cli_write_visual_checkpoint_does_not_leave_html_when_design_brief_unconfirmed(
    tmp_path: Path,
):
    run_root = tmp_path / "runs"
    run_dir = run_root / "run-visual-unconfirmed"
    created = _run_cli(
        [
            "create-run",
            "--run-root",
            str(run_root),
            "--run-id",
            "run-visual-unconfirmed",
            "--prompt",
            "查詢費用分析",
        ],
        cwd=Path.cwd(),
    )
    assert created.returncode == 0, created.stderr

    package = {
        "catalog_guardrail": "financial-control",
        "prompt": "查詢費用分析",
        "report_type": "管理摘要",
        "data_profile": {"columns": ["department", "amount"], "row_count": 1},
        "datasets": {
            "columns": ["department", "amount"],
            "embedded_rows": [{"department": "管理部", "amount": 1000}],
        },
        "aggregates": {"amount_sum": 1000, "amount_avg": 1000},
    }
    design_brief = _run_cli(
        [
            "write-design-brief",
            "--run-dir",
            str(run_dir),
            "--package",
            json.dumps(package, ensure_ascii=False),
        ],
        cwd=Path.cwd(),
    )
    assert design_brief.returncode == 0, design_brief.stderr

    result = _run_cli(
        [
            "write-visual-checkpoint",
            "--run-dir",
            str(run_dir),
            "--brief",
            json.dumps(json.loads(design_brief.stdout)["payload"], ensure_ascii=False),
            "--package",
            json.dumps(package, ensure_ascii=False),
        ],
        cwd=Path.cwd(),
    )

    assert result.returncode == 2
    error = json.loads(result.stderr)
    assert error["code"] == "visual_checkpoint_error"
    assert "Design brief must be confirmed" in error["message"]
    assert not (run_dir / "visual" / "visual-checkpoint.html").exists()


def test_cli_write_design_brief_reports_validation_errors_from_overrides(tmp_path: Path):
    run_root = tmp_path / "runs"
    run_dir = run_root / "run-invalid-design"
    created = _run_cli(
        [
            "create-run",
            "--run-root",
            str(run_root),
            "--run-id",
            "run-invalid-design",
            "--prompt",
            "查詢費用分析",
        ],
        cwd=Path.cwd(),
    )
    assert created.returncode == 0, created.stderr

    result = _run_cli(
        [
            "write-design-brief",
            "--run-dir",
            str(run_dir),
            "--package",
            '{"catalog_guardrail":"financial-control","data_profile":{"columns":["department","amount"]},"datasets":{"columns":["department","amount"]}}',
            "--overrides",
            '{"chart_recipe":[{"type":"combo"}]}',
        ],
        cwd=Path.cwd(),
    )

    assert result.returncode == 2
    error = json.loads(result.stderr)
    assert error["code"] == "design_brief_invalid"
    assert "chart_recipe[0].purpose" in error["message"]


def test_cli_write_design_brief_rejects_malformed_package_catalog_guardrail(tmp_path: Path):
    run_root = tmp_path / "runs"
    run_dir = run_root / "run-invalid-catalog"
    created = _run_cli(
        [
            "create-run",
            "--run-root",
            str(run_root),
            "--run-id",
            "run-invalid-catalog",
            "--prompt",
            "查詢費用分析",
        ],
        cwd=Path.cwd(),
    )
    assert created.returncode == 0, created.stderr

    result = _run_cli(
        [
            "write-design-brief",
            "--run-dir",
            str(run_dir),
            "--package",
            '{"catalog_guardrail":["bad"],"data_profile":{"columns":["department","amount"]},"datasets":{"columns":["department","amount"]}}',
        ],
        cwd=Path.cwd(),
    )

    assert result.returncode == 2
    error = json.loads(result.stderr)
    assert error["code"] == "design_brief_invalid"
    assert "catalog_guardrail" in error["message"]

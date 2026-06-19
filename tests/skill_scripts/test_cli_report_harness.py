from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from skill_scripts.report_harness import ReportHarness
from skill_scripts.report_package import build_report_package
from skill_scripts.style_replay import build_style_capsule
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
        if role == "excel_classification_reviewer":
            evidence = [
                {"type": "file", "path": "data/field-classification.json"},
                {"type": "metric", "name": "classified_columns", "value": 4},
                {"type": "metric", "name": "db_field_count", "value": 2},
                {"type": "metric", "name": "formula_field_count", "value": 1},
                {"type": "metric", "name": "lookup_field_count", "value": 1},
                {"type": "metric", "name": "manual_only_count", "value": 0},
                {"type": "inspection", "name": "metadata_readability", "status": "pass"},
            ]
        if role == "sqlite_enrichment_reviewer":
            evidence = [
                {"type": "file", "path": "sqlite/wferp_run_sqlite_manifest.json"},
                {"type": "metric", "name": "raw_row_count", "value": 1},
                {"type": "metric", "name": "enriched_row_count", "value": 1},
                {"type": "metric", "name": "ignored_lookup_rows", "value": 0},
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


def _style_capsule() -> dict[str, object]:
    return build_style_capsule(
        {
            "catalog_guardrail": "trend-briefing",
            "layout_recipe": {"mode": "trend-first"},
            "chart_recipe": [{"id": "period_trend", "type": "line", "required_columns": ["period"]}],
            "table_recipe": [{"id": "period_table", "features": ["filter"]}],
            "interaction_recipe": {"cross_filter": True},
            "visual_direction": {"tone": "趨勢解讀"},
            "embedded_data_policy": {"mode": "smart-tiered"},
        }
    )


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _sheet_xml(rows: list[list[str | int | tuple[str, str] | None]]) -> str:
    rendered_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row, start=1):
            cell_ref = f"{_column_name(column_index)}{row_index}"
            if isinstance(value, tuple) and value[0] == "formula":
                formula = value[1].lstrip("=")
                cells.append(f'<c r="{cell_ref}"><f>{escape(formula)}</f><v></v></c>')
            elif value is None:
                cells.append(f'<c r="{cell_ref}" t="inlineStr"><is><t></t></is></c>')
            else:
                cells.append(
                    f'<c r="{cell_ref}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'
                )
        rendered_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(rendered_rows)}</sheetData>'
        "</worksheet>"
    )


def _classification_workbook(path: Path) -> None:
    sheets = [
        (
            "明細帳",
            [
                ["科目編號", "傳票日期", "金額-原幣", "BU"],
                ["6111", "20260101", ("formula", "=C2-D2"), ("formula", "=VLOOKUP(A2,對照表!A:B,2,0)")],
            ],
        ),
        (
            "對照表",
            [
                ["科目編號", "BU", "費用類別"],
                ["公司別", "AIS", ""],
                ["科目編號", "BU", "費用類別"],
                ["6111", "營運管理中心", "8.租金支出"],
                [None, None, None],
                ["加總 - 換算台幣", None, None],
            ],
        ),
    ]
    workbook_sheets = []
    rels = []
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            + "".join(
                f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                for index, _ in enumerate(sheets, start=1)
            )
            + "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>",
        )
        for index, (name, rows) in enumerate(sheets, start=1):
            workbook_sheets.append(
                f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>'
            )
            rels.append(
                f'<Relationship Id="rId{index}" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                f'Target="worksheets/sheet{index}.xml"/>'
            )
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _sheet_xml(rows))
        archive.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<sheets>{"".join(workbook_sheets)}</sheets>'
            "</workbook>",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'{"".join(rels)}'
            "</Relationships>",
        )


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


def test_cli_inspect_style_replay_allows_compatible_columns():
    result = _run_cli(
        [
            "inspect-style-replay",
            "--capsule",
            json.dumps(_style_capsule(), ensure_ascii=False),
            "--columns",
            "period,amount",
        ],
        cwd=Path.cwd(),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "checked"
    assert payload["requires_checkpoint"] is False


def test_cli_inspect_style_replay_requires_checkpoint_for_missing_columns():
    result = _run_cli(
        [
            "inspect-style-replay",
            "--capsule",
            json.dumps(_style_capsule(), ensure_ascii=False),
            "--columns",
            "department,amount",
        ],
        cwd=Path.cwd(),
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "checked"
    assert payload["requires_checkpoint"] is True
    assert payload["incompatible_charts"] == ["period_trend"]


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


def test_cli_wait_confirmation_returns_existing_checkpoint_confirmation(tmp_path: Path):
    run_root = tmp_path / "runs"
    run_dir = run_root / "run-wait-existing"

    created = _run_cli(
        [
            "create-run",
            "--run-root",
            str(run_root),
            "--run-id",
            "run-wait-existing",
            "--prompt",
            "查詢費用分析",
        ],
        cwd=Path.cwd(),
    )
    assert created.returncode == 0, created.stderr

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

    confirmed = _run_cli(
        [
            "confirm",
            "--run-dir",
            str(run_dir),
            "--checkpoint",
            "sql_review",
            "--action",
            "調整需求",
            "--comment",
            "請加入期預算比較",
            "--selected-option",
            "chart=bar",
        ],
        cwd=Path.cwd(),
    )
    assert confirmed.returncode == 0, confirmed.stderr

    waited = _run_cli(
        [
            "wait-confirmation",
            "--run-dir",
            str(run_dir),
            "--checkpoint",
            "sql_review",
            "--allow-existing",
            "--timeout-seconds",
            "0.1",
            "--poll-interval-seconds",
            "0.01",
        ],
        cwd=Path.cwd(),
    )

    assert waited.returncode == 0, waited.stderr
    payload = json.loads(waited.stdout)
    assert payload["status"] == "confirmed"
    assert payload["checkpoint"] == "sql_review"
    assert payload["action"] == "調整需求"
    assert payload["comment"] == "請加入期預算比較"
    assert payload["selectedOptions"] == {"chart": "bar"}


def test_cli_wait_confirmation_times_out_when_user_has_not_confirmed(tmp_path: Path):
    run_root = tmp_path / "runs"
    run_dir = run_root / "run-wait-timeout"

    created = _run_cli(
        [
            "create-run",
            "--run-root",
            str(run_root),
            "--run-id",
            "run-wait-timeout",
            "--prompt",
            "查詢費用分析",
        ],
        cwd=Path.cwd(),
    )
    assert created.returncode == 0, created.stderr

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

    waited = _run_cli(
        [
            "wait-confirmation",
            "--run-dir",
            str(run_dir),
            "--checkpoint",
            "sql_review",
            "--timeout-seconds",
            "0.05",
            "--poll-interval-seconds",
            "0.01",
        ],
        cwd=Path.cwd(),
    )

    assert waited.returncode == 2
    error = json.loads(waited.stderr)
    assert error["code"] == "confirmation_timeout"
    assert error["checkpoint"] == "sql_review"


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


def test_cli_sqlite_enrichment_flow_writes_raw_and_enriched_checkpoints(tmp_path: Path):
    run_root = tmp_path / "runs"
    run_dir = run_root / "run-sqlite"
    workbook = tmp_path / "req.xlsx"
    _classification_workbook(workbook)

    created = _run_cli(
        [
            "create-run",
            "--run-root",
            str(run_root),
            "--run-id",
            "run-sqlite",
            "--prompt",
            "費用分析",
            "--input-file",
            str(workbook),
        ],
        cwd=Path.cwd(),
    )
    assert created.returncode == 0, created.stderr

    classified = _run_cli(
        [
            "classify-workbook",
            "--run-dir",
            str(run_dir),
            "--input-file",
            str(workbook),
            "--primary-sheet",
            "明細帳",
        ],
        cwd=Path.cwd(),
    )
    assert classified.returncode == 0, classified.stderr
    assert json.loads(classified.stdout)["checkpoint"] == "field_formula_classification"

    initialized = _run_cli(["init-sqlite-workspace", "--run-dir", str(run_dir)], cwd=Path.cwd())
    assert initialized.returncode == 0, initialized.stderr
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert Path(state["sqlite_manifest_path"]).exists()

    imported = _run_cli(
        [
            "import-lookups",
            "--run-dir",
            str(run_dir),
            "--input-file",
            str(workbook),
            "--sheet-name",
            "對照表",
            "--logical-name",
            "lookup_account_category",
            "--key-column",
            "A",
            "--value-column",
            "bu=B",
            "--value-column",
            "expense_category=C",
        ],
        cwd=Path.cwd(),
    )
    assert imported.returncode == 0, imported.stderr
    imported_payload = json.loads(imported.stdout)
    assert imported_payload["imported_row_count"] == 1
    assert imported_payload["ignored_row_count"] == 5
    lookup_table = imported_payload["table_name"]
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert state["sqlite_manifest"]["lookup_row_counts"] == {lookup_table: 1}
    assert state["sqlite_manifest"]["ignored_lookup_rows"][lookup_table][0]["reason"] == "header_or_metadata"

    raw_rows = tmp_path / "raw-rows.json"
    raw_rows.write_text('[{"account_code":"6111","amount":100}]', encoding="utf-8")
    raw = _run_cli(["write-raw-table", "--run-dir", str(run_dir), "--rows", str(raw_rows)], cwd=Path.cwd())
    assert raw.returncode == 0, raw.stderr

    raw_preview = _run_cli(["write-raw-preview", "--run-dir", str(run_dir)], cwd=Path.cwd())
    assert raw_preview.returncode == 0, raw_preview.stderr
    raw_payload = json.loads(raw_preview.stdout)
    assert raw_payload["checkpoint"] == "raw_data_preview"
    assert raw_payload["payload"]["row_count"] == 1
    assert raw_payload["payload"]["columns"] == ["account_code", "amount"]

    enriched = _run_cli(
        [
            "run-sqlite-enrichment",
            "--run-dir",
            str(run_dir),
            "--computed-columns",
            '[{"name":"amount_twice","expression":"raw.\\"amount\\" * 2"}]',
            "--lookup-columns",
            (
                '[{"name":"expense_category","lookup_table":"'
                + lookup_table
                + '","raw_key":"account_code","lookup_key":"account_code","lookup_value":"expense_category"}]'
            ),
        ],
        cwd=Path.cwd(),
    )
    assert enriched.returncode == 0, enriched.stderr

    enriched_preview = _run_cli(["write-enriched-preview", "--run-dir", str(run_dir)], cwd=Path.cwd())
    assert enriched_preview.returncode == 0, enriched_preview.stderr
    enriched_payload = json.loads(enriched_preview.stdout)
    assert enriched_payload["checkpoint"] == "enriched_data_preview"
    assert enriched_payload["payload"]["sample_rows"] == [
        {
            "account_code": "6111",
            "amount": 100,
            "expense_category": "8.租金支出",
            "amount_twice": 200,
        }
    ]

    retention = _run_cli(["write-sqlite-retention", "--run-dir", str(run_dir)], cwd=Path.cwd())
    assert retention.returncode == 0, retention.stderr
    retention_payload = json.loads(retention.stdout)
    assert retention_payload["checkpoint"] == "sqlite_retention"
    table_names = {item["table_name"] for item in retention_payload["payload"]["tables"]}
    assert lookup_table in table_names


def test_harness_sql_review_clears_sqlite_preview_checkpoints(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-state", prompt="費用分析")
    harness.write_sql_review("SELECT old", {"status": "pending_user_confirmation"})
    harness.write_raw_data_preview({"row_count": 1, "columns": ["account_code"], "sample_rows": []})
    harness.write_enriched_data_preview({"row_count": 1, "columns": ["account_code"], "sample_rows": []})
    harness.write_sqlite_retention({"manifest_path": "/tmp/manifest.json", "tables": []})

    harness.write_sql_review("SELECT new", {"status": "pending_user_confirmation"})
    state = harness.state()
    checkpoints = {item["checkpoint"] for item in state["checkpoints"]}

    assert "raw_data_preview" not in checkpoints
    assert "enriched_data_preview" not in checkpoints
    assert "sqlite_retention" not in checkpoints
    assert state["raw_data_preview"] is None
    assert state["enriched_data_preview"] is None
    assert state["sqlite_retention"] is None


def test_harness_raw_preview_clears_enriched_and_report_downstream(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-state", prompt="費用分析")
    harness.write_raw_data_preview({"row_count": 1, "columns": ["account_code"], "sample_rows": []})
    harness.write_enriched_data_preview({"row_count": 1, "columns": ["account_code"], "sample_rows": []})
    harness.write_sqlite_retention({"manifest_path": "/tmp/manifest.json", "tables": []})
    harness.write_report_selection({"selected_report_type": "expense-analysis", "selected_options": {}})
    harness.confirm("report_selection", "產生報告")

    harness.write_raw_data_preview({"row_count": 2, "columns": ["account_code"], "sample_rows": []})
    state = harness.state()
    checkpoints = {item["checkpoint"] for item in state["checkpoints"]}

    assert "enriched_data_preview" not in checkpoints
    assert "sqlite_retention" not in checkpoints
    assert "report_selection" not in checkpoints
    assert "report_selection" not in state.get("user_confirmations", {})
    assert state["enriched_data_preview"] is None
    assert state["sqlite_retention"] is None
    assert state["report_options"] == {}

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from skill_scripts.validator_contracts import REQUIRED_VALIDATORS
from tests.skill_scripts.test_excel_intake import _write_requirement_workbook


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
    assert (run_dir / "checkpoints" / "05_report_draft.json").exists()
    assert (run_dir / "checkpoints" / "06_final_review.json").exists()

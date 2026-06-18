from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

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

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skill_scripts.report_harness_state import (
    CHECKPOINT_DEFINITIONS,
    create_report_run,
    load_run_state,
    record_checkpoint,
)


def test_creates_run_directory_with_state_json(tmp_path: Path):
    state = create_report_run(
        tmp_path,
        run_id="demo-run",
        prompt="請產出費用分析",
        input_files=["需求.xlsx"],
    )

    run_dir = tmp_path / "demo-run"
    assert run_dir.is_dir()
    assert (run_dir / "state.json").is_file()
    for child in ["inputs", "sql", "data", "checkpoints", "reports"]:
        assert (run_dir / child).is_dir()

    persisted = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert persisted["run_id"] == "demo-run"
    assert persisted["prompt"] == "請產出費用分析"
    assert persisted["input_files"] == ["需求.xlsx"]
    assert state["user_confirmations"] == {}


def test_create_report_run_rejects_existing_run_id(tmp_path: Path):
    create_report_run(tmp_path, run_id="demo-run", prompt="first")

    with pytest.raises(FileExistsError, match="demo-run"):
        create_report_run(tmp_path, run_id="demo-run", prompt="second")


def test_records_excel_confirmation_checkpoint(tmp_path: Path):
    create_report_run(tmp_path, run_id="demo-run", prompt="prompt")

    checkpoint = record_checkpoint(
        tmp_path / "demo-run",
        "excel_confirmation",
        {"資料庫欄位": [{"顯示名稱": "未稅金額"}]},
    )

    path = tmp_path / "demo-run" / "checkpoints" / "01_excel_confirmation.json"
    assert path.is_file()
    assert checkpoint["title"] == "確認欄位與公式"
    assert checkpoint["actions"] == ["確認欄位與公式", "要求修正"]


def test_records_sql_review_checkpoint(tmp_path: Path):
    create_report_run(tmp_path, run_id="demo-run", prompt="prompt")

    checkpoint = record_checkpoint(
        tmp_path / "demo-run",
        "sql_review",
        {"sql": "SELECT * FROM ACPTA"},
    )

    assert checkpoint["title"] == "SQL 查詢確認"
    assert checkpoint["actions"] == ["同意查詢", "調整需求"]


def test_records_data_preview_checkpoint(tmp_path: Path):
    create_report_run(tmp_path, run_id="demo-run", prompt="prompt")

    checkpoint = record_checkpoint(
        tmp_path / "demo-run",
        "data_preview",
        {"row_count": 3, "columns": ["部門", "總額"]},
    )

    assert checkpoint["title"] == "資料預覽確認"
    assert checkpoint["actions"] == ["資料正確", "重新查詢"]


def test_records_report_selection_checkpoint(tmp_path: Path):
    create_report_run(tmp_path, run_id="demo-run", prompt="prompt")

    checkpoint = record_checkpoint(
        tmp_path / "demo-run",
        "report_selection",
        {"report_types": ["管理摘要"]},
    )

    assert checkpoint["title"] == "報表格式選擇"
    assert checkpoint["actions"] == ["產生報告", "修改格式"]


def test_all_checkpoint_payloads_have_chinese_titles_and_actions():
    expected_actions = {
        "excel_confirmation": ["確認欄位與公式", "要求修正"],
        "sql_review": ["同意查詢", "調整需求"],
        "data_preview": ["資料正確", "重新查詢"],
        "report_selection": ["產生報告", "修改格式"],
        "report_draft": ["接受", "修正報告"],
        "final_review": ["完成", "回到初稿"],
    }

    assert set(CHECKPOINT_DEFINITIONS) == set(expected_actions)
    for key, actions in expected_actions.items():
        definition = CHECKPOINT_DEFINITIONS[key]
        assert definition["title"]
        assert definition["actions"] == actions
        assert all(any("\u4e00" <= character <= "\u9fff" for character in action) for action in actions)


def test_load_run_state_round_trips_persisted_state(tmp_path: Path):
    create_report_run(tmp_path, run_id="demo-run", prompt="prompt")
    record_checkpoint(tmp_path / "demo-run", "excel_confirmation", {"ok": True})

    state = load_run_state(tmp_path / "demo-run")

    assert state["run_id"] == "demo-run"
    assert state["checkpoints"][-1]["checkpoint"] == "excel_confirmation"


def test_repeated_checkpoint_replaces_history_entry(tmp_path: Path):
    create_report_run(tmp_path, run_id="demo-run", prompt="prompt")
    record_checkpoint(tmp_path / "demo-run", "sql_review", {"sql": "SELECT 1"})
    record_checkpoint(tmp_path / "demo-run", "sql_review", {"sql": "SELECT 2"})

    state = load_run_state(tmp_path / "demo-run")

    assert [item["checkpoint"] for item in state["checkpoints"]] == ["sql_review"]
    checkpoint = json.loads(
        (tmp_path / "demo-run" / "checkpoints" / "02_sql_review.json").read_text(encoding="utf-8")
    )
    assert checkpoint["payload"]["sql"] == "SELECT 2"

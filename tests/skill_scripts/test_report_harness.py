from __future__ import annotations

from pathlib import Path

import pytest

from skill_scripts.report_harness import ReportHarness, ReportHarnessError


def test_rejects_state_transition_without_required_confirmation(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="demo-run", prompt="請查詢費用")
    harness.write_sql_review("SELECT * FROM ACPTA")

    with pytest.raises(ReportHarnessError, match="SQL must be confirmed"):
        harness.write_data_preview({"rows": [], "row_count": 0})


def test_confirmed_sql_allows_data_preview_checkpoint(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="demo-run", prompt="請查詢費用")
    harness.write_sql_review("SELECT * FROM ACPTA")
    harness.confirm("sql_review", "同意查詢")

    checkpoint = harness.write_data_preview({"rows": [{"部門": "D001"}], "row_count": 1})

    assert checkpoint["checkpoint"] == "data_preview"
    assert checkpoint["payload"]["row_count"] == 1


def test_rewriting_sql_review_requires_reconfirmation(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="demo-run", prompt="請查詢費用")
    harness.write_sql_review("SELECT 1")
    harness.confirm("sql_review", "同意查詢")
    harness.write_sql_review("SELECT 2")

    with pytest.raises(ReportHarnessError, match="SQL must be confirmed"):
        harness.write_data_preview({"rows": [], "row_count": 0})


def test_rewriting_sql_review_clears_downstream_state_and_checkpoints(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="demo-run", prompt="請查詢費用")
    harness.write_sql_review("SELECT 1")
    harness.confirm("sql_review", "同意查詢")
    harness.write_data_preview({"rows": [{"部門": "D001"}], "row_count": 1})
    harness.write_report_selection(
        {
            "selected_report_type": "管理摘要",
            "selected_report_design": "financial-control",
            "selected_options": {"include_table": True},
        }
    )

    harness.write_sql_review("SELECT 2")

    state = harness.state()
    assert state["execution_result_summary"] is None
    assert state["report_type"] is None
    assert state["report_design"] is None
    assert state["report_options"] == {}
    assert [checkpoint["checkpoint"] for checkpoint in state["checkpoints"]] == ["sql_review"]
    assert not (harness.run_dir / "checkpoints" / "03_data_preview.json").exists()
    assert not (harness.run_dir / "checkpoints" / "04_report_selection.json").exists()


def test_confirm_requires_existing_checkpoint_and_valid_action(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="demo-run", prompt="請查詢費用")

    with pytest.raises(ReportHarnessError, match="checkpoint has not been created"):
        harness.confirm("sql_review", "同意查詢")

    harness.write_sql_review("SELECT * FROM ACPTA")

    with pytest.raises(ReportHarnessError, match="Invalid checkpoint action"):
        harness.confirm("sql_review", "直接執行")


def test_report_draft_requires_report_selection_confirmation(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="demo-run", prompt="請查詢費用")
    harness.write_report_selection({"report_types": ["管理摘要"]})

    with pytest.raises(ReportHarnessError, match="Report selection must be confirmed"):
        harness.write_report_draft({"sections": []})


def test_report_selection_updates_canonical_state_fields(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="demo-run", prompt="請查詢費用")

    harness.write_report_selection(
        {
            "selected_report_type": "管理摘要",
            "selected_report_design": "financial-control",
            "selected_options": {
                "include_chart": True,
                "include_table": True,
                "include_analysis": True,
                "include_recommendations": False,
            },
        }
    )

    state = harness.state()
    assert state["report_type"] == "管理摘要"
    assert state["report_design"] == "financial-control"
    assert state["report_options"]["include_chart"] is True


def test_final_review_requires_draft_acceptance(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="demo-run", prompt="請查詢費用")
    harness.write_report_selection({"report_types": ["管理摘要"]})
    harness.confirm("report_selection", "產生報告")
    harness.write_report_draft({"sections": ["摘要"]})

    with pytest.raises(ReportHarnessError, match="Draft must be accepted"):
        harness.write_final_review({"status": "ready"})

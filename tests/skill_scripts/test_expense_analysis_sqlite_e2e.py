from __future__ import annotations

from tests.skill_scripts import expense_report_fixture
from tests.skill_scripts.expense_report_fixture import EXPECTED_COLUMNS


def test_expense_analysis_sqlite_e2e_quantitative_acceptance(tmp_path):
    runner = getattr(expense_report_fixture, "run_expense_analysis_sqlite_e2e", None)

    assert callable(runner)

    result = runner(tmp_path)

    assert result["row_count"] == 6
    assert result["columns"] == EXPECTED_COLUMNS
    assert result["aggregates"]["total_amount"] == 120000
    assert result["aggregates"]["total_budget"] == 100000
    assert result["aggregates"]["variance_amount"] == 20000
    assert result["aggregates"]["max_expense_ratio"] == 0.35
    assert result["excluded_rows"]["non_2026"] == 1
    assert result["excluded_rows"]["non_expense_account"] == 1
    assert result["sql_safety"]["readonly"] is True
    assert result["sql_safety"]["blocked_keywords"] == []
    assert result["sqlite_manifest"]["raw_row_count"] >= 1
    assert result["sqlite_manifest"]["enriched_row_count"] == result["sqlite_manifest"]["raw_row_count"]
    assert result["ignored_lookup_rows"] >= 0
    assert result["sqlite_manifest"]["cleanup_status"] == "active"

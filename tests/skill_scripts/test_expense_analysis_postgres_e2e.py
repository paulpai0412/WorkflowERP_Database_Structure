from __future__ import annotations

import os

import pytest

from tests.skill_scripts.expense_report_fixture import EXPECTED_COLUMNS, run_expense_analysis_postgres_e2e


pytestmark = pytest.mark.skipif(
    os.getenv("WFERP_RUN_POSTGRES_E2E") != "1",
    reason="set WFERP_RUN_POSTGRES_E2E=1 and start the Docker PostgreSQL fixture to run this test",
)


def test_expense_analysis_postgres_e2e_quantitative_acceptance():
    result = run_expense_analysis_postgres_e2e(
        os.getenv("WFERP_POSTGRES_E2E_CONTAINER", "wferp-postgres-e2e")
    )

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

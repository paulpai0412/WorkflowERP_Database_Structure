import csv
from decimal import Decimal
import os
import subprocess

import pytest

from skill_scripts.postgres_readonly_adapter import translate_sqlserver_select_to_postgres
from tests.skill_scripts.expense_report_fixture import expense_report_sql


PROMPT = "請產出2026第一季費用分析，依部門與會計科目彙總未稅金額、稅額、總額與占比"
EXPECTED_COLUMNS = {
    "expense_department",
    "expense_account",
    "untaxed_amount",
    "tax_amount",
    "total_amount",
    "total_amount_pct",
}
BLOCKED_KEYWORDS = ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "EXEC", "MERGE", "TRUNCATE")


pytestmark = pytest.mark.skipif(
    os.getenv("WFERP_RUN_POSTGRES_E2E") != "1",
    reason="set WFERP_RUN_POSTGRES_E2E=1 and start the PostgreSQL fixture to run this test",
)


def _generated_sql() -> str:
    return expense_report_sql("_Source")


def _execute_postgres(sql: str) -> list[dict[str, str]]:
    container = os.getenv("WFERP_POSTGRES_E2E_CONTAINER", "wferp-postgres-e2e")
    completed = subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            container,
            "psql",
            "-U",
            "wferp",
            "-d",
            "wferp_e2e",
            "--csv",
            "-P",
            "footer=off",
            "-c",
            sql,
        ],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return list(csv.DictReader(completed.stdout.splitlines()))


@pytest.fixture(scope="module")
def expense_rows():
    sql = _generated_sql()
    translated = translate_sqlserver_select_to_postgres(sql)
    return _execute_postgres(translated)


def _decimal(value: str) -> Decimal:
    return Decimal(str(value))


def _decimal_sum(rows: list[dict[str, str]], column: str) -> Decimal:
    return sum((_decimal(row[column]) for row in rows), Decimal("0.00"))


def test_expense_analysis_query_executes_against_postgres_fixture(expense_rows):
    assert len(expense_rows) == 6


def test_expense_analysis_rows_columns_and_totals_match_fixture(expense_rows):
    assert set(expense_rows[0].keys()) == EXPECTED_COLUMNS
    assert _decimal_sum(expense_rows, "untaxed_amount") == Decimal("130000.00")
    assert _decimal_sum(expense_rows, "tax_amount") == Decimal("6500.00")
    assert _decimal_sum(expense_rows, "total_amount") == Decimal("136500.00")


def test_expense_analysis_excluded_rows_are_not_counted(expense_rows):
    totals = {_decimal(row["total_amount"]) for row in expense_rows}

    assert Decimal("999999.00") not in totals
    assert Decimal("7777.00") not in totals
    assert Decimal("8888.00") not in totals
    assert _decimal_sum(expense_rows, "total_amount") == Decimal("136500.00")


def test_expense_analysis_percentage_sum_is_approximately_100(expense_rows):
    pct_sum = _decimal_sum(expense_rows, "total_amount_pct")

    assert abs(pct_sum - Decimal("100.0000")) <= Decimal("0.0001")


def test_expense_analysis_query_contains_no_blocked_sql():
    sql = _generated_sql()
    sql_upper = sql.upper()

    assert sql.lstrip().upper().startswith("SELECT")
    assert "[VPIC1].[dbo].[ACPTA]" in sql
    assert "[VPIC1].[dbo].[ACPTB]" in sql
    assert "detail.[TB014] AS expense_department" in sql
    assert "SUM(detail.[TB017] + detail.[TB018]) AS total_amount" in sql
    assert ";" not in sql.rstrip(";")
    assert "--" not in sql
    assert "/*" not in sql
    assert "*/" not in sql
    for keyword in BLOCKED_KEYWORDS:
        assert keyword not in sql_upper


def test_expense_analysis_top_row_is_d002_6201(expense_rows):
    top_row = expense_rows[0]

    assert top_row["expense_department"] == "D002"
    assert top_row["expense_account"] == "6201"
    assert _decimal(top_row["total_amount"]) == Decimal("37800.00")

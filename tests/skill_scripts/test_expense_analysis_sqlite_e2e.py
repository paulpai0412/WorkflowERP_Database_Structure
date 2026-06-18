from decimal import Decimal
import os
import sqlite3

import pytest

from skill_scripts.sqlite_readonly_adapter import translate_sqlserver_select_to_sqlite
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
    os.getenv("WFERP_RUN_SQLITE_E2E") != "1",
    reason="set WFERP_RUN_SQLITE_E2E=1 to run the local SQLite expense E2E test",
)


def _generated_sql() -> str:
    return expense_report_sql("_Source")


def _seed_sqlite(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP TABLE IF EXISTS "ACPTB";
        DROP TABLE IF EXISTS "ACPTA";
        CREATE TABLE "ACPTA" (
            "TA001" text NOT NULL,
            "TA002" text NOT NULL,
            "TA003" text NOT NULL,
            "TA018" text,
            "TA024" text NOT NULL,
            PRIMARY KEY ("TA001", "TA002")
        );
        CREATE TABLE "ACPTB" (
            "TB001" text NOT NULL,
            "TB002" text NOT NULL,
            "TB003" text NOT NULL,
            "TB013" text NOT NULL,
            "TB014" text NOT NULL,
            "TB017" numeric NOT NULL,
            "TB018" numeric NOT NULL,
            PRIMARY KEY ("TB001", "TB002", "TB003")
        );
        """
    )
    conn.executemany(
        'INSERT INTO "ACPTA" ("TA001", "TA002", "TA003", "TA018", "TA024") VALUES (?, ?, ?, ?, ?)',
        [
            ("E1", "202601-001", "20260110", None, "Y"),
            ("E1", "202601-002", "20260120", "", "Y"),
            ("E1", "202602-001", "20260205", None, "Y"),
            ("E1", "202602-002", "20260218", "", "Y"),
            ("E1", "202603-001", "20260308", None, "Y"),
            ("E1", "202603-002", "20260322", "", "Y"),
            ("E1", "202512-999", "20251231", None, "Y"),
            ("E1", "202601-777", "20260115", None, "N"),
            ("E1", "202601-888", "20260118", "Y", "Y"),
        ],
    )
    conn.executemany(
        'INSERT INTO "ACPTB" ("TB001", "TB002", "TB003", "TB013", "TB014", "TB017", "TB018") VALUES (?, ?, ?, ?, ?, ?, ?)',
        [
            ("E1", "202601-001", "0001", "6101", "D001", "12000.00", "600.00"),
            ("E1", "202601-001", "0002", "6101", "D001", "10000.00", "500.00"),
            ("E1", "202601-002", "0001", "6201", "D001", "8000.00", "400.00"),
            ("E1", "202601-002", "0002", "6201", "D001", "7000.00", "350.00"),
            ("E1", "202602-001", "0001", "6101", "D002", "14000.00", "700.00"),
            ("E1", "202602-001", "0002", "6101", "D002", "10000.00", "500.00"),
            ("E1", "202602-002", "0001", "6201", "D002", "20000.00", "1000.00"),
            ("E1", "202602-002", "0002", "6201", "D002", "16000.00", "800.00"),
            ("E1", "202603-001", "0001", "6101", "D003", "15000.00", "750.00"),
            ("E1", "202603-001", "0002", "6101", "D003", "9000.00", "450.00"),
            ("E1", "202603-002", "0001", "6201", "D003", "5000.00", "250.00"),
            ("E1", "202603-002", "0002", "6201", "D003", "4000.00", "200.00"),
            ("E1", "202512-999", "0001", "9999", "D999", "999999.00", "0.00"),
            ("E1", "202601-777", "0001", "7777", "D777", "7777.00", "0.00"),
            ("E1", "202601-888", "0001", "8888", "D888", "8888.00", "0.00"),
        ],
    )
    conn.commit()


@pytest.fixture()
def expense_rows(tmp_path):
    db_path = tmp_path / "wferp_expense.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _seed_sqlite(conn)
    sql = translate_sqlserver_select_to_sqlite(_generated_sql())
    rows = [dict(row) for row in conn.execute(sql).fetchall()]
    conn.close()
    return rows


def _decimal(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.0001"))


def _decimal_sum(rows: list[dict], column: str) -> Decimal:
    return sum((_decimal(row[column]) for row in rows), Decimal("0.0000"))


def test_sqlite_expense_analysis_query_executes_first(expense_rows):
    assert len(expense_rows) == 6


def test_sqlite_expense_analysis_rows_columns_and_totals_match_fixture(expense_rows):
    assert set(expense_rows[0].keys()) == EXPECTED_COLUMNS
    assert _decimal_sum(expense_rows, "untaxed_amount") == Decimal("130000.0000")
    assert _decimal_sum(expense_rows, "tax_amount") == Decimal("6500.0000")
    assert _decimal_sum(expense_rows, "total_amount") == Decimal("136500.0000")


def test_sqlite_expense_analysis_excluded_rows_are_not_counted(expense_rows):
    totals = {_decimal(row["total_amount"]) for row in expense_rows}

    assert Decimal("999999.0000") not in totals
    assert Decimal("7777.0000") not in totals
    assert Decimal("8888.0000") not in totals
    assert _decimal_sum(expense_rows, "total_amount") == Decimal("136500.0000")


def test_sqlite_expense_analysis_percentage_sum_is_approximately_100(expense_rows):
    pct_sum = _decimal_sum(expense_rows, "total_amount_pct")

    assert abs(pct_sum - Decimal("100.0000")) <= Decimal("0.0001")


def test_sqlite_expense_analysis_top_row_is_d002_6201(expense_rows):
    top_row = expense_rows[0]

    assert top_row["expense_department"] == "D002"
    assert top_row["expense_account"] == "6201"
    assert _decimal(top_row["total_amount"]) == Decimal("37800.0000")


def test_sqlite_expense_analysis_query_contains_no_blocked_sql():
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

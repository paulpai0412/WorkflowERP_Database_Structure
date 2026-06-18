from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
import sqlite3
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from skill_scripts.postgres_readonly_adapter import translate_sqlserver_select_to_postgres
from skill_scripts.sqlite_readonly_adapter import translate_sqlserver_select_to_sqlite


TABLE_NAME = "EXPENSE_ANALYSIS_FIXTURE"
SQLSERVER_TABLE = f"[VPIC1].[dbo].[{TABLE_NAME}]"
EXPECTED_COLUMNS = [
    "department_code",
    "department_name",
    "expense_subject",
    "amount",
    "budget_amount",
    "variance_amount",
    "expense_ratio",
]
BLOCKED_KEYWORDS = ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "EXEC", "MERGE", "TRUNCATE")


@dataclass(frozen=True)
class ExpenseFixtureRow:
    year: int
    department_code: str
    department_name: str
    expense_subject: str
    amount: int
    budget_amount: int
    account_type: str


EXPENSE_FIXTURE_ROWS = [
    ExpenseFixtureRow(2026, "ADM", "行政部", "旅費", 35000, 30000, "expense"),
    ExpenseFixtureRow(2026, "ADM", "行政部", "文具", 10000, 8000, "expense"),
    ExpenseFixtureRow(2026, "RND", "研發部", "雲端服務", 30000, 25000, "expense"),
    ExpenseFixtureRow(2026, "RND", "研發部", "軟體訂閱", 25000, 22000, "expense"),
    ExpenseFixtureRow(2026, "SAL", "業務部", "交際費", 12000, 10000, "expense"),
    ExpenseFixtureRow(2026, "SAL", "業務部", "廣告費", 8000, 5000, "expense"),
    ExpenseFixtureRow(2025, "ADM", "行政部", "旅費", 9000, 9000, "expense"),
    ExpenseFixtureRow(2026, "ADM", "行政部", "資產購置", 50000, 50000, "asset"),
]


def expense_analysis_sql() -> str:
    return f"""
SELECT
    [department_code] AS department_code,
    [department_name] AS department_name,
    [expense_subject] AS expense_subject,
    [amount] AS amount,
    [budget_amount] AS budget_amount,
    [amount] - [budget_amount] AS variance_amount,
    CAST([amount] AS REAL) / NULLIF((
        SELECT SUM([budget_amount])
        FROM {SQLSERVER_TABLE}
        WHERE [year] = 2026 AND [account_type] = 'expense'
    ), 0) AS expense_ratio
FROM {SQLSERVER_TABLE}
WHERE [year] = 2026 AND [account_type] = 'expense'
ORDER BY [department_code], [expense_subject]
""".strip()


def create_sqlite_expense_fixture(conn: sqlite3.Connection) -> None:
    conn.executescript(
        f"""
        DROP TABLE IF EXISTS "{TABLE_NAME}";
        CREATE TABLE "{TABLE_NAME}" (
            "year" integer NOT NULL,
            "department_code" text NOT NULL,
            "department_name" text NOT NULL,
            "expense_subject" text NOT NULL,
            "amount" numeric NOT NULL,
            "budget_amount" numeric NOT NULL,
            "account_type" text NOT NULL
        );
        """
    )
    conn.executemany(
        f"""
        INSERT INTO "{TABLE_NAME}"
            ("year", "department_code", "department_name", "expense_subject", "amount", "budget_amount", "account_type")
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row.year,
                row.department_code,
                row.department_name,
                row.expense_subject,
                row.amount,
                row.budget_amount,
                row.account_type,
            )
            for row in EXPENSE_FIXTURE_ROWS
        ],
    )
    conn.commit()


def postgres_seed_sql() -> str:
    rows_sql = ",\n".join(
        "    "
        f"({row.year}, '{_sql_literal(row.department_code)}', '{_sql_literal(row.department_name)}', "
        f"'{_sql_literal(row.expense_subject)}', {row.amount}, {row.budget_amount}, '{_sql_literal(row.account_type)}')"
        for row in EXPENSE_FIXTURE_ROWS
    )
    return f"""
DROP SCHEMA IF EXISTS dbo CASCADE;
CREATE SCHEMA dbo;

CREATE TABLE dbo."{TABLE_NAME}" (
    "year" integer NOT NULL,
    "department_code" text NOT NULL,
    "department_name" text NOT NULL,
    "expense_subject" text NOT NULL,
    "amount" numeric(18, 2) NOT NULL,
    "budget_amount" numeric(18, 2) NOT NULL,
    "account_type" text NOT NULL
);

INSERT INTO dbo."{TABLE_NAME}"
    ("year", "department_code", "department_name", "expense_subject", "amount", "budget_amount", "account_type")
VALUES
{rows_sql};
""".strip()


def _sql_literal(value: str) -> str:
    return value.replace("'", "''")


def _sql_safety(sql: str) -> dict[str, Any]:
    upper = sql.upper()
    blocked = [keyword for keyword in BLOCKED_KEYWORDS if keyword in upper]
    readonly = sql.lstrip().upper().startswith("SELECT") and not blocked and ";" not in sql
    return {"readonly": readonly, "blocked_keywords": blocked}


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _to_number(value: Decimal) -> int | float:
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def _round_ratio(value: Any) -> float:
    return float(_decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _build_result(rows: list[dict[str, Any]], excluded_rows: dict[str, int], sql: str) -> dict[str, Any]:
    total_amount = sum((_decimal(row["amount"]) for row in rows), Decimal("0"))
    total_budget = sum((_decimal(row["budget_amount"]) for row in rows), Decimal("0"))
    variance_amount = sum((_decimal(row["variance_amount"]) for row in rows), Decimal("0"))
    max_expense_ratio = max((_round_ratio(row["expense_ratio"]) for row in rows), default=0.0)
    return {
        "row_count": len(rows),
        "columns": list(rows[0].keys()) if rows else [],
        "rows": rows,
        "aggregates": {
            "total_amount": _to_number(total_amount),
            "total_budget": _to_number(total_budget),
            "variance_amount": _to_number(variance_amount),
            "max_expense_ratio": max_expense_ratio,
        },
        "excluded_rows": excluded_rows,
        "sql_safety": _sql_safety(sql),
        "sql": sql,
    }


def run_expense_analysis_sqlite_e2e(tmp_path: Path) -> dict[str, Any]:
    db_path = tmp_path / "wferp_expense.sqlite3"
    sql = expense_analysis_sql()
    translated = translate_sqlserver_select_to_sqlite(sql)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        create_sqlite_expense_fixture(conn)
        rows = [dict(row) for row in conn.execute(translated).fetchall()]
        excluded_rows = {
            "non_2026": conn.execute(
                f'SELECT COUNT(*) FROM "{TABLE_NAME}" WHERE "year" <> 2026 AND "account_type" = ?',
                ("expense",),
            ).fetchone()[0],
            "non_expense_account": conn.execute(
                f'SELECT COUNT(*) FROM "{TABLE_NAME}" WHERE "year" = 2026 AND "account_type" <> ?',
                ("expense",),
            ).fetchone()[0],
        }
    finally:
        conn.close()
    return _build_result(rows, excluded_rows, sql)


def run_expense_analysis_postgres_e2e(container: str = "wferp-postgres-e2e") -> dict[str, Any]:
    sql = expense_analysis_sql()
    translated = translate_sqlserver_select_to_postgres(sql)
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
            translated,
        ],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    rows = list(csv.DictReader(completed.stdout.splitlines()))
    excluded_rows = _postgres_excluded_rows(container)
    return _build_result(rows, excluded_rows, sql)


def _postgres_excluded_rows(container: str) -> dict[str, int]:
    counts_sql = f"""
SELECT
    SUM(CASE WHEN "year" <> 2026 AND "account_type" = 'expense' THEN 1 ELSE 0 END) AS non_2026,
    SUM(CASE WHEN "year" = 2026 AND "account_type" <> 'expense' THEN 1 ELSE 0 END) AS non_expense_account
FROM dbo."{TABLE_NAME}"
""".strip()
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
            counts_sql,
        ],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    row = next(csv.DictReader(completed.stdout.splitlines()))
    return {
        "non_2026": int(row["non_2026"]),
        "non_expense_account": int(row["non_expense_account"]),
    }


def format_expense_e2e_pass_line(prefix: str, result: dict[str, Any]) -> str:
    aggregates = result["aggregates"]
    return (
        f"{prefix}=pass row_count={result['row_count']} "
        f"total_amount={aggregates['total_amount']} "
        f"total_budget={aggregates['total_budget']} "
        f"variance_amount={aggregates['variance_amount']} "
        f"max_expense_ratio={aggregates['max_expense_ratio']:.2f}"
    )


def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite-e2e", action="store_true")
    parser.add_argument("--postgres-seed-sql", action="store_true")
    parser.add_argument("--postgres-e2e", action="store_true")
    parser.add_argument("--container", default="wferp-postgres-e2e")
    args = parser.parse_args()

    if args.postgres_seed_sql:
        print(postgres_seed_sql())
        return
    if args.sqlite_e2e:
        with TemporaryDirectory() as tmp:
            result = run_expense_analysis_sqlite_e2e(Path(tmp))
        print(format_expense_e2e_pass_line("sqlite_expense_e2e", result))
        return
    if args.postgres_e2e:
        result = run_expense_analysis_postgres_e2e(args.container)
        print(format_expense_e2e_pass_line("postgres_expense_e2e", result))
        return
    print(expense_analysis_sql())


if __name__ == "__main__":
    _main()

from __future__ import annotations

import re
import sqlite3
from typing import Any

from skill_scripts.sqlite_workspace import SQLiteRunWorkspace


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _validate_lookup_table(workspace: SQLiteRunWorkspace, table_name: str) -> None:
    if table_name not in workspace.manifest().get("lookup_tables", []):
        raise ValueError(f"Lookup table is not registered in workspace manifest: {table_name}")


_IDENTIFIER_PATTERN = r'(?:raw\.)?"(?:[^"]|"")+"'
_NUMBER_PATTERN = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)'
_VALUE_PATTERN = rf'(?:{_IDENTIFIER_PATTERN}|{_NUMBER_PATTERN})'
_BINARY_EXPR_RE = re.compile(rf'\A\(?\s*{_VALUE_PATTERN}\s*[-*]\s*{_VALUE_PATTERN}\s*\)?\Z')
_SCALED_BINARY_EXPR_RE = re.compile(
    rf'\A{_NUMBER_PATTERN}\s*\*\s*\(\s*{_IDENTIFIER_PATTERN}\s*[-*]\s*{_IDENTIFIER_PATTERN}\s*\)\Z'
)
_SIMPLE_EXPR_RE = re.compile(rf'\A(?:{_VALUE_PATTERN})\Z')
_SUBSTR_EXPR_RE = re.compile(rf'\ASUBSTR\(\s*{_IDENTIFIER_PATTERN}\s*,\s*\d+\s*,\s*\d+\s*\)\Z', re.IGNORECASE)
_CASE_LEFT_EXPR_RE = re.compile(
    rf"\ACASE WHEN SUBSTR\(\s*{_IDENTIFIER_PATTERN}\s*,\s*1\s*,\s*\d+\s*\)\s*=\s*'[^']*'\s+"
    rf"THEN\s+'[^']*'\s+ELSE SUBSTR\(\s*{_IDENTIFIER_PATTERN}\s*,\s*1\s*,\s*\d+\s*\)\s+END\Z",
    re.IGNORECASE,
)


def _validate_computed_expression(expression: str) -> None:
    text = expression.strip()
    if not text:
        raise ValueError("Unsafe computed expression: expression cannot be empty")
    if (
        _SIMPLE_EXPR_RE.fullmatch(text)
        or _BINARY_EXPR_RE.fullmatch(text)
        or _SCALED_BINARY_EXPR_RE.fullmatch(text)
        or _SUBSTR_EXPR_RE.fullmatch(text)
        or _CASE_LEFT_EXPR_RE.fullmatch(text)
    ):
        return
    raise ValueError(f"Unsafe computed expression: {expression}")


def run_enrichment(
    workspace: SQLiteRunWorkspace,
    *,
    computed_columns: list[dict[str, str]],
    lookup_columns: list[dict[str, str]],
) -> dict[str, Any]:
    select_parts = ["raw.*"]
    joins: list[str] = []

    for index, lookup in enumerate(lookup_columns):
        lookup_table = lookup["lookup_table"]
        _validate_lookup_table(workspace, lookup_table)
        alias = f"lk{index}"
        joins.append(
            f"LEFT JOIN {_quote_identifier(lookup_table)} {alias} "
            f"ON {alias}.{_quote_identifier(lookup['lookup_key'])} = "
            f"raw.{_quote_identifier(lookup['raw_key'])}"
        )
        select_parts.append(
            f"{alias}.{_quote_identifier(lookup['lookup_value'])} AS {_quote_identifier(lookup['name'])}"
        )

    for column in computed_columns:
        expression = column["expression"]
        _validate_computed_expression(expression)
        select_parts.append(f"{expression} AS {_quote_identifier(column['name'])}")

    enrichment_sql = (
        f"CREATE TABLE {_quote_identifier(workspace.enriched_table)} AS "
        f"SELECT {', '.join(select_parts)} "
        f"FROM {_quote_identifier(workspace.raw_table)} raw"
    )
    if joins:
        enrichment_sql += " " + " ".join(joins)

    with sqlite3.connect(workspace.sqlite_db_path) as conn:
        conn.execute(f"DROP TABLE IF EXISTS {_quote_identifier(workspace.enriched_table)}")
        conn.execute(enrichment_sql)
        row_count = conn.execute(
            f"SELECT COUNT(*) FROM {_quote_identifier(workspace.enriched_table)}"
        ).fetchone()[0]

    manifest = workspace.manifest()
    manifest["enriched_row_count"] = row_count
    manifest["enrichment_sql"] = enrichment_sql
    workspace._write_manifest(manifest)

    return {
        "status": "enriched",
        "enriched_table": workspace.enriched_table,
        "enriched_row_count": row_count,
        "sql": enrichment_sql,
    }

from __future__ import annotations

import re
from typing import Any


_CELL_RE = re.compile(r"([A-Z]+)\d+$", re.IGNORECASE)
_SAFE_IDENTIFIER_RE = r'"(?:[^"]|"")+"'
_SAFE_MAPPED_SQL_RE = re.compile(
    rf"\s*(?:{_SAFE_IDENTIFIER_RE}|raw\.{_SAFE_IDENTIFIER_RE}|[+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*$"
)


def _unsupported(formula: str, function: str, *, strict: bool) -> dict[str, Any]:
    if strict:
        if function == "UNKNOWN":
            raise ValueError(f"Unsupported Excel formula: {formula}")
        raise ValueError(f"Unsupported Excel formula function: {function}")
    return {"status": "unsupported", "function": function, "formula": formula}


def _function_name(text: str) -> str:
    match = re.match(r"\s*([A-Z][A-Z0-9.]*)\s*\(", text, re.IGNORECASE)
    return match.group(1).upper() if match else "UNKNOWN"


def _sql_for_cell(cell_ref: str, column_map: dict[str, str]) -> str:
    match = _CELL_RE.fullmatch(cell_ref.strip())
    if not match:
        raise ValueError(f"Unsupported cell reference: {cell_ref}")

    column = match.group(1).upper()
    if column not in column_map:
        raise ValueError(f"No SQLite mapping for Excel column: {column}")

    mapped = column_map[column]
    if not _SAFE_MAPPED_SQL_RE.fullmatch(mapped):
        raise ValueError(f"Unsafe SQLite mapping for Excel column: {column}")
    return mapped.strip()


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def translate_formula(
    formula: str,
    column_map: dict[str, str],
    *,
    strict: bool = True,
) -> str | dict[str, Any]:
    text = formula.strip()
    if text.startswith("="):
        text = text[1:].strip()

    arithmetic = re.fullmatch(
        r"([A-Z]+\d+)\s*([-*])\s*([A-Z]+\d+)",
        text,
        re.IGNORECASE,
    )
    if arithmetic:
        left, operator, right = arithmetic.groups()
        return f"({_sql_for_cell(left, column_map)} {operator} {_sql_for_cell(right, column_map)})"

    mid = re.fullmatch(
        r"MID\(\s*([A-Z]+\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)",
        text,
        re.IGNORECASE,
    )
    if mid:
        cell, start, length = mid.groups()
        return f"SUBSTR({_sql_for_cell(cell, column_map)}, {start}, {length})"

    if_left = re.fullmatch(
        r'IF\(\s*LEFT\(\s*([A-Z]+\d+)\s*,\s*(\d+)\s*\)\s*=\s*"([^"]*)"\s*,\s*"([^"]*)"\s*,\s*LEFT\(\s*([A-Z]+\d+)\s*,\s*(\d+)\s*\)\s*\)',
        text,
        re.IGNORECASE,
    )
    if if_left:
        test_cell, test_len, expected, true_value, else_cell, else_len = if_left.groups()
        return (
            f"CASE WHEN SUBSTR({_sql_for_cell(test_cell, column_map)}, 1, {test_len}) = {_sql_string(expected)} "
            f"THEN {_sql_string(true_value)} ELSE SUBSTR({_sql_for_cell(else_cell, column_map)}, 1, {else_len}) END"
        )

    return _unsupported(formula, _function_name(text), strict=strict)

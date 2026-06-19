from __future__ import annotations

import pytest

from skill_scripts.formula_sqlite_translator import translate_formula


def test_translate_arithmetic_cell_formula_to_sqlite_expression():
    column_map = {
        "Q": '"original_debit"',
        "R": '"original_credit"',
        "AB": '"local_signed"',
        "AN": "4.5958",
    }

    assert translate_formula("=Q2-R2", column_map) == '("original_debit" - "original_credit")'
    assert translate_formula("=AN2*AB2", column_map) == '(4.5958 * "local_signed")'


def test_translate_mid_and_if_left_formula():
    column_map = {"F": '"voucher_no"', "A": '"account_code"'}

    assert translate_formula("=MID(F2,6,6)", column_map) == 'SUBSTR("voucher_no", 6, 6)'
    assert translate_formula('=IF(LEFT(A2,2)="57","57",LEFT(A2,1))', column_map) == (
        'CASE WHEN SUBSTR("account_code", 1, 2) = \'57\' THEN \'57\' '
        'ELSE SUBSTR("account_code", 1, 1) END'
    )


def test_translate_formula_allows_safe_raw_alias_qualified_identifiers():
    column_map = {"F": 'raw."voucher_no"', "A": 'raw."account_code"'}

    assert translate_formula("=MID(F2,6,6)", column_map) == 'SUBSTR(raw."voucher_no", 6, 6)'
    assert translate_formula('=IF(LEFT(A2,2)="57","57",LEFT(A2,1))', column_map) == (
        'CASE WHEN SUBSTR(raw."account_code", 1, 2) = \'57\' THEN \'57\' '
        'ELSE SUBSTR(raw."account_code", 1, 1) END'
    )


def test_unsupported_formula_returns_structured_error_when_not_strict():
    result = translate_formula("=INDIRECT(A2)", {"A": '"account_code"'}, strict=False)

    assert result == {
        "status": "unsupported",
        "function": "INDIRECT",
        "formula": "=INDIRECT(A2)",
    }


def test_unsupported_formula_raises_when_strict():
    with pytest.raises(ValueError, match="Unsupported Excel formula function: INDIRECT"):
        translate_formula("=INDIRECT(A2)", {"A": '"account_code"'})


def test_translate_formula_rejects_arbitrary_sql_payload():
    with pytest.raises(ValueError, match="Unsupported Excel formula"):
        translate_formula('="x"; DROP TABLE raw_ledger; --', {})

    result = translate_formula("=A2+1", {"A": '"account_code"'}, strict=False)

    assert result == {
        "status": "unsupported",
        "function": "UNKNOWN",
        "formula": "=A2+1",
    }


def test_translate_formula_rejects_unsafe_column_map_values():
    with pytest.raises(ValueError, match="Unsafe SQLite mapping"):
        translate_formula("=A2-B2", {"A": 'raw."amount"; DROP TABLE x; --', "B": '"credit"'})

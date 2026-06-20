from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from skill_scripts.formula_sqlite_translator import translate_formula
from skill_scripts.sqlite_enrichment import run_enrichment
from skill_scripts.sqlite_workspace import SQLiteRunWorkspace


def test_run_enrichment_creates_enriched_table_from_raw_and_lookup(tmp_path: Path):
    workspace = SQLiteRunWorkspace.create(tmp_path / "run-001", run_id="run-001")
    workspace.write_raw_rows(
        [
            {
                "account_code": "6111",
                "original_debit": 100.0,
                "original_credit": 0.0,
                "local_debit": 459.58,
                "local_credit": 0.0,
            },
            {
                "account_code": "6113",
                "original_debit": 0.0,
                "original_credit": 25.0,
                "local_debit": 0.0,
                "local_credit": 114.895,
            },
        ]
    )
    lookup_table = workspace.register_lookup_table(
        "lookup_account_category",
        [
            {"account_code": "6111", "expense_category": "8.租金支出"},
            {"account_code": "6113", "expense_category": "9001.旅費"},
        ],
    )

    result = run_enrichment(
        workspace,
        computed_columns=[
            {"name": "amount_original", "expression": '"original_debit" - "original_credit"'},
            {"name": "amount_local", "expression": '"local_debit" - "local_credit"'},
            {"name": "rate_2", "expression": "4.5958"},
            {"name": "amount_ntd", "expression": '4.5958 * ("local_debit" - "local_credit")'},
        ],
        lookup_columns=[
            {
                "name": "expense_category",
                "lookup_table": lookup_table,
                "raw_key": "account_code",
                "lookup_key": "account_code",
                "lookup_value": "expense_category",
            }
        ],
    )

    assert result["status"] == "enriched"
    assert result["enriched_table"] == workspace.enriched_table
    assert result["enriched_row_count"] == 2
    with sqlite3.connect(workspace.sqlite_db_path) as conn:
        rows = conn.execute(
            f'SELECT account_code, amount_original, expense_category FROM "{workspace.enriched_table}" ORDER BY account_code'
        ).fetchall()
    assert rows == [("6111", 100.0, "8.租金支出"), ("6113", -25.0, "9001.旅費")]


def test_run_enrichment_quotes_identifiers_and_updates_manifest(tmp_path: Path):
    workspace = SQLiteRunWorkspace.create(tmp_path / "run-quoted", run_id="run quoted")
    workspace.write_raw_rows(
        [
            {'account "code"': "6111", "original debit": 100.0},
            {'account "code"': "9999", "original debit": 50.0},
        ]
    )
    lookup_table = workspace.register_lookup_table(
        'lookup "category"',
        [{'account "code"': "6111", "expense category": "8.租金支出"}],
    )

    result = run_enrichment(
        workspace,
        computed_columns=[
            {"name": 'copied "amount"', "expression": 'raw."original debit"'},
        ],
        lookup_columns=[
            {
                "name": "expense category",
                "lookup_table": lookup_table,
                "raw_key": 'account "code"',
                "lookup_key": 'account "code"',
                "lookup_value": "expense category",
            }
        ],
    )

    with sqlite3.connect(workspace.sqlite_db_path) as conn:
        rows = conn.execute(
            (
                f'SELECT "account ""code""", "copied ""amount""", "expense category" '
                f'FROM "{workspace.enriched_table}" ORDER BY "account ""code"""'
            )
        ).fetchall()

    assert rows == [("6111", 100.0, "8.租金支出"), ("9999", 50.0, None)]
    manifest = workspace.manifest()
    assert manifest["enriched_row_count"] == 2
    assert manifest["enrichment_sql"] == result["sql"]
    assert 'LEFT JOIN "' in manifest["enrichment_sql"]
    assert '"account ""code"""' in manifest["enrichment_sql"]


def test_run_enrichment_rejects_unvalidated_computed_expression(tmp_path: Path):
    workspace = SQLiteRunWorkspace.create(tmp_path / "run-injection", run_id="run-injection")
    workspace.write_raw_rows([{"account_code": "6111", "amount": 100.0}])

    with pytest.raises(ValueError, match="Unsafe computed expression"):
        run_enrichment(
            workspace,
            computed_columns=[
                {"name": "bad", "expression": '"amount"; DROP TABLE raw_ledger; --'},
            ],
            lookup_columns=[],
        )

    for expression in [
        'raw."amount" + (SELECT count(*) FROM sqlite_master)',
        'raw."amount" + random()',
        '"amount" OR 1=1',
    ]:
        with pytest.raises(ValueError, match="Unsafe computed expression"):
            run_enrichment(
                workspace,
                computed_columns=[
                    {"name": "bad", "expression": expression},
                ],
                lookup_columns=[],
            )


def test_translated_formula_expression_works_with_lookup_join_without_ambiguous_columns(tmp_path: Path):
    workspace = SQLiteRunWorkspace.create(tmp_path / "run-formula-join", run_id="run-formula-join")
    workspace.write_raw_rows(
        [
            {"account_code": "570101", "voucher_no": "ABCDE123456Z"},
            {"account_code": "6111", "voucher_no": "FGHIJ654321Z"},
        ]
    )
    lookup_table = workspace.register_lookup_table(
        "lookup_account_category",
        [
            {"account_code": "570101", "expense_category": "57類"},
            {"account_code": "6111", "expense_category": "其他"},
        ],
    )

    voucher_segment = translate_formula("=MID(F2,6,6)", {"F": 'raw."voucher_no"'})
    account_group = translate_formula(
        '=IF(LEFT(A2,2)="57","57",LEFT(A2,1))',
        {"A": 'raw."account_code"'},
    )
    result = run_enrichment(
        workspace,
        computed_columns=[
            {"name": "voucher_segment", "expression": voucher_segment},
            {"name": "account_group", "expression": account_group},
        ],
        lookup_columns=[
            {
                "name": "expense_category",
                "lookup_table": lookup_table,
                "raw_key": "account_code",
                "lookup_key": "account_code",
                "lookup_value": "expense_category",
            }
        ],
    )

    assert result["enriched_row_count"] == 2
    with sqlite3.connect(workspace.sqlite_db_path) as conn:
        rows = conn.execute(
            (
                f'SELECT account_code, voucher_segment, account_group, expense_category '
                f'FROM "{workspace.enriched_table}" ORDER BY account_code'
            )
        ).fetchall()

    assert rows == [
        ("570101", "123456", "57", "57類"),
        ("6111", "654321", "6", "其他"),
    ]

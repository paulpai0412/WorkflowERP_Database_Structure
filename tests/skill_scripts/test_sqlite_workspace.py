from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from skill_scripts.sqlite_workspace import SQLiteRunWorkspace


REQUIRED_MANIFEST_KEYS = {
    "sqlite_db_path",
    "run_prefix",
    "raw_table",
    "lookup_tables",
    "enriched_table",
    "raw_row_count",
    "enriched_row_count",
    "lookup_row_counts",
    "ignored_lookup_rows",
    "cleanup_status",
    "retention_decision",
    "created_at",
    "residual_risks",
    "source_workbook",
    "source_workbook_hash",
    "formal_db_query_hash",
}


def _table_names(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        return {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }


def test_workspace_creates_unique_run_prefix_and_complete_manifest(tmp_path: Path):
    first = SQLiteRunWorkspace.create(tmp_path, run_id="run-001")
    second = SQLiteRunWorkspace.create(tmp_path, run_id="run-001")

    assert first.run_prefix != second.run_prefix
    assert first.raw_table.startswith(first.run_prefix)
    assert first.raw_table.endswith("_raw_ledger")
    assert first.enriched_table.startswith(first.run_prefix)
    assert first.enriched_table.endswith("_enriched_ledger")
    assert first.raw_table != first.enriched_table
    assert first.sqlite_db_path == tmp_path / "sqlite" / "wferp-report.sqlite3"
    assert first.manifest_path.exists()

    manifest = first.manifest()
    assert REQUIRED_MANIFEST_KEYS <= set(manifest)
    assert manifest["sqlite_db_path"] == str(first.sqlite_db_path)
    assert manifest["run_prefix"] == first.run_prefix
    assert manifest["raw_table"] == first.raw_table
    assert manifest["lookup_tables"] == []
    assert manifest["enriched_table"] == first.enriched_table
    assert manifest["raw_row_count"] == 0
    assert manifest["enriched_row_count"] == 0
    assert manifest["lookup_row_counts"] == {}
    assert manifest["ignored_lookup_rows"] == {}
    assert manifest["cleanup_status"] == "active"
    assert manifest["retention_decision"] == "keep"
    assert manifest["created_at"]
    assert manifest["residual_risks"] == []
    assert manifest["source_workbook"] is None
    assert manifest["source_workbook_hash"] is None
    assert manifest["formal_db_query_hash"] is None


def test_workspace_writes_raw_rows_to_sqlite_and_updates_manifest(tmp_path: Path):
    workspace = SQLiteRunWorkspace.create(tmp_path, run_id="run-001")

    workspace.write_raw_rows(
        [
            {"account_code": "6111", "amount": 100, "note": "租金"},
            {"account_code": "6113", "amount": 200.5, "note": "運費"},
        ]
    )

    with sqlite3.connect(workspace.sqlite_db_path) as conn:
        rows = conn.execute(
            f'SELECT account_code, amount, note FROM "{workspace.raw_table}" ORDER BY account_code'
        ).fetchall()
    assert rows == [("6111", 100, "租金"), ("6113", 200.5, "運費")]
    assert workspace.manifest()["raw_row_count"] == 2


def test_register_lookup_table_sanitizes_names_and_records_counts(tmp_path: Path):
    workspace = SQLiteRunWorkspace.create(tmp_path, run_id="run-001")

    lookup_table = workspace.register_lookup_table(
        'lookup account"; DROP TABLE unrelated_table; --',
        [{"account_code": "6111", "category": "租金"}],
    )

    assert lookup_table.startswith(workspace.run_prefix)
    assert lookup_table.endswith("_lookup_account_drop_table_unrelated_table")
    assert '"' not in lookup_table
    assert ";" not in lookup_table
    assert "--" not in lookup_table

    with sqlite3.connect(workspace.sqlite_db_path) as conn:
        rows = conn.execute(
            f'SELECT account_code, category FROM "{lookup_table}"'
        ).fetchall()
    assert rows == [("6111", "租金")]

    manifest = workspace.manifest()
    assert manifest["lookup_tables"] == [lookup_table]
    assert manifest["lookup_row_counts"] == {lookup_table: 1}
    assert manifest["ignored_lookup_rows"] == {}


def test_cleanup_run_tables_only_drops_manifest_tables(tmp_path: Path):
    workspace = SQLiteRunWorkspace.create(tmp_path, run_id="run-001")
    with sqlite3.connect(workspace.sqlite_db_path) as conn:
        conn.execute("CREATE TABLE unrelated_table(id INTEGER)")
        conn.execute("CREATE TABLE unrelated_lookup(id INTEGER)")
        conn.execute(f'CREATE TABLE "{workspace.enriched_table}"(id INTEGER)')

    workspace.write_raw_rows(
        [{"account_code": "6111", "amount": 100}, {"account_code": "6113", "amount": 200}]
    )
    lookup_table = workspace.register_lookup_table(
        "lookup_account", [{"account_code": "6111", "category": "租金"}]
    )
    workspace.cleanup_run_tables()

    names = _table_names(workspace.sqlite_db_path)
    assert "unrelated_table" in names
    assert "unrelated_lookup" in names
    assert workspace.raw_table not in names
    assert workspace.enriched_table not in names
    assert lookup_table not in names

    manifest = workspace.manifest()
    assert manifest["cleanup_status"] == "deleted"
    assert manifest["retention_decision"] == "delete"


def test_write_rows_rejects_empty_rows_without_creating_table(tmp_path: Path):
    workspace = SQLiteRunWorkspace.create(tmp_path, run_id="run-001")

    with pytest.raises(ValueError, match="without rows"):
        workspace.write_raw_rows([])

    assert workspace.raw_table not in _table_names(workspace.sqlite_db_path)
    assert workspace.manifest()["raw_row_count"] == 0


def test_write_raw_rows_preserves_columns_that_appear_after_first_row(tmp_path: Path):
    workspace = SQLiteRunWorkspace.create(tmp_path, run_id="run-001")

    workspace.write_raw_rows(
        [
            {"account_code": "6111"},
            {"account_code": "6113", "department_code": "D001"},
        ]
    )

    with sqlite3.connect(workspace.sqlite_db_path) as conn:
        columns = [
            row[1]
            for row in conn.execute(f'PRAGMA table_info("{workspace.raw_table}")').fetchall()
        ]
        rows = conn.execute(
            f'SELECT account_code, department_code FROM "{workspace.raw_table}" ORDER BY account_code'
        ).fetchall()

    assert columns == ["account_code", "department_code"]
    assert rows == [("6111", None), ("6113", "D001")]
    assert workspace.manifest()["raw_row_count"] == 2


def test_manifest_file_is_valid_utf8_json(tmp_path: Path):
    workspace = SQLiteRunWorkspace.create(tmp_path, run_id="報表 run")

    payload = json.loads(workspace.manifest_path.read_text(encoding="utf-8"))

    assert payload["run_prefix"].startswith("wferp_")
    assert "報表" not in payload["run_prefix"]

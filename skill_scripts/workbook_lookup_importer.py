from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from skill_scripts.excel_intake import _read_xlsx_sheets_with_metadata
from skill_scripts.sqlite_workspace import SQLiteRunWorkspace


META_KEYS = {"", "科目編號", "公司別", "加總 - 換算台幣", "本月匯率"}


def _cell_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _column_index(column: str) -> int:
    value = 0
    for char in column.strip().upper():
        if not "A" <= char <= "Z":
            raise ValueError(f"Invalid Excel column letter: {column}")
        value = value * 26 + (ord(char) - 64)
    if value == 0:
        raise ValueError("Excel column letter cannot be empty")
    return value - 1


def _row_value(row: list[str], index: int) -> str:
    return _cell_text(row[index] if index < len(row) else "")


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_manifest(workspace: SQLiteRunWorkspace, manifest: dict[str, Any]) -> None:
    workspace.manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def import_lookup_sheet(
    workbook_path: str | Path,
    workspace: SQLiteRunWorkspace,
    *,
    sheet_name: str,
    logical_name: str,
    key_column: str,
    value_columns: dict[str, str],
) -> dict[str, Any]:
    path = Path(workbook_path)
    sheets = _read_xlsx_sheets_with_metadata(path)
    if sheet_name not in sheets:
        raise ValueError(f"Workbook sheet not found: {sheet_name}")

    key_index = _column_index(key_column)
    value_indexes = {
        output_name: _column_index(column)
        for output_name, column in value_columns.items()
    }
    imported_rows: list[dict[str, Any]] = []
    ignored_rows: list[dict[str, Any]] = []

    for row_number, row in enumerate(sheets[sheet_name].rows, start=1):
        key = _row_value(row, key_index)
        if key in META_KEYS or key.startswith("加總"):
            ignored_rows.append(
                {
                    "row_number": row_number,
                    "key": key,
                    "reason": "header_or_metadata",
                }
            )
            continue

        record = {"account_code": key}
        for output_name, value_index in value_indexes.items():
            record[output_name] = _row_value(row, value_index)

        if not any(value for field, value in record.items() if field != "account_code"):
            ignored_rows.append(
                {
                    "row_number": row_number,
                    "key": key,
                    "reason": "blank_values",
                }
            )
            continue

        imported_rows.append(record)

    table_name = workspace.register_lookup_table(logical_name, imported_rows)
    manifest = workspace.manifest()
    ignored_lookup_rows = dict(manifest.get("ignored_lookup_rows", {}))
    ignored_lookup_rows[table_name] = ignored_rows
    manifest["ignored_lookup_rows"] = ignored_lookup_rows
    manifest["source_workbook"] = str(path)
    manifest["source_workbook_hash"] = _file_hash(path)
    _write_manifest(workspace, manifest)

    return {
        "table_name": table_name,
        "sheet_name": sheet_name,
        "imported_row_count": len(imported_rows),
        "ignored_row_count": len(ignored_rows),
        "ignored_rows": ignored_rows,
    }

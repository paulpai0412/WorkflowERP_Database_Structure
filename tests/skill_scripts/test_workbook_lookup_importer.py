from __future__ import annotations

import hashlib
import sqlite3
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from skill_scripts.sqlite_workspace import SQLiteRunWorkspace
from skill_scripts.workbook_lookup_importer import import_lookup_sheet


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _sheet_xml(rows: list[list[str | int | None]]) -> str:
    rendered_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row, start=1):
            cell_ref = f"{_column_name(column_index)}{row_index}"
            text = "" if value is None else str(value)
            cells.append(
                f'<c r="{cell_ref}" t="inlineStr"><is><t>{escape(text)}</t></is></c>'
            )
        rendered_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(rendered_rows)}</sheetData>'
        "</worksheet>"
    )


def _lookup_workbook(path: Path) -> None:
    sheets = [
        (
            "明細帳",
            [
                ["科目編號", "金額"],
                ["6111", 100],
            ],
        ),
        (
            "對照表",
            [
                ["科目編號", "費用類別", "費用類別 (群組)"],
                ["公司別", "AIS", "0"],
                ["本月匯率", "31.5", ""],
                ["6111", "8.租金支出", "8.租金支出"],
                ["6112", None, None],
                ["6113", "9001.旅費", "9001.旅費"],
                [None, None, None],
                ["加總 - 換算台幣", None, None],
                ["加總 6111", None, None],
            ],
        ),
    ]

    workbook_sheets = []
    rels = []
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            + "".join(
                f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                for index, _ in enumerate(sheets, start=1)
            )
            + "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>",
        )
        for index, (name, rows) in enumerate(sheets, start=1):
            workbook_sheets.append(
                f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>'
            )
            rels.append(
                f'<Relationship Id="rId{index}" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                f'Target="worksheets/sheet{index}.xml"/>'
            )
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _sheet_xml(rows))
        archive.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<sheets>{"".join(workbook_sheets)}</sheets>'
            "</workbook>",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'{"".join(rels)}'
            "</Relationships>",
        )


def test_import_lookup_sheet_ignores_headers_metadata_and_blank_values(tmp_path: Path):
    workbook = tmp_path / "lookup.xlsx"
    _lookup_workbook(workbook)
    workspace = SQLiteRunWorkspace.create(tmp_path / "run-001", run_id="run-001")

    result = import_lookup_sheet(
        workbook,
        workspace,
        sheet_name="對照表",
        logical_name="lookup_account_category",
        key_column="A",
        value_columns={"expense_category": "B", "expense_group": "C"},
    )

    assert result["imported_row_count"] == 2
    assert result["ignored_row_count"] == 7
    assert [row["reason"] for row in result["ignored_rows"]].count("blank_values") == 1
    assert result["ignored_rows"][0] == {
        "row_number": 1,
        "key": "科目編號",
        "reason": "header_or_metadata",
    }

    with sqlite3.connect(workspace.sqlite_db_path) as conn:
        rows = conn.execute(
            f'SELECT account_code, expense_category, expense_group FROM "{result["table_name"]}" ORDER BY account_code'
        ).fetchall()
    assert rows == [
        ("6111", "8.租金支出", "8.租金支出"),
        ("6113", "9001.旅費", "9001.旅費"),
    ]

    manifest = workspace.manifest()
    assert manifest["lookup_tables"] == [result["table_name"]]
    assert manifest["lookup_row_counts"] == {result["table_name"]: 2}
    assert manifest["ignored_lookup_rows"][result["table_name"]] == result["ignored_rows"]
    assert manifest["source_workbook"] == str(workbook)
    assert manifest["source_workbook_hash"] == hashlib.sha256(workbook.read_bytes()).hexdigest()
    assert manifest["raw_table"] == workspace.raw_table
    assert manifest["formal_db_query_hash"] is None

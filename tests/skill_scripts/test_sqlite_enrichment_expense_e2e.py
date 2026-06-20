from __future__ import annotations

import sqlite3
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape
import json

from skill_scripts.formula_sqlite_translator import translate_formula
from skill_scripts.llm_workbook_classifier import classify_workbook_with_llm
from skill_scripts.sqlite_enrichment import run_enrichment
from skill_scripts.sqlite_workspace import SQLiteRunWorkspace
from skill_scripts.workbook_lookup_importer import import_lookup_sheet


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _sheet_xml(rows: list[list[str | int | tuple[str, str]]]) -> str:
    rendered_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row, start=1):
            cell_ref = f"{_column_name(column_index)}{row_index}"
            if isinstance(value, tuple) and value[0] == "formula":
                cells.append(f'<c r="{cell_ref}"><f>{escape(value[1].lstrip("="))}</f><v></v></c>')
            else:
                cells.append(
                    f'<c r="{cell_ref}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'
                )
        rendered_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(rendered_rows)}</sheetData>'
        "</worksheet>"
    )


def _expense_workbook(path: Path) -> None:
    sheets = [
        (
            "明細帳",
            [
                [
                    "科目編號",
                    "科目名稱",
                    "部門代號",
                    "部門名稱",
                    "傳票日期",
                    "本幣借方金額",
                    "本幣貸方金額",
                    "金額-本幣",
                    "費用類別",
                ],
                [
                    "6111",
                    "租金支出",
                    "ADM",
                    "行政部",
                    "20260105",
                    1000,
                    0,
                    ("formula", "=F2-G2"),
                    ("formula", "=VLOOKUP(A2,對照表!A:B,2,0)"),
                ],
                [
                    "6113",
                    "旅費",
                    "RND",
                    "研發部",
                    "20260106",
                    300,
                    0,
                    ("formula", "=F3-G3"),
                    ("formula", "=VLOOKUP(A3,對照表!A:B,2,0)"),
                ],
            ],
        ),
        (
            "對照表",
            [
                ["科目編號", "費用類別"],
                ["公司別", "AIS"],
                ["科目編號", "費用類別"],
                ["6111", "8.租金支出"],
                ["6113", "9001.旅費"],
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


def test_expense_sqlite_enrichment_e2e_with_llm_classification_contract(tmp_path: Path, monkeypatch):
    workbook = tmp_path / "expense.xlsx"
    _expense_workbook(workbook)
    monkeypatch.setenv(
        "LLM_MOCK_RESPONSE",
        json.dumps(
            {
                "candidate_tables": [
                    {
                        "table_id": "ACTML",
                        "table_name": "分類帳檔",
                        "reason": "費用明細帳交易列最可能在分類帳檔",
                        "confidence": 0.9,
                    }
                ],
                "column_mappings": [
                    {
                        "excel_column": "A",
                        "excel_header": "科目編號",
                        "classification": "db_source_field",
                        "processing_location": "formal_db_sql",
                        "source_expression": "ACTML.ML006",
                        "fields": [{"table_id": "ACTML", "column_id": "ML006", "business_meaning": "明細科目編號"}],
                        "relationship_path": [],
                        "lookup_sheet": "",
                        "confidence": 0.9,
                        "reason": "LLM selected ACTML before mapping fields.",
                        "risks": [],
                    },
                    {
                        "excel_column": "C",
                        "excel_header": "部門代號",
                        "classification": "db_source_field",
                        "processing_location": "formal_db_sql",
                        "source_expression": "ACTML.ML010",
                        "fields": [{"table_id": "ACTML", "column_id": "ML010", "business_meaning": "部門"}],
                        "relationship_path": [],
                        "lookup_sheet": "",
                        "confidence": 0.9,
                        "reason": "LLM selected ACTML before mapping fields.",
                        "risks": [],
                    },
                    {
                        "excel_column": "H",
                        "excel_header": "金額-本幣",
                        "classification": "db_derived_field",
                        "processing_location": "sqlite_enrichment",
                        "source_expression": "=F2-G2",
                        "fields": [
                            {"table_id": "ACTML", "column_id": "ML007", "business_meaning": "借貸別"},
                            {"table_id": "ACTML", "column_id": "ML008", "business_meaning": "本幣金額"},
                        ],
                        "relationship_path": [],
                        "lookup_sheet": "",
                        "confidence": 0.86,
                        "reason": "Excel amount formula must be enriched locally.",
                        "risks": [],
                    },
                    {
                        "excel_column": "I",
                        "excel_header": "費用類別",
                        "classification": "excel_enrichment_field",
                        "processing_location": "sqlite_enrichment",
                        "source_expression": "=VLOOKUP(A2,對照表!A:B,2,0)",
                        "fields": [],
                        "relationship_path": [],
                        "lookup_sheet": "對照表",
                        "confidence": 0.9,
                        "reason": "Workbook lookup formula.",
                        "risks": [],
                    },
                ],
                "assumptions": [],
                "confidence": 0.88,
            },
            ensure_ascii=False,
        ),
    )
    classification = classify_workbook_with_llm(
        workbook,
        source_dir="_Source",
        primary_sheet="明細帳",
        user_prompt="費用分析",
        llm_provider="mock",
        llm_model="mock",
    )
    by_header = {column["excel_header"]: column for column in classification["columns"]}
    assert by_header["科目編號"]["classification"] == "db_source_field"
    assert by_header["部門代號"]["classification"] == "db_source_field"
    assert by_header["金額-本幣"]["classification"] == "db_derived_field"
    assert by_header["金額-本幣"]["processing_location"] == "sqlite_enrichment"
    assert by_header["費用類別"]["classification"] == "excel_enrichment_field"
    assert by_header["費用類別"]["lookup_sheet"] == "對照表"
    amount_expression = translate_formula(
        "=F2-G2",
        {
            "F": '"local_debit"',
            "G": '"local_credit"',
        },
    )

    workspace = SQLiteRunWorkspace.create(tmp_path / "run-expense", run_id="expense")
    workspace.write_raw_rows(
        [
            {
                "account_code": "6111",
                "account_name": "租金支出",
                "department_code": "ADM",
                "department_name": "行政部",
                "voucher_date": "20260105",
                "local_debit": 1000.0,
                "local_credit": 0.0,
            },
            {
                "account_code": "6113",
                "account_name": "旅費",
                "department_code": "RND",
                "department_name": "研發部",
                "voucher_date": "20260106",
                "local_debit": 300.0,
                "local_credit": 0.0,
            },
        ]
    )
    lookup = import_lookup_sheet(
        workbook,
        workspace,
        sheet_name="對照表",
        logical_name="lookup_account_category",
        key_column="A",
        value_columns={"expense_category": "B"},
    )

    result = run_enrichment(
        workspace,
        computed_columns=[{"name": "amount_local", "expression": amount_expression}],
        lookup_columns=[
            {
                "name": "expense_category",
                "lookup_table": lookup["table_name"],
                "raw_key": "account_code",
                "lookup_key": "account_code",
                "lookup_value": "expense_category",
            }
        ],
    )

    assert result["enriched_row_count"] == 2
    assert lookup["ignored_row_count"] == 3
    with sqlite3.connect(workspace.sqlite_db_path) as conn:
        columns = [
            row[1]
            for row in conn.execute(
                f'PRAGMA table_info("{workspace.enriched_table}")'
            ).fetchall()
        ]
        rows = conn.execute(
            (
                f'SELECT department_name, account_code, amount_local, expense_category '
                f'FROM "{workspace.enriched_table}" ORDER BY account_code'
            )
        ).fetchall()
        department_totals = conn.execute(
            (
                f'SELECT department_name, SUM(amount_local) '
                f'FROM "{workspace.enriched_table}" '
                f'GROUP BY department_name ORDER BY department_name'
            )
        ).fetchall()
        total = conn.execute(
            f'SELECT SUM(amount_local) FROM "{workspace.enriched_table}"'
        ).fetchone()[0]

    assert columns == [
        "account_code",
        "account_name",
        "department_code",
        "department_name",
        "voucher_date",
        "local_debit",
        "local_credit",
        "expense_category",
        "amount_local",
    ]
    assert rows == [
        ("行政部", "6111", 1000.0, "8.租金支出"),
        ("研發部", "6113", 300.0, "9001.旅費"),
    ]
    assert department_totals == [("研發部", 300.0), ("行政部", 1000.0)]
    assert total == 1300.0
    manifest = workspace.manifest()
    assert Path(manifest["sqlite_db_path"]).is_file()
    assert manifest["run_prefix"] in manifest["raw_table"]
    assert manifest["run_prefix"] in manifest["enriched_table"]
    assert manifest["source_workbook"] == str(workbook)
    assert manifest["source_workbook_hash"]
    assert manifest["raw_row_count"] == 2
    assert manifest["enriched_row_count"] == 2
    assert manifest["lookup_row_counts"][lookup["table_name"]] == 2
    assert len(manifest["ignored_lookup_rows"][lookup["table_name"]]) == 3
    assert manifest["retention_decision"] == "keep"
    assert manifest["cleanup_status"] == "active"

    workspace.cleanup_run_tables()
    deleted_manifest = workspace.manifest()
    assert deleted_manifest["cleanup_status"] == "deleted"
    assert deleted_manifest["retention_decision"] == "delete"
    with sqlite3.connect(workspace.sqlite_db_path) as conn:
        table_names = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert workspace.raw_table not in table_names
    assert workspace.enriched_table not in table_names
    assert lookup["table_name"] not in table_names

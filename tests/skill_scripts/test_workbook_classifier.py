from __future__ import annotations

import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from skill_scripts.workbook_classifier import classify_workbook


REQUIRED_COLUMN_KEYS = {
    "excel_column",
    "excel_header",
    "classification",
    "processing_location",
    "source_expression",
    "lookup_sheet",
    "field_metadata",
    "lineage_inputs",
    "confidence",
    "reason",
    "risks",
}


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _sheet_xml(rows: list[list[str | int | tuple[str, str] | None]]) -> str:
    rendered_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row, start=1):
            cell_ref = f"{_column_name(column_index)}{row_index}"
            if isinstance(value, tuple) and value[0] == "formula":
                formula = value[1].lstrip("=")
                cells.append(f'<c r="{cell_ref}"><f>{escape(formula)}</f><v></v></c>')
            elif value is None:
                cells.append(f'<c r="{cell_ref}" t="inlineStr"><is><t></t></is></c>')
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


def _classification_workbook(path: Path) -> None:
    sheets = [
        (
            "明細帳",
            [
                [
                    "科目編號",
                    "傳票日期",
                    "原幣借方金額",
                    "原幣貸方金額",
                    "本幣借方金額",
                    "本幣貸方金額",
                    "金額-本幣",
                    "年月",
                    "金額-原幣",
                    "BU",
                    "人工調整",
                    "原幣餘額",
                ],
                [
                    "6111",
                    "20260101",
                    100,
                    0,
                    3200,
                    0,
                    ("formula", "=E2-F2"),
                    ("formula", "=LEFT(B2,6)"),
                    ("formula", "=C2-D2"),
                    ("formula", "=VLOOKUP(A2,對照表!A:B,2,0)"),
                    ("formula", "=Z99+1"),
                    None,
                ],
            ],
        ),
        (
            "對照表",
            [
                ["科目編號", "BU"],
                ["6111", "營運管理中心"],
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


def test_classify_workbook_splits_db_derived_excel_and_unresolved_columns(tmp_path: Path):
    workbook = tmp_path / "req.xlsx"
    _classification_workbook(workbook)

    result = classify_workbook(workbook, source_dir="_Source", primary_sheet="明細帳")
    by_header = {item["excel_header"]: item for item in result["columns"]}

    assert by_header["科目編號"]["classification"] == "db_source_field"
    assert by_header["科目編號"]["processing_location"] == "formal_db_sql"
    assert by_header["科目編號"]["field_metadata"][0]["table_id"] == "ACTML"
    assert by_header["科目編號"]["field_metadata"][0]["column_id"] == "ML006"
    assert by_header["科目編號"]["field_metadata"][0]["column_name"] == "明細科目編號"
    assert by_header["傳票日期"]["classification"] == "db_source_field"
    assert by_header["金額-原幣"]["classification"] == "db_derived_field"
    assert by_header["金額-原幣"]["processing_location"] == "sqlite_enrichment"
    assert by_header["金額-原幣"]["source_expression"] == "=C2-D2"
    assert [(item["table_id"], item["column_id"]) for item in by_header["金額-原幣"]["lineage_inputs"]] == [
        ("ACTML", "ML007"),
        ("ACTML", "ML014"),
    ]
    assert [
        (item["table_id"], item["column_id"], item["column_name"])
        for item in by_header["本幣借方金額"]["lineage_inputs"]
    ] == [
        ("ACTML", "ML007", "借貸別"),
        ("ACTML", "ML008", "本幣金額"),
    ]
    assert [
        (item["table_id"], item["column_id"], item["column_name"])
        for item in by_header["本幣貸方金額"]["lineage_inputs"]
    ] == [
        ("ACTML", "ML007", "借貸別"),
        ("ACTML", "ML008", "本幣金額"),
    ]
    assert [
        (item["table_id"], item["column_id"], item["column_name"])
        for item in by_header["金額-本幣"]["lineage_inputs"]
    ] == [
        ("ACTML", "ML007", "借貸別"),
        ("ACTML", "ML008", "本幣金額"),
    ]
    assert [(item["table_id"], item["column_id"]) for item in by_header["年月"]["lineage_inputs"]] == [
        ("ACTML", "ML002"),
    ]
    assert by_header["BU"]["classification"] == "excel_enrichment_field"
    assert by_header["BU"]["processing_location"] == "sqlite_enrichment"
    assert by_header["BU"]["lookup_sheet"] == "對照表"
    assert [(item["table_id"], item["column_id"]) for item in by_header["BU"]["lineage_inputs"]] == [
        ("ACTML", "ML006"),
    ]
    assert by_header["人工調整"]["classification"] == "unresolved_field"
    assert by_header["人工調整"]["processing_location"] == "excluded_pending_rule"
    assert by_header["人工調整"]["risks"]
    assert by_header["原幣餘額"]["classification"] == "unresolved_field"
    assert by_header["原幣餘額"]["processing_location"] == "excluded_pending_rule"
    assert by_header["原幣餘額"]["risks"]
    assert result["lookup_sheet_inventory"] == [{"sheet_name": "對照表", "role": "lookup_sheet"}]


def test_every_column_has_confidence_reason_and_processing_location(tmp_path: Path):
    workbook = tmp_path / "req.xlsx"
    _classification_workbook(workbook)

    result = classify_workbook(workbook, source_dir="_Source", primary_sheet="明細帳")

    assert result["workbook_path"] == str(workbook)
    assert result["primary_sheet"] == "明細帳"
    for column in result["columns"]:
        assert set(column) == REQUIRED_COLUMN_KEYS
        assert column["confidence"] in {"high", "medium", "low"}
        assert column["reason"]
        assert column["processing_location"] in {
            "formal_db_sql",
            "sqlite_enrichment",
            "excluded_pending_rule",
        }

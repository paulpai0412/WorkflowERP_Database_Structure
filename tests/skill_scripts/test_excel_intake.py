from __future__ import annotations

import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from skill_scripts.excel_intake import (
    build_excel_confirmation_payload,
    parse_excel_requirement,
)


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _sheet_xml(rows: list[list[str | tuple[str, str]]]) -> str:
    rendered_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row, start=1):
            cell_ref = f"{_column_name(column_index)}{row_index}"
            if isinstance(value, tuple) and value[0] == "formula":
                formula = value[1].lstrip("=")
                cells.append(
                    f'<c r="{cell_ref}"><f>{escape(formula)}</f><v></v></c>'
                )
            elif isinstance(value, tuple) and value[0] == "shared_formula":
                cells.append(f'<c r="{cell_ref}"><f t="shared" si="{escape(value[1])}"/><v></v></c>')
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


def _write_requirement_workbook(path: Path) -> None:
    sheets = [
        (
            "需求欄位",
            [
                ["表格", "欄位", "顯示名稱", "說明"],
                ["ACPTA", "TA003", "單據日期", "傳票日期"],
                ["ACPTB", "TB017", "未稅金額", "本幣未稅金額"],
                ["ACPTB", "TB018", "稅額", "本幣稅額"],
            ],
        ),
        (
            "自訂公式",
            [
                ["欄位名稱", "公式", "說明"],
                ["總額", ("formula", "=未稅金額+稅額"), "含稅金額"],
                ["稅率", ("formula", "=稅額/未稅金額"), "稅額除以未稅"],
            ],
        ),
        (
            "管理報表",
            [
                ["輸出欄位", "來源欄位", "公式"],
                ["單據日期", "單據日期", ""],
                ["總額", "總額", ("formula", "=未稅金額+稅額")],
                ["毛利率", "", ("formula", "=毛利/營收")],
            ],
        ),
    ]

    workbook_sheets = []
    rels = []
    overrides = []
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
            overrides.append(_sheet_xml(rows))
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


def test_reads_required_database_fields_from_workbook(tmp_path: Path):
    workbook = tmp_path / "requirement.xlsx"
    _write_requirement_workbook(workbook)

    requirement = parse_excel_requirement(workbook)

    assert [(field.table, field.field, field.display_name) for field in requirement.database_fields] == [
        ("ACPTA", "TA003", "單據日期"),
        ("ACPTB", "TB017", "未稅金額"),
        ("ACPTB", "TB018", "稅額"),
    ]


def test_reads_user_formula_fields(tmp_path: Path):
    workbook = tmp_path / "requirement.xlsx"
    _write_requirement_workbook(workbook)

    requirement = parse_excel_requirement(workbook)

    assert [(field.name, field.formula) for field in requirement.formula_fields] == [
        ("總額", "=未稅金額+稅額"),
        ("稅率", "=稅額/未稅金額"),
    ]


def test_extracts_formula_references(tmp_path: Path):
    workbook = tmp_path / "requirement.xlsx"
    _write_requirement_workbook(workbook)

    requirement = parse_excel_requirement(workbook)

    lineage = {item.field_name: item.references for item in requirement.formula_lineage}
    assert lineage["總額"] == [
        {"name": "未稅金額", "source": "database-backed"},
        {"name": "稅額", "source": "database-backed"},
    ]
    assert lineage["稅率"] == [
        {"name": "稅額", "source": "database-backed"},
        {"name": "未稅金額", "source": "database-backed"},
    ]


def test_extracts_formula_backed_references(tmp_path: Path):
    workbook = tmp_path / "requirement.xlsx"
    _write_requirement_workbook(workbook)
    with zipfile.ZipFile(workbook, "a", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "xl/worksheets/sheet2.xml",
            _sheet_xml(
                [
                    ["欄位名稱", "公式", "說明"],
                    ["總額", ("formula", "=未稅金額+稅額"), "含稅金額"],
                    ["費用率", ("formula", "=總額/未稅金額"), "公式欄位除以未稅"],
                ]
            ),
        )

    requirement = parse_excel_requirement(workbook)

    lineage = {item.field_name: item.references for item in requirement.formula_lineage}
    assert {"name": "總額", "source": "formula-backed"} in lineage["費用率"]


def test_detects_formula_columns_without_database_source(tmp_path: Path):
    workbook = tmp_path / "requirement.xlsx"
    _write_requirement_workbook(workbook)

    requirement = parse_excel_requirement(workbook)

    assert any("毛利" in warning and "unresolved" in warning for warning in requirement.warnings)
    assert any("營收" in warning and "unresolved" in warning for warning in requirement.warnings)


def test_warns_about_empty_or_shared_formula_cells(tmp_path: Path):
    workbook = tmp_path / "requirement.xlsx"
    _write_requirement_workbook(workbook)
    with zipfile.ZipFile(workbook, "a", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "xl/worksheets/sheet2.xml",
            _sheet_xml(
                [
                    ["欄位名稱", "公式", "說明"],
                    ["總額", ("shared_formula", "1"), "copied formula"],
                ]
            ),
        )

    requirement = parse_excel_requirement(workbook)

    assert any("總額" in warning and "shared formula" in warning for warning in requirement.warnings)


def test_builds_confirmation_payload_in_chinese(tmp_path: Path):
    workbook = tmp_path / "requirement.xlsx"
    _write_requirement_workbook(workbook)

    requirement = parse_excel_requirement(workbook)
    payload = build_excel_confirmation_payload(requirement)

    assert set(payload) == {"資料庫欄位", "使用者公式欄位", "報表輸出欄位", "需使用者確認"}
    assert payload["資料庫欄位"][0]["顯示名稱"] == "單據日期"
    assert payload["使用者公式欄位"][0]["公式"] == "=未稅金額+稅額"
    assert payload["報表輸出欄位"][1]["輸出欄位"] == "總額"
    assert payload["需使用者確認"]

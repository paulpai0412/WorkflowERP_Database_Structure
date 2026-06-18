from __future__ import annotations

from dataclasses import asdict, dataclass
import re
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
from typing import Any


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


@dataclass(frozen=True)
class DatabaseFieldRequirement:
    table: str
    field: str
    display_name: str
    description: str = ""


@dataclass(frozen=True)
class FormulaFieldRequirement:
    name: str
    formula: str
    description: str = ""


@dataclass(frozen=True)
class ReportFieldRequirement:
    output_name: str
    source_name: str = ""
    formula: str = ""


@dataclass(frozen=True)
class FormulaLineage:
    field_name: str
    formula: str
    references: list[dict[str, str]]


@dataclass(frozen=True)
class WorkbookRequirement:
    database_fields: list[DatabaseFieldRequirement]
    formula_fields: list[FormulaFieldRequirement]
    report_fields: list[ReportFieldRequirement]
    formula_lineage: list[FormulaLineage]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _text(element: ET.Element | None) -> str:
    if element is None or element.text is None:
        return ""
    return element.text.strip()


def _load_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        raw = archive.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(raw)
    strings = []
    for item in root.findall(f"{{{MAIN_NS}}}si"):
        parts = [node.text or "" for node in item.findall(f".//{{{MAIN_NS}}}t")]
        strings.append("".join(parts))
    return strings


def _cell_column(ref: str) -> int:
    letters = "".join(ch for ch in ref if ch.isalpha())
    value = 0
    for ch in letters:
        value = value * 26 + (ord(ch.upper()) - 64)
    return value


def _read_cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    formula = cell.find(f"{{{MAIN_NS}}}f")
    if formula is not None:
        return "=" + _text(formula).lstrip("=")

    cell_type = cell.attrib.get("t", "")
    if cell_type == "inlineStr":
        return _text(cell.find(f".//{{{MAIN_NS}}}t"))

    value = _text(cell.find(f"{{{MAIN_NS}}}v"))
    if cell_type == "s" and value:
        try:
            return shared_strings[int(value)]
        except (ValueError, IndexError):
            return ""
    return value


def _normalise_target(target: str) -> str:
    target = target.lstrip("/")
    if target.startswith("xl/"):
        return target
    return f"xl/{target}"


def _read_xlsx_sheets(path: Path) -> dict[str, list[list[str]]]:
    with zipfile.ZipFile(path) as archive:
        shared_strings = _load_shared_strings(archive)
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        rel_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        rel_targets = {
            rel.attrib["Id"]: _normalise_target(rel.attrib["Target"])
            for rel in rel_root.findall(f"{{{REL_NS}}}Relationship")
        }

        sheets: dict[str, list[list[str]]] = {}
        for sheet in workbook.findall(f".//{{{MAIN_NS}}}sheet"):
            name = sheet.attrib["name"]
            rel_id = sheet.attrib[f"{{{DOC_REL_NS}}}id"]
            sheet_root = ET.fromstring(archive.read(rel_targets[rel_id]))
            rows: list[list[str]] = []
            for row in sheet_root.findall(f".//{{{MAIN_NS}}}row"):
                values: dict[int, str] = {}
                for cell in row.findall(f"{{{MAIN_NS}}}c"):
                    ref = cell.attrib.get("r", "")
                    values[_cell_column(ref)] = _read_cell_value(cell, shared_strings)
                max_column = max(values, default=0)
                rows.append([values.get(index, "") for index in range(1, max_column + 1)])
            sheets[name] = rows
        return sheets


def _rows_as_dicts(rows: list[list[str]]) -> list[dict[str, str]]:
    if not rows:
        return []
    headers = [str(value).strip() for value in rows[0]]
    records = []
    for row in rows[1:]:
        if not any(str(value).strip() for value in row):
            continue
        records.append(
            {
                headers[index]: str(row[index]).strip() if index < len(row) else ""
                for index in range(len(headers))
            }
        )
    return records


def _formula_references(formula: str) -> list[str]:
    body = formula.lstrip("=")
    tokens = re.findall(r"[\u4e00-\u9fffA-Za-z_][\u4e00-\u9fffA-Za-z0-9_]*", body)
    seen: set[str] = set()
    references = []
    for token in tokens:
        upper = token.upper()
        if upper in {"SUM", "AVG", "MIN", "MAX", "IF", "CASE", "WHEN"}:
            continue
        if token not in seen:
            seen.add(token)
            references.append(token)
    return references


def _build_lineage(
    field_name: str,
    formula: str,
    database_names: set[str],
    formula_names: set[str],
) -> FormulaLineage:
    references = []
    for name in _formula_references(formula):
        if name in database_names:
            source = "database-backed"
        elif name in formula_names:
            source = "formula-backed"
        else:
            source = "unresolved"
        references.append({"name": name, "source": source})
    return FormulaLineage(field_name=field_name, formula=formula, references=references)


def parse_excel_requirement(path: str | Path) -> WorkbookRequirement:
    workbook_path = Path(path)
    sheets = _read_xlsx_sheets(workbook_path)
    missing = [name for name in ("需求欄位", "自訂公式", "管理報表") if name not in sheets]
    if missing:
        raise ValueError("Missing required workbook sheets: " + ", ".join(missing))

    database_fields = [
        DatabaseFieldRequirement(
            table=row.get("表格", ""),
            field=row.get("欄位", ""),
            display_name=row.get("顯示名稱", ""),
            description=row.get("說明", ""),
        )
        for row in _rows_as_dicts(sheets["需求欄位"])
    ]
    formula_fields = [
        FormulaFieldRequirement(
            name=row.get("欄位名稱", ""),
            formula=row.get("公式", ""),
            description=row.get("說明", ""),
        )
        for row in _rows_as_dicts(sheets["自訂公式"])
    ]
    report_fields = [
        ReportFieldRequirement(
            output_name=row.get("輸出欄位", ""),
            source_name=row.get("來源欄位", ""),
            formula=row.get("公式", ""),
        )
        for row in _rows_as_dicts(sheets["管理報表"])
    ]

    database_names = {field.display_name for field in database_fields if field.display_name}
    formula_names = {field.name for field in formula_fields if field.name}
    lineage = [
        _build_lineage(field.name, field.formula, database_names, formula_names)
        for field in formula_fields
        if field.formula
    ]
    lineage.extend(
        _build_lineage(field.output_name, field.formula, database_names, formula_names)
        for field in report_fields
        if field.formula
    )

    warnings = [
        f"Formula field '{item.field_name}' references unresolved source '{ref['name']}'."
        for item in lineage
        for ref in item.references
        if ref["source"] == "unresolved"
    ]
    warnings.extend(
        f"Formula field '{field.name}' appears to use an empty or shared formula that cannot be resolved locally."
        for field in formula_fields
        if field.formula.strip() == "="
    )
    warnings.extend(
        f"Report field '{field.output_name}' appears to use an empty or shared formula that cannot be resolved locally."
        for field in report_fields
        if field.formula.strip() == "="
    )

    return WorkbookRequirement(
        database_fields=database_fields,
        formula_fields=formula_fields,
        report_fields=report_fields,
        formula_lineage=lineage,
        warnings=warnings,
    )


def build_excel_confirmation_payload(requirement: WorkbookRequirement) -> dict[str, list[dict[str, Any]] | list[str]]:
    return {
        "資料庫欄位": [
            {
                "表格": field.table,
                "欄位": field.field,
                "顯示名稱": field.display_name,
                "說明": field.description,
            }
            for field in requirement.database_fields
        ],
        "使用者公式欄位": [
            {
                "欄位名稱": field.name,
                "公式": field.formula,
                "說明": field.description,
                "公式來源": next(
                    (
                        item.references
                        for item in requirement.formula_lineage
                        if item.field_name == field.name and item.formula == field.formula
                    ),
                    [],
                ),
            }
            for field in requirement.formula_fields
        ],
        "報表輸出欄位": [
            {
                "輸出欄位": field.output_name,
                "來源欄位": field.source_name,
                "公式": field.formula,
            }
            for field in requirement.report_fields
        ],
        "需使用者確認": requirement.warnings,
    }

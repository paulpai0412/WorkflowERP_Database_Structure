from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from skill_scripts.excel_intake import _read_xlsx_sheets_with_metadata
from skill_scripts.schema_metadata import SchemaMetadata


FIELD_SEEDS: dict[str, list[dict[str, str]]] = {
    "科目編號": [{"table_id": "ACTML", "column_id": "ML006", "reason": "明細帳科目編號"}],
    "傳票日期": [{"table_id": "ACTML", "column_id": "ML002", "reason": "傳票日期"}],
    "部門代號": [{"table_id": "ACTML", "column_id": "ML010", "reason": "部門代號"}],
    "專案代號": [{"table_id": "ACTML", "column_id": "ML011", "reason": "專案代號"}],
    "摘要": [{"table_id": "ACTML", "column_id": "ML009", "reason": "摘要"}],
    "幣別": [{"table_id": "ACTML", "column_id": "ML012", "reason": "幣別"}],
    "匯率": [{"table_id": "ACTML", "column_id": "ML013", "reason": "匯率"}],
}

DERIVED_FIELD_SEEDS: dict[str, list[dict[str, str]]] = {
    "金額-原幣": [
        {"table_id": "ACTML", "column_id": "ML007", "reason": "借貸別"},
        {"table_id": "ACTML", "column_id": "ML014", "reason": "原幣金額"},
    ],
    "原幣借方金額": [
        {"table_id": "ACTML", "column_id": "ML007", "reason": "借貸別"},
        {"table_id": "ACTML", "column_id": "ML014", "reason": "原幣金額"},
    ],
    "原幣貸方金額": [
        {"table_id": "ACTML", "column_id": "ML007", "reason": "借貸別"},
        {"table_id": "ACTML", "column_id": "ML014", "reason": "原幣金額"},
    ],
    "本幣借方金額": [
        {"table_id": "ACTML", "column_id": "ML007", "reason": "借貸別"},
        {"table_id": "ACTML", "column_id": "ML008", "reason": "本幣金額"},
    ],
    "本幣貸方金額": [
        {"table_id": "ACTML", "column_id": "ML007", "reason": "借貸別"},
        {"table_id": "ACTML", "column_id": "ML008", "reason": "本幣金額"},
    ],
    "金額-本幣": [
        {"table_id": "ACTML", "column_id": "ML007", "reason": "借貸別"},
        {"table_id": "ACTML", "column_id": "ML008", "reason": "本幣金額"},
    ],
    "年月": [{"table_id": "ACTML", "column_id": "ML002", "reason": "傳票日期"}],
}

UNRESOLVED_HEADERS = {"原幣餘額", "原幣借/貸餘", "本幣餘額", "本幣借/貸餘"}


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _lookup_sheet(formula: str) -> str:
    match = re.search(
        r"VLOOKUP\s*\([^,]+,\s*(?:'([^']+)'|([^!,]+))!",
        formula,
        re.IGNORECASE,
    )
    if not match:
        return ""
    return (match.group(1) or match.group(2) or "").strip()


def _lookup_key_column_index(formula: str) -> int:
    match = re.search(r"VLOOKUP\s*\(\s*'?([A-Z]+)\$?\d+", formula, re.IGNORECASE)
    if not match:
        return 0
    index = 0
    for char in match.group(1).upper():
        index = index * 26 + (ord(char) - 64)
    return index


def _describe_fields(metadata: SchemaMetadata, fields: list[dict[str, str]]) -> list[dict[str, Any]]:
    return [
        metadata.describe_field(
            item["table_id"],
            item["column_id"],
            business_meaning=item.get("reason", ""),
        )
        for item in fields
    ]


def _source_expression(fields: list[dict[str, str]], fallback: str = "") -> str:
    if fallback:
        return fallback
    if not fields:
        return ""
    return " + ".join(f"{item['table_id']}.{item['column_id']}" for item in fields)


def _classify_column(
    header: str,
    formula: str,
    metadata: SchemaMetadata,
) -> tuple[str, str, str, str, list[dict[str, Any]], str, list[str]]:
    field_inputs = FIELD_SEEDS.get(header, [])
    if field_inputs:
        field_metadata = _describe_fields(metadata, field_inputs)
        return (
            "db_source_field",
            "formal_db_sql",
            "high",
            "",
            field_metadata,
            "Header matched deterministic WFERP seed mapping.",
            [],
        )

    lookup_sheet = _lookup_sheet(formula)
    if lookup_sheet:
        return (
            "excel_enrichment_field",
            "sqlite_enrichment",
            "high",
            lookup_sheet,
            [],
            f"Formula references workbook lookup sheet {lookup_sheet}.",
            [],
        )

    derived_inputs = DERIVED_FIELD_SEEDS.get(header, [])
    if derived_inputs:
        field_metadata = _describe_fields(metadata, derived_inputs) if derived_inputs else []
        return (
            "db_derived_field",
            "sqlite_enrichment",
            "medium",
            "",
            field_metadata,
            "Column can be derived from raw database fields during SQLite enrichment.",
            [],
        )

    if formula:
        return (
            "unresolved_field",
            "excluded_pending_rule",
            "low",
            "",
            [],
            "Formula has no deterministic DB raw-field lineage or supported lookup pattern.",
            ["Unsupported formula must be confirmed before enrichment."],
        )

    if header in UNRESOLVED_HEADERS:
        return (
            "unresolved_field",
            "excluded_pending_rule",
            "medium",
            "",
            [],
            "Column requires opening-balance or external business rule before enrichment.",
            ["Needs a confirmed business rule before it can be included in enrichment."],
        )

    return (
        "unresolved_field",
        "excluded_pending_rule",
        "low",
        "",
        [],
        "No deterministic schema, formula, or lookup evidence was found.",
        ["No rule-backed mapping was found for this workbook column."],
    )


def classify_workbook(
    workbook_path: str | Path,
    *,
    source_dir: str | Path,
    primary_sheet: str = "",
) -> dict[str, Any]:
    path = Path(workbook_path)
    sheets = _read_xlsx_sheets_with_metadata(path)
    sheet_name = primary_sheet or next(iter(sheets))
    if sheet_name not in sheets:
        raise ValueError(f"Workbook sheet not found: {sheet_name}")

    sheet = sheets[sheet_name]
    headers = [str(value).strip() for value in sheet.rows[0]] if sheet.rows else []
    sample_row = sheet.rows[1] if len(sheet.rows) > 1 else []
    metadata = SchemaMetadata.from_source_dir(source_dir)
    columns: list[dict[str, Any]] = []
    lookup_sheets: set[str] = set()

    for index, header in enumerate(headers, start=1):
        sample = sample_row[index - 1] if index <= len(sample_row) else ""
        formula = sample if str(sample).startswith("=") else ""
        (
            classification,
            processing_location,
            confidence,
            lookup_sheet,
            field_metadata,
            reason,
            risks,
        ) = _classify_column(header, formula, metadata)
        if lookup_sheet:
            lookup_sheets.add(lookup_sheet)
        seed_inputs = FIELD_SEEDS.get(header, DERIVED_FIELD_SEEDS.get(header, []))
        if lookup_sheet:
            key_index = _lookup_key_column_index(formula)
            key_header = headers[key_index - 1] if 0 < key_index <= len(headers) else ""
            seed_inputs = FIELD_SEEDS.get(key_header, DERIVED_FIELD_SEEDS.get(key_header, []))
        lineage_inputs = _describe_fields(metadata, seed_inputs) if seed_inputs else []
        columns.append(
            {
                "excel_column": _column_name(index),
                "excel_header": header,
                "classification": classification,
                "processing_location": processing_location,
                "source_expression": _source_expression(seed_inputs, formula),
                "lookup_sheet": lookup_sheet,
                "field_metadata": field_metadata,
                "lineage_inputs": lineage_inputs,
                "confidence": confidence,
                "reason": reason,
                "risks": risks,
            }
        )

    return {
        "workbook_path": str(path),
        "primary_sheet": sheet_name,
        "columns": columns,
        "lookup_sheet_inventory": [
            {"sheet_name": name, "role": "lookup_sheet"} for name in sorted(lookup_sheets)
        ],
    }

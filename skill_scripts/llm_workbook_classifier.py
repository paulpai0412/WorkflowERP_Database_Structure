from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from skill_scripts.data_dictionary import build_alias_index
from skill_scripts.excel_intake import _read_xlsx_sheets_with_metadata
from skill_scripts.llm_sql_generator import call_llm
from skill_scripts.schema_loader import load_schema_bundle
from skill_scripts.schema_metadata import SchemaMetadata
from skill_scripts.workbook_classifier import _column_name, _lookup_sheet


def _strip_fence(text: str) -> str:
    value = str(text or "").strip()
    if not value.startswith("```"):
        return value
    lines = value.splitlines()
    if lines and lines[0].startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return value


def _field_ref(table_id: str, column_id: str) -> str:
    return f"{table_id.strip().upper()}.{column_id.strip().upper()}"


def _schema_indexes(bundle: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    tables = {str(row.get("TableID", "")).strip().upper(): row for row in bundle.get("tables", [])}
    fields = {
        _field_ref(str(row.get("TableID", "")), str(row.get("ID", ""))): row
        for row in bundle.get("fields", [])
        if str(row.get("TableID", "")).strip() and str(row.get("ID", "")).strip()
    }
    return tables, fields


def _workbook_columns(workbook_path: Path, primary_sheet: str) -> tuple[str, list[dict[str, Any]], set[str]]:
    sheets = _read_xlsx_sheets_with_metadata(workbook_path)
    sheet_name = primary_sheet or next(iter(sheets))
    if sheet_name not in sheets:
        raise ValueError(f"Workbook sheet not found: {sheet_name}")
    sheet = sheets[sheet_name]
    headers = [str(value).strip() for value in sheet.rows[0]] if sheet.rows else []
    sample_row = sheet.rows[1] if len(sheet.rows) > 1 else []
    lookup_sheets: set[str] = set()
    columns = []
    for index, header in enumerate(headers, start=1):
        sample = sample_row[index - 1] if index <= len(sample_row) else ""
        formula = sample if str(sample).startswith("=") else ""
        lookup_sheet = _lookup_sheet(formula)
        if lookup_sheet:
            lookup_sheets.add(lookup_sheet)
        columns.append(
            {
                "excel_column": _column_name(index),
                "excel_header": header,
                "sample_value": "" if formula else str(sample or "")[:120],
                "formula": formula,
                "lookup_sheet": lookup_sheet,
            }
        )
    return sheet_name, columns, lookup_sheets


def _candidate_schema_context(bundle: dict[str, Any], workbook_columns: list[dict[str, Any]]) -> dict[str, Any]:
    tables_by_id, fields_by_ref = _schema_indexes(bundle)
    alias_index = build_alias_index(bundle.get("fields", []))
    table_scores: dict[str, int] = {}
    candidate_refs: set[str] = set()

    for column in workbook_columns:
        header = str(column.get("excel_header", "")).strip().lower()
        if not header:
            continue
        for ref in alias_index.get(header, [])[:20]:
            candidate_refs.add(ref)
            table_scores[ref.split(".", 1)[0].upper()] = table_scores.get(ref.split(".", 1)[0].upper(), 0) + 5

    # Broad accounting context for the LLM to choose table groups from. This is retrieval,
    # not final mapping: the LLM must still name candidate tables and justify them.
    for table in bundle.get("tables", []):
        table_id = str(table.get("TableID", "")).strip().upper()
        table_name = str(table.get("TableName", "")).strip()
        if table_id.startswith("ACT") or any(token in table_name for token in ("會計", "分類帳", "科目", "傳票")):
            table_scores[table_id] = table_scores.get(table_id, 0) + 1

    top_tables = sorted(table_scores, key=lambda table_id: (-table_scores[table_id], table_id))[:40]
    table_payload = []
    for table_id in top_tables:
        table = tables_by_id.get(table_id, {})
        table_fields = [
            {
                "column_id": str(field.get("ID", "")).strip(),
                "column_name": str(field.get("FieldName", "")).strip(),
                "description": str(field.get("Description", "")).strip(),
            }
            for ref, field in fields_by_ref.items()
            if ref.startswith(f"{table_id}.")
        ][:80]
        table_payload.append(
            {
                "table_id": table_id,
                "table_name": str(table.get("TableName", "")).strip(),
                "module_id": str(table.get("ModuleID", "")).strip(),
                "fields": table_fields,
            }
        )

    return {
        "candidate_tables_for_llm_to_choose_from": table_payload,
        "direct_alias_hits": sorted(candidate_refs)[:120],
        "relationship_edges_hint": "Use relationship_edges.json from repo context conceptually; output explicit join path when a field comes from another table.",
    }


def build_llm_table_first_classification_prompt(
    *,
    user_prompt: str,
    workbook_path: Path,
    primary_sheet: str,
    workbook_columns: list[dict[str, Any]],
    schema_context: dict[str, Any],
) -> str:
    return (
        "You are a Workflow ERP schema analyst. Classify workbook columns for a report harness.\n"
        "You MUST reason table-first: first identify the most likely WFERP table group(s) containing the report data, "
        "then map each workbook column to table fields or enrichment formulas.\n"
        "Do not map a column by header alone. Use table purpose, field meaning, formulas, and relationship paths.\n"
        "Output JSON only with keys: candidate_tables, column_mappings, assumptions, confidence.\n"
        "candidate_tables: list of {table_id, table_name, reason, confidence}.\n"
        "column_mappings: one item per workbook column with keys: excel_column, excel_header, classification "
        "(db_source_field|db_derived_field|excel_enrichment_field|unresolved_field), processing_location "
        "(formal_db_sql|sqlite_enrichment|excluded_pending_rule), source_expression, fields "
        "([{table_id,column_id,business_meaning}]), relationship_path "
        "([{from_table,from_columns,to_table,to_columns,reason,confidence}]), lookup_sheet, confidence, reason, risks.\n"
        "Rules: DB query may only retrieve raw DB source fields. Excel formulas and lookups must be sqlite_enrichment. "
        "If relationship is uncertain, keep the mapping but add a risk instead of hiding the uncertainty.\n"
        f"User request: {user_prompt}\n"
        f"Workbook: {workbook_path}\n"
        f"Primary sheet: {primary_sheet}\n"
        f"Workbook columns: {json.dumps(workbook_columns, ensure_ascii=False)}\n"
        f"Schema context: {json.dumps(schema_context, ensure_ascii=False)}"
    )


def _parse_llm_payload(raw_text: str) -> dict[str, Any]:
    payload = json.loads(_strip_fence(raw_text))
    if not isinstance(payload.get("candidate_tables"), list):
        raise ValueError("LLM classification missing candidate_tables")
    if not isinstance(payload.get("column_mappings"), list):
        raise ValueError("LLM classification missing column_mappings")
    return payload


def _describe_llm_fields(
    metadata: SchemaMetadata,
    fields: list[dict[str, Any]],
    fields_by_ref: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    described = []
    for field in fields:
        table_id = str(field.get("table_id", "")).strip()
        column_id = str(field.get("column_id", "")).strip()
        if not table_id or not column_id:
            continue
        ref = _field_ref(table_id, column_id)
        item = metadata.describe_field(
            table_id,
            column_id,
            business_meaning=str(field.get("business_meaning", "")).strip(),
        )
        if ref not in fields_by_ref:
            item["metadata_status"] = "warning"
            item["business_meaning"] = (item["business_meaning"] + "; LLM field ref not found").strip()
        described.append(item)
    return described


def classify_workbook_with_llm(
    workbook_path: str | Path,
    *,
    source_dir: str | Path,
    primary_sheet: str = "",
    user_prompt: str = "",
    llm_provider: str,
    llm_model: str,
    timeout_sec: float = 60.0,
) -> dict[str, Any]:
    path = Path(workbook_path)
    sheet_name, workbook_columns, lookup_sheets = _workbook_columns(path, primary_sheet)
    bundle = load_schema_bundle(str(source_dir))
    _tables_by_id, fields_by_ref = _schema_indexes(bundle)
    schema_context = _candidate_schema_context(bundle, workbook_columns)
    prompt = build_llm_table_first_classification_prompt(
        user_prompt=user_prompt,
        workbook_path=path,
        primary_sheet=sheet_name,
        workbook_columns=workbook_columns,
        schema_context=schema_context,
    )
    raw = call_llm(llm_provider, llm_model, prompt, timeout_sec=timeout_sec)
    llm_payload = _parse_llm_payload(raw)
    metadata = SchemaMetadata.from_source_dir(source_dir)

    by_key = {
        (str(item.get("excel_column", "")).strip(), str(item.get("excel_header", "")).strip()): item
        for item in llm_payload["column_mappings"]
        if isinstance(item, dict)
    }

    columns = []
    for column in workbook_columns:
        key = (str(column["excel_column"]), str(column["excel_header"]))
        mapping = by_key.get(key)
        if not mapping:
            mapping = {
                "excel_column": column["excel_column"],
                "excel_header": column["excel_header"],
                "classification": "unresolved_field",
                "processing_location": "excluded_pending_rule",
                "source_expression": "",
                "fields": [],
                "relationship_path": [],
                "lookup_sheet": column.get("lookup_sheet", ""),
                "confidence": "low",
                "reason": "LLM did not return a mapping for this workbook column.",
                "risks": ["Missing LLM mapping."],
            }
        field_metadata = _describe_llm_fields(
            metadata,
            [field for field in mapping.get("fields", []) if isinstance(field, dict)],
            fields_by_ref,
        )
        lookup_sheet = str(mapping.get("lookup_sheet") or column.get("lookup_sheet") or "")
        if lookup_sheet:
            lookup_sheets.add(lookup_sheet)
        confidence = mapping.get("confidence", "low")
        if isinstance(confidence, (int, float)):
            confidence = "high" if float(confidence) >= 0.8 else "medium" if float(confidence) >= 0.5 else "low"
        columns.append(
            {
                "excel_column": column["excel_column"],
                "excel_header": column["excel_header"],
                "classification": str(mapping.get("classification") or "unresolved_field"),
                "processing_location": str(mapping.get("processing_location") or "excluded_pending_rule"),
                "source_expression": str(mapping.get("source_expression") or ""),
                "lookup_sheet": lookup_sheet,
                "field_metadata": field_metadata,
                "lineage_inputs": field_metadata,
                "relationship_path": mapping.get("relationship_path", []),
                "schema_candidates": [],
                "confidence": str(confidence),
                "reason": str(mapping.get("reason") or "LLM table-first classification."),
                "risks": [str(risk) for risk in mapping.get("risks", [])],
            }
        )

    return {
        "workbook_path": str(path),
        "primary_sheet": sheet_name,
        "resolver_strategy": "llm_table_first_schema_relationship_resolver",
        "llm_status": "used",
        "llm_provider": llm_provider,
        "llm_model": llm_model,
        "candidate_tables": llm_payload["candidate_tables"],
        "assumptions": llm_payload.get("assumptions", []),
        "confidence": llm_payload.get("confidence", 0),
        "columns": columns,
        "lookup_sheet_inventory": [
            {"sheet_name": name, "role": "lookup_sheet"} for name in sorted(lookup_sheets)
        ],
    }

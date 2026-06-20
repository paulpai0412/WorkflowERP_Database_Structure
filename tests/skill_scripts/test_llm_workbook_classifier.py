from __future__ import annotations

import json
from pathlib import Path

from tests.skill_scripts.test_workbook_classifier import _classification_workbook
from skill_scripts.llm_workbook_classifier import (
    build_llm_table_first_classification_prompt,
    classify_workbook_with_llm,
)


def test_llm_prompt_requires_table_first_resolution(tmp_path: Path):
    prompt = build_llm_table_first_classification_prompt(
        user_prompt="產生每月損益比較表",
        workbook_path=tmp_path / "req.xlsx",
        primary_sheet="明細帳",
        workbook_columns=[{"excel_column": "A", "excel_header": "科目名稱", "formula": ""}],
        schema_context={"candidate_tables_for_llm_to_choose_from": []},
    )

    assert "table-first" in prompt
    assert "first identify the most likely WFERP table group" in prompt
    assert "Do not map a column by header alone" in prompt
    assert "candidate_tables" in prompt
    assert "relationship_path" in prompt


def test_classify_workbook_with_llm_uses_candidate_tables_before_field_mapping(
    tmp_path: Path, monkeypatch
):
    workbook = tmp_path / "req.xlsx"
    _classification_workbook(workbook)
    llm_payload = {
        "candidate_tables": [
            {
                "table_id": "ACTML",
                "table_name": "分類帳檔",
                "reason": "明細帳交易列最可能在分類帳檔",
                "confidence": 0.93,
            },
            {
                "table_id": "ACTMA",
                "table_name": "會計科目資料檔",
                "reason": "科目名稱需由科目主檔取得",
                "confidence": 0.88,
            },
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
                "confidence": 0.92,
                "reason": "LLM selected ACTML as ledger table first, then mapped account code.",
                "risks": [],
            },
            {
                "excel_column": "J",
                "excel_header": "BU",
                "classification": "excel_enrichment_field",
                "processing_location": "sqlite_enrichment",
                "source_expression": "=VLOOKUP(A2,對照表!A:B,2,0)",
                "fields": [],
                "relationship_path": [],
                "lookup_sheet": "對照表",
                "confidence": 0.9,
                "reason": "Workbook lookup formula, not formal DB SQL.",
                "risks": [],
            },
        ],
        "assumptions": ["mock table-first classifier response"],
        "confidence": 0.9,
    }
    monkeypatch.setenv("LLM_MOCK_RESPONSE", json.dumps(llm_payload, ensure_ascii=False))

    result = classify_workbook_with_llm(
        workbook,
        source_dir="_Source",
        primary_sheet="明細帳",
        user_prompt="產生每月損益比較表",
        llm_provider="mock",
        llm_model="mock",
    )

    assert result["resolver_strategy"] == "llm_table_first_schema_relationship_resolver"
    assert result["llm_status"] == "used"
    assert [table["table_id"] for table in result["candidate_tables"]][:2] == ["ACTML", "ACTMA"]
    by_header = {column["excel_header"]: column for column in result["columns"]}
    assert by_header["科目編號"]["field_metadata"][0]["table_id"] == "ACTML"
    assert by_header["科目編號"]["field_metadata"][0]["column_id"] == "ML006"
    assert by_header["BU"]["classification"] == "excel_enrichment_field"
    assert by_header["BU"]["lookup_sheet"] == "對照表"

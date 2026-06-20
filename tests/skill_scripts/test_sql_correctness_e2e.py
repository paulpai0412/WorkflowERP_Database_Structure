import json
import os
from decimal import Decimal
from typing import SupportsFloat, cast

import pytest

from skill_scripts.database_client import DatabaseClient, DatabaseConfig
from skill_scripts.execution_validator import AggregateExpectation, ExecutionExpectation
from skill_scripts.governed_query import run_governed_query
from skill_scripts.sql_router import RoutingOptions


def _bundle() -> dict[str, list[dict[str, str]]]:
    return {
        "modules": [{"ModuleID": "ACT", "ModuleName": "會計總帳管理系統"}],
        "tables": [
            {"DB": "wferp_test.dbo.", "TableID": "ACTMK", "TableName": "科目/部門預算單身檔", "TableNameViet": "", "ModuleID": "ACT"},
        ],
        "fields": [
            {"TableID": "ACTMK", "ID": "MK001", "FieldName": "預算編號", "NameVietnam": ""},
            {"TableID": "ACTMK", "ID": "MK002", "FieldName": "會計年度", "NameVietnam": "Năm kế toán"},
            {"TableID": "ACTMK", "ID": "MK005", "FieldName": "期別", "NameVietnam": ""},
            {"TableID": "ACTMK", "ID": "MK006", "FieldName": "期預算", "NameVietnam": "Dự toán kỳ"},
        ],
        "index_keys": [
            {"TableName": "ACTMK", "IndexColumnName": "MK001+MK002+MK003+MK004+MK005", "isPrimaryKey": "1"},
        ],
    }


def _money(value: object) -> float:
    if isinstance(value, Decimal):
        return float(value)
    return float(cast(SupportsFloat, value))


def test_real_test_db_actmk_fixture_supports_2026_budget_correctness(monkeypatch: pytest.MonkeyPatch) -> None:
    if os.getenv("WFERP_RUN_DB_E2E") != "1":
        pytest.skip("Set WFERP_RUN_DB_E2E=1 after starting and seeding test_db to run SQL correctness E2E.")

    config = DatabaseConfig.from_env()
    assert config.env == "test"
    client = DatabaseClient(config)

    contrast_rows = client.execute_readonly("SELECT [MK002],[MK006] FROM [dbo].[ACTMK] WHERE [MK002] = '2025'")
    assert len(contrast_rows) == 1
    assert str(contrast_rows[0]["MK002"]).strip() == "2025"
    assert _money(contrast_rows[0]["MK006"]) == 999999.0

    monkeypatch.setenv(
        "LLM_MOCK_RESPONSE",
        json.dumps(
            {
                "sql": "SELECT [MK002],[MK006] FROM [dbo].[ACTMK] WHERE [MK002] = '2026' ORDER BY [MK005]",
                "used_tables": ["ACTMK"],
                "assumptions": [],
                "confidence": 0.95,
            },
            ensure_ascii=False,
        ),
    )
    result = run_governed_query(
        prompt="查詢2026年的工程預算明細",
        bundle=_bundle(),
        options=RoutingOptions(
            mode="llm-first",
            llm_provider="mock",
            llm_model="mock",
            min_confidence=0.5,
            execution_expectation=ExecutionExpectation(
                required_columns=["MK002", "MK006"],
                min_rows=3,
                max_rows=3,
                aggregates=[AggregateExpectation(operation="sum", column="MK006", expected_value=450000.0)],
            ),
        ),
        db_client=client,
        sample_rows_limit=3,
    )

    assert result.evidence.validation_status == "OK"
    assert result.evidence.execution_status == "OK"
    assert result.evidence.returned_columns == ["MK002", "MK006"]
    assert result.evidence.row_count == 3
    assert [str(row["MK002"]).strip() for row in result.evidence.sample_rows] == ["2026", "2026", "2026"]
    assert sum(_money(row["MK006"]) for row in result.evidence.sample_rows) == 450000.0
    assert result.evidence.aggregate_checks == [
        {"operation": "sum", "column": "MK006", "expected_value": 450000.0, "tolerance": 0.0}
    ]

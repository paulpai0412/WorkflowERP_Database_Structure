"""E2E-003: Analyst Approval gate before Chart Spec (issue #33).

Focused slice that proves the existing query-approval gate behavior for the
``查詢2026年的工程預算明細`` prompt:

* AC1 - A governed query result is produced from the deterministic 2026
  engineering-budget scenario via the existing CLI/library surface.
* AC2 - Attempting to create a Chart Spec from the unapproved governed query
  result fails with the existing query-approval gate.
* AC3 - After Analyst Approval, the same governed query result can author a
  bar Chart Spec using ``MK006`` as the budget value field.
* AC4 - Refusal and approved paths are recorded as compact behavioral
  assertions; raw command logs are not embedded.
* AC5 - This test is additive and does not weaken Chart Spec, governed-query,
  or Dashboard Canvas assertions exercised by the broader MVP E2E.

Both Chart Spec entry points that depend on
``require_query_result_approved_for_chart_spec`` are exercised here so neither
wrapper can silently weaken the gate:
``skill_scripts.chart_spec.author_chart_spec`` and
``skill_scripts.dashboard_canvas.create_dashboard_chart_draft``.
"""

from __future__ import annotations

import json
from typing import Protocol, cast

from pytest import MonkeyPatch

import skill_scripts.governed_query as governed_query_module
from skill_scripts.chart_spec import ChartSpec, author_chart_spec
from skill_scripts.dashboard_canvas import (
    DashboardChartDraft,
    create_dashboard_chart_draft,
)
from skill_scripts.execution_validator import ExecutionExpectation
from skill_scripts.governed_query import (
    GovernedQueryResult,
    approve_query_result,
)
from skill_scripts.sql_router import RoutingOptions


PROMPT: str = "查詢2026年的工程預算明細"
EXPECTED_GATE_ERROR_CODE: str = "QUERY_RESULT_NOT_APPROVED"


def _bundle() -> dict[str, list[dict[str, str]]]:
    return {
        "modules": [{"ModuleID": "ACT", "ModuleName": "會計總帳管理系統"}],
        "tables": [
            {
                "DB": "VPIC1.dbo.",
                "TableID": "ACTMK",
                "TableName": "科目/部門預算單身檔",
                "TableNameViet": "",
                "ModuleID": "ACT",
            },
        ],
        "fields": [
            {"TableID": "ACTMK", "ID": "MK002", "FieldName": "會計年度", "NameVietnam": "Năm kế toán"},
            {"TableID": "ACTMK", "ID": "MK006", "FieldName": "期預算", "NameVietnam": "Dự toán kỳ"},
        ],
        "index_keys": [
            {"TableName": "ACTMK", "IndexColumnName": "MK001+MK002+MK003+MK004+MK005", "isPrimaryKey": "1"},
        ],
    }


class _FakeDbConfig:
    def __init__(self, env: str = "test") -> None:
        self.env: str = env


class _FakeDbClient:
    def __init__(self) -> None:
        self.config: _FakeDbConfig = _FakeDbConfig(env="test")
        self.executed_sql: list[str] = []

    def execute_readonly(self, sql: str) -> list[dict[str, object]]:
        self.executed_sql.append(sql)
        return [
            {"MK002": "2026", "MK006": 150000.0},
            {"MK002": "2026", "MK006": 150000.0},
            {"MK002": "2026", "MK006": 150000.0},
        ]

    def health_check(self) -> tuple[bool, str]:
        return True, "OK"


class _RunGovernedQuery(Protocol):
    def __call__(
        self,
        prompt: str,
        bundle: dict[str, list[dict[str, str]]],
        options: RoutingOptions,
        db_client: _FakeDbClient,
        sample_rows_limit: int = 5,
    ) -> GovernedQueryResult: ...


def _routing_options() -> RoutingOptions:
    return RoutingOptions(
        mode="llm-first",
        llm_provider="mock",
        llm_model="mock",
        min_confidence=0.5,
        execution_expectation=ExecutionExpectation(
            required_columns=["MK002", "MK006"],
            min_rows=1,
        ),
    )


def _bar_chart_payload_with_mk006_value_field() -> dict[str, object]:
    return {
        "chart_type": "bar",
        "title": "2026 工程預算明細",
        "x_field": "MK002",
        "y_field": "MK006",
        "number_format": {"field": "MK006", "style": "currency", "currency": "TWD"},
    }


def _produce_governed_query_result(monkeypatch: MonkeyPatch) -> GovernedQueryResult:
    monkeypatch.setenv(
        "LLM_MOCK_RESPONSE",
        json.dumps(
            {
                "sql": "SELECT [MK002],[MK006] FROM [VPIC1].[dbo].[ACTMK] WHERE [MK002] = '2026'",
                "used_tables": ["ACTMK"],
                "assumptions": [],
                "confidence": 0.95,
            },
            ensure_ascii=False,
        ),
    )
    run_governed_query = cast(_RunGovernedQuery, governed_query_module.run_governed_query)
    return run_governed_query(
        prompt=PROMPT,
        bundle=_bundle(),
        options=_routing_options(),
        db_client=_FakeDbClient(),
    )


def test_unapproved_query_result_blocks_chart_spec_authoring(monkeypatch: MonkeyPatch) -> None:
    """AC1 + AC2 + AC4: gate refuses Chart Spec authoring before approval."""
    query_result = _produce_governed_query_result(monkeypatch)

    assert query_result.approval_state == "ready_for_analyst_approval"
    assert query_result.evidence.returned_columns == ["MK002", "MK006"]
    assert query_result.evidence.row_count == 3

    try:
        _ = author_chart_spec(query_result, _bar_chart_payload_with_mk006_value_field())
        raise AssertionError("expected RuntimeError from author_chart_spec")
    except RuntimeError as exc:
        assert str(exc) == EXPECTED_GATE_ERROR_CODE

    try:
        _ = create_dashboard_chart_draft(query_result, _bar_chart_payload_with_mk006_value_field())
        raise AssertionError("expected RuntimeError from create_dashboard_chart_draft")
    except RuntimeError as exc:
        assert str(exc) == EXPECTED_GATE_ERROR_CODE


def test_approved_query_result_authors_mk006_bar_chart_spec(monkeypatch: MonkeyPatch) -> None:
    """AC1 + AC3 + AC4 + AC5: approved result authors a bar Chart Spec on MK006."""
    query_result = _produce_governed_query_result(monkeypatch)
    approved = approve_query_result(query_result)

    assert approved.approval_state == "approved_for_chart_spec"
    assert approved.evidence == query_result.evidence

    spec = author_chart_spec(approved, _bar_chart_payload_with_mk006_value_field())
    assert isinstance(spec, ChartSpec)
    assert spec.chart_type == "bar"
    assert spec.title == "2026 工程預算明細"
    assert spec.x_field == "MK002"
    assert spec.y_field == "MK006"
    assert spec.number_format == {"field": "MK006", "style": "currency", "currency": "TWD"}

    draft = create_dashboard_chart_draft(approved, _bar_chart_payload_with_mk006_value_field())
    assert isinstance(draft, DashboardChartDraft)
    assert draft.chart.chart_type == "bar"
    assert draft.chart.x_field == "MK002"
    assert draft.chart.y_field == "MK006"

    preview = draft.preview
    assert preview["chart_type"] == "bar"
    assert preview["x_field"] == "MK002"
    assert preview["y_field"] == "MK006"

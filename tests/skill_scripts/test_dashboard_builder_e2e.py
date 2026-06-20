import json
from typing import Protocol, cast

from pytest import MonkeyPatch

import skill_scripts.governed_query as governed_query_module
from skill_scripts.dashboard_canvas import DashboardCanvas, create_dashboard_chart_draft
from skill_scripts.dashboard_publish import (
    DashboardDraft,
    PublishedDashboard,
    approve_dashboard_draft,
    create_published_dashboard_link,
    preview_dashboard_draft,
    publish_dashboard,
    refresh_published_dashboard_view,
    render_published_dashboard_link,
    revoke_published_dashboard_link,
)
from skill_scripts.design_template_catalog import select_design_template
from skill_scripts.execution_validator import ExecutionExpectation
from skill_scripts.governed_query import GovernedQueryResult, approve_query_result, capture_live_llm_query_evidence
from skill_scripts.sql_router import RoutingOptions


def _bundle() -> dict[str, list[dict[str, str]]]:
    return {
        "modules": [{"ModuleID": "ACT", "ModuleName": "會計總帳管理系統"}],
        "tables": [
            {"DB": "VPIC1.dbo.", "TableID": "ACTMK", "TableName": "科目/部門預算單身檔", "TableNameViet": "", "ModuleID": "ACT"},
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
        self.calls: list[str] = []

    def execute_readonly(self, sql: str) -> list[dict[str, object]]:
        self.calls.append(sql)
        return [{"MK002": "2026", "MK006": 1000.0}]

    def health_check(self) -> tuple[bool, str]:
        return True, "OK"


class _FakePublishedDashboardDataSource:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def read_published_dashboard(self, published: PublishedDashboard, *, reason: str) -> dict[str, object]:
        _ = published
        self.calls.append(reason)
        return {"rows": [{"MK002": "2026", "MK006": 1000.0}], "reason": reason}


ChartPayload = dict[str, object]


class _RunGovernedQuery(Protocol):
    def __call__(
        self,
        prompt: str,
        bundle: dict[str, list[dict[str, str]]],
        options: RoutingOptions,
        db_client: _FakeDbClient,
        sample_rows_limit: int = 5,
    ) -> GovernedQueryResult: ...


def test_cli_target_case_covers_prompt_to_published_dashboard_journey(monkeypatch: MonkeyPatch) -> None:
    run_governed_query = cast(_RunGovernedQuery, governed_query_module.run_governed_query)
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
    query_result: GovernedQueryResult = run_governed_query(
        prompt="查詢2026年的工程預算明細",
        bundle=_bundle(),
        options=RoutingOptions(
            mode="llm-first",
            llm_provider="mock",
            llm_model="mock",
            min_confidence=0.5,
            execution_expectation=ExecutionExpectation(required_columns=["MK002", "MK006"], min_rows=1),
        ),
        db_client=_FakeDbClient(),
    )

    chart_payload: ChartPayload = {
        "chart_type": "bar",
        "title": "2026 Budget",
        "x_field": "MK002",
        "y_field": "MK006",
        "number_format": {"field": "MK006", "style": "currency", "currency": "TWD"},
    }
    try:
        _ = create_dashboard_chart_draft(query_result, chart_payload)
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "QUERY_RESULT_NOT_APPROVED" in str(exc)

    approved_query = approve_query_result(query_result)
    chart_draft = create_dashboard_chart_draft(approved_query, chart_payload)
    canvas = DashboardCanvas(columns=12, rows=8)
    _ = canvas.add_chart("budget", chart_draft, x=0, y=0, w=6, h=4)
    _ = canvas.move_chart("budget", x=3, y=1)
    _ = canvas.resize_chart("budget", w=7, h=4)

    template = select_design_template("soft_operations")
    draft = DashboardDraft(
        dashboard_id="dashboard-ac17",
        canvas_payload=canvas.to_payload(),
        template_selection=template,
    )
    preview = preview_dashboard_draft(draft)
    assert preview["template"] == template.to_payload()
    assert preview["canvas"] == {
        "columns": 12,
        "rows": 8,
        "items": [
            {
                "chart_id": "budget",
                "x": 3,
                "y": 1,
                "w": 7,
                "h": 4,
                "chart": {
                    "chart_type": "bar",
                    "title": "2026 Budget",
                    "x_field": "MK002",
                    "y_field": "MK006",
                    "number_format": {"field": "MK006", "style": "currency", "currency": "TWD"},
                },
            }
        ],
    }

    try:
        _ = publish_dashboard(draft)
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "DASHBOARD_FINAL_APPROVAL_REQUIRED" in str(exc)

    published = publish_dashboard(approve_dashboard_draft(draft, approver="analyst-1"))
    link = create_published_dashboard_link(published)
    data_source = _FakePublishedDashboardDataSource()

    rendered = render_published_dashboard_link(
        token=link.token,
        links=[link],
        dashboards=[published],
        data_source=data_source,
        now="2026-05-07T00:00:00+00:00",
    )
    assert rendered["status"] == "ok"
    assert rendered["view_only"] is True
    assert rendered["authoring_actions"] == []

    refreshed = refresh_published_dashboard_view(
        rendered,
        published=published,
        data_source=data_source,
        refresh_interval_seconds=300,
    )
    assert refreshed["refresh"] == {"status": "fresh", "interval_seconds": 300}
    assert data_source.calls == ["view", "refresh"]

    revoked = revoke_published_dashboard_link(link)
    denied = render_published_dashboard_link(
        token=revoked.token,
        links=[revoked],
        dashboards=[published],
        data_source=data_source,
        now="2026-05-07T00:00:00+00:00",
    )
    assert denied["status"] == "denied"
    assert denied["code"] == "LINK_TOKEN_REVOKED"
    assert denied["dashboard"] is None
    assert denied["data"] is None


def test_live_llm_governed_query_evidence_is_non_blocking_when_provider_unavailable() -> None:
    evidence = capture_live_llm_query_evidence(
        prompt="查詢2026年的工程預算明細",
        bundle=_bundle(),
        options=RoutingOptions(
            mode="llm-first",
            llm_provider="none",
            llm_model="none",
            min_confidence=0.5,
            execution_expectation=ExecutionExpectation(required_columns=["MK002", "MK006"], min_rows=1),
        ),
        db_client=_FakeDbClient(),
    )

    assert evidence == {
        "prompt": "查詢2026年的工程預算明細",
        "status": "failed",
        "failure_classification": "llm_availability",
        "blocking": False,
        "evidence_type": "live_llm_governed_query",
        "error_code": "LLM_PROVIDER_NOT_CONFIGURED",
    }

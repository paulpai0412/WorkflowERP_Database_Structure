from __future__ import annotations

from pathlib import Path

from skill_scripts.report_catalog import (
    build_report_selection_payload,
    list_report_designs,
    list_report_types,
)


def test_report_catalog_contains_required_report_types():
    names = {item["name"] for item in list_report_types()}

    assert {
        "明細查詢表",
        "彙總統計表",
        "趨勢分析表",
        "比較分析表",
        "異常稽核表",
        "管理摘要",
        "完整分析報告",
    }.issubset(names)


def test_report_designs_are_loadable_markdown():
    designs = list_report_designs()

    ids = {design["id"] for design in designs}
    assert {
        "executive-summary",
        "financial-control",
        "operations-review",
        "exception-audit",
        "trend-briefing",
        "detail-ledger",
    }.issubset(ids)
    assert all(Path(design["path"]).suffix == ".md" for design in designs)


def test_each_design_declares_required_sections():
    designs = list_report_designs()

    for design in designs:
        assert design["name"]
        assert design["required_sections"]
        for key in [
            "best_for",
            "visual_policy",
            "table_policy",
            "analysis_policy",
            "recommendation_policy",
            "react_component_hints",
            "validator_checklist",
        ]:
            assert design[key], design["id"]


def test_default_options_include_chart_table_analysis_recommendation_flags():
    payload = build_report_selection_payload()

    assert payload["default_options"] == {
        "include_chart": True,
        "include_table": True,
        "include_analysis": True,
        "include_recommendations": True,
    }
    assert any(item["name"] == "管理摘要" for item in payload["report_types"])
    assert any(item["id"] == "financial-control" for item in payload["report_designs"])

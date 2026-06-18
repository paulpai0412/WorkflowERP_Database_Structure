from __future__ import annotations

from skill_scripts.dynamic_design_brief import build_design_brief, validate_design_brief


def _expense_package(columns: list[str] | None = None) -> dict[str, object]:
    return {
        "schema_version": "wferp.report-package.v1",
        "prompt": "查詢 2026 年費用明細",
        "catalog_guardrail": "financial-control",
        "report_type": "管理摘要",
        "data_profile": {
            "row_count": 12,
            "columns": columns or ["department", "expense_amount", "budget_amount"],
        },
        "datasets": {"columns": columns or ["department", "expense_amount", "budget_amount"]},
        "aggregates": {"expense_amount_sum": 42000},
    }


def test_financial_control_expense_package_uses_default_chart_and_table_recipes():
    brief = build_design_brief(_expense_package())

    assert list(brief) == [
        "schema_version",
        "report_intent",
        "catalog_guardrail",
        "target_audience",
        "layout_recipe",
        "chart_recipe",
        "table_recipe",
        "interaction_recipe",
        "visual_direction",
        "embedded_data_policy",
    ]
    assert brief["schema_version"] == "wferp.design-brief.v1"
    assert brief["layout_recipe"]["mode"] == "kpi-first-dashboard"
    assert [chart["type"] for chart in brief["chart_recipe"]] == ["combo", "stacked-bar", "bar"]
    assert all({"id", "type", "purpose"}.issubset(chart) for chart in brief["chart_recipe"])
    assert isinstance(brief["table_recipe"], list)
    assert brief["table_recipe"][0]["id"]
    assert brief["table_recipe"][0]["type"] == "data-table"
    assert brief["table_recipe"][0]["features"] == [
        "filter",
        "sort",
        "drilldown",
        "column_visibility",
    ]
    assert brief["embedded_data_policy"]["mode"] == "smart-tiered"
    assert validate_design_brief(brief)["valid"] is True


def test_period_column_adds_line_chart_before_default_expense_charts():
    brief = build_design_brief(_expense_package(["month", "department", "expense_amount"]))

    assert [chart["type"] for chart in brief["chart_recipe"]] == [
        "line",
        "combo",
        "stacked-bar",
        "bar",
    ]
    assert brief["chart_recipe"][0]["id"]
    assert brief["chart_recipe"][0]["purpose"]
    assert validate_design_brief(brief)["valid"] is True


def test_validate_design_brief_rejects_chart_without_purpose():
    brief = build_design_brief(
        _expense_package(),
        user_overrides={"chart_recipe": [{"type": "combo"}]},
    )

    result = validate_design_brief(brief)
    assert result["valid"] is False
    assert "chart_recipe[0].purpose" in result["errors"]


def test_validate_design_brief_rejects_empty_required_top_level_value():
    brief = build_design_brief(_expense_package())
    brief["report_intent"] = {}

    result = validate_design_brief(brief)

    assert result["valid"] is False
    assert "report_intent" in result["errors"]


def test_validate_design_brief_rejects_wrong_schema_version():
    brief = build_design_brief(_expense_package(), user_overrides={"schema_version": "bad"})

    result = validate_design_brief(brief)

    assert result["valid"] is False
    assert "schema_version" in result["errors"]


def test_validate_design_brief_rejects_non_mapping_layout_recipe():
    brief = build_design_brief(_expense_package(), user_overrides={"layout_recipe": "bad"})

    result = validate_design_brief(brief)

    assert result["valid"] is False
    assert "layout_recipe" in result["errors"]


def test_validate_design_brief_rejects_non_string_catalog_guardrail():
    brief = build_design_brief(_expense_package(), user_overrides={"catalog_guardrail": []})

    result = validate_design_brief(brief)

    assert result["valid"] is False
    assert "catalog_guardrail" in result["errors"]

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


SCHEMA_VERSION = "wferp.design-brief.v1"
REQUIRED_TOP_LEVEL_KEYS = [
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
TABLE_FEATURES = ["filter", "sort", "drilldown", "column_visibility"]
PERIOD_COLUMN_MARKERS = ("period", "month", "date", "月份", "期間", "日期", "年月")


def _package_columns(package: Mapping[str, Any]) -> list[str]:
    data_profile = package.get("data_profile")
    if isinstance(data_profile, Mapping) and isinstance(data_profile.get("columns"), list):
        return [str(column) for column in data_profile["columns"]]

    datasets = package.get("datasets")
    if isinstance(datasets, Mapping) and isinstance(datasets.get("columns"), list):
        return [str(column) for column in datasets["columns"]]

    return []


def _has_period_column(columns: list[str]) -> bool:
    for column in columns:
        normalized = column.lower()
        if any(marker in normalized for marker in PERIOD_COLUMN_MARKERS):
            return True
    return False


def _chart_recipe(package: Mapping[str, Any]) -> list[dict[str, str]]:
    charts = [
        {
            "id": "expense-budget-variance",
            "type": "combo",
            "purpose": "Compare actual expense, budget, and variance in one control view.",
        },
        {
            "id": "expense-composition",
            "type": "stacked-bar",
            "purpose": "Show expense composition across departments or categories.",
        },
        {
            "id": "expense-driver-ranking",
            "type": "bar",
            "purpose": "Rank the largest expense drivers for exception review.",
        },
    ]
    if _has_period_column(_package_columns(package)):
        return [
            {
                "id": "period-expense-trend",
                "type": "line",
                "purpose": "Reveal period trend and month-over-month movement.",
            },
            *charts,
        ]
    return charts


def _merge_overrides(base: dict[str, Any], overrides: Mapping[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), dict):
            merged[key] = _merge_overrides(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def build_design_brief(
    package: Mapping[str, Any],
    *,
    user_overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    package_catalog_guardrail = package.get("catalog_guardrail")
    if isinstance(package_catalog_guardrail, str):
        catalog_guardrail: Any = package_catalog_guardrail.strip() or "financial-control"
    elif package_catalog_guardrail is None:
        catalog_guardrail = "financial-control"
    else:
        catalog_guardrail = package_catalog_guardrail
    prompt = str(package.get("prompt") or "")
    report_type = str(package.get("report_type") or "管理摘要")
    row_count = 0
    data_profile = package.get("data_profile")
    if isinstance(data_profile, Mapping) and isinstance(data_profile.get("row_count"), int):
        row_count = data_profile["row_count"]

    brief = {
        "schema_version": SCHEMA_VERSION,
        "report_intent": {
            "prompt": prompt,
            "report_type": report_type,
            "primary_goal": "Expose financial-control exceptions and decision-ready expense signals.",
        },
        "catalog_guardrail": catalog_guardrail,
        "target_audience": {
            "role": "finance controller",
            "needs": ["budget variance review", "expense concentration review", "audit follow-up"],
        },
        "layout_recipe": {
            "mode": "kpi-first-dashboard",
            "sections": [
                "executive-summary",
                "kpi-overview",
                "expense-trend",
                "exception-review",
                "data-table",
            ],
            "density": "analysis-first",
        },
        "chart_recipe": _chart_recipe(package),
        "table_recipe": [
            {
                "id": "expense-detail-table",
                "type": "data-table",
                "features": TABLE_FEATURES,
                "row_count": row_count,
            }
        ],
        "interaction_recipe": {
            "filters": _package_columns(package),
            "drilldowns": ["department", "category", "document"],
        },
        "visual_direction": {
            "tone": "quiet financial operations dashboard",
            "emphasis": ["variance", "outliers", "approval-ready summary"],
        },
        "embedded_data_policy": {
            "mode": "smart-tiered",
            "summary_threshold_rows": 5000,
        },
    }
    if user_overrides:
        brief = _merge_overrides(brief, user_overrides)
    return {key: brief[key] for key in REQUIRED_TOP_LEVEL_KEYS if key in brief}


def validate_design_brief(brief: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    for key in REQUIRED_TOP_LEVEL_KEYS:
        if not brief.get(key):
            errors.append(key)

    if brief.get("schema_version") != SCHEMA_VERSION and "schema_version" not in errors:
        errors.append("schema_version")

    catalog_guardrail = brief.get("catalog_guardrail")
    if (
        (not isinstance(catalog_guardrail, str) or not catalog_guardrail.strip())
        and "catalog_guardrail" not in errors
    ):
        errors.append("catalog_guardrail")

    for key in [
        "report_intent",
        "target_audience",
        "layout_recipe",
        "interaction_recipe",
        "visual_direction",
        "embedded_data_policy",
    ]:
        if key not in errors and not isinstance(brief.get(key), Mapping):
            errors.append(key)

    chart_recipe = brief.get("chart_recipe")
    if not isinstance(chart_recipe, list):
        errors.append("chart_recipe")
    else:
        for index, chart in enumerate(chart_recipe):
            if not isinstance(chart, Mapping):
                errors.append(f"chart_recipe[{index}]")
                continue
            chart_id = chart.get("id")
            if not isinstance(chart_id, str) or not chart_id.strip():
                errors.append(f"chart_recipe[{index}].id")
            chart_type = chart.get("type")
            if not isinstance(chart_type, str) or not chart_type.strip():
                errors.append(f"chart_recipe[{index}].type")
            purpose = chart.get("purpose")
            if not isinstance(purpose, str) or not purpose.strip():
                errors.append(f"chart_recipe[{index}].purpose")

    table_recipe = brief.get("table_recipe")
    if not isinstance(table_recipe, list):
        errors.append("table_recipe")
    else:
        for index, table in enumerate(table_recipe):
            if not isinstance(table, Mapping):
                errors.append(f"table_recipe[{index}]")
                continue
            table_id = table.get("id")
            if not isinstance(table_id, str) or not table_id.strip():
                errors.append(f"table_recipe[{index}].id")
            table_type = table.get("type")
            if not isinstance(table_type, str) or not table_type.strip():
                errors.append(f"table_recipe[{index}].type")
            if table.get("features") != TABLE_FEATURES:
                errors.append(f"table_recipe[{index}].features")

    embedded_data_policy = brief.get("embedded_data_policy")
    mode = embedded_data_policy.get("mode") if isinstance(embedded_data_policy, Mapping) else None
    if mode != "smart-tiered":
        errors.append("embedded_data_policy.mode")

    return {"valid": not errors, "errors": errors}

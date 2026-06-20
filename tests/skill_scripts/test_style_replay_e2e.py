from __future__ import annotations

from skill_scripts.dynamic_design_brief import build_design_brief
from skill_scripts.style_replay import apply_style_capsule
from skill_scripts.style_replay import build_style_capsule
from skill_scripts.style_replay import detect_replay_adjustments


def _package(prompt: str, total_amount: int, columns: list[str]) -> dict:
    return {
        "package_id": prompt,
        "prompt": prompt,
        "catalog_guardrail": "financial-control",
        "data_profile": {"row_count": 2, "columns": columns},
        "aggregates": {
            "total_amount": total_amount,
            "total_budget": 100000,
            "variance_amount": total_amount - 100000,
        },
    }


def test_style_replay_generates_new_report_with_same_style_and_new_data():
    first_package = _package("查詢 2026 Q1 費用", 120000, ["department", "amount", "budget_amount"])
    first_brief = build_design_brief(first_package)
    capsule = build_style_capsule(first_brief)

    replay = apply_style_capsule(capsule, new_prompt="改查 2027 Q1 行政部費用")
    second_package = _package(replay["prompt"], 88000, ["department", "amount", "budget_amount"])

    assert replay["style_fingerprint"] == capsule["style_fingerprint"]
    assert second_package["prompt"] != first_package["prompt"]
    assert second_package["aggregates"]["total_amount"] != first_package["aggregates"]["total_amount"]
    assert second_package["aggregates"]["variance_amount"] == -12000


def test_style_replay_requires_design_adjustment_checkpoint_when_chart_columns_missing():
    trend_package = _package("查詢月趨勢", 120000, ["period", "amount"])
    trend_brief = build_design_brief(trend_package)
    trend_brief["chart_recipe"] = [
        {"id": "period_trend", "type": "line", "purpose": "月趨勢", "required_columns": ["period"]}
    ]
    capsule = build_style_capsule(trend_brief)

    result = detect_replay_adjustments(capsule, new_columns=["department", "amount"])

    assert result["requires_checkpoint"] is True
    assert result["incompatible_charts"] == ["period_trend"]

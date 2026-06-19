from __future__ import annotations

from skill_scripts.style_replay import apply_style_capsule
from skill_scripts.style_replay import build_style_capsule
from skill_scripts.style_replay import detect_replay_adjustments


def _brief() -> dict:
    return {
        "catalog_guardrail": "trend-briefing",
        "layout_recipe": {"mode": "trend-first", "sections": ["趨勢摘要"]},
        "chart_recipe": [
            {
                "id": "period_trend",
                "type": "line",
                "purpose": "期間趨勢",
                "required_columns": ["period"],
            }
        ],
        "table_recipe": [{"id": "period_table", "type": "interactive-detail", "features": ["filter"]}],
        "interaction_recipe": {"cross_filter": True},
        "visual_direction": {"density": "balanced", "tone": "趨勢解讀"},
        "embedded_data_policy": {"mode": "smart-tiered"},
    }


def test_style_capsule_has_stable_fingerprint():
    first = build_style_capsule(_brief())
    second = build_style_capsule(_brief())

    assert first["style_fingerprint"] == second["style_fingerprint"]
    assert first["catalog_guardrail"] == "trend-briefing"
    assert first["style_version"] == "wferp.style-capsule.v1"


def test_style_capsule_excludes_query_result_row_count_from_table_recipe():
    first_brief = _brief()
    second_brief = _brief()
    first_brief["table_recipe"][0]["row_count"] = 25
    second_brief["table_recipe"][0]["row_count"] = 5000

    first = build_style_capsule(first_brief)
    second = build_style_capsule(second_brief)

    assert "row_count" not in first["table_recipe"][0]
    assert first["style_fingerprint"] == second["style_fingerprint"]


def test_apply_style_capsule_preserves_layout_and_uses_new_prompt():
    capsule = build_style_capsule(_brief())
    replayed = apply_style_capsule(capsule, new_prompt="改查 2027 Q1 行政部費用")

    assert replayed["prompt"] == "改查 2027 Q1 行政部費用"
    assert replayed["layout_recipe"] == capsule["layout_recipe"]
    assert replayed["style_fingerprint"] == capsule["style_fingerprint"]


def test_detect_replay_adjustments_requires_checkpoint_for_missing_columns():
    capsule = build_style_capsule(_brief())
    result = detect_replay_adjustments(capsule, new_columns=["department", "amount"])

    assert result["requires_checkpoint"] is True
    assert result["incompatible_charts"] == ["period_trend"]
    assert result["suggested_replacements"][0]["type"] == "bar"


def test_detect_replay_adjustments_allows_compatible_columns():
    capsule = build_style_capsule(_brief())
    result = detect_replay_adjustments(capsule, new_columns=["period", "amount"])

    assert result == {
        "requires_checkpoint": False,
        "incompatible_charts": [],
        "suggested_replacements": [],
    }

from __future__ import annotations

import json
from pathlib import Path

from skill_scripts.report_catalog import (
    build_report_selection_payload,
    get_report_design_defaults,
    load_report_design_catalog,
    list_report_designs,
    list_report_types,
)


REQUIRED_PROFILE_IDS = [
    "financial-control",
    "executive-summary",
    "detail-ledger",
    "exception-audit",
    "operations-review",
    "trend-briefing",
]


REQUIRED_PRODUCT_KEYS = {
    "id",
    "label",
    "best_for",
    "required_sections",
    "default_components",
    "chart_policy",
    "table_policy",
    "kpi_policy",
    "tone",
    "layout_density",
    "validator_focus",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


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
    assert ids == set(REQUIRED_PROFILE_IDS)
    assert all(Path(design["path"]).suffix == ".md" for design in designs)


def test_design_catalog_requires_all_product_metadata():
    catalog = load_report_design_catalog(repo_root() / "report_designs")

    assert catalog.profile_ids == REQUIRED_PROFILE_IDS
    financial = catalog.get_profile("financial-control")
    assert set(financial) >= REQUIRED_PRODUCT_KEYS
    assert financial["label"] == "財務控制"
    assert financial["best_for"] == ["費用分析", "預算差異", "異常控管"]
    assert financial["required_sections"] == [
        "executive-summary",
        "kpi-overview",
        "trend",
        "detail-table",
        "recommendations",
    ]
    assert financial["default_components"] == [
        "KpiGrid",
        "ChartBlock",
        "DataTable",
        "InsightBlock",
        "RecommendationList",
    ]
    assert financial["chart_policy"] == {"preferred": ["bar", "stacked-bar", "combo"], "avoid": ["pie"]}
    assert financial["table_policy"] == {
        "density": "compact",
        "summary_rows": True,
        "conditional_formatting": True,
    }
    assert financial["kpi_policy"] == {"include_variance": True, "include_budget_ratio": True}
    assert financial["tone"] == "管理控制、明確、可追責"
    assert financial["layout_density"] == "dense"
    assert financial["validator_focus"] == [
        "aggregate_consistency",
        "variance_explanation",
        "exception_visibility",
    ]


def test_each_design_declares_required_product_metadata():
    designs = list_report_designs()

    for design in designs:
        assert set(design) >= REQUIRED_PRODUCT_KEYS
        for key in REQUIRED_PRODUCT_KEYS:
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


def test_selected_design_defaults_are_exposed_for_scaffold():
    defaults = get_report_design_defaults("financial-control")

    assert defaults["id"] == "financial-control"
    assert defaults["sections"] == [
        "executive-summary",
        "kpi-overview",
        "trend",
        "detail-table",
        "recommendations",
    ]
    assert defaults["components"] == [
        "KpiGrid",
        "ChartBlock",
        "DataTable",
        "InsightBlock",
        "RecommendationList",
    ]
    assert defaults["chart_policy"]["preferred"] == ["bar", "stacked-bar", "combo"]
    assert defaults["table_policy"]["summary_rows"] is True
    assert defaults["kpi_policy"]["include_variance"] is True


def _write_profile(root: Path, profile: dict[str, object]) -> None:
    lines = ["---"]
    for key, value in profile.items():
        lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    lines.extend(["---", "", f"# {profile['label']}"])
    (root / f"{profile['id']}.md").write_text("\n".join(lines), encoding="utf-8")


def _base_profile(profile_id: str = "financial-control") -> dict[str, object]:
    return {
        "id": profile_id,
        "label": "財務控制",
        "best_for": ["費用分析"],
        "required_sections": ["executive-summary"],
        "default_components": ["DataTable"],
        "chart_policy": {"preferred": ["bar"], "avoid": []},
        "table_policy": {"density": "compact", "summary_rows": True, "conditional_formatting": True},
        "kpi_policy": {"include_variance": True, "include_budget_ratio": True},
        "tone": "管理控制",
        "layout_density": "dense",
        "validator_focus": ["aggregate_consistency"],
    }


def _write_complete_index(root: Path) -> None:
    root.joinpath("index.json").write_text(json.dumps(REQUIRED_PROFILE_IDS), encoding="utf-8")


def _write_complete_profiles(root: Path, *, skip: set[str] | None = None) -> None:
    skipped = skip or set()
    for profile_id in REQUIRED_PROFILE_IDS:
        if profile_id in skipped:
            continue
        profile = _base_profile(profile_id)
        profile["label"] = profile_id
        _write_profile(root, profile)


def test_catalog_rejects_missing_profile_file(tmp_path):
    _write_complete_index(tmp_path)
    _write_complete_profiles(tmp_path, skip={"financial-control"})

    try:
        load_report_design_catalog(tmp_path)
    except ValueError as exc:
        assert "Missing report design profile file" in str(exc)
        assert "financial-control.md" in str(exc)
    else:
        raise AssertionError("Expected missing profile file to be rejected")


def test_catalog_rejects_profile_not_listed_in_index(tmp_path):
    _write_complete_index(tmp_path)
    _write_complete_profiles(tmp_path)
    _write_profile(tmp_path, _base_profile("rogue-design"))

    try:
        load_report_design_catalog(tmp_path)
    except ValueError as exc:
        assert "Profile file is not listed in index.json" in str(exc)
        assert "rogue-design.md" in str(exc)
    else:
        raise AssertionError("Expected unindexed profile to be rejected")


def test_catalog_rejects_unindexed_filename_even_with_indexed_profile_id(tmp_path):
    _write_complete_index(tmp_path)
    _write_complete_profiles(tmp_path)
    _write_profile(tmp_path, _base_profile("financial-control"))
    (tmp_path / "financial-control.md").replace(tmp_path / "rogue.md")
    _write_profile(tmp_path, _base_profile("financial-control"))

    try:
        load_report_design_catalog(tmp_path)
    except ValueError as exc:
        assert "Profile file is not listed in index.json" in str(exc)
        assert "rogue.md" in str(exc)
    else:
        raise AssertionError("Expected unindexed duplicate-id profile file to be rejected")


def test_catalog_rejects_profiles_missing_required_keys(tmp_path):
    _write_complete_index(tmp_path)
    _write_complete_profiles(tmp_path, skip={"financial-control"})
    profile = _base_profile("financial-control")
    del profile["validator_focus"]
    _write_profile(tmp_path, profile)

    try:
        load_report_design_catalog(tmp_path)
    except ValueError as exc:
        assert "missing metadata" in str(exc)
        assert "validator_focus" in str(exc)
    else:
        raise AssertionError("Expected missing required metadata to be rejected")

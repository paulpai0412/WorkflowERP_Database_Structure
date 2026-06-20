from skill_scripts.dashboard_canvas import DashboardCanvas, create_dashboard_chart_draft
from skill_scripts.design_template_catalog import (
    DesignTemplateSelection,
    apply_design_template_to_canvas_preview,
    list_design_template_options,
    select_design_template,
)
from skill_scripts.governed_query import GovernedQueryResult, QueryEvidence, approve_query_result


def _query_result() -> GovernedQueryResult:
    return GovernedQueryResult(
        evidence=QueryEvidence(
            prompt="查詢2026年月營收",
            sql="SELECT [month],[revenue] FROM [dbo].[SALES]",
            route="rule",
            route_reason="test",
            validation_status="OK",
            execution_status="OK",
            execution_timestamp="2026-05-07T00:00:00+00:00",
            returned_columns=["month", "revenue"],
            row_count=2,
            sample_rows=[
                {"month": "2026-01", "revenue": 1000.0},
                {"month": "2026-02", "revenue": 1500.0},
            ],
        )
    )


def _canvas() -> DashboardCanvas:
    canvas = DashboardCanvas(columns=12, rows=8)
    chart = create_dashboard_chart_draft(
        approve_query_result(_query_result()),
        {"chart_type": "bar", "title": "Monthly Revenue", "x_field": "month", "y_field": "revenue"},
    )
    _ = canvas.add_chart("revenue", chart, x=0, y=0, w=6, h=4)
    return canvas


def test_catalog_presents_deterministic_generic_design_template_options() -> None:
    first_payload = list_design_template_options()
    second_payload = list_design_template_options()

    assert first_payload == second_payload
    assert first_payload == {
        "templates": [
            {
                "template_id": "executive_contrast",
                "name": "Executive Contrast",
                "description": "High-contrast dashboard styling for dense operational reviews.",
                "preview_tokens": {"background": "#0f172a", "surface": "#1e293b", "accent": "#38bdf8"},
            },
            {
                "template_id": "soft_operations",
                "name": "Soft Operations",
                "description": "Light, spacious dashboard styling for day-to-day process monitoring.",
                "preview_tokens": {"background": "#f8fafc", "surface": "#ffffff", "accent": "#2563eb"},
            },
            {
                "template_id": "ledger_focus",
                "name": "Ledger Focus",
                "description": "Structured dashboard styling for finance and tabular control views.",
                "preview_tokens": {"background": "#f5f1e8", "surface": "#fffaf0", "accent": "#b45309"},
            },
        ]
    }


def test_catalog_options_do_not_use_source_brand_names_as_official_names() -> None:
    brand_names = {"apple", "stripe", "linear", "notion", "vercel", "shopify", "slack", "github", "voltagent"}

    for option in list_design_template_options()["templates"]:
        official_name = str(option["name"]).lower()
        assert all(brand_name not in official_name for brand_name in brand_names)


def test_allowed_design_template_can_be_selected_for_dashboard_preview() -> None:
    selection = select_design_template("soft_operations")
    preview = apply_design_template_to_canvas_preview(_canvas(), selection)

    assert isinstance(selection, DesignTemplateSelection)
    assert selection.to_payload() == {
        "template_id": "soft_operations",
        "name": "Soft Operations",
        "tokens": {"background": "#f8fafc", "surface": "#ffffff", "accent": "#2563eb", "text": "#0f172a"},
    }
    assert preview == {
        "template": selection.to_payload(),
        "canvas": {
            "columns": 12,
            "rows": 8,
            "items": [
                {
                    "chart_id": "revenue",
                    "x": 0,
                    "y": 0,
                    "w": 6,
                    "h": 4,
                    "chart": {"chart_type": "bar", "title": "Monthly Revenue", "x_field": "month", "y_field": "revenue"},
                }
            ],
        },
    }


def test_switching_design_templates_replaces_the_active_template() -> None:
    selection = select_design_template("executive_contrast")
    selection = select_design_template("ledger_focus", current_selection=selection)
    preview = apply_design_template_to_canvas_preview(_canvas(), selection)

    assert selection.template_id == "ledger_focus"
    assert preview["template"] == {
        "template_id": "ledger_focus",
        "name": "Ledger Focus",
        "tokens": {"background": "#f5f1e8", "surface": "#fffaf0", "accent": "#b45309", "text": "#292524"},
    }
    assert "executive_contrast" not in str(preview)


def test_invalid_design_template_selection_is_refused_with_clear_error() -> None:
    for template_id in ("", "stripe", "unknown_template"):
        try:
            _ = select_design_template(template_id)
            assert False, "expected RuntimeError"
        except RuntimeError as exc:
            assert f"DESIGN_TEMPLATE_NOT_ALLOWED:{template_id}" in str(exc)


def test_preview_refuses_unselected_or_invalid_design_templates() -> None:
    cases: list[object] = [None, object(), select_design_template("soft_operations").to_payload()]

    for selection in cases:
        try:
            _ = apply_design_template_to_canvas_preview(_canvas(), selection)
            assert False, "expected RuntimeError"
        except RuntimeError as exc:
            assert "DESIGN_TEMPLATE_SELECTION_REQUIRED" in str(exc)


def test_preview_canonicalizes_manually_constructed_design_template_selection() -> None:
    forged_selection = DesignTemplateSelection(
        template_id="soft_operations",
        name="Stripe",
        tokens={"background": "#000000", "surface": "#000000", "accent": "#000000", "text": "#000000"},
    )

    preview = apply_design_template_to_canvas_preview(_canvas(), forged_selection)

    assert preview["template"] == {
        "template_id": "soft_operations",
        "name": "Soft Operations",
        "tokens": {"background": "#f8fafc", "surface": "#ffffff", "accent": "#2563eb", "text": "#0f172a"},
    }

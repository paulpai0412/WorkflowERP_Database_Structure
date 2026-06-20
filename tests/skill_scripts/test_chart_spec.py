from skill_scripts.chart_spec import ChartSpec, author_chart_spec, render_chart_preview
from skill_scripts.governed_query import GovernedQueryResult, QueryEvidence, approve_query_result


ChartPayload = dict[str, object]


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
            returned_columns=["month", "revenue", "category"],
            row_count=2,
            sample_rows=[
                {"month": "2026-01", "revenue": 1000.0, "category": "A"},
                {"month": "2026-02", "revenue": 1500.0, "category": "B"},
            ],
        )
    )


def _numeric_query_result() -> GovernedQueryResult:
    return GovernedQueryResult(
        evidence=QueryEvidence(
            prompt="查詢營收排序",
            sql="SELECT [month],[revenue] FROM [dbo].[SALES]",
            route="rule",
            route_reason="test",
            validation_status="OK",
            execution_status="OK",
            execution_timestamp="2026-05-07T00:00:00+00:00",
            returned_columns=["month", "revenue"],
            row_count=2,
            sample_rows=[
                {"month": "2026-01", "revenue": 9.0},
                {"month": "2026-02", "revenue": 100.0},
            ],
        )
    )


def test_table_chart_spec_requires_approved_query_result() -> None:
    payload: ChartPayload = {
        "chart_type": "table",
        "title": "Monthly Revenue",
        "fields": ["month", "revenue", "category"],
    }

    try:
        _ = author_chart_spec(_query_result(), payload)
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "QUERY_RESULT_NOT_APPROVED" in str(exc)

    spec = author_chart_spec(approve_query_result(_query_result()), payload)
    preview = render_chart_preview(approve_query_result(_query_result()), spec)

    assert spec.chart_type == "table"
    assert preview["chart_type"] == "table"
    assert preview["columns"] == ["month", "revenue", "category"]
    assert preview["rows"] == [
        {"month": "2026-01", "revenue": 1000.0, "category": "A"},
        {"month": "2026-02", "revenue": 1500.0, "category": "B"},
    ]


def test_bar_chart_spec_validates_mappings_sorting_color_and_formatting() -> None:
    approved = approve_query_result(_query_result())

    spec = author_chart_spec(
        approved,
        {
            "chart_type": "bar",
            "title": "Monthly Revenue",
            "x_field": "month",
            "y_field": "revenue",
            "series_field": "month",
            "sort": {"field": "revenue", "direction": "desc"},
            "color": "#3366ff",
            "number_format": {"field": "revenue", "style": "currency", "currency": "TWD"},
            "date_format": {"field": "month", "format": "YYYY-MM"},
        },
    )
    preview = render_chart_preview(approved, spec)

    assert spec.chart_type == "bar"
    assert preview["x_field"] == "month"
    assert preview["y_field"] == "revenue"
    assert preview["series_field"] == "month"
    assert preview["data"] == [
        {"x": "2026-02", "y": 1500.0, "series": "2026-02"},
        {"x": "2026-01", "y": 1000.0, "series": "2026-01"},
    ]


def test_invalid_mappings_are_rejected_with_clear_errors() -> None:
    approved = approve_query_result(_query_result())

    cases: list[tuple[ChartPayload, str]] = [
        ({"chart_type": "pie", "title": "Bad"}, "UNSUPPORTED_CHART_TYPE:pie"),
        ({"chart_type": "bar", "title": "Bad", "y_field": "revenue"}, "X_FIELD_REQUIRED"),
        ({"chart_type": "bar", "title": "Bad", "x_field": "month", "y_field": "bad"}, "UNSUPPORTED_FIELD:bad"),
        (
            {"chart_type": "bar", "title": "Bad", "x_field": "month", "y_field": "revenue", "sort": {"field": "month", "direction": "sideways"}},
            "INVALID_SORT_DIRECTION:sideways",
        ),
        (
            {"chart_type": "bar", "title": "Bad", "x_field": "month", "y_field": "revenue", "color": "blue"},
            "INVALID_COLOR:blue",
        ),
        (
            {
                "chart_type": "bar",
                "title": "Bad",
                "x_field": "month",
                "y_field": "revenue",
                "number_format": {"field": "month", "style": "currency"},
            },
            "NUMBER_FORMAT_FIELD_NOT_NUMERIC:month",
        ),
    ]

    for payload, expected in cases:
        try:
            _ = author_chart_spec(approved, payload)
            assert False, "expected RuntimeError"
        except RuntimeError as exc:
            assert expected in str(exc)


def test_kpi_card_spec_renders_single_metric_preview() -> None:
    approved = approve_query_result(_query_result())

    spec = author_chart_spec(
        approved,
        {
            "chart_type": "kpi_card",
            "title": "Latest Revenue",
            "value_field": "revenue",
            "label_field": "month",
            "sort": {"field": "month", "direction": "desc"},
            "color": "#00aa66",
            "number_format": {"field": "revenue", "style": "number"},
        },
    )
    preview = render_chart_preview(approved, spec)

    assert preview == {
        "chart_type": "kpi_card",
        "title": "Latest Revenue",
        "value_field": "revenue",
        "label_field": "month",
        "color": "#00aa66",
        "number_format": {"field": "revenue", "style": "number"},
        "value": 1500.0,
        "label": "2026-02",
    }


def test_line_chart_spec_renders_ordered_series_preview() -> None:
    approved = approve_query_result(_query_result())

    spec = author_chart_spec(
        approved,
        {
            "chart_type": "line",
            "title": "Revenue Trend",
            "x_field": "month",
            "y_field": "revenue",
            "sort": {"field": "month", "direction": "asc"},
            "color": "#6633ff",
            "date_format": {"field": "month", "format": "YYYY-MM"},
        },
    )
    preview = render_chart_preview(approved, spec)

    assert preview["chart_type"] == "line"
    assert preview["data"] == [
        {"x": "2026-01", "y": 1000.0, "series": None},
        {"x": "2026-02", "y": 1500.0, "series": None},
    ]


def test_chart_spec_rejects_missing_kpi_required_fields() -> None:
    approved = approve_query_result(_query_result())

    try:
        _ = author_chart_spec(approved, {"chart_type": "kpi_card", "title": "Bad"})
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "VALUE_FIELD_REQUIRED" in str(exc)


def test_chart_spec_can_round_trip_as_form_payload_dict() -> None:
    approved = approve_query_result(_query_result())

    spec = author_chart_spec(
        approved,
        {
            "chart_type": "table",
            "title": "Monthly Revenue",
            "fields": ["month", "revenue"],
            "sort": {"field": "month", "direction": "asc"},
            "color": "#112233",
            "date_format": {"field": "month", "format": "YYYY-MM"},
        },
    )

    assert spec.to_payload() == {
        "chart_type": "table",
        "title": "Monthly Revenue",
        "fields": ["month", "revenue"],
        "sort": {"field": "month", "direction": "asc"},
        "color": "#112233",
        "date_format": {"field": "month", "format": "YYYY-MM"},
    }


def test_render_preview_revalidates_public_chart_spec_objects() -> None:
    approved = approve_query_result(_query_result())

    try:
        _ = render_chart_preview(
            approved,
            ChartSpec(chart_type="bar", title="Bad", x_field="month", y_field="missing"),
        )
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "UNSUPPORTED_FIELD:missing" in str(exc)

    try:
        _ = render_chart_preview(approved, ChartSpec(chart_type="pie", title="Bad"))
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "UNSUPPORTED_CHART_TYPE:pie" in str(exc)


def test_render_preview_sorts_numeric_values_by_number() -> None:
    approved = approve_query_result(_numeric_query_result())
    spec = author_chart_spec(
        approved,
        {
            "chart_type": "bar",
            "title": "Revenue by Month",
            "x_field": "month",
            "y_field": "revenue",
            "sort": {"field": "revenue", "direction": "desc"},
        },
    )

    preview = render_chart_preview(approved, spec)

    assert preview["data"] == [
        {"x": "2026-02", "y": 100.0, "series": None},
        {"x": "2026-01", "y": 9.0, "series": None},
    ]

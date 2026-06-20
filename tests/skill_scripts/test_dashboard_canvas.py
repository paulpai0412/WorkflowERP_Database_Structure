from skill_scripts.chart_spec import author_chart_spec
from skill_scripts.dashboard_canvas import DashboardCanvas, DashboardChartDraft, create_dashboard_chart_draft, load_dashboard_canvas
from skill_scripts.governed_query import GovernedQueryResult, QueryEvidence, approve_query_result
from typing import cast


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


def _bar_chart(title: str = "Monthly Revenue"):
    return author_chart_spec(
        approve_query_result(_query_result()),
        {
            "chart_type": "bar",
            "title": title,
            "x_field": "month",
            "y_field": "revenue",
        },
    )


def _bar_chart_draft(title: str = "Monthly Revenue"):
    return create_dashboard_chart_draft(
        approve_query_result(_query_result()),
        {
            "chart_type": "bar",
            "title": title,
            "x_field": "month",
            "y_field": "revenue",
        },
    )


def test_approved_chart_draft_can_be_added_to_dashboard_canvas() -> None:
    canvas = DashboardCanvas(columns=12, rows=8)

    placed = canvas.add_chart("revenue", _bar_chart_draft(), x=0, y=0, w=6, h=4)

    assert placed.chart_id == "revenue"
    assert canvas.render_layout() == [
        {
            "chart_id": "revenue",
            "x": 0,
            "y": 0,
            "w": 6,
            "h": 4,
            "chart": {
                "chart_type": "bar",
                "title": "Monthly Revenue",
                "x_field": "month",
                "y_field": "revenue",
            },
        }
    ]


def test_canvas_rejects_invalid_chart_drafts_before_placement() -> None:
    canvas = DashboardCanvas(columns=12, rows=8)

    cases: list[object] = [object(), _bar_chart(), DashboardChartDraft(chart=_bar_chart(), preview={})]
    for invalid_draft in cases:
        try:
            _ = canvas.add_chart("bad", invalid_draft, x=0, y=0, w=6, h=4)
            assert False, "expected RuntimeError"
        except RuntimeError as exc:
            assert "INVALID_CHART_DRAFT" in str(exc)

    try:
        _ = create_dashboard_chart_draft(
            _query_result(),
            {
                "chart_type": "bar",
                "title": "Monthly Revenue",
                "x_field": "month",
                "y_field": "revenue",
            },
        )
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "QUERY_RESULT_NOT_APPROVED" in str(exc)


def test_chart_can_be_moved_and_resized_without_losing_identity() -> None:
    canvas = DashboardCanvas(columns=12, rows=8)
    _ = canvas.add_chart("revenue", _bar_chart_draft(), x=0, y=0, w=4, h=3)

    moved = canvas.move_chart("revenue", x=4, y=1)
    resized = canvas.resize_chart("revenue", w=5, h=4)

    assert moved.chart_id == "revenue"
    assert resized.chart_id == "revenue"
    assert canvas.render_layout()[0]["chart_id"] == "revenue"
    assert canvas.render_layout()[0]["x"] == 4
    assert canvas.render_layout()[0]["y"] == 1
    assert canvas.render_layout()[0]["w"] == 5
    assert canvas.render_layout()[0]["h"] == 4


def test_layout_persistence_round_trips_coordinates_dimensions_and_chart_payloads() -> None:
    canvas = DashboardCanvas(columns=12, rows=8)
    _ = canvas.add_chart("revenue", _bar_chart_draft("Revenue"), x=0, y=0, w=6, h=4)
    _ = canvas.add_chart("trend", _bar_chart_draft("Trend"), x=6, y=0, w=6, h=4)

    payload = canvas.to_payload()
    restored = load_dashboard_canvas(payload)

    assert payload == {
        "columns": 12,
        "rows": 8,
        "items": [
            {
                "chart_id": "revenue",
                "x": 0,
                "y": 0,
                "w": 6,
                "h": 4,
                "chart": {"chart_type": "bar", "title": "Revenue", "x_field": "month", "y_field": "revenue"},
            },
            {
                "chart_id": "trend",
                "x": 6,
                "y": 0,
                "w": 6,
                "h": 4,
                "chart": {"chart_type": "bar", "title": "Trend", "x_field": "month", "y_field": "revenue"},
            },
        ],
    }
    assert restored.render_layout() == canvas.render_layout()


def test_overlap_and_bounds_violations_are_rejected_deterministically() -> None:
    canvas = DashboardCanvas(columns=12, rows=8)
    _ = canvas.add_chart("revenue", _bar_chart_draft("Revenue"), x=0, y=0, w=6, h=4)

    cases = [
        lambda: canvas.add_chart("overlap", _bar_chart_draft("Overlap"), x=5, y=0, w=4, h=4),
        lambda: canvas.add_chart("bounds", _bar_chart_draft("Bounds"), x=10, y=0, w=4, h=4),
        lambda: canvas.move_chart("revenue", x=-1, y=0),
        lambda: canvas.resize_chart("revenue", w=13, h=4),
    ]
    expected_codes = [
        "DASHBOARD_CANVAS_OVERLAP:overlap:revenue",
        "DASHBOARD_CANVAS_OUT_OF_BOUNDS:bounds",
        "DASHBOARD_CANVAS_OUT_OF_BOUNDS:revenue",
        "DASHBOARD_CANVAS_OUT_OF_BOUNDS:revenue",
    ]

    for attempt, expected_code in zip(cases, expected_codes, strict=True):
        try:
            _ = attempt()
            assert False, "expected RuntimeError"
        except RuntimeError as exc:
            assert expected_code in str(exc)


def test_persisted_layout_replay_rejects_invalid_overlap_and_bounds_payloads() -> None:
    payload = {
        "columns": 12,
        "rows": 8,
        "items": [
            {"chart_id": "one", "x": 0, "y": 0, "w": 6, "h": 4, "chart": _bar_chart("One").to_payload()},
            {"chart_id": "two", "x": 5, "y": 0, "w": 6, "h": 4, "chart": _bar_chart("Two").to_payload()},
        ],
    }

    try:
        _ = load_dashboard_canvas(payload)
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "DASHBOARD_CANVAS_OVERLAP:two:one" in str(exc)


def test_canvas_rejects_fractional_grid_values() -> None:
    canvas = DashboardCanvas(columns=12, rows=8)

    cases = [
        lambda: DashboardCanvas(columns=cast(int, 12.5), rows=8),
        lambda: canvas.add_chart("fractional", _bar_chart_draft(), x=cast(int, 0.5), y=0, w=6, h=4),
        lambda: canvas.add_chart("string-fractional", _bar_chart_draft(), x=cast(int, cast(object, "0.5")), y=0, w=6, h=4),
        lambda: load_dashboard_canvas(
            {
                "columns": 12,
                "rows": 8,
                "items": [{"chart_id": "one", "x": 0.5, "y": 0, "w": 6, "h": 4, "chart": _bar_chart("One").to_payload()}],
            }
        ),
    ]

    for attempt in cases:
        try:
            _ = attempt()
            assert False, "expected RuntimeError"
        except RuntimeError as exc:
            assert "DASHBOARD_CANVAS_INVALID_PAYLOAD" in str(exc)


def test_persisted_layout_replay_rejects_malformed_chart_metadata() -> None:
    cases = [
        {"chart_type": "bar", "title": "Bad", "x_field": "month", "y_field": "revenue", "sort": {"field": "month", "direction": 1}},
        {"chart_type": "bar", "title": "Bad", "x_field": "month", "y_field": "revenue", "sort": {"field": "month", "direction": "sideways"}},
        {"chart_type": "bar", "title": "Bad", "x_field": "month", "y_field": "revenue", "number_format": {"field": "revenue", "unknown": "x"}},
        {"chart_type": "bar", "title": "Bad", "x_field": "month", "y_field": "revenue", "number_format": {"field": "revenue", "style": "bogus"}},
        {"chart_type": "bar", "title": "Bad", "x_field": "month", "y_field": "revenue", "date_format": "YYYY-MM"},
        {"chart_type": "bar", "title": "Bad", "x_field": "month", "y_field": "revenue", "date_format": {"field": "month", "format": "MM/DD"}},
        {"chart_type": "bar", "title": "Bad", "x_field": "month", "y_field": "revenue", "color": "blue"},
        {"chart_type": "bar ", "title": "Bad", "x_field": "month", "y_field": "revenue"},
        {"chart_type": "bar", "title": "Bad", "x_field": " month", "y_field": "revenue"},
        {"chart_type": "bar", "title": "Bad", "x_field": "month", "y_field": "revenue", "color": " #ff0000"},
    ]

    for chart_payload in cases:
        try:
            _ = load_dashboard_canvas(
                {
                    "columns": 12,
                    "rows": 8,
                    "items": [{"chart_id": "one", "x": 0, "y": 0, "w": 6, "h": 4, "chart": chart_payload}],
                }
            )
            assert False, "expected RuntimeError"
        except RuntimeError as exc:
            assert "INVALID_CHART_DRAFT" in str(exc)

from skill_scripts.dashboard_canvas import DashboardCanvas, create_dashboard_chart_draft, load_dashboard_canvas
from typing import cast

from skill_scripts.dashboard_publish import (
    DashboardDraft,
    PublishedDashboard,
    PublishedDashboardLink,
    create_published_dashboard_link,
    approve_dashboard_draft,
    mark_dashboard_data_meaning_changed,
    preview_dashboard_draft,
    publish_dashboard,
    reject_dashboard_draft,
    render_published_dashboard_link,
    refresh_published_dashboard_view,
    revoke_published_dashboard_link,
)
from skill_scripts.design_template_catalog import select_design_template
from skill_scripts.governed_query import GovernedQueryResult, QueryEvidence, approve_query_result


def _query_result(sql: str = "SELECT [month],[revenue] FROM [dbo].[SALES]") -> GovernedQueryResult:
    return GovernedQueryResult(
        evidence=QueryEvidence(
            prompt="查詢2026年月營收",
            sql=sql,
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


def _canvas(sql: str = "SELECT [month],[revenue] FROM [dbo].[SALES]") -> DashboardCanvas:
    canvas = DashboardCanvas(columns=12, rows=8)
    chart = create_dashboard_chart_draft(
        approve_query_result(_query_result(sql=sql)),
        {"chart_type": "bar", "title": "Monthly Revenue", "x_field": "month", "y_field": "revenue"},
    )
    _ = canvas.add_chart("revenue", chart, x=0, y=0, w=6, h=4)
    return canvas


def _draft(dashboard_id: str = "dashboard-1", sql: str = "SELECT [month],[revenue] FROM [dbo].[SALES]") -> DashboardDraft:
    return DashboardDraft(
        dashboard_id=dashboard_id,
        canvas_payload=_canvas(sql=sql).to_payload(),
        template_selection=select_design_template("soft_operations"),
    )


def _published() -> PublishedDashboard:
    return publish_dashboard(approve_dashboard_draft(_draft(), approver="analyst-1"))


class FakeReadOnlyDashboardDataSource:
    def __init__(self, *, fail_view: bool = False, fail_refresh: bool = False) -> None:
        self.fail_view: bool = fail_view
        self.fail_refresh: bool = fail_refresh
        self.calls: list[tuple[str, str, int]] = []

    def read_published_dashboard(self, published: PublishedDashboard, *, reason: str) -> dict[str, object]:
        self.calls.append((reason, published.dashboard_id, published.version))
        if reason == "view" and self.fail_view:
            raise RuntimeError("READ_ONLY_REPLICA_TIMEOUT")
        if reason == "refresh" and self.fail_refresh:
            raise RuntimeError("READ_ONLY_REPLICA_TIMEOUT")
        return {"rows": [{"month": "2026-01", "revenue": 1000}], "reason": reason}


def test_dashboard_draft_preview_includes_canvas_chart_specs_and_template() -> None:
    persisted_canvas = _canvas().to_payload()
    reloaded_canvas = load_dashboard_canvas(persisted_canvas)
    draft = DashboardDraft(
        dashboard_id="dashboard-1",
        canvas_payload=reloaded_canvas.to_payload(),
        template_selection=select_design_template("soft_operations"),
    )

    preview = preview_dashboard_draft(draft)

    assert preview == {
        "dashboard_id": "dashboard-1",
        "state": "draft",
        "template": {
            "template_id": "soft_operations",
            "name": "Soft Operations",
            "tokens": {"background": "#f8fafc", "surface": "#ffffff", "accent": "#2563eb", "text": "#0f172a"},
        },
        "canvas": persisted_canvas,
    }
    preview_canvas = cast(dict[str, object], preview["canvas"])
    preview_items = cast(list[dict[str, object]], preview_canvas["items"])
    assert preview_items[0]["chart"] == {"chart_type": "bar", "title": "Monthly Revenue", "x_field": "month", "y_field": "revenue"}


def test_published_dashboard_link_token_is_opaque_and_scoped_to_dashboard() -> None:
    published = _published()

    link = create_published_dashboard_link(published, expires_at="2026-05-08T00:00:00+00:00")

    assert link.dashboard_id == "dashboard-1"
    assert link.token != "dashboard-1"
    assert link.token != "dashboard-1:1"
    assert len(link.token) >= 32
    assert link.audit_events[-1] == {
        "event": "published_dashboard_link_created",
        "dashboard_id": "dashboard-1",
        "version": 1,
        "expires_at": "2026-05-08T00:00:00+00:00",
    }


def test_valid_published_dashboard_link_renders_view_only_without_authoring_controls() -> None:
    published = _published()
    link = create_published_dashboard_link(published, expires_at="2026-05-08T00:00:00+00:00")
    data_source = FakeReadOnlyDashboardDataSource()

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
    dashboard = cast(dict[str, object], rendered["dashboard"])
    assert dashboard["dashboard_id"] == "dashboard-1"
    assert dashboard["canvas"] == published.payload["canvas"]
    assert rendered["data"] == {"rows": [{"month": "2026-01", "revenue": 1000}], "reason": "view"}
    assert data_source.calls == [("view", "dashboard-1", 1)]


def test_initial_view_data_source_failure_returns_safe_failure_state() -> None:
    published = _published()
    link = create_published_dashboard_link(published, expires_at="2026-05-08T00:00:00+00:00")
    data_source = FakeReadOnlyDashboardDataSource(fail_view=True)

    rendered = render_published_dashboard_link(
        token=link.token,
        links=[link],
        dashboards=[published],
        data_source=data_source,
        now="2026-05-07T00:00:00+00:00",
    )

    assert rendered["status"] == "error"
    assert rendered["code"] == "DASHBOARD_VIEW_FAILED"
    assert rendered["view_only"] is True
    assert rendered["authoring_actions"] == []
    assert rendered["dashboard"] is None
    assert rendered["data"] is None
    events = cast(list[dict[str, object]], rendered["audit_events"])
    assert events[-1] == {
        "event": "published_dashboard_view_failed",
        "dashboard_id": "dashboard-1",
        "version": 1,
        "code": "DASHBOARD_VIEW_FAILED",
    }
    assert data_source.calls == [("view", "dashboard-1", 1)]


def test_malformed_link_expiration_is_denied_without_runtime_crash_or_payload_leak() -> None:
    published = _published()
    link = create_published_dashboard_link(published, expires_at="not-a-timestamp")
    data_source = FakeReadOnlyDashboardDataSource()

    rendered = render_published_dashboard_link(
        token=link.token,
        links=[link],
        dashboards=[published],
        data_source=data_source,
        now="2026-05-07T00:00:00+00:00",
    )

    assert rendered["status"] == "denied"
    assert rendered["code"] == "LINK_EXPIRATION_MALFORMED"
    assert rendered["dashboard"] is None
    assert rendered["data"] is None
    events = cast(list[dict[str, object]], rendered["audit_events"])
    assert events[-1]["event"] == "published_dashboard_link_denied_malformed_expiration"
    assert data_source.calls == []


def test_revoked_expired_malformed_and_unpublished_links_are_denied_without_payload_leak() -> None:
    published = _published()
    link = create_published_dashboard_link(published, expires_at="2026-05-08T00:00:00+00:00")
    revoked = revoke_published_dashboard_link(link)
    expired = create_published_dashboard_link(published, expires_at="2026-05-06T00:00:00+00:00")
    data_source = FakeReadOnlyDashboardDataSource()

    denial_cases: list[tuple[str, list[PublishedDashboardLink], str, str]] = [
        ("missing", [], "LINK_TOKEN_MALFORMED", "published_dashboard_link_malformed"),
        (revoked.token, [revoked], "LINK_TOKEN_REVOKED", "published_dashboard_link_denied_revoked"),
        (expired.token, [expired], "LINK_TOKEN_EXPIRED", "published_dashboard_link_denied_expired"),
        (link.token, [link], "PUBLISHED_DASHBOARD_NOT_AVAILABLE", "published_dashboard_link_denied_unpublished"),
    ]

    for token, links, code, event_name in denial_cases:
        rendered = render_published_dashboard_link(token=token, links=links, dashboards=[], data_source=data_source, now="2026-05-07T00:00:00+00:00")
        assert rendered["status"] == "denied"
        assert rendered["code"] == code
        assert rendered["dashboard"] is None
        assert rendered["data"] is None
        events = cast(list[dict[str, object]], rendered["audit_events"])
        assert events[-1]["event"] == event_name

    assert data_source.calls == []
    assert revoked.audit_events[-1]["event"] == "published_dashboard_link_revoked"


def test_published_dashboard_refresh_uses_read_only_source_with_bounded_interval() -> None:
    published = _published()
    link = create_published_dashboard_link(published)
    data_source = FakeReadOnlyDashboardDataSource()
    rendered = render_published_dashboard_link(token=link.token, links=[link], dashboards=[published], data_source=data_source, now="2026-05-07T00:00:00+00:00")

    refreshed = refresh_published_dashboard_view(rendered, published=published, data_source=data_source, refresh_interval_seconds=300)

    assert refreshed["status"] == "ok"
    assert refreshed["refresh"] == {"status": "fresh", "interval_seconds": 300}
    assert refreshed["data"] == {"rows": [{"month": "2026-01", "revenue": 1000}], "reason": "refresh"}
    assert data_source.calls == [("view", "dashboard-1", 1), ("refresh", "dashboard-1", 1)]


def test_refresh_policy_rejects_out_of_bounds_intervals_and_reports_safe_failure_state() -> None:
    published = _published()
    rendered: dict[str, object] = {"status": "ok", "data": {"rows": [{"month": "2026-01", "revenue": 1000}]}, "audit_events": []}

    for interval, code in [(59, "DASHBOARD_REFRESH_INTERVAL_TOO_FAST"), (3601, "DASHBOARD_REFRESH_INTERVAL_TOO_SLOW")]:
        try:
            _ = refresh_published_dashboard_view(rendered, published=published, data_source=FakeReadOnlyDashboardDataSource(), refresh_interval_seconds=interval)
            assert False, "expected RuntimeError"
        except RuntimeError as exc:
            assert code in str(exc)

    failed = refresh_published_dashboard_view(
        rendered,
        published=published,
        data_source=FakeReadOnlyDashboardDataSource(fail_refresh=True),
        refresh_interval_seconds=300,
    )

    assert failed["status"] == "ok"
    assert failed["data"] == {"rows": [{"month": "2026-01", "revenue": 1000}]}
    assert failed["refresh"] == {"status": "stale_error", "interval_seconds": 300, "code": "DASHBOARD_REFRESH_FAILED"}
    failed_events = cast(list[dict[str, object]], failed["audit_events"])
    assert failed_events[-1] == {
        "event": "published_dashboard_refresh_failed",
        "dashboard_id": "dashboard-1",
        "version": 1,
        "code": "DASHBOARD_REFRESH_FAILED",
    }


def test_dashboard_draft_requires_final_analyst_approval_before_publish() -> None:
    draft = _draft()

    try:
        _ = publish_dashboard(draft)
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "DASHBOARD_FINAL_APPROVAL_REQUIRED" in str(exc)

    approved = approve_dashboard_draft(draft, approver="analyst-1")
    published = publish_dashboard(approved)

    assert published.dashboard_id == "dashboard-1"
    assert published.version == 1
    assert published.payload["state"] == "published"
    assert published.audit_events[-1]["event"] == "dashboard_published"


def test_published_dashboard_version_is_immutable_after_draft_changes() -> None:
    approved = approve_dashboard_draft(_draft(), approver="analyst-1")
    published = publish_dashboard(approved)
    original_payload = published.payload
    changed_draft = DashboardDraft(
        dashboard_id="dashboard-1",
        canvas_payload=_canvas().to_payload(),
        template_selection=select_design_template("ledger_focus"),
    )

    changed_preview = preview_dashboard_draft(changed_draft)

    assert changed_preview["template"] != original_payload["template"]
    assert published.payload == original_payload
    assert published.payload["version"] == 1


def test_data_meaning_changes_require_reapproval_before_republish() -> None:
    approved = approve_dashboard_draft(_draft(), approver="analyst-1")
    published = publish_dashboard(approved)
    changed = mark_dashboard_data_meaning_changed(approved, reason="sql_changed")

    try:
        _ = publish_dashboard(changed, previous=published)
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "DASHBOARD_REAPPROVAL_REQUIRED" in str(exc)

    reapproved = approve_dashboard_draft(changed, approver="analyst-2")
    republished = publish_dashboard(reapproved, previous=published)

    assert republished.version == 2
    assert [event["event"] for event in republished.audit_events][-3:] == [
        "dashboard_reapproval_required",
        "dashboard_final_approved",
        "dashboard_published",
    ]


def test_rejected_and_invalid_dashboard_publish_transitions_are_refused() -> None:
    rejected = reject_dashboard_draft(_draft(), approver="analyst-1", reason="wrong metric")

    try:
        _ = approve_dashboard_draft(rejected, approver="analyst-2")
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "DASHBOARD_DRAFT_NOT_APPROVABLE:rejected" in str(exc)

    try:
        _ = publish_dashboard(rejected)
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "DASHBOARD_FINAL_APPROVAL_REQUIRED" in str(exc)

    try:
        _ = reject_dashboard_draft(_draft(), approver="analyst-1", reason="")
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "DASHBOARD_REJECTION_REASON_REQUIRED" in str(exc)


def test_approval_rejection_publish_and_reapproval_events_are_audited() -> None:
    rejected = reject_dashboard_draft(_draft(), approver="analyst-1", reason="wrong metric")
    approved = approve_dashboard_draft(_draft(), approver="analyst-1")
    published = publish_dashboard(approved)
    changed = mark_dashboard_data_meaning_changed(approved, reason="dashboard_data_source_changed")

    assert rejected.audit_events[-1] == {
        "event": "dashboard_final_rejected",
        "dashboard_id": "dashboard-1",
        "state": "rejected",
        "approver": "analyst-1",
        "reason": "wrong metric",
    }
    assert approved.audit_events[-1]["event"] == "dashboard_final_approved"
    assert published.audit_events[-1] == {
        "event": "dashboard_published",
        "dashboard_id": "dashboard-1",
        "version": 1,
        "state": "published",
    }
    assert changed.audit_events[-1] == {
        "event": "dashboard_reapproval_required",
        "dashboard_id": "dashboard-1",
        "state": "reapproval_required",
        "reason": "dashboard_data_source_changed",
    }

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
import secrets
from typing import Protocol, cast

from skill_scripts.dashboard_canvas import load_dashboard_canvas
from skill_scripts.design_template_catalog import DesignTemplateSelection, apply_design_template_to_canvas_preview


AuditEvent = dict[str, object]
MIN_REFRESH_INTERVAL_SECONDS = 60
MAX_REFRESH_INTERVAL_SECONDS = 3600


@dataclass(frozen=True)
class DashboardDraft:
    dashboard_id: str
    canvas_payload: Mapping[str, object]
    template_selection: DesignTemplateSelection
    state: str = "draft"
    audit_events: list[AuditEvent] = field(default_factory=list)


@dataclass(frozen=True)
class PublishedDashboard:
    dashboard_id: str
    version: int
    payload: dict[str, object]
    audit_events: list[AuditEvent] = field(default_factory=list)


@dataclass(frozen=True)
class PublishedDashboardLink:
    token: str
    dashboard_id: str
    version: int
    expires_at: str | None = None
    revoked: bool = False
    audit_events: list[AuditEvent] = field(default_factory=list)


class ReadOnlyDashboardDataSource(Protocol):
    def read_published_dashboard(self, published: PublishedDashboard, *, reason: str) -> Mapping[str, object]: ...


def preview_dashboard_draft(draft: DashboardDraft) -> dict[str, object]:
    dashboard_id = _dashboard_id(draft.dashboard_id)
    canvas = load_dashboard_canvas(draft.canvas_payload)
    preview = apply_design_template_to_canvas_preview(canvas, draft.template_selection)
    return {
        "dashboard_id": dashboard_id,
        "state": draft.state,
        "template": preview["template"],
        "canvas": preview["canvas"],
    }


def approve_dashboard_draft(draft: DashboardDraft, approver: str) -> DashboardDraft:
    if draft.state not in {"draft", "reapproval_required"}:
        raise RuntimeError(f"DASHBOARD_DRAFT_NOT_APPROVABLE:{draft.state}")
    approver_id = _required_text(approver, "DASHBOARD_APPROVER_REQUIRED")
    event: AuditEvent = {
        "event": "dashboard_final_approved",
        "dashboard_id": _dashboard_id(draft.dashboard_id),
        "state": "approved",
        "approver": approver_id,
    }
    return DashboardDraft(
        dashboard_id=draft.dashboard_id,
        canvas_payload=draft.canvas_payload,
        template_selection=draft.template_selection,
        state="approved",
        audit_events=[*_audit_events(draft.audit_events), event],
    )


def reject_dashboard_draft(draft: DashboardDraft, approver: str, reason: str) -> DashboardDraft:
    if draft.state not in {"draft", "reapproval_required"}:
        raise RuntimeError(f"DASHBOARD_DRAFT_NOT_REJECTABLE:{draft.state}")
    approver_id = _required_text(approver, "DASHBOARD_APPROVER_REQUIRED")
    rejection_reason = _required_text(reason, "DASHBOARD_REJECTION_REASON_REQUIRED")
    event: AuditEvent = {
        "event": "dashboard_final_rejected",
        "dashboard_id": _dashboard_id(draft.dashboard_id),
        "state": "rejected",
        "approver": approver_id,
        "reason": rejection_reason,
    }
    return DashboardDraft(
        dashboard_id=draft.dashboard_id,
        canvas_payload=draft.canvas_payload,
        template_selection=draft.template_selection,
        state="rejected",
        audit_events=[*_audit_events(draft.audit_events), event],
    )


def mark_dashboard_data_meaning_changed(draft: DashboardDraft, reason: str) -> DashboardDraft:
    change_reason = _required_data_meaning_reason(reason)
    event: AuditEvent = {
        "event": "dashboard_reapproval_required",
        "dashboard_id": _dashboard_id(draft.dashboard_id),
        "state": "reapproval_required",
        "reason": change_reason,
    }
    return DashboardDraft(
        dashboard_id=draft.dashboard_id,
        canvas_payload=draft.canvas_payload,
        template_selection=draft.template_selection,
        state="reapproval_required",
        audit_events=[*_audit_events(draft.audit_events), event],
    )


def publish_dashboard(draft: DashboardDraft, previous: PublishedDashboard | None = None) -> PublishedDashboard:
    if draft.state != "approved":
        if draft.state == "reapproval_required":
            raise RuntimeError("DASHBOARD_REAPPROVAL_REQUIRED")
        raise RuntimeError("DASHBOARD_FINAL_APPROVAL_REQUIRED")
    dashboard_id = _dashboard_id(draft.dashboard_id)
    version = 1 if previous is None else previous.version + 1
    preview = preview_dashboard_draft(draft)
    payload: dict[str, object] = {
        "dashboard_id": dashboard_id,
        "version": version,
        "state": "published",
        "template": _copy_mapping(cast(Mapping[str, object], preview["template"])),
        "canvas": _copy_mapping(cast(Mapping[str, object], preview["canvas"])),
    }
    event: AuditEvent = {
        "event": "dashboard_published",
        "dashboard_id": dashboard_id,
        "version": version,
        "state": "published",
    }
    return PublishedDashboard(
        dashboard_id=dashboard_id,
        version=version,
        payload=payload,
        audit_events=[*_audit_events(draft.audit_events), event],
    )


def create_published_dashboard_link(published: PublishedDashboard, expires_at: str | None = None) -> PublishedDashboardLink:
    event: AuditEvent = {
        "event": "published_dashboard_link_created",
        "dashboard_id": published.dashboard_id,
        "version": published.version,
        "expires_at": expires_at,
    }
    return PublishedDashboardLink(
        token=secrets.token_urlsafe(32),
        dashboard_id=published.dashboard_id,
        version=published.version,
        expires_at=expires_at,
        audit_events=[*_audit_events(published.audit_events), event],
    )


def revoke_published_dashboard_link(link: PublishedDashboardLink) -> PublishedDashboardLink:
    event: AuditEvent = {
        "event": "published_dashboard_link_revoked",
        "dashboard_id": link.dashboard_id,
        "version": link.version,
    }
    return PublishedDashboardLink(
        token=link.token,
        dashboard_id=link.dashboard_id,
        version=link.version,
        expires_at=link.expires_at,
        revoked=True,
        audit_events=[*_audit_events(link.audit_events), event],
    )


def render_published_dashboard_link(
    *,
    token: str,
    links: list[PublishedDashboardLink],
    dashboards: list[PublishedDashboard],
    data_source: ReadOnlyDashboardDataSource,
    now: str,
) -> dict[str, object]:
    link = _find_link(token, links)
    if link is None:
        return _denied("published_dashboard_link_malformed", "LINK_TOKEN_MALFORMED", token="")
    if link.revoked:
        return _denied("published_dashboard_link_denied_revoked", "LINK_TOKEN_REVOKED", link=link)
    if link.expires_at is not None:
        try:
            expired = _parse_timestamp(now) >= _parse_timestamp(link.expires_at)
        except ValueError:
            return _denied("published_dashboard_link_denied_malformed_expiration", "LINK_EXPIRATION_MALFORMED", link=link)
        if expired:
            return _denied("published_dashboard_link_denied_expired", "LINK_TOKEN_EXPIRED", link=link)
    published = _find_published_dashboard(link, dashboards)
    if published is None:
        return _denied("published_dashboard_link_denied_unpublished", "PUBLISHED_DASHBOARD_NOT_AVAILABLE", link=link)
    try:
        data = data_source.read_published_dashboard(published, reason="view")
    except Exception:
        return _view_failed(link)
    return {
        "status": "ok",
        "view_only": True,
        "authoring_actions": [],
        "dashboard": _copy_mapping(published.payload),
        "data": data,
        "audit_events": _audit_events(link.audit_events),
    }


def refresh_published_dashboard_view(
    rendered_view: Mapping[str, object],
    *,
    published: PublishedDashboard,
    data_source: ReadOnlyDashboardDataSource,
    refresh_interval_seconds: int,
) -> dict[str, object]:
    interval = _refresh_interval(refresh_interval_seconds)
    refreshed = _copy_mapping(rendered_view)
    try:
        refreshed["data"] = data_source.read_published_dashboard(published, reason="refresh")
        refreshed["refresh"] = {"status": "fresh", "interval_seconds": interval}
    except Exception:
        event: AuditEvent = {
            "event": "published_dashboard_refresh_failed",
            "dashboard_id": published.dashboard_id,
            "version": published.version,
            "code": "DASHBOARD_REFRESH_FAILED",
        }
        refreshed["refresh"] = {"status": "stale_error", "interval_seconds": interval, "code": "DASHBOARD_REFRESH_FAILED"}
        refreshed["audit_events"] = [*_audit_events(cast(list[AuditEvent], rendered_view.get("audit_events", []))), event]
    return refreshed


def _dashboard_id(value: str) -> str:
    return _required_text(value, "DASHBOARD_ID_REQUIRED")


def _find_link(token: str, links: list[PublishedDashboardLink]) -> PublishedDashboardLink | None:
    text = str(token or "").strip()
    if not text:
        return None
    for link in links:
        if secrets.compare_digest(link.token, text):
            return link
    return None


def _find_published_dashboard(link: PublishedDashboardLink, dashboards: list[PublishedDashboard]) -> PublishedDashboard | None:
    for dashboard in dashboards:
        if dashboard.dashboard_id == link.dashboard_id and dashboard.version == link.version and dashboard.payload.get("state") == "published":
            return dashboard
    return None


def _denied(event_name: str, code: str, *, link: PublishedDashboardLink | None = None, token: str | None = None) -> dict[str, object]:
    event: AuditEvent = {"event": event_name, "code": code}
    if link is not None:
        event["dashboard_id"] = link.dashboard_id
        event["version"] = link.version
    if token is not None:
        event["token_present"] = bool(token)
    return {"status": "denied", "code": code, "dashboard": None, "data": None, "audit_events": [event]}


def _view_failed(link: PublishedDashboardLink) -> dict[str, object]:
    event: AuditEvent = {
        "event": "published_dashboard_view_failed",
        "dashboard_id": link.dashboard_id,
        "version": link.version,
        "code": "DASHBOARD_VIEW_FAILED",
    }
    return {
        "status": "error",
        "code": "DASHBOARD_VIEW_FAILED",
        "view_only": True,
        "authoring_actions": [],
        "dashboard": None,
        "data": None,
        "audit_events": [*_audit_events(link.audit_events), event],
    }


def _parse_timestamp(value: str) -> datetime:
    text = _required_text(value, "TIMESTAMP_REQUIRED")
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


def _refresh_interval(value: int) -> int:
    interval = int(value)
    if interval < MIN_REFRESH_INTERVAL_SECONDS:
        raise RuntimeError("DASHBOARD_REFRESH_INTERVAL_TOO_FAST")
    if interval > MAX_REFRESH_INTERVAL_SECONDS:
        raise RuntimeError("DASHBOARD_REFRESH_INTERVAL_TOO_SLOW")
    return interval


def _required_text(value: str, code: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise RuntimeError(code)
    return text


def _required_data_meaning_reason(value: str) -> str:
    reason = _required_text(value, "DASHBOARD_DATA_MEANING_CHANGE_REASON_REQUIRED")
    if reason not in {"sql_changed", "dashboard_data_source_changed", "query_semantics_changed"}:
        raise RuntimeError(f"DASHBOARD_DATA_MEANING_CHANGE_NOT_SUPPORTED:{reason}")
    return reason


def _audit_events(events: list[AuditEvent]) -> list[AuditEvent]:
    return [_copy_mapping(event) for event in events]


def _copy_mapping(value: Mapping[str, object]) -> dict[str, object]:
    copied: dict[str, object] = {}
    for key, item in value.items():
        if isinstance(item, dict):
            copied[key] = _copy_mapping(cast(Mapping[str, object], item))
        elif isinstance(item, list):
            values = cast(list[object], item)
            copied[key] = [_copy_mapping(cast(Mapping[str, object], entry)) if isinstance(entry, dict) else entry for entry in values]
        else:
            copied[key] = item
    return copied

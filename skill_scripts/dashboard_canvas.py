from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import cast

from skill_scripts.chart_spec import ChartSpec, author_chart_spec, render_chart_preview
from skill_scripts.governed_query import GovernedQueryResult, QueryEvidence


_APPROVED_DRAFT_MARKER = object()


@dataclass(frozen=True)
class DashboardChartDraft:
    chart: ChartSpec
    preview: dict[str, object]
    approval_marker: object | None = None

    def to_payload(self) -> dict[str, object]:
        return self.chart.to_payload()


@dataclass(frozen=True)
class DashboardCanvasItem:
    chart_id: str
    chart: DashboardChartDraft
    x: int
    y: int
    w: int
    h: int

    def to_payload(self) -> dict[str, object]:
        return {
            "chart_id": self.chart_id,
            "x": self.x,
            "y": self.y,
            "w": self.w,
            "h": self.h,
            "chart": self.chart.to_payload(),
        }


class DashboardCanvas:
    def __init__(self, columns: int = 12, rows: int = 12) -> None:
        self.columns: int = _int_value(columns)
        self.rows: int = _int_value(rows)
        if self.columns <= 0 or self.rows <= 0:
            raise RuntimeError("DASHBOARD_CANVAS_INVALID_GRID")
        self._items: dict[str, DashboardCanvasItem] = {}

    def add_chart(self, chart_id: str, chart: object, x: int, y: int, w: int, h: int) -> DashboardCanvasItem:
        normalized_id = _chart_id(chart_id)
        if normalized_id in self._items:
            raise RuntimeError(f"DASHBOARD_CANVAS_DUPLICATE_CHART:{normalized_id}")
        if not isinstance(chart, DashboardChartDraft) or chart.approval_marker is not _APPROVED_DRAFT_MARKER:
            raise RuntimeError("INVALID_CHART_DRAFT")
        item = DashboardCanvasItem(chart_id=normalized_id, chart=chart, x=_int_value(x), y=_int_value(y), w=_int_value(w), h=_int_value(h))
        self._validate_item(item)
        self._items[normalized_id] = item
        return item

    def move_chart(self, chart_id: str, x: int, y: int) -> DashboardCanvasItem:
        item = self._existing_item(chart_id)
        moved = replace(item, x=_int_value(x), y=_int_value(y))
        self._validate_item(moved, ignore_chart_id=item.chart_id)
        self._items[item.chart_id] = moved
        return moved

    def resize_chart(self, chart_id: str, w: int, h: int) -> DashboardCanvasItem:
        item = self._existing_item(chart_id)
        resized = replace(item, w=_int_value(w), h=_int_value(h))
        self._validate_item(resized, ignore_chart_id=item.chart_id)
        self._items[item.chart_id] = resized
        return resized

    def render_layout(self) -> list[dict[str, object]]:
        return [item.to_payload() for item in self._ordered_items()]

    def to_payload(self) -> dict[str, object]:
        return {"columns": self.columns, "rows": self.rows, "items": self.render_layout()}

    def _ordered_items(self) -> list[DashboardCanvasItem]:
        return sorted(self._items.values(), key=lambda item: (item.y, item.x, item.chart_id))

    def _existing_item(self, chart_id: str) -> DashboardCanvasItem:
        normalized_id = _chart_id(chart_id)
        try:
            return self._items[normalized_id]
        except KeyError as exc:
            raise RuntimeError(f"DASHBOARD_CANVAS_CHART_NOT_FOUND:{normalized_id}") from exc

    def _validate_item(self, item: DashboardCanvasItem, ignore_chart_id: str = "") -> None:
        if item.x < 0 or item.y < 0 or item.w <= 0 or item.h <= 0 or item.x + item.w > self.columns or item.y + item.h > self.rows:
            raise RuntimeError(f"DASHBOARD_CANVAS_OUT_OF_BOUNDS:{item.chart_id}")
        for existing in self._ordered_items():
            if existing.chart_id == ignore_chart_id:
                continue
            if _overlaps(item, existing):
                raise RuntimeError(f"DASHBOARD_CANVAS_OVERLAP:{item.chart_id}:{existing.chart_id}")


def load_dashboard_canvas(payload: Mapping[str, object]) -> DashboardCanvas:
    canvas = DashboardCanvas(columns=_int_value(payload.get("columns", 12)), rows=_int_value(payload.get("rows", 12)))
    items = payload.get("items", [])
    if not isinstance(items, list):
        raise RuntimeError("DASHBOARD_CANVAS_INVALID_PAYLOAD")
    item_values = cast(list[object], items)
    for item_value in item_values:
        if not isinstance(item_value, dict):
            raise RuntimeError("DASHBOARD_CANVAS_INVALID_PAYLOAD")
        item = cast(dict[str, object], item_value)
        chart_payload = item.get("chart")
        if not isinstance(chart_payload, dict):
            raise RuntimeError("INVALID_CHART_DRAFT")
        _ = canvas.add_chart(
            chart_id=str(item.get("chart_id", "")),
            chart=_persisted_chart_draft_from_payload(cast(dict[str, object], chart_payload)),
            x=_int_value(item.get("x", 0)),
            y=_int_value(item.get("y", 0)),
            w=_int_value(item.get("w", 0)),
            h=_int_value(item.get("h", 0)),
        )
    return canvas


def create_dashboard_chart_draft(result: GovernedQueryResult, chart_payload: Mapping[str, object]) -> DashboardChartDraft:
    chart = author_chart_spec(result, chart_payload)
    preview = render_chart_preview(result, chart)
    return DashboardChartDraft(chart=chart, preview=preview, approval_marker=_APPROVED_DRAFT_MARKER)


def _chart_id(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise RuntimeError("DASHBOARD_CANVAS_CHART_ID_REQUIRED")
    return normalized


def _int_value(value: object) -> int:
    if isinstance(value, bool):
        raise RuntimeError("DASHBOARD_CANVAS_INVALID_PAYLOAD")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped and (stripped.isdigit() or (stripped.startswith("-") and stripped[1:].isdigit())):
            return int(stripped)
    raise RuntimeError("DASHBOARD_CANVAS_INVALID_PAYLOAD")


def _persisted_chart_draft_from_payload(payload: Mapping[str, object]) -> DashboardChartDraft:
    chart = _validate_persisted_chart_payload(payload)
    return DashboardChartDraft(chart=chart, preview={}, approval_marker=_APPROVED_DRAFT_MARKER)


def _validate_persisted_chart_payload(payload: Mapping[str, object]) -> ChartSpec:
    chart_type = str(payload.get("chart_type", "")).strip()
    title = str(payload.get("title", "")).strip()
    _require_clean_string(payload.get("chart_type", ""))
    _require_clean_string(payload.get("title", ""))
    if not title:
        raise RuntimeError("INVALID_CHART_DRAFT")
    if chart_type not in {"table", "kpi_card", "bar", "line"}:
        raise RuntimeError("INVALID_CHART_DRAFT")
    if chart_type == "table" and not _string_list(payload.get("fields", [])):
        raise RuntimeError("INVALID_CHART_DRAFT")
    if chart_type == "table":
        _require_clean_string_list(payload.get("fields", []))
    if chart_type == "kpi_card" and not str(payload.get("value_field", "")).strip():
        raise RuntimeError("INVALID_CHART_DRAFT")
    if chart_type == "kpi_card":
        _require_clean_string(payload.get("value_field", ""))
        label_field = str(payload.get("label_field", ""))
        if label_field:
            _require_clean_string(label_field)
    if chart_type in {"bar", "line"} and (not str(payload.get("x_field", "")).strip() or not str(payload.get("y_field", "")).strip()):
        raise RuntimeError("INVALID_CHART_DRAFT")
    if chart_type in {"bar", "line"}:
        _require_clean_string(payload.get("x_field", ""))
        _require_clean_string(payload.get("y_field", ""))
        series_field = str(payload.get("series_field", ""))
        if series_field:
            _require_clean_string(series_field)
    _validate_persisted_optional_field_mapping(payload.get("sort", {}), allowed_keys={"field", "direction"})
    _validate_persisted_optional_field_mapping(payload.get("number_format", {}), allowed_keys={"field", "style", "currency"})
    _validate_persisted_optional_field_mapping(payload.get("date_format", {}), allowed_keys={"field", "format"})
    color = str(payload.get("color", "")).strip()
    if color:
        _require_clean_string(payload.get("color", ""))
    if color and (len(color) != 7 or not color.startswith("#")):
        raise RuntimeError("INVALID_CHART_DRAFT")
    if color:
        try:
            _ = int(color[1:], 16)
        except ValueError as exc:
            raise RuntimeError("INVALID_CHART_DRAFT") from exc
    try:
        return author_chart_spec(_persisted_chart_result(payload), payload)
    except RuntimeError as exc:
        raise RuntimeError("INVALID_CHART_DRAFT") from exc


def _persisted_chart_result(payload: Mapping[str, object]) -> GovernedQueryResult:
    return GovernedQueryResult(
        evidence=QueryEvidence(
            prompt="persisted Dashboard Canvas chart replay",
            sql="SELECT [persisted]",
            route="persisted",
            route_reason="dashboard_canvas_reload",
            validation_status="OK",
            execution_status="OK",
            execution_timestamp="",
            returned_columns=_persisted_chart_fields(payload),
            row_count=1,
            sample_rows=[_persisted_chart_sample_row(payload)],
        ),
        approval_state="approved_for_chart_spec",
    )


def _persisted_chart_fields(payload: Mapping[str, object]) -> list[str]:
    fields: list[str] = []
    for key in ("fields", "x_field", "y_field", "series_field", "value_field", "label_field"):
        value = payload.get(key, []) if key == "fields" else payload.get(key, "")
        if isinstance(value, list):
            list_values = cast(list[object], value)
            for item in list_values:
                if isinstance(item, str) and item.strip() and item.strip() not in fields:
                    fields.append(item.strip())
        if isinstance(value, str) and value.strip() and value.strip() not in fields:
            fields.append(value.strip())
    for value in (payload.get("sort", {}), payload.get("number_format", {}), payload.get("date_format", {})):
        if isinstance(value, dict):
            mapping = cast(dict[object, object], value)
            field_name = mapping.get("field", "")
            if isinstance(field_name, str) and field_name.strip() and field_name.strip() not in fields:
                fields.append(field_name.strip())
    return fields


def _persisted_chart_sample_row(payload: Mapping[str, object]) -> dict[str, object]:
    row: dict[str, object] = {}
    number_field = ""
    number_format = payload.get("number_format", {})
    if isinstance(number_format, dict):
        number_mapping = cast(dict[object, object], number_format)
        field_value = number_mapping.get("field", "")
        if isinstance(field_value, str):
            number_field = field_value.strip()
    for field_name in _persisted_chart_fields(payload):
        row[field_name] = 1.0 if field_name == number_field else field_name
    return row


def _validate_persisted_optional_field_mapping(value: object, allowed_keys: set[str]) -> None:
    if value in ({}, None):
        return
    if not isinstance(value, dict):
        raise RuntimeError("INVALID_CHART_DRAFT")
    mapping = cast(dict[object, object], value)
    if any(not isinstance(key, str) or key not in allowed_keys for key in mapping):
        raise RuntimeError("INVALID_CHART_DRAFT")
    if any(not isinstance(mapped, str) or not mapped.strip() for mapped in mapping.values()):
        raise RuntimeError("INVALID_CHART_DRAFT")
    if any(mapped != mapped.strip() for mapped in mapping.values() if isinstance(mapped, str)):
        raise RuntimeError("INVALID_CHART_DRAFT")


def _require_clean_string(value: object) -> None:
    if not isinstance(value, str) or value != value.strip():
        raise RuntimeError("INVALID_CHART_DRAFT")


def _require_clean_string_list(value: object) -> None:
    if not isinstance(value, list):
        raise RuntimeError("INVALID_CHART_DRAFT")
    values = cast(list[object], value)
    if any(not isinstance(item, str) or not item.strip() or item != item.strip() for item in values):
        raise RuntimeError("INVALID_CHART_DRAFT")


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    values = cast(list[object], value)
    return [item for item in values if isinstance(item, str)]


def _overlaps(left: DashboardCanvasItem, right: DashboardCanvasItem) -> bool:
    return left.x < right.x + right.w and left.x + left.w > right.x and left.y < right.y + right.h and left.y + left.h > right.y

from dataclasses import dataclass, field
from collections.abc import Mapping
from typing import cast

from skill_scripts.governed_query import GovernedQueryResult, require_query_result_approved_for_chart_spec


@dataclass(frozen=True)
class ChartSpec:
    chart_type: str
    title: str
    fields: list[str] = field(default_factory=list)
    x_field: str = ""
    y_field: str = ""
    series_field: str = ""
    sort: dict[str, str] = field(default_factory=dict)
    color: str = ""
    number_format: dict[str, str] = field(default_factory=dict)
    date_format: dict[str, str] = field(default_factory=dict)
    value_field: str = ""
    label_field: str = ""

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {"chart_type": self.chart_type, "title": self.title}
        if self.fields:
            payload["fields"] = self.fields
        if self.x_field:
            payload["x_field"] = self.x_field
        if self.y_field:
            payload["y_field"] = self.y_field
        if self.series_field:
            payload["series_field"] = self.series_field
        if self.value_field:
            payload["value_field"] = self.value_field
        if self.label_field:
            payload["label_field"] = self.label_field
        if self.sort:
            payload["sort"] = self.sort
        if self.color:
            payload["color"] = self.color
        if self.number_format:
            payload["number_format"] = self.number_format
        if self.date_format:
            payload["date_format"] = self.date_format
        return payload


def _sample_rows(result: GovernedQueryResult) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    sample_rows: list[dict[str, object]] = result.evidence.sample_rows
    for row in sample_rows:
        copied: dict[str, object] = {}
        for key, value in row.items():
            copied[key] = value
        rows.append(copied)
    return rows


def _available_fields(result: GovernedQueryResult) -> set[str]:
    return set(result.evidence.returned_columns)


def _require_field(field_name: str, available_fields: set[str]) -> None:
    if field_name not in available_fields:
        raise RuntimeError(f"UNSUPPORTED_FIELD:{field_name}")


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    copied: dict[str, object] = {}
    for key in ("field", "direction", "style", "currency", "format"):
        if key in value:
            copied[key] = value[key]
    return copied


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    source = cast(list[object], value)
    strings: list[str] = []
    for item in source:
        if isinstance(item, str) and item.strip():
            strings.append(item.strip())
    return strings


def _is_numeric_field(result: GovernedQueryResult, field_name: str) -> bool:
    for row in _sample_rows(result):
        value = row.get(field_name)
        if value is not None:
            return isinstance(value, int | float)
    return False


def _validate_sort(sort: object, available_fields: set[str]) -> dict[str, str]:
    sort_payload = _mapping(sort)
    if not sort_payload:
        return {}
    field_name = str(sort_payload.get("field", "")).strip()
    direction = str(sort_payload.get("direction", "asc")).strip().lower()
    _require_field(field_name, available_fields)
    if direction not in {"asc", "desc"}:
        raise RuntimeError(f"INVALID_SORT_DIRECTION:{direction}")
    return {"field": field_name, "direction": direction}


def _validate_color(color: object) -> str:
    color_value = str(color or "").strip()
    if not color_value:
        return ""
    if len(color_value) != 7 or not color_value.startswith("#"):
        raise RuntimeError(f"INVALID_COLOR:{color_value}")
    try:
        _ = int(color_value[1:], 16)
    except ValueError as exc:
        raise RuntimeError(f"INVALID_COLOR:{color_value}") from exc
    return color_value


def _validate_number_format(result: GovernedQueryResult, value: object, available_fields: set[str]) -> dict[str, str]:
    format_payload = _mapping(value)
    if not format_payload:
        return {}
    field_name = str(format_payload.get("field", "")).strip()
    style = str(format_payload.get("style", "")).strip()
    _require_field(field_name, available_fields)
    if not _is_numeric_field(result, field_name):
        raise RuntimeError(f"NUMBER_FORMAT_FIELD_NOT_NUMERIC:{field_name}")
    if style not in {"number", "currency", "percent"}:
        raise RuntimeError(f"INVALID_NUMBER_FORMAT_STYLE:{style}")
    formatted = {"field": field_name, "style": style}
    currency = str(format_payload.get("currency", "")).strip()
    if currency:
        formatted["currency"] = currency
    return formatted


def _validate_date_format(value: object, available_fields: set[str]) -> dict[str, str]:
    format_payload = _mapping(value)
    if not format_payload:
        return {}
    field_name = str(format_payload.get("field", "")).strip()
    date_format = str(format_payload.get("format", "")).strip()
    _require_field(field_name, available_fields)
    if date_format not in {"YYYY-MM-DD", "YYYY-MM", "YYYY"}:
        raise RuntimeError(f"INVALID_DATE_FORMAT:{date_format}")
    return {"field": field_name, "format": date_format}


def _sort_value(value: object) -> tuple[int, object]:
    if value is None:
        return (1, "")
    if isinstance(value, int | float) and not isinstance(value, bool):
        return (0, float(value))
    return (0, str(value))


def author_chart_spec(result: GovernedQueryResult, payload: Mapping[str, object]) -> ChartSpec:
    require_query_result_approved_for_chart_spec(result)
    chart_type = str(payload.get("chart_type", "")).strip()
    if chart_type not in {"table", "kpi_card", "bar", "line"}:
        raise RuntimeError(f"UNSUPPORTED_CHART_TYPE:{chart_type}")
    title = str(payload.get("title", "")).strip()
    if not title:
        raise RuntimeError("TITLE_REQUIRED")
    available_fields = _available_fields(result)
    if chart_type == "table":
        fields = _string_list(payload.get("fields", []))
        if not fields:
            raise RuntimeError("FIELDS_REQUIRED")
        for field in fields:
            _require_field(field, available_fields)
        return ChartSpec(
            chart_type=chart_type,
            title=title,
            fields=fields,
            sort=_validate_sort(payload.get("sort"), available_fields),
            color=_validate_color(payload.get("color")),
            number_format=_validate_number_format(result, payload.get("number_format"), available_fields),
            date_format=_validate_date_format(payload.get("date_format"), available_fields),
        )

    if chart_type == "kpi_card":
        value_field = str(payload.get("value_field", "")).strip()
        if not value_field:
            raise RuntimeError("VALUE_FIELD_REQUIRED")
        _require_field(value_field, available_fields)
        label_field = str(payload.get("label_field", "")).strip()
        if label_field:
            _require_field(label_field, available_fields)
        return ChartSpec(
            chart_type=chart_type,
            title=title,
            value_field=value_field,
            label_field=label_field,
            sort=_validate_sort(payload.get("sort"), available_fields),
            color=_validate_color(payload.get("color")),
            number_format=_validate_number_format(result, payload.get("number_format"), available_fields),
        )

    x_field = str(payload.get("x_field", "")).strip()
    if not x_field:
        raise RuntimeError("X_FIELD_REQUIRED")
    y_field = str(payload.get("y_field", "")).strip()
    if not y_field:
        raise RuntimeError("Y_FIELD_REQUIRED")
    _require_field(x_field, available_fields)
    _require_field(y_field, available_fields)
    series_field = str(payload.get("series_field", "")).strip()
    if series_field:
        _require_field(series_field, available_fields)
    return ChartSpec(
        chart_type=chart_type,
        title=title,
        x_field=x_field,
        y_field=y_field,
        series_field=series_field,
        sort=_validate_sort(payload.get("sort"), available_fields),
        color=_validate_color(payload.get("color")),
        number_format=_validate_number_format(result, payload.get("number_format"), available_fields),
        date_format=_validate_date_format(payload.get("date_format"), available_fields),
    )


def render_chart_preview(result: GovernedQueryResult, spec: ChartSpec) -> dict[str, object]:
    spec = author_chart_spec(result, spec.to_payload())
    if spec.chart_type == "table":
        return {
            "chart_type": spec.chart_type,
            "title": spec.title,
            "columns": spec.fields,
            "rows": [{field: row.get(field) for field in spec.fields} for row in result.evidence.sample_rows],
        }
    rows = _sample_rows(result)
    if spec.sort:
        rows.sort(key=lambda row: _sort_value(row.get(spec.sort["field"])), reverse=spec.sort["direction"] == "desc")
    if spec.chart_type == "kpi_card":
        selected = rows[0] if rows else {}
        return {
            "chart_type": spec.chart_type,
            "title": spec.title,
            "value_field": spec.value_field,
            "label_field": spec.label_field,
            "color": spec.color,
            "number_format": spec.number_format,
            "value": selected.get(spec.value_field),
            "label": selected.get(spec.label_field) if spec.label_field else None,
        }
    return {
        "chart_type": spec.chart_type,
        "title": spec.title,
        "x_field": spec.x_field,
        "y_field": spec.y_field,
        "series_field": spec.series_field,
        "color": spec.color,
        "number_format": spec.number_format,
        "date_format": spec.date_format,
        "data": [
            {
                "x": row.get(spec.x_field),
                "y": row.get(spec.y_field),
                "series": row.get(spec.series_field) if spec.series_field else None,
            }
            for row in rows
        ],
    }

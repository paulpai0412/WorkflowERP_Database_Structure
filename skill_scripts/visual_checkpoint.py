from __future__ import annotations

from html import escape
from typing import Any, Mapping


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _columns(package: Mapping[str, Any]) -> list[str]:
    data_profile = _mapping(package.get("data_profile"))
    columns = _string_list(data_profile.get("columns"))
    if columns:
        return columns
    datasets = _mapping(package.get("datasets"))
    return _string_list(datasets.get("columns"))


def _kpis(package: Mapping[str, Any]) -> list[dict[str, Any]]:
    aggregates = _mapping(package.get("aggregates"))
    return [
        {"label": str(label), "value": value}
        for label, value in aggregates.items()
        if isinstance(value, (int, float, str))
    ]


def build_visual_checkpoint_payload(
    brief: Mapping[str, Any],
    package: Mapping[str, Any],
) -> dict[str, Any]:
    columns = _columns(package)
    data_profile = dict(_mapping(package.get("data_profile")))
    if columns:
        data_profile["columns"] = columns

    charts = []
    for chart in brief.get("chart_recipe", []):
        if not isinstance(chart, Mapping):
            continue
        charts.append(
            {
                "id": str(chart.get("id") or ""),
                "type": str(chart.get("type") or ""),
                "purpose": str(chart.get("purpose") or ""),
            }
        )

    tables = []
    for table in brief.get("table_recipe", []):
        if not isinstance(table, Mapping):
            continue
        tables.append(
            {
                "id": str(table.get("id") or ""),
                "type": str(table.get("type") or ""),
                "columns": columns,
                "features": _string_list(table.get("features")),
                "row_count": table.get("row_count", data_profile.get("row_count", 0)),
            }
        )

    layout_recipe = _mapping(brief.get("layout_recipe"))
    interaction_recipe = _mapping(brief.get("interaction_recipe"))
    return {
        "title": "費用分析視覺設計確認",
        "catalog_guardrail": str(brief.get("catalog_guardrail") or package.get("catalog_guardrail") or ""),
        "layout": {
            "mode": str(layout_recipe.get("mode") or ""),
            "sections": _string_list(layout_recipe.get("sections")),
            "density": str(layout_recipe.get("density") or ""),
        },
        "kpis": _kpis(package),
        "charts": charts,
        "tables": tables,
        "interactions": {
            "filters": _string_list(interaction_recipe.get("filters")),
            "drilldowns": _string_list(interaction_recipe.get("drilldowns")),
        },
        "visual_direction": dict(_mapping(brief.get("visual_direction"))),
        "data_profile": data_profile,
    }


def _render_list(items: list[str]) -> str:
    if not items:
        return "<li>無</li>"
    return "".join(f"<li>{escape(item)}</li>" for item in items)


def render_visual_checkpoint_html(payload: Mapping[str, Any]) -> str:
    title = escape(str(payload.get("title") or "費用分析視覺設計確認"))
    layout = _mapping(payload.get("layout"))
    data_profile = _mapping(payload.get("data_profile"))
    visual_direction = _mapping(payload.get("visual_direction"))

    kpi_cards = "".join(
        f"<article><span>{escape(str(kpi.get('label', '')))}</span><strong>{escape(str(kpi.get('value', '')))}</strong></article>"
        for kpi in payload.get("kpis", [])
        if isinstance(kpi, Mapping)
    )
    chart_items = "".join(
        "<li>"
        f"<strong>{escape(str(chart.get('type', '')))}</strong>"
        f"<span>{escape(str(chart.get('purpose', '')))}</span>"
        "</li>"
        for chart in payload.get("charts", [])
        if isinstance(chart, Mapping)
    )
    table_items = "".join(
        "<li>"
        f"<strong>{escape(str(table.get('id', '')))}</strong>"
        f"<span>{escape(', '.join(_string_list(table.get('columns'))))}</span>"
        "</li>"
        for table in payload.get("tables", [])
        if isinstance(table, Mapping)
    )
    interactions = _mapping(payload.get("interactions"))
    emphasis = _string_list(visual_direction.get("emphasis"))

    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 32px; color: #202124; background: #f7f8fa; }}
    main {{ max-width: 1080px; margin: 0 auto; }}
    section {{ background: #fff; border: 1px solid #d8dde6; border-radius: 8px; padding: 20px; margin: 16px 0; }}
    .kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }}
    article {{ border-left: 4px solid #2563eb; background: #f8fafc; padding: 12px; }}
    article span, li span {{ display: block; color: #5f6b7a; margin-top: 4px; }}
  </style>
</head>
<body>
  <main>
    <h1>{title}</h1>
    <section>
      <h2>版面</h2>
      <p>{escape(str(layout.get("mode", "")))} / {escape(str(layout.get("density", "")))}</p>
      <ul>{_render_list(_string_list(layout.get("sections")))}</ul>
    </section>
    <section>
      <h2>KPI</h2>
      <div class="kpis">{kpi_cards}</div>
    </section>
    <section>
      <h2>圖表目的</h2>
      <ul>{chart_items}</ul>
    </section>
    <section>
      <h2>表格</h2>
      <ul>{table_items}</ul>
    </section>
    <section>
      <h2>互動</h2>
      <h3>篩選</h3>
      <ul>{_render_list(_string_list(interactions.get("filters")))}</ul>
      <h3>下鑽</h3>
      <ul>{_render_list(_string_list(interactions.get("drilldowns")))}</ul>
    </section>
    <section>
      <h2>視覺方向</h2>
      <p>{escape(str(visual_direction.get("tone", "")))}</p>
      <ul>{_render_list(emphasis)}</ul>
    </section>
    <section>
      <h2>資料輪廓</h2>
      <p>rows: {escape(str(data_profile.get("row_count", 0)))}</p>
      <p>columns: {escape(", ".join(_string_list(data_profile.get("columns"))))}</p>
    </section>
  </main>
</body>
</html>"""

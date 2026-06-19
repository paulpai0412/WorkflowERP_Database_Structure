from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread
from typing import Any, Iterator, Mapping
from urllib.parse import urlparse

from skill_scripts.report_harness import ReportHarness, ReportHarnessError
from skill_scripts.report_harness_state import (
    CHECKPOINT_DEFINITIONS,
    append_audit_event,
    load_run_state,
    write_confirmation,
)


MAX_REQUEST_BYTES = 65536
MAX_TABLE_ROWS = 100
CHART_TYPE_OPTIONS = [
    ("combo", "Combo：實際 / 預算 / 差異"),
    ("bar", "Bar：排行與比較"),
    ("stacked-bar", "Stacked Bar：組成占比"),
    ("line", "Line：趨勢"),
]
LAYOUT_OPTIONS = [
    ("kpi-first-dashboard", "KPI 優先儀表板"),
    ("four-chart-grid", "四圖比較網格"),
    ("executive-one-page", "主管一頁式"),
    ("detail-audit", "明細稽核型"),
]


class CheckpointHTTPServer(ThreadingHTTPServer):
    daemon_threads = True


@dataclass
class RunningCheckpointServer:
    httpd: CheckpointHTTPServer
    thread: Thread
    base_url: str


def _json_script_payload(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def _format_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "是" if value else "否"
    if value is None:
        return "無"
    return str(value)


def _render_badge(value: Any) -> str:
    text = _format_scalar(value)
    lowered = text.lower()
    status = "neutral"
    if lowered in {"pass", "passed", "ok", "true", "valid", "executed"} or text == "是":
        status = "pass"
    elif lowered in {"fail", "failed", "false", "invalid", "blocked", "error"} or text == "否":
        status = "fail"
    elif lowered in {"warning", "pending", "pending_user_confirmation"}:
        status = "warning"
    return f"<span class=\"badge badge-{status}\">{escape(text)}</span>"


def _render_key_values(value: Mapping[str, Any]) -> str:
    rows = []
    for key, item in value.items():
        if isinstance(item, (dict, list)):
            rendered = _render_value(item)
        else:
            rendered = f"<span class=\"kv-value\">{escape(_format_scalar(item))}</span>"
        rows.append(
            "<div class=\"kv-row\">"
            f"<dt>{escape(str(key))}</dt><dd>{rendered}</dd>"
            "</div>"
        )
    return f"<dl class=\"kv-grid\">{''.join(rows)}</dl>"


def _render_list(items: list[Any]) -> str:
    if not items:
        return "<p class=\"muted\">沒有資料</p>"
    if all(isinstance(item, Mapping) for item in items):
        return "".join(
            f"<div class=\"nested-card\">{_render_key_values(dict(item))}</div>" for item in items
        )
    return "<ul class=\"clean-list\">" + "".join(
        f"<li>{_render_value(item) if isinstance(item, (dict, list)) else escape(_format_scalar(item))}</li>"
        for item in items
    ) + "</ul>"


def _render_value(value: Any) -> str:
    if isinstance(value, Mapping):
        return _render_key_values(value)
    if isinstance(value, list):
        return _render_list(value)
    return escape(_format_scalar(value))


def _columns_from_rows(rows: list[Any]) -> list[str]:
    columns: list[str] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        for key in row.keys():
            key_text = str(key)
            if key_text not in columns:
                columns.append(key_text)
    return columns


def _render_table(rows: list[Any], columns: list[str] | None = None) -> str:
    if not rows:
        return "<p class=\"muted\">沒有資料列</p>"
    usable_rows = [row for row in rows if isinstance(row, Mapping)]
    if not usable_rows:
        return _render_list(rows)
    table_columns = columns or _columns_from_rows(usable_rows)
    header = "".join(f"<th>{escape(str(column))}</th>" for column in table_columns)
    body_rows = []
    for row in usable_rows[:MAX_TABLE_ROWS]:
        body_rows.append(
            "<tr>"
            + "".join(
                f"<td>{escape(_format_scalar(row.get(column)))}</td>" for column in table_columns
            )
            + "</tr>"
        )
    overflow = ""
    if len(usable_rows) > MAX_TABLE_ROWS:
        overflow = (
            f"<p class=\"muted table-note\">只顯示前 {MAX_TABLE_ROWS} 筆，"
            f"完整資料共 {len(usable_rows)} 筆。</p>"
        )
    return (
        "<div class=\"table-wrap\"><table><thead><tr>"
        + header
        + "</tr></thead><tbody>"
        + "".join(body_rows)
        + "</tbody></table></div>"
        + overflow
    )


def _mapping_list(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _table_from_mappings(items: list[Mapping[str, Any]]) -> str:
    if not items:
        return "<p class=\"muted\">沒有可驗證資料。</p>"
    return _render_table([dict(item) for item in items])


def _metric_cards_from_kpis(kpis: list[Mapping[str, Any]]) -> str:
    values: dict[str, Any] = {}
    for kpi in kpis:
        label = str(kpi.get("label") or kpi.get("id") or "")
        if label:
            values[label] = kpi.get("value")
    return _render_kpi_grid(values) if values else "<p class=\"muted\">尚未產生 KPI 數值。</p>"


def _chart_mock(chart: Mapping[str, Any], rows: list[Mapping[str, Any]] | None = None) -> str:
    chart_id = str(chart.get("id") or chart.get("title") or "chart")
    chart_type = str(chart.get("type") or chart.get("chart_type") or "bar")
    purpose = str(chart.get("purpose") or chart.get("data_source") or "")
    bars = []
    if rows:
        numeric_columns = [
            key for key in rows[0].keys()
            if any(isinstance(row.get(key), (int, float)) for row in rows)
        ]
        label_key = next((key for key in rows[0].keys() if isinstance(rows[0].get(key), str)), "")
        value_key = next((key for key in numeric_columns if key in {"actual_amount", "budget_amount", "variance_amount", "amount"}), numeric_columns[0] if numeric_columns else "")
        max_value = max(
            (abs(float(row.get(value_key) or 0)) for row in rows if isinstance(row.get(value_key), (int, float))),
            default=1,
        ) or 1
        for index, row in enumerate(rows[:6]):
            raw_value = row.get(value_key)
            value = float(raw_value) if isinstance(raw_value, (int, float)) else 0
            height = max(8, abs(value) / max_value * 72)
            label = str(row.get(label_key) or f"Row {index + 1}")
            bars.append(
                "<div class=\"chart-bar-wrap\">"
                f"<span class=\"chart-value\">{escape(_format_scalar(raw_value))}</span>"
                f"<div class=\"chart-bar-fill\" style=\"height:{height:.1f}px\"></div>"
                f"<span class=\"chart-x-label\">{escape(label)}</span>"
                "</div>"
            )
    if not bars:
        bars = [
            "<div class=\"chart-bar-wrap\"><span class=\"chart-value\">A</span><div class=\"chart-bar-fill\" style=\"height:52px\"></div><span class=\"chart-x-label\">實際</span></div>",
            "<div class=\"chart-bar-wrap\"><span class=\"chart-value\">B</span><div class=\"chart-bar-fill muted-fill\" style=\"height:38px\"></div><span class=\"chart-x-label\">預算</span></div>",
            "<div class=\"chart-bar-wrap\"><span class=\"chart-value\">V</span><div class=\"chart-bar-fill alert-fill\" style=\"height:24px\"></div><span class=\"chart-x-label\">差異</span></div>",
        ]
    return (
        f"<article class=\"preview-chart\" data-chart-card data-chart-id=\"{escape(chart_id)}\" data-chart-type=\"{escape(chart_type)}\">"
        f"<div class=\"preview-card-head\"><strong>{escape(chart_id)}</strong><span>{escape(chart_type)}</span></div>"
        f"<p>{escape(purpose or '依目前資料產生可驗證圖表預覽。')}</p>"
        f"<div class=\"chart-render-note\">呈現方式：{escape(_chart_render_note(chart_type))}</div>"
        f"<div class=\"chart-mock\" role=\"img\" aria-label=\"{escape(chart_id)} preview\">{''.join(bars)}</div>"
        "</article>"
    )


def _chart_render_note(chart_type: str) -> str:
    return {
        "combo": "同一圖中比較實際、預算與差異，適合財務管控。",
        "bar": "用長條排序主要費用驅動項目，適合找最大影響來源。",
        "stacked-bar": "用堆疊長條看費用組成，適合比較分類占比。",
        "line": "用折線看期間趨勢，適合有月份或日期欄位時使用。",
    }.get(chart_type, "用目前資料欄位產生基本視覺比較。")


def _table_component_mock(table: Mapping[str, Any], rows: list[Mapping[str, Any]] | None = None) -> str:
    columns = _string_list(table.get("columns"))
    features = _string_list(table.get("features"))
    table_id = str(table.get("id") or "data-table")
    if rows:
        table_html = _render_table([dict(row) for row in rows], columns or None)
    elif columns:
        placeholder = {column: "..." for column in columns}
        table_html = _render_table([placeholder], columns)
    else:
        table_html = "<p class=\"muted\">尚未指定欄位。</p>"
    feature_tags = "".join(f"<span class=\"feature-tag\">{escape(feature)}</span>" for feature in features)
    return (
        "<article class=\"preview-table-component\">"
        f"<div class=\"preview-card-head\"><strong>{escape(table_id)}</strong><span>DataTable</span></div>"
        f"<div class=\"feature-row\">{feature_tags}</div>"
        f"{table_html}"
        "</article>"
    )


def _render_visual_controls(
    *,
    layout_mode: str,
    charts: list[Mapping[str, Any]],
    sections: list[str],
) -> str:
    chart_count = min(max(len(charts) or 1, 1), 4)
    layout_options = "".join(
        f"<option value=\"{escape(value)}\"{' selected' if value == layout_mode else ''}>{escape(label)}</option>"
        for value, label in LAYOUT_OPTIONS
    )
    count_options = "".join(
        f"<option value=\"{count}\"{' selected' if count == chart_count else ''}>{count} 張圖</option>"
        for count in range(1, 5)
    )
    chart_controls = []
    for index in range(4):
        chart = charts[index] if index < len(charts) else {}
        chart_id = str(chart.get("id") or f"chart-{index + 1}")
        chart_type = str(chart.get("type") or chart.get("chart_type") or CHART_TYPE_OPTIONS[index % len(CHART_TYPE_OPTIONS)][0])
        type_options = "".join(
            f"<option value=\"{escape(value)}\"{' selected' if value == chart_type else ''}>{escape(label)}</option>"
            for value, label in CHART_TYPE_OPTIONS
        )
        hidden = " hidden-control" if index >= chart_count else ""
        chart_controls.append(
            f"<label class=\"control-field chart-control{hidden}\" data-chart-control=\"{index}\">"
            f"<span>Chart {index + 1}</span>"
            f"<input data-chart-id=\"{index}\" value=\"{escape(chart_id)}\" aria-label=\"Chart {index + 1} id\">"
            f"<select data-chart-type=\"{index}\" aria-label=\"Chart {index + 1} type\">{type_options}</select>"
            "</label>"
        )
    return (
        "<div class=\"preview-controls\" data-preview-controls>"
        "<div class=\"control-group\">"
        "<label class=\"control-field\"><span>Layout</span>"
        f"<select data-layout-mode>{layout_options}</select></label>"
        "<label class=\"control-field\"><span>Chart 數量</span>"
        f"<select data-chart-count>{count_options}</select></label>"
        "</div>"
        "<div class=\"chart-control-grid\">"
        + "".join(chart_controls)
        + "</div>"
        f"<input type=\"hidden\" data-layout-sections value=\"{escape(json.dumps(sections, ensure_ascii=False))}\">"
        "<button type=\"button\" class=\"action-button secondary\" data-refresh-preview>Refresh HTML 預覽</button>"
        "<p class=\"muted\">調整 layout、chart 數量或 chart type 後，按 Refresh 會即時重繪下方 HTML 預覽；送出確認時會保存這些選擇。</p>"
        "</div>"
    )


def _render_component_preview(payload: Mapping[str, Any], *, checkpoint: str) -> str:
    layout = payload.get("layout_recipe") or payload.get("layout") or {}
    layout_map = layout if isinstance(layout, Mapping) else {}
    sections = _string_list(layout_map.get("sections"))
    charts = _mapping_list(payload.get("chart_recipe") or payload.get("charts"))
    tables = _mapping_list(payload.get("table_recipe") or payload.get("tables"))
    kpis = _mapping_list(payload.get("kpis"))
    visual_direction = payload.get("visual_direction")
    visual_map = visual_direction if isinstance(visual_direction, Mapping) else {}
    rows: list[Mapping[str, Any]] = []
    for table in tables:
        rows = _mapping_list(table.get("rows"))
        if rows:
            break
    summary = payload.get("summary")
    summary_map = summary if isinstance(summary, Mapping) else {}
    title = str(payload.get("title") or "報表預覽")
    if not kpis and summary_map:
        kpis = [{"label": key, "value": value} for key, value in summary_map.items() if not isinstance(value, (dict, list))]

    section_blocks = "".join(
        f"<div class=\"layout-zone\"><span>{escape(section)}</span></div>" for section in sections
    ) or "<div class=\"layout-zone\"><span>report-body</span></div>"
    charts_html = "".join(_chart_mock(chart, rows) for chart in charts)
    tables_html = "".join(_table_component_mock(table, rows if _mapping_list(table.get("rows")) else None) for table in tables)
    if not tables_html and rows:
        tables_html = _render_table([dict(row) for row in rows])
    analysis = payload.get("analysis")
    recommendations = payload.get("recommendations")
    content_blocks = ""
    if isinstance(analysis, list):
        content_blocks += f"<div class=\"preview-copy\"><h4>分析</h4>{_render_list(analysis)}</div>"
    if isinstance(recommendations, list):
        content_blocks += f"<div class=\"preview-copy\"><h4>建議</h4>{_render_list(recommendations)}</div>"

    tone = str(visual_map.get("tone") or "")
    emphasis = _string_list(visual_map.get("emphasis"))
    html_label = "HTML 報表預覽" if checkpoint == "report_draft" else "HTML 版面與元件預覽"
    layout_mode = str(layout_map.get("mode") or "kpi-first-dashboard")
    controls = _render_visual_controls(layout_mode=layout_mode, charts=charts, sections=sections)
    return (
        f"<div class=\"report-preview\" data-preview-kind=\"{escape(checkpoint)}\">"
        f"{controls}"
        "<div class=\"preview-toolbar\">"
        f"<span>{escape(html_label)}</span>"
        f"<strong>{escape(tone or 'financial-control')}</strong>"
        "</div>"
        "<div class=\"preview-report-shell\">"
        "<header class=\"preview-report-header\">"
        f"<p>WFERP Finance Report</p><h3>{escape(title)}</h3>"
        f"<div>{''.join(f'<span class=\"feature-tag\">{escape(item)}</span>' for item in emphasis)}</div>"
        "</header>"
        f"<section class=\"preview-layout-map\">{section_blocks}</section>"
        f"<section class=\"preview-kpis\">{_metric_cards_from_kpis(kpis)}</section>"
        f"<section class=\"preview-chart-grid\">{charts_html or '<p class=\"muted\">尚未配置圖表。</p>'}</section>"
        f"<section class=\"preview-table-grid\">{tables_html or '<p class=\"muted\">尚未配置資料表。</p>'}</section>"
        f"{content_blocks}"
        "</div>"
        "</div>"
    )


def _render_field_formula_checkpoint(payload: Mapping[str, Any]) -> str:
    details = payload.get("technical_details")
    details_map = details if isinstance(details, Mapping) else {}
    fields = _mapping_list(details_map.get("database_fields"))
    formulas = _mapping_list(details_map.get("derived_formula_fields"))
    defaults = details_map.get("recommended_defaults")
    html = []
    if fields:
        field_rows = [
            {
                "需求欄位": field.get("semantic_name"),
                "候選資料庫欄位": ", ".join(_string_list(field.get("candidate_columns"))),
                "狀態": field.get("status"),
            }
            for field in fields
        ]
        html.append("<h3>資料庫欄位來源驗證</h3>" + _render_table(field_rows))
    if formulas:
        formula_rows = [
            {"衍生欄位": formula.get("field"), "公式": formula.get("formula")}
            for formula in formulas
        ]
        html.append("<h3>Excel / 報表公式驗證</h3>" + _render_table(formula_rows))
    if isinstance(defaults, Mapping):
        html.append("<h3>預設資料來源與條件</h3>" + _render_key_values(dict(defaults)))
    return "".join(html) if html else _render_value(payload)


def _render_classification_checkpoint(payload: Mapping[str, Any]) -> str:
    columns = _mapping_list(payload.get("columns"))
    rows: list[dict[str, Any]] = []
    for column in columns:
        metadata_items = _mapping_list(column.get("field_metadata")) or _mapping_list(
            column.get("lineage_inputs")
        )
        if not metadata_items:
            rows.append(
                {
                    "Excel Header": column.get("excel_header"),
                    "Classification": column.get("classification"),
                    "Processing Location": column.get("processing_location"),
                    "Table Name": "",
                    "Column Name": "",
                    "ERP Code": "",
                    "Confidence": column.get("confidence"),
                    "Reason": column.get("reason"),
                }
            )
            continue
        for metadata in metadata_items:
            table_id = str(metadata.get("table_id") or "")
            column_id = str(metadata.get("column_id") or "")
            rows.append(
                {
                    "Excel Header": column.get("excel_header"),
                    "Classification": column.get("classification"),
                    "Processing Location": column.get("processing_location"),
                    "Table Name": metadata.get("table_name"),
                    "Column Name": metadata.get("column_name"),
                    "ERP Code": f"{table_id}.{column_id}" if table_id and column_id else "",
                    "Confidence": column.get("confidence"),
                    "Reason": column.get("reason") or metadata.get("business_meaning"),
                }
            )
    return _render_table(rows) if rows else _render_value(payload)


def _render_sqlite_preview(payload: Mapping[str, Any]) -> str:
    summary = {
        "Row Count": payload.get("row_count"),
        "Table": payload.get("table_name"),
        "SQLite DB": payload.get("sqlite_db_path"),
        "Columns": ", ".join(_string_list(payload.get("columns"))),
    }
    html = ["<h3>Preview Summary</h3>", _render_key_values(summary)]
    rows = payload.get("sample_rows")
    columns = payload.get("columns")
    if isinstance(rows, list):
        html.extend(
            [
                "<h3>Sample Rows</h3>",
                _render_table(rows, columns if isinstance(columns, list) else None),
            ]
        )
    aggregates = payload.get("aggregates")
    if isinstance(aggregates, Mapping):
        html.extend(["<h3>Aggregates</h3>", _render_kpi_grid(aggregates)])
    return "".join(html)


def _render_sqlite_retention(payload: Mapping[str, Any]) -> str:
    summary = {
        "Manifest Path": payload.get("manifest_path"),
        "SQLite DB": payload.get("sqlite_db_path"),
        "Default Action": payload.get("default_action", "保留本地資料"),
        "Retention Decision": payload.get("retention_decision"),
        "Cleanup Status": payload.get("cleanup_status"),
    }
    html = ["<h3>Retention Summary</h3>", _render_key_values(summary)]
    tables = payload.get("tables")
    if isinstance(tables, list):
        html.extend(["<h3>Manifest Tables</h3>", _render_table(tables)])
    return "".join(html)


def _render_payload_sections(checkpoint: str, payload: dict[str, Any]) -> str:
    sections: list[str] = []

    def add(title: str, html: str) -> None:
        if html:
            sections.append(f"<section class=\"panel\"><h2>{escape(title)}</h2>{html}</section>")

    if checkpoint == "excel_confirmation":
        add("欄位來源與公式驗證", _render_field_formula_checkpoint(payload))
        evidence = payload.get("validator_evidence")
        if isinstance(evidence, Mapping):
            add("Validator Evidence", _render_key_values(dict(evidence)))
    elif checkpoint == "field_formula_classification":
        add("欄位分類與 DB Metadata", _render_classification_checkpoint(payload))
    elif checkpoint == "sql_review":
        add("SQL", f"<pre class=\"code-block\"><code>{escape(str(payload.get('sql', '')))}</code></pre>")
        validation = payload.get("validation")
        if isinstance(validation, Mapping):
            add("Validator Evidence", _render_key_values(dict(validation)))
    elif checkpoint == "data_preview":
        aggregates = payload.get("aggregates")
        if isinstance(aggregates, Mapping):
            add("Aggregates", _render_kpi_grid(aggregates))
        rows = payload.get("rows")
        columns = payload.get("columns")
        if isinstance(rows, list):
            add("Data Preview", _render_table(rows, columns if isinstance(columns, list) else None))
        checks = payload.get("acceptance_checks")
        if isinstance(checks, Mapping):
            add("Acceptance Checks", _render_key_values(dict(checks)))
    elif checkpoint in {"raw_data_preview", "enriched_data_preview"}:
        add("SQLite Preview", _render_sqlite_preview(payload))
    elif checkpoint == "sqlite_retention":
        add("SQLite Retention", _render_sqlite_retention(payload))
    elif checkpoint == "report_selection":
        selected = {
            "selected_report_type": payload.get("selected_report_type"),
            "selected_report_design": payload.get("selected_report_design"),
            "selected_options": payload.get("selected_options"),
        }
        add("目前選擇", _render_key_values(selected))
        designs = payload.get("report_designs")
        if isinstance(designs, list):
            add("Design Candidates", _render_design_cards(designs))
        report_types = payload.get("report_types")
        if isinstance(report_types, list):
            add("Report Types", _render_list(report_types))
    elif checkpoint in {"design_brief", "visual_design"}:
        add("HTML 版面與元件預覽", _render_component_preview(payload, checkpoint=checkpoint))
        layout = payload.get("layout_recipe") or payload.get("layout")
        if isinstance(layout, Mapping):
            add("Layout 設定", _render_key_values(dict(layout)))
        charts = payload.get("chart_recipe") or payload.get("charts")
        if isinstance(charts, list):
            add("Chart 元件設定", _render_list(charts))
        tables = payload.get("table_recipe") or payload.get("tables")
        if isinstance(tables, list):
            add("Table 元件設定", _render_list(tables))
        kpis = payload.get("kpis")
        if isinstance(kpis, list):
            add("KPI 元件設定", _render_list(kpis))
        visual_direction = payload.get("visual_direction")
        if isinstance(visual_direction, Mapping):
            add("Visual Direction 設定", _render_key_values(dict(visual_direction)))
    elif checkpoint == "report_draft":
        add("HTML 報告初稿預覽", _render_component_preview(payload, checkpoint=checkpoint))
        summary = payload.get("summary")
        if isinstance(summary, Mapping):
            add("管理摘要", _render_kpi_grid(summary))
        charts = payload.get("charts")
        if isinstance(charts, list):
            add("圖表規劃", _render_list(charts))
        tables = payload.get("tables")
        if isinstance(tables, list):
            for table in tables:
                if isinstance(table, Mapping) and isinstance(table.get("rows"), list):
                    columns = table.get("columns")
                    add(
                        str(table.get("id") or "資料表"),
                        _render_table(table["rows"], columns if isinstance(columns, list) else None),
                    )
        analysis = payload.get("analysis")
        if isinstance(analysis, list):
            add("分析", _render_list(analysis))
        recommendations = payload.get("recommendations")
        if isinstance(recommendations, list):
            add("管理建議", _render_list(recommendations))
    elif checkpoint == "final_review":
        summary = payload.get("summary")
        if isinstance(summary, Mapping):
            add("Final Summary", _render_kpi_grid(summary))
        validators = payload.get("validator_results")
        if isinstance(validators, list):
            add("Validator Results", _render_validator_table(validators))
            role_prefixed_risks = _role_prefixed_residual_risks(validators)
            if role_prefixed_risks:
                add("Residual Risks", _render_risk_checkboxes(role_prefixed_risks))
        elif isinstance(payload.get("residual_risks"), list):
            add("Residual Risks", _render_risk_checkboxes(payload["residual_risks"]))
    else:
        add("Checkpoint Payload", _render_value(payload))

    rendered_keys = {
        "sql",
        "technical_details",
        "validator_evidence",
        "workbook_path",
        "primary_sheet",
        "lookup_sheet_inventory",
        "field_metadata",
        "validation",
        "aggregates",
        "rows",
        "sample_rows",
        "columns",
        "row_count",
        "table_name",
        "sqlite_db_path",
        "manifest_path",
        "default_action",
        "retention_decision",
        "cleanup_status",
        "acceptance_checks",
        "report_designs",
        "report_types",
        "layout_recipe",
        "layout",
        "chart_recipe",
        "charts",
        "table_recipe",
        "tables",
        "kpis",
        "visual_direction",
        "summary",
        "analysis",
        "recommendations",
        "validator_results",
        "residual_risks",
    }
    remaining = {key: value for key, value in payload.items() if key not in rendered_keys}
    if remaining:
        add("其他 Payload", _render_value(remaining))

    return "".join(sections)


def _render_kpi_grid(values: Mapping[str, Any]) -> str:
    cards = []
    for key, value in values.items():
        if isinstance(value, (dict, list)):
            continue
        cards.append(
            "<div class=\"kpi-card\">"
            f"<div class=\"kpi-label\">{escape(str(key))}</div>"
            f"<div class=\"kpi-value\">{escape(_format_scalar(value))}</div>"
            "</div>"
        )
    if not cards:
        return _render_key_values(values)
    return f"<div class=\"kpi-grid\">{''.join(cards)}</div>"


def _render_design_cards(designs: list[Any]) -> str:
    cards = []
    for design in designs:
        if not isinstance(design, Mapping):
            continue
        design_id = str(design.get("id") or design.get("label") or "")
        label = str(design.get("label") or design.get("name") or design_id)
        body = str(design.get("tone") or design.get("body") or design.get("description") or "")
        cards.append(
            "<div class=\"card\" data-choice=\""
            + escape(design_id)
            + "\" onclick=\"toggleSelect(this)\">"
            + f"<div class=\"card-body\"><h3>{escape(label)}</h3><p>{escape(body[:180])}</p></div>"
            + "</div>"
        )
    return f"<div class=\"cards\">{''.join(cards)}</div>" if cards else "<p class=\"muted\">沒有設計候選</p>"


def _render_validator_table(validators: list[Any]) -> str:
    rows = []
    for validator in validators:
        if not isinstance(validator, Mapping):
            continue
        rows.append(
            "<tr>"
            f"<td>{escape(str(validator.get('role', '')))}</td>"
            f"<td>{_render_badge(validator.get('status'))}</td>"
            f"<td>{escape('; '.join(str(item) for item in validator.get('findings', [])[:2]))}</td>"
            f"<td>{escape('; '.join(str(item) for item in validator.get('residualRisks', [])[:2]))}</td>"
            "</tr>"
        )
    return (
        "<div class=\"table-wrap\"><table><thead><tr>"
        "<th>Role</th><th>Status</th><th>Findings</th><th>Residual Risks</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
    )


def _role_prefixed_residual_risks(validators: list[Any]) -> list[str]:
    risks: list[str] = []
    for validator in validators:
        if not isinstance(validator, Mapping):
            continue
        role = str(validator.get("role") or "").strip()
        for risk in validator.get("residualRisks", []):
            risk_text = str(risk)
            if role and not risk_text.startswith(f"{role}: "):
                risks.append(f"{role}: {risk_text}")
            else:
                risks.append(risk_text)
    return risks


def _render_risk_checkboxes(risks: list[Any]) -> str:
    if not risks:
        return "<p class=\"muted\">沒有 residual risks</p>"
    return "<div class=\"risk-list\">" + "".join(
        "<label class=\"risk-item\">"
        f"<input type=\"checkbox\" data-risk=\"{escape(str(risk))}\" checked> "
        f"<span>{escape(str(risk))}</span>"
        "</label>"
        for risk in risks
    ) + "</div>"


def _render_progress(state: Mapping[str, Any], current: str, run_id: str) -> str:
    confirmed = state.get("user_confirmations")
    confirmed_map = confirmed if isinstance(confirmed, Mapping) else {}
    checkpoint_entries = state.get("checkpoints")
    available = {
        str(entry.get("checkpoint"))
        for entry in checkpoint_entries
        if isinstance(entry, Mapping) and entry.get("checkpoint")
    } if isinstance(checkpoint_entries, list) else set()
    items = []
    for key, definition in sorted(
        CHECKPOINT_DEFINITIONS.items(),
        key=lambda item: float(item[1]["index"]),
    ):
        css = "step"
        if key == current:
            css += " current"
        elif key in confirmed_map:
            css += " done"
        elif key not in available:
            css += " disabled"
        content = (
            f"<span class=\"step-index\">{escape(str(definition['index']))}</span>"
            f"<strong>{escape(definition['title'])}</strong>"
        )
        if key in available:
            content = (
                f"<a href=\"/runs/{escape(run_id)}/checkpoints/{escape(key)}\" "
                f"aria-label=\"開啟 {escape(definition['title'])}\">{content}</a>"
            )
        else:
            content = f"<div class=\"step-disabled\">{content}</div>"
        items.append(
            f"<li class=\"{css}\">{content}</li>"
        )
    return "<ol class=\"progress\">" + "".join(items) + "</ol>"


def _render_checkpoint_page(
    *,
    run_id: str,
    checkpoint: str,
    definition: Mapping[str, Any],
    checkpoint_payload: Mapping[str, Any],
    state: Mapping[str, Any],
) -> str:
    payload = checkpoint_payload.get("payload")
    payload_dict = payload if isinstance(payload, dict) else {}
    confirm_url = f"/api/runs/{run_id}/checkpoints/{checkpoint}/confirm"
    actions = "".join(
        f"<button type=\"button\" class=\"action-button\" data-action=\"{escape(action)}\">"
        f"{escape(action)}</button>"
        for action in definition["actions"]
    )
    confirmed_action = ""
    confirmations = state.get("user_confirmations")
    if isinstance(confirmations, Mapping) and checkpoint in confirmations:
        confirmed_action = str(confirmations[checkpoint])

    return "\n".join(
        [
            "<!doctype html>",
            "<html lang=\"zh-Hant\">",
            "<head>",
            "<meta charset=\"utf-8\">",
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
            f"<title>{escape(str(definition['title']))}</title>",
            "<style>",
            _COMPANION_CSS,
            "</style>",
            "</head>",
            "<body>",
            "<header class=\"topbar\">",
            "<div><p class=\"eyebrow\">WFERP Report Companion</p>",
            f"<h1>{escape(str(definition['title']))}</h1></div>",
            f"<div class=\"run-chip\">{escape(run_id)}</div>",
            "</header>",
            "<main class=\"shell\">",
            "<aside class=\"side-rail\">",
            _render_progress(state, checkpoint, run_id),
            "</aside>",
            f"<section class=\"content\" data-confirm-url=\"{escape(confirm_url)}\" "
            f"data-checkpoint=\"{escape(checkpoint)}\">",
            "<div class=\"hero panel\">",
            f"<p class=\"eyebrow\">Current checkpoint</p><h2>{escape(str(checkpoint_payload.get('title') or definition['title']))}</h2>",
            f"<p class=\"subtitle\">{escape(str(payload_dict.get('summary') or '請檢查此 checkpoint 的資料、證據與風險後再確認。'))}</p>",
            f"<div id=\"confirmation-status\" class=\"status-line\">"
            f"{'已確認：' + escape(confirmed_action) if confirmed_action else '尚未確認'}</div>",
            "</div>",
            _render_payload_sections(checkpoint, payload_dict),
            "<section class=\"panel sticky-actions\">",
            "<h2>確認動作</h2>",
            "<label class=\"comment-label\">補充意見</label>",
            "<textarea id=\"confirmation-comment\" placeholder=\"可留空；若需修正請描述條件或欄位。\"></textarea>",
            f"<div class=\"actions\">{actions}</div>",
            "</section>",
            "</section>",
            "</main>",
            "<script>",
            f"window.__CHECKPOINT_PAYLOAD__ = {_json_script_payload(dict(checkpoint_payload))};",
            _COMPANION_JS,
            "</script>",
            "</body>",
            "</html>",
        ]
    )


_COMPANION_CSS = """
*{box-sizing:border-box}html,body{margin:0;min-height:100%;font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f6f7f9;color:#17202a}body{line-height:1.5}.topbar{position:sticky;top:0;z-index:5;display:flex;justify-content:space-between;align-items:center;padding:16px 24px;background:#fff;border-bottom:1px solid #d9dee7}.topbar h1{font-size:20px;margin:2px 0 0}.eyebrow{margin:0;color:#667085;text-transform:uppercase;letter-spacing:.08em;font-size:11px;font-weight:700}.run-chip{font-size:12px;border:1px solid #d0d5dd;border-radius:999px;padding:6px 10px;background:#f9fafb;color:#475467}.shell{display:grid;grid-template-columns:280px minmax(0,1fr);gap:24px;padding:24px}.side-rail{position:sticky;top:82px;align-self:start}.progress{list-style:none;margin:0;padding:0;display:grid;gap:8px}.step{border:1px solid #d0d5dd;border-radius:8px;background:#fff;color:#667085}.step a,.step-disabled{display:flex;gap:10px;align-items:center;width:100%;padding:10px;color:inherit;text-decoration:none}.step a:hover{background:#f8fafc}.step.disabled{opacity:.48}.step-index{display:grid;place-items:center;width:26px;height:26px;border-radius:50%;background:#eef2f6;font-size:12px;flex:0 0 26px}.step strong{font-size:13px}.step.done{border-color:#9bd3b0;color:#176b3a}.step.done .step-index{background:#def7e7}.step.current{border-color:#2f6fed;box-shadow:0 0 0 3px rgba(47,111,237,.12);color:#17202a}.step.current .step-index{background:#2f6fed;color:#fff}.content{display:grid;gap:18px;max-width:1180px}.panel{background:#fff;border:1px solid #d9dee7;border-radius:10px;padding:18px;box-shadow:0 1px 2px rgba(16,24,40,.04)}.hero h2{font-size:28px;margin:4px 0 8px}.subtitle{color:#475467;margin:0}.status-line{margin-top:14px;padding:10px 12px;border-radius:8px;background:#f1f5ff;color:#2446a4;font-weight:600}h2{font-size:18px;margin:0 0 12px}h3{font-size:15px;margin:16px 0 8px}.kpi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}.kpi-card{border:1px solid #d9dee7;border-radius:8px;padding:14px;background:#fbfcfe}.kpi-label{font-size:12px;color:#667085}.kpi-value{font-size:24px;font-weight:750;margin-top:4px}.kv-grid{display:grid;gap:8px}.kv-row{display:grid;grid-template-columns:minmax(150px,240px) minmax(0,1fr);gap:12px;padding:9px 0;border-bottom:1px solid #eef1f5}.kv-row dt{font-weight:700;color:#344054}.kv-row dd{margin:0;min-width:0}.kv-value{overflow-wrap:anywhere}.nested-card{border:1px solid #e5e7ec;border-radius:8px;padding:12px;margin:8px 0;background:#fbfcfe}.clean-list{margin:0;padding-left:20px}.clean-list li{margin:6px 0}.table-wrap{overflow:auto;border:1px solid #d9dee7;border-radius:8px}table{border-collapse:collapse;width:100%;font-size:13px;background:#fff}th,td{padding:9px 10px;border-bottom:1px solid #edf0f5;text-align:left;vertical-align:top;white-space:nowrap}th{background:#f8fafc;color:#344054;font-weight:750}.table-note,.muted{color:#667085}.code-block{margin:0;white-space:pre-wrap;overflow:auto;background:#111827;color:#f9fafb;border-radius:8px;padding:14px;font-size:13px}.badge{display:inline-flex;border-radius:999px;padding:3px 8px;font-size:12px;font-weight:700}.badge-pass{background:#dcfae6;color:#067647}.badge-fail{background:#fee4e2;color:#b42318}.badge-warning{background:#fef0c7;color:#b54708}.badge-neutral{background:#eef2f6;color:#475467}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}.card{border:1px solid #d9dee7;border-radius:8px;background:#fbfcfe;cursor:pointer}.card:hover,.card.selected{border-color:#2f6fed;box-shadow:0 0 0 3px rgba(47,111,237,.12)}.card-body{padding:14px}.card h3{margin:0 0 6px}.card p{margin:0;color:#667085}.report-preview{border:1px solid #b8c7dc;border-radius:10px;background:#eef3f7;padding:10px}.preview-toolbar{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:6px 4px 12px;color:#344054;font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:.06em}.preview-report-shell{background:#fff;border:1px solid #d6dde7;border-radius:8px;padding:18px;box-shadow:0 10px 28px rgba(23,32,42,.08)}.preview-report-header{display:grid;gap:6px;border-bottom:1px solid #e6ebf2;padding-bottom:14px;margin-bottom:14px}.preview-report-header p{margin:0;color:#667085;font-size:12px;font-weight:800;text-transform:uppercase}.preview-report-header h3{font-size:24px;margin:0}.feature-tag{display:inline-flex;margin:3px 5px 3px 0;border:1px solid #cbd5e1;border-radius:999px;padding:3px 8px;background:#f8fafc;color:#334155;font-size:12px;font-weight:700}.preview-layout-map{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin:14px 0}.layout-zone{min-height:58px;border:1px dashed #9fb1c7;border-radius:8px;background:#f8fafc;display:grid;place-items:center;color:#475467;font-weight:750}.preview-kpis{margin:14px 0}.preview-chart-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;margin:14px 0}.preview-chart,.preview-table-component,.preview-copy{border:1px solid #d9dee7;border-radius:8px;background:#fbfcfe;padding:14px}.preview-card-head{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-bottom:8px}.preview-card-head span{color:#667085;font-size:12px;font-weight:800;text-transform:uppercase}.preview-chart p{min-height:38px;margin:0 0 10px;color:#667085}.chart-mock{height:142px;display:flex;align-items:end;gap:12px;border:1px solid #e4e9f1;border-radius:8px;background:linear-gradient(180deg,#fff,#f8fafc);padding:12px 12px 24px}.chart-bar-wrap{display:grid;grid-template-rows:auto 1fr auto;align-items:end;justify-items:center;min-width:42px;flex:1;height:100%}.chart-value{font-size:11px;color:#667085}.chart-bar-fill{width:100%;max-width:46px;background:#286b7a;border-radius:5px 5px 0 0}.muted-fill{background:#91a4b7}.alert-fill{background:#c45f3c}.chart-x-label{font-size:11px;color:#475467;margin-top:6px;max-width:76px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.preview-table-grid{display:grid;gap:12px}.feature-row{margin-bottom:8px}.preview-copy{margin-top:12px}.preview-copy h4{margin:0 0 8px}.risk-list{display:grid;gap:8px}.risk-item{display:flex;gap:8px;align-items:flex-start;padding:10px;border:1px solid #f2d596;background:#fff9eb;border-radius:8px}.sticky-actions{position:sticky;bottom:0;border-color:#b9c7e8}.comment-label{display:block;font-weight:700;margin-bottom:6px}textarea{width:100%;min-height:78px;resize:vertical;border:1px solid #d0d5dd;border-radius:8px;padding:10px;font:inherit}.actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:12px}.action-button{border:0;border-radius:8px;background:#2f6fed;color:#fff;font-weight:750;padding:10px 14px;cursor:pointer}.action-button:hover{background:#245bd0}.action-button.secondary{background:#eef2f6;color:#344054}@media(max-width:860px){.shell{grid-template-columns:1fr}.side-rail{position:static}.topbar{align-items:flex-start;gap:10px;flex-direction:column}.kv-row{grid-template-columns:1fr}th,td{white-space:normal}.chart-mock{overflow:auto}.preview-report-header h3{font-size:20px}}
"""

_COMPANION_CSS += """
.preview-controls{border:1px solid #c8d4e3;border-radius:8px;background:#fff;padding:12px;margin-bottom:12px}
.control-group,.chart-control-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px}
.control-field{display:grid;gap:5px}
.control-field span{font-size:12px;font-weight:800;color:#475467}
.control-field input,.control-field select{border:1px solid #cbd5e1;border-radius:7px;background:#fff;padding:8px;font:inherit}
.hidden-control{display:none}
.chart-render-note{font-size:12px;color:#475467;background:#eef6f6;border:1px solid #d1e3e4;border-radius:7px;padding:7px;margin:8px 0}
"""


_COMPANION_JS = """
function toggleSelect(el){
  const container = el.closest('.cards');
  if(container){ container.querySelectorAll('.card').forEach(card => card.classList.remove('selected')); }
  el.classList.add('selected');
}

function chartRenderNote(type){
  const notes = {
    'combo': '同一圖中比較實際、預算與差異，適合財務管控。',
    'bar': '用長條排序主要費用驅動項目，適合找最大影響來源。',
    'stacked-bar': '用堆疊長條看費用組成，適合比較分類占比。',
    'line': '用折線看期間趨勢，適合有月份或日期欄位時使用。'
  };
  return notes[type] || '用目前資料欄位產生基本視覺比較。';
}

function layoutSections(mode, fallback){
  const map = {
    'kpi-first-dashboard': ['executive-summary', 'kpi-overview', 'expense-trend', 'exception-review', 'data-table'],
    'four-chart-grid': ['kpi-overview', 'chart-grid-2x2', 'exception-review', 'data-table'],
    'executive-one-page': ['decision-summary', 'kpi-strip', 'key-chart', 'recommendations'],
    'detail-audit': ['query-scope', 'detail-table', 'exception-list', 'audit-notes']
  };
  return map[mode] || fallback || ['report-body'];
}

function readVisualSelection(){
  const root = document.querySelector('[data-preview-controls]');
  if (!root) return {};
  const chartCount = Number(root.querySelector('[data-chart-count]')?.value || 0);
  const layoutMode = root.querySelector('[data-layout-mode]')?.value || '';
  const charts = [];
  for (let index = 0; index < chartCount; index += 1) {
    charts.push({
      id: root.querySelector(`[data-chart-id="${index}"]`)?.value || `chart-${index + 1}`,
      type: root.querySelector(`[data-chart-type="${index}"]`)?.value || 'bar'
    });
  }
  return { layoutMode, chartCount, charts };
}

function refreshPreview(){
  const root = document.querySelector('[data-preview-controls]');
  const preview = document.querySelector('.report-preview');
  if (!root || !preview) return;
  const selection = readVisualSelection();
  root.querySelectorAll('[data-chart-control]').forEach((control) => {
    const index = Number(control.dataset.chartControl || 0);
    control.classList.toggle('hidden-control', index >= selection.chartCount);
  });
  let fallback = [];
  try {
    fallback = JSON.parse(root.querySelector('[data-layout-sections]')?.value || '[]');
  } catch (_error) {
    fallback = [];
  }
  const layout = preview.querySelector('.preview-layout-map');
  if (layout) {
    layout.innerHTML = layoutSections(selection.layoutMode, fallback)
      .map((section) => `<div class="layout-zone"><span>${section}</span></div>`)
      .join('');
  }
  const chartGrid = preview.querySelector('.preview-chart-grid');
  if (chartGrid) {
    chartGrid.innerHTML = selection.charts.map((chart) => `
      <article class="preview-chart" data-chart-card data-chart-id="${chart.id}" data-chart-type="${chart.type}">
        <div class="preview-card-head"><strong>${chart.id}</strong><span>${chart.type}</span></div>
        <p>依目前 prompt 與選擇產生 ${chart.type} 圖表預覽。</p>
        <div class="chart-render-note">呈現方式：${chartRenderNote(chart.type)}</div>
        <div class="chart-mock" role="img" aria-label="${chart.id} preview">
          <div class="chart-bar-wrap"><span class="chart-value">A</span><div class="chart-bar-fill" style="height:62px"></div><span class="chart-x-label">實際</span></div>
          <div class="chart-bar-wrap"><span class="chart-value">B</span><div class="chart-bar-fill muted-fill" style="height:46px"></div><span class="chart-x-label">預算</span></div>
          <div class="chart-bar-wrap"><span class="chart-value">V</span><div class="chart-bar-fill alert-fill" style="height:30px"></div><span class="chart-x-label">差異</span></div>
        </div>
      </article>
    `).join('');
  }
}

function selectedOptions(){
  const options = {};
  document.querySelectorAll('[data-choice].selected').forEach((el) => {
    options.choice = el.dataset.choice || '';
  });
  const visualSelection = readVisualSelection();
  if (visualSelection.layoutMode) {
    options.visualSelection = visualSelection;
  }
  const acceptedRisks = Array.from(document.querySelectorAll('[data-risk]:checked')).map((el) => {
    const risk = el.getAttribute('data-risk') || '';
    const checkpoint = document.querySelector('[data-checkpoint]')?.dataset.checkpoint || '';
    if (checkpoint === 'final_review' && !risk.includes(':')) {
      return risk;
    }
    return risk;
  });
  if (acceptedRisks.length) {
    options.acceptedResidualRisks = acceptedRisks;
  }
  return options;
}

async function confirmCheckpoint(action){
  const root = document.querySelector('[data-confirm-url]');
  const status = document.getElementById('confirmation-status');
  const confirmUrl = root.dataset.confirmUrl;
  const checkpoint = root.dataset.checkpoint;
  const comment = document.getElementById('confirmation-comment')?.value || '';
  status.textContent = '送出確認中...';
  try {
    const response = await fetch(confirmUrl, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        checkpointId: checkpoint,
        action,
        comment,
        selectedOptions: selectedOptions()
      })
    });
    const body = await response.json();
    if (!response.ok) {
      status.textContent = '確認失敗：' + (body.error || body.status || response.status);
      status.classList.add('error');
      return;
    }
    status.textContent = '已確認：' + action;
    status.classList.remove('error');
    status.classList.add('confirmed');
  } catch (error) {
    status.textContent = '確認失敗：' + error;
    status.classList.add('error');
  }
}

document.addEventListener('click', (event) => {
  const choice = event.target.closest('[data-choice]');
  if (choice) toggleSelect(choice);
  const refresh = event.target.closest('[data-refresh-preview]');
  if (refresh) refreshPreview();
  const action = event.target.closest('[data-action]');
  if (action) confirmCheckpoint(action.dataset.action);
});

document.addEventListener('change', (event) => {
  if (event.target.closest('[data-preview-controls]')) refreshPreview();
});
"""


class CheckpointCompanionServer:
    @staticmethod
    @contextmanager
    def serve(
        run_dir: str | Path,
        host: str = "127.0.0.1",
        port: int = 0,
    ) -> Iterator[RunningCheckpointServer]:
        run_path = Path(run_dir)

        class Handler(BaseHTTPRequestHandler):
            def _json(self, status: int, payload: dict[str, Any]) -> None:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _html(self, status: int, body: str) -> None:
                content = body.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)

            def _path_parts(self) -> list[str]:
                return [part for part in urlparse(self.path).path.split("/") if part]

            def _read_json(self) -> dict[str, Any] | None:
                try:
                    content_length = int(self.headers.get("Content-Length", ""))
                except ValueError:
                    self._json(400, {"status": "bad_request"})
                    return None

                if content_length > MAX_REQUEST_BYTES:
                    self._json(413, {"status": "request_too_large"})
                    return None

                try:
                    raw_body = self.rfile.read(content_length)
                    payload = json.loads(raw_body.decode("utf-8"))
                except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
                    self._json(400, {"status": "bad_request"})
                    return None
                if not isinstance(payload, dict):
                    self._json(400, {"status": "bad_request"})
                    return None
                return payload

            def do_GET(self) -> None:
                parts = self._path_parts()
                if len(parts) != 4 or parts[:1] != ["runs"] or parts[2] != "checkpoints":
                    self._json(404, {"status": "not_found"})
                    return

                run_id = parts[1]
                requested_checkpoint = parts[3]
                if run_path.name != run_id:
                    self._json(409, {"status": "wrong_run"})
                    return

                state = load_run_state(run_path)
                checkpoints = state.get("checkpoints", [])
                if not checkpoints:
                    self._json(404, {"status": "no_checkpoint"})
                    return

                if requested_checkpoint == "current":
                    checkpoint_entry = checkpoints[-1]
                else:
                    checkpoint_entry = next(
                        (
                            entry for entry in checkpoints
                            if isinstance(entry, Mapping)
                            and entry.get("checkpoint") == requested_checkpoint
                        ),
                        None,
                    )
                    if checkpoint_entry is None:
                        self._json(404, {"status": "checkpoint_not_found"})
                        return

                checkpoint = checkpoint_entry["checkpoint"]
                definition = CHECKPOINT_DEFINITIONS[checkpoint]
                checkpoint_file = run_path / checkpoint_entry["file"]
                try:
                    checkpoint_payload = json.loads(checkpoint_file.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    self._json(500, {"status": "checkpoint_unreadable"})
                    return

                self._html(
                    200,
                    _render_checkpoint_page(
                        run_id=run_id,
                        checkpoint=checkpoint,
                        definition=definition,
                        checkpoint_payload=checkpoint_payload,
                        state=state,
                    ),
                )

            def do_POST(self) -> None:
                parts = self._path_parts()
                if (
                    len(parts) != 6
                    or parts[:2] != ["api", "runs"]
                    or parts[3] != "checkpoints"
                    or parts[5] != "confirm"
                ):
                    self._json(404, {"status": "not_found"})
                    return

                run_id = parts[2]
                checkpoint = parts[4]
                if run_path.name != run_id:
                    self._json(409, {"status": "wrong_run"})
                    return

                try:
                    payload = self._read_json()
                    if payload is None:
                        return
                    action = payload["action"]
                    if payload.get("checkpointId", checkpoint) != checkpoint:
                        self._json(409, {"status": "wrong_checkpoint"})
                        return

                    harness = ReportHarness(run_path)
                    selected_options = payload.get("selectedOptions")
                    harness.confirm(
                        checkpoint,
                        action,
                        selected_options=selected_options if isinstance(selected_options, dict) else None,
                    )
                    confirmation = write_confirmation(run_path, checkpoint, payload)
                    append_audit_event(
                        run_path,
                        "checkpoint_confirmed",
                        {"checkpoint": checkpoint, "action": action},
                    )
                except (KeyError, json.JSONDecodeError):
                    self._json(400, {"status": "bad_request"})
                    return
                except (ReportHarnessError, ValueError) as error:
                    self._json(400, {"status": "rejected", "error": str(error)})
                    return

                self._json(200, {"status": "confirmed", "confirmation": confirmation})

            def log_message(self, format: str, *args: object) -> None:
                return

        httpd = CheckpointHTTPServer((host, port), Handler)
        thread = Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        running = RunningCheckpointServer(
            httpd=httpd,
            thread=thread,
            base_url=f"http://{host}:{httpd.server_address[1]}",
        )
        try:
            yield running
        finally:
            httpd.shutdown()
            thread.join(timeout=5)
            httpd.server_close()

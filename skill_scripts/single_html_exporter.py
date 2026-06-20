from __future__ import annotations

import base64
import gzip
import hashlib
from html import escape
import json
from pathlib import Path
from typing import Any, Mapping

from skill_scripts.report_package import validate_report_package
from skill_scripts.style_replay import build_style_capsule


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _package_hash(package: Mapping[str, Any]) -> str:
    hashes = package.get("hashes")
    package_sha = hashes.get("package_sha256") if isinstance(hashes, Mapping) else None
    if isinstance(package_sha, str) and package_sha:
        return package_sha
    return hashlib.sha256(_canonical_json(package).encode("utf-8")).hexdigest()


def _sql_text(package: Mapping[str, Any]) -> str:
    sql = package.get("sql")
    if isinstance(sql, Mapping):
        return str(sql.get("text") or "")
    return ""


def _report_title(package: Mapping[str, Any], brief: Mapping[str, Any]) -> str:
    for source in (brief, package):
        for key in ("title", "report_title"):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    prompt = str(package.get("prompt") or "")
    if "費用" in prompt:
        return "費用分析管理報表"
    report_type = package.get("report_type") or package.get("catalog_guardrail")
    if isinstance(report_type, str) and report_type.strip():
        return f"{report_type.strip()} 管理報表"
    return "WFERP 管理報表"


def _row_count(package: Mapping[str, Any]) -> int:
    data_profile = package.get("data_profile")
    if isinstance(data_profile, Mapping):
        value = data_profile.get("row_count")
        if isinstance(value, int) and value >= 0:
            return value
    datasets = package.get("datasets")
    rows = datasets.get("embedded_rows") if isinstance(datasets, Mapping) else None
    return len(rows) if isinstance(rows, list) else 0


def _embedded_rows(package: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    datasets = package.get("datasets")
    rows = datasets.get("embedded_rows") if isinstance(datasets, Mapping) else None
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, Mapping)]


def _columns(package: Mapping[str, Any]) -> list[str]:
    data_profile = package.get("data_profile")
    if isinstance(data_profile, Mapping) and isinstance(data_profile.get("columns"), list):
        return [str(column) for column in data_profile["columns"]]
    datasets = package.get("datasets")
    dataset_columns = datasets.get("columns") if isinstance(datasets, Mapping) else None
    if isinstance(dataset_columns, list):
        return [str(column) for column in dataset_columns]
    columns: list[str] = []
    for row in _embedded_rows(package):
        for key in row:
            key_text = str(key)
            if key_text not in columns:
                columns.append(key_text)
    return columns


def _aggregates(package: Mapping[str, Any]) -> Mapping[str, Any]:
    aggregates = package.get("aggregates")
    return aggregates if isinstance(aggregates, Mapping) else {}


def _format_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (int, float)):
        if isinstance(value, float) and abs(value) <= 1:
            return f"{value:.2f}"
        return f"{value:,.0f}" if float(value).is_integer() else f"{value:,.2f}"
    return str(value)


def _first_text_column(columns: list[str], rows: list[Mapping[str, Any]]) -> str | None:
    for column in columns:
        if any(isinstance(row.get(column), str) for row in rows):
            return column
    return columns[0] if columns else None


def _first_numeric_column(columns: list[str], rows: list[Mapping[str, Any]]) -> str | None:
    preferred = ["amount", "variance_amount", "budget_amount"]
    for column in preferred:
        if column in columns and any(isinstance(row.get(column), (int, float)) for row in rows):
            return column
    for column in columns:
        if any(isinstance(row.get(column), (int, float)) for row in rows):
            return column
    return None


def _chart_data(columns: list[str], rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    label_column = _first_text_column(columns, rows)
    value_column = _first_numeric_column(columns, rows)
    if not label_column or not value_column:
        return []
    totals: dict[str, float] = {}
    for row in rows:
        label = str(row.get(label_column) or "未分類")
        raw_value = row.get(value_column)
        value = float(raw_value) if isinstance(raw_value, (int, float)) else 0
        totals[label] = totals.get(label, 0) + value
    return [{"label": label, "value": value} for label, value in totals.items()]


def _render_kpi_cards(package: Mapping[str, Any]) -> str:
    aggregates = _aggregates(package)
    kpis = [
        ("資料筆數", _row_count(package)),
        ("總費用", aggregates.get("total_amount")),
        ("總預算", aggregates.get("total_budget")),
        ("預算差異", aggregates.get("variance_amount")),
        ("最高費用占比", aggregates.get("max_expense_ratio")),
    ]
    cards = []
    for label, value in kpis:
        if value is None:
            continue
        cards.append(
            f'<article class="kpi-card"><span>{escape(label)}</span><strong>{escape(_format_value(value))}</strong></article>'
        )
    return "\n".join(cards)


def _render_chart(chart_data: list[dict[str, Any]]) -> str:
    if not chart_data:
        return '<p class="muted">目前資料不足以產生圖表。</p>'
    width = 760
    height = 300
    plot_bottom = 238
    plot_top = 34
    plot_height = plot_bottom - plot_top
    max_value = max((datum["value"] for datum in chart_data), default=1) or 1
    step = width / len(chart_data)
    bars = []
    labels = []
    for index, datum in enumerate(chart_data):
        value = datum["value"]
        bar_height = max(2, (value / max_value) * plot_height)
        x = step * index + step * 0.22
        y = plot_bottom - bar_height
        bar_width = max(step * 0.56, 18)
        label_x = step * index + step / 2
        bars.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_width:.2f}" height="{bar_height:.2f}" rx="4" '
            f'class="chart-bar"><title>{escape(str(datum["label"]))}: {escape(_format_value(value))}</title></rect>'
        )
        labels.append(
            f'<text x="{label_x:.2f}" y="272" text-anchor="middle" class="chart-label">{escape(str(datum["label"]))}</text>'
        )
    return (
        f'<svg class="chart-svg" viewBox="0 0 {width} {height}" role="img" aria-label="費用圖表證明">'
        f'<line x1="0" x2="{width}" y1="{plot_bottom}" y2="{plot_bottom}" class="chart-axis" />'
        + "".join(bars)
        + "".join(labels)
        + "</svg>"
    )


def _render_table(columns: list[str], rows: list[Mapping[str, Any]]) -> str:
    if not columns or not rows:
        return '<p class="muted">沒有可呈現的明細資料。</p>'
    header = "".join(f"<th>{escape(column)}</th>" for column in columns)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{escape(_format_value(row.get(column)))}</td>" for column in columns)
        body_rows.append(f"<tr>{cells}</tr>")
    return f'<div class="table-wrap"><table aria-label="費用明細資料表"><thead><tr>{header}</tr></thead><tbody>{"".join(body_rows)}</tbody></table></div>'


def _render_analysis(package: Mapping[str, Any]) -> str:
    aggregates = _aggregates(package)
    total_amount = aggregates.get("total_amount")
    total_budget = aggregates.get("total_budget")
    variance = aggregates.get("variance_amount")
    max_ratio = aggregates.get("max_expense_ratio")
    rows = _embedded_rows(package)
    highest = max(rows, key=lambda row: float(row.get("amount", 0) or 0), default={})
    highest_text = ""
    if highest:
        subject = highest.get("expense_subject") or highest.get("department_name") or highest.get("department") or "最高項目"
        highest_text = f"最高費用項目為 {escape(str(subject))}，金額 {escape(_format_value(highest.get('amount')))}。"
    parts = [
        f"本次查詢回傳 {_row_count(package)} 筆資料。",
        f"總費用 {escape(_format_value(total_amount))}，總預算 {escape(_format_value(total_budget))}，差異 {escape(_format_value(variance))}。",
    ]
    if max_ratio is not None:
        parts.append(f"最高費用占比為 {escape(_format_value(max_ratio))}，可作為優先追蹤依據。")
    if highest_text:
        parts.append(highest_text)
    return " ".join(parts)


def _render_recommendations(package: Mapping[str, Any]) -> str:
    aggregates = _aggregates(package)
    variance = aggregates.get("variance_amount")
    recommendations = [
        "針對高費用與高差異項目建立月度追蹤清單。",
        "保留 SQL、資料預覽與 validator evidence，讓管理數字可追溯。",
    ]
    if isinstance(variance, (int, float)) and variance > 0:
        recommendations.insert(0, "本期費用高於預算，建議優先檢視超支部門與科目。")
    return "".join(f"<li>{escape(item)}</li>" for item in recommendations)


def _validator_status(package: Mapping[str, Any]) -> str:
    summary = package.get("validator_summary")
    if not isinstance(summary, list) or not summary:
        return "unknown"
    statuses = [item.get("status") for item in summary if isinstance(item, Mapping)]
    if statuses and all(status == "pass" for status in statuses):
        return "pass"
    if any(status in {"fail", "error"} for status in statuses):
        return "fail"
    return str(statuses[0]) if statuses else "unknown"


def _encoded_payload(package: Mapping[str, Any], brief: Mapping[str, Any]) -> str:
    payload = {"package": package, "brief": brief}
    compressed = gzip.compress(_canonical_json(payload).encode("utf-8"))
    return base64.b64encode(compressed).decode("ascii")


def _render_html(package: Mapping[str, Any], brief: Mapping[str, Any]) -> str:
    encoded = _encoded_payload(package, brief)
    title = _report_title(package, brief)
    prompt = str(package.get("prompt") or "")
    sql_text = _sql_text(package)
    rows = _embedded_rows(package)
    columns = _columns(package)
    chart_data = _chart_data(columns, rows)
    column_text = ", ".join(columns) if columns else "No columns provided"
    escaped_title = escape(title)
    escaped_prompt = escape(prompt)
    escaped_sql = escape(sql_text)
    escaped_column_text = escape(column_text)
    kpi_cards = _render_kpi_cards(package)
    chart = _render_chart(chart_data)
    table = _render_table(columns, rows)
    analysis = _render_analysis(package)
    recommendations = _render_recommendations(package)
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_title}</title>
  <style>
    body {{
      margin: 0;
      font-family: Arial, "Noto Sans TC", sans-serif;
      color: #172033;
      background: #f4f6f8;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 32px 24px 48px;
    }}
    section {{
      background: #ffffff;
      border: 1px solid #dde3ea;
      border-radius: 6px;
      margin-top: 16px;
      padding: 20px;
      box-shadow: 0 8px 24px rgba(31, 44, 63, 0.06);
    }}
    h1 {{
      font-size: 30px;
      margin: 0 0 8px;
    }}
    h2 {{
      font-size: 18px;
      margin: 0 0 12px;
    }}
    .subtitle, .muted {{
      color: #5f6d7f;
    }}
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 12px;
    }}
    .kpi-card {{
      border: 1px solid #d7dee7;
      border-left: 5px solid #286b7a;
      border-radius: 6px;
      padding: 14px;
      background: #fbfcfd;
    }}
    .kpi-card span {{
      display: block;
      color: #607086;
      font-size: 12px;
      font-weight: 700;
      margin-bottom: 6px;
    }}
    .kpi-card strong {{
      display: block;
      color: #152236;
      font-size: 24px;
    }}
    .chart-svg {{
      width: 100%;
      min-height: 280px;
      border: 1px solid #d7dee7;
      border-radius: 6px;
      background: #ffffff;
    }}
    .chart-bar {{
      fill: #286b7a;
    }}
    .chart-axis {{
      stroke: #9aa8b7;
      stroke-width: 1;
    }}
    .chart-label {{
      fill: #314158;
      font-size: 12px;
      font-weight: 700;
    }}
    .table-wrap {{
      overflow: auto;
      border: 1px solid #d7dee7;
      border-radius: 6px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th, td {{
      padding: 10px 12px;
      border-bottom: 1px solid #e4eaf1;
      text-align: left;
      white-space: nowrap;
    }}
    th {{
      color: #25364b;
      background: #eef3f7;
      font-weight: 760;
    }}
    .analysis-text {{
      color: #38485d;
      font-size: 15px;
      line-height: 1.7;
    }}
    .recommendations li {{
      margin-top: 8px;
      color: #38485d;
      line-height: 1.6;
    }}
    pre {{
      white-space: pre-wrap;
      background: #111827;
      color: #f9fafb;
      padding: 16px;
      border-radius: 6px;
      overflow-wrap: anywhere;
    }}
  </style>
</head>
<body>
  <main>
    <h1>{escaped_title}</h1>
    <p class="subtitle">{escaped_prompt}</p>
    <section>
      <h2>管理摘要</h2>
      <div class="kpi-grid">{kpi_cards}</div>
      <p class="muted">資料欄位：{escaped_column_text}</p>
    </section>
    <section>
      <h2>圖表證明</h2>
      {chart}
    </section>
    <section>
      <h2>管理分析</h2>
      <p class="analysis-text">{analysis}</p>
    </section>
    <section>
      <h2>建議事項</h2>
      <ol class="recommendations">{recommendations}</ol>
    </section>
    <section>
      <h2>資料明細</h2>
      {table}
    </section>
    <section>
      <h2>Query</h2>
      <pre>{escaped_sql}</pre>
    </section>
  </main>
  <script>
    window.__WFERP_REPORT_PACKAGE__ = "{encoded}";
    window.__WFERP_REPORT_PACKAGE_ENCODING__ = "gzip+base64";
  </script>
</body>
</html>
"""


def export_single_html_report(
    output_root: str | Path,
    package: dict[str, Any],
    brief: dict[str, Any],
) -> dict[str, Any]:
    package_result = validate_report_package(package)
    if not package_result["valid"]:
        return {"status": "error", "errors": package_result["errors"]}

    output_path = Path(output_root)
    delivery_dir = output_path / "delivery"
    evidence_dir = delivery_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    package_text = _pretty_json(package)
    brief_text = _pretty_json(brief)
    style_capsule = build_style_capsule(brief)
    sql_text = _sql_text(package)
    (evidence_dir / "report-package.json").write_text(package_text, encoding="utf-8")
    (evidence_dir / "report-design-brief.json").write_text(brief_text, encoding="utf-8")
    (evidence_dir / "report-style-capsule.json").write_text(_pretty_json(style_capsule), encoding="utf-8")
    (evidence_dir / "query.sql").write_text(sql_text + ("\n" if sql_text else ""), encoding="utf-8")

    html_path = delivery_dir / "report.html"
    html_text = _render_html(package, brief)
    html_path.write_text(html_text, encoding="utf-8")
    html_sha256 = _sha256_text(html_text)

    manifest = {
        "html_path": str(html_path),
        "html_sha256": html_sha256,
        "package_sha256": _package_hash(package),
        "catalog_guardrail": package.get("catalog_guardrail"),
        "row_count": _row_count(package),
        "validator_status": _validator_status(package),
        "style_fingerprint": style_capsule["style_fingerprint"],
    }
    (delivery_dir / "delivery-manifest.json").write_text(_pretty_json(manifest), encoding="utf-8")

    return {"status": "exported", "html_path": str(html_path), "html_sha256": html_sha256}

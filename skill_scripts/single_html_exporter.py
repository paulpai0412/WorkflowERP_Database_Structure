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


def _row_count(package: Mapping[str, Any]) -> int:
    data_profile = package.get("data_profile")
    if isinstance(data_profile, Mapping):
        value = data_profile.get("row_count")
        if isinstance(value, int) and value >= 0:
            return value
    datasets = package.get("datasets")
    rows = datasets.get("embedded_rows") if isinstance(datasets, Mapping) else None
    return len(rows) if isinstance(rows, list) else 0


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
    title = str(brief.get("title") or package.get("report_type") or "WFERP Report")
    prompt = str(package.get("prompt") or "")
    row_count = _row_count(package)
    sql_text = _sql_text(package)
    columns = []
    data_profile = package.get("data_profile")
    if isinstance(data_profile, Mapping) and isinstance(data_profile.get("columns"), list):
        columns = [str(column) for column in data_profile["columns"]]
    column_text = ", ".join(columns) if columns else "No columns provided"
    escaped_title = escape(title)
    escaped_prompt = escape(prompt)
    escaped_sql = escape(sql_text)
    escaped_column_text = escape(column_text)
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
      color: #17202a;
      background: #f6f7f9;
    }}
    main {{
      max-width: 960px;
      margin: 0 auto;
      padding: 40px 24px;
    }}
    section {{
      background: #ffffff;
      border: 1px solid #dde3ea;
      border-radius: 8px;
      margin-top: 16px;
      padding: 20px;
    }}
    h1 {{
      font-size: 30px;
      margin: 0 0 8px;
    }}
    h2 {{
      font-size: 18px;
      margin: 0 0 12px;
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
    <p>{escaped_prompt}</p>
    <section>
      <h2>Report Summary</h2>
      <p>Rows: {row_count}</p>
      <p>Columns: {escaped_column_text}</p>
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

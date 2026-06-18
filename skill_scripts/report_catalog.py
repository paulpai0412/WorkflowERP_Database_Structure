from __future__ import annotations

from pathlib import Path
from typing import Any


REPORT_TYPES = [
    {"id": "detail-query", "name": "明細查詢表", "description": "逐筆列出交易與來源欄位，適合查核與追蹤。"},
    {"id": "summary-statistics", "name": "彙總統計表", "description": "依部門、科目或期間彙總金額與數量。"},
    {"id": "trend-analysis", "name": "趨勢分析表", "description": "呈現期間序列變化與異常波動。"},
    {"id": "comparison-analysis", "name": "比較分析表", "description": "比較部門、科目、期間或版本差異。"},
    {"id": "exception-audit", "name": "異常稽核表", "description": "聚焦例外、缺漏、超額與控制風險。"},
    {"id": "management-summary", "name": "管理摘要", "description": "提供主管可快速判讀的摘要、重點與建議。"},
    {"id": "complete-analysis", "name": "完整分析報告", "description": "整合摘要、明細、趨勢、比較、稽核與建議。"},
]


REQUIRED_DESIGN_KEYS = [
    "id",
    "name",
    "best_for",
    "required_sections",
    "optional_sections",
    "visual_policy",
    "table_policy",
    "analysis_policy",
    "recommendation_policy",
    "react_component_hints",
    "validator_checklist",
]


def _default_design_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "report_designs"


def _parse_list(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _parse_design(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"Design file missing metadata block: {path}")
    _, block, _body = text.split("---", 2)
    data: dict[str, Any] = {"path": str(path)}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, raw = line.split(":", 1)
        key = key.strip()
        value = raw.strip()
        if key in {"required_sections", "optional_sections", "validator_checklist"}:
            data[key] = _parse_list(value)
        else:
            data[key] = value
    missing = [key for key in REQUIRED_DESIGN_KEYS if not data.get(key)]
    if missing:
        raise ValueError(f"Design file {path} missing metadata: {', '.join(missing)}")
    return data


def list_report_types() -> list[dict[str, str]]:
    return [dict(item) for item in REPORT_TYPES]


def list_report_designs(design_dir: str | Path | None = None) -> list[dict[str, Any]]:
    root = Path(design_dir) if design_dir is not None else _default_design_dir()
    return sorted(
        [_parse_design(path) for path in root.glob("*.md") if path.name not in {"README.md", "design.md"}],
        key=lambda item: item["id"],
    )


def build_report_selection_payload() -> dict[str, Any]:
    return {
        "report_types": list_report_types(),
        "report_designs": list_report_designs(),
        "default_options": {
            "include_chart": True,
            "include_table": True,
            "include_analysis": True,
            "include_recommendations": True,
        },
    }

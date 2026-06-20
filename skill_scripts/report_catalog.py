from __future__ import annotations

from copy import deepcopy
import json
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


REQUIRED_PROFILE_IDS = [
    "financial-control",
    "executive-summary",
    "detail-ledger",
    "exception-audit",
    "operations-review",
    "trend-briefing",
]


REQUIRED_PROFILE_KEYS = [
    "id",
    "label",
    "best_for",
    "required_sections",
    "default_components",
    "chart_policy",
    "table_policy",
    "kpi_policy",
    "tone",
    "layout_density",
    "validator_focus",
]


LIST_KEYS = {"best_for", "required_sections", "default_components", "validator_focus"}
DICT_KEYS = {"chart_policy", "table_policy", "kpi_policy"}
DOC_FILES = {"README.md", "design.md"}


class ReportDesignCatalog:
    def __init__(self, design_dir: Path, profile_ids: list[str], profiles: dict[str, dict[str, Any]]) -> None:
        self.design_dir = design_dir
        self.profile_ids = list(profile_ids)
        self._profiles = profiles

    def get_profile(self, profile_id: str) -> dict[str, Any]:
        if profile_id not in self._profiles:
            raise ValueError(f"Unknown report design profile: {profile_id}")
        return deepcopy(self._profiles[profile_id])

    def list_profiles(self) -> list[dict[str, Any]]:
        return [self.get_profile(profile_id) for profile_id in self.profile_ids]

    def get_scaffold_defaults(self, profile_id: str) -> dict[str, Any]:
        profile = self.get_profile(profile_id)
        return {
            "id": profile["id"],
            "label": profile["label"],
            "sections": list(profile["required_sections"]),
            "components": list(profile["default_components"]),
            "chart_policy": deepcopy(profile["chart_policy"]),
            "table_policy": deepcopy(profile["table_policy"]),
            "kpi_policy": deepcopy(profile["kpi_policy"]),
            "tone": profile["tone"],
            "layout_density": profile["layout_density"],
            "validator_focus": list(profile["validator_focus"]),
        }


def _default_design_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "report_designs"


def _parse_scalar(raw: str) -> Any:
    value = raw.strip()
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _parse_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    raise ValueError(f"Expected list metadata, got {type(value).__name__}")


def _parse_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    raise ValueError(f"Expected object metadata, got {type(value).__name__}")


def _parse_profile(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"Design file missing metadata block: {path}")
    try:
        _, block, body = text.split("---", 2)
    except ValueError as exc:
        raise ValueError(f"Design file has invalid metadata block: {path}") from exc

    data: dict[str, Any] = {"path": str(path), "body": body.strip()}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, raw = line.split(":", 1)
        key = key.strip()
        if not key:
            continue
        value = _parse_scalar(raw)
        if key in LIST_KEYS:
            data[key] = _parse_list(value)
        elif key in DICT_KEYS:
            data[key] = _parse_dict(value)
        else:
            data[key] = str(value).strip()

    missing = [key for key in REQUIRED_PROFILE_KEYS if not data.get(key)]
    if missing:
        raise ValueError(f"Design file {path} missing metadata: {', '.join(missing)}")

    for key in LIST_KEYS:
        if not isinstance(data[key], list) or not data[key]:
            raise ValueError(f"Design file {path} metadata must be a non-empty list: {key}")
    for key in DICT_KEYS:
        if not isinstance(data[key], dict) or not data[key]:
            raise ValueError(f"Design file {path} metadata must be a non-empty object: {key}")

    data["name"] = data["label"]
    return data


def _load_index(root: Path) -> list[str]:
    index_path = root / "index.json"
    if not index_path.exists():
        raise ValueError(f"Missing report design index.json: {index_path}")
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid report design index.json: {index_path}") from exc
    if data != REQUIRED_PROFILE_IDS:
        raise ValueError(
            "report_designs/index.json must list exactly: " + ", ".join(REQUIRED_PROFILE_IDS)
        )
    return list(data)


def load_report_design_catalog(design_dir: str | Path | None = None) -> ReportDesignCatalog:
    root = Path(design_dir) if design_dir is not None else _default_design_dir()
    profile_ids = _load_index(root)

    missing_paths = [root / f"{profile_id}.md" for profile_id in profile_ids if not (root / f"{profile_id}.md").exists()]
    if missing_paths:
        names = ", ".join(path.name for path in missing_paths)
        raise ValueError(f"Missing report design profile file: {names}")

    profiles: dict[str, dict[str, Any]] = {}
    for profile_id in profile_ids:
        profile = _parse_profile(root / f"{profile_id}.md")
        if profile["id"] != profile_id:
            raise ValueError(
                f"Design file {(root / f'{profile_id}.md')} declares id {profile['id']}, expected {profile_id}"
            )
        profiles[profile_id] = profile

    indexed = set(profile_ids)
    for path in root.glob("*.md"):
        if path.name in DOC_FILES:
            continue
        if path.stem not in indexed:
            raise ValueError(f"Profile file is not listed in index.json: {path.name}")
        profile = _parse_profile(path)
        if profile["id"] not in indexed:
            raise ValueError(f"Profile ID is not listed in index.json: {profile['id']}")

    return ReportDesignCatalog(root, profile_ids, profiles)


def list_report_types() -> list[dict[str, str]]:
    return [dict(item) for item in REPORT_TYPES]


def list_report_designs(design_dir: str | Path | None = None) -> list[dict[str, Any]]:
    return load_report_design_catalog(design_dir).list_profiles()


def get_report_design_defaults(profile_id: str, design_dir: str | Path | None = None) -> dict[str, Any]:
    return load_report_design_catalog(design_dir).get_scaffold_defaults(profile_id)


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

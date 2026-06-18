from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

STYLE_KEYS = [
    "catalog_guardrail",
    "layout_recipe",
    "chart_recipe",
    "table_recipe",
    "interaction_recipe",
    "visual_direction",
    "embedded_data_policy",
]
QUERY_RESULT_KEYS = {"row_count"}


def _fingerprint(data: dict[str, Any]) -> str:
    encoded = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_style_capsule(brief: dict[str, Any]) -> dict[str, Any]:
    capsule = {key: _style_only_value(key, brief.get(key)) for key in STYLE_KEYS}
    capsule["style_version"] = "wferp.style-capsule.v1"
    capsule["style_fingerprint"] = _fingerprint({key: capsule[key] for key in STYLE_KEYS})
    return capsule


def _style_only_value(key: str, value: Any) -> Any:
    copied = copy.deepcopy(value)
    if key == "table_recipe" and isinstance(copied, list):
        return [_without_query_result_keys(item) for item in copied]
    return copied


def _without_query_result_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_query_result_keys(item)
            for key, item in value.items()
            if key not in QUERY_RESULT_KEYS
        }
    if isinstance(value, list):
        return [_without_query_result_keys(item) for item in value]
    return value


def apply_style_capsule(capsule: dict[str, Any], *, new_prompt: str) -> dict[str, Any]:
    replayed = {key: copy.deepcopy(capsule[key]) for key in STYLE_KEYS if key in capsule}
    replayed["prompt"] = new_prompt
    replayed["style_fingerprint"] = capsule["style_fingerprint"]
    replayed["style_version"] = capsule["style_version"]
    return replayed


def detect_replay_adjustments(capsule: dict[str, Any], *, new_columns: list[str]) -> dict[str, Any]:
    column_set = set(new_columns)
    incompatible: list[str] = []
    for chart in capsule.get("chart_recipe", []):
        required = set(chart.get("required_columns", []))
        if required and not required.issubset(column_set):
            incompatible.append(chart["id"])
    return {
        "requires_checkpoint": bool(incompatible),
        "incompatible_charts": incompatible,
        "suggested_replacements": [{"id": chart_id, "type": "bar"} for chart_id in incompatible],
    }

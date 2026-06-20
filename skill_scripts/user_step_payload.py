from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from skill_scripts.harness_state_machine import USER_STEP_MAPPING
from skill_scripts.report_harness_state import load_run_state


def _checkpoint_payload(run_dir: Path, filename: str) -> dict[str, Any]:
    path = run_dir / "checkpoints" / filename
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    nested = payload.get("payload")
    return nested if isinstance(nested, dict) else {}


def _step_header(step: int, state: dict[str, Any]) -> dict[str, Any]:
    step_definition = USER_STEP_MAPPING[step]
    return {
        "run_id": state.get("run_id", ""),
        "prompt": state.get("prompt", ""),
        "user_step": step,
        "title": step_definition["title"],
        "label": step_definition["label"],
        "internal_phases": step_definition["phases"],
        "gate_status": state.get("gate_status", {}),
        "blocking_repair_request": state.get("blocking_repair_request"),
    }


def _limit_preview_rows(preview: dict[str, Any], *, limit: int = 50) -> dict[str, Any]:
    if not isinstance(preview, dict):
        return {"columns": [], "sample_rows": [], "total_row_count": 0, "preview_row_limit": limit}

    result = dict(preview)
    rows = result.get("sample_rows") or result.get("rows") or []
    if not isinstance(rows, list):
        rows = []
    result["sample_rows"] = rows[:limit]
    result["preview_row_limit"] = limit
    result["total_row_count"] = int(result.get("row_count") or len(rows))
    return result


def _step_1(run_dir: Path, state: dict[str, Any]) -> dict[str, Any]:
    classification = state.get("column_classification")
    if not isinstance(classification, dict):
        classification = _checkpoint_payload(run_dir, "01b_field_formula_classification.json")
    if not isinstance(classification, dict):
        classification = {}

    return {
        **_step_header(1, state),
        "output_targets": classification.get("output_targets", ["html"]),
        "source_inventory": classification.get("source_inventory", []),
        "source_to_output_matrix": classification.get("source_to_output_matrix", []),
        "formula_semantics": classification.get("formula_semantics", []),
        "unresolved_items": classification.get("unresolved_items", []),
        "technical_checkpoints": ["excel_confirmation", "field_formula_classification"],
    }


def _step_2(run_dir: Path, state: dict[str, Any]) -> dict[str, Any]:
    sql_payload = _checkpoint_payload(run_dir, "02_sql_review.json")
    return {
        **_step_header(2, state),
        "sql": sql_payload.get("sql") or state.get("sql_candidate", ""),
        "validation": sql_payload.get("validation") or state.get("sql_validation") or {},
        "db_target": sql_payload.get("db_target") or {},
        "logic_not_in_sql": sql_payload.get("logic_not_in_sql", []),
        "technical_checkpoints": ["sql_review"],
    }


def _step_3(_run_dir: Path, state: dict[str, Any]) -> dict[str, Any]:
    raw_preview = state.get("raw_data_preview")
    enriched_preview = state.get("enriched_data_preview")
    sqlite_manifest = state.get("sqlite_manifest")
    if not isinstance(raw_preview, dict):
        raw_preview = {}
    if not isinstance(enriched_preview, dict):
        enriched_preview = {}
    if not isinstance(sqlite_manifest, dict):
        sqlite_manifest = {}

    return {
        **_step_header(3, state),
        "data_source": "current-run",
        "uses_mock_data": False,
        "raw_preview": _limit_preview_rows(raw_preview),
        "enriched_preview": _limit_preview_rows(enriched_preview),
        "sqlite_summary": {
            "manifest_path": state.get("sqlite_manifest_path"),
            "lookup_tables": sqlite_manifest.get("lookup_tables", []),
            "lookup_row_counts": sqlite_manifest.get("lookup_row_counts", {}),
            "ignored_lookup_rows": sqlite_manifest.get("ignored_lookup_rows", {}),
        },
        "html_preview": state.get("visual_design_checkpoint") or {},
        "excel_workbook_preview": state.get("excel_workbook_preview") or {},
        "technical_checkpoints": ["raw_data_preview", "enriched_data_preview", "sqlite_retention"],
    }


def _step_4(_run_dir: Path, state: dict[str, Any]) -> dict[str, Any]:
    return {
        **_step_header(4, state),
        "delivery_status": state.get("delivery_status", "not_ready"),
        "validator_results": state.get("validator_results", []),
        "sqlite_retention": state.get("sqlite_retention"),
        "final_html": state.get("final_html_path", ""),
        "final_xlsx": state.get("final_xlsx_path", ""),
        "technical_checkpoints": ["report_draft", "final_review"],
    }


def build_user_step_payload(run_dir: str | Path, step: int) -> dict[str, Any]:
    run_path = Path(run_dir)
    state = load_run_state(run_path)
    if step == 1:
        return _step_1(run_path, state)
    if step == 2:
        return _step_2(run_path, state)
    if step == 3:
        return _step_3(run_path, state)
    if step == 4:
        return _step_4(run_path, state)
    raise ValueError(f"Unknown user step: {step}")

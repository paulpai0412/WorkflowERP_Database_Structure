from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from skill_scripts.report_harness import ReportHarness
from skill_scripts.report_harness_state import load_run_state
from skill_scripts.sql2000_guard import validate_sql


SCHEMA_VERSION = "wferp.report-package.v1"
MAX_EMBEDDED_ROWS = 5000
SECRET_KEY_PARTS = (
    "password",
    "pwd",
    "credential",
    "connection_string",
    "db_connection_string",
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _without_package_hash(package: Mapping[str, Any]) -> dict[str, Any]:
    candidate = deepcopy(dict(package))
    hashes = candidate.get("hashes")
    if isinstance(hashes, dict):
        hashes.pop("package_sha256", None)
    return candidate


def _secret_key_paths(value: Any, path: tuple[str, ...] = ()) -> list[str]:
    paths: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            child_path = (*path, key_text)
            lowered = key_text.lower()
            if any(part in lowered for part in SECRET_KEY_PARTS):
                paths.append(".".join(child_path))
            paths.extend(_secret_key_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            paths.extend(_secret_key_paths(child, (*path, str(index))))
    return paths


def _columns_from_rows(rows: list[Any]) -> list[str]:
    columns: list[str] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        for key in row:
            key_text = str(key)
            if key_text not in columns:
                columns.append(key_text)
    return columns


def _data_profile(execution_result: Mapping[str, Any]) -> dict[str, Any]:
    raw_rows = execution_result.get("rows", [])
    rows = raw_rows if isinstance(raw_rows, list) else []
    raw_columns = execution_result.get("columns")
    columns = list(raw_columns) if isinstance(raw_columns, list) else _columns_from_rows(rows)
    row_count_value = execution_result.get("row_count", len(rows))
    row_count = row_count_value if isinstance(row_count_value, int) and row_count_value >= 0 else len(rows)
    embedded_count = min(len(rows), MAX_EMBEDDED_ROWS)
    embedded_mode = "full_rows" if row_count <= MAX_EMBEDDED_ROWS else "summary_plus_preview"
    return {
        "row_count": row_count,
        "columns": columns,
        "embedded_mode": embedded_mode,
        "embedded_rows": embedded_count,
        "full_rows_in_evidence_packet": row_count > MAX_EMBEDDED_ROWS,
    }


def build_report_package(run_dir: str | Path) -> dict[str, Any]:
    run_path = Path(run_dir)
    state = load_run_state(run_path)
    harness = ReportHarness(run_path)
    delivery_gate = harness.can_deliver()
    if state.get("user_confirmations", {}).get("final_review") != "完成":
        delivery_gate = {
            **delivery_gate,
            "allowed": False,
            "blocking_validators": [
                *delivery_gate.get("blocking_validators", []),
                "final_review_confirmation",
            ],
        }

    sql_text = str(state.get("sql_candidate") or "")
    sql_valid, sql_reason = validate_sql(sql_text)
    sql_validation = dict(state.get("sql_validation") or {})
    sql_validation.setdefault("readonly", sql_valid)
    sql_validation.setdefault("readonly_reason", sql_reason)

    execution_result = state.get("execution_result_summary")
    if not isinstance(execution_result, Mapping):
        execution_result = {}
    raw_rows = execution_result.get("rows", [])
    rows = raw_rows if isinstance(raw_rows, list) else []
    data_profile = _data_profile(execution_result)
    embedded_rows = rows[:MAX_EMBEDDED_ROWS]
    validator_results = state.get("validator_results", [])
    if not isinstance(validator_results, list):
        validator_results = []

    report_options = state.get("report_options")
    report_design = state.get("report_design")
    catalog_guardrail = (
        report_design if isinstance(report_design, str) and report_design else "financial-control"
    )
    package: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": state.get("run_id"),
        "package_id": state.get("run_id"),
        "prompt": state.get("prompt"),
        "catalog_guardrail": catalog_guardrail,
        "report_type": state.get("report_type"),
        "report_options": report_options if isinstance(report_options, dict) else {},
        "sql": {
            "text": sql_text,
            "validation": sql_validation,
        },
        "data_profile": data_profile,
        "datasets": {
            "columns": data_profile["columns"],
            "embedded_rows": embedded_rows,
        },
        "aggregates": execution_result.get("aggregates", {}),
        "excluded_rows": execution_result.get("excluded_rows", []),
        "validator_summary": deepcopy(validator_results),
        "accepted_residual_risks": delivery_gate.get("accepted_residual_risks", []),
        "delivery_gate": delivery_gate,
        "evidence_index": [
            {"id": "sql", "path": "evidence/query.sql"},
            {"id": "execution_result", "path": "evidence/execution-result.json"},
            {"id": "validators", "path": "evidence/validator-results.json"},
        ],
        "security": {
            "source_secret_key_paths": _secret_key_paths(state),
        },
        "hashes": {
            "sql_sha256": _sha256_text(sql_text),
        },
    }
    package["hashes"]["package_sha256"] = _sha256_json(_without_package_hash(package))
    return package


def validate_report_package(package: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []

    security = package.get("security")
    source_secret_key_paths = (
        security.get("source_secret_key_paths") if isinstance(security, Mapping) else None
    )
    if _secret_key_paths(package) or source_secret_key_paths:
        errors.append("credentials")

    delivery_gate = package.get("delivery_gate")
    if not isinstance(delivery_gate, Mapping) or delivery_gate.get("allowed") is not True:
        errors.append("delivery_gate")

    sql = package.get("sql")
    sql_text = sql.get("text") if isinstance(sql, Mapping) else None
    readonly, _reason = validate_sql(str(sql_text or ""))
    if not readonly:
        errors.append("sql_readonly")

    data_profile = package.get("data_profile")
    datasets = package.get("datasets")
    columns = data_profile.get("columns") if isinstance(data_profile, Mapping) else None
    dataset_columns = datasets.get("columns") if isinstance(datasets, Mapping) else None
    embedded_rows = datasets.get("embedded_rows") if isinstance(datasets, Mapping) else None
    if not isinstance(columns, list) or not columns or columns != dataset_columns:
        errors.append("columns")
    elif isinstance(embedded_rows, list):
        row_keys = set()
        for row in embedded_rows:
            if isinstance(row, Mapping):
                row_keys.update(str(key) for key in row)
        if row_keys and not row_keys.issubset(set(str(column) for column in columns)):
            errors.append("columns")
    else:
        errors.append("columns")

    hashes = package.get("hashes")
    expected_hash = hashes.get("package_sha256") if isinstance(hashes, Mapping) else None
    if not isinstance(expected_hash, str) or _sha256_json(_without_package_hash(package)) != expected_hash:
        errors.append("package_hash")

    return {"valid": not errors, "errors": errors}

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from skill_scripts.dynamic_design_brief import build_design_brief
from skill_scripts.html_self_validator import validate_single_html_static
from skill_scripts.single_html_exporter import export_single_html_report
from tests.skill_scripts.expense_report_fixture import EXPECTED_COLUMNS
from tests.skill_scripts.expense_report_fixture import run_expense_analysis_sqlite_e2e


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _package_hash(package: dict) -> str:
    candidate = json.loads(json.dumps(package, ensure_ascii=False))
    candidate["hashes"].pop("package_sha256", None)
    encoded = json.dumps(candidate, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _sha256(encoded)


def _package_from_expense_result(expense: dict) -> dict:
    package = {
        "schema_version": "wferp.report-package.v1",
        "package_id": "expense-e2e",
        "prompt": "費用分析",
        "catalog_guardrail": "financial-control",
        "sql": {"text": expense["sql"], "validation": expense["sql_safety"]},
        "data_profile": {
            "row_count": expense["row_count"],
            "columns": expense["columns"],
            "embedded_mode": "full_rows",
        },
        "datasets": {"columns": expense["columns"], "embedded_rows": expense["rows"]},
        "aggregates": expense["aggregates"],
        "excluded_rows": expense["excluded_rows"],
        "validator_summary": [
            {"validator": "sqlite_expense_e2e", "status": "pass", "message": "SQLite E2E verified."}
        ],
        "evidence_index": [{"id": "sql", "path": "delivery/evidence/query.sql"}],
        "security": {"source_secret_key_paths": []},
        "hashes": {"sql_sha256": _sha256(expense["sql"])},
        "delivery_gate": {"allowed": True, "blocking_validators": []},
    }
    package["hashes"]["package_sha256"] = _package_hash(package)
    return package


def test_single_html_expense_analysis_e2e(tmp_path: Path):
    expense = run_expense_analysis_sqlite_e2e(tmp_path)
    package = _package_from_expense_result(expense)
    brief = build_design_brief(package)

    result = export_single_html_report(tmp_path, package, brief)
    validation = validate_single_html_static(result["html_path"])

    assert result["status"] == "exported"
    assert validation["valid"] is True
    assert Path(result["html_path"]).exists()
    html = Path(result["html_path"]).read_text(encoding="utf-8")
    assert "__WFERP_REPORT_PACKAGE__" in html
    assert "https://" not in html
    assert expense["row_count"] == 6
    assert expense["columns"] == EXPECTED_COLUMNS
    assert expense["aggregates"]["total_amount"] == 120000
    assert expense["aggregates"]["total_budget"] == 100000
    assert expense["aggregates"]["variance_amount"] == 20000
    assert expense["aggregates"]["max_expense_ratio"] == 0.35

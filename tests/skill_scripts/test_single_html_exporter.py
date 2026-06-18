from __future__ import annotations

import json
from pathlib import Path

from skill_scripts.report_package import build_report_package
from skill_scripts.single_html_exporter import export_single_html_report
from tests.skill_scripts.test_report_package import _accepted_report_run


def _package(tmp_path: Path) -> dict[str, object]:
    harness = _accepted_report_run(tmp_path)
    return build_report_package(harness.run_dir)


def _brief() -> dict[str, object]:
    return {
        "schema_version": "wferp.report-design-brief.v1",
        "title": "採購單查詢",
        "layout": {"sections": ["summary", "table"]},
    }


def test_export_single_html_report_writes_delivery_manifest_and_evidence(tmp_path: Path):
    result = export_single_html_report(tmp_path, _package(tmp_path), _brief())

    delivery = tmp_path / "delivery"
    html_path = delivery / "report.html"
    manifest_path = delivery / "delivery-manifest.json"
    evidence_dir = delivery / "evidence"

    assert result["status"] == "exported"
    assert Path(result["html_path"]) == html_path
    assert html_path.exists()
    assert manifest_path.exists()
    assert (evidence_dir / "report-package.json").exists()
    assert (evidence_dir / "report-design-brief.json").exists()
    assert (evidence_dir / "query.sql").read_text(encoding="utf-8").strip() == (
        "SELECT department, amount FROM expenses"
    )

    html = html_path.read_text(encoding="utf-8")
    assert html.startswith("<!doctype html>")
    assert "__WFERP_REPORT_PACKAGE__" in html
    assert "<script src=" not in html.lower()
    assert "<link rel=" not in html.lower()
    assert "fetch(" not in html

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["html_path"] == str(html_path)
    assert manifest["html_sha256"] == result["html_sha256"]
    assert manifest["package_sha256"]
    assert manifest["catalog_guardrail"] == "financial-control"
    assert manifest["row_count"] == 2
    assert manifest["validator_status"] == "pass"


def test_export_single_html_report_rejects_invalid_package_before_writing_html(tmp_path: Path):
    package = _package(tmp_path)
    package["delivery_gate"] = {"allowed": False, "blocking_validators": ["final_review"]}

    result = export_single_html_report(tmp_path, package, _brief())

    assert result["status"] == "error"
    assert "delivery_gate" in result["errors"]
    assert not (tmp_path / "delivery" / "report.html").exists()

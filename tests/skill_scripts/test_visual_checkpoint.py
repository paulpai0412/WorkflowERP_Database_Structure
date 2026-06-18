from __future__ import annotations

from pathlib import Path

import pytest

from skill_scripts.dynamic_design_brief import build_design_brief, validate_design_brief
from skill_scripts.report_harness import ReportHarness, ReportHarnessError
from skill_scripts.visual_checkpoint import (
    build_visual_checkpoint_payload,
    render_visual_checkpoint_html,
)


def _report_package() -> dict[str, object]:
    return {
        "catalog_guardrail": "financial-control",
        "prompt": "分析 2026 年各部門費用",
        "report_type": "管理摘要",
        "data_profile": {
            "columns": ["department", "amount", "month"],
            "row_count": 3,
            "embedded_mode": "full_rows",
            "embedded_rows": 3,
        },
        "datasets": {
            "columns": ["department", "amount", "month"],
            "embedded_rows": [
                {"department": "管理部", "amount": 1200, "month": "2026-01"},
                {"department": "研發部", "amount": 2500, "month": "2026-01"},
                {"department": "業務部", "amount": 1800, "month": "2026-02"},
            ],
        },
        "aggregates": {
            "amount_sum": 5500,
            "amount_avg": 1833.33,
            "department_count": 3,
        },
    }


def _design_brief(package: dict[str, object]) -> dict[str, object]:
    brief = build_design_brief(package)
    assert validate_design_brief(brief)["valid"] is True
    return brief


def test_visual_checkpoint_payload_uses_real_labels_and_aggregates():
    package = _report_package()
    payload = build_visual_checkpoint_payload(_design_brief(package), package)

    assert payload["title"] == "費用分析視覺設計確認"
    assert payload["catalog_guardrail"] == "financial-control"
    assert payload["data_profile"]["row_count"] == 3
    assert {"label": "amount_sum", "value": 5500} in payload["kpis"]
    assert {"label": "amount_avg", "value": 1833.33} in payload["kpis"]
    assert any(chart["purpose"] for chart in payload["charts"])
    assert any(table["columns"] == ["department", "amount", "month"] for table in payload["tables"])


def test_visual_checkpoint_html_is_static_and_contains_design_sections():
    package = _report_package()
    payload = build_visual_checkpoint_payload(_design_brief(package), package)

    html = render_visual_checkpoint_html(payload)

    assert "費用分析視覺設計確認" in html
    assert "amount_sum" in html
    assert payload["charts"][0]["purpose"] in html
    assert "視覺方向" in html
    assert "互動" in html
    assert "fetch(" not in html
    assert "new WebSocket" not in html
    assert "SQL" not in html


def test_report_draft_requires_visual_design_confirmation_after_design_brief(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="分析 2026 年各部門費用")
    package = _report_package()
    brief = _design_brief(package)

    harness.write_report_selection(
        {"selected_report_type": "管理摘要", "selected_report_design": "financial-control"}
    )
    harness.confirm("report_selection", "產生報告")
    harness.write_design_brief(brief)
    harness.confirm("design_brief", "確認設計")

    with pytest.raises(ReportHarnessError, match="Visual design must be confirmed"):
        harness.write_report_draft({"sections": ["executive-summary"]})

    payload = build_visual_checkpoint_payload(brief, package)
    harness.write_visual_design(payload)
    harness.confirm("visual_design", "確認視覺設計")

    checkpoint = harness.write_report_draft({"sections": ["executive-summary"]})

    assert checkpoint["checkpoint"] == "report_draft"

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from skill_scripts.excel_workbook_exporter import export_workbook
from skill_scripts.report_harness import ReportHarness
from skill_scripts.cli_report_harness import main


def test_export_workbook_writes_real_xlsx_and_evidence(tmp_path: Path):
    payload = {
        "sheets": [
            {
                "name": "Detail",
                "columns": ["department", "amount"],
                "rows": [{"department": "A", "amount": 1000}],
                "formula_strategy": "hybrid",
            },
            {
                "name": "Formula Notes",
                "columns": ["field", "logic"],
                "rows": [{"field": "amount", "logic": "from SQLite enriched data"}],
                "formula_strategy": "value-only",
            },
        ]
    }

    result = export_workbook(payload, tmp_path / "report.xlsx", evidence_path=tmp_path / "excel-evidence.json")

    assert result["status"] == "exported"
    assert result["workbook_path"].endswith("report.xlsx")
    assert result["sheets"][0]["name"] == "Detail"
    assert result["sheets"][0]["row_count"] == 1
    assert result["verification"]["xlsx_contains_workbook_xml"] is True
    assert (tmp_path / "report.xlsx").is_file()
    assert (tmp_path / "excel-evidence.json").is_file()
    with zipfile.ZipFile(tmp_path / "report.xlsx") as archive:
        assert "xl/workbook.xml" in archive.namelist()


def test_export_excel_workbook_cli_updates_state(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="build workbook")
    payload_path = tmp_path / "payload.json"
    payload_path.write_text(
        json.dumps(
            {
                "sheets": [
                    {
                        "name": "Detail",
                        "columns": ["department", "amount"],
                        "rows": [{"department": "A", "amount": 1000}],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = main(
        [
            "export-excel-workbook",
            "--run-dir",
            str(harness.run_dir),
            "--payload",
            str(payload_path),
        ]
    )

    assert result == 0
    state = harness.state()
    assert state["final_xlsx_path"].endswith("report.xlsx")
    assert state["excel_workbook_evidence"]["status"] == "exported"
    assert (harness.run_dir / "report" / "delivery" / "report.xlsx").is_file()

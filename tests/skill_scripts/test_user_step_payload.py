from __future__ import annotations

import json
from pathlib import Path

from skill_scripts.report_harness import ReportHarness
from skill_scripts.user_step_payload import build_user_step_payload


def test_step_1_builds_source_to_output_logic_payload(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="build html and excel report")
    harness.write_field_formula_classification(
        {
            "output_targets": ["html", "excel"],
            "source_inventory": [{"kind": "excel_source", "name": "orders.xlsx"}],
            "source_to_output_matrix": [
                {
                    "output_item": "Excel detail sheet",
                    "source": "DB raw rows + Excel lookup",
                    "transformation_logic": "join raw rows with lookup table and compute totals",
                    "processing_layer": "sqlite-enrichment",
                    "verification": "HTML KPI and Excel totals match",
                }
            ],
            "formula_semantics": [
                {
                    "name": "total_amount",
                    "intent": "sum order amounts",
                    "processing_layer": "sqlite-enrichment",
                }
            ],
        }
    )

    payload = build_user_step_payload(harness.run_dir, 1)

    assert payload["user_step"] == 1
    assert payload["label"] == "source_to_output_logic"
    assert payload["output_targets"] == ["html", "excel"]
    assert payload["source_to_output_matrix"][0]["output_item"] == "Excel detail sheet"
    assert payload["formula_semantics"][0]["processing_layer"] == "sqlite-enrichment"
    assert payload["technical_checkpoints"] == ["excel_confirmation", "field_formula_classification"]


def test_step_3_uses_real_raw_and_enriched_rows_with_50_row_limit(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="build report")
    raw_rows = [{"id": index, "amount": index * 10} for index in range(60)]
    enriched_rows = [{"id": index, "amount": index * 10, "category": "A"} for index in range(60)]
    harness.update_state(
        raw_data_preview={"row_count": 60, "columns": ["id", "amount"], "sample_rows": raw_rows},
        enriched_data_preview={
            "row_count": 60,
            "columns": ["id", "amount", "category"],
            "sample_rows": enriched_rows,
        },
        sqlite_manifest={
            "lookup_tables": ["lookup_customer"],
            "lookup_row_counts": {"lookup_customer": 3},
            "ignored_lookup_rows": {},
        },
    )

    payload = build_user_step_payload(harness.run_dir, 3)

    assert payload["user_step"] == 3
    assert payload["label"] == "data_result_and_report_design"
    assert len(payload["raw_preview"]["sample_rows"]) == 50
    assert len(payload["enriched_preview"]["sample_rows"]) == 50
    assert payload["raw_preview"]["total_row_count"] == 60
    assert payload["enriched_preview"]["total_row_count"] == 60
    assert payload["sqlite_summary"]["lookup_tables"] == ["lookup_customer"]
    assert payload["data_source"] == "current-run"
    assert payload["uses_mock_data"] is False


def test_write_user_step_preview_cli_persists_payload(tmp_path: Path):
    from skill_scripts.cli_report_harness import main

    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="build report")
    result = main(["write-user-step-preview", "--run-dir", str(harness.run_dir), "--step", "1"])

    assert result == 0
    persisted = json.loads(
        (harness.run_dir / "checkpoints" / "user_step_1.json").read_text(encoding="utf-8")
    )
    assert persisted["user_step"] == 1
    assert persisted["label"] == "source_to_output_logic"

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skill_scripts.dynamic_design_brief import build_design_brief, validate_design_brief
from skill_scripts.report_harness import ReportHarness, ReportHarnessError
from skill_scripts.report_harness_state import CHECKPOINT_DEFINITIONS, write_confirmation
from skill_scripts.validator_contracts import REQUIRED_VALIDATORS
from skill_scripts.visual_checkpoint import build_visual_checkpoint_payload


def _validator_result(role: str, status: str = "pass") -> dict[str, object]:
    evidence: list[dict[str, object]] = [{"command": f"review {role}"}]
    if role == "data_preview_reviewer":
        evidence = [
            {
                "name": "preview_shape",
                "status": "pass",
                "metrics": {"row_count": 10, "column_count": 4},
            }
        ]
    if role == "excel_classification_reviewer":
        evidence = [
            {"type": "file", "path": "data/field-classification.json"},
            {"type": "metric", "name": "classified_columns", "value": 10},
            {"type": "metric", "name": "db_field_count", "value": 6},
            {"type": "metric", "name": "formula_field_count", "value": 2},
            {"type": "metric", "name": "lookup_field_count", "value": 1},
            {"type": "metric", "name": "manual_only_count", "value": 1},
            {"type": "inspection", "name": "metadata_readability", "status": "pass"},
        ]
    if role == "sqlite_enrichment_reviewer":
        evidence = [
            {"type": "file", "path": "sqlite/wferp_run_sqlite_manifest.json"},
            {"type": "metric", "name": "raw_row_count", "value": 10},
            {"type": "metric", "name": "enriched_row_count", "value": 10},
            {"type": "metric", "name": "ignored_lookup_rows", "value": 0},
        ]
    return {
        "role": role,
        "status": status,
        "reviewer_identity": {"kind": "subagent", "id": f"{role}-agent"},
        "checked_scope": ["run-dir"],
        "input_artifact_paths": ["checkpoints/current.json"],
        "reviewed_at": "2026-06-20T00:00:00Z",
        "evidence": evidence,
        "findings": [] if status == "pass" else [f"{role} failed"],
        "requiredFixes": [] if status == "pass" else [f"repair {role}"],
        "residualRisks": [] if status == "pass" else [f"accepted risk for {role}"],
    }


def _all_validator_results(status_overrides: dict[str, str] | None = None) -> list[dict[str, object]]:
    overrides = status_overrides or {}
    return [_validator_result(role, overrides.get(role, "pass")) for role in REQUIRED_VALIDATORS]


def _sql_gate_validator_results() -> list[dict[str, object]]:
    return [
        _validator_result("sql_safety_reviewer"),
        _validator_result("schema_mapping_reviewer"),
    ]


def _valid_design_brief(harness: ReportHarness) -> dict[str, object]:
    brief = build_design_brief(
        {
            "catalog_guardrail": "financial-control",
            "prompt": harness.state().get("prompt"),
            "report_type": harness.state().get("report_type"),
            "data_profile": {"columns": ["department", "amount"], "row_count": 1},
            "datasets": {"columns": ["department", "amount"]},
        }
    )
    assert validate_design_brief(brief)["valid"] is True
    return brief


def _confirm_design_brief(harness: ReportHarness) -> None:
    brief = _valid_design_brief(harness)
    harness.write_design_brief(brief)
    harness.confirm("design_brief", "確認設計")


def _confirm_visual_design(harness: ReportHarness) -> None:
    package = {
        "catalog_guardrail": "financial-control",
        "prompt": harness.state().get("prompt"),
        "report_type": harness.state().get("report_type"),
        "data_profile": {"columns": ["department", "amount"], "row_count": 2},
        "datasets": {
            "columns": ["department", "amount"],
            "embedded_rows": [
                {"department": "管理部", "amount": 1000},
                {"department": "研發部", "amount": 2500},
            ],
        },
        "aggregates": {"amount_sum": 3500, "amount_avg": 1750},
    }
    payload = build_visual_checkpoint_payload(harness.state()["report_design_brief"], package)
    harness.write_visual_design(payload)
    harness.confirm("visual_design", "確認視覺設計")


def test_rejects_state_transition_without_required_confirmation(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="demo-run", prompt="請查詢費用")
    harness.write_sql_review("SELECT * FROM ACPTA")

    with pytest.raises(ReportHarnessError, match="SQL must be confirmed"):
        harness.write_data_preview({"rows": [], "row_count": 0})


def test_field_formula_readability_failure_does_not_pollute_state(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="demo-run", prompt="prompt")

    with pytest.raises(ReportHarnessError, match="text readability"):
        harness.write_field_formula_classification(
            {"source_to_output_matrix": [{"Excel??": "A", "label": "????"}]}
        )

    state = harness.state()
    assert state["column_classification"] is None
    assert not (
        tmp_path / "demo-run" / "checkpoints" / "01b_field_formula_classification.json"
    ).exists()


def test_confirmed_sql_allows_data_preview_checkpoint(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="demo-run", prompt="請查詢費用")
    harness.write_sql_review("SELECT * FROM ACPTA")
    harness.update_state(validator_results=_sql_gate_validator_results())
    harness.confirm("sql_review", "同意查詢")

    checkpoint = harness.write_data_preview({"rows": [{"部門": "D001"}], "row_count": 1})

    assert harness.state()["user_confirmations"]["sql_review"] == "同意查詢"
    assert checkpoint["checkpoint"] == "data_preview"
    assert checkpoint["payload"]["row_count"] == 1


def test_state_gate_blocks_data_preview_when_confirmation_identity_is_missing(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="demo-run", prompt="請查詢費用")
    harness.write_sql_review("SELECT * FROM ACPTA")
    harness.update_state(
        artifact_status={
            "sql/query.sql": "complete",
            "checkpoints/02_sql_review.json": "complete",
        },
        validator_results=_sql_gate_validator_results(),
        user_confirmations={"sql_review": "同意查詢"},
    )

    with pytest.raises(ReportHarnessError, match="confirmation_identity"):
        harness.write_data_preview({"rows": [{"部門": "D001"}], "row_count": 1})


def test_rewriting_sql_review_invalidates_confirmation_identity(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="demo-run", prompt="請查詢費用")
    harness.write_sql_review("SELECT 1")
    harness.update_state(validator_results=_sql_gate_validator_results())
    harness.confirm("sql_review", "同意查詢")
    old_identity = harness.state()["confirmation_identity"]["sql_review"]

    harness.write_sql_review("SELECT 2")
    harness.update_state(
        validator_results=_sql_gate_validator_results(),
        user_confirmations={"sql_review": "同意查詢"},
        confirmation_identity={"sql_review": old_identity},
    )

    with pytest.raises(ReportHarnessError, match="confirmation_identity"):
        harness.write_data_preview({"rows": [{"部門": "D001"}], "row_count": 1})


def test_rewriting_sql_review_requires_reconfirmation(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="demo-run", prompt="請查詢費用")
    harness.write_sql_review("SELECT 1")
    harness.update_state(validator_results=_sql_gate_validator_results())
    harness.confirm("sql_review", "同意查詢")
    harness.write_sql_review("SELECT 2")

    with pytest.raises(ReportHarnessError, match="SQL must be confirmed"):
        harness.write_data_preview({"rows": [], "row_count": 0})


def test_rewriting_sql_review_clears_downstream_state_and_checkpoints(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="demo-run", prompt="請查詢費用")
    harness.write_sql_review("SELECT 1")
    harness.update_state(validator_results=_sql_gate_validator_results())
    harness.confirm("sql_review", "同意查詢")
    harness.write_data_preview({"rows": [{"部門": "D001"}], "row_count": 1})
    harness.write_report_selection(
        {
            "selected_report_type": "管理摘要",
            "selected_report_design": "financial-control",
            "selected_options": {"include_table": True},
        }
    )

    harness.write_sql_review("SELECT 2")

    state = harness.state()
    assert state["execution_result_summary"] is None
    assert state["report_type"] is None
    assert state["report_design"] is None
    assert state["report_options"] == {}


def test_prompt_repair_blocks_forward_progress_until_cleared(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="build report")
    harness.write_sql_review("SELECT * FROM ACPTA", {"status": "pass"})
    repair_action = CHECKPOINT_DEFINITIONS["sql_review"]["actions"][1]

    harness.confirm(
        "sql_review",
        repair_action,
        selected_options={
            "changeScope": "sql_conditions",
            "targetUserStep": 2,
            "requiresRerender": True,
            "prompt": "add date condition",
        },
        comment="add date condition",
    )

    state = harness.state()
    assert state["blocking_repair_request"]["changeScope"] == "sql_conditions"
    assert state["blocking_repair_request"]["comment"] == "add date condition"
    assert state["allowed_next_actions"] == ["repair_current_step"]
    assert "execute_select" not in state["allowed_next_actions"]
    assert [checkpoint["checkpoint"] for checkpoint in state["checkpoints"]] == ["sql_review"]
    assert not (harness.run_dir / "checkpoints" / "03_data_preview.json").exists()
    assert not (harness.run_dir / "checkpoints" / "04_report_selection.json").exists()


def test_confirm_requires_existing_checkpoint_and_valid_action(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="demo-run", prompt="請查詢費用")

    with pytest.raises(ReportHarnessError, match="checkpoint has not been created"):
        harness.confirm("sql_review", "同意查詢")

    harness.write_sql_review("SELECT * FROM ACPTA")

    with pytest.raises(ReportHarnessError, match="Invalid checkpoint action"):
        harness.confirm("sql_review", "直接執行")


def test_report_draft_requires_report_selection_confirmation(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="demo-run", prompt="請查詢費用")
    harness.write_report_selection({"report_types": ["管理摘要"]})

    with pytest.raises(ReportHarnessError, match="Report selection must be confirmed"):
        harness.write_report_draft({"sections": []})


def test_report_selection_updates_canonical_state_fields(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="demo-run", prompt="請查詢費用")

    harness.write_report_selection(
        {
            "selected_report_type": "管理摘要",
            "selected_report_design": "financial-control",
            "selected_options": {
                "include_chart": True,
                "include_table": True,
                "include_analysis": True,
                "include_recommendations": False,
            },
        }
    )

    state = harness.state()
    assert state["report_type"] == "管理摘要"
    assert state["report_design"] == "financial-control"
    assert state["report_options"]["include_chart"] is True


def test_final_review_requires_draft_acceptance(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="demo-run", prompt="請查詢費用")
    harness.write_report_selection({"report_types": ["管理摘要"]})
    harness.confirm("report_selection", "產生報告")
    _confirm_design_brief(harness)
    _confirm_visual_design(harness)
    harness.write_report_draft({"sections": ["摘要"]})

    with pytest.raises(ReportHarnessError, match="Draft must be accepted"):
        harness.write_final_review({"status": "ready"})


def test_success_is_blocked_when_any_validator_fails(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="查詢費用")
    harness.write_report_selection(
        {"selected_report_type": "管理摘要", "selected_report_design": "financial-control"}
    )
    harness.confirm("report_selection", "產生報告")
    _confirm_design_brief(harness)
    _confirm_visual_design(harness)
    harness.write_report_draft({"sections": ["摘要"]})
    harness.confirm("report_draft", "接受")
    harness.write_final_review(
        {
            "validator_results": _all_validator_results({"visual_taste_reviewer": "fail"}),
        }
    )

    assert harness.can_deliver() == {
        "allowed": False,
        "blocking_validators": ["visual_taste_reviewer"],
        "accepted_residual_risks": [],
    }


def test_delivery_allows_explicitly_accepted_residual_risk_at_final_checkpoint(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="查詢費用")
    harness.write_report_selection(
        {"selected_report_type": "管理摘要", "selected_report_design": "financial-control"}
    )
    harness.confirm("report_selection", "產生報告")
    _confirm_design_brief(harness)
    _confirm_visual_design(harness)
    harness.write_report_draft({"sections": ["摘要"]})
    harness.confirm("report_draft", "接受")
    harness.write_final_review(
        {
            "validator_results": _all_validator_results({"visual_taste_reviewer": "warning"}),
        }
    )

    assert harness.can_deliver()["allowed"] is False

    harness.confirm(
        "final_review",
        "完成",
        selected_options={
            "acceptedResidualRisks": ["visual_taste_reviewer: accepted risk for visual_taste_reviewer"],
        },
    )

    assert harness.can_deliver() == {
        "allowed": True,
        "blocking_validators": [],
        "accepted_residual_risks": ["visual_taste_reviewer: accepted risk for visual_taste_reviewer"],
    }


def test_final_review_payload_string_residual_risks_do_not_allow_delivery(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="查詢費用")
    harness.write_report_selection(
        {"selected_report_type": "管理摘要", "selected_report_design": "financial-control"}
    )
    harness.confirm("report_selection", "產生報告")
    _confirm_design_brief(harness)
    _confirm_visual_design(harness)
    harness.write_report_draft({"sections": ["摘要"]})
    harness.confirm("report_draft", "接受")
    harness.write_final_review(
        {
            "validator_results": _all_validator_results({"visual_taste_reviewer": "warning"}),
            "accepted_residual_risks": "yes",
        }
    )
    harness.confirm("final_review", "完成")

    assert harness.can_deliver() == {
        "allowed": False,
        "blocking_validators": ["visual_taste_reviewer"],
        "accepted_residual_risks": [],
    }


def test_non_pass_validator_delivers_only_with_matching_user_accepted_risk(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="查詢費用")
    harness.write_report_selection(
        {"selected_report_type": "管理摘要", "selected_report_design": "financial-control"}
    )
    harness.confirm("report_selection", "產生報告")
    _confirm_design_brief(harness)
    _confirm_visual_design(harness)
    harness.write_report_draft({"sections": ["摘要"]})
    harness.confirm("report_draft", "接受")
    harness.write_final_review(
        {
            "validator_results": _all_validator_results({"visual_taste_reviewer": "warning"}),
        }
    )

    harness.confirm(
        "final_review",
        "完成",
        selected_options={
            "acceptedResidualRisks": ["visual_taste_reviewer: accepted risk for visual_taste_reviewer"],
        },
    )

    assert harness.can_deliver() == {
        "allowed": True,
        "blocking_validators": [],
        "accepted_residual_risks": ["visual_taste_reviewer: accepted risk for visual_taste_reviewer"],
    }


def test_partial_residual_risk_acceptance_still_blocks_other_non_pass_validators(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="查詢費用")
    harness.write_report_selection(
        {"selected_report_type": "管理摘要", "selected_report_design": "financial-control"}
    )
    harness.confirm("report_selection", "產生報告")
    _confirm_design_brief(harness)
    _confirm_visual_design(harness)
    harness.write_report_draft({"sections": ["摘要"]})
    harness.confirm("report_draft", "接受")
    harness.write_final_review(
        {
            "validator_results": _all_validator_results(
                {
                    "visual_taste_reviewer": "warning",
                    "data_visualization_reviewer": "warning",
                }
            ),
        }
    )

    harness.confirm(
        "final_review",
        "完成",
        selected_options={
            "acceptedResidualRisks": ["visual_taste_reviewer: accepted risk for visual_taste_reviewer"],
        },
    )

    assert harness.can_deliver() == {
        "allowed": False,
        "blocking_validators": ["data_visualization_reviewer"],
        "accepted_residual_risks": ["visual_taste_reviewer: accepted risk for visual_taste_reviewer"],
    }


def test_can_deliver_reads_final_confirmation_file_when_state_options_are_empty(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="查詢費用")
    harness.write_report_selection(
        {"selected_report_type": "管理摘要", "selected_report_design": "financial-control"}
    )
    harness.confirm("report_selection", "產生報告")
    _confirm_design_brief(harness)
    _confirm_visual_design(harness)
    harness.write_report_draft({"sections": ["摘要"]})
    harness.confirm("report_draft", "接受")
    harness.write_final_review(
        {
            "validator_results": _all_validator_results({"visual_taste_reviewer": "warning"}),
        }
    )
    harness.confirm("final_review", "完成")
    checkpoint_payload = json.loads(
        (harness.run_dir / "checkpoints" / "06_final_review.json").read_text(encoding="utf-8")
    )
    write_confirmation(
        harness.run_dir,
        "final_review",
        {
            "action": "完成",
            "run_id": checkpoint_payload["run_id"],
            "checkpoint_id": checkpoint_payload["checkpoint_id"],
            "payload_hash": checkpoint_payload["payload_hash"],
            "confirmation_id": "confirm-final-risk",
            "selectedOptions": {
                "acceptedResidualRisks": [
                    "visual_taste_reviewer: accepted risk for visual_taste_reviewer"
                ]
            },
        },
    )

    assert harness.state()["user_confirmation_options"]["final_review"] == {}
    assert harness.can_deliver() == {
        "allowed": True,
        "blocking_validators": [],
        "accepted_residual_risks": ["visual_taste_reviewer: accepted risk for visual_taste_reviewer"],
    }


def test_append_repair_log_writes_minimal_vertical_slice_entry(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="查詢費用")

    path = harness.append_repair_log(
        validator="sql_safety_reviewer",
        failure="SELECT INTO is blocked",
        scope="sql/query.sql",
        minimal_vertical_slice="Remove SELECT INTO while preserving selected columns",
        files_changed=["sql/query.sql", "skill_scripts/report_harness.py"],
        validation_rerun="pytest tests/skill_scripts/test_report_harness.py -v",
        residual_risk="None",
    )

    content = path.read_text(encoding="utf-8")
    assert "sql_safety_reviewer" in content
    assert "Failure:\nSELECT INTO is blocked" in content
    assert "Scope:\nsql/query.sql" in content
    assert "Minimal vertical slice:\nRemove SELECT INTO while preserving selected columns" in content
    assert "Files changed:\n- sql/query.sql\n- skill_scripts/report_harness.py" in content
    assert "Validation rerun:\npytest tests/skill_scripts/test_report_harness.py -v" in content
    assert "Residual risk:\nNone" in content


def test_write_design_brief_records_checkpoint_and_clears_downstream_state(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="查詢費用")
    harness.write_report_selection(
        {"selected_report_type": "管理摘要", "selected_report_design": "financial-control"}
    )
    harness.confirm("report_selection", "產生報告")
    _confirm_design_brief(harness)
    _confirm_visual_design(harness)
    harness.write_report_draft({"sections": ["摘要"]})
    harness.update_state(
        validator_results=[_validator_result("visual_taste_reviewer")],
        visual_design_checkpoint={"status": "ready"},
    )

    brief = _valid_design_brief(harness)
    brief["chart_recipe"][0]["purpose"] = "比較部門"
    assert validate_design_brief(brief)["valid"] is True

    checkpoint = harness.write_design_brief(brief)

    state = harness.state()
    assert checkpoint["checkpoint"] == "design_brief"
    assert checkpoint["title"] == "動態設計確認"
    assert state["report_design_brief"] == brief
    assert state["visual_design_checkpoint"] is None
    assert state["validator_results"] == []
    assert "design_brief" not in state["user_confirmations"]
    assert "report_draft" not in {item["checkpoint"] for item in state["checkpoints"]}
    assert not (harness.run_dir / "checkpoints" / "05_report_draft.json").exists()


def test_write_visual_design_requires_confirmed_design_brief(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="查詢費用")
    payload = {"title": "費用分析視覺設計確認"}

    with pytest.raises(
        ReportHarnessError,
        match="Design brief must be confirmed before visual checkpoint",
    ):
        harness.write_visual_design(payload)


def test_write_visual_design_records_checkpoint_and_clears_downstream_state(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="查詢費用")
    harness.write_report_selection(
        {"selected_report_type": "管理摘要", "selected_report_design": "financial-control"}
    )
    harness.confirm("report_selection", "產生報告")
    _confirm_design_brief(harness)
    _confirm_visual_design(harness)
    harness.write_report_draft({"sections": ["摘要"]})
    harness.confirm("report_draft", "接受")
    harness.write_final_review({"validator_results": _all_validator_results()})

    payload = {"title": "費用分析視覺設計確認", "kpis": [{"label": "amount_sum", "value": 3500}]}
    checkpoint = harness.write_visual_design(payload)

    state = harness.state()
    assert checkpoint["checkpoint"] == "visual_design"
    assert checkpoint["title"] == "視覺設計確認"
    assert state["visual_design_checkpoint"] == payload
    assert state["validator_results"] == []
    assert "visual_design" not in state["user_confirmations"]
    assert "report_draft" not in {item["checkpoint"] for item in state["checkpoints"]}
    assert "final_review" not in {item["checkpoint"] for item in state["checkpoints"]}
    assert not (harness.run_dir / "checkpoints" / "05_report_draft.json").exists()
    assert not (harness.run_dir / "checkpoints" / "06_final_review.json").exists()


def test_report_draft_requires_confirmed_design_brief_after_report_selection(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="demo-run", prompt="請查詢費用")
    harness.write_report_selection({"report_types": ["管理摘要"]})
    harness.confirm("report_selection", "產生報告")
    harness.write_design_brief(_valid_design_brief(harness))

    with pytest.raises(ReportHarnessError, match="Design brief must be confirmed before writing draft"):
        harness.write_report_draft({"sections": []})


def test_changed_report_selection_clears_design_brief_and_future_checkpoints(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="查詢費用")
    harness.write_report_selection(
        {"selected_report_type": "管理摘要", "selected_report_design": "financial-control"}
    )
    harness.confirm("report_selection", "產生報告")
    _confirm_design_brief(harness)
    harness.update_state(
        visual_design_checkpoint={"status": "ready"},
        validator_results=[_validator_result("visual_taste_reviewer")],
    )

    harness.write_report_selection(
        {"selected_report_type": "明細表", "selected_report_design": "financial-control"}
    )

    state = harness.state()
    assert state["report_design_brief"] is None
    assert state["visual_design_checkpoint"] is None
    assert state["validator_results"] == []
    assert "design_brief" not in state["user_confirmations"]
    assert "design_brief" not in {item["checkpoint"] for item in state["checkpoints"]}
    assert not (harness.run_dir / "checkpoints" / "04a_design_brief.json").exists()

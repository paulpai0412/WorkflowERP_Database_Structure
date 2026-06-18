from __future__ import annotations

from pathlib import Path

import pytest

from skill_scripts.dynamic_design_brief import build_design_brief, validate_design_brief
from skill_scripts.report_harness import ReportHarness, ReportHarnessError
from skill_scripts.report_harness_state import write_confirmation
from skill_scripts.validator_contracts import REQUIRED_VALIDATORS


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
    return {
        "role": role,
        "status": status,
        "evidence": evidence,
        "findings": [] if status == "pass" else [f"{role} failed"],
        "requiredFixes": [] if status == "pass" else [f"repair {role}"],
        "residualRisks": [] if status == "pass" else [f"accepted risk for {role}"],
    }


def _all_validator_results(status_overrides: dict[str, str] | None = None) -> list[dict[str, object]]:
    overrides = status_overrides or {}
    return [_validator_result(role, overrides.get(role, "pass")) for role in REQUIRED_VALIDATORS]


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


def test_rejects_state_transition_without_required_confirmation(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="demo-run", prompt="請查詢費用")
    harness.write_sql_review("SELECT * FROM ACPTA")

    with pytest.raises(ReportHarnessError, match="SQL must be confirmed"):
        harness.write_data_preview({"rows": [], "row_count": 0})


def test_confirmed_sql_allows_data_preview_checkpoint(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="demo-run", prompt="請查詢費用")
    harness.write_sql_review("SELECT * FROM ACPTA")
    harness.confirm("sql_review", "同意查詢")

    checkpoint = harness.write_data_preview({"rows": [{"部門": "D001"}], "row_count": 1})

    assert harness.state()["user_confirmations"]["sql_review"] == "同意查詢"
    assert checkpoint["checkpoint"] == "data_preview"
    assert checkpoint["payload"]["row_count"] == 1


def test_rewriting_sql_review_requires_reconfirmation(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="demo-run", prompt="請查詢費用")
    harness.write_sql_review("SELECT 1")
    harness.confirm("sql_review", "同意查詢")
    harness.write_sql_review("SELECT 2")

    with pytest.raises(ReportHarnessError, match="SQL must be confirmed"):
        harness.write_data_preview({"rows": [], "row_count": 0})


def test_rewriting_sql_review_clears_downstream_state_and_checkpoints(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="demo-run", prompt="請查詢費用")
    harness.write_sql_review("SELECT 1")
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
    harness.write_report_draft({"sections": ["摘要"]})
    harness.confirm("report_draft", "接受")
    harness.write_final_review(
        {
            "validator_results": _all_validator_results({"visual_taste_reviewer": "warning"}),
        }
    )
    harness.confirm("final_review", "完成")
    write_confirmation(
        harness.run_dir,
        "final_review",
        {
            "action": "完成",
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
    harness.write_report_draft({"sections": ["摘要"]})
    harness.update_state(
        validator_results=[{"role": "visual_taste_reviewer", "status": "pass"}],
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
        validator_results=[{"role": "visual_taste_reviewer", "status": "pass"}],
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

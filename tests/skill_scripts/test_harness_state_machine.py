from __future__ import annotations

from pathlib import Path

import pytest

from skill_scripts.harness_state_machine import (
    GATE_DEFINITIONS,
    USER_STEP_MAPPING,
    GateBlockedError,
    initialize_state_machine,
    evaluate_gate,
    assert_can_advance,
)
from skill_scripts.report_harness_state import create_report_run, load_run_state


def test_initialize_state_machine_adds_required_workflow_fields(tmp_path: Path):
    state = create_report_run(tmp_path, run_id="demo-run", prompt="產出報表")
    initialized = initialize_state_machine(state)

    assert initialized["current_user_step"] == 1
    assert initialized["current_internal_phase"] == 0
    assert initialized["user_step_mapping"] == USER_STEP_MAPPING
    assert initialized["user_step_mapping"] == {
        1: {
            "title": "Source-to-Output Logic",
            "label": "source_to_output_logic",
            "phases": [0, 1, 2, 3],
        },
        2: {"title": "SQL Query", "label": "sql_query", "phases": [4, 5]},
        3: {
            "title": "Data Result and Report Design",
            "label": "data_result_and_report_design",
            "phases": [6, 7, 8, 9],
        },
        4: {"title": "Final Delivery", "label": "final_delivery", "phases": [10, 11, 12]},
    }
    assert initialized["gate_status"]["phase_4_sql_review"] == {
        "status": "blocked",
        "user_step": 2,
        "required_artifacts": ["sql/query.sql", "checkpoints/02_sql_review.json"],
        "required_validators": ["sql_safety_reviewer", "schema_mapping_reviewer"],
        "confirmation": {
            "required": True,
            "checkpoint_id": "sql_review",
            "payload_hash": None,
        },
        "allowed_next_actions": ["execute_select", "request_changes"],
        "blocking_reason": [
            "missing_artifact:sql/query.sql",
            "missing_artifact:checkpoints/02_sql_review.json",
            "missing_validator:sql_safety_reviewer",
            "missing_validator:schema_mapping_reviewer",
            "missing_confirmation:sql_review",
        ],
    }
    assert initialized["blocking_repair_request"] is None
    assert initialized["delivery_status"] == "not_ready"
    assert initialized["allowed_next_actions"] == ["prepare_source_logic"]
    assert initialized["phase_status"] == {
        "phase_3_field_formula": "blocked",
        "phase_4_sql_review": "blocked",
        "phase_6_data_preview": "blocked",
        "phase_12_delivery": "blocked",
    }
    assert initialized["required_artifacts"] == {
        gate: definition["required_artifacts"] for gate, definition in GATE_DEFINITIONS.items()
    }
    assert initialized["required_validators"] == {
        gate: definition["required_validators"] for gate, definition in GATE_DEFINITIONS.items()
    }


def test_create_report_run_persists_state_machine_fields(tmp_path: Path):
    create_report_run(tmp_path, run_id="demo-run", prompt="產出報表")

    state = load_run_state(tmp_path / "demo-run")

    assert state["current_user_step"] == 1
    assert state["current_internal_phase"] == 0
    assert "phase_3_field_formula" in state["gate_status"]
    assert state["confirmation_identity"] == {}
    assert "phase_status" in state
    assert "required_artifacts" in state
    assert "required_validators" in state
    assert state["gate_status"]["phase_3_field_formula"]["confirmation"]["checkpoint_id"] == (
        "field_formula_classification"
    )


def test_gate_definitions_match_required_plan_contract():
    assert GATE_DEFINITIONS == {
        "phase_3_field_formula": {
            "user_step": 1,
            "required_artifacts": ["checkpoints/01b_field_formula_classification.json"],
            "required_validators": [
                "requirement_understanding_reviewer",
                "schema_mapping_reviewer",
            ],
            "confirmation_checkpoint": "field_formula_classification",
            "allowed_next_actions": ["generate_sql", "request_changes"],
        },
        "phase_4_sql_review": {
            "user_step": 2,
            "required_artifacts": ["sql/query.sql", "checkpoints/02_sql_review.json"],
            "required_validators": ["sql_safety_reviewer", "schema_mapping_reviewer"],
            "confirmation_checkpoint": "sql_review",
            "allowed_next_actions": ["execute_select", "request_changes"],
        },
        "phase_6_data_preview": {
            "user_step": 3,
            "required_artifacts": [
                "checkpoints/03a_raw_data_preview.json",
                "checkpoints/03b_enriched_data_preview.json",
            ],
            "required_validators": ["db_execution_reviewer", "data_preview_reviewer"],
            "confirmation_checkpoint": "enriched_data_preview",
            "allowed_next_actions": ["render_report_design", "request_changes"],
        },
        "phase_12_delivery": {
            "user_step": 4,
            "required_artifacts": [
                "report/delivery/report.html",
                "report/delivery/report.xlsx",
                "review/final-review.json",
            ],
            "required_validators": [
                "report_content_reviewer",
                "visual_taste_reviewer",
                "react_technical_reviewer",
                "delivery_reviewer",
            ],
            "confirmation_checkpoint": "final_review",
            "allowed_next_actions": ["deliver", "request_changes"],
        },
    }


def test_evaluate_gate_returns_complete_when_gate_inputs_are_ready():
    state = initialize_state_machine(
        {
            "artifact_status": {
                "sql/query.sql": "complete",
                "checkpoints/02_sql_review.json": "complete",
            },
            "validator_results": [
                {"role": "sql_safety_reviewer", "status": "pass"},
                {"role": "schema_mapping_reviewer", "status": "pass"},
            ],
            "confirmation_identity": {
                "sql_review": {"confirmation_id": "confirm-1", "payload_hash": "hash-1"}
            },
        }
    )

    evaluation = evaluate_gate(state, "phase_4_sql_review")

    assert evaluation["status"] == "complete"
    assert evaluation["confirmation"]["checkpoint_id"] == "sql_review"
    assert evaluation["confirmation"]["payload_hash"] == "hash-1"
    assert evaluation["blocking_reason"] == []


def test_evaluate_gate_preserves_checkpoint_hash_before_confirmation():
    state = initialize_state_machine(
        {
            "artifact_status": {
                "checkpoints/01b_field_formula_classification.json": "complete",
            },
            "validator_results": [
                {"role": "requirement_understanding_reviewer", "status": "pass"},
                {"role": "schema_mapping_reviewer", "status": "pass"},
            ],
            "checkpoints": [
                {
                    "checkpoint": "field_formula_classification",
                    "checkpoint_id": "field_formula_classification",
                    "file": "checkpoints/01b_field_formula_classification.json",
                    "payload_hash": "checkpoint-hash",
                }
            ],
        }
    )

    evaluation = evaluate_gate(state, "phase_3_field_formula")

    assert evaluation["status"] == "blocked"
    assert evaluation["blocking_reason"] == ["missing_confirmation:field_formula_classification"]
    assert evaluation["confirmation"]["payload_hash"] == "checkpoint-hash"


def test_initialize_state_machine_merges_existing_gate_status_without_resetting_progress():
    initialized = initialize_state_machine(
        {
            "gate_status": {
                "phase_4_sql_review": {
                    "status": "complete",
                    "user_step": 99,
                    "required_artifacts": ["wrong"],
                    "required_validators": ["wrong"],
                    "allowed_next_actions": ["wrong"],
                    "confirmation": {
                        "required": False,
                        "checkpoint_id": "wrong",
                        "payload_hash": "existing-hash",
                    },
                    "blocking_reason": [],
                    "custom_metadata": {"reviewed_at": "2026-06-20T00:00:00Z"},
                }
            }
        }
    )

    sql_gate = initialized["gate_status"]["phase_4_sql_review"]
    assert sql_gate["status"] == "complete"
    assert sql_gate["confirmation"]["payload_hash"] == "existing-hash"
    assert sql_gate["confirmation"]["required"] is True
    assert sql_gate["confirmation"]["checkpoint_id"] == "sql_review"
    assert sql_gate["custom_metadata"] == {"reviewed_at": "2026-06-20T00:00:00Z"}
    assert sql_gate["user_step"] == 2
    assert sql_gate["required_artifacts"] == ["sql/query.sql", "checkpoints/02_sql_review.json"]
    assert sql_gate["required_validators"] == ["sql_safety_reviewer", "schema_mapping_reviewer"]
    assert sql_gate["allowed_next_actions"] == ["execute_select", "request_changes"]
    assert "phase_12_delivery" in initialized["gate_status"]
    assert initialized["phase_status"]["phase_4_sql_review"] == "complete"


@pytest.mark.parametrize("validator_status", ["complete", True])
def test_evaluate_gate_does_not_treat_non_pass_validator_status_as_passed(validator_status):
    state = initialize_state_machine(
        {
            "artifact_status": {
                "sql/query.sql": "complete",
                "checkpoints/02_sql_review.json": "complete",
            },
            "validator_results": [
                {"role": "sql_safety_reviewer", "status": validator_status},
                {"role": "schema_mapping_reviewer", "status": "pass"},
            ],
            "confirmation_identity": {
                "sql_review": {"confirmation_id": "confirm-1", "payload_hash": "hash-1"}
            },
        }
    )

    evaluation = evaluate_gate(state, "phase_4_sql_review")

    assert evaluation["status"] == "blocked"
    assert evaluation["blocking_reason"] == ["missing_validator:sql_safety_reviewer"]


def test_assert_can_advance_raises_when_gate_is_blocked_by_repair_request():
    state = initialize_state_machine(
        {
            "artifact_status": {
                "sql/query.sql": "complete",
                "checkpoints/02_sql_review.json": "complete",
            },
            "validator_results": [
                {"validator": "sql_safety_reviewer", "status": "pass"},
                {"role": "schema_mapping_reviewer", "status": "pass"},
            ],
            "confirmation_identity": {
                "sql_review": {"confirmation_id": "confirm-1", "payload_hash": "hash-1"}
            },
            "blocking_repair_request": {"gate": "phase_4_sql_review", "reason": "revise SQL"},
        }
    )

    with pytest.raises(GateBlockedError, match="phase_4_sql_review"):
        assert_can_advance(state, "phase_4_sql_review")

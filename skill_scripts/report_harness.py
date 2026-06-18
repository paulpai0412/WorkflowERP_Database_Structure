from __future__ import annotations

from pathlib import Path
from typing import Any

from skill_scripts.report_harness_state import (
    CHECKPOINT_DEFINITIONS,
    create_report_run,
    load_run_state,
    record_checkpoint,
    save_run_state,
)


class ReportHarnessError(RuntimeError):
    pass


class ReportHarness:
    def __init__(self, run_dir: str | Path):
        self.run_dir = Path(run_dir)

    @classmethod
    def create(
        cls,
        run_root: str | Path,
        *,
        run_id: str,
        prompt: str,
        input_files: list[str] | None = None,
    ) -> "ReportHarness":
        create_report_run(run_root, run_id=run_id, prompt=prompt, input_files=input_files)
        return cls(Path(run_root) / run_id)

    def state(self) -> dict[str, Any]:
        return load_run_state(self.run_dir)

    def update_state(self, **updates: Any) -> dict[str, Any]:
        state = self.state()
        state.update(updates)
        return save_run_state(self.run_dir, state)

    def invalidate_confirmations(self, *checkpoints: str) -> dict[str, Any]:
        state = self.state()
        confirmations = state.setdefault("user_confirmations", {})
        for checkpoint in checkpoints:
            confirmations.pop(checkpoint, None)
        return save_run_state(self.run_dir, state)

    def clear_downstream(self, checkpoints: list[str], **state_resets: Any) -> dict[str, Any]:
        state = self.state()
        checkpoint_set = set(checkpoints)
        state["checkpoints"] = [
            item for item in state.get("checkpoints", []) if item["checkpoint"] not in checkpoint_set
        ]
        confirmations = state.setdefault("user_confirmations", {})
        for checkpoint in checkpoints:
            confirmations.pop(checkpoint, None)
            definition = CHECKPOINT_DEFINITIONS.get(checkpoint)
            if definition:
                (self.run_dir / "checkpoints" / definition["file"]).unlink(missing_ok=True)
        state.update(state_resets)
        return save_run_state(self.run_dir, state)

    def confirm(self, checkpoint: str, action: str) -> dict[str, Any]:
        state = self.state()
        if checkpoint not in CHECKPOINT_DEFINITIONS:
            raise ReportHarnessError(f"Unknown checkpoint: {checkpoint}")
        if action not in CHECKPOINT_DEFINITIONS[checkpoint]["actions"]:
            raise ReportHarnessError(f"Invalid checkpoint action for {checkpoint}: {action}")
        if checkpoint not in {item["checkpoint"] for item in state.get("checkpoints", [])}:
            raise ReportHarnessError(f"{checkpoint} checkpoint has not been created")
        state.setdefault("user_confirmations", {})[checkpoint] = action
        return save_run_state(self.run_dir, state)

    def write_excel_confirmation(self, payload: dict[str, Any]) -> dict[str, Any]:
        return record_checkpoint(self.run_dir, "excel_confirmation", payload)

    def write_sql_review(self, sql: str, validation: dict[str, Any] | None = None) -> dict[str, Any]:
        self.clear_downstream(
            ["data_preview", "report_selection", "report_draft", "final_review"],
            execution_result_summary=None,
            report_type=None,
            report_design=None,
            report_options={},
            validator_results=[],
        )
        self.invalidate_confirmations("sql_review")
        self.update_state(sql_candidate=sql, sql_validation=validation or {"status": "pending_user_confirmation"})
        return record_checkpoint(self.run_dir, "sql_review", {"sql": sql, "validation": validation or {}})

    def write_data_preview(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.state().get("user_confirmations", {}).get("sql_review") != "同意查詢":
            raise ReportHarnessError("SQL must be confirmed before writing data preview")
        self.update_state(execution_result_summary=payload)
        return record_checkpoint(self.run_dir, "data_preview", payload)

    def write_report_selection(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.clear_downstream(["report_draft", "final_review"], validator_results=[])
        self.invalidate_confirmations("report_selection")
        updates: dict[str, Any] = {"report_options": payload.get("selected_options", payload)}
        if payload.get("selected_report_type"):
            updates["report_type"] = payload["selected_report_type"]
        if payload.get("selected_report_design"):
            updates["report_design"] = payload["selected_report_design"]
        self.update_state(**updates)
        return record_checkpoint(self.run_dir, "report_selection", payload)

    def write_report_draft(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.state().get("user_confirmations", {}).get("report_selection") != "產生報告":
            raise ReportHarnessError("Report selection must be confirmed before writing draft")
        self.clear_downstream(["final_review"], validator_results=[])
        self.invalidate_confirmations("report_draft")
        return record_checkpoint(self.run_dir, "report_draft", payload)

    def write_final_review(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.state().get("user_confirmations", {}).get("report_draft") != "接受":
            raise ReportHarnessError("Draft must be accepted before final review")
        self.update_state(validator_results=payload.get("validator_results", []))
        return record_checkpoint(self.run_dir, "final_review", payload)

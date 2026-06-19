from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from skill_scripts.validator_contracts import ValidatorContractError, build_final_review_gate
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
        confirmation_options = state.setdefault("user_confirmation_options", {})
        for checkpoint in checkpoints:
            confirmations.pop(checkpoint, None)
            confirmation_options.pop(checkpoint, None)
        return save_run_state(self.run_dir, state)

    def clear_downstream(self, checkpoints: list[str], **state_resets: Any) -> dict[str, Any]:
        state = self.state()
        checkpoint_set = set(checkpoints)
        state["checkpoints"] = [
            item for item in state.get("checkpoints", []) if item["checkpoint"] not in checkpoint_set
        ]
        confirmations = state.setdefault("user_confirmations", {})
        confirmation_options = state.setdefault("user_confirmation_options", {})
        for checkpoint in checkpoints:
            confirmations.pop(checkpoint, None)
            confirmation_options.pop(checkpoint, None)
            definition = CHECKPOINT_DEFINITIONS.get(checkpoint)
            if definition:
                (self.run_dir / "checkpoints" / definition["file"]).unlink(missing_ok=True)
            if checkpoint == "visual_design":
                (self.run_dir / "visual" / "visual-checkpoint.html").unlink(missing_ok=True)
        state.update(state_resets)
        return save_run_state(self.run_dir, state)

    def confirm(
        self,
        checkpoint: str,
        action: str,
        *,
        selected_options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        state = self.state()
        if checkpoint not in CHECKPOINT_DEFINITIONS:
            raise ReportHarnessError(f"Unknown checkpoint: {checkpoint}")
        if action not in CHECKPOINT_DEFINITIONS[checkpoint]["actions"]:
            raise ReportHarnessError(f"Invalid checkpoint action for {checkpoint}: {action}")
        if checkpoint not in {item["checkpoint"] for item in state.get("checkpoints", [])}:
            raise ReportHarnessError(f"{checkpoint} checkpoint has not been created")
        state.setdefault("user_confirmations", {})[checkpoint] = action
        state.setdefault("user_confirmation_options", {})[checkpoint] = selected_options or {}
        return save_run_state(self.run_dir, state)

    def write_excel_confirmation(self, payload: dict[str, Any]) -> dict[str, Any]:
        return record_checkpoint(self.run_dir, "excel_confirmation", payload)

    def write_sql_review(self, sql: str, validation: dict[str, Any] | None = None) -> dict[str, Any]:
        self.clear_downstream(
            ["data_preview", "report_selection", "design_brief", "visual_design", "report_draft", "final_review"],
            execution_result_summary=None,
            report_type=None,
            report_design=None,
            report_design_brief=None,
            visual_design_checkpoint=None,
            report_options={},
            validator_results=[],
        )
        self.invalidate_confirmations("sql_review")
        self.update_state(sql_candidate=sql, sql_validation=validation or {"status": "pending_user_confirmation"})
        return record_checkpoint(self.run_dir, "sql_review", {"sql": sql, "validation": validation or {}})

    def write_data_preview(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.state().get("user_confirmations", {}).get("sql_review") != "同意查詢":
            raise ReportHarnessError("SQL must be confirmed before writing data preview")
        self.clear_downstream(
            ["report_selection", "design_brief", "visual_design", "report_draft", "final_review"],
            report_type=None,
            report_design=None,
            report_design_brief=None,
            visual_design_checkpoint=None,
            report_options={},
            validator_results=[],
        )
        self.update_state(execution_result_summary=payload)
        return record_checkpoint(self.run_dir, "data_preview", payload)

    def write_report_selection(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.clear_downstream(
            ["design_brief", "visual_design", "report_draft", "final_review"],
            report_design_brief=None,
            visual_design_checkpoint=None,
            validator_results=[],
        )
        self.invalidate_confirmations("report_selection")
        updates: dict[str, Any] = {"report_options": payload.get("selected_options", payload)}
        if payload.get("selected_report_type"):
            updates["report_type"] = payload["selected_report_type"]
        if payload.get("selected_report_design"):
            updates["report_design"] = payload["selected_report_design"]
        self.update_state(**updates)
        return record_checkpoint(self.run_dir, "report_selection", payload)

    def write_design_brief(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.clear_downstream(
            ["visual_design", "report_draft", "final_review"],
            validator_results=[],
            visual_design_checkpoint=None,
        )
        self.invalidate_confirmations("design_brief")
        self.update_state(report_design_brief=payload)
        return record_checkpoint(self.run_dir, "design_brief", payload)

    def write_visual_design(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.state().get("user_confirmations", {}).get("design_brief") != "確認設計":
            raise ReportHarnessError("Design brief must be confirmed before visual checkpoint")
        self.clear_downstream(
            ["report_draft", "final_review"],
            validator_results=[],
        )
        self.invalidate_confirmations("visual_design")
        self.update_state(visual_design_checkpoint=payload)
        return record_checkpoint(self.run_dir, "visual_design", payload)

    def write_report_draft(self, payload: dict[str, Any]) -> dict[str, Any]:
        confirmations = self.state().get("user_confirmations", {})
        if confirmations.get("report_selection") != "產生報告":
            raise ReportHarnessError("Report selection must be confirmed before writing draft")
        if confirmations.get("design_brief") != "確認設計":
            raise ReportHarnessError("Design brief must be confirmed before writing draft")
        if confirmations.get("visual_design") != "確認視覺設計":
            raise ReportHarnessError("Visual design must be confirmed before writing draft")
        self.clear_downstream(["final_review"], validator_results=[])
        self.invalidate_confirmations("report_draft")
        return record_checkpoint(self.run_dir, "report_draft", payload)

    def write_final_review(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.state().get("user_confirmations", {}).get("report_draft") != "接受":
            raise ReportHarnessError("Draft must be accepted before final review")
        self.update_state(
            validator_results=payload.get("validator_results", []),
            accepted_residual_risks=[],
        )
        return record_checkpoint(self.run_dir, "final_review", payload)

    def _final_confirmation_selected_options(self, state: dict[str, Any]) -> dict[str, Any]:
        options = state.get("user_confirmation_options", {}).get("final_review")
        if isinstance(options, dict) and options:
            return options

        definition = CHECKPOINT_DEFINITIONS["final_review"]
        path = self.run_dir / "checkpoints" / definition["file"].replace(".json", ".confirmation.json")
        if not path.exists():
            return {}
        try:
            confirmation = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        selected_options = confirmation.get("selectedOptions")
        return selected_options if isinstance(selected_options, dict) else {}

    def _final_confirmation_accepted_residual_risks(self, state: dict[str, Any]) -> list[str]:
        if state.get("user_confirmations", {}).get("final_review") != "完成":
            return []
        accepted = self._final_confirmation_selected_options(state).get("acceptedResidualRisks")
        if not isinstance(accepted, list) or not all(isinstance(item, str) for item in accepted):
            return []
        return accepted

    def can_deliver(self) -> dict[str, Any]:
        state = self.state()
        accepted_residual_risks = self._final_confirmation_accepted_residual_risks(state)
        explicit_user_acceptance = bool(accepted_residual_risks)
        try:
            return build_final_review_gate(
                state.get("validator_results", []),
                explicit_user_acceptance=explicit_user_acceptance,
                accepted_residual_risks=accepted_residual_risks,
            )
        except ValidatorContractError as exc:
            return {
                "allowed": False,
                "blocking_validators": ["validator_contract"],
                "accepted_residual_risks": accepted_residual_risks,
                "error": str(exc),
            }

    def append_repair_log(
        self,
        *,
        validator: str,
        failure: str,
        scope: str,
        minimal_vertical_slice: str,
        files_changed: list[str],
        validation_rerun: str,
        residual_risk: str,
    ) -> Path:
        path = self.run_dir / "review" / "repair-log.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        changed = "\n".join(f"- {item}" for item in files_changed) if files_changed else "- None"
        entry = (
            f"## {validator}\n\n"
            f"Failure:\n{failure}\n\n"
            f"Scope:\n{scope}\n\n"
            f"Minimal vertical slice:\n{minimal_vertical_slice}\n\n"
            f"Files changed:\n{changed}\n\n"
            f"Validation rerun:\n{validation_rerun}\n\n"
            f"Residual risk:\n{residual_risk}\n\n"
        )
        with path.open("a", encoding="utf-8") as handle:
            handle.write(entry)
        return path

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


CHECKPOINT_DEFINITIONS: dict[str, dict[str, Any]] = {
    "excel_confirmation": {
        "index": 1,
        "file": "01_excel_confirmation.json",
        "title": "確認欄位與公式",
        "actions": ["確認欄位與公式", "要求修正"],
    },
    "sql_review": {
        "index": 2,
        "file": "02_sql_review.json",
        "title": "SQL 查詢確認",
        "actions": ["同意查詢", "調整需求"],
    },
    "data_preview": {
        "index": 3,
        "file": "03_data_preview.json",
        "title": "資料預覽確認",
        "actions": ["資料正確", "重新查詢"],
    },
    "report_selection": {
        "index": 4,
        "file": "04_report_selection.json",
        "title": "報表格式選擇",
        "actions": ["產生報告", "修改格式"],
    },
    "report_draft": {
        "index": 5,
        "file": "05_report_draft.json",
        "title": "報告初稿審核",
        "actions": ["接受", "修正報告"],
    },
    "final_review": {
        "index": 6,
        "file": "06_final_review.json",
        "title": "最終報告審核",
        "actions": ["完成", "回到初稿"],
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_path(run_dir: str | Path) -> Path:
    return Path(run_dir) / "state.json"


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def create_report_run(
    run_root: str | Path,
    *,
    run_id: str,
    prompt: str,
    input_files: list[str] | None = None,
) -> dict[str, Any]:
    run_dir = Path(run_root) / run_id
    if _state_path(run_dir).exists():
        raise FileExistsError(f"Report run already exists: {run_id}")
    for child in [
        "inputs",
        "sql",
        "data",
        "checkpoints",
        "reports",
        "source",
        "plan",
        "audit",
        "review",
        "report/payload",
    ]:
        (run_dir / child).mkdir(parents=True, exist_ok=True)

    state = {
        "run_id": run_id,
        "prompt": prompt,
        "input_files": input_files or [],
        "schema_snapshot": None,
        "excel_requirement": None,
        "sql_candidate": None,
        "sql_validation": None,
        "execution_result_summary": None,
        "report_type": None,
        "report_design": None,
        "report_options": {},
        "validator_results": [],
        "user_confirmations": {},
        "checkpoints": [],
        "created_at": _now(),
        "updated_at": _now(),
    }
    _write_json(_state_path(run_dir), state)
    return state


def load_run_state(run_dir: str | Path) -> dict[str, Any]:
    return json.loads(_state_path(run_dir).read_text(encoding="utf-8"))


def save_run_state(run_dir: str | Path, state: dict[str, Any]) -> dict[str, Any]:
    state = deepcopy(state)
    state["updated_at"] = _now()
    _write_json(_state_path(run_dir), state)
    return state


def record_checkpoint(run_dir: str | Path, checkpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    if checkpoint not in CHECKPOINT_DEFINITIONS:
        raise ValueError(f"Unknown checkpoint: {checkpoint}")
    definition = CHECKPOINT_DEFINITIONS[checkpoint]
    checkpoint_payload = {
        "checkpoint": checkpoint,
        "title": definition["title"],
        "actions": definition["actions"],
        "payload": payload,
        "created_at": _now(),
    }
    run_path = Path(run_dir)
    _write_json(run_path / "checkpoints" / definition["file"], checkpoint_payload)

    state = load_run_state(run_path)
    entry = {
        "checkpoint": checkpoint,
        "file": f"checkpoints/{definition['file']}",
        "created_at": checkpoint_payload["created_at"],
    }
    state["checkpoints"] = [item for item in state["checkpoints"] if item["checkpoint"] != checkpoint]
    state["checkpoints"].append(entry)
    save_run_state(run_path, state)
    return checkpoint_payload


def append_audit_event(run_dir: str | Path, event: str, payload: dict[str, Any]) -> dict[str, Any]:
    entry = {"event": event, "payload": payload, "created_at": _now()}
    path = Path(run_dir) / "audit" / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def write_confirmation(run_dir: str | Path, checkpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    if checkpoint not in CHECKPOINT_DEFINITIONS:
        raise ValueError(f"Unknown checkpoint: {checkpoint}")
    definition = CHECKPOINT_DEFINITIONS[checkpoint]
    confirmation = {
        "checkpoint": checkpoint,
        "action": payload["action"],
        "comment": payload.get("comment", ""),
        "selectedOptions": payload.get("selectedOptions", {}),
        "created_at": _now(),
    }
    filename = definition["file"].replace(".json", ".confirmation.json")
    _write_json(Path(run_dir) / "checkpoints" / filename, confirmation)
    return confirmation

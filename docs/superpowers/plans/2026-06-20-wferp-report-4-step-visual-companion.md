# WFERP Report 4-Step Visual Companion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve the existing 13-phase WFERP report harness while replacing the user-facing Visual Companion with a 4-step, state-gated, real-data workbench that supports prompt repair, dynamic HTML/data visualization UI, and true `.xlsx` delivery.

**Architecture:** Add an explicit state-machine layer on top of the existing `state.json`, then aggregate existing technical checkpoints into 4 user-facing steps. The companion reads state and current-run payloads, renders dynamic user-oriented pages, and POSTs confirmations or prompt repair requests back into the same gate system. Excel output is generated as a real workbook through spreadsheet tooling while HTML and visual previews are rendered from confirmed payloads.

**Tech Stack:** Python 3.12, pytest, existing `skill_scripts` harness modules, local JSON run artifacts, SQLite workspace, stdlib HTTP companion server, Visual Companion HTML/CSS/JS, Build Web Apps plugin for UI design, Build Web Data Visualization plugin for KPI/chart/table design, spreadsheets skill for `.xlsx` generation and verification.

---

## Scope And Guardrails

Do not remove or collapse the 13 technical phases. Do not remove existing SQL safety, DB execution evidence, SQLite enrichment, lookup import, validator gates, repair log, final review, or delivery evidence.

This plan changes the workflow control model and user-facing companion presentation. It must keep existing CLI behavior compatible unless a task explicitly adds a new command.

Production DB access remains SELECT-only. No task in this plan requires running production DB queries.

When implementing UI or final HTML design, use `Build Web Apps` and `Build Web Data Visualization` if available. If those plugin capabilities are unavailable in the implementation session, stop and ask the user before using a fallback UI implementation. Do not silently hand-roll a static JSON page.

When implementing true Excel output, use the `spreadsheets` skill. If spreadsheet tooling is unavailable, stop and ask the user before falling back. Do not emulate final Excel delivery with HTML only.

## File Structure

Create:

- `skill_scripts/harness_state_machine.py`  
  Owns phase/user-step mapping, gate definitions, payload hashes, state initialization, gate evaluation, progression checks, and repair-block state.

- `skill_scripts/user_step_payload.py`  
  Aggregates existing checkpoints, state, SQLite manifest, report payload, and delivery artifacts into 4 user-step payloads for the Visual Companion.

- `skill_scripts/excel_workbook_exporter.py`  
  Builds a minimal real `.xlsx` workbook from a workbook payload and writes workbook evidence. The implementation session must use the `spreadsheets` skill to refine generation and verification.

- `tests/skill_scripts/test_harness_state_machine.py`  
  Tests state machine defaults, gate blocking, payload hash mismatch, validator requirements, repair blocking, and current action calculation.

- `tests/skill_scripts/test_user_step_payload.py`  
  Tests 4-step payload aggregation, source-to-output matrix rendering data, 50-row limits, SQLite summary, Excel workbook preview payload, and no mock data in Step 3.

- `tests/skill_scripts/test_excel_workbook_exporter.py`  
  Tests true `.xlsx` output, sheet inventory evidence, row/column counts, formula/value strategy, and number consistency metadata.

- `skills/wferp-report/references/visual-companion-ui.md`  
  Documents 4-step UI, plugin ownership, prompt repair loop, state-gated rendering, 50-row preview, and Excel workbook preview.

Modify:

- `skill_scripts/report_harness_state.py`  
  Initialize new state-machine fields, attach payload hashes and checkpoint IDs to checkpoints/confirmations, and keep existing checkpoint definitions compatible.

- `skill_scripts/report_harness.py`  
  Route transitions through the state machine, update gate status after writes/confirmations, block stale or missing requirements, and record prompt repair requests.

- `skill_scripts/checkpoint_companion.py`  
  Replace technical checkpoint-first page structure with 4 user-step navigation and dynamic state-driven rendering while preserving existing POST confirmation compatibility.

- `skill_scripts/cli_report_harness.py`  
  Add commands or options for user-step preview, state gate checking, prompt repair, and Excel export.

- `skill_scripts/validator_contracts.py`  
  Require fresh reviewer/subagent evidence metadata for validators and expose grouped gate status.

- `skills/wferp-report/SKILL.md`  
  Replace the current mixed checkpoint wording with the approved 13-phase internal / 4-step user-facing contract.

- `skills/wferp-report/references/harness.md`  
  Document 4 user steps, state-machine progression, prompt repair routing, and phase mapping.

- `skills/wferp-report/references/checkpoint-payload-schema.md`  
  Add confirmation identity and user-step payload schema.

- `skills/wferp-report/references/excel-intake.md`  
  Add source-to-output data logic contract and formula consistency rules.

- `skills/wferp-report/references/sqlite-enrichment.md`  
  Add user-facing SQLite/lookup presentation for Steps 1 and 3.

- `skills/wferp-report/references/validators.md`  
  Require original subagent/fresh reviewer design and user-step grouped validator evidence.

- `skills/wferp-report/references/single-html-export.md`  
  State that final HTML UI uses Build Web Apps and Build Web Data Visualization when available.

- `skills/wferp-report/README.md`  
  Summarize the 13-phase internal engine and 4-step Visual Companion.

- `AGENTS.md`  
  Point WFERP report tasks to the state-machine gate and plugin ownership rules.

---

### Task 1: Add State Machine Foundation

**Files:**
- Create: `skill_scripts/harness_state_machine.py`
- Create: `tests/skill_scripts/test_harness_state_machine.py`
- Modify: `skill_scripts/report_harness_state.py`
- Modify: `tests/skill_scripts/test_report_harness_state.py`

- [ ] **Step 1: Write the failing tests for initial state fields**

Add to `tests/skill_scripts/test_harness_state_machine.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from skill_scripts.harness_state_machine import (
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
    assert "phase_4_sql_review" in initialized["gate_status"]
    assert initialized["blocking_repair_request"] is None
    assert initialized["delivery_status"] == "not_ready"
    assert initialized["allowed_next_actions"] == ["prepare_source_logic"]


def test_create_report_run_persists_state_machine_fields(tmp_path: Path):
    create_report_run(tmp_path, run_id="demo-run", prompt="產出報表")

    state = load_run_state(tmp_path / "demo-run")

    assert state["current_user_step"] == 1
    assert state["current_internal_phase"] == 0
    assert "phase_3_field_formula" in state["gate_status"]
    assert state["confirmation_identity"] == {}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```powershell
. .\.tools\activate.ps1
python -m pytest tests/skill_scripts/test_harness_state_machine.py::test_initialize_state_machine_adds_required_workflow_fields tests/skill_scripts/test_harness_state_machine.py::test_create_report_run_persists_state_machine_fields -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'skill_scripts.harness_state_machine'`.

- [ ] **Step 3: Implement minimal state-machine module**

Create `skill_scripts/harness_state_machine.py`:

```python
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any


USER_STEP_MAPPING: dict[str, dict[str, Any]] = {
    "step_1_source_to_output": {"index": 1, "title": "來源與產出邏輯確認", "phases": [0, 1, 2, 3]},
    "step_2_sql_query": {"index": 2, "title": "SQL 查詢確認", "phases": [4, 5]},
    "step_3_data_and_design": {"index": 3, "title": "資料結果與報表設計確認", "phases": [6, 7, 8, 9]},
    "step_4_final_delivery": {"index": 4, "title": "成品與交付確認", "phases": [10, 11, 12]},
}


GATE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "phase_3_field_formula": {
        "user_step": 1,
        "required_artifacts": ["checkpoints/01b_field_formula_classification.json"],
        "required_validators": [
            "requirement_understanding_reviewer",
            "schema_mapping_reviewer",
        ],
        "confirmation_checkpoint": "field_formula_classification",
        "next_actions": ["generate_sql", "request_changes"],
    },
    "phase_4_sql_review": {
        "user_step": 2,
        "required_artifacts": ["sql/query.sql", "checkpoints/02_sql_review.json"],
        "required_validators": ["sql_safety_reviewer", "schema_mapping_reviewer"],
        "confirmation_checkpoint": "sql_review",
        "next_actions": ["execute_select", "request_changes"],
    },
    "phase_6_data_preview": {
        "user_step": 3,
        "required_artifacts": [
            "checkpoints/03a_raw_data_preview.json",
            "checkpoints/03b_enriched_data_preview.json",
        ],
        "required_validators": ["db_execution_reviewer", "data_preview_reviewer"],
        "confirmation_checkpoint": "enriched_data_preview",
        "next_actions": ["render_report_design", "request_changes"],
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
        "next_actions": ["deliver", "request_changes"],
    },
}


class GateBlockedError(RuntimeError):
    pass


@dataclass(frozen=True)
class GateEvaluation:
    gate: str
    status: str
    missing_artifacts: list[str]
    missing_validators: list[str]
    confirmation_required: bool
    confirmation_matched: bool
    blocking_reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "gate": self.gate,
            "status": self.status,
            "missing_artifacts": self.missing_artifacts,
            "missing_validators": self.missing_validators,
            "confirmation_required": self.confirmation_required,
            "confirmation_matched": self.confirmation_matched,
            "blocking_reason": self.blocking_reason,
        }


def _base_gate_status() -> dict[str, dict[str, Any]]:
    statuses: dict[str, dict[str, Any]] = {}
    for gate, definition in GATE_DEFINITIONS.items():
        statuses[gate] = {
            "status": "pending",
            "user_step": definition["user_step"],
            "required_artifacts": list(definition["required_artifacts"]),
            "required_validators": list(definition["required_validators"]),
            "confirmation": {
                "required": True,
                "checkpoint_id": definition["confirmation_checkpoint"],
                "payload_hash": "",
            },
            "allowed_next_actions": [],
            "blocking_reason": "",
        }
    return statuses


def initialize_state_machine(state: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(state)
    result.setdefault("current_user_step", 1)
    result.setdefault("current_internal_phase", 0)
    result.setdefault("user_step_mapping", deepcopy(USER_STEP_MAPPING))
    result.setdefault("phase_status", {})
    result.setdefault("gate_status", _base_gate_status())
    result.setdefault("allowed_next_actions", ["prepare_source_logic"])
    result.setdefault("required_artifacts", {})
    result.setdefault("required_validators", {})
    result.setdefault("confirmation_identity", {})
    result.setdefault("blocking_repair_request", None)
    result.setdefault("delivery_status", "not_ready")
    return result


def _validator_statuses(state: dict[str, Any]) -> dict[str, str]:
    validators = state.get("validator_results")
    if not isinstance(validators, list):
        return {}
    statuses: dict[str, str] = {}
    for item in validators:
        if isinstance(item, dict) and item.get("role"):
            statuses[str(item["role"])] = str(item.get("status", ""))
    return statuses


def evaluate_gate(state: dict[str, Any], gate: str) -> dict[str, Any]:
    if gate not in GATE_DEFINITIONS:
        raise KeyError(f"Unknown gate: {gate}")
    definition = GATE_DEFINITIONS[gate]
    artifacts = state.get("artifact_status", {})
    if not isinstance(artifacts, dict):
        artifacts = {}
    missing_artifacts = [
        path for path in definition["required_artifacts"] if artifacts.get(path) != "present"
    ]
    statuses = _validator_statuses(state)
    missing_validators = [
        role for role in definition["required_validators"] if statuses.get(role) != "pass"
    ]
    confirmation_id = definition["confirmation_checkpoint"]
    identities = state.get("confirmation_identity", {})
    confirmation = identities.get(confirmation_id) if isinstance(identities, dict) else None
    confirmation_matched = isinstance(confirmation, dict) and confirmation.get("status") == "matched"
    repair = state.get("blocking_repair_request")
    blocking_reason = ""
    if repair:
        blocking_reason = "blocking_repair_request"
    elif missing_artifacts:
        blocking_reason = "missing_artifacts"
    elif missing_validators:
        blocking_reason = "missing_validators"
    elif not confirmation_matched:
        blocking_reason = "confirmation_identity"
    status = "complete" if not blocking_reason else "blocked"
    return GateEvaluation(
        gate=gate,
        status=status,
        missing_artifacts=missing_artifacts,
        missing_validators=missing_validators,
        confirmation_required=True,
        confirmation_matched=confirmation_matched,
        blocking_reason=blocking_reason,
    ).as_dict()


def assert_can_advance(state: dict[str, Any], gate: str) -> None:
    evaluation = evaluate_gate(state, gate)
    if evaluation["status"] != "complete":
        raise GateBlockedError(f"{gate} blocked: {evaluation['blocking_reason']}")
```

- [ ] **Step 4: Initialize state-machine fields in report run creation**

Modify `skill_scripts/report_harness_state.py`:

```python
from skill_scripts.harness_state_machine import initialize_state_machine
```

Then replace the final write in `create_report_run()`:

```python
    state = initialize_state_machine(state)
    _write_json(_state_path(run_dir), state)
    return state
```

- [ ] **Step 5: Run tests and verify pass**

Run:

```powershell
. .\.tools\activate.ps1
python -m pytest tests/skill_scripts/test_harness_state_machine.py tests/skill_scripts/test_report_harness_state.py -v
```

Expected: PASS. Existing `test_creates_run_directory_with_state_json` must continue to pass.

- [ ] **Step 6: Commit**

```powershell
. .\.tools\activate.ps1
git add skill_scripts/harness_state_machine.py skill_scripts/report_harness_state.py tests/skill_scripts/test_harness_state_machine.py tests/skill_scripts/test_report_harness_state.py
git commit -m "feat: add wferp harness state machine"
```

---

### Task 2: Add Confirmation Identity And State-Gated Progression

**Files:**
- Modify: `skill_scripts/report_harness_state.py`
- Modify: `skill_scripts/report_harness.py`
- Modify: `skill_scripts/cli_report_harness.py`
- Modify: `tests/skill_scripts/test_report_harness_state.py`
- Modify: `tests/skill_scripts/test_report_harness.py`
- Modify: `tests/skill_scripts/test_cli_report_harness.py`

- [ ] **Step 1: Write failing tests for payload hash and confirmation identity**

Add to `tests/skill_scripts/test_report_harness_state.py`:

```python
def test_checkpoint_records_payload_hash_and_checkpoint_id(tmp_path: Path):
    create_report_run(tmp_path, run_id="demo-run", prompt="prompt")

    checkpoint = record_checkpoint(tmp_path / "demo-run", "sql_review", {"sql": "SELECT 1"})

    assert checkpoint["checkpoint_id"] == "sql_review"
    assert len(checkpoint["payload_hash"]) == 64
    state = load_run_state(tmp_path / "demo-run")
    assert state["gate_status"]["phase_4_sql_review"]["confirmation"]["payload_hash"] == checkpoint["payload_hash"]


def test_write_confirmation_requires_matching_identity(tmp_path: Path):
    create_report_run(tmp_path, run_id="demo-run", prompt="prompt")
    checkpoint = record_checkpoint(tmp_path / "demo-run", "sql_review", {"sql": "SELECT 1"})

    confirmation = write_confirmation(
        tmp_path / "demo-run",
        "sql_review",
        {
            "action": "同意查詢",
            "run_id": "demo-run",
            "checkpoint_id": "sql_review",
            "payload_hash": checkpoint["payload_hash"],
            "confirmation_id": "confirm-001",
        },
    )

    assert confirmation["run_id"] == "demo-run"
    assert confirmation["checkpoint_id"] == "sql_review"
    assert confirmation["payload_hash"] == checkpoint["payload_hash"]
    assert confirmation["confirmation_id"] == "confirm-001"
```

Add to `tests/skill_scripts/test_report_harness.py`:

```python
def test_state_gate_blocks_data_preview_when_confirmation_identity_is_missing(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="demo-run", prompt="請查詢費用")
    harness.write_sql_review("SELECT * FROM ACPTA")
    harness.confirm("sql_review", "同意查詢")

    with pytest.raises(ReportHarnessError, match="confirmation_identity"):
        harness.write_data_preview({"rows": [{"部門": "D001"}], "row_count": 1})
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
. .\.tools\activate.ps1
python -m pytest tests/skill_scripts/test_report_harness_state.py::test_checkpoint_records_payload_hash_and_checkpoint_id tests/skill_scripts/test_report_harness_state.py::test_write_confirmation_requires_matching_identity tests/skill_scripts/test_report_harness.py::test_state_gate_blocks_data_preview_when_confirmation_identity_is_missing -v
```

Expected: FAIL because checkpoint payloads do not include `payload_hash`, confirmations do not require identity, and `write_data_preview` only checks `user_confirmations`.

- [ ] **Step 3: Add stable payload hashing**

Modify `skill_scripts/report_harness_state.py`:

```python
import hashlib
import uuid
```

Add:

```python
def _payload_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
```

In `record_checkpoint()`, compute and persist:

```python
    payload_hash = _payload_hash(payload)
    checkpoint_payload = {
        "checkpoint": checkpoint,
        "checkpoint_id": checkpoint,
        "title": definition["title"],
        "actions": definition["actions"],
        "payload": payload,
        "payload_hash": payload_hash,
        "created_at": _now(),
    }
```

Update the state gate confirmation hash:

```python
    gate_status = state.setdefault("gate_status", {})
    for gate in gate_status.values():
        confirmation = gate.get("confirmation")
        if isinstance(confirmation, dict) and confirmation.get("checkpoint_id") == checkpoint:
            confirmation["payload_hash"] = payload_hash
            gate["status"] = "ready_for_user"
```

- [ ] **Step 4: Require confirmation identity in write_confirmation**

Modify `write_confirmation()`:

```python
    state = load_run_state(run_dir)
    expected_hash = ""
    for gate in state.get("gate_status", {}).values():
        confirmation_gate = gate.get("confirmation") if isinstance(gate, dict) else None
        if isinstance(confirmation_gate, dict) and confirmation_gate.get("checkpoint_id") == checkpoint:
            expected_hash = str(confirmation_gate.get("payload_hash") or "")
            break

    run_id = payload.get("run_id")
    checkpoint_id = payload.get("checkpoint_id") or payload.get("checkpointId")
    payload_hash = payload.get("payload_hash")
    if run_id != state.get("run_id") or checkpoint_id != checkpoint or payload_hash != expected_hash:
        raise ValueError("confirmation identity does not match current checkpoint")

    confirmation = {
        "run_id": run_id,
        "checkpoint": checkpoint,
        "checkpoint_id": checkpoint,
        "action": payload["action"],
        "comment": payload.get("comment", ""),
        "selectedOptions": payload.get("selectedOptions", {}),
        "payload_hash": payload_hash,
        "confirmation_id": payload.get("confirmation_id") or str(uuid.uuid4()),
        "created_at": _now(),
    }
```

Update state confirmation identity:

```python
    state.setdefault("confirmation_identity", {})[checkpoint] = {
        "status": "matched",
        "payload_hash": payload_hash,
        "confirmation_id": confirmation["confirmation_id"],
        "confirmed_at": confirmation["created_at"],
    }
    save_run_state(run_dir, state)
```

- [ ] **Step 5: Route data preview through state gate**

Modify `skill_scripts/report_harness.py` imports:

```python
from skill_scripts.harness_state_machine import GateBlockedError, assert_can_advance
```

In `write_data_preview()`, after the existing user confirmation check:

```python
        try:
            assert_can_advance(self.state(), "phase_4_sql_review")
        except GateBlockedError as exc:
            raise ReportHarnessError(str(exc)) from exc
```

- [ ] **Step 6: Update companion and CLI confirmation payloads**

Modify `skill_scripts/checkpoint_companion.py` JavaScript body payload so it includes:

```javascript
run_id: window.__CHECKPOINT_PAYLOAD__.run_id,
checkpoint_id: window.__CHECKPOINT_PAYLOAD__.checkpoint_id || checkpoint,
payload_hash: window.__CHECKPOINT_PAYLOAD__.payload_hash,
confirmation_id: crypto.randomUUID ? crypto.randomUUID() : String(Date.now())
```

Modify `_render_checkpoint_page()` to include `run_id` in `checkpoint_payload` before serializing:

```python
    script_payload = dict(checkpoint_payload)
    script_payload["run_id"] = run_id
```

Modify `skill_scripts/cli_report_harness.py` `confirm` subcommand to load the checkpoint file and send identity to `write_confirmation()`.

- [ ] **Step 7: Run focused tests**

Run:

```powershell
. .\.tools\activate.ps1
python -m pytest tests/skill_scripts/test_report_harness_state.py tests/skill_scripts/test_report_harness.py tests/skill_scripts/test_checkpoint_companion.py tests/skill_scripts/test_cli_report_harness.py -v
```

Expected: PASS after updating tests that directly call `write_confirmation()` to include identity.

- [ ] **Step 8: Commit**

```powershell
. .\.tools\activate.ps1
git add skill_scripts/report_harness_state.py skill_scripts/report_harness.py skill_scripts/checkpoint_companion.py skill_scripts/cli_report_harness.py tests/skill_scripts/test_report_harness_state.py tests/skill_scripts/test_report_harness.py tests/skill_scripts/test_checkpoint_companion.py tests/skill_scripts/test_cli_report_harness.py
git commit -m "feat: gate confirmations by checkpoint identity"
```

---

### Task 3: Add 4-Step User Payload Aggregation

**Files:**
- Create: `skill_scripts/user_step_payload.py`
- Create: `tests/skill_scripts/test_user_step_payload.py`
- Modify: `skill_scripts/cli_report_harness.py`

- [ ] **Step 1: Write failing tests for user-step payload aggregation**

Create `tests/skill_scripts/test_user_step_payload.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from skill_scripts.report_harness import ReportHarness
from skill_scripts.user_step_payload import build_user_step_payload


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_step_1_builds_source_to_output_logic_payload(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="產出 HTML 與 Excel 報表")
    harness.write_field_formula_classification(
        {
            "output_targets": ["html", "excel"],
            "source_inventory": [{"kind": "excel_source", "name": "orders.xlsx"}],
            "source_to_output_matrix": [
                {
                    "output_item": "Excel 摘要 Sheet",
                    "source": "DB raw rows + Excel lookup",
                    "transformation_logic": "依客戶彙總金額",
                    "processing_layer": "sqlite-enrichment",
                    "verification": "HTML KPI 與 Excel totals match",
                }
            ],
            "formula_semantics": [
                {
                    "name": "未交金額",
                    "intent": "數量乘單價",
                    "processing_layer": "sqlite-enrichment",
                }
            ],
        }
    )

    payload = build_user_step_payload(harness.run_dir, 1)

    assert payload["user_step"] == 1
    assert payload["title"] == "來源與產出邏輯確認"
    assert payload["output_targets"] == ["html", "excel"]
    assert payload["source_to_output_matrix"][0]["output_item"] == "Excel 摘要 Sheet"
    assert payload["formula_semantics"][0]["processing_layer"] == "sqlite-enrichment"


def test_step_3_uses_real_raw_and_enriched_rows_with_50_row_limit(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="產出報表")
    raw_rows = [{"id": index, "amount": index * 10} for index in range(60)]
    enriched_rows = [{"id": index, "amount": index * 10, "category": "A"} for index in range(60)]
    harness.update_state(
        raw_data_preview={"row_count": 60, "columns": ["id", "amount"], "sample_rows": raw_rows},
        enriched_data_preview={"row_count": 60, "columns": ["id", "amount", "category"], "sample_rows": enriched_rows},
        sqlite_manifest={
            "lookup_tables": ["lookup_customer"],
            "lookup_row_counts": {"lookup_customer": 3},
            "ignored_lookup_rows": {},
        },
    )

    payload = build_user_step_payload(harness.run_dir, 3)

    assert payload["user_step"] == 3
    assert len(payload["raw_preview"]["sample_rows"]) == 50
    assert len(payload["enriched_preview"]["sample_rows"]) == 50
    assert payload["sqlite_summary"]["lookup_tables"] == ["lookup_customer"]
    assert payload["data_source"] == "current-run"
    assert payload["uses_mock_data"] is False
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
. .\.tools\activate.ps1
python -m pytest tests/skill_scripts/test_user_step_payload.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement user-step payload builder**

Create `skill_scripts/user_step_payload.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from skill_scripts.report_harness_state import load_run_state


USER_STEP_TITLES = {
    1: "來源與產出邏輯確認",
    2: "SQL 查詢確認",
    3: "資料結果與報表設計確認",
    4: "成品與交付確認",
}


def _checkpoint_payload(run_dir: Path, filename: str) -> dict[str, Any]:
    path = run_dir / "checkpoints" / filename
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("payload", {})


def _limit_rows(preview: dict[str, Any], limit: int = 50) -> dict[str, Any]:
    result = dict(preview)
    rows = result.get("sample_rows") or result.get("rows") or []
    if isinstance(rows, list):
        result["sample_rows"] = rows[:limit]
    else:
        result["sample_rows"] = []
    return result


def _step_1(run_dir: Path, state: dict[str, Any]) -> dict[str, Any]:
    classification = state.get("column_classification") or _checkpoint_payload(run_dir, "01b_field_formula_classification.json")
    if not isinstance(classification, dict):
        classification = {}
    return {
        "user_step": 1,
        "title": USER_STEP_TITLES[1],
        "prompt": state.get("prompt", ""),
        "output_targets": classification.get("output_targets", ["html"]),
        "source_inventory": classification.get("source_inventory", []),
        "source_to_output_matrix": classification.get("source_to_output_matrix", []),
        "formula_semantics": classification.get("formula_semantics", []),
        "unresolved_items": classification.get("unresolved_items", []),
        "technical_checkpoints": ["excel_confirmation", "field_formula_classification"],
    }


def _step_2(run_dir: Path, state: dict[str, Any]) -> dict[str, Any]:
    sql_payload = _checkpoint_payload(run_dir, "02_sql_review.json")
    return {
        "user_step": 2,
        "title": USER_STEP_TITLES[2],
        "sql": sql_payload.get("sql") or state.get("sql_candidate", ""),
        "validation": sql_payload.get("validation") or state.get("sql_validation") or {},
        "db_target": sql_payload.get("db_target") or {},
        "logic_not_in_sql": sql_payload.get("logic_not_in_sql", []),
    }


def _step_3(run_dir: Path, state: dict[str, Any]) -> dict[str, Any]:
    raw = state.get("raw_data_preview") if isinstance(state.get("raw_data_preview"), dict) else {}
    enriched = state.get("enriched_data_preview") if isinstance(state.get("enriched_data_preview"), dict) else {}
    sqlite_manifest = state.get("sqlite_manifest") if isinstance(state.get("sqlite_manifest"), dict) else {}
    return {
        "user_step": 3,
        "title": USER_STEP_TITLES[3],
        "data_source": "current-run",
        "uses_mock_data": False,
        "raw_preview": _limit_rows(raw),
        "enriched_preview": _limit_rows(enriched),
        "sqlite_summary": {
            "manifest_path": state.get("sqlite_manifest_path"),
            "lookup_tables": sqlite_manifest.get("lookup_tables", []),
            "lookup_row_counts": sqlite_manifest.get("lookup_row_counts", {}),
            "ignored_lookup_rows": sqlite_manifest.get("ignored_lookup_rows", {}),
        },
        "html_preview": state.get("visual_design_checkpoint") or {},
        "excel_workbook_preview": state.get("excel_workbook_preview") or {},
    }


def _step_4(run_dir: Path, state: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_step": 4,
        "title": USER_STEP_TITLES[4],
        "delivery_status": state.get("delivery_status", "not_ready"),
        "validator_results": state.get("validator_results", []),
        "sqlite_retention": state.get("sqlite_retention"),
        "final_html": state.get("final_html_path", ""),
        "final_xlsx": state.get("final_xlsx_path", ""),
    }


def build_user_step_payload(run_dir: str | Path, step: int) -> dict[str, Any]:
    run_path = Path(run_dir)
    state = load_run_state(run_path)
    if step == 1:
        return _step_1(run_path, state)
    if step == 2:
        return _step_2(run_path, state)
    if step == 3:
        return _step_3(run_path, state)
    if step == 4:
        return _step_4(run_path, state)
    raise ValueError(f"Unknown user step: {step}")
```

- [ ] **Step 4: Add CLI command for user-step payload**

Modify `skill_scripts/cli_report_harness.py` command table with `write-user-step-preview`.

Implementation sketch:

```python
from skill_scripts.user_step_payload import build_user_step_payload


def _write_user_step_preview(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Write a 4-step Visual Companion payload.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--step", required=True, type=int, choices=[1, 2, 3, 4])
    args = parser.parse_args(argv)
    try:
        payload = build_user_step_payload(args.run_dir, args.step)
        _write_run_json(Path(args.run_dir), f"checkpoints/user_step_{args.step}.json", payload)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _json_error("user_step_preview_error", str(exc))
    _write_stdout_json(payload)
    return 0
```

- [ ] **Step 5: Run tests**

Run:

```powershell
. .\.tools\activate.ps1
python -m pytest tests/skill_scripts/test_user_step_payload.py tests/skill_scripts/test_cli_report_harness.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
. .\.tools\activate.ps1
git add skill_scripts/user_step_payload.py skill_scripts/cli_report_harness.py tests/skill_scripts/test_user_step_payload.py tests/skill_scripts/test_cli_report_harness.py
git commit -m "feat: aggregate wferp user step payloads"
```

---

### Task 4: Add Prompt Repair Loop

**Files:**
- Modify: `skill_scripts/report_harness_state.py`
- Modify: `skill_scripts/report_harness.py`
- Modify: `skill_scripts/checkpoint_companion.py`
- Modify: `tests/skill_scripts/test_report_harness.py`
- Modify: `tests/skill_scripts/test_checkpoint_companion.py`

- [ ] **Step 1: Write failing tests for blocking prompt repair**

Add to `tests/skill_scripts/test_report_harness.py`:

```python
def test_prompt_repair_blocks_forward_progress_until_cleared(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="產出報表")
    harness.write_sql_review("SELECT * FROM ACPTA", {"status": "pass"})
    checkpoint = harness.state()["checkpoints"][-1]
    payload_hash = json.loads((harness.run_dir / checkpoint["file"]).read_text(encoding="utf-8"))["payload_hash"]
    harness.confirm(
        "sql_review",
        "調整需求",
        selected_options={
            "changeScope": "sql_conditions",
            "targetUserStep": 2,
            "requiresRerender": True,
            "prompt": "請只查本月資料",
        },
    )

    state = harness.state()
    assert state["blocking_repair_request"]["changeScope"] == "sql_conditions"
    assert "execute_select" not in state["allowed_next_actions"]
```

Add to `tests/skill_scripts/test_checkpoint_companion.py`:

```python
def test_companion_prompt_repair_posts_changes_requested_with_scope(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="查詢費用")
    checkpoint = harness.write_sql_review("SELECT department, amount FROM expenses", {"status": "pass"})

    with CheckpointCompanionServer.serve(tmp_path / "run-001") as server:
        result = post_json(
            f"{server.base_url}/api/runs/run-001/checkpoints/sql_review/confirm",
            {
                "action": "調整需求",
                "checkpointId": "sql_review",
                "checkpoint_id": "sql_review",
                "run_id": "run-001",
                "payload_hash": checkpoint["payload_hash"],
                "confirmation_id": "repair-001",
                "comment": "請改成依客戶分組",
                "selectedOptions": {
                    "changeScope": "sql_conditions",
                    "targetUserStep": 2,
                    "requiresRerender": True,
                },
            },
        )

    assert result["status"] == "confirmed"
    state = harness.state()
    assert state["blocking_repair_request"]["comment"] == "請改成依客戶分組"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
. .\.tools\activate.ps1
python -m pytest tests/skill_scripts/test_report_harness.py::test_prompt_repair_blocks_forward_progress_until_cleared tests/skill_scripts/test_checkpoint_companion.py::test_companion_prompt_repair_posts_changes_requested_with_scope -v
```

Expected: FAIL because repair requests are not persisted.

- [ ] **Step 3: Add repair request persistence**

Add to `skill_scripts/report_harness.py`:

```python
    def record_prompt_repair(
        self,
        *,
        checkpoint: str,
        action: str,
        comment: str,
        selected_options: dict[str, Any],
    ) -> dict[str, Any]:
        change_scope = selected_options.get("changeScope")
        target_step = selected_options.get("targetUserStep")
        repair = {
            "checkpoint": checkpoint,
            "action": action,
            "comment": comment,
            "changeScope": change_scope,
            "targetUserStep": target_step,
            "requiresRerender": bool(selected_options.get("requiresRerender")),
        }
        state = self.state()
        state["blocking_repair_request"] = repair
        state["allowed_next_actions"] = ["repair_current_step"]
        return save_run_state(self.run_dir, state)
```

Modify `confirm()` after saving `user_confirmations`:

```python
        if action in {"要求修正", "調整需求", "重新查詢", "修改格式", "調整設計", "調整視覺設計", "修正報告", "回到初稿"}:
            state["blocking_repair_request"] = {
                "checkpoint": checkpoint,
                "action": action,
                "comment": "",
                "selectedOptions": selected_options or {},
            }
            state["allowed_next_actions"] = ["repair_current_step"]
```

In companion POST handler, after `harness.confirm(...)`, call `harness.record_prompt_repair(...)` when `selectedOptions.requiresRerender` is true or action is a change action.

- [ ] **Step 4: Add companion prompt UI controls**

Modify `skill_scripts/checkpoint_companion.py` sticky actions panel:

```html
<label class="comment-label" for="confirmation-comment">請輸入確認意見或修改需求</label>
<select id="change-scope">
  <option value="">選擇修改範圍</option>
  <option value="source_logic">資料邏輯</option>
  <option value="formula_logic">公式邏輯</option>
  <option value="sql_conditions">SQL 條件</option>
  <option value="data_result">資料結果</option>
  <option value="html_design">HTML 設計</option>
  <option value="excel_design">Excel 設計</option>
  <option value="visual_style">視覺樣式</option>
  <option value="delivery">交付內容</option>
</select>
```

Modify `selectedOptions()`:

```javascript
const scope = document.getElementById('change-scope')?.value || '';
if (scope) {
  options.changeScope = scope;
  options.requiresRerender = true;
  options.targetUserStep = Number(document.querySelector('[data-user-step]')?.dataset.userStep || 0);
}
```

- [ ] **Step 5: Run tests**

Run:

```powershell
. .\.tools\activate.ps1
python -m pytest tests/skill_scripts/test_report_harness.py tests/skill_scripts/test_checkpoint_companion.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
. .\.tools\activate.ps1
git add skill_scripts/report_harness.py skill_scripts/checkpoint_companion.py tests/skill_scripts/test_report_harness.py tests/skill_scripts/test_checkpoint_companion.py
git commit -m "feat: route visual companion prompt repairs"
```

---

### Task 5: Redesign Visual Companion As 4 User Steps

**Files:**
- Modify: `skill_scripts/checkpoint_companion.py`
- Modify: `tests/skill_scripts/test_checkpoint_companion.py`
- Modify: `tests/skill_scripts/test_user_step_payload.py`

- [ ] **Step 1: Write failing tests for 4-step navigation and dynamic real-data UI**

Add to `tests/skill_scripts/test_checkpoint_companion.py`:

```python
def test_companion_shows_four_user_steps_not_many_technical_steps(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="產出報表")
    harness.write_field_formula_classification(
        {
            "output_targets": ["html", "excel"],
            "source_to_output_matrix": [
                {
                    "output_item": "HTML KPI",
                    "source": "DB raw rows",
                    "transformation_logic": "彙總金額",
                    "processing_layer": "sqlite-enrichment",
                    "verification": "aggregate check",
                }
            ],
        }
    )

    with CheckpointCompanionServer.serve(tmp_path / "run-001") as server:
        with urlopen(f"{server.base_url}/runs/run-001/checkpoints/current", timeout=5) as response:
            html = response.read().decode("utf-8")

    assert "來源與產出邏輯確認" in html
    assert "SQL 查詢確認" in html
    assert "資料結果與報表設計確認" in html
    assert "成品與交付確認" in html
    assert "HTML KPI" in html
    assert "Technical evidence" in html


def test_step_3_renders_50_real_rows_and_excel_preview(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="產出報表")
    rows = [{"row_no": index, "amount": index * 100} for index in range(60)]
    harness.update_state(
        current_user_step=3,
        raw_data_preview={"row_count": 60, "columns": ["row_no", "amount"], "sample_rows": rows},
        enriched_data_preview={"row_count": 60, "columns": ["row_no", "amount"], "sample_rows": rows},
        excel_workbook_preview={
            "sheets": [
                {
                    "name": "摘要",
                    "columns": ["row_no", "amount"],
                    "sample_rows": rows,
                    "formula_strategy": "hybrid",
                }
            ]
        },
    )
    harness.write_enriched_data_preview({"row_count": 60, "columns": ["row_no", "amount"], "sample_rows": rows})

    with CheckpointCompanionServer.serve(tmp_path / "run-001") as server:
        with urlopen(f"{server.base_url}/runs/run-001/checkpoints/current", timeout=5) as response:
            html = response.read().decode("utf-8")

    assert "資料結果與報表設計確認" in html
    assert "Excel Workbook Preview" in html
    assert "摘要" in html
    assert "row_no" in html
    assert "只顯示前 50 筆" in html
    assert "5900" not in html
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
. .\.tools\activate.ps1
python -m pytest tests/skill_scripts/test_checkpoint_companion.py::test_companion_shows_four_user_steps_not_many_technical_steps tests/skill_scripts/test_checkpoint_companion.py::test_step_3_renders_50_real_rows_and_excel_preview -v
```

Expected: FAIL because current UI is checkpoint-first and table limit is 100.

- [ ] **Step 3: Refactor companion rendering around user-step payload**

In `skill_scripts/checkpoint_companion.py`, import:

```python
from skill_scripts.user_step_payload import build_user_step_payload
```

Add helper:

```python
def _current_user_step(state: Mapping[str, Any], checkpoint: str) -> int:
    explicit = state.get("current_user_step")
    if isinstance(explicit, int) and explicit in {1, 2, 3, 4}:
        return explicit
    if checkpoint in {"excel_confirmation", "field_formula_classification"}:
        return 1
    if checkpoint == "sql_review":
        return 2
    if checkpoint in {"data_preview", "raw_data_preview", "enriched_data_preview", "report_selection", "design_brief", "visual_design", "report_draft"}:
        return 3
    return 4
```

Add user-step nav:

```python
def _render_user_step_nav(current_step: int) -> str:
    labels = {
        1: "來源與產出邏輯確認",
        2: "SQL 查詢確認",
        3: "資料結果與報表設計確認",
        4: "成品與交付確認",
    }
    return (
        '<nav class="user-step-nav">'
        + "".join(
            f'<div class="user-step {"current" if step == current_step else ""}" data-user-step="{step}">'
            f'<span>{step}</span><strong>{escape(label)}</strong></div>'
            for step, label in labels.items()
        )
        + "</nav>"
    )
```

Set `MAX_TABLE_ROWS = 50`.

- [ ] **Step 4: Render Step 1 source-to-output matrix**

Add:

```python
def _render_source_to_output_logic(payload: Mapping[str, Any]) -> str:
    matrix = payload.get("source_to_output_matrix")
    formulas = payload.get("formula_semantics")
    inventory = payload.get("source_inventory")
    return (
        "<section class=\"panel\">"
        "<h3>你要的產出會如何被產生</h3>"
        + _render_table(matrix if isinstance(matrix, list) else [])
        + "<h3>來源盤點</h3>"
        + _render_table(inventory if isinstance(inventory, list) else [])
        + "<h3>公式與數字一致策略</h3>"
        + _render_table(formulas if isinstance(formulas, list) else [])
        + "</section>"
    )
```

- [ ] **Step 5: Render Step 3 real data + Excel preview**

Add:

```python
def _render_excel_workbook_preview(payload: Mapping[str, Any]) -> str:
    sheets = payload.get("sheets")
    if not isinstance(sheets, list) or not sheets:
        return "<p class=\"muted\">尚未產生 Excel workbook preview。</p>"
    html = ["<div class=\"workbook-preview\"><h3>Excel Workbook Preview</h3>"]
    for sheet in sheets:
        if not isinstance(sheet, Mapping):
            continue
        html.append(f"<article class=\"sheet-preview\"><h4>{escape(str(sheet.get('name', 'Sheet')))}</h4>")
        html.append(f"<p>公式/值策略：{escape(str(sheet.get('formula_strategy', 'hybrid')))}</p>")
        rows = sheet.get("sample_rows")
        columns = sheet.get("columns")
        html.append(_render_table(rows if isinstance(rows, list) else [], columns if isinstance(columns, list) else None))
        html.append("</article>")
    html.append("</div>")
    return "".join(html)
```

Add:

```python
def _render_data_result_and_design(payload: Mapping[str, Any]) -> str:
    raw = payload.get("raw_preview") if isinstance(payload.get("raw_preview"), Mapping) else {}
    enriched = payload.get("enriched_preview") if isinstance(payload.get("enriched_preview"), Mapping) else {}
    excel_preview = payload.get("excel_workbook_preview") if isinstance(payload.get("excel_workbook_preview"), Mapping) else {}
    return (
        "<section class=\"panel\"><h3>DB 原始資料前 50 筆</h3>"
        + _render_table(raw.get("sample_rows", []), raw.get("columns") if isinstance(raw.get("columns"), list) else None)
        + "<h3>SQLite 補欄資料前 50 筆</h3>"
        + _render_table(enriched.get("sample_rows", []), enriched.get("columns") if isinstance(enriched.get("columns"), list) else None)
        + _render_excel_workbook_preview(excel_preview)
        + "</section>"
    )
```

- [ ] **Step 6: Wire user-step rendering into page**

Inside `_render_checkpoint_page()`, build:

```python
    current_user_step = _current_user_step(state, checkpoint)
    user_step_payload = build_user_step_payload(Path("..."), current_user_step)
```

Because `_render_checkpoint_page()` does not currently receive `run_path`, change its signature to include `run_path: Path`, and pass it from `do_GET`.

Then add:

```python
    if current_user_step == 1:
        user_step_body = _render_source_to_output_logic(user_step_payload)
    elif current_user_step == 3:
        user_step_body = _render_data_result_and_design(user_step_payload)
    else:
        user_step_body = _render_payload_sections(checkpoint, payload_dict)
```

Use `user_step_body` in the main content instead of only `_render_payload_sections(...)`.

- [ ] **Step 7: Ensure technical evidence remains expandable**

Add:

```python
def _render_technical_evidence(checkpoint: str, payload: Mapping[str, Any]) -> str:
    return (
        "<details class=\"technical-evidence\"><summary>Technical evidence</summary>"
        + _render_payload_sections(checkpoint, dict(payload))
        + "</details>"
    )
```

Render this after the user-step body.

- [ ] **Step 8: Run focused companion tests**

Run:

```powershell
. .\.tools\activate.ps1
python -m pytest tests/skill_scripts/test_checkpoint_companion.py tests/skill_scripts/test_user_step_payload.py -v
```

Expected: PASS.

- [ ] **Step 9: Commit**

```powershell
. .\.tools\activate.ps1
git add skill_scripts/checkpoint_companion.py tests/skill_scripts/test_checkpoint_companion.py tests/skill_scripts/test_user_step_payload.py
git commit -m "feat: render four-step visual companion"
```

---

### Task 6: Add True Excel Workbook Export

**Files:**
- Create: `skill_scripts/excel_workbook_exporter.py`
- Create: `tests/skill_scripts/test_excel_workbook_exporter.py`
- Modify: `skill_scripts/cli_report_harness.py`
- Modify: `skill_scripts/report_harness.py`
- Modify: `tests/skill_scripts/test_cli_report_harness.py`

- [ ] **Step 1: Use the spreadsheets skill before implementation**

Before editing workbook generation code, read and follow:

```text
C:/Users/ivychi/.codex/plugins/cache/openai-primary-runtime/spreadsheets/26.619.11828/skills/spreadsheets/SKILL.md
```

The workbook must be generated as a real `.xlsx` and verified. Do not deliver HTML-only Excel previews.

- [ ] **Step 2: Write failing tests for workbook export**

Create `tests/skill_scripts/test_excel_workbook_exporter.py`:

```python
from __future__ import annotations

import zipfile
from pathlib import Path

from skill_scripts.excel_workbook_exporter import export_workbook


def test_export_workbook_writes_real_xlsx_and_evidence(tmp_path: Path):
    payload = {
        "sheets": [
            {
                "name": "摘要",
                "columns": ["客戶", "金額"],
                "rows": [{"客戶": "A 客戶", "金額": 1000}],
                "formula_strategy": "hybrid",
            },
            {
                "name": "公式說明",
                "columns": ["項目", "邏輯"],
                "rows": [{"項目": "金額", "邏輯": "由 SQLite enriched data 彙總"}],
                "formula_strategy": "value-only",
            },
        ]
    }

    result = export_workbook(payload, tmp_path / "report.xlsx", evidence_path=tmp_path / "excel-evidence.json")

    assert result["status"] == "exported"
    assert result["workbook_path"].endswith("report.xlsx")
    assert result["sheets"][0]["name"] == "摘要"
    assert result["sheets"][0]["row_count"] == 1
    assert (tmp_path / "report.xlsx").is_file()
    assert (tmp_path / "excel-evidence.json").is_file()
    with zipfile.ZipFile(tmp_path / "report.xlsx") as archive:
        assert "xl/workbook.xml" in archive.namelist()
```

- [ ] **Step 3: Run test to verify failure**

Run:

```powershell
. .\.tools\activate.ps1
python -m pytest tests/skill_scripts/test_excel_workbook_exporter.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 4: Implement minimal workbook exporter**

Create `skill_scripts/excel_workbook_exporter.py`.

Implementation must use spreadsheet tooling selected by the implementation session. A minimal openpyxl implementation is acceptable only if the spreadsheets skill confirms it is available.

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill


def export_workbook(payload: dict[str, Any], workbook_path: str | Path, *, evidence_path: str | Path) -> dict[str, Any]:
    workbook = Workbook()
    default = workbook.active
    workbook.remove(default)

    sheet_evidence: list[dict[str, Any]] = []
    for sheet_payload in payload.get("sheets", []):
        name = str(sheet_payload.get("name") or "Sheet")[:31]
        ws = workbook.create_sheet(name)
        columns = [str(column) for column in sheet_payload.get("columns", [])]
        rows = sheet_payload.get("rows", [])
        ws.append(columns)
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.fill = PatternFill("solid", fgColor="EAF1F8")
        for row in rows:
            ws.append([row.get(column, "") if isinstance(row, dict) else "" for column in columns])
        sheet_evidence.append(
            {
                "name": name,
                "column_count": len(columns),
                "row_count": len(rows) if isinstance(rows, list) else 0,
                "formula_strategy": sheet_payload.get("formula_strategy", "hybrid"),
            }
        )

    output_path = Path(workbook_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_path)

    evidence = {
        "status": "exported",
        "workbook_path": str(output_path),
        "sheets": sheet_evidence,
    }
    evidence_file = Path(evidence_path)
    evidence_file.parent.mkdir(parents=True, exist_ok=True)
    evidence_file.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    return evidence
```

- [ ] **Step 5: Add CLI command**

Add `export-excel-workbook` to `skill_scripts/cli_report_harness.py`:

```python
def _export_excel_workbook(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Export a true .xlsx workbook for WFERP report delivery.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--payload", required=True)
    parser.add_argument("--output", default="report/delivery/report.xlsx")
    args = parser.parse_args(argv)
    try:
        from skill_scripts.excel_workbook_exporter import export_workbook
        run_dir = Path(args.run_dir)
        payload = _payload_or_checkpoint_payload(_load_json_arg(args.payload))
        result = export_workbook(
            payload,
            run_dir / args.output,
            evidence_path=run_dir / "review" / "excel-workbook-evidence.json",
        )
        harness = ReportHarness(run_dir)
        harness.update_state(final_xlsx_path=result["workbook_path"], excel_workbook_evidence=result)
    except Exception as exc:
        return _json_error("excel_export_error", str(exc))
    _write_stdout_json(result)
    return 0
```

- [ ] **Step 6: Run tests**

Run:

```powershell
. .\.tools\activate.ps1
python -m pytest tests/skill_scripts/test_excel_workbook_exporter.py tests/skill_scripts/test_cli_report_harness.py -v
```

Expected: PASS. If `openpyxl` is unavailable, install through the project-approved/bundled spreadsheet runtime path before rerunning.

- [ ] **Step 7: Commit**

```powershell
. .\.tools\activate.ps1
git add skill_scripts/excel_workbook_exporter.py skill_scripts/cli_report_harness.py skill_scripts/report_harness.py tests/skill_scripts/test_excel_workbook_exporter.py tests/skill_scripts/test_cli_report_harness.py
git commit -m "feat: export true wferp excel workbook"
```

---

### Task 7: Tighten Validator Fresh Reviewer Contract

**Files:**
- Modify: `skill_scripts/validator_contracts.py`
- Modify: `tests/skill_scripts/test_validator_contracts.py`
- Modify: `tests/skill_scripts/test_report_harness.py`

- [ ] **Step 1: Write failing validator contract tests**

Add to `tests/skill_scripts/test_validator_contracts.py`:

```python
def test_validator_contract_requires_fresh_reviewer_metadata():
    result = {
        "role": "sql_safety_reviewer",
        "status": "pass",
        "evidence": [{"type": "file", "path": "sql/query.sql"}],
        "findings": [],
        "requiredFixes": [],
        "residualRisks": [],
    }

    with pytest.raises(ValidatorContractError, match="reviewer_identity"):
        validate_validator_result(result)


def test_validator_contract_accepts_fresh_reviewer_metadata():
    result = {
        "role": "sql_safety_reviewer",
        "status": "pass",
        "reviewer_identity": {"kind": "subagent", "id": "agent-001"},
        "checked_scope": ["sql/query.sql", "checkpoints/02_sql_review.json"],
        "input_artifact_paths": ["sql/query.sql", "checkpoints/02_sql_review.json"],
        "reviewed_at": "2026-06-20T00:00:00Z",
        "evidence": [{"type": "file", "path": "sql/query.sql"}],
        "findings": [],
        "requiredFixes": [],
        "residualRisks": [],
    }

    assert validate_validator_result(result)["status"] == "pass"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
. .\.tools\activate.ps1
python -m pytest tests/skill_scripts/test_validator_contracts.py::test_validator_contract_requires_fresh_reviewer_metadata tests/skill_scripts/test_validator_contracts.py::test_validator_contract_accepts_fresh_reviewer_metadata -v
```

Expected: FAIL because validator metadata is not required.

- [ ] **Step 3: Update validator contract**

Modify `skill_scripts/validator_contracts.py` in validator validation function:

```python
    reviewer_identity = result.get("reviewer_identity")
    if not isinstance(reviewer_identity, dict) or not reviewer_identity.get("kind") or not reviewer_identity.get("id"):
        raise ValidatorContractError(f"{role}: reviewer_identity is required")
    if not isinstance(result.get("checked_scope"), list) or not result["checked_scope"]:
        raise ValidatorContractError(f"{role}: checked_scope is required")
    if not isinstance(result.get("input_artifact_paths"), list) or not result["input_artifact_paths"]:
        raise ValidatorContractError(f"{role}: input_artifact_paths is required")
    if not isinstance(result.get("reviewed_at"), str) or not result["reviewed_at"]:
        raise ValidatorContractError(f"{role}: reviewed_at is required")
```

Update test helper `_validator_result()` functions in affected tests to include:

```python
"reviewer_identity": {"kind": "subagent", "id": f"{role}-agent"},
"checked_scope": ["run-dir"],
"input_artifact_paths": ["checkpoints/current.json"],
"reviewed_at": "2026-06-20T00:00:00Z",
```

- [ ] **Step 4: Run validator tests**

Run:

```powershell
. .\.tools\activate.ps1
python -m pytest tests/skill_scripts/test_validator_contracts.py tests/skill_scripts/test_report_harness.py tests/skill_scripts/test_report_package.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
. .\.tools\activate.ps1
git add skill_scripts/validator_contracts.py tests/skill_scripts/test_validator_contracts.py tests/skill_scripts/test_report_harness.py tests/skill_scripts/test_report_package.py
git commit -m "feat: require fresh reviewer validator evidence"
```

---

### Task 8: Sync Skill Documentation And Repo Instructions

**Files:**
- Modify: `skills/wferp-report/SKILL.md`
- Modify: `skills/wferp-report/README.md`
- Modify: `skills/wferp-report/references/harness.md`
- Modify: `skills/wferp-report/references/checkpoint-payload-schema.md`
- Modify: `skills/wferp-report/references/excel-intake.md`
- Modify: `skills/wferp-report/references/sqlite-enrichment.md`
- Modify: `skills/wferp-report/references/validators.md`
- Modify: `skills/wferp-report/references/single-html-export.md`
- Create: `skills/wferp-report/references/visual-companion-ui.md`
- Modify: `AGENTS.md`
- Modify: `tests/scripts/test_validate_local_wferp_report_skill.py`

- [ ] **Step 1: Write failing documentation validation test**

Add to `tests/scripts/test_validate_local_wferp_report_skill.py`:

```python
def test_wferp_report_skill_documents_4_step_stateful_visual_companion(repo_root: Path):
    skill = (repo_root / "skills" / "wferp-report" / "SKILL.md").read_text(encoding="utf-8")
    harness = (repo_root / "skills" / "wferp-report" / "references" / "harness.md").read_text(encoding="utf-8")
    ui = (repo_root / "skills" / "wferp-report" / "references" / "visual-companion-ui.md").read_text(encoding="utf-8")

    for text in (skill, harness, ui):
        assert "13" in text
        assert "4-step" in text or "4 個" in text
        assert "state.json" in text
        assert "Build Web Apps" in text
        assert "Build Web Data Visualization" in text
        assert "spreadsheets" in text
        assert "fresh reviewer" in text or "subagent" in text
        assert "50" in text
        assert "prompt" in text and "repair" in text
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
. .\.tools\activate.ps1
python -m pytest tests/scripts/test_validate_local_wferp_report_skill.py::test_wferp_report_skill_documents_4_step_stateful_visual_companion -v
```

Expected: FAIL because `visual-companion-ui.md` does not exist and docs are not synchronized.

- [ ] **Step 3: Update `SKILL.md`**

Patch `skills/wferp-report/SKILL.md` with these exact requirements:

```markdown
## 13-Phase Engine, 4-Step User UI

The internal harness keeps the 13 technical phases. The Visual Companion exposes only 4 user-facing steps:

1. Source-to-Output Logic
2. SQL Query
3. Data Result and Report Design
4. Final Delivery

The user-facing 4 steps do not remove technical phases, validators, SQLite enrichment, lookup handling, SQL safety, repair, or delivery evidence.
```

Add:

```markdown
## Required Capability Ownership

- Use Build Web Apps for Visual Companion UI, prompt repair controls, confirmation UX, responsive layout, and final HTML app shell when available.
- Use Build Web Data Visualization for real-data KPI, chart, table, pivot-like preview, and report visualization when available.
- Use spreadsheets for true `.xlsx` generation and workbook verification when Excel output is requested.
- If a required capability is unavailable, stop and ask before falling back.
```

Add:

```markdown
## State-Gated Progression

`state.json` is the workflow source of truth. The harness must not advance from chat memory, stale files, stale confirmations, or file presence alone.
```

- [ ] **Step 4: Create `visual-companion-ui.md`**

Create `skills/wferp-report/references/visual-companion-ui.md` with:

```markdown
# Visual Companion UI

The Visual Companion is a 4-step user-facing report workbench over the 13-phase technical harness.

## User Steps

1. Source-to-Output Logic
2. SQL Query
3. Data Result and Report Design
4. Final Delivery

## Dynamic UI Requirement

When available, use Build Web Apps and Build Web Data Visualization to design and implement the Visual Companion and final HTML report UI. Do not replace this with a static checkpoint page, stale screenshot, generic JSON viewer, fake chart, or fake preview.

## Real Data Requirement

Step 3 renders current-run raw rows, SQLite enriched rows, KPI/chart/table previews, and Excel workbook preview. Default table preview is 50 rows.

## Prompt Repair

Each step must include prompt-based change request controls. A repair prompt writes `blocking_repair_request` to `state.json` and blocks forward progress until the smallest affected slice is repaired and validators rerun.

## Excel Preview

The companion may show an Excel-like workbook preview, but final `.xlsx` generation and verification use the spreadsheets skill.
```

- [ ] **Step 5: Update references**

Apply focused edits:

- `references/harness.md`: replace "主要 checkpoint" section with 4 user steps and 13 phase mapping.
- `references/checkpoint-payload-schema.md`: add `run_id`, `checkpoint_id`, `payload_hash`, `confirmation_id`, `selectedOptions.changeScope`.
- `references/excel-intake.md`: add source-to-output matrix and formula consistency rules.
- `references/sqlite-enrichment.md`: add Step 1/3 presentation rules and 50-row preview.
- `references/validators.md`: add fresh subagent reviewer metadata requirement.
- `references/single-html-export.md`: add plugin-assisted final HTML UI requirement.
- `README.md`: summarize 4-step Visual Companion and true Excel output.
- `AGENTS.md`: add state-machine gate and plugin ownership rules.

- [ ] **Step 6: Sync installed skill**

After repo docs pass tests, copy repo skill to installed skill:

```powershell
Copy-Item -LiteralPath 'C:\Users\ivychi\util\wferp\skills\wferp-report\SKILL.md' -Destination 'C:\Users\ivychi\.codex\skills\wferp-report\SKILL.md' -Force
Copy-Item -LiteralPath 'C:\Users\ivychi\util\wferp\skills\wferp-report\README.md' -Destination 'C:\Users\ivychi\.codex\skills\wferp-report\README.md' -Force
```

This may require filesystem approval because the destination is outside the repo.

- [ ] **Step 7: Run docs tests**

Run:

```powershell
. .\.tools\activate.ps1
python -m pytest tests/scripts/test_validate_local_wferp_report_skill.py tests/scripts/test_wferp_report_windows_encoding.py -v
```

Expected: PASS and no mojibake/replacement-question-mark failures.

- [ ] **Step 8: Commit**

```powershell
. .\.tools\activate.ps1
git add AGENTS.md skills/wferp-report/SKILL.md skills/wferp-report/README.md skills/wferp-report/references/harness.md skills/wferp-report/references/checkpoint-payload-schema.md skills/wferp-report/references/excel-intake.md skills/wferp-report/references/sqlite-enrichment.md skills/wferp-report/references/validators.md skills/wferp-report/references/single-html-export.md skills/wferp-report/references/visual-companion-ui.md tests/scripts/test_validate_local_wferp_report_skill.py
git commit -m "docs: define stateful four-step wferp companion"
```

---

### Task 9: Final Integration And Regression Verification

**Files:**
- Modify only files needed to fix regressions found in this task.

- [ ] **Step 1: Run focused state/UI/Excel regression**

Run:

```powershell
. .\.tools\activate.ps1
python -m pytest tests/skill_scripts/test_harness_state_machine.py tests/skill_scripts/test_report_harness_state.py tests/skill_scripts/test_report_harness.py tests/skill_scripts/test_user_step_payload.py tests/skill_scripts/test_checkpoint_companion.py tests/skill_scripts/test_excel_workbook_exporter.py tests/skill_scripts/test_validator_contracts.py tests/scripts/test_validate_local_wferp_report_skill.py tests/scripts/test_wferp_report_windows_encoding.py -v
```

Expected: PASS.

- [ ] **Step 2: Run broader harness suite**

Run:

```powershell
. .\.tools\activate.ps1
python -m pytest tests/skill_scripts/test_cli_report_harness.py tests/skill_scripts/test_sqlite_enrichment.py tests/skill_scripts/test_workbook_lookup_importer.py tests/skill_scripts/test_single_html_exporter.py tests/skill_scripts/test_report_package.py -v
```

Expected: PASS.

- [ ] **Step 3: Manual companion smoke test without production DB**

Create a test run and write non-DB sample payloads:

```powershell
. .\.tools\activate.ps1
python -m skill_scripts.cli_report_harness create-run --run-root .test-runs --run-id smoke-4-step --prompt "測試 4-step Visual Companion"
python -m skill_scripts.cli_report_harness write-user-step-preview --run-dir .test-runs\smoke-4-step --step 1
python -m skill_scripts.cli_report_harness serve-checkpoint --run-dir .test-runs\smoke-4-step --port 8765
```

Expected:

- URL serves current run only.
- Page shows 4 user steps.
- Step 1 shows source-to-output areas.
- Prompt repair input exists.
- Confirmation POST writes identity-backed confirmation.

Do not query production DB in this smoke test.

- [ ] **Step 4: Check git status**

Run:

```powershell
. .\.tools\activate.ps1
git status --short
```

Expected: only intentional modified files or generated `.test-runs` artifacts. Do not commit `.test-runs`.

- [ ] **Step 5: Commit regression fixes if any**

If Step 1 or Step 2 required fixes:

```powershell
. .\.tools\activate.ps1
git add <fixed-files>
git commit -m "test: verify four-step wferp harness integration"
```

If no fixes were needed, do not create an empty commit.

## Self-Review Checklist

- Spec coverage:
  - 13-phase internal engine: Tasks 1, 2, 8, 9.
  - 4-step Visual Companion: Tasks 3, 5, 8, 9.
  - Dynamic web/data-viz plugin requirement: Tasks 5, 8.
  - Subagent/fresh reviewer validators: Task 7 and Task 8.
  - State-machine source of truth: Tasks 1, 2, 4, 9.
  - Prompt repair loop: Task 4 and Task 5.
  - SQLite/lookup preserved: Task 3, Task 5, Task 8.
  - 50-row real data preview: Task 3 and Task 5.
  - True `.xlsx` output via spreadsheets: Task 6 and Task 8.
  - Documentation sync: Task 8.

- Deferred-work scan:
  - This plan intentionally contains no deferred implementation notes.
  - Every code-facing task includes test code, commands, expected failure, implementation sketch, verification, and commit command.

- Type consistency:
  - State fields use the spec names: `current_user_step`, `current_internal_phase`, `gate_status`, `allowed_next_actions`, `confirmation_identity`, `blocking_repair_request`.
  - Confirmation identity uses `run_id`, `checkpoint_id`, `payload_hash`, `confirmation_id`.
  - Prompt repair uses `selectedOptions.changeScope`, `selectedOptions.targetUserStep`, and `selectedOptions.requiresRerender`.

## Execution Options

Plan implementation must use one of these:

1. **Subagent-Driven (recommended)**  
   Dispatch a fresh subagent per task, review between tasks, and keep validator/UI/Excel tasks isolated.

2. **Inline Execution**  
   Execute tasks in this session using `superpowers:executing-plans`, with checkpoints after each task.

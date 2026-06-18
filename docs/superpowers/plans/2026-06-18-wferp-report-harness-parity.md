# WFERP Report Harness Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Every task begins with failing tests, implements the smallest production-quality vertical slice, then commits only the files in that task.

**Goal:** Build `wferp-report` into a product-grade local Codex skill that executes a beautiful-article-style harness: prompt/Excel intake, WFERP schema-aware SELECT SQL generation, user checkpoints in a local React companion, safe DB execution, data preview, report format selection, scaffolded React report generation, validator evidence, and minimal-slice repair.

**Architecture:** Keep the local skill outside the repository at `/home/timmypai/.codex/skills/wferp-report/`; keep executable runtime inside this repository under `skill_scripts/`, `report_renderer/`, `scripts/`, `report_designs/`, and tests. Use fixed React checkpoint components driven by JSON payloads, and generate one per-run final report workspace from a strict scaffold template.

**Tech Stack:** Python 3, pytest, local file-backed harness state, `http.server`-based checkpoint companion, React 19, Vite, Vitest, Testing Library, SQLite for first local E2E, Docker PostgreSQL as formal MSSQL substitute E2E, WFERP `_Source` schema metadata.

---

## Approved Spec

Implement against:

- `docs/superpowers/specs/2026-06-18-wferp-report-harness-parity-design.md`

The design has already been reviewed by the user. Do not reduce scope. Phases may be delivered sequentially, but each task must leave a production-grade vertical slice with tests and measurable acceptance criteria.

## Goal Prompt For Execution

Use this prompt to execute the plan in a fresh Codex session:

```text
使用 superpowers:subagent-driven-development 與 TDD 執行 /home/timmypai/.codex/worktrees/5f5b/wferp/docs/superpowers/plans/2026-06-18-wferp-report-harness-parity.md。

要求：
1. 每個 Task 派一個 fresh subagent 實作，主 agent 只做 task packet、review、整合與下一步決策。
2. 每個 Task 必須先寫 failing tests，確認失敗訊息符合 plan，再做最小產品級實作。
3. 每個 Task 完成後需提供 evidence packet：修改檔案、測試命令、失敗前證據、通過後證據、量化驗收、剩餘風險。
4. 不得使用 fake、mock、smoke 來替代 E2E。費用分析 E2E 必須先跑 SQLite-first，再跑 Docker PostgreSQL formal MSSQL substitute，建立真實 schema、seed 真實測試資料、執行真實 SQL、驗證 rows/columns/aggregates/percentages/exclusions。
5. 使用者可見文件與 skill 文案使用繁體中文。程式命名與 commit message 可使用英文。
6. 嚴格保護安全邊界：只允許唯讀 SELECT；未經 checkpoint confirmation 不得連 DB；瀏覽器端不得連 DB、不得執行 SQL、不得存 credentials。
7. 每個 Task 通過後做小 commit。不要 stage unrelated worktree changes。
8. 若 validator 或 E2E 失敗，依 repair policy 做最小垂直切片修復，不得重寫整個流程掩蓋單點失敗。
```

## File Structure

### Repository Runtime

- Create: `skill_scripts/checkpoint_companion.py`  
  Local HTTP companion server, checkpoint JSON loading, confirmation POST handling, audit append, stale-check protection.
- Modify: `skill_scripts/report_harness_state.py`  
  Add audit directory, confirmation files, checkpoint version/hash, phase directories matching spec.
- Modify: `skill_scripts/report_harness.py`  
  Use confirmation files, enforce hard gates, append repair logs, expose run-root defaults.
- Modify: `skill_scripts/cli_report_harness.py`  
  Add commands for starting companion, emitting current checkpoint, scaffolding report, validating final delivery.
- Create: `skill_scripts/report_scaffold.py`  
  Copy scaffold template into per-run workspace, write payload, validate one-section-one-file protocol.
- Modify: `skill_scripts/excel_intake.py`  
  Parse uploaded Excel requirements, distinguish DB fields from user formula fields, capture formula lineage.
- Modify: `skill_scripts/validator_contracts.py`  
  Add validator roles from spec, JSON evidence contract, pass/fail aggregation, residual-risk handling.
- Modify: `skill_scripts/report_catalog.py`  
  Read `report_designs/index.json`, load selected profile, validate required metadata.
- Modify: `scripts/validate_local_wferp_report_skill.py`  
  Validate full local skill parity structure, required references, scripts, catalog, scaffold template.

### React Checkpoint App

- Modify: `report_renderer/src/App.tsx`
- Modify: `report_renderer/src/components/CheckpointPage.tsx`
- Modify: `report_renderer/src/components/DataPreviewTable.tsx`
- Modify: `report_renderer/src/components/ReportOptionPanel.tsx`
- Create: `report_renderer/src/components/CheckpointShell.tsx`
- Create: `report_renderer/src/components/ManagementView.tsx`
- Create: `report_renderer/src/components/TechnicalView.tsx`
- Create: `report_renderer/src/components/FieldFormulaReview.tsx`
- Create: `report_renderer/src/components/SqlReviewPanel.tsx`
- Create: `report_renderer/src/components/AggregateCheckPanel.tsx`
- Create: `report_renderer/src/components/ValidatorEvidencePanel.tsx`
- Create: `report_renderer/src/components/ActionBar.tsx`
- Create: `report_renderer/src/components/ChartBlock.tsx`
- Create: `report_renderer/src/components/InsightBlock.tsx`
- Create: `report_renderer/src/components/RecommendationList.tsx`
- Create: `report_renderer/src/components/RawBlockNotice.tsx`
- Modify: `report_renderer/src/styles.css`
- Modify: `report_renderer/tests/renderer.spec.ts`

### Local Skill Outside Repo

- Modify: `/home/timmypai/.codex/skills/wferp-report/SKILL.md`
- Create: `/home/timmypai/.codex/skills/wferp-report/manifest.json`
- Create: `/home/timmypai/.codex/skills/wferp-report/README.md`
- Create missing references under `/home/timmypai/.codex/skills/wferp-report/references/`
- Create: `/home/timmypai/.codex/skills/wferp-report/report_designs/index.json`
- Create: `/home/timmypai/.codex/skills/wferp-report/assets/scaffold-template/`
- Create: `/home/timmypai/.codex/skills/wferp-report/examples/`
- Modify local skill scripts under `/home/timmypai/.codex/skills/wferp-report/scripts/`

### Tests

- Create: `tests/skill_scripts/test_checkpoint_companion.py`
- Modify: `tests/skill_scripts/test_report_harness_state.py`
- Modify: `tests/skill_scripts/test_report_harness.py`
- Create: `tests/skill_scripts/test_report_scaffold.py`
- Modify: `tests/skill_scripts/test_excel_intake.py`
- Modify: `tests/skill_scripts/test_validator_contracts.py`
- Modify: `tests/skill_scripts/test_report_catalog.py`
- Modify: `tests/scripts/test_validate_local_wferp_report_skill.py`
- Modify: `tests/skill_scripts/test_expense_analysis_sqlite_e2e.py`
- Modify: `tests/skill_scripts/test_expense_analysis_postgres_e2e.py`
- Modify: `report_renderer/tests/renderer.spec.ts`

---

## Task 1: Local Skill Parity Structure

**Files:**
- Modify: `/home/timmypai/.codex/skills/wferp-report/SKILL.md`
- Create: `/home/timmypai/.codex/skills/wferp-report/manifest.json`
- Create: `/home/timmypai/.codex/skills/wferp-report/README.md`
- Create: `/home/timmypai/.codex/skills/wferp-report/references/checkpoint-payload-schema.md`
- Create: `/home/timmypai/.codex/skills/wferp-report/references/report-payload-schema.md`
- Create: `/home/timmypai/.codex/skills/wferp-report/references/component-policy.md`
- Create: `/home/timmypai/.codex/skills/wferp-report/references/rawblock-policy.md`
- Create: `/home/timmypai/.codex/skills/wferp-report/references/scaffold.md`
- Create: `/home/timmypai/.codex/skills/wferp-report/references/section-build.md`
- Create: `/home/timmypai/.codex/skills/wferp-report/references/report-plan-template.md`
- Create: `/home/timmypai/.codex/skills/wferp-report/references/review-checklist.md`
- Create: `/home/timmypai/.codex/skills/wferp-report/references/repair-policy.md`
- Create: `/home/timmypai/.codex/skills/wferp-report/references/html-output.md`
- Create: `/home/timmypai/.codex/skills/wferp-report/report_designs/index.json`
- Create: `/home/timmypai/.codex/skills/wferp-report/examples/checkpoint-sql-review.json`
- Modify: `scripts/validate_local_wferp_report_skill.py`
- Modify: `tests/scripts/test_validate_local_wferp_report_skill.py`

- [ ] **Step 1: Write failing validator tests**

Add test cases requiring the beautiful-article-style structure:

```python
def test_validator_requires_harness_parity_files(tmp_path):
    skill_dir = tmp_path / "wferp-report"
    (skill_dir / "references").mkdir(parents=True)
    (skill_dir / "scripts").mkdir()
    (skill_dir / "report_designs").mkdir()
    (skill_dir / "SKILL.md").write_text("## 背景原則\n", encoding="utf-8")

    result = validate_skill_directory(skill_dir)

    missing = {item["path"] for item in result["missing"]}
    assert "manifest.json" in missing
    assert "references/checkpoint-payload-schema.md" in missing
    assert "references/rawblock-policy.md" in missing
    assert "references/scaffold.md" in missing
    assert "report_designs/index.json" in missing
    assert "assets/scaffold-template/package.json" in missing
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/scripts/test_validate_local_wferp_report_skill.py -v
```

Expected: FAIL because the validator does not require every parity file.

- [ ] **Step 3: Implement validator requirements**

Update `scripts/validate_local_wferp_report_skill.py` with this required file set:

```python
REQUIRED_FILES = [
    "SKILL.md",
    "manifest.json",
    "README.md",
    "references/harness.md",
    "references/db-config.md",
    "references/excel-intake.md",
    "references/schema-context.md",
    "references/sql-safety.md",
    "references/checkpoint-payload-schema.md",
    "references/report-payload-schema.md",
    "references/component-policy.md",
    "references/rawblock-policy.md",
    "references/scaffold.md",
    "references/section-build.md",
    "references/report-plan-template.md",
    "references/review-checklist.md",
    "references/repair-policy.md",
    "references/html-output.md",
    "references/validators.md",
    "references/e2e-expense-analysis.md",
    "scripts/scaffold-report.sh",
    "scripts/validate-skill.sh",
    "scripts/print-expense-fixture-sql.sh",
    "scripts/run-expense-sqlite-e2e.sh",
    "scripts/run-expense-postgres-e2e.sh",
    "report_designs/index.json",
    "report_designs/design.md",
    "report_designs/financial-control.md",
    "report_designs/executive-summary.md",
    "report_designs/detail-ledger.md",
    "report_designs/exception-audit.md",
    "report_designs/operations-review.md",
    "report_designs/trend-briefing.md",
    "assets/scaffold-template/package.json",
    "assets/scaffold-template/index.html",
    "assets/scaffold-template/report/Report.tsx",
]
```

- [ ] **Step 4: Update local skill documents**

Rewrite `/home/timmypai/.codex/skills/wferp-report/SKILL.md` in Chinese with the exact chapter mapping from the spec:

```markdown
## 背景原則
## 邊界
## 工作流總覽
## 硬性質檢協議
## 各階段文件讀取指南
## Phase 0 —— Intake
## Phase 1 —— Source / Excel Requirement
## Phase 2 —— Report Planning
## Phase 3 —— Field & Formula Checkpoint
## Phase 4 —— SQL Review Checkpoint
## Phase 5 —— Confirmed DB Execution
## Phase 6 —— Data Preview Checkpoint
## Phase 7 —— Report Selection Checkpoint
## Phase 8 —— Final Report Scaffold
## Phase 9 —— Section Build
## Phase 10 —— Final Review
## Phase 11 —— Repair
## Phase 12 —— Delivery
## 預設策略
## 成功標準
## 相關資源
```

Every phase must include:

```text
目標：
輸入：
必讀 references：
執行步驟：
產物：
停止條件：
使用者 checkpoint：
validator：
失敗時 repair slice：
```

- [ ] **Step 5: Run validator**

Run:

```bash
bash /home/timmypai/.codex/skills/wferp-report/scripts/validate-skill.sh
pytest tests/scripts/test_validate_local_wferp_report_skill.py -v
```

Expected:

```text
wferp-report skill validation passed
```

- [ ] **Step 6: Commit**

```bash
git add scripts/validate_local_wferp_report_skill.py tests/scripts/test_validate_local_wferp_report_skill.py
git commit -m "docs: complete wferp report skill parity structure"
```

Local skill files live outside the repo; include their paths in the evidence packet instead of staging them.

---

## Task 2: Checkpoint Companion Server And Audit State

**Files:**
- Create: `skill_scripts/checkpoint_companion.py`
- Modify: `skill_scripts/report_harness_state.py`
- Modify: `skill_scripts/report_harness.py`
- Modify: `skill_scripts/cli_report_harness.py`
- Create: `tests/skill_scripts/test_checkpoint_companion.py`
- Modify: `tests/skill_scripts/test_report_harness_state.py`
- Modify: `tests/skill_scripts/test_report_harness.py`

- [ ] **Step 1: Write failing companion tests**

Create `tests/skill_scripts/test_checkpoint_companion.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request, urlopen

from skill_scripts.checkpoint_companion import CheckpointCompanionServer
from skill_scripts.report_harness import ReportHarness


def post_json(url: str, payload: dict) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def test_confirmation_post_writes_confirmation_and_audit(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="查詢費用")
    harness.write_sql_review("SELECT department, amount FROM expenses", {"status": "pass"})

    with CheckpointCompanionServer.serve(tmp_path / "run-001") as server:
        result = post_json(
            f"{server.base_url}/api/runs/run-001/checkpoints/sql_review/confirm",
            {
                "action": "同意查詢",
                "checkpointId": "sql_review",
                "comment": "條件正確，可以查詢",
                "selectedOptions": {"view": "management"},
            },
        )

    assert result["status"] == "confirmed"
    confirmation = json.loads(
        (tmp_path / "run-001" / "checkpoints" / "02_sql_review.confirmation.json").read_text(encoding="utf-8")
    )
    assert confirmation["action"] == "同意查詢"
    assert confirmation["comment"] == "條件正確，可以查詢"
    audit_lines = (tmp_path / "run-001" / "audit" / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(audit_lines) == 1
    assert json.loads(audit_lines[0])["event"] == "checkpoint_confirmed"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/skill_scripts/test_checkpoint_companion.py -v
```

Expected: FAIL because `skill_scripts.checkpoint_companion` does not exist.

- [ ] **Step 3: Implement companion server**

Create `skill_scripts/checkpoint_companion.py` with:

```python
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread
from typing import Iterator
from urllib.parse import urlparse

from skill_scripts.report_harness import ReportHarness
from skill_scripts.report_harness_state import append_audit_event, write_confirmation


@dataclass
class RunningCheckpointServer:
    httpd: ThreadingHTTPServer
    thread: Thread
    base_url: str


class CheckpointCompanionServer:
    @staticmethod
    @contextmanager
    def serve(run_dir: str | Path, host: str = "127.0.0.1", port: int = 0) -> Iterator[RunningCheckpointServer]:
        run_path = Path(run_dir)

        class Handler(BaseHTTPRequestHandler):
            def _json(self, status: int, payload: dict) -> None:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self) -> None:
                parsed = urlparse(self.path)
                parts = [part for part in parsed.path.split("/") if part]
                if len(parts) != 6 or parts[:2] != ["api", "runs"] or parts[3] != "checkpoints" or parts[5] != "confirm":
                    self._json(404, {"status": "not_found"})
                    return
                run_id = parts[2]
                checkpoint = parts[4]
                if run_path.name != run_id:
                    self._json(409, {"status": "wrong_run"})
                    return
                content_length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
                harness = ReportHarness(run_path)
                harness.confirm(checkpoint, payload["action"])
                confirmation = write_confirmation(run_path, checkpoint, payload)
                append_audit_event(run_path, "checkpoint_confirmed", {"checkpoint": checkpoint, "action": payload["action"]})
                self._json(200, {"status": "confirmed", "confirmation": confirmation})

            def log_message(self, format: str, *args: object) -> None:
                return

        httpd = ThreadingHTTPServer((host, port), Handler)
        thread = Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        running = RunningCheckpointServer(
            httpd=httpd,
            thread=thread,
            base_url=f"http://{host}:{httpd.server_address[1]}",
        )
        try:
            yield running
        finally:
            httpd.shutdown()
            thread.join(timeout=5)
```

- [ ] **Step 4: Add state helpers**

Add helpers to `skill_scripts/report_harness_state.py`:

```python
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
```

Also update `create_report_run()` to create `source`, `plan`, `audit`, `review`, and `report/payload`.

- [ ] **Step 5: Expose CLI companion command**

Add command:

```bash
python3 -m skill_scripts.cli_report_harness serve-checkpoint --run-dir <run-dir>
```

Expected stdout:

```text
checkpoint_companion_url=http://127.0.0.1:<port>/runs/<run-id>/checkpoints/current
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/skill_scripts/test_checkpoint_companion.py tests/skill_scripts/test_report_harness_state.py tests/skill_scripts/test_report_harness.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add skill_scripts/checkpoint_companion.py skill_scripts/report_harness_state.py skill_scripts/report_harness.py skill_scripts/cli_report_harness.py tests/skill_scripts/test_checkpoint_companion.py tests/skill_scripts/test_report_harness_state.py tests/skill_scripts/test_report_harness.py
git commit -m "feat: add checkpoint companion confirmation server"
```

---

## Task 3: Product Checkpoint React App

**Files:**
- Modify: `report_renderer/src/App.tsx`
- Modify: `report_renderer/src/components/CheckpointPage.tsx`
- Modify: `report_renderer/src/components/DataPreviewTable.tsx`
- Modify: `report_renderer/src/components/ReportOptionPanel.tsx`
- Create: `report_renderer/src/components/CheckpointShell.tsx`
- Create: `report_renderer/src/components/ManagementView.tsx`
- Create: `report_renderer/src/components/TechnicalView.tsx`
- Create: `report_renderer/src/components/FieldFormulaReview.tsx`
- Create: `report_renderer/src/components/SqlReviewPanel.tsx`
- Create: `report_renderer/src/components/AggregateCheckPanel.tsx`
- Create: `report_renderer/src/components/ValidatorEvidencePanel.tsx`
- Create: `report_renderer/src/components/ActionBar.tsx`
- Modify: `report_renderer/src/styles.css`
- Modify: `report_renderer/tests/renderer.spec.ts`

- [ ] **Step 1: Write failing renderer tests**

Add tests:

```ts
it("renders management view by default and hides SQL until technical tab is selected", () => {
  render(<App payload={sqlReviewPayload} />);
  expect(screen.getByRole("heading", { name: "SQL 查詢確認" })).toBeInTheDocument();
  expect(screen.getByText("主管檢視")).toHaveAttribute("aria-selected", "true");
  expect(screen.queryByText("SELECT department, amount FROM expenses")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("tab", { name: "技術明細" }));
  expect(screen.getByText("SELECT department, amount FROM expenses")).toBeInTheDocument();
});

it("posts checkpoint confirmation to the harness endpoint", async () => {
  const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ status: "confirmed" }), { status: 200 })
  );
  render(<App payload={{ ...sqlReviewPayload, confirmUrl: "/api/runs/run-001/checkpoints/sql_review/confirm" }} />);
  fireEvent.click(screen.getByRole("button", { name: "同意查詢" }));
  await screen.findByText("已送出確認");
  expect(fetchSpy).toHaveBeenCalledWith(
    "/api/runs/run-001/checkpoints/sql_review/confirm",
    expect.objectContaining({ method: "POST" })
  );
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd report_renderer
npm test
```

Expected: FAIL because fixed checkpoint app lacks tabs and POST confirmation.

- [ ] **Step 3: Implement payload types**

Extend `CheckpointPayload` in `report_renderer/src/App.tsx`:

```ts
export interface CheckpointPayload {
  kind: "checkpoint";
  checkpointId: string;
  title: string;
  step?: string;
  confirmUrl?: string;
  fieldFormulaReview?: FieldFormulaReviewPayload;
  sqlReview?: SqlReview;
  dataPreview?: DataPreview;
  aggregateChecks?: AggregateCheck[];
  reportTypes?: ReportTypeChoice[];
  validatorEvidence?: ValidatorEvidence[];
  actions?: string[];
}
```

- [ ] **Step 4: Implement CheckpointShell and ActionBar**

`ActionBar` must POST:

```ts
await fetch(confirmUrl, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    action,
    checkpointId,
    comment,
    selectedOptions,
  }),
});
```

Show states: `idle`, `submitting`, `confirmed`, `failed`.

- [ ] **Step 5: Implement management and technical views**

Management view includes:

- requirement summary
- field/formula confirmation
- data preview
- aggregate checks
- exceptions/risks
- next-step actions

Technical view includes:

- generated SQL
- schema/table/field mapping
- relationship path
- SQL safety checks
- execution environment
- validator evidence

- [ ] **Step 6: Run renderer tests and build**

```bash
cd report_renderer
npm test
npm run build
```

Expected: PASS and Vite build completes with no TypeScript errors.

- [ ] **Step 7: Commit**

```bash
git add report_renderer/src report_renderer/tests/renderer.spec.ts
git commit -m "feat: add product checkpoint companion UI"
```

---

## Task 4: Excel Requirement And Formula Lineage

**Files:**
- Modify: `skill_scripts/excel_intake.py`
- Modify: `tests/skill_scripts/test_excel_intake.py`
- Create: `/home/timmypai/.codex/skills/wferp-report/examples/checkpoint-excel-confirmation.json`

- [ ] **Step 1: Write failing Excel intake tests**

Add tests that create a real `.xlsx` workbook with `openpyxl` or the bundled spreadsheet runtime. The workbook must contain:

- sheet `需求欄位`
- DB fields: `部門代號`, `部門名稱`, `費用科目`, `金額`
- user formula fields: `費用占比 = 金額 / 總金額`, `異常旗標 = IF(金額>預算,"超支","正常")`
- output report sheet with linked formulas

Test assertion:

```python
assert requirement["db_fields"] == ["部門代號", "部門名稱", "費用科目", "金額"]
assert requirement["formula_fields"][0]["name"] == "費用占比"
assert requirement["formula_fields"][0]["formula"] == "=金額/總金額"
assert requirement["formula_fields"][0]["dependencies"] == ["金額", "總金額"]
assert requirement["report_outputs"][0]["sheet"] == "管理報表"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/skill_scripts/test_excel_intake.py -v
```

Expected: FAIL because formula lineage and output report links are incomplete.

- [ ] **Step 3: Implement parser contract**

Return this shape:

```python
{
    "source_type": "excel",
    "db_fields": [
        {"label": "部門代號", "required": True, "matched_schema_field": None},
        {"label": "金額", "required": True, "matched_schema_field": None},
    ],
    "formula_fields": [
        {
            "name": "費用占比",
            "formula": "=金額/總金額",
            "dependencies": ["金額", "總金額"],
            "requires_user_confirmation": True,
        }
    ],
    "report_outputs": [
        {"sheet": "管理報表", "cells": [{"address": "B6", "formula": "=SUM(明細!D:D)"}]}
    ],
    "warnings": [],
}
```

- [ ] **Step 4: Add checkpoint example**

Write `/home/timmypai/.codex/skills/wferp-report/examples/checkpoint-excel-confirmation.json` using the same shape and actions:

```json
{
  "checkpointId": "excel_confirmation",
  "title": "確認欄位與公式",
  "actions": ["確認欄位與公式", "要求修正"]
}
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/skill_scripts/test_excel_intake.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add skill_scripts/excel_intake.py tests/skill_scripts/test_excel_intake.py
git commit -m "feat: parse excel report requirements and formulas"
```

Local example file is outside repo; include it in evidence packet.

---

## Task 5: Final Report Scaffold Workspace

**Files:**
- Create: `skill_scripts/report_scaffold.py`
- Modify: `skill_scripts/cli_report_harness.py`
- Create: `tests/skill_scripts/test_report_scaffold.py`
- Create: `/home/timmypai/.codex/skills/wferp-report/assets/scaffold-template/package.json`
- Create: `/home/timmypai/.codex/skills/wferp-report/assets/scaffold-template/vite.config.ts`
- Create: `/home/timmypai/.codex/skills/wferp-report/assets/scaffold-template/tsconfig.json`
- Create: `/home/timmypai/.codex/skills/wferp-report/assets/scaffold-template/index.html`
- Create: `/home/timmypai/.codex/skills/wferp-report/assets/scaffold-template/report/Report.tsx`
- Create scaffold component and directory files under `/home/timmypai/.codex/skills/wferp-report/assets/scaffold-template/report/`

- [ ] **Step 1: Write failing scaffold tests**

```python
def test_scaffold_creates_one_section_per_file_workspace(tmp_path):
    run_dir = tmp_path / "run-001"
    template_dir = tmp_path / "template"
    create_minimal_template(template_dir)

    result = scaffold_report_workspace(
        run_dir=run_dir,
        template_dir=template_dir,
        sections=["executive-summary", "kpi-overview", "data-table"],
        payload={"approved_query_result": {"rows": []}},
    )

    assert (run_dir / "report" / "Report.tsx").exists()
    assert (run_dir / "report" / "sections" / "01-executive-summary.tsx").exists()
    assert (run_dir / "report" / "sections" / "02-kpi-overview.tsx").exists()
    assert (run_dir / "report" / "sections" / "03-data-table.tsx").exists()
    assert (run_dir / "report" / "payload" / "approved-query-result.json").exists()
    assert result["section_count"] == 3
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/skill_scripts/test_report_scaffold.py -v
```

Expected: FAIL because `report_scaffold.py` does not exist.

- [ ] **Step 3: Implement scaffold runtime**

Create:

```python
def scaffold_report_workspace(run_dir: Path, template_dir: Path, sections: list[str], payload: dict) -> dict:
    copy_template(template_dir, run_dir)
    write_payload(run_dir, payload)
    create_section_files(run_dir, sections)
    validate_report_protocol(run_dir)
    return {"section_count": len(sections), "run_dir": str(run_dir)}
```

Protocol validation:

- `Report.tsx` imports generated section files.
- Every section file exports one React component.
- `raw-blocks/` exists but is empty unless selected design requires it.
- `payload/approved-query-result.json` exists.

- [ ] **Step 4: Add CLI command**

```bash
python3 -m skill_scripts.cli_report_harness scaffold-report --run-dir <run-dir> --design financial-control
```

Expected output:

```json
{"status":"scaffolded","section_count":5}
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/skill_scripts/test_report_scaffold.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add skill_scripts/report_scaffold.py skill_scripts/cli_report_harness.py tests/skill_scripts/test_report_scaffold.py
git commit -m "feat: scaffold per-run react report workspaces"
```

Local scaffold template is outside repo; include it in evidence packet.

---

## Task 6: ChartBlock, DataTable, RawBlock Policy

**Files:**
- Create: `report_renderer/src/components/ChartBlock.tsx`
- Modify: `report_renderer/src/components/DataPreviewTable.tsx`
- Create: `report_renderer/src/components/InsightBlock.tsx`
- Create: `report_renderer/src/components/RecommendationList.tsx`
- Create: `report_renderer/src/components/RawBlockNotice.tsx`
- Modify: `report_renderer/src/components/ReportPage.tsx`
- Modify: `report_renderer/src/styles.css`
- Modify: `report_renderer/tests/renderer.spec.ts`
- Modify: `/home/timmypai/.codex/skills/wferp-report/references/component-policy.md`
- Modify: `/home/timmypai/.codex/skills/wferp-report/references/rawblock-policy.md`

- [ ] **Step 1: Write failing component tests**

Add renderer tests for:

- bar, stacked bar, line, area, pie/donut, combo chart labels
- chart suitability warning when category count exceeds configured limit
- table sorting
- table text filter
- table number range filter
- table show/hide column
- summary row
- CSV export button creates a downloadable blob
- RawBlock policy notice renders metadata and risk level

Example:

```ts
it("sorts and filters management report rows", async () => {
  render(<DataPreviewTable preview={expensePreview} enableControls />);
  fireEvent.change(screen.getByLabelText("搜尋全部欄位"), { target: { value: "行政部" } });
  expect(screen.getByText("行政部")).toBeInTheDocument();
  expect(screen.queryByText("研發部")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "金額排序" }));
  expect(screen.getAllByTestId("data-row")[0]).toHaveTextContent("12,000");
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd report_renderer
npm test
```

Expected: FAIL because the components lack product table/chart controls.

- [ ] **Step 3: Implement ChartBlock without new dependencies**

Use accessible SVG for Phase 1 chart types to avoid adding a chart dependency before design review:

```ts
export type ChartType = "bar" | "stacked-bar" | "line" | "area" | "pie" | "donut" | "combo";
```

`ChartBlock` must render title, subtitle, legend, tooltip labels through `aria-label`, empty/error states, and a suitability warning when the data shape is wrong.

- [ ] **Step 4: Implement DataTable controls**

Product Phase 1 table controls:

- sorting
- text contains filtering
- number/date range filtering
- category multi-select
- show/hide columns
- frozen key column styling
- summary row
- group subtotal row
- conditional formatting
- number/date/percent/currency formatting
- full-table search
- CSV export
- pagination for large row sets

- [ ] **Step 5: Implement RawBlockNotice**

`RawBlockNotice` displays:

```ts
{
  id: string;
  title: string;
  purpose: string;
  dataDependencies: string[];
  riskLevel: "low" | "medium" | "high";
}
```

It must not execute arbitrary code. It only renders metadata and policy warnings.

- [ ] **Step 6: Run tests and build**

```bash
cd report_renderer
npm test
npm run build
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add report_renderer/src report_renderer/tests/renderer.spec.ts
git commit -m "feat: add product chart and table report components"
```

Local policy docs are outside repo; include them in evidence packet.

---

## Task 7: Report Design Catalog Enforcement

**Files:**
- Modify: `report_designs/README.md`
- Modify: `report_designs/design.md`
- Create: `report_designs/index.json`
- Modify: `report_designs/financial-control.md`
- Modify: `report_designs/executive-summary.md`
- Modify: `report_designs/detail-ledger.md`
- Modify: `report_designs/exception-audit.md`
- Modify: `report_designs/operations-review.md`
- Modify: `report_designs/trend-briefing.md`
- Modify: `skill_scripts/report_catalog.py`
- Modify: `tests/skill_scripts/test_report_catalog.py`
- Mirror the same catalog under `/home/timmypai/.codex/skills/wferp-report/report_designs/`

- [ ] **Step 1: Write failing catalog tests**

```python
def test_design_catalog_requires_all_product_metadata(repo_root):
    catalog = load_report_design_catalog(repo_root / "report_designs")
    financial = catalog.get_profile("financial-control")
    assert financial["label"] == "財務控制"
    assert financial["best_for"]
    assert financial["required_sections"]
    assert financial["default_components"]
    assert financial["chart_policy"]
    assert financial["table_policy"]
    assert financial["kpi_policy"]
    assert financial["tone"]
    assert financial["layout_density"]
    assert financial["validator_focus"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/skill_scripts/test_report_catalog.py -v
```

Expected: FAIL because `index.json` or required metadata validation is incomplete.

- [ ] **Step 3: Implement `index.json`**

Required IDs:

```json
[
  "financial-control",
  "executive-summary",
  "detail-ledger",
  "exception-audit",
  "operations-review",
  "trend-briefing"
]
```

Every profile entry must define:

```json
{
  "id": "financial-control",
  "label": "財務控制",
  "best_for": ["費用分析", "預算差異", "異常控管"],
  "required_sections": ["executive-summary", "kpi-overview", "trend", "detail-table", "recommendations"],
  "default_components": ["KpiGrid", "ChartBlock", "DataTable", "InsightBlock", "RecommendationList"],
  "chart_policy": {"preferred": ["bar", "stacked-bar", "combo"], "avoid": ["pie"]},
  "table_policy": {"density": "compact", "summary_rows": true, "conditional_formatting": true},
  "kpi_policy": {"include_variance": true, "include_budget_ratio": true},
  "tone": "管理控制、明確、可追責",
  "layout_density": "dense",
  "validator_focus": ["aggregate_consistency", "variance_explanation", "exception_visibility"]
}
```

- [ ] **Step 4: Enforce selected design in runtime**

`skill_scripts/report_catalog.py` must:

- read `index.json`
- reject missing profile files
- reject profile IDs not listed in index
- reject profiles missing any required key
- expose selected design defaults for report scaffold

- [ ] **Step 5: Run tests**

```bash
pytest tests/skill_scripts/test_report_catalog.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add report_designs skill_scripts/report_catalog.py tests/skill_scripts/test_report_catalog.py
git commit -m "feat: enforce report design catalog metadata"
```

Local mirrored catalog is outside repo; include it in evidence packet.

---

## Task 8: Validator Protocol And Minimal Repair Policy

**Files:**
- Modify: `skill_scripts/validator_contracts.py`
- Modify: `skill_scripts/report_harness.py`
- Modify: `tests/skill_scripts/test_validator_contracts.py`
- Modify: `tests/skill_scripts/test_report_harness.py`
- Modify: `/home/timmypai/.codex/skills/wferp-report/references/validators.md`
- Modify: `/home/timmypai/.codex/skills/wferp-report/references/repair-policy.md`
- Modify: `/home/timmypai/.codex/skills/wferp-report/references/review-checklist.md`

- [ ] **Step 1: Write failing validator tests**

```python
def test_validator_result_requires_evidence_and_repair_fields():
    result = ValidatorResult(
        role="sql_safety_reviewer",
        status="fail",
        evidence=[{"command": "python3 -m skill_scripts.cli_report_harness validate-sql"}],
        findings=["SELECT INTO is blocked"],
        requiredFixes=["Remove SELECT INTO"],
        residualRisks=[],
    )
    assert result.to_dict()["status"] == "fail"


def test_success_is_blocked_when_any_validator_fails(tmp_path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="查詢費用")
    harness.write_report_selection({"selected_report_type": "管理摘要", "selected_report_design": "financial-control"})
    harness.confirm("report_selection", "產生報告")
    harness.write_report_draft({"sections": ["摘要"]})
    harness.confirm("report_draft", "接受")
    harness.write_final_review({
        "validator_results": [
            {"role": "visual_taste_reviewer", "status": "fail", "evidence": [], "findings": ["文字重疊"], "requiredFixes": ["修正表格寬度"], "residualRisks": []}
        ]
    })
    assert harness.can_deliver()["allowed"] is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/skill_scripts/test_validator_contracts.py tests/skill_scripts/test_report_harness.py -v
```

Expected: FAIL because final delivery gate does not aggregate validator failures.

- [ ] **Step 3: Implement validator roles**

Required roles:

```python
VALIDATOR_ROLES = {
    "source_requirement_reviewer",
    "excel_formula_reviewer",
    "sql_safety_reviewer",
    "schema_relationship_reviewer",
    "data_preview_reviewer",
    "report_content_reviewer",
    "visual_taste_reviewer",
    "data_visualization_reviewer",
    "react_technical_reviewer",
}
```

- [ ] **Step 4: Implement delivery gate**

`ReportHarness.can_deliver()` returns:

```python
{
    "allowed": False,
    "blocking_validators": ["visual_taste_reviewer"],
    "accepted_residual_risks": [],
}
```

Only allow delivery when all validators pass or user confirmation explicitly accepts residual risk at final checkpoint.

- [ ] **Step 5: Implement repair log append**

`ReportHarness.append_repair_log()` writes `review/repair-log.md` entries:

```text
## 2026-06-18 sql_safety_reviewer

Failure:
Scope:
Minimal vertical slice:
Files changed:
Validation rerun:
Residual risk:
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/skill_scripts/test_validator_contracts.py tests/skill_scripts/test_report_harness.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add skill_scripts/validator_contracts.py skill_scripts/report_harness.py tests/skill_scripts/test_validator_contracts.py tests/skill_scripts/test_report_harness.py
git commit -m "feat: enforce report validators and repair gates"
```

Local reference docs are outside repo; include them in evidence packet.

---

## Task 9: SQLite-First And PostgreSQL Formal E2E Acceptance

**Files:**
- Modify: `tests/skill_scripts/expense_report_fixture.py`
- Modify: `tests/skill_scripts/test_expense_analysis_sqlite_e2e.py`
- Modify: `tests/skill_scripts/test_expense_analysis_postgres_e2e.py`
- Modify: `scripts/run_expense_analysis_sqlite_e2e.sh`
- Modify: `scripts/run_expense_analysis_postgres_e2e.sh`
- Modify: `/home/timmypai/.codex/skills/wferp-report/references/e2e-expense-analysis.md`

- [ ] **Step 1: Write failing quantitative E2E assertions**

SQLite-first acceptance:

```python
def test_expense_analysis_sqlite_e2e_quantitative_acceptance(tmp_path):
    result = run_expense_analysis_sqlite_e2e(tmp_path)
    assert result["row_count"] == 6
    assert result["columns"] == ["department_code", "department_name", "expense_subject", "amount", "budget_amount", "variance_amount", "expense_ratio"]
    assert result["aggregates"]["total_amount"] == 120000
    assert result["aggregates"]["total_budget"] == 100000
    assert result["aggregates"]["variance_amount"] == 20000
    assert result["aggregates"]["max_expense_ratio"] == 0.35
    assert result["excluded_rows"]["non_2026"] == 1
    assert result["excluded_rows"]["non_expense_account"] == 1
    assert result["sql_safety"]["readonly"] is True
    assert result["sql_safety"]["blocked_keywords"] == []
```

PostgreSQL formal substitute acceptance must run the same semantic query against Docker PostgreSQL and assert the same aggregates.

- [ ] **Step 2: Run SQLite test to verify it fails**

```bash
pytest tests/skill_scripts/test_expense_analysis_sqlite_e2e.py -v
```

Expected: FAIL if any required quantitative assertion is missing or incorrect.

- [ ] **Step 3: Implement deterministic fixture data**

Fixture rows:

```text
2026 行政部 旅費 35000 budget 30000
2026 行政部 文具 10000 budget 8000
2026 研發部 雲端服務 30000 budget 25000
2026 研發部 軟體訂閱 25000 budget 22000
2026 業務部 交際費 12000 budget 10000
2026 業務部 廣告費 8000 budget 5000
2025 行政部 旅費 9000 budget 9000
2026 行政部 資產購置 50000 budget 50000
```

Expected included amount: `120000`. Exclude `2025` and `資產購置`.

- [ ] **Step 4: Run SQLite E2E**

```bash
bash scripts/run_expense_analysis_sqlite_e2e.sh
```

Expected:

```text
sqlite_expense_e2e=pass row_count=6 total_amount=120000 total_budget=100000 variance_amount=20000 max_expense_ratio=0.35
```

- [ ] **Step 5: Run PostgreSQL E2E**

```bash
bash scripts/run_expense_analysis_postgres_e2e.sh
```

Expected:

```text
postgres_expense_e2e=pass row_count=6 total_amount=120000 total_budget=100000 variance_amount=20000 max_expense_ratio=0.35
```

- [ ] **Step 6: Run both pytest files**

```bash
pytest tests/skill_scripts/test_expense_analysis_sqlite_e2e.py tests/skill_scripts/test_expense_analysis_postgres_e2e.py -v
```

Expected: PASS. These are real E2E tests with real local DB setup and real SQL execution.

- [ ] **Step 7: Commit**

```bash
git add tests/skill_scripts/expense_report_fixture.py tests/skill_scripts/test_expense_analysis_sqlite_e2e.py tests/skill_scripts/test_expense_analysis_postgres_e2e.py scripts/run_expense_analysis_sqlite_e2e.sh scripts/run_expense_analysis_postgres_e2e.sh
git commit -m "test: enforce expense report e2e acceptance"
```

Local E2E reference doc is outside repo; include it in evidence packet.

---

## Task 10: Full Flow Wiring And Final Verification

**Files:**
- Modify: `skill_scripts/cli_report_harness.py`
- Modify: `skill_scripts/report_harness.py`
- Modify: `report_renderer/README.md`
- Modify: `/home/timmypai/.codex/skills/wferp-report/SKILL.md`
- Modify: `/home/timmypai/.codex/skills/wferp-report/README.md`
- Modify: `/home/timmypai/.codex/skills/wferp-report/references/harness.md`

- [ ] **Step 1: Write failing CLI flow test**

Add a CLI test that executes the local flow through files:

```python
import json
import subprocess
import sys


def run_cli(args, expect_code=0):
    completed = subprocess.run(
        [sys.executable, "-m", "skill_scripts.cli_report_harness", *args],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == expect_code, completed.stderr
    if expect_code == 0:
        return json.loads(completed.stdout)
    return {"stdout": completed.stdout, "stderr": completed.stderr, "returncode": completed.returncode}


def test_cli_full_flow_blocks_and_advances_by_confirmation(tmp_path):
    run_root = tmp_path / "runs"
    result = run_cli(["create-run", "--run-root", str(run_root), "--run-id", "run-001", "--prompt", "查詢費用分析"])
    assert result["status"] == "created"

    sql_result = run_cli(["write-sql-review", "--run-dir", str(run_root / "run-001"), "--sql", "SELECT department, amount FROM expenses"])
    assert sql_result["checkpoint"] == "sql_review"

    blocked = run_cli(["write-data-preview", "--run-dir", str(run_root / "run-001"), "--payload", "{}"], expect_code=2)
    assert "SQL must be confirmed" in blocked["stderr"]

    confirm = run_cli(["confirm", "--run-dir", str(run_root / "run-001"), "--checkpoint", "sql_review", "--action", "同意查詢"])
    assert confirm["status"] == "confirmed"
```

- [ ] **Step 2: Run flow tests to verify failure**

```bash
pytest tests/skill_scripts/test_cli_report_harness.py -v
```

Expected: FAIL where CLI commands are missing or not enforcing confirmation files.

- [ ] **Step 3: Wire CLI commands**

Required commands:

```text
create-run
write-excel-confirmation
write-sql-review
confirm
write-data-preview
write-report-selection
scaffold-report
write-final-review
can-deliver
serve-checkpoint
```

Each command outputs JSON and returns non-zero on blocked gates.

- [ ] **Step 4: Update user-facing docs**

Update local `SKILL.md` and `references/harness.md` so executing the skill means executing this harness:

```text
1. 建立 run
2. 解析 prompt/Excel
3. 開啟欄位與公式 checkpoint
4. 生成 SQL review checkpoint
5. 使用者確認後查詢 DB
6. 開啟 data preview checkpoint
7. 開啟 report selection checkpoint
8. scaffold final React report
9. 執行 validators
10. repair 或 delivery
```

- [ ] **Step 5: Run complete verification**

```bash
pytest tests/scripts/test_validate_local_wferp_report_skill.py -v
pytest tests/skill_scripts/test_checkpoint_companion.py tests/skill_scripts/test_report_harness.py tests/skill_scripts/test_report_scaffold.py tests/skill_scripts/test_validator_contracts.py tests/skill_scripts/test_cli_report_harness.py -v
pytest tests/skill_scripts/test_expense_analysis_sqlite_e2e.py -v
bash scripts/run_expense_analysis_postgres_e2e.sh
cd report_renderer && npm test && npm run build
bash /home/timmypai/.codex/skills/wferp-report/scripts/validate-skill.sh
```

Expected:

- all pytest targets PASS
- PostgreSQL E2E prints `postgres_expense_e2e=pass`
- Vitest PASS
- Vite build completes
- skill validator prints `wferp-report skill validation passed`

- [ ] **Step 6: Commit**

```bash
git add skill_scripts/cli_report_harness.py skill_scripts/report_harness.py report_renderer/README.md tests/skill_scripts/test_cli_report_harness.py
git commit -m "feat: wire wferp report harness flow"
```

Local skill docs are outside repo; include them in evidence packet.

---

## Subagent Evidence Packet

Every subagent must return this packet:

```json
{
  "task": "Task N name",
  "status": "pass",
  "files_changed": [],
  "outside_repo_files_changed": [],
  "tests_failed_first": [
    {"command": "pytest ...", "expected_failure": "module not found or assertion failure"}
  ],
  "tests_passed_after": [
    {"command": "pytest ...", "evidence": "PASS"}
  ],
  "quantitative_acceptance": {},
  "validator_evidence": [],
  "commits": [],
  "residual_risks": []
}
```

Main agent review requirements:

- reject a packet without failing-test evidence
- reject a packet that uses non-real E2E instead of SQLite/PostgreSQL real execution
- reject a packet that stages unrelated worktree changes
- reject a packet that changes confirmed Excel fields without returning to the field/formula checkpoint
- reject a packet that delivers report output while validators are failing

## Final Acceptance Criteria

- Local skill has full beautiful-article-style chapter mapping and progressive disclosure references.
- Checkpoint companion opens a local URL, posts confirmation to harness, writes confirmation JSON and audit JSONL.
- Management view is understandable without reading SQL; technical view exposes SQL/schema/validator evidence.
- Excel intake captures DB fields, user formula fields, formula dependencies, and desired output report links.
- Final report scaffold creates one section per file and uses approved component protocol.
- `RawBlock` is documented and constrained to readonly props and no browser/DB/SQL side effects.
- ChartBlock supports bar, stacked bar, line, area, pie/donut, and combo.
- DataTable supports sorting, filtering, show/hide columns, summary rows, conditional formatting, full-table search, CSV export, and pagination.
- Report design catalog includes `index.json` and six product profiles.
- Validators block delivery on failures unless user explicitly accepts residual risk.
- Repair log records minimal vertical slice scope.
- SQLite-first E2E passes with `row_count=6`, `total_amount=120000`, `total_budget=100000`, `variance_amount=20000`, `max_expense_ratio=0.35`.
- Docker PostgreSQL formal E2E passes with the same quantitative acceptance.
- React test and build pass.
- Local skill structure validator passes.

# Harness

執行 `wferp-report` skill 就是執行 harness flow。主 agent / LLM 負責理解、規劃與生成；harness 負責 checkpoint、user confirmation、evidence、validator gate 與 repair loop。不要只產出 SQL 後停止。

此 harness 採用 beautiful-article 式逐層揭露：先理解需求，再讓使用者確認欄位/公式/視覺規劃，再確認 SQL，再確認資料，再確認報表設計與最終 HTML。每個硬 gate 都必須保存 JSON payload、HTML companion、confirmation file 與 validator evidence。

## Input Matrix

四種輸入組合全部收斂成同一條 pipeline：

| 資料來源需求 | 報表格式需求 | Harness 處理 |
|---|---|---|
| prompt | prompt | LLM 從 prompt + WFERP schema 推導 source requirement、report logic、chart/layout proposal。 |
| prompt | Excel template | LLM 從 prompt 推資料來源，從 Excel template 抽象報表格式、公式與版型。 |
| Excel source | prompt | LLM 解析 Excel 欄位、公式、lookup 與 manual fields，再依 prompt 產報表規劃。 |
| Excel source | Excel template | LLM 同時理解 source workbook 與 template workbook，抽象來源資料與目標報表。 |

後續 SQL、DB execution、SQLite enrichment、React renderer 與 single HTML delivery 只讀 `plan/normalized-report-plan.json` 與確認後的資料/evidence。

## Phase Map

| Phase | 名稱 | 主要輸出 | 硬 gate |
|---|---|---|---|
| 0 | Intake | `source/source-inventory.json`、`db/db-config.json` | 不明確時停止 |
| 1 | Source / Excel Requirement | `source/workbook-map.json`、`plan/formula-semantics.json` | 併入 Phase 3 |
| 2 | Report Planning | `plan/normalized-report-plan.json`、`plan/chart-plan.json`、`plan/layout-plan.json` | 併入 Phase 3 |
| 3 | Field & Formula Checkpoint | `checkpoints/01_field_formula.json` | 必須 user confirmation |
| 4 | SQL Review Checkpoint | `sql/query.sql`、`checkpoints/02_sql_review.json` | 必須 user confirmation |
| 5 | Confirmed DB Execution | `data/raw-preview.json`、`sqlite/run.sqlite3` | SQL confirmed + validators pass |
| 6 | Data Preview Checkpoint | `data/enriched-preview.json`、`checkpoints/03_data_preview.json` | 必須 user confirmation |
| 7 | Report Selection Checkpoint | `plan/selected-report-design.json`、`checkpoints/04_report_selection.json` | 必須 user confirmation |
| 8 | Final Report Scaffold | `report/payload/report-payload.json`、`report/scaffold/` | payload/schema gate |
| 9 | Section Build | LLM-generated `report/sections/*.tsx`、chart/table/component payload | section validator gate |
| 10 | Final Review | `review/final-review.json`、validators | validators pass / accepted warning |
| 11 | Repair | `review/repair-log.md` | 重跑受影響 validators |
| 12 | Delivery | `report/delivery/report.html`、delivery manifest | final user confirmation |

## Main Checkpoints

使用者主要只面對四個 checkpoint。內部 phase 可以更多，但不要讓使用者在每個小步驟被打斷。

1. **Field & Formula Checkpoint**：確認 uploaded files、Excel confirmation、sheet roles、DB-backed / formula-backed / lookup-backed / manual-only 欄位、WFERP schema/relationship mapping、report logic、chart/layout 初稿。
2. **SQL Review Checkpoint**：確認 read-only SQL、table/field readable names、joins、filters、aggregates、assumptions 與不下推 DB 的公式/enrichment 欄位。
3. **Data Preview Checkpoint**：確認 DB raw data preview、SQLite enrichment、lookup hit/miss、formula status、aggregate checks 與 excluded rows。
4. **Report Selection / Final Checkpoint**：確認 report type、design/options、chart/table/layout、React HTML report、Excel-like view、validator evidence、residual risks 與 SQLite retention。

## CLI Flow

所有命令都輸出 JSON。被 gate 擋下時，命令必須以 non-zero exit code 結束，並在 stderr 輸出 JSON error。

```bash
python3 -m skill_scripts.cli_report_harness create-run \
  --run-root wferp-report-runs \
  --run-id run-001 \
  --prompt "查詢費用分析" \
  --llm-provider codex

python3 -m skill_scripts.cli_report_harness classify-workbook \
  --run-dir wferp-report-runs/run-001 \
  --input-file requirement.xlsx \
  --llm-provider codex

python3 -m skill_scripts.cli_report_harness write-sql-review \
  --run-dir wferp-report-runs/run-001 \
  --sql "SELECT department, amount FROM expenses"

python3 -m skill_scripts.cli_report_harness serve-checkpoint \
  --run-dir wferp-report-runs/run-001 \
  --host 127.0.0.1 \
  --port 0

python3 -m skill_scripts.cli_report_harness wait-confirmation \
  --run-dir wferp-report-runs/run-001 \
  --checkpoint sql_review \
  --timeout-seconds 1800

python3 -m skill_scripts.cli_report_harness init-sqlite-workspace \
  --run-dir wferp-report-runs/run-001

python3 -m skill_scripts.cli_report_harness write-raw-table \
  --run-dir wferp-report-runs/run-001 \
  --rows query-result.json

python3 -m skill_scripts.cli_report_harness write-raw-preview \
  --run-dir wferp-report-runs/run-001

python3 -m skill_scripts.cli_report_harness run-sqlite-enrichment \
  --run-dir wferp-report-runs/run-001

python3 -m skill_scripts.cli_report_harness write-enriched-preview \
  --run-dir wferp-report-runs/run-001

python3 -m skill_scripts.cli_report_harness write-report-selection \
  --run-dir wferp-report-runs/run-001 \
  --report-design financial-control \
  --include-chart \
  --include-table \
  --include-analysis

python3 -m skill_scripts.cli_report_harness scaffold-report \
  --run-dir wferp-report-runs/run-001

python3 -m skill_scripts.cli_report_harness generate-report-section \
  --run-dir wferp-report-runs/run-001 \
  --section-id 01-executive-summary \
  --component-name ExecutiveSummary01Section \
  --code-file /tmp/section.tsx

python3 -m skill_scripts.cli_report_harness validate-report-section \
  --run-dir wferp-report-runs/run-001 \
  --section-id 01-executive-summary

python3 -m skill_scripts.cli_report_harness write-report-draft \
  --run-dir wferp-report-runs/run-001 \
  --payload report-draft.json

python3 -m skill_scripts.cli_report_harness write-final-review \
  --run-dir wferp-report-runs/run-001 \
  --payload final-review.json

python3 -m skill_scripts.cli_report_harness can-deliver \
  --run-dir wferp-report-runs/run-001
```

## Companion / Confirmation Contract

`serve-checkpoint` 會啟動本地確認服務並輸出 checkpoint URL JSON。瀏覽器只讀 checkpoint payload，不得連 DB、不得執行 SQL、不得保存 credentials。

主 agent 不得只等待使用者在聊天端回報按了哪個按鈕。每次開啟 checkpoint companion 後，都要用 `wait-confirmation` 阻塞等待瀏覽器 POST 產生的 confirmation file：

```bash
python3 -m skill_scripts.cli_report_harness wait-confirmation \
  --run-dir wferp-report-runs/run-001 \
  --checkpoint field_formula \
  --timeout-seconds 1800
```

`wait-confirmation` 成功時會輸出 `status=confirmed`、`action`、`comment`、`selectedOptions` 與 `confirmation_file`。若 agent 啟動等待前使用者已在瀏覽器按過按鈕，只有在 confirmation file 屬於目前 checkpoint 且 mtime 晚於 checkpoint payload 時，才可使用 `--allow-existing` 回收。

## Gate Rules

- `write-raw-table` 必須在 SQL Review Checkpoint action 為 `同意查詢`，且 `sql_safety_reviewer`、`schema_mapping_reviewer` 都 pass 後才能執行。
- `write-raw-preview` 必須在 raw table 寫入後執行，讓使用者先確認 DB 資料本身。
- `run-sqlite-enrichment` 必須在 Field & Formula Checkpoint 已確認、lookup import 完成、raw preview 可追溯時執行。
- `write-enriched-preview` 必須呈現 enrichment 後欄位、formula status、lookup hit/miss、row count 與 aggregate checks。
- `write-report-selection` 之前必須有 `db_execution_reviewer`、`data_preview_reviewer` 與必要的 `sqlite_enrichment_reviewer` evidence。
- `scaffold-report` 必須在 Report Selection Checkpoint 已確認後執行。
- `generate-report-section` / `repair-report-section` 只允許寫入單一 run-scoped `report/sections/*.tsx`，不得寫其他 repo 或系統檔案。
- `validate-report-section` 必須在每個 LLM-generated section 寫入或修復後執行，並確認 section export、data refs、safe imports、無 network/env/DB/SQL side effect、與 `Report.tsx` linkage。
- `write-report-draft` 必須使用確認後的 report design、chart plan、layout plan 與 data package。
- `write-final-review` 必須在 draft 可開啟後執行，且 `report_content_reviewer`、`visual_taste_reviewer`、`react_technical_reviewer`、`delivery_reviewer` 都已輸出 evidence。
- `can-deliver` 只有在 required validators 都 pass，或 final checkpoint 明確接受相符 residual risks 時才允許 delivery。
- SQLite temp table retention 必須在 delivery 前詢問使用者是否保留；若選擇刪除，需保存 cleanup evidence。

## Subagent Gate Flow

- 主 agent 負責產生 checkpoint、spawn reviewer、彙整 reviewer JSON、驗證 contract、判斷 gate。
- subagent reviewer 負責內容驗證，包含 contract、evidence、資料、SQL、schema、報告內容、HTML 視覺與互動。
- validator gate 是 subagent review 的結果，不是主 agent 另行自填。
- 任一 reviewer `fail` 或 `blocked`：停止該硬 gate，主 agent 依 `requiredFixes` 做最小 repair slice，修復後只重跑該 reviewer 與受影響下游 reviewer。
- 任一 reviewer `warning`：可進入可逆下游工作，但 final delivery 前必須在 final checkpoint 由使用者接受 role-prefixed residual risk。
- 可並行工作可先做，但不能越過依賴 gate。例如 SQL reviewer 執行中可準備 report plan 摘要，但不可執行 DB query。
## 13-Phase Engine, 4-Step User Workbench

The harness keeps all 13 technical phases. The Visual Companion groups them into 4 user-facing steps:

| User Step | Technical Coverage | Required Evidence |
|---|---|---|
| 1. Source-to-Output Logic | Phase 0-3 | source inventory, Excel extraction, source-to-output matrix, formula semantics, schema mapping, chart/layout plan |
| 2. SQL Query | Phase 4 | single SELECT SQL, readable table/field mapping, SQL safety validator, schema validator, user query consent |
| 3. Data Result and Report Design | Phase 5-7 | production SELECT evidence, raw data preview, local SQLite table, enriched preview, 50-row table preview, chart/table/report options |
| 4. Final Delivery | Phase 8-12 | report payload, single-file HTML, true `.xlsx`, validator evidence, visual evidence, residual risk decision |

`state.json` is the source of truth for all transitions. A checkpoint can advance only when the current `run_id`, `checkpoint_id`, and `payload_hash` match the persisted confirmation. Stale files, stale browser tabs, and chat memory do not unlock a gate.

The companion can be simplified to 4 user steps, but the harness must not remove validator execution, SQLite enrichment, prompt repair, production SELECT-only safety, or final delivery evidence.

Capability ownership remains explicit: use Build Web Apps for the companion and final HTML UI, Build Web Data Visualization for real-data KPI/chart/table/report visualization, and spreadsheets for true `.xlsx` workbook generation and verification.

---
name: wferp-report
description: Use when the user needs a WFERP/Workflow ERP management report from prompt and/or Excel inputs, including natural-language SQL generation, Excel formula/template understanding, DB-backed data preview, chart/layout confirmation, and single-file HTML report delivery.
---

# wferp-report

## Production DB Baseline

The current workstation WFERP database connection is production. Treat the
Excel/ODC connection from the user's attachments as production unless the user
explicitly provides a verified test database.

Canonical production connection evidence:

- ODC attachment: `C:/Users/ivychi/util/test/css04 CHD View_Customer.odc`
- Excel attachment: `C:/Users/ivychi/util/test/1 財務_訂單報表即時分析_CHD.XLSX`
- Provider: `SQLOLEDB.1`
- Authentication: `Integrated Security=SSPI`
- User ID in the workbook connection string: `IRO`
- Initial Catalog: `CHD`
- Data Source: `css04`
- Workstation ID in the workbook connection string: `CPC100`
- Default source object: `[CHD].[dbo].[View_Customer]`

Production SQL rule:

- Only execute `SELECT` statements against this database connection.
- Allowed smoke test: `SELECT TOP 1 1 AS connection_test`.
- Allowed schema probe: `SELECT TOP 0 * FROM [CHD].[dbo].[View_Customer]`.
- Do not execute `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `TRUNCATE`, `DROP`,
  `ALTER`, `CREATE`, `EXEC`, stored procedures, transaction-changing commands,
  or any other data-changing SQL against production.
- Local CSV, JSON, SQLite, and HTML artifacts may be written under the run
  folder, but they must be labeled as local artifacts, not production writes.

Read `references/db-config.md` before any DB-backed phase. If a requested SQL
operation is not SELECT-only, stop and ask the user for a verified
non-production environment.

## 13-Phase Engine, 4-Step User UI

The internal harness keeps the 13 technical phases. The Visual Companion exposes only 4 user-facing steps:

1. Source-to-Output Logic
2. SQL Query
3. Data Result and Report Design
4. Final Delivery

The user-facing 4 steps do not remove technical phases, validators, SQLite enrichment, lookup handling, SQL safety, repair, or delivery evidence. Each 4-step page is an aggregation over current-run artifacts and `state.json`, not a replacement for the harness.

Step 3 must render real current-run raw and enriched data tables. The default visible preview is 50 rows, with total row count and source labels still shown.

## Required Capability Ownership

- Use Build Web Apps for Visual Companion UI, prompt repair controls, confirmation UX, responsive layout, and final HTML app shell when available.
- Use Build Web Data Visualization for real-data KPI, chart, table, pivot-like preview, and report visualization when available.
- Use spreadsheets for true `.xlsx` generation and workbook verification when Excel output is requested. The current implementation routes through `@oai/artifact-tool` rather than `openpyxl`.
- If a required capability is unavailable, stop and ask before falling back.

## State-Gated Progression

`state.json` is the workflow source of truth. The harness must not advance from chat memory, stale files, stale confirmations, or file presence alone. Confirmation identity must match the current `run_id`, `checkpoint_id`, and `payload_hash`.

## 背景原則

`wferp-report` 是 **LLM-driven report generation harness**，不是 deterministic SQL 工具。主 agent / LLM 負責讀懂使用者 prompt、uploaded files、Excel 欄位與公式、WFERP schema 與 relationships、報表需求、chart/layout 偏好，並生成 SQL、資料語意、React report payload 與 single-file HTML 報告。Harness 負責 checkpoint、evidence、user confirmation、repair loop 與 gating。Subagent validators 負責獨立審查，不能用主 agent 自己的摘要取代。

Excel 在本 skill 中可能同時是來源資料欄位、lookup 對照表、公式邏輯、舊管理報表模板、人工加工痕跡與格式提示。預設不逐格複製 Excel；除非使用者明確要求，Excel 公式是理解報表語意的來源，而不是最終必須逐格重現的交付目標。

最終交付預設包含：single-file HTML 管理報告、Excel-like summary/template view、read-only SQL、data preview、SQLite enrichment evidence、validator evidence、residual risks 與可重播的 report payload。

---

## 邊界（先判斷是否進入本 Skill）

進入本 skill：

- 使用者用 prompt 要求產生 WFERP / Workflow ERP 管理報表或 SQL。
- 使用者提供 uploaded files，例如 Excel source workbook、明細帳、欄位清單、lookup 表、公式或既有報表模板。
- 使用者要求費用分析、損益表、預算實績、明細帳、管理分析、異常稽核、趨勢比較等 DB-backed 報表。
- 使用者要求以 harness 方式完成 SQL safety、DB execution、data preview、React renderer、HTML report 與 validation evidence。

不要進入本 skill：

- 純靜態文章、美化長文、非 DB-backed 內容整理。
- 純前端 dashboard prototype，不需要 WFERP schema / DB / SQL。
- 使用者只要解釋一段 SQL，不要執行 harness。
- 使用者要求寫入、更新或刪除 DB 資料。

硬邊界：

- SQL 只允許 read-only SQL，也就是單一 `SELECT`。
- 禁止 `INSERT`、`UPDATE`、`DELETE`、`DROP`、`ALTER`、`EXEC`、`MERGE`、`TRUNCATE`、`SELECT INTO`、multi statement、comments、`xp_`。
- 未經 SQL checkpoint、user confirmation 與 validator gate，不得連 DB 執行查詢。
- Browser / React renderer 只能讀 structured payload，不得連 DB、不得執行 SQL、不得保存 credentials。
- 正式報告不得用 fake、mock、smoke 取代 DB execution evidence。
- 不得偷偷 fallback 到 rule classifier / rule SQL generator。理解與生成預設由 LLM 完成；deterministic code 只做 guard、validation、translation、evidence persistence。

---

## 四種輸入組合（全部收斂成同一條 pipeline）

使用者可能提供兩類資訊：資料來源需求與報表格式需求。資料來源需求可能來自 prompt 或 Excel source；報表格式需求可能來自 prompt 或 Excel report template。

| 資料來源需求 | 報表格式需求 | 處理方式 |
|---|---|---|
| prompt | prompt | LLM 從 prompt + WFERP schema 推 source plan，並生成 report type、chart/layout proposal。 |
| prompt | Excel template | LLM 從 prompt 推資料來源，從 Excel template 抽象報表邏輯與版型。 |
| Excel source | prompt | LLM 解析 Excel source 欄位/公式/lookup，依 prompt 動態設計報表。 |
| Excel source | Excel template | LLM 同時理解 source workbook 與 template workbook，抽象 formula/report logic。 |

四種輸入不得分裂成四套流程。必須先 normalize 成同一份 **Normalized Report Plan**，再進 SQL / data / report harness。

---

## Normalized Report Plan

所有輸入最後都必須轉成同一個中介規格，後續 SQL、資料預覽、報告生成只讀它：

```json
{
  "source_requirement": {},
  "report_logic": {},
  "layout_plan": {},
  "chart_plan": {},
  "formula_semantics": {},
  "manual_exceptions": [],
  "assumptions": [],
  "validation_targets": []
}
```

`source_requirement` 說明需要哪些 DB source tables / fields、哪些欄位由 Excel source 提供語意、哪些欄位由 lookup / SQLite enrichment 產出、哪些欄位 manual-only 或 unresolved。

`report_logic` 說明報表的管理問題、每個重要數字的 business definition、指標如何由 raw data / enrichment / aggregate 推得，以及 Excel 公式被保留、簡化、移除或轉成語意邏輯的原因。

`layout_plan` / `chart_plan` 說明 HTML 報告章節、Excel-like summary/template view、chart 類型、欄位、用途、替代方案，以及表格互動功能。

---

## 工作流總覽

```text
Phase 0  Intake
   判斷 prompt / uploaded files / DB / LLM / run workspace
   ▼
Phase 1  Source / Excel Requirement
   LLM 解析 source prompt、Excel source、欄位、公式、lookup、template sheets
   ▼
Phase 2  Report Planning
   產出 Normalized Report Plan、report type、chart/layout proposal
   ▼
Phase 3  Field & Formula Checkpoint       ★ user confirmation
   HTML companion 顯示欄位、公式、manual exceptions、圖表與 layout
   ▼
Phase 4  SQL Review Checkpoint            ★ user confirmation
   LLM 產 SELECT；SQL safety + schema/relationship validators
   ▼
Phase 5  Confirmed DB Execution
   只在 SQL confirmed + validators pass 後查 DB，保存 raw evidence
   ▼
Phase 6  Data Preview Checkpoint          ★ user confirmation
   顯示 raw/enriched data preview、aggregate checks、formula status
   ▼
Phase 7  Report Selection Checkpoint      ★ user confirmation
   使用者確認 report type / design / chart / table / layout options
   ▼
Phase 8  Final Report Scaffold
   React renderer scaffold + report payload + single HTML export setup
   ▼
Phase 9  Section Build
   逐段生成 report sections、chart/table/component payload
   ▼
Phase 10 Final Review
   validators 檢查內容、數字、HTML、視覺、技術與 delivery evidence
   ▼
Phase 11 Repair
   最小垂直切片修復，重跑受影響 validators
   ▼
Phase 12 Delivery
   交付 single-file HTML、payload、SQL、data、validator evidence
```

四個主要使用者 checkpoint：

1. **欄位/公式/規劃確認**：source plan、formula semantics、manual exceptions、chart/layout 初稿。
2. **SQL 確認**：read-only SQL、table/field readable names、joins、filters、assumptions。
3. **資料預覽確認**：raw preview、enriched preview、aggregate checks、lookup hit/miss。
4. **報表選型與成品確認**：report type/design/options、final HTML、Excel-like view、residual risks。

---

## 工作區結構

每次 run 建立 `wferp-report-runs/<run-id>/`，不得只依賴聊天上下文保存決策。

```text
<run>/
  source/       source-inventory.json  workbook-map.json  extraction-notes.md
  plan/         normalized-report-plan.json  report-plan.md  logic-summary.md
  sql/          query.sql  query.sql.json  sql-review-evidence.json
  data/         raw-preview.json  enriched-preview.json  aggregate-checks.json
  sqlite/       manifest.json  run.sqlite3
  report/       payload/report-payload.json  scaffold/  delivery/report.html
  review/       validators/*.json  final-review.json  repair-log.md
  checkpoints/  01_field_formula.json  02_sql_review.json  03_data_preview.json  04_report_selection.json  05_final_review.json
  db/           db-config.json  db-env.example  schema-inventory.json
```

檔名可以依現有 harness 實作調整，但資訊不可遺失。

---

## LLM Provider 原則

- 預設使用本機 Codex OAuth provider：`--llm-provider codex`。
- 不得以 opencode 作為預設 provider。
- 只有使用者明確指定 `--llm-provider opencode` 時才可使用 opencode。
- 若安全政策阻擋 Codex 將 schema context 傳送到外部服務，必須停止並取得使用者明確批准；不得回退 rule fallback。
- 使用者已在本機核准 `wferp-report` 可使用 Codex OAuth 產生 schema/context SQL 時，後續同一工作環境可直接使用，除非更高優先級政策阻擋。

LLM 主要負責 workbook sheet role 判斷、Excel 公式與報表邏輯理解、manual/helper/format-only 欄位抽象、schema/table/field candidate 推導、source_requirement / report_logic / chart_plan / layout_plan 生成、SQL 生成與根據 validator feedback 做最小 repair、HTML report narrative 與 Excel-like view 結構。

Deterministic code 主要負責 SQL guard、metadata reference validation、DB env / execution guard、SQLite temp workspace、payload schema validation、static HTML validation、evidence persistence。

---

## 硬性質檢協議

Subagent validators 是 gate，不是生成主內容的 helper。主 agent 不得用自己的摘要替代 validator pass。

| 節點 | Validator | 產物 | Gate |
|---|---|---|---|
| Phase 1/2 Understanding | `requirement_understanding_reviewer` | `review/validators/requirement-understanding.json` | Checkpoint 1 前 required |
| Phase 1/2 Excel logic | `excel_logic_reviewer` | `review/validators/excel-logic.json` | 有 Excel 時 required |
| Phase 1/2 Schema mapping | `schema_mapping_reviewer` | `review/validators/schema-mapping.json` | SQL 前 required |
| Phase 3 Chart/layout | `chart_layout_reviewer` | `review/validators/chart-layout.json` | report planning 後 required |
| Phase 4 SQL | `sql_safety_reviewer` | `review/validators/sql-safety.json` | DB execution 前 required |
| Phase 5 DB | `db_execution_reviewer` | `review/validators/db-execution.json` | Data checkpoint 前 required |
| Phase 6 Data | `data_preview_reviewer` | `review/validators/data-preview.json` | Report selection 前 required |
| Phase 6 Enrichment | `sqlite_enrichment_reviewer` | `review/validators/sqlite-enrichment.json` | 有 enrichment 時 required |
| Phase 7 Report options | `report_design_reviewer` | `review/validators/report-design.json` | Scaffold 前 required |
| Phase 8/9 Report content | `report_content_reviewer` | `review/validators/report-content.json` | Delivery 前 required |
| Phase 10 Visual | `visual_taste_reviewer` | `review/validators/visual-taste.json` | Delivery 前 required |
| Phase 10 Technical | `react_technical_reviewer` | `review/validators/react-technical.json` | Delivery 前 required |
| Phase 12 Delivery | `delivery_reviewer` | `review/validators/delivery.json` | Final checkpoint 前 required |

每個 validator 必須輸出 JSON：

```json
{
  "role": "sql_safety_reviewer",
  "status": "pass | fail | warning | blocked",
  "checked_items": [],
  "evidence": [],
  "findings": [],
  "required_fixes": [],
  "residual_risks": []
}
```

鐵律：Validator `fail` 或 `blocked` 時停止該 gate，主 agent 只做最小 repair slice。Repair 後只重跑受影響 validator 與必要下游 validator。Validator `warning` 可做可逆下游準備，但 final delivery 前必須由使用者明確接受 residual risk。

---

## 決策收集鐵律

參考 beautiful-article 的 checkpoint 原則：不得靜默替使用者選擇。可以推薦，但不能直接替使用者決定 chart type、layout mode、report type、manual exceptions 是否忽略、residual risk 是否接受、SQL 是否可執行、DB target 是否可用於正式查詢。

每個 checkpoint 要在 HTML companion 顯示清楚，並由 `wait-confirmation` 等待頁面 POST。主 agent 不得只等聊天訊息或假設使用者已按。若使用者已先按過按鈕，只能在確認檔 mtime 晚於目前 checkpoint 時回收；不得沿用舊 checkpoint 的 confirmation。

`Excel confirmation` 是硬需求：只要有 Excel uploaded files，就必須以 HTML companion 顯示 sheet roles、欄位分類、公式語意、lookup 判斷、manual exceptions 與 unresolved items，並取得 user confirmation 後才能進 SQL。

---

## 各階段文件讀取指南（漸進載入）

| 階段 | 必读 | 按需查 |
|---|---|---|
| Phase 0 Intake | `references/harness.md`、`references/db-config.md` | `README.md` |
| Phase 1 Source / Excel Requirement | `references/excel-intake.md`、`references/field-classification.md` | `references/schema-context.md` |
| Phase 2 Report Planning | `references/report-plan-template.md`、`references/checkpoint-payload-schema.md` | `report_designs/*.md` |
| Phase 3 Field & Formula Checkpoint | `references/checkpoint-payload-schema.md`、`references/dynamic-design-brief.md` | `references/component-policy.md` |
| Phase 4 SQL Review Checkpoint | `references/sql-safety.md`、`references/schema-context.md` | `examples/checkpoint-sql-review.json` |
| Phase 5 Confirmed DB Execution | `references/db-config.md`、`references/sql-safety.md` | `references/e2e-expense-analysis.md` |
| Phase 6 Data Preview Checkpoint | `references/sqlite-enrichment.md`、`references/validators.md` | `references/report-payload-schema.md` |
| Phase 7 Report Selection Checkpoint | `report_designs/index.json`、`report_designs/design.md`、`references/dynamic-design-brief.md` | `report_designs/*.md` |
| Phase 8 Final Report Scaffold | `references/scaffold.md`、`references/report-payload-schema.md` | `references/component-policy.md` |
| Phase 9 Section Build | `references/section-build.md`、`references/component-policy.md`、`references/rawblock-policy.md` | `references/style-replay.md` |
| Phase 10 Final Review | `references/review-checklist.md`、`references/validators.md`、`references/single-html-export.md` | `references/html-output.md` |
| Phase 11 Repair | `references/repair-policy.md` | 失敗 phase 的 reference |
| Phase 12 Delivery | `references/html-output.md`、`references/single-html-export.md` | `references/e2e-expense-analysis.md` |

---

## Phase 0 —— Intake

目標：建立 run、判斷四種輸入組合、記錄 DB/LLM 可用性。

輸入：使用者 prompt、uploaded files、repo root、DB config、LLM provider。

必讀 references：`references/harness.md`、`references/db-config.md`。

執行步驟：建立 `wferp-report-runs/<run-id>/`；產出 `source/source-inventory.json`；判斷是否有 Excel source、Excel template、lookup sheets、support sheets；判斷 report format source 是 `prompt`、`excel_template` 或 `mixed`；記錄 LLM provider，預設 `codex`；記錄 DB config 是否只存在環境變數或 run-scoped config。

產物：`source/source-inventory.json`、`db/db-config.json`、`checkpoints/intake-state.json`。

停止條件：沒有 prompt，也沒有可解析來源；使用者要求查 DB 但 DB target 不明；LLM provider 不可用且沒有使用者批准的替代方案。

使用者 checkpoint：通常不停止；若 DB target、uploaded files 用途或 LLM provider 不明，建立 intake checkpoint 詢問。

validator：無；若來源複雜可啟動 `requirement_understanding_reviewer` 做早期審查。

失敗時 repair slice：只修 run metadata、DB config reference 或 file inventory，不進入 downstream。

---

## Phase 1 —— Source / Excel Requirement

目標：由 LLM 讀懂 prompt 與 Excel，不直接產 SQL。

輸入：`source/source-inventory.json`、使用者 prompt、uploaded files、Excel workbook extracts、WFERP schema inventory。

必讀 references：`references/excel-intake.md`、`references/field-classification.md`、`references/schema-context.md`。

執行步驟：若只有 prompt，推導 source intent、report intent、assumptions 與需確認項；若有 Excel source，判斷 sheet roles，解析欄位、sample values、公式、lookup ranges，分類 DB-backed、formula-backed、lookup-backed、manual-only、format-only、unresolved；若有 Excel template，找出報表標題、區塊、指標、公式、圖表、彙總表，建立 formula dependency graph，抽象 business metric，不逐格複製公式。

產物：`source/workbook-map.json`、`source/extraction-notes.md`、`plan/formula-semantics.json`、`plan/manual-exceptions.json`。

停止條件：Excel 無法讀取；LLM 無法判斷 sheet roles；關鍵欄位無法分類；schema/relationship context 不足以推導 candidate tables。

使用者 checkpoint：不單獨停止；結果要合併到 Phase 3 的 Excel confirmation / field & formula checkpoint。

validator：`requirement_understanding_reviewer`；有 Excel 時加 `excel_logic_reviewer`。

失敗時 repair slice：只修 workbook extraction、sheet role、field classification、formula semantics 或 schema context retrieval。

---

## Phase 2 —— Report Planning

目標：把四種輸入統一成 Normalized Report Plan，並提出 report type/design/options。

輸入：Phase 1 產物、WFERP schema/relationship context、使用者 prompt、report_designs catalog、Excel template semantics。

必讀 references：`references/report-plan-template.md`、`references/checkpoint-payload-schema.md`、`references/dynamic-design-brief.md`。

執行步驟：產生 `plan/normalized-report-plan.json`；產生 `plan/report-plan.md`；產生 `chart_plan` 與 `layout_plan`；如果 report format source 是 prompt，必須提供可選的 report type、chart/layout proposal；如果 report format source 是 Excel template，優先抽象 template logic，模板有圖表時轉成 chart spec，沒有圖表時可建議補圖但不得強制。

產物：`plan/normalized-report-plan.json`、`plan/report-plan.md`、`plan/chart-plan.json`、`plan/layout-plan.json`。

停止條件：重要指標缺少資料 lineage；formula semantics 與 report logic 不一致；chart/layout 無法被使用者理解；manual exceptions 未揭露。

使用者 checkpoint：不單獨停止；Phase 3 顯示規劃結果並取得 user confirmation。

validator：`schema_mapping_reviewer`、`chart_layout_reviewer`；有 Excel 時加 `excel_logic_reviewer`。

失敗時 repair slice：只修 Normalized Report Plan、chart_plan、layout_plan 或 manual exceptions。

---

## Phase 3 —— Field & Formula Checkpoint

目標：在 HTML companion 中讓使用者確認欄位、公式、lookup、manual exceptions、chart/layout 初稿。

輸入：`plan/normalized-report-plan.json`、`plan/formula-semantics.json`、`plan/chart-plan.json`、validator evidence。

必讀 references：`references/checkpoint-payload-schema.md`、`references/dynamic-design-brief.md`、`references/component-policy.md`。

執行步驟：生成 checkpoint payload；用 visual companion 呈現資料來源理解、WFERP schema/table/field readable names、relationships、Excel formula semantics、lookup 判斷、manual exceptions、report type、chart plan、layout plan；啟動 `wait-confirmation` 等待頁面 POST。

產物：`checkpoints/01_field_formula.json`、`review/validators/requirement-understanding.json`、`review/validators/excel-logic.json`、`review/validators/schema-mapping.json`、`review/validators/chart-layout.json`。

停止條件：使用者未確認；任一 required validator fail/blocked；checkpoint 頁面無法顯示；confirmation 檔案不是目前 checkpoint。

使用者 checkpoint：`確認規劃` 進 Phase 4；`要求修正` 回 Phase 1/2 做最小修復。

validator：`requirement_understanding_reviewer`、`schema_mapping_reviewer`、有 Excel 時 `excel_logic_reviewer`、`chart_layout_reviewer`。

失敗時 repair slice：只修被指出的欄位分類、公式語意、schema mapping、chart 或 layout。

---

## Phase 4 —— SQL Review Checkpoint

目標：LLM 根據已確認的 Normalized Report Plan 產生 read-only SQL，並讓使用者確認後才查 DB。

輸入：`plan/normalized-report-plan.json`、WFERP schema/relationship context、DB target metadata、Phase 3 confirmation。

必讀 references：`references/sql-safety.md`、`references/schema-context.md`、`references/checkpoint-payload-schema.md`。

執行步驟：使用 `--llm-provider codex` 產 SQL；SQL 只查 raw DB source fields 或必要 aggregate；Excel/report formula 預設不塞進 DB，除非可由 SQL function/join 等價且有 schema evidence；執行 local SQL safety validation；執行 metadata reference validation；生成 SQL review HTML companion，顯示 SQL、table/field readable names、filters、joins、grouping、aggregates、assumptions 與不進 DB 的 formula/enrichment 欄位。

產物：`sql/query.sql`、`sql/query.sql.json`、`sql/sql-review-evidence.json`、`checkpoints/02_sql_review.json`。

停止條件：SQL safety fail；schema/relationship validator fail；使用者未按 `同意查詢`；SQL 包含非 SELECT 或 unresolved mapping。

使用者 checkpoint：`同意查詢` 進 Phase 5；`調整需求` 回 SQL repair 或 Phase 3。

validator：`sql_safety_reviewer`、`schema_mapping_reviewer`。

失敗時 repair slice：只修 SQL fragment、join condition、field mapping、filter 或 aggregate expression。

---

## Phase 5 —— Confirmed DB Execution

目標：在 SQL confirmed + validators pass 後查 DB，保存可驗證 evidence。

輸入：`sql/query.sql`、`sql/sql-review-evidence.json`、Phase 4 user confirmation、DB config。

必讀 references：`references/db-config.md`、`references/sql-safety.md`、`references/e2e-expense-analysis.md`。

執行步驟：檢查 DB target 是 test / allowed override；執行唯讀查詢；保存 rows、columns、row count、duration、errors；建立 run-scoped SQLite workspace；將 DB raw rows 寫入 SQLite raw table。

產物：`data/raw-preview.json`、`data/query-execution.json`、`sqlite/manifest.json`、`sqlite/run.sqlite3`。

停止條件：SQL 未確認；validator 未 pass；DB_ENV 不是 test 且沒有 allow evidence；DB target 與 SQL table 不一致；SQL 執行失敗。

使用者 checkpoint：不單獨停止；Phase 6 顯示 data preview 並取得 user confirmation。

validator：`db_execution_reviewer`。

失敗時 repair slice：只修 DB config、SQL compatibility、connection guard 或 execution evidence，不重做 report planning。

---

## Phase 6 —— Data Preview Checkpoint

目標：使用者確認 raw data preview、SQLite enrichment、formula/report semantic result 與 aggregate checks。

輸入：`data/raw-preview.json`、`sqlite/run.sqlite3`、`plan/formula-semantics.json`、`plan/normalized-report-plan.json`。

必讀 references：`references/sqlite-enrichment.md`、`references/validators.md`、`references/report-payload-schema.md`。

執行步驟：顯示 raw sample table；執行 SQLite lookup / formula / semantic enrichment；顯示 enriched summary / template semantic result；驗證 row count、aggregates、percentages、exclusions；若有 Excel template，顯示模板語意結果，不顯示逐格公式 dump。

產物：`data/enriched-preview.json`、`data/aggregate-checks.json`、`checkpoints/03_data_preview.json`、`review/validators/data-preview.json`。

停止條件：資料列數、欄位、合計或公式結果不符合 validation targets；lookup miss 未揭露；使用者未確認 data preview。

使用者 checkpoint：`資料正確` 進 Phase 7；`要求修正` 回 SQL / enrichment repair。

validator：`data_preview_reviewer`、有 enrichment 時 `sqlite_enrichment_reviewer`。

失敗時 repair slice：只修 enrichment rule、lookup mapping、aggregate expression、data display 或 SQL filter。

---

## Phase 7 —— Report Selection Checkpoint

目標：讓使用者確認 report type、design、chart/table/layout options，再進 React renderer。

輸入：`plan/normalized-report-plan.json`、`data/enriched-preview.json`、report_designs catalog、使用者偏好。

必讀 references：`report_designs/index.json`、`report_designs/design.md`、`references/dynamic-design-brief.md`。

執行步驟：若使用者已有 prompt 報表格式，將其轉成可確認 options；若沒有，提供數個 report type/design/options，例如財務管控型、經營摘要型、明細追查型、異常稽核型、趨勢簡報型；明確列出 chart type、圖表數量、table 功能、layout 區塊、是否包含分析與建議；生成 visual companion 讓使用者看得到選項，不只列 JSON payload。

產物：`checkpoints/04_report_selection.json`、`plan/selected-report-design.json`、`review/validators/report-design.json`。

停止條件：使用者未選 report type/design/options；chart/table/layout 未確認；選項與資料量或報表目的不相容。

使用者 checkpoint：`確認設計` 進 Phase 8；`調整設計` 回 Phase 2/7 修正。

validator：`report_design_reviewer`、`chart_layout_reviewer`。

失敗時 repair slice：只修 report type、chart plan、table interactions、layout 或 design tokens。

---

## Phase 8 —— Final Report Scaffold

目標：建立 React renderer scaffold 與 report payload contract，準備輸出 single-file HTML。

輸入：`plan/selected-report-design.json`、`data/enriched-preview.json`、`sql/query.sql`、validator evidence。

必讀 references：`references/scaffold.md`、`references/report-payload-schema.md`、`references/component-policy.md`。

執行步驟：建立 React scaffold；寫 structured `report-payload.json`；套用 selected report design；把 SQL evidence、data preview、chart plan、Excel-like view 與 validator evidence 放入 payload；確保 renderer 不連 DB、不執行 SQL、不發 network requests。

產物：`report/payload/report-payload.json`、`report/scaffold/`、`report/scaffold/index.html`。

停止條件：payload schema invalid；缺少 SQL/data/evidence lineage；scaffold 需要 network；renderer 直接讀 credentials 或 DB。

使用者 checkpoint：不單獨停止；Phase 10/12 會做 final review。

validator：`react_technical_reviewer` 可先做 scaffold-level review。

失敗時 repair slice：只修 payload schema、renderer scaffold 或 unsafe dependency。

---

## Phase 9 —— Section Build

目標：逐段生成報告內容、chart/table/component payload、Excel-like view、management narrative，必要時允許 LLM 依需求產生單一 React section 程式碼。

輸入：`report/payload/report-payload.json`、selected design、chart/table/layout plan、data preview。

必讀 references：`references/section-build.md`、`references/component-policy.md`、`references/rawblock-policy.md`、`references/style-replay.md`。

執行步驟：生成 executive summary、KPI cards、chart sections、data tables、Excel-like summary/template view、analysis/findings、recommendations、appendix evidence；使用 semantic components 與受控 Raw layer；若固定元件不足，主 agent / LLM 可產生單一 section TSX，但必須用 `generate-report-section` 寫入、用 `validate-report-section` 驗證；修復時必須用 `repair-report-section`；所有數字必須能追到 SQL / raw data / enriched data / formula semantics。

產物：`report/payload/report-payload.json` 更新版、`report/sections/*.tsx`、`report/scaffold/src` 或等價 component files、`report/section-build-log.json`。

停止條件：section 數字無 lineage；chart/table 與 confirmed design 不一致；section code 未通過 harness safety validation；Raw layer 破壞安全或可攜性；內容遺漏 validation targets。

使用者 checkpoint：不單獨停止；Phase 12 final HTML 給使用者確認。

validator：`report_content_reviewer` 可在重要 section 完成後並行檢查；有 LLM-generated TSX 時，`react_technical_reviewer` 必須檢查 section export、data refs、safe imports、無 network/env/DB/SQL side effect、與 `Report.tsx` linkage。

失敗時 repair slice：只修 failing section、chart/table binding、narrative 或 evidence reference；section 程式碼修復只能替換單一 `report/sections/*.tsx`。

---

## Phase 10 —— Final Review

目標：在交付前由 subagent validators 檢查內容正確、視覺品質、React 技術與 single-file HTML 可用性。

輸入：報告 HTML、report payload、SQL/data/evidence、selected design、validation targets。

必讀 references：`references/review-checklist.md`、`references/validators.md`、`references/single-html-export.md`、`references/html-output.md`。

執行步驟：執行 report content review；執行 visual/taste review，檢查版面、字級、圖表、表格、RWD、overlap、中文顯示；執行 React technical review，檢查 hydration/build、network requests = 0、不得連 DB、不得執行 SQL；執行 delivery review，檢查檔案與 evidence 完整。

產物：`review/validators/report-content.json`、`review/validators/visual-taste.json`、`review/validators/react-technical.json`、`review/validators/delivery.json`、`review/final-review.json`。

停止條件：任一 required validator fail/blocked；HTML 無法離線開啟；數字無法追溯；visual review 發現明顯排版錯誤。

使用者 checkpoint：不單獨停止；若 validators pass，進 Phase 12 final checkpoint；若 fail，進 Phase 11。

validator：`report_content_reviewer`、`visual_taste_reviewer`、`react_technical_reviewer`、`delivery_reviewer`。

失敗時 repair slice：只修 validator 指出的最小 component、section、style、payload 或 evidence 缺口。

---

## Phase 11 —— Repair

目標：對 validator 或使用者指出的問題做最小垂直切片修復，不大範圍重做。

輸入：failed validator JSON、使用者修正要求、repair log、受影響 phase 產物。

必讀 references：`references/repair-policy.md` 與失敗 phase 的 reference。

執行步驟：分類失敗類型；只修改最小必要 artifact；重跑受影響 validator 與必要 downstream validator；更新 `review/repair-log.md`；若同一問題三次 repair 仍失敗，標記 blocked 並回報使用者決策點。

產物：`review/repair-log.md`、更新後 artifact、更新後 validators。

停止條件：修復需要改變使用者已確認的決策；同一問題三次失敗；缺少可驗證資料或 DB evidence。

使用者 checkpoint：若修復改變已確認的需求、SQL、資料結果或視覺設計，回到對應 checkpoint 重新取得 user confirmation。

validator：重跑與失敗項目相關的 validator，不重跑無關 validator。

失敗時 repair slice：再縮小到單一欄位、單一公式、單一 SQL fragment、單一 component 或單一 evidence file。

---

## Phase 12 —— Delivery

目標：交付最終 single-file HTML 報告與完整 evidence packet，並讓使用者最後確認。

輸入：validated HTML、report payload、SQL/data/evidence、final review、SQLite retention choice。

必讀 references：`references/html-output.md`、`references/single-html-export.md`、`references/e2e-expense-analysis.md`。

執行步驟：生成 final checkpoint HTML companion；顯示 final HTML report link / preview、Excel-like view、SQL evidence、raw/enriched row counts、chart/layout summary、validator pass/fail/warning、residual risks、SQLite temp table retention choice；取得 user confirmation；保存 delivery manifest。

產物：`report/delivery/report.html`、`report/payload/report-payload.json`、`sql/query.sql`、`data/raw-preview.json`、`data/enriched-preview.json`、`plan/normalized-report-plan.json`、`review/final-review.json`、SQLite retention evidence。

停止條件：使用者未接受；delivery evidence 缺失；single-file HTML 不是離線可開；residual risks 未被接受。

使用者 checkpoint：`接受` / `完成` 代表 delivery；`要求修正` 回 Phase 11；`保留 SQLite` / `刪除 SQLite` 保存 retention decision。

validator：`delivery_reviewer` 必須 pass；有 warning 時需使用者接受 residual risks。

失敗時 repair slice：只補缺失 delivery file、修 final HTML、補 evidence、或回 Phase 11 修具體問題。

---

## Repair Policy 摘要

Repair 必須是最小垂直切片，不得大範圍重做。

| 失敗類型 | 最小修復範圍 |
|---|---|
| source understanding wrong | 只修 sheet role / source requirement |
| formula semantics wrong | 只修 formula/report logic |
| chart/layout wrong | 只修 chart_plan / layout_plan |
| SQL invalid | 只修 SQL fragment 或 mapping |
| DB execution failed | 只修 DB config 或 SQL compatibility |
| aggregate mismatch | 只修 enrichment / aggregate expression |
| visual issue | 只修 failing component / section |
| delivery missing evidence | 只補缺失 evidence |

修復後只重跑相關 validator 與必要下游 validator。

---

## 預設策略

- 預設 repo root：`/home/timmypai/.codex/worktrees/5f5b/wferp`。
- 預設 LLM provider：`codex`。
- 預設輸出：single-file HTML + Excel-like summary/template view。
- 預設報表語氣：management-first，附 technical evidence。
- Prompt report format 時，必須提供 chart/layout proposal。
- Excel template report format 時，優先解析 template logic；不逐格複製公式。
- Excel 中 manual/helper/format-only 欄位預設簡化或移除，但需在 Phase 3 顯示原因。
- SQL 預設 raw-source-first；只有可證明等價且有 schema evidence 的公式才下推 SQL。
- DB execution 預設只允許 test DB；production 需明確 allow evidence。
- 複雜報表可使用 LLM-generated section TSX，但只能經 `generate-report-section` / `repair-report-section` 寫入 run-scoped section，且每次都要跑 `validate-report-section`。

---

## 成功標準

- 四種輸入組合都能收斂成 Normalized Report Plan。
- 使用者通過主要 checkpoint，不被迫理解所有技術細節。
- SQL 是 confirmed read-only SQL。
- DB execution evidence 包含 rows、columns、row count、duration、aggregates。
- Excel formula/report logic 有 semantic lineage。
- Chart/layout 在報告生成前已由使用者確認。
- React renderer 產出的 HTML report 可離線開啟。
- LLM-generated section code 已通過 section validation、React technical review 與 report content review。
- Excel-like view 能對照報表邏輯與資料結果。
- Required validator evidence 全部 pass；warning/residual risks 已由使用者接受。
- 所有重要數字能追溯到 SQL raw data、SQLite enrichment 或 formula semantics。

---

## 相關資源

- `manifest.json`
- `README.md`
- `references/harness.md`
- `references/excel-intake.md`
- `references/field-classification.md`
- `references/schema-context.md`
- `references/sql-safety.md`
- `references/sqlite-enrichment.md`
- `references/checkpoint-payload-schema.md`
- `references/report-payload-schema.md`
- `references/validators.md`
- `references/review-checklist.md`
- `references/repair-policy.md`
- `references/html-output.md`
- `references/single-html-export.md`
- `report_designs/index.json`
- `assets/scaffold-template/`
- `scripts/validate-skill.sh`
- `scripts/scaffold-report.sh`

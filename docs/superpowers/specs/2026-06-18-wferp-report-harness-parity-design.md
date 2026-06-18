# WFERP Report Harness Parity Design

## 背景原則

`wferp-report` 不應只是 SQL generator 或一組 React 頁面。它必須是一個完整 harness：從使用者需求、Excel 欄位與公式、WFERP schema/relationship、SQL 安全驗證、DB 查詢確認、資料預覽、報表格式選擇、React 報告生成、validator evidence 到最終交付，都由 skill 的 phase flow 明確驅動。

此設計對齊 `beautiful-article` 的做法：`SKILL.md` 是 harness 操作手冊，執行 skill 就是執行 harness。差異是 `beautiful-article` 的核心產物是單檔 HTML 文章；`wferp-report` 的核心產物是可驗證、可追溯、可互動確認的 WFERP 管理報表。

使用者明確要求此設計不得以階段化名義降低功能範圍。可以分階段交付，但每一階段都必須是產品級垂直切片，有明確驗收標準與 roadmap。

## 邊界

- 只產生唯讀 `SELECT` SQL。
- 不產生或執行 `INSERT`、`UPDATE`、`DELETE`、`DROP`、`ALTER`、`EXEC`、`MERGE`、`TRUNCATE`、`SELECT INTO`、multi statement、SQL comments、`xp_`。
- 瀏覽器端不連 DB、不執行 SQL、不存取 credentials。
- 未經使用者在 checkpoint companion 或 chat fallback 確認，不得查詢 DB。
- 費用分析只作為 E2E fixture 測試 skill 功能，不得成為產品 code 的特殊 SQL 分支。
- Final report 可使用 sandboxed React `RawBlock`，但 `RawBlock` 不得 fetch、連 DB、執行 SQL、讀寫 browser storage、改寫 global state 或注入 `<script>`。
- 舊 `index.html` / `HTML/*.html` 靜態文件不作為新報表 renderer；只保留 WFERP schema metadata 與 relationship 用於 SQL/report generation。

## 全章節 Mapping

`wferp-report/SKILL.md` 必須用中文撰寫，並與 `beautiful-article/SKILL.md` 做全章節對應。

| beautiful-article 章節 | wferp-report 對應章節 |
|---|---|
| 背景原則 | 背景原則：報表不是 SQL 片段，而是可驗證管理報表 harness |
| 邊界 | 邊界：唯讀 SELECT、DB execution gate、無費用專用產品分支 |
| 工作流總覽 | Phase 0-12 報表 harness 總覽 |
| 硬性質檢協議 | Excel / SQL / Schema / Data / Report / Visual / Technical validators |
| 各階段文件讀取指南 | 漸進揭露指南：每 phase 只讀必要 references |
| Phase 0 Intake | 需求 intake：prompt、上傳檔案、報表目標 |
| Phase 1 Source -> Markdown | Source / Excel -> requirement model |
| Phase 2 Editorial Planning | Report planning：schema mapping、SQL plan、data validation plan、report outline |
| Phase 3 Plan Checkpoint | Checkpoint 1：欄位與公式確認 |
| Phase 4 First Spread | Checkpoint App first usable slice：SQL review + data preview UI baseline |
| Checkpoint 2 First Spread | Checkpoint 2：SQL review，必須停 |
| Phase 5 Full Article Build | Final report build：一節一檔 |
| Phase 6 Final Review | 多視角終審 |
| Phase 7 Repair | 最小垂直切片 repair |
| Checkpoint 3 Final | 最終交付確認 |
| Phase 8 Delivery | Delivery：checkpoint evidence + single-file HTML report |
| 預設策略 | DB safety、run root、雙視圖、report design defaults |
| 成功標準 | SQL 安全、資料驗收、報表可讀性、validator evidence、E2E passing |
| 相關資源 | references/scripts/designs/components 的何時讀指南 |

## 目標 Skill 結構

Local skill 位於 repo 外：

```text
/home/timmypai/.codex/skills/wferp-report/
  SKILL.md
  manifest.json
  README.md
  references/
    harness.md
    db-config.md
    excel-intake.md
    schema-context.md
    sql-safety.md
    checkpoint-payload-schema.md
    report-payload-schema.md
    component-policy.md
    rawblock-policy.md
    scaffold.md
    section-build.md
    report-plan-template.md
    review-checklist.md
    repair-policy.md
    html-output.md
    validators.md
    e2e-expense-analysis.md
  scripts/
    scaffold-report.sh
    validate-skill.sh
    print-expense-fixture-sql.sh
    run-expense-sqlite-e2e.sh
    run-expense-postgres-e2e.sh
  assets/
    scaffold-template/
      package.json
      vite.config.ts
      tsconfig.json
      index.html
      report/
        Report.tsx
        sections/
        raw-blocks/
        components/
        payload/
      source/
      plan/
      checkpoints/
      review/
  report_designs/
    index.json
    design.md
    financial-control.md
    executive-summary.md
    detail-ledger.md
    exception-audit.md
    operations-review.md
    trend-briefing.md
  examples/
    checkpoint-excel-confirmation.json
    checkpoint-sql-review.json
    checkpoint-data-preview.json
    report-selection.json
    final-report-payload.json
```

實作 runtime 保留在 repository 內（`skill_scripts/`、`report_renderer/`、`scripts/`）。Local skill 的 `scripts/` 只作為穩定 wrapper，呼叫 repo runtime 指令，對齊 `beautiful-article` 以 skill assets/scripts 定義入口與模板的作法。

## 工作流總覽

```text
Phase 0  Intake
Phase 1  Source / Excel Requirement
Phase 2  Report Planning
Phase 3  Field & Formula Checkpoint
Phase 4  SQL Review Checkpoint
Phase 5  Confirmed DB Execution
Phase 6  Data Preview Checkpoint
Phase 7  Report Selection Checkpoint
Phase 8  Final Report Scaffold
Phase 9  Section Build
Phase 10 Final Review
Phase 11 Repair
Phase 12 Delivery
```

每個 phase 在 `SKILL.md` 中必須使用固定格式：

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

## 漸進揭露

Agent 不得一次讀完整個 skill reference set。每個 phase 只讀必要文件。

| Phase | 必读 | 按需 |
|---|---|---|
| Intake | `references/harness.md` | `references/db-config.md` |
| Excel intake | `references/excel-intake.md` | examples/sample workbook |
| Schema/SQL planning | `references/schema-context.md`, `references/sql-safety.md` | relationship graph docs |
| Checkpoint UI | `references/checkpoint-payload-schema.md` | `references/component-policy.md` |
| Report selection | `report_designs/index.json`, selected design profile | `report_designs/design.md` |
| Final scaffold | `references/scaffold.md`, `references/component-policy.md`, `references/section-build.md` | `references/rawblock-policy.md` |
| Review | `references/review-checklist.md`, `references/validators.md` | specific validator contract |
| Repair | `references/repair-policy.md` | failed section/component/payload schema |
| Delivery | `references/html-output.md` | selected export policy |

長流程必須依賴 run files，而不是聊天記憶。所有決策持久化於：

```text
source/
plan/
checkpoints/
review/
report/payload/
```

## Checkpoint Companion Runtime

Checkpoint UI 必須像瀏覽器 companion，而不是靜態 HTML 成品。效果需等同 brainstorming companion：Codex 開啟本地頁面，使用者在頁面內審閱、選擇、確認，harness 收到確認結果後才繼續。

```text
Codex starts harness
  -> create run state
  -> start local checkpoint companion server
  -> open local checkpoint page
  -> user confirms/modifies/selects in browser
  -> browser POSTs action to harness
  -> harness writes state + audit
  -> Codex detects confirmation
  -> next phase
```

本地 URL 形狀：

```text
http://127.0.0.1:<port>/runs/<run-id>/checkpoints/current
```

確認 API：

```http
POST /api/runs/<run-id>/checkpoints/<checkpoint-id>/confirm
```

請求 payload：

```json
{
  "action": "同意查詢",
  "checkpointId": "sql_review",
  "comment": "條件正確，可以查詢",
  "selectedOptions": {
    "view": "management"
  }
}
```

狀態與 audit files：

```text
<run-root>/<run-id>/
  state.json
  checkpoints/
    02-sql-review.json
    02-sql-review.confirmation.json
  audit/
    events.jsonl
```

硬性 gates：

| Checkpoint | 未確認前禁止 |
|---|---|
| 欄位與公式確認 | 禁止產 SQL |
| SQL review | 禁止連 DB |
| Data preview | 禁止產 final report |
| Report selection | 禁止 scaffold report |
| Draft review | 禁止 final review |
| Final review | 禁止 delivery |

若本地 browser/server 不可用，harness 才使用 chat fallback。fallback 仍寫入同一種 confirmation file，只是輸入通道不同。

## Renderer Architecture

採用已確認的 hybrid 設計：

- Checkpoint / SQL / data preview: fixed React App + JSON payload.
- Final report: per-run scaffold workspace outside repo by default.

預設 run root：

```text
/home/timmypai/.codex/wferp-report-runs/<run-id>/
```

覆寫設定：

```text
WFERP_REPORT_RUN_ROOT=/custom/path
```

Checkpoint App 必須是產品級介面，不是 debug page。它提供：

- management view by default
- technical details tab
- progress navigation
- durable action state
- validator evidence
- stale checkpoint detection
- reload-safe recovery
- clear error states

## Checkpoint Component Catalog

Checkpoint app 使用固定 React components 搭配動態 payload。資料不得寫死在 component 內。

必要 components：

```text
CheckpointShell
ManagementView
TechnicalView
RequirementSummary
FieldFormulaReview
SqlReviewPanel
DataPreviewPanel
AggregateCheckPanel
ReportSelectionPanel
ValidatorEvidencePanel
ActionBar
```

Management view 面向主管與財務使用者：

- request summary
- field/formula confirmation
- data preview
- aggregate checks
- exceptions/risks
- next-step actions

Technical view 面向 ERP、IT、DBA 使用者：

- generated SQL
- schema/table/field mapping
- relationship path
- SQL safety checks
- execution environment
- validator evidence

## Final Report Component Catalog

Final report scaffold 遵守嚴格 component protocol。`Report.tsx` 只負責組裝 sections；內容必須是一個 section 一個檔案。

允許使用的 components：

```text
ReportShell
ReportHero
ReportSection
KpiGrid
DataTable
ChartBlock
InsightBlock
RecommendationList
EvidencePanel
FormulaLineagePanel
SqlSafetyPanel
ValidatorEvidencePanel
RawBlock
```

規則：

- No arbitrary bare HTML/CSS in sections.
- Use approved semantic components for report content.
- `RawBlock` 只允許用於特殊互動或自訂視覺化。
- `RawBlock` 必須宣告 `id`、`title`、`purpose`、`dataDependencies`、`riskLevel`。
- `RawBlock` 只能接收 readonly props。
- `RawBlock` 不得 fetch、連 DB、執行 SQL、寫入 browser storage、改寫 globals、注入 scripts，或隱藏 validator failures。

## ChartBlock Product Requirements

Chart support 必須是產品級並可分階段交付。Product Phase 1 必須支援管理報表所需 chart types：

1. bar chart
2. stacked bar chart
3. line chart
4. area chart
5. pie/donut chart
6. combo chart

Roadmap chart types：

- heatmap
- waterfall
- scatter
- treemap
- box plot
- bullet chart
- gauge card
- sparkline

共同能力：

- title/subtitle
- x/y encoding
- series/color encoding
- sort
- Top N
- number/percent/date formatting
- tooltip
- legend
- empty/error state
- category cardinality guard
- chart suitability validation
- accessibility labels
- responsive desktop/mobile layout

Data visualization review 必須驗證 chart choice 支援管理決策，且不會誤導使用者。

## DataTable Product Requirements

Table support 必須是產品級，定位接近管理報表表格，而不是靜態 preview。

Product Phase 1 table capabilities：

1. column sorting
2. column filtering
3. text contains filter
4. number range filter
5. date range filter
6. category multi-select
7. show/hide columns
8. frozen key columns
9. summary rows
10. group subtotals
11. conditional formatting
12. number/date/percent/currency formatting
13. full-table search
14. CSV export
15. pagination or virtual scroll for large result sets

Roadmap capabilities：

- pivot-like grouping
- drill-down row expansion
- copy selected cells
- saved views
- XLSX export with styles/formulas
- cross-filter with charts
- pinned summary panel

這不是 spreadsheet editor，而是用於審閱、確認、管理決策的產品級報表表格。

## Final Report Scaffold Workspace

每份 final report 都有獨立 per-run workspace：

```text
<run-root>/<run-id>/
  source/
    source.md
    extraction-notes.md
  plan/
    report-plan.md
  checkpoints/
    01-field-formula.json
    02-sql-review.json
    03-data-preview.json
    04-report-selection.json
  review/
    final-review.md
    repair-log.md
  report/
    Report.tsx
    sections/
      01-executive-summary.tsx
      02-kpi-overview.tsx
      03-data-table.tsx
      04-analysis.tsx
      05-recommendations.tsx
    raw-blocks/
      NN-*.tsx
    payload/
      approved-query-result.json
      report-context.json
```

一個 section 等於一個檔案。`Report.tsx` 只作為 assembler。這讓 parallel subagents 與精準 validation 可以成立。

## Report Design Catalog

既有 design profiles 需正式化為 catalog：

```text
report_designs/index.json
report_designs/design.md
report_designs/financial-control.md
report_designs/executive-summary.md
report_designs/detail-ledger.md
report_designs/exception-audit.md
report_designs/operations-review.md
report_designs/trend-briefing.md
```

每個 design profile 必須定義：

- `id`
- `label`
- `best_for`
- `required_sections`
- `default_components`
- `chart_policy`
- `table_policy`
- `kpi_policy`
- `tone`
- `layout_density`
- `validator_focus`

`report_designs/index.json` 扮演與 beautiful-article `theme-profiles/index.json` 相同的角色：agent 先讀 index 選候選 profile，再讀被選中的 profile。

## Frontend Quality And Taste Workflow

設計與驗證階段需使用已安裝的 frontend/design skills：

- `build-web-apps:frontend-app-builder`
- `web-design-engineer`
- `build-web-data-visualization:data-visualization`
- `build-web-apps:react-best-practices`
- `build-web-apps:shadcn` when a shadcn component system is adopted

若未來 session 已安裝 `ui-ux-pro-max` 或 `taste` skill，需納入 UX/taste review。若不可用，使用上列 frontend/design skills 作為 fallback。

品質要求：

- checkpoint companion must be understandable to non-technical users
- SQL is available in technical view, not the default focal point
- mobile/desktop responsive layouts
- no text overlap or clipping
- no decorative one-note UI
- chart/table choices must support management decisions
- React components must be payload-driven and side-effect free in the browser

Final review 必須包含 UX Reviewer、Visual/Taste Reviewer、Data Visualization Reviewer、React/Technical Reviewer。

## Validator Protocol

Validators：

- Source/Requirement Reviewer
- Excel Formula Reviewer
- SQL Safety Reviewer
- Schema Relationship Reviewer
- Data Preview Reviewer
- Report Content Reviewer
- Visual/Taste Reviewer
- Data Visualization Reviewer
- React/Technical Reviewer

Validator outputs 必須包含：

```json
{
  "role": "sql_safety_reviewer",
  "status": "pass",
  "evidence": [],
  "findings": [],
  "requiredFixes": [],
  "residualRisks": []
}
```

硬性規則：validator failures 必須 repair 後才能回報成功，除非使用者在 checkpoint 明確接受 residual risk。

## Repair Policy

Repair 必須使用能解決 failure 的最小 vertical slice。

禁止：

- 因單一 section failure 重寫整個 report workspace
- 為了掩蓋單一 broken phase 而重跑整個 harness
- 除非同一 failure 必然需要同時修改三者，否則不得同時改 SQL、report text、RawBlock
- 因 visual issue 修改 data logic
- 未回到 field/formula checkpoint 就修改已確認的 Excel fields

最小 vertical slices：

| Failure | Minimal repair slice |
|---|---|
| Excel formula parse wrong | parser + confirmation payload + formula validator |
| field mapping wrong | schema mapping + affected SQL + SQL checkpoint |
| relationship wrong | relationship path + join SQL + schema validator |
| SQL safety fail | SQL builder/guard + SQL checkpoint only |
| aggregate mismatch | query/filter/data preview path |
| report section content wrong | 單一 `report/sections/NN-*.tsx` + section validator |
| RawBlock violation | 單一 `raw-blocks/NN-*.tsx` + RawBlock validator |
| final HTML build fail | scaffold/build config + affected component |
| visual issue | affected section/component styling/token usage only |

若發生 repair，需 append：

```text
review/repair-log.md
```

格式：

```text
## <date> <checkpoint/reviewer>

Failure:
Scope:
Minimal vertical slice:
Files changed:
Validation rerun:
Residual risk:
```

## Success Standards

- `SKILL.md` 是中文 harness manual，不是 command index。
- 所有 beautiful-article chapters 都有明確 wferp-report mapping。
- Checkpoint companion 可在本地開啟、接收使用者確認、寫入可 audit 的 state。
- Management users 不需要閱讀 SQL 也能完成 checkpoints。
- IT/DBA users 可檢視 SQL、schema mapping、validator evidence。
- Final report scaffold 使用嚴格 component protocol、一個 section 一個檔案、sandboxed RawBlock。
- ChartBlock 與 DataTable 達到產品級管理報表需求。
- Report design catalog 具備 index/profile metadata。
- 所有 phase decisions 都持久化於 run files。
- Repair 使用 minimal vertical slices。
- SQLite-first E2E 與 PostgreSQL formal MSSQL simulation E2E 通過量化 assertions。
- React tests/build 與 skill structure validator 通過。

## Implementation Planning Notes

Implementation 應拆成產品級 phases：

1. Harness parity docs 與 local skill structure。
2. Checkpoint companion runtime 與 confirmation API。
3. Checkpoint component catalog 與 payload schemas。
4. Final report scaffold template 與 component protocol。
5. ChartBlock/DataTable product components。
6. Report design catalog/index 與 selected design enforcement。
7. Validator 與 repair-policy enforcement。
8. End-to-end tests，包含 SQLite-first 與 PostgreSQL formal simulation。

每個 phase 都必須是 production-ready vertical slice，並有自己的 tests 與 acceptance criteria。

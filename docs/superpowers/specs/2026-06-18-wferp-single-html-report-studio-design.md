# WFERP Single HTML Report Studio Design

## 背景

目前 `wferp-report` 已完成 harness、checkpoint companion、Excel intake、SQL review、data preview、report design catalog、React report scaffold、validator gate、SQLite/PostgreSQL 費用分析 E2E 與 local skill validation。

下一階段目標不是再增加一個固定報表模板，而是把交付升級成類似 `beautiful-article` 的動態設計體驗，同時維持 WFERP 報表需要的資料正確、安全邊界與稽核證據。

本設計定義 **WFERP Single HTML Report Studio**：

- 產出完全自含的 `report.html`。
- 同時產出完整 evidence packet。
- 使用 catalog 作為 guardrail，而不是固定模板。
- 由 agent 依當次 prompt、Excel、schema、data preview 動態產生報表設計。
- 使用者透過文字摘要與 semi-real HTML visual checkpoint 確認圖表、layout、表格與 evidence 呈現。
- 支援未來以既有報告樣式重新套用新 prompt / 新查詢條件的 Style Replay。

## 目標

1. 產出可離線開啟的 single-file HTML report。
2. HTML 內不可連 DB、不可執行 SQL、不可保存 credentials、不可依賴 CDN。
3. 同時輸出完整 evidence packet，保留 SQL、rows、validator、manifest、repair log。
4. 支援完整互動報表工作台能力：cross-filter、drilldown、group by、chart selection、table search/sort/pagination、evidence drawer。
5. 依使用者當下需求動態生成 layout、chart、section 與視覺方向。
6. 使用者可要求多放圖、換圖表類型、調整 layout、改表格或 evidence 呈現方式。
7. 六個 catalog profile 仍存在，但角色改為 guardrail。
8. 實作真 E2E 驗收：SQLite、Docker PostgreSQL、single HTML、Playwright、visual/interaction/data validators。
9. 支援 Style Replay：用舊報告樣式重新生成新條件的新 single HTML。

## 非目標

- 不讓 single HTML 連線 DB。
- 不讓 single HTML 動態產生或執行 SQL。
- 不把舊 HTML 改造成可重新查詢資料庫的 BI 服務。
- 不用 remote CDN、remote font 或外部 API。
- 不用 fake、mock、smoke 取代 E2E。
- 不把 catalog 固定為不可調整的模板。

## 核心架構

### 1. Report Package

`report-package.json` 是 HTML 與 evidence packet 的唯一資料來源。

來源：

- confirmed SQL
- DB execution result
- data preview
- aggregate checks
- selected catalog guardrail
- confirmed dynamic design brief
- report draft sections
- validator results
- accepted residual risks

責任：

- 固定資料真相。
- 提供 HTML 所需的 KPI、chart datasets、table datasets、drilldown datasets。
- 保存 package hash 與 source evidence references。
- 避免 final HTML 與 evidence packet 使用不同資料。

### 2. Catalog Guardrail

六個 catalog 仍保留：

- `financial-control`
- `executive-summary`
- `detail-ledger`
- `exception-audit`
- `operations-review`
- `trend-briefing`

但 catalog 不再代表固定畫面。它只提供：

- report intent classification
- default validator focus
- recommended chart/table/layout policies
- visual density guardrail
- evidence visibility policy
- risk and repair expectations

實際畫面由 dynamic design brief 決定。

### 3. Dynamic Design Brief

每次報表生成前，agent 產出 `report-design-brief.json`。

最小欄位：

```json
{
  "report_intent": "費用分析",
  "catalog_guardrail": "financial-control",
  "target_audience": "部門主管與財務主管",
  "layout_recipe": {
    "mode": "kpi-first-dashboard",
    "sections": ["主管摘要", "費用差異", "部門排行", "明細 drilldown", "建議與風險"]
  },
  "chart_recipe": [
    {"id": "budget_vs_actual", "type": "combo", "purpose": "比較實際與預算"},
    {"id": "department_mix", "type": "stacked-bar", "purpose": "呈現部門費用組成"}
  ],
  "table_recipe": [
    {"id": "detail_drilldown", "type": "interactive-detail", "features": ["filter", "sort", "drilldown"]}
  ],
  "interaction_recipe": {
    "cross_filter": true,
    "drilldown": true,
    "evidence_drawer": "collapsed"
  },
  "visual_direction": {
    "density": "dense",
    "tone": "管理控制",
    "emphasis": ["variance", "exception", "traceability"]
  },
  "embedded_data_policy": {
    "mode": "smart-tiered",
    "preview_rows": 200,
    "full_rows_threshold": 5000
  }
}
```

### 4. Text Checkpoint

Agent 先用文字摘要說明設計：

- 報表目的
- catalog guardrail
- layout
- chart 數量與用途
- table/drilldown 方式
- evidence 呈現方式
- HTML 內嵌資料範圍
- full evidence packet 範圍
- known risks

使用者可要求：

- 多放圖
- 刪圖
- 改 chart type
- 改 section 順序
- 改 layout 模式
- 改視覺密度
- 改 evidence 常駐或抽屜

### 5. Semi-real HTML Visual Checkpoint

同時產出一個 semi-real HTML 草圖。

特性：

- 使用真欄位名稱。
- 使用真 aggregate 數字。
- 使用真 section title。
- 接近 final 的 chart/table/card layout。
- 顯示 filter bar、drilldown drawer、evidence drawer placeholder。
- 不在此階段輸出 final single HTML。
- 不嵌入完整 rows。

目的：

- 讓一般使用者看得懂報表將如何呈現。
- 在 final export 前調整 layout、圖表、表格與互動。

### 6. Confirmed Design Brief

使用者確認後，`report-design-brief.json` 變成 immutable input。

後續 validator 必須檢查：

- final HTML 是否符合 confirmed brief。
- chart/table/section 是否沒有靜默偏離。
- 若資料結構不支援原設計，是否有 design adjustment checkpoint。

## Single HTML Export Pipeline

### Step 1. Build Report Package

從 harness run 建立 `report-package.json`。

必要檢查：

- final delivery gate allowed。
- SQL review 已確認。
- data preview 已確認。
- report selection / design brief 已確認。
- validator results 存在。
- no credentials。

### Step 2. Package Validation Gate

Export 前驗證：

- SQL 是 read-only SELECT。
- 無 blocked keywords。
- data rows / aggregates / exclusions 與 validator evidence 對得上。
- selected catalog 存在於 `report_designs/index.json`。
- confirmed design brief 存在。
- delivery gate allowed。
- payload size 未超過設定上限。
- HTML embedded data policy 合理。

### Step 3. Compile Dynamic Template

Template compiler 讀取：

- `report-package.json`
- `report-design-brief.json`
- catalog guardrail

輸出：

- layout tree
- component tree
- chart/table/drilldown recipes
- visual theme tokens
- evidence drawer recipe

### Step 4. Bundle Offline Runtime

產生單檔 runtime：

- inline CSS
- inline JS
- inline report renderer
- inline offline interaction engine
- inline compressed package
- inline bootstrap loader
- inline hash metadata

禁止：

- external script
- external stylesheet
- remote font
- network fetch
- DB endpoint
- SQL execution API

### Step 5. Export Delivery Artifacts

輸出：

```text
delivery/
  report.html
  evidence/
    query.sql
    report-package.json
    report-style-capsule.json
    execution-result.json
    query-result.csv
    validator-results.json
    report-design-brief.json
    delivery-manifest.json
    repair-log.md
```

### Step 6. HTML Self-validation

用 Playwright 開 `report.html`。

驗證：

- 無 console error。
- network requests = 0。
- title / KPI / chart / table / evidence summary 可見。
- chart 不是空白。
- table 可互動。
- filter/drilldown 會改變結果。
- evidence drawer 可開啟。
- HTML 不含 credentials / connection string。
- manifest hash 對得上。
- KPI/chart/table 數字等於 package。

## Embedded Data Policy

採 smart-tiered policy。

HTML 內嵌：

- KPI
- aggregate checks
- chart datasets
- drilldown summary
- preview rows
- selected rows
- validator summary
- evidence index

Evidence packet 保留：

- full rows
- full SQL
- full execution result
- full validator result
- full repair log

例外：

- 若 catalog 是 `detail-ledger`，或 row count / compressed size 低於門檻，可嵌入 full rows。
- 預設門檻建議：`<= 5000 rows` 或 `<= 5 MB compressed payload`。
- 超過門檻時，HTML 改用 summary-plus-preview mode，並在 evidence drawer 說明完整明細在 packet。

## Offline Interaction Engine

HTML 內支援：

- cross-filter
- drilldown
- group by
- local summary
- chart selection
- table filter / sort / pagination
- column visibility
- evidence drawer
- export visible table CSV

互動只作用於 embedded package data。

不可：

- 連 DB
- 產 SQL
- 執行 SQL
- fetch remote URL
- 保存 credentials
- 修改 source evidence

## Style Replay / Design Capsule

每次 delivery 產生 `report-style-capsule.json`。

內容：

- catalog guardrail
- confirmed design brief
- layout recipe
- chart recipe
- table/drilldown recipe
- visual theme tokens
- component composition
- evidence display mode
- interaction behavior
- export settings
- style fingerprint
- style version

Style capsule 會：

- embedded 到 `report.html`
- 保存於 evidence packet
- 記錄在 `delivery-manifest.json`

### Replay 流程

使用者可說：

> 用上次費用分析報告的樣式，改查 2027 Q1 行政部費用。

Harness 流程：

1. 讀取舊報告的 `report-style-capsule.json`。
2. 解析新 prompt / 新查詢條件。
3. 重新做 schema mapping / SQL generation / SQL safety。
4. 重新查 DB。
5. 重新 build report package。
6. 沿用 capsule 的 layout / chart / visual style。
7. 依新資料微調 chart scale / table rows / KPI。
8. 產出新的 single HTML。
9. 產出新的 evidence packet。

舊 HTML 不會自己查 DB，也不會執行新 SQL。舊報告只提供樣式與設計 recipe。

### Replay 例外規則

若新資料不適合原圖表，例如原報告是趨勢圖但新資料沒有期間欄位：

- Agent 可提出替代圖表。
- 必須開 design adjustment checkpoint。
- 使用者確認後才可替換。
- 不得硬套原圖。
- 不得靜默更改。

## Validator 設計

### Data Correctness Validators

驗證：

- SQL safety
- WFERP schema mapping
- relationship mapping
- Excel formula lineage
- row count
- columns
- aggregates
- exclusions
- ratios / percentages
- package hash
- evidence consistency

### Single HTML Portability Validators

驗證：

- HTML 可直接開啟。
- network requests = 0。
- 無 CDN / remote font。
- 無 DB connection string。
- 無 credentials。
- 無 SQL execution endpoint。
- inline payload 可解壓。
- manifest hash 可驗證。
- 離線互動可用。
- 檔案大小在上限內。

### Visual / Interaction Validators

用 Playwright 驗證：

- desktop / tablet / mobile 不破版。
- 標題、KPI、圖表、表格、evidence drawer 可見。
- 文字不重疊。
- 圖表不是空白。
- table 可排序 / 搜尋 / pagination。
- cross-filter / drilldown 可改變 chart/table。
- evidence drawer 可開啟。
- final HTML 符合 confirmed design brief。

### Style Replay Validators

驗證：

- 新報告沿用 style fingerprint。
- 新 SQL 依新 prompt 重新產生。
- 新資料沒有沿用舊 rows。
- 新 KPI/chart/table 來自新 execution result。
- layout 符合 capsule。
- 不相容圖表有 design adjustment checkpoint。
- evidence packet 是新的一份。

## E2E 驗收

### Single HTML Expense Analysis E2E

流程：

1. seed SQLite。
2. seed Docker PostgreSQL。
3. execute SQL。
4. build report package。
5. generate dynamic design brief。
6. render semi-real visual checkpoint。
7. confirm brief。
8. export single HTML。
9. export evidence packet。
10. open HTML with Playwright。
11. assert data, visual, interaction, offline safety。

量化標準：

```text
row_count = 6
total_amount = 120000
total_budget = 100000
variance_amount = 20000
max_expense_ratio = 0.35
html_file_exists = true
html_is_single_file = true
network_requests = 0
console_errors = 0
kpi_mismatch = 0
chart_blank_count = 0
table_rows_visible >= 1
filter_changes_result = true
evidence_drawer_opens = true
manifest_hash_valid = true
```

### Style Replay E2E

流程：

1. 產出第一次費用分析 single HTML。
2. 保存 style capsule。
3. 用不同 prompt / 查詢條件重新產出第二份報告。
4. 驗證：
   - `style_fingerprint` 相同。
   - SQL filters 不同。
   - execution result 不同。
   - HTML layout 結構一致。
   - KPI/chart/table 數字對應新資料。
   - evidence packet 是新的一份。
   - 沒有 stale data。

若新資料不支援原圖表，E2E 必須驗證 design adjustment checkpoint 被建立。

## Repair Policy

任一 validator fail，只能修最小垂直切片。

範例：

- package mismatch -> 修 package builder。
- chart blank -> 修 chart dataset 或 renderer。
- HTML not single-file -> 修 exporter。
- visual overflow -> 修 template CSS。
- drilldown mismatch -> 修 interaction engine。
- evidence mismatch -> 修 manifest / evidence index。
- replay stale data -> 修 replay package builder。
- replay chart incompatible -> 修 design adjustment checkpoint。

不得重寫整條 pipeline 來掩蓋單點失敗。

## 文件與 Skill 更新

需要更新：

- `/home/timmypai/.codex/skills/wferp-report/SKILL.md`
- `/home/timmypai/.codex/skills/wferp-report/README.md`
- `/home/timmypai/.codex/skills/wferp-report/references/html-output.md`
- `/home/timmypai/.codex/skills/wferp-report/references/harness.md`
- `/home/timmypai/.codex/skills/wferp-report/references/component-policy.md`
- `/home/timmypai/.codex/skills/wferp-report/references/validators.md`
- 新增 `/home/timmypai/.codex/skills/wferp-report/references/single-html-export.md`
- 新增 `/home/timmypai/.codex/skills/wferp-report/references/dynamic-design-brief.md`
- 新增 `/home/timmypai/.codex/skills/wferp-report/references/style-replay.md`

## Open Decisions

目前沒有待決策項。

已確認：

- single HTML 需完全自含。
- evidence packet 仍要輸出。
- catalog 不當固定模板，只當 guardrail。
- 使用文字摘要 + HTML visual checkpoint。
- visual checkpoint 採 semi-real preview。
- single HTML 支援完整互動，但只能前端離線重算。
- 六個 catalog 都納入產品級設計範圍。
- style replay 支援新 prompt / 新條件重新沿用舊樣式。
- replay 不相容圖表時，agent 可建議替代圖，但必須 checkpoint 確認。

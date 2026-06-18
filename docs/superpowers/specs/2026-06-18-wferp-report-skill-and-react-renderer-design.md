# WFERP Report Skill 與 React 報告渲染器設計

日期：2026-06-18
專案：`wferp`
主題：在 Workflow ERP schema metadata 與 SQL tooling 之上，建立本機 Codex `wferp-report` skill 與 React 渲染的報告/checkpoint harness。

## 1. 背景

目前 repository 有兩代功能：

- 舊版靜態 schema 文件，輸出到 `index.html`、`df_style.css`、`HTML/`；
- 新版 Workflow ERP SQL 生成與驗證工具，位於 `skill_scripts/`，資料基礎來自 `_Source/` 的 schema metadata。

新的方向不需要舊版 schema browser。新的流程需要的是 Workflow ERP schema metadata、relationship inference、SQL 安全檢查、metadata validation、execution validation，以及既有 database access boundary。

目標是建立一個由 Codex 驅動的報告 harness：使用者提供自然語言需求，並上傳或貼上欄位名稱、欄位格式與內容；系統產生一條安全的 `SELECT` SQL，先在本地驗證語法與安全性，再查詢設定好的真實資料庫；回傳資料後先讓使用者驗證，最後互動式產出 React 渲染的 HTML 報告與 CSV 匯出。

## 2. 目標

1. 建立本機 Codex skill，名稱為 `wferp-report`，放在 worktree 之外：

   ```text
   /home/timmypai/.codex/skills/wferp-report/
   ```

2. 保留現有 Workflow ERP schema rebuild 能力，但把 `_Source/1_mssql_to_json.py` 裡的資料庫連線帳密抽出。
3. SQL 生成流程必須以 `_Source/*.json`、schema loader、relationship inference、SQL safety validation、metadata validation、execution validation 為基礎。
4. 將用不到的舊版靜態文件產物隔離，但不刪除。
5. 新增 React/Reacticle 報告渲染器，用於每個 checkpoint page 與最終 HTML 報告。
6. 將 skill 設計成有狀態的 harness，參考 `beautiful-article` 的 phase/checkpoint/review/repair 作法。
7. 全流程使用 HTML review page 讓使用者確認。
8. 內建報告格式 catalog 與 `DESIGN.md` repository，讓使用者明確選擇報告結構與設計風格。
9. 使用 SubAgent validators 驗證 SQL、資料、報告內容、視覺與技術輸出，通過後才交付。
10. 支援 Excel workbook 作為需求來源：解析使用者需要的資料庫欄位、Excel 公式新增欄位、跨 sheet 公式連結，以及使用者想產出的管理報表樣式。

## 3. 非目標

- 不用 React 重建舊的 `index.html + HTML/*.html` schema browser。
- 不把舊版靜態文件頁面當作新的報告 UI。
- 不允許 skill 執行任意 SQL。
- 不允許 write operation、stored procedure、DDL 或 multi-statement batch。
- 不把真實資料庫帳密存進版本控管檔案。
- 不依賴聊天上下文保存長流程決策。

## 4. Repository 邊界

### 4.1 保留 Active 的區域

下列區域維持 active：

- `_Source/1_mssql_to_json.py`
- `_Source/2_FieldNameConvert2utf8.py`
- `_Source/*.json`
- `skill_scripts/`
- `skill_scripts/artifacts/`
- `tests/skill_scripts/`
- `test_db/`
- `skills/workflow-erp-sql-generator/`

### 4.2 Legacy Static Documentation 隔離

下列 artifact 會移到可回復的隔離區，因為新報告流程不會使用它們：

- `index.html`
- `HTML/`
- 舊版 `df_style.css`
- `_Source/3_CreateIndexHtml.py`
- `_Source/4_CreateTableStructureHtml.py`
- `_Source/5_CreateTableStructureSQL.py`

隔離是非破壞性移動。隔離區必須包含 manifest，記錄原路徑、移動時間、隔離理由與還原方式。

## 5. Schema Rebuild 資料庫設定

`_Source/1_mssql_to_json.py` 目前有 hardcoded connection constants。這些常數要從程式碼中移除，改為讀取環境變數：

```text
WFERP_SCHEMA_DB_HOST
WFERP_SCHEMA_DB_PORT
WFERP_SCHEMA_DB_DATABASE
WFERP_SCHEMA_DB_USERNAME
WFERP_SCHEMA_DB_PASSWORD
```

`WFERP_SCHEMA_DB_DATABASE` 可以預設為 `DSCSYS`，但必須明確寫在文件中，且不能推測任何敏感 credential。

缺少必要設定時，腳本必須在寫出 JSON 前停止並回報明確錯誤，例如：

- `WFERP_SCHEMA_DB_HOST_REQUIRED`
- `WFERP_SCHEMA_DB_USERNAME_REQUIRED`
- `WFERP_SCHEMA_DB_PASSWORD_REQUIRED`

Schema extraction 的資料庫設定要與報表查詢資料庫設定分開。報表查詢繼續使用 `skill_scripts/database_client.py` 現有的 `DB_*` 設定，因為 metadata extraction 與實際業務資料查詢可能連到不同 database 或 replica。

## 6. SQL 與資料流程

報告 harness 應重用既有 SQL tooling，不重寫 SQL generator。

主要流程：

1. 使用既有 schema loader 從 `_Source/` 載入 schema metadata。
2. 使用既有 relationship tooling 建立或讀取 relationship artifacts。
3. 將使用者需求、上傳欄位、欄位格式與貼上內容轉成 structured request packet。
4. 若使用者上傳 Excel workbook，先解析 workbook 欄位來源與公式 lineage，再產生 Excel field/formula review 給使用者確認。
5. 透過既有 SQL router/generator 產生一條 candidate SQL。
6. 在查詢資料庫前做本地驗證：
   - 單一 statement；
   - 只能是 `SELECT`；
   - SQL Server 2000 compatible；
   - 無 DDL/DML/procedure forbidden tokens；
   - metadata references 存在；
   - prompt 要求有反映在 SQL；
   - join 有 relationship evidence。
7. SQL 與語意驗證通過後才執行資料庫查詢。
8. 捕捉 data evidence：
   - SQL；
   - route 與 route reason；
   - execution timestamp；
   - returned columns；
   - row count；
   - sample rows；
   - validation checks；
   - redacted database connection summary。
9. 顯示 data preview，讓使用者確認後才進入報告生成。

若使用者拒絕 data preview，harness 必須回到需求修正或 SQL 生成，而不是繼續產報告。

## 7. Excel Workbook Intake 與公式解析

使用者可能上傳 Excel workbook 作為需求來源。這類 workbook 可能同時包含：

- 想從資料庫查出的原始欄位；
- 使用者在 Excel 以公式新增的衍生欄位；
- 跨 sheet、跨表格或跨區塊的公式連結；
- 使用者已經做出的管理報表版型；
- 圖表、彙總表、KPI 或文字註解，暗示最終報告的呈現方式。

`wferp-report` 不能把 Excel 只當成資料檔。它必須先解析 workbook 的需求語意，並在 SQL 生成前讓使用者確認。

解析輸出至少包含：

- workbook sheets 清單；
- 每個 sheet 的 used range；
- 欄位標題、欄位位置、資料型態與樣本值；
- 欄位分類：
  - `db-source-field`：應由資料庫查詢取得；
  - `excel-derived-field`：由 Excel 公式算出；
  - `manual-input-field`：使用者手填或無明確資料庫來源；
  - `report-layout-field`：只用於報表呈現、標題、分組或註解；
- 公式欄位清單；
- 公式 dependencies，包括同 sheet、跨 sheet、固定儲存格、命名範圍、彙總區間；
- 公式是否能轉成 SQL expression；
- 公式是否應保留在報告層計算；
- 無法安全轉換的公式與原因；
- 推測出的管理報表區塊，例如明細表、彙總表、KPI 區、圖表來源區。

SQL 生成前必須先產生 `Excel Field / Formula Review` checkpoint。使用者需確認：

1. 哪些欄位要從資料庫查詢；
2. 哪些欄位是 Excel 衍生欄位；
3. 哪些公式要轉成 SQL；
4. 哪些公式要保留在報告渲染層；
5. 哪些公式或欄位不納入報告；
6. 原 Excel 管理報表版型是否作為 final report layout 參考。

Codex 可以推薦分類與公式處理策略，但不能替使用者默選。若 formula lineage 不清楚，harness 必須停在 checkpoint，要求使用者確認或提供補充。

## 8. 本機 Skill 結構

本機 skill 放在 worktree 之外：

```text
/home/timmypai/.codex/skills/wferp-report/
  SKILL.md
  references/
    harness.md
    report-types.md
    excel-intake.md
    db-configuration.md
    validator-checklist.md
    checkpoint-pages.md
    renderer-contract.md
  assets/
    report-template/
    checkpoint-template/
  report_designs/
    index.json
    executive-summary/DESIGN.md
    financial-control/DESIGN.md
    operations-review/DESIGN.md
    exception-audit/DESIGN.md
    trend-briefing/DESIGN.md
    detail-ledger/DESIGN.md
```

`SKILL.md` 必須保持精簡。詳細 workflow、報告格式、validator 與 renderer 規則放在 reference files，需要時再讀取。

## 9. Harness Workspace

每次報告 run 建立一個持久 workspace，位置可在 repo 外或設定好的 reports 目錄。run workspace 用來保存決策與 evidence，讓 agent 可恢復流程，不依賴聊天上下文。

建議結構：

```text
wferp-report-runs/<timestamp-or-slug>/
  source/
    request.md
    uploaded-fields.md
    uploaded-content.md
    workbook-summary.md
    workbook-field-map.md
    workbook-formula-lineage.md
    intake-notes.md
  db/
    db-summary.md
    schema-db-summary.md
  sql/
    query.sql
    validation.md
    schema-relationship-evidence.md
  data/
    result.csv
    sample.json
    preview.md
  plan/
    report-plan.md
    selected-report-type.md
    selected-design.md
  checkpoint/
    intake-review.html
    excel-field-formula-review.html
    sql-review.html
    data-preview.html
    report-planning.html
    first-report-draft.html
    final-review.html
  report/
    report.html
  review/
    source-review.md
    workbook-formula-review.md
    sql-safety-review.md
    sql-semantic-review.md
    data-preview-review.md
    first-report-review.md
    final-review.md
    repair-log.md
```

Review files 只在對應 validation step 使用時建立。`repair-log.md` 只有發生修復時才建立。

## 10. HTML Checkpoint Pages

Harness 採用類似 `brainstorming` 與 `beautiful-article` 的 checkpoint 模式，但每個主要 checkpoint 都產生本機 HTML review page。

Codex 對話仍是 orchestration channel。HTML pages 負責讓使用者更容易檢查 SQL、資料、報告選項與 review evidence。使用者看完頁面後，回到 Codex 對話確認，harness 才進下一步。

Checkpoints：

1. **Intake Review**
   - 使用者需求；
   - 上傳/貼上的欄位名稱與內容摘要；
   - 推測的報告目的；
   - 缺漏或模糊的需求。

2. **Excel Field / Formula Review**
   - workbook sheets 與 used ranges；
   - DB source fields；
   - Excel-derived fields；
   - manual input fields；
   - formula dependencies；
   - 建議轉成 SQL 的公式；
   - 建議保留在報告層的公式；
   - 無法安全解析或轉換的公式；
   - 原 workbook 管理報表區塊與 final report layout 參考價值。

3. **SQL Review**
   - generated SQL；
   - referenced tables and fields；
   - relationship path evidence；
   - local safety validation；
   - semantic validation；
   - blocked risks。

4. **Data Preview**
   - row count；
   - returned columns；
   - sample rows；
   - required column checks；
   - null/duplicate/anomaly summary；
   - explicit user confirmation request。

5. **Report Planning**
   - report type catalog options；
   - design repository options；
   - Codex recommendation with reason；
   - chart/table/analysis/recommendation choices；
   - 不允許 user-facing report decisions 有 silent defaults。

6. **First Report Draft**
   - report cover/hero；
   - first data section；
   - one representative chart or table；
   - applied `DESIGN.md` style；
   - validation result。

7. **Final Review**
   - full report；
   - SQL and data evidence；
   - selected report type and design；
   - final validator findings；
   - `report.html` 與 `result.csv` 交付連結。

## 11. Report Type Catalog

報告格式選擇必須明確發生在 final report generation 前。Codex 可以推薦一種格式，但必須等使用者確認。

第一版 catalog：

| ID | 名稱 | 預設形態 |
| --- | --- | --- |
| `detail-query` | 明細查詢報告 | 高密度資料表、欄位說明、少量圖表 |
| `summary-statistics` | 彙總統計報告 | 彙總、KPI cards、summary table、bar chart |
| `trend-analysis` | 趨勢分析報告 | time-series line chart、趨勢摘要、異常點說明 |
| `comparison-analysis` | 比較分析報告 | 比較表、bar chart、差異說明 |
| `exception-audit` | 異常檢核報告 | 異常清單、嚴重度分類、處置建議 |
| `management-summary` | 管理摘要報告 | executive KPI、精簡洞察、少量明細表 |
| `full-analysis` | 完整分析報告 | 摘要、KPI、圖表、明細表、分析、建議 |

每種報告格式定義：

- 資訊保留比例；
- 預設是否使用圖表；
- 預設分析深度；
- 預設建議段落行為；
- 表格/圖表/文字比例；
- 必要使用者確認項目。

## 12. Report Design Repository

Report design repository 讓使用者做第二個明確選擇：報告結構與視覺/呈現風格分開決策。

第一版 design set：

```text
report_designs/
  index.json
  executive-summary/DESIGN.md
  financial-control/DESIGN.md
  operations-review/DESIGN.md
  exception-audit/DESIGN.md
  trend-briefing/DESIGN.md
  detail-ledger/DESIGN.md
```

每個 `DESIGN.md` 定義：

- 適用報告格式；
- 視覺語氣；
- first-screen structure；
- KPI 呈現方式；
- 表格密度；
- 圖表偏好；
- 分析與建議段落風格；
- color and typography token guidance；
- 禁止事項；
- 最小驗收標準。

範例組合：

- `summary-statistics + financial-control`
- `exception-audit + exception-audit`
- `management-summary + executive-summary`
- `trend-analysis + trend-briefing`
- `detail-query + detail-ledger`

## 13. React Renderer

Repository 應擁有 React report renderer，用於新的 report 與 checkpoint HTML output。它不重建舊版 schema browser。

Renderer 可改造 `beautiful-article` 的 Vite + React + Reacticle 單檔 HTML 模式：

- Vite build；
- React components；
- 必要時使用 Reacticle theme/component protocol；
- single-file HTML output，方便分享；
- CSV 作為資料匯出。

Renderer 必須支援：

- checkpoint pages；
- final report pages；
- Excel field/formula review tables；
- formula lineage diagrams or dependency tables；
- SQL evidence blocks；
- data preview tables；
- KPI cards；
- simple charts；
- analysis and recommendation sections；
- selected `DESIGN.md` style contract。

Renderer 消費 harness 產生的 structured JSON/state files。Renderer 不直接查詢資料庫。

## 14. Validator System

Validation 參考 `beautiful-article` 原則：每個階段使用正確的驗證方式，且必須先修復 fail items 才能前進。

### 14.1 Source / Intake Validator

預設：main agent inline checklist。

當上傳內容複雜、低信心或高風險時，升級為 SubAgent。

檢查項目：

- 欄位名稱沒有漏讀或誤讀；
- 欄位格式與貼上內容摘要正確；
- 使用者需求與欄位摘要一致；
- 缺漏輸入有列出；
- 沒有默默加入使用者未說明的業務條件。

產物：只有使用 SubAgent 時才產生 `review/source-review.md`。

### 14.2 Excel Workbook / Formula Validator

當使用者上傳 Excel workbook 時必跑。Validator 可使用 workbook inspection/render 結果與公式清單，但不得猜測不明公式的業務意義。

檢查項目：

- workbook sheets 與 used ranges 有完整列出；
- 欄位標題、位置、資料型態與樣本值有被正確抽取；
- database source 欄位、Excel-derived 欄位、manual input 欄位與 report layout 欄位分類合理；
- 公式欄位有列出原始公式；
- formula dependencies 有追蹤到同 sheet、跨 sheet、固定儲存格、命名範圍與彙總區間；
- 能轉成 SQL 的公式有轉換理由；
- 不應轉成 SQL、應保留在報告層的公式有保留理由；
- 無法支援或高風險公式有明確列出；
- 推測出的管理報表區塊與 workbook 視覺/公式 evidence 一致；
- 沒有把 Excel sample values 誤當成資料庫完整結果。

產物：`review/workbook-formula-review.md`。

### 14.3 SQL Safety Validator

查詢真實資料庫前必跑。

檢查項目：

- exactly one statement；
- `SELECT` only；
- 無 DDL/DML/procedure execution；
- 無 multi-statement separators；
- SQL Server 2000 compatible；
- 無 forbidden tokens；
- 所有 referenced tables and columns 都存在於 metadata。

產物：`review/sql-safety-review.md`。

### 14.4 Schema / Relationship Validator

針對 WFERP schema 與 relationship evidence 驗證語意正確性。

檢查項目：

- tables and fields 對應 `_Source/*.json`；
- joins 有 relationship evidence 或明確紀錄 assumption；
- prompt 要求的欄位、篩選、期間、彙總邏輯有出現在 SQL；
- selected aliases 對業務使用者可讀；
- database qualifiers 符合 configured catalog rules。

產物：`review/sql-semantic-review.md`。

### 14.5 Data Preview Validator

資料庫查詢後執行。SubAgent 只讀 redacted evidence 與 samples，不取得 raw credentials。

檢查項目：

- row count、columns、sample rows 與 execution evidence 一致；
- required columns 存在；
- empty result 會阻擋 report generation，除非使用者明確接受空報告；
- nulls、duplicates、outliers、suspicious values 有摘要；
- preview 足以讓使用者驗證資料。

產物：`review/data-preview-review.md`。

### 14.6 First Report Draft Validator

SubAgent validator，類似 `beautiful-article` 的 First Spread review。

檢查項目：

- first screen 清楚呈現報告目的；
- 第一個 data section 只使用已確認資料；
- representative table/chart 不誤導；
- Excel-derived 欄位若出現在報告中，計算邏輯與 workbook formula review 一致；
- 有遵守選定的 `DESIGN.md`；
- HTML 可 build；
- desktop 與 mobile 可讀；
- browser console 無 blocking errors。

產物：`review/first-report-review.md`。

### 14.7 Final Review Validators

使用三個 SubAgent 視角，優先並行。

**Data Correctness Reviewer**

- SQL evidence 與 report data 一致；
- tables、KPI values、chart values、summaries 一致；
- aggregation math 正確；
- 從 Excel 公式轉換或保留的衍生欄位計算正確；
- final report 中的公式連結、彙總、KPI 與 workbook formula lineage 一致；
- report 不把 sample data 當作 full data 呈現。

**Report Editorial Reviewer**

- 報告結構符合選定 report type；
- 分析與建議根據資料，不編造原因或結論；
- 使用者確認過的需求都有涵蓋；
- 語言清楚且一致。

**Visual / Technical Reviewer**

- final HTML build 成功；
- single-file report 可開啟且沒有 broken assets；
- tables and charts 可讀；
- 遵守選定 `DESIGN.md` 的視覺限制；
- 基本 accessibility 存在；
- browser console 無錯誤。

產物：全部追加到 `review/final-review.md`。

Main agent 必須先修復 fail items 才能交付。只有 validator output 不代表完成。

## 15. 安全與資料處理

- 不把真實 credential 寫進 repository files。
- HTML checkpoint pages 不顯示完整 connection string。
- 所有 evidence 必須遮蔽 password 與 sensitive tokens。
- 真實 DB execution 必須在 SQL safety validation 之後。
- 預設只允許 read-only query execution。
- non-test execution 必須明確且可稽核。
- 除非使用者要求 full export，否則不要保存超過 preview/report 所需的 result rows。
- Excel workbook 內可能含敏感資料、內部公式與管理報表邏輯；checkpoint pages 只能顯示必要樣本與公式摘要，避免暴露超出報告需求的原始內容。

## 16. 測試策略

測試應聚焦 contract 與 observable behavior。

預期測試區域：

- schema extraction config 從 `WFERP_SCHEMA_DB_*` 載入；
- 缺少必要 schema DB env 時會失敗；
- legacy static docs quarantine manifest generation；
- report type catalog loading and validation；
- `DESIGN.md` repository index loading and design validation；
- Excel workbook sheet/range extraction；
- Excel formula lineage extraction；
- Excel 欄位分類與使用者確認 checkpoint；
- 公式轉 SQL 與保留在報告層的決策記錄；
- checkpoint state file creation；
- SQL safety and semantic validation gates；
- data preview evidence redaction；
- React checkpoint page rendering；
- final report HTML build；
- CSV export generation。

React-rendered checkpoint pages 與 final report pages 必須做 browser verification。

## 17. 待 Implementation Plan 決定的事項

下列事項留到 implementation plan 決定：

- quarantine directory 的精確名稱；
- repository 內 report renderer 的精確目錄名稱；
- renderer 直接使用 Reacticle，或包一層 WFERP-specific components；
- 圖表 library 選擇；
- Excel workbook parsing 的實作工具與支援公式範圍；
- preview 與 CSV export 的最大 row limit；
- report run workspace 放在 `/tmp`、`~/.codex`，或設定的 project directory。

這些事項必須在 implementation plan 中定案後再進入 code changes。

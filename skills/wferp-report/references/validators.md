# Validators

wferp-report 的 validator gate 必須併入 subagent review。每個 validator result 不是主 agent 自填的檢查清單，而是由獨立 reviewer subagent 讀取 run directory、checkpoint payload、SQL、資料預覽、HTML 與 evidence 後產生。主 agent 只負責分派 review、彙整 JSON、驗證 contract、判斷 gate 與執行最小 repair slice。

若目前執行環境無法 spawn subagent，必須明確標記為 `blocked` 或使用「獨立審查步驟」替代，並在 evidence 中說明替代原因；不得把主 agent 的一般摘要偽裝成 subagent validator。

## Contract

每個 subagent reviewer 的結果必須符合下列欄位：

- `role`：固定 reviewer role。
- `status`：`pass`、`fail`、`warning` 或 `blocked`。
- `checked_items`：此 reviewer 實際檢查的項目。
- `evidence`：命令、檔案、截圖、SQL、row/column/aggregate metrics、HTML URL 或檢查摘要。
- `findings`：發現的問題；`fail` 或 `blocked` 時不可空白。
- `required_fixes`：必要修復；`fail` 或 `blocked` 時不可空白。
- `residual_risks`：仍可接受或需使用者確認的殘餘風險。

相容性：若現有工具仍輸出 camelCase `requiredFixes` / `residualRisks`，主 agent 必須轉成 snake_case 後再寫入 final evidence。

## Subagent Gate Policy

- **主 agent 不直接宣告 validator pass**：主 agent 只能檢查 subagent output 是否符合 contract，不能取代 reviewer 做內容判斷。
- **有問題回主 agent repair**：任一 subagent 回傳 `fail` 或 `blocked` 時，主 agent 必須依 `required_fixes` 開最小垂直修復，不得跳過、不得用使用者確認覆蓋。
- **warning 只能帶風險前進**：`warning` 可進入下一個可逆步驟，但 final delivery 前必須由使用者明確接受 role-prefixed residual risk。
- **可並行但不可越過硬 gate**：不依賴該 review 結果的工作可先做，但不得執行 DB query、final delivery 等依賴該 gate 的不可逆步驟。
- **Evidence 必須具體**：每個 subagent 必須列出實際讀取檔案、命令、截圖、HTML URL、row/column/aggregate metrics 或視覺檢查結論。
- **HTML 必須實看**：涉及 visual / report / delivery 的 reviewer 不得只看 JSON payload，必須實際開啟 HTML 或 companion page，檢查亂碼、重疊、溢出、chart/table 誤導、按鈕互動與 mobile/desktop 明顯破版。

## Required Subagent Gates

不是每個 checkpoint 都需要 subagent。下列 gate 需要獨立 subagent review：

1. **Requirement / Excel / Schema Gate**：`requirement_understanding_reviewer`、有 Excel 時 `excel_logic_reviewer`、`schema_mapping_reviewer`、`chart_layout_reviewer`。通過後才可把 Normalized Report Plan 視為 SQL 輸入。
2. **SQL Execution Gate**：`sql_safety_reviewer`、`schema_mapping_reviewer`。通過後且使用者確認 SQL 後才可執行 DB query。
3. **DB Execution Gate**：`db_execution_reviewer`。通過後才可將 raw DB rows 視為 data preview 來源。
4. **Data / SQLite Enrichment Gate**：`data_preview_reviewer`、有 enrichment 時 `sqlite_enrichment_reviewer`。通過後才可進入 report selection / report design。
5. **Report Design Gate**：`report_design_reviewer` 與 `chart_layout_reviewer`。通過後才可進 React scaffold。
6. **Report / Visual / Technical Gate**：`report_content_reviewer`、`visual_taste_reviewer`、`react_technical_reviewer`。通過或 warning 被記錄後才可進 final review。
7. **Delivery Gate**：`delivery_reviewer`，必要時重跑 `visual_taste_reviewer` 與 `react_technical_reviewer` 確認 single HTML。

## 必備 reviewer roles

- 需求/來源 validator：對應 `requirement_understanding_reviewer`。
- Excel 欄位與公式 validator：對應 `excel_logic_reviewer`。
- SQL 安全 validator：對應 `sql_safety_reviewer`。
- Schema/relationship validator：對應 `schema_mapping_reviewer`。
- DB execution validator：對應 `db_execution_reviewer`。
- SQLite enrichment validator：對應 `sqlite_enrichment_reviewer`。
- Data preview validator：對應 `data_preview_reviewer`。
- Report design validator：對應 `report_design_reviewer`。
- Chart/layout validator：對應 `chart_layout_reviewer`。
- 報告內容 validator：對應 `report_content_reviewer`。
- 視覺/技術 validator：由 `visual_taste_reviewer`、`react_technical_reviewer`、`delivery_reviewer` 共同覆蓋。

## Role Requirements

`requirement_understanding_reviewer`：確認 prompt、uploaded files、需求欄位、報表目標、使用者確認紀錄與 Normalized Report Plan 一致。

`excel_logic_reviewer`：確認 Excel sheet roles、欄位分類、公式 lineage、lookup 判斷、manual-only / format-only / unresolved 欄位是否完整。DB 欄位需有 readable field name / description、schema path、confidence、reason 與 lineage。

`schema_mapping_reviewer`：確認 LLM 找到的是最可能存在資料的 table/field 組合，而不是單一欄位關鍵字命中；檢查 WFERP schema、relationship、join path、field readable names 與 business intent 是否合理。

`chart_layout_reviewer`：確認 chart type、chart 數量、layout、section order、Excel-like view 與使用者 report intent 一致；若資料不足以支援圖表，必須要求主 agent 回 Phase 2/7 修正。

`sql_safety_reviewer`：確認 SQL 為唯讀 SELECT，無 DDL/DML、危險 keyword、multi statement、comments、未確認查詢或跨權限查詢；確認 SQL 欄位都能追到 schema mapping。

`db_execution_reviewer`：確認 DB target、DB_ENV、execution evidence、row count、column count、duration、error handling 與 SQL confirmed evidence 一致。

`sqlite_enrichment_reviewer`：確認 SQLite manifest、raw/enriched temp table 名稱唯一、raw row count、enriched row count、ignored lookup rows、formula status、lookup hit/miss 與 retention decision evidence；evidence 必須包含 manifest file 與 `raw_row_count`、`enriched_row_count`、`ignored_lookup_rows` metrics。

`data_preview_reviewer`：確認 preview rows、columns、aggregate totals、excluded rows 與 prompt intent；evidence 必須有 numeric `row_count` 與 `column_count`。

`report_design_reviewer`：確認 report type/design/options、chart/table/layout、分析與建議需求都已被使用者確認，且 selected design 可以用目前 data package 產出。

`report_content_reviewer`：確認報告文字、KPI、表格、建議與資料證據一致；所有重要數字能追溯到 SQL raw data、SQLite enrichment 或 formula semantics。

`visual_taste_reviewer`：確認排版、層級、留白、可讀性、中文文案、視覺美化、行動/桌面版面與使用者選擇的 design profile 一致。

`react_technical_reviewer`：確認 React scaffold 可 build、payload schema 正確、固定元件使用合規、LLM-generated section code 已通過 `validate-report-section`、section export 與 `Report.tsx` linkage 正確、data refs 存在、無 unsafe RawBlock、無外部 network requests、不得連 DB、不得執行 SQL。

`delivery_reviewer`：確認 single-file HTML、payload、SQL、raw/enriched data、Normalized Report Plan、final review、validator evidence 與 SQLite retention evidence 齊全。

## Subagent Spawn Prompt Template

主 agent spawn reviewer 時使用此 prompt，並替換 role / phase / paths：

```text
你是 wferp-report 的獨立 reviewer subagent。

請審查 run_dir: <RUN_DIR>
phase: <PHASE>
reviewer_role: <ROLE>
files_to_review:
- <PATHS>

你必須自己讀取檔案、checkpoint payload、SQL、data preview、report draft、HTML 或 evidence。不得只驗 JSON 欄位是否存在。

檢查要求：
1. 檢查 validator contract 是否完整。
2. 檢查 evidence 是否足以支持 pass。
3. 檢查此 phase 的資料、SQL、schema、報告內容或 HTML 是否正確。
4. 若有 HTML 或 companion URL，必須實際開啟並檢查：
   - 是否可開啟、是否亂碼
   - layout 是否重疊、溢出或不可讀
   - table 是否顯示實際資料且欄位正確
   - chart type、label、legend、排序與資料是否合理
   - button / refresh / confirmation 是否明顯可用
   - mobile / desktop 是否有明顯破版
5. 若發現問題，提出最小 repair slice，讓主 agent 修復後重跑你或受影響 reviewer。

輸出只能是 JSON：
{
  "role": "<ROLE>",
  "status": "pass|fail|warning|blocked",
  "checked_items": [],
  "evidence": [
    {"type": "file", "path": "..."},
    {"type": "metric", "name": "...", "value": 0},
    {"type": "inspection", "name": "...", "status": "pass|fail|warning"},
    {"type": "command", "command": "..."}
  ],
  "findings": [],
  "required_fixes": [],
  "residual_risks": []
}
```

## Delivery Gate

`ReportHarness.can_deliver()` 必須彙整 final review 的 validator results：

- 所有必備 validators 都存在且全部 `pass` 時，才可直接交付。
- 若任何 validator 是 `fail`、`warning` 或 `blocked`，預設不可交付。
- 若使用者在 final checkpoint 明確確認「完成」，且 confirmation 的 `selectedOptions.acceptedResidualRisks` 逐項列出相符的 `validator_role: risk text`，才可帶風險交付。
- CLI acceptance 使用 `python3 -m skill_scripts.cli_report_harness confirm --checkpoint final_review --action 完成 --accepted-residual-risk "validator_role: risk text"`；不得用 final review payload 的 `accepted_residual_risks` 取代使用者確認。
- 缺少任一必備 validator 時不可交付，不能用使用者確認覆蓋。

交付訊息必須列出 `blocking_validators` 與 `accepted_residual_risks`，讓使用者知道是通過、被擋下，或是帶風險接受。
## Fresh Reviewer Metadata

Required validators must be fresh reviewer or subagent artifacts. Main-agent self-review cannot pass a gate.

Each validator JSON must include:

- `reviewer_identity`: object with `kind` and `id`; `kind` should be `subagent` when a subagent was used.
- `checked_scope`: non-empty list of artifacts or surfaces reviewed.
- `input_artifact_paths`: non-empty list of run files, SQL files, HTML files, screenshots, or evidence packets read by the reviewer.
- `reviewed_at`: timestamp of the review.
- `evidence`: concrete proof such as row counts, rendered URLs, screenshots, command outputs, or file paths.

Validators must stay generic. Do not hardcode a customer, company, database, table, field, report type, or business domain into pass/fail logic. Domain context must come from the current run's prompt, source inventory, schema evidence, normalized report plan, SQL evidence, and data preview.

# Excel Intake

Excel workbook 必須解析 `需求欄位`、`自訂公式`、`lookup 對照表`、`管理報表`。確認 database-backed、formula-backed、lookup-backed、manual-only、unresolved references，並向使用者呈現 `資料庫欄位`、`使用者公式欄位`、`對照表欄位`、`報表輸出欄位`、`需使用者確認`。

## Default Workbook Rule

- 若使用者說明 A 欄至 Z 欄由資料庫查詢，這些欄位預設分類為 `db_field`，但仍需用 WFERP schema metadata 驗證。
- AA 欄後若為 Excel 公式、lookup 或人工欄位，預設不得送正式 DB 查詢。
- 可由 SQL function 或 join 取得的公式欄位，仍先評估是否屬於正式 DB schema 可追溯欄位；若無法明確證明，改由 SQLite enrichment 處理。
- lookup 對照表先匯入 run-scoped SQLite lookup table，再與 raw DB rows 產生 enriched table。
- 無法轉譯的 Excel 公式不得忽略；必須列入 checkpoint，通知使用者並討論處理方式。

## Required Extraction

對每個 sheet 記錄：

- sheet name、used range、header row、data start row。
- 每個欄位的 excel column、header、sample values、formula。
- 公式 lineage：引用欄位、引用 sheet、lookup range、常數、跨 sheet reference。
- 管理報表區塊：標題、輸出欄位、公式連結、圖表或彙總位置。
- lookup table candidates：小型對照表、重複 key/value 區塊、VLOOKUP/XLOOKUP/INDEX-MATCH 引用範圍。

## Output Contract

`excel_requirement.json` 與 `field_formula_classification.json` 需能回答：

- 哪些欄位會進正式 DB raw SELECT。
- 哪些欄位會由 SQLite formula / lookup enrichment 產生。
- 哪些欄位需人工確認。
- 每個 DB 欄位的 readable field name / description。
- 每個公式欄位的處理狀態：`translated`、`lookup_join`、`manual_required`、`unresolved`。

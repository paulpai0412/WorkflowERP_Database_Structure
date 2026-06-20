# Field Classification

Excel workbook 進入 SQL 生成前，skill 必須先自動分類欄位，不要求使用者手動標註 DB 欄位或公式欄位。

## Classification Types

- `db_field`：A:Z 或其他來源欄位可直接對應 WFERP schema，由正式 DB raw SELECT 取得。
- `formula_field`：Excel 公式產生，不能送正式 DB 查詢；可轉譯時在 SQLite enrichment 補齊。
- `lookup_field`：由 Excel 對照表、VLOOKUP/XLOOKUP/INDEX-MATCH 或可識別 lookup sheet 產生，先匯入 SQLite lookup table 再補齊。
- `manual_only`：純人工輸入、註記或沒有可靠資料 lineage，不得猜測成 DB 查詢。
- `unresolved`：欄位名稱、公式或 schema 對應不足，必須在 checkpoint 呈現給使用者確認。

## Required Metadata

每個欄位至少記錄：

- `excel_column`、`sheet_name`、`header`。
- `classification`、`confidence`、`reason`。
- `processing_location`：`db_raw_query`、`sqlite_enrichment`、`manual_review`。
- DB 欄位需包含 `table_name`、`field_name`、`readable_name`、`description`、`relationship_path`。
- 公式欄位需包含 `formula`、`lineage_inputs`、`translation_status`。
- lookup 欄位需包含 `lookup_sheet`、`lookup_key_columns`、`lookup_value_columns`、`unmatched_policy`。

## Checkpoint Requirements

`field_formula_classification` checkpoint 必須讓使用者同時看到管理語意與技術欄位：

- 欄位名稱或中文/越文說明，避免只顯示無意義 field code。
- 哪些欄位會送正式 DB 查詢。
- 哪些欄位會留在 SQLite temp table enrichment。
- 哪些公式或 lookup 無法自動處理，以及建議處理方式。

通過 `excel_classification_reviewer` 與使用者確認前，不得產出正式 SQL。

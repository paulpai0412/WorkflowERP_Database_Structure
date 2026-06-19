# SQLite Enrichment

正式 DB 只負責查詢已確認的 raw fields；Excel 公式、lookup、補充欄位一律在本次 run 專用 SQLite workspace 中處理，避免把 Excel 邏輯硬塞進正式 DB。

## Workspace Rules

- 每次 run 建立唯一 SQLite workspace 與 temp table name，不得重複。
- Manifest 必須寫入 `sqlite/wferp_run_sqlite_manifest.json`，包含 database path、raw table、enriched table、lookup tables、row counts、cleanup status。
- temp table 名稱需包含 run id 或安全 hash，避免資料殘留混用。
- Browser / React renderer 只能讀 JSON payload，不得直接讀 SQLite。

## Flow

1. `init-sqlite-workspace` 建立 SQLite 檔與 manifest。
2. `import-lookups` 將 Excel lookup sheets 匯入 SQLite lookup tables。
3. `write-raw-table` 將 DB raw SELECT 回來的 rows 寫入 raw table。
4. `write-raw-preview` 產生 raw data checkpoint。
5. `run-sqlite-enrichment` 依 formula lineage 與 lookup rules 產生 enriched table。
6. `write-enriched-preview` 產生 enriched data checkpoint。
7. `write-sqlite-retention` 詢問使用者保留或清除 temp data。
8. 若使用者選擇清除，`cleanup-sqlite-run` 刪除 SQLite 檔或標記 temp tables cleaned。

## Validation Requirements

`sqlite_enrichment_reviewer` 必須檢查：

- manifest file 存在且可追溯到 run。
- raw table 與 enriched table row count 一致，除非 checkpoint 明確列出排除原因。
- `raw_row_count`、`enriched_row_count`、`ignored_lookup_rows` metrics 具體可量化。
- formula 欄位有 translation status；無法轉譯時已通知使用者並列入 unresolved。
- lookup hit/miss 有統計，未命中資料不能默默填空。
- retention decision 已保存，cleanup 有 evidence。

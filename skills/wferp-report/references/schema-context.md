# Schema Context

使用 `_Source/TableName.json`、`_Source/TableStructure.json`、`_Source/MoudleName.json` 與 `skill_scripts/schema_loader.py` 載入 WFERP schema。使用 relationship graph 對應 header/detail join。

## Readable Metadata

WFERP 欄位代碼常無法讓一般使用者理解。每次帶出 DB 欄位時，checkpoint 與 reviewer evidence 必須同時顯示：

- table code、table readable name、module。
- field code、field readable name、field description。
- key / nullable / data type / length。
- relationship path 或 join reason。
- confidence 與 mapping reason。

若 `_Source` metadata 缺少中文或可讀名稱，應從既有 language/name conversion artifacts、field dictionary 或 Excel header 補足候選說明；仍無法補足時標成 `unresolved_description`，不得只把無意義 field code 呈現給使用者確認。

## SQL Mapping Rule

- SQL 只能引用已確認為 `db_field` 的欄位。
- Excel formula / lookup 欄位不直接變成正式 DB SQL select item，除非 schema_relationship_reviewer 明確確認該欄位為資料庫可追溯欄位。
- Header/detail join 必須由 relationship graph 或已知 key path 支持。
- 若 prompt 需要彙總，先保留 raw detail 欄位，必要的 report aggregate 可在 SQLite enrichment 或報告 payload 中形成可追溯彙總。

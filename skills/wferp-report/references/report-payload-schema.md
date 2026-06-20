# Report Payload Schema

報告 renderer 只接受 structured JSON payload，不讀 DB、不執行 SQL。

## 必填欄位

- `report_id`
- `title`
- `design_profile`
- `source_inventory`
- `sql_evidence`
- `data_preview`
- `sections`
- `validator_evidence`
- `residual_risks`

每個 section 必須包含 `id`、`title`、`purpose`、`data_refs`、`component` 與 `validation_notes`。

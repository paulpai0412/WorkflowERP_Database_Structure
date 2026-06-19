# DB Config

Schema rebuild 使用 `WFERP_SCHEMA_DB_HOST`、`WFERP_SCHEMA_DB_PORT`、`WFERP_SCHEMA_DB_DATABASE`、`WFERP_SCHEMA_DB_USERNAME`、`WFERP_SCHEMA_DB_PASSWORD`。

Report query execution 使用 repo 既有 `DB_*` 設定與 governed validation path。非 `DB_ENV=test` 不可自動執行，除非使用者明確允許。

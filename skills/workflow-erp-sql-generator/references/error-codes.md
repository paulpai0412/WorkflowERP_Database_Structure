# Error Codes

| Code | Meaning |
| --- | --- |
| `NON_SELECT_INTENT` | Request implies non-SELECT operation. |
| `UNSUPPORTED_SQL2000_FEATURE` | SQL contains SQL Server 2000-incompatible syntax/features. |
| `MULTI_STATEMENT_NOT_ALLOWED` | SQL contains multiple statements/batch content. |
| `TABLE_REFERENCE_FORMAT_INVALID` | Table reference format is not bracketed metadata format. |
| `NO_TABLE_REFERENCE` | No table reference detected. |
| `UNKNOWN_TABLE` | Referenced table is absent from metadata. |
| `UNKNOWN_TABLE_ALIAS` | Qualified column uses an alias not introduced in FROM/JOIN. |
| `UNKNOWN_COLUMN` | Referenced column is absent from metadata. |
| `UNKNOWN_COLUMN_FOR_TABLE` | Referenced column does not belong to the referenced table/alias. |
| `YEAR_MISMATCH` | Year filter is inconsistent with expected domain/context. |
| `TOP_MISMATCH` | TOP behavior conflicts with prompt intent. |
| `DOMAIN_MISMATCH` | Prompt condition conflicts with detected column domain. |
| `DB_ENV_NOT_TEST` | Execution validation attempted outside `DB_ENV=test`. |
| `DB_CLIENT_REQUIRED` | Execution validation was enabled without a database client. |
| `ROWCOUNT_TOO_LOW` | Result rows are fewer than `--min-rows`. |
| `ROWCOUNT_TOO_HIGH` | Result rows exceed `--max-rows`. |
| `MISSING_REQUIRED_COLUMN` | Required columns are absent from execution results. |
| `MISSING_AGGREGATE_COLUMN` | Aggregate check column is absent from execution results. |
| `AGGREGATE_MISMATCH` | Aggregate validation differs from expected value beyond tolerance. |
| `EXECUTION_VALIDATION_ERROR` | Execution attempt failed before row/column/aggregate checks completed. |
| `DB_CONNECTION_NOT_CONFIGURED` | No usable DB connection string or derived connection config was available. |
| `DB_PASSWORD_MISSING` | SQL auth mode was selected but no DB password is available. |
| `DB_USERNAME_MISSING` | Windows domain auth mode was selected but username is missing. |
| `DB_DRIVER_NOT_INSTALLED` | Required DB driver module (`pymssql` or `pyodbc`) is not installed. |
| `DB_CONNECTION_FAILED` | Connection attempt to database failed. |
| `DB_DRIVER_UNSUPPORTED` | `DB_DRIVER` value is not supported by runtime. |
| `LLM_PROVIDER_NOT_CONFIGURED` | LLM provider config is missing or disabled. |
| `LLM_PROVIDER_UNSUPPORTED` | Selected LLM provider value is not supported. |
| `LLM_PROVIDER_ERROR` | LLM provider returned a non-success process/API outcome. |
| `LLM_TIMEOUT` | LLM call timed out. |
| `LLM_BAD_RESPONSE` | LLM response format/content could not be parsed as expected. |
| `LLM_NETWORK_ERROR` | Network failure occurred while calling remote LLM endpoint. |
| `LLM_HTTP_ERROR:<status>` | Remote LLM endpoint returned HTTP error status code. |
| `OPENCODE_CLI_NOT_INSTALLED` | Local `opencode` CLI is not installed or not in PATH. |
| `LLM_REPAIR_FAILED:<reason>` | All llm-first repair attempts were exhausted without a valid result. |

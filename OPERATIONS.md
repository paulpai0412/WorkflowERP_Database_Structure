# Operation Manual

## Purpose

This runbook covers the day-to-day workflows for regenerating documentation, building SQL artifacts, validating SQL, and running tests.

## 1) Legacy schema regeneration

Export the schema database connection environment variables before rebuilding metadata.

Required:

```bash
export WFERP_SCHEMA_DB_HOST="your-sql-server-host"
export WFERP_SCHEMA_DB_USERNAME="your-username"
export WFERP_SCHEMA_DB_PASSWORD="your-password"
```

Optional defaults:

```bash
export WFERP_SCHEMA_DB_PORT="1433"
export WFERP_SCHEMA_DB_DATABASE="DSCSYS"
```

Run these commands from `schema/_Source/` because the scripts use relative paths:

```bash
python3 1_mssql_to_json.py
python3 2_FieldNameConvert2utf8.py
```

### Verification

1. confirm `_Source/MoudleName.json`, `_Source/TableName.json`, and
   `_Source/TableStructure.json` were regenerated;
2. run `python3 -m skill_scripts.cli_generate_select --build-artifacts` from
   repo root;
3. run `pytest tests/skill_scripts/test_schema_loader.py -v`.

## 2) Build SQL-tooling artifacts

Run from `schema/`:

```bash
python3 -m skill_scripts.cli_generate_select --build-artifacts
```

Use this after changing schema-loading, relationship, or dictionary logic, or when `_Source/` artifacts change.

## 3) Generate SQL from a prompt

### Default command

```bash
python3 -m skill_scripts.cli_generate_select --prompt "查詢採購單前 20 筆"
```

### Rule-only mode

```bash
python3 -m skill_scripts.cli_generate_select --prompt "查詢採購單前 20 筆" --mode rule
```

### Shadow mode

```bash
python3 -m skill_scripts.cli_generate_select --prompt "查詢2026年的工程預算明細" --mode shadow
```

### LLM-first mode

```bash
python3 -m skill_scripts.cli_generate_select --prompt "查詢2026年的工程預算明細" --mode llm-first
```

## 4) Validate SQL execution and result correctness

Start and seed the test DB if needed:

```bash
docker compose -f test_db/docker-compose.testdb.yml up -d
docker exec -i wferp-mssql-test /opt/mssql-tools18/bin/sqlcmd -C -S localhost -U sa -P Passw0rd\!234 -i /init/01_create_wferp_test.sql
```

Export the test environment variables in the current shell:

```bash
export DB_DRIVER=mssql
export DB_AUTH_MODE=sql_auth
export DB_CONNECTION_STRING="server=127.0.0.1:1433;user=sa;password=Passw0rd!234;database=wferp_test"
export DB_ENV=test
```

Run a prompt with execution validation:

```bash
python3 -m skill_scripts.cli_generate_select --prompt "查詢2026年的工程預算明細" --validate-execution --required-columns MK002,MK006 --min-rows 1
```

### Required operator rule

Do not stop at SQL string inspection. A SQL-generation task is only complete after:

1. the SQL executes successfully; and
2. the returned result matches the prompt intent.

## 5) Run tests

Run the full SQL-tooling suite:

```bash
pytest tests/skill_scripts/ -v
```

Run one focused test file:

```bash
pytest tests/skill_scripts/test_schema_loader.py -v
```

Use focused tests while iterating and the full suite before finalizing tooling changes.

## 6) Report harness workflow

Create a report run from a prompt:

```bash
python3 -m skill_scripts.cli_report_harness --prompt "請產出費用分析" --run-dir wferp-report-runs/demo
```

Parse a real Excel requirement workbook and write the Excel confirmation checkpoint:

```bash
python3 -m skill_scripts.cli_report_harness --prompt "請產出費用分析" --input-file /path/to/需求.xlsx --run-dir wferp-report-runs/demo --checkpoint excel
```

Create the SQL review checkpoint without executing the database:

```bash
python3 -m skill_scripts.cli_report_harness --prompt "查詢採購單前 20 筆" --run-dir wferp-report-runs/demo --checkpoint sql --mode rule
```

Execution validation remains gated. `--validate-execution` does not execute without `--confirm-sql`, and non-test DB environments require `--allow-non-test-db-execution`.

## 7) Run the expense-analysis E2E

Run the deterministic expense-analysis path. The runner validates SQLite first,
then uses Docker PostgreSQL as the local simulation of the formal MSSQL DB:

```bash
bash scripts/run_expense_analysis_postgres_e2e.sh
```

The runner:

1. runs `bash scripts/run_expense_analysis_sqlite_e2e.sh`;
2. creates a real local SQLite DB in pytest and validates row counts, columns,
   totals, exclusions, and percentages;
3. starts `wferp-postgres-e2e`;
4. recreates and seeds `dbo."ACPTA"` and `dbo."ACPTB"`;
5. prints fixture counts, included totals, excluded control totals, and generated SQL;
6. runs `pytest tests/skill_scripts/test_expense_analysis_postgres_e2e.py -v`.

The SQLite pytest file is skipped unless `WFERP_RUN_SQLITE_E2E=1` is set. The
PostgreSQL pytest file is skipped unless `WFERP_RUN_POSTGRES_E2E=1` is set. The
runner sets both flags.

## 8) Operational decision guide

| Task | Work area |
| --- | --- |
| Source ERP metadata changed | `_Source/` |
| SQL generation logic changed | `skill_scripts/` + `tests/skill_scripts/` |
| Query execution validation changed | `skill_scripts/` + `test_db/` |
| Agent usage guidance changed | `skills/workflow-erp-sql-generator/` |

## 9) Common failure cases

### Generated SQL looks valid but fails task intent

Run execution validation with required columns or aggregate checks. Do not accept the query based only on syntax.

### Test DB rejects execution

- check container health;
- confirm the DB environment variables are exported;
- confirm the seed SQL ran successfully.

### HTML output breaks after regeneration

- verify you ran the scripts from `_Source/`;
- verify generated links still keep the expected Windows-style `HTML\\...` format;
- rerun the pipeline in sequence instead of skipping intermediate steps.

## 10) Related references

- `AGENTS.md`
- `INSTALLATION.md`
- `skills/workflow-erp-sql-generator/SKILL.md`
- `skills/workflow-erp-sql-generator/references/functions.md`

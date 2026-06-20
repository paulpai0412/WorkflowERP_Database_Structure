# Installation Guide

## Purpose

This guide covers local setup for the Workflow ERP schema documentation and SQL-generation repo.

## 1) Prerequisites

- Python 3
- `pip`
- Docker and Docker Compose
- access to a Workflow ERP SQL Server instance if you need to regenerate `_Source/` artifacts from scratch

## 2) Repository root

Run the commands in this guide from `schema/` unless a step explicitly says `_Source/`.

## 3) Python environment

Create and activate a virtual environment if needed:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the verified dependencies used by this repo:

```bash
python3 -m pip install pymssql pandas pytest
```

Notes:

- there is no checked-in dependency manifest;
- `pytest` is used by `tests/skill_scripts/` even though it is not declared in a repo-level requirements file;
- `pyodbc` is only needed if you choose that driver path in `database_client.py`;
- `openpyxl` is optional for ad hoc workbook inspection. The report Excel intake parser reads real `.xlsx` files with the Python standard library, so the harness tests do not require `openpyxl`.

## 4) Test database setup

Start the Dockerized SQL Server container:

```bash
docker compose -f test_db/docker-compose.testdb.yml up -d
```

Initialize schema and seed data after the container becomes healthy:

```bash
docker exec -i wferp-mssql-test /opt/mssql-tools18/bin/sqlcmd -C -S localhost -U sa -P Passw0rd\!234 -i /init/01_create_wferp_test.sql
```

Export the default test environment variables:

```bash
export DB_DRIVER=mssql
export DB_AUTH_MODE=sql_auth
export DB_CONNECTION_STRING="server=127.0.0.1:1433;user=sa;password=Passw0rd!234;database=wferp_test"
export DB_ENV=test
```

## 5) First-run verification

Verify the schema loader smoke test:

```bash
pytest tests/skill_scripts/test_schema_loader.py -v
```

Build SQL-tooling artifacts:

```bash
python3 -m skill_scripts.cli_generate_select --build-artifacts
```

Run a sample SQL prompt:

```bash
python3 -m skill_scripts.cli_generate_select --prompt "查詢採購單前 20 筆"
```

Create a report harness run from a prompt:

```bash
python3 -m skill_scripts.cli_report_harness create-run \
  --run-root wferp-report-runs \
  --run-id demo \
  --prompt "請產出費用分析"
```

Create an Excel confirmation checkpoint from a real workbook:

```bash
python3 -m skill_scripts.cli_report_harness classify-workbook \
  --run-dir wferp-report-runs/demo \
  --input-file /path/to/需求.xlsx
python3 -m skill_scripts.cli_report_harness serve-checkpoint \
  --run-dir wferp-report-runs/demo \
  --host 127.0.0.1 \
  --port 0
python3 -m skill_scripts.cli_report_harness wait-confirmation \
  --run-dir wferp-report-runs/demo \
  --checkpoint field_formula_classification
```

## 6) Expense-analysis E2E fixtures

The expense-analysis E2E runs in two stages:

1. local SQLite first-pass validation with a real SQLite database, real seed
   data, generated SQL, and aggregate assertions;
2. Docker PostgreSQL validation as the local simulation of the formal MSSQL DB
   execution target for the generated SQL Server SELECT subset.

Run from the repository root:

```bash
bash scripts/run_expense_analysis_postgres_e2e.sh
```

The PostgreSQL runner first executes:

```bash
bash scripts/run_expense_analysis_sqlite_e2e.sh
```

Then it starts `wferp-postgres-e2e`, seeds `wferp_e2e`, prints fixture counts
and the generated SQL, then runs:

```bash
pytest tests/skill_scripts/test_expense_analysis_postgres_e2e.py -v
```

## 7) Optional legacy regeneration setup

If you need to rebuild the legacy schema artifacts, export the schema database connection environment variables before running the `_Source/` pipeline from the `_Source/` directory.

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

Run the rebuild from `_Source/` because the scripts use relative paths:

```bash
cd _Source
python3 1_mssql_to_json.py
python3 2_FieldNameConvert2utf8.py
```

## 8) Troubleshooting

### `pytest` not found

Install it in the active environment:

```bash
python3 -m pip install pytest
```

### `DB_DRIVER_NOT_INSTALLED`

Install the required Python driver for the selected DB mode, typically `pymssql` for the default configuration.

### Connection failures in execution validation

- confirm the `wferp-mssql-test` container is healthy;
- confirm `DB_CONNECTION_STRING` and `DB_ENV=test` are exported in the current shell;
- rerun the seed command if the schema is missing.

### PostgreSQL expense-analysis E2E fails to connect

- confirm Docker is running;
- confirm port `55432` is free;
- rerun `bash scripts/run_expense_analysis_postgres_e2e.sh` so the fixture is
  recreated before pytest executes.

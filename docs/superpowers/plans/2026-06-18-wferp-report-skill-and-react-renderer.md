# WFERP Report Skill And React Renderer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to execute this plan step-by-step.

本計畫把 `docs/superpowers/specs/2026-06-18-wferp-report-skill-and-react-renderer-design.md` 轉成可執行工作。所有使用者可見文件、skill 文案、互動頁面文字、驗收紀錄使用繁體中文。程式、測試名稱、commit message 可使用英文。

## Goal

建立本地端 `wferp-report` Codex skill 與 repo 內支援工具，使使用者能在 Codex 以自然語言與上傳欄位/Excel 需求檔啟動流程，skill 依 DB 設定與 WFERP schema/relationship 生成合法唯讀 `SELECT` SQL，先本地驗證語法與禁止語法，再查詢真實資料庫，呈現資料預覽供使用者確認，接著讓使用者選擇報告格式與設計樣式，用 React renderer 產生互動確認頁與最終報告。

## Constraints

- 不把 local skill 放進 worktree；skill 目標路徑是 `/home/timmypai/.codex/skills/wferp-report/`。實作時寫入此路徑需要依 sandbox 規則請求 escalation。
- 保留 schema 重建功能：`_Source/1_mssql_to_json.py` 與 `_Source/2_FieldNameConvert2utf8.py` 不隔離；DB 連線設定不可硬編碼在程式內。
- 隔離不再使用的 static doc artifacts：root `index.html`、`df_style.css`、`HTML/`，以及只用於舊 static HTML/SQL 輸出的 `_Source/3_CreateIndexHtml.py`、`_Source/4_CreateTableStructureHtml.py`、`_Source/5_CreateTableStructureSQL.py`。
- 保留 `_Source/*.json` schema metadata、relationship、`skill_scripts/`、`tests/skill_scripts/`、`test_db/` 作為 SQL 生成與驗證基礎。
- E2E 測試必須使用 Docker 內 PostgreSQL 當成 MS-SQL substitute，建立真實測試 schema 與資料，執行真實 SQL，不使用 fake、smoke、mock。
- SQL 執行只允許唯讀 `SELECT`；任何 `INSERT`、`UPDATE`、`DELETE`、`DROP`、`ALTER`、`EXEC`、`MERGE`、`TRUNCATE`、`xp_` 類語法必須被阻擋。
- 報告 HTML 由 React renderer 產生，不再依賴舊 `index.html` 或 `HTML/*.html`。

## Desired End State

- `_Source/1_mssql_to_json.py` 從 `WFERP_SCHEMA_DB_*` 環境變數讀取 schema rebuild DB 設定。
- `skill_scripts/cli_generate_select.py` 或新增 harness entrypoint 可支援費用分析類需求，產出 WFERP schema 對應 SQL，並可在本地 PostgreSQL E2E fixture 上執行驗證。
- 新增 Excel intake parser，可解析使用者上傳 workbook 中的需求欄位、使用者公式欄位、公式 lineage、輸出報表 sheet 結構。
- 新增 report harness state schema 與 checkpoint payload，讓 skill 能生成互動 HTML 給使用者確認：需求欄位/公式、SQL、資料預覽、報告格式、報告初稿、最終審核。
- 新增 React renderer project，使用 React 產生 checkpoint/final report HTML，可套用 beautiful-article/reacticle 作法與 report design repository。
- `/home/timmypai/.codex/skills/wferp-report/` 存在可用的 local Codex skill：`SKILL.md`、references、report designs、validator prompts、harness instructions。
- 新增一個費用分析本地端 E2E：Docker PostgreSQL 建資料、seed deterministic data、產 SQL、轉譯安全子集、執行查詢、驗證 rows/columns/aggregates/percentages/exclusions。

## Implementation Strategy

先做可量化、可測試的核心路徑，再補上 skill 與 React 互動層：

1. DB config externalization 與舊 artifacts 隔離是低風險基礎整理。
2. 費用分析 SQL 生成與 PostgreSQL E2E 是端到端驗收核心。
3. Excel intake 與 report harness state 讓 skill 能理解上傳檔案與公式需求。
4. React renderer 與 local skill 檔案最後接上全流程互動。

每一組工作都先寫 failing test，再實作，再跑對應測試。每個 major milestone 建議獨立 commit。

## Task 1: Externalize Schema Rebuild DB Config

### Files

- Add: `_Source/schema_db_config.py`
- Modify: `_Source/1_mssql_to_json.py`
- Add: `tests/source/test_schema_db_config.py`
- Modify: `INSTALLATION.md`
- Modify: `OPERATIONS.md`

### Tests First

新增 `tests/source/test_schema_db_config.py`，用 `importlib.util.spec_from_file_location` 載入 `_Source/schema_db_config.py`，避免 `_Source` 不是 package 的問題。

Test cases:

- `test_schema_db_config_reads_required_env`
- `test_schema_db_config_defaults_port_and_database`
- `test_schema_db_config_rejects_missing_host_username_password`
- `test_schema_db_config_redacts_password_for_logging`

Expected initial command:

```bash
pytest tests/source/test_schema_db_config.py -v
```

Expected initial result: fail because `_Source/schema_db_config.py` does not exist.

### Implementation

`_Source/schema_db_config.py` 提供：

```python
from dataclasses import dataclass
import os


class SchemaDbConfigError(ValueError):
    pass


@dataclass(frozen=True)
class SchemaDbConfig:
    host: str
    port: int
    database: str
    username: str
    password: str

    @classmethod
    def from_env(cls, environ=None):
        env = os.environ if environ is None else environ
        missing = [
            name
            for name in ("WFERP_SCHEMA_DB_HOST", "WFERP_SCHEMA_DB_USERNAME", "WFERP_SCHEMA_DB_PASSWORD")
            if not env.get(name)
        ]
        if missing:
            raise SchemaDbConfigError("Missing schema DB env vars: " + ", ".join(missing))
        return cls(
            host=env["WFERP_SCHEMA_DB_HOST"],
            port=int(env.get("WFERP_SCHEMA_DB_PORT", "1433")),
            database=env.get("WFERP_SCHEMA_DB_DATABASE", "DSCSYS"),
            username=env["WFERP_SCHEMA_DB_USERNAME"],
            password=env["WFERP_SCHEMA_DB_PASSWORD"],
        )

    def redacted(self):
        return {
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "username": self.username,
            "password": "***",
        }
```

`_Source/1_mssql_to_json.py` 移除 `SERVER_IP`、`USERNAME`、`PASSWORD`、`DATABASE` 硬編碼，改用：

```python
from schema_db_config import SchemaDbConfig

config = SchemaDbConfig.from_env()
conn = pymssql.connect(
    server=config.host,
    port=config.port,
    user=config.username,
    password=config.password,
    database=config.database,
    charset="utf8",
)
```

### Verification

```bash
pytest tests/source/test_schema_db_config.py -v
python3 -m py_compile _Source/schema_db_config.py _Source/1_mssql_to_json.py
rg "SERVER_IP|USERNAME|PASSWORD|DATABASE =" _Source/1_mssql_to_json.py
```

Expected:

- pytest passes.
- py_compile passes.
- `rg` returns no old credential constants in `_Source/1_mssql_to_json.py`.

## Task 2: Quarantine Legacy Static HTML Artifacts

### Files

- Add: `scripts/quarantine_legacy_static_docs.py`
- Add: `tests/scripts/test_quarantine_legacy_static_docs.py`
- Runtime output after executing script once:
  - `legacy_static_docs/index.html`
  - `legacy_static_docs/df_style.css`
  - `legacy_static_docs/HTML/`
  - `legacy_static_docs/_Source/3_CreateIndexHtml.py`
  - `legacy_static_docs/_Source/4_CreateTableStructureHtml.py`
  - `legacy_static_docs/_Source/5_CreateTableStructureSQL.py`
  - `legacy_static_docs/manifest.json`

### Tests First

Test cases:

- `test_quarantine_dry_run_lists_expected_paths`
- `test_quarantine_moves_expected_paths_and_writes_manifest`
- `test_quarantine_is_idempotent_when_sources_already_moved`

Use `tmp_path` and copy tiny fixture files into a fake repo root. Do not operate on real repo in unit test.

Expected initial command:

```bash
pytest tests/scripts/test_quarantine_legacy_static_docs.py -v
```

Expected initial result: fail because script does not exist.

### Implementation

Script contract:

```bash
python3 scripts/quarantine_legacy_static_docs.py --repo-root /home/timmypai/.codex/worktrees/5f5b/wferp --dry-run
python3 scripts/quarantine_legacy_static_docs.py --repo-root /home/timmypai/.codex/worktrees/5f5b/wferp
```

Behavior:

- Create `legacy_static_docs/`.
- Move only listed legacy paths.
- Preserve relative path under quarantine.
- Write manifest with source path, destination path, moved_at ISO timestamp, reason.
- If a source path is already absent and destination exists, record `already_quarantined`.
- Never move `_Source/*.json`, `_Source/1_mssql_to_json.py`, `_Source/2_FieldNameConvert2utf8.py`, `skill_scripts/`, `test_db/`, `tests/`.

### Verification

```bash
pytest tests/scripts/test_quarantine_legacy_static_docs.py -v
python3 scripts/quarantine_legacy_static_docs.py --repo-root /home/timmypai/.codex/worktrees/5f5b/wferp --dry-run
python3 scripts/quarantine_legacy_static_docs.py --repo-root /home/timmypai/.codex/worktrees/5f5b/wferp
test -f legacy_static_docs/index.html
test -d legacy_static_docs/HTML
test -f legacy_static_docs/_Source/3_CreateIndexHtml.py
test -f _Source/1_mssql_to_json.py
test -f _Source/2_FieldNameConvert2utf8.py
```

## Task 3: Add Expense Analysis SQL Generation Path

### Files

- Modify: `skill_scripts/sql_generator.py`
- Modify or add tests in: `tests/skill_scripts/test_sql_generator.py`
- Modify if necessary: `skill_scripts/prompt_sql_consistency.py`
- Modify if necessary: `tests/skill_scripts/test_prompt_sql_consistency.py`

### Tests First

新增 deterministic tests，不能使用 `LLM_MOCK_RESPONSE`。

Test cases:

- `test_generates_expense_analysis_sql_for_2026_q1`
- `test_expense_analysis_sql_uses_acpta_acptb_join`
- `test_expense_analysis_sql_excludes_void_and_unconfirmed_vouchers`
- `test_expense_analysis_sql_is_sql_server_2000_compatible`
- `test_expense_analysis_sql_uses_required_amount_fields`

Expected checks:

```python
assert "FROM [DSCSYS].[dbo].[ACPTA]" in sql
assert "JOIN [DSCSYS].[dbo].[ACPTB]" in sql
assert "TA001" in sql and "TA002" in sql
assert "TB001" in sql and "TB002" in sql
assert "TB014" in sql
assert "TB013" in sql
assert "SUM" in sql
assert "TB017" in sql
assert "TB018" in sql
assert "TA003 >= '20260101'" in sql
assert "TA003 <= '20260331'" in sql
assert "TA018 <> 'Y'" in sql
assert "TA024 = 'Y'" in sql
assert "WITH " not in sql.upper()
assert "OVER (" not in sql.upper()
```

Expected initial command:

```bash
pytest tests/skill_scripts/test_sql_generator.py -v
```

Expected initial result: fail because generator does not yet have expense-specific SQL.

### Implementation

Add a narrow deterministic branch in `generate_select_sql`:

- Trigger keywords: `費用`, `費用分析`, `部門費用`, `科目費用`, `Q1`, `第一季`, `2026`.
- Tables:
  - `ACPTA` header: voucher type/number/date/status.
  - `ACPTB` body: department/account/amount/tax.
- SQL Server target remains bracketed identifiers.
- Do not use modern SQL Server syntax. Use derived subquery for grand total percentage instead of window functions.

SQL shape:

```sql
SELECT
    detail.TB014 AS expense_department,
    detail.TB013 AS expense_account,
    SUM(detail.TB017) AS untaxed_amount,
    SUM(detail.TB018) AS tax_amount,
    SUM(detail.TB017 + detail.TB018) AS total_amount,
    CAST(
        CASE
            WHEN grand.grand_total_amount = 0 THEN 0
            ELSE SUM(detail.TB017 + detail.TB018) * 100.0 / grand.grand_total_amount
        END AS decimal(18, 4)
    ) AS total_amount_pct
FROM [DSCSYS].[dbo].[ACPTA] header
JOIN [DSCSYS].[dbo].[ACPTB] detail
    ON header.TA001 = detail.TB001
   AND header.TA002 = detail.TB002
CROSS JOIN (
    SELECT SUM(grand_detail.TB017 + grand_detail.TB018) AS grand_total_amount
    FROM [DSCSYS].[dbo].[ACPTA] grand_header
    JOIN [DSCSYS].[dbo].[ACPTB] grand_detail
        ON grand_header.TA001 = grand_detail.TB001
       AND grand_header.TA002 = grand_detail.TB002
    WHERE grand_header.TA003 >= '20260101'
      AND grand_header.TA003 <= '20260331'
      AND ISNULL(grand_header.TA018, '') <> 'Y'
      AND grand_header.TA024 = 'Y'
) grand
WHERE header.TA003 >= '20260101'
  AND header.TA003 <= '20260331'
  AND ISNULL(header.TA018, '') <> 'Y'
  AND header.TA024 = 'Y'
GROUP BY detail.TB014, detail.TB013, grand.grand_total_amount
ORDER BY total_amount DESC
```

If existing SQL validator rejects aliases in `ORDER BY`, order by aggregate expression instead:

```sql
ORDER BY SUM(detail.TB017 + detail.TB018) DESC
```

### Verification

```bash
pytest tests/skill_scripts/test_sql_generator.py -v
pytest tests/skill_scripts/test_prompt_sql_consistency.py -v
python3 -m skill_scripts.cli_generate_select --prompt "請產出2026第一季費用分析，依部門與會計科目彙總未稅金額、稅額、總額與占比" --mode rule
```

Expected:

- Unit tests pass.
- CLI prints SQL containing `ACPTA`, `ACPTB`, `TB014`, `TB013`, `TB017`, `TB018`.

## Task 4: Add PostgreSQL Readonly Adapter For Local E2E

### Files

- Add: `skill_scripts/postgres_readonly_adapter.py`
- Add: `tests/skill_scripts/test_postgres_readonly_adapter.py`

### Tests First

The adapter is only for test execution of a verified read-only SQL Server subset against PostgreSQL. It must not be used to make unsafe SQL acceptable.

Test cases:

- `test_translates_bracketed_schema_identifiers`
- `test_translates_top_to_limit`
- `test_translates_isnull_to_coalesce`
- `test_preserves_readonly_select_semantics`
- `test_rejects_non_select_before_translation`
- `test_rejects_semicolon_chained_statements`

Expected initial command:

```bash
pytest tests/skill_scripts/test_postgres_readonly_adapter.py -v
```

Expected initial result: fail because adapter does not exist.

### Implementation

Expose:

```python
class PostgresReadonlyAdapterError(ValueError):
    pass


def translate_sqlserver_select_to_postgres(sql: str) -> str:
    ...
```

Supported transforms:

- `[DSCSYS].[dbo].[ACPTA]` -> `dbo."ACPTA"`
- `[DSCSYS].[dbo].[ACPTB]` -> `dbo."ACPTB"`
- `[Column]` -> `"Column"` for simple identifiers if generated SQL includes column brackets.
- `ISNULL(` -> `COALESCE(`
- `SELECT TOP 20 ...` -> `SELECT ... LIMIT 20`
- SQL Server `decimal(18, 4)` remains accepted by PostgreSQL as `decimal(18, 4)`.

Safety checks before and after translation:

- Exactly one statement.
- Must start with `SELECT`.
- Reject blocked keywords with word boundaries: `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `EXEC`, `MERGE`, `TRUNCATE`, `CREATE`, `GRANT`, `REVOKE`.
- Reject comments `--`, `/*`.

### Verification

```bash
pytest tests/skill_scripts/test_postgres_readonly_adapter.py -v
python3 -m py_compile skill_scripts/postgres_readonly_adapter.py
```

## Task 5: Add PostgreSQL E2E Test Database Fixture

### Files

- Add: `test_db/docker-compose.postgres-e2e.yml`
- Add: `test_db/postgres_e2e/01_create_expense_fixture.sql`
- Add: `test_db/postgres_e2e/README.md`

### Fixture Contract

Use PostgreSQL service name `wferp-postgres-e2e`, database `wferp_e2e`, user `wferp`, password `wferp_pass`.

DDL:

```sql
CREATE SCHEMA IF NOT EXISTS dbo;

CREATE TABLE dbo."ACPTA" (
    "TA001" varchar(4) NOT NULL,
    "TA002" varchar(20) NOT NULL,
    "TA003" varchar(8) NOT NULL,
    "TA018" varchar(1),
    "TA024" varchar(1) NOT NULL,
    PRIMARY KEY ("TA001", "TA002")
);

CREATE TABLE dbo."ACPTB" (
    "TB001" varchar(4) NOT NULL,
    "TB002" varchar(20) NOT NULL,
    "TB003" varchar(4) NOT NULL,
    "TB013" varchar(20) NOT NULL,
    "TB014" varchar(20) NOT NULL,
    "TB017" numeric(18, 2) NOT NULL,
    "TB018" numeric(18, 2) NOT NULL,
    PRIMARY KEY ("TB001", "TB002", "TB003"),
    FOREIGN KEY ("TB001", "TB002") REFERENCES dbo."ACPTA" ("TA001", "TA002")
);
```

Seed expected included rows:

| Department | Account | Untaxed | Tax | Total |
| --- | --- | ---: | ---: | ---: |
| D001 | 6101 | 22000.00 | 1100.00 | 23100.00 |
| D001 | 6201 | 15000.00 | 750.00 | 15750.00 |
| D002 | 6101 | 24000.00 | 1200.00 | 25200.00 |
| D002 | 6201 | 36000.00 | 1800.00 | 37800.00 |
| D003 | 6101 | 24000.00 | 1200.00 | 25200.00 |
| D003 | 6201 | 9000.00 | 450.00 | 9450.00 |

Grand totals:

- included detail rows: `12`
- grouped rows: `6`
- untaxed total: `130000.00`
- tax total: `6500.00`
- total amount: `136500.00`
- department totals:
  - D001: `38850.00`
  - D002: `63000.00`
  - D003: `34650.00`
- percentage total tolerance: `99.9999 <= sum(total_amount_pct) <= 100.0001`

Excluded control rows:

- one 2025 row with total `999999.00`, excluded by date.
- one 2026 Q1 row with `TA024 = 'N'`, excluded by confirmation status.
- one 2026 Q1 row with `TA018 = 'Y'`, excluded by void status.

### Verification

```bash
docker compose -f test_db/docker-compose.postgres-e2e.yml up -d
docker exec -i wferp-postgres-e2e psql -U wferp -d wferp_e2e -f /init/01_create_expense_fixture.sql
docker exec -i wferp-postgres-e2e psql -U wferp -d wferp_e2e -c "SELECT COUNT(*) FROM dbo.\"ACPTA\";"
docker exec -i wferp-postgres-e2e psql -U wferp -d wferp_e2e -c "SELECT COUNT(*) FROM dbo.\"ACPTB\";"
```

Expected:

- ACPTA count includes approved and excluded voucher headers.
- ACPTB count includes 12 included detail rows plus excluded control rows.

## Task 6: Add Real Expense Analysis E2E Test

### Files

- Add: `tests/skill_scripts/test_expense_analysis_postgres_e2e.py`
- Add: `scripts/run_expense_analysis_postgres_e2e.sh`
- Modify: `INSTALLATION.md`
- Modify: `OPERATIONS.md`

### Tests First

Use real generator and real database. Do not use LLM response fixtures. The test may skip with an explicit message if `WFERP_RUN_POSTGRES_E2E=1` is not set, but the runner script must set it and run the full path.

Test cases:

- `test_expense_analysis_query_executes_against_postgres_fixture`
- `test_expense_analysis_rows_columns_and_totals_match_fixture`
- `test_expense_analysis_excluded_rows_are_not_counted`
- `test_expense_analysis_percentage_sum_is_approximately_100`
- `test_expense_analysis_query_contains_no_blocked_sql`

Expected initial command after adding test:

```bash
WFERP_RUN_POSTGRES_E2E=1 pytest tests/skill_scripts/test_expense_analysis_postgres_e2e.py -v
```

Expected initial result: fail until Tasks 3-5 are complete and PostgreSQL dependency/client path exists.

### Implementation

Add test dependency path:

- Prefer `psycopg` if available.
- If repo keeps manual dependencies only, document:

```bash
python3 -m pip install psycopg[binary]
```

Test structure:

```python
def test_expense_analysis_rows_columns_and_totals_match_fixture():
    sql = generate_select_sql(
        prompt="請產出2026第一季費用分析，依部門與會計科目彙總未稅金額、稅額、總額與占比",
        mode="rule",
    )
    translated = translate_sqlserver_select_to_postgres(sql)
    rows = execute_postgres(translated)

    assert len(rows) == 6
    assert set(rows[0].keys()) == {
        "expense_department",
        "expense_account",
        "untaxed_amount",
        "tax_amount",
        "total_amount",
        "total_amount_pct",
    }
    assert_decimal_sum(rows, "untaxed_amount", "130000.00")
    assert_decimal_sum(rows, "tax_amount", "6500.00")
    assert_decimal_sum(rows, "total_amount", "136500.00")
```

Runner script:

```bash
#!/usr/bin/env bash
set -euo pipefail

docker compose -f test_db/docker-compose.postgres-e2e.yml up -d
docker exec -i wferp-postgres-e2e psql -U wferp -d wferp_e2e -f /init/01_create_expense_fixture.sql
export WFERP_RUN_POSTGRES_E2E=1
export WFERP_POSTGRES_E2E_DSN="postgresql://wferp:wferp_pass@127.0.0.1:55432/wferp_e2e"
pytest tests/skill_scripts/test_expense_analysis_postgres_e2e.py -v
```

### Quantitative Acceptance

Pass criteria:

- Generated SQL starts with `SELECT`.
- Blocked keyword count is `0`.
- Query returns exactly `6` grouped rows.
- Returned columns exactly match expected column set.
- Untaxed total equals `130000.00`.
- Tax total equals `6500.00`.
- Total amount equals `136500.00`.
- D002/6201 is top row by `total_amount` with `37800.00`.
- Excluded totals `999999.00`, `7777.00`, `8888.00` do not appear in any aggregate.
- Sum of `total_amount_pct` is within `0.0001` of `100.0000`.

### Verification

```bash
bash scripts/run_expense_analysis_postgres_e2e.sh
pytest tests/skill_scripts/test_postgres_readonly_adapter.py -v
pytest tests/skill_scripts/test_sql_generator.py -v
```

## Task 7: Add Excel Requirement Intake And Formula Lineage Parser

### Files

- Add: `skill_scripts/excel_intake.py`
- Add: `tests/skill_scripts/test_excel_intake.py`
- Add fixtures:
  - `tests/fixtures/expense_analysis_requirement.xlsx`
  - or generated inside test using `openpyxl`
- Modify: `INSTALLATION.md`

### Tests First

Use a real workbook, not CSV-only substitute. The workbook must contain:

- `需求欄位` sheet: WFERP table/field hints and display names.
- `自訂公式` sheet: user-defined fields with formulas.
- `管理報表` sheet: intended output columns and formulas linking back to requirement fields.

Test cases:

- `test_reads_required_database_fields_from_workbook`
- `test_reads_user_formula_fields`
- `test_extracts_formula_references`
- `test_detects_formula_columns_without_database_source`
- `test_builds_confirmation_payload_in_chinese`

Expected initial command:

```bash
pytest tests/skill_scripts/test_excel_intake.py -v
```

Expected initial result: fail because parser does not exist.

### Implementation

Add dependency documentation:

```bash
python3 -m pip install openpyxl
```

Expose:

```python
@dataclass(frozen=True)
class WorkbookRequirement:
    database_fields: list[DatabaseFieldRequirement]
    formula_fields: list[FormulaFieldRequirement]
    report_fields: list[ReportFieldRequirement]
    formula_lineage: list[FormulaLineage]
    warnings: list[str]


def parse_excel_requirement(path: str) -> WorkbookRequirement:
    ...


def build_excel_confirmation_payload(requirement: WorkbookRequirement) -> dict:
    ...
```

Formula lineage requirements:

- Preserve formula text, e.g. `=未稅金額+稅額`.
- Extract referenced display fields.
- Mark references as:
  - database-backed
  - formula-backed
  - unresolved
- Produce Chinese confirmation payload sections:
  - `資料庫欄位`
  - `使用者公式欄位`
  - `報表輸出欄位`
  - `需使用者確認`

### Verification

```bash
pytest tests/skill_scripts/test_excel_intake.py -v
python3 -m py_compile skill_scripts/excel_intake.py
```

## Task 8: Add Report Harness State And Checkpoint Payloads

### Files

- Add: `skill_scripts/report_harness_state.py`
- Add: `skill_scripts/report_harness.py`
- Add: `tests/skill_scripts/test_report_harness_state.py`
- Add: `tests/skill_scripts/test_report_harness.py`

### Tests First

Test cases:

- `test_creates_run_directory_with_state_json`
- `test_records_excel_confirmation_checkpoint`
- `test_records_sql_review_checkpoint`
- `test_records_data_preview_checkpoint`
- `test_records_report_selection_checkpoint`
- `test_rejects_state_transition_without_required_confirmation`
- `test_all_checkpoint_payloads_have_chinese_titles_and_actions`

Expected initial command:

```bash
pytest tests/skill_scripts/test_report_harness_state.py tests/skill_scripts/test_report_harness.py -v
```

Expected initial result: fail because harness state does not exist.

### Implementation

Run directory shape:

```text
wferp-report-runs/<run-id>/
  state.json
  inputs/
  sql/
  data/
  checkpoints/
    01_excel_confirmation.json
    02_sql_review.json
    03_data_preview.json
    04_report_selection.json
    05_report_draft.json
    06_final_review.json
  reports/
```

State schema fields:

- `run_id`
- `prompt`
- `input_files`
- `schema_snapshot`
- `excel_requirement`
- `sql_candidate`
- `sql_validation`
- `execution_result_summary`
- `report_type`
- `report_design`
- `report_options`
- `validator_results`
- `user_confirmations`

Checkpoint actions must be explicit:

- Excel confirmation: `確認欄位與公式`, `要求修正`
- SQL review: `同意查詢`, `調整需求`
- Data preview: `資料正確`, `重新查詢`
- Report selection: `產生報告`, `修改格式`
- Draft review: `接受`, `修正報告`
- Final review: `完成`, `回到初稿`

### Verification

```bash
pytest tests/skill_scripts/test_report_harness_state.py tests/skill_scripts/test_report_harness.py -v
python3 -m py_compile skill_scripts/report_harness_state.py skill_scripts/report_harness.py
```

## Task 9: Add Report Type Catalog And Design Repository

### Files In Repo

- Add: `report_designs/README.md`
- Add: `report_designs/design.md`
- Add: `report_designs/executive-summary.md`
- Add: `report_designs/financial-control.md`
- Add: `report_designs/operations-review.md`
- Add: `report_designs/exception-audit.md`
- Add: `report_designs/trend-briefing.md`
- Add: `report_designs/detail-ledger.md`
- Add: `skill_scripts/report_catalog.py`
- Add: `tests/skill_scripts/test_report_catalog.py`

### Files In Local Skill

Mirror the same design repository into:

- `/home/timmypai/.codex/skills/wferp-report/report_designs/`

### Tests First

Test cases:

- `test_report_catalog_contains_required_report_types`
- `test_report_designs_are_loadable_markdown`
- `test_each_design_declares_required_sections`
- `test_default_options_include_chart_table_analysis_recommendation_flags`

Required report types:

- 明細查詢表
- 彙總統計表
- 趨勢分析表
- 比較分析表
- 異常稽核表
- 管理摘要
- 完整分析報告

Expected initial command:

```bash
pytest tests/skill_scripts/test_report_catalog.py -v
```

Expected initial result: fail because catalog does not exist.

### Implementation

`report_designs/design.md` defines common contract:

- `id`
- `name`
- `best_for`
- `required_sections`
- `optional_sections`
- `visual_policy`
- `table_policy`
- `analysis_policy`
- `recommendation_policy`
- `react_component_hints`
- `validator_checklist`

`skill_scripts/report_catalog.py` exposes:

```python
def list_report_types() -> list[dict]:
    ...


def list_report_designs(design_dir: str | Path | None = None) -> list[dict]:
    ...


def build_report_selection_payload() -> dict:
    ...
```

### Verification

```bash
pytest tests/skill_scripts/test_report_catalog.py -v
rg "管理摘要|完整分析報告|financial-control|executive-summary" report_designs skill_scripts
```

## Task 10: Add React Renderer Project

### Files

- Add: `report_renderer/package.json`
- Add: `report_renderer/index.html`
- Add: `report_renderer/src/main.tsx`
- Add: `report_renderer/src/App.tsx`
- Add: `report_renderer/src/components/CheckpointPage.tsx`
- Add: `report_renderer/src/components/ReportPage.tsx`
- Add: `report_renderer/src/components/DataPreviewTable.tsx`
- Add: `report_renderer/src/components/ReportOptionPanel.tsx`
- Add: `report_renderer/src/styles.css`
- Add: `report_renderer/examples/expense-analysis-checkpoint.json`
- Add: `report_renderer/examples/expense-analysis-report.json`
- Add: `report_renderer/tests/renderer.spec.ts`

### Tests First

Use Vitest or Playwright depending on installed frontend stack. If adding dependencies is required, ask for network escalation.

Renderer tests:

- `renders checkpoint page title in Chinese`
- `renders SQL review payload without executing SQL`
- `renders data preview table with row count`
- `renders report type choices`
- `renders final report sections`
- `does not render legacy iframe or static HTML links`

Expected initial command:

```bash
cd report_renderer
npm test
```

Expected initial result: fail until renderer exists and dependencies are installed.

### Implementation

Use React rendering only. The renderer consumes JSON from `window.__WFERP_REPORT_PAYLOAD__` or `?payload=<path>` during local development. It must not connect to DB.

Component rules:

- Checkpoint pages are real interaction surfaces: clear title, data preview, action buttons.
- Final report supports charts/tables/analysis/recommendations based on selected options.
- Use restrained business-report styling, not landing page style.
- Avoid old `index.html` and `HTML/*.html`.
- If beautiful-article/reacticle components are locally available, use their component protocol and theme constraints. If the dependency is not installable, implement a compatible internal component layer and document the deviation in `report_renderer/README.md`.

### Verification

```bash
cd report_renderer
npm install
npm test
npm run build
npm run dev -- --host 127.0.0.1 --port 4173
```

Browser QA:

- Open `http://127.0.0.1:4173`.
- Verify checkpoint example renders.
- Verify final report example renders.
- Verify no console errors.
- Verify desktop and mobile widths do not overlap text/table controls.

## Task 11: Add Local Skill `/home/timmypai/.codex/skills/wferp-report`

### Files

Create outside worktree:

```text
/home/timmypai/.codex/skills/wferp-report/
  SKILL.md
  references/
    harness.md
    db-config.md
    schema-context.md
    excel-intake.md
    sql-safety.md
    validators.md
    react-renderer.md
    e2e-expense-analysis.md
  report_designs/
    design.md
    executive-summary.md
    financial-control.md
    operations-review.md
    exception-audit.md
    trend-briefing.md
    detail-ledger.md
  assets/
    sample-expense-analysis-prompt.md
```

### Tests First

Because this is outside worktree, add repo-side validator script and tests:

- Add: `scripts/validate_local_wferp_report_skill.py`
- Add: `tests/scripts/test_validate_local_wferp_report_skill.py`

Test cases:

- `test_validator_accepts_complete_skill_tree`
- `test_validator_rejects_missing_skill_md`
- `test_validator_requires_harness_sections`
- `test_validator_requires_validator_references`
- `test_validator_requires_report_designs`

Expected initial command:

```bash
pytest tests/scripts/test_validate_local_wferp_report_skill.py -v
```

Expected initial result: fail until validator exists.

### Implementation

`SKILL.md` must instruct Codex to:

1. Intake prompt and uploaded files.
2. Build source inventory.
3. Parse Excel fields/formulas if workbook exists.
4. Generate Excel confirmation HTML.
5. Map requested fields to WFERP schema/relationship.
6. Generate read-only SQL.
7. Validate SQL safety locally.
8. Execute only after user confirmation and DB policy allows.
9. Present data preview HTML.
10. Ask user to choose report type/design/options.
11. Generate report draft HTML via React renderer.
12. Run validators using subagents.
13. Present final report and validation evidence.

Validator references must define subagent roles:

- 需求/來源 validator
- Excel 欄位與公式 validator
- SQL 安全 validator
- Schema/relationship validator
- Data preview validator
- 報告內容 validator
- 視覺/技術 validator

### Verification

```bash
pytest tests/scripts/test_validate_local_wferp_report_skill.py -v
python3 scripts/validate_local_wferp_report_skill.py --skill-root /home/timmypai/.codex/skills/wferp-report
```

Expected:

- Validator passes on local skill tree.

## Task 12: Wire CLI/Harness Entry Points

### Files

- Modify: `skill_scripts/cli_generate_select.py`
- Add: `skill_scripts/cli_report_harness.py`
- Add: `tests/skill_scripts/test_cli_report_harness.py`
- Modify: `OPERATIONS.md`

### Tests First

Test cases:

- `test_cli_report_harness_creates_run_from_prompt_only`
- `test_cli_report_harness_accepts_excel_input_path`
- `test_cli_report_harness_builds_excel_checkpoint`
- `test_cli_report_harness_builds_sql_checkpoint`
- `test_cli_report_harness_does_not_execute_db_without_confirmation_flag`
- `test_cli_report_harness_requires_allow_non_test_db_execution_for_non_test_env`

Expected initial command:

```bash
pytest tests/skill_scripts/test_cli_report_harness.py -v
```

Expected initial result: fail because CLI does not exist.

### Implementation

CLI shape:

```bash
python3 -m skill_scripts.cli_report_harness \
  --prompt "請產出2026第一季費用分析，依部門與會計科目彙總" \
  --input-file /path/to/需求.xlsx \
  --run-dir wferp-report-runs/expense-analysis-demo \
  --mode rule \
  --checkpoint excel
```

Execution step:

```bash
python3 -m skill_scripts.cli_report_harness \
  --run-dir wferp-report-runs/expense-analysis-demo \
  --confirm-sql \
  --validate-execution
```

Report generation step:

```bash
python3 -m skill_scripts.cli_report_harness \
  --run-dir wferp-report-runs/expense-analysis-demo \
  --report-type 管理摘要 \
  --report-design financial-control \
  --include-chart \
  --include-table \
  --include-analysis \
  --include-recommendations
```

### Verification

```bash
pytest tests/skill_scripts/test_cli_report_harness.py -v
python3 -m skill_scripts.cli_report_harness --help
```

## Task 13: Add Validator Prompts And Evidence Packets

### Files

- Add: `skill_scripts/validator_contracts.py`
- Add: `tests/skill_scripts/test_validator_contracts.py`
- Add local skill references:
  - `/home/timmypai/.codex/skills/wferp-report/references/validators.md`

### Tests First

Test cases:

- `test_validator_contracts_include_required_roles`
- `test_validator_contract_requires_status_evidence_and_findings`
- `test_validator_contract_rejects_missing_quantitative_checks_for_data_validator`
- `test_report_final_review_requires_all_validators_pass_or_explicit_user_acceptance`

Expected initial command:

```bash
pytest tests/skill_scripts/test_validator_contracts.py -v
```

Expected initial result: fail because contracts do not exist.

### Implementation

Evidence packet JSON shape:

```json
{
  "validator": "sql_safety",
  "status": "pass",
  "checked_at": "2026-06-18T00:00:00+08:00",
  "inputs": ["sql/expense_analysis.sql"],
  "checks": [
    {
      "name": "readonly_select_only",
      "status": "pass",
      "evidence": "SQL starts with SELECT and contains zero blocked keywords."
    }
  ],
  "findings": [],
  "residual_risks": []
}
```

Required validators:

- `source_intake`
- `excel_formula`
- `sql_safety`
- `schema_relationship`
- `data_preview`
- `report_content`
- `visual_technical`

### Verification

```bash
pytest tests/skill_scripts/test_validator_contracts.py -v
```

## Task 14: Full Regression And Documentation Pass

### Files

- Modify: `README.md` if present.
- Modify: `INSTALLATION.md`
- Modify: `OPERATIONS.md`
- Modify: `docs/superpowers/specs/2026-06-18-wferp-report-skill-and-react-renderer-design.md` only if implementation discovers a necessary correction.

### Verification Commands

Run focused backend tests:

```bash
pytest tests/source/test_schema_db_config.py -v
pytest tests/scripts/test_quarantine_legacy_static_docs.py -v
pytest tests/scripts/test_validate_local_wferp_report_skill.py -v
pytest tests/skill_scripts/test_sql_generator.py -v
pytest tests/skill_scripts/test_postgres_readonly_adapter.py -v
pytest tests/skill_scripts/test_excel_intake.py -v
pytest tests/skill_scripts/test_report_catalog.py -v
pytest tests/skill_scripts/test_report_harness_state.py tests/skill_scripts/test_report_harness.py -v
pytest tests/skill_scripts/test_cli_report_harness.py -v
pytest tests/skill_scripts/test_validator_contracts.py -v
```

Run required real E2E:

```bash
bash scripts/run_expense_analysis_postgres_e2e.sh
```

Run existing suite:

```bash
pytest tests/skill_scripts/ -v
```

Run renderer checks:

```bash
cd report_renderer
npm test
npm run build
```

Final repository checks:

```bash
git status --short
python3 - <<'PY'
from pathlib import Path
markers = ["TO" + "DO", "TB" + "D", "place" + "holder", "待" + "定"]
roots = [
    Path("docs/superpowers/plans"),
    Path("docs/superpowers/specs"),
    Path("skill_scripts"),
    Path("tests"),
    Path("report_designs"),
    Path("report_renderer"),
]
for root in roots:
    if not root.exists():
        continue
    for path in root.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="ignore")
            for marker in markers:
                if marker in text:
                    print(f"{path}: contains unfinished marker {marker}")
PY
rg "SERVER_IP|USERNAME|PASSWORD|DATABASE =" _Source/1_mssql_to_json.py || true
```

Expected:

- All focused tests pass.
- Expense E2E passes with real Docker PostgreSQL execution.
- Existing `tests/skill_scripts/` pass.
- Renderer test/build pass.
- No accidental old credential constants remain.
- Git status only contains intentional changes.

## Commit Plan

Recommended commits:

1. `refactor: externalize schema rebuild database config`
2. `chore: quarantine legacy static docs`
3. `feat: add expense analysis SQL generation`
4. `test: add postgres expense analysis e2e`
5. `feat: parse excel report requirements`
6. `feat: add report harness and catalog`
7. `feat: add react report renderer`
8. `feat: install local wferp report skill`
9. `docs: document wferp report workflow`

## Risk Controls

- Keep SQL generation deterministic for the E2E path; LLM-based generation can remain an optional future path, but this plan's acceptance cannot depend on an LLM.
- Treat PostgreSQL adapter as test-only. Do not claim PostgreSQL is production target for WFERP.
- Keep report renderer pure: it consumes payload JSON and does not read DB env vars or execute SQL.
- Any write to `/home/timmypai/.codex/skills/wferp-report/` must request sandbox escalation during implementation.
- If dependency install is needed (`openpyxl`, `psycopg`, frontend packages), request network escalation and record exact installed package versions in docs.

## Goal Prompt For Implementation Worker

Paste the following prompt into a fresh Codex worker when ready to execute this implementation plan:

```text
你是 Codex implementation worker。請在 repo `/home/timmypai/.codex/worktrees/5f5b/wferp` 依照 `/home/timmypai/.codex/worktrees/5f5b/wferp/docs/superpowers/plans/2026-06-18-wferp-report-skill-and-react-renderer.md` 完整執行。

必須遵守：
- 回覆使用者使用繁體中文。
- 先使用 `superpowers:executing-plans`，逐項執行 plan。
- 先寫 failing test，再實作，再跑對應驗證。
- 不可刪除或回復使用者既有變更。
- local skill 必須建立在 `/home/timmypai/.codex/skills/wferp-report/`，不可放入 worktree；需要寫入該路徑時依 sandbox 規則請求 escalation。
- 保留 `_Source/1_mssql_to_json.py` 與 `_Source/2_FieldNameConvert2utf8.py` 的 schema rebuild 功能，但 DB 連線設定必須改由 `WFERP_SCHEMA_DB_*` 環境變數提供，不可硬編碼 credentials。
- 將 root `index.html`、`df_style.css`、`HTML/` 與 `_Source/3_CreateIndexHtml.py`、`_Source/4_CreateTableStructureHtml.py`、`_Source/5_CreateTableStructureSQL.py` 移至隔離區，保留 schema JSON 與 SQL tooling。
- 新增費用分析 E2E：用 Docker PostgreSQL 當本地 MS-SQL substitute，建立真實 WFERP fixture schema/data，產生真實 SQL，經 test-only readonly adapter 轉譯後執行真實查詢。此 E2E 不可使用 fake、smoke、mock。
- E2E 量化驗收必須包含：6 grouped rows、untaxed total 130000.00、tax total 6500.00、total amount 136500.00、D002/6201 top row 37800.00、排除 2025/未確認/作廢控制資料、percentage sum 約等於 100。
- 新增 Excel intake，可解析需求欄位、使用者公式欄位、公式 lineage、管理報表輸出欄位，並產生中文確認 payload。
- 新增 report catalog/design repository，至少包含：明細查詢表、彙總統計表、趨勢分析表、比較分析表、異常稽核表、管理摘要、完整分析報告。
- 新增 React renderer，最終 checkpoint/report HTML 必須由 React 渲染，不使用舊 `index.html` 或 `HTML/*.html`。
- 新增 validator contracts，支援 source intake、excel formula、sql safety、schema relationship、data preview、report content、visual technical validator evidence packet。

驗證至少執行：
- `pytest tests/skill_scripts/ -v`
- `bash scripts/run_expense_analysis_postgres_e2e.sh`
- React renderer 的 `npm test` 與 `npm run build`，若 frontend dependencies 需要安裝，先請求 escalation。
- schema DB config、quarantine、local skill validator、Excel intake、report harness、report catalog、validator contracts 的 focused tests。

完成後請輸出：
1. 已完成的檔案與功能摘要。
2. 實際執行過的驗證命令與結果。
3. 若有未完成或被 sandbox/network 阻擋的項目，列出具體 blocker 與下一步。
4. 建議下一步是否 commit、merge 或請使用者試跑 skill。
```

## Execution Notes

- This plan intentionally separates design/spec from implementation. Do not start by rewriting the design spec unless implementation evidence contradicts it.
- Prefer small helpers over broad rewrites in existing `skill_scripts/`.
- Keep Chinese/Vietnamese metadata UTF-8 intact.
- Do not run destructive cleanup commands. Use the quarantine script for planned moves.

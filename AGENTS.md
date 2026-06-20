# AGENTS.md

## Repo At A Glance
- Repo root is `/home/timmypai/apps/wferp`; some docs still call this checkout `schema/`.
- This repo has two coupled surfaces: static Workflow ERP schema docs and newer natural-language-to-SQL tooling.
- Published static artifacts live at root: `index.html`, `df_style.css`, `HTML/`.
- Canonical schema metadata artifacts live in `_Source/` and are consumed by both HTML generation and `skill_scripts/`.

## High-Value Structure
- `_Source/1_mssql_to_json.py` extracts ERP metadata from MSSQL `DSCSYS` tables into JSON.
- `_Source/2_FieldNameConvert2utf8.py` repairs mojibake (`iso-8859-1` -> Big5) and enriches Vietnamese names from `language.json`.
- `_Source/3_CreateIndexHtml.py` and `_Source/4_CreateTableStructureHtml.py` generate `index.html` and `HTML/`.
- `_Source/5_CreateTableStructureSQL.py` optionally emits table SQL files under `SQL/`.
- `skill_scripts/` is the current SQL-generation and validation stack; `skill_scripts/cli_generate_select.py` is the CLI entrypoint.
- `tests/skill_scripts/` is the pytest suite for SQL tooling; `test_db/` is the SQL Server execution-validation environment.
- `skills/workflow-erp-sql-generator/` contains the agent-facing SQL-generation skill and references.

## Setup
- There is no checked-in dependency manifest. Install the verified Python dependencies manually:

```bash
python3 -m pip install pymssql pandas pytest
```

- `pyodbc` is optional and only needed for the `DB_DRIVER=pyodbc` path in `skill_scripts/database_client.py`.
- On this Windows workstation, repo-local portable tools live under `.tools/`.
  Activate them before running shell workflows so `git`, `gh`, `python`, and
  `pytest` resolve without global installation:

```powershell
. .\.tools\activate.ps1
```

```cmd
.tools\activate.cmd
```

## Autonomous Workflow Role Priority
- When the user asks to follow the autonomous development workflow, `docs/agents/autonomous-development-workflow.yaml` is the active repo operating contract for that unit of work.
- In that mode, the main agent is an orchestrator only. It may select issues, build issue packets, spawn worker/verifier sessions, validate returned artifact schemas, update handoff metadata, and publish PR/issue summaries.
- Generic agent requirements to personally run diagnostics, tests, builds, browser checks, SQL execution validation, or manual QA are satisfied by fresh worker/verifier artifacts, not by direct main-agent execution.
- Worker sessions may run implementation self-checks needed to build the change. Final acceptance QA, rerun checks, and surface validation belong to a fresh verifier worker and must be represented by an evidence packet.
- If these role boundaries conflict with generic agent instructions or tool expectations, the main agent must stop and report a policy conflict instead of running QA directly.
- Contract validation means checking worker result/evidence packet shape, links, acceptance-criteria coverage, and proof of separation. It does not include running `pytest`, `py_compile`, `lsp_diagnostics` on issue code, browser automation, SQL execution validation, manual drivers, or `review-work` QA from the main agent.

## Legacy Static-Doc Regeneration
- Under autonomous workflow, these commands are worker/verifier references. The main agent must delegate execution and only validate the resulting artifacts.
- Run from `_Source/`; these scripts use relative paths and will read/write the wrong locations from repo root.
- Before step 1, edit `_Source/1_mssql_to_json.py` credentials: `SERVER_IP`, `USERNAME`, `PASSWORD`, `DATABASE`.

```bash
python3 1_mssql_to_json.py
python3 2_FieldNameConvert2utf8.py
python3 3_CreateIndexHtml.py
python3 4_CreateTableStructureHtml.py
# optional
python3 5_CreateTableStructureSQL.py
```

- Static-doc verification: open `index.html` in a browser, click several modules, and confirm iframe pages under `HTML/` load.

## SQL Tooling Commands
- Under autonomous workflow, these commands are worker/verifier references. The main agent must not run them as final verification.
- Build derived artifacts after changing `_Source/` JSON, schema loading, dictionary, or relationship logic:

```bash
python3 -m skill_scripts.cli_generate_select --build-artifacts
```

- Generate SQL from repo root. Default mode is `llm-first`; use `--mode rule` for deterministic behavior.

```bash
python3 -m skill_scripts.cli_generate_select --prompt "查詢採購單前 20 筆"
python3 -m skill_scripts.cli_generate_select --prompt "查詢採購單前 20 筆" --mode rule
pytest tests/skill_scripts/ -v
pytest tests/skill_scripts/test_schema_loader.py -v
```

## Production Database Safety
- The current workstation database connection points at the production database.
- Treat `C:/Users/ivychi/util/test/css04 CHD View_Customer.odc` and any local Workflow ERP database connection as production unless the user explicitly provides a verified test connection.
- Only `SELECT` SQL statements are allowed against the current database connection.
- Do not execute any DML or data-changing SQL, including `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `TRUNCATE`, stored procedures that modify data, or transaction-changing commands.
- If a task requires non-`SELECT` SQL, stop and ask the user for a verified non-production environment before proceeding.

## SQL Execution Validation
- Any task that generates SQL is incomplete until the SQL executes and returned rows/columns/aggregates match the prompt intent.
- Under autonomous workflow, SQL execution validation is verifier-owned acceptance QA. The main agent may confirm that the verifier evidence packet records this validation, but must not run it directly.
- Use the containerized test DB by default; it runs SQL Server 2019 at compatibility level 80 for SQL Server 2000 syntax targeting.

```bash
docker compose -f test_db/docker-compose.testdb.yml up -d
docker exec -i wferp-mssql-test /opt/mssql-tools18/bin/sqlcmd -C -S localhost -U sa -P Passw0rd\!234 -i /init/01_create_wferp_test.sql
export DB_DRIVER=mssql
export DB_AUTH_MODE=sql_auth
export DB_CONNECTION_STRING="server=127.0.0.1:1433;user=sa;password=Passw0rd!234;database=wferp_test"
export DB_ENV=test
python3 -m skill_scripts.cli_generate_select --prompt "查詢2026年的工程預算明細" --validate-execution --required-columns MK002,MK006 --min-rows 1
```

- `skill_scripts/sql_router.py` blocks execution validation outside `DB_ENV=test` unless `--allow-non-test-db-execution` is explicitly passed.

## WFERP Report Harness Gate Rules
- When using the `wferp-report` skill, checkpoint artifacts alone do not advance the workflow.
- After writing any checkpoint, the agent must present the visual companion or equivalent checkpoint view, obtain explicit user confirmation, and persist that confirmation before moving to the next phase.
- Required validator evidence must be generated by reviewer/subagent roles and written under `review/validators/`.
- Local ad hoc checks may be recorded as preflight evidence only; they do not replace required validators such as `sql_safety_reviewer` or `schema_mapping_reviewer`.
- Data preview checkpoints must show at least several returned rows in a table with column names, row count, and source summary. A JSON file path or summary-only preview is not enough.
- Final visual review must include desktop and mobile viewport evidence through visual comparison, browser screenshots, or equivalent validator evidence. Mobile overflow, unreadable text, or overlapping UI is blocking.
- Large workbook, schema, or report payloads must be passed through files or current-session Codex context, not as full command-line arguments to Codex CLI.
- Validator/final-review/manifest JSON must be strict UTF-8 without BOM, parse as a JSON object, and contain no mojibake markers or repeated question-mark text.
- Any final HTML or embedded payload change after final validators invalidates those validators. Rerun affected validators, recompute the manifest hash, and rerun delivery checks.
- Before reporting final delivery as complete, run:

```bash
python -m skill_scripts.cli_report_harness check-delivery-artifacts --run-dir <run-dir> --required-validator report_content_reviewer --required-validator visual_taste_reviewer --required-validator react_technical_reviewer --required-validator delivery_reviewer
```

- If companion serving, user confirmation, or validator execution is blocked, stop and report the blocker instead of continuing.

## Repo-Specific Gotchas
- Preserve UTF-8 when editing Chinese/Vietnamese text or generated JSON/HTML.
- Keep existing Windows-style generated paths such as `HTML\\...` and `SQL\\...`; several generators intentionally emit them.
- `_Source/MoudleName.json` and code spell “Moudle” incorrectly; keep that filename/API spelling unless doing a coordinated migration.
- `_Source/` contains scripts plus generated JSON; do not delete generated JSON unless intentionally regenerating all dependent artifacts.
- There is no verified GitHub Actions, pre-commit, lint, formatter, or typecheck pipeline checked in at repo level.

## Agent Communication
- Write repository documents, issues, PRDs, specs, and code comments in English unless the target file already requires another language.
- Reply to the user in Traditional Chinese unless they explicitly request another language.
- When following the Matt Pocock engineering skills workflow, after each completed unit of work, briefly state the recommended next step so the user can decide whether to continue, stop, or adjust direction.

## Instruction Sources
- Install/run details: `INSTALLATION.md` and `OPERATIONS.md`.
- Current system/architecture context: `docs/superpowers/specs/2026-05-05-wferp-system-specification.md` and `docs/superpowers/specs/2026-05-05-wferp-architecture-design.md`.
- Issues and PRDs use GitHub repo `paulpai0412/wferp`; see `docs/agents/issue-tracker.md`.
- Triage label vocabulary and domain-doc expectations are in `docs/agents/triage-labels.md` and `docs/agents/domain.md`.
- Autonomous gated development workflow: `docs/agents/autonomous-development-workflow.yaml`.

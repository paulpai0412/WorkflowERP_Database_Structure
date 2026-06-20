---
name: wferp-report
description: "Use when the user needs a WFERP / Workflow ERP management report from a prompt, Excel workbook, ODC connection, or existing SQL evidence. Build the report through a small harness: intake -> source and Excel extraction -> normalized report plan -> field/formula checkpoint -> SELECT-only SQL review -> confirmed production read -> local SQLite enrichment -> data preview checkpoint -> report build -> final review -> single-file HTML delivery. Production database access is strictly read-only: only SELECT statements are allowed against css04 / CHD or any configured WFERP production connection."
---

# WFERP Report

## Purpose

Turn WFERP business requirements, Excel workbooks, and production read-only data into an auditable management report. The final deliverable is normally a single HTML report plus local evidence files: source inventory, field mapping, SELECT SQL, row counts, local SQLite database, report payload, validation results, and residual risks.

This skill follows a small harness style: clear phases, hard checkpoints, file-backed decisions, and repair after review. Do not rely only on chat memory. Record every important decision and evidence item in the run folder.

## Boundary

Use this skill for:
- WFERP / Workflow ERP management reports.
- Excel-backed report reconstruction and analysis.
- ODC or workbook connection inspection.
- Natural-language report requests that need SELECT SQL and local report artifacts.
- Single-file HTML reports with charts, tables, evidence, and validation notes.

Do not use this skill for:
- Production data maintenance or mutation.
- Generic web apps or dashboards with no WFERP data evidence.
- SQL-only tasks that do not need report planning or delivery artifacts.
- Any request that requires non-SELECT SQL against production.

If the user asks for mutation, stop and ask for a verified non-production environment. Do not improvise a workaround.

---

## Production Database Safety

The current workstation database connection is production unless the user provides a verified test connection.

Known production baseline:
- Data Source: `css04`
- Initial Catalog: `CHD`
- Provider: `SQLOLEDB.1`
- Common source object: `[CHD].[dbo].[View_Customer]`
- Reference file: `references/db-config.md`

Allowed against production:
- SELECT queries.
- SELECT TOP smoke tests.
- SELECT-only schema probes such as `SELECT TOP 0 * FROM ...`.

Forbidden against production:
- INSERT, UPDATE, DELETE, MERGE, TRUNCATE.
- DROP, ALTER, CREATE.
- EXEC or stored procedure calls.
- Transactional mutation or side-effect statements.
- Any script that builds or executes non-SELECT SQL against production.

Local artifacts may be written under the run folder, including CSV, SQLite, JSON, and HTML. Label those writes as local only.

---

## Harness Overview

```text
Phase 0  Intake and Boundary Check
   v
Phase 1  Source and Excel Extraction       -> source inventory + workbook evidence
   v
Phase 2  Normalized Report Planning        -> report plan + field mapping
   v
Checkpoint 1  Field, Formula, and Report Logic Confirmation  (must stop)
   v
Phase 3  SELECT SQL Draft and Safety Review -> sql review evidence, no DB execution yet
   v
Checkpoint 2  SQL Execution Confirmation   (must stop)
   v
Phase 4  Confirmed SELECT Execution         -> CSV + local SQLite + execution evidence
   v
Checkpoint 3  Data Preview and Design Confirmation (must stop)
   v
Phase 5  Report Build                       -> payload + scaffold + HTML draft
   v
Phase 6  Final Review                       -> content, data, visual, technical review
   v
Phase 7  Repair                             -> smallest necessary fixes
   v
Phase 8  Delivery                           -> single HTML + evidence summary
```

Hard rule: Checkpoints 1, 2, and 3 require explicit user confirmation unless the user has already given a direct instruction that covers that exact phase. Do not bundle independent decisions into one vague yes/no question.

---

## Run Workspace

Create one timestamped run folder for every report request:

```text
wferp-report-runs/<run-id>/
  source/
    source-inventory.json
    workbook-fields.json
    workbook-connections.json
    extraction-notes.md
  plan/
    normalized-report-plan.json
    report-plan.md
  checkpoints/
    01_field_formula.json
    02_sql_review.json
    03_data_preview.json
  sql/
    extract.sql
    sql-safety.json
  data/
    raw.csv
    raw-preview.json
    aggregate-checks.json
  sqlite/
    report.sqlite3
    manifest.json
  db/
    db-config.json
    query-execution.json
  report/
    payload/
      report-payload.json
    scaffold/
    delivery/
      report.html
  review/
    validators/
    final-review.md
    repair-log.md
```

Only create files that are relevant to the actual run, but keep names stable when the phase exists.

---

## Quality Protocol

Use review at phase boundaries. Keep review lightweight where the main agent already has hot context, and stronger where independent verification matters.

| Node | Review method | Artifact | Gate |
|---|---|---|---|
| Phase 1 Source | Main-agent checklist | `source/extraction-notes.md` | Required before planning |
| Phase 2 Plan | Main-agent checklist | `checkpoints/01_field_formula.json` | Required before SQL |
| Phase 3 SQL | SQL safety validator | `checkpoints/02_sql_review.json` and `sql/sql-safety.json` | Required before DB execution |
| Phase 4 DB read | Execution validator | `db/query-execution.json` | Required before data preview |
| Phase 4 SQLite | Local data validator | `sqlite/manifest.json` | Required before report build |
| Phase 5 Report | Payload and content validator | `review/validators/report-payload.json` | Required before final review |
| Phase 6 Final | Content, data, visual, technical review | `review/final-review.md` | Required before delivery |

A `fail` or `blocked` status stops downstream work until repaired. Fix the artifact first, then report what changed.

---

## Decision Collection Rules

At each checkpoint:
- List each decision separately.
- State the recommended option and why.
- Give the user a chance to override.
- Wait for the required answer before moving to the next phase.

Never say "I already chose X; tell me if wrong" for required decisions. Recommendation is allowed; silent choice is not.

Required checkpoint decisions:

Checkpoint 1, before SQL generation:
- Confirm interpreted workbook fields and formulas.
- Confirm report objective and metrics.
- Confirm dimensions, filters, and date logic.
- Confirm unresolved assumptions or manual exceptions.

Checkpoint 2, before production DB execution:
- Confirm the exact SELECT SQL to execute.
- Confirm source object and row/column scope.
- Confirm smoke test or preview limit, if any.
- Confirm that only SELECT will be executed.

Checkpoint 3, before report build:
- Confirm data preview and row counts.
- Confirm report layout and chart plan.
- Confirm local SQLite enrichment views.
- Confirm any residual risk or missing field.

---

## Phase 0 - Intake and Boundary Check

Capture:
- User objective.
- Attached files and paths.
- Expected report language.
- Report audience.
- Required measures, dimensions, filters, and date range.
- Whether production DB execution is requested or only SQL is needed.
- Whether the user has already authorized SELECT smoke tests or extraction.

Read `references/harness.md` and `references/db-config.md` when setting up the run.

If the request is missing required files or the user wants an app instead of a report, ask a focused question and stop.

---

## Phase 1 - Source and Excel Extraction

When an Excel workbook or ODC file is provided:
- Copy the workbook to the run folder if Excel has it locked.
- Extract workbook connections, pivot cache fields, table definitions, formulas, filters, and named ranges.
- Preserve exact workbook field names.
- Classify fields as dimension, date, measure, identifier, formula, lookup, manual, or unknown.
- Record low-confidence extraction notes.

Read as needed:
- `references/excel-intake.md`
- `references/field-classification.md`
- `references/schema-context.md`

Output:
- `source/source-inventory.json`
- `source/workbook-fields.json`
- `source/workbook-connections.json`
- `source/extraction-notes.md`

---

## Phase 2 - Normalized Report Planning

Produce a normalized plan before writing SQL.

Required plan sections:
- Objective and audience.
- Source files and source objects.
- Measures and dimensions.
- Workbook formula semantics.
- Filters and date logic.
- SQL extraction strategy.
- Local SQLite enrichment plan.
- Report sections, charts, and tables.
- Validators and acceptance criteria.
- Assumptions and open questions.

Output:
- `plan/normalized-report-plan.json`
- `plan/report-plan.md`
- `checkpoints/01_field_formula.json`

Read as needed:
- `references/report-plan-template.md`
- `references/checkpoint-payload-schema.md`
- `references/report-payload-schema.md`

Then stop at Checkpoint 1.

---

## Checkpoint 1 - Field, Formula, and Report Logic

Before SQL generation, show the user:
- Interpreted workbook fields.
- Measures, dimensions, and filters.
- Formula or pivot semantics.
- Proposed report sections and charts.
- Open assumptions.

Wait for confirmation. After confirmation, update `checkpoints/01_field_formula.json` and continue.

---

## Phase 3 - SELECT SQL Draft and Safety Review

Generate the smallest useful production SELECT query.

Rules:
- Use bracketed SQL Server identifiers.
- Prefer explicit column lists.
- Avoid mutation, temp-table mutation, procedures, and side effects.
- Save SQL before execution.
- Validate forbidden tokens before asking for execution confirmation.

Output:
- `sql/extract.sql`
- `sql/sql-safety.json`
- `checkpoints/02_sql_review.json`

Read as needed:
- `references/sql-safety.md`
- `references/schema-context.md`

Then stop at Checkpoint 2.

---

## Checkpoint 2 - SQL Execution Confirmation

Before production DB execution, show:
- Exact SELECT SQL path and summary.
- Source object.
- Selected columns.
- Expected row scope.
- Safety validation result.

Wait for the user to confirm execution. If the user does not confirm, deliver the SQL and mark execution as not performed.

---

## Phase 4 - Confirmed SELECT Execution and Local SQLite

After confirmation:
- Execute only SELECT statements against production.
- Capture row count, column list, duration, and any error.
- Export rows to local CSV.
- Import rows into local SQLite.
- Create local SQLite views for report sections when useful.
- Verify CSV row count equals SQLite table row count.

Output:
- `data/raw.csv`
- `data/raw-preview.json`
- `data/aggregate-checks.json`
- `db/query-execution.json`
- `sqlite/report.sqlite3`
- `sqlite/manifest.json`
- `checkpoints/03_data_preview.json`

Read as needed:
- `references/sqlite-enrichment.md`
- `references/validators.md`

Then stop at Checkpoint 3.

---

## Checkpoint 3 - Data Preview and Design Confirmation

Before report build, show:
- Row count and column count.
- Raw preview and aggregate checks.
- Local SQLite views.
- Proposed report sections, charts, and tables.
- Residual risks.

Wait for confirmation before building the final report.

---

## Phase 5 - Report Build

Build the report from local payload data only. The browser report must not connect to production DB.

Steps:
- Create `report/payload/report-payload.json`.
- Use `assets/scaffold-template/` only as a starting point when a React report is useful.
- Build sections for KPI summary, trends, rankings, detail tables, and validation notes.
- Use operational report design: dense, calm, readable, and evidence-backed.
- Save the draft under `report/delivery/`.

Read as needed:
- `references/scaffold.md`
- `references/section-build.md`
- `references/component-policy.md`
- `references/rawblock-policy.md`
- `references/html-output.md`
- `report_designs/index.json`
- selected `report_designs/*.md`

---

## Phase 6 - Final Review

Review from four angles:
- Content: objective, metrics, labels, and business meaning.
- Data: row counts, aggregates, source fields, and residual risks.
- Visual: readability, chart choice, layout, and mobile behavior.
- Technical: single-file HTML behavior, no production calls, payload validity.

Output:
- `review/final-review.md`
- validator JSON files under `review/validators/`

---

## Phase 7 - Repair

Repair the smallest broken artifact:
- If SQL is unsafe, fix SQL and repeat safety validation before any DB execution.
- If extraction is wrong, fix source extraction and update the plan.
- If data is inconsistent, fix local import or aggregates and update evidence.
- If the report is unclear, fix the affected section only.

Write `review/repair-log.md` only when repairs were made.

---

## Phase 8 - Delivery

Deliver:
- Single-file HTML report path.
- Report payload path.
- SQL path and SQL safety evidence.
- Data row counts and SQLite manifest, if execution was performed.
- Validator summary.
- Residual risks.

Do not claim DB execution occurred unless `db/query-execution.json` exists and records the SELECT execution evidence.

---

## Progressive Reference Loading

Load only the files needed for the active phase.

| Phase | Read |
|---|---|
| 0 | `references/harness.md`, `references/db-config.md` |
| 1 | `references/excel-intake.md`, `references/field-classification.md`, `references/schema-context.md` |
| 2 | `references/report-plan-template.md`, `references/checkpoint-payload-schema.md`, `references/report-payload-schema.md` |
| 3 | `references/sql-safety.md`, `references/schema-context.md` |
| 4 | `references/sqlite-enrichment.md`, `references/validators.md` |
| 5 | `references/scaffold.md`, `references/section-build.md`, `references/component-policy.md`, `references/rawblock-policy.md`, selected report design |
| 6-8 | `references/review-checklist.md`, `references/repair-policy.md`, `references/html-output.md`, `references/single-html-export.md` |

---

## Defaults

- Final report format: single-file HTML.
- Database mode: production read-only, SELECT only.
- Smoke test: `SELECT TOP 1 1 AS connection_test` only after user approval or explicit instruction.
- Report style: operational management report, not a marketing page.
- Local data store: SQLite under the run folder.
- Language: follow the user request; otherwise use the workbook/report language.

---

## Success Standards

- The report is traceable from user request and Excel fields to SQL, local data, payload, and HTML.
- Production SQL is SELECT only and validated before execution.
- DB execution evidence is truthful and saved.
- Local SQLite row counts match extracted data.
- The final HTML opens offline and uses local payload data only.
- Business labels, measures, dimensions, and filters match the confirmed plan.
- Residual risks are visible instead of hidden.

# WFERP Report Harness

This reference expands the phase workflow in `SKILL.md`. Use it when creating or resuming a report run.

## Operating Principle

The harness turns a report request into auditable local artifacts. Every phase should leave evidence in the run folder. If a phase is skipped because the user directly authorized a later step, record that reason in the checkpoint or manifest.

Production DB access remains SELECT only.

## Phase Artifacts

| Phase | Main artifacts | Required before next phase |
|---|---|---|
| 0 Intake | run folder, source inventory stub | DB safety boundary recorded |
| 1 Source | workbook fields, connections, extraction notes | field classification complete |
| 2 Plan | normalized plan, markdown plan, checkpoint 1 | user confirms logic |
| 3 SQL | extract.sql, sql-safety.json, checkpoint 2 | user confirms execution |
| 4 Data | raw CSV, SQLite, manifests, checkpoint 3 | user confirms preview/design |
| 5 Build | payload JSON, HTML draft | payload validates |
| 6 Review | final-review.md, validator JSON | failures repaired |
| 7 Repair | repair-log.md when needed | targeted validators rerun |
| 8 Delivery | report.html and summary | evidence paths provided |

## Checkpoint Payloads

Checkpoint payloads should include:
- `checkpoint`: stable checkpoint id.
- `status`: `draft`, `ready_for_review`, `approved`, `blocked`, or `skipped_with_reason`.
- `summary`: concise human-readable summary.
- `decisions_required`: independent decisions still waiting on the user.
- `evidence`: paths to supporting artifacts.
- `approved_by_user`: true only after explicit confirmation.
- `residual_risks`: known limitations.

## SQL Gate

Before any production execution:
1. Save SQL to `sql/extract.sql`.
2. Confirm it is a single SELECT or WITH...SELECT statement.
3. Strip comments and string literals for forbidden-token scanning.
4. Reject any DML, DDL, EXEC, procedure, transaction mutation, or side-effect statement.
5. Save `sql/sql-safety.json`.
6. Stop at Checkpoint 2 unless the user already gave exact approval for that SQL execution.

## Data Gate

After production SELECT execution:
1. Save raw extracted data locally.
2. Save execution metadata: user, server, database, object, row count, column count, duration, and SQL path.
3. Import to local SQLite.
4. Verify CSV row count equals SQLite table row count.
5. Save aggregate checks that support report KPIs.
6. Stop at Checkpoint 3 before building the final report.

## Report Gate

The report must be built from local artifacts only. It must not query production from the browser. Include validation notes so reviewers can trace the numbers.

## Resume Rules

When resuming a run:
- Read the latest checkpoint first.
- Read manifests before re-running extraction.
- Do not re-execute production SQL unless the user confirms again or the prior instruction clearly still applies.
- Prefer continuing from saved artifacts when they are valid.

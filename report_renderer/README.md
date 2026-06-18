# WFERP Report Renderer

This is a standalone React renderer for WFERP report checkpoints and final report payloads. It consumes structured JSON only and does not connect to databases or execute SQL.

## Payload sources

- `window.__WFERP_REPORT_PAYLOAD__`
- `?payload=/examples/expense-analysis-checkpoint.json`
- The bundled checkpoint example when no payload is provided

## Harness flow

The renderer is the browser surface for the local `wferp-report` harness. It only
renders checkpoint/report JSON produced by `python3 -m skill_scripts.cli_report_harness`;
the CLI owns run state, checkpoint gates, DB execution evidence, report scaffold
payloads, and final validator evidence.

Typical command sequence:

1. `create-run`
2. `write-excel-confirmation`
3. `write-sql-review`
4. `confirm --checkpoint sql_review --action 同意查詢`
5. `write-data-preview`
6. `write-report-selection`
7. `confirm --checkpoint report_selection --action 產生報告`
8. `scaffold-report`
9. `write-report-draft`
10. `confirm --checkpoint report_draft --action 接受`
11. `write-final-review`
12. `can-deliver`

`serve-checkpoint` starts the local companion server for user confirmations. The
browser never connects to the database, executes SQL, or stores credentials.

## Component layer note

The beautiful-article/reacticle package is not used in this project because it is not available as an installed local dependency for this worktree. The renderer implements a compatible internal semantic component layer using React sections, panels, status rows, option controls, data tables, and report blocks with restrained business-report styling.

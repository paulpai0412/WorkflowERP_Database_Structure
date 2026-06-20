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
3. `classify-workbook`
4. `serve-checkpoint`
5. `wait-confirmation --checkpoint field_formula_classification`
6. `write-sql-review`
7. `wait-confirmation --checkpoint sql_review`
8. `init-sqlite-workspace`
9. `write-raw-table`
10. `write-raw-preview`
11. `run-sqlite-enrichment`
12. `write-enriched-preview`
13. `wait-confirmation --checkpoint enriched_data_preview`
14. `write-report-selection`
15. `wait-confirmation --checkpoint report_selection`
16. `scaffold-report`
17. `generate-report-section`
18. `validate-report-section`
19. `write-report-draft`
20. `wait-confirmation --checkpoint report_draft`
21. `write-final-review`
22. `can-deliver`
23. `export-single-html`

`serve-checkpoint` starts the local companion server for user confirmations. The
browser never connects to the database, executes SQL, or stores credentials.

`write-data-preview` remains available for older scripts, but new report runs
should prefer the raw/enriched flow: `write-raw-table`, `write-raw-preview`,
`run-sqlite-enrichment`, and `write-enriched-preview`.

Complex reports may include LLM-generated React section files. Those sections
must be written through `generate-report-section` or `repair-report-section`,
then checked with `validate-report-section`; the renderer still consumes only
embedded payload data and never connects to the database.

## Single HTML export

Final delivery can be exported as a self-contained offline HTML file:

```bash
python3 -m skill_scripts.cli_report_harness export-single-html \
  --run-dir /path/to/run \
  --package /path/to/report-package.json \
  --brief /path/to/report-design-brief.json
```

The command writes `delivery/report.html`, `delivery/delivery-manifest.json`, and
an evidence packet under `delivery/evidence/` containing `report-package.json`,
`report-design-brief.json`, and `query.sql`. The HTML file embeds the compressed
report package and design brief inline and does not load external scripts,
stylesheets, or fetch resources.

## Component layer note

The beautiful-article/reacticle package is not used in this project because it is not available as an installed local dependency for this worktree. The renderer implements a compatible internal semantic component layer using React sections, panels, status rows, option controls, data tables, and report blocks with restrained business-report styling.

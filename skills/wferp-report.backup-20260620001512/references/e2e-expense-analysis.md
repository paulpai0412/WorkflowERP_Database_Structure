# End-to-End Report Example

A complete run should produce:
- `source/source-inventory.json`
- `plan/normalized-report-plan.json`
- `plan/report-plan.md`
- `checkpoints/01_field_formula.json`
- `checkpoints/02_sql_review.json`
- `checkpoints/03_data_preview.json`
- `sql/*.sql`
- `data/*.csv` and preview JSON
- `sqlite/*.sqlite3` and manifest JSON
- `report/payload/*.json`
- `report/*.html`
- `review/validators/*.json`

The production database step must execute SELECT only.

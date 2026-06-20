# Report Payload Schema

The report payload is JSON consumed by the final HTML report.

Suggested top-level fields:
- `title`: report title.
- `subtitle`: optional context line.
- `generated_at`: ISO timestamp.
- `source`: source workbook and database object metadata.
- `kpis`: list of label/value/unit items.
- `sections`: chart, table, and narrative sections.
- `validation`: evidence from row counts, SQL review, and data checks.
- `warnings`: known limitations or unresolved assumptions.

Use stable field names so the renderer can be reused.

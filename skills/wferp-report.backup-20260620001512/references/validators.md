# Validators

Run validators before delivery.

Recommended checks:
- `skill_encoding`: no replacement characters or known mojibake markers in skill files.
- `sql_safety`: generated production SQL is SELECT only.
- `row_count`: local SQLite row count matches extracted CSV row count.
- `schema_match`: extracted columns match expected workbook fields.
- `payload_shape`: report payload has required top-level fields.
- `html_smoke`: final HTML opens and contains report title and core sections.

Save validator outputs as JSON under `review/validators/`.

Create a WFERP expense analysis report from the attached Excel workbook.

Required output:
- Read workbook fields, formulas, filters, and pivot configuration.
- Generate read-only SELECT SQL for source data.
- Load the result into a local SQLite database.
- Build a single-file HTML report with summary metrics, charts, and validation notes.

Database safety:
- Production database access is read-only.
- Smoke tests and extraction queries must be SELECT only.

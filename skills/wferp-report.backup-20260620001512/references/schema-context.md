# Schema Context

For WFERP reports, schema context comes from:
- Excel connection metadata.
- Workbook pivot cache fields.
- SELECT-only schema probes such as `SELECT TOP 0 * FROM ...`.
- Existing repo documentation and prior run manifests.

SQL generation rules:
- Use bracketed identifiers for SQL Server columns and objects.
- Select only required columns when possible.
- Keep source object names explicit.
- Save generated SQL under the run folder before execution.

# SQLite Enrichment

Use local SQLite for report shaping after production SELECT extraction.

Allowed local operations:
- Create local tables and views.
- Import CSV data extracted from production SELECT queries.
- Build aggregate views for report sections.
- Store manifests, row counts, and validation evidence.

Production restrictions do not prevent local SQLite writes, but artifacts must clearly identify that writes are local only.

# Excel Intake

When an Excel workbook is attached:

1. Work from a copied file if the workbook is locked by Excel.
2. Inspect workbook XML, connections, pivot caches, tables, formulas, filters, and named ranges.
3. Extract field names exactly as Excel stores them.
4. Classify each field as dimension, measure, date, identifier, formula, or unknown.
5. Record workbook connection metadata without exposing sensitive secrets.
6. Compare workbook fields with database schema using SELECT-only metadata checks.

For `.xlsx`, prefer structured workbook parsing over manual string search.

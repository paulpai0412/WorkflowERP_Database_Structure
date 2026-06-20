# Checkpoint Payload Schema

Checkpoint files are JSON documents stored under `checkpoints/`.

Common fields:
- `checkpoint`: stable checkpoint name.
- `status`: `draft`, `ready_for_review`, `approved`, or `blocked`.
- `created_at`: ISO timestamp when available.
- `inputs`: source files or database objects used.
- `findings`: concise evidence and decisions.
- `questions`: unresolved user-facing questions.

Required checkpoints:
- `01_field_formula.json`: Excel fields, formulas, pivots, filters, and inferred metrics.
- `02_sql_review.json`: SELECT-only SQL review and safety evidence.
- `03_data_preview.json`: row counts, sample rows, aggregates, and anomalies.

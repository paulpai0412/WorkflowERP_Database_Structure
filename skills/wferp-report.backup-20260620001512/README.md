# wferp-report

This skill helps Codex build Workflow ERP management reports from prompts and Excel inputs.

Core rules:
- Treat configured WFERP database connections as production.
- Execute only SELECT statements against the production database.
- Never run INSERT, UPDATE, DELETE, MERGE, TRUNCATE, DROP, ALTER, CREATE, EXEC, or stored procedures against production.
- Write extracted data only to local run artifacts such as CSV, SQLite, JSON, and HTML.

Use SKILL.md as the entry point. Load reference files only when the active task needs them.

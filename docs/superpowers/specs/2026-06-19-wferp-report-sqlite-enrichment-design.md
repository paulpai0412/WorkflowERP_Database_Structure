# WFERP Report SQLite Enrichment Pipeline Design

Date: 2026-06-19  
Project: `wferp`  
Topic: Redesign the `wferp-report` skill data pipeline so formal database access remains a single reviewed read-only SQL query, while Excel formulas and lookup-sheet enrichments are applied in a run-scoped local SQLite workspace.

## 1) Purpose

The current `wferp-report` workflow can generate very large SQL statements when Excel workbook columns depend on lookup sheets, formulas, manually maintained classifications, or currency conversion tables. This makes the formal database SQL hard to review, expensive to parse, and brittle when Excel lookup tables change.

This design changes the default architecture:

1. query the formal Workflow ERP database only for raw database-backed fields;
2. import workbook lookup sheets into a local run-scoped SQLite workspace;
3. enrich the returned raw rows locally using SQLite expressions derived from Excel formulas and lookup references;
4. show both raw database data and enriched report data to the user before report generation.

The result preserves the one-SELECT formal database boundary while making Excel-derived report logic explicit, auditable, and easier to validate.

## 2) Confirmed Product Decisions

- The formal database receives only one reviewed read-only `SELECT`.
- Excel formula columns and workbook lookup columns are not pushed into the formal database query.
- The skill must automatically classify workbook columns into database fields, database-derived fields, Excel enrichment fields, and unresolved fields; the user should not need to identify those categories manually.
- Any database field shown to the user must include readable metadata: table id, table name, column id, column name, and business/source reason.
- Data preview must show two layers: raw database result and SQLite-enriched result.
- Each run uses unique SQLite table names to avoid collisions and accidental data reuse.
- At the final checkpoint, the skill asks whether to keep or delete local SQLite temp tables; the default is to keep them for audit, rerendering, and debugging.

## 3) Scope

### In scope

- Excel workbook intake and automatic column classification.
- Schema metadata enrichment for every database field reference.
- Formal database raw SQL generation and SQL review checkpoint.
- Importing Excel lookup sheets into local SQLite tables.
- Writing formal database results into a local SQLite raw table.
- Applying formulas and lookup logic into a local SQLite enriched table.
- Raw/enriched data preview checkpoints.
- SQLite manifest, cleanup checkpoint, and retention behavior.
- Subagent validation gates for SQL, schema/formula classification, enrichment correctness, data preview, and final report evidence.

### Out of scope

- Writing enrichment tables back to the formal ERP database.
- Creating permanent ERP lookup tables from Excel workbook sheets.
- Supporting write SQL, DDL, stored procedure execution, or multi-statement formal database SQL.
- Guaranteeing that every Excel formula can be translated automatically; unsupported formulas become unresolved fields with explicit repair options.

## 4) Column Classification Model

The skill must classify each workbook output column into one of four categories.

| Category | Meaning | Processing location | Example |
| --- | --- | --- | --- |
| `db_source_field` | Direct database field or join field. | Formal DB SQL raw query. | `ACTML.ML006` as account code. |
| `db_derived_field` | Computed from raw database fields without workbook lookup state. | Prefer local SQLite enrichment unless it is needed to reduce DB result shape. | Debit amount from debit/credit flag and amount. |
| `excel_enrichment_field` | Formula, VLOOKUP, workbook lookup, currency table, classification, or manually maintained mapping. | Local SQLite enrichment. | Department BU from `對照表`, related-party flag from `關係人`, converted NTD amount from `匯率表!C3`. |
| `unresolved_field` | Insufficient evidence or unsupported formula/source. | Excluded from formal DB query and flagged in checkpoint. | Running balance requiring opening-balance rules. |

The classification engine uses these evidence sources:

- formula presence and formula tokens;
- referenced sheets/ranges;
- sheet role detection such as main data, lookup table, currency table, related-party table;
- WFERP schema metadata and relationship hints;
- column names, sample values, data types, and code patterns;
- user-confirmed decisions from prior checkpoints.

Every classified column records:

- `excel_column`;
- `excel_header`;
- `classification`;
- `processing_location`;
- `source_expression`;
- `lineage_inputs`;
- `confidence`;
- `reason`;
- `risks`.

## 5) Database Field Metadata Requirement

Field codes such as `ML006` and `TB008` are not user-readable. Any checkpoint, SQL explanation, or data lineage view that references a database field must include:

- `table_id`, for example `ACTML`;
- `table_name`, for example `分類帳檔`;
- `column_id`, for example `ML006`;
- `column_name`, for example `明細科目編號`;
- `join_reason` when the field comes from a joined table;
- `business_meaning` or `source_reason`;
- `metadata_status`, with `warning` if table or column descriptions are missing.

User-facing checkpoint tables should show the readable name first and the ERP code as supporting evidence.

Example:

| Excel column | Header | Classification | Field | Readable name | Table | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| A | 科目編號 | `db_source_field` | `ACTML.ML006` | 明細科目編號 | 分類帳檔 | Main ledger account code. |
| B | 科目名稱 | `db_source_field` | `ACTMA.MA003` | 科目名稱 | 會計科目檔 | Joined by `ACTMA.MA001 = ACTML.ML006`. |
| AA | 金額-原幣 | `db_derived_field` | `ML007 + ML014` | 借貸別 + 原幣金額 | 分類帳檔 | Rebuilds Excel formula `Q-R`. |

## 6) Data Flow

### Phase A: Workbook intake

The skill reads workbook sheets, formulas, values, ranges, hidden sheets when available, and sample rows. It detects the primary data sheet and candidate lookup sheets. It creates:

- `excel_requirement.json`;
- `column_classification.json`;
- `lookup_sheet_inventory.json`;
- `field_metadata_map.json`.

### Phase B: Field and formula checkpoint

The user sees a classification checkpoint with readable field names, formula lineage, lookup sheet usage, confidence, and risks. The checkpoint does not ask the user to manually classify every field; it asks them to approve, repair, or provide missing business rules for unresolved fields.

### Phase C: Formal DB raw query

The skill generates one formal DB `SELECT` for only the raw database fields needed by:

- `db_source_field`;
- lineage inputs for `db_derived_field`;
- lineage inputs for `excel_enrichment_field`.

The SQL review checkpoint shows:

- SQL text;
- field metadata summary;
- join explanation;
- excluded Excel-enrichment columns;
- unresolved columns;
- SQL safety and schema reviewer evidence.

### Phase D: SQLite staging

After the user confirms SQL and the formal DB query executes, the skill writes returned rows into a run-scoped raw table.

Example table names:

- `wferp_20260619_143012_a8f3_raw_ledger`;
- `wferp_20260619_143012_a8f3_lookup_department_bu`;
- `wferp_20260619_143012_a8f3_lookup_related_party`;
- `wferp_20260619_143012_a8f3_lookup_currency_rate`;
- `wferp_20260619_143012_a8f3_enriched_ledger`.

The run prefix must be generated from timestamp plus random suffix and stored in the run state.

### Phase E: Lookup import

Workbook lookup sheets are normalized into SQLite lookup tables. Each lookup table records:

- source workbook path;
- sheet name;
- source range;
- source row count;
- ignored row count;
- ignored row reasons such as header, blank, subtotal, or metadata;
- source file hash;
- extraction rules.

Header and metadata rows must be excluded. For example, rows whose key cell equals `科目編號`, `公司別`, a blank value, or a subtotal label must not become lookup mappings.

### Phase F: Enrichment

The skill builds SQLite enrichment SQL that reads from the raw table and lookup tables. This produces the enriched table used by reports.

Supported initial enrichment patterns:

- arithmetic formulas such as `Q-R`, `S-T`, and `AN*AB`;
- substring/date extraction such as `MID(F,6,6)`;
- `IF` and simple conditional expressions;
- `VLOOKUP` and exact-match lookup ranges;
- fixed cell references such as `匯率表!C3`;
- constants such as company code and actual/budget marker.

Unsupported formulas become unresolved columns and are excluded from the enriched table or filled with `NULL` only when the user explicitly approves that behavior.

### Phase G: Raw and enriched data preview

The data preview checkpoint shows:

1. raw database rows and aggregates;
2. enriched rows and aggregates;
3. column lineage from raw fields to final report columns;
4. unresolved or intentionally excluded columns;
5. row counts and reconciliation checks.

The user validates data at this layer before report layout and chart selection.

### Phase H: Report generation

Report selection, visual design, report draft, final HTML export, and final validators query only the enriched table or its exported JSON payload. The final single-file HTML report embeds data derived from the user-confirmed enriched dataset, not from unconfirmed raw rows.

### Phase I: Cleanup checkpoint

The final checkpoint asks the user how to handle local SQLite artifacts:

- keep local SQLite temp tables, default;
- delete tables for this run prefix;
- export/archive evidence and then delete the tables.

Deletion must only target tables listed in the run manifest for that run prefix.

## 7) SQLite Manifest

Each run writes `sqlite_manifest.json`.

Required fields:

- `sqlite_db_path`;
- `run_prefix`;
- `raw_table`;
- `lookup_tables`;
- `enriched_table`;
- `source_workbook`;
- `source_workbook_hash`;
- `formal_db_query_hash`;
- `raw_row_count`;
- `enriched_row_count`;
- `lookup_row_counts`;
- `ignored_lookup_rows`;
- `created_at`;
- `cleanup_status`;
- `retention_decision`;
- `residual_risks`.

This manifest is part of the delivery packet when the user keeps SQLite artifacts.

## 8) Checkpoints

The harness adds or updates these checkpoints:

| Checkpoint | Purpose | Gate |
| --- | --- | --- |
| Source/Excel intake | Confirm detected workbook role and source inventory. | Required before classification. |
| Field/formula classification | Show automatic classification with readable DB field metadata. | Required before formal DB SQL. |
| SQL review | Confirm one formal DB read-only SQL and excluded enrichment columns. | Required before formal DB execution. |
| Raw DB preview | Confirm rows returned from the formal DB. | Required before SQLite enrichment. |
| Enriched preview | Confirm SQLite formula/lookup output. | Required before report design. |
| Report selection/design | Confirm report contents, charts, tables, layout direction. | Required before report draft. |
| Report draft/final review | Confirm report output and validator findings. | Required before delivery. |
| SQLite retention | Keep, delete, or archive local SQLite artifacts. | Required at delivery close. |

## 9) Subagent Validators

Validator gates must be subagent-owned. Main-agent local checks can be evidence input but cannot replace reviewer conclusions.

Required validators:

- `excel_classification_reviewer`: verifies automatic classification, formula lineage, lookup sheet role detection, and unresolved fields.
- `schema_relationship_reviewer`: verifies WFERP table/field mappings, readable metadata, joins, and relationship assumptions.
- `sql_safety_reviewer`: verifies formal DB SQL is read-only, SQL Server 2000 compatible, single statement, and free of forbidden constructs.
- `sqlite_enrichment_reviewer`: verifies lookup import hygiene, formula translation, run-scoped table names, and enrichment row counts.
- `data_preview_reviewer`: verifies raw/enriched row counts, sample data, aggregates, and reconciliation checks.
- `report_content_reviewer`: verifies report claims trace back to enriched data.
- `visual_taste_reviewer` and `react_technical_reviewer`: verify final HTML layout, visual quality, offline behavior, and accessibility.

If any required validator returns `fail` or `blocked`, the main agent performs the smallest repair slice and reruns the affected reviewer.

## 10) Error Handling and Repair

### Classification errors

If a column is misclassified, the repair scope is limited to that column and any downstream fields that depend on it.

### Unsupported formulas

Unsupported formulas are marked unresolved with:

- original formula;
- unsupported token or function;
- referenced cells/ranges;
- suggested handling options.

The system must not silently approximate unsupported formulas.

### Lookup extraction errors

Lookup import must reject or ignore rows with non-data keys such as headers, totals, blank keys, and metadata labels. The ignored rows are recorded in the manifest.

### SQLite execution errors

SQLite enrichment errors stop before report generation. The checkpoint shows the failed expression, source formula, target column, and affected lookup table.

### Cleanup errors

Cleanup failures do not delete partial state silently. The manifest records failed table names and the exact error.

## 11) Testing Strategy

The implementation plan should include tests at these levels:

- unit tests for workbook column classification;
- unit tests for DB field metadata enrichment from `_Source/TableStructure.json` and `_Source/TableName.json`;
- unit tests for lookup sheet extraction and ignored header/meta rows;
- unit tests for formula-to-SQLite expression translation;
- integration tests for raw table plus lookup tables producing an enriched table;
- harness tests for raw/enriched preview checkpoints;
- E2E test using a local SQLite workspace for an expense-analysis workbook scenario, with no fake, smoke, or mock substitution for the enrichment pipeline.

Quantitative acceptance criteria:

- 100% of DB field references in checkpoints include readable table and column names or a warning reason.
- 100% of workbook output columns are classified as one of the four categories.
- 0 header/meta lookup rows are imported as business mappings.
- Raw and enriched row counts are recorded and reconciled.
- A retained run can rerender the report from the enriched table without requerying the formal DB.
- Cleanup removes only tables listed in that run manifest.

## 12) Security and Data Retention

- SQLite files stay local to the run workspace.
- Formal DB credentials are never written into SQLite, checkpoint payloads, or final HTML.
- The final HTML embeds only user-approved report data, not credentials or live database connection settings.
- Default retention is keep, but the final checkpoint must make the local data retention decision explicit.
- Deleted runs must remove only the current run prefix tables and update `sqlite_manifest.json`.

## 13) Open Product Risks

- Some workbook formulas may depend on external workbooks, hidden manual values, or volatile Excel functions that are not suitable for automatic SQLite translation.
- Some WFERP columns may have ambiguous schema matches; these must remain warnings until user-confirmed or schema-validated.
- Keeping local SQLite artifacts is useful for audit and rerendering, but it increases local data retention responsibility.
- Large workbooks may require indexing lookup tables and raw/enriched tables to keep preview responsive.

## 14) Success Criteria

The redesigned skill is successful when:

- users upload a workbook without manually explaining which columns are database fields;
- the skill automatically classifies fields and shows readable ERP metadata;
- formal DB SQL remains short enough to review and contains only raw database field retrieval;
- SQLite enrichment reproduces supported Excel formulas and lookup mappings with evidence;
- users can compare raw database data and enriched report data before report generation;
- final reports use the enriched, user-confirmed dataset;
- the run can be retained or cleaned up without cross-run data collisions.

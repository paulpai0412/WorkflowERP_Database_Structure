# WFERP Report 4-Step Visual Companion Design

## Purpose

Redesign the `wferp-report` user experience without weakening the existing technical harness.

The internal report harness keeps the original 13 technical phases, validator gates, SQL safety, SQLite enrichment, lookup handling, evidence files, repair loop, HTML delivery, and production DB read-only rules. The user-facing Visual Companion becomes a 4-step report workbench that shows real data, real report previews, and prompt-driven repair controls.

This is a UI and workflow presentation redesign, not a replacement for the original technical design.

## Non-Negotiable Principles

- Keep the 13 technical phases as the internal engine.
- Do not remove SQL review, DB execution evidence, SQLite enrichment, lookup tables, validator gates, repair policy, or final delivery evidence.
- Visual Companion must be user-oriented Traditional Chinese UI, not a JSON viewer or technical checklist.
- Visual Companion must support prompt-based change requests that are routed back to the main agent.
- The current run and current checkpoint must be verified; stale run pages and stale confirmations are invalid.
- Production DB access remains SELECT-only.
- Data previews must render real current-run data. Default preview size is 50 rows.
- True Excel output means a real `.xlsx` workbook, not only Excel-like HTML.

## Capability Ownership

| Capability | Owns | Does Not Own |
|---|---|---|
| `wferp-report` | 13-phase harness, prompt/Excel understanding, SQL, DB read safety, SQLite enrichment, lookup handling, formula semantics, validators, evidence, repair routing | User-facing UI design, chart design, workbook rendering details |
| `Build Web Apps` | 4-step Visual Companion UI, prompt repair input, confirmation UX, responsive app shell, final HTML app layout | SQL, DB execution, formula correctness, validator decisions |
| `Build Web Data Visualization` | Real-data KPI, chart, table, pivot-like preview, HTML report visualization, 50-row data preview usability | SQL generation, DB access, SQLite mutation, validator decisions |
| `spreadsheets` | Real `.xlsx` workbook generation, sheet layout, formatting, formula/value strategy, workbook verification | SQL safety, DB execution, SQLite evidence, HTML report UI |

When these capabilities are available, they are mandatory for their ownership areas. If unavailable, the agent must stop and ask before falling back. It must not silently hand-roll a static checkpoint page, generic JSON viewer, fake Excel preview, or fake `.xlsx` delivery.

Visual Companion UI and final HTML report UI must be dynamically designed and implemented with `Build Web Apps` plus `Build Web Data Visualization` when those plugin capabilities are available. The WFERP skill may provide structured payloads and safety gates, but it must not hand-roll static checkpoint HTML, generic JSON pages, fake charts, or fake report previews as a substitute.

Dynamic UI generation must preserve the original harness contract: current-run routing, POST confirmation, prompt-based repair, selectedOptions, confirmation identity checks, and `wait-confirmation` compatibility.

## Internal 13 Phases

The internal harness remains:

1. Phase 0 Intake
2. Phase 1 Source / Excel Requirement
3. Phase 2 Report Planning
4. Phase 3 Field & Formula Checkpoint
5. Phase 4 SQL Review Checkpoint
6. Phase 5 Confirmed DB Execution
7. Phase 6 Data Preview Checkpoint
8. Phase 7 Report Selection Checkpoint
9. Phase 8 Final Report Scaffold
10. Phase 9 Section Build
11. Phase 10 Final Review
12. Phase 11 Repair
13. Phase 12 Delivery

These phases are technical execution boundaries. They are not all shown as separate user steps.

## User-Facing 4 Steps

| User Step | Internal Phase Coverage | User Decision |
|---|---|---|
| 1. Source-to-Output Logic | Phase 0-3 | Confirm sources, output targets, formulas, lookup logic, lineage, and unresolved fields before SQL |
| 2. SQL Query | Phase 4-5 | Confirm SELECT SQL, DB target, filters, joins, aggregates, and permission to query |
| 3. Data Result and Report Design | Phase 6-9 | Confirm real raw/enriched data, SQLite results, HTML report preview, and Excel workbook preview |
| 4. Final Delivery | Phase 10-12 | Confirm final HTML, final `.xlsx`, validator evidence, residual risks, and SQLite retention |

The Visual Companion navigation should show only these 4 user steps. Technical checkpoints and validator details remain available in expandable evidence panels.

## Step 1: Source-to-Output Logic

Step 1 answers: "Did the agent understand what data I provided and how it will become the final HTML/Excel report?"

Primary sections:

- Requirement summary: user prompt, business question, requested output.
- Source inventory: prompt, Excel source workbook, Excel template workbook, lookup sheets, local mapping tables, DB/schema candidates.
- Output targets: HTML, Excel, or HTML plus Excel.
- Source-to-output matrix.
- Formula semantics and number consistency policy.
- SQLite and SQL responsibility split.
- HTML report outline.
- Excel workbook outline.
- Current unresolved/manual decisions.

The page should be output-first. Each row should show something the user will see in the final report.

Example source-to-output matrix:

| Output Item | Source | Transformation Logic | Processing Layer | Verification |
|---|---|---|---|---|
| KPI amount | DB raw columns plus Excel lookup | Compute agreed business metric and aggregate by selected dimension | SQLite enrichment or report layer | Compare against aggregate check |
| Detail table column | DB SELECT field | Rename, format, and optionally map through lookup table | SQL raw plus SQLite lookup | 50-row preview |
| Excel summary sheet | Enriched dataset | Group and summarize according to confirmed report logic | Spreadsheet generation | HTML KPI and Excel totals match |

Formula policy:

- Do not replicate the old workbook mechanics by default.
- Preserve the numeric definition and lineage.
- Each formula-backed output must state dependencies, intent, processing layer, and verification method.
- Formula handling choices are `sqlite-enrichment`, `report-layer`, `excel-formula`, `value-only`, `hybrid`, `manual`, or `unresolved`.
- The default Excel output strategy is `hybrid`: write verified result values in primary report sheets and include a formula explanation sheet. If the user requests editable formulas, use `excel-formula` where safe and verifiable.

Step 1 confirmation is a data logic contract. SQL, SQLite enrichment, HTML rendering, and Excel generation must follow it.

## Step 2: SQL Query

Step 2 answers: "Is this the correct and safe query to run?"

Primary sections:

- SELECT SQL to execute.
- DB target and connection label.
- Table and field readable names.
- Filters, joins, grouping, and aggregates.
- Logic not pushed into SQL and why.
- SQL safety validator status.
- Schema mapping validator status.

The page must make production safety obvious. Query execution is blocked until the user confirms this step and required validators pass.

## Step 3: Data Result and Report Design

Step 3 answers: "Do the actual data and report previews look right?"

This step must render real current-run data, not mock data.

Primary sections:

- Raw DB table preview: first 50 rows, columns, row count, source summary.
- SQLite enriched table preview: first 50 rows, computed columns, lookup columns, row count.
- Lookup hit/miss statistics and unresolved mappings.
- Aggregate checks and number consistency checks.
- HTML report live preview: KPI, chart, table, narrative blocks using current-run data.
- Excel workbook preview: sheet tabs, columns, first 50 rows, summary rows, formatting intent, formula/value strategy.
- Prompt repair input for changing grouping, charts, tables, Excel sheets, visual style, or data logic.

The HTML preview and Excel preview should be rendered as real report-like blocks. The user should not need to read JSON to understand what will be delivered.

If the user enters a prompt repair request, the companion writes a blocking `changes_requested` confirmation with scope metadata. The main agent routes the request to the smallest affected internal phase and reopens the current user step after repair.

## Step 4: Final Delivery

Step 4 answers: "Can I accept these final deliverables?"

Primary sections:

- Final single-file HTML report preview/link.
- Final `.xlsx` workbook link and workbook summary.
- Validator status grouped by user step and technical gate.
- Residual risks and explicit accept/reject controls.
- SQLite retention choice: keep run SQLite evidence or clean up temp data.
- Delivery manifest and evidence links.

Final delivery is blocked until required validators pass or the user explicitly accepts matching residual risks.

## Prompt-Based Repair Loop

Every user step must provide a prompt input for change requests.

Required persisted fields:

- `action = changes_requested`
- `comment = user prompt`
- `selectedOptions.changeScope`
- `selectedOptions.targetUserStep`
- `selectedOptions.requiresRerender = true`
- `run_id`
- `checkpoint_id`
- `payload_hash`
- `confirmation_id`
- `created_at`
- `confirmed_at`

Supported change scopes:

- `source_logic`
- `formula_logic`
- `sql_conditions`
- `data_result`
- `html_design`
- `excel_design`
- `visual_style`
- `delivery`

The main agent must stop forward progress on any prompt repair request. It repairs the smallest affected technical slice, reruns affected validators, regenerates affected previews, and reopens the relevant user step.

## SQLite and Lookup Presentation

SQLite is retained as the run-scoped local processing layer.

Data flow:

```text
Prompt / Excel / DB schema
        ↓
Confirmed source-to-output logic
        ↓
SELECT-only DB raw rows
        ↓
Run-scoped SQLite workspace
        ↓
Raw table + lookup tables + enriched table + aggregate checks
        ↓
HTML payload + Excel workbook payload
        ↓
Final HTML + final .xlsx
```

Visual Companion must show SQLite as a local processing workspace, not as a production write. It should show lookup tables, computed columns, hit/miss statistics, row counts, aggregate checks, and retention state in user-readable terms.

## Excel Output Requirements

True Excel output uses the `spreadsheets` skill.

Required workbook design preview in Step 3:

- Sheet tabs and sheet purpose.
- Columns and first 50 rows where data exists.
- Summary rows, totals, KPI areas, and formatting intent.
- Formula/value strategy per sheet.
- Source lineage for important numbers.

Required final workbook evidence in Step 4:

- `.xlsx` path.
- Workbook sheet inventory.
- Row/column counts per sheet.
- Formula/value strategy summary.
- Recalculation or verification evidence where applicable.
- Number consistency evidence against HTML/report payload.

The companion may render an Excel-like preview, but final Excel delivery must be a real workbook artifact generated and verified through spreadsheet tooling.

## UI Design Rules

- Use Traditional Chinese user-facing labels.
- Default view shows report content, data previews, and workbook previews.
- Visual Companion pages must be generated as dynamic web UI from current-run structured payloads. Static HTML mocks, stale screenshots, generic JSON viewers, and hardcoded sample screens are invalid.
- Use `Build Web Apps` for user interaction structure, responsive layout, prompt repair controls, confirmation actions, and final HTML app shell when available.
- Use `Build Web Data Visualization` for real-data KPI, chart, table, pivot-like preview, and report visualization design when available.
- JSON and technical evidence are hidden behind expandable details.
- Tables support at least 50-row preview, horizontal scrolling, sticky headers, and clear source labels.
- Charts and KPI blocks must use real current-run data once Step 3 is reached.
- Empty or unavailable data must be labeled as pending, not rendered as fake values.
- Every number shown in HTML or Excel preview must have lineage to SQL raw data, SQLite enrichment, or formula semantics.
- The companion must make "confirm" and "request changes" actions obvious and persistent.

## Validation Model

The UI is simplified; validators are not simplified away.

- Validators must keep the original subagent/fresh reviewer design.
- The main agent may orchestrate, route, and summarize validator results, but must not self-certify validator pass.
- Each required validator must be produced by a fresh reviewer/subagent invocation and must record reviewer identity, input artifact paths, checked scope, timestamp, status, findings, required fixes, and residual risks.
- Validators still run at their technical gates.
- Validator evidence is grouped by 4 user steps for readability.
- A user step cannot advance if any required validator for its internal phase coverage is `fail` or `blocked`.
- `warning` may proceed only where reversible, and must be explicitly accepted before final delivery.
- Any data, SQL, HTML, Excel, or payload change invalidates affected downstream validators.

## Documentation Changes Needed

Update these skill files after this design is approved:

- `skills/wferp-report/SKILL.md`: define 13-phase internal engine plus 4-step user-facing UI.
- `skills/wferp-report/references/harness.md`: replace current checkpoint presentation with the 4-step user flow and phase mapping.
- `skills/wferp-report/references/checkpoint-payload-schema.md`: add user-step payload and confirmation identity requirements.
- `skills/wferp-report/references/excel-intake.md`: add source-to-output logic contract and formula consistency requirements.
- `skills/wferp-report/references/sqlite-enrichment.md`: describe how SQLite/lookup evidence appears in user steps 1 and 3.
- `skills/wferp-report/references/validators.md`: clarify validators remain technical gates but are grouped by user step in UI.
- Add `skills/wferp-report/references/visual-companion-ui.md`: define 4-step UI, prompt repair loop, plugin ownership, real-data rendering rules, and Excel preview requirements.
- Add or update Excel output docs to require `spreadsheets` for true `.xlsx` delivery.

## Implementation Scope After Approval

Implementation should be planned separately. Likely work areas:

- Visual Companion page structure and user-step navigation.
- Payload aggregation from existing technical checkpoints into 4 user steps.
- Prompt repair persistence and routing metadata.
- Real-data rendering for 50-row previews.
- HTML report preview integration with web app/data visualization capabilities.
- Excel workbook preview and final `.xlsx` generation path through spreadsheet tooling.
- Tests for current run identity, prompt repair POST, confirmation persistence, 50-row preview, stale run rejection, and no mock data in Step 3.

## Acceptance Criteria

- User sees only 4 main Visual Companion steps.
- Internal 13 phases and validators remain intact.
- Step 1 clearly explains source-to-output data logic.
- Step 3 renders real current-run raw/enriched data, HTML report preview, and Excel workbook preview.
- Data preview default is 50 rows.
- Prompt repair from Visual Companion routes back to the main agent and blocks forward progress.
- Final delivery includes real HTML and real `.xlsx` when Excel output is requested.
- No fake data, stale run page, static JSON viewer, or silent fallback is accepted.

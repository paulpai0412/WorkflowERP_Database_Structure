# Visual Companion UI

The Visual Companion is a 4-step user-facing report workbench over the 13-phase technical harness.

## User Steps

1. Source-to-Output Logic
2. SQL Query
3. Data Result and Report Design
4. Final Delivery

## Dynamic UI Requirement

When available, use Build Web Apps and Build Web Data Visualization to design and implement the Visual Companion and final HTML report UI. Do not replace this with a static checkpoint page, stale screenshot, generic JSON viewer, fake chart, or fake preview.

## Real Data Requirement

Step 3 renders current-run raw rows, SQLite enriched rows, KPI/chart/table previews, and Excel workbook preview. Default table preview is 50 rows. Step 3 must clearly label whether data comes from production SELECT evidence, local SQLite enrichment, workbook extraction, or user-provided prompt assumptions.

## Prompt Repair

Each step must include prompt-based change request controls. A repair prompt writes `blocking_repair_request` to `state.json` and blocks forward progress until the smallest affected slice is repaired and validators rerun.

## Excel Preview

The companion may show an Excel-like workbook preview, but final `.xlsx` generation and verification use the spreadsheets skill and `@oai/artifact-tool`. Do not use `openpyxl` as the default workbook-generation path for this skill.

## Confirmation Contract

Confirmations must be written through the harness endpoint or CLI so they persist `run_id`, `checkpoint_id`, `payload_hash`, `confirmation_id`, `comment`, and `selectedOptions`. A stale confirmation must never unlock a newer checkpoint.

## Validator Contract

Required validators are fresh reviewer or subagent artifacts. The main agent may summarize validator results, but must not self-approve a gate. Validator evidence must include reviewer identity, checked scope, input artifact paths, timestamp, and concrete findings.

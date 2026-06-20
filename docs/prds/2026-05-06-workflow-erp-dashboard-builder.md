# PRD: Workflow ERP Dashboard Builder

## Problem Statement

Workflow ERP users can currently browse schema documentation and use the SQL tooling to generate SQL Server 2000-compatible, `SELECT`-only SQL from natural-language prompts. That solves the query-generation problem, but it does not give data analysts a complete path from a natural-language data question to a reviewed chart and a shareable Dashboard.

Today, an analyst still needs to manually bridge several risky steps: confirm that generated SQL returns the intended data, decide how the result should be visualized, arrange multiple charts into a Dashboard, apply a consistent visual design, and publish a view-only link for consumers. Without a governed product flow, SQL correctness, chart correctness, visual consistency, refresh behavior, and published-link access are all easy to drift apart.

## Solution

Build a v1 Workflow ERP Dashboard Builder that sits above the existing NL-to-SQL and validation stack.

The product lets a user enter a natural-language prompt, generate one validated `SELECT` SQL statement, execute it against a read-only replica, and present the result for Analyst Approval. After the SQL execution result is approved, the analyst creates one or more charts using form-based Chart Specs, sends those charts to a draggable/resizable Dashboard Canvas, chooses one LLM-presented Design Template derived from approved `DESIGN.md` patterns, and submits the Dashboard for final approval. Once approved, the Dashboard becomes a Published Dashboard with a token-accessible Published Dashboard Link.

For v1, Published Dashboards query the read-only replica when viewed and may auto-refresh at a configured bounded frequency. They do not query the live production ERP database directly by default.

## MVP Scope

The MVP is the smallest end-to-end slice that proves a governed path from natural-language data request to Published Dashboard.

- The analyst can submit a natural-language prompt and receive one validated SQL Server 2000-compatible `SELECT` statement.
- The SQL result can be executed against the read-only replica through the existing validation and execution boundary.
- The analyst can review concrete result evidence before approving the query result for chart creation.
- The analyst can create charts from approved query results using form-based Chart Specs.
- The MVP chart set includes table, KPI card, bar chart, and line chart. Additional chart types are deferred until the core flow is stable.
- The analyst can place and resize charts on a grid-based Dashboard Canvas.
- The analyst can choose one Design Template from a curated set of generic `DESIGN.md`-derived template options.
- The analyst or approver can preview the Dashboard and grant final Analyst Approval before publication.
- The system can publish an immutable Published Dashboard version with a token-accessible Published Dashboard Link.
- The Published Dashboard opens in view-only mode from a valid token link.
- The Published Dashboard can query the read-only replica on view and can auto-refresh within product-defined frequency bounds.
- The publisher can revoke a Published Dashboard Link.

## Acceptance Criteria

1. Given a supported natural-language prompt, when the analyst requests SQL generation, then the system produces exactly one SQL Server 2000-compatible `SELECT` statement or a clear refusal/error state.
2. Given generated SQL, when the system validates it, then non-`SELECT`, multi-statement, DDL/DML, stored procedure, hallucinated table/column, and SQL Server 2000-incompatible SQL are rejected before execution.
3. Given a valid generated SQL statement, when execution is requested, then the query runs only through the read-only execution boundary against the read-only replica.
4. Given a query execution result, when the analyst reviews it, then the UI shows result evidence including SQL, validation status, execution timestamp, returned columns, row count, sample rows, and configured aggregate checks when present.
5. Given an unapproved query result, when the analyst tries to create a chart, then chart creation is blocked.
6. Given an approved query result, when the analyst creates a Chart Spec, then the system accepts valid table, KPI card, bar chart, and line chart specs through forms and rejects invalid field mappings.
7. Given one or more valid Chart Specs, when the analyst adds them to the Dashboard Canvas, then each chart is placed in a grid cell layout that can be moved, resized, persisted, and replayed without overlap or out-of-bounds placement.
8. Given curated Design Templates, when the analyst asks for template options, then the LLM presents generic descriptive options and the Dashboard applies only one selected template at a time.
9. Given a Dashboard draft, when final Analyst Approval has not been granted, then the system cannot create or update a Published Dashboard from that draft.
10. Given a final-approved Dashboard version, when it is published, then the system creates an immutable Published Dashboard version and an opaque token Published Dashboard Link.
11. Given a valid, unexpired, unrevoked Published Dashboard Link, when a viewer opens it, then the Dashboard renders in view-only mode and does not expose authoring controls.
12. Given a revoked, expired, malformed, or unpublished token link, when a viewer opens it, then access is denied without exposing dashboard data.
13. Given a Published Dashboard with auto-refresh configured, when the refresh interval is below the product minimum or above allowed policy, then the system rejects the setting.
14. Given a Published Dashboard query refresh failure, when the viewer is on the Dashboard, then the UI shows a safe stale/error state instead of silently presenting stale data as current.
15. Given an existing Published Dashboard, when SQL, Dashboard Data Source, or query semantics change, then the system requires re-approval before those changes can be republished.
16. Given approval, publish, revoke, expire, token access denial, or refresh failure events, when they occur, then the system records auditable events.
17. Given the MVP is complete, when exercised end-to-end, then a user can go from prompt to validated SQL, approved result, chart creation, grid canvas layout, Design Template selection, final approval, token publication, token viewing, auto-refresh, and link revocation without bypassing validation gates.

## User Stories

1. As a data analyst, I want to enter a natural-language data prompt, so that I can start analysis without manually finding ERP tables and columns.
2. As a data analyst, I want the system to generate exactly one `SELECT` SQL statement, so that the query is constrained to a safe read-only shape.
3. As a data analyst, I want generated SQL to be checked against SQL Server 2000 compatibility, so that the query can run in the supported Workflow ERP environment.
4. As a data analyst, I want generated SQL to be checked against schema metadata, so that hallucinated tables and columns are rejected before execution.
5. As a data analyst, I want prompt/SQL consistency checks, so that obvious mismatches between my prompt and the generated SQL are caught.
6. As a data analyst, I want SQL execution to use a read-only replica, so that dashboard work does not directly load or risk the live production ERP database.
7. As a data analyst, I want to preview returned rows and columns, so that I can confirm the result matches the business question.
8. As a data analyst, I want to see result metadata such as row count and required columns, so that I can review data correctness before visualization.
9. As a data analyst, I want to approve a SQL execution result, so that only reviewed data can be used for chart creation.
10. As a data analyst, I want rejected query results to remain editable as drafts, so that I can revise the prompt or query path and try again.
11. As a data analyst, I want to create a Chart Spec from an approved query result, so that the chart is tied to reviewed data.
12. As a data analyst, I want to choose chart type through form controls, so that I do not need to write visualization-library JSON.
13. As a data analyst, I want to map x-axis, y-axis, and series fields through form controls, so that chart semantics are explicit.
14. As a data analyst, I want to set chart title, colors, sorting, and number/date formatting, so that the chart is readable and presentation-ready.
15. As a data analyst, I want invalid Chart Specs to be rejected before rendering, so that broken charts cannot enter a Dashboard.
16. As a data analyst, I want to send a chart to the Dashboard Canvas, so that I can compose a Dashboard from multiple approved charts.
17. As a data analyst, I want to repeat the prompt-to-chart flow, so that I can add multiple charts to the same Dashboard.
18. As a data analyst, I want to drag charts on a grid Dashboard Canvas, so that I can arrange Dashboard layout visually.
19. As a data analyst, I want to resize charts on the Dashboard Canvas, so that each chart can receive the right amount of space.
20. As a data analyst, I want grid layout changes to persist, so that the Published Dashboard matches the reviewed arrangement.
21. As a data analyst, I want the layout system to prevent invalid grid states, so that charts do not overlap or render outside the Dashboard Canvas.
22. As a data analyst, I want the LLM to batch-present Design Template options, so that I can choose a visual style quickly.
23. As a data analyst, I want Design Templates to use generic descriptive names, so that the product does not present copied brand names as official themes.
24. As a data analyst, I want only one selected Design Template applied at a time, so that Dashboard styling remains predictable.
25. As a data analyst, I want to preview the Dashboard before publishing, so that I can check charts, layout, and template together.
26. As an approver, I want final Analyst Approval before publishing, so that only reviewed Dashboard versions become Published Dashboards.
27. As an approver, I want to review the SQL result evidence, Chart Specs, layout, template, and refresh policy before publishing, so that approval covers the complete Dashboard behavior.
28. As a data analyst, I want a Published Dashboard to be versioned, so that published content is not silently changed by editing a draft.
29. As a data analyst, I want SQL or data-source changes to require re-approval, so that published analytics do not drift from reviewed data.
30. As a data analyst, I want visual-only draft edits to be recorded, so that Dashboard changes remain auditable.
31. As a publisher, I want to create a Published Dashboard Link, so that viewers can access the approved Dashboard through a standalone URL.
32. As a publisher, I want the Published Dashboard Link to use an unguessable token, so that access is not based on predictable URLs.
33. As a publisher, I want a Published Dashboard Link to be revocable, so that shared access can be removed when needed.
34. As a publisher, I want a Published Dashboard Link to support expiration, so that access can be time-bounded.
35. As a viewer, I want a valid token link to open a read-only Published Dashboard, so that I can consume analytics without changing them.
36. As a viewer, I want revoked, expired, malformed, or unpublished links to be denied, so that unavailable Dashboards are not exposed.
37. As a viewer, I want clear stale-data or refresh-error indicators, so that I do not mistake old data for current data.
38. As a data analyst, I want to configure Dashboard auto-refresh frequency within product-defined bounds, so that viewers can see updated data without overloading the replica.
39. As a system operator, I want refresh frequency limits, query timeouts, and row limits, so that Published Dashboards cannot exhaust the read-only replica.
40. As a system operator, I want audit events for approval, publishing, link revocation, expiration, and refresh failure, so that sensitive ERP-derived analytics can be traced.
41. As a maintainer, I want the Dashboard Builder to reuse the existing SQL safety and validation stack, so that prompt-to-SQL behavior remains consistent with current Workflow ERP tooling.
42. As a maintainer, I want Dashboard-specific behavior to live above the SQL tooling layer, so that chart, canvas, and publishing concerns do not pollute the core SQL generator.

## Implementation Decisions

- The Dashboard Builder is a new product layer above the existing Workflow ERP SQL-generation stack. It reuses the current prompt-to-SQL, SQL policy validation, metadata validation, prompt/SQL consistency, execution validation, and database-client concepts rather than replacing them.
- v1 uses the read-only replica as the Dashboard Data Source. Published Dashboards do not directly query live production ERP by default.
- Generated SQL must remain one SQL Server 2000-compatible `SELECT` statement. Non-`SELECT` intent, multi-statement SQL, DDL/DML, stored procedure execution, and SQL Server 2000-incompatible constructs remain forbidden.
- Query execution for the Dashboard Builder must go through a read-only execution boundary with health checks, query timeout handling, row limits, and clear failure states.
- Analyst Approval is required after SQL execution result review before chart creation, and again before a Dashboard version becomes a Published Dashboard.
- Publishing creates or updates an approved Published Dashboard version. A Published Dashboard must not be a live mutable draft.
- SQL, Dashboard Data Source, or query-semantics changes require re-approval before republishing. Visual-only changes should be recorded and may follow a lighter review policy, but they must not silently alter data meaning.
- A Published Dashboard Link uses an opaque, non-guessable token scoped to one Published Dashboard. Tokens must be revocable and should support expiration.
- Published Dashboard access is view-only. Token access does not imply authoring permissions.
- Published Dashboards query the read-only replica when viewed and may poll at a configured auto-refresh frequency. Refresh frequency must be bounded by product limits.
- The v1 refresh model is view-time query plus optional bounded polling. A separate background scheduling system is not required unless a later phase adds cached refresh jobs.
- Chart Specs are edited through forms. The v1 interface supports chart type, field mapping, sorting, title, color, and number/date formatting. Users do not directly edit the underlying visualization-library JSON.
- Chart Spec validation is server-side and chart-type aware. Invalid mappings or unsupported field combinations cannot be published.
- The Dashboard Canvas uses a draggable and resizable grid layout. Layout persistence stores grid coordinates and dimensions for each chart and validates bounds and collisions.
- Design Templates are copied or adapted from the MIT-licensed `VoltAgent/awesome-design-md` collection, renamed into generic descriptive theme names, and presented by the LLM for user selection.
- Only one selected Design Template is applied to a Dashboard at a time. The product should not blend multiple templates in v1.
- The PRD expects several deep modules with stable, testable interfaces:
  - SQL Request Orchestrator: prompt-to-SQL generation, validation, execution request, and result evidence capture.
  - Approval Workflow State Machine: draft, result-reviewed, approved, published, revoked, and expired lifecycle transitions.
  - Published Link Policy: token issuance, validation, expiration, revocation, and view-only enforcement.
  - Refresh Policy Evaluator: refresh interval bounds, disabled auto-refresh, view-time refresh, and safe failure states.
  - Chart Spec Validator: chart-type-specific field mapping and formatting validation.
  - Dashboard Canvas Layout Engine: grid placement, resize, collision rules, bounds validation, and serialization.
  - Design Template Catalog: curated `DESIGN.md` template ingestion, generic naming, LLM presentation, and selected-template application.
  - Published Dashboard Runtime: render a published version, resolve token access, run bounded queries, and present refresh states.
- Audit events should capture query result approval, publish, revoke, expire, token access denial, and query refresh failure.

## Testing Decisions

- Tests should verify external behavior and state transitions, not implementation details. Pure modules should be tested with fake dependencies where possible.
- SQL safety tests should cover unsafe SQL, schema-invalid SQL, prompt mismatches, SQL Server 2000-incompatible syntax, and non-`SELECT` intent.
- SQL execution integration tests should use the existing test database pattern and verify read-only execution, expected columns, row-count bounds, and aggregate checks.
- Approval Workflow State Machine tests should cover draft to result-reviewed, approved, published, revoked, expired, rejected, and invalid transition paths.
- Published Link Policy tests should cover valid token, malformed token, expired token, revoked token, unpublished Dashboard, and view-only behavior.
- Refresh Policy Evaluator tests should cover disabled refresh, allowed frequency, too-frequent intervals, view-time query, query timeout, and refresh failure stale/error output.
- Chart Spec Validator tests should cover valid and invalid specs for each supported v1 chart type, including missing fields, unsupported dimensions, invalid formatting, and field type mismatches.
- Dashboard Canvas Layout Engine tests should cover add, move, resize, overlap rejection, bounds rejection, serialization, and persisted layout replay.
- Design Template Catalog tests should verify generic naming, allowed template selection, one-template-at-a-time application, and deterministic presentation payloads.
- Published Dashboard Runtime integration tests should cover token-access view, read-only rendering, bounded refresh, data-source failure, and revocation denial.
- Browser-level tests are required when a web UI exists, especially for chart creation, grid dragging/resizing, template selection, and Published Dashboard rendering.
- Snapshot tests for generated Design Template output should only be used if template output is deterministic enough to remain stable.

## Out of Scope

- Writeback dashboards, ERP updates, inserts, deletes, DDL, stored procedures, or arbitrary production DB execution.
- Arbitrary SQL execution that bypasses the existing SQL safety and validation stack.
- Arbitrary custom JavaScript, arbitrary custom CSS, or direct free-form chart JSON editing.
- Live production ERP queries as the default v1 Dashboard Data Source.
- Real-time streaming dashboards or sub-second refresh.
- Full BI semantic layer, metric catalog, lineage browser, or advanced drill-through system.
- Full role-based access control or row-level security beyond token revocation and expiration.
- Multi-template composition or user-uploaded unvetted design systems.
- Collaborative real-time Dashboard editing.
- Email delivery, scheduled exports, alerting, dashboard marketplace, or external embedding SDK.
- Replacing the legacy schema publication workflow or changing static schema documentation generation.

## Further Notes

- The existing repo already defines SQL correctness operationally: SQL is not correct merely because it parses; execution result shape and values must match the prompt intent.
- Token-accessible Published Dashboard Links are convenient but weaker than authenticated access. v1 must treat token leakage as a real risk and include revocation, expiration, and audit logging.
- Read-only replicas reduce production ERP risk but can still be overloaded by expensive reads. v1 must include refresh frequency bounds, query timeouts, and row limits.
- Analyst Approval should capture concrete evidence: prompt, generated SQL, validation results, execution timestamp, returned columns, sample rows, row counts, and aggregate checks when applicable.
- Design Templates from `VoltAgent/awesome-design-md` are MIT licensed, but v1 should use generic descriptive names and avoid copying protected brand assets or presenting brand names as official Dashboard themes.
- This PRD is published as a GitHub issue with `needs-triage` and is also stored locally so future issue breakdown can reference the same source text.

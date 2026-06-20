# PRD: SQL-to-Dashboard E2E Test Cases

## Problem Statement

Workflow ERP now has a CLI/library Dashboard Builder path that can move from a natural-language prompt to a Published Dashboard, but the current E2E coverage is still mostly library-driven and uses limited deterministic data. Maintainers need executable test case intent that proves the SQL-to-Dashboard path against real SQL execution evidence, deterministic test data, Analyst Approval gates, Chart Spec creation, Dashboard Canvas publication, and Published Dashboard Link denial behavior.

The product also has a future browser-level requirement, but the repository does not yet contain a Dashboard Web UI that Playwright can operate. The immediate problem is therefore to materialize CLI/library E2E test cases that are honest about the current surface while preserving a clear path to browser Playwright tests once a Web UI exists.

## Solution

Create a focused SQL-to-Dashboard E2E test-case PRD for the current CLI/library surface. The test cases will use the existing Dashboard Builder modules, the existing SQL Server test database pattern, live LLM SQL generation as non-blocking evidence, and deterministic AI-authored SQL fixture data committed to the repository.

The first business scenario is `查詢2026年的工程預算明細`. It will extend the existing ACTMK budget-detail fixture shape to include three 2026 rows and one 2025 contrast row. SQL correctness will be judged by execution result shape and values, not exact SQL string equality. The expected 2026 aggregate is `sum(MK006)=450000`.

The first batch contains four executable test intents:

1. Happy path from prompt to Published Dashboard.
2. SQL result shape/value correctness against the real test database.
3. Query Analyst Approval gate before Chart Spec creation.
4. Revoked Published Dashboard Link denial without dashboard data exposure.

Browser Playwright E2E remains deferred until a real Dashboard Web UI exists.

## User Stories

1. As a data analyst, I want the 2026 engineering budget prompt to execute against deterministic test data, so that SQL result evidence can be reviewed with confidence.
2. As a data analyst, I want SQL correctness to be judged by returned columns, row count, sample rows, and aggregate checks, so that a query is not accepted merely because it parses.
3. As a data analyst, I want the 2025 contrast budget row excluded from the 2026 prompt result, so that prompt/year semantics are verified.
4. As a data analyst, I want the query result to require Analyst Approval before chart creation, so that unreviewed data cannot enter a Dashboard.
5. As a data analyst, I want an approved query result to produce a bar Chart Spec using `MK006`, so that budget values can be visualized consistently.
6. As a data analyst, I want the Chart Spec to be placed on a Dashboard Canvas, so that the SQL result can flow into the current Dashboard Builder surface.
7. As an approver, I want final Analyst Approval before publishing, so that only reviewed Dashboard versions become Published Dashboards.
8. As a publisher, I want the Published Dashboard Link to render view-only output before revocation, so that consumers can safely view approved analytics.
9. As a publisher, I want a revoked Published Dashboard Link to return a denial state, so that shared access can be removed.
10. As a security reviewer, I want revoked-link denial to expose no dashboard payload and no data rows, so that ERP-derived analytics do not leak after revocation.
11. As a maintainer, I want live LLM E2E runs to produce evidence without blocking release by default, so that model availability does not create false product failures.
12. As a maintainer, I want deterministic regression coverage beside live LLM evidence, so that product behavior can still be gated reliably.
13. As a maintainer, I want AI-generated test data committed as a fixed SQL fixture, so that test results are reproducible and reviewable.
14. As a maintainer, I want one issue per executable E2E test case, so that workers and verifiers can repair and validate cases independently.
15. As a future UI implementer, I want browser Playwright E2E marked as deferred until a Dashboard Web UI exists, so that tests do not pretend to cover a non-existent browser surface.

## Implementation Decisions

- The current implementation target is the CLI/library surface, not a browser UI.
- Browser Playwright tests are out of the first implementation batch because no Dashboard Web UI currently exists in the repository.
- The primary business prompt is `查詢2026年的工程預算明細`.
- The primary ERP table remains ACTMK because the current SQL tooling, test database, and Dashboard Builder E2E already use ACTMK budget-detail semantics.
- Test data will be generated with AI assistance during development, reviewed, and committed as deterministic SQL fixture data. Tests must not call AI to create fixture rows at runtime.
- The fixture data shape is three 2026 ACTMK budget rows plus one 2025 contrast row.
- The expected aggregate for 2026 rows is `sum(MK006)=450000`.
- SQL correctness is defined by execution result shape and values: returned columns, row count, sample rows, and aggregate checks.
- Exact SQL string equality is not the primary correctness assertion. SQL may be inspected for diagnostics, but passing depends on result evidence.
- Live LLM generation is part of the first-batch E2E evidence, but it is non-blocking by default because model/network availability can fail independently of product behavior.
- A deterministic regression bucket must accompany live LLM evidence and should remain suitable for release gating.
- The first Chart Spec is a bar chart using `MK006` as the budget value field.
- The first batch should be split into four E2E test case issues after this PRD is accepted.
- Existing domain terms must be preserved: Analyst Approval, Chart Spec, Dashboard Canvas, Published Dashboard, Published Dashboard Link, and Dashboard Data Source.

## Testing Decisions

- Tests should verify external behavior and state transitions rather than implementation details.
- The SQL correctness test must execute against the SQL Server test database in `DB_ENV=test`.
- The SQL correctness test must assert required returned columns including `MK002` and `MK006`.
- The SQL correctness test must assert the 2026 result row count is three.
- The SQL correctness test must assert `sum(MK006)=450000` for the 2026 result set.
- The SQL correctness test must ensure the 2025 contrast row does not satisfy the 2026 prompt intent.
- The approval gate test must prove that Chart Spec creation fails before query result Analyst Approval and succeeds after approval.
- The Dashboard flow test must prove the approved query result can become a bar Chart Spec, enter a Dashboard Canvas, receive final Analyst Approval, become a Published Dashboard, and render through a Published Dashboard Link.
- The link-denial test must prove revoked token access returns a denial state with no dashboard payload and no data rows.
- Live LLM test evidence must classify failures as product, test data seed, infra, or LLM availability before any release decision treats the failure as blocking.
- Deterministic regression tests should continue to cover the existing governed query, Chart Spec, Dashboard Canvas, Design Template Catalog, and Published Dashboard runtime surfaces.
- Evidence packets must stay compact and reference artifact manifests rather than embedding raw SQL logs, raw Playwright traces, screenshots, or verbose command output.
- Browser Playwright cases should be represented only as deferred intent until a real Dashboard Web UI route, server startup command, and stable selectors exist.

### E2E Test Intents

```yaml
e2e_test_intents:
  - test_case_id: "E2E-001"
    source_ac: "Dashboard Builder AC17"
    scenario: "Prompt-to-Published-Dashboard happy path for 2026 engineering budget."
    surface: "cli|library"
    expected_outcome: "Live LLM governed query returns execution evidence, Analyst Approval unlocks bar Chart Spec creation, Dashboard Canvas preview publishes, and a Published Dashboard Link renders view-only."
    risk_level: "high"
    executable_status: "draft"
  - test_case_id: "E2E-002"
    source_ac: "SQL execution correctness"
    scenario: "2026 engineering budget SQL executes against deterministic test data with expected columns, row count, sample rows, and aggregate value."
    surface: "sql|cli|library"
    expected_outcome: "Returned columns include MK002 and MK006, row_count is 3 for 2026 rows, and sum(MK006)=450000 while the 2025 contrast row is excluded."
    risk_level: "high"
    executable_status: "draft"
  - test_case_id: "E2E-003"
    source_ac: "Dashboard Builder AC5"
    scenario: "Unapproved query result cannot create a Chart Spec."
    surface: "library"
    expected_outcome: "Chart Spec creation fails with a query-approval gate before Analyst Approval and succeeds after approval."
    risk_level: "medium"
    executable_status: "draft"
  - test_case_id: "E2E-004"
    source_ac: "Dashboard Builder AC12"
    scenario: "Revoked Published Dashboard Link denies access without exposing dashboard data."
    surface: "library"
    expected_outcome: "Valid link renders before revocation; revoked link returns denied with no dashboard payload and no data rows."
    risk_level: "medium"
    executable_status: "draft"
```

## Out of Scope

- Implementing a Dashboard Web UI.
- Writing browser Playwright tests before a Dashboard Web UI exists.
- Treating live LLM E2E failure as an automatic release blocker.
- Runtime AI generation of test data.
- Exact SQL string equality as the primary correctness assertion.
- Production database execution or any non-test Dashboard Data Source.
- DML, DDL, stored procedures, writeback dashboards, or arbitrary SQL execution.
- Replacing the existing Dashboard Builder PRD.
- Replacing the legacy static schema documentation workflow.

## Further Notes

- This PRD supplements the existing Workflow ERP Dashboard Builder PRD by focusing on executable E2E test-case materialization.
- The current repository has a CLI/library Dashboard Builder surface and static schema documentation, but no Dashboard Web UI. Future browser Playwright E2E should be introduced only after a real UI route, startup command, and stable selectors exist.
- SQL Server 2019 test containers cannot truly emulate SQL Server 2000 compatibility level 80. The repo should continue using explicit SQL Server 2000 syntax guards and deterministic execution checks.
- The next step after this PRD is accepted is to use `to-issues` to create independently grabbable issues for the fixture, SQL correctness case, Dashboard flow case, approval gate case, and link denial case.

# Workflow ERP Analytics Context

## Glossary

### Published Dashboard

A versioned dashboard that has been approved for use and exposed through a standalone URL. A Published Dashboard is distinct from the existing published static schema documentation artifacts (`index.html`, `df_style.css`, and `HTML/`).

### Dashboard Data Source

The database or stored result set that a Published Dashboard reads from when rendering charts.

For v1, Published Dashboards use a read-only replica as their Dashboard Data Source. They do not query the live production ERP database directly by default.

### Published Dashboard Link

The standalone URL used to view a Published Dashboard.

For v1, a Published Dashboard Link is token-accessible: anyone with a valid unguessable token can view the dashboard without signing in. Tokens must be revocable and should support expiration because the link can expose ERP-derived analytics data if shared outside the intended audience.

### Dashboard Refresh Policy

The rule that determines when a Published Dashboard re-queries its Dashboard Data Source.

For v1, Published Dashboards query the read-only replica when viewed and may be configured with an automatic refresh frequency. The refresh frequency must be bounded by product-level limits to protect the replica from excessive dashboard traffic.

### Analyst Approval

Human confirmation by a data analyst that a query result or dashboard version is correct enough to proceed.

For v1, Analyst Approval is required after SQL execution result review before chart creation, and again before publishing a dashboard version as a Published Dashboard.

### Chart Spec

The product-level configuration for rendering a chart from an approved query result.

For v1, a Chart Spec is edited through form controls such as chart type, x/y/series field mapping, sorting, title, color, and number/date formatting. Users do not directly edit the underlying visualization-library JSON in v1.

### Design Template

A dashboard visual style derived from a `DESIGN.md`-style markdown design system document.

For v1, Design Templates are copied or adapted from the MIT-licensed `VoltAgent/awesome-design-md` collection, renamed into generic descriptive theme names, and batch-presented by the LLM for user selection. The product should avoid exposing brand names as official dashboard theme names, and should apply one selected Design Template at a time to avoid bloated LLM context and inconsistent generated styling.

### Dashboard Canvas

The editable layout surface where approved charts are placed before dashboard publication.

For v1, the Dashboard Canvas uses a draggable and resizable grid layout rather than a freeform whiteboard. Layout should be stored as grid coordinates and dimensions for each chart so a Published Dashboard can render consistently.

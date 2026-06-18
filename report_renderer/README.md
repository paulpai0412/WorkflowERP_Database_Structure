# WFERP Report Renderer

This is a standalone React renderer for WFERP report checkpoints and final report payloads. It consumes structured JSON only and does not connect to databases or execute SQL.

## Payload sources

- `window.__WFERP_REPORT_PAYLOAD__`
- `?payload=/examples/expense-analysis-checkpoint.json`
- The bundled checkpoint example when no payload is provided

## Component layer note

The beautiful-article/reacticle package is not used in this project because it is not available as an installed local dependency for this worktree. The renderer implements a compatible internal semantic component layer using React sections, panels, status rows, option controls, data tables, and report blocks with restrained business-report styling.

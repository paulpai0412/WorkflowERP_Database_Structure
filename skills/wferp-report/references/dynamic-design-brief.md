# Dynamic Design Brief

Every report run creates `report-design-brief.json` before final export. The brief is the user-visible design contract for the report, not a hard-coded catalog decision.

The agent must show both:

- a Traditional Chinese text summary
- a semi-real HTML visual checkpoint

The user can request more charts, different chart types, a different layout, table position changes, density changes, evidence display changes, or different management narrative emphasis. The confirmed brief is immutable input for final single HTML export.

Required brief content:

- report intent and target audience
- selected or generated layout recipe
- chart recipe with required columns
- table recipe and Excel-like table features
- interaction recipe, including cross-filter and evidence drawer expectations
- visual direction and density
- embedded data policy

Checkpoint behavior:

1. Generate brief from the validated report package and user prompt.
2. Render semi-real HTML visual checkpoint using real labels, row counts, aggregates, and expected chart/table blocks.
3. Ask user to confirm or revise.
4. If user changes prompt/query condition but wants the same style, preserve the previous style capsule and regenerate SQL/data/package before export.
5. If requested layout/chart cannot be supported by current data shape, open a design adjustment checkpoint before replacing the chart.

Repair slice:

- Chart mismatch: adjust only chart recipe and affected visual checkpoint.
- Layout mismatch: adjust only layout recipe and checkpoint HTML.
- Evidence presentation mismatch: adjust only evidence drawer/section recipe.
- Data mismatch: do not repair design first; return to SQL/data preview phases.

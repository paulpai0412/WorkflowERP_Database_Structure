# Design Contract

`report_designs/index.json` is the canonical allowlist. It must list exactly:

1. `financial-control`
2. `executive-summary`
3. `detail-ledger`
4. `exception-audit`
5. `operations-review`
6. `trend-briefing`

Each report design must define the following front matter keys:

- `id`
- `label`
- `best_for`
- `required_sections`
- `default_components`
- `chart_policy`
- `table_policy`
- `kpi_policy`
- `tone`
- `layout_density`
- `validator_focus`

The content after front matter should explain how the report should be structured, what evidence is expected, and which validator concerns are most important. Front matter arrays and objects should be JSON-compatible so the Python catalog loader can parse the metadata without a YAML dependency.

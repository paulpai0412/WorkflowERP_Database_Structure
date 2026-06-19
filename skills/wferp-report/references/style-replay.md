# Style Replay

Style replay lets a future prompt reuse the visual style of a prior report while regenerating SQL, data, package, and final single HTML.

The prior report provides `report-style-capsule.json`. The new run must still regenerate SQL, rerun SQL safety, execute the DB query through the governed harness, and build a new report package.

The old HTML never connects to DB and never executes SQL. It is only a visual and evidence reference.

Replay contract:

1. Load prior `report-style-capsule.json`.
2. Apply capsule to the new prompt.
3. Generate new read-only SQL from WFERP schema and relationship context.
4. Run SQL safety and schema validators.
5. Ask user to confirm SQL before DB execution.
6. Execute governed DB query and build new package.
7. Compare new columns against capsule chart recipes.
8. If compatible, regenerate single HTML with the same `style_fingerprint` and new package data.
9. If incompatible, open a design adjustment checkpoint and ask user to approve replacement chart/layout.

Required validation:

- `style_fingerprint` remains stable when style-only fields are unchanged.
- New prompt and new package data must differ from the prior report when the user changed query conditions.
- Stale rows, stale aggregates, and stale SQL are delivery blockers.
- Incompatible chart recipes must set `requires_checkpoint=true`.

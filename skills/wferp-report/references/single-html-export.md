# Single HTML Export

Final delivery produces a fully self-contained single HTML report plus an evidence packet. This flow happens only after the package, design brief, visual checkpoint, final review, and delivery gate are valid.

Rules:

- HTML must not depend on CDN, remote fonts, external scripts, external stylesheets, fetch, WebSocket, or any remote runtime.
- HTML must not contain credentials, DB connection strings, passwords, or environment values.
- HTML 不得連 DB。
- HTML 不得執行 SQL。
- HTML uses embedded compressed report package data only.
- network requests = 0 during validation.
- The exported HTML must support offline interaction only against embedded package rows, aggregates, validator evidence, and style capsule metadata.

Required artifacts:

- `delivery/report.html`
- `delivery/evidence/report-package.json`
- `delivery/evidence/report-design-brief.json`
- `delivery/evidence/report-style-capsule.json`
- `delivery/evidence/query.sql`
- `delivery/evidence/validator-results.json`
- `delivery/evidence/delivery-manifest.json`

Execution contract:

1. Build `report-package.json` from confirmed SQL, DB execution result, aggregates, excluded rows, validator summary, accepted residual risks, and delivery gate.
2. Validate package before any final HTML write. If package validation fails, stop and open the smallest repair checkpoint.
3. Build dynamic design brief from the package and user-confirmed visual choices.
4. Build style capsule from style-only brief fields. Do not include query result row count or stale data in the style fingerprint.
5. Export `delivery/report.html` and evidence packet.
6. Run static single HTML validation. Required result: `valid=true`, no external network references, no credentials, no missing package marker.

Repair checkpoint rules:

- Missing package marker: repair exporter/runtime only.
- External resource reference: repair renderer/export template only.
- Credential string: repair package/evidence source and rerun package validation.
- Invalid manifest/hash: repair exporter manifest generation only.
- User asks layout/chart changes after export: reopen dynamic design brief checkpoint, regenerate HTML with the same data package or a newly confirmed package.

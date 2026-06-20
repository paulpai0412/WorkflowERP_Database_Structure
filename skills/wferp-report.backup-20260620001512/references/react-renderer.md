# React Renderer

Use React only when it makes the HTML report easier to build or test.

Renderer rules:
- Read data from generated payload JSON or an embedded payload object.
- Keep visual components small and deterministic.
- Prefer tables and charts that support scanning and comparison.
- Do not fetch production data from the browser.
- The browser report must use already extracted local data.

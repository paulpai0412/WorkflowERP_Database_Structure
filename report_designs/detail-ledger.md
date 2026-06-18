---
id: "detail-ledger"
label: "明細查詢表"
best_for: ["逐筆交易", "來源欄位確認", "明細匯出"]
required_sections: ["query-scope", "detail-table", "field-notes", "data-limitations"]
default_components: ["DataTable", "InsightBlock"]
chart_policy: {"preferred": [], "avoid": ["pie", "donut", "area"]}
table_policy: {"density": "compact", "summary_rows": true, "conditional_formatting": true}
kpi_policy: {"include_variance": false, "include_budget_ratio": false}
tone: "查核導向、逐筆、可回溯"
layout_density: "dense"
validator_focus: ["column_completeness", "row_count_consistency", "filter_transparency"]
---

# 明細查詢表

Use this design when the user primarily needs a reliable ledger-style output with source keys and minimal interpretation.

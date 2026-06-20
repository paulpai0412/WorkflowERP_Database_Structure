---
id: "exception-audit"
label: "異常稽核表"
best_for: ["缺漏檢查", "超額檢查", "控制例外"]
required_sections: ["audit-scope", "exception-rules", "exception-table", "risk-notes", "recommendations"]
default_components: ["KpiGrid", "DataTable", "InsightBlock", "RecommendationList"]
chart_policy: {"preferred": ["bar", "stacked-bar"], "avoid": ["pie"]}
table_policy: {"density": "compact", "summary_rows": true, "conditional_formatting": true}
kpi_policy: {"include_variance": true, "include_budget_ratio": false}
tone: "稽核、證據優先、風險分級"
layout_density: "dense"
validator_focus: ["rule_clarity", "source_key_presence", "residual_risk_disclosure"]
---

# 異常稽核表

Use this design when the report must prioritize exceptions and give the user a concrete audit trail for follow-up.

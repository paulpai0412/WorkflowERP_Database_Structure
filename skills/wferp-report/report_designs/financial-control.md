---
id: "financial-control"
label: "財務控制"
best_for: ["費用分析", "預算差異", "異常控管"]
required_sections: ["executive-summary", "kpi-overview", "trend", "detail-table", "recommendations"]
default_components: ["KpiGrid", "ChartBlock", "DataTable", "InsightBlock", "RecommendationList"]
chart_policy: {"preferred": ["bar", "stacked-bar", "combo"], "avoid": ["pie"]}
table_policy: {"density": "compact", "summary_rows": true, "conditional_formatting": true}
kpi_policy: {"include_variance": true, "include_budget_ratio": true}
tone: "管理控制、明確、可追責"
layout_density: "dense"
validator_focus: ["aggregate_consistency", "variance_explanation", "exception_visibility"]
---

# 財務控制

Use this design for expense analysis, budget variance review, voucher checks, tax review, and control-oriented management reports. It should lead with verified totals and variances, keep exception rows visible, and make every recommendation traceable to source fields, SQL filters, and aggregate checks.

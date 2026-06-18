---
id: "operations-review"
label: "營運檢討報告"
best_for: ["部門檢討", "流程瓶頸", "採購庫存營運"]
required_sections: ["operations-summary", "kpi-overview", "ranking", "process-observations", "recommendations"]
default_components: ["KpiGrid", "ChartBlock", "DataTable", "InsightBlock", "RecommendationList"]
chart_policy: {"preferred": ["bar", "line", "stacked-bar"], "avoid": ["pie"]}
table_policy: {"density": "balanced", "summary_rows": true, "conditional_formatting": true}
kpi_policy: {"include_variance": true, "include_budget_ratio": false}
tone: "營運改善、可執行、追蹤導向"
layout_density: "balanced"
validator_focus: ["grouping_correctness", "metric_definition", "actionability"]
---

# 營運檢討報告

Use this design for repeatable operating reviews where users compare performance across departments, periods, or process stages.

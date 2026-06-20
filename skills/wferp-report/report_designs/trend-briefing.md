---
id: "trend-briefing"
label: "趨勢簡報"
best_for: ["月趨勢", "季趨勢", "年度變動"]
required_sections: ["trend-summary", "period-chart", "period-table", "change-analysis", "next-observations"]
default_components: ["KpiGrid", "ChartBlock", "DataTable", "InsightBlock"]
chart_policy: {"preferred": ["line", "area", "combo"], "avoid": ["pie", "donut"]}
table_policy: {"density": "comfortable", "summary_rows": true, "conditional_formatting": true}
kpi_policy: {"include_variance": true, "include_budget_ratio": false}
tone: "趨勢解讀、期間清楚、保留假設"
layout_density: "balanced"
validator_focus: ["period_ordering", "delta_recalculation", "missing_period_disclosure"]
---

# 趨勢簡報

Use this design for management briefings where direction, acceleration, and outlier periods matter more than individual transaction rows.

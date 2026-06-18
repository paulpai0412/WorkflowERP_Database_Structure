---
id: "executive-summary"
label: "管理摘要"
best_for: ["主管簡報", "快速決策", "重點風險"]
required_sections: ["executive-summary", "kpi-overview", "ranked-insights", "recommendations"]
default_components: ["KpiGrid", "ChartBlock", "InsightBlock", "RecommendationList"]
chart_policy: {"preferred": ["bar", "line", "combo"], "avoid": ["donut"]}
table_policy: {"density": "comfortable", "summary_rows": true, "conditional_formatting": false}
kpi_policy: {"include_variance": true, "include_budget_ratio": false}
tone: "主管視角、精簡、結論先行"
layout_density: "balanced"
validator_focus: ["metric_traceability", "evidence_for_claims", "risk_assumption_split"]
---

# 管理摘要

Use this design when the user needs a concise management-facing view. The report should lead with the decision-relevant answer, then show supporting metrics, risks, and recommended actions without turning into a ledger.

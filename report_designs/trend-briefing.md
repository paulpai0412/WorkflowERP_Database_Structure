---
id: trend-briefing
name: 趨勢簡報
best_for: 月、季、年序列分析與變動說明
required_sections: 趨勢摘要, 期間資料, 變動解讀, 後續觀察
optional_sections: 同比比較, 環比比較, 異常期間
visual_policy: 使用時間序列圖與變動標記，避免與資料粒度不符的圖形
table_policy: 表格需保留期間、指標、變動量與變動率
analysis_policy: 解釋趨勢時需標示資料涵蓋期間與缺漏
recommendation_policy: 建議需聚焦後續監控與需補資料的期間
react_component_hints: TrendLinePanel, PeriodDeltaTable, ChangeNarrative
validator_checklist: 期間排序正確, 變動率可重算, 缺漏期間揭露
---

# 趨勢簡報

Use this design for management briefings where direction, acceleration, and outlier periods matter more than individual transaction rows.

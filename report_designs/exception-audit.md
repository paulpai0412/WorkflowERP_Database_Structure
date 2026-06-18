---
id: exception-audit
name: 異常稽核表
best_for: 找出缺漏、未確認、作廢、超額、負數或不一致資料
required_sections: 稽核範圍, 異常規則, 異常清單, 風險說明
optional_sections: 排除清單, 抽樣建議, 修正追蹤
visual_policy: 視覺只用於突出嚴重度與數量，不弱化逐筆證據
table_policy: 異常表格需保留來源鍵值、規則名稱、嚴重度與說明
analysis_policy: 每個異常類型需說明判定條件與可能原因
recommendation_policy: 建議需分成資料修正、流程控制與人工確認
react_component_hints: AuditRuleSummary, SeverityBadgeTable, ResidualRiskPanel
validator_checklist: 異常規則明確, 來源鍵值存在, residual risks 完整
---

# 異常稽核表

Use this design when the report must prioritize exceptions and give the user a concrete audit trail for follow-up.

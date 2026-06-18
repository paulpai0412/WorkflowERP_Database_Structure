---
id: financial-control
name: 財務控制分析
best_for: 費用、預算、傳票、稅額與控制例外分析
required_sections: 控制摘要, 金額彙總, 異常項目, 查核建議
optional_sections: 部門比較, 科目比較, 明細抽樣
visual_policy: 使用金額排序、占比與例外標記，不使用無法查核來源的裝飾圖
table_policy: 金額欄位需保留小計與總計，異常列需能回查來源欄位
analysis_policy: 區分已確認資料、待確認資料與排除資料
recommendation_policy: 每項建議需對應控制風險與後續查核步驟
react_component_hints: ControlSummaryBand, ExceptionTable, AmountBreakdownChart
validator_checklist: 金額合計正確, 排除條件清楚, SQL來源可追溯
---

# 財務控制分析

This design emphasizes auditability. It is the default choice for expense analysis, voucher checks, tax review, and management reports that must explain exclusions.

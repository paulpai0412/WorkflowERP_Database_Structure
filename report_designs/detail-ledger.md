---
id: detail-ledger
name: 明細查詢表
best_for: 逐筆交易查詢、來源欄位確認與明細匯出
required_sections: 查詢條件, 明細表格, 欄位說明, 資料限制
optional_sections: 小計, 排序說明, 匯出提示
visual_policy: 以表格為主，可用簡單標記輔助狀態，不以圖表取代明細
table_policy: 保留來源表鍵值、日期、金額、狀態與使用者要求欄位
analysis_policy: 分析文字需簡短，重點放在欄位定義與篩選條件
recommendation_policy: 建議以後續查詢或人工確認為主
react_component_hints: DetailLedgerTable, FilterSummary, FieldDefinitionPanel
validator_checklist: 欄位完整, row_count 符合預期, 篩選條件清楚
---

# 明細查詢表

Use this design when the user primarily needs a reliable ledger-style output with source keys and minimal interpretation.

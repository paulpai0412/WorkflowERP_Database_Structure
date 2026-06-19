# Repair Policy

Repair 必須是最小垂直切片。目標是修正 validator 指出的單點失敗，而不是重寫整個流程掩蓋問題。

## 最小垂直切片

每次 repair 只選一個 failed validator 對應的最小範圍：

- 來源/需求：只修 prompt 摘要、欄位 mapping 或確認 payload。
- Excel：只修欄位 lineage、公式解析或衍生欄位描述。
- SQL：只修 SQL safety、schema 欄位、join 或篩選條件。
- Data preview：只修查詢執行、row/column/aggregate evidence 或 preview payload。
- Report section：只修受影響 section 的文字、表格、圖表或建議。
- React/HTML：只修受影響 component、payload binding、layout 或 build error。

## Repair Loop

1. 指認 failed validator、status、findings、requiredFixes 與 evidence。
2. 定義 repair scope 與 minimal vertical slice。
3. 只修改該 slice 需要的檔案。
4. 重跑該 validator 與受影響的下游 validators。
5. 更新 `review/repair-log.md`。
6. 若仍失敗，新增下一筆 repair log，不覆寫前次 evidence。

## Repair Log 格式

每次修復必須由 `ReportHarness.append_repair_log()` 追加下列欄位：

```text
## sql_safety_reviewer

Failure:
Scope:
Minimal vertical slice:
Files changed:
Validation rerun:
Residual risk:
```

欄位不可省略。若沒有殘餘風險，寫 `None`。若使用者接受風險，需同時在 final review payload 的 `accepted_residual_risks` 記錄。

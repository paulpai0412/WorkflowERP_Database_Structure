# Review Checklist

最終交付前依序確認下列項目。任何一項不能確認時，產生對應 validator failure，進入 minimal vertical repair。

## Source And Excel

- 使用者 prompt、上傳檔、欄位名稱、格式、管理報表目標都已納入 source evidence。
- Excel 原始欄位、公式欄位、衍生欄位與跨表公式都有 lineage。
- 欄位來源與 WFERP schema 欄位的 mapping 沒有未說明的猜測。

## SQL And Schema

- SQL 是唯讀 SELECT。
- 無 INSERT、UPDATE、DELETE、MERGE、DROP、ALTER、CREATE、TRUNCATE、EXEC、SELECT INTO。
- Join relationship 可由 WFERP schema/relationship evidence 解釋。
- 查詢條件、日期、幣別、部門、科目或費用分類符合需求。

## Data Preview

- DB execution 有實際 rows、columns 與 aggregate evidence。
- `data_preview_reviewer` evidence 包含 numeric `row_count` 與 `column_count`。
- Preview 的欄位與筆數足以讓使用者確認報表方向。
- 排除資料、空值、異常值與公式計算結果有說明。

## Report And Visual

- 使用者已確認 report design profile 與報表內容方向。
- 每個 report section 都能連回 SQL/data preview/Excel formula evidence。
- 表格、KPI、圖表與建議沒有與資料來源矛盾。
- Chart type 適合資料，不用不合適的 pie/donut/stacked/combo 誤導比較。
- 中文標題、單位、註解、建議與管理語氣清楚。
- React report 可 build，可離線開啟，無 legacy static HTML dependency。

## Delivery Gate

- 9 個 required validators 都存在。
- 全部 `pass` 才能直接交付。
- 若存在 `warning`、`fail` 或 `blocked`，必須有 final checkpoint 的使用者確認與 `accepted_residual_risks`。
- `review/repair-log.md` 已記錄所有 repair slice、重跑驗證與殘餘風險。

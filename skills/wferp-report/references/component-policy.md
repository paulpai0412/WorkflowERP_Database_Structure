# Component Policy

wferp-report 產出的報告必須優先使用固定 React components。固定元件可被 validator 檢查資料來源、欄位 lineage、視覺結構與互動行為；不得為了排版方便任意拼貼不可驗證的 HTML。

## 允許元件

- `InsightBlock`：呈現一段管理分析、例外原因或驗證後的文字洞察。
- `MetricGrid`：呈現有 data refs 的 KPI、差異、比率與門檻狀態。
- `DataTable`：呈現查詢結果與 Excel-like 管理表格。必須支援排序、全文搜尋、數字/日期範圍篩選、分類多選、欄位顯示切換、凍結 key column、summary row、group subtotal row、條件格式、格式化與 CSV 匯出。
- `ChartBlock`：呈現 bar、stacked-bar、line、area、pie、donut、combo。必須有 title、subtitle、legend、可讀 `aria-label` mark labels、empty/error state，且在資料形狀或分類數不適合時顯示 suitability warning。
- `RecommendationList`：呈現可執行的管理建議，需連回報告中的數據或 validator evidence。
- `EvidencePanel`：呈現 SQL safety、execution validation、formula lineage、visual validator、repair history 等驗證證據。
- `RawBlockNotice`：只作為 RawBlock 例外的審核告示，不得執行任意程式碼。

## 使用規則

- 每個數字、圖表 mark、表格欄位與建議都必須可追溯到 `data_refs`、SQL result 欄位或 Excel formula lineage。
- 元件內不得執行 SQL、讀取 credentials、開啟 DB 連線、呼叫外部追蹤或動態載入遠端 script。
- 報告 section 應逐層揭露：先給管理摘要，再提供圖表/表格，最後才顯示技術 evidence。
- `ChartBlock` 不適合高分類數、缺少數值欄位或 pie/donut 分類過多時，必須降級為 `DataTable` 或顯示 suitability warning。
- `DataTable` 的互動只允許在本地瀏覽器處理已取得的查詢結果，不得在表格互動時重新查詢資料庫。
- 需要客製 HTML 時，必須先加入 `RawBlockNotice`，並遵守 `rawblock-policy.md` 的例外流程。

## Validator 檢查點

- 檢查報告只使用允許元件，或 RawBlock 已有 notice 與風險紀錄。
- 檢查 chart/table 的欄位都存在於 SQL result 或 Excel lineage。
- 檢查互動表格仍可離線運作，CSV 匯出不包含隱藏的 credentials 或 SQL 連線資訊。
- 檢查所有 RawBlock 都沒有 script、event handler、外部 iframe、DB/SQL side effect。

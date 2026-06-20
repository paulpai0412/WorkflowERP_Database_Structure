# RawBlock Policy

RawBlock 是例外機制，不是預設排版方式。wferp-report 預設只能使用固定 React components；只有固定元件無法忠實呈現已驗證內容時，才允許使用 RawBlock。

## 可使用情境

- 固定元件無法表達的特殊管理表格、稽核聲明、法遵揭露或 ERP 欄位對照說明。
- 已有 validator evidence 證明內容、欄位、公式與查詢結果一致。
- 使用者明確確認 RawBlock 的目的、資料依賴與風險等級。

## 必填紀錄

每個 RawBlock 都必須先呈現 `RawBlockNotice`，並包含：

- `id`：穩定且唯一的 RawBlock 識別碼。
- `title`：使用者可理解的標題。
- `purpose`：為何需要 RawBlock。
- `dataDependencies`：SQL result 欄位、ERP schema 欄位或 Excel formula lineage。
- `riskLevel`：`low`、`medium`、`high`。
- 替代元件不可行原因。
- 視覺 validator、資料 validator、SQL safety validator 結果。

## 禁止事項

RawBlock 不得包含：

- `<script>`、inline event handler、`eval`、`Function`、動態 import 或任意程式碼執行。
- 外部追蹤、iframe、pixel、第三方 widget 或未批准的 CDN。
- DB 連線、SQL 執行、credential 讀取、環境變數讀取或檔案系統讀寫。
- 會改變查詢結果、修改本地資料、送出使用者資料的 side effect。

## Repair 原則

- 若 validator 發現 RawBlock 違規，先嘗試改回固定元件。
- 若必須保留 RawBlock，只修最小垂直切片：移除違規節點、保留已驗證文字與資料、重新執行 validator。
- 修復後必須更新 `RawBlockNotice` 的 riskLevel 或 evidence，讓使用者可重新確認。

# Section Build

每次只建置或修復一個 section，避免大範圍改動掩蓋 validator failure。

## 協議

- 一個 section 一個檔案。
- 每個 section 必須列出 `data_refs`。
- 每個 section 完成後執行報告內容 validator。
- 若視覺或內容失敗，只修該 section 與必要 payload。

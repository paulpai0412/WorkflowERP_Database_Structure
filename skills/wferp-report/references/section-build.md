# Section Build

每次只建置或修復一個 section，避免大範圍改動掩蓋 validator failure。複雜報表允許主 agent / LLM 依已確認需求產生 React section 程式碼，但只能寫入本次 run 的 `report/sections/*.tsx`，且必須通過 harness 安全檢查與 protocol validation。

## 協議

- 一個 section 一個檔案。
- 每個 section 必須列出 `data_refs`。
- 每個 section 完成後執行報告內容 validator。
- 若視覺或內容失敗，只修該 section 與必要 payload。
- LLM 產生的 section 必須用 `generate-report-section` 寫入，不得手動繞過 harness。
- 修復既有 section 必須用 `repair-report-section`，且只替換該 section。
- 每次寫入或修復後都必須跑 `validate-report-section`。

## CLI

```bash
python3 -m skill_scripts.cli_report_harness generate-report-section \
  --run-dir wferp-report-runs/run-001 \
  --section-id 01-executive-summary \
  --component-name ExecutiveSummary01Section \
  --code-file /tmp/section.tsx

python3 -m skill_scripts.cli_report_harness validate-report-section \
  --run-dir wferp-report-runs/run-001 \
  --section-id 01-executive-summary

python3 -m skill_scripts.cli_report_harness repair-report-section \
  --run-dir wferp-report-runs/run-001 \
  --section-id 01-executive-summary \
  --component-name ExecutiveSummary01Section \
  --code-file /tmp/repaired-section.tsx
```

## Section Safety Rules

- Section 必須 export exactly one requested React function component。
- Import 只允許 `react` 與相對路徑 local components。
- Section 必須宣告 `data-refs` 或 `dataRefs`，讓 validator 可追溯資料來源。
- Section 必須 render 對應的 `data-section="<slug>"`。
- 禁止 network：`fetch`、`XMLHttpRequest`、`WebSocket`、`EventSource`、`axios`、外部 URL。
- 禁止環境/credential：`process.env`、`document.cookie`。
- 禁止動態程式：`eval`、`Function`、dynamic import、`require`。
- 禁止 browser storage side effect：`localStorage`、`sessionStorage`、`indexedDB`。
- Section 只能讀 embedded payload / props，不得連 DB、不得執行 SQL、不得讀檔案系統。

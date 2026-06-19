# Scaffold

Final report scaffold 由 `scripts/scaffold-report.sh` 建立。它複製 `assets/scaffold-template/` 到 run workspace，保留固定入口與 payload contract。

## 輸入

- run root
- report id
- selected design profile
- data preview payload

## 產出

- `package.json`
- `index.html`
- `report/Report.tsx`
- `report_payload.json`

Scaffold 只建立骨架，不替代 section build 與 final review。

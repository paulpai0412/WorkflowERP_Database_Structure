# React Renderer

React renderer 位於 repo `report_renderer/`。它只消費 structured JSON payload，不讀 DB env、不執行 SQL。checkpoint/report HTML 不得依賴舊 root `index.html` 或 `HTML/*.html`。

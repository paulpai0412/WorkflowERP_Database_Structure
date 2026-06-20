import React from "react";
import { createRoot } from "react-dom/client";
import App, { ReportPayload } from "./App";
import checkpointExample from "../examples/expense-analysis-checkpoint.json";
import "./styles.css";

declare global {
  interface Window {
    __WFERP_REPORT_PAYLOAD__?: ReportPayload;
  }
}

async function loadPayload(): Promise<ReportPayload> {
  if (window.__WFERP_REPORT_PAYLOAD__) {
    return window.__WFERP_REPORT_PAYLOAD__;
  }

  const payloadPath = new URLSearchParams(window.location.search).get("payload");
  if (payloadPath) {
    const response = await fetch(payloadPath);
    if (!response.ok) {
      throw new Error(`Unable to load report payload: ${payloadPath}`);
    }
    return (await response.json()) as ReportPayload;
  }

  return checkpointExample as ReportPayload;
}

const root = document.getElementById("root");

if (!root) {
  throw new Error("Missing #root element");
}

loadPayload()
  .then((payload) => {
    createRoot(root).render(
      <React.StrictMode>
        <App payload={payload} />
      </React.StrictMode>,
    );
  })
  .catch((error: unknown) => {
    const message = error instanceof Error ? error.message : "無法載入報表資料";
    createRoot(root).render(
      <main className="app-shell">
        <section className="panel error-panel">
          <p className="eyebrow">Renderer Error</p>
          <h1>無法載入報表資料</h1>
          <p>{message}</p>
        </section>
      </main>,
    );
  });

import React from "react";
import { createRoot } from "react-dom/client";

type ReportPayload = {
  title?: string;
  summary?: string;
  sections?: Array<{
    id: string;
    title: string;
    body?: string;
    data_refs?: string[];
  }>;
  validator_evidence?: Array<{
    validator: string;
    status: string;
  }>;
};

const payload: ReportPayload = {
  title: "WFERP 報告",
  summary: "請以 scaffold 隨附的 report_payload.json 取代此預設內容。",
  sections: [],
  validator_evidence: []
};

function Report() {
  return (
    <main style={{ fontFamily: "system-ui, sans-serif", margin: "40px auto", maxWidth: 960, lineHeight: 1.6 }}>
      <h1>{payload.title}</h1>
      <p>{payload.summary}</p>
      {(payload.sections ?? []).map((section) => (
        <section key={section.id}>
          <h2>{section.title}</h2>
          {section.body ? <p>{section.body}</p> : null}
          {section.data_refs?.length ? <small>Data refs: {section.data_refs.join(", ")}</small> : null}
        </section>
      ))}
    </main>
  );
}

createRoot(document.getElementById("root") as HTMLElement).render(<Report />);

import React from "react";
import { createRoot } from "react-dom/client";

type ReportSection = {
  id: string;
  title: string;
  body?: string;
  data_refs?: string[];
};

type ValidatorEvidence = {
  validator: string;
  status: string;
};

type ReportPayload = {
  title?: string;
  summary?: string;
  sections?: ReportSection[];
  validator_evidence?: ValidatorEvidence[];
};

const payload: ReportPayload = {
  title: "WFERP Report",
  summary: "Replace this scaffold payload with the generated report payload JSON.",
  sections: [],
  validator_evidence: []
};

function Report() {
  return (
    <main style={{ fontFamily: "system-ui, sans-serif", margin: "40px auto", maxWidth: 960, lineHeight: 1.6 }}>
      <h1>{payload.title}</h1>
      {payload.summary ? <p>{payload.summary}</p> : null}
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

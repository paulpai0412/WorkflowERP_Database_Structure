import { FinalReportPayload } from "../App";
import DataPreviewTable from "./DataPreviewTable";

interface ReportPageProps {
  payload: FinalReportPayload;
}

const optionLabels: Array<[keyof NonNullable<FinalReportPayload["options"]>, string]> = [
  ["charts", "圖表"],
  ["tables", "表格"],
  ["analysis", "分析"],
  ["recommendations", "建議"],
];

export default function ReportPage({ payload }: ReportPageProps) {
  const enabledOptions = optionLabels.filter(([key]) => payload.options?.[key]);
  const sections = payload.sections ?? [];

  return (
    <main className="app-shell report-shell">
      <header className="page-header">
        <div>
          <p className="eyebrow">WFERP Management Report</p>
          <h1>{payload.title}</h1>
          {payload.subtitle ? <p className="subtitle">{payload.subtitle}</p> : null}
        </div>
        <div className="status-stack option-flags" aria-label="報告內容旗標">
          {enabledOptions.map(([, label]) => (
            <span className="status-item positive" key={label}>
              {label}
            </span>
          ))}
        </div>
      </header>

      <section className="report-grid" aria-label="報告章節">
        {sections.map((section) => (
          <article className={`panel report-section ${section.type}`} key={`${section.type}-${section.title}`}>
            <p className="eyebrow">{section.type}</p>
            <h2>{section.title}</h2>
            {section.body ? <p>{section.body}</p> : null}
            {section.items ? (
              <ul>
                {section.items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : null}
          </article>
        ))}
      </section>

      {payload.options?.charts ? (
        <section className="panel chart-panel" aria-label="圖表摘要">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Chart</p>
              <h2>費用占比圖表</h2>
            </div>
          </div>
          <div className="bar-chart" aria-hidden="true">
            <span style={{ height: "72%" }} />
            <span style={{ height: "48%" }} />
            <span style={{ height: "64%" }} />
            <span style={{ height: "36%" }} />
          </div>
        </section>
      ) : null}

      {payload.options?.tables ? <DataPreviewTable preview={payload.dataPreview} /> : null}
    </main>
  );
}

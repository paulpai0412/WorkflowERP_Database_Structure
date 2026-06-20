import React from "react";
import { FinalReportPayload } from "../App";
import ChartBlock, { ChartDatum } from "./ChartBlock";
import DataPreviewTable from "./DataPreviewTable";
import InsightBlock from "./InsightBlock";
import RecommendationList from "./RecommendationList";

interface ReportPageProps {
  payload: FinalReportPayload;
}

const optionLabels: Array<[keyof NonNullable<FinalReportPayload["options"]>, string]> = [
  ["charts", "圖表"],
  ["tables", "表格"],
  ["analysis", "分析"],
  ["recommendations", "建議"],
];

function buildChartData(payload: FinalReportPayload): ChartDatum[] {
  const preview = payload.dataPreview;
  if (!preview || preview.rows.length === 0) {
    return [];
  }
  const labelColumn =
    preview.columns.find((column) => preview.rows.some((row) => typeof row[column] === "string")) ?? preview.columns[0];
  const valueColumn = preview.columns.find((column) => preview.rows.some((row) => typeof row[column] === "number"));
  if (!valueColumn) {
    return [];
  }
  const totals = new Map<string, number>();
  preview.rows.forEach((row) => {
    const label = String(row[labelColumn] ?? "未分類");
    const value = typeof row[valueColumn] === "number" ? row[valueColumn] : Number(row[valueColumn] ?? 0);
    totals.set(label, (totals.get(label) ?? 0) + (Number.isFinite(value) ? value : 0));
  });
  return Array.from(totals.entries()).map(([label, value]) => ({ label, value }));
}

export default function ReportPage({ payload }: ReportPageProps) {
  const useReactState = (React as unknown as {
    useState: <T>(initial: T) => [T, (value: T | ((current: T) => T)) => void];
  }).useState;
  const [selectedLabel, setSelectedLabel] = useReactState<string | null>(null);
  const [evidenceOpen, setEvidenceOpen] = useReactState(false);
  const enabledOptions = optionLabels.filter(([key]) => payload.options?.[key]);
  const sections = payload.sections ?? [];
  const chartData = buildChartData(payload);
  const selectedRows =
    selectedLabel && payload.dataPreview
      ? payload.dataPreview.rows.filter((row) =>
          Object.values(row).some((value) => String(value) === selectedLabel),
        )
      : null;
  const filteredPreview =
    selectedRows && payload.dataPreview
      ? {
          ...payload.dataPreview,
          rowCount: selectedRows.length,
          rows: selectedRows,
        }
      : payload.dataPreview;
  const evidence = payload.validatorEvidence ?? payload.validatorEvidenceSummary ?? [];

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
        {sections.map((section) => {
          if (section.type === "analysis") {
            return (
              <div key={`${section.type}-${section.title}`}>
                <InsightBlock title={section.title} body={section.body} />
              </div>
            );
          }
          if (section.type === "recommendations") {
            return (
              <div key={`${section.type}-${section.title}`}>
                <RecommendationList title={section.title} items={section.items} />
              </div>
            );
          }
          return (
            <article className={`panel report-section ${section.type}`} key={`${section.type}-${section.title}`}>
              <p className="eyebrow">{section.type}</p>
              <h2>{section.title}</h2>
              {section.body ? <p>{section.body}</p> : null}
            </article>
          );
        })}
      </section>

      {payload.options?.charts ? (
        <>
          <ChartBlock type="bar" title="費用占比圖表" subtitle="依第一個文字欄位彙總第一個數值欄位" data={chartData} />
          {chartData.length > 0 ? (
            <section className="panel cross-filter-panel" aria-label="離線交叉篩選">
              <div className="section-heading">
                <div>
                  <p className="eyebrow">Offline Filter</p>
                  <h2>圖表交叉篩選</h2>
                </div>
                {selectedLabel ? <span className="count-pill">已篩選</span> : null}
              </div>
              <div className="button-row filter-button-row">
                {chartData.map((datum) => (
                  <button
                    key={datum.label}
                    type="button"
                    className="secondary-button"
                    onClick={() => setSelectedLabel(datum.label)}
                  >
                    篩選 {datum.label}
                  </button>
                ))}
                {selectedLabel ? (
                  <button type="button" className="secondary-button" onClick={() => setSelectedLabel(null)}>
                    清除篩選
                  </button>
                ) : null}
              </div>
              {selectedLabel ? <p className="muted active-filter-text">已套用篩選：{selectedLabel}</p> : null}
            </section>
          ) : null}
        </>
      ) : null}

      {payload.options?.tables ? <DataPreviewTable preview={filteredPreview} enableControls /> : null}

      <section className="panel evidence-drawer">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Evidence</p>
            <h2>驗證證據</h2>
          </div>
          <button type="button" className="secondary-button" onClick={() => setEvidenceOpen((current) => !current)}>
            Evidence
          </button>
        </div>
        {evidenceOpen ? <pre>{JSON.stringify(evidence, null, 2)}</pre> : null}
      </section>
    </main>
  );
}

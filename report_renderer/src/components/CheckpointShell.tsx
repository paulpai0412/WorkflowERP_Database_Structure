import React from "react";
import { CheckpointPayload } from "../App";
import ActionBar from "./ActionBar";
import ManagementView from "./ManagementView";
import { executionLabel } from "./SqlReviewPanel";
import TechnicalView from "./TechnicalView";

type ActiveTab = "management" | "technical";

interface CheckpointShellProps {
  payload: CheckpointPayload;
}

export default function CheckpointShell({ payload }: CheckpointShellProps) {
  const useReactState = (React as unknown as {
    useState: <T>(initial: T) => [T, (value: T) => void];
  }).useState;
  const [activeTab, setActiveTab] = useReactState<ActiveTab>("management");
  const [selectedReportType, setSelectedReportType] = useReactState<string | undefined>(payload.reportTypes?.[0]?.id);
  const validation = payload.sqlReview?.validation;

  return (
    <main className="app-shell">
      <header className="page-header">
        <div>
          <p className="eyebrow">WFERP Report Checkpoint</p>
          <h1>{payload.title}</h1>
          {payload.step ? <p className="subtitle">Checkpoint：{payload.step}</p> : null}
        </div>
        <div className="status-stack" aria-label="查詢狀態">
          <span className="status-item positive">唯讀：{validation?.readonly === false ? "否" : "是"}</span>
          <span className="status-item neutral">{executionLabel(validation?.executionStatus)}</span>
        </div>
      </header>

      <nav className="tab-bar" role="tablist" aria-label="checkpoint view">
        <button
          aria-controls="management-panel"
          aria-selected={activeTab === "management"}
          className="tab-button"
          id="management-tab"
          onClick={() => setActiveTab("management")}
          role="tab"
          type="button"
        >
          主管檢視
        </button>
        <button
          aria-controls="technical-panel"
          aria-selected={activeTab === "technical"}
          className="tab-button"
          id="technical-tab"
          onClick={() => setActiveTab("technical")}
          role="tab"
          type="button"
        >
          技術明細
        </button>
      </nav>

      {activeTab === "management" ? (
        <ManagementView
          payload={payload}
          selectedReportType={selectedReportType}
          onReportTypeChange={setSelectedReportType}
        />
      ) : (
        <TechnicalView payload={payload} />
      )}

      <ActionBar
        actions={payload.actions}
        checkpointId={payload.checkpointId}
        confirmUrl={payload.confirmUrl}
        selectedOptions={{ reportType: selectedReportType ?? "" }}
      />
    </main>
  );
}

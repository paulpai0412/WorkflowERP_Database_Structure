import { CheckpointPayload } from "../App";
import AggregateCheckPanel from "./AggregateCheckPanel";
import DataPreviewTable from "./DataPreviewTable";
import FieldFormulaReview from "./FieldFormulaReview";
import ReportOptionPanel from "./ReportOptionPanel";

interface ManagementViewProps {
  payload: CheckpointPayload;
  selectedReportType?: string;
  onReportTypeChange: (reportType: string) => void;
}

export default function ManagementView({
  payload,
  selectedReportType,
  onReportTypeChange,
}: ManagementViewProps) {
  const exceptions = payload.exceptions ?? [];

  return (
    <div className="view-stack" role="tabpanel" aria-labelledby="management-tab" id="management-panel">
      <section className="panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Requirement</p>
            <h2>需求摘要</h2>
          </div>
        </div>
        <p className="summary-text">{payload.requirementSummary ?? "尚未提供需求摘要。"}</p>
      </section>

      <FieldFormulaReview review={payload.fieldFormulaReview} />
      <DataPreviewTable preview={payload.dataPreview} />
      <AggregateCheckPanel checks={payload.aggregateChecks} />

      <section className="panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Exceptions & Risks</p>
            <h2>例外與風險</h2>
          </div>
          <span className="count-pill">{exceptions.length} 項</span>
        </div>
        {exceptions.length > 0 ? (
          <ul className="risk-list">
            {exceptions.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : (
          <p className="muted">目前沒有額外例外或風險。</p>
        )}
      </section>

      <ReportOptionPanel
        choices={payload.reportTypes}
        selectedId={selectedReportType}
        onChange={onReportTypeChange}
      />

      <section className="panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Next Step</p>
            <h2>下一步動作</h2>
          </div>
        </div>
        <p className="muted">確認欄位、公式、資料預覽與彙總檢核後，請使用頁面底部操作送出決策。</p>
      </section>
    </div>
  );
}

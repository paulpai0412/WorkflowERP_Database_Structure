import { CheckpointPayload } from "../App";
import DataPreviewTable from "./DataPreviewTable";
import ReportOptionPanel from "./ReportOptionPanel";

interface CheckpointPageProps {
  payload: CheckpointPayload;
}

function executionLabel(status?: string) {
  if (status === "executed") {
    return "已執行 SQL";
  }
  if (status === "blocked") {
    return "已阻擋查詢";
  }
  return "尚未執行 SQL";
}

export default function CheckpointPage({ payload }: CheckpointPageProps) {
  const validation = payload.sqlReview?.validation;

  return (
    <main className="app-shell">
      <header className="page-header">
        <div>
          <p className="eyebrow">WFERP Report Checkpoint</p>
          <h1>{payload.title}</h1>
        </div>
        <div className="status-stack" aria-label="查詢狀態">
          <span className="status-item positive">唯讀：{validation?.readonly === false ? "否" : "是"}</span>
          <span className="status-item neutral">{executionLabel(validation?.executionStatus)}</span>
        </div>
      </header>

      <section className="panel sql-panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">SQL Review</p>
            <h2>{payload.sqlReview?.title ?? "SQL 查詢審核"}</h2>
          </div>
          <span className="count-pill">
            禁止語法 {validation?.blockedKeywords?.length ?? 0}
          </span>
        </div>
        <pre aria-label="SQL 查詢內容">{payload.sqlReview?.sql ?? "尚未產生 SQL"}</pre>
      </section>

      <DataPreviewTable preview={payload.dataPreview} />
      <ReportOptionPanel choices={payload.reportTypes} />

      {payload.actions && payload.actions.length > 0 ? (
        <section className="action-bar" aria-label="使用者操作">
          {payload.actions.map((action, index) => (
            <button className={index === 0 ? "primary-button" : "secondary-button"} key={action} type="button">
              {action}
            </button>
          ))}
        </section>
      ) : null}
    </main>
  );
}

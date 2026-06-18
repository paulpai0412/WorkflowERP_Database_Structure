import { SqlReview } from "../App";

interface SqlReviewPanelProps {
  review?: SqlReview;
}

export function executionLabel(status?: string) {
  if (status === "executed") {
    return "已執行 SQL";
  }
  if (status === "blocked") {
    return "已阻擋查詢";
  }
  return "尚未執行 SQL";
}

export default function SqlReviewPanel({ review }: SqlReviewPanelProps) {
  const validation = review?.validation;
  const blockedKeywords = validation?.blockedKeywords ?? [];

  return (
    <section className="panel sql-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">SQL Review</p>
          <h2>{review?.title ?? "SQL 查詢審核"}</h2>
        </div>
        <div className="status-stack compact">
          <span className="status-item positive">唯讀：{validation?.readonly === false ? "否" : "是"}</span>
          <span className="status-item neutral">{executionLabel(validation?.executionStatus)}</span>
          <span className="count-pill">禁止語法 {blockedKeywords.length}</span>
        </div>
      </div>
      <pre aria-label="SQL 查詢內容">{review?.sql ?? "尚未產生 SQL"}</pre>

      <div className="detail-grid">
        <section>
          <h3>SQL 安全檢查</h3>
          {(review?.safetyChecks ?? []).length > 0 ? (
            <ul>
              {review?.safetyChecks?.map((check) => <li key={check}>{check}</li>)}
            </ul>
          ) : (
            <p className="muted">尚無安全檢查明細。</p>
          )}
        </section>
        <section>
          <h3>執行環境</h3>
          <p>{review?.executionEnvironment ?? "尚未提供執行環境。"}</p>
        </section>
      </div>
    </section>
  );
}

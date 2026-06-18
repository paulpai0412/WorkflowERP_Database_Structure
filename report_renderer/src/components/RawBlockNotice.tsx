interface RawBlockNoticeProps {
  id: string;
  title: string;
  purpose: string;
  dataDependencies: string[];
  riskLevel: "low" | "medium" | "high";
  unsafeCode?: string;
  onUnsafeExecute?: () => void;
}

const riskLabels: Record<RawBlockNoticeProps["riskLevel"], string> = {
  low: "低",
  medium: "中",
  high: "高",
};

export default function RawBlockNotice({
  id,
  title,
  purpose,
  dataDependencies,
  riskLevel,
}: RawBlockNoticeProps) {
  return (
    <section className={`panel raw-block-notice ${riskLevel}`} aria-label={`RawBlock policy ${id}`}>
      <div className="section-heading">
        <div>
          <p className="eyebrow">RawBlock Policy Notice</p>
          <h2>{title}</h2>
        </div>
        <span className={`status-item ${riskLevel === "low" ? "positive" : "neutral"}`}>
          風險等級：{riskLevel}
        </span>
      </div>
      <dl className="rawblock-meta">
        <div>
          <dt>ID</dt>
          <dd>{id}</dd>
        </div>
        <div>
          <dt>風險</dt>
          <dd>{riskLabels[riskLevel]}</dd>
        </div>
        <div>
          <dt>目的</dt>
          <dd>{purpose}</dd>
        </div>
      </dl>
      <div className="rawblock-dependencies">
        <h3>Data Dependencies</h3>
        <ul>
          {dataDependencies.map((dependency) => (
            <li key={dependency}>{dependency}</li>
          ))}
        </ul>
      </div>
      <p className="muted">
        RawBlock 僅能作為已驗證內容的呈現容器；本元件不執行 script、SQL、DB 連線或外部追蹤。
      </p>
    </section>
  );
}

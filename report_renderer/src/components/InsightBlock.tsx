interface InsightBlockProps {
  title: string;
  body?: string;
  tone?: "neutral" | "warning" | "positive";
}

export default function InsightBlock({ title, body, tone = "neutral" }: InsightBlockProps) {
  return (
    <article className={`panel report-section insight-block ${tone}`}>
      <p className="eyebrow">Insight</p>
      <h2>{title}</h2>
      {body ? <p>{body}</p> : <p className="muted">尚無分析內容。</p>}
    </article>
  );
}

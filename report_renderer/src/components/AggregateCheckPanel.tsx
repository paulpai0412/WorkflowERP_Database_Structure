import { AggregateCheck } from "../App";

interface AggregateCheckPanelProps {
  checks?: AggregateCheck[];
}

function statusLabel(status: AggregateCheck["status"]) {
  if (status === "pass") {
    return "通過";
  }
  if (status === "warning") {
    return "需注意";
  }
  return "未通過";
}

export default function AggregateCheckPanel({ checks = [] }: AggregateCheckPanelProps) {
  return (
    <section className="panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Aggregate Checks</p>
          <h2>彙總檢核</h2>
        </div>
        <span className="count-pill">{checks.length} 項</span>
      </div>
      {checks.length > 0 ? (
        <div className="check-grid">
          {checks.map((check) => (
            <article className={`check-card ${check.status}`} key={check.label}>
              <div>
                <strong>{check.label}</strong>
                {check.note ? <p>{check.note}</p> : null}
              </div>
              <dl>
                <div>
                  <dt>預期</dt>
                  <dd>{check.expected ?? "未提供"}</dd>
                </div>
                <div>
                  <dt>實際</dt>
                  <dd>{check.actual ?? "未提供"}</dd>
                </div>
                <div>
                  <dt>狀態</dt>
                  <dd>{statusLabel(check.status)}</dd>
                </div>
              </dl>
            </article>
          ))}
        </div>
      ) : (
        <p className="muted">尚無彙總檢核結果。</p>
      )}
    </section>
  );
}

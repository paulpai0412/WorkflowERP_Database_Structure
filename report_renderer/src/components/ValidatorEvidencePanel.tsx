import { ValidatorEvidence } from "../App";

interface ValidatorEvidencePanelProps {
  evidence?: ValidatorEvidence[];
}

function statusLabel(status: ValidatorEvidence["status"]) {
  if (status === "pass") {
    return "通過";
  }
  if (status === "warning") {
    return "需注意";
  }
  return "未通過";
}

export default function ValidatorEvidencePanel({ evidence = [] }: ValidatorEvidencePanelProps) {
  return (
    <section className="panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Validator Evidence</p>
          <h2>驗證證據</h2>
        </div>
        <span className="count-pill">{evidence.length} 筆</span>
      </div>
      {evidence.length > 0 ? (
        <div className="evidence-list">
          {evidence.map((item) => (
            <article className={`evidence-item ${item.status}`} key={`${item.validator}-${item.message}`}>
              <strong>{item.validator}</strong>
              <span>{statusLabel(item.status)}</span>
              <p>{item.message}</p>
              {item.evidencePath ? <small>{item.evidencePath}</small> : null}
            </article>
          ))}
        </div>
      ) : (
        <p className="muted">尚無 validator evidence。</p>
      )}
    </section>
  );
}

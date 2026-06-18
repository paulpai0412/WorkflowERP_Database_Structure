import { FieldFormulaReviewPayload } from "../App";

interface FieldFormulaReviewProps {
  review?: FieldFormulaReviewPayload;
}

function renderItems(
  title: string,
  emptyLabel: string,
  items: NonNullable<FieldFormulaReviewPayload["fields"]>,
) {
  return (
    <div className="review-list">
      <h3>{title}</h3>
      {items.length > 0 ? (
        <ul>
          {items.map((item) => (
            <li key={`${title}-${item.label}`}>
              <strong>{item.label}</strong>
              {item.source ? <span>{item.source}</span> : null}
              {item.expression ? <span>{item.expression}</span> : null}
              {item.confirmation ? <small>{item.confirmation}</small> : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">{emptyLabel}</p>
      )}
    </div>
  );
}

export default function FieldFormulaReview({ review }: FieldFormulaReviewProps) {
  const fields = review?.fields ?? [];
  const formulas = review?.formulas ?? [];

  return (
    <section className="panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Field & Formula</p>
          <h2>欄位與公式確認</h2>
        </div>
        <span className="count-pill">{fields.length + formulas.length} 項</span>
      </div>
      <div className="split-grid">
        {renderItems("資料欄位", "尚無欄位確認資料。", fields)}
        {renderItems("使用者公式", "尚無公式確認資料。", formulas)}
      </div>
    </section>
  );
}

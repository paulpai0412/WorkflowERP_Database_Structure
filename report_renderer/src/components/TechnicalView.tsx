import { CheckpointPayload } from "../App";
import SqlReviewPanel from "./SqlReviewPanel";
import ValidatorEvidencePanel from "./ValidatorEvidencePanel";

interface TechnicalViewProps {
  payload: CheckpointPayload;
}

export default function TechnicalView({ payload }: TechnicalViewProps) {
  const mappings = payload.sqlReview?.schemaMapping ?? [];
  const relationshipPath = payload.sqlReview?.relationshipPath ?? [];

  return (
    <div className="view-stack" role="tabpanel" aria-labelledby="technical-tab" id="technical-panel">
      <SqlReviewPanel review={payload.sqlReview} />

      <section className="panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Schema Mapping</p>
            <h2>資料表與欄位對應</h2>
          </div>
          <span className="count-pill">{mappings.length} 欄</span>
        </div>
        {mappings.length > 0 ? (
          <div className="table-scroll">
            <table aria-label="資料表與欄位對應">
              <thead>
                <tr>
                  <th scope="col">輸出欄位</th>
                  <th scope="col">資料表</th>
                  <th scope="col">欄位</th>
                  <th scope="col">說明</th>
                </tr>
              </thead>
              <tbody>
                {mappings.map((mapping) => (
                  <tr key={`${mapping.field}-${mapping.table}-${mapping.column}`}>
                    <td>{mapping.field}</td>
                    <td>{mapping.table}</td>
                    <td>{mapping.column}</td>
                    <td>{mapping.note ?? ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted">尚無 schema/table/field mapping。</p>
        )}
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Relationship Path</p>
            <h2>關聯路徑</h2>
          </div>
          <span className="count-pill">{relationshipPath.length} 段</span>
        </div>
        {relationshipPath.length > 0 ? (
          <ol className="relationship-list">
            {relationshipPath.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ol>
        ) : (
          <p className="muted">尚無關聯路徑。</p>
        )}
      </section>

      <ValidatorEvidencePanel evidence={payload.validatorEvidence} />
    </div>
  );
}

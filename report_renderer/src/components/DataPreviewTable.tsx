import { DataPreview } from "../App";

interface DataPreviewTableProps {
  preview?: DataPreview;
  title?: string;
}

function formatCell(value: string | number | boolean | null) {
  if (value === null) {
    return "";
  }
  if (typeof value === "boolean") {
    return value ? "是" : "否";
  }
  return String(value);
}

export default function DataPreviewTable({ preview, title = "資料預覽" }: DataPreviewTableProps) {
  if (!preview) {
    return (
      <section className="panel">
        <h2>{title}</h2>
        <p className="muted">尚無預覽資料。</p>
      </section>
    );
  }

  return (
    <section className="panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Data Preview</p>
          <h2>{title}：{preview.rowCount} 筆</h2>
        </div>
        <span className="count-pill">{preview.columns.length} 欄</span>
      </div>
      <div className="table-scroll">
        <table aria-label="資料預覽">
          <thead>
            <tr>
              {preview.columns.map((column) => (
                <th key={column} scope="col">
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {preview.rows.map((row, rowIndex) => (
              <tr key={`${rowIndex}-${preview.columns.join("-")}`}>
                {preview.columns.map((column) => (
                  <td key={column}>{formatCell(row[column])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

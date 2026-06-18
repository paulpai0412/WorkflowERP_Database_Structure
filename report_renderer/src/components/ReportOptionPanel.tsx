import { ReportTypeChoice } from "../App";

interface ReportOptionPanelProps {
  choices?: ReportTypeChoice[];
  selectedId?: string;
  onChange?: (choiceId: string) => void;
}

export default function ReportOptionPanel({ choices = [], selectedId, onChange }: ReportOptionPanelProps) {
  if (choices.length === 0) {
    return null;
  }

  return (
    <section className="panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Report Type</p>
          <h2>報告格式選擇</h2>
        </div>
      </div>
      <div className="option-grid" role="radiogroup" aria-label="報告格式">
        {choices.map((choice, index) => (
          <label className="report-option" key={choice.id}>
            <input
              type="radio"
              name="report-type"
              checked={(selectedId ?? choices[0]?.id) === choice.id}
              onChange={() => onChange?.(choice.id)}
              readOnly={!onChange}
            />
            <span>
              <strong>{choice.label}</strong>
              <small>{choice.description}</small>
            </span>
          </label>
        ))}
      </div>
    </section>
  );
}

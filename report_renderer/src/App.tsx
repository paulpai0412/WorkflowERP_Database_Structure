import CheckpointPage from "./components/CheckpointPage";
import ReportPage from "./components/ReportPage";

export type TableRow = Record<string, string | number | boolean | null>;

export interface DataPreview {
  rowCount: number;
  columns: string[];
  rows: TableRow[];
}

export interface SqlReview {
  title?: string;
  sql: string;
  validation?: {
    readonly?: boolean;
    blockedKeywords?: string[];
    executionStatus?: "not_executed" | "executed" | "blocked";
  };
  schemaMapping?: FieldMapping[];
  relationshipPath?: string[];
  safetyChecks?: string[];
  executionEnvironment?: string;
}

export interface ReportTypeChoice {
  id: string;
  label: string;
  description: string;
}

export interface FieldFormulaReviewPayload {
  fields?: FieldFormulaItem[];
  formulas?: FieldFormulaItem[];
}

export interface FieldFormulaItem {
  label: string;
  source?: string;
  expression?: string;
  confirmation?: string;
}

export interface FieldMapping {
  field: string;
  table: string;
  column: string;
  note?: string;
}

export interface AggregateCheck {
  label: string;
  expected?: string | number;
  actual?: string | number;
  status: "pass" | "warning" | "fail";
  note?: string;
}

export interface ValidatorEvidence {
  validator: string;
  status: "pass" | "warning" | "fail";
  message: string;
  evidencePath?: string;
}

export interface CheckpointPayload {
  kind: "checkpoint";
  checkpointId?: string;
  title: string;
  step?: string;
  confirmUrl?: string;
  requirementSummary?: string;
  fieldFormulaReview?: FieldFormulaReviewPayload;
  sqlReview?: SqlReview;
  dataPreview?: DataPreview;
  aggregateChecks?: AggregateCheck[];
  reportTypes?: ReportTypeChoice[];
  exceptions?: string[];
  validatorEvidence?: ValidatorEvidence[];
  actions?: string[];
}

export interface ReportSection {
  type: "chart" | "table" | "analysis" | "recommendations";
  title: string;
  body?: string;
  items?: string[];
}

export interface FinalReportPayload {
  kind: "report";
  title: string;
  subtitle?: string;
  options?: {
    charts?: boolean;
    tables?: boolean;
    analysis?: boolean;
    recommendations?: boolean;
  };
  sections?: ReportSection[];
  dataPreview?: DataPreview;
}

export type ReportPayload = CheckpointPayload | FinalReportPayload;

interface AppProps {
  payload: ReportPayload;
}

export default function App({ payload }: AppProps) {
  if (payload.kind === "report") {
    return <ReportPage payload={payload} />;
  }

  return <CheckpointPage payload={payload} />;
}

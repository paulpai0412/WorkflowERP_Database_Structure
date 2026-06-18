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
}

export interface ReportTypeChoice {
  id: string;
  label: string;
  description: string;
}

export interface CheckpointPayload {
  kind: "checkpoint";
  title: string;
  step?: string;
  sqlReview?: SqlReview;
  dataPreview?: DataPreview;
  reportTypes?: ReportTypeChoice[];
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

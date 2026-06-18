import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import App from "../src/App";
import ChartBlock from "../src/components/ChartBlock";
import DataPreviewTable from "../src/components/DataPreviewTable";
import RawBlockNotice from "../src/components/RawBlockNotice";

const checkpointPayload = {
  kind: "checkpoint",
  checkpointId: "run-001-sql-review",
  title: "費用分析查詢確認",
  step: "sql_review",
  requirementSummary: "查詢 2026 第一季已確認且未作廢的費用資料，依部門與會計科目彙總。",
  fieldFormulaReview: {
    fields: [
      { label: "部門", source: "ACPTA.TA004", confirmation: "依請購單表頭部門代號輸出。" },
      { label: "未稅金額", source: "ACPTB.TB013", confirmation: "明細未稅金額加總。" },
    ],
    formulas: [
      { label: "總額", expression: "未稅金額 + 稅額", confirmation: "用於主管檢視金額合計。" },
    ],
  },
  sqlReview: {
    title: "SQL 查詢審核",
    sql: "SELECT TOP 20 TA001, TA002 FROM [DSCSYS].[dbo].[ACPTA] WHERE TA024 = 'Y'",
    validation: {
      readonly: true,
      blockedKeywords: [],
      executionStatus: "not_executed",
    },
    schemaMapping: [
      { field: "部門", table: "ACPTA", column: "TA004", note: "表頭部門" },
      { field: "未稅金額", table: "ACPTB", column: "TB013", note: "明細未稅金額" },
    ],
    relationshipPath: ["ACPTA.TA001 = ACPTB.TB001", "ACPTA.TA002 = ACPTB.TB002"],
    safetyChecks: ["只允許 SELECT", "未偵測 UPDATE/DELETE/INSERT"],
    executionEnvironment: "DB_ENV=test，尚未連線正式資料庫",
  },
  dataPreview: {
    rowCount: 2,
    columns: ["部門", "會計科目", "未稅金額"],
    rows: [
      { 部門: "D001", 會計科目: "6201", 未稅金額: 12000 },
      { 部門: "D002", 會計科目: "6251", 未稅金額: 18000 },
    ],
  },
  aggregateChecks: [
    { label: "未稅金額合計", expected: 30000, actual: 30000, status: "pass" },
  ],
  reportTypes: [
    { id: "financial-control", label: "財務控管", description: "適合費用異常追蹤" },
    { id: "executive-summary", label: "主管摘要", description: "適合高階快速瀏覽" },
  ],
  exceptions: ["排除未確認與作廢單據。"],
  validatorEvidence: [
    { validator: "sql_safety", status: "pass", message: "SQL 為唯讀 SELECT。" },
  ],
  actions: ["同意查詢", "調整需求"],
};

const reportPayload = {
  kind: "report",
  title: "2026 第一季費用分析報告",
  subtitle: "依部門與會計科目彙總",
  options: {
    charts: true,
    tables: true,
    analysis: true,
    recommendations: true,
  },
  sections: [
    {
      type: "analysis",
      title: "重點分析",
      body: "D002 部門費用占比最高，需追蹤差旅與維修科目。",
    },
    {
      type: "recommendations",
      title: "建議事項",
      items: ["確認高額費用憑證", "建立月度預算差異追蹤"],
    },
  ],
  dataPreview: checkpointPayload.dataPreview,
  validatorEvidence: checkpointPayload.validatorEvidence,
};

const expensePreview = {
  rowCount: 5,
  columns: ["部門", "日期", "會計科目", "金額", "達成率"],
  rows: [
    { 部門: "行政部", 日期: "2026-01-05", 會計科目: "差旅費", 金額: 12000, 達成率: 0.32 },
    { 部門: "研發部", 日期: "2026-01-08", 會計科目: "設備費", 金額: 18000, 達成率: 0.48 },
    { 部門: "行政部", 日期: "2026-02-03", 會計科目: "維修費", 金額: 26000, 達成率: 0.7 },
    { 部門: "業務部", 日期: "2026-02-10", 會計科目: "交際費", 金額: 9000, 達成率: 0.24 },
    { 部門: "研發部", 日期: "2026-03-15", 會計科目: "雲端費", 金額: 33000, 達成率: 0.88 },
  ],
};

const chartData = [
  { label: "行政部", value: 38000, values: { 差旅費: 12000, 維修費: 26000 }, lineValue: 0.7 },
  { label: "研發部", value: 51000, values: { 設備費: 18000, 雲端費: 33000 }, lineValue: 0.88 },
  { label: "業務部", value: 9000, values: { 交際費: 9000, 雲端費: 0 }, lineValue: 0.24 },
];

describe("WFERP report renderer", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders checkpoint page title in Chinese", () => {
    render(React.createElement(App, { payload: checkpointPayload }));

    expect(screen.getByRole("heading", { name: "費用分析查詢確認" })).toBeTruthy();
  });

  it("renders management view by default and hides SQL until technical tab is selected", () => {
    render(React.createElement(App, { payload: checkpointPayload }));

    expect(screen.getByRole("heading", { name: "費用分析查詢確認" })).toBeTruthy();
    expect(screen.getByRole("tab", { name: "主管檢視" }).getAttribute("aria-selected")).toBe("true");
    expect(screen.queryByText(/SELECT TOP 20/)).toBeNull();

    fireEvent.click(screen.getByRole("tab", { name: "技術明細" }));

    expect(screen.getByText(/SELECT TOP 20/)).toBeTruthy();
  });

  it("renders SQL review payload without executing SQL in the technical view", () => {
    render(React.createElement(App, { payload: checkpointPayload }));

    fireEvent.click(screen.getByRole("tab", { name: "技術明細" }));

    expect(screen.getAllByText("尚未執行 SQL").length).toBeGreaterThan(0);
    expect(screen.queryByText(/執行查詢中|已連線資料庫/)).toBeNull();
  });

  it("posts checkpoint confirmation to the harness endpoint", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ status: "confirmed" }), { status: 200 }),
    );

    render(
      React.createElement(App, {
        payload: {
          ...checkpointPayload,
          confirmUrl: "/api/runs/run-001/checkpoints/sql_review/confirm",
        },
      }),
    );

    fireEvent.click(screen.getByRole("button", { name: "同意查詢" }));

    expect(await screen.findByText("已送出確認")).toBeTruthy();
    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/runs/run-001/checkpoints/sql_review/confirm",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "同意查詢",
          checkpointId: "run-001-sql-review",
          comment: "",
          selectedOptions: { reportType: "financial-control" },
        }),
      }),
    );

  });

  it("does not show persisted confirmation when confirmUrl is missing", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");

    render(React.createElement(App, { payload: checkpointPayload }));

    fireEvent.click(screen.getByRole("button", { name: "同意查詢" }));

    expect(await screen.findByText("此頁僅供預覽，未連接確認端點")).toBeTruthy();
    expect(screen.queryByText("已送出確認")).toBeNull();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("shows failed state when checkpoint confirmation is rejected", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("network unavailable"));

    render(
      React.createElement(App, {
        payload: {
          ...checkpointPayload,
          confirmUrl: "/api/runs/run-001/checkpoints/sql_review/confirm",
        },
      }),
    );

    fireEvent.click(screen.getByRole("button", { name: "同意查詢" }));

    expect(await screen.findByText("送出失敗，請重試")).toBeTruthy();
  });

  it("does not post twice while checkpoint confirmation is pending", () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockReturnValue(new Promise<Response>(() => undefined));

    render(
      React.createElement(App, {
        payload: {
          ...checkpointPayload,
          confirmUrl: "/api/runs/run-001/checkpoints/sql_review/confirm",
        },
      }),
    );

    const approveButton = screen.getByRole("button", { name: "同意查詢" });
    fireEvent.click(approveButton);
    fireEvent.click(approveButton);

    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it("renders data preview table with row count", () => {
    render(React.createElement(App, { payload: checkpointPayload }));

    expect(screen.getByText("資料預覽：2 筆")).toBeTruthy();
    const table = screen.getByRole("table", { name: "資料預覽" });
    expect(within(table).getByText("D001")).toBeTruthy();
    expect(within(table).getByText("18000")).toBeTruthy();
  });

  it("renders report type choices", () => {
    render(React.createElement(App, { payload: checkpointPayload }));

    expect(screen.getByRole("radio", { name: /財務控管/ })).toBeTruthy();
    expect(screen.getByRole("radio", { name: /主管摘要/ })).toBeTruthy();
  });

  it("renders final report sections", () => {
    render(React.createElement(App, { payload: reportPayload }));

    expect(screen.getByRole("heading", { name: "2026 第一季費用分析報告" })).toBeTruthy();
    expect(screen.getByText("圖表")).toBeTruthy();
    expect(screen.getByText("表格")).toBeTruthy();
    expect(screen.getByText("分析")).toBeTruthy();
    expect(screen.getByText("建議")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "重點分析" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "建議事項" })).toBeTruthy();
  });

  it("filters report charts and tables through offline cross-filter controls", () => {
    render(React.createElement(App, { payload: reportPayload }));

    const table = screen.getByRole("table", { name: "資料預覽" });
    expect(within(table).getByText("D001")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /篩選 D002/ }));

    expect(within(table).queryByText("D001")).toBeNull();
    expect(within(table).getByText("D002")).toBeTruthy();
    expect(screen.getByText(/已套用篩選/)).toBeTruthy();
  });

  it("opens evidence drawer without network calls", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    render(React.createElement(App, { payload: reportPayload }));

    fireEvent.click(screen.getByRole("button", { name: "Evidence" }));

    expect(screen.getByText(/validator/i)).toBeTruthy();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("does not render legacy iframe or static HTML links", () => {
    const { container } = render(React.createElement(App, { payload: checkpointPayload }));

    expect(container.querySelector("iframe")).toBeNull();
    expect(container.querySelector('a[href*="HTML/"]')).toBeNull();
    expect(container.querySelector('a[href="index.html"]')).toBeNull();
  });

  it("renders supported chart types with labels, legend, and accessible mark tooltips", () => {
    const chartTypes = ["bar", "stacked-bar", "line", "area", "pie", "donut", "combo"] as const;

    chartTypes.forEach((type) => {
      const { unmount } = render(
        React.createElement(ChartBlock, {
          type,
          title: `${type} 費用趨勢`,
          subtitle: "依部門彙總",
          data: chartData,
          series: [
            { key: "差旅費", label: "差旅費" },
            { key: "維修費", label: "維修費" },
            { key: "設備費", label: "設備費" },
            { key: "雲端費", label: "雲端費" },
          ],
        }),
      );

      expect(screen.getByRole("heading", { name: `${type} 費用趨勢` })).toBeTruthy();
      expect(screen.getByText("依部門彙總")).toBeTruthy();
      expect(screen.getByText("差旅費")).toBeTruthy();
      expect(screen.getAllByLabelText(new RegExp(`${type}.*行政部`)).length).toBeGreaterThan(0);
      unmount();
    });
  });

  it("renders chart empty, error, and suitability warning states", () => {
    const { rerender } = render(
      React.createElement(ChartBlock, {
        type: "bar",
        title: "空白圖表",
        data: [],
      }),
    );

    expect(screen.getByText("尚無圖表資料")).toBeTruthy();

    rerender(
      React.createElement(ChartBlock, {
        type: "line",
        title: "錯誤圖表",
        data: chartData,
        error: "缺少日期欄位",
      }),
    );
    expect(screen.getByText("圖表無法呈現：缺少日期欄位")).toBeTruthy();

    rerender(
      React.createElement(ChartBlock, {
        type: "pie",
        title: "分類過多",
        data: chartData,
        maxCategories: 2,
      }),
    );
    expect(screen.getByText(/分類數量 3 已超過建議上限 2/)).toBeTruthy();
  });

  it("supports data table sorting, search, filters, visibility, formatting, grouping, summary, conditional flags, CSV export, and pagination", () => {
    const createObjectUrl = vi.fn(() => "blob:expense-csv");
    const revokeObjectUrl = vi.fn();
    vi.stubGlobal("URL", { createObjectURL: createObjectUrl, revokeObjectURL: revokeObjectUrl });

    const { container } = render(
      React.createElement(DataPreviewTable, {
        preview: expensePreview,
        enableControls: true,
        keyColumn: "部門",
        pageSize: 2,
        groupBy: "部門",
        columnTypes: {
          日期: "date",
          金額: "currency",
          達成率: "percent",
          部門: "category",
        },
        summary: { 金額: "sum", 達成率: "avg" },
        conditionalFormats: [{ column: "金額", operator: "gte", value: 25000, label: "高額費用" }],
      }),
    );

    expect(screen.getAllByText("NT$12,000").length).toBeGreaterThan(0);
    expect(screen.getAllByText("32%").length).toBeGreaterThan(0);
    expect(container.querySelector(".frozen-column")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "金額排序" }));
    expect(screen.getAllByTestId("data-row")[0].textContent).toContain("NT$33,000");

    fireEvent.change(screen.getByLabelText("搜尋全部欄位"), { target: { value: "行政部" } });
    expect(screen.getByText("維修費")).toBeTruthy();
    expect(screen.queryByText("雲端費")).toBeNull();

    fireEvent.change(screen.getByLabelText("金額 最小值"), { target: { value: "20000" } });
    expect(screen.getAllByText("NT$26,000").length).toBeGreaterThan(0);
    expect(screen.queryByText("NT$12,000")).toBeNull();

    fireEvent.change(screen.getByLabelText("日期 起日"), { target: { value: "2026-02-01" } });
    expect(screen.getByText("2026/02/03")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("搜尋全部欄位"), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText("金額 最小值"), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText("日期 起日"), { target: { value: "" } });
    fireEvent.click(screen.getByLabelText("部門: 行政部"));
    fireEvent.click(screen.getByLabelText("部門: 研發部"));
    expect(screen.queryByText("維修費")).toBeNull();

    fireEvent.click(screen.getByLabelText("部門: 研發部"));
    expect(screen.getByText("雲端費")).toBeTruthy();
    expect(screen.getByText("研發部 小計")).toBeTruthy();
    expect(screen.getByText("總計")).toBeTruthy();
    expect(container.querySelector('[data-condition="高額費用"]')).toBeTruthy();

    fireEvent.click(screen.getByLabelText("顯示 會計科目"));
    expect(screen.queryByText("雲端費")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "下載 CSV" }));
    expect(createObjectUrl).toHaveBeenCalledTimes(1);
    expect(container.querySelector('a[download="資料預覽.csv"]')).toBeTruthy();

    fireEvent.click(screen.getByLabelText("部門: 行政部"));
    expect(screen.getByText(/第 1 \/ 3 頁/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "下一頁" }));
    expect(screen.getByText(/第 2 \/ 3 頁/)).toBeTruthy();
  });

  it("shows zero data rows when every category option is unchecked", () => {
    render(
      React.createElement(DataPreviewTable, {
        preview: expensePreview,
        enableControls: true,
        columnTypes: { 部門: "category" },
      }),
    );

    fireEvent.click(screen.getByLabelText("部門: 行政部"));
    fireEvent.click(screen.getByLabelText("部門: 研發部"));
    fireEvent.click(screen.getByLabelText("部門: 業務部"));

    expect(screen.queryAllByTestId("data-row")).toHaveLength(0);
    expect(screen.queryByText("差旅費")).toBeNull();
    expect(screen.queryByText("雲端費")).toBeNull();
  });

  it("escapes spreadsheet formulas in exported CSV blob contents", async () => {
    let exportedBlob: Blob | undefined;
    vi.stubGlobal("URL", {
      createObjectURL: vi.fn((blob: Blob) => {
        exportedBlob = blob;
        return "blob:safe-csv";
      }),
      revokeObjectURL: vi.fn(),
    });

    render(
      React.createElement(DataPreviewTable, {
        preview: {
          rowCount: 4,
          columns: ["欄位", "內容"],
          rows: [
            { 欄位: "equals", 內容: "=SUM(A1:A2)" },
            { 欄位: "plus", 內容: "+cmd" },
            { 欄位: "minus", 內容: "-10" },
            { 欄位: "at", 內容: "@HYPERLINK" },
          ],
        },
        enableControls: true,
      }),
    );

    fireEvent.click(screen.getByRole("button", { name: "下載 CSV" }));

    expect(exportedBlob).toBeTruthy();
    const csv = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = () => reject(reader.error);
      reader.readAsText(exportedBlob as Blob);
    });
    expect(csv).toContain("\"'=SUM(A1:A2)\"");
    expect(csv).toContain("\"'+cmd\"");
    expect(csv).toContain("\"'-10\"");
    expect(csv).toContain("\"'@HYPERLINK\"");
  });

  it("renders RawBlock policy metadata without executing arbitrary code", () => {
    const sideEffect = vi.fn();
    const { container } = render(
      React.createElement(RawBlockNotice, {
        id: "custom-aging-note",
        title: "帳齡補充說明",
        purpose: "呈現固定元件無法覆蓋的管理註記",
        dataDependencies: ["ACPTA.TA004", "ACPTB.TB013"],
        riskLevel: "medium",
        unsafeCode: "window.__rawBlockExecuted = true",
        onUnsafeExecute: sideEffect,
      }),
    );

    expect(screen.getByText("custom-aging-note")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "帳齡補充說明" })).toBeTruthy();
    expect(screen.getByText("呈現固定元件無法覆蓋的管理註記")).toBeTruthy();
    expect(screen.getByText("ACPTA.TA004")).toBeTruthy();
    expect(screen.getByText("風險等級：medium")).toBeTruthy();
    expect(container.querySelector("script")).toBeNull();
    expect(sideEffect).not.toHaveBeenCalled();
  });
});

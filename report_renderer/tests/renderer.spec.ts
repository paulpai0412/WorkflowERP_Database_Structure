import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import App from "../src/App";

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
};

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

  it("does not render legacy iframe or static HTML links", () => {
    const { container } = render(React.createElement(App, { payload: checkpointPayload }));

    expect(container.querySelector("iframe")).toBeNull();
    expect(container.querySelector('a[href*="HTML/"]')).toBeNull();
    expect(container.querySelector('a[href="index.html"]')).toBeNull();
  });
});

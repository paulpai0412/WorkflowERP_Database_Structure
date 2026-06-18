import React from "react";
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import App from "../src/App";

const checkpointPayload = {
  kind: "checkpoint",
  title: "費用分析查詢確認",
  step: "sql_review",
  sqlReview: {
    title: "SQL 查詢審核",
    sql: "SELECT TOP 20 TA001, TA002 FROM [DSCSYS].[dbo].[ACPTA] WHERE TA024 = 'Y'",
    validation: {
      readonly: true,
      blockedKeywords: [],
      executionStatus: "not_executed",
    },
  },
  dataPreview: {
    rowCount: 2,
    columns: ["部門", "會計科目", "未稅金額"],
    rows: [
      { 部門: "D001", 會計科目: "6201", 未稅金額: 12000 },
      { 部門: "D002", 會計科目: "6251", 未稅金額: 18000 },
    ],
  },
  reportTypes: [
    { id: "financial-control", label: "財務控管", description: "適合費用異常追蹤" },
    { id: "executive-summary", label: "主管摘要", description: "適合高階快速瀏覽" },
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
  });

  it("renders checkpoint page title in Chinese", () => {
    render(React.createElement(App, { payload: checkpointPayload }));

    expect(screen.getByRole("heading", { name: "費用分析查詢確認" })).toBeTruthy();
  });

  it("renders SQL review payload without executing SQL", () => {
    render(React.createElement(App, { payload: checkpointPayload }));

    expect(screen.getByText(/SELECT TOP 20/)).toBeTruthy();
    expect(screen.getByText("尚未執行 SQL")).toBeTruthy();
    expect(screen.queryByText(/執行查詢中|已連線資料庫/)).toBeNull();
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

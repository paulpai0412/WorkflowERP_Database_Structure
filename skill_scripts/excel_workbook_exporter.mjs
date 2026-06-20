import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

const [, , payloadPath, outputPath, evidencePath, resultPath] = process.argv;
const artifactToolModule = process.env.WFERP_ARTIFACT_TOOL_MODULE;
if (!artifactToolModule) {
  throw new Error("WFERP_ARTIFACT_TOOL_MODULE is required");
}
const { SpreadsheetFile, Workbook } = await import(pathToFileURL(artifactToolModule).href);

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function asObject(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function normalizeCell(value) {
  if (value === undefined) return null;
  if (value === null) return null;
  if (typeof value === "number" || typeof value === "boolean" || typeof value === "string") return value;
  return JSON.stringify(value);
}

function inferColumns(rows) {
  const columns = [];
  for (const row of rows) {
    for (const key of Object.keys(asObject(row))) {
      if (!columns.includes(key)) columns.push(key);
    }
  }
  return columns.length ? columns : ["value"];
}

function sanitizeSheetName(rawName, usedNames) {
  const cleaned = String(rawName || "Report")
    .replace(/[\[\]:*?/\\]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 31) || "Report";
  let name = cleaned;
  let suffix = 2;
  while (usedNames.has(name.toLowerCase())) {
    const marker = ` ${suffix}`;
    name = `${cleaned.slice(0, 31 - marker.length)}${marker}`;
    suffix += 1;
  }
  usedNames.add(name.toLowerCase());
  return name;
}

function normalizeSheets(payload) {
  const sheets = asArray(payload.sheets);
  if (sheets.length) return sheets;
  const rows = asArray(payload.rows || payload.sample_rows || payload.embedded_rows);
  if (rows.length) {
    return [{ name: payload.name || "Report", columns: payload.columns || inferColumns(rows), rows }];
  }
  return [
    {
      name: "Report",
      columns: ["message"],
      rows: [{ message: "No tabular payload was provided." }],
    },
  ];
}

async function buildWorkbook(payload) {
  const workbook = Workbook.create();
  const usedNames = new Set();
  const evidence = {
    status: "exported",
    workbook_path: outputPath,
    sheets: [],
    verification: {
      artifact_tool: "@oai/artifact-tool",
      render_preview_path: "",
      render_preview_status: "not_run",
      formula_error_count: 0,
    },
  };

  for (const sheetPayload of normalizeSheets(payload)) {
    const sourceRows = asArray(sheetPayload.rows || sheetPayload.sample_rows || sheetPayload.embedded_rows);
    const columns = asArray(sheetPayload.columns).length ? asArray(sheetPayload.columns).map(String) : inferColumns(sourceRows);
    const name = sanitizeSheetName(sheetPayload.name || sheetPayload.sheet_name || "Report", usedNames);
    const sheet = workbook.worksheets.add(name);
    sheet.showGridLines = false;

    const title = String(sheetPayload.title || name);
    sheet.getRange("A1").values = [[title]];
    sheet.getRange("A1").format = {
      font: { bold: true, color: "#111827" },
      fill: "#F8FAFC",
    };

    const matrix = [
      columns,
      ...sourceRows.map((row) => {
        const objectRow = asObject(row);
        return columns.map((column) => normalizeCell(objectRow[column]));
      }),
    ];
    const width = Math.max(columns.length, 1);
    const height = Math.max(matrix.length, 1);
    const tableRange = sheet.getRangeByIndexes(2, 0, height, width);
    tableRange.values = matrix;

    sheet.getRangeByIndexes(2, 0, 1, width).format = {
      fill: "#0F766E",
      font: { bold: true, color: "#FFFFFF" },
    };
    try {
      sheet.freezePanes.freezeRows(3);
      tableRange.format.autofitColumns();
      tableRange.format.autofitRows();
    } catch (error) {
      evidence.verification.autofit_warning = String(error?.message || error);
    }

    evidence.sheets.push({
      name,
      column_count: columns.length,
      row_count: sourceRows.length,
      formula_strategy: String(sheetPayload.formula_strategy || sheetPayload.formulaStrategy || "value-only"),
    });
  }

  if (evidence.sheets.length) {
    try {
      const previewPath = path.join(path.dirname(evidencePath), "excel-preview.png");
      const preview = await workbook.render({
        sheetName: evidence.sheets[0].name,
        autoCrop: "all",
        scale: 1,
        format: "png",
      });
      await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
      evidence.verification.render_preview_path = previewPath;
      evidence.verification.render_preview_status = "rendered";
    } catch (error) {
      evidence.verification.render_preview_status = "warning";
      evidence.verification.render_preview_warning = String(error?.message || error);
    }
  }

  await fs.mkdir(path.dirname(outputPath), { recursive: true });
  const xlsx = await SpreadsheetFile.exportXlsx(workbook);
  await xlsx.save(outputPath);
  return evidence;
}

const payload = JSON.parse(await fs.readFile(payloadPath, "utf8"));
const result = await buildWorkbook(payload);
await fs.writeFile(evidencePath, `${JSON.stringify(result, null, 2)}\n`, "utf8");
await fs.writeFile(resultPath, `${JSON.stringify(result, null, 2)}\n`, "utf8");

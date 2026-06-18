import React from "react";
import { DataPreview, TableRow } from "../App";

type ColumnType = "text" | "number" | "date" | "percent" | "currency" | "category";
type SummaryMode = "sum" | "avg" | "count";
type Operator = "gt" | "gte" | "lt" | "lte" | "eq";

interface ConditionalFormat {
  column: string;
  operator: Operator;
  value: number | string;
  label: string;
}

interface DataPreviewTableProps {
  preview?: DataPreview;
  title?: string;
  enableControls?: boolean;
  keyColumn?: string;
  pageSize?: number;
  groupBy?: string;
  columnTypes?: Record<string, ColumnType>;
  summary?: Record<string, SummaryMode>;
  conditionalFormats?: ConditionalFormat[];
}

interface SortState {
  column: string;
  direction: "asc" | "desc";
}

type StateSetter<T> = (value: T | ((current: T) => T)) => void;
type InputChangeEvent = { target: { value: string } };

function asNumber(value: TableRow[string]) {
  if (typeof value === "number") {
    return value;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function asDateValue(value: TableRow[string]) {
  if (!value) {
    return 0;
  }
  const parsed = new Date(String(value)).getTime();
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatCell(value: TableRow[string], type: ColumnType = "text") {
  if (value === null) {
    return "";
  }
  if (typeof value === "boolean") {
    return value ? "是" : "否";
  }
  if (type === "currency") {
    return `NT$${asNumber(value).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
  }
  if (type === "percent") {
    const number = asNumber(value);
    const normalized = Math.abs(number) <= 1 ? number * 100 : number;
    return `${new Intl.NumberFormat("zh-TW", { maximumFractionDigits: 1 }).format(normalized)}%`;
  }
  if (type === "number") {
    return asNumber(value).toLocaleString("en-US", { maximumFractionDigits: 2 });
  }
  if (type === "date") {
    const date = new Date(String(value));
    if (Number.isNaN(date.getTime())) {
      return String(value);
    }
    const month = `${date.getMonth() + 1}`.padStart(2, "0");
    const day = `${date.getDate()}`.padStart(2, "0");
    return `${date.getFullYear()}/${month}/${day}`;
  }
  return String(value);
}

function compareValues(left: TableRow[string], right: TableRow[string], type: ColumnType) {
  if (type === "currency" || type === "number" || type === "percent") {
    return asNumber(left) - asNumber(right);
  }
  if (type === "date") {
    return asDateValue(left) - asDateValue(right);
  }
  return String(left ?? "").localeCompare(String(right ?? ""), "zh-TW");
}

function csvEscape(value: string) {
  return `"${value.replace(/"/g, '""')}"`;
}

function csvSafeValue(value: string) {
  return /^[=+\-@]/.test(value) ? `'${value}` : value;
}

function matchesCondition(row: TableRow, condition: ConditionalFormat) {
  const current = row[condition.column];
  if (typeof condition.value === "number") {
    const value = asNumber(current);
    if (condition.operator === "gt") return value > condition.value;
    if (condition.operator === "gte") return value >= condition.value;
    if (condition.operator === "lt") return value < condition.value;
    if (condition.operator === "lte") return value <= condition.value;
    return value === condition.value;
  }
  return String(current ?? "") === condition.value;
}

function summarize(rows: TableRow[], column: string, mode: SummaryMode) {
  if (mode === "count") {
    return rows.length;
  }
  const values = rows.map((row) => asNumber(row[column]));
  const sum = values.reduce((total, value) => total + value, 0);
  return mode === "avg" && values.length > 0 ? sum / values.length : sum;
}

export default function DataPreviewTable({
  preview,
  title = "資料預覽",
  enableControls = false,
  keyColumn,
  pageSize = 25,
  groupBy,
  columnTypes = {},
  summary = {},
  conditionalFormats = [],
}: DataPreviewTableProps) {
  const useReactState = (React as unknown as {
    useState: <T>(initial: T) => [T, StateSetter<T>];
  }).useState;
  const useReactMemo = (React as unknown as {
    useMemo: <T>(factory: () => T, deps: unknown[]) => T;
  }).useMemo;
  const [search, setSearch] = useReactState("");
  const [sort, setSort] = useReactState<SortState | null>(null);
  const [hiddenColumns, setHiddenColumns] = useReactState<Set<string>>(new Set());
  const [numberFilters, setNumberFilters] = useReactState<Record<string, { min?: string; max?: string }>>({});
  const [dateFilters, setDateFilters] = useReactState<Record<string, { min?: string; max?: string }>>({});
  const [categorySelections, setCategorySelections] = useReactState<Record<string, Set<string>>>({});
  const [page, setPage] = useReactState(1);
  const [csvUrl, setCsvUrl] = useReactState("");

  const visibleColumns = useReactMemo(
    () => preview?.columns.filter((column) => !hiddenColumns.has(column)) ?? [],
    [hiddenColumns, preview?.columns],
  );

  const categoryValues = useReactMemo(() => {
    const values: Record<string, string[]> = {};
    preview?.columns.forEach((column) => {
      if (columnTypes[column] === "category") {
        values[column] = Array.from(new Set(preview.rows.map((row) => String(row[column] ?? "")))).sort();
      }
    });
    return values;
  }, [columnTypes, preview]);

  const filteredRows = useReactMemo(() => {
    if (!preview) {
      return [];
    }
    const query = search.trim().toLowerCase();
    const rows = preview.rows.filter((row) => {
      if (query && !preview.columns.some((column) => String(row[column] ?? "").toLowerCase().includes(query))) {
        return false;
      }

      for (const [column, filter] of Object.entries(numberFilters)) {
        const value = asNumber(row[column]);
        if (filter.min !== undefined && filter.min !== "" && value < Number(filter.min)) return false;
        if (filter.max !== undefined && filter.max !== "" && value > Number(filter.max)) return false;
      }

      for (const [column, filter] of Object.entries(dateFilters)) {
        const value = asDateValue(row[column]);
        if (filter.min && value < asDateValue(filter.min)) return false;
        if (filter.max && value > asDateValue(filter.max)) return false;
      }

      for (const [column, selected] of Object.entries(categorySelections)) {
        if (!selected.has(String(row[column] ?? ""))) {
          return false;
        }
      }

      return true;
    });

    if (!sort) {
      return rows;
    }
    return [...rows].sort((left, right) => {
      const comparison = compareValues(left[sort.column], right[sort.column], columnTypes[sort.column] ?? "text");
      return sort.direction === "asc" ? comparison : -comparison;
    });
  }, [categorySelections, columnTypes, dateFilters, numberFilters, preview, search, sort]);

  const totalPages = Math.max(1, Math.ceil(filteredRows.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const pagedRows = enableControls
    ? filteredRows.slice((currentPage - 1) * pageSize, currentPage * pageSize)
    : filteredRows;

  if (!preview) {
    return (
      <section className="panel">
        <h2>{title}</h2>
        <p className="muted">尚無預覽資料。</p>
      </section>
    );
  }

  function toggleSort(column: string) {
    setPage(1);
    setSort((current) => {
      if (current?.column === column) {
        return { column, direction: current.direction === "asc" ? "desc" : "asc" };
      }
      return { column, direction: "desc" };
    });
  }

  function toggleColumn(column: string) {
    setHiddenColumns((current) => {
      const next = new Set(current);
      if (next.has(column)) {
        next.delete(column);
      } else {
        next.add(column);
      }
      return next;
    });
  }

  function toggleCategory(column: string, value: string) {
    setPage(1);
    setCategorySelections((current) => {
      const allValues = categoryValues[column] ?? [];
      const selected = new Set(current[column] ?? allValues);
      if (selected.has(value)) {
        selected.delete(value);
      } else {
        selected.add(value);
      }
      return { ...current, [column]: selected };
    });
  }

  function exportCsv() {
    const csv = [
      visibleColumns.map(csvEscape).join(","),
      ...filteredRows.map((row) =>
        visibleColumns
          .map((column) => csvEscape(csvSafeValue(formatCell(row[column], columnTypes[column] ?? "text"))))
          .join(","),
      ),
    ].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    if (csvUrl) {
      URL.revokeObjectURL(csvUrl);
    }
    setCsvUrl(URL.createObjectURL(blob));
  }

  function renderFilter(column: string) {
    const type = columnTypes[column];
    if (!enableControls) return null;
    if (type === "currency" || type === "number" || type === "percent") {
      return (
        <div className="filter-pair" key={`${column}-number-filter`}>
          <label>
            {column} 最小值
            <input
              aria-label={`${column} 最小值`}
              inputMode="decimal"
              value={numberFilters[column]?.min ?? ""}
              onChange={(event: InputChangeEvent) => {
                setPage(1);
                setNumberFilters((current) => ({
                  ...current,
                  [column]: { ...current[column], min: event.target.value },
                }));
              }}
            />
          </label>
          <label>
            {column} 最大值
            <input
              aria-label={`${column} 最大值`}
              inputMode="decimal"
              value={numberFilters[column]?.max ?? ""}
              onChange={(event: InputChangeEvent) => {
                setPage(1);
                setNumberFilters((current) => ({
                  ...current,
                  [column]: { ...current[column], max: event.target.value },
                }));
              }}
            />
          </label>
        </div>
      );
    }
    if (type === "date") {
      return (
        <div className="filter-pair" key={`${column}-date-filter`}>
          <label>
            {column} 起日
            <input
              aria-label={`${column} 起日`}
              type="date"
              value={dateFilters[column]?.min ?? ""}
              onChange={(event: InputChangeEvent) => {
                setPage(1);
                setDateFilters((current) => ({
                  ...current,
                  [column]: { ...current[column], min: event.target.value },
                }));
              }}
            />
          </label>
          <label>
            {column} 迄日
            <input
              aria-label={`${column} 迄日`}
              type="date"
              value={dateFilters[column]?.max ?? ""}
              onChange={(event: InputChangeEvent) => {
                setPage(1);
                setDateFilters((current) => ({
                  ...current,
                  [column]: { ...current[column], max: event.target.value },
                }));
              }}
            />
          </label>
        </div>
      );
    }
    if (type === "category") {
      return (
        <fieldset className="category-filter" key={`${column}-category-filter`}>
          <legend>{column}</legend>
          {(categoryValues[column] ?? []).map((value) => {
            const selected = categorySelections[column] ?? new Set(categoryValues[column]);
            return (
              <label key={`${column}-${value}`}>
                <input
                  type="checkbox"
                  aria-label={`${column}: ${value}`}
                  checked={selected.has(value)}
                  onChange={() => toggleCategory(column, value)}
                />
                {value}
              </label>
            );
          })}
        </fieldset>
      );
    }
    return null;
  }

  function renderSummaryRow(rows: TableRow[], label: string, className: string, rowKey: string) {
    if (Object.keys(summary).length === 0) {
      return null;
    }
    return (
      <tr className={className} key={rowKey}>
        {visibleColumns.map((column, index) => (
          <td key={`${className}-${column}`} className={column === keyColumn ? "frozen-column" : undefined}>
            {index === 0
              ? label
              : summary[column]
                ? formatCell(summarize(rows, column, summary[column]), columnTypes[column] ?? "number")
                : ""}
          </td>
        ))}
      </tr>
    );
  }

  return (
    <section className="panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Data Preview</p>
          <h2>
            {title}：{preview.rowCount} 筆
          </h2>
        </div>
        <span className="count-pill">{preview.columns.length} 欄</span>
      </div>

      {enableControls ? (
        <div className="table-controls" aria-label="資料表控制">
          <label className="search-field">
            搜尋全部欄位
            <input
              aria-label="搜尋全部欄位"
              value={search}
              onChange={(event: InputChangeEvent) => {
                setSearch(event.target.value);
                setPage(1);
              }}
            />
          </label>
          <div className="column-toggle-grid" aria-label="欄位顯示">
            {preview.columns.map((column) => (
              <label key={column}>
                <input
                  type="checkbox"
                  aria-label={`顯示 ${column}`}
                  checked={!hiddenColumns.has(column)}
                  onChange={() => toggleColumn(column)}
                />
                {column}
              </label>
            ))}
          </div>
          <div className="filter-grid">{preview.columns.map((column) => renderFilter(column))}</div>
          <div className="button-row table-action-row">
            <button className="secondary-button" type="button" onClick={exportCsv}>
              下載 CSV
            </button>
            {csvUrl ? (
              <a className="download-link" href={csvUrl} download={`${title}.csv`}>
                CSV 已準備
              </a>
            ) : null}
          </div>
        </div>
      ) : null}

      <div className="table-scroll">
        <table aria-label="資料預覽">
          <thead>
            <tr>
              {visibleColumns.map((column) => (
                <th key={column} scope="col" className={column === keyColumn ? "frozen-column" : undefined}>
                  {enableControls ? (
                    <button className="table-sort-button" type="button" onClick={() => toggleSort(column)}>
                      {column}排序
                    </button>
                  ) : (
                    column
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pagedRows.map((row, rowIndex) => (
              <tr key={`${rowIndex}-${preview.columns.join("-")}`} data-testid="data-row">
                {visibleColumns.map((column) => {
                  const matchedCondition = conditionalFormats.find((condition) => matchesCondition(row, condition));
                  return (
                    <td
                      key={column}
                      className={column === keyColumn ? "frozen-column" : undefined}
                      data-condition={matchedCondition?.label}
                    >
                      {formatCell(row[column], columnTypes[column] ?? "text")}
                    </td>
                  );
                })}
              </tr>
            ))}
            {groupBy
              ? Array.from(new Set(pagedRows.map((row) => String(row[groupBy] ?? "")))).map((group) =>
                  renderSummaryRow(
                    pagedRows.filter((row) => String(row[groupBy] ?? "") === group),
                    `${group} 小計`,
                    "subtotal-row",
                    `${group}-subtotal`,
                  ),
                )
              : null}
            {renderSummaryRow(filteredRows, "總計", "summary-row", "summary-total")}
          </tbody>
        </table>
      </div>

      {enableControls ? (
        <div className="pagination-row">
          <button
            className="secondary-button"
            type="button"
            disabled={currentPage <= 1}
            onClick={() => setPage((current) => Math.max(1, current - 1))}
          >
            上一頁
          </button>
          <span>
            第 {currentPage} / {totalPages} 頁
          </span>
          <button
            className="secondary-button"
            type="button"
            disabled={currentPage >= totalPages}
            onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
          >
            下一頁
          </button>
        </div>
      ) : null}
    </section>
  );
}

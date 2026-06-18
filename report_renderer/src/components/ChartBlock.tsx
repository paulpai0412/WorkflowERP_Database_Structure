export type ChartType = "bar" | "stacked-bar" | "line" | "area" | "pie" | "donut" | "combo";

export interface ChartDatum {
  label: string;
  value?: number;
  values?: Record<string, number>;
  lineValue?: number;
  barValue?: number;
}

export interface ChartSeries {
  key: string;
  label: string;
  color?: string;
}

interface ChartBlockProps {
  type: ChartType;
  title: string;
  subtitle?: string;
  data?: ChartDatum[];
  series?: ChartSeries[];
  maxCategories?: number;
  error?: string;
}

const palette = ["#286b7a", "#8a6f2a", "#5a7a32", "#9a4d3b", "#4c647d", "#7a4f79"];
const chartTypeLabels: Record<ChartType, string> = {
  bar: "bar",
  "stacked-bar": "stacked-bar",
  line: "line",
  area: "area",
  pie: "pie",
  donut: "donut",
  combo: "combo",
};

function numericValue(datum: ChartDatum) {
  if (typeof datum.value === "number") {
    return datum.value;
  }
  if (typeof datum.barValue === "number") {
    return datum.barValue;
  }
  if (datum.values) {
    return Object.values(datum.values).reduce((sum, value) => sum + value, 0);
  }
  return 0;
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("zh-TW", { maximumFractionDigits: 2 }).format(value);
}

function pointPath(points: Array<[number, number]>) {
  return points.map(([x, y], index) => `${index === 0 ? "M" : "L"} ${x} ${y}`).join(" ");
}

function polygonPath(points: Array<[number, number]>, height: number) {
  if (points.length === 0) {
    return "";
  }
  const first = points[0];
  const last = points[points.length - 1];
  return `${pointPath(points)} L ${last[0]} ${height} L ${first[0]} ${height} Z`;
}

function piePath(cx: number, cy: number, radius: number, start: number, end: number) {
  const startX = cx + radius * Math.cos(start);
  const startY = cy + radius * Math.sin(start);
  const endX = cx + radius * Math.cos(end);
  const endY = cy + radius * Math.sin(end);
  const largeArc = end - start > Math.PI ? 1 : 0;
  return `M ${cx} ${cy} L ${startX} ${startY} A ${radius} ${radius} 0 ${largeArc} 1 ${endX} ${endY} Z`;
}

export default function ChartBlock({
  type,
  title,
  subtitle,
  data = [],
  series = [],
  maxCategories = 12,
  error,
}: ChartBlockProps) {
  const values = data.map(numericValue);
  const maxValue = Math.max(...values, 1);
  const width = 720;
  const height = 280;
  const plotTop = 24;
  const plotBottom = 238;
  const plotHeight = plotBottom - plotTop;
  const step = data.length > 0 ? width / data.length : width;
  const warning =
    data.length > maxCategories
      ? `分類數量 ${data.length} 已超過建議上限 ${maxCategories}，請改用表格、篩選或彙總後再呈現。`
      : null;

  if (error) {
    return (
      <section className="panel chart-block error-panel">
        <h2>{title}</h2>
        {subtitle ? <p className="subtitle">{subtitle}</p> : null}
        <p className="muted">圖表無法呈現：{error}</p>
      </section>
    );
  }

  if (data.length === 0) {
    return (
      <section className="panel chart-block">
        <h2>{title}</h2>
        {subtitle ? <p className="subtitle">{subtitle}</p> : null}
        <p className="muted">尚無圖表資料</p>
      </section>
    );
  }

  const points = data.map((datum, index) => {
    const x = step * index + step / 2;
    const y = plotBottom - (numericValue(datum) / maxValue) * plotHeight;
    return [x, y] as [number, number];
  });

  const total = values.reduce((sum, value) => sum + value, 0) || 1;
  let arcStart = -Math.PI / 2;

  return (
    <section className="panel chart-block">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Chart</p>
          <h2>{title}</h2>
          {subtitle ? <p className="subtitle">{subtitle}</p> : null}
        </div>
        <span className="count-pill">{chartTypeLabels[type]}</span>
      </div>
      {warning ? <p className="warning-text">{warning}</p> : null}
      <div className="chart-legend" aria-label="圖例">
        {(series.length > 0 ? series : [{ key: "value", label: "金額" }]).map((item, index) => (
          <span key={item.key}>
            <i style={{ background: item.color ?? palette[index % palette.length] }} />
            {item.label}
          </span>
        ))}
      </div>
      <svg className="chart-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${title} ${type}`}>
        <title>{title}</title>
        {[0, 1, 2, 3].map((line) => (
          <line
            key={line}
            x1="0"
            x2={width}
            y1={plotTop + (plotHeight / 3) * line}
            y2={plotTop + (plotHeight / 3) * line}
            className="chart-grid-line"
          />
        ))}
        {(type === "bar" || type === "combo") &&
          data.map((datum, index) => {
            const value = type === "combo" && typeof datum.barValue === "number" ? datum.barValue : numericValue(datum);
            const barHeight = (value / maxValue) * plotHeight;
            return (
              <rect
                key={`${datum.label}-bar`}
                x={step * index + step * 0.22}
                y={plotBottom - barHeight}
                width={Math.max(step * 0.56, 18)}
                height={barHeight}
                rx="3"
                className="chart-mark primary"
                aria-label={`${type} mark ${datum.label} ${formatNumber(value)}`}
              />
            );
          })}
        {type === "stacked-bar" &&
          data.flatMap((datum, index) => {
            const entries = Object.entries(datum.values ?? { value: numericValue(datum) });
            const totalForDatum = entries.reduce((sum, [, value]) => sum + value, 0) || 1;
            let yCursor = plotBottom;
            return entries.map(([key, value], stackIndex) => {
              const segmentHeight = (value / Math.max(maxValue, totalForDatum)) * plotHeight;
              yCursor -= segmentHeight;
              return (
                <rect
                  key={`${datum.label}-${key}`}
                  x={step * index + step * 0.22}
                  y={yCursor}
                  width={Math.max(step * 0.56, 18)}
                  height={segmentHeight}
                  className="chart-mark"
                  style={{ fill: palette[stackIndex % palette.length] }}
                  aria-label={`${type} mark ${datum.label} ${key} ${formatNumber(value)}`}
                />
              );
            });
          })}
        {type === "area" ? (
          <path className="chart-area" d={polygonPath(points, plotBottom)} aria-label={`${type} area ${title}`} />
        ) : null}
        {(type === "line" || type === "area" || type === "combo") && (
          <path className="chart-line" d={pointPath(points)} aria-label={`${type} line ${title}`} />
        )}
        {(type === "line" || type === "area" || type === "combo") &&
          points.map(([x, y], index) => (
            <circle
              key={`${data[index].label}-point`}
              cx={x}
              cy={y}
              r="5"
              className="chart-point"
              aria-label={`${type} mark ${data[index].label} ${formatNumber(numericValue(data[index]))}`}
            />
          ))}
        {(type === "pie" || type === "donut") &&
          data.map((datum, index) => {
            const value = numericValue(datum);
            const arcEnd = arcStart + (value / total) * Math.PI * 2;
            const path = piePath(width / 2, 132, 92, arcStart, arcEnd);
            arcStart = arcEnd;
            return (
              <path
                key={`${datum.label}-arc`}
                d={path}
                className="chart-arc"
                style={{ fill: palette[index % palette.length] }}
                aria-label={`${type} mark ${datum.label} ${formatNumber(value)}`}
              />
            );
          })}
        {type === "donut" ? <circle cx={width / 2} cy="132" r="48" className="chart-donut-hole" /> : null}
        {data.map((datum, index) => (
          <text key={`${datum.label}-label`} x={step * index + step / 2} y="266" className="chart-axis-label">
            {datum.label}
          </text>
        ))}
      </svg>
    </section>
  );
}

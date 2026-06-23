import type { Severity } from '../../types/security';

const severityColors: Record<Severity, string> = {
  low: '#22c55e',
  medium: '#f59e0b',
  high: '#fb923c',
  critical: '#fb1746',
};

export function LineChart({ data }: { data: { label: string; value: number }[] }) {
  const width = 520;
  const height = 210;
  const chartData = data.length > 0 ? data : [{ label: '--', value: 0 }];
  const max = Math.max(...chartData.map((item) => item.value), 100);
  const points = chartData.map((item, index) => {
    const x = chartData.length === 1 ? width / 2 : 24 + (index * (width - 48)) / (chartData.length - 1);
    const y = height - 28 - (item.value / max) * (height - 62);
    return { x, y, ...item };
  });
  const path = points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ');

  if (data.length === 0) return <div className="chart-empty">Chưa có dữ liệu xu hướng</div>;

  return (
    <svg className="chart-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Biểu đồ xu hướng rủi ro">
      {[0, 1, 2, 3].map((line) => <line key={line} x1="24" x2={width - 24} y1={32 + line * 42} y2={32 + line * 42} className="grid-line" />)}
      <path d={`${path} L ${width - 24} ${height - 28} L 24 ${height - 28} Z`} className="area-path" />
      <path d={path} className="line-path" />
      {points.map((point) => <circle key={point.label} cx={point.x} cy={point.y} r="4" className="line-dot" />)}
      {points.map((point, index) => index % 2 === 0 ? <text key={point.label} x={point.x} y={height - 8} textAnchor="middle" className="axis-text">{point.label}</text> : null)}
    </svg>
  );
}

export function BarChart({ data }: { data: { label: string; value: number; severity: Severity }[] }) {
  if (data.length === 0 || data.every((item) => item.value === 0)) return <div className="chart-empty">Chưa có dữ liệu cảnh báo</div>;
  const max = Math.max(...data.map((item) => item.value), 1);
  return (
    <div className="bar-chart" aria-label="Biểu đồ số lượng cảnh báo theo mức độ">
      {data.map((item) => (
        <div className="bar-column" key={item.label}>
          <div className="bar-track"><span style={{ height: `${(item.value / max) * 100}%`, background: severityColors[item.severity] }} /></div>
          <strong>{item.value}</strong>
          <p>{item.label}</p>
        </div>
      ))}
    </div>
  );
}

export function DonutChart({ data, centerLabel = 'thực thể' }: { data: { label: string; value: number; color: string }[]; centerLabel?: string }) {
  const rawTotal = data.reduce((sum, item) => sum + Math.max(0, item.value), 0);
  if (data.length === 0 || rawTotal === 0) return <div className="chart-empty">Chưa có dữ liệu phân loại rủi ro</div>;

  const normalized = normalizeToHundred(data.map((item) => item.value));
  const displayData = data.map((item, index) => ({ ...item, value: normalized[index] ?? 0 }));
  const segments = displayData.map((item, index) => {
    const previous = displayData.slice(0, index).reduce((sum, entry) => sum + entry.value, 0);
    const dash = item.value;
    return <circle key={item.label} cx="72" cy="72" r="54" fill="none" stroke={item.color} strokeWidth="16" strokeDasharray={`${dash} ${100 - dash}`} strokeDashoffset={25 - previous} pathLength="100" />;
  });

  return (
    <div className="donut-wrap">
      <svg viewBox="0 0 144 144" className="donut-chart" role="img" aria-label="Biểu đồ phân bố rủi ro">
        <circle cx="72" cy="72" r="54" fill="none" stroke="rgba(148,163,184,.16)" strokeWidth="16" />
        {segments}
        <text x="72" y="68" textAnchor="middle" className="donut-total">100%</text>
        <text x="72" y="88" textAnchor="middle" className="donut-label">{centerLabel}</text>
      </svg>
      <div className="donut-legend">
        {displayData.map((item) => <div key={item.label}><i style={{ background: item.color }} />{item.label}<span>{item.value}%</span></div>)}
      </div>
    </div>
  );
}

function normalizeToHundred(values: number[]): number[] {
  const total = values.reduce((sum, value) => sum + Math.max(0, value), 0);
  if (total <= 0) return values.map(() => 0);
  const exact = values.map((value) => (Math.max(0, value) / total) * 100);
  const floors = exact.map(Math.floor);
  let remainder = 100 - floors.reduce((sum, value) => sum + value, 0);
  const order = exact
    .map((value, index) => ({ index, fraction: value - Math.floor(value) }))
    .sort((a, b) => b.fraction - a.fraction);
  for (let i = 0; i < order.length && remainder > 0; i += 1, remainder -= 1) {
    floors[order[i].index] += 1;
  }
  return floors;
}

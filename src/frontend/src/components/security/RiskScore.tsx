export function RiskScore({ value, size = 'md' }: { value: number; size?: 'sm' | 'md' | 'lg' }) {
  const safeValue = Math.max(0, Math.min(100, Math.round(value || 0)));
  const level = safeValue >= 81 ? 'critical' : safeValue >= 61 ? 'high' : safeValue >= 31 ? 'medium' : 'low';
  return (
    <div className={`risk-score risk-${level} risk-size-${size}`}>
      <span>{safeValue}</span>
      {size !== 'sm' && <div className="risk-bar"><i style={{ width: `${safeValue}%` }} /></div>}
    </div>
  );
}

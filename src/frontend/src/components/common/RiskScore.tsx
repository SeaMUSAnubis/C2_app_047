interface RiskScoreProps {
  value: number;
}

export function RiskScore({ value }: RiskScoreProps) {
  let colorClass = 'risk-low';
  if (value >= 70) colorClass = 'risk-high';
  else if (value >= 40) colorClass = 'risk-medium';

  return <span className={`risk-score ${colorClass}`}>{value}</span>;
}

interface StatusBadgeProps {
  status: string;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const normalized = status.toLowerCase();
  let className = 'status-badge ';
  if (normalized === 'active') className += 'status-active';
  else if (normalized === 'inactive') className += 'status-inactive';
  else if (normalized === 'locked') className += 'status-locked';

  return <span className={className}>{status}</span>;
}

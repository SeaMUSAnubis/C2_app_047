import type { ReactNode } from 'react';

export function StatCard({ label, value, delta, icon, tone }: { label: string; value: string; delta: string; icon: ReactNode; tone: string }) {
  return (
    <article className={`stat-card tone-${tone}`}>
      <div className="stat-card-top">
        <div className="stat-icon">{icon}</div>
        <span className="stat-trend">{delta}</span>
      </div>
      <div>
        <p>{label}</p>
        <strong>{value}</strong>
        <span>So với kỳ trước</span>
      </div>
    </article>
  );
}

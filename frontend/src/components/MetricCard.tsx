interface MetricCardProps {
  label: string;
  value: number;
  note: string;
}

export function MetricCard({ label, value, note }: MetricCardProps) {
  return (
    <article className="metric-card">
      <p className="metric-card__label">{label}</p>
      <strong className="metric-card__value">{value.toLocaleString()}</strong>
      <p className="metric-card__note">{value === 0 ? "No records yet" : note}</p>
    </article>
  );
}

interface StatusBadgeProps {
  label: string;
  tone: "positive" | "neutral";
}

export function StatusBadge({ label, tone }: StatusBadgeProps) {
  return <span className={`status-badge status-badge--${tone}`}>{label}</span>;
}

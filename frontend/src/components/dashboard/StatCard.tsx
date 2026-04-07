interface StatCardProps {
  icon: string;
  value: string;
  label: string;
  detail?: string;
  changePercent?: number;
  colorClass?: string;
}

export function StatCard({ icon, value, label, detail, changePercent, colorClass }: StatCardProps) {
  const changeColor =
    changePercent === undefined
      ? ""
      : changePercent > 0
        ? "text-emerald-600"
        : changePercent < 0
          ? "text-red-500"
          : "text-text-muted";

  return (
    <div className="bg-surface border border-border rounded-xl p-4 shadow-sm">
      <div className="flex items-start justify-between mb-2">
        <span className="text-2xl">{icon}</span>
        {changePercent !== undefined && changePercent !== 0 && (
          <span className={`text-xs font-medium ${changeColor}`}>
            {changePercent > 0 ? "↑" : "↓"} {Math.abs(changePercent)}%
          </span>
        )}
      </div>
      <div className={`text-2xl font-bold ${colorClass || "text-foreground"}`}>{value}</div>
      <div className="text-xs text-text-muted mt-0.5">{label}</div>
      {detail && <div className="text-xs text-text-muted mt-1">{detail}</div>}
    </div>
  );
}

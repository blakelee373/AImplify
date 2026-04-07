import Link from "next/link";

interface ChainCardProps {
  id: string;
  name: string;
  description: string | null;
  workflowCount: number;
  overallStatus: string;
}

const STATUS_COLORS: Record<string, string> = {
  active: "bg-emerald-100 text-emerald-700",
  testing: "bg-amber-100 text-amber-700",
  paused: "bg-gray-100 text-gray-600",
  draft: "bg-blue-100 text-blue-700",
};

export function ChainCard({ id, name, description, workflowCount, overallStatus }: ChainCardProps) {
  return (
    <Link
      href={`/dashboard/chains/${id}`}
      className="block bg-surface border border-border rounded-xl p-5 hover:shadow-md hover:border-primary/30 transition-all group"
    >
      <div className="flex items-start gap-3">
        <span className="text-2xl mt-0.5">🔗</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-semibold text-foreground truncate">{name}</h3>
            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[overallStatus] || STATUS_COLORS.draft}`}>
              {overallStatus}
            </span>
          </div>
          {description && <p className="text-sm text-text-muted line-clamp-2">{description}</p>}
          <p className="text-xs text-text-muted mt-2">
            {workflowCount} {workflowCount === 1 ? "step" : "steps"}
          </p>
        </div>
        <span className="text-text-muted/40 group-hover:text-primary transition-colors mt-2">→</span>
      </div>
    </Link>
  );
}

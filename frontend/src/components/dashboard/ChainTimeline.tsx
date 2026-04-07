import Link from "next/link";
import { timeAgo } from "@/lib/time";

interface ChainWorkflow {
  id: string;
  name: string;
  description: string | null;
  position: number;
  delay_after_previous: number;
  status: string;
  last_run_at: string | null;
}

interface ChainTimelineProps {
  workflows: ChainWorkflow[];
}

const STATUS_DOTS: Record<string, string> = {
  active: "bg-emerald-500",
  testing: "bg-amber-400",
  paused: "bg-gray-300",
  draft: "bg-blue-400",
};

function formatDelay(minutes: number): string {
  if (minutes === 0) return "Immediately";
  if (minutes < 60) return `${minutes} minutes later`;
  if (minutes < 1440) {
    const h = Math.round(minutes / 60);
    return `${h} ${h === 1 ? "hour" : "hours"} later`;
  }
  const d = Math.round(minutes / 1440);
  return `${d} ${d === 1 ? "day" : "days"} later`;
}

export function ChainTimeline({ workflows }: ChainTimelineProps) {
  return (
    <div className="relative">
      {workflows.map((wf, i) => {
        const isLast = i === workflows.length - 1;
        const dotColor = STATUS_DOTS[wf.status] || STATUS_DOTS.draft;

        return (
          <div key={wf.id} className="relative flex gap-4">
            {/* Timeline line + dot */}
            <div className="flex flex-col items-center shrink-0 w-6">
              <div className={`w-3 h-3 rounded-full mt-1.5 z-10 ${dotColor} ring-2 ring-surface`} />
              {!isLast && <div className="w-0.5 flex-1 bg-border" />}
            </div>

            {/* Content */}
            <div className={`flex-1 ${isLast ? "pb-0" : "pb-6"}`}>
              {/* Delay label */}
              {i > 0 && wf.delay_after_previous >= 0 && (
                <div className="text-xs text-text-muted mb-1 -mt-0.5">
                  ⏱ {formatDelay(wf.delay_after_previous)}
                </div>
              )}

              <Link
                href={`/dashboard/workflows/${wf.id}`}
                className="block bg-surface border border-border rounded-lg p-4 hover:border-primary/30 transition-colors"
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-semibold text-text-muted">Step {wf.position}</span>
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                    wf.status === "active" ? "bg-emerald-100 text-emerald-700" : "bg-gray-100 text-gray-600"
                  }`}>
                    {wf.status}
                  </span>
                </div>
                <h4 className="font-medium text-foreground">{wf.name}</h4>
                {wf.description && (
                  <p className="text-sm text-text-muted mt-0.5 line-clamp-1">{wf.description}</p>
                )}
                {wf.last_run_at && (
                  <p className="text-xs text-text-muted mt-1">Last ran {timeAgo(wf.last_run_at)}</p>
                )}
              </Link>
            </div>
          </div>
        );
      })}
    </div>
  );
}

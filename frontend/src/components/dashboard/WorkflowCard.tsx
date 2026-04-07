import Link from "next/link";
import { timeAgo } from "@/lib/time";

interface WorkflowCardProps {
  id: string;
  name: string;
  description: string | null;
  status: string;
  primaryActionType: string;
  lastRunAt: string | null;
  runCountToday: number;
  hasErrors: boolean;
}

const ACTION_ICONS: Record<string, string> = {
  send_sms: "💬",
  send_template_sms: "💬",
  send_email: "✉️",
  send_template_email: "✉️",
  create_calendar_event: "📅",
  send_review_request: "⭐",
};

const STATUS_BADGES: Record<string, { bg: string; text: string; label: string }> = {
  active: { bg: "bg-emerald-100", text: "text-emerald-700", label: "Active" },
  testing: { bg: "bg-amber-100", text: "text-amber-700", label: "Testing" },
  paused: { bg: "bg-gray-100", text: "text-gray-600", label: "Paused" },
  draft: { bg: "bg-blue-100", text: "text-blue-700", label: "Draft" },
};

export function WorkflowCard({
  id,
  name,
  description,
  status,
  primaryActionType,
  lastRunAt,
  runCountToday,
  hasErrors,
}: WorkflowCardProps) {
  const icon = ACTION_ICONS[primaryActionType] || "⚡";
  const badge = STATUS_BADGES[status] || STATUS_BADGES.draft;

  let lastActivity = "Hasn't run yet";
  if (runCountToday > 0) {
    lastActivity = `Ran ${runCountToday} ${runCountToday === 1 ? "time" : "times"} today`;
  } else if (lastRunAt) {
    lastActivity = `Last ran ${timeAgo(lastRunAt)}`;
  }

  return (
    <Link
      href={`/dashboard/workflows/${id}`}
      className="block bg-surface border border-border rounded-xl p-5 hover:shadow-md hover:border-primary/30 transition-all group"
    >
      <div className="flex items-start gap-3">
        <span className="text-2xl mt-0.5">{icon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-semibold text-foreground truncate">{name}</h3>
            <span className={`shrink-0 px-2 py-0.5 rounded-full text-xs font-medium ${badge.bg} ${badge.text}`}>
              {badge.label}
            </span>
            {hasErrors && (
              <span className="shrink-0 w-2 h-2 rounded-full bg-red-500" title="Has errors" />
            )}
          </div>
          {description && (
            <p className="text-sm text-text-muted line-clamp-2">{description}</p>
          )}
          <p className="text-xs text-text-muted mt-2">{lastActivity}</p>
        </div>
        <span className="text-text-muted/40 group-hover:text-primary transition-colors mt-2">
          →
        </span>
      </div>
    </Link>
  );
}

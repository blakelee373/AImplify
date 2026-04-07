"use client";

import { timeAgo } from "@/lib/time";

interface ActivityEntryProps {
  actionType: string;
  description: string;
  workflowName: string | null;
  timestamp: string;
  success: boolean;
  friendlyError?: string | null;
  compact?: boolean;
}

const TYPE_ICONS: Record<string, string> = {
  send_sms: "💬",
  send_template_sms: "💬",
  send_email: "✉️",
  send_template_email: "✉️",
  create_calendar_event: "📅",
  send_review_request: "⭐",
  workflow_executed: "✅",
  workflow_created: "🆕",
  step_failed: "❌",
};

export function ActivityEntry({
  actionType,
  description,
  workflowName,
  timestamp,
  success,
  friendlyError,
  compact,
}: ActivityEntryProps) {
  const icon = TYPE_ICONS[actionType] || "⚡";
  const time = timeAgo(timestamp);

  return (
    <div className={`flex items-start gap-3 ${compact ? "py-2" : "py-3"}`}>
      <span className={compact ? "text-base" : "text-lg"}>{icon}</span>
      <div className="flex-1 min-w-0">
        <p className={`text-foreground ${compact ? "text-sm" : "text-sm font-medium"}`}>
          {description}
        </p>
        {workflowName && (
          <p className="text-xs text-text-muted mt-0.5">
            {workflowName} • {time}
          </p>
        )}
        {!success && friendlyError && (
          <p className="text-xs text-red-600 mt-1">{friendlyError}</p>
        )}
      </div>
      <span className="shrink-0 mt-0.5">
        {success ? (
          <span className="text-emerald-500 text-sm">✓</span>
        ) : (
          <span className="text-red-500 text-sm">✗</span>
        )}
      </span>
    </div>
  );
}

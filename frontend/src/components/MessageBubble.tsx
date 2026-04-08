import { WorkflowSummaryCard } from "./WorkflowSummaryCard";

interface MessageMetadata {
  message_type?: string;
  workflow_draft?: {
    name: string;
    description: string;
    trigger_type: string;
    trigger_config: Record<string, string>;
    steps: Array<{
      step_order: number;
      action_type: string;
      description: string;
    }>;
  };
  workflow_id?: number;
  action_type?: string;
  action_params?: Record<string, unknown>;
  success?: boolean;
  details?: Record<string, unknown>;
  manage_action?: string;
  workflow_name?: string;
  workflow_status?: string;
  detail?: string;
  query?: string;
}

interface MessageBubbleProps {
  role: "user" | "assistant";
  content: string;
  metadata?: MessageMetadata | null;
}

export function MessageBubble({ role, content, metadata }: MessageBubbleProps) {
  const isUser = role === "user";

  // Workflow confirmed — show success banner
  if (metadata?.message_type === "workflow_confirmed") {
    return (
      <div className="flex justify-start">
        <div className="max-w-[75%] space-y-3">
          <div className="bg-stone-100 rounded-2xl px-4 py-3 text-sm leading-relaxed text-stone-800 rounded-bl-md">
            {content}
          </div>
          <div className="bg-green-50 border border-green-200 rounded-xl px-4 py-3 text-sm text-green-700 font-medium">
            Saved! You can view this on the Dashboard.
          </div>
        </div>
      </div>
    );
  }

  // Workflow management request — show pending confirmation
  if (metadata?.message_type === "workflow_manage_request") {
    const actionStyles: Record<string, { icon: string; cls: string }> = {
      pause: { icon: "⏸", cls: "bg-amber-50 border-amber-200 text-amber-700" },
      resume: { icon: "▶", cls: "bg-green-50 border-green-200 text-green-700" },
      delete: { icon: "🗑", cls: "bg-red-50 border-red-200 text-red-700" },
    };
    const info = actionStyles[metadata.manage_action || ""] || { icon: "⚙", cls: "bg-stone-50 border-stone-200 text-stone-700" };
    return (
      <div className="flex justify-start">
        <div className="max-w-[75%] space-y-3">
          <div className="bg-stone-100 rounded-2xl px-4 py-3 text-sm leading-relaxed text-stone-800 rounded-bl-md">
            {content}
          </div>
          <div className={`${info.cls} border rounded-xl px-4 py-3 text-sm font-medium`}>
            {info.icon} {metadata.manage_action?.charAt(0).toUpperCase()}{metadata.manage_action?.slice(1)} &ldquo;{metadata.workflow_name}&rdquo;
            {metadata.workflow_status && (
              <span className="text-xs font-normal ml-2">(currently {metadata.workflow_status})</span>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Workflow management result — show success/error
  if (metadata?.message_type === "workflow_manage_result") {
    const ok = metadata.success;
    return (
      <div className="flex justify-start">
        <div className="max-w-[75%] space-y-3">
          <div className="bg-stone-100 rounded-2xl px-4 py-3 text-sm leading-relaxed text-stone-800 rounded-bl-md">
            {content}
          </div>
          <div className={`${ok ? "bg-green-50 border-green-200 text-green-700" : "bg-red-50 border-red-200 text-red-700"} border rounded-xl px-4 py-3 text-sm font-medium`}>
            {metadata.detail || (ok ? "Done!" : "Something went wrong")}
          </div>
        </div>
      </div>
    );
  }

  // Workflow management not found
  if (metadata?.message_type === "workflow_manage_not_found") {
    return (
      <div className="flex justify-start">
        <div className="max-w-[75%] space-y-3">
          <div className="bg-stone-100 rounded-2xl px-4 py-3 text-sm leading-relaxed text-stone-800 rounded-bl-md">
            {content}
          </div>
          <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm text-amber-700 font-medium">
            Could not find a workflow matching &ldquo;{metadata.query}&rdquo;
          </div>
        </div>
      </div>
    );
  }

  // Action request — show confirmation card with details
  if (metadata?.message_type === "action_request" && metadata.action_params) {
    return (
      <div className="flex justify-start">
        <div className="max-w-[75%] space-y-3">
          <div className="bg-stone-100 rounded-2xl px-4 py-3 text-sm leading-relaxed text-stone-800 rounded-bl-md">
            {content}
          </div>
          <ActionRequestCard actionType={metadata.action_type || ""} params={metadata.action_params} />
        </div>
      </div>
    );
  }

  // Action result — show success or error banner
  if (metadata?.message_type === "action_result") {
    return (
      <div className="flex justify-start">
        <div className="max-w-[75%] space-y-3">
          <div className="bg-stone-100 rounded-2xl px-4 py-3 text-sm leading-relaxed text-stone-800 rounded-bl-md">
            {content}
          </div>
          <ActionResultBanner
            success={metadata.success ?? false}
            actionType={metadata.action_type || ""}
            details={metadata.details || {}}
          />
        </div>
      </div>
    );
  }

  // Workflow summary — show the card below the message
  if (metadata?.message_type === "workflow_summary" && metadata.workflow_draft) {
    return (
      <div className="flex justify-start">
        <div className="max-w-[75%] space-y-3">
          <div className="bg-stone-100 rounded-2xl px-4 py-3 text-sm leading-relaxed text-stone-800 rounded-bl-md">
            {content}
          </div>
          <WorkflowSummaryCard draft={metadata.workflow_draft} />
        </div>
      </div>
    );
  }

  // Regular message
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
          isUser
            ? "bg-primary text-white rounded-br-md"
            : "bg-stone-100 text-stone-800 rounded-bl-md"
        }`}
      >
        {content}
      </div>
    </div>
  );
}

/* ── Action sub-components ──────────────────────────────────────────────────── */

const ACTION_LABELS: Record<string, { icon: string; label: string }> = {
  send_email: { icon: "✉️", label: "Send Email" },
  create_event: { icon: "📅", label: "Create Event" },
  update_event: { icon: "📝", label: "Update Event" },
  check_availability: { icon: "🔍", label: "Check Availability" },
  list_events: { icon: "📋", label: "List Events" },
};

function formatParamValue(key: string, value: unknown): string {
  const str = String(value);
  // Format ISO timestamps as readable dates
  if ((key.includes("time") || key === "start" || key === "end") && /^\d{4}-\d{2}-\d{2}T/.test(str)) {
    return new Date(str).toLocaleString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  }
  // Format arrays (e.g., attendees)
  if (Array.isArray(value)) {
    return value.join(", ");
  }
  return str.length > 120 ? str.slice(0, 120) + "..." : str;
}

/** Human-friendly labels for action parameter keys */
const PARAM_LABELS: Record<string, string> = {
  recipient: "To",
  subject: "Subject",
  body: "Message",
  summary: "Event",
  start_time: "Starts",
  end_time: "Ends",
  description: "Notes",
  attendees: "Inviting",
  add_attendees: "Adding",
};

function ActionRequestCard({
  actionType,
  params,
}: {
  actionType: string;
  params: Record<string, unknown>;
}) {
  const info = ACTION_LABELS[actionType] || { icon: "⚡", label: actionType };

  const filteredParams = Object.entries(params).filter(
    ([, value]) => value != null && String(value) !== "<UNKNOWN>" && String(value) !== ""
  );

  return (
    <div className="bg-blue-50 border-2 border-blue-300 rounded-xl overflow-hidden">
      <div className="bg-blue-100 px-4 py-2.5 flex items-center gap-2">
        <span className="text-base">{info.icon}</span>
        <span className="text-sm font-semibold text-blue-900">Ready to {info.label.toLowerCase()}</span>
      </div>
      <div className="px-4 py-3 space-y-2">
        {filteredParams.map(([key, value]) => (
          <div key={key} className="flex gap-2 text-sm">
            <span className="font-medium text-blue-800 min-w-[60px] shrink-0">
              {PARAM_LABELS[key] || key.replace(/_/g, " ")}:
            </span>
            <span className="text-blue-700">
              {formatParamValue(key, value)}
            </span>
          </div>
        ))}
      </div>
      <div className="bg-blue-100/50 px-4 py-2 text-xs text-blue-600 border-t border-blue-200">
        Reply <span className="font-semibold">&ldquo;yes&rdquo;</span> to confirm or tell me what to change
      </div>
    </div>
  );
}

function ActionResultBanner({
  success,
  actionType,
  details,
}: {
  success: boolean;
  actionType: string;
  details: Record<string, unknown>;
}) {
  if (success) {
    let summary = "Done!";
    if (actionType === "send_email" && details.message_id) {
      summary = `Email sent successfully`;
    } else if (actionType === "create_event" && details.event_id) {
      summary = `Event created`;
    } else if (actionType === "check_availability") {
      const available = details.available;
      summary = available ? "That time slot is available!" : "There are conflicts in that time slot";
    } else if (actionType === "list_events") {
      const count = details.count as number;
      summary = count > 0 ? `Found ${count} upcoming event${count !== 1 ? "s" : ""}` : "No upcoming events";
    }

    return (
      <div className="bg-green-50 border border-green-200 rounded-xl px-4 py-3 text-sm text-green-700 font-medium">
        {summary}
      </div>
    );
  }

  return (
    <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700 font-medium">
      Something went wrong: {String(details.error || "Unknown error")}
    </div>
  );
}

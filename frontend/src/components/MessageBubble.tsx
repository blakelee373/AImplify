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
  check_availability: { icon: "🔍", label: "Check Availability" },
  list_events: { icon: "📋", label: "List Events" },
};

function ActionRequestCard({
  actionType,
  params,
}: {
  actionType: string;
  params: Record<string, unknown>;
}) {
  const info = ACTION_LABELS[actionType] || { icon: "⚡", label: actionType };

  return (
    <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3 space-y-1.5">
      <div className="text-sm font-medium text-blue-800">
        {info.icon} {info.label}
      </div>
      {Object.entries(params)
        .filter(([, value]) => value != null && String(value) !== "<UNKNOWN>" && String(value) !== "")
        .map(([key, value]) => (
        <div key={key} className="text-xs text-blue-600">
          <span className="font-medium capitalize">{key.replace(/_/g, " ")}:</span>{" "}
          {String(value).length > 120 ? String(value).slice(0, 120) + "..." : String(value)}
        </div>
      ))}
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

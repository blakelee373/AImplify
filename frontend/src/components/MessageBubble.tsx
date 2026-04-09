import { WorkflowSummaryCard } from "./WorkflowSummaryCard";

interface WorkflowListItem {
  id: number;
  name: string;
  status: string;
  description?: string;
  trigger_type?: string;
  step_count: number;
  updated_at?: string;
}

interface ActivityItem {
  action_type: string;
  description: string;
  created_at?: string;
  workflow_id?: number;
  details?: Record<string, unknown>;
}

interface StepResult {
  step_order: number;
  action_type: string;
  description?: string;
  status: string;
  details?: Record<string, unknown>;
}

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
  provider?: string;
  error?: string;
  workflows?: WorkflowListItem[];
  workflow?: WorkflowListItem;
  recent_activity?: ActivityItem[];
  activity?: ActivityItem[];
  step_count?: number;
  steps_executed?: number;
  results?: StepResult[];
  new_schedule?: string;
  next_run_at?: string;
  current_schedule?: string;
}

interface MessageBubbleProps {
  role: "user" | "assistant";
  content: string;
  metadata?: MessageMetadata | null;
  onConnectTool?: (provider: string) => void;
}

export function MessageBubble({ role, content, metadata, onConnectTool }: MessageBubbleProps) {
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

  // Workflow list — show all workflows with status
  if (metadata?.message_type === "workflow_list" && metadata.workflows) {
    return (
      <div className="flex justify-start">
        <div className="max-w-[75%] space-y-3">
          <div className="bg-stone-100 rounded-2xl px-4 py-3 text-sm leading-relaxed text-stone-800 rounded-bl-md">
            {content}
          </div>
          <WorkflowListCard workflows={metadata.workflows} />
        </div>
      </div>
    );
  }

  // Workflow status — detail card with activity log
  if (metadata?.message_type === "workflow_status" && metadata.workflow) {
    return (
      <div className="flex justify-start">
        <div className="max-w-[75%] space-y-3">
          <div className="bg-stone-100 rounded-2xl px-4 py-3 text-sm leading-relaxed text-stone-800 rounded-bl-md">
            {content}
          </div>
          <WorkflowStatusCard workflow={metadata.workflow} activity={metadata.recent_activity || []} />
        </div>
      </div>
    );
  }

  // Activity summary — system-wide activity feed
  if (metadata?.message_type === "workflow_activity" && metadata.activity) {
    return (
      <div className="flex justify-start">
        <div className="max-w-[75%] space-y-3">
          <div className="bg-stone-100 rounded-2xl px-4 py-3 text-sm leading-relaxed text-stone-800 rounded-bl-md">
            {content}
          </div>
          <ActivityFeedCard activity={metadata.activity} />
        </div>
      </div>
    );
  }

  // Workflow run request — confirmation card
  if (metadata?.message_type === "workflow_run_request") {
    return (
      <div className="flex justify-start">
        <div className="max-w-[75%] space-y-3">
          <div className="bg-stone-100 rounded-2xl px-4 py-3 text-sm leading-relaxed text-stone-800 rounded-bl-md">
            {content}
          </div>
          <div className="bg-blue-50 border-2 border-blue-300 rounded-xl overflow-hidden">
            <div className="bg-blue-100 px-4 py-2.5 flex items-center gap-2">
              <span className="text-base">{"\u25B6\uFE0F"}</span>
              <span className="text-sm font-semibold text-blue-900">Run &ldquo;{metadata.workflow_name}&rdquo;</span>
            </div>
            <div className="px-4 py-3 space-y-1">
              {metadata.workflow_status && (
                <div className="text-xs text-blue-600">Status: {metadata.workflow_status}</div>
              )}
              {metadata.step_count != null && (
                <div className="text-xs text-blue-600">{metadata.step_count} step{metadata.step_count !== 1 ? "s" : ""} to execute</div>
              )}
            </div>
            <div className="bg-blue-100/50 px-4 py-2 text-xs text-blue-600 border-t border-blue-200">
              Reply <span className="font-semibold">&ldquo;yes&rdquo;</span> to run or <span className="font-semibold">&ldquo;no&rdquo;</span> to cancel
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Workflow run result — step-by-step execution results
  if (metadata?.message_type === "workflow_run_result") {
    return (
      <div className="flex justify-start">
        <div className="max-w-[75%] space-y-3">
          <div className="bg-stone-100 rounded-2xl px-4 py-3 text-sm leading-relaxed text-stone-800 rounded-bl-md">
            {content}
          </div>
          <WorkflowRunResultCard
            workflowName={metadata.workflow_name || ""}
            success={metadata.success ?? false}
            stepsExecuted={metadata.steps_executed ?? 0}
            results={metadata.results || []}
            error={metadata.error}
          />
        </div>
      </div>
    );
  }

  // Schedule change request — show full workflow summary card for confirmation
  if (metadata?.message_type === "workflow_schedule_request") {
    return (
      <div className="flex justify-start">
        <div className="max-w-[75%] space-y-3">
          <div className="bg-stone-100 rounded-2xl px-4 py-3 text-sm leading-relaxed text-stone-800 rounded-bl-md">
            {content}
          </div>
          {metadata.workflow_draft ? (
            <WorkflowSummaryCard draft={metadata.workflow_draft} />
          ) : (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
              <h3 className="font-semibold text-stone-900 text-sm">{metadata.workflow_name}</h3>
              {metadata.current_schedule && (
                <div className="text-xs text-amber-700 mt-1">Current: {metadata.current_schedule}</div>
              )}
            </div>
          )}
          <div className="bg-amber-100/50 border border-amber-200 rounded-lg px-4 py-2 text-xs text-amber-700">
            Reply <span className="font-semibold">&ldquo;yes&rdquo;</span> to confirm or <span className="font-semibold">&ldquo;no&rdquo;</span> to cancel
          </div>
        </div>
      </div>
    );
  }

  // Schedule change result — success/error
  if (metadata?.message_type === "workflow_schedule_result") {
    const ok = metadata.success;
    return (
      <div className="flex justify-start">
        <div className="max-w-[75%] space-y-3">
          <div className="bg-stone-100 rounded-2xl px-4 py-3 text-sm leading-relaxed text-stone-800 rounded-bl-md">
            {content}
          </div>
          {ok ? (
            <div className="bg-green-50 border border-green-200 rounded-xl px-4 py-3 text-sm text-green-700">
              <span className="font-medium">{"\u2705"} Schedule updated</span>
              {metadata.new_schedule && (
                <span className="ml-1">&mdash; {metadata.new_schedule}</span>
              )}
              {metadata.next_run_at && (
                <div className="text-xs text-green-600 mt-1">
                  Next run: {new Date(metadata.next_run_at).toLocaleString(undefined, {
                    weekday: "short",
                    month: "short",
                    day: "numeric",
                    hour: "numeric",
                    minute: "2-digit",
                  })}
                </div>
              )}
            </div>
          ) : (
            <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700 font-medium">
              {metadata.error || "Failed to update schedule"}
            </div>
          )}
        </div>
      </div>
    );
  }

  // Connect tool — show connect button card
  if (metadata?.message_type === "connect_tool" && metadata.provider) {
    const info = PROVIDER_DISPLAY[metadata.provider] || { icon: "\u{1F517}", name: metadata.provider };
    return (
      <div className="flex justify-start">
        <div className="max-w-[75%] space-y-3">
          <div className="bg-stone-100 rounded-2xl px-4 py-3 text-sm leading-relaxed text-stone-800 rounded-bl-md">
            {content}
          </div>
          <div className="bg-blue-50 border-2 border-blue-300 rounded-xl overflow-hidden">
            <div className="bg-blue-100 px-4 py-2.5 flex items-center gap-2">
              <span className="text-base">{info.icon}</span>
              <span className="text-sm font-semibold text-blue-900">Connect {info.name}</span>
            </div>
            <div className="px-4 py-3">
              <button
                onClick={() => onConnectTool?.(metadata.provider!)}
                className="px-4 py-2 text-sm rounded-lg bg-primary text-white font-semibold hover:bg-primary-hover transition-colors"
              >
                Connect {info.name}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Already connected — info banner
  if (metadata?.message_type === "connect_already" && metadata.provider) {
    const info = PROVIDER_DISPLAY[metadata.provider] || { icon: "\u{1F517}", name: metadata.provider };
    return (
      <div className="flex justify-start">
        <div className="max-w-[75%] space-y-3">
          <div className="bg-stone-100 rounded-2xl px-4 py-3 text-sm leading-relaxed text-stone-800 rounded-bl-md">
            {content}
          </div>
          <div className="bg-green-50 border border-green-200 rounded-xl px-4 py-3 text-sm text-green-700 font-medium">
            {info.icon} {info.name} is already connected
          </div>
        </div>
      </div>
    );
  }

  // Disconnect request — confirmation card
  if (metadata?.message_type === "disconnect_request" && metadata.provider) {
    const info = PROVIDER_DISPLAY[metadata.provider] || { icon: "\u{1F517}", name: metadata.provider };
    return (
      <div className="flex justify-start">
        <div className="max-w-[75%] space-y-3">
          <div className="bg-stone-100 rounded-2xl px-4 py-3 text-sm leading-relaxed text-stone-800 rounded-bl-md">
            {content}
          </div>
          <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm text-amber-700 font-medium">
            {"\u26A0\uFE0F"} Disconnect {info.name}
            <div className="mt-1 text-xs font-normal">Reply &ldquo;yes&rdquo; to confirm or &ldquo;no&rdquo; to cancel</div>
          </div>
        </div>
      </div>
    );
  }

  // Disconnect result — success/error banner
  if (metadata?.message_type === "disconnect_result") {
    const info = PROVIDER_DISPLAY[metadata.provider || ""] || { icon: "\u{1F517}", name: metadata.provider };
    return (
      <div className="flex justify-start">
        <div className="max-w-[75%] space-y-3">
          <div className="bg-stone-100 rounded-2xl px-4 py-3 text-sm leading-relaxed text-stone-800 rounded-bl-md">
            {content}
          </div>
          {metadata.success ? (
            <div className="bg-green-50 border border-green-200 rounded-xl px-4 py-3 text-sm text-green-700 font-medium">
              {info.name} disconnected
            </div>
          ) : (
            <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700 font-medium">
              Failed to disconnect {info.name}: {metadata.error || "Unknown error"}
            </div>
          )}
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

/* ── Provider display info ─────────────────────────────────────────────────── */

const PROVIDER_DISPLAY: Record<string, { icon: string; name: string }> = {
  gmail: { icon: "\u2709", name: "Gmail" },
  google_calendar: { icon: "\uD83D\uDCC5", name: "Google Calendar" },
};

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
  cc: "CC",
  bcc: "BCC",
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
    // List events — show each event
    if (actionType === "list_events") {
      const events = (details.events || []) as Array<Record<string, string>>;
      if (events.length === 0) {
        return (
          <div className="bg-green-50 border border-green-200 rounded-xl px-4 py-3 text-sm text-green-700 font-medium">
            No upcoming events
          </div>
        );
      }
      return (
        <div className="bg-green-50 border border-green-200 rounded-xl overflow-hidden">
          <div className="bg-green-100 px-4 py-2.5 text-sm font-semibold text-green-900">
            📋 {events.length} upcoming event{events.length !== 1 ? "s" : ""}
          </div>
          <div className="divide-y divide-green-200">
            {events.map((event, i) => (
              <div key={i} className="px-4 py-2.5 flex justify-between items-start gap-3">
                <span className="text-sm font-medium text-green-800">{event.summary}</span>
                <span className="text-xs text-green-600 whitespace-nowrap shrink-0">
                  {event.start ? new Date(event.start).toLocaleString(undefined, {
                    weekday: "short", month: "short", day: "numeric",
                    hour: "numeric", minute: "2-digit",
                  }) : ""}
                </span>
              </div>
            ))}
          </div>
        </div>
      );
    }

    // Check availability — show conflicts if any
    if (actionType === "check_availability") {
      const result = details.result as Record<string, unknown> | undefined;
      const available = result?.available ?? details.available;
      const conflicts = (result?.conflicts || details.conflicts || []) as Array<Record<string, string>>;
      if (available) {
        return (
          <div className="bg-green-50 border border-green-200 rounded-xl px-4 py-3 text-sm text-green-700 font-medium">
            That time slot is available!
          </div>
        );
      }
      return (
        <div className="bg-amber-50 border border-amber-200 rounded-xl overflow-hidden">
          <div className="bg-amber-100 px-4 py-2.5 text-sm font-semibold text-amber-900">
            ⚠️ {conflicts.length} conflict{conflicts.length !== 1 ? "s" : ""} found
          </div>
          <div className="divide-y divide-amber-200">
            {conflicts.map((c, i) => (
              <div key={i} className="px-4 py-2.5 text-sm text-amber-700">
                {new Date(c.start).toLocaleString(undefined, {
                  weekday: "short", month: "short", day: "numeric",
                  hour: "numeric", minute: "2-digit",
                })}
                {" — "}
                {new Date(c.end).toLocaleString(undefined, {
                  hour: "numeric", minute: "2-digit",
                })}
              </div>
            ))}
          </div>
        </div>
      );
    }

    let summary = "Done!";
    if (actionType === "send_email" && details.message_id) {
      summary = `Email sent successfully`;
    } else if (actionType === "create_event" && details.event_id) {
      summary = `Event created`;
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

/* ── Workflow query sub-components ─────────────────────────────────────────── */

const STATUS_STYLES: Record<string, { dot: string; text: string }> = {
  active: { dot: "bg-green-500", text: "text-green-700" },
  paused: { dot: "bg-amber-500", text: "text-amber-700" },
  draft: { dot: "bg-stone-400", text: "text-stone-500" },
  testing: { dot: "bg-blue-500", text: "text-blue-700" },
};

function WorkflowListCard({ workflows }: { workflows: WorkflowListItem[] }) {
  if (workflows.length === 0) {
    return (
      <div className="bg-stone-50 border border-stone-200 rounded-xl px-4 py-3 text-sm text-stone-500 font-medium">
        No workflows set up yet.
      </div>
    );
  }
  return (
    <div className="bg-stone-50 border border-stone-200 rounded-xl overflow-hidden">
      <div className="bg-stone-200/60 px-4 py-2.5 text-sm font-semibold text-stone-800">
        {workflows.length} workflow{workflows.length !== 1 ? "s" : ""}
      </div>
      <div className="divide-y divide-stone-200">
        {workflows.map((wf) => {
          const style = STATUS_STYLES[wf.status] || STATUS_STYLES.draft;
          return (
            <div key={wf.id} className="px-4 py-3 flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="text-sm font-medium text-stone-800 truncate">{wf.name}</div>
                {wf.description && (
                  <div className="text-xs text-stone-500 truncate mt-0.5">{wf.description}</div>
                )}
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <span className={`w-2 h-2 rounded-full ${style.dot}`} />
                <span className={`text-xs font-medium ${style.text}`}>{wf.status}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function WorkflowStatusCard({ workflow, activity }: { workflow: WorkflowListItem; activity: ActivityItem[] }) {
  const style = STATUS_STYLES[workflow.status] || STATUS_STYLES.draft;
  return (
    <div className="bg-stone-50 border border-stone-200 rounded-xl overflow-hidden">
      <div className="bg-stone-200/60 px-4 py-2.5 flex items-center justify-between">
        <span className="text-sm font-semibold text-stone-800">{workflow.name}</span>
        <div className="flex items-center gap-1.5">
          <span className={`w-2 h-2 rounded-full ${style.dot}`} />
          <span className={`text-xs font-medium ${style.text}`}>{workflow.status}</span>
        </div>
      </div>
      {workflow.description && (
        <div className="px-4 py-2 text-xs text-stone-500 border-b border-stone-200">{workflow.description}</div>
      )}
      <div className="px-4 py-2 text-xs text-stone-400 border-b border-stone-200">
        {workflow.step_count} step{workflow.step_count !== 1 ? "s" : ""}
        {workflow.trigger_type && <> &middot; {workflow.trigger_type}</>}
      </div>
      {activity.length > 0 ? (
        <div className="divide-y divide-stone-100">
          <div className="px-4 py-2 text-xs font-medium text-stone-600 bg-stone-100/50">Recent activity</div>
          {activity.map((a, i) => (
            <div key={i} className="px-4 py-2 flex items-start justify-between gap-3">
              <span className="text-xs text-stone-600 min-w-0 truncate">{a.description}</span>
              {a.created_at && (
                <span className="text-xs text-stone-400 whitespace-nowrap shrink-0">
                  {formatTimeAgo(a.created_at)}
                </span>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="px-4 py-3 text-xs text-stone-400">No recent activity</div>
      )}
    </div>
  );
}

function ActivityFeedCard({ activity }: { activity: ActivityItem[] }) {
  if (activity.length === 0) {
    return (
      <div className="bg-stone-50 border border-stone-200 rounded-xl px-4 py-3 text-sm text-stone-500 font-medium">
        No recent activity.
      </div>
    );
  }
  return (
    <div className="bg-stone-50 border border-stone-200 rounded-xl overflow-hidden">
      <div className="bg-stone-200/60 px-4 py-2.5 text-sm font-semibold text-stone-800">
        Recent activity
      </div>
      <div className="divide-y divide-stone-100">
        {activity.map((a, i) => (
          <div key={i} className="px-4 py-2.5 flex items-start justify-between gap-3">
            <span className="text-xs text-stone-600 min-w-0">{a.description}</span>
            {a.created_at && (
              <span className="text-xs text-stone-400 whitespace-nowrap shrink-0">
                {formatTimeAgo(a.created_at)}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function WorkflowRunResultCard({
  workflowName,
  success,
  stepsExecuted,
  results,
  error,
}: {
  workflowName: string;
  success: boolean;
  stepsExecuted: number;
  results: StepResult[];
  error?: string;
}) {
  if (!success && error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700 font-medium">
        Failed to run &ldquo;{workflowName}&rdquo;: {error}
      </div>
    );
  }
  return (
    <div className={`${success ? "bg-green-50 border-green-200" : "bg-amber-50 border-amber-200"} border rounded-xl overflow-hidden`}>
      <div className={`${success ? "bg-green-100 text-green-900" : "bg-amber-100 text-amber-900"} px-4 py-2.5 text-sm font-semibold`}>
        {success ? "\u2705" : "\u26A0\uFE0F"} {workflowName} — {stepsExecuted} step{stepsExecuted !== 1 ? "s" : ""} {success ? "completed" : "ran"}
      </div>
      <div className={`divide-y ${success ? "divide-green-200" : "divide-amber-200"}`}>
        {results.map((r, i) => (
          <div key={i} className="px-4 py-2.5 flex items-center justify-between gap-3">
            <div className="min-w-0">
              <span className="text-xs font-medium text-stone-700">Step {r.step_order}</span>
              {r.description && <span className="text-xs text-stone-500 ml-2">{r.description}</span>}
            </div>
            <span className={`text-xs font-medium shrink-0 ${r.status === "success" ? "text-green-600" : "text-red-600"}`}>
              {r.status === "success" ? "\u2713" : "\u2717"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function formatTimeAgo(iso: string): string {
  // Backend stores UTC but SQLite drops timezone info — treat bare timestamps as UTC
  const utcIso = iso.includes("Z") || iso.includes("+") || /\d{2}:\d{2}$/.test(iso) ? iso : iso + "Z";
  const diff = Date.now() - new Date(utcIso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

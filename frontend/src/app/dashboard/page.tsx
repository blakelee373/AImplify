"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { timeAgo } from "@/lib/workflow-utils";
import { WorkflowStatusBadge } from "@/components/WorkflowStatusBadge";

/* ── Types ─────────────────────────────────────────────────────────────────── */

interface SendEmailResult {
  status: string;
  recipient: string;
  subject: string;
  gmail_message_id: string;
}

interface CalendarEvent {
  event_id: string;
  summary: string;
  start: string;
  end: string;
  link?: string;
}

interface CreateEventResult {
  event_id: string;
  link: string;
  summary: string;
  start: string;
  end: string;
}

interface UpcomingEventsResult {
  events: CalendarEvent[];
  count: number;
}

interface AvailabilityResult {
  available: boolean;
  conflicts: { start: string; end: string }[];
}

interface WorkflowStep {
  id: number;
  step_order: number;
  action_type: string;
  description?: string;
}

interface WorkflowItem {
  id: number;
  name: string;
  description?: string;
  status: string;
  trigger_type?: string;
  steps: WorkflowStep[];
}

interface StepResult {
  step_order: number;
  action_type: string;
  description?: string;
  status: string;
  details: Record<string, unknown>;
}

interface ExecuteResult {
  workflow_id: number;
  workflow_name: string;
  status: string;
  steps_executed: number;
  results: StepResult[];
}

interface ActivityLogEntry {
  id: number;
  action_type: string;
  description: string;
  details: Record<string, unknown> | null;
  workflow_id: number | null;
  created_at: string;
}

type ActionResult = { type: "success" | "error"; message: string } | null;

/* ── Helpers ───────────────────────────────────────────────────────────────── */

function toLocalDatetimeValue(d: Date): string {
  const pad = (n: number) => n.toString().padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function localToISO(local: string): string {
  return new Date(local).toISOString();
}

const ACTION_ICONS: Record<string, string> = {
  send_email: "✉",
  create_event: "📅",
  check_calendar: "🔍",
};

function formatEventTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

/* ── Shared UI ─────────────────────────────────────────────────────────────── */

const inputClass =
  "mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary";

const btnClass =
  "px-5 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed";

function ResultBanner({ result }: { result: ActionResult }) {
  if (!result) return null;
  return (
    <div
      className={`mt-4 rounded-lg px-4 py-3 text-sm ${
        result.type === "success"
          ? "bg-green-50 text-green-800 border border-green-200"
          : "bg-red-50 text-red-800 border border-red-200"
      }`}
    >
      {result.message}
    </div>
  );
}

/* ── Component ─────────────────────────────────────────────────────────────── */

export default function DashboardPage() {
  /* Workflow state */
  const [workflows, setWorkflows] = useState<WorkflowItem[]>([]);
  const [loadingWorkflows, setLoadingWorkflows] = useState(false);
  const [runningId, setRunningId] = useState<number | null>(null);
  const [contextInputs, setContextInputs] = useState<Record<number, Record<string, string>>>({});
  const [execResults, setExecResults] = useState<Record<number, ExecuteResult | null>>({});
  const [execErrors, setExecErrors] = useState<Record<number, string | null>>({});

  /* Activity log state */
  const [activityLogs, setActivityLogs] = useState<ActivityLogEntry[]>([]);
  const [loadingLogs, setLoadingLogs] = useState(false);

  /* Email state */
  const [recipient, setRecipient] = useState("");
  const [emailSubject, setEmailSubject] = useState("");
  const [emailBody, setEmailBody] = useState("");
  const [sendingEmail, setSendingEmail] = useState(false);
  const [emailResult, setEmailResult] = useState<ActionResult>(null);

  /* Create event state */
  const now = new Date();
  const oneHourLater = new Date(now.getTime() + 60 * 60 * 1000);
  const [eventSummary, setEventSummary] = useState("");
  const [eventStart, setEventStart] = useState(toLocalDatetimeValue(now));
  const [eventEnd, setEventEnd] = useState(toLocalDatetimeValue(oneHourLater));
  const [eventDesc, setEventDesc] = useState("");
  const [creatingEvent, setCreatingEvent] = useState(false);
  const [eventResult, setEventResult] = useState<ActionResult>(null);

  /* Upcoming events state */
  const [upcomingEvents, setUpcomingEvents] = useState<CalendarEvent[]>([]);
  const [loadingEvents, setLoadingEvents] = useState(false);

  /* Check availability state */
  const [availStart, setAvailStart] = useState(toLocalDatetimeValue(now));
  const [availEnd, setAvailEnd] = useState(toLocalDatetimeValue(oneHourLater));
  const [checkingAvail, setCheckingAvail] = useState(false);
  const [availResult, setAvailResult] = useState<ActionResult>(null);

  /* Load data on mount */
  useEffect(() => {
    fetchWorkflows();
    fetchActivityLogs();
    fetchUpcoming();
  }, []);

  /* ── Workflow handlers ─────────────────────────────────────────────────── */

  async function fetchWorkflows() {
    setLoadingWorkflows(true);
    try {
      const data = await api.get<WorkflowItem[]>("/api/workflows");
      setWorkflows(data);
    } catch {
      setWorkflows([]);
    } finally {
      setLoadingWorkflows(false);
    }
  }

  async function fetchActivityLogs() {
    setLoadingLogs(true);
    try {
      const data = await api.get<ActivityLogEntry[]>("/api/activity-logs?limit=20");
      setActivityLogs(data);
    } catch {
      setActivityLogs([]);
    } finally {
      setLoadingLogs(false);
    }
  }

  function setCtxField(workflowId: number, key: string, value: string) {
    setContextInputs((prev) => ({
      ...prev,
      [workflowId]: { ...(prev[workflowId] || {}), [key]: value },
    }));
  }

  async function handleRunWorkflow(workflowId: number) {
    setRunningId(workflowId);
    setExecResults((prev) => ({ ...prev, [workflowId]: null }));
    setExecErrors((prev) => ({ ...prev, [workflowId]: null }));
    try {
      const data = await api.post<ExecuteResult>(
        `/api/workflows/${workflowId}/execute`,
        { context: contextInputs[workflowId] || {} },
      );
      setExecResults((prev) => ({ ...prev, [workflowId]: data }));
    } catch (err) {
      setExecErrors((prev) => ({
        ...prev,
        [workflowId]: err instanceof Error ? err.message : "Execution failed",
      }));
    } finally {
      setRunningId(null);
    }
  }

  /* ── Other handlers ────────────────────────────────────────────────────── */

  async function handleSendEmail(e: React.FormEvent) {
    e.preventDefault();
    if (!recipient.trim() || !emailSubject.trim() || !emailBody.trim()) return;
    setSendingEmail(true);
    setEmailResult(null);
    try {
      const data = await api.post<SendEmailResult>("/api/actions/send-email", {
        recipient: recipient.trim(),
        subject: emailSubject.trim(),
        body: emailBody.trim(),
      });
      setEmailResult({ type: "success", message: `Email sent to ${data.recipient}` });
      setRecipient("");
      setEmailSubject("");
      setEmailBody("");
    } catch (err) {
      setEmailResult({ type: "error", message: err instanceof Error ? err.message : "Failed to send email" });
    } finally {
      setSendingEmail(false);
    }
  }

  async function handleCreateEvent(e: React.FormEvent) {
    e.preventDefault();
    if (!eventSummary.trim()) return;
    setCreatingEvent(true);
    setEventResult(null);
    try {
      const data = await api.post<CreateEventResult>("/api/actions/create-event", {
        summary: eventSummary.trim(),
        start_time: localToISO(eventStart),
        end_time: localToISO(eventEnd),
        description: eventDesc.trim() || undefined,
      });
      setEventResult({ type: "success", message: `Event "${data.summary}" created` });
      setEventSummary("");
      setEventDesc("");
      fetchUpcoming();
    } catch (err) {
      setEventResult({ type: "error", message: err instanceof Error ? err.message : "Failed to create event" });
    } finally {
      setCreatingEvent(false);
    }
  }

  async function fetchUpcoming() {
    setLoadingEvents(true);
    try {
      const data = await api.get<UpcomingEventsResult>("/api/actions/upcoming-events?max_results=5");
      setUpcomingEvents(data.events);
    } catch {
      setUpcomingEvents([]);
    } finally {
      setLoadingEvents(false);
    }
  }

  async function handleCheckAvailability(e: React.FormEvent) {
    e.preventDefault();
    setCheckingAvail(true);
    setAvailResult(null);
    try {
      const data = await api.post<AvailabilityResult>("/api/actions/check-availability", {
        start_time: localToISO(availStart),
        end_time: localToISO(availEnd),
      });
      if (data.available) {
        setAvailResult({ type: "success", message: "That time slot is available!" });
      } else {
        const conflicts = data.conflicts.map((c) => `${formatEventTime(c.start)} - ${formatEventTime(c.end)}`).join(", ");
        setAvailResult({ type: "error", message: `Conflicts found: ${conflicts}` });
      }
    } catch (err) {
      setAvailResult({ type: "error", message: err instanceof Error ? err.message : "Failed to check availability" });
    } finally {
      setCheckingAvail(false);
    }
  }

  /* ── Render ─────────────────────────────────────────────────────────────── */

  return (
    <div className="p-6 max-w-2xl space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-stone-900">Dashboard</h1>
        <p className="text-sm text-stone-500 mt-1">
          Run your workflows and test individual actions.
        </p>
      </div>

      {/* ── Workflows ───────────────────────────────────────────────────── */}
      <section className="rounded-lg border border-stone-200 bg-white p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-stone-900">Your Workflows</h2>
            <p className="text-sm text-stone-500 mt-1">
              Run a saved workflow with context — the AI fills in the details.
            </p>
          </div>
          <div className="flex items-center gap-4">
            <Link href="/dashboard/workflows" className="text-sm text-primary hover:text-primary-hover font-medium">
              View all &rarr;
            </Link>
            <button onClick={fetchWorkflows} disabled={loadingWorkflows} className="text-sm text-primary hover:text-primary-hover font-medium">
              {loadingWorkflows ? "Loading..." : "Refresh"}
            </button>
          </div>
        </div>

        {workflows.length === 0 && !loadingWorkflows && (
          <p className="mt-4 text-sm text-stone-400">
            No workflows yet. Go to Chat and describe a task to create one.
          </p>
        )}

        <div className="mt-4 space-y-6">
          {workflows.map((wf) => (
            <div key={wf.id} className="rounded-lg border border-stone-200 p-4">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-stone-900">{wf.name}</h3>
                  {wf.description && (
                    <p className="text-xs text-stone-500 mt-0.5">{wf.description}</p>
                  )}
                </div>
                <WorkflowStatusBadge status={wf.status} />
              </div>

              {/* Steps preview */}
              <div className="mt-3 space-y-1">
                {wf.steps.map((step) => (
                  <div key={step.id} className="flex items-center gap-2 text-xs text-stone-600">
                    <span className="w-5 h-5 rounded-full bg-stone-100 flex items-center justify-center text-[10px] font-medium">
                      {step.step_order}
                    </span>
                    <span>{step.description || step.action_type}</span>
                  </div>
                ))}
              </div>

              {/* Context inputs */}
              <div className="mt-3 grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-stone-600">Client name</label>
                  <input
                    type="text"
                    placeholder="Jane Smith"
                    value={contextInputs[wf.id]?.client_name || ""}
                    onChange={(e) => setCtxField(wf.id, "client_name", e.target.value)}
                    className={inputClass}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-stone-600">Client email</label>
                  <input
                    type="email"
                    placeholder="jane@example.com"
                    value={contextInputs[wf.id]?.client_email || ""}
                    onChange={(e) => setCtxField(wf.id, "client_email", e.target.value)}
                    className={inputClass}
                  />
                </div>
              </div>

              {/* Run button */}
              <button
                onClick={() => handleRunWorkflow(wf.id)}
                disabled={runningId === wf.id}
                className={`mt-3 ${btnClass}`}
              >
                {runningId === wf.id ? "Running..." : "Run Workflow"}
              </button>

              {/* Execution results */}
              {execErrors[wf.id] && (
                <div className="mt-3 rounded-lg bg-red-50 text-red-800 border border-red-200 px-4 py-3 text-sm">
                  {execErrors[wf.id]}
                </div>
              )}
              {execResults[wf.id] && (
                <div className="mt-3 space-y-2">
                  <div className={`rounded-lg px-4 py-3 text-sm ${
                    execResults[wf.id]!.status === "completed"
                      ? "bg-green-50 text-green-800 border border-green-200"
                      : "bg-amber-50 text-amber-800 border border-amber-200"
                  }`}>
                    {execResults[wf.id]!.status === "completed"
                      ? `All ${execResults[wf.id]!.steps_executed} steps completed successfully`
                      : `Completed with errors (${execResults[wf.id]!.steps_executed} steps run)`}
                  </div>
                  {execResults[wf.id]!.results.map((r) => (
                    <div key={r.step_order} className="flex items-center gap-2 text-xs text-stone-600">
                      <span className={`w-2 h-2 rounded-full ${r.status === "success" ? "bg-green-500" : "bg-red-500"}`} />
                      Step {r.step_order}: {r.description || r.action_type} — {r.status}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* ── Recent Activity ────────────────────────────────────────────── */}
      <section className="rounded-lg border border-stone-200 bg-white p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-stone-900">Recent Activity</h2>
            <p className="text-sm text-stone-500 mt-1">What the system has been doing.</p>
          </div>
          <button onClick={fetchActivityLogs} disabled={loadingLogs} className="text-sm text-primary hover:text-primary-hover font-medium">
            {loadingLogs ? "Loading..." : "Refresh"}
          </button>
        </div>
        <div className="mt-4 space-y-3">
          {activityLogs.length === 0 && !loadingLogs && (
            <p className="text-sm text-stone-400">No activity yet. Send an email or run a workflow to see it here.</p>
          )}
          {activityLogs.map((log) => (
            <div key={log.id} className="flex items-start gap-3 rounded-lg bg-stone-50 px-4 py-3">
              <span className="text-lg shrink-0 mt-0.5">
                {ACTION_ICONS[log.action_type] || "⚡"}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-stone-900">{log.description}</p>
                <p className="text-xs text-stone-400 mt-0.5">{timeAgo(log.created_at)}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Send Email ──────────────────────────────────────────────────── */}
      <section className="rounded-lg border border-stone-200 bg-white p-6">
        <h2 className="text-lg font-semibold text-stone-900">Send Test Email</h2>
        <p className="text-sm text-stone-500 mt-1">Send an email through your connected Gmail account.</p>
        <ResultBanner result={emailResult} />
        <form onSubmit={handleSendEmail} className="mt-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-stone-700">To</label>
            <input type="email" value={recipient} onChange={(e) => setRecipient(e.target.value)} placeholder="test@example.com" required className={inputClass} />
          </div>
          <div>
            <label className="block text-sm font-medium text-stone-700">Subject</label>
            <input type="text" value={emailSubject} onChange={(e) => setEmailSubject(e.target.value)} placeholder="Welcome to our medspa!" required className={inputClass} />
          </div>
          <div>
            <label className="block text-sm font-medium text-stone-700">Body</label>
            <textarea value={emailBody} onChange={(e) => setEmailBody(e.target.value)} placeholder="Hi there! Thank you for booking with us..." required rows={3} className={`${inputClass} resize-none`} />
          </div>
          <button type="submit" disabled={sendingEmail || !recipient.trim() || !emailSubject.trim() || !emailBody.trim()} className={btnClass}>
            {sendingEmail ? "Sending..." : "Send Email"}
          </button>
        </form>
      </section>

      {/* ── Create Event ────────────────────────────────────────────────── */}
      <section className="rounded-lg border border-stone-200 bg-white p-6">
        <h2 className="text-lg font-semibold text-stone-900">Create Calendar Event</h2>
        <p className="text-sm text-stone-500 mt-1">Add an event to your Google Calendar.</p>
        <ResultBanner result={eventResult} />
        <form onSubmit={handleCreateEvent} className="mt-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-stone-700">Title</label>
            <input type="text" value={eventSummary} onChange={(e) => setEventSummary(e.target.value)} placeholder="Client consultation" required className={inputClass} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-stone-700">Start</label>
              <input type="datetime-local" value={eventStart} onChange={(e) => setEventStart(e.target.value)} required className={inputClass} />
            </div>
            <div>
              <label className="block text-sm font-medium text-stone-700">End</label>
              <input type="datetime-local" value={eventEnd} onChange={(e) => setEventEnd(e.target.value)} required className={inputClass} />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-stone-700">Description (optional)</label>
            <textarea value={eventDesc} onChange={(e) => setEventDesc(e.target.value)} placeholder="Notes about the appointment..." rows={2} className={`${inputClass} resize-none`} />
          </div>
          <button type="submit" disabled={creatingEvent || !eventSummary.trim()} className={btnClass}>
            {creatingEvent ? "Creating..." : "Create Event"}
          </button>
        </form>
      </section>

      {/* ── Upcoming Events ─────────────────────────────────────────────── */}
      <section className="rounded-lg border border-stone-200 bg-white p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-stone-900">Upcoming Events</h2>
            <p className="text-sm text-stone-500 mt-1">Next 5 events on your calendar.</p>
          </div>
          <button onClick={fetchUpcoming} disabled={loadingEvents} className="text-sm text-primary hover:text-primary-hover font-medium">
            {loadingEvents ? "Loading..." : "Refresh"}
          </button>
        </div>
        <div className="mt-4 space-y-3">
          {upcomingEvents.length === 0 && !loadingEvents && (
            <p className="text-sm text-stone-400">No upcoming events found.</p>
          )}
          {upcomingEvents.map((ev) => (
            <div key={ev.event_id} className="flex items-start justify-between rounded-lg bg-stone-50 px-4 py-3">
              <div>
                <p className="text-sm font-medium text-stone-900">{ev.summary}</p>
                <p className="text-xs text-stone-500 mt-0.5">
                  {formatEventTime(ev.start)} &mdash; {formatEventTime(ev.end)}
                </p>
              </div>
              {ev.link && (
                <a href={ev.link} target="_blank" rel="noopener noreferrer" className="text-xs text-primary hover:underline shrink-0">
                  Open
                </a>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* ── Check Availability ──────────────────────────────────────────── */}
      <section className="rounded-lg border border-stone-200 bg-white p-6">
        <h2 className="text-lg font-semibold text-stone-900">Check Availability</h2>
        <p className="text-sm text-stone-500 mt-1">See if a time slot is free on your calendar.</p>
        <ResultBanner result={availResult} />
        <form onSubmit={handleCheckAvailability} className="mt-4 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-stone-700">Start</label>
              <input type="datetime-local" value={availStart} onChange={(e) => setAvailStart(e.target.value)} required className={inputClass} />
            </div>
            <div>
              <label className="block text-sm font-medium text-stone-700">End</label>
              <input type="datetime-local" value={availEnd} onChange={(e) => setAvailEnd(e.target.value)} required className={inputClass} />
            </div>
          </div>
          <button type="submit" disabled={checkingAvail} className={btnClass}>
            {checkingAvail ? "Checking..." : "Check Availability"}
          </button>
        </form>
      </section>
    </div>
  );
}

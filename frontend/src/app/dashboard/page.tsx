"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";

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

type ActionResult = { type: "success" | "error"; message: string } | null;

/* ── Helpers ───────────────────────────────────────────────────────────────── */

function toLocalDatetimeValue(d: Date): string {
  const pad = (n: number) => n.toString().padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function localToISO(local: string): string {
  return new Date(local).toISOString();
}

function formatEventTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

/* ── Component ─────────────────────────────────────────────────────────────── */

export default function DashboardPage() {
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

  /* Load upcoming events on mount */
  useEffect(() => {
    fetchUpcoming();
  }, []);

  /* ── Handlers ──────────────────────────────────────────────────────────── */

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

  /* ── Shared UI helpers ─────────────────────────────────────────────────── */

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

  /* ── Render ─────────────────────────────────────────────────────────────── */

  return (
    <div className="p-6 max-w-2xl space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-stone-900">Dashboard</h1>
        <p className="text-sm text-stone-500 mt-1">
          Test your connected Google actions below.
        </p>
      </div>

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

"use client";

import { useState } from "react";
import { api } from "@/lib/api";

interface SendEmailResult {
  status: string;
  recipient: string;
  subject: string;
  gmail_message_id: string;
}

export default function DashboardPage() {
  const [recipient, setRecipient] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!recipient.trim() || !subject.trim() || !body.trim()) return;

    setSending(true);
    setResult(null);

    try {
      const data = await api.post<SendEmailResult>("/api/actions/send-email", {
        recipient: recipient.trim(),
        subject: subject.trim(),
        body: body.trim(),
      });
      setResult({
        type: "success",
        message: `Email sent to ${data.recipient} (ID: ${data.gmail_message_id})`,
      });
      setRecipient("");
      setSubject("");
      setBody("");
    } catch (err) {
      setResult({
        type: "error",
        message:
          err instanceof Error ? err.message : "Failed to send email",
      });
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="p-6 max-w-2xl">
      <h1 className="text-xl font-semibold text-stone-900">Dashboard</h1>
      <p className="text-sm text-stone-500 mt-1">
        Your workflows and activity will appear here.
      </p>

      {/* Send Test Email */}
      <div className="mt-8 rounded-lg border border-stone-200 bg-white p-6">
        <h2 className="text-lg font-semibold text-stone-900">
          Send Test Email
        </h2>
        <p className="text-sm text-stone-500 mt-1">
          Send an email through your connected Gmail account.
        </p>

        {result && (
          <div
            className={`mt-4 rounded-lg px-4 py-3 text-sm ${
              result.type === "success"
                ? "bg-green-50 text-green-800 border border-green-200"
                : "bg-red-50 text-red-800 border border-red-200"
            }`}
          >
            {result.message}
          </div>
        )}

        <form onSubmit={handleSend} className="mt-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-stone-700">
              To
            </label>
            <input
              type="email"
              value={recipient}
              onChange={(e) => setRecipient(e.target.value)}
              placeholder="test@example.com"
              required
              className="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-stone-700">
              Subject
            </label>
            <input
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="Welcome to our medspa!"
              required
              className="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-stone-700">
              Body
            </label>
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="Hi there! Thank you for booking with us..."
              required
              rows={4}
              className="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary resize-none"
            />
          </div>

          <button
            type="submit"
            disabled={sending || !recipient.trim() || !subject.trim() || !body.trim()}
            className="px-5 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {sending ? "Sending..." : "Send Email"}
          </button>
        </form>
      </div>
    </div>
  );
}

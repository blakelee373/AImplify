"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface IntegrationStatus {
  provider: string;
  status: string;
  scopes: string[];
  connected_at: string | null;
}

function IntegrationsContent() {
  const [integrations, setIntegrations] = useState<IntegrationStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [disconnecting, setDisconnecting] = useState<string | null>(null);
  const searchParams = useSearchParams();
  const justConnected = searchParams.get("status") === "success";

  useEffect(() => {
    fetchStatus();
  }, []);

  async function fetchStatus() {
    try {
      const data = await api.get<IntegrationStatus[]>(
        "/api/integrations/status"
      );
      setIntegrations(data);
    } catch {
      // Backend might not be reachable
    } finally {
      setLoading(false);
    }
  }

  async function handleDisconnect(provider: string) {
    setDisconnecting(provider);
    try {
      await api.post(`/api/integrations/${provider}/disconnect`, {});
      await fetchStatus();
    } catch {
      // Best effort
    } finally {
      setDisconnecting(null);
    }
  }

  const gmail = integrations.find((i) => i.provider === "gmail");
  const calendar = integrations.find((i) => i.provider === "google_calendar");
  const gmailConnected = gmail?.status === "connected";
  const calendarConnected = calendar?.status === "connected";

  return (
    <div className="p-6 max-w-2xl">
      <h1 className="text-xl font-semibold text-stone-900">
        Connected Accounts
      </h1>
      <p className="text-sm text-stone-500 mt-1">
        Connect your tools so AImplify can work with them.
      </p>

      {justConnected && (
        <div className="mt-4 bg-green-50 border border-green-200 rounded-lg px-4 py-3 text-sm text-green-700">
          Account connected successfully!
        </div>
      )}

      <div className="mt-6 space-y-4">
        {/* Gmail */}
        <div className="border border-stone-200 rounded-xl p-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-red-50 flex items-center justify-center text-lg">
                ✉
              </div>
              <div>
                <h3 className="font-medium text-stone-900">Gmail</h3>
                <p className="text-xs text-stone-500">
                  Send emails through your Google account
                </p>
              </div>
            </div>

            <span
              className={`text-xs font-medium px-2.5 py-1 rounded-full ${
                gmailConnected
                  ? "bg-green-100 text-green-700"
                  : "bg-stone-100 text-stone-500"
              }`}
            >
              {gmailConnected ? "Connected" : "Not connected"}
            </span>
          </div>

          <div className="mt-4">
            {gmailConnected ? (
              <button
                onClick={() => handleDisconnect("gmail")}
                disabled={disconnecting === "gmail"}
                className="px-4 py-2 text-sm rounded-lg border border-red-200 text-red-600 hover:bg-red-50 transition-colors disabled:opacity-50"
              >
                {disconnecting === "gmail" ? "Disconnecting..." : "Disconnect"}
              </button>
            ) : (
              <a
                href={`${API_URL}/api/integrations/gmail/connect`}
                className="inline-flex items-center px-4 py-2 text-sm rounded-lg bg-primary text-white font-semibold hover:bg-primary-hover transition-colors"
              >
                Connect Gmail
              </a>
            )}
          </div>
        </div>

        {/* Google Calendar */}
        <div className="border border-stone-200 rounded-xl p-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center text-lg">
                📅
              </div>
              <div>
                <h3 className="font-medium text-stone-900">Google Calendar</h3>
                <p className="text-xs text-stone-500">
                  Create events and check availability
                </p>
              </div>
            </div>

            <span
              className={`text-xs font-medium px-2.5 py-1 rounded-full ${
                calendarConnected
                  ? "bg-green-100 text-green-700"
                  : "bg-stone-100 text-stone-500"
              }`}
            >
              {calendarConnected ? "Connected" : "Not connected"}
            </span>
          </div>

          <div className="mt-4">
            {calendarConnected ? (
              <button
                onClick={() => handleDisconnect("google_calendar")}
                disabled={disconnecting === "google_calendar"}
                className="px-4 py-2 text-sm rounded-lg border border-red-200 text-red-600 hover:bg-red-50 transition-colors disabled:opacity-50"
              >
                {disconnecting === "google_calendar"
                  ? "Disconnecting..."
                  : "Disconnect"}
              </button>
            ) : (
              <a
                href={`${API_URL}/api/integrations/google_calendar/connect`}
                className="inline-flex items-center px-4 py-2 text-sm rounded-lg bg-primary text-white font-semibold hover:bg-primary-hover transition-colors"
              >
                Connect Google Calendar
              </a>
            )}
          </div>
        </div>
      </div>

      {loading && (
        <p className="mt-4 text-sm text-stone-400">Loading status...</p>
      )}
    </div>
  );
}

export default function IntegrationsPage() {
  return (
    <Suspense>
      <IntegrationsContent />
    </Suspense>
  );
}

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
  const [disconnecting, setDisconnecting] = useState(false);
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

  async function handleDisconnect() {
    setDisconnecting(true);
    try {
      await api.post("/api/integrations/google/disconnect", {});
      await fetchStatus();
    } catch {
      // Best effort
    } finally {
      setDisconnecting(false);
    }
  }

  const google = integrations.find((i) => i.provider === "google");
  const isConnected = google?.status === "connected";

  const scopeLabels: Record<string, string> = {
    "https://www.googleapis.com/auth/gmail.modify": "Gmail",
    "https://www.googleapis.com/auth/calendar": "Calendar",
    "https://www.googleapis.com/auth/userinfo.email": "Email",
    openid: "Sign-in",
  };

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
          Google account connected successfully!
        </div>
      )}

      <div className="mt-6 border border-stone-200 rounded-xl p-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-stone-100 flex items-center justify-center text-lg">
              G
            </div>
            <div>
              <h3 className="font-medium text-stone-900">Google</h3>
              <p className="text-xs text-stone-500">
                Gmail and Google Calendar access
              </p>
            </div>
          </div>

          <span
            className={`text-xs font-medium px-2.5 py-1 rounded-full ${
              isConnected
                ? "bg-green-100 text-green-700"
                : "bg-stone-100 text-stone-500"
            }`}
          >
            {isConnected ? "Connected" : "Not connected"}
          </span>
        </div>

        {isConnected && google?.scopes && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {google.scopes.map((scope) => (
              <span
                key={scope}
                className="text-xs bg-stone-50 text-stone-600 px-2 py-0.5 rounded"
              >
                {scopeLabels[scope] || scope}
              </span>
            ))}
          </div>
        )}

        <div className="mt-4">
          {isConnected ? (
            <button
              onClick={handleDisconnect}
              disabled={disconnecting}
              className="px-4 py-2 text-sm rounded-lg border border-red-200 text-red-600 hover:bg-red-50 transition-colors disabled:opacity-50"
            >
              {disconnecting ? "Disconnecting..." : "Disconnect"}
            </button>
          ) : (
            <a
              href={`${API_URL}/api/integrations/google/connect`}
              className="inline-flex items-center px-4 py-2 text-sm rounded-lg bg-primary text-white font-semibold hover:bg-primary-hover transition-colors"
            >
              Connect Google Account
            </a>
          )}
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

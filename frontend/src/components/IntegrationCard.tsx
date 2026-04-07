"use client";

import type { IntegrationInfo } from "@/lib/api";

interface IntegrationCardProps {
  integration: IntegrationInfo;
  onConnect: () => void;
  onDisconnect: () => void;
  onTest: () => void;
  loading?: boolean;
}

const ICONS: Record<string, string> = {
  google_calendar: "📅",
  gmail: "✉️",
  twilio_sms: "💬",
};

const STATUS_STYLES: Record<string, { dot: string; label: string; labelColor: string }> = {
  connected: { dot: "bg-emerald-500", label: "Connected", labelColor: "text-emerald-700" },
  disconnected: { dot: "bg-gray-300", label: "Not connected", labelColor: "text-text-muted" },
  error: { dot: "bg-red-500", label: "Reconnection needed", labelColor: "text-red-600" },
  expired: { dot: "bg-red-500", label: "Reconnection needed", labelColor: "text-red-600" },
};

export function IntegrationCard({
  integration,
  onConnect,
  onDisconnect,
  onTest,
  loading,
}: IntegrationCardProps) {
  const icon = ICONS[integration.name] || "🔌";
  const status = STATUS_STYLES[integration.status] || STATUS_STYLES.disconnected;
  const isConnected = integration.status === "connected";
  const needsReconnect = integration.status === "error" || integration.status === "expired";

  return (
    <div className="bg-surface border border-border rounded-xl p-5 flex flex-col gap-4 shadow-sm">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <span className="text-3xl">{icon}</span>
          <div>
            <h3 className="font-semibold text-foreground">{integration.display_name}</h3>
            <p className="text-sm text-text-muted">{integration.description}</p>
          </div>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <span className={`w-2 h-2 rounded-full ${status.dot}`} />
          <span className={`text-xs font-medium ${status.labelColor}`}>{status.label}</span>
        </div>
      </div>

      <div className="flex gap-2 mt-auto">
        {isConnected ? (
          <>
            <button
              onClick={onTest}
              disabled={loading}
              className="px-3 py-1.5 text-sm font-medium rounded-lg border border-border hover:bg-background transition-colors disabled:opacity-50"
            >
              Test Connection
            </button>
            <button
              onClick={onDisconnect}
              disabled={loading}
              className="px-3 py-1.5 text-sm font-medium rounded-lg text-red-600 border border-red-200 hover:bg-red-50 transition-colors disabled:opacity-50"
            >
              Disconnect
            </button>
          </>
        ) : (
          <button
            onClick={onConnect}
            disabled={loading}
            className="px-4 py-2 text-sm font-semibold rounded-lg bg-primary text-white hover:bg-primary-hover transition-colors disabled:opacity-50"
          >
            {needsReconnect ? "Reconnect" : "Connect"}
          </button>
        )}
      </div>
    </div>
  );
}

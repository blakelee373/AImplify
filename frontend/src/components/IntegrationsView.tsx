"use client";

import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { IntegrationCard } from "@/components/IntegrationCard";
import { TwilioSetupModal } from "@/components/TwilioSetupModal";
import {
  api,
  fetchIntegrations,
  connectGoogle,
  connectTwilio,
  disconnectIntegration,
  testIntegration,
  type IntegrationInfo,
} from "@/lib/api";

export function IntegrationsView() {
  const searchParams = useSearchParams();
  const justConnected = searchParams.get("connected");

  const [integrations, setIntegrations] = useState<IntegrationInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [twilioOpen, setTwilioOpen] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  useEffect(() => {
    loadIntegrations();
  }, []);

  useEffect(() => {
    if (justConnected === "google") {
      setSuccessMsg("Google account connected successfully!");
      loadIntegrations();
    }
  }, [justConnected]);

  async function loadIntegrations() {
    try {
      const data = await fetchIntegrations();
      setIntegrations(data);
    } catch {
      // Silently fail — page still shows cards in disconnected state
    }
  }

  async function handleConnect(name: string) {
    setLoading(true);
    try {
      if (name === "google_calendar" || name === "gmail" || name === "google_reviews") {
        const data = await connectGoogle();
        window.location.href = data.auth_url;
      } else if (name === "twilio_sms") {
        setTwilioOpen(true);
      } else if (name === "stripe" || name === "square_appointments" || name === "boulevard" || name === "hubspot") {
        // API key integrations — use the same TwilioSetupModal pattern with a generic prompt
        const key = prompt(`Enter your ${name.replace("_", " ")} API key:`);
        if (key) {
          const endpoint = name === "stripe" ? "stripe" : name === "square_appointments" ? "square" : name;
          await api.post(`/api/integrations/connect/${endpoint}`, { secret_key: key, api_key: key });
          setSuccessMsg(`${name.replace("_", " ")} connected!`);
          await loadIntegrations();
        }
      }
    } catch {
      setSuccessMsg("Failed to connect. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  async function handleTwilioSubmit(creds: {
    account_sid: string;
    auth_token: string;
    phone_number: string;
  }) {
    setLoading(true);
    try {
      await connectTwilio(creds);
      setTwilioOpen(false);
      setSuccessMsg("Twilio SMS connected successfully!");
      await loadIntegrations();
    } catch {
      setSuccessMsg("Invalid Twilio credentials. Please check and try again.");
    } finally {
      setLoading(false);
    }
  }

  async function handleDisconnect(name: string) {
    if (!confirm("Disconnect this integration? Active tasks using it will stop working.")) return;
    setLoading(true);
    try {
      await disconnectIntegration(name);
      setSuccessMsg("Disconnected.");
      await loadIntegrations();
    } finally {
      setLoading(false);
    }
  }

  async function handleTest(name: string) {
    setLoading(true);
    try {
      const result = await testIntegration(name);
      setSuccessMsg(
        result.connected ? "Connection is working!" : "Connection test failed. Try reconnecting."
      );
    } catch {
      setSuccessMsg("Connection test failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-full bg-background">
      <div className="max-w-4xl mx-auto px-6 py-10">
        {/* Header */}
        <div className="flex items-center gap-3 mb-1">
          <Link
            href="/chat"
            className="text-text-muted hover:text-foreground transition-colors"
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M12 4l-6 6 6 6" />
            </svg>
          </Link>
          <h1 className="text-2xl font-bold text-foreground">Connected Tools</h1>
        </div>
        <p className="text-text-muted mb-8 ml-8">
          Connect the tools your business already uses. AImplify works across all of them.
        </p>

        {/* Success message */}
        {successMsg && (
          <div className="mb-6 px-4 py-3 rounded-lg bg-primary-light border border-primary/20 text-sm text-foreground flex items-center justify-between">
            <span>{successMsg}</span>
            <button onClick={() => setSuccessMsg(null)} className="text-text-muted hover:text-foreground">
              ✕
            </button>
          </div>
        )}

        {/* Integration cards */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {integrations.map((int) => (
            <IntegrationCard
              key={int.name}
              integration={int}
              onConnect={() => handleConnect(int.name)}
              onDisconnect={() => handleDisconnect(int.name)}
              onTest={() => handleTest(int.name)}
              loading={loading}
            />
          ))}
        </div>

        {integrations.length === 0 && (
          <div className="text-center py-20 text-text-muted">
            Loading integrations...
          </div>
        )}
      </div>

      <TwilioSetupModal
        open={twilioOpen}
        onClose={() => setTwilioOpen(false)}
        onSubmit={handleTwilioSubmit}
        loading={loading}
      />
    </div>
  );
}

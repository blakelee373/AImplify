"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { api, testWorkflow, activateWorkflow, type WorkflowTestResult } from "@/lib/api";
import { MessagePreview } from "@/components/dashboard/MessagePreview";
import { ActivityEntry } from "@/components/dashboard/ActivityEntry";
import { WorkflowTestResults } from "@/components/WorkflowTestResults";
import { ConfirmationModal } from "@/components/ConfirmationModal";
import { friendlyDateTime } from "@/lib/time";

interface WorkflowDetailData {
  id: string;
  name: string;
  description: string | null;
  status: string;
  created_at: string;
  trigger: { type: string | null; description: string; config: unknown };
  steps: {
    step_order: number;
    action_type: string;
    description: string;
    message_preview: { template: string; example: string };
    integration_required: string | null;
    integration_connected: boolean;
  }[];
  conditions: string[];
  stats: {
    total_runs: number;
    successful_runs: number;
    failed_runs: number;
    last_run_at: string | null;
    runs_today: number;
    runs_this_week: number;
  };
  recent_executions: {
    id: string;
    started_at: string;
    completed_at: string | null;
    status: string;
    trigger_context_summary: string;
    results: { step_order: number; action_type: string; success: boolean; description: string }[];
    error: string | null;
  }[];
}

const STATUS_BADGES: Record<string, { bg: string; text: string; label: string }> = {
  active: { bg: "bg-emerald-100", text: "text-emerald-700", label: "Active" },
  testing: { bg: "bg-amber-100", text: "text-amber-700", label: "Testing" },
  paused: { bg: "bg-gray-100", text: "text-gray-600", label: "Paused" },
  draft: { bg: "bg-blue-100", text: "text-blue-700", label: "Draft" },
};

const TRIGGER_ICONS: Record<string, string> = {
  event_based: "📅",
  time_based: "⏰",
  condition_based: "🔀",
};

export default function WorkflowDetailPage() {
  const params = useParams();
  const router = useRouter();
  const workflowId = params.id as string;

  const [data, setData] = useState<WorkflowDetailData | null>(null);
  const [testResult, setTestResult] = useState<WorkflowTestResult | null>(null);
  const [modal, setModal] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.get<WorkflowDetailData>(`/api/workflows/${workflowId}/detail`)
      .then(setData)
      .catch(() => router.push("/dashboard"));
  }, [workflowId, router]);

  const handleStatusChange = useCallback(async (newStatus: string) => {
    setLoading(true);
    try {
      await api.patch(`/api/workflows/${workflowId}`, { status: newStatus });
      setData((d) => d ? { ...d, status: newStatus } : d);
      setModal(null);
    } finally {
      setLoading(false);
    }
  }, [workflowId]);

  async function handleTest() {
    setLoading(true);
    try {
      const result = await testWorkflow(workflowId);
      setTestResult(result);
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete() {
    setLoading(true);
    try {
      await api.delete(`/api/workflows/${workflowId}`);
      router.push("/dashboard");
    } finally {
      setLoading(false);
    }
  }

  if (!data) {
    return (
      <div className="max-w-4xl mx-auto px-6 py-10">
        <div className="h-8 w-64 bg-border rounded-lg animate-pulse mb-4" />
        <div className="h-40 bg-border rounded-xl animate-pulse" />
      </div>
    );
  }

  const badge = STATUS_BADGES[data.status] || STATUS_BADGES.draft;
  const triggerIcon = TRIGGER_ICONS[data.trigger.type || ""] || "⚡";

  return (
    <div className="max-w-4xl mx-auto px-6 py-10 space-y-8">
      {/* Breadcrumbs */}
      <nav className="text-sm text-text-muted">
        <Link href="/dashboard" className="hover:text-primary">Dashboard</Link>
        <span className="mx-2">›</span>
        <span className="text-foreground">{data.name}</span>
      </nav>

      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-2xl font-bold text-foreground">{data.name}</h1>
            <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${badge.bg} ${badge.text}`}>
              {badge.label}
            </span>
          </div>
          {data.description && <p className="text-text-muted">{data.description}</p>}
          <p className="text-xs text-text-muted mt-2">
            Set up on {new Date(data.created_at).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })}
          </p>
        </div>

        {/* Controls */}
        <div className="flex gap-2 shrink-0">
          <button onClick={handleTest} disabled={loading} className="px-4 py-2 text-sm font-medium rounded-lg border border-border hover:bg-background transition-colors disabled:opacity-50">
            Test
          </button>
          {data.status === "active" && (
            <button onClick={() => setModal("pause")} className="px-4 py-2 text-sm font-semibold rounded-lg bg-amber-500 text-white hover:bg-amber-600 transition-colors">
              Pause
            </button>
          )}
          {(data.status === "paused" || data.status === "testing" || data.status === "draft") && (
            <button onClick={() => setModal("activate")} className="px-4 py-2 text-sm font-semibold rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 transition-colors">
              {data.status === "paused" ? "Resume" : "Turn On"}
            </button>
          )}
          <Link href={`/chat?edit=${workflowId}`} className="px-4 py-2 text-sm font-medium rounded-lg border border-border hover:bg-background transition-colors">
            Edit
          </Link>
        </div>
      </div>

      {/* Test results */}
      {testResult && (
        <WorkflowTestResults
          result={testResult}
          onActivate={() => handleStatusChange("active")}
          onAdjust={() => router.push(`/chat?edit=${workflowId}`)}
          loading={loading}
        />
      )}

      {/* How it works */}
      <section className="bg-surface rounded-xl border border-border p-6 space-y-4">
        <h2 className="font-semibold text-foreground">How This Worker Works</h2>

        <div className="space-y-2 text-sm">
          <div className="flex gap-2">
            <span>{triggerIcon}</span>
            <span><strong>When:</strong> {data.trigger.description}</span>
          </div>
        </div>

        {data.steps.map((step) => (
          <div key={step.step_order} className="space-y-2">
            <div className="flex items-center gap-2 text-sm">
              <span className="w-5 h-5 rounded-full bg-primary/10 text-primary text-xs font-bold flex items-center justify-center">
                {step.step_order}
              </span>
              <span className="font-medium">{step.description}</span>
              {step.integration_required && !step.integration_connected && (
                <Link href="/integrations" className="text-xs text-red-500 hover:underline">
                  (needs connection)
                </Link>
              )}
            </div>
            {step.message_preview.example && (
              <div className="ml-7">
                <MessagePreview
                  template={step.message_preview.template}
                  example={step.message_preview.example}
                  actionType={step.action_type}
                />
              </div>
            )}
          </div>
        ))}

        {data.conditions.length > 0 && (
          <div className="text-sm text-text-muted pt-2 border-t border-border">
            <strong>Conditions:</strong> {data.conditions.join(", ")}
          </div>
        )}
      </section>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-surface border border-border rounded-xl p-4 text-center">
          <div className="text-2xl font-bold text-foreground">{data.stats.total_runs}</div>
          <div className="text-xs text-text-muted">total runs</div>
        </div>
        <div className="bg-surface border border-border rounded-xl p-4 text-center">
          <div className="text-2xl font-bold text-emerald-600">{data.stats.successful_runs}</div>
          <div className="text-xs text-text-muted">successful</div>
        </div>
        <div className="bg-surface border border-border rounded-xl p-4 text-center">
          <div className="text-2xl font-bold text-red-500">{data.stats.failed_runs}</div>
          <div className="text-xs text-text-muted">failed</div>
        </div>
        <div className="bg-surface border border-border rounded-xl p-4 text-center">
          <div className="text-2xl font-bold text-foreground">{data.stats.runs_this_week}</div>
          <div className="text-xs text-text-muted">this week</div>
        </div>
      </div>

      {/* Execution history */}
      <section>
        <h2 className="font-semibold text-foreground mb-3">Recent Activity</h2>
        {data.recent_executions.length === 0 ? (
          <p className="text-sm text-text-muted py-8 text-center bg-surface rounded-xl border border-border">
            This worker hasn&apos;t run yet. It will start automatically when the trigger conditions are met.
          </p>
        ) : (
          <div className="bg-surface rounded-xl border border-border divide-y divide-border px-4">
            {data.recent_executions.map((ex) => (
              <div key={ex.id} className="py-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium text-foreground">{ex.trigger_context_summary}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    ex.status === "completed" ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"
                  }`}>
                    {ex.status}
                  </span>
                </div>
                <p className="text-xs text-text-muted">{friendlyDateTime(ex.started_at)}</p>
                {ex.error && <p className="text-xs text-red-600 mt-1">{ex.error}</p>}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Delete */}
      <div className="border-t border-border pt-6">
        <button onClick={() => setModal("delete")} className="text-sm text-red-500 hover:text-red-700 transition-colors">
          Delete this worker
        </button>
      </div>

      {/* Modals */}
      <ConfirmationModal
        open={modal === "activate"}
        title="Turn on this worker?"
        message="This will start running for real. Your clients will receive actual messages."
        confirmLabel="Yes, turn it on"
        confirmColor="bg-emerald-600 hover:bg-emerald-700"
        onConfirm={() => handleStatusChange("active")}
        onCancel={() => setModal(null)}
        loading={loading}
      />
      <ConfirmationModal
        open={modal === "pause"}
        title="Pause this worker?"
        message="This will stop running until you turn it back on. Any tasks already in progress will finish."
        confirmLabel="Pause"
        confirmColor="bg-amber-500 hover:bg-amber-600"
        onConfirm={() => handleStatusChange("paused")}
        onCancel={() => setModal(null)}
        loading={loading}
      />
      <ConfirmationModal
        open={modal === "delete"}
        title="Delete this worker?"
        message="This will permanently remove this AI worker and all its history. This can't be undone."
        confirmLabel="Delete"
        confirmColor="bg-red-600 hover:bg-red-700"
        onConfirm={handleDelete}
        onCancel={() => setModal(null)}
        loading={loading}
      />
    </div>
  );
}

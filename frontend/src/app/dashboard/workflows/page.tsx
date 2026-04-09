"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { WorkflowCard } from "@/components/WorkflowCard";

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
  trigger_config?: Record<string, string> | null;
  steps: WorkflowStep[];
  created_at: string;
  updated_at: string;
  next_run_at?: string | null;
  last_run_at?: string | null;
}

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<WorkflowItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchWorkflows();
  }, []);

  async function fetchWorkflows() {
    setLoading(true);
    try {
      const data = await api.get<WorkflowItem[]>("/api/workflows");
      setWorkflows(data);
    } catch {
      setWorkflows([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 max-w-2xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-stone-900">Workflows</h1>
          <p className="text-sm text-stone-500 mt-1">
            All your saved workflows at a glance.
          </p>
        </div>
        <button
          onClick={fetchWorkflows}
          disabled={loading}
          className="text-sm text-primary hover:text-primary-hover font-medium"
        >
          {loading ? "Loading..." : "Refresh"}
        </button>
      </div>

      {loading && workflows.length === 0 && (
        <p className="text-sm text-stone-400">Loading workflows...</p>
      )}

      {!loading && workflows.length === 0 && (
        <div className="rounded-lg border border-stone-200 bg-white p-8 text-center">
          <p className="text-sm text-stone-500">
            No workflows yet.{" "}
            <Link href="/chat" className="text-primary hover:text-primary-hover font-medium">
              Go to Chat
            </Link>{" "}
            and describe a task to create one.
          </p>
        </div>
      )}

      <div className="space-y-3">
        {workflows.map((wf) => (
          <WorkflowCard key={wf.id} workflow={wf} />
        ))}
      </div>
    </div>
  );
}

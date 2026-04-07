"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { StatusBar } from "@/components/dashboard/StatusBar";
import { StatsGrid } from "@/components/dashboard/StatsGrid";
import { WorkflowCard } from "@/components/dashboard/WorkflowCard";
import { ActivityEntry } from "@/components/dashboard/ActivityEntry";

interface DashboardSummary {
  greeting_time: string;
  status: string;
  status_message: string;
  attention_items: { type: string; message: string; action_url: string }[];
  stats: {
    active_workflows: number;
    tasks_completed_today: number;
    tasks_completed_this_week: number;
    errors_today: number;
  };
  workflows: {
    id: string;
    name: string;
    description: string | null;
    status: string;
    primary_action_type: string;
    last_run_at: string | null;
    run_count_today: number;
    run_count_total: number;
    has_errors: boolean;
  }[];
  recent_activity: {
    id: string;
    action_type: string;
    description: string;
    workflow_name: string | null;
    timestamp: string;
    success: boolean;
  }[];
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardSummary | null>(null);

  useEffect(() => {
    api.get<DashboardSummary>("/api/dashboard/summary")
      .then(setData)
      .catch(() => {});
  }, []);

  if (!data) {
    return (
      <div className="max-w-5xl mx-auto px-6 py-10 space-y-6">
        <div className="h-8 w-48 bg-border rounded-lg animate-pulse" />
        <div className="h-16 bg-border rounded-xl animate-pulse" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[0, 1, 2, 3].map((i) => <div key={i} className="h-28 bg-border rounded-xl animate-pulse" />)}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-10 space-y-8">
      <StatusBar
        greetingTime={data.greeting_time}
        status={data.status}
        statusMessage={data.status_message}
        attentionItems={data.attention_items}
      />

      <StatsGrid />

      {/* AI Workers */}
      <section>
        <h2 className="text-lg font-semibold text-foreground mb-4">Your AI Workers</h2>
        {data.workflows.length === 0 ? (
          <div className="text-center py-16 bg-surface rounded-xl border border-border">
            <p className="text-text-muted mb-4">No AI workers yet. Head to the chat to set one up!</p>
            <Link
              href="/chat"
              className="inline-block px-5 py-2 bg-primary text-white text-sm font-semibold rounded-lg hover:bg-primary-hover transition-colors"
            >
              Start Chatting
            </Link>
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {data.workflows.map((w) => (
              <WorkflowCard
                key={w.id}
                id={w.id}
                name={w.name}
                description={w.description}
                status={w.status}
                primaryActionType={w.primary_action_type}
                lastRunAt={w.last_run_at}
                runCountToday={w.run_count_today}
                hasErrors={w.has_errors}
              />
            ))}
          </div>
        )}
      </section>

      {/* Recent Activity */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-foreground">Recent Activity</h2>
          <Link href="/dashboard/activity" className="text-sm text-primary font-medium hover:underline">
            See all activity →
          </Link>
        </div>
        {data.recent_activity.length === 0 ? (
          <p className="text-sm text-text-muted py-8 text-center">
            No activity yet. Once your AI workers start running, you&apos;ll see everything they do here.
          </p>
        ) : (
          <div className="bg-surface rounded-xl border border-border divide-y divide-border px-4">
            {data.recent_activity.map((a) => (
              <ActivityEntry
                key={a.id}
                actionType={a.action_type}
                description={a.description}
                workflowName={a.workflow_name}
                timestamp={a.timestamp}
                success={a.success}
                compact
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

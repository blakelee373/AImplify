"use client";

import { useState, useEffect } from "react";
import { StatCard } from "./StatCard";
import { api } from "@/lib/api";

interface StatsData {
  tasks_completed: number;
  tasks_change_percent: number;
  messages_sent: { total: number; sms: number; email: number };
  estimated_time_saved_minutes: number;
  success_rate: number;
}

export function StatsGrid() {
  const [stats, setStats] = useState<StatsData | null>(null);

  useEffect(() => {
    api.get<StatsData>("/api/dashboard/stats?period=this_week")
      .then(setStats)
      .catch(() => {});
  }, []);

  if (!stats) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="bg-surface border border-border rounded-xl p-4 h-28 animate-pulse" />
        ))}
      </div>
    );
  }

  const hours = (stats.estimated_time_saved_minutes / 60).toFixed(1);

  const successColor =
    stats.success_rate >= 90
      ? "text-emerald-600"
      : stats.success_rate >= 75
        ? "text-amber-600"
        : "text-red-600";

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      <StatCard
        icon="✓"
        value={String(stats.tasks_completed)}
        label="tasks this week"
        changePercent={stats.tasks_change_percent}
      />
      <StatCard
        icon="💬"
        value={String(stats.messages_sent.total)}
        label="messages sent"
        detail={`${stats.messages_sent.sms} texts, ${stats.messages_sent.email} emails`}
      />
      <StatCard
        icon="⏱"
        value={`${hours} hrs`}
        label="estimated time saved"
      />
      <StatCard
        icon="🎯"
        value={`${stats.success_rate}%`}
        label="success rate"
        colorClass={successColor}
      />
    </div>
  );
}

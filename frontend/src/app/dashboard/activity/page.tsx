"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { ActivityEntry } from "@/components/dashboard/ActivityEntry";
import { friendlyDate } from "@/lib/time";

interface ActivityItem {
  id: string;
  action_type: string;
  description: string;
  workflow_id: string | null;
  workflow_name: string | null;
  details: unknown;
  success: boolean;
  friendly_error: string | null;
  created_at: string;
}

interface ActivityResponse {
  items: ActivityItem[];
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
}

const FILTERS = [
  { key: "", label: "All" },
  { key: "sms", label: "Texts" },
  { key: "email", label: "Emails" },
  { key: "calendar", label: "Calendar" },
  { key: "errors", label: "Errors" },
];

export default function ActivityPage() {
  const [items, setItems] = useState<ActivityItem[]>([]);
  const [filter, setFilter] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(false);
  const [errorCount, setErrorCount] = useState(0);

  const loadPage = useCallback(async (p: number, f: string) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(p), per_page: "20" });
      if (f) params.set("action_type", f);
      const data = await api.get<ActivityResponse>(`/api/activity?${params}`);
      if (p === 1) {
        setItems(data.items);
      } else {
        setItems((prev) => [...prev, ...data.items]);
      }
      setTotalPages(data.total_pages);
    } finally {
      setLoading(false);
    }
  }, []);

  // Load error count for badge
  useEffect(() => {
    api.get<ActivityResponse>("/api/activity?action_type=errors&per_page=1")
      .then((d) => setErrorCount(d.total))
      .catch(() => {});
  }, []);

  useEffect(() => {
    setPage(1);
    loadPage(1, filter);
  }, [filter, loadPage]);

  function handleLoadMore() {
    const next = page + 1;
    setPage(next);
    loadPage(next, filter);
  }

  // Group items by date
  const groups: { date: string; items: ActivityItem[] }[] = [];
  let currentDate = "";
  for (const item of items) {
    const d = new Date(item.created_at).toDateString();
    if (d !== currentDate) {
      currentDate = d;
      groups.push({ date: item.created_at, items: [] });
    }
    groups[groups.length - 1].items.push(item);
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-10 space-y-6">
      {/* Breadcrumbs */}
      <nav className="text-sm text-text-muted">
        <Link href="/dashboard" className="hover:text-primary">Dashboard</Link>
        <span className="mx-2">›</span>
        <span className="text-foreground">Activity</span>
      </nav>

      <div>
        <h1 className="text-2xl font-bold text-foreground">Activity</h1>
        <p className="text-text-muted text-sm mt-1">Everything your AI workers have done</p>
      </div>

      {/* Filters */}
      <div className="flex gap-2 flex-wrap">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
              filter === f.key
                ? "bg-primary text-white"
                : "bg-surface border border-border text-text-muted hover:border-primary/30"
            }`}
          >
            {f.label}
            {f.key === "errors" && errorCount > 0 && (
              <span className="ml-1.5 px-1.5 py-0.5 rounded-full text-xs bg-red-500 text-white">
                {errorCount}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Grouped entries */}
      {items.length === 0 && !loading ? (
        <p className="text-sm text-text-muted py-16 text-center">
          {filter
            ? "No matching activity found."
            : "No activity yet. Once your AI workers start running, you'll see everything they do here."}
        </p>
      ) : (
        <div className="space-y-6">
          {groups.map((group) => (
            <div key={group.date}>
              <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-2">
                {friendlyDate(group.date)}
              </h3>
              <div className="bg-surface rounded-xl border border-border divide-y divide-border px-4">
                {group.items.map((item) => (
                  <ActivityEntry
                    key={item.id}
                    actionType={item.action_type}
                    description={item.description}
                    workflowName={item.workflow_name}
                    timestamp={item.created_at}
                    success={item.success}
                    friendlyError={item.friendly_error}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Load more */}
      {page < totalPages && (
        <div className="text-center">
          <button
            onClick={handleLoadMore}
            disabled={loading}
            className="px-5 py-2 text-sm font-medium rounded-lg border border-border hover:bg-background transition-colors disabled:opacity-50"
          >
            {loading ? "Loading..." : "Load more"}
          </button>
        </div>
      )}
    </div>
  );
}

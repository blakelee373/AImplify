"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { ChainTimeline } from "@/components/dashboard/ChainTimeline";
import { ConfirmationModal } from "@/components/ConfirmationModal";

interface ChainDetail {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  workflows: {
    id: string;
    name: string;
    description: string | null;
    position: number;
    delay_after_previous: number;
    condition_from_previous: string | null;
    status: string;
    last_run_at: string | null;
  }[];
}

export default function ChainDetailPage() {
  const params = useParams();
  const router = useRouter();
  const chainId = params.id as string;

  const [data, setData] = useState<ChainDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [modal, setModal] = useState<string | null>(null);

  useEffect(() => {
    api.get<ChainDetail>(`/api/chains/${chainId}`)
      .then(setData)
      .catch(() => router.push("/dashboard"));
  }, [chainId, router]);

  async function handlePauseAll() {
    setLoading(true);
    try {
      await api.patch(`/api/chains/${chainId}`, { pause_all: true });
      const updated = await api.get<ChainDetail>(`/api/chains/${chainId}`);
      setData(updated);
      setModal(null);
    } finally {
      setLoading(false);
    }
  }

  async function handleResumeAll() {
    setLoading(true);
    try {
      await api.patch(`/api/chains/${chainId}`, { resume_all: true });
      const updated = await api.get<ChainDetail>(`/api/chains/${chainId}`);
      setData(updated);
      setModal(null);
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete() {
    setLoading(true);
    try {
      await api.delete(`/api/chains/${chainId}?delete_workflows=true`);
      router.push("/dashboard");
    } finally {
      setLoading(false);
    }
  }

  if (!data) {
    return (
      <div className="max-w-4xl mx-auto px-6 py-10">
        <div className="h-8 w-64 bg-border rounded-lg animate-pulse mb-4" />
        <div className="h-60 bg-border rounded-xl animate-pulse" />
      </div>
    );
  }

  const hasActive = data.workflows.some((w) => w.status === "active");
  const hasPaused = data.workflows.some((w) => w.status === "paused");

  return (
    <div className="max-w-4xl mx-auto px-6 py-10 space-y-8">
      <nav className="text-sm text-text-muted">
        <Link href="/dashboard" className="hover:text-primary">Dashboard</Link>
        <span className="mx-2">›</span>
        <span className="text-foreground">{data.name}</span>
      </nav>

      <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="text-2xl">🔗</span>
            <h1 className="text-2xl font-bold text-foreground">{data.name}</h1>
          </div>
          {data.description && <p className="text-text-muted">{data.description}</p>}
          <p className="text-xs text-text-muted mt-2">
            {data.workflows.length} steps • Created {new Date(data.created_at).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })}
          </p>
        </div>

        <div className="flex gap-2 shrink-0">
          {hasActive && (
            <button onClick={() => setModal("pause")} className="px-4 py-2 text-sm font-semibold rounded-lg bg-amber-500 text-white hover:bg-amber-600 transition-colors">
              Pause All
            </button>
          )}
          {hasPaused && (
            <button onClick={handleResumeAll} className="px-4 py-2 text-sm font-semibold rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 transition-colors">
              Resume All
            </button>
          )}
        </div>
      </div>

      <ChainTimeline workflows={data.workflows} />

      <div className="border-t border-border pt-6">
        <button onClick={() => setModal("delete")} className="text-sm text-red-500 hover:text-red-700 transition-colors">
          Delete this journey
        </button>
      </div>

      <ConfirmationModal
        open={modal === "pause"}
        title="Pause entire journey?"
        message="All steps in this journey will be paused until you resume them."
        confirmLabel="Pause All"
        confirmColor="bg-amber-500 hover:bg-amber-600"
        onConfirm={handlePauseAll}
        onCancel={() => setModal(null)}
        loading={loading}
      />
      <ConfirmationModal
        open={modal === "delete"}
        title="Delete this journey?"
        message="This will remove the journey and all its steps. This can't be undone."
        confirmLabel="Delete"
        confirmColor="bg-red-600 hover:bg-red-700"
        onConfirm={handleDelete}
        onCancel={() => setModal(null)}
        loading={loading}
      />
    </div>
  );
}

"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { timeAgo } from "@/lib/workflow-utils";
import { Plus, Search, Trash2, MessageSquare } from "lucide-react";

interface ConversationSummary {
  id: number;
  title: string | null;
  created_at: string;
  updated_at: string;
}

interface ConversationListProps {
  activeId: number | null;
  onSelect: (id: number) => void;
  onNew: () => void;
  refreshKey: number;
}

export function ConversationList({
  activeId,
  onSelect,
  onNew,
  refreshKey,
}: ConversationListProps) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);

  useEffect(() => {
    fetchConversations();
  }, [refreshKey]);

  async function fetchConversations() {
    setLoading(true);
    try {
      const data = await api.get<ConversationSummary[]>("/api/conversations");
      setConversations(data);
    } catch {
      setConversations([]);
    } finally {
      setLoading(false);
    }
  }

  const [deleteError, setDeleteError] = useState<string | null>(null);

  async function handleDelete(id: number) {
    setDeletingId(id);
    setDeleteError(null);
    try {
      await api.delete(`/api/conversations/${id}`);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      setConfirmDeleteId(null);
      if (activeId === id) {
        onNew();
      }
    } catch {
      setDeleteError("Failed to delete. Try again.");
      setConfirmDeleteId(null);
    } finally {
      setDeletingId(null);
    }
  }

  const filtered = search.trim()
    ? conversations.filter((c) =>
        (c.title || "").toLowerCase().includes(search.toLowerCase()),
      )
    : conversations;

  return (
    <div className="flex flex-col h-full bg-stone-50 border-r border-stone-200">
      {/* Header */}
      <div className="px-4 py-4 border-b border-stone-200">
        <button
          onClick={onNew}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-hover transition-colors"
        >
          <Plus className="w-4 h-4" />
          New conversation
        </button>
      </div>

      {/* Search */}
      <div className="px-4 py-3 border-b border-stone-200">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-stone-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search conversations..."
            className="w-full pl-9 pr-3 py-2 rounded-lg border border-stone-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary bg-white"
          />
        </div>
      </div>

      {/* Error banner */}
      {deleteError && (
        <div className="mx-4 mt-3 px-3 py-2 rounded-lg bg-red-50 text-red-700 text-xs border border-red-200">
          {deleteError}
        </div>
      )}

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto">
        {loading && conversations.length === 0 && (
          <div className="px-4 py-8 text-center text-sm text-stone-400">
            Loading...
          </div>
        )}

        {!loading && filtered.length === 0 && (
          <div className="px-4 py-8 text-center text-sm text-stone-400">
            {search.trim()
              ? "No conversations match your search."
              : "No conversations yet. Start a new one!"}
          </div>
        )}

        <div className="py-2">
          {filtered.map((conv) => {
            const isActive = conv.id === activeId;
            const isConfirming = confirmDeleteId === conv.id;

            return (
              <div
                key={conv.id}
                className={`group relative mx-2 mb-0.5 rounded-lg transition-colors ${
                  isActive
                    ? "bg-primary/10 border border-primary/20"
                    : "hover:bg-stone-100 border border-transparent"
                }`}
              >
                {isConfirming ? (
                  /* Delete confirmation replaces the entire row */
                  <div className="flex items-center justify-between px-3 py-3">
                    <span className="text-xs text-stone-600 font-medium truncate mr-2">
                      Delete this conversation?
                    </span>
                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        onClick={() => handleDelete(conv.id)}
                        disabled={deletingId === conv.id}
                        className="px-2 py-1 rounded text-xs font-medium bg-red-500 text-white hover:bg-red-600 transition-colors disabled:opacity-50"
                      >
                        {deletingId === conv.id ? "..." : "Delete"}
                      </button>
                      <button
                        onClick={() => setConfirmDeleteId(null)}
                        className="px-2 py-1 rounded text-xs font-medium bg-stone-200 text-stone-600 hover:bg-stone-300 transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  /* Normal conversation row */
                  <button
                    onClick={() => onSelect(conv.id)}
                    className="w-full text-left px-3 py-3"
                  >
                    <div className="flex items-start gap-2.5">
                      <MessageSquare
                        className={`w-4 h-4 shrink-0 mt-0.5 ${
                          isActive ? "text-primary" : "text-stone-400"
                        }`}
                      />
                      <div className="flex-1 min-w-0">
                        <p
                          className={`text-sm font-medium truncate ${
                            isActive ? "text-stone-900" : "text-stone-700"
                          }`}
                        >
                          {conv.title || "New conversation"}
                        </p>
                        <p className="text-xs text-stone-400 mt-0.5">
                          {timeAgo(conv.updated_at)}
                        </p>
                      </div>
                    </div>
                  </button>
                )}

                {/* Trash icon (only visible on hover, hidden during confirmation) */}
                {!isConfirming && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setConfirmDeleteId(conv.id);
                    }}
                    className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-md text-stone-400 hover:text-red-500 hover:bg-stone-200 opacity-0 group-hover:opacity-100 transition-all z-10"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

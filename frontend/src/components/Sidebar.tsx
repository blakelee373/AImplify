"use client";

import Link from "next/link";
import type { ConversationSummary } from "@/lib/api";

interface SidebarProps {
  conversations: ConversationSummary[];
  activeId: string | null;
  isOpen: boolean;
  onSelect: (id: string) => void;
  onNew: () => void;
  onClose: () => void;
}

function formatDate(dateStr: string) {
  const d = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays}d ago`;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function Sidebar({
  conversations,
  activeId,
  isOpen,
  onSelect,
  onNew,
  onClose,
}: SidebarProps) {
  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={`
          fixed md:relative z-50 md:z-auto
          w-[280px] h-full bg-sidebar-bg text-sidebar-text
          flex flex-col shrink-0
          transition-transform duration-200 ease-in-out
          ${isOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"}
        `}
      >
        {/* Logo */}
        <div className="px-5 py-5 flex items-center gap-2">
          <span className="text-xl">✨</span>
          <span className="font-bold text-lg tracking-tight text-white">
            AImplify
          </span>
        </div>

        {/* New conversation button */}
        <div className="px-3 mb-2">
          <button
            onClick={() => {
              onNew();
              onClose();
            }}
            className="w-full flex items-center gap-2 px-3 py-2.5 rounded-lg border border-white/15 text-sm font-medium text-white hover:bg-sidebar-hover transition-colors"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M8 3v10M3 8h10" />
            </svg>
            New Conversation
          </button>
        </div>

        {/* Conversation list */}
        <nav className="flex-1 overflow-y-auto px-3 space-y-0.5">
          {conversations.map((conv) => {
            const active = conv.id === activeId;
            return (
              <button
                key={conv.id}
                onClick={() => {
                  onSelect(conv.id);
                  onClose();
                }}
                className={`w-full text-left rounded-lg px-3 py-2.5 text-sm transition-colors truncate ${
                  active
                    ? "bg-sidebar-active text-white"
                    : "text-sidebar-text/70 hover:bg-sidebar-hover hover:text-white"
                }`}
              >
                <div className="truncate font-medium">
                  {conv.title || "New Conversation"}
                </div>
                <div className="text-xs mt-0.5 opacity-50">
                  {formatDate(conv.updated_at)}
                </div>
              </button>
            );
          })}
        </nav>

        {/* Dashboard link */}
        <div className="px-3 py-4 border-t border-white/10">
          <Link
            href="/dashboard"
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-sidebar-text/70 hover:bg-sidebar-hover hover:text-white transition-colors"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
              <rect x="2" y="2" width="5" height="5" rx="1" />
              <rect x="9" y="2" width="5" height="5" rx="1" />
              <rect x="2" y="9" width="5" height="5" rx="1" />
              <rect x="9" y="9" width="5" height="5" rx="1" />
            </svg>
            Dashboard
          </Link>
        </div>
      </aside>
    </>
  );
}

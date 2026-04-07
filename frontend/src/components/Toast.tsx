"use client";

import { useEffect } from "react";
import Link from "next/link";

interface ToastProps {
  message: string;
  visible: boolean;
  onDismiss: () => void;
}

export function Toast({ message, visible, onDismiss }: ToastProps) {
  useEffect(() => {
    if (visible) {
      const timer = setTimeout(onDismiss, 6000);
      return () => clearTimeout(timer);
    }
  }, [visible, onDismiss]);

  if (!visible) return null;

  return (
    <div className="fixed bottom-6 right-6 z-50 animate-toast">
      <div className="flex items-center gap-3 bg-emerald-50 border border-emerald-200 rounded-xl px-4 py-3 shadow-lg max-w-sm">
        <span className="text-emerald-600 text-lg">✓</span>
        <div className="flex-1 text-sm">
          <p className="font-medium text-emerald-900">{message}</p>
          <Link
            href="/dashboard"
            className="text-emerald-600 underline text-xs mt-0.5 inline-block"
          >
            View Dashboard
          </Link>
        </div>
        <button
          onClick={onDismiss}
          className="text-emerald-400 hover:text-emerald-600 transition-colors"
          aria-label="Dismiss"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M4 4l8 8M12 4l-8 8" />
          </svg>
        </button>
      </div>
    </div>
  );
}

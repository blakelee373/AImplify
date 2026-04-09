export function getTriggerLabel(
  triggerType?: string | null,
  triggerConfig?: Record<string, string> | null,
): string {
  if (!triggerConfig) return "Manual";

  if (triggerConfig.event_type) {
    if (triggerConfig.event_type === "email_received" && triggerConfig.description) {
      return `Watches for ${triggerConfig.description}`;
    }
    const labels: Record<string, string> = {
      new_booking: "When a new booking comes in",
      email_received: "When a matching email arrives",
      cancellation: "When a booking is cancelled",
    };
    return labels[triggerConfig.event_type] || `When: ${triggerConfig.event_type}`;
  }
  if (triggerConfig.schedule) {
    return triggerConfig.schedule;
  }
  if (triggerConfig.frequency) {
    return `Runs ${triggerConfig.frequency}`;
  }
  return "Manual";
}

export function timeAgo(iso: string): string {
  const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function formatNextRun(iso: string): string {
  // next_run_at is stored as UTC — append Z if missing so JS parses it correctly
  const date = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");
  const now = new Date();
  const diffMs = date.getTime() - now.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  const timeStr = date.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });

  if (diffMs < 0) return "Overdue";
  if (diffDays === 0) return `Today at ${timeStr}`;
  if (diffDays === 1) return `Tomorrow at ${timeStr}`;
  if (diffDays < 7) {
    const day = date.toLocaleDateString(undefined, { weekday: "long" });
    return `${day} at ${timeStr}`;
  }
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function getTriggerLabel(
  triggerType?: string | null,
  triggerConfig?: Record<string, string> | null,
): string {
  if (!triggerConfig) return "Manual";

  if (triggerConfig.event_type) {
    const labels: Record<string, string> = {
      new_booking: "When a new booking comes in",
      email_received: "When an email arrives",
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

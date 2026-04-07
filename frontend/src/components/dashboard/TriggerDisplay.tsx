interface TriggerDisplayProps {
  type: string | null;
  description: string;
}

const TRIGGER_LABELS: Record<string, { icon: string; prefix: string }> = {
  event_based: { icon: "🔔", prefix: "This runs when" },
  time_based: { icon: "⏰", prefix: "This runs" },
  condition_based: { icon: "🔀", prefix: "This runs when" },
};

export function TriggerDisplay({ type, description }: TriggerDisplayProps) {
  const label = TRIGGER_LABELS[type || ""] || { icon: "⚡", prefix: "Trigger" };

  return (
    <div className="flex gap-2 text-sm">
      <span>{label.icon}</span>
      <span>
        <span className="font-medium">{label.prefix}:</span> {description}
      </span>
    </div>
  );
}

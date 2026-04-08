const STATUS_STYLES: Record<string, string> = {
  draft: "bg-stone-100 text-stone-600",
  testing: "bg-blue-100 text-blue-700",
  active: "bg-green-100 text-green-700",
  paused: "bg-amber-100 text-amber-700",
};

export function WorkflowStatusBadge({ status }: { status: string }) {
  const colors = STATUS_STYLES[status] || STATUS_STYLES.draft;
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${colors}`}>
      {status}
    </span>
  );
}

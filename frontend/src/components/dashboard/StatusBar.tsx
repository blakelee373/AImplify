interface AttentionItem {
  type: string;
  message: string;
  action_url: string;
}

interface StatusBarProps {
  greetingTime: string;
  status: string;
  statusMessage: string;
  attentionItems: AttentionItem[];
}

export function StatusBar({ greetingTime, status, statusMessage, attentionItems }: StatusBarProps) {
  const bgClass =
    status === "healthy"
      ? "bg-emerald-50 border-emerald-200"
      : status === "attention_needed"
        ? "bg-amber-50 border-amber-200"
        : "bg-background border-border";

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-foreground">
        Good {greetingTime}! 👋
      </h1>
      <div className={`rounded-xl border px-5 py-4 ${bgClass}`}>
        <p className="text-sm font-medium text-foreground">{statusMessage}</p>
      </div>

      {attentionItems.length > 0 && (
        <div className="space-y-2">
          {attentionItems.map((item, i) => (
            <a
              key={i}
              href={item.action_url}
              className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-amber-50 border border-amber-200 text-sm hover:bg-amber-100 transition-colors"
            >
              <span className="text-amber-600">⚠</span>
              <span className="text-amber-900">{item.message}</span>
              <span className="ml-auto text-amber-500 text-xs">Fix →</span>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

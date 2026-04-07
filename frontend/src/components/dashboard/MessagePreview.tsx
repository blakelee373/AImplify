interface MessagePreviewProps {
  template: string;
  example: string;
  actionType: string;
}

export function MessagePreview({ example, actionType }: MessagePreviewProps) {
  const isEmail = actionType.includes("email");

  return (
    <div className={`rounded-lg border-2 border-dashed p-4 text-sm leading-relaxed ${
      isEmail ? "border-blue-200 bg-blue-50/50" : "border-emerald-200 bg-emerald-50/50"
    }`}>
      <p className="text-xs font-medium text-text-muted mb-2 uppercase tracking-wide">
        {isEmail ? "Email preview" : "Text message preview"}
      </p>
      <p className="text-foreground whitespace-pre-wrap">{example || "(No message content)"}</p>
    </div>
  );
}

interface SuggestionChipsProps {
  onSelect: (text: string) => void;
}

const SUGGESTIONS = [
  "Help me with appointment reminders",
  "I want to automate follow-up messages",
  "Show me what you can do",
];

export function SuggestionChips({ onSelect }: SuggestionChipsProps) {
  return (
    <div className="flex flex-col items-center justify-center h-full px-6 text-center">
      <div className="text-5xl mb-4">👋</div>
      <h2 className="text-2xl font-bold text-foreground">
        Hi! I&apos;m AImplify.
      </h2>
      <p className="mt-3 text-text-muted max-w-md leading-relaxed">
        Tell me about a task you or your staff do over and over, and I&apos;ll
        help you automate it.
      </p>
      <div className="flex flex-wrap justify-center gap-2 mt-8">
        {SUGGESTIONS.map((text) => (
          <button
            key={text}
            onClick={() => onSelect(text)}
            className="px-4 py-2.5 rounded-full border border-border bg-surface text-sm font-medium text-foreground hover:border-primary hover:bg-primary-light transition-colors shadow-sm"
          >
            {text}
          </button>
        ))}
      </div>
    </div>
  );
}

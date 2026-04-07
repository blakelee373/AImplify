export function TypingIndicator() {
  return (
    <div className="flex justify-start animate-message">
      <div className="bg-assistant-bubble border border-assistant-bubble-border rounded-2xl rounded-bl-md px-4 py-3 shadow-sm">
        <div className="flex gap-1.5 items-center h-5">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="w-2 h-2 bg-text-muted/40 rounded-full"
              style={{
                animation: `bounce-dot 1.2s ease-in-out ${i * 0.15}s infinite`,
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

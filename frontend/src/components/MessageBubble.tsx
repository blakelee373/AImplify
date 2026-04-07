"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MessageBubbleProps {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

function formatTime(dateStr: string) {
  return new Date(dateStr).toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

// Detect workflow summary cards (contain 📋 and the structured format)
function isWorkflowSummary(content: string) {
  return content.includes("📋") && content.includes("When:") && content.includes("What I'll do:");
}

export function MessageBubble({ role, content, timestamp }: MessageBubbleProps) {
  const isUser = role === "user";
  const isWorkflow = !isUser && isWorkflowSummary(content);

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} animate-message`}>
      <div className="max-w-[80%] md:max-w-[70%]">
        <div
          className={`rounded-2xl px-4 py-3 text-[15px] leading-relaxed ${
            isUser
              ? "bg-user-bubble text-user-bubble-text rounded-br-md"
              : isWorkflow
                ? "bg-primary-light border-2 border-primary/20 rounded-bl-md"
                : "bg-assistant-bubble border border-assistant-bubble-border rounded-bl-md shadow-sm"
          }`}
        >
          {isUser ? (
            <span>{content}</span>
          ) : (
            <div className="prose-chat">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  p: ({ children }) => (
                    <p className="mb-2 last:mb-0">{children}</p>
                  ),
                  strong: ({ children }) => (
                    <strong className="font-semibold">{children}</strong>
                  ),
                  ul: ({ children }) => (
                    <ul className="list-disc ml-4 mb-2 space-y-1">{children}</ul>
                  ),
                  ol: ({ children }) => (
                    <ol className="list-decimal ml-4 mb-2 space-y-1">{children}</ol>
                  ),
                  li: ({ children }) => <li>{children}</li>,
                  a: ({ href, children }) => (
                    <a href={href} className="text-primary underline" target="_blank" rel="noopener noreferrer">
                      {children}
                    </a>
                  ),
                }}
              >
                {content}
              </ReactMarkdown>
            </div>
          )}
        </div>
        <div
          className={`text-[11px] text-text-muted mt-1 px-1 ${
            isUser ? "text-right" : "text-left"
          }`}
        >
          {formatTime(timestamp)}
        </div>
      </div>
    </div>
  );
}

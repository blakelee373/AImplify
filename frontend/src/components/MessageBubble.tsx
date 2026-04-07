import { WorkflowSummaryCard } from "./WorkflowSummaryCard";

interface MessageMetadata {
  message_type?: string;
  workflow_draft?: {
    name: string;
    description: string;
    trigger_type: string;
    trigger_config: Record<string, string>;
    steps: Array<{
      step_order: number;
      action_type: string;
      description: string;
    }>;
  };
  workflow_id?: number;
}

interface MessageBubbleProps {
  role: "user" | "assistant";
  content: string;
  metadata?: MessageMetadata | null;
}

export function MessageBubble({ role, content, metadata }: MessageBubbleProps) {
  const isUser = role === "user";

  // Workflow confirmed — show success banner
  if (metadata?.message_type === "workflow_confirmed") {
    return (
      <div className="flex justify-start">
        <div className="max-w-[75%] space-y-3">
          <div className="bg-stone-100 rounded-2xl px-4 py-3 text-sm leading-relaxed text-stone-800 rounded-bl-md">
            {content}
          </div>
          <div className="bg-green-50 border border-green-200 rounded-xl px-4 py-3 text-sm text-green-700 font-medium">
            Saved! You can view this on the Dashboard.
          </div>
        </div>
      </div>
    );
  }

  // Workflow summary — show the card below the message
  if (metadata?.message_type === "workflow_summary" && metadata.workflow_draft) {
    return (
      <div className="flex justify-start">
        <div className="max-w-[75%] space-y-3">
          <div className="bg-stone-100 rounded-2xl px-4 py-3 text-sm leading-relaxed text-stone-800 rounded-bl-md">
            {content}
          </div>
          <WorkflowSummaryCard draft={metadata.workflow_draft} />
        </div>
      </div>
    );
  }

  // Regular message
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
          isUser
            ? "bg-primary text-white rounded-br-md"
            : "bg-stone-100 text-stone-800 rounded-bl-md"
        }`}
      >
        {content}
      </div>
    </div>
  );
}

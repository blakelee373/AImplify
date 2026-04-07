interface WorkflowDraft {
  name: string;
  description: string;
  trigger_type: string;
  trigger_config: Record<string, string>;
  steps: Array<{
    step_order: number;
    action_type: string;
    description: string;
  }>;
}

interface WorkflowSummaryCardProps {
  draft: WorkflowDraft;
}

function getTriggerLabel(draft: WorkflowDraft): string {
  const config = draft.trigger_config;
  if (config.event_type) {
    const labels: Record<string, string> = {
      new_booking: "When a new booking comes in",
      email_received: "When an email arrives",
      cancellation: "When a booking is cancelled",
    };
    return labels[config.event_type] || `When: ${config.event_type}`;
  }
  if (config.schedule) {
    return config.schedule;
  }
  if (config.frequency) {
    return `Runs ${config.frequency}`;
  }
  return "Manual";
}

export function WorkflowSummaryCard({ draft }: WorkflowSummaryCardProps) {
  return (
    <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 space-y-3">
      <div>
        <h3 className="font-semibold text-stone-900 text-sm">{draft.name}</h3>
        <p className="text-xs text-stone-500 mt-0.5">{draft.description}</p>
      </div>

      <div className="text-xs text-amber-700 font-medium bg-amber-100 rounded-md px-2.5 py-1 inline-block">
        {getTriggerLabel(draft)}
      </div>

      <ol className="space-y-2">
        {draft.steps
          .sort((a, b) => a.step_order - b.step_order)
          .map((step) => (
            <li key={step.step_order} className="flex gap-2.5 items-start">
              <span className="flex-shrink-0 w-5 h-5 rounded-full bg-primary text-white text-xs flex items-center justify-center font-medium">
                {step.step_order}
              </span>
              <span className="text-sm text-stone-700">{step.description}</span>
            </li>
          ))}
      </ol>
    </div>
  );
}

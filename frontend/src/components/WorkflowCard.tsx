import Link from "next/link";
import { WorkflowStatusBadge } from "./WorkflowStatusBadge";
import { getTriggerLabel, timeAgo } from "@/lib/workflow-utils";

interface WorkflowCardProps {
  workflow: {
    id: number;
    name: string;
    description?: string;
    status: string;
    trigger_type?: string;
    trigger_config?: Record<string, string> | null;
    steps: Array<{ id: number; step_order: number; action_type: string; description?: string }>;
    updated_at: string;
  };
}

export function WorkflowCard({ workflow }: WorkflowCardProps) {
  const stepCount = workflow.steps.length;

  return (
    <Link
      href={`/dashboard/workflows/${workflow.id}`}
      className="block rounded-lg border border-stone-200 p-4 hover:border-stone-300 transition-colors"
    >
      <div className="flex items-start justify-between">
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold text-stone-900">{workflow.name}</h3>
          {workflow.description && (
            <p className="text-xs text-stone-500 mt-0.5 line-clamp-2">{workflow.description}</p>
          )}
        </div>
        <WorkflowStatusBadge status={workflow.status} />
      </div>

      <div className="mt-3 flex items-center gap-3 text-xs text-stone-400">
        <span>{getTriggerLabel(workflow.trigger_type, workflow.trigger_config)}</span>
        <span>&middot;</span>
        <span>{stepCount} step{stepCount !== 1 ? "s" : ""}</span>
        <span>&middot;</span>
        <span>Updated {timeAgo(workflow.updated_at)}</span>
      </div>
    </Link>
  );
}

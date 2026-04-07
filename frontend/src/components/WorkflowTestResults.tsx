"use client";

import type { WorkflowTestResult } from "@/lib/api";

interface WorkflowTestResultsProps {
  result: WorkflowTestResult;
  onActivate: () => void;
  onAdjust: () => void;
  loading?: boolean;
}

export function WorkflowTestResults({
  result,
  onActivate,
  onAdjust,
  loading,
}: WorkflowTestResultsProps) {
  return (
    <div className="bg-surface border border-border rounded-xl p-5 space-y-4">
      <h3 className="font-semibold text-foreground">
        {result.dry_run ? "Here's what would happen:" : "Execution Results"}
      </h3>

      <div className="space-y-3">
        {result.steps.map((step) => (
          <div
            key={step.step_order}
            className="bg-background rounded-lg p-4 border border-border"
          >
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-semibold text-text-muted uppercase">
                Step {step.step_order}
              </span>
              {step.success ? (
                <span className="text-xs text-emerald-600">✓</span>
              ) : (
                <span className="text-xs text-red-500">✗</span>
              )}
            </div>
            <p className="text-sm text-foreground font-medium mb-1">{step.description}</p>
            {step.preview && (
              <p className="text-sm text-text-muted bg-white border border-border rounded-md px-3 py-2 mt-2">
                {step.preview}
              </p>
            )}
            {step.error && (
              <p className="text-sm text-red-600 mt-1">Error: {step.error}</p>
            )}
          </div>
        ))}
      </div>

      {result.dry_run && (
        <div className="flex gap-2 pt-2">
          <button
            onClick={onActivate}
            disabled={loading}
            className="px-5 py-2 text-sm font-semibold rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 transition-colors disabled:opacity-50"
          >
            Looks good — turn it on!
          </button>
          <button
            onClick={onAdjust}
            disabled={loading}
            className="px-4 py-2 text-sm font-medium rounded-lg border border-border hover:bg-background transition-colors disabled:opacity-50"
          >
            Let me adjust something
          </button>
        </div>
      )}
    </div>
  );
}

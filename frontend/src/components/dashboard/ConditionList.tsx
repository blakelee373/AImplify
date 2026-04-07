interface Condition {
  type: string;
  params?: Record<string, unknown>;
}

interface ConditionListProps {
  conditions: (Condition | string)[];
}

const CONDITION_LABELS: Record<string, string> = {
  "client.is_new": "The client is a first-time visitor",
  "client.is_returning": "The client has visited before",
  "client.has_email": "The client has an email on file",
  "client.has_phone": "The client has a phone number on file",
  "appointment.is_weekday": "The appointment is on a weekday",
  "appointment.is_weekend": "The appointment is on a weekend",
  "appointment.is_first_appointment": "It's the client's first booking",
  "current_time.is_business_hours": "It's during business hours",
  "workflow.has_not_run_today": "This hasn't run yet today",
};

function formatCondition(condition: Condition | string): string {
  if (typeof condition === "string") return condition;

  const base = CONDITION_LABELS[condition.type];
  if (base) return base;

  const params = condition.params || {};
  if (condition.type === "appointment.service_type_is") {
    return `The appointment is for ${params.service_type || "a specific service"}`;
  }
  if (condition.type === "appointment.service_type_is_not") {
    return `The appointment is NOT for ${params.service_type || "a specific service"}`;
  }
  if (condition.type === "client.visit_count_greater_than") {
    return `The client has visited more than ${params.count || "N"} times`;
  }
  if (condition.type === "client.days_since_last_visit_greater_than") {
    return `It's been more than ${params.days || "N"} days since the client's last visit`;
  }
  if (condition.type === "workflow.has_not_run_for_client_in_days") {
    return `The client hasn't been contacted in ${params.days || "N"} days`;
  }
  if (condition.type === "workflow.total_runs_today_less_than") {
    return `This has run fewer than ${params.count || "N"} times today`;
  }

  return condition.type.replace(/\./g, " ").replace(/_/g, " ");
}

export function ConditionList({ conditions }: ConditionListProps) {
  if (!conditions || conditions.length === 0) return null;

  return (
    <div className="text-sm text-text-muted mt-2 ml-6">
      <p className="font-medium text-foreground mb-1">Only when:</p>
      <ul className="space-y-1">
        {conditions.map((c, i) => (
          <li key={i} className="flex items-start gap-1.5">
            <span className="text-emerald-500 mt-0.5">✓</span>
            <span>{formatCondition(c)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

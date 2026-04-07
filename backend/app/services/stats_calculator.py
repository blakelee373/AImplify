"""Calculate dashboard statistics for a given time period."""

from datetime import datetime, timedelta, timezone
from typing import Dict, Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.workflow import Workflow
from app.models.workflow_execution import WorkflowExecution
from app.models.activity_log import ActivityLog

# Estimated manual minutes per action type
TIME_PER_ACTION = {
    "send_sms": 2,
    "send_template_sms": 2,
    "send_email": 5,
    "send_template_email": 5,
    "send_review_request": 3,
    "create_calendar_event": 3,
    "create_task": 1,
    "create_reminder": 1,
    "workflow_executed": 0,
    "workflow_created": 0,
    "step_failed": 0,
}


def _period_bounds(period: str) -> tuple:
    """Return (start, end) datetimes for the named period."""
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if period == "today":
        return today, now
    elif period == "this_week":
        start = today - timedelta(days=today.weekday())  # Monday
        return start, now
    elif period == "last_week":
        this_monday = today - timedelta(days=today.weekday())
        return this_monday - timedelta(weeks=1), this_monday
    elif period == "this_month":
        start = today.replace(day=1)
        return start, now
    elif period == "last_month":
        first = today.replace(day=1)
        end = first
        start = (first - timedelta(days=1)).replace(day=1)
        return start, end
    else:  # all_time
        return datetime(2020, 1, 1, tzinfo=timezone.utc), now


def calculate_stats(db: Session, period: str = "this_week") -> Dict[str, Any]:
    start, end = _period_bounds(period)

    # Previous period (same length)
    delta = end - start
    prev_start = start - delta
    prev_end = start

    # Current period executions
    current_execs = (
        db.query(WorkflowExecution)
        .filter(
            WorkflowExecution.started_at >= start,
            WorkflowExecution.started_at <= end,
            WorkflowExecution.status != "dry_run",
        )
        .all()
    )

    total = len(current_execs)
    successful = sum(1 for e in current_execs if e.status == "completed")
    failed = sum(1 for e in current_execs if e.status == "failed")

    # Previous period count
    prev_count = (
        db.query(func.count(WorkflowExecution.id))
        .filter(
            WorkflowExecution.started_at >= prev_start,
            WorkflowExecution.started_at <= prev_end,
            WorkflowExecution.status.in_(["completed", "failed"]),
        )
        .scalar()
    ) or 0

    change_pct = 0.0
    if prev_count > 0:
        change_pct = round(((total - prev_count) / prev_count) * 100, 1)

    # Message breakdown from activity logs
    sms_count = (
        db.query(func.count(ActivityLog.id))
        .filter(
            ActivityLog.created_at >= start,
            ActivityLog.created_at <= end,
            ActivityLog.action_type.in_(["send_sms", "send_template_sms", "send_review_request"]),
        )
        .scalar()
    ) or 0

    email_count = (
        db.query(func.count(ActivityLog.id))
        .filter(
            ActivityLog.created_at >= start,
            ActivityLog.created_at <= end,
            ActivityLog.action_type.in_(["send_email", "send_template_email"]),
        )
        .scalar()
    ) or 0

    # Time saved estimate
    activity_types = (
        db.query(ActivityLog.action_type, func.count(ActivityLog.id))
        .filter(
            ActivityLog.created_at >= start,
            ActivityLog.created_at <= end,
        )
        .group_by(ActivityLog.action_type)
        .all()
    )
    time_saved = sum(
        count * TIME_PER_ACTION.get(action_type, 0)
        for action_type, count in activity_types
    )

    # Workflow counts
    active_workflows = (
        db.query(func.count(Workflow.id))
        .filter(Workflow.status == "active", Workflow.deleted_at.is_(None))
        .scalar()
    ) or 0

    total_workflows = (
        db.query(func.count(Workflow.id))
        .filter(Workflow.deleted_at.is_(None))
        .scalar()
    ) or 0

    success_rate = round((successful / total) * 100, 1) if total > 0 else 100.0

    return {
        "period": period,
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "tasks_completed": successful,
        "tasks_completed_previous_period": prev_count,
        "tasks_change_percent": change_pct,
        "messages_sent": {
            "total": sms_count + email_count,
            "sms": sms_count,
            "email": email_count,
        },
        "estimated_time_saved_minutes": time_saved,
        "success_rate": success_rate,
        "total_executions": total,
        "successful_executions": successful,
        "failed_executions": failed,
        "workflows_active": active_workflows,
        "workflows_total": total_workflows,
    }

"""Evaluate workflow conditions against trigger context."""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

from app.database import SessionLocal
from app.models.workflow_execution import WorkflowExecution

logger = logging.getLogger(__name__)


def evaluate_conditions(conditions: List[Dict[str, Any]], context: Dict[str, Any]) -> bool:
    """Return True only if ALL conditions pass (AND logic)."""
    for condition in conditions:
        cond_type = condition.get("type", "")
        params = condition.get("params", {})

        if not _evaluate_single(cond_type, params, context):
            logger.info("Condition failed: %s", cond_type)
            return False

    return True


def _evaluate_single(cond_type: str, params: dict, ctx: dict) -> bool:
    """Evaluate one condition. Returns True if the condition passes."""

    # --- Client conditions ---
    if cond_type == "client.is_new":
        return ctx.get("is_new_client", True)

    if cond_type == "client.is_returning":
        return not ctx.get("is_new_client", True)

    if cond_type == "client.visit_count_greater_than":
        return int(ctx.get("visit_count", 0)) > int(params.get("count", 0))

    if cond_type == "client.visit_count_less_than":
        return int(ctx.get("visit_count", 0)) < int(params.get("count", 999))

    if cond_type == "client.days_since_last_visit_greater_than":
        days = ctx.get("days_since_last_visit")
        if days is None:
            return True  # no visit history, treat as inactive
        return int(days) > int(params.get("days", 0))

    if cond_type == "client.has_email":
        return bool(ctx.get("client_email"))

    if cond_type == "client.has_phone":
        return bool(ctx.get("client_phone"))

    # --- Appointment conditions ---
    if cond_type == "appointment.service_type_is":
        service = ctx.get("service_type", "").lower()
        target = params.get("service_type", "").lower()
        return target in service

    if cond_type == "appointment.service_type_is_not":
        service = ctx.get("service_type", "").lower()
        target = params.get("service_type", "").lower()
        return target not in service

    if cond_type == "appointment.is_first_appointment":
        return ctx.get("is_new_client", False)

    if cond_type == "appointment.is_weekday":
        dt = _parse_appointment_dt(ctx)
        return dt.weekday() < 5 if dt else True

    if cond_type == "appointment.is_weekend":
        dt = _parse_appointment_dt(ctx)
        return dt.weekday() >= 5 if dt else True

    # --- Time conditions ---
    if cond_type == "current_time.is_business_hours":
        # Simplified: 9 AM - 6 PM local
        hour = datetime.now().hour
        return 9 <= hour < 18

    if cond_type == "current_time.day_is":
        target_day = params.get("day", "").lower()
        current_day = datetime.now().strftime("%A").lower()
        return current_day == target_day

    # --- Workflow conditions ---
    if cond_type == "workflow.has_not_run_for_client_in_days":
        days = int(params.get("days", 7))
        return _check_client_cooldown(ctx, days)

    if cond_type == "workflow.total_runs_today_less_than":
        limit = int(params.get("count", 100))
        return _count_runs_today(ctx.get("workflow_id", "")) < limit

    if cond_type == "workflow.has_not_run_today":
        return _count_runs_today(ctx.get("workflow_id", "")) == 0

    # Unknown condition — pass by default (don't block on unrecognized conditions)
    logger.warning("Unknown condition type: %s — passing by default", cond_type)
    return True


def _parse_appointment_dt(ctx: dict):
    raw = ctx.get("appointment_time") or ctx.get("start_time")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _check_client_cooldown(ctx: dict, days: int) -> bool:
    """True if the workflow hasn't run for this client within N days."""
    from datetime import timedelta
    client_email = ctx.get("client_email", "")
    workflow_id = ctx.get("workflow_id", "")
    if not client_email or not workflow_id:
        return True

    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        recent = (
            db.query(WorkflowExecution)
            .filter(
                WorkflowExecution.workflow_id == workflow_id,
                WorkflowExecution.started_at >= cutoff,
                WorkflowExecution.status == "completed",
            )
            .all()
        )
        # Check if any execution was for the same client
        for ex in recent:
            tc = ex.trigger_context or {}
            if tc.get("client_email") == client_email:
                return False
        return True
    finally:
        db.close()


def _count_runs_today(workflow_id: str) -> int:
    if not workflow_id:
        return 0
    db = SessionLocal()
    try:
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        from sqlalchemy import func
        count = (
            db.query(func.count(WorkflowExecution.id))
            .filter(
                WorkflowExecution.workflow_id == workflow_id,
                WorkflowExecution.started_at >= today,
                WorkflowExecution.status != "dry_run",
            )
            .scalar()
        ) or 0
        return count
    finally:
        db.close()

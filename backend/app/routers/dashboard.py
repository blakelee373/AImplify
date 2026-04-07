"""Dashboard endpoints — summary, stats, activity feed."""

import math
from datetime import datetime, timedelta, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.workflow import Workflow
from app.models.workflow_execution import WorkflowExecution
from app.models.activity_log import ActivityLog
from app.models.integration import Integration
from app.services.stats_calculator import calculate_stats
from app.services.error_translator import translate_error

router = APIRouter()


@router.get("/dashboard/summary")
async def dashboard_summary(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    hour = datetime.now().hour

    if hour < 12:
        greeting_time = "morning"
    elif hour < 17:
        greeting_time = "afternoon"
    else:
        greeting_time = "evening"

    # Workflows
    workflows = (
        db.query(Workflow)
        .filter(Workflow.deleted_at.is_(None))
        .order_by(Workflow.created_at.desc())
        .all()
    )
    active_count = sum(1 for w in workflows if w.status == "active")

    # Today's executions
    today_execs = (
        db.query(WorkflowExecution)
        .filter(
            WorkflowExecution.started_at >= today_start,
            WorkflowExecution.status != "dry_run",
        )
        .all()
    )
    tasks_today = sum(1 for e in today_execs if e.status == "completed")
    errors_today = sum(1 for e in today_execs if e.status == "failed")

    # This week
    week_start = today_start - timedelta(days=today_start.weekday())
    tasks_week = (
        db.query(func.count(WorkflowExecution.id))
        .filter(
            WorkflowExecution.started_at >= week_start,
            WorkflowExecution.status == "completed",
        )
        .scalar()
    ) or 0

    # Status + message
    attention_items = _check_attention_items(db, now)
    if attention_items:
        status = "attention_needed"
        status_message = "Heads up — {} {} your attention.".format(
            len(attention_items),
            "item needs" if len(attention_items) == 1 else "items need",
        )
    elif active_count > 0 and tasks_today > 0:
        status = "healthy"
        status_message = "Everything's running smoothly. Your AI workers handled {} {} today.".format(
            tasks_today, "task" if tasks_today == 1 else "tasks"
        )
    elif active_count > 0:
        status = "healthy"
        status_message = "All quiet so far today. Your AI workers are standing by."
    else:
        status = "quiet"
        status_message = "All quiet today. Your AI workers are standing by."

    # Build workflow summaries
    workflow_summaries = []
    for w in workflows:
        if w.status in ("draft",) and not w.steps:
            continue
        last_exec = (
            db.query(WorkflowExecution)
            .filter(
                WorkflowExecution.workflow_id == w.id,
                WorkflowExecution.status != "dry_run",
            )
            .order_by(desc(WorkflowExecution.started_at))
            .first()
        )
        runs_today = (
            db.query(func.count(WorkflowExecution.id))
            .filter(
                WorkflowExecution.workflow_id == w.id,
                WorkflowExecution.started_at >= today_start,
                WorkflowExecution.status != "dry_run",
            )
            .scalar()
        ) or 0
        runs_total = (
            db.query(func.count(WorkflowExecution.id))
            .filter(
                WorkflowExecution.workflow_id == w.id,
                WorkflowExecution.status != "dry_run",
            )
            .scalar()
        ) or 0

        primary_action = "send_sms"
        if w.steps:
            primary_action = w.steps[0].action_type

        workflow_summaries.append({
            "id": w.id,
            "name": w.name,
            "description": w.description,
            "status": w.status,
            "primary_action_type": primary_action,
            "last_run_at": last_exec.started_at.isoformat() if last_exec else None,
            "run_count_today": runs_today,
            "run_count_total": runs_total,
            "has_errors": any(
                e.status == "failed"
                for e in today_execs
                if e.workflow_id == w.id
            ),
        })

    # Recent activity
    recent = (
        db.query(ActivityLog)
        .order_by(desc(ActivityLog.created_at))
        .limit(5)
        .all()
    )
    recent_activity = []
    for a in recent:
        wf_name = None
        if a.workflow_id:
            wf = db.query(Workflow.name).filter(Workflow.id == a.workflow_id).first()
            if wf:
                wf_name = wf[0]
        recent_activity.append({
            "id": a.id,
            "action_type": a.action_type,
            "description": a.description or a.action_type,
            "workflow_name": wf_name,
            "timestamp": a.created_at.isoformat(),
            "success": a.action_type != "step_failed",
        })

    return {
        "greeting_time": greeting_time,
        "status": status,
        "status_message": status_message,
        "attention_items": attention_items,
        "stats": {
            "active_workflows": active_count,
            "tasks_completed_today": tasks_today,
            "tasks_completed_this_week": tasks_week,
            "errors_today": errors_today,
        },
        "workflows": workflow_summaries,
        "recent_activity": recent_activity,
    }


@router.get("/dashboard/stats")
async def dashboard_stats(
    period: str = Query("this_week"),
    db: Session = Depends(get_db),
):
    return calculate_stats(db, period)


@router.get("/activity")
async def activity_feed(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    action_type: Optional[str] = None,
    status: Optional[str] = None,
    workflow_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(ActivityLog)

    if action_type:
        if action_type == "sms":
            query = query.filter(ActivityLog.action_type.in_(["send_sms", "send_template_sms", "send_review_request"]))
        elif action_type == "email":
            query = query.filter(ActivityLog.action_type.in_(["send_email", "send_template_email"]))
        elif action_type == "calendar":
            query = query.filter(ActivityLog.action_type.in_(["create_calendar_event", "check_availability"]))
        elif action_type == "errors":
            query = query.filter(ActivityLog.action_type == "step_failed")
        else:
            query = query.filter(ActivityLog.action_type == action_type)

    if workflow_id:
        query = query.filter(ActivityLog.workflow_id == workflow_id)

    total = query.count()
    entries = (
        query.order_by(desc(ActivityLog.created_at))
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    items = []
    for a in entries:
        wf_name = None
        if a.workflow_id:
            wf = db.query(Workflow.name).filter(Workflow.id == a.workflow_id).first()
            if wf:
                wf_name = wf[0]

        friendly_error = None
        if a.action_type == "step_failed" and a.description:
            friendly_error = translate_error(a.description)

        items.append({
            "id": a.id,
            "action_type": a.action_type,
            "description": a.description or a.action_type,
            "workflow_id": a.workflow_id,
            "workflow_name": wf_name,
            "details": a.details,
            "success": a.action_type != "step_failed",
            "friendly_error": friendly_error,
            "created_at": a.created_at.isoformat(),
        })

    return {
        "items": items,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": math.ceil(total / per_page) if total > 0 else 1,
    }


def _check_attention_items(db: Session, now: datetime) -> List[dict]:
    items = []
    yesterday = now - timedelta(hours=24)

    # Disconnected/expired integrations
    bad_integrations = (
        db.query(Integration)
        .filter(Integration.status.in_(["error", "expired"]))
        .all()
    )
    for integ in bad_integrations:
        items.append({
            "type": "disconnected_integration",
            "message": "Your {} connection needs to be refreshed.".format(
                integ.integration_type.replace("_", " ").title()
            ),
            "action_url": "/integrations",
        })

    # Failed executions in last 24h
    failed_count = (
        db.query(func.count(WorkflowExecution.id))
        .filter(
            WorkflowExecution.started_at >= yesterday,
            WorkflowExecution.status == "failed",
        )
        .scalar()
    ) or 0
    if failed_count > 0:
        items.append({
            "type": "error",
            "message": "{} {} failed in the last 24 hours.".format(
                failed_count, "task" if failed_count == 1 else "tasks"
            ),
            "action_url": "/dashboard/activity?filter=errors",
        })

    # Stale drafts (>3 days old)
    three_days_ago = now - timedelta(days=3)
    stale_drafts = (
        db.query(func.count(Workflow.id))
        .filter(
            Workflow.status == "draft",
            Workflow.created_at <= three_days_ago,
            Workflow.deleted_at.is_(None),
        )
        .scalar()
    ) or 0
    if stale_drafts > 0:
        items.append({
            "type": "approval_needed",
            "message": "You have {} unfinished {} waiting to be activated.".format(
                stale_drafts, "task" if stale_drafts == 1 else "tasks"
            ),
            "action_url": "/dashboard",
        })

    return items

import math
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.workflow import Workflow, WorkflowStep
from app.models.workflow_execution import WorkflowExecution
from app.models.integration import Integration
from app.schemas.workflow import WorkflowResponse, WorkflowUpdate
from app.services.workflow_executor import execute_workflow
from app.services.variable_resolver import resolve_variables
from app.services.error_translator import translate_error

router = APIRouter()


@router.get("/workflows", response_model=List[WorkflowResponse])
async def list_workflows(db: Session = Depends(get_db)):
    workflows = (
        db.query(Workflow)
        .filter(Workflow.deleted_at.is_(None))
        .order_by(Workflow.created_at.desc())
        .all()
    )
    return workflows


@router.get("/workflows/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(workflow_id: str, db: Session = Depends(get_db)):
    workflow = db.query(Workflow).filter(
        Workflow.id == workflow_id,
        Workflow.deleted_at.is_(None),
    ).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@router.patch("/workflows/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: str,
    update: WorkflowUpdate,
    db: Session = Depends(get_db),
):
    workflow = db.query(Workflow).filter(
        Workflow.id == workflow_id,
        Workflow.deleted_at.is_(None),
    ).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    update_data = update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(workflow, field, value)

    db.commit()
    db.refresh(workflow)
    return workflow


@router.delete("/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str, db: Session = Depends(get_db)):
    workflow = db.query(Workflow).filter(
        Workflow.id == workflow_id,
        Workflow.deleted_at.is_(None),
    ).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "deleted"}


@router.post("/workflows/{workflow_id}/test")
async def test_workflow(workflow_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Run a workflow in dry-run mode with sample data."""
    workflow = db.query(Workflow).filter(
        Workflow.id == workflow_id,
        Workflow.deleted_at.is_(None),
    ).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Build sample trigger context
    sample_context = {
        "client_name": "Sarah Johnson",
        "client_email": "sarah@example.com",
        "client_phone": "+15551234567",
        "appointment_time": "Tuesday, April 15 at 2:00 PM",
        "appointment_date": "April 15, 2026",
        "service_type": "Hydrafacial",
        "business_name": "Glow Medspa",
        "business_phone": "(555) 987-6543",
        "review_link": "https://g.page/r/example",
        "provider_name": "Dr. Smith",
        "days_since_visit": "30",
        "trigger_type": "manual_test",
    }

    result = await execute_workflow(
        workflow_id=workflow.id,
        trigger_context=sample_context,
        dry_run=True,
    )
    return result


# --- Detail & execution history ---

SAMPLE_CONTEXT = {
    "client_name": "Sarah Johnson",
    "client_email": "sarah@example.com",
    "client_phone": "+15551234567",
    "appointment_time": "Tuesday, April 15 at 2:00 PM",
    "appointment_date": "April 15, 2026",
    "service_type": "Hydrafacial",
    "business_name": "Glow Medspa",
    "business_phone": "(555) 987-6543",
    "review_link": "https://g.page/r/example",
    "provider_name": "Dr. Smith",
    "days_since_visit": "30",
}


@router.get("/workflows/{workflow_id}/detail")
async def get_workflow_detail(workflow_id: str, db: Session = Depends(get_db)):
    workflow = db.query(Workflow).filter(
        Workflow.id == workflow_id,
        Workflow.deleted_at.is_(None),
    ).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Build step previews
    steps_out = []
    for step in workflow.steps:
        cfg = step.action_config or {}
        template = cfg.get("message_template", "")
        example = resolve_variables(template, SAMPLE_CONTEXT) if template else ""

        # Check if required integration is connected
        int_name = _action_to_integration(step.action_type)
        int_connected = False
        if int_name:
            integ = db.query(Integration).filter(
                Integration.integration_type == int_name,
                Integration.status == "connected",
            ).first()
            int_connected = integ is not None

        steps_out.append({
            "step_order": step.step_order,
            "action_type": step.action_type,
            "description": step.description or step.action_type,
            "message_preview": {
                "template": template,
                "example": example,
            },
            "integration_required": int_name,
            "integration_connected": int_connected,
        })

    # Stats
    total_runs = db.query(func.count(WorkflowExecution.id)).filter(
        WorkflowExecution.workflow_id == workflow_id,
        WorkflowExecution.status != "dry_run",
    ).scalar() or 0

    successful_runs = db.query(func.count(WorkflowExecution.id)).filter(
        WorkflowExecution.workflow_id == workflow_id,
        WorkflowExecution.status == "completed",
    ).scalar() or 0

    failed_runs = db.query(func.count(WorkflowExecution.id)).filter(
        WorkflowExecution.workflow_id == workflow_id,
        WorkflowExecution.status == "failed",
    ).scalar() or 0

    last_exec = (
        db.query(WorkflowExecution)
        .filter(WorkflowExecution.workflow_id == workflow_id, WorkflowExecution.status != "dry_run")
        .order_by(desc(WorkflowExecution.started_at))
        .first()
    )

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - datetime.timedelta(days=today_start.weekday()) if hasattr(datetime, 'timedelta') else today_start

    from datetime import timedelta
    week_start = today_start - timedelta(days=today_start.weekday())

    runs_today = db.query(func.count(WorkflowExecution.id)).filter(
        WorkflowExecution.workflow_id == workflow_id,
        WorkflowExecution.started_at >= today_start,
        WorkflowExecution.status != "dry_run",
    ).scalar() or 0

    runs_week = db.query(func.count(WorkflowExecution.id)).filter(
        WorkflowExecution.workflow_id == workflow_id,
        WorkflowExecution.started_at >= week_start,
        WorkflowExecution.status != "dry_run",
    ).scalar() or 0

    # Recent executions
    recent_execs = (
        db.query(WorkflowExecution)
        .filter(WorkflowExecution.workflow_id == workflow_id, WorkflowExecution.status != "dry_run")
        .order_by(desc(WorkflowExecution.started_at))
        .limit(20)
        .all()
    )

    executions_out = []
    for ex in recent_execs:
        ctx = ex.trigger_context or {}
        summary_parts = []
        if ctx.get("service_type"):
            summary_parts.append(ctx["service_type"])
        if ctx.get("client_name"):
            summary_parts.append("with " + ctx["client_name"])
        if ctx.get("appointment_time"):
            summary_parts.append("at " + ctx["appointment_time"])
        ctx_summary = " ".join(summary_parts) if summary_parts else "Manual trigger"

        step_results = []
        if ex.results and "steps" in ex.results:
            for sr in ex.results["steps"]:
                step_results.append({
                    "step_order": sr.get("step_order"),
                    "action_type": sr.get("action_type"),
                    "success": sr.get("success", False),
                    "description": sr.get("preview") or sr.get("description", ""),
                    "timestamp": sr.get("timestamp"),
                })

        executions_out.append({
            "id": ex.id,
            "started_at": ex.started_at.isoformat(),
            "completed_at": ex.completed_at.isoformat() if ex.completed_at else None,
            "status": ex.status,
            "trigger_context_summary": ctx_summary,
            "results": step_results,
            "error": translate_error(ex.error, "") if ex.error else None,
        })

    return {
        "id": workflow.id,
        "name": workflow.name,
        "description": workflow.description,
        "status": workflow.status,
        "created_at": workflow.created_at.isoformat(),
        "trigger": {
            "type": workflow.trigger_type,
            "description": workflow.trigger_description or "Not specified",
            "config": workflow.trigger_config,
        },
        "steps": steps_out,
        "conditions": workflow.conditions or [],
        "stats": {
            "total_runs": total_runs,
            "successful_runs": successful_runs,
            "failed_runs": failed_runs,
            "last_run_at": last_exec.started_at.isoformat() if last_exec else None,
            "runs_today": runs_today,
            "runs_this_week": runs_week,
        },
        "recent_executions": executions_out,
    }


@router.get("/workflows/{workflow_id}/executions")
async def get_workflow_executions(
    workflow_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(WorkflowExecution).filter(
        WorkflowExecution.workflow_id == workflow_id,
        WorkflowExecution.status != "dry_run",
    )
    if status:
        query = query.filter(WorkflowExecution.status == status)

    total = query.count()
    items = (
        query.order_by(desc(WorkflowExecution.started_at))
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return {
        "items": [
            {
                "id": ex.id,
                "started_at": ex.started_at.isoformat(),
                "completed_at": ex.completed_at.isoformat() if ex.completed_at else None,
                "status": ex.status,
                "results": ex.results,
                "error": translate_error(ex.error, "") if ex.error else None,
            }
            for ex in items
        ],
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": math.ceil(total / per_page) if total > 0 else 1,
    }


def _action_to_integration(action_type: str) -> Optional[str]:
    mapping = {
        "send_sms": "twilio_sms",
        "send_template_sms": "twilio_sms",
        "send_review_request": "twilio_sms",
        "send_email": "gmail",
        "send_template_email": "gmail",
        "create_calendar_event": "google_calendar",
    }
    return mapping.get(action_type)

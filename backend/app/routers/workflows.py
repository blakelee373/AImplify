from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.workflow import Workflow, WorkflowStep
from app.models.activity_log import ActivityLog
from app.schemas.workflow import WorkflowResponse
from app.services.workflow_runner import run_workflow

router = APIRouter(prefix="/api")


class ExecuteWorkflowRequest(BaseModel):
    context: Optional[Dict] = None


class UpdateStatusRequest(BaseModel):
    status: str  # "active", "paused"


ALLOWED_STATUS_TRANSITIONS = {
    "draft": ["active", "paused"],
    "testing": ["active", "paused"],
    "active": ["paused"],
    "paused": ["active"],
}


@router.get("/workflows", response_model=List[WorkflowResponse])
async def list_workflows(db: Session = Depends(get_db)):
    workflows = db.query(Workflow).order_by(Workflow.updated_at.desc()).all()
    return [WorkflowResponse.model_validate(w) for w in workflows]


@router.patch("/workflows/{workflow_id}/status", response_model=WorkflowResponse)
async def update_workflow_status(
    workflow_id: int,
    req: UpdateStatusRequest,
    db: Session = Depends(get_db),
):
    """Pause or resume a workflow."""
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    allowed = ALLOWED_STATUS_TRANSITIONS.get(workflow.status, [])
    if req.status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot change status from '{workflow.status}' to '{req.status}'",
        )

    old_status = workflow.status
    workflow.status = req.status
    workflow.updated_at = datetime.now(timezone.utc)

    # Sync next_run_at for scheduled workflows
    if req.status == "active" and workflow.trigger_type == "schedule":
        from app.services.scheduler import update_next_run
        update_next_run(db, workflow)
    elif req.status == "paused":
        workflow.next_run_at = None

    log = ActivityLog(
        workflow_id=workflow.id,
        action_type="workflow_status_change",
        description=f"Workflow '{workflow.name}' changed from {old_status} to {req.status}",
        details={"old_status": old_status, "new_status": req.status},
    )
    db.add(log)
    db.commit()
    db.refresh(workflow)
    return WorkflowResponse.model_validate(workflow)


@router.delete("/workflows/{workflow_id}")
async def delete_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
):
    """Delete a workflow and all its steps."""
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow_name = workflow.name
    db.query(WorkflowStep).filter(WorkflowStep.workflow_id == workflow_id).delete()

    log = ActivityLog(
        action_type="workflow_deleted",
        description=f"Workflow '{workflow_name}' was deleted",
        details={"workflow_id": workflow_id, "workflow_name": workflow_name},
    )
    db.add(log)
    db.delete(workflow)
    db.commit()

    return {"detail": f"Workflow '{workflow_name}' deleted", "workflow_id": workflow_id}


@router.post("/workflows/{workflow_id}/execute")
async def execute_workflow(
    workflow_id: int,
    req: ExecuteWorkflowRequest,
    db: Session = Depends(get_db),
):
    """Execute all steps in a workflow with the given runtime context."""
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    if workflow.status == "paused":
        raise HTTPException(status_code=400, detail="Cannot run a paused workflow — resume it first")

    if not workflow.steps:
        raise HTTPException(status_code=400, detail="Workflow has no steps")

    context = req.context or {}
    results = await run_workflow(db, workflow, context)

    all_success = all(r["status"] == "success" for r in results)

    return {
        "workflow_id": workflow.id,
        "workflow_name": workflow.name,
        "status": "completed" if all_success else "partial_failure",
        "steps_executed": len(results),
        "results": results,
    }

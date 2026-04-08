from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.workflow import Workflow
from app.schemas.workflow import WorkflowResponse
from app.services.workflow_runner import run_workflow

router = APIRouter(prefix="/api")


class ExecuteWorkflowRequest(BaseModel):
    context: Optional[Dict] = None


@router.get("/workflows", response_model=List[WorkflowResponse])
async def list_workflows(db: Session = Depends(get_db)):
    workflows = db.query(Workflow).order_by(Workflow.updated_at.desc()).all()
    return [WorkflowResponse.model_validate(w) for w in workflows]


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

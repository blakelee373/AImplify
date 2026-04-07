from typing import List
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.workflow import Workflow
from app.schemas.workflow import WorkflowResponse, WorkflowUpdate

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

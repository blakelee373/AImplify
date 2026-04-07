from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.workflow import Workflow
from app.schemas.workflow import WorkflowResponse

router = APIRouter(prefix="/api")


@router.get("/workflows", response_model=List[WorkflowResponse])
async def list_workflows(db: Session = Depends(get_db)):
    workflows = db.query(Workflow).order_by(Workflow.updated_at.desc()).all()
    return [WorkflowResponse.model_validate(w) for w in workflows]

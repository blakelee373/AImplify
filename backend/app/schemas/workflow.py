from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime


class WorkflowStepResponse(BaseModel):
    id: str
    step_order: int
    action_type: str
    action_config: Optional[dict] = None
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class WorkflowResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    status: str
    trigger_type: Optional[str] = None
    trigger_description: Optional[str] = None
    trigger_config: Optional[dict] = None
    conditions: Optional[list] = None
    created_at: datetime
    updated_at: datetime
    steps: List[WorkflowStepResponse] = []

    model_config = {"from_attributes": True}


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None

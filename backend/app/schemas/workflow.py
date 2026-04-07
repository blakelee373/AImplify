from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel


class WorkflowStepResponse(BaseModel):
    id: int
    step_order: int
    action_type: str
    action_config: Optional[dict] = None
    description: Optional[str] = None

    class Config:
        from_attributes = True


class WorkflowResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    status: str
    trigger_type: Optional[str] = None
    trigger_config: Optional[dict] = None
    created_at: datetime
    updated_at: datetime
    steps: List[WorkflowStepResponse] = []

    class Config:
        from_attributes = True

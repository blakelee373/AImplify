from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    workflow_edit_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    message_id: str
    workflow_saved: bool = False


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    metadata: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationSummary(BaseModel):
    id: str
    title: Optional[str] = None
    workflow_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetail(BaseModel):
    id: str
    title: Optional[str] = None
    workflow_id: Optional[str] = None
    created_at: datetime
    messages: List[MessageResponse] = []

    model_config = {"from_attributes": True}

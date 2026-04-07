from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, model_validator


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[int] = None


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    metadata: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True

    @model_validator(mode="before")
    @classmethod
    def map_metadata_field(cls, data):
        """Map the DB's metadata_json column to the schema's metadata field."""
        if hasattr(data, "__dict__"):
            obj_dict = {k: v for k, v in data.__dict__.items() if not k.startswith("_")}
            if "metadata_json" in obj_dict:
                obj_dict["metadata"] = obj_dict.pop("metadata_json")
            return obj_dict
        return data


class ChatResponse(BaseModel):
    conversation_id: int
    message: MessageResponse


class ConversationSummary(BaseModel):
    id: int
    title: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConversationDetail(BaseModel):
    id: int
    title: Optional[str]
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse]

    class Config:
        from_attributes = True

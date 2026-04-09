from typing import Optional
from datetime import datetime

from pydantic import BaseModel


class BusinessMemoryCreate(BaseModel):
    category: str = "general"
    key: str
    value: str


class BusinessMemoryUpdate(BaseModel):
    category: Optional[str] = None
    key: Optional[str] = None
    value: Optional[str] = None


class BusinessMemoryResponse(BaseModel):
    id: int
    business_id: Optional[int] = None
    category: str
    key: str
    value: str
    source: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

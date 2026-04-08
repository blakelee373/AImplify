from typing import Optional, List
from pydantic import BaseModel


class IntegrationStatus(BaseModel):
    provider: str
    status: str
    scopes: List[str] = []
    connected_at: Optional[str] = None

    class Config:
        from_attributes = True

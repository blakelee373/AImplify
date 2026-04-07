"""Base integration class — all third-party connectors extend this (Phase 2+)."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class BaseIntegration(ABC):
    """Every integration (Gmail, Calendar, Twilio, etc.) implements this interface."""

    @abstractmethod
    async def connect(self, credentials: Dict[str, Any]) -> bool:
        """Establish connection with the third-party service."""
        ...

    @abstractmethod
    async def disconnect(self) -> bool:
        """Tear down the connection."""
        ...

    @abstractmethod
    async def test_connection(self) -> bool:
        """Verify the connection is still valid."""
        ...

    @abstractmethod
    async def execute(self, action: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run a specific action (send email, create event, etc.)."""
        ...

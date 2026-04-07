"""Base class for third-party tool connectors (Phase 2+)."""

from abc import ABC, abstractmethod


class BaseIntegration(ABC):
    """All integrations (Google Calendar, Twilio, etc.) extend this."""

    @abstractmethod
    async def connect(self, credentials: dict) -> bool:
        """Authenticate with the external service."""
        ...

    @abstractmethod
    async def execute(self, action: str, params: dict) -> dict:
        """Run an action against the external service."""
        ...

"""Base class for all third-party integrations."""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any


class BaseIntegration(ABC):
    name: str = ""
    display_name: str = ""
    description: str = ""
    auth_type: str = "oauth2"  # "oauth2" or "api_key"
    capabilities: List[str] = []

    @abstractmethod
    async def connect(self, business_id: Optional[str], auth_data: dict) -> bool:
        """Store credentials and mark as connected."""
        ...

    @abstractmethod
    async def disconnect(self, business_id: Optional[str]) -> bool:
        """Remove credentials and mark as disconnected."""
        ...

    @abstractmethod
    async def is_connected(self, business_id: Optional[str]) -> bool:
        """Check if this integration has valid stored credentials."""
        ...

    @abstractmethod
    async def execute_action(self, action_type: str, params: dict) -> Dict[str, Any]:
        """Run a specific action. Returns standardized result dict."""
        ...

    @abstractmethod
    async def test_connection(self, business_id: Optional[str]) -> bool:
        """Verify stored credentials still work."""
        ...

"""Route workflow actions to the correct integration."""

import logging
from datetime import datetime, timezone
from typing import Dict, Any

from app.services.integration_manager import get_integration_for_action

logger = logging.getLogger(__name__)


async def route_action(action_type: str, params: dict) -> Dict[str, Any]:
    """Execute an action by routing it to the appropriate integration.

    Returns a standardised result dict regardless of which integration handled it.
    """
    integration = get_integration_for_action(action_type)
    if not integration:
        return {
            "success": False,
            "action_type": action_type,
            "details": None,
            "error": "No integration registered for action '{}'".format(action_type),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    result = await integration.execute_action(action_type, params)
    result["timestamp"] = datetime.now(timezone.utc).isoformat()
    return result

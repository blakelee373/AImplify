"""Resolve {{variable}} placeholders in workflow templates."""

import logging
import re
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Fallback values when a variable can't be resolved
FALLBACKS = {
    "client_name": "there",
    "client_email": "",
    "client_phone": "",
    "appointment_time": "your upcoming appointment",
    "appointment_date": "your upcoming appointment",
    "service_type": "your appointment",
    "business_name": "our office",
    "business_phone": "",
    "review_link": "",
    "days_since_visit": "",
    "provider_name": "your provider",
}


def resolve_variables(template: str, context: Dict) -> str:
    """Replace all {{var}} placeholders with values from context.

    Falls back to sensible defaults rather than leaving raw placeholders.
    """
    def _replacer(match: re.Match) -> str:
        var_name = match.group(1).strip()
        value = context.get(var_name)
        if value is not None:
            return str(value)
        fallback = FALLBACKS.get(var_name, "")
        if fallback == "":
            logger.warning("Unresolved variable with no fallback: %s", var_name)
        return fallback

    return re.sub(r"\{\{(\w+)\}\}", _replacer, template)


def build_context_from_event(event_data: Dict, business_data: Optional[Dict] = None) -> Dict:
    """Build a variable context dict from a calendar event and business info."""
    ctx: Dict[str, str] = {}

    # From calendar event
    if event_data:
        attendees = event_data.get("attendees", [])
        if attendees:
            first = attendees[0]
            ctx["client_name"] = first.get("name") or first.get("email", "").split("@")[0]
            ctx["client_email"] = first.get("email", "")

        ctx["service_type"] = event_data.get("title", "")

        start = event_data.get("start_time")
        if start:
            try:
                dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                ctx["appointment_time"] = dt.strftime("%A, %B %d at %I:%M %p")
                ctx["appointment_date"] = dt.strftime("%B %d, %Y")
            except (ValueError, AttributeError):
                ctx["appointment_time"] = start
                ctx["appointment_date"] = start

    # From business info
    if business_data:
        ctx["business_name"] = business_data.get("name", "")
        ctx["business_phone"] = business_data.get("phone", "")
        ctx["review_link"] = business_data.get("review_link", "")

    return ctx

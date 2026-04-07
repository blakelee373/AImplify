"""Central event routing — integrations publish, workflows subscribe."""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from app.database import SessionLocal
from app.models.business_event import BusinessEvent
from app.models.workflow import Workflow

logger = logging.getLogger(__name__)

# Maps event_type patterns to trigger_config.event values
EVENT_TO_TRIGGER = {
    "appointment.created": "new_booking",
    "appointment.cancelled": "appointment_cancelled",
    "appointment.completed": "appointment_completed",
    "appointment.no_show": "no_show",
    "appointment.upcoming": "appointment_upcoming",
    "email.received.new_lead": "new_lead",
    "email.received.from_client": "email_from_client",
    "sms.received.confirmation": "sms_confirmation",
    "sms.received.reschedule": "sms_reschedule",
    "sms.received.cancellation": "sms_cancellation",
    "sms.received": "sms_received",
    "schedule.daily": "time_schedule",
    "schedule.weekly": "time_schedule",
    "workflow.completed": "workflow_completed",
    "client.inactive": "days_since_last_visit",
}


async def publish_event(
    event_type: str,
    source_integration: str,
    payload: Optional[Dict[str, Any]] = None,
    business_id: Optional[str] = None,
) -> str:
    """Persist an event and return its ID for processing."""
    db = SessionLocal()
    try:
        event = BusinessEvent(
            business_id=business_id,
            event_type=event_type,
            source_integration=source_integration,
            payload=payload or {},
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        logger.info("Event published: %s from %s", event_type, source_integration)
        return event.id
    finally:
        db.close()


def get_matching_workflows(event_type: str) -> List[Dict[str, Any]]:
    """Find all active workflows whose trigger matches this event type."""
    trigger_value = EVENT_TO_TRIGGER.get(event_type)
    if not trigger_value:
        return []

    db = SessionLocal()
    try:
        workflows = (
            db.query(Workflow)
            .filter(
                Workflow.status.in_(["active", "testing"]),
                Workflow.deleted_at.is_(None),
            )
            .all()
        )

        matches = []
        for w in workflows:
            cfg = w.trigger_config or {}
            wf_event = cfg.get("event", "")

            if wf_event == trigger_value:
                matches.append({
                    "id": w.id,
                    "name": w.name,
                    "status": w.status,
                    "trigger_config": w.trigger_config,
                    "conditions": w.conditions,
                })

            # Also match generic event types
            if event_type.startswith("appointment.") and wf_event == "new_booking" and event_type == "appointment.created":
                continue  # already matched above
            if event_type == "workflow.completed":
                # Check if workflow listens for a specific previous workflow
                prev_id = cfg.get("previous_workflow_id")
                if prev_id:
                    matches = [m for m in matches if True]  # filter handled in processor

        return matches
    finally:
        db.close()

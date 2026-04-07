"""Background service that polls Google Calendar for new/changed events."""

import logging
from datetime import datetime, timezone
from typing import List, Dict

from app.database import SessionLocal
from app.models.integration import Integration
from app.models.calendar_event import CalendarEventCache
from app.models.workflow import Workflow
from app.integrations.google_calendar import google_calendar
from app.services.workflow_executor import execute_workflow
from app.services.variable_resolver import build_context_from_event

logger = logging.getLogger(__name__)


async def poll_calendars():
    """Check all connected Google Calendars for new events.

    For each new event detected, fire any matching 'new_booking' workflows.
    """
    db = SessionLocal()
    try:
        integrations = (
            db.query(Integration)
            .filter(
                Integration.integration_type == "google_calendar",
                Integration.status == "connected",
            )
            .all()
        )

        for integration in integrations:
            try:
                await _poll_single_calendar(integration, db)
            except Exception as e:
                logger.error("Calendar poll failed for integration %s: %s", integration.id, e)
                integration.last_error = str(e)
                db.commit()
    finally:
        db.close()


async def _poll_single_calendar(integration: Integration, db):
    """Poll one calendar for changes since last check."""
    config = integration.config or {}
    last_poll_str = config.get("last_poll")

    if last_poll_str:
        since = datetime.fromisoformat(last_poll_str)
    else:
        since = datetime.now(timezone.utc)
        # First poll — just record the timestamp, don't fire on existing events
        config["last_poll"] = since.isoformat()
        integration.config = config
        db.commit()
        return

    # Fetch changed events from Google
    try:
        changed_events = google_calendar.get_new_events_since(since)
    except Exception as e:
        logger.error("Failed to fetch calendar events: %s", e)
        return

    new_events: List[Dict] = []

    for event in changed_events:
        google_id = event.get("event_id")
        if not google_id:
            continue

        # Check if we've seen this event before
        cached = (
            db.query(CalendarEventCache)
            .filter(CalendarEventCache.google_event_id == google_id)
            .first()
        )

        if not cached:
            # Brand new event — cache it and mark as new
            cache_entry = CalendarEventCache(
                business_id=integration.business_id,
                google_event_id=google_id,
                title=event.get("title"),
                start_time=_parse_dt(event.get("start_time")),
                end_time=_parse_dt(event.get("end_time")),
                attendee_email=(event.get("attendees", [{}])[0].get("email") if event.get("attendees") else None),
                attendee_name=(event.get("attendees", [{}])[0].get("name") if event.get("attendees") else None),
                status=event.get("status", "confirmed"),
                raw_data=event,
            )
            db.add(cache_entry)
            new_events.append(event)
        else:
            # Existing event — update cache
            cached.title = event.get("title")
            cached.start_time = _parse_dt(event.get("start_time"))
            cached.end_time = _parse_dt(event.get("end_time"))
            cached.status = event.get("status", cached.status)
            cached.raw_data = event

    # Update poll timestamp
    config["last_poll"] = datetime.now(timezone.utc).isoformat()
    integration.config = config
    integration.last_used_at = datetime.now(timezone.utc)
    db.commit()

    # Fire workflows for new events
    for event in new_events:
        if event.get("status") == "cancelled":
            continue
        await _fire_new_booking_workflows(event, integration.business_id)


async def _fire_new_booking_workflows(event_data: Dict, business_id=None):
    """Find and execute workflows triggered by a new booking."""
    db = SessionLocal()
    try:
        workflows = (
            db.query(Workflow)
            .filter(
                Workflow.status.in_(["active", "testing"]),
                Workflow.trigger_type == "event_based",
                Workflow.deleted_at.is_(None),
            )
            .all()
        )

        for workflow in workflows:
            trigger_cfg = workflow.trigger_config or {}
            if trigger_cfg.get("event") != "new_booking":
                continue

            context = build_context_from_event(event_data)
            context["trigger_type"] = "new_booking"

            logger.info("Firing workflow '%s' for new event '%s'", workflow.name, event_data.get("title"))
            await execute_workflow(
                workflow_id=workflow.id,
                trigger_context=context,
                dry_run=(workflow.status == "testing"),
                trigger_event_id=event_data.get("event_id"),
            )
    finally:
        db.close()


def _parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None

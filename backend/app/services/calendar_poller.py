"""Background service that polls Google Calendar and publishes events."""

import logging
from datetime import datetime, timezone
from typing import List, Dict

from app.database import SessionLocal
from app.models.integration import Integration
from app.models.calendar_event import CalendarEventCache
from app.integrations.google_calendar import google_calendar
from app.services.event_bus import publish_event
from app.services.event_processor import enqueue_event

logger = logging.getLogger(__name__)


async def poll_calendars():
    """Check all connected Google Calendars for new/changed events."""
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
    config = integration.config or {}
    last_poll_str = config.get("last_poll")

    if last_poll_str:
        since = datetime.fromisoformat(last_poll_str)
    else:
        since = datetime.now(timezone.utc)
        config["last_poll"] = since.isoformat()
        integration.config = config
        db.commit()
        return

    try:
        changed_events = google_calendar.get_new_events_since(since)
    except Exception as e:
        logger.error("Failed to fetch calendar events: %s", e)
        return

    for event in changed_events:
        google_id = event.get("event_id")
        if not google_id:
            continue

        cached = (
            db.query(CalendarEventCache)
            .filter(CalendarEventCache.google_event_id == google_id)
            .first()
        )

        if not cached:
            # New event
            _cache_event(db, integration.business_id, event)
            event_type = (
                "appointment.cancelled" if event.get("status") == "cancelled"
                else "appointment.created"
            )
        else:
            # Updated event
            _update_cache(cached, event)
            if event.get("status") == "cancelled" and cached.status != "cancelled":
                event_type = "appointment.cancelled"
            else:
                event_type = "appointment.updated"

        # Publish to event bus
        if event.get("status") != "cancelled" or event_type == "appointment.cancelled":
            event_id = await publish_event(
                event_type=event_type,
                source_integration="google_calendar",
                payload=event,
                business_id=integration.business_id,
            )
            await enqueue_event(event_id)

    config["last_poll"] = datetime.now(timezone.utc).isoformat()
    integration.config = config
    integration.last_used_at = datetime.now(timezone.utc)
    db.commit()


def _cache_event(db, business_id, event):
    attendees = event.get("attendees", [])
    cache_entry = CalendarEventCache(
        business_id=business_id,
        google_event_id=event.get("event_id"),
        title=event.get("title"),
        start_time=_parse_dt(event.get("start_time")),
        end_time=_parse_dt(event.get("end_time")),
        attendee_email=attendees[0].get("email") if attendees else None,
        attendee_name=attendees[0].get("name") if attendees else None,
        status=event.get("status", "confirmed"),
        raw_data=event,
    )
    db.add(cache_entry)


def _update_cache(cached, event):
    cached.title = event.get("title")
    cached.start_time = _parse_dt(event.get("start_time"))
    cached.end_time = _parse_dt(event.get("end_time"))
    cached.status = event.get("status", cached.status)
    cached.raw_data = event


def _parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None

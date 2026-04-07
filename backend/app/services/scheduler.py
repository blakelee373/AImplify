"""Time-based trigger scheduler — fires events for upcoming appointments and schedules."""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict

from app.database import SessionLocal
from app.models.workflow import Workflow
from app.models.calendar_event import CalendarEventCache
from app.services.event_bus import publish_event
from app.services.deduplication import is_duplicate

logger = logging.getLogger(__name__)


async def check_time_triggers():
    """Scan upcoming appointments and fire time-relative triggers.

    Called every minute by the background loop in main.py.
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        # Get all active workflows with time-based triggers
        workflows = (
            db.query(Workflow)
            .filter(
                Workflow.status.in_(["active", "testing"]),
                Workflow.trigger_type == "time_based",
                Workflow.deleted_at.is_(None),
            )
            .all()
        )

        if not workflows:
            return

        # Get upcoming events from cache (next 48 hours)
        upcoming_cutoff = now + timedelta(hours=48)
        events = (
            db.query(CalendarEventCache)
            .filter(
                CalendarEventCache.start_time >= now,
                CalendarEventCache.start_time <= upcoming_cutoff,
                CalendarEventCache.status != "cancelled",
            )
            .all()
        )

        for wf in workflows:
            cfg = wf.trigger_config or {}
            delay_minutes = cfg.get("delay_minutes", 0)
            direction = cfg.get("direction", "before")  # "before" or "after"

            for event in events:
                if not event.start_time:
                    continue

                # Calculate when this trigger should fire
                if direction == "before":
                    fire_at = event.start_time - timedelta(minutes=abs(delay_minutes))
                else:
                    fire_at = event.start_time + timedelta(minutes=abs(delay_minutes))

                # Check if we're within the 5-minute firing window
                window_start = fire_at - timedelta(minutes=2.5)
                window_end = fire_at + timedelta(minutes=2.5)

                if window_start <= now <= window_end:
                    dedup_key = "{}_{}".format(wf.id, event.google_event_id)

                    if is_duplicate(wf.id, dedup_key, cooldown_minutes=0):
                        continue

                    logger.info(
                        "Time trigger firing: workflow='%s' for event '%s'",
                        wf.name, event.title,
                    )

                    payload = {
                        "title": event.title,
                        "start_time": event.start_time.isoformat() if event.start_time else None,
                        "end_time": event.end_time.isoformat() if event.end_time else None,
                        "attendees": [],
                        "event_id": event.google_event_id,
                    }
                    if event.attendee_email:
                        payload["attendees"] = [{
                            "email": event.attendee_email,
                            "name": event.attendee_name or "",
                        }]

                    await publish_event(
                        event_type="appointment.upcoming",
                        source_integration="scheduler",
                        payload=payload,
                        business_id=event.business_id,
                    )

    finally:
        db.close()


async def check_completed_appointments():
    """Detect appointments that have ended (for post-appointment triggers)."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        buffer = timedelta(minutes=15)  # 15 min buffer for running over
        check_window = now - buffer

        # Events that ended in the last 20 minutes
        recent_end = now - timedelta(minutes=20)
        completed = (
            db.query(CalendarEventCache)
            .filter(
                CalendarEventCache.end_time >= recent_end,
                CalendarEventCache.end_time <= check_window,
                CalendarEventCache.status == "confirmed",
            )
            .all()
        )

        for event in completed:
            dedup_key = "completed_{}".format(event.google_event_id)
            if is_duplicate("__completed__", dedup_key, cooldown_minutes=0):
                continue

            payload = {
                "title": event.title,
                "start_time": event.start_time.isoformat() if event.start_time else None,
                "end_time": event.end_time.isoformat() if event.end_time else None,
                "event_id": event.google_event_id,
                "attendees": [],
            }
            if event.attendee_email:
                payload["attendees"] = [{
                    "email": event.attendee_email,
                    "name": event.attendee_name or "",
                }]

            await publish_event(
                event_type="appointment.completed",
                source_integration="scheduler",
                payload=payload,
                business_id=event.business_id,
            )

    finally:
        db.close()

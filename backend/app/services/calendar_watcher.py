"""Background calendar watcher — polls Google Calendar for event-triggered workflows."""

import asyncio
import logging
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# In-memory ordered dict of recently processed calendar event IDs per workflow.
# Key: workflow_id, Value: OrderedDict of {event_id: True}
_processed_ids: Dict[int, OrderedDict] = {}
_MAX_TRACKED_IDS = 200  # Per-workflow cap to prevent unbounded growth


def _parse_iso(value: str) -> Optional[datetime]:
    """Parse an ISO 8601 string to datetime, handling Z suffix and date-only values."""
    if not value:
        return None
    # Handle Z suffix (Python 3.9 fromisoformat doesn't support it)
    value = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _matches_calendar_filter(event: dict, calendar_filter: Optional[dict]) -> bool:
    """Check if a calendar event matches the trigger's filter criteria.

    All specified criteria must match (AND logic).
    Empty or None filter matches all events.
    """
    if not calendar_filter:
        return True

    summary = (event.get("summary") or "").lower()
    description = (event.get("description") or "").lower()
    attendees = [a.lower() for a in event.get("attendees", [])]

    if "summary_contains" in calendar_filter:
        if calendar_filter["summary_contains"].lower() not in summary:
            return False

    if "description_contains" in calendar_filter:
        if calendar_filter["description_contains"].lower() not in description:
            return False

    if "attendee_email" in calendar_filter:
        if calendar_filter["attendee_email"].lower() not in attendees:
            return False

    if "min_duration_minutes" in calendar_filter:
        try:
            start = _parse_iso(event["start"])
            end = _parse_iso(event["end"])
            if start and end:
                duration_minutes = (end - start).total_seconds() / 60
                if duration_minutes < calendar_filter["min_duration_minutes"]:
                    return False
        except (ValueError, KeyError, TypeError):
            return False

    return True


def _build_calendar_context(db, workflow, event: dict) -> dict:
    """Build runtime context for a calendar-triggered workflow run.

    Injects calendar event details plus the owner's email address so
    steps can reference the triggering event.
    """
    context = {
        "calendar_event_summary": event.get("summary", ""),
        "calendar_event_start": event.get("start", ""),
        "calendar_event_end": event.get("end", ""),
        "calendar_event_description": event.get("description", ""),
        "calendar_event_attendees": ", ".join(event.get("attendees", [])),
        "calendar_event_id": event.get("event_id", ""),
        "calendar_event_link": event.get("link", ""),
    }

    # Inject timezone from trigger config
    tz_name = (workflow.trigger_config or {}).get("timezone", "UTC")
    context["timezone"] = tz_name

    # Inject owner's Gmail address (same pattern as email watcher)
    try:
        from app.services.google_auth import get_google_credentials
        from googleapiclient.discovery import build as goog_build

        creds = get_google_credentials(db, provider="gmail")
        if creds:
            service = goog_build("gmail", "v1", credentials=creds)
            profile = service.users().getProfile(userId="me").execute()
            email = profile.get("emailAddress")
            if email:
                context["owner_email"] = email
                context["client_email"] = email
    except Exception:
        pass

    return context


async def calendar_watcher_loop() -> None:
    """Background task that polls Google Calendar every 60s for calendar-triggered workflows."""
    from app.database import SessionLocal
    from app.models.workflow import Workflow
    from app.models.activity_log import ActivityLog
    from app.services.workflow_runner import run_workflow
    from app.services.calendar import (
        list_recently_modified_events,
        list_events_starting_between,
    )

    # Stagger startup after email watcher (10s) and scheduler
    await asyncio.sleep(15)
    logger.info("Calendar watcher started")

    while True:
        try:
            db = SessionLocal()
            try:
                now = datetime.now(timezone.utc)

                # Find all active event-triggered workflows
                event_workflows = (
                    db.query(Workflow)
                    .filter(
                        Workflow.trigger_type == "event",
                        Workflow.status == "active",
                    )
                    .all()
                )

                # Filter to calendar event types
                calendar_workflows = [
                    w for w in event_workflows
                    if (w.trigger_config or {}).get("event_type") in (
                        "calendar_event_created",
                        "calendar_event_starting",
                    )
                ]

                for workflow in calendar_workflows:
                    try:
                        config = workflow.trigger_config or {}
                        event_type = config.get("event_type")
                        calendar_filter = config.get("calendar_filter", {})

                        # Fetch events based on trigger type
                        try:
                            if event_type == "calendar_event_created":
                                events = _poll_created_events(
                                    db, workflow, now
                                )
                            else:  # calendar_event_starting
                                events = _poll_starting_events(
                                    db, workflow, config, now
                                )
                        except ValueError:
                            logger.warning(
                                "Calendar watcher: Google Calendar not connected "
                                "for workflow %d",
                                workflow.id,
                            )
                            continue
                        except Exception as api_exc:
                            logger.warning(
                                "Calendar watcher: Calendar API error for "
                                "workflow %d: %s",
                                workflow.id,
                                api_exc,
                            )
                            continue

                        if not events:
                            continue

                        # Initialize processed dict for this workflow
                        if workflow.id not in _processed_ids:
                            _processed_ids[workflow.id] = OrderedDict()

                        processed = _processed_ids[workflow.id]
                        new_events_found = False

                        for event in events:
                            event_id = event["event_id"]
                            if event_id in processed:
                                continue

                            # Apply filter criteria
                            if not _matches_calendar_filter(event, calendar_filter):
                                continue

                            # Build context and run workflow
                            context = _build_calendar_context(
                                db, workflow, event
                            )

                            logger.info(
                                "Calendar watcher firing workflow %d (%s) "
                                "for event: %s",
                                workflow.id,
                                workflow.name,
                                event.get("summary", "(No title)"),
                            )

                            try:
                                results = await run_workflow(
                                    db, workflow, context
                                )
                                all_success = all(
                                    r["status"] == "success" for r in results
                                )

                                log = ActivityLog(
                                    workflow_id=workflow.id,
                                    action_type="calendar_triggered_run",
                                    description=(
                                        f"Calendar event '{event.get('summary', '(No title)')}' "
                                        f"triggered '{workflow.name}' — "
                                        + (
                                            "all steps succeeded"
                                            if all_success
                                            else "some steps failed"
                                        )
                                    ),
                                    details={
                                        "trigger": "calendar_watcher",
                                        "calendar_event_summary": event.get(
                                            "summary", ""
                                        ),
                                        "calendar_event_id": event_id,
                                        "calendar_event_start": event.get(
                                            "start", ""
                                        ),
                                        "steps_executed": len(results),
                                        "all_success": all_success,
                                    },
                                )
                                db.add(log)

                            except Exception as run_exc:
                                logger.exception(
                                    "Calendar watcher error running "
                                    "workflow %d: %s",
                                    workflow.id,
                                    run_exc,
                                )
                                log = ActivityLog(
                                    workflow_id=workflow.id,
                                    action_type="calendar_triggered_run",
                                    description=(
                                        f"Calendar-triggered run of "
                                        f"'{workflow.name}' failed: {run_exc}"
                                    ),
                                    details={
                                        "trigger": "calendar_watcher",
                                        "calendar_event_id": event_id,
                                        "error": str(run_exc),
                                    },
                                )
                                db.add(log)

                            # Mark as processed
                            processed[event_id] = True
                            new_events_found = True

                        # Trim oldest entries to prevent unbounded growth
                        while len(processed) > _MAX_TRACKED_IDS:
                            processed.popitem(last=False)

                        # Only update last_run_at when new events were processed
                        if new_events_found:
                            try:
                                workflow.last_run_at = now
                                workflow.updated_at = now
                                db.commit()
                            except Exception as adv_exc:
                                logger.exception(
                                    "Calendar watcher failed to update "
                                    "workflow %d: %s",
                                    workflow.id,
                                    adv_exc,
                                )
                                db.rollback()

                    except Exception as wf_exc:
                        logger.exception(
                            "Calendar watcher error processing "
                            "workflow %d: %s",
                            workflow.id,
                            wf_exc,
                        )

            finally:
                db.close()

        except Exception as exc:
            logger.exception("Calendar watcher loop error: %s", exc)

        await asyncio.sleep(60)


def _poll_created_events(db, workflow, now: datetime):
    """Poll for recently created/modified calendar events."""
    from app.services.calendar import list_recently_modified_events

    # Use last_run_at as the polling window start, with 60s overlap buffer
    # SQLite strips timezone info, so treat naive datetimes as UTC
    if workflow.last_run_at:
        last_run = workflow.last_run_at
        if last_run.tzinfo is None:
            last_run = last_run.replace(tzinfo=timezone.utc)
        updated_min = (last_run - timedelta(seconds=60)).isoformat()
    else:
        # First poll: look back 1 hour
        updated_min = (now - timedelta(hours=1)).isoformat()

    # Only match events in the future (avoid ancient events that were just edited)
    time_min = (now - timedelta(hours=1)).isoformat()

    return list_recently_modified_events(
        db, updated_min=updated_min, time_min=time_min
    )


def _poll_starting_events(db, workflow, config: dict, now: datetime):
    """Poll for events starting within the lead time window."""
    from app.services.calendar import list_events_starting_between

    lead_time = config.get("lead_time_minutes", 30)
    time_min = now.isoformat()
    time_max = (now + timedelta(minutes=lead_time)).isoformat()

    return list_events_starting_between(
        db, time_min=time_min, time_max=time_max
    )

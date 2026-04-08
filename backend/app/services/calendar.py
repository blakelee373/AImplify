"""Google Calendar integration — create events, list upcoming, check availability."""

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from app.services.google_auth import get_google_credentials


def _get_calendar_service(db: Session):
    """Build a Google Calendar API client or raise if not connected."""
    creds = get_google_credentials(db, provider="google_calendar")
    if creds is None:
        raise ValueError("Google Calendar is not connected. Please connect it in Settings.")
    return build("calendar", "v3", credentials=creds)


def create_event(
    db: Session,
    summary: str,
    start_time: str,
    end_time: str,
    description: Optional[str] = None,
    attendees: Optional[List[str]] = None,
) -> dict:
    """Create a Google Calendar event.

    start_time / end_time are ISO 8601 strings (e.g. '2026-04-10T14:00:00-05:00').
    Returns the created event's id, link, and times.
    """
    service = _get_calendar_service(db)

    event_body = {
        "summary": summary,
        "start": {"dateTime": start_time},
        "end": {"dateTime": end_time},
    }
    if description:
        event_body["description"] = description
    if attendees:
        event_body["attendees"] = [{"email": e} for e in attendees]

    send_updates = "all" if attendees else "none"
    event = service.events().insert(
        calendarId="primary", body=event_body, sendUpdates=send_updates
    ).execute()

    return {
        "event_id": event["id"],
        "link": event.get("htmlLink"),
        "summary": event.get("summary"),
        "start": event["start"].get("dateTime"),
        "end": event["end"].get("dateTime"),
    }


def list_upcoming_events(
    db: Session,
    max_results: int = 10,
) -> List[dict]:
    """Return the next N upcoming events from the user's primary calendar."""
    service = _get_calendar_service(db)

    now = datetime.now(timezone.utc).isoformat()
    result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=now,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events = []
    for item in result.get("items", []):
        start = item["start"].get("dateTime", item["start"].get("date"))
        end = item["end"].get("dateTime", item["end"].get("date"))
        events.append({
            "event_id": item["id"],
            "summary": item.get("summary", "(No title)"),
            "start": start,
            "end": end,
            "link": item.get("htmlLink"),
        })

    return events


def check_availability(
    db: Session,
    start_time: str,
    end_time: str,
) -> dict:
    """Check if a time slot is free on the user's primary calendar.

    Uses the freeBusy API for efficiency.
    Returns {"available": bool, "conflicts": [...]}.
    """
    service = _get_calendar_service(db)

    body = {
        "timeMin": start_time,
        "timeMax": end_time,
        "items": [{"id": "primary"}],
    }

    result = service.freebusy().query(body=body).execute()
    busy_slots = result.get("calendars", {}).get("primary", {}).get("busy", [])

    return {
        "available": len(busy_slots) == 0,
        "conflicts": [
            {"start": slot["start"], "end": slot["end"]}
            for slot in busy_slots
        ],
    }

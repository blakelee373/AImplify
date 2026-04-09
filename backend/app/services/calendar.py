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


def update_event(
    db: Session,
    event_id: str,
    summary: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    description: Optional[str] = None,
    attendees: Optional[List[str]] = None,
    add_attendees: Optional[List[str]] = None,
) -> dict:
    """Update an existing Google Calendar event.

    If add_attendees is provided, merges them with existing attendees.
    If attendees is provided, replaces all attendees.
    """
    service = _get_calendar_service(db)

    # Fetch existing event
    existing = service.events().get(calendarId="primary", eventId=event_id).execute()

    patch_body = {}
    if summary:
        patch_body["summary"] = summary
    if start_time:
        patch_body["start"] = {"dateTime": start_time}
    if end_time:
        patch_body["end"] = {"dateTime": end_time}
    if description is not None:
        patch_body["description"] = description

    if add_attendees:
        current = existing.get("attendees", [])
        current_emails = {a["email"] for a in current}
        for email in add_attendees:
            if email not in current_emails:
                current.append({"email": email})
        patch_body["attendees"] = current
    elif attendees is not None:
        patch_body["attendees"] = [{"email": e} for e in attendees]

    has_attendees = "attendees" in patch_body
    send_updates = "all" if has_attendees else "none"

    event = service.events().patch(
        calendarId="primary", eventId=event_id, body=patch_body,
        sendUpdates=send_updates,
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
    time_min: Optional[str] = None,
    time_max: Optional[str] = None,
) -> List[dict]:
    """Return upcoming events from the user's primary calendar.

    If time_min/time_max are provided, only events within that range are returned.
    """
    service = _get_calendar_service(db)

    now = datetime.now(timezone.utc).isoformat()
    params = {
        "calendarId": "primary",
        "timeMin": time_min or now,
        "maxResults": max_results,
        "singleEvents": True,
        "orderBy": "startTime",
    }
    if time_max:
        params["timeMax"] = time_max
    result = service.events().list(**params).execute()

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


def _parse_event_detail(item: dict) -> dict:
    """Extract full event details from a Google Calendar API event item."""
    start = item["start"].get("dateTime", item["start"].get("date"))
    end = item["end"].get("dateTime", item["end"].get("date"))
    attendees = [
        a["email"] for a in item.get("attendees", []) if "email" in a
    ]
    return {
        "event_id": item["id"],
        "summary": item.get("summary", "(No title)"),
        "start": start,
        "end": end,
        "description": item.get("description", ""),
        "attendees": attendees,
        "link": item.get("htmlLink"),
        "updated": item.get("updated"),
    }


def list_recently_modified_events(
    db: Session,
    updated_min: str,
    time_min: Optional[str] = None,
    max_results: int = 25,
) -> List[dict]:
    """Return events modified since updated_min (ISO 8601).

    Used by the calendar watcher to detect new/changed events.
    """
    service = _get_calendar_service(db)

    now = datetime.now(timezone.utc).isoformat()
    result = service.events().list(
        calendarId="primary",
        updatedMin=updated_min,
        timeMin=time_min or now,
        maxResults=max_results,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    return [_parse_event_detail(item) for item in result.get("items", [])]


def list_events_starting_between(
    db: Session,
    time_min: str,
    time_max: str,
    max_results: int = 25,
) -> List[dict]:
    """Return events starting within a time window.

    Used by the calendar watcher for 'N minutes before' triggers.
    """
    service = _get_calendar_service(db)

    result = service.events().list(
        calendarId="primary",
        timeMin=time_min,
        timeMax=time_max,
        maxResults=max_results,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    return [_parse_event_detail(item) for item in result.get("items", [])]


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

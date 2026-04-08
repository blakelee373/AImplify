"""Action endpoints — manually trigger agent actions like sending emails and calendar ops."""

from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.activity_log import ActivityLog
from app.services.gmail import send_email
from app.services.calendar import create_event, list_upcoming_events, check_availability

router = APIRouter(prefix="/api")


# ── Email ────────────────────────────────────────────────────────────────────


class SendEmailRequest(BaseModel):
    recipient: str
    subject: str
    body: str


@router.post("/actions/send-email")
async def action_send_email(
    req: SendEmailRequest,
    db: Session = Depends(get_db),
):
    """Send an email through the connected Gmail account."""
    try:
        result = send_email(db, req.recipient, req.subject, req.body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gmail API error: {e}")

    log = ActivityLog(
        action_type="send_email",
        description=f"Sent email to {req.recipient}: {req.subject}",
        details={
            "recipient": req.recipient,
            "subject": req.subject,
            "gmail_message_id": result["message_id"],
        },
    )
    db.add(log)
    db.commit()

    return {
        "status": "sent",
        "recipient": req.recipient,
        "subject": req.subject,
        "gmail_message_id": result["message_id"],
    }


# ── Calendar ─────────────────────────────────────────────────────────────────


class CreateEventRequest(BaseModel):
    summary: str
    start_time: str
    end_time: str
    description: Optional[str] = None
    attendees: Optional[List[str]] = None


class CheckAvailabilityRequest(BaseModel):
    start_time: str
    end_time: str


@router.post("/actions/create-event")
async def action_create_event(
    req: CreateEventRequest,
    db: Session = Depends(get_db),
):
    """Create a Google Calendar event."""
    try:
        result = create_event(
            db,
            summary=req.summary,
            start_time=req.start_time,
            end_time=req.end_time,
            description=req.description,
            attendees=req.attendees,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Calendar API error: {e}")

    log = ActivityLog(
        action_type="create_event",
        description=f"Created calendar event: {req.summary}",
        details={
            "summary": req.summary,
            "start": req.start_time,
            "end": req.end_time,
            "event_id": result["event_id"],
        },
    )
    db.add(log)
    db.commit()

    return result


# ── Activity Log ─────────────────────────────────────────────────────────────


@router.get("/activity-logs")
async def get_activity_logs(
    limit: int = Query(default=20, le=100),
    db: Session = Depends(get_db),
):
    """Return recent activity logs, newest first."""
    logs = (
        db.query(ActivityLog)
        .order_by(ActivityLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": log.id,
            "action_type": log.action_type,
            "description": log.description,
            "details": log.details,
            "workflow_id": log.workflow_id,
            "created_at": log.created_at.isoformat() + "Z",
        }
        for log in logs
    ]


@router.get("/actions/upcoming-events")
async def action_upcoming_events(
    max_results: int = Query(default=10, le=50),
    db: Session = Depends(get_db),
):
    """List upcoming events from the connected Google Calendar."""
    try:
        events = list_upcoming_events(db, max_results=max_results)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Calendar API error: {e}")

    return {"events": events, "count": len(events)}


@router.post("/actions/check-availability")
async def action_check_availability(
    req: CheckAvailabilityRequest,
    db: Session = Depends(get_db),
):
    """Check if a time slot is available on the connected Google Calendar."""
    try:
        result = check_availability(db, req.start_time, req.end_time)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Calendar API error: {e}")

    return result

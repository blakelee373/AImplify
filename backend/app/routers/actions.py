"""Action endpoints — manually trigger agent actions like sending emails."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.activity_log import ActivityLog
from app.services.gmail import send_email

router = APIRouter(prefix="/api")


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

    # Log the action
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

"""Gmail integration — send emails through the user's connected Google account."""

import base64
from email.mime.text import MIMEText
from typing import Optional

from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from app.services.google_auth import get_google_credentials


def send_email(
    db: Session,
    recipient: str,
    subject: str,
    body: str,
) -> dict:
    """Send an email via the user's Gmail account.

    Returns a dict with message id and thread id on success.
    Raises ValueError if Google is not connected.
    Raises Exception on Gmail API errors.
    """
    creds = get_google_credentials(db, provider="gmail")
    if creds is None:
        raise ValueError("Gmail is not connected. Please connect it in Settings.")

    service = build("gmail", "v1", credentials=creds)

    message = MIMEText(body)
    message["to"] = recipient
    message["subject"] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    sent = (
        service.users()
        .messages()
        .send(userId="me", body={"raw": raw})
        .execute()
    )

    return {"message_id": sent["id"], "thread_id": sent.get("threadId")}

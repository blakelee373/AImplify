"""Gmail integration — send emails through the user's connected Google account."""

import base64
from email.mime.text import MIMEText
from typing import List, Optional, Union

from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from app.services.google_auth import get_google_credentials


def send_email(
    db: Session,
    recipient: Union[str, List[str]],
    subject: str,
    body: str,
    cc: Optional[Union[str, List[str]]] = None,
    bcc: Optional[Union[str, List[str]]] = None,
) -> dict:
    """Send an email via the user's Gmail account.

    recipient can be a single email string or a list of emails.
    cc and bcc are optional, each a single email or list of emails.

    Returns a dict with message id and thread id on success.
    Raises ValueError if Google is not connected.
    Raises Exception on Gmail API errors.
    """
    creds = get_google_credentials(db, provider="gmail")
    if creds is None:
        raise ValueError("Gmail is not connected. Please connect it in Settings.")

    service = build("gmail", "v1", credentials=creds)

    # Normalize to comma-separated strings
    if isinstance(recipient, list):
        to_str = ", ".join(recipient)
    else:
        to_str = recipient

    message = MIMEText(body)
    message["to"] = to_str
    message["subject"] = subject

    if cc:
        message["cc"] = ", ".join(cc) if isinstance(cc, list) else cc
    if bcc:
        message["bcc"] = ", ".join(bcc) if isinstance(bcc, list) else bcc

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    sent = (
        service.users()
        .messages()
        .send(userId="me", body={"raw": raw})
        .execute()
    )

    return {"message_id": sent["id"], "thread_id": sent.get("threadId")}

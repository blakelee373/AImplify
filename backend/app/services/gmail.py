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


def list_messages(
    db: Session,
    query: str,
    max_results: int = 10,
) -> List[dict]:
    """Search the user's Gmail inbox using a query string.

    Returns a list of message dicts (id, threadId) matching the query,
    or an empty list if no results are found.
    Raises ValueError if Gmail is not connected.
    """
    creds = get_google_credentials(db, provider="gmail")
    if creds is None:
        raise ValueError("Gmail is not connected. Please connect it in Settings.")

    service = build("gmail", "v1", credentials=creds)

    response = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )

    return response.get("messages", [])


def get_message(
    db: Session,
    message_id: str,
) -> dict:
    """Get a single Gmail message's details by ID.

    Returns a dict with id, thread_id, snippet, sender, subject, to, date,
    and internal_date fields.
    Raises ValueError if Gmail is not connected.
    """
    creds = get_google_credentials(db, provider="gmail")
    if creds is None:
        raise ValueError("Gmail is not connected. Please connect it in Settings.")

    service = build("gmail", "v1", credentials=creds)

    msg = (
        service.users()
        .messages()
        .get(
            userId="me",
            id=message_id,
            format="metadata",
            metadataHeaders=["From", "Subject", "To", "Date"],
        )
        .execute()
    )

    # Parse headers into a flat dict
    headers = {}
    for header in msg.get("payload", {}).get("headers", []):
        headers[header["name"]] = header["value"]

    return {
        "id": msg["id"],
        "thread_id": msg.get("threadId"),
        "snippet": msg.get("snippet", ""),
        "sender": headers.get("From", ""),
        "subject": headers.get("Subject", ""),
        "to": headers.get("To", ""),
        "date": headers.get("Date", ""),
        "internal_date": int(msg.get("internalDate", 0)),
    }


def mark_as_read(db: Session, message_id: str) -> None:
    """Mark a Gmail message as read by removing the UNREAD label.

    This prevents email-triggered workflows from re-processing the same
    message on subsequent poll cycles when the query includes 'is:unread'.
    """
    creds = get_google_credentials(db, provider="gmail")
    if creds is None:
        raise ValueError("Gmail is not connected. Please connect it in Settings.")

    service = build("gmail", "v1", credentials=creds)

    service.users().messages().modify(
        userId="me",
        id=message_id,
        body={"removeLabelIds": ["UNREAD"]},
    ).execute()

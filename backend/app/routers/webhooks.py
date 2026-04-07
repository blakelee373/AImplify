"""Inbound webhook endpoints — Twilio SMS replies."""

import logging
import re
from typing import Optional

from fastapi import APIRouter, Request, Response

from app.services.event_bus import publish_event
from app.services.event_processor import enqueue_event

logger = logging.getLogger(__name__)
router = APIRouter()

CONFIRM_WORDS = {"c", "yes", "confirm", "confirmed", "see you", "sounds good", "y"}
RESCHEDULE_WORDS = {"r", "reschedule", "change", "move", "different time"}
CANCEL_WORDS = {"cancel", "can't make it", "not coming", "no"}


def _classify_sms(body: str) -> str:
    """Determine intent from inbound SMS body."""
    text = body.strip().lower()

    if text in CONFIRM_WORDS or any(w in text for w in CONFIRM_WORDS):
        return "sms.received.confirmation"
    if text in RESCHEDULE_WORDS or any(w in text for w in RESCHEDULE_WORDS):
        return "sms.received.reschedule"
    if text in CANCEL_WORDS or any(w in text for w in CANCEL_WORDS):
        return "sms.received.cancellation"
    return "sms.received"


@router.post("/webhooks/twilio/incoming")
async def twilio_incoming_sms(request: Request):
    """Handle inbound SMS from Twilio.

    Twilio POSTs form data with From, Body, etc.
    We must respond quickly with a 200 (or TwiML).
    """
    form = await request.form()
    from_phone = form.get("From", "")
    body = form.get("Body", "")
    message_sid = form.get("MessageSid", "")

    logger.info("Inbound SMS from %s: %s", from_phone, body[:50])

    # Classify the message
    event_type = _classify_sms(body)

    payload = {
        "from_phone": from_phone,
        "body": body,
        "message_sid": message_sid,
    }

    # Publish the specific event
    event_id = await publish_event(
        event_type=event_type,
        source_integration="twilio_sms",
        payload=payload,
    )
    await enqueue_event(event_id)

    # Also publish generic sms.received if it was a specific intent
    if event_type != "sms.received":
        generic_id = await publish_event(
            event_type="sms.received",
            source_integration="twilio_sms",
            payload=payload,
        )
        await enqueue_event(generic_id)

    # Return empty TwiML (no auto-reply for now)
    return Response(
        content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
        media_type="application/xml",
    )

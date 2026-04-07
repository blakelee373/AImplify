"""Inbound webhook endpoints — Twilio, Square, Stripe, Boulevard, generic."""

import logging
from typing import Optional

from fastapi import APIRouter, Request, Response, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.webhook_config import WebhookConfig
from app.services.event_bus import publish_event
from app.services.event_processor import enqueue_event
from app.integrations.webhook.generic_webhook import process_incoming_webhook

logger = logging.getLogger(__name__)
router = APIRouter()

CONFIRM_WORDS = {"c", "yes", "confirm", "confirmed", "see you", "sounds good", "y"}
RESCHEDULE_WORDS = {"r", "reschedule", "change", "move", "different time"}
CANCEL_WORDS = {"cancel", "can't make it", "not coming", "no"}


def _classify_sms(body: str) -> str:
    text = body.strip().lower()
    if text in CONFIRM_WORDS or any(w in text for w in CONFIRM_WORDS):
        return "sms.received.confirmation"
    if text in RESCHEDULE_WORDS or any(w in text for w in RESCHEDULE_WORDS):
        return "sms.received.reschedule"
    if text in CANCEL_WORDS or any(w in text for w in CANCEL_WORDS):
        return "sms.received.cancellation"
    return "sms.received"


# --- Twilio ---

@router.post("/webhooks/twilio/incoming")
async def twilio_incoming_sms(request: Request):
    form = await request.form()
    from_phone = form.get("From", "")
    body = form.get("Body", "")
    message_sid = form.get("MessageSid", "")
    logger.info("Inbound SMS from %s: %s", from_phone, body[:50])

    event_type = _classify_sms(body)
    payload = {"from_phone": from_phone, "body": body, "message_sid": message_sid}
    event_id = await publish_event(event_type=event_type, source_integration="twilio_sms", payload=payload)
    await enqueue_event(event_id)
    if event_type != "sms.received":
        gid = await publish_event(event_type="sms.received", source_integration="twilio_sms", payload=payload)
        await enqueue_event(gid)
    return Response(content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>', media_type="application/xml")


# --- Square ---

@router.post("/webhooks/square")
async def square_webhook(request: Request):
    body = await request.json()
    event_map = {"booking.created": "appointment.created", "booking.updated": "appointment.updated", "booking.cancelled": "appointment.cancelled"}
    mapped = event_map.get(body.get("type", ""))
    if mapped:
        eid = await publish_event(event_type=mapped, source_integration="square_appointments", payload=body.get("data", {}))
        await enqueue_event(eid)
    return {"status": "ok"}


# --- Stripe ---

@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    body = await request.json()
    event_map = {"invoice.payment_succeeded": "payment.received", "invoice.payment_failed": "payment.failed"}
    mapped = event_map.get(body.get("type", ""))
    if mapped:
        eid = await publish_event(event_type=mapped, source_integration="stripe", payload=body.get("data", {}).get("object", {}))
        await enqueue_event(eid)
    return {"status": "ok"}


# --- Boulevard ---

@router.post("/webhooks/boulevard")
async def boulevard_webhook(request: Request):
    body = await request.json()
    eid = await publish_event(event_type="appointment.updated", source_integration="boulevard", payload=body)
    await enqueue_event(eid)
    return {"status": "ok"}


# --- Generic webhook configs ---

class WebhookCreate(BaseModel):
    name: str
    description: Optional[str] = None
    expected_source: Optional[str] = None


@router.get("/webhooks/configs")
async def list_webhook_configs(db: Session = Depends(get_db)):
    configs = db.query(WebhookConfig).filter(WebhookConfig.is_active == True).all()  # noqa: E712
    from app.config import BACKEND_URL
    return [
        {
            "id": c.id,
            "name": c.name,
            "description": c.description,
            "expected_source": c.expected_source,
            "webhook_url": "{}/api/webhooks/incoming/{}".format(BACKEND_URL, c.webhook_key),
            "receive_count": c.receive_count,
            "last_received_at": c.last_received_at.isoformat() if c.last_received_at else None,
        }
        for c in configs
    ]


@router.post("/webhooks/configs")
async def create_webhook_config(data: WebhookCreate, db: Session = Depends(get_db)):
    config = WebhookConfig(name=data.name, description=data.description, expected_source=data.expected_source)
    db.add(config)
    db.commit()
    db.refresh(config)
    from app.config import BACKEND_URL
    return {
        "id": config.id,
        "name": config.name,
        "webhook_key": config.webhook_key,
        "webhook_url": "{}/api/webhooks/incoming/{}".format(BACKEND_URL, config.webhook_key),
    }


@router.delete("/webhooks/configs/{config_id}")
async def delete_webhook_config(config_id: str, db: Session = Depends(get_db)):
    config = db.query(WebhookConfig).filter(WebhookConfig.id == config_id).first()
    if not config:
        raise HTTPException(404, "Webhook config not found")
    config.is_active = False
    db.commit()
    return {"status": "deleted"}


@router.post("/webhooks/incoming/{webhook_key}")
async def receive_generic_webhook(webhook_key: str, request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = dict(await request.form())
    result = await process_incoming_webhook(webhook_key, payload)
    return result

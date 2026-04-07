"""Generic webhook receiver — accepts data from any external tool and uses AI to parse it."""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from app.database import SessionLocal
from app.models.integration import Integration
from app.services.ai_engine import client as ai_client
from app.services.event_bus import publish_event
from app.services.event_processor import enqueue_event

logger = logging.getLogger(__name__)

PARSE_PROMPT = """Given this incoming webhook payload:
{payload}

This webhook is configured as: "{name}" from "{source}".

Extract the following information if available:
- Is this a new lead/contact form submission?
- Client name, email, phone
- What service or topic they're interested in
- Any message or notes

Respond with JSON only:
{{
  "event_type": "new_lead | form_submission | status_update | notification | unknown",
  "client": {{
    "name": "",
    "email": "",
    "phone": ""
  }},
  "details": {{
    "service_interested_in": "",
    "message": "",
    "source": ""
  }},
  "raw_summary": "One sentence description"
}}"""


async def process_incoming_webhook(
    webhook_key: str,
    payload: dict,
) -> Dict[str, Any]:
    """Receive a webhook, parse it with AI, and publish an event."""
    from app.models.webhook_config import WebhookConfig

    db = SessionLocal()
    try:
        config = db.query(WebhookConfig).filter(
            WebhookConfig.webhook_key == webhook_key,
            WebhookConfig.is_active == True,  # noqa: E712
        ).first()

        if not config:
            return {"error": "Invalid webhook key"}

        # Update stats
        config.last_received_at = datetime.now(timezone.utc)
        config.receive_count = (config.receive_count or 0) + 1
        db.commit()

        # Parse with AI
        parsed = await _parse_payload(payload, config.name, config.expected_source or "unknown")

        # Publish event
        event_payload = {
            "webhook_config_id": config.id,
            "webhook_name": config.name,
            "parsed": parsed,
            "raw_payload": payload,
        }

        # Map parsed event type
        ai_event_type = parsed.get("event_type", "unknown")
        if ai_event_type == "new_lead":
            event_type = "email.received.new_lead"
        elif ai_event_type == "form_submission":
            event_type = "webhook.received"
        else:
            event_type = "webhook.received"

        # Add client info to payload for variable resolver
        client_info = parsed.get("client", {})
        if client_info.get("name"):
            parts = client_info["name"].split(" ", 1)
            event_payload["client_name"] = client_info["name"]
            event_payload["client_first_name"] = parts[0]
            event_payload["client_last_name"] = parts[1] if len(parts) > 1 else ""
        if client_info.get("email"):
            event_payload["client_email"] = client_info["email"]
        if client_info.get("phone"):
            event_payload["client_phone"] = client_info["phone"]

        event_id = await publish_event(
            event_type=event_type,
            source_integration="webhook",
            payload=event_payload,
            business_id=config.business_id,
        )
        await enqueue_event(event_id)

        return {"status": "received", "parsed": parsed}

    except Exception as e:
        logger.error("Webhook processing error: %s", e)
        return {"error": str(e)}
    finally:
        db.close()


async def _parse_payload(payload: dict, name: str, source: str) -> dict:
    """Use Claude to intelligently parse the webhook payload."""
    try:
        prompt = PARSE_PROMPT.format(
            payload=json.dumps(payload, indent=2)[:3000],  # cap payload size
            name=name,
            source=source,
        )
        response = await ai_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system="You are a JSON parser. Return ONLY valid JSON, no other text.",
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        return json.loads(text)
    except Exception as e:
        logger.error("AI webhook parsing failed: %s", e)
        return {"event_type": "unknown", "client": {}, "details": {}, "raw_summary": "Unparsed webhook"}

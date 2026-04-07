"""Central registry for all integrations."""

from typing import Dict, List, Optional, Any

from app.database import SessionLocal
from app.models.integration import Integration
from app.integrations.google_calendar import google_calendar
from app.integrations.gmail import gmail
from app.integrations.twilio_sms import twilio_sms
from app.integrations.booking.square import square_appointments
from app.integrations.booking.boulevard import boulevard
from app.integrations.booking.vagaro import vagaro
from app.integrations.crm.hubspot import hubspot
from app.integrations.payments.stripe_integration import stripe_integration
from app.integrations.reviews.google_reviews import google_reviews
from app.integrations.base import BaseIntegration

REGISTRY: Dict[str, BaseIntegration] = {
    "google_calendar": google_calendar,
    "gmail": gmail,
    "twilio_sms": twilio_sms,
    "square_appointments": square_appointments,
    "boulevard": boulevard,
    "vagaro": vagaro,
    "hubspot": hubspot,
    "stripe": stripe_integration,
    "google_reviews": google_reviews,
}

ACTION_TO_INTEGRATION = {
    # SMS
    "send_sms": "twilio_sms",
    "send_template_sms": "twilio_sms",
    "send_review_request": "twilio_sms",
    # Email
    "send_email": "gmail",
    "send_template_email": "gmail",
    # Calendar
    "read_upcoming_events": "google_calendar",
    "create_calendar_event": "google_calendar",
    "check_availability": "google_calendar",
    # CRM
    "create_crm_contact": "hubspot",
    "update_crm_contact": "hubspot",
    "log_crm_activity": "hubspot",
    "add_crm_note": "hubspot",
    "add_to_crm_list": "hubspot",
    "create_crm_deal": "hubspot",
    "update_crm_deal_stage": "hubspot",
    # Payments
    "send_invoice": "stripe",
    "send_payment_link": "stripe",
    "send_payment_reminder": "stripe",
    # Booking
    "create_appointment": "square_appointments",
    "cancel_appointment": "square_appointments",
}


def get_integration(name: str) -> Optional[BaseIntegration]:
    return REGISTRY.get(name)


def get_integration_for_action(action_type: str) -> Optional[BaseIntegration]:
    name = ACTION_TO_INTEGRATION.get(action_type)
    if name:
        return REGISTRY.get(name)
    return None


def list_available_integrations() -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        statuses = {}
        for row in db.query(Integration).all():
            statuses[row.integration_type] = row.status

        result = []
        for name, integration in REGISTRY.items():
            result.append({
                "name": integration.name,
                "display_name": integration.display_name,
                "description": integration.description,
                "auth_type": integration.auth_type,
                "capabilities": integration.capabilities,
                "status": statuses.get(name, "disconnected"),
            })
        return result
    finally:
        db.close()


async def get_connected_integration_names() -> List[str]:
    db = SessionLocal()
    try:
        rows = (
            db.query(Integration.integration_type)
            .filter(Integration.status == "connected")
            .all()
        )
        return [r[0] for r in rows]
    finally:
        db.close()

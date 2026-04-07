"""Automatically sync booking data to CRM (HubSpot)."""

import logging
from typing import Optional

from app.database import SessionLocal
from app.models.client_cache import ClientCache
from app.integrations.crm.hubspot import hubspot

logger = logging.getLogger(__name__)


async def sync_client_to_crm(
    email: Optional[str],
    first_name: str,
    last_name: str,
    phone: Optional[str] = None,
    activity_description: Optional[str] = None,
) -> Optional[dict]:
    """Ensure a client exists in the CRM and optionally log an activity."""
    if not await hubspot.is_connected(None):
        return None

    if not email and not phone:
        logger.debug("Cannot sync to CRM without email or phone")
        return None

    try:
        contact = hubspot.find_or_create_contact(
            email=email or "",
            first_name=first_name,
            last_name=last_name,
            phone=phone,
        )

        if activity_description and contact.get("id"):
            hubspot.log_activity(
                contact_id=contact["id"],
                activity_type="AImplify",
                description=activity_description,
            )

        return contact

    except Exception as e:
        logger.error("CRM sync failed: %s", e)
        return None


def cache_client(
    external_id: str,
    source_platform: str,
    first_name: str,
    last_name: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    business_id: Optional[str] = None,
):
    """Upsert a client in the local cache."""
    db = SessionLocal()
    try:
        cached = db.query(ClientCache).filter(
            ClientCache.external_client_id == external_id,
            ClientCache.source_platform == source_platform,
        ).first()

        if cached:
            cached.first_name = first_name
            cached.last_name = last_name
            if email:
                cached.email = email
            if phone:
                cached.phone = phone
        else:
            cached = ClientCache(
                external_client_id=external_id,
                source_platform=source_platform,
                business_id=business_id,
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=phone,
            )
            db.add(cached)

        db.commit()
    finally:
        db.close()

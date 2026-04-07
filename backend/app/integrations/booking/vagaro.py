"""Vagaro integration (limited API — stub implementation)."""

import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from app.database import SessionLocal
from app.models.integration import Integration
from app.utils.encryption import encrypt_credentials
from app.integrations.booking.base_booking import BaseBookingIntegration
from app.integrations.booking.models import (
    StandardAppointment, StandardClient, StandardService,
    StandardProvider, TimeSlot,
)

logger = logging.getLogger(__name__)


class VagaroIntegration(BaseBookingIntegration):
    name = "vagaro"
    display_name = "Vagaro"
    description = "Sync appointments from Vagaro (limited API — use with Google Calendar as backup)"
    auth_type = "api_key"
    capabilities = ["read_appointments"]

    async def connect(self, business_id: Optional[str], auth_data: dict) -> bool:
        db = SessionLocal()
        try:
            integ = db.query(Integration).filter(Integration.integration_type == self.name).first()
            if not integ:
                integ = Integration(integration_type=self.name, business_id=business_id)
                db.add(integ)
            integ.credentials = encrypt_credentials(auth_data)
            integ.status = "connected"
            integ.connected_at = datetime.now(timezone.utc)
            db.commit()
            return True
        except Exception as e:
            logger.error("Vagaro connect failed: %s", e)
            return False
        finally:
            db.close()

    async def disconnect(self, business_id: Optional[str]) -> bool:
        db = SessionLocal()
        try:
            integ = db.query(Integration).filter(Integration.integration_type == self.name).first()
            if integ:
                integ.credentials = None
                integ.status = "disconnected"
                db.commit()
            return True
        finally:
            db.close()

    async def is_connected(self, business_id: Optional[str]) -> bool:
        db = SessionLocal()
        try:
            return db.query(Integration).filter(
                Integration.integration_type == self.name, Integration.status == "connected"
            ).first() is not None
        finally:
            db.close()

    async def test_connection(self, business_id: Optional[str]) -> bool:
        return await self.is_connected(business_id)

    async def execute_action(self, action_type: str, params: dict) -> Dict[str, Any]:
        return {"success": False, "action_type": action_type, "details": None, "error": "Vagaro has limited API access. Use Google Calendar as backup."}

    # Stubs — Vagaro's public API is very limited
    async def get_upcoming_appointments(self, business_id, days_ahead=7): return []
    async def get_appointment_detail(self, business_id, appointment_id): return StandardAppointment(id=appointment_id)
    async def get_todays_appointments(self, business_id): return []
    async def get_new_appointments_since(self, business_id, since): return []
    async def get_cancelled_appointments_since(self, business_id, since): return []
    async def get_client(self, business_id, client_id): return StandardClient(id=client_id, first_name="", last_name="")
    async def search_clients(self, business_id, query): return []
    async def get_client_appointment_history(self, business_id, client_id): return []
    async def get_services(self, business_id): return []
    async def get_providers(self, business_id): return []
    async def create_appointment(self, business_id, client_id, service_id, provider_id, start_time, notes=None): return StandardAppointment(id="")
    async def cancel_appointment(self, business_id, appointment_id, reason=None): return False
    async def get_available_slots(self, business_id, service_id, provider_id=None, date_from=None, date_to=None): return []


vagaro = VagaroIntegration()

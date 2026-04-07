"""Square Appointments integration via Square SDK."""

import logging
from datetime import datetime, timedelta, timezone, date
from typing import Optional, List, Dict, Any

from app.database import SessionLocal
from app.models.integration import Integration
from app.utils.encryption import encrypt_credentials, decrypt_credentials
from app.integrations.booking.base_booking import BaseBookingIntegration
from app.integrations.booking.models import (
    StandardAppointment, StandardClient, StandardService,
    StandardProvider, TimeSlot,
)

logger = logging.getLogger(__name__)


class SquareIntegration(BaseBookingIntegration):
    name = "square_appointments"
    display_name = "Square Appointments"
    description = "Sync appointments, clients, and services from Square"
    auth_type = "oauth2"
    capabilities = [
        "read_appointments", "create_appointment", "cancel_appointment",
        "read_clients", "search_clients", "read_services", "read_providers",
        "check_availability",
    ]

    def _get_client(self):
        """Build Square API client from stored credentials."""
        from square.client import Client
        db = SessionLocal()
        try:
            integ = db.query(Integration).filter(
                Integration.integration_type == self.name,
                Integration.status == "connected",
            ).first()
            if not integ or not integ.credentials:
                raise RuntimeError("Square not connected")
            creds = decrypt_credentials(integ.credentials)
            return Client(access_token=creds["access_token"], environment="production")
        finally:
            db.close()

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
            integ.last_error = None
            db.commit()
            return True
        except Exception as e:
            logger.error("Square connect failed: %s", e)
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
                Integration.integration_type == self.name,
                Integration.status == "connected",
            ).first() is not None
        finally:
            db.close()

    async def test_connection(self, business_id: Optional[str]) -> bool:
        try:
            client = self._get_client()
            result = client.locations.list_locations()
            return result.is_success()
        except Exception:
            return False

    async def execute_action(self, action_type: str, params: dict) -> Dict[str, Any]:
        try:
            if action_type == "read_upcoming_appointments":
                data = await self.get_upcoming_appointments(params.get("business_id", ""))
                return {"success": True, "action_type": action_type, "details": data, "error": None}
            return {"success": False, "action_type": action_type, "details": None, "error": "Unknown action"}
        except Exception as e:
            return {"success": False, "action_type": action_type, "details": None, "error": str(e)}

    # --- Booking methods ---

    async def get_upcoming_appointments(self, business_id: str, days_ahead: int = 7) -> List[StandardAppointment]:
        client = self._get_client()
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=days_ahead)
        result = client.bookings.list_bookings(
            start_at_min=now.isoformat(),
            start_at_max=end.isoformat(),
        )
        if not result.is_success():
            return []
        return [self._parse_booking(b) for b in (result.body.get("bookings") or [])]

    async def get_appointment_detail(self, business_id: str, appointment_id: str) -> StandardAppointment:
        client = self._get_client()
        result = client.bookings.retrieve_booking(booking_id=appointment_id)
        return self._parse_booking(result.body.get("booking", {}))

    async def get_todays_appointments(self, business_id: str) -> List[StandardAppointment]:
        return await self.get_upcoming_appointments(business_id, days_ahead=1)

    async def get_new_appointments_since(self, business_id: str, since: datetime) -> List[StandardAppointment]:
        return await self.get_upcoming_appointments(business_id, days_ahead=30)

    async def get_cancelled_appointments_since(self, business_id: str, since: datetime) -> List[StandardAppointment]:
        all_appts = await self.get_upcoming_appointments(business_id, days_ahead=30)
        return [a for a in all_appts if a.status == "cancelled"]

    async def get_client(self, business_id: str, client_id: str) -> StandardClient:
        client = self._get_client()
        result = client.customers.retrieve_customer(customer_id=client_id)
        cust = result.body.get("customer", {})
        return self._parse_customer(cust)

    async def search_clients(self, business_id: str, query: str) -> List[StandardClient]:
        client = self._get_client()
        result = client.customers.search_customers(body={
            "query": {"filter": {"email_address": {"fuzzy": query}}}
        })
        return [self._parse_customer(c) for c in (result.body.get("customers") or [])]

    async def get_client_appointment_history(self, business_id: str, client_id: str) -> List[StandardAppointment]:
        return []  # Square doesn't have a direct endpoint for this

    async def get_services(self, business_id: str) -> List[StandardService]:
        client = self._get_client()
        result = client.catalog.list_catalog(types="ITEM")
        items = result.body.get("objects") or []
        return [
            StandardService(
                id=item.get("id", ""),
                name=item.get("item_data", {}).get("name", ""),
                category=item.get("item_data", {}).get("category", {}).get("name"),
                duration_minutes=0,
                source_platform="square",
            )
            for item in items
        ]

    async def get_providers(self, business_id: str) -> List[StandardProvider]:
        client = self._get_client()
        result = client.team.search_team_members(body={"query": {"filter": {"status": "ACTIVE"}}})
        members = result.body.get("team_members") or []
        return [
            StandardProvider(
                id=m.get("id", ""),
                first_name=m.get("given_name", ""),
                last_name=m.get("family_name", ""),
                email=m.get("email_address"),
                source_platform="square",
            )
            for m in members
        ]

    async def create_appointment(self, business_id, client_id, service_id, provider_id, start_time, notes=None):
        client = self._get_client()
        body = {
            "booking": {
                "customer_id": client_id,
                "start_at": start_time.isoformat() if isinstance(start_time, datetime) else start_time,
                "appointment_segments": [{"service_variation_id": service_id, "team_member_id": provider_id}],
            }
        }
        if notes:
            body["booking"]["customer_note"] = notes
        result = client.bookings.create_booking(body=body)
        return self._parse_booking(result.body.get("booking", {}))

    async def cancel_appointment(self, business_id, appointment_id, reason=None):
        client = self._get_client()
        result = client.bookings.cancel_booking(booking_id=appointment_id, body={})
        return result.is_success()

    async def get_available_slots(self, business_id, service_id, provider_id=None, date_from=None, date_to=None):
        client = self._get_client()
        body = {
            "query": {
                "filter": {
                    "start_at_range": {
                        "start_at": (date_from or datetime.now(timezone.utc)).isoformat(),
                        "end_at": (date_to or datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                    },
                    "segment_filters": [{"service_variation_id": service_id}],
                }
            }
        }
        if provider_id:
            body["query"]["filter"]["segment_filters"][0]["team_member_id_filter"] = {"any": [provider_id]}
        result = client.bookings.search_availability(body=body)
        avails = result.body.get("availabilities") or []
        return [
            TimeSlot(
                start_time=datetime.fromisoformat(a["start_at"].replace("Z", "+00:00")),
                end_time=datetime.fromisoformat(a["start_at"].replace("Z", "+00:00")) + timedelta(minutes=a.get("appointment_segments", [{}])[0].get("duration_minutes", 60)),
                available=True,
            )
            for a in avails
        ]

    @staticmethod
    def _parse_booking(b: dict) -> StandardAppointment:
        segments = b.get("appointment_segments") or [{}]
        seg = segments[0] if segments else {}
        return StandardAppointment(
            id=b.get("id", ""),
            start_time=datetime.fromisoformat(b["start_at"].replace("Z", "+00:00")) if b.get("start_at") else None,
            duration_minutes=seg.get("duration_minutes", 0),
            status=b.get("status", "confirmed").lower(),
            notes=b.get("customer_note"),
            created_at=datetime.fromisoformat(b["created_at"].replace("Z", "+00:00")) if b.get("created_at") else None,
            updated_at=datetime.fromisoformat(b["updated_at"].replace("Z", "+00:00")) if b.get("updated_at") else None,
            source_platform="square",
            raw_data=b,
        )

    @staticmethod
    def _parse_customer(c: dict) -> StandardClient:
        return StandardClient(
            id=c.get("id", ""),
            first_name=c.get("given_name", ""),
            last_name=c.get("family_name", ""),
            email=c.get("email_address"),
            phone=c.get("phone_number"),
            created_at=datetime.fromisoformat(c["created_at"].replace("Z", "+00:00")) if c.get("created_at") else None,
            source_platform="square",
            raw_data=c,
        )


square_appointments = SquareIntegration()

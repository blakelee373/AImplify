"""Google Calendar integration — read events, create events, check availability."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from app.database import SessionLocal
from app.models.integration import Integration
from app.utils.encryption import encrypt_credentials, decrypt_credentials
from app.integrations.base import BaseIntegration

logger = logging.getLogger(__name__)


class GoogleCalendarIntegration(BaseIntegration):
    name = "google_calendar"
    display_name = "Google Calendar"
    description = "Read and create calendar events"
    auth_type = "oauth2"
    capabilities = [
        "read_events",
        "create_event",
        "check_availability",
        "get_new_events",
    ]

    def _get_service(self, creds_data: dict):
        """Build a Google Calendar API service from stored credentials."""
        creds = Credentials(
            token=creds_data.get("access_token"),
            refresh_token=creds_data.get("refresh_token"),
            token_uri=creds_data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=creds_data.get("client_id"),
            client_secret=creds_data.get("client_secret"),
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Update stored token
            creds_data["access_token"] = creds.token
            self._update_stored_credentials(creds_data)

        return build("calendar", "v3", credentials=creds, cache_discovery=False)

    def _update_stored_credentials(self, creds_data: dict):
        db = SessionLocal()
        try:
            integration = (
                db.query(Integration)
                .filter(Integration.integration_type == self.name)
                .first()
            )
            if integration:
                integration.credentials = encrypt_credentials(creds_data)
                db.commit()
        finally:
            db.close()

    def _get_credentials(self) -> dict:
        db = SessionLocal()
        try:
            integration = (
                db.query(Integration)
                .filter(
                    Integration.integration_type == self.name,
                    Integration.status == "connected",
                )
                .first()
            )
            if not integration or not integration.credentials:
                raise RuntimeError("Google Calendar not connected")
            return decrypt_credentials(integration.credentials)
        finally:
            db.close()

    # --- BaseIntegration interface ---

    async def connect(self, business_id: Optional[str], auth_data: dict) -> bool:
        db = SessionLocal()
        try:
            integration = (
                db.query(Integration)
                .filter(Integration.integration_type == self.name)
                .first()
            )
            if not integration:
                integration = Integration(
                    integration_type=self.name,
                    business_id=business_id,
                )
                db.add(integration)
            integration.credentials = encrypt_credentials(auth_data)
            integration.status = "connected"
            integration.connected_at = datetime.now(timezone.utc)
            integration.last_error = None
            db.commit()
            return True
        except Exception as e:
            logger.error("Failed to connect Google Calendar: %s", e)
            return False
        finally:
            db.close()

    async def disconnect(self, business_id: Optional[str]) -> bool:
        db = SessionLocal()
        try:
            integration = (
                db.query(Integration)
                .filter(Integration.integration_type == self.name)
                .first()
            )
            if integration:
                integration.credentials = None
                integration.status = "disconnected"
                db.commit()
            return True
        finally:
            db.close()

    async def is_connected(self, business_id: Optional[str]) -> bool:
        db = SessionLocal()
        try:
            integration = (
                db.query(Integration)
                .filter(
                    Integration.integration_type == self.name,
                    Integration.status == "connected",
                )
                .first()
            )
            return integration is not None
        finally:
            db.close()

    async def test_connection(self, business_id: Optional[str]) -> bool:
        try:
            creds_data = self._get_credentials()
            service = self._get_service(creds_data)
            service.calendarList().list(maxResults=1).execute()
            return True
        except Exception as e:
            logger.error("Google Calendar test failed: %s", e)
            return False

    async def execute_action(self, action_type: str, params: dict) -> Dict[str, Any]:
        try:
            if action_type == "read_upcoming_events":
                events = self.read_upcoming_events(**params)
                return {"success": True, "action_type": action_type, "details": events, "error": None}
            elif action_type == "create_event":
                event = self.create_event(**params)
                return {"success": True, "action_type": action_type, "details": event, "error": None}
            elif action_type == "check_availability":
                result = self.check_availability(**params)
                return {"success": True, "action_type": action_type, "details": result, "error": None}
            else:
                return {"success": False, "action_type": action_type, "details": None, "error": "Unknown action"}
        except Exception as e:
            return {"success": False, "action_type": action_type, "details": None, "error": str(e)}

    # --- Calendar-specific methods ---

    def read_upcoming_events(
        self, days_ahead: int = 7, calendar_id: str = "primary"
    ) -> List[Dict]:
        creds_data = self._get_credentials()
        service = self._get_service(creds_data)

        now = datetime.now(timezone.utc)
        time_max = now + timedelta(days=days_ahead)

        result = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=now.isoformat(),
                timeMax=time_max.isoformat(),
                singleEvents=True,
                orderBy="startTime",
                maxResults=100,
            )
            .execute()
        )

        return [self._parse_event(e) for e in result.get("items", [])]

    def get_todays_events(self, calendar_id: str = "primary") -> List[Dict]:
        creds_data = self._get_credentials()
        service = self._get_service(creds_data)

        now = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)

        result = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=start.isoformat(),
                timeMax=end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        return [self._parse_event(e) for e in result.get("items", [])]

    def get_new_events_since(
        self, since: datetime, calendar_id: str = "primary"
    ) -> List[Dict]:
        """Fetch events created or modified after *since*."""
        creds_data = self._get_credentials()
        service = self._get_service(creds_data)

        result = (
            service.events()
            .list(
                calendarId=calendar_id,
                updatedMin=since.isoformat(),
                singleEvents=True,
                orderBy="startTime",
                showDeleted=True,
                maxResults=50,
            )
            .execute()
        )

        return [self._parse_event(e) for e in result.get("items", [])]

    def create_event(
        self,
        title: str,
        start_time: str,
        end_time: str,
        attendees: Optional[List[str]] = None,
        description: Optional[str] = None,
        location: Optional[str] = None,
        calendar_id: str = "primary",
    ) -> Dict:
        creds_data = self._get_credentials()
        service = self._get_service(creds_data)

        body: Dict[str, Any] = {
            "summary": title,
            "start": {"dateTime": start_time},
            "end": {"dateTime": end_time},
        }
        if description:
            body["description"] = description
        if location:
            body["location"] = location
        if attendees:
            body["attendees"] = [{"email": e} for e in attendees]

        event = service.events().insert(calendarId=calendar_id, body=body).execute()
        return self._parse_event(event)

    def check_availability(
        self, start_time: str, end_time: str, calendar_id: str = "primary"
    ) -> Dict:
        creds_data = self._get_credentials()
        service = self._get_service(creds_data)

        result = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=start_time,
                timeMax=end_time,
                singleEvents=True,
            )
            .execute()
        )

        conflicts = [self._parse_event(e) for e in result.get("items", [])]
        return {"is_available": len(conflicts) == 0, "conflicts": conflicts}

    @staticmethod
    def _parse_event(event: dict) -> Dict:
        start = event.get("start", {})
        end = event.get("end", {})
        attendees = event.get("attendees", [])
        return {
            "event_id": event.get("id"),
            "title": event.get("summary", "(No title)"),
            "start_time": start.get("dateTime") or start.get("date"),
            "end_time": end.get("dateTime") or end.get("date"),
            "attendees": [
                {"name": a.get("displayName", ""), "email": a.get("email", "")}
                for a in attendees
            ],
            "description": event.get("description"),
            "location": event.get("location"),
            "status": event.get("status", "confirmed"),
            "created": event.get("created"),
            "updated": event.get("updated"),
        }


google_calendar = GoogleCalendarIntegration()

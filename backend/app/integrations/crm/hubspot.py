"""HubSpot CRM integration — contacts, deals, activity logging."""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from app.database import SessionLocal
from app.models.integration import Integration
from app.utils.encryption import encrypt_credentials, decrypt_credentials
from app.integrations.base import BaseIntegration

logger = logging.getLogger(__name__)


class HubSpotIntegration(BaseIntegration):
    name = "hubspot"
    display_name = "HubSpot CRM"
    description = "Manage client contacts and track interactions"
    auth_type = "oauth2"
    capabilities = [
        "create_contact", "update_contact", "find_contact",
        "create_deal", "log_activity", "add_note", "add_to_list",
    ]

    def _get_client(self):
        from hubspot import HubSpot
        db = SessionLocal()
        try:
            integ = db.query(Integration).filter(
                Integration.integration_type == self.name,
                Integration.status == "connected",
            ).first()
            if not integ or not integ.credentials:
                raise RuntimeError("HubSpot not connected")
            creds = decrypt_credentials(integ.credentials)
            return HubSpot(access_token=creds.get("access_token"))
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
            logger.error("HubSpot connect failed: %s", e)
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
        try:
            client = self._get_client()
            client.crm.contacts.basic_api.get_page(limit=1)
            return True
        except Exception:
            return False

    async def execute_action(self, action_type: str, params: dict) -> Dict[str, Any]:
        try:
            if action_type == "create_crm_contact":
                result = self.find_or_create_contact(**params)
                return {"success": True, "action_type": action_type, "details": result, "error": None}
            if action_type == "update_crm_contact":
                result = self.update_contact(**params)
                return {"success": True, "action_type": action_type, "details": result, "error": None}
            if action_type == "log_crm_activity":
                result = self.log_activity(**params)
                return {"success": True, "action_type": action_type, "details": result, "error": None}
            if action_type == "add_crm_note":
                result = self.add_note(**params)
                return {"success": True, "action_type": action_type, "details": result, "error": None}
            return {"success": False, "action_type": action_type, "details": None, "error": "Unknown action"}
        except Exception as e:
            return {"success": False, "action_type": action_type, "details": None, "error": str(e)}

    # --- CRM methods ---

    def find_contact(self, email: Optional[str] = None, phone: Optional[str] = None) -> Optional[dict]:
        client = self._get_client()
        from hubspot.crm.contacts import PublicObjectSearchRequest
        filters = []
        if email:
            filters.append({"propertyName": "email", "operator": "EQ", "value": email})
        if phone:
            filters.append({"propertyName": "phone", "operator": "EQ", "value": phone})
        if not filters:
            return None
        request = PublicObjectSearchRequest(filter_groups=[{"filters": filters}])
        result = client.crm.contacts.search_api.do_search(public_object_search_request=request)
        if result.results:
            c = result.results[0]
            return {"id": c.id, "properties": c.properties}
        return None

    def create_contact(self, email: str, first_name: str, last_name: str, phone: Optional[str] = None) -> dict:
        client = self._get_client()
        from hubspot.crm.contacts import SimplePublicObjectInputForCreate
        props = {"email": email, "firstname": first_name, "lastname": last_name}
        if phone:
            props["phone"] = phone
        obj = SimplePublicObjectInputForCreate(properties=props)
        result = client.crm.contacts.basic_api.create(simple_public_object_input_for_create=obj)
        return {"id": result.id, "properties": result.properties}

    def find_or_create_contact(self, email: str, first_name: str, last_name: str, phone: Optional[str] = None, **kwargs) -> dict:
        existing = self.find_contact(email=email)
        if existing:
            return existing
        if phone:
            existing = self.find_contact(phone=phone)
            if existing:
                return existing
        return self.create_contact(email, first_name, last_name, phone)

    def update_contact(self, contact_id: str, properties: dict, **kwargs) -> dict:
        client = self._get_client()
        from hubspot.crm.contacts import SimplePublicObjectInput
        obj = SimplePublicObjectInput(properties=properties)
        result = client.crm.contacts.basic_api.update(contact_id=contact_id, simple_public_object_input=obj)
        return {"id": result.id, "properties": result.properties}

    def log_activity(self, contact_id: str, activity_type: str, description: str, **kwargs) -> dict:
        client = self._get_client()
        from hubspot.crm.objects.notes import SimplePublicObjectInputForCreate
        props = {"hs_note_body": "[{}] {}".format(activity_type, description), "hs_timestamp": datetime.now(timezone.utc).isoformat()}
        obj = SimplePublicObjectInputForCreate(properties=props, associations=[{
            "to": {"id": contact_id},
            "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}],
        }])
        result = client.crm.objects.notes.basic_api.create(simple_public_object_input_for_create=obj)
        return {"id": result.id}

    def add_note(self, contact_id: str, note_body: str, **kwargs) -> dict:
        return self.log_activity(contact_id, "Note", note_body)

    def create_deal(self, contact_id: str, deal_name: str, amount: Optional[float] = None, stage: Optional[str] = None, **kwargs) -> dict:
        client = self._get_client()
        from hubspot.crm.deals import SimplePublicObjectInputForCreate
        props = {"dealname": deal_name, "dealstage": stage or "appointmentscheduled"}
        if amount:
            props["amount"] = str(amount)
        obj = SimplePublicObjectInputForCreate(properties=props, associations=[{
            "to": {"id": contact_id},
            "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 3}],
        }])
        result = client.crm.deals.basic_api.create(simple_public_object_input_for_create=obj)
        return {"id": result.id, "properties": result.properties}


hubspot = HubSpotIntegration()

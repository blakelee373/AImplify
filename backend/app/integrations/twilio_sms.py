"""Twilio SMS integration — send and check text messages."""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from twilio.rest import Client as TwilioClient
from twilio.base.exceptions import TwilioRestException

from app.config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER
from app.database import SessionLocal
from app.models.integration import Integration
from app.utils.encryption import encrypt_credentials, decrypt_credentials
from app.utils.phone import format_phone_e164
from app.integrations.base import BaseIntegration

logger = logging.getLogger(__name__)

SMS_MAX_LENGTH = 1600


class TwilioSmsIntegration(BaseIntegration):
    name = "twilio_sms"
    display_name = "SMS (Twilio)"
    description = "Send text messages to clients"
    auth_type = "api_key"
    capabilities = ["send_sms", "check_sms_status"]

    def _get_client_and_number(self) -> tuple:
        """Return (TwilioClient, from_phone_number)."""
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
            if integration and integration.credentials:
                creds = decrypt_credentials(integration.credentials)
                client = TwilioClient(creds["account_sid"], creds["auth_token"])
                return client, creds["phone_number"]
        finally:
            db.close()

        # Fallback to env vars
        if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
            client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            return client, TWILIO_PHONE_NUMBER

        raise RuntimeError("Twilio not connected")

    # --- BaseIntegration interface ---

    async def connect(self, business_id: Optional[str], auth_data: dict) -> bool:
        """Validate Twilio credentials and store them."""
        try:
            client = TwilioClient(auth_data["account_sid"], auth_data["auth_token"])
            # Verify by fetching account info
            client.api.accounts(auth_data["account_sid"]).fetch()
        except Exception as e:
            logger.error("Twilio credential validation failed: %s", e)
            return False

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
            logger.error("Failed to store Twilio credentials: %s", e)
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
            return (
                db.query(Integration)
                .filter(
                    Integration.integration_type == self.name,
                    Integration.status == "connected",
                )
                .first()
            ) is not None
        finally:
            db.close()

    async def test_connection(self, business_id: Optional[str]) -> bool:
        try:
            client, _ = self._get_client_and_number()
            client.api.accounts.list(limit=1)
            return True
        except Exception as e:
            logger.error("Twilio test failed: %s", e)
            return False

    async def execute_action(self, action_type: str, params: dict) -> Dict[str, Any]:
        try:
            if action_type in ("send_sms", "send_review_request"):
                result = self.send_sms(**params)
                return {"success": True, "action_type": action_type, "details": result, "error": None}
            elif action_type == "send_template_sms":
                result = self.send_template_sms(**params)
                return {"success": True, "action_type": action_type, "details": result, "error": None}
            elif action_type == "check_sms_status":
                result = self.check_sms_status(**params)
                return {"success": True, "action_type": action_type, "details": result, "error": None}
            else:
                return {"success": False, "action_type": action_type, "details": None, "error": "Unknown action"}
        except Exception as e:
            return {"success": False, "action_type": action_type, "details": None, "error": str(e)}

    # --- SMS-specific methods ---

    def send_sms(self, to_phone: str, message_body: str) -> Dict:
        client, from_number = self._get_client_and_number()
        to_e164 = format_phone_e164(to_phone)

        if len(message_body) > SMS_MAX_LENGTH:
            logger.warning("SMS body truncated from %d to %d chars", len(message_body), SMS_MAX_LENGTH)
            message_body = message_body[:SMS_MAX_LENGTH]

        try:
            message = client.messages.create(
                body=message_body,
                from_=from_number,
                to=to_e164,
            )
            return {
                "message_sid": message.sid,
                "status": message.status,
                "to": to_e164,
                "error": None,
            }
        except TwilioRestException as e:
            logger.error("Twilio send failed: %s", e)
            return {
                "message_sid": None,
                "status": "failed",
                "to": to_e164,
                "error": str(e),
            }

    def send_template_sms(self, to_phone: str, template_body: str, variables: dict) -> Dict:
        """Fill in template variables and send."""
        body = template_body
        for key, value in variables.items():
            placeholder = "{{{{{}}}}}".format(key)
            body = body.replace(placeholder, str(value))
        return self.send_sms(to_phone, body)

    def check_sms_status(self, message_sid: str) -> Dict:
        client, _ = self._get_client_and_number()
        message = client.messages(message_sid).fetch()
        return {
            "message_sid": message.sid,
            "status": message.status,
            "error_code": message.error_code,
            "error_message": message.error_message,
        }


twilio_sms = TwilioSmsIntegration()

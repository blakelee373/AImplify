"""Gmail integration — send emails, read inbox."""

import base64
import logging
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List, Dict, Any

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from app.database import SessionLocal
from app.models.integration import Integration
from app.utils.encryption import encrypt_credentials, decrypt_credentials
from app.integrations.base import BaseIntegration

logger = logging.getLogger(__name__)


class GmailIntegration(BaseIntegration):
    name = "gmail"
    display_name = "Gmail"
    description = "Send emails to clients"
    auth_type = "oauth2"
    capabilities = ["send_email", "read_emails", "unread_count"]

    def _get_service(self, creds_data: dict):
        creds = Credentials(
            token=creds_data.get("access_token"),
            refresh_token=creds_data.get("refresh_token"),
            token_uri=creds_data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=creds_data.get("client_id"),
            client_secret=creds_data.get("client_secret"),
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            creds_data["access_token"] = creds.token
            self._update_stored_credentials(creds_data)

        return build("gmail", "v1", credentials=creds, cache_discovery=False)

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
                raise RuntimeError("Gmail not connected")
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
            logger.error("Failed to connect Gmail: %s", e)
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
            creds_data = self._get_credentials()
            service = self._get_service(creds_data)
            service.users().getProfile(userId="me").execute()
            return True
        except Exception as e:
            logger.error("Gmail test failed: %s", e)
            return False

    async def execute_action(self, action_type: str, params: dict) -> Dict[str, Any]:
        try:
            if action_type == "send_email":
                result = self.send_email(**params)
                return {"success": True, "action_type": action_type, "details": result, "error": None}
            elif action_type == "send_template_email":
                result = self.send_template_email(**params)
                return {"success": True, "action_type": action_type, "details": result, "error": None}
            else:
                return {"success": False, "action_type": action_type, "details": None, "error": "Unknown action"}
        except Exception as e:
            return {"success": False, "action_type": action_type, "details": None, "error": str(e)}

    # --- Gmail-specific methods ---

    def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
        from_name: Optional[str] = None,
    ) -> Dict:
        creds_data = self._get_credentials()
        service = self._get_service(creds_data)

        msg = MIMEMultipart("alternative")
        msg["To"] = to_email
        msg["Subject"] = subject
        if from_name:
            # Get the sender email from Gmail profile
            profile = service.users().getProfile(userId="me").execute()
            msg["From"] = "{} <{}>".format(from_name, profile["emailAddress"])

        if body_text:
            msg.attach(MIMEText(body_text, "plain"))
        msg.attach(MIMEText(body_html, "html"))

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        result = service.users().messages().send(userId="me", body={"raw": raw}).execute()

        return {
            "message_id": result.get("id"),
            "thread_id": result.get("threadId"),
            "status": "sent",
        }

    def send_template_email(
        self,
        to_email: str,
        subject_template: str,
        body_template: str,
        variables: dict,
        from_name: Optional[str] = None,
    ) -> Dict:
        """Fill in template variables and send."""
        subject = subject_template
        body = body_template
        for key, value in variables.items():
            placeholder = "{{{{{}}}}}".format(key)
            subject = subject.replace(placeholder, str(value))
            body = body.replace(placeholder, str(value))

        return self.send_email(
            to_email=to_email,
            subject=subject,
            body_html=body,
            from_name=from_name,
        )

    def read_recent_emails(self, max_results: int = 20, query: Optional[str] = None) -> List[Dict]:
        creds_data = self._get_credentials()
        service = self._get_service(creds_data)

        params: Dict[str, Any] = {"userId": "me", "maxResults": max_results}
        if query:
            params["q"] = query

        result = service.users().messages().list(**params).execute()
        messages = []
        for msg_ref in result.get("messages", []):
            msg = service.users().messages().get(userId="me", id=msg_ref["id"], format="metadata").execute()
            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            messages.append({
                "message_id": msg["id"],
                "thread_id": msg.get("threadId"),
                "from": headers.get("From", ""),
                "to": headers.get("To", ""),
                "subject": headers.get("Subject", ""),
                "snippet": msg.get("snippet", ""),
                "date": headers.get("Date", ""),
                "is_read": "UNREAD" not in msg.get("labelIds", []),
            })

        return messages

    def get_unread_count(self) -> int:
        creds_data = self._get_credentials()
        service = self._get_service(creds_data)
        result = service.users().messages().list(userId="me", q="is:unread", maxResults=1).execute()
        return result.get("resultSizeEstimate", 0)


gmail = GmailIntegration()

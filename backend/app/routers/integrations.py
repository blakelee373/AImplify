"""Integration management — connect, disconnect, OAuth callbacks."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from google_auth_oauthlib.flow import Flow

from app.config import (
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    BACKEND_URL,
    FRONTEND_URL,
)
from app.database import get_db
from app.services.integration_manager import list_available_integrations
from app.integrations.google_calendar import google_calendar
from app.integrations.gmail import gmail
from app.integrations.twilio_sms import twilio_sms

logger = logging.getLogger(__name__)
router = APIRouter()

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]


def _build_google_flow() -> Flow:
    return Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=GOOGLE_SCOPES,
        redirect_uri="{}/api/integrations/callback/google".format(BACKEND_URL),
    )


# ─── List available integrations ────────────────────────────────────

@router.get("/integrations")
async def get_integrations():
    return list_available_integrations()


# ─── Connect ────────────────────────────────────────────────────────

@router.get("/integrations/connect/google")
async def connect_google():
    """Return the Google OAuth consent URL."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(400, "Google OAuth credentials not configured")

    flow = _build_google_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return {"auth_url": auth_url}


@router.get("/integrations/callback/google")
async def google_callback(code: str):
    """Exchange the OAuth code for tokens and store them."""
    flow = _build_google_flow()
    flow.fetch_token(code=code)
    credentials = flow.credentials

    token_data = {
        "access_token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": list(credentials.scopes or []),
    }

    # Store for both Calendar and Gmail
    await google_calendar.connect(None, token_data)
    await gmail.connect(None, token_data)

    return RedirectResponse(url="{}/integrations?connected=google".format(FRONTEND_URL))


class TwilioCredentials(BaseModel):
    account_sid: str
    auth_token: str
    phone_number: str


@router.post("/integrations/connect/twilio")
async def connect_twilio(creds: TwilioCredentials):
    """Validate and store Twilio credentials."""
    success = await twilio_sms.connect(None, creds.dict())
    if not success:
        raise HTTPException(400, "Invalid Twilio credentials")
    return {"status": "connected"}


# ─── Disconnect ─────────────────────────────────────────────────────

@router.post("/integrations/disconnect/{integration_type}")
async def disconnect_integration(integration_type: str):
    if integration_type == "google_calendar":
        await google_calendar.disconnect(None)
        # Also disconnect Gmail (same Google account)
        await gmail.disconnect(None)
    elif integration_type == "gmail":
        await gmail.disconnect(None)
        await google_calendar.disconnect(None)
    elif integration_type == "twilio_sms":
        await twilio_sms.disconnect(None)
    else:
        raise HTTPException(404, "Unknown integration type")
    return {"status": "disconnected"}


# ─── Status / Test ──────────────────────────────────────────────────

@router.get("/integrations/status/{integration_type}")
async def test_integration(integration_type: str):
    integration_map = {
        "google_calendar": google_calendar,
        "gmail": gmail,
        "twilio_sms": twilio_sms,
    }
    integration = integration_map.get(integration_type)
    if not integration:
        raise HTTPException(404, "Unknown integration type")

    ok = await integration.test_connection(None)
    return {"integration": integration_type, "connected": ok}

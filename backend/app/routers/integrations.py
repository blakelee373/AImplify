from typing import List

import requests as http_requests
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from sqlalchemy.orm import Session

from app.config import (
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    BACKEND_URL,
    FRONTEND_URL,
)
from app.database import get_db
from app.models.integration import Integration
from app.services.encryption import encrypt_token, decrypt_token

router = APIRouter(prefix="/api")

# Scopes for Gmail and Calendar access
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]

GOOGLE_CLIENT_CONFIG = {
    "web": {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}


def _make_flow() -> Flow:
    return Flow.from_client_config(
        GOOGLE_CLIENT_CONFIG,
        scopes=GOOGLE_SCOPES,
        redirect_uri=f"{BACKEND_URL}/api/integrations/google/callback",
    )


@router.get("/integrations/google/connect")
async def google_connect():
    """Redirect the user to Google's OAuth consent screen."""
    flow = _make_flow()
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return RedirectResponse(url=authorization_url)


@router.get("/integrations/google/callback")
async def google_callback(code: str, db: Session = Depends(get_db)):
    """Handle the OAuth callback — exchange code for tokens and store them."""
    flow = _make_flow()
    flow.fetch_token(code=code)

    credentials = flow.credentials

    encrypted_access = encrypt_token(credentials.token)
    encrypted_refresh = (
        encrypt_token(credentials.refresh_token) if credentials.refresh_token else None
    )

    # Upsert integration row
    integration = db.query(Integration).filter(Integration.provider == "google").first()
    if integration:
        integration.access_token = encrypted_access
        integration.refresh_token = encrypted_refresh or integration.refresh_token
        integration.token_expiry = credentials.expiry
        integration.scopes = " ".join(credentials.scopes or GOOGLE_SCOPES)
        integration.status = "connected"
    else:
        integration = Integration(
            provider="google",
            access_token=encrypted_access,
            refresh_token=encrypted_refresh,
            token_expiry=credentials.expiry,
            scopes=" ".join(credentials.scopes or GOOGLE_SCOPES),
            status="connected",
        )
        db.add(integration)

    db.commit()
    return RedirectResponse(url=f"{FRONTEND_URL}/settings/integrations?status=success")


@router.get("/integrations/status")
async def integrations_status(db: Session = Depends(get_db)):
    """Return the status of all integrations. Never exposes tokens."""
    integrations = db.query(Integration).all()
    return [
        {
            "provider": i.provider,
            "status": i.status,
            "scopes": i.scopes.split(" ") if i.scopes else [],
            "connected_at": i.updated_at.isoformat() if i.status == "connected" else None,
        }
        for i in integrations
    ]


@router.post("/integrations/google/disconnect")
async def google_disconnect(db: Session = Depends(get_db)):
    """Revoke the Google token and mark as disconnected."""
    integration = db.query(Integration).filter(Integration.provider == "google").first()
    if not integration:
        raise HTTPException(status_code=404, detail="Google integration not found")

    # Best-effort revocation with Google
    if integration.access_token:
        try:
            token = decrypt_token(integration.access_token)
            http_requests.post(
                "https://oauth2.googleapis.com/revoke",
                params={"token": token},
                timeout=5,
            )
        except Exception:
            pass

    integration.access_token = None
    integration.refresh_token = None
    integration.token_expiry = None
    integration.status = "disconnected"
    db.commit()

    return {"status": "disconnected"}

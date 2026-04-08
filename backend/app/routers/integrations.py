import json
import os
from pathlib import Path
from typing import List

import requests as http_requests
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from sqlalchemy.orm import Session

# Allow HTTP redirect URIs for local development
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
# Allow scope to expand when include_granted_scopes merges prior grants
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

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

# ── Scope definitions per provider ───────────────────────────────────────────

PROVIDER_SCOPES = {
    "gmail": [
        "https://www.googleapis.com/auth/gmail.modify",
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
    ],
    "google_calendar": [
        "https://www.googleapis.com/auth/calendar",
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
    ],
}

GOOGLE_CLIENT_CONFIG = {
    "web": {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}

# Persist code verifiers to disk so they survive uvicorn reloads
_VERIFIER_FILE = Path(__file__).resolve().parent.parent.parent / ".oauth_verifiers.json"


def _save_verifier(provider: str, verifier: str):
    data = {}
    if _VERIFIER_FILE.exists():
        data = json.loads(_VERIFIER_FILE.read_text())
    data[provider] = verifier
    _VERIFIER_FILE.write_text(json.dumps(data))


def _pop_verifier(provider: str):
    if not _VERIFIER_FILE.exists():
        return None
    data = json.loads(_VERIFIER_FILE.read_text())
    verifier = data.pop(provider, None)
    _VERIFIER_FILE.write_text(json.dumps(data))
    return verifier


def _make_flow(provider: str) -> Flow:
    return Flow.from_client_config(
        GOOGLE_CLIENT_CONFIG,
        scopes=PROVIDER_SCOPES[provider],
        redirect_uri=f"{BACKEND_URL}/api/integrations/{provider}/callback",
    )


def _connect(provider: str):
    flow = _make_flow(provider)
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    _save_verifier(provider, flow.code_verifier)
    return RedirectResponse(url=authorization_url)


def _callback(provider: str, code: str, db: Session):
    try:
        flow = _make_flow(provider)
        flow.code_verifier = _pop_verifier(provider)
        flow.fetch_token(code=code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth token exchange failed: {e}")

    credentials = flow.credentials

    encrypted_access = encrypt_token(credentials.token)
    encrypted_refresh = (
        encrypt_token(credentials.refresh_token) if credentials.refresh_token else None
    )

    # Upsert integration row for this provider
    integration = db.query(Integration).filter(Integration.provider == provider).first()
    if integration:
        integration.access_token = encrypted_access
        integration.refresh_token = encrypted_refresh or integration.refresh_token
        integration.token_expiry = credentials.expiry
        integration.scopes = " ".join(credentials.scopes or PROVIDER_SCOPES[provider])
        integration.status = "connected"
    else:
        integration = Integration(
            provider=provider,
            access_token=encrypted_access,
            refresh_token=encrypted_refresh,
            token_expiry=credentials.expiry,
            scopes=" ".join(credentials.scopes or PROVIDER_SCOPES[provider]),
            status="connected",
        )
        db.add(integration)

    db.commit()
    return RedirectResponse(url=f"{FRONTEND_URL}/settings/integrations?status=success")


def _disconnect(provider: str, db: Session):
    integration = db.query(Integration).filter(Integration.provider == provider).first()
    if not integration:
        raise HTTPException(status_code=404, detail=f"{provider} integration not found")

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

    return {"status": "disconnected", "provider": provider}


# ── Gmail endpoints ──────────────────────────────────────────────────────────


@router.get("/integrations/gmail/connect")
async def gmail_connect():
    """Redirect the user to Google's OAuth consent screen for Gmail."""
    return _connect("gmail")


@router.get("/integrations/gmail/callback")
async def gmail_callback(code: str, db: Session = Depends(get_db)):
    """Handle the Gmail OAuth callback."""
    return _callback("gmail", code, db)


@router.post("/integrations/gmail/disconnect")
async def gmail_disconnect(db: Session = Depends(get_db)):
    """Revoke Gmail token and mark as disconnected."""
    return _disconnect("gmail", db)


# ── Google Calendar endpoints ────────────────────────────────────────────────


@router.get("/integrations/google_calendar/connect")
async def calendar_connect():
    """Redirect the user to Google's OAuth consent screen for Calendar."""
    return _connect("google_calendar")


@router.get("/integrations/google_calendar/callback")
async def calendar_callback(code: str, db: Session = Depends(get_db)):
    """Handle the Calendar OAuth callback."""
    return _callback("google_calendar", code, db)


@router.post("/integrations/google_calendar/disconnect")
async def calendar_disconnect(db: Session = Depends(get_db)):
    """Revoke Calendar token and mark as disconnected."""
    return _disconnect("google_calendar", db)


# ── Status ───────────────────────────────────────────────────────────────────


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

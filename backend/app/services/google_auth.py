"""Google OAuth credential management — single point of access for all Google API calls."""

from datetime import datetime, timezone
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from sqlalchemy.orm import Session

from app.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
from app.models.integration import Integration
from app.services.encryption import encrypt_token, decrypt_token


def get_google_credentials(db: Session) -> Optional[Credentials]:
    """Get valid Google credentials, refreshing if expired.

    Returns None if no Google integration is connected.
    """
    integration = db.query(Integration).filter(
        Integration.provider == "google",
        Integration.status == "connected",
    ).first()

    if not integration or not integration.access_token:
        return None

    creds = Credentials(
        token=decrypt_token(integration.access_token),
        refresh_token=decrypt_token(integration.refresh_token) if integration.refresh_token else None,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
    )

    # Refresh if expired
    # SQLite stores naive datetimes, so compare both as naive UTC
    expiry = integration.token_expiry.replace(tzinfo=None) if integration.token_expiry else None
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    if expiry and expiry < now_utc:
        if creds.refresh_token:
            creds.refresh(Request())
            # Update stored tokens with fresh ones
            integration.access_token = encrypt_token(creds.token)
            integration.token_expiry = creds.expiry
            db.commit()
        else:
            return None  # No refresh token — user must re-auth

    return creds

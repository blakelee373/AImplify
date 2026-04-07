"""Fernet symmetric encryption for storing integration credentials."""

import json
import logging

from cryptography.fernet import Fernet, InvalidToken

from app.config import ENCRYPTION_KEY

logger = logging.getLogger(__name__)


def _get_fernet() -> Fernet:
    if not ENCRYPTION_KEY:
        raise RuntimeError(
            "ENCRYPTION_KEY is not set. Generate one with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(ENCRYPTION_KEY.encode())


def encrypt_credentials(data: dict) -> str:
    """Encrypt a dict of credentials to a Fernet-encrypted string."""
    f = _get_fernet()
    return f.encrypt(json.dumps(data).encode()).decode()


def decrypt_credentials(encrypted: str) -> dict:
    """Decrypt a Fernet-encrypted string back to a dict."""
    try:
        f = _get_fernet()
        return json.loads(f.decrypt(encrypted.encode()).decode())
    except InvalidToken:
        logger.error("Failed to decrypt credentials — key may have changed")
        raise

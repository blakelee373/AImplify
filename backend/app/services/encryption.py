from cryptography.fernet import Fernet
from app.config import ENCRYPTION_KEY

_fernet = Fernet(ENCRYPTION_KEY.encode()) if ENCRYPTION_KEY else None


def encrypt_token(plaintext: str) -> str:
    """Encrypt a token string and return the ciphertext as a UTF-8 string."""
    if not _fernet:
        raise RuntimeError("ENCRYPTION_KEY is not configured")
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    """Decrypt a ciphertext string and return the original token."""
    if not _fernet:
        raise RuntimeError("ENCRYPTION_KEY is not configured")
    return _fernet.decrypt(ciphertext.encode()).decode()

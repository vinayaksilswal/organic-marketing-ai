"""
=============================================================================
Organic Marketing AI — Cryptography Service
=============================================================================
Provides AES-256 encryption for securing sensitive OAuth tokens and API keys
at rest within the PostgreSQL database.
=============================================================================
"""

import base64
from cryptography.fernet import Fernet
from loguru import logger
from config import settings

def _get_fernet() -> Fernet:
    """Returns a configured Fernet instance using the application encryption key."""
    if not settings.encryption_key:
        raise ValueError("ENCRYPTION_KEY is not set in configuration.")
    
    # Ensure the key is exactly 32 url-safe base64-encoded bytes
    try:
        # Check if it's already a valid Fernet key
        return Fernet(settings.encryption_key.encode('utf-8'))
    except ValueError:
        # If not, derive a 32-byte key from it
        key_bytes = settings.encryption_key.encode('utf-8')
        if len(key_bytes) < 32:
            key_bytes = key_bytes.ljust(32, b'0')
        elif len(key_bytes) > 32:
            key_bytes = key_bytes[:32]
        fernet_key = base64.urlsafe_b64encode(key_bytes)
        return Fernet(fernet_key)

def encrypt_token(token: str | None) -> str | None:
    """Encrypts a plaintext token string using AES-256 (Fernet)."""
    if not token:
        return None
    try:
        f = _get_fernet()
        return f.encrypt(token.encode('utf-8')).decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to encrypt token: {e}")
        from exceptions import OrganicMarketingException
        raise OrganicMarketingException("Encryption failed", status_code=500, error_code="CRYPTO_ERROR")

def decrypt_token(encrypted_token: str | None) -> str | None:
    """
    Decrypts an AES-256 (Fernet) encrypted token string back to plaintext.
    If decryption fails (e.g. legacy plaintext tokens during migration), logs a warning
    and returns the original string to ensure system stability.
    """
    if not encrypted_token:
        return None
    try:
        f = _get_fernet()
        return f.decrypt(encrypted_token.encode('utf-8')).decode('utf-8')
    except Exception as e:
        logger.warning(f"Failed to decrypt token (may be plaintext legacy token): {e}")
        return encrypted_token


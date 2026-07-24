"""
=============================================================================
Organic Marketing AI — JWT Authentication Helpers
=============================================================================
Handles JWT token creation and admin session verification.
Uses timezone-aware datetime for token expiry (no deprecated utcnow).
=============================================================================
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, Request, status
from loguru import logger

from config import settings


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT access token with expiry."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=1440))
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_credentials(request: Request) -> str:
    """
    Verify admin session from cookie or Bearer token.
    Returns the admin username on success, raises 401 on failure.
    """
    token = request.cookies.get("admin_session")

    # Check authorization header as fallback for API endpoints
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        username: str = payload.get("sub")
        if username is None or username != settings.admin_username:
            raise HTTPException(status_code=401, detail="Invalid session")
        return username
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid session")

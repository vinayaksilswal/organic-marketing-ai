"""Connecting an X account, so the publishing code that already exists can run.

services/twitter_service.py has been able to post for a long time, and the
worker calls it on every publish. It has never posted once, because nothing
could put a token in the database: there was no connect flow, no button, and
no way for a customer to grant access. The capability existed and did nothing,
which is the same shape as several other things found in this codebase.

WHY OAUTH 1.0a RATHER THAN 2.0
------------------------------
Not a preference. tweepy.Client is constructed in twitter_service with
consumer_key/consumer_secret/access_token/access_token_secret -- that is 1.0a
user context, and it is what the existing posting code expects. Issuing 2.0
bearer tokens here would mean rewriting the half that already works, so this
matches it instead.

The request-token step is synchronous network I/O inside tweepy, so both calls
run in a thread rather than blocking the event loop.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from loguru import logger
from sqlalchemy import select

from config import settings
from database import AsyncSessionLocal, BusinessProfile, SocialConnection
from routers.auth import verify_user
from services.crypto_service import encrypt_token

router = APIRouter(prefix="/api/v1/x", tags=["X (Twitter)"])

_STATE_TTL_SECONDS = 900

# oauth_token -> {"secret": ..., "ws": ..., "sub": ...}
#
# In memory on purpose: it lives for the ninety seconds between leaving for X
# and coming back, and a restart in that window costs one retry. Persisting a
# half-finished handshake would mean storing a credential fragment for a flow
# that may never complete.
_PENDING: dict[str, dict[str, Any]] = {}


def _configured() -> bool:
    return bool(settings.twitter_api_key and settings.twitter_api_secret)


def _callback_url() -> str:
    base = (settings.backend_public_url or "").rstrip("/")
    if not base:
        raise HTTPException(
            status_code=500,
            detail="BACKEND_PUBLIC_URL is not configured; cannot build the X redirect URI.",
        )
    return f"{base}/api/v1/x/callback"


def _dashboard_url(status: str, message: str = "") -> str:
    from urllib.parse import urlencode

    frontend = (settings.frontend_url or settings.allowed_origins[0]).rstrip("/")
    query = urlencode({"x": status, **({"message": message} if message else {})})
    return f"{frontend}/dashboard/workspaces?{query}"


def _encode_state(workspace_id: str, user_id: str) -> str:
    return jwt.encode(
        {
            "ws": workspace_id,
            "sub": user_id,
            "purpose": "x_oauth",
            "exp": datetime.now(timezone.utc) + timedelta(seconds=_STATE_TTL_SECONDS),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def _decode_state(state: str) -> Optional[dict[str, Any]]:
    try:
        payload = jwt.decode(state, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except Exception as e:
        logger.warning(f"X OAuth state rejected: {e}")
        return None
    if payload.get("purpose") != "x_oauth":
        # A state minted for Meta must not be accepted here.
        logger.warning("X OAuth state had the wrong purpose claim")
        return None
    return payload


@router.get("/connect")
async def x_connect(workspace_id: str, user_id: str = Depends(verify_user)) -> dict:
    """Start the handshake and hand back the URL to send the customer to."""
    if not _configured():
        raise HTTPException(
            status_code=503,
            detail="X is not configured on this server (missing TWITTER_API_KEY / TWITTER_API_SECRET).",
        )

    async with AsyncSessionLocal() as session:
        bp = await session.get(BusinessProfile, workspace_id)
        if not bp or bp.userId != user_id:
            raise HTTPException(status_code=404, detail="Workspace not found")

    try:
        import tweepy
    except ImportError:
        raise HTTPException(status_code=503, detail="X support is not installed on this server.")

    def _request_token():
        handler = tweepy.OAuth1UserHandler(
            settings.twitter_api_key,
            settings.twitter_api_secret,
            callback=_callback_url(),
        )
        url = handler.get_authorization_url(signin_with_twitter=False)
        return url, handler.request_token

    try:
        # tweepy's handshake is synchronous; off the event loop it goes.
        auth_url, request_token = await asyncio.to_thread(_request_token)
    except Exception as e:
        logger.error(f"X request token failed: {e}")
        raise HTTPException(status_code=502, detail="X refused to start the connection. Check the app keys and callback URL.")

    _PENDING[request_token["oauth_token"]] = {
        "secret": request_token["oauth_token_secret"],
        "ws": workspace_id,
        "sub": user_id,
        "state": _encode_state(workspace_id, user_id),
    }

    return {"success": True, "authUrl": auth_url}


@router.get("/callback")
async def x_callback(request: Request) -> RedirectResponse:
    """Where X sends the customer back. Always redirects, never returns JSON.

    A person is looking at this in a browser tab, so every outcome has to end
    somewhere they can read. An error rendered as raw JSON is a dead end.
    """
    oauth_token = request.query_params.get("oauth_token")
    verifier = request.query_params.get("oauth_verifier")

    if request.query_params.get("denied"):
        return RedirectResponse(_dashboard_url("cancelled", "You cancelled the X connection."))
    if not oauth_token or not verifier:
        return RedirectResponse(_dashboard_url("error", "X did not return the expected details."))

    pending = _PENDING.pop(oauth_token, None)
    if not pending:
        # Expired, already used, or minted by another process.
        return RedirectResponse(_dashboard_url("error", "That connection attempt expired. Try again."))

    claims = _decode_state(pending.get("state", ""))
    if not claims:
        return RedirectResponse(_dashboard_url("error", "That connection attempt could not be verified."))

    try:
        import tweepy

        def _exchange():
            handler = tweepy.OAuth1UserHandler(
                settings.twitter_api_key,
                settings.twitter_api_secret,
                callback=_callback_url(),
            )
            handler.request_token = {
                "oauth_token": oauth_token,
                "oauth_token_secret": pending["secret"],
            }
            access_token, access_secret = handler.get_access_token(verifier)
            client = tweepy.Client(
                consumer_key=settings.twitter_api_key,
                consumer_secret=settings.twitter_api_secret,
                access_token=access_token,
                access_token_secret=access_secret,
            )
            me = client.get_me()
            handle = me.data.username if me and me.data else None
            return access_token, access_secret, handle

        access_token, access_secret, handle = await asyncio.to_thread(_exchange)
    except Exception as e:
        logger.error(f"X token exchange failed: {e}")
        return RedirectResponse(_dashboard_url("error", "X refused the connection. Please try again."))

    workspace_id, user_id = claims["ws"], claims["sub"]
    async with AsyncSessionLocal() as session:
        conn = (await session.execute(
            select(SocialConnection).where(SocialConnection.businessProfileId == workspace_id)
        )).scalars().first()
        if not conn:
            conn = SocialConnection(userId=user_id, businessProfileId=workspace_id)
            session.add(conn)
        # Encrypted at rest, like every other token here.
        conn.twitterAccessToken = encrypt_token(access_token)
        conn.twitterAccessSecret = encrypt_token(access_secret)
        await session.commit()

    logger.info(f"X connected for workspace {workspace_id}" + (f" as @{handle}" if handle else ""))
    return RedirectResponse(_dashboard_url("connected", f"@{handle}" if handle else "your X account"))


@router.post("/disconnect")
async def x_disconnect(workspace_id: str, user_id: str = Depends(verify_user)) -> dict:
    """Drop the stored token. Posting stops immediately; nothing else changes."""
    async with AsyncSessionLocal() as session:
        bp = await session.get(BusinessProfile, workspace_id)
        if not bp or bp.userId != user_id:
            raise HTTPException(status_code=404, detail="Workspace not found")

        conn = (await session.execute(
            select(SocialConnection).where(SocialConnection.businessProfileId == workspace_id)
        )).scalars().first()
        if conn:
            conn.twitterAccessToken = None
            conn.twitterAccessSecret = None
            await session.commit()

    return {"success": True, "message": "X disconnected. Nothing will be posted there."}

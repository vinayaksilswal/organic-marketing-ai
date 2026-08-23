"""Connecting a YouTube channel.

Same shape as the X and LinkedIn flows: a connect endpoint that hands back an
authorisation URL, a callback that always redirects somewhere readable, and a
disconnect that stops publishing without deleting anything on the platform.

WHY ONLY THE REFRESH TOKEN IS STORED
------------------------------------
Google's access tokens last an hour. The scheduler runs every few hours, so a
stored access token is almost always expired by the time it is wanted, and
storing it would mean two credentials to keep in sync for no benefit. The
refresh token is durable; an access token is minted from it per upload.

Getting one at all requires `access_type=offline` AND `prompt=consent`. Google
returns a refresh token only on the first authorisation unless consent is
forced, so a customer who reconnects after revoking would otherwise get an
access token, no refresh token, and a connection that works for one hour and
then silently stops.

THE QUOTA IS THE REAL CONSTRAINT
--------------------------------
A YouTube upload costs 1,600 quota units against a default 10,000 per day —
for the whole application, across every customer, not per channel. That is six
uploads a day in total. This is a fact about the platform rather than
something to engineer around, so it is stated at connect time instead of being
discovered when the seventh upload of the day fails.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from loguru import logger
from sqlalchemy import select

from config import settings
from database import AsyncSessionLocal, BusinessProfile, SocialConnection
from routers.auth import verify_user
from services.crypto_service import encrypt_token

router = APIRouter(prefix="/api/v1/youtube", tags=["YouTube"])

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"

# upload is what publishing needs; readonly is what naming the connected
# channel needs. Nothing broader is requested.
SCOPES = " ".join([
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
])

_STATE_TTL_SECONDS = 900


def _client_id() -> Optional[str]:
    return settings.youtube_client_id or settings.google_client_id


def _client_secret() -> Optional[str]:
    return settings.youtube_client_secret or settings.google_client_secret


def _configured() -> bool:
    return bool(_client_id() and _client_secret())


def _callback_url() -> str:
    base = (settings.backend_public_url or "").rstrip("/")
    if not base:
        raise HTTPException(
            status_code=500,
            detail="BACKEND_PUBLIC_URL is not configured; cannot build the YouTube redirect URI.",
        )
    return f"{base}/api/v1/youtube/callback"


def _dashboard_url(status: str, message: str = "") -> str:
    frontend = (settings.frontend_url or settings.allowed_origins[0]).rstrip("/")
    query = urlencode({"youtube": status, **({"message": message} if message else {})})
    return f"{frontend}/dashboard/workspaces?{query}"


def _encode_state(workspace_id: str, user_id: str) -> str:
    return jwt.encode(
        {
            "ws": workspace_id,
            "sub": user_id,
            "purpose": "youtube_oauth",
            "exp": datetime.now(timezone.utc) + timedelta(seconds=_STATE_TTL_SECONDS),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def _decode_state(state: str) -> Optional[dict[str, Any]]:
    try:
        payload = jwt.decode(state, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except Exception as e:
        logger.warning(f"YouTube OAuth state rejected: {e}")
        return None
    if payload.get("purpose") != "youtube_oauth":
        # A state minted for Meta, X or LinkedIn must not be spent here.
        logger.warning("YouTube OAuth state had the wrong purpose claim")
        return None
    return payload


@router.get("/connect")
async def youtube_connect(workspace_id: str, user_id: str = Depends(verify_user)) -> dict:
    if not _configured():
        raise HTTPException(
            status_code=503,
            detail=(
                "YouTube is not configured on this server (missing "
                "YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET)."
            ),
        )

    async with AsyncSessionLocal() as session:
        bp = await session.get(BusinessProfile, workspace_id)
        if not bp or bp.userId != user_id:
            raise HTTPException(status_code=404, detail="Workspace not found")

    query = {
        "client_id": _client_id(),
        "redirect_uri": _callback_url(),
        "response_type": "code",
        "scope": SCOPES,
        "state": _encode_state(workspace_id, user_id),
        # Both are required to be handed a refresh token. Without them the
        # connection works for one hour and then stops without saying why.
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
    }
    return {"success": True, "authUrl": f"{AUTH_URL}?{urlencode(query)}"}


@router.get("/callback")
async def youtube_callback(request: Request) -> RedirectResponse:
    """Where Google sends the customer back. Always redirects, never JSON."""
    error = request.query_params.get("error")
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if error:
        status = "cancelled" if "denied" in error.lower() or "cancel" in error.lower() else "error"
        return RedirectResponse(_dashboard_url(status, error[:160]))
    if not code or not state:
        return RedirectResponse(_dashboard_url("error", "YouTube did not return the expected details."))

    claims = _decode_state(state)
    if not claims:
        return RedirectResponse(_dashboard_url("error", "That connection attempt expired. Try again."))

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            token_res = await client.post(TOKEN_URL, data={
                "code": code,
                "client_id": _client_id(),
                "client_secret": _client_secret(),
                "redirect_uri": _callback_url(),
                "grant_type": "authorization_code",
            })
            payload = token_res.json()
            access_token = payload.get("access_token")
            refresh_token = payload.get("refresh_token")

            if not access_token:
                logger.error(f"YouTube token exchange failed: {str(payload)[:200]}")
                return RedirectResponse(_dashboard_url("error", "Google refused the connection."))

            if not refresh_token:
                # Google withholds it when the user has authorised before and
                # consent was not forced. Without it the connection dies in an
                # hour, so this is refused rather than stored half-working.
                return RedirectResponse(_dashboard_url(
                    "error",
                    "Google did not return a long-lived token. Remove Organiflo at "
                    "myaccount.google.com/permissions and connect again.",
                ))

            info = await client.get(CHANNELS_URL, params={
                "part": "snippet", "mine": "true",
            }, headers={"Authorization": f"Bearer {access_token}"})
            channels = (info.json().get("items") or []) if info.status_code == 200 else []
    except Exception as e:
        logger.error(f"YouTube callback failed: {e}")
        return RedirectResponse(_dashboard_url("error", "Could not complete the YouTube connection."))

    if not channels:
        return RedirectResponse(_dashboard_url(
            "error",
            "That Google account has no YouTube channel. Create one, then connect again.",
        ))

    channel = channels[0]
    channel_id = channel.get("id")
    channel_title = ((channel.get("snippet") or {}).get("title")) or "your channel"

    workspace_id, user_id = claims["ws"], claims["sub"]

    async with AsyncSessionLocal() as session:
        conn = (await session.execute(
            select(SocialConnection).where(SocialConnection.businessProfileId == workspace_id)
        )).scalars().first()
        if not conn:
            conn = SocialConnection(userId=user_id, businessProfileId=workspace_id)
            session.add(conn)
        conn.youtubeRefreshToken = encrypt_token(refresh_token)
        conn.youtubeChannelId = channel_id
        conn.youtubeChannelTitle = channel_title
        await session.commit()

    logger.info(f"YouTube connected for workspace {workspace_id}: {channel_title}")
    return RedirectResponse(_dashboard_url("connected", channel_title))


@router.post("/disconnect")
async def youtube_disconnect(workspace_id: str, user_id: str = Depends(verify_user)) -> dict:
    async with AsyncSessionLocal() as session:
        bp = await session.get(BusinessProfile, workspace_id)
        if not bp or bp.userId != user_id:
            raise HTTPException(status_code=404, detail="Workspace not found")

        conn = (await session.execute(
            select(SocialConnection).where(SocialConnection.businessProfileId == workspace_id)
        )).scalars().first()
        if conn:
            conn.youtubeRefreshToken = None
            conn.youtubeChannelId = None
            conn.youtubeChannelTitle = None
            await session.commit()

    return {"success": True, "message": "YouTube disconnected. Nothing will be published there."}

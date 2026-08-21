"""Connecting LinkedIn, so its publishing code can run.

services/linkedin_service.py has been able to post since it was written, and
the worker calls it on every publish. It has never posted once. Two things
stopped it: nothing could put a token in the database, and `post_text` returns
None unless LINKEDIN_ORGANIZATION_ID is set in the environment, which it never
was.

PERSONAL PROFILE FIRST, PAGE WHEN THE REVIEW CLEARS
---------------------------------------------------
Posting to a Company Page needs LinkedIn's Community Management API, which
needs app review. Posting to a personal profile needs `w_member_social` and
nothing else. A customer who wants to publish this week gets the second.

So the actor is stored per connection rather than read from one global env
var. `urn:li:person:xxx` today, `urn:li:organization:123` when the review
clears, and the posting code does not need a second branch to handle it.

The member id comes from the OpenID `sub` claim on /v2/userinfo, which
`openid profile` grants without review.
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

router = APIRouter(prefix="/api/v1/linkedin", tags=["LinkedIn"])

AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"

# openid + profile identify who is posting; w_member_social is the permission
# to post as them. None of the three need app review.
SCOPES = "openid profile w_member_social"

_STATE_TTL_SECONDS = 900


def _configured() -> bool:
    return bool(settings.linkedin_client_id and settings.linkedin_client_secret)


def _callback_url() -> str:
    base = (settings.backend_public_url or "").rstrip("/")
    if not base:
        raise HTTPException(
            status_code=500,
            detail="BACKEND_PUBLIC_URL is not configured; cannot build the LinkedIn redirect URI.",
        )
    return f"{base}/api/v1/linkedin/callback"


def _dashboard_url(status: str, message: str = "") -> str:
    frontend = (settings.frontend_url or settings.allowed_origins[0]).rstrip("/")
    query = urlencode({"linkedin": status, **({"message": message} if message else {})})
    return f"{frontend}/dashboard/workspaces?{query}"


def _encode_state(workspace_id: str, user_id: str) -> str:
    return jwt.encode(
        {
            "ws": workspace_id,
            "sub": user_id,
            "purpose": "linkedin_oauth",
            "exp": datetime.now(timezone.utc) + timedelta(seconds=_STATE_TTL_SECONDS),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def _decode_state(state: str) -> Optional[dict[str, Any]]:
    try:
        payload = jwt.decode(state, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except Exception as e:
        logger.warning(f"LinkedIn OAuth state rejected: {e}")
        return None
    if payload.get("purpose") != "linkedin_oauth":
        # A state minted for Meta or X must not be spent here.
        logger.warning("LinkedIn OAuth state had the wrong purpose claim")
        return None
    return payload


@router.get("/connect")
async def linkedin_connect(workspace_id: str, user_id: str = Depends(verify_user)) -> dict:
    if not _configured():
        raise HTTPException(
            status_code=503,
            detail="LinkedIn is not configured on this server (missing LINKEDIN_CLIENT_ID / LINKEDIN_CLIENT_SECRET).",
        )

    async with AsyncSessionLocal() as session:
        bp = await session.get(BusinessProfile, workspace_id)
        if not bp or bp.userId != user_id:
            raise HTTPException(status_code=404, detail="Workspace not found")

    query = {
        "response_type": "code",
        "client_id": settings.linkedin_client_id,
        "redirect_uri": _callback_url(),
        "state": _encode_state(workspace_id, user_id),
        "scope": SCOPES,
    }
    return {"success": True, "authUrl": f"{AUTH_URL}?{urlencode(query)}"}


@router.get("/callback")
async def linkedin_callback(request: Request) -> RedirectResponse:
    """Where LinkedIn sends the customer back. Always redirects, never JSON."""
    error = request.query_params.get("error")
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if error:
        reason = request.query_params.get("error_description") or error
        status = "cancelled" if "denied" in error.lower() or "cancel" in reason.lower() else "error"
        return RedirectResponse(_dashboard_url(status, reason[:160]))
    if not code or not state:
        return RedirectResponse(_dashboard_url("error", "LinkedIn did not return the expected details."))

    claims = _decode_state(state)
    if not claims:
        return RedirectResponse(_dashboard_url("error", "That connection attempt expired. Try again."))

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            token_res = await client.post(
                TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": _callback_url(),
                    "client_id": settings.linkedin_client_id,
                    "client_secret": settings.linkedin_client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            payload = token_res.json()
            access_token = payload.get("access_token")
            if not access_token:
                logger.error(f"LinkedIn token exchange failed: {str(payload)[:200]}")
                return RedirectResponse(_dashboard_url("error", "LinkedIn refused the connection."))

            # Who we will be posting as. Without this the author URN is unknown
            # and every post would be rejected.
            info = await client.get(
                USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}
            )
            profile = info.json() if info.status_code == 200 else {}
    except Exception as e:
        logger.error(f"LinkedIn callback failed: {e}")
        return RedirectResponse(_dashboard_url("error", "Could not complete the LinkedIn connection."))

    member_id = profile.get("sub")
    if not member_id:
        return RedirectResponse(
            _dashboard_url("error", "LinkedIn did not return your profile id. Check the app has the openid and profile scopes.")
        )

    display = profile.get("name") or "your LinkedIn profile"
    workspace_id, user_id = claims["ws"], claims["sub"]

    async with AsyncSessionLocal() as session:
        conn = (await session.execute(
            select(SocialConnection).where(SocialConnection.businessProfileId == workspace_id)
        )).scalars().first()
        if not conn:
            conn = SocialConnection(userId=user_id, businessProfileId=workspace_id)
            session.add(conn)
        conn.linkedinAccessToken = encrypt_token(access_token)
        conn.linkedinActorUrn = f"urn:li:person:{member_id}"
        await session.commit()

    logger.info(f"LinkedIn connected for workspace {workspace_id} as {display}")
    return RedirectResponse(_dashboard_url("connected", display))


@router.post("/disconnect")
async def linkedin_disconnect(workspace_id: str, user_id: str = Depends(verify_user)) -> dict:
    async with AsyncSessionLocal() as session:
        bp = await session.get(BusinessProfile, workspace_id)
        if not bp or bp.userId != user_id:
            raise HTTPException(status_code=404, detail="Workspace not found")

        conn = (await session.execute(
            select(SocialConnection).where(SocialConnection.businessProfileId == workspace_id)
        )).scalars().first()
        if conn:
            conn.linkedinAccessToken = None
            conn.linkedinActorUrn = None
            await session.commit()

    return {"success": True, "message": "LinkedIn disconnected. Nothing will be posted there."}

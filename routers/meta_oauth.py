"""
=============================================================================
Meta (Facebook + Instagram) OAuth Connect Flow
=============================================================================
Replaces manual access-token pasting with a real OAuth handshake using the
Facebook Developer app credentials (fb_app_id / fb_app_secret).

Flow:
  1. GET  /api/v1/meta/connect?workspace_id=...  -> returns Facebook auth URL
  2. User authorises on Facebook
  3. GET  /api/v1/meta/callback?code=...&state=... -> exchanges code for a
     long-lived user token, discovers the Page + linked Instagram Business
     account, encrypts and stores them against the workspace, then redirects
     the browser back to the dashboard.
=============================================================================
"""

import json
import secrets
import time
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from loguru import logger
from sqlalchemy import select

from config import settings
from database import AsyncSessionLocal, BusinessProfile, SocialConnection
from routers.auth import verify_user
from services.crypto_service import encrypt_token

router = APIRouter(prefix="/api/v1/meta", tags=["Meta OAuth"])

GRAPH_API_VERSION = "v19.0"
GRAPH_BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

# Permissions required to publish to a Page and its linked IG Business account
META_SCOPES = ",".join([
    "pages_show_list",
    "pages_read_engagement",
    "pages_manage_posts",
    "instagram_basic",
    "instagram_content_publish",
    "business_management",
])

# state token -> {workspace_id, user_id, expires}. Short-lived, single-use.
_OAUTH_STATE: dict[str, dict[str, Any]] = {}
_STATE_TTL_SECONDS = 600


def _redirect_uri() -> str:
    """The callback URL registered in the Facebook app settings."""
    base = (settings.backend_public_url or "").rstrip("/")
    if not base:
        raise HTTPException(
            status_code=500,
            detail="BACKEND_PUBLIC_URL is not configured; cannot build the OAuth redirect URI.",
        )
    return f"{base}/api/v1/meta/callback"


def _dashboard_url(status: str, message: str = "") -> str:
    frontend = (settings.frontend_url or settings.allowed_origins[0]).rstrip("/")
    from urllib.parse import urlencode
    query = urlencode({"meta": status, **({"message": message} if message else {})})
    return f"{frontend}/dashboard/workspaces?{query}"


def _purge_expired_state() -> None:
    now = time.time()
    for key in [k for k, v in _OAUTH_STATE.items() if v["expires"] < now]:
        _OAUTH_STATE.pop(key, None)


@router.get("/connect")
async def meta_connect(request: Request, workspace_id: str, user_id: str = Depends(verify_user)):
    """Return the Facebook authorisation URL for this workspace."""
    if not settings.fb_app_id or not settings.fb_app_secret:
        raise HTTPException(
            status_code=503,
            detail="Meta integration is not configured on this server (missing FB_APP_ID / FB_APP_SECRET).",
        )

    async with AsyncSessionLocal() as session:
        bp = await session.get(BusinessProfile, workspace_id)
        if not bp or bp.userId != user_id:
            raise HTTPException(status_code=404, detail="Workspace not found")

    _purge_expired_state()
    state = secrets.token_urlsafe(32)
    _OAUTH_STATE[state] = {
        "workspace_id": workspace_id,
        "user_id": user_id,
        "expires": time.time() + _STATE_TTL_SECONDS,
    }

    from urllib.parse import urlencode
    params = urlencode({
        "client_id": settings.fb_app_id,
        "redirect_uri": _redirect_uri(),
        "state": state,
        "scope": META_SCOPES,
        "response_type": "code",
    })
    return {"success": True, "authUrl": f"https://www.facebook.com/{GRAPH_API_VERSION}/dialog/oauth?{params}"}


@router.get("/callback")
async def meta_callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None):
    """Exchange the OAuth code for tokens and store them against the workspace."""
    if error:
        return RedirectResponse(_dashboard_url("error", error), status_code=303)
    if not code or not state:
        return RedirectResponse(_dashboard_url("error", "Missing authorisation code"), status_code=303)

    _purge_expired_state()
    ctx = _OAUTH_STATE.pop(state, None)  # single-use
    if not ctx:
        return RedirectResponse(_dashboard_url("error", "This connection link expired. Please try again."), status_code=303)

    workspace_id = ctx["workspace_id"]
    user_id = ctx["user_id"]

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1. Short-lived user token
            token_res = await client.get(f"{GRAPH_BASE_URL}/oauth/access_token", params={
                "client_id": settings.fb_app_id,
                "client_secret": settings.fb_app_secret,
                "redirect_uri": _redirect_uri(),
                "code": code,
            })
            token_res.raise_for_status()
            short_token = token_res.json()["access_token"]

            # 2. Exchange for a long-lived (~60 day) user token
            long_res = await client.get(f"{GRAPH_BASE_URL}/oauth/access_token", params={
                "grant_type": "fb_exchange_token",
                "client_id": settings.fb_app_id,
                "client_secret": settings.fb_app_secret,
                "fb_exchange_token": short_token,
            })
            long_res.raise_for_status()
            long_token = long_res.json()["access_token"]

            # 3. Discover Pages. Page tokens derived from a long-lived user token
            #    do not expire, which is what we want for unattended posting.
            pages_res = await client.get(f"{GRAPH_BASE_URL}/me/accounts", params={
                "access_token": long_token,
                "fields": "id,name,access_token,instagram_business_account{id,username}",
            })
            pages_res.raise_for_status()
            pages = pages_res.json().get("data", [])

        if not pages:
            return RedirectResponse(
                _dashboard_url("error", "No Facebook Pages found. You need a Page (not a personal profile) to publish."),
                status_code=303,
            )

        page = pages[0]
        ig = page.get("instagram_business_account") or {}

        async with AsyncSessionLocal() as session:
            stmt = select(SocialConnection).where(
                SocialConnection.userId == user_id,
                SocialConnection.businessProfileId == workspace_id,
            )
            conn = (await session.execute(stmt)).scalars().first()
            if not conn:
                conn = SocialConnection(userId=user_id, businessProfileId=workspace_id)
                session.add(conn)

            conn.fbAccessToken = encrypt_token(page["access_token"])
            conn.fbPageId = page["id"]
            conn.fbPageName = page.get("name")
            if ig.get("id"):
                conn.igAccountId = ig["id"]
                conn.igAccountName = ig.get("username")

            await session.commit()

        logger.info(f"Meta connected for workspace {workspace_id}: page={page.get('name')} ig={ig.get('username')}")
        connected = page.get("name") or "Facebook Page"
        if ig.get("username"):
            connected += f" + @{ig['username']}"
        return RedirectResponse(_dashboard_url("connected", connected), status_code=303)

    except httpx.HTTPStatusError as e:
        detail = e.response.text[:200]
        logger.error(f"Meta OAuth exchange failed for workspace {workspace_id}: {detail}")
        return RedirectResponse(_dashboard_url("error", "Facebook rejected the connection. Please try again."), status_code=303)
    except Exception as e:
        logger.exception(f"Meta OAuth callback failed for workspace {workspace_id}")
        return RedirectResponse(_dashboard_url("error", "Could not complete the connection."), status_code=303)


@router.delete("/disconnect")
async def meta_disconnect(workspace_id: str, user_id: str = Depends(verify_user)):
    """Clear the stored Meta credentials for a workspace."""
    async with AsyncSessionLocal() as session:
        stmt = select(SocialConnection).where(
            SocialConnection.userId == user_id,
            SocialConnection.businessProfileId == workspace_id,
        )
        conn = (await session.execute(stmt)).scalars().first()
        if not conn:
            raise HTTPException(status_code=404, detail="No connection found")

        conn.fbAccessToken = None
        conn.fbPageId = None
        conn.fbPageName = None
        conn.igAccountId = None
        conn.igAccountName = None
        await session.commit()

    return {"success": True, "message": "Meta account disconnected."}

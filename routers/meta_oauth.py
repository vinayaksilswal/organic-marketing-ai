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
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
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
# Exactly what this integration uses, and nothing more:
#   pages_show_list          -> discover the user's Pages via /me/accounts
#   pages_read_engagement    -> read Page metadata
#   pages_manage_posts       -> publish to the Page
#   instagram_basic          -> resolve the linked IG Business account
#   instagram_content_publish-> publish to Instagram
#
# business_management was requested previously but never used. It is a
# heavyweight permission that needs its own App Review justification and is a
# common cause of "Invalid Scopes" at the login dialog, so it is not asked for.
META_SCOPES = ",".join([
    "pages_show_list",
    "pages_read_engagement",
    "pages_manage_posts",
    "instagram_basic",
    "instagram_content_publish",
])

# The OAuth `state` is a signed, expiring JWT rather than a server-side dict.
#
# It was previously held in memory, which silently broke the flow in
# production: Render restarts the service on every deploy and when the free
# instance sleeps, so a restart between /connect and Facebook's redirect back
# discarded the state. The callback then took the "link expired" branch — which
# also returns 303, making a failed connect indistinguishable from a successful
# one in the access log. The same applies to any multi-worker deployment, where
# the callback can land on a different process than the one that issued it.
_STATE_TTL_SECONDS = 600


def _encode_state(workspace_id: str, user_id: str) -> str:
    return jwt.encode(
        {
            "ws": workspace_id,
            "sub": user_id,
            "purpose": "meta_oauth",
            "exp": datetime.now(timezone.utc) + timedelta(seconds=_STATE_TTL_SECONDS),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def _decode_state(state: str) -> dict[str, Any] | None:
    """Return the state payload, or None if it is invalid, expired or foreign."""
    try:
        payload = jwt.decode(state, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except Exception as e:
        logger.warning(f"Meta OAuth state rejected: {e}")
        return None
    if payload.get("purpose") != "meta_oauth":
        logger.warning("Meta OAuth state had the wrong purpose claim")
        return None
    return payload

# selection token -> {workspace_id, user_id, pages, expires}.
# Used when the account owns several Pages and the user must choose which one
# this business should publish to. Page tokens are held here only until the
# choice is made, then encrypted into the database.
_PENDING_SELECTION: dict[str, dict[str, Any]] = {}
_SELECTION_TTL_SECONDS = 900


def _serialise_page(page: dict[str, Any]) -> dict[str, Any]:
    """Public-safe view of a Page — never includes the access token."""
    ig = page.get("instagram_business_account") or {}
    return {
        "id": page["id"],
        "name": page.get("name") or "Facebook Page",
        "instagramId": ig.get("id"),
        "instagramUsername": ig.get("username"),
    }


async def _store_connection(user_id: str, workspace_id: str, page: dict[str, Any]) -> dict[str, Any]:
    """Encrypt and persist the chosen Page (and its linked IG account)."""
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
        # Clear any previous IG link so switching Pages cannot leave a stale one
        conn.igAccountId = ig.get("id")
        conn.igAccountName = ig.get("username")

        await session.commit()

    logger.info(
        f"Meta connected for workspace {workspace_id}: "
        f"page={page.get('name')} ig={ig.get('username')}"
    )
    return _serialise_page(page)


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

    state = _encode_state(workspace_id, user_id)

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

    ctx = _decode_state(state)
    if not ctx:
        return RedirectResponse(
            _dashboard_url("error", "This connection link expired. Please try connecting again."),
            status_code=303,
        )

    workspace_id = ctx["ws"]
    user_id = ctx["sub"]
    logger.info(f"Meta OAuth callback accepted for workspace {workspace_id}")

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
            # An empty /me/accounts has two very different causes and the user
            # can only act on the right one. Ask Facebook which permissions were
            # actually granted rather than guessing "you have no Pages" — a
            # reconnect silently reuses a previous, possibly narrower, grant.
            granted: set[str] = set()
            declined: set[str] = set()
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    perm_res = await client.get(
                        f"{GRAPH_BASE_URL}/me/permissions",
                        params={"access_token": long_token},
                    )
                for p in perm_res.json().get("data", []):
                    (granted if p.get("status") == "granted" else declined).add(p.get("permission"))
            except Exception as e:
                logger.warning(f"Could not read granted Meta permissions: {e}")

            logger.warning(
                f"Meta connect returned no Pages for workspace {workspace_id}. "
                f"granted={sorted(granted)} declined={sorted(declined)}"
            )

            missing = {"pages_show_list", "pages_manage_posts"} - granted
            if missing:
                msg = (
                    "Facebook did not grant Page access ("
                    + ", ".join(sorted(missing))
                    + "). Press Connect again and choose 'Edit settings' / 'Edit access', "
                    "then tick your Page — a reconnect reuses your previous choices."
                )
            else:
                msg = (
                    "Page permissions were granted but no Page was selected. Press Connect "
                    "again, choose 'Edit settings', and select the Page you want to publish to. "
                    "You need a Facebook Page — a personal profile cannot be published to."
                )
            return RedirectResponse(_dashboard_url("error", msg), status_code=303)

        # With several Pages we must not guess which one this business posts as.
        if len(pages) > 1:
            for key in [k for k, v in _PENDING_SELECTION.items() if v["expires"] < time.time()]:
                _PENDING_SELECTION.pop(key, None)

            sel_token = secrets.token_urlsafe(32)
            _PENDING_SELECTION[sel_token] = {
                "workspace_id": workspace_id,
                "user_id": user_id,
                "pages": pages,
                "expires": time.time() + _SELECTION_TTL_SECONDS,
            }
            return RedirectResponse(
                _dashboard_url("select", "") + f"&token={sel_token}",
                status_code=303,
            )

        page = pages[0]
        saved = await _store_connection(user_id, workspace_id, page)
        connected = saved["name"]
        if saved.get("instagramUsername"):
            connected += f" + @{saved['instagramUsername']}"
        return RedirectResponse(_dashboard_url("connected", connected), status_code=303)

    except httpx.HTTPStatusError as e:
        detail = e.response.text[:200]
        logger.error(f"Meta OAuth exchange failed for workspace {workspace_id}: {detail}")
        return RedirectResponse(_dashboard_url("error", "Facebook rejected the connection. Please try again."), status_code=303)
    except Exception as e:
        logger.exception(f"Meta OAuth callback failed for workspace {workspace_id}")
        return RedirectResponse(_dashboard_url("error", "Could not complete the connection."), status_code=303)


@router.get("/pages")
async def list_pending_pages(token: str, user_id: str = Depends(verify_user)):
    """List the Pages discovered during OAuth so the user can choose one."""
    ctx = _PENDING_SELECTION.get(token)
    if not ctx or ctx["expires"] < time.time():
        _PENDING_SELECTION.pop(token, None)
        raise HTTPException(status_code=410, detail="This selection expired. Please connect again.")
    if ctx["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="This selection belongs to another account.")

    return {
        "success": True,
        "workspaceId": ctx["workspace_id"],
        "pages": [_serialise_page(p) for p in ctx["pages"]],
    }


class SelectPageRequest(BaseModel):
    token: str
    page_id: str


@router.post("/select-page")
async def select_page(data: SelectPageRequest, user_id: str = Depends(verify_user)):
    """Persist the Page the user chose for this workspace."""
    ctx = _PENDING_SELECTION.get(data.token)
    if not ctx or ctx["expires"] < time.time():
        _PENDING_SELECTION.pop(data.token, None)
        raise HTTPException(status_code=410, detail="This selection expired. Please connect again.")
    if ctx["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="This selection belongs to another account.")

    page = next((p for p in ctx["pages"] if p["id"] == data.page_id), None)
    if not page:
        raise HTTPException(status_code=404, detail="That Page was not part of this connection.")

    saved = await _store_connection(user_id, ctx["workspace_id"], page)
    _PENDING_SELECTION.pop(data.token, None)  # single-use; drops the held tokens

    return {"success": True, "connected": saved}


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

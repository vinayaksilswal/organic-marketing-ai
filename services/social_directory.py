"""The connected accounts shown on the landing page.

A strip of real, clickable Instagram and Facebook profiles is stronger proof
than a logo wall, because a visitor can open one and see posts arriving on a
schedule. It also grows on its own as customers connect accounts.

Two things this must not do. It must not put Meta's API on the critical path
of a sales page -- a Graph call per pageview would be slow, rate-limited and
would take the page down with Meta. And it must not query the database on
every view either. So the result is built at most once every CACHE_MINUTES and
served from memory, and any failure serves the last good snapshot rather than
an empty strip.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger
from sqlalchemy import select

GRAPH = "https://graph.facebook.com/v21.0"

# Long enough that Meta is called a handful of times an hour no matter the
# traffic, short enough that a newly connected account appears the same day.
CACHE_MINUTES = 30

_cache: Dict[str, Any] = {"at": 0.0, "accounts": []}


async def _instagram_profile(
    client: httpx.AsyncClient, ig_id: str, token: str
) -> Optional[Dict[str, str]]:
    try:
        body = (await client.get(
            f"{GRAPH}/{ig_id}",
            params={
                "access_token": token,
                "fields": "username,profile_picture_url,followers_count",
            },
        )).json()
    except Exception:
        return None
    if "error" in body or not body.get("username"):
        return None
    return {
        "platform": "instagram",
        "name": body["username"],
        "avatar": body.get("profile_picture_url") or "",
        "url": f"https://www.instagram.com/{body['username']}/",
        "followers": body.get("followers_count") or 0,
    }


async def _facebook_profile(
    client: httpx.AsyncClient, page_id: str, token: str
) -> Optional[Dict[str, str]]:
    try:
        body = (await client.get(
            f"{GRAPH}/{page_id}",
            params={"access_token": token, "fields": "name,link,picture{url}"},
        )).json()
    except Exception:
        return None
    if "error" in body or not body.get("name"):
        return None
    return {
        "platform": "facebook",
        "name": body["name"],
        "avatar": ((body.get("picture") or {}).get("data") or {}).get("url", ""),
        "url": body.get("link") or f"https://www.facebook.com/{page_id}",
        "followers": 0,
    }


async def _build() -> List[Dict[str, str]]:
    from database import AsyncSessionLocal, BusinessProfile, SocialConnection
    from services.crypto_service import decrypt_token

    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(BusinessProfile, SocialConnection)
            .join(SocialConnection,
                  SocialConnection.businessProfileId == BusinessProfile.id)
            .order_by(BusinessProfile.name)
        )).all()

    accounts: List[Dict[str, str]] = []
    async with httpx.AsyncClient(timeout=20) as client:
        for _profile, conn in rows:
            if not conn.fbAccessToken:
                continue
            try:
                token = decrypt_token(conn.fbAccessToken)
            except Exception:
                continue

            if conn.igAccountId:
                account = await _instagram_profile(client, conn.igAccountId, token)
                if account:
                    accounts.append(account)
            if conn.fbPageId:
                account = await _facebook_profile(client, conn.fbPageId, token)
                if account:
                    accounts.append(account)

    return accounts


async def public_accounts(force: bool = False) -> List[Dict[str, str]]:
    """Connected accounts, cached. Never raises, never returns stale-empty."""
    age = time.time() - _cache["at"]
    if not force and _cache["accounts"] and age < CACHE_MINUTES * 60:
        return _cache["accounts"]

    try:
        accounts = await _build()
    except Exception as e:
        logger.warning(f"Could not refresh connected accounts: {e}")
        return _cache["accounts"]

    if accounts:
        _cache["accounts"] = accounts
        _cache["at"] = time.time()
        logger.info(f"Connected-accounts strip refreshed: {len(accounts)} accounts")
    return _cache["accounts"]

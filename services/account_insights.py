"""What the connected accounts are actually doing.

`engagement_insights` already reads a workspace's Instagram history, but it
exists to feed the caption writer: it returns three statements a model can act
on and deliberately throws the rest away. An operator needs the opposite —
the numbers, the posts, and which account they came from.

So this reads the same connection and answers a different question: for each
account attached to this business, who is it, how many people follow it, and
how did the last few weeks go.

WHAT IT DOES NOT DO
-------------------
It does not invent a metric it cannot read. Instagram's insight fields depend
on the account type and the permissions granted, and a number shown with no
idea where it came from is worse than a blank — so a field that comes back
missing is reported as missing rather than defaulted to zero. Zero engagement
and unavailable engagement look identical on a dashboard and mean opposite
things.

It also never raises into the caller. A page that cannot load its numbers
should say so on the row it could not load; nothing here justifies a 500 on a
dashboard the customer is paying for.
"""

from __future__ import annotations

import statistics
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
from loguru import logger

GRAPH = "https://graph.facebook.com/v21.0"

LOOKBACK_DAYS = 30
POST_LIMIT = 50
TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def _parse_ts(raw: Optional[str]) -> Optional[datetime]:
    try:
        return datetime.fromisoformat((raw or "").replace("Z", "+00:00"))
    except Exception:
        return None


async def _get(client: httpx.AsyncClient, path: str, params: dict) -> dict:
    """One Graph read. Returns {} on anything that is not a clean answer."""
    try:
        r = await client.get(f"{GRAPH}/{path}", params=params)
        data = r.json()
    except Exception as e:
        logger.warning(f"Graph read failed for {path}: {e}")
        return {}
    if isinstance(data, dict) and "error" in data:
        # Surfaced, not swallowed: a refused read is usually a scope or a
        # token problem and the message is the only thing that identifies it.
        logger.warning(f"Graph refused {path}: {data['error'].get('message')}")
        return {}
    return data if isinstance(data, dict) else {}


async def _instagram(client: httpx.AsyncClient, ig_id: str, token: str) -> dict:
    profile = await _get(client, ig_id, {
        "access_token": token,
        "fields": "username,name,followers_count,follows_count,media_count,profile_picture_url",
    })
    if not profile:
        return {}

    media = await _get(client, f"{ig_id}/media", {
        "access_token": token,
        "limit": POST_LIMIT,
        "fields": (
            "id,caption,media_type,media_product_type,timestamp,"
            "like_count,comments_count,permalink,thumbnail_url,media_url"
        ),
    })

    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    posts = []
    for m in (media.get("data") or []):
        when = _parse_ts(m.get("timestamp"))
        if not when or when < cutoff:
            continue
        likes, comments = m.get("like_count"), m.get("comments_count")
        posts.append({
            "id": m.get("id"),
            "caption": (m.get("caption") or "").strip(),
            "kind": m.get("media_product_type") or m.get("media_type") or "POST",
            "postedAt": when.isoformat(),
            # None rather than 0 when the field was not returned. Zero
            # engagement and unavailable engagement mean opposite things.
            "likes": likes,
            "comments": comments,
            "engagement": (likes or 0) + (comments or 0) if likes is not None else None,
            "permalink": m.get("permalink"),
            "thumbnail": m.get("thumbnail_url") or m.get("media_url"),
        })

    posts.sort(key=lambda p: p["postedAt"], reverse=True)
    return {
        "platform": "instagram",
        "id": ig_id,
        "handle": profile.get("username"),
        "name": profile.get("name") or profile.get("username"),
        "avatar": profile.get("profile_picture_url"),
        "followers": profile.get("followers_count"),
        "following": profile.get("follows_count"),
        "totalPosts": profile.get("media_count"),
        "posts": posts,
        "summary": _summarise(posts),
    }


async def _facebook(client: httpx.AsyncClient, page_id: str, token: str) -> dict:
    page = await _get(client, page_id, {
        "access_token": token,
        "fields": "name,username,fan_count,followers_count,link,picture{url}",
    })
    if not page:
        return {}
    return {
        "platform": "facebook",
        "id": page_id,
        "handle": page.get("username"),
        "name": page.get("name"),
        "avatar": (page.get("picture") or {}).get("data", {}).get("url"),
        "followers": page.get("followers_count") or page.get("fan_count"),
        "following": None,
        "totalPosts": None,
        "link": page.get("link"),
        # Page post metrics need read_insights, which this app does not
        # currently request. Claiming a number we cannot read would be worse
        # than saying where it comes from.
        "posts": [],
        "summary": {"available": False, "note": "Page post metrics need extra permissions."},
    }


def _summarise(posts: list) -> dict:
    """The few numbers worth putting at the top of a card."""
    scored = [p for p in posts if p.get("engagement") is not None]
    if not scored:
        return {"available": False, "note": "No engagement figures returned for this account."}

    values = [p["engagement"] for p in scored]
    best = max(scored, key=lambda p: p["engagement"])
    by_kind: dict[str, list[int]] = {}
    for p in scored:
        by_kind.setdefault(p["kind"], []).append(p["engagement"])

    return {
        "available": True,
        "postsInWindow": len(scored),
        "windowDays": LOOKBACK_DAYS,
        "totalEngagement": sum(values),
        "medianEngagement": round(statistics.median(values), 1),
        "bestEngagement": best["engagement"],
        "bestPermalink": best.get("permalink"),
        "bestCaption": (best.get("caption") or "")[:120],
        # Only reported where there is enough of each format to compare.
        "byFormat": {
            k: {"posts": len(v), "median": round(statistics.median(v), 1)}
            for k, v in sorted(by_kind.items()) if len(v) >= 2
        },
    }


async def for_workspace(session: Any, workspace_id: str) -> dict:
    """Every connected account for one business, with its numbers."""
    from sqlalchemy import select

    from database import SocialConnection
    from services.crypto_service import decrypt_token

    conn = (await session.execute(
        select(SocialConnection).where(
            SocialConnection.businessProfileId == workspace_id
        ).limit(1)
    )).scalars().first()

    if not conn or not conn.fbAccessToken:
        return {"accounts": [], "note": "No social account is connected to this business yet."}

    try:
        token = decrypt_token(conn.fbAccessToken)
    except Exception as e:
        logger.warning(f"Could not decrypt token for {workspace_id}: {e}")
        return {"accounts": [], "note": "The stored access token could not be read. Reconnect the account."}

    accounts = []
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        if conn.igAccountId:
            ig = await _instagram(client, conn.igAccountId, token)
            if ig:
                accounts.append(ig)
            else:
                accounts.append({
                    "platform": "instagram", "id": conn.igAccountId,
                    "name": conn.igAccountName or "Instagram",
                    "unavailable": "Instagram refused this read. The token may have expired — reconnect the account.",
                })
        if conn.fbPageId:
            fb = await _facebook(client, conn.fbPageId, token)
            if fb:
                accounts.append(fb)
            else:
                accounts.append({
                    "platform": "facebook", "id": conn.fbPageId,
                    "name": conn.fbPageName or "Facebook Page",
                    "unavailable": "Facebook refused this read. The token may have expired — reconnect the account.",
                })

    if not accounts:
        return {"accounts": [], "note": "No Facebook Page or Instagram account is connected."}
    return {"accounts": accounts}

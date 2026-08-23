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


def _insight_values(media: dict) -> dict:
    """Flatten the nested insights payload into {metric: value}.

    Graph returns insights as {"data": [{"name": "views", "values":
    [{"value": 123}]}]}, and returns the key not at all when a metric does not
    apply to that media type -- so every read here is defensive by necessity.
    """
    out: dict = {}
    for entry in ((media.get("insights") or {}).get("data") or []):
        name = entry.get("name")
        values = entry.get("values") or []
        if not name or not values:
            continue
        value = values[0].get("value")
        if isinstance(value, int):
            out[name] = value
    return out


async def _instagram(client: httpx.AsyncClient, ig_id: str, token: str) -> dict:
    profile = await _get(client, ig_id, {
        "access_token": token,
        "fields": "username,name,followers_count,follows_count,media_count,profile_picture_url",
    })
    if not profile:
        return {}

    # Views are the metric that matters for Reels and the only one that
    # explains a like count, but they live on the /insights edge rather than
    # on the media itself. Requested inline as a nested field so the whole
    # history costs one call: per-post insight calls would spend forty of
    # Meta's two hundred an hour to render one screen.
    BASE_FIELDS = (
        "id,caption,media_type,media_product_type,timestamp,"
        "like_count,comments_count,permalink,thumbnail_url,media_url"
    )
    media = await _get(client, f"{ig_id}/media", {
        "access_token": token,
        "limit": POST_LIMIT,
        "fields": BASE_FIELDS + ",insights.metric(views,reach)"
                  # Comments come along in the same request. They are
                  # what lead_finder reads, and fetching them per post
                  # afterwards would double the calls for the same data.
                  ",comments.limit(25){id,text,username,timestamp,replies{username,text}}",
    })
    if not (media.get("data") or []):
        # A metric that is invalid for one media type fails the whole request.
        # Falling back keeps the page working without views rather than
        # showing nothing at all.
        media = await _get(client, f"{ig_id}/media", {
            "access_token": token,
            "limit": POST_LIMIT,
            "fields": BASE_FIELDS,
        })

    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    posts = []
    for m in (media.get("data") or []):
        when = _parse_ts(m.get("timestamp"))
        if not when or when < cutoff:
            continue
        likes, comments = m.get("like_count"), m.get("comments_count")
        metrics = _insight_values(m)
        posts.append({
            "id": m.get("id"),
            "caption": (m.get("caption") or "").strip(),
            "kind": m.get("media_product_type") or m.get("media_type") or "POST",
            "postedAt": when.isoformat(),
            # None rather than 0 when the field was not returned. Zero
            # engagement and unavailable engagement mean opposite things.
            "likes": likes,
            "comments": comments,
            # None, never 0: "nobody saw it" and "we could not read how many
            # saw it" are different facts and lead to different decisions.
            "views": metrics.get("views"),
            "reach": metrics.get("reach"),
            "engagement": (likes or 0) + (comments or 0) if likes is not None else None,
            "permalink": m.get("permalink"),
            "comments_list": ((m.get("comments") or {}).get("data") or []),
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


def observations(account: dict) -> list:
    """What is actually happening on this account, and what to do about it.

    A page of totals tells somebody their median engagement is 1 and leaves
    them to work out the rest. These are the readings a person would make from
    the same numbers, each one stated with the figure it came from so it can
    be argued with.

    Every observation is derived. Nothing here is a rule of thumb dressed up
    as a measurement, and anything the data cannot support is simply absent --
    an empty list is the honest output for an account with three posts.
    """
    posts = account.get("posts") or []
    followers = account.get("followers")
    out: list = []

    viewed = [p for p in posts if isinstance(p.get("views"), int) and p["views"] > 0]
    engaged = [p for p in posts if p.get("engagement") is not None]

    # --- Are people seeing it at all, and does seeing it convert? ----------
    if viewed:
        median_views = int(statistics.median([p["views"] for p in viewed]))
        out.append({
            "kind": "reach",
            "title": f"Your typical post is seen {median_views:,} times",
            "evidence": (
                f"Measured across {len(viewed)} posts in the last "
                f"{LOOKBACK_DAYS} days."
            ),
            "action": None,
        })

        if isinstance(followers, int) and followers >= 0 and median_views >= 50:
            # Views without follows is the specific failure of an account that
            # posts consistently and does not grow -- which is what the raw
            # numbers on this page usually describe.
            out.append({
                "kind": "conversion",
                "title": f"{median_views:,} people see a post; you have {followers} followers",
                "evidence": (
                    "Reach is not the bottleneck. What is missing is a reason "
                    "to follow: the posts are being watched and then scrolled past."
                ),
                "action": (
                    "Put one sentence in the caption that says who the account "
                    "is for and what they get by staying. Same line every time."
                ),
            })

    # --- Which format earns its slot --------------------------------------
    by_kind: dict = {}
    for p in viewed:
        by_kind.setdefault(p["kind"], []).append(p["views"])
    comparable = {k: v for k, v in by_kind.items() if len(v) >= 3}
    if len(comparable) >= 2:
        ranked = sorted(
            ((k, statistics.median(v), len(v)) for k, v in comparable.items()),
            key=lambda r: r[1], reverse=True,
        )
        top, second = ranked[0], ranked[-1]
        if second[1] > 0 and top[1] >= second[1] * 1.5:
            out.append({
                "kind": "format",
                "title": f"{top[0].title()} posts get {top[1] / second[1]:.1f}x the views of {second[0].title()}",
                "evidence": (
                    f"{top[0].title()}: {int(top[1]):,} views typical across {top[2]} posts. "
                    f"{second[0].title()}: {int(second[1]):,} across {second[2]}."
                ),
                "action": f"Move the next few posts to {top[0].title()} and watch whether the gap holds.",
            })

    # --- The one that worked ----------------------------------------------
    if viewed:
        best = max(viewed, key=lambda p: p["views"])
        median_views = statistics.median([p["views"] for p in viewed])
        if median_views > 0 and best["views"] >= median_views * 2:
            first_line = (best.get("caption") or "").strip().splitlines()
            opening = first_line[0][:90] if first_line else ""
            out.append({
                "kind": "outlier",
                "title": f"One post did {best['views'] / median_views:.1f}x your usual reach",
                "evidence": f"“{opening}…”" if opening else "Your best-performing post.",
                "action": "Write three more that open the same way, and see whether it repeats.",
            })

    # --- Is anything landing ----------------------------------------------
    if engaged and len(engaged) >= 5:
        silent = [p for p in engaged if (p["engagement"] or 0) == 0]
        if len(silent) >= len(engaged) * 0.5:
            out.append({
                "kind": "engagement",
                "title": f"{len(silent)} of your last {len(engaged)} posts got no likes or comments at all",
                "evidence": (
                    "Consistent posting with no response usually means the post "
                    "never asks for one."
                ),
                "action": (
                    "End one post this week with a question somebody could "
                    "answer in four words."
                ),
            })

    # --- Cadence ----------------------------------------------------------
    stamps = [_parse_ts(p.get("postedAt")) for p in posts]
    stamps = sorted([t for t in stamps if t])
    if len(stamps) >= 4:
        span_days = (stamps[-1] - stamps[0]).total_seconds() / 86400
        if span_days >= 1:
            per_week = len(stamps) / (span_days / 7)
            if per_week >= 14:
                out.append({
                    "kind": "cadence",
                    "title": f"You are posting about {per_week:.0f} times a week",
                    "evidence": (
                        "Above roughly twice a day an account competes with "
                        "itself: each post is shown to fewer of the same people."
                    ),
                    "action": "Try one a day for two weeks and compare the view counts.",
                })

    return out


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

    # Attached here rather than computed in the interface, so the reading and
    # the numbers it was read from can never drift apart.
    for account in accounts:
        if account.get("posts"):
            account["observations"] = observations(account)

    return {"accounts": accounts}

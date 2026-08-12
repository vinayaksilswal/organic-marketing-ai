"""What is actually working on this account, read from Instagram.

Every caption before this was written from the brand profile alone -- an
account's own results never fed back into what it published next. The system
could produce the same underperforming shape a thousand times and never notice.

WHAT THIS CAN AND CANNOT SEE, measured against a live token on 12 Aug 2026:

    like_count, comments_count      available with instagram_basic
    impressions, reach, views       BLOCKED, needs instagram_manage_insights
    Facebook post engagement        BLOCKED, needs pages_read_engagement

So this ranks on likes and comments, not views. That is a weaker signal and it
is stated plainly rather than dressed up: an account whose median post gets one
like has almost no signal to learn from, and the honest output in that case is
"not enough data" rather than a confident theory built on a difference between
two likes and three.

The insights permissions are already requested in META_SCOPES. The moment App
Review grants them, reach becomes available here and the ranking gets much
better without the callers changing.
"""

from __future__ import annotations

import re
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger

GRAPH = "https://graph.facebook.com/v21.0"

# Below this, differences between posts are noise. Ranking three posts by a
# one-like gap produces confident nonsense, and a caption writer told "carousels
# work best" on that basis will keep making carousels forever.
MIN_POSTS_FOR_SIGNAL = 12

# Engagement decays as an account grows, so old posts are not comparable with
# recent ones. Long enough to gather a sample, short enough to describe now.
LOOKBACK_DAYS = 60


def _hashtags(caption: str) -> List[str]:
    return re.findall(r"#\w+", caption or "")


def _first_line(caption: str) -> str:
    return (caption or "").strip().split("\n")[0][:120]


async def fetch_recent_media(
    ig_account_id: str, access_token: str, limit: int = 50
) -> List[Dict[str, Any]]:
    """Recent Instagram posts with the engagement fields we are allowed."""
    fields = (
        "id,caption,media_type,media_product_type,timestamp,"
        "like_count,comments_count,permalink"
    )
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.get(
                f"{GRAPH}/{ig_account_id}/media",
                params={"access_token": access_token, "fields": fields, "limit": limit},
            )
            data = r.json()
    except Exception as e:
        logger.warning(f"Could not read Instagram media: {e}")
        return []

    if "error" in data:
        logger.warning(f"Instagram media read refused: {data['error'].get('message')}")
        return []
    return data.get("data", []) or []


def analyse(media: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Turn raw posts into the few statements a caption writer can use.

    Deliberately small. A model handed twenty statistics writes about the
    statistics; handed three it writes a better caption.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    rows = []
    for m in media:
        ts = m.get("timestamp")
        try:
            when = datetime.fromisoformat((ts or "").replace("Z", "+00:00"))
        except Exception:
            continue
        if when < cutoff:
            continue
        rows.append({
            "id": m.get("id"),
            "caption": m.get("caption") or "",
            "kind": m.get("media_product_type") or m.get("media_type") or "UNKNOWN",
            "when": when,
            "score": (m.get("like_count") or 0) + 3 * (m.get("comments_count") or 0),
            "likes": m.get("like_count") or 0,
            "comments": m.get("comments_count") or 0,
        })

    if len(rows) < MIN_POSTS_FOR_SIGNAL:
        return {
            "enough_data": False,
            "posts": len(rows),
            "note": (
                f"Only {len(rows)} posts in the last {LOOKBACK_DAYS} days. "
                f"Need {MIN_POSTS_FOR_SIGNAL} before differences mean anything."
            ),
        }

    scores = [r["score"] for r in rows]
    median = statistics.median(scores)
    best = sorted(rows, key=lambda r: r["score"], reverse=True)[:5]

    # A format only counts as better if it clears the account's own median by a
    # margin. Anything less is the same performance with a different label.
    by_kind: Dict[str, List[int]] = {}
    for r in rows:
        by_kind.setdefault(r["kind"], []).append(r["score"])
    kind_medians = {
        k: statistics.median(v) for k, v in by_kind.items() if len(v) >= 3
    }
    best_kind = None
    if len(kind_medians) > 1:
        top = max(kind_medians, key=kind_medians.get)
        rest = [v for k, v in kind_medians.items() if k != top]
        if rest and kind_medians[top] > max(rest) * 1.5:
            best_kind = top

    # Openings, not whole captions: the first line is what decides the scroll.
    top_openings = [_first_line(r["caption"]) for r in best if r["caption"].strip()]

    # A tag is only interesting if it appears on several winners and is not
    # simply on everything.
    tag_scores: Dict[str, List[int]] = {}
    for r in rows:
        for tag in set(_hashtags(r["caption"])):
            tag_scores.setdefault(tag.lower(), []).append(r["score"])
    strong_tags = [
        tag for tag, vals in tag_scores.items()
        if len(vals) >= 3 and statistics.median(vals) > median * 1.3
    ][:15]

    return {
        "enough_data": True,
        "posts": len(rows),
        "median_engagement": median,
        "best_engagement": best[0]["score"] if best else 0,
        "best_format": best_kind,
        "top_openings": top_openings,
        "strong_hashtags": strong_tags,
        "flat": max(scores) <= 3,
    }


def to_caption_guidance(insights: Optional[Dict[str, Any]]) -> str:
    """The paragraph a caption prompt can actually use, or empty.

    Returns nothing rather than something vague when the account has no signal.
    A caption writer told "engagement is low, try harder" writes worse copy
    than one told nothing at all.
    """
    if not insights or not insights.get("enough_data"):
        return ""

    if insights.get("flat"):
        return (
            "This account's posts currently receive almost no engagement, so "
            "there is no pattern to copy and nothing here is evidence. Write "
            "the strongest possible post for the brand and audience described "
            "above, and open with a concrete, specific first line rather than "
            "a general statement."
        )

    parts = [
        f"On this account, the median post earns {insights['median_engagement']:.0f} "
        f"engagements and the best earned {insights['best_engagement']:.0f}."
    ]
    if insights.get("best_format"):
        parts.append(
            f"{insights['best_format']} posts clearly outperform the other "
            f"formats here."
        )
    if insights.get("top_openings"):
        shown = " / ".join(f'"{o}"' for o in insights["top_openings"][:3])
        parts.append(
            f"The opening lines of the best performing posts were: {shown}. "
            f"Match what makes these work -- specificity, tension or a concrete "
            f"claim -- without reusing the wording."
        )
    if insights.get("strong_hashtags"):
        parts.append(
            "Tags associated with above-average posts: "
            + " ".join(insights["strong_hashtags"][:8])
        )
    return " ".join(parts)


async def for_workspace(session: Any, workspace_id: str) -> Dict[str, Any]:
    """Read and analyse one workspace's Instagram performance."""
    from sqlalchemy import select

    from database import SocialConnection
    from services.crypto_service import decrypt_token

    conn = (await session.execute(
        select(SocialConnection).where(
            SocialConnection.businessProfileId == workspace_id
        ).limit(1)
    )).scalars().first()

    if not conn or not conn.igAccountId or not conn.fbAccessToken:
        return {"enough_data": False, "posts": 0, "note": "no Instagram account connected"}

    try:
        token = decrypt_token(conn.fbAccessToken)
    except Exception as e:
        logger.warning(f"Could not decrypt token for {workspace_id}: {e}")
        return {"enough_data": False, "posts": 0, "note": "token unreadable"}

    media = await fetch_recent_media(conn.igAccountId, token)
    return analyse(media)

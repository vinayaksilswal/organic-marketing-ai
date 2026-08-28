"""Whether each connected platform is actually publishing, and what to do.

WHY THIS EXISTS
---------------
Two Pages rejected every Facebook post for a fortnight. The reason was
recorded — in the errorLog column of individual posts, behind a green POSTED
badge, on a platform that was also succeeding on Instagram. Nobody could have
found it without reading the database, and nobody did.

A per-post error is the wrong altitude for a standing problem. "This post
failed" is noise you scroll past; "Facebook has published nothing for 20 days
and here is why" is a thing somebody fixes.

HOW THE STATE IS DERIVED
------------------------
From what actually happened, not from a stored flag. A flag has to be written
by something, that something can fail, and then the flag lies. Recent posts
carry the evidence: which platform ids came back, which errors were recorded,
and when the last real publish was.

THE RULES
---------
- Never attempted        -> unknown. Not a fault.
- Last attempt succeeded -> healthy.
- Every recent attempt failed with the same reason -> action required, with
  the reason and the fix.
- Failing intermittently -> degraded. Worth showing, not worth alarming.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select

# The id column that proves a platform actually published.
PROOF_FIELD = {
    "facebook": "fbPostId",
    "instagram": "igPostId",
    "x": "twitterPostId",
    "linkedin": "linkedinPostId",
}

# multi_publisher and the scheduler both record failures as "platform: reason".
_KEYED = re.compile(r"(?:^|\|)\s*([a-z]+)\s*:\s*(.+?)(?=\s*\||$)", re.IGNORECASE)

# How far back to look. Long enough to catch a standing block, short enough
# that a problem fixed last month does not still show as broken.
WINDOW_DAYS = 30
RECENT_ATTEMPTS = 8

LABEL = {
    "facebook": "Facebook",
    "instagram": "Instagram",
    "x": "X",
    "linkedin": "LinkedIn",
    "youtube": "YouTube",
}


def _reasons_by_platform(error_log: Optional[str]) -> Dict[str, str]:
    """Split "facebook: ... | linkedin: ..." into a per-platform mapping.

    A post to five platforms records one errorLog containing every failure.
    Attributing the whole string to every platform would show LinkedIn as
    broken because Facebook was.
    """
    if not error_log:
        return {}
    found: Dict[str, str] = {}
    for match in _KEYED.finditer(error_log):
        key = match.group(1).strip().lower()
        if key in PROOF_FIELD or key == "youtube":
            found[key] = match.group(2).strip()
    return found


def _targets(platform_token: Optional[str]) -> List[str]:
    """Which platforms a post row was aimed at."""
    token = (platform_token or "").upper()
    if token == "ALL":
        return ["facebook", "instagram", "x", "linkedin", "youtube"]
    if token == "BOTH":
        return ["facebook", "instagram"]
    return {
        "FACEBOOK": ["facebook"], "INSTAGRAM": ["instagram"],
        "TWITTER": ["x"], "X": ["x"],
        "LINKEDIN": ["linkedin"], "YOUTUBE": ["youtube"],
    }.get(token, [])


# What a person should do about the errors we have actually seen. Only reasons
# observed in production are here; inventing guidance for the rest would put
# confident wrong advice in front of somebody fixing their own account.
def _guidance(reason: str) -> Optional[str]:
    low = (reason or "").lower()
    if "confirm your identity" in low or "4854002" in low:
        return ("Open the Facebook app on your phone, go to this Page, and finish "
                "identity confirmation. It blocks every post until it is done. "
                "Nothing here needs reconnecting.")
    if "code 190" in low or "access token" in low or "expired" in low:
        return "The connection expired. Reconnect this account in Businesses & accounts."
    if "rate limit" in low or "429" in low or "too many requests" in low:
        return "The platform is rate-limiting this account. Posting resumes on its own."
    if "permission" in low or "scope" in low:
        return ("The connection is missing a permission. Disconnect and reconnect "
                "the account to grant it.")
    return None


async def report(session: Any, workspace_id: str) -> List[Dict[str, Any]]:
    """One row per connected platform. Never raises."""
    from database import SocialPost
    from services.multi_publisher import connected_platforms

    try:
        available = await connected_platforms(session, workspace_id)
    except Exception as e:
        logger.warning(f"Could not read connections for {workspace_id}: {e}")
        return []

    since = datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)
    try:
        posts = (await session.execute(
            select(SocialPost)
            .where(SocialPost.businessProfileId == workspace_id,
                   SocialPost.createdAt >= since)
            .order_by(SocialPost.createdAt.desc())
            .limit(120)
        )).scalars().all()
    except Exception as e:
        logger.warning(f"Could not read posts for {workspace_id}: {e}")
        posts = []

    out: List[Dict[str, Any]] = []
    for platform, is_connected in available.items():
        if not is_connected:
            continue

        attempts: List[bool] = []       # newest first
        last_success: Optional[datetime] = None
        last_reason: Optional[str] = None

        for post in posts:
            if platform not in _targets(post.platform):
                continue

            field = PROOF_FIELD.get(platform)
            published = bool(getattr(post, field, None)) if field else None
            reasons = _reasons_by_platform(post.errorLog)
            failed = platform in reasons

            # YouTube has no id column, so success is inferred from the absence
            # of a recorded failure on a post that did publish somewhere.
            if published is None:
                if failed:
                    published = False
                elif post.status in ("POSTED", "PUBLISHED"):
                    published = True
                else:
                    continue

            # The state is judged on the most recent handful of attempts, but
            # the scan keeps going: "last published 17 days ago" is the single
            # most useful line on this panel, and stopping at eight failures
            # meant a Page that worked until a fortnight ago reported "never".
            room = len(attempts) < RECENT_ATTEMPTS

            if published:
                if last_success is None and post.postedAt:
                    last_success = post.postedAt
                if room:
                    attempts.append(True)
            elif failed:
                if last_reason is None:
                    last_reason = reasons[platform]
                if room:
                    attempts.append(False)

        # Asked for directly rather than scanned for. A workspace posting every
        # four hours fills the recent-post window in under three weeks, so a
        # Page that last worked a fortnight ago reported "never" -- which reads
        # as "this never worked" when the truth is "this stopped working", and
        # those two send somebody to completely different places.
        field = PROOF_FIELD.get(platform)
        if last_success is None and field:
            try:
                column = getattr(SocialPost, field)
                last_success = (await session.execute(
                    select(SocialPost.postedAt)
                    .where(SocialPost.businessProfileId == workspace_id,
                           column.isnot(None))
                    .order_by(SocialPost.postedAt.desc())
                    .limit(1)
                )).scalars().first()
            except Exception:
                pass

        if not attempts:
            state, headline = "unknown", "Nothing published yet"
        elif attempts[0]:
            state, headline = "healthy", "Publishing normally"
        elif all(a is False for a in attempts):
            state, headline = "action_required", f"{LABEL.get(platform, platform)} is rejecting every post"
        else:
            state, headline = "degraded", "Some posts are failing"

        out.append({
            "platform": platform,
            "label": LABEL.get(platform, platform.title()),
            "state": state,
            "headline": headline,
            "reason": last_reason,
            "guidance": _guidance(last_reason or ""),
            "lastSuccess": last_success.isoformat() if last_success else None,
            "recentFailures": sum(1 for a in attempts if not a),
            "recentAttempts": len(attempts),
        })

    # Problems first. A healthy platform is not what somebody opened this for.
    order = {"action_required": 0, "degraded": 1, "unknown": 2, "healthy": 3}
    out.sort(key=lambda r: order.get(r["state"], 9))
    return out

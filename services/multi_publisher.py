"""Publishing one post to every platform a workspace has actually connected.

The worker used to attempt all four unconditionally. A workspace with only
Facebook and Instagram connected -- which is every workspace today -- appended
"Twitter: ..." and "LinkedIn: ..." to its delivery log on every single cycle,
because the services return None when there is no token. Two permanent
failures per post, on every post, for a reason that is not a failure at all.

That is worse than untidy. A log where two lines are always red is a log
nobody reads, so the day Instagram genuinely breaks it looks exactly like
every other day.

So: a platform with no credentials is SKIPPED, and skipped is reported
separately from failed.

ONE POST, FOUR VOICES
---------------------
The caption is written for Instagram -- long, warm, and carrying a wall of
hashtags. Posting that verbatim elsewhere is what makes cross-posting
obvious:

  X caps at 280 characters. The old code cut at 277 and appended an ellipsis,
  which lands mid-word and often mid-hashtag.

  LinkedIn has no character problem but a cultural one. A paragraph ending in
  fifteen hashtags reads as spam there, and the first line is what shows
  before "see more".

Each platform gets the same message shaped for how it is read. Not a different
message -- the same one, which is what keeps the brand consistent.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from loguru import logger
from sqlalchemy import select

X_LIMIT = 280
LINKEDIN_SOFT_LIMIT = 2800

_HASHTAG = re.compile(r"(?:^|\s)(#[A-Za-z0-9_]+)")


def _split_hashtags(caption: str) -> tuple[str, list[str]]:
    """The message, and its hashtags, separated."""
    tags = [m.group(1) for m in _HASHTAG.finditer(caption or "")]
    body = _HASHTAG.sub(" ", caption or "")
    body = re.sub(r"[ \t]{2,}", " ", body)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    return body, tags


def _truncate_on_a_word(text: str, limit: int) -> str:
    """Cut at a word boundary, never mid-word.

    The old behaviour sliced at limit-3 and appended an ellipsis, which
    routinely produced "...our new produ…" and broken half-hashtags.
    """
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[: limit - 1]
    if " " in cut:
        cut = cut[: cut.rindex(" ")]
    return cut.rstrip(" ,.;:-") + "…"


def caption_for(platform: str, caption: str) -> str:
    """The same message, shaped for how each platform is read."""
    platform = (platform or "").lower()
    body, tags = _split_hashtags(caption or "")

    if platform in ("x", "twitter"):
        # Two tags at most: on X a wall of them reads as spam and eats the
        # character budget the message needs.
        keep = " ".join(tags[:2])
        room = X_LIMIT - (len(keep) + 1 if keep else 0)
        text = _truncate_on_a_word(body, room)
        return f"{text} {keep}".strip() if keep else text

    if platform == "linkedin":
        # Hashtags move to their own line at the end rather than sitting in
        # the paragraph, and only a few survive.
        keep = " ".join(tags[:3])
        text = _truncate_on_a_word(body, LINKEDIN_SOFT_LIMIT)
        return f"{text}\n\n{keep}" if keep else text

    # Facebook and Instagram get the caption as written: it was written for
    # them, hashtags included.
    return (caption or "").strip()


async def connected_platforms(session: Any, workspace_id: str) -> dict[str, bool]:
    """Which platforms this workspace can actually publish to right now."""
    from database import SocialConnection

    conn = (await session.execute(
        select(SocialConnection).where(SocialConnection.businessProfileId == workspace_id)
    )).scalars().first()

    if not conn:
        return {"facebook": False, "instagram": False, "x": False, "linkedin": False}

    return {
        "facebook": bool(conn.fbPageId and conn.fbAccessToken),
        "instagram": bool(conn.igAccountId and conn.fbAccessToken),
        "x": bool(conn.twitterAccessToken and conn.twitterAccessSecret),
        # Both halves are needed: a token with no actor URN cannot name an
        # author, and LinkedIn rejects the post.
        "linkedin": bool(conn.linkedinAccessToken and getattr(conn, "linkedinActorUrn", None)),
    }


async def publish_everywhere(
    workspace_id: str,
    caption: str,
    media_urls: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Publish to every connected platform. Never raises.

    Returns {published: [...], skipped: [...], failed: [{platform, error}]}.
    Skipped and failed are kept apart on purpose -- one is a configuration
    fact and the other is something to fix, and merging them is how a log
    stops being read.
    """
    from database import AsyncSessionLocal

    media_urls = media_urls or []
    published: list[dict[str, Any]] = []
    skipped: list[str] = []
    failed: list[dict[str, str]] = []

    async with AsyncSessionLocal() as session:
        available = await connected_platforms(session, workspace_id)

    async def attempt(name: str, coro_factory) -> None:
        if not available.get(name):
            skipped.append(name)
            return
        try:
            result = await coro_factory()
            if result:
                published.append({"platform": name, "id": str(result)})
                logger.info(f"[PUBLISH] {name} ok for {workspace_id}")
            else:
                # A None return means the service refused without raising --
                # usually a credential it could not read.
                failed.append({"platform": name, "error": "returned no post id"})
        except Exception as e:
            failed.append({"platform": name, "error": str(e)[:200]})
            logger.error(f"[PUBLISH] {name} failed for {workspace_id}: {e}")

    from services.social_service import post_to_facebook, post_to_instagram

    await attempt("facebook", lambda: post_to_facebook(
        workspace_id, caption_for("facebook", caption), media_urls=media_urls))

    # Instagram cannot publish without media. That is a platform rule, not a
    # failure of this workspace, so it is a skip.
    if media_urls:
        await attempt("instagram", lambda: post_to_instagram(
            workspace_id, caption_for("instagram", caption), media_urls=media_urls))
    elif available.get("instagram"):
        skipped.append("instagram")

    from services.twitter_service import twitter_service

    await attempt("x", lambda: twitter_service.post_tweet(
        workspace_id, caption_for("x", caption)))

    from services.linkedin_service import linkedin_service

    await attempt("linkedin", lambda: linkedin_service.post_text(
        workspace_id, caption_for("linkedin", caption)))

    return {"published": published, "skipped": skipped, "failed": failed}

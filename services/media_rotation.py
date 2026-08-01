"""Least-recently-used rotation over a workspace's media catalog.

Both automation paths used to pick media in ways that repeated assets long
before the catalog was exhausted:

    routers/marketing.py    random.choice(postable)
    worker.py               all_media[0]  # after every candidate was "used"

The random one repeats by birthday collision — with six assets there is a
better-than-even chance of a repeat within four posts. The worker one is worse
and not random at all: once every candidate appears in the recent-post window
it returns index 0, the newest asset, on every single run forever. That is the
"same media again and again" the timeline shows.

The rule this module implements instead: an asset is never reused while any
other asset has been used less recently. Never-published assets always outrank
published ones, so a full pass over the catalog completes before anything
repeats, and the pass runs in a stable order rather than a shuffled one.
"""

from __future__ import annotations

from datetime import timezone
from typing import Any, List, Optional

from loguru import logger
from sqlalchemy import select

from database import Media, SocialPost

# Nothing in the catalog should be excluded from rotation by a LIMIT — that is
# how assets became permanently unreachable. This cap only exists so a runaway
# catalog cannot exhaust memory, and it sits far above any real workspace.
_MAX_CATALOG = 5000

# The window of history that defines "recently used". It has to comfortably
# exceed the catalog size or the oldest usage falls off the end and an asset
# looks never-used again.
_MAX_HISTORY = 2000


def _is_postable(media: Any) -> bool:
    """A row that can actually be attached to a post.

    The catalog also holds prompt-only notes from Video Studio, which have no
    URL and previously produced posts with no media attached.
    """
    url = (getattr(media, "url", "") or "").strip()
    if not url:
        return False
    if not getattr(media, "isActive", True):
        return False
    mime = (getattr(media, "mimeType", "") or "").lower()
    return mime.startswith("image/") or mime.startswith("video/")


async def select_next_media(
    session: Any,
    workspace_id: str,
    *,
    prefer_ai_generated: bool = False,
) -> Optional[Any]:
    """Return the media row that has gone longest without being published.

    Returns None when the workspace has no postable media at all. Callers
    distinguish "empty catalog" from "nothing postable" themselves, since the
    two need different messages to the user.
    """
    catalog_stmt = (
        select(Media)
        .where(Media.businessProfileId == workspace_id)
        .order_by(Media.createdAt.asc())
        .limit(_MAX_CATALOG)
    )
    catalog: List[Any] = [
        m for m in (await session.execute(catalog_stmt)).scalars().all() if _is_postable(m)
    ]
    if not catalog:
        return None

    # When was each URL last published? mediaUrls is a JSON array, so this is
    # resolved in Python rather than SQL to stay portable across the JSON
    # column types in play.
    history_stmt = (
        select(SocialPost.mediaUrls, SocialPost.postedAt, SocialPost.createdAt)
        .where(
            SocialPost.businessProfileId == workspace_id,
            SocialPost.mediaUrls.isnot(None),
        )
        .order_by(SocialPost.createdAt.desc())
        .limit(_MAX_HISTORY)
    )
    last_used: dict = {}
    for urls, posted_at, created_at in (await session.execute(history_stmt)).all():
        # A queued post still counts as consumed, otherwise the same asset is
        # selected again on the next tick before the first one publishes.
        when = posted_at or created_at
        if not urls or not when:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        for url in urls:
            if url and (url not in last_used or when > last_used[url]):
                last_used[url] = when

    never_used = [m for m in catalog if m.url not in last_used]
    if never_used:
        pool = never_used
        if prefer_ai_generated:
            # Only narrows within assets that are already unpublished, so a
            # preference can never resurrect an asset the rotation has covered.
            ai_first = [m for m in pool if getattr(m, "aiGenerated", False)]
            pool = ai_first or pool
        chosen = pool[0]  # oldest first — the catalog fills in a stable order
        logger.info(
            f"Media rotation: {len(never_used)} of {len(catalog)} assets still "
            f"unpublished, selected {chosen.id}"
        )
        return chosen

    # Full pass complete. Start the next one from whatever has waited longest.
    chosen = min(catalog, key=lambda m: last_used[m.url])
    logger.info(
        f"Media rotation: catalog of {len(catalog)} fully covered, recycling "
        f"{chosen.id} (last used {last_used[chosen.url].isoformat()})"
    )
    return chosen

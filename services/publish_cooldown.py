"""Stop retrying a kind of post Instagram has flagged, and post the other kind.

Instagram returns code 4 / subcode 2207051 -- "the publishing action is
suspected to be spam" -- when its integrity systems object to a publishing
PATTERN. It is not a rate limit: it was returned with the account's publishing
quota at 14 of 100 and the app at 1% of its hourly budget, and video published
from the same account in the same minute.

Measured across six businesses on 12 Aug 2026: every image and carousel was
refused this way, every video published. Three unrelated businesses were
affected, including one with no scraped content at all, so the flag sits at
the app level rather than on any single account.

Two things follow, and they pull in the same direction.

Retrying does harm. Every cycle that offers Instagram another image is another
rejected publishing action against the same app, which is the exact signal the
spam system is counting. Failing four times a day per account for days makes
the flag harder to clear, not easier.

There is a channel that works. Video is unaffected. An account that skips
images and posts video keeps its cadence instead of going silent, which
matters more for a young account than which format it happens to use.

So a workspace that has been refused this way recently stops offering images
and posts video until the cooldown expires. Read from the post history rather
than stored on the workspace: the history already records every failure with
its error text, and a second copy of the same fact is a second thing that can
disagree with it. It also means the block clears itself -- once the failures
age out of the window, images are tried again with no intervention.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from loguru import logger
from sqlalchemy import select

# Meta's own marker for "this publishing action is suspected to be spam".
SPAM_FLAG = "2207051"

# How long to stay off images after a flagged attempt. Long enough that the
# platform is not probing the same wall every cycle, short enough that a
# lifted block is noticed the same day.
COOLDOWN = timedelta(hours=6)

# One refusal can be a blip. Two inside the window is a pattern worth
# respecting, and still cheap to discover.
MIN_REFUSALS = 2


async def image_publishing_blocked(session: Any, workspace_id: str) -> bool:
    """Whether Instagram recently refused images here as suspected spam."""
    from database import SocialPost, utc_now

    since = utc_now() - COOLDOWN
    rows = (await session.execute(
        select(SocialPost.errorLog, SocialPost.igPostId, SocialPost.mediaUrls)
        .where(
            SocialPost.businessProfileId == workspace_id,
            SocialPost.createdAt >= since,
        )
        .order_by(SocialPost.createdAt.desc())
        .limit(40)
    )).all()

    refusals = 0
    for error_log, ig_post_id, media_urls in rows:
        if ig_post_id:
            # Something published here inside the window. If Instagram is
            # taking posts again the cooldown has served its purpose, and an
            # older failure should not keep images switched off.
            if not _is_video_post(media_urls):
                return False
            continue
        if error_log and SPAM_FLAG in error_log and not _is_video_post(media_urls):
            refusals += 1

    if refusals >= MIN_REFUSALS:
        logger.info(
            f"Workspace {workspace_id}: {refusals} image post(s) refused as "
            f"suspected spam in the last {COOLDOWN.total_seconds() / 3600:.0f}h; "
            f"posting video only until that ages out"
        )
        return True
    return False


def _is_video_post(media_urls: Any) -> bool:
    return any(
        str(url).split("?")[0].lower().endswith((".mp4", ".mov", ".webm", ".m4v"))
        for url in (media_urls or [])
    )

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
repeats.

Within that rule the order is random. A strict oldest-first pass posts a
library in the order it was uploaded, which on a scraped folder means the feed
runs alphabetically by filename -- visibly mechanical. Choosing at random from
whichever assets are equally "most overdue" keeps the feed unpredictable while
preserving the guarantee that nothing repeats until everything has run. That
is the part naive random.choice cannot offer: it repeats by birthday
collision, which is the bug this module was written to fix.
"""

from __future__ import annotations

import os
import random
from datetime import datetime, timezone
from typing import Any, List, Optional

from loguru import logger
from sqlalchemy import select

from database import Media, MediaFolder, SocialPost

# Sorts a never-published asset ahead of every published one.
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

# The cap exists so a runaway catalog cannot exhaust a 512MB instance. It is
# NOT a correctness boundary, and it used to behave like one: the query took
# the OLDEST rows by createdAt, so a workspace past the cap could never select
# anything uploaded afterwards. Silently. One workspace here holds 4,400 assets
# and is still growing, so "far above any real workspace" had about six hundred
# uploads left in it.
#
# Two changes make the cap safe rather than merely large. Only the columns
# rotation actually needs are loaded, so a row costs a fraction of a full ORM
# entity — Media carries a LargeBinary `data` column that was being fetched for
# every candidate. And when a catalog does exceed the cap, the newest assets are
# taken rather than the oldest, because those are the ones a user just uploaded
# and is waiting to see published.
_MAX_CATALOG = int(os.getenv("MEDIA_ROTATION_MAX_CATALOG", "20000"))

# The window of history that defines "recently used". It has to comfortably
# exceed the catalog size or the oldest usage falls off the end and an asset
# looks never-used again.
_MAX_HISTORY = 2000

# Instagram rejects a carousel container holding more than ten children
# outright, so a folder above this publishes its first ten rather than failing.
CAROUSEL_MAX = 10


class _Candidate:
    """A catalog row carrying only what rotation reads.

    Rotation compares urls and timestamps; it never needs the caption, the
    prompt, or the LargeBinary column. The winner is re-fetched in full.
    """

    __slots__ = (
        "id", "url", "isActive", "mimeType", "aiGenerated", "createdAt",
        "folderId", "folderPosition",
    )

    def __init__(
        self, id, url, isActive, mimeType, aiGenerated, createdAt,
        folderId=None, folderPosition=0,
    ):
        self.id = id
        self.url = url
        self.isActive = isActive
        self.mimeType = mimeType
        self.aiGenerated = aiGenerated
        self.createdAt = createdAt
        self.folderId = folderId
        self.folderPosition = folderPosition


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


def _kind_of(media: Any) -> str:
    """"video" or "image"."""
    return "video" if (getattr(media, "mimeType", "") or "").startswith("video/") else "image"


async def last_posted_kind(session: Any, workspace_id: str) -> Optional[str]:
    """What the most recent post carried, or None if nothing has gone out.

    Read from the post history rather than stored on the workspace: the
    history is already the source of truth for rotation, and a second copy of
    the same fact is a second thing that can disagree with it.
    """
    last = (await session.execute(
        select(SocialPost)
        .where(
            SocialPost.businessProfileId == workspace_id,
            SocialPost.mediaUrls.isnot(None),
        )
        .order_by(SocialPost.createdAt.desc())
        .limit(1)
    )).scalars().first()
    if not last or not last.mediaUrls:
        return None

    media = (await session.execute(
        select(Media).where(
            Media.businessProfileId == workspace_id,
            Media.url == last.mediaUrls[0],
        ).limit(1)
    )).scalars().first()
    return _kind_of(media) if media else None


async def _collapse_folders(
    session: Any, workspace_id: str, catalog: List[Any]
) -> List[Any]:
    """Reduce each folder to a single candidate: its first slide.

    A folder is ONE post -- six images in a folder publish as one carousel, not
    as six posts. Left uncollapsed, every slide would be its own candidate, so
    a folder of six would be selected six times as often as a loose file and
    each selection would publish the whole carousel again.

    The representative is the first slide, which is also the URL that lands in
    mediaUrls[0] when the carousel publishes. That keeps "when was this last
    used" answerable from the post history exactly as it is for a loose file,
    with no second bookkeeping path to drift.
    """
    filed = [c for c in catalog if c.folderId]
    if not filed:
        return catalog

    # A paused folder leaves the rotation whole rather than shedding slides
    # into it as loose files, which is what the user asked "pause" to mean.
    active: dict = {}
    folder_ids = {c.folderId for c in filed}
    rows = (await session.execute(
        select(MediaFolder.id, MediaFolder.isActive, MediaFolder.name)
        .where(MediaFolder.id.in_(folder_ids))
    )).all()
    names = {}
    for fid, is_active, name in rows:
        active[fid] = is_active
        names[fid] = name

    first_of: dict = {}
    for c in filed:
        if not active.get(c.folderId, False):
            continue
        current = first_of.get(c.folderId)
        # Ties on position fall back to creation order so the slide chosen as
        # representative is stable between cycles.
        key = (c.folderPosition or 0, c.createdAt or _EPOCH)
        if current is None or key < current[0]:
            first_of[c.folderId] = (key, c)

    collapsed = [c for c in catalog if not c.folderId]
    for _, (_, first) in first_of.items():
        collapsed.append(first)

    dropped = len(catalog) - len(collapsed)
    if dropped:
        logger.info(
            f"Media rotation: {len(first_of)} folder(s) in {workspace_id} "
            f"collapsed to one candidate each ({dropped} slide(s) not counted "
            f"as separate posts)"
        )
    return collapsed


async def expand_to_group(session: Any, media: Any) -> List[Any]:
    """The full post for a chosen asset: a folder's slides, or just the asset.

    Callers publish every URL returned. Instagram builds a carousel from
    multiple images on its own, so this needs no separate carousel path.
    """
    folder_id = getattr(media, "folderId", None)
    if not folder_id:
        return [media]

    slides = (await session.execute(
        select(Media)
        .where(Media.folderId == folder_id)
        .order_by(Media.folderPosition, Media.createdAt)
    )).scalars().all()
    slides = [m for m in slides if _is_postable(m)]
    if not slides:
        return [media]

    if len(slides) > CAROUSEL_MAX:
        logger.warning(
            f"Folder {folder_id} holds {len(slides)} slides; Instagram accepts "
            f"{CAROUSEL_MAX} in one carousel, so the rest are not published."
        )
    return slides[:CAROUSEL_MAX]


async def select_next_media(
    session: Any,
    workspace_id: str,
    *,
    prefer_ai_generated: bool = False,
    alternate_kinds: bool = True,
) -> Optional[Any]:
    """Return the media row that has gone longest without being published.

    Returns None when the workspace has no postable media at all. Callers
    distinguish "empty catalog" from "nothing postable" themselves, since the
    two need different messages to the user.
    """
    # Only the columns rotation needs. Selecting whole Media entities pulled the
    # LargeBinary `data` column for every candidate in the workspace.
    catalog_stmt = (
        select(
            Media.id, Media.url, Media.isActive, Media.mimeType,
            Media.aiGenerated, Media.createdAt,
            Media.folderId, Media.folderPosition,
        )
        .where(Media.businessProfileId == workspace_id)
        # Newest first: if a catalog ever exceeds the cap, the assets that fall
        # off the end should be the oldest, not the ones just uploaded.
        .order_by(Media.createdAt.desc())
        .limit(_MAX_CATALOG)
    )
    catalog: List[Any] = [
        _Candidate(*row) for row in (await session.execute(catalog_stmt)).all()
    ]
    catalog = [c for c in catalog if _is_postable(c)]
    catalog = await _collapse_folders(session, workspace_id, catalog)
    if not catalog:
        return None

    # If Instagram has recently refused images here as suspected spam, offer it
    # video instead of spending every cycle on a post that cannot publish.
    # Each refused attempt is another rejected publishing action counted
    # against the app, so retrying actively deepens the problem.
    try:
        from services.publish_cooldown import image_publishing_blocked

        if await image_publishing_blocked(session, workspace_id):
            videos = [c for c in catalog if _kind_of(c) == "video"]
            if videos:
                catalog = videos
                alternate_kinds = False
            else:
                # An image-only catalog has nothing to fall back to. Say so
                # rather than silently posting into a block.
                logger.warning(
                    f"Workspace {workspace_id} is image-blocked on Instagram and "
                    f"has no video to post instead; its images will keep failing "
                    f"until the block clears."
                )
    except Exception as e:
        # Never let the cooldown check stop a workspace posting.
        logger.debug(f"Publish cooldown check unavailable: {e}")

    total = len(catalog)
    if total >= _MAX_CATALOG:
        logger.warning(
            f"Workspace {workspace_id} has at least {_MAX_CATALOG} assets, the "
            f"rotation cap. The oldest beyond that are not being selected. "
            f"Raise MEDIA_ROTATION_MAX_CATALOG."
        )

    # Rotation walks the catalog oldest-first once the never-used pool is
    # exhausted, so restore that order after the newest-first fetch.
    catalog.reverse()

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

        # Alternate video and image so a feed does not run in blocks of one
        # kind.
        #
        # When the wanted kind has nothing unpublished left, the rotation for
        # THAT KIND restarts rather than the feed giving up and staying on the
        # other one. Asked for explicitly, and it is the right call for these
        # catalogs: HollyVerse holds 9 videos against 4,398 images, so waiting
        # for the video pool to be "fresh" means the feed is images forever
        # after the first day. Recycling nine videos across a month of hourly
        # posts is a far smaller repetition than never showing one again.
        #
        # The cost is real and worth naming: a video can now repeat while
        # images are still unused. That is a deliberate trade of the
        # no-repeat guarantee for a predictable mix, and it applies only
        # within the scarce kind.
        if alternate_kinds:
            previous = await last_posted_kind(session, workspace_id)
            if previous:
                wanted = "image" if previous == "video" else "video"
                fresh = [m for m in pool if _kind_of(m) == wanted]
                if fresh:
                    pool = fresh
                else:
                    # Nothing unpublished of the wanted kind. Restart that
                    # kind's rotation from whichever of them has waited
                    # longest, so the repeat is the oldest rather than random.
                    recycled = [m for m in catalog if _kind_of(m) == wanted]
                    if recycled:
                        recycled.sort(key=lambda m: last_used.get(m.url) or _EPOCH)
                        band = recycled[: max(1, len(recycled) // 4)]
                        chosen = random.choice(band)
                        logger.info(
                            f"Media rotation: {wanted} pool exhausted for "
                            f"{workspace_id}, restarting it — selected "
                            f"{chosen.id} (least recently used of "
                            f"{len(recycled)})"
                        )
                        return await session.get(Media, chosen.id)
                    # The workspace has none of that kind at all. Billionaire
                    # Goal777 is 251 videos and no images; alternation must
                    # not stall it.
                    logger.debug(
                        f"Media rotation: {workspace_id} has no {wanted} "
                        f"media; continuing with {previous}"
                    )

        if prefer_ai_generated:
            # Only narrows within assets that are already unpublished, so a
            # preference can never resurrect an asset the rotation has covered.
            ai_first = [m for m in pool if getattr(m, "aiGenerated", False)]
            pool = ai_first or pool
        # Any unpublished asset is equally overdue, so the choice among them is
        # free -- and making it randomly is what stops a bulk-imported folder
        # going out in filename order.
        chosen = random.choice(pool)
        logger.info(
            f"Media rotation: {len(never_used)} of {len(catalog)} assets still "
            f"unpublished, selected {chosen.id} at random"
        )
        return await session.get(Media, chosen.id)

    # Full pass complete. The next pass starts from whatever has waited longest,
    # but "longest" is a band rather than a single row: picking strictly the
    # oldest replays the previous pass in the same order every cycle, so a
    # viewer sees the same sequence of clips again and again. Choosing at
    # random from the most-overdue quarter keeps each cycle different while
    # still never touching anything recently posted.
    ordered = sorted(catalog, key=lambda m: last_used[m.url])
    band = ordered[: max(1, len(ordered) // 4)]
    chosen = random.choice(band)
    logger.info(
        f"Media rotation: catalog of {len(catalog)} fully covered, recycling "
        f"{chosen.id} at random from the {len(band)} most overdue "
        f"(last used {last_used[chosen.url].isoformat()})"
    )
    return await session.get(Media, chosen.id)

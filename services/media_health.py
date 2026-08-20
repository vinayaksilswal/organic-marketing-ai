"""Assets that no longer exist should stop being scheduled.

`_is_postable` asks whether a row LOOKS publishable: active, has a URL, is an
image or a video. It cannot ask whether the URL still resolves, and a Media row
pointing at a deleted file passes every one of those checks. The scheduler then
picks it, Meta tries to fetch it, and the post fails — with the failure landing
on the customer's delivery log rather than on the asset that caused it.

Six assets in one production workspace are in exactly that state: the
Cloudinary account serves fine, those particular files are gone.

WHAT THIS WILL NOT DO
---------------------
It deactivates on 404 and 410 only. Those mean "this is not coming back". A
timeout, a 429, a 5xx or a connection error mean "ask again later", and
treating them as death would empty a customer's catalog over a network blip —
which is a far worse failure than the one being fixed, and irreversible in
practice because nobody remembers which assets were fine yesterday.

Nothing is deleted. isActive goes false, the reason is recorded, and the row
stays there to be re-enabled by hand or by a later sweep that finds it serving
again.
"""

from __future__ import annotations

from typing import Any, Optional

import httpx
from loguru import logger
from sqlalchemy import select

# Definitively gone. Everything else is treated as temporary.
DEAD_STATUSES = {404, 410}

TIMEOUT = httpx.Timeout(15.0, connect=8.0)
CONCURRENCY = 6


async def _probe(client: httpx.AsyncClient, url: str) -> Optional[int]:
    """The status for this URL, or None when it could not be asked.

    HEAD first because it costs nothing, falling back to a ranged GET: some
    CDNs answer HEAD with 405 while serving the object perfectly well, and
    treating that as death would be the same mistake in a different place.
    """
    try:
        r = await client.head(url, follow_redirects=True)
        if r.status_code in (403, 405, 501):
            r = await client.get(url, headers={"Range": "bytes=0-0"}, follow_redirects=True)
        return r.status_code
    except Exception as e:
        logger.debug(f"Could not reach {url[:80]}: {type(e).__name__}")
        return None


async def sweep(workspace_id: Optional[str] = None, dry_run: bool = False) -> dict[str, Any]:
    """Check every active asset and retire the ones that are definitively gone."""
    import asyncio

    from database import AsyncSessionLocal, Media

    async with AsyncSessionLocal() as session:
        stmt = select(Media).where(Media.isActive.is_(True))
        if workspace_id:
            stmt = stmt.where(Media.businessProfileId == workspace_id)
        rows = (await session.execute(stmt)).scalars().all()

        candidates = [
            m for m in rows
            if (m.url or "").startswith("http")
            and (m.mimeType or "").lower().startswith(("image/", "video/"))
        ]

        checked = dead = unreachable = 0
        retired: list[dict] = []
        gate = asyncio.Semaphore(CONCURRENCY)

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            async def handle(media) -> None:
                nonlocal checked, dead, unreachable
                async with gate:
                    status = await _probe(client, media.url)
                checked += 1
                if status is None:
                    unreachable += 1
                    return
                if status not in DEAD_STATUSES:
                    return
                dead += 1
                retired.append({
                    "id": media.id,
                    "filename": media.filename,
                    "status": status,
                    "workspace": media.businessProfileId,
                })
                if not dry_run:
                    media.isActive = False
                    # generationError already means "why this asset is not
                    # usable", which is exactly what this is.
                    media.generationError = (
                        f"Storage returned {status} for this file, so it was retired "
                        f"from the posting rotation. Re-upload it to use it again."
                    )

            await asyncio.gather(*(handle(m) for m in candidates))

        if not dry_run and dead:
            await session.commit()

    logger.info(
        f"Media sweep: {checked} checked, {dead} retired, {unreachable} unreachable"
        + (" (dry run)" if dry_run else "")
    )
    return {
        "checked": checked,
        "retired": dead,
        "unreachable": unreachable,
        "dryRun": dry_run,
        "items": retired,
    }

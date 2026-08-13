"""Has any asset been posted twice?

While media_publish was returning 403 on posts it had actually published, the
asset stayed marked unpublished, so rotation was free to choose it again. That
is the expensive half of the bug: the same photo going out twice on a
customer's feed.

Checks every asset that appears in more than one post, and how far apart.
"""

import asyncio
import sys
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from database import (
    AsyncSessionLocal, BusinessProfile, SocialPost, init_db, utc_now,
)

LOOKBACK_DAYS = 3


async def main() -> None:
    await init_db()
    now = utc_now()
    cutoff = now - timedelta(days=LOOKBACK_DAYS)

    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(SocialPost, BusinessProfile.name)
            .join(BusinessProfile,
                  BusinessProfile.id == SocialPost.businessProfileId)
            .where(SocialPost.createdAt >= cutoff)
            .order_by(SocialPost.createdAt)
        )).all()

    seen = defaultdict(list)
    for post, name in rows:
        for url in (post.mediaUrls or []):
            seen[(name, url)].append(post)

    repeats = {k: v for k, v in seen.items() if len(v) > 1}

    print(f"{len(rows)} posts in the last {LOOKBACK_DAYS} days, "
          f"{len(seen)} distinct assets used\n")

    if not repeats:
        print("No asset was posted more than once. The 403 bug did not cause "
              "duplicates before it was fixed.")
        return

    print(f"{len(repeats)} asset(s) appear in more than one post:\n")
    for (name, url), posts in sorted(repeats.items(), key=lambda kv: -len(kv[1])):
        times = [p.createdAt for p in posts if p.createdAt]
        gap = ""
        if len(times) > 1:
            hours = (max(times) - min(times)).total_seconds() / 3600
            gap = f", {hours:.1f}h apart"
        live = sum(1 for p in posts if p.igPostId)
        print(f"  {name}: {url.split('/')[-1][:44]}")
        print(f"    {len(posts)} posts{gap}; {live} carry an Instagram id")


if __name__ == "__main__":
    asyncio.run(main())

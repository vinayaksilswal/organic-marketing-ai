"""Of the posts marked POSTED, how many actually reached Instagram?

A post is recorded POSTED if EITHER platform accepted it. That is reasonable
bookkeeping and a terrible dashboard: an account whose Instagram has been
failing for a week looks entirely healthy, because Facebook keeps succeeding
and carries the status.
"""

import asyncio
import sys
from collections import Counter
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from database import (
    AsyncSessionLocal, BusinessProfile, SocialPost, init_db, utc_now,
)


async def main() -> None:
    await init_db()
    cutoff = utc_now() - timedelta(days=7)

    async with AsyncSessionLocal() as session:
        profiles = (await session.execute(
            select(BusinessProfile).order_by(BusinessProfile.name)
        )).scalars().all()

        print(f"{'BUSINESS':<20} {'POSTED':>7} {'BOTH':>6} {'FB ONLY':>8} "
              f"{'IG ONLY':>8} {'NEITHER':>8}")
        print("-" * 62)

        for p in profiles:
            posts = (await session.execute(
                select(SocialPost).where(
                    SocialPost.businessProfileId == p.id,
                    SocialPost.status == "POSTED",
                    SocialPost.createdAt >= cutoff,
                )
            )).scalars().all()
            if not posts:
                continue

            c = Counter()
            for post in posts:
                has_fb = bool(post.fbPostId)
                has_ig = bool(post.igPostId)
                if has_fb and has_ig:
                    c["both"] += 1
                elif has_fb:
                    c["fb"] += 1
                elif has_ig:
                    c["ig"] += 1
                else:
                    c["neither"] += 1

            print(f"{(p.name or '?')[:19]:<20} {len(posts):>7} {c['both']:>6} "
                  f"{c['fb']:>8} {c['ig']:>8} {c['neither']:>8}")

            # The errors recorded on posts that still counted as successes are
            # where a silent one-platform failure explains itself.
            if c["fb"] or c["neither"]:
                sample = next(
                    (x.errorLog for x in posts if not x.igPostId and x.errorLog), None
                )
                if sample:
                    print(f"    IG error on 'successful' posts: {sample[:150]}")


if __name__ == "__main__":
    asyncio.run(main())

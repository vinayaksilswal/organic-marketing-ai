"""Why did Facebook not carry these posts?

Billionaire Goal777 and HollyVerse record 155 posts between them with no
Facebook id, all marked POSTED because Instagram succeeded. Both have a valid
token and working Page access, so the reason is in what was attempted.
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

WATCH = ("Billionaire Goal777", "HollyVerse", "BollyVerse")


async def main() -> None:
    await init_db()
    cutoff = utc_now() - timedelta(days=7)

    async with AsyncSessionLocal() as session:
        for name in WATCH:
            profile = (await session.execute(
                select(BusinessProfile).where(BusinessProfile.name == name)
            )).scalars().first()
            if not profile:
                continue

            posts = (await session.execute(
                select(SocialPost).where(
                    SocialPost.businessProfileId == profile.id,
                    SocialPost.createdAt >= cutoff,
                ).order_by(SocialPost.createdAt.desc()).limit(200)
            )).scalars().all()

            no_fb = [p for p in posts if not p.fbPostId]
            print(f"\n=== {name}: {len(no_fb)} of {len(posts)} posts had no Facebook id ===")

            errs = Counter()
            kinds = Counter()
            for p in no_fb:
                log = p.errorLog or "(no error recorded)"
                # Keep only the Facebook part of a combined log.
                fb_part = next(
                    (seg.strip() for seg in log.split("|") if seg.strip().startswith("FB")),
                    "(no FB error recorded)",
                )
                errs[fb_part[:130]] += 1
                kinds["video" if any(
                    str(u).lower().endswith((".mp4", ".mov")) for u in (p.mediaUrls or [])
                ) else ("image" if p.mediaUrls else "no media")] += 1

            for err, n in errs.most_common(5):
                print(f"  {n:>4}x  {err}")
            print(f"  attached: {dict(kinds)}")


if __name__ == "__main__":
    asyncio.run(main())

"""Which image posts have actually succeeded, and how many slides did they carry?

The user reports seeing 2-3 image posts land on the account, which contradicts
the conclusion that image publishing is blocked. Either the restriction has
lifted, or it depends on slide count. Both are visible in the post history.
"""

import asyncio
import sys
from collections import Counter
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import desc, select

from database import (
    AsyncSessionLocal, BusinessProfile, SocialPost, init_db, utc_now,
)


def is_video(urls) -> bool:
    return any(
        str(u).split("?")[0].lower().endswith((".mp4", ".mov", ".webm"))
        for u in (urls or [])
    )


async def main() -> None:
    await init_db()
    now = utc_now()
    since = now - timedelta(hours=24)

    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(SocialPost, BusinessProfile.name)
            .join(BusinessProfile,
                  BusinessProfile.id == SocialPost.businessProfileId)
            .where(SocialPost.createdAt >= since)
            .order_by(desc(SocialPost.createdAt))
        )).all()

    by_slides = {"ok": Counter(), "refused": Counter()}
    print("IMAGE posts in the last 24h, newest first\n")
    print(f"{'WHEN':<7} {'BUSINESS':<20} {'SLIDES':>6}  RESULT")
    print("-" * 60)

    for post, name in rows:
        urls = post.mediaUrls or []
        if not urls or is_video(urls):
            continue
        slides = len(urls)
        ok = bool(post.igPostId)
        by_slides["ok" if ok else "refused"][slides] += 1
        age = (now - post.createdAt).total_seconds() / 60
        print(f"{age:>5.0f}m {name[:19]:<20} {slides:>6}  "
              f"{'IG PUBLISHED ' + str(post.igPostId) if ok else 'IG refused'}")

    print("\n" + "=" * 60)
    print(f"published by slide count: {dict(sorted(by_slides['ok'].items()))}")
    print(f"refused   by slide count: {dict(sorted(by_slides['refused'].items()))}")

    if by_slides["ok"]:
        newest_ok = max(
            ((now - p.createdAt).total_seconds() / 60
             for p, _ in rows
             if p.igPostId and p.mediaUrls and not is_video(p.mediaUrls)),
            default=None,
        )
        if newest_ok is not None:
            print(f"most recent successful image post: {newest_ok:.0f} minutes ago")


if __name__ == "__main__":
    asyncio.run(main())

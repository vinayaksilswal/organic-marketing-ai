"""Every post since the geometry fix deployed, with its real per-platform result.

The question this answers is narrow and the only one that matters right now:
are posts made ON THE NEW CODE reaching both platforms?
"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from database import (
    AsyncSessionLocal, BusinessProfile, SocialPost, init_db, utc_now,
)

# 60df1b1 went live on Render at roughly 19:20 UTC+5:30 on 12 Aug 2026.
DEPLOY = datetime(2026, 8, 12, 13, 50, tzinfo=timezone.utc)


async def main() -> None:
    await init_db()
    now = utc_now()
    print(f"now={now.isoformat()}  deploy={DEPLOY.isoformat()}")

    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(SocialPost, BusinessProfile.name)
            .join(BusinessProfile, BusinessProfile.id == SocialPost.businessProfileId)
            .where(SocialPost.createdAt >= DEPLOY)
            .order_by(SocialPost.createdAt)
        )).all()

        if not rows:
            print("\nNo posts at all since the deploy — the scheduler has not "
                  "run a cycle yet. Nothing is proven either way.")
            return

        print(f"\n{len(rows)} post(s) since deploy:\n")
        for post, name in rows:
            kind = "video" if any(
                str(u).lower().endswith((".mp4", ".mov"))
                for u in (post.mediaUrls or [])
            ) else "image"
            fb = "FB ok" if post.fbPostId else "FB --"
            ig = "IG ok" if post.igPostId else "IG --"
            when = post.createdAt.strftime("%H:%M")
            print(f"  {when}  {name[:18]:<19} {kind:<6} {post.status:<7} {fb}  {ig}")
            if post.errorLog:
                print(f"          {post.errorLog[:180]}")


if __name__ == "__main__":
    asyncio.run(main())

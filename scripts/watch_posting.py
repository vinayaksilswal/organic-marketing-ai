"""Emit one line per new post outcome. Proof the geometry fix worked, or that
it did not.

Prints only posts created after the script starts, so the history does not
drown the signal.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from database import (
    AsyncSessionLocal, BusinessProfile, SocialPost, init_db, utc_now,
)

WATCH = {"HollyVerse", "BollyVerse", "MyCart4U", "Lumively"}


async def main() -> None:
    await init_db()
    start = utc_now()
    seen: set = set()
    print(f"watching from {start.isoformat()}", flush=True)

    while True:
        try:
            async with AsyncSessionLocal() as session:
                rows = (await session.execute(
                    select(SocialPost, BusinessProfile.name)
                    .join(BusinessProfile,
                          BusinessProfile.id == SocialPost.businessProfileId)
                    .where(SocialPost.createdAt >= start)
                    .order_by(SocialPost.createdAt)
                )).all()

                for post, name in rows:
                    if post.id in seen or name not in WATCH:
                        continue
                    seen.add(post.id)
                    kind = "video" if any(
                        str(u).lower().endswith((".mp4", ".mov"))
                        for u in (post.mediaUrls or [])
                    ) else "image"
                    if post.status == "POSTED":
                        print(f"OK   {name}: {kind} published "
                              f"(ig={post.igPostId or '-'} fb={post.fbPostId or '-'})",
                              flush=True)
                    elif post.status == "FAILED":
                        err = (post.errorLog or "")[:110].replace("\n", " ")
                        print(f"FAIL {name}: {kind} — {err}", flush=True)
        except Exception as e:
            print(f"watch error: {type(e).__name__}: {e}", flush=True)

        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())

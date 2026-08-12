"""Did the corrected geometry fix work? One line per post, from the deploy on.

Reports each new post's per-platform outcome, and a running tally, so the
answer does not depend on reading a dashboard that counts a post as successful
when only one platform took it.
"""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from database import (
    AsyncSessionLocal, BusinessProfile, SocialPost, init_db,
)

# Only posts made after the geometry rewrite and the Graph error surfacing.
# Earlier posts are already accounted for and would only add noise.
DEPLOY = datetime(2026, 8, 12, 18, 0, tzinfo=timezone.utc)


async def main() -> None:
    await init_db()
    seen: set = set()
    ig_ok = ig_bad = fb_ok = fb_bad = 0

    while True:
        try:
            async with AsyncSessionLocal() as session:
                rows = (await session.execute(
                    select(SocialPost, BusinessProfile.name)
                    .join(BusinessProfile,
                          BusinessProfile.id == SocialPost.businessProfileId)
                    .where(SocialPost.createdAt >= DEPLOY)
                    .order_by(SocialPost.createdAt)
                )).all()

            for post, name in rows:
                if post.id in seen:
                    continue
                seen.add(post.id)

                is_video = any(
                    str(u).lower().endswith((".mp4", ".mov"))
                    for u in (post.mediaUrls or [])
                )
                kind = "video" if is_video else "image"

                if post.igPostId:
                    ig_ok += 1
                else:
                    ig_bad += 1
                if post.fbPostId:
                    fb_ok += 1
                else:
                    fb_bad += 1

                ig = "IG ok" if post.igPostId else "IG --"
                fb = "FB ok" if post.fbPostId else "FB --"
                print(f"{name[:16]:<17} {kind:<6} {fb}  {ig}   "
                      f"[running: IG {ig_ok}/{ig_ok + ig_bad}, "
                      f"FB {fb_ok}/{fb_ok + fb_bad}]", flush=True)

                if not post.igPostId and post.errorLog:
                    ig_err = next(
                        (s.strip() for s in post.errorLog.split("|")
                         if s.strip().startswith("IG")), "")
                    if ig_err:
                        print(f"    {ig_err[:150]}", flush=True)
                if not post.fbPostId and post.errorLog:
                    fb_err = next(
                        (s.strip() for s in post.errorLog.split("|")
                         if s.strip().startswith("FB")), "")
                    if fb_err:
                        print(f"    {fb_err[:150]}", flush=True)
        except Exception as e:
            print(f"watch error: {type(e).__name__}: {e}", flush=True)

        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())

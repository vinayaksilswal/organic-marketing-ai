"""Is the scheduler still running, and is rotation still returning media?

Asked because 4,397 HollyVerse assets were just filed into 678 folders, which
changed what rotation sees. A change that silently returns nothing would look
exactly like a stalled scheduler.
"""

import asyncio
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import desc, select

from database import (
    AsyncSessionLocal, BusinessProfile, MarketingLog, SocialPost, init_db, utc_now,
)
from services.media_rotation import expand_to_group, select_next_media


async def main() -> None:
    await init_db()
    now = utc_now()

    async with AsyncSessionLocal() as session:
        # When did the loop last record anything at all?
        recent_logs = (await session.execute(
            select(MarketingLog)
            .order_by(desc(MarketingLog.createdAt))
            .limit(5)
        )).scalars().all()

        print("most recent marketing log rows:")
        for log in recent_logs:
            age = now - log.createdAt if log.createdAt else None
            mins = f"{age.total_seconds() / 60:.0f} min ago" if age else "?"
            print(f"  {log.createdAt}  {mins:<14} "
                  f"{getattr(log, 'status', '?')}  "
                  f"{str(getattr(log, 'message', ''))[:80]}")

        last_post = (await session.execute(
            select(SocialPost).order_by(desc(SocialPost.createdAt)).limit(1)
        )).scalars().first()
        if last_post:
            age = (now - last_post.createdAt).total_seconds() / 60
            print(f"\nlast post of any kind: {age:.0f} min ago "
                  f"({last_post.createdAt})")

        # The important one: can rotation still choose something for each
        # workspace now that folders exist?
        print("\nrotation check per workspace:")
        profiles = (await session.execute(
            select(BusinessProfile).order_by(BusinessProfile.name)
        )).scalars().all()
        for p in profiles:
            try:
                chosen = await select_next_media(session, p.id)
            except Exception as e:
                print(f"  {p.name[:20]:<21} RAISED {type(e).__name__}: {e}")
                continue
            if chosen is None:
                print(f"  {p.name[:20]:<21} returns NOTHING — cannot post")
                continue
            group = await expand_to_group(session, chosen)
            kind = "carousel" if len(group) > 1 else "single"
            folder = f" folder={chosen.folderId[:8]}" if chosen.folderId else ""
            print(f"  {p.name[:20]:<21} ok — {kind} of {len(group)}{folder}")


if __name__ == "__main__":
    asyncio.run(main())

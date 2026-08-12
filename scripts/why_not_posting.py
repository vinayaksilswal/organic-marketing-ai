"""The loop is running and rotation returns media, but nothing publishes.

Prints the state each workspace is actually in when the scheduler looks at it,
plus what the last cycle recorded, so the gate that is refusing names itself
instead of being guessed at.
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


async def main() -> None:
    await init_db()
    now = utc_now()

    async with AsyncSessionLocal() as session:
        logs = (await session.execute(
            select(MarketingLog).order_by(desc(MarketingLog.createdAt)).limit(3)
        )).scalars().all()

        print("what the last cycles recorded:")
        for log in logs:
            print(f"\n  {log.createdAt}")
            for field in ("status", "message", "details", "errorLog", "type", "action"):
                value = getattr(log, field, None)
                if value:
                    print(f"    {field}: {str(value)[:700]}")

        print("\n\nper-workspace state the scheduler sees:")
        profiles = (await session.execute(
            select(BusinessProfile).order_by(BusinessProfile.name)
        )).scalars().all()

        for p in profiles:
            last = (await session.execute(
                select(SocialPost)
                .where(SocialPost.businessProfileId == p.id)
                .order_by(desc(SocialPost.createdAt))
                .limit(1)
            )).scalars().first()

            interval = getattr(p, "postingIntervalHours", None)
            paused = getattr(p, "automationPaused", None)
            auto = getattr(p, "autoGenerateCreatives", None)
            since = ((now - last.createdAt).total_seconds() / 3600) if last else None

            due = "?"
            if interval and since is not None:
                due = "DUE" if since >= interval else f"in {interval - since:.1f}h"

            print(f"  {p.name[:20]:<21} interval={str(interval):<5} "
                  f"paused={str(paused):<5} auto={str(auto):<5} "
                  f"lastPost={f'{since:.1f}h ago' if since is not None else 'never':<12} {due}")


if __name__ == "__main__":
    asyncio.run(main())

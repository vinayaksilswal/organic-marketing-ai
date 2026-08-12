"""Is each business actually publishing? One line per workspace.

Answers the question that matters before any feature work: which accounts are
posting, which are silent, and why.
"""

import asyncio
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from database import (
    AsyncSessionLocal, BusinessProfile, Media, SocialConnection, SocialPost,
    init_db, utc_now,
)


async def main() -> None:
    await init_db()
    now = utc_now()

    async with AsyncSessionLocal() as session:
        profiles = (await session.execute(
            select(BusinessProfile).order_by(BusinessProfile.name)
        )).scalars().all()

        print(f"{'BUSINESS':<22} {'INT':>4} {'PAUSE':>5} {'MEDIA':>6} "
              f"{'24H':>4} {'7D':>4} {'FAIL7':>5}  LAST POST / LAST ERROR")
        print("-" * 118)

        for p in profiles:
            posts = (await session.execute(
                select(SocialPost)
                .where(SocialPost.businessProfileId == p.id)
                .order_by(SocialPost.createdAt.desc())
                .limit(200)
            )).scalars().all()

            def since(days):
                cut = now - timedelta(days=days)
                return [x for x in posts if x.createdAt and x.createdAt >= cut]

            recent24 = [x for x in since(1) if x.status == "POSTED"]
            recent7 = [x for x in since(7) if x.status == "POSTED"]
            failed7 = [x for x in since(7) if x.status == "FAILED"]

            media_n = (await session.execute(
                select(Media).where(Media.businessProfileId == p.id)
            )).scalars().all()

            conn = (await session.execute(
                select(SocialConnection).where(
                    SocialConnection.businessProfileId == p.id
                ).limit(1)
            )).scalars().first()

            last = next((x for x in posts if x.status == "POSTED"), None)
            if last and last.postedAt:
                age = now - last.postedAt
                hours = age.total_seconds() / 3600
                note = f"{hours:.1f}h ago" if hours < 72 else f"{age.days}d ago"
            else:
                note = "NEVER POSTED"

            if not conn:
                note += "  [no social connection]"
            elif not conn.igAccountId:
                note += "  [no Instagram]"

            if failed7:
                err = (failed7[0].errorLog or "")[:52].replace("\n", " ")
                note += f"  ERR: {err}"

            print(
                f"{(p.name or '?')[:21]:<22} "
                f"{getattr(p, 'postingIntervalHours', 0) or 0:>4} "
                f"{'YES' if getattr(p, 'automationPaused', False) else '-':>5} "
                f"{len(media_n):>6} {len(recent24):>4} {len(recent7):>4} "
                f"{len(failed7):>5}  {note}"
            )


if __name__ == "__main__":
    asyncio.run(main())

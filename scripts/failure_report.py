"""Group recent failed posts by the error they actually recorded.

Guessing at this cost several nights already. The errorLog column holds what
happened; this counts it.
"""

import asyncio
import re
import sys
from collections import Counter
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from database import (
    AsyncSessionLocal, BusinessProfile, SocialPost, init_db, utc_now,
)


def _shape(err: str) -> str:
    """Collapse ids and numbers so the same fault groups together."""
    e = re.sub(r"\b\d{6,}\b", "<id>", err or "")
    e = re.sub(r"https?://\S+", "<url>", e)
    e = re.sub(r"\s+", " ", e).strip()
    return e[:150]


async def main() -> None:
    await init_db()
    cutoff = utc_now() - timedelta(days=7)

    async with AsyncSessionLocal() as session:
        profiles = (await session.execute(
            select(BusinessProfile).order_by(BusinessProfile.name)
        )).scalars().all()

        for p in profiles:
            failed = (await session.execute(
                select(SocialPost).where(
                    SocialPost.businessProfileId == p.id,
                    SocialPost.status == "FAILED",
                    SocialPost.createdAt >= cutoff,
                ).order_by(SocialPost.createdAt.desc()).limit(300)
            )).scalars().all()
            if not failed:
                continue

            print(f"\n=== {p.name}: {len(failed)} failed in 7 days ===")
            for shape, n in Counter(_shape(f.errorLog) for f in failed).most_common(6):
                print(f"  {n:>4}x  {shape or '(no error recorded)'}")

            # What was attached when it failed -- a video-only failure and an
            # image-only failure are different bugs.
            kinds = Counter(
                "video" if any(
                    str(u).lower().endswith((".mp4", ".mov", ".webm"))
                    for u in (f.mediaUrls or [])
                ) else ("image" if f.mediaUrls else "no media")
                for f in failed
            )
            print(f"  attached: {dict(kinds)}")


if __name__ == "__main__":
    asyncio.run(main())

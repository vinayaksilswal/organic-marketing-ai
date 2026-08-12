"""How many assets are in a format Instagram will actually accept?

Instagram's Content Publishing API accepts JPEG for images. It does not accept
WebP, and it does not convert: the container is created, the fetch succeeds,
and publishing fails with a format error that reads like a URL problem.
"""

import asyncio
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from database import AsyncSessionLocal, BusinessProfile, Media, init_db

# What Instagram's API will publish. JPEG only for images; MP4/MOV for video.
IG_OK_IMAGE = {".jpg", ".jpeg"}
IG_OK_VIDEO = {".mp4", ".mov"}


def _ext(url: str) -> str:
    tail = (url or "").split("?")[0].split("/")[-1]
    return ("." + tail.rsplit(".", 1)[-1].lower()) if "." in tail else "(none)"


async def main() -> None:
    await init_db()

    async with AsyncSessionLocal() as session:
        profiles = (await session.execute(
            select(BusinessProfile).order_by(BusinessProfile.name)
        )).scalars().all()

        for p in profiles:
            rows = (await session.execute(
                select(Media.url, Media.mimeType, Media.isActive)
                .where(Media.businessProfileId == p.id)
            )).all()
            if not rows:
                continue

            exts = Counter(_ext(u) for u, _, _ in rows)
            postable = sum(
                n for e, n in exts.items() if e in IG_OK_IMAGE or e in IG_OK_VIDEO
            )
            blocked = sum(
                n for e, n in exts.items()
                if e not in IG_OK_IMAGE and e not in IG_OK_VIDEO and e != "(none)"
            )

            print(f"\n=== {p.name}: {len(rows)} assets ===")
            for e, n in exts.most_common(8):
                ok = "publishable" if (e in IG_OK_IMAGE or e in IG_OK_VIDEO) else "REJECTED BY INSTAGRAM"
                print(f"  {n:>5}  {e:<8} {ok}")
            if blocked:
                pct = 100 * blocked / len(rows)
                print(f"  -> {blocked} of {len(rows)} ({pct:.0f}%) cannot publish as-is")


if __name__ == "__main__":
    asyncio.run(main())

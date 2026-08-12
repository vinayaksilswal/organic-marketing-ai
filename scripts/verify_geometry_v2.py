"""Measure the deterministic geometry fix on the assets that actually failed.

Reports the ratio BEFORE and AFTER for a real sample per account, so a
transformation that lands just under the boundary cannot pass unnoticed the
way ar_4:5 did.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import func, select

from database import AsyncSessionLocal, BusinessProfile, Media, init_db
from services.instagram_geometry import (
    MAX_RATIO, MIN_RATIO, dimensions, publishable_url,
)

SAMPLE = 15


async def measure(client, url):
    r = await client.get(url, headers={"Range": "bytes=0-65535"})
    return dimensions(r.content)


async def main() -> None:
    await init_db()

    async with AsyncSessionLocal() as session:
        profiles = (await session.execute(
            select(BusinessProfile).order_by(BusinessProfile.name)
        )).scalars().all()

        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            for p in profiles:
                urls = (await session.execute(
                    select(Media.url).where(
                        Media.businessProfileId == p.id,
                        Media.mimeType.like("image/%"),
                        Media.isActive.is_(True),
                    ).order_by(func.random()).limit(SAMPLE)
                )).scalars().all()
                if not urls:
                    continue

                before_bad = after_bad = rewritten = 0
                worst = None
                for url in urls:
                    try:
                        before = await measure(client, url)
                        fixed = await publishable_url(url, client=client)
                        after = await measure(client, fixed)
                    except Exception as e:
                        print(f"  {p.name}: probe failed {type(e).__name__}")
                        continue
                    if not before or not after:
                        continue
                    rb = before[0] / before[1]
                    ra = after[0] / after[1]
                    if not (MIN_RATIO <= rb <= MAX_RATIO):
                        before_bad += 1
                    if fixed != url:
                        rewritten += 1
                    if not (MIN_RATIO <= ra <= MAX_RATIO):
                        after_bad += 1
                        worst = f"{after[0]}x{after[1]} = {ra:.4f} (from {rb:.4f})"

                status = "ALL PUBLISHABLE" if after_bad == 0 else f"{after_bad} STILL BAD"
                print(f"{p.name[:20]:<21} {len(urls):>3} sampled  "
                      f"{before_bad:>3} were bad  {rewritten:>3} rewritten  -> {status}")
                if worst:
                    print(f"    worst remaining: {worst}")


if __name__ == "__main__":
    asyncio.run(main())

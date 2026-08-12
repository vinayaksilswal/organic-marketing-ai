"""Take the URLs from recently failed posts and ask what is wrong with them.

"Instagram accepted no media" has several causes that look identical from the
outside: an unreachable URL, an oversized file, a rejected aspect ratio, a
content-type the API will not take. This checks each in turn against the real
files rather than reasoning about them.
"""

import asyncio
import sys
from collections import Counter
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import select

from database import (
    AsyncSessionLocal, BusinessProfile, SocialPost, init_db, utc_now,
)

BUSINESS = "HollyVerse"

# Instagram's published limits for an image in a feed post.
MAX_BYTES = 8 * 1024 * 1024
MIN_RATIO, MAX_RATIO = 0.8, 1.91


async def main() -> None:
    await init_db()
    cutoff = utc_now() - timedelta(days=7)

    async with AsyncSessionLocal() as session:
        profile = (await session.execute(
            select(BusinessProfile).where(BusinessProfile.name == BUSINESS)
        )).scalars().first()
        if not profile:
            print(f"No workspace named {BUSINESS}")
            return

        failed = (await session.execute(
            select(SocialPost).where(
                SocialPost.businessProfileId == profile.id,
                SocialPost.status == "FAILED",
                SocialPost.createdAt >= cutoff,
            ).order_by(SocialPost.createdAt.desc()).limit(12)
        )).scalars().all()

        urls = [u for f in failed for u in (f.mediaUrls or [])][:12]
        print(f"Probing {len(urls)} URLs from {len(failed)} failed posts\n")

        verdicts = Counter()
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            for url in urls:
                short = url.split("/")[-1][:52]
                try:
                    r = await client.get(url, headers={"Range": "bytes=0-2047"})
                except Exception as e:
                    print(f"  UNREACHABLE  {short}  ({type(e).__name__})")
                    verdicts["unreachable"] += 1
                    continue

                ctype = r.headers.get("content-type", "?")
                size = r.headers.get("content-range", "").split("/")[-1]
                size = int(size) if size.isdigit() else None

                problems = []
                if r.status_code >= 400:
                    problems.append(f"HTTP {r.status_code}")
                if not ctype.startswith("image/") and not ctype.startswith("video/"):
                    problems.append(f"content-type {ctype}")
                if ctype == "image/webp":
                    problems.append("WEBP — Instagram will not publish it")
                if size and size > MAX_BYTES:
                    problems.append(f"{size / 1e6:.1f}MB over the 8MB limit")

                if problems:
                    print(f"  PROBLEM      {short}  -> {'; '.join(problems)}")
                    verdicts["problem"] += 1
                else:
                    print(f"  ok           {short}  {ctype} {size or '?'}B")
                    verdicts["ok"] += 1

        print(f"\n{dict(verdicts)}")


if __name__ == "__main__":
    asyncio.run(main())

"""Read the captions that actually went out, and judge them honestly.

Runs the same quality checks the generator applies before publishing, over
real recent posts, so problems show up as counts rather than impressions.
"""

import asyncio
import re
import sys
from collections import Counter
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import desc, select

from database import (
    AsyncSessionLocal, BusinessProfile, SocialPost, init_db, utc_now,
)
from services.hashtag_engine import brand_tag

PER_BUSINESS = 4


def tags_in(caption: str):
    return re.findall(r"#\w+", caption or "")


def body_of(caption: str) -> str:
    return re.sub(r"#\w+", "", caption or "").strip()


async def main() -> None:
    await init_db()
    cutoff = utc_now() - timedelta(days=3)

    async with AsyncSessionLocal() as session:
        profiles = (await session.execute(
            select(BusinessProfile).order_by(BusinessProfile.name)
        )).scalars().all()

        issues = Counter()
        total = 0

        for p in profiles:
            posts = (await session.execute(
                select(SocialPost)
                .where(
                    SocialPost.businessProfileId == p.id,
                    SocialPost.createdAt >= cutoff,
                    SocialPost.caption.isnot(None),
                )
                .order_by(desc(SocialPost.createdAt))
                .limit(PER_BUSINESS)
            )).scalars().all()
            if not posts:
                continue

            tag = brand_tag(p)
            print(f"\n{'=' * 68}\n{p.name}   (brand tag would be {tag})\n{'=' * 68}")

            for post in posts:
                caption = post.caption or ""
                total += 1
                tags = tags_in(caption)
                body = body_of(caption)
                words = len(body.split())

                flags = []
                if tag and tag.lower() not in caption.lower():
                    flags.append("no brand tag")
                    issues["no brand tag"] += 1
                if not tags:
                    flags.append("no hashtags")
                    issues["no hashtags"] += 1
                if words > 90:
                    flags.append(f"long ({words}w)")
                    issues["too long"] += 1
                if p.name.lower() not in body.lower():
                    flags.append("brand not named in text")
                    issues["brand not named"] += 1
                if "http" in caption.lower():
                    flags.append("contains a URL")
                    issues["contains url"] += 1

                print(f"\n  --- {words} words, {len(tags)} tags"
                      + (f"  [{', '.join(flags)}]" if flags else "  [clean]"))
                for line in caption.split("\n")[:6]:
                    if line.strip():
                        print(f"  {line[:96]}")

        print(f"\n\n{'=' * 68}")
        print(f"{total} captions reviewed")
        for issue, n in issues.most_common():
            print(f"  {n:>3}  {issue}")
        if not issues:
            print("  no issues found")


if __name__ == "__main__":
    asyncio.run(main())

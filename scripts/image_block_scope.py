"""Is the Instagram image block per-account, or app-wide?

It matters enormously. Per-account is those accounts' problem; app-wide means
no customer of this platform can publish an image to Instagram, and the folder
carousel feature cannot work for anyone.

Prints the exact Instagram error recorded against every recent image post,
grouped by business, so the scope is read off the data rather than inferred
from the two accounts that were looked at first.
"""

import asyncio
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from database import (
    AsyncSessionLocal, BusinessProfile, SocialPost, init_db,
)

SINCE = datetime(2026, 8, 12, 17, 0, tzinfo=timezone.utc)


def ig_error(log: str) -> str:
    if not log:
        return ""
    for segment in log.split("|"):
        segment = segment.strip()
        if segment.startswith("IG"):
            code = re.search(r"code (\d+)/(\d+)", segment)
            return f"code {code.group(1)}/{code.group(2)}" if code else segment[:90]
    return ""


async def main() -> None:
    await init_db()

    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(SocialPost, BusinessProfile.name)
            .join(BusinessProfile,
                  BusinessProfile.id == SocialPost.businessProfileId)
            .where(SocialPost.createdAt >= SINCE)
            .order_by(SocialPost.createdAt)
        )).all()

    by_business = defaultdict(lambda: {"video": Counter(), "image": Counter()})

    for post, name in rows:
        urls = post.mediaUrls or []
        if not urls:
            continue
        kind = "video" if any(
            str(u).lower().endswith((".mp4", ".mov")) for u in urls
        ) else "image"
        outcome = "IG ok" if post.igPostId else (ig_error(post.errorLog) or "IG failed")
        by_business[name][kind][outcome] += 1

    print(f"Instagram outcomes since {SINCE:%H:%M} UTC, by business and media kind\n")
    image_fail_codes = Counter()
    for name in sorted(by_business):
        print(f"  {name}")
        for kind in ("video", "image"):
            counts = by_business[name][kind]
            if not counts:
                continue
            summary = ", ".join(f"{n}x {outcome}" for outcome, n in counts.most_common())
            print(f"    {kind:<6} {summary}")
            if kind == "image":
                for outcome, n in counts.items():
                    if outcome != "IG ok":
                        image_fail_codes[outcome] += n

    print("\n" + "=" * 60)
    businesses_failing_images = [
        name for name, kinds in by_business.items()
        if any(o != "IG ok" for o in kinds["image"])
    ]
    businesses_ok_video = [
        name for name, kinds in by_business.items()
        if kinds["video"].get("IG ok")
    ]
    print(f"businesses whose IMAGES failed : {sorted(businesses_failing_images)}")
    print(f"businesses whose VIDEOS worked : {sorted(businesses_ok_video)}")
    print(f"image failure codes            : {dict(image_fail_codes)}")

    if len(businesses_failing_images) > 2:
        print("\nMore than the two scraped-content accounts are affected, so this "
              "is NOT explained by those accounts' content.")


if __name__ == "__main__":
    asyncio.run(main())

"""What do the filenames actually look like, and what groups them into a post?

The user's read is that the date identifies a post. The date may be too coarse
-- several posts can share a day -- so this prints real samples and counts how
many distinct groups each candidate key produces before anything is created.
"""

import asyncio
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from database import AsyncSessionLocal, BusinessProfile, Media, init_db

WORKSPACES = ("BollyVerse", "HollyVerse")

# anfxf_ai/anfxf_ai_2026-07-31_DbcfKPqCMeV_9.webp
#          ^account      ^date      ^shortcode ^slide
PATTERN = re.compile(
    r"(?P<account>[A-Za-z0-9_.]+?)_"
    r"(?P<date>\d{4}-\d{2}-\d{2})_"
    r"(?P<code>[A-Za-z0-9_-]+?)"
    r"(?:_(?P<slide>\d+))?"
    r"\.(?P<ext>[A-Za-z0-9]+)$"
)


async def main() -> None:
    await init_db()

    async with AsyncSessionLocal() as session:
        for name in WORKSPACES:
            profile = (await session.execute(
                select(BusinessProfile).where(BusinessProfile.name == name)
            )).scalars().first()
            if not profile:
                continue

            rows = (await session.execute(
                select(Media.filename, Media.folderId, Media.mimeType)
                .where(Media.businessProfileId == profile.id)
            )).all()

            print(f"\n=== {name}: {len(rows)} assets ===")
            print("  samples:")
            for fn, _, _ in rows[:5]:
                print(f"    {fn}")

            matched = 0
            by_date = defaultdict(list)
            by_code = defaultdict(list)
            already_filed = 0
            unmatched_samples = []

            for fn, folder_id, mime in rows:
                if folder_id:
                    already_filed += 1
                tail = (fn or "").split("/")[-1]
                m = PATTERN.match(tail)
                if not m:
                    if len(unmatched_samples) < 5:
                        unmatched_samples.append(tail)
                    continue
                matched += 1
                by_date[(m["account"], m["date"])].append(tail)
                by_code[(m["account"], m["date"], m["code"])].append(tail)

            print(f"\n  filename pattern matched: {matched} of {len(rows)}")
            print(f"  already in a folder     : {already_filed}")
            if unmatched_samples:
                print("  unmatched samples:")
                for u in unmatched_samples:
                    print(f"    {u}")

            multi_date = {k: v for k, v in by_date.items() if len(v) > 1}
            multi_code = {k: v for k, v in by_code.items() if len(v) > 1}
            print(f"\n  grouping by DATE      : {len(by_date)} groups, "
                  f"{len(multi_date)} with 2+ files")
            print(f"  grouping by SHORTCODE : {len(by_code)} groups, "
                  f"{len(multi_code)} with 2+ files")

            sizes = Counter(len(v) for v in by_date.values())
            print(f"  date group sizes  : {dict(sorted(sizes.items())[:8])}")
            sizes = Counter(len(v) for v in by_code.values())
            print(f"  code group sizes  : {dict(sorted(sizes.items())[:8])}")

            # A date group holding several shortcodes proves the date alone
            # would merge unrelated posts into one carousel.
            worst = None
            for (acct, date), files in by_date.items():
                codes = {PATTERN.match(f)["code"] for f in files}
                if worst is None or len(codes) > worst[1]:
                    worst = ((acct, date), len(codes), len(files))
            if worst:
                print(f"  busiest date {worst[0][1]}: {worst[2]} files across "
                      f"{worst[1]} distinct shortcode(s)")


if __name__ == "__main__":
    asyncio.run(main())

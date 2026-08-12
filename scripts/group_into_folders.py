"""Rebuild the original Instagram carousels as folders, from the filenames.

These libraries were scraped post by post, and the filenames still carry which
post each file came from. Grouping on that restores the original carousels
instead of publishing 4,400 slides as 4,400 unrelated single posts.

THE GROUPING KEY IS THE SHORTCODE, NOT THE DATE.

The date looks like the right key and is not: BollyVerse's busiest day holds 24
files across 5 distinct Instagram posts, so grouping by date would fuse five
unrelated carousels into one. The shortcode -- DXeL24alHVg -- is Instagram's
own id for a single post, so it groups exactly what was originally together.

Two layouts are in play and both are handled:

    BollyVerse   anfxf_ai/anfxf_ai_2026-04-23_DXeL24alHVg_3.jpg
                 date and code live in the filename
    HollyVerse   sensual_beautiful_angels/2026-04-26_DXmxt_UDB-o/
                     sensual_beautiful_angels_DXmxt_UDB-o_6.webp
                 date and code live in the DIRECTORY; the filename has no date

The trailing number is the slide's position in the original carousel, so the
folder is ordered by it rather than by upload time -- the order the audience
originally saw.

Groups larger than Instagram's ten-item limit are split into consecutive parts
rather than truncated, so no slide is stranded where it can never publish.

Run with no arguments for a dry run. Pass --apply to write.
"""

import argparse
import asyncio
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger
from sqlalchemy import select

from database import AsyncSessionLocal, BusinessProfile, Media, MediaFolder, init_db

WORKSPACES = ("BollyVerse", "HollyVerse")
CAROUSEL_MAX = 10

# A directory named "<date>_<shortcode>" -- HollyVerse's layout.
DIR_KEY = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})_(?P<code>.+)$")

# "<account>_<date>_<shortcode>_<slide>.<ext>" -- BollyVerse's layout. The code
# is greedy because shortcodes contain underscores (DXxLf_Rk4cP), so only the
# LAST _<digits> before the extension is the slide number.
FILE_KEY = re.compile(
    r"^.+?_(?P<date>\d{4}-\d{2}-\d{2})_(?P<code>.+)_(?P<slide>\d+)\.[A-Za-z0-9]+$"
)

# Trailing "_<digits>" on any basename, for the directory layout where the
# filename carries the slide but not the date.
SLIDE_ONLY = re.compile(r"_(?P<slide>\d+)\.[A-Za-z0-9]+$")


def parse(filename: str):
    """(group_key, slide_index) for one asset, or None if it is not part of a set."""
    if not filename:
        return None
    parts = filename.replace("\\", "/").split("/")
    basename = parts[-1]

    # Layout 1: the directory names the post.
    for segment in parts[:-1]:
        m = DIR_KEY.match(segment)
        if m:
            slide = SLIDE_ONLY.search(basename)
            return (
                f"{m['date']}_{m['code']}",
                int(slide["slide"]) if slide else 0,
            )

    # Layout 2: the filename names the post.
    m = FILE_KEY.match(basename)
    if m:
        return f"{m['date']}_{m['code']}", int(m["slide"])

    return None


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write the folders")
    args = ap.parse_args()

    await init_db()

    async with AsyncSessionLocal() as session:
        for name in WORKSPACES:
            profile = (await session.execute(
                select(BusinessProfile).where(BusinessProfile.name == name)
            )).scalars().first()
            if not profile:
                print(f"{name}: no such workspace")
                continue

            media = (await session.execute(
                select(Media).where(Media.businessProfileId == profile.id)
            )).scalars().all()

            groups = defaultdict(list)
            skipped_filed = 0
            unparsed = 0
            for m in media:
                # Never touch what the user filed by hand.
                if m.folderId:
                    skipped_filed += 1
                    continue
                parsed = parse(m.filename)
                if not parsed:
                    unparsed += 1
                    continue
                key, slide = parsed
                groups[key].append((slide, m))

            # A group of one is a single post already; a folder would add
            # nothing and would clutter the panel.
            sets = {k: v for k, v in groups.items() if len(v) > 1}
            singles = len(groups) - len(sets)
            oversized = {k: v for k, v in sets.items() if len(v) > CAROUSEL_MAX}

            folders_needed = sum(
                (len(v) + CAROUSEL_MAX - 1) // CAROUSEL_MAX for v in sets.values()
            )
            filed = sum(len(v) for v in sets.values())

            print(f"\n=== {name} ===")
            print(f"  {len(media)} assets, {skipped_filed} already filed by hand, "
                  f"{unparsed} with no recognisable post id")
            print(f"  {len(sets)} original posts with 2+ slides -> {filed} files")
            print(f"  {singles} single-slide posts left loose")
            print(f"  {len(oversized)} post(s) over {CAROUSEL_MAX} slides, split into parts")
            print(f"  folders to create: {folders_needed}")

            if not args.apply:
                for key in list(sets)[:3]:
                    slides = sorted(sets[key])
                    print(f"    e.g. {key}: {len(slides)} slides "
                          f"-> {[s for s, _ in slides][:12]}")
                continue

            created = 0
            for key, entries in sorted(sets.items()):
                entries.sort(key=lambda t: t[0])
                chunks = [
                    entries[i:i + CAROUSEL_MAX]
                    for i in range(0, len(entries), CAROUSEL_MAX)
                ]
                for index, chunk in enumerate(chunks, start=1):
                    label = key if len(chunks) == 1 else f"{key} (part {index})"
                    folder = MediaFolder(
                        name=label[:120],
                        businessProfileId=profile.id,
                    )
                    session.add(folder)
                    await session.flush()
                    for position, (_, asset) in enumerate(chunk):
                        asset.folderId = folder.id
                        asset.folderPosition = position
                    created += 1

                # Commit per post so an interruption leaves finished folders
                # intact rather than rolling back thousands of rows.
                await session.commit()

            print(f"  created {created} folder(s)")
            logger.info(f"{name}: {created} carousel folders rebuilt from filenames")


if __name__ == "__main__":
    asyncio.run(main())

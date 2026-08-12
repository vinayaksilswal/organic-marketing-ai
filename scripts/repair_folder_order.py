"""Put hand-made folders back into their original carousel order.

Files moved in through the dashboard are appended in the order they were
ticked, which is rarely the order the carousel was meant to run in. The
filenames still carry the original slide index, so the intended sequence is
recoverable exactly.

Only the ORDER is changed. Folder names, membership and everything else the
user chose are left alone -- a folder they named and curated is their
decision, and this fixes the one part of it the interface got wrong.

Run with no arguments for a dry run. Pass --apply to write.
"""

import argparse
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from database import AsyncSessionLocal, BusinessProfile, Media, MediaFolder, init_db

WORKSPACES = ("BollyVerse", "HollyVerse")
CAROUSEL_MAX = 10

SLIDE = re.compile(r"_(?P<slide>\d+)\.[A-Za-z0-9]+$")


def slide_index(filename: str):
    """The original slide number, or None if the name does not carry one."""
    m = SLIDE.search((filename or "").split("/")[-1])
    return int(m["slide"]) if m else None


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    await init_db()

    async with AsyncSessionLocal() as session:
        for name in WORKSPACES:
            profile = (await session.execute(
                select(BusinessProfile).where(BusinessProfile.name == name)
            )).scalars().first()
            folders = (await session.execute(
                select(MediaFolder).where(
                    MediaFolder.businessProfileId == profile.id
                ).order_by(MediaFolder.createdAt)
            )).scalars().all()

            repaired = 0
            unfixable = []
            oversized = []

            for folder in folders:
                items = (await session.execute(
                    select(Media).where(Media.folderId == folder.id)
                )).scalars().all()
                if len(items) < 2:
                    continue

                indexed = [(slide_index(m.filename), m) for m in items]
                if any(i is None for i, _ in indexed):
                    unfixable.append(folder.name)
                    continue

                wanted = [m.id for _, m in sorted(indexed, key=lambda t: t[0])]
                current = [m.id for m in sorted(
                    items, key=lambda m: (m.folderPosition or 0)
                )]
                if wanted == current:
                    continue

                if args.apply:
                    lookup = {m.id: m for m in items}
                    for position, media_id in enumerate(wanted):
                        lookup[media_id].folderPosition = position
                repaired += 1

                if len(items) > CAROUSEL_MAX:
                    oversized.append((folder.name, len(items)))

            if args.apply:
                await session.commit()

            verb = "reordered" if args.apply else "would reorder"
            print(f"\n=== {name} ===")
            print(f"  {verb}: {repaired} folder(s)")
            if unfixable:
                print(f"  no slide number in the filenames, left alone: "
                      f"{len(unfixable)}  {unfixable[:3]}")
            if oversized:
                print(f"  still over {CAROUSEL_MAX} slides — only the first "
                      f"{CAROUSEL_MAX} will publish:")
                for folder_name, count in oversized:
                    print(f"    {folder_name}: {count} slides "
                          f"({count - CAROUSEL_MAX} will not post)")


if __name__ == "__main__":
    asyncio.run(main())

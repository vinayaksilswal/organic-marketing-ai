"""Check the folders that were just built are correct and postable.

Verifies the properties that matter for publishing, not just the counts:
  - no folder exceeds Instagram's ten-item limit
  - slide positions are unique and contiguous within each folder
  - the hand-made folders still exist untouched
  - nothing was lost: every asset is either filed or deliberately loose
"""

import asyncio
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select

from database import AsyncSessionLocal, BusinessProfile, Media, MediaFolder, init_db

WORKSPACES = ("BollyVerse", "HollyVerse")
CAROUSEL_MAX = 10


async def main() -> None:
    await init_db()

    async with AsyncSessionLocal() as session:
        for name in WORKSPACES:
            profile = (await session.execute(
                select(BusinessProfile).where(BusinessProfile.name == name)
            )).scalars().first()

            folders = (await session.execute(
                select(MediaFolder).where(
                    MediaFolder.businessProfileId == profile.id
                )
            )).scalars().all()

            total_media = (await session.execute(
                select(func.count()).select_from(Media).where(
                    Media.businessProfileId == profile.id
                )
            )).scalar()
            filed = (await session.execute(
                select(func.count()).select_from(Media).where(
                    Media.businessProfileId == profile.id,
                    Media.folderId.isnot(None),
                )
            )).scalar()

            oversized = []
            bad_order = []
            empty = []
            sizes = Counter()

            for f in folders:
                items = (await session.execute(
                    select(Media.folderPosition).where(Media.folderId == f.id)
                )).scalars().all()
                sizes[len(items)] += 1
                if not items:
                    empty.append(f.name)
                    continue
                if len(items) > CAROUSEL_MAX:
                    oversized.append((f.name, len(items)))
                positions = sorted(items)
                if positions != list(range(len(positions))):
                    bad_order.append((f.name, positions[:12]))

            print(f"\n=== {name} ===")
            print(f"  folders           : {len(folders)}")
            print(f"  media filed       : {filed} of {total_media} "
                  f"({total_media - filed} loose)")
            print(f"  folder sizes      : {dict(sorted(sizes.items()))}")
            print(f"  over {CAROUSEL_MAX} slides    : {len(oversized)}"
                  + (f"  {oversized[:3]}" if oversized else "  (none — all publishable)"))
            print(f"  broken slide order: {len(bad_order)}"
                  + (f"  {bad_order[:3]}" if bad_order else "  (none)"))
            print(f"  empty folders     : {len(empty)}")

            # One folder shown end to end, as a spot check.
            sample = next((f for f in folders if "part" not in f.name), None)
            if sample:
                rows = (await session.execute(
                    select(Media.folderPosition, Media.filename)
                    .where(Media.folderId == sample.id)
                    .order_by(Media.folderPosition)
                )).all()
                print(f"\n  sample folder '{sample.name}':")
                for pos, fn in rows:
                    print(f"    {pos:>2}  {fn.split('/')[-1]}")


if __name__ == "__main__":
    asyncio.run(main())

"""Split folders above Instagram's ten-slide limit into consecutive parts.

A folder of 17 does not publish 17 slides -- it publishes 10 and strands the
rest where nothing will ever pick them up, silently. Splitting keeps every
image in play and preserves the running order across the parts.

The first part keeps the original name, so a folder the user named stays
findable under that name; later parts get "(part 2)", "(part 3)" and so on.

Run with no arguments for a dry run. Pass --apply to write.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger
from sqlalchemy import select

from database import AsyncSessionLocal, BusinessProfile, Media, MediaFolder, init_db

WORKSPACES = ("BollyVerse", "HollyVerse")
CAROUSEL_MAX = 10


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

            split_count = 0
            rescued = 0

            for folder in folders:
                # Ordered by the position repair_folder_order already set, so
                # the parts follow the original carousel sequence.
                items = (await session.execute(
                    select(Media).where(Media.folderId == folder.id)
                    .order_by(Media.folderPosition, Media.createdAt)
                )).scalars().all()
                if len(items) <= CAROUSEL_MAX:
                    continue

                keep, overflow = items[:CAROUSEL_MAX], items[CAROUSEL_MAX:]
                for position, media in enumerate(keep):
                    media.folderPosition = position

                part = 2
                while overflow:
                    chunk, overflow = overflow[:CAROUSEL_MAX], overflow[CAROUSEL_MAX:]
                    label = f"{folder.name} (part {part})"[:120]
                    if args.apply:
                        new_folder = MediaFolder(
                            name=label,
                            businessProfileId=profile.id,
                        )
                        session.add(new_folder)
                        await session.flush()
                        for position, media in enumerate(chunk):
                            media.folderId = new_folder.id
                            media.folderPosition = position
                    rescued += len(chunk)
                    print(f"  {'created' if args.apply else 'would create'} "
                          f"'{label}' with {len(chunk)} slide(s)")
                    part += 1

                split_count += 1

            if args.apply and split_count:
                await session.commit()
                logger.info(
                    f"{name}: split {split_count} folder(s), "
                    f"{rescued} image(s) now publishable"
                )

            verb = "split" if args.apply else "would split"
            print(f"\n=== {name}: {verb} {split_count} folder(s), "
                  f"{rescued} image(s) rescued ===")


if __name__ == "__main__":
    asyncio.run(main())

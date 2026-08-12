"""Does the cooldown read the live data correctly, and what will each post next?

A rule that fires on test fixtures and not on the real failures it was written
for is worse than none, so this asks the live database.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from database import AsyncSessionLocal, BusinessProfile, init_db
from services.media_rotation import expand_to_group, select_next_media
from services.publish_cooldown import image_publishing_blocked


async def main() -> None:
    await init_db()

    async with AsyncSessionLocal() as session:
        profiles = (await session.execute(
            select(BusinessProfile).order_by(BusinessProfile.name)
        )).scalars().all()

        print(f"{'BUSINESS':<22} {'IMAGE-BLOCKED':<14} WOULD POST NEXT")
        print("-" * 68)

        for p in profiles:
            blocked = await image_publishing_blocked(session, p.id)
            try:
                chosen = await select_next_media(session, p.id)
            except Exception as e:
                print(f"{p.name[:21]:<22} {str(blocked):<14} ERROR {type(e).__name__}")
                continue

            if chosen is None:
                print(f"{p.name[:21]:<22} {str(blocked):<14} nothing to post")
                continue

            group = await expand_to_group(session, chosen)
            kind = "video" if (chosen.mimeType or "").startswith("video/") else "image"
            shape = f"carousel of {len(group)}" if len(group) > 1 else kind
            flag = ""
            if blocked and kind == "image":
                flag = "  <-- image-only catalog, nothing else to offer"
            print(f"{p.name[:21]:<22} {'YES' if blocked else 'no':<14} {shape}{flag}")


if __name__ == "__main__":
    asyncio.run(main())

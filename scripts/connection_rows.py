"""How many SocialConnection rows does each workspace have, and do they agree?

_get_fb_credentials selects with no ORDER BY and takes .first(). With more than
one row that is whichever the database hands back, which can differ between
calls -- so Instagram can read a good row while Facebook reads a broken one on
the very same post.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from database import AsyncSessionLocal, BusinessProfile, SocialConnection, init_db


async def main() -> None:
    await init_db()

    async with AsyncSessionLocal() as session:
        profiles = (await session.execute(
            select(BusinessProfile).order_by(BusinessProfile.name)
        )).scalars().all()

        for p in profiles:
            conns = (await session.execute(
                select(SocialConnection).where(
                    SocialConnection.businessProfileId == p.id
                )
            )).scalars().all()
            if not conns:
                continue

            flag = "  <-- MORE THAN ONE" if len(conns) > 1 else ""
            print(f"\n{p.name}: {len(conns)} connection row(s){flag}")
            for c in conns:
                print(
                    f"    id={c.id[:8]}  page={c.fbPageId or 'NONE':<18} "
                    f"ig={c.igAccountId or 'NONE':<20} "
                    f"token={'yes' if c.fbAccessToken else 'NO':<3} "
                    f"created={getattr(c, 'createdAt', None)}"
                )


if __name__ == "__main__":
    asyncio.run(main())

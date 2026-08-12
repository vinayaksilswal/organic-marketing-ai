"""Add the provenOffers column and write the measured offers onto their businesses.

Run once against the live database:  python -m scripts.apply_proven_offers
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text

from database import BusinessProfile, AsyncSessionLocal, init_db
from services.proven_offers import MEASURED, backfill, for_profile, to_caption_guidance


async def main() -> None:
    engine = await init_db()
    async with engine.begin() as conn:
        await conn.execute(
            text('ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "provenOffers" JSONB')
        )
    print("column provenOffers ready")

    async with AsyncSessionLocal() as session:
        written = await backfill(session)
        print(f"backfilled {written} business(es)")

        profiles = (await session.execute(select(BusinessProfile))).scalars().all()
        for p in profiles:
            offers = for_profile(p)
            if not offers:
                continue
            print(f"\n=== {p.name} ===")
            print(to_caption_guidance(offers))

    known = ", ".join(MEASURED)
    print(f"\nmeasured table covers: {known}")


if __name__ == "__main__":
    asyncio.run(main())

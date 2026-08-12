"""Replicate post_to_facebook's exact payload, minus publication.

The only difference from production is published=false, which keeps the photo
in the page's media library instead of the feed. Nothing becomes visible.

Tests a real caption too: a bare upload succeeding proves less than it looks
if the caption is what Facebook objects to.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import select

from database import (
    AsyncSessionLocal, BusinessProfile, Media, SocialConnection, SocialPost,
    init_db,
)
from services.crypto_service import decrypt_token
from services.instagram_geometry import publishable_url

GRAPH = "https://graph.facebook.com/v21.0"


async def main() -> None:
    await init_db()

    async with AsyncSessionLocal() as session:
        profile = (await session.execute(
            select(BusinessProfile).where(BusinessProfile.name == "HollyVerse")
        )).scalars().first()
        conn = (await session.execute(
            select(SocialConnection).where(
                SocialConnection.businessProfileId == profile.id
            ).limit(1)
        )).scalars().first()
        token = decrypt_token(conn.fbAccessToken)

        # A caption that really went out, so the test uses production text.
        recent = (await session.execute(
            select(SocialPost).where(
                SocialPost.businessProfileId == profile.id,
                SocialPost.caption.isnot(None),
            ).order_by(SocialPost.createdAt.desc()).limit(1)
        )).scalars().first()
        caption = (recent.caption if recent else "test") or "test"

        img = (await session.execute(
            select(Media.url).where(
                Media.businessProfileId == profile.id,
                Media.mimeType.like("image/%"),
                Media.isActive.is_(True),
            ).limit(1)
        )).scalars().first()

        vid = (await session.execute(
            select(Media.url).where(
                Media.businessProfileId == profile.id,
                Media.mimeType.like("video/%"),
                Media.isActive.is_(True),
            ).limit(1)
        )).scalars().first()

        print(f"caption is {len(caption)} chars, starts: {caption[:70]!r}\n")

        async with httpx.AsyncClient(timeout=120) as client:
            # 1. Image with the real caption, unpublished.
            r = await client.post(
                f"{GRAPH}/{conn.fbPageId}/photos",
                data={
                    "access_token": token,
                    "message": caption,
                    "url": await publishable_url(img),
                    "published": "false",
                },
            )
            print(f"image + caption -> HTTP {r.status_code}: {json.dumps(r.json())[:300]}")

            # 2. The video endpoint. This one has no unpublished mode that is
            #    safe to assume, so only the URL is validated -- not posted.
            if vid:
                head = await client.head(vid)
                print(f"\nvideo url -> HTTP {head.status_code} "
                      f"type={head.headers.get('content-type')} "
                      f"size={head.headers.get('content-length')}")


if __name__ == "__main__":
    asyncio.run(main())

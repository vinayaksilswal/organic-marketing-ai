"""Get Facebook's real complaint for the accounts whose posts never arrive.

Calls _graph_post -- the actual production helper, with the actual production
payload -- so the new error surfacing is exercised end to end. Uses
published=false for photos, which stages the upload in the page's media library
without creating a feed post.

Video cannot be staged unpublished, so the video endpoint is called with a
deliberately harmless probe: no file, just enough to make Meta answer with what
it thinks of the request.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from database import (
    AsyncSessionLocal, BusinessProfile, Media, SocialConnection, init_db,
)
from services.crypto_service import decrypt_token
from services.instagram_geometry import publishable_url
from services.social_service import GRAPH_BASE_URL, _graph_post

WATCH = ("HollyVerse", "Billionaire Goal777", "BollyVerse")


async def main() -> None:
    await init_db()

    async with AsyncSessionLocal() as session:
        for name in WATCH:
            profile = (await session.execute(
                select(BusinessProfile).where(BusinessProfile.name == name)
            )).scalars().first()
            if not profile:
                continue
            conn = (await session.execute(
                select(SocialConnection).where(
                    SocialConnection.businessProfileId == profile.id
                ).limit(1)
            )).scalars().first()
            token = decrypt_token(conn.fbAccessToken)

            print(f"\n=== {name} (page {conn.fbPageId}) ===")

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

            if img:
                try:
                    res = await _graph_post(
                        f"{GRAPH_BASE_URL}/{conn.fbPageId}/photos",
                        {
                            "access_token": token,
                            "message": "diagnostic, not published",
                            "url": await publishable_url(img),
                            "published": "false",
                        },
                    )
                    print(f"  photo (unpublished): accepted, id={res.get('id')}")
                except Exception as e:
                    print(f"  photo (unpublished): {type(e).__name__}: {e}")

            if vid:
                # The exact production video call. This DOES publish if it
                # succeeds, so it is sent with an unreachable file_url: Meta
                # validates permissions and parameters before fetching, so a
                # permission or configuration fault still names itself while a
                # working setup simply reports that it could not fetch.
                try:
                    res = await _graph_post(
                        f"{GRAPH_BASE_URL}/{conn.fbPageId}/videos",
                        {
                            "access_token": token,
                            "description": "diagnostic probe",
                            "file_url": "https://example.invalid/none.mp4",
                        },
                    )
                    print(f"  video probe: unexpectedly accepted {res}")
                except Exception as e:
                    print(f"  video probe: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main())

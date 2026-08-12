"""Does a SINGLE image publish, when a carousel will not?

The distinction decides what is actually wrong:

  carousel refused, single image fine  -> the carousel flow is the problem
  both refused, video fine             -> image publishing is blocked outright

Every data point so far fits the second reading -- HollyVerse's 131 image
failures, BollyVerse's images failing while its videos publish, Billionaire
Goal777 being video-only and working -- but no single image has been published
since the geometry fix, so it has never been tested cleanly.

THIS PUBLISHES one image.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import select

from database import (
    AsyncSessionLocal, BusinessProfile, Media, SocialConnection, init_db,
)
from services.crypto_service import decrypt_token
from services.instagram_geometry import publishable_url

GRAPH = "https://graph.facebook.com/v21.0"
BUSINESS = "HollyVerse"


async def main() -> None:
    await init_db()
    async with AsyncSessionLocal() as session:
        profile = (await session.execute(
            select(BusinessProfile).where(BusinessProfile.name == BUSINESS)
        )).scalars().first()
        conn = (await session.execute(
            select(SocialConnection).where(
                SocialConnection.businessProfileId == profile.id
            ).limit(1)
        )).scalars().first()
        url = (await session.execute(
            select(Media.url).where(
                Media.businessProfileId == profile.id,
                Media.mimeType.like("image/%"),
                Media.isActive.is_(True),
            ).limit(1)
        )).scalars().first()

    token = decrypt_token(conn.fbAccessToken)

    async with httpx.AsyncClient(timeout=120) as client:
        fixed = await publishable_url(url, client=client)

        r = await client.post(
            f"{GRAPH}/{conn.igAccountId}/media",
            data={
                "access_token": token,
                "image_url": fixed,
                "caption": "Golden hour, quietly.",
            },
        )
        body = r.json()
        if "error" in body:
            print(f"container REFUSED: {json.dumps(body)[:300]}")
            return
        container = body.get("id")
        print(f"container ok: {container}")

        for _ in range(6):
            st = (await client.get(
                f"{GRAPH}/{container}",
                params={"access_token": token, "fields": "status_code"},
            )).json()
            if st.get("status_code") in ("FINISHED", "ERROR", "EXPIRED"):
                break
            await asyncio.sleep(5)
        print(f"status: {st.get('status_code')}")

        r = await client.post(
            f"{GRAPH}/{conn.igAccountId}/media_publish",
            data={"access_token": token, "creation_id": container},
        )
        body = r.json()
        print(f"publish -> HTTP {r.status_code}: {json.dumps(body)[:350]}")

        if "error" not in body:
            print("\nSINGLE IMAGE PUBLISHED — so only the CAROUSEL flow is blocked.")
        else:
            err = body["error"]
            print(f"\nSINGLE IMAGE REFUSED too: code={err.get('code')}"
                  f"/{err.get('error_subcode')}")
            print("Images are blocked outright on this account; video still works.")


if __name__ == "__main__":
    asyncio.run(main())

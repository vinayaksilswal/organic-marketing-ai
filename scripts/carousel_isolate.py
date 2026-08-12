"""Which call in the carousel flow does Instagram actually refuse?

The flow is: N child containers, then a parent CAROUSEL container, then
media_publish. The error surfaces as one message from the whole sequence, so
this walks it step by step and prints each result.

STOPS BEFORE media_publish. Nothing is posted.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import select

from database import (
    AsyncSessionLocal, BusinessProfile, Media, MediaFolder, SocialConnection,
    init_db,
)
from services.crypto_service import decrypt_token
from services.instagram_geometry import publishable_urls

GRAPH = "https://graph.facebook.com/v21.0"
BUSINESS = "HollyVerse"
PACING = 3.0


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

        folder = (await session.execute(
            select(MediaFolder).where(
                MediaFolder.businessProfileId == profile.id
            ).limit(1)
        )).scalars().first()
        urls = (await session.execute(
            select(Media.url).where(Media.folderId == folder.id)
            .order_by(Media.folderPosition).limit(3)
        )).scalars().all()

    token = decrypt_token(conn.fbAccessToken)
    fixed = await publishable_urls(list(urls))
    print(f"folder '{folder.name}', {len(fixed)} slides, pacing {PACING}s\n")

    children = []
    async with httpx.AsyncClient(timeout=90) as client:
        for index, url in enumerate(fixed):
            if index:
                await asyncio.sleep(PACING)
            r = await client.post(
                f"{GRAPH}/{conn.igAccountId}/media",
                data={
                    "access_token": token,
                    "image_url": url,
                    "is_carousel_item": "true",
                },
            )
            body = r.json()
            if "error" in body:
                err = body["error"]
                print(f"  child {index + 1}: REFUSED code={err.get('code')}"
                      f"/{err.get('error_subcode')} — {err.get('message')}")
            else:
                children.append(body.get("id"))
                print(f"  child {index + 1}: ok {body.get('id')}")

        if not children:
            print("\nNo children created — the refusal is at the CHILD step.")
            return

        await asyncio.sleep(PACING)
        r = await client.post(
            f"{GRAPH}/{conn.igAccountId}/media",
            data={
                "access_token": token,
                "media_type": "CAROUSEL",
                "children": ",".join(children),
                "caption": "diagnostic, not published",
            },
        )
        body = r.json()
        if "error" in body:
            err = body["error"]
            print(f"\n  PARENT: REFUSED code={err.get('code')}"
                  f"/{err.get('error_subcode')} — {err.get('message')}")
            print("\nThe refusal is at the PARENT container step.")
            return

        parent = body.get("id")
        print(f"\n  PARENT: ok {parent}")

        status = (await client.get(
            f"{GRAPH}/{parent}",
            params={"access_token": token, "fields": "status_code,status"},
        )).json()
        print(f"  status: {status.get('status_code')} — {status.get('status')}")
        print(f"\nEverything up to publish succeeded. Parent {parent} left "
              f"UNPUBLISHED, so the only untested step is media_publish.")


if __name__ == "__main__":
    asyncio.run(main())

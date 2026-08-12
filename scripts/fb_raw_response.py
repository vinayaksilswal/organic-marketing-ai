"""What does the Graph API actually return for these pages?

post_to_facebook only records a post when the response carries an id, and only
records a failure when the call raises. A 200 response in any other shape
produces neither -- no post, no error, and "credentials may be missing" in the
log. This prints the raw response so the shape is visible.

Uploads are UNPUBLISHED (published=false). An unpublished photo is a staging
object on the page's media library; it does not appear in the feed and nobody
sees it. No feed post is created by this script.
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
WATCH = ("HollyVerse", "Billionaire Goal777", "BollyVerse")


async def main() -> None:
    await init_db()

    async with AsyncSessionLocal() as session:
        for name in WATCH:
            profile = (await session.execute(
                select(BusinessProfile).where(BusinessProfile.name == name)
            )).scalars().first()
            conn = (await session.execute(
                select(SocialConnection).where(
                    SocialConnection.businessProfileId == profile.id
                ).limit(1)
            )).scalars().first()
            token = decrypt_token(conn.fbAccessToken)

            img = (await session.execute(
                select(Media.url).where(
                    Media.businessProfileId == profile.id,
                    Media.mimeType.like("image/%"),
                    Media.isActive.is_(True),
                ).limit(1)
            )).scalars().first()

            print(f"\n=== {name} (page {conn.fbPageId}) ===")

            async with httpx.AsyncClient(timeout=90) as client:
                # What kind of token is this, and can it publish?
                info = (await client.get(
                    f"{GRAPH}/{conn.fbPageId}",
                    params={
                        "access_token": token,
                        "fields": "id,name,access_token,tasks",
                    },
                )).json()
                if "error" in info:
                    print(f"  page read: ERROR {info['error'].get('message')}")
                else:
                    has_page_token = bool(info.get("access_token"))
                    print(f"  page: {info.get('name')}")
                    print(f"  tasks granted: {info.get('tasks')}")
                    print(f"  page-scoped token returned: {has_page_token}")

                if not img:
                    print("  no image asset to test with")
                    continue

                # The exact call post_to_facebook makes for a single image,
                # but unpublished so nothing reaches the feed.
                r = await client.post(
                    f"{GRAPH}/{conn.fbPageId}/photos",
                    data={
                        "access_token": token,
                        "url": await publishable_url(img),
                        "published": "false",
                    },
                )
                body = r.json()
                print(f"  POST /photos -> HTTP {r.status_code}")
                print(f"  body: {json.dumps(body)[:400]}")
                if "error" not in body:
                    print(f"  has 'id': {'id' in body}   has 'post_id': {'post_id' in body}")


if __name__ == "__main__":
    asyncio.run(main())

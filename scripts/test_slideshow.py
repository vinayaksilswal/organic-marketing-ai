"""Render one folder as a slideshow Reel, and check Instagram will take it.

Builds the video, uploads it, then creates an Instagram container and reads
its status. Stops before media_publish, so nothing is posted -- the question
is whether Instagram accepts the FORMAT, and the container answers that.
"""

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import select

from database import (
    AsyncSessionLocal, BusinessProfile, Media, MediaFolder, SocialConnection,
    init_db,
)
from services.crypto_service import decrypt_token
from services.slideshow import build_slideshow

GRAPH = "https://graph.facebook.com/v21.0"


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--business", default="HollyVerse")
    ap.add_argument("--publish", action="store_true",
                    help="actually post it, not just stage it")
    args = ap.parse_args()

    await init_db()

    async with AsyncSessionLocal() as session:
        profile = (await session.execute(
            select(BusinessProfile).where(BusinessProfile.name == args.business)
        )).scalars().first()
        conn = (await session.execute(
            select(SocialConnection).where(
                SocialConnection.businessProfileId == profile.id
            ).limit(1)
        )).scalars().first()

        folder = (await session.execute(
            select(MediaFolder)
            .where(MediaFolder.businessProfileId == profile.id)
            .limit(1)
        )).scalars().first()
        urls = (await session.execute(
            select(Media.url).where(Media.folderId == folder.id)
            .order_by(Media.folderPosition)
        )).scalars().all()

    print(f"folder '{folder.name}': {len(urls)} slides")

    media_id = str(uuid.uuid4())
    url = await build_slideshow(list(urls), profile.id, media_id, profile=profile)
    if not url:
        print("slideshow build FAILED")
        return
    print(f"built and uploaded: {url}")

    token = decrypt_token(conn.fbAccessToken)
    async with httpx.AsyncClient(timeout=180) as client:
        r = await client.post(
            f"{GRAPH}/{conn.igAccountId}/media",
            data={
                "access_token": token,
                "media_type": "REELS",
                "video_url": url,
                "caption": "A few frames from the archive.",
            },
        )
        body = r.json()
        if "error" in body:
            print(f"container REFUSED: {json.dumps(body)[:300]}")
            return
        container = body.get("id")
        print(f"container: {container}")

        for _ in range(24):
            st = (await client.get(
                f"{GRAPH}/{container}",
                params={"access_token": token, "fields": "status_code,status"},
            )).json()
            if st.get("status_code") in ("FINISHED", "ERROR", "EXPIRED"):
                break
            await asyncio.sleep(5)
        print(f"status: {st.get('status_code')} — {st.get('status')}")

        if st.get("status_code") != "FINISHED":
            return

        if not args.publish:
            print("\nInstagram accepted the slideshow as a Reel. "
                  "Left unpublished; pass --publish to post one.")
            return

        r = await client.post(
            f"{GRAPH}/{conn.igAccountId}/media_publish",
            data={"access_token": token, "creation_id": container},
        )
        body = r.json()
        print(f"publish -> HTTP {r.status_code}: {json.dumps(body)[:300]}")
        if "error" not in body:
            print(f"\nPUBLISHED {body.get('id')} — blocked images now reach "
                  f"Instagram as Reels.")


if __name__ == "__main__":
    asyncio.run(main())

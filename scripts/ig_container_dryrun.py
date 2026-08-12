"""Ask Instagram what is wrong with an asset, without publishing anything.

Creating a media container is a staging step: it uploads nothing to the feed
and expires on its own in 24 hours. Only the separate media_publish call makes
a post public, and this script never makes it. That makes the container the
one safe way to get the API's real verdict instead of inferring it from
"accepted no media".

Also reports each image's pixel dimensions, because the most common silent
rejection is an aspect ratio outside Instagram's 0.8 to 1.91 window -- a
9:16 story-shaped image is 0.5625 and is refused.
"""

import asyncio
import io
import struct
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import select

from database import (
    AsyncSessionLocal, BusinessProfile, SocialConnection, SocialPost,
    init_db, utc_now,
)
from services.crypto_service import decrypt_token

GRAPH = "https://graph.facebook.com/v21.0"
BUSINESS = "HollyVerse"
MIN_RATIO, MAX_RATIO = 0.8, 1.91


def jpeg_size(data: bytes):
    """Width and height from JPEG SOF markers, without pulling in Pillow."""
    try:
        stream = io.BytesIO(data)
        if stream.read(2) != b"\xff\xd8":
            return None
        while True:
            marker = stream.read(2)
            if len(marker) < 2 or marker[0] != 0xFF:
                return None
            if 0xC0 <= marker[1] <= 0xCF and marker[1] not in (0xC4, 0xC8, 0xCC):
                stream.read(3)
                h, w = struct.unpack(">HH", stream.read(4))
                return w, h
            length = struct.unpack(">H", stream.read(2))[0]
            stream.seek(length - 2, 1)
    except Exception:
        return None


async def main() -> None:
    await init_db()
    cutoff = utc_now() - timedelta(days=7)

    async with AsyncSessionLocal() as session:
        profile = (await session.execute(
            select(BusinessProfile).where(BusinessProfile.name == BUSINESS)
        )).scalars().first()
        conn = (await session.execute(
            select(SocialConnection).where(
                SocialConnection.businessProfileId == profile.id
            ).limit(1)
        )).scalars().first()
        token = decrypt_token(conn.fbAccessToken)

        failed = (await session.execute(
            select(SocialPost).where(
                SocialPost.businessProfileId == profile.id,
                SocialPost.status == "FAILED",
                SocialPost.createdAt >= cutoff,
            ).order_by(SocialPost.createdAt.desc()).limit(4)
        )).scalars().all()
        posted = (await session.execute(
            select(SocialPost).where(
                SocialPost.businessProfileId == profile.id,
                SocialPost.status == "POSTED",
                SocialPost.createdAt >= cutoff,
            ).order_by(SocialPost.createdAt.desc()).limit(4)
        )).scalars().all()

    async def check(label, posts):
        print(f"\n--- {label} ---")
        async with httpx.AsyncClient(timeout=90, follow_redirects=True) as client:
            for p in posts:
                for url in (p.mediaUrls or [])[:1]:
                    dims = None
                    try:
                        head = await client.get(url, headers={"Range": "bytes=0-65535"})
                        dims = jpeg_size(head.content)
                    except Exception:
                        pass

                    ratio_note = ""
                    if dims:
                        w, h = dims
                        ratio = w / h
                        flag = "OK" if MIN_RATIO <= ratio <= MAX_RATIO else "OUT OF RANGE"
                        ratio_note = f"{w}x{h} ratio {ratio:.3f} {flag}"

                    r = await client.post(
                        f"{GRAPH}/{conn.igAccountId}/media",
                        data={
                            "access_token": token,
                            "image_url": url,
                            "caption": "diagnostic container, not published",
                        },
                    )
                    body = r.json()
                    if "error" in body:
                        msg = body["error"].get("message", "")
                        sub = body["error"].get("error_user_msg") or ""
                        print(f"  REJECTED  {ratio_note}")
                        print(f"            {msg}")
                        if sub:
                            print(f"            {sub}")
                    else:
                        print(f"  accepted  {ratio_note}  container {body.get('id')} "
                              f"(left unpublished, expires in 24h)")

    await check("assets from FAILED posts", failed)
    await check("assets from SUCCESSFUL posts", posted)


if __name__ == "__main__":
    asyncio.run(main())

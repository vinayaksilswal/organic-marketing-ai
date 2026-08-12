"""Prove the geometry fix on real assets, and on Instagram itself.

Two checks, because either alone can mislead:
  1. The transformed URL really returns an in-range image.
  2. Instagram accepts a container for it -- created and left unpublished.
"""

import asyncio
import io
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import func, select

from database import (
    AsyncSessionLocal, BusinessProfile, Media, SocialConnection, init_db,
)
from services.crypto_service import decrypt_token
from services.instagram_geometry import MAX_RATIO, MIN_RATIO, publishable_url

GRAPH = "https://graph.facebook.com/v21.0"
SAMPLE = 12


def jpeg_size(data: bytes):
    try:
        s = io.BytesIO(data)
        if s.read(2) != b"\xff\xd8":
            return None
        while True:
            marker = s.read(2)
            if len(marker) < 2 or marker[0] != 0xFF:
                return None
            if 0xC0 <= marker[1] <= 0xCF and marker[1] not in (0xC4, 0xC8, 0xCC):
                s.read(3)
                h, w = struct.unpack(">HH", s.read(4))
                return w, h
            length = struct.unpack(">H", s.read(2))[0]
            s.seek(length - 2, 1)
    except Exception:
        return None


async def main() -> None:
    await init_db()

    async with AsyncSessionLocal() as session:
        for name in ("HollyVerse", "BollyVerse", "MyCart4U"):
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
            urls = (await session.execute(
                select(Media.url).where(
                    Media.businessProfileId == profile.id,
                    Media.mimeType.like("image/%"),
                    Media.isActive.is_(True),
                ).order_by(func.random()).limit(SAMPLE)
            )).scalars().all()

            print(f"\n=== {name} ===")
            fixed_count = 0
            still_bad = 0
            token = decrypt_token(conn.fbAccessToken) if conn and conn.fbAccessToken else None

            async with httpx.AsyncClient(timeout=90, follow_redirects=True) as client:
                for url in urls:
                    new = publishable_url(url)
                    try:
                        r = await client.get(new, headers={"Range": "bytes=0-65535"})
                        dims = jpeg_size(r.content)
                    except Exception as e:
                        print(f"  FETCH FAILED {type(e).__name__}")
                        still_bad += 1
                        continue
                    if not dims:
                        print(f"  unreadable after transform (HTTP {r.status_code})")
                        still_bad += 1
                        continue
                    w, h = dims
                    ratio = w / h
                    ok = MIN_RATIO <= ratio <= MAX_RATIO
                    if new != url:
                        fixed_count += 1
                    if not ok:
                        still_bad += 1
                        print(f"  STILL OUT OF RANGE {w}x{h} {ratio:.4f}")

                print(f"  {len(urls)} sampled, {fixed_count} rewritten, "
                      f"{still_bad} still unpublishable")

                # The authoritative check: does Instagram take it?
                if token and conn.igAccountId and urls:
                    probe = publishable_url(urls[0])
                    resp = (await client.post(
                        f"{GRAPH}/{conn.igAccountId}/media",
                        data={
                            "access_token": token,
                            "image_url": probe,
                            "caption": "geometry check, not published",
                        },
                    )).json()
                    if "error" in resp:
                        print(f"  IG container: REJECTED — {resp['error'].get('message')}")
                    else:
                        cid = resp.get("id")
                        status = (await client.get(
                            f"{GRAPH}/{cid}",
                            params={"access_token": token, "fields": "status_code,status"},
                        )).json()
                        print(f"  IG container: accepted {cid} "
                              f"status={status.get('status_code')} (left unpublished)")


if __name__ == "__main__":
    asyncio.run(main())

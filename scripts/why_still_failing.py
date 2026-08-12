"""Take the asset from the post that just failed and follow it all the way.

Checks, in order:
  1. what the stored URL measures
  2. what the transformed URL measures
  3. what Instagram says when asked to stage it
  4. what the container's own status reports

Step 4 is the one the earlier verification skipped. A container being ACCEPTED
proved nothing -- Instagram accepted them before the fix too, and refused at
publish. The container's status_code is where the refusal actually shows.
"""

import asyncio
import io
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import select

from database import (
    AsyncSessionLocal, BusinessProfile, SocialConnection, SocialPost, init_db,
)
from services.crypto_service import decrypt_token
from services.instagram_geometry import publishable_url

GRAPH = "https://graph.facebook.com/v21.0"
DEPLOY = datetime(2026, 8, 12, 13, 50, tzinfo=timezone.utc)


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


async def measure(client, url):
    try:
        r = await client.get(url, headers={"Range": "bytes=0-65535"})
        dims = jpeg_size(r.content)
    except Exception as e:
        return f"fetch failed: {type(e).__name__}"
    if not dims:
        return f"HTTP {r.status_code}, no readable JPEG header"
    w, h = dims
    ratio = w / h
    verdict = "in range" if 0.8 <= ratio <= 1.91 else "OUT OF RANGE"
    return f"{w}x{h} ratio {ratio:.4f} {verdict}"


async def main() -> None:
    await init_db()

    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(SocialPost, BusinessProfile.name, SocialConnection)
            .join(BusinessProfile, BusinessProfile.id == SocialPost.businessProfileId)
            .join(SocialConnection,
                  SocialConnection.businessProfileId == BusinessProfile.id)
            .where(
                SocialPost.createdAt >= DEPLOY,
                SocialPost.igPostId.is_(None),
            )
            .order_by(SocialPost.createdAt.desc())
        )).all()

    if not rows:
        print("No Instagram-missing posts since the deploy.")
        return

    async with httpx.AsyncClient(timeout=90, follow_redirects=True) as client:
        for post, name, conn in rows[:3]:
            urls = [u for u in (post.mediaUrls or [])
                    if not str(u).lower().endswith((".mp4", ".mov"))]
            if not urls:
                print(f"\n=== {name}: video post, geometry does not apply ===")
                continue

            url = urls[0]
            fixed = await publishable_url(url)
            print(f"\n=== {name} at {post.createdAt.strftime('%H:%M')} ===")
            print(f"  stored URL      : {await measure(client, url)}")
            print(f"  transformed URL : {await measure(client, fixed)}")
            print(f"  transform applied: {fixed != url}")

            token = decrypt_token(conn.fbAccessToken)
            r = await client.post(
                f"{GRAPH}/{conn.igAccountId}/media",
                data={"access_token": token, "image_url": fixed,
                      "caption": "diagnostic, not published"},
            )
            body = r.json()
            if "error" in body:
                print(f"  container       : REJECTED - {body['error'].get('message')}")
                continue

            cid = body.get("id")
            # The step the earlier check missed.
            for attempt in range(6):
                st = (await client.get(
                    f"{GRAPH}/{cid}",
                    params={"access_token": token,
                            "fields": "status_code,status"},
                )).json()
                code = st.get("status_code")
                if code in ("FINISHED", "ERROR", "EXPIRED"):
                    break
                await asyncio.sleep(5)
            print(f"  container status: {st.get('status_code')} - {st.get('status')}")
            print(f"  (container {cid} left unpublished)")


if __name__ == "__main__":
    asyncio.run(main())

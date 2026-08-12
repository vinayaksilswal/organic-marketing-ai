"""Is Instagram blocking IMAGES, or blocking THESE images?

The two readings need completely different remedies:

  images as a category   nothing to do but appeal and wait
  these images           stop publishing scraped re-uploads; originals work

Every image tried so far came from a scraped library -- photographs that
already exist on Instagram under other accounts. Re-uploading content the
platform has already seen is exactly what image-spam detection is built to
catch, and it would explain why video, of which far less was published, went
untouched.

So this publishes an image Instagram has certainly never seen: generated here,
pixel by pixel, seconds before upload. Nothing about it matches any existing
media. If it publishes, the block is about the CONTENT, not the format.

Posts to quantcai by default -- the user's own platform, where a clean
abstract graphic is on-brand rather than out of place.
"""

import argparse
import asyncio
import hashlib
import io
import json
import math
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from PIL import Image, ImageDraw
from sqlalchemy import select

from database import (
    AsyncSessionLocal, BusinessProfile, SocialConnection, init_db,
)
from services.crypto_service import decrypt_token
from services.storage_service import upload_media_to_cloudinary

GRAPH = "https://graph.facebook.com/v21.0"


def build_image() -> bytes:
    """A 1080x1080 graphic that has never existed before.

    Seeded on the current microsecond, so every run produces different pixels
    and no perceptual hash can match anything already published anywhere.
    """
    seed = datetime.now(timezone.utc).isoformat()
    rnd = int(hashlib.sha256(seed.encode()).hexdigest(), 16)

    size = 1080
    img = Image.new("RGB", (size, size), (10, 12, 24))
    draw = ImageDraw.Draw(img)

    # A field of concentric arcs whose geometry depends on the seed.
    for i in range(60):
        offset = (rnd >> (i % 32)) & 0xFF
        radius = 60 + i * 17
        hue = (
            40 + (offset % 120),
            60 + ((offset * 3) % 150),
            140 + ((offset * 7) % 115),
        )
        box = [
            size // 2 - radius + (offset % 23) - 11,
            size // 2 - radius + (offset % 17) - 8,
            size // 2 + radius - (offset % 19) + 9,
            size // 2 + radius - (offset % 13) + 6,
        ]
        start = (offset * 5) % 360
        draw.arc(box, start=start, end=start + 90 + (offset % 180), fill=hue, width=3)

    for i in range(220):
        angle = (rnd >> (i % 24)) % 360
        distance = 80 + ((rnd >> (i % 16)) % 430)
        x = size // 2 + int(distance * math.cos(math.radians(angle + i)))
        y = size // 2 + int(distance * math.sin(math.radians(angle * 1.7 + i)))
        r = 1 + (i % 3)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(200, 220, 255))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--business", default="quantcai")
    ap.add_argument("--caption", default="Signal, not noise.")
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

    token = decrypt_token(conn.fbAccessToken)
    data = build_image()
    digest = hashlib.sha256(data).hexdigest()[:16]
    print(f"generated 1080x1080 JPEG, {len(data)} bytes, sha256 {digest}")

    media_id = str(uuid.uuid4())
    uploaded = await upload_media_to_cloudinary(
        profile.id, media_id, f"novel-{digest}.jpg", data, resource_type="image"
    )
    if not uploaded:
        print("Cloudinary upload failed; cannot run the test.")
        return
    url = uploaded["secure_url"]
    print(f"uploaded: {url}")

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            f"{GRAPH}/{conn.igAccountId}/media",
            data={"access_token": token, "image_url": url, "caption": args.caption},
        )
        body = r.json()
        if "error" in body:
            print(f"container REFUSED: {json.dumps(body)[:300]}")
            return
        container = body.get("id")
        print(f"container: {container}")

        for _ in range(8):
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
        print(f"publish -> HTTP {r.status_code}: {json.dumps(body)[:300]}")

        print()
        if "error" not in body:
            print("A BRAND NEW IMAGE PUBLISHED.")
            print("So images are not blocked as a format. What is blocked is the")
            print("SCRAPED content -- re-uploads of photos Instagram already has.")
        else:
            err = body["error"]
            print(f"REFUSED too: code={err.get('code')}/{err.get('error_subcode')}")
            print("An image with no prior existence anywhere is still refused, so")
            print("the block is on image publishing itself, app-wide, and no")
            print("change of content will get around it.")


if __name__ == "__main__":
    asyncio.run(main())

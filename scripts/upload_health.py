"""Why are media uploads failing?

Checks the things that fail quietly, in the order they are likely:
  1. recent Media rows and their generation status
  2. whether stored URLs actually resolve
  3. whether Cloudinary accepts a fresh upload right now
  4. how much of the Cloudinary plan is left
"""

import asyncio
import io
import sys
import uuid
from collections import Counter
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import desc, select

from database import AsyncSessionLocal, BusinessProfile, Media, init_db, utc_now


async def main() -> None:
    await init_db()
    now = utc_now()

    async with AsyncSessionLocal() as session:
        recent = (await session.execute(
            select(Media, BusinessProfile.name)
            .outerjoin(BusinessProfile, BusinessProfile.id == Media.businessProfileId)
            .where(Media.createdAt >= now - timedelta(days=2))
            .order_by(desc(Media.createdAt))
            .limit(25)
        )).all()

    print(f"=== {len(recent)} media rows in the last 48h ===")
    if recent:
        states = Counter((m.generationStatus or "—") for m, _ in recent)
        print(f"generationStatus: {dict(states)}\n")
        for m, biz in recent[:10]:
            age = (now - m.createdAt).total_seconds() / 60
            err = (m.generationError or "")[:70]
            print(f"  {age:>6.0f}m  {str(biz)[:14]:<15} {str(m.mimeType)[:12]:<13} "
                  f"{str(m.generationStatus or '—'):<9} {'URL' if m.url else 'NO URL':<7} {err}")
    else:
        print("  none — nothing has been uploaded in 48h\n")

    # Do the stored URLs actually work?
    print("\n=== are recent stored URLs reachable? ===")
    async with httpx.AsyncClient(timeout=45, follow_redirects=True) as client:
        checked = 0
        for m, _ in recent:
            if not m.url or checked >= 5:
                continue
            checked += 1
            try:
                r = await client.head(m.url)
                print(f"  HTTP {r.status_code}  {m.url.split('/')[-1][:48]}")
            except Exception as e:
                print(f"  FAILED {type(e).__name__}  {m.url[:60]}")
        if not checked:
            print("  no URLs to check")

    # Can Cloudinary take a new file right now?
    print("\n=== live Cloudinary upload test ===")
    try:
        from PIL import Image

        from services.storage_service import upload_media_to_cloudinary

        buf = io.BytesIO()
        Image.new("RGB", (64, 64), (90, 60, 200)).save(buf, format="JPEG")
        media_id = str(uuid.uuid4())
        result = await upload_media_to_cloudinary(
            "upload-health-check", media_id, f"probe-{media_id}.jpg",
            buf.getvalue(), resource_type="image",
        )
        if result and result.get("secure_url"):
            print(f"  OK — {result['secure_url'][:88]}")
        else:
            print(f"  FAILED — uploader returned {result!r}")
    except Exception as e:
        print(f"  RAISED {type(e).__name__}: {e}")

    # Plan headroom, which is the classic silent cause.
    print("\n=== Cloudinary account usage ===")
    try:
        import cloudinary
        import cloudinary.api

        usage = cloudinary.api.usage()
        for key in ("plan", "credits", "storage", "bandwidth", "transformations", "requests"):
            value = usage.get(key)
            if isinstance(value, dict):
                used = value.get("usage") or value.get("used_percent")
                limit = value.get("limit") or value.get("credits_limit")
                print(f"  {key}: used={used} limit={limit}")
            elif value is not None:
                print(f"  {key}: {value}")
    except Exception as e:
        print(f"  could not read usage: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main())

"""How much of each catalog is outside Instagram's publishable aspect ratio?

Instagram's feed accepts 0.8 (4:5 portrait) to 1.91 (landscape). An image
outside that is accepted as a container and then refused at publish, which
surfaces to the caller as "Instagram accepted no media from this post" -- a
message that sends you looking at URLs and file formats, both of which are
fine.

Samples rather than reads every asset: a 4,400-asset catalog scraped from one
source is overwhelmingly uniform, and the point is the proportion.
"""

import asyncio
import io
import struct
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import func, select

from database import AsyncSessionLocal, BusinessProfile, Media, init_db

MIN_RATIO, MAX_RATIO = 0.8, 1.91
SAMPLE = 25


def jpeg_size(data: bytes):
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

    async with AsyncSessionLocal() as session:
        profiles = (await session.execute(
            select(BusinessProfile).order_by(BusinessProfile.name)
        )).scalars().all()

        for p in profiles:
            images = (await session.execute(
                select(Media.url)
                .where(
                    Media.businessProfileId == p.id,
                    Media.mimeType.like("image/%"),
                    Media.isActive.is_(True),
                )
                .order_by(func.random())
                .limit(SAMPLE)
            )).scalars().all()
            if not images:
                continue

            shapes = Counter()
            bad = 0
            async with httpx.AsyncClient(timeout=45, follow_redirects=True) as client:
                for url in images:
                    try:
                        r = await client.get(url, headers={"Range": "bytes=0-65535"})
                        dims = jpeg_size(r.content)
                    except Exception:
                        dims = None
                    if not dims:
                        shapes["unreadable"] += 1
                        continue
                    w, h = dims
                    ratio = w / h
                    shapes[f"{w}x{h} ({ratio:.3f})"] += 1
                    if not (MIN_RATIO <= ratio <= MAX_RATIO):
                        bad += 1

            total = sum(shapes.values())
            pct = 100 * bad / total if total else 0
            verdict = "OK" if bad == 0 else f"{bad}/{total} ({pct:.0f}%) UNPUBLISHABLE"
            print(f"\n=== {p.name} — sampled {total} images: {verdict} ===")
            for shape, n in shapes.most_common(5):
                print(f"  {n:>3}x  {shape}")


if __name__ == "__main__":
    asyncio.run(main())

"""Which Cloudinary transformation actually fixes the ratio? Measured, not assumed."""

import asyncio
import io
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

# A real HollyVerse asset measured at 1440x1920 (ratio 0.750).
BASE = ("https://res.cloudinary.com/qpojfnua/image/upload/"
        "v1785824093/tenants/a9f955ac-c4d2-4646-b9b0-68e5118bd0ef/"
        "media/fa4faa5b-6446-4811-b6b3-a6beed88ad62.jpg")

CANDIDATES = [
    ("unchanged (control)", ""),
    ("smart crop to 4:5", "c_fill,ar_4:5,g_auto"),
    ("pad to 4:5, blurred fill", "c_pad,ar_4:5,b_blurred:400:15"),
    ("pad to 4:5, auto colour", "c_pad,ar_4:5,b_auto"),
    ("conditional: only if too tall", "if_ar_lt_0.8,c_fill,ar_4:5,g_auto,if_end"),
    ("conditional slash form", "if_ar_lt_0.8/c_fill,ar_4:5,g_auto/if_end"),
    ("conditional pad, too tall", "if_ar_lt_0.8/c_pad,ar_4:5,b_blurred:400:15/if_end"),
]


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


def build(transform: str) -> str:
    if not transform:
        return BASE
    return BASE.replace("/image/upload/", f"/image/upload/{transform}/")


async def main() -> None:
    async with httpx.AsyncClient(timeout=90, follow_redirects=True) as client:
        for label, transform in CANDIDATES:
            url = build(transform)
            try:
                r = await client.get(url, headers={"Range": "bytes=0-65535"})
            except Exception as e:
                print(f"  {label:<32} ERROR {type(e).__name__}")
                continue
            if r.status_code >= 400:
                print(f"  {label:<32} HTTP {r.status_code}  {r.text[:70]}")
                continue
            dims = jpeg_size(r.content)
            if not dims:
                print(f"  {label:<32} HTTP {r.status_code}, unreadable header")
                continue
            w, h = dims
            ratio = w / h
            ok = "PUBLISHABLE" if 0.8 <= ratio <= 1.91 else "still rejected"
            print(f"  {label:<32} {w}x{h} ratio {ratio:.3f}  {ok}")


if __name__ == "__main__":
    asyncio.run(main())

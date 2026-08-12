"""Make an image publishable by Instagram without re-encoding it.

Instagram's feed accepts an aspect ratio between 0.8 (4:5 portrait) and 1.91
(landscape). Outside that window the Content Publishing API still ACCEPTS the
container and reports FINISHED -- the upload looks like it worked -- and then
refuses at media_publish. What reached the caller was "Instagram accepted no
media from this post", a message about the file, when the file was a reachable
correctly-formed JPEG.

Sampled from the live catalogs on 12 Aug 2026:

    HollyVerse   56% of images outside the window, mostly 1440x1920 (0.750)
    BollyVerse   44% outside
    MyCart4U     27% outside, including 768x1376 (0.558) story crops

WHY THIS MEASURES INSTEAD OF ASKING CLOUDINARY

The first version used Cloudinary's conditional transformations --
`if_ar_lt_0.8/c_fill,ar_4:5,g_auto/if_end` -- so no dimensions had to be known
here. It failed in two ways that only appeared against real assets:

  A 1186x1483 image (0.7997, genuinely rejected) came back untouched. The
  condition did not fire, and Cloudinary gives no way to see why.

  `ar_4:5` on a 1440x1788 image produced 1430x1788 -- 0.7998. Asking for a
  RATIO lets Cloudinary pick integer pixel dimensions, and it can land just
  under the boundary. That turned an in-range image into a rejected one.

Both are the same underlying problem: the decision and the arithmetic happen
somewhere unobservable. So the ratio is measured here, the comparison happens
in Python, and the transformation names EXPLICIT PIXELS -- 1080x1350, which is
exactly 0.8 by construction and cannot round anywhere else.

The measurement costs one ranged request for the first 64KB of the file, which
is enough for the JPEG or PNG header. Cloudinary still does the cropping, so
this instance never decodes an image -- which matters on 512MB with an ffmpeg
pipeline already peaking at 311MB.
"""

from __future__ import annotations

import io
import struct
from typing import Optional, Tuple

import httpx
from loguru import logger

# Instagram's documented feed window.
MIN_RATIO = 0.8
MAX_RATIO = 1.91

# Explicit pixels, not a ratio. 1080/1350 is exactly 0.8 and 1080/566 is
# 1.9081 -- both safely inside the window with no rounding to land wrong.
PORTRAIT = "c_fill,w_1080,h_1350,g_auto"
LANDSCAPE = "c_fill,w_1080,h_566,g_auto"

_MARKER = "/image/upload/"
_HEADER_BYTES = 65536


def is_cloudinary_image(url: str) -> bool:
    return bool(url) and "res.cloudinary.com" in url and _MARKER in url


def already_normalised(url: str) -> bool:
    return "c_fill,w_1080," in (url or "")


def _jpeg_dimensions(data: bytes) -> Optional[Tuple[int, int]]:
    """Width and height from JPEG SOF markers, without decoding the image."""
    try:
        stream = io.BytesIO(data)
        if stream.read(2) != b"\xff\xd8":
            return None
        while True:
            marker = stream.read(2)
            if len(marker) < 2 or marker[0] != 0xFF:
                return None
            # SOF0-SOF15 carry the frame size; DHT/JPG/DAC do not.
            if 0xC0 <= marker[1] <= 0xCF and marker[1] not in (0xC4, 0xC8, 0xCC):
                stream.read(3)
                height, width = struct.unpack(">HH", stream.read(4))
                return width, height
            length = struct.unpack(">H", stream.read(2))[0]
            stream.seek(length - 2, 1)
    except Exception:
        return None


def _png_dimensions(data: bytes) -> Optional[Tuple[int, int]]:
    try:
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            return None
        width, height = struct.unpack(">II", data[16:24])
        return width, height
    except Exception:
        return None


def dimensions(data: bytes) -> Optional[Tuple[int, int]]:
    return _jpeg_dimensions(data) or _png_dimensions(data)


def transform_for(width: int, height: int) -> Optional[str]:
    """The transformation this shape needs, or None if it is already fine."""
    if not width or not height:
        return None
    ratio = width / height
    if ratio < MIN_RATIO:
        return PORTRAIT
    if ratio > MAX_RATIO:
        return LANDSCAPE
    return None


def apply(url: str, transform: str) -> str:
    return url.replace(_MARKER, f"{_MARKER}{transform}/")


async def publishable_url(url: str, client: Optional[httpx.AsyncClient] = None) -> str:
    """The URL to hand Instagram, cropped only if the shape requires it.

    Never raises. A post going out with the original URL is the behaviour that
    existed before this module; a post not going out because measurement failed
    would be a regression.
    """
    if not is_cloudinary_image(url) or already_normalised(url):
        return url

    own_client = client is None
    try:
        if own_client:
            client = httpx.AsyncClient(timeout=30, follow_redirects=True)
        response = await client.get(url, headers={"Range": f"bytes=0-{_HEADER_BYTES - 1}"})
        dims = dimensions(response.content)
    except Exception as e:
        logger.warning(f"Could not measure {url[:80]}: {e}. Posting it unchanged.")
        return url
    finally:
        if own_client and client is not None:
            await client.aclose()

    if not dims:
        logger.warning(f"No readable image header for {url[:80]}. Posting it unchanged.")
        return url

    transform = transform_for(*dims)
    if not transform:
        return url

    logger.info(
        f"Image geometry: {dims[0]}x{dims[1]} (ratio {dims[0] / dims[1]:.4f}) is "
        f"outside Instagram's {MIN_RATIO}-{MAX_RATIO} window; cropping at fetch time"
    )
    return apply(url, transform)


def _is_video(url: str) -> bool:
    return (url or "").split("?")[0].lower().endswith((".mp4", ".mov", ".webm", ".m4v"))


async def publishable_urls(urls: Optional[list]) -> list:
    """Normalise a whole post's media.

    Videos are left alone: Reels accept far taller shapes than feed images, and
    cropping a vertical video to 4:5 would break the format that works.
    """
    if not urls:
        return []

    out = []
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for url in urls:
            if not url or _is_video(url):
                out.append(url)
                continue
            out.append(await publishable_url(url, client=client))
    return out

"""Make an image publishable by Instagram without re-encoding it.

Instagram's feed accepts an aspect ratio between 0.8 (4:5 portrait) and 1.91
(landscape). Outside that window the Content Publishing API still ACCEPTS the
container -- the upload looks like it worked -- and then refuses at the publish
step. What reaches the caller is "Instagram accepted no media from this post",
which reads like a broken URL and sends the investigation to the wrong place.

Measured on the live catalogs, 12 Aug 2026:

    HollyVerse   56% of images unpublishable, nearly all 1440x1920 (0.750)
    BollyVerse   44% unpublishable
    MyCart4U     27% unpublishable, including 768x1376 (0.558) story crops

More than half of a 4,400-asset catalog could never post, and every attempt
consumed a scheduler slot and recorded a failure.

The fix is a Cloudinary URL transformation, not a re-encode. These assets are
already on Cloudinary, which crops on the fly and caches the result: it costs
this server nothing, which matters on a 512MB instance that already has an
ffmpeg pipeline peaking at 311MB.

The transformation is CONDITIONAL. `if_ar_lt_0.8/.../if_end` applies only to
images that are actually out of range, so a square or landscape asset passes
through byte-identical and no already-working post changes.

Crop rather than pad, for a measured reason: Cloudinary's `c_pad,ar_4:5`
returned 1535x1919 on a test asset -- 0.79989, still below the limit and still
rejected. Padding to an exact ratio is subject to rounding in a way cropping is
not. `g_auto` keeps the subject in frame, and for the dominant 0.750 case the
crop removes about 6% of the height.
"""

from __future__ import annotations

from typing import Optional

from loguru import logger

# Instagram's documented feed window.
MIN_RATIO = 0.8
MAX_RATIO = 1.91

# Applied only when the source is outside the window. Verified against live
# assets: a 1440x1920 image comes back 1440x1800 (exactly 0.8), and an
# in-range image is returned untouched.
_TOO_TALL = "if_ar_lt_0.8/c_fill,ar_4:5,g_auto/if_end"
_TOO_WIDE = "if_ar_gt_1.91/c_fill,ar_1.91,g_auto/if_end"

_MARKER = "/image/upload/"


def is_cloudinary_image(url: str) -> bool:
    return bool(url) and "res.cloudinary.com" in url and _MARKER in url


def already_normalised(url: str) -> bool:
    """Whether this URL has been through here already.

    Applying the transformation twice is harmless but produces an ugly URL and
    a second cache entry, and it makes logs hard to read.
    """
    return "if_ar_lt_0.8" in (url or "")


def publishable_url(url: str) -> str:
    """The URL to hand Instagram. Non-Cloudinary URLs pass through unchanged.

    Never raises. A post going out with the original URL is the behaviour that
    exists today; a post not going out at all because this raised would be a
    regression.
    """
    try:
        if not is_cloudinary_image(url) or already_normalised(url):
            return url
        return url.replace(_MARKER, f"{_MARKER}{_TOO_TALL}/{_TOO_WIDE}/")
    except Exception as e:
        logger.warning(f"Could not normalise image geometry for {url}: {e}")
        return url


def _is_video(url: str) -> bool:
    return (url or "").split("?")[0].lower().endswith((".mp4", ".mov", ".webm", ".m4v"))


def publishable_urls(urls: Optional[list]) -> list:
    """Normalise a whole post's media.

    Videos are left alone: Reels accept a far wider range of shapes than feed
    images, and cropping a vertical video to 4:5 would ruin the format that is
    working.
    """
    if not urls:
        return []
    out = []
    changed = 0
    for u in urls:
        if not u or _is_video(u):
            out.append(u)
            continue
        fixed = publishable_url(u)
        if fixed != u:
            changed += 1
        out.append(fixed)
    if changed:
        logger.info(
            f"Image geometry: {changed} of {len(urls)} asset(s) will be cropped "
            f"to Instagram's aspect ratio window at fetch time"
        )
    return out

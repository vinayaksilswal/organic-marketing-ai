"""Turn a folder of images into a Reel, because Reels are what publishes.

Instagram has restricted image publishing on HollyVerse, BollyVerse and
MyCart4U. Verified on 13 Aug 2026 by controlled experiment: an image generated
seconds earlier, which cannot match anything Instagram has seen, is refused on
HollyVerse and accepted on quantcai. It is the account, not the format and not
the content, and no code change lifts it -- only Meta's appeal does.

Video is untouched on every account. So roughly 5,300 parked images become
postable by becoming video: a folder's slides, in the order the user arranged
them, as a short slideshow Reel.

MEMORY. This runs on a 512MB instance whose encoder already peaks at 311MB,
and an earlier filter-graph approach to video here reached 1010MB and was
OOM-killed. So slides are encoded ONE AT A TIME and joined with the concat
demuxer and -c copy, which streams and never holds the sequence in memory. A
twenty-slide slideshow costs the same as a one-slide slideshow.

SILENT BY DESIGN. The output carries no audio track, which makes it eligible
for the music bed the posting path already adds to silent clips. Muxing here
would cost a re-encode and would bypass the operator's track choices.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

from loguru import logger

from services.video_outro import (
    ENCODE_SAFETY_MB,
    QUALITY_CRF,
    TARGET_H,
    TARGET_W,
    _ffmpeg,
    build_watermark_png,
    choose_encode_size,
    memory_headroom_mb,
    release_memory,
)

# Long enough to read an image, short enough that a ten-slide Reel stays under
# half a minute. Instagram's own data is unambiguous that completion rate falls
# off a cliff on long Reels, and a slideshow has no narrative to hold anyone.
SECONDS_PER_SLIDE = float(os.getenv("SLIDESHOW_SECONDS_PER_SLIDE", "2.4"))

# Reels accept up to 90s; this is a slideshow, not a film.
MAX_SLIDES = int(os.getenv("SLIDESHOW_MAX_SLIDES", "12"))

FPS = 30

# A slow push in. Enough that the frame is not dead, small enough that nobody
# notices it as an effect.
ZOOM_PER_FRAME = 0.0006
ZOOM_LIMIT = 1.12

# Encoding one still frame repeatedly is far cheaper than encoding real video,
# so the peak here is well under the 308MB a 1080x1920 clip encode needs. The
# margin is kept anyway because this shares an instance with that encoder.
SLIDESHOW_PEAK_MB = 120


def _headroom_allows(size: Tuple[int, int]) -> bool:
    headroom = memory_headroom_mb()
    if headroom is None:
        return True
    return headroom >= SLIDESHOW_PEAK_MB + ENCODE_SAFETY_MB


def _slide_filter(width: int, height: int, zoom_in: bool, watermark: bool) -> str:
    """Scale, crop to frame, drift slowly, and stamp the mark.

    Scaling happens BEFORE zoompan. zoompan on a 1440x1920 source allocates
    against the source dimensions, and the catalogs here are full of them.
    """
    frames = max(int(SECONDS_PER_SLIDE * FPS), 1)

    # Oversample slightly so the zoom has pixels to eat into rather than
    # softening the image as it pushes in.
    over_w, over_h = int(width * 1.2), int(height * 1.2)

    if zoom_in:
        zoom = f"min(zoom+{ZOOM_PER_FRAME},{ZOOM_LIMIT})"
    else:
        # Starting zoomed and easing out reads as a different shot, which
        # stops a ten-slide sequence feeling mechanical.
        zoom = f"max({ZOOM_LIMIT}-on*{ZOOM_PER_FRAME},1.0)"

    chain = (
        f"scale={over_w}:{over_h}:force_original_aspect_ratio=increase,"
        f"crop={over_w}:{over_h},"
        f"zoompan=z='{zoom}':d={frames}"
        f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":s={width}x{height}:fps={FPS},"
        f"setsar=1"
    )
    if watermark:
        chain = f"[0:v]{chain}[bg];[bg][1:v]overlay=W-w-40:H-h-56"
    return chain


def _encode_slide(
    ff: str,
    image: Path,
    dest: Path,
    size: Tuple[int, int],
    zoom_in: bool,
    mark: Optional[Path],
) -> bool:
    width, height = size
    cmd = [ff, "-y", "-hide_banner", "-loglevel", "error",
           "-loop", "1", "-t", f"{SECONDS_PER_SLIDE:.2f}", "-i", str(image)]
    if mark:
        cmd += ["-i", str(mark)]

    chain = _slide_filter(width, height, zoom_in, watermark=bool(mark))
    cmd += ["-filter_complex" if mark else "-vf", chain]

    cmd += [
        "-r", str(FPS),
        # NOT the video pipeline's CRF 18. A slow pan across a still frame
        # gives x264 almost nothing to predict away, so CRF 18 produced 91MB
        # for seven seconds -- a twelve-slide Reel would have been ~350MB to
        # upload and for Instagram to transcode. CRF 26 with a hard ceiling is
        # visually identical on a still and roughly a tenth the size.
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
        "-maxrate", "4M", "-bufsize", "8M",
        "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1",
        # One thread, as everywhere else here: parallel encoding multiplies
        # the peak by the thread count on an instance that cannot afford it.
        "-threads", "1",
        "-an",
        str(dest),
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, errors="ignore", timeout=180,
            preexec_fn=(lambda: os.nice(19)) if hasattr(os, "nice") else None,
        )
    except subprocess.TimeoutExpired:
        logger.warning(f"Slideshow: slide {image.name} timed out")
        return False
    except Exception as e:
        logger.warning(f"Slideshow: slide {image.name} failed to start: {e}")
        return False

    if result.returncode != 0 or not dest.exists() or dest.stat().st_size == 0:
        logger.warning(
            f"Slideshow: ffmpeg rejected slide {image.name}: "
            f"{(result.stderr or '')[:200]}"
        )
        return False
    return True


def _concat(ff: str, clips: List[Path], dest: Path) -> bool:
    """Join finished clips without re-encoding.

    Every clip came out of the same command with the same parameters, so the
    streams are compatible and -c copy is safe. This is what keeps a
    twenty-slide slideshow as cheap as a one-slide one.
    """
    listing = dest.parent / "slides.txt"
    listing.write_text(
        "\n".join(f"file '{c.as_posix()}'" for c in clips), encoding="utf-8"
    )
    cmd = [
        ff, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(listing),
        "-c", "copy", "-movflags", "+faststart", str(dest),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                errors="ignore", timeout=300)
    except subprocess.TimeoutExpired:
        logger.error("Slideshow: concat timed out")
        return False
    if result.returncode != 0 or not dest.exists() or dest.stat().st_size == 0:
        logger.error(f"Slideshow: concat failed: {(result.stderr or '')[:300]}")
        return False
    return True


async def build_slideshow(
    image_urls: List[str],
    workspace_id: str,
    media_id: str,
    *,
    profile=None,
) -> Optional[str]:
    """Render images into a Reel and upload it. Returns the URL, or None.

    Never raises. A workspace that cannot render a slideshow should fall back
    to whatever it was posting before, not stop posting.
    """
    import httpx

    from services.storage_service import upload_media_to_cloudinary

    urls = [u for u in (image_urls or []) if u][:MAX_SLIDES]
    if len(urls) < 2:
        logger.info("Slideshow: needs at least two images")
        return None

    ff = _ffmpeg()
    if not ff:
        logger.warning("Slideshow: ffmpeg is not available")
        return None

    size = choose_encode_size(memory_headroom_mb()) or (TARGET_W, TARGET_H)
    if not _headroom_allows(size):
        logger.warning(
            f"Slideshow: only {memory_headroom_mb()}MB free, need "
            f"{SLIDESHOW_PEAK_MB + ENCODE_SAFETY_MB}MB. Skipping this cycle."
        )
        return None

    work = Path(tempfile.mkdtemp(prefix="slideshow_"))
    try:
        mark = None
        brand = (getattr(profile, "name", "") or "").strip() if profile else ""
        if brand:
            try:
                # Same wordmark the video pipeline stamps, so a slideshow Reel
                # is not visibly a different kind of post from a real clip.
                mark = build_watermark_png(brand, size[0], size[1])
            except Exception as e:
                logger.debug(f"Slideshow: no watermark ({e})")

        clips: List[Path] = []
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            for index, url in enumerate(urls):
                source = work / f"src{index:02d}.jpg"
                try:
                    async with client.stream("GET", url) as response:
                        response.raise_for_status()
                        with source.open("wb") as fh:
                            async for chunk in response.aiter_bytes(1024 * 256):
                                fh.write(chunk)
                except Exception as e:
                    logger.warning(f"Slideshow: could not fetch slide {index}: {e}")
                    continue

                clip = work / f"clip{index:02d}.mp4"
                if _encode_slide(ff, source, clip, size, index % 2 == 0, mark):
                    clips.append(clip)

                # The source is no longer needed and the next fetch is about to
                # allocate again.
                source.unlink(missing_ok=True)
                release_memory()

        if len(clips) < 2:
            logger.warning(
                f"Slideshow: only {len(clips)} slide(s) encoded, not enough for a Reel"
            )
            return None

        output = work / "slideshow.mp4"
        if not _concat(ff, clips, output):
            return None

        for clip in clips:
            clip.unlink(missing_ok=True)
        release_memory()

        seconds = len(clips) * SECONDS_PER_SLIDE
        logger.info(
            f"Slideshow: {len(clips)} slides -> {seconds:.1f}s "
            f"{size[0]}x{size[1]} ({output.stat().st_size / 1e6:.1f}MB)"
        )

        uploaded = await upload_media_to_cloudinary(
            workspace_id, media_id, f"slideshow-{media_id}.mp4",
            output.read_bytes(), resource_type="video",
        )
        return uploaded.get("secure_url") if uploaded else None

    except Exception as e:
        logger.error(f"Slideshow: failed for workspace {workspace_id}: {e}")
        return None
    finally:
        shutil.rmtree(work, ignore_errors=True)
        release_memory()

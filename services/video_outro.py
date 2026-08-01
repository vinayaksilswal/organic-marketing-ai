"""Composite a branded outro onto a generated clip before it is posted.

Why this exists rather than asking the video model for it:

A diffusion model draws text as pixels it has learned to associate with a
prompt. One short word survives that — a rendered test confirmed a
bottom-centre wordmark comes back clean — but a sentence does not. "Visit
quantcai.info and start your free scan" comes back as smeared pseudo-glyphs
every time, which is why the call to action is spoken rather than written.

ffmpeg draws text as text. The font is the font, the spelling is the spelling,
and it is identical on every clip. So the last two seconds are composited here
instead: brand name, the offer, and a URL that is actually legible.

Everything degrades to the original video. A missing binary, an unreadable
file, a codec the build cannot handle — all of it returns the input path and
logs, because a clip that posts without an outro is worth far more than a
scheduled post that never goes out.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple

from loguru import logger

# Two seconds is the ceiling. Instagram counts a view at three, and watch-time
# ratio is a ranking input, so a long card taxes the whole clip's performance.
DEFAULT_OUTRO_SECONDS = 1.8

# Fonts present on typical Linux containers, then macOS, then Windows. Falls
# back to Pillow's own font, which is ugly but never absent.
_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def _ffmpeg() -> Optional[str]:
    """The ffmpeg binary, preferring the pinned wheel over whatever is on PATH.

    imageio-ffmpeg ships a static build, so behaviour matches between a laptop
    and the container. A system ffmpeg is accepted as a fallback but its
    feature set is not guaranteed.
    """
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg")


def _probe(video: Path) -> Optional[Tuple[int, int, float, bool, float]]:
    """Return (width, height, fps, has_audio, duration) for the source clip.

    The outro has to match the source exactly — concat rejects streams that
    disagree on dimensions or pixel format, and a mismatched fps silently
    resamples the whole video.
    """
    ff = _ffmpeg()
    if not ff:
        return None
    try:
        out = subprocess.run(
            [ff, "-hide_banner", "-i", str(video)],
            capture_output=True, text=True, errors="ignore", timeout=60,
        ).stderr
    except Exception as e:
        logger.warning(f"Outro: could not probe {video.name}: {e}")
        return None

    import re

    dim = re.search(r"(\d{2,5})x(\d{2,5})", out)
    fps = re.search(r"(\d+(?:\.\d+)?)\s*fps", out)
    dur = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", out)
    if not dim:
        return None
    seconds = 0.0
    if dur:
        seconds = int(dur.group(1)) * 3600 + int(dur.group(2)) * 60 + float(dur.group(3))
    return (
        int(dim.group(1)),
        int(dim.group(2)),
        float(fps.group(1)) if fps else 24.0,
        "Audio:" in out,
        seconds,
    )


def _load_font(size: int):
    from PIL import ImageFont

    for path in _FONT_CANDIDATES:
        try:
            if Path(path).exists():
                return ImageFont.truetype(path, size)
        except Exception:
            continue
    try:
        # Pillow >= 10 accepts a size on the built-in font.
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def build_outro_card(
    brand: str,
    cta: str = "",
    url: str = "",
    width: int = 1080,
    height: int = 1920,
    background: str = "#0B0D10",
    accent: str = "#FFFFFF",
) -> Optional[Path]:
    """Draw the end card as a PNG. Returns None if Pillow is unavailable."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        logger.warning("Outro: Pillow is not installed, skipping the end card")
        return None

    img = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(img)

    # Scaled off the frame width so the card looks identical at 720p and 1080p.
    brand_size = max(48, int(width * 0.11))
    cta_size = max(26, int(width * 0.045))
    url_size = max(22, int(width * 0.033))

    brand_font = _load_font(brand_size)
    cta_font = _load_font(cta_size)
    url_font = _load_font(url_size)

    def _centre(text: str, font, y: int, fill: str):
        if not text:
            return y
        box = draw.textbbox((0, 0), text, font=font)
        draw.text(((width - (box[2] - box[0])) / 2, y), text, font=font, fill=fill)
        return y + (box[3] - box[1])

    # Optically centred: text sits slightly above the middle so it does not
    # collide with the platform UI along the bottom of a Reel.
    block_top = int(height * 0.40)
    y = _centre(brand, brand_font, block_top, accent)

    if cta:
        y = _centre(cta, cta_font, y + int(height * 0.035), accent)
    if url:
        _centre(url, url_font, y + int(height * 0.028), "#8A93A0")

    # A thin accent rule reads as deliberate design rather than a title card.
    rule_w = int(width * 0.16)
    rule_y = block_top - int(height * 0.030)
    draw.rectangle(
        [(width - rule_w) // 2, rule_y, (width + rule_w) // 2, rule_y + max(3, width // 300)],
        fill=accent,
    )

    path = Path(tempfile.mkdtemp(prefix="outro_")) / "card.png"
    img.save(path)
    return path


# Instagram and Facebook cap vertical video at 1080x1920 and downscale
# anything larger on ingest. Delivering 2K therefore costs storage and encode
# time and then gets thrown away — worse, it hands the platform's own
# downscaler a job we would rather do ourselves with lanczos. 1440p is here for
# platforms that keep it (YouTube Shorts), not as a default.
#
# Set VIDEO_TARGET_HEIGHT=2560 in the environment to deliver 1440x2560.
_TARGET_H = int(os.getenv("VIDEO_TARGET_HEIGHT", "1920"))
TARGET_H = 2560 if _TARGET_H >= 2560 else 1920
TARGET_W = 1440 if TARGET_H == 2560 else 1080

# Re-encoding cannot add detail that is not in the source; the point is to stop
# throwing more of it away and to hand the platform its preferred shape.
#
# crf 18 rather than 21, and a 12M ceiling rather than 7M. Measured on a real
# 720p source: 5.1MB -> 7.8MB and 7.2s -> 11.0s. That is the quality Instagram
# actually retains, unlike extra resolution, which it discards.
#
# The cap still matters. Upscaling then sharpening manufactures high-frequency
# detail that CRF faithfully spends bits on: uncapped at crf 19 the same 1.8MB
# source came back as 44.8MB.
QUALITY_CRF = int(os.getenv("VIDEO_CRF", "18"))
MAX_BITRATE = os.getenv("VIDEO_MAX_BITRATE", "12M")
BUFSIZE = f"{int(MAX_BITRATE.rstrip('M')) * 2}M"


def build_watermark_png(
    brand: str, width: int = TARGET_W, height: int = TARGET_H
) -> Optional[Path]:
    """A transparent PNG holding the wordmark, bottom-centre.

    The video prompt also asks the model for this, but a diffusion model may or
    may not honour it and cannot spell reliably. Compositing it here means every
    clip carries the same mark, correctly, including uploads that were never
    generated by us.

    Drawn with Pillow rather than ffmpeg's drawtext so there is no dependency on
    a font path existing inside the container.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    size = max(28, int(width * 0.052))
    font = _load_font(size)
    box = draw.textbbox((0, 0), brand, font=font)
    text_w, text_h = box[2] - box[0], box[3] - box[1]

    # Sits above the very bottom edge: Instagram's own UI overlays the lowest
    # ~12% of a Reel with the caption and action buttons.
    x = (width - text_w) / 2
    y = height - int(height * 0.135) - text_h

    # A soft shadow keeps it legible over both bright and dark footage without
    # needing a plate behind it.
    draw.text((x + 2, y + 2), brand, font=font, fill=(0, 0, 0, 90))
    draw.text((x, y), brand, font=font, fill=(255, 255, 255, 210))

    path = Path(tempfile.mkdtemp(prefix="wm_")) / "watermark.png"
    img.save(path)
    return path


def append_outro(
    video_path: str | Path,
    brand: str,
    cta: str = "",
    url: str = "",
    seconds: float = DEFAULT_OUTRO_SECONDS,
    output_path: Optional[str | Path] = None,
) -> str:
    """Append a branded end card. Returns the new path, or the original.

    Never raises. Posting a clip without its outro is a cosmetic loss; failing
    to post at all is a missed slot in the schedule that never comes back.
    """
    src = Path(video_path)
    if not src.exists():
        logger.warning(f"Outro: {src} does not exist")
        return str(video_path)

    ff = _ffmpeg()
    if not ff:
        logger.warning("Outro: no ffmpeg binary available, posting the clip as-is")
        return str(video_path)

    probed = _probe(src)
    if not probed:
        logger.warning("Outro: could not read the source clip, posting as-is")
        return str(video_path)
    width, height, fps, has_audio, duration = probed

    card = build_outro_card(brand, cta, url, width=width, height=height)
    if not card:
        return str(video_path)

    dest = Path(output_path) if output_path else src.with_name(f"{src.stem}_outro.mp4")

    # Everything happens in ONE encode. Watermarking and then appending the
    # card as two passes means encoding the footage twice, and every H.264
    # generation throws away detail that cannot come back.
    #
    # Delivered at Instagram's own vertical spec. Re-encoding cannot add detail
    # the source never had, but handing the platform a correctly sized file
    # stops its encoder upscaling a 720p clip with a cheap scaler first.
    tw, th = TARGET_W, TARGET_H
    watermark = build_watermark_png(brand, tw, th)

    # lanczos preserves edge detail when scaling up; a light unsharp pass
    # recovers the softness scaling introduces. Both are conservative — heavy
    # sharpening reads as artefacting once the platform compresses it again.
    polish = (
        f"scale={tw}:{th}:force_original_aspect_ratio=decrease:flags=lanczos,"
        f"pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2:color=black,"
        # Gentle. On upscaled footage a heavy unsharp mostly manufactures
        # detail that is not real, and every bit of it costs bitrate.
        f"unsharp=5:5:0.35:5:5:0.0,"
        f"fps={fps},format=yuv420p,setsar=1"
    )

    chain = f"[0:v]{polish}[polished];"
    if watermark:
        chain += (
            "[polished][2:v]overlay=0:0:format=auto[main];"
            f"[1:v]scale={tw}:{th}:flags=lanczos,fps={fps},format=yuv420p,setsar=1[card];"
        )
    else:
        chain += (
            "[polished]null[main];"
            f"[1:v]scale={tw}:{th}:flags=lanczos,fps={fps},format=yuv420p,setsar=1[card];"
        )
    chain += "[main][card]concat=n=2:v=1:a=0[v]"

    cmd = [
        ff, "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src),
        "-loop", "1", "-t", str(seconds), "-i", str(card),
    ]
    if watermark:
        # Bounded to the clip. An earlier "-t 9999" made ffmpeg generate a
        # 9999-second overlay stream, so a nine-second video took minutes and
        # would have blown the request timeout all over again.
        cmd += ["-loop", "1", "-t", f"{max(duration, 1.0):.3f}", "-i", str(watermark)]

    if has_audio:
        # The card needs its own silence, or concat drops the audio stream and
        # the clip posts mute.
        chain += (
            f";anullsrc=channel_layout=stereo:sample_rate=44100,"
            f"atrim=duration={seconds}[silence];"
            f"[0:a][silence]concat=n=2:v=0:a=1[a]"
        )
        cmd += ["-filter_complex", chain, "-map", "[v]", "-map", "[a]"]
    else:
        cmd += ["-filter_complex", chain, "-map", "[v]"]

    cmd += [
        # "faster" rather than "veryfast": this no longer runs inside a
        # request, so a few extra seconds per clip buys real compression
        # efficiency. Not "slow" — encodes are serialised to keep the single
        # worker responsive, so per-clip time is the whole backlog's time.
        # -threads 1 is the important one. libx264 defaults to every visible
        # core, and this runs on a starter instance with a fraction of one —
        # so a background encode starved the web server badly enough that
        # /health itself stopped answering. Moving it to a thread fixed the
        # event loop; it did not stop ffmpeg eating the CPU the loop needs.
        #
        # One thread makes each encode slower and leaves the service able to
        # answer requests while a backlog is processed, which is the correct
        # trade for work that is already asynchronous.
        "-threads", "1",
        "-c:v", "libx264", "-preset", "faster", "-crf", str(QUALITY_CRF),
        # High profile at level 4.1 is what every phone decodes and what
        # Instagram expects; anything more exotic gets re-encoded harder.
        "-profile:v", "high", "-level", "4.1",
        "-maxrate", MAX_BITRATE, "-bufsize", BUFSIZE,
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        # Two seconds between keyframes: the platform seeks on them, and a
        # sparse GOP makes the first frames of a scroll-in look mushy.
        "-g", str(int(fps * 2)), "-sc_threshold", "0",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
        str(dest),
    ]

    def _low_priority():
        """Let the OS schedule the web server ahead of a background encode."""
        try:
            os.nice(19)
        except Exception:
            pass

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, errors="ignore", timeout=600,
            # POSIX only; ignored on Windows, where this never runs in prod.
            preexec_fn=_low_priority if os.name == "posix" else None,
        )
    except subprocess.TimeoutExpired:
        logger.error("Outro: ffmpeg timed out, posting the clip as-is")
        return str(video_path)
    finally:
        shutil.rmtree(card.parent, ignore_errors=True)
        if watermark:
            shutil.rmtree(watermark.parent, ignore_errors=True)

    if result.returncode != 0 or not dest.exists() or dest.stat().st_size == 0:
        logger.error(f"Outro: ffmpeg failed ({result.returncode}): {result.stderr[:400]}")
        return str(video_path)

    logger.info(
        f"Branded {src.name}: watermark + {seconds}s card, {tw}x{th} "
        f"crf{QUALITY_CRF} capped {MAX_BITRATE} -> {dest.stat().st_size / 1e6:.1f}MB"
    )
    return str(dest)


def outro_text_for(profile) -> Tuple[str, str, str]:
    """Work out what the card should say from a BusinessProfile.

    The spoken CTA drives the video; this is its written counterpart, and here
    a URL is safe because ffmpeg renders it legibly.
    """
    import re as _re

    brand = (getattr(profile, "name", "") or "").strip()
    cta = (getattr(profile, "primaryOffer", "") or "").strip().rstrip(".")

    url = (getattr(profile, "websiteUrl", "") or "").strip()
    for prefix in ("https://", "http://", "www."):
        if url.lower().startswith(prefix):
            url = url[len(prefix):]
    url = url.rstrip("/")

    # A themed page has nothing to sell, so the offer field is either empty or
    # describes a transaction that does not exist. The whole economy of the
    # account is the follow, and the handle is what a viewer can act on — there
    # is usually no website to put on the card at all.
    model = (getattr(profile, "businessModel", "") or "").strip().lower()
    if model in {"social page", "social_page", "page"}:
        handle = _re.sub(r"[^a-z0-9]", "", brand.lower())
        if not cta or not _re.match(r"^(follow|subscribe)\b", cta, _re.IGNORECASE):
            cta = "Follow for more"
        if not url and handle:
            url = f"@{handle}"

    # A long offer wraps badly on a 1080-wide card and reads as a paragraph.
    if len(cta.split()) > 6:
        cta = " ".join(cta.split()[:6])
    return brand, cta, url


async def brand_video_at_url(
    video_url: str,
    profile,
    workspace_id: str,
    media_id: str,
    seconds: float = DEFAULT_OUTRO_SECONDS,
) -> str:
    """Download a rendered clip, append its outro, and re-upload it.

    Returns the branded URL, or the original one on any failure. Called on the
    finished render rather than at request time, because json2video renders
    asynchronously — at the point the render is requested there is no file to
    composite onto yet.
    """
    import httpx

    from services.storage_service import upload_media_to_cloudinary

    brand, cta, url = outro_text_for(profile)
    if not brand:
        logger.warning("Outro: workspace has no business name, skipping")
        return video_url

    work = Path(tempfile.mkdtemp(prefix="brandvid_"))
    try:
        source = work / "source.mp4"
        try:
            # Streamed to disk rather than held in memory. This instance has
            # 512MB and Render killed it twice for exceeding that: several
            # concurrent tasks each holding a whole video, plus ffmpeg's own
            # working set, is more than the budget allows. The file has to be
            # on disk for ffmpeg anyway, so buffering it first bought nothing.
            async with httpx.AsyncClient(timeout=180.0, follow_redirects=True) as client:
                async with client.stream("GET", video_url) as resp:
                    resp.raise_for_status()
                    with source.open("wb") as fh:
                        async for chunk in resp.aiter_bytes(1024 * 256):
                            fh.write(chunk)
        except Exception as e:
            logger.error(f"Outro: could not download {video_url}: {e}")
            return video_url

        # append_outro shells out to ffmpeg with a blocking subprocess call.
        # Awaiting it directly on the event loop froze the entire server for
        # the duration — this runs on a single uvicorn worker, so branding a
        # backlog of clips made the API unreachable and uploads failed while
        # it churned. Off to a thread.
        branded = Path(
            await asyncio.to_thread(
                append_outro, source, brand, cta, url, seconds
            )
        )
        if branded == source:
            # append_outro already logged why; the clip is still postable.
            return video_url

        uploaded = await upload_media_to_cloudinary(
            workspace_id=workspace_id,
            media_id=f"{media_id}_branded",
            filename=f"{brand}_branded.mp4",
            source=branded.read_bytes(),
            resource_type="video",
            tags=[brand, "outro", "ai-generated"],
        )
        if not uploaded or not uploaded.get("secure_url"):
            logger.error("Outro: upload of the branded clip failed, keeping the original")
            return video_url

        logger.info(f"Outro: branded clip published for {brand}")
        return uploaded["secure_url"]
    finally:
        shutil.rmtree(work, ignore_errors=True)

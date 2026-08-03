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
import functools
import hashlib
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


# What an encode actually costs, measured on a real clip rather than guessed:
#
#     1080x1920   308 MB peak
#      720x1280   189 MB peak
#
# Starting one without the room does not produce a slow encode, it produces an
# OOM kill that takes the web server with it and fails every upload in flight.
# Render restarted this service twice that way.
#
# But refusing outright was worse than it looked. A single threshold of 340MB
# blocked branding on an instance holding 199MB of 537MB -- 338MB free, short
# by two megabytes, while 199 + 308 = 507 would have fitted with 30MB to
# spare. Nothing branded, and the dashboard gave no reason.
#
# So the size is chosen to fit the room available: full resolution when it
# fits, 720p when it does not, and only skipped when even that has nowhere to
# go. A clip delivered at 720p is worth incomparably more than one delivered
# never -- and the platform re-encodes everything anyway.
ENCODE_PEAK_MB = {(1080, 1920): 308, (720, 1280): 189}

# Enough that a normal fluctuation in the web server's own usage during an
# encode does not push the container over.
ENCODE_SAFETY_MB = int(os.getenv("VIDEO_ENCODE_SAFETY_MB", "25"))

# Kept for callers and tests that refer to it: the room a full-size encode
# needs, including the margin.
ENCODE_HEADROOM_MB = int(
    os.getenv("VIDEO_ENCODE_HEADROOM_MB",
              str(ENCODE_PEAK_MB[(1080, 1920)] + ENCODE_SAFETY_MB))
)


def choose_encode_size(headroom_mb: Optional[float]) -> Optional[Tuple[int, int]]:
    """The largest delivery size this instance has room for right now.

    None means not even 720p fits and the clip should be left alone. An
    unknown headroom (not containerised) means no limit to respect.
    """
    if headroom_mb is None:
        return (TARGET_W, TARGET_H)
    for size in sorted(ENCODE_PEAK_MB, key=lambda wh: -wh[0] * wh[1]):
        if size[0] > TARGET_W or size[1] > TARGET_H:
            continue
        if headroom_mb >= ENCODE_PEAK_MB[size] + ENCODE_SAFETY_MB:
            return size
    return None


_CGROUP_FILES = (
    # cgroup v2, then v1. The third entry is the stat file and the fourth is
    # the key in it holding anonymous memory.
    ("/sys/fs/cgroup/memory.current", "/sys/fs/cgroup/memory.max",
     "/sys/fs/cgroup/memory.stat", ("anon", "slab", "sock")),
    ("/sys/fs/cgroup/memory/memory.usage_in_bytes",
     "/sys/fs/cgroup/memory/memory.limit_in_bytes",
     "/sys/fs/cgroup/memory/memory.stat", ("total_rss",)),
)


def read_memory_stat(stat_file: str) -> dict:
    """Parse a cgroup memory.stat into {key: bytes}."""
    out = {}
    try:
        for line in Path(stat_file).read_text().splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1].isdigit():
                out[parts[0]] = int(parts[1])
    except Exception:
        pass
    return out


def container_memory(pairs=_CGROUP_FILES) -> Optional[Tuple[float, float]]:
    """(irreclaimable_mb, limit_mb) for this container, or None off a cgroup.

    "Used" here counts anonymous memory, slab and socket buffers -- the memory
    the kernel cannot take back. It deliberately excludes the page cache.

    That distinction has cost this service two nights. Every video downloaded,
    encoded and written to disk enters the page cache, and memory.current
    counts all of it. The reading therefore parks a few megabytes below the
    limit and stays there, while the process is in no danger whatsoever: the
    kernel drops cache on demand. A first attempt subtracted only
    inactive_file, which is the portion that has aged out -- freshly written
    video sits in active_file, so the reading still said "6MB free" and the
    headroom guard refused every encode after the first.

    The proof it is cache and not usage: this container has sat at 536 of
    537MB for many minutes at a stretch, repeatedly, and has never once been
    killed for it. Anonymous memory at that level plus a 311MB encode would
    not survive a second.

    Falls back to (current - file) and then to current, so a kernel that does
    not expose these keys degrades to the old conservative behaviour rather
    than reporting nonsense.
    """
    for used_file, limit_file, stat_file, keys in pairs:
        try:
            current = int(Path(used_file).read_text().strip())
            raw = Path(limit_file).read_text().strip()
            if raw == "max":
                continue
            limit = int(raw)
            # An unset v1 limit is a huge sentinel rather than the word "max".
            if not (0 < limit < (1 << 62)):
                continue

            stat = read_memory_stat(stat_file)
            if keys[0] in stat:
                used = sum(stat.get(k, 0) for k in keys)
            elif "file" in stat:
                used = max(current - stat["file"], 0)
            elif "total_cache" in stat:
                used = max(current - stat["total_cache"], 0)
            else:
                used = current
            return min(used, current) / 1e6, limit / 1e6
        except Exception:
            continue
    return None


def memory_headroom_mb() -> Optional[float]:
    """How much room is left before the container is killed. None if unknown."""
    reading = container_memory()
    return None if reading is None else reading[1] - reading[0]


def release_memory() -> None:
    """Hand freed memory back to the OS.

    Python releasing an 8MB video buffer does not shrink the process: glibc
    keeps the arena for reuse, and it fragments badly when large blocks are
    allocated across the worker threads ffmpeg is driven from. Measured on
    this service, the working set sat at ~530MB of a 537MB limit between
    encodes with only 2MB of it page cache — so the headroom guard refused
    every clip after the first, and exactly one got branded.

    malloc_trim releases the tops of those arenas. Cheap, and a no-op on
    platforms without it.
    """
    import gc

    gc.collect()
    try:
        import ctypes

        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except Exception:
        # Not glibc (macOS, musl, Windows). Nothing to do.
        pass


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


# Music the operator has the rights to, stored per workspace and rotated so a
# feed does not carry one track on every clip.
#
# Deliberately NOT a bundled "trending" library. Chart music is copyrighted;
# Instagram's Content ID mutes or removes posts that use it. Instagram's own
# licensed catalogue is only attachable inside the app — the Content Publishing
# API has no field for it — so the in-app music picker cannot be automated at
# all. What can be automated is applying tracks the operator already holds,
# which includes Meta's own Sound Collection: free, and licensed precisely for
# organic Instagram and Facebook content.
AUDIO_TYPES = {".mp3", ".m4a", ".aac", ".wav", ".ogg", ".flac"}

# A bed under silence, not under a voice. Only ever applied to clips with no
# audio of their own, so there is nothing for it to compete with.
BED_VOLUME = 0.85


def stable_choice(items: list, seed_key: str = ""):
    """One item from a list, chosen deterministically from seed_key.

    Hashed rather than random so re-running a repair does not swap the track
    under a clip that already went out with a different one.
    """
    if not items:
        return None
    digest = hashlib.sha256(seed_key.encode("utf-8", "replace")).hexdigest()
    return items[int(digest, 16) % len(items)]


def append_outro(
    video_path: str | Path,
    brand: str,
    cta: str = "",
    url: str = "",
    seconds: float = DEFAULT_OUTRO_SECONDS,
    output_path: Optional[str | Path] = None,
    audio_bed: Optional[str | Path] = None,
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

    # Three passes, but the footage is encoded exactly once.
    #
    # This used to be a single ffmpeg call that scaled, watermarked and
    # concatenated the end card in one filter graph. Measured on a real clip
    # that peaked at 1010MB of RSS — on a 512MB instance, so Render killed the
    # service mid-backlog, twice. Almost all of it was the graph holding the
    # main video and the card alive at once while `concat` joined them.
    #
    # Encoding each part separately and joining with the concat demuxer at
    # `-c copy` peaks at 311MB for identical output: same 1080x1920, same
    # bitrate, same duration. Stream copy re-encodes nothing, so splitting the
    # work costs no generation loss — the earlier single-pass comment assumed
    # a second encode that never has to happen.
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

    # A bed is only laid under a clip that has no sound of its own. A clip that
    # already carries speech or ambience keeps it — dropping music over
    # someone talking ruins both.
    bed = Path(audio_bed) if (audio_bed and not has_audio) else None
    if bed and not bed.exists():
        logger.warning(f"Audio bed {bed} is missing; posting the clip silent")
        bed = None
    want_audio = has_audio or bed is not None

    dest = Path(output_path) if output_path else src.with_name(f"{src.stem}_outro.mp4")
    main_path = src.with_name(f"{src.stem}__main.mp4")
    card_path = src.with_name(f"{src.stem}__card.mp4")
    list_path = src.with_name(f"{src.stem}__join.txt")

    # Identical on both encodes, or the concat demuxer refuses to join them.
    encode = [
        # -threads 1 is the important one. libx264 defaults to every visible
        # core, and this runs on a starter instance with a fraction of one —
        # so a background encode starved the web server badly enough that
        # /health itself stopped answering.
        "-threads", "1",
        "-c:v", "libx264", "-preset", "faster", "-crf", str(QUALITY_CRF),
        # x264 holds a frame buffer per lookahead slot, and at 1080x1920 that
        # is ~3MB each. The default costs ~70MB for compression gains that are
        # invisible next to what the platform's own re-encode does.
        "-x264-params", "rc-lookahead=10:sync-lookahead=0",
        # High profile at level 4.1 is what every phone decodes and what
        # Instagram expects; anything more exotic gets re-encoded harder.
        "-profile:v", "high", "-level", "4.1",
        "-maxrate", MAX_BITRATE, "-bufsize", BUFSIZE,
        "-pix_fmt", "yuv420p",
        # Two seconds between keyframes: the platform seeks on them, and a
        # sparse GOP makes the first frames of a scroll-in look mushy.
        "-g", str(int(fps * 2)), "-sc_threshold", "0",
    ]
    audio_encode = ["-c:a", "aac", "-b:a", "192k", "-ar", "44100"]

    def _low_priority():
        """Let the OS schedule the web server ahead of a background encode."""
        try:
            os.nice(19)
        except Exception:
            pass

    def _run(cmd, label: str) -> bool:
        try:
            r = subprocess.run(
                cmd, capture_output=True, text=True, errors="ignore", timeout=600,
                # POSIX only; ignored on Windows, where this never runs in prod.
                preexec_fn=_low_priority if os.name == "posix" else None,
            )
        except subprocess.TimeoutExpired:
            logger.error(f"Outro: ffmpeg timed out during {label}")
            return False
        if r.returncode != 0:
            logger.error(f"Outro: {label} failed ({r.returncode}): {r.stderr[:400]}")
            return False
        return True

    def _cleanup():
        shutil.rmtree(card.parent, ignore_errors=True)
        if watermark:
            shutil.rmtree(watermark.parent, ignore_errors=True)
        for leftover in (main_path, card_path, list_path):
            try:
                leftover.unlink(missing_ok=True)
            except Exception:
                pass

    # Checked here rather than at the top so the log line reports the real
    # number on every clip, which is how we learn what this instance actually
    # runs at instead of inferring it from crash events.
    headroom = memory_headroom_mb()
    size = choose_encode_size(headroom)
    if size is None:
        logger.warning(
            f"Outro: only {headroom:.0f}MB free, not enough for even a 720p "
            f"encode ({ENCODE_PEAK_MB[(720, 1280)] + ENCODE_SAFETY_MB}MB). "
            f"Leaving {src.name} unbranded for the next pass rather than "
            f"risking an out-of-memory kill."
        )
        _cleanup()
        return str(video_path)

    if size != (tw, th):
        logger.warning(
            f"Outro: {headroom:.0f}MB free, delivering {src.name} at "
            f"{size[0]}x{size[1]} instead of {tw}x{th}. A smaller clip beats "
            f"no clip, and the platform re-encodes it regardless."
        )
        tw, th = size
        # The watermark and card were built for the original size.
        if watermark:
            shutil.rmtree(watermark.parent, ignore_errors=True)
        watermark = build_watermark_png(brand, tw, th)
        polish = (
            f"scale={tw}:{th}:force_original_aspect_ratio=decrease:flags=lanczos,"
            f"pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"unsharp=5:5:0.35:5:5:0.0,"
            f"fps={fps},format=yuv420p,setsar=1"
        )
    elif headroom is not None:
        logger.info(
            f"Outro: {headroom:.0f}MB free, encoding {src.name} at {tw}x{th}"
        )

    try:
        # ── pass 1: the footage. Scaled, sharpened, watermarked, encoded once.
        cmd = [ff, "-y", "-hide_banner", "-loglevel", "error", "-i", str(src)]
        chain = f"[0:v]{polish}[polished]"
        if watermark:
            # A still image input, not a looped stream. Looping it produced a
            # full-length second video of 1080x1920 RGBA frames — 324MB of the
            # original 1010MB peak. overlay repeats the last frame by itself.
            cmd += ["-i", str(watermark)]
            chain += ";[polished][1:v]overlay=0:0:format=auto:eof_action=repeat[v]"
        else:
            chain += ";[polished]null[v]"

        maps = ["-map", "[v]"]
        if bed:
            # Looped in case the track is shorter than the clip, trimmed to the
            # footage, and faded so it neither starts abruptly nor cuts off
            # mid-note. The end card stays silent: the cut to it is a hard
            # visual break, so music resolving there reads as deliberate.
            bed_index = 2 if watermark else 1
            cmd += ["-stream_loop", "-1", "-i", str(bed)]
            chain += (
                f";[{bed_index}:a]atrim=duration={duration:.3f},"
                f"afade=t=in:st=0:d=0.4,"
                f"afade=t=out:st={max(duration - 0.6, 0):.3f}:d=0.6,"
                f"volume={BED_VOLUME}[a]"
            )
            maps += ["-map", "[a]"]
        elif has_audio:
            maps += ["-map", "0:a?"]

        cmd += ["-filter_complex", chain] + maps + encode
        cmd += (audio_encode if want_audio else ["-an"]) + [str(main_path)]
        if not _run(cmd, "main encode"):
            return str(video_path)

        # ── pass 2: the end card. Seconds long, so this is cheap.
        cmd = [
            ff, "-y", "-hide_banner", "-loglevel", "error",
            "-framerate", str(fps), "-loop", "1", "-t", str(seconds), "-i", str(card),
        ]
        if want_audio:
            # The card needs its own silence, or the join drops the audio
            # stream from that point and the clip posts mute.
            cmd += ["-f", "lavfi", "-i",
                    "anullsrc=channel_layout=stereo:sample_rate=44100"]
        cmd += ["-vf", f"scale={tw}:{th}:flags=lanczos,format=yuv420p,setsar=1"]
        cmd += encode + (audio_encode + ["-shortest"] if want_audio else ["-an"])
        cmd += [str(card_path)]
        if not _run(cmd, "card encode"):
            return str(video_path)

        # ── pass 3: join. No re-encode, so this is nearly free in both time
        # and memory — 25MB against the 311MB the encode itself needs.
        list_path.write_text(
            f"file '{main_path.as_posix()}'\nfile '{card_path.as_posix()}'\n",
            encoding="utf-8",
        )
        if not _run([
            ff, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", str(list_path),
            "-c", "copy", "-movflags", "+faststart", str(dest),
        ], "join"):
            return str(video_path)

        if not dest.exists() or dest.stat().st_size == 0:
            logger.error("Outro: join produced an empty file, posting the clip as-is")
            return str(video_path)
    finally:
        _cleanup()

    before = memory_headroom_mb()
    release_memory()
    after = memory_headroom_mb()
    reclaimed = "" if (before is None or after is None) else         f", freed {after - before:.0f}MB (now {after:.0f}MB free)"

    logger.info(
        f"Branded {src.name}: watermark + {seconds}s card, {tw}x{th} "
        f"crf{QUALITY_CRF} capped {MAX_BITRATE} -> "
        f"{dest.stat().st_size / 1e6:.1f}MB{reclaimed}"
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


def probe_audio(path: str | Path) -> Optional[bool]:
    """Does this file carry a sound track? None when it cannot be read.

    None and False mean different things to the caller: False is "definitely
    silent, hold it back from auto-publishing", None is "unknown, treat it as
    postable" — guessing silent on an unreadable probe would quietly stall a
    schedule.
    """
    probed = _probe(Path(path))
    return None if probed is None else probed[3]


async def brand_video_at_url(
    video_url: str,
    profile,
    workspace_id: str,
    media_id: str,
    seconds: float = DEFAULT_OUTRO_SECONDS,
    probe_out: Optional[dict] = None,
    bed_url: Optional[str] = None,
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

        # The file is already on disk for ffmpeg, so this costs one probe
        # rather than a second download. Reported through probe_out because
        # the caller owns the database session and this function does not.
        has_audio = probe_audio(source)
        if probe_out is not None:
            probe_out["has_audio"] = has_audio

        # The track is fetched only once the probe says the clip is silent.
        # Downloading it for every clip would spend bandwidth on the majority
        # that already carry their own sound and will never use it.
        bed_path = None
        if bed_url and has_audio is False:
            bed_path = work / f"bed{Path(bed_url.split('?')[0]).suffix or '.mp3'}"
            try:
                async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
                    async with client.stream("GET", bed_url) as resp:
                        resp.raise_for_status()
                        with bed_path.open("wb") as fh:
                            async for chunk in resp.aiter_bytes(1024 * 256):
                                fh.write(chunk)
            except Exception as e:
                # A missing track is not a reason to leave the clip unbranded.
                logger.warning(f"Outro: could not fetch the music bed: {e}")
                bed_path = None

        # append_outro shells out to ffmpeg with a blocking subprocess call.
        # Awaiting it directly on the event loop froze the entire server for
        # the duration — this runs on a single uvicorn worker, so branding a
        # backlog of clips made the API unreachable and uploads failed while
        # it churned. Off to a thread.
        branded = Path(
            await asyncio.to_thread(
                functools.partial(
                    append_outro, source, brand, cta, url, seconds,
                    audio_bed=bed_path,
                )
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


async def add_music_at_url(
    video_url: str,
    bed_url: str,
    workspace_id: str,
    media_id: str,
) -> Optional[str]:
    """Lay a music bed under a finished clip. Returns the new URL, or None.

    Done at posting time rather than at branding time, because that is when it
    is nearly free: the video stream is copied, not re-encoded, so this costs
    21MB and half a second against the 311MB and thirty-plus seconds a full
    encode needs. It also means a clip does not have to be re-branded to gain
    music, and the operator can add tracks whenever they like.

    The caller is responsible for checking the clip is actually silent. Mixing
    music under existing speech ruins both.
    """
    import httpx

    from services.storage_service import upload_media_to_cloudinary

    ff = _ffmpeg()
    if not ff:
        return None

    work = Path(tempfile.mkdtemp(prefix="score_"))
    try:
        source = work / "clip.mp4"
        bed = work / f"bed{Path(bed_url.split('?')[0]).suffix or '.mp3'}"
        try:
            async with httpx.AsyncClient(timeout=180.0, follow_redirects=True) as client:
                for url, target in ((video_url, source), (bed_url, bed)):
                    async with client.stream("GET", url) as resp:
                        resp.raise_for_status()
                        with target.open("wb") as fh:
                            async for chunk in resp.aiter_bytes(1024 * 256):
                                fh.write(chunk)
        except Exception as e:
            logger.warning(f"Music: could not fetch the clip or track: {e}")
            return None

        probed = _probe(source)
        if not probed:
            return None
        duration = probed[4]
        if probed[3]:
            # Belt and braces. The caller checks this, but a clip that gained
            # audio between the check and here must not have it overwritten.
            logger.info("Music: clip already has audio, leaving it alone")
            return None

        dest = work / "scored.mp4"
        cmd = [
            ff, "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(source),
            # Looped in case the track is shorter than the clip.
            "-stream_loop", "-1", "-i", str(bed),
            "-filter_complex",
            f"[1:a]atrim=duration={duration:.3f},"
            f"afade=t=in:st=0:d=0.4,"
            f"afade=t=out:st={max(duration - 0.6, 0):.3f}:d=0.6,"
            f"volume={BED_VOLUME}[a]",
            # -c:v copy is the whole point: the picture is untouched, so there
            # is no generation loss and no encoder to feed.
            "-map", "0:v", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
            "-movflags", "+faststart", str(dest),
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True,
                               errors="ignore", timeout=300)
        except subprocess.TimeoutExpired:
            logger.error("Music: ffmpeg timed out, posting the clip silent")
            return None
        if r.returncode != 0 or not dest.exists() or dest.stat().st_size == 0:
            logger.error(f"Music: ffmpeg failed ({r.returncode}): {r.stderr[:300]}")
            return None

        uploaded = await upload_media_to_cloudinary(
            workspace_id=workspace_id,
            # "_branded" is retained deliberately: the catalog decides whether a
            # clip still needs branding by looking for it in the URL, and a
            # name without it would send an already-branded clip back through
            # a 311MB encode.
            media_id=f"{media_id}_branded_scored",
            filename="scored.mp4",
            source=dest.read_bytes(),
            resource_type="video",
            tags=["music", "ai-generated"],
        )
        if not uploaded or not uploaded.get("secure_url"):
            logger.error("Music: upload failed, posting the clip silent")
            return None

        logger.info(f"Music: bed laid under {media_id}")
        return uploaded["secure_url"]
    finally:
        shutil.rmtree(work, ignore_errors=True)

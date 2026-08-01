"""Bulk media ingest, with a base caption written from what the file shows.

The base caption is what the post-caption writer reads to know what an asset
depicts. Uploading a folder without one leaves every asset described as
nothing, and the captions go generic — which is the failure the caption field
was added to fix in the first place.

Filenames cannot supply it. A real folder looks like:

    thetrillionairelife_2025-12-23_DSnJoNaklOM_2.mp4
    leandrolopesofficial_2026-07-31_DbbP1EeM3wd_0.mp4

That is a handle and an ID. So the asset is actually LOOKED AT: a frame is
pulled from each video with ffmpeg, described by the vision model, and turned
into one sentence in the language of this specific business.

Concurrency is capped because a folder can hold hundreds of files and the
provider is a shared free tier. Failures are per-file: one asset that cannot
be described still uploads, with an empty caption the user can fill in.
"""

from __future__ import annotations

import asyncio
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

# Vision calls are the slow part. Four at a time keeps a 240-file folder moving
# without tripping the provider's rate limit, which returns 429 for everything
# in flight rather than queueing.
MAX_CONCURRENT = 4

# ffmpeg is CPU-bound, not IO-bound. Four concurrent 1080p encodes saturate a
# shared container even from worker threads, and the web server is competing
# for the same core — a backlog of branding made the API unreachable and
# uploads failed while it churned. One at a time: the pass takes longer and
# the service stays up, which is the correct trade for background work.
MAX_ENCODES = 1
_encode_slot = asyncio.Semaphore(MAX_ENCODES)

# FREE MODELS ONLY, by choice.
#
# The cost of that choice, measured rather than assumed: on a sample of six
# real files the first free model returned 504 on every one. A single free
# model is not reliable enough to describe a library, so several are chained
# and the first that answers wins.
#
# `openrouter/free` is deliberately NOT in this list. It routes across whatever
# free capacity is up, which included nemotron-3.5-content-safety — a safety
# classifier that answered "User Safety: safe" instead of describing the frame.
# Three of six test files came back with that. A wrong description is worse than
# none, because it silently poisons every caption written from the asset.
#
# If a whole pass comes back with empty captions, that is the free tier being
# down rather than a fault in this code, and the assets are still uploaded and
# editable. Adding a paid model to this list is a one-line change.
VISION_MODELS = [
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-nano-12b-v2-vl:free",
    "google/gemma-4-26b-a4b-it:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
]

# Files past this are almost certainly not social assets, and a folder often
# contains a stray export or archive.
MAX_BYTES = 200 * 1024 * 1024

IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic"}
VIDEO_TYPES = {".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"}


def _mime_for(filename: str) -> Optional[str]:
    ext = Path(filename).suffix.lower()
    if ext in IMAGE_TYPES:
        return f"image/{'jpeg' if ext in {'.jpg', '.jpeg'} else ext.lstrip('.')}"
    if ext in VIDEO_TYPES:
        return f"video/{'mp4' if ext in {'.mp4', '.m4v'} else ext.lstrip('.')}"
    return None


def extract_poster_frame(video_bytes: bytes) -> Optional[bytes]:
    """A single frame from ~1s in, as JPEG.

    Frame zero is often black or a fade, so it describes nothing. One second in
    the shot has usually started.
    """
    from services.video_outro import _ffmpeg

    ff = _ffmpeg()
    if not ff:
        return None

    work = Path(tempfile.mkdtemp(prefix="poster_"))
    try:
        src = work / "clip.mp4"
        src.write_bytes(video_bytes)
        out = work / "frame.jpg"
        subprocess.run(
            [ff, "-y", "-hide_banner", "-loglevel", "error",
             "-ss", "1", "-i", str(src), "-frames:v", "1",
             "-vf", "scale=512:-1", str(out)],
            capture_output=True, timeout=90,
        )
        if not out.exists() or out.stat().st_size == 0:
            # Clips shorter than a second have no frame at 1s.
            subprocess.run(
                [ff, "-y", "-hide_banner", "-loglevel", "error",
                 "-i", str(src), "-frames:v", "1",
                 "-vf", "scale=512:-1", str(out)],
                capture_output=True, timeout=90,
            )
        return out.read_bytes() if out.exists() and out.stat().st_size else None
    except Exception as e:
        logger.warning(f"Poster frame extraction failed: {e}")
        return None
    finally:
        shutil.rmtree(work, ignore_errors=True)


# Answers that are not descriptions. A safety classifier reached through a
# routing model replied "User Safety: safe" for half a test batch, and a
# refusal or an empty acknowledgement reads as success to a status check.
# Storing any of them is worse than storing nothing: the caption writer treats
# the base caption as fact.
_NOT_A_DESCRIPTION = re.compile(
    r"^\s*(user safety|response safety|safety:|unsafe|safe|i can(?:'|no)t|"
    r"i'm sorry|sorry,|as an ai|unable to|no image|cannot see)",
    re.IGNORECASE,
)


def _looks_like_a_description(text: str) -> bool:
    """Whether this reads as a description of a frame rather than a verdict."""
    if _NOT_A_DESCRIPTION.match(text):
        return False
    # A real description of a scene runs to a sentence. Four words is a label.
    return len(text.split()) >= 5


async def describe_asset(
    content: bytes, filename: str, profile: Any
) -> str:
    """One sentence describing what this asset shows, in this brand's terms.

    Returns "" rather than a guess when the asset cannot be seen. An empty
    caption is honest and editable; an invented one silently misleads every
    post that uses the asset.
    """
    import base64

    from config import settings

    mime = _mime_for(filename) or ""
    # Blocking subprocess; keep it off the event loop.
    image_bytes = (
        content if mime.startswith("image/")
        else await asyncio.to_thread(extract_poster_frame, content)
    )
    if not image_bytes:
        return ""

    # The description is the highest-value field here — it is what tells the
    # model whether a shot of a car is stock footage or this brand's own
    # product, and which of two plausible readings of a frame is the relevant
    # one. Content pillars matter for the same reason.
    brand_bits = []
    for label, attr in (
        ("Business", "name"),
        ("What this business is", "description"),
        ("Who it is for", "targetAudience"),
        ("Voice", "toneOfVoice"),
        ("Industry", "industry"),
    ):
        v = (getattr(profile, attr, None) or "").strip()
        if v:
            brand_bits.append(f"{label}: {v[:400]}")

    pillars = getattr(profile, "contentPillars", None)
    if pillars:
        if isinstance(pillars, (list, tuple)):
            pillars = ", ".join(str(p) for p in pillars)
        brand_bits.append(f"Content pillars: {str(pillars)[:300]}")

    # The stored understanding, when the workspace has one, carries the pain
    # point and transformation the flat fields do not.
    try:
        from services.brand_intelligence import to_scene_context

        ctx = to_scene_context(getattr(profile, "brandIntelligence", None))
        if ctx.get("what_it_does"):
            brand_bits.append(f"In practice: {ctx['what_it_does'][:300]}")
    except Exception:
        pass

    prompt = (
        "You are describing one frame of an asset belonging to the business "
        "below, so that a caption writer who cannot see it knows what it "
        "shows.\n\n"
        + "\n".join(brand_bits)
        + "\n\nWrite ONE sentence, at most 25 words, naming the concrete "
        "things actually in frame: the object, the setting, the action, and "
        "any visible text.\n\n"
        "Read the frame THROUGH this business. If the brand is about "
        "hypercars and the frame shows a car, say which kind of shot it is — "
        "a rolling exterior, a cabin detail, a badge close-up — because that "
        "is the distinction the caption depends on.\n\n"
        "Do not write marketing copy. Do not use words like stunning, "
        "luxurious or breathtaking. Do not state anything you cannot see: if "
        "the frame is ambiguous, describe only what is certain."
    )

    import httpx

    from services.ai_service import LLM_TIMEOUT

    b64 = base64.b64encode(image_bytes).decode()
    body = {
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ],
        }],
    }

    for index, model in enumerate(VISION_MODELS):
        try:
            async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.openrouter_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={**body, "model": model},
                )
            if resp.status_code == 200:
                data = resp.json()
                # OpenRouter answers 200 with an error body when a model
                # rejects a request, so the payload has to be checked too.
                if data.get("error"):
                    raise RuntimeError(str(data["error"])[:160])
                text = data["choices"][0]["message"]["content"]
                described = " ".join(str(text).strip().split())[:300]
                if described and not _looks_like_a_description(described):
                    logger.warning(
                        f"{model} returned a non-description for {filename}: "
                        f"{described[:60]!r}"
                    )
                    described = ""
                if described:
                    if index:
                        logger.info(f"Described {filename} via fallback {model}")
                    return described
                raise RuntimeError("empty description")

            if resp.status_code in (429, 402, 503):
                logger.info(
                    f"{model} unavailable for {filename} ({resp.status_code}); "
                    f"trying the next model"
                )
                continue
            logger.warning(f"Vision failed for {filename}: {resp.status_code}")
        except Exception as e:
            logger.warning(f"{model} failed for {filename}: {e}")

    logger.warning(f"No vision model could describe {filename}")
    return ""


async def ingest_one(
    content: bytes,
    filename: str,
    profile: Any,
    user_id: str,
    workspace_id: str,
    write_captions: bool = True,
) -> Dict[str, Any]:
    """Upload one asset and return a row describing what happened."""
    from services.storage_service import upload_media_to_cloudinary

    mime = _mime_for(filename)
    if not mime:
        return {"filename": filename, "ok": False, "reason": "unsupported file type"}
    if len(content) > MAX_BYTES:
        return {"filename": filename, "ok": False,
                "reason": f"larger than {MAX_BYTES // (1024 * 1024)}MB"}

    # Vision does NOT run here. A frame extract plus a vision call takes tens
    # of seconds per asset, and gunicorn kills the worker at --timeout 120, so
    # a batch of eight videos could never finish inside one request — every
    # batch returned 500. Captions are written afterwards by
    # describe_pending_media and fill in progressively.
    caption = ""

    # Branding does NOT happen here either. Scaling to 1080p, compositing a
    # watermark and concatenating an end card is ~15s per clip on a laptop and
    # several times that on a shared container — three of them exceeded the
    # 120s request timeout on Render even though they fit locally.
    #
    # The asset is stored raw and branded by the background pass, which also
    # writes the caption. One trip through ffmpeg, off the request path.
    media_id = str(uuid.uuid4())
    try:
        uploaded = await upload_media_to_cloudinary(
            workspace_id=workspace_id,
            media_id=media_id,
            filename=filename,
            source=content,
            resource_type="video" if mime.startswith("video/") else "image",
        )
    except Exception as e:
        return {"filename": filename, "ok": False, "reason": f"upload failed: {e}"}

    if not uploaded or not uploaded.get("secure_url"):
        return {"filename": filename, "ok": False, "reason": "storage unavailable"}

    return {
        "filename": filename,
        "ok": True,
        "mediaId": media_id,
        "url": uploaded["secure_url"],
        "mimeType": mime,
        "caption": caption,
    }


async def ingest_folder(
    files: List[tuple],
    profile: Any,
    user_id: str,
    workspace_id: str,
    write_captions: bool = True,
) -> Dict[str, Any]:
    """Ingest many assets concurrently. `files` is [(filename, bytes), ...].

    Partial success is the expected outcome on a large folder, so every file
    reports its own result rather than one failure aborting the batch.
    """
    sem = asyncio.Semaphore(MAX_CONCURRENT)

    async def _one(name: str, data: bytes):
        async with sem:
            try:
                return await ingest_one(
                    data, name, profile, user_id, workspace_id, write_captions
                )
            except Exception as e:
                logger.exception(f"Bulk ingest failed for {name}")
                return {"filename": name, "ok": False, "reason": str(e)[:200]}

    results = await asyncio.gather(*(_one(n, d) for n, d in files))
    succeeded = [r for r in results if r.get("ok")]
    logger.info(
        f"Bulk ingest for {workspace_id}: {len(succeeded)}/{len(results)} stored"
    )
    return {
        "total": len(results),
        "stored": len(succeeded),
        "failed": len(results) - len(succeeded),
        "described": sum(1 for r in succeeded if r.get("caption")),
        "items": results,
    }


async def finish_pending_media(
    workspace_id: str, media_ids: List[str], profile: Any
) -> None:
    """Brand and describe already-stored assets, out of band.

    Runs after the upload request has returned. Each asset is fetched from
    storage, a frame is described, and the row is updated — so the catalog is
    usable immediately and the descriptions arrive over the following minutes.

    Per-asset failures are logged and skipped: an empty caption is editable,
    and one unreadable file must not stop the rest of a 242-file library.
    """
    import httpx

    from database import AsyncSessionLocal, Media
    from services.video_outro import brand_video_at_url

    sem = asyncio.Semaphore(MAX_CONCURRENT)

    async def _one(media_id: str):
        async with sem:
            try:
                async with AsyncSessionLocal() as session:
                    media = await session.get(Media, media_id)
                    if not media or not media.url:
                        return

                    # These are two independent jobs. The guard used to be
                    # `if media.caption: return`, which returned before the
                    # branding block below — so anything that already had a
                    # description was never branded, and since descriptions are
                    # written first that was almost everything. Descriptions
                    # filled in and watermarks never appeared.
                    is_video = (media.mimeType or "").startswith("video/")
                    needs_caption = not media.caption
                    needs_brand = is_video and "_branded" not in media.url
                    if not needs_caption and not needs_brand:
                        return

                    if needs_caption:
                        # Only the first megabytes are needed: describe_asset
                        # pulls a frame at the one-second mark. Fetching whole
                        # clips into memory, four at a time, is what pushed
                        # this 512MB instance into an out-of-memory kill.
                        body = bytearray()
                        async with httpx.AsyncClient(
                            timeout=120.0, follow_redirects=True
                        ) as c:
                            async with c.stream("GET", media.url) as resp:
                                if resp.status_code != 200:
                                    logger.warning(
                                        f"Could not fetch {media.filename} to "
                                        f"describe it: {resp.status_code}"
                                    )
                                else:
                                    async for chunk in resp.aiter_bytes(1024 * 256):
                                        body.extend(chunk)
                                        if len(body) >= 6 * 1024 * 1024:
                                            break

                        if body:
                            caption = await describe_asset(
                                bytes(body), media.filename or "asset", profile
                            )
                            if caption:
                                media.caption = caption
                                await session.commit()
                                logger.info(
                                    f"Described {media.filename}: {caption[:70]}"
                                )

                # Branded after describing, so the description comes from the
                # original footage rather than a frame carrying our own mark.
                if needs_brand:
                    async with _encode_slot:
                        branded = await brand_video_at_url(
                            media.url, profile, workspace_id, media_id
                        )
                    if branded and branded != media.url:
                        async with AsyncSessionLocal() as s2:
                            row = await s2.get(Media, media_id)
                            if row:
                                row.url = branded
                                await s2.commit()
                        logger.info(f"Branded {media.filename}")
            except Exception:
                logger.exception(f"Could not describe media {media_id}")

    await asyncio.gather(*(_one(mid) for mid in media_ids))
    logger.info(f"Caption pass finished for {len(media_ids)} assets in {workspace_id}")

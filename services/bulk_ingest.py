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
    image_bytes = content if mime.startswith("image/") else extract_poster_frame(content)
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

    try:
        import httpx

        from services.ai_service import LLM_TIMEOUT
        from services.video_pipeline_service import VISION_MODEL

        b64 = base64.b64encode(image_bytes).decode()
        async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": VISION_MODEL,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url",
                             "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                        ],
                    }],
                },
            )
        if resp.status_code != 200:
            logger.warning(f"Vision failed for {filename}: {resp.status_code}")
            return ""
        text = resp.json()["choices"][0]["message"]["content"]
        return " ".join(str(text).strip().split())[:300]
    except Exception as e:
        logger.warning(f"Could not describe {filename}: {e}")
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

    caption = ""
    if write_captions:
        caption = await describe_asset(content, filename, profile)

    # Same branding the single-file upload applies, so a bulk-added clip is not
    # the odd one out in the feed.
    if mime.startswith("video/"):
        try:
            from services.video_outro import append_outro, outro_text_for

            brand, cta, url = outro_text_for(profile)
            if brand:
                work = Path(tempfile.mkdtemp(prefix="bulk_outro_"))
                try:
                    src = work / "clip.mp4"
                    src.write_bytes(content)
                    branded = Path(append_outro(src, brand, cta, url))
                    if branded != src and branded.exists():
                        content = branded.read_bytes()
                finally:
                    shutil.rmtree(work, ignore_errors=True)
        except Exception:
            logger.exception(f"Outro failed for {filename}; storing the original")

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

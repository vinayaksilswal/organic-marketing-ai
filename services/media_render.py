"""Actually spending the key the customer connected.

`services/media_providers.py` stores a rendering credential. Until this
module existed it was never used: the connect button worked, the key was
encrypted, and nothing ever called the provider. A stored key that is never
spent is the same failure this codebase keeps producing — a capability that
exists and does nothing.

WHY ONLY THREE PROVIDERS
------------------------
Replicate, OpenAI and fal each take a prompt over one HTTP call and hand back
an image or a video. Runway needs an input image for its video endpoint and
Kling signs requests with a JWT built from a key pair — neither is a prompt in,
file out, and a half-guessed version of either would fail *after* a customer
believed it was set up. They are not in the catalogue, so no key can be
connected that this cannot spend.

WHOSE MONEY THIS IS
-------------------
Every call here bills the customer's own account. So: one render per request,
no retries on a successful-but-unwanted result, and a hard ceiling on polling
so a stuck prediction cannot quietly bill for an hour.
"""

from __future__ import annotations

import asyncio
import base64
import time
from typing import Any, Dict, Optional

import httpx
from loguru import logger

# A render is slow — a video model can take minutes — but not unbounded. Past
# this the prediction is abandoned rather than polled forever.
POLL_TIMEOUT_SECONDS = 300
POLL_INTERVAL_SECONDS = 3

# Instagram is the target, so vertical unless the provider cannot express it.
ASPECT_RATIO = "9:16"


class RenderError(Exception):
    """Something the customer can read and act on."""


async def render(session: Any, user_id: str, workspace_id: str, *,
                 kind: str, prompt: str) -> Dict[str, Any]:
    """Turn one prompt into one file on the customer's own account.

    Returns {"url", "provider", "model", "kind"}. Raises RenderError with a
    message meant for a person, never a bare provider payload.
    """
    from services import media_providers
    from services.crypto_service import decrypt_token

    prompt = (prompt or "").strip()
    if not prompt:
        raise RenderError("There is no prompt to render.")

    row = await _config_row(session, user_id, workspace_id, kind)
    if not row:
        raise RenderError(
            f"No {kind} account is connected. Connect one first, then generate."
        )

    key = decrypt_token(row.apiKey)
    if not key:
        raise RenderError(
            f"The stored {kind} key could not be read. Reconnect the account."
        )

    provider = (row.provider or "").lower()
    model = row.model or _default_model(kind, provider)

    if provider == "replicate":
        url = await _replicate(key, model, prompt, kind)
    elif provider == "openai":
        url = await _openai_image(key, model, prompt)
    elif provider == "fal":
        url = await _fal(key, model, prompt)
    else:
        # Reachable only for a key stored before the catalogue was trimmed.
        raise RenderError(
            f"'{provider}' cannot be rendered from here. Reconnect using one of: "
            f"{', '.join(p['id'] for p in media_providers.PROVIDERS.get(kind, []))}."
        )

    if not url:
        raise RenderError("The provider accepted the prompt but returned no file.")

    return {"url": url, "provider": provider, "model": model, "kind": kind}


async def _config_row(session: Any, user_id: str, workspace_id: str, kind: str):
    from sqlalchemy import select

    from database import VideoApiConfig

    return (await session.execute(
        select(VideoApiConfig).where(
            VideoApiConfig.userId == user_id,
            VideoApiConfig.businessProfileId == workspace_id,
            VideoApiConfig.kind == kind,
        )
    )).scalars().first()


def _default_model(kind: str, provider: str) -> str:
    from services import media_providers

    for entry in media_providers.PROVIDERS.get(kind, []):
        if entry["id"] == provider and entry["models"]:
            return entry["models"][0]
    return ""


# ---------------------------------------------------------------------------
# Replicate — image and video
# ---------------------------------------------------------------------------

async def _replicate(key: str, model: str, prompt: str, kind: str) -> Optional[str]:
    """Create a prediction, then poll it.

    Replicate answers immediately with a job, not a file. The `Prefer: wait`
    header sometimes returns the finished result inline, so that is checked
    before falling back to polling — it saves a round trip when it works and
    costs nothing when it does not.
    """
    if "/" not in model:
        raise RenderError(f"'{model}' is not a Replicate model path.")

    payload: Dict[str, Any] = {"input": {"prompt": prompt}}
    if kind == "image":
        payload["input"]["aspect_ratio"] = ASPECT_RATIO

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "wait",
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"https://api.replicate.com/v1/models/{model}/predictions",
            headers=headers, json=payload,
        )
        if resp.status_code == 401:
            raise RenderError("Replicate rejected the key. Reconnect the account.")
        if resp.status_code == 402:
            raise RenderError("Replicate reports no credit on this account.")
        if resp.status_code not in (200, 201):
            raise RenderError(_provider_message("Replicate", resp))

        job = resp.json()
        url = _replicate_output(job)
        if url:
            return url

        poll_url = (job.get("urls") or {}).get("get")
        if not poll_url:
            raise RenderError("Replicate did not say where to collect the result.")

        # A wall-clock deadline, not an accumulated counter. Adding the
        # interval to a running total means a zero interval never advances it
        # and the loop spins forever -- which is exactly what happened the
        # first time this was tested with the sleep patched out.
        deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

            check = await client.get(poll_url, headers={"Authorization": f"Bearer {key}"})
            if check.status_code != 200:
                continue

            job = check.json()
            status = job.get("status")
            if status == "succeeded":
                return _replicate_output(job)
            if status in ("failed", "canceled"):
                raise RenderError(
                    f"Replicate could not render this: {job.get('error') or status}."
                )

    raise RenderError(
        f"Replicate was still working after {POLL_TIMEOUT_SECONDS // 60} minutes. "
        "The render may still finish on your Replicate dashboard."
    )


def _replicate_output(job: Dict[str, Any]) -> Optional[str]:
    """`output` is a URL, or a list of them, or absent while still running."""
    out = job.get("output")
    if isinstance(out, str):
        return out
    if isinstance(out, list) and out:
        first = out[0]
        return first if isinstance(first, str) else None
    return None


# ---------------------------------------------------------------------------
# OpenAI Images
# ---------------------------------------------------------------------------

async def _openai_image(key: str, model: str, prompt: str) -> Optional[str]:
    """gpt-image-1 returns base64; dall-e-3 returns a URL. Both are handled.

    The base64 case is returned as a data URI so the caller has one shape to
    deal with — it is uploaded to storage immediately afterwards either way.
    """
    payload = {
        "model": model or "gpt-image-1",
        "prompt": prompt,
        "n": 1,
        # Vertical, for Reels and Stories.
        "size": "1024x1536",
    }

    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(
            "https://api.openai.com/v1/images/generations",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
        )

    if resp.status_code == 401:
        raise RenderError("OpenAI rejected the key. Reconnect the account.")
    if resp.status_code == 429:
        raise RenderError("OpenAI is rate-limiting this account. Try again shortly.")
    if resp.status_code != 200:
        raise RenderError(_provider_message("OpenAI", resp))

    data = (resp.json().get("data") or [])
    if not data:
        return None

    first = data[0]
    if first.get("url"):
        return first["url"]

    b64 = first.get("b64_json")
    if b64:
        # Validated before it is handed on: a malformed payload should fail
        # here, not deep inside the uploader.
        try:
            base64.b64decode(b64[:64] + "==", validate=False)
        except Exception:
            raise RenderError("OpenAI returned an image that could not be decoded.")
        return f"data:image/png;base64,{b64}"

    return None


# ---------------------------------------------------------------------------
# fal.ai
# ---------------------------------------------------------------------------

async def _fal(key: str, model: str, prompt: str) -> Optional[str]:
    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(
            f"https://fal.run/{model}",
            headers={"Authorization": f"Key {key}", "Content-Type": "application/json"},
            json={"prompt": prompt, "image_size": "portrait_16_9"},
        )

    if resp.status_code in (401, 403):
        raise RenderError("fal.ai rejected the key. Reconnect the account.")
    if resp.status_code != 200:
        raise RenderError(_provider_message("fal.ai", resp))

    body = resp.json()
    for collection in ("images", "video", "videos"):
        item = body.get(collection)
        if isinstance(item, dict) and item.get("url"):
            return item["url"]
        if isinstance(item, list) and item and isinstance(item[0], dict):
            return item[0].get("url")
    return None


def _provider_message(name: str, resp: Any) -> str:
    """One readable line from a provider error.

    The raw body is logged, not shown: it can carry account identifiers, and a
    customer needs to know what to do rather than what the JSON said.
    """
    try:
        logger.warning(f"{name} render failed [{resp.status_code}]: {resp.text[:400]}")
    except Exception:
        pass
    return f"{name} refused the request ({resp.status_code}). The prompt may be too long or blocked by their filters."


# ---------------------------------------------------------------------------
# Render, then keep the result
#
# The render itself is backgrounded. A video model takes minutes and Render's
# proxy closes an idle request long before that, so holding the connection
# would turn every video render into a gateway timeout the customer reads as a
# failure -- while their account is billed for a file that did render.
#
# So the request returns immediately, this runs detached, and the finished
# file lands in the Media catalog where the rest of the product already looks
# for assets.
# ---------------------------------------------------------------------------

async def render_and_store(user_id: str, workspace_id: str, *,
                           kind: str, prompt: str) -> Optional[str]:
    """Render one prompt and file the result. Never raises into the caller.

    Returns the stored URL, or None. Failures are logged rather than thrown:
    this runs detached, so there is nobody left to catch anything.
    """
    from database import AsyncSessionLocal, Media, generate_uuid
    from services.storage_service import upload_media_to_cloudinary

    try:
        async with AsyncSessionLocal() as session:
            result = await render(session, user_id, workspace_id,
                                  kind=kind, prompt=prompt)
    except RenderError as e:
        logger.warning(f"Render refused for workspace {workspace_id}: {e}")
        return None
    except Exception as e:
        logger.opt(exception=e).error(f"Render crashed for workspace {workspace_id}")
        return None

    source = result["url"]
    media_id = generate_uuid()

    # Onto our own storage. A provider URL is signed and expires -- posting a
    # week later would publish a dead link, which is exactly the class of
    # silent breakage this codebase keeps finding.
    stored = None
    try:
        stored = await upload_media_to_cloudinary(
            workspace_id, media_id, source,
            resource_type="video" if kind == "video" else "image",
            tags=["ai-generated", f"provider:{result['provider']}"],
        )
    except Exception as e:
        logger.warning(f"Could not store the render: {e}")

    final_url = (stored or {}).get("secure_url") or (stored or {}).get("url")
    if not final_url:
        if source.startswith("data:"):
            # Nothing to fall back to: a data URI is not a link anybody else
            # can fetch, and writing it into the catalog would produce a row
            # that looks fine and cannot be posted.
            logger.error("Render succeeded but storage failed and the result is inline only.")
            return None
        final_url = source

    ext = "mp4" if kind == "video" else "png"
    try:
        async with AsyncSessionLocal() as session:
            session.add(Media(
                id=media_id,
                userId=user_id,
                businessProfileId=workspace_id,
                filename=f"AI_{result['provider']}_{media_id[:8]}.{ext}",
                mimeType="video/mp4" if kind == "video" else "image/png",
                url=final_url,
                tags=["ai-generated", f"provider:{result['provider']}"],
                aiGenerated=True,
                prompt=prompt,
                promptType=kind,
                # The prompt describes what the asset shows, which is the
                # strongest signal the caption writer has.
                caption=prompt,
            ))
            await session.commit()
    except Exception as e:
        logger.opt(exception=e).error("Rendered and stored, but the catalog row failed")
        return final_url

    logger.info(f"Rendered {kind} via {result['provider']} for workspace {workspace_id}")
    return final_url

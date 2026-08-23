"""Bringing your own image and video generation account.

The platform writes the prompts. Rendering them is a separate paid service —
Runway, Kling, Replicate — and metering everyone's renders through one shared
account is a business that loses money on its best customers.

So a workspace connects its own key and picks its own model. That turns the
prompt studio from something you copy out of into something that finishes the
job, without this platform standing between a customer and their own spend.

THE KEY IS THE CUSTOMER'S MONEY
-------------------------------
It is encrypted at rest with the same Fernet helper as the social tokens, and
it is never returned to the browser. The interface gets a masked hint and a
connected flag, which is everything it needs to render honestly and nothing
that would matter if a response were logged.

WHAT IS NOT HERE
----------------
No rendering. This stores and reports the connection; the call that spends the
customer's credits belongs with the code that builds the request for each
provider, and inventing that for six providers before any customer has
connected one would be six guesses.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select

# What a workspace can connect. Kept deliberately short: each entry here is a
# promise that a key of this kind will be used, and a list of twenty providers
# nobody has wired up is a list of twenty small lies.
PROVIDERS: Dict[str, List[Dict[str, Any]]] = {
    "image": [
        {
            "id": "replicate",
            "name": "Replicate",
            "models": ["black-forest-labs/flux-1.1-pro", "black-forest-labs/flux-schnell",
                       "stability-ai/sdxl"],
            "keyHint": "Starts r8_ — from replicate.com/account/api-tokens",
        },
        {
            "id": "openai",
            "name": "OpenAI Images",
            "models": ["gpt-image-1", "dall-e-3"],
            "keyHint": "Starts sk- — from platform.openai.com/api-keys",
        },
        {
            "id": "fal",
            "name": "fal.ai",
            "models": ["fal-ai/flux/dev", "fal-ai/flux-pro"],
            "keyHint": "From fal.ai/dashboard/keys",
        },
    ],
    "video": [
        {
            "id": "runway",
            "name": "Runway",
            "models": ["gen4_turbo", "gen3a_turbo"],
            "keyHint": "From dev.runwayml.com",
        },
        {
            "id": "kling",
            "name": "Kling",
            "models": ["kling-v2-master", "kling-v1-6-pro"],
            "keyHint": "From klingai.com developer settings",
        },
        {
            "id": "replicate",
            "name": "Replicate",
            "models": ["minimax/video-01", "tencent/hunyuan-video"],
            "keyHint": "Starts r8_ — from replicate.com/account/api-tokens",
        },
    ],
}

KINDS = tuple(PROVIDERS)


def catalogue() -> Dict[str, Any]:
    """What can be connected. Static, and safe to serve to anyone signed in."""
    return {"providers": PROVIDERS, "kinds": list(KINDS)}


def is_supported(kind: str, provider: str, model: Optional[str]) -> Optional[str]:
    """Validate a connection request. Returns a reason, or None if it is fine.

    Checked here rather than trusted from the browser: a provider id that is
    not in the catalogue would be stored, reported as connected, and then fail
    at render time — long after the customer believed they had set it up.
    """
    if kind not in PROVIDERS:
        return f"Unknown kind '{kind}'. Expected one of: {', '.join(KINDS)}."

    entry = next((p for p in PROVIDERS[kind] if p["id"] == provider), None)
    if not entry:
        names = ", ".join(p["id"] for p in PROVIDERS[kind])
        return f"Unknown {kind} provider '{provider}'. Supported: {names}."

    if model and model not in entry["models"]:
        return (
            f"{entry['name']} does not offer '{model}' here. "
            f"Choose one of: {', '.join(entry['models'])}."
        )

    return None


def mask(key: Optional[str]) -> str:
    """A hint that identifies the key without being usable.

    Enough for somebody to recognise which of their keys is connected, and
    useless to anyone who reads it out of a log.
    """
    if not key:
        return ""
    if len(key) <= 8:
        return "•" * len(key)
    return f"{key[:4]}…{key[-4:]}"


async def save(session: Any, user_id: str, workspace_id: str, *,
               kind: str, provider: str, api_key: str,
               model: Optional[str] = None) -> Dict[str, Any]:
    """Store or replace one connection. The key is encrypted before it lands."""
    from database import VideoApiConfig
    from services.crypto_service import encrypt_token

    existing = (await session.execute(
        select(VideoApiConfig).where(
            VideoApiConfig.userId == user_id,
            VideoApiConfig.businessProfileId == workspace_id,
            VideoApiConfig.kind == kind,
        )
    )).scalars().first()

    if not existing:
        existing = VideoApiConfig(
            userId=user_id, businessProfileId=workspace_id, kind=kind
        )
        session.add(existing)

    existing.provider = provider
    existing.model = model
    existing.apiKey = encrypt_token(api_key)
    await session.commit()

    logger.info(f"{kind} provider {provider} connected for workspace {workspace_id}")
    return {"kind": kind, "provider": provider, "model": model,
            "connected": True, "keyHint": mask(api_key)}


async def connections(session: Any, user_id: str, workspace_id: str) -> Dict[str, Any]:
    """What this workspace has connected. Never includes a key."""
    from database import VideoApiConfig
    from services.crypto_service import decrypt_token

    rows = (await session.execute(
        select(VideoApiConfig).where(
            VideoApiConfig.userId == user_id,
            VideoApiConfig.businessProfileId == workspace_id,
        )
    )).scalars().all()

    out: Dict[str, Any] = {kind: {"connected": False} for kind in KINDS}
    for row in rows:
        kind = getattr(row, "kind", None) or "video"
        if kind not in out:
            continue
        try:
            plain = decrypt_token(row.apiKey)
        except Exception:
            plain = None
        out[kind] = {
            "connected": bool(row.apiKey),
            "provider": row.provider,
            "model": getattr(row, "model", None),
            # The hint, never the key.
            "keyHint": mask(plain),
        }
    return out


async def disconnect(session: Any, user_id: str, workspace_id: str, kind: str) -> bool:
    """Forget one connection. Removes the row rather than blanking the key, so
    nothing is left holding an encrypted secret nobody uses."""
    from database import VideoApiConfig

    row = (await session.execute(
        select(VideoApiConfig).where(
            VideoApiConfig.userId == user_id,
            VideoApiConfig.businessProfileId == workspace_id,
            VideoApiConfig.kind == kind,
        )
    )).scalars().first()

    if not row:
        return False

    await session.delete(row)
    await session.commit()
    return True

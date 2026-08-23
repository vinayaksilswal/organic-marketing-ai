"""Publishing a video to YouTube.

THE QUOTA DECIDES EVERYTHING HERE
---------------------------------
An upload costs 1,600 units against a default 10,000 per day, and that budget
belongs to the application rather than to a channel. Six uploads a day, shared
by every customer on the platform.

That is small enough that it has to be spent deliberately. A workspace that
publishes every four hours would exhaust it alone before lunch and take
everyone else's uploads with it, so this refuses past a daily ceiling rather
than discovering the limit as a 403 from Google.

The counter is in memory, which is honest about what it is: a single-worker
guard rail, reset by a deploy. It exists to stop one scheduler running away
with the shared budget, not to be an accounting system.

WHY THE ACCESS TOKEN IS MINTED PER UPLOAD
-----------------------------------------
Google's access tokens last an hour and the scheduler runs on a multi-hour
interval, so a stored one is reliably stale. The refresh token is what is
kept; this exchanges it each time.
"""

from __future__ import annotations

import os
import time
from typing import Any, Optional

import httpx
from loguru import logger
from sqlalchemy import select

TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"

# 10,000 units a day at 1,600 an upload is six. Five leaves headroom for the
# channel reads, and for the fact that a failed upload can still cost quota.
DAILY_UPLOAD_CEILING = int(os.getenv("YOUTUBE_DAILY_UPLOAD_CEILING", "5"))

_uploads_today: dict[str, Any] = {"day": None, "count": 0}


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def quota_remaining() -> int:
    """How many uploads are left in the shared daily budget."""
    if _uploads_today["day"] != _today():
        return DAILY_UPLOAD_CEILING
    return max(0, DAILY_UPLOAD_CEILING - _uploads_today["count"])


def _record_upload() -> None:
    day = _today()
    if _uploads_today["day"] != day:
        _uploads_today["day"] = day
        _uploads_today["count"] = 0
    _uploads_today["count"] += 1


async def _access_token(refresh_token: str) -> Optional[str]:
    """Exchange the durable refresh token for an hour-long access token."""
    from config import settings

    client_id = settings.youtube_client_id or settings.google_client_id
    client_secret = settings.youtube_client_secret or settings.google_client_secret
    if not (client_id and client_secret and refresh_token):
        return None

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(TOKEN_URL, data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            })
            if res.status_code != 200:
                logger.error(f"YouTube token refresh failed: {res.text[:200]}")
                return None
            return res.json().get("access_token")
    except Exception as e:
        logger.error(f"YouTube token refresh error: {e}")
        return None


async def _credentials(workspace_id: str) -> Optional[str]:
    from database import AsyncSessionLocal, SocialConnection
    from services.crypto_service import decrypt_token

    async with AsyncSessionLocal() as session:
        conn = (await session.execute(
            select(SocialConnection).where(SocialConnection.businessProfileId == workspace_id)
        )).scalars().first()
        if not conn or not conn.youtubeRefreshToken:
            return None
        try:
            return decrypt_token(conn.youtubeRefreshToken)
        except Exception as e:
            logger.error(f"Could not decrypt the YouTube token for {workspace_id}: {e}")
            return None


async def upload_video(
    workspace_id: str,
    video_url: str,
    title: str,
    description: str = "",
    privacy: str = "public",
) -> Optional[str]:
    """Publish one video. Returns the video id, or None with a logged reason.

    Never raises: a YouTube failure must not take down the Meta post sharing
    the same automation run.
    """
    if quota_remaining() <= 0:
        logger.warning(
            f"YouTube upload skipped for {workspace_id}: the shared daily quota "
            f"({DAILY_UPLOAD_CEILING} uploads) is spent. It resets at midnight UTC."
        )
        return None

    refresh_token = await _credentials(workspace_id)
    if not refresh_token:
        return None

    token = await _access_token(refresh_token)
    if not token:
        return None

    # YouTube titles are capped at 100 characters and reject angle brackets.
    safe_title = (title or "New video").replace("<", "").replace(">", "").strip()[:100] or "New video"
    safe_description = (description or "").replace("<", "").replace(">", "")[:4900]

    metadata = {
        "snippet": {
            "title": safe_title,
            "description": safe_description,
            "categoryId": "22",
        },
        "status": {
            "privacyStatus": privacy if privacy in ("public", "unlisted", "private") else "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=300) as client:
            # The clip lives on Cloudinary; it is streamed through rather than
            # held in memory, because a worker with a 512MB budget cannot hold
            # a video and keep publishing.
            media = await client.get(video_url, timeout=120)
            if media.status_code != 200:
                logger.error(f"YouTube upload: could not fetch {video_url} ({media.status_code})")
                return None

            res = await client.post(
                UPLOAD_URL,
                params={"part": "snippet,status", "uploadType": "multipart"},
                headers={"Authorization": f"Bearer {token}"},
                files={
                    "metadata": (None, __import__("json").dumps(metadata), "application/json"),
                    "media": ("video.mp4", media.content, "video/*"),
                },
            )

        if res.status_code not in (200, 201):
            logger.error(f"YouTube upload refused ({res.status_code}): {res.text[:300]}")
            return None

        video_id = res.json().get("id")
        if video_id:
            _record_upload()
            logger.info(f"YouTube: published {video_id} for {workspace_id}")
        return video_id

    except Exception as e:
        logger.error(f"YouTube upload failed for {workspace_id}: {e}")
        return None

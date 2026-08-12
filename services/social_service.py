"""
=============================================================================
Lumively — Meta Graph API Client (Facebook + Instagram Publishing)
=============================================================================
Implements container-based publishing for Instagram and direct publishing
for Facebook, with full video/image/carousel handling.

Publishing Logic (Priority Order):
  1. If a video link exists → Post as REELS (Instagram) / Video (Facebook)
  2. If multiple images → Post as Carousel
  3. If single image → Post as single image
  4. Text-only fallback for Facebook (Instagram requires media)

Instagram Container Flow:
  1. Create media container via POST {ig-user-id}/media
  2. Asynchronous polling via asyncio.sleep to check container readiness
  3. Publish via POST {ig-user-id}/media_publish

All HTTP calls are fully async via httpx with exponential backoff.
Error handling catches "Unsupported post request" without crashing.
=============================================================================
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from loguru import logger
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import settings
from exceptions import IntegrationError
from services.lock_service import distributed_lock
from database import AsyncSessionLocal, SocialConnection
from sqlalchemy import select
from services.crypto_service import decrypt_token

# =============================================================================
# Constants
# =============================================================================
GRAPH_API_VERSION = "v19.0"
GRAPH_BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

# Timeout for Meta API calls (video uploads can be slow)
META_TIMEOUT = httpx.Timeout(60.0, connect=15.0)

# Instagram container polling settings
CONTAINER_POLL_INTERVAL = 5  # seconds between status checks
CONTAINER_POLL_MAX_ATTEMPTS = 24  # max 2 minutes of polling (24 * 5s)


# =============================================================================
# Helper — Detect video URLs
# =============================================================================
def _is_video(url: str) -> bool:
    """Check if a URL points to a video file based on extension or query param."""
    if not url:
        return False
    url_lower = url.lower()
    if "type=video" in url_lower:
        return True
    
    # Check if any common video extension is present in the URL (handles query params like ?type=.mp4)
    if any(ext in url_lower for ext in [".mp4", ".mov", ".webm", ".avi"]):
        return True
        
    return False


# =============================================================================
# HTTP Helper — Retry-wrapped async POST to Graph API
# =============================================================================
@retry(
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    before_sleep=lambda retry_state: logger.warning(
        f"Meta API retry attempt {retry_state.attempt_number}"
    ),
)
async def _graph_post(url: str, data: dict[str, Any]) -> dict:
    """POST to the Meta Graph API with exponential backoff retry."""
    async with httpx.AsyncClient(timeout=META_TIMEOUT) as client:
        response = await client.post(url, data=data)
        if response.is_error:
            logger.error(f"Meta Graph API Error: {response.status_code} - {response.text}")
            try:
                error_code = response.json().get("error", {}).get("code")
                if error_code == 190:
                    raise ValueError(f"Meta Graph API OAuth Error: {response.text}")
            except ValueError:
                raise
            except Exception:
                pass
        response.raise_for_status()
        return response.json()


@retry(
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
)
async def _graph_get(url: str, params: dict[str, str]) -> dict:
    """GET from the Meta Graph API with exponential backoff retry."""
    async with httpx.AsyncClient(timeout=META_TIMEOUT) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()


async def _get_fb_credentials(workspace_id: str) -> tuple[str | None, str | None]:
    """Get Facebook Page credentials from DB for the specific workspace."""
    async with AsyncSessionLocal() as session:
        stmt = select(SocialConnection).where(SocialConnection.businessProfileId == workspace_id)
        conn = (await session.execute(stmt)).scalars().first()
        if conn and conn.fbAccessToken and conn.fbPageId:
            return decrypt_token(conn.fbAccessToken) or conn.fbAccessToken, conn.fbPageId
    return None, None


async def _get_ig_credentials(workspace_id: str) -> tuple[str | None, str | None]:
    """Get Instagram Business Account credentials from DB for the specific workspace."""
    async with AsyncSessionLocal() as session:
        stmt = select(SocialConnection).where(SocialConnection.businessProfileId == workspace_id)
        conn = (await session.execute(stmt)).scalars().first()
        if conn and conn.fbAccessToken and conn.igAccountId:
            return decrypt_token(conn.fbAccessToken) or conn.fbAccessToken, conn.igAccountId
    return None, None


# =============================================================================
# Facebook Publishing
# =============================================================================
async def post_to_facebook(
    workspace_id: str, message: str, media_urls: list[str] | None = None
) -> str | None:
    """
    Post content to the Facebook Page for a specific workspace.

    Enterprise Logic:
    - Videos: Posted individually to /{page-id}/videos (Native Video/Reels).
    - Images: Grouped into a single multi-photo feed post (or single photo post).
    - Returns a comma-separated list of all successful post IDs.

    Args:
        workspace_id: The tenant's workspace ID
        message: The post caption/message text
        media_urls: Optional list of media URLs (images and/or videos)

    Returns:
        The Facebook post ID string (comma-separated if multiple), or None on failure
    """
    access_token, page_id = await _get_fb_credentials(workspace_id)
    if not access_token or not page_id:
        logger.warning("Facebook credentials missing — skipping post")
        return None

    if not media_urls:
        media_urls = []

    # Acquire distributed lock to prevent concurrent posts to the same page
    lock_key = f"fb_post_{page_id}"
    async with distributed_lock(lock_key, timeout_seconds=120) as acquired:
        if not acquired:
            logger.error(f"Could not acquire lock for Facebook Page {page_id}")
            return None

        # Facebook fetches the media itself, so relative paths must be made
        # absolute against THIS backend. The previous hardcoded marketing
        # domain does not serve media, so any relative URL was unfetchable.
        _base = (settings.backend_public_url or "").rstrip("/")
        media_urls = [
            f"{_base}{url}" if url.startswith("/") and _base else url
            for url in media_urls
        ]

        video_urls = [url for url in media_urls if _is_video(url)]
        image_urls = [url for url in media_urls if not _is_video(url)]

        post_ids = []
        # Why each attempt failed. Every branch below used to log its exception
        # and return None, and the caller reported "credentials may be
        # missing" -- a guess that was wrong and sent an investigation after
        # tokens that were valid. The Graph API says exactly what is wrong;
        # this carries that sentence back to the person who can act on it.
        failures: list[str] = []

        # --- 1. Post Each Video Separately ---
        for vid_url in video_urls:
            url = f"{GRAPH_BASE_URL}/{page_id}/videos"
            payload = {
                "access_token": access_token,
                "description": message,
                "file_url": vid_url,
            }
            try:
                result = await _graph_post(url, payload)
                post_id = result.get("id")
                if post_id:
                    logger.info(f"✓ Facebook video posted: {post_id}")
                    post_ids.append(post_id)
            except Exception as e:
                logger.error(f"Facebook video post failed: {e}")
                failures.append(f"video: {e}")

        # --- 2. Post Images ---
        if len(image_urls) > 1:
            # Multi-image carousel-style post (upload unpublished, then combine)
            attached_media: list[dict[str, str]] = []
            for img_url in image_urls[:10]:
                photo_payload = {
                    "access_token": access_token,
                    "url": img_url,
                    "published": "false",
                }
                try:
                    res = await _graph_post(f"{GRAPH_BASE_URL}/{page_id}/photos", photo_payload)
                    media_id = res.get("id")
                    if media_id:
                        attached_media.append({"media_fbid": media_id})
                except Exception as e:
                    logger.warning(f"Failed to upload unpublished FB photo: {e}")

            if attached_media:
                import json as json_lib
                feed_payload = {
                    "access_token": access_token,
                    "message": message,
                    "attached_media": json_lib.dumps(attached_media),
                }
                try:
                    result = await _graph_post(f"{GRAPH_BASE_URL}/{page_id}/feed", feed_payload)
                    post_id = result.get("id")
                    if post_id:
                        logger.info(f"✓ Facebook multi-photo post created: {post_id}")
                        post_ids.append(post_id)
                except Exception as e:
                    logger.error(f"Facebook multi-photo post failed: {e}")
                    failures.append(f"multi-photo: {e}")

        elif len(image_urls) == 1:
            # Single image
            url = f"{GRAPH_BASE_URL}/{page_id}/photos"
            payload = {
                "access_token": access_token,
                "message": message,
                "url": image_urls[0],
            }
            try:
                result = await _graph_post(url, payload)
                post_id = result.get("post_id") or result.get("id")
                if post_id:
                    logger.info(f"✓ Facebook single image posted: {post_id}")
                    post_ids.append(post_id)
            except Exception as e:
                logger.error(f"Facebook image post failed: {e}")
                failures.append(f"image: {e}")

        # --- 3. Text only (if no media was provided) ---
        if not video_urls and not image_urls:
            url = f"{GRAPH_BASE_URL}/{page_id}/feed"
            payload = {
                "access_token": access_token,
                "message": message,
            }
            try:
                result = await _graph_post(url, payload)
                post_id = result.get("id")
                if post_id:
                    logger.info(f"✓ Facebook text posted: {post_id}")
                    post_ids.append(post_id)
            except Exception as e:
                logger.error(f"Facebook text post failed: {e}")
                failures.append(f"text: {e}")

        if not post_ids:
            if failures:
                # Raised rather than returned: the caller records the message
                # of anything raised, and drops the detail of anything that
                # merely returns None.
                raise IntegrationError(
                    "Facebook rejected every attempt — " + " | ".join(failures)
                )
            logger.warning(
                f"Facebook post for page {page_id} produced no id and no error; "
                f"media_urls={len(media_urls)}"
            )
            return None
        return ",".join(post_ids)


# =============================================================================
# Instagram Container Polling
# =============================================================================
async def _poll_container_status(
    container_id: str, access_token: str
) -> bool:
    """
    Asynchronously poll an Instagram media container until it's ready.

    Instagram containers go through processing stages:
    - IN_PROGRESS: Still processing (especially videos)
    - FINISHED: Ready to publish
    - ERROR: Processing failed

    Uses asyncio.sleep for non-blocking waits between polls.

    Args:
        container_id: The Instagram container/creation ID
        access_token: The Page access token

    Returns:
        True if the container is ready (FINISHED), False on error/timeout
    """
    url = f"{GRAPH_BASE_URL}/{container_id}"
    # `status` carries Meta's human-readable reason on ERROR; status_code alone
    # only says "ERROR", which is what made every failure look identical.
    params = {
        "fields": "status_code,status",
        "access_token": access_token,
    }

    for attempt in range(CONTAINER_POLL_MAX_ATTEMPTS):
        try:
            result = await _graph_get(url, params)
            status = result.get("status_code", "IN_PROGRESS")

            if status == "FINISHED":
                logger.info(
                    f"✓ IG container {container_id} ready "
                    f"(polled {attempt + 1} times)"
                )
                return True
            elif status == "ERROR":
                detail = result.get("status") or "Instagram could not process the media."
                logger.error(f"IG container {container_id} failed processing: {detail}")
                raise IntegrationError(f"Instagram rejected the media: {detail}")
            else:
                # Still processing — wait and try again
                logger.debug(
                    f"IG container {container_id} status: {status} "
                    f"(attempt {attempt + 1}/{CONTAINER_POLL_MAX_ATTEMPTS})"
                )
                await asyncio.sleep(CONTAINER_POLL_INTERVAL)

        except Exception as e:
            logger.warning(f"IG container poll error: {e}")
            await asyncio.sleep(CONTAINER_POLL_INTERVAL)

    logger.error(
        f"IG container {container_id} timed out after "
        f"{CONTAINER_POLL_MAX_ATTEMPTS * CONTAINER_POLL_INTERVAL}s"
    )
    return False


# =============================================================================
# Instagram Publishing
# =============================================================================
async def post_to_instagram(
    workspace_id: str, message: str, media_urls: list[str] | None = None
) -> str | None:
    """
    Post content to Instagram using the container-based publishing flow.

    Flow:
    1. Create a media container (image, video/REELS, or carousel)
    2. Poll the container status until FINISHED
    3. Publish the container

    Priority:
    - Video links → REELS
    - Multiple images → Carousel
    - Single image → Standard image post

    Args:
        workspace_id: The tenant's workspace ID
        message: The post caption
        media_urls: List of media URLs (required — IG needs at least one)

    Returns:
        The Instagram post ID string.

    Raises:
        IntegrationError: with a reason the user can act on. This function used
        to swallow every failure and return None, so the delivery log could only
        say "Post returned None" whether the account was missing, the file was
        the wrong format, or Meta could not fetch the URL.
    """
    # Every failure below used to `return None`, and the caller could only
    # report "Post returned None" — identical text for a missing account, an
    # unfetchable video and a rejected format. Each now says what happened.
    access_token, ig_user_id = await _get_ig_credentials(workspace_id)
    if not access_token or not ig_user_id:
        raise IntegrationError(
            "No Instagram account is connected to this business. Connect one in "
            "Businesses → Edit."
        )

    if not media_urls:
        raise IntegrationError(
            "Instagram posts must include an image or video. This post has no media."
        )

    # Acquire distributed lock to prevent concurrent posts to the same IG account
    lock_key = f"ig_post_{ig_user_id}"
    async with distributed_lock(lock_key, timeout_seconds=300) as acquired:
        if not acquired:
            raise IntegrationError(
                "Another post to this Instagram account is already in progress. "
                "Try again in a moment."
            )

        # Instagram fetches the media itself, so a relative path cannot work.
        # The old prefix here was a hardcoded marketing domain that does not
        # serve media at all, guaranteeing an unfetchable URL.
        absolute = []
        for url in media_urls:
            if url.startswith("/"):
                base = (settings.backend_public_url or "").rstrip("/")
                if not base:
                    raise IntegrationError(
                        "Media URL is relative and no public backend URL is configured, "
                        "so Instagram cannot fetch it."
                    )
                url = f"{base}{url}"
            absolute.append(url)
        media_urls = absolute

        # Separate videos and images
        video_urls = [url for url in media_urls if _is_video(url)]
        image_urls = [url for url in media_urls if not _is_video(url)]

        post_ids = []

        # --- Post each video as a separate REEL ---
        for vid_url in video_urls:
            vid_id = await _ig_post_video(ig_user_id, access_token, message, vid_url)
            if vid_id:
                post_ids.append(vid_id)

        # --- Post images as Carousel or Single Image ---
        if len(image_urls) > 1:
            img_id = await _ig_post_carousel(ig_user_id, access_token, message, image_urls)
            if img_id:
                post_ids.append(img_id)
        elif len(image_urls) == 1:
            img_id = await _ig_post_single_image(ig_user_id, access_token, message, image_urls[0])
            if img_id:
                post_ids.append(img_id)

        if not post_ids:
            raise IntegrationError(
                "Instagram accepted no media from this post. Check that the file is "
                "a supported format (MP4/H.264 for Reels, JPG or PNG for images) and "
                "that its URL is publicly reachable."
            )

        return ",".join(post_ids)


async def _ig_post_video(
    ig_user_id: str, access_token: str, caption: str, video_url: str
) -> str | None:
    """Post a video as an Instagram Reel."""
    container_url = f"{GRAPH_BASE_URL}/{ig_user_id}/media"
    container_payload = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": access_token,
    }
    try:
        res = await _graph_post(container_url, container_payload)
        container_id = res.get("id")
        if not container_id:
            raise IntegrationError(
                "Instagram would not accept the video. Check it is MP4/H.264, "
                "under 90 seconds, and that its URL is publicly reachable."
            )

        # Poll until the video is processed and ready
        is_ready = await _poll_container_status(container_id, access_token)
        if not is_ready:
            raise IntegrationError(
                "Instagram was still processing the video when we gave up waiting. "
                "A shorter or smaller file usually resolves this."
            )

        # Publish
        publish_url = f"{GRAPH_BASE_URL}/{ig_user_id}/media_publish"
        publish_payload = {
            "creation_id": container_id,
            "access_token": access_token,
        }
        pub_res = await _graph_post(publish_url, publish_payload)
        post_id = pub_res.get("id")
        logger.info(f"✓ Instagram Reel posted: {post_id}")
        return post_id

    except Exception as e:
        # Log with context, then re-raise so the reason reaches the delivery
        # log. Swallowing it here is what produced "Post returned None".
        _handle_ig_error("video/REELS", e)
        raise IntegrationError(f"Reel upload failed: {e}") from e


async def _ig_post_single_image(
    ig_user_id: str, access_token: str, caption: str, image_url: str
) -> str | None:
    """Post a single image to Instagram."""
    container_url = f"{GRAPH_BASE_URL}/{ig_user_id}/media"
    container_payload = {
        "image_url": image_url,
        "caption": caption,
        "access_token": access_token,
    }
    try:
        res = await _graph_post(container_url, container_payload)
        container_id = res.get("id")
        if not container_id:
            raise IntegrationError(
                "Instagram would not accept the image. Check it is JPG or PNG and "
                "that its URL is publicly reachable."
            )

        # Images are usually ready immediately, but poll to be safe
        is_ready = await _poll_container_status(container_id, access_token)
        if not is_ready:
            raise IntegrationError("Instagram never finished processing the image.")

        publish_url = f"{GRAPH_BASE_URL}/{ig_user_id}/media_publish"
        publish_payload = {
            "creation_id": container_id,
            "access_token": access_token,
        }
        pub_res = await _graph_post(publish_url, publish_payload)
        post_id = pub_res.get("id")
        logger.info(f"✓ Instagram image posted: {post_id}")
        return post_id

    except Exception as e:
        _handle_ig_error("image", e)
        return None


async def _ig_post_carousel(
    ig_user_id: str,
    access_token: str,
    caption: str,
    image_urls: list[str],
) -> str | None:
    """Post a multi-image carousel to Instagram."""
    children_ids: list[str] = []

    # Step 1: Create individual carousel item containers
    for img_url in image_urls[:10]:  # Max 10 items per carousel
        item_url = f"{GRAPH_BASE_URL}/{ig_user_id}/media"
        item_payload = {
            "image_url": img_url,
            "is_carousel_item": "true",
            "access_token": access_token,
        }
        try:
            res = await _graph_post(item_url, item_payload)
            item_id = res.get("id")
            if item_id:
                children_ids.append(item_id)
        except Exception as e:
            logger.warning(f"Failed to create IG carousel item: {e}")

    if not children_ids:
        logger.error("No carousel items created for Instagram")
        return None

    # Step 2: Create the carousel container
    container_url = f"{GRAPH_BASE_URL}/{ig_user_id}/media"
    container_payload = {
        "media_type": "CAROUSEL",
        "children": ",".join(children_ids),
        "caption": caption,
        "access_token": access_token,
    }
    try:
        res = await _graph_post(container_url, container_payload)
        container_id = res.get("id")
        if not container_id:
            return None

        # Step 3: Poll until ready
        is_ready = await _poll_container_status(container_id, access_token)
        if not is_ready:
            return None

        # Step 4: Publish
        publish_url = f"{GRAPH_BASE_URL}/{ig_user_id}/media_publish"
        publish_payload = {
            "creation_id": container_id,
            "access_token": access_token,
        }
        pub_res = await _graph_post(publish_url, publish_payload)
        post_id = pub_res.get("id")
        logger.info(f"✓ Instagram carousel posted: {post_id} ({len(children_ids)} items)")
        return post_id

    except Exception as e:
        _handle_ig_error("carousel", e)
        raise IntegrationError(f"Carousel upload failed: {e}") from e


def _handle_ig_error(post_type: str, error: Exception) -> None:
    """
    Handle Instagram-specific errors gracefully.
    Catches "Unsupported post request" and similar Meta API errors
    without crashing the main thread.
    """
    error_msg = str(error)
    if "Unsupported post request" in error_msg:
        logger.warning(
            f"Instagram '{post_type}' post rejected: Unsupported post request. "
            f"This usually means the media format or account type doesn't support "
            f"this post type. Skipping gracefully."
        )
    else:
        logger.error(f"Instagram '{post_type}' post failed: {error_msg}")


# =============================================================================
# Post Update Functions (for editing existing posts)
# =============================================================================
async def update_facebook_post(workspace_id: str, post_id: str, new_message: str) -> bool:
    """Update the text/message of an existing Facebook post."""
    access_token, _ = await _get_fb_credentials(workspace_id)
    if not access_token:
        logger.warning("Facebook credentials missing — cannot update post")
        return False

    url = f"{GRAPH_BASE_URL}/{post_id}"
    payload = {
        "access_token": access_token,
        "message": new_message,
    }
    try:
        await _graph_post(url, payload)
        logger.info(f"✓ Facebook post updated: {post_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to update Facebook post {post_id}: {e}")
        return False


async def update_instagram_post(workspace_id: str, media_id: str, new_caption: str) -> bool:
    """Update the caption of an existing Instagram post."""
    access_token, _ = await _get_ig_credentials(workspace_id)
    if not access_token:
        logger.warning("Instagram credentials missing — cannot update post")
        return False

    url = f"{GRAPH_BASE_URL}/{media_id}"
    payload = {
        "access_token": access_token,
        "caption": new_caption,
    }
    try:
        await _graph_post(url, payload)
        logger.info(f"✓ Instagram post updated: {media_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to update Instagram post {media_id}: {e}")
        return False

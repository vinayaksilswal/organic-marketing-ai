"""
=============================================================================
Organic Marketing AI — Cloudinary Media Storage Service
=============================================================================
Handles uploading and retrieving media from Cloudinary with tenant isolation.
Supports upload from URL (for AI-generated videos/images), from bytes,
and from file-like objects.

Tenant Isolation:
  All media is stored under: tenants/{workspace_id}/{media_type}/

Dependencies:
  pip install cloudinary
=============================================================================
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Optional

import cloudinary
import cloudinary.uploader
import cloudinary.api
from loguru import logger

from config import settings


# =============================================================================
# Cloudinary Configuration (initialized once on import)
# =============================================================================
def _configure_cloudinary() -> bool:
    """Configure Cloudinary SDK with credentials from settings."""
    if not settings.cloudinary_cloud_name:
        logger.warning("CLOUDINARY_CLOUD_NAME not configured — media uploads disabled")
        return False

    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True,
    )
    return True


_cloudinary_ready = _configure_cloudinary()


# =============================================================================
# Core Upload Functions
# =============================================================================
async def upload_media_to_cloudinary(
    workspace_id: str,
    media_id: str,
    filename: str,
    source: str | bytes,
    resource_type: str = "auto",
    tags: list[str] | None = None,
) -> dict | None:
    """
    Upload a file to Cloudinary with tenant-partitioned folder structure.

    Args:
        workspace_id: The business profile / workspace ID for tenant isolation
        media_id: Unique media identifier
        filename: Original filename (used for display name)
        source: Either a public URL string or raw bytes to upload
        resource_type: 'image', 'video', 'raw', or 'auto' (auto-detect)
        tags: Optional list of tags for organization

    Returns:
        Dict with 'url', 'secure_url', 'public_id', 'resource_type', 'format',
        'width', 'height', 'duration' (for video), 'bytes' — or None on failure
    """
    if not _cloudinary_ready:
        logger.warning("Cloudinary not configured. Cannot upload media.")
        return None

    # Tenant-partitioned folder path
    folder = f"tenants/{workspace_id}/media"
    public_id = f"{folder}/{media_id}"

    upload_tags = tags or []
    upload_tags.append(f"workspace:{workspace_id}")

    try:
        # Run the synchronous Cloudinary SDK in a thread pool to avoid blocking
        result = await asyncio.to_thread(
            cloudinary.uploader.upload,
            source,
            public_id=public_id,
            resource_type=resource_type,
            folder=None,  # We embed folder in public_id
            tags=upload_tags,
            overwrite=True,
            invalidate=True,
            transformation=[
                {"quality": "auto", "fetch_format": "auto"}
            ] if resource_type == "image" else None,
        )

        logger.info(
            f"✓ Cloudinary upload success: {result.get('public_id')} "
            f"({result.get('bytes', 0)} bytes, {result.get('resource_type')})"
        )

        return {
            "url": result.get("url"),
            "secure_url": result.get("secure_url"),
            "public_id": result.get("public_id"),
            "resource_type": result.get("resource_type"),
            "format": result.get("format"),
            "width": result.get("width"),
            "height": result.get("height"),
            "duration": result.get("duration"),  # For videos
            "bytes": result.get("bytes"),
        }

    except Exception as e:
        logger.error(f"Cloudinary upload failed for {filename}: {e}")
        return None


async def upload_video_from_url(
    workspace_id: str,
    media_id: str,
    video_url: str,
    filename: str = "ai_video",
    tags: list[str] | None = None,
) -> dict | None:
    """
    Upload a video to Cloudinary from a public URL.
    Cloudinary will fetch and transcode the video automatically.
    """
    return await upload_media_to_cloudinary(
        workspace_id=workspace_id,
        media_id=media_id,
        filename=filename,
        source=video_url,
        resource_type="video",
        tags=tags,
    )


async def upload_image_from_url(
    workspace_id: str,
    media_id: str,
    image_url: str,
    filename: str = "ai_image",
    tags: list[str] | None = None,
) -> dict | None:
    """
    Upload an image to Cloudinary from a public URL.
    Cloudinary auto-optimizes with quality=auto and format=auto.
    """
    return await upload_media_to_cloudinary(
        workspace_id=workspace_id,
        media_id=media_id,
        filename=filename,
        source=image_url,
        resource_type="image",
        tags=tags,
    )


async def delete_media_from_cloudinary(public_id: str, resource_type: str = "image") -> bool:
    """Delete a media asset from Cloudinary by its public_id."""
    if not _cloudinary_ready:
        return False

    try:
        result = await asyncio.to_thread(
            cloudinary.uploader.destroy,
            public_id,
            resource_type=resource_type,
        )
        success = result.get("result") == "ok"
        if success:
            logger.info(f"✓ Cloudinary delete success: {public_id}")
        else:
            logger.warning(f"Cloudinary delete returned: {result}")
        return success
    except Exception as e:
        logger.error(f"Cloudinary delete failed for {public_id}: {e}")
        return False


def get_cloudinary_url(
    public_id: str,
    resource_type: str = "image",
    width: int | None = None,
    height: int | None = None,
    crop: str = "fill",
) -> str:
    """
    Generate an optimized Cloudinary delivery URL with optional transformations.
    """
    transformations = []
    if width or height:
        t = {"crop": crop}
        if width:
            t["width"] = width
        if height:
            t["height"] = height
        transformations.append(t)
    transformations.append({"quality": "auto", "fetch_format": "auto"})

    url, _ = cloudinary.utils.cloudinary_url(
        public_id,
        resource_type=resource_type,
        transformation=transformations,
        secure=True,
    )
    return url

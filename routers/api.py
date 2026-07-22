"""
=============================================================================
Organic Marketing AI — API Router (v1)
=============================================================================
Handles all REST API endpoints for:
  - Social Campaign CRUD (scoped to authenticated user)
  - Media upload & retrieval
  - AI Chatbot
  - Social media triggers & status

All endpoints use request.app.state.prisma (no standalone Prisma instances).
=============================================================================
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Response
from loguru import logger
from pydantic import BaseModel, Field

from auth import verify_credentials
from routers.auth import verify_user
from services.chat_agent import chat_with_agent


# =============================================================================
# User-Authenticated Router (for frontend dashboard)
# =============================================================================
router = APIRouter(
    prefix="/api/v1",
    tags=["API"],
    dependencies=[Depends(verify_user)],
)


# =============================================================================
# Request/Response Models
# =============================================================================
class StandardResponse(BaseModel):
    """Standard API response wrapper."""
    success: bool
    message: Optional[str] = None
    data: Optional[Any] = None


class ChatRequest(BaseModel):
    """Request model for the AI chatbot."""
    messages: List[Dict[str, Any]] = Field(
        ..., description="Conversation messages array"
    )


class CampaignCreate(BaseModel):
    baseCaption: str
    mediaUrl: str
    mediaType: str


class CampaignUpdate(BaseModel):
    isActive: Optional[bool] = None
    baseCaption: Optional[str] = None
    mediaUrl: Optional[str] = None
    mediaType: Optional[str] = None


# =============================================================================
# Upload Endpoints
# =============================================================================
import base64

@router.post("/upload-media", response_model=StandardResponse)
async def upload_media(
    request: Request,
    file: UploadFile = File(...),
    user_id: str = Depends(verify_user),
) -> StandardResponse:
    """Upload a video or image file to the database."""
    try:
        import asyncpg
        from config import settings

        mime_type = file.content_type or "application/octet-stream"
        file_content = await file.read()
        media_id = str(uuid.uuid4())

        conn = await asyncpg.connect(settings.database_url)
        try:
            await conn.execute(
                'INSERT INTO "Media" (id, "userId", filename, "mimeType", url, "createdAt") '
                'VALUES ($1, $2, $3, $4, $5, NOW())',
                media_id, user_id, file.filename or "upload", mime_type,
                f"/api/v1/media/{media_id}",
            )
        finally:
            await conn.close()

        url_suffix = "?type=video" if mime_type.startswith("video/") else ""
        base_url = str(request.base_url).rstrip("/")

        return StandardResponse(
            success=True,
            data={"url": f"{base_url}/api/v1/media/{media_id}{url_suffix}"},
        )
    except Exception as e:
        logger.error(f"Failed to upload media: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


# =============================================================================
# Public Router (no auth required — for media serving)
# =============================================================================
public_router = APIRouter(
    prefix="/api/v1",
    tags=["Public API"],
)


@public_router.get("/media/{media_id}")
async def get_media(media_id: str, request: Request):
    """Retrieve media from the database (PUBLIC)."""
    import asyncpg
    from config import settings
    from fastapi.responses import FileResponse

    cache_dir = "uploads/cache"
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f"{media_id}.bin")
    mime_path = os.path.join(cache_dir, f"{media_id}.mime")

    req_type = request.query_params.get("type")
    mime_type = "application/octet-stream"

    if os.path.exists(cache_path) and os.path.exists(mime_path):
        with open(mime_path, "r") as f:
            mime_type = f.read().strip()
    else:
        conn = await asyncpg.connect(settings.database_url)
        try:
            row = await conn.fetchrow(
                'SELECT "mimeType", data FROM "Media" WHERE id = $1',
                media_id,
            )
        finally:
            await conn.close()

        if not row:
            raise HTTPException(status_code=404, detail="Media not found")

        mime_type = row["mimeType"]
        data_bytes = row["data"]

        with open(cache_path, "wb") as f:
            f.write(data_bytes)
        with open(mime_path, "w") as f:
            f.write(mime_type)

    # Override mime type if requested
    if req_type:
        if req_type == "video" or req_type.endswith(".mp4"):
            mime_type = "video/mp4"
        elif req_type.endswith(".jpg") or req_type.endswith(".jpeg"):
            mime_type = "image/jpeg"
        elif req_type.endswith(".png"):
            mime_type = "image/png"

    return FileResponse(
        path=cache_path,
        media_type=mime_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


# =============================================================================
# Social Campaign Endpoints (User-Scoped)
# =============================================================================
@router.post("/campaigns", response_model=StandardResponse)
async def create_campaign(
    data: CampaignCreate,
    request: Request,
    user_id: str = Depends(verify_user),
) -> StandardResponse:
    """Create a new social media campaign for the authenticated user."""
    prisma = request.app.state.prisma
    try:
        campaign = await prisma.socialcampaign.create(
            data={
                "userId": user_id,
                "baseCaption": data.baseCaption,
                "mediaUrl": data.mediaUrl,
                "mediaType": data.mediaType,
            }
        )
        return StandardResponse(success=True, data=campaign.model_dump())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/campaigns", response_model=StandardResponse)
async def get_campaigns(
    request: Request,
    user_id: str = Depends(verify_user),
) -> StandardResponse:
    """Get all social media campaigns for the authenticated user."""
    prisma = request.app.state.prisma
    try:
        campaigns = await prisma.socialcampaign.find_many(
            where={"userId": user_id},
            order={"createdAt": "desc"},
        )
        data = [c.model_dump() for c in campaigns]
        return StandardResponse(success=True, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/campaigns/{cid}", response_model=StandardResponse)
async def update_campaign(
    cid: str,
    data: CampaignUpdate,
    request: Request,
    user_id: str = Depends(verify_user),
) -> StandardResponse:
    """Update a social media campaign (only if owned by authenticated user)."""
    prisma = request.app.state.prisma
    try:
        # Verify ownership
        existing = await prisma.socialcampaign.find_first(
            where={"id": cid, "userId": user_id}
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Campaign not found")

        update_data = {}
        if data.isActive is not None:
            update_data["isActive"] = data.isActive
        if data.baseCaption is not None:
            update_data["baseCaption"] = data.baseCaption
        if data.mediaUrl is not None:
            update_data["mediaUrl"] = data.mediaUrl
        if data.mediaType is not None:
            update_data["mediaType"] = data.mediaType

        updated = await prisma.socialcampaign.update(
            where={"id": cid},
            data=update_data,
        )
        return StandardResponse(success=True, data=updated.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/campaigns/{cid}", response_model=StandardResponse)
async def delete_campaign(
    cid: str,
    request: Request,
    user_id: str = Depends(verify_user),
) -> StandardResponse:
    """Delete a social media campaign (only if owned by authenticated user)."""
    prisma = request.app.state.prisma
    try:
        existing = await prisma.socialcampaign.find_first(
            where={"id": cid, "userId": user_id}
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Campaign not found")

        await prisma.socialcampaign.delete(where={"id": cid})
        return StandardResponse(success=True, message="Campaign deleted")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Chatbot Endpoint
# =============================================================================
@router.post("/chat", response_model=StandardResponse)
async def chat_api(req: ChatRequest, request: Request) -> StandardResponse:
    """
    AI Chatbot with LLM tool calling.
    Accepts a conversation history and returns the assistant's response.
    """
    prisma = request.app.state.prisma
    response_message = await chat_with_agent(req.messages, prisma)
    return StandardResponse(success=True, data=response_message)


# =============================================================================
# Social Media — Manual Trigger & Status Endpoints
# =============================================================================
@router.post("/social/trigger", response_model=StandardResponse)
async def trigger_social_post(
    request: Request,
    user_id: str = Depends(verify_user),
) -> StandardResponse:
    """Manually trigger one full marketing loop iteration."""
    import asyncio
    from services.scheduler import execute_marketing_loop

    logger.info(f"[MANUAL TRIGGER] User {user_id} triggered marketing loop")
    asyncio.create_task(execute_marketing_loop())
    return StandardResponse(
        success=True,
        message="Marketing loop triggered. Check recent posts for results.",
    )


@router.get("/social/recent-posts", response_model=StandardResponse)
async def get_recent_social_posts(
    request: Request,
    user_id: str = Depends(verify_user),
) -> StandardResponse:
    """Returns the 10 most recent social post records for the authenticated user."""
    prisma = request.app.state.prisma
    try:
        posts = await prisma.socialpost.find_many(
            where={"userId": user_id},
            order={"createdAt": "desc"},
            take=10,
            include={"campaign": True},
        )
        data = [
            {
                "id": p.id,
                "campaignId": p.campaignId,
                "platform": p.platform,
                "type": p.type,
                "status": p.status,
                "caption": (p.caption or "")[:120] + ("..." if len(p.caption or "") > 120 else ""),
                "fbPostId": p.fbPostId,
                "igPostId": p.igPostId,
                "postedAt": p.postedAt.isoformat() if p.postedAt else None,
                "scheduledAt": p.scheduledAt.isoformat() if p.scheduledAt else None,
                "errorLog": p.errorLog,
            }
            for p in posts
        ]
        return StandardResponse(success=True, data=data)
    except Exception as e:
        logger.error(f"Failed to fetch recent social posts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/social/scheduler-status", response_model=StandardResponse)
async def get_scheduler_status(
    request: Request,
    user_id: str = Depends(verify_user),
) -> StandardResponse:
    """Returns the scheduler status and auto-approve setting for the user."""
    prisma = request.app.state.prisma
    scheduler = request.app.state.scheduler

    next_run = None
    try:
        if scheduler:
            job = scheduler.get_job("marketing_loop")
            if job and job.next_run_time:
                next_run = job.next_run_time.isoformat()
    except Exception:
        pass

    state = await prisma.marketingstate.find_unique(where={"userId": user_id})
    return StandardResponse(
        success=True,
        data={
            "schedulerRunning": scheduler.running if scheduler else False,
            "nextRunAt": next_run,
            "autoApprove": state.autoApprove if state else False,
            "lastSocialIdx": state.lastSocialIdx if state else 0,
            "lastEmailIdx": state.lastEmailIdx if state else 0,
        },
    )

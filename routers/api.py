"""
=============================================================================
Organic Marketing AI — API Router (v1)
=============================================================================
Handles REST API endpoints using SQLAlchemy 2.0 Async ORM:
  - Media Upload & Public Retrieval
  - User-Scoped Social Campaigns CRUD
  - AI Chatbot Command Center
  - Social Media Triggers & Status
=============================================================================
"""

from __future__ import annotations

import os
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import select, delete

from database import (
    AsyncSessionLocal,
    SocialCampaign,
    SocialPost,
    MarketingState,
    Media,
)
from routers.auth import verify_user
from services.chat_agent import chat_with_agent


# =============================================================================
# Authenticated Router
# =============================================================================
router = APIRouter(
    prefix="/api/v1",
    tags=["API"],
    dependencies=[Depends(verify_user)],
)


# =============================================================================
# Request / Response Models
# =============================================================================
class StandardResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    data: Optional[Any] = None


class ChatRequest(BaseModel):
    messages: List[Dict[str, Any]] = Field(..., description="Conversation messages array")


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
# Upload Media Endpoint
# =============================================================================
@router.post("/upload-media", response_model=StandardResponse)
async def upload_media(
    request: Request,
    file: UploadFile = File(...),
    user_id: str = Depends(verify_user),
) -> StandardResponse:
    """Upload a video or image file to the database."""
    try:
        mime_type = file.content_type or "application/octet-stream"
        file_content = await file.read()
        media_id = str(uuid.uuid4())

        async with AsyncSessionLocal() as session:
            media = Media(
                id=media_id,
                userId=user_id,
                filename=file.filename or "upload",
                mimeType=mime_type,
                url=f"/api/v1/media/{media_id}",
                data=file_content,
            )
            session.add(media)
            await session.commit()

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
# Public Router (Media Retrieval)
# =============================================================================
public_router = APIRouter(
    prefix="/api/v1",
    tags=["Public API"],
)


@public_router.get("/media/{media_id}")
async def get_media(media_id: str, request: Request):
    """Retrieve binary media from the database (PUBLIC)."""
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
        async with AsyncSessionLocal() as session:
            stmt = select(Media).where(Media.id == media_id)
            res = await session.execute(stmt)
            row = res.scalar_one_or_none()

            if not row:
                raise HTTPException(status_code=404, detail="Media not found")

            mime_type = row.mimeType
            data_bytes = row.data or b""

            with open(cache_path, "wb") as f:
                f.write(data_bytes)
            with open(mime_path, "w") as f:
                f.write(mime_type)

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
    """Create a new social campaign for the user."""
    async with AsyncSessionLocal() as session:
        campaign = SocialCampaign(
            userId=user_id,
            baseCaption=data.baseCaption,
            mediaUrl=data.mediaUrl,
            mediaType=data.mediaType,
        )
        session.add(campaign)
        await session.commit()
        await session.refresh(campaign)

        return StandardResponse(
            success=True,
            data={
                "id": campaign.id,
                "userId": campaign.userId,
                "baseCaption": campaign.baseCaption,
                "mediaUrl": campaign.mediaUrl,
                "mediaType": campaign.mediaType,
                "isActive": campaign.isActive,
                "createdAt": campaign.createdAt.isoformat() if campaign.createdAt else None,
            },
        )


@router.get("/campaigns", response_model=StandardResponse)
async def get_campaigns(
    request: Request,
    user_id: str = Depends(verify_user),
) -> StandardResponse:
    """Get all social campaigns for the authenticated user."""
    async with AsyncSessionLocal() as session:
        stmt = (
            select(SocialCampaign)
            .where(SocialCampaign.userId == user_id)
            .order_by(SocialCampaign.createdAt.desc())
        )
        res = await session.execute(stmt)
        campaigns = res.scalars().all()

        data = [
            {
                "id": c.id,
                "userId": c.userId,
                "baseCaption": c.baseCaption,
                "mediaUrl": c.mediaUrl,
                "mediaType": c.mediaType,
                "isActive": c.isActive,
                "createdAt": c.createdAt.isoformat() if c.createdAt else None,
            }
            for c in campaigns
        ]
        return StandardResponse(success=True, data=data)


@router.put("/campaigns/{cid}", response_model=StandardResponse)
async def update_campaign(
    cid: str,
    data: CampaignUpdate,
    request: Request,
    user_id: str = Depends(verify_user),
) -> StandardResponse:
    """Update a social campaign."""
    async with AsyncSessionLocal() as session:
        stmt = select(SocialCampaign).where(
            SocialCampaign.id == cid, SocialCampaign.userId == user_id
        )
        res = await session.execute(stmt)
        campaign = res.scalar_one_or_none()

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        if data.isActive is not None:
            campaign.isActive = data.isActive
        if data.baseCaption is not None:
            campaign.baseCaption = data.baseCaption
        if data.mediaUrl is not None:
            campaign.mediaUrl = data.mediaUrl
        if data.mediaType is not None:
            campaign.mediaType = data.mediaType

        await session.commit()
        await session.refresh(campaign)

        return StandardResponse(
            success=True,
            data={
                "id": campaign.id,
                "baseCaption": campaign.baseCaption,
                "mediaUrl": campaign.mediaUrl,
                "mediaType": campaign.mediaType,
                "isActive": campaign.isActive,
            },
        )


@router.delete("/campaigns/{cid}", response_model=StandardResponse)
async def delete_campaign(
    cid: str,
    request: Request,
    user_id: str = Depends(verify_user),
) -> StandardResponse:
    """Delete a social campaign."""
    async with AsyncSessionLocal() as session:
        stmt = select(SocialCampaign).where(
            SocialCampaign.id == cid, SocialCampaign.userId == user_id
        )
        res = await session.execute(stmt)
        campaign = res.scalar_one_or_none()

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        await session.delete(campaign)
        await session.commit()
        return StandardResponse(success=True, message="Campaign deleted")


# =============================================================================
# Chatbot & Triggers
# =============================================================================
@router.post("/chat", response_model=StandardResponse)
async def chat_api(req: ChatRequest, request: Request) -> StandardResponse:
    """AI Chatbot with LLM function calling."""
    response_message = await chat_with_agent(req.messages)
    return StandardResponse(success=True, data=response_message)


@router.post("/social/trigger", response_model=StandardResponse)
async def trigger_social_post(
    request: Request,
    user_id: str = Depends(verify_user),
) -> StandardResponse:
    """Manually trigger one marketing loop iteration."""
    import asyncio
    from services.scheduler import execute_marketing_loop

    logger.info(f"[MANUAL TRIGGER] User {user_id} triggered marketing loop")
    asyncio.create_task(execute_marketing_loop(user_id=user_id))
    return StandardResponse(
        success=True,
        message="Marketing loop triggered. Check recent posts for results.",
    )


@router.get("/social/recent-posts", response_model=StandardResponse)
async def get_recent_social_posts(
    request: Request,
    user_id: str = Depends(verify_user),
) -> StandardResponse:
    """Returns the 10 most recent social posts for the user."""
    async with AsyncSessionLocal() as session:
        stmt = (
            select(SocialPost)
            .where(SocialPost.userId == user_id)
            .order_by(SocialPost.createdAt.desc())
            .limit(10)
        )
        res = await session.execute(stmt)
        posts = res.scalars().all()

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


@router.get("/social/scheduler-status", response_model=StandardResponse)
async def get_scheduler_status(
    request: Request,
    user_id: str = Depends(verify_user),
) -> StandardResponse:
    """Returns scheduler running status and user autoApprove setting."""
    scheduler = getattr(request.app.state, "scheduler", None)
    next_run = None
    try:
        if scheduler:
            job = scheduler.get_job("marketing_loop")
            if job and job.next_run_time:
                next_run = job.next_run_time.isoformat()
    except Exception:
        pass

    async with AsyncSessionLocal() as session:
        stmt = select(MarketingState).where(MarketingState.userId == user_id)
        res = await session.execute(stmt)
        state = res.scalar_one_or_none()

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

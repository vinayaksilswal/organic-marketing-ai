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
from services.storage_service import upload_media_to_s3
from fastapi.responses import FileResponse
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import select, delete

from database import (
    AsyncSessionLocal,
    BusinessProfile,
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
    """Upload a video or image file to the database and register in Media catalog."""
    try:
        mime_type = file.content_type or "application/octet-stream"
        file_content = await file.read()
        media_id = str(uuid.uuid4())

        workspace_id = request.headers.get("x-workspace-id") or request.headers.get("X-Workspace-Id")

        async with AsyncSessionLocal() as session:
            if not workspace_id:
                bp_stmt = select(BusinessProfile).where(BusinessProfile.userId == user_id)
                bp = (await session.execute(bp_stmt)).scalars().first()
                if bp:
                    workspace_id = bp.id

            # Attempt to upload to S3
            s3_url = await upload_media_to_s3(
                workspace_id=workspace_id or "default",
                media_id=media_id,
                filename=file.filename or "upload",
                content=file_content,
                mime_type=mime_type
            )

            # Fallback to local API URL if S3 is not configured
            final_url = s3_url if s3_url else f"/api/v1/media/{media_id}"
            
            # If uploaded to S3, we don't necessarily need to save data bytes in DB, 
            # but we keep it for fallback/local parity.
            media = Media(
                id=media_id,
                userId=user_id,
                businessProfileId=workspace_id,
                filename=file.filename or "upload",
                mimeType=mime_type,
                url=final_url,
                data=file_content if not s3_url else None,
            )
            session.add(media)
            await session.commit()

        url_suffix = "?type=video" if mime_type.startswith("video/") else ""
        base_url = str(request.base_url).rstrip("/")
        
        # Format the URL appropriately based on if it's external (S3) or internal
        if final_url.startswith("http"):
            full_url = final_url
        else:
            full_url = f"{base_url}{final_url}{url_suffix}"

        return StandardResponse(
            success=True,
            data={"url": full_url},
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

    import mimetypes
    from fastapi import Response
    
    file_size = os.path.getsize(cache_path)
    range_header = request.headers.get("range")
    
    headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "public, max-age=86400",
        "Content-Type": mime_type,
    }
    
    if range_header:
        # e.g. "bytes=0-" or "bytes=0-100"
        range_str = range_header.replace("bytes=", "")
        start_str, end_str = range_str.split("-")
        
        start = int(start_str) if start_str else 0
        end = int(end_str) if end_str else file_size - 1
        
        # clamp the end value
        end = min(end, file_size - 1)
        length = end - start + 1
        
        headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        headers["Content-Length"] = str(length)
        
        with open(cache_path, "rb") as f:
            f.seek(start)
            data = f.read(length)
            
        return Response(content=data, status_code=206, headers=headers, media_type=mime_type)
        
    else:
        headers["Content-Length"] = str(file_size)
        with open(cache_path, "rb") as f:
            data = f.read()
        return Response(content=data, status_code=200, headers=headers, media_type=mime_type)



# =============================================================================
# Social Campaign Endpoints (User-Scoped)
# =============================================================================
@router.post("/campaigns", response_model=StandardResponse)
async def create_campaign(
    data: CampaignCreate,
    request: Request,
    user_id: str = Depends(verify_user),
) -> StandardResponse:
    """Create a new social campaign for the user and register media in catalog if present."""
    workspace_id = request.headers.get("x-workspace-id") or request.headers.get("X-Workspace-Id")
    async with AsyncSessionLocal() as session:
        if not workspace_id:
            bp_stmt = select(BusinessProfile).where(BusinessProfile.userId == user_id)
            bp = (await session.execute(bp_stmt)).scalars().first()
            if bp:
                workspace_id = bp.id

        campaign = SocialCampaign(
            userId=user_id,
            businessProfileId=workspace_id,
            baseCaption=data.baseCaption,
            mediaUrl=data.mediaUrl,
            mediaType=data.mediaType,
        )
        session.add(campaign)

        # Register campaign media in Media catalog if provided and not already present
        if data.mediaUrl:
            existing_media = (await session.execute(
                select(Media).where(Media.url == data.mediaUrl)
            )).scalars().first()
            if not existing_media:
                media_id = str(uuid.uuid4())
                fname = f"Campaign_{data.mediaType}_{media_id[:8]}"
                mtype = "video/mp4" if data.mediaType == "video" else "image/jpeg"
                session.add(Media(
                    id=media_id,
                    userId=user_id,
                    businessProfileId=workspace_id,
                    filename=fname,
                    mimeType=mtype,
                    url=data.mediaUrl,
                ))

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

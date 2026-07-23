"""
=============================================================================
Organic Marketing AI — Creative API Router
=============================================================================
Endpoints for managing AI-generated creatives:
  - Generate new creatives on demand
  - List pending/approved creatives
  - Approve/reject individual creatives
  - Generate AI images via Pollinations
  - Get brand analysis status
=============================================================================
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select, and_

from database import (
    AsyncSessionLocal,
    BusinessProfile,
    SocialCampaign,
    Media,
    MarketingState,
)
from routers.auth import verify_user
from services.creative_service import (
    generate_brand_context,
    generate_starter_creatives,
    get_pollinations_image_url,
    auto_populate_workspace,
)


router = APIRouter(
    prefix="/api/v1/creatives",
    tags=["Creatives"],
    dependencies=[Depends(verify_user)],
)


class GenerateRequest(BaseModel):
    topic: Optional[str] = None
    count: int = 3


class VideoCampaignRequest(BaseModel):
    product_name: str
    product_url: str
    image_url: str
    goal: str = "conversion"



class ImageGenerateRequest(BaseModel):
    prompt: str
    width: int = 1080
    height: int = 1080


@router.get("/brand-status")
async def get_brand_analysis_status(
    request: Request,
    user_id: str = Depends(verify_user),
) -> dict[str, Any]:
    """Check if brand analysis is complete for the active workspace."""
    workspace_id = request.headers.get("x-workspace-id") or request.headers.get("X-Workspace-Id")

    async with AsyncSessionLocal() as session:
        if workspace_id:
            profile = await session.get(BusinessProfile, workspace_id)
        else:
            stmt = select(BusinessProfile).where(BusinessProfile.userId == user_id)
            profile = (await session.execute(stmt)).scalars().first()

        if not profile:
            return {"complete": False, "message": "No workspace found"}

        return {
            "complete": profile.brandAnalysisComplete,
            "industry": profile.industry,
            "targetAudience": profile.targetAudience,
            "toneOfVoice": profile.toneOfVoice,
            "contentPillars": profile.contentPillars,
            "suggestedHashtags": profile.suggestedHashtags,
            "brandColors": profile.brandColors,
        }

@router.post("/generate-video-campaign")
async def generate_video_campaign(
    data: VideoCampaignRequest,
    user_id: str = Depends(verify_user),
) -> dict[str, Any]:
    """Generate a video campaign using the automated pipeline."""
    from services.video_pipeline_service import execute_video_pipeline
    
    result = await execute_video_pipeline(
        product_name=data.product_name,
        product_url=data.product_url,
        image_url=data.image_url,
        goal=data.goal
    )
    return result

@router.post("/generate")
async def generate_creatives(
    data: GenerateRequest,
    request: Request,
    user_id: str = Depends(verify_user),
) -> dict[str, Any]:
    """Generate new AI creatives for the active workspace."""
    workspace_id = request.headers.get("x-workspace-id") or request.headers.get("X-Workspace-Id")

    async with AsyncSessionLocal() as session:
        if workspace_id:
            profile = await session.get(BusinessProfile, workspace_id)
        else:
            stmt = select(BusinessProfile).where(BusinessProfile.userId == user_id)
            profile = (await session.execute(stmt)).scalars().first()
        if not profile:
            raise HTTPException(status_code=404, detail="No workspace found")

        # If brand analysis not done yet, run it first
        if not profile.brandAnalysisComplete:
            brand_ctx = await generate_brand_context(profile)
            profile.industry = brand_ctx["industry"]
            profile.targetAudience = brand_ctx["targetAudience"]
            profile.toneOfVoice = brand_ctx["toneOfVoice"]
            profile.contentPillars = brand_ctx["contentPillars"]
            profile.suggestedHashtags = brand_ctx["suggestedHashtags"]
            profile.brandColors = brand_ctx["brandColors"]
            profile.brandAnalysisComplete = True
            await session.commit()
            await session.refresh(profile)

        creatives = await generate_starter_creatives(profile)

        # Create campaigns as DRAFT
        created = []
        import uuid
        for creative in creatives[:data.count]:
            img_prompt = f"Modern social media graphic for {profile.name}, {profile.businessModel}, topic: {creative['topic']}, professional clean design"
            img_url = get_pollinations_image_url(img_prompt, 1080, 1080)

            # Register in media
            media_id = str(uuid.uuid4())
            media = Media(
                id=media_id,
                userId=user_id,
                businessProfileId=workspace_id or profile.id,
                filename=f"AI_Render_{creative['topic'].replace(' ', '_')}_{media_id[:8]}.png",
                mimeType="image/png",
                url=img_url,
                tags=[creative["topic"], "ai-generated"],
                aiGenerated=True,
            )
            session.add(media)

            campaign = SocialCampaign(
                userId=user_id,
                businessProfileId=workspace_id or profile.id,
                baseCaption=creative["caption"],
                mediaUrl=img_url,
                mediaType="image",
                isActive=True,
            )
            session.add(campaign)
            await session.flush()

            created.append({
                "id": campaign.id,
                "caption": creative["caption"],
                "topic": creative["topic"],
                "imageUrl": img_url,
                "platform": creative.get("platform", "BOTH"),
            })

        await session.commit()

        return {
            "success": True,
            "count": len(created),
            "creatives": created,
        }


@router.post("/generate-image")
async def generate_ai_image(
    data: ImageGenerateRequest,
    request: Request,
    user_id: str = Depends(verify_user),
) -> dict[str, Any]:
    """Generate a single AI image via Pollinations.ai."""
    url = get_pollinations_image_url(data.prompt, data.width, data.height)
    return {
        "success": True,
        "url": url,
        "prompt": data.prompt,
    }


@router.get("/queue")
async def get_creative_queue(
    request: Request,
    user_id: str = Depends(verify_user),
) -> dict[str, Any]:
    """List all campaigns (creatives) for the workspace, grouped by status."""
    workspace_id = request.headers.get("x-workspace-id") or request.headers.get("X-Workspace-Id")

    async with AsyncSessionLocal() as session:
        if workspace_id:
            stmt = select(SocialCampaign).where(
                SocialCampaign.businessProfileId == workspace_id
            ).order_by(SocialCampaign.createdAt.desc())
        else:
            stmt = select(SocialCampaign).where(
                SocialCampaign.userId == user_id
            ).order_by(SocialCampaign.createdAt.desc())

        campaigns = (await session.execute(stmt)).scalars().all()

        return {
            "success": True,
            "data": [
                {
                    "id": c.id,
                    "caption": c.baseCaption,
                    "mediaUrl": c.mediaUrl,
                    "mediaType": c.mediaType,
                    "isActive": c.isActive,
                    "createdAt": c.createdAt.isoformat() if c.createdAt else None,
                }
                for c in campaigns
            ],
        }


@router.post("/{creative_id}/approve")
async def approve_creative(
    creative_id: str,
    request: Request,
    user_id: str = Depends(verify_user),
) -> dict[str, Any]:
    """Approve a creative (activate the campaign)."""
    async with AsyncSessionLocal() as session:
        campaign = await session.get(SocialCampaign, creative_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Creative not found")
        campaign.isActive = True
        await session.commit()
        return {"success": True, "message": "Creative approved"}


@router.post("/{creative_id}/reject")
async def reject_creative(
    creative_id: str,
    request: Request,
    user_id: str = Depends(verify_user),
) -> dict[str, Any]:
    """Reject a creative (deactivate the campaign)."""
    async with AsyncSessionLocal() as session:
        campaign = await session.get(SocialCampaign, creative_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Creative not found")
        campaign.isActive = False
        await session.commit()
        return {"success": True, "message": "Creative rejected"}


@router.post("/re-analyze")
async def re_analyze_brand(
    request: Request,
    user_id: str = Depends(verify_user),
) -> dict[str, Any]:
    """Re-run brand analysis for the workspace."""
    workspace_id = request.headers.get("x-workspace-id") or request.headers.get("X-Workspace-Id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="No workspace selected")

    async with AsyncSessionLocal() as session:
        profile = await session.get(BusinessProfile, workspace_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Workspace not found")

        brand_ctx = await generate_brand_context(profile)
        profile.industry = brand_ctx["industry"]
        profile.targetAudience = brand_ctx["targetAudience"]
        profile.toneOfVoice = brand_ctx["toneOfVoice"]
        profile.contentPillars = brand_ctx["contentPillars"]
        profile.suggestedHashtags = brand_ctx["suggestedHashtags"]
        profile.brandColors = brand_ctx["brandColors"]
        profile.brandAnalysisComplete = True
        await session.commit()

        return {"success": True, "brandContext": brand_ctx}


class CreativeSettingsUpdate(BaseModel):
    creativeGenerationIntervalHours: Optional[int] = None
    autoGenerateCreatives: Optional[bool] = None


@router.get("/settings")
async def get_creative_settings(
    request: Request,
    user_id: str = Depends(verify_user),
) -> dict[str, Any]:
    """Get creative generation scheduler settings for active workspace."""
    workspace_id = request.headers.get("x-workspace-id") or request.headers.get("X-Workspace-Id")
    async with AsyncSessionLocal() as session:
        if workspace_id:
            profile = await session.get(BusinessProfile, workspace_id)
        else:
            stmt = select(BusinessProfile).where(BusinessProfile.userId == user_id)
            profile = (await session.execute(stmt)).scalars().first()

        if not profile:
            return {
                "creativeGenerationIntervalHours": 2,
                "autoGenerateCreatives": True,
            }

        return {
            "creativeGenerationIntervalHours": getattr(profile, "creativeGenerationIntervalHours", 2),
            "autoGenerateCreatives": getattr(profile, "autoGenerateCreatives", True),
        }


@router.post("/settings")
async def update_creative_settings(
    data: CreativeSettingsUpdate,
    request: Request,
    user_id: str = Depends(verify_user),
) -> dict[str, Any]:
    """Update creative generation interval and auto-generation toggle."""
    workspace_id = request.headers.get("x-workspace-id") or request.headers.get("X-Workspace-Id")
    async with AsyncSessionLocal() as session:
        if workspace_id:
            profile = await session.get(BusinessProfile, workspace_id)
        else:
            stmt = select(BusinessProfile).where(BusinessProfile.userId == user_id)
            profile = (await session.execute(stmt)).scalars().first()

        if not profile:
            raise HTTPException(status_code=404, detail="Workspace not found")

        if data.creativeGenerationIntervalHours is not None:
            profile.creativeGenerationIntervalHours = max(1, data.creativeGenerationIntervalHours)
        if data.autoGenerateCreatives is not None:
            profile.autoGenerateCreatives = data.autoGenerateCreatives

        await session.commit()
        return {
            "success": True,
            "creativeGenerationIntervalHours": profile.creativeGenerationIntervalHours,
            "autoGenerateCreatives": profile.autoGenerateCreatives,
        }


@router.post("/auto-generate-now")
async def trigger_auto_generation(
    request: Request,
    user_id: str = Depends(verify_user),
) -> dict[str, Any]:
    """Manually trigger immediate batch creative generation for active workspace."""
    workspace_id = request.headers.get("x-workspace-id") or request.headers.get("X-Workspace-Id")
    if not workspace_id:
        async with AsyncSessionLocal() as session:
            stmt = select(BusinessProfile).where(BusinessProfile.userId == user_id)
            profile = (await session.execute(stmt)).scalars().first()
            if profile:
                workspace_id = profile.id

    if not workspace_id:
        raise HTTPException(status_code=404, detail="No active workspace found")

    from services.creative_service import auto_generate_creative_batch
    res = await auto_generate_creative_batch(workspace_id, count=3)
    return res


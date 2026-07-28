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

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select, and_

from database import (
    AsyncSessionLocal,
    BusinessProfile,
    SocialCampaign,
    Media,
    MarketingState,
    Product,
    VideoApiConfig,
)
from routers.auth import verify_user
from services.crypto_service import decrypt_token
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
    product_url: Optional[str] = None
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
    request: Request,
    user_id: str = Depends(verify_user),
) -> dict[str, Any]:
    """Generate a video campaign using the automated pipeline."""
    from services.video_pipeline_service import execute_video_pipeline
    
    workspace_id = request.headers.get("x-workspace-id") or request.headers.get("X-Workspace-Id")
    async with AsyncSessionLocal() as session:
        if workspace_id:
            profile = await session.get(BusinessProfile, workspace_id)
        else:
            stmt = select(BusinessProfile).where(BusinessProfile.userId == user_id)
            profile = (await session.execute(stmt)).scalars().first()
        if not profile:
            raise HTTPException(status_code=404, detail="No workspace found")

    
    result = await execute_video_pipeline(
        product_name=data.product_name,
        product_url=data.product_url,
        image_url=data.image_url,
        goal=data.goal,
        profile=profile
    )

    # Persist the generated prompt into the workspace media library so the user
    # can find it later next to the asset it describes.
    veo_prompt = result.get("veo_prompt")
    if veo_prompt:
        try:
            async with AsyncSessionLocal() as session:
                session.add(Media(
                    userId=user_id,
                    businessProfileId=profile.id,
                    filename=f"Video prompt — {data.product_name}",
                    mimeType="text/plain",
                    url=data.image_url or "",
                    tags=[data.product_name, "video-prompt", "ai-generated"],
                    aiGenerated=True,
                    prompt=veo_prompt,
                    promptType="video",
                ))
                await session.commit()
        except Exception:
            logger.exception("Failed to save video prompt to media library")

    return result

class AutoVideoRequest(BaseModel):
    product_id: Optional[str] = None   # optional; e-commerce workspaces only
    goal: str = "conversion"
    render: bool = True                # attempt a render if a key is configured


@router.post("/auto-video")
async def auto_video(
    data: AutoVideoRequest,
    request: Request,
    user_id: str = Depends(verify_user),
) -> dict[str, Any]:
    """One-click video prompt for the active business.

    Derives everything from the workspace's own brand profile — no manual form.
    Picks a product when the workspace has a catalog, otherwise pitches the
    business itself. Always saves the prompt to the media library; renders a
    video too when a json2video key is configured for the workspace.
    """
    from services.video_pipeline_service import execute_video_pipeline

    workspace_id = request.headers.get("x-workspace-id") or request.headers.get("X-Workspace-Id")

    async with AsyncSessionLocal() as session:
        if workspace_id:
            profile = await session.get(BusinessProfile, workspace_id)
            if profile and profile.userId != user_id:
                raise HTTPException(status_code=403, detail="That workspace is not yours")
        else:
            profile = (await session.execute(
                select(BusinessProfile).where(BusinessProfile.userId == user_id)
            )).scalars().first()
        if not profile:
            raise HTTPException(status_code=404, detail="Add a business first, then generate a video.")

        # Choose the subject: an explicit product, else any product in the
        # catalog, else the business itself.
        product = None
        if data.product_id:
            product = await session.get(Product, data.product_id)
            if product and product.businessProfileId != profile.id:
                raise HTTPException(status_code=403, detail="That product belongs to another workspace")
        if not product:
            product = (await session.execute(
                select(Product).where(Product.businessProfileId == profile.id).limit(1)
            )).scalars().first()

        if product:
            subject_name = product.title
            subject_url = product.url or profile.websiteUrl
            subject_image = product.imageUrl or profile.logoUrl or ""
        else:
            subject_name = profile.name
            subject_url = profile.websiteUrl
            subject_image = profile.logoUrl or ""

        video_cfg = (await session.execute(
            select(VideoApiConfig).where(and_(
                VideoApiConfig.userId == user_id,
                VideoApiConfig.businessProfileId == profile.id,
            ))
        )).scalars().first()

        profile_id, profile_name = profile.id, profile.name

    result = await execute_video_pipeline(
        product_name=subject_name,
        product_url=subject_url,
        image_url=subject_image,
        goal=data.goal,
        profile=profile,
    )

    veo_prompt = result.get("veo_prompt")
    if not veo_prompt:
        raise HTTPException(status_code=502, detail="The AI did not return a usable prompt. Please try again.")

    media_id = None
    async with AsyncSessionLocal() as session:
        media = Media(
            userId=user_id,
            businessProfileId=profile_id,
            filename=f"Video prompt — {subject_name}",
            mimeType="text/plain",
            url=subject_image or "",
            tags=[subject_name, "video-prompt", "ai-generated"],
            aiGenerated=True,
            prompt=veo_prompt,
            promptType="video",
        )
        session.add(media)
        await session.commit()
        await session.refresh(media)
        media_id = media.id

    # Render only if the workspace actually has a key. Absence is a normal
    # state, not an error — the prompt is still the deliverable.
    render_status = "skipped"
    render_detail = "No video API key configured for this business."
    api_key = None
    if data.render and video_cfg and video_cfg.apiKey:
        try:
            api_key = decrypt_token(video_cfg.apiKey)
        except Exception:
            logger.warning(f"Could not decrypt video API key for workspace {profile_id}")
            api_key = None

    if api_key:
        try:
            payload = {
                "resolution": "instagram-story",
                "quality": "high",
                "scenes": [{
                    "elements": (
                        [{"type": "image", "src": subject_image, "duration": 8}] if subject_image else []
                    ) + [{
                        "type": "text",
                        "text": subject_name,
                        "duration": 8,
                        "settings": {"font-size": "64px", "font-family": "Poppins"},
                    }],
                }],
            }
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    "https://api.json2video.com/v2/movies",
                    json=payload,
                    headers={"x-api-key": api_key, "Content-Type": "application/json"},
                )
            if resp.status_code < 300:
                body = resp.json()
                render_status = "queued"
                render_detail = body.get("project") or "Render queued with json2video."
            else:
                render_status = "failed"
                render_detail = f"json2video returned {resp.status_code}."
                logger.warning(f"json2video render failed for workspace {profile_id}: {resp.text[:200]}")
        except Exception as e:
            render_status = "failed"
            render_detail = "Could not reach the video service."
            logger.exception(f"json2video render error for workspace {profile_id}")

    return {
        "status": "success",
        "business": profile_name,
        "subject": subject_name,
        "usedProduct": bool(product),
        "veo_prompt": veo_prompt,
        "intelligence": result.get("intelligence"),
        "creative_strategy": result.get("creative_strategy"),
        "mediaId": media_id,
        "render": {"status": render_status, "detail": render_detail},
    }


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

from fastapi import Form
@router.put("/{creative_id}")
async def edit_creative(
    creative_id: str,
    request: Request,
    caption: str = Form(None),
    media_url: str = Form(None),
    user_id: str = Depends(verify_user),
) -> dict[str, Any]:
    """Edit a creative's caption and media."""
    async with AsyncSessionLocal() as session:
        campaign = await session.get(SocialCampaign, creative_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Creative not found")
        if caption is not None:
            campaign.baseCaption = caption
        if media_url is not None:
            campaign.mediaUrl = media_url
        await session.commit()
        return {"success": True, "message": "Creative updated successfully"}

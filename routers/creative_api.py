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
from typing import Any, Optional, List, Dict

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
from routers.auth import verify_user, verify_workspace_access
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
    dependencies=[Depends(verify_user), Depends(verify_workspace_access)],
)


class GenerateRequest(BaseModel):
    topic: Optional[str] = None
    count: int = 3


class VideoCampaignRequest(BaseModel):
    product_name: str
    product_url: Optional[str] = None
    image_url: str
    goal: str = "conversion"
    # 8-30. Clamped in services.video_beats rather than validated here, so an
    # out-of-range value from an older client still produces a usable clip
    # instead of a 422 the user cannot act on.
    duration_seconds: int = 10



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

    
    # What this workspace has already been given. Without it the pipeline
    # started from the same brand profile every run and produced the same
    # scene, which is what made a feed of these look like one video reposted.
    from services.prompt_history import generate_unique, recent_prompts

    async with AsyncSessionLocal() as session:
        history = await recent_prompts(session, profile.id)

    async def _attempt(prior: list) -> str:
        out = await execute_video_pipeline(
            product_name=data.product_name,
            product_url=data.product_url,
            image_url=data.image_url,
            goal=data.goal,
            profile=profile,
            recent_prompts=prior,
            duration_seconds=data.duration_seconds,
        )
        _attempt.last = out
        return out.get("veo_prompt") or ""

    _attempt.last = {}
    unique_prompt, uniqueness = await generate_unique(_attempt, history)
    result = _attempt.last or {}
    if unique_prompt:
        result["veo_prompt"] = unique_prompt
    result["uniqueness"] = uniqueness
    result["prompts_seen_before"] = len(history)

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
                    # Seed the base caption from the prompt so the caption
                    # writer knows what this asset depicts. The user can edit it.
                    caption=veo_prompt,
                ))
                await session.commit()
        except Exception:
            logger.exception("Failed to save video prompt to media library")

    return result

# asyncio keeps only a WEAK reference to a running task. Without a strong
# reference of our own the task can be garbage-collected mid-execution, which
# leaves the asset row stuck on PENDING with an empty prompt and no error —
# exactly the "it generates but the prompt is empty" symptom.
# https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task
_BACKGROUND_TASKS: set[asyncio.Task] = set()


def _spawn_background(coro) -> asyncio.Task:
    """Run a coroutine detached from the request, holding it alive until done."""
    task = asyncio.create_task(coro)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)

    def _log_failure(t: asyncio.Task) -> None:
        if t.cancelled():
            logger.warning("Background generation task was cancelled")
            return
        exc = t.exception()
        if exc:
            logger.opt(exception=exc).error("Background generation task crashed")

    task.add_done_callback(_log_failure)
    return task


class AutoVideoRequest(BaseModel):
    product_id: Optional[str] = None   # optional; e-commerce workspaces only
    goal: str = "conversion"
    render: bool = True                # attempt a render if a key is configured
    duration_seconds: int = 10         # 8-30, clamped downstream


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

    # Metered: every prompt is a paid AI call. Checked before any work starts.
    from services import billing_service as billing
    allowed, why = await billing.check_quota(user_id, "prompts")
    if not allowed:
        raise HTTPException(status_code=402, detail=why)

    async with AsyncSessionLocal() as session:
        profile = await session.get(BusinessProfile, profile.id)

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

        # What this business has already had generated. Fed to the model as an
        # explicit avoid-list — otherwise every run reads the same brand profile
        # and returns near-identical scenes.
        recent_prompts = [
            p for p in (await session.execute(
                select(Media.prompt)
                .where(and_(
                    Media.businessProfileId == profile.id,
                    Media.promptType == "video",
                    Media.prompt.isnot(None),
                ))
                .order_by(Media.createdAt.desc())
                .limit(6)
            )).scalars().all() if p
        ]

        profile_id, profile_name = profile.id, profile.name

    # Create the asset row FIRST, as PENDING, and return straight away.
    #
    # The pipeline runs several LLM calls in sequence, each of which may walk a
    # fallback chain of free models that rate-limit. Holding the HTTP request
    # open for that regularly exceeded the server timeout, and a killed worker
    # sends no response at all — so the browser saw a missing CORS header and
    # reported a CORS failure for an endpoint whose CORS config was correct.
    async with AsyncSessionLocal() as session:
        media = Media(
            userId=user_id,
            businessProfileId=profile_id,
            filename=f"Video prompt — {subject_name}",
            mimeType="text/plain",
            url=subject_image or "",
            tags=[subject_name, "video-prompt", "ai-generated"],
            aiGenerated=True,
            promptType="video",
            generationStatus="PENDING",
        )
        session.add(media)
        await session.commit()
        await session.refresh(media)
        media_id = media.id

    render_key = None
    if data.render and video_cfg and video_cfg.apiKey:
        try:
            render_key = decrypt_token(video_cfg.apiKey)
        except Exception:
            logger.warning(f"Could not decrypt video API key for workspace {profile_id}")

    # Counted at dispatch, not on success: the AI call is billed by the
    # provider whether or not it returns something usable, and counting on
    # success would let a retry loop run free.
    from services import billing_service as billing
    await billing.record_usage(user_id, "prompts")

    _spawn_background(
        _run_video_generation(
            media_id=media_id,
            profile_id=profile_id,
            subject_name=subject_name,
            subject_url=subject_url,
            subject_image=subject_image,
            goal=data.goal,
            recent_prompts=recent_prompts,
            render_key=render_key,
            duration_seconds=data.duration_seconds,
        )
    )

    return {
        "status": "pending",
        "business": profile_name,
        "subject": subject_name,
        "usedProduct": bool(product),
        "mediaId": media_id,
        "message": "Writing your prompt. It will appear below in under a minute.",
    }


async def _run_video_generation(
    media_id: str,
    profile_id: str,
    subject_name: str,
    subject_url: Optional[str],
    subject_image: str,
    goal: str,
    recent_prompts: list,
    render_key: Optional[str],
    duration_seconds: int = 10,
) -> None:
    """Generate the prompt out of band and write the result onto the asset row.

    Runs detached from any request, so nothing here may raise into a caller —
    every failure has to land on the row as FAILED with a readable reason, or
    the user is left staring at PENDING forever.
    """
    from services.video_pipeline_service import execute_video_pipeline

    async def _finish(**fields) -> None:
        try:
            async with AsyncSessionLocal() as session:
                row = await session.get(Media, media_id)
                if not row:
                    return
                for k, v in fields.items():
                    setattr(row, k, v)
                await session.commit()
        except Exception:
            logger.exception(f"Could not record generation result for media {media_id}")

    try:
        async with AsyncSessionLocal() as session:
            profile = await session.get(BusinessProfile, profile_id)

        # A hard ceiling. Without one a stuck provider leaves the row PENDING
        # indefinitely and the user has no idea whether to wait or retry.
        result = await asyncio.wait_for(
            execute_video_pipeline(
                product_name=subject_name,
                product_url=subject_url,
                image_url=subject_image,
                goal=goal,
                profile=profile,
                recent_prompts=recent_prompts,
                duration_seconds=duration_seconds,
            ),
            timeout=600,
        )
    except asyncio.TimeoutError:
        logger.warning(f"Video pipeline timed out for workspace {profile_id}")
        await _finish(
            generationStatus="FAILED",
            generationError="Generation took too long and was stopped. Please try again.",
        )
        return
    except Exception as e:
        detail = str(e)
        exhausted = (
            "429" in detail
            or "Too Many Requests" in detail
            or "unavailable or rate-limited" in detail
            or "RetryError" in type(e).__name__
        )
        logger.exception(f"Video pipeline failed for workspace {profile_id}")
        await _finish(
            generationStatus="FAILED",
            generationError=(
                "Every AI provider is busy or rate-limited right now. Please try again in a minute."
                if exhausted else
                "The AI provider could not complete this request."
            ),
        )
        return

    veo_prompt = (result or {}).get("veo_prompt")
    if not veo_prompt:
        await _finish(
            generationStatus="FAILED",
            generationError="The AI did not return a usable prompt. Please try again.",
        )
        return

    # The two stills are stored beside the prompt. They were being generated
    # and dropped: the pipeline returned them and nothing read the return, so
    # the frame carrying the brand name and "Visit ... today" existed for the
    # length of one function call and never reached anybody.
    await _finish(
        generationStatus="READY",
        generationError=None,
        prompt=veo_prompt,
        caption=veo_prompt,
        keyframes=(result or {}).get("keyframes") or None,
        plan=(result or {}).get("plan") or None,
    )

    # Rendering is optional and must never turn a good prompt into a failure.
    if not render_key:
        return

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
                headers={"x-api-key": render_key, "Content-Type": "application/json"},
            )
        if resp.status_code >= 300:
            logger.warning(
                f"json2video render failed for workspace {profile_id}: {resp.text[:200]}"
            )
    except Exception:
        logger.exception(f"json2video render error for workspace {profile_id}")


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
            # Only set the offer when the business has not written its own —
            # a re-analysis must never overwrite a CTA the owner chose.
            if not (profile.primaryOffer or "").strip():
                profile.primaryOffer = brand_ctx.get("primaryOffer")
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
        # Only set the offer when the business has not written its own —
        # a re-analysis must never overwrite a CTA the owner chose.
        if not (profile.primaryOffer or "").strip():
            profile.primaryOffer = brand_ctx.get("primaryOffer")
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


@router.get("/prompt-history")
async def prompt_history(
    request: Request,
    limit: int = 25,
    user_id: str = Depends(verify_user),
) -> dict[str, Any]:
    """Every video prompt this workspace has generated, newest first.

    Each entry carries how similar it is to the one before it, so a run of
    near-identical creatives is visible rather than something you only notice
    once the feed looks repetitive.
    """
    from services.prompt_history import DUPLICATE_THRESHOLD, similarity

    workspace_id = request.headers.get("x-workspace-id") or request.headers.get("X-Workspace-Id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="X-Workspace-Id header required")

    async with AsyncSessionLocal() as session:
        profile = await session.get(BusinessProfile, workspace_id)
        if not profile or profile.userId != user_id:
            raise HTTPException(status_code=404, detail="Workspace not found")

        stmt = (
            select(Media)
            .where(
                Media.businessProfileId == workspace_id,
                Media.promptType == "video",
                Media.prompt.isnot(None),
            )
            .order_by(Media.createdAt.desc())
            .limit(max(1, min(limit, 100)))
        )
        rows = (await session.execute(stmt)).scalars().all()

    items = []
    for i, m in enumerate(rows):
        prior = rows[i + 1].prompt if i + 1 < len(rows) else None
        overlap = similarity(m.prompt, prior) if prior else 0.0
        items.append({
            "id": m.id,
            "prompt": m.prompt,
            "createdAt": m.createdAt.isoformat() if m.createdAt else None,
            "imageUrl": m.url or None,
            "similarityToPrevious": round(overlap, 3),
            "tooSimilar": overlap >= DUPLICATE_THRESHOLD,
            # The opening still and the closing card. Returned so the studio
            # can show them next to the video prompt -- they are what the
            # image model is fed, and the last one is the only place the brand
            # name and the offer are rendered as real text.
            "keyframes": m.keyframes or None,
            "plan": m.plan or None,
        })

    repeats = sum(1 for i in items if i["tooSimilar"])
    return {
        "total": len(items),
        "nearDuplicates": repeats,
        "threshold": DUPLICATE_THRESHOLD,
        "items": items,
    }


class RefreshIntelligenceRequest(BaseModel):
    force: bool = False


@router.get("/brand-intelligence")
async def get_brand_intelligence(
    request: Request,
    user_id: str = Depends(verify_user),
) -> dict[str, Any]:
    """What the system currently understands about this business.

    This is the profile every prompt is written from, so being able to read it
    is the difference between "the ads are wrong" and "the ads are wrong
    because it thinks we sell something else".
    """
    from services.brand_intelligence import is_stale, to_scene_context

    workspace_id = request.headers.get("x-workspace-id") or request.headers.get("X-Workspace-Id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="X-Workspace-Id header required")

    async with AsyncSessionLocal() as session:
        profile = await session.get(BusinessProfile, workspace_id)
        if not profile or profile.userId != user_id:
            raise HTTPException(status_code=404, detail="Workspace not found")

        stale, reason = is_stale(profile)
        intel = profile.brandIntelligence
        return {
            "built": bool(intel),
            "stale": stale,
            "reason": reason,
            "builtAt": profile.brandIntelligenceAt.isoformat()
                       if profile.brandIntelligenceAt else None,
            # The flattened view is what the writer actually consumes, so it is
            # the part worth checking for accuracy.
            "usedForPrompts": to_scene_context(intel),
            "full": intel,
        }


@router.post("/brand-intelligence/refresh")
async def refresh_brand_intelligence(
    data: RefreshIntelligenceRequest,
    request: Request,
    user_id: str = Depends(verify_user),
) -> dict[str, Any]:
    """Rebuild the understanding — after a repositioning, or if it got it wrong."""
    from services.brand_intelligence import get_or_build, to_scene_context

    workspace_id = request.headers.get("x-workspace-id") or request.headers.get("X-Workspace-Id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="X-Workspace-Id header required")

    async with AsyncSessionLocal() as session:
        profile = await session.get(BusinessProfile, workspace_id)
        if not profile or profile.userId != user_id:
            raise HTTPException(status_code=404, detail="Workspace not found")

        intel, built = await get_or_build(session, profile, force=data.force or True)
        if not intel:
            raise HTTPException(
                status_code=502,
                detail="Could not analyse this business. Check the website URL on the profile, then try again.",
            )
        return {
            "success": True,
            "rebuilt": built,
            "usedForPrompts": to_scene_context(intel),
        }


@router.get("/proven-offers")
async def get_proven_offers_endpoint(
    request: Request,
    user_id: str = Depends(verify_user),
) -> dict[str, Any]:
    """Return proven converting Meta ad angles and offers for the active business."""
    from services.proven_offers import for_profile

    workspace_id = request.headers.get("x-workspace-id") or request.headers.get("X-Workspace-Id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="X-Workspace-Id header required")

    async with AsyncSessionLocal() as session:
        profile = await session.get(BusinessProfile, workspace_id)
        if not profile or profile.userId != user_id:
            raise HTTPException(status_code=404, detail="Workspace not found")

        offers = for_profile(profile)
        return {
            "success": True,
            "business": profile.name,
            "hasProvenOffers": bool(offers),
            "offers": offers,
        }


# =============================================================================
# Faceless Short Videos on Auto-Pilot & Algorithm Analyzer Endpoints
# =============================================================================
class FacelessGenerateRequest(BaseModel):
    topic_id: str = "scary_stories"
    custom_topic: Optional[str] = None
    visual_style_id: str = "cinematic_realism"
    voice_id: str = "adam_storyteller"
    duration_seconds: int = 20
    publishing_mode: str = "PUBLIC"
    channel_name: Optional[str] = None
    schedule_to_queue: bool = False


class FacelessAutopilotRequest(BaseModel):
    schedule_preset: str = "daily"
    custom_days: Optional[List[int]] = None
    publishing_mode: str = "PUBLIC"
    auto_approve: bool = False
    platforms: Optional[List[str]] = None


class AnalyzeAlgorithmRequest(BaseModel):
    content_text: Optional[str] = None
    media_id: Optional[str] = None
    media_url: Optional[str] = None
    niche: Optional[str] = None
    platform: str = "YouTube Shorts / Reels / Reels"


@router.get("/faceless-presets")
async def get_faceless_presets_endpoint(
    request: Request,
    user_id: str = Depends(verify_user),
) -> dict[str, Any]:
    """Return all ready-made viral topics, visual styles, voice personas, publishing modes, and schedule presets."""
    from services.faceless_service import get_faceless_presets, PUBLISHING_MODES

    presets = get_faceless_presets()
    presets["publishing_modes"] = list(PUBLISHING_MODES.values())
    return {"success": True, **presets}


@router.post("/faceless-generate")
async def generate_faceless_short_endpoint(
    data: FacelessGenerateRequest,
    request: Request,
    user_id: str = Depends(verify_user),
) -> dict[str, Any]:
    """Generate a complete Faceless Short video package with hook, voiceover script, keyframe prompts, and viral caption."""
    from services.faceless_service import generate_faceless_short
    from services import billing_service as billing

    # Quota check
    allowed, why = await billing.check_quota(user_id, "prompts")
    if not allowed:
        raise HTTPException(status_code=402, detail=why)

    workspace_id = request.headers.get("x-workspace-id") or request.headers.get("X-Workspace-Id")
    async with AsyncSessionLocal() as session:
        profile = None
        if workspace_id:
            profile = await session.get(BusinessProfile, workspace_id)
        if not profile:
            profile = (await session.execute(
                select(BusinessProfile).where(BusinessProfile.userId == user_id)
            )).scalars().first()

        channel_name = data.channel_name or (profile.name if profile else "Faceless Viral Shorts")

    # Generate complete creative package
    package = await generate_faceless_short(
        topic_id=data.topic_id,
        custom_topic=data.custom_topic,
        visual_style_id=data.visual_style_id,
        voice_id=data.voice_id,
        duration_seconds=data.duration_seconds,
        channel_name=channel_name,
    )

    # Save to media library
    if profile:
        async with AsyncSessionLocal() as session:
            media_row = Media(
                userId=user_id,
                businessProfileId=profile.id,
                type="image",
                url="https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=1080&q=80",
                caption=package.get("viral_caption") or package.get("title"),
                meta={
                    "faceless_package": package,
                    "publishing_mode": data.publishing_mode,
                    "topic_id": data.topic_id,
                    "visual_style_id": data.visual_style_id,
                    "voice_id": data.voice_id,
                },
            )
            session.add(media_row)

            # Auto-schedule into Social Scheduler if requested
            if data.schedule_to_queue:
                from database import SocialPost, utc_now
                post_row = SocialPost(
                    userId=user_id,
                    businessProfileId=profile.id,
                    platform="YOUTUBE",
                    type="AUTO",
                    status="SCHEDULED" if data.publishing_mode == "PUBLIC" else "DRAFT",
                    caption=package.get("viral_caption") or package.get("title"),
                    mediaUrls=[media_row.url],
                    scheduledAt=utc_now(),
                )
                session.add(post_row)

            await session.commit()
            await session.refresh(media_row)
            package["saved_media_id"] = media_row.id

    return {
        "success": True,
        "package": package,
    }


@router.post("/faceless-autopilot")
async def configure_faceless_autopilot(
    data: FacelessAutopilotRequest,
    request: Request,
    user_id: str = Depends(verify_user),
) -> dict[str, Any]:
    """Configure auto-pilot scheduling days, frequency, and publishing visibility."""
    from services.faceless_service import SCHEDULE_PRESETS

    workspace_id = request.headers.get("x-workspace-id") or request.headers.get("X-Workspace-Id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="Select a business first.")

    preset = SCHEDULE_PRESETS.get(data.schedule_preset, SCHEDULE_PRESETS["daily"])
    active_days = data.custom_days if data.schedule_preset == "custom" and data.custom_days else preset["days"]

    async with AsyncSessionLocal() as session:
        profile = await session.get(BusinessProfile, workspace_id)
        if not profile or profile.userId != user_id:
            raise HTTPException(status_code=404, detail="Workspace not found.")

        profile.postingDays = active_days
        profile.postIntervalHours = preset["interval_hours"]
        profile.publishingMode = data.publishing_mode.upper().strip()
        profile.businessModel = "Faceless Channel"

        # Update marketing state
        state = (await session.execute(
            select(MarketingState).where(MarketingState.businessProfileId == workspace_id)
        )).scalars().first()
        if state:
            state.autoApprove = data.auto_approve
            state.postIntervalHours = preset["interval_hours"]

        await session.commit()

        logger.info(
            f"Faceless Auto-Pilot active for {profile.name}: {data.schedule_preset} "
            f"({len(active_days)} days/wk), mode={profile.publishingMode}, autoApprove={data.auto_approve}"
        )

        return {
            "success": True,
            "message": "Auto-Pilot Channel schedule activated successfully.",
            "schedule_preset": data.schedule_preset,
            "postingDays": active_days,
            "intervalHours": profile.postIntervalHours,
            "publishingMode": profile.publishingMode,
            "autoApprove": data.auto_approve,
        }


@router.post("/analyze-algorithm")
async def analyze_algorithm_endpoint(
    data: AnalyzeAlgorithmRequest,
    request: Request,
    user_id: str = Depends(verify_user),
) -> dict[str, Any]:
    """Analyze short-form content or media video, compute 5 radar metrics, predict view potential, and output Fix-The-Fail optimizations."""
    from services.faceless_service import analyze_short_form_content
    from services import billing_service as billing

    # Metered. A scoring run is a model call like any other generation, and a
    # validator that costs nothing to hammer is the cheapest way for a free
    # account to spend someone else's API budget.
    allowed, why = await billing.check_quota(user_id, "prompts")
    if not allowed:
        raise HTTPException(status_code=402, detail=why)

    content_to_analyze = (data.content_text or "").strip()
    media_url = data.media_url

    if data.media_id:
        async with AsyncSessionLocal() as session:
            media_item = await session.get(Media, data.media_id)
            # A media id arrives in the BODY, so the router's workspace guard
            # -- which checks the header -- does not cover it. Without this an
            # account could score another tenant's asset and read its caption
            # back in the response.
            if media_item and media_item.userId != user_id:
                raise HTTPException(status_code=404, detail="Media not found")
            if media_item:
                media_url = media_item.url or media_url
                if not content_to_analyze:
                    content_to_analyze = media_item.caption or (
                        media_item.meta.get("faceless_package", {}).get("voiceover_script")
                        if isinstance(media_item.meta, dict) else ""
                    ) or "Short-form vertical video demonstration"

    if not content_to_analyze or len(content_to_analyze) < 3:
        content_to_analyze = "High energy vertical short video with fast hook, problem agitation, and call to action."

    analysis = await analyze_short_form_content(
        content_text=content_to_analyze,
        niche=data.niche,
        platform=data.platform,
        media_url=media_url,
    )

    await billing.record_usage(user_id, "prompts")

    return {
        "success": True,
        "analysis": analysis,
    }


# =============================================================================
# PostShip Multi-Platform Repurposing (X, LinkedIn, Reddit)
# =============================================================================
class PostShipGenerateRequest(BaseModel):
    input_text: str
    url: Optional[str] = None
    schedule_to_queue: bool = False


class StrategistCampaignRequest(BaseModel):
    count: int = 3
    goal: Optional[str] = None


@router.post("/strategist-campaign")
async def generate_strategist_campaign(
    data: StrategistCampaignRequest,
    request: Request,
    user_id: str = Depends(verify_user),
) -> dict[str, Any]:
    """Instagram creatives built in stages: angles, scored, then scene by scene.

    Each creative costs its own model call, so this is metered per creative
    rather than per request — otherwise asking for five would cost the same as
    asking for one and the plan limits would mean nothing.
    """
    from services import billing_service as billing
    from services import creative_strategist

    # Bounded before anything is charged or spent. Without a ceiling a single
    # request could ask for two hundred creatives and spend an afternoon of
    # model budget on one click.
    count = max(1, min(5, int(data.count or 3)))

    for _ in range(count):
        allowed, why = await billing.check_quota(user_id, "prompts")
        if not allowed:
            raise HTTPException(status_code=402, detail=why)

    workspace_id = request.headers.get("x-workspace-id") or request.headers.get("X-Workspace-Id")
    async with AsyncSessionLocal() as session:
        profile = None
        if workspace_id:
            profile = await session.get(BusinessProfile, workspace_id)
            if profile and profile.userId != user_id:
                # Another tenant's business. Refused rather than quietly
                # generating creatives from somebody else's brand.
                raise HTTPException(status_code=404, detail="Workspace not found")
        if not profile:
            profile = (await session.execute(
                select(BusinessProfile).where(BusinessProfile.userId == user_id)
            )).scalars().first()

        if not profile:
            raise HTTPException(
                status_code=400,
                detail="Add a business first — the creatives are written from it.",
            )

        # Detached after this block, so everything needed is read now.
        snapshot = _ProfileSnapshot(profile)

    result = await creative_strategist.create_campaign(snapshot, count=count)

    # Charged for what was produced, not for what was asked for. A run that
    # degraded to two creatives must not bill for five.
    for _ in range(len(result.get("creatives") or [])):
        await billing.record_usage(user_id, "prompts")

    return {"success": True, **result}


class _ProfileSnapshot:
    """A plain copy of the fields the strategist reads.

    The ORM object is detached once its session closes, and a detached
    instance is one lazy attribute away from raising inside a path the
    customer has already been charged for.
    """

    def __init__(self, profile: Any) -> None:
        for field in ("id", "name", "websiteUrl", "description", "businessModel",
                      "industry", "niche", "targetAudience", "toneOfVoice",
                      "primaryOffer", "logoUrl"):
            setattr(self, field, getattr(profile, field, None))


@router.post("/postship-generate")
async def generate_postship_endpoint(
    data: PostShipGenerateRequest,
    request: Request,
    user_id: str = Depends(verify_user),
) -> dict[str, Any]:
    """Generate 3 native, platform-optimized social posts for X (Twitter), LinkedIn, and Reddit from a single ship line or idea."""
    from services.postship_service import generate_postship_bundle
    from services import billing_service as billing

    if not data.input_text or len(data.input_text.strip()) < 3:
        raise HTTPException(status_code=400, detail="Please enter an idea, ship line, or URL to generate posts.")

    # Metered. This writes three posts with a paid model call, and optionally
    # scrapes a URL first -- the same shape of spend as any other generator
    # here, and it was the only one costing money without counting it.
    allowed, why = await billing.check_quota(user_id, "prompts")
    if not allowed:
        raise HTTPException(status_code=402, detail=why)

    workspace_id = request.headers.get("x-workspace-id") or request.headers.get("X-Workspace-Id")
    async with AsyncSessionLocal() as session:
        profile = None
        if workspace_id:
            profile = await session.get(BusinessProfile, workspace_id)
        if not profile:
            profile = (await session.execute(
                select(BusinessProfile).where(BusinessProfile.userId == user_id)
            )).scalars().first()

        business_name = profile.name if profile else "Founder"
        industry = profile.industry or profile.businessModel if profile else "Tech"
        # Carried out as a plain id. The object below is used after this
        # session closes, and a detached instance is one lazy attribute away
        # from raising in a path that has already been paid for.
        profile_id = profile.id if profile else None

    bundle = await generate_postship_bundle(
        input_text=data.input_text,
        url=data.url,
        business_name=business_name,
        industry=industry,
    )

    await billing.record_usage(user_id, "prompts")

    # If user requests scheduling, schedule posts in the SocialPost queue
    if data.schedule_to_queue and profile_id:
        async with AsyncSessionLocal() as session:
            from database import SocialPost, utc_now
            # X post
            x_post = SocialPost(
                userId=user_id,
                businessProfileId=profile_id,
                platform="TWITTER",
                type="AUTO",
                status="SCHEDULED",
                caption=bundle.get("x_post", {}).get("content"),
                scheduledAt=utc_now(),
            )
            session.add(x_post)
            # LinkedIn post
            li_post = SocialPost(
                userId=user_id,
                businessProfileId=profile_id,
                platform="LINKEDIN",
                type="AUTO",
                status="SCHEDULED",
                caption=bundle.get("linkedin_post", {}).get("content"),
                scheduledAt=utc_now(),
            )
            session.add(li_post)
            await session.commit()

    return {
        "success": True,
        "bundle": bundle,
    }



# ---------------------------------------------------------------------------
# Bring-your-own image and video generation accounts
#
# The prompt studios write the brief; rendering it costs money at Runway or
# Replicate. A workspace connects its own key so the studio finishes the job
# instead of being something you copy out of.
#
# The key is written encrypted and never read back to the browser — the
# responses below carry a masked hint and a connected flag, which is all the
# interface needs to be honest about the state.
# ---------------------------------------------------------------------------

class MediaProviderRequest(BaseModel):
    kind: str
    provider: str
    apiKey: str
    model: Optional[str] = None


@router.get("/media-providers")
async def list_media_providers(
    request: Request,
    user_id: str = Depends(verify_user),
):
    """What can be connected, and what this workspace already has connected."""
    workspace_id = request.headers.get("x-workspace-id") or request.headers.get("X-Workspace-Id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="No workspace selected.")

    from services import media_providers

    async with AsyncSessionLocal() as session:
        connected = await media_providers.connections(session, user_id, workspace_id)

    return {"success": True, **media_providers.catalogue(), "connected": connected}


@router.post("/media-providers")
async def connect_media_provider(
    body: MediaProviderRequest,
    request: Request,
    user_id: str = Depends(verify_user),
):
    """Connect or replace one key.

    Validated against the catalogue before it is stored. A provider id nobody
    supports would otherwise be saved, reported as connected, and only fail
    at render time — long after the customer believed it was set up.
    """
    workspace_id = request.headers.get("x-workspace-id") or request.headers.get("X-Workspace-Id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="No workspace selected.")

    from services import media_providers

    key = (body.apiKey or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="Paste the API key first.")

    problem = media_providers.is_supported(body.kind, body.provider, body.model)
    if problem:
        raise HTTPException(status_code=400, detail=problem)

    async with AsyncSessionLocal() as session:
        saved = await media_providers.save(
            session, user_id, workspace_id,
            kind=body.kind, provider=body.provider, api_key=key, model=body.model,
        )

    return {"success": True, **saved}


@router.delete("/media-providers/{kind}")
async def disconnect_media_provider(
    kind: str,
    request: Request,
    user_id: str = Depends(verify_user),
):
    """Forget one connection."""
    workspace_id = request.headers.get("x-workspace-id") or request.headers.get("X-Workspace-Id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="No workspace selected.")

    from services import media_providers

    async with AsyncSessionLocal() as session:
        removed = await media_providers.disconnect(session, user_id, workspace_id, kind)

    return {"success": True, "removed": removed, "kind": kind}

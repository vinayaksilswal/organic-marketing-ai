"""
=============================================================================
Organic Marketing AI — ARQ Worker Entrypoint
=============================================================================
This file defines the ARQ worker settings and the distributed tasks that
replace the old synchronous scheduler loops.
=============================================================================
"""

import asyncio
from typing import Any
from loguru import logger
from arq.connections import RedisSettings

from config import settings
from database import init_db, close_db, AsyncSessionLocal, BusinessProfile, SocialCampaign, SocialPost, MarketingState
from sqlalchemy import select
from datetime import datetime, timezone
import uuid

# Import services used by the worker
from services.ai_service import generate_campaign_variation
from services.social_service import post_to_facebook, post_to_instagram
from services.twitter_service import twitter_service
from services.linkedin_service import linkedin_service


def utc_now() -> datetime:
    return datetime.now(timezone.utc)

async def _get_next_campaign_for_workspace(session: Any, profile: BusinessProfile) -> SocialCampaign | None:
    """Get the next active campaign for a specific workspace."""
    query = select(SocialCampaign).where(
        SocialCampaign.businessProfileId == profile.id,
        SocialCampaign.isActive == True
    ).order_by(SocialCampaign.createdAt.asc())
    
    res = await session.execute(query)
    campaigns = res.scalars().all()

    if not campaigns:
        return None

    state_query = select(MarketingState).where(MarketingState.businessProfileId == profile.id)
    state_res = await session.execute(state_query)
    state = state_res.scalars().first()

    if not state:
        state = MarketingState(
            userId=profile.userId,
            businessProfileId=profile.id,
            lastSocialIdx=0,
            lastEmailIdx=0,
            autoApprove=getattr(profile, 'autoGenerateCreatives', True)
        )
        session.add(state)
        await session.flush()

    next_idx = state.lastSocialIdx + 1
    if next_idx >= len(campaigns):
        next_idx = 0

    state.lastSocialIdx = next_idx
    return campaigns[next_idx]

async def context_aggregation_task(ctx: dict, workspace_id: str) -> str:
    """
    Step 1: Gathers business context and prepares state for generation or rendering.
    Picks the next campaign, generates the final copy, and posts it.
    """
    logger.info(f"[ARQ Worker] Executing context_aggregation_task for workspace {workspace_id}")
    
    try:
        async with AsyncSessionLocal() as session:
            profile = await session.get(BusinessProfile, workspace_id)
            if not profile:
                logger.error(f"Workspace {workspace_id} not found.")
                return "error_workspace_not_found"

            campaign = await _get_next_campaign_for_workspace(session, profile)
            if not campaign:
                logger.info(f"No active campaigns found for workspace {workspace_id}.")
                return "no_campaigns"

            logger.info(f"Selected campaign {campaign.id} for workspace {workspace_id}")

            # Synthesize final social copy
            prompt = f"Optimize this caption for social media for {profile.name} (Tone: {profile.toneOfVoice}): {campaign.baseCaption}. Include 3-4 hashtags."
            final_caption = await generate_campaign_variation(prompt)
            if not final_caption:
                final_caption = campaign.baseCaption

            # Distribute content to Meta, Twitter, LinkedIn
            media_urls = [campaign.mediaUrl] if campaign.mediaUrl else []
            
            # Post to Facebook
            fb_res = await post_to_facebook(final_caption, media_urls=media_urls)
            if fb_res:
                logger.info(f"Posted to Facebook: {fb_res}")
            
            # Post to Instagram (Only if we have media)
            ig_res = None
            if media_urls:
                ig_res = await post_to_instagram(final_caption, media_urls=media_urls)
                if ig_res:
                    logger.info(f"Posted to Instagram: {ig_res}")
            
            # Post to Twitter
            try:
                # Assuming twitter service handles text with links correctly
                await twitter_service.post_tweet(final_caption + (f" {media_urls[0]}" if media_urls else ""))
                logger.info("Posted to Twitter")
            except Exception as e:
                logger.error(f"Twitter post failed: {e}")
                
            # Post to LinkedIn
            try:
                await linkedin_service.post_share(final_caption + (f" {media_urls[0]}" if media_urls else ""))
                logger.info("Posted to LinkedIn")
            except Exception as e:
                logger.error(f"LinkedIn post failed: {e}")

            # Record the SocialPost
            post = SocialPost(
                id=str(uuid.uuid4()),
                userId=profile.userId,
                businessProfileId=profile.id,
                socialCampaignId=campaign.id,
                platform="ALL",
                content=final_caption,
                mediaUrl=campaign.mediaUrl,
                status="PUBLISHED",
                scheduledAt=utc_now()
            )
            session.add(post)
            await session.commit()
            
            return "success"
    except Exception as e:
        logger.error(f"[ARQ Worker] Error in context_aggregation_task: {e}")
        return "error"

async def startup(ctx: dict) -> None:
    logger.info("Starting ARQ Worker...")
    await init_db()

async def shutdown(ctx: dict) -> None:
    logger.info("Shutting down ARQ Worker...")
    await close_db()


class WorkerSettings:
    functions = [context_aggregation_task]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
    on_shutdown = shutdown

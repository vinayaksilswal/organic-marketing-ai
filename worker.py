"""
=============================================================================
Organic Marketing AI — ARQ Worker Entrypoint
=============================================================================
Distributed task worker for heavy async operations:
  - context_aggregation_task: Picks a campaign, generates copy, posts to all
    connected social platforms, and records the result.

Uses ARQ (async Redis queue) for reliable background task execution.
Falls back to inline execution if Redis is unavailable.
=============================================================================
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from arq.connections import RedisSettings
from loguru import logger
from sqlalchemy import select

from config import settings
from database import (
    AsyncSessionLocal,
    BusinessProfile,
    MarketingLog,
    MarketingState,
    Media,
    SocialCampaign,
    SocialPost,
    init_db,
    close_db,
)
from services.ai_service import generate_campaign_variation
from services.social_service import post_to_facebook, post_to_instagram
from services.twitter_service import twitter_service
from services.linkedin_service import linkedin_service


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def _get_next_campaign_for_workspace(
    session: Any, profile: BusinessProfile
) -> SocialCampaign | None:
    """Get the next active campaign for a specific workspace using round-robin."""
    query = (
        select(SocialCampaign)
        .where(
            SocialCampaign.businessProfileId == profile.id,
            SocialCampaign.isActive == True,
        )
        .order_by(SocialCampaign.createdAt.asc())
    )

    res = await session.execute(query)
    campaigns = res.scalars().all()

    if not campaigns:
        return None

    state_query = select(MarketingState).where(
        MarketingState.businessProfileId == profile.id
    )
    state_res = await session.execute(state_query)
    state = state_res.scalars().first()

    if not state:
        state = MarketingState(
            userId=profile.userId,
            businessProfileId=profile.id,
            lastSocialIdx=0,
            lastEmailIdx=0,
            autoApprove=getattr(profile, "autoGenerateCreatives", True),
        )
        session.add(state)
        await session.flush()

    next_idx = state.lastSocialIdx + 1
    if next_idx >= len(campaigns):
        next_idx = 0

    state.lastSocialIdx = next_idx
    return campaigns[next_idx]


async def _select_media_for_post(
    session: Any, profile: BusinessProfile
) -> str | None:
    """
    Select the best media URL from the workspace's Media catalog.
    Prioritizes AI-generated, unused media. Falls back to any available media.
    """
    # Try to find AI-generated media that hasn't been used in a post yet
    media_stmt = (
        select(Media)
        .where(
            Media.businessProfileId == profile.id,
            Media.aiGenerated == True,
        )
        .order_by(Media.createdAt.desc())
        .limit(20)
    )
    all_media = (await session.execute(media_stmt)).scalars().all()

    if not all_media:
        # Fall back to any media in the catalog
        fallback_stmt = (
            select(Media)
            .where(Media.businessProfileId == profile.id)
            .order_by(Media.createdAt.desc())
            .limit(10)
        )
        all_media = (await session.execute(fallback_stmt)).scalars().all()

    if not all_media:
        return None

    # Get list of media URLs already used in recent posts
    recent_posts_stmt = (
        select(SocialPost.mediaUrls)
        .where(SocialPost.businessProfileId == profile.id)
        .order_by(SocialPost.scheduledAt.desc())
        .limit(20)
    )
    recent_posts = (await session.execute(recent_posts_stmt)).scalars().all()
    used_urls = set()
    for urls in recent_posts:
        if urls:
            used_urls.update(urls)

    # Pick first unused media
    for media in all_media:
        if media.url not in used_urls:
            return media.url

    # If all used, just pick the first one (rotate)
    return all_media[0].url if all_media else None


async def context_aggregation_task(ctx: dict, workspace_id: str) -> str:
    """
    The core automated marketing task:
    1. Picks the next campaign from round-robin rotation
    2. Selects the best media from the catalog
    3. Generates a fresh AI caption using the LLM
    4. Posts to Facebook, Instagram, Twitter, LinkedIn
    5. Records SocialPost and MarketingLog

    Args:
        ctx: ARQ worker context
        workspace_id: The BusinessProfile ID to process

    Returns:
        Status string: 'success', 'no_campaigns', 'error_workspace_not_found', or 'error'
    """
    logger.info(f"[ARQ Worker] Executing context_aggregation_task for workspace {workspace_id}")

    errors: list[str] = []

    try:
        async with AsyncSessionLocal() as session:
            profile = await session.get(BusinessProfile, workspace_id)
            if not profile:
                logger.error(f"Workspace {workspace_id} not found.")
                return "error_workspace_not_found"

            # 1. Get next campaign
            campaign = await _get_next_campaign_for_workspace(session, profile)
            if not campaign:
                logger.info(f"No active campaigns found for workspace {workspace_id}.")
                return "no_campaigns"

            logger.info(f"Selected campaign {campaign.id} for workspace {workspace_id}")

            # 2. Select media from catalog (prefer unused AI-generated)
            media_url = await _select_media_for_post(session, profile)
            if not media_url and campaign.mediaUrl:
                media_url = campaign.mediaUrl
            media_urls = [media_url] if media_url else []

            # 3. Generate fresh AI caption
            prompt = (
                f"Write a highly engaging social media post for {profile.name} "
                f"(Industry: {profile.industry or 'General'}, "
                f"Tone: {profile.toneOfVoice or 'Professional'}). "
                f"Base content: {campaign.baseCaption}. "
                f"Include 3-5 relevant hashtags from: "
                f"{', '.join(profile.suggestedHashtags or ['#business', '#growth'])}. "
                f"Make it compelling with emojis and a clear CTA."
            )
            try:
                final_caption = await generate_campaign_variation(prompt)
            except Exception as e:
                logger.warning(f"AI caption generation failed, using base caption: {e}")
                final_caption = None

            if not final_caption or len(final_caption) < 10:
                final_caption = campaign.baseCaption

            # 4. Post to all platforms
            fb_post_id = None
            ig_post_id = None

            # Facebook
            try:
                fb_post_id = await post_to_facebook(final_caption, media_urls=media_urls)
                if fb_post_id:
                    logger.info(f"✓ Posted to Facebook: {fb_post_id}")
                else:
                    errors.append("FB: Post returned None (credentials may be missing)")
            except Exception as e:
                errors.append(f"FB: {str(e)}")
                logger.error(f"Facebook post failed: {e}")

            # Instagram (requires media)
            ig_post_id = None
            if media_urls:
                try:
                    ig_post_id = await post_to_instagram(final_caption, media_urls=media_urls)
                    if ig_post_id:
                        logger.info(f"✓ Posted to Instagram: {ig_post_id}")
                    else:
                        errors.append("IG: Post returned None (credentials may be missing)")
                except Exception as e:
                    errors.append(f"IG: {str(e)}")
                    logger.error(f"Instagram post failed: {e}")

            # Twitter
            try:
                tweet_text = final_caption
                if len(tweet_text) > 280:
                    tweet_text = tweet_text[:277] + "..."
                await twitter_service.post_tweet(tweet_text)
                logger.info("✓ Posted to Twitter")
            except Exception as e:
                errors.append(f"Twitter: {str(e)}")
                logger.error(f"Twitter post failed: {e}")

            # LinkedIn
            try:
                await linkedin_service.post_share(final_caption)
                logger.info("✓ Posted to LinkedIn")
            except Exception as e:
                errors.append(f"LinkedIn: {str(e)}")
                logger.error(f"LinkedIn post failed: {e}")

            # 5. Record the SocialPost (using correct field names!)
            is_success = fb_post_id is not None or ig_post_id is not None
            post = SocialPost(
                id=str(uuid.uuid4()),
                userId=profile.userId,
                businessProfileId=profile.id,
                campaignId=campaign.id,           # Fixed: was 'socialCampaignId'
                platform="ALL",
                type="AUTO",
                caption=final_caption,              # Fixed: was 'content'
                mediaUrls=media_urls,               # Fixed: was 'mediaUrl' (string)
                status="POSTED" if is_success else "FAILED",
                scheduledAt=utc_now(),
                postedAt=utc_now() if is_success else None,
                fbPostId=fb_post_id,
                igPostId=ig_post_id,
                errorLog=" | ".join(errors) if errors else None,
            )
            session.add(post)

            # Record marketing log
            log = MarketingLog(
                userId=profile.userId,
                businessProfileId=profile.id,
                status="SUCCESS" if is_success else "PARTIAL" if errors else "FAILED",
                socialSuccess=is_success,
                errorLog=" | ".join(errors) if errors else None,
            )
            session.add(log)

            await session.commit()

            if is_success:
                logger.info(
                    f"[ARQ Worker] ✓ Successfully posted for workspace {workspace_id} "
                    f"(FB: {fb_post_id}, IG: {ig_post_id})"
                )
            else:
                logger.warning(
                    f"[ARQ Worker] Partially failed for workspace {workspace_id}: "
                    f"{', '.join(errors)}"
                )

            return "success" if is_success else "partial"

    except Exception as e:
        logger.error(f"[ARQ Worker] Critical error in context_aggregation_task: {e}")

        # Try to log the failure
        try:
            async with AsyncSessionLocal() as session:
                log = MarketingLog(
                    businessProfileId=workspace_id,
                    status="FAILED",
                    socialSuccess=False,
                    errorLog=f"Worker critical error: {str(e)}",
                )
                session.add(log)
                await session.commit()
        except Exception:
            pass

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
    max_jobs = 10
    job_timeout = 300  # 5 minute timeout per job

"""
=============================================================================
Organic Marketing AI — Marketing Automation Scheduler (6-Hour Autonomous Loop)
=============================================================================
Implements the autonomous marketing loop using SQLAlchemy 2.0 Async Session:

  1. Query database for NEXT campaign (sequential round-robin)
  2. Generate marketing copy via OpenRouter (AI)
  3. Push to Meta APIs (Facebook + Instagram), Twitter, LinkedIn
  4. Send email blast to Audience
  5. Log posts to SocialPost / EmailCampaign tables

Uses APScheduler's AsyncIOScheduler for non-blocking task execution.
Zero binary dependencies.
=============================================================================
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger
from sqlalchemy import select, text
from arq import create_pool
from arq.connections import RedisSettings
from config import settings

from database import (
    AsyncSessionLocal,
    User,
    SocialCampaign,
    SocialPost,
    EmailCampaign,
    MarketingState,
    BusinessProfile,
)
from services.ai_service import (
    generate_campaign_variation,
    generate_campaign_email,
    generate_arxiv_content,
    _classify_paper_category,
    _build_arxiv_cta_link,
)
from services.email_service import send_email_blast
from services.social_service import post_to_facebook, post_to_instagram
from services.twitter_service import twitter_service
from services.linkedin_service import linkedin_service
from services.arxiv_newsroom import (
    ArxivRegistry,
    fetch_and_filter_new_papers,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# =============================================================================
# =============================================================================
# Campaign Rotation (Workspace-Scoped)
# =============================================================================
async def _get_next_campaign_for_workspace(session, profile: BusinessProfile) -> SocialCampaign | None:
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


# =============================================================================
# The Autonomous Marketing Loop — Runs Frequently
# =============================================================================
async def execute_marketing_loop(user_id: Optional[str] = None) -> None:
    """The unified autonomous marketing loop executing via SQLAlchemy."""
    logger.info("=" * 60)
    logger.info("[MARKETING LOOP] Starting autonomous marketing cycle (ARQ Enqueue)")
    logger.info("=" * 60)

    try:
        redis_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        
        async with AsyncSessionLocal() as session:
            stmt = select(BusinessProfile).where(BusinessProfile.brandAnalysisComplete == True)
            profiles = (await session.execute(stmt)).scalars().all()

            for profile in profiles:
                try:
                    # Check when this profile last posted
                    last_post_stmt = select(SocialPost).where(
                        SocialPost.userId == profile.userId
                    ).order_by(SocialPost.scheduledAt.desc()).limit(1)
                    
                    last_post = (await session.execute(last_post_stmt)).scalars().first()
                    
                    now = utc_now()
                    interval_hours = profile.postIntervalHours or 2
                    
                    if last_post and last_post.scheduledAt:
                        last_at = last_post.scheduledAt
                        if last_at.tzinfo is None:
                            last_at = last_at.replace(tzinfo=timezone.utc)
                        hours_since_last_post = (now - last_at).total_seconds() / 3600.0
                        if hours_since_last_post < interval_hours:
                            continue # Not due yet

                    logger.info(f"[MARKETING LOOP] Enqueueing aggregation task for workspace {profile.id} ({profile.name})")
                    
                    # Enqueue ARQ task instead of blocking
                    await redis_pool.enqueue_job('context_aggregation_task', profile.id)
                    
                except Exception as workspace_err:
                    logger.error(f"[MARKETING LOOP] Critical error enqueueing workspace {profile.id}: {workspace_err}")
                    continue
    except Exception as e:
        logger.error(f"[MARKETING LOOP] Loop exception: {e}")
    finally:
        if 'redis_pool' in locals():
            await redis_pool.close()

    logger.info("=" * 60)
    logger.info("[MARKETING LOOP] Cycle enqueue complete")
    logger.info("=" * 60)


# =============================================================================
# ArXiv Autonomous Newsroom Loop — Runs Every 2 Hours
# =============================================================================
async def execute_arxiv_newsroom_loop() -> None:
    """The autonomous arXiv Newsroom loop that runs every 2 hours."""
    logger.info("=" * 60)
    logger.info("[ARXIV NEWSROOM] Starting 2-hour paper ingestion cycle")
    logger.info("=" * 60)

    try:
        new_papers = await fetch_and_filter_new_papers()
        if not new_papers:
            logger.info("[ARXIV NEWSROOM] No new arXiv papers found in registry search")
            return

        for paper in new_papers:
            arxiv_id = paper.get("arxiv_id", "")
            title = paper.get("title", "")
            abstract = paper.get("abstract", "")
            category = _classify_paper_category(paper)
            cta_link = _build_arxiv_cta_link(arxiv_id, category)

            copy_res = await generate_arxiv_content(
                arxiv_id=arxiv_id,
                title=title,
                abstract=abstract,
                cta_link=cta_link,
            )

            social_caption = copy_res.get("socialCaption", f"New arXiv paper: {title}\n{cta_link}")

            # Post directly to Twitter & LinkedIn
            try:
                await twitter_service.post_tweet(social_caption)
                await linkedin_service.post_share(social_caption)
                ArxivRegistry.mark_as_processed(arxiv_id)
                logger.info(f"[ARXIV NEWSROOM] Published paper {arxiv_id} to Twitter & LinkedIn")
            except Exception as pub_err:
                logger.error(f"[ARXIV NEWSROOM] Failed publishing paper {arxiv_id}: {pub_err}")

    except Exception as e:
        logger.error(f"[ARXIV NEWSROOM] Ingestion loop exception: {e}")

    logger.info("=" * 60)
    logger.info("[ARXIV NEWSROOM] 2-hour cycle complete")
    logger.info("=" * 60)


# =============================================================================
# =============================================================================
# Autonomous AI Creative Generation Loop
# =============================================================================
async def execute_creative_generation_loop() -> None:
    """The autonomous creative generation loop running frequently to populate media assets."""
    logger.info("=" * 60)
    logger.info("[CREATIVE GENERATOR] Starting automated creative generation cycle")
    logger.info("=" * 60)

    try:
        from database import BusinessProfile
        from services.creative_service import auto_generate_creative_batch

        async with AsyncSessionLocal() as session:
            stmt = select(BusinessProfile).where(BusinessProfile.brandAnalysisComplete == True)
            profiles = (await session.execute(stmt)).scalars().all()

        if not profiles:
            logger.info("[CREATIVE GENERATOR] No active workspaces found for creative generation")
            return

        for profile in profiles:
            # Check when creatives were last generated. We check SocialCampaigns
            async with AsyncSessionLocal() as session:
                last_campaign_stmt = select(SocialCampaign).where(
                    SocialCampaign.businessProfileId == profile.id
                ).order_by(SocialCampaign.createdAt.desc()).limit(1)
                
                last_campaign = (await session.execute(last_campaign_stmt)).scalars().first()
                
            now = utc_now()
            auto_gen = getattr(profile, 'autoGenerateCreatives', True)
            if not auto_gen:
                logger.debug(f"[CREATIVE GENERATOR] Auto-generation disabled for workspace {profile.id}")
                continue

            interval_hours = getattr(profile, 'creativeGenerationIntervalHours', 12) or 12
            
            if last_campaign and last_campaign.createdAt:
                last_at = last_campaign.createdAt
                if last_at.tzinfo is None:
                    last_at = last_at.replace(tzinfo=timezone.utc)
                hours_since_last = (now - last_at).total_seconds() / 3600.0
                if hours_since_last < interval_hours:
                    continue # Not due yet

            logger.info(f"[CREATIVE GENERATOR] Generating creatives for workspace {profile.id} (Interval: {interval_hours}h)")
            try:
                res = await auto_generate_creative_batch(profile.id, count=3)
                logger.info(f"[CREATIVE GENERATOR] Generated {res.get('count', 0)} creatives for business: {profile.name} ({profile.id})")
            except Exception as e:
                logger.error(f"[CREATIVE GENERATOR] Failed generating for workspace {profile.id}: {e}")

    except Exception as e:
        logger.error(f"[CREATIVE GENERATOR] Loop execution exception: {e}")

    logger.info("=" * 60)
    logger.info("[CREATIVE GENERATOR] Cycle complete")
    logger.info("=" * 60)


# =============================================================================
# Scheduler Lifecycle Management
# =============================================================================
def create_scheduler() -> AsyncIOScheduler:
    """Create and configure the APScheduler AsyncIOScheduler instance."""
    scheduler = AsyncIOScheduler(timezone="UTC")

    scheduler.add_job(
        execute_marketing_loop,
        trigger=IntervalTrigger(hours=2),
        id="marketing_loop",
        name="Autonomous 2-Hour Marketing Loop",
        replace_existing=True,
    )

    scheduler.add_job(
        execute_creative_generation_loop,
        trigger=IntervalTrigger(hours=2),
        id="creative_generation_loop",
        name="Autonomous 2-Hour Creative Generation Loop",
        replace_existing=True,
    )

    scheduler.add_job(
        execute_arxiv_newsroom_loop,
        trigger=IntervalTrigger(hours=2),
        id="arxiv_newsroom_loop",
        name="Autonomous 2-Hour arXiv Newsroom Loop",
        replace_existing=True,
    )

    logger.info("APScheduler initialized (Marketing Loop: 2h, Creative Loop: 2h, Arxiv Loop: 2h)")
    return scheduler


def shutdown_scheduler(scheduler: AsyncIOScheduler) -> None:
    """Gracefully shut down the APScheduler instance."""
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler shut down successfully")


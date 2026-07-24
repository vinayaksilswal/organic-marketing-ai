"""
=============================================================================
Organic Marketing AI — Marketing Automation Scheduler
=============================================================================
Implements the autonomous marketing loop using APScheduler:

  Every 2 hours (configurable per workspace):
  1. Query all active workspaces with completed brand analysis
  2. Check if each workspace is due for a post (based on interval)
  3. Enqueue to ARQ worker (or execute inline if Redis unavailable)

  Creative Generation Loop (every 2 hours):
  1. Check each workspace's creative generation interval
  2. Generate new AI creatives and upload to Cloudinary

Uses APScheduler's AsyncIOScheduler for non-blocking task execution.
Falls back to inline execution if Redis/ARQ is unavailable.
=============================================================================
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger
from sqlalchemy import select

from config import settings
from database import (
    AsyncSessionLocal,
    BusinessProfile,
    MarketingState,
    SocialCampaign,
    SocialPost,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# =============================================================================
# Campaign Rotation (Workspace-Scoped)
# =============================================================================
async def _get_next_campaign_for_workspace(session, profile: BusinessProfile) -> SocialCampaign | None:
    """Get the next active campaign for a specific workspace."""
    query = select(SocialCampaign).where(
        SocialCampaign.businessProfileId == profile.id,
        SocialCampaign.isActive == True,
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
            autoApprove=getattr(profile, "autoGenerateCreatives", True),
        )
        session.add(state)
        await session.flush()

    next_idx = state.lastSocialIdx + 1
    if next_idx >= len(campaigns):
        next_idx = 0

    state.lastSocialIdx = next_idx
    return campaigns[next_idx]


# =============================================================================
# The Autonomous Marketing Loop
# =============================================================================
async def execute_marketing_loop(user_id: Optional[str] = None) -> None:
    """
    The unified autonomous marketing loop.
    Tries to enqueue tasks via ARQ/Redis. Falls back to inline execution.
    """
    try:
        from arq import create_pool
        from arq.connections import RedisSettings
        redis_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        lock = await redis_pool.set("lock:marketing_loop", "1", nx=True, ex=300)
        await redis_pool.close()
        if not lock:
            logger.info("[MARKETING LOOP] Another instance is already running")
            return
    except Exception as e:
        logger.warning(f"[MARKETING LOOP] Redis lock check failed: {e}")

    logger.info("=" * 60)
    logger.info("[MARKETING LOOP] Starting autonomous marketing cycle")
    logger.info("=" * 60)

    try:
        async with AsyncSessionLocal() as session:
            stmt = select(BusinessProfile).where(BusinessProfile.brandAnalysisComplete == True)
            profiles = (await session.execute(stmt)).scalars().all()

            if not profiles:
                logger.info("[MARKETING LOOP] No active workspaces found")
                return

            for profile in profiles:
                try:
                    # Check when this profile last posted
                    last_post_stmt = (
                        select(SocialPost)
                        .where(SocialPost.businessProfileId == profile.id)
                        .order_by(SocialPost.scheduledAt.desc())
                        .limit(1)
                    )
                    last_post = (await session.execute(last_post_stmt)).scalars().first()

                    now = utc_now()
                    interval_hours = profile.postIntervalHours or 2

                    if last_post and last_post.scheduledAt:
                        last_at = last_post.scheduledAt
                        if last_at.tzinfo is None:
                            last_at = last_at.replace(tzinfo=timezone.utc)
                        hours_since_last_post = (now - last_at).total_seconds() / 3600.0
                        if hours_since_last_post < interval_hours:
                            logger.debug(
                                f"[MARKETING LOOP] Skipping {profile.name} — "
                                f"posted {hours_since_last_post:.1f}h ago (interval: {interval_hours}h)"
                            )
                            continue

                    logger.info(f"[MARKETING LOOP] Processing workspace: {profile.name} ({profile.id})")

                    # Try ARQ (Redis) first, fall back to inline
                    enqueued = await _try_enqueue_arq(profile.id)
                    if not enqueued:
                        logger.info(f"[MARKETING LOOP] Running inline for {profile.name}")
                        await _execute_inline(profile.id)

                except Exception as workspace_err:
                    logger.error(f"[MARKETING LOOP] Error processing {profile.id}: {workspace_err}")
                    continue

    except Exception as e:
        logger.error(f"[MARKETING LOOP] Loop exception: {e}")

    logger.info("[MARKETING LOOP] Cycle complete")


async def _try_enqueue_arq(workspace_id: str) -> bool:
    """Try to enqueue a task via ARQ/Redis. Returns False if Redis is unavailable."""
    try:
        from arq import create_pool
        from arq.connections import RedisSettings

        redis_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        await redis_pool.enqueue_job("context_aggregation_task", workspace_id)
        await redis_pool.close()
        logger.info(f"[MARKETING LOOP] Enqueued ARQ task for workspace {workspace_id}")
        return True
    except Exception as e:
        logger.debug(f"[MARKETING LOOP] ARQ unavailable ({e}), will use inline execution")
        return False


async def _execute_inline(workspace_id: str) -> None:
    """Execute the marketing task inline (without ARQ worker)."""
    try:
        from worker import context_aggregation_task
        result = await context_aggregation_task({}, workspace_id)
        logger.info(f"[MARKETING LOOP] Inline execution result for {workspace_id}: {result}")
    except Exception as e:
        logger.error(f"[MARKETING LOOP] Inline execution failed for {workspace_id}: {e}")


# =============================================================================
# Autonomous AI Creative Generation Loop
# =============================================================================
async def execute_creative_generation_loop() -> None:
    """The autonomous creative generation loop running frequently to populate media assets."""
    try:
        from arq import create_pool
        from arq.connections import RedisSettings
        redis_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        lock = await redis_pool.set("lock:creative_loop", "1", nx=True, ex=600)
        await redis_pool.close()
        if not lock:
            logger.info("[CREATIVE GENERATOR] Another instance is already running")
            return
    except Exception as e:
        logger.warning(f"[CREATIVE GENERATOR] Redis lock check failed: {e}")

    logger.info("=" * 60)
    logger.info("[CREATIVE GENERATOR] Starting automated creative generation cycle")
    logger.info("=" * 60)

    try:
        from services.creative_service import auto_generate_creative_batch

        async with AsyncSessionLocal() as session:
            stmt = select(BusinessProfile).where(BusinessProfile.brandAnalysisComplete == True)
            profiles = (await session.execute(stmt)).scalars().all()

        if not profiles:
            logger.info("[CREATIVE GENERATOR] No active workspaces found")
            return

        for profile in profiles:
            auto_gen = getattr(profile, "autoGenerateCreatives", True)
            if not auto_gen:
                logger.debug(f"[CREATIVE GENERATOR] Auto-generation disabled for {profile.name}")
                continue

            # Check when creatives were last generated
            async with AsyncSessionLocal() as session:
                last_campaign_stmt = (
                    select(SocialCampaign)
                    .where(SocialCampaign.businessProfileId == profile.id)
                    .order_by(SocialCampaign.createdAt.desc())
                    .limit(1)
                )
                last_campaign = (await session.execute(last_campaign_stmt)).scalars().first()

            now = utc_now()
            interval_hours = getattr(profile, "creativeGenerationIntervalHours", 12) or 12

            if last_campaign and last_campaign.createdAt:
                last_at = last_campaign.createdAt
                if last_at.tzinfo is None:
                    last_at = last_at.replace(tzinfo=timezone.utc)
                hours_since_last = (now - last_at).total_seconds() / 3600.0
                if hours_since_last < interval_hours:
                    continue

            logger.info(f"[CREATIVE GENERATOR] Generating creatives for {profile.name} ({profile.id})")
            try:
                res = await auto_generate_creative_batch(profile.id, count=3)
                logger.info(
                    f"[CREATIVE GENERATOR] ✓ Generated {res.get('count', 0)} creatives "
                    f"for {profile.name}"
                )
            except Exception as e:
                logger.error(f"[CREATIVE GENERATOR] Failed for {profile.id}: {e}")

    except Exception as e:
        logger.error(f"[CREATIVE GENERATOR] Loop exception: {e}")

    logger.info("[CREATIVE GENERATOR] Cycle complete")


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

    logger.info("APScheduler initialized (Marketing Loop: 2h, Creative Loop: 2h)")
    return scheduler


def shutdown_scheduler(scheduler: AsyncIOScheduler) -> None:
    """Gracefully shut down the APScheduler instance."""
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler shut down successfully")

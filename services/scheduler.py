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

import os
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
    SocialCampaign,
    SocialConnection,
    SocialPost,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


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
            # Every workspace is eligible, not just those whose brand analysis
            # finished. Gating on brandAnalysisComplete meant a workspace whose
            # analysis failed once — a rate limit, a dropped background task —
            # was skipped forever with no error and no way to recover. Brand
            # analysis improves caption quality; it is not a precondition for
            # posting. Workspaces without it fall back to a brand template.
            stmt = select(BusinessProfile)
            profiles = (await session.execute(stmt)).scalars().all()

            if not profiles:
                logger.info("[MARKETING LOOP] No workspaces found")
                return

            # Self-heal a missing brand profile rather than degrading forever.
            # Onboarding builds one automatically, but if that attempt failed —
            # a rate limit, a dropped task — the workspace previously stayed
            # generic permanently and the only remedy was a manual button. The
            # loop already runs every couple of hours, so it is the natural
            # place to retry. Each attempt is isolated: a failure here must not
            # stop the workspace from posting.
            for profile in profiles:
                if profile.brandAnalysisComplete:
                    continue
                try:
                    from services.creative_service import generate_brand_context
                    logger.info(f"[MARKETING LOOP] Building missing brand profile for {profile.name}")
                    ctx = await generate_brand_context(profile)
                    profile.industry = ctx["industry"]
                    profile.targetAudience = ctx["targetAudience"]
                    profile.toneOfVoice = ctx["toneOfVoice"]
                    profile.contentPillars = ctx["contentPillars"]
                    profile.suggestedHashtags = ctx["suggestedHashtags"]
                    profile.brandColors = ctx["brandColors"]
                    profile.brandAnalysisComplete = True
                    await session.commit()
                    logger.info(f"[MARKETING LOOP] Brand profile ready for {profile.name}")
                except Exception as e:
                    await session.rollback()
                    logger.warning(
                        f"[MARKETING LOOP] Brand profile for {profile.name} still unavailable "
                        f"({e}); posting continues with fallback captions"
                    )

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
                        if not is_post_due(hours_since_last_post, interval_hours):
                            logger.debug(
                                f"[MARKETING LOOP] Skipping {profile.name} — "
                                f"posted {hours_since_last_post:.1f}h ago (interval: {interval_hours}h)"
                            )
                            continue

                    connection = (await session.execute(
                        select(SocialConnection).where(
                            SocialConnection.businessProfileId == profile.id
                        ).limit(1)
                    )).scalars().first()
                    if connection is None:
                        logger.warning(
                            f"[MARKETING LOOP] {profile.name} has no connected social "
                            f"account, so there is nowhere to publish. Connect "
                            f"Facebook or Instagram in Businesses -> Edit -> Social."
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
# How often the loop wakes up. This is the resolution of the whole schedule,
# not the posting rate -- each workspace posts on its own postIntervalHours.
#
# It used to be 2 hours, which broke the setting two ways. "Every 1 hour" was
# unreachable at any setting, because the loop simply never ran that often.
# And a 4-hour workspace posted every 6: a post's scheduledAt lands a little
# after the tick that created it, so at the 4-hour tick the elapsed time was
# 3h59m, the check failed, and it waited for the 6-hour tick. Two real
# workspaces show it exactly -- 20:58, 02:58, 08:58 on a 4-hour setting.
MARKETING_LOOP_MINUTES = int(os.getenv("MARKETING_LOOP_MINUTES", "15"))


def is_post_due(hours_since_last: float, interval_hours: float,
                loop_minutes: int = MARKETING_LOOP_MINUTES) -> bool:
    """Whether a workspace is due to post.

    The grace is half a loop period. Without it the comparison is a race
    against its own bookkeeping: elapsed is measured from when the last post
    was recorded, which is always slightly after the tick that produced it, so
    an exact multiple never quite arrives and the workspace slips a whole
    period. Half a tick is small enough never to post meaningfully early and
    large enough to absorb the delay.
    """
    grace = (loop_minutes / 60.0) / 2.0
    return hours_since_last >= max(interval_hours - grace, 0)


def create_scheduler() -> AsyncIOScheduler:
    """Create and configure the APScheduler AsyncIOScheduler instance."""
    scheduler = AsyncIOScheduler(timezone="UTC")

    scheduler.add_job(
        execute_marketing_loop,
        trigger=IntervalTrigger(minutes=MARKETING_LOOP_MINUTES),
        id="marketing_loop",
        name="Marketing Loop",
        replace_existing=True,
        # A tick that overruns must not queue a second copy behind it.
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        execute_creative_generation_loop,
        trigger=IntervalTrigger(hours=2),
        id="creative_generation_loop",
        name="Autonomous 2-Hour Creative Generation Loop",
        replace_existing=True,
    )

    logger.info(
        f"APScheduler initialized (Marketing Loop: {MARKETING_LOOP_MINUTES}m, "
        f"Creative Loop: 2h)"
    )
    return scheduler


def shutdown_scheduler(scheduler: AsyncIOScheduler) -> None:
    """Gracefully shut down the APScheduler instance."""
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler shut down successfully")

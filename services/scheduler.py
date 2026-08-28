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
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

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


# A ceiling on autonomous posting, per workspace, per rolling 24 hours.
#
# The posting interval is the customer's setting; this is a safety rail on top
# of it, and it exists to protect something the customer does not own -- the
# standing of the Meta app every customer publishes through.
#
# Meta scores an app on the aggregate behaviour of the accounts authorised to
# it. If a meaningful share of those accounts are flagged as spam, the app's
# API access is throttled, its permissions cut, or the app removed. That is not
# one customer losing reach; it is every customer losing the ability to publish
# at all, and the product with them.
#
# An hourly interval is 24 posts a day. No authentic business account posts
# hourly, and the platform will read it as automated flooding whether the post
# arrives through the API or the app. The interval setting alone could not
# express that risk, because a customer choosing "every 1 hour" is choosing a
# cadence, not accepting a ban.
#
# Eight is deliberately above what any real business needs and well beneath
# what looks automated. Raise it with SOCIAL_MAX_POSTS_PER_DAY if a specific
# account has the engagement to carry more.
MAX_POSTS_PER_DAY = int(os.getenv("SOCIAL_MAX_POSTS_PER_DAY", "8"))


async def posts_in_last_24h(session, workspace_id: str) -> int:
    """How many posts this workspace has published in the last rolling day."""
    from sqlalchemy import func

    since = utc_now() - timedelta(hours=24)
    return (await session.execute(
        select(func.count(SocialPost.id)).where(
            SocialPost.businessProfileId == workspace_id,
            SocialPost.scheduledAt >= since.replace(tzinfo=None),
        )
    )).scalar() or 0


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
    cycle_started = utc_now()

    try:
        # Read the workspace list, then let the connection go.
        #
        # This loop used to hold ONE session open across every workspace while
        # each one published -- and publishing a Reel means uploading a video
        # to Instagram and polling until it finishes, which takes minutes. The
        # database connection sat idle throughout, and Neon closes idle
        # connections. By the fifth workspace the session was dead:
        #
        #   InterfaceError: connection is closed
        #     SELECT count("Audience".id) ... WHERE businessProfileId = ...
        #
        # Every workspace after that point failed on the dead session, every
        # run, permanently. Two workspaces kept posting and five stopped, with
        # the only difference being their position in the iteration -- which is
        # exactly what it looked like from the dashboard: some businesses work
        # and some never do.
        #
        # Each step now takes a connection only for as long as it is using one,
        # and no connection is held across the publish.
        async with AsyncSessionLocal() as session:
            # Every workspace is eligible, not just those whose brand analysis
            # finished. Gating on brandAnalysisComplete meant a workspace whose
            # analysis failed once — a rate limit, a dropped background task —
            # was skipped forever with no error and no way to recover. Brand
            # analysis improves caption quality; it is not a precondition for
            # posting. Workspaces without it fall back to a brand template.
            profiles = (await session.execute(select(BusinessProfile))).scalars().all()
            workspaces = [
                (p.id, p.name, p.postIntervalHours or 2,
                 bool(p.brandAnalysisComplete), p.userId,
                 bool(getattr(p, "automationPaused", False)),
                 # The posting window travels as plain values rather than as a
                 # detached ORM object, which would raise the moment this
                 # session closes.
                 {
                     "postingDays": p.postingDays,
                     "postingStartHour": p.postingStartHour,
                     "postingEndHour": p.postingEndHour,
                     "postingTimezone": p.postingTimezone,
                 })
                for p in profiles
            ]

        if not workspaces:
            logger.info("[MARKETING LOOP] No workspaces found")
            return

        # Every workspace's outcome, written to the database at the end of the
        # cycle. Two businesses posted on schedule and two never did, and the
        # logs said nothing at all about the ones that did not -- no attempt,
        # no skip, no error. A cycle that leaves no trace of where it stopped
        # cannot be diagnosed without guessing, and guessing has been expensive
        # here. This records the answer instead.
        outcomes: list = []

        for (workspace_id, name, interval_hours, brand_ready, owner_id,
             paused, window) in workspaces:
            try:
                # Checked before anything else, including the brand backfill:
                # a paused workspace should consume no LLM calls either.
                if paused:
                    logger.info(f"[MARKETING LOOP] {name} is paused by its owner")
                    outcomes.append(f"{name}: paused")
                    continue

                # Self-heal a missing brand profile rather than degrading
                # forever. Onboarding builds one automatically, but if that
                # attempt failed the workspace previously stayed generic
                # permanently. Isolated: a failure here must not stop the
                # workspace from posting.
                if not brand_ready:
                    try:
                        from services.creative_service import generate_brand_context

                        async with AsyncSessionLocal() as session:
                            profile = await session.get(BusinessProfile, workspace_id)
                            if profile is not None:
                                logger.info(
                                    f"[MARKETING LOOP] Building missing brand profile for {name}"
                                )
                                ctx = await generate_brand_context(profile)
                                profile.industry = ctx["industry"]
                                profile.targetAudience = ctx["targetAudience"]
                                profile.toneOfVoice = ctx["toneOfVoice"]
                                profile.contentPillars = ctx["contentPillars"]
                                profile.suggestedHashtags = ctx["suggestedHashtags"]
                                profile.brandColors = ctx["brandColors"]
                                profile.brandAnalysisComplete = True
                                await session.commit()
                                logger.info(f"[MARKETING LOOP] Brand profile ready for {name}")
                    except Exception as e:
                        logger.warning(
                            f"[MARKETING LOOP] Brand profile for {name} still unavailable "
                            f"({e}); posting continues with fallback captions"
                        )

                # Due check and connection check, on their own short-lived
                # connection.
                async with AsyncSessionLocal() as session:
                    last_post = (await session.execute(
                        select(SocialPost)
                        .where(SocialPost.businessProfileId == workspace_id)
                        .order_by(SocialPost.scheduledAt.desc())
                        .limit(1)
                    )).scalars().first()

                    now = utc_now()
                    if last_post and last_post.scheduledAt:
                        last_at = last_post.scheduledAt
                        if last_at.tzinfo is None:
                            last_at = last_at.replace(tzinfo=timezone.utc)
                        hours_since_last_post = (now - last_at).total_seconds() / 3600.0
                        if not is_post_due(hours_since_last_post, interval_hours):
                            logger.debug(
                                f"[MARKETING LOOP] Skipping {name} — posted "
                                f"{hours_since_last_post:.1f}h ago (interval: {interval_hours}h)"
                            )
                            outcomes.append(
                                f"{name}: not due ({hours_since_last_post:.1f}h "
                                f"of {interval_hours}h)"
                            )
                            continue

                    # Due, but is this a moment the customer chose? The window
                    # only ever withholds -- a window that FORCED a post would
                    # fire every workspace at 09:00 sharp, which is the most
                    # obviously automated thing an account can do.
                    from services.posting_window import within_window

                    allowed, why = within_window(_Window(window), now)
                    if not allowed:
                        logger.info(f"[MARKETING LOOP] {name} is outside its posting window - {why}")
                        outcomes.append(f"{name}: outside posting window ({why})")
                        continue

                    # The interval said it is time. This asks whether going
                    # ahead would make the account look automated.
                    # An unlimited account has accepted the trade knowingly:
                    # enterprise is granted, not bought, and the operator's own
                    # workspaces are the ones whose cadence they own outright.
                    # The rail protects customers who did not choose it.
                    from services import billing_service as _billing

                    unlimited = await _billing._is_unlimited(owner_id)

                    published_today = 0 if unlimited else await posts_in_last_24h(
                        session, workspace_id
                    )
                    if published_today >= MAX_POSTS_PER_DAY:
                        logger.warning(
                            f"[MARKETING LOOP] {name} has published "
                            f"{published_today} times in 24h, at the safety "
                            f"ceiling of {MAX_POSTS_PER_DAY}. Holding until the "
                            f"window clears. A {interval_hours}h interval asks "
                            f"for {24 // max(interval_hours, 1)} posts a day, "
                            f"which reads as spam and risks the app's standing "
                            f"for every workspace on it."
                        )
                        outcomes.append(
                            f"{name}: daily cap ({published_today}/{MAX_POSTS_PER_DAY})"
                        )
                        continue

                    connection = (await session.execute(
                        select(SocialConnection)
                        .where(SocialConnection.businessProfileId == workspace_id)
                        .limit(1)
                    )).scalars().first()

                if connection is None:
                    logger.warning(
                        f"[MARKETING LOOP] {name} has no connected social account, "
                        f"so there is nowhere to publish. Connect Facebook or "
                        f"Instagram in Businesses -> Edit -> Social."
                    )
                    outcomes.append(f"{name}: no social connection")
                    continue

                logger.info(f"[MARKETING LOOP] Processing workspace: {name} ({workspace_id})")

                # No session is open here. This is the slow part -- uploading a
                # video to Instagram and waiting for it to process -- and it is
                # precisely what killed the connection when one was held.
                started = utc_now()
                enqueued = await _try_enqueue_arq(workspace_id)
                if enqueued:
                    # Only meaningful if an ARQ worker is actually consuming the
                    # queue. If none is, the job is accepted and never runs --
                    # which looks exactly like a workspace that quietly refuses
                    # to post.
                    outcomes.append(f"{name}: ENQUEUED to arq (not run inline)")
                else:
                    logger.info(f"[MARKETING LOOP] Running inline for {name}")
                    result = await _execute_inline(workspace_id)
                    took = (utc_now() - started).total_seconds()
                    # The task's own verdict, not an assumption that running it
                    # meant something was published.
                    outcomes.append(f"{name}: {result} ({took:.0f}s)")

            except Exception as workspace_err:
                # One workspace failing must never affect the next one. It used
                # to, because they shared a connection.
                logger.error(
                    f"[MARKETING LOOP] Error processing {name} ({workspace_id}): "
                    f"{workspace_err}"
                )
                outcomes.append(f"{name}: ERROR {type(workspace_err).__name__}: {workspace_err}")
                continue

        await _record_cycle(outcomes, cycle_started)

    except Exception as e:
        # str(e) is empty for a whole family of exceptions -- asyncpg's, most
        # timeouts, anything raised bare. Two cycles aborted an hour apart and
        # recorded "LOOP ABORTED:" with nothing after the colon, which is a
        # log line that costs time and returns none of it. The type is what
        # identifies the fault; the message is a bonus.
        import traceback

        detail = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
        logger.error(f"[MARKETING LOOP] Loop exception: {detail}\n{traceback.format_exc()}")
        try:
            # The last frame says which line gave up, which is the difference
            # between "something failed" and a place to look.
            frames = traceback.extract_tb(e.__traceback__)
            where = ""
            if frames:
                last = frames[-1]
                where = f" at {last.filename.rsplit('/', 1)[-1]}:{last.lineno} in {last.name}"
            await _record_cycle(
                (outcomes if "outcomes" in dir() else [])
                + [f"LOOP ABORTED: {detail}{where}"],
                cycle_started,
            )
        except Exception:
            pass

    logger.info("[MARKETING LOOP] Cycle complete")


async def _record_cycle(outcomes: list, started) -> None:
    """Write what the cycle did, per workspace, as one row.

    A run that reaches only some of the workspaces is indistinguishable from a
    run that reached all of them and found nothing to do -- unless it says so.
    Written on a fresh session because the cycle deliberately holds none.
    """
    from database import MarketingLog

    took = (utc_now() - started).total_seconds()
    summary = f"cycle {took:.0f}s | " + " | ".join(outcomes) if outcomes else \
        f"cycle {took:.0f}s | no workspaces considered"
    try:
        async with AsyncSessionLocal() as session:
            session.add(MarketingLog(
                userId=None,
                businessProfileId=None,
                status="CYCLE",
                socialSuccess=False,
                emailSuccess=False,
                emailCount=0,
                errorLog=summary[:4000],
            ))
            await session.commit()
    except Exception as e:
        logger.warning(f"[MARKETING LOOP] Could not record cycle summary: {e}")


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


async def _execute_inline(workspace_id: str) -> str:
    """Execute the marketing task inline (without ARQ worker).

    Returns what the task reported. This used to be discarded, so a task that
    returned "no_campaigns" in seconds without publishing anything was
    indistinguishable from one that published -- and the cycle summary
    confidently recorded "PUBLISHED" for three workspaces that had posted
    nothing for hours.
    """
    try:
        from worker import context_aggregation_task
        result = await context_aggregation_task({}, workspace_id)
        logger.info(f"[MARKETING LOOP] Inline execution result for {workspace_id}: {result}")
        return str(result)
    except Exception as e:
        logger.error(f"[MARKETING LOOP] Inline execution failed for {workspace_id}: {e}")
        return f"exception: {e}"


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


class _Window:
    """Attribute access over the window values carried out of the session."""

    def __init__(self, values: dict):
        for k, v in (values or {}).items():
            setattr(self, k, v)


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


async def execute_due_scheduled_posts() -> None:
    """Publish one-time scheduled posts that have come due.

    THE BUG THIS REPLACES
    ---------------------
    This used to test only for FACEBOOK, INSTAGRAM and BOTH. PostShip queues
    rows with platform TWITTER and LINKEDIN. Those matched no branch, so no
    publisher ran, no error was recorded -- and the status line

        "POSTED" if not errors or fb_post_id or ig_post_id else "FAILED"

    read an empty error list and marked them POSTED. The customer was told
    their post went out; nothing had been sent anywhere.

    A visible failure is recoverable. A false success is not: nobody goes
    looking for a post the dashboard says already shipped. So the rule here
    is now the opposite of what it was -- POSTED requires evidence that
    something published, and anything this function does not understand is
    FAILED with a reason, never quietly successful.
    """
    now = utc_now()
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(SocialPost).where(
                SocialPost.status == "SCHEDULED",
                SocialPost.scheduledAt <= now
            )
            res = await session.execute(stmt)
            due_posts = res.scalars().all()

            for post in due_posts:
                try:
                    await _publish_one_scheduled_post(post)
                except Exception as e:
                    # One bad row must not take the rest of the batch with it.
                    post.status = "FAILED"
                    post.errorLog = str(e)[:500]
                    post.postedAt = utc_now()
                logger.info(f"[SCHEDULED POST] Processed post {post.id} for {post.businessProfileId} -> {post.status}")

            if due_posts:
                await session.commit()
    except Exception as e:
        logger.error(f"[SCHEDULED POSTS] Loop exception: {e}")


# Which platform tokens this function knows how to publish. A row carrying
# anything else is a bug somewhere upstream, and it fails loudly rather than
# being counted as sent.
_SCHEDULED_TARGETS = {
    "FACEBOOK": ("facebook",),
    "INSTAGRAM": ("instagram",),
    "BOTH": ("facebook", "instagram"),
    "TWITTER": ("x",),
    "X": ("x",),
    "LINKEDIN": ("linkedin",),
    "YOUTUBE": ("youtube",),
    "ALL": ("facebook", "instagram", "x", "linkedin", "youtube"),
}

_POST_ID_FIELD = {
    "facebook": "fbPostId",
    "instagram": "igPostId",
    "x": "twitterPostId",
    "linkedin": "linkedinPostId",
}


async def _publish_one_scheduled_post(post: Any) -> None:
    """Send one row to every platform it names, and record what happened.

    Split out of the loop above so a single post can be tested without
    standing up a scheduler, a database and a clock.
    """

    workspace_id = post.businessProfileId
    media_urls = post.mediaUrls or []
    caption = post.caption or ""
    token = (post.platform or "").upper()

    targets = _SCHEDULED_TARGETS.get(token)
    if not targets:
        post.status = "FAILED"
        post.errorLog = f"Unknown platform '{post.platform}' -- nothing was sent."
        post.postedAt = utc_now()
        return

    website = None
    try:
        from database import BusinessProfile
        async with AsyncSessionLocal() as s:
            profile = await s.get(BusinessProfile, workspace_id)
            website = getattr(profile, "website", None) if profile else None
    except Exception:
        pass

    published: dict[str, str] = {}
    errors: list[str] = []

    for platform in targets:
        try:
            post_id = await _publish_to(
                platform, workspace_id, caption, media_urls, website,
                explicit=len(targets) == 1,
            )
        except _PlatformSkip as skip:
            # A rule of the platform, not a failure of this workspace. Only
            # reached on multi-target rows; a row aimed at one platform that
            # cannot take it is a real failure and says so.
            logger.info(f"[SCHEDULED POST] skipped {platform}: {skip}")
            continue
        except Exception as e:
            errors.append(f"{platform}: {e}")
            continue

        if post_id:
            published[platform] = str(post_id)
            field = _POST_ID_FIELD.get(platform)
            if field:
                setattr(post, field, str(post_id))

    # POSTED needs evidence. This is the line that used to lie.
    post.status = "POSTED" if published else "FAILED"
    post.postedAt = utc_now()
    if errors:
        post.errorLog = " | ".join(errors)[:500]
    elif not published:
        post.errorLog = "Nothing published."
    else:
        post.errorLog = None


class _PlatformSkip(Exception):
    """This platform cannot take this post, and that is not an error."""


async def _publish_to(platform, workspace_id, caption, media_urls, website, *, explicit):
    """One publish call. Raises _PlatformSkip when the platform's own rules
    make the post impossible, and lets real failures propagate."""
    from services.multi_publisher import caption_for, _looks_like_video

    text = caption_for(platform, caption, website)

    if platform == "facebook":
        from services.social_service import post_to_facebook
        return await post_to_facebook(workspace_id, message=text, media_urls=media_urls)

    if platform == "instagram":
        # Instagram will not accept a caption on its own.
        if not media_urls:
            if explicit:
                raise RuntimeError("Instagram needs an image or video -- this post had neither.")
            raise _PlatformSkip("no media")
        from services.social_service import post_to_instagram
        return await post_to_instagram(workspace_id, message=text, media_urls=media_urls)

    if platform == "x":
        from services.twitter_service import twitter_service
        return await twitter_service.post_tweet(workspace_id, text, media_urls=media_urls)

    if platform == "linkedin":
        from services.linkedin_service import linkedin_service
        return await linkedin_service.post_text(workspace_id, text, media_urls=media_urls)

    if platform == "youtube":
        video = next((u for u in media_urls if _looks_like_video(u)), None)
        if not video:
            if explicit:
                raise RuntimeError("YouTube needs a video -- this post had none.")
            raise _PlatformSkip("no video")
        from services import youtube_service
        return await youtube_service.upload_video(
            workspace_id, video, title=text,
            description=caption_for("facebook", caption, website),
        )

    raise RuntimeError(f"No publisher for '{platform}'.")


async def daily_linkedin_news() -> None:
    """One LinkedIn post per workspace per day, reacting to industry news.

    WHY A SEPARATE JOB
    ------------------
    The marketing loop runs every couple of hours and publishes media. This is
    daily, text-only, and goes to one platform. Threading it into that loop
    would mean either posting news four times a day or adding a "have I done
    this today" check to a function that already carries enough state.

    WHAT IT COSTS
    -------------
    One model call per workspace per day, and only for workspaces that have
    LinkedIn connected. A workspace with no LinkedIn spends nothing here --
    checked before the news is fetched, not after.

    Never raises. A job that throws can take its next run with it.
    """
    from database import BusinessProfile, SocialPost, utc_now
    from services import news_service
    from services.multi_publisher import connected_platforms

    try:
        async with AsyncSessionLocal() as session:
            profiles = (await session.execute(select(BusinessProfile))).scalars().all()
            candidates = [
                (p.id, p.name, p.userId, bool(getattr(p, "automationPaused", False)))
                for p in profiles
            ]

        posted = 0
        for workspace_id, name, owner_id, paused in candidates:
            if paused:
                continue

            try:
                async with AsyncSessionLocal() as session:
                    available = await connected_platforms(session, workspace_id)
                    if not available.get("linkedin"):
                        continue

                    # One a day. The job runs daily, but a restart re-runs it,
                    # and two takes on the news in one morning reads worse than
                    # none at all.
                    since = utc_now() - timedelta(hours=20)
                    already = (await session.execute(
                        select(SocialPost.id).where(
                            SocialPost.businessProfileId == workspace_id,
                            SocialPost.platform == "LINKEDIN",
                            SocialPost.type == "NEWS",
                            SocialPost.createdAt >= since,
                        ).limit(1)
                    )).scalars().first()
                    if already:
                        continue

                    profile = await session.get(BusinessProfile, workspace_id)
                    if not profile:
                        continue

                    # What this workspace has already said, so the same story
                    # is not covered twice in a week.
                    recent = (await session.execute(
                        select(SocialPost.caption)
                        .where(SocialPost.businessProfileId == workspace_id)
                        .order_by(SocialPost.createdAt.desc()).limit(30)
                    )).scalars().all()

                stories = await news_service.fetch(profile, limit=5)
                if not stories:
                    logger.info(f"[NEWS] No fresh stories for {name}")
                    continue

                blob = " ".join(c or "" for c in recent).lower()
                fresh = [s for s in stories if s["title"].lower()[:45] not in blob]
                if not fresh:
                    continue

                # The angle rotates with the day, so a week of posts is five
                # different kinds of take rather than five summaries.
                angle = utc_now().timetuple().tm_yday % len(news_service.ANGLES)
                post = await news_service.linkedin_post_from_news(
                    profile, fresh[0], angle_index=angle
                )
                if not post:
                    continue

                async with AsyncSessionLocal() as session:
                    session.add(SocialPost(
                        userId=owner_id,
                        businessProfileId=workspace_id,
                        platform="LINKEDIN",
                        # Marked so tomorrow's run can tell that today's went
                        # out, and so the activity log can say what it was.
                        type="NEWS",
                        status="SCHEDULED",
                        caption=post["content"],
                        scheduledAt=utc_now() + timedelta(minutes=15),
                    ))
                    await session.commit()

                posted += 1
                logger.info(f"[NEWS] Queued a LinkedIn post for {name}: {post['source_title'][:60]}")

            except Exception as e:
                # One workspace failing must not stop the rest.
                logger.warning(f"[NEWS] {name} skipped: {e}")

        if posted:
            logger.info(f"[NEWS] {posted} LinkedIn posts queued")
    except Exception as e:
        logger.error(f"[NEWS] Loop exception: {e}")


async def _run_media_sweep() -> None:
    """Daily sweep, never raising into the scheduler.

    A job that throws takes its next run with it in some APScheduler
    configurations, and a catalog check failing must never be the reason
    posting stops.
    """
    try:
        from services.media_health import sweep

        result = await sweep()
        if result["retired"]:
            logger.warning(
                f"[MEDIA SWEEP] Retired {result['retired']} asset(s) whose files "
                f"are gone; {result['unreachable']} could not be checked."
            )
    except Exception as e:
        logger.error(f"[MEDIA SWEEP] failed: {e}")


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
        execute_due_scheduled_posts,
        trigger=IntervalTrigger(minutes=1),
        id="scheduled_posts_loop",
        name="1-Minute Scheduled Posts Publisher",
        replace_existing=True,
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

    # Prune posts older than 15 days that never reached 100 views. Daily
    # rather than hourly: the input only changes on the scale of days, and a
    # job that DELETES published content should run as seldom as it can while
    # still doing its work.
    # Daily, in the morning. News is stale by the afternoon and a take on
    # yesterday's story reads as an account that is not paying attention.
    scheduler.add_job(
        daily_linkedin_news,
        trigger=IntervalTrigger(hours=24),
        id="daily_linkedin_news",
        name="Daily LinkedIn News Post",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        _run_post_cleanup,
        trigger=IntervalTrigger(hours=24),
        id="post_cleanup",
        name="Daily Post Cleanup",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Retire assets whose files no longer exist. Daily, and deliberately not
    # more often: it is an outbound probe against a CDN, and the failures it
    # must NOT act on -- rate limits, timeouts -- are exactly what hammering
    # one would produce.
    scheduler.add_job(
        _run_media_sweep,
        trigger=IntervalTrigger(hours=24),
        id="media_health_sweep",
        name="Daily Media Reachability Sweep",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    logger.info(
        f"APScheduler initialized (Marketing Loop: {MARKETING_LOOP_MINUTES}m, "
        f"Scheduled Posts: 1m, Creative Loop: 2h, Post Cleanup: 24h)"
    )
    return scheduler


async def _run_post_cleanup() -> None:
    """Daily cleanup, wrapped so a failure cannot take the scheduler down."""
    try:
        from services.post_cleanup import run_cleanup

        results = await run_cleanup()
        for outcome in results:
            if outcome.get("deleted") or outcome.get("note"):
                logger.info(
                    f"[CLEANUP] {outcome.get('name')}: "
                    f"{outcome.get('deleted', 0)} deleted of "
                    f"{outcome.get('found', 0)} found. {outcome.get('note', '')}"
                )
    except Exception as e:
        logger.error(f"[CLEANUP] Daily post cleanup failed: {e}")


def shutdown_scheduler(scheduler: AsyncIOScheduler) -> None:
    """Gracefully shut down the APScheduler instance."""
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler shut down successfully")

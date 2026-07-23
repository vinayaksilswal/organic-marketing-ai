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
    logger.info("[MARKETING LOOP] Starting autonomous marketing cycle")
    logger.info("=" * 60)

    try:
        async with AsyncSessionLocal() as session:
            stmt = select(BusinessProfile).where(BusinessProfile.brandAnalysisComplete == True)
            profiles = (await session.execute(stmt)).scalars().all()

            for profile in profiles:
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

                logger.info(f"[MARKETING LOOP] Processing workspace {profile.id} ({profile.name})")
                
                campaign = await _get_next_campaign_for_workspace(session, profile)
                if not campaign:
                    logger.info(f"[MARKETING LOOP] No active campaigns for workspace {profile.id}")
                    continue

                auto_approve = getattr(profile, 'autoGenerateCreatives', True)
                
                caption: str = ""
                email_subject: str = ""
                email_text: str = ""
                email_html: str = ""
                social_errors: list[str] = []
                email_errors: list[str] = []

                try:
                    caption = await generate_campaign_variation(campaign.baseCaption)
                    email_content = await generate_campaign_email(campaign)
                    email_subject = email_content.get("subject", "Organic Marketing AI Update")
                    email_text = email_content.get("bodyText", "")
                    email_html = email_content.get("bodyHtml", "")
                except Exception as e:
                    logger.error(f"[MARKETING LOOP] AI generation failed: {e}")
                    caption = campaign.baseCaption
                    email_subject = "Organic Marketing AI Update"
                    email_text = campaign.baseCaption
                    email_html = f"<p>{campaign.baseCaption}</p>"

                vid_url = campaign.mediaUrl
                if vid_url.startswith("/"):
                    vid_url = f"https://organicmarketing.ai{vid_url}"

                post_obj = SocialPost(
                    userId=campaign.userId,
                    campaignId=campaign.id,
                    platform="BOTH",
                    type="AUTO",
                    caption=caption,
                    mediaUrls=[vid_url],
                    status="POSTED" if auto_approve else "PENDING_APPROVAL",
                    scheduledAt=utc_now(),
                )
                session.add(post_obj)
                await session.flush()
                
                if auto_approve:
                    # FB
                    try:
                        fb_res = await post_to_facebook(caption, vid_url, campaign.mediaType)
                        if fb_res.get("success"):
                            post_obj.fbPostId = fb_res.get("post_id")
                        else:
                            social_errors.append(f"FB: {fb_res.get('error')}")
                    except Exception as e:
                        social_errors.append(f"FB exception: {e}")

                    # IG
                    try:
                        ig_res = await post_to_instagram(caption, vid_url, campaign.mediaType)
                        if ig_res.get("success"):
                            post_obj.igPostId = ig_res.get("post_id")
                        else:
                            social_errors.append(f"IG: {ig_res.get('error')}")
                    except Exception as e:
                        social_errors.append(f"IG exception: {e}")

                    # Twitter
                    try:
                        tw_res = await twitter_service.post_tweet(caption, [vid_url] if vid_url else None)
                        if tw_res.get("success"):
                            post_obj.twitterPostId = tw_res.get("tweet_id")
                    except Exception as e:
                        social_errors.append(f"Twitter: {e}")

                    # LinkedIn
                    try:
                        li_res = await linkedin_service.post_share(caption, vid_url if vid_url else None)
                        if li_res.get("success"):
                            post_obj.linkedinPostId = li_res.get("post_id")
                    except Exception as e:
                        social_errors.append(f"LinkedIn: {e}")

                    post_obj.postedAt = utc_now()
                    if social_errors:
                        post_obj.errorLog = "; ".join(social_errors)

                email_count = 0
                try:
                    email_res = await send_email_blast(subject=email_subject, body_html=email_html, body_text=email_text, user_id=campaign.userId)
                    if email_res.get("success"):
                        email_count = email_res.get("sent_count", 0)
                    else:
                        email_errors.append(f"Email: {email_res.get('error')}")
                except Exception as e:
                    email_errors.append(f"Email exception: {e}")

                email_obj = EmailCampaign(
                    userId=campaign.userId,
                    campaignId=campaign.id,
                    status="SENT" if email_count > 0 else "FAILED",
                    subject=email_subject,
                    bodyText=email_text,
                    bodyHtml=email_html,
                    scheduledAt=utc_now(),
                    sentAt=utc_now() if email_count > 0 else None,
                    recipientCount=email_count,
                    errorLog="; ".join(email_errors) if email_errors else None,
                )
                session.add(email_obj)
            
            await session.commit()
    except Exception as e:
        logger.error(f"[MARKETING LOOP] Loop exception: {e}")

    logger.info("=" * 60)
    logger.info("[MARKETING LOOP] Cycle complete")
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
        trigger=IntervalTrigger(hours=1),
        id="marketing_loop",
        name="Autonomous 1-Hour Marketing Loop",
        replace_existing=True,
    )

    scheduler.add_job(
        execute_creative_generation_loop,
        trigger=IntervalTrigger(hours=1),
        id="creative_generation_loop",
        name="Autonomous 1-Hour Creative Generation Loop",
        replace_existing=True,
    )

    scheduler.add_job(
        execute_arxiv_newsroom_loop,
        trigger=IntervalTrigger(hours=2),
        id="arxiv_newsroom_loop",
        name="Autonomous 2-Hour arXiv Newsroom Loop",
        replace_existing=True,
    )

    logger.info("APScheduler initialized (Marketing Loop: 1h, Creative Loop: 1h, Arxiv Loop: 2h)")
    return scheduler


def shutdown_scheduler(scheduler: AsyncIOScheduler) -> None:
    """Gracefully shut down the APScheduler instance."""
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler shut down successfully")


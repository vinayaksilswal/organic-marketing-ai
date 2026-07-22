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
# Campaign Rotation — Sequential Round-Robin (User-Scoped)
# =============================================================================
async def _get_next_campaign(user_id: Optional[str] = None) -> SocialCampaign | None:
    """Get the next active campaign in the sequential rotation using SQLAlchemy session."""
    async with AsyncSessionLocal() as session:
        # Find active campaigns
        query = select(SocialCampaign).where(SocialCampaign.isActive == True).order_by(SocialCampaign.createdAt.asc())
        if user_id:
            query = query.where(SocialCampaign.userId == user_id)

        res = await session.execute(query)
        campaigns = res.scalars().all()

        if not campaigns:
            logger.info("No active campaigns in database for marketing rotation")
            return None

        # Find or create marketing state
        state_query = select(MarketingState)
        if user_id:
            state_query = state_query.where(MarketingState.userId == user_id)
        
        state_res = await session.execute(state_query)
        state = state_res.scalars().first()

        if not state:
            target_user_id = user_id
            if not target_user_id:
                u_res = await session.execute(select(User))
                first_user = u_res.scalars().first()
                if first_user:
                    target_user_id = first_user.id

            if not target_user_id:
                logger.warning("No users exist yet — skipping marketing rotation")
                return None

            state = MarketingState(userId=target_user_id, lastSocialIdx=0, lastEmailIdx=0, autoApprove=False)
            session.add(state)
            await session.commit()
            await session.refresh(state)

        next_idx = state.lastSocialIdx + 1
        if next_idx >= len(campaigns):
            next_idx = 0

        state.lastSocialIdx = next_idx
        await session.commit()

        selected = campaigns[next_idx]
        logger.info(f"Marketing rotation: selected campaign [{next_idx}/{len(campaigns)}] → {selected.id}")
        return selected


# =============================================================================
# The Autonomous Marketing Loop — Runs Every 6 Hours
# =============================================================================
async def execute_marketing_loop(user_id: Optional[str] = None) -> None:
    """The unified 6-hour autonomous marketing loop executing via SQLAlchemy."""
    logger.info("=" * 60)
    logger.info("[MARKETING LOOP] Starting autonomous marketing cycle")
    logger.info("=" * 60)

    async with AsyncSessionLocal() as session:
        try:
            await session.execute(text("SELECT 1"))
        except Exception as e:
            logger.warning(f"[MARKETING LOOP] Database ping check: {e}")

    campaign = await _get_next_campaign(user_id=user_id)
    if not campaign:
        logger.info("[MARKETING LOOP] No active campaigns available — skipping cycle")
        return

    auto_approve = False
    async with AsyncSessionLocal() as session:
        state_stmt = select(MarketingState)
        if campaign.userId:
            state_stmt = state_stmt.where(MarketingState.userId == campaign.userId)
        st_res = await session.execute(state_stmt)
        st = st_res.scalars().first()
        if st:
            auto_approve = st.autoApprove

    logger.info(f"[MARKETING LOOP] Auto-Approve is {'ON' if auto_approve else 'OFF'}")

    caption: str = ""
    email_subject: str = ""
    email_text: str = ""
    email_html: str = ""
    fb_post_id: str | None = None
    ig_post_id: str | None = None
    tw_post_id: str | None = None
    li_post_id: str | None = None
    social_errors: list[str] = []
    email_errors: list[str] = []

    try:
        caption = await generate_campaign_variation(campaign.baseCaption)
        email_content = await generate_campaign_email(campaign)
        email_subject = email_content.get("subject", "Organic Marketing AI Update")
        email_text = email_content.get("bodyText", "")
        email_html = email_content.get("bodyHtml", "")
        logger.info("[MARKETING LOOP] ✓ AI campaign content generated")
    except Exception as e:
        logger.error(f"[MARKETING LOOP] AI generation failed: {e}")
        caption = campaign.baseCaption
        email_subject = "Organic Marketing AI Update"
        email_text = campaign.baseCaption
        email_html = f"<p>{campaign.baseCaption}</p>"

    vid_url = campaign.mediaUrl
    if vid_url.startswith("/"):
        vid_url = f"https://organicmarketing.ai{vid_url}"

    # Create SocialPost draft in SQLAlchemy
    social_post_id = None
    async with AsyncSessionLocal() as session:
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
        await session.commit()
        await session.refresh(post_obj)
        social_post_id = post_obj.id

    if auto_approve:
        logger.info("[MARKETING LOOP] Publishing social post (Auto-Approve ON)...")
        # Facebook
        try:
            fb_res = await post_to_facebook(caption, vid_url, campaign.mediaType)
            if fb_res.get("success"):
                fb_post_id = fb_res.get("post_id")
                logger.info(f"[MARKETING LOOP] ✓ Posted to Facebook: {fb_post_id}")
            else:
                social_errors.append(f"FB: {fb_res.get('error')}")
        except Exception as e:
            social_errors.append(f"FB exception: {e}")

        # Instagram
        try:
            ig_res = await post_to_instagram(caption, vid_url, campaign.mediaType)
            if ig_res.get("success"):
                ig_post_id = ig_res.get("post_id")
                logger.info(f"[MARKETING LOOP] ✓ Posted to Instagram: {ig_post_id}")
            else:
                social_errors.append(f"IG: {ig_res.get('error')}")
        except Exception as e:
            social_errors.append(f"IG exception: {e}")

        # Twitter
        try:
            tw_res = await twitter_service.post_tweet(caption, [vid_url] if vid_url else None)
            if tw_res.get("success"):
                tw_post_id = tw_res.get("tweet_id")
                logger.info(f"[MARKETING LOOP] ✓ Posted to Twitter: {tw_post_id}")
        except Exception as e:
            social_errors.append(f"Twitter: {e}")

        # LinkedIn
        try:
            li_res = await linkedin_service.post_share(caption, vid_url if vid_url else None)
            if li_res.get("success"):
                li_post_id = li_res.get("post_id")
                logger.info(f"[MARKETING LOOP] ✓ Posted to LinkedIn: {li_post_id}")
        except Exception as e:
            social_errors.append(f"LinkedIn: {e}")

        # Update SocialPost record with results
        async with AsyncSessionLocal() as session:
            stmt = select(SocialPost).where(SocialPost.id == social_post_id)
            p_res = await session.execute(stmt)
            p_obj = p_res.scalar_one_or_none()
            if p_obj:
                p_obj.fbPostId = fb_post_id
                p_obj.igPostId = ig_post_id
                p_obj.twitterPostId = tw_post_id
                p_obj.linkedinPostId = li_post_id
                p_obj.postedAt = utc_now()
                if social_errors:
                    p_obj.errorLog = "; ".join(social_errors)
                await session.commit()
    else:
        logger.info("[MARKETING LOOP] Social post created as PENDING_APPROVAL")

    # Send Email Blast
    email_count = 0
    try:
        email_res = await send_email_blast(
            subject=email_subject,
            body_html=email_html,
            body_text=email_text,
            user_id=campaign.userId,
        )
        if email_res.get("success"):
            email_count = email_res.get("sent_count", 0)
            logger.info(f"[MARKETING LOOP] ✓ Email blast sent to {email_count} recipients")
        else:
            email_errors.append(f"Email: {email_res.get('error')}")
    except Exception as e:
        email_errors.append(f"Email exception: {e}")

    # Create EmailCampaign record in SQLAlchemy
    async with AsyncSessionLocal() as session:
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

    logger.info("=" * 60)
    logger.info("[MARKETING LOOP] 6-hour autonomous cycle complete")
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
# Scheduler Lifecycle Management
# =============================================================================
def create_scheduler() -> AsyncIOScheduler:
    """Create and configure the APScheduler AsyncIOScheduler instance."""
    scheduler = AsyncIOScheduler(timezone="UTC")

    scheduler.add_job(
        execute_marketing_loop,
        trigger=IntervalTrigger(hours=6),
        id="marketing_loop",
        name="Autonomous 6-Hour Marketing Loop",
        replace_existing=True,
    )

    scheduler.add_job(
        execute_arxiv_newsroom_loop,
        trigger=IntervalTrigger(hours=2),
        id="arxiv_newsroom_loop",
        name="Autonomous 2-Hour arXiv Newsroom Loop",
        replace_existing=True,
    )

    logger.info("APScheduler initialized (Marketing Loop: 6h, Arxiv Loop: 2h)")
    return scheduler


def shutdown_scheduler(scheduler: AsyncIOScheduler) -> None:
    """Gracefully shut down the APScheduler instance."""
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler shut down successfully")

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
    Product,
    SocialCampaign,
    SocialPost,
    init_db,
    close_db,
)
from services.ai_service import generate_campaign_variation
from services.social_service import post_to_facebook, post_to_instagram
from services import multi_publisher
from services.twitter_service import twitter_service
from services.linkedin_service import linkedin_service
from services.crypto_service import decrypt_token


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
            autoApprove=False,
        )
        session.add(state)
        await session.flush()

    next_idx = state.lastSocialIdx + 1
    if next_idx >= len(campaigns):
        next_idx = 0

    state.lastSocialIdx = next_idx
    return campaigns[next_idx]


async def _get_next_product_for_workspace(
    session: Any, profile: BusinessProfile
) -> Product | None:
    """Get the next product for a specific workspace using round-robin."""
    query = (
        select(Product)
        .where(Product.businessProfileId == profile.id)
        .order_by(Product.createdAt.asc())
    )

    res = await session.execute(query)
    products = res.scalars().all()

    if not products:
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
            lastProductIdx=0,
            autoApprove=False,
        )
        session.add(state)
        await session.flush()

    # Need to check if lastProductIdx is present on MarketingState, else default to 0
    current_idx = getattr(state, "lastProductIdx", 0)
    next_idx = current_idx + 1
    if next_idx >= len(products):
        next_idx = 0

    state.lastProductIdx = next_idx
    return products[next_idx]

async def _select_media_for_post(session: Any, profile: BusinessProfile) -> str | None:
    """Backwards-compatible wrapper returning just the URL."""
    media = await _select_media_object_for_post(session, profile)
    return media.url if media else None


async def _select_media_object_for_post(
    session: Any, profile: BusinessProfile
) -> Any:
    """
    Select the best media asset from the workspace's Media catalog.
    Prioritizes AI-generated, unused media. Falls back to any available media.

    Returns the Media row, not just its URL: the caption writer needs the
    asset's description to write about what is actually on screen.
    """
    # This used to cap candidates at the 20 newest and compare them against the
    # 20 most recent posts, then fall back to `all_media[0]` when everything in
    # that window looked used. That fallback is not a rotation: index 0 is the
    # newest asset, so once the window filled, every subsequent run published
    # the same asset indefinitely. Anything older than the 20th asset was also
    # permanently unreachable.
    from services.media_rotation import select_next_media

    media = await select_next_media(
        session, profile.id, prefer_ai_generated=True
    )
    if media is not None:
        await _ensure_media_has_sound(session, media, profile.id)
    return media


async def _ensure_media_has_sound(session: Any, media: Any, workspace_id: str) -> None:
    """Give a silent clip a music bed before it is posted, if one is available.

    Instagram's own music picker exists only inside the app — the Content
    Publishing API has no field for a track — so a silent clip published
    automatically stays silent forever. This is the only point where that can
    be fixed without a human opening their phone.

    Done here rather than during branding because muxing onto a finished clip
    copies the video stream instead of re-encoding it: 21MB and half a second,
    against 311MB and thirty seconds. It also means tracks uploaded next month
    still reach clips branded today.
    """
    from sqlalchemy import select

    from database import Media
    from services.video_outro import add_music_at_url, stable_choice

    if not (media.mimeType or "").startswith("video/"):
        return
    # None means nobody has probed it yet, and guessing wrong would either skip
    # a silent clip or overwrite a clip that has speech. Branding fills this in.
    if media.hasAudio is not False:
        return

    tracks = [
        (m.id, m.url) for m in (await session.execute(
            select(Media).where(
                Media.businessProfileId == workspace_id,
                Media.mimeType.like("audio/%"),
                Media.isActive.is_(True),
            )
        )).scalars().all() if m.url
    ]
    if not tracks:
        logger.info(
            "Media has no audio and the workspace has no music tracks; "
            "posting it silent"
        )
        return

    # Hashed on the clip so the rotation spreads across the library rather than
    # putting one song on every post.
    chosen = stable_choice(tracks, media.id)
    scored = await add_music_at_url(media.url, chosen[1], workspace_id, media.id)
    if not scored:
        return

    # Persisted so the work happens once per clip rather than once per post.
    media.url = scored
    media.hasAudio = True
    await session.commit()


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

            # Deterministic pick: duplicates used to make this a coin flip
            # against whichever row the settings toggle had written.
            state_stmt = (
                select(MarketingState)
                .where(MarketingState.businessProfileId == workspace_id)
                .order_by(MarketingState.createdAt.asc())
            )
            state = (await session.execute(state_stmt)).scalars().first()
            # No state row means the owner has never enabled anything. Default
            # to drafting, never to publishing.
            auto_approve = bool(state.autoApprove) if state else False

            # Only some branches below set these. Initialise them here so the
            # shared caption path cannot hit an UnboundLocalError — the same
            # class of bug that `campaign` vs `campaign_id` caused.
            media_obj = None
            product = None

            if profile.businessModel == "E-commerce" and getattr(profile, "productCatalogUrl", None):
                # E-commerce Flow: Pick a product and generate a post
                product = await _get_next_product_for_workspace(session, profile)
                if not product:
                    logger.info(f"No products found for E-commerce workspace {workspace_id}. Falling back to standard campaign.")
                    campaign = await _get_next_campaign_for_workspace(session, profile)
                    if not campaign:
                        return "no_campaigns"
                    media_obj = await _select_media_object_for_post(session, profile)
                    media_url = media_obj.url if media_obj else None
                    if not media_url and campaign.mediaUrl:
                        media_url = campaign.mediaUrl
                    media_urls = [media_url] if media_url else []
                    
                    prompt = (
                        f"You are a world-class, enterprise-grade copywriter for {profile.name} (Industry: {profile.industry or 'General'}).\n"
                        f"Business Description: {profile.description or 'No description provided.'}\n"
                        f"Target Audience: {profile.targetAudience or 'General audience'}\n"
                        f"Tone of Voice: {profile.toneOfVoice or 'Professional'}\n"
                        f"Content Pillars: {', '.join(profile.contentPillars or [])}\n"
                        f"Base Idea: {campaign.baseCaption}\n\n"
                        "Instructions: Write a high-converting social media post following the AIDA (Attention, Interest, Desire, Action) framework.\n"
                        "1. Start with a scroll-stopping hook.\n"
                        "2. Provide compelling value and build desire.\n"
                        "3. End with a strong, actionable Call-To-Action (CTA).\n"
                        f"Include 3-5 relevant hashtags from: {', '.join(profile.suggestedHashtags or ['#business', '#growth'])}.\n"
                        "Make it sound natural, professional, and use emojis appropriately."
                    )
                    fallback_caption = campaign.baseCaption
                    campaign_id = campaign.id
                else:
                    logger.info(f"Selected product {product.id} ({product.title}) for workspace {workspace_id}")
                    # The product's own image is the subject here, not a catalog
                    # asset — so there is no Media row to describe.
                    media_obj = None
                    media_urls = []
                    if getattr(product, "videoUrl", None):
                        media_urls.append(product.videoUrl)
                    elif product.imageUrl:
                        media_urls.append(product.imageUrl)
                        
                    price_info = f" Price: ${product.price}." if getattr(product, "price", None) else ""
                    prompt = (
                        f"You are an elite, enterprise-grade e-commerce copywriter for {profile.name} (Industry: {profile.industry or 'E-commerce'}).\n"
                        f"Business Description: {profile.description or 'No description provided.'}\n"
                        f"Target Audience: {profile.targetAudience or 'General audience'}\n"
                        f"Tone of Voice: {profile.toneOfVoice or 'Persuasive & Excited'}\n"
                        f"Product Name: {product.title}\n"
                        f"Product Description: {product.description or 'A high quality product.'}{price_info}\n\n"
                        "Instructions: Write a high-converting product highlight post following the PAS (Problem, Agitate, Solution) framework.\n"
                        "1. Hook the reader with a relevant problem or strong desire.\n"
                        "2. Highlight how this product solves it flawlessly.\n"
                        "3. End with an urgent and clear Call-To-Action to buy now.\n"
                        "Never write a URL in the caption — Instagram does not make them "
                        "clickable, so a raw link reads as spam. Say 'link in bio' instead.\n"
                        f"Include 3-5 relevant hashtags from: {', '.join(profile.suggestedHashtags or ['#ecommerce', '#musthave'])}."
                    )
                    fallback_caption = f"Check out our {product.title} — link in bio."
                    # Use a dummy campaign ID or the first active one if required by DB schema
                    dummy_campaign = await _get_next_campaign_for_workspace(session, profile)
                    if dummy_campaign:
                        campaign_id = dummy_campaign.id
                    else:
                        dummy_campaign = SocialCampaign(
                            userId=profile.userId,
                            businessProfileId=profile.id,
                            baseCaption="[Automated Product Highlight]",
                            mediaUrl="",
                            isActive=True
                        )
                        session.add(dummy_campaign)
                        await session.flush()
                        campaign_id = dummy_campaign.id

            elif profile.businessModel == "AI Influencer":
                # AI Influencer Flow: Use character chart/reference
                #
                # Same rule as the standard flow: a campaign is a base idea,
                # not a precondition. A persona workspace built by importing a
                # folder has media and no campaigns, and would otherwise stop
                # dead exactly as the Social Page workspaces did.
                campaign = await _get_next_campaign_for_workspace(session, profile)
                media_obj = await _select_media_object_for_post(session, profile)
                if not campaign and not media_obj and not getattr(profile, "influencerReferenceUrl", None):
                    logger.info(
                        f"Workspace {workspace_id} has no campaigns, no media and no "
                        f"character reference, so there is nothing to publish."
                    )
                    return "no_campaigns"

                if campaign:
                    logger.info(f"Selected campaign {campaign.id} for AI Influencer workspace {workspace_id}")

                media_url = media_obj.url if media_obj else None
                if getattr(profile, "influencerReferenceUrl", None):
                    # If they have a reference URL, prioritize it if we don't have fresh media
                    if not media_url:
                        media_url = profile.influencerReferenceUrl
                elif not media_url and campaign and campaign.mediaUrl:
                    media_url = campaign.mediaUrl

                media_urls = [media_url] if media_url else []

                influencer_idea = (
                    campaign.baseCaption if campaign
                    else (media_obj.caption or media_obj.prompt if media_obj else None)
                    or f"A moment in the life of {profile.name}"
                )

                char_reference = f"\nCHARACTER VISUAL REFERENCE URL: {profile.influencerReferenceUrl}" if getattr(profile, "influencerReferenceUrl", None) else ""
                
                prompt = (
                    f"You are a top-tier digital persona and AI Influencer named {profile.name}.\n"
                    f"Tone of Voice: {profile.toneOfVoice or 'Authentic & Playful'}\n"
                    f"Persona Description: {profile.description or 'No description provided.'}\n"
                    f"Target Audience: {profile.targetAudience or 'General audience'}\n"
                    f"Content Pillars: {', '.join(profile.contentPillars or [])}\n"
                    f"Base Idea: {influencer_idea}\n"
                    f"{char_reference}\n\n"
                    "Instructions: Write a highly authentic, first-person social media post. Focus on building parasocial connection with the audience.\n"
                    "1. Start with an engaging, conversational hook.\n"
                    "2. Share a personal thought, lifestyle moment, or relatable story.\n"
                    "3. End with a question or community-driven CTA to encourage comments and engagement.\n"
                    f"Include 3-5 hashtags naturally at the bottom from: {', '.join(profile.suggestedHashtags or ['#aiinfluencer', '#lifestyle'])}."
                )
                fallback_caption = influencer_idea
                campaign_id = campaign.id if campaign else None

            else:
                # Standard Flow: a campaign if there is one, the catalog if not.
                #
                # A campaign contributes exactly two things here: a base idea
                # for the caption prompt, and a fallback image when the catalog
                # is empty. Neither is essential when the workspace has media.
                #
                # Requiring one silently stopped every Social Page workspace.
                # Those are built by bulk-importing a folder, which never
                # creates campaigns, so the task returned "no_campaigns" in
                # seconds and wrote nothing -- no post, no error, and no
                # advance to the last-posted time, so it repeated every cycle
                # forever. Three businesses holding 5631 finished assets
                # between them published nothing for hours while two others on
                # the same loop posted normally. The only difference was
                # whether a campaign row happened to exist.
                campaign = await _get_next_campaign_for_workspace(session, profile)
                media_obj = await _select_media_object_for_post(session, profile)

                if not campaign and not media_obj:
                    logger.info(
                        f"Workspace {workspace_id} has no campaigns and no postable "
                        f"media, so there is nothing to publish."
                    )
                    return "no_campaigns"

                media_url = media_obj.url if media_obj else None
                if campaign:
                    logger.info(f"Selected campaign {campaign.id} for workspace {workspace_id}")
                    base_idea = campaign.baseCaption
                    campaign_id = campaign.id
                    if not media_url and campaign.mediaUrl:
                        media_url = campaign.mediaUrl
                else:
                    # The asset's own description is a better base idea than a
                    # campaign line anyway: it describes what is actually in
                    # the picture, which is what the caption should talk about.
                    base_idea = (
                        media_obj.caption
                        or media_obj.prompt
                        or f"A post for {profile.name}"
                    )
                    campaign_id = None
                    logger.info(
                        f"No campaigns for workspace {workspace_id}; posting from "
                        f"the media catalog using the asset's own description"
                    )

                media_urls = [media_url] if media_url else []

                # 3. Generate fresh AI caption
                prompt = (
                    f"You are a world-class, enterprise-grade copywriter for {profile.name} (Industry: {profile.industry or 'General'}).\n"
                    f"Business Description: {profile.description or 'No description provided.'}\n"
                    f"Target Audience: {profile.targetAudience or 'General audience'}\n"
                    f"Tone of Voice: {profile.toneOfVoice or 'Professional'}\n"
                    f"Content Pillars: {', '.join(profile.contentPillars or [])}\n"
                    f"Base Idea: {base_idea}\n\n"
                    "Instructions: Write a high-converting social media post following the AIDA (Attention, Interest, Desire, Action) framework.\n"
                    "1. Start with a scroll-stopping hook.\n"
                    "2. Provide compelling value and build desire.\n"
                    "3. End with a strong, actionable Call-To-Action (CTA).\n"
                    f"Include 3-5 relevant hashtags from: {', '.join(profile.suggestedHashtags or ['#business', '#growth'])}.\n"
                    "Make it sound natural, professional, and use emojis appropriately."
                )
                fallback_caption = base_idea

            # Caption generation. The scheduled loop used to build its own
            # inline prompt from campaign.baseCaption, which meant unattended
            # posts — the large majority — were written without ever knowing
            # what the visual showed, without the business's primary offer, and
            # without the no-URL rule. The manual "Run Automation" button used
            # a much better writer. Both now share one path.
            from routers.marketing import _generate_post_caption, _strip_urls

            final_caption = None

            # A folder carousel can carry a caption the user wrote for the set
            # as a whole. Six slides telling one story rarely read well under a
            # caption generated from slide one alone, so when the user has
            # written one it wins outright.
            folder_caption = None
            if media_obj is not None and getattr(media_obj, "folderId", None):
                try:
                    from database import MediaFolder

                    folder = await session.get(MediaFolder, media_obj.folderId)
                    folder_caption = (getattr(folder, "caption", None) or "").strip() or None
                except Exception as e:
                    logger.debug(f"Could not read folder caption: {e}")

            try:
                if folder_caption:
                    final_caption = folder_caption
                elif media_obj is not None or product is not None:
                    final_caption = await _generate_post_caption(
                        profile, media_obj, product=product
                    )
                else:
                    # Nothing visual to describe — fall back to the campaign's
                    # own idea, which is all the context that exists.
                    final_caption = await generate_campaign_variation(prompt)
            except Exception as e:
                logger.warning(f"AI caption generation failed, using base caption: {e}")
                final_caption = None

            if not final_caption or len(final_caption) < 10:
                final_caption = fallback_caption

            # Backstop the no-links rule even on the fallback paths.
            final_caption = _strip_urls(final_caption) or fallback_caption

            # Last gate before anything reaches a public account. Seventy-eight
            # captions went out declaring these pages as adult content in
            # plain text; Meta acts on caption text alone, and the app's
            # standing is shared by every workspace publishing through it.
            from services.caption_policy import enforce as enforce_caption_policy

            asset_description = (
                (media_obj.caption or media_obj.prompt or "") if media_obj else ""
            )
            final_caption, violations = enforce_caption_policy(
                final_caption, asset_description, workspace=profile.name
            )
            if violations and not final_caption:
                # Nothing safe to say about this asset. One empty slot in a
                # schedule is cheaper than one actioned app.
                logger.error(
                    f"Skipping post for {profile.name}: caption and asset "
                    f"description both contain {violations}"
                )
                return "blocked_by_caption_policy"

            # A folder in the media catalog is ONE post carrying every file in
            # it, so the chosen asset expands into its siblings here — after
            # every branch above has settled on an asset and before anything is
            # published. Instagram builds the carousel itself from multiple
            # image URLs, so no separate carousel path is needed.
            #
            # Rotation already collapsed the folder to a single candidate, so
            # this cannot make a folder post more often than a loose file.
            if media_obj is not None and getattr(media_obj, "folderId", None):
                from services.media_rotation import expand_to_group

                slides = await expand_to_group(session, media_obj)
                if len(slides) > 1:
                    media_urls = [s.url for s in slides if s.url]
                    logger.info(
                        f"Workspace {workspace_id}: posting folder "
                        f"{media_obj.folderId} as one carousel of "
                        f"{len(media_urls)} slides"
                    )

            # 4. Post to all platforms
            fb_post_id = None
            ig_post_id = None
            x_post_id = None
            li_post_id = None

            # The plan is checked HERE, at the only point where the automation
            # actually publishes on someone's behalf.
            #
            # Manual posting through the API has always been metered. This path
            # never was -- so the free tier advertised "5 published posts a
            # month" while the scheduler published every one to four hours,
            # indefinitely, unmetered. The single capability the subscription
            # exists to sell was the only one given away without limit, which
            # leaves no reason to ever upgrade.
            #
            # Over quota is not an error: the workspace is working exactly as
            # its plan describes. It records a DRAFT the operator can publish
            # by hand and returns a status the cycle summary reports plainly.
            if auto_approve:
                from services import billing_service as billing

                allowed, why = await billing.check_quota(profile.userId, "posts")
                if not allowed:
                    logger.info(
                        f"Workspace {workspace_id} is over its plan's posting "
                        f"limit; drafting instead of publishing. {why}"
                    )
                    auto_approve = False
                    errors.append(f"Plan limit: {why}")

            if auto_approve:
                # Every platform this workspace has actually connected, each
                # getting the caption shaped for how it is read there.
                #
                # This used to attempt all four unconditionally. A workspace
                # with only Meta connected logged an X failure and a LinkedIn
                # failure on every single post, because the services return
                # None when there is no token. A delivery log where two lines
                # are always red is a log nobody reads.
                outcome = await multi_publisher.publish_everywhere(
                    workspace_id, final_caption, media_urls=media_urls
                )
                for entry in outcome["published"]:
                    platform, post_id = entry["platform"], entry["id"]
                    if platform == "facebook":
                        fb_post_id = post_id
                    elif platform == "instagram":
                        ig_post_id = post_id
                    elif platform == "x":
                        x_post_id = post_id
                    elif platform == "linkedin":
                        li_post_id = post_id
                published_to = [e["platform"] for e in outcome["published"]]
                logger.info(
                    f"Published to {published_to or 'nowhere'}; "
                    f"skipped {outcome['skipped'] or 'none'}"
                )
                for f in outcome["failed"]:
                    errors.append(f"{f['platform']}: {f['error']}")


            # 5. Record the SocialPost (using correct field names!)
            if auto_approve:
                # Success is 'it reached at least one platform'. This used
                # to read Meta only, so a workspace connected to X and
                # LinkedIn alone recorded every delivered post as FAILED
                # and was never charged a post against its plan.
                is_success = any(
                    pid is not None
                    for pid in (fb_post_id, ig_post_id, x_post_id, li_post_id)
                )
                status = "POSTED" if is_success else "FAILED"
                if is_success:
                    # One published post, however many platforms carried it.
                    # Counted only on success, so a failed attempt does not
                    # consume someone's allowance.
                    try:
                        await billing.record_usage(profile.userId, "posts")
                    except Exception as e:
                        logger.warning(f"Could not record post usage: {e}")
            else:
                is_success = True
                status = "DRAFT"

            post = SocialPost(
                id=str(uuid.uuid4()),
                userId=profile.userId,
                businessProfileId=profile.id,
                # Every branch above sets campaign_id; only some set `campaign`.
                # The e-commerce product branch does not, so dereferencing
                # `campaign` here raised UnboundLocalError and killed the whole
                # run for any workspace with a product catalog.
                campaignId=campaign_id,
                platform="ALL",
                type="AUTO",
                caption=final_caption,              # Fixed: was 'content'
                mediaUrls=media_urls,               # Fixed: was 'mediaUrl' (string)
                status=status,
                scheduledAt=utc_now(),
                postedAt=utc_now() if (auto_approve and is_success) else None,
                fbPostId=fb_post_id,
                igPostId=ig_post_id,
                # These two columns have existed since the schema was
                # written and nothing ever wrote to them.
                twitterPostId=x_post_id,
                linkedinPostId=li_post_id,
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

            if auto_approve:
                if is_success:
                    logger.info(
                        f"[ARQ Worker] ✓ Successfully posted for workspace {workspace_id} "
                        f"(FB: {fb_post_id}, IG: {ig_post_id})"
                    )
                else:
                    logger.warning(
                        f"[ARQ Worker] Failed for workspace {workspace_id}: "
                        f"{', '.join(errors)}"
                    )
                    from exceptions import IntegrationError
                    raise IntegrationError(f"Social post failed: {', '.join(errors)}")
            else:
                logger.info(f"[ARQ Worker] ✓ Successfully drafted for workspace {workspace_id}")

            return "success"

    except Exception as e:
        logger.error(f"[ARQ Worker] Task failed with unhandled exception: {e}")
        
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

        raise e


async def auto_populate_workspace_task(ctx: dict, user_id: str, workspace_id: str) -> None:
    """ARQ background task to execute AI onboarding."""
    try:
        from services.creative_service import auto_populate_workspace
        logger.info(f"[ARQ Worker] Executing auto_populate_workspace for {workspace_id}")
        await auto_populate_workspace(user_id, workspace_id)
    except Exception as e:
        logger.error(f"[ARQ Worker] auto_populate_workspace failed: {e}")
        raise e

async def sync_workspace_catalog_task(ctx: dict, workspace_id: str) -> None:
    """ARQ background task to sync product catalog."""
    try:
        from services.catalog_service import sync_workspace_catalog
        logger.info(f"[ARQ Worker] Executing sync_workspace_catalog for {workspace_id}")
        await sync_workspace_catalog(workspace_id)
    except Exception as e:
        logger.error(f"[ARQ Worker] sync_workspace_catalog failed: {e}")
        raise e


async def startup(ctx: dict) -> None:
    logger.info("Starting ARQ Worker...")
    await init_db()


async def shutdown(ctx: dict) -> None:
    logger.info("Shutting down ARQ Worker...")
    await close_db()


class WorkerSettings:
    functions = [
        context_aggregation_task,
        auto_populate_workspace_task,
        sync_workspace_catalog_task,
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 10
    job_timeout = 300  # 5 minute timeout per job

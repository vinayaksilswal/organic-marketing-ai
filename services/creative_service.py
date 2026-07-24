"""
=============================================================================
Organic Marketing AI — AI Creative Service (Enterprise)
=============================================================================
Handles automated brand analysis and creative generation during business
onboarding. Generates brand context, starter content, and AI images/videos.

Content Pipeline:
  1. Brand Analysis → LLM generates industry, audience, tone, pillars
  2. Starter Creatives → LLM generates 3 social post templates
  3. AI Image Generation → Pollinations.ai (free, no key)
  4. Media Storage → Cloudinary (tenant-partitioned)
  5. Campaign Creation → SocialCampaign + Media records in DB

All media is uploaded to Cloudinary under tenants/{workspace_id}/media/
=============================================================================
"""

from __future__ import annotations

import uuid
import json
import urllib.parse
from typing import Any, Dict, List, Optional

from loguru import logger

from database import (
    AsyncSessionLocal,
    BusinessProfile,
    SocialCampaign,
    Media,
    MarketingState,
)
from services.ai_service import generate_campaign_variation


async def _call_llm(prompt: str) -> str:
    """Call the LLM via the existing AI service infrastructure."""
    try:
        from services.ai_service import generate_campaign_variation
        return await generate_campaign_variation(prompt)
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return ""


async def generate_brand_context(profile: BusinessProfile) -> Dict[str, Any]:
    """
    Analyze a business profile and generate comprehensive brand context.
    Returns: industry, targetAudience, toneOfVoice, contentPillars, suggestedHashtags
    """
    niche_hint = f"\nBusiness Niche/Category: {profile.niche}" if getattr(profile, 'niche', None) else ""

    prompt = f"""You are a top-tier Enterprise Marketing Strategist. Analyze this business and generate a highly converting, structured brand context.

Business Name: {profile.name}
Website: {profile.websiteUrl or 'Not provided'}
Description: {profile.description or 'Not provided'}
Business Model: {profile.businessModel or 'General'}{niche_hint}

Return a JSON object with exactly these fields (nothing else, no markdown):
{{
    "industry": "the primary industry this business operates in (e.g. SaaS, E-Commerce, Local Services)",
    "targetAudience": "highly detailed description of the ideal customer persona (2-3 sentences)",
    "toneOfVoice": "one of: Professional, Casual, Bold, Playful, Authoritative, Friendly, Visionary",
    "contentPillars": ["pillar1", "pillar2", "pillar3", "pillar4"],
    "suggestedHashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5"],
    "brandColors": ["#8B5CF6", "#3B82F6"]
}}

Ensure contentPillars are 4 specific, actionable content themes for social media that drive engagement and sales.
Ensure suggestedHashtags are 5 highly relevant, trending hashtags WITH the # prefix."""

    try:
        result = await _call_llm(prompt)
        cleaned = result.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()

        parsed = json.loads(cleaned)
        return {
            "industry": parsed.get("industry", "General"),
            "targetAudience": parsed.get("targetAudience", "Business professionals and entrepreneurs"),
            "toneOfVoice": parsed.get("toneOfVoice", "Professional"),
            "contentPillars": parsed.get("contentPillars", ["Industry News", "Tips & Tricks", "Behind the Scenes", "Customer Stories"]),
            "suggestedHashtags": parsed.get("suggestedHashtags", ["#business", "#marketing", "#growth", "#startup", "#entrepreneur"]),
            "brandColors": parsed.get("brandColors", ["#8B5CF6", "#3B82F6"]),
        }
    except Exception as e:
        logger.warning(f"Brand context generation failed, using defaults: {e}")
        return {
            "industry": "General",
            "targetAudience": "Business professionals and entrepreneurs seeking growth",
            "toneOfVoice": "Professional",
            "contentPillars": ["Industry Insights", "Tips & Guides", "Behind the Scenes", "Success Stories"],
            "suggestedHashtags": ["#business", "#marketing", "#growth", "#startup", "#entrepreneur"],
            "brandColors": ["#8B5CF6", "#3B82F6"],
        }


async def generate_starter_creatives(profile: BusinessProfile) -> List[Dict[str, str]]:
    """
    Generate 3 AI social post templates with captions based on brand context.
    Returns list of {caption, topic, platform} dicts.
    """
    pillars = profile.contentPillars or ["Industry Insights", "Tips", "Behind the Scenes"]
    tone = profile.toneOfVoice or "Professional"
    biz_name = profile.name or "Our Business"
    desc = profile.description or "a business"

    prompt = f"""You are an elite enterprise social media copywriter. Generate exactly 3 highly-converting social media posts for this brand.

Brand: {biz_name}
Description: {desc}
Tone: {tone}
Content Pillars: {', '.join(pillars[:4])}
Hashtags to include: {', '.join((profile.suggestedHashtags or ['#business', '#growth'])[:3])}

Return a JSON array with exactly 3 objects, each with these fields (nothing else, no markdown):
[
    {{"caption": "A compelling, hook-driven post text with emojis, clear value proposition, and hashtags (3-5 sentences). It must drive engagement.", "topic": "Content pillar name", "platform": "BOTH"}},
    {{"caption": "...", "topic": "...", "platform": "BOTH"}},
    {{"caption": "...", "topic": "...", "platform": "BOTH"}}
]

Make each post highly engaging, authentic, and ready to publish to a professional audience. Include relevant emojis and 3-5 hashtags. End with a clear call to action (CTA)."""

    try:
        result = await _call_llm(prompt)
        cleaned = result.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()

        posts = json.loads(cleaned)
        if isinstance(posts, list):
            return [
                {
                    "caption": p.get("caption", ""),
                    "topic": p.get("topic", "General"),
                    "platform": p.get("platform", "BOTH"),
                }
                for p in posts[:5]
            ]
    except Exception as e:
        logger.warning(f"Starter creative generation failed: {e}")

    # Fallback creatives
    return [
        {
            "caption": f"🚀 Exciting things are happening at {biz_name}! We're here to help you grow. Stay tuned for more updates. #growth #business #launch",
            "topic": "Launch",
            "platform": "BOTH",
        },
        {
            "caption": f"💡 Did you know? {desc[:100]}. Follow us for tips, insights, and more! #tips #knowledge #value",
            "topic": "Education",
            "platform": "BOTH",
        },
        {
            "caption": f"🌟 At {biz_name}, we believe in delivering real value. Here's what sets us apart. Stay connected! #brand #quality #trust",
            "topic": "Brand Story",
            "platform": "BOTH",
        },
    ]


def get_pollinations_image_url(prompt: str, width: int = 1024, height: int = 1024) -> str:
    """
    Generate a Pollinations.ai image URL (free, no API key required).
    The image is generated server-side when the URL is fetched.
    """
    encoded_prompt = urllib.parse.quote(prompt)
    return f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&nologo=true"


async def _upload_image_to_cloudinary(
    image_url: str,
    workspace_id: str,
    topic: str,
    media_id: str,
) -> str:
    """
    Upload an AI-generated image to Cloudinary and return the secure URL.
    Falls back to the original URL if Cloudinary is not configured.
    """
    try:
        from services.storage_service import upload_image_from_url
        result = await upload_image_from_url(
            workspace_id=workspace_id,
            media_id=media_id,
            image_url=image_url,
            filename=f"AI_{topic.replace(' ', '_')}_{media_id[:8]}",
            tags=[topic, "ai-generated"],
        )
        if result and result.get("secure_url"):
            logger.info(f"✓ Uploaded to Cloudinary: {result['secure_url']}")
            return result["secure_url"]
    except Exception as e:
        logger.warning(f"Cloudinary upload failed, using direct URL: {e}")

    return image_url


async def auto_populate_workspace(user_id: str, workspace_id: str) -> Dict[str, Any]:
    """
    Full onboarding pipeline: analyze brand → generate creatives → upload to
    Cloudinary → populate media & campaigns.
    Called as a background task after business profile creation.
    """
    result = {
        "brand_analysis": False,
        "creatives_generated": 0,
        "campaigns_created": 0,
    }

    try:
        async with AsyncSessionLocal() as session:
            profile = await session.get(BusinessProfile, workspace_id)
            if not profile:
                logger.error(f"Workspace {workspace_id} not found for auto-populate")
                return result

            # Step 1: Generate brand context via LLM
            logger.info(f"[CREATIVE] Generating brand context for workspace {workspace_id}")
            brand_ctx = await generate_brand_context(profile)

            profile.industry = brand_ctx["industry"]
            profile.targetAudience = brand_ctx["targetAudience"]
            profile.toneOfVoice = brand_ctx["toneOfVoice"]
            profile.contentPillars = brand_ctx["contentPillars"]
            profile.suggestedHashtags = brand_ctx["suggestedHashtags"]
            profile.brandColors = brand_ctx["brandColors"]
            profile.brandAnalysisComplete = True
            await session.commit()
            await session.refresh(profile)
            result["brand_analysis"] = True

            # Step 2: Generate starter creatives via LLM
            logger.info(f"[CREATIVE] Generating starter creatives for workspace {workspace_id}")
            creatives = await generate_starter_creatives(profile)
            result["creatives_generated"] = len(creatives)

            # Step 3: For each creative — generate AI image → upload to Cloudinary → create campaign
            for creative in creatives:
                media_id = str(uuid.uuid4())

                # Generate AI image prompt
                img_prompt = (
                    f"Modern professional social media graphic for {profile.name}, "
                    f"{profile.businessModel or 'business'}, "
                    f"topic: {creative['topic']}, clean design, minimal text, "
                    f"brand colors {', '.join(profile.brandColors or ['#8B5CF6'])}"
                )
                pollinations_url = get_pollinations_image_url(img_prompt, 1080, 1080)

                # Upload to Cloudinary (returns secure URL, falls back to direct URL)
                final_media_url = await _upload_image_to_cloudinary(
                    image_url=pollinations_url,
                    workspace_id=workspace_id,
                    topic=creative["topic"],
                    media_id=media_id,
                )

                # Determine mime type based on URL
                mime_type = "image/png"

                # Register in Media catalog
                media = Media(
                    id=media_id,
                    userId=user_id,
                    businessProfileId=workspace_id,
                    filename=f"AI_{creative['topic'].replace(' ', '_')}_{media_id[:8]}.png",
                    mimeType=mime_type,
                    url=final_media_url,
                    tags=[creative["topic"], "ai-generated", "starter"],
                    aiGenerated=True,
                )
                session.add(media)

                # Create campaign
                campaign = SocialCampaign(
                    userId=user_id,
                    businessProfileId=workspace_id,
                    baseCaption=creative["caption"],
                    mediaUrl=final_media_url,
                    mediaType="image",
                    isActive=True,
                )
                session.add(campaign)
                result["campaigns_created"] += 1

            # Step 4: Ensure MarketingState exists with auto-approve
            from sqlalchemy import select
            ms_stmt = select(MarketingState).where(MarketingState.businessProfileId == workspace_id)
            ms = (await session.execute(ms_stmt)).scalars().first()
            if not ms:
                ms = MarketingState(
                    userId=user_id,
                    businessProfileId=workspace_id,
                    autoApprove=True,
                    postIntervalHours=2,
                )
                session.add(ms)

            await session.commit()
            logger.info(f"[CREATIVE] ✓ Auto-populate complete for workspace {workspace_id}: {result}")

    except Exception as e:
        logger.error(f"[CREATIVE] Auto-populate failed for workspace {workspace_id}: {e}")

    return result


async def auto_generate_creative_batch(workspace_id: str, count: int = 3) -> Dict[str, Any]:
    """
    Generate a new batch of AI creatives for a given workspace and deposit them
    directly into the Media catalog and SocialCampaign queue.
    Uploads all images to Cloudinary.
    """
    created_items = []
    try:
        async with AsyncSessionLocal() as session:
            profile = await session.get(BusinessProfile, workspace_id)
            if not profile:
                logger.error(f"Workspace {workspace_id} not found for creative batch generation")
                return {"success": False, "count": 0, "message": "Workspace not found"}

            user_id = profile.userId

            # Ensure brand context is populated
            if not profile.brandAnalysisComplete:
                brand_ctx = await generate_brand_context(profile)
                profile.industry = brand_ctx["industry"]
                profile.targetAudience = brand_ctx["targetAudience"]
                profile.toneOfVoice = brand_ctx["toneOfVoice"]
                profile.contentPillars = brand_ctx["contentPillars"]
                profile.suggestedHashtags = brand_ctx["suggestedHashtags"]
                profile.brandColors = brand_ctx["brandColors"]
                profile.brandAnalysisComplete = True
                await session.commit()
                await session.refresh(profile)

            creatives = await generate_starter_creatives(profile)

            for creative in creatives[:count]:
                media_id = str(uuid.uuid4())
                topic = creative.get("topic", "Brand Highlight")

                img_prompt = (
                    f"Modern social media graphic for {profile.name}, "
                    f"{profile.businessModel or 'Business'}, "
                    f"niche {profile.industry or 'Tech'}, "
                    f"topic: {topic}, professional design, 8k quality"
                )
                pollinations_url = get_pollinations_image_url(img_prompt, 1080, 1080)

                # Upload to Cloudinary
                final_media_url = await _upload_image_to_cloudinary(
                    image_url=pollinations_url,
                    workspace_id=workspace_id,
                    topic=topic,
                    media_id=media_id,
                )

                media = Media(
                    id=media_id,
                    userId=user_id,
                    businessProfileId=workspace_id,
                    filename=f"AI_{topic.replace(' ', '_')}_{media_id[:8]}.png",
                    mimeType="image/png",
                    url=final_media_url,
                    tags=[topic, "ai-generated", "automated-schedule"],
                    aiGenerated=True,
                )
                session.add(media)

                campaign = SocialCampaign(
                    userId=user_id,
                    businessProfileId=workspace_id,
                    baseCaption=creative["caption"],
                    mediaUrl=final_media_url,
                    mediaType="image",
                    isActive=True,
                )
                session.add(campaign)
                await session.flush()

                created_items.append({
                    "id": campaign.id,
                    "caption": creative["caption"],
                    "topic": topic,
                    "mediaUrl": final_media_url,
                    "mediaId": media_id,
                })

            await session.commit()
            logger.info(f"[CREATIVE BATCH] ✓ Generated {len(created_items)} creatives for workspace {workspace_id}")
            return {"success": True, "count": len(created_items), "items": created_items}

    except Exception as e:
        logger.error(f"[CREATIVE BATCH] Generation failed for workspace {workspace_id}: {e}")
        return {"success": False, "count": 0, "error": str(e)}

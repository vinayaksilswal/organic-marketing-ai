"""
=============================================================================
Organic Marketing AI — AI Creative Service
=============================================================================
Handles automated brand analysis and creative generation during business
onboarding. Generates brand context, starter content, and AI images using
Pollinations.ai (free, no API key required).
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
    prompt = f"""You are a marketing strategist. Analyze this business and generate a structured brand context.

Business Name: {profile.name}
Website: {profile.websiteUrl or 'Not provided'}
Description: {profile.description or 'Not provided'}
Business Model: {profile.businessModel or 'General'}

Return a JSON object with exactly these fields (nothing else, no markdown):
{{
    "industry": "the primary industry this business operates in",
    "targetAudience": "detailed description of ideal customer persona (2-3 sentences)",
    "toneOfVoice": "one of: Professional, Casual, Bold, Playful, Authoritative, Friendly",
    "contentPillars": ["pillar1", "pillar2", "pillar3", "pillar4"],
    "suggestedHashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5"],
    "brandColors": ["#8B5CF6", "#3B82F6"]
}}

Ensure contentPillars are 4 specific content themes for social media.
Ensure suggestedHashtags are 5 relevant hashtags WITH the # prefix."""

    try:
        result = await _call_llm(prompt)
        # Try to extract JSON from the response
        # Handle case where LLM wraps in markdown code block
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

    prompt = f"""You are a social media copywriter. Generate exactly 3 social media posts for this brand.

Brand: {biz_name}
Description: {desc}
Tone: {tone}
Content Pillars: {', '.join(pillars[:4])}
Hashtags to include: {', '.join((profile.suggestedHashtags or ['#business', '#growth'])[:3])}

Return a JSON array with exactly 3 objects, each with these fields (nothing else, no markdown):
[
    {{"caption": "Full post text with emojis and hashtags (2-4 sentences)", "topic": "Content pillar name", "platform": "BOTH"}},
    {{"caption": "...", "topic": "...", "platform": "BOTH"}},
    {{"caption": "...", "topic": "...", "platform": "BOTH"}}
]

Make each post engaging, authentic, and ready to publish. Include relevant emojis and 3-5 hashtags."""

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


async def auto_populate_workspace(user_id: str, workspace_id: str) -> Dict[str, Any]:
    """
    Full onboarding pipeline: analyze brand → generate creatives → populate media & campaigns.
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

            # Step 1: Generate brand context
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

            # Step 2: Generate starter creatives
            logger.info(f"[CREATIVE] Generating starter creatives for workspace {workspace_id}")
            creatives = await generate_starter_creatives(profile)
            result["creatives_generated"] = len(creatives)

            # Step 3: Create campaigns from creatives
            for creative in creatives:
                # Generate an AI image for this post
                img_prompt = f"Modern professional social media graphic for {profile.name}, {profile.businessModel} business, topic: {creative['topic']}, clean design, minimal text"
                img_url = get_pollinations_image_url(img_prompt, 1080, 1080)

                # Register image in Media catalog
                media_id = str(uuid.uuid4())
                media = Media(
                    id=media_id,
                    userId=user_id,
                    businessProfileId=workspace_id,
                    filename=f"AI_Render_{creative['topic'].replace(' ', '_')}_{media_id[:8]}.png",
                    mimeType="image/png",
                    url=img_url,
                    tags=[creative["topic"], "ai-generated", "starter"],
                    aiGenerated=True,
                )
                session.add(media)

                # Create campaign
                campaign = SocialCampaign(
                    userId=user_id,
                    businessProfileId=workspace_id,
                    baseCaption=creative["caption"],
                    mediaUrl=img_url,
                    mediaType="image",
                    isActive=True,
                )
                session.add(campaign)
                result["campaigns_created"] += 1

            # Step 4: Ensure MarketingState exists with 2hr default
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
            logger.info(f"[CREATIVE] Auto-populate complete for workspace {workspace_id}: {result}")

    except Exception as e:
        logger.error(f"[CREATIVE] Auto-populate failed for workspace {workspace_id}: {e}")

    return result

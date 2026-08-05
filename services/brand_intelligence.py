"""Understand the business once, then write from that understanding.

marketing_intelligence_synthesis already produced a good profile — pain point,
transformation, objection, decision driver, competitor visual world. But it ran
inside execute_video_pipeline, so every prompt paid for a website scrape, a
vision call and an LLM call, and then discarded the answer.

Two consequences, and the second is the one that mattered:

  Cost      three network round trips per prompt, on the generation path.
  Drift     nothing anchored the answer, so two runs an hour apart could
            decide the same business sold different things. A brand cannot
            have a consistent voice if the system re-decides what the brand
            IS before every sentence it writes.

So it is built once, stored on the profile, and reused. Rebuilt only when it
goes stale, when the brand's own fields change materially, or when the user
asks.

The profile is also the substantiation source for check_rendered_claims — a
figure may only appear in an ad if it appears here — which is another reason it
has to be a stable stored artefact rather than a fresh guess each time.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from loguru import logger

# Long enough that routine posting never triggers a rebuild, short enough that
# a repositioned business is picked up within a sales quarter.
STALE_AFTER = timedelta(days=90)

# Fields that change what the business IS. A new logo or a changed posting
# interval does not invalidate the understanding; a rewritten description does.
_MATERIAL_FIELDS = (
    "name",
    "description",
    "websiteUrl",
    "industry",
    "niche",
    "targetAudience",
    "primaryOffer",
    "businessModel",
)


def _fingerprint(profile: Any) -> str:
    """Hash of the inputs the understanding was derived from."""
    payload = "|".join(
        str(getattr(profile, f, "") or "").strip().lower() for f in _MATERIAL_FIELDS
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def is_stale(profile: Any) -> Tuple[bool, str]:
    """Whether the stored understanding still describes this business."""
    stored = getattr(profile, "brandIntelligence", None)
    if not stored or not isinstance(stored, dict):
        return True, "never built"

    if stored.get("_fingerprint") != _fingerprint(profile):
        return True, "brand details changed since it was built"

    built_at = getattr(profile, "brandIntelligenceAt", None)
    if not built_at:
        return True, "no build timestamp"
    if built_at.tzinfo is None:
        built_at = built_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - built_at > STALE_AFTER:
        return True, f"older than {STALE_AFTER.days} days"

    return False, "current"


async def build(profile: Any, image_url: str = "") -> Optional[Dict[str, Any]]:
    """Run the full synthesis for this business. Returns None on failure."""
    from services.video_pipeline_service import (
        image_vision_analysis,
        marketing_intelligence_synthesis,
        scrape_product_url,
    )

    website = (getattr(profile, "websiteUrl", None) or "").strip()
    scraped = ""
    if website:
        try:
            raw = await scrape_product_url(website)
            # Whoever controls that page controls these bytes, and the model
            # reading them cannot tell an instruction from a description.
            # Fenced with a per-call nonce so an imperative inside it reads as
            # content rather than as a turn in the conversation.
            if raw:
                from services.untrusted_text import guarded_block

                scraped = guarded_block(
                    raw, label="website_content", source=website
                )
        except Exception as e:
            # Thin or missing website content is expected and handled by the
            # synthesis prompt's Tier 3 rules, so this is not fatal.
            logger.warning(f"Brand intelligence: scrape of {website} failed: {e}")

    vision = ""
    logo = image_url or (getattr(profile, "logoUrl", None) or "")
    if logo:
        try:
            vision = await image_vision_analysis(logo)
        except Exception as e:
            logger.warning(f"Brand intelligence: vision analysis failed: {e}")

    try:
        intel = await marketing_intelligence_synthesis(
            product_name=getattr(profile, "name", "") or "this business",
            scrape_content=scraped,
            vision_yaml=vision,
            profile=profile,
        )
    except Exception as e:
        logger.error(f"Brand intelligence synthesis failed: {e}")
        return None

    if not isinstance(intel, dict) or intel.get("error"):
        logger.error(f"Brand intelligence synthesis returned no usable profile: {intel}")
        return None

    intel["_fingerprint"] = _fingerprint(profile)
    intel["_sources"] = {
        "website": bool(scraped),
        "logo_vision": bool(vision),
        "profile_fields": True,
    }
    return intel


async def get_or_build(
    session: Any,
    profile: Any,
    *,
    force: bool = False,
    image_url: str = "",
) -> Tuple[Optional[Dict[str, Any]], bool]:
    """The understanding for this business. Returns (intelligence, was_built).

    Falls back to the stored copy if a rebuild fails, so a provider outage
    degrades to slightly stale understanding rather than to no understanding
    at all — which would drop generation back to the generic template.
    """
    stale, reason = is_stale(profile)
    if not (force or stale):
        return profile.brandIntelligence, False

    logger.info(
        f"Building brand intelligence for {getattr(profile, 'name', '?')} ({reason})"
    )
    intel = await build(profile, image_url=image_url)
    if not intel:
        stored = getattr(profile, "brandIntelligence", None)
        if stored:
            logger.warning("Rebuild failed; keeping the stored understanding")
            return stored, False
        return None, False

    profile.brandIntelligence = intel
    profile.brandIntelligenceAt = datetime.now(timezone.utc)
    session.add(profile)
    await session.commit()
    return intel, True


def _first(*values) -> str:
    for v in values:
        if v and str(v).strip():
            return str(v).strip()
    return ""


def to_scene_context(intel: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """Flatten the profile into what the scene writer actually consumes.

    The writer takes a handful of plain strings, not a nested schema. Passing
    the whole document would bury the three fields that change the output —
    what it does, what the viewer cares about, and how it should look — under
    twenty that do not.
    """
    if not isinstance(intel, dict):
        return {}

    product = intel.get("product_intelligence", {}) or {}
    audience = intel.get("audience_intelligence", {}) or {}
    visual = intel.get("visual_identity", {}) or {}
    strategy = intel.get("creative_strategy", {}) or {}
    industry = intel.get("industry_visual_language", {}) or {}

    what_it_does = _first(
        product.get("value_proposition"),
        product.get("product_subcategory"),
        product.get("product_category"),
    )
    features = product.get("key_features") or []
    if isinstance(features, list) and features:
        what_it_does = (what_it_does + " Specifically: " +
                        ", ".join(str(f) for f in features[:3])).strip()

    # The motivator, not the demographic. Meta's own guidance, and the reason
    # the old prompts leaked labels like "perfect for entrepreneur parents":
    # naming the segment makes the model write to the label instead of the
    # person's actual barrier.
    motivator = _first(
        audience.get("objection_to_overcome"),
        product.get("primary_pain_point_solved"),
        strategy.get("hero_marketing_hook"),
    )

    aesthetic = _first(
        industry.get("lighting_signature"),
        visual.get("visual_tone"),
        audience.get("aesthetic_preference"),
    )

    return {
        "what_it_does": what_it_does,
        "audience_motivator": motivator,
        "brand_aesthetic": aesthetic,
        "transformation": _first(product.get("transformation_statement")),
        "avoid_visual_world": _first(
            visual.get("competitor_visual_world"),
            intel.get("competitive_differentiation", {}).get("category_codes_to_break"),
        ),
        "product_type": _first(product.get("product_type")),
        "vertical": _first(industry.get("vertical")),
        "data_confidence": _first(product.get("data_confidence")) or "unknown",
    }


def substantiation_source(intel: Optional[Dict[str, Any]], profile: Any = None) -> str:
    """Text a rendered figure must appear in to be allowed on screen.

    check_rendered_claims blocks any number in an on-screen string that is not
    present here, which is what stopped live output reading "47 Vulnerable Keys
    Found" about a customer whose key count nobody knows.
    """
    parts = []
    if profile is not None:
        parts += [
            str(getattr(profile, f, "") or "")
            for f in ("name", "description", "primaryOffer", "toneOfVoice")
        ]
    if isinstance(intel, dict):
        # Everything the synthesis derived from real sources, flattened. A
        # figure genuinely on the website survives the scrape into here.
        parts.append(json.dumps(intel, default=str))
    return " ".join(p for p in parts if p)

"""LLM-powered caption generation with motivator-based prompting.

Generates direct-response social captions using the AI service (OpenRouter LLM)
with the research-specified motivator-based system prompt, negative exemplars,
and forced specificity slots. Implements a retry-with-validation loop and falls
back to deterministic templates when LLM is unavailable.

Research Reference: Section B — Captions for Instagram and Facebook
"""

from __future__ import annotations

from typing import List, Optional

from loguru import logger

from prompt_engine.compilers import build_caption_system_prompt
from prompt_engine.validator import validate_caption
from prompt_engine.models import PromptValidationResult
from database import BusinessProfile


MAX_LLM_RETRIES = 3


async def _call_llm(prompt: str) -> str:
    """Thin wrapper around the AI service for mockability in tests."""
    from services.ai_service import generate_campaign_variation
    return await generate_campaign_variation(prompt)


def _build_template_caption(
    brand_name: str,
    product_feature: str,
    brand_language_anchor: str,
    website_url: Optional[str] = None,
) -> str:
    """Deterministic template fallback when LLM is unavailable.

    Produces a minimal but valid 3-line caption that passes all validation
    gates. Used as a degraded-mode response — functional but not optimised.
    """
    sentence1 = (
        f"If you require verified proof before adopting {product_feature}, "
        f"consider how {brand_language_anchor} solves this directly."
    )
    sentence2 = (
        f"Built with zero fluff, {brand_language_anchor} delivers "
        f"verifiable results without unnecessary complexity."
    )
    sentence3 = f"Get started today at {website_url or 'our store'}."

    return f"{sentence1}\n\n{sentence2}\n\n{sentence3}"


def _clean_llm_output(raw: str) -> str:
    """Strip common LLM artifacts from the output.

    Removes markdown fences, labels like 'Caption:', and leading/trailing
    whitespace that LLMs sometimes prepend despite instructions.
    """
    text = raw.strip()

    # Remove markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    # Remove common prefixes LLMs add despite instructions
    prefixes_to_strip = [
        "Caption:", "caption:", "CAPTION:",
        "Here's the caption:", "Here is the caption:",
        "Output:", "Result:",
    ]
    for prefix in prefixes_to_strip:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()

    # Remove surrounding quotes
    if (text.startswith('"') and text.endswith('"')) or \
       (text.startswith("'") and text.endswith("'")):
        text = text[1:-1].strip()

    return text


async def generate_caption_via_llm(
    business_profile: BusinessProfile,
    product_feature: str,
    customer_motivator: str,
    brand_language_anchor: str,
    website_rag_context: Optional[List[str]] = None,
    past_captions: Optional[List[str]] = None,
    llm_enabled: bool = True,
) -> tuple[str, PromptValidationResult, str]:
    """Generate a caption via LLM with retry-on-validation-failure loop.

    Returns:
        Tuple of (caption_text, validation_result, generation_method).
        generation_method is "llm" or "template".
    """
    brand_name = business_profile.name or "the brand"
    website_url = business_profile.websiteUrl

    # If LLM is disabled, go straight to template
    if not llm_enabled:
        caption = _build_template_caption(
            brand_name, product_feature, brand_language_anchor, website_url
        )
        validation = validate_caption(
            business_profile=business_profile,
            caption=caption,
            customer_motivator=customer_motivator,
            website_rag_context=website_rag_context or [brand_language_anchor, business_profile.primaryOffer or ""],
            past_captions=past_captions,
        )
        return caption, validation, "template"

    # Build the system prompt per the research specification
    system_prompt = build_caption_system_prompt(
        brand_name=brand_name,
        customer_motivator=customer_motivator,
        brand_language_anchor=brand_language_anchor,
        product_feature=product_feature,
    )

    # Retry loop: generate and validate, re-attempt if gates fail
    last_caption = ""
    last_validation = None

    for attempt in range(MAX_LLM_RETRIES):
        try:
            # Call the AI service
            raw_output = await _call_llm(system_prompt)

            if not raw_output or not raw_output.strip():
                logger.warning(f"LLM returned empty caption on attempt {attempt + 1}")
                continue

            caption = _clean_llm_output(raw_output)
            last_caption = caption

            # Validate against all gates
            validation = validate_caption(
                business_profile=business_profile,
                caption=caption,
                customer_motivator=customer_motivator,
                website_rag_context=website_rag_context or [brand_language_anchor, business_profile.primaryOffer or ""],
                past_captions=past_captions,
            )
            last_validation = validation

            if validation.is_valid:
                logger.info(f"LLM caption passed all gates on attempt {attempt + 1}")
                return caption, validation, "llm"
            else:
                logger.warning(
                    f"LLM caption failed validation on attempt {attempt + 1}: "
                    f"{validation.errors}"
                )

        except Exception as e:
            logger.error(f"LLM caption generation failed on attempt {attempt + 1}: {e}")

    # If LLM failed all retries, return the last attempt (if any) or fall back to template
    if last_caption and last_validation:
        logger.warning("All LLM retry attempts failed validation, returning last attempt with errors")
        return last_caption, last_validation, "llm"

    # Full fallback to template
    logger.warning("LLM unavailable after all retries, falling back to template caption")
    caption = _build_template_caption(
        brand_name, product_feature, brand_language_anchor, website_url
    )
    validation = validate_caption(
        business_profile=business_profile,
        caption=caption,
        customer_motivator=customer_motivator,
        website_rag_context=website_rag_context or [brand_language_anchor, business_profile.primaryOffer or ""],
        past_captions=past_captions,
    )
    return caption, validation, "template"

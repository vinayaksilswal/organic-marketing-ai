"""
=============================================================================
Organic Marketing AI — OpenRouter LLM Client (AI Copy & Marketing Asset Generation)
=============================================================================
Integrates with OpenRouter's API at https://openrouter.ai/api/v1/chat/completions
using the tencent/hy3:free model for marketing copy generation.

Key Functions:
  - generate_campaign_variation(): Unique variations for social media
  - generate_campaign_email(): Full email content (subject, text, HTML)

All HTTP calls are fully async via httpx with tenacity exponential backoff.
=============================================================================
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape

import httpx
from loguru import logger
from pydantic import BaseModel, Field, ValidationError
from tenacity import (
    retry,
    retry_if_exception,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import settings

# =============================================================================
# Constants
# =============================================================================
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# google/gemma-2-9b-it:free — Used for marketing copy generation (free tier)
# google/gemma-2-9b-it:free was retired by OpenRouter and returned 404 on every
# call, so the default model for all marketing copy was silently dead.
MARKETING_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"

# Shared timeout for LLM API calls (LLMs can be slow)
LLM_TIMEOUT = httpx.Timeout(60.0, connect=15.0)


# =============================================================================
# Core LLM Call — Async with Retry
# =============================================================================
def _is_worth_retrying(exc: BaseException) -> bool:
    """Retry only faults that a second attempt on the SAME model might fix.

    A 429 means this model is out of capacity — retrying it wastes time we
    should spend on the next model in the chain. Retrying every status here
    turned one busy model into 3 backed-off attempts, and with 4 models in the
    chain that became up to 12 slow calls and a request that timed out rather
    than degrading. 4xx are caller faults and never retryable.
    """
    if isinstance(exc, httpx.RequestError):
        return True  # connection reset, DNS blip, timeout
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500  # provider-side, may recover
    return False


@retry(
    wait=wait_exponential(multiplier=1, min=1, max=6),
    stop=stop_after_attempt(2),
    retry=retry_if_exception(_is_worth_retrying),
    reraise=True,
    before_sleep=lambda retry_state: logger.warning(
        f"LLM transient error, retry {retry_state.attempt_number}"
    ),
)
async def _call_openrouter_once(
    prompt: str,
    *,
    model: str = MARKETING_MODEL,
    json_response: bool = False,
    system_prompt: str | None = None,
) -> str:
    """
    Core async function to call OpenRouter's chat completions API.

    Args:
        prompt: The user message/prompt to send
        model: Which model to use (defaults to marketing model)
        json_response: If True, requests JSON output format
        system_prompt: Optional system message to prepend

    Returns:
        The assistant's response content as a string, or empty string on failure
    """
    if not settings.openrouter_api_key:
        logger.warning("OPENROUTER_API_KEY not configured — LLM calls disabled")
        return ""

    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://organicmarketing.ai",
        "X-Title": "Organic Marketing AI",
    }

    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
    }

    if json_response:
        payload["response_format"] = {"type": "json_object"}

    async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
        response = await client.post(OPENROUTER_URL, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()

        # OpenRouter answers 200 with an {"error": {...}} body when a model
        # rejects the request — an unsupported response_format, a moderation
        # block, an upstream provider being down. Indexing straight into
        # ["choices"] turned all of those into a bare KeyError, so the log said
        # only "unavailable (KeyError)" and the actual reason was lost. The
        # 550B model at the head of the chain failed this way on every call and
        # nobody could see why.
        if "choices" not in result:
            err = result.get("error")
            if isinstance(err, dict):
                detail = err.get("message") or str(err)
                code = err.get("code")
                raise RuntimeError(
                    f"{model} rejected the request"
                    + (f" [{code}]" if code else "")
                    + f": {str(detail)[:300]}"
                )
            raise RuntimeError(
                f"{model} returned no choices: {str(result)[:300]}"
            )

        choices = result["choices"]
        if not choices:
            raise RuntimeError(f"{model} returned an empty choices list")

        message = choices[0].get("message") or {}
        content = (message.get("content") or "").strip()
        if not content:
            # Some models put the text under a reasoning field, or return an
            # empty assistant turn when they refuse.
            finish = choices[0].get("finish_reason")
            raise RuntimeError(
                f"{model} returned empty content"
                + (f" (finish_reason={finish})" if finish else "")
            )
        return content


# =============================================================================
# Provider fallback chain
# =============================================================================
# OpenRouter's free tier rate-limits hard (429). A single model being busy must
# not fail the whole request, so we try several free models, then fall back to
# calling Gemini directly if a key is available.
# Verified against OpenRouter's live catalogue. Hardcoding slugs is fragile —
# an earlier chain listed four models that had all been retired, so every
# fallback returned 404 and only the rate-limited primary was ever tried. These
# are the seed values; _free_models() refreshes them from the API at runtime.
FREE_MODEL_CHAIN = [
    # Ordered by capability for marketing copy, strongest first. The chain
    # falls through on rate limits, so leading with the best model costs
    # nothing when it is busy but noticeably improves caption quality when it
    # is not.
    "nvidia/nemotron-3-ultra-550b-a55b:free",      # 550B MoE, 1M ctx
    "nvidia/nemotron-3-super-120b-a12b:free",      # 120B MoE
    "inclusionai/ling-3.0-flash:free",             # 124B MoE
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "openai/gpt-oss-20b:free",
    "nvidia/nemotron-3-nano-30b-a3b:free",
]

# Models unsuited to marketing copy: safety classifiers, code-only, vision-only.
_MODEL_EXCLUDE = ("content-safety", "-code", "-vl", "guard")

_model_cache: dict[str, Any] = {"models": None, "fetched_at": 0.0}
_MODEL_CACHE_TTL = 3600  # seconds


async def _free_models() -> list[str]:
    """The free models OpenRouter currently offers, cached for an hour.

    Discovering these rather than hardcoding them means a retired model can no
    longer silently break the fallback chain. Falls back to FREE_MODEL_CHAIN if
    the catalogue cannot be reached.
    """
    now = time.time()
    if _model_cache["models"] and now - _model_cache["fetched_at"] < _MODEL_CACHE_TTL:
        return _model_cache["models"]

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            resp = await client.get("https://openrouter.ai/api/v1/models")
            resp.raise_for_status()
            ids = [
                m["id"] for m in resp.json().get("data", [])
                if m.get("id", "").endswith(":free")
                and not any(x in m["id"] for x in _MODEL_EXCLUDE)
            ]
        if ids:
            # Keep our preferred models first, then everything else discovered.
            ordered = [m for m in FREE_MODEL_CHAIN if m in ids]
            ordered += [m for m in ids if m not in ordered]
            _model_cache.update({"models": ordered, "fetched_at": now})
            logger.info(f"Refreshed OpenRouter free model list: {len(ordered)} available")
            return ordered
    except Exception as e:
        logger.warning(f"Could not refresh OpenRouter model list, using defaults: {e}")

    return FREE_MODEL_CHAIN

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_MODEL = "gemini-2.0-flash"


async def _call_gemini(
    prompt: str,
    *,
    json_response: bool = False,
    system_prompt: str | None = None,
) -> str:
    """Direct Gemini call, used when OpenRouter is exhausted."""
    key = getattr(settings, "gemini_api_key", None)
    if not key:
        return ""

    text = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
    body: dict[str, Any] = {"contents": [{"parts": [{"text": text}]}]}
    if json_response:
        body["generationConfig"] = {"response_mime_type": "application/json"}

    async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
        resp = await client.post(
            GEMINI_URL.format(model=GEMINI_MODEL),
            headers={"Content-Type": "application/json", "x-goog-api-key": key},
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()


async def _call_openrouter(
    prompt: str,
    *,
    model: str = MARKETING_MODEL,
    json_response: bool = False,
    system_prompt: str | None = None,
) -> str:
    """Call an LLM, degrading through providers rather than failing outright.

    Order: the requested model, then the other free models, then Gemini direct.
    Only raises if every option is exhausted, so a single 429 no longer takes
    down creative generation.
    """
    tried: list[str] = []
    available = await _free_models()
    chain = [model] + [m for m in available if m != model]

    for candidate in chain:
        try:
            result = await _call_openrouter_once(
                prompt,
                model=candidate,
                json_response=json_response,
                system_prompt=system_prompt,
            )
            if result:
                if tried:
                    logger.info(f"LLM succeeded on fallback model {candidate} after {tried} failed")
                return result
        except Exception as e:
            # Not every free model supports response_format. Skipping the model
            # outright costs us the strongest option in the chain for every
            # JSON call, so retry it once in plain text — the callers already
            # tolerate a bare JSON object without the response_format hint.
            if json_response and "response_format" in str(e).lower():
                try:
                    result = await _call_openrouter_once(
                        prompt,
                        model=candidate,
                        json_response=False,
                        system_prompt=system_prompt,
                    )
                    if result:
                        logger.info(
                            f"LLM model {candidate} does not support response_format; "
                            "succeeded without it"
                        )
                        return result
                except Exception as retry_exc:
                    e = retry_exc

            tried.append(candidate)
            status = getattr(getattr(e, "response", None), "status_code", None)
            # 429/5xx are capacity problems worth retrying elsewhere; a 401 or
            # 400 will fail identically on every model, so stop early.
            if status in (400, 401, 403):
                logger.error(f"LLM request rejected ({status}) — not retrying other models")
                break
            # Log the reason, not just the exception class. "unavailable
            # (KeyError)" told us nothing across dozens of production calls.
            logger.warning(
                f"LLM model {candidate} unavailable "
                f"({status or type(e).__name__}): {str(e)[:250]}; trying next"
            )

    try:
        gemini = await _call_gemini(prompt, json_response=json_response, system_prompt=system_prompt)
        if gemini:
            logger.info("LLM served by Gemini fallback after OpenRouter was exhausted")
            return gemini
    except Exception as e:
        logger.warning(f"Gemini fallback also failed: {e}")

    logger.error(f"All LLM providers failed. Tried: {tried}")
    raise RuntimeError("Every configured AI provider is unavailable or rate-limited.")


def _parse_json_response(text: str) -> dict | None:
    """
    Helper to parse JSON from LLM responses, handling common markdown wrapping.
    LLMs often wrap JSON in ```json ... ``` code blocks despite instructions.
    """
    if not text:
        return None

    cleaned = text.strip()

    # Strip markdown code fences if present
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]

    try:
        return json.loads(cleaned.strip())
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse LLM JSON response: {e}")
        logger.debug(f"Raw LLM output: {text[:500]}")
        return None


# =============================================================================
# Schema Validation & Guardrails
# =============================================================================
class OmnichannelContentSchema(BaseModel):
    caption: str = Field(..., max_length=2200, description="Main social media caption (strict <2200 chars for TikTok).")
    hashtags: list[str] = Field(default_factory=list, max_items=15, description="Relevant hashtags.")
    email_subject: str = Field(..., max_length=100, description="Promotional email subject line.")
    email_headline: str = Field(..., max_length=100, description="Email headline (2-5 words).")
    email_subheadline: str = Field(..., max_length=200, description="Email subheadline.")
    email_body_copy: str = Field(..., description="Persuasive body copy for the email.")
    email_cta_text: str = Field(..., max_length=30, description="Call to action button text.")
    video_hook: str = Field(..., max_length=100, description="Short text hook for the video overlay.")

# =============================================================================
# Omnichannel Generation (Enterprise)
# =============================================================================
async def generate_omnichannel_content(business_context: str, campaign_context: str) -> dict:
    """
    Enterprise-grade multimodal generation using strict Pydantic validation.
    """
    system_prompt = (
        "You are an elite enterprise marketing copywriter and brand strategist. "
        "Your goal is to drive high-value organic conversions through psychological hooks, clear ROI, and precise audience targeting. "
        "MANDATORY RULES:\n"
        "1. NO CLICHES: Never use words like 'cutting-edge', 'state of the art', 'dynamic', 'revolutionary', 'unlock', or 'synergy'.\n"
        "2. SPECIFICITY: Speak directly to the pain point. Use concrete outcomes over vague promises.\n"
        "3. HOOK-FIRST: Every caption and email must start with a pattern-interrupting hook.\n"
        "4. NO EMOJI SPAM: Use emojis surgically, maximum 2 per post.\n"
        "Your output MUST be a valid JSON object matching the requested schema exactly. "
        "No markdown fences. Return ONLY the raw JSON."
    )

    prompt = f"""Generate enterprise-grade omnichannel marketing content based on the following context.
    
Business Context:
{business_context}

Campaign Context:
{campaign_context}

FRAMEWORK REQUIREMENT:
Use the PAS (Problem-Agitation-Solution) or AIDA (Attention-Interest-Desire-Action) framework for the social caption and email body. 

Return a JSON object with:
1. "caption": A highly engaging social media caption (under 2200 characters). Must start with a hook.
2. "hashtags": An array of 3-5 hyper-relevant niche hashtags (no generic tags like #business).
3. "email_subject": A high-converting, curiosity-driven email subject line (under 50 chars).
4. "email_headline": A strong 2-5 word email headline focusing on concrete business value.
5. "email_subheadline": A short sentence elaborating on the headline with urgency.
6. "email_body_copy": 2-3 sentences of persuasive body copy selling the service. Focus on the transformation. DO NOT include HTML.
7. "email_cta_text": Action-oriented text for an email button (e.g. "Get Your Audit", not "Click Here").
8. "video_hook": A punchy 3-5 word text overlay for the first 3 seconds of a vertical video."""

    for attempt in range(3):
        try:
            text = await _call_openrouter(prompt, system_prompt=system_prompt, json_response=True)
            parsed = _parse_json_response(text)
            
            if not parsed:
                continue

            # Strict Pydantic Validation
            validated_data = OmnichannelContentSchema(**parsed)
            return validated_data.model_dump()
            
        except ValidationError as e:
            logger.warning(f"LLM output failed Pydantic validation: {e}. Retrying...")
            # We could append the validation error to the prompt for the next attempt
            prompt += f"\n\nERROR in previous attempt: Please fix these validation errors:\n{e}"
        except Exception as e:
            logger.error(f"Error during omnichannel generation: {e}")
            
    # Fallback if all attempts fail
    return {
        "caption": "Check out our latest updates to scale your business! 🚀",
        "hashtags": ["#BusinessGrowth", "#Automation"],
        "email_subject": "Transform your business with Organic Marketing AI",
        "email_headline": "Unlock Enterprise AI",
        "email_subheadline": "Automate your workflows today.",
        "email_body_copy": "Check out our latest automation tools to help you scale.",
        "email_cta_text": "Learn More",
        "video_hook": "Scale Your Business"
    }


# =============================================================================
# generate_campaign_email() — Legacy Fallback
# =============================================================================
async def generate_campaign_email(campaign: Any) -> dict[str, str]:
    """
    Generate a complete promotional email (subject, text body, HTML body)
    for a social campaign.
    """
    system_prompt = (
        "You are a master direct-response copywriter for B2B and B2C enterprise brands. "
        "Your goal is to maximize email open rates and click-through rates. "
        "MANDATORY RULES:\n"
        "1. NO CLICHES: Never use 'cutting-edge', 'revolutionize', 'unlock', 'transform your business', or 'supercharge'.\n"
        "2. CURIOSITY + BENEFIT: The subject line must combine a specific benefit with a curiosity gap.\n"
        "3. CONVERSATIONAL TONE: Write like a human expert talking to a peer, not a corporate robot.\n"
        "Your output MUST be a valid JSON object with EXACTLY 5 keys: "
        "subject, headline, subheadline, body_copy, cta_text. "
        "No markdown fences. Return ONLY the raw JSON."
    )

    prompt = f"""Write a high-converting promotional email based on this campaign context:

Campaign Base Content: {campaign.baseCaption}

COPYWRITING FRAMEWORK:
Use a direct, pain-point-focused approach. Agitate a specific problem they have, then introduce our solution as the inevitable answer.

Return a JSON object with:
1. "subject": A high-converting, curiosity-driven email subject line (e.g., "The real reason your ads are failing (and the fix)")
2. "headline": A strong 2-5 word headline focusing on concrete business value
3. "subheadline": A short sentence elaborating on the headline and adding urgency or proof
4. "body_copy": 2-3 sentences of persuasive body copy. Focus on the 'Before -> After' transformation. DO NOT include HTML.
5. "cta_text": Action-oriented text for a button (e.g., "See how it works", "Get the playbook")"""

    text = await _call_openrouter(
        prompt,
        system_prompt=system_prompt,
    )

    parsed = _parse_json_response(text)
    
    # Defaults in case of failure or missing keys
    content = {
        "subject": "Transform your business with Organic Marketing AI",
        "headline": "Unlock Enterprise AI",
        "subheadline": "Automate your workflows today.",
        "body_copy": "Check out our latest automation tools to help you scale.",
        "cta_text": "Learn More"
    }

    if parsed and isinstance(parsed, dict):
        content.update(parsed)
        
    # Prepare template variables (with UTM tracking)
    campaign_url = f"https://organicmarketing.ai/?utm_source=auto_email&utm_medium=organic&utm_campaign=ai_loop_{campaign.id}"
    
    # Premium Enterprise HTML Layout
    body_html = f"""
    <!DOCTYPE html>
    <html>
    <body style="margin: 0; padding: 0; background-color: #f4f7f6; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;">
        <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #f4f7f6; padding: 40px 0;">
            <tr>
                <td align="center">
                    <table width="600" border="0" cellspacing="0" cellpadding="0" style="background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); overflow: hidden;">
                        <!-- Header -->
                        <tr>
                            <td style="padding: 40px 40px 20px; text-align: center; background-color: #0f172a;">
                                <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 700; letter-spacing: -0.5px;">Organic<span style="color: #6366f1;">Marketing</span></h1>
                            </td>
                        </tr>
                        <!-- Hero Section -->
                        <tr>
                            <td style="padding: 30px 40px; text-align: center;">
                                <h2 style="margin: 0 0 15px 0; color: #1e293b; font-size: 24px; font-weight: 700;">{content['headline']}</h2>
                                <p style="margin: 0; color: #64748b; font-size: 18px; line-height: 1.5;">{content['subheadline']}</p>
                            </td>
                        </tr>
                        <!-- Media -->
                        <tr>
                            <td style="padding: 0 40px;">
                                <img src="{campaign.mediaUrl}" alt="Organic Marketing AI" style="width: 100%; max-width: 520px; height: auto; border-radius: 8px; border: 1px solid #e2e8f0; display: block; margin: 0 auto;" />
                            </td>
                        </tr>
                        <!-- Body Copy -->
                        <tr>
                            <td style="padding: 30px 40px;">
                                <p style="margin: 0; color: #334155; font-size: 16px; line-height: 1.6;">{content['body_copy']}</p>
                            </td>
                        </tr>
                        <!-- CTA Button -->
                        <tr>
                            <td style="padding: 10px 40px 40px; text-align: center;">
                                <a href="{campaign_url}" style="display: inline-block; padding: 16px 36px; background-color: #4f46e5; color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px; transition: background-color 0.2s;">{content['cta_text']}</a>
                            </td>
                        </tr>
                        <!-- Footer -->
                        <tr>
                            <td style="padding: 30px 40px; background-color: #f8fafc; border-top: 1px solid #e2e8f0; text-align: center;">
                                <p style="margin: 0; color: #94a3b8; font-size: 13px;">Enterprise Marketing Automation Infrastructure.</p>
                                <p style="margin: 10px 0 0; color: #94a3b8; font-size: 12px;">You're receiving this because you're part of the Organic Marketing AI community. <a href="https://organicmarketing.ai/unsubscribe" style="color: #64748b; text-decoration: underline;">Unsubscribe</a></p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    return {
        "subject": content["subject"],
        "bodyText": f"{content['headline']}\n\n{content['body_copy']}\n\n{content['cta_text']}: {campaign_url}",
        "bodyHtml": body_html,
    }


# =============================================================================
# generate_campaign_variation() — AI Rewrite for Social Campaigns
# =============================================================================
async def generate_campaign_variation(
    base_caption: str, link: Optional[str] = None
) -> str:
    """Write the caption for a post.

    Two things used to be hardcoded here, and both were wrong the moment this
    platform had a customer other than us.

    It instructed the model to write "for an enterprise B2B audience" on every
    caption for every workspace -- overriding the audience the caller had just
    spent a long prompt describing. A luxury lifestyle page and an AI art page
    both came out sounding like a SaaS landing page.

    Worse, it appended https://organicmarketing.ai to the end of every post.
    That is our marketing link in a paying customer's Instagram caption,
    advertising us on their account instead of their own site. Charging someone
    $17 a month and then using their audience as our billboard is not a feature.

    `link` is now supplied by the caller, which passes the workspace's own
    website or nothing at all. Social pages generally have no website, and a
    caption with no link outperforms one carrying an irrelevant commercial URL.
    """
    link_line = (
        f"End the post with this link on its own line: {link}\n" if link else
        "Do not include any URL or link in the post.\n"
    )
    prompt = f"""Rewrite the following brief into a finished social media caption.
Follow the audience, tone and content pillars given in the brief exactly -- they
describe this specific account and are not interchangeable with any other.
Use modern formatting, relevant hashtags and emojis where they suit the tone.
{link_line}
Brief:
{base_caption}

Return ONLY the caption text. No intro, no commentary, no quotes around it."""

    text = await _call_openrouter(prompt)
    return text if text and len(text) > 10 else base_caption

# =============================================================================
# generate_social_caption()
# =============================================================================
async def generate_social_caption(product: Any) -> str:
    """
    Generate an engaging social media caption for a product.
    """
    prompt = f"""Write an engaging social media caption for this product:
Product Name: {product.productName}
Description: {product.description}
Price: ${product.sellPrice}

Keep it exciting, use emojis, and include relevant hashtags.
Return ONLY the caption text."""
    
    text = await _call_openrouter(prompt)
    return text if text and len(text) > 10 else f"Check out our new {product.productName}! Available now for just ${product.sellPrice}. 🚀 #newarrival #musthave"

# =============================================================================
# generate_promotional_email()
# =============================================================================
async def generate_promotional_email(product: Any) -> dict[str, str]:
    """
    Generate a promotional email for a product.
    """
    system_prompt = (
        "You are a marketing email copywriter. "
        "Your output MUST be a valid JSON object with EXACTLY 5 keys: "
        "subject, headline, subheadline, body_copy, cta_text. "
        "No markdown fences. Return ONLY the JSON."
    )

    prompt = f"""Write a promotional email for this product:
Product Name: {product.productName}
Description: {product.description}
Price: ${product.sellPrice}

Return a JSON object with:
1. "subject": A catchy email subject line
2. "headline": A strong 2-5 word headline
3. "subheadline": A short sentence elaborating on the headline
4. "body_copy": 2-3 sentences of persuasive body copy selling the product. DO NOT include HTML.
5. "cta_text": Short text for a button (e.g. "Buy Now")"""

    text = await _call_openrouter(prompt, system_prompt=system_prompt, json_response=True)
    parsed = _parse_json_response(text)
    
    content = {
        "subject": f"Special Offer: {product.productName}",
        "headline": "New Arrival!",
        "subheadline": f"Get the {product.productName} today.",
        "body_copy": str(product.description)[:100] + "..." if product.description else "Check out our newest addition.",
        "cta_text": "Shop Now"
    }

    if parsed and isinstance(parsed, dict):
        content.update(parsed)

    product_url = "https://organicmarketing.ai/" # default url
    
    img_url = ""
    if hasattr(product, 'productImage') and product.productImage:
        img_url = product.productImage
    elif hasattr(product, 'productImages') and product.productImages and len(product.productImages) > 0:
        img_url = product.productImages[0]

    img_html = f'<div style="text-align: center; margin: 20px 0;"><img src="{img_url}" alt="{product.productName}" style="max-width: 100%; border-radius: 8px;" /></div>' if img_url else ""

    body_html = f"""
    <!DOCTYPE html>
    <html>
    <body style="margin: 0; padding: 0; background-color: #f4f7f6; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;">
        <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #f4f7f6; padding: 40px 0;">
            <tr>
                <td align="center">
                    <table width="600" border="0" cellspacing="0" cellpadding="0" style="background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); overflow: hidden;">
                        <!-- Header -->
                        <tr>
                            <td style="padding: 40px 40px 20px; text-align: center; background-color: #0f172a;">
                                <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 700; letter-spacing: -0.5px;">Quant<span style="color: #6366f1;">CAI</span></h1>
                            </td>
                        </tr>
                        <!-- Hero Section -->
                        <tr>
                            <td style="padding: 30px 40px; text-align: center;">
                                <h2 style="margin: 0 0 15px 0; color: #1e293b; font-size: 24px; font-weight: 700;">{content['headline']}</h2>
                                <p style="margin: 0; color: #64748b; font-size: 18px; line-height: 1.5;">{content['subheadline']}</p>
                            </td>
                        </tr>
                        <!-- Media -->
                        <tr>
                            <td style="padding: 0 40px;">
                                {img_html}
                            </td>
                        </tr>
                        <!-- Body Copy -->
                        <tr>
                            <td style="padding: 30px 40px;">
                                <p style="margin: 0; color: #334155; font-size: 16px; line-height: 1.6;">{content['body_copy']}</p>
                            </td>
                        </tr>
                        <!-- CTA Button -->
                        <tr>
                            <td style="padding: 10px 40px 40px; text-align: center;">
                                <a href="{product_url}" style="display: inline-block; padding: 16px 36px; background-color: #4f46e5; color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px;">{content['cta_text']}</a>
                            </td>
                        </tr>
                        <!-- Footer -->
                        <tr>
                            <td style="padding: 30px 40px; background-color: #f8fafc; border-top: 1px solid #e2e8f0; text-align: center;">
                                <p style="margin: 0; color: #94a3b8; font-size: 13px;">Enterprise Marketing Automation Infrastructure.</p>
                                <p style="margin: 10px 0 0; color: #94a3b8; font-size: 12px;">You're receiving this because you're part of the Organic Marketing AI community. <a href="https://organicmarketing.ai/unsubscribe" style="color: #64748b; text-decoration: underline;">Unsubscribe</a></p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    return {
        "subject": content["subject"],
        "bodyText": f"{content['headline']}\n\n{content['body_copy']}\n\n{content['cta_text']}: {product_url}",
        "bodyHtml": body_html,
    }


# =============================================================================
# arXiv Research → Social Content Generation
# =============================================================================
# These functions transform academic paper abstracts into platform-ready
# social media content for the autonomous arXiv newsroom pipeline.
# =============================================================================

ARXIV_X_SYSTEM_PROMPT = """You are a senior technology advocate writing for X (Twitter).
Your audience is developers, researchers, and technical professionals.

RULES:
- Write exactly 3 posts for an X thread. Each post MUST be under 280 characters.
- Post 1: Hook — summarize what the paper discovered in a punchy, engaging way. Use an emoji opener.
- Post 2: Technical implications — what this means for practitioners. Include relevant context.
- Post 3: Call-to-action — direct readers to learn more. Use the CTA link provided.
- Be technically accurate but accessible. No hype or buzzwords.
- Include 3-5 relevant hashtags separately.

OUTPUT FORMAT (strict JSON, no markdown fences):
{
  "post_1": "...",
  "post_2": "...",
  "post_3": "...",
  "hashtags": ["#Research", "#Tech", ...]
}"""

ARXIV_LINKEDIN_SYSTEM_PROMPT = """You are a technology thought leader writing for LinkedIn.
Your audience is technical leaders, engineering managers, and industry professionals.

RULES:
- Write a professional executive summary (max 3000 characters).
- Frame the research around its practical industry implications.
- Emphasize actionable insights and future impact.
- End with a clear call-to-action using the CTA link provided.
- Include 3-5 professional hashtags separately.
- Do NOT use emojis. Use professional tone throughout.

OUTPUT FORMAT (strict JSON, no markdown fences):
{
  "body": "...",
  "hashtags": ["#Research", "#Technology", ...]
}"""


def _classify_paper_category(title: str, abstract: str) -> str:
    """Classify an arXiv paper into a broad category based on keywords."""
    text = (title + " " + abstract).lower()
    category_keywords = {
        "cybersecurity": ["cryptograph", "vulnerability", "cybersecurity", "encryption", "tls", "certificate", "malware", "intrusion"],
        "ai_ml": ["machine learning", "deep learning", "neural network", "transformer", "llm", "reinforcement learning", "diffusion model"],
        "quantum": ["quantum", "qubit", "entanglement", "superposition"],
    }
    for category, keywords in category_keywords.items():
        for kw in keywords:
            if kw in text:
                return category
    return "general"


def _build_arxiv_cta_link(category: str, arxiv_id: str) -> str:
    """Build a trackable CTA link for the paper."""
    base = "https://organicmarketing.ai"
    utm = f"utm_source=arxiv_newsroom&utm_medium=social&utm_campaign={arxiv_id}"
    return f"{base}/research?{utm}"


async def generate_arxiv_x_thread(
    title: str, abstract: str, arxiv_id: str, cta_link: str
) -> dict:
    """
    Generate a 3-post X thread from an arXiv paper abstract.

    Returns:
        Dict with keys: post_1, post_2, post_3, hashtags
    """
    prompt = f"""Paper Title: {title}
Paper ID: {arxiv_id}
Abstract: {abstract}

CTA Link to include in post 3: {cta_link}"""

    text = await _call_openrouter(
        prompt,
        system_prompt=ARXIV_X_SYSTEM_PROMPT,
    )

    parsed = _parse_json_response(text)
    if parsed and isinstance(parsed, dict):
        return {
            "post_1": str(parsed.get("post_1", ""))[:280],
            "post_2": str(parsed.get("post_2", ""))[:280],
            "post_3": str(parsed.get("post_3", ""))[:280],
            "hashtags": parsed.get("hashtags", ["#Research", "#OrganicAI"]),
        }

    # Fallback if LLM fails
    return {
        "post_1": f"🔬 New research: {title[:200]}",
        "post_2": f"Read the full paper: https://arxiv.org/abs/{arxiv_id}",
        "post_3": f"Explore more → {cta_link}",
        "hashtags": ["#Research", "#Tech", "#OrganicMarketingAI"],
    }


async def generate_arxiv_linkedin_post(
    title: str, abstract: str, arxiv_id: str, cta_link: str
) -> dict:
    """
    Generate a LinkedIn executive summary from an arXiv paper abstract.

    Returns:
        Dict with keys: body, hashtags
    """
    prompt = f"""Paper Title: {title}
Paper ID: {arxiv_id}
Abstract: {abstract}

CTA Link: {cta_link}"""

    text = await _call_openrouter(
        prompt,
        system_prompt=ARXIV_LINKEDIN_SYSTEM_PROMPT,
    )

    parsed = _parse_json_response(text)
    if parsed and isinstance(parsed, dict):
        return {
            "body": str(parsed.get("body", ""))[:3000],
            "hashtags": parsed.get("hashtags", ["#Research", "#Technology"]),
        }

    # Fallback if LLM fails
    return {
        "body": (
            f"New research published on arXiv highlights important developments.\n\n"
            f'"{title}"\n\n'
            f"Read the full paper and explore more at {cta_link}"
        ),
        "hashtags": ["#Research", "#Technology", "#Innovation"],
    }


async def generate_arxiv_content(
    title: str, abstract: str, arxiv_id: str
) -> dict:
    """
    Full pipeline: Generate both X thread and LinkedIn post from an arXiv paper.

    Returns:
        Dict with keys: category, cta_link, x_thread, linkedin_post
    """
    category = _classify_paper_category(title, abstract)
    cta_link = _build_arxiv_cta_link(category, arxiv_id)

    x_thread = await generate_arxiv_x_thread(title, abstract, arxiv_id, cta_link)
    linkedin_post = await generate_arxiv_linkedin_post(title, abstract, arxiv_id, cta_link)

    return {
        "category": category,
        "cta_link": cta_link,
        "x_thread": x_thread,
        "linkedin_post": linkedin_post,
    }

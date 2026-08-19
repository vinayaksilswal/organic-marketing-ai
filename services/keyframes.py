"""First and last frame prompts for keyframe-driven video generation.

WHY FRAMES RATHER THAN ONE VIDEO PROMPT
---------------------------------------
A text-to-video model draws text as pixels it has learned to associate with a
prompt, so a sentence comes back as smeared pseudo-glyphs. That is why the
call to action in `video_pipeline_service` is spoken rather than written, and
why `video_outro` composites the end card with ffmpeg instead of asking for it.

An IMAGE model is a different proposition. Short strings render cleanly, and a
still has no motion to destabilise them. So the two frames that carry meaning
are generated as images first:

  FIRST FRAME  locks the look — subject, palette, lens, light. Every video
               model that accepts a start image inherits all of it, which is
               what stops one brand's clips looking like they came from five
               different companies.

  LAST FRAME   carries the brand name and the offer as real, readable text.
               This is the frame a viewer is looking at when they decide
               whether to act, and it is the one a video model is least able
               to produce unaided.

The clip is generated between them, which also fixes a structural problem: a
model asked for a ten-second story spends its fidelity budget evenly. Given a
start and an end it has somewhere to go.

SHAPE OF THE CLIP
-----------------
  0-3s   the hook. One image, already moving, already speaking.
  3-8s   the single action.
  8-10s  the outro, resolving onto the last frame.

The three-second hook is not a stylistic choice. It is the window in which a
scroll is decided, and it is also the point at which Instagram counts a view.
"""

from __future__ import annotations

import re
from typing import Any, Optional, Tuple

from loguru import logger

# =============================================================================
# What the end frame asks the viewer to do
# =============================================================================
# One source of truth, shared by the composited ffmpeg outro and the generated
# last frame. When these disagreed, the video said one thing and the card said
# another on the same clip.

HOOK_SECONDS = 3.0
OUTRO_SECONDS = 2.0
TOTAL_SECONDS = 10.0

# Deliberately narrow. A creator or influencer account often does sell
# something, so forcing "Follow for more" would overwrite a real offer.
_PAGE_MODELS = {"social page", "social_page", "page"}
_SHOP_MODELS = {"e-commerce", "ecommerce", "e commerce", "retail", "dtc", "shop"}


def _clean_domain(url: str) -> str:
    """Strip a URL to the part a person would read aloud."""
    url = (url or "").strip()
    for prefix in ("https://", "http://", "www."):
        if url.lower().startswith(prefix):
            url = url[len(prefix):]
    # The path stays. "acme.com/pricing" is where the offer actually lives,
    # and truncating it to the apex domain sends people somewhere else.
    # Lowercased because domains are case-insensitive and "Lumively.com" on an
    # end card reads as a typo rather than as a brand.
    return url.rstrip("/").strip().lower()


def _handle_from(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def cta_for(profile: Any) -> Tuple[str, str, str]:
    """(brand, call to action, destination) for this business.

    The business's own words win when it has stated them. `primaryOffer` is
    written from the copy on their own site, and "Start free - no credit card"
    beats any default we could invent because it is a promise they have
    already made publicly.

    The defaults below are for the businesses that stated nothing, which today
    is most of them: both e-commerce workspaces and two of the SaaS ones have
    an empty offer, so their end card rendered a brand name and nothing to do
    with it.
    """
    brand = (getattr(profile, "name", "") or "").strip()
    offer = (getattr(profile, "primaryOffer", "") or "").strip().rstrip(".")
    model = (getattr(profile, "businessModel", "") or "").strip().lower()
    domain = _clean_domain(getattr(profile, "websiteUrl", "") or "")

    if model in _PAGE_MODELS:
        # A themed page has nothing to sell and usually no website. The whole
        # economy of the account is the follow, so an offer describing a
        # transaction is wrong even when one has been set.
        cta = offer if re.match(r"^(follow|subscribe)\b", offer, re.IGNORECASE) else "Follow for more"
        if domain:
            # A page that does have a site still wants that traffic. The
            # handle is the fallback for having no site, not a replacement.
            return brand, cta, domain
        handle = _handle_from(brand)
        return brand, cta, (f"@{handle}" if handle else "")

    if model in _SHOP_MODELS:
        return brand, (offer or "Shop now"), domain

    # Everything else is a business with a site to send people to.
    if offer:
        return brand, offer, domain
    if domain:
        return brand, f"Visit {domain} today", domain
    return brand, "See how it works", ""


def cta_line(profile: Any) -> str:
    """The offer as one spoken sentence, for the video's closing line."""
    brand, cta, dest = cta_for(profile)
    if dest.startswith("@"):
        return f"{cta} - {brand}."
    # "Visit quantcai.in today at quantcai.in" - the default CTA already names
    # the destination, so appending it again stutters. Only add it when the
    # offer is the business's own wording and does not mention where to go.
    if dest and dest.lower() not in cta.lower():
        return f"{cta} at {dest}."
    if cta.lower().endswith(dest.lower()) or dest.lower() in cta.lower():
        return f"{cta}."
    return f"{cta} with {brand}." if brand else cta


# =============================================================================
# Frame prompts
# =============================================================================

_IMAGE_RULES = """
Rules for the prompt you write:
- Describe one literal scene a camera could photograph: subject, setting,
  lighting, lens, depth of field, mood.
- One subject only. Two subjects in a still means neither is sharp.
- Ground it in this industry's real world - the objects, tools, screens and
  environments these people actually use.
- No abstract blobs, no glowing brains, no floating holograms, no data
  particles, no neon cityscapes, no stock-photo handshakes.
- 40-70 words, comma-separated descriptive phrases.
Output ONLY the prompt text, no preamble and no quotes around it.
"""


async def first_frame_prompt(
    profile: Any,
    intelligence: dict,
    scene_hint: str = "",
    recent_prompts: Optional[list] = None,
) -> str:
    """The opening still. It has three seconds to stop a scroll.

    Written as a frame of an ALREADY-MOVING moment rather than an establishing
    shot. A start image of an empty room tells the video model to begin with an
    empty room, and the hook is gone before anything happens.
    """
    from services.ai_service import _call_openrouter

    brand = (getattr(profile, "name", "") or "the brand").strip()
    what = (getattr(profile, "description", "") or "").strip()
    audience = (getattr(profile, "targetAudience", "") or "").strip()
    colors = ", ".join(getattr(profile, "brandColors", None) or []) or "a restrained modern palette"
    hook = (intelligence or {}).get("hook") or (intelligence or {}).get("pain_point") or ""

    avoid = ""
    if recent_prompts:
        joined = "\n".join(f"- {p[:140]}" for p in recent_prompts[:4])
        avoid = f"\nRecent openings for this brand. Choose a different subject and setting:\n{joined}\n"

    instruction = (
        "Write ONE image-generation prompt for the OPENING FRAME of a "
        "10-second vertical ad.\n\n"
        f"Brand: {brand}\n"
        + (f"What it does: {what}\n" if what else "")
        + (f"Audience: {audience}\n" if audience else "")
        + (f"The tension it resolves: {hook}\n" if hook else "")
        + (f"Scene to open on: {scene_hint}\n" if scene_hint else "")
        + f"Brand colours: {colors}\n"
        + avoid
        + "\nThis frame is the first thing a viewer sees and it has about three "
        "seconds to earn the rest. So it is a frame taken from the MIDDLE of an "
        "action, not the start of one: someone already reacting, already "
        "reaching, already mid-expression. Never an empty room, never a wide "
        "establishing shot, never a logo.\n"
        "No text, letters, numbers or logos anywhere in this frame - the "
        "closing frame carries all of the words.\n"
        + _IMAGE_RULES
    )

    try:
        out = (await _call_openrouter(
            instruction,
            system_prompt=(
                "You are an art director writing prompts for image generation "
                "models. You describe concrete scenes, never marketing abstractions."
            ),
        )).strip().strip('"')
        if out:
            return f"{out[:900]}, vertical 9:16, {colors} colour palette, photographic, sharp focus, no text"
    except Exception as e:
        logger.warning(f"First frame prompt failed for {brand}: {e}")

    subject = what.split(".")[0][:120] if what else "a person at work"
    return (
        f"Editorial photograph, close on {subject}, caught mid-action, natural window light, "
        f"shallow depth of field, vertical 9:16, {colors} colour palette, photographic, "
        f"sharp focus, no text"
    )


async def last_frame_prompt(profile: Any, first_frame: str = "") -> str:
    """The closing still, carrying the brand name and the offer as real text.

    Deliberately NOT written by the language model. Everything that matters on
    this frame is a fixed string - the brand name and the call to action - and
    handing fixed strings to a model that paraphrases is how a card ends up
    saying "Shop Today!" for a business whose offer is "Shop now". The only
    variable is the palette, and that is read rather than invented.

    The layout is spare on purpose. Image models render short text well and
    crowded text badly, so this asks for two lines on a plain ground with
    nothing competing: no product, no person, no scenery.
    """
    brand, cta, dest = cta_for(profile)
    colors = ", ".join(getattr(profile, "brandColors", None) or []) or "deep charcoal with a single bright accent"

    # The destination only earns a line when it is not already inside the CTA.
    show_dest = dest and dest.lower() not in cta.lower()

    lines = [
        f'the brand name "{brand}" in large bold clean sans-serif type, centred',
        f'below it the words "{cta}" in medium weight, smaller, centred',
    ]
    if show_dest:
        lines.append(f'below that "{dest}" in small light type, centred')

    return (
        "A minimal vertical 9:16 end card, flat solid background in "
        f"{colors}, no photograph and no objects, nothing else in frame: "
        + ", ".join(lines)
        + ". Generous even margins, all text horizontally centred and "
        "vertically centred as one block, crisp high-contrast lettering, "
        "perfectly spelled, no logo, no icons, no decoration, no gradients, "
        "sharp focus, clean typography, poster design"
    )


async def build_keyframes(
    profile: Any,
    intelligence: dict,
    scene_hint: str = "",
    recent_prompts: Optional[list] = None,
) -> dict:
    """Both frame prompts plus the timing the clip should be built to."""
    first = await first_frame_prompt(
        profile, intelligence, scene_hint=scene_hint, recent_prompts=recent_prompts
    )
    last = await last_frame_prompt(profile, first_frame=first)
    brand, cta, dest = cta_for(profile)

    return {
        "firstFramePrompt": first,
        "lastFramePrompt": last,
        "brand": brand,
        "cta": cta,
        "destination": dest,
        "spokenClosingLine": cta_line(profile),
        "timing": {
            "hookSeconds": HOOK_SECONDS,
            "outroSeconds": OUTRO_SECONDS,
            "totalSeconds": TOTAL_SECONDS,
        },
    }

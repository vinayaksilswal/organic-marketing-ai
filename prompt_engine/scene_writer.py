"""LLM-backed scene writing for video briefs.

The compilers in this package assemble a brief into each model's dialect, but
they were also *inventing* the content from f-string templates:

    "A single subject in an isolated setting illustrating {intent}."
    "The subject performs one smooth, continuous linear motion highlighting {offer}."

That is structurally valid and creatively dead — no person, no place, no hook,
and the raw intent dropped in mid-sentence. It is the same failure as the
original image-prompt template ("Modern social media graphic for {name}...")
which made every asset identical.

Division of responsibility now:

    scene_writer  — the LLM writes the creative content as structured fields
    compilers     — assemble those fields into model-specific syntax
    validator     — reject anything that breaks a documented render rule

The brief below encodes what the research established about 8-12s vertical
ads, and what these models can actually render.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from loguru import logger

# One camera move, chosen from moves these models execute cleanly. Anything
# that changes direction mid-shot produces morphing.
ALLOWED_CAMERA_MOVES = [
    "slow push-in",
    "slow pull-back",
    "slow pan left",
    "slow pan right",
    "locked-off static",
    "gentle handheld sway",
    "slow overhead descent",
]

_SYSTEM = """You write shot briefs for AI video generators making Instagram Reels and paid social ads. You are writing an ADVERTISEMENT, not a showreel: a viewer scrolling with the sound off must stop, understand what this business does, and want it.

WHAT MAKES THESE ADS WORK
- The hook is the FIRST FRAME. Something is already happening. No establishing drift, no fade in, no logo card.
- The strongest ten seconds is almost always a HUMAN REACTION — the second a result lands, shoulders dropping, a slow nod, a breath let out, a smile someone did not plan. That sells far harder than showing the product working.
- Specificity is what stops the scroll. "a woman at a desk" is invisible. "a founder still in yesterday's hoodie, phone face-down beside cold coffee" is a person.

WHAT THESE MODELS CANNOT RENDER — avoid absolutely
- Legible screen content. Never describe what a monitor, phone, dashboard or terminal displays. A screen is light and colour on a face, always out of focus.
- More than four words of on-screen text, and usually none.
- Camera moves that change direction, cuts, or "then it flips to reveal".
- More than one person, or more than three notable props. Every extra element steals definition from the rest.
- Fast physics: pouring, splashing, bouncing, shattering. Mass and momentum break down.

OUTPUT — valid JSON only, no markdown, no preamble:
{
  "camera": "<one move from the allowed list, plus a lens if useful>",
  "subject": "<one specific person or object, with two concrete identifying details>",
  "action": "<one continuous physical action, and the reaction it produces>",
  "environment": "<the room and its light, two details maximum>",
  "mood": "<the feeling, in three or four words>",
  "audio": "<ambience plus one punctuating sound, 12 words maximum>",
  "onscreen_text": "<1-4 words, or empty string for none>"
}

Every field is a fragment, not a sentence. No trailing full stops."""


def _extract_json(raw: str) -> Optional[Dict[str, Any]]:
    """Pull a JSON object out of whatever shape the model returned."""
    text = (raw or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        parts = text.split("\n", 1)
        text = parts[1] if len(parts) > 1 else ""
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
        text = text.strip()
    try:
        parsed = json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
        except Exception:
            return None
    if isinstance(parsed, list) and parsed:
        parsed = parsed[0]
    return parsed if isinstance(parsed, dict) else None


def _clean_fragment(value: Any, limit: int = 200) -> str:
    text = str(value or "").strip().strip(".").strip()
    text = re.sub(r"\s+", " ", text)
    return text[:limit]


async def write_scene(
    intent: str,
    business_name: Optional[str] = None,
    what_it_does: Optional[str] = None,
    audience_motivator: Optional[str] = None,
    brand_aesthetic: Optional[str] = None,
    primary_offer: Optional[str] = None,
    recent_scenes: Optional[list] = None,
) -> Optional[Dict[str, str]]:
    """Write the creative content of one shot. Returns None if the LLM fails.

    Callers fall back to their template so a provider outage degrades the
    output rather than breaking generation.
    """
    known = [f"What the ad is for: {intent}"]
    if business_name:
        known.append(f"Business: {business_name}")
    if what_it_does:
        known.append(f"What it actually does: {what_it_does}")
    if audience_motivator:
        known.append(f"What the viewer cares about: {audience_motivator}")
    if brand_aesthetic:
        known.append(f"Brand look: {brand_aesthetic}")
    if primary_offer:
        known.append(
            f"The action it should drive: {primary_offer} "
            "(mood context only — do NOT put this sentence on screen)"
        )

    avoid = ""
    if recent_scenes:
        lines = "\n".join(f"- {str(s)[:160]}" for s in recent_scenes[:5])
        avoid = (
            "\n\nRecent shots for this brand are below. Yours must differ in "
            "setting, camera and opening beat — not be a paraphrase:\n" + lines
        )

    prompt = (
        "\n".join(known)
        + avoid
        + "\n\nAllowed camera moves: "
        + ", ".join(ALLOWED_CAMERA_MOVES)
        + "\n\nWrite the shot as JSON."
    )

    try:
        from services.ai_service import _call_openrouter

        raw = await _call_openrouter(prompt, system_prompt=_SYSTEM, json_response=True)
        data = _extract_json(raw)
        if not data:
            # Some free models reject response_format outright.
            raw = await _call_openrouter(
                prompt + "\n\nReply with the JSON object only.", system_prompt=_SYSTEM
            )
            data = _extract_json(raw)
        if not data:
            logger.warning("Scene writer returned nothing parseable")
            return None

        scene = {
            "camera": _clean_fragment(data.get("camera"), 80) or "slow push-in",
            "subject": _clean_fragment(data.get("subject"), 160),
            "action": _clean_fragment(data.get("action"), 200),
            "environment": _clean_fragment(data.get("environment"), 160),
            "mood": _clean_fragment(data.get("mood"), 80),
            "audio": _clean_fragment(data.get("audio"), 100),
            "onscreen_text": _clean_fragment(data.get("onscreen_text"), 40),
        }
        if not scene["subject"] or not scene["action"]:
            logger.warning("Scene writer omitted subject or action")
            return None

        # On-screen text degrades past a few words, so hard-cap it here rather
        # than trusting the model to have counted.
        words = scene["onscreen_text"].split()
        if len(words) > 4:
            scene["onscreen_text"] = " ".join(words[:4])

        return scene
    except Exception as e:
        logger.warning(f"Scene writer failed, caller will fall back: {e}")
        return None

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

THE FIRST THREE SECONDS DECIDE EVERYTHING
Meta's own creative research is unambiguous: a 9:16 ad has to land three hooks
SIMULTANEOUSLY inside the first three seconds, not in sequence.

  VISUAL   something already in motion, filling the frame. Not an establishing
           drift, not a fade in, not a logo card.
  VERBAL   the spoken line has STARTED. Its first words state the problem.
  TEXT     the hero string is already on screen and readable.

All three at once, from frame one. This is a constraint on the fields below,
not a field of its own:

  `action` must START mid-movement. Never "she sits down and then opens the
  laptop" — the laptop is already open and the scan is already running.
  `hero_text` must be on screen from the first frame. Never save it for a
  reveal at the end; the viewer who was going to scroll has already scrolled.
  `voiceover` must open on the PROBLEM, not on a greeting or the brand name.
  Its first four words are the ones that matter.

Then 3-8s plays the single action out, and 8-10s is the reaction plus the brand
word.

WHAT MAKES THESE ADS WORK
- Show the PROBLEM or the RESULT as a thing the viewer can see and read, not as a mood. "A red alert banner reading 'RSA-2048 Encryption Vulnerable'" sells; "an atmosphere of quiet concern" does not.
- Specificity is what stops the scroll. "a woman at a desk" is invisible. "a founder still in yesterday's hoodie, phone face-down beside cold coffee" is a person.
- A human reaction — shoulders dropping, a slow nod — is the closing beat, not the whole ad. It only means something after the viewer has seen what caused it.

THE SCREEN IS USUALLY THE HERO
For software, the product IS the shot. Current models render a large, central,
high-contrast string on a screen accurately — a red alert banner reading
"RSA-2048 Encryption Vulnerable", a chat box being typed into reading "why is
my circuit failing?", a notification card sliding in reading "$27 Pro Tier
Sale". Ask for ONE such string and it lands.

What still fails is INCIDENTAL text — the small labels, menu items and body
copy around it. Do not ask for those. Describe them as out of focus and let
them blur into texture; nobody reads them and the hero string carries the
message on its own.

So: name the one string the viewer must read, say where it renders, and let
everything else fall away. A shot can be pure product with no person in it at
all — that is often the strongest option for software.

WHAT THESE MODELS STILL CANNOT DO — avoid absolutely
- Camera moves that change direction, cuts, or "then it flips to reveal".
- More than one person. Extra faces trigger identity drift and morphing.
- Fast physics: pouring, splashing, bouncing, shattering. Mass and momentum break down.
- More than one hero string. Two competing text elements and both degrade.
- Naming a typeface, a hex colour or a brand colour name. The model cannot map
  "Quantum Cyan" or "Space Grotesk" to anything — say "cold blue" or "clean sans".
- Listing what you do not want. These prompts have no negative parsing, so
  "no holograms" simply raises the odds of a hologram. Describe what IS there.

BRANDING — THE LAST BEAT
The clip has to leave the viewer knowing WHOSE it is, or the reach builds
nothing. So the final beat carries the brand, on a real surface the camera is
already looking at: a logo etched on the product, a name on the workshop wall,
a handle in a corner lower-third.

But it must stay SHORT. "Visit our website, link in bio" is six words and comes
back as smeared glyphs — it destroys the shot and says nothing. The brand name
or the @handle alone renders cleanly and is what people actually remember and
search for. A full call to action belongs in the caption, which is read, not
rendered.

  GOOD end frame: "QuantCAI"  /  "@ridgelinebikes"  /  "Bristol built"
  BAD  end frame: "Visit quantcai.info to start your free scan"
                  "Follow us for more tips"  (says nothing, wastes the frame)

Put it on something PHYSICAL that holds still: etched into the product, painted
on the wall, stamped into leather, embossed on the packaging. Never on a screen,
monitor, phone or a floating overlay — those surfaces are re-drawn every frame
and the word dissolves.

Describe that placement in `brand_moment`. Put the word itself in
`onscreen_text`.

OUTPUT — valid JSON only, no markdown, no preamble:
{
  "camera": "<one move from the allowed list, plus a lens if useful>",
  "subject": "<the product on screen, or one specific person, with two concrete identifying details>",
  "action": "<one continuous physical action, and the reaction it produces>",
  "environment": "<the room and its light, two details maximum>",
  "mood": "<the feeling, in three or four words>",
  "audio": "<ambience plus one punctuating sound, 12 words maximum>",
  "hero_text": "<the ONE string the viewer must read: the problem, the result, or the offer. 2-6 words. Empty only if the shot has no screen>",
  "hero_surface": "<where it renders: a red alert banner, a chat box mid-typing, a notification card sliding in, the dashboard header>",
  "voiceover": "<the exact words spoken aloud, verbatim, 10-20 words. See below>",
  "brand_moment": "<where the brand word sits in the closing beat, on a physical surface>"
}

NEVER INVENT A NUMBER
The hero string and the spoken line are advertising claims. A made-up figure —
"47 Keys Exposed", "3x faster", "10,000 teams" — is an unsubstantiated claim
about a real customer, and it is illegal to publish, not merely inaccurate.

Use a figure ONLY if it appears verbatim in the business context above.
Otherwise name the STATE, which is just as concrete and costs nothing:

  GOOD: "Vulnerable Keys Found"   BAD: "47 Vulnerable Keys Found"
  GOOD: "Scan Complete"           BAD: "Scan Complete in 4.2s"
  GOOD: "Migration Ready"         BAD: "92% Migration Ready"

THE SPOKEN LINE
These models generate synchronised speech, so write the actual line — not a
description of one. "Explains the benefit" produces nothing. The words do.

Write it the way a real person talks to camera: contractions, one idea, no
slogan cadence. It should land the same beat the visual lands, then hand off.

  GOOD: "I found out our encryption breaks in four years. Took one scan."
  GOOD: "Everyone says migrate to post-quantum. Nobody says which keys are exposed."
  BAD:  "Discover the power of enterprise-grade quantum readiness today."
        (nobody says this out loud; it is a banner, not a sentence)
  BAD:  "The founder explains the security benefit." (a description, not a line)

Keep it to 10-20 words. Past that the delivery outruns ten seconds and the
model clips it mid-word.

Every other field is a fragment, not a sentence. No trailing full stops."""


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


def _clean_voiceover(value: Any) -> str:
    """The spoken line, kept to what fits in ten seconds.

    Unlike the other fields this IS a sentence, so trailing punctuation is
    preserved — it carries the delivery. Roughly 20 words is the ceiling at
    natural pace before the model clips mid-word.
    """
    text = re.sub(r"\s+", " ", str(value or "").strip()).strip('"')
    if not text:
        return ""
    words = text.split()
    if len(words) > 20:
        text = " ".join(words[:20]).rstrip(",;:") + "."
    return text[:220]


# Legal and filing suffixes are never part of how anyone says a brand out loud,
# so they only eat frame budget.
_LEGAL_SUFFIX = re.compile(
    r"\b(inc|llc|ltd|limited|co|corp|corporation|gmbh|bv|nv|plc|pty|pvt|"
    r"private|llp|sarl|ag|oy|ab|as|srl|spa)\b\.?",
    re.IGNORECASE,
)


def _brand_endframe(business_name: Optional[str]) -> str:
    """The word the final frame holds.

    One word, because that is what these models render legibly and what a
    viewer can actually retain and type into a search box afterwards. Anything
    longer comes back as smeared glyphs and buys nothing.
    """
    name = _LEGAL_SUFFIX.sub(" ", str(business_name or ""))
    name = re.sub(r"[^\w\s&'-]", " ", name)
    words = [w for w in name.split() if w]
    if not words:
        return ""
    # Leading filler is not the brand — "The Ridgeline" is remembered as
    # "Ridgeline".
    if len(words) > 1 and words[0].lower() in {"the", "a", "an", "my", "get", "go", "try", "we"}:
        words = words[1:]

    # One word is the rule. The exception is a short two-word name whose first
    # word is meaningless alone: "Blue Bottle" clipped to "Blue" recalls
    # nothing, and at eleven characters the pair still reads as one glyph
    # cluster in a vertical frame. Past twelve characters it does not, so
    # "Northwind Coffee" correctly becomes "Northwind".
    joined = " ".join(words[:2])
    if len(words) > 1 and len(joined) <= 12:
        return joined
    return words[0][:20]


async def write_scene(
    intent: str,
    business_name: Optional[str] = None,
    what_it_does: Optional[str] = None,
    audience_motivator: Optional[str] = None,
    brand_aesthetic: Optional[str] = None,
    primary_offer: Optional[str] = None,
    recent_scenes: Optional[list] = None,
    transformation: Optional[str] = None,
    avoid_visual_world: Optional[str] = None,
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
    if transformation:
        # The before/after is the argument the ad makes. Without it the writer
        # has a subject and a setting but no reason for the shot to exist, and
        # produces a mood piece.
        known.append(
            f"The change this makes for the viewer: {transformation} "
            "(the hero string names the BEFORE or the AFTER — pick one)"
        )
    if primary_offer:
        known.append(
            f"The action it should drive: {primary_offer} "
            "(mood context only — do NOT put this sentence on screen)"
        )
    if avoid_visual_world:
        known.append(
            f"How every competitor in this category already looks: "
            f"{avoid_visual_world} (do not shoot that — it is invisible "
            "precisely because everyone uses it)"
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
            "hero_text": _clean_fragment(data.get("hero_text"), 60),
            "hero_surface": _clean_fragment(data.get("hero_surface"), 120),
            "voiceover": _clean_voiceover(data.get("voiceover")),
            "brand_moment": _clean_fragment(data.get("brand_moment"), 120),
        }

        # One hero string, six words at most. Past that the reference material
        # shows glyphs starting to break down, and a scrolling viewer stops
        # reading anyway.
        hero_words = scene["hero_text"].split()
        if len(hero_words) > 6:
            scene["hero_text"] = " ".join(hero_words[:6])
        if not scene["subject"] or not scene["action"]:
            logger.warning("Scene writer omitted subject or action")
            return None

        # The end frame is not a creative decision. Every clip closes on the
        # business name so the reach compounds into brand recall instead of
        # evaporating — and on ONE word, because that is the only text length
        # these models render legibly and the only length a scrolling viewer
        # retains. The model's suggestion is only a fallback for when we have
        # no business name to use.
        scene["onscreen_text"] = _brand_endframe(business_name)
        return scene
    except Exception as e:
        logger.warning(f"Scene writer failed, caller will fall back: {e}")
        return None

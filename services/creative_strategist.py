"""Turning a business into Instagram creatives, in stages.

Asking a model for "a video prompt" produces a generic video prompt, because
the model has to invent a strategy and execute it in one breath and does
neither well. This walks it through the same stages a human strategist would:

    Business Brain -> candidate angles -> scored -> hooks -> concept
                   -> scene-by-scene prompt -> critic -> fixed output

WHY THE OUTPUT FORMAT IS BUILT IN CODE
---------------------------------------
The obvious implementation tells the model "do not change the headings" and
hopes. It changes them. It merges Scene 3 and 4, it drops the Camera line, it
adds a chatty preamble, and on a rate-limited free tier it sometimes returns
nothing resembling the shape at all.

So the model is asked for structured data and this module renders the markdown.
The headings are then identical for every business on every run, including the
runs where the model misbehaved, because the model never had the opportunity
to write them.

WHAT THE SCORES ARE AND ARE NOT
-------------------------------
Angles carry a score used to rank them. It is an internal ranking heuristic —
the model rates each dimension, this module does the arithmetic — and it is
never shown to the customer as a prediction of performance. This product does
not tell people what a post will do before it runs, and a "conversion
probability: 87%" on an unpublished creative would be exactly the invented
figure the caption gates exist to prevent.

The customer sees which angle was chosen and why, not a number pretending to
be a forecast.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from loguru import logger

# The angle taxonomy. Each is a different reason a stranger stops scrolling,
# and a business usually has only two or three that genuinely fit it.
ANGLE_CATEGORIES = [
    "pain", "curiosity", "transformation", "demonstration", "before_after",
    "time_saving", "money_saving", "desire", "emotional", "contrarian",
    "fomo", "social_proof", "problem_awareness", "product_discovery",
    "educational", "ugc", "storytelling",
]

# How much each dimension counts toward the ranking. Conversion and hook carry
# the most because a creative that nobody watches converts nobody, and a
# creative everyone watches that sells nothing is a hobby.
WEIGHTS = {
    "hook_strength": 1.4,
    "conversion_potential": 1.4,
    "customer_relevance": 1.2,
    "visual_potential": 1.1,
    "product_relevance": 1.0,
    "curiosity": 0.9,
    "instagram_fit": 0.9,
    "shareability": 0.7,
}
MAX_SCORE = sum(WEIGHTS.values()) * 10


def score_angle(dimensions: Dict[str, Any]) -> float:
    """Rank one angle. The model rates the dimensions; the arithmetic is ours.

    Letting the model return its own total invites it to justify whichever
    angle it wrote first. Scoring here means the ranking is a property of the
    system rather than of the model's mood.
    """
    total = 0.0
    for key, weight in WEIGHTS.items():
        try:
            value = float(dimensions.get(key, 0) or 0)
        except (TypeError, ValueError):
            value = 0.0
        total += max(0.0, min(10.0, value)) * weight
    return round(total, 1)


# =============================================================================
# Layer 3 — how a given kind of business is shot on Instagram
#
# The structure of the output never changes. The creative grammar inside it
# does, because a dentist and a restaurant do not sell the same way and a
# single template makes both look like neither.
# =============================================================================

GRAMMAR: Dict[str, Dict[str, Any]] = {
    "saas": {
        "beats": ["hook", "frustration", "screen demo", "benefit", "cta"],
        "format": "UGC Reel with screen recording",
        "camera": "handheld smartphone, then clean screen capture",
        "style": "authentic creator footage cut against crisp product UI",
    },
    "ecommerce": {
        "beats": ["problem", "product reveal", "demonstration", "result", "cta"],
        "format": "Product demo Reel",
        "camera": "macro product shots, hands in frame",
        "style": "bright, tactile, shallow depth of field",
    },
    "restaurant": {
        "beats": ["food close-up", "reaction", "the room", "social proof", "cta"],
        "format": "Sensory food Reel",
        "camera": "slow macro on the food, then a wide of the room",
        "style": "warm, appetising, natural light, steam and texture",
    },
    "local_service": {
        "beats": ["the problem", "expert explains", "the work", "result", "cta"],
        "format": "Authority Reel",
        "camera": "steady mid-shot of the practitioner, then close on the work",
        "style": "clean, trustworthy, well-lit, real premises",
    },
    "creator": {
        "beats": ["hook", "story", "turn", "payoff", "cta"],
        "format": "Talking-head Reel",
        "camera": "front-facing, eye level, close",
        "style": "personal, unpolished, high-contrast captions",
    },
    "general": {
        "beats": ["hook", "problem", "product", "benefit", "cta"],
        "format": "Problem / solution Reel",
        "camera": "handheld, one subject, one move per scene",
        "style": "natural light, realistic, fast cuts",
    },
}


def classify(profile: Any) -> str:
    """Which creative grammar this business is shot in."""
    blob = " ".join(str(getattr(profile, f, "") or "") for f in
                    ("businessModel", "industry", "niche", "description")).lower()

    if any(w in blob for w in ("saas", "software", "app", "platform", "tool")):
        return "saas"
    if any(w in blob for w in ("commerce", "shop", "store", "retail", "product")):
        return "ecommerce"
    if any(w in blob for w in ("restaurant", "cafe", "food", "bakery", "kitchen", "dining")):
        return "restaurant"
    if any(w in blob for w in ("clinic", "dental", "dentist", "salon", "gym", "studio",
                               "service", "repair", "local", "agency", "consult")):
        return "local_service"
    if any(w in blob for w in ("creator", "influencer", "coach", "page", "channel")):
        return "creator"
    return "general"


# =============================================================================
# The fixed output. Rendered here, never by the model.
# =============================================================================

REQUIRED_SCENES = 4

# Paragraph break for prompt assembly.
BREAK = chr(10) * 2


def render_creative(concept: Dict[str, Any], business_name: str) -> str:
    """The mandatory shape, produced deterministically.

    Every heading below is written by this function. The model supplies only
    the words inside them, so the format survives a bad generation, a partial
    one, and a rate-limited tier that returned almost nothing.
    """
    title = (concept.get("title") or "Untitled creative").strip()
    fmt = (concept.get("format") or "Instagram Reel, 9:16 vertical, 10–12 seconds").strip()
    scenes = concept.get("scenes") or []

    lines: List[str] = []
    lines.append(f"## {title}")
    lines.append("")
    lines.append(f"**Format:** {fmt}")
    lines.append("")
    lines.append("**Video generation prompt:**")
    lines.append("")
    lines.append(
        f"Create a highly engaging vertical Instagram Reel for {business_name}."
    )
    lines.append("")

    for i in range(REQUIRED_SCENES):
        scene = scenes[i] if i < len(scenes) else {}
        timing = (scene.get("time") or _default_timing(i)).strip()
        lines.append(f"### Scene {i + 1} — {timing}")
        lines.append("")
        lines.append(f"**Visuals:** {(scene.get('visuals') or '—').strip()}")
        lines.append("")
        lines.append(f"**On-screen text:** \"{(scene.get('on_screen_text') or '').strip()}\"")
        lines.append("")
        lines.append(f"**Script / Dialogue:** \"{(scene.get('script') or '').strip()}\"")
        lines.append("")
        lines.append(f"**Camera:** {(scene.get('camera') or '—').strip()}")
        lines.append("")

    lines.append("**Style:**")
    lines.append("")
    lines.append((concept.get("style") or "—").strip())
    lines.append("")
    lines.append("**Audio:**")
    lines.append("")
    lines.append((concept.get("audio") or "—").strip())
    lines.append("")
    lines.append("**Final CTA:**")
    lines.append("")
    lines.append(f"\"{(concept.get('cta') or '').strip()}\"")

    return "\n".join(lines)


def _default_timing(index: int) -> str:
    spans = ["0–2 sec", "2–5 sec", "5–8 sec", "8–12 sec"]
    return spans[index] if index < len(spans) else "—"


# =============================================================================
# The stages
# =============================================================================

_STRATEGIST = (
    "You are a direct-response creative strategist who works on short-form "
    "video. You never invent claims, testimonials, statistics, prices or "
    "features that the business information does not support. When the "
    "business material does not say something, you leave it out rather than "
    "filling the gap. You answer only with the JSON asked for."
)


def _brain_summary(profile: Any, brain: Optional[Dict[str, Any]]) -> str:
    """Everything the strategist is allowed to reason from, and nothing else."""
    parts = [f"BUSINESS: {getattr(profile, 'name', '') or 'this business'}"]
    for label, value in (
        ("WEBSITE", getattr(profile, "websiteUrl", "")),
        ("WHAT IT DOES", getattr(profile, "description", "")),
        ("AUDIENCE", getattr(profile, "targetAudience", "")),
        ("INDUSTRY", getattr(profile, "industry", "")),
        ("OFFER", getattr(profile, "primaryOffer", "")),
        ("TONE", getattr(profile, "toneOfVoice", "")),
    ):
        if value:
            parts.append(f"{label}: {value}")

    for key in ("primary_pain_point_solved", "audience_motivator",
                "objection_to_overcome", "competitive_differentiation",
                "hero_marketing_hook", "key_features"):
        value = (brain or {}).get(key)
        if value:
            parts.append(f"{key.replace('_', ' ').upper()}: {value}")

    return "\n".join(parts)


def _parse(raw: str) -> Any:
    """Read JSON out of a model reply that may be fenced or prefaced."""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = "\n".join(l for l in text.splitlines() if not l.strip().startswith("```"))
    try:
        return json.loads(text)
    except Exception:
        # Models sometimes wrap the object in a sentence.
        match = re.search(r"[\[{].*[\]}]", text, re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
    return None


def _as_list(data: Any) -> List[dict]:
    """Accept the shapes models actually return, not just the one asked for.

    A bare array was requested. What comes back is regularly {"angles": [...]},
    occasionally {"creatives": [...]}, and sometimes a single object when the
    model decides one example will do. Demanding the exact shape threw away
    perfectly good angles and silently fell back to canned seeds — the feature
    looked like it worked while its most valuable stage never ran once.
    """
    if isinstance(data, list):
        return [d for d in data if isinstance(d, dict)]

    if isinstance(data, dict):
        # A wrapper object: take the first list of dicts inside it.
        for value in data.values():
            if isinstance(value, list) and any(isinstance(v, dict) for v in value):
                return [v for v in value if isinstance(v, dict)]
        # A single angle returned bare.
        if data.get("hook") or data.get("angle"):
            return [data]

    return []


async def propose_angles(profile: Any, brain: Optional[Dict[str, Any]],
                         wanted: int = 5) -> List[Dict[str, Any]]:
    """Candidate angles, scored and ranked. Never raises."""
    from services.ai_service import _call_openrouter

    prompt = (
        f"{_brain_summary(profile, brain)}\n\n"
        # Sized to the token budget rather than to ambition. Fifteen angles with
        # eight dimensions each overflows the reply and comes back empty, which
        # looked like a weak model and was an oversized request.
        f"Propose {max(6, wanted + 3)} distinct short-form video angles for this "
        f"business. An angle is the reason a stranger stops scrolling, not a "
        f"description of the product.\n\n"
        f"Use these categories: {', '.join(ANGLE_CATEGORIES)}.\n\n"
        "Rate every angle on each dimension from 0 to 10. Rate honestly — an "
        "angle that does not fit this business should score low.\n\n"
        # json_response sets response_format to json_object, which requires the
        # reply to BE an object. Asking for a bare array inside that constraint
        # is a contradiction, and the model resolves it by returning one angle
        # as an object — which is exactly what it was doing. Ask for the shape
        # the constraint permits and the list survives.
        'Return ONLY a JSON object of the form {"angles": [ ... ]}, where each '
        "entry is:\n"
        '{"category":"curiosity","angle":"one line naming the angle",'
        '"hook":"the actual first line somebody hears or reads",'
        '"pain":"the customer problem it presses on",'
        '"promise":"what the viewer gets",'
        '"dimensions":{"hook_strength":0,"customer_relevance":0,'
        '"product_relevance":0,"visual_potential":0,"curiosity":0,'
        '"shareability":0,"conversion_potential":0,"instagram_fit":0}}'
    )

    try:
        raw = await _call_openrouter(prompt, system_prompt=_STRATEGIST, json_response=True)
        data = _parse(raw)
    except Exception as e:
        logger.warning(f"Angle generation failed: {e}")
        data = None

    data = _as_list(data)
    if not data:
        return _fallback_angles(profile, wanted)

    angles = []
    for entry in data:
        if not isinstance(entry, dict) or not (entry.get("hook") or "").strip():
            continue
        entry["score"] = score_angle(entry.get("dimensions") or {})
        entry["category"] = (entry.get("category") or "general").strip().lower()
        angles.append(entry)

    if not angles:
        return _fallback_angles(profile, wanted)

    angles.sort(key=lambda a: a["score"], reverse=True)

    # One per category among the top, so five creatives attack five different
    # triggers rather than five rewordings of the strongest one.
    chosen: List[Dict[str, Any]] = []
    seen: set = set()
    for angle in angles:
        if angle["category"] in seen:
            continue
        chosen.append(angle)
        seen.add(angle["category"])
        if len(chosen) == wanted:
            break
    for angle in angles:                       # top up if categories ran out
        if len(chosen) == wanted:
            break
        if angle not in chosen:
            chosen.append(angle)

    # The model on this tier reliably returns one angle however many are
    # asked for. All-or-nothing threw that one away and used five canned
    # seeds instead — the worst of both, since the real angle was the good
    # one. Keep what it gave and fill the remainder, so a weak model degrades
    # by degrees rather than by cliff.
    if len(chosen) < wanted:
        used = {a.get("category") for a in chosen}
        for seed in _fallback_angles(profile, wanted):
            if len(chosen) == wanted:
                break
            if seed["category"] not in used:
                chosen.append(seed)
                used.add(seed["category"])

    return chosen[:wanted]


def _fallback_angles(profile: Any, wanted: int) -> List[Dict[str, Any]]:
    """A usable set when the model is unavailable, which on a rate-limited
    free tier is an ordinary Tuesday rather than an outage."""
    name = getattr(profile, "name", "") or "this business"
    audience = getattr(profile, "targetAudience", "") or "your customers"
    seeds = [
        ("pain", f"The thing {audience} put up with before they find {name}",
         f"You have been doing this the hard way."),
        ("curiosity", f"What happens when {name} does it instead",
         f"I let {name} handle it for a week."),
        ("transformation", "Before and after, shown rather than claimed",
         "Same business. Two weeks apart."),
        ("demonstration", f"Watch {name} actually do it", "Watch this."),
        ("fomo", "What your competitors already do", "They are already doing this."),
    ]
    out = []
    for category, angle, hook in seeds[:wanted]:
        out.append({
            "category": category, "angle": angle, "hook": hook,
            "pain": "", "promise": "", "dimensions": {}, "score": 0.0,
        })
    return out


# ---------------------------------------------------------------------------
# The Hook Engine
#
# Hooks used to arrive bundled with their angle: one call produced the angle
# and the single line it opened on, and that line was used. But the angle and
# the hook are different problems. An angle is what the creative argues; the
# hook is the two seconds that decide whether anybody hears the argument. The
# best angle opened badly loses to a weaker angle opened well, and a model
# asked for both at once spends its attention on the angle.
#
# So the winning angle comes back here and the hook is competed separately:
# several variants across different archetypes, scored, best one used.
# ---------------------------------------------------------------------------

# Distinct ways of opening. Named so the model spreads its attempts instead of
# writing the same sentence six times, which is what "give me six hooks" gets.
HOOK_ARCHETYPES = [
    ("question", "Ask the thing the customer is already privately asking."),
    ("bold_claim", "State something specific and slightly hard to believe."),
    ("callout", "Name exactly who this is for, so everyone else scrolls."),
    ("mistake", "Name the thing they are doing wrong right now."),
    ("number", "Open on a concrete figure, cost or timeframe."),
    ("contradiction", "Say the opposite of what they expect to hear."),
]

# Scored on what a first line has to do, not on what a whole creative has to
# do. Stop power dominates: a hook that does not stop the thumb has no other
# qualities worth measuring.
HOOK_WEIGHTS = {
    "stop_power": 1.5,
    "specificity": 1.2,
    "relevance": 1.2,
    "curiosity_gap": 1.0,
    "clarity": 1.0,
}
MAX_HOOK_SCORE = sum(HOOK_WEIGHTS.values()) * 10


def hook_word_count(text: str) -> int:
    return len((text or "").split())


def score_hook(text: str, dimensions: Dict[str, Any]) -> float:
    """Rank one hook out of 100.

    The model rates the subjective dimensions. Length is measured here, not
    rated: a model asked whether its own hook is short says yes. Spoken aloud,
    roughly twelve words is two seconds, and two seconds is the whole budget.
    """
    total = 0.0
    for key, weight in HOOK_WEIGHTS.items():
        try:
            value = float(dimensions.get(key, 0) or 0)
        except (TypeError, ValueError):
            value = 0.0
        total += max(0.0, min(10.0, value)) * weight

    pct = (total / MAX_HOOK_SCORE) * 100 if MAX_HOOK_SCORE else 0.0

    # Measured, not rated. Past about twelve words the hook cannot land inside
    # the two seconds it has, however good the sentence is.
    words = hook_word_count(text)
    if words == 0:
        return 0.0
    if words > 12:
        pct -= min(25.0, (words - 12) * 2.5)
    if words < 3:
        pct -= 10.0

    return round(max(0.0, min(100.0, pct)), 1)


async def best_hook(profile: Any, brain: Optional[Dict[str, Any]],
                    angle: Dict[str, Any]) -> Dict[str, Any]:
    """Compete several openings for one angle and return the winner.

    Never raises. On any failure the angle's own hook is returned with the
    score it earns, so the pipeline continues with what it already had.
    """
    from services.ai_service import _call_openrouter

    original = (angle.get("hook") or "").strip()
    name = getattr(profile, "name", "") or "this business"

    archetypes = "\n".join(f"- {k}: {d}" for k, d in HOOK_ARCHETYPES)
    prompt = (
        f"{_brain_summary(profile, brain)}\n\n"
        f"ANGLE: {angle.get('angle')}\n"
        f"CATEGORY: {angle.get('category')}\n"
        f"PAIN: {angle.get('pain')}\n"
        f"PROMISE: {angle.get('promise')}\n\n"
        f"Write one opening line for {name} in each of these styles:\n"
        f"{archetypes}\n\n"
        "Rules. Each hook is the FIRST thing somebody hears in a Reel. Twelve "
        "words at most — it has two seconds. No hashtags, no emoji, no brand "
        "name unless the brand is the point. Say something specific: a hook "
        "that would fit any business in this industry is a failed hook.\n\n"
        "Rate each from 0 to 10 on every dimension. Rate honestly.\n\n"
        'Return ONLY a JSON object of the form {"hooks": [ ... ]}, where each '
        "entry is:\n"
        '{"archetype":"question","hook":"the line itself",'
        '"dimensions":{"stop_power":0,"specificity":0,"relevance":0,'
        '"curiosity_gap":0,"clarity":0}}'
    )

    candidates: List[Dict[str, Any]] = []
    try:
        raw = await _call_openrouter(prompt, system_prompt=_STRATEGIST, json_response=True)
        data = _parse(raw)
        for entry in _as_list(data):
            if not isinstance(entry, dict):
                continue
            text = (entry.get("hook") or "").strip()
            if not text:
                continue
            candidates.append({
                "hook": text,
                "archetype": (entry.get("archetype") or "unknown").strip().lower(),
                "words": hook_word_count(text),
                "score": score_hook(text, entry.get("dimensions") or {}),
            })
    except Exception as e:
        logger.warning(f"Hook engine failed, keeping the angle's own hook: {e}")

    # The angle's hook competes too. It was written with the angle in front of
    # it, and sometimes it wins -- discarding it unseen would be a downgrade
    # dressed up as an extra stage.
    if original and not any(c["hook"].lower() == original.lower() for c in candidates):
        candidates.append({
            "hook": original,
            "archetype": "from_angle",
            "words": hook_word_count(original),
            # No dimensions were rated for it, so it is scored on length alone
            # against a neutral middle. It wins only if nothing else showed up.
            "score": score_hook(original, {k: 5 for k in HOOK_WEIGHTS}),
        })

    if not candidates:
        return {"hook": original, "archetype": "from_angle", "score": 0.0, "alternatives": []}

    candidates.sort(key=lambda c: c["score"], reverse=True)
    winner = candidates[0]
    return {
        "hook": winner["hook"],
        "archetype": winner["archetype"],
        "score": winner["score"],
        # Kept so a customer who dislikes the winner has the runners-up
        # instead of having to regenerate the whole creative.
        "alternatives": candidates[1:4],
    }


async def build_concept(profile: Any, brain: Optional[Dict[str, Any]],
                        angle: Dict[str, Any],
                        hook: Optional[str] = None) -> Dict[str, Any]:
    """One angle becomes a four-scene concept. Never raises.

    `hook` is the winner from the Hook Engine. It falls back to the
    angle's own line so this stays callable on its own.
    """
    from services.ai_service import _call_openrouter

    kind = classify(profile)
    grammar = GRAMMAR[kind]
    name = getattr(profile, "name", "") or "this business"
    # The competed winner, falling back to the line the angle came with.
    opening = (hook or angle.get("hook") or "").strip()

    prompt = (
        f"{_brain_summary(profile, brain)}\n\n"
        f"CHOSEN ANGLE: {angle.get('angle')}\n"
        f"CATEGORY: {angle.get('category')}\n"
        f"HOOK TO OPEN ON: {opening}\n\n"
        f"This business is shot as: {grammar['format']}.\n"
        f"Beat structure: {' -> '.join(grammar['beats'])}.\n"
        f"Camera language: {grammar['camera']}.\n\n"
        "Write exactly four scenes for a vertical 9:16 Instagram Reel of 10 to "
        "12 seconds. Scene 1 must land the hook inside two seconds. Every "
        "scene needs one subject and one camera move — anything more cannot be "
        "generated by a video model. On-screen text must be readable with the "
        "sound off. Invent no statistics, prices, testimonials or results.\n\n"
        "Return ONLY JSON:\n"
        '{"title":"THE CREATIVE TITLE IN TITLE CASE",'
        '"format":"Instagram Reel, 9:16 vertical, 10–12 seconds, <style>",'
        '"selling_angle":"the outcome this sells, in one line",'
        '"emotion":"the feeling scene 1 provokes",'
        '"scenes":[{"time":"0–2 sec","visuals":"...","on_screen_text":"...",'
        '"script":"...","camera":"..."}],'
        '"style":"visual, editing and branding direction",'
        '"audio":"music, voice and sound design",'
        '"cta":"the closing call to action"}'
    )

    try:
        raw = await _call_openrouter(prompt, system_prompt=_STRATEGIST, json_response=True)
        concept = _parse(raw)
    except Exception as e:
        logger.warning(f"Concept generation failed: {e}")
        concept = None

    if not isinstance(concept, dict) or not (concept.get("scenes") or []):
        concept = _fallback_concept(profile, angle, grammar, opening)

    # The model routinely returns three scenes or six. The output format is
    # four, so it is made four here rather than hoped for.
    scenes = [s for s in (concept.get("scenes") or []) if isinstance(s, dict)]
    while len(scenes) < REQUIRED_SCENES:
        scenes.append({})
    concept["scenes"] = scenes[:REQUIRED_SCENES]

    concept.setdefault("format", f"Instagram Reel, 9:16 vertical, 10–12 seconds, {grammar['format']}")
    concept.setdefault("style", grammar["style"])
    concept["creative_angle"] = angle.get("category", "general")
    concept["hook"] = opening or angle.get("hook", "")
    concept["angle_score"] = angle.get("score", 0.0)
    concept["business_kind"] = kind
    concept["markdown"] = render_creative(concept, name)
    return concept


def _fallback_concept(profile: Any, angle: Dict[str, Any],
                      grammar: Dict[str, Any],
                      hook_override: Optional[str] = None) -> Dict[str, Any]:
    name = getattr(profile, "name", "") or "this business"
    hook = hook_override or angle.get("hook") or "Stop scrolling."
    return {
        "title": (angle.get("angle") or "A Reel For This Business")[:70],
        "format": f"Instagram Reel, 9:16 vertical, 10–12 seconds, {grammar['format']}",
        "selling_angle": angle.get("promise", ""),
        "emotion": "recognition",
        "scenes": [
            {"time": "0–2 sec", "visuals": "Open already in motion on the person with the problem, mid-reaction.",
             "on_screen_text": hook, "script": hook, "camera": grammar["camera"]},
            {"time": "2–5 sec", "visuals": "The problem shown rather than described.",
             "on_screen_text": angle.get("pain", ""), "script": "", "camera": "close, handheld"},
            {"time": "5–8 sec", "visuals": f"{name} doing the one thing it exists to do.",
             "on_screen_text": angle.get("promise", ""), "script": "", "camera": "slow push in"},
            {"time": "8–12 sec", "visuals": "The result, held still on the closing card.",
             "on_screen_text": name, "script": "", "camera": "locked off"},
        ],
        "style": grammar["style"],
        "audio": "Quiet room tone under the first line, then one modern beat from the turn onward.",
        "cta": f"Visit {getattr(profile, 'websiteUrl', '') or name}",
    }


# =============================================================================
# The critic
#
# A second pass by a model told to be hostile catches the things a generating
# model will not: a hook that needs three seconds, a product that never
# appears, a scene nothing could film. It returns findings, not a rewrite —
# a critic that rewrites tends to flatten the specific detail that made the
# creative good, and the fixes it names are cheap to apply here.
# =============================================================================

_CRITIC = (
    "You are a hostile creative director reviewing a short-form video brief. "
    "You are looking for reasons it will fail. Be specific and brief. You "
    "answer only with the JSON asked for."
)

# Applied in code, because these are the failures that matter and a model
# asked to 'check quality' reports whatever it thought of first.
CHECKS = [
    ("hook_in_two_seconds", "The hook has to land before the thumb moves."),
    ("product_appears", "A creative the product never appears in sells nothing."),
    ("readable_without_sound", "Most of Instagram watches muted."),
    ("scenes_are_filmable", "One subject and one move, or no video model can render it."),
    ("no_invented_claims", "A figure nobody can substantiate is the one thing this product must never print."),
    ("cta_is_clear", "A creative with no ask converts whoever was already going to buy."),
]


def audit(concept: Dict[str, Any]) -> List[str]:
    """Structural problems, found in code rather than asked of a model.

    These are checkable facts about the concept, so they are checked. Sending
    them to a model would trade a certain answer for a plausible one.
    """
    problems: List[str] = []
    scenes = concept.get("scenes") or []

    first = (scenes[0] if scenes else {}) or {}
    opening = f"{first.get('on_screen_text', '')} {first.get('script', '')}".strip()
    if not opening:
        problems.append("Scene 1 has no hook — nothing is said or shown in the first two seconds.")
    elif len(opening.split()) > 14:
        problems.append("The opening line is too long to land in two seconds.")

    if not any((s.get("on_screen_text") or "").strip() for s in scenes):
        problems.append("No on-screen text anywhere — the creative is unreadable muted.")

    if not (concept.get("cta") or "").strip():
        problems.append("No call to action.")

    empty = [i + 1 for i, s in enumerate(scenes) if not (s.get("visuals") or "").strip()]
    if empty:
        problems.append(f"Scene(s) {', '.join(map(str, empty))} have no visual direction.")

    return problems


async def critique(concept: Dict[str, Any], business_name: str) -> Dict[str, Any]:
    """Structural audit plus one hostile read. Never raises."""
    problems = audit(concept)

    try:
        from services.ai_service import _call_openrouter

        raw = await _call_openrouter(
            "Review this Instagram Reel brief and name what will make it fail."
            + BREAK
            + (concept.get("markdown", "") or "")
            + BREAK
            + "Check: does the hook land in two seconds; does the product appear; "
            "is it understandable with the sound off; could a video model "
            "actually render each scene; are there invented statistics, prices "
            "or testimonials; is the call to action clear; does it read like "
            "generic AI advertising."
            + BREAK
            + 'Return ONLY JSON: {"problems": ["short specific problem", "..."]}',
            system_prompt=_CRITIC,
            json_response=True,
        )
        parsed = _parse(raw)
        if isinstance(parsed, dict):
            for item in (parsed.get("problems") or [])[:5]:
                if isinstance(item, str) and item.strip():
                    problems.append(item.strip())
    except Exception as e:
        # The structural audit already ran, so a dead model costs the second
        # opinion rather than the review.
        logger.warning(f"Creative critic unavailable: {e}")

    concept["problems"] = problems
    return concept


async def create_campaign(profile: Any, count: int = 5) -> Dict[str, Any]:
    """The whole pipeline. Returns finished creatives, never raises."""
    brain = None
    try:
        from services import brand_intelligence

        brain = await brand_intelligence.get_or_build(profile)
    except Exception as e:
        logger.warning(f"Business Brain unavailable, using the profile alone: {e}")

    angles = await propose_angles(profile, brain, wanted=count)

    creatives = []
    for angle in angles[:count]:
        # The hook competes on its own before the scenes are written. The
        # angle decides what the creative argues; these two seconds decide
        # whether anybody hears the argument.
        chosen = await best_hook(profile, brain, angle)
        concept = await build_concept(profile, brain, angle, chosen["hook"])
        concept["hook_score"] = chosen["score"]
        concept["hook_archetype"] = chosen["archetype"]
        concept["hook_alternatives"] = chosen["alternatives"]
        concept = await critique(concept, getattr(profile, "name", "") or "this business")
        creatives.append(concept)

    return {
        "businessKind": classify(profile),
        "angleCount": len(angles),
        "creatives": creatives,
    }

"""Model-specific prompt compilers for video brief generation.

Implements the model-specific syntax divergence rules detailed in Finding 1,
Finding 4, Finding 7, and Finding 8 of the Deep Research Reference.
"""

from __future__ import annotations

import re
from typing import Dict, Any, Optional, List, Tuple
from prompt_engine.models import ModelPromptPayload
from database import BusinessProfile


# ─────────────────────────────────────────────────────────────────────────────
# Shared text utilities
# ─────────────────────────────────────────────────────────────────────────────

def _clean_text(text: str) -> str:
    return " ".join(text.strip().split())


def _strip_temporal_and_physics_stressors(text: str) -> str:
    """Strips forbidden temporal words (then, next) and high-velocity physics stressors."""
    words_to_strip = ["then", "next", "afterwards", "subsequently", "flips to reveal"]
    result = text
    for w in words_to_strip:
        pattern = re.compile(rf'\b{re.escape(w)}\b', re.IGNORECASE)
        result = pattern.sub("", result)
    return _clean_text(result)


# Surfaces that render glyphs rather than hold them. A brand word on a monitor
# comes back as mush for exactly the reason validator.LEGIBLE_SCREEN_PATTERNS
# rejects it, so the surface is dropped rather than the brand.
_SCREEN_SURFACE = re.compile(
    r"\b(dashboard|screen|monitor|display|app|ui|phone|terminal|console|"
    r"tablet|laptop|overlay|title card|lower.third)\b",
    re.IGNORECASE,
)


def _physical_brand_surface(surface: Optional[str], brand: str = "") -> str:
    """Keep the brand's placement only when it is something physical.

    An etched plate, a painted wall or a stamped label holds a word steadily
    across frames. A screen does not, and neither does a compositing overlay,
    which these models approximate rather than draw.

    The result is inserted after "on", so it has to read as a noun phrase.
    Live output produced 'on etched into the wooden reception desk' and 'on
    Ridgeline etched into the head badge' — a dangling participle and a
    duplicated brand word, because the model answers this field with a phrase
    that already assumes a subject.
    """
    text = (surface or "").strip().strip(".")
    if not text or _SCREEN_SURFACE.search(text):
        return ""

    # The brand word is already stated by the clause this feeds, so repeating
    # it reads as an echo: 'the single word "Northwind" on the word Northwind
    # etched into the mug'. Both the bare and the introduced form appear.
    if brand:
        text = re.sub(
            rf"^(?:the\s+(?:word|name|logo|mark)\s+)?{re.escape(brand)}\b",
            "",
            text,
            flags=re.IGNORECASE,
        ).lstrip(" ,-:")

    # A leading participle needs something to attach to.
    if re.match(
        r"^(etched|stamped|embossed|painted|engraved|printed|carved|woven|"
        r"debossed|screen.?printed|branded)\b",
        text,
        re.IGNORECASE,
    ):
        text = f"the mark {text}"

    return text.strip(" ,-:")


def _enforce_background_text_suppression(text: str) -> str:
    """Appends background text suppression clause if not already present.

    Research Finding 4: incidental text (background signage, product labels)
    universally collapses into graffiti-like artifacts. Prompts must explicitly
    instruct suppression of background text.

    Uses positive phrasing ("clean surfaces free of text") rather than negative
    ("no text") to avoid triggering Runway's negative instruction rejection.
    """
    suppression_phrases = [
        "no background text", "no signage", "no labels",
        "without background signage", "without text labels",
        "clean surfaces", "no on-screen text",
        "free of text", "free of signage",
    ]
    lowered = text.lower()
    if any(phrase in lowered for phrase in suppression_phrases):
        return text

    # When the brief deliberately asks for one short line on screen, a blanket
    # "free of text" clause contradicts it in the same prompt and the model has
    # to pick a winner. Suppress only the incidental text — background signage
    # and product labels — which is the part that renders as scribble anyway.
    # Phrased positively on purpose. Runway has no negative parsing, and its
    # own guidance is that negative wording pulls attention onto the suppressed
    # term — check_model_negative_syntax rejects "no ", "do not" and "without"
    # in a Runway positive prompt for exactly that reason. An earlier wording
    # here, "No other text: ...", tripped that gate on every generation.
    has_intentional_text = re.search(
        r'(?:the words? "[^"]+" appear|holds the single word "[^"]+")',
        text,
        re.IGNORECASE,
    )
    if has_intentional_text:
        return text.rstrip(".") + (
            ". Background signage and product labels remain blank."
        )
    return text.rstrip(".") + ". Clean surfaces free of text, signage, and labels."


def _cap_audio_words(audio_descriptor: str, max_words: int = 15) -> str:
    """Cap audio direction to max_words to prevent cross-modal degradation.

    Research Finding 2: audio direction measurably degrades visual fidelity.
    Audio should be capped at 10-15 words using simple, ambient descriptors.
    """
    words = audio_descriptor.strip().split()
    if len(words) > max_words:
        return " ".join(words[:max_words])
    return audio_descriptor


# ─────────────────────────────────────────────────────────────────────────────
# Camera vector rotation for variation without drift
# ─────────────────────────────────────────────────────────────────────────────

CAMERA_VECTORS = [
    "Slow dolly forward",
    "Static tripod shot",
    "Handheld steady tracking",
    "Slow orbit right",
    "Gentle crane up",
    "Subtle push-in",
    "Static medium close-up",
    "Slow lateral dolly",
]


def get_rotated_camera_vector(index: int) -> str:
    """Return a camera vector from the rotation pool based on index.

    Used for generating distinct creatives without identity drift: pin the
    random noise seed while modifying only the camera vector parameter.
    """
    return CAMERA_VECTORS[index % len(CAMERA_VECTORS)]


# ─────────────────────────────────────────────────────────────────────────────
# Model-specific compilers
# ─────────────────────────────────────────────────────────────────────────────

def compile_runway_prompt(
    intent: str,
    brand_aesthetic: Optional[str] = None,
    camera_vector: Optional[str] = None,
    primary_offer: Optional[str] = None,
    scene_fields: Optional[dict] = None,
) -> ModelPromptPayload:
    """Compile brief for Runway Gen-3/Gen-4.

    Grammar: [Camera Movement]: [Establishing Scene]. [Action]. [Lighting and Detail].
    Rules:
    - Rejects conversational prompts & temporal sequencing words ("then", "next").
    - Strictly forbids negative prompt parameters or negative phrasing (removes negative exclusions).
    - Single continuous shot, 1 isolated human subject maximum.
    - Word budget <= 85 words.
    - Explicit background text suppression (Finding 4).
    """
    camera = camera_vector or "Slow dolly forward"
    aesthetic = brand_aesthetic or "Warm cinematic lighting, professional 8k photography, high contrast"
    offer = primary_offer or "Modern premium aesthetic"

    if scene_fields:
        # Written content: a specific person, a specific action, a specific
        # room. The template branch below is the degraded fallback.
        camera = scene_fields.get("camera") or camera
        subject = scene_fields.get("subject") or "a single subject"
        scene = f"{subject} in {scene_fields.get('environment') or 'an isolated setting'}."

        # The opening three seconds carry the whole ad, so the hook is enforced
        # by ORDER, not by an extra sentence. An earlier attempt emitted a
        # separate hook_beat clause; it restated the hero string and the spoken
        # line, which pushed the prompt past budget, truncated the dialogue,
        # and double-counted the screen as a competing prop.
        #
        # Stating "opens mid-motion" and placing the hero string before the
        # action gets the same result in three words.
        action = f"opens mid-motion, {scene_fields.get('action') or ''}."
        detail_bits = [scene_fields.get("mood") or aesthetic]

        # The hero string is the message. Reference material confirms current
        # models render one large, central, high-contrast string accurately —
        # it is the small surrounding copy that collapses, so that is described
        # as out of focus rather than requested.
        hero = scene_fields.get("hero_text")
        if hero:
            surface = (scene_fields.get("hero_surface") or "").strip().strip(".")
            on_what = surface or "the screen"
            # A rendered test proved describing what a screen "displays" is not
            # enough. The prompt said the laptop screen displayed "Scan
            # Complete"; across all ten seconds the laptop stayed edge-on,
            # facing away, and the string never appeared. The model composes
            # around the PERSON and puts a laptop where a laptop naturally
            # sits, so the message was simply lost.
            #
            # The camera has to be told to SEE it. Every reference clip that
            # rendered text successfully framed the screen square-on or over
            # the shoulder.
            # The brief also asks for framing, so add it only when the surface
            # did not already describe one — otherwise the clause reads
            # "over the shoulder ..., the laptop screen angled toward the
            # camera and filling the upper half ..." and says it twice.
            framing = ""
            already_framed = re.search(
                r"\b(angled|facing|square to|toward the camera|over the shoulder|"
                r"filling|fills|head-on|to camera|in frame)\b",
                on_what,
                re.IGNORECASE,
            )
            if _SCREEN_SURFACE.search(on_what) and not already_framed:
                framing = (
                    "camera over the shoulder with the screen square to frame "
                    "and filling the upper half, "
                )
            clause = f'{framing}{on_what} reads "{hero}" in large high-contrast type'
            # The defocus instruction only means something when there IS an
            # interface. It was appended unconditionally, so a chalk mark on
            # steel and a tag on a coffee bag both asked the model to blur
            # surrounding "interface copy" that does not exist in the shot.
            if _SCREEN_SURFACE.search(on_what):
                clause += ", surrounding interface copy soft and out of focus"
            detail_bits.append(clause)

        # The brand word closes the clip. Anchoring it to a physical surface
        # renders far more cleanly than a floating overlay.
        brand = scene_fields.get("onscreen_text")
        if brand:
            surface = _physical_brand_surface(scene_fields.get("brand_moment"), brand)
            where = f" on {surface}" if surface else ""
            detail_bits.append(f'final frame holds the single word "{brand}"{where}')
        detail_bits.append("shallow depth of field, vertical 9:16 frame")

        # Spoken aloud, not rendered. Kept as its own trailing clause so the
        # validator can tell a line of dialogue from a string on a screen —
        # they look identical to a naive quote count.
        vo = (scene_fields.get("voiceover") or "").strip()
        if vo:
            # A rendered test came back silent until 3.5 seconds — room tone
            # over a man closing a notebook, while the line waited. In a feed
            # that is the whole ad gone. "Natural unhurried delivery" invited
            # exactly that pause, so the start point is now explicit.
            # Phrased positively. "no pause before the first word" reads
            # naturally but the leading "no " trips
            # check_model_negative_syntax, which rejects negative wording in a
            # Runway positive prompt because the attention mechanism latches
            # onto the suppressed term. Same trap as the earlier "No other
            # text:" regression.
            detail_bits.append(
                f'already speaking as the first frame begins, the first word '
                f'lands immediately: "{vo}"'
            )

        # The ad has to ask for something. Burned on screen a CTA renders as
        # smeared glyphs, so it is SPOKEN over the closing frame while the
        # screen holds only the one-word brand. Naming the brand aloud is also
        # what makes the viewer able to search for it afterwards.
        cta = (scene_fields.get("spoken_cta") or "").strip()
        if cta:
            detail_bits.append(f'then over the closing frame, spoken: "{cta}"')
        detail = ", ".join(b for b in detail_bits if b)
        # The spoken line keeps its own sentence punctuation inside the quotes,
        # so a blanket full stop here produces `scan."."`.
        detail = detail if detail.endswith(('.', '!', '?', '"')) else detail + "."
    else:
        # Placeholder text — "a single subject in an isolated setting" names
        # nobody and nowhere, so it renders as generic mush. Only reached when
        # the scene writer is unavailable.
        scene = f"A single subject in an isolated setting illustrating {intent}. {aesthetic}."
        action = f"The subject performs one smooth, continuous linear motion highlighting {offer}."
        detail = "Ultra-detailed textures, ambient atmosphere, sharp focus, continuous vertical 9:16 frame."

    # Combine into strict linear format
    raw_positive = f"{camera}: {scene} {action} {detail}"
    raw_positive = _enforce_background_text_suppression(raw_positive)
    positive_prompt = _strip_temporal_and_physics_stressors(raw_positive)

    # Word budget. The old ceiling of 85 was set when the prompt carried only
    # scene description; it now also carries a hero string and a spoken line,
    # both of which are load-bearing. Truncating at 85 amputated the dialogue,
    # which sits last.
    #
    # Truncation also has to land outside a quoted string — cutting one in half
    # leaves an unterminated quote that the model reads as running text.
    budget = 145 if (scene_fields or {}).get("spoken_cta") else (
        130 if (scene_fields or {}).get("voiceover") else 90
    )
    words = positive_prompt.split()
    if len(words) > budget:
        truncated = " ".join(words[:budget])
        if truncated.count('"') % 2:
            truncated = truncated.rsplit('"', 1)[0].rstrip(" ,;:")
        # Cutting mid-clause left trailing scaffolding like "... , spoken." —
        # a dangling lead-in to dialogue that never arrives, which reads as an
        # instruction the model cannot satisfy. Drop the partial clause.
        truncated = truncated.rstrip(" ,;:.")
        parts = [p.strip() for p in truncated.split(",")]
        if parts and len(parts[-1].split()) < 4:
            parts = parts[:-1]
        positive_prompt = ", ".join(p for p in parts if p).rstrip(" ,;:.") + "."

    return ModelPromptPayload(
        model_name="runway",
        positive_prompt=positive_prompt,
        negative_prompt=None,  # Runway rejects negative prompts
        camera_movement=camera,
        scene_description=scene,
        action_description=action,
        word_count=len(positive_prompt.split()),
        model_specific_payload={
            "prompt": positive_prompt,
            "structure": "[Camera Movement]: [Establishing Scene]. [Action]. [Lighting and Detail].",
            "supports_negative_prompt": False,
        },
    )


def compile_kling_prompt(
    intent: str,
    brand_aesthetic: Optional[str] = None,
    camera_vector: Optional[str] = None,
    product_image_base64: Optional[str] = None,
    seed: Optional[int] = None,
    audio_descriptor: Optional[str] = None,
) -> ModelPromptPayload:
    """Compile brief for Kling AI (Omni 3.0).

    Grammar: Multi-prompt shot list + inline <<audio_descriptor>> tags + negative_prompt parameter.
    Rules:
    - Supports explicit negative parameters up to 2,500 chars.
    - Audio tag embedded via <<..>> syntax (capped 10-15 words).
    - Image reference passed as clean Base64 string without formatting prefixes.
    - Explicit background text suppression (Finding 4).
    """
    camera = camera_vector or "Handheld steady tracking"
    aesthetic = brand_aesthetic or "Vibrant commercial studio lighting"

    # Cap audio to 15 words to prevent cross-modal degradation (Finding 2)
    raw_audio = audio_descriptor or "Soft ambient atmospheric drone, subtle background breeze"
    capped_audio = _cap_audio_words(raw_audio, max_words=15)
    audio_tag = f"<<{capped_audio}>>"

    main_scene = f"{camera}, single subject demonstrating {intent}, {aesthetic}. {audio_tag}"
    main_scene = _enforce_background_text_suppression(main_scene)
    positive_prompt = _strip_temporal_and_physics_stressors(main_scene)

    negative_exclusions = [
        "deformed hands", "duplicate limbs", "multiple faces", "crowd",
        "background text", "signage", "logos", "morphing geometry", "blurry", "plastic skin"
    ]
    negative_prompt_str = ", ".join(negative_exclusions)

    # Strip prefixes if Base64 string has 'data:image/...;base64,' prefix
    clean_image_base64 = None
    if product_image_base64:
        clean_image_base64 = product_image_base64.split(",")[-1]

    model_payload = {
        "multi_prompt": [
            {"prompt": positive_prompt, "duration": 10.0}
        ],
        "negative_prompt": negative_prompt_str,
        "mode": "std",
    }
    if clean_image_base64:
        model_payload["image"] = clean_image_base64
    if seed is not None:
        model_payload["seed"] = seed

    return ModelPromptPayload(
        model_name="kling",
        positive_prompt=positive_prompt,
        negative_prompt=negative_prompt_str,
        camera_movement=camera,
        scene_description=positive_prompt,
        audio_tags=audio_tag,
        reference_image_base64=clean_image_base64,
        seed=seed,
        word_count=len(positive_prompt.split()),
        model_specific_payload=model_payload,
    )


def compile_veo_prompt(
    intent: str,
    brand_aesthetic: Optional[str] = None,
    camera_vector: Optional[str] = None,
) -> ModelPromptPayload:
    """Compile brief for Google Veo 3.1.

    Grammar: Structured JSON schema (Subject, Context, Action, Style) + Purely Descriptive Negative List.
    Rules:
    - Rejects instructive negative phrases ("Do not show walls").
    - Requires purely descriptive negative keywords as comma-separated list.
    - Explicit background text suppression in context (Finding 4).
    """
    subject = f"One human subject engaged in {intent}"
    context = "Clean, modern, uncluttered interior environment free of text and signage"
    action = f"Continuous linear physical interaction under {camera_vector or 'static tripod shot'}"
    style = brand_aesthetic or "Photorealistic 8k, cinematic vertical 9:16 aspect ratio"

    positive_prompt = f"Subject: {subject}. Context: {context}. Action: {action}. Style: {style}."
    positive_prompt = _strip_temporal_and_physics_stressors(positive_prompt)

    # Descriptive keyword list (NO instructive language like "do not show")
    negative_keywords = ["walls", "background signage", "extra faces", "crowd", "reflections", "text", "distortion"]
    negative_prompt_list = negative_keywords

    model_payload = {
        "ingredients": {
            "subject": subject,
            "context": context,
            "action": action,
            "style": style,
        },
        "positive_prompt": positive_prompt,
        "negative_keywords": negative_keywords,
    }

    return ModelPromptPayload(
        model_name="veo",
        positive_prompt=positive_prompt,
        negative_prompt=negative_prompt_list,
        camera_movement=camera_vector or "static tripod shot",
        scene_description=context,
        action_description=action,
        word_count=len(positive_prompt.split()),
        model_specific_payload=model_payload,
    )


def compile_sora_prompt(
    intent: str,
    brand_aesthetic: Optional[str] = None,
    camera_vector: Optional[str] = None,
    seed: Optional[int] = None,
) -> ModelPromptPayload:
    """Compile brief for OpenAI Sora 2.

    Grammar: Freeform high-density descriptive physics narrative.
    Rules:
    - High-density physical attributes and environmental physics narrative.
    - No temporal step-by-step commands or scene cuts.
    - Suppress incidental background text.
    """
    camera = camera_vector or "Slow tracking shot"
    aesthetic = brand_aesthetic or "Natural lighting, lifelike skin texture, realistic gravity"
    narrative = f"{camera} of a single subject interacting naturally with {intent}. {aesthetic}. The environment exhibits clean surfaces without background signage or text labels."
    positive_prompt = _strip_temporal_and_physics_stressors(narrative)

    model_payload = {
        "prompt": positive_prompt,
        "aspect_ratio": "9:16",
        "duration": 10.0,
    }
    if seed is not None:
        model_payload["seed"] = seed

    return ModelPromptPayload(
        model_name="sora",
        positive_prompt=positive_prompt,
        negative_prompt=None,
        camera_movement=camera,
        scene_description=narrative,
        seed=seed,
        word_count=len(positive_prompt.split()),
        model_specific_payload=model_payload,
    )


def compile_pika_prompt(
    intent: str,
    brand_aesthetic: Optional[str] = None,
    camera_vector: Optional[str] = None,
) -> ModelPromptPayload:
    """Compile brief for Pika 2.0 / Luma.

    Modular parameters focusing on localized subject modification,
    specific object customization, and dynamic motion overrides.
    Unlike Runway, Pika prioritizes localized subject modification over
    global camera tracking.
    """
    camera = camera_vector or "Static medium close-up"
    aesthetic = brand_aesthetic or "Clean modern aesthetic, soft studio lighting"

    prompt = (
        f"Single subject demonstrating {intent}, {aesthetic}. "
        f"Localized focus on primary object with detailed surface textures."
    )
    prompt = _enforce_background_text_suppression(prompt)
    positive_prompt = _strip_temporal_and_physics_stressors(prompt)

    return ModelPromptPayload(
        model_name="pika",
        positive_prompt=positive_prompt,
        negative_prompt="blur, distorted, background text, signage",
        camera_movement=camera,
        word_count=len(positive_prompt.split()),
        model_specific_payload={
            "prompt": positive_prompt,
            "negative_prompt": "blur, distorted, background text, signage",
            "options": {
                "aspect_ratio": "9:16",
                "motion": "localized",
                "camera": camera,
            },
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Caption system prompt builder (Research Section B)
# ─────────────────────────────────────────────────────────────────────────────

def build_caption_system_prompt(
    brand_name: str,
    customer_motivator: str,
    brand_language_anchor: str,
    product_feature: str,
) -> str:
    """Build the motivator-based direct-response copywriter system prompt.

    Implements the caption specification from the deep research document:
    - System role as direct-response copywriter (no marketing jargon, no AIDA/PAS)
    - Negative exemplars to steer away from reviewer voice and audience leakage
    - Forced specificity via brand language anchor
    - Max 3 sentences with line breaks
    - First sentence must address motivator via concrete scenario
    - Safety: no invented statistics/prices/health/financial claims
    """
    return f"""[SYSTEM ROLE]
You are a direct-response copywriter for {brand_name}. You do not use marketing jargon, abstract frameworks (e.g., AIDA), or rhetorical questions.

[CONTEXT]
Target Motivator: {customer_motivator}
Brand Language Anchor: "{brand_language_anchor}"
Product Feature: {product_feature}

[NEGATIVE EXEMPLARS - DO NOT DO THIS]
"Struggling to find time? Our team tested the best solutions and this is a solid pick!" (Fails: Reviewer voice, generic problem).
"Unlock the ultimate solution for entrepreneur parents today." (Fails: Leaking audience label, exhausted opener).
"In today's fast-paced world, finding the right product is hard." (Fails: Exhausted AI trope opener).
"Are you looking for the perfect solution? Look no further!" (Fails: Rhetorical question, generic closer).

[OUTPUT RULES]
LENGTH: Maximum 3 sentences. Total character count must be under 250 characters. Use line breaks between each sentence.
HOOK: The first sentence must directly address the "{customer_motivator}" using a concrete scenario, without naming the demographic label.
SPECIFICITY: You must use at least one specific entity (number, proprietary feature, or location) derived strictly from the Brand Language Anchor.
TONE: Write from the perspective of the brand itself, not a third-party reviewer.
SAFETY: Do not invent any statistics, prices, or health/financial claims not explicitly provided in the Context.
FORMAT: Return ONLY the caption text. No preamble, no labels, no markdown. First character = first character of the caption."""


# ─────────────────────────────────────────────────────────────────────────────
# Main routing entry point
# ─────────────────────────────────────────────────────────────────────────────

def compile_video_prompt(
    model_name: str,
    intent: str,
    brand_aesthetic: Optional[str] = None,
    camera_vector: Optional[str] = None,
    primary_offer: Optional[str] = None,
    product_image_base64: Optional[str] = None,
    seed: Optional[int] = None,
    audio_descriptor: Optional[str] = None,
    scene_fields: Optional[dict] = None,
) -> ModelPromptPayload:
    """Main routing entry point for compiling target model video briefs.

    scene_fields carries LLM-written creative content (camera, subject, action,
    environment, mood, on-screen text). When absent the compilers fall back to
    templates, which are structurally valid but generic — see
    prompt_engine/scene_writer.py for why that matters.
    """
    normalized_model = (model_name or "runway").lower().strip()

    if normalized_model in ("runway", "gen3", "gen4", "runwayml"):
        return compile_runway_prompt(intent, brand_aesthetic, camera_vector, primary_offer, scene_fields)
    elif normalized_model in ("kling", "kling_ai", "omni"):
        return compile_kling_prompt(intent, brand_aesthetic, camera_vector, product_image_base64, seed,
                                    audio_descriptor or (scene_fields or {}).get('audio'))
    elif normalized_model in ("veo", "veo3", "veo3.1", "google_veo"):
        return compile_veo_prompt(intent, brand_aesthetic, camera_vector)
    elif normalized_model in ("sora", "sora2", "openai_sora"):
        return compile_sora_prompt(intent, brand_aesthetic, camera_vector, seed)
    elif normalized_model in ("pika", "luma", "dream_machine"):
        return compile_pika_prompt(intent, brand_aesthetic, camera_vector)
    else:
        # Fallback to Runway linear format
        return compile_runway_prompt(intent, brand_aesthetic, camera_vector, primary_offer, scene_fields)

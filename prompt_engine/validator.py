"""Validator utilities for prompt engine.

Provides deterministic validation gates for AI video briefs and social captions,
implementing the automated quality gates specified in Section C (Automated Checks)
and Section B of the Deep Research Reference.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import List, Dict, Any, Optional, Set, Tuple
from prompt_engine.models import PromptValidationResult
from database import BusinessProfile

CAPTION_MAX_LENGTH = 300
CAPTION_MAX_SENTENCES = 3
# 85 was set when a prompt carried only scene description. It now also carries
# a hero string and a verbatim spoken line, both load-bearing, so the old
# ceiling rejected every prompt that included dialogue. Kept as a real ceiling
# rather than removed: past ~130 words these models start dropping elements
# silently, which is worse than a hard failure.
PROMPT_MAX_WORDS = 130
PROMPT_MAX_ENTITIES = 10
AUDIO_MAX_WORDS = 15

REVIEWER_VOICE_PATTERNS = [
    r"\bwe tested\b",
    r"\bour team\b",
    r"\bour pick\b",
    r"\bhighly recommend\b",
    r"\bI've been using\b",
    r"\bmy honest opinion\b",
]

EXHAUSTED_OPENER_PATTERNS = [
    r"in today'?s fast-paced world",
    r"unlock the power of",
    r"are you looking for",
    r"elevate your",
    r"game-changer",
    r"look no further",
    r"welcome to the future of",
]

TEMPORAL_SEQUENCE_WORDS = {"then", "next", "afterwards", "subsequently", "flips"}
PHYSICS_STRESSORS = {"splashes", "pour", "explode", "burst", "high-velocity", "bouncing"}

# Health and financial claim patterns (FTC Section 5)
HEALTH_CLAIM_PATTERNS = [
    r"\bcures?\b", r"\bheals?\b", r"\btreats?\b", r"\bprevents?\b",
    r"\beliminates?\b", r"\bclinically proven\b", r"\bmedically proven\b",
    r"\bfda approved\b", r"\bdoctor recommended\b",
]
FINANCIAL_CLAIM_PATTERNS = [
    r"\bguaranteed returns?\b", r"\bearn \$\d+\b", r"\bmake money\b",
    r"\bpassive income\b", r"\bfinancial freedom\b", r"\brisk.?free\b",
    r"\bget rich\b", r"\b\d+x returns?\b",
]

# Subject count patterns (Finding 3: Inverse Scaling Law of Crowd Dynamics)
MULTI_SUBJECT_PATTERNS = [
    r"\bcrowd\b", r"\bgroup of\b", r"\bmultiple people\b",
    r"\bmultiple faces\b", r"\bmany people\b", r"\bseveral people\b",
    r"\bteam of\b", r"\bfamily\b", r"\bcouple\b", r"\bfriends\b",
    r"\bbackground extras\b",
]

# Props that each pull the model's attention. Finding 3 is about fidelity being
# divided, and that happens with objects just as much as with extra faces — a
# phone AND a laptop AND server racks AND an LED strip is four things competing
# even though only one human is named.
COMPETING_PROP_PATTERNS = [
    r"\bphone\b", r"\blaptop\b", r"\bmonitor\b", r"\bscreen\b", r"\btablet\b",
    r"\bterminal\b", r"\bdashboard\b", r"\bkeyboard\b", r"\bserver rack\b",
    r"\bled\b", r"\bheadphones\b", r"\bcoffee\b", r"\bnotebook\b", r"\bmug\b",
]
MAX_COMPETING_PROPS = 3

# Background text request patterns (Finding 4)
BACKGROUND_TEXT_REQUEST_PATTERNS = [
    r"\bshow text\b", r"\bdisplay text\b", r"\btext overlay\b",
    r"\bon-screen text\b", r"\bshow signage\b", r"\bdisplay signage\b",
    r"\bbillboard\b", r"\bbanner text\b", r"\bproduct label\b",
]

# The real failure mode is not the word "text" — it is describing legible
# screen content without ever using that word. These catch the shape of it:
# a surface that renders glyphs, plus content described as readable.
# What actually fails is BULK legible copy, not a hero string. Reference
# footage from current models shows a large central string rendering accurately
# — a red alert banner reading "RSA-2048 Encryption Vulnerable", a chat box
# reading "why is my circuit failing?", a notification card reading "$27 Pro
# Tier Sale". An earlier version of this list rejected all of those, which
# stripped the product out of every ad and left abstract mood pieces.
#
# So these patterns now target only the things that still collapse: many small
# labels, and body copy asked for as readable.
LEGIBLE_SCREEN_PATTERNS = [
    # Bulk running copy, as opposed to one headline string.
    (r"\b(tailing|scrolling|streaming)\b[^.]{0,30}\b(logs?|output|code|json)\b",
     'streaming log or code output, which renders as scribble'),
    (r"\b(paragraphs?|body copy|full sentences?|blocks? of text|walls? of text)\b",
     'running body copy'),
    (r"\b(legible|readable|crisp|sharp|detailed)\b[^.]{0,25}\b(menus?|labels?|captions?|sidebar|toolbar|spreadsheet|table)\b",
     'small interface labels asked for as legible'),
    (r"\b(rows? of|columns? of|list of)\b[^.]{0,20}\b(data|numbers|entries|records|logs?)\b",
     'tabular detail, which the model fills with noise'),
]

# More than one competing string and both degrade. Counted separately from the
# patterns above because the failure is arithmetic, not phrasing.
MAX_HERO_STRINGS = 2

# The model cannot resolve a named typeface or a brand colour name to anything,
# so these silently waste prompt budget and displace real description.
UNRENDERABLE_SPEC_PATTERNS = [
    (r"#[0-9a-fA-F]{6}\b", 'a hex colour'),
    (r"\b(space grotesk|helvetica|inter|roboto|montserrat|futura|gotham|arial|poppins)\b",
     'a named typeface'),
    (r"\bin [A-Z][a-z]+ [A-Z][a-z]+ (?:font|type|typeface)\b", 'a named typeface'),
]

# Negative payloads embedded in the positive prompt. Finding 8: this belongs in
# a separate field (Kling, Veo) or nowhere at all (Runway). Inline it is at best
# ignored and at worst focuses attention on the very thing being suppressed.
INLINE_NEGATIVE_PATTERNS = [
    r"\s-v\s", r"\s--no\s", r"\bnegative prompt:", r"\bnegative:",
]

# Clichés the brief bans but nothing enforced.
BANNED_VISUAL_CLICHES = [
    "bloomberg-terminal", "bloomberg terminal", "futuristic holographic",
    "neon-lit trading floor", "dynamic and vibrant", "flying data particles",
    "glowing orbs", "neon cityscape", "fish-eye", "holographic dashboard",
]


def _word_count(text: str) -> int:
    return len(text.split())


def _extract_numbers_and_claims(text: str) -> List[str]:
    """Extract quantitative claims, health outcomes, and financial promises.

    Enhanced per research Section B / Section C to catch not only numeric
    patterns but also health/financial language that must be substantiated.
    """
    claims = []

    # Quantitative patterns (percentages, dollar figures, multipliers)
    numeric_pattern = r"(\d+%|\$\d+[\d,]*|\b\d+\s*x\b|\b\d+\s*percent\b)"
    claims.extend(re.findall(numeric_pattern, text, flags=re.IGNORECASE))

    # Health outcome claims
    lowered = text.lower()
    for pattern in HEALTH_CLAIM_PATTERNS:
        matches = re.findall(pattern, lowered)
        claims.extend(matches)

    # Financial promise claims
    for pattern in FINANCIAL_CLAIM_PATTERNS:
        matches = re.findall(pattern, lowered)
        claims.extend(matches)

    return claims


def _compute_jaccard_similarity(text1: str, text2: str) -> float:
    """Compute word-level Jaccard similarity between two text strings."""
    w1 = set(re.findall(r"\w+", text1.lower()))
    w2 = set(re.findall(r"\w+", text2.lower()))
    if not w1 or not w2:
        return 0.0
    intersection = w1.intersection(w2)
    union = w1.union(w2)
    return len(intersection) / float(len(union))


def _compute_tfidf_cosine_similarity(text1: str, text2: str) -> float:
    """Compute TF-IDF weighted cosine similarity between two texts.

    Uses a lightweight, dependency-free implementation. Falls back to Jaccard
    if texts are too short for meaningful TF-IDF. This replaces the basic
    Jaccard similarity for near-duplicate detection per the research spec.
    """
    def _tokenize(text: str) -> List[str]:
        return re.findall(r"\w+", text.lower())

    tokens1 = _tokenize(text1)
    tokens2 = _tokenize(text2)

    if len(tokens1) < 3 or len(tokens2) < 3:
        return _compute_jaccard_similarity(text1, text2)

    # Build term frequency vectors
    tf1 = Counter(tokens1)
    tf2 = Counter(tokens2)

    # Build IDF from both documents (2-document corpus)
    all_terms = set(tf1.keys()) | set(tf2.keys())
    idf: Dict[str, float] = {}
    for term in all_terms:
        doc_count = (1 if term in tf1 else 0) + (1 if term in tf2 else 0)
        idf[term] = math.log(2.0 / doc_count) + 1.0  # smoothed IDF

    # Compute TF-IDF vectors
    vec1: Dict[str, float] = {t: tf1[t] * idf[t] for t in tf1}
    vec2: Dict[str, float] = {t: tf2[t] * idf[t] for t in tf2}

    # Cosine similarity
    dot_product = sum(vec1.get(t, 0) * vec2.get(t, 0) for t in all_terms)
    mag1 = math.sqrt(sum(v ** 2 for v in vec1.values()))
    mag2 = math.sqrt(sum(v ** 2 for v in vec2.values()))

    if mag1 == 0 or mag2 == 0:
        return 0.0

    return dot_product / (mag1 * mag2)


# ─────────────────────────────────────────────────────────────────────────────
# Individual validation gates
# ─────────────────────────────────────────────────────────────────────────────

def check_claim_substantiation(
    caption: str,
    website_rag_context: Optional[List[str]] = None,
    brand_anchor: Optional[str] = None,
) -> bool:
    """FTC Section 5 Claim Substantiation Gate.

    If quantitative metrics, health outcomes, or financial promises exist in
    the caption, verify they exist in the brand anchor or website RAG context.
    If unverified, return False.
    """
    claims = _extract_numbers_and_claims(caption)
    if not claims:
        return True  # No quantitative claims to substantiate

    context_list = list(website_rag_context or [])
    if brand_anchor:
        context_list.append(brand_anchor)
    all_context = " ".join(context_list).lower()

    for claim in claims:
        # Check if metric string appears in retrieved RAG context
        clean_claim = claim.lower().strip()
        if clean_claim not in all_context:
            return False

    return True


def check_reviewer_voice(caption: str) -> bool:
    """Check for reviewer-voice pronoun clusters."""
    lowered = caption.lower()
    for pattern in REVIEWER_VOICE_PATTERNS:
        if re.search(pattern, lowered):
            return False
    return True


def check_audience_leakage(caption: str, target_audience: Optional[str]) -> bool:
    """Check if raw targetAudience JSON text appears verbatim in caption."""
    if not target_audience or len(target_audience.strip()) < 3:
        return True
    return target_audience.lower().strip() not in caption.lower()


def check_exhausted_openers(caption: str) -> bool:
    """Check against overused AI copy tropes."""
    lowered = caption.lower()
    for pattern in EXHAUSTED_OPENER_PATTERNS:
        if re.search(pattern, lowered):
            return False
    return True


def check_near_duplicate(caption: str, past_captions: Optional[List[str]] = None) -> bool:
    """Check if caption cosine similarity exceeds 0.85 against recent published captions.

    Uses TF-IDF weighted cosine similarity (dependency-free) for more semantically
    aware duplicate detection than basic Jaccard. Falls back to Jaccard for very
    short texts.
    """
    if not past_captions:
        return True
    for past in past_captions:
        sim = _compute_tfidf_cosine_similarity(caption, past)
        if sim > 0.85:
            return False
    return True


def check_model_negative_syntax(
    model_name: str,
    positive_prompt: str,
    negative_prompt: Optional[Any],
) -> Tuple[bool, Optional[str]]:
    """Verify negative prompt syntax stratification per model."""
    norm_model = (model_name or "runway").lower().strip()

    # An inline negative payload is wrong for every model: Runway has no
    # negative parsing at all, and Kling/Veo expect it in a separate field.
    # This fires regardless of target because the fix is the same — move it out
    # of the positive prompt. The previous check only looked at the dedicated
    # negative_prompt argument, so a "-v oversaturated, plastic" suffix sitting
    # inside the positive string passed silently.
    for pattern in INLINE_NEGATIVE_PATTERNS:
        if re.search(pattern, positive_prompt, re.IGNORECASE):
            return False, (
                "Negative terms are embedded in the positive prompt. Runway has no "
                "negative parsing; Kling and Veo expect a separate negative field. "
                "Move them out of the positive text."
            )

    if norm_model in ("runway", "gen3", "gen4"):
        # Runway rejects negative prompts completely
        if negative_prompt:
            return False, "Runway Gen-3/4 does not support negative prompts. Negative prompt payload must be null."
        # Forbid negative instructional phrasing in positive prompt
        if re.search(r"\b(do not|no |don't|without)\b", positive_prompt, re.IGNORECASE):
            return False, "Runway positive prompt contains negative instruction phrasing which causes attention focus on suppressed terms."

    elif norm_model in ("veo", "veo3", "google_veo"):
        # Veo requires purely descriptive negative keywords (no "do not show")
        if isinstance(negative_prompt, str):
            if re.search(r"\b(do not|no |don't|without|forbid)\b", negative_prompt, re.IGNORECASE):
                return False, "Veo negative prompt contains instructive language. Must use purely descriptive keywords."

    return True, None


def check_audio_word_budget(audio_tags: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Validate audio direction is within the 15-word budget.

    Research Finding 2: complex audio prompts cause physical reasoning to break
    down due to cross-modal attention conflicts.
    """
    if not audio_tags:
        return True, None

    # Extract content between << and >> if present
    match = re.search(r"<<(.+?)>>", audio_tags)
    if match:
        audio_text = match.group(1)
    else:
        audio_text = audio_tags

    word_count = len(audio_text.strip().split())
    if word_count > AUDIO_MAX_WORDS:
        return False, f"Audio direction exceeds {AUDIO_MAX_WORDS}-word budget ({word_count} words). Complex audio degrades visual fidelity."

    return True, None


def check_background_text_suppression(positive_prompt: str) -> Tuple[bool, Optional[str]]:
    """Reject bulk legible copy, and anything the model cannot resolve.

    One hero string on screen is fine and is usually the point of the ad — see
    LEGIBLE_SCREEN_PATTERNS for why this check no longer rejects those.
    """
    lowered = positive_prompt.lower()
    for pattern in BACKGROUND_TEXT_REQUEST_PATTERNS:
        if re.search(pattern, lowered):
            return False, "Prompt requests background signage or product labels, which render as scribble. Put the message in one hero string instead."

    for pattern, what in LEGIBLE_SCREEN_PATTERNS:
        if re.search(pattern, lowered):
            return False, (
                f"Prompt describes {what}. Keep one large hero string and let the "
                "surrounding interface fall out of focus."
            )

    # Only strings the model has to DRAW count here. A spoken line is also
    # quoted but costs the renderer nothing, so it is excluded by requiring a
    # rendering verb in front of the quote.
    rendered = re.findall(
        r'\b(?:reads?|displays?|shows?|holds the single word|the words?)\s+"[^"]{1,60}"',
        positive_prompt,
        re.IGNORECASE,
    )
    if len(rendered) > MAX_HERO_STRINGS:
        return False, (
            f"Prompt asks for {len(rendered)} separate rendered strings. "
            "Competing text degrades all of it — keep one hero string plus the "
            "brand word."
        )

    for pattern, what in UNRENDERABLE_SPEC_PATTERNS:
        if re.search(pattern, positive_prompt, re.IGNORECASE):
            return False, (
                f"Prompt specifies {what}, which the model cannot resolve. "
                "Describe the look in plain words instead."
            )

    hits = [c for c in BANNED_VISUAL_CLICHES if c in lowered]
    if hits:
        return False, f"Prompt uses banned visual cliches: {', '.join(hits[:3])}."

    return True, None


def check_rendered_claims(
    positive_prompt: str, substantiated: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """Reject invented figures burned into the video.

    A hero string is an advertising claim with the same standing as the
    caption, and captions already pass check_claim_substantiation. Live runs
    produced "12 RSA-2048 Keys Exposed" and "47 keys exposed to quantum" —
    plausible, specific, and entirely fabricated, which is exactly the
    unsubstantiated-claim exposure the caption gate exists to prevent.

    A figure is allowed only when it appears in the substantiating source,
    which is the business profile text the scene was written from.
    """
    source = (substantiated or "").lower()
    for match in re.finditer(r'"([^"]{1,80})"', positive_prompt):
        phrase = match.group(1)
        for figure in re.findall(
            r"\b\d[\d,.]*\s*(?:%|percent|x|k\b|m\b|bn\b)?", phrase
        ):
            token = figure.strip()
            # Bare years and version numbers are naming, not claims —
            # "RSA-2048" and "FIPS 205" are the names of the things.
            if re.fullmatch(r"\d{3,4}", token) and token in phrase.replace(" ", ""):
                if re.search(rf"[A-Za-z-]\s*{re.escape(token)}", phrase):
                    continue
            if token and token.lower() not in source:
                return False, (
                    f'Rendered string "{phrase}" states a figure ({token}) that is '
                    "not in the business profile. Name the state instead — "
                    '"Vulnerable Keys Found", not "47 Vulnerable Keys Found".'
                )
    return True, None


def check_subject_count(positive_prompt: str) -> Tuple[bool, Optional[str]]:
    """Validate prompt restricts to a single prominent human figure.

    Research Finding 3: VBench-2.0 demonstrates an inverse scaling effect —
    as entity count increases, individual feature resolution collapses
    (flickering, morphed anatomies, thousand-hand yoga effect).
    """
    lowered = positive_prompt.lower()
    for pattern in MULTI_SUBJECT_PATTERNS:
        if re.search(pattern, lowered):
            return False, "Prompt specifies multiple human subjects which causes facial collapse and identity drift. Restrict to a single isolated subject."

    # Fidelity is divided by props as well as by faces. One human surrounded by
    # a phone, a laptop, server racks and an LED strip is still five things
    # competing for the same attention budget.
    #
    # The hero-string clause is excluded first. It has to name the surface the
    # string renders on ("the dashboard header reads ..."), and that surface is
    # the same physical object already counted in the scene — counting it again
    # failed prompts for owning one laptop.
    countable = re.sub(
        r'\b[^.,]{0,60}\breads\s+"[^"]{1,60}"[^.]{0,80}', " ", lowered
    )
    # A screen named in the scene and again as the hero surface is one object,
    # not two. Collapse the whole family so "dashboard on the monitor, screen
    # glass reflecting" counts once rather than three times.
    countable = re.sub(
        r"\b(dashboard|monitor|screen|display|laptop screen)\b", "screen", countable
    )
    props = sorted({
        re.sub(r"\\b", "", p).strip()
        for p in COMPETING_PROP_PATTERNS
        if re.search(p, countable)
    })
    if len(props) > MAX_COMPETING_PROPS:
        return False, (
            f"Prompt names {len(props)} competing objects ({', '.join(props[:5])}). "
            f"Keep to one subject and at most {MAX_COMPETING_PROPS} props, or every "
            "element loses definition."
        )

    return True, None


def check_caption_sentence_count(caption: str) -> Tuple[bool, Optional[str]]:
    """Ensure caption is maximum 3 sentences with line breaks.

    Research Section B: Maximum 3 sentences with line breaks between each.
    Dense paragraphs suppress engagement on high-speed mobile scrolling.
    """
    # Split on line breaks to count logical sentences
    lines = [line.strip() for line in caption.split("\n") if line.strip()]
    if len(lines) > CAPTION_MAX_SENTENCES:
        return False, f"Caption has {len(lines)} sentences/lines (max {CAPTION_MAX_SENTENCES}). Dense paragraphs suppress engagement."

    return True, None


# ─────────────────────────────────────────────────────────────────────────────
# Composite validation functions
# ─────────────────────────────────────────────────────────────────────────────

def validate_video_prompt(
    business_profile: BusinessProfile,
    prompt_payload: dict,
    target_model: str = "runway",
) -> PromptValidationResult:
    """Validate a generated video prompt against physical and grammar gates."""
    errors: List[str] = []

    positive_prompt = prompt_payload.get("positive_prompt") or prompt_payload.get("prompt") or ""
    if isinstance(positive_prompt, dict):
        positive_prompt = " ".join(str(v) for v in positive_prompt.values())
    elif not isinstance(positive_prompt, str):
        positive_prompt = str(positive_prompt)

    negative_prompt = prompt_payload.get("negative_prompt") or prompt_payload.get("negative_keywords")

    # Gate 1: Brand voice fields
    if not business_profile.toneOfVoice:
        errors.append("BusinessProfile.toneOfVoice is missing – brand voice cannot be enforced.")
    if not business_profile.primaryOffer:
        errors.append("BusinessProfile.primaryOffer is missing – CTA must be present.")

    # Gate 2: Visual density threshold
    word_count = _word_count(positive_prompt)
    visual_density_valid = word_count <= PROMPT_MAX_WORDS
    if not visual_density_valid:
        errors.append(f"Prompt exceeds word budget of {PROMPT_MAX_WORDS} (found {word_count} words).")

    # Gate 3: Physics and cut constraint (temporal sequence words + physics stressors)
    physics_and_cut_valid = True
    tokens = set(re.findall(r"\w+", positive_prompt.lower()))
    if found_temporal := TEMPORAL_SEQUENCE_WORDS.intersection(tokens):
        physics_and_cut_valid = False
        errors.append(f"Prompt contains temporal sequencing words {found_temporal} which cause identity drift across frames.")

    if found_stressors := PHYSICS_STRESSORS.intersection(tokens):
        physics_and_cut_valid = False
        errors.append(f"Prompt includes high-velocity physics stressors {found_stressors} which degrade physical commonsense.")

    # Gate 4: Negative syntax stratification
    syntax_ok, syntax_err = check_model_negative_syntax(target_model, positive_prompt, negative_prompt)
    if not syntax_ok:
        errors.append(syntax_err or "Invalid negative prompt syntax for target model.")

    # Gate 5: Audio word budget (if audio tags present)
    audio_tags = prompt_payload.get("audio_tags") or None
    # Also check within multi_prompt for inline audio tags
    if not audio_tags:
        multi_prompt = prompt_payload.get("multi_prompt", [])
        for mp in multi_prompt:
            prompt_text = mp.get("prompt", "")
            match = re.search(r"(<<.+?>>)", prompt_text)
            if match:
                audio_tags = match.group(1)
                break
    audio_ok, audio_err = check_audio_word_budget(audio_tags)
    audio_word_budget_valid = audio_ok
    if not audio_ok:
        errors.append(audio_err or "Audio direction exceeds word budget.")

    # Gate 6: Background text suppression
    bg_ok, bg_err = check_background_text_suppression(positive_prompt)
    background_text_suppression_valid = bg_ok
    if not bg_ok:
        errors.append(bg_err or "Prompt requests background text rendering.")

    # Gate 6b: Figures rendered into the frame are advertising claims, and get
    # the same substantiation treatment as the caption. The business profile is
    # the source of truth, same as check_claim_substantiation uses.
    # The stored brand intelligence is included because it holds what the
    # website actually said. A figure genuinely published by the business
    # survives the scrape into there, so this is what lets a real price or a
    # real customer count through while still blocking an invented one.
    from services.brand_intelligence import substantiation_source

    claim_source = substantiation_source(
        getattr(business_profile, "brandIntelligence", None), business_profile
    )
    claim_ok, claim_err = check_rendered_claims(positive_prompt, claim_source)
    if not claim_ok:
        errors.append(claim_err or "Prompt renders an unsubstantiated figure.")

    # Gate 7: Subject count (single isolated subject)
    subj_ok, subj_err = check_subject_count(positive_prompt)
    subject_count_valid = subj_ok
    if not subj_ok:
        errors.append(subj_err or "Prompt contains multiple human subjects.")

    return PromptValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        visual_density_valid=visual_density_valid,
        physics_and_cut_valid=physics_and_cut_valid,
        model_negative_syntax_valid=syntax_ok,
        audio_word_budget_valid=audio_word_budget_valid,
        background_text_suppression_valid=background_text_suppression_valid,
        subject_count_valid=subject_count_valid,
    )


def validate_caption(
    business_profile: BusinessProfile,
    caption: str,
    customer_motivator: Optional[str] = None,
    website_rag_context: Optional[List[str]] = None,
    past_captions: Optional[List[str]] = None,
) -> PromptValidationResult:
    """Validate a generated social caption against all quality and safety gates."""
    errors: List[str] = []

    # Check 1: Length
    if len(caption) > CAPTION_MAX_LENGTH:
        errors.append(f"Caption exceeds max length of {CAPTION_MAX_LENGTH} characters.")

    # Check 2: FTC Claim Substantiation Gate
    claim_substantiated = check_claim_substantiation(
        caption=caption,
        website_rag_context=website_rag_context,
        brand_anchor=business_profile.primaryOffer,
    )
    if not claim_substantiated:
        errors.append("Caption contains unverified quantitative or health claims not substantiated by website RAG context (FTC Sec 5 violation).")

    # Check 3: Reviewer Voice Check
    reviewer_voice_free = check_reviewer_voice(caption)
    if not reviewer_voice_free:
        errors.append("Caption contains reviewer-voice phrasing ('we tested', 'our pick', etc.).")

    # Check 4: Audience Leakage Check
    audience_leakage_free = check_audience_leakage(caption, business_profile.targetAudience)
    if not audience_leakage_free:
        errors.append("Caption leaks raw targetAudience string verbatim instead of addressing motivator.")

    # Check 5: Exhausted Openers
    exhausted_opener_free = check_exhausted_openers(caption)
    if not exhausted_opener_free:
        errors.append("Caption uses overused AI copy trope opener.")

    # Check 6: Near Duplicate Detection (TF-IDF cosine similarity)
    near_duplicate_free = check_near_duplicate(caption, past_captions)
    if not near_duplicate_free:
        errors.append("Caption is a near-duplicate (>0.85 cosine similarity) of a recently published post.")

    # Check 7: Sentence count (max 3 with line breaks)
    sent_ok, sent_err = check_caption_sentence_count(caption)
    caption_sentence_count_valid = sent_ok
    if not sent_ok:
        errors.append(sent_err or "Caption exceeds sentence count limit.")

    is_valid = len(errors) == 0

    return PromptValidationResult(
        is_valid=is_valid,
        errors=errors,
        claim_substantiated=claim_substantiated,
        reviewer_voice_free=reviewer_voice_free,
        audience_leakage_free=audience_leakage_free,
        exhausted_opener_free=exhausted_opener_free,
        near_duplicate_free=near_duplicate_free,
        caption_sentence_count_valid=caption_sentence_count_valid,
    )

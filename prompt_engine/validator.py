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
PROMPT_MAX_WORDS = 85
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

# Background text request patterns (Finding 4)
BACKGROUND_TEXT_REQUEST_PATTERNS = [
    r"\bshow text\b", r"\bdisplay text\b", r"\btext overlay\b",
    r"\bon-screen text\b", r"\bshow signage\b", r"\bdisplay signage\b",
    r"\bbillboard\b", r"\bbanner text\b", r"\bproduct label\b",
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
    """Check that the video prompt does not request on-screen text rendering.

    Research Finding 4: incidental text rendering collapses into graffiti-like
    artifacts. Prompts requesting text, signage, or labels will degrade output.
    """
    lowered = positive_prompt.lower()
    for pattern in BACKGROUND_TEXT_REQUEST_PATTERNS:
        if re.search(pattern, lowered):
            return False, f"Prompt requests on-screen text/signage which causes rendering artifacts. Remove text requests or use a dedicated text-rendering sub-model."

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
            return False, f"Prompt specifies multiple human subjects which causes facial collapse and identity drift. Restrict to a single isolated subject."

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

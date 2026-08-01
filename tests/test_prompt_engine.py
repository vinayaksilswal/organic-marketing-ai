"""Unit and integration tests for Prompt Engine module.

Tests model-specific brief compilers, 8 automated quality gates (FTC claim substantiation,
reviewer voice, audience leakage, exhausted openers, density, physics/cuts),
new gates (audio budget, background text suppression, subject count, caption sentences),
caption system prompt builder, LLM caption generation, FastAPI prompt engine router
endpoints, and CI golden dataset evaluation.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from prompt_engine.compilers import (
    compile_runway_prompt,
    compile_kling_prompt,
    compile_veo_prompt,
    compile_sora_prompt,
    compile_pika_prompt,
    compile_video_prompt,
    build_caption_system_prompt,
    _enforce_background_text_suppression,
    _cap_audio_words,
    get_rotated_camera_vector,
)
from prompt_engine.validator import (
    check_claim_substantiation,
    check_reviewer_voice,
    check_audience_leakage,
    check_exhausted_openers,
    check_near_duplicate,
    check_model_negative_syntax,
    check_audio_word_budget,
    check_background_text_suppression,
    check_subject_count,
    check_caption_sentence_count,
    validate_video_prompt,
    validate_caption,
    _compute_tfidf_cosine_similarity,
)
from prompt_engine.models import PromptCreateRequest, CaptionCreateRequest
from database import BusinessProfile


@pytest.fixture
def mock_business_profile():
    bp = MagicMock(spec=BusinessProfile)
    bp.id = "bp_test_123"
    bp.businessProfileId = "ws_test_123"
    bp.companyName = "Acme Organic Labs"
    bp.primaryOffer = "Organic Vitamin C Serum"
    bp.toneOfVoice = "Professional, warm, scientifically grounded"
    bp.targetAudience = "Tech professionals and wellness enthusiasts"
    bp.websiteUrl = "https://acmeorganic.com"
    bp.name = "Acme Organic Labs"
    return bp


# ─────────────────────────────────────────────────────────────────────────────
# Compiler Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_compile_runway_prompt():
    payload = compile_runway_prompt(
        intent="Show serum application on face",
        brand_aesthetic="Warm natural daylight",
        camera_vector="Slow dolly forward",
        primary_offer="Organic Vitamin C Serum",
    )
    assert payload.model_name == "runway"
    assert "Slow dolly forward:" in payload.positive_prompt
    assert payload.negative_prompt is None  # Runway rejects negative prompts
    assert payload.word_count <= 85
    assert "then" not in payload.positive_prompt.lower()


def test_compile_runway_prompt_has_background_text_suppression():
    payload = compile_runway_prompt(
        intent="Show serum bottle on shelf",
        brand_aesthetic="Clean studio",
    )
    lowered = payload.positive_prompt.lower()
    assert any(phrase in lowered for phrase in [
        "free of text", "free of signage", "no signage", "no labels",
        "without background signage", "clean surfaces",
    ])


def test_compile_kling_prompt():
    payload = compile_kling_prompt(
        intent="Show serum bottle on pedestal",
        brand_aesthetic="Luxury dark mode studio",
        camera_vector="Static tripod shot",
        product_image_base64="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAE=",
        seed=42,
        audio_descriptor="Soft ambient piano note",
    )
    assert payload.model_name == "kling"
    assert "<<Soft ambient piano note>>" in payload.positive_prompt
    assert payload.reference_image_base64 == "iVBORw0KGgoAAAANSUhEUgAAAAE="
    assert payload.seed == 42
    assert "negative_prompt" in payload.model_specific_payload


def test_compile_kling_audio_capped():
    """Verify that audio descriptors exceeding 15 words are truncated."""
    long_audio = "very " * 20 + "long ambient sound"
    payload = compile_kling_prompt(
        intent="Show bottle",
        audio_descriptor=long_audio,
    )
    # Extract audio tag content
    import re
    match = re.search(r"<<(.+?)>>", payload.positive_prompt)
    assert match
    audio_words = match.group(1).split()
    assert len(audio_words) <= 15


def test_compile_veo_prompt():
    payload = compile_veo_prompt(
        intent="Demonstrate skin absorption",
        brand_aesthetic="Photorealistic 8k vertical 9:16",
        camera_vector="Handheld steady tracking",
    )
    assert payload.model_name == "veo"
    assert "Subject:" in payload.positive_prompt
    assert "Context:" in payload.positive_prompt
    assert isinstance(payload.negative_prompt, list)
    assert "walls" in payload.negative_prompt


def test_compile_veo_prompt_no_text_in_context():
    """Veo context field should suppress background text."""
    payload = compile_veo_prompt(intent="Show product")
    assert "free of text" in payload.model_specific_payload["ingredients"]["context"].lower() or \
           "no text" in payload.model_specific_payload["ingredients"]["context"].lower()


def test_compile_sora_prompt():
    payload = compile_sora_prompt(
        intent="Droplet landing on smooth surface",
        brand_aesthetic="Realistic gravity and lighting",
        seed=100,
    )
    assert payload.model_name == "sora"
    assert payload.seed == 100
    assert payload.word_count > 0


def test_compile_pika_prompt():
    payload = compile_pika_prompt(intent="Show ceramic mug with steam")
    assert payload.model_name == "pika"
    assert "localized" in payload.model_specific_payload["options"].get("motion", "").lower() or \
           "localized" in payload.positive_prompt.lower()
    # Pika should have background text suppression
    lowered = payload.positive_prompt.lower()
    assert "no visible background text" in lowered or "signage" in lowered


def test_compile_video_prompt_routing():
    p1 = compile_video_prompt("runway", "Test intent")
    assert p1.model_name == "runway"

    p2 = compile_video_prompt("veo", "Test intent")
    assert p2.model_name == "veo"

    p3 = compile_video_prompt("kling", "Test intent")
    assert p3.model_name == "kling"

    p4 = compile_video_prompt("sora", "Test intent")
    assert p4.model_name == "sora"

    p5 = compile_video_prompt("pika", "Test intent")
    assert p5.model_name == "pika"


# ─────────────────────────────────────────────────────────────────────────────
# Background text suppression utility tests
# ─────────────────────────────────────────────────────────────────────────────

def test_enforce_background_text_suppression_adds_clause():
    result = _enforce_background_text_suppression("A beautiful scene in a studio.")
    assert "free of text" in result.lower()


def test_enforce_background_text_suppression_skips_if_present():
    original = "A studio scene with no signage or labels."
    result = _enforce_background_text_suppression(original)
    # Should not double-append
    assert result.count("no signage") == 1 or result.count("No visible") == 0


# ─────────────────────────────────────────────────────────────────────────────
# Audio cap utility tests
# ─────────────────────────────────────────────────────────────────────────────

def test_cap_audio_words_within_limit():
    assert _cap_audio_words("Soft piano", max_words=15) == "Soft piano"


def test_cap_audio_words_truncates():
    long_audio = " ".join(["word"] * 20)
    result = _cap_audio_words(long_audio, max_words=15)
    assert len(result.split()) == 15


# ─────────────────────────────────────────────────────────────────────────────
# Camera rotation tests
# ─────────────────────────────────────────────────────────────────────────────

def test_camera_vector_rotation():
    v0 = get_rotated_camera_vector(0)
    v1 = get_rotated_camera_vector(1)
    assert v0 != v1
    # Should wrap around
    v_wrap = get_rotated_camera_vector(8)
    assert v_wrap == v0


# ─────────────────────────────────────────────────────────────────────────────
# Caption system prompt builder tests
# ─────────────────────────────────────────────────────────────────────────────

def test_build_caption_system_prompt_contains_key_elements():
    prompt = build_caption_system_prompt(
        brand_name="Acme Labs",
        customer_motivator="needs peer-reviewed safety evidence",
        brand_language_anchor="100% Organic Vitamin C",
        product_feature="Vitamin C Serum",
    )
    assert "Acme Labs" in prompt
    assert "needs peer-reviewed safety evidence" in prompt
    assert "100% Organic Vitamin C" in prompt
    assert "Vitamin C Serum" in prompt
    # Should contain negative exemplars
    assert "DO NOT DO THIS" in prompt
    assert "Fails:" in prompt
    # Should contain output rules
    assert "Maximum 3 sentences" in prompt
    assert "SAFETY:" in prompt


# ─────────────────────────────────────────────────────────────────────────────
# Validator Tests — Original gates
# ─────────────────────────────────────────────────────────────────────────────

def test_ftc_claim_substantiation_gate():
    # Valid claim present in RAG context
    substantiated = check_claim_substantiation(
        caption="Get 34% smoother skin with our serum.",
        website_rag_context=["Clinical trial results showed 34% smoother skin in 14 days."],
        brand_anchor="Organic Vitamin C Serum",
    )
    assert substantiated is True

    # Unverified claim NOT in RAG context
    unverified = check_claim_substantiation(
        caption="Guaranteed 99% wrinkle removal in 2 hours for $50.",
        website_rag_context=["Our serum provides hydration."],
        brand_anchor="Organic Vitamin C Serum",
    )
    assert unverified is False


def test_ftc_health_claim_detection():
    """Verify that health outcome claims are caught by the FTC gate."""
    result = check_claim_substantiation(
        caption="This serum cures acne and prevents wrinkles.",
        website_rag_context=["Our serum provides deep hydration."],
        brand_anchor="Organic Vitamin C Serum",
    )
    assert result is False


def test_ftc_financial_claim_detection():
    """Verify that financial promise claims are caught by the FTC gate."""
    result = check_claim_substantiation(
        caption="Earn $500 passive income monthly with our platform.",
        website_rag_context=["Our platform helps you save time."],
        brand_anchor="Marketing Platform",
    )
    assert result is False


def test_reviewer_voice_check():
    assert check_reviewer_voice("Try our Organic Vitamin C Serum today.") is True
    assert check_reviewer_voice("We tested this serum and our team highly recommends it!") is False
    assert check_reviewer_voice("Our pick for the best serum of 2026.") is False


def test_audience_leakage_check():
    target_aud = "Tech professionals and wellness enthusiasts"
    assert check_audience_leakage("Formulated for busy professionals seeking clarity.", target_aud) is True
    assert check_audience_leakage("Perfect for Tech professionals and wellness enthusiasts!", target_aud) is False


def test_exhausted_openers_check():
    assert check_exhausted_openers("Nourish your skin with pure botanical extracts.") is True
    assert check_exhausted_openers("In today's fast-paced world, finding skincare is hard.") is False
    assert check_exhausted_openers("Unlock the power of radiant skin today.") is False


def test_near_duplicate_check():
    past = ["Nourish your skin with our pure botanical Vitamin C serum everyday."]
    assert check_near_duplicate("Transform your routine with rich facial hydration.", past) is True
    assert check_near_duplicate("Nourish your skin with our pure botanical Vitamin C serum everyday.", past) is False


def test_model_negative_syntax_check():
    # Runway must have null negative prompt
    ok, _ = check_model_negative_syntax("runway", "Slow dolly of a serum bottle.", None)
    assert ok is True

    bad, msg = check_model_negative_syntax("runway", "Slow dolly of a serum bottle.", "-v plastic")
    assert bad is False

    # Runway positive prompt must not use negative phrasing
    bad_pos, msg_pos = check_model_negative_syntax("runway", "Do not show walls around bottle.", None)
    assert bad_pos is False

    # Veo negative keywords must not use instructive language
    veo_bad, veo_msg = check_model_negative_syntax("veo", "Subject: Bottle.", "do not show reflections")
    assert veo_bad is False


# ─────────────────────────────────────────────────────────────────────────────
# Validator Tests — New gates
# ─────────────────────────────────────────────────────────────────────────────

def test_audio_word_budget_valid():
    ok, _ = check_audio_word_budget("<<Soft ambient piano>>")
    assert ok is True


def test_audio_word_budget_exceeded():
    long_audio = "<<" + " ".join(["word"] * 20) + ">>"
    ok, msg = check_audio_word_budget(long_audio)
    assert ok is False
    assert "exceeds" in msg.lower()


def test_audio_word_budget_none():
    ok, _ = check_audio_word_budget(None)
    assert ok is True


def test_background_text_suppression_clean():
    ok, _ = check_background_text_suppression("A single subject in a studio with warm lighting.")
    assert ok is True


def test_background_text_suppression_violation():
    ok, msg = check_background_text_suppression("Show text overlay with product name and billboard in background.")
    assert ok is False
    assert "render" in msg.lower() or "hero string" in msg.lower()


def test_subject_count_valid():
    ok, _ = check_subject_count("A single subject in an isolated setting.")
    assert ok is True


def test_subject_count_violation():
    ok, msg = check_subject_count("A crowd of people walking through a busy street.")
    assert ok is False
    assert "multiple" in msg.lower() or "facial collapse" in msg.lower()


def test_subject_count_group():
    ok, msg = check_subject_count("A group of friends enjoying coffee at a cafe.")
    assert ok is False


def test_caption_sentence_count_valid():
    caption = "Line one.\n\nLine two.\n\nLine three."
    ok, _ = check_caption_sentence_count(caption)
    assert ok is True


def test_caption_sentence_count_exceeded():
    caption = "Line one.\n\nLine two.\n\nLine three.\n\nLine four."
    ok, msg = check_caption_sentence_count(caption)
    assert ok is False
    assert "4" in msg


# ─────────────────────────────────────────────────────────────────────────────
# TF-IDF cosine similarity tests
# ─────────────────────────────────────────────────────────────────────────────

def test_tfidf_cosine_identical():
    sim = _compute_tfidf_cosine_similarity(
        "Nourish your skin with our pure botanical serum",
        "Nourish your skin with our pure botanical serum",
    )
    assert sim > 0.99


def test_tfidf_cosine_different():
    sim = _compute_tfidf_cosine_similarity(
        "Nourish your skin with our pure botanical serum",
        "Transform your workflow with enterprise analytics",
    )
    assert sim < 0.5


def test_tfidf_cosine_short_fallback():
    """Short texts should fall back to Jaccard."""
    sim = _compute_tfidf_cosine_similarity("hi", "hi")
    assert sim > 0.99


# ─────────────────────────────────────────────────────────────────────────────
# Composite validation tests
# ─────────────────────────────────────────────────────────────────────────────

def test_validate_video_prompt(mock_business_profile):
    valid_payload = {
        "positive_prompt": "Slow dolly forward: A single subject demonstrating serum application. Warm cinematic lighting. Ultra-detailed 8k.",
        "negative_prompt": None,
    }
    result = validate_video_prompt(mock_business_profile, valid_payload, target_model="runway")
    assert result.is_valid is True
    assert result.visual_density_valid is True
    assert result.physics_and_cut_valid is True
    assert result.audio_word_budget_valid is True
    assert result.background_text_suppression_valid is True
    assert result.subject_count_valid is True

    invalid_payload = {
        "positive_prompt": "First show face then pan to terminal next flip to reveal splashes burst explosion high-velocity",
        "negative_prompt": None,
    }
    invalid_res = validate_video_prompt(mock_business_profile, invalid_payload, target_model="runway")
    assert invalid_res.is_valid is False
    assert invalid_res.physics_and_cut_valid is False


def test_validate_video_prompt_catches_crowd(mock_business_profile):
    payload = {
        "positive_prompt": "A crowd of people walking through a busy market street.",
        "negative_prompt": None,
    }
    result = validate_video_prompt(mock_business_profile, payload, target_model="runway")
    assert result.subject_count_valid is False


def test_validate_caption(mock_business_profile):
    good_caption = "Formulated with 100% organic Vitamin C. Experience deep hydration daily at acmeorganic.com."
    res = validate_caption(
        mock_business_profile,
        good_caption,
        website_rag_context=["100% organic Vitamin C"],
    )
    assert res.is_valid is True
    assert res.claim_substantiated is True
    assert res.reviewer_voice_free is True

    bad_caption = "We tested this product and our team gives it 99% approval! In today's fast-paced world, perfect for Tech professionals and wellness enthusiasts."
    bad_res = validate_caption(
        mock_business_profile,
        bad_caption,
        website_rag_context=["Hydrating serum"],
    )
    assert bad_res.is_valid is False
    assert bad_res.reviewer_voice_free is False
    assert bad_res.audience_leakage_free is False
    assert bad_res.exhausted_opener_free is False
    assert bad_res.claim_substantiated is False


def test_validate_caption_sentence_count(mock_business_profile):
    """Caption with more than 3 lines should fail sentence count check."""
    long_caption = "Line 1.\n\nLine 2.\n\nLine 3.\n\nLine 4."
    res = validate_caption(mock_business_profile, long_caption)
    assert res.caption_sentence_count_valid is False


# ─────────────────────────────────────────────────────────────────────────────
# Caption generator tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_caption_generator_template_fallback(mock_business_profile):
    """When LLM is disabled, should produce a valid template caption."""
    from prompt_engine.caption_generator import generate_caption_via_llm

    caption, validation, method = await generate_caption_via_llm(
        business_profile=mock_business_profile,
        product_feature="Vitamin C Serum",
        customer_motivator="needs peer-reviewed evidence",
        brand_language_anchor="Organic Vitamin C Serum",
        website_rag_context=["Organic Vitamin C Serum"],
        llm_enabled=False,
    )
    assert method == "template"
    assert len(caption) > 0
    assert "Vitamin C Serum" in caption or "Organic Vitamin C Serum" in caption


@pytest.mark.asyncio
async def test_caption_generator_llm_success(mock_business_profile):
    """When LLM returns a valid caption, should return it on first attempt."""
    from prompt_engine.caption_generator import generate_caption_via_llm

    mock_llm_output = (
        "Your morning routine deserves Organic Vitamin C Serum for visible radiance.\n\n"
        "Formulated with verified botanical extracts for measurable hydration.\n\n"
        "Explore the full collection at acmeorganic.com."
    )

    with patch("prompt_engine.caption_generator._call_llm", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_llm_output

        caption, validation, method = await generate_caption_via_llm(
            business_profile=mock_business_profile,
            product_feature="Vitamin C Serum",
            customer_motivator="needs peer-reviewed evidence",
            brand_language_anchor="Organic Vitamin C Serum",
            website_rag_context=["Organic Vitamin C Serum"],
            llm_enabled=True,
        )
        assert method == "llm"
        assert len(caption) > 0


@pytest.mark.asyncio
async def test_caption_generator_llm_failure_falls_back(mock_business_profile):
    """When LLM fails repeatedly, should fall back to template."""
    from prompt_engine.caption_generator import generate_caption_via_llm

    with patch("prompt_engine.caption_generator._call_llm", new_callable=AsyncMock) as mock_gen:
        mock_gen.side_effect = Exception("LLM unavailable")

        caption, validation, method = await generate_caption_via_llm(
            business_profile=mock_business_profile,
            product_feature="Vitamin C Serum",
            customer_motivator="needs evidence",
            brand_language_anchor="Organic Vitamin C Serum",
            website_rag_context=["Organic Vitamin C Serum"],
            llm_enabled=True,
        )
        assert method == "template"
        assert len(caption) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Integration tests (require client fixture)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_prompt_video_and_retrieval(authed_client, db_session):
    client, login = authed_client
    login('ws_api_test')
    # Setup BusinessProfile
    bp = BusinessProfile(
        id="bp_api_test",
        userId="ws_api_test",
        name="Test Bio",
        primaryOffer="Botanical Face Oil",
        toneOfVoice="Sleek and natural",
        targetAudience="Wellness enthusiasts",
    )
    db_session.add(bp)
    await db_session.commit()

    headers = {"X-Workspace-Id": "bp_api_test"}
    payload = {
        "business_profile_id": "bp_api_test",
        "intent": "Demonstrate face oil application",
        "model_name": "runway",
        "brand_aesthetic": "Warm daylight",
    }

    resp = await client.post("/api/v1/prompt/video", json=payload, headers=headers)
    if resp.status_code != 200:
        print("VIDEO 422 DETAIL:", resp.json())
    assert resp.status_code == 200
    data = resp.json()
    assert data["model_name"] == "runway"
    assert data["is_valid"] is True
    prompt_id = data["id"]

    # Retrieve prompt by ID
    get_resp = await client.get(f"/api/v1/prompt/{prompt_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == prompt_id

    # Retrieve prompt validation log by ID
    val_resp = await client.get(f"/api/v1/prompt/{prompt_id}/validation", headers=headers)
    assert val_resp.status_code == 200
    assert val_resp.json()["is_valid"] is True


@pytest.mark.asyncio
async def test_api_prompt_caption(authed_client, db_session):
    client, login = authed_client
    login('ws_cap_test')
    bp = BusinessProfile(
        id="bp_cap_test",
        userId="ws_cap_test",
        name="Pure Botanical",
        primaryOffer="100% Organic Vitamin C Serum",
        toneOfVoice="Clear and direct",
        targetAudience="Skincare lovers",
    )
    db_session.add(bp)
    await db_session.commit()

    headers = {"X-Workspace-Id": "bp_cap_test"}
    payload = {
        "business_profile_id": "bp_cap_test",
        "product_feature": "100% Organic Vitamin C Serum",
        "customer_motivator": "needs peer-reviewed safety evidence",
        "brand_language_anchor": "100% Organic Vitamin C Serum",
        "website_rag_context": ["100% Organic Vitamin C Serum"],
    }

    resp = await client.post("/api/v1/prompt/caption", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_valid"] is True
    assert "detailed_checks" in data
    assert data["detailed_checks"]["claim_substantiated"] is True


@pytest.mark.asyncio
async def test_api_caption_validate_standalone(authed_client, db_session):
    client, login = authed_client
    login('ws_val_test')
    bp = BusinessProfile(
        id="bp_val_test",
        userId="ws_val_test",
        name="Validate Corp",
        primaryOffer="Analytics Platform",
        toneOfVoice="Professional",
        targetAudience="Enterprise users",
    )
    db_session.add(bp)
    await db_session.commit()

    headers = {"X-Workspace-Id": "bp_val_test"}
    payload = {
        "business_profile_id": "bp_val_test",
        "caption": "Our Analytics Platform delivers real-time insights.\n\nBuilt for scale.",
        "website_rag_context": ["Analytics Platform"],
    }

    resp = await client.post("/api/v1/prompt/caption/validate", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_valid"] is True


@pytest.mark.asyncio
async def test_api_ci_golden_dataset_eval(authed_client):
    client, login = authed_client
    login('ws_ci_test')
    headers = {}
    payload = {"dataset_name": "default_golden_dataset"}

    resp = await client.post("/api/v1/prompt/eval/ci", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_samples"] > 0
    assert data["safety_pass_rate"] == 1.0
    assert data["passed_ci_gate"] is True


# ─────────────────────────────────────────────────────────────────────────────
# Brand end-frame: every clip closes on the business name so the reach
# compounds into recall. One word, because that is the only length these models
# render legibly and the only length a scrolling viewer retains.
# ─────────────────────────────────────────────────────────────────────────────

def _brand_scene(**overrides):
    scene = dict(
        camera="slow push-in 35mm",
        subject="compliance lead in wrinkled button-down, lanyard askew",
        action="watches terminal, shoulders drop into slow exhale",
        environment="sterile ops room, blue bias lighting",
        mood="audit relief validated",
        brand_moment="the plate etched into the rack door",
        onscreen_text="quantcai",
    )
    scene.update(overrides)
    return scene


@pytest.mark.parametrize("raw,expected", [
    ("quantcai", "quantcai"),
    ("Northwind Coffee Co.", "Northwind"),      # too long as a pair
    ("The Ridgeline Bikes Ltd", "Ridgeline"),   # filler and suffix stripped
    ("Blue Bottle", "Blue Bottle"),             # short pair: "Blue" recalls nothing
    ("ACME, Inc.", "ACME"),
    ("", ""),
])
def test_brand_endframe_reduces_to_one_rememberable_word(raw, expected):
    from prompt_engine.scene_writer import _brand_endframe
    assert _brand_endframe(raw) == expected


def test_brand_watermark_reaches_the_compiled_prompt():
    """A render confirmed a bottom-centre semi-transparent wordmark comes back
    clean, so it replaced the old 'etched onto a physical surface' treatment —
    that only branded the final beat and needed the scene to contain a surface
    worth etching, which most businesses' scenes do not."""
    from prompt_engine.compilers import compile_video_prompt
    p = compile_video_prompt("runway", "post-quantum readiness",
                             scene_fields=_brand_scene())
    assert '"quantcai"' in p.positive_prompt
    assert "wordmark centred along the bottom edge" in p.positive_prompt
    assert "holding for the whole clip" in p.positive_prompt


@pytest.mark.parametrize("brand", ["quantcai", "Northwind", "Ridgeline"])
def test_every_business_gets_the_watermark(brand):
    """It has to be unconditional — no business should ship an unattributed ad."""
    from prompt_engine.compilers import compile_video_prompt
    p = compile_video_prompt(
        "runway", "x", scene_fields=_brand_scene(onscreen_text=brand)
    )
    assert f'the word "{brand}" as a soft semi-transparent' in p.positive_prompt


def test_watermark_ignores_whatever_surface_the_model_suggested():
    """brand_moment is no longer consulted: the wordmark is composited at the
    bottom edge regardless, which is why it works for every business rather
    than only ones whose scenes contain something engravable."""
    from prompt_engine.compilers import compile_video_prompt
    from prompt_engine import validator

    p = compile_video_prompt(
        "runway", "post-quantum readiness",
        scene_fields=_brand_scene(brand_moment="the monitor bezel display"),
    )
    assert "wordmark centred along the bottom edge" in p.positive_prompt
    assert "monitor bezel" not in p.positive_prompt
    ok, msg = validator.check_background_text_suppression(p.positive_prompt)
    assert ok, msg


@pytest.mark.parametrize("surface", [
    "the plate etched into the rack door",
    "the monitor bezel display",
    "",
])
def test_brand_end_frame_passes_every_gate(surface):
    """The regression that shipped once: the suppression clause contradicted
    the brand word, or its wording tripped Runway's negative-syntax gate."""
    from prompt_engine.compilers import compile_video_prompt
    from prompt_engine import validator

    p = compile_video_prompt("runway", "post-quantum readiness",
                             scene_fields=_brand_scene(brand_moment=surface))
    for name, res in [
        ("background text", validator.check_background_text_suppression(p.positive_prompt)),
        ("runway negatives", validator.check_model_negative_syntax(
            "runway", p.positive_prompt, p.negative_prompt)),
        ("subject count", validator.check_subject_count(p.positive_prompt)),
    ]:
        ok, msg = res if isinstance(res, tuple) else (res, None)
        assert ok, f"{name} gate failed: {msg}"


def test_suppression_clause_does_not_contradict_the_brand_word():
    """"Free of text" and a requested brand word in one prompt makes the model
    pick a winner. Only incidental text is suppressed when a brand is present."""
    from prompt_engine.compilers import compile_video_prompt

    with_brand = compile_video_prompt("runway", "x", scene_fields=_brand_scene())
    assert "free of text" not in with_brand.positive_prompt.lower()
    assert "remain blank" in with_brand.positive_prompt.lower()

    without = compile_video_prompt("runway", "x",
                                   scene_fields=_brand_scene(onscreen_text=""))
    assert "free of text" in without.positive_prompt.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Every clip has to ask for something. Ending on the bare brand name leaves the
# viewer with nothing to do, which is the difference between an ad and a clip.
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("brand,offer,expected", [
    ("quantcai", "Run a free scan", "Run a free scan at quantcai."),
    ("Ridgeline", "Book a fitting", "Book a fitting at Ridgeline."),
    ("Northwind Coffee", "Start a subscription", "Start a subscription at Northwind Coffee."),
    # A vague object is replaced by the brand rather than having it bolted on.
    ("Acme", "Visit us", "Visit Acme."),
    ("Acme", "Visit our site", "Visit Acme."),
    # No offer at all still yields a usable line.
    ("Acme", "", "Visit Acme to get started."),
])
def test_fallback_cta_always_names_the_brand(brand, offer, expected):
    from prompt_engine.scene_writer import _fallback_cta
    assert _fallback_cta(brand, offer) == expected


def test_fallback_cta_rejects_an_offer_too_long_to_speak():
    """A long offer outruns the closing beat and the model clips it mid-word."""
    from prompt_engine.scene_writer import _fallback_cta
    out = _fallback_cta("Acme", "Head over to our website today and browse the entire spring collection now")
    assert len(out.split()) <= 9
    assert "Acme" in out


def test_fallback_cta_needs_a_brand():
    from prompt_engine.scene_writer import _fallback_cta
    assert _fallback_cta("", "Run a scan") == ""


def test_spoken_cta_reaches_the_compiled_prompt():
    from prompt_engine.compilers import compile_video_prompt
    p = compile_video_prompt(
        "runway", "x",
        scene_fields=_brand_scene(spoken_cta="Run your free scan at quantcai"),
    )
    assert 'over the closing frame, spoken: "Run your free scan at quantcai"' in p.positive_prompt


def test_cta_is_spoken_not_rendered():
    """Burned on screen a CTA sentence renders as smeared glyphs. The only
    rendered text stays the hero string plus the one-word watermark."""
    from prompt_engine.compilers import compile_video_prompt
    from prompt_engine import validator

    p = compile_video_prompt(
        "runway", "x",
        scene_fields=_brand_scene(spoken_cta="Run your free scan at quantcai"),
    )
    assert "spoken" in p.positive_prompt
    ok, msg = validator.check_background_text_suppression(p.positive_prompt)
    assert ok, msg
    ok, msg = validator.check_model_negative_syntax("runway", p.positive_prompt, p.negative_prompt)
    assert ok, msg


# ─────────────────────────────────────────────────────────────────────────────
# The live pipeline path. A render from it came back silent until 3.5 seconds,
# which threw away the verbal third of the three-second hook.
# ─────────────────────────────────────────────────────────────────────────────

_LIVE = ('Slow push-in on a matte-black smartphone. The screen occupies the frame, '
         'reading "RSA-2048 Vulnerable" in large white monospace. Low room tone. '
         '"I found our RSA keys are quantum vulnerable. One scan gave us the CBOM." '
         'Run your free scan at QuantCAI.')


def test_speech_is_pinned_to_the_first_frame():
    from services.video_pipeline_service import _enforce_speech_starts_immediately as f
    out = f(_LIVE)
    assert "already speaking as the first frame begins" in out
    assert "I found our RSA keys" in out


def test_speech_pinning_is_idempotent():
    from services.video_pipeline_service import _enforce_speech_starts_immediately as f
    assert f(f(_LIVE)) == f(_LIVE)


def test_speech_pinning_leaves_short_quotes_alone():
    """A hero string is not dialogue and must not be prefixed as speech."""
    from services.video_pipeline_service import _enforce_speech_starts_immediately as f
    short = 'A mug on a bench, the tag reads "Roasted This Week".'
    assert f(short) == short


def test_speech_pinning_survives_the_runway_negative_gate():
    """The natural phrasing, "no pause before the first word", trips
    check_model_negative_syntax on the leading "no "."""
    from prompt_engine.validator import check_model_negative_syntax
    from services.video_pipeline_service import _enforce_speech_starts_immediately as f
    ok, msg = check_model_negative_syntax("runway", f(_LIVE), None)
    assert ok, msg


def test_brief_vocabulary_never_reaches_a_render():
    """Live output once asked the renderer to draw the words "hero string"."""
    from services.video_pipeline_service import _strip_brief_vocabulary as f
    bad = 'the laptop where the QuantCAI screen displays the hero string "Scan Complete"'
    out = f(bad)
    assert "hero string" not in out
    assert '"Scan Complete"' in out

"""
Tests for Faceless Short Videos on Auto-Pilot & Algorithm Analyzer
"""

import pytest
from services.faceless_service import (
    get_faceless_presets,
    generate_faceless_short,
    analyze_short_form_content,
    FACELESS_TOPICS,
    VISUAL_STYLES,
    VOICE_PERSONAS,
    PUBLISHING_MODES,
    SCHEDULE_PRESETS,
)


def test_presets_structure():
    presets = get_faceless_presets()
    assert "topics" in presets
    assert len(presets["topics"]) >= 5
    assert "visual_styles" in presets
    assert len(presets["visual_styles"]) >= 6
    assert "voice_personas" in presets
    assert len(presets["voice_personas"]) >= 5
    assert "schedule_presets" in presets
    assert len(presets["schedule_presets"]) >= 4

    # Verify topics: Scary Stories, Jokes, Life Pro Tips, Today I Learned, You Should Know
    topic_ids = [t["id"] for t in presets["topics"]]
    assert "scary_stories" in topic_ids
    assert "jokes" in topic_ids
    assert "life_pro_tips" in topic_ids
    assert "today_i_learned" in topic_ids
    assert "you_should_know" in topic_ids


def test_publishing_modes():
    assert "PUBLIC" in PUBLISHING_MODES
    assert "PRIVATE" in PUBLISHING_MODES
    assert "DRAFT_REVIEW" in PUBLISHING_MODES
    # The mode survived the TikTok removal; only its branding went. Holding a
    # post for a one-tap sign-off is useful whoever invented the idea.
    assert "review" in PUBLISHING_MODES["DRAFT_REVIEW"]["label"].lower()
    for mode in PUBLISHING_MODES.values():
        blob = f"{mode.get('label', '')} {mode.get('description', '')}".lower()
        assert "tiktok" not in blob, "TikTok is banned where this product is sold"


@pytest.mark.asyncio
async def test_generate_faceless_short_mock():
    # Test generation with fallback parsing
    result = await generate_faceless_short(
        topic_id="scary_stories",
        visual_style_id="cinematic_realism",
        voice_id="shadow_whisper",
        duration_seconds=20,
        channel_name="Nightmare Chronicles",
    )
    assert "title" in result
    assert "hook" in result
    assert "voiceover_script" in result
    assert "first_frame_prompt" in result
    assert "video_prompt" in result
    assert "last_frame_prompt" in result
    assert "viral_caption" in result
    assert result["duration_seconds"] == 20
    assert result["topic"]["id"] == "scary_stories"


@pytest.mark.asyncio
async def test_generate_faceless_short_custom_topic():
    result = await generate_faceless_short(
        topic_id="custom",
        custom_topic="Dark Greek Mythology & Medusa's Curse",
        visual_style_id="dark_cyberpunk",
        voice_id="adam_storyteller",
        duration_seconds=15,
        channel_name="Mythos Lore",
    )
    assert "title" in result
    assert "Medusa" in result["topic"]["title"] or "Mythology" in result["topic"]["title"]
    assert result["duration_seconds"] == 15


@pytest.mark.asyncio
async def test_analyze_short_form_content():
    content = "Stop scrolling. This one psychology trick makes anyone tell the truth in 3 seconds."
    analysis = await analyze_short_form_content(
        content_text=content,
        niche="Psychology & Life Hacks",
        platform="TikTok / YouTube Shorts",
    )
    assert "viral_score" in analysis
    assert isinstance(analysis["viral_score"], int)
    assert "metrics" in analysis
    assert "hook" in analysis["metrics"]
    assert "fix_the_fail" in analysis
    assert "optimized_rewrite" in analysis
    assert "optimized_hook" in analysis["optimized_rewrite"]

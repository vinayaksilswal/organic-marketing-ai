"""
Tests for Faceless Short Videos on Auto-Pilot & Algorithm Analyzer
"""

import json

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

import services.faceless_service as fs


# These three used to call the live model, which made them a test of the
# provider's uptime: green on a machine with an API key, red in CI without
# one. The model is stubbed now, and the junk-reply path is covered too --
# with a rate-limited free tier that fallback is the common case, not an
# edge case.


SHORT_JSON = json.dumps({
    "title": "The Whisper in the Hallway",
    "hook": "Stop scrolling if you have ever heard your name at 3am.",
    "voiceover_script": "Stop scrolling. [pause] Nobody believed her either.",
    "word_count": 45,
    "first_frame_prompt": "Vertical 9:16, dark hallway, one door ajar, no text",
    "video_prompt": "Vertical 9:16 slow push-in down a dark hallway, 4k",
    "last_frame_prompt": "Minimal 9:16 end card, bold text",
    "viral_caption": "Would you have opened the door? #scarystories",
    "audio_music_recommendation": "low drone",
})

ANALYSIS_JSON = json.dumps({
    "viral_score": 91,
    "growth_tier": "High Growth",
    "percentile_summary": "Better than 91% of content in this niche.",
    "metrics": {"hook": 94, "retention": 88, "shareability": 90,
                "likeability": 81, "commentability": 93},
    "fix_the_fail": [
        {"title": "Pacing drops.", "action": "Cut at 0:04.",
         "severity": "CRITICAL OUTPUT", "timestamp": "At 0:04"},
    ],
    "optimized_rewrite": {"optimized_hook": "Everyone hears it. Nobody says it."},
})


@pytest.fixture
def model(monkeypatch):
    """Answers instantly and identically every run."""

    def _set(response):
        async def fake(*a, **kw):
            return response

        monkeypatch.setattr(fs, "_call_openrouter", fake)

    return _set


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
async def test_generate_faceless_short_mock(model):
    model(SHORT_JSON)
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
async def test_generate_faceless_short_custom_topic(model):
    model(SHORT_JSON)
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
async def test_analyze_short_form_content(model):
    model(ANALYSIS_JSON)
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


@pytest.mark.asyncio
async def test_junk_from_the_model_still_produces_a_usable_short(model):
    """The customer gets a script they can edit, not an error. With a free
    tier that rate-limits, this is the common path."""
    model("I'm sorry, I can't help with that.")
    result = await generate_faceless_short(
        topic_id="scary_stories",
        visual_style_id="cinematic_realism",
        voice_id="shadow_whisper",
        duration_seconds=20,
        channel_name="Nightmare Chronicles",
    )
    for field in ("title", "hook", "voiceover_script", "first_frame_prompt",
                  "video_prompt", "last_frame_prompt", "viral_caption"):
        assert result.get(field), f"{field} came back empty"
    assert result["duration_seconds"] == 20


@pytest.mark.asyncio
async def test_a_fenced_reply_is_still_read(model):
    """Models wrap JSON in ``` fences constantly."""
    model("```json\n" + SHORT_JSON + "\n```")
    result = await generate_faceless_short(
        topic_id="scary_stories",
        visual_style_id="cinematic_realism",
        voice_id="shadow_whisper",
        duration_seconds=20,
        channel_name="Nightmare Chronicles",
    )
    assert result["title"] == "The Whisper in the Hallway"


@pytest.mark.asyncio
async def test_junk_still_scores_the_content(model):
    model("not json at all")
    analysis = await analyze_short_form_content(
        content_text="Stop scrolling.",
        niche="Psychology",
        platform="Reels / Shorts",
    )
    assert isinstance(analysis["viral_score"], int)
    assert set(analysis["metrics"]) >= {"hook", "retention", "shareability"}

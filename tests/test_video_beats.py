"""A clip of any supported length gets a clock, and the clock reaches the model.

Video models take a duration. The prompts written for them almost never say
what happens WHEN, so a model handed "a 30-second ad" spends its budget evenly
and produces thirty seconds of nothing in particular.

Two things must never scale with length. The hook is the window in which a
scroll is decided and the point at which a view is counted; a longer ad does
not earn a longer hook, it earns the same three seconds and then has to keep
what it caught. The end card is one still with a name and an offer, and
holding it longer does not make anyone read it twice.
"""

import pytest

from services import video_beats as vb
from services.video_pipeline_service import generate_prompt


@pytest.mark.parametrize("duration", [8, 10, 15, 20, 30])
def test_the_beats_account_for_every_second(duration):
    beats = vb.build_beats(duration)
    assert beats[0]["start"] == 0.0
    assert beats[-1]["end"] == float(duration)
    for earlier, later in zip(beats, beats[1:]):
        assert earlier["end"] == pytest.approx(later["start"], abs=0.15), (
            "a gap or an overlap between beats leaves seconds unscripted"
        )


@pytest.mark.parametrize("duration", [8, 10, 15, 20, 30])
def test_the_hook_is_always_the_first_three_seconds(duration):
    """The clip is cut into three-second blocks and the first one IS the scroll
    decision, so it never grows with the length of the ad."""
    beats = vb.build_beats(duration)
    assert beats[0]["seconds"] == vb.SEGMENT_SECONDS
    assert beats[0]["name"] == "HOOK"


@pytest.mark.parametrize("duration", [8, 10, 15, 20, 30])
def test_the_last_block_asks_for_the_click(duration):
    beats = vb.build_beats(duration)
    assert "CTA" in beats[-1]["name"]
    # The still card holds for the final two seconds inside that block.
    assert beats[-1]["seconds"] >= vb.OUTRO_SECONDS


@pytest.mark.parametrize("duration", [8, 10, 15, 20, 30])
def test_every_block_is_three_seconds_or_a_folded_tail(duration):
    """A stub shorter than two seconds is folded into the block before it --
    below that a model renders a flash rather than a beat."""
    for b in vb.build_beats(duration):
        assert vb.MIN_TAIL_SECONDS <= b["seconds"] <= vb.SEGMENT_SECONDS + vb.MIN_TAIL_SECONDS


@pytest.mark.parametrize("duration", [8, 10, 15, 20, 30])
def test_no_single_beat_is_long_enough_to_drift(duration):
    """Past roughly eight seconds one shot stops holding: the subject morphs
    and the product becomes a different product."""
    for beat in vb.build_beats(duration):
        assert beat["seconds"] <= vb.MAX_BEAT_SECONDS + 0.01


def test_longer_clips_get_more_beats_not_longer_ones():
    assert len(vb.build_beats(30)) > len(vb.build_beats(10))


@pytest.mark.parametrize("raw,expected", [
    (None, vb.DEFAULT_DURATION),
    ("nonsense", vb.DEFAULT_DURATION),
    (3, vb.MIN_DURATION),
    (120, vb.MAX_DURATION),
    ("15", 15),
    (15.4, 15),
])
def test_a_bad_length_still_produces_a_clip(raw, expected):
    """Clamped rather than rejected: an out-of-range value from an old client
    should make a usable video, not a 422 the user cannot act on."""
    assert vb.clamp_duration(raw) == expected


def test_the_word_budget_grows_with_the_clip():
    assert vb.word_budget(30) > vb.word_budget(10) > vb.word_budget(8)


def test_the_sheet_is_a_timeline_a_person_can_edit():
    """The customer has to find the third block, change one line and paste it
    into a video tool. A paragraph is unreviewable, and an unreviewable prompt
    gets used unedited or not at all."""
    sheet = vb.beat_sheet(20)
    assert "0:00-0:03" in sheet, "blocks are not clock-labelled"
    assert "HOOK" in sheet and "CTA" in sheet
    assert "    VISUAL:" in sheet, "no indented VISUAL line to edit"
    assert "    SCRIPT:" in sheet, "no indented SCRIPT line to edit"
    assert str(vb.word_budget(20)) in sheet


def test_every_block_gets_its_own_visual_and_script():
    sheet = vb.beat_sheet(30)
    blocks = len(vb.build_beats(30))
    assert sheet.count("VISUAL:") >= blocks
    assert sheet.count("SCRIPT:") >= blocks


def test_a_silent_block_still_has_a_script_line():
    """Otherwise the model quietly drops the label and the timeline stops
    being parseable by the person reading it."""
    assert "(silence)" in vb.beat_sheet(30)


def test_continuity_is_stated_once_not_per_block():
    """Repeating a wardrobe description per block is how a model ends up
    rendering two different people."""
    sheet = vb.beat_sheet(30)
    assert "CONTINUITY" in sheet


def test_the_prompt_generator_takes_a_length():
    import inspect

    assert "duration_seconds" in inspect.signature(generate_prompt).parameters


def test_the_prompt_no_longer_hardcodes_ten_seconds():
    """The brief used to state a fixed ten-second clock, which silently
    overrode whatever length the caller asked for."""
    import inspect

    src = inspect.getsource(generate_prompt)
    assert "TEN SECONDS:\n  0-1s" not in src
    assert "beat_sheet" in src, "the generated clock never reaches the prompt"

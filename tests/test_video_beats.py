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
def test_the_hook_and_the_end_card_never_stretch(duration):
    beats = vb.build_beats(duration)
    assert beats[0]["seconds"] == vb.HOOK_SECONDS
    assert beats[-1]["seconds"] == vb.OUTRO_SECONDS


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


def test_the_sheet_names_every_range_and_the_budget():
    sheet = vb.beat_sheet(20)
    assert "0-3s" in sheet and "20s" in sheet
    assert "HOOK" in sheet and "OUTRO" in sheet
    assert str(vb.word_budget(20)) in sheet


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

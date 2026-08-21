"""No caption declaring adult content may reach a public account.

Seventy-eight published captions described these pages as adult content in
plain text -- "We generate fully licensed Bollywood NSFW via AI", hashtagged
#NSFWContent and #AdultAI. Meta's sexual solicitation policy acts on caption
text alone; it does not need to assess the imagery.

The blast radius is the app, not the account. Meta scores an app on the
aggregate behaviour of everything published through it, so one workspace's
captions can cost API access for every customer on the platform.
"""

import inspect

import pytest

from services.caption_policy import enforce, find_violations, is_publishable

# Real captions this platform published.
PUBLISHED_AND_UNACCEPTABLE = [
    "Unlicensed Bollywood NSFW AI gets your account banned. We generate fully "
    "licensed Bollywood NSFW via AI. #NSFWContent #AdultAI",
    "We report daily on how generative video reshapes studios and the NSFW "
    "economy. #AdultTech #NSFWTech",
    "AI adult media revenues are accelerating without transparent data. "
    "#AIAdultMedia #AdultIndustry",
]

# Real captions this platform published that are fine, plus the near-misses a
# careless filter destroys.
LEGITIMATE = [
    "The forest doesn't wait for golden hour. You create it. Cinematic AI "
    "portrait, volumetric fog. #aiart #cinematic",
    "Most avoid the pressure. You step into it. #luxurylifestyle #successmindset",
    "Our adult education programme starts Monday.",
    "He reached adulthood before the company did.",
    "The brief explicitly asks for three revisions.",
    "",
]


@pytest.mark.parametrize("caption", PUBLISHED_AND_UNACCEPTABLE)
def test_captions_that_were_actually_published_are_now_blocked(caption):
    assert find_violations(caption), f"still publishable: {caption[:60]}"
    assert not is_publishable(caption)


@pytest.mark.parametrize("caption", LEGITIMATE)
def test_legitimate_copy_is_untouched(caption):
    """A filter that mangles real captions gets switched off, and then it
    protects nothing."""
    assert is_publishable(caption), f"false positive: {caption[:60]}"


def test_hashtags_are_matched():
    """#NSFWContent has no word boundary before NSFW. Matching only on plain
    words would have missed the most common form in the real captions."""
    assert find_violations("Great shoot today #NSFWContent")
    assert find_violations("#AdultAI is the future")


def test_substrings_inside_ordinary_words_do_not_trip_it():
    assert not find_violations("adulthood")
    assert not find_violations("explicitly stated")


def test_it_falls_back_to_the_asset_description():
    """The vision model writes the description from the picture itself, so it
    carries none of the positioning language that causes this."""
    caption, violations = enforce(
        "Daily NSFW drops #AdultAI",
        "A woman in a red gown seated on a moss-covered log at dusk.",
    )
    assert violations
    assert "moss-covered log" in caption
    assert is_publishable(caption)


def test_it_refuses_when_the_fallback_is_also_unusable():
    """Posting nothing costs one slot in a schedule. Posting this costs the
    app, and with it every other customer."""
    caption, violations = enforce("NSFW content daily", "More NSFW content")
    assert violations
    assert caption == ""


def test_a_clean_caption_passes_through_unchanged():
    original = "Golden hour over the marina. #luxurylifestyle"
    caption, violations = enforce(original, "a boat")
    assert caption == original
    assert violations == []


def test_the_gate_runs_before_publishing():
    import worker

    src = inspect.getsource(worker.context_aggregation_task)
    gate = src.index("enforce_caption_policy")
    # The single point where anything leaves for any platform. Asserting it is
    # present first means a rename cannot turn this test into a pass by making
    # the landmark disappear.
    assert "publish_everywhere" in src, "the publishing landmark moved again"
    publish = src.index("publish_everywhere")
    assert gate < publish, "captions are policy-checked after they are published"


def test_a_blocked_post_is_abandoned_not_published_empty():
    import worker

    src = inspect.getsource(worker.context_aggregation_task)
    assert "blocked_by_caption_policy" in src, (
        "a caption with nothing safe to say must stop the post, not publish a "
        "blank one"
    )


def test_the_list_is_extendable_without_a_deploy():
    import services.caption_policy as policy

    assert "CAPTION_BLOCKED_TERMS" in inspect.getsource(policy)

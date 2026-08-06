"""A ceiling on autonomous posting, to protect the app rather than the account.

The posting interval belongs to the customer. This does not: Meta scores an
app on the aggregate behaviour of every account authorised to it, so one
workspace flooding its feed degrades API access for every other workspace on
the same app -- and for the product itself.

An hourly interval is 24 posts a day. No authentic business account posts
hourly, and the platform reads it as automated flooding whether the post
arrives via the API or the app. A customer selecting "every 1 hour" is
choosing a cadence, not consenting to a ban, so the interval setting alone
could not carry this decision.
"""

import inspect

import pytest

import services.scheduler as scheduler


def test_a_ceiling_exists():
    assert hasattr(scheduler, "MAX_POSTS_PER_DAY")
    assert scheduler.MAX_POSTS_PER_DAY > 0


def test_the_ceiling_is_below_what_looks_automated():
    """Hourly posting is the pattern that gets accounts flagged. The rail has
    to sit under it or it is decoration."""
    assert scheduler.MAX_POSTS_PER_DAY < 24


def test_the_ceiling_allows_a_real_publishing_schedule():
    """Several posts a day is normal for an active business. A rail that
    blocked that would be protecting the app by breaking the product."""
    assert scheduler.MAX_POSTS_PER_DAY >= 4


def test_it_is_configurable_without_a_code_change():
    src = inspect.getsource(scheduler)
    assert "SOCIAL_MAX_POSTS_PER_DAY" in src, (
        "an account with the engagement to carry more has no way to raise it"
    )


def test_the_window_is_rolling_not_calendar():
    """A midnight reset lets a workspace post its whole allowance at 23:59 and
    again at 00:01, which is exactly the burst the rail exists to prevent."""
    src = inspect.getsource(scheduler.posts_in_last_24h)
    assert "hours=24" in src
    assert "utc_now()" in src


def test_the_check_runs_before_publishing():
    src = inspect.getsource(scheduler.execute_marketing_loop)
    cap = src.index("posts_in_last_24h")
    publish = src.index("_execute_inline(workspace_id)")
    assert cap < publish, "the cap is checked after the post has gone out"


def test_hitting_the_cap_is_reported_not_silent():
    """Every silent skip in this loop has cost hours to diagnose.

    Asserted on the outcome label and the presence of a warning rather than on
    the prose of the log line -- the message is wrapped across source lines, so
    matching a phrase in it tests the formatter, not the behaviour.
    """
    src = inspect.getsource(scheduler.execute_marketing_loop)
    assert "daily cap" in src, "the cycle summary does not record the cap"

    window = src[src.index("posts_in_last_24h"):]
    window = window[: window.index("connection = ")]
    assert "logger.warning" in window, "the cap is applied without saying so"


def test_the_cap_defers_rather_than_failing():
    """The workspace is healthy and its interval is honoured again as soon as
    the rolling window clears. This is a delay, not an error."""
    src = inspect.getsource(scheduler.execute_marketing_loop)
    window = src[src.index("posts_in_last_24h"):]
    window = window[: window.index("connection = ")]
    assert "continue" in window
    assert "raise" not in window


@pytest.mark.parametrize("interval,per_day", [(1, 24), (2, 12), (4, 6), (24, 1)])
def test_which_intervals_the_rail_actually_binds(interval, per_day):
    """Documents the real effect: 1h and 2h are throttled, 4h and slower are
    untouched. If this changes, it should change deliberately."""
    bound = per_day > scheduler.MAX_POSTS_PER_DAY
    assert bound == (interval in (1, 2))

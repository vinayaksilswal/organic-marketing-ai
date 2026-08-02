"""When a workspace is due to post.

Two real workspaces were set to publish every 4 hours and published every 6:

    Lumively   20:58 -> 02:58 -> 08:58
    quantcai   21:00 -> 02:59 -> 08:59

The loop ran every 2 hours and compared elapsed time against the interval
exactly. A post's scheduledAt is recorded slightly after the tick that created
it, so at the 4-hour tick elapsed was 3h59m, the comparison failed, and the
workspace slipped to the 6-hour tick. Every setting that was not a multiple of
the loop period drifted the same way, and "every 1 hour" was unreachable at
any setting because the loop never ran that often.
"""

import pytest

from services.scheduler import MARKETING_LOOP_MINUTES, is_post_due


def test_the_six_hour_bug():
    """3h59m into a 4-hour interval is due. Requiring a full 4h is what cost
    these workspaces a whole extra period."""
    assert is_post_due(3.99, 4)


def test_exactly_on_the_interval_is_due():
    assert is_post_due(4.0, 4)


def test_well_short_of_the_interval_is_not_due():
    """The grace absorbs bookkeeping delay; it must not post early."""
    assert not is_post_due(3.0, 4)
    assert not is_post_due(3.5, 4)


@pytest.mark.parametrize("interval", [1, 2, 4, 8, 12, 24])
def test_every_option_in_the_dropdown_is_reachable(interval):
    """The UI offers 1, 2, 4, 8, 12 and 24 hours. A loop that runs every two
    hours cannot honour the first of those at all, so the setting was a lie."""
    assert MARKETING_LOOP_MINUTES <= 60, (
        "the loop must tick at least hourly or 'every 1 hour' is unreachable"
    )
    # Just under the interval, as the drift always leaves it.
    assert is_post_due(interval - (MARKETING_LOOP_MINUTES / 60.0) / 2, interval)
    # A whole tick early is still not due.
    assert not is_post_due(interval - (MARKETING_LOOP_MINUTES / 60.0) * 2, interval)


def test_grace_is_small_relative_to_the_shortest_interval():
    """A grace approaching the interval would post continuously."""
    grace_hours = (MARKETING_LOOP_MINUTES / 60.0) / 2
    assert grace_hours < 1.0 / 4, f"grace of {grace_hours}h is too large for a 1h interval"


def test_never_posted_yet_is_due():
    """A workspace with no history should not wait for a phantom interval."""
    assert is_post_due(10_000.0, 24)


def test_a_negative_interval_does_not_block_forever():
    """Defensive: bad data should degrade to posting, not to silence."""
    assert is_post_due(0.0, 0)

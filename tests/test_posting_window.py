"""A workspace can say WHEN it posts, not only how often.

An interval alone drifts through the whole clock. A 4-hour cadence that starts
at 20:58 posts at 02:58 and 08:58 -- two live workspaces show exactly that
pattern -- so a shop whose customers are asleep gives a third of its output to
nobody.

The window only ever withholds. It never causes a post, because a window that
forced one would fire every workspace at 09:00 sharp, which is the most
obviously automated thing an account can do.
"""

from datetime import datetime, timezone

import pytest

from services import posting_window as pw


class _P:
    def __init__(self, **kw):
        self.postingDays = kw.get("postingDays")
        self.postingStartHour = kw.get("postingStartHour")
        self.postingEndHour = kw.get("postingEndHour")
        self.postingTimezone = kw.get("postingTimezone")


def at(y, m, d, h, tz=timezone.utc):
    return datetime(y, m, d, h, 0, tzinfo=tz)


# =============================================================================
# The default must never restrict anything
# =============================================================================

def test_an_unconfigured_workspace_may_always_post():
    """Every existing workspace has all four fields null. A scheduling feature
    that silently narrows when an account may post is one that silently stops
    it posting."""
    allowed, _ = pw.within_window(_P(), at(2026, 8, 20, 3))
    assert allowed


@pytest.mark.parametrize("days", [None, [], [0, 1, 2, 3, 4, 5, 6]])
def test_no_days_and_all_days_both_mean_no_restriction(days):
    """Empty is what a UI reaches when someone deselects everything. Treating
    it as 'never post' makes silence the default failure."""
    assert pw.normalise_days(days) is None


# =============================================================================
# Days
# =============================================================================

def test_a_weekday_only_workspace_is_held_on_a_sunday():
    # 2026-08-23 is a Sunday.
    weekdays = _P(postingDays=[0, 1, 2, 3, 4])
    allowed, why = pw.within_window(weekdays, at(2026, 8, 23, 12))
    assert not allowed and "Sun" in why


def test_a_weekday_only_workspace_posts_on_a_thursday():
    # 2026-08-20 is a Thursday.
    allowed, _ = pw.within_window(_P(postingDays=[0, 1, 2, 3, 4]), at(2026, 8, 20, 12))
    assert allowed


# =============================================================================
# Hours
# =============================================================================

@pytest.mark.parametrize("hour,expected", [(8, False), (9, True), (17, True), (18, False)])
def test_an_hour_range_is_half_open(hour, expected):
    """Start is inclusive, end exclusive -- 9 to 18 means nine in the morning
    up to but not including six, which is what 'until six' means."""
    p = _P(postingStartHour=9, postingEndHour=18)
    allowed, _ = pw.within_window(p, at(2026, 8, 20, hour))
    assert allowed is expected


@pytest.mark.parametrize("hour,expected", [(21, False), (22, True), (2, True), (6, False)])
def test_a_window_may_wrap_midnight(hour, expected):
    """22:00-06:00 is the normal case for nightlife, delivery, and anything
    selling into another timezone."""
    p = _P(postingStartHour=22, postingEndHour=6)
    allowed, _ = pw.within_window(p, at(2026, 8, 20, hour))
    assert allowed is expected


def test_an_impossible_range_is_ignored_rather_than_enforced():
    """start == end cannot describe a window. Enforcing it would mean either
    always or never, and 'never' silently stops the account."""
    allowed, _ = pw.within_window(_P(postingStartHour=9, postingEndHour=9), at(2026, 8, 20, 3))
    assert allowed


# =============================================================================
# Timezone
# =============================================================================

def test_the_window_is_read_in_the_customer_timezone():
    """'Post between 9 and 6' means nothing without knowing whose 9 and 6.
    03:30 UTC is 09:00 in Kolkata."""
    p = _P(postingStartHour=9, postingEndHour=18, postingTimezone="Asia/Kolkata")
    inside, _ = pw.within_window(p, at(2026, 8, 20, 4))     # 09:30 IST
    outside, _ = pw.within_window(p, at(2026, 8, 20, 20))   # 01:30 IST next day
    assert inside and not outside


def test_a_broken_timezone_does_not_stop_the_account():
    """Withholding every post because a settings string is malformed is a far
    worse failure than posting on the wrong clock."""
    p = _P(postingTimezone="Not/AZone")
    allowed, _ = pw.within_window(p, at(2026, 8, 20, 12))
    assert allowed


# =============================================================================
# It composes with the interval rather than replacing it
# =============================================================================

def test_the_scheduler_checks_the_window_only_after_the_interval():
    """Due-ness still decides. The window is a veto placed after it, so it can
    withhold a post but never manufacture one."""
    import inspect

    from services import scheduler

    src = inspect.getsource(scheduler.execute_marketing_loop)
    assert "within_window" in src, "the loop ignores the posting window"
    assert src.index("is_post_due") < src.index("within_window"), (
        "the window is evaluated before the interval, so it could force a post"
    )


def test_describe_reads_as_a_sentence():
    assert pw.describe(_P()) == "Every day, any time (UTC)"
    p = _P(postingDays=[0, 1, 2, 3, 4], postingStartHour=9, postingEndHour=18,
           postingTimezone="Asia/Kolkata")
    assert pw.describe(p) == "Mon, Tue, Wed, Thu, Fri, 09:00-18:00 (Asia/Kolkata)"

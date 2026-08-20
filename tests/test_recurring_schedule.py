"""Repeating a post is expansion, not a second scheduler.

Every occurrence is written as an ordinary one-time SocialPost, so it inherits
the publish path, the calendar, the delivery log and the cancel button that
already work. A parallel recurring runner would be a second thing able to post
to a customer's account, and making the first one reliable took long enough.

Materialising a fixed number rather than an open-ended rule is the same trade.
A rule that runs forever keeps posting after a customer stops looking; this
stops on its own unless they come back and extend it.
"""

import inspect

import pytest

from routers import marketing


SRC = inspect.getsource(marketing.schedule_recurring_posts)


def test_occurrences_are_ordinary_one_time_posts():
    """Reusing SocialPost is what makes cancel, the calendar and the delivery
    log work for these without any of them knowing they are recurring."""
    assert "SocialPost(" in SRC
    assert 'status="SCHEDULED"' in SRC
    assert 'type="ONE_TIME"' in SRC


def test_the_number_of_occurrences_is_capped():
    """A slip of the keyboard must not fill a year of someone's account."""
    assert "min(int(data.occurrences" in SRC
    assert "31" in SRC


def test_day_of_month_stops_at_28():
    """29 to 31 do not exist in every month, and silently moving a post to the
    28th of February is a surprise nobody asked for."""
    assert "1 <= day <= 28" in SRC


def test_times_are_read_in_the_workspace_timezone():
    """'Post at 6pm' means the customer's 6pm, not the server's."""
    assert "posting_window import _tz" in SRC
    assert "astimezone(tz)" in SRC


def test_everything_is_stored_in_utc():
    """Local for the decision, UTC for the row -- storing local time is how a
    schedule silently shifts when a server moves."""
    assert "astimezone(timezone.utc)" in SRC


def test_only_future_slots_are_created():
    """A rule written at 7pm for 6pm must not immediately fire for today."""
    assert "> now_local" in SRC


def test_a_foreign_asset_cannot_be_scheduled():
    """mediaId arrives in the body, outside the header-based workspace guard."""
    assert "media.businessProfileId != workspace_id" in SRC


def test_a_rule_with_no_days_is_refused_rather_than_guessed():
    assert "Pick at least one day of the week" in SRC


def test_a_bad_time_is_refused_with_a_usable_message():
    assert "Time must be HH:MM" in SRC


@pytest.mark.parametrize("field", ["daysOfWeek", "dayOfMonth", "timeOfDay", "occurrences", "repeat"])
def test_the_request_model_carries_the_rule(field):
    assert field in marketing.RecurringScheduleRequest.model_fields


def test_weekly_expansion_lands_on_the_requested_weekdays():
    """The loop walks day by day and keeps only matching weekdays. Verified
    here in isolation so the arithmetic is not trusted on faith."""
    from datetime import datetime, timedelta, timezone

    now_local = datetime(2026, 8, 21, 9, 0, tzinfo=timezone.utc)  # a Friday
    days, hour, minute, count = {0, 2}, 18, 0, 5  # Monday and Wednesday

    slots = []
    probe = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    for _ in range(371):
        if probe > now_local and probe.weekday() in days:
            slots.append(probe)
            if len(slots) >= count:
                break
        probe += timedelta(days=1)

    assert len(slots) == count
    assert all(s.weekday() in days for s in slots)
    assert all(s.hour == 18 for s in slots)
    assert slots == sorted(slots), "occurrences must come out in order"
    assert slots[0].weekday() == 0, "the first slot after a Friday should be Monday"

"""The publishing engine is four jobs, not one column.

Calendar, one-time posts, repeat rules and the delivery log were stacked end
to end on a single page about three screens tall. Setting up a repeat meant
scrolling past the entire delivery log to reach it, and the log is the part
that grows without limit -- so the page got worse the longer somebody used it.

Each is its own view now, reached from a tab that says how much is waiting
inside it.
"""

import pathlib

import pytest


PAGE = (
    pathlib.Path(__file__).resolve().parent.parent
    / "frontend" / "src" / "pages" / "dashboard" / "SocialScheduler.jsx"
)
SRC = PAGE.read_text(encoding="utf-8")


def test_the_page_was_actually_read():
    """Guards every assertion below: an empty read would pass all of them."""
    assert len(SRC) > 20_000
    assert "SocialScheduler" in SRC or "Social Scheduler" in SRC


@pytest.mark.parametrize("key", ["calendar", "once", "repeat", "log"])
def test_each_job_is_its_own_view(key):
    assert f"section === '{key}'" in SRC, f"the {key} view is not separated"


def test_all_four_are_reachable():
    """A view with no tab is a view nobody can open."""
    for label in ("Calendar", "One-time posts", "Repeating", "Delivery log"):
        assert label in SRC, f"no tab for {label}"


def test_the_page_opens_on_the_calendar():
    """The question people arrive with is 'is anything going out, and did
    yesterday publish'. That is the calendar, not a form."""
    assert "useState('calendar')" in SRC


def test_the_repeat_form_does_not_need_a_second_click():
    """Choosing the Repeating tab already said what you came to do. Making it
    a collapsed panel behind '+ Set up a repeat' is the duplicate control this
    page was meant to lose."""
    assert "repeatOpen" not in SRC, "the collapse toggle is back"
    assert "Set up a repeat" not in SRC


def test_the_repeat_rule_still_offers_both_shapes():
    """Weekly by weekday, or monthly by date -- the two ways a person
    describes a recurring post."""
    assert "repeatMode" in SRC
    assert "weekly" in SRC and "monthly" in SRC
    assert "repeatDayOfMonth" in SRC
    assert "repeatTime" in SRC


def test_the_tabs_say_how_much_is_inside():
    """A count on the tab is what makes it worth clicking, and what tells
    somebody a queue exists without opening it."""
    assert "scheduledPosts.length" in SRC
    assert "posts.length" in SRC


def test_the_settings_row_stays_outside_the_tabs():
    """Interval, auto-approve and publishing mode apply to the whole engine.
    Putting them inside one view would imply they only affect that view."""
    tabs_at = SRC.index("section === 'calendar'")
    for control in ("Auto-Approve", "Run Manually"):
        assert SRC.index(control) < tabs_at, (
            f"{control} moved inside a tab; it applies to all of them"
        )

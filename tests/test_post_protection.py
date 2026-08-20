"""A post that worked is never deleted by automation. Any automation.

post_cleanup was written carefully -- it refuses to judge a post it cannot
measure, will not touch anything under a week old, and caps its own blast
radius. None of that protected a reel that reached four thousand views,
because the thing that deleted it was not post_cleanup.

purge_url_captions matched on caption text and nothing else. No views read, no
threshold, no exemption. It deleted fifty-four posts in one run, and a post
that performed and happened to carry a link was indistinguishable to it from
one that did neither.

So the rule is not "delete underperformers carefully". It is that reach
outranks every other reason to delete, and every path answers to the same
floor.
"""

import inspect
import pathlib

import pytest

from services import post_cleanup, post_protection


# =============================================================================
# The floor itself
# =============================================================================

def test_a_performing_post_is_protected():
    assert post_protection.is_protected(4000) is True
    assert post_protection.is_protected(post_protection.PROTECT_ABOVE_VIEWS) is True


def test_an_unmeasurable_post_is_protected():
    """A post that cannot be measured cannot be shown to have failed, and
    Meta's delete is irreversible."""
    assert post_protection.is_protected(None) is True


def test_a_genuine_failure_is_not_protected():
    """The floor must not be so high that nothing is ever cleaned up."""
    assert post_protection.is_protected(3) is False
    assert post_protection.is_protected(0) is False


def test_the_floor_sits_clear_of_the_underperformance_threshold():
    """A borderline post should not be decided by which rule ran first."""
    assert post_protection.PROTECT_ABOVE_VIEWS >= post_cleanup.MIN_VIEWS * 2


# =============================================================================
# Every path answers to it
# =============================================================================

def test_the_scheduled_cleanup_checks_the_floor():
    src = inspect.getsource(post_cleanup.find_underperformers)
    assert "is_protected(views)" in src
    guard = src.index("is_protected(views)")
    append = src.index("candidates.append")
    assert guard < append, "a protected post can still reach the delete list"


def test_the_url_purge_reads_views_before_deleting():
    """This is the script that cost the four-thousand-view reel. It matched on
    caption text and deleted without ever asking how the post did."""
    src = pathlib.Path("scripts/purge_url_captions.py").read_text(encoding="utf-8")
    assert "is_protected(views)" in src, "the purge still deletes without reading views"
    guard = src.index("is_protected(views)")
    delete = src.index("client.delete(")
    assert guard < delete, "views are checked after the delete call"


def test_the_url_purge_reports_what_it_kept():
    """A run that silently keeps things teaches the operator nothing about
    why the count changed."""
    src = pathlib.Path("scripts/purge_url_captions.py").read_text(encoding="utf-8")
    assert "total_protected" in src
    assert "KEPT" in src


@pytest.mark.parametrize("views", [None, 300, 999, 4000])
def test_no_path_deletes_a_post_at_or_above_the_floor(views):
    assert post_protection.is_protected(views) is True


def test_the_reason_is_stated_rather_than_implied():
    assert "views" in post_protection.refusal_reason(4000)
    assert "could not be read" in post_protection.refusal_reason(None)

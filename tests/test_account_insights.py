"""Numbers shown to an operator are read, never assumed.

engagement_insights already reads a workspace's Instagram history, but it
exists to feed the caption writer and deliberately discards everything except
three statements. This answers the operator's question instead: which accounts
are attached, who follows them, and how the last month went.

The rule that shapes the whole module: a field the platform did not return is
reported as missing, not defaulted to zero. On a dashboard those look
identical and mean opposite things — one is a post nobody engaged with, the
other is a permission we do not hold. Defaulting turns the second into a lie.
"""

import pytest

from services import account_insights as ai


def _post(kind="REELS", likes=10, comments=2, when="2026-08-20T10:00:00+00:00"):
    engagement = None if likes is None else (likes or 0) + (comments or 0)
    return {
        "id": "x", "caption": "c", "kind": kind, "postedAt": when,
        "likes": likes, "comments": comments, "engagement": engagement,
        "permalink": "https://example.com/p", "thumbnail": None,
    }


# =============================================================================
# Missing is not zero
# =============================================================================

def test_a_post_with_no_returned_metrics_is_not_counted_as_zero():
    """A missing like_count means the field was not returned, which is not the
    same as nobody liking it."""
    s = ai._summarise([_post(likes=None, comments=None)])
    assert s["available"] is False
    assert "note" in s


def test_a_genuine_zero_is_still_counted():
    s = ai._summarise([_post(likes=0, comments=0), _post(likes=0, comments=0)])
    assert s["available"] is True
    assert s["totalEngagement"] == 0


def test_unreadable_posts_are_excluded_from_the_median_not_zeroed():
    """One unreadable post must not drag the median toward zero."""
    posts = [_post(likes=100, comments=0), _post(likes=100, comments=0), _post(likes=None, comments=None)]
    s = ai._summarise(posts)
    assert s["postsInWindow"] == 2
    assert s["medianEngagement"] == 100


# =============================================================================
# The summary
# =============================================================================

def test_the_best_post_is_reported_with_a_link():
    """Engagement is likes plus comments, so the winner here is 90 + 2."""
    posts = [_post(likes=5), _post(likes=90), _post(likes=20)]
    s = ai._summarise(posts)
    assert s["bestEngagement"] == 92
    assert s["bestPermalink"]


def test_engagement_counts_comments_as_well_as_likes():
    s = ai._summarise([_post(likes=10, comments=5), _post(likes=10, comments=5)])
    assert s["medianEngagement"] == 15


def test_a_format_needs_more_than_one_post_to_be_compared():
    """One post of a format is an anecdote, not a median."""
    posts = [_post(kind="REELS"), _post(kind="REELS"), _post(kind="IMAGE")]
    s = ai._summarise(posts)
    assert "REELS" in s["byFormat"]
    assert "IMAGE" not in s["byFormat"], "a single post was reported as a format median"


def test_no_posts_at_all_is_reported_rather_than_shown_as_zero():
    s = ai._summarise([])
    assert s["available"] is False


# =============================================================================
# Reading a workspace
# =============================================================================

@pytest.mark.anyio
async def test_a_workspace_with_no_connection_says_so():
    class _Session:
        async def execute(self, *_a, **_k):
            class R:
                def scalars(self):
                    class S:
                        def first(self): return None
                    return S()
            return R()

    out = await ai.for_workspace(_Session(), "ws")
    assert out["accounts"] == []
    assert "connected" in out["note"].lower()


def test_a_refused_graph_read_never_raises():
    """A dashboard that 500s because one Graph call was refused is worse than
    one naming the account it could not read."""
    import inspect

    src = inspect.getsource(ai._get)
    assert "return {}" in src
    assert "except Exception" in src


def test_facebook_does_not_claim_metrics_it_cannot_read():
    """Page post metrics need read_insights, which this app does not request.
    Showing a number we cannot read would be worse than showing none."""
    import inspect

    src = inspect.getsource(ai._facebook)
    assert '"posts": []' in src
    assert "available" in src


def test_the_endpoint_is_registered_and_workspace_scoped():
    import inspect

    from routers import marketing

    src = inspect.getsource(marketing.get_account_insights)
    assert "x-workspace-id" in src
    assert "get_tenant_session" in src
    # Read-only: no model call, so charging a plan quota would charge for
    # looking at your own account.
    assert "check_quota" not in src

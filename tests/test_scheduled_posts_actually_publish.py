"""A scheduled post must not be marked POSTED unless something published.

The scheduler used to branch on FACEBOOK, INSTAGRAM and BOTH only. PostShip
queues TWITTER and LINKEDIN rows. Those matched nothing, collected no errors,
and the status line read an empty error list as success:

    "POSTED" if not errors or fb_post_id or ig_post_id else "FAILED"

So the post was never sent and the customer was told it shipped. A visible
failure gets retried; a false success does not, because nobody goes looking
for a post the dashboard says already went out.

Every test here fails against the old code.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

import services.scheduler as sched


class _Post(SimpleNamespace):
    """Enough of a SocialPost to be published, with no database behind it."""

    def __init__(self, platform, media_urls=None, caption="hello"):
        super().__init__(
            id="p1", businessProfileId="w1", platform=platform,
            mediaUrls=media_urls or [], caption=caption,
            status="SCHEDULED", postedAt=None, errorLog=None,
            fbPostId=None, igPostId=None, twitterPostId=None, linkedinPostId=None,
        )


@pytest.fixture(autouse=True)
def _no_database(monkeypatch):
    """The website lookup must not reach for Neon during a unit test."""
    @asynccontextmanager
    async def _fake():
        raise RuntimeError("no database in tests")
        yield  # pragma: no cover

    monkeypatch.setattr(sched, "AsyncSessionLocal", _fake)


def _run(post):
    asyncio.run(sched._publish_one_scheduled_post(post))
    return post


# ---------------------------------------------------------------------------
# The regression itself
# ---------------------------------------------------------------------------

def test_an_x_post_is_actually_sent_to_x(monkeypatch):
    sent = {}

    class _TW:
        async def post_tweet(self, workspace_id, text, media_urls=None):
            sent["text"] = text
            return "tweet-123"

    monkeypatch.setattr("services.twitter_service.twitter_service", _TW())

    post = _run(_Post("TWITTER"))

    assert sent["text"], "the publisher was never called -- this is the original bug"
    assert post.status == "POSTED"
    assert post.twitterPostId == "tweet-123", "the id was never recorded, so nothing links to the live post"


def test_a_linkedin_post_is_actually_sent_to_linkedin(monkeypatch):
    class _LI:
        async def post_text(self, workspace_id, text):
            return "urn:li:share:9"

    monkeypatch.setattr("services.linkedin_service.linkedin_service", _LI())

    post = _run(_Post("LINKEDIN"))
    assert post.status == "POSTED"
    assert post.linkedinPostId == "urn:li:share:9"


def test_a_platform_nobody_can_publish_is_failed_not_posted():
    """The exact shape of the old bug: no branch matched, no error, POSTED."""
    post = _run(_Post("MASTODON"))

    assert post.status == "FAILED", "an unpublishable post was reported as sent"
    assert "MASTODON" in (post.errorLog or "")


def test_a_publisher_that_raises_produces_FAILED_not_POSTED(monkeypatch):
    class _TW:
        async def post_tweet(self, *a, **k):
            raise RuntimeError("token expired")

    monkeypatch.setattr("services.twitter_service.twitter_service", _TW())

    post = _run(_Post("TWITTER"))
    assert post.status == "FAILED"
    assert "token expired" in post.errorLog


def test_posted_requires_evidence_across_every_platform(monkeypatch):
    """No route through this function reaches POSTED without a published id."""
    class _Boom:
        async def post_tweet(self, *a, **k):
            raise RuntimeError("nope")

        async def post_text(self, *a, **k):
            raise RuntimeError("nope")

    async def _boom(*a, **k):
        raise RuntimeError("nope")

    monkeypatch.setattr("services.twitter_service.twitter_service", _Boom())
    monkeypatch.setattr("services.linkedin_service.linkedin_service", _Boom())
    monkeypatch.setattr("services.social_service.post_to_facebook", _boom)
    monkeypatch.setattr("services.social_service.post_to_instagram", _boom)

    for token in ("FACEBOOK", "INSTAGRAM", "TWITTER", "X", "LINKEDIN", "YOUTUBE", "BOTH", "ALL"):
        post = _run(_Post(token, media_urls=["https://x/a.jpg"]))
        assert post.status == "FAILED", f"{token} reported success with no publish"


# ---------------------------------------------------------------------------
# Platform rules: what cannot be posted, and how that is reported
# ---------------------------------------------------------------------------

def test_instagram_without_media_fails_with_a_reason_a_person_can_act_on(monkeypatch):
    post = _run(_Post("INSTAGRAM", media_urls=[]))

    assert post.status == "FAILED"
    assert "image or video" in post.errorLog, "the reason has to say what to do about it"


def test_youtube_without_a_video_fails_with_a_reason(monkeypatch):
    post = _run(_Post("YOUTUBE", media_urls=["https://x/a.jpg"]))

    assert post.status == "FAILED"
    assert "video" in post.errorLog.lower()


def test_a_text_post_to_ALL_skips_instagram_and_youtube_rather_than_failing(monkeypatch):
    """Their rules make it impossible; that is not this workspace's failure."""
    class _TW:
        async def post_tweet(self, *a, **k):
            return "t1"

    class _LI:
        async def post_text(self, *a, **k):
            return "l1"

    async def _fb(*a, **k):
        return "f1"

    async def _ig(*a, **k):  # pragma: no cover - must never be reached
        raise AssertionError("Instagram was called with no media")

    monkeypatch.setattr("services.twitter_service.twitter_service", _TW())
    monkeypatch.setattr("services.linkedin_service.linkedin_service", _LI())
    monkeypatch.setattr("services.social_service.post_to_facebook", _fb)
    monkeypatch.setattr("services.social_service.post_to_instagram", _ig)

    post = _run(_Post("ALL", media_urls=[]))

    assert post.status == "POSTED"
    assert post.fbPostId == "f1" and post.twitterPostId == "t1" and post.linkedinPostId == "l1"
    assert post.igPostId is None
    # Skips are not errors. A customer who posted text everywhere it could go
    # should not see a red mark for the two places it could not.
    assert post.errorLog is None


def test_one_platform_failing_does_not_discard_the_ones_that_worked(monkeypatch):
    class _TW:
        async def post_tweet(self, *a, **k):
            return "t1"

    class _LI:
        async def post_text(self, *a, **k):
            raise RuntimeError("linkedin down")

    async def _fb(*a, **k):
        return "f1"

    monkeypatch.setattr("services.twitter_service.twitter_service", _TW())
    monkeypatch.setattr("services.linkedin_service.linkedin_service", _LI())
    monkeypatch.setattr("services.social_service.post_to_facebook", _fb)
    monkeypatch.setattr("services.social_service.post_to_instagram", _fb)

    post = _run(_Post("ALL", media_urls=[]))

    assert post.status == "POSTED", "two platforms published; that is not a failed post"
    assert post.twitterPostId == "t1" and post.fbPostId == "f1"
    assert "linkedin down" in post.errorLog, "the partial failure still has to be visible"


# ---------------------------------------------------------------------------
# The queue side: PostShip must not enqueue accounts nobody connected
# ---------------------------------------------------------------------------

def test_postship_only_queues_platforms_that_are_connected():
    """Reads the endpoint's source: the behaviour needs a live database, but
    a row written for an unconnected account is a guaranteed failure and the
    guard against it must not quietly disappear."""
    import pathlib

    src = (pathlib.Path(sched.__file__).parent.parent / "routers" / "creative_api.py").read_text(
        encoding="utf-8", errors="ignore"
    )
    block = src[src.index("# Feed the automatic posting loop."):]
    block = block[: block.index("@router.get")]

    assert "connected_platforms" in block, "posts are queued without checking the account exists"
    assert "available.get(key)" in block
    # Instagram and YouTube cannot take a text-only post.
    assert "INSTAGRAM" not in block and "YOUTUBE" not in block
    # And they must not all fire in the same tick.
    assert "timedelta" in block

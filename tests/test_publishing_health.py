"""A standing publishing failure has to be visible as a state, not a log line.

Two Pages rejected every Facebook post for a fortnight. The reason was
recorded — on individual posts, behind a green POSTED badge, on posts that
were simultaneously succeeding on Instagram. Finding it required reading the
database directly, which is what it took.

The shape of the real failure is reproduced in
test_the_real_facebook_outage_is_reported_correctly: the exact errorLog
string those Pages have been producing, on ALL-platform posts that succeeded
on Instagram.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from services import publishing_health as ph


NOW = datetime.now(timezone.utc)

REAL_ERROR = (
    "facebook: Facebook rejected every attempt — video: Confirm your identity "
    "before you can publish as this Page. Open the Facebook app on your phone and "
    "follow the instructions. [code 368/4854002]"
)


def _post(platform="ALL", *, fb=None, ig=None, x=None, li=None,
          error=None, days=0, status="POSTED"):
    return SimpleNamespace(
        id=f"p{days}", businessProfileId="w1", platform=platform, status=status,
        errorLog=error, createdAt=NOW - timedelta(days=days),
        postedAt=NOW - timedelta(days=days),
        fbPostId=fb, igPostId=ig, twitterPostId=x, linkedinPostId=li,
    )


def _session(posts, connected, last_success=None):
    """A session serving the post scan, then the per-platform last-success
    lookup. The second query is what resolves "last published 17 days ago"."""
    calls = {"n": 0}

    class _Session:
        async def execute(self, *_a, **_k):
            calls["n"] += 1
            first_call = calls["n"] == 1
            return SimpleNamespace(
                scalars=lambda: SimpleNamespace(
                    all=lambda: posts if first_call else [],
                    first=lambda: None if first_call else last_success,
                )
            )

    async def _connected(_s, _w):
        return connected

    return _Session(), _connected


def _run(posts, connected, monkeypatch, last_success=None):
    session, conn = _session(posts, connected, last_success)
    monkeypatch.setattr("services.multi_publisher.connected_platforms", conn)
    return {r["platform"]: r for r in asyncio.run(ph.report(session, "w1"))}


# ---------------------------------------------------------------------------
# The real outage
# ---------------------------------------------------------------------------

def test_the_real_facebook_outage_is_reported_correctly(monkeypatch):
    """The exact production shape: ALL-platform posts, Instagram succeeding,
    Facebook rejected every time with Meta code 368/4854002."""
    posts = [_post(ig=f"ig{i}", error=REAL_ERROR, days=i) for i in range(8)]
    out = _run(posts, {"facebook": True, "instagram": True}, monkeypatch,
               last_success=NOW - timedelta(days=17))

    fb = out["facebook"]
    assert fb["state"] == "action_required"
    assert "rejecting every post" in fb["headline"]
    assert "Confirm your identity" in fb["reason"]
    # The fix, not the error code.
    assert "Facebook app on your phone" in fb["guidance"]
    assert "nothing here needs reconnecting" in fb["guidance"].lower()

    # And Instagram, on the very same posts, must not be dragged down with it.
    assert out["instagram"]["state"] == "healthy"


def test_one_platforms_failure_is_not_attributed_to_another(monkeypatch):
    """A post to five platforms records one errorLog holding every failure.
    Attributing the whole string to each would show LinkedIn broken because
    Facebook was.

    Note the shape: LinkedIn is given NO post id here. An earlier version of
    this test gave every platform an id, and a real id outranks a parsed
    error — so cross-attribution could not show and the test passed against
    deliberately broken code. A platform with no proof of its own is the only
    case where mis-attribution is observable.
    """
    posts = [_post(ig="ig1", error="facebook: identity hold", days=0)]
    out = _run(posts, {"facebook": True, "instagram": True, "linkedin": True}, monkeypatch)

    assert out["facebook"]["state"] == "action_required"
    assert out["instagram"]["state"] == "healthy", "a real post id proves it published"
    assert out["linkedin"]["state"] == "unknown", (
        "LinkedIn was never attempted on this post and is being reported as "
        "broken because Facebook was"
    )


def test_last_success_is_asked_for_not_scanned_for(monkeypatch):
    """A workspace posting every four hours fills the recent-post window in
    under three weeks, so scanning reported "never" for a Page that stopped
    working a fortnight ago. "Never worked" and "stopped working" send
    somebody to completely different places."""
    posts = [_post(ig=f"ig{i}", error=REAL_ERROR, days=i) for i in range(8)]
    out = _run(posts, {"facebook": True}, monkeypatch,
               last_success=NOW - timedelta(days=17))

    assert out["facebook"]["lastSuccess"] is not None, (
        "a Page that published until recently is reporting that it never did"
    )


# ---------------------------------------------------------------------------
# The states
# ---------------------------------------------------------------------------

def test_a_platform_that_just_published_is_healthy(monkeypatch):
    out = _run([_post("FACEBOOK", fb="fb1", days=0)], {"facebook": True}, monkeypatch)
    assert out["facebook"]["state"] == "healthy"


def test_an_untried_platform_is_unknown_not_broken(monkeypatch):
    """Connected but never used is not a fault, and showing it red would send
    somebody to fix a thing that is fine."""
    out = _run([], {"linkedin": True}, monkeypatch)
    assert out["linkedin"]["state"] == "unknown"
    assert out["linkedin"]["reason"] is None


def test_intermittent_failure_is_degraded_not_critical(monkeypatch):
    posts = [
        _post("FACEBOOK", fb="fb1", days=0),
        _post("FACEBOOK", error="facebook: transient", days=1),
        _post("FACEBOOK", fb="fb2", days=2),
    ]
    out = _run(posts, {"facebook": True}, monkeypatch)
    assert out["facebook"]["state"] == "healthy", "the most recent attempt worked"

    posts.insert(0, _post("FACEBOOK", error="facebook: transient", days=0))
    out = _run(posts, {"facebook": True}, monkeypatch)
    assert out["facebook"]["state"] == "degraded", "some worked; this is not a total block"


def test_unconnected_platforms_are_left_out(monkeypatch):
    out = _run([], {"facebook": True, "instagram": False, "x": False}, monkeypatch)
    assert "facebook" in out
    assert "instagram" not in out and "x" not in out


def test_problems_are_listed_before_healthy_accounts(monkeypatch):
    posts = [
        _post("FACEBOOK", error="facebook: identity hold", days=0),
        _post("INSTAGRAM", ig="ig1", days=0),
    ]
    session, conn = _session(posts, {"facebook": True, "instagram": True})
    monkeypatch.setattr("services.multi_publisher.connected_platforms", conn)
    rows = asyncio.run(ph.report(session, "w1"))
    assert rows[0]["platform"] == "facebook", "a healthy account was listed above a broken one"


# ---------------------------------------------------------------------------
# Guidance
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("reason,expected", [
    ("Confirm your identity before you can publish [code 368/4854002]", "Facebook app on your phone"),
    ("OAuthException code 190: access token expired", "Reconnect"),
    ("429 Too Many Requests", "rate-limiting"),
])
def test_known_failures_carry_a_fix(reason, expected):
    assert expected in (ph._guidance(reason) or "")


def test_an_unknown_failure_gets_no_invented_advice():
    """Confident wrong advice in front of somebody mid-problem is worse than
    the platform's own message."""
    assert ph._guidance("something nobody has seen before") is None
    assert ph._guidance("") is None


# ---------------------------------------------------------------------------
# Reachability
# ---------------------------------------------------------------------------

def test_the_endpoint_exists_and_the_interface_calls_it():
    import pathlib

    from routers.api import router

    assert "/api/v1/social/publishing-health" in {r.path for r in router.routes}

    front = pathlib.Path("frontend/src")
    src = "\n".join(f.read_text(encoding="utf-8", errors="ignore")
                    for f in front.rglob("*.jsx"))
    assert "social/publishing-health" in src, "the endpoint exists and nothing calls it"
    assert "<PublishingHealth" in src, "the component exists and no page renders it"


def test_a_healthy_account_shows_nothing_on_the_dashboard():
    """A row of green ticks at the top of a dashboard is furniture, and
    furniture at the top trains people to stop reading the top."""
    import pathlib

    src = pathlib.Path("frontend/src/components/PublishingHealth.jsx").read_text(encoding="utf-8")
    assert "if (shown.length === 0) return null;" in src
    assert "alwaysShow" in src, "no way to show the full list where it is useful"


def test_the_report_never_raises(monkeypatch):
    """It renders at the top of the dashboard. Raising would take the page."""
    async def _boom(*a, **k):
        raise RuntimeError("connections unavailable")

    monkeypatch.setattr("services.multi_publisher.connected_platforms", _boom)

    class _S:
        async def execute(self, *a, **k):
            raise RuntimeError("db down")

    assert asyncio.run(ph.report(_S(), "w1")) == []


# ---------------------------------------------------------------------------
# A requirement that lives only in a test is not enforced
# ---------------------------------------------------------------------------

def test_the_caption_prompt_forbids_narrating_the_visual_with_no_asset():
    """A live smoke test asserted captions must not narrate camera work, and
    nothing in the prompt said so.

    The prohibition existed only in the branch that has a director's brief to
    guard against. A caption with no attached asset is the case where the
    model is MOST likely to invent a scene -- it has nothing to describe, so
    it reaches for "watch the" and "zoom in" to fill the space. The public
    demo always takes that branch, which is why the smoke test kept failing
    intermittently against a rule the model was never given.

    Measured after the fix: 0 trips in 6 live generations.
    """
    import inspect

    import routers.marketing as marketing

    src = inspect.getsource(marketing._generate_post_caption)
    no_asset = src[src.index("No description of the visual is available"):]
    no_asset = no_asset[:900]

    for phrase in ("watch the", "zoom in", "the camera"):
        assert phrase in no_asset.lower(), (
            f"the no-asset branch does not forbid '{phrase}', so only a test "
            "enforces it and the model never hears the rule"
        )
    assert "shot list" in no_asset.lower()

"""Industry news as raw material for daily LinkedIn posts.

The interesting failure here was not a crash. Google News search RSS is
relevance-sorted, not date-sorted, so a bare query returns articles months
old — measured: 62 results, none from the last six months. The 7-day filter
then dropped every one of them and the feature silently returned nothing.

Recency has to be asked for in the query (`when:7d`), not filtered after.
That is what most of these guard.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from services import news_service as ns


PROFILE = SimpleNamespace(
    name="Organiflo", industry="SaaS marketing", businessModel="B2B SaaS",
    targetAudience="founders and small teams who post inconsistently",
    toneOfVoice="direct", country="IN",
)


def _feed(items):
    """A Google News RSS document."""
    body = "".join(
        "<item>"
        f"<title>{t}</title>"
        f"<source url='x'>{s}</source>"
        f"<link>https://news/{i}</link>"
        f"<pubDate>{d}</pubDate>"
        "</item>"
        for i, (t, s, d) in enumerate(items)
    )
    return f"<?xml version='1.0'?><rss><channel>{body}</channel></rss>".encode()


def _rfc(when):
    return when.strftime("%a, %d %b %Y %H:%M:%S GMT")


class _Resp:
    def __init__(self, content, status=200):
        self.content = content
        self.status_code = status


def _patch_feed(monkeypatch, content, capture=None):
    class _Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url, headers=None, **k):
            if capture is not None:
                capture["url"] = url
            return _Resp(content)

    monkeypatch.setattr("services.news_service.httpx.AsyncClient", lambda **k: _Client())


# ---------------------------------------------------------------------------
# The recency bug
# ---------------------------------------------------------------------------

def test_recency_is_requested_in_the_query_not_filtered_afterwards(monkeypatch):
    """This is the bug. Without `when:` the feed returns months-old articles
    and the age filter drops all of them, so the feature returns nothing at
    all rather than failing visibly."""
    capture = {}
    _patch_feed(monkeypatch, _feed([]), capture)

    asyncio.run(ns.fetch(PROFILE))

    assert "when%3A7d" in capture["url"] or "when:7d" in capture["url"], (
        "the query does not ask for recent stories, so old ones come back and "
        "are silently discarded"
    )


def test_old_stories_are_still_dropped_if_they_slip_through(monkeypatch):
    now = datetime.now(timezone.utc)
    _patch_feed(monkeypatch, _feed([
        ("Fresh story", "Reuters", _rfc(now - timedelta(days=1))),
        ("Ancient story", "Reuters", _rfc(now - timedelta(days=90))),
    ]))

    out = asyncio.run(ns.fetch(PROFILE))
    titles = [s["title"] for s in out]

    assert "Fresh story" in titles
    assert "Ancient story" not in titles


# ---------------------------------------------------------------------------
# The query
# ---------------------------------------------------------------------------

def test_the_query_does_not_repeat_words():
    """industry "SaaS marketing" + model "B2B SaaS" produced
    "SaaS marketing B2B SaaS", narrowing the search for no gain."""
    q = ns._query_for(PROFILE)
    words = [w.lower() for w in q.split()]
    assert len(words) == len(set(words)), f"repeated words in query: {q}"


def test_the_audience_is_left_out_of_the_query():
    """It describes who reads the post, not what the news is about. Including
    it made the query so narrow the feed came back empty."""
    q = ns._query_for(PROFILE).lower()
    assert "founders" not in q and "inconsistently" not in q


def test_a_business_with_no_industry_still_gets_a_query():
    bare = SimpleNamespace(name="X", industry=None, businessModel=None)
    assert ns._query_for(bare).strip()


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def test_the_duplicated_source_is_stripped_from_the_title(monkeypatch):
    """Google appends it: "Headline - Reuters", while also providing it
    separately. Left in, every post says the source twice."""
    now = datetime.now(timezone.utc)
    _patch_feed(monkeypatch, _feed([
        ("Big news for SaaS - Reuters", "Reuters", _rfc(now)),
    ]))

    out = asyncio.run(ns.fetch(PROFILE))
    assert out[0]["title"] == "Big news for SaaS"
    assert out[0]["source"] == "Reuters"


def test_stories_already_written_about_are_excluded(monkeypatch):
    """Posting the same headline twice in a week is how an account starts to
    look automated."""
    now = datetime.now(timezone.utc)
    _patch_feed(monkeypatch, _feed([
        ("Already covered", "Reuters", _rfc(now)),
        ("Not yet covered", "Reuters", _rfc(now)),
    ]))

    out = asyncio.run(ns.fetch(PROFILE, exclude_titles=["already covered"]))
    assert [s["title"] for s in out] == ["Not yet covered"]


def test_a_broken_feed_returns_nothing_rather_than_raising(monkeypatch):
    """This runs inside the daily loop. Raising would take the loop with it."""
    _patch_feed(monkeypatch, b"this is not xml at all")
    assert asyncio.run(ns.fetch(PROFILE)) == []


def test_an_http_failure_returns_nothing_rather_than_raising(monkeypatch):
    class _Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, *a, **k):
            raise RuntimeError("network down")

    monkeypatch.setattr("services.news_service.httpx.AsyncClient", lambda **k: _Client())
    assert asyncio.run(ns.fetch(PROFILE)) == []


# ---------------------------------------------------------------------------
# The post
# ---------------------------------------------------------------------------

def test_the_prompt_forbids_inventing_facts():
    """The model is handed a headline and a source, nothing else. Without this
    it fills in figures and quotes that were never in the story — which would
    go out under the customer's name."""
    prompt = ns._post_prompt(PROFILE, {"title": "T", "source": "S", "link": ""},
                             "disagree", "Take the opposite position.")
    low = prompt.lower()
    assert "do not invent" in low
    assert "headline and the source" in low


def test_the_prompt_names_the_linkedin_fold():
    prompt = ns._post_prompt(PROFILE, {"title": "T", "source": "S", "link": ""},
                             "practical", "x")
    assert "210" in prompt, "the model is not told where LinkedIn truncates"


def test_the_post_carries_what_it_is_reacting_to(monkeypatch):
    """A take with no visible source reads as an opinion from nowhere, and
    the customer cannot check it is about something real."""
    async def _fake(prompt, **k):
        return '{"post": "A real opinion about the thing.", "hook": "A real opinion"}'

    monkeypatch.setattr("services.ai_service._call_openrouter", _fake)

    out = asyncio.run(ns.linkedin_post_from_news(
        PROFILE, {"title": "Headline", "source": "Reuters", "link": "https://n/1"},
    ))

    assert out["content"] == "A real opinion about the thing."
    assert out["source_title"] == "Headline"
    assert out["source_name"] == "Reuters"
    assert out["source_link"] == "https://n/1"


def test_angles_rotate_so_a_week_is_not_seven_paraphrases():
    assert len(ns.ANGLES) >= 5
    keys = [a[0] for a in ns.ANGLES]
    assert len(keys) == len(set(keys))

    # The index wraps rather than raising on day 6.
    prompts = {
        ns._post_prompt(PROFILE, {"title": "T", "source": "S", "link": ""},
                        *ns.ANGLES[i % len(ns.ANGLES)])
        for i in range(len(ns.ANGLES) + 2)
    }
    assert len(prompts) == len(ns.ANGLES), "angles are not producing distinct prompts"


def test_a_model_failure_returns_none_rather_than_raising(monkeypatch):
    async def _boom(*a, **k):
        raise RuntimeError("429")

    monkeypatch.setattr("services.ai_service._call_openrouter", _boom)
    out = asyncio.run(ns.linkedin_post_from_news(
        PROFILE, {"title": "T", "source": "S", "link": ""}))
    assert out is None


def test_an_empty_post_is_not_returned_as_a_success(monkeypatch):
    async def _blank(*a, **k):
        return '{"post": "   ", "hook": ""}'

    monkeypatch.setattr("services.ai_service._call_openrouter", _blank)
    assert asyncio.run(ns.linkedin_post_from_news(
        PROFILE, {"title": "T", "source": "S", "link": ""})) is None


# ---------------------------------------------------------------------------
# Reachability
# ---------------------------------------------------------------------------

def test_the_endpoints_exist_and_the_interface_calls_them():
    import pathlib

    from routers.creative_api import router

    paths = {r.path for r in router.routes}
    assert "/api/v1/creatives/news" in paths
    assert "/api/v1/creatives/news-post" in paths

    front = pathlib.Path("frontend/src")
    src = "\n".join(f.read_text(encoding="utf-8", errors="ignore")
                    for f in front.rglob("*.jsx"))
    assert "creatives/news-post" in src, "the endpoint exists and nothing calls it"


def test_a_news_post_is_only_queued_to_linkedin():
    """It is a text post with no image, written in LinkedIn's register.
    Instagram cannot take it at all."""
    import inspect

    import routers.creative_api as mod

    src = inspect.getsource(mod.news_linkedin_post)
    block = src[src.index("if body.schedule_to_queue"):]
    assert 'platform="LINKEDIN"' in block
    assert "INSTAGRAM" not in block
    assert 'available.get("linkedin")' in block, "queued without checking it is connected"


# ---------------------------------------------------------------------------
# The weekly newsletter
# ---------------------------------------------------------------------------

def _draft(**over):
    base = {
        "subject": "The week in SaaS",
        "preheader": "Three things worth knowing",
        "intro": "This week:",
        "outro": "See you next week.",
        "items": [
            {"heading": "One", "body": "Something happened.", "source": "Reuters"},
            {"heading": "Two", "body": "Something else.", "source": "TechCrunch"},
            {"heading": "Three", "body": "A third thing.", "source": "The Verge"},
        ],
    }
    base.update(over)
    import json as _j
    return _j.dumps(base)


def _stories(n):
    return [{"title": f"Story {i}", "source": "Reuters", "link": ""} for i in range(n)]


def test_a_thin_week_produces_no_newsletter_rather_than_a_thin_one(monkeypatch):
    """A "weekly roundup" with one item reads as a business with nothing to
    say, which is worse than not sending at all."""
    async def _never(*a, **k):  # pragma: no cover - must not be reached
        raise AssertionError("the model was called with too few stories")

    monkeypatch.setattr("services.ai_service._call_openrouter", _never)

    out = asyncio.run(ns.weekly_newsletter(PROFILE, stories=_stories(2)))
    assert out is None


def test_a_full_week_produces_a_sendable_draft(monkeypatch):
    async def _fake(*a, **k):
        return _draft()

    monkeypatch.setattr("services.ai_service._call_openrouter", _fake)

    out = asyncio.run(ns.weekly_newsletter(PROFILE, stories=_stories(5)))

    assert out["subject"] == "The week in SaaS"
    assert out["itemCount"] == 3
    assert "<table" in out["html"]
    assert out["text"] and "<" not in out["text"], "the text part must not contain markup"


def test_the_html_is_inline_styled_for_outlook(monkeypatch):
    """Outlook ignores most of a stylesheet. A newsletter that renders broken
    there is one a third of the list never reads."""
    async def _fake(*a, **k):
        return _draft()

    monkeypatch.setattr("services.ai_service._call_openrouter", _fake)
    out = asyncio.run(ns.weekly_newsletter(PROFILE, stories=_stories(4)))

    assert "<style" not in out["html"], "a stylesheet block will be dropped by Outlook"
    assert 'style="' in out["html"]
    assert "cellpadding" in out["html"], "table layout is what survives across clients"


def test_a_plain_text_part_is_always_produced(monkeypatch):
    """HTML with no text alternative is a spam signal."""
    async def _fake(*a, **k):
        return _draft()

    monkeypatch.setattr("services.ai_service._call_openrouter", _fake)
    out = asyncio.run(ns.weekly_newsletter(PROFILE, stories=_stories(4)))

    assert "Reuters" in out["text"]
    assert "One" in out["text"] and "Three" in out["text"]


def test_content_is_escaped_into_the_html(monkeypatch):
    """Model output goes straight into an email body. Unescaped, a headline
    containing markup would break the layout for everyone on the list."""
    async def _fake(*a, **k):
        return _draft(items=[
            {"heading": "<script>alert(1)</script>", "body": "b & c", "source": "s"},
            {"heading": "Two", "body": "x", "source": "s"},
            {"heading": "Three", "body": "y", "source": "s"},
        ])

    monkeypatch.setattr("services.ai_service._call_openrouter", _fake)
    out = asyncio.run(ns.weekly_newsletter(PROFILE, stories=_stories(4)))

    assert "<script>" not in out["html"]
    assert "&lt;script&gt;" in out["html"]
    assert "&amp;" in out["html"]


def test_a_draft_with_no_items_is_not_a_success(monkeypatch):
    async def _fake(*a, **k):
        return _draft(items=[])

    monkeypatch.setattr("services.ai_service._call_openrouter", _fake)
    assert asyncio.run(ns.weekly_newsletter(PROFILE, stories=_stories(4))) is None


def test_the_newsletter_prompt_forbids_invention_and_advertising():
    prompt = ns._newsletter_prompt(PROFILE, _stories(4))
    low = prompt.lower()
    assert "do not invent" in low
    assert "advert" in low, "nothing stops it becoming a product pitch"


def test_the_newsletter_endpoint_exists_and_does_not_send():
    """A newsletter that goes out the instant it is generated is one nobody
    read first."""
    import inspect

    from routers.creative_api import router
    import routers.creative_api as mod

    assert "/api/v1/creatives/newsletter" in {r.path for r in router.routes}

    src = inspect.getsource(mod.weekly_newsletter)
    assert "send_email_blast" not in src and "send_single_email" not in src


# ---------------------------------------------------------------------------
# The daily job
# ---------------------------------------------------------------------------

def test_the_daily_job_is_registered():
    """Built and never scheduled is the failure this codebase keeps making."""
    import inspect

    import services.scheduler as sched

    src = inspect.getsource(sched)
    assert "daily_linkedin_news," in src, "the job exists but nothing runs it"
    assert 'id="daily_linkedin_news"' in src


def test_the_job_checks_linkedin_before_spending_a_model_call():
    """A workspace with no LinkedIn must cost nothing here."""
    import inspect

    import services.scheduler as sched

    src = inspect.getsource(sched.daily_linkedin_news)
    assert src.index('available.get("linkedin")') < src.index("news_service.fetch"), (
        "news is fetched before checking the platform is even connected"
    )


def test_the_job_posts_at_most_once_a_day():
    """The job runs daily, but a restart re-runs it, and two takes on the news
    in one morning reads worse than none."""
    import inspect

    import services.scheduler as sched

    src = inspect.getsource(sched.daily_linkedin_news)
    assert 'type == "NEWS"' in src
    assert "hours=20" in src, "no window guarding against a second run"


def test_one_workspace_failing_does_not_stop_the_others():
    import inspect

    import services.scheduler as sched

    src = inspect.getsource(sched.daily_linkedin_news)
    body = src[src.index("for workspace_id"):]
    assert "except Exception" in body, "one bad workspace takes the whole run down"


def test_the_job_never_raises_into_the_scheduler():
    """A job that throws can take its next run with it."""
    import inspect

    import services.scheduler as sched

    src = inspect.getsource(sched.daily_linkedin_news)
    assert src.rstrip().endswith('logger.error(f"[NEWS] Loop exception: {e}")')

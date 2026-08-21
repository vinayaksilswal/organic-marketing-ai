"""PostShip: one idea, shaped for X, LinkedIn and Reddit.

These tests used to call the live model. That made them a test of the
provider's uptime rather than of this code: they passed on a machine with an
API key and failed in CI without one, so the pipeline went red for a reason
that had nothing to do with the change being tested.

The model is stubbed here. Both paths are covered, because both happen in
production -- the free tier returns 429 often enough that the fallback is not
an edge case, it is the common case.
"""

import json

import pytest

import services.postship_service as ps
from services.postship_service import generate_postship_bundle


GOOD_JSON = json.dumps({
    "x_post": {
        "content": "Shipped writing styles today. The render race is fixed.",
        "metrics_estimate": {"impressions": "2-5k"},
    },
    "linkedin_post": {
        "content": "We shipped writing styles today, and fixed a render race "
                   "that had been biting us for a week.",
        "metrics_estimate": {"impressions": "1-3k"},
    },
    "reddit_post": {
        "title": "Fixed a render race that took a week to find",
        "body": "Here is what it turned out to be.",
        "subreddit": "r/webdev",
    },
})


@pytest.fixture
def model(monkeypatch):
    """Replace the model with something that answers instantly and the same
    way every time."""

    def _set(response: str):
        async def fake(*a, **kw):
            return response

        monkeypatch.setattr(ps, "_call_openrouter", fake)

    return _set


def _assert_shape(bundle):
    """Every field the interface renders. A missing one is a blank card."""
    assert "x_post" in bundle
    assert "linkedin_post" in bundle
    assert "reddit_post" in bundle

    x = bundle["x_post"]
    assert "content" in x
    assert len(x["content"]) > 10
    assert "metrics_estimate" in x

    li = bundle["linkedin_post"]
    assert "content" in li
    assert len(li["content"]) > 15
    assert "metrics_estimate" in li

    rd = bundle["reddit_post"]
    assert "title" in rd
    assert "body" in rd
    assert "subreddit" in rd
    assert rd["subreddit"].startswith("r/")


@pytest.mark.asyncio
async def test_generate_postship_bundle_from_text(model):
    model(GOOD_JSON)
    bundle = await generate_postship_bundle(
        input_text="Fixed the render race, shipped writing styles today.",
        business_name="BuildLog",
        industry="DevTools SaaS",
    )
    _assert_shape(bundle)
    assert "writing styles" in bundle["x_post"]["content"]


@pytest.mark.asyncio
async def test_generate_postship_bundle_from_url(model):
    model(GOOD_JSON)
    bundle = await generate_postship_bundle(
        input_text="Check out our new AI organic social marketing platform",
        url="https://github.com",
        business_name="Organiflo",
        industry="Marketing AI",
    )
    assert bundle["x_post"]["content"] is not None
    assert bundle["linkedin_post"]["content"] is not None
    assert bundle["reddit_post"]["title"] is not None


@pytest.mark.asyncio
async def test_a_fenced_reply_is_still_read(model):
    """Models wrap JSON in ``` fences constantly. Treating that as a parse
    failure would throw away a perfectly good answer."""
    model(f"```json\n{GOOD_JSON}\n```")
    bundle = await generate_postship_bundle(
        input_text="Shipped something", business_name="BuildLog"
    )
    _assert_shape(bundle)
    assert "writing styles" in bundle["x_post"]["content"]


@pytest.mark.asyncio
async def test_junk_from_the_model_still_produces_a_usable_bundle(model):
    """The customer gets a bundle they can edit, not an error page. This is
    the path a rate-limited free tier takes."""
    model("I'm sorry, I can't help with that.")
    bundle = await generate_postship_bundle(
        input_text="Shipped writing styles today.", business_name="BuildLog"
    )
    _assert_shape(bundle)


@pytest.mark.asyncio
async def test_an_empty_reply_still_produces_a_usable_bundle(model):
    model("")
    bundle = await generate_postship_bundle(
        input_text="Shipped writing styles today.", business_name="BuildLog"
    )
    _assert_shape(bundle)

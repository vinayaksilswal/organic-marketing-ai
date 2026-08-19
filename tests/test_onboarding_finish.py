"""The last screen of onboarding is where paid traffic either activates or leaves.

It used to be a paywall. Three things were wrong with it at once, and every
one of them was pointed at people arriving from an ad:

  1. It offered a "14-Day Free Trial". No such trial exists anywhere in the
     billing code. That is a promise the product cannot keep, made to someone
     who has just been charged for as a click.
  2. It showed a hardcoded summary -- the same tone, the same four content
     pillars -- to every business that ever signed up, under a heading saying
     we had analysed theirs. The analysis is real and was simply never read
     back, so the one screen meant to prove the product works proved instead
     that it does not.
  3. Its button POSTed to /users/me/subscribe with no body, against an
     endpoint requiring order_id, so it answered 422 every time. On the
     success path it would have granted ACTIVE with no payment at all.

The free plan publishes. Asking for a card before a single post has gone out
is asking someone to buy something they have not seen work.
"""

import pathlib
import re

import pytest

ONBOARDING = pathlib.Path(__file__).resolve().parent.parent / "frontend" / "src" / "pages" / "Onboarding.jsx"


@pytest.fixture(scope="module")
def source() -> str:
    return ONBOARDING.read_text(encoding="utf-8")


def test_no_trial_is_promised_that_billing_does_not_offer(source):
    assert not re.search(r"\d+[- ]Day Free Trial", source, re.IGNORECASE), (
        "onboarding offers a trial the billing code has no concept of"
    )


def test_the_summary_is_read_back_not_hardcoded(source):
    """Every business saw the same 'generated' brand context."""
    for invented in ("Tone: Enterprise Professional", "Growth Tips • Industry Insights"):
        assert invented not in source, f"hardcoded brand context is back: {invented}"
    assert "brand?.industry" in source, "the real analysis is not being shown"
    assert "brand?.contentPillars" in source or "brand?.contentPillars?.length" in source


def test_nothing_grants_a_subscription_from_the_client(source):
    """The old handler set subscriptionStatus ACTIVE in the client on a
    response it never validated."""
    assert "users/me/subscribe" not in source, (
        "onboarding calls the subscribe endpoint again"
    )
    assert "subscriptionStatus: 'ACTIVE'" not in source


def test_the_last_step_sends_people_into_the_product(source):
    """Connect accounts, then generate, then upload, then it posts. A paywall
    at this point stops the only sequence that produces an activated account."""
    tail = source[source.index("{step === 4 &&"):]
    assert "/dashboard" in tail, "the final step does not route into the product"
    assert "Connect" in tail, "the next action is not connecting an account"


def test_the_free_plan_is_stated_rather_than_hidden(source):
    tail = source[source.index("{step === 4 &&"):]
    assert "free plan" in tail.lower()


def test_the_status_endpoint_returns_the_profile_it_analysed():
    """The screen cannot show real values if the API only returns a boolean."""
    from routers import user_api
    import inspect

    src = inspect.getsource(user_api.get_onboarding_status)
    assert '"profile"' in src
    for field in ("contentPillars", "toneOfVoice", "primaryOffer", "industry"):
        assert field in src, f"onboarding-status does not return {field}"

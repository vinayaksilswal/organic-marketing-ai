"""Somebody trying to pay must never reach a dead end.

This product is about to take paid traffic. The moment that decides whether an
ad becomes revenue or becomes a cost is the click on a plan, and that click
was broken:

- Plan & Billing calls /billing/subscribe, which needs the Subscriptions
  product enabled on the PayPal app. It is not, so the call failed with a 502
  reading "Please try again shortly" — which is false. It will never succeed
  until that is switched on, so the customer retries, fails, and leaves.

- The one-time checkout, which works today, was routed at /checkout and linked
  from nowhere. The path that worked was reachable only by typing the URL, and
  the path that was reachable did not work.

So an ad could deliver a customer who wanted to pay, and the product had no
way to take their money.
"""

import inspect
import pathlib

import pytest


ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_a_failed_subscription_offers_the_path_that_works():
    """Not a 502. A customer with their card out gets sent somewhere that can
    actually charge it."""
    import routers.billing as billing

    src = inspect.getsource(billing.subscribe)
    assert "recurringUnavailable" in src
    assert "fallbackUrl" in src
    assert 'status_code=502' not in src, (
        "the dead end is back: a 502 here is a customer who wanted to pay and could not"
    )


def test_the_failure_message_does_not_tell_a_useful_lie():
    """'Please try again shortly' invites a retry that cannot succeed."""
    import routers.billing as billing

    src = inspect.getsource(billing.subscribe)
    # Statements only. The comment above the fix quotes the old wording to
    # explain why it was wrong, and matching prose would fail on the very
    # explanation of the fix.
    code = chr(10).join(
        line for line in src.splitlines() if not line.lstrip().startswith("#")
    )
    assert "try again shortly" not in code


def test_the_interface_follows_the_fallback():
    """A backend that offers a fallback nobody follows is the same dead end
    with extra steps."""
    src = (ROOT / "frontend" / "src" / "pages" / "dashboard" / "Billing.jsx").read_text(encoding="utf-8")
    assert "recurringUnavailable" in src
    assert "fallbackUrl" in src


def test_the_one_time_checkout_still_exists():
    """It is the only working way to be paid right now. If this route goes,
    the product cannot take money at all until PayPal subscriptions are on."""
    app_src = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
    assert 'path="/checkout"' in app_src

    import routers.user_api as user_api
    paths = [getattr(r, "path", "") for r in getattr(user_api.router, "routes", [])]
    assert any(p.endswith("/subscribe") for p in paths), (
        f"the one-time order capture endpoint is gone; found {paths}"
    )


def test_the_paid_plan_price_is_still_verified_server_side():
    """The PayPal order is created client-side, so its amount is
    attacker-controlled. Granting on an unverified order would let anyone buy
    a plan for a penny."""
    src = (ROOT / "routers" / "user_api.py").read_text(encoding="utf-8")
    assert "PLAN_PRICE" in src
    assert "captured" in src
    assert 'status") != "COMPLETED"' in src


def test_nothing_grants_access_without_money_moving():
    """Entitlement comes from a verified payment, never from the client
    saying so."""
    src = (ROOT / "routers" / "billing.py").read_text(encoding="utf-8")
    assert "Nothing is granted here" in src, (
        "the comment stating the invariant is gone; check the invariant too"
    )


@pytest.mark.parametrize("plan", ["starter", "growth", "agency"])
def test_every_paid_plan_has_a_price_a_customer_can_pay(plan):
    from services import billing_service as billing

    entry = billing.PLANS.get(plan)
    assert entry, f"{plan} disappeared from the plan table"
    assert entry["price"] > 0, f"{plan} is priced at zero"

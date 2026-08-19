"""Paying has to actually grant the plan that was paid for.

Two different things record "this account paid". User.subscriptionStatus is a
boolean that predates recurring billing; the Subscription row carries the plan
and the period end, and it is the one every limit in the product reads through
active_plan_code().

The one-time order path set only the first. A customer could pay $17, be
marked ACTIVE, and still be held to the free plan's 5 posts and 10 media --
they would have paid for nothing, and the first they would hear of it is a
quota message telling them to upgrade.

This matters more than usual right now: the live PayPal app has no
subscription scopes, so one-time orders are the only way money can reach this
product at all.
"""

import inspect

from routers import user_api
from services import billing_service as billing


def test_paying_writes_a_subscription_row():
    """User.subscriptionStatus alone does not lift a single limit."""
    src = inspect.getsource(user_api.activate_subscription)
    assert "Subscription(" in src, (
        "a completed order no longer creates the row that grants the plan"
    )
    assert 'sub.planCode = "starter"' in src


def test_the_granted_plan_is_one_that_exists_and_lifts_limits():
    starter = billing.PLANS["starter"]["limits"]
    free = billing.PLANS["free"]["limits"]
    for metric in ("posts", "prompts", "media"):
        assert starter[metric] > free[metric], (
            f"starter does not give more {metric} than free"
        )


def test_a_one_off_payment_buys_a_window_not_forever():
    """An order is not a recurring subscription. Without a period end, one $17
    payment in March is indistinguishable from an active customer in December."""
    src = inspect.getsource(user_api.activate_subscription)
    assert "currentPeriodEnd" in src
    assert "timedelta(days=31)" in src


def test_the_window_closes_by_itself():
    """active_plan_code falls back to free on a lapsed period, so nothing has
    to run on a schedule to end the grant."""
    src = inspect.getsource(billing.active_plan_code)
    assert "currentPeriodEnd" in src
    assert "DEFAULT_PLAN" in src
    assert "lapsed" in src.lower()


def test_a_one_off_grant_does_not_claim_it_will_renew():
    """Nothing will charge this card again. Presenting it as renewing is a
    promise the payment method cannot keep."""
    src = inspect.getsource(user_api.activate_subscription)
    assert "cancelAtPeriodEnd = True" in src


def test_the_payment_is_still_verified_before_anything_is_granted():
    """The order is built client-side, so the amount on it is
    attacker-controlled. Guard rails must sit ahead of the grant."""
    src = inspect.getsource(user_api.activate_subscription)
    grant = src.index("sub.planCode")
    for guard in ("COMPLETED", "PLAN_CURRENCY", "paypalOrderId"):
        assert guard in src, f"lost the {guard} check"
        assert src.index(guard) < grant, f"{guard} is checked after the plan is granted"

"""Unlimited accounts bypass metering; everyone else is told why they stopped.

Two separate powers used to be the same switch. isSuperAdmin made an account
unlimited, but it also grants access across other tenants -- so the only way to
lift a customer's cap was to hand them the keys to everyone else's data. The
enterprise plan exists for exactly this: granted, never purchasable, every
limit null.

The daily posting rail is exempted too. It protects customers who did not
choose their cadence from a risk they cannot see; an operator running their own
brands, or an enterprise account under a negotiated contract, has accepted that
trade knowingly.
"""

import inspect

import pytest

from services import billing_service as billing


def test_enterprise_has_no_limits_at_all():
    limits = billing.PLANS["enterprise"]["limits"]
    assert limits, "the enterprise plan has no limits block"
    assert all(v is None for v in limits.values()), (
        f"enterprise still caps something: "
        f"{[k for k, v in limits.items() if v is not None]}"
    )


def test_unlimited_is_reachable_without_super_admin():
    """Lifting a cap should not require granting cross-tenant access."""
    src = inspect.getsource(billing._is_unlimited)
    assert "active_plan_code" in src, (
        "unlimited still depends solely on the super-admin flag"
    )
    assert "isSuperAdmin" in src, "the operator's own bypass was removed"


def test_enterprise_is_granted_not_purchasable():
    assert "enterprise" not in billing.PAID_PLANS
    assert billing.PLANS["enterprise"].get("hidden") is True


@pytest.mark.parametrize("code", ["free", "starter", "growth"])
def test_metered_plans_still_cap_posts(code):
    """The bypass must not leak into the plans that pay for the product."""
    assert billing.PLANS[code]["limits"]["posts"] is not None


def test_a_capped_customer_is_told_what_happened_and_what_to_do():
    """"Nothing posted today" with no reason is a support ticket. The message
    has to name the limit, the plan, and the way out."""
    src = inspect.getsource(billing.check_quota)
    assert "You have used all" in src
    assert "plan" in src and "Upgrade" in src


def test_the_daily_rail_exempts_unlimited_accounts():
    import services.scheduler as sched

    src = inspect.getsource(sched.execute_marketing_loop)
    assert "_is_unlimited" in src, (
        "the safety rail still throttles accounts that have opted out of it"
    )
    exempt = src.index("_is_unlimited")
    check = src.index("published_today >=")
    assert exempt < check, "the exemption is evaluated after the rail is applied"


def test_the_rail_still_applies_to_ordinary_accounts():
    """Removing it for everyone would trade a customer's reach for nothing."""
    import services.scheduler as sched

    src = inspect.getsource(sched.execute_marketing_loop)
    assert "MAX_POSTS_PER_DAY" in src
    assert "daily cap" in src


def test_a_metering_failure_does_not_grant_unlimited():
    """A database blip must not silently make every account unlimited -- that
    is the whole product given away by an outage."""
    src = inspect.getsource(billing._is_unlimited)
    tail = src[src.index("except Exception"):]
    assert "return False" in tail, (
        "a failed lookup falls through to unlimited rather than to the plan"
    )

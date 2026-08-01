"""
=============================================================================
Organic Marketing AI — Billing (PayPal recurring subscriptions + metering)
=============================================================================
Checkout previously took a one-time $17 PayPal ORDER and set
User.subscriptionStatus = "ACTIVE" permanently. Nothing renewed, nothing
lapsed, and a customer who paid once in March looked identical to one paying
every month.

This module owns:
  - the plan catalogue and its per-tier limits
  - PayPal product/plan provisioning (idempotent, done once on demand)
  - subscription creation, lookup and cancellation
  - monthly usage metering and quota checks

Quotas are counted, not derived. Deleting a post must not refund the AI call
that produced it, and changing plan must not rewrite last month's usage.
=============================================================================
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from loguru import logger
from sqlalchemy import select

from config import settings
from database import AsyncSessionLocal, Subscription, UsageCounter

# =============================================================================
# Plan catalogue
# =============================================================================
# limit of None means unlimited. Metrics are counted per billing month.
PLANS: dict[str, dict[str, Any]] = {
    "free": {
        "code": "free",
        "name": "Free",
        "price": 0.0,
        "tagline": "Try the whole pipeline before you pay.",
        "features": [
            "1 business",
            "5 published posts a month",
            "3 AI creative prompts a month",
            "Facebook + Instagram publishing",
        ],
        "limits": {"businesses": 1, "posts": 5, "prompts": 3, "emails": 0, "media": 10},
    },
    "starter": {
        "code": "starter",
        "name": "Starter",
        "price": 17.0,
        "tagline": "One business, running itself.",
        "features": [
            "1 business",
            "60 published posts a month",
            "30 AI creative prompts a month",
            "1,000 marketing emails a month",
            "Automated posting every 2 hours",
        ],
        "limits": {"businesses": 1, "posts": 60, "prompts": 30, "emails": 1000, "media": 200},
    },
    "growth": {
        "code": "growth",
        "name": "Growth",
        "price": 49.0,
        "tagline": "Several brands, one operator.",
        "features": [
            "5 businesses",
            "300 published posts a month",
            "150 AI creative prompts a month",
            "10,000 marketing emails a month",
            "Your own email sending domain",
        ],
        "limits": {"businesses": 5, "posts": 300, "prompts": 150, "emails": 10000, "media": 1000},
    },
    "agency": {
        "code": "agency",
        "name": "Agency",
        "price": 149.0,
        "tagline": "Run marketing for clients.",
        "features": [
            "25 businesses",
            "Unlimited published posts",
            "600 AI creative prompts a month",
            "50,000 marketing emails a month",
            "Team seats and roles",
        ],
        "limits": {"businesses": 25, "posts": None, "prompts": 600, "emails": 50000, "media": None},
    },
    # Everything uncapped. Two uses: a negotiated contract that does not fit a
    # self-serve tier, and the operator's own account — running the platform
    # should not mean paying yourself through PayPal to use it.
    #
    # Deliberately not in PAID_PLANS, so it never appears in the public pricing
    # table and cannot be self-selected at checkout. It is granted, not bought.
    "enterprise": {
        "code": "enterprise",
        "name": "Enterprise",
        # price 0.0 rendered as "Free" on the pricing table, which reads as the
        # cheapest tier rather than the most expensive one. `custom` tells the
        # frontend to show "Custom" and a contact button instead of a number.
        "price": 0.0,
        "custom": True,
        "cta": "Contact us",
        "tagline": "Unlimited, priced to your volume.",
        "features": [
            "Unlimited businesses",
            "Unlimited published posts",
            "Unlimited AI creative prompts",
            "Unlimited marketing emails",
            "Team seats and roles",
            "Priority support",
        ],
        "limits": {
            "businesses": None, "posts": None, "prompts": None,
            "emails": None, "media": None,
        },
        "hidden": True,
    },
}

DEFAULT_PLAN = "free"
# Purchasable tiers. Enterprise is excluded by price and by the hidden flag —
# it is granted, never checked out.
PAID_PLANS = [
    c for c in PLANS
    if PLANS[c]["price"] > 0 and not PLANS[c].get("hidden")
]
PUBLIC_PLANS = [c for c in PLANS if not PLANS[c].get("hidden")]

METRIC_LABELS = {
    "posts": "published posts",
    "prompts": "AI creative prompts",
    "emails": "marketing emails",
    "media": "media uploads",
    "businesses": "businesses",
}


def _paypal_base() -> str:
    return (
        "https://api-m.paypal.com"
        if settings.environment == "production"
        else "https://api-m.sandbox.paypal.com"
    )


def current_period() -> str:
    """The billing month key, e.g. '2026-07'."""
    now = datetime.now(timezone.utc)
    return f"{now.year:04d}-{now.month:02d}"


def plan_for(code: Optional[str]) -> dict[str, Any]:
    return PLANS.get((code or "").lower(), PLANS[DEFAULT_PLAN])


# =============================================================================
# PayPal REST helpers
# =============================================================================
async def _paypal_token(client: httpx.AsyncClient) -> Optional[str]:
    if not settings.paypal_client_id or not settings.paypal_client_secret:
        logger.error("PayPal credentials are not configured")
        return None
    resp = await client.post(
        f"{_paypal_base()}/v1/oauth2/token",
        data={"grant_type": "client_credentials"},
        auth=(settings.paypal_client_id, settings.paypal_client_secret),
    )
    if resp.status_code != 200:
        logger.error(f"PayPal auth failed: {resp.status_code} {resp.text[:200]}")
        return None
    return resp.json().get("access_token")


# Cached per process. Creating the product/plan is idempotent via
# PayPal-Request-Id, but re-checking on every call would be wasteful.
_PLAN_ID_CACHE: dict[str, str] = {}


async def ensure_paypal_plan(plan_code: str) -> Optional[str]:
    """Return the PayPal billing plan id for one of our plans, creating it once.

    PayPal-Request-Id makes both calls idempotent, so a retry or a second
    worker cannot create duplicate products or plans.
    """
    plan = PLANS.get(plan_code)
    if not plan or plan["price"] <= 0:
        return None
    if plan_code in _PLAN_ID_CACHE:
        return _PLAN_ID_CACHE[plan_code]

    async with httpx.AsyncClient(timeout=30.0) as client:
        token = await _paypal_token(client)
        if not token:
            return None
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        product_resp = await client.post(
            f"{_paypal_base()}/v1/catalogs/products",
            headers={**headers, "PayPal-Request-Id": "organicai-product-v1"},
            json={
                "id": "ORGANICAI-SAAS",
                "name": "Organic Marketing AI",
                "description": "Automated organic marketing for businesses",
                "type": "SERVICE",
                "category": "SOFTWARE",
            },
        )
        if product_resp.status_code not in (200, 201):
            # 422 with DUPLICATE_RESOURCE_IDENTIFIER means it already exists.
            if "DUPLICATE" not in product_resp.text.upper():
                logger.error(f"PayPal product creation failed: {product_resp.text[:300]}")
                return None
        product_id = "ORGANICAI-SAAS"

        plan_resp = await client.post(
            f"{_paypal_base()}/v1/billing/plans",
            headers={**headers, "PayPal-Request-Id": f"organicai-plan-{plan_code}-v1"},
            json={
                "product_id": product_id,
                "name": f"Organic Marketing AI — {plan['name']}",
                "description": plan["tagline"],
                "status": "ACTIVE",
                "billing_cycles": [
                    {
                        "frequency": {"interval_unit": "MONTH", "interval_count": 1},
                        "tenure_type": "REGULAR",
                        "sequence": 1,
                        "total_cycles": 0,  # 0 = renew forever
                        "pricing_scheme": {
                            "fixed_price": {
                                "value": f"{plan['price']:.2f}",
                                "currency_code": "USD",
                            }
                        },
                    }
                ],
                "payment_preferences": {
                    "auto_bill_outstanding": True,
                    "setup_fee_failure_action": "CONTINUE",
                    "payment_failure_threshold": 2,
                },
            },
        )
        if plan_resp.status_code in (200, 201):
            plan_id = plan_resp.json().get("id")
            if plan_id:
                _PLAN_ID_CACHE[plan_code] = plan_id
                logger.info(f"PayPal plan ready for {plan_code}: {plan_id}")
                return plan_id

        # Already created on a previous boot — find it by name.
        list_resp = await client.get(
            f"{_paypal_base()}/v1/billing/plans",
            headers=headers,
            params={"product_id": product_id, "page_size": 20},
        )
        if list_resp.status_code == 200:
            for p in list_resp.json().get("plans", []):
                if p.get("name", "").endswith(plan["name"]):
                    _PLAN_ID_CACHE[plan_code] = p["id"]
                    return p["id"]

        logger.error(f"Could not provision PayPal plan for {plan_code}: {plan_resp.text[:300]}")
        return None


async def create_paypal_subscription(
    user_id: str, user_email: str, plan_code: str, return_url: str, cancel_url: str
) -> Optional[dict[str, Any]]:
    """Create a subscription and return its id plus the approval URL."""
    paypal_plan_id = await ensure_paypal_plan(plan_code)
    if not paypal_plan_id:
        return None

    async with httpx.AsyncClient(timeout=30.0) as client:
        token = await _paypal_token(client)
        if not token:
            return None
        resp = await client.post(
            f"{_paypal_base()}/v1/billing/subscriptions",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "plan_id": paypal_plan_id,
                # custom_id is what the webhook uses to find the user.
                "custom_id": user_id,
                "subscriber": {"email_address": user_email},
                "application_context": {
                    "brand_name": "Organic Marketing AI",
                    "user_action": "SUBSCRIBE_NOW",
                    "shipping_preference": "NO_SHIPPING",
                    "payment_method": {
                        "payer_selected": "PAYPAL",
                        "payee_preferred": "IMMEDIATE_PAYMENT_REQUIRED",
                    },
                    "return_url": return_url,
                    "cancel_url": cancel_url,
                },
            },
        )
        if resp.status_code not in (200, 201):
            logger.error(f"PayPal subscription creation failed: {resp.text[:300]}")
            return None

        body = resp.json()
        approve = next(
            (l["href"] for l in body.get("links", []) if l.get("rel") == "approve"), None
        )
        return {
            "subscriptionId": body.get("id"),
            "paypalPlanId": paypal_plan_id,
            "approveUrl": approve,
            "status": body.get("status"),
        }


async def fetch_paypal_subscription(subscription_id: str) -> Optional[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        token = await _paypal_token(client)
        if not token:
            return None
        resp = await client.get(
            f"{_paypal_base()}/v1/billing/subscriptions/{subscription_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code != 200:
            logger.warning(f"PayPal subscription lookup failed: {resp.text[:200]}")
            return None
        return resp.json()


async def cancel_paypal_subscription(subscription_id: str, reason: str = "User requested") -> bool:
    async with httpx.AsyncClient(timeout=30.0) as client:
        token = await _paypal_token(client)
        if not token:
            return False
        resp = await client.post(
            f"{_paypal_base()}/v1/billing/subscriptions/{subscription_id}/cancel",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"reason": reason[:127]},
        )
        if resp.status_code not in (204, 200):
            logger.error(f"PayPal cancellation failed: {resp.status_code} {resp.text[:200]}")
            return False
        return True


# =============================================================================
# Subscription state
# =============================================================================
async def get_subscription(user_id: str) -> Optional[Subscription]:
    async with AsyncSessionLocal() as session:
        return (await session.execute(
            select(Subscription)
            .where(Subscription.userId == user_id)
            .order_by(Subscription.createdAt.desc())
        )).scalars().first()


async def active_plan_code(user_id: str) -> str:
    """The plan a user is entitled to right now.

    A subscription that has lapsed past its period end is not active, however
    it is labelled — otherwise a failed renewal grants service forever.
    """
    sub = await get_subscription(user_id)
    if not sub or sub.status != "ACTIVE":
        return DEFAULT_PLAN
    if sub.currentPeriodEnd:
        end = sub.currentPeriodEnd
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        if end < datetime.now(timezone.utc):
            logger.info(f"Subscription for {user_id} lapsed at {end}; falling back to free")
            return DEFAULT_PLAN
    return sub.planCode or DEFAULT_PLAN


# =============================================================================
# Metering
# =============================================================================
async def get_usage(user_id: str) -> dict[str, int]:
    period = current_period()
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(UsageCounter).where(
                UsageCounter.userId == user_id,
                UsageCounter.periodStart == period,
            )
        )).scalars().all()
    return {r.metric: r.count for r in rows}


async def record_usage(user_id: str, metric: str, amount: int = 1) -> None:
    """Increment a meter. Never raises — metering must not break the feature."""
    if not user_id or amount <= 0:
        return
    period = current_period()
    try:
        async with AsyncSessionLocal() as session:
            row = (await session.execute(
                select(UsageCounter).where(
                    UsageCounter.userId == user_id,
                    UsageCounter.metric == metric,
                    UsageCounter.periodStart == period,
                )
            )).scalars().first()
            if row:
                row.count = (row.count or 0) + amount
            else:
                session.add(UsageCounter(
                    userId=user_id, metric=metric, periodStart=period, count=amount
                ))
            await session.commit()
    except Exception as e:
        logger.warning(f"Could not record usage {metric} for {user_id}: {e}")


async def _is_unlimited(user_id: str) -> bool:
    """Whether this account bypasses metering entirely.

    User.isSuperAdmin has existed since the first schema and nothing ever read
    it. Honouring it here means the operator can run their own businesses on
    the platform without buying a subscription from themselves, and support can
    lift a cap during an incident without touching PayPal.
    """
    from database import AsyncSessionLocal, User

    try:
        async with AsyncSessionLocal() as session:
            user = await session.get(User, user_id)
            return bool(user and getattr(user, "isSuperAdmin", False))
    except Exception as e:
        # Metering must not be the thing that takes the product down. A failed
        # lookup falls through to the normal plan check rather than raising.
        logger.warning(f"Could not read super-admin flag for {user_id}: {e}")
        return False


async def check_quota(user_id: str, metric: str, amount: int = 1) -> tuple[bool, str]:
    """(allowed, message). Message is user-facing when not allowed."""
    if await _is_unlimited(user_id):
        return True, ""
    plan = plan_for(await active_plan_code(user_id))
    limit = plan["limits"].get(metric)
    if limit is None:
        return True, ""

    used = (await get_usage(user_id)).get(metric, 0)
    if used + amount <= limit:
        return True, ""

    label = METRIC_LABELS.get(metric, metric)
    return False, (
        f"You have used all {limit} {label} included in the {plan['name']} plan "
        f"this month. Upgrade to keep going."
    )


async def check_business_quota(user_id: str, current_count: int) -> tuple[bool, str]:
    """Businesses are a standing total, not a monthly meter."""
    if await _is_unlimited(user_id):
        return True, ""
    plan = plan_for(await active_plan_code(user_id))
    limit = plan["limits"].get("businesses")
    if limit is None or current_count < limit:
        return True, ""
    return False, (
        f"The {plan['name']} plan includes {limit} "
        f"business{'es' if limit != 1 else ''}. Upgrade to add more."
    )


async def billing_summary(user_id: str) -> dict[str, Any]:
    """Everything the billing screen needs in one call."""
    sub = await get_subscription(user_id)
    code = await active_plan_code(user_id)
    plan = plan_for(code)
    usage = await get_usage(user_id)

    return {
        "plan": {
            "code": plan["code"],
            "name": plan["name"],
            "price": plan["price"],
            "tagline": plan["tagline"],
            "features": plan["features"],
            "limits": plan["limits"],
        },
        "subscription": {
            "status": sub.status if sub else "NONE",
            "planCode": sub.planCode if sub else None,
            "currentPeriodEnd": (
                sub.currentPeriodEnd.isoformat() if sub and sub.currentPeriodEnd else None
            ),
            "cancelAtPeriodEnd": sub.cancelAtPeriodEnd if sub else False,
            "lastPaymentAt": (
                sub.lastPaymentAt.isoformat() if sub and sub.lastPaymentAt else None
            ),
            "lastError": sub.lastError if sub else None,
        } if sub else {"status": "NONE"},
        "usage": {
            m: {
                "used": usage.get(m, 0),
                "limit": plan["limits"].get(m),
                "label": METRIC_LABELS.get(m, m),
            }
            for m in ("posts", "prompts", "emails", "media")
        },
        "period": current_period(),
    }

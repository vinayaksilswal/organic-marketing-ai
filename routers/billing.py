"""
=============================================================================
Organic Marketing AI — Billing Router
=============================================================================
Plans, subscription lifecycle and usage. The PayPal webhook lives in
routers/paypal_webhook.py; this router is what the dashboard talks to.
=============================================================================
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select

from config import settings
from database import AsyncSessionLocal, Subscription, User
from routers.auth import verify_user
from services import billing_service as billing

router = APIRouter(prefix="/api/v1/billing", tags=["Billing"])


class SubscribeRequest(BaseModel):
    planCode: str


@router.get("/plans")
async def list_plans() -> dict[str, Any]:
    """The public plan catalogue. No auth: the pricing page needs it."""
    return {
        "success": True,
        "plans": [
            {
                "code": p["code"],
                "name": p["name"],
                "price": p["price"],
                # Enterprise is quoted, not listed. Without these the pricing
                # table rendered it at $0 as "Free".
                "custom": p.get("custom", False),
                "cta": p.get("cta"),
                "tagline": p["tagline"],
                "features": p["features"],
                "limits": p["limits"],
            }
            for p in billing.PLANS.values()
        ],
    }


@router.get("/me")
async def my_billing(user_id: str = Depends(verify_user)) -> dict[str, Any]:
    """Current plan, subscription state and this month's usage."""
    return {"success": True, **(await billing.billing_summary(user_id))}


@router.post("/subscribe")
async def subscribe(
    data: SubscribeRequest,
    request: Request,
    user_id: str = Depends(verify_user),
) -> dict[str, Any]:
    """Start a recurring monthly subscription and return PayPal's approval URL.

    Nothing is granted here. Entitlement is only ever written by the webhook
    after PayPal confirms the money moved — a client that simply calls this
    endpoint gets an unapproved subscription and no access.
    """
    plan_code = (data.planCode or "").lower()
    plan = billing.PLANS.get(plan_code)
    if not plan:
        raise HTTPException(status_code=400, detail="Unknown plan.")
    if plan["price"] <= 0:
        raise HTTPException(status_code=400, detail="The free plan does not need a subscription.")

    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Account not found.")
        email = user.email

        existing = (await session.execute(
            select(Subscription)
            .where(Subscription.userId == user_id)
            .order_by(Subscription.createdAt.desc())
        )).scalars().first()

    if existing and existing.status == "ACTIVE" and existing.planCode == plan_code:
        raise HTTPException(status_code=400, detail=f"You are already on the {plan['name']} plan.")

    frontend = (settings.frontend_url or "").rstrip("/")
    result = await billing.create_paypal_subscription(
        user_id=user_id,
        user_email=email,
        plan_code=plan_code,
        return_url=f"{frontend}/dashboard/billing?subscribed=1",
        cancel_url=f"{frontend}/dashboard/billing?cancelled=1",
    )
    if not result or not result.get("approveUrl"):
        # Recurring billing needs the Subscriptions product enabled on the
        # PayPal app, and it is not. This used to raise a 502 saying "please
        # try again shortly", which was false — it will never succeed until
        # that is switched on — and it stopped the customer dead at the exact
        # moment they were trying to hand over money.
        #
        # The one-time order path works today and buys the same access for a
        # month, so send them there instead of nowhere. A sale that does not
        # auto-renew beats no sale.
        logger.warning(
            f"Recurring subscription unavailable for {user_id}; offering the "
            f"one-time checkout instead."
        )
        return {
            "success": False,
            "recurringUnavailable": True,
            "fallbackUrl": "/checkout",
            "message": (
                "Automatic monthly billing is not switched on yet. You can buy "
                "a month now — it will not renew on its own."
            ),
        }

    async with AsyncSessionLocal() as session:
        sub = Subscription(
            userId=user_id,
            planCode=plan_code,
            paypalSubscriptionId=result["subscriptionId"],
            paypalPlanId=result.get("paypalPlanId"),
            status="APPROVAL_PENDING",
        )
        session.add(sub)
        await session.commit()

    logger.info(f"Subscription {result['subscriptionId']} pending approval for user {user_id}")
    return {
        "success": True,
        "approveUrl": result["approveUrl"],
        "subscriptionId": result["subscriptionId"],
    }


@router.post("/sync")
async def sync_subscription(user_id: str = Depends(verify_user)) -> dict[str, Any]:
    """Reconcile against PayPal on demand.

    Webhooks can be delayed or lost, and a customer who has just paid should
    not be told to wait. This asks PayPal directly and is safe to call often.
    """
    sub = await billing.get_subscription(user_id)
    if not sub or not sub.paypalSubscriptionId:
        return {"success": True, "status": "NONE", **(await billing.billing_summary(user_id))}

    remote = await billing.fetch_paypal_subscription(sub.paypalSubscriptionId)
    if not remote:
        return {"success": True, **(await billing.billing_summary(user_id))}

    status = remote.get("status")
    next_billing = (remote.get("billing_info") or {}).get("next_billing_time")

    async with AsyncSessionLocal() as session:
        row = await session.get(Subscription, sub.id)
        if row:
            row.status = status or row.status
            if next_billing:
                try:
                    row.currentPeriodEnd = datetime.fromisoformat(
                        next_billing.replace("Z", "+00:00")
                    )
                except ValueError:
                    pass
            await session.commit()

        # Keep the legacy flag in step so older checks stay correct.
        user = await session.get(User, user_id)
        if user:
            user.subscriptionStatus = "ACTIVE" if status == "ACTIVE" else "INACTIVE"
            await session.commit()

    return {"success": True, **(await billing.billing_summary(user_id))}


@router.post("/cancel")
async def cancel(user_id: str = Depends(verify_user)) -> dict[str, Any]:
    """Cancel at PayPal. Access continues until the period already paid for ends."""
    sub = await billing.get_subscription(user_id)
    if not sub or not sub.paypalSubscriptionId or sub.status not in ("ACTIVE", "SUSPENDED"):
        raise HTTPException(status_code=400, detail="There is no active subscription to cancel.")

    ok = await billing.cancel_paypal_subscription(sub.paypalSubscriptionId)
    if not ok:
        raise HTTPException(
            status_code=502,
            detail="PayPal did not accept the cancellation. Please try again, or cancel from your PayPal account.",
        )

    async with AsyncSessionLocal() as session:
        row = await session.get(Subscription, sub.id)
        if row:
            row.cancelAtPeriodEnd = True
            row.status = "CANCELLED"
            await session.commit()

    logger.info(f"Subscription cancelled for user {user_id}")
    return {
        "success": True,
        "message": (
            "Subscription cancelled. You keep access until the end of the period "
            "you have already paid for."
        ),
    }

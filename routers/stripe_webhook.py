"""
Stripe Checkout & Webhook Router
Handles creating checkout sessions and processing Stripe webhook events
with proper signature verification.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select

from config import settings
from database import AsyncSessionLocal, User
from routers.auth import verify_user

router = APIRouter(prefix="/api/v1/stripe", tags=["Stripe"])


class CreateCheckoutRequest(BaseModel):
    price_id: str | None = None


@router.post("/create-checkout-session")
async def create_checkout_session(data: CreateCheckoutRequest, user_id: str = Depends(verify_user)):
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Stripe is not configured")

    import stripe
    stripe.api_key = settings.stripe_secret_key

    async with AsyncSessionLocal() as session:
        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

    frontend_url = settings.allowed_origins[0] if settings.allowed_origins else "https://organic-marketing-ai.vercel.app"

    try:
        checkout = stripe.checkout.Session.create(
            mode="subscription",
            payment_method_types=["card"],
            line_items=[{
                "price": data.price_id or settings.stripe_price_id,
                "quantity": 1,
            }],
            success_url=f"{frontend_url}/dashboard?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{frontend_url}/checkout?cancelled=true",
            client_reference_id=user_id,
            customer_email=user.email if user else None,
        )
        return {"url": checkout.url, "session_id": checkout.id}
    except Exception as e:
        logger.error(f"Stripe checkout creation failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to create checkout session")


@router.post("/webhook")
async def stripe_webhook(request: Request):
    if not settings.stripe_secret_key or not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Stripe webhooks not configured")

    import stripe
    stripe.api_key = settings.stripe_secret_key

    payload = await request.body()
    sig = request.headers.get("stripe-signature")

    if not sig:
        raise HTTPException(status_code=400, detail="Missing Stripe signature header")

    try:
        event = stripe.Webhook.construct_event(payload, sig, settings.stripe_webhook_secret)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=403, detail="Invalid Stripe signature")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook error: {e}")

    if event["type"] == "checkout.session.completed":
        session_data = event["data"]["object"]
        user_id = session_data.get("client_reference_id")
        if user_id:
            async with AsyncSessionLocal() as db:
                user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
                if user:
                    user.subscriptionStatus = "ACTIVE"
                    await db.commit()
                    logger.info(f"Stripe subscription activated for user {user_id}")

    elif event["type"] == "customer.subscription.deleted":
        sub = event["data"]["object"]
        customer_email = sub.get("customer_email") or sub.get("metadata", {}).get("email")
        if customer_email:
            async with AsyncSessionLocal() as db:
                user = (await db.execute(select(User).where(User.email == customer_email))).scalar_one_or_none()
                if user:
                    user.subscriptionStatus = "INACTIVE"
                    await db.commit()
                    logger.info(f"Stripe subscription cancelled for {customer_email}")

    return {"received": True}

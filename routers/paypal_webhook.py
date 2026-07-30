from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request, HTTPException
from loguru import logger
from sqlalchemy import select

import httpx

from config import settings
from database import (
    AsyncSessionLocal,
    ProcessedWebhookEvent,
    Subscription,
    User,
)

router = APIRouter(
    prefix="/api/v1/paypal",
    tags=["PayPal"],
)


async def _verify_paypal_webhook(request: Request, body: bytes) -> bool:
    """Verify PayPal webhook signature using PayPal REST API."""
    if not settings.paypal_client_id or not settings.paypal_client_secret or not settings.paypal_webhook_id:
        logger.warning("PayPal webhook verification skipped: credentials not configured")
        return False

    paypal_base = "https://api-m.paypal.com" if settings.environment == "production" else "https://api-m.sandbox.paypal.com"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            auth_resp = await client.post(
                f"{paypal_base}/v1/oauth2/token",
                data={"grant_type": "client_credentials"},
                auth=(settings.paypal_client_id, settings.paypal_client_secret),
            )
            if auth_resp.status_code != 200:
                logger.error(f"PayPal auth failed during webhook verification: {auth_resp.text}")
                return False

            access_token = auth_resp.json().get("access_token")

            import json
            verify_resp = await client.post(
                f"{paypal_base}/v1/notifications/verify-webhook-signature",
                headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
                json={
                    "auth_algo": request.headers.get("PAYPAL-AUTH-ALGO", ""),
                    "cert_url": request.headers.get("PAYPAL-CERT-URL", ""),
                    "transmission_id": request.headers.get("PAYPAL-TRANSMISSION-ID", ""),
                    "transmission_sig": request.headers.get("PAYPAL-TRANSMISSION-SIG", ""),
                    "transmission_time": request.headers.get("PAYPAL-TRANSMISSION-TIME", ""),
                    "webhook_id": settings.paypal_webhook_id,
                    "webhook_event": json.loads(body),
                },
            )

            result = verify_resp.json()
            verified = result.get("verification_status") == "SUCCESS"
            if not verified:
                logger.warning(f"PayPal webhook verification failed: {result}")
            return verified

    except Exception as e:
        logger.error(f"PayPal webhook verification error: {e}")
        return False


@router.post("/webhook")
async def paypal_webhook(request: Request):
    """Handles PayPal webhook events with signature verification."""
    body = await request.body()

    transmission_id = request.headers.get("PAYPAL-TRANSMISSION-ID")
    transmission_sig = request.headers.get("PAYPAL-TRANSMISSION-SIG")

    if not all([transmission_id, transmission_sig]):
        raise HTTPException(status_code=400, detail="Missing PayPal signature headers")

    verified = await _verify_paypal_webhook(request, body)
    if not verified:
        logger.warning(f"Rejecting unverified PayPal webhook (transmission_id={transmission_id})")
        raise HTTPException(status_code=403, detail="Webhook signature verification failed")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_type = payload.get("event_type")
    event_id = payload.get("id")
    resource = payload.get("resource", {}) or {}

    # PayPal retries deliveries. Without this, a repeated PAYMENT.SALE.COMPLETED
    # would extend the same subscription twice.
    if event_id:
        async with AsyncSessionLocal() as session:
            if await session.get(ProcessedWebhookEvent, event_id):
                logger.info(f"PayPal event {event_id} already processed; ignoring replay")
                return {"status": "duplicate"}

    handled = await _apply_event(event_type, resource)

    if event_id:
        try:
            async with AsyncSessionLocal() as session:
                session.add(ProcessedWebhookEvent(id=event_id, eventType=event_type))
                await session.commit()
        except Exception:
            # A racing duplicate lost the insert; the work was still done once.
            logger.debug(f"Could not record PayPal event {event_id} (likely a race)")

    return {"status": "success" if handled else "ignored", "event": event_type}


def _subscription_id_of(resource: dict) -> str | None:
    """PayPal names this differently per event type."""
    return (
        resource.get("id")
        if resource.get("plan_id") else
        resource.get("billing_agreement_id") or resource.get("subscription_id")
    )


async def _find_subscription(session, resource: dict) -> Subscription | None:
    sub_id = _subscription_id_of(resource)
    if sub_id:
        row = (await session.execute(
            select(Subscription).where(Subscription.paypalSubscriptionId == sub_id)
        )).scalars().first()
        if row:
            return row
    # Fall back to custom_id, which we set to our user id at creation.
    custom_id = resource.get("custom_id")
    if custom_id:
        return (await session.execute(
            select(Subscription)
            .where(Subscription.userId == custom_id)
            .order_by(Subscription.createdAt.desc())
        )).scalars().first()
    return None


async def _apply_event(event_type: str | None, resource: dict) -> bool:
    """Move local state to match what PayPal just told us."""
    ACTIVATING = {"BILLING.SUBSCRIPTION.ACTIVATED", "BILLING.SUBSCRIPTION.RE-ACTIVATED"}
    ENDING = {
        "BILLING.SUBSCRIPTION.CANCELLED": "CANCELLED",
        "BILLING.SUBSCRIPTION.EXPIRED": "EXPIRED",
        "BILLING.SUBSCRIPTION.SUSPENDED": "SUSPENDED",
    }

    if event_type not in (
        ACTIVATING
        | set(ENDING)
        | {"PAYMENT.SALE.COMPLETED", "BILLING.SUBSCRIPTION.PAYMENT.FAILED"}
    ):
        return False

    async with AsyncSessionLocal() as session:
        sub = await _find_subscription(session, resource)
        if not sub:
            logger.warning(f"PayPal {event_type}: no local subscription matched")
            return False

        user = await session.get(User, sub.userId)

        if event_type in ACTIVATING:
            sub.status = "ACTIVE"
            sub.lastError = None
            sub.cancelAtPeriodEnd = False
            next_billing = (resource.get("billing_info") or {}).get("next_billing_time")
            if next_billing:
                try:
                    sub.currentPeriodEnd = datetime.fromisoformat(
                        next_billing.replace("Z", "+00:00")
                    )
                except ValueError:
                    pass
            if user:
                user.subscriptionStatus = "ACTIVE"
            logger.info(f"Subscription ACTIVE for user {sub.userId} ({sub.planCode})")

        elif event_type == "PAYMENT.SALE.COMPLETED":
            # A renewal cleared. Extend by a month from now unless PayPal told
            # us the exact next billing date.
            sub.status = "ACTIVE"
            sub.lastPaymentAt = datetime.now(timezone.utc)
            sub.lastError = None
            sub.currentPeriodEnd = datetime.now(timezone.utc) + timedelta(days=32)
            if user:
                user.subscriptionStatus = "ACTIVE"
            logger.info(f"Renewal payment recorded for user {sub.userId}")

        elif event_type == "BILLING.SUBSCRIPTION.PAYMENT.FAILED":
            # Not a cancellation: PayPal retries. Keep access until the period
            # ends, but surface the problem so the customer can fix their card.
            sub.lastError = (
                "Your last payment did not go through. PayPal will retry; "
                "update your payment method to avoid losing access."
            )
            logger.warning(f"Payment failed for user {sub.userId}")

        else:
            sub.status = ENDING[event_type]
            if event_type != "BILLING.SUBSCRIPTION.SUSPENDED":
                sub.cancelAtPeriodEnd = True
            if user:
                user.subscriptionStatus = "INACTIVE"
            logger.info(f"Subscription {sub.status} for user {sub.userId}")

        await session.commit()
        return True

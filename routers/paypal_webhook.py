from fastapi import APIRouter, Request, HTTPException
from loguru import logger
from sqlalchemy import select

import httpx

from config import settings
from database import AsyncSessionLocal, User

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

    if event_type in ["BILLING.SUBSCRIPTION.ACTIVATED", "PAYMENT.SALE.COMPLETED"]:
        resource = payload.get("resource", {})
        custom_id = resource.get("custom_id")

        if not custom_id:
            logger.warning(f"PayPal webhook {event_type} received but no custom_id found.")
            return {"status": "ignored", "reason": "no custom_id"}

        async with AsyncSessionLocal() as session:
            stmt = select(User).where(User.id == custom_id).with_for_update()
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()

            if user:
                if user.subscriptionStatus != "ACTIVE":
                    user.subscriptionStatus = "ACTIVE"
                    await session.commit()
                    logger.info(f"Subscription activated for user {custom_id} via PayPal webhook")
                else:
                    logger.info(f"Subscription already ACTIVE for user {custom_id} (idempotent)")
                return {"status": "success"}
            else:
                logger.error(f"User not found for custom_id {custom_id}")
                return {"status": "error", "reason": "user not found"}

    return {"status": "ignored"}

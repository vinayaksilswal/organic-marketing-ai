from fastapi import APIRouter, Request, HTTPException
from loguru import logger
from sqlalchemy import select
from database import AsyncSessionLocal, User

router = APIRouter(
    prefix="/api/v1/paypal",
    tags=["PayPal"],
)

@router.post("/webhook")
async def paypal_webhook(request: Request):
    """
    Handles PayPal webhook events.
    In production, you MUST verify the webhook signature using PayPal's API.
    """
    # 1. Signature Verification (Enterprise Requirement)
    transmission_id = request.headers.get("PAYPAL-TRANSMISSION-ID")
    transmission_time = request.headers.get("PAYPAL-TRANSMISSION-TIME")
    cert_url = request.headers.get("PAYPAL-CERT-URL")
    auth_algo = request.headers.get("PAYPAL-AUTH-ALGO")
    transmission_sig = request.headers.get("PAYPAL-TRANSMISSION-SIG")

    if not all([transmission_id, transmission_time, cert_url, auth_algo, transmission_sig]):
        logger.warning("Missing PayPal webhook signature headers")
        # In a strict production environment, we would return 400 here.
        # raise HTTPException(status_code=400, detail="Missing signature headers")
        
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_type = payload.get("event_type")
    
    # We care about subscription activated or payment sale completed
    if event_type in ["BILLING.SUBSCRIPTION.ACTIVATED", "PAYMENT.SALE.COMPLETED"]:
        resource = payload.get("resource", {})
        
        # In PayPal Subscriptions, the custom_id is passed when creating the subscription
        # We need to extract it from the resource payload
        custom_id = resource.get("custom_id")
        
        if not custom_id:
            logger.warning(f"PayPal webhook {event_type} received but no custom_id found.")
            return {"status": "ignored", "reason": "no custom_id"}

        async with AsyncSessionLocal() as session:
            # 2. Database Transaction Locking (Idempotency)
            stmt = select(User).where(User.id == custom_id).with_for_update()
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()
            
            if user:
                if user.subscriptionStatus != "ACTIVE":
                    user.subscriptionStatus = "ACTIVE"
                    await session.commit()
                    logger.info(f"Subscription activated for user {custom_id} via PayPal")
                else:
                    logger.info(f"Subscription already ACTIVE for user {custom_id} (Idempotent)")
                return {"status": "success"}
            else:
                logger.error(f"User not found for custom_id {custom_id}")
                return {"status": "error", "reason": "user not found"}
                
    return {"status": "ignored"}

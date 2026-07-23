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
    For MVP, we extract the event type and update the user.
    """
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
            stmt = select(User).where(User.id == custom_id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()
            
            if user:
                user.subscriptionStatus = "ACTIVE"
                await session.commit()
                logger.info(f"Subscription activated for user {custom_id} via PayPal")
                return {"status": "success"}
            else:
                logger.error(f"User not found for custom_id {custom_id}")
                return {"status": "error", "reason": "user not found"}
                
    return {"status": "ignored"}

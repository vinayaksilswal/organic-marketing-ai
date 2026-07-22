from fastapi import APIRouter, Request, HTTPException
from loguru import logger
import stripe
from sqlalchemy import select
from config import settings
from database import AsyncSessionLocal, User

router = APIRouter(
    prefix="/api/v1/stripe",
    tags=["Stripe"],
)

stripe.api_key = getattr(settings, "stripe_secret_key", "")
STRIPE_WEBHOOK_SECRET = getattr(settings, "stripe_webhook_secret", "")

@router.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")

    if not sig_header or not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=400, detail="Invalid Stripe configuration or signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        logger.error("Invalid Stripe payload")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid Stripe signature")
        raise HTTPException(status_code=400, detail="Invalid signature")

    async with AsyncSessionLocal() as session:
        if event['type'] == 'checkout.session.completed':
            evt_session = event['data']['object']
            customer_id = evt_session.get('customer')
            subscription_id = evt_session.get('subscription')
            client_reference_id = evt_session.get('client_reference_id')

            if client_reference_id:
                stmt = select(User).where(User.id == client_reference_id)
                res = await session.execute(stmt)
                user = res.scalar_one_or_none()
                if user:
                    user.subscriptionStatus = "ACTIVE"
                    await session.commit()
                    logger.info(f"Subscription activated for user {client_reference_id}")

        elif event['type'] == 'customer.subscription.deleted':
            subscription = event['data']['object']
            customer_id = subscription.get('customer')

            stmt = select(User).where(User.id == customer_id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()
            if user:
                user.subscriptionStatus = "INACTIVE"
                await session.commit()
                logger.info(f"Subscription canceled for user {user.id}")

    return {"status": "success"}

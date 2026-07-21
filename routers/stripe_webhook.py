from fastapi import APIRouter, Request, HTTPException, Depends
from loguru import logger
import stripe
from config import settings

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
    except ValueError as e:
        logger.error("Invalid Stripe payload")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        logger.error("Invalid Stripe signature")
        raise HTTPException(status_code=400, detail="Invalid signature")

    prisma = request.app.state.prisma

    # Handle the event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        customer_id = session.get('customer')
        subscription_id = session.get('subscription')
        client_reference_id = session.get('client_reference_id') # Usually the user ID

        if client_reference_id:
            await prisma.user.update(
                where={"id": client_reference_id},
                data={
                    "stripeCustomerId": customer_id,
                    "stripeSubscriptionId": subscription_id,
                    "subscriptionStatus": "ACTIVE",
                    "subscriptionPlan": "PRO"
                }
            )
            logger.info(f"Subscription activated for user {client_reference_id}")

    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        customer_id = subscription.get('customer')
        
        user = await prisma.user.find_first(where={"stripeCustomerId": customer_id})
        if user:
            await prisma.user.update(
                where={"id": user.id},
                data={
                    "subscriptionStatus": "CANCELLED"
                }
            )
            logger.info(f"Subscription cancelled for user {user.id}")

    elif event['type'] == 'invoice.payment_failed':
        invoice = event['data']['object']
        customer_id = invoice.get('customer')
        
        user = await prisma.user.find_first(where={"stripeCustomerId": customer_id})
        if user:
            await prisma.user.update(
                where={"id": user.id},
                data={
                    "subscriptionStatus": "INACTIVE"
                }
            )
            logger.warning(f"Payment failed for user {user.id}, subscription marked INACTIVE")

    return {"status": "success"}

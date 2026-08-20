from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta, timezone
import asyncio
import httpx
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from loguru import logger

# Pricing for the single paid plan. The PayPal order is built client-side, so
# the server must independently enforce what a valid payment looks like.
PLAN_PRICE = 17.00
PLAN_CURRENCY = "USD"

from config import settings
from database import (
    AsyncSessionLocal, User, BusinessProfile, SocialConnection,
    Media, SocialPost, SocialCampaign, EmailCampaign, MarketingLog,
    MarketingState, Product, Audience, VideoApiConfig, TeamMember,
    Subscription,
)
from routers.auth import verify_user, verify_workspace_access
from services.onboarding_service import OnboardingService
from services.crypto_service import encrypt_token, decrypt_token

router = APIRouter(
    prefix="/api/v1/users/me",
    tags=["User API"],
    dependencies=[Depends(verify_user), Depends(verify_workspace_access)],
)

businesses_router = APIRouter(
    prefix="/api/v1/businesses",
    tags=["Businesses"],
    dependencies=[Depends(verify_user), Depends(verify_workspace_access)],
)

class BusinessProfileUpdate(BaseModel):
    name: Optional[str] = None
    websiteUrl: Optional[str] = None
    description: Optional[str] = None
    businessModel: Optional[str] = None
    logoUrl: Optional[str] = None
    productCatalogUrl: Optional[str] = None
    influencerReferenceUrl: Optional[str] = None
    niche: Optional[str] = None
    primaryOffer: Optional[str] = None
    postIntervalHours: Optional[int] = None
    automationPaused: Optional[bool] = None
    creativeGenerationIntervalHours: Optional[int] = None
    autoGenerateCreatives: Optional[bool] = None
    # When this workspace may post. Null on any field means no restriction.
    postingDays: Optional[list[int]] = None
    postingStartHour: Optional[int] = None
    postingEndHour: Optional[int] = None
    postingTimezone: Optional[str] = None

class SocialConnectionUpdate(BaseModel):
    fbAccessToken: Optional[str] = None
    fbPageId: Optional[str] = None
    fbPageName: Optional[str] = None
    igAccountId: Optional[str] = None
    igAccountName: Optional[str] = None
    twitterAccessToken: Optional[str] = None
    twitterAccessSecret: Optional[str] = None
    linkedinAccessToken: Optional[str] = None

@router.get("")
async def get_current_user(request: Request, user_id: str = Depends(verify_user)):
    try:
        async with AsyncSessionLocal() as session:
            workspace_id = request.headers.get("x-workspace-id")

            stmt = (
                select(User)
                .where(User.id == user_id)
                .options(
                    selectinload(User.businessProfiles),
                    selectinload(User.socialConnections),
                )
            )
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()

            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            if not user.businessProfiles or len(user.businessProfiles) == 0:
                default_profile = BusinessProfile(
                    userId=user.id,
                    name="Default Workspace",
                    websiteUrl="https://organicmarketing.ai",
                    description="Default automated growth & marketing workspace",
                    businessModel="SaaS",
                )
                session.add(default_profile)
                await session.commit()

                stmt = select(User).where(User.id == user_id).options(
                    selectinload(User.businessProfiles),
                    selectinload(User.socialConnections),
                ).execution_options(populate_existing=True)
                res = await session.execute(stmt)
                user = res.scalar_one_or_none()

            profiles_data = []
            for bp in (user.businessProfiles or []):
                created_str = bp.createdAt.isoformat() if getattr(bp, "createdAt", None) else None
                profiles_data.append({
                    "id": str(bp.id),
                    "name": getattr(bp, "name", None) or "Default Workspace",
                    "websiteUrl": getattr(bp, "websiteUrl", None),
                    "description": getattr(bp, "description", None),
                    "businessModel": getattr(bp, "businessModel", None) or "General",
                    "postIntervalHours": getattr(bp, "postIntervalHours", 2),
                    "automationPaused": bool(getattr(bp, "automationPaused", False)),
                    "publishingMode": getattr(bp, "publishingMode", "PUBLIC") or "PUBLIC",
                    "postingDays": getattr(bp, "postingDays", None),
                    "postingStartHour": getattr(bp, "postingStartHour", None),
                    "postingEndHour": getattr(bp, "postingEndHour", None),
                    "postingTimezone": getattr(bp, "postingTimezone", None),
                    "industry": getattr(bp, "industry", None),
                    "targetAudience": getattr(bp, "targetAudience", None),
                    "toneOfVoice": getattr(bp, "toneOfVoice", None),
                    "contentPillars": getattr(bp, "contentPillars", None) or [],
                    "suggestedHashtags": getattr(bp, "suggestedHashtags", None) or [],
                    "brandAnalysisComplete": bool(getattr(bp, "brandAnalysisComplete", False)),
                    "createdAt": created_str,
                })

            social_data = None
            connections = getattr(user, "socialConnections", None) or []
            active_conn = next(
                (c for c in connections if getattr(c, "businessProfileId", None) == workspace_id),
                connections[0] if connections else None,
            )
            if active_conn:
                social_data = {
                    "id": str(active_conn.id),
                    "fbPageId": getattr(active_conn, "fbPageId", None),
                    "fbPageName": getattr(active_conn, "fbPageName", None),
                    "igAccountId": getattr(active_conn, "igAccountId", None),
                    "igAccountName": getattr(active_conn, "igAccountName", None),
                    "hasTwitter": bool(getattr(active_conn, "twitterAccessToken", None)),
                    "hasLinkedin": bool(getattr(active_conn, "linkedinAccessToken", None)),
                }

            return {
                "id": str(user.id),
                "email": user.email,
                "subscriptionStatus": getattr(user, "subscriptionStatus", "INACTIVE"),
                "businessProfile": profiles_data[0] if profiles_data else None,
                "businessProfiles": profiles_data,
                "socialConnection": social_data,
                "createdAt": user.createdAt.isoformat() if getattr(user, "createdAt", None) else None,
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error in get_current_user: {e}")
        raise HTTPException(status_code=500, detail=f"User profile error: {str(e)}")

@router.post("/business-profile")
async def update_business_profile_post(
    data: BusinessProfileUpdate, request: Request, user_id: str = Depends(verify_user)
):
    profile = await OnboardingService.update_business_profile(user_id, data.model_dump(exclude_unset=True))

    return {
        "success": True,
        "data": {
            "id": profile.id,
            "name": profile.name,
            "websiteUrl": profile.websiteUrl,
            "description": profile.description,
            "businessModel": profile.businessModel,
            "productCatalogUrl": profile.productCatalogUrl,
            "postIntervalHours": profile.postIntervalHours,
            "creativeGenerationIntervalHours": profile.creativeGenerationIntervalHours,
            "autoGenerateCreatives": profile.autoGenerateCreatives,
            "postingDays": profile.postingDays,
            "postingStartHour": profile.postingStartHour,
            "postingEndHour": profile.postingEndHour,
            "postingTimezone": profile.postingTimezone,
        },
    }

@router.post("/social-connection")
async def update_social_connection(
    data: SocialConnectionUpdate, request: Request, user_id: str = Depends(verify_user)
):
    workspace_id = request.headers.get("x-workspace-id")
    async with AsyncSessionLocal() as session:
        stmt = select(SocialConnection).where(
            SocialConnection.userId == user_id,
            SocialConnection.businessProfileId == workspace_id,
        )
        res = await session.execute(stmt)
        conn = res.scalars().first()

        if conn:
            if data.fbAccessToken is not None:
                conn.fbAccessToken = encrypt_token(data.fbAccessToken)
            if data.fbPageId is not None:
                conn.fbPageId = data.fbPageId
            if data.fbPageName is not None:
                conn.fbPageName = data.fbPageName
            if data.igAccountId is not None:
                conn.igAccountId = data.igAccountId
            if data.igAccountName is not None:
                conn.igAccountName = data.igAccountName
            if data.twitterAccessToken is not None:
                conn.twitterAccessToken = encrypt_token(data.twitterAccessToken) if data.twitterAccessToken else None
            if data.twitterAccessSecret is not None:
                conn.twitterAccessSecret = encrypt_token(data.twitterAccessSecret) if data.twitterAccessSecret else None
            if data.linkedinAccessToken is not None:
                conn.linkedinAccessToken = encrypt_token(data.linkedinAccessToken) if data.linkedinAccessToken else None
        else:
            conn = SocialConnection(
                userId=user_id,
                businessProfileId=workspace_id,
                fbAccessToken=encrypt_token(data.fbAccessToken) if data.fbAccessToken else None,
                fbPageId=data.fbPageId,
                fbPageName=data.fbPageName,
                igAccountId=data.igAccountId,
                igAccountName=data.igAccountName,
                twitterAccessToken=encrypt_token(data.twitterAccessToken) if data.twitterAccessToken else None,
                twitterAccessSecret=encrypt_token(data.twitterAccessSecret) if data.twitterAccessSecret else None,
                linkedinAccessToken=encrypt_token(data.linkedinAccessToken) if data.linkedinAccessToken else None,
            )
            session.add(conn)

        await session.commit()
        await session.refresh(conn)

        return {
            "success": True,
            "data": {
                "id": conn.id,
                "fbPageId": conn.fbPageId,
                "fbPageName": conn.fbPageName,
                "igAccountId": conn.igAccountId,
                "igAccountName": conn.igAccountName,
                "hasTwitter": bool(conn.twitterAccessToken),
                "hasLinkedin": bool(conn.linkedinAccessToken),
            },
        }

@router.get("/onboarding-status")
async def get_onboarding_status(request: Request, user_id: str = Depends(verify_user)):
    async with AsyncSessionLocal() as session:
        stmt = select(BusinessProfile).where(BusinessProfile.userId == user_id).order_by(BusinessProfile.createdAt.desc())
        res = await session.execute(stmt)
        profile = res.scalars().first()
        if not profile:
            return {"brandAnalysisComplete": False, "profile": None}

        # The final onboarding screen showed a hardcoded summary -- "Tone:
        # Enterprise Professional", the same four content pillars -- to every
        # business that ever signed up, under a heading saying we had analysed
        # theirs. The analysis is real; it was simply never read back. These
        # are the actual stored values.
        return {
            "brandAnalysisComplete": profile.brandAnalysisComplete,
            "profile": {
                "id": profile.id,
                "name": profile.name,
                "industry": profile.industry,
                "businessModel": profile.businessModel,
                "toneOfVoice": profile.toneOfVoice,
                "targetAudience": profile.targetAudience,
                "contentPillars": profile.contentPillars or [],
                "suggestedHashtags": profile.suggestedHashtags or [],
                "primaryOffer": profile.primaryOffer,
                "postIntervalHours": profile.postIntervalHours,
                "autoGenerateCreatives": profile.autoGenerateCreatives,
                "automationPaused": profile.automationPaused,
                "websiteUrl": profile.websiteUrl,
            },
        }

class SubscribeRequest(BaseModel):
    order_id: str

@router.post("/subscribe")
async def activate_subscription(data: SubscribeRequest, request: Request, user_id: str = Depends(verify_user)):
    """Activate subscription after verifying PayPal payment."""
    if not settings.paypal_client_id or not settings.paypal_client_secret:
        raise HTTPException(status_code=503, detail="Payment verification not configured")

    paypal_base = "https://api-m.paypal.com" if settings.environment == "production" else "https://api-m.sandbox.paypal.com"

    async with httpx.AsyncClient(timeout=15.0) as client:
        auth_resp = await client.post(
            f"{paypal_base}/v1/oauth2/token",
            data={"grant_type": "client_credentials"},
            auth=(settings.paypal_client_id, settings.paypal_client_secret),
        )
        if auth_resp.status_code != 200:
            logger.error(f"PayPal auth failed: {auth_resp.text}")
            raise HTTPException(status_code=502, detail="Payment verification failed")

        access_token = auth_resp.json().get("access_token")

        order_resp = await client.get(
            f"{paypal_base}/v2/checkout/orders/{data.order_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if order_resp.status_code != 200:
            raise HTTPException(status_code=402, detail="Payment order not found")

        order = order_resp.json()
        if order.get("status") != "COMPLETED":
            raise HTTPException(status_code=402, detail="Payment not completed")

        # The PayPal order is created client-side, so the amount it carries is
        # attacker-controlled. Verify the captured total actually covers the plan.
        captured = 0.0
        currency = None
        for unit in order.get("purchase_units", []):
            for capture in (unit.get("payments", {}) or {}).get("captures", []):
                if capture.get("status") == "COMPLETED":
                    amount = capture.get("amount", {})
                    captured += float(amount.get("value", 0))
                    currency = currency or amount.get("currency_code")

        if currency != PLAN_CURRENCY or captured + 0.01 < PLAN_PRICE:
            logger.warning(
                f"Underpaid subscription attempt by user {user_id}: "
                f"order {data.order_id} captured {captured} {currency}, expected {PLAN_PRICE} {PLAN_CURRENCY}"
            )
            raise HTTPException(
                status_code=402,
                detail=f"Payment of {PLAN_PRICE:.2f} {PLAN_CURRENCY} is required to activate this plan.",
            )

    async with AsyncSessionLocal() as session:
        # A completed order may only ever activate one account.
        claimed = (await session.execute(
            select(User).where(User.paypalOrderId == data.order_id)
        )).scalar_one_or_none()
        if claimed and claimed.id != user_id:
            logger.warning(f"Replayed PayPal order {data.order_id} by user {user_id}")
            raise HTTPException(status_code=409, detail="This payment has already been used to activate an account.")

        stmt = select(User).where(User.id == user_id)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user.subscriptionStatus = "ACTIVE"
        user.paypalOrderId = data.order_id

        # Grant the plan they actually paid for.
        #
        # This endpoint only ever set User.subscriptionStatus, which is a
        # boolean "did someone pay once". Every limit in the product is read
        # from active_plan_code(), and that reads the Subscription table -- so
        # a customer could pay $17, be marked ACTIVE, and still be held to the
        # free plan's 5 posts and 10 media. They would have paid for nothing
        # and the first they would know is a quota message.
        #
        # A one-time order is not a recurring subscription, so it buys a fixed
        # window rather than open-ended access. 31 days, after which
        # active_plan_code() sees a lapsed period and falls back to free by
        # itself -- no cron, no reconciliation, nothing to forget.
        now = datetime.now(timezone.utc)
        sub = (await session.execute(
            select(Subscription).where(Subscription.userId == user_id)
        )).scalars().first()
        if sub is None:
            sub = Subscription(userId=user_id)
            session.add(sub)
        sub.planCode = "starter"
        sub.status = "ACTIVE"
        sub.currentPeriodEnd = now + timedelta(days=31)
        sub.lastPaymentAt = now
        sub.cancelAtPeriodEnd = True  # it does not renew; nothing will charge again
        sub.lastError = None

        try:
            await session.commit()
        except IntegrityError:
            # Lost a race against a concurrent claim of the same order
            await session.rollback()
            raise HTTPException(status_code=409, detail="This payment has already been used to activate an account.")

        logger.info(f"Subscription activated for user {user_id} via PayPal order {data.order_id}")
        return {"success": True, "message": "Subscription activated successfully"}


# =============================================================================
# Multi-Tenant Businesses / Workspaces Router
# =============================================================================
@businesses_router.get("")
@businesses_router.get("/")
async def get_user_businesses(request: Request, user_id: str = Depends(verify_user)):
    """List all business profiles (workspaces) with their social connections."""
    try:
        async with AsyncSessionLocal() as session:
            stmt = (
                select(BusinessProfile)
                .options(selectinload(BusinessProfile.socialconnections))
                .where(BusinessProfile.userId == user_id)
                .order_by(BusinessProfile.createdAt.asc())
            )
            res = await session.execute(stmt)
            bps = res.scalars().all()

            result = []
            for bp in bps:
                conns = getattr(bp, "socialconnections", None) or []
                sc = conns[0] if conns else None
                created_str = bp.createdAt.isoformat() if getattr(bp, "createdAt", None) else None
                result.append({
                    "id": str(bp.id),
                    "name": getattr(bp, "name", None) or "Default Workspace",
                    "websiteUrl": getattr(bp, "websiteUrl", None),
                    "description": getattr(bp, "description", None),
                    "businessModel": getattr(bp, "businessModel", None) or "General",
                    "logoUrl": getattr(bp, "logoUrl", None),
                    "productCatalogUrl": getattr(bp, "productCatalogUrl", None),
                    "influencerReferenceUrl": getattr(bp, "influencerReferenceUrl", None),
                    "niche": getattr(bp, "niche", None),
                    "primaryOffer": getattr(bp, "primaryOffer", None),
                    "postIntervalHours": getattr(bp, "postIntervalHours", 2),
                    "automationPaused": bool(getattr(bp, "automationPaused", False)),
                    "publishingMode": getattr(bp, "publishingMode", "PUBLIC") or "PUBLIC",
                    "creativeGenerationIntervalHours": getattr(bp, "creativeGenerationIntervalHours", 2),
                    "autoGenerateCreatives": bool(getattr(bp, "autoGenerateCreatives", True)),
                    "brandAnalysisComplete": bool(getattr(bp, "brandAnalysisComplete", False)),
                    "industry": getattr(bp, "industry", None),
                    "targetAudience": getattr(bp, "targetAudience", None),
                    "toneOfVoice": getattr(bp, "toneOfVoice", None),
                    "createdAt": created_str,
                    "socialConnection": {
                        "fbPageId": getattr(sc, "fbPageId", None),
                        "fbPageName": getattr(sc, "fbPageName", None),
                        "igAccountId": getattr(sc, "igAccountId", None),
                        "igAccountName": getattr(sc, "igAccountName", None),
                        "hasTwitter": bool(getattr(sc, "twitterAccessToken", None)),
                        "hasLinkedin": bool(getattr(sc, "linkedinAccessToken", None)),
                        "hasFacebook": bool(getattr(sc, "fbAccessToken", None)),
                    } if sc else None,
                })
            return result
    except Exception as e:
        logger.exception(f"Error in get_user_businesses: {e}")
        raise HTTPException(status_code=500, detail=f"Businesses query error: {str(e)}")

@businesses_router.post("")
@businesses_router.post("/")
async def create_user_business(data: BusinessProfileUpdate, request: Request, user_id: str = Depends(verify_user)):
    """Create a new business workspace entity."""
    # Businesses are a standing total rather than a monthly meter, so count
    # what exists rather than reading a usage counter.
    from services import billing_service as billing
    from sqlalchemy import func as sa_func

    async with AsyncSessionLocal() as session:
        owned = (await session.execute(
            select(sa_func.count(BusinessProfile.id)).where(BusinessProfile.userId == user_id)
        )).scalar() or 0
    allowed, why = await billing.check_business_quota(user_id, owned)
    if not allowed:
        raise HTTPException(status_code=402, detail=why)

    try:
        profile = await OnboardingService.create_business_profile(user_id, data.model_dump(exclude_unset=True))

        return {
            "success": True,
            "data": {
                "id": profile.id,
                "name": profile.name,
                "websiteUrl": profile.websiteUrl,
                "description": profile.description,
                "businessModel": profile.businessModel,
                "productCatalogUrl": getattr(profile, "productCatalogUrl", None),
                "influencerReferenceUrl": getattr(profile, "influencerReferenceUrl", None),
                "brandAnalysisComplete": False,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create workspace: {str(e)}")


@businesses_router.delete("/{workspace_id}")
async def delete_business(workspace_id: str, request: Request, user_id: str = Depends(verify_user)):
    """Delete a workspace and every record belonging to it.

    Children are removed explicitly rather than relying on ORM cascade: an async
    session.delete() would lazy-load each relationship and raise MissingGreenlet,
    and older rows may predate the ondelete='CASCADE' constraints.
    """
    async with AsyncSessionLocal() as session:
        bp = await session.get(BusinessProfile, workspace_id)
        if not bp or bp.userId != user_id:
            raise HTTPException(status_code=404, detail="Workspace not found")

        name = bp.name
        for model in (
            Media, SocialPost, SocialCampaign, EmailCampaign, MarketingLog,
            MarketingState, Product, Audience, SocialConnection, VideoApiConfig,
            TeamMember,
        ):
            await session.execute(
                delete(model).where(model.businessProfileId == workspace_id)
            )
        await session.execute(
            delete(BusinessProfile).where(BusinessProfile.id == workspace_id)
        )
        await session.commit()
        logger.info(f"Deleted workspace {workspace_id} ({name}) for user {user_id}")

        return {"success": True, "message": f"'{name}' and all its data were deleted."}


@businesses_router.patch("/{workspace_id}")
async def update_business(workspace_id: str, data: BusinessProfileUpdate, request: Request, user_id: str = Depends(verify_user)):
    """Update any fields on a workspace the user owns."""
    async with AsyncSessionLocal() as session:
        bp = await session.get(BusinessProfile, workspace_id)
        if not bp or bp.userId != user_id:
            raise HTTPException(status_code=404, detail="Workspace not found")

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(bp, field):
                setattr(bp, field, value)

        await session.commit()
        await session.refresh(bp)

        return {
            "success": True,
            "data": {
                "id": bp.id,
                "name": bp.name,
                "websiteUrl": bp.websiteUrl,
                "description": bp.description,
                "businessModel": bp.businessModel,
                "logoUrl": bp.logoUrl,
                "productCatalogUrl": bp.productCatalogUrl,
                "influencerReferenceUrl": bp.influencerReferenceUrl,
                "postIntervalHours": bp.postIntervalHours,
                "automationPaused": bool(getattr(bp, "automationPaused", False)),
                "automationPaused": bool(getattr(bp, "automationPaused", False)),
                "creativeGenerationIntervalHours": bp.creativeGenerationIntervalHours,
                "autoGenerateCreatives": bp.autoGenerateCreatives,
            },
        }

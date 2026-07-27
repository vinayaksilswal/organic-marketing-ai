from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
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
)
from routers.auth import verify_user
from services.onboarding_service import OnboardingService
from services.crypto_service import encrypt_token, decrypt_token

router = APIRouter(
    prefix="/api/v1/users/me",
    tags=["User API"],
    dependencies=[Depends(verify_user)],
)

businesses_router = APIRouter(
    prefix="/api/v1/businesses",
    tags=["Businesses"],
    dependencies=[Depends(verify_user)],
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
    postIntervalHours: Optional[int] = None
    creativeGenerationIntervalHours: Optional[int] = None
    autoGenerateCreatives: Optional[bool] = None

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

        profiles_data = [
            {
                "id": bp.id,
                "name": bp.name or "Default Workspace",
                "websiteUrl": bp.websiteUrl,
                "description": bp.description,
                "businessModel": bp.businessModel or "General",
                "postIntervalHours": bp.postIntervalHours,
                "industry": bp.industry,
                "targetAudience": bp.targetAudience,
                "toneOfVoice": bp.toneOfVoice,
                "contentPillars": bp.contentPillars,
                "suggestedHashtags": bp.suggestedHashtags,
                "brandAnalysisComplete": bp.brandAnalysisComplete,
                "createdAt": bp.createdAt.isoformat() if bp.createdAt else None,
            }
            for bp in user.businessProfiles
        ]

        social_data = None
        active_conn = next(
            (c for c in user.socialConnections if c.businessProfileId == workspace_id),
            user.socialConnections[0] if user.socialConnections else None,
        )
        if active_conn:
            social_data = {
                "id": active_conn.id,
                "fbPageId": active_conn.fbPageId,
                "fbPageName": active_conn.fbPageName,
                "igAccountId": active_conn.igAccountId,
                "igAccountName": active_conn.igAccountName,
                "hasTwitter": bool(active_conn.twitterAccessToken),
                "hasLinkedin": bool(active_conn.linkedinAccessToken),
            }

        return {
            "id": user.id,
            "email": user.email,
            "subscriptionStatus": user.subscriptionStatus,
            "businessProfile": profiles_data[0] if profiles_data else None,
            "businessProfiles": profiles_data,
            "socialConnection": social_data,
            "createdAt": user.createdAt.isoformat() if user.createdAt else None,
        }

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
            return {"brandAnalysisComplete": False}
        return {"brandAnalysisComplete": profile.brandAnalysisComplete}

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
    async with AsyncSessionLocal() as session:
        stmt = (
            select(BusinessProfile)
            .options(selectinload(BusinessProfile.socialconnections))
            .where(BusinessProfile.userId == user_id)
            .order_by(BusinessProfile.createdAt.asc())
        )
        res = await session.execute(stmt)
        bps = res.scalars().all()

        # New users start with zero businesses — the UI shows an empty state
        # prompting them to create their first one. Never auto-create.
        result = []
        for bp in bps:
            sc = bp.socialconnections[0] if bp.socialconnections else None
            result.append({
                "id": bp.id,
                "name": bp.name or "Default Workspace",
                "websiteUrl": bp.websiteUrl,
                "description": bp.description,
                "businessModel": bp.businessModel or "General",
                "logoUrl": bp.logoUrl,
                "productCatalogUrl": bp.productCatalogUrl,
                "influencerReferenceUrl": bp.influencerReferenceUrl,
                "niche": bp.niche,
                "postIntervalHours": bp.postIntervalHours,
                "creativeGenerationIntervalHours": bp.creativeGenerationIntervalHours,
                "autoGenerateCreatives": bp.autoGenerateCreatives,
                "brandAnalysisComplete": bp.brandAnalysisComplete,
                "industry": bp.industry,
                "targetAudience": bp.targetAudience,
                "toneOfVoice": bp.toneOfVoice,
                "createdAt": bp.createdAt.isoformat() if bp.createdAt else None,
                "socialConnection": {
                    "fbPageId": sc.fbPageId,
                    "fbPageName": sc.fbPageName,
                    "igAccountId": sc.igAccountId,
                    "igAccountName": sc.igAccountName,
                    "hasTwitter": bool(sc.twitterAccessToken),
                    "hasLinkedin": bool(sc.linkedinAccessToken),
                    "hasFacebook": bool(sc.fbAccessToken),
                } if sc else None,
            })
        return result

@businesses_router.post("")
@businesses_router.post("/")
async def create_user_business(data: BusinessProfileUpdate, request: Request, user_id: str = Depends(verify_user)):
    """Create a new business workspace entity."""
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
                "creativeGenerationIntervalHours": bp.creativeGenerationIntervalHours,
                "autoGenerateCreatives": bp.autoGenerateCreatives,
            },
        }

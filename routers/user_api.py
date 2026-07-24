from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
import asyncio
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database import AsyncSessionLocal, User, BusinessProfile, SocialConnection
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
        stmt = (
            select(User)
            .where(User.id == user_id)
            .options(
                selectinload(User.businessProfiles),
                selectinload(User.socialConnection),
            )
        )
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Auto-create Default Workspace if user has no business profiles
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
            
            # Re-fetch user with newly created profile
            stmt = select(User).where(User.id == user_id).options(
                selectinload(User.businessProfiles),
                selectinload(User.socialConnection),
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
        if user.socialConnection:
            social_data = {
                "id": user.socialConnection.id,
                "fbPageId": user.socialConnection.fbPageId,
                "fbPageName": user.socialConnection.fbPageName,
                "igAccountId": user.socialConnection.igAccountId,
                "igAccountName": user.socialConnection.igAccountName,
                "hasTwitter": bool(user.socialConnection.twitterAccessToken),
                "hasLinkedin": bool(user.socialConnection.linkedinAccessToken),
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
    async with AsyncSessionLocal() as session:
        stmt = select(SocialConnection).where(SocialConnection.userId == user_id)
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

@router.post("/subscribe")
async def activate_subscription(request: Request, user_id: str = Depends(verify_user)):
    """Activate subscription status for the current user."""
    async with AsyncSessionLocal() as session:
        stmt = select(User).where(User.id == user_id)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user.subscriptionStatus = "ACTIVE"
        await session.commit()
        return {"success": True, "message": "Subscription activated successfully"}


# =============================================================================
# Multi-Tenant Businesses / Workspaces Router
# =============================================================================
@businesses_router.get("")
@businesses_router.get("/")
async def get_user_businesses(request: Request, user_id: str = Depends(verify_user)):
    """List all business profiles (workspaces) for the user."""
    async with AsyncSessionLocal() as session:
        stmt = select(BusinessProfile).where(BusinessProfile.userId == user_id).order_by(BusinessProfile.createdAt.asc())
        res = await session.execute(stmt)
        bps = res.scalars().all()

        if not bps:
            default_profile = BusinessProfile(
                userId=user_id,
                name="Default Workspace",
                websiteUrl="https://organicmarketing.ai",
                description="Default automated growth & marketing workspace",
                businessModel="SaaS",
            )
            session.add(default_profile)
            await session.commit()
            await session.refresh(default_profile)
            bps = [default_profile]

        return [
            {
                "id": bp.id,
                "name": bp.name or "Default Workspace",
                "websiteUrl": bp.websiteUrl,
                "description": bp.description,
                "businessModel": bp.businessModel or "General",
                "productCatalogUrl": bp.productCatalogUrl,
                "postIntervalHours": bp.postIntervalHours,
                "creativeGenerationIntervalHours": bp.creativeGenerationIntervalHours,
                "autoGenerateCreatives": bp.autoGenerateCreatives,
                "createdAt": bp.createdAt.isoformat() if bp.createdAt else None,
            }
            for bp in bps
        ]

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

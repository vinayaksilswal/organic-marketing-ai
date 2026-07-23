from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
import asyncio
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database import AsyncSessionLocal, User, BusinessProfile, SocialConnection
from routers.auth import verify_user
from services.creative_service import auto_populate_workspace

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

class SocialConnectionUpdate(BaseModel):
    fbAccessToken: Optional[str] = None
    fbPageId: Optional[str] = None
    fbPageName: Optional[str] = None
    igAccountId: Optional[str] = None
    igAccountName: Optional[str] = None

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
            )
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
    async with AsyncSessionLocal() as session:
        stmt = select(BusinessProfile).where(BusinessProfile.userId == user_id)
        res = await session.execute(stmt)
        profile = res.scalars().first()

        if profile:
            if data.name is not None:
                profile.name = data.name
            if data.websiteUrl is not None:
                profile.websiteUrl = data.websiteUrl
            if data.description is not None:
                profile.description = data.description
            if data.businessModel is not None:
                profile.businessModel = data.businessModel
        else:
            profile = BusinessProfile(
                userId=user_id,
                name=data.name or "Default Workspace",
                websiteUrl=data.websiteUrl,
                description=data.description,
                businessModel=data.businessModel,
            )
            session.add(profile)

        await session.commit()
        await session.refresh(profile)

        # Trigger AI brand analysis in the background
        asyncio.create_task(auto_populate_workspace(user_id, profile.id))

        return {
            "success": True,
            "data": {
                "id": profile.id,
                "name": profile.name,
                "websiteUrl": profile.websiteUrl,
                "description": profile.description,
                "businessModel": profile.businessModel,
            },
        }

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
                "postIntervalHours": bp.postIntervalHours,
                "createdAt": bp.createdAt.isoformat() if bp.createdAt else None,
            }
            for bp in bps
        ]

@businesses_router.post("")
@businesses_router.post("/")
async def create_user_business(data: BusinessProfileUpdate, request: Request, user_id: str = Depends(verify_user)):
    """Create a new business workspace entity."""
    try:
        async with AsyncSessionLocal() as session:
            profile = BusinessProfile(
                userId=user_id,
                name=data.name or "New Workspace",
                websiteUrl=data.websiteUrl,
                description=data.description,
                businessModel=data.businessModel or "General",
            )
            session.add(profile)
            await session.commit()
            await session.refresh(profile)

            # Trigger AI brand analysis + starter creative generation in background
            asyncio.create_task(auto_populate_workspace(user_id, profile.id))

            return {
                "success": True,
                "data": {
                    "id": profile.id,
                    "name": profile.name,
                    "websiteUrl": profile.websiteUrl,
                    "description": profile.description,
                    "businessModel": profile.businessModel,
                    "brandAnalysisComplete": False,
                },
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create workspace: {str(e)}")


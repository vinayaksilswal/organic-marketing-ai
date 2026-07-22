from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database import AsyncSessionLocal, User, BusinessProfile, SocialConnection
from routers.auth import verify_user

router = APIRouter(
    prefix="/api/v1/users/me",
    tags=["User API"],
    dependencies=[Depends(verify_user)],
)

class BusinessProfileUpdate(BaseModel):
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
                selectinload(User.businessProfile),
                selectinload(User.socialConnection),
            )
        )
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        profile_data = None
        if user.businessProfile:
            profile_data = {
                "id": user.businessProfile.id,
                "websiteUrl": user.businessProfile.websiteUrl,
                "description": user.businessProfile.description,
                "businessModel": user.businessProfile.businessModel,
            }

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
            "businessProfile": profile_data,
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
        profile = res.scalar_one_or_none()

        if profile:
            if data.websiteUrl is not None:
                profile.websiteUrl = data.websiteUrl
            if data.description is not None:
                profile.description = data.description
            if data.businessModel is not None:
                profile.businessModel = data.businessModel
        else:
            profile = BusinessProfile(
                userId=user_id,
                websiteUrl=data.websiteUrl,
                description=data.description,
                businessModel=data.businessModel,
            )
            session.add(profile)

        await session.commit()
        await session.refresh(profile)
        return {
            "success": True,
            "data": {
                "id": profile.id,
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

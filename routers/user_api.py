from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
from routers.auth import verify_user, get_prisma

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
    prisma = await get_prisma(request)
    user = await prisma.user.find_unique(
        where={"id": user_id},
        include={"businessProfile": True, "socialConnection": True}
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Do not leak hashed password
    user_data = user.model_dump()
    user_data.pop("password", None)
    return user_data

@router.post("/business-profile")
async def update_business_profile_post(data: BusinessProfileUpdate, request: Request, user_id: str = Depends(verify_user)):
    prisma = await get_prisma(request)
    profile = await prisma.businessprofile.upsert(
        where={"userId": user_id},
        data={
            "create": {
                "userId": user_id,
                "websiteUrl": data.websiteUrl,
                "description": data.description,
                "businessModel": data.businessModel
            },
            "update": {
                "websiteUrl": data.websiteUrl,
                "description": data.description,
                "businessModel": data.businessModel
            }
        }
    )
    return {"success": True, "data": profile.model_dump()}

@router.put("/business-profile")
async def update_business_profile(data: BusinessProfileUpdate, request: Request, user_id: str = Depends(verify_user)):
    return await update_business_profile_post(data, request, user_id)

@router.post("/subscribe")
async def activate_subscription(request: Request, user_id: str = Depends(verify_user)):
    prisma = request.app.state.prisma
    
    # Mocking successful payment update
    user = await prisma.user.update(
        where={"id": user_id},
        data={
            "subscriptionPlan": "PRO",
            "subscriptionStatus": "ACTIVE"
        }
    )
    return {"success": True, "message": "Subscription activated successfully"}

@router.get("/social-connection")
async def get_social_connection(request: Request, user_id: str = Depends(verify_user)):
    prisma = request.app.state.prisma
    conn = await prisma.socialconnection.find_unique(where={"userId": user_id})
    return {"success": True, "data": conn.model_dump() if conn else None}

@router.put("/social-connection")
async def update_social_connection(data: SocialConnectionUpdate, request: Request, user_id: str = Depends(verify_user)):
    prisma = request.app.state.prisma
    conn = await prisma.socialconnection.upsert(
        where={"userId": user_id},
        data={
            "create": {
                "userId": user_id,
                "fbAccessToken": data.fbAccessToken,
                "fbPageId": data.fbPageId,
                "fbPageName": data.fbPageName,
                "igAccountId": data.igAccountId,
                "igAccountName": data.igAccountName
            },
            "update": {
                "fbAccessToken": data.fbAccessToken,
                "fbPageId": data.fbPageId,
                "fbPageName": data.fbPageName,
                "igAccountId": data.igAccountId,
                "igAccountName": data.igAccountName
            }
        }
    )
    return {"success": True, "data": conn.model_dump()}

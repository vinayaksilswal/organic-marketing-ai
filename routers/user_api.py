from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from typing import Optional
from routers.auth import verify_user

router = APIRouter(
    prefix="/api/v1/user",
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

@router.get("/business-profile")
async def get_business_profile(request: Request, user_id: str = Depends(verify_user)):
    prisma = request.app.state.prisma
    profile = await prisma.businessprofile.find_unique(where={"userId": user_id})
    return {"success": True, "data": profile.model_dump() if profile else None}

@router.put("/business-profile")
async def update_business_profile(data: BusinessProfileUpdate, request: Request, user_id: str = Depends(verify_user)):
    prisma = request.app.state.prisma
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

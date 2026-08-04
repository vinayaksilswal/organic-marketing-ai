"""
Team Management Router — invite, list, update, remove workspace members.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from database import AsyncSessionLocal, TeamMember, BusinessProfile, User
from routers.auth import verify_user, verify_workspace_access

router = APIRouter(
    prefix="/api/v1/team",
    tags=["Team Management"],
    dependencies=[Depends(verify_user), Depends(verify_workspace_access)],
)


class InviteRequest(BaseModel):
    email: str
    role: str = "editor"


class UpdateRoleRequest(BaseModel):
    role: str


@router.get("")
async def list_team_members(request: Request, user_id: str = Depends(verify_user)):
    workspace_id = request.headers.get("x-workspace-id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="X-Workspace-Id header required")

    async with AsyncSessionLocal() as session:
        stmt = select(TeamMember).where(TeamMember.businessProfileId == workspace_id)
        members = (await session.execute(stmt)).scalars().all()

        return [
            {
                "id": m.id,
                "email": m.email,
                "role": m.role,
                "status": m.status,
                "invitedAt": m.invitedAt.isoformat() if m.invitedAt else None,
                "acceptedAt": m.acceptedAt.isoformat() if m.acceptedAt else None,
            }
            for m in members
        ]


@router.post("")
async def invite_team_member(data: InviteRequest, request: Request, user_id: str = Depends(verify_user)):
    workspace_id = request.headers.get("x-workspace-id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="X-Workspace-Id header required")

    if data.role not in ("admin", "editor", "viewer"):
        raise HTTPException(status_code=400, detail="Role must be admin, editor, or viewer")

    async with AsyncSessionLocal() as session:
        bp = (await session.execute(
            select(BusinessProfile).where(BusinessProfile.id == workspace_id, BusinessProfile.userId == user_id)
        )).scalar_one_or_none()
        if not bp:
            raise HTTPException(status_code=403, detail="Only workspace owners can invite members")

        existing = (await session.execute(
            select(TeamMember).where(
                TeamMember.businessProfileId == workspace_id,
                TeamMember.email == data.email.strip().lower(),
            )
        )).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="This email is already invited")

        invited_user = (await session.execute(
            select(User).where(User.email == data.email.strip().lower())
        )).scalar_one_or_none()

        member = TeamMember(
            businessProfileId=workspace_id,
            userId=invited_user.id if invited_user else None,
            email=data.email.strip().lower(),
            role=data.role,
            status="active" if invited_user else "pending",
            acceptedAt=datetime.now(timezone.utc) if invited_user else None,
        )
        session.add(member)
        await session.commit()
        await session.refresh(member)

        return {
            "success": True,
            "member": {
                "id": member.id,
                "email": member.email,
                "role": member.role,
                "status": member.status,
            },
        }


@router.patch("/{member_id}")
async def update_team_member_role(
    member_id: str, data: UpdateRoleRequest, request: Request, user_id: str = Depends(verify_user)
):
    workspace_id = request.headers.get("x-workspace-id")
    if data.role not in ("admin", "editor", "viewer"):
        raise HTTPException(status_code=400, detail="Role must be admin, editor, or viewer")

    async with AsyncSessionLocal() as session:
        member = (await session.execute(
            select(TeamMember).where(TeamMember.id == member_id, TeamMember.businessProfileId == workspace_id)
        )).scalar_one_or_none()
        if not member:
            raise HTTPException(status_code=404, detail="Team member not found")

        member.role = data.role
        await session.commit()
        return {"success": True}


@router.delete("/{member_id}")
async def remove_team_member(member_id: str, request: Request, user_id: str = Depends(verify_user)):
    workspace_id = request.headers.get("x-workspace-id")

    async with AsyncSessionLocal() as session:
        member = (await session.execute(
            select(TeamMember).where(TeamMember.id == member_id, TeamMember.businessProfileId == workspace_id)
        )).scalar_one_or_none()
        if not member:
            raise HTTPException(status_code=404, detail="Team member not found")

        await session.delete(member)
        await session.commit()
        return {"success": True}

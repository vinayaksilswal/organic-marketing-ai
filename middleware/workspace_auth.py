"""
Workspace authorization dependency — verifies the current user owns or
has access to the workspace specified in X-Workspace-Id.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select

from database import AsyncSessionLocal, BusinessProfile, TeamMember
from routers.auth import verify_user


async def verify_workspace_access(request: Request, user_id: str = Depends(verify_user)) -> str:
    """
    Verify the authenticated user has access to the workspace in X-Workspace-Id.
    Returns the workspace_id on success, raises 403 otherwise.
    """
    workspace_id = request.headers.get("x-workspace-id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="X-Workspace-Id header is required")

    async with AsyncSessionLocal() as session:
        bp = (await session.execute(
            select(BusinessProfile).where(
                BusinessProfile.id == workspace_id,
                BusinessProfile.userId == user_id,
            )
        )).scalar_one_or_none()

        if bp:
            return workspace_id

        team = (await session.execute(
            select(TeamMember).where(
                TeamMember.businessProfileId == workspace_id,
                TeamMember.userId == user_id,
                TeamMember.status == "active",
            )
        )).scalar_one_or_none()

        if team:
            return workspace_id

    raise HTTPException(status_code=403, detail="You do not have access to this workspace")

import asyncio
from database import init_db, AsyncSessionLocal, User, BusinessProfile
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import uuid

async def main():
    await init_db()
    async with AsyncSessionLocal() as session:
        user_id = str(uuid.uuid4())
        u = User(id=user_id, email=f"test_{user_id}@test.com", password="pwd")
        session.add(u)
        await session.commit()
        
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
        print("User:", user)

        if not user.businessProfiles or len(user.businessProfiles) == 0:
            print("Creating default profile")
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
                selectinload(User.socialConnection),
            ).execution_options(populate_existing=True)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()
            print("User re-fetched:", user)
        
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
        print(profiles_data)

asyncio.run(main())
